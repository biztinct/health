# -*- coding: utf-8 -*-
"""The Channel Connection Center's server side (CC-C, architecture §9).

An ``_inherit`` extension rather than more methods on
``care_channel_connection.py``: that file is the state machine and the secret
store, and it stays readable only if the tenant-facing choreography lives
somewhere else.

Everything here obeys the same four rules:

1. **Every write goes through ``sudo()._internal()``.** The Center is the ONLY
   sanctioned way for a tenant to change a connection, and the write guard
   refuses every other door (``USER_WRITABLE`` is ``active`` and nothing else).
2. **No secret ever leaves.** Not in a return value, not in a check detail, not
   in an audit row: the pasted Telegram token is validated, encrypted and
   forgotten, and what comes back is the bot's public name.
3. **Every provider failure is a redacted ``UserError``**, with its evidence
   written first (``_note_*`` / the CC-B ``_persist_send_failure`` idiom,
   ledger §5.65) — the tenant gets a clean sentence, we keep the fact.
4. **Readiness is still derived.** Nothing here asserts ``ready``: the stepper
   proves checks (``authorization_valid`` from ``getMe``,
   ``webhook_configured`` from ``setWebhook``, ``inbound_ok`` from a real
   message, ``outbound_ok`` from a real send) and ``_recompute_ready`` decides.

Two channels are self-service end to end this phase: **web chat** (one click,
an embed snippet, and the first real widget message finishes it) and
**Telegram** (BotFather → paste → validate → register → say hello). The other
six render honestly and their steppers are structure only (CC-D/E/F).
"""
import logging
import re
import secrets
from urllib.parse import urlparse

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.health_care_command.models.care_conversation import (
    CHANNEL_SELECTION,
)

from ..services.adapters import (
    MODE_GUIDED_SECRET, MODE_ONE_CLICK, ChannelSendError,
)
from ..services.redact import redact
from .care_channel_connection import SENDABLE_STATES

_logger = logging.getLogger(__name__)

# The catalogue order IS the dock order (health_care_command CHANNEL_SELECTION).
CENTER_CHANNELS = [key for key, _label in CHANNEL_SELECTION]

# Modes whose stepper is actually implemented. Everything else renders its
# structure and says so — an honest "not yet" beats a button that cannot work.
IMPLEMENTED_MODES = {MODE_GUIDED_SECRET, MODE_ONE_CLICK}

# Only these channels have a working begin/validate/test flow in CC-C. The
# `call` adapter also declares guided_secret, but its credential exchange is
# CC-F (and its endpoints are unverified — architecture §12.8), so it must not
# be offered here.
CENTER_IMPLEMENTED_CHANNELS = {'telegram', 'webchat'}

# A pasted Telegram bot token is `<bot id>:<secret>`. Deliberately loose: the
# real validation is getMe, this only avoids burning an HTTP call (and a log
# line) on an obvious paste accident.
_TG_TOKEN_RE = re.compile(r'^\d+:[A-Za-z0-9_-]{10,}$')

# Web chat: a tenant with more than this many origins is configuring something
# other than their own website.
MAX_ORIGINS = 20
GREETING_CAP = 200

WIDGET_JS = '/health_care_command_channels/static/src/webchat/widget.js'
WEBCHAT_DEMO_PATH = '/care_channels/webchat/demo'
TELEGRAM_WEBHOOK_PATH = '/care_channels/telegram/webhook/'


class CareChannelConnectionCenter(models.Model):
    _inherit = 'care.channel.connection'

    # ==================================================================
    # Translated vocabulary — kept SERVER-side on purpose
    # ==================================================================
    # The UI renders what the server sends, so vi.po covers each string once
    # instead of once per surface (handover §5).

    @api.model
    def _center_channel_labels(self):
        labels = dict(CHANNEL_SELECTION)
        labels.update({
            'zalo': _('Zalo'),
            'call': _('Calls'),
            'email': _('Email'),
            'zns': _('Zalo notifications (ZNS)'),
            'whatsapp': _('WhatsApp'),
            'fb': _('Messenger'),
            'telegram': _('Telegram'),
            'webchat': _('Web chat'),
        })
        return labels

    @api.model
    def _center_state_chips(self):
        """architecture §9 — the chip vocabulary, no jargon anywhere."""
        return {
            'not_connected': _('Not connected'),
            'authorizing': _('Connecting…'),
            'select_resource': _('Connecting…'),
            'configuring': _('Setting up…'),
            'testing': _('Almost there'),
            'ready': _('Connected'),
            'action_required': _('Action required'),
            'expiring': _('Expiring soon'),
            'error': _('Error'),
            'disabled': _('Turned off'),
            'legacy': _('Not migrated'),
        }

    @api.model
    def _center_check_labels(self):
        """Readiness keys in words a clinic manager can act on."""
        return {
            'authorization_valid': _('Sign-in valid'),
            'scopes_granted': _('Permissions granted'),
            'resource_selected': _('Account chosen'),
            'webhook_configured': _('Connection set up'),
            'webhook_verified': _('Connection confirmed'),
            'outbound_ok': _('Sending works'),
            'inbound_ok': _('Receiving works'),
            'token_fresh': _('Sign-in up to date'),
            'provider_approvals': _('Provider approvals'),
        }

    @api.model
    def _center_guide_texts(self):
        """``guide_steps`` keys → the words on the stepper screens.

        The two implemented channels carry real copy; the rest carry titles so
        a tenant can see what connecting WOULD involve before it is offered.
        """
        return {
            # -- Telegram (guided secret) ---------------------------------
            'channel_hub.guide.telegram.botfather': {
                'title': _('Create your bot'),
                'body': _('Open Telegram and message @BotFather. Send '
                          '/newbot, choose a name, and BotFather replies with '
                          'a key.'),
                'link': 'https://t.me/BotFather',
                'link_label': _('Open BotFather'),
            },
            'channel_hub.guide.telegram.paste': {
                'title': _('Paste the key'),
                'body': _('Paste the key BotFather gave you. We check it with '
                          'Telegram before saving anything, and you will see '
                          'your bot name to confirm it is the right one.'),
            },
            'channel_hub.guide.telegram.connecting': {
                'title': _('We set things up'),
                'body': _('We connect your bot to Health19. Nothing to do '
                          'here — it takes a moment.'),
            },
            'channel_hub.guide.telegram.test': {
                'title': _('Say hello'),
                'body': _('Open Telegram, find your bot and send it any '
                          'message — we will answer here.'),
            },
            # -- Web chat (one click) -------------------------------------
            'channel_hub.guide.webchat.enable': {
                'title': _('Turn on web chat'),
                'body': _('Tell us which website addresses the chat bubble '
                          'may appear on, for example https://vietuc.vn.'),
            },
            'channel_hub.guide.webchat.embed': {
                'title': _('Add it to your website'),
                'body': _('Copy this one line into your website, just before '
                          'the closing body tag.'),
            },
            'channel_hub.guide.webchat.verify': {
                'title': _('Send a test message'),
                'body': _('Open your website, use the chat bubble and send a '
                          'message. It appears in Care Command straight away.'),
            },
            # -- structure only (CC-D / CC-E / CC-F) -----------------------
            'channel_hub.guide.whatsapp.signin': {'title': _('Sign in with Meta')},
            'channel_hub.guide.whatsapp.number': {'title': _('Choose your number')},
            'channel_hub.guide.whatsapp.connecting': {'title': _('We set things up')},
            'channel_hub.guide.whatsapp.test': {'title': _('Send a test')},
            'channel_hub.guide.fb.signin': {'title': _('Sign in with Facebook')},
            'channel_hub.guide.fb.page': {'title': _('Choose your Page')},
            'channel_hub.guide.fb.connecting': {'title': _('We set things up')},
            'channel_hub.guide.fb.test': {'title': _('Send a test')},
            'channel_hub.guide.zalo.signin': {'title': _('Sign in with Zalo')},
            'channel_hub.guide.zalo.webhook': {'title': _('Point Zalo at us')},
            'channel_hub.guide.zalo.verify': {'title': _('Wait for confirmation')},
            'channel_hub.guide.zalo.test': {'title': _('Send a test')},
            'channel_hub.guide.zns.templates': {'title': _('Message templates')},
            'channel_hub.guide.email.signin': {'title': _('Sign in to your mailbox')},
            'channel_hub.guide.email.mailbox': {'title': _('Confirm the mailbox')},
            'channel_hub.guide.email.test': {'title': _('Send a test')},
            'channel_hub.guide.call.credentials': {'title': _('Enter your phone system key')},
            'channel_hub.guide.call.webhook': {'title': _('Point your phone system at us')},
            'channel_hub.guide.call.test': {'title': _('Make a test call')},
        }

    # ==================================================================
    # Access + lookup
    # ==================================================================
    @api.model
    def _center_connection(self, channel, company=None):
        """The company's live connection row for ``channel``, if any.

        Disabled rows are INCLUDED on purpose (a deviation from the handover's
        "non-disabled"): disconnect is a state, not a delete, so the row a
        tenant must be able to reconnect is exactly the disabled one — and the
        partial unique index means creating a second active row for the same
        channel would raise instead. Archived rows stay invisible (the implicit
        ``active`` filter), which is what "newest active" is really for.
        """
        company = company or self.env.company
        if channel not in CENTER_CHANNELS:
            raise UserError(_('Unknown channel.'))
        return self.sudo().search([
            ('channel', '=', channel),
            ('company_id', '=', company.id),
        ], order='id desc', limit=1)

    @api.model
    def _center_get(self, conn_id):
        """Resolve + gate one connection id coming from the browser."""
        try:
            conn_id = int(conn_id or 0)
        except (TypeError, ValueError):
            conn_id = 0
        conn = self.sudo().browse(conn_id).exists()
        if not conn:
            raise UserError(_('This channel is not set up yet.'))
        conn._check_center_access()
        return conn

    @api.model
    def _center_platform_available(self, caps):
        """Is the platform-side prerequisite in place for this channel?

        ``needs_platform_app`` channels are offerable only where the platform
        operator has seeded (and kept active) the provider's app — otherwise
        "Connect" could only ever fail, and the honest answer is the
        pending-approval copy (architecture §4).
        """
        if not caps.get('needs_platform_app'):
            return True
        providers = list(caps.get('platform_providers') or [])
        if not providers:
            # Declared as needing one but naming none: refuse to claim it is
            # available rather than guess.
            return False
        return bool(self.env['channel.platform.app'].sudo().search_count(
            [('provider', 'in', providers), ('active', '=', True)]))

    # ==================================================================
    # 1. center_overview — the catalogue
    # ==================================================================
    @api.model
    def center_overview(self):
        """One card dict per channel key, for ``self.env.company``.

        Carries NO credential material of any kind — not the hint, not the
        ciphertext, not a scope string. T97 dumps the whole payload to JSON and
        asserts the seeded secrets do not appear in it.
        """
        if not self._center_group_ok():
            raise UserError(_(
                'Only a Care Command manager or a tenant administrator can '
                'set up channels.'))
        company = self.env.company
        labels = self._center_channel_labels()
        chips = self._center_state_chips()
        check_labels = self._center_check_labels()
        cards = []
        for channel in CENTER_CHANNELS:
            probe = self.sudo().new({'channel': channel,
                                     'company_id': company.id})
            try:
                caps = probe._capabilities()
            except ValueError:
                continue
            parent = caps.get('parent_channel')
            conn = self._center_connection(parent or channel, company)
            available = self._center_platform_available(caps)
            implemented = (caps.get('mode') in IMPLEMENTED_MODES
                           and channel in CENTER_IMPLEMENTED_CHANNELS)
            state = conn.state if conn else 'not_connected'
            required = set(caps.get('required_checks') or [])
            statuses = ({c.check_key: c.status for c in conn.readiness_check_ids}
                        if conn else {})
            checks = [{
                'key': key,
                'label': check_labels.get(key, key),
                'status': statuses.get(key, 'pending'),
            } for key in caps.get('required_checks') or []]
            action, action_label = self._center_primary_action(
                state, available, implemented)
            cards.append({
                'channel': channel,
                'label': labels.get(channel, channel),
                'state': state,
                'state_chip': chips.get(state, state),
                'connection_id': conn.id if conn else False,
                'resource_line': conn._center_resource_line() if conn else '',
                'last_inbound_at': (fields.Datetime.to_string(conn.last_inbound_at)
                                    if conn and conn.last_inbound_at else ''),
                'last_outbound_at': (fields.Datetime.to_string(conn.last_outbound_at)
                                     if conn and conn.last_outbound_at else ''),
                'health_status': (conn.health_status or '') if conn else '',
                'primary_action': action,
                'primary_label': action_label,
                'available': available,
                'implemented': implemented,
                'sendable': state in SENDABLE_STATES,
                'checks': checks,
                'checks_done': sum(1 for c in checks if c['status'] == 'pass'),
                'checks_total': len(required),
                'mode': caps.get('mode'),
                'parent_channel': parent or '',
                'guide_steps': self._center_guide_steps(caps, conn),
            })
        return cards

    @api.model
    def _center_primary_action(self, state, available, implemented):
        """ONE primary action per card (architecture §9)."""
        if not available:
            return 'unavailable', _('Not available yet')
        if not implemented:
            return 'unavailable', _('Available in an upcoming update')
        return {
            'not_connected': ('connect', _('Connect')),
            'authorizing': ('continue', _('Continue setup')),
            'select_resource': ('continue', _('Continue setup')),
            'configuring': ('continue', _('Continue setup')),
            'testing': ('continue', _('Finish setup')),
            'ready': ('open', _('Manage')),
            'action_required': ('fix', _('Fix')),
            'expiring': ('reconnect', _('Reconnect')),
            'error': ('fix', _('Fix')),
            'disabled': ('reconnect', _('Turn back on')),
            'legacy': ('reconnect', _('Upgrade connection')),
        }.get(state, ('connect', _('Connect')))

    def _center_resource_line(self):
        """The card subtitle: what is connected, in the tenant's own words."""
        self.ensure_one()
        return (self.resource_display_name or self.resource_external_id or '')

    @api.model
    def _center_guide_steps(self, caps, conn=None):
        """Resolve the adapter's guide-step KEYS into stepper screens."""
        texts = self._center_guide_texts()
        bot = (conn.resource_display_name or '') if conn else ''
        steps = []
        for key in caps.get('guide_steps') or []:
            entry = dict(texts.get(key) or {'title': _('Set up')})
            if key == 'channel_hub.guide.telegram.test' and bot:
                entry['body'] = _(
                    'Open Telegram, find %s and send it any message — we will '
                    'answer here.', bot)
            entry['key'] = key
            steps.append(entry)
        return steps

    # ==================================================================
    # 2. center_begin — get-or-create, then start the stepper
    # ==================================================================
    @api.model
    def center_begin(self, channel):
        """Get-or-create this company's connection and open its flow.

        Idempotent by construction (T104): the lookup runs before the create,
        and the partial unique index is the backstop.
        """
        if not self._center_group_ok():
            raise UserError(_(
                'Only a Care Command manager or a tenant administrator can '
                'set up channels.'))
        if channel not in CENTER_CHANNELS:
            raise UserError(_('Unknown channel.'))
        probe = self.sudo().new({'channel': channel,
                                 'company_id': self.env.company.id})
        caps = probe._capabilities()
        if caps.get('parent_channel'):
            raise UserError(_(
                'This channel is part of the %s connection — set that up '
                'first.', self._center_channel_labels().get(
                    caps['parent_channel'], caps['parent_channel'])))
        if not self._center_platform_available(caps):
            raise UserError(_('This channel is not available yet.'))
        if caps.get('mode') not in IMPLEMENTED_MODES \
                or channel not in CENTER_IMPLEMENTED_CHANNELS:
            raise UserError(_('This channel is not available yet.'))

        conn = self._center_connection(channel)
        if not conn:
            conn = self.sudo()._internal().create({
                'channel': channel,
                'company_id': self.env.company.id,
            })
            conn = self.sudo().browse(conn.id)
        conn._check_center_access()

        # `authorizing` is where a flow starts; a connection already past that
        # point (or already working) is resumed where it stands.
        if conn.state in ('not_connected', 'disabled', 'error', 'legacy'):
            conn._transition('authorizing', reason='center begin')
        self.env['care.channel.audit']._log(
            'connect_start', connection=conn, detail='channel %s' % channel)
        return {
            'connection_id': conn.id,
            'channel': channel,
            'state': conn.state,
            'mode': caps.get('mode'),
            'guide_steps': self._center_guide_steps(caps, conn),
            'has_credentials': conn.has_credentials,
        }

    # ==================================================================
    # 3. Telegram — the guided BotFather wizard
    # ==================================================================
    @api.model
    def center_telegram_validate(self, conn_id, token):
        """Check a pasted bot token with Telegram, then store it encrypted.

        NOTHING is written before ``getMe`` answers: an invalid token leaves
        no secret, no resource, no state move and no readiness row (T99).
        """
        conn = self._center_get(conn_id)
        if conn.channel != 'telegram':
            raise UserError(_('This is not a Telegram connection.'))
        token = (token or '').strip()
        if not token or not _TG_TOKEN_RE.match(token):
            raise UserError(_(
                'That does not look like a bot key. BotFather sends a line '
                'like 123456789:AAG… — copy the whole line.'))
        try:
            bot = conn._get_adapter().validate_token(token)
        except ChannelSendError as exc:
            _logger.info('care_channels: telegram token validation refused on '
                         'connection %s', conn.id)
            raise UserError(_(
                'Telegram did not accept that key: %s',
                redact(exc) or _('unknown error'))) from exc

        username = bot.get('username') or ''
        display = ('@%s' % username) if username else (bot.get('first_name')
                                                       or bot['id'])
        # Order matters: the secret first (it is what everything else is
        # about), then the public facts, then the checks that derive readiness.
        conn.action_set_secret('provider_secret', token)
        conn.sudo()._internal().write({
            'resource_external_id': bot['id'],
            'resource_display_name': display,
        })
        Check = self.env['care.channel.readiness.check']
        Check.upsert_check(conn, 'authorization_valid', 'pass')
        Check.upsert_check(conn, 'resource_selected', 'pass')
        if conn.state in ('authorizing', 'select_resource'):
            conn._transition('configuring', reason='telegram token validated')
        self.env['care.channel.audit']._log(
            'resource_selected', connection=conn, detail='telegram bot %s' % display)
        return {
            'connection_id': conn.id,
            'bot_name': bot.get('first_name') or display,
            'bot_username': username,
            'resource_line': conn._center_resource_line(),
            'state': conn.state,
        }

    @api.model
    def center_telegram_register_webhook(self, conn_id):
        """Point Telegram at us: mint the path secret once, then ``setWebhook``.

        The path secret is BOTH the unguessable URL segment and the
        ``secret_token`` header value (CC-B's verifier checks the header when
        present), so it is minted once and reused on every re-registration —
        rotating it silently would orphan a webhook Telegram still holds.
        """
        conn = self._center_get(conn_id)
        if conn.channel != 'telegram':
            raise UserError(_('This is not a Telegram connection.'))
        if not conn.has_credentials:
            raise UserError(_('Add your bot key first.'))
        base = (self.env['ir.config_parameter'].sudo().get_param('web.base.url')
                or '').strip().rstrip('/')
        if not base.lower().startswith('https://'):
            # Telegram refuses plain http, and registering one would either
            # fail or hand the updates to an unencrypted hop. Refuse loudly.
            raise UserError(_(
                'Your Health19 address must start with https:// before '
                'Telegram can send messages to it. Ask your administrator to '
                'set the website address, then try again.'))
        secret = conn.sudo().webhook_path_secret
        if not secret:
            secret = secrets.token_urlsafe(32)
            conn.sudo()._internal().write({'webhook_path_secret': secret})
        url = '%s%s%s' % (base, TELEGRAM_WEBHOOK_PATH, secret)
        try:
            conn.sudo()._get_adapter().register_webhook(
                url=url, secret_token=secret)
        except ChannelSendError as exc:
            # The UserError below rolls this transaction back, so the evidence
            # goes to an independent cursor first (ledger §5.65). No identity
            # is involved, so `_persist_send_failure` records the redacted
            # reason and the audit row without a message row.
            if not conn._persist_send_failure(None, None, exc):
                conn._note_send_failure(exc)
                self.env['care.channel.audit']._log(
                    'test_fail', connection=conn, detail='setWebhook: %s' % exc)
            raise UserError(_(
                'Telegram could not be connected: %s',
                redact(exc) or _('unknown error'))) from exc

        conn.sudo()._internal().write({'webhook_state': 'subscribed'})
        self.env['care.channel.readiness.check'].upsert_check(
            conn, 'webhook_configured', 'pass')
        if conn.state in ('authorizing', 'select_resource', 'configuring',
                          'action_required'):
            conn._transition('testing', reason='telegram webhook registered')
            conn._recompute_ready()
        self.env['care.channel.audit']._log(
            'webhook_subscribed', connection=conn, detail='telegram setWebhook')
        return {'connection_id': conn.id, 'state': conn.state,
                'resource_line': conn._center_resource_line()}

    # ==================================================================
    # 4. Web chat — one click
    # ==================================================================
    @api.model
    def _center_validate_origins(self, origins):
        """Website addresses the widget may be embedded on.

        A scheme and a host, nothing else: a path, a query, credentials or a
        ``javascript:`` scheme are all rejected rather than silently trimmed,
        because this list becomes the CORS allowlist of a public route.
        """
        if isinstance(origins, str):
            origins = origins.replace('\n', ',').split(',')
        cleaned = []
        for raw in origins or []:
            value = (raw or '').strip().rstrip('/')
            if not value:
                continue
            parts = urlparse(value)
            local = (parts.hostname or '') in ('localhost', '127.0.0.1', '::1')
            if parts.scheme not in ('http', 'https') or not parts.netloc \
                    or parts.path or parts.params or parts.query \
                    or parts.fragment or parts.username or parts.password \
                    or (parts.scheme == 'http' and not local):
                raise UserError(_(
                    'Use the address of your website, starting with https:// '
                    'and with nothing after the domain — for example '
                    'https://vietuc.vn. We could not use "%s".', value[:80]))
            origin = '%s://%s' % (parts.scheme, parts.netloc)
            if origin not in cleaned:
                cleaned.append(origin)
        if not cleaned:
            raise UserError(_('Add at least one website address.'))
        if len(cleaned) > MAX_ORIGINS:
            raise UserError(_('That is more websites than we can enable at '
                              'once (%s maximum).', MAX_ORIGINS))
        return cleaned

    @api.model
    def center_webchat_enable(self, conn_id, origins, greeting=None):
        """Turn the widget on for a list of websites and hand back the snippet."""
        conn = self._center_get(conn_id)
        if conn.channel != 'webchat':
            raise UserError(_('This is not a web chat connection.'))
        cleaned = self._center_validate_origins(origins)
        settings = {'allowed_origins': cleaned}
        if greeting is not None:
            settings['greeting'] = (greeting or '').strip()[:GREETING_CAP]
        conn.set_settings(settings)
        conn.sudo()._internal().write({
            'resource_external_id': 'default',
            'resource_display_name': _('Website widget'),
        })
        self.env['care.channel.readiness.check'].upsert_check(
            conn, 'resource_selected', 'pass')
        if conn.state in ('authorizing', 'select_resource', 'configuring',
                          'action_required', 'not_connected'):
            if conn.state == 'not_connected':
                conn._transition('authorizing', reason='web chat enable')
            conn._transition('testing', reason='web chat enabled')
            conn._recompute_ready()
        self.env['care.channel.audit']._log(
            'resource_selected', connection=conn,
            detail='webchat origins: %s' % len(cleaned))
        return {
            'connection_id': conn.id,
            'state': conn.state,
            'origins': cleaned,
            'greeting': conn.get_setting('greeting') or '',
            'snippet': self._webchat_embed_snippet(),
            'demo_url': self._webchat_demo_url(),
            'resource_line': conn._center_resource_line(),
        }

    @api.model
    def center_webchat_settings(self, conn_id):
        """What the stepper needs to re-open an already-enabled web chat."""
        conn = self._center_get(conn_id)
        if conn.channel != 'webchat':
            raise UserError(_('This is not a web chat connection.'))
        origins = conn.get_setting('allowed_origins') or []
        if isinstance(origins, str):
            origins = [o.strip() for o in origins.split(',') if o.strip()]
        return {
            'connection_id': conn.id,
            'origins': origins,
            'greeting': conn.get_setting('greeting') or '',
            'snippet': self._webchat_embed_snippet(),
            'demo_url': self._webchat_demo_url(),
        }

    # -- the embed snippet (ONE implementation, shared with the controller) --
    @api.model
    def _widget_version(self):
        """Cache-busting stamp for the embeddable widget (ledger §5.64b).

        Odoo serves ``/<module>/static/…`` with ``max-age=604800`` and no
        revalidation, so without a ``?v=`` every visitor keeps the old widget
        for a week after an upgrade. The installed module version changes on
        exactly the right cadence.
        """
        module = self.env['ir.module.module'].sudo().search(
            [('name', '=', 'health_care_command_channels')], limit=1)
        return module.latest_version or '1'

    @api.model
    def _center_base_url(self):
        return (self.env['ir.config_parameter'].sudo().get_param('web.base.url')
                or '').strip().rstrip('/')

    @api.model
    def _webchat_embed_snippet(self, base=None):
        base = base if base is not None else self._center_base_url()
        return '<script src="%s%s?v=%s" data-origin="%s"></script>' % (
            base, WIDGET_JS, self._widget_version(),
            base or 'https://your-health19-host')

    @api.model
    def _webchat_demo_url(self):
        return '%s%s' % (self._center_base_url(), WEBCHAT_DEMO_PATH)

    # ==================================================================
    # 5. center_test — a SYNTHETIC send, never patient data (§7.6)
    # ==================================================================
    @api.model
    def _center_test_body(self):
        return _('Health19 connection test — please ignore.')

    @api.model
    def center_test(self, conn_id):
        conn = self._center_get(conn_id)
        if conn.channel not in CENTER_IMPLEMENTED_CHANNELS:
            raise UserError(_('Testing this channel is not available yet.'))
        if conn.state in ('not_connected', 'disabled', 'legacy'):
            # `testing` is deliberately allowed: proving outbound is exactly
            # what this button exists for, and that is a testing-state job.
            raise UserError(_('This channel is turned off right now.'))
        identity = self.env['care.channel.identity'].sudo().search(
            [('connection_id', '=', conn.id)], order='last_seen_at desc, id desc',
            limit=1)
        if not identity:
            if conn.channel == 'telegram':
                raise UserError(_(
                    'Send your bot a message from Telegram first — we can '
                    'only reply to a conversation somebody started.'))
            raise UserError(_(
                'Send a message from the chat bubble on your website first — '
                'we can only reply to a conversation somebody started.'))

        body = self._center_test_body()
        Message = self.env['care.channel.message']
        try:
            result = conn.sudo()._get_adapter().send_message(identity, body)
        except Exception as exc:  # noqa: BLE001 — provider/network failure
            auth = any(marker in str(exc).lower()
                       for marker in ('401', 'unauthorized', 'invalid token'))
            if not conn._persist_send_failure(identity, body, exc,
                                              auth_failure=auth):
                Message._record_outbound(conn, identity, body, error=exc)
                conn._note_send_failure(exc, auth_failure=auth)
            self.env['care.channel.audit']._log(
                'test_fail', connection=conn, detail=str(exc))
            raise UserError(_(
                'The test message could not be sent: %s',
                redact(exc) or _('unknown error'))) from exc

        Message._record_outbound(conn, identity, body, result=result)
        self.env['care.channel.audit']._log('test_ok', connection=conn)
        return {'connection_id': conn.id, 'state': conn.state,
                'sent_to': identity.display_name or '',
                'message': _('Test message sent.')}

    # ==================================================================
    # 6. Disconnect / reconnect
    # ==================================================================
    @api.model
    def center_disconnect(self, conn_id):
        """Stop new traffic. NEVER deletes, NEVER wipes a credential.

        Re-enabling must not re-prompt for the bot key (rotation is
        ``action_set_secret``'s job), and the conversation history belongs to
        the clinic, not to the connection.
        """
        conn = self._center_get(conn_id)
        if conn.state == 'disabled':
            return {'connection_id': conn.id, 'state': conn.state}
        conn._transition('disabled', reason='tenant disconnect')
        self.env['care.channel.audit']._log('disconnect', connection=conn)
        return {'connection_id': conn.id, 'state': conn.state,
                'message': _('Turned off.')}

    @api.model
    def center_reconnect(self, conn_id):
        conn = self._center_get(conn_id)
        if conn.state == 'ready':
            return {'connection_id': conn.id, 'state': conn.state}
        conn._transition('authorizing', reason='tenant reconnect')
        self.env['care.channel.audit']._log('reconnect', connection=conn)
        caps = conn._capabilities()
        return {'connection_id': conn.id, 'state': conn.state,
                'mode': caps.get('mode'),
                'has_credentials': conn.has_credentials,
                'guide_steps': self._center_guide_steps(caps, conn)}
