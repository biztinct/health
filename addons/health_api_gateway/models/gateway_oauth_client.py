# -*- coding: utf-8 -*-
import hashlib
import hmac
import logging
import secrets
import uuid

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class GatewayOauthClient(models.Model):
    """OAuth2 client-credentials client (spec B.2.3)."""
    _name = 'gateway.oauth.client'
    _description = 'API Gateway OAuth2 Client'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(required=True, tracking=True)
    client_id = fields.Char(
        required=True, index=True, copy=False,
        default=lambda self: uuid.uuid4().hex)
    client_secret_hash = fields.Char(
        copy=False, groups='health_api_gateway.group_gateway_admin',
        help='Hashed client secret. The plaintext is shown exactly once, '
             'when (re)generated — it is never stored.')
    allowed_scope_ids = fields.Many2many(
        'api.key.scope', 'gateway_oauth_client_scope_rel',
        'client_id', 'scope_id', string='Allowed Scopes')
    user_id = fields.Many2one(
        'res.users', required=True, string='Service User',
        help='Tokens issued to this client act as this user '
             '(record rules apply naturally).')
    token_lifetime = fields.Integer(default=3600, help='Token lifetime in seconds.')
    jwks = fields.Text(
        string='JWKS',
        help='Optional RFC 7523 client-assertion public keys '
             '(SMART backend services, Phase 3).')
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('client_id_unique', 'unique(client_id)', 'client_id must be unique.'),
    ]

    # ------------------------------------------------------------------
    # Secret hashing — passlib crypt context when available, salted
    # sha256 fallback. Plaintext secrets are never persisted.
    # ------------------------------------------------------------------
    def _get_crypt_context(self):
        try:
            users = self.env['res.users']
            if hasattr(users, '_crypt_context'):
                return users._crypt_context()
        except Exception:  # pragma: no cover - defensive
            pass
        return None

    @api.model
    def _hash_secret(self, secret):
        ctx = self._get_crypt_context()
        if ctx is not None:
            try:
                return ctx.hash(secret)
            except Exception:
                _logger.warning('crypt context hash failed, using sha256 fallback')
        salt = secrets.token_hex(16)
        digest = hashlib.sha256((salt + secret).encode('utf-8')).hexdigest()
        return 'sha256$%s$%s' % (salt, digest)

    def _verify_secret(self, secret):
        self.ensure_one()
        stored = self.sudo().client_secret_hash
        if not stored or not secret:
            return False
        if stored.startswith('sha256$'):
            try:
                _prefix, salt, digest = stored.split('$', 2)
            except ValueError:
                return False
            candidate = hashlib.sha256((salt + secret).encode('utf-8')).hexdigest()
            return hmac.compare_digest(candidate, digest)
        ctx = self._get_crypt_context()
        if ctx is not None:
            try:
                return bool(ctx.verify(secret, stored))
            except Exception:
                return False
        return False

    def _set_secret(self, secret):
        """Set the client secret (hashed). Used by tests and the regenerate action."""
        self.ensure_one()
        self.sudo().write({'client_secret_hash': self._hash_secret(secret)})

    def action_regenerate_secret(self):
        """Generate a new secret, store only its hash, and show the plaintext
        exactly once in a sticky notification (spec: secret shown once)."""
        self.ensure_one()
        secret = secrets.token_urlsafe(32)
        self._set_secret(secret)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Client secret generated'),
                'message': _(
                    'Copy it now — it will not be shown again:\n%s', secret),
                'type': 'warning',
                'sticky': True,
            },
        }

    @api.model
    def _authenticate_client(self, client_id, client_secret):
        """Return the active client record if credentials match, else empty."""
        if not client_id or not client_secret:
            return self.browse()
        client = self.sudo().search([('client_id', '=', client_id),
                                     ('active', '=', True)], limit=1)
        if client and client._verify_secret(client_secret):
            return client
        return self.browse()
