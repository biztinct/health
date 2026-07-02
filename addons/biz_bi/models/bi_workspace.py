# -*- coding: utf-8 -*-
from odoo import api, fields, models


class BiWorkspace(models.Model):
    """Sharing and organization unit: datasets, charts and dashboards live in
    a workspace; record rules scope everything through it."""
    _name = 'bi.workspace'
    _description = 'BI Workspace'
    _inherit = ['mail.thread']
    _order = 'sequence, id'

    name = fields.Char(required=True, translate=True, tracking=True)
    code = fields.Char(help="Short technical code, used in exports and logs.")
    description = fields.Text(translate=True)
    sequence = fields.Integer(default=10)
    color = fields.Integer(default=0)
    icon = fields.Char(default='layout-grid',
                       help="Lucide icon name rendered on the workspace card.")
    active = fields.Boolean(default=True)
    is_default = fields.Boolean(
        help="Default workspace for new datasets and dashboards.")

    owner_id = fields.Many2one(
        'res.users', string='Owner', default=lambda self: self.env.user,
        tracking=True)
    member_ids = fields.Many2many(
        'res.users', 'bi_workspace_users_rel', 'workspace_id', 'user_id',
        string='Members',
        help="Users who can see this workspace. Empty = everyone with BI access.")
    group_ids = fields.Many2many(
        'res.groups', 'bi_workspace_groups_rel', 'workspace_id', 'group_id',
        string='Shared with Groups')
    company_ids = fields.Many2many(
        'res.company', string='Companies',
        help="Restrict the workspace to specific companies. Empty = all.")

    dataset_ids = fields.One2many('bi.dataset', 'workspace_id', string='Datasets')
    dashboard_ids = fields.One2many('bi.dashboard', 'workspace_id', string='Dashboards')
    dataset_count = fields.Integer(compute='_compute_counts')
    dashboard_count = fields.Integer(compute='_compute_counts')

    @api.depends('dataset_ids', 'dashboard_ids')
    def _compute_counts(self):
        for ws in self:
            ws.dataset_count = len(ws.dataset_ids)
            ws.dashboard_count = len(ws.dashboard_ids)

    @api.model
    def get_home_data(self):
        """Payload for the BI Home client action."""
        workspaces = self.search([])
        return {
            'workspaces': [{
                'id': ws.id,
                'name': ws.name,
                'description': ws.description or '',
                'color': ws.color,
                'icon': ws.icon or 'layout-grid',
                'dataset_count': ws.dataset_count,
                'dashboard_count': ws.dashboard_count,
                'is_default': ws.is_default,
            } for ws in workspaces],
            'is_creator': self.env.user.has_group('biz_bi.group_bi_creator'),
            'is_modeler': self.env.user.has_group('biz_bi.group_bi_modeler'),
            'is_admin': self.env.user.has_group('biz_bi.group_bi_admin'),
        }
