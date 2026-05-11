# -*- coding: utf-8 -*-
from odoo import models, fields


class HrEmployeePublic(models.Model):
    _inherit = 'hr.employee.public'

    is_healthcare_staff = fields.Boolean(
        'Healthcare Staff',
        compute='_compute_healthcare_flags',
        readonly=True,
    )

    healthcare_role = fields.Selection([
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
    ], string='Healthcare Role (Deprecated)', compute='_compute_healthcare_flags', readonly=True)

    access_role_display = fields.Char(
        string='Role', compute='_compute_healthcare_flags', readonly=True,
    )
    is_doctor_role = fields.Boolean(
        compute='_compute_healthcare_flags', readonly=True,
    )
    is_nurse_role = fields.Boolean(
        compute='_compute_healthcare_flags', readonly=True,
    )

    def _compute_healthcare_flags(self):
        employees = {emp.id: emp for emp in self.env['hr.employee'].sudo().browse(self.ids)}
        for public_rec in self:
            emp = employees.get(public_rec.id)
            public_rec.is_healthcare_staff = bool(emp and emp.is_healthcare_staff)
            public_rec.healthcare_role = emp.healthcare_role if emp else False
            public_rec.access_role_display = emp.access_role_display if emp else ''
            public_rec.is_doctor_role = emp.is_doctor_role if emp else False
            public_rec.is_nurse_role = emp.is_nurse_role if emp else False
