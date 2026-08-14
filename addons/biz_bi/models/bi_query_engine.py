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
from odoo.exceptions import AccessError, UserError
from odoo.tools import SQL

from ..bi_tz import (as_calendar_date, day_start_utc, to_user_tz,
                     user_timezone, user_tz_name)
from .bi_expression import ExpressionCompiler, ExpressionError

_logger = logging.getLogger(__name__)

MAX_ROWS = 5000
GOLD_ALIAS = 'g'

# 'aggregate' = one row per group (GROUP BY); 'detail' = one row per
# underlying record (Records table + Excel export). Anything else is a
# client bug and must not silently fall back to a mode the caller did not ask
# for — the two have different egress volumes.
ALLOWED_MODES = ('aggregate', 'detail')

# Server-side ceiling for /bi/export/xlsx. Overridable with the
# `biz_bi.export_row_cap` ir.config_parameter; NEVER from a client payload.
DEFAULT_EXPORT_ROW_CAP = 20000

ALLOWED_AGGS = {
    'sum': "SUM(%s)",
    'avg': "AVG(%s)",
    'min': "MIN(%s)",
    'max': "MAX(%s)",
    'count': "COUNT(%s)",
    'count_distinct': "COUNT(DISTINCT %s)",
}

ALLOWED_GRAINS = {'year', 'quarter', 'month', 'week', 'day'}

# A many2one column groups by id (distinct entities) but must READ as the
# record's name. Resolution is per-user and never cached, so the comodel's
# own record rules decide whose name is shown; above this many distinct
# values a legend of names is useless anyway, so we leave the raw ids.
MAX_LABEL_LOOKUP = 2000

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
    def export_row_cap(self):
        """Row ceiling for a server-side export run. Not named `read`/`fetch`
        /`search`/`browse` — see ledger §5.136."""
        raw = self.env['ir.config_parameter'].sudo().get_param(
            'biz_bi.export_row_cap')
        # get_param returns False (not None) for a missing key, and
        # int(False) is a perfectly silent 0 — which max(1, …)ed the export
        # down to a single row. Treat every falsy read as "not configured".
        try:
            cap = int(raw) if raw else DEFAULT_EXPORT_ROW_CAP
        except (TypeError, ValueError):
            cap = DEFAULT_EXPORT_ROW_CAP
        return max(1, cap)

    @api.model
    def run(self, request, hard_cap=None):
        """`hard_cap` replaces MAX_ROWS as the row clamp. It is a SERVER-side
        argument (the export controller passes the configured cap) and is
        deliberately stripped from the request payload: a client must never be
        able to raise its own row ceiling by adding a key to the JSON body."""
        request = dict(request or {})
        request.pop('hard_cap', None)
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
        # the clamp is part of the result identity: the same request run with
        # a 5k preview clamp and a 20k export clamp are different answers, and
        # without this a client could prime the cache at 5k and have the
        # export serve it back (or vice versa).
        key_payload = dict(request, __hard_cap__=int(hard_cap)) \
            if hard_cap else request
        cache_key = Cache.make_key(key_payload, fingerprint, lang,
                                   user_tz_name(self.env))
        cached = Cache.fetch_result(cache_key)
        if cached is not None:
            cached.setdefault('meta', {})['cache'] = 'hit'
            return self._attach_relation_labels(cached)

        started = time.monotonic()
        spec = self._resolve_request(dataset, request, hard_cap=hard_cap)
        top_n = spec['top_n'] if (spec['mode'] == 'aggregate'
                                  and len(spec['dimensions']) == 1) else None
        if top_n:
            ref = top_n.get('ref') or ('m0' if spec['measures'] else 'd0')
            spec['sort'] = [{'ref': ref, 'dir': 'desc'}]
            spec['limit'] = min(int(top_n.get('n') or 10), spec['limit'])
        query = self._build_sql(dataset, spec)
        rows = self._execute(query)
        if top_n and top_n.get('others') and rows:
            rows = rows + self._others_row(dataset, spec, rows)
        duration_ms = int((time.monotonic() - started) * 1000)

        meta = {
            'row_count': len(rows),
            'truncated': len(rows) >= spec['limit'],
            'duration_ms': duration_ms,
            'freshness_at': fields.Datetime.to_string(
                dataset.freshness_at),
            'source': spec['target'],
            'cache': 'miss',
        }
        if spec['mode'] == 'detail':
            # an honest total: how many records the filters actually match,
            # independent of the row clamp, so the UI never implies that the
            # capped page IS the result set.
            total_count = self._count_detail_rows(dataset, spec)
            meta.update({
                'mode': 'detail',
                'total_count': total_count,
                'truncated': total_count > len(rows),
                'export_cap': self.export_row_cap(),
            })
        envelope = {
            'columns': spec['columns_meta'],
            'rows': [self._json_safe_row(row) for row in rows],
            'meta': meta,
        }

        ttl = (self._ttl_until_next_refresh(dataset)
               if spec['target'] == 'gold' else 60)
        # stored WITHOUT relation labels: the cache is shared by every user
        # with the same RLS fingerprint, but the comodel's record rules are
        # not part of that fingerprint — so names are resolved per reader.
        Cache.store(cache_key, dataset.id, envelope, ttl)
        self.env['bi.audit.log'].sudo().log(
            'query', dataset=dataset,
            payload={'duration_ms': duration_ms, 'rows': len(rows)})
        return self._attach_relation_labels(envelope)

    def _attach_relation_labels(self, envelope):
        """Give many2one dimension columns a `value_labels` map so the
        frontend renders 'Ho Chi Minh City' where the column stores 4.

        Grouping still happens on the id — two records that share a name
        stay two groups. Ids the reader may not read keep their raw value
        rather than borrowing someone else's name.
        """
        columns = envelope.get('columns') or []
        rows = envelope.get('rows') or []
        if not rows:
            return envelope
        BiField = self.env['bi.field']
        for index, column in enumerate(columns):
            if not str(column.get('ref') or '').startswith('d'):
                continue
            field = BiField.browse(column.get('field_id')).exists()
            model_name = field.relation_model
            if not model_name or model_name not in self.env:
                continue
            ids = {row[index] for row in rows
                   if isinstance(row[index], int)
                   and not isinstance(row[index], bool)}
            if not ids or len(ids) > MAX_LABEL_LOOKUP:
                continue
            try:
                records = self.env[model_name].search([('id', 'in', list(ids))])
                # JSON object keys are strings — match how the client looks
                # them up (the same contract as selection_labels).
                labels = {str(record.id): record.display_name
                          for record in records}
            except AccessError:
                continue  # no read access to the lookup model — show ids
            if labels:
                column['value_labels'] = labels
        return envelope

    # ==================================================================
    # Request resolution & authorization
    # ==================================================================

    def _resolve_request(self, dataset, request, hard_cap=None):
        masked = self.env['bi.access.rule']._masked_field_ids(dataset)
        nulled = self.env['bi.access.rule']._nulled_field_ids(dataset)

        mode = request.get('mode') or 'aggregate'
        if mode not in ALLOWED_MODES:
            raise UserError(_("Unknown query mode '%s'.", mode))
        detail = mode == 'detail'

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
            if detail:
                # records show the real date — a grain would bucket them
                grain = None
            else:
                if grain and grain not in ALLOWED_GRAINS:
                    raise UserError(_("Invalid date grain '%s'.", grain))
                if field.data_type not in ('date', 'datetime'):
                    grain = None  # grain is only meaningful on dates — ignore
            dimensions.append({'field': field, 'grain': grain,
                               'nulled': field.id in nulled})

        fanout_unsafe = (dataset._fanout_unsafe_node_ids()
                         if dataset.has_fanout else set())
        measures = []
        if detail and (request.get('measures') or []):
            raise UserError(_(
                "Records mode returns one row per record — remove the "
                "aggregated measures, or switch back to Summary."))
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

        limit = min(int(request.get('limit') or 1000),
                    int(hard_cap) if hard_cap else MAX_ROWS)
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
            column = {
                'ref': 'd%d' % index,
                'field_id': field.id,
                'label': field.name,
                'type': field.data_type,
                'role': field.role,
                'grain': dim['grain'],
                'format': field.format_json or {},
                'selection_labels': field._selection_labels_for(),
            }
            if dim['nulled']:
                # a 'null' column mask used to apply to MEASURES only, so the
                # same field used as a DIMENSION was returned in full. It is
                # nulled in both roles now; the flag lets the UI say why the
                # column is empty instead of looking broken.
                column['nulled'] = True
            columns_meta.append(column)
        for index, meas in enumerate(measures):
            field = meas['field']
            if meas['agg'] == 'count':
                label = _("Count")  # a row count is not about the field
            elif meas['agg'] == 'count_distinct':
                label = _("# unique %s", field.name)
            else:
                label = field.name
            columns_meta.append({
                'ref': 'm%d' % index,
                'field_id': field.id,
                'label': label,
                'type': field.data_type,
                'role': 'measure',
                'agg': meas['agg'],
                'format': field.format_json or {},
            })

        return {
            'mode': mode,
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

    def _dimension_expr(self, dim, spec, target, lang):
        """SELECT/GROUP BY expression for one dimension, in either mode.

        A 'null'-masked field yields a typed NULL constant in BOTH roles and
        BOTH modes — grouping by it still collapses to a single bucket, so no
        value ever leaves the database.
        """
        field = dim['field']
        if dim.get('nulled'):
            return SQL("NULL::text")
        if field.origin == 'calculated':
            try:
                expr, _uses_agg = self._calc_expr(field, target, lang, False)
            except ExpressionError:
                if spec['mode'] == 'detail':
                    raise UserError(_(
                        "Calculated field %s aggregates rows, so it cannot be "
                        "a Records column. Use Summary mode for it.",
                        field.name))
                raise
        else:
            expr = self._field_expr(field, target, lang)
        if dim['grain']:
            expr = SQL("DATE_TRUNC('" + dim['grain'] + "', %s)", expr)
        return expr

    def _build_sql(self, dataset, spec):
        lang = self.env.user.lang or 'en_US'
        target = spec['target']
        detail = spec['mode'] == 'detail'

        select_parts, group_parts = [], []
        for index, dim in enumerate(spec['dimensions']):
            expr = self._dimension_expr(dim, spec, target, lang)
            select_parts.append(SQL(
                "%s AS %s", expr, SQL.identifier('d%d' % index)))
            if not detail:
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

    def _count_detail_rows(self, dataset, spec):
        """How many records match, ignoring the row clamp. Same FROM and the
        same (unchanged) WHERE chain as the page query — no GROUP BY, no
        ORDER BY, no LIMIT — so the banner's total is the real total."""
        lang = self.env.user.lang or 'en_US'
        target = spec['target']
        query = SQL("SELECT COUNT(*) FROM %s",
                    self._build_from(dataset, target))
        where_parts = self._build_where(dataset, spec, target, lang)
        if where_parts:
            query = SQL("%s WHERE %s", query,
                        SQL(" AND ").join(where_parts))
        rows = self._execute(query)
        return int(rows[0][0]) if rows else 0

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
        expr = self._dimension_expr(dim, spec, spec['target'], lang)
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
            start, end = self.window_bounds_for_field(start, end, field)
            return SQL("(%s >= %s AND %s < %s)", column, start, column, end)
        if op == 'date_range':
            # internal half-open range [start, end) — used for shifted
            # previous-period comparisons and for dashboard drill-down
            if not isinstance(value, (list, tuple)) or len(value) != 2:
                raise UserError(_("'date_range' filter needs [start, end)."))
            start, end = self.window_bounds_for_field(
                value[0], value[1], field)
            return SQL("(%s >= %s AND %s < %s)", column, start, column, end)
        raise UserError(_("Unknown filter operator '%s'.", op))

    # ------------------------------------------------------------------
    # Relative date windows — the caller's CALENDAR, the column's CLOCK
    # ------------------------------------------------------------------
    #
    # A window has two halves and they live in different systems. The
    # boundaries are CALENDAR dates in the reader's timezone ("today" for a
    # Vietnamese user is the Vietnamese day). The column is either a
    # calendar `date` — in which case those boundaries go in as they are —
    # or a `datetime` stored in UTC, in which case each boundary becomes the
    # UTC INSTANT at which that local day begins. Comparing a user-tz
    # calendar date against a UTC timestamp with no conversion (what this
    # engine did until now, ledger §5.157) shifts every window by the
    # offset: seven hours of yesterday counted as today, and seven hours of
    # today missing from it.

    @api.model
    def _tz(self):
        return user_timezone(self.env)

    @api.model
    def _relative_now(self):
        """The UTC instant every relative window is measured from.

        A seam, deliberately: pinning a near-midnight window in a test means
        patching this, never sleeping until 23:59 (handover BG-2 §1.2).
        """
        return fields.Datetime.now()

    @api.model
    def relative_today(self):
        """`today` as the CALLER's calendar sees it — their timezone, not
        UTC. Equivalent to `fields.Date.context_today`, but derived through
        the module's own tz resolution so the window and the bounds
        conversion below can never disagree about which zone is in force."""
        return to_user_tz(self._relative_now(), self._tz()).date()

    @api.model
    def relative_bounds(self, value):
        """Half-open [start, end) CALENDAR boundaries for a named range."""
        builder = RELATIVE_RANGES.get(value)
        if not builder:
            raise UserError(_(
                "Unknown relative range '%s'. Allowed: %s",
                value, ', '.join(sorted(RELATIVE_RANGES))))
        return builder(self.relative_today())

    @api.model
    def window_bounds_for_field(self, start, end, field):
        """Calendar boundaries -> what to compare against THIS column.

        A `date` column keeps them (a date has no clock). A `datetime`
        column gets the UTC instants of those local midnights. A bound that
        already carries a time — a dashboard drill-down passes real bucket
        boundaries like `2026-04-01 00:00:00` — is left exactly as it is.
        """
        if getattr(field, 'data_type', None) != 'datetime':
            return start, end
        tz = self._tz()
        bounds = []
        for bound in (start, end):
            day = as_calendar_date(bound)
            bounds.append(day_start_utc(day, tz) if day is not None else bound)
        return bounds[0], bounds[1]

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
            elif isinstance(value, (bytes, memoryview)):
                # detail mode selects raw columns; a bytea from a sql_view
                # source would blow up JSON serialization
                result.append(None)
            elif value is None or isinstance(value, (str, int, float, bool)):
                result.append(value)
            else:
                # time/interval/uuid/… — stringify rather than 500
                result.append(str(value))
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
