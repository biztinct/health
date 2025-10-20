# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class HealthFSOClinicalNotesWizard(models.TransientModel):
    """
    Wizard for viewing and editing clinical notes from FSO Dashboard
    """
    _name = 'health.fso.clinical.notes.wizard'
    _description = 'FSO Clinical Notes Wizard'

    fso_id = fields.Many2one(
        'health.fieldservice.order',
        string='Booking',
        required=True,
        ondelete='cascade'
    )

    patient_id = fields.Many2one(
        'res.partner',
        related='fso_id.patient_id',
        string='Patient',
        readonly=True
    )

    service_type = fields.Selection(
        related='fso_id.service_type',
        string='Service Type',
        readonly=True
    )

    scheduled_datetime = fields.Datetime(
        related='fso_id.scheduled_datetime',
        string='Scheduled Date & Time',
        readonly=True
    )

    actual_start_datetime = fields.Datetime(
        related='fso_id.actual_start_datetime',
        string='Service Start Time',
        readonly=True
    )

    actual_end_datetime = fields.Datetime(
        related='fso_id.actual_end_datetime',
        string='Service End Time',
        readonly=True
    )

    # Editable Clinical Fields
    symptoms = fields.Text(
        string='Symptoms/Chief Complaint',
        help='Patient\'s reported symptoms or reason for visit'
    )

    diagnosis = fields.Html(
        string='Diagnosis',
        help='Medical diagnosis (Chuẩn đoán) - MOH compliance field'
    )

    clinical_notes = fields.Html(
        string='Clinical Notes',
        help='Clinical observations and notes from service provider'
    )

    treatment_performed = fields.Text(
        string='Treatment Performed',
        help='Detailed description of treatment provided'
    )

    medications_prescribed = fields.Text(
        string='Medications Prescribed',
        help='Medications prescribed during service'
    )

    vital_signs = fields.Text(
        string='Vital Signs',
        help='Recorded vital signs during service'
    )

    patient_condition_before = fields.Text(
        string='Patient Condition (Before)',
        help='Patient condition before service'
    )

    patient_condition_after = fields.Text(
        string='Patient Condition (After)',
        help='Patient condition after service'
    )

    follow_up_required = fields.Boolean(
        string='Follow-up Required'
    )

    follow_up_date = fields.Date(
        string='Follow-up Date'
    )

    follow_up_notes = fields.Text(
        string='Follow-up Notes'
    )

    clinical_notes_submitted = fields.Boolean(
        related='fso_id.clinical_notes_submitted',
        string='Clinical Notes Submitted',
        readonly=True
    )

    @api.model
    def default_get(self, fields_list):
        """Pre-populate wizard with FSO data"""
        res = super().default_get(fields_list)

        fso_id = self.env.context.get('default_fso_id')
        if fso_id:
            fso = self.env['health.fieldservice.order'].browse(fso_id)
            res.update({
                'symptoms': fso.symptoms,
                'diagnosis': fso.diagnosis,
                'clinical_notes': fso.clinical_notes,
                'treatment_performed': fso.treatment_performed,
                'medications_prescribed': fso.medications_prescribed,
                'vital_signs': fso.vital_signs,
                'patient_condition_before': fso.patient_condition_before,
                'patient_condition_after': fso.patient_condition_after,
                'follow_up_required': fso.follow_up_required,
                'follow_up_date': fso.follow_up_date,
                'follow_up_notes': fso.follow_up_notes,
            })

        return res

    def action_save_clinical_notes(self):
        """Save clinical notes to FSO and close wizard"""
        self.ensure_one()

        # Update FSO with clinical notes
        self.fso_id.write({
            'symptoms': self.symptoms,
            'diagnosis': self.diagnosis,
            'clinical_notes': self.clinical_notes,
            'treatment_performed': self.treatment_performed,
            'medications_prescribed': self.medications_prescribed,
            'vital_signs': self.vital_signs,
            'patient_condition_before': self.patient_condition_before,
            'patient_condition_after': self.patient_condition_after,
            'follow_up_required': self.follow_up_required,
            'follow_up_date': self.follow_up_date,
            'follow_up_notes': self.follow_up_notes,
        })

        # Post message to chatter
        self.fso_id.message_post(
            body=_('Clinical notes updated from dashboard'),
            subject='Clinical Notes Updated',
            message_type='notification'
        )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Clinical Notes Saved'),
                'message': _('Clinical notes have been updated successfully.'),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_save_and_close(self):
        """Save and close wizard"""
        self.action_save_clinical_notes()
        return {'type': 'ir.actions.act_window_close'}
