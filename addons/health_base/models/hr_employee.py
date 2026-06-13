# -*- coding: utf-8 -*-
from odoo import api, models, fields


class HrEmployee(models.Model):
    """Extend HR Employee with basic healthcare classification"""
    _inherit = 'hr.employee'

    # Basic healthcare staff classification
    is_healthcare_staff = fields.Boolean(
        'Healthcare Staff',
        help='Check if this employee provides healthcare services'
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
    ], string='Healthcare Role (Deprecated)', tracking=True)

    access_role_id = fields.Many2one(
        'access.role', string='Access Role',
        compute='_compute_access_role', inverse='_inverse_access_role',
        store=True, readonly=False,
    )
    is_duty_doctor = fields.Boolean('Is Duty Doctor', default=False, tracking=True)
    is_head_nurse = fields.Boolean('Is Head Nurse', default=False, tracking=True)

    is_doctor_role = fields.Boolean(
        compute='_compute_role_flags', store=True,
    )
    is_nurse_role = fields.Boolean(
        compute='_compute_role_flags', store=True,
    )
    is_om_role = fields.Boolean(
        compute='_compute_role_flags', store=True,
    )
    access_role_display = fields.Char(
        string='Role', compute='_compute_role_flags', store=True,
    )

    @api.depends('user_id', 'user_id.access_role_id')
    def _compute_access_role(self):
        for emp in self:
            emp.access_role_id = emp.user_id.access_role_id if emp.user_id else False

    def _inverse_access_role(self):
        """Allow editing Access Role on the staff form once a login exists.
        Writes back to the linked user, whose own write() syncs the security
        groups for the chosen role (see access_roles/models/res_users.py).
        Staff without a user account can't have a role and stay read-only."""
        for emp in self:
            if emp.user_id and emp.user_id.access_role_id != emp.access_role_id:
                emp.user_id.access_role_id = emp.access_role_id

    @api.depends('access_role_id', 'access_role_id.name')
    def _compute_role_flags(self):
        for emp in self:
            role_name = (emp.access_role_id.name or '').lower()
            emp.is_doctor_role = 'doctor' in role_name
            emp.is_nurse_role = 'nurse' in role_name
            emp.is_om_role = 'operations manager' in role_name
            emp.access_role_display = emp.access_role_id.name or ''
