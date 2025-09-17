# -*- coding: utf-8 -*-
import json
from collections import defaultdict
from datetime import datetime, timedelta

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class AnalyticsDashboard(models.Model):
    """Analytics Dashboard Configuration"""
    _name = 'analytics.dashboard'
    _description = 'Analytics Dashboard'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, name'

    name = fields.Char('Dashboard Name', required=True, tracking=True)
    description = fields.Text('Description')
    
    # Dashboard Settings
    sequence = fields.Integer('Sequence', default=10)
    active = fields.Boolean('Active', default=True, tracking=True)
    color = fields.Integer('Color Index', default=0)
    
    # Layout Configuration
    layout_type = fields.Selection([
        ('grid', 'Grid Layout'),
        ('kanban', 'Kanban Layout'),
        ('list', 'List Layout')
    ], string='Layout Type', default='grid', required=True)
    
    columns = fields.Integer('Grid Columns', default=4, help='Number of columns in grid layout')
    widget_spacing = fields.Integer('Widget Spacing', default=20, help='Spacing between widgets in pixels')
    
    # Theme and Styling
    theme = fields.Selection([
        ('light', 'Light Theme'),
        ('dark', 'Dark Theme'),
        ('auto', 'Auto (System)')
    ], string='Theme', default='light')
    
    background_color = fields.Char('Background Color', default='#ffffff')
    accent_color = fields.Char('Accent Color', default='#875A7B')
    
    # Access Control
    user_ids = fields.Many2many('res.users', string='Allowed Users',
                               help='Users who can access this dashboard. Leave empty for all users.')
    group_ids = fields.Many2many('res.groups', string='Allowed Groups',
                                help='Groups who can access this dashboard.')
    is_public = fields.Boolean('Public Dashboard', default=False,
                              help='Dashboard visible to all users')
    
    # Dashboard Content
    widget_ids = fields.One2many('analytics.widget', 'dashboard_id', string='Widgets')
    dataset_ids = fields.Many2many('analytics.dataset', string='Available Datasets',
                                  help='Datasets available for widgets in this dashboard')
    
    # Computed Fields
    widget_count = fields.Integer('Widget Count', compute='_compute_widget_count')
    last_updated = fields.Datetime('Last Updated', compute='_compute_last_updated')
    
    # Dashboard Data (JSON)
    dashboard_data = fields.Text('Dashboard Data', compute='_compute_dashboard_data')
    filter_data = fields.Text('Filter Configuration', default='{}')
    layout_data = fields.Text('Layout Configuration', default='{}')
    
    # Auto-refresh Settings
    auto_refresh = fields.Boolean('Auto Refresh', default=False)
    refresh_interval = fields.Integer('Refresh Interval (minutes)', default=5)
    
    # Export Settings
    allow_export = fields.Boolean('Allow Export', default=True)
    export_formats = fields.Selection([
        ('pdf', 'PDF Only'),
        ('excel', 'Excel Only'),
        ('both', 'PDF and Excel'),
        ('all', 'All Formats (PDF, Excel, PNG)')
    ], string='Export Formats', default='all')

    @api.depends('widget_ids')
    def _compute_widget_count(self):
        for dashboard in self:
            dashboard.widget_count = len(dashboard.widget_ids)

    @api.depends('widget_ids.write_date', 'write_date')
    def _compute_last_updated(self):
        for dashboard in self:
            dates = [dashboard.write_date] + [w.write_date for w in dashboard.widget_ids if w.write_date]
            dashboard.last_updated = max(dates) if dates else dashboard.write_date

    def _compute_dashboard_data(self):
        """Compute dashboard data similar to Odoo's kanban dashboard"""
        for dashboard in self:
            data = {
                'id': dashboard.id,
                'name': dashboard.name,
                'theme': dashboard.theme,
                'layout': {
                    'type': dashboard.layout_type,
                    'columns': dashboard.columns,
                    'spacing': dashboard.widget_spacing
                },
                'colors': {
                    'background': dashboard.background_color,
                    'accent': dashboard.accent_color
                },
                'widgets': [],
                'filters': json.loads(dashboard.filter_data or '{}'),
                'settings': {
                    'auto_refresh': dashboard.auto_refresh,
                    'refresh_interval': dashboard.refresh_interval,
                    'allow_export': dashboard.allow_export,
                    'export_formats': dashboard.export_formats
                }
            }
            
            # Add widget data
            for widget in dashboard.widget_ids.filtered('active'):
                widget_data = {
                    'id': widget.id,
                    'name': widget.name,
                    'type': widget.widget_type,
                    'chart_type': widget.chart_type,
                    'position': {
                        'x': widget.position_x,
                        'y': widget.position_y,
                        'width': widget.width,
                        'height': widget.height
                    },
                    'config': json.loads(widget.config_data or '{}'),
                    'dataset_id': widget.dataset_id.id if widget.dataset_id else False
                }
                data['widgets'].append(widget_data)
            
            dashboard.dashboard_data = json.dumps(data)

    @api.constrains('columns')
    def _check_columns(self):
        for dashboard in self:
            if dashboard.columns < 1 or dashboard.columns > 12:
                raise ValidationError(_('Grid columns must be between 1 and 12.'))

    @api.constrains('refresh_interval')
    def _check_refresh_interval(self):
        for dashboard in self:
            if dashboard.auto_refresh and dashboard.refresh_interval < 1:
                raise ValidationError(_('Refresh interval must be at least 1 minute.'))

    def action_view_widgets(self):
        """View widgets in this dashboard"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Dashboard Widgets'),
            'res_model': 'analytics.widget',
            'view_mode': 'list,form',
            'domain': [('dashboard_id', '=', self.id)],
            'context': {
                'default_dashboard_id': self.id,
                'create': True
            }
        }

    def action_preview_dashboard(self):
        """Preview dashboard (will open analytics view)"""
        return {
            'type': 'ir.actions.act_window',
            'name': self.name,
            'res_model': 'analytics.dashboard',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('biz_analytics.view_analytics_dashboard_preview').id,
            'target': 'new'
        }

    def action_duplicate_dashboard(self):
        """Duplicate dashboard with all widgets"""
        new_dashboard = self.copy({
            'name': _('%s (Copy)') % self.name,
        })
        
        # Copy all widgets
        for widget in self.widget_ids:
            widget.copy({'dashboard_id': new_dashboard.id})
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Duplicated Dashboard'),
            'res_model': 'analytics.dashboard',
            'res_id': new_dashboard.id,
            'view_mode': 'form',
            'target': 'current'
        }

    def refresh_dashboard_data(self):
        """Force refresh dashboard data"""
        # Clear cache and recompute
        self.invalidate_cache(['dashboard_data'])
        self._compute_dashboard_data()
        return True

    def get_user_access(self):
        """Check if current user has access to this dashboard"""
        if self.is_public:
            return True
        if not self.user_ids and not self.group_ids:
            return True
        if self.user_ids and self.env.user in self.user_ids:
            return True
        if self.group_ids and any(group in self.env.user.groups_id for group in self.group_ids):
            return True
        return False

    @api.model
    def get_user_dashboards(self):
        """Get all dashboards accessible by current user"""
        dashboards = self.search([
            '|', '|',
            ('is_public', '=', True),
            ('user_ids', '=', False),
            ('user_ids', 'in', self.env.user.ids)
        ])
        
        # Filter by groups
        accessible_dashboards = []
        for dashboard in dashboards:
            if dashboard.get_user_access():
                accessible_dashboards.append({
                    'id': dashboard.id,
                    'name': dashboard.name,
                    'description': dashboard.description,
                    'widget_count': dashboard.widget_count,
                    'last_updated': dashboard.last_updated,
                    'theme': dashboard.theme
                })
        
        return accessible_dashboards