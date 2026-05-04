# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class BiBusinessDomain(models.Model):
    """Curated business data domains — like Power BI 'workspaces'.
    
    Each domain groups related Odoo models under a business-friendly name
    so managers see 'Finance Analytics' instead of 'account.move'.
    """
    _name = 'bi.business.domain'
    _description = 'BI Business Domain'
    _order = 'sequence, name'

    name = fields.Char('Domain Name', required=True, translate=True)
    description = fields.Text('Description', translate=True)
    icon = fields.Char('Icon', default='fa-chart-bar',
                       help='FontAwesome icon class')
    color = fields.Char('Color', default='#875A7B',
                        help='Theme color for this domain')
    sequence = fields.Integer('Sequence', default=10)
    active = fields.Boolean('Active', default=True)

    # Curated models in this domain
    allowed_model_ids = fields.Many2many(
        'ir.model',
        'bi_domain_model_rel',
        'domain_id', 'model_id',
        string='Available Models',
        help='Odoo models available for dataset creation in this domain'
    )

    # Access control
    group_ids = fields.Many2many(
        'res.groups',
        'bi_domain_group_rel',
        'domain_id', 'group_id',
        string='Allowed Groups',
        help='User groups that can access this domain. Empty = everyone.'
    )

    dataset_count = fields.Integer('Datasets', compute='_compute_dataset_count')

    @api.depends()
    def _compute_dataset_count(self):
        for domain in self:
            domain.dataset_count = self.env['bi.dataset'].search_count([
                ('domain_id', '=', domain.id)
            ])

    @api.model
    def get_user_domains(self):
        """Get domains accessible by current user, used by frontend."""
        domains = self.search([])
        result = []
        user_groups = self.env.user.groups_id
        for domain in domains:
            # If no groups set, domain is public
            if domain.group_ids and not (domain.group_ids & user_groups):
                continue
            result.append({
                'id': domain.id,
                'name': domain.name,
                'description': domain.description or '',
                'icon': domain.icon or 'fa-chart-bar',
                'color': domain.color or '#875A7B',
                'model_count': len(domain.allowed_model_ids),
                'dataset_count': domain.dataset_count,
            })
        return result

    @api.model
    def get_domain_models(self, domain_id):
        """Get models in a domain with friendly names for the explorer."""
        domain = self.browse(domain_id)
        if not domain.exists():
            return []
        
        result = []
        for model in domain.allowed_model_ids:
            # Check user has read access to this model
            try:
                self.env[model.model].check_access_rights('read')
            except Exception:
                continue
            
            result.append({
                'id': model.id,
                'name': model.name,  # Friendly name from ir.model
                'model': model.model,  # Technical name
            })
        
        return sorted(result, key=lambda x: x['name'])

    def action_view_datasets(self):
        """View datasets in this domain."""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Datasets: %s') % self.name,
            'res_model': 'bi.dataset',
            'view_mode': 'list,form',
            'domain': [('domain_id', '=', self.id)],
            'context': {'default_domain_id': self.id},
        }
