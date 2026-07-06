# -*- coding: utf-8 -*-
import hashlib
import secrets
from datetime import timedelta

from odoo import api, fields, models

TOKEN_PREFIX = 'hg_'


class GatewayToken(models.Model):
    """Opaque-token store (spec B.2.4) — simpler than JWT for CE, no shared
    secret rotation problem. Only the SHA-256 of the token is stored; the raw
    token is returned once by :meth:`issue` and resolved by hash."""
    _name = 'gateway.token'
    _description = 'API Gateway Access Token'
    _order = 'expires_at desc'
    _rec_name = 'token_hash'

    token_hash = fields.Char(size=64, required=True, index=True, readonly=True)
    client_id = fields.Many2one('gateway.oauth.client', ondelete='cascade',
                                index=True, string='OAuth Client')
    user_id = fields.Many2one('res.users', required=True, ondelete='cascade',
                              string='Service User')
    scope_codes = fields.Char(help='Space-separated granted scope codes.')
    expires_at = fields.Datetime(required=True, index=True)

    _sql_constraints = [
        ('token_hash_unique', 'unique(token_hash)', 'Token hash collision.'),
    ]

    def init(self):
        # Odoo 19 no longer materializes _sql_constraints automatically —
        # create the unique index explicitly.
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS gateway_token_hash_uidx
            ON gateway_token (token_hash)
        """)

    @staticmethod
    def _hash(raw):
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()

    @api.model
    def issue(self, client, scopes):
        """Issue a raw ``hg_<48 hex>`` token for `client` limited to `scopes`
        (iterable of scope codes). Returns the raw token string — the only
        time it is ever available."""
        raw = TOKEN_PREFIX + secrets.token_hex(24)
        self.sudo().create({
            'token_hash': self._hash(raw),
            'client_id': client.id,
            'user_id': client.user_id.id,
            'scope_codes': ' '.join(sorted(set(scopes or []))),
            'expires_at': fields.Datetime.now()
                + timedelta(seconds=client.token_lifetime or 3600),
        })
        return raw

    @api.model
    def resolve(self, raw):
        """Resolve a raw token. Returns
        ``{'user_id': int, 'scope_names': set, 'client_id': int,
           'client_code': str}`` or ``None`` (unknown/expired)."""
        if not raw or not raw.startswith(TOKEN_PREFIX):
            return None
        token = self.sudo().search([('token_hash', '=', self._hash(raw))], limit=1)
        if not token:
            return None
        if not token.expires_at or token.expires_at <= fields.Datetime.now():
            return None
        if not token.user_id.active:
            return None
        return {
            'user_id': token.user_id.id,
            'scope_names': set((token.scope_codes or '').split()),
            'client_id': token.client_id.id,
            'client_code': token.client_id.client_id or '',
        }

    @api.model
    def _cron_purge_expired(self):
        """Hourly purge of expired tokens (spec B.2.4)."""
        expired = self.sudo().search([('expires_at', '<', fields.Datetime.now())])
        expired.unlink()
        return True
