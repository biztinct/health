# -*- coding: utf-8 -*-

import hashlib
import hmac
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


def verify_voip_signature(secret, raw_body, signature):
    """HMAC-SHA256 over the RAW request bytes, compared in constant time.

    Extracted to a module function in CC-F so the webhook route can verify an
    event that belongs to a Channel Center connection with no ``voip.config``
    row behind it yet. The logic is byte-for-byte what
    ``_verify_webhook_signature`` has always done — this is a move, not a
    rewrite. Fails CLOSED on a missing secret or a missing signature.
    """
    if not secret or not signature:
        return False
    expected = hmac.new(secret.encode(), raw_body or b'',
                        hashlib.sha256).hexdigest()
    provided = signature.strip().lower()
    if provided.startswith('sha256='):
        provided = provided[len('sha256='):]
    return hmac.compare_digest(expected, provided)


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

    def _verify_webhook_signature(self, raw_body, signature, connection=None):
        """Validate the HMAC-SHA256 signature of a webhook payload.

        Fails CLOSED: the webhook route is public and runs su, so an
        unconfigured secret must reject events, not accept everything —
        otherwise anyone who guesses the account_id can inject forged calls.

        CC-F changes exactly one thing here: WHERE the secret comes from. The
        algorithm, the raw-bytes basis, the ``sha256=`` tolerance and the
        constant-time compare are untouched — this verifier was already the
        posture the rest of the framework was told to clone (ledger §5.61).
        """
        self.ensure_one()
        secret = self._effective_webhook_secret(connection=connection)
        if not secret:
            _logger.warning(
                'VoIP24h webhook rejected for %s: no webhook secret configured '
                '(signature validation cannot run)', self.name)
            return False
        return verify_voip_signature(secret, raw_body, signature)

    # ==================================================================
    # CC-F — the Channel Center facade
    # ==================================================================
    # Same shape as CC-D's zalo facade, and for the same reason: there is
    # deliberately NO Many2one from here to `care.channel.connection`. The two
    # modules have no dependency edge in either direction (ledger §5.71 — the
    # loop CC-D closed by accident made the whole graph skip), so the join key
    # is the framework's own uniqueness contract: one active connection per
    # (channel, company), backed by its partial unique index.
    #
    # Every reference below is SOFT: health_voip24h must stay installable and
    # working on a server with no Channel Center at all, which is also what
    # every not-yet-migrated deployment looks like.

    def _channel_connection(self):
        """The Calls connection behind this config, as sudo, or None.

        Resolution order matters, and getting it wrong is a real bug rather
        than a tidiness point. The webhook router resolves by ``account_id``
        (company-agnostic — the provider addresses us by account, and whose
        company it is is exactly what we are working out). If this method
        resolved *only* by company, the verifier and the ingest gate could end
        up consulting a DIFFERENT connection than the one the event was routed
        to: verifying against the wrong secret, or gating on the wrong state.
        So the account id is tried first, and the company match is only the
        fallback that keeps a freshly migrated legacy row — which may carry no
        resource id yet — working. (Found in the CC-F self-review.)
        """
        self.ensure_one()
        if 'care.channel.connection' not in self.env:
            return None
        Conn = self.env['care.channel.connection'].sudo()
        company_id = (self.company_id or self.env.company).id
        # Company-scoped on BOTH branches. The company-agnostic lookup belongs
        # to the webhook router alone, which is answering "who owns this
        # account across the deployment"; a config asking "which connection is
        # MINE" that resolved company-agnostically would happily adopt another
        # tenant's connection and verify with their secret. (Caught by T150f
        # after the first attempt at this fix left the account-id branch
        # unscoped — the guard and its test were written together, and the
        # test is what found the hole.)
        if self.account_id:
            exact = Conn.search([
                ('channel', '=', 'call'),
                ('company_id', '=', company_id),
                ('resource_external_id', '=', self.account_id),
            ], order='id desc', limit=1)
            if exact:
                return exact
        fallback = Conn.search([
            ('channel', '=', 'call'),
            ('company_id', '=', company_id),
        ], order='id desc', limit=1)
        if (fallback and self.account_id and fallback.resource_external_id
                and fallback.resource_external_id != self.account_id):
            # It has claimed a DIFFERENT account. Standing in for this one
            # would verify an event with someone else's secret, so answer
            # "no connection" and let the legacy column decide.
            return Conn.browse()
        return fallback

    def _effective_webhook_secret(self, connection=None):
        """The webhook secret to verify against, from wherever it really lives.

        ``connection`` is passed in by the webhook route so the secret we
        verify with belongs to the connection the event was actually routed
        to. Re-deriving it here would be a second, independent answer to the
        same question, and two answers to one question eventually disagree.

        The connection wins when it has one: there the value is encrypted at
        rest (AES-GCM), while this model's own column is plaintext. The legacy
        column stays readable so a deployment that never migrates keeps
        working — nothing is deleted by this phase.
        """
        self.ensure_one()
        conn = connection if connection is not None else self._channel_connection()
        if conn:
            try:
                secret = conn._get_secret('provider_secret')
            except Exception:  # noqa: BLE001 — a broken token must not
                # silently accept events; fall through to the legacy column.
                _logger.exception('Could not read the channel webhook secret '
                                  'for voip config %s', self.id)
                secret = None
            if secret:
                return secret
        return self.sudo().webhook_secret

    @api.model
    def _resolve_channel_connection(self, account_id):
        """The Calls connection a webhook's ``account_id`` belongs to, or None.

        Company-agnostic on purpose (the provider addresses us by account id;
        which company owns it is exactly what we are resolving) and usable
        with NO ``voip.config`` row at all — a tenant who set Calls up through
        the Center alone must still be routable.
        """
        if not account_id or 'care.channel.connection' not in self.env:
            return None
        return self.env['care.channel.connection']._find_for_resource(
            'call', account_id) or None

    @api.model
    def _route_channel_connection(self, config, account_id):
        """The connection that may speak for ``account_id`` on the webhook.

        Company-agnostic resolution is correct in itself — the provider
        addresses us by account id, and whose company that is is exactly what
        we are working out — but it becomes a company-isolation break the
        moment two tenants can claim the same id. ``call`` is the one channel
        whose resource id a tenant TYPES, so that was reachable: typing a
        neighbour's account name made this lookup return YOUR connection for
        THEIR event, which skipped their legacy ``webhook_enabled`` off switch
        and pointed verification at the wrong secret.

        The Center now refuses the claim at source, so a collision cannot be
        created any more. This is the guard for databases where one already
        exists: when the resolved connection and the config that owns the
        account disagree about the company, the connection does not speak —
        the legacy config keeps its own switch and its own secret.
        """
        conn = self._resolve_channel_connection(account_id)
        if config and conn and conn.company_id != config.company_id:
            _logger.warning(
                'VoIP24h webhook: connection %s (company %s) and config %s '
                '(company %s) disagree about who owns this account; the '
                'connection does not speak for it',
                conn.id, conn.company_id.id, config.id, config.company_id.id)
            return None
        return conn

    @api.model
    def _sync_from_connection(self, connection, account_id=None):
        """A Center-configured Calls channel needs a config row to land in.

        ``process_call_event`` resolves ``voip.config`` by ``account_id`` and
        ``voip.call.log.voip_config_id`` is required, so without this a tenant
        would finish the stepper, see call events arrive, watch the card turn
        Connected — and get zero call logs. That is the "configured ≠
        connected" lie in reverse, so the row is created when it is missing.

        **What is deliberately NOT written is the point of this method.**
        ``api_key`` and ``api_secret`` stay EMPTY, and that emptiness is a
        safety mechanism, not an omission: ``_check_credentials`` refuses to
        build an API client without them, which is what keeps every unverified
        VoIP24h endpoint (``/auth/login``, ``/calls/history``, the recording
        download) unreachable from a connection this phase created. For the
        same reason ``state`` stays ``draft`` and ``auto_sync_enabled`` is
        forced off: the CDR cron ships ACTIVE on this deployment and selects
        on exactly those two fields, so a 'connected' row with auto-sync on
        would start calling an endpoint nobody has ever verified, every 15
        minutes.
        """
        connection.ensure_one()
        account_id = (account_id or connection.resource_external_id or '').strip()
        if not account_id:
            return False
        company = connection.company_id or self.env.company
        config = self.sudo().search([
            ('company_id', '=', company.id), ('active', '=', True)], limit=1)
        if not config:
            config = self.sudo().create({
                'name': 'Health19 Channel Center',
                'company_id': company.id,
                'account_id': account_id,
                'webhook_enabled': True,
                # See the docstring: every one of these is load-bearing.
                'state': 'draft',
                'auto_sync_enabled': False,
                'enable_call_functionality': False,
            })
            _logger.info('health_voip24h: created config %s for channel '
                         'connection %s', config.id, connection.id)
            return config
        vals = {'webhook_enabled': True}
        if config.account_id != account_id:
            vals['account_id'] = account_id
        config.sudo().write(vals)
        return config

    def _note_channel_event(self, event_type=None, connection=None):
        """Framework bookkeeping for an ALREADY-VERIFIED call event.

        Returns one of:

        * ``'ignored'`` — a connection owns this account and is not in an
          ingestable state (disabled, errored, still not_connected). The
          caller must drop the event.
        * ``'ok'`` — either no connection governs this account (legacy
          behaviour, unchanged) or one does and accepted it.

        The gate applies ONLY to a connection that actually owns the setup.
        A ``legacy`` row — which is all the migration creates for an existing
        deployment — observes traffic without gating it, because demoting a
        working phone system to "ignored" the day this module upgrades would
        be exactly the §5.66 lockout in a new costume.
        """
        self.ensure_one()
        conn = connection if connection is not None else self._channel_connection()
        if not conn:
            return 'ok'
        governed = conn.state not in ('legacy', 'not_connected')
        if governed and not conn._may_ingest():
            self.env['care.channel.audit']._log(
                'webhook_ignored', connection=conn,
                detail='call event while %s' % conn.state)
            return 'ignored'
        conn._note_inbound()
        return 'ok'

    @api.model
    def _migrate_legacy_connections(self):
        """One ``state='legacy'`` connection per active config. Idempotent.

        Nothing is deleted and nothing is invalidated: an existing VoIP setup
        keeps working exactly as it did until a human completes the new setup
        in the Channel Center. The three plaintext secrets are ENCRYPT-COPIED
        onto the connection; the legacy columns are left in place so the
        existing code keeps reading what it always read.
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
                ('channel', '=', 'call'),
                ('company_id', '=', company.id)], order='id desc', limit=1)
            if not conn:
                conn = Connection._internal().create({
                    'channel': 'call', 'company_id': company.id})
                conn = Connection.browse(conn.id)
                conn._transition('legacy', reason='migrated voip.config')
                created += 1
            else:
                existing_count += 1
            vals = {}
            if config.account_id and not conn.resource_external_id:
                vals['resource_external_id'] = config.account_id
            if config.name and not conn.resource_display_name:
                vals['resource_display_name'] = config.name
            # api_key / api_secret have no semantic slot of their own on the
            # connection, so they ride the two token columns. The mapping is
            # explicit here and nowhere else; nothing in CC-F ever SPENDS
            # them, because there is no verified endpoint to spend them at.
            pairs = (('webhook_secret', 'provider_secret_enc'),
                     ('api_key', 'access_token_enc'),
                     ('api_secret', 'refresh_token_enc'))
            for legacy_field, column in pairs:
                value = config.sudo()[legacy_field]
                if value and not conn.sudo()[column]:
                    vals[column] = channel_crypto.encrypt(self.env, value)
                    copied += 1
            if vals:
                conn.sudo()._internal().write(vals)
        _logger.info('health_voip24h CC-F migration: %s connection(s) created, '
                     '%s already present, %s secret(s) copied',
                     created, existing_count, copied)
        return {'created': created, 'existing': existing_count, 'copied': copied}
