# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError

EVENTS = [
    ('query', 'Query Executed'),
    ('dataset_publish', 'Dataset Published'),
    ('dataset_unpublish', 'Dataset Unpublished'),
    ('gold_publish', 'Gold View Created'),
    ('gold_refresh', 'Gold View Refreshed'),
    ('chart_save', 'Chart Saved'),
    ('dashboard_view', 'Dashboard Viewed'),
    ('dashboard_share', 'Dashboard Shared'),
    ('export', 'Export'),
    ('rls_change', 'Access Rule Changed'),
    ('provider_change', 'AI Provider Changed'),
    ('ai_request', 'AI Request'),
    ('csv_import', 'CSV Import'),
    ('external_sync', 'External Sync'),
]


class BiAuditLog(models.Model):
    """Append-only audit trail. Rows are created through sudo by the
    platform itself; nobody edits or deletes them."""
    _name = 'bi.audit.log'
    _description = 'BI Audit Log'
    _order = 'id desc'
    _log_access = False

    user_id = fields.Many2one('res.users', required=True, index=True,
                              default=lambda self: self.env.user)
    event = fields.Selection(EVENTS, required=True, index=True)
    dataset_id = fields.Many2one('bi.dataset', ondelete='set null', index=True)
    res_model = fields.Char()
    res_id = fields.Integer()
    payload_json = fields.Json()
    created_at = fields.Datetime(default=fields.Datetime.now, required=True)

    @api.model
    def log(self, event, dataset=None, record=None, payload=None):
        self.sudo().create({
            'user_id': self.env.uid,
            'event': event,
            'dataset_id': dataset.id if dataset else False,
            'res_model': record._name if record is not None else False,
            'res_id': record.id if record is not None else False,
            'payload_json': payload or {},
        })

    def write(self, vals):
        raise UserError(_("Audit log entries cannot be modified."))

    def unlink(self):
        raise UserError(_("Audit log entries cannot be deleted."))

    @api.model
    def get_recents(self, limit=10):
        """Recently viewed dashboards for the BI Home screen."""
        self.env.cr.execute("""
            SELECT res_id, MAX(created_at) AS seen_at
            FROM bi_audit_log
            WHERE user_id = %s AND event = 'dashboard_view'
              AND res_model = 'bi.dashboard'
            GROUP BY res_id ORDER BY seen_at DESC LIMIT %s
        """, (self.env.uid, limit))
        dashboard_ids = [row[0] for row in self.env.cr.fetchall()]
        dashboards = self.env['bi.dashboard'].search(
            [('id', 'in', dashboard_ids)])
        by_id = {d.id: d for d in dashboards}
        return [{
            'id': d.id, 'name': d.name,
            'workspace': d.workspace_id.name,
        } for did in dashboard_ids if (d := by_id.get(did))]
