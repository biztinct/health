# -*- coding: utf-8 -*-
import base64
import csv
import io
import re
from datetime import datetime

from psycopg2.extras import execute_values

from odoo import _, fields, models
from odoo.exceptions import UserError
from odoo.tools import SQL

COLUMN_NAME_RE = re.compile(r'[^a-z0-9_]+')
DATE_FORMATS = ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%d/%m/%y')
DATETIME_FORMATS = ('%d/%m/%Y %H:%M:%S', '%Y-%m-%d %H:%M:%S',
                    '%d/%m/%Y %H:%M')
SAMPLE_ROWS = 1000
MAX_ROWS = 500000


class BiCsvImportWizard(models.TransientModel):
    """Upload a CSV/Excel-exported-CSV file into a typed Bronze staging
    table (bi_stage_<source_id>) and optionally create a dataset on it."""
    _name = 'bi.csv.import.wizard'
    _description = 'BI CSV Import'

    name = fields.Char(string='Source Name', required=True)
    file = fields.Binary(required=True)
    filename = fields.Char()
    has_header = fields.Boolean(default=True, string='First row is header')
    date_format_hint = fields.Selection([
        ('%d/%m/%Y', 'DD/MM/YYYY (Vietnam default)'),
        ('%Y-%m-%d', 'YYYY-MM-DD (ISO)'),
        ('%m/%d/%Y', 'MM/DD/YYYY (US)'),
    ], default='%d/%m/%Y', string='Date Format')
    existing_source_id = fields.Many2one(
        'bi.source', domain=[('type', '=', 'csv')],
        string='Replace Existing Source',
        help="Leave empty to create a new source; select one to replace its "
             "staged data.")
    create_dataset = fields.Boolean(default=True,
                                    string='Create a dataset from this file')
    workspace_id = fields.Many2one(
        'bi.workspace',
        default=lambda self: self.env['bi.workspace'].search(
            [('is_default', '=', True)], limit=1))

    # ------------------------------------------------------------------

    def action_import(self):
        self.ensure_one()
        rows, headers = self._parse_file()
        if not rows:
            raise UserError(_("The file has no data rows."))
        if len(rows) > MAX_ROWS:
            raise UserError(_("File too large (max %s rows).", MAX_ROWS))

        column_names = self._sanitize_columns(headers, len(rows[0]))
        column_types = self._infer_types(rows)

        source = self.existing_source_id
        if not source:
            source = self.env['bi.source'].create({
                'name': self.name, 'type': 'csv', 'state': 'ready'})
        table = source.stage_table

        self._create_stage_table(table, column_names, column_types)
        self._load_rows(table, column_names, column_types, rows)
        source.write({'last_sync': fields.Datetime.now(), 'state': 'ready'})
        self.env['bi.audit.log'].sudo().log(
            'csv_import', record=source,
            payload={'rows': len(rows), 'columns': column_names})

        if self.create_dataset and not self.existing_source_id:
            dataset = self.env['bi.dataset'].create({
                'name': self.name,
                'workspace_id': self.workspace_id.id,
            })
            node = self.env['bi.dataset.node'].create({
                'dataset_id': dataset.id, 'source_id': source.id,
                'is_root': True})
            node.action_scan_fields()
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'bi.dataset',
                'res_id': dataset.id,
                'view_mode': 'form',
                'target': 'current',
            }
        return {'type': 'ir.actions.act_window_close'}

    # ------------------------------------------------------------------

    def _parse_file(self):
        raw = base64.b64decode(self.file)
        text = None
        for encoding in ('utf-8-sig', 'utf-8', 'cp1258', 'latin-1'):
            try:
                text = raw.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        if text is None:
            raise UserError(_("Could not decode the file — save it as UTF-8."))
        sample = text[:8192]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=',;\t|')
        except csv.Error:
            dialect = csv.excel
        reader = csv.reader(io.StringIO(text), dialect)
        all_rows = [row for row in reader if any(cell.strip() for cell in row)]
        if not all_rows:
            return [], []
        if self.has_header:
            return all_rows[1:], all_rows[0]
        return all_rows, []

    def _sanitize_columns(self, headers, width):
        names, seen = [], set()
        for index in range(width):
            header = headers[index].strip().lower() if index < len(headers) \
                else ''
            name = COLUMN_NAME_RE.sub('_', header).strip('_')
            if not name or not name[0].isalpha():
                name = 'col_%d' % (index + 1)
            base = name
            counter = 2
            while name in seen or name.startswith('_bi_'):
                name = '%s_%d' % (base, counter)
                counter += 1
            seen.add(name)
            names.append(name)
        return names

    def _infer_types(self, rows):
        """Column types from a sample: integer -> float -> datetime -> date
        -> boolean -> text (most specific type that fits every sample)."""
        width = len(rows[0])
        types = []
        for col in range(width):
            values = [row[col].strip() for row in rows[:SAMPLE_ROWS]
                      if col < len(row) and row[col].strip()]
            types.append(self._infer_one(values))
        return types

    def _infer_one(self, values):
        if not values:
            return 'text'
        checks = [
            ('integer', lambda v: re.fullmatch(r'-?\d{1,18}', v)),
            ('float', self._is_float),
            ('datetime', lambda v: self._parse_dt(v, DATETIME_FORMATS)),
            ('date', lambda v: self._parse_dt(
                v, (self.date_format_hint,) + DATE_FORMATS)),
            ('boolean', lambda v: v.lower() in
                ('true', 'false', '0', '1', 'yes', 'no')),
        ]
        for type_name, check in checks:
            if all(check(v) for v in values):
                return type_name
        return 'text'

    @staticmethod
    def _is_float(value):
        try:
            float(value.replace(',', '.'))
            return True
        except ValueError:
            return False

    @staticmethod
    def _parse_dt(value, formats):
        for fmt in formats:
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        return None

    PG_TYPES = {'integer': 'bigint', 'float': 'numeric', 'date': 'date',
                'datetime': 'timestamp', 'boolean': 'boolean',
                'text': 'text'}

    def _create_stage_table(self, table, names, types):
        cr = self.env.cr
        cr.execute(SQL("DROP TABLE IF EXISTS %s CASCADE",
                       SQL.identifier(table)))
        columns = [SQL("_bi_row_id bigserial PRIMARY KEY"),
                   SQL("_bi_loaded_at timestamp DEFAULT (now() AT TIME ZONE 'UTC')")]
        for name, type_name in zip(names, types):
            columns.append(SQL("%s " + self.PG_TYPES[type_name],
                               SQL.identifier(name)))
        cr.execute(SQL("CREATE TABLE %s (%s)",
                       SQL.identifier(table), SQL(", ").join(columns)))

    def _convert(self, value, type_name):
        value = (value or '').strip()
        if not value:
            return None
        if type_name == 'integer':
            return int(value)
        if type_name == 'float':
            return float(value.replace(',', '.'))
        if type_name == 'date':
            parsed = self._parse_dt(
                value, (self.date_format_hint,) + DATE_FORMATS)
            return parsed.date() if parsed else None
        if type_name == 'datetime':
            return self._parse_dt(value, DATETIME_FORMATS)
        if type_name == 'boolean':
            return value.lower() in ('true', '1', 'yes')
        return value

    def _load_rows(self, table, names, types, rows):
        converted = []
        for row in rows:
            converted.append(tuple(
                self._convert(row[index] if index < len(row) else '',
                              types[index])
                for index in range(len(names))))
        columns_sql = self.env.cr.mogrify(
            SQL(", ").join(SQL.identifier(n) for n in names)).decode()
        execute_values(
            self.env.cr._obj,
            'INSERT INTO "%s" (%s) VALUES %%s' % (table, columns_sql),
            converted, page_size=2000)
