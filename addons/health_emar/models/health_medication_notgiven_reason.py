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
    _inherit = ['health.vi.alias.mixin']
    _order = 'sequence, name'

    name = fields.Char(required=True, translate=True)
    # Mirrors the vi_VN translation of `name` instead of being a second
    # column — a many2one dropdown renders `name`, so a standalone name_vi was
    # never visible where users pick the value. See health.vi.alias.mixin.
    name_vi = fields.Char(
        string='Vietnamese Name', compute='_compute_vi_alias',
        inverse='_inverse_vi_alias', store=False)
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
