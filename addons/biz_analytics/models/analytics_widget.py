# -*- coding: utf-8 -*-
import json
from datetime import datetime, timedelta

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class AnalyticsWidget(models.Model):
    """Individual widget/chart configuration"""
    _name = 'analytics.widget'
    _description = 'Analytics Widget'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'dashboard_id, sequence, name'

    name = fields.Char('Widget Name', required=True, tracking=True)
    description = fields.Text('Description')
    
    # Widget Configuration
    dashboard_id = fields.Many2one('analytics.dashboard', string='Dashboard', 
                                  required=True, ondelete='cascade')
    dataset_id = fields.Many2one('analytics.dataset', string='Dataset',
                                required=True, ondelete='cascade')
    
    sequence = fields.Integer('Sequence', default=10)
    active = fields.Boolean('Active', default=True, tracking=True)
    
    # Widget Type and Display
    widget_type = fields.Selection([
        ('chart', 'Chart'),
        ('table', 'Data Table'),
        ('metric', 'Key Metric'),
        ('text', 'Text Widget'),
        ('filter', 'Filter Widget')
    ], string='Widget Type', default='chart', required=True)
    
    chart_type = fields.Selection([
        ('bar', 'Bar Chart'),
        ('line', 'Line Chart'),
        ('pie', 'Pie Chart'),
        ('doughnut', 'Doughnut Chart'),
        ('area', 'Area Chart'),
        ('scatter', 'Scatter Plot'),
        ('radar', 'Radar Chart'),
        ('gauge', 'Gauge Chart'),
        ('heatmap', 'Heatmap'),
        ('combo', 'Combo Chart')
    ], string='Chart Type', default='bar')
    
    # Position and Size
    position_x = fields.Integer('Position X', default=0)
    position_y = fields.Integer('Position Y', default=0)
    width = fields.Integer('Width', default=6, help='Widget width (1-12 grid units)')
    height = fields.Integer('Height', default=4, help='Widget height in grid units')
    
    # Data Configuration
    x_axis_field_id = fields.Many2one('analytics.dataset.field', string='X-Axis Field',
                                     domain="[('dataset_id', '=', dataset_id), ('field_type', 'in', ['dimension', 'date'])]")
    y_axis_field_id = fields.Many2one('analytics.dataset.field', string='Y-Axis Field',
                                     domain="[('dataset_id', '=', dataset_id), ('field_type', '=', 'measure')]")
    color_field_id = fields.Many2one('analytics.dataset.field', string='Color Grouping Field',
                                    domain="[('dataset_id', '=', dataset_id), ('field_type', '=', 'dimension')]")
    
    # Additional Fields for Complex Charts
    additional_field_ids = fields.Many2many('analytics.dataset.field', string='Additional Fields',
                                          domain="[('dataset_id', '=', dataset_id)]")
    
    # Filters and Aggregation
    widget_filters = fields.Text('Widget Filters', default='[]',
                                help='Specific filters for this widget')
    aggregation_method = fields.Selection([
        ('sum', 'Sum'),
        ('avg', 'Average'),
        ('min', 'Minimum'),
        ('max', 'Maximum'),
        ('count', 'Count'),
        ('count_distinct', 'Count Distinct')
    ], string='Aggregation Method', default='sum')
    
    # Display Options
    title_display = fields.Boolean('Show Title', default=True)
    legend_display = fields.Boolean('Show Legend', default=True)
    grid_display = fields.Boolean('Show Grid', default=True)
    animation_enabled = fields.Boolean('Enable Animation', default=True)
    
    # Styling
    color_scheme = fields.Selection([
        ('default', 'Default'),
        ('blue', 'Blue Theme'),
        ('green', 'Green Theme'),
        ('orange', 'Orange Theme'),
        ('purple', 'Purple Theme'),
        ('custom', 'Custom Colors')
    ], string='Color Scheme', default='default')
    
    custom_colors = fields.Text('Custom Colors', default='[]',
                               help='JSON array of custom colors')
    background_color = fields.Char('Background Color', default='transparent')
    border_color = fields.Char('Border Color', default='#e0e0e0')
    
    # Advanced Configuration (JSON)
    config_data = fields.Text('Advanced Configuration', default='{}',
                             help='Advanced widget configuration in JSON format')
    
    # Data Refresh
    auto_refresh = fields.Boolean('Auto Refresh', default=True)
    refresh_interval = fields.Integer('Refresh Interval (minutes)', default=5)
    last_refresh = fields.Datetime('Last Refresh')
    
    # Interactivity
    clickable = fields.Boolean('Enable Click Events', default=True)
    drilldown_enabled = fields.Boolean('Enable Drill-down', default=False)
    export_enabled = fields.Boolean('Enable Export', default=True)
    
    # Computed Fields
    widget_data = fields.Text('Widget Data', compute='_compute_widget_data')
    chart_config = fields.Text('Chart Configuration', compute='_compute_chart_config')

    @api.depends('dataset_id', 'x_axis_field_id', 'y_axis_field_id', 'color_field_id', 'widget_filters')
    def _compute_widget_data(self):
        """Compute widget data for display"""
        for widget in self:
            try:
                data = widget._get_widget_data()
                widget.widget_data = json.dumps(data)
            except Exception as e:
                widget.widget_data = json.dumps({'error': str(e)})

    def _compute_chart_config(self):
        """Generate Chart.js configuration"""
        for widget in self:
            config = widget._generate_chart_config()
            widget.chart_config = json.dumps(config)

    def _get_widget_data(self):
        """Get processed data for the widget"""
        if not self.dataset_id or not self.x_axis_field_id:
            return {'labels': [], 'datasets': []}
        
        # Get domain from dataset and widget filters
        domain = eval(self.dataset_id.domain or '[]')
        widget_filters = eval(self.widget_filters or '[]')
        domain.extend(widget_filters)
        
        # Get records
        records = self.env[self.dataset_id.model_name].search(domain)
        
        if not records:
            return {'labels': [], 'datasets': []}
        
        # Process data based on chart type and fields
        return self._process_chart_data(records)

    def _process_chart_data(self, records):
        """Process records into chart data format"""
        data = {'labels': [], 'datasets': []}
        
        x_field = self.x_axis_field_id.field_name
        y_field = self.y_axis_field_id.field_name if self.y_axis_field_id else None
        color_field = self.color_field_id.field_name if self.color_field_id else None
        
        # Group data
        grouped_data = {}
        labels = set()
        
        for record in records:
            x_value = self._get_field_value(record, x_field)
            y_value = self._get_field_value(record, y_field) if y_field else 1
            color_value = self._get_field_value(record, color_field) if color_field else 'Default'
            
            str_x = str(x_value) if x_value is not None else 'N/A'
            str_color = str(color_value) if color_value is not None else 'Default'
            
            labels.add(str_x)
            
            if str_color not in grouped_data:
                grouped_data[str_color] = {}
            if str_x not in grouped_data[str_color]:
                grouped_data[str_color][str_x] = []
            
            grouped_data[str_color][str_x].append(float(y_value) if y_value is not None else 0)
        
        # Sort labels
        data['labels'] = sorted(list(labels))
        
        # Create datasets
        colors = self._get_color_palette(len(grouped_data))
        for i, (series_name, series_data) in enumerate(grouped_data.items()):
            dataset_values = []
            for label in data['labels']:
                values = series_data.get(label, [0])
                # Apply aggregation
                if self.aggregation_method == 'sum':
                    value = sum(values)
                elif self.aggregation_method == 'avg':
                    value = sum(values) / len(values) if values else 0
                elif self.aggregation_method == 'min':
                    value = min(values) if values else 0
                elif self.aggregation_method == 'max':
                    value = max(values) if values else 0
                elif self.aggregation_method == 'count':
                    value = len(values)
                elif self.aggregation_method == 'count_distinct':
                    value = len(set(values))
                else:
                    value = sum(values)
                dataset_values.append(value)
            
            dataset = {
                'label': series_name,
                'data': dataset_values,
                'backgroundColor': colors[i % len(colors)],
                'borderColor': colors[i % len(colors)],
                'borderWidth': 1
            }
            data['datasets'].append(dataset)
        
        return data

    def _get_field_value(self, record, field_name):
        """Get field value from record with proper handling"""
        if not field_name:
            return None
            
        try:
            value = record[field_name]
            if hasattr(value, 'name'):  # Many2one
                return value.name
            elif hasattr(value, 'mapped'):  # Many2many
                return ', '.join(value.mapped('name'))
            return value
        except Exception:
            return None

    def _get_color_palette(self, count):
        """Get color palette for charts"""
        if self.color_scheme == 'custom' and self.custom_colors:
            try:
                return json.loads(self.custom_colors)
            except Exception:
                pass
        
        # Default color schemes
        palettes = {
            'default': ['#875A7B', '#E94B3C', '#00A09D', '#F19600', '#5D4070'],
            'blue': ['#4285F4', '#34A853', '#FBBC05', '#EA4335', '#9AA0A6'],
            'green': ['#00A09D', '#00C4A7', '#00E8CC', '#B2F5EA', '#4A5568'],
            'orange': ['#F19600', '#FF8F00', '#FFA726', '#FFB74D', '#FFCC02'],
            'purple': ['#875A7B', '#9C27B0', '#BA68C8', '#CE93D8', '#E1BEE7']
        }
        
        colors = palettes.get(self.color_scheme, palettes['default'])
        
        # Extend colors if needed
        while len(colors) < count:
            colors.extend(colors)
        
        return colors[:count]

    def _generate_chart_config(self):
        """Generate Chart.js configuration"""
        config = {
            'type': self.chart_type or 'bar',
            'data': json.loads(self.widget_data or '{"labels": [], "datasets": []}'),
            'options': {
                'responsive': True,
                'maintainAspectRatio': False,
                'plugins': {
                    'title': {
                        'display': self.title_display,
                        'text': self.name
                    },
                    'legend': {
                        'display': self.legend_display
                    }
                },
                'scales': {},
                'animation': {
                    'duration': 1000 if self.animation_enabled else 0
                }
            }
        }
        
        # Add scales based on chart type
        if self.chart_type in ['bar', 'line', 'area']:
            config['options']['scales'] = {
                'x': {
                    'display': True,
                    'title': {
                        'display': bool(self.x_axis_field_id),
                        'text': self.x_axis_field_id.field_label if self.x_axis_field_id else ''
                    },
                    'grid': {
                        'display': self.grid_display
                    }
                },
                'y': {
                    'display': True,
                    'title': {
                        'display': bool(self.y_axis_field_id),
                        'text': self.y_axis_field_id.field_label if self.y_axis_field_id else ''
                    },
                    'grid': {
                        'display': self.grid_display
                    }
                }
            }
        
        # Merge with advanced configuration
        try:
            advanced_config = json.loads(self.config_data or '{}')
            config = self._deep_merge(config, advanced_config)
        except Exception:
            pass
        
        return config

    def _deep_merge(self, dict1, dict2):
        """Deep merge two dictionaries"""
        result = dict1.copy()
        for key, value in dict2.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    @api.constrains('width', 'height')
    def _check_dimensions(self):
        for widget in self:
            if widget.width < 1 or widget.width > 12:
                raise ValidationError(_('Widget width must be between 1 and 12 grid units.'))
            if widget.height < 1 or widget.height > 20:
                raise ValidationError(_('Widget height must be between 1 and 20 grid units.'))

    @api.constrains('position_x', 'position_y')
    def _check_position(self):
        for widget in self:
            if widget.position_x < 0 or widget.position_y < 0:
                raise ValidationError(_('Widget position cannot be negative.'))

    def action_refresh_data(self):
        """Manually refresh widget data"""
        self.last_refresh = fields.Datetime.now()
        self.invalidate_cache(['widget_data'])
        self._compute_widget_data()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Widget Refreshed'),
                'message': _('Widget "%s" has been refreshed successfully.') % self.name,
                'type': 'success'
            }
        }

    def action_preview_widget(self):
        """Preview widget in popup"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Preview: %s') % self.name,
            'res_model': 'analytics.widget',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('biz_analytics.view_analytics_widget_preview').id,
            'target': 'new'
        }

    def action_duplicate_widget(self):
        """Duplicate widget"""
        new_widget = self.copy({
            'name': _('%s (Copy)') % self.name,
            'position_x': self.position_x + 1,
            'position_y': self.position_y + 1
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Duplicated Widget'),
            'res_model': 'analytics.widget',
            'res_id': new_widget.id,
            'view_mode': 'form',
            'target': 'current'
        }