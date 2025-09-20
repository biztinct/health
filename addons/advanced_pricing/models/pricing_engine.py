# -*- coding: utf-8 -*-
from odoo import models, fields, api, tools
from odoo.exceptions import ValidationError
import json
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)

class AdvancedPricingEngine(models.Model):
    _name = 'advanced.pricing.engine'
    _description = 'Advanced Pricing Calculation Engine'
    _rec_name = 'name'
    _order = 'sequence, id'

    name = fields.Char('Engine Name', required=True)
    sequence = fields.Integer('Sequence', default=10)
    active = fields.Boolean('Active', default=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    
    rule_ids = fields.One2many('advanced.pricing.rule', 'engine_id', string='Pricing Rules')
    
    cache_duration = fields.Integer('Cache Duration (seconds)', default=300)
    enable_multi_level = fields.Boolean('Enable Multi-Level Rules', default=True)
    enable_cascade = fields.Boolean('Enable Cascading', default=True)
    
    @api.model
    @tools.ormcache('product_id', 'quantity', 'partner_id', 'context_str')
    def calculate_price(self, product_id, quantity, partner_id, context_data):
        """Calculate price with multi-level rules"""
        product = self.env['product.product'].browse(product_id)
        base_price = product.list_price
        
        context_str = json.dumps(context_data, sort_keys=True)
        
        # Apply Level 1 rules
        if self.enable_multi_level:
            level1_rules = self.rule_ids.filtered(lambda r: r.level == '1' and r.active)
            for rule in level1_rules.sorted('sequence'):
                if rule.evaluate_condition(product_id, partner_id, quantity, context_data):
                    base_price = rule.apply_action(base_price, context_data)
        
        # Apply Level 2 cascading rules
        if self.enable_cascade:
            level2_rules = self.rule_ids.filtered(lambda r: r.level == '2' and r.active)
            for rule in level2_rules.sorted('sequence'):
                if rule.evaluate_condition(product_id, partner_id, quantity, context_data):
                    base_price = rule.apply_cascading_action(base_price, context_data)
        
        return round(base_price, 2)