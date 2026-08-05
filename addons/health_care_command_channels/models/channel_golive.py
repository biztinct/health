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
import hashlib
import json
import logging
import re
import secrets
from datetime import timedelta

import psycopg2

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

# Every provider the Studio drives, in home-screen order. GL-4 added google
# and microsoft: their sign-in runs on Odoo's own mixins rather than on our
# OAuth engine, which changes what the steps SAY and nothing about how they
# are declared — the whole point of the framework GL-1 built.
#
# VoIP24h is deliberately absent and must stay absent: `CallAdapter` declares
# `needs_platform_app: False`, so there is no provider application to create,
# no console paperwork to guide, and a flow would be an invented lie. The
# Studio home carries a static truth card for it instead (GL-4 D4), and
# `_golive_step('call'|'voip24h', …)` raises.
GOLIVE_PROVIDERS = ('meta', 'zalo', 'google', 'microsoft')

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

# ---------------------------------------------------------------------------
# GL-3 — delegation invites
# ---------------------------------------------------------------------------
# How long a link stays usable. Long enough for somebody to get round to it,
# short enough that a forwarded mail in an archive is not a standing key.
INVITE_TTL_DAYS = 14

# The public page's path. ONE definition: the controller's route and the URL
# the email carries must be the same string or the link 404s.
INVITE_PATH = '/channels/golive/%s'

# The ONLY copy values a public page may render. Anything else a future step
# declares — a client id, an account number — is simply not shown to a
# stranger, whatever the declaration says (D3, and it fails closed).
INVITE_COPY_KEYS = ('oauth_redirect_uri', 'webhook_urls', VERIFY_TOKEN_KEY)

# Brand names, deliberately untranslated and deliberately NOT the Selection
# label ("Meta (WhatsApp + Messenger)" is a picker label, not a sentence).
# Mirrors PROVIDER_NAME in static/src/golive/golive_studio.js.
GOLIVE_PROVIDER_NAMES = {'meta': 'Meta', 'zalo': 'Zalo',
                         'google': 'Google', 'microsoft': 'Microsoft'}


def mask_email(email):
    """``john@example.com`` -> ``j***@example.com``.

    Enough for an operator to recognise the address they typed, and the most
    that may reach an append-only audit row that a whole tenant can read.
    """
    email = (email or '').strip()
    if '@' not in email:
        return '***'
    local, _sep, domain = email.partition('@')
    return '%s***@%s' % (local[:1], domain)


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


class ChannelGoliveInvite(models.Model):
    """GL-3 — one do-step, handed to the person who has the provider console.

    The human who can open Meta's App Dashboard is very often not the human who
    has a Health19 login. This row is how a single step travels to them without
    an account, and everything about it is shaped by the fact that its URL is
    reachable by anyone who has the link:

    * **The token is never stored.** Only ``sha256(token)`` reaches a column.
      The plaintext exists inside ``golive_invite_send`` for the length of one
      call — long enough to build the URL and put it in the email body — and is
      in no return value, no audit row and no log line. A stolen database backup
      contains no usable link.
    * **Revoked, never erased** (``perm_unlink`` 0 on the ACL). A link that was
      handed out is evidence; withdrawing it is a flag, not a delete.
    * **No ``tracking=True`` on anything** (Z1, the whole platform plane's rule):
      a tracked field copies its value into ``mail.tracking.value``, which is a
      leak path that bypasses field groups entirely.
    """
    _name = 'channel.golive.invite'
    _description = 'Go-Live Studio Invite'
    _order = 'id desc'

    provider = fields.Selection(PROVIDERS, required=True, index=True)
    # ONE step per invite in v1: a link that carries three steps is a link that
    # is right for none of them a week later.
    step_key = fields.Char(required=True)
    email = fields.Char(required=True)
    token_hash = fields.Char(
        required=True, index=True,
        help='SHA-256 hex digest of the link token. The token itself is never '
             'stored, logged or audited — it exists only in the email.')
    invited_by_id = fields.Many2one(
        'res.users', required=True, ondelete='restrict',
        help='Whose language and company the public page speaks in.')
    expires_at = fields.Datetime(required=True)
    revoked = fields.Boolean(default=False)
    view_count = fields.Integer(default=0)
    last_viewed_at = fields.Datetime()
    active = fields.Boolean(default=True)

    # ------------------------------------------------------------------
    # Token handling — the whole security posture of the phase
    # ------------------------------------------------------------------
    @staticmethod
    def _hash_token(token):
        return hashlib.sha256((token or '').encode('utf-8')).hexdigest()

    @api.model
    def _mint(self, provider, step_key, email, user):
        """Create an invite and return ``(record, plaintext token)``.

        The ONLY place a plaintext token exists. The caller must put it in the
        email and drop it — it must not be returned to an RPC caller, written
        to a field, or logged.
        """
        token = secrets.token_urlsafe(32)
        invite = self.sudo().create({
            'provider': provider,
            'step_key': step_key,
            'email': email,
            'token_hash': self._hash_token(token),
            'invited_by_id': user.id,
            'expires_at': (fields.Datetime.now()
                           + timedelta(days=INVITE_TTL_DAYS)),
        })
        return invite, token

    @api.model
    def _resolve(self, token):
        """The ONE lookup, by digest, in SQL.

        Nothing is compared in Python and nothing is echoed: an unknown token
        and a revoked one leave the same trace here (none), which is what makes
        the controller's single dead-end page honest.
        """
        token = (token or '').strip()
        # A length cap before hashing: the route's own path segment is already
        # bounded by the server, but a 10 MB "token" should cost us one branch,
        # not a digest.
        if not token or len(token) > 256:
            return self.browse()
        return self.sudo().search(
            [('token_hash', '=', self._hash_token(token))], limit=1)

    def _is_live(self):
        self.ensure_one()
        return bool(self.active and not self.revoked and self.expires_at
                    and self.expires_at > fields.Datetime.now())

    def _register_view(self):
        """The ONLY write the public route may cause on this row.

        Note what it does NOT do: it never touches ``expires_at``. A link that
        renewed itself every time somebody opened it would never expire at all.
        """
        self.ensure_one()
        self.sudo().write({
            'view_count': self.view_count + 1,
            'last_viewed_at': fields.Datetime.now(),
        })

    def _payload(self):
        """What the Studio is told about an invite. No token material, and
        nothing about the recipient beyond the address the operator typed."""
        self.ensure_one()
        return {
            'id': self.id,
            'provider': self.provider,
            'step_key': self.step_key,
            'email': self.email or '',
            'sent_on': fields.Datetime.to_string(self.create_date),
            'expires_at': fields.Datetime.to_string(self.expires_at),
            'revoked': bool(self.revoked),
            'expired': bool(self.expires_at
                            and self.expires_at <= fields.Datetime.now()),
            'view_count': self.view_count or 0,
            'last_viewed_at': (fields.Datetime.to_string(self.last_viewed_at)
                               if self.last_viewed_at else False),
        }


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
            # ==========================================================
            # GL-4 — Google (Gmail). Five steps, one channel: email.
            #
            # Three facts shape every declaration below, and each one is a
            # trap somebody would otherwise fall into:
            #
            # * **`store_secret` verifies `manual`, never `preflight`.**
            #   `action_preflight` is Meta-only; every other provider answers
            #   `unverifiable` (channel_platform_app.py:427). The status branch
            #   only accepts a preflight-declared step when the status is
            #   `pass`, so declaring `preflight` here would strand the step at
            #   `todo` forever. `manual` is also the honest reading: Google
            #   publishes no credentials-only check, and these credentials are
            #   proven at the first real mailbox sign-in.
            # * **The console links are STATIC.** Google's console does not key
            #   on the OAuth client id in any stable public URL, so an
            #   `{app_id}`-templated link would 404 in the operator's face.
            # * **No `webhook_urls` in `copy_values`.** Email has no webhook at
            #   all — mail arrives by IMAP poll — so `WEBHOOK_PATHS['google']`
            #   is `[]` and the value would render as an empty block rather
            #   than as an explanation.
            # ==========================================================
            'google': [
                {
                    'key': 'create_app',
                    'kind': 'do',
                    'title': _('Create the sign-in client'),
                    'body': _(
                        'Open the Google Cloud Console and create a project, '
                        'or pick the one your company already uses. Turn on '
                        'the Gmail API for that project. Then open '
                        'Credentials, choose Create credentials, and pick '
                        'OAuth client ID of type Web application, named after '
                        'your company. Google shows a Client ID the moment it '
                        'is created — copy it here.'),
                    'console': ('https://console.cloud.google.com/apis/'
                                'credentials'),
                    'console_label': _('Open Google Cloud credentials'),
                    'copy_values': [],
                    'inputs': [{
                        'name': 'client_id',
                        'label': _('Client ID'),
                        'secret': False,
                        'regex': r'^\S+\.apps\.googleusercontent\.com$',
                        'error': _('A Google client ID ends in '
                                   '.apps.googleusercontent.com — copy it '
                                   'from the Credentials page.'),
                    }],
                    'verify': 'manual',
                    'est': _('about 15 minutes'),
                },
                {
                    'key': 'store_secret',
                    'kind': 'do',
                    'title': _('Store the client secret'),
                    'body': _(
                        "The client's own page shows a Client secret beside "
                        'the Client ID. Paste it here; we encrypt it and '
                        'never show it again. Google gives us no harmless way '
                        'to test these credentials from here, so this step '
                        'turns green as soon as the secret is stored — they '
                        'are really proven the first time a clinic connects '
                        'its mailbox.'),
                    'console': ('https://console.cloud.google.com/apis/'
                                'credentials'),
                    'console_label': _('Open Google Cloud credentials'),
                    'copy_values': [],
                    'inputs': [{
                        'name': 'client_secret',
                        'label': _('Client secret'),
                        'secret': True,
                        'regex': r'^\S{10,128}$',
                        'error': _('The client secret is one run of '
                                   'characters with no spaces, shown on the '
                                   "OAuth client's own page."),
                    }],
                    'verify': 'manual',
                    'est': _('about 5 minutes'),
                },
                {
                    'key': 'redirect_uri',
                    'kind': 'do',
                    'title': _('Tell Google where to come back'),
                    'body': _(
                        'Open the OAuth client and add the address below to '
                        'Authorised redirect URIs. Gmail sign-in runs on '
                        "Odoo's own Gmail integration, so this is its "
                        'address, and Google refuses the sign-in unless it '
                        'matches exactly, character for character.'),
                    'console': ('https://console.cloud.google.com/apis/'
                                'credentials'),
                    'console_label': _('Open Google Cloud credentials'),
                    'copy_values': ['oauth_redirect_uri'],
                    'inputs': [],
                    'verify': 'manual',
                    'est': _('about 5 minutes'),
                },
                {
                    'key': 'consent_screen',
                    'kind': 'wait',
                    'title': _('Publish the consent screen'),
                    'body': _(
                        'A consent screen left in testing expires every '
                        "mailbox's access after 7 days, which reaches the "
                        'clinics as random sign-outs nobody can explain. '
                        'Publish it. Google may come back with verification '
                        'questions about the Gmail permissions, and answering '
                        'them can take days. Mark this step once you have '
                        'submitted it, so you can see where you are.'),
                    'console': ('https://console.cloud.google.com/apis/'
                                'credentials/consent'),
                    'console_label': _('Open the consent screen'),
                    'copy_values': [],
                    'inputs': [],
                    'verify': 'manual',
                    'est': _('a few days if Google asks questions'),
                },
                {
                    'key': 'done',
                    'kind': 'check',
                    'title': _('Gmail is ready to offer'),
                    'body': _(
                        'Email through Gmail is ready to offer. Each clinic '
                        'connects its own mailbox from the Channel Center — '
                        'nothing further is needed from you. You only need '
                        'ONE of Google or Microsoft for the Email card to be '
                        'available; doing both simply lets a clinic choose. '
                        "The sign-in itself runs on Odoo's Gmail integration "
                        '(the google_gmail addon), which has to be installed '
                        'on this deployment for a mailbox to connect. This '
                        'step reads the credentials we hold; whether the '
                        "redirect address really reached Google's console is "
                        "something we cannot see, so if a clinic's sign-in is "
                        'refused, that is the first place to look.'),
                    'console': False,
                    'console_label': False,
                    'copy_values': [],
                    'inputs': [],
                    'verify': 'manual',
                    'est': False,
                },
            ],
            # ==========================================================
            # GL-4 — Microsoft (Outlook / Microsoft 365). Same three rules as
            # google above, plus one of its own: the Entra console links are
            # static because a deep link into an app registration needs the
            # OBJECT id, which is not the Application (client) id we hold —
            # a templated link would 404.
            # ==========================================================
            'microsoft': [
                {
                    'key': 'create_app',
                    'kind': 'do',
                    'title': _('Register the application'),
                    'body': _(
                        'In the Microsoft Entra admin center open App '
                        'registrations, then New registration. Name it after '
                        'your company. For supported account types choose '
                        'accounts in any organisational directory and '
                        'personal Microsoft accounts, unless every clinic '
                        "mailbox lives in your own tenant. The app's Overview "
                        'page then shows an Application (client) ID — copy it '
                        'here.'),
                    'console': 'https://entra.microsoft.com',
                    'console_label': _('Open the Microsoft Entra admin center'),
                    'copy_values': [],
                    'inputs': [{
                        'name': 'client_id',
                        'label': _('Application (client) ID'),
                        'secret': False,
                        'regex': (r'^[0-9a-fA-F]{8}-([0-9a-fA-F]{4}-){3}'
                                  r'[0-9a-fA-F]{12}$'),
                        'error': _('The Application (client) ID is a UUID '
                                   'like 12345678-abcd-… — copy it from the '
                                   "app's Overview page."),
                    }],
                    'verify': 'manual',
                    'est': _('about 10 minutes'),
                },
                {
                    'key': 'redirect_uri',
                    'kind': 'do',
                    'title': _('Tell Microsoft where to come back'),
                    'body': _(
                        'Open Authentication, then Add a platform, and choose '
                        'Web. Paste the address below as the redirect URI. It '
                        "belongs to Odoo's own Outlook integration, and "
                        'Microsoft refuses the sign-in unless it matches '
                        'exactly, character for character.'),
                    'console': 'https://entra.microsoft.com',
                    'console_label': _('Open the Microsoft Entra admin center'),
                    'copy_values': ['oauth_redirect_uri'],
                    'inputs': [],
                    'verify': 'manual',
                    'est': _('about 5 minutes'),
                },
                {
                    'key': 'permissions',
                    'kind': 'do',
                    'title': _('Grant the mailbox permissions'),
                    'body': _(
                        'Open API permissions, then Add a permission, then '
                        'Microsoft Graph, and choose Delegated. Add '
                        'Mail.Send, Mail.ReadWrite, IMAP.AccessAsUser.All and '
                        'offline_access. Then press Grant admin consent, or '
                        'every clinic is asked to approve them one by one and '
                        'most will not be allowed to.'),
                    'console': 'https://entra.microsoft.com',
                    'console_label': _('Open the Microsoft Entra admin center'),
                    'copy_values': [],
                    'inputs': [],
                    'verify': 'manual',
                    'est': _('about 10 minutes'),
                },
                {
                    'key': 'store_secret',
                    'kind': 'do',
                    'title': _('Create and store a client secret'),
                    'body': _(
                        'Open Certificates & secrets, then New client secret. '
                        'Copy the Value column, NOT the Secret ID — that is '
                        'the classic mistake, and the Value is shown only '
                        'once. Paste it here; we encrypt it and never show it '
                        'again. Entra secrets expire after 24 months at the '
                        'most, so write the expiry date into the note on the '
                        'platform application while you have it.'),
                    'console': 'https://entra.microsoft.com',
                    'console_label': _('Open the Microsoft Entra admin center'),
                    'copy_values': [],
                    'inputs': [{
                        'name': 'client_secret',
                        'label': _('Client secret value'),
                        'secret': True,
                        'regex': r'^\S{10,128}$',
                        'error': _('The secret Value is one run of characters '
                                   'with no spaces. If what you pasted looks '
                                   'like a UUID you copied the Secret ID '
                                   'instead.'),
                    }],
                    'verify': 'manual',
                    'est': _('about 5 minutes'),
                },
                {
                    'key': 'done',
                    'kind': 'check',
                    'title': _('Outlook is ready to offer'),
                    'body': _(
                        'Email through Microsoft 365 is ready to offer. Each '
                        'clinic connects its own mailbox from the Channel '
                        'Center — nothing further is needed from you. You '
                        'only need ONE of Google or Microsoft for the Email '
                        'card to be available; doing both simply lets a '
                        'clinic choose. The sign-in itself runs on Odoo\'s '
                        'Outlook integration (the microsoft_outlook addon), '
                        'which has to be installed on this deployment for a '
                        'mailbox to connect. This step reads the credentials '
                        'we hold; whether the redirect address and the four '
                        'permissions really reached Entra is something we '
                        "cannot see, so if a clinic's sign-in is refused, "
                        'that is the first place to look.'),
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
            # GL-3, additive-only: the GL-1/GL-2 payload above is untouched.
            'invites': self._golive_invites(provider),
        }

    @api.model
    def _golive_invites(self, provider):
        """The invitations worth showing for a provider.

        Every LIVE one (there is at most one per step — a re-send rotates), plus
        the newest revoked/expired one per step so "you already sent this to
        somebody, and it is dead" is visible instead of silently vanishing.
        Older dead ones stay in the table as evidence and out of the screen.
        """
        rows = self.env['channel.golive.invite'].sudo().search(
            [('provider', '=', provider)])
        payloads, dead_seen = [], set()
        for invite in rows:                      # _order = 'id desc'
            payload = invite._payload()
            if payload['revoked'] or payload['expired']:
                if payload['step_key'] in dead_seen:
                    continue
                dead_seen.add(payload['step_key'])
            payloads.append(payload)
        return payloads

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

    # ==================================================================
    # GL-3 — delegation
    # ==================================================================
    @api.model
    def _golive_validate_email(self, email):
        """A plain ``@`` check, deliberately (D1).

        An RFC-strict regex refuses far more real addresses than it catches
        typos, and the person who notices the address is wrong is the operator
        reading it back off the card a second later — not a regex.
        """
        email = (email or '').strip()
        local, _sep, domain = email.partition('@')
        if (not email or len(email) > 254 or email.count('@') != 1
                or not local or not domain
                or any(char.isspace() for char in email)
                or '.' not in domain
                or domain.startswith('.') or domain.endswith('.')):
            raise ValidationError(_(
                'That does not look like an email address. Type the whole '
                'address of the person who has access to the console.'))
        return email

    @api.model
    def golive_invite_send(self, provider, step_key, email):
        """Send ONE do-step to the person who has the provider console.

        A re-send is a ROTATION, not a second key: any live invitation for the
        same (provider, step) is revoked first, so at every moment exactly one
        link can open a given step. The plaintext token exists only between
        ``_mint`` and the rendered email body — it is not returned to the
        caller, and the caller could not be given it safely anyway (an RPC
        response lands in a browser's memory, its devtools and its logs).
        """
        self._require_operator()
        step = self._golive_step(provider, step_key)
        if step['kind'] != 'do':
            raise ValidationError(_(
                'Only a step somebody can actually carry out in the provider '
                'console can be sent on. This one is a wait for the provider '
                'to finish a review of their own.'))
        email = self._golive_validate_email(email)

        Invite = self.env['channel.golive.invite'].sudo()
        rotated = Invite.search([('provider', '=', provider),
                                 ('step_key', '=', step_key),
                                 ('revoked', '=', False)])
        if rotated:
            rotated.write({'revoked': True})

        invite, token = Invite._mint(provider, step_key, email, self.env.user)
        url = '%s%s' % (self._base_url(), INVITE_PATH % token)
        # Raises (and takes the invite down with it) when the mail cannot go.
        self._golive_invite_mail(invite, step, url)

        self.env['care.channel.audit']._log(
            'golive_invite_sent',
            detail='%s/%s to %s%s' % (
                provider, step_key, mask_email(email),
                ' (rotated %s)' % len(rotated) if rotated else ''))
        return self.golive_state()

    @api.model
    def golive_invite_revoke(self, invite_id):
        self._require_operator()
        invite = self.env['channel.golive.invite'].sudo().browse(
            int(invite_id or 0)).exists()
        if not invite:
            raise ValidationError(_('That invitation no longer exists.'))
        if not invite.revoked:
            invite.write({'revoked': True})
            self.env['care.channel.audit']._log(
                'golive_invite_revoked',
                detail='%s/%s invite %s to %s' % (
                    invite.provider, invite.step_key, invite.id,
                    mask_email(invite.email)))
        return self.golive_state()

    # ------------------------------------------------------------------
    # The email (D4)
    # ------------------------------------------------------------------
    @api.model
    def _golive_invite_mail(self, invite, step, url):
        """Render and send the invitation, or refuse the whole operation.

        NO ``mail.template`` record: Odoo renders every template's subject and
        body AT INSTALL against a bare sample record, and one that cannot render
        blocks the module's install (ledger §5.14 — health_messaging paid for
        it). A QWeb view rendered here carries no such contract.

        The token lives ONLY in this body. So a send that fails is not a
        half-success to paper over: the invitation is revoked on the spot and
        the operator is told to fix the outgoing mail server, because a link
        nobody received is a link that can only ever be found by a guesser.
        """
        company = invite.invited_by_id.sudo().company_id or self.env.company
        provider_name = GOLIVE_PROVIDER_NAMES.get(invite.provider,
                                                  invite.provider)
        body = self.env['ir.qweb']._render(
            'health_care_command_channels.golive_invite_mail', {
                'url': url,
                'step_title': step['title'],
                'step_body': step['body'],
                'provider_name': provider_name,
                'sender_name': self.env.user.name,
                'company_name': company.name,
                'expires_on': fields.Date.to_string(
                    fields.Datetime.context_timestamp(
                        self, invite.expires_at).date()),
            })
        values = {
            'subject': _(
                '%(company)s: one step to finish in the %(provider)s console',
                company=company.name, provider=provider_name),
            'body_html': body,
            'email_to': invite.email,
            # The token is in this body. It has no business outliving delivery
            # in a table half the database can read.
            'auto_delete': True,
        }
        email_from = company.email or self.env.user.email_formatted
        if email_from:
            values['email_from'] = email_from
        mail = self.env['mail.mail'].sudo().create(values)
        try:
            mail.send(raise_exception=True)
        except psycopg2.Error:
            # Never swallow the read-only-cursor retry signal (ledger §5.38).
            raise
        except Exception as exc:  # noqa: BLE001 — every send failure is one
            # The CLASS, not the message. `redact()` strips a URL's query
            # string, and this URL has none: its token is in the PATH, so a
            # provider error body that echoed it back would go straight into
            # the log. Odoo's own mail_mail logs the delivery failure anyway.
            _logger.warning('Go-Live invite mail failed (%s)',
                            type(exc).__name__)
            invite.sudo().write({'revoked': True})
            raise UserError(_(
                'The invitation could not be sent, so its link has been '
                'revoked — nobody received it and nobody can use it. Check '
                'the outgoing mail server, then send it again.'))

    # ------------------------------------------------------------------
    # The public page's values (D3) — read-only, and it renders nothing else
    # ------------------------------------------------------------------
    @api.model
    def _golive_invite_values(self, invite):
        """Everything the public page shows, or ``False`` for a dead end.

        Called from a public route, so it reads and it never writes. Note the
        two independent refusals folded in here, both of which the controller
        turns into the SAME page as an unknown token:

        * the step is no longer declared, or is no longer a ``do`` step;
        * a platform application EXISTS for this provider but is archived —
          the operator took the go-live down, so the links it handed out die
          with it. A provider with no row at all is not a refusal: that is a
          go-live which has not started, and step one is what the link is for.
        """
        provider = invite.provider
        try:
            step = self._golive_step(provider, invite.step_key)
        except ValidationError:
            return False
        if step['kind'] != 'do':
            return False

        app = self._get_for_provider(provider)
        if not app and self.sudo().with_context(active_test=False).search_count(
                [('provider', '=', provider)]):
            return False

        redirect, webhooks = self._golive_urls(provider)
        client_id = (app.client_id if app else '') or ''
        console = step['console']
        if console and '{app_id}' in console:
            console = (console.replace('{app_id}', client_id)
                       if client_id else False)

        blocks = []
        for key in step['copy_values'] or []:
            if key not in INVITE_COPY_KEYS:
                # Fails CLOSED: a future step may declare a value we have not
                # decided is safe for a stranger's screen. It simply is not
                # rendered until somebody decides.
                continue
            if key == 'webhook_urls':
                for line in (webhooks or '').split('\n'):
                    line = line.strip()
                    if not line:
                        continue
                    label, _sep, value = line.partition(': ')
                    blocks.append({
                        'label': (_('Webhook address — %s', label) if value
                                  else _('Webhook address')),
                        'value': value or line,
                        'note': False,
                    })
            elif key == 'oauth_redirect_uri':
                blocks.append({'label': _('Sign-in redirect address'),
                               'value': redirect, 'note': False})
            else:                                  # VERIFY_TOKEN_KEY
                token = str((app.get_extra(VERIFY_TOKEN_KEY)
                             if app else '') or '').strip()
                blocks.append({
                    'label': _('Webhook verify token'),
                    'value': token,
                    # A public route must NEVER write configuration. If the
                    # token does not exist yet, say so — minting one here would
                    # let a stranger change what Meta must hold.
                    'note': False if token else _(
                        'Not created yet — ask the sender to create it in the '
                        'Studio first.'),
                })

        return {
            'provider_name': GOLIVE_PROVIDER_NAMES.get(provider, provider),
            'company_name': (invite.invited_by_id.sudo().company_id.name
                             or self.env.company.name),
            'step_title': step['title'],
            'step_body': step['body'],
            'console': console or False,
            'console_label': step['console_label'] or False,
            'blocks': blocks,
            'expires_on': fields.Date.to_string(
                fields.Datetime.context_timestamp(
                    self, invite.expires_at).date()),
        }
