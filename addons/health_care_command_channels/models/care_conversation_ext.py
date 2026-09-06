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

# The channels this module powers. The base rails (zalo/call/email/zns) are live
# rails maintained elsewhere and are never gated by a connection here. walk_in
# joins them because it has no connection to be gated BY — the front desk can
# always log someone who walked through the door.
EXT_CHANNELS = ('whatsapp', 'fb', 'telegram', 'webchat')
BASE_CHANNELS = ('zalo', 'call', 'email', 'zns', 'walk_in')

# Provider errors that mean "the grant is gone", not "the network hiccuped".
AUTH_ERROR_MARKERS = ('401', '403', 'oauthexception', 'code 190',
                      '"code": 190', "'code': 190", 'invalid_token',
                      'access token', 'permission')


class CareConversationChannelExt(models.Model):
    _inherit = 'care.conversation'

    channel_identity_id = fields.Many2one(
        'care.channel.identity', string='Channel Identity', index=True,
        ondelete='set null')
    # WHICH account this thread arrived on. Stored (not a plain related) so ops
    # can filter and group the wall by account — with two Facebook pages and
    # two Zalo OAs live, "show me the Hanoi inbox" is a routine ask and a
    # non-stored related cannot answer it in a domain.
    channel_connection_id = fields.Many2one(
        'care.channel.connection', string='Channel Account',
        related='channel_identity_id.connection_id',
        store=True, index=True, readonly=True, ondelete='set null')

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
    # Attribution (client requirement 3): "capture the GCLID for google and
    # equivalents for Facebook and Zalo, so we can feed back actual contacts
    # to the algorithms".
    #
    # The touchpoint model already exists and already reserves the vocabulary
    # for this — `zalo_click`, `messenger_click`, `click_to_call` were declared
    # by W1 and written by nothing, precisely so the channel phases would add
    # rows rather than a migration (lead_touchpoint.py:35-46). So this writes
    # THERE rather than inventing a parallel store, and the deferred W4
    # offline-conversion export to Google Ads / Meta CAPI reads one table.
    # ------------------------------------------------------------------
    TOUCHPOINT_TYPES = {
        'zalo': 'zalo_click',
        'zns': 'zalo_click',
        'fb': 'messenger_click',
        'whatsapp': 'messenger_click',
        'call': 'click_to_call',
    }

    # What a caller may put in an `attribution` dict. A strict whitelist: this
    # data comes off a public web page in the webchat case, so anything not
    # named here is dropped rather than stored.
    ATTRIBUTION_KEYS = (
        'utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term',
        'gclid', 'wbraid', 'gbraid', 'fbclid', 'ad_id', 'ad_account_id',
        'referral_ref', 'referral_source', 'entry_point',
        'page_url', 'referrer_url',
    )
    ATTRIBUTION_VALUE_CAP = 500

    @api.model
    def _clean_attribution(self, attribution):
        """Whitelist, stringify and cap one attribution dict."""
        if not isinstance(attribution, dict):
            return {}
        out = {}
        for key in self.ATTRIBUTION_KEYS:
            value = attribution.get(key)
            if value in (None, False, ''):
                continue
            if not isinstance(value, str):
                value = str(value)
            value = value.strip()[:self.ATTRIBUTION_VALUE_CAP]
            if value:
                out[key] = value
        return out

    def _record_attribution(self, attribution, connection=None,
                            occurred_at=None, external_event_id=None):
        """Store how this conversation was reached. First touch wins.

        Deliberately FIRST-touch: the ad click that produced the conversation
        is the thing the ad platforms need back, and a later message on the
        same thread carries no click id to overwrite it with anyway. So a
        conversation that already has a touchpoint is left alone.

        Never raises. Attribution is analytics; losing it must never cost us
        the message that carried it.
        """
        self.ensure_one()
        if 'health.lead.touchpoint' not in self.env:
            # health_web_leads is not installed: there is nowhere to put this,
            # and that is a deployment choice rather than an error.
            return self.browse()
        data = self._clean_attribution(attribution)
        connection = connection or self.channel_connection_id
        # The account's own defaults are the FLOOR — a real per-event value
        # from the provider always wins. This is what attributes a phone call,
        # which can never carry a click id, to the number that was dialled.
        if connection:
            data.setdefault('utm_source', connection.utm_source_id.name or '')
            data.setdefault('utm_medium', connection.utm_medium_id.name or '')
            data.setdefault('utm_campaign', connection.campaign_id.name or '')
            data = {k: v for k, v in data.items() if v}
        Touch = self.env['health.lead.touchpoint'].sudo()
        if not data:
            return Touch.browse()
        if Touch.search_count([('conversation_id', '=', self.id)], limit=1):
            return Touch.browse()
        channel = self.channel_effective or (connection.channel if connection
                                             else '')
        # R1 post-review (deviation D11), the SIBLING of D3 and the same repair.
        # `touchpoint_type` became the `touchpoint_type_id` lookup in the
        # dropdown-vocabulary conversion (health_base/lookup_registry.py:520)
        # and this writer was left behind, so `create()` raised
        # `Invalid field 'touchpoint_type'` — swallowed by the guard below,
        # which is why EVERY conversation's marketing attribution has been lost
        # on every database since that conversion. The warning is not decoration:
        # a silent write is exactly how the first one hid (ledger §5.174).
        type_code = self.TOUCHPOINT_TYPES.get(channel, 'manual')
        type_id = self.env['health.lookup.value']._default_for(
            'touchpoint_type', type_code)
        if not type_id:
            _logger.warning(
                'care_channels: no touchpoint_type lookup value for %r — '
                'attribution for conversation %s cannot be recorded',
                type_code, self.id)
            return Touch.browse()
        try:
            with self.env.cr.savepoint():
                return Touch.create(dict(
                    data,
                    conversation_id=self.id,
                    lead_id=self.lead_id.id or False,
                    touchpoint_type_id=type_id,
                    occurred_at=occurred_at or self.last_inbound_at
                    or fields.Datetime.now(),
                    external_event_id=external_event_id or False,
                ))
        except Exception:  # noqa: BLE001 — analytics must not break ingest
            _logger.exception(
                'care_channels: attribution write failed for conversation %s',
                self.id)
            return Touch.browse()

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
        """The connection that may send on THIS conversation's channel.

        Multi-account correctness: a reply belongs to the ACCOUNT the message
        arrived on. With two Facebook pages connected, answering from whichever
        page the search happened to return first delivers the reply from the
        wrong identity — to a stranger, or to nobody.

        So the fallback is scoped to the same provider resource rather than to
        the channel. That still covers the case it was written for (a reconnect
        archives the old row and creates a new one for the SAME page, and the
        old peers must not go mute), while refusing to cross accounts. If the
        peer's own page is genuinely down, the composer says so — see
        ``_channel_window`` — instead of sending from a sibling.
        """
        self.ensure_one()
        ident = self.channel_identity_id
        if not ident:
            return self.env['care.channel.connection'].browse()
        conn = ident.connection_id.sudo()
        if conn.state in SENDABLE_STATES and conn.active:
            return conn
        return self.env['care.channel.connection']._find_sendable_for_resource(
            ident.channel, self.company_id.id, conn.resource_external_id)

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
