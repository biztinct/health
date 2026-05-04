# -*- coding: utf-8 -*-

import json
import logging

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class BiVisual(models.Model):
    """A single chart/visualization — like a Power BI visual or Tableau sheet.
    
    Each visual connects to a dataset, assigns fields to chart slots
    (X-axis, Y-axis, Color, etc.), and stores rendering config.
    """
    _name = 'bi.visual'
    _description = 'BI Visual'
    _inherit = ['mail.thread']
    _order = 'report_page_id, sequence, name'

    name = fields.Char('Visual Name', required=True, tracking=True)
    description = fields.Text('Description')

    # Data source
    dataset_id = fields.Many2one('bi.dataset', string='Dataset',
                                 required=True, ondelete='cascade')

    # Parent report page
    report_page_id = fields.Many2one('bi.report.page', string='Report Page',
                                     ondelete='cascade')

    sequence = fields.Integer('Sequence', default=10)
    active = fields.Boolean('Active', default=True)

    # Visual type
    visual_type = fields.Selection([
        ('bar', 'Bar Chart'),
        ('column', 'Column Chart'),
        ('line', 'Line Chart'),
        ('area', 'Area Chart'),
        ('pie', 'Pie Chart'),
        ('doughnut', 'Doughnut Chart'),
        ('scatter', 'Scatter Plot'),
        ('radar', 'Radar Chart'),
        ('treemap', 'Treemap'),
        ('heatmap', 'Heatmap'),
        ('waterfall', 'Waterfall Chart'),
        ('funnel', 'Funnel Chart'),
        ('gauge', 'Gauge / Meter'),
        ('kpi_card', 'KPI Card'),
        ('data_table', 'Data Table'),
        ('combo', 'Combo Chart'),
    ], string='Visual Type', default='bar', required=True, tracking=True)

    # Field configuration (JSON) — the chart "slots"
    # Structure: {
    #   "x_axis": { "field_id": 5, "field_path": "partner_id.name", "label": "Customer" },
    #   "y_axis": [
    #     { "field_id": 8, "field_path": "amount_total", "aggregation": "sum", "label": "Revenue" }
    #   ],
    #   "color": { "field_id": 12, "field_path": "state", "label": "Status" },
    #   "size": null,
    #   "tooltip": [],
    #   "filters": [
    #     { "field_path": "state", "operator": "=", "value": "posted" }
    #   ],
    #   "sort": { "field_path": "amount_total", "order": "desc" },
    #   "limit": 20,
    #   "time_granularity": "month"
    # }
    config_json = fields.Text('Configuration', default='{}')

    # Layout position (for GridStack)
    position_x = fields.Integer('Grid X', default=0)
    position_y = fields.Integer('Grid Y', default=0)
    width = fields.Integer('Grid Width', default=6)
    height = fields.Integer('Grid Height', default=4)

    # Styling
    color_palette = fields.Selection([
        ('default', 'Default'),
        ('blue', 'Ocean Blue'),
        ('green', 'Forest Green'),
        ('sunset', 'Sunset Orange'),
        ('purple', 'Royal Purple'),
        ('mono', 'Monochrome'),
        ('pastel', 'Pastel'),
        ('vivid', 'Vivid'),
    ], string='Color Palette', default='default')

    show_legend = fields.Boolean('Show Legend', default=True)
    show_labels = fields.Boolean('Show Data Labels', default=False)
    show_grid = fields.Boolean('Show Grid Lines', default=True)
    enable_animation = fields.Boolean('Enable Animation', default=True)
    background_color = fields.Char('Background Color', default='transparent')

    # Interactivity
    drill_down_enabled = fields.Boolean('Enable Drill-down', default=False)
    click_action = fields.Selection([
        ('none', 'None'),
        ('filter', 'Cross-filter Dashboard'),
        ('drill', 'Drill Down'),
        ('action', 'Open Odoo Action'),
    ], string='Click Action', default='none')
    target_action_id = fields.Many2one('ir.actions.act_window',
                                       string='Target Action')

    # Computed
    chart_data = fields.Text('Chart Data', compute='_compute_chart_data')

    def _compute_chart_data(self):
        """Compute chart data for ECharts rendering."""
        for visual in self:
            try:
                data = visual._build_chart_data()
                visual.chart_data = json.dumps(data)
            except Exception as e:
                visual.chart_data = json.dumps({'error': str(e)})

    def _build_chart_data(self):
        """Build ECharts-compatible data from the dataset."""
        config = self._parse_config()
        if not config.get('x_axis') or not config.get('y_axis'):
            return {'labels': [], 'datasets': []}

        dataset = self.dataset_id
        if not dataset or not dataset.model_name:
            return {'labels': [], 'datasets': []}

        # Get the raw data from dataset
        flat_data = dataset._get_flat_data(limit=config.get('limit', 100))
        if not flat_data.get('rows'):
            return {'labels': [], 'datasets': []}

        # Build column index
        col_index = {}
        for i, col in enumerate(flat_data['columns']):
            col_index[col['name']] = i

        x_path = config['x_axis'].get('field_path')
        x_idx = col_index.get(x_path)
        if x_idx is None:
            return {'labels': [], 'datasets': []}

        # Aggregate data
        from collections import defaultdict, OrderedDict
        
        y_fields = config.get('y_axis', [])
        color_field = config.get('color')
        has_color = color_field and color_field.get('field_path')
        color_idx = col_index.get(color_field['field_path']) if has_color else None

        if not has_color:
            # Simple aggregation: group by X, aggregate Y
            grouped = OrderedDict()
            for row in flat_data['rows']:
                x_val = str(row[x_idx]) if row[x_idx] is not None else 'N/A'
                if x_val not in grouped:
                    grouped[x_val] = defaultdict(list)
                for yf in y_fields:
                    y_idx = col_index.get(yf.get('field_path'))
                    if y_idx is not None:
                        val = row[y_idx]
                        if isinstance(val, (int, float)):
                            grouped[x_val][yf['field_path']].append(val)
                        else:
                            grouped[x_val][yf['field_path']].append(0)

            labels = list(grouped.keys())
            datasets = []
            for yf in y_fields:
                agg = yf.get('aggregation', 'sum')
                data_points = []
                for x_val in labels:
                    values = grouped[x_val].get(yf['field_path'], [0])
                    data_points.append(self._aggregate(values, agg))
                datasets.append({
                    'name': yf.get('label', yf['field_path']),
                    'data': data_points,
                    'type': self._echarts_series_type(),
                })

            return {'labels': labels, 'datasets': datasets}
        else:
            # Color-grouped aggregation
            all_labels = OrderedDict()
            series_data = defaultdict(lambda: defaultdict(list))
            
            for row in flat_data['rows']:
                x_val = str(row[x_idx]) if row[x_idx] is not None else 'N/A'
                c_val = str(row[color_idx]) if color_idx is not None and row[color_idx] is not None else 'Default'
                all_labels[x_val] = True
                for yf in y_fields:
                    y_idx = col_index.get(yf.get('field_path'))
                    if y_idx is not None:
                        val = row[y_idx]
                        series_data[c_val][x_val].append(
                            val if isinstance(val, (int, float)) else 0)

            labels = list(all_labels.keys())
            datasets = []
            for series_name, x_values in series_data.items():
                agg = y_fields[0].get('aggregation', 'sum') if y_fields else 'sum'
                data_points = []
                for x_val in labels:
                    values = x_values.get(x_val, [0])
                    data_points.append(self._aggregate(values, agg))
                datasets.append({
                    'name': series_name,
                    'data': data_points,
                    'type': self._echarts_series_type(),
                })

            return {'labels': labels, 'datasets': datasets}

    def _aggregate(self, values, method):
        """Apply aggregation to a list of values."""
        if not values:
            return 0
        if method == 'sum':
            return sum(values)
        elif method == 'avg':
            return sum(values) / len(values)
        elif method == 'min':
            return min(values)
        elif method == 'max':
            return max(values)
        elif method == 'count':
            return len(values)
        elif method == 'count_distinct':
            return len(set(values))
        return sum(values)

    def _echarts_series_type(self):
        """Map visual type to ECharts series type."""
        mapping = {
            'bar': 'bar',
            'column': 'bar',
            'line': 'line',
            'area': 'line',
            'pie': 'pie',
            'doughnut': 'pie',
            'scatter': 'scatter',
            'radar': 'radar',
            'treemap': 'treemap',
            'heatmap': 'heatmap',
            'funnel': 'funnel',
            'gauge': 'gauge',
        }
        return mapping.get(self.visual_type, 'bar')

    def _parse_config(self):
        """Parse config JSON safely."""
        try:
            return json.loads(self.config_json or '{}')
        except Exception:
            return {}

    @api.constrains('width', 'height')
    def _check_dimensions(self):
        for v in self:
            if v.width < 1 or v.width > 12:
                raise ValidationError(_('Width must be between 1 and 12.'))
            if v.height < 1 or v.height > 20:
                raise ValidationError(_('Height must be between 1 and 20.'))

    # =========================================================================
    # RPC methods for frontend
    # =========================================================================

    @api.model
    def get_visual_chart_data(self, visual_id):
        """Get chart data for rendering on the frontend."""
        visual = self.browse(visual_id)
        if not visual.exists():
            return {'error': 'Visual not found'}
        return json.loads(visual.chart_data or '{}')

    def save_visual_config(self, config):
        """Save visual configuration from the frontend designer."""
        self.ensure_one()
        self.config_json = json.dumps(config)
        return True
