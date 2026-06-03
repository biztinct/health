# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

# (weekday index 0..6, field-prefix, legacy Char field, label)
_DAYS = [
    (0, 'mon', 'working_hours_monday', 'Monday'),
    (1, 'tue', 'working_hours_tuesday', 'Tuesday'),
    (2, 'wed', 'working_hours_wednesday', 'Wednesday'),
    (3, 'thu', 'working_hours_thursday', 'Thursday'),
    (4, 'fri', 'working_hours_friday', 'Friday'),
    (5, 'sat', 'working_hours_saturday', 'Saturday'),
    (6, 'sun', 'working_hours_sunday', 'Sunday'),
]


class HealthStaffScheduleWizard(models.TransientModel):
    """Easy weekly working-hours editor. Writes the staff's standard
    resource.calendar (per-employee), so Odoo's working-time / availability APIs
    understand it, and keeps the legacy working_hours_* Char fields in sync."""
    _name = 'health.staff.schedule.wizard'
    _description = 'Set Staff Working Hours'

    employee_id = fields.Many2one(
        'hr.employee', string='Staff', required=True,
        domain="[('is_healthcare_staff', '=', True)]",
    )
    mon_off = fields.Boolean('Mon off')
    mon_from = fields.Float('Mon from', default=9.0)
    mon_to = fields.Float('Mon to', default=17.0)
    tue_off = fields.Boolean('Tue off')
    tue_from = fields.Float('Tue from', default=9.0)
    tue_to = fields.Float('Tue to', default=17.0)
    wed_off = fields.Boolean('Wed off')
    wed_from = fields.Float('Wed from', default=9.0)
    wed_to = fields.Float('Wed to', default=17.0)
    thu_off = fields.Boolean('Thu off')
    thu_from = fields.Float('Thu from', default=9.0)
    thu_to = fields.Float('Thu to', default=17.0)
    fri_off = fields.Boolean('Fri off')
    fri_from = fields.Float('Fri from', default=9.0)
    fri_to = fields.Float('Fri to', default=17.0)
    sat_off = fields.Boolean('Sat off', default=True)
    sat_from = fields.Float('Sat from', default=9.0)
    sat_to = fields.Float('Sat to', default=13.0)
    sun_off = fields.Boolean('Sun off', default=True)
    sun_from = fields.Float('Sun from', default=9.0)
    sun_to = fields.Float('Sun to', default=13.0)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        emp_id = self.env.context.get('default_employee_id') or self.env.context.get('active_id')
        if emp_id and self.env.context.get('active_model', 'hr.employee') == 'hr.employee':
            emp = self.env['hr.employee'].browse(emp_id)
            if emp.exists():
                res['employee_id'] = emp.id
                for idx, pre, _char, _label in _DAYS:
                    ivs = emp._working_intervals_for(idx)
                    if ivs:
                        res[f'{pre}_off'] = False
                        res[f'{pre}_from'] = ivs[0][0]
                        res[f'{pre}_to'] = ivs[-1][1]
                    else:
                        res[f'{pre}_off'] = True
        return res

    def action_confirm(self):
        self.ensure_one()
        emp = self.employee_id

        # Get-or-create a per-employee calendar (don't edit the shared company one)
        cal = emp.resource_calendar_id
        company_cal = self.env.company.resource_calendar_id
        if (not cal) or cal == company_cal:
            cal = self.env['resource.calendar'].sudo().create({
                'name': _('%s — Schedule') % (emp.name or _('Staff')),
                'tz': (company_cal.tz if company_cal else False) or self.env.user.tz or 'Asia/Ho_Chi_Minh',
            })
            emp.sudo().write({'resource_calendar_id': cal.id})

        att_vals = []
        char_vals = {}
        for idx, pre, char_field, _label in _DAYS:
            off = self[f'{pre}_off']
            hf = self[f'{pre}_from']
            ht = self[f'{pre}_to']
            if off or ht <= hf:
                char_vals[char_field] = ''
                continue
            att_vals.append((0, 0, {
                'name': _('Work'),
                'dayofweek': str(idx),
                'hour_from': hf,
                'hour_to': ht,
                'day_period': 'morning' if hf < 12 else 'afternoon',
            }))
            char_vals[char_field] = '%02d:%02d-%02d:%02d' % (
                int(hf), round((hf % 1) * 60), int(ht), round((ht % 1) * 60))

        cal.sudo().write({'attendance_ids': [(5, 0, 0)] + att_vals})
        emp.sudo().write(char_vals)
        return {'type': 'ir.actions.act_window_close'}
