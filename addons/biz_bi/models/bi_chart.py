# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError

CHART_TYPES = [
    ('bar', 'Bar'),
    ('bar_stacked', 'Stacked Bar'),
    ('bar_h', 'Horizontal Bar'),
    ('line', 'Line'),
    ('area', 'Area'),
    ('combo', 'Bar + Line'),
    ('donut', 'Donut'),
    ('kpi', 'KPI Card'),
    ('table', 'Table'),
    ('scatter', 'Scatter'),
    ('heatmap', 'Heatmap'),
    ('treemap', 'Treemap'),
    ('funnel', 'Funnel'),
    ('gauge', 'Gauge'),
    ('waterfall', 'Waterfall'),
    ('pareto', 'Pareto'),
    ('pivot', 'Pivot Matrix'),
]


class BiChart(models.Model):
    """A saved visualization. `config_json` (slots/filters/display) is the
    single source of truth: the server derives the query request from it, so
    saved charts never accept raw field lists from the client."""
    _name = 'bi.chart'
    _description = 'BI Chart'
    _order = 'write_date desc'

    name = fields.Char(required=True, translate=True)
    dataset_id = fields.Many2one('bi.dataset', required=True,
                                 ondelete='cascade', index=True)
    workspace_id = fields.Many2one(
        'bi.workspace', related='dataset_id.workspace_id', store=True)
    chart_type = fields.Selection(CHART_TYPES, required=True, default='bar')
    config_json = fields.Json(required=True, default=dict)
    owner_id = fields.Many2one('res.users', default=lambda self: self.env.user,
                               index=True)
    is_template = fields.Boolean()

    @api.model_create_multi
    def create(self, vals_list):
        charts = super().create(vals_list)
        for chart in charts:
            self.env['bi.audit.log'].sudo().log(
                'chart_save', dataset=chart.dataset_id, record=chart)
        return charts

    def _to_query_request(self, extra_filters=None):
        """Compile config_json into an engine request. `extra_filters` are
        dashboard global/local filters: [{field_id, op, value}]."""
        self.ensure_one()
        config = self.config_json or {}
        slots = config.get('slots') or {}

        dimensions = []
        seen = set()
        for slot_name in ('x', 'series'):
            for entry in (slots.get(slot_name) or []):
                key = (entry.get('field_id'), entry.get('grain'))
                if key in seen:
                    continue  # same field+grain in x and series adds nothing
                seen.add(key)
                dimensions.append({
                    'field_id': entry.get('field_id'),
                    'grain': entry.get('grain'),
                })
        measures = [{
            'field_id': entry.get('field_id'),
            'agg': entry.get('agg'),
        } for entry in (slots.get('values') or [])]

        if not measures and self.chart_type != 'table':
            raise UserError(_(
                "Chart %s has no measure configured.", self.name))

        filters = list(config.get('filters') or [])
        for extra in (extra_filters or []):
            if extra.get('field_id') and extra.get('op'):
                filters.append(extra)

        return {
            'dataset_id': self.dataset_id.id,
            'dimensions': dimensions,
            'measures': measures,
            'filters': filters,
            'sort': config.get('sort') or [],
            'limit': config.get('limit') or 500,
            'options': config.get('options') or {},
        }

    def _to_compare_request(self, extra_filters=None):
        """Same query shifted one period back (KPI comparison). Returns None
        when there is no relative/date-range filter to shift."""
        self.ensure_one()
        request = self._to_query_request(extra_filters)
        shifted, any_shifted = self.env['bi.query.engine'] \
            .shift_filters_previous(request['filters'])
        if not any_shifted:
            return None
        request['filters'] = shifted
        return request

    def action_duplicate(self):
        self.ensure_one()
        return self.copy({'name': _("%s (copy)", self.name)})
