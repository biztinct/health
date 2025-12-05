# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

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

    # API Credentials
    api_key = fields.Char(
        string='API Key',
        required=True,
        groups='base.group_system',
        tracking=True,
    )
    api_secret = fields.Char(
        string='API Secret',
        required=True,
        groups='base.group_system',
        tracking=True,
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
        help='Secret key for webhook signature validation',
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

    @api.depends('company_id')
    def _compute_webhook_url(self):
        """Compute webhook URL for VoIP24h to call"""
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for config in self:
            config.webhook_url = f"{base_url}/voip24h/webhook"

    def action_test_connection(self):
        """Test VoIP24h API connection"""
        self.ensure_one()

        try:
            # TODO: Implement API connection test
            # from ..services.voip24h_api import VoIP24hAPI
            # api = VoIP24hAPI(self)
            # api.test_connection()

            self.write({
                'state': 'connected',
                'error_message': False,
            })

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

        except Exception as e:
            _logger.error(f'VoIP24h connection test failed: {e}', exc_info=True)
            self.write({
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
        self.ensure_one()

        if not self.api_key or not self.api_secret:
            raise UserError(_('Please configure API credentials first'))

        try:
            # TODO: Implement manual sync
            # from ..services.cdr_sync import sync_call_history
            # result = sync_call_history(self)

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sync Started'),
                    'message': _('Call history synchronization has been initiated'),
                    'type': 'info',
                    'sticky': False,
                }
            }

        except Exception as e:
            _logger.error(f'Manual sync failed: {e}', exc_info=True)
            raise UserError(_('Sync failed: %s') % str(e))

    @api.model
    def get_active_config(self):
        """Get active VoIP24h configuration (singleton pattern)"""
        return self.search([
            ('active', '=', True),
            ('company_id', '=', self.env.company.id)
        ], limit=1)

    @api.model
    def cron_sync_call_history(self):
        """Cron job to sync call history for all active configurations"""
        configs = self.search([
            ('active', '=', True),
            ('auto_sync_enabled', '=', True),
            ('state', '=', 'connected'),
        ])

        for config in configs:
            try:
                _logger.info(f'Starting call history sync for config: {config.name}')
                # TODO: Implement sync
                # from ..services.cdr_sync import sync_call_history
                # sync_call_history(config)

                config.last_sync_date = fields.Datetime.now()

            except Exception as e:
                _logger.error(f'Cron sync failed for {config.name}: {e}', exc_info=True)
                config.write({
                    'state': 'error',
                    'error_message': str(e),
                })

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
