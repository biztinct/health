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
    FB_MESSAGE_TAGS, META_SDK_URL, MODE_EMBEDDED_SIGNUP, MODE_GUIDED_SECRET,
    MODE_OAUTH_POPUP, MODE_ONE_CLICK, ZALO_WEBHOOK_PATH, ChannelSendError,
    meta_window_state,
)
from ..services.redact import redact
from .care_channel_connection import SENDABLE_STATES

_logger = logging.getLogger(__name__)

# The catalogue order IS the dock order (health_care_command CHANNEL_SELECTION).
CENTER_CHANNELS = [key for key, _label in CHANNEL_SELECTION]

# Modes whose stepper is actually implemented. Everything else renders its
# structure and says so — an honest "not yet" beats a button that cannot work.
IMPLEMENTED_MODES = {MODE_GUIDED_SECRET, MODE_ONE_CLICK, MODE_OAUTH_POPUP,
                     MODE_EMBEDDED_SIGNUP}

# Only these channels have a working begin/validate/test flow. The `call`
# adapter also declares guided_secret and `email` declares a popup, but their
# credential exchanges are CC-F — BOTH gates must pass, so those cards stay
# honestly "in an upcoming update".
#
# CC-E adds `whatsapp` and `fb`: their onboarding is software-complete against
# mocks. Being *implemented* is not the same as being *available* — with no
# `channel.platform.app` for provider `meta`, `_center_platform_available`
# still renders both as "Not available yet" and `center_begin` still refuses,
# which is exactly the state of vietuat today (T137).
CENTER_IMPLEMENTED_CHANNELS = {'telegram', 'webchat', 'zalo', 'whatsapp', 'fb'}

# Meta channels, and the `channel.platform.app.extra_json` key that configures
# each one's sign-in (operator checklist §12.3).
META_CHANNELS = ('whatsapp', 'fb')

# ZNS template ids live in per-module ir.config_parameters (architecture §1.2,
# the frozen 10-module contract). The Center counts how many are actually set:
# a tenant with a verified OA and zero configured templates can send nothing,
# and saying "Connected" there would be a lie. Read-only honesty — the Center
# never writes these, and each consumer module owns its own key.
ZNS_TEMPLATE_PARAMS = (
    'health_workflow_auto.zns_template_visit_offer',
    'health_self_booking.zns_template_invite',
    'health_telehealth.zns_template_join',
    'health_schedule_drag.zns_template_rescheduled',
    'health_messaging.zns_template_confirmation',
    'health_messaging.zns_template_reminder24',
    'health_messaging.zns_template_reminder2',
    'health_messaging.zns_template_cancellation',
    'health_family_link.zns_template_family_link',
    'health_family_link.zns_template_family_snapshot',
    'health_family_messages.zns_template_reply',
    'health_pwa_family.zns_template_update',
)

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
    def _center_approval_labels(self):
        """Meta's human review gates, in plain language.

        These are PROVIDER states, not our errors (handover §1.3): a tenant
        whose display name is still under review has done nothing wrong and
        must not see a red failure — they see what is pending and where.
        """
        return {
            'business_verification': {
                'label': _('Business verification'),
                'pending': _('Meta is still reviewing your business.'),
                'pass': _('Meta has verified your business.'),
                'fail': _('Meta did not accept your business verification. '
                          'Open the Meta Business Suite to see what is '
                          'missing.'),
            },
            'display_name': {
                'label': _('Display name'),
                'pending': _('Meta is still reviewing the name clients will '
                             'see.'),
                'pass': _('Your display name is approved.'),
                'fail': _('Meta declined the display name. Choose another one '
                          'in the Meta Business Suite.'),
            },
            'templates': {
                'label': _('Message templates'),
                'pending': _('No approved template yet. Templates are '
                             'approved by Meta, not by us — you need one to '
                             'start a conversation more than 24 hours after a '
                             'client last wrote.'),
                'pass': _('You have at least one approved template.'),
                'fail': _('Meta declined your templates.'),
            },
            'page_access': {
                'label': _('Page access'),
                'pending': _('We could not confirm access to your Page yet.'),
                'pass': _('We can reach your Page.'),
                'fail': _('We can no longer reach your Page. Sign in again.'),
            },
            'unreadable': {
                'label': _('Approval status'),
                'pending': _('We could not read the approval status from Meta '
                             'just now. Nothing is wrong on your side.'),
                'pass': _('Everything Meta reviews is approved.'),
                'fail': _('Meta reported a problem.'),
            },
        }

    @api.model
    def _center_window_texts(self):
        """The provider messaging windows, said out loud (handover §1.4)."""
        return {
            'whatsapp_open': _('You can reply freely for now.'),
            'whatsapp_closed': _(
                'More than 24 hours have passed since this client last wrote, '
                'so WhatsApp only accepts an approved template.'),
            'whatsapp_never': _(
                'This client has never written to you on WhatsApp, so only an '
                'approved template may be sent.'),
            'fb_open': _('You can reply freely for now.'),
            'fb_tag': _(
                'More than 24 hours have passed, so Facebook only accepts a '
                'human-agent reply — available for up to 7 days.'),
            'fb_blocked': _(
                'More than 7 days have passed since this client last wrote. '
                'Facebook no longer allows a reply on this conversation.'),
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
            # -- WhatsApp (Meta Embedded Signup) --------------------------
            'channel_hub.guide.whatsapp.signin': {
                'title': _('Sign in with Meta'),
                'body': _('A Meta window opens. Sign in as the owner of your '
                          'business, then choose or create the WhatsApp '
                          'account you want to use. Your Facebook password is '
                          "only ever typed on Meta's own page."),
            },
            'channel_hub.guide.whatsapp.number': {
                'title': _('Choose your number'),
                'body': _('Pick the WhatsApp number clients should message. '
                          'You can change it later.'),
            },
            'channel_hub.guide.whatsapp.connecting': {
                'title': _('We set things up'),
                'body': _('We tell Meta to send your messages to Health19. '
                          'Nothing to do here — it takes a moment.'),
            },
            'channel_hub.guide.whatsapp.test': {
                'title': _('Send a test'),
                'body': _('Message your WhatsApp number from any phone — we '
                          'will answer here. Meta only lets a business reply '
                          'freely for 24 hours after a client writes; after '
                          'that only an approved template may go out.'),
            },
            # -- Messenger (Facebook Login for Business) -------------------
            'channel_hub.guide.fb.signin': {
                'title': _('Sign in with Facebook'),
                'body': _('A Facebook window opens. Sign in as an '
                          'administrator of your Page and allow Health19 to '
                          'read and reply to its messages. Your Facebook '
                          "password is only ever typed on Facebook's own page."),
            },
            'channel_hub.guide.fb.page': {
                'title': _('Choose your Page'),
                'body': _('Pick the Page whose messages should arrive in Care '
                          'Command.'),
            },
            'channel_hub.guide.fb.connecting': {
                'title': _('We set things up'),
                'body': _('We tell Facebook to send your Page messages to '
                          'Health19. Nothing to do here.'),
            },
            'channel_hub.guide.fb.test': {
                'title': _('Send a test'),
                'body': _('Message your Page from Messenger — we will answer '
                          'here. Facebook lets a business reply freely for 24 '
                          'hours; after that only a human-agent reply is '
                          'allowed, for up to 7 days.'),
            },
            # -- Zalo (OAuth popup + a portal-guided webhook step) ---------
            'channel_hub.guide.zalo.signin': {
                'title': _('Sign in with Zalo'),
                'body': _('A Zalo window opens. Sign in as the owner of your '
                          'Official Account and allow Health19 to work with '
                          'it. Your Zalo password is only ever typed on '
                          "Zalo's own page."),
            },
            'channel_hub.guide.zalo.webhook': {
                'title': _('Point Zalo at us'),
                'body': _('Open the Zalo developer portal, choose your app, '
                          'and paste the address below into the Webhook '
                          'field. Zalo shows a secret on that page — copy it '
                          'back here.'),
                'link': 'https://developers.zalo.me/app',
                'link_label': _('Open the Zalo developer portal'),
            },
            'channel_hub.guide.zalo.verify': {
                'title': _('Wait for confirmation'),
                'body': _('Send your Official Account any message from Zalo. '
                          'The moment it reaches us, this step turns green.'),
            },
            'channel_hub.guide.zalo.test': {
                'title': _('Send a test'),
                'body': _('We reply to the newest Zalo conversation so you '
                          'can see the whole round trip working.'),
            },
            'channel_hub.guide.zns.templates': {
                'title': _('Message templates'),
                'body': _('Zalo notification templates are approved by Zalo, '
                          'not by us. Each Health19 feature that sends one '
                          'has its own template setting.'),
            },
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
            if channel == 'zns':
                cards[-1]['zns'] = self._center_zns_status(conn)
            if channel in META_CHANNELS:
                cards[-1]['approvals'] = self._center_approvals(conn)
        return cards

    # ------------------------------------------------------------------
    # Meta approvals — first-class STATE on the card, never an error dialog
    # ------------------------------------------------------------------
    @api.model
    def _center_approvals(self, conn=None):
        """The provider-review rows for a Meta connection, translated.

        Reads the CACHE the adapter wrote on its last health check or explicit
        refresh: rendering the catalogue must never make a Graph call, and a
        Meta outage must never blank the Center. An empty cache is honest —
        "we have not asked yet" — not an assertion that anything is approved.
        """
        labels = self._center_approval_labels()
        rows = []
        if conn:
            try:
                rows = conn.sudo()._get_adapter().approvals()
            except (ValueError, NotImplementedError, AttributeError):
                rows = []
        out = []
        for row in rows or []:
            key = row.get('key') or 'unreadable'
            text = labels.get(key) or labels['unreadable']
            status = row.get('status') if row.get('status') in (
                'pass', 'pending', 'fail') else 'pending'
            out.append({
                'key': key,
                'label': text['label'],
                'status': status,
                'message': text[status],
            })
        return out

    # ------------------------------------------------------------------
    # ZNS readiness — honest, and never asserted
    # ------------------------------------------------------------------
    @api.model
    def _center_zns_status(self, conn=None):
        """What is really true about Zalo notifications right now.

        Two independent facts, neither of which we can fake:

        * how many of the ten consumer modules' ZNS template ids are actually
          configured (read-only count over their own ir.config_parameters);
        * whether a ZNS message has EVER been accepted by Zalo — which is what
          flips ``provider_approvals`` to ``pass``. Template approval is a
          human Zalo review with a funded ZCA behind it (architecture §13);
          there is no attestation button here, because a tenant clicking "yes
          it is approved" would prove nothing.
        """
        icp = self.env['ir.config_parameter'].sudo()
        configured = [key for key in ZNS_TEMPLATE_PARAMS
                      if (icp.get_param(key) or '').strip()]
        approvals = 'pending'
        if conn:
            row = self.env['care.channel.readiness.check'].sudo().search([
                ('connection_id', '=', conn.id),
                ('check_key', '=', 'provider_approvals')], limit=1)
            approvals = row.status if row else 'pending'
        return {
            'templates_configured': len(configured),
            'templates_total': len(ZNS_TEMPLATE_PARAMS),
            'approvals': approvals,
            'last_outbound_at': (fields.Datetime.to_string(conn.last_outbound_at)
                                 if conn and conn.last_outbound_at else ''),
            'note': (_('%(done)s of %(total)s notification templates are '
                       'configured.',
                       done=len(configured), total=len(ZNS_TEMPLATE_PARAMS))),
            'proof': (_('Proven: Zalo has accepted a notification from this '
                        'account.') if approvals == 'pass'
                      else _('Not proven yet: no notification has been '
                             'accepted by Zalo from this account.')),
        }

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
                    'test_fail', connection=conn,
                    detail='setWebhook: %s' % redact(exc))
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
    # 3b. Zalo — the first OAuth-popup channel
    # ==================================================================
    @api.model
    def _center_zalo(self, conn_id):
        conn = self._center_get(conn_id)
        if conn.channel != 'zalo':
            raise UserError(_('This is not a Zalo connection.'))
        return conn

    @api.model
    def _center_require_https(self):
        base = self._center_base_url()
        if not base.lower().startswith('https://'):
            raise UserError(_(
                'Your Health19 address must start with https:// before Zalo '
                'can sign you in or send messages to it. Ask your '
                'administrator to set the website address, then try again.'))
        return base

    @api.model
    def center_zalo_authorize(self, conn_id):
        """Mint a single-use authorization attempt and hand back its URL.

        The raw state and the PKCE verifier NEVER come back to the browser as
        values of their own: the state is inside the URL because the provider
        needs it there, and the verifier never leaves the server at all.
        """
        conn = self._center_zalo(conn_id)
        caps = conn._capabilities()
        if not self._center_platform_available(caps):
            raise UserError(_('This channel is not available yet.'))
        self._center_require_https()
        if conn.state in ('not_connected', 'disabled', 'error', 'legacy',
                          'configuring', 'testing', 'select_resource',
                          'action_required', 'ready', 'expiring'):
            if conn.state != 'authorizing':
                conn._transition('authorizing', reason='zalo sign-in')
        Session = self.env['care.channel.oauth.session']
        opened = Session.create_for(conn, provider='zalo')
        session = Session.sudo().browse(opened['session_id'])
        try:
            url = conn.sudo()._get_adapter().authorize_url(
                session, opened['state'], opened['code_challenge'])
        except ChannelSendError as exc:
            session.sudo().write({'outcome': 'error',
                                  'detail_redacted': redact(exc)})
            raise UserError(_(
                'Zalo sign-in could not be started: %s',
                redact(exc) or _('unknown error'))) from exc
        return {'connection_id': conn.id, 'state': conn.state, 'url': url}

    @api.model
    def center_zalo_info(self, conn_id):
        """Everything the webhook step needs to render — and no secret."""
        conn = self._center_zalo(conn_id)
        return {
            'connection_id': conn.id,
            'state': conn.state,
            'webhook_url': '%s%s' % (self._center_base_url(),
                                     ZALO_WEBHOOK_PATH),
            'has_webhook_secret': bool(conn.sudo().provider_secret_enc),
            'resource_line': conn._center_resource_line(),
            'zns': self._center_zns_status(conn),
        }

    @api.model
    def center_zalo_set_webhook_secret(self, conn_id, secret):
        """Store the per-OA webhook secret the tenant copied from the portal.

        This proves the tenant has done THEIR half (``webhook_configured``).
        ``webhook_verified`` stays pending until a real signed event arrives —
        a pasted secret is a claim, an accepted signature is evidence.
        """
        conn = self._center_zalo(conn_id)
        self._center_require_https()
        secret = (secret or '').strip()
        if not secret:
            raise UserError(_(
                'Paste the webhook secret Zalo shows on your app page.'))
        conn.action_set_secret('provider_secret', secret)
        conn.sudo()._internal().write({'webhook_state': 'subscribed'})
        self.env['care.channel.readiness.check'].upsert_check(
            conn, 'webhook_configured', 'pass')
        if conn.state in ('authorizing', 'select_resource', 'configuring',
                          'action_required'):
            conn._transition('testing', reason='zalo webhook secret stored')
            conn._recompute_ready()
        self.env['care.channel.audit']._log(
            'webhook_subscribed', connection=conn,
            detail='zalo per-OA webhook secret stored')
        return {'connection_id': conn.id, 'state': conn.state,
                'webhook_url': '%s%s' % (self._center_base_url(),
                                         ZALO_WEBHOOK_PATH),
                'has_webhook_secret': True}

    # ==================================================================
    # 3c. Meta — WhatsApp (Embedded Signup v4) and Messenger (FLB)
    # ==================================================================
    @api.model
    def _center_meta(self, conn_id):
        conn = self._center_get(conn_id)
        if conn.channel not in META_CHANNELS:
            raise UserError(_('This is not a WhatsApp or Messenger connection.'))
        return conn

    @api.model
    def center_meta_start(self, channel):
        """Open a sign-in attempt for a Meta channel.

        WhatsApp gets the payload its JS SDK needs (app id + Embedded Signup
        configuration id + the single-use state); Messenger gets the Facebook
        Login for Business dialog URL. **Neither carries the app secret** — it
        exists only in the server-to-server exchange (T127).
        """
        if channel not in META_CHANNELS:
            raise UserError(_('Unknown channel.'))
        conn = self._center_connection(channel)
        if not conn:
            raise UserError(_('This channel is not set up yet.'))
        conn._check_center_access()
        caps = conn._capabilities()
        if not self._center_platform_available(caps):
            raise UserError(_('This channel is not available yet.'))
        self._center_require_https()
        if conn.state != 'authorizing':
            conn._transition('authorizing', reason='meta sign-in')
        Session = self.env['care.channel.oauth.session']
        # PKCE is stored but unused: Meta's server-side code exchange does not
        # accept a code_verifier (handover §2.3). The single-use, hashed,
        # 10-minute state is mandatory either way.
        opened = Session.create_for(conn, provider='meta')
        session = Session.sudo().browse(opened['session_id'])
        try:
            payload = conn.sudo()._get_adapter().authorize_url(
                session, opened['state'], opened['code_challenge'])
        except ChannelSendError as exc:
            session.sudo().write({'outcome': 'error',
                                  'detail_redacted': redact(exc)})
            raise UserError(_(
                'Sign-in could not be started: %s',
                redact(exc) or _('unknown error'))) from exc
        result = {'connection_id': conn.id, 'channel': channel,
                  'state': conn.state, 'mode': caps.get('mode'),
                  'sdk_url': META_SDK_URL}
        if isinstance(payload, dict):
            result.update(payload)
            result['state_token'] = payload.get('state')
            # `state` on the envelope is the CONNECTION state (every other
            # Center endpoint uses it that way); the authorization state rides
            # as `state_token` so the two can never be confused in the UI.
            result['state'] = conn.state
        else:
            result['url'] = payload
        return result

    @api.model
    def center_meta_exchange(self, conn_id, code, state=None,
                             resource_hint=None):
        """WhatsApp only: the Embedded Signup code, handed over by the SDK.

        The ES popup returns its code to the BROWSER (there is no redirect for
        the OAuth controller to catch), so this endpoint is the exchange's
        front door — and it is gated exactly like ``center_telegram_validate``:
        group, company, channel. The code is credential material and is never
        logged, never echoed and never stored.

        ``state`` is the single-use authorization state minted by
        ``center_meta_start``; it is burned here, so a code cannot be replayed
        into a second connection or a second tab (deviation D1 — the handover's
        signature named only ``(conn_id, code)``, but T127's "state single-use"
        needs a consumer).

        ``resource_hint`` carries the ``waba_id`` / ``phone_number_id`` the ES
        popup announced through ``postMessage``. Both are PUBLIC provider ids,
        never credentials, and they are only a hint: the authoritative WABA
        list still comes from Meta's own ``debug_token`` granular scopes.
        """
        conn = self._center_meta(conn_id)
        if conn.channel != 'whatsapp':
            raise UserError(_(
                'Messenger sign-in finishes on its own — there is nothing to '
                'paste here.'))
        if not code or not isinstance(code, str) or not code.strip():
            raise UserError(_('Meta sign-in did not complete. Please try '
                              'again.'))
        Session = self.env['care.channel.oauth.session']
        session = Session._consume(state)
        if not session or session.connection_id != conn \
                or session.provider != 'meta':
            # One generic refusal for unknown / used / expired / foreign — the
            # endpoint must not become an oracle for valid states.
            raise UserError(_('This sign-in has expired. Please start again.'))
        params = {'code': code.strip()}
        if isinstance(resource_hint, dict):
            for key in ('waba_id', 'phone_number_id'):
                value = str(resource_hint.get(key) or '').strip()
                # Provider ids are digits; refusing anything else keeps a
                # browser-supplied value out of a Graph path.
                if value and value.isdigit():
                    params[key] = value
        try:
            result = conn.sudo()._get_adapter().handle_callback(session, params)
        except ChannelSendError as exc:
            session.sudo().write({'outcome': 'error',
                                  'detail_redacted': redact(exc)})
            self.env['care.channel.audit']._log(
                'callback_error', connection=conn, detail=exc)
            raise UserError(_(
                'Meta did not complete the sign-in: %s',
                redact(exc) or _('unknown error'))) from exc
        session.sudo().write({'outcome': 'ok'})
        self.env['care.channel.audit']._log(
            'callback_ok', connection=conn, detail='whatsapp embedded signup')
        conn.invalidate_recordset()
        return {
            'connection_id': conn.id,
            'state': conn.state,
            'missing_scopes': (result or {}).get('missing_scopes') or [],
            'resource_line': conn._center_resource_line(),
        }

    @api.model
    def center_meta_resources(self, conn_id):
        """The picker list: WhatsApp numbers, or Facebook Pages.

        Carries no token of any kind — the Messenger reply from Meta contains
        one non-expiring credential per Page, and the adapter strips them
        before this ever returns.
        """
        conn = self._center_meta(conn_id)
        try:
            resources = conn.sudo()._get_adapter().list_resources()
        except ChannelSendError as exc:
            raise UserError(_(
                'We could not read your %(channel)s accounts: %(reason)s',
                channel=self._center_channel_labels().get(conn.channel,
                                                          conn.channel),
                reason=redact(exc) or _('unknown error'))) from exc
        return {'connection_id': conn.id, 'state': conn.state,
                'selected': conn.resource_external_id or '',
                'hint': conn.sudo().get_setting('meta_phone_hint') or '',
                'resources': resources}

    @api.model
    def center_meta_select(self, conn_id, external_id):
        """Pin the connection to one number / Page."""
        conn = self._center_meta(conn_id)
        try:
            resource = conn.sudo()._get_adapter().select_resource(external_id)
        except ChannelSendError as exc:
            raise UserError(_(
                'That choice could not be saved: %s',
                redact(exc) or _('unknown error'))) from exc
        if conn.state in ('authorizing', 'select_resource'):
            conn._transition('configuring', reason='meta resource selected')
        conn.invalidate_recordset()
        return {'connection_id': conn.id, 'state': conn.state,
                'selected': conn.resource_external_id or '',
                'resource_line': conn._center_resource_line(),
                'resource': resource}

    @api.model
    def center_meta_subscribe(self, conn_id):
        """Register the webhook with Meta (``POST /{id}/subscribed_apps``).

        A refusal writes the redacted evidence and leaves ``webhook_state`` /
        ``webhook_configured`` untouched: a card that says "connection set up"
        when Meta said no is precisely the lie this framework exists to stop.
        """
        conn = self._center_meta(conn_id)
        self._center_require_https()
        try:
            conn.sudo()._get_adapter().subscribe_webhook()
        except ChannelSendError as exc:
            if not conn._persist_send_failure(None, None, exc):
                conn._note_send_failure(exc)
            raise UserError(_(
                'Meta could not be connected: %s',
                redact(exc) or _('unknown error'))) from exc
        if conn.state in ('authorizing', 'select_resource', 'configuring',
                          'action_required'):
            conn._transition('testing', reason='meta webhook subscribed')
        conn._recompute_ready()
        conn.invalidate_recordset()
        return {'connection_id': conn.id, 'state': conn.state,
                'resource_line': conn._center_resource_line()}

    @api.model
    def center_meta_approvals(self, conn_id, refresh=False):
        """Where Meta's human reviews stand, optionally re-read from Graph."""
        conn = self._center_meta(conn_id)
        if refresh:
            conn.sudo()._get_adapter().refresh_approvals()
            self.env['care.channel.audit']._log(
                'approvals_refreshed', connection=conn)
            conn.invalidate_recordset()
        return {'connection_id': conn.id, 'state': conn.state,
                'approvals': self._center_approvals(conn)}

    @api.model
    def center_meta_templates(self, conn_id):
        """The WhatsApp templates Meta has APPROVED — the outside-window path."""
        conn = self._center_meta(conn_id)
        if conn.channel != 'whatsapp':
            raise UserError(_('Only WhatsApp uses message templates.'))
        try:
            templates = conn.sudo()._get_adapter().list_message_templates()
        except ChannelSendError as exc:
            raise UserError(_(
                'We could not read your templates: %s',
                redact(exc) or _('unknown error'))) from exc
        return {'connection_id': conn.id, 'templates': templates,
                'tags': list(FB_MESSAGE_TAGS)}

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
    def _center_window(self, conn, identity=None):
        """The provider messaging window for one peer, with its plain words.

        Channels that have no window (Telegram, web chat, Zalo) answer ``open``
        with no restriction, so every caller can ask unconditionally.
        """
        state = meta_window_state(self.env, conn.sudo(), identity)
        texts = self._center_window_texts()
        if conn.channel == 'whatsapp':
            if state['open']:
                state['message'] = texts['whatsapp_open']
            elif not state['last_inbound_at']:
                state['message'] = texts['whatsapp_never']
            else:
                state['message'] = texts['whatsapp_closed']
        elif conn.channel == 'fb':
            if state['open']:
                state['message'] = texts['fb_open']
            elif state['requires_tag']:
                state['message'] = texts['fb_tag']
            else:
                state['message'] = texts['fb_blocked']
        else:
            state['message'] = ''
        return state

    @api.model
    def center_test(self, conn_id):
        conn = self._center_get(conn_id)
        if conn.channel not in CENTER_IMPLEMENTED_CHANNELS:
            raise UserError(_('Testing this channel is not available yet.'))
        if conn.state in ('not_connected', 'disabled', 'legacy'):
            # `testing` is deliberately allowed: proving outbound is exactly
            # what this button exists for, and that is a testing-state job.
            raise UserError(_('This channel is turned off right now.'))
        if conn.channel == 'zalo':
            return self._center_test_zalo(conn)
        identity = self.env['care.channel.identity'].sudo().search(
            [('connection_id', '=', conn.id)], order='last_seen_at desc, id desc',
            limit=1)
        if not identity:
            if conn.channel == 'telegram':
                raise UserError(_(
                    'Send your bot a message from Telegram first — we can '
                    'only reply to a conversation somebody started.'))
            if conn.channel == 'whatsapp':
                raise UserError(_(
                    'Message your WhatsApp number from any phone first — Meta '
                    'only lets a business reply to a conversation the client '
                    'started.'))
            if conn.channel == 'fb':
                raise UserError(_(
                    'Message your Page from Messenger first — Facebook only '
                    'lets a business reply to a conversation the client '
                    'started.'))
            raise UserError(_(
                'Send a message from the chat bubble on your website first — '
                'we can only reply to a conversation somebody started.'))

        body = self._center_test_body()
        Message = self.env['care.channel.message']
        # Meta's customer-service window applies to the test send too: pushing
        # a free-form message at a closed window would fail AT META and read
        # as "the connection is broken" when the connection is fine (§1.4).
        window = self._center_window(conn, identity)
        kwargs = {}
        if window.get('blocked'):
            raise UserError(_(
                'Facebook no longer allows a reply on that conversation — it '
                'is more than 7 days old. Ask someone to message your Page '
                'again, then test.'))
        if window.get('requires_template'):
            raise UserError(_(
                'WhatsApp only accepts an approved template more than 24 '
                'hours after a client last wrote. Message your WhatsApp '
                'number from any phone, then test again.'))
        if window.get('requires_tag') and window.get('tags'):
            kwargs['tag'] = window['tags'][0]
        try:
            result = conn.sudo()._get_adapter().send_message(
                identity, body, **kwargs)
        except Exception as exc:  # noqa: BLE001 — provider/network failure
            auth = any(marker in str(exc).lower()
                       for marker in ('401', 'unauthorized', 'invalid token'))
            if not conn._persist_send_failure(identity, body, exc,
                                              auth_failure=auth):
                Message._record_outbound(conn, identity, body, error=exc)
                conn._note_send_failure(exc, auth_failure=auth)
            self.env['care.channel.audit']._log(
                'test_fail', connection=conn, detail=redact(exc))
            raise UserError(_(
                'The test message could not be sent: %s',
                redact(exc) or _('unknown error'))) from exc

        Message._record_outbound(conn, identity, body, result=result)
        self.env['care.channel.audit']._log('test_ok', connection=conn)
        return {'connection_id': conn.id, 'state': conn.state,
                'sent_to': identity.display_name or '',
                'message': _('Test message sent.')}

    @api.model
    def _center_test_zalo(self, conn):
        """Reply on the newest Zalo thread, through the rails ops already use.

        NOT an adapter send: Zalo chat storage and the ops send path stay on
        ``zalo.message`` (handover §2.3), so the test writes exactly the row
        the composer writes and calls the same ``action_send_message``. The
        body is the fixed synthetic string — never patient data (§7.6).

        Deliberately NOT routed through ``care.conversation.action_send_zalo``:
        that method gates on the CRM-staff group, which two of the Center's
        three personas (a platform operator, a tenant administrator) are not
        in — the test button would refuse the very people the Center is for.
        """
        if 'zalo.message' not in self.env:
            raise UserError(_('The Zalo module is not installed.'))
        Care = self.env['care.conversation'].sudo()
        conv = Care.search([
            ('company_id', '=', conn.company_id.id),
            ('zalo_conversation_id', '!=', False),
        ], order='last_event_at desc, id desc', limit=1)
        if not conv:
            raise UserError(_(
                'Send your Official Account a message from Zalo first — we '
                'can only reply to a conversation somebody started.'))
        body = self._center_test_body()
        message = self.env['zalo.message'].sudo().create({
            'conversation_id': conv.zalo_conversation_id.id,
            'direction': 'outgoing',
            'message_type': 'text',
            'text': body,
            'state': 'draft',
        })
        try:
            message.action_send_message()
        except Exception as exc:  # noqa: BLE001 — provider/network failure
            auth = any(marker in str(exc).lower()
                       for marker in ('401', 'unauthorized', 'invalid token',
                                      'access token'))
            # Evidence first, on an independent cursor: the UserError below
            # rolls this transaction back, message row included (§5.65).
            if not conn._persist_send_failure(None, body, exc,
                                              auth_failure=auth):
                conn._note_send_failure(exc, auth_failure=auth)
            self.env['care.channel.audit']._log(
                'test_fail', connection=conn, detail=redact(exc))
            raise UserError(_(
                'The test message could not be sent: %s',
                redact(exc) or _('unknown error'))) from exc
        conn._note_outbound()
        self.env['care.channel.audit']._log('test_ok', connection=conn)
        return {'connection_id': conn.id, 'state': conn.state,
                'sent_to': conv.display_name_c or '',
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
        if conn.state in ('ready', 'authorizing'):
            return {'connection_id': conn.id, 'state': conn.state}
        conn._transition('authorizing', reason='tenant reconnect')
        self.env['care.channel.audit']._log('reconnect', connection=conn)
        caps = conn._capabilities()
        return {'connection_id': conn.id, 'state': conn.state,
                'mode': caps.get('mode'),
                'has_credentials': conn.has_credentials,
                'guide_steps': self._center_guide_steps(caps, conn)}
