# -*- coding: utf-8 -*-
"""VoIP → Care Command projection.

What changed, and why the old shape was wrong
----------------------------------------------

The previous bridge ran on ``voip.call.log.create`` — once, at creation, before
anything was known. Three consequences, each of which cost real work:

* it projected **before matching**, so a call that later resolved to a patient
  had already been filed against a bare phone number;
* it projected **before finalisation**, so a record corrected by a later
  delivery (the ring group's winner, a transfer, a re-sent CDR) never updated;
* **every** outgoing call set ``waiting`` and zeroed unread, which clears the
  missed-call flag and the unread count for WhatsApp, Zalo and email too. Ring
  a patient about a completed appointment and their unanswered Zalo message
  quietly stopped being unread.

So projection now happens from the effect outbox — after the call is settled,
after the contact is matched, and again on a meaningful correction — and it
changes call-related state **narrowly**. It never touches another channel's
work, and a late record about an old call cannot reopen newer work, because the
session carries a watermark of what has already been projected.

``_voip_project_session`` is the seam ``health_voip24h``'s worker calls when it
exists. Core checks with ``hasattr``, so a deployment without Care Command
behaves as if this file were absent.
"""

import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)

# Incoming outcomes where the customer reached out and we never spoke to them.
_MISSED_LIKE = ('missed', 'abandoned', 'busy', 'failed', 'voicemail',
                'no_answer', 'unknown')


class VoipCallSessionBridge(models.Model):
    _inherit = 'voip.call.session'

    care_conversation_id = fields.Many2one(
        'care.conversation', string='Care Command Conversation',
        ondelete='set null', index=True, readonly=True)

    # ------------------------------------------------------------------

    def _voip_project_session(self, reason='final', projection_version=0):
        """Project this settled interaction into Care Command. Idempotent.

        Called from ``voip.call.effect`` delivery, so a failure here is a
        retry rather than a lost provider event — the old create-hook swallowed
        its exception and the conversation update was simply gone.
        """
        self.ensure_one()
        try:
            with self.env.cr.savepoint():
                return self._do_project(reason, projection_version)
        except Exception:
            _logger.exception(
                'care_command: projection failed for voip call %s', self.id)
            raise

    def _do_project(self, reason, projection_version):
        # Live states are awareness only. A ringing phone is not yet a work
        # item, and turning one into a conversation would put every abandoned
        # dial on the wall.
        if reason in ('ringing', 'answered'):
            return False
        if not self.is_final and reason != 'final':
            return False
        if self.direction == 'internal':
            # Internal telephony history. No patient conversation, ever.
            return False

        event_at = self.ended_at or self.started_at or fields.Datetime.now()

        # The watermark is what stops a late, older record from reopening work
        # somebody has since dealt with.
        if self.care_watermark and event_at < self.care_watermark:
            _logger.info('care_command: ignoring an older record for voip call '
                         '%s (event %s < watermark %s)',
                         self.id, event_at, self.care_watermark)
            return False

        Care = self.env['care.conversation']
        anchor = {
            'partner_id': self.partner_id.id or False,
            'lead_id': self.lead_id.id or False,
            'phone_normalized': Care._safe_phone(self.external_peer_key
                                                 or self.external_peer_raw),
        }
        if not anchor['phone_normalized'] and self.external_peer_raw:
            # `_safe_phone` refuses anything the Vietnamese helper cannot
            # parse — an international caller, a short code. The raw number is
            # still something a person can ring back, so it is kept.
            anchor['phone_normalized'] = self.external_peer_raw.strip()[:32] or False

        if not any(anchor.values()):
            self._capture_unrouted()
            return False

        # Resolve the existing thread BEFORE deciding what to say about it.
        # The status this call may set depends on what other channels are
        # already waiting on, and `_find_or_create_for` would have applied the
        # signal before we could look.
        existing = self._existing_conversation(anchor)
        signal = self._call_signal(event_at, existing)
        conversation = Care._find_or_create_for(anchor, signal)
        self.sudo().write({
            'care_conversation_id': conversation.id,
            'care_watermark': event_at,
        })
        return conversation

    def _existing_conversation(self, anchor):
        """The thread this call belongs to, if there already is one.

        Same precedence as ``care.conversation._find_or_create_for`` uses, but
        read-only: nothing is created and no signal is applied.
        """
        Conversation = self.env['care.conversation'].sudo()
        company = self.company_id or self.env.company
        for key in ('partner_id', 'lead_id', 'phone_normalized'):
            value = anchor.get(key)
            if not value:
                continue
            found = Conversation.search(
                [('company_id', '=', company.id), (key, '=', value)], limit=1)
            if found:
                return found
        return Conversation.browse()

    def _call_signal(self, event_at, existing=None):
        """The narrow signal one call is entitled to send.

        ``unread`` is ``keep`` in every branch. The old bridge sent ``zero`` on
        every outgoing call, and ``care.conversation._apply_signal`` zeroes
        unread and clears the missed-call and watch flags whenever the status
        becomes ``waiting`` — so ringing somebody wiped their unanswered
        messages on every other channel too.
        """
        answered = self.outcome == 'answered' or any(
            leg.outcome == 'answered' for leg in self.leg_ids)

        if self.direction == 'outgoing':
            if answered and self.talk_seconds:
                # We reached them. This closes the call obligation only; any
                # other channel's unread work is none of this call's business.
                return {
                    'channel': 'call',
                    'inbound': False,
                    'event_at': event_at,
                    'set_status': (None if self._other_channel_work(existing)
                                   else 'waiting'),
                    'unread': 'keep',
                }
            # An attempt. Nothing is resolved by a call that did not connect.
            return {
                'channel': 'call',
                'inbound': False,
                'event_at': event_at,
                'unread': 'keep',
            }

        if answered:
            # Answered incoming: a real interaction, but not one awaiting a
            # reply — so no invented status change on an existing thread.
            return {
                'channel': 'call',
                'inbound': True,
                'event_at': event_at,
                'unread': 'keep',
            }

        # They rang and we did not speak to them.
        return {
            'channel': 'call',
            'inbound': True,
            'event_at': event_at,
            'set_status': 'needs_reply',
            'missed_call': True,
            'unread': 'keep',
        }

    def _other_channel_work(self, conversation=None):
        """Is there work on this thread that this call did not resolve?

        If there is, the call does not get to declare the thread "waiting" —
        ``_apply_signal`` zeroes unread and clears the missed-call and watch
        flags on that transition, and this call never touched the WhatsApp,
        Zalo or email message that raised them.
        """
        self.ensure_one()
        conversation = conversation if conversation is not None \
            else self.care_conversation_id
        if not conversation:
            return False
        if conversation.unread_count:
            return True
        last_inbound = conversation.last_inbound_at
        reference = self.ended_at or self.started_at
        if last_inbound and reference and last_inbound > reference:
            return True
        return False

    def _capture_unrouted(self):
        """A caller with no number at all still has to be visible somewhere."""
        self.ensure_one()
        if 'care.contact.capture' not in self.env:
            return
        self.env['care.contact.capture']._capture(
            'unmatched_call', 'call',
            peer_hint=self.external_peer_raw or '',
            body=self.outcome or '',
            external_event_id='voip.call.session:%s' % self.id,
            occurred_at=self.started_at)


class VoipCallLogBridge(models.Model):
    """The legacy create-hook, kept for the legacy ingest path only.

    ``voip.call.log`` rows created by the v3 reducer carry a ``session_id`` and
    are projected from the session above, after matching and finalisation. Rows
    from the old signed webhook or the polling path have no session, and this
    keeps them working exactly as they did.
    """
    _inherit = 'voip.call.log'

    @api.model_create_multi
    def create(self, vals_list):
        logs = super().create(vals_list)
        for log in logs:
            if log.session_id:
                # The session owns the projection. Doing it here as well is how
                # a clinic ends up with two call-back tasks for one call.
                continue
            try:
                with self.env.cr.savepoint():
                    self._care_ingest_call(log)
            except Exception:
                _logger.exception(
                    'care_command: voip.call.log ingest failed (log %s)', log.id)
        return logs

    def _care_ingest_call(self, log):
        Care = self.env['care.conversation']
        customer_number = (
            log.called_number_normalized if log.direction == 'outgoing'
            else log.caller_number_normalized)
        anchor = {
            'partner_id': log.partner_id.id or False,
            'lead_id': log.lead_id.id or False,
            'phone_normalized': Care._safe_phone(customer_number),
        }
        if not anchor['phone_normalized']:
            raw = (log.called_number if log.direction == 'outgoing'
                   else log.caller_number)
            anchor['phone_normalized'] = (raw or '').strip()[:32] or False

        if not any(anchor.values()):
            if 'care.contact.capture' in self.env:
                self.env['care.contact.capture']._capture(
                    'unmatched_call', 'call',
                    peer_hint=log.caller_number or log.called_number,
                    body=log.call_type or '',
                    external_event_id='voip.call.log:%s' % log.id,
                    occurred_at=log.call_date)
            return

        if log.direction == 'outgoing':
            # Only a call that actually CONNECTED closes the obligation. The
            # old hook set `waiting` on EVERY outgoing log, so a busy tone or
            # a no-answer cleared the missed-call flag and dropped the
            # customer off the wall without anyone having spoken to them.
            #
            # `unread` is `keep`, never `zero`: ringing somebody must not mark
            # their unanswered WhatsApp, Zalo or email as read. When the
            # status does become `waiting`, `_apply_signal` zeroes unread by
            # its own rule — which is exactly why `_other_work_pending` below
            # decides whether this call is entitled to set it at all.
            connected = (log.call_type == 'answered'
                         and (log.talk_duration_seconds or 0) > 0)
            signal = {
                'channel': 'call',
                'inbound': False,
                'event_at': log.call_date,
                'unread': 'keep',
            }
            if connected:
                existing = self._legacy_existing_conversation(log, anchor)
                if not self._legacy_other_work(existing, log):
                    signal['set_status'] = 'waiting'
        elif log.direction == 'incoming' and log.call_type in _MISSED_LIKE:
            signal = {
                'channel': 'call',
                'inbound': True,
                'event_at': log.call_date,
                'set_status': 'needs_reply',
                'missed_call': True,
                'unread': 'keep',
            }
        else:
            signal = {
                'channel': 'call',
                'inbound': log.direction == 'incoming',
                'event_at': log.call_date,
                'unread': 'keep',
            }
        Care._find_or_create_for(anchor, signal)

    def _legacy_existing_conversation(self, log, anchor):
        """The thread this legacy call belongs to, read-only."""
        Conversation = self.env['care.conversation'].sudo()
        company = log.company_id or self.env.company
        for key in ('partner_id', 'lead_id', 'phone_normalized'):
            value = anchor.get(key)
            if not value:
                continue
            found = Conversation.search(
                [('company_id', '=', company.id), (key, '=', value)], limit=1)
            if found:
                return found
        return Conversation.browse()

    @staticmethod
    def _legacy_other_work(conversation, log):
        """Is there work this call did not resolve? Then it may not say
        "waiting" — that transition clears flags this call never raised."""
        if not conversation:
            return False
        if conversation.unread_count:
            return True
        last_inbound = conversation.last_inbound_at
        return bool(last_inbound and log.call_date and last_inbound > log.call_date)


class VoipConfigBridge(models.Model):
    """Where a Channel Center owns the setup, its store owns the secrets.

    Core ships its own cipher so a standalone install still works. When the
    Channel Center is present it is the tenant's single place for provider
    credentials, so the backend is pointed there and secrets written by this
    deployment land in the store the operator already administers.
    """
    _inherit = 'voip.config'

    def _voip_secret_backend(self):
        connection = self._channel_connection()
        if connection:
            from odoo.addons.health_care_command_channels.services import (  # noqa: PLC0415
                channel_crypto,
            )
            return channel_crypto
        return super()._voip_secret_backend()


class CareConversationCallBridge(models.Model):
    _inherit = 'care.conversation'

    @api.model
    def resolve_incoming_call(self, payload):
        """Map a live ringing notification to an existing conversation.

        Unchanged in purpose; what changes is the payload it now receives. The
        bus no longer carries a caller's number to every signed-in browser, so
        the lookup starts from the call session — which the reader must already
        be allowed to see — and falls back to the number only for the legacy
        path.
        """
        self._ensure_access()
        payload = payload or {}
        session_id = payload.get('session_id')
        if session_id and 'voip.call.session' in self.env:
            session = self.env['voip.call.session'].browse(int(session_id))
            if session.exists():
                # Reading it through the user's own recordset is the access
                # check: a session outside their scope simply is not there.
                conversation = session.care_conversation_id
                if conversation:
                    return {'conv_id': conversation.id,
                            'name': conversation.display_name_c}
                payload = dict(payload, partner_id=session.partner_id.id or False,
                               lead_id=session.lead_id.id or False,
                               caller_number=session.external_peer_key or '')
        return super().resolve_incoming_call(payload)
