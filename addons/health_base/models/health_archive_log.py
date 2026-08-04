# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HealthArchiveLog(models.Model):
    """Append-only audit trail of the record lifecycle: archive / unarchive
    (custodian), delete / restore (user soft delete) and purge (owner physical
    delete), including the mandatory justification captured at action time."""
    _name = 'health.archive.log'
    _description = 'Healthcare Record Lifecycle Log'
    _order = 'create_date desc'
    _rec_name = 'record_name'

    model_technical = fields.Char('Model', readonly=True, index=True)
    model_name = fields.Char('Model Name', readonly=True)
    res_id = fields.Integer('Record ID', readonly=True, index=True)
    record_name = fields.Char('Record', readonly=True)
    action = fields.Selection([
        ('archive', 'Archived'),
        ('unarchive', 'Unarchived'),
        ('delete', 'Deleted'),
        ('restore', 'Restored'),
        ('purge', 'Purged'),
    ], string='Action', readonly=True, index=True)
    reason = fields.Text('Reason', readonly=True)
    user_id = fields.Many2one(
        'res.users', string='User', readonly=True,
        default=lambda self: self.env.uid, index=True)
    record_state = fields.Selection([
        ('deleted', 'Awaiting Verification'),
        ('archived', 'Archived'),
        ('active', 'Active'),
        ('purged', 'Purged'),
    ], string='Current State', compute='_compute_record_state',
        help='Live state of the target record, so the custodian console shows '
             'what still needs attention.')

    def _compute_record_state(self):
        for log in self:
            state = 'purged'
            model = log.model_technical
            if model and model in self.env and log.res_id:
                rec = self.env[model].sudo().with_context(
                    active_test=False, deleted_test=False,
                ).browse(log.res_id).exists()
                if rec:
                    if 'deleted' in rec._fields and rec.deleted:
                        state = 'deleted'
                    elif 'active' in rec._fields and not rec.active:
                        state = 'archived'
                    else:
                        state = 'active'
            log.record_state = state

    def action_open_record(self):
        self.ensure_one()
        if not self.model_technical or self.model_technical not in self.env:
            raise UserError(_('The record model is not installed.'))
        return {
            'type': 'ir.actions.act_window',
            'res_model': self.model_technical,
            'res_id': self.res_id,
            'view_mode': 'form',
            'target': 'current',
            # Deleted/archived records must open from the console.
            'context': {'deleted_test': False, 'active_test': False},
        }

    def write(self, vals):
        raise UserError(_('Lifecycle log entries are append-only and cannot be modified.'))

    def unlink(self):
        raise UserError(_('Lifecycle log entries are append-only and cannot be deleted.'))
