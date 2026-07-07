# -*- coding: utf-8 -*-
"""Bulk CSV importer for medical codes (handover §2).

Idempotent upsert keyed on (system_id, code): existing rows are updated,
never duplicated; parents are resolved in a second pass (they may appear
after their children); malformed rows are counted and reported, never
aborting the whole import."""

import base64
import csv
import io

from odoo import _, api, fields, models

CSV_COLUMNS = ('code', 'display', 'display_vi', 'parent_code', 'synonyms')
BATCH_SIZE = 1000
MAX_ERRORS = 20


class MedicalCodeImport(models.TransientModel):
    _name = 'medical.code.import'
    _description = 'Medical Code Import'

    system_id = fields.Many2one(
        'medical.coding.system', string='Coding System', required=True)
    file = fields.Binary(string='CSV File', required=True)
    filename = fields.Char()
    delimiter = fields.Char(default=',', required=True,
                            help='CSV field delimiter.')
    has_header = fields.Boolean(default=True, string='File Has Header Row')
    created_count = fields.Integer(readonly=True)
    updated_count = fields.Integer(readonly=True)
    skipped_count = fields.Integer(readonly=True)
    error_text = fields.Text(readonly=True, string='Errors')

    def action_import(self):
        self.ensure_one()
        Code = self.env['medical.code']
        rows = self._read_rows()

        errors = []
        skipped = 0
        parsed = []          # (code, display, display_vi, parent_code, synonyms)
        seen_codes = set()
        for line_no, row in rows:
            if not row or all(not (cell or '').strip() for cell in row):
                continue  # blank line
            cells = [(row[idx].strip() if idx < len(row) else '')
                     for idx in range(len(CSV_COLUMNS))]
            code, display, display_vi, parent_code, synonyms = cells
            if not code or not display:
                skipped += 1
                if len(errors) < MAX_ERRORS:
                    errors.append(_('Row %s: missing code or display.')
                                  % line_no)
                continue
            if code in seen_codes:
                skipped += 1
                if len(errors) < MAX_ERRORS:
                    errors.append(_('Row %s: duplicate code "%s" in file.')
                                  % (line_no, code))
                continue
            seen_codes.add(code)
            parsed.append((code, display, display_vi, parent_code, synonyms))

        # -- upsert pass -------------------------------------------------
        existing = {c.code: c for c in Code.with_context(
            active_test=False).search([('system_id', '=', self.system_id.id)])}
        to_create = []
        updated = 0
        for code, display, display_vi, parent_code, synonyms in parsed:
            record = existing.get(code)
            if record:
                vals = {}
                if record.display != display:
                    vals['display'] = display
                if (record.display_vi or '') != display_vi:
                    vals['display_vi'] = display_vi or False
                if (record.synonyms or '') != synonyms:
                    vals['synonyms'] = synonyms or False
                if vals:
                    record.write(vals)
                    updated += 1
            else:
                to_create.append({
                    'system_id': self.system_id.id,
                    'code': code,
                    'display': display,
                    'display_vi': display_vi or False,
                    'synonyms': synonyms or False,
                })

        created = 0
        for start in range(0, len(to_create), BATCH_SIZE):
            batch = to_create[start:start + BATCH_SIZE]
            Code.create(batch)
            created += len(batch)

        # -- parent-resolution pass (parents may post-date their children) --
        all_codes = {c.code: c for c in Code.with_context(
            active_test=False).search([('system_id', '=', self.system_id.id)])}
        for code, display, display_vi, parent_code, synonyms in parsed:
            if not parent_code:
                continue
            record = all_codes.get(code)
            parent = all_codes.get(parent_code)
            if parent and record and record.parent_id.id != parent.id:
                record.parent_id = parent.id
            elif not parent and len(errors) < MAX_ERRORS:
                errors.append(_('Code "%s": unknown parent_code "%s".')
                              % (code, parent_code))

        self.write({
            'created_count': created,
            'updated_count': updated,
            'skipped_count': skipped,
            'error_text': '\n'.join(errors) or False,
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'medical.code.import',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'name': _('Import Medical Codes'),
        }

    def _read_rows(self):
        """Decode the upload (utf-8-sig strips the Excel BOM) → list of
        (1-based line number, row cells)."""
        content = base64.b64decode(self.file or b'')
        text = content.decode('utf-8-sig', errors='replace')
        reader = csv.reader(io.StringIO(text),
                            delimiter=(self.delimiter or ','))
        rows = list(enumerate(reader, start=1))
        if self.has_header and rows:
            rows = rows[1:]
        return rows
