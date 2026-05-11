# -*- coding: utf-8 -*-
import pytz

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


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
    access_role_id = fields.Many2one('access.role', string='Access Role')
    is_duty_doctor = fields.Boolean('Is Duty Doctor')
    is_head_nurse = fields.Boolean('Is Head Nurse')

    show_duty_doctor = fields.Boolean(compute='_compute_show_qualifiers')
    show_head_nurse = fields.Boolean(compute='_compute_show_qualifiers')
    is_owner_role = fields.Boolean(compute='_compute_show_qualifiers')

    catchment_province_id = fields.Many2one(
        'health.catchment.province', string='Catchment Province',
        options="{'no_create': True}",
    )
    healthcare_facility_id = fields.Many2one(
        'health.facility', string='Healthcare Facility',
        domain="[('catchment_province_id', '=', catchment_province_id)]",
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

    @api.depends('access_role_id', 'access_role_id.name')
    def _compute_show_qualifiers(self):
        for rec in self:
            role_name = (rec.access_role_id.name or '').lower()
            rec.show_duty_doctor = 'doctor' in role_name
            rec.show_head_nurse = 'nurse' in role_name
            rec.is_owner_role = role_name == 'owner'

    @api.onchange('access_role_id')
    def _onchange_access_role_id(self):
        if not self.access_role_id:
            self.is_duty_doctor = False
            self.is_head_nurse = False
            return
        role_name = (self.access_role_id.name or '').lower()
        if 'doctor' not in role_name:
            self.is_duty_doctor = False
        if 'nurse' not in role_name:
            self.is_head_nurse = False

    @api.onchange('catchment_province_id')
    def _onchange_catchment_province_id(self):
        self.healthcare_facility_id = False

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
            'is_duty_doctor': self.is_duty_doctor,
            'is_head_nurse': self.is_head_nurse,
            'catchment_province_id': self.catchment_province_id.id or False,
        })

        if self.access_role_id:
            self.access_role_id.sudo().write({'user_ids': [(4, new_user.id)]})

        self.env['hr.employee'].sudo().create({
            'name': self.name,
            'user_id': new_user.id,
            'company_id': self.company_id.id or self.env.company.id,
            'is_healthcare_staff': True,
            'is_duty_doctor': self.is_duty_doctor,
            'is_head_nurse': self.is_head_nurse,
            'healthcare_facility_id': self.healthcare_facility_id.id or False,
            'staff_catchment_province_id': self.catchment_province_id.id or False,
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
