# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class BiDashboard(models.Model):
    _name = 'bi.dashboard'
    _description = 'BI Dashboard'
    _inherit = ['mail.thread']
    _order = 'sequence, name'

    name = fields.Char(required=True, translate=True, tracking=True)
    description = fields.Text(translate=True)
    sequence = fields.Integer(default=10)
    workspace_id = fields.Many2one(
        'bi.workspace', required=True, index=True, ondelete='restrict',
        default=lambda self: self.env['bi.workspace'].search(
            [('is_default', '=', True)], limit=1))
    owner_id = fields.Many2one('res.users', default=lambda self: self.env.user,
                               index=True)
    active = fields.Boolean(default=True)

    widget_ids = fields.One2many('bi.dashboard.widget', 'dashboard_id',
                                 string='Widgets')
    filter_ids = fields.One2many('bi.dashboard.filter', 'dashboard_id',
                                 string='Global Filters')
    share_mode = fields.Selection([
        ('private', 'Private'),
        ('workspace', 'Workspace'),
    ], default='workspace', required=True)
    is_tv_mode_enabled = fields.Boolean(default=True)
    refresh_seconds = fields.Integer(
        default=300, help="Auto-reload interval in TV mode.")

    def get_dashboard_data(self):
        """Full payload for the dashboard client action."""
        self.ensure_one()
        self.env['bi.audit.log'].sudo().log(
            'dashboard_view', record=self)
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description or '',
            'workspace_id': self.workspace_id.id,
            'workspace': self.workspace_id.name,
            'can_edit': (
                self.owner_id == self.env.user
                and self.env.user.has_group('biz_bi.group_bi_creator')
            ) or self.env.user.has_group('biz_bi.group_bi_modeler'),
            'tv_enabled': self.is_tv_mode_enabled,
            'refresh_seconds': self.refresh_seconds,
            'widgets': [{
                'id': widget.id,
                'chart_id': widget.chart_id.id,
                'title': widget.title_override or widget.chart_id.name,
                'show_title': widget.show_title,
                'chart_type': widget.chart_id.chart_type,
                'config': widget.chart_id.config_json or {},
                'dataset_id': widget.chart_id.dataset_id.id,
                'grid': {'x': widget.grid_x, 'y': widget.grid_y,
                         'w': widget.grid_w, 'h': widget.grid_h},
            } for widget in self.widget_ids],
            'filters': [{
                'id': flt.id,
                'name': flt.name,
                'filter_type': flt.filter_type,
                'default': flt.default_json or {},
                'mappings': [{
                    'dataset_id': mapping.dataset_id.id,
                    'field_id': mapping.field_id.id,
                    'data_type': mapping.field_id.data_type,
                    'selection_labels':
                        mapping.field_id.selection_labels_json or {},
                } for mapping in flt.mapping_ids],
            } for flt in self.filter_ids],
        }

    def save_layout(self, layout):
        """Persist GridStack positions: [{widget_id, x, y, w, h}]."""
        self.ensure_one()
        widgets_by_id = {w.id: w for w in self.widget_ids}
        for item in layout:
            widget = widgets_by_id.get(item.get('widget_id'))
            if widget:
                widget.write({
                    'grid_x': item.get('x', 0),
                    'grid_y': item.get('y', 0),
                    'grid_w': item.get('w', 4),
                    'grid_h': item.get('h', 4),
                })
        return True

    def add_chart(self, chart_id):
        """Place a chart on the dashboard below existing widgets."""
        self.ensure_one()
        chart = self.env['bi.chart'].browse(int(chart_id))
        chart.check_access('read')
        bottom = max(
            (w.grid_y + w.grid_h for w in self.widget_ids), default=0)
        defaults = {'kpi': (3, 3), 'table': (6, 5)}
        width, height = defaults.get(chart.chart_type, (6, 5))
        widget = self.env['bi.dashboard.widget'].create({
            'dashboard_id': self.id,
            'chart_id': chart.id,
            'grid_x': 0, 'grid_y': bottom,
            'grid_w': width, 'grid_h': height,
        })
        return widget.id


class BiDashboardWidget(models.Model):
    _name = 'bi.dashboard.widget'
    _description = 'BI Dashboard Widget'
    _order = 'grid_y, grid_x'

    dashboard_id = fields.Many2one('bi.dashboard', required=True,
                                   ondelete='cascade', index=True)
    chart_id = fields.Many2one('bi.chart', required=True, ondelete='cascade')
    title_override = fields.Char(translate=True)
    show_title = fields.Boolean(default=True)
    grid_x = fields.Integer(default=0)
    grid_y = fields.Integer(default=0)
    grid_w = fields.Integer(default=6)
    grid_h = fields.Integer(default=5)
    local_filters_json = fields.Json()


class BiDashboardFilter(models.Model):
    """A dashboard-level filter mapped onto one field per dataset, so a
    single date picker can drive widgets built on different datasets."""
    _name = 'bi.dashboard.filter'
    _description = 'BI Dashboard Filter'
    _order = 'sequence'

    dashboard_id = fields.Many2one('bi.dashboard', required=True,
                                   ondelete='cascade', index=True)
    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    filter_type = fields.Selection([
        ('list', 'Value List'),
        ('daterange', 'Date Range'),
        ('relative_date', 'Relative Date'),
        ('search', 'Text Search'),
    ], required=True, default='list')
    default_json = fields.Json(help='{"op": "relative", "value": "this_month"}')
    mapping_ids = fields.One2many('bi.dashboard.filter.mapping', 'filter_id',
                                  string='Field Mappings')


class BiDashboardFilterMapping(models.Model):
    _name = 'bi.dashboard.filter.mapping'
    _description = 'BI Dashboard Filter Mapping'

    filter_id = fields.Many2one('bi.dashboard.filter', required=True,
                                ondelete='cascade')
    dataset_id = fields.Many2one('bi.dataset', required=True,
                                 ondelete='cascade')
    field_id = fields.Many2one(
        'bi.field', required=True, ondelete='cascade',
        domain="[('dataset_id', '=', dataset_id)]")

    _sql_constraints = [
        ('dataset_uniq', 'unique(filter_id, dataset_id)',
         'One field mapping per dataset per filter.'),
    ]
