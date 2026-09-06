# -*- coding: utf-8 -*-
"""Plane 1 — per-deployment provider applications (architecture §5.1).

One row per provider per database, owned exclusively by the platform operator
(``base.group_system``). Tenants never see, enter or receive these values: the
Meta/Zalo/Google/Microsoft app secret is what makes every tenant authorization
possible, so it is the single most sensitive credential in the system.

Design rules paid for elsewhere:

* **No ``tracking=True`` on anything** — Z1 in the health_zalo defect list is
  exactly this: a tracked ``app_secret`` copies plaintext secrets into
  ``mail.tracking.value``, a leak path that bypasses field groups entirely.
* The secret is **never a form field**. It is written by
  :meth:`action_set_secret` from a TransientModel wizard, and read back only by
  server-side adapter code through ``_get_secret()``.
* ``_sql_constraints`` are not materialised on Odoo 19 (ledger §5.1), so the
  one-active-app-per-provider contract is a partial unique index created in
  ``init()`` — plus a pre-check in ``create``/``write`` so user input raises a
  clean ValidationError instead of poisoning the transaction with an
  IntegrityError (ledger §5.3).
"""
import json
import logging
import secrets

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from ..services import channel_crypto
from ..services.adapters import (
    CHANNEL_ADAPTERS, META_CALLBACK_PATH, OAUTH_REDIRECT_BASE_PARAM,
    ZALO_CALLBACK_PATH,
    ZALO_WEBHOOK_PATH, ChannelSendError, meta_app_identity,
)
from ..services.redact import redact
from ..services.webhook_verify import VERIFY_TOKEN_KEY

_logger = logging.getLogger(__name__)

PROVIDERS = [
    ('meta', 'Meta (WhatsApp + Messenger)'),
    ('zalo', 'Zalo'),
    ('google', 'Google'),
    ('microsoft', 'Microsoft'),
]

# ---------------------------------------------------------------------------
# CC-G — the go-live console's computed values
# ---------------------------------------------------------------------------
# Where each provider's sign-in comes back to. meta and zalo run on THIS
# module's callback (controllers/oauth.py:46); google and microsoft are driven
# by Odoo's own mixins, which own their redirect URIs
# (google_gmail/controllers/main.py:20, microsoft_outlook/controllers/main.py:19)
# — printing ours for them would be a paste Google refuses at the first
# sign-in, which is the exact failure this tab exists to prevent (deviation D1).
OAUTH_REDIRECT_PATHS = {
    'meta': META_CALLBACK_PATH,
    'zalo': ZALO_CALLBACK_PATH,
    'google': '/google_gmail/confirm',
    'microsoft': '/microsoft_outlook/confirm',
}

# Inbound webhook URLs the operator pastes into the provider's dashboard.
# Meta's route is `/care_channels/meta/<channel>/webhook`
# (controllers/meta.py:44) and both products are subscribed separately; Zalo
# allows exactly ONE URL per app (architecture §13). Email has none at all —
# mail arrives by IMAP poll — and saying so is more useful than an empty box.
META_WEBHOOK_PATH = '/care_channels/meta/%s/webhook'
WEBHOOK_PATHS = {
    'meta': [('WhatsApp', META_WEBHOOK_PATH % 'whatsapp'),
             ('Messenger', META_WEBHOOK_PATH % 'fb')],
    'zalo': [('Zalo OA', ZALO_WEBHOOK_PATH)],
    'google': [],
    'microsoft': [],
}

# The provider's own console — every step behind these links is human
# paperwork (operator checklist §12), and none of it is automatable.
PROVIDER_CONSOLE = {
    'meta': ('https://developers.facebook.com/apps',
             'Meta App Dashboard'),
    'zalo': ('https://developers.zalo.me', 'Zalo Developers'),
    'google': ('https://console.cloud.google.com/apis/credentials',
               'Google Cloud Console'),
    'microsoft': ('https://entra.microsoft.com', 'Microsoft Entra admin center'),
}

# What a human must finish OUTSIDE Health19 before the credentials on this row
# can do anything. Deliberately terse: the authority is the provider's own
# console, this is only the reminder of what to look for.
#
# GL-1 emptied meta and zalo out of here; GL-4 emptied google and microsoft.
# Every provider's paperwork is now declared exactly ONCE, in structured and
# translatable form, by ``_golive_steps()`` (models/channel_golive.py) — which
# the Go-Live Studio drives and which this checklist reads too. Two lists of
# the same paperwork is how they drift apart, and these entries were already
# a shorter, untranslatable copy of the declarations that replaced them.
#
# The constant and its fallback at ``_render_go_live_checklist`` STAY. A future
# provider (GL-5) may want a checklist before it wants a guided flow, and the
# mechanism costs one dict lookup; deleting it would make that phase reinvent
# it. Empty is the honest state, not a dead branch.
PROVIDER_EXTERNAL_STEPS = {}

# Odoo's own addon behind each email provider. Model presence is the honest
# test that it is installed (adapters.EmailAdapter._addon_installed).
EMAIL_ADDON_MODEL = {'google': 'google.gmail.mixin',
                     'microsoft': 'microsoft.outlook.mixin'}

PREFLIGHT_UNVERIFIABLE = (
    'No harmless server-side check exists for this provider — the credentials '
    'are proven on the first real sign-in.')


class ChannelPlatformApp(models.Model):
    _name = 'channel.platform.app'
    _description = 'Channel Platform Application'
    _order = 'provider'

    provider = fields.Selection(PROVIDERS, required=True, index=True)
    client_id = fields.Char(string='Client / App ID')
    client_secret_enc = fields.Text(
        string='Client Secret (encrypted)', groups='base.group_system',
        help='AES-256-GCM token. Written only by action_set_secret, read only '
             'by server-side adapter code.')
    secret_hint = fields.Char(
        string='Secret', readonly=True,
        help='Last 4 characters only — enough to tell two secrets apart, '
             'useless on its own.')
    has_secret = fields.Boolean(
        compute='_compute_has_secret', string='Secret stored')
    extra_json = fields.Text(
        string='Extra configuration (JSON)',
        help='Provider-specific ids that are NOT secrets: Embedded Signup / '
             'Login-for-Business config ids, webhook verify token name, etc.')
    environment_note = fields.Char(
        help='Free note for the platform operator, e.g. "dev app — 10 tenant cap".')
    active = fields.Boolean(default=True)

    # ------------------------------------------------------------------
    # CC-G — the go-live console. Computed (never stored): every value is
    # derived from `web.base.url`, the adapter declarations and this row, and
    # a stored copy would go stale the day the deployment address changes.
    # No `tracking=True` here either (Z1) — the rule covers the whole model.
    # ------------------------------------------------------------------
    oauth_redirect_uri = fields.Char(
        string='Redirect URI', compute='_compute_go_live_urls',
        help='Paste this into the provider application as the allowed OAuth '
             'redirect / callback URI.')
    webhook_urls = fields.Text(
        string='Webhook URLs', compute='_compute_go_live_urls',
        help='The inbound URLs this deployment answers on for this provider.')
    go_live_checklist = fields.Html(
        string='Go-live checklist', compute='_compute_go_live_checklist',
        sanitize=False,
        help='What is still missing before the channels this provider serves '
             'can be offered to a tenant.')

    preflight_status = fields.Selection(
        [('none', 'Not checked'),
         ('pass', 'Passed'),
         ('fail', 'Failed'),
         ('unverifiable', 'Proven on first sign-in')],
        string='Preflight', default='none', required=True, readonly=True)
    preflight_at = fields.Datetime(string='Checked on', readonly=True)
    preflight_detail = fields.Char(
        string='Preflight detail', readonly=True,
        help='Redacted outcome of the last check. Never a credential.')

    # ------------------------------------------------------------------
    # DB constraints
    # ------------------------------------------------------------------
    def init(self):
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS channel_platform_app_provider_uniq
            ON channel_platform_app (provider) WHERE active
        """)

    @api.depends('client_secret_enc')
    def _compute_has_secret(self):
        # Read through sudo(): the source field is group-restricted, and the
        # batched fetch would otherwise raise for a non-system reader.
        for rec in self:
            rec.has_secret = bool(rec.sudo().client_secret_enc)

    # ------------------------------------------------------------------
    # Uniqueness pre-check (ledger §5.3 — before super(), never after)
    # ------------------------------------------------------------------
    @api.model
    def _check_provider_unique(self, provider, active, exclude_id=None):
        if not provider or not active:
            return
        domain = [('provider', '=', provider), ('active', '=', True)]
        if exclude_id:
            domain.append(('id', '!=', exclude_id))
        if self.sudo().search_count(domain):
            raise ValidationError(_(
                'An active platform application already exists for this '
                'provider. Archive it before creating another.'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._check_provider_unique(
                vals.get('provider'), vals.get('active', True))
        return super().create(vals_list)

    def write(self, vals):
        if 'provider' in vals or 'active' in vals:
            for rec in self:
                self._check_provider_unique(
                    vals.get('provider', rec.provider),
                    vals.get('active', rec.active),
                    exclude_id=rec.id)
        if 'extra_json' in vals and vals['extra_json']:
            self._validate_extra_json(vals['extra_json'])
        return super().write(vals)

    @api.model
    def _validate_extra_json(self, raw):
        try:
            parsed = json.loads(raw)
        except ValueError:
            raise ValidationError(_('Extra configuration must be valid JSON.'))
        if not isinstance(parsed, dict):
            raise ValidationError(_('Extra configuration must be a JSON object.'))

    def get_extra(self, key, default=None):
        """Read one non-secret provider config value from ``extra_json``."""
        self.ensure_one()
        try:
            return (json.loads(self.extra_json or '{}') or {}).get(key, default)
        except ValueError:
            return default

    # ==================================================================
    # CC-G §G2 — the go-live console
    # ==================================================================
    @api.model
    def _base_url(self):
        return (self.env['ir.config_parameter'].sudo().get_param('web.base.url')
                or '').strip().rstrip('/')

    @api.model
    def _redirect_base(self, provider):
        """The address a completed sign-in comes back to, for one provider.

        Meta only: on a platform running one system per customer the Meta
        sign-in returns to the PLATFORM's single address, which then sends the
        browser home (R1). The parameter is written into a customer system by
        the platform; where it is unset — the platform itself, and any
        single-system deployment — this is this system's own address, exactly
        as before. Every other provider is unaffected.
        """
        if provider == 'meta':
            base = (self.env['ir.config_parameter'].sudo()
                    .get_param(OAUTH_REDIRECT_BASE_PARAM) or '').strip().rstrip('/')
            if base:
                return base
        return self._base_url()

    def _adapter_requirements(self):
        """What the adapters that USE this provider demand of this row.

        Returns ``(channels, extra_keys)`` — the declaration is read from the
        registry rather than restated here, so a channel that starts requiring
        a new ``extra_json`` key shows up on this checklist automatically.
        """
        self.ensure_one()
        channels, keys = [], []
        for channel in sorted(CHANNEL_ADAPTERS):
            caps = CHANNEL_ADAPTERS[channel](
                self.env, channel).authorization_capabilities()
            if self.provider not in (caps.get('platform_providers') or ()):
                continue
            channels.append(channel)
            for key in caps.get('required_platform_keys') or ():
                if key not in keys:
                    keys.append(key)
        return channels, keys

    @api.depends('provider')
    def _compute_go_live_urls(self):
        base = self._base_url()
        for rec in self:
            path = OAUTH_REDIRECT_PATHS.get(rec.provider or '')
            redirect_base = self._redirect_base(rec.provider)
            rec.oauth_redirect_uri = (
                '%s%s' % (redirect_base, path) if path else '')
            hooks = WEBHOOK_PATHS.get(rec.provider or '', [])
            if hooks:
                rec.webhook_urls = '\n'.join(
                    '%s: %s%s' % (label, base, path) for label, path in hooks)
            else:
                # An empty box reads as "not configured yet"; the truth is
                # that this provider has no webhook at all.
                rec.webhook_urls = _(
                    'No webhook — mail arrives by IMAP poll.')

    def _go_live_rows(self):
        """[(label, done)] — every prerequisite this row can satisfy itself."""
        self.ensure_one()
        _channels, keys = self._adapter_requirements()
        rows = [
            (_('Application (client) ID entered'), bool(self.client_id)),
            (_('Client secret stored'), bool(self.sudo().client_secret_enc)),
        ]
        for key in keys:
            rows.append((
                _('Extra configuration: %s', key),
                bool(str(self.get_extra(key) or '').strip())))
        addon_model = EMAIL_ADDON_MODEL.get(self.provider)
        if addon_model:
            rows.append((
                _('Odoo mail addon installed (%s)', addon_model),
                addon_model in self.env))
        return rows

    @api.depends('provider', 'client_id', 'client_secret_enc', 'extra_json')
    def _compute_go_live_checklist(self):
        for rec in self:
            rec.go_live_checklist = rec._render_go_live_checklist()

    def _render_go_live_checklist(self):
        """The checklist as Html.

        Flat mono colours, no icons and no emoji (conventions §4): a badge
        with a word in it says pass/todo in every theme and needs no asset.
        Every interpolated value goes through ``Markup(...) % value``, which
        escapes it — a provider id pasted with an angle bracket must not
        become markup (ledger §5.20).
        """
        self.ensure_one()
        if not self.provider:
            return False
        channels, _keys = self._adapter_requirements()
        rows = self._go_live_rows()
        done = Markup('<span class="badge text-bg-success">%s</span>') % _('Done')
        todo = Markup('<span class="badge text-bg-secondary">%s</span>') % _('To do')
        body = Markup('').join(
            Markup('<tr><td class="pe-3">%s</td><td>%s</td></tr>') % (
                label, done if ok else todo)
            for label, ok in rows)
        html = Markup('<p class="text-muted">%s</p>') % (
            _('Channels served by this application: %s', ', '.join(channels))
            if channels else _('No channel uses this provider.'))
        html += Markup('<table class="table table-sm w-auto">%s</table>') % body

        ready = all(ok for _label, ok in rows)
        html += Markup('<p>%s</p>') % (
            _('Every prerequisite Health19 can see is in place. The channel '
              'cards become available as soon as this row is active.')
            if ready else
            _('Until every row above is done, the channels served by this '
              'application stay "Not available yet" for every tenant.'))

        # GL-1: one source of truth. Where the Go-Live Studio declares the
        # steps, they are the steps — this checklist renders their titles
        # rather than a second, drifting copy of the same paperwork.
        declared = self._golive_steps().get(self.provider) or []
        # GL-4: every provider in the catalogue is declared, so the fallback
        # below never fires today. It is kept for the provider that arrives
        # with paperwork before it has a flow.
        steps = ([step['title'] for step in declared] or
                 PROVIDER_EXTERNAL_STEPS.get(self.provider) or [])
        if steps:
            console_url, console_name = PROVIDER_CONSOLE.get(
                self.provider, ('', ''))
            html += Markup('<h6 class="mt-3">%s</h6>') % _(
                'Done outside Health19 (%s)', console_name)
            html += Markup('<ol>%s</ol>') % Markup('').join(
                Markup('<li>%s</li>') % step for step in steps)
            if console_url:
                html += Markup(
                    '<p><a href="%s" target="_blank" '
                    'rel="noopener noreferrer">%s</a></p>') % (
                        console_url, console_url)
        return html

    def action_generate_verify_token(self):
        """Mint the Meta webhook verify token (CC-G).

        A value both sides must hold identically: without it
        ``meta_challenge`` refuses the dashboard handshake and
        ``webhook_verified`` can never pass. Generating it here rather than
        asking the operator to invent one is the difference between 24 random
        bytes and "vietuc2026".
        """
        self.ensure_one()
        self._require_operator()
        if self.provider != 'meta':
            raise UserError(_(
                'Only the Meta application uses a webhook verify token.'))
        if str(self.get_extra(VERIFY_TOKEN_KEY) or '').strip():
            raise UserError(_(
                'This application already has a webhook verify token, and '
                'Meta\'s dashboard still holds the old one. Clear the '
                '"%s" entry from the extra configuration (and from the Meta '
                'app) before generating a new one.', VERIFY_TOKEN_KEY))
        try:
            extra = json.loads(self.extra_json or '{}') or {}
        except ValueError:
            raise UserError(_('Extra configuration must be valid JSON.'))
        if not isinstance(extra, dict):
            raise UserError(_('Extra configuration must be a JSON object.'))
        # MERGE, never replace: es_config_id / flb_config_id live in the same
        # object and losing either one dark-cards a channel.
        extra[VERIFY_TOKEN_KEY] = secrets.token_urlsafe(24)
        self.sudo().write({'extra_json': json.dumps(extra, indent=2,
                                                    sort_keys=True)})
        self.env['care.channel.audit']._log(
            'verify_token_generated',
            detail='platform app %s' % self.provider)
        return self._notify(
            _('Verify token generated'),
            _('It is in the extra configuration below. Paste the same value '
              'into the Meta app\'s webhook settings — the handshake fails '
              'until both sides hold it.'))

    # ==================================================================
    # CC-G §G3 — preflight
    # ==================================================================
    def action_preflight(self):
        """Check this application against the provider, where that is possible.

        Persist first, notify after (ledger §5.65): a provider refusal is an
        ANSWER, not an exception, so this never raises on one — the row keeps
        the evidence and the operator gets a notification either way. That
        also means the write cannot be rolled back by the raise it would have
        caused, so no independent cursor is needed here.
        """
        self.ensure_one()
        self._require_operator()
        if self.provider == 'meta':
            status, detail = self._preflight_meta()
        else:
            # Translated through the module constant so the sentence has ONE
            # source: the tests assert it, the catalogue keys on it.
            status, detail = 'unverifiable', _(PREFLIGHT_UNVERIFIABLE)
        self.sudo().write({
            'preflight_status': status,
            'preflight_at': fields.Datetime.now(),
            'preflight_detail': detail,
        })
        self.env['care.channel.audit']._log(
            'preflight', detail='platform app %s: %s' % (self.provider, status))
        titles = {'pass': _('Application verified'),
                  'fail': _('The provider refused these credentials'),
                  'unverifiable': _('Nothing to check server-side')}
        return self._notify(titles.get(status, _('Preflight result')), detail,
                            kind={'pass': 'success', 'fail': 'danger'}.get(
                                status, 'info'))

    def _preflight_meta(self):
        """(status, detail) from Meta's app-access-token endpoint.

        The only provider in the catalogue that documents a credentials-only
        call. Anything at all going wrong is a ``fail`` with redacted detail —
        never a traceback in the operator's face, and never a secret in the
        stored string (the redaction is belt AND braces: ``redact`` strips
        credential-shaped values, and the literal secret is scrubbed after it
        in case a provider echoed it in a shape the denylist does not know).
        """
        self.ensure_one()
        app = self.sudo()
        if not app.client_id or not app.client_secret_enc:
            return 'fail', _('Enter the app id and store the secret first.')
        try:
            secret = app._get_secret()
        except Exception as exc:  # noqa: BLE001 — a corrupt secret is a fail
            _logger.warning('Preflight: platform app %s secret unreadable',
                            self.id)
            return 'fail', redact(exc) or _('The stored secret is unreadable.')
        try:
            name = meta_app_identity(self.env, app.client_id, secret)
        except ChannelSendError as exc:
            return 'fail', self._scrub(redact(exc), secret) or _('refused')
        except Exception as exc:  # noqa: BLE001 — never a traceback here
            _logger.exception('Preflight failed for platform app %s', self.id)
            return 'fail', self._scrub(redact(exc), secret) or _('failed')
        return 'pass', self._scrub(
            name or _('Meta accepted these credentials.'), secret)

    @staticmethod
    def _scrub(text, secret):
        """Last line of defence: the secret itself never reaches a stored field."""
        if text and secret and secret in text:
            text = text.replace(secret, '<redacted>')
        return text

    # ------------------------------------------------------------------
    # Shared plumbing for the two CC-G buttons
    # ------------------------------------------------------------------
    def _require_operator(self):
        """Both buttons are RPC-reachable by name, so the ACL is not the whole
        story — the same reasoning as ``action_set_secret``."""
        if not self.env.user.has_group('base.group_system'):
            raise UserError(_(
                'Only a platform administrator can manage a platform '
                'application.'))

    @staticmethod
    def _notify(title, message, kind='success'):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': title, 'message': message or '',
                       'type': kind, 'sticky': False},
        }

    # ------------------------------------------------------------------
    # Secret handling (architecture §7.2)
    # ------------------------------------------------------------------
    def action_set_secret(self, secret):
        """Encrypt and store the platform app secret. Returns a notification.

        Group-gated explicitly *and* by ACL: this method is RPC-reachable by
        name, so the ACL alone is not the whole story.
        """
        self.ensure_one()
        if not self.env.user.has_group('base.group_system'):
            raise UserError(_(
                'Only a platform administrator can set a platform application '
                'secret.'))
        if not secret or not isinstance(secret, str) or not secret.strip():
            raise UserError(_('The secret cannot be empty.'))
        secret = secret.strip()
        self.sudo().write({
            'client_secret_enc': channel_crypto.encrypt(self.env, secret),
            # No tail for short secrets: '••••' + last4 of a 4-char value IS
            # the value (CC-A review finding #6).
            'secret_hint': '••••' + (secret[-4:] if len(secret) >= 8 else ''),
        })
        self.env['care.channel.audit']._log(
            'secret_rotated',
            detail='platform app %s' % self.provider)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Secret stored'),
                'message': _('The platform application secret is encrypted at '
                             'rest and will never be displayed again.'),
                'type': 'success',
            },
        }

    def _get_secret(self):
        """Server-side only. Leading underscore ⇒ not RPC-callable."""
        self.ensure_one()
        return channel_crypto.decrypt(self.env, self.sudo().client_secret_enc or '')

    @api.model
    def _get_for_provider(self, provider):
        """The active platform app for ``provider``, or an empty recordset."""
        return self.sudo().search(
            [('provider', '=', provider), ('active', '=', True)], limit=1)


class ChannelPlatformAppSecretWizard(models.TransientModel):
    _name = 'channel.platform.app.secret.wizard'
    _description = 'Set Platform Application Secret'

    app_id = fields.Many2one(
        'channel.platform.app', string='Platform application', required=True,
        ondelete='cascade')
    # NOT required at the model level: action_apply() blanks the column right
    # after storing the secret, and a NOT NULL constraint would refuse that
    # (the transient row outlives the call by up to a day). The view marks it
    # required, and action_set_secret refuses an empty value anyway.
    secret = fields.Char(help='Pasted once; never displayed again.')

    def action_apply(self):
        self.ensure_one()
        result = self.app_id.action_set_secret(self.secret)
        # Do not leave the plaintext sitting in the transient row.
        self.sudo().write({'secret': False})
        return result
