# -*- coding: utf-8 -*-
"""Source-level transformation pipelines (Silver cleaning).

A pipeline turns a source's raw relation (Bronze: odoo table, stage table,
registered view) into a cleaned view ``bi_clean_<source_id>`` via a chain of
validated steps transpiled to SQL CTEs. Datasets then consume the cleaned
view transparently — the scanner sees renamed/calculated columns as normal
stored fields and the join graph stays the only joining mechanism.

Step schema ({"version": 1, "steps": [...]}), each step
{"id": "s1", "type": ..., "params": {...}}:

  rename  {"map": {"old_col": "new_col", ...}}
  cast    {"col": "amount", "to": "numeric|integer|date|timestamp|boolean|text"}
  filter  {"conditions": [["col", op, value], ...]}   # engine op enum
  calc    {"as": "margin", "expression": "[revenue] - [cost]"}
  dedupe  {"keys": ["col"], "order_by": [{"col": "date", "dir": "desc"}]}

All identifiers are resolved against the previous step's tracked output
schema — user strings never become SQL identifiers.
"""
import logging
import re

from odoo import _, api, fields, models, tools
from odoo.exceptions import UserError, ValidationError
from odoo.tools import SQL

from .bi_expression import ExpressionCompiler, ExpressionError  # noqa: F401 — ExpressionError used in editor API

_logger = logging.getLogger(__name__)

COLUMN_RE = re.compile(r'^[a-z][a-z0-9_]*$')

CAST_TARGETS = {
    'numeric': 'numeric', 'integer': 'bigint', 'date': 'date',
    'timestamp': 'timestamp', 'boolean': 'boolean', 'text': 'text',
}
NUMERIC_GUARD = r"^-?\d+([.,]\d+)?$"


class BiPipeline(models.Model):
    _name = 'bi.pipeline'
    _description = 'BI Transformation Pipeline'

    source_id = fields.Many2one('bi.source', required=True,
                                ondelete='cascade', index=True)
    is_active = fields.Boolean(default=True)
    steps_json = fields.Json(
        default=lambda self: {'version': 1, 'steps': []},
        help='{"version": 1, "steps": [{"id": "s1", "type": "rename|cast|'
             'filter|calc|dedupe", "params": {...}}]}')
    last_compiled_sql = fields.Text(readonly=True)
    last_error = fields.Text(readonly=True)

    _sql_constraints = [
        ('source_uniq', 'unique(source_id)',
         'A source has a single pipeline.'),
    ]

    def _clean_view_name(self):
        self.ensure_one()
        return 'bi_clean_%d' % self.source_id.id

    # ------------------------------------------------------------------
    # Transpiler
    # ------------------------------------------------------------------

    def _base_relation(self):
        """The raw relation under the pipeline (never the clean view)."""
        return self.source_id._table_name(raw=True)

    def _base_schema(self):
        """{column: odoo_type} of the raw relation."""
        return {col['name']: col['odoo_type']
                for col in self.source_id._fetch_schema(raw=True)}

    def compile_sql(self):
        """Transpile steps to `WITH s1 AS (...), ... SELECT * FROM s<n>`.
        Returns (SQL, final_schema)."""
        self.ensure_one()
        steps = (self.steps_json or {}).get('steps') or []
        schema = self._base_schema()
        if not schema:
            raise UserError(_("Source %s has no columns to transform.",
                              self.source_id.name))
        base = SQL("SELECT * FROM %s", SQL.identifier(self._base_relation()))
        if not steps:
            return base, schema

        ctes = [(SQL.identifier('s0'), base)]
        previous = 's0'
        for index, step in enumerate(steps, start=1):
            if not isinstance(step, dict):
                raise UserError(_("Step %s must be an object.", index))
            step_type = step.get('type')
            handler = getattr(self, '_step_%s' % step_type, None)
            if handler is None:
                raise UserError(_(
                    "Unknown step type '%(type)s' (step %(n)s). Allowed: "
                    "rename, cast, filter, calc, dedupe.",
                    type=step_type, n=index))
            alias = 's%d' % index
            select_sql, schema = handler(
                step.get('params') or {}, previous, schema, index)
            ctes.append((SQL.identifier(alias), select_sql))
            previous = alias

        with_sql = SQL(", ").join(
            SQL("%s AS (%s)", alias, body) for alias, body in ctes)
        return SQL("WITH %s SELECT * FROM %s",
                   with_sql, SQL.identifier(previous)), schema

    # -- step handlers: (params, prev_alias, schema, index)
    #    -> (SELECT SQL, new_schema) --------------------------------------

    def _require_column(self, name, schema, index):
        if name not in schema:
            raise UserError(_(
                "Step %(n)s references unknown column '%(col)s'. "
                "Available: %(cols)s",
                n=index, col=name, cols=', '.join(sorted(schema))))
        return name

    @staticmethod
    def _valid_new_column(name, schema, index):
        if not name or not COLUMN_RE.match(name):
            raise UserError(_(
                "Step %(n)s: '%(col)s' is not a valid column name "
                "(lowercase letters, digits, underscores).",
                n=index, col=name))
        if name in schema:
            raise UserError(_(
                "Step %(n)s: column '%(col)s' already exists.",
                n=index, col=name))
        return name

    def _step_rename(self, params, prev, schema, index):
        mapping = params.get('map') or {}
        if not mapping:
            raise UserError(_("Step %s: rename needs a 'map'.", index))
        new_schema = {}
        parts = []
        for column, col_type in schema.items():
            if column in mapping:
                new_name = mapping[column]
                self._valid_new_column(new_name, new_schema, index)
                parts.append(SQL("%s AS %s", SQL.identifier(column),
                                 SQL.identifier(new_name)))
                new_schema[new_name] = col_type
            else:
                parts.append(SQL.identifier(column))
                new_schema[column] = col_type
        for old in mapping:
            self._require_column(old, schema, index)
        return SQL("SELECT %s FROM %s", SQL(", ").join(parts),
                   SQL.identifier(prev)), new_schema

    def _step_cast(self, params, prev, schema, index):
        column = self._require_column(params.get('col'), schema, index)
        target = params.get('to')
        if target not in CAST_TARGETS:
            raise UserError(_(
                "Step %(n)s: cast target must be one of %(targets)s.",
                n=index, targets=', '.join(sorted(CAST_TARGETS))))
        pg_type = CAST_TARGETS[target]
        if target in ('numeric', 'integer'):
            expr = SQL(
                "CASE WHEN (%s)::text ~ %s THEN "
                "REPLACE((%s)::text, ',', '.')::" + pg_type + " END",
                SQL.identifier(column), NUMERIC_GUARD, SQL.identifier(column))
        else:
            expr = SQL("NULLIF((%s)::text, '')::" + pg_type,
                       SQL.identifier(column))
        parts = [SQL("%s AS %s", expr, SQL.identifier(column))
                 if col == column else SQL.identifier(col)
                 for col in schema]
        new_schema = dict(schema)
        new_schema[column] = {
            'numeric': 'float', 'integer': 'integer', 'date': 'date',
            'timestamp': 'datetime', 'boolean': 'boolean', 'text': 'char',
        }[target]
        return SQL("SELECT %s FROM %s", SQL(", ").join(parts),
                   SQL.identifier(prev)), new_schema

    def _step_filter(self, params, prev, schema, index):
        conditions = params.get('conditions') or []
        if not conditions:
            raise UserError(_("Step %s: filter needs 'conditions'.", index))
        engine = self.env['bi.query.engine']
        predicates = []
        for condition in conditions:
            if not isinstance(condition, (list, tuple)) or len(condition) != 3:
                raise UserError(_(
                    "Step %s: each condition is [column, op, value].", index))
            column, op, value = condition
            self._require_column(column, schema, index)
            predicates.append(engine._compile_filter_op(
                SQL.identifier(column), op, value, None))
        return SQL("SELECT * FROM %s WHERE %s", SQL.identifier(prev),
                   SQL(" AND ").join(predicates)), dict(schema)

    def _step_calc(self, params, prev, schema, index):
        new_column = self._valid_new_column(params.get('as'), schema, index)
        expression = params.get('expression')
        if not expression:
            raise UserError(_("Step %s: calc needs an 'expression'.", index))

        def resolver(name):
            if name not in schema:
                raise ExpressionError(
                    "Unknown column reference [%s]" % name)
            return SQL.identifier(name)

        try:
            expr_sql = ExpressionCompiler(resolver).compile(expression)
        except ExpressionError as exc:
            raise UserError(_("Step %(n)s: %(err)s", n=index, err=exc))
        new_schema = dict(schema)
        new_schema[new_column] = 'float'  # analytics-friendly default
        return SQL("SELECT *, %s AS %s FROM %s", expr_sql,
                   SQL.identifier(new_column),
                   SQL.identifier(prev)), new_schema

    def _step_dedupe(self, params, prev, schema, index):
        keys = params.get('keys') or []
        if not keys:
            raise UserError(_("Step %s: dedupe needs 'keys'.", index))
        for key in keys:
            self._require_column(key, schema, index)
        order_parts = []
        for order in (params.get('order_by') or []):
            column = self._require_column(order.get('col'), schema, index)
            direction = SQL("DESC") if order.get('dir') == 'desc' else SQL("ASC")
            order_parts.append(SQL("%s %s", SQL.identifier(column), direction))
        if not order_parts:
            order_parts = [SQL("%s ASC", SQL.identifier(keys[0]))]
        partition = SQL(", ").join(SQL.identifier(k) for k in keys)
        return SQL(
            "SELECT %s FROM (SELECT *, ROW_NUMBER() OVER "
            "(PARTITION BY %s ORDER BY %s) AS _bi_rn FROM %s) ranked "
            "WHERE _bi_rn = 1",
            SQL(", ").join(SQL.identifier(c) for c in schema),
            partition, SQL(", ").join(order_parts),
            SQL.identifier(prev)), dict(schema)

    # ------------------------------------------------------------------
    # Apply / lifecycle
    # ------------------------------------------------------------------

    def action_apply(self):
        """Validate, (re)create the clean view, rescan dependent nodes."""
        for pipeline in self:
            view_name = pipeline._clean_view_name()
            try:
                compiled, _schema = pipeline.compile_sql()
            except (UserError, ValidationError) as exc:
                pipeline.write({'last_error': str(exc)})
                raise
            tools.drop_view_if_exists(self.env.cr, view_name)
            if pipeline.is_active:
                self.env.cr.execute(SQL(
                    "CREATE VIEW %s AS (%s)",
                    SQL.identifier(view_name), compiled))
            pipeline.write({
                'last_compiled_sql': self.env.cr.mogrify(compiled).decode(),
                'last_error': False,
            })
            # dependent datasets: silver views read through the clean view
            nodes = self.env['bi.dataset.node'].search(
                [('source_id', '=', pipeline.source_id.id)])
            for dataset in nodes.mapped('dataset_id'):
                if dataset.state == 'published':
                    dataset._recreate_silver_view()
            _logger.info("biz_bi: applied pipeline for source %s (%s)",
                         pipeline.source_id.name, view_name)
        return True

    def unlink(self):
        for pipeline in self:
            tools.drop_view_if_exists(
                self.env.cr, pipeline._clean_view_name())
        return super().unlink()

    # ------------------------------------------------------------------
    # Visual editor API
    # ------------------------------------------------------------------

    def _step_schemas(self, steps):
        """Schema BEFORE each step (index-aligned) plus the final schema.
        On an invalid step, returns what compiled so far + the error."""
        self.ensure_one()
        schema = self._base_schema()
        schemas = [dict(schema)]
        for index, step in enumerate(steps, start=1):
            handler = getattr(
                self, '_step_%s' % (step or {}).get('type'), None)
            if handler is None:
                return schemas, index - 1, _(
                    "Unknown step type '%s'.", (step or {}).get('type'))
            try:
                _sql, schema = handler(
                    step.get('params') or {}, 's%d' % (index - 1),
                    schema, index)
            except (UserError, ValidationError, ExpressionError) as exc:
                return schemas, index - 1, str(exc)
            schemas.append(dict(schema))
        return schemas, None, None

    @api.model
    def get_editor_data(self, source_id):
        source = self.env['bi.source'].browse(int(source_id))
        source.check_access('read')
        pipeline = source.pipeline_id[:1]
        steps = (pipeline.steps_json or {}).get('steps') or [] \
            if pipeline else []
        if pipeline:
            schemas, invalid_step, error = pipeline._step_schemas(steps)
        else:
            schemas = [{col['name']: col['odoo_type']
                        for col in source._fetch_schema(raw=True)}]
            invalid_step, error = None, None

        preview = None
        if pipeline and source.has_active_pipeline:
            view = pipeline._clean_view_name()
            self.env.cr.execute(SQL(
                "SELECT * FROM %s LIMIT 10", SQL.identifier(view)))
            columns = [d.name for d in self.env.cr.description
                       if not d.name.startswith('_bi_')]
            indexes = [i for i, d in enumerate(self.env.cr.description)
                       if not d.name.startswith('_bi_')]
            preview = {
                'columns': columns,
                'rows': [[str(row[i]) if row[i] is not None else None
                          for i in indexes]
                         for row in self.env.cr.fetchall()],
            }

        return {
            'source_id': source.id,
            'source_name': source.name,
            'source_type': source.type,
            'is_active': pipeline.is_active if pipeline else True,
            'applied': source.has_active_pipeline,
            'steps': steps,
            'schemas': [sorted(s.items()) for s in schemas],
            'invalid_step': invalid_step,
            'error': error or (pipeline.last_error if pipeline else None),
            'preview': preview,
        }

    @api.model
    def save_steps(self, source_id, steps, is_active=True):
        """Persist + apply the pipeline; returns fresh editor data. On a
        validation error nothing is applied and the error is reported
        against its step."""
        source = self.env['bi.source'].browse(int(source_id))
        source.check_access('write')
        pipeline = source.pipeline_id[:1]
        if not pipeline:
            pipeline = self.create({'source_id': source.id})
        pipeline.write({
            'steps_json': {'version': 1, 'steps': steps},
            'is_active': is_active,
        })
        try:
            pipeline.action_apply()
        except (UserError, ValidationError):
            pass  # error captured on the record; editor shows it per-step
        return self.get_editor_data(source.id)
