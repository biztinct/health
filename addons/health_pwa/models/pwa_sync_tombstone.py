# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models


class HealthPwaSyncTombstone(models.Model):
    """Records a hard-deleted record id so the incremental sync delta can emit
    a `{id, is_deleted: True}` removal to offline clients (the pull query cannot
    see a row that no longer exists). Written sudo from the FSO unlink hook
    below; read sudo from the sync controller. ACL: base.group_system only."""

    _name = 'health.pwa.sync.tombstone'
    _description = 'PWA Sync Deletion Tombstone'

    res_model = fields.Char(string='Model', required=True)
    res_id = fields.Integer(string='Record ID', required=True, index=True)
    stamp = fields.Datetime(string='Deleted At', default=fields.Datetime.now, index=True)

    @api.autovacuum
    def _gc_tombstones(self):
        """Prune tombstones older than the sync fallback horizon (90 days). A
        client that has been offline longer than that does a full re-pull and
        drops out-of-scope rows itself, so old tombstones carry no signal."""
        horizon = fields.Datetime.now() - timedelta(days=90)
        self.sudo().search([('stamp', '<', horizon)]).unlink()


class HealthFieldserviceOrderTombstone(models.Model):
    """Hard-delete hook: stamp a tombstone for every FSO id BEFORE it is
    unlinked so the next sync delta can tell offline devices to drop it.

    NOTE (conventions §5.30): a cascade delete happens at the SQL layer and
    bypasses this Python unlink(), so an FSO removed via a parent cascade would
    skip the tombstone. Accepted for v1 — FSOs are not routinely cascade
    children of anything that gets deleted; natural cache staleness + the
    90-day full-pull fallback cover that edge."""

    _inherit = 'health.fieldservice.order'

    def unlink(self):
        if self.ids:
            self.env['health.pwa.sync.tombstone'].sudo().create([
                {'res_model': 'health.fieldservice.order', 'res_id': oid}
                for oid in self.ids
            ])
        return super().unlink()
