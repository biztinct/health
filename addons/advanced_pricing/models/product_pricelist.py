# -*- coding: utf-8 -*-
from odoo import models, fields, api

class ProductPricelist(models.Model):
    _inherit = 'product.pricelist'
    
    use_advanced_pricing = fields.Boolean('Use Advanced Pricing Engine', default=False)
    advanced_engine_id = fields.Many2one('advanced.pricing.engine', 'Advanced Pricing Engine')
    
    @api.model
    def _compute_price_rule(self, products_qty_partner, date=False, uom_id=False):
        """Override to use advanced pricing when enabled"""
        for pricelist in self:
            if pricelist.use_advanced_pricing and pricelist.advanced_engine_id:
                return self._compute_advanced_price_rule(products_qty_partner, date, uom_id)
        
        return super()._compute_price_rule(products_qty_partner, date, uom_id)
    
    def _compute_advanced_price_rule(self, products_qty_partner, date=False, uom_id=False):
        """Compute price using advanced pricing engine"""
        self.ensure_one()
        results = {}
        
        for product, qty, partner in products_qty_partner:
            context_data = {
                'date': date or fields.Datetime.now(),
                'uom_id': uom_id,
                'pricelist_id': self.id,
            }
            
            price = self.advanced_engine_id.calculate_price(
                product.id, qty, partner.id if partner else False, context_data
            )
            
            results[product.id] = (price, False)
        
        return results