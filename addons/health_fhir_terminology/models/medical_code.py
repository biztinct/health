# -*- coding: utf-8 -*-
"""Local terminology code table (architecture-interop.md §2).

Vietnamese-first display and typeahead: ``display_name`` and ``name_search``
prefer ``display_vi`` so ``many2many_tags`` pickers get MOH-language search
for free (spec §2.3). Imported codes are archived, never unlinked.

The ``fhir_lookup`` / ``fhir_expand`` classmethods build the CodeSystem/$lookup
and ValueSet/$expand payloads; the controller is a thin HTTP wrapper over them
so the logic stays testable without an HTTP client."""

from datetime import datetime

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class MedicalCode(models.Model):
    _name = 'medical.code'
    _description = 'Medical Code'
    _order = 'system_id, code'

    system_id = fields.Many2one(
        'medical.coding.system', string='Coding System', required=True,
        ondelete='restrict', index=True)
    code = fields.Char(required=True, index=True,
                       help='e.g. I10, 8867-4.')
    display = fields.Char(required=True, help='English display.')
    display_vi = fields.Char(string='Vietnamese Display',
                             help='MOH translation.')
    parent_id = fields.Many2one(
        'medical.code', string='Parent', ondelete='set null',
        help='Hierarchy (ICD-10 chapter/block).')
    synonyms = fields.Char(
        help='Semicolon-separated alternates, searched by the typeahead.')
    active = fields.Boolean(default=True)
    display_name = fields.Char(compute='_compute_display_name', store=True)

    def init(self):
        # Odoo 19 does not materialize _sql_constraints (conventions §5.1).
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
                medical_code_system_code_uidx
            ON medical_code (system_id, code)
        """)

    @api.depends('code', 'display', 'display_vi')
    def _compute_display_name(self):
        for record in self:
            label = record.display_vi or record.display or ''
            record.display_name = '[%s] %s' % (record.code or '', label)

    @api.model_create_multi
    def create(self, vals_list):
        # Pre-check (system_id, code) BEFORE super() so a duplicate raises a
        # ValidationError instead of the unique index's IntegrityError, which
        # would poison the transaction (conventions §5.3).
        seen = set()
        for vals in vals_list:
            system_id, code = vals.get('system_id'), vals.get('code')
            if system_id and code:
                key = (system_id, code)
                if key in seen or self.search_count([
                        ('system_id', '=', system_id), ('code', '=', code)]):
                    raise ValidationError(_(
                        'Code "%s" already exists in this coding system.')
                        % code)
                seen.add(key)
        return super().create(vals_list)

    @api.model
    def name_search(self, name='', domain=None, operator='ilike', limit=100):
        """Vietnamese-first typeahead: prefix match on code, ilike on
        display / display_vi / synonyms, OR-combined."""
        domain = list(domain or [])
        if name:
            search_domain = [
                '|', '|', '|',
                ('code', '=ilike', name + '%'),
                ('display', 'ilike', name),
                ('display_vi', 'ilike', name),
                ('synonyms', 'ilike', name),
            ]
            records = self.search(search_domain + domain, limit=limit)
            return [(record.id, record.display_name) for record in records]
        return super().name_search(
            name=name, domain=domain, operator=operator, limit=limit)

    @api.model
    def get(self, system_code, code):
        """Resolve one code by (system short code, code) — empty recordset
        when unknown (mirrors health.vitals.type.get_by_code ergonomics)."""
        return self.with_context(active_test=False).search([
            ('system_id.code', '=', system_code),
            ('code', '=', code),
        ], limit=1)

    # ------------------------------------------------------------------
    # FHIR terminology operation payloads (testable without HTTP)
    # ------------------------------------------------------------------
    @api.model
    def fhir_lookup(self, system_uri, code):
        """CodeSystem/$lookup → FHIR Parameters dict, or None when the
        system/code is unknown."""
        system = self.env['medical.coding.system'].search(
            [('uri', '=', system_uri)], limit=1)
        if not system:
            return None
        record = self.search([
            ('system_id', '=', system.id), ('code', '=', code),
        ], limit=1)
        if not record:
            return None
        parameters = [
            {'name': 'name', 'valueString': system.name or system.code or ''},
            {'name': 'display',
             'valueString': record.display or record.display_vi or ''},
        ]
        if system.version:
            parameters.append(
                {'name': 'version', 'valueString': system.version})
        if record.display_vi:
            parameters.append({
                'name': 'designation',
                'part': [
                    {'name': 'language', 'valueCode': 'vi'},
                    {'name': 'value', 'valueString': record.display_vi},
                ],
            })
        return {'resourceType': 'Parameters', 'parameter': parameters}

    @api.model
    def fhir_expand(self, system_uri, filter_text=None, count=20):
        """ValueSet/$expand → dynamically-built FHIR ValueSet dict, or None
        when the system URI is unknown. ``count`` is clamped to 1..50."""
        system = self.env['medical.coding.system'].search(
            [('uri', '=', system_uri)], limit=1)
        if not system:
            return None
        try:
            count = int(count or 20)
        except (TypeError, ValueError):
            count = 20
        count = max(1, min(count, 50))
        base_domain = [('system_id', '=', system.id), ('active', '=', True)]
        if filter_text:
            matches = self.name_search(
                name=filter_text, domain=base_domain, limit=count)
            records = self.browse([match[0] for match in matches])
        else:
            records = self.search(base_domain, limit=count)
        contains = [{
            'system': system.uri,
            'code': record.code,
            'display': record.display or record.display_vi or '',
        } for record in records]
        return {
            'resourceType': 'ValueSet',
            'status': 'active',
            'expansion': {
                'timestamp': datetime.utcnow().replace(
                    microsecond=0).isoformat() + '+00:00',
                'total': len(contains),
                'contains': contains,
            },
        }
