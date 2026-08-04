# -*- coding: utf-8 -*-
"""Care Command spine extension for the adapter channels (phase6 §2.4).

The four new channels are NOT a parallel inbox: they land on the SAME
``care.conversation`` records the live rails use, through the same
``_find_or_create_for`` upsert. What this file adds is exactly four things:

* ``channel_identity_id`` — one new anchor (mirroring the ``zalo_conversation_id``
  precedent), because a Messenger PSID or a Telegram chat id is all the identity
  a first contact has;
* identity-first resolution, so WhatsApp merges into an existing phone-anchored
  thread instead of forking a duplicate;
* the merged timeline + snippet, read-time as everywhere else;
* ``action_send_channel`` — the ONE outbound trigger, a human pressing send.

There is no auto-reply, no bot, no queue. And ``_channel_keys()`` tells the
dock the truth: an adapter channel is only offered when a connection for THIS
company can actually send on it.
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..services.redact import redact
from .care_channel_connection import SENDABLE_STATES

_logger = logging.getLogger(__name__)

# The channels this module powers. The base four (zalo/call/email/zns) are live
# rails maintained elsewhere and are never gated by a connection here.
EXT_CHANNELS = ('whatsapp', 'fb', 'telegram', 'webchat')
BASE_CHANNELS = ('zalo', 'call', 'email', 'zns')

# Provider errors that mean "the grant is gone", not "the network hiccuped".
AUTH_ERROR_MARKERS = ('401', '403', 'oauthexception', 'code 190',
                      '"code": 190', "'code': 190", 'invalid_token',
                      'access token', 'permission')


class CareConversationChannelExt(models.Model):
    _inherit = 'care.conversation'

    channel_identity_id = fields.Many2one(
        'care.channel.identity', string='Channel Identity', index=True,
        ondelete='set null')

    def init(self):
        super().init()
        # Same partial-unique posture as zalo_conversation_id
        # (care_conversation.py:161-171): one thread per external peer.
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
                care_conversation_channel_identity_uniq
            ON care_conversation (channel_identity_id)
            WHERE channel_identity_id IS NOT NULL
        """)

    # ------------------------------------------------------------------
    # Anchor + display
    # ------------------------------------------------------------------
    @api.constrains('partner_id', 'lead_id', 'zalo_conversation_id',
                    'phone_normalized', 'email_normalized',
                    'channel_identity_id')
    def _check_anchor(self):
        # A channel identity is a valid SOLE anchor: FB/Telegram/webchat give
        # us no phone, no email and no partner at first contact. The decorator
        # is re-declared in full (the base's fields plus ours) — overriding a
        # constrains with a partial decorator silently drops dependencies.
        rest = self.filtered(lambda r: not r.channel_identity_id)
        if rest:
            super(CareConversationChannelExt, rest)._check_anchor()

    @api.depends('partner_id', 'partner_id.name',
                 'lead_id', 'lead_id.contact_name', 'lead_id.partner_name',
                 'lead_id.name', 'zalo_conversation_id.zalo_user_name',
                 'email_normalized', 'phone_normalized',
                 'channel_identity_id.display_name')
    def _compute_display_name_c(self):
        super()._compute_display_name_c()
        for rec in self:
            ident = rec.channel_identity_id
            if not ident or not ident.display_name:
                continue
            # Only fill in where the spine had nothing better: a real contact,
            # lead or phone always outranks a provider handle.
            if not (rec.partner_id or rec.lead_id or rec.zalo_conversation_id
                    or rec.email_normalized or rec.phone_normalized):
                rec.display_name_c = ident.display_name

    @api.depends('channel_identity_id.catchment_province_id',
                 'partner_id.catchment_province_id',
                 'partner_id.primary_facility_id.catchment_province_id',
                 'lead_id.catchment_province_id')
    def _compute_catchment_province_id(self):
        """The channel ACCOUNT wins.

        Each area runs its own Zalo OA and Facebook page, so the account a
        message landed on is the most reliable statement of which area owns the
        conversation — and it is known at first contact, before there is any
        partner or lead to ask. The spine's contact/lead walk stays as the
        fallback for conversations with no channel traffic (leads logged by
        hand, walk-ins) and for connections left unassigned.

        The decorator is re-declared in full rather than extended: overriding a
        depends with a partial one silently drops the parent's dependencies,
        the same trap `_check_anchor` above documents.
        """
        for rec in self:
            from_channel = rec.channel_identity_id.catchment_province_id
            rec.catchment_province_id = (
                from_channel or rec._catchment_from_anchors())

    # ------------------------------------------------------------------
    # Identity-first upsert
    # ------------------------------------------------------------------
    @api.model
    def _find_or_create_for(self, anchor, signal):
        ident_id = (anchor or {}).get('channel_identity_id')
        if not ident_id:
            return super()._find_or_create_for(anchor, signal)
        Conv = self.sudo()
        rec = Conv.search([
            ('company_id', '=', self.env.company.id),
            ('channel_identity_id', '=', ident_id)], limit=1)
        if rec:
            return rec._apply_signal(anchor, signal)
        # No thread for this peer yet: let the base precedence run over the
        # OTHER anchors first (WhatsApp carries a phone, so it merges into an
        # existing phone thread rather than forking one), then backfill the
        # identity onto whatever it resolved to.
        rec = super()._find_or_create_for(anchor, signal)
        if rec and not rec.channel_identity_id:
            rec.sudo().write({'channel_identity_id': ident_id})
        return rec

    # ------------------------------------------------------------------
    # Read-time merge
    # ------------------------------------------------------------------
    def _channel_messages(self, limit=100):
        self.ensure_one()
        if not self.channel_identity_id:
            return self.env['care.channel.message'].browse()
        return self.env['care.channel.message'].sudo().search(
            [('identity_id', '=', self.channel_identity_id.id)],
            order='event_at desc, id desc', limit=limit)

    def _detail_timeline(self):
        events = super()._detail_timeline()
        for m in self._channel_messages():
            events.append({
                'kind': m.channel,
                'direction': 'out' if m.direction == 'outgoing' else 'in',
                'text': m.body or '[%s]' % (m.message_type or 'message'),
                'ts': m.event_at.isoformat() if m.event_at else False,
                'delivery': m.state,
            })
        events = [e for e in events if e.get('ts')]
        events.sort(key=lambda e: e['ts'])
        return events[-100:]

    def _snippet(self):
        self.ensure_one()
        if self.channel_identity_id:
            msg = self.env['care.channel.message'].sudo().search(
                [('identity_id', '=', self.channel_identity_id.id),
                 ('direction', '=', 'incoming')],
                order='event_at desc, id desc', limit=1)
            if msg and msg.body:
                return msg.body[:120]
        return super()._snippet()

    # ------------------------------------------------------------------
    # Capabilities + dock honesty
    # ------------------------------------------------------------------
    def _sendable_connection(self):
        """The connection that may send on THIS conversation's channel."""
        self.ensure_one()
        ident = self.channel_identity_id
        if not ident:
            return self.env['care.channel.connection'].browse()
        conn = ident.connection_id.sudo()
        if conn.state in SENDABLE_STATES and conn.active:
            return conn
        # The peer's own connection is down — fall back to whatever active
        # connection serves this channel for the company (a reconnect creates
        # a new row; the old peers must not go mute because of it).
        return self.env['care.channel.connection']._find_sendable(
            ident.channel, self.company_id.id)

    def _capabilities(self):
        caps = super()._capabilities()
        if self.channel_identity_id and self._sendable_connection():
            caps['ext_reply_channel'] = self.channel_identity_id.channel
            # CC-E: the composer must KNOW about Meta's 24 h customer-service
            # window rather than discovering it as a failed send (§1.4). Every
            # channel answers, so a caller never has to special-case Meta;
            # channels with no window simply report `open` with no restriction.
            caps['ext_window'] = self._channel_window()
        return caps

    def _channel_window(self):
        """What may go out on this conversation right now, and why.

        Returns the adapter's window state plus one plain sentence
        (``message``) and, for WhatsApp outside the window, the fact that a
        template is the only path. The composer renders that instead of
        offering a send that Meta would refuse.
        """
        self.ensure_one()
        ident = self.channel_identity_id
        connection = self._sendable_connection()
        if not ident or not connection:
            return {'channel': ident.channel if ident else '', 'open': False,
                    'requires_template': False, 'requires_tag': False,
                    'blocked': True, 'tags': [], 'message': _(
                        'This channel is not connected right now.')}
        return self.env['care.channel.connection'].sudo()._center_window(
            connection, ident)

    @api.model
    def channel_send_window(self, conv_id):
        """RPC face of :meth:`_channel_window` — group- and company-gated."""
        return self._guarded(conv_id)._channel_window()

    @api.model
    def channel_templates(self, conv_id):
        """The APPROVED WhatsApp templates for this conversation's connection."""
        rec = self._guarded(conv_id)
        ident = rec.channel_identity_id
        connection = rec._sendable_connection()
        if not ident or ident.channel != 'whatsapp' or not connection:
            return {'templates': []}
        try:
            templates = connection._get_adapter().list_message_templates()
        except Exception as exc:  # noqa: BLE001 — provider/network failure
            raise UserError(_(
                'We could not read your WhatsApp templates: %s',
                redact(exc) or _('unknown error'))) from exc
        return {'templates': templates}

    @api.model
    def action_send_channel_template(self, conv_id, channel, template_name,
                                     language='vi', params=None):
        """Send an APPROVED WhatsApp template — the outside-window path.

        Human composer only, exactly like :meth:`action_send_channel`. The body
        stored on the message row is the template name plus the parameters the
        agent supplied: the rendered text lives at Meta, and inventing our own
        rendering of it would put words in the record that were never sent.
        """
        rec = self._guarded(conv_id)
        ident = rec.channel_identity_id
        if not ident:
            raise UserError(_('This conversation has no messaging channel.'))
        if channel != ident.channel or channel != 'whatsapp':
            raise UserError(_('Only WhatsApp uses message templates.'))
        connection = rec._sendable_connection()
        if not connection:
            raise UserError(_(
                'This channel is not connected right now. Open Care Command → '
                'Channels to reconnect it.'))
        name = (template_name or '').strip()
        if not name:
            raise UserError(_('Choose an approved template.'))
        values = [str(v) for v in (params or []) if v is not None]
        body = '[%s] %s' % (name, ' · '.join(values)) if values else '[%s]' % name

        Message = self.env['care.channel.message']
        try:
            result = connection._get_adapter().send_template(
                ident, name, language=language, params=values)
        except Exception as exc:  # noqa: BLE001 — provider/network failure
            auth = any(m in str(exc).lower() for m in AUTH_ERROR_MARKERS)
            if not connection._persist_send_failure(
                    ident, body, exc, auth_failure=auth, conversation=rec):
                Message._record_outbound(connection, ident, body,
                                         conversation=rec, error=exc)
                connection._note_send_failure(exc, auth_failure=auth)
            raise UserError(_(
                'The template could not be sent: %s',
                redact(exc) or _('unknown error')))

        msg = Message._record_outbound(connection, ident, body, result=result,
                                       conversation=rec)
        rec.write({'status': 'waiting', 'unread_count': 0,
                   'last_event_at': fields.Datetime.now()})
        return {
            'kind': ident.channel,
            'direction': 'out',
            'text': body,
            'ts': (msg.event_at or fields.Datetime.now()).isoformat(),
            'delivery': msg.state,
        }

    @api.model
    def _channel_keys(self):
        """Dock/count honesty (phase6 §5.3): the base rails plus every adapter
        channel that has a sendable connection FOR THE CURRENT COMPANY.

        A draft, testing, disabled or absent connection means the dock icon
        stays inactive — "we could support this" is not "this works".
        """
        base = list(super()._channel_keys())
        conns = self.env['care.channel.connection'].sudo().search([
            ('channel', 'in', list(EXT_CHANNELS)),
            ('company_id', '=', self.env.company.id),
            ('state', 'in', sorted(SENDABLE_STATES)),
        ])
        connected = {c.channel for c in conns}
        return tuple(k for k in base
                     if k in BASE_CHANNELS or k in connected)

    # ------------------------------------------------------------------
    # The ONE outbound trigger (phase6 §2.4)
    # ------------------------------------------------------------------
    @api.model
    def action_send_channel(self, conv_id, channel, text):
        """Send ``text`` on ``channel`` for this conversation.

        Human composer only — nothing in this module ever sends by itself.
        Every failure surfaces as a clean UserError with a redacted provider
        reason: an agent must never be blocked from doing manual work by an
        adapter problem, and a raw provider body could carry a bearer token.
        """
        rec = self._guarded(conv_id)
        text = (text or '').strip()
        if not text:
            raise UserError(_('Message is empty.'))
        ident = rec.channel_identity_id
        if not ident:
            raise UserError(_('This conversation has no messaging channel.'))
        if channel != ident.channel:
            raise UserError(_('This conversation is not a %s conversation.',
                              channel))
        connection = rec._sendable_connection()
        if not connection:
            raise UserError(_(
                'This channel is not connected right now. Open Care Command → '
                'Channels to reconnect it.'))

        # CC-E §1.4: Meta's customer-service window is checked HERE, before the
        # network, so an agent is told what to do instead of watching a send
        # fail at Meta. WhatsApp outside 24 h ⇒ the template path;
        # Messenger outside 24 h ⇒ the HUMAN_AGENT tag (7 days), then nothing.
        window = rec._channel_window()
        kwargs = {}
        if window.get('requires_template'):
            raise UserError(_(
                '%s Send an approved template instead.', window['message']))
        if window.get('blocked') and ident.channel == 'fb':
            raise UserError(window['message'])
        if window.get('requires_tag') and window.get('tags'):
            kwargs['tag'] = window['tags'][0]

        Message = self.env['care.channel.message']
        try:
            result = connection._get_adapter().send_message(ident, text,
                                                            **kwargs)
        except Exception as exc:  # noqa: BLE001 — provider/network failure
            auth = any(m in str(exc).lower() for m in AUTH_ERROR_MARKERS)
            # The evidence has to outlive the UserError below, which rolls this
            # transaction back — so it goes to an independent cursor first. If
            # that path is unavailable (tests), record it in-transaction
            # instead: exactly one failure row either way.
            if not connection._persist_send_failure(
                    ident, text, exc, auth_failure=auth, conversation=rec):
                Message._record_outbound(connection, ident, text,
                                         conversation=rec, error=exc)
                connection._note_send_failure(exc, auth_failure=auth)
            raise UserError(_(
                'The message could not be sent: %s', redact(exc) or _('unknown error')))

        msg = Message._record_outbound(connection, ident, text, result=result,
                                       conversation=rec)
        rec.write({'status': 'waiting', 'unread_count': 0,
                   'last_event_at': fields.Datetime.now()})
        return {
            'kind': ident.channel,
            'direction': 'out',
            'text': text,
            'ts': (msg.event_at or fields.Datetime.now()).isoformat(),
            'delivery': msg.state,
        }
