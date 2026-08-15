# -*- coding: utf-8 -*-
"""Vital-sign / observation catalog (clinical spec §2.2.1).

One row per LOINC-coded observation type. Panels (blood pressure) carry
no value themselves; their components point back through ``parent_id``
(FHIR ``Observation.component`` grouping).
"""
from odoo import api, fields, models


class HealthVitalsType(models.Model):
    _name = 'health.vitals.type'
    _description = 'Vital Sign / Observation Type'
    _inherit = ['health.vi.alias.mixin']
    _order = 'sequence, name'

    name = fields.Char(
        required=True, translate=True,
        help="English display name (FHIR code.coding.display).")
    # Mirrors the vi_VN translation of `name` instead of being a second
    # column — a many2one dropdown renders `name`, so a standalone name_vi was
    # never visible where users pick the value. See health.vi.alias.mixin.
    name_vi = fields.Char(
        string='Vietnamese Name', compute='_compute_vi_alias',
        inverse='_inverse_vi_alias', store=False)
    code = fields.Char(
        required=True,
        help="Internal short code (bp_sys, hr, ...) used by the PWA "
             "and data seeds.")
    loinc_code = fields.Char(
        string='LOINC Code', required=True, index=True,
        help="LOINC code (FHIR code.coding.code, system "
             "http://loinc.org).")
    ucum_unit = fields.Char(
        string='UCUM Unit',
        help="UCUM unit code (mm[Hg], Cel, kg, /min, %, cm, mmol/L) — "
             "FHIR valueQuantity.code.")
    unit_display = fields.Char(
        string='Unit Display',
        help="Human-readable unit (mmHg, °C, bpm) — FHIR "
             "valueQuantity.unit.")
    value_type = fields.Selection([
        ('quantity', 'Numeric'),
        ('string', 'Text'),
        ('panel', 'Panel (no value)'),
    ], default='quantity', required=True,
        help="Panels (blood pressure) carry no value themselves.")
    parent_id = fields.Many2one(
        'health.vitals.type', string='Panel',
        help="Component-to-panel link (systolic → BP panel); FHIR "
             "Observation.component grouping.")
    child_ids = fields.One2many(
        'health.vitals.type', 'parent_id', string='Panel Members')
    decimals = fields.Integer(default=0, help='Display precision.')
    plausible_min = fields.Float(
        help='Hard input-validation lower bound (not a clinical alert).')
    plausible_max = fields.Float(
        help='Hard input-validation upper bound (not a clinical alert).')
    default_method = fields.Char(help="e.g. 'oscillometric'")
    is_fhir_vital_sign = fields.Boolean(
        string='FHIR Vital Sign', default=False,
        help="Member of the FHIR vital-signs profile (adds category "
             "'vital-signs').")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('uniq_loinc', 'UNIQUE(loinc_code)', 'LOINC code must be unique.'),
        ('uniq_code', 'UNIQUE(code)', 'Internal code must be unique.'),
    ]

    def init(self):
        # Odoo 19 no longer materializes _sql_constraints — create the
        # unique indexes explicitly.
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
                health_vitals_type_loinc_uidx
            ON health_vitals_type (loinc_code)
        """)
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
                health_vitals_type_code_uidx
            ON health_vitals_type (code)
        """)

    @api.model
    def get_by_code(self, loinc_code):
        """Resolve a catalog row by LOINC code (public interface, used
        by health_forms and health.observation.create_coded).

        Falls back to the internal short code (hr, bp_sys, ...) so PWA
        payload codes resolve through the same entry point. Returns an
        empty recordset when unknown (caller decides how to fail).
        Archived types are still resolvable (inbound interop).
        """
        domain_ctx = self.with_context(active_test=False)
        vtype = domain_ctx.search([('loinc_code', '=', loinc_code)], limit=1)
        if not vtype:
            vtype = domain_ctx.search([('code', '=', loinc_code)], limit=1)
        return vtype
