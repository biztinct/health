# -*- coding: utf-8 -*-
import pytz

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

ROLE_NAME_TO_HEALTHCARE = {
    'nurse': 'nurse',
    'head nurse': 'head_nurse',
    'doctor': 'doctor',
    'duty doctor': 'duty_doctor',
    'specialist': 'specialist',
    'therapist': 'therapist',
    'technician': 'technician',
    'support': 'support',
    'support staff': 'support',
    'operations manager': 'operations_manager',
    'admin': 'admin',
    'administrator': 'admin',
    'owner': 'owner',
    'accountant': 'accountant',
}

HEALTHCARE_ROLE_SELECTION = [
    ('doctor', 'Doctor'),
    ('duty_doctor', 'Duty Doctor'),
    ('nurse', 'Nurse'),
    ('head_nurse', 'Head Nurse'),
    ('specialist', 'Specialist'),
    ('therapist', 'Therapist'),
    ('technician', 'Technician'),
    ('support', 'Support Staff'),
    ('operations_manager', 'Operations Manager'),
    ('admin', 'Admin'),
    ('owner', 'Owner'),
    ('accountant', 'Accountant'),
]


class HealthCreateUserWizard(models.TransientModel):
    _name = 'health.create.user.wizard'
    _description = 'Create User and Employee'

    name = fields.Char('Name', required=True)
    login = fields.Char('Email', required=True)
    phone = fields.Char('Phone')
    password = fields.Char('Password')
    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company,
    )
    lang = fields.Selection(
        '_get_lang', string='Language',
        default=lambda self: self.env.lang or 'en_US',
    )
    tz = fields.Selection(
        '_tz_get', string='Timezone',
        default=lambda self: self.env.context.get('tz') or self.env.user.tz or 'Asia/Ho_Chi_Minh',
    )
    access_role_id = fields.Many2one(
        'access.role', string='Access Role',
        options="{'no_create': False}",
    )
    healthcare_role = fields.Selection(
        HEALTHCARE_ROLE_SELECTION, string='Healthcare Role', required=True,
    )
    employment_status = fields.Selection([
        ('active', 'Active'),
        ('on_leave', 'On Leave'),
        ('suspended', 'Suspended'),
        ('terminated', 'Terminated'),
    ], string='Employment Status', default='active')
    employment_type = fields.Selection([
        ('full_time', 'Full-Time Staff'),
        ('part_time', 'Part-Time Staff'),
        ('casual', 'Casual/Contract'),
    ], string='Employment Type', default='full_time')

    @api.model
    def _get_lang(self):
        return self.env['res.lang'].get_installed()

    @api.model
    def _tz_get(self):
        return [(tz, tz) for tz in sorted(pytz.all_timezones, key=lambda tz: tz if not tz.startswith('Etc/') else '_')]

    @api.onchange('access_role_id')
    def _onchange_access_role_id(self):
        if not self.access_role_id:
            return
        role_name = (self.access_role_id.name or '').strip().lower()

        if 'doctor' in role_name:
            if self.healthcare_role not in ('doctor', 'duty_doctor'):
                self.healthcare_role = 'doctor'
            return
        if 'nurse' in role_name:
            if self.healthcare_role not in ('nurse', 'head_nurse'):
                self.healthcare_role = 'nurse'
            return

        matched = ROLE_NAME_TO_HEALTHCARE.get(role_name)
        if matched:
            self.healthcare_role = matched

    def action_create_user(self):
        self.ensure_one()

        existing = self.env['res.users'].sudo().with_context(active_test=False).search(
            [('login', '=', self.login)], limit=1,
        )
        if existing:
            raise ValidationError(_("A user with email '%s' already exists.", self.login))

        user_vals = {
            'name': self.name,
            'login': self.login,
            'phone': self.phone or False,
            'access_role_id': self.access_role_id.id if self.access_role_id else False,
            'company_id': self.company_id.id or self.env.company.id,
            'company_ids': [(6, 0, [self.company_id.id or self.env.company.id])],
            'lang': self.lang,
            'tz': self.tz,
        }
        if self.password:
            user_vals['password'] = self.password

        result = self.env['res.users'].action_saas_create_user(user_vals)
        new_user = self.env['res.users'].sudo().browse(result['id'])
        new_user.write({
            'is_healthcare_staff': True,
            'healthcare_role': self.healthcare_role,
        })

        self.env['hr.employee'].sudo().create({
            'name': self.name,
            'user_id': new_user.id,
            'company_id': self.company_id.id or self.env.company.id,
            'is_healthcare_staff': True,
            'healthcare_role': self.healthcare_role,
            'employment_status': self.employment_status or 'active',
            'employment_type': self.employment_type or 'full_time',
        })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': _('User "%s" created successfully.', self.name),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
