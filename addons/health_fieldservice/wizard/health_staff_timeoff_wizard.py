# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class HealthStaffTimeoffWizard(models.TransientModel):
    """Quick entry to record staff time off. Creates standard hr.leave records and
    validates them directly (no apply/approve flow for now) so they immediately
    affect availability. The same hr.leave records feed a future self-service flow."""
    _name = 'health.staff.timeoff.wizard'
    _description = 'Record Staff Time Off'

    employee_ids = fields.Many2many(
        'hr.employee', string='Staff', required=True,
        domain="[('is_healthcare_staff', '=', True)]",
    )
    holiday_status_id = fields.Many2one(
        'hr.leave.type', string='Time Off Type', required=True)
    request_date_from = fields.Date('From', required=True, default=fields.Date.context_today)
    request_date_to = fields.Date('To', required=True, default=fields.Date.context_today)
    name = fields.Char('Reason')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'holiday_status_id' in fields_list and not res.get('holiday_status_id'):
            # Prefer a type that doesn't require an allocation (simplest to validate)
            lt = self.env['hr.leave.type'].search(
                [('requires_allocation', '=', 'no')], limit=1
            ) or self.env['hr.leave.type'].search([], limit=1)
            if lt:
                res['holiday_status_id'] = lt.id
        return res

    def action_confirm(self):
        self.ensure_one()
        if not self.employee_ids:
            raise UserError(_('Select at least one staff member.'))
        if self.request_date_to < self.request_date_from:
            raise UserError(_('The "To" date must be on or after the "From" date.'))

        Leave = self.env['hr.leave']
        created = self.env['hr.leave']
        for emp in self.employee_ids:
            leave = Leave.sudo().create({
                'employee_id': emp.id,
                'holiday_status_id': self.holiday_status_id.id,
                'request_date_from': self.request_date_from,
                'request_date_to': self.request_date_to,
                'name': self.name or _('Time Off'),
            })
            # Validate directly; fall back to a forced state if the type needs an
            # allocation/approval we intentionally skip.
            try:
                leave.action_validate()
            except Exception:
                leave.write({'state': 'validate'})
            created |= leave

        return {
            'type': 'ir.actions.act_window',
            'name': _('Recorded Time Off'),
            'res_model': 'hr.leave',
            'view_mode': 'list,form',
            'domain': [('id', 'in', created.ids)],
            'target': 'current',
        }
