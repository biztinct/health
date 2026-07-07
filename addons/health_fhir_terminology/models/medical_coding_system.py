# -*- coding: utf-8 -*-
"""Local terminology system table (architecture-interop.md §2).

One row per code system (ICD-10, LOINC, UCUM, …). The canonical ``uri`` and
the short ``code`` are both unique (indexes created in ``init()`` — Odoo 19
does not materialize ``_sql_constraints``)."""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class MedicalCodingSystem(models.Model):
    _name = 'medical.coding.system'
    _description = 'Medical Coding System'
    _order = 'name'

    name = fields.Char(required=True, translate=True,
                       help='Human name, e.g. "ICD-10 (WHO + MOH VN)".')
    uri = fields.Char(required=True,
                      help='Canonical system URI (FHIR CodeSystem.url).')
    code = fields.Char(required=True,
                       help='Short key: icd10, loinc, ucum, rxnorm, snomed, '
                            'health19-services.')
    version = fields.Char(help='Free text, e.g. "2019".')
    description = fields.Text()
    active = fields.Boolean(default=True)
    code_count = fields.Integer(
        compute='_compute_code_count', string='Codes',
        help='Number of codes registered under this system.')

    def init(self):
        # Odoo 19 does not materialize _sql_constraints — create the unique
        # indexes explicitly (conventions §5.1).
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
                medical_coding_system_uri_uidx
            ON medical_coding_system (uri)
        """)
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
                medical_coding_system_code_uidx
            ON medical_coding_system (code)
        """)

    def _compute_code_count(self):
        Code = self.env['medical.code'].with_context(active_test=False)
        for system in self:
            system.code_count = (
                Code.search_count([('system_id', '=', system.id)])
                if system.id else 0)

    @api.model_create_multi
    def create(self, vals_list):
        # Pre-check uniqueness BEFORE super() so callers get a
        # ValidationError rather than the unique index's IntegrityError,
        # which would poison the transaction (conventions §5.3).
        seen_uris, seen_codes = set(), set()
        for vals in vals_list:
            uri, code = vals.get('uri'), vals.get('code')
            if uri:
                if uri in seen_uris or self.search_count([('uri', '=', uri)]):
                    raise ValidationError(_(
                        'A coding system with URI "%s" already exists.') % uri)
                seen_uris.add(uri)
            if code:
                if code in seen_codes or self.search_count(
                        [('code', '=', code)]):
                    raise ValidationError(_(
                        'A coding system with code "%s" already exists.')
                        % code)
                seen_codes.add(code)
        return super().create(vals_list)
