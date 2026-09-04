# -*- coding: utf-8 -*-
"""The job on the staff record, and the four things the rest of the product
reads off it.

THE FIELD NAMES ARE NOT NEW AND THAT IS THE POINT. `is_doctor_role`,
`is_nurse_role`, `is_om_role` and `access_role_display` are read in sixty-odd
places — staff pickers, the roster, the booking form, the schedule, the PWA,
the clinical note's author line. What they MEAN is now a job somebody chose
rather than a word in a role's name; what they are CALLED has not moved, so
nothing that reads them had to change.

MIRRORED BOTH WAYS, EXACTLY AS BEFORE. The job lives on the login and is shown
on the staff record, because that is the screen this clinic edits people on. A
staff member with no login has no job to show, and the field is read-only for
them — there is nothing for it to write to.
"""

from odoo import api, fields, models

from .res_users import JOB_HELP


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    # "Employed as" rather than "Job" ON THIS MODEL ONLY. The staff record
    # already has a `job_id` labelled Job — the job POSITION somebody was hired
    # into — and two fields with one label is a form nobody can read (and a
    # warning on every registry load). The login's own copy keeps "Job",
    # because nothing there competes for the word.
    job_role_id = fields.Many2one(
        'biz.access.role', string='Employed as', ondelete='restrict',
        domain="[('active', '=', True)]",
        compute='_compute_job_role', inverse='_inverse_job_role',
        store=True, readonly=False, help=JOB_HELP)

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

    @api.depends('user_id', 'user_id.job_role_id')
    def _compute_job_role(self):
        for emp in self:
            emp.job_role_id = emp.user_id.job_role_id if emp.user_id else False

    def _inverse_job_role(self):
        """Write it back to the login, which is where the job actually lives.

        The login's own `write` is what grants the role; this only carries the
        value there, so a staff record and a passport can never disagree about
        somebody's job. Staff without a login are skipped rather than refused —
        the field is read-only for them on the form.
        """
        for emp in self:
            if emp.user_id and emp.user_id.job_role_id != emp.job_role_id:
                emp.user_id.job_role_id = emp.job_role_id

    @api.depends('job_role_id', 'job_role_id.clinical_kind',
                 'job_role_id.name')
    def _compute_role_flags(self):
        for emp in self:
            kind = emp.job_role_id.clinical_kind if emp.job_role_id else False
            emp.is_doctor_role = kind == 'doctor'
            emp.is_nurse_role = kind == 'nurse'
            emp.is_om_role = kind == 'operations_manager'
            emp.access_role_display = emp.job_role_id.name or ''
