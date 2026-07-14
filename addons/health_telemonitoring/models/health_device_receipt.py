# -*- coding: utf-8 -*-
"""``health.device.receipt`` — idempotency ledger for device ingestion batches.

Clone of ``health.pwa.action.receipt`` (conventions §5.1 / fact 5): a unique
index on ``(device_id, client_batch_uuid)`` plus a search-first replay in the
ingestion controller guarantees that N POSTs of the same batch produce exactly
ONE set of observations. The stored ``result_json`` is replayed verbatim on
every subsequent POST of the same uuid.

Rows are immutable (append-only, §5.4 — the guard is unconditional so it holds
for uid 1 / admin / tests too) and pruned after ``receipt_retention_days`` by a
daily cron.
"""
import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from . import tm_config

_logger = logging.getLogger(__name__)


class HealthDeviceReceipt(models.Model):
    _name = 'health.device.receipt'
    _description = 'Device Ingestion Receipt'
    _order = 'create_date desc'

    device_id = fields.Many2one(
        'health.monitor.device', string='Device', required=True, index=True,
        ondelete='cascade')
    client_batch_uuid = fields.Char(
        string='Client Batch UUID', required=True, size=64)
    state = fields.Selection([
        ('applied', 'Applied'),
        ('partial', 'Partial'),
        ('rejected', 'Rejected'),
    ], string='State', required=True, default='applied')
    result_json = fields.Text(string='Result Payload')
    received_at = fields.Datetime(string='Received At')

    def init(self):
        # §5.1 — the idempotency unique index the search-first replay relies on.
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS health_device_receipt_uniq
            ON health_device_receipt (device_id, client_batch_uuid)
        """)

    def write(self, vals):
        # Append-only: an ingestion receipt is an immutable record of what the
        # server did with a batch. Unconditional (§5.4): uid 1 runs as su and
        # tests run as uid 1, so a conditional guard would be dead code.
        if vals:
            raise UserError(_('Device ingestion receipts are immutable.'))
        return super().write(vals)

    @api.model
    def cron_gc_receipts(self):
        """Prune receipts older than ``receipt_retention_days`` (default 90).
        A partner offline longer than the retention horizon re-POSTs under a
        fresh batch uuid, so an aged receipt carries no replay signal."""
        days = tm_config.get_int(self.env, 'receipt_retention_days', 90)
        horizon = fields.Datetime.now() - timedelta(days=days)
        stale = self.sudo().search([('create_date', '<', horizon)])
        count = len(stale)
        stale.unlink()
        _logger.info('Device receipt GC: removed %s rows older than %s days.',
                     count, days)
        return True
