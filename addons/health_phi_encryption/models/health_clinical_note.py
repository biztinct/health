# -*- coding: utf-8 -*-
"""Transparent PHI encryption for clinical note narrative fields."""
from odoo import api, fields, models

from . import phi_crypto

NOTE_PHI_MAP = {
    'clinical_notes': ('clinical_notes_enc', None),
    'diagnosis': ('diagnosis_enc', None),
    'treatment_performed': ('treatment_performed_enc', None),
    'medications_prescribed': ('medications_prescribed_enc', None),
    'vital_signs': ('vital_signs_enc', None),
    'patient_condition_before': ('patient_condition_before_enc', None),
    'patient_condition_after': ('patient_condition_after_enc', None),
}


class HealthClinicalNote(models.Model):
    _inherit = 'health.clinical.note'

    _phi_map = NOTE_PHI_MAP

    # --- encrypted storage -------------------------------------------------
    clinical_notes_enc = fields.Text('Clinical Notes (encrypted)')
    diagnosis_enc = fields.Text('Diagnosis (encrypted)')
    treatment_performed_enc = fields.Text('Treatment Performed (encrypted)')
    medications_prescribed_enc = fields.Text('Medications Prescribed (encrypted)')
    vital_signs_enc = fields.Text('Vital Signs (encrypted)')
    patient_condition_before_enc = fields.Text('Condition Before (encrypted)')
    patient_condition_after_enc = fields.Text('Condition After (encrypted)')

    # --- exposed fields (names/labels unchanged) ----------------------------
    clinical_notes = fields.Html(
        'Clinical Notes',
        compute='_compute_phi_fields', inverse='_inverse_phi_fields')
    diagnosis = fields.Text(
        'Diagnosis',
        compute='_compute_phi_fields', inverse='_inverse_phi_fields')
    treatment_performed = fields.Text(
        'Treatment Performed',
        compute='_compute_phi_fields', inverse='_inverse_phi_fields')
    medications_prescribed = fields.Text(
        'Medications Prescribed',
        compute='_compute_phi_fields', inverse='_inverse_phi_fields')
    vital_signs = fields.Text(
        'Vital Signs',
        compute='_compute_phi_fields', inverse='_inverse_phi_fields')
    patient_condition_before = fields.Text(
        'Patient Condition (Before)',
        compute='_compute_phi_fields', inverse='_inverse_phi_fields')
    patient_condition_after = fields.Text(
        'Patient Condition (After)',
        compute='_compute_phi_fields', inverse='_inverse_phi_fields')

    @api.depends(*(enc for enc, _b in NOTE_PHI_MAP.values()))
    def _compute_phi_fields(self):
        for rec in self:
            for exposed, (enc, _bidx) in self._phi_map.items():
                rec[exposed] = phi_crypto.decrypt(self.env, rec[enc]) or False

    def _inverse_phi_fields(self):
        for rec in self:
            for exposed, (enc, _bidx) in self._phi_map.items():
                value = rec[exposed]
                rec[enc] = phi_crypto.encrypt(self.env, value) if value else False
