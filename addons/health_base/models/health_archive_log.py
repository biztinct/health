# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HealthArchiveLog(models.Model):
    """Append-only audit trail of archive / unarchive actions on business
    records, including the mandatory justification captured at archive time."""
    _name = 'health.archive.log'
    _description = 'Healthcare Archive Audit Log'
    _order = 'create_date desc'
    _rec_name = 'record_name'

    model_technical = fields.Char('Model', readonly=True, index=True)
    model_name = fields.Char('Model Name', readonly=True)
    res_id = fields.Integer('Record ID', readonly=True, index=True)
    record_name = fields.Char('Record', readonly=True)
    action = fields.Selection([
        ('archive', 'Archived'),
        ('unarchive', 'Unarchived'),
    ], string='Action', readonly=True, index=True)
    reason = fields.Text('Reason', readonly=True)
    user_id = fields.Many2one(
        'res.users', string='User', readonly=True,
        default=lambda self: self.env.uid, index=True)

    def write(self, vals):
        raise UserError(_('Archive log entries are append-only and cannot be modified.'))

    def unlink(self):
        raise UserError(_('Archive log entries are append-only and cannot be deleted.'))
