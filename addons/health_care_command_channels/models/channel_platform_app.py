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

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from ..services import channel_crypto

_logger = logging.getLogger(__name__)

PROVIDERS = [
    ('meta', 'Meta (WhatsApp + Messenger)'),
    ('zalo', 'Zalo'),
    ('google', 'Google'),
    ('microsoft', 'Microsoft'),
]


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
            'secret_hint': '••••' + secret[-4:],
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
