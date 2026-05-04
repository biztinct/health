# -*- coding: utf-8 -*-

import json
import logging

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class BiReportPage(models.Model):
    """A dashboard/report page — like a Power BI report page or Tableau dashboard.
    
    Contains multiple visuals arranged on a GridStack canvas with global filters.
    """
    _name = 'bi.report.page'
    _description = 'BI Report Page'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, name'

    name = fields.Char('Report Name', required=True, tracking=True)
    description = fields.Text('Description')
    sequence = fields.Integer('Sequence', default=10)
    active = fields.Boolean('Active', default=True)

    # Visuals
    visual_ids = fields.One2many('bi.visual', 'report_page_id',
                                 string='Visuals')

    # Available datasets
    dataset_ids = fields.Many2many('bi.dataset',
                                    'bi_report_dataset_rel',
                                    'report_id', 'dataset_id',
                                    string='Available Datasets')

    # Layout (GridStack positions JSON)
    grid_layout = fields.Text('Grid Layout', default='[]',
                              help='GridStack widget positions JSON')

    # Global filters
    global_filters = fields.Text('Global Filters', default='[]')

    # Theme
    theme = fields.Selection([
        ('light', 'Light'),
        ('dark', 'Dark'),
        ('auto', 'System Default'),
    ], string='Theme', default='light')
    background_color = fields.Char('Background Color', default='#f8f9fa')
    accent_color = fields.Char('Accent Color', default='#6366f1')

    # Auto-refresh
    auto_refresh = fields.Boolean('Auto Refresh', default=False)
    refresh_interval = fields.Integer('Refresh Interval (seconds)',
                                      default=300)

    # Access control
    is_public = fields.Boolean('Public', default=False, tracking=True)
    owner_id = fields.Many2one('res.users', string='Owner',
                               default=lambda self: self.env.user)
    user_ids = fields.Many2many('res.users',
                                'bi_report_user_rel',
                                'report_id', 'user_id',
                                string='Allowed Users')
    group_ids = fields.Many2many('res.groups',
                                 'bi_report_group_rel',
                                 'report_id', 'group_id',
                                 string='Allowed Groups')

    # Export
    allow_export = fields.Boolean('Allow Export', default=True)

    # Computed
    visual_count = fields.Integer('Visuals', compute='_compute_visual_count')

    @api.depends('visual_ids')
    def _compute_visual_count(self):
        for page in self:
            page.visual_count = len(page.visual_ids)

    # =========================================================================
    # Access
    # =========================================================================

    def check_user_access(self):
        """Check if current user can view this report."""
        self.ensure_one()
        if self.is_public:
            return True
        if self.owner_id == self.env.user:
            return True
        if not self.user_ids and not self.group_ids:
            return True
        if self.env.user in self.user_ids:
            return True
        if self.group_ids & self.env.user.groups_id:
            return True
        return False

    # =========================================================================
    # RPC for frontend
    # =========================================================================

    @api.model
    def get_user_reports(self):
        """Get all report pages accessible by the current user."""
        reports = self.search([])
        result = []
        for report in reports:
            if report.check_user_access():
                result.append({
                    'id': report.id,
                    'name': report.name,
                    'description': report.description or '',
                    'visual_count': report.visual_count,
                    'theme': report.theme,
                    'owner': report.owner_id.name,
                })
        return result

    def get_report_data(self):
        """Get full report data for rendering the dashboard."""
        self.ensure_one()
        if not self.check_user_access():
            return {'error': 'Access denied'}

        visuals = []
        for visual in self.visual_ids.filtered('active'):
            try:
                chart_data = json.loads(visual.chart_data or '{}')
            except Exception:
                chart_data = {}

            try:
                config = json.loads(visual.config_json or '{}')
            except Exception:
                config = {}

            visuals.append({
                'id': visual.id,
                'name': visual.name,
                'visual_type': visual.visual_type,
                'config': config,
                'chart_data': chart_data,
                'position': {
                    'x': visual.position_x,
                    'y': visual.position_y,
                    'w': visual.width,
                    'h': visual.height,
                },
                'styling': {
                    'color_palette': visual.color_palette,
                    'show_legend': visual.show_legend,
                    'show_labels': visual.show_labels,
                    'show_grid': visual.show_grid,
                    'background_color': visual.background_color,
                    'enable_animation': visual.enable_animation,
                },
                'dataset_name': visual.dataset_id.name,
            })

        return {
            'id': self.id,
            'name': self.name,
            'theme': self.theme,
            'background_color': self.background_color,
            'accent_color': self.accent_color,
            'visuals': visuals,
            'grid_layout': json.loads(self.grid_layout or '[]'),
            'global_filters': json.loads(self.global_filters or '[]'),
            'auto_refresh': self.auto_refresh,
            'refresh_interval': self.refresh_interval,
            'allow_export': self.allow_export,
        }

    def save_grid_layout(self, layout):
        """Save GridStack layout from frontend."""
        self.ensure_one()
        self.grid_layout = json.dumps(layout)
        
        # Update visual positions
        for item in layout:
            visual_id = item.get('id')
            if visual_id:
                visual = self.env['bi.visual'].browse(int(visual_id))
                if visual.exists():
                    visual.write({
                        'position_x': item.get('x', 0),
                        'position_y': item.get('y', 0),
                        'width': item.get('w', 6),
                        'height': item.get('h', 4),
                    })
        return True

    # =========================================================================
    # Actions
    # =========================================================================

    def action_open_report_canvas(self):
        """Open the interactive report canvas (frontend component)."""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'bi_studio.report_canvas',
            'params': {
                'report_id': self.id,
            },
            'name': self.name,
        }
