# -*- coding: utf-8 -*-
from odoo import models, fields, api

class ProductPricelist(models.Model):
    _inherit = 'product.pricelist'
    
    use_advanced_pricing = fields.Boolean('Use Advanced Pricing Engine', default=False)
    advanced_engine_id = fields.Many2one('advanced.pricing.engine', 'Advanced Pricing Engine')
    
    # Advanced pricing is handled in sale.order.line._compute_advanced_price()
    # This keeps the Catalog functionality working while still applying our pricing rules