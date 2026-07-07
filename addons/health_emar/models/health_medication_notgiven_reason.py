# -*- coding: utf-8 -*-
"""Not-given / refused reason lookup (spec §3.2.4).

Aged-care audit requirement: every administration recorded as
``not_given`` or ``refused`` MUST carry one of these coded reasons
(FHIR MedicationAdministration.statusReason).
"""
from odoo import fields, models


class HealthMedicationNotgivenReason(models.Model):
    _name = 'health.medication.notgiven.reason'
    _description = 'Medication Not-Given Reason'
    _order = 'sequence, name'

    name = fields.Char(required=True, translate=True)
    name_vi = fields.Char(string='Vietnamese Name')
    code = fields.Char(required=True)
    applies_to = fields.Selection([
        ('refused', 'Refused'),
        ('not_given', 'Not Given'),
        ('both', 'Both'),
    ], default='both', required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    def init(self):
        # Odoo 19 does not materialize _sql_constraints — create the
        # unique index explicitly (platform gotcha).
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
                health_medication_notgiven_reason_code_uidx
            ON health_medication_notgiven_reason (code)
        """)
