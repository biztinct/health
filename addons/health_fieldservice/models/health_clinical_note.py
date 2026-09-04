from odoo import models, fields, api


class HealthClinicalNote(models.Model):
    _name = 'health.clinical.note'
    _description = 'Clinical Note'
    _order = 'create_date desc'
    _rec_name = 'display_name'

    order_id = fields.Many2one(
        'health.fieldservice.order',
        string='Service Order',
        required=True,
        ondelete='cascade',
        index=True,
    )
    author_id = fields.Many2one(
        'res.users',
        string='Author',
        default=lambda self: self.env.uid,
        readonly=True,
    )
    # Catchment area, taken from the visit the note belongs to. Stored so the
    # Unsigned Notes list can be filtered and record-ruled on it; a note has no
    # area of its own, it inherits the visit's.
    catchment_province_id = fields.Many2one(
        'health.catchment.province', string='Catchment Area',
        related='order_id.catchment_province_id', store=True, index=True,
        readonly=True)
    author_name = fields.Char(related='author_id.name', store=True)
    author_role = fields.Char(
        string='Role',
        compute='_compute_author_role',
        store=True,
    )

    clinical_notes = fields.Html('Clinical Notes')
    diagnosis = fields.Text('Diagnosis')
    treatment_performed = fields.Text('Treatment Performed')
    medications_prescribed = fields.Text('Medications Prescribed')
    vital_signs = fields.Text('Vital Signs')
    patient_condition_before = fields.Text('Patient Condition (Before)')
    patient_condition_after = fields.Text('Patient Condition (After)')

    injection_count = fields.Integer('Injections Given', default=0)
    medication_count = fields.Integer('Medications Given', default=0)
    wound_count = fields.Integer('Wounds Treated', default=0)
    iv_fluid_count = fields.Integer('IV Fluid Bags', default=0)

    image_ids = fields.Many2many(
        'ir.attachment',
        'health_clinical_note_image_rel',
        'note_id', 'attachment_id',
        string='Clinical Images',
    )

    display_name = fields.Char(
        compute='_compute_display_name',
        store=True,
    )

    @api.depends('author_id', 'create_date')
    def _compute_display_name(self):
        for rec in self:
            date_str = rec.create_date.strftime('%d/%m/%Y %H:%M') if rec.create_date else 'New'
            author = rec.author_id.name or 'Unknown'
            rec.display_name = f"{author} - {date_str}"

    @api.depends('author_id')
    def _compute_author_role(self):
        for rec in self:
            role = ''
            if rec.author_id:
                user = rec.author_id
                # THE SAME WORDS AS BEFORE, off a different field. The job used
                # to be a pointer at the previous access application's row and
                # is now a role bundle; the NAME it resolves to is the same, so
                # every note already sealed still verifies against it.
                if user.job_role_id:
                    role = user.job_role_id.name
                if not role:
                    employee = self.env['hr.employee'].search(
                        [('user_id', '=', user.id)], limit=1
                    )
                    if employee and employee.access_role_display:
                        role = employee.access_role_display
            rec.author_role = role or 'Staff'
