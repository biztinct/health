# -*- coding: utf-8 -*-
from odoo import models, fields, api

class ProductProduct(models.Model):
    _inherit = 'product.product'
    
    def action_return_to_healthcare_quote(self):
        """Return to Healthcare Quote from product catalog"""
        context = self.env.context
        quote_order_id = context.get('quote_order_id') or context.get('order_id')
        
        if not quote_order_id:
            return False
            
        # Get the quote/sale order
        quote = self.env['sale.order'].browse(quote_order_id)
        
        if not quote.exists():
            return False
            
        # Return to Healthcare Quote form
        return {
            'type': 'ir.actions.act_window',
            'name': f'Healthcare Quote - {quote.name}',
            'res_model': 'sale.order',
            'res_id': quote.id,
            'view_mode': 'form',
            'view_id': self.env.ref('health_fieldservice.view_healthcare_quote_form_custom').id,
            'target': 'main',
            'context': {
                'healthcare_context': True,
                'from_catalog': True,
            }
        }