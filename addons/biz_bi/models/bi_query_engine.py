# -*- coding: utf-8 -*-
"""The BI query engine.

Takes a validated request ({dataset, dimensions, measures, filters, sort,
limit}) and generates parameterized SQL against either the live join tree
or the gold materialized view.

Trust boundary rules (non-negotiable):
* every identifier comes from a validated ``bi.field``/``bi.dataset.node``
  record and goes through ``SQL.identifier`` — user strings never become
  SQL identifiers;
* every value is a query parameter;
* operators come from the enum below;
* RLS + company predicates are injected server-side and are part of the
  cache key fingerprint.
"""
import datetime
import hashlib
import logging
import time
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import SQL

from .bi_expression import ExpressionCompiler, ExpressionError

_logger = logging.getLogger(__name__)

MAX_ROWS = 5000
GOLD_ALIAS = 'g'

ALLOWED_AGGS = {
    'sum': "SUM(%s)",
    'avg': "AVG(%s)",
    'min': "MIN(%s)",
    'max': "MAX(%s)",
    'count': "COUNT(%s)",
    'count_distinct': "COUNT(DISTINCT %s)",
}

ALLOWED_GRAINS = {'year', 'quarter', 'month', 'week', 'day'}

RELATIVE_RANGES = {
    'today': lambda today: (today, today + relativedelta(days=1)),
    'yesterday': lambda today: (today - relativedelta(days=1), today),
    'last_7_days': lambda today: (today - relativedelta(days=7),
                                  today + relativedelta(days=1)),
    'last_30_days': lambda today: (today - relativedelta(days=30),
                                   today + relativedelta(days=1)),
    'this_week': lambda today: (
        today - relativedelta(days=today.weekday()),
        today - relativedelta(days=today.weekday()) + relativedelta(days=7)),
    'this_month': lambda today: (
        today.replace(day=1), today.replace(day=1) + relativedelta(months=1)),
    'last_month': lambda today: (
        today.replace(day=1) - relativedelta(months=1), today.replace(day=1)),
    'this_quarter': lambda today: (
        today.replace(month=(today.month - 1) // 3 * 3 + 1, day=1),
        today.replace(month=(today.month - 1) // 3 * 3 + 1, day=1)
        + relativedelta(months=3)),
    'last_6_months': lambda today: (
        today.replace(day=1) - relativedelta(months=5),
        today.replace(day=1) + relativedelta(months=1)),
    'last_12_months': lambda today: (
        today.replace(day=1) - relativedelta(months=11),
        today.replace(day=1) + relativedelta(months=1)),
    'this_year': lambda today: (
        today.replace(month=1, day=1),
        today.replace(month=1, day=1) + relativedelta(years=1)),
    'last_year': lambda today: (
        today.replace(month=1, day=1) - relativedelta(years=1),
        today.replace(month=1, day=1)),
}


class BiQueryEngine(models.AbstractModel):
    _name = 'bi.query.engine'
    _description = 'BI Query Engine'

    # ==================================================================
    # Public API
    # ==================================================================

    @api.model
    def run_batch(self, requests):
        """Execute a list of query requests serially (one dashboard load =
        one RPC). Each entry gets its own envelope; a failing request
        yields {'error': ...} without sinking its siblings."""
        results = []
        for request in requests:
            try:
                results.append(self.run(request))
            except (UserError, ExpressionError) as exc:
                results.append({'error': str(exc)})
            except Exception:
                _logger.exception("biz_bi: query failed: %s", request)
                results.append({'error': _("Query failed — see server log.")})
        return results

    @api.model
    def run(self, request):
        dataset = self.env['bi.dataset'].browse(
            int(request.get('dataset_id') or 0))
        if not dataset.exists():
            raise UserError(_("Dataset not found."))
        dataset.check_access('read')
        if dataset.state != 'published':
            # modelers may preview drafts
            if not self.env.user.has_group('biz_bi.group_bi_modeler'):
                raise UserError(_("Dataset %s is not published.", dataset.name))
            if dataset.root_node_id and dataset.field_ids:
                dataset._recreate_silver_view()

        lang = self.env.user.lang or 'en_US'
        fingerprint = self._rls_fingerprint(dataset)
        Cache = self.env['bi.query.cache'].sudo()
        cache_key = Cache.make_key(request, fingerprint, lang)
        cached = Cache.fetch(cache_key)
        if cached is not None:
            cached.setdefault('meta', {})['cache'] = 'hit'
            return cached

        started = time.monotonic()
        spec = self._resolve_request(dataset, request)
        top_n = spec['top_n'] if len(spec['dimensions']) == 1 else None
        if top_n:
            ref = top_n.get('ref') or ('m0' if spec['measures'] else 'd0')
            spec['sort'] = [{'ref': ref, 'dir': 'desc'}]
            spec['limit'] = min(int(top_n.get('n') or 10), spec['limit'])
        query = self._build_sql(dataset, spec)
        rows = self._execute(query)
        if top_n and top_n.get('others') and rows:
            rows = rows + self._others_row(dataset, spec, rows)
        duration_ms = int((time.monotonic() - started) * 1000)

        envelope = {
            'columns': spec['columns_meta'],
            'rows': [self._json_safe_row(row) for row in rows],
            'meta': {
                'row_count': len(rows),
                'truncated': len(rows) >= spec['limit'],
                'duration_ms': duration_ms,
                'freshness_at': fields.Datetime.to_string(
                    dataset.freshness_at),
                'source': spec['target'],
                'cache': 'miss',
            },
        }

        ttl = (self._ttl_until_next_refresh(dataset)
               if spec['target'] == 'gold' else 60)
        Cache.store(cache_key, dataset.id, envelope, ttl)
        self.env['bi.audit.log'].sudo().log(
            'query', dataset=dataset,
            payload={'duration_ms': duration_ms, 'rows': len(rows)})
        return envelope

    # ==================================================================
    # Request resolution & authorization
    # ==================================================================

    def _resolve_request(self, dataset, request):
        masked = self.env['bi.access.rule']._masked_field_ids(dataset)
        nulled = self.env['bi.access.rule']._nulled_field_ids(dataset)

        def browse_field(field_id, usage):
            field = self.env['bi.field'].browse(int(field_id))
            if not field.exists() or field.dataset_id != dataset:
                raise UserError(_("Unknown field in %s.", usage))
            if field.id in masked:
                raise UserError(_(
                    "You do not have access to the field used in %s.", usage))
            return field

        dimensions = []
        for dim in request.get('dimensions') or []:
            field = browse_field(dim.get('field_id'), _("dimensions"))
            grain = dim.get('grain')
            if grain and grain not in ALLOWED_GRAINS:
                raise UserError(_("Invalid date grain '%s'.", grain))
            if field.data_type not in ('date', 'datetime'):
                grain = None  # grain is only meaningful on dates — ignore
            dimensions.append({'field': field, 'grain': grain})

        fanout_unsafe = (dataset._fanout_unsafe_node_ids()
                         if dataset.has_fanout else set())
        measures = []
        for meas in request.get('measures') or []:
            field = browse_field(meas.get('field_id'), _("measures"))
            agg = meas.get('agg') or field.default_agg or 'sum'
            if field.origin == 'calculated':
                agg = 'expression'
            elif agg not in ALLOWED_AGGS:
                raise UserError(_("Invalid aggregation '%s'.", agg))
            if (field.node_id.id in fanout_unsafe
                    and agg in ('sum', 'avg')
                    and field.origin == 'stored'):
                raise UserError(_(
                    "Measure %s would double-count because the dataset joins "
                    "detail rows (fan-out). Use count distinct, or move the "
                    "measure to the detail node.", field.name))
            measures.append({'field': field, 'agg': agg,
                             'nulled': field.id in nulled})

        if not dimensions and not measures:
            raise UserError(_("Nothing to query — add a field."))

        filters = []
        for filt in request.get('filters') or []:
            field = browse_field(filt.get('field_id'), _("filters"))
            filters.append({'field': field, 'op': filt.get('op'),
                            'value': filt.get('value')})

        limit = min(int(request.get('limit') or 1000), MAX_ROWS)
        sort = request.get('sort') or []
        top_n = (request.get('options') or {}).get('top_n')

        # target selection
        target = 'live'
        if dataset.storage_mode == 'gold' and dataset.refresh_job_id \
                and dataset.refresh_job_id.is_healthy():
            target = 'gold'

        columns_meta = []
        for index, dim in enumerate(dimensions):
            field = dim['field']
            columns_meta.append({
                'ref': 'd%d' % index,
                'field_id': field.id,
                'label': field.name,
                'type': field.data_type,
                'role': field.role,
                'grain': dim['grain'],
                'format': field.format_json or {},
                'selection_labels': field.selection_labels_json or {},
            })
        for index, meas in enumerate(measures):
            field = meas['field']
            columns_meta.append({
                'ref': 'm%d' % index,
                'field_id': field.id,
                'label': field.name,
                'type': field.data_type,
                'role': 'measure',
                'agg': meas['agg'],
                'format': field.format_json or {},
            })

        return {
            'dimensions': dimensions,
            'measures': measures,
            'filters': filters,
            'sort': sort,
            'limit': limit,
            'offset': int(request.get('offset') or 0),
            'top_n': top_n,
            'target': target,
            'columns_meta': columns_meta,
        }

    # ==================================================================
    # SQL generation
    # ==================================================================

    def _field_expr(self, field, target, lang):
        """SQL expression for one stored field on the chosen target,
        unwrapping translated jsonb columns to the user language."""
        if target == 'gold':
            expr = SQL("%s.%s", SQL.identifier(GOLD_ALIAS),
                       SQL.identifier('f_%d' % field.id))
        else:
            expr = SQL("%s.%s", SQL.identifier(field.node_id.alias),
                       SQL.identifier(field.technical_name))
        if field.is_translated_column:
            expr = SQL("COALESCE(%s ->> %s, %s ->> 'en_US')",
                       expr, lang, expr)
        return expr

    def _calc_expr(self, field, target, lang, allow_aggregates):
        mapping = field._expression_field_map()

        def resolver(name):
            sibling = mapping.get(name)
            if sibling is None:
                raise ExpressionError("Unknown field reference [%s]" % name)
            return self._field_expr(sibling, target, lang)

        compiler = ExpressionCompiler(
            resolver, allow_aggregates=allow_aggregates)
        return compiler.compile(field.expression), compiler.uses_aggregates

    def _build_sql(self, dataset, spec):
        lang = self.env.user.lang or 'en_US'
        target = spec['target']

        select_parts, group_parts = [], []
        for index, dim in enumerate(spec['dimensions']):
            field = dim['field']
            if field.origin == 'calculated':
                expr, _uses_agg = self._calc_expr(field, target, lang, False)
            else:
                expr = self._field_expr(field, target, lang)
            if dim['grain']:
                expr = SQL("DATE_TRUNC('" + dim['grain'] + "', %s)", expr)
            select_parts.append(SQL(
                "%s AS %s", expr, SQL.identifier('d%d' % index)))
            group_parts.append(expr)

        for index, meas in enumerate(spec['measures']):
            field = meas['field']
            if meas.get('nulled'):
                expr = SQL("NULL")
            elif field.origin == 'calculated':
                expr, uses_agg = self._calc_expr(field, target, lang, True)
                if not uses_agg:
                    expr = SQL("SUM(%s)", expr)
            else:
                base = self._field_expr(field, target, lang)
                expr = SQL(ALLOWED_AGGS[meas['agg']], base)
            select_parts.append(SQL(
                "%s AS %s", expr, SQL.identifier('m%d' % index)))

        from_sql = self._build_from(dataset, target)
        where_parts = self._build_where(dataset, spec, target, lang)

        query = SQL("SELECT %s FROM %s",
                    SQL(", ").join(select_parts), from_sql)
        if where_parts:
            query = SQL("%s WHERE %s", query,
                        SQL(" AND ").join(where_parts))
        if group_parts:
            query = SQL("%s GROUP BY %s", query,
                        SQL(", ").join(group_parts))

        order_sql = self._build_order(spec)
        if order_sql:
            query = SQL("%s ORDER BY %s", query, order_sql)
        query = SQL("%s LIMIT %s OFFSET %s", query,
                    spec['limit'], spec['offset'])
        return query

    def _build_from(self, dataset, target):
        if target == 'gold':
            return SQL("%s AS %s",
                       SQL.identifier(dataset._gold_matview_name()),
                       SQL.identifier(GOLD_ALIAS))
        ordered, edges = dataset._ordered_nodes()
        root = ordered[0]
        from_sql = SQL("%s AS %s",
                       SQL.identifier(root.source_id._table_name()),
                       SQL.identifier(root.alias))
        for rel in edges:
            join_kw = SQL("LEFT JOIN") if rel.join_type == 'left' \
                else SQL("JOIN")
            from_sql = SQL(
                "%s %s %s AS %s ON %s.%s = %s.%s",
                from_sql, join_kw,
                SQL.identifier(rel.child_node_id.source_id._table_name()),
                SQL.identifier(rel.child_node_id.alias),
                SQL.identifier(rel.parent_node_id.alias),
                SQL.identifier(rel.parent_field),
                SQL.identifier(rel.child_node_id.alias),
                SQL.identifier(rel.child_field))
        return from_sql

    def _build_where(self, dataset, spec, target, lang):
        parts = []
        # 1. request filters
        for filt in spec['filters']:
            field = filt['field']
            if field.origin == 'calculated':
                column, _uses_agg = self._calc_expr(field, target, lang, False)
            else:
                column = self._field_expr(field, target, lang)
            parts.append(self._compile_filter_op(
                column, filt['op'], filt['value'], field))

        # 2. static filters (live only — gold has them baked in)
        if target == 'live':
            static_sql = dataset._compile_static_filters()
            if static_sql:
                parts.append(static_sql)

        # 3. RLS row rules
        rls = self.env['bi.access.rule']._compile_row_rules(
            dataset, lambda f: self._field_expr(f, target, lang), self)
        if rls is not None:
            parts.append(rls)

        # 4. multi-company predicate
        if dataset.company_field_id:
            company_expr = self._field_expr(
                dataset.company_field_id, target, lang)
            parts.append(SQL("(%s IS NULL OR %s = ANY(%s))",
                             company_expr, company_expr,
                             self.env.companies.ids))

        # 5. root model ir.rule (live odoo_model datasets, root table only)
        if target == 'live':
            rule_sql = self._compile_root_ir_rules(dataset)
            if rule_sql is not None:
                parts.append(rule_sql)

        # 6. engine-internal predicates (top-N "Others" exclusion)
        parts.extend(spec.get('extra_predicates') or [])
        return parts

    OTHERS_KEY = '__bi_others__'

    def _others_row(self, dataset, spec, rows):
        """Aggregate everything outside the top-N into one 'Others' row.
        Only correct for additive aggregations — silently skipped otherwise
        (avg of group-avgs would lie)."""
        additive = all(
            m['agg'] in ('sum', 'count') and m['field'].origin == 'stored'
            for m in spec['measures'])
        if not additive or not spec['measures']:
            return []
        lang = self.env.user.lang or 'en_US'
        dim = spec['dimensions'][0]
        field = dim['field']
        if field.origin == 'calculated':
            expr, _uses_agg = self._calc_expr(field, spec['target'], lang, False)
        else:
            expr = self._field_expr(field, spec['target'], lang)
        if dim['grain']:
            expr = SQL("DATE_TRUNC('" + dim['grain'] + "', %s)", expr)
        top_values = [row[0] for row in rows if row[0] is not None]
        if not top_values:
            return []
        others_spec = dict(
            spec, dimensions=[], sort=[], limit=1, offset=0,
            extra_predicates=[SQL(
                "(%s IS NULL OR NOT (%s = ANY(%s)))",
                expr, expr, top_values)])
        others = self._execute(self._build_sql(dataset, others_spec))
        if others and any(value not in (None, 0) for value in others[0]):
            return [(self.OTHERS_KEY,) + tuple(others[0])]
        return []

    def _compile_root_ir_rules(self, dataset):
        root_source = dataset.root_node_id.source_id
        if root_source.type != 'odoo_model':
            return None
        model_name = root_source.model_name
        rule_domain = self.env['ir.rule']._compute_domain(model_name, 'read')
        if rule_domain is None or rule_domain.is_true():
            return None
        query = self.env[model_name]._search(
            rule_domain, bypass_access=True, active_test=False)
        return SQL("%s.id IN (%s)",
                   SQL.identifier(dataset.root_node_id.alias),
                   query.subselect())

    def _compile_filter_op(self, column, op, value, field):
        """Shared operator compiler (also used for dataset static filters).
        `column` is a compiled SQL expression; `value` is always a parameter."""
        if op == 'eq':
            return SQL("%s = %s", column, value)
        if op == 'neq':
            return SQL("(%s IS DISTINCT FROM %s)", column, value)
        if op == 'gt':
            return SQL("%s > %s", column, value)
        if op == 'gte':
            return SQL("%s >= %s", column, value)
        if op == 'lt':
            return SQL("%s < %s", column, value)
        if op == 'lte':
            return SQL("%s <= %s", column, value)
        if op == 'in':
            if not isinstance(value, (list, tuple)) or not value:
                raise UserError(_("'in' filter needs a non-empty list."))
            return SQL("%s = ANY(%s)", column, list(value))
        if op == 'not_in':
            if not isinstance(value, (list, tuple)) or not value:
                raise UserError(_("'not in' filter needs a non-empty list."))
            return SQL("(%s IS NULL OR NOT (%s = ANY(%s)))",
                       column, column, list(value))
        if op == 'between':
            if not isinstance(value, (list, tuple)) or len(value) != 2:
                raise UserError(_("'between' filter needs [start, end]."))
            return SQL("(%s >= %s AND %s <= %s)",
                       column, value[0], column, value[1])
        if op == 'like_i':
            return SQL("(%s)::text ILIKE %s", column,
                       '%%%s%%' % str(value or ''))
        if op == 'is_set':
            return SQL("%s IS NOT NULL", column)
        if op == 'is_null':
            return SQL("%s IS NULL", column)
        if op == 'relative':
            start, end = self.relative_bounds(value)
            return SQL("(%s >= %s AND %s < %s)", column, start, column, end)
        if op == 'date_range':
            # internal half-open range [start, end) — used for shifted
            # previous-period comparisons
            if not isinstance(value, (list, tuple)) or len(value) != 2:
                raise UserError(_("'date_range' filter needs [start, end)."))
            return SQL("(%s >= %s AND %s < %s)",
                       column, value[0], column, value[1])
        raise UserError(_("Unknown filter operator '%s'.", op))

    @api.model
    def relative_bounds(self, value):
        builder = RELATIVE_RANGES.get(value)
        if not builder:
            raise UserError(_(
                "Unknown relative range '%s'. Allowed: %s",
                value, ', '.join(sorted(RELATIVE_RANGES))))
        return builder(fields.Date.context_today(self))

    @api.model
    def shift_filters_previous(self, filters):
        """Shift every relative/date_range filter one window back (for
        previous-period KPI comparisons). Returns (shifted_filters, shifted?)
        — shifted? is False when there is no date filter to compare against."""
        shifted = []
        any_shifted = False
        for filt in filters or []:
            op, value = filt.get('op'), filt.get('value')
            if op == 'relative':
                start, end = self.relative_bounds(value)
                length = end - start
                shifted.append(dict(filt, op='date_range',
                                    value=[start - length, start]))
                any_shifted = True
            elif op == 'date_range' and isinstance(value, (list, tuple)) \
                    and len(value) == 2:
                start, end = fields.Date.to_date(value[0]), \
                    fields.Date.to_date(value[1])
                length = end - start
                shifted.append(dict(filt, value=[start - length, start]))
                any_shifted = True
            else:
                shifted.append(filt)
        return shifted, any_shifted

    def _build_order(self, spec):
        valid_refs = {'d%d' % i for i in range(len(spec['dimensions']))}
        valid_refs |= {'m%d' % i for i in range(len(spec['measures']))}
        parts = []
        for item in spec['sort']:
            ref = item.get('ref')
            if ref not in valid_refs:
                raise UserError(_("Sort references unknown column '%s'.", ref))
            direction = SQL("DESC") if item.get('dir') == 'desc' else SQL("ASC")
            parts.append(SQL("%s %s NULLS LAST",
                             SQL.identifier(ref), direction))
        if not parts and spec['dimensions']:
            # deterministic default: first dimension ascending
            parts.append(SQL("%s ASC NULLS LAST", SQL.identifier('d0')))
        return SQL(", ").join(parts) if parts else None

    # ==================================================================
    # Execution & helpers
    # ==================================================================

    def _execute(self, query):
        timeout_ms = int(self.env['ir.config_parameter'].sudo().get_param(
            'biz_bi.query_timeout_ms', 15000))
        cr = self.env.cr
        try:
            with cr.savepoint():
                cr.execute("SET LOCAL statement_timeout = %s", (timeout_ms,))
                cr.execute(query)
                return cr.fetchall()
        except Exception as exc:
            message = str(exc)
            if 'statement timeout' in message.lower():
                raise UserError(_(
                    "The query took longer than %s seconds. Add filters or "
                    "publish the dataset to Gold.", timeout_ms // 1000))
            raise

    @staticmethod
    def _json_safe_row(row):
        result = []
        for value in row:
            if isinstance(value, (datetime.datetime, datetime.date)):
                result.append(value.isoformat())
            elif hasattr(value, 'quantize'):  # Decimal
                result.append(float(value))
            else:
                result.append(value)
        return result

    def _rls_fingerprint(self, dataset):
        rules = self.env['bi.access.rule']._applicable_rules(dataset)
        raw = '|'.join([
            str(sorted(rules.ids)),
            str(self.env.uid),
            str(sorted(self.env.companies.ids)),
        ])
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _ttl_until_next_refresh(self, dataset):
        job = dataset.refresh_job_id
        if job and job.next_run:
            delta = (job.next_run - fields.Datetime.now()).total_seconds()
            return max(int(delta), 60)
        return 3600
