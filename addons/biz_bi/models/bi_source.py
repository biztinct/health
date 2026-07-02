# -*- coding: utf-8 -*-
import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

SQL_VIEW_NAME_RE = re.compile(r'^bi_[a-z0-9_]+$')


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
                try:
                    entry['selection'] = dict(
                        field_obj._description_selection(self.env))
                except Exception:
                    entry['selection'] = False
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
        else:
            raise ValidationError(_(
                "Connector type %s is not implemented yet.", self.type))

    def _fetch_batch(self, cursor_state=None):
        """External connectors pull batches into the stage table (Phase 3)."""
        raise NotImplementedError
