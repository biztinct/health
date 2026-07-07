# -*- coding: utf-8 -*-
"""Coding sidecar on the clinical note (architecture-interop.md §2.3).

Non-destructive: this ADDS a coded-diagnosis m2m alongside the existing
free-text ``diagnosis`` field (some note fields are PHI-encrypted compute
fields — untouched here)."""

from odoo import fields, models


class HealthClinicalNote(models.Model):
    _inherit = 'health.clinical.note'

    condition_code_ids = fields.Many2many(
        'medical.code', 'clinical_note_condition_code_rel',
        'note_id', 'code_id', string='Coded Diagnoses (ICD-10)',
        domain="[('system_id.code', '=', 'icd10')]",
        help='ICD-10 coded diagnoses (sidecar to the free-text diagnosis; '
             'Circular 13/2025 EMR export).')
