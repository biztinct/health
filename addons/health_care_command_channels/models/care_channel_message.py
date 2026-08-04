# -*- coding: utf-8 -*-
"""ONE message store for every adapter channel + the single ingest funnel
(architecture §5.6, phase6 §2.3).

Shape generalised from ``zalo.message``: one row per provider message, both
directions, with the raw payload kept behind ACLs and NEVER in the logger.

Two rules do the heavy lifting:

1. **Idempotency is structural.** Meta redelivers aggressively; a partial
   unique index on ``(connection_id, external_message_id)`` plus a pre-check in
   the funnel means a redelivered event produces one row, one conversation and
   no second unread bump (ledger §5.3 — pre-check, because letting the index
   fire would poison the webhook transaction).
2. **The conversation upsert runs inside ``cr.savepoint()``** (ledger §5.55): a
   database-level error while touching the spine must not abort the webhook's
   own transaction, and the message row must survive even if the spine write
   fails.
"""
import json
import logging
import uuid
from datetime import timedelta

from odoo import _, api, fields, models

from ..services.redact import redact
from .care_channel_connection import INGESTABLE_STATES

_logger = logging.getLogger(__name__)

DIRECTIONS = [('incoming', 'Incoming'), ('outgoing', 'Outgoing')]

MESSAGE_TYPES = [
    ('text', 'Text'),
    ('image', 'Image'),
    ('file', 'File'),
    ('location', 'Location'),
    ('other', 'Other'),
]

STATES = [
    ('received', 'Received'),
    ('queued', 'Queued'),
    ('sent', 'Sent'),
    ('delivered', 'Delivered'),
    ('read', 'Read'),
    ('failed', 'Failed'),
]

# Provider status names → our state, for the WhatsApp `statuses` events.
STATUS_MAP = {'sent': 'sent', 'delivered': 'delivered', 'read': 'read',
              'failed': 'failed'}

BODY_CAP = 4000

# Web chat is a PUBLIC surface: everything about it is bounded.
WEBCHAT_TEXT_CAP = 2000
WEBCHAT_POLL_CAP = 100
WEBCHAT_GC_DAYS = 7


class CareChannelMessage(models.Model):
    _name = 'care.channel.message'
    _description = 'Care Channel Message'
    _order = 'event_at asc, id asc'

    connection_id = fields.Many2one(
        'care.channel.connection', required=True, index=True,
        ondelete='restrict')
    channel = fields.Selection(
        related='connection_id.channel', store=True, index=True, readonly=True)
    company_id = fields.Many2one(
        related='connection_id.company_id', store=True, index=True,
        readonly=True)
    catchment_province_id = fields.Many2one(
        related='connection_id.catchment_province_id', store=True, index=True,
        readonly=True, string='Catchment Area')
    identity_id = fields.Many2one(
        'care.channel.identity', required=True, index=True,
        ondelete='restrict')
    conversation_id = fields.Many2one(
        'care.conversation', index=True, ondelete='set null')

    external_message_id = fields.Char(
        index=True,
        help='wamid… / Messenger mid / "<chat_id>:<message_id>" / webchat uuid.')
    direction = fields.Selection(DIRECTIONS, required=True, index=True)
    message_type = fields.Selection(MESSAGE_TYPES, default='text')
    body = fields.Text()

    # Metadata ONLY — v1 downloads no media (binding non-goal).
    attachment_url = fields.Char()
    attachment_name = fields.Char()
    attachment_mime = fields.Char()

    raw_payload = fields.Text(
        help='json.dumps of the provider event. Behind ACLs; never logged.')
    state = fields.Selection(STATES, default='received', index=True)
    error_message = fields.Char()
    event_at = fields.Datetime(required=True, index=True,
                               default=fields.Datetime.now)

    def init(self):
        # §5.1 + phase6 §2.3 — the webhook-redelivery dedupe contract.
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
                care_channel_message_conn_extid_uniq
            ON care_channel_message (connection_id, external_message_id)
            WHERE external_message_id IS NOT NULL
        """)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @api.model
    def _existing(self, connection, external_message_id):
        if not external_message_id:
            return self.browse()
        return self.sudo().search([
            ('connection_id', '=', connection.id),
            ('external_message_id', '=', external_message_id)], limit=1)

    @staticmethod
    def _dump(payload):
        try:
            return json.dumps(payload, default=str)[:60000]
        except (TypeError, ValueError):
            return False

    # ------------------------------------------------------------------
    # THE single inbound funnel (phase6 §2.3)
    # ------------------------------------------------------------------
    @api.model
    def _ingest_inbound(self, connection, event):
        """Land one normalised inbound event. Idempotent, savepoint-isolated.

        ``event`` is what ``adapter.parse_inbound`` produces: ``external_id``,
        ``external_message_id``, ``text``, ``peer_name``, ``message_type``,
        ``attachment``, ``event_at``, ``raw``.
        """
        connection.ensure_one()
        existing = self._existing(connection, event.get('external_message_id'))
        if existing:
            # Redelivery: one row, one conversation, no second unread bump.
            return existing

        Care = self.env['care.conversation']
        ident = self.env['care.channel.identity']._upsert(
            connection, event.get('external_id'), event.get('peer_name'),
            when=event.get('event_at'))
        if not ident:
            _logger.info('care_channels: inbound with no external id on '
                         'connection %s — captured', connection.id)
            # Nothing vanishes: without a sender id we cannot open a thread,
            # but the message itself is real and an operator can still read it.
            self.env['care.contact.capture']._capture(
                'no_identity', connection.channel, connection=connection,
                peer_hint=event.get('peer_name'), body=event.get('text'),
                raw=self._dump(event.get('raw')),
                external_event_id=event.get('external_message_id'),
                occurred_at=event.get('event_at'))
            return self.browse()

        attachment = event.get('attachment') or {}
        msg = self.sudo().create({
            'connection_id': connection.id,
            'identity_id': ident.id,
            'external_message_id': event.get('external_message_id') or False,
            'direction': 'incoming',
            'message_type': event.get('message_type') or 'text',
            'body': (event.get('text') or '')[:BODY_CAP] or False,
            'attachment_url': attachment.get('url'),
            'attachment_name': attachment.get('name'),
            'attachment_mime': attachment.get('mime'),
            'raw_payload': self._dump(event.get('raw')),
            'state': 'received',
            'event_at': event.get('event_at') or fields.Datetime.now(),
        })

        # --- the spine, isolated (ledger §5.55) -------------------------
        try:
            with self.env.cr.savepoint():
                CareCo = Care.with_company(connection.company_id)
                anchor = {'channel_identity_id': ident.id}
                if connection.channel == 'whatsapp':
                    # WA is the one channel whose external id IS a phone —
                    # asserted by the PROVIDER — so it may merge into an
                    # existing phone-anchored thread. A phone merely typed
                    # into the webchat pre-chat form must NOT anchor: an
                    # anonymous visitor claiming a patient's number would be
                    # merged onto the patient's thread and every ops reply
                    # there would route to the visitor. The volunteered phone
                    # stays display-only on the identity.
                    anchor['phone_normalized'] = CareCo._safe_phone(
                        event.get('external_id'))
                conv = CareCo._find_or_create_for(anchor, {
                    'channel': connection.channel,
                    'inbound': True,
                    'event_at': msg.event_at,
                    'set_status': 'needs_reply',
                    'unread': 1,
                    'watch_hits': CareCo._match_watchlist(event.get('text')),
                })
                msg.sudo().write({'conversation_id': conv.id})
                # Client requirement 3. First-touch, and this IS the first
                # touch: a Click-to-Messenger ad puts its ref and ad id on the
                # opening event and never repeats them. `_record_attribution`
                # falls back to the account's own utm defaults, so even an
                # organic message is attributed to the page it arrived on.
                attribution = event.get('attribution')
                if not attribution and ident.attribution_json:
                    # Web chat: the click ids were captured at `start`, before
                    # this conversation existed.
                    try:
                        attribution = json.loads(ident.attribution_json)
                    except ValueError:
                        attribution = None
                conv._record_attribution(
                    attribution, connection=connection,
                    occurred_at=msg.event_at,
                    external_event_id=event.get('external_message_id'))
        except Exception:  # noqa: BLE001 — the message row must survive
            _logger.exception('care_channels: conversation upsert failed for '
                              'message %s', msg.id)

        # Traffic is the only honest proof a webhook works (CC-B §2.4).
        connection._note_inbound(msg.event_at)
        return msg

    # ------------------------------------------------------------------
    # Outbound mirror (phase6 §2.3 — zalo outgoing signal, hooks.py:60-67)
    # ------------------------------------------------------------------
    @api.model
    def _record_outbound(self, connection, identity, text, result=None,
                         conversation=None, error=None):
        connection.ensure_one()
        result = result or {}
        state = result.get('state') or ('failed' if error else 'sent')
        # A provider that re-returns an id we already stored (retried send,
        # idempotent provider) must not fire the dedupe index into the RPC
        # transaction (§5.3 posture, same as the inbound funnel).
        existing = self._existing(connection, result.get('external_message_id'))
        if existing:
            return existing
        msg = self.sudo().create({
            'connection_id': connection.id,
            'identity_id': identity.id,
            'conversation_id': conversation.id if conversation else False,
            'external_message_id': result.get('external_message_id') or False,
            'direction': 'outgoing',
            'message_type': 'text',
            'body': (text or '')[:BODY_CAP] or False,
            'state': state,
            'error_message': redact(error) or False,
            'event_at': fields.Datetime.now(),
        })
        if state != 'failed':
            connection._note_outbound(msg.event_at)
        return msg

    # ------------------------------------------------------------------
    # Delivery receipts (phase6 T69)
    # ------------------------------------------------------------------
    @api.model
    def _apply_status(self, connection, event):
        """Move an outgoing row along its delivery states.

        An unknown message id is ignored quietly: providers send receipts for
        messages we may never have stored (a resent template, another worker's
        row), and a warning per receipt would be noise, not signal.
        """
        connection.ensure_one()
        state = STATUS_MAP.get(event.get('status'))
        row = self._existing(connection, event.get('external_message_id'))
        if not state or not row or row.direction != 'outgoing':
            return self.browse()
        # Never walk backwards: a late 'sent' after a 'read' is out-of-order
        # delivery, not new information.
        order = [s[0] for s in STATES]
        if order.index(state) <= order.index(row.state or 'received') \
                and state != 'failed':
            return row
        vals = {'state': state}
        if state == 'failed':
            vals['error_message'] = redact(event.get('error')) or _('Delivery failed')
        row.sudo().write(vals)
        return row

    # ==================================================================
    # Webhook routing (CC-B §2.3) — multi-tenant, no oracles
    # ==================================================================
    @api.model
    def _meta_resource_ids(self, channel, payload):
        """Distinct provider resource ids carried by one Meta payload.

        WhatsApp addresses us by ``phone_number_id``, Messenger by the page id
        on the entry. One POST may carry several of either — and, on a shared
        platform app, several tenants'.
        """
        ids = []
        for entry in (payload or {}).get('entry') or []:
            if channel == 'fb':
                if entry.get('id') is not None:
                    ids.append(str(entry['id']))
                continue
            for change in entry.get('changes') or []:
                metadata = (change.get('value') or {}).get('metadata') or {}
                if metadata.get('phone_number_id'):
                    ids.append(str(metadata['phone_number_id']))
        # Order-stable dedupe: a redelivered batch must route identically.
        seen, out = set(), []
        for rid in ids:
            if rid not in seen:
                seen.add(rid)
                out.append(rid)
        return out

    @api.model
    def _dispatch_meta(self, channel, payload):
        """Route a SIGNATURE-VERIFIED Meta payload to its tenants and ingest.

        Returns a small counter dict for the caller's log line. Never raises:
        the controller must answer 200 after verification whatever happens
        below, or Meta retries the same batch forever.
        """
        counts = {'ingested': 0, 'status': 0, 'ignored': 0, 'unknown': 0}
        Connection = self.env['care.channel.connection']
        for resource_id in self._meta_resource_ids(channel, payload):
            connection = Connection._find_for_resource(channel, resource_id)
            if not connection:
                # No oracle: nothing about the unknown id goes into the
                # response, and only the event TYPE goes into the log.
                #
                # It IS captured, though. A signature-verified event for a page
                # we do not recognise is the single most useful thing in the
                # Unrouted queue — it is what a newly-created Facebook page
                # nobody connected yet looks like from in here.
                _logger.info('care_channels: %s webhook for an unknown '
                             'resource — captured', channel)
                self.env['care.contact.capture']._capture(
                    'unknown_resource', channel,
                    resource_external_id=resource_id,
                    raw=self._dump(payload))
                counts['unknown'] += 1
                continue
            counts_for = self._dispatch_connection(connection, payload)
            for key, value in counts_for.items():
                counts[key] = counts.get(key, 0) + value
        return counts

    @api.model
    def _dispatch_connection(self, connection, payload):
        """Parse + ingest one verified payload for ONE resolved connection."""
        counts = {'ingested': 0, 'status': 0, 'ignored': 0}
        if not connection._may_ingest():
            # A disabled or errored channel must not keep filling the inbox.
            # NOTE for CC-C: the ingestable set is SENDABLE ∪
            # {testing, configuring} (handover §2.3). Because readiness is
            # DERIVED, a connection sitting in `testing` with unmet required
            # checks is moved to `action_required` by the very first inbound it
            # proves itself with — and `action_required` is not ingestable, so
            # later traffic is dropped until the tenant finishes setup. The
            # stepper must therefore complete its checks (or park the
            # connection in `configuring`) before pointing a provider at us.
            self.env['care.channel.audit']._log(
                'webhook_ignored', connection=connection,
                detail='state %s' % connection.state)
            # The audit row records that we dropped it; the capture keeps the
            # CONTACT. Someone messaged a page that is half set up — that is a
            # customer waiting, not an operations footnote.
            self.env['care.contact.capture']._capture(
                'not_ingestable', connection.channel, connection=connection,
                resource_external_id=connection.resource_external_id,
                raw=self._dump(payload))
            counts['ignored'] += 1
            return counts
        connection = connection.sudo()
        try:
            events = connection._get_adapter().parse_inbound(payload)
        except Exception:  # noqa: BLE001 — a malformed payload is not our bug
            _logger.exception('care_channels: parse failed on connection %s',
                              connection.id)
            return counts
        for event in events:
            # Per-event savepoint: one poisoned event must not lose the batch
            # (ledger §5.55).
            try:
                with self.env.cr.savepoint():
                    if event.get('kind') == 'status':
                        self._apply_status(connection, event)
                        counts['status'] += 1
                    else:
                        self._ingest_inbound(connection, event)
                        counts['ingested'] += 1
            except Exception:  # noqa: BLE001
                _logger.exception('care_channels: ingest failed on '
                                  'connection %s', connection.id)
        return counts

    # ==================================================================
    # Zalo (CC-D) — the ONE channel whose storage stays where it was
    # ==================================================================
    @api.model
    def _dispatch_zalo(self, connection, payload):
        """A SIGNATURE-VERIFIED Zalo event → the legacy ``zalo.message`` rails.

        Zalo chat deliberately does NOT become ``care.channel.message`` rows:
        Care Command's detail timeline reads ``zalo.message`` and its ops send
        path writes them (handover §2.3), and moving that storage would be a
        core rewrite for no gain. What CC-D takes over is the *boundary* —
        verification, tenant routing, dedupe and traffic-truth — while the
        pipeline underneath is the one that has always run, minus the
        ``with_delay()`` that silently dropped every event (defect Z3).

        Never raises: the controller answers 200 after verification whatever
        happens here, or Zalo retries the same event forever.
        """
        connection.ensure_one()
        counts = {'ingested': 0, 'duplicate': 0, 'ignored': 0, 'skipped': 0}
        if not connection._may_ingest():
            self.env['care.channel.audit']._log(
                'webhook_ignored', connection=connection,
                detail='state %s' % connection.state)
            self.env['care.contact.capture']._capture(
                'not_ingestable', connection.channel, connection=connection,
                resource_external_id=connection.resource_external_id,
                raw=self._dump(payload))
            counts['ignored'] += 1
            return counts
        if 'zalo.message.handler' not in self.env:
            # The framework works with or without health_zalo installed; a
            # verified event we have nowhere to put is still honest traffic.
            _logger.warning('care_channels: zalo webhook verified but '
                            'health_zalo is not installed — event skipped')
            counts['skipped'] += 1
        else:
            try:
                with self.env.cr.savepoint():
                    # with_company, or the legacy pipeline resolves its config
                    # by `self.env.company` — company 1 for the webhook's
                    # superuser env — and a second tenant's verified events
                    # would find no config, or worse, land on company 1's
                    # conversations (CC-D review).
                    # zalo_oa_id, or the legacy pipeline resolves "the" active
                    # config for the company — and with two Official Accounts
                    # connected that files OA #2's messages under OA #1's
                    # conversations, and replies leave from the wrong account.
                    # The legacy handler does not thread ids through its
                    # internals, so the routed OA rides in the context and
                    # `zalo.config.get_active_config` reads it there.
                    result = self.env['zalo.message.handler'].sudo() \
                        .with_company(connection.company_id) \
                        .with_context(
                            zalo_oa_id=connection.resource_external_id) \
                        ._ingest_verified_event(payload)
                if isinstance(result, dict):
                    for key in ('ingested', 'duplicate', 'skipped'):
                        counts[key] += result.get(key, 0)
                else:
                    counts['ingested'] += 1
                self._zalo_record_attribution(connection, payload)
            except Exception:  # noqa: BLE001 — one poisoned event, not a batch
                _logger.exception('care_channels: zalo ingest failed on '
                                  'connection %s', connection.id)
        connection._note_inbound()
        return counts

    # ------------------------------------------------------------------
    # Zalo attribution (client requirement 3)
    # ------------------------------------------------------------------
    # HONESTY NOTE. Unlike Meta's `referral` object, Zalo's ad-referral payload
    # is NOT verified: developers.zalo.me is geo-blocked from where this was
    # written, the same wall that left the VoIP24h payload shape unconfirmed
    # (health_voip24h/controllers/webhook.py:52-56). What IS known is that
    # `user_click_chatnow` and the follow events carry a tracking string, and
    # that Zalo has moved its name between `ref`, `campaign_id` and a nested
    # `info` object across versions.
    #
    # So this reads a GENERIC bucket — every plausible key, first match wins —
    # and keeps the raw event on the touchpoint either way. When the docs are
    # reachable from a Vietnamese connection, the exact mapping replaces the
    # bucket and nothing else has to change.
    ZALO_REF_KEYS = ('ref', 'campaign_id', 'tracking_id', 'utm_source',
                     'source', 'ad_id')
    ZALO_REF_EVENTS = ('user_click_chatnow', 'follow', 'user_seen_message',
                       'oa_send_text')

    @api.model
    def _zalo_attribution(self, payload):
        """Best-effort tracking payload off one Zalo event. ``{}`` if none."""
        payload = payload or {}
        if payload.get('event_name') not in self.ZALO_REF_EVENTS:
            return {}
        pools = [payload, payload.get('info') or {},
                 payload.get('follower') or {}, payload.get('message') or {}]
        found = {}
        for pool in pools:
            if not isinstance(pool, dict):
                continue
            for key in self.ZALO_REF_KEYS:
                value = pool.get(key)
                if value and 'referral_ref' not in found:
                    found['referral_ref'] = str(value)[:500]
        if not found:
            return {}
        found['referral_source'] = 'zalo'
        found['entry_point'] = payload.get('event_name')
        return found

    @api.model
    def _zalo_record_attribution(self, connection, payload):
        """Attach a Zalo event's tracking payload to its conversation.

        Zalo chat lives on the legacy ``zalo.message`` rails, so there is no
        identity row to hang this off — the conversation is resolved back
        through ``zalo.conversation`` by the sender's user id. Never raises:
        this runs inside a webhook that must answer 200.
        """
        data = self._zalo_attribution(payload)
        if not data:
            return False
        user_id = ((payload or {}).get('sender') or {}).get('id')
        if not user_id or 'zalo.conversation' not in self.env:
            return False
        try:
            with self.env.cr.savepoint():
                zconv = self.env['zalo.conversation'].sudo().search(
                    [('zalo_user_id', '=', str(user_id))], limit=1)
                if not zconv:
                    return False
                conv = self.env['care.conversation'].sudo().search(
                    [('zalo_conversation_id', '=', zconv.id)], limit=1)
                if not conv:
                    return False
                conv._record_attribution(data, connection=connection)
                return True
        except Exception:  # noqa: BLE001 — analytics never breaks ingest
            _logger.exception('care_channels: zalo attribution failed on '
                              'connection %s', connection.id)
            return False

    # ==================================================================
    # Web chat (phase6 §2.6) — our own widget, no provider at all
    # ==================================================================
    @api.model
    def _webchat_connection(self):
        """The connection that serves the public widget.

        Single-company-per-database is the deployment reality (architecture
        §1.5), so there is exactly one; ``limit=1`` with a stable order keeps
        a multi-company install deterministic rather than random.
        """
        return self.env['care.channel.connection'].sudo().search([
            ('channel', '=', 'webchat'),
            ('state', 'in', sorted(INGESTABLE_STATES)),
        ], order='id', limit=1)

    @api.model
    def _webchat_identity(self, session):
        session = (session or '').strip()
        if not session:
            return self.env['care.channel.identity'].browse()
        return self.env['care.channel.identity'].sudo().search([
            ('channel', '=', 'webchat'), ('external_id', '=', session)],
            limit=1)

    @api.model
    def _webchat_start(self, session=None, name=None, phone=None,
                       attribution=None):
        """Open (or resume) a widget session. Returns ``{session, greeting}``.

        The session id is generated SERVER-side: a client-chosen id would let a
        visitor claim someone else's thread. A supplied one is honoured only if
        it already exists.
        """
        connection = self._webchat_connection()
        if not connection:
            return {}
        identity = self._webchat_identity(session)
        if not identity or identity.connection_id != connection:
            token = uuid.uuid4().hex
            identity = self.env['care.channel.identity']._upsert(
                connection, token,
                peer_name=(name or '').strip()[:120]
                or _('Web visitor %s', token[:8]))
        elif name:
            identity.sudo().write({'peer_name': (name or '').strip()[:120]})
        if phone:
            # Stored, not trusted: it only ever feeds the phone anchor.
            identity.sudo().write({'peer_phone': (phone or '').strip()[:32]})
        # Park the click ids until the first message creates a conversation.
        # First touch wins: a visitor who reopens the widget from an organic
        # visit must not overwrite the ad click that brought them originally.
        if attribution and not identity.attribution_json:
            cleaned = self.env['care.conversation']._clean_attribution(
                attribution)
            if cleaned:
                identity.sudo().write(
                    {'attribution_json': json.dumps(cleaned)[:4000]})
        # A visitor who filled in the pre-chat form and then typed nothing has
        # still contacted us, and used to disappear entirely: no message row,
        # so no conversation, and the 7-day GC deleted the identity. Capture
        # the details they volunteered so the contact survives the silence.
        # (No conversation: an unverified name and phone typed into a public
        # widget must not anchor a thread — see the WhatsApp note in
        # `_ingest_inbound`. Converting is an operator's decision.)
        if (name or phone) and not self.sudo().search_count([
                ('identity_id', '=', identity.id),
                ('direction', '=', 'incoming')]):
            self.env['care.contact.capture']._capture(
                'webchat_abandoned', 'webchat', connection=connection,
                peer_hint=name, phone=phone,
                external_event_id='webchat:%s' % identity.external_id)
        return {
            'session': identity.external_id,
            'greeting': connection.get_setting('greeting') or '',
        }

    @api.model
    def _webchat_ingest(self, session, text):
        """One visitor message. Unknown session → empty (the route 404s)."""
        connection = self._webchat_connection()
        identity = self._webchat_identity(session)
        if not connection or not identity or identity.connection_id != connection:
            return self.browse()
        text = (text or '').strip()[:WEBCHAT_TEXT_CAP]
        if not text:
            return self.browse()
        return self._ingest_inbound(connection, {
            'kind': 'message',
            'external_id': identity.external_id,
            'external_message_id': uuid.uuid4().hex,
            'peer_name': identity.peer_name,
            'message_type': 'text',
            'text': text,
            'attachment': {},
            'event_at': fields.Datetime.now(),
            'raw': None,
        })

    @api.model
    def _webchat_poll(self, session, after_id=0):
        """Both directions, id-ordered, so multiple tabs stay consistent."""
        identity = self._webchat_identity(session)
        if not identity:
            return []
        try:
            after_id = int(after_id or 0)
        except (TypeError, ValueError):
            after_id = 0
        rows = self.sudo().search(
            [('identity_id', '=', identity.id), ('id', '>', after_id)],
            order='id asc', limit=WEBCHAT_POLL_CAP)
        return [{
            'id': row.id,
            'direction': row.direction,
            'body': row.body or '',
            'ts': row.event_at.isoformat() if row.event_at else False,
        } for row in rows]

    # ------------------------------------------------------------------
    # Web-chat garbage collection (phase6 §2.6)
    # ------------------------------------------------------------------
    @api.model
    def _cron_gc_webchat(self):
        """Drop abandoned widget sessions: an identity older than
        ``WEBCHAT_GC_DAYS`` that never produced an inbound message is a
        launcher click, not a conversation."""
        cutoff = fields.Datetime.now() - timedelta(days=WEBCHAT_GC_DAYS)
        Identity = self.env['care.channel.identity'].sudo()
        stale = Identity.search([
            ('channel', '=', 'webchat'),
            ('create_date', '<', cutoff),
        ])
        removed = 0
        for identity in stale:
            if self.sudo().search_count([
                    ('identity_id', '=', identity.id),
                    ('direction', '=', 'incoming')]):
                continue
            convs = self.env['care.conversation'].sudo().search(
                [('channel_identity_id', '=', identity.id)])
            # Capture before deleting, and only where the visitor left
            # something reachable. A bare launcher click with no name and no
            # phone is not a contact and captures nothing — the queue has to
            # stay worth reading.
            if identity.peer_phone:
                self.env['care.contact.capture']._capture(
                    'webchat_abandoned', 'webchat',
                    connection=identity.connection_id,
                    peer_hint=identity.peer_name, phone=identity.peer_phone,
                    external_event_id='webchat:%s' % identity.external_id,
                    occurred_at=identity.create_date)
            try:
                with self.env.cr.savepoint():
                    self.sudo().search(
                        [('identity_id', '=', identity.id)]).unlink()
                    identity.unlink()
                    convs.filtered(
                        lambda c: not (c.partner_id or c.lead_id)).unlink()
                    removed += 1
            except Exception:  # noqa: BLE001 — one stuck row is not a failure
                _logger.exception('care_channels: webchat GC failed for '
                                  'identity %s', identity.id)
        if removed:
            _logger.info('care_channels: web-chat GC removed %s empty '
                         'session(s)', removed)
        return removed
