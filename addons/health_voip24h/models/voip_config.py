# -*- coding: utf-8 -*-

import hashlib
import hmac
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class VoIP24hConfig(models.Model):
    """
    VoIP24h Configuration and Authentication.

    Manages API credentials, webhooks, sync settings, and call functionality controls.
    """
    _name = 'voip.config'
    _description = 'VoIP24h Configuration'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'

    # Basic Info
    name = fields.Char(
        string='Configuration Name',
        required=True,
        default='VoIP24h Integration',
        tracking=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True,
        index=True,
    )
    active = fields.Boolean(
        default=True,
        tracking=True,
    )

    # API Credentials (never tracked: tracking would log secrets into chatter)
    api_key = fields.Char(
        string='API Key',
        groups='base.group_system',
    )
    api_secret = fields.Char(
        string='API Secret',
        groups='base.group_system',
    )
    account_id = fields.Char(
        string='Account ID',
        required=True,
        tracking=True,
    )
    domain = fields.Char(
        string='VoIP24h Domain',
        default='voip24h.vn',
    )
    api_base_url = fields.Char(
        string='API Base URL',
        default='https://api.voip24h.vn/v1',
        required=True,
    )

    # Authentication Token
    access_token = fields.Char(
        string='Access Token',
        groups='base.group_system',
        readonly=True,
    )
    token_expires_at = fields.Datetime(
        string='Token Expires At',
        readonly=True,
    )
    token_type = fields.Char(
        string='Token Type',
        readonly=True,
    )

    # Webhook Configuration
    webhook_enabled = fields.Boolean(
        string='Webhook Enabled',
        default=False,
        tracking=True,
        help='Enable real-time webhook notifications from VoIP24h',
    )
    webhook_url = fields.Char(
        string='Webhook URL',
        compute='_compute_webhook_url',
        readonly=True,
        help='URL for VoIP24h to send webhook notifications',
    )
    webhook_secret = fields.Char(
        string='Webhook Secret',
        groups='base.group_system',
        help='Secret key for webhook signature validation (HMAC-SHA256 of the raw body)',
    )

    # Call Functionality Control (Master Switch Feature)
    enable_call_functionality = fields.Boolean(
        string='Enable Call Functionality',
        default=False,
        tracking=True,
        help='Enable click-to-dial and incoming call popups. '
             'When disabled, only call logs, recordings, and analytics are available.',
    )
    enable_outgoing_calls = fields.Boolean(
        string='Enable Outgoing Calls',
        default=True,
        tracking=True,
        help='Allow users to initiate calls via click-to-dial. '
             'Requires "Enable Call Functionality" to be enabled.',
    )
    enable_incoming_call_popups = fields.Boolean(
        string='Enable Incoming Call Popups',
        default=True,
        tracking=True,
        help='Show real-time popups for incoming calls. '
             'Requires "Enable Call Functionality" to be enabled.',
    )

    # Sync Settings
    auto_sync_enabled = fields.Boolean(
        string='Auto Sync CDR',
        default=True,
        tracking=True,
        help='Automatically sync call detail records periodically',
    )
    sync_interval_minutes = fields.Integer(
        string='Sync Interval (Minutes)',
        default=15,
        help='How often to sync call history (in minutes)',
    )
    sync_history_days = fields.Integer(
        string='Sync History (Days)',
        default=30,
        help='Number of days to sync call history on first setup',
    )
    last_sync_date = fields.Datetime(
        string='Last Sync Date',
        readonly=True,
    )

    # Statistics
    total_calls_synced = fields.Integer(
        string='Total Calls Synced',
        readonly=True,
        default=0,
    )
    total_recordings_synced = fields.Integer(
        string='Total Recordings Synced',
        readonly=True,
        default=0,
    )

    # State
    state = fields.Selection([
        ('draft', 'Draft'),
        ('connected', 'Connected'),
        ('error', 'Connection Error'),
    ], string='Status', default='draft', tracking=True, required=True)

    error_message = fields.Text(
        string='Error Message',
        readonly=True,
    )

    extension_ids = fields.One2many(
        'voip.extension',
        'voip_config_id',
        string='Extensions',
    )
    extension_count = fields.Integer(
        compute='_compute_extension_count',
    )

    @api.depends('company_id')
    def _compute_webhook_url(self):
        """Compute webhook URL for VoIP24h to call"""
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for config in self:
            config.webhook_url = f"{base_url}/voip24h/webhook"

    def _compute_extension_count(self):
        counts = dict(self.env['voip.extension']._read_group(
            [('voip_config_id', 'in', self.ids)],
            groupby=['voip_config_id'],
            aggregates=['__count'],
        ))
        for config in self:
            config.extension_count = counts.get(config, 0)

    def _check_credentials(self):
        self.ensure_one()
        config_sudo = self.sudo()
        if not config_sudo.api_key or not config_sudo.api_secret:
            raise UserError(_('Please configure the VoIP24h API credentials first.'))

    def _get_api_client(self):
        """Return an authenticated-capable API client for this config."""
        from ..services.voip24h_api import VoIP24hAPI
        self.ensure_one()
        self._check_credentials()
        # sudo: api_key/api_secret/access_token are group_system-protected fields
        return VoIP24hAPI(self.sudo())

    def action_test_connection(self):
        """Test VoIP24h API connection"""
        self.ensure_one()

        try:
            api = self._get_api_client()
            api.authenticate()

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Connection Successful'),
                    'message': _('Successfully connected to VoIP24h API'),
                    'type': 'success',
                    'sticky': False,
                }
            }

        except UserError:
            raise
        except Exception as e:
            _logger.error('VoIP24h connection test failed: %s', e, exc_info=True)
            self.sudo().write({
                'state': 'error',
                'error_message': str(e),
            })

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Connection Failed'),
                    'message': str(e),
                    'type': 'danger',
                    'sticky': True,
                }
            }

    def action_sync_call_history(self):
        """Manually trigger call history sync"""
        from ..services.cdr_sync import sync_call_history
        self.ensure_one()
        self._check_credentials()

        result = sync_call_history(self.sudo())

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Sync Completed'),
                'message': _(
                    '%(created)s new calls, %(updated)s updated, %(errors)s errors.',
                    created=result['created'],
                    updated=result['updated'],
                    errors=result['errors'],
                ),
                'type': 'success' if not result['errors'] else 'warning',
                'sticky': False,
            }
        }

    def action_sync_extensions(self):
        """Fetch extensions/lines from VoIP24h and upsert voip.extension records."""
        self.ensure_one()
        api = self._get_api_client()
        extensions = api.get_extensions()

        Extension = self.env['voip.extension']
        created = updated = 0
        for ext_data in extensions:
            number = str(ext_data.get('extension') or ext_data.get('extension_number') or '').strip()
            if not number:
                continue
            vals = {
                'name': ext_data.get('name') or number,
                'extension_number': number,
                'voip_config_id': self.id,
            }
            existing = Extension.with_context(active_test=False).search([
                ('voip_config_id', '=', self.id),
                ('extension_number', '=', number),
            ], limit=1)
            if existing:
                existing.write(vals)
                updated += 1
            else:
                Extension.create(vals)
                created += 1

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Extensions Synced'),
                'message': _(
                    '%(created)s created, %(updated)s updated.',
                    created=created, updated=updated,
                ),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_view_extensions(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Extensions'),
            'res_model': 'voip.extension',
            'view_mode': 'list,form',
            'domain': [('voip_config_id', '=', self.id)],
            'context': {'default_voip_config_id': self.id},
        }

    @api.model
    def get_active_config(self):
        """Get active VoIP24h configuration (singleton pattern per company)"""
        return self.search([
            ('company_id', '=', self.env.company.id)
        ], limit=1)

    @api.model
    def cron_sync_call_history(self):
        """Cron job to sync call history for all active configurations"""
        from ..services.cdr_sync import sync_call_history

        configs = self.search([
            ('auto_sync_enabled', '=', True),
            ('state', '=', 'connected'),
        ])

        now = fields.Datetime.now()
        for config in configs:
            # Respect the per-config interval (the cron itself runs frequently)
            interval = max(config.sync_interval_minutes or 15, 1)
            if config.last_sync_date and (now - config.last_sync_date).total_seconds() < interval * 60:
                continue
            try:
                _logger.info('Starting VoIP24h call history sync for config: %s', config.name)
                sync_call_history(config.sudo())
                self.env.cr.commit()
            except Exception as e:
                _logger.error('Cron sync failed for %s: %s', config.name, e, exc_info=True)
                self.env.cr.rollback()
                config.sudo().write({
                    'state': 'error',
                    'error_message': str(e),
                })
                self.env.cr.commit()

    # ------------------------------------------------------------------
    # Call functionality gates
    # ------------------------------------------------------------------

    def is_calling_enabled(self):
        """Check if calling functionality is enabled"""
        self.ensure_one()
        return self.enable_call_functionality

    def can_make_outgoing_calls(self):
        """Check if outgoing calls are allowed"""
        self.ensure_one()
        return self.enable_call_functionality and self.enable_outgoing_calls

    def can_show_incoming_popups(self):
        """Check if incoming call popups should be shown"""
        self.ensure_one()
        return self.enable_call_functionality and self.enable_incoming_call_popups

    # ------------------------------------------------------------------
    # Click-to-dial
    # ------------------------------------------------------------------

    def _get_user_extension(self, user=None):
        """Extension assigned to the given (or current) user on this config."""
        self.ensure_one()
        user = user or self.env.user
        return self.env['voip.extension'].search([
            ('voip_config_id', '=', self.id),
            ('user_id', '=', user.id),
            ('allow_outgoing', '=', True),
        ], limit=1)

    def initiate_user_call(self, phone_number, extension=None):
        """Initiate an outbound call for the current user via VoIP24h.

        Returns the raw API response dict.
        """
        self.ensure_one()

        if not self.can_make_outgoing_calls():
            raise UserError(_('Outgoing calls are disabled. Please contact your administrator.'))
        if not phone_number:
            raise UserError(_('No phone number to call.'))

        extension = extension or self._get_user_extension()
        if not extension:
            raise UserError(_(
                'No VoIP extension is assigned to your user. '
                'Please contact your administrator.'))

        api = self._get_api_client()
        result = api.initiate_call(extension.extension_number, phone_number)
        _logger.info('Click-to-dial: user %s ext %s -> %s',
                     self.env.user.login, extension.extension_number, phone_number)
        return result

    # ------------------------------------------------------------------
    # Webhook signature
    # ------------------------------------------------------------------

    def _verify_webhook_signature(self, raw_body, signature):
        """Validate the HMAC-SHA256 signature of a webhook payload.

        Returns True when no secret is configured (validation disabled).
        """
        self.ensure_one()
        secret = self.sudo().webhook_secret
        if not secret:
            return True
        if not signature:
            return False
        expected = hmac.new(secret.encode(), raw_body or b'', hashlib.sha256).hexdigest()
        provided = signature.strip().lower()
        if provided.startswith('sha256='):
            provided = provided[len('sha256='):]
        return hmac.compare_digest(expected, provided)
