# -*- coding: utf-8 -*-
from odoo import models, fields

class HrEmployeePublic(models.Model):
    _inherit = 'hr.employee.public'

    is_healthcare_staff = fields.Boolean(
        'Healthcare Staff',
        readonly=True
    )

    healthcare_role = fields.Selection([
        ('doctor', 'Doctor'),
        ('nurse', 'Nurse'),
        ('specialist', 'Specialist'),
        ('therapist', 'Therapist'),
        ('technician', 'Technician'),
        ('support', 'Support Staff'),
        ('operations_manager', 'Operations Manager')
    ], string='Healthcare Role', readonly=True)
