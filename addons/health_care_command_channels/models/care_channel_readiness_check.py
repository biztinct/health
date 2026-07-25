# -*- coding: utf-8 -*-
"""Explicit readiness, never one boolean (architecture §5.4).

Every distinct thing that can be true-or-false about a connection gets its own
row: the grant is valid, the scopes were actually granted, a resource was
picked, the webhook is registered, the webhook was seen firing, an outbound
message went out, an inbound one came in, the token is fresh, the provider's
human approvals are through. ``care.channel.connection.state == 'ready'`` is
derived from these — it is never asserted by whoever wrote the row.

That separation is the whole point: "configured" and "connected" are different
claims, and the old config models could only ever express the first one.
"""
from odoo import api, fields, models

from ..services.redact import redact

CHECK_KEYS = [
    ('authorization_valid', 'Authorization valid'),
    ('scopes_granted', 'Scopes granted'),
    ('resource_selected', 'Resource selected'),
    ('webhook_configured', 'Webhook configured'),
    ('webhook_verified', 'Webhook verified'),
    ('outbound_ok', 'Outbound proven'),
    ('inbound_ok', 'Inbound proven'),
    ('token_fresh', 'Token fresh'),
    ('provider_approvals', 'Provider approvals'),
]

STATUSES = [
    ('pass', 'Pass'),
    ('fail', 'Fail'),
    ('pending', 'Pending'),
    ('n_a', 'Not applicable'),
]


class CareChannelReadinessCheck(models.Model):
    _name = 'care.channel.readiness.check'
    _description = 'Channel Readiness Check'
    _order = 'connection_id, check_key'

    connection_id = fields.Many2one(
        'care.channel.connection', required=True, index=True,
        ondelete='cascade')
    company_id = fields.Many2one(
        related='connection_id.company_id', store=True, index=True)
    check_key = fields.Selection(CHECK_KEYS, required=True, index=True)
    status = fields.Selection(STATUSES, required=True, default='pending')
    detail_redacted = fields.Char(string='Detail')
    checked_at = fields.Datetime(default=fields.Datetime.now)

    def init(self):
        # §5.1: one row per (connection, check).
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
                care_channel_readiness_check_conn_key_uniq
            ON care_channel_readiness_check (connection_id, check_key)
        """)

    @api.model
    def upsert_check(self, connection, check_key, status, detail=None):
        """Record one check result and re-derive the connection's readiness.

        Search+write rather than an ON CONFLICT upsert: at most nine rows per
        connection exist, so the simple path is the honest one. ``detail``
        always goes through the shared redaction helper — provider error text
        is the most likely place for a bearer token to leak into the database.
        """
        connection.ensure_one()
        vals = {
            'status': status,
            'detail_redacted': redact(detail),
            'checked_at': fields.Datetime.now(),
        }
        existing = self.sudo().search([
            ('connection_id', '=', connection.id),
            ('check_key', '=', check_key)], limit=1)
        if existing:
            existing.write(vals)
            record = existing
        else:
            vals.update({'connection_id': connection.id, 'check_key': check_key})
            record = self.sudo().create(vals)
        connection.sudo()._recompute_ready()
        return record
