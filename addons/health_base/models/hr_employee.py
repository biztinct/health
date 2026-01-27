# -*- coding: utf-8 -*-
from odoo import models, fields


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
        ('operations_manager', 'Operations Manager')
    ], string='Healthcare Role', tracking=True)
