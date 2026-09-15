# -*- coding: utf-8 -*-
"""``google.ads.oauth.session`` — one Google sign-in attempt.

Cloned from ``care.channel.oauth.session`` (health_care_command_channels),
kernel for kernel: the random state is returned to the browser exactly ONCE
and stored hashed, PKCE S256 is mandatory and its verifier is encrypted at
rest, the session expires in ten minutes, and :meth:`_consume` burns it with a
single atomic ``UPDATE … RETURNING`` so two workers racing the same callback
cannot both proceed.

Unknown, already-used, expired and wrong-provider states are all
indistinguishable to the caller — the callback route is public, so anything
that told them apart would be an oracle for guessing a valid state.

The callback LOGIC lives here rather than in a controller so a TransactionCase
can cover it end to end (ledger §5.32: this module ships zero HttpCase). The
HTTP shell is the existing ``/channel_hub/oauth/callback/<provider>`` route,
reached through the ``care.channel.oauth.session._handle_callback`` override
in ``care_channel_oauth_session.py`` — no edit to the channels module.
"""
import base64
import hashlib
import logging
import secrets
from datetime import timedelta

from odoo import _, api, fields, models

from odoo.addons.health_care_command_channels.services import channel_crypto
from odoo.addons.health_care_command_channels.services.redact import redact

from ..services import google_ads_client as gads

_logger = logging.getLogger(__name__)

SESSION_TTL_MINUTES = 10
PURGE_AFTER_HOURS = 24

OUTCOMES = [
    ('pending', 'Pending'),
    ('ok', 'Completed'),
    ('denied', 'Denied by user'),
    ('expired', 'Expired'),
    ('error', 'Error'),
]

CHANNEL_KEY = 'google_ads'


def _s256(verifier):
    """RFC 7636 code_challenge: base64url(sha256(verifier)), no padding."""
    digest = hashlib.sha256(verifier.encode('ascii')).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b'=').decode('ascii')


class GoogleAdsOauthSession(models.Model):
    _name = 'google.ads.oauth.session'
    _description = 'Google Ads Sign-in Session'
    _order = 'id desc'

    account_id = fields.Many2one(
        'google.ads.account', required=True, index=True, ondelete='cascade')
    company_id = fields.Many2one('res.company', required=True, index=True)
    user_id = fields.Many2one('res.users', required=True, index=True)
    state_hash = fields.Char(required=True, index=True)
    pkce_verifier_enc = fields.Text(groups='base.group_system')
    redirect_target = fields.Char()
    expires_at = fields.Datetime(required=True)
    used_at = fields.Datetime()
    outcome = fields.Selection(OUTCOMES, default='pending', required=True)
    detail_redacted = fields.Char(string='Detail')

    def init(self):
        init = getattr(super(), 'init', None)
        if callable(init):
            init()
        # §5.1 — the hash lookup in _consume() depends on this being unique.
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
                google_ads_oauth_session_state_hash_uniq
            ON google_ads_oauth_session (state_hash)
        """)

    # ------------------------------------------------------------------
    # Create / consume
    # ------------------------------------------------------------------
    @api.model
    def _mint_state(self):
        """The random string that identifies one sign-in attempt.

        OPAQUE to everything but :meth:`_consume`, which hashes whatever comes
        back and compares it to the hash of whatever went out. Never parsed,
        never logged, never stored in the clear.
        """
        return secrets.token_urlsafe(32)

    @api.model
    def create_for(self, account):
        """Open a sign-in attempt.

        Returns ``{'session_id', 'state', 'code_verifier', 'code_challenge',
        'code_challenge_method'}`` — the ONLY time the raw state or the PKCE
        verifier leaves the server.
        """
        account.ensure_one()
        state = self._mint_state()
        verifier = secrets.token_urlsafe(64)
        session = self.sudo().create({
            'account_id': account.id,
            'company_id': account.company_id.id,
            'user_id': self.env.uid,
            'state_hash': hashlib.sha256(state.encode('utf-8')).hexdigest(),
            'pkce_verifier_enc': channel_crypto.encrypt(self.env, verifier),
            'expires_at': fields.Datetime.now() + timedelta(
                minutes=SESSION_TTL_MINUTES),
        })
        return {
            'session_id': session.id,
            'state': state,
            'code_verifier': verifier,
            'code_challenge': _s256(verifier),
            'code_challenge_method': 'S256',
        }

    @api.model
    def _consume(self, state):
        """Look a state up by hash and burn it. Returns the session or None.

        Unknown, already-used and expired all return ``None``. ``used_at`` is
        stamped in the same transaction, BEFORE any provider HTTP, so a crash
        mid-exchange still leaves the state single-use.
        """
        if not state or not isinstance(state, str):
            return None
        digest = hashlib.sha256(state.encode('utf-8')).hexdigest()
        # ONE atomic statement: a read-then-write pair lets two workers racing
        # the same callback both observe `used_at IS NULL`. Flush first /
        # invalidate after — raw SQL and the ORM cache otherwise disagree
        # about this row (ledger §5.9).
        self.env.flush_all()
        self.env.cr.execute("""
            UPDATE google_ads_oauth_session
               SET used_at = (now() AT TIME ZONE 'utc')
             WHERE state_hash = %s
               AND used_at IS NULL
               AND expires_at > (now() AT TIME ZONE 'utc')
         RETURNING id
        """, (digest,))
        row = self.env.cr.fetchone()
        if row:
            session = self.sudo().browse(row[0])
            session.invalidate_recordset(['used_at'])
            return session
        # Lost the race, unknown, already used — or expired, which still gets
        # burned and labelled so the purge cron and the audit read true.
        session = self.sudo().search(
            [('state_hash', '=', digest), ('used_at', '=', False)], limit=1)
        if session:
            session.write({'outcome': 'expired',
                           'used_at': fields.Datetime.now()})
        return None

    def _get_pkce_verifier(self):
        """Server-side only (leading underscore ⇒ not RPC-callable)."""
        self.ensure_one()
        return channel_crypto.decrypt(
            self.env, self.sudo().pkce_verifier_enc or '')

    # ------------------------------------------------------------------
    # Callback logic
    # ------------------------------------------------------------------
    @api.model
    def _handle_callback(self, params):
        """Process one return from Google.

        Returns ``{'outcome', 'ok', 'channel'}``. ``outcome`` is one of
        ``generic`` (unknown / used / expired — one indistinguishable
        bucket), ``denied``, ``error`` or ``ok``. Nothing from ``params`` is
        ever returned, rendered or logged: the authorization code is used once
        inside the exchange and is never persisted.
        """
        generic = {'outcome': 'generic', 'ok': False, 'channel': CHANNEL_KEY}
        params = params or {}
        session = self._consume(params.get('state'))
        if not session:
            return generic

        account = session.account_id.sudo()
        # A CANCELLED RECONNECT MUST NOT DISCONNECT A WORKING ACCOUNT: the
        # only state this callback may lower is one that was already on its
        # way somewhere.
        was_connected = account.reporting_state == 'connected'

        if params.get('error') or params.get('error_description'):
            session.write({
                'outcome': 'denied',
                'detail_redacted': redact(params.get('error_description')
                                          or params.get('error')
                                          or 'denied'),
            })
            if not was_connected:
                account._internal().write({'reporting_state': 'not_connected'})
            return {'outcome': 'denied', 'ok': False, 'channel': CHANNEL_KEY}

        config = self.env['google.ads.platform.config']._active()
        if not config or not config._ready():
            return self._fail(session, account, was_connected, 'not_configured',
                              'the Google Ads application is not configured')

        code = params.get('code')
        if not code or not isinstance(code, str):
            return self._fail(session, account, was_connected,
                              'oauth_exchange', 'no authorization code')

        try:
            # Ledger §5.55: the savepoint, not the `try`, is what keeps the
            # outer transaction usable when the guarded body dies on a
            # database-level error.
            with self.env.cr.savepoint():
                body = gads._http_post_form(gads.TOKEN_URL, data={
                    'grant_type': 'authorization_code',
                    'code': code,
                    'client_id': config.client_id,
                    'client_secret': config._get_client_secret(),
                    'redirect_uri': config.redirect_uri,
                    'code_verifier': session._get_pkce_verifier(),
                })
        except gads.GoogleAdsError as err:
            return self._fail(session, account, was_connected, 'oauth_exchange',
                              err.detail_redacted or err.code)
        except Exception as exc:  # noqa: BLE001 — never 500 a public route
            _logger.warning('google_ads: token exchange failed', exc_info=True)
            return self._fail(session, account, was_connected, 'oauth_exchange',
                              exc)

        body = body if isinstance(body, dict) else {}
        access = body.get('access_token')
        expires_in = body.get('expires_in')
        if not access or not expires_in:
            return self._fail(session, account, was_connected,
                              'exchange_malformed',
                              'the sign-in answer was incomplete')

        scope = str(body.get('scope') or '')
        if 'adwords' not in scope:
            return self._fail(
                session, account, was_connected, 'scope_missing',
                'the sign-in did not include permission to read advertising '
                'accounts')

        refresh = body.get('refresh_token')
        if not refresh and not account.refresh_token_enc:
            # Google only returns a refresh token with access_type=offline AND
            # a fresh consent. A re-consent that omits one while we hold none
            # leaves nothing that survives the hour.
            return self._fail(
                session, account, was_connected, 'no_refresh_token',
                'Google did not return a long-lived permission')

        try:
            expires_in = int(expires_in)
        except (TypeError, ValueError):
            expires_in = 3600
        vals = {
            'access_token_enc': channel_crypto.encrypt(self.env, access),
            'token_expires_at': fields.Datetime.now() + timedelta(
                seconds=max(expires_in - 60, 0)),
            'token_scope': scope[:255],
            'authorized_by': session.user_id.id,
            'authorized_at': fields.Datetime.now(),
            'last_error_code': False,
            'reporting_error_redacted': False,
        }
        if refresh:
            # KEEP the existing refresh token when the response omits one.
            vals['refresh_token_enc'] = channel_crypto.encrypt(
                self.env, refresh)
        account._internal().write(vals)

        if not account.customer_id:
            account._internal().write({'reporting_state': 'select_account'})
        else:
            # The account already knows which advertising customer it is —
            # a reconnect. Prove the grant still reads it before saying
            # "Connected".
            try:
                info = account._validate_reporting_access(
                    account.customer_id, account.login_customer_id)
            except gads.GoogleAdsError as err:
                account._internal().write({
                    'reporting_state': 'action_required',
                    'last_error_code': (err.code or 'error')[:64],
                    'reporting_error_redacted': account._reporting_message(err),
                })
            else:
                account._internal().write(dict(
                    account._provider_vals(info),
                    reporting_state='connected'))

        session.write({'outcome': 'ok'})
        # Status only — no token, no code, no state (rail R1/R2).
        account.message_post(body=_(
            'Google sign-in completed by %s.', session.user_id.name))
        return {'outcome': 'ok', 'ok': True, 'channel': CHANNEL_KEY}

    def _fail(self, session, account, was_connected, code, detail):
        """One failure shape: session labelled, account told, nothing leaked."""
        session.write({'outcome': 'error',
                       'detail_redacted': redact(detail)})
        vals = {
            'last_error_code': code[:64],
            'reporting_error_redacted': account._reporting_message_for(code),
        }
        if not was_connected:
            vals['reporting_state'] = 'not_connected'
        account._internal().write(vals)
        return {'outcome': 'error', 'ok': False, 'channel': CHANNEL_KEY}

    # ------------------------------------------------------------------
    # Purge cron
    # ------------------------------------------------------------------
    @api.model
    def _cron_purge_oauth_sessions(self):
        cutoff = fields.Datetime.now() - timedelta(hours=PURGE_AFTER_HOURS)
        stale = self.sudo().search([('create_date', '<', cutoff)])
        count = len(stale)
        if count:
            stale.unlink()
            _logger.info('Purged %s expired Google sign-in session(s)', count)
        return count
