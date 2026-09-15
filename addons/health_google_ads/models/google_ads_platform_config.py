# -*- coding: utf-8 -*-
"""``google.ads.platform.config`` — the platform operator's Google credentials.

Two credential planes, exactly as the messaging channels have (architecture
§7.1):

* **this model** holds the Google Cloud OAuth client (id + secret) and the
  Google Ads developer token. One active row per database, operator-only, and
  every secret encrypted with the same recipe the channel secrets use.
* ``google.ads.account`` holds the per-clinic tokens Google issued to that
  clinic's own sign-in.

Nothing here is ever readable by a clinic user: the ACL grants
``base.group_system`` only, the two ``*_enc`` columns additionally carry
``groups='base.group_system'``, and the secrets are written through a wizard
that never reads them back.

This model deliberately does NOT reuse Odoo's Gmail OAuth client rows. An
operator MAY paste the same client id and secret if that Google Cloud project
also has the Ads API enabled — but storage, rotation and lifecycle stay
separate, so revoking one integration cannot silently break the other.
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.health_care_command_channels.services import channel_crypto

from ..services import google_ads_client as gads

_logger = logging.getLogger(__name__)

ACCESS_LEVEL_SELECTION = [
    ('unknown', 'Not stated'),
    ('test', 'Test accounts only'),
    ('basic', 'Basic access'),
    ('standard', 'Standard access'),
]

KIND_SELECTION = [
    ('client_secret', 'Sign-in secret'),
    ('developer_token', 'Advertising access token'),
]


class GoogleAdsPlatformConfig(models.Model):
    _name = 'google.ads.platform.config'
    _description = 'Google Ads Application'
    _inherit = ['mail.thread']
    _order = 'id desc'

    name = fields.Char(
        string='Name', required=True, default='Google Ads application',
        help='A label for this set of Google credentials. Only the platform '
             'operator ever sees it.')
    active = fields.Boolean(string='Active', default=True)

    client_id = fields.Char(
        string='Sign-in ID', tracking=True,
        help='The client ID of the web application created in the Google '
             'Cloud console. It is not a secret.')
    client_secret_enc = fields.Text(
        string='Sign-in Secret (stored)', groups='base.group_system',
        help='Encrypted at rest. It is never shown again after it is stored.')
    client_secret_hint = fields.Char(
        string='Sign-in Secret', readonly=True,
        help='The last few characters, so an operator can tell which secret '
             'is stored. Never the whole value.')
    has_client_secret = fields.Boolean(
        string='Sign-in Secret Stored', compute='_compute_has_secrets')

    developer_token_enc = fields.Text(
        string='Advertising Access Token (stored)',
        groups='base.group_system',
        help='Encrypted at rest. It is never shown again after it is stored.')
    developer_token_hint = fields.Char(
        string='Advertising Access Token', readonly=True,
        help='The last few characters only.')
    has_developer_token = fields.Boolean(
        string='Advertising Access Token Stored',
        compute='_compute_has_secrets')

    access_level = fields.Selection(
        ACCESS_LEVEL_SELECTION, string='Access Level', default='unknown',
        required=True, tracking=True,
        help='What Google has granted this application. It is recorded here '
             'for the operator only — Google decides it, not this screen. '
             'With test-account access, only Google Ads test accounts can be '
             'read.')

    redirect_uri = fields.Char(
        string='Return Address', compute='_compute_redirect_uri',
        help='The exact address Google sends a person back to after they '
             'sign in. Register it in the Google Cloud console.')
    environment_note = fields.Char(
        string='Note',
        help='Anything the next operator needs to know — which Google Cloud '
             'project this is, who owns it. Never a password.')
    checklist = fields.Html(
        string='Checklist', compute='_compute_checklist', sanitize=False)

    # ==================================================================
    # Computes
    # ==================================================================
    @api.depends('client_secret_enc', 'developer_token_enc')
    def _compute_has_secrets(self):
        # Read through sudo(): both source columns are group-restricted, and
        # the batched fetch would otherwise raise for a non-system reader
        # (the channel_platform_app._compute_has_secret precedent).
        for rec in self:
            secure = rec.sudo()
            rec.has_client_secret = bool(secure.client_secret_enc)
            rec.has_developer_token = bool(secure.developer_token_enc)

    def _compute_redirect_uri(self):
        base = (self.env['ir.config_parameter'].sudo()
                .get_param('web.base.url') or '').rstrip('/')
        for rec in self:
            rec.redirect_uri = '%s%s' % (base, gads.CALLBACK_PATH)

    @api.depends('client_id', 'client_secret_enc', 'developer_token_enc')
    def _compute_checklist(self):
        for rec in self:
            rows = [
                (bool(rec.client_id), _('Sign-in ID')),
                (rec.has_client_secret, _('Sign-in secret')),
                (rec.has_developer_token, _('Advertising access token')),
            ]
            html = ['<ul class="list-unstyled mb-0">']
            for done, label in rows:
                mark = '✓' if done else '•'
                state = _('done') if done else _('to do')
                css = 'text-success' if done else 'text-muted'
                html.append('<li class="%s">%s %s — %s</li>'
                            % (css, mark, label, state))
            # The one row nothing on this server can verify: Google does not
            # tell us what is registered against the application. Saying
            # "done" here would be a guess dressed as a measurement.
            html.append('<li class="text-muted">? %s — %s</li>' % (
                _('Return address registered with Google'),
                _('confirmed on the first successful sign-in')))
            html.append('</ul>')
            rec.checklist = ''.join(html)

    # ==================================================================
    # One active application per database
    # ==================================================================
    def init(self):
        init = getattr(super(), 'init', None)
        if callable(init):
            init()
        # Ledger §5.1 — `_sql_constraints` are not materialized on Odoo 19.
        # A partial unique index on `active` allows exactly one active row
        # (every active row carries the same value) and any number of
        # archived ones.
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
                google_ads_platform_config_active_uniq
            ON google_ads_platform_config (active) WHERE active
        """)

    @api.model
    def _check_single_active(self, active, exclude_id=None):
        """Pre-checked in Python so the message is actionable.

        Ledger §5.3: the DB unique index fires BEFORE any Python constraint
        and its IntegrityError poisons the whole transaction, so this has to
        run ahead of the INSERT, not in an `@api.constrains`.
        """
        if not active:
            return
        domain = [('active', '=', True)]
        if exclude_id:
            domain.append(('id', '!=', exclude_id))
        if self.sudo().search_count(domain):
            raise UserError(_(
                'A Google Ads application is already set up on this system. '
                'Open that one and change it, or archive it first.'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._check_single_active(vals.get('active', True))
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('active'):
            for rec in self:
                if not rec.active:
                    self._check_single_active(True, exclude_id=rec.id)
        return super().write(vals)

    # ==================================================================
    # Secrets
    # ==================================================================
    def _require_operator(self):
        """Both setters are RPC-reachable by name, so the ACL is not the whole
        story — the ``channel.platform.app.action_set_secret`` posture."""
        if self.env.su or self.env.user.has_group('base.group_system'):
            return
        raise UserError(_(
            'Only a platform administrator can set up the Google Ads '
            'application.'))

    @staticmethod
    def _hint(secret):
        # No tail for a short secret: '••••' plus the last four of a
        # five-character value IS the value (CC-A review finding #6).
        return '••••' + (secret[-4:] if len(secret) >= 8 else '')

    def action_set_client_secret(self, secret):
        self.ensure_one()
        self._require_operator()
        secret = (secret or '').strip() if isinstance(secret, str) else ''
        if not secret:
            raise UserError(_('The sign-in secret cannot be empty.'))
        self.sudo().write({
            'client_secret_enc': channel_crypto.encrypt(self.env, secret),
            'client_secret_hint': self._hint(secret),
        })
        # Status only — never the value, never a fragment of it.
        self.sudo().message_post(body=_(
            'The Google sign-in secret was stored by %s.', self.env.user.name))
        return self._notify(
            _('Sign-in secret stored'),
            _('It is encrypted on this server and will never be shown '
              'again.'))

    def action_set_developer_token(self, token):
        self.ensure_one()
        self._require_operator()
        token = (token or '').strip() if isinstance(token, str) else ''
        if not token:
            raise UserError(_('The advertising access token cannot be empty.'))
        self.sudo().write({
            'developer_token_enc': channel_crypto.encrypt(self.env, token),
            'developer_token_hint': self._hint(token),
        })
        self.sudo().message_post(body=_(
            'The Google advertising access token was stored by %s.',
            self.env.user.name))
        return self._notify(
            _('Advertising access token stored'),
            _('It is encrypted on this server and will never be shown '
              'again.'))

    def _get_client_secret(self):
        """Server-side only (leading underscore ⇒ not RPC-callable)."""
        self.ensure_one()
        blob = self.sudo().client_secret_enc
        if not blob:
            raise UserError(_(
                'The Google Ads application is not configured. Ask the '
                'platform operator to finish setting it up.'))
        return channel_crypto.decrypt(self.env, blob)

    def _get_developer_token(self):
        """Server-side only (leading underscore ⇒ not RPC-callable)."""
        self.ensure_one()
        blob = self.sudo().developer_token_enc
        if not blob:
            raise UserError(_(
                'The Google Ads application is not configured. Ask the '
                'platform operator to finish setting it up.'))
        return channel_crypto.decrypt(self.env, blob)

    def _ready(self):
        """True when a sign-in can actually be started with this row."""
        self.ensure_one()
        secure = self.sudo()
        return bool(secure.client_id and secure.client_secret_enc
                    and secure.developer_token_enc)

    @api.model
    def _active(self):
        """The one active application, or an empty recordset."""
        return self.sudo().search([('active', '=', True)], limit=1)

    # ==================================================================
    # Buttons
    # ==================================================================
    def _open_secret_wizard(self, kind):
        self.ensure_one()
        self._require_operator()
        return {
            'type': 'ir.actions.act_window',
            'name': (_('Set the sign-in secret') if kind == 'client_secret'
                     else _('Set the advertising access token')),
            'res_model': 'google.ads.platform.secret.wizard',
            'view_mode': 'form',
            'views': [(self.env.ref(
                'health_google_ads.view_google_ads_platform_secret_wizard_form'
            ).id, 'form')],
            'target': 'new',
            'context': {'default_config_id': self.id, 'default_kind': kind},
        }

    def action_open_client_secret_wizard(self):
        return self._open_secret_wizard('client_secret')

    def action_open_developer_token_wizard(self):
        return self._open_secret_wizard('developer_token')

    @staticmethod
    def _notify(title, message, kind='success'):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': title, 'message': message or '',
                       'type': kind, 'sticky': False},
        }

    def _with_reload(self, action):
        """Re-open this record behind the notification.

        FOUND BY DRIVING THE SCREEN: `checklist` and the two hints are
        non-stored computes, so a wizard that answers with a notification
        alone leaves the form showing "Sign-in secret — to do" one second
        after the secret was stored — which reads as a failure. (The same
        `_with_reload` posture the account's buttons already use.)
        """
        self.ensure_one()
        if isinstance(action, dict) and isinstance(action.get('params'), dict):
            action['params']['next'] = {
                'type': 'ir.actions.act_window',
                'res_model': self._name,
                'res_id': self.id,
                'views': [(False, 'form')],
                'target': 'current',
            }
        return action


class GoogleAdsPlatformSecretWizard(models.TransientModel):
    _name = 'google.ads.platform.secret.wizard'
    _description = 'Set Google Ads Application Secret'

    config_id = fields.Many2one(
        'google.ads.platform.config', string='Google Ads application',
        required=True, ondelete='cascade')
    kind = fields.Selection(KIND_SELECTION, string='What to set',
                            required=True, default='client_secret')
    # NOT required at the model level: `action_apply` blanks the column right
    # after storing the value, and a NOT NULL constraint would refuse that
    # (the transient row outlives the call by up to a day). The view marks it
    # required, and the setters refuse an empty value anyway.
    secret = fields.Char(
        string='Value', help='Pasted once; never displayed again.')

    def action_apply(self):
        self.ensure_one()
        if self.kind == 'developer_token':
            result = self.config_id.action_set_developer_token(self.secret)
        else:
            result = self.config_id.action_set_client_secret(self.secret)
        # Do not leave the plaintext sitting in the transient row.
        self.sudo().write({'secret': False})
        return self.config_id._with_reload(result)
