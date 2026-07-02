# -*- coding: utf-8 -*-
import logging
import re
from datetime import datetime, timedelta

import requests
from psycopg2.extras import execute_values

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import SQL

_logger = logging.getLogger(__name__)

SQL_VIEW_NAME_RE = re.compile(r'^bi_[a-z0-9_]+$')
COLUMN_NAME_RE = re.compile(r'[^a-z0-9_]+')
MAX_SYNC_ROWS = 200000


class BiSource(models.Model):
    """A queryable data source: an Odoo model, an admin-registered read-only
    SQL view, a CSV staging table (Phase 2) or an external connector (Phase 3).

    The connector contract (`_test_connection` / `_fetch_schema` /
    `_fetch_batch`) is defined here so later source types plug in without
    touching datasets or the query engine.
    """
    _name = 'bi.source'
    _description = 'BI Data Source'
    _order = 'name'

    name = fields.Char(required=True, translate=True)
    type = fields.Selection([
        ('odoo_model', 'Odoo Model'),
        ('sql_view', 'SQL View'),
        ('csv', 'CSV / Excel Upload'),
        ('external', 'External Connector'),
    ], required=True, default='odoo_model')
    active = fields.Boolean(default=True)

    # odoo_model
    model_id = fields.Many2one('ir.model', ondelete='cascade',
                               string='Odoo Model')
    model_name = fields.Char(related='model_id.model', store=True,
                             string='Technical Model')

    # sql_view — admins register an existing read-only view; they never type
    # SQL into this record, so the only validation needed is name + existence.
    view_name = fields.Char(
        string='View Name',
        help="Existing PostgreSQL view or table, must match ^bi_[a-z0-9_]+$.")

    # csv (Phase 2): stage table is derived from the id, never from user text
    stage_table = fields.Char(compute='_compute_stage_table')

    # external (Phase 3)
    connector_type = fields.Selection([
        ('rest_json', 'REST API (JSON)'),
        ('postgres', 'External PostgreSQL'),
    ])
    connection_json = fields.Json(
        help="Connector configuration. Credentials go in ir.config_parameter, "
             "never in this field.")

    state = fields.Selection([
        ('draft', 'Draft'),
        ('ready', 'Ready'),
        ('error', 'Error'),
    ], default='draft')
    last_sync = fields.Datetime(readonly=True)
    last_error = fields.Text(readonly=True)

    sync_interval = fields.Selection([
        ('manual', 'Manual Only'),
        ('hourly', 'Every Hour'),
        ('daily', 'Daily'),
    ], default='manual', string='Auto-Sync',
        help="Automatic refresh cadence for external connectors.")
    next_sync = fields.Datetime(readonly=True, copy=False)

    pipeline_id = fields.One2many('bi.pipeline', 'source_id',
                                  string='Pipeline')
    has_active_pipeline = fields.Boolean(compute='_compute_has_pipeline')

    def _compute_has_pipeline(self):
        for source in self:
            pipeline = source.pipeline_id[:1]
            source.has_active_pipeline = bool(
                pipeline and pipeline.is_active
                and pipeline.last_compiled_sql and not pipeline.last_error
                and source._pg_relation_exists(
                    pipeline._clean_view_name()))

    _sql_constraints = [
        ('model_uniq', 'unique(model_id)',
         'A source already exists for this Odoo model.'),
    ]

    @api.depends('type')
    def _compute_stage_table(self):
        for source in self:
            source.stage_table = (
                'bi_stage_%d' % source.id
                if source.type in ('csv', 'external') and source.id else False)

    @api.constrains('type', 'model_id', 'view_name')
    def _check_source_target(self):
        for source in self:
            if source.type == 'odoo_model':
                if not source.model_id:
                    raise ValidationError(_("An Odoo model is required."))
                if self.env[source.model_name]._abstract:
                    raise ValidationError(
                        _("Abstract models cannot be used as sources."))
            elif source.type == 'sql_view':
                if not source.view_name:
                    raise ValidationError(_("A view name is required."))
                if not SQL_VIEW_NAME_RE.match(source.view_name):
                    raise ValidationError(_(
                        "View name must match ^bi_[a-z0-9_]+$ "
                        "(got %s).", source.view_name))
                if not self._pg_relation_exists(source.view_name):
                    raise ValidationError(_(
                        "View %s does not exist in the database.",
                        source.view_name))

    def _pg_relation_exists(self, relname):
        self.env.cr.execute(
            "SELECT 1 FROM pg_class WHERE relname = %s "
            "AND relkind IN ('r', 'v', 'm') LIMIT 1", (relname,))
        return bool(self.env.cr.fetchone())

    # ------------------------------------------------------------------
    # Physical access — what the query engine builds FROM clauses with
    # ------------------------------------------------------------------

    def _table_name(self, raw=False):
        """Physical relation backing this source. With an applied active
        pipeline, that's the cleaned view (Silver) unless raw=True."""
        self.ensure_one()
        if not raw and self.has_active_pipeline:
            return self.pipeline_id[:1]._clean_view_name()
        if self.type == 'odoo_model':
            return self.env[self.model_name]._table
        if self.type == 'sql_view':
            return self.view_name
        if self.type in ('csv', 'external'):
            return self.stage_table
        raise ValidationError(_("Source %s has no physical table.", self.name))

    # ------------------------------------------------------------------
    # Schema introspection — feeds the field scanner
    # ------------------------------------------------------------------

    def _fetch_schema(self, raw=False):
        """Return column descriptors:
        [{name, odoo_type, string, comodel, translated, selection}]
        Only stored, physically-present columns are returned — the engine
        queries tables, not the ORM. With an applied pipeline, the cleaned
        view's columns are what's real (renames/calcs included).
        """
        self.ensure_one()
        if not raw and self.has_active_pipeline:
            return self._fetch_schema_pg(
                self.pipeline_id[:1]._clean_view_name())
        if self.type == 'odoo_model':
            return self._fetch_schema_odoo()
        if self.type in ('sql_view', 'csv', 'external'):
            return self._fetch_schema_pg()
        return []

    def _fetch_schema_odoo(self):
        model = self.env[self.model_name]
        columns = self._pg_columns(model._table)
        result = []
        for fname, field_obj in model._fields.items():
            if not field_obj.store or fname not in columns:
                continue
            if field_obj.type in ('binary', 'reference', 'many2many',
                                  'one2many', 'json', 'properties',
                                  'properties_definition'):
                continue
            entry = {
                'name': fname,
                'odoo_type': field_obj.type,
                'string': field_obj.string or fname,
                'comodel': field_obj.comodel_name or False,
                'translated': bool(field_obj.translate),
                'selection': False,
            }
            if field_obj.type == 'selection':
                # bake labels for EVERY installed language so any user sees
                # selection values in their own language (generic — not tied
                # to one country)
                labels = {}
                for lang_code, _name in self.env['res.lang'].get_installed():
                    try:
                        labels[lang_code] = dict(
                            field_obj._description_selection(
                                self.env(context=dict(self.env.context,
                                                      lang=lang_code))))
                    except Exception:
                        continue
                entry['selection'] = labels or False
            result.append(entry)
        return result

    PG_TYPE_MAP = {
        'integer': 'integer', 'bigint': 'integer', 'smallint': 'integer',
        'numeric': 'float', 'double precision': 'float', 'real': 'float',
        'character varying': 'char', 'text': 'char',
        'boolean': 'boolean',
        'date': 'date',
        'timestamp without time zone': 'datetime',
        'timestamp with time zone': 'datetime',
        'jsonb': 'char',
    }

    def _fetch_schema_pg(self, table=None):
        self.env.cr.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = %s AND table_schema = current_schema()
            ORDER BY ordinal_position
        """, (table or self._table_name(raw=True),))
        return [{
            'name': row[0],
            'odoo_type': self.PG_TYPE_MAP.get(row[1], 'char'),
            'string': row[0].replace('_', ' ').title(),
            'comodel': False,
            'translated': False,
            'selection': False,
        } for row in self.env.cr.fetchall()
            if not row[0].startswith('_bi_')]

    def _pg_columns(self, table):
        self.env.cr.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = %s AND table_schema = current_schema()
        """, (table,))
        return {row[0] for row in self.env.cr.fetchall()}

    # ------------------------------------------------------------------
    # Connector contract (implemented per type; external lands Phase 3)
    # ------------------------------------------------------------------

    def action_open_pipeline_editor(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'biz_bi.pipeline',
            'name': _("Pipeline: %s", self.name),
            'params': {'source_id': self.id},
        }

    def action_test_connection(self):
        self.ensure_one()
        try:
            self._test_connection()
            self.write({'state': 'ready', 'last_error': False})
        except Exception as exc:
            self.write({'state': 'error', 'last_error': str(exc)})
        return True

    def _test_connection(self):
        self.ensure_one()
        if self.type == 'odoo_model':
            self.env[self.model_name].check_access('read')
        elif self.type == 'sql_view':
            if not self._pg_relation_exists(self.view_name):
                raise ValidationError(
                    _("View %s not found.", self.view_name))
        elif self.type == 'external' and self.connector_type == 'rest_json':
            response = requests.request(
                (self.connection_json or {}).get('method', 'GET'),
                self._rest_url(), headers=self._rest_headers(), timeout=30)
            response.raise_for_status()
        elif self.type == 'csv':
            if not self._pg_relation_exists(self.stage_table):
                raise ValidationError(_(
                    "No staged data yet — import a file first."))
        else:
            raise ValidationError(_(
                "Connector type %s is not implemented yet.", self.type))

    # ------------------------------------------------------------------
    # REST JSON connector
    # connection_json: {"url", "method", "headers": {...}, "params": {...},
    #                   "json_path": "data.items"}
    # Header values written as "param:some.key" resolve from
    # ir.config_parameter so tokens never live in this record.
    # ------------------------------------------------------------------

    def _rest_url(self):
        url = (self.connection_json or {}).get('url')
        if not url or not url.startswith(('http://', 'https://')):
            raise UserError(_("Connector needs a valid http(s) 'url'."))
        return url

    def _rest_headers(self):
        headers = dict((self.connection_json or {}).get('headers') or {})
        Params = self.env['ir.config_parameter'].sudo()
        for key, value in headers.items():
            if isinstance(value, str) and value.startswith('param:'):
                resolved = Params.get_param(value[6:])
                if not resolved:
                    raise UserError(_(
                        "System parameter '%s' is not set.", value[6:]))
                headers[key] = resolved
        return headers

    def action_sync_now(self):
        self.ensure_one()
        if self.type != 'external' or self.connector_type != 'rest_json':
            raise UserError(_("Sync applies to REST connectors."))
        try:
            rows = self._fetch_batch()
            self._stage_write(rows)
            self.write({'state': 'ready', 'last_error': False,
                        'last_sync': fields.Datetime.now()})
            self.env['bi.audit.log'].sudo().log(
                'external_sync', record=self, payload={'rows': len(rows)})
        except Exception as exc:
            self.write({'state': 'error', 'last_error': str(exc)})
            raise
        finally:
            self._bump_next_sync()
        return True

    def _bump_next_sync(self):
        for source in self:
            if source.sync_interval == 'hourly':
                source.next_sync = fields.Datetime.now() + timedelta(hours=1)
            elif source.sync_interval == 'daily':
                source.next_sync = fields.Datetime.now() + timedelta(days=1)
            else:
                source.next_sync = False

    def write(self, vals):
        result = super().write(vals)
        if 'sync_interval' in vals:
            for source in self:
                if source.sync_interval != 'manual' and not source.next_sync:
                    source._bump_next_sync()
                elif source.sync_interval == 'manual':
                    source.next_sync = False
        return result

    @api.model
    def _process_sync_queue(self):
        """Hourly cron: refresh external sources that are due. One failure
        never blocks the rest; failures back off to the next interval."""
        due = self.search([
            ('type', '=', 'external'),
            ('connector_type', '=', 'rest_json'),
            ('sync_interval', '!=', 'manual'),
            ('next_sync', '!=', False),
            ('next_sync', '<=', fields.Datetime.now()),
        ])
        for source in due:
            try:
                source.action_sync_now()
            except Exception:  # noqa: BLE001 — logged on the record
                _logger.exception("biz_bi: auto-sync failed for %s",
                                  source.name)

    def _fetch_batch(self, cursor_state=None):
        """Pull the full JSON payload and return a list of flat dicts."""
        self.ensure_one()
        config = self.connection_json or {}
        response = requests.request(
            config.get('method', 'GET'), self._rest_url(),
            headers=self._rest_headers(), params=config.get('params'),
            timeout=120)
        response.raise_for_status()
        payload = response.json()
        for part in filter(None, (config.get('json_path') or '').split('.')):
            if not isinstance(payload, dict) or part not in payload:
                raise UserError(_(
                    "json_path '%s' not found in the response.",
                    config.get('json_path')))
            payload = payload[part]
        if isinstance(payload, dict):
            payload = [payload]
        if not isinstance(payload, list):
            raise UserError(_("The response is not a list of records."))
        if len(payload) > MAX_SYNC_ROWS:
            raise UserError(_("Response too large (max %s rows).",
                              MAX_SYNC_ROWS))
        rows = []
        for item in payload:
            if isinstance(item, dict):
                rows.append({key: value for key, value in item.items()
                             if not isinstance(value, (dict, list))})
        if not rows:
            raise UserError(_("No flat records found in the response."))
        return rows

    # -- staging: JSON-typed rows -> typed bi_stage_<id> table ----------

    @staticmethod
    def _stage_column_name(key):
        name = COLUMN_NAME_RE.sub('_', str(key).lower()).strip('_')
        if not name or not name[0].isalpha() or name.startswith('_bi_'):
            return None
        return name

    def _stage_write(self, rows):
        self.ensure_one()
        # pass 1: derive the column schema across all rows
        columns = {}
        for row in rows:
            for key, value in row.items():
                name = self._stage_column_name(key)
                if name:
                    columns[name] = self._merge_pg_type(
                        columns.get(name), self._pg_type_of(value))
        if not columns:
            raise UserError(_("No usable columns in the response."))
        cr = self.env.cr
        table = self.stage_table
        cr.execute(SQL("DROP TABLE IF EXISTS %s CASCADE",
                       SQL.identifier(table)))
        column_defs = [SQL("_bi_row_id bigserial PRIMARY KEY"),
                       SQL("_bi_loaded_at timestamp DEFAULT "
                           "(now() AT TIME ZONE 'UTC')")]
        for name, pg_type in columns.items():
            column_defs.append(SQL("%s " + pg_type, SQL.identifier(name)))
        cr.execute(SQL("CREATE TABLE %s (%s)", SQL.identifier(table),
                       SQL(", ").join(column_defs)))
        # pass 2: values, first raw key mapping to a column name wins
        names = list(columns)
        values = []
        for row in rows:
            normalized = {}
            for key, value in row.items():
                name = self._stage_column_name(key)
                if name and name not in normalized:
                    normalized[name] = value
            values.append(tuple(
                self._coerce_stage_value(normalized.get(n), columns[n])
                for n in names))
        columns_sql = self.env.cr.mogrify(
            SQL(", ").join(SQL.identifier(n) for n in names)).decode()
        execute_values(
            cr._obj,
            'INSERT INTO "%s" (%s) VALUES %%s' % (table, columns_sql),
            values, page_size=2000)
        _logger.info("biz_bi: staged %s rows into %s", len(rows), table)

    @staticmethod
    def _pg_type_of(value):
        if value is None:
            return None
        if isinstance(value, bool):
            return 'boolean'
        if isinstance(value, int):
            return 'bigint'
        if isinstance(value, float):
            return 'numeric'
        if isinstance(value, str):
            text = value.rstrip('Z').split('+')[0]
            try:
                datetime.strptime(text[:19], '%Y-%m-%dT%H:%M:%S')
                return 'timestamp'
            except ValueError:
                pass
            try:
                datetime.strptime(text, '%Y-%m-%d')
                return 'date'
            except ValueError:
                pass
        return 'text'

    @staticmethod
    def _merge_pg_type(previous, current):
        if previous is None:
            return current or 'text'
        if current is None or previous == current:
            return previous
        if {previous, current} == {'bigint', 'numeric'}:
            return 'numeric'
        return 'text'

    @staticmethod
    def _coerce_stage_value(value, pg_type):
        if value is None:
            return None
        if pg_type == 'text':
            return str(value)
        if pg_type in ('date', 'timestamp') and isinstance(value, str):
            return value.rstrip('Z').split('+')[0][:19]
        return value
