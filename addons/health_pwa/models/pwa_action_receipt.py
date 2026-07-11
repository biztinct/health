# -*- coding: utf-8 -*-
"""Idempotency ledger for replayed offline visit actions (pwa-offline-actions
phase). Clones the health_evv event idempotency seam (conventions §5.1 / phase
fact 5): a unique index on (fso_id, action_type, client_action_uuid) plus a
search-first replay in the sync push controller guarantees that N replays of one
queued action produce exactly ONE server effect. The stored result_json is
replayed VERBATIM on every subsequent push of the same uuid — an applied action
stays applied, a rejected action stays rejected. Written/read sudo from the sync
controller; ACL is base.group_system only."""
import logging
from datetime import timedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class HealthPwaActionReceipt(models.Model):
    _name = 'health.pwa.action.receipt'
    _description = 'PWA Offline Action Receipt'
    _order = 'create_date desc'

    fso_id = fields.Many2one(
        'health.fieldservice.order', string='Service Order',
        required=True, index=True, ondelete='cascade')
    action_type = fields.Char(string='Action Type', required=True)
    client_action_uuid = fields.Char(string='Client Action UUID', required=True, size=64)
    claimed_at = fields.Datetime(string='Claimed At')
    staff_id = fields.Many2one('hr.employee', string='Staff')
    state = fields.Selection([
        ('applied', 'Applied'),
        ('rejected', 'Rejected'),
    ], string='State', required=True, default='applied')
    reject_reason = fields.Char(string='Reject Reason')
    result_json = fields.Text(string='Result Payload')

    def init(self):
        # §5.1 — Odoo 19 does not materialize _sql_constraints; create the
        # idempotency unique index explicitly. This is the uniqueness contract
        # the search-first replay (fact 5) relies on.
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS health_pwa_action_receipt_uniq
            ON health_pwa_action_receipt (fso_id, action_type, client_action_uuid)
        """)

    @api.autovacuum
    def _gc_receipts(self):
        """Prune receipts older than 90 days (clone of the tombstone GC in
        pwa_sync_tombstone.py). A client offline longer than the sync fallback
        horizon does a full re-pull, so an old receipt carries no replay
        signal — the queued action doc that would replay it is long gone."""
        horizon = fields.Datetime.now() - timedelta(days=90)
        self.sudo().search([('create_date', '<', horizon)]).unlink()
