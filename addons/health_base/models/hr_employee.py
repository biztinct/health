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
        ('operations_manager', 'Operations Manager'),
        ('admin', 'Admin'),
        ('owner', 'Owner'),
        ('accountant', 'Accountant'),
    ], string='Healthcare Role (Deprecated)', tracking=True)

    is_duty_doctor = fields.Boolean('Is Duty Doctor', default=False, tracking=True)
    is_head_nurse = fields.Boolean('Is Head Nurse', default=False, tracking=True)

    # ===================================================================
    # WHAT SOMEBODY'S JOB MAKES THEM — DECLARED HERE, DECIDED ABOVE.
    #
    # These four are read in sixty-odd places across a dozen modules: the staff
    # pickers, the roster, the booking form, the schedule, the offline app, the
    # author line on a clinical note. What they MEAN is now a job somebody was
    # given — a role bundle — and that is a model this module cannot know
    # about: `health_base` is the root of the tree and the Access home sits
    # well above it. So the ANSWER is computed up there
    # (`health_access/models/hr_employee.py`) and only the QUESTION is asked
    # here.
    #
    # THEY ARE DECLARED HERE AND NOT MOVED, AND THAT IS NOT TIDINESS. Moving
    # them broke the registry outright: `health_fieldservice` names
    # `is_doctor_role` in an `@api.depends`, and a dependency is resolved when
    # THAT module's models are set up — before anything above it has been
    # loaded. A field that only exists higher in the graph does not exist yet
    # at that moment, and the whole database refuses to load. Declaring the
    # field here and overriding it above is what lets both be true.
    #
    # On a database without the Access home they are simply never computed:
    # nobody is a doctor, nobody is a nurse, and the label is empty — which is
    # the honest answer for a system with no roles in it.
    # ===================================================================
    is_doctor_role = fields.Boolean(store=True)
    is_nurse_role = fields.Boolean(store=True)
    is_om_role = fields.Boolean(store=True)
    access_role_display = fields.Char(string='Role', store=True)
