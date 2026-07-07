# -*- coding: utf-8 -*-
"""Clinical note extension (clinical spec §2.2.4).

The free-text ``vital_signs`` field is KEPT untouched (coding-sidecar
pattern — structured rows sit alongside, never replace). NOTE: the
narrative fields on health.clinical.note (incl. vital_signs) are
encrypted computed fields when health_phi_encryption is installed —
always read/write them through the ORM, never SQL.
``has_structured_vitals`` is a plain stored Boolean (not encrypted).
"""
from odoo import api, fields, models


class HealthClinicalNote(models.Model):
    _inherit = 'health.clinical.note'

    observation_ids = fields.One2many(
        'health.observation', 'clinical_note_id',
        string='Structured Vitals')
    has_structured_vitals = fields.Boolean(
        string='Structured', compute='_compute_has_structured_vitals',
        store=True)

    @api.depends('observation_ids')
    def _compute_has_structured_vitals(self):
        for note in self:
            note.has_structured_vitals = bool(note.observation_ids)
