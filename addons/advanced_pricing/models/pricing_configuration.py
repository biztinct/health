# -*- coding: utf-8 -*-
from odoo import models, fields, api

class AdvancedPricingConfig(models.Model):
    _name = 'advanced.pricing.config'
    _description = 'Advanced Pricing Configuration'
    _rec_name = 'name'
    
    name = fields.Char('Configuration Name', required=True)
    active = fields.Boolean('Active', default=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    
    enable_visual_builder = fields.Boolean('Enable Visual Rule Builder', default=True)
    enable_caching = fields.Boolean('Enable Price Caching', default=True)
    cache_duration = fields.Integer('Cache Duration (seconds)', default=300)
    
    enable_api = fields.Boolean('Enable REST API', default=True)
    api_key = fields.Char('API Key', copy=False)
    
    default_engine_id = fields.Many2one('advanced.pricing.engine', 'Default Pricing Engine')
    
    enable_templates = fields.Boolean('Enable Rule Templates', default=True)
    enable_audit = fields.Boolean('Enable Audit Trail', default=True)
    
    @api.model
    def get_config(self):
        """Get active configuration for current company"""
        config = self.search([
            ('company_id', '=', self.env.company.id),
            ('active', '=', True)
        ], limit=1)
        
        if not config:
            config = self.create({
                'name': f'Default Config - {self.env.company.name}',
                'company_id': self.env.company.id
            })
        
        return config