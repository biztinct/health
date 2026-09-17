# -*- coding: utf-8 -*-

import hashlib
import hmac
import logging
import secrets
from contextlib import contextmanager
from datetime import timedelta

from odoo import models, fields, api, _
from odoo.exceptions import UserError

from ..services import voip_crypto
from ..services.voip24h_api import (
    DEFAULT_API_BASE_URL,
    default_token_expiry,
    parse_provider_datetime,
)

_logger = logging.getLogger(__name__)

# PostgreSQL advisory-lock namespace for per-config token renewal (§5.74: an
# advisory lock, never a row lock, because the token is written from the same
# transaction that holds the lock).
_AUTH_LOCK_CLASS = 0x0710  # arbitrary, stable, module-private

# How long before the validated expiry a token is considered due for renewal.
TOKEN_RENEW_MARGIN = timedelta(minutes=30)

# Receiver token entropy. 32 bytes = 256 bits, per the handover's floor.
RECEIVER_TOKEN_BYTES = 32


def verify_voip_signature(secret, raw_body, signature):
    """HMAC-SHA256 over the RAW request bytes, compared in constant time.

    Retained verbatim for the LEGACY ``/voip24h/webhook`` route only. No
    supplied VoIP24h document describes a signature header, so the v3
    receivers below do not require this — they authenticate by a high-entropy
    URL token (and, where the provider proves it delivers ``param.auth``, by a
    bearer value too). Fails CLOSED on a missing secret or signature.
    """
    if not secret or not signature:
        return False
    expected = hmac.new(secret.encode(), raw_body or b'',
                        hashlib.sha256).hexdigest()
    provided = signature.strip().lower()
    if provided.startswith('sha256='):
        provided = provided[len('sha256='):]
    return hmac.compare_digest(expected, provided)


def token_digest(value):
    """The stored form of a receiver token. Never store the token itself."""
    return hashlib.sha256((value or '').encode('utf-8')).hexdigest()


class VoIP24hConfig(models.Model):
    """VoIP24h connection, capabilities and callback identity.

    One row per company holds: the provider credentials, the token obtained
    from V1, the public receiver identities the provider calls back on, and the
    capability flags that decide what this deployment is allowed to do. Every
    provider-facing action defaults OFF; a valid token switches none of them
    on, because a token proves credentials and nothing else.
    """
    _name = 'voip.config'
    _description = 'VoIP24h Configuration'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'

    def init(self):
        # §5.1 — _sql_constraints are not materialized on Odoo 19.
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS voip_config_receiver_uidx
            ON voip_config (receiver_id)
            WHERE receiver_id IS NOT NULL
        """)

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------
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
    active = fields.Boolean(default=True, tracking=True)

    account_id = fields.Char(
        string='Phone System Account',
        required=True,
        tracking=True,
    )
    domain = fields.Char(string='VoIP24h Domain', default='voip24h.vn')
    api_base_url = fields.Char(
        string='API Base URL',
        default=DEFAULT_API_BASE_URL,
        required=True,
        help='Must be an https:// address on an allow-listed provider host.',
    )

    provider_timezone = fields.Selection(
        selection='_selection_provider_timezone',
        string='Phone System Time Zone',
        default='Asia/Ho_Chi_Minh',
        required=True,
        tracking=True,
        help='The time zone the phone system stamps its call times in. '
             'Call times arrive without a zone; reading them in the wrong one '
             'shifts every call in the history.',
    )

    # ------------------------------------------------------------------
    # Credentials and token (all group_system; never tracked)
    # ------------------------------------------------------------------
    api_key = fields.Char(string='API Key', groups='base.group_system')
    api_secret = fields.Char(string='API Secret', groups='base.group_system')

    access_token_enc = fields.Char(
        string='Access Token (encrypted)',
        groups='base.group_system',
        readonly=True,
    )
    token_expires_at = fields.Datetime(string='Token Expires At', readonly=True)
    token_obtained_at = fields.Datetime(string='Token Obtained At', readonly=True)
    token_expiry_quality = fields.Selection([
        ('none', 'No token yet'),
        ('ok', 'Read from the phone system'),
        ('missing', 'Phone system sent no expiry'),
        ('unparsable', 'Expiry could not be read'),
        ('no_timezone', 'Expiry has no usable time zone'),
    ], string='Expiry Source', default='none', readonly=True, tracking=True,
        help='Anything other than “Read from the phone system” means the '
             'renewal time is a guess and the connection is degraded.')
    token_longlive = fields.Boolean(string='Long-lived Token', readonly=True)
    auth_longlive = fields.Boolean(
        string='Request 7-day Token',
        default=False,
        tracking=True,
        help='Off requests the 1-day token, which is the safer default.',
    )
    auth_longlive_wire = fields.Selection([
        ('bool', 'JSON true/false (as documented)'),
        ('string', 'Text "true"/"false" (as the samples show)'),
    ], string='Token Lifetime Format', default='bool',
        help='The supplier documents a true/false value but every sample '
             'sends text. Switch this only if authentication is refused.')

    # Legacy plaintext columns. KEPT so an unmigrated deployment still reads
    # what it always read; the migration copies them into the encrypted store
    # and then blanks them. Nothing new ever writes these.
    access_token = fields.Char(string='Access Token (legacy)',
                               groups='base.group_system', readonly=True)
    token_type = fields.Char(string='Token Type (legacy)', readonly=True)
    webhook_secret = fields.Char(
        string='Legacy Webhook Secret', groups='base.group_system',
        help='Only used by the old /voip24h/webhook route.')
    webhook_enabled = fields.Boolean(
        string='Accept Legacy Call-backs', default=False, tracking=True,
        help='The pre-v3 signed call-back route. Leave off unless a producer '
             'is known to still post to it.')

    # ------------------------------------------------------------------
    # Callback receivers
    # ------------------------------------------------------------------
    receiver_id = fields.Char(
        string='Callback ID',
        readonly=True,
        copy=False,
        help='A random public identifier that appears in the callback '
             'address. It names this connection; it does not authorise '
             'anything on its own.',
    )
    cdr_token_digest = fields.Char(string='Completed-call Token Digest',
                                   groups='base.group_system', readonly=True,
                                   copy=False)
    cdr_token_enc = fields.Char(string='Completed-call Token (encrypted)',
                                groups='base.group_system', readonly=True,
                                copy=False)
    state_token_digest = fields.Char(string='Live-events Token Digest',
                                     groups='base.group_system', readonly=True,
                                     copy=False)
    state_token_enc = fields.Char(string='Live-events Token (encrypted)',
                                  groups='base.group_system', readonly=True,
                                  copy=False)
    # Rotation overlap: the previous digest stays valid until it expires, so a
    # rotation does not drop the events in flight.
    cdr_token_prev_digest = fields.Char(groups='base.group_system',
                                        readonly=True, copy=False)
    state_token_prev_digest = fields.Char(groups='base.group_system',
                                          readonly=True, copy=False)
    token_rotation_grace_until = fields.Datetime(readonly=True, copy=False)

    cdr_webhook_url = fields.Char(string='Completed-call Callback',
                                  compute='_compute_receiver_urls')
    state_webhook_url = fields.Char(string='Live-events Callback',
                                    compute='_compute_receiver_urls')

    callback_auth_profile = fields.Selection([
        ('url_token', 'Address token only'),
        ('url_token_param_auth', 'Address token + supplier auth value'),
        ('hmac', 'Signed request (not offered by this supplier)'),
    ], string='Callback Security', default='url_token', required=True,
        tracking=True,
        help='An address token proves possession of the address. It is not a '
             'signature: it does not prove the message body is untouched or '
             'that the request is fresh.')
    callback_param_auth = fields.Char(
        string='Supplier Auth Value', groups='base.group_system',
        help='The value sent back in the callback’s auth parameter, if the '
             'supplier proves it delivers one.')
    callback_source_ips = fields.Char(
        string='Allowed Source Addresses',
        help='Optional comma-separated list. Leave empty until the supplier '
             'confirms the addresses their system calls from.')

    # Subscription bookkeeping (what we last asked the provider for)
    subscription_url = fields.Char(string='Registered Callback Address',
                                   readonly=True)
    subscription_method = fields.Selection([('GET', 'GET'), ('POST', 'POST')],
                                           string='Registered Method',
                                           default='POST')
    subscription_active = fields.Boolean(string='Registration Active',
                                         readonly=True)
    subscription_registered_at = fields.Datetime(readonly=True)
    subscription_note = fields.Text(
        string='Registration Notes',
        help='Who owned the callback address before this one, and anything '
             'the supplier said. Never overwrite another system’s callback '
             'without recording what it was.')

    # ------------------------------------------------------------------
    # Capability flags — every provider-facing action is off by default
    # ------------------------------------------------------------------
    cdr_ingest_enabled = fields.Boolean(
        string='Accept Completed Calls', default=False, tracking=True)
    state_ingest_enabled = fields.Boolean(
        string='Accept Live Call Events', default=False, tracking=True)
    live_notifications_enabled = fields.Boolean(
        string='Show Live Notifications', default=False, tracking=True)
    webrtc_enabled = fields.Boolean(
        string='Allow Calling in the Browser', default=False, tracking=True)
    outbound_enabled = fields.Boolean(
        string='Allow Outgoing Calls', default=False, tracking=True)
    recording_access_enabled = fields.Boolean(
        string='Allow Recording Playback', default=False, tracking=True)
    history_sync_verified = fields.Boolean(
        string='Past-calls Interface Confirmed', default=False, tracking=True)
    rest_originate_verified = fields.Boolean(
        string='Server Dialling Confirmed', default=False, tracking=True)
    extension_sync_verified = fields.Boolean(
        string='Extension List Confirmed', default=False, tracking=True)

    # Legacy master switch, kept as a facade over the browser/outgoing
    # controls ONLY. It must never disable historical ingestion — a clinic
    # that turns calling off still needs its call history.
    enable_call_functionality = fields.Boolean(
        string='Enable Calling', default=False, tracking=True,
        help='Turns the browser phone and outgoing calls on or off. Call '
             'history, recordings and reporting are unaffected.')
    enable_outgoing_calls = fields.Boolean(string='Enable Outgoing Calls',
                                           default=True, tracking=True)
    enable_incoming_call_popups = fields.Boolean(
        string='Enable Incoming Call Alerts', default=True, tracking=True)

    # ------------------------------------------------------------------
    # WebRTC / SDK profile
    # ------------------------------------------------------------------
    sdk_library_url = fields.Char(
        string='Phone Library Address',
        default='https://sipgetway.voip24h.vn/public/js/voip24hlibrary.min.js')
    sdk_gateway_url = fields.Char(
        string='Phone Gateway Address',
        default='https://sipgetway.voip24h.vn/public/js/voip24hgateway.min.js')
    sdk_pinned_version = fields.Char(
        string='Phone Library Version',
        help='Recorded for audit. The supplier does not version these files '
             'in their address, so this is what was reviewed, not a promise '
             'about what is served.')
    sip_host_default = fields.Char(
        string='Default SIP Server',
        help='The address extensions register against, unless an extension '
             'overrides it.')

    lease_heartbeat_seconds = fields.Integer(
        string='Phone Heartbeat (seconds)', default=10)
    lease_expiry_seconds = fields.Integer(
        string='Phone Lease Expiry (seconds)', default=30)
    finalisation_grace_seconds = fields.Integer(
        string='Call Settle Time (seconds)', default=30,
        help='How long a call stays open after its last leg ends, waiting for '
             'the phone system’s final record.')
    correlation_window_seconds = fields.Integer(
        string='Matching Window (seconds)', default=15)
    callback_target_minutes = fields.Integer(
        string='Call-back Target (minutes)', default=0,
        help='Zero means no target is set. This is a clinic decision, not a '
             'contractual promise.')

    # ------------------------------------------------------------------
    # Retention
    # ------------------------------------------------------------------
    event_retention_days = fields.Integer(
        string='Keep Raw Events (days)', default=14)
    diagnostic_retention_days = fields.Integer(
        string='Keep Diagnostics (days)', default=90)
    recording_retention_days = fields.Integer(
        string='Keep Recordings (days)', default=0,
        help='Zero means keep indefinitely. Set this only after the clinic '
             'has agreed a retention policy.')
    allowed_recording_hosts = fields.Char(
        string='Allowed Recording Hosts',
        default='customer.voip24h.vn',
        help='Comma-separated. A recording address on any other host is '
             'refused.')

    # ------------------------------------------------------------------
    # Readiness — seven independent facts, never one green light
    # ------------------------------------------------------------------
    ready_api_at = fields.Datetime(string='API Authenticated', readonly=True)
    ready_cdr_at = fields.Datetime(string='Completed Calls Received',
                                   readonly=True)
    ready_state_at = fields.Datetime(string='Live Events Received',
                                     readonly=True)
    ready_recording_at = fields.Datetime(string='Recording Reached',
                                         readonly=True)
    ready_registration_at = fields.Datetime(string='Extension Registered',
                                            readonly=True)
    ready_inbound_call_at = fields.Datetime(string='Inbound Browser Call',
                                            readonly=True)
    ready_outbound_call_at = fields.Datetime(string='Outbound Browser Call',
                                             readonly=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('connected', 'Connected'),
        ('degraded', 'Degraded'),
        ('error', 'Connection Error'),
    ], string='Status', default='draft', tracking=True, required=True)
    error_message = fields.Text(string='Error Message', readonly=True)

    # ------------------------------------------------------------------
    # Legacy sync settings (the guessed-endpoint cron selects on these)
    # ------------------------------------------------------------------
    auto_sync_enabled = fields.Boolean(
        string='Auto Sync Past Calls', default=False, tracking=True,
        help='Needs a confirmed past-calls interface. Off by default.')
    sync_interval_minutes = fields.Integer(string='Sync Interval (Minutes)',
                                           default=15)
    sync_history_days = fields.Integer(string='Sync History (Days)', default=30)
    last_sync_date = fields.Datetime(string='Last Sync Date', readonly=True)
    total_calls_synced = fields.Integer(readonly=True, default=0)
    total_recordings_synced = fields.Integer(readonly=True, default=0)

    extension_ids = fields.One2many('voip.extension', 'voip_config_id',
                                    string='Extensions')
    extension_count = fields.Integer(compute='_compute_extension_count')

    pending_event_count = fields.Integer(compute='_compute_event_health')
    oldest_pending_event = fields.Datetime(compute='_compute_event_health')
    quarantined_event_count = fields.Integer(compute='_compute_event_health')

    # ==================================================================
    # Computes / selections
    # ==================================================================

    @api.model
    def _selection_provider_timezone(self):
        try:
            import pytz
            return [(tz, tz) for tz in pytz.common_timezones]
        except ImportError:  # pragma: no cover
            try:
                from zoneinfo import available_timezones
                return [(tz, tz) for tz in sorted(available_timezones())]
            except Exception:  # noqa: BLE001
                return [('Asia/Ho_Chi_Minh', 'Asia/Ho_Chi_Minh'),
                        ('UTC', 'UTC')]

    def _base_url(self):
        return (self.env['ir.config_parameter'].sudo()
                .get_param('web.base.url') or '').strip().rstrip('/')

    def _callback_base(self):
        """Where the phone supplier should be told to send call-backs.

        Normally this system's own address. On a platform that serves several
        clinics from one machine, the platform writes its OWN address into
        ``voip24h.callback_base`` on every clinic it serves, so the supplier is
        given ONE address for everybody and the platform passes each call on to
        the clinic it belongs to.

        The receiver id and the token in the address are the same either way:
        the platform routes on the receiver id and forwards the token
        untouched, so the check this system does on arrival is the same check
        whichever address the supplier dialled. Nothing else in this module
        needs to know which of the two is in play.
        """
        relayed = (self.env['ir.config_parameter'].sudo()
                   .get_param('voip24h.callback_base') or '').strip().rstrip('/')
        # https only, and never a bare hostname: this string is published to a
        # third party and pasted into their dashboard. A setting that is not a
        # usable address is ignored rather than published.
        if relayed.startswith('https://') and len(relayed) > len('https://'):
            return relayed
        if relayed:
            _logger.warning("VoIP24h: the platform call-back address %r is not "
                            "an https address — using this system's own",
                            relayed)
        return self._base_url()

    @api.depends('receiver_id')
    def _compute_receiver_urls(self):
        base = self._callback_base()
        is_admin = self.env.user.has_group('base.group_system')
        for config in self:
            if not config.receiver_id:
                config.cdr_webhook_url = False
                config.state_webhook_url = False
                continue
            if not is_admin:
                # The address IS the credential. Anybody who can read it can
                # inject call events, so it is administrator-only — a masked
                # form is what everyone else sees.
                masked = '%s/voip24h/v3/cdr/%s/••••••' % (base, config.receiver_id)
                config.cdr_webhook_url = masked
                config.state_webhook_url = masked.replace('/cdr/', '/events/')
                continue
            cdr = config.sudo()._voip_secret_read('cdr_token')
            state = config.sudo()._voip_secret_read('state_token')
            config.cdr_webhook_url = '%s/voip24h/v3/cdr/%s/%s' % (
                base, config.receiver_id, cdr or '<token-not-stored>')
            config.state_webhook_url = '%s/voip24h/v3/events/%s/%s' % (
                base, config.receiver_id, state or '<token-not-stored>')

    def _compute_extension_count(self):
        counts = dict(self.env['voip.extension']._read_group(
            [('voip_config_id', 'in', self.ids)],
            groupby=['voip_config_id'],
            aggregates=['__count'],
        ))
        for config in self:
            config.extension_count = counts.get(config, 0)

    def _compute_event_health(self):
        Event = self.env['voip.call.event'].sudo()
        for config in self:
            pending = Event.search(
                [('voip_config_id', '=', config.id),
                 ('processing_state', 'in', ('pending', 'retry'))],
                order='received_at asc', limit=1)
            config.pending_event_count = Event.search_count(
                [('voip_config_id', '=', config.id),
                 ('processing_state', 'in', ('pending', 'retry'))])
            config.oldest_pending_event = pending.received_at or False
            config.quarantined_event_count = Event.search_count(
                [('voip_config_id', '=', config.id),
                 ('processing_state', '=', 'quarantined')])

    # ==================================================================
    # Secret store
    # ==================================================================
    #
    # ``_voip_secret_backend`` is the single overridable seam. Core answers
    # with its own AES-GCM cipher (services/voip_crypto.py); the Care Command
    # bridge may answer with the channel connection store where a Channel
    # Center owns the setup. Both are encrypted at rest. There is no plaintext
    # branch anywhere in this pair of methods.

    _SECRET_COLUMNS = {
        'access_token': 'access_token_enc',
        'cdr_token': 'cdr_token_enc',
        'state_token': 'state_token_enc',
        'callback_param_auth': 'callback_param_auth',
    }

    def _voip_secret_backend(self):
        """Return an object with ``encrypt(env, v)`` / ``decrypt(env, v)``."""
        return voip_crypto

    def _voip_secret_read(self, name):
        """Decrypt and return the named secret, or None.

        Fails CLOSED and LOUDLY-IN-THE-LOG: an undecryptable secret returns
        None (so the caller refuses to act) rather than a mangled value that
        would be sent to a provider.
        """
        self.ensure_one()
        column = self._SECRET_COLUMNS.get(name)
        if not column:
            raise ValueError('unknown telephony secret %r' % name)
        raw = self.sudo()[column]
        if not raw:
            return None
        try:
            return self._voip_secret_backend().decrypt(self.env, raw)
        except Exception:  # noqa: BLE001 — never leak, never guess
            _logger.exception('Telephony secret %s unreadable on config %s',
                              name, self.id)
            return None

    def _voip_secret_write(self, name, value):
        self.ensure_one()
        column = self._SECRET_COLUMNS.get(name)
        if not column:
            raise ValueError('unknown telephony secret %r' % name)
        enc = self._voip_secret_backend().encrypt(self.env, value) if value else False
        self.sudo().write({column: enc})

    # ==================================================================
    # Credentials and token lifecycle
    # ==================================================================

    def _check_credentials(self):
        self.ensure_one()
        config_sudo = self.sudo()
        if not config_sudo.api_key or not config_sudo.api_secret:
            raise UserError(_(
                'The phone system credentials have not been entered yet.'))

    def _get_api_client(self):
        from ..services.voip24h_api import VoIP24hAPI
        self.ensure_one()
        self._check_credentials()
        return VoIP24hAPI(self.sudo())

    @contextmanager
    def _auth_single_flight(self):
        """Advisory transaction lock around token renewal (§5.74).

        Yields True when this transaction owns the renewal, False when another
        one does. Never blocks: a caller that does not get the lock re-reads
        rather than queueing behind a provider round trip.
        """
        self.ensure_one()
        self.env.cr.execute('SELECT pg_try_advisory_xact_lock(%s, %s)',
                            (_AUTH_LOCK_CLASS, self.id))
        acquired = bool(self.env.cr.fetchone()[0])
        yield acquired
        # Advisory *xact* locks release on commit/rollback — nothing to undo.

    def _token_is_usable(self):
        self.ensure_one()
        me = self.sudo()
        if not me.access_token_enc:
            return False
        if not me.token_expires_at:
            return False
        return fields.Datetime.now() < me.token_expires_at - TOKEN_RENEW_MARGIN

    def _parse_provider_expiry(self, value):
        self.ensure_one()
        return parse_provider_datetime(value, self.provider_timezone)

    def _store_token(self, token, expires_at, expiry_quality, longlive,
                     created_at_raw=''):
        self.ensure_one()
        me = self.sudo()
        me._voip_secret_write('access_token', token)
        vals = {
            'token_obtained_at': fields.Datetime.now(),
            'token_expiry_quality': expiry_quality,
            'token_longlive': longlive,
            'ready_api_at': fields.Datetime.now(),
            'error_message': False,
            # A token that is stored is not a plaintext token any more.
            'access_token': False,
            'token_type': False,
        }
        if expires_at:
            vals['token_expires_at'] = expires_at
            vals['state'] = 'connected'
        else:
            # Documented lifetime as a SCHEDULING hint only, and the state
            # says degraded so the operator can see that the renewal time is
            # a guess rather than a fact.
            vals['token_expires_at'] = default_token_expiry(longlive)
            vals['state'] = 'degraded'
        me.write(vals)
        if created_at_raw:
            _logger.debug('VoIP24h token issued at %s (config %s)',
                          created_at_raw, self.id)

    def _note_auth_failure(self, code, message):
        self.ensure_one()
        self.sudo().write({
            'state': 'error',
            'error_message': '%s: %s' % (code, message or ''),
        })

    def _ensure_token(self):
        """Return a usable token, renewing if it is close to expiry."""
        self.ensure_one()
        if self._token_is_usable():
            return self.sudo()._voip_secret_read('access_token')
        self._get_api_client().authenticate()
        return self.sudo()._voip_secret_read('access_token')

    # ==================================================================
    # Receiver identity
    # ==================================================================

    def _ensure_receiver(self):
        """Create the public receiver id and its two tokens if absent."""
        self.ensure_one()
        me = self.sudo()
        if not me.receiver_id:
            me.write({'receiver_id': secrets.token_urlsafe(12)})
        for name, digest_field in (('cdr_token', 'cdr_token_digest'),
                                   ('state_token', 'state_token_digest')):
            if not me[digest_field]:
                raw = secrets.token_urlsafe(RECEIVER_TOKEN_BYTES)
                me._voip_secret_write(name, raw)
                me.write({digest_field: token_digest(raw)})
        return me.receiver_id

    def action_rotate_receiver_tokens(self):
        """New callback tokens, with a bounded overlap so nothing is dropped.

        The previous digests stay valid for the grace window, which is what
        makes rotation safe while events are in flight. Re-registering the new
        address with the provider is a separate, deliberate step.
        """
        self.ensure_one()
        me = self.sudo()
        me.write({
            'cdr_token_prev_digest': me.cdr_token_digest,
            'state_token_prev_digest': me.state_token_digest,
            'token_rotation_grace_until': fields.Datetime.now() + timedelta(hours=24),
            'cdr_token_digest': False,
            'state_token_digest': False,
        })
        me._ensure_receiver()
        me.message_post(body=_(
            'Call-back addresses were renewed. The previous addresses keep '
            'working for 24 hours. Register the new completed-call address '
            'with the supplier before then.'))
        return self._notify(_('Call-back addresses renewed'), _(
            'Register the new address with the supplier within 24 hours.'))

    def _verify_receiver_token(self, feed, supplied):
        """Constant-time check of a supplied callback token for one feed."""
        self.ensure_one()
        me = self.sudo()
        if not supplied:
            return False
        digest = token_digest(supplied)
        current = me.cdr_token_digest if feed == 'cdr' else me.state_token_digest
        if current and hmac.compare_digest(digest, current):
            return True
        grace = me.token_rotation_grace_until
        if grace and fields.Datetime.now() <= grace:
            previous = (me.cdr_token_prev_digest if feed == 'cdr'
                        else me.state_token_prev_digest)
            if previous and hmac.compare_digest(digest, previous):
                return True
        return False

    @api.model
    def _resolve_receiver(self, receiver_id, feed, supplied_token):
        """Find the config a callback belongs to, or an empty recordset.

        Resolution is by the receiver id ALONE — never by a query parameter,
        never by ``account_id``, never by an extension. The database was
        already chosen by the tenant hostname and dbfilter before this method
        runs; nothing in the request body may re-select a tenant.
        """
        if not receiver_id or not supplied_token:
            return self.browse()
        config = self.sudo().with_context(active_test=False).search(
            [('receiver_id', '=', receiver_id)], limit=1)
        if not config:
            return self.browse()
        if not config._verify_receiver_token(feed, supplied_token):
            return self.browse()
        return config

    # ==================================================================
    # Actions
    # ==================================================================

    def _notify(self, title, message, kind='success', sticky=False):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': title, 'message': message, 'type': kind,
                       'sticky': sticky},
        }

    def action_test_connection(self):
        """Authenticate. Proves the credentials — and says so, precisely."""
        self.ensure_one()
        try:
            result = self._get_api_client().test_connection()
        except UserError as exc:
            self.sudo().write({'state': 'error', 'error_message': str(exc)})
            return self._notify(_('Could not connect'), str(exc), 'danger', True)
        except Exception as exc:  # noqa: BLE001
            _logger.error('VoIP24h connection test failed: %s', exc, exc_info=True)
            self.sudo().write({'state': 'error', 'error_message': str(exc)})
            return self._notify(_('Could not connect'), _(
                'Something went wrong reaching the phone system.'),
                'danger', True)
        if result.get('expiry_quality') != 'ok':
            return self._notify(_('Connected, with a warning'), _(
                'The credentials were accepted, but the phone system did not '
                'give a usable expiry time for the access it granted. The '
                'connection will still work; renewals are scheduled on the '
                'documented lifetime instead.'), 'warning', True)
        return self._notify(_('Credentials accepted'), _(
            'The phone system accepted these credentials. This does not yet '
            'prove that call records arrive or that a browser can ring.'))

    def action_register_cdr_webhook(self):
        """Register the completed-call callback (V2)."""
        self.ensure_one()
        self._ensure_receiver()
        me = self.sudo()
        if me.subscription_url and me.subscription_url != me.cdr_webhook_url \
                and not me.subscription_note:
            raise UserError(_(
                'A different call-back address is already registered with the '
                'supplier. Record what it was in Registration Notes first so '
                'it can be put back — replacing another system’s call-back '
                'silently would stop their call records arriving.'))
        auth_value = ''
        if me.callback_auth_profile == 'url_token_param_auth':
            auth_value = me._voip_secret_read('callback_param_auth') or ''
            if not auth_value:
                raise UserError(_(
                    'This connection is set to use a supplier auth value, but '
                    'none has been entered.'))
        api = self._get_api_client()
        api.register_call_log_webhook(
            url=me.cdr_webhook_url,
            method=me.subscription_method or 'POST',
            active=True,
            auth_token=auth_value,
        )
        me.write({
            'subscription_url': me.cdr_webhook_url,
            'subscription_active': True,
            'subscription_registered_at': fields.Datetime.now(),
        })
        me.message_post(body=_(
            'The completed-call call-back was registered with the supplier.'))
        return self._notify(_('Call-back registered'), _(
            'The supplier accepted the registration. Call records will only '
            'confirm it once a real call arrives.'))

    def action_delete_cdr_webhook(self):
        self.ensure_one()
        me = self.sudo()
        if not me.subscription_url:
            raise UserError(_('No call-back address is registered.'))
        self._get_api_client().delete_call_log_webhook(me.subscription_url)
        me.write({'subscription_active': False})
        me.message_post(body=_('The completed-call call-back was removed.'))
        return self._notify(_('Call-back removed'), _(
            'The supplier will stop sending completed-call records.'))

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

    def action_view_events(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Phone System Messages'),
            'res_model': 'voip.call.event',
            'view_mode': 'list,form',
            'domain': [('voip_config_id', '=', self.id)],
        }

    def action_sync_call_history(self):
        """Kept so the button and the wizard have an owner — it now refuses."""
        self.ensure_one()
        if not self.history_sync_verified:
            raise UserError(_(
                'Downloading past calls needs a part of the phone system’s '
                'interface the supplier has not confirmed for this account. '
                'Completed calls still arrive by call-back as they happen.'))
        from ..services.cdr_sync import sync_call_history
        result = sync_call_history(self.sudo())
        return self._notify(_('Sync completed'), _(
            '%(created)s new calls, %(updated)s updated, %(errors)s errors.',
            created=result['created'], updated=result['updated'],
            errors=result['errors']))

    def action_sync_extensions(self):
        self.ensure_one()
        if not self.extension_sync_verified:
            raise UserError(_(
                'Reading the extension list needs a part of the phone '
                'system’s interface the supplier has not confirmed for this '
                'account. Extensions can be added by hand in the meantime.'))
        raise UserError(_(
            'The extension-list interface is marked confirmed but no captured '
            'contract has been implemented for it yet.'))

    # ==================================================================
    # Gates
    # ==================================================================

    @api.model
    def get_active_config(self):
        return self.search([('company_id', '=', self.env.company.id)], limit=1)

    def is_calling_enabled(self):
        self.ensure_one()
        return bool(self.enable_call_functionality and self.webrtc_enabled)

    def can_make_outgoing_calls(self):
        self.ensure_one()
        return bool(self.enable_call_functionality
                    and self.enable_outgoing_calls
                    and self.outbound_enabled)

    def can_show_incoming_popups(self):
        self.ensure_one()
        return bool(self.enable_incoming_call_popups
                    and (self.live_notifications_enabled or self.webrtc_enabled))

    def _get_user_extension(self, user=None):
        self.ensure_one()
        user = user or self.env.user
        return self.env['voip.extension'].sudo().search([
            ('voip_config_id', '=', self.id),
            ('user_id', '=', user.id),
        ], limit=1)

    def initiate_user_call(self, phone_number, extension=None):
        """Server-originated dial. Refuses until that contract is confirmed.

        The browser phone is the supported path (see ``controllers/phone.py``);
        this method exists because a desk-phone click-to-dial is a real ask,
        and the honest answer today is that the supplier has not given us an
        originate contract.
        """
        self.ensure_one()
        if not self.rest_originate_verified:
            raise UserError(_(
                'Starting a call from the server is not available for this '
                'account. Use the phone panel in the browser instead.'))
        if not self.can_make_outgoing_calls():
            raise UserError(_('Outgoing calls are switched off.'))
        extension = extension or self._get_user_extension()
        if not extension:
            raise UserError(_('You do not have an extension assigned.'))
        return self._get_api_client().initiate_call(
            extension.extension_number, phone_number)

    # ==================================================================
    # Crons
    # ==================================================================

    @api.model
    def cron_renew_tokens(self):
        """Renew tokens shortly before validated expiry."""
        horizon = fields.Datetime.now() + TOKEN_RENEW_MARGIN
        configs = self.sudo().search([
            ('active', '=', True),
            ('access_token_enc', '!=', False),
            ('token_expires_at', '<=', horizon),
        ])
        for config in configs:
            try:
                with self.env.cr.savepoint():
                    config._get_api_client().authenticate()
            except Exception as exc:  # noqa: BLE001
                _logger.warning('Token renewal failed for config %s: %s',
                                config.id, exc)

    @api.model
    def cron_sync_call_history(self):
        """Past-call polling. Selects on the CONFIRMED flag as well.

        Ledger §5.81: this cron ships active, and the only thing that ever
        kept it harmless was that it found no rows. Now it also refuses any
        config whose past-calls interface has not been confirmed, so a newly
        valid token cannot wake an unevidenced endpoint.
        """
        configs = self.sudo().search([
            ('auto_sync_enabled', '=', True),
            ('history_sync_verified', '=', True),
            ('state', 'in', ('connected', 'degraded')),
        ])
        if not configs:
            return
        from ..services.cdr_sync import sync_call_history
        now = fields.Datetime.now()
        for config in configs:
            interval = max(config.sync_interval_minutes or 15, 1)
            if config.last_sync_date and \
                    (now - config.last_sync_date).total_seconds() < interval * 60:
                continue
            try:
                sync_call_history(config)
                self.env.cr.commit()
            except Exception as exc:  # noqa: BLE001
                _logger.error('Cron sync failed for %s: %s', config.name, exc,
                              exc_info=True)
                self.env.cr.rollback()
                config.write({'state': 'error', 'error_message': str(exc)})
                self.env.cr.commit()

    @api.model
    def cron_apply_retention(self):
        """Delete raw event payloads past their retention window."""
        Event = self.env['voip.call.event'].sudo()
        for config in self.sudo().search([('active', '=', True)]):
            days = config.event_retention_days or 0
            if days <= 0:
                continue
            cutoff = fields.Datetime.now() - timedelta(days=days)
            stale = Event.search([
                ('voip_config_id', '=', config.id),
                ('received_at', '<', cutoff),
                ('payload_raw', '!=', False),
            ], limit=2000)
            if stale:
                stale.write({'payload_raw': False, 'payload_redacted': False})
                _logger.info('Cleared raw payloads on %s events for config %s',
                             len(stale), config.id)

    # ==================================================================
    # Legacy webhook signature (old route only)
    # ==================================================================

    def _verify_webhook_signature(self, raw_body, signature, connection=None):
        self.ensure_one()
        secret = self._effective_webhook_secret(connection=connection)
        if not secret:
            _logger.warning(
                'VoIP24h legacy webhook rejected for %s: no secret configured',
                self.name)
            return False
        return verify_voip_signature(secret, raw_body, signature)

    # ==================================================================
    # Channel Center facade (unchanged contract; see CC-F)
    # ==================================================================

    def _channel_connection(self):
        self.ensure_one()
        if 'care.channel.connection' not in self.env:
            return None
        Conn = self.env['care.channel.connection'].sudo()
        company_id = (self.company_id or self.env.company).id
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
            return Conn.browse()
        return fallback

    def _effective_webhook_secret(self, connection=None):
        self.ensure_one()
        conn = connection if connection is not None else self._channel_connection()
        if conn:
            try:
                secret = conn._get_secret('provider_secret')
            except Exception:  # noqa: BLE001
                _logger.exception('Could not read the channel webhook secret '
                                  'for voip config %s', self.id)
                secret = None
            if secret:
                return secret
        return self.sudo().webhook_secret

    @api.model
    def _resolve_channel_connection(self, account_id):
        if not account_id or 'care.channel.connection' not in self.env:
            return None
        return self.env['care.channel.connection']._find_for_resource(
            'call', account_id) or None

    @api.model
    def _route_channel_connection(self, config, account_id):
        conn = self._resolve_channel_connection(account_id)
        if config and conn and conn.company_id != config.company_id:
            _logger.warning(
                'VoIP24h webhook: connection %s and config %s disagree about '
                'who owns this account; the connection does not speak for it',
                conn.id, config.id)
            return None
        return conn

    @api.model
    def _sync_from_connection(self, connection, account_id=None):
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
                # §5.81: enumerate every field the crons select on, explicitly.
                'state': 'draft',
                'auto_sync_enabled': False,
                'history_sync_verified': False,
                'enable_call_functionality': False,
                'cdr_ingest_enabled': False,
                'state_ingest_enabled': False,
                'webrtc_enabled': False,
                'outbound_enabled': False,
            })
            _logger.info('health_voip24h: created config %s for channel '
                         'connection %s', config.id, connection.id)
            return config
        vals = {}
        if config.account_id != account_id:
            vals['account_id'] = account_id
        if vals:
            config.sudo().write(vals)
        return config

    def _note_channel_event(self, event_type=None, connection=None):
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
        """One ``state='legacy'`` connection per active config. Idempotent."""
        if 'care.channel.connection' not in self.env:
            return {'created': 0, 'existing': 0, 'copied': 0}
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

    # ==================================================================
    # The Channel Center's Calls card (CC-F2)
    # ==================================================================
    # A SOFT reference in both directions: there is no manifest dependency
    # edge either way (ledger §5.71), so the Channel Center probes
    # ``'voip.config' in env`` and calls these, and this module never imports
    # anything of theirs. Everything the card needs is here rather than there,
    # because the supplier's contract is this module's business.
    #
    # WHAT THE SUPPLIER'S DOCUMENTS ACTUALLY SAY, since the card used to claim
    # otherwise and an operator followed it:
    #
    #  * Authorization.docx — an API key and an API secret are exchanged for a
    #    token. That is the only credential a customer holds.
    #  * Webhook.docx — the customer REGISTERS a call-back address themselves
    #    (`POST /v3/webhook-call-log/`, Bearer token), or gives it to the
    #    supplier's staff. Either way the address is ours to mint.
    #  * The delivery carries msgid, id, calldate, callid, play, eplay,
    #    download, did, src, dst, status, note, disposition, billsec, duration
    #    and type — and NOTHING that says which customer it belongs to. There
    #    is no account identifier in an event, no signature, and no signing
    #    header. Identity is the receiver id in the address we minted, which is
    #    why the card no longer asks for an account name or a secret.

    @api.model
    def _center_phone_config(self, company=None, create=False):
        """This company's phone connection, optionally creating it."""
        company = company or self.env.company
        config = self.sudo().search(
            [('company_id', '=', company.id), ('active', '=', True)], limit=1)
        if config or not create:
            return config
        config = self.sudo().create({
            'name': company.name or 'Phone system',
            'company_id': company.id,
            # `account_id` is required and is the string the Channel Center
            # connection is linked by (`_channel_connection`). It is NOT sent
            # by the supplier and must never be asked for as though it were:
            # the receiver id is stable, unique and already ours.
            'account_id': 'CC-%s' % secrets.token_urlsafe(9),
            'state': 'draft',
            'auto_sync_enabled': False,
            'history_sync_verified': False,
            'enable_call_functionality': False,
            'cdr_ingest_enabled': True,
            'state_ingest_enabled': True,
        })
        config._ensure_receiver()
        _logger.info('health_voip24h: Channel Center created config %s for '
                     'company %s', config.id, company.id)
        return config

    @api.model
    def _center_phone_state(self, company=None):
        """One read with everything the Calls card shows. No credentials."""
        config = self._center_phone_config(company)
        if not config:
            return {'available': True, 'configured': False}
        me = config.sudo()
        return {
            'available': True,
            'configured': True,
            'config_id': me.id,
            'account_key': me.account_id or '',
            'has_credentials': bool(me.api_key and me.api_secret),
            # Evidence, not a claim: `state` is written by the authentication
            # itself — 'connected' when the supplier also gave a usable expiry,
            # 'degraded' when it accepted the credentials but the expiry had to
            # be guessed from the documented lifetime, 'error' when it refused.
            # Degraded still means ACCEPTED, so both count. A stored key nobody
            # has ever used is 'draft', and is not "working".
            'credentials_ok': me.state in ('connected', 'degraded'),
            'credentials_error': me.error_message or '',
            'callback_ready': bool(me.receiver_id),
            # Masked for anybody but a system administrator — the address IS
            # the credential (see `_compute_receiver_urls`).
            'callback_url': config.cdr_webhook_url or '',
            'relayed': bool(self.env['ir.config_parameter'].sudo().get_param(
                'voip24h.callback_base')),
            # Whether call records are being taken at all. False means paused:
            # deliveries are acknowledged and dropped, nothing is stored.
            'receiving': bool(me.cdr_ingest_enabled or me.state_ingest_enabled),
            'registered': bool(me.subscription_active),
            'registered_url': me.subscription_url or '',
            'registered_at': me.subscription_registered_at and
            fields.Datetime.to_string(me.subscription_registered_at) or '',
            'events_seen': self.env['voip.call.event'].sudo().search_count(
                [('voip_config_id', '=', me.id)]),
        }

    @api.model
    def _center_phone_save_credentials(self, api_key, api_secret,
                                       company=None):
        """Store the key and secret ONLY if the supplier accepts them.

        A rejected credential raises, and an Odoo request that raises rolls its
        whole transaction back — so nothing is kept. That is deliberate: a
        stored key that has never worked is exactly the state that makes a card
        read "connected" while no call will ever arrive.
        """
        api_key = (api_key or '').strip()
        api_secret = (api_secret or '').strip()
        if not api_key or not api_secret:
            raise UserError(_(
                'Enter both the API key and the API secret from your phone '
                'system provider.'))
        config = self._center_phone_config(company, create=True)
        config.sudo().write({'api_key': api_key, 'api_secret': api_secret})
        # Proves the pair against `POST /v3/authentication`. Raises UserError
        # with the supplier's own reason when they refuse it.
        config._get_api_client().test_connection()
        config._ensure_receiver()
        return self._center_phone_state(company)

    @api.model
    def _center_phone_register(self, company=None):
        """Mint the address if needed and register it with the supplier."""
        config = self._center_phone_config(company)
        if not config:
            raise UserError(_('Enter your phone system credentials first.'))
        config._ensure_receiver()
        config.action_register_cdr_webhook()
        return self._center_phone_state(company)

    @api.model
    def _center_phone_set_receiving(self, on, company=None):
        """Pause or resume taking call records. Returns True if it moved.

        WHAT PAUSE DOES, AND WHAT IT DELIBERATELY DOES NOT DO.

        It switches the two ingest flags off. An authenticated delivery then
        gets ``200 {"status": "ignored"}`` — acknowledged, audited, and NOT
        stored: no event row, no call record, no call back, no notification.

        It does NOT unregister the call-back with the supplier, and it does NOT
        archive the connection:

        * unregistering would mean re-registering on resume, over an API that
          can refuse, so a pause could strand a clinic with no way back;
        * archiving would drop the platform relay's route (it reads ACTIVE
          configs only), and the supplier would start getting 403s at the
          platform for a clinic that is merely paused rather than gone. A
          polite 200-and-ignore is the right answer to a partner who is doing
          nothing wrong.

        So resume is instant and needs nothing from the supplier. The cost is
        that records which arrive while paused are lost rather than queued —
        which is what "paused" should mean, and is said in those words on the
        screen.
        """
        config = self._center_phone_config(company)
        if not config:
            return False
        me = config.sudo()
        wanted = bool(on)
        if me.cdr_ingest_enabled == wanted and me.state_ingest_enabled == wanted:
            return False
        me.write({'cdr_ingest_enabled': wanted,
                  'state_ingest_enabled': wanted})
        me.message_post(body=_('Taking call records was switched %s.',
                               _('on') if wanted else _('off')))
        _logger.info('health_voip24h: receiving switched %s for config %s',
                     'on' if wanted else 'off', me.id)
        return True

    # ==================================================================
    # Frontend-safe view of this config
    # ==================================================================

    def _client_profile(self, user=None):
        """What the browser is allowed to know. No credentials, ever."""
        self.ensure_one()
        user = user or self.env.user
        extension = self._get_user_extension(user)
        return {
            'config_id': self.id,
            'company_id': self.company_id.id,
            'calling_enabled': self.is_calling_enabled(),
            'outgoing_enabled': self.can_make_outgoing_calls(),
            'alerts_enabled': self.can_show_incoming_popups(),
            'webrtc_enabled': bool(self.webrtc_enabled),
            'recording_enabled': bool(self.recording_access_enabled),
            'has_extension': bool(extension),
            'extension_number': extension.extension_number if extension else False,
            'browser_phone_allowed': bool(extension and extension.browser_enabled
                                          and self.webrtc_enabled),
            'heartbeat_seconds': self.lease_heartbeat_seconds or 10,
            'lease_expiry_seconds': self.lease_expiry_seconds or 30,
            'transfer_enabled': bool(extension and extension.allow_transfer),
            'dtmf_enabled': bool(extension and extension.allow_dtmf),
        }
