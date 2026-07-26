# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import logging
import json
from datetime import datetime, timedelta

from ..services.zalo_api import get_api_client

_logger = logging.getLogger(__name__)

# Fields whose value decides WHERE a token is posted. A Zalo manager who can
# repoint them exfiltrates the next refresh (defect Z5): the attacker's host
# receives app_id + refresh_token. Server paths (sudo, crons, the framework
# adapter) still write them; a user, however privileged in Zalo terms, does
# not. A write guard rather than `groups=` on the field, because the ZNS
# contract has non-system callers READING api_base_url on every send.
SYSTEM_ONLY_FIELDS = ('api_base_url', 'api_version')


class ZaloConfig(models.Model):
    """
    Zalo Official Account configuration and OAuth token management.

    **CC-D: this model is now a FACADE.** The credentials it exposes may live
    on a ``care.channel.connection`` (encrypted at rest, rotated under a row
    lock, never in a chatter tracking value); the plaintext columns below stay
    for connections that were never migrated and are read only as a fallback.
    Nothing in the frozen 10-module ZNS contract changes: ``get_api_client``,
    ``search([('active','=',True)])`` and ``send_zns_notification`` behave
    exactly as they did.
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
        # NO tracking (defect Z1): a tracked secret is copied verbatim into
        # mail.tracking.value on every change, which is readable by anyone who
        # can read the chatter — a leak path that walks straight around the
        # field's own `groups=`.
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

    # ------------------------------------------------------------------
    # CC-D facade — ONE place that answers "what is our token, really"
    # ------------------------------------------------------------------
    # There is deliberately NO `connection_id` column. The handover asked for
    # one, but a Many2one from here to `care.channel.connection` cannot be
    # built: health_zalo loads BEFORE the channels module (health_care_command
    # sits between them and depends on this one), and Odoo runs an incremental
    # `_setup_models__` after every module it loads — the comodel would not
    # exist yet. Declaring the dependency the other way closes a loop and the
    # whole graph is skipped. So the join key is the framework's OWN
    # uniqueness key instead: one active connection per (channel, company),
    # which is exactly what its partial unique index enforces.
    def _channel_connection(self):
        """This company's Zalo connection, as sudo, or None.

        SOFT reference: health_zalo must stay installable and working with no
        Channel Center at all — which is also what every never-migrated
        deployment looks like.
        """
        self.ensure_one()
        if 'care.channel.connection' not in self.env:
            return None
        return self.env['care.channel.connection'].sudo().search([
            ('channel', '=', 'zalo'),
            ('company_id', '=', (self.company_id or self.env.company).id),
        ], order='id desc', limit=1)

    def _connection(self):
        """The connection that actually holds credentials, or an empty/None."""
        self.ensure_one()
        conn = self._channel_connection()
        if not conn:
            return conn
        return conn if conn.has_credentials else conn.browse()

    def _effective_access_token(self):
        """The access token to use, from wherever it actually lives."""
        self.ensure_one()
        conn = self._connection()
        if conn:
            token = conn._get_secret('access_token')
            if token:
                return token
        return self.sudo().access_token

    def _effective_refresh_token(self):
        self.ensure_one()
        conn = self._connection()
        if conn:
            token = conn._get_secret('refresh_token')
            if token:
                return token
        return self.sudo().refresh_token

    def _effective_expires_at(self):
        self.ensure_one()
        conn = self._connection()
        if conn and conn.token_expires_at:
            return conn.token_expires_at
        return self.token_expires_at

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

    # ------------------------------------------------------------------
    # Z5 — only a system administrator may repoint the API host
    # ------------------------------------------------------------------
    def _check_system_only_fields(self, vals):
        offending = [f for f in SYSTEM_ONLY_FIELDS if f in vals]
        if offending and not (self.env.su
                              or self.env.user.has_group('base.group_system')):
            raise UserError(_(
                'Only a system administrator can change where Zalo requests '
                'are sent (%s).', ', '.join(offending)))

    def write(self, vals):
        self._check_system_only_fields(vals)
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        # The same gate on the way IN (CC-D review): guarding only `write`
        # left "create it already pointed at my host" open, which is the same
        # exfil with one less step.
        for vals in vals_list:
            self._check_system_only_fields(vals)
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # Z6 — the legacy OAuth flow is retired, not patched
    # ------------------------------------------------------------------
    # It had no PKCE (Zalo v4 requires S256), a state that lived forever and
    # was bound to nobody, a permanently persisted authorization code and a
    # naive-vs-UTC expiry skew. All four are fixed STRUCTURALLY by
    # care.channel.oauth.session; re-implementing them here would only give an
    # attacker a second, weaker door.
    _CENTER_HINT = ('Connect Zalo from Care Command Setup → Channel Center. '
                    'The old sign-in on this form has been retired: it did '
                    'not use the security Zalo now requires.')

    def action_connect_zalo(self):
        raise UserError(_(self._CENTER_HINT))

    def action_exchange_code_for_token(self, code):
        raise UserError(_(self._CENTER_HINT))

    def action_refresh_token(self):
        """Refresh the access token.

        A connection-linked config refreshes through the framework: the row
        lock (``FOR UPDATE NOWAIT``) makes two workers unable to burn Zalo's
        single-use refresh token, the corrected endpoint carries the
        ``secret_key`` header (defect Z8), and the new pair is persisted on an
        independent cursor BEFORE anything uses it.
        """
        self.ensure_one()
        conn = self._connection()
        if conn:
            result = conn._get_adapter().refresh_authorization()
            if result == 'locked':
                # Another worker holds the row: it is refreshing right now,
                # and burning a second rotation would kill the grant.
                _logger.info('Zalo config %s: refresh already in progress',
                             self.id)
                return {'locked': True}
            self.invalidate_recordset()
            return {'type': 'ir.actions.client', 'tag': 'display_notification',
                    'params': {'title': _('Success'),
                               'message': _('Access token refreshed successfully'),
                               'type': 'success'}}

        if not self._effective_refresh_token():
            raise UserError(_('No refresh token available. Please reconnect to Zalo.'))

        token_service = self.env['zalo.token.manager']
        result = token_service.refresh_access_token(self)

        if result.get('access_token'):
            self.sudo().write({
                'access_token': result['access_token'],
                'refresh_token': result.get('refresh_token') or self.sudo().refresh_token,
                'token_expires_at': fields.Datetime.now() + timedelta(
                    seconds=int(result.get('expires_in') or 3600)),
                'state': 'connected',
            })
            _logger.info('Zalo access token refreshed for config %s', self.id)
            return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
                'title': _('Success'),
                'message': _('Access token refreshed successfully'),
                'type': 'success',
            }}
        self.sudo().state = 'error'
        raise UserError(_('Failed to refresh token: %s') % result.get('error'))

    def action_disconnect_zalo(self):
        """Disconnect from Zalo and clear tokens"""
        self.ensure_one()
        if self._connection():
            raise UserError(_(
                'Turn this channel off from Care Command Setup → Channel '
                'Center, so the conversations and the audit trail stay '
                'consistent.'))

        self.sudo().write({
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

        if not self._effective_access_token():
            raise UserError(_('No access token available. Please connect to Zalo first.'))

        try:
            # The real seam is the ZaloAPIClient factory — `zalo.api.client`
            # is NOT a registered model (§5.54).
            api_service = get_api_client(self.env)
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

        expires_at = self._effective_expires_at()
        if not expires_at:
            # No expiry known but a token in hand: treat it as usable rather
            # than forcing a refresh that would burn the single-use grant.
            return not self._effective_access_token()

        # Consider expired if less than 5 minutes remaining
        buffer_time = timedelta(minutes=5)
        return fields.Datetime.now() >= (expires_at - buffer_time)

    def get_valid_token(self):
        """Get a valid access token, refreshing if necessary"""
        self.ensure_one()

        if self.is_token_expired() and self._effective_refresh_token():
            _logger.info('Zalo access token expired for config %s, refreshing',
                         self.id)
            self.action_refresh_token()
            self.invalidate_recordset()

        return self._effective_access_token()

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

    # ------------------------------------------------------------------
    # Z9 — the webhook buttons were a TODO that flipped a boolean
    # ------------------------------------------------------------------
    # They claimed "Webhook Enabled" while registering nothing with anybody.
    # Zalo's webhook URL is portal-only, one per app (architecture §13), so
    # there is no API to call: the Channel Center walks the tenant through the
    # portal instead and proves it with a real signed event.
    def action_enable_webhook(self):
        raise UserError(_(self._CENTER_HINT))

    def action_disable_webhook(self):
        raise UserError(_(self._CENTER_HINT))

    @api.model
    def cron_refresh_expiring_tokens(self):
        """Cron job to auto-refresh tokens that will expire soon"""
        configs = self.search([
            ('active', '=', True),
            ('state', '=', 'connected'),
        ])

        for config in configs:
            if config.is_token_expired() and config._effective_refresh_token():
                try:
                    with self.env.cr.savepoint():
                        config.action_refresh_token()
                    _logger.info('Auto-refreshed Zalo token for config %s',
                                 config.id)
                except Exception as e:  # noqa: BLE001
                    _logger.warning('Failed to auto-refresh Zalo token for '
                                    'config %s: %s', config.id, e)
                    config.sudo().state = 'error'

    # ==================================================================
    # CC-D — the bridge to the framework connection
    # ==================================================================
    @api.model
    def _sync_from_connection(self, connection, oa_id=None, oa_name=None):
        """A framework connection just authorized: make the legacy side usable.

        Called by ``ZaloAdapter.handle_callback`` through a SOFT reference
        (the framework never imports this module). Writes no credential here —
        the tokens stay encrypted on the connection and are read through the
        facade. What it DOES write matters: the legacy chat pipeline resolves
        its config through ``get_active_config()``, which requires
        ``state='connected'``, so without this the inbound handler would raise
        "No active Zalo configuration found" on the first real message.
        """
        connection.ensure_one()
        config = self.sudo().search([
            ('company_id', '=', connection.company_id.id),
            ('active', '=', True)], limit=1)
        if not config:
            _logger.info('No zalo.config to bridge for connection %s',
                         connection.id)
            return False
        vals = {'state': 'connected'}
        if oa_id and config.oa_id != oa_id:
            vals['oa_id'] = oa_id
        if oa_name and not config.name:
            vals['name'] = oa_name
        config.sudo().write(vals)
        return config

    @api.model
    def _migrate_legacy_connections(self):
        """One ``state='legacy'`` connection per active config. Idempotent.

        Nothing is deleted and nothing is invalidated: an existing Zalo setup
        keeps working exactly as it did until a human completes the new
        sign-in in the Channel Center. Where the config carries plaintext
        tokens they are ENCRYPT-COPIED onto the connection (the legacy columns
        are left in place this phase — a wipe is a separate, reversible
        decision).
        """
        if 'care.channel.connection' not in self.env:
            return {'created': 0, 'existing': 0, 'copied': 0}
        # Imported here, not at module level: this module must stay importable
        # and installable with no Channel Center at all.
        from odoo.addons.health_care_command_channels.services import (  # noqa: PLC0415
            channel_crypto,
        )
        Connection = self.env['care.channel.connection'].sudo()
        created, existing_count, copied = 0, 0, 0
        configs = self.sudo().with_context(active_test=False).search(
            [('active', '=', True)])
        for config in configs:
            company = config.company_id or self.env.company
            conn = Connection.with_context(active_test=False).search([
                ('channel', '=', 'zalo'),
                ('company_id', '=', company.id)], order='id desc', limit=1)
            if not conn:
                conn = Connection._internal().create({
                    'channel': 'zalo', 'company_id': company.id})
                conn = Connection.browse(conn.id)
                conn._transition('legacy', reason='migrated zalo.config')
                created += 1
            else:
                # Already migrated (or already connected for real): link to
                # what is there, never duplicate. This is what makes a re-run
                # a no-op.
                existing_count += 1
            vals = {}
            if config.oa_id and not conn.resource_external_id:
                vals['resource_external_id'] = config.oa_id
            if config.name and not conn.resource_display_name:
                vals['resource_display_name'] = config.name
            access = config.sudo().access_token
            refresh = config.sudo().refresh_token
            if access and not conn.sudo().access_token_enc:
                vals['access_token_enc'] = channel_crypto.encrypt(
                    self.env, access)
                copied += 1
            if refresh and not conn.sudo().refresh_token_enc:
                vals['refresh_token_enc'] = channel_crypto.encrypt(
                    self.env, refresh)
            if config.token_expires_at and not conn.token_expires_at:
                vals['token_expires_at'] = config.token_expires_at
            if vals:
                conn.sudo()._internal().write(vals)
        _logger.info('health_zalo CC-D migration: %s connection(s) created, '
                     '%s already present, %s credential set(s) copied',
                     created, existing_count, copied)
        return {'created': created, 'existing': existing_count,
                'copied': copied}

    @api.model
    def _drop_app_secret_tracking(self):
        """Z1 clean-up: delete the tracking rows that already leaked.

        Removing ``tracking=True`` stops NEW leaks; the values written before
        this phase are still sitting in ``mail.tracking.value`` where any
        chatter reader can see them.
        """
        field = self.env['ir.model.fields']._get(self._name, 'app_secret')
        if not field:
            return 0
        rows = self.env['mail.tracking.value'].sudo().search(
            [('field_id', '=', field.id)])
        count = len(rows)
        if count:
            rows.unlink()
            _logger.info('health_zalo: removed %s leaked app_secret tracking '
                         'value(s)', count)
        return count
