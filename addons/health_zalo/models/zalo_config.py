# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import logging
import json
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)


class ZaloConfig(models.Model):
    """
    Zalo Official Account configuration and OAuth token management.

    Stores app credentials, OAuth tokens, and provides token refresh functionality.
    Singleton model - only one active configuration per company.
    """
    _name = 'zalo.config'
    _description = 'Zalo OA Configuration'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    # Company & Basic Info
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        tracking=True,
    )
    name = fields.Char(
        string='Configuration Name',
        required=True,
        default='Zalo OA Configuration',
        tracking=True,
    )
    active = fields.Boolean(
        string='Active',
        default=True,
        tracking=True,
        help='Only one configuration can be active per company',
    )

    # Zalo Official Account Credentials
    app_id = fields.Char(
        string='App ID',
        required=True,
        tracking=True,
        help='Zalo Official Account App ID from https://developers.zalo.me',
    )
    app_secret = fields.Char(
        string='App Secret',
        required=True,
        tracking=True,
        groups='base.group_system',
        help='Zalo Official Account App Secret (only visible to administrators)',
    )
    oa_id = fields.Char(
        string='OA ID',
        required=True,
        tracking=True,
        help='Zalo Official Account ID',
    )

    # OAuth Tokens
    access_token = fields.Char(
        string='Access Token',
        groups='base.group_system',
        help='OAuth 2.0 access token for Zalo API calls',
    )
    refresh_token = fields.Char(
        string='Refresh Token',
        groups='base.group_system',
        help='OAuth 2.0 refresh token for obtaining new access tokens',
    )
    token_expires_at = fields.Datetime(
        string='Token Expires At',
        help='When the current access token will expire',
    )
    token_type = fields.Char(
        string='Token Type',
        default='Bearer',
    )

    # OAuth Configuration
    oauth_redirect_uri = fields.Char(
        string='OAuth Redirect URI',
        compute='_compute_oauth_redirect_uri',
        store=True,
        help='Callback URL for OAuth flow (must match Zalo app settings)',
    )
    oauth_code = fields.Char(
        string='Authorization Code',
        help='Temporary code from OAuth callback (used once to obtain tokens)',
    )
    oauth_state = fields.Char(
        string='OAuth State',
        help='CSRF protection token for OAuth flow',
    )

    # Webhook Configuration
    webhook_url = fields.Char(
        string='Webhook URL',
        compute='_compute_webhook_url',
        store=True,
        help='URL where Zalo will send incoming message notifications',
    )
    webhook_secret = fields.Char(
        string='Webhook Secret',
        groups='base.group_system',
        help='Secret key for validating webhook signatures',
    )
    webhook_enabled = fields.Boolean(
        string='Webhook Enabled',
        default=False,
        tracking=True,
        help='Enable webhook for receiving real-time message notifications',
    )

    # Status & Statistics
    state = fields.Selection([
        ('draft', 'Draft'),
        ('connected', 'Connected'),
        ('disconnected', 'Disconnected'),
        ('error', 'Error'),
    ], string='Status', default='draft', required=True, tracking=True)

    last_sync_date = fields.Datetime(
        string='Last Sync',
        readonly=True,
    )
    total_messages_sent = fields.Integer(
        string='Messages Sent',
        default=0,
        readonly=True,
    )
    total_messages_received = fields.Integer(
        string='Messages Received',
        default=0,
        readonly=True,
    )

    # API Configuration
    api_base_url = fields.Char(
        string='API Base URL',
        default='https://openapi.zalo.me',
        required=True,
    )
    api_version = fields.Char(
        string='API Version',
        default='v2.0',
        required=True,
    )

    @api.depends('company_id')
    def _compute_oauth_redirect_uri(self):
        """Compute OAuth redirect URI based on Odoo base URL"""
        for config in self:
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            config.oauth_redirect_uri = f"{base_url}/zalo/oauth/callback"

    @api.depends('company_id')
    def _compute_webhook_url(self):
        """Compute webhook URL based on Odoo base URL"""
        for config in self:
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            config.webhook_url = f"{base_url}/zalo/webhook"

    @api.constrains('active', 'company_id')
    def _check_active_config(self):
        """Ensure only one active configuration per company"""
        for config in self:
            if config.active:
                other_active = self.search([
                    ('id', '!=', config.id),
                    ('company_id', '=', config.company_id.id),
                    ('active', '=', True),
                ])
                if other_active:
                    raise ValidationError(_(
                        'Only one Zalo configuration can be active per company. '
                        'Please deactivate the existing configuration first.'
                    ))

    def action_connect_zalo(self):
        """Initiate OAuth 2.0 authorization flow"""
        self.ensure_one()

        if not self.app_id or not self.app_secret:
            raise UserError(_('Please configure App ID and App Secret first.'))

        # Generate random state for CSRF protection
        import secrets
        oauth_state = secrets.token_urlsafe(32)
        self.oauth_state = oauth_state

        # Construct Zalo OAuth URL
        auth_url = (
            f"https://oauth.zalo.me/v4/permission"
            f"?app_id={self.app_id}"
            f"&redirect_uri={self.oauth_redirect_uri}"
            f"&state={oauth_state}"
        )

        return {
            'type': 'ir.actions.act_url',
            'url': auth_url,
            'target': 'new',
        }

    def action_exchange_code_for_token(self, code):
        """
        Exchange authorization code for access/refresh tokens.
        Called by webhook controller after OAuth callback.
        """
        self.ensure_one()

        token_service = self.env['zalo.token.manager']
        result = token_service.exchange_code_for_token(self, code)

        if result.get('access_token'):
            self.write({
                'access_token': result['access_token'],
                'refresh_token': result.get('refresh_token'),
                'token_expires_at': datetime.now() + timedelta(seconds=result.get('expires_in', 3600)),
                'oauth_code': code,
                'state': 'connected',
            })
            _logger.info(f'Zalo OAuth connected successfully for {self.name}')
        else:
            self.state = 'error'
            raise UserError(_('Failed to exchange authorization code for token: %s') % result.get('error'))

    def action_refresh_token(self):
        """Manually refresh access token"""
        self.ensure_one()

        if not self.refresh_token:
            raise UserError(_('No refresh token available. Please reconnect to Zalo.'))

        token_service = self.env['zalo.token.manager']
        result = token_service.refresh_access_token(self)

        if result.get('access_token'):
            self.write({
                'access_token': result['access_token'],
                'refresh_token': result.get('refresh_token', self.refresh_token),
                'token_expires_at': datetime.now() + timedelta(seconds=result.get('expires_in', 3600)),
                'state': 'connected',
            })
            _logger.info(f'Zalo access token refreshed for {self.name}')
            return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
                'title': _('Success'),
                'message': _('Access token refreshed successfully'),
                'type': 'success',
            }}
        else:
            self.state = 'error'
            raise UserError(_('Failed to refresh token: %s') % result.get('error'))

    def action_disconnect_zalo(self):
        """Disconnect from Zalo and clear tokens"""
        self.ensure_one()

        self.write({
            'access_token': False,
            'refresh_token': False,
            'token_expires_at': False,
            'oauth_code': False,
            'state': 'disconnected',
        })

        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
            'title': _('Disconnected'),
            'message': _('Zalo account disconnected successfully'),
            'type': 'info',
        }}

    def action_test_connection(self):
        """Test Zalo API connection by fetching OA profile"""
        self.ensure_one()

        if not self.access_token:
            raise UserError(_('No access token available. Please connect to Zalo first.'))

        try:
            api_service = self.env['zalo.api.client']
            profile = api_service.get_oa_profile(self)

            if profile:
                self.state = 'connected'
                return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
                    'title': _('Connection Successful'),
                    'message': _('Connected to Zalo OA: %s') % profile.get('name', 'Unknown'),
                    'type': 'success',
                }}
            else:
                self.state = 'error'
                raise UserError(_('Failed to fetch OA profile'))
        except Exception as e:
            self.state = 'error'
            raise UserError(_('Connection test failed: %s') % str(e))

    def is_token_expired(self):
        """Check if access token is expired or will expire soon"""
        self.ensure_one()

        if not self.token_expires_at:
            return True

        # Consider expired if less than 5 minutes remaining
        buffer_time = timedelta(minutes=5)
        return fields.Datetime.now() >= (self.token_expires_at - buffer_time)

    def get_valid_token(self):
        """Get a valid access token, refreshing if necessary"""
        self.ensure_one()

        if self.is_token_expired():
            _logger.info(f'Access token expired for {self.name}, refreshing...')
            self.action_refresh_token()

        return self.access_token

    @api.model
    def get_active_config(self):
        """Get the active Zalo configuration for current company"""
        config = self.search([
            ('company_id', '=', self.env.company.id),
            ('active', '=', True),
            ('state', '=', 'connected'),
        ], limit=1)

        if not config:
            _logger.warning('No active Zalo configuration found for current company')
            return False

        return config

    def action_enable_webhook(self):
        """Enable webhook and register with Zalo"""
        self.ensure_one()

        if not self.webhook_secret:
            # Generate webhook secret if not exists
            import secrets
            self.webhook_secret = secrets.token_hex(32)

        # TODO: Register webhook URL with Zalo API
        # This requires calling Zalo's webhook registration endpoint

        self.webhook_enabled = True

        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
            'title': _('Webhook Enabled'),
            'message': _('Webhook URL: %s') % self.webhook_url,
            'type': 'success',
        }}

    def action_disable_webhook(self):
        """Disable webhook"""
        self.ensure_one()

        # TODO: Unregister webhook URL from Zalo API

        self.webhook_enabled = False

        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
            'title': _('Webhook Disabled'),
            'message': _('Webhook has been disabled'),
            'type': 'info',
        }}

    @api.model
    def cron_refresh_expiring_tokens(self):
        """Cron job to auto-refresh tokens that will expire soon"""
        configs = self.search([
            ('active', '=', True),
            ('state', '=', 'connected'),
        ])

        for config in configs:
            if config.is_token_expired():
                try:
                    config.action_refresh_token()
                    _logger.info(f'Auto-refreshed token for {config.name}')
                except Exception as e:
                    _logger.error(f'Failed to auto-refresh token for {config.name}: {e}')
                    config.state = 'error'
