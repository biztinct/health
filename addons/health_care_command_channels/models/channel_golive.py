# -*- coding: utf-8 -*-
"""Phase GL-1 — the Go-Live Studio's server framework.

CC-G gave the platform operator a *checklist*: a Html field that says what is
still missing. This phase gives the same knowledge a **structure** — an ordered
list of steps per provider, each one saying what to do, where to do it, what to
paste, what to type back, and how Health19 will know it happened — so that GL-2
can build a real console on top of it and GL-3 can hand a step to somebody who
is not the operator.

Three rules shape everything below.

* **Copy is translated at call time.** ``_golive_steps()`` is an ``@api.model``
  method returning ``_()`` strings, cloned from
  ``channel.center._center_guide_texts()``. A module-level list of strings
  would be frozen in English at import (the selection-translation rule).
* **The step keys are a stable API.** GL-2's UI, GL-3's invitations and the
  progress rows all key on them. Renaming one after ship silently orphans an
  operator's marks.
* **Derived truth beats a checkbox.** ``channel.golive.progress`` is operator
  *convenience* — "I have submitted the paperwork" — and it can never make a
  step say done when the artifact it is about is missing. Every step whose
  completion Health19 can observe (a client id, a stored secret, a passing
  preflight, a webhook handshake, a configuration id) is computed from the
  observation, and the mark is only consulted where there is nothing to
  observe.

Safety posture inherited from ``channel_platform_app.py`` and unchanged here:
no ``tracking=True`` on anything, the secret is written ONLY through
``action_set_secret``, ``extra_json`` is merged and never replaced, and no
credential material appears in any return value — ``secret_hint`` and the
webhook verify token (which already lives in the visible ``extra_json``) are
the ceiling.
"""
import json
import logging
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from ..services.adapters import (
    CHANNEL_ADAPTERS, META_ES_CONFIG_KEY, META_FLB_CONFIG_KEY,
)
from ..services.webhook_verify import VERIFY_TOKEN_KEY

from .channel_platform_app import (
    OAUTH_REDIRECT_PATHS, PROVIDERS, WEBHOOK_PATHS,
)

_logger = logging.getLogger(__name__)

# The two providers the Studio drives in GL-1. Google and Microsoft are GL-4:
# their sign-in runs on Odoo's own mixins, so their steps are a different
# shape and inventing them now would be guesswork with a UI attached.
GOLIVE_PROVIDERS = ('meta', 'zalo')

# Which audit channels prove a provider's webhook handshake reached us. Meta
# subscribes each product separately and either one proves the app's webhook
# configuration; Zalo has exactly one URL for the whole deployment.
GOLIVE_HANDSHAKE_CHANNELS = {'meta': ['whatsapp', 'fb'], 'zalo': ['zalo']}

# The non-secret provider ids a step may write into ``extra_json``.
GOLIVE_EXTRA_KEYS = (META_ES_CONFIG_KEY, META_FLB_CONFIG_KEY)

# Every field a step declaration carries. Present on every step, always —
# ``False`` or ``[]`` where it does not apply, so the UI never has to ask.
GOLIVE_STEP_KEYS = ('key', 'kind', 'title', 'body', 'console', 'console_label',
                    'copy_values', 'inputs', 'verify', 'est')


class ChannelGoliveProgress(models.Model):
    """Operator convenience state — one row per provider.

    Holds ONLY what Health19 cannot observe for itself: "I submitted the
    Business Verification documents on the 3rd". Never a credential, never a
    status another model already knows. No views and no menus: the Studio is
    the only reader.
    """
    _name = 'channel.golive.progress'
    _description = 'Go-Live Studio Progress'
    _order = 'provider'

    provider = fields.Selection(PROVIDERS, required=True, index=True)
    steps_json = fields.Text(
        default='{}',
        help='{step_key: {"marked": true, "marked_on": "YYYY-MM-DD"}} — the '
             'operator\'s own notes on the steps only a human can finish.')
    active = fields.Boolean(default=True)

    # ------------------------------------------------------------------
    # DB constraints — `_sql_constraints` are not materialised on Odoo 19
    # (ledger §5.1), so this is a partial unique index plus a pre-check that
    # runs BEFORE super() (ledger §5.3): a clean ValidationError instead of an
    # IntegrityError that poisons the transaction.
    # ------------------------------------------------------------------
    def init(self):
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS channel_golive_progress_provider_uniq
            ON channel_golive_progress (provider) WHERE active
        """)

    @api.model
    def _check_provider_unique(self, provider, active, exclude_id=None):
        if not provider or not active:
            return
        domain = [('provider', '=', provider), ('active', '=', True)]
        if exclude_id:
            domain.append(('id', '!=', exclude_id))
        if self.sudo().search_count(domain):
            raise ValidationError(_(
                'Go-live progress for this provider already exists.'))

    @api.model
    def _validate_steps_json(self, raw):
        try:
            parsed = json.loads(raw)
        except ValueError:
            raise ValidationError(_('Go-live progress must be valid JSON.'))
        if not isinstance(parsed, dict):
            raise ValidationError(_(
                'Go-live progress must be a JSON object.'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._check_provider_unique(
                vals.get('provider'), vals.get('active', True))
            if vals.get('steps_json'):
                self._validate_steps_json(vals['steps_json'])
        return super().create(vals_list)

    def write(self, vals):
        if 'provider' in vals or 'active' in vals:
            for rec in self:
                self._check_provider_unique(
                    vals.get('provider', rec.provider),
                    vals.get('active', rec.active),
                    exclude_id=rec.id)
        if 'steps_json' in vals and vals['steps_json']:
            self._validate_steps_json(vals['steps_json'])
        return super().write(vals)

    def _steps(self):
        """The parsed marks. A corrupt column reads as "nothing marked" rather
        than breaking the console that would let an operator fix it."""
        self.ensure_one()
        try:
            parsed = json.loads(self.steps_json or '{}')
        except ValueError:
            _logger.warning('channel.golive.progress %s: unparsable steps_json',
                            self.id)
            return {}
        return parsed if isinstance(parsed, dict) else {}


class ChannelPlatformAppGoLive(models.Model):
    _inherit = 'channel.platform.app'

    # ==================================================================
    # D1 — the step declarations
    # ==================================================================
    @api.model
    def _golive_steps(self):
        """Ordered go-live steps per provider.

        All copy goes through ``_()`` at CALL time — a module-level list would
        be frozen in the language the server was imported in. The keys are a
        stable API for the GL-2 UI and the progress rows: never rename one
        after ship.
        """
        return {
            'meta': [
                {
                    'key': 'create_app',
                    'kind': 'do',
                    'title': _('Create the app'),
                    'body': _(
                        'Open the Meta App Dashboard and create a new app of '
                        'type Business. Give it your own company name — every '
                        'clinic signs in through this one app. When the app '
                        'exists, Meta shows an App ID at the top of its '
                        'dashboard. Copy that number here.'),
                    'console': 'https://developers.facebook.com/apps/creation/',
                    'console_label': _('Open the Meta App Dashboard'),
                    'copy_values': [],
                    'inputs': [{
                        'name': 'client_id',
                        'label': _('App ID'),
                        'secret': False,
                        'regex': r'^\d{10,20}$',
                        'error': _('A Meta App ID is a long number — copy it '
                                   'from the top of the app dashboard.'),
                    }],
                    'verify': 'manual',
                    'est': _('about 10 minutes'),
                },
                {
                    'key': 'store_secret',
                    'kind': 'do',
                    'title': _('Store the app secret'),
                    'body': _(
                        'In the same app open Settings, then Basic. The App '
                        'Secret is hidden behind a Show button. Paste it '
                        'here. We encrypt it and never display it again, and '
                        'we ask Meta to confirm it straight away — you will '
                        'see your own app name come back.'),
                    'console': ('https://developers.facebook.com/apps/'
                                '{app_id}/settings/basic/'),
                    'console_label': _('Open Settings, then Basic'),
                    'copy_values': [],
                    'inputs': [{
                        'name': 'client_secret',
                        'label': _('App secret'),
                        'secret': True,
                        'regex': r'^\S{16,128}$',
                        'error': _('The app secret is one long run of '
                                   'characters with no spaces. Press Show '
                                   'next to App Secret in Settings, Basic.'),
                    }],
                    'verify': 'preflight',
                    'est': _('about 5 minutes'),
                },
                {
                    'key': 'business_verification',
                    'kind': 'wait',
                    'title': _('Complete Business Verification'),
                    'body': _(
                        'Meta verifies the business behind the app before it '
                        'lets anyone message clients. Submit your company '
                        'documents in the Security Center. This takes one to '
                        'three weeks and Meta may come back asking for a '
                        'further document. Mark this step once you have '
                        'submitted, so you can see where you are.'),
                    'console': ('https://business.facebook.com/settings/'
                                'security-center'),
                    'console_label': _('Open the Meta Security Center'),
                    'copy_values': [],
                    'inputs': [],
                    'verify': 'manual',
                    'est': _('one to three weeks'),
                },
                {
                    'key': 'app_review',
                    'kind': 'wait',
                    'title': _('Pass App Review'),
                    'body': _(
                        'Ask Meta for these five permissions: '
                        'whatsapp_business_management, '
                        'whatsapp_business_messaging, pages_show_list, '
                        'pages_messaging and pages_manage_metadata. Each one '
                        'needs a short description of how the clinics use it '
                        'and a screen recording. Mark this step once the '
                        'submission is in.'),
                    'console': ('https://developers.facebook.com/apps/'
                                '{app_id}/app-review/permissions/'),
                    'console_label': _('Open App Review'),
                    'copy_values': [],
                    'inputs': [],
                    'verify': 'manual',
                    'est': _('a few days to two weeks'),
                },
                {
                    'key': 'webhooks',
                    'kind': 'do',
                    'title': _('Point Meta at us'),
                    'body': _(
                        'Open Webhooks in the app and subscribe both '
                        'products. Paste the WhatsApp address into the '
                        'WhatsApp product, the Messenger address into the '
                        'Messenger product, and the same verify token into '
                        'both. Add the redirect address to the app while you '
                        'are there. Then press Verify and save: this step '
                        "turns green the moment Meta's check reaches us."),
                    'console': ('https://developers.facebook.com/apps/'
                                '{app_id}/webhooks/'),
                    'console_label': _('Open Webhooks'),
                    'copy_values': ['oauth_redirect_uri', 'webhook_urls',
                                    'verify_token'],
                    'inputs': [],
                    'verify': 'handshake',
                    'est': _('about 10 minutes'),
                },
                {
                    'key': 'config_ids',
                    'kind': 'do',
                    'title': _('Create the two sign-in configurations'),
                    'body': _(
                        'WhatsApp sign-in runs on an Embedded Signup '
                        'configuration; Messenger sign-in runs on a Login for '
                        'Business configuration. Create one of each in the '
                        'app and paste both ids here. Without them a clinic '
                        'cannot even start its sign-in, so the two cards stay '
                        'dark until they are in.'),
                    'console': 'https://developers.facebook.com/apps/{app_id}/',
                    'console_label': _('Open the app dashboard'),
                    'copy_values': [],
                    'inputs': [
                        {
                            'name': META_ES_CONFIG_KEY,
                            'label': _('Embedded Signup configuration id '
                                       '(WhatsApp)'),
                            'secret': False,
                            'regex': r'^\d{5,30}$',
                            'error': _('An Embedded Signup configuration id '
                                       'is a number, shown next to the '
                                       'configuration in the WhatsApp '
                                       'product.'),
                        },
                        {
                            'name': META_FLB_CONFIG_KEY,
                            'label': _('Login for Business configuration id '
                                       '(Messenger)'),
                            'secret': False,
                            'regex': r'^\d{5,30}$',
                            'error': _('A Login for Business configuration id '
                                       'is a number, shown next to the '
                                       'configuration in Facebook Login for '
                                       'Business.'),
                        },
                    ],
                    'verify': 'manual',
                    'est': _('about 15 minutes'),
                },
                {
                    'key': 'done',
                    'kind': 'wait',
                    'title': _('Meta is ready'),
                    'body': _(
                        'Everything Health19 needs from Meta is in place. The '
                        'WhatsApp and Messenger cards are live for every '
                        'clinic, and a clinic can connect its own number or '
                        'Page without anything further from you.'),
                    'console': False,
                    'console_label': False,
                    'copy_values': [],
                    'inputs': [],
                    'verify': 'manual',
                    'est': False,
                },
            ],
            'zalo': [
                {
                    'key': 'create_app',
                    'kind': 'do',
                    'title': _('Create the app'),
                    'body': _(
                        'Create an app on Zalo Developers and link the '
                        'Official Account the clinics will message from. '
                        'Zalo shows the App ID and the App Secret on the '
                        "app's own page once it exists."),
                    'console': 'https://developers.zalo.me',
                    'console_label': _('Open Zalo Developers'),
                    'copy_values': [],
                    'inputs': [],
                    'verify': 'manual',
                    'est': _('about 15 minutes'),
                },
                {
                    'key': 'credentials',
                    'kind': 'do',
                    'title': _('Copy the app credentials'),
                    'body': _(
                        'Copy the App ID and the App Secret from the app '
                        'page. We encrypt the secret and never display it '
                        'again. Zalo publishes no way to check credentials on '
                        "their own, so the first clinic's sign-in is what "
                        'proves them — which is why this step does not turn '
                        'green by itself.'),
                    'console': 'https://developers.zalo.me/app',
                    'console_label': _('Open your Zalo app'),
                    'copy_values': [],
                    'inputs': [
                        {
                            'name': 'client_id',
                            'label': _('Zalo App ID'),
                            'secret': False,
                            'regex': r'^\d{6,30}$',
                            'error': _('A Zalo App ID is a number, shown at '
                                       'the top of the app page.'),
                        },
                        {
                            'name': 'client_secret',
                            'label': _('Zalo App Secret'),
                            'secret': True,
                            'regex': r'^\S{8,128}$',
                            'error': _('The Zalo app secret is one run of '
                                       'characters with no spaces, shown '
                                       'beside the App ID.'),
                        },
                    ],
                    'verify': 'manual',
                    'est': _('about 5 minutes'),
                },
                {
                    'key': 'oauth_redirect',
                    'kind': 'do',
                    'title': _('Add the sign-in address'),
                    'body': _(
                        "Open the app's Official Account settings and add the "
                        'address below as the callback URL. Zalo refuses the '
                        'sign-in unless it matches exactly, character for '
                        'character.'),
                    'console': 'https://developers.zalo.me/app',
                    'console_label': _('Open your Zalo app'),
                    'copy_values': ['oauth_redirect_uri'],
                    'inputs': [],
                    'verify': 'manual',
                    'est': _('about 5 minutes'),
                },
                {
                    'key': 'webhook',
                    'kind': 'do',
                    'title': _('Point Zalo at us'),
                    'body': _(
                        'Paste the address below into the Webhook field of '
                        'the app and turn on the message events. Zalo allows '
                        'ONE webhook address per app, and every clinic '
                        'Official Account shares it — that is normal, we '
                        'recognise each event by the account it came from. '
                        'This step completes when the first verified Zalo '
                        'event arrives.'),
                    'console': 'https://developers.zalo.me/app',
                    'console_label': _('Open your Zalo app'),
                    'copy_values': ['webhook_urls'],
                    'inputs': [],
                    'verify': 'handshake',
                    'est': _('about 10 minutes'),
                },
                {
                    'key': 'done',
                    'kind': 'wait',
                    'title': _('Zalo is ready'),
                    'body': _(
                        'Everything Health19 needs from Zalo is in place. The '
                        'Zalo card is live for every clinic, and each one '
                        'signs in with its own Official Account.'),
                    'console': False,
                    'console_label': False,
                    'copy_values': [],
                    'inputs': [],
                    'verify': 'manual',
                    'est': False,
                },
            ],
        }

    # ------------------------------------------------------------------
    # Declaration lookups
    # ------------------------------------------------------------------
    @api.model
    def _golive_step(self, provider, step_key):
        """One declared step, or a clean ValidationError for either miss."""
        steps = self._golive_steps().get(provider)
        if provider not in GOLIVE_PROVIDERS or not steps:
            raise ValidationError(_(
                'The Go-Live Studio does not drive "%s".', provider))
        for step in steps:
            if step['key'] == step_key:
                return step
        raise ValidationError(_(
            '"%s" is not a step of this go-live.', step_key))

    @api.model
    def _golive_channels(self, provider):
        """The channels an app for ``provider`` serves, from the registry."""
        channels = []
        for channel in sorted(CHANNEL_ADAPTERS):
            caps = CHANNEL_ADAPTERS[channel](
                self.env, channel).authorization_capabilities()
            if provider in (caps.get('platform_providers') or ()):
                channels.append(channel)
        return channels

    @api.model
    def _golive_urls(self, provider):
        """``(redirect_uri, webhook_urls)`` for a provider with or without a row.

        The Studio shows these BEFORE the operator has created anything — they
        are properties of this deployment, not of the row — so they are built
        from the same constants ``_compute_go_live_urls`` uses rather than
        read off a record that may not exist yet.
        """
        base = self._base_url()
        path = OAUTH_REDIRECT_PATHS.get(provider or '')
        redirect = '%s%s' % (base, path) if path else ''
        hooks = WEBHOOK_PATHS.get(provider or '') or []
        webhooks = '\n'.join('%s: %s%s' % (label, base, hook)
                             for label, hook in hooks)
        return redirect, webhooks

    @api.model
    def _golive_handshake_at(self, provider):
        """When a provider's webhook handshake last reached us, or False.

        Read from ``care.channel.audit`` — append-only evidence written by the
        public webhook routes themselves (D4). A step that says "Meta has
        called us" must be backed by Meta actually having called us.
        """
        channels = GOLIVE_HANDSHAKE_CHANNELS.get(provider) or []
        if not channels:
            return False
        row = self.env['care.channel.audit'].sudo().search(
            [('event', '=', 'webhook_handshake'), ('channel', 'in', channels)],
            order='ts desc, id desc', limit=1)
        return fields.Datetime.to_string(row.ts) if row else False

    @api.model
    def _golive_progress_row(self, provider, create=False):
        Progress = self.env['channel.golive.progress'].sudo()
        row = Progress.search(
            [('provider', '=', provider), ('active', '=', True)], limit=1)
        if not row and create:
            row = Progress.create({'provider': provider})
        return row

    # ==================================================================
    # D3 — the RPC surface
    # ==================================================================
    @api.model
    def golive_state(self):
        """The whole Studio, for every provider it drives.

        The UI repaints from this and from nothing else, which is why every
        write method returns it again: a screen that keeps its own copy of
        "step 3 is done" is a screen that can disagree with the database.
        """
        self._require_operator()
        return [self._golive_provider_state(provider)
                for provider in GOLIVE_PROVIDERS]

    def _golive_provider_state(self, provider):
        """One provider's payload. NEVER contains credential material —
        ``secret_hint`` is four characters and the webhook verify token is
        non-secret by design (it already lives in the visible ``extra_json``,
        and both Meta and we must hold it identically for the handshake to
        work at all)."""
        app = self._get_for_provider(provider)
        redirect, webhooks = self._golive_urls(provider)
        progress_row = self._golive_progress_row(provider)
        progress = progress_row._steps() if progress_row else {}
        last_handshake_at = self._golive_handshake_at(provider)

        values = {'oauth_redirect_uri': redirect, 'webhook_urls': webhooks}
        if provider == 'meta':
            values[VERIFY_TOKEN_KEY] = (
                app.get_extra(VERIFY_TOKEN_KEY) if app else False) or False
            for key in GOLIVE_EXTRA_KEYS:
                values[key] = (app.get_extra(key) if app else False) or False

        rows = app._go_live_rows() if app else []
        ctx = {
            'client_id': (app.client_id if app else False) or False,
            'has_secret': bool(app.client_secret_enc) if app else False,
            'preflight_status': (app.preflight_status if app else 'none'),
            'last_handshake_at': last_handshake_at,
            'extras': {key: bool(str(app.get_extra(key) or '').strip())
                       for key in GOLIVE_EXTRA_KEYS} if app else {},
            'all_rows_done': bool(rows) and all(ok for _label, ok in rows),
            'progress': progress,
        }

        channels = self._golive_channels(provider)
        return {
            'provider': provider,
            'app_id': app.id if app else False,
            'client_id': ctx['client_id'],
            'secret_hint': (app.secret_hint if app else False) or False,
            'preflight': {
                'status': ctx['preflight_status'],
                'at': (fields.Datetime.to_string(app.preflight_at)
                       if app and app.preflight_at else False),
                'detail': (app.preflight_detail if app else False) or False,
            },
            'values': values,
            'last_handshake_at': last_handshake_at,
            'progress': progress,
            'channels': channels,
            'platform_ready': {
                channel: bool(CHANNEL_ADAPTERS[channel](
                    self.env, channel).platform_ready())
                for channel in channels},
            'steps': [self._golive_step_payload(step, ctx)
                      for step in self._golive_steps()[provider]],
        }

    def _golive_step_payload(self, step, ctx):
        mark = ctx['progress'].get(step['key']) or {}
        payload = {key: step[key] for key in GOLIVE_STEP_KEYS}
        console = step['console']
        if console and '{app_id}' in console:
            # An un-resolvable console link is worse than none: it 404s in the
            # operator's face and looks like Meta lost their app.
            console = (console.replace('{app_id}', ctx['client_id'])
                       if ctx['client_id'] else False)
        payload['console'] = console
        payload['status'] = self._golive_step_status(step, ctx)
        payload['marked_on'] = mark.get('marked_on') or False
        return payload

    @api.model
    def _golive_step_status(self, step, ctx):
        """``done`` | ``todo`` | ``waiting`` | ``fail``.

        The core rule of the phase: a progress mark can never say ``done`` for
        a step whose artifact is missing. Only where there is nothing for us
        to observe does the mark decide.
        """
        key, verify, kind = step['key'], step['verify'], step['kind']
        marked = bool((ctx['progress'].get(key) or {}).get('marked'))

        if key == 'create_app':
            return 'done' if ctx['client_id'] else 'todo'
        if key in ('store_secret', 'credentials'):
            if ctx['preflight_status'] == 'fail':
                return 'fail'
            if ctx['has_secret'] and (verify != 'preflight'
                                      or ctx['preflight_status'] == 'pass'):
                return 'done'
            return 'todo'
        if key == 'done':
            # The whole point of the last step: it is the platform-app
            # completeness check, said in words. It cannot be hand-marked into
            # existence, because the cards read the same rows.
            return 'done' if ctx['all_rows_done'] else 'todo'
        if verify == 'handshake':
            return 'done' if ctx['last_handshake_at'] else 'todo'
        if key == 'config_ids':
            extras = ctx['extras']
            return ('done' if extras and all(extras.values()) else 'todo')
        if kind == 'wait':
            return 'waiting' if marked else 'todo'
        return 'done' if marked else 'todo'

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------
    @api.model
    def golive_submit(self, provider, step_key, payload=None):
        """Save what a step asks the operator to type.

        Every write goes through the path that already exists for it —
        ``action_set_secret`` for the secret, a read-modify-write MERGE for
        ``extra_json``, ``action_generate_verify_token`` for the token — so
        the encryption, the hint, the audit rows and the refuse-if-exists rule
        are the same ones CC-G shipped. Nothing here is a second door.
        """
        self._require_operator()
        step = self._golive_step(provider, step_key)
        payload = payload or {}
        if not isinstance(payload, dict):
            raise ValidationError(_(
                'The values for a go-live step must be a JSON object.'))

        declared = {spec['name']: spec for spec in step['inputs']}
        cleaned = {}
        for name, raw in payload.items():
            spec = declared.get(name)
            if not spec:
                raise ValidationError(_(
                    '"%s" is not a value this step asks for.', name))
            value = raw.strip() if isinstance(raw, str) else raw
            if not isinstance(value, str) or not re.match(spec['regex'], value):
                raise ValidationError(spec['error'])
            cleaned[name] = value
        if not cleaned:
            raise ValidationError(_('This step has nothing to save.'))

        # Only NOW may a row appear: a rejected paste must leave the database
        # exactly as it found it.
        app = self._get_for_provider(provider)
        if not app:
            app = self.sudo().create({'provider': provider})

        if 'client_id' in cleaned:
            app.write({'client_id': cleaned['client_id']})
        if 'client_secret' in cleaned:
            # The ONLY secret write path in the module (architecture §7.2).
            app.action_set_secret(cleaned['client_secret'])
            if step['verify'] == 'preflight':
                # Never raises on a provider refusal — the outcome is
                # persisted on the row and read back by golive_state().
                app.action_preflight()

        extras = {key: value for key, value in cleaned.items()
                  if key in GOLIVE_EXTRA_KEYS}
        if extras:
            self._golive_merge_extra(app, extras)
            # The first extra-write is the natural place to mint the webhook
            # verify token: the operator is on the app dashboard anyway, and
            # the generator refuses to overwrite one Meta already holds.
            if provider == 'meta' and not str(
                    app.get_extra(VERIFY_TOKEN_KEY) or '').strip():
                app.action_generate_verify_token()

        return self.golive_state()

    @api.model
    def _golive_merge_extra(self, app, values):
        """Read-modify-write on ``extra_json``. MERGE, never replace: losing a
        sibling key dark-cards a channel (channel_platform_app.py:399-403)."""
        try:
            extra = json.loads(app.extra_json or '{}') or {}
        except ValueError:
            raise ValidationError(_('Extra configuration must be valid JSON.'))
        if not isinstance(extra, dict):
            raise ValidationError(_('Extra configuration must be a JSON object.'))
        extra.update(values)
        app.sudo().write({'extra_json': json.dumps(extra, indent=2,
                                                   sort_keys=True)})

    @api.model
    def golive_mark(self, provider, step_key, marked=True):
        """Record that a human finished something we cannot see.

        Refused for every step Health19 proves for itself: letting an operator
        tick "the secret is stored" would put a green step on a screen whose
        channels are still dark, which is the exact lie the readiness model
        exists to prevent.
        """
        self._require_operator()
        step = self._golive_step(provider, step_key)
        if step['kind'] != 'wait' and step['verify'] != 'manual':
            raise UserError(_(
                'Health19 checks this step for itself — it turns green when '
                'the work is really done, and cannot be ticked by hand.'))

        row = self._golive_progress_row(provider, create=True)
        steps = row._steps()
        if marked:
            steps[step_key] = {
                'marked': True,
                'marked_on': fields.Date.to_string(
                    fields.Date.context_today(self)),
            }
        else:
            steps[step_key] = {'marked': False, 'marked_on': False}
        row.write({'steps_json': json.dumps(steps, sort_keys=True)})
        return self.golive_state()
