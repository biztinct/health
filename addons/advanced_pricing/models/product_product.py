# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    rounding_rule = fields.Selection([
        ('round_1000', 'Round up to next 1,000'),
        ('round_5min', 'Round up to next 5 mins'),
        ('round_30min', 'Round up to next 30 mins'),
        ('round_half_hour', 'Round up to next half hour'),
        ('round_hour', 'Round up to next hour'),
    ], string='Rounding Rule',
       help='Rounding rule applied to the calculated price for this product')


class ProductProduct(models.Model):
    _inherit = 'product.product'

    catalog_catchment_area = fields.Selection([
        ('hanoi', 'Hanoi'),
        ('tphcm', 'Ho Chi Minh City'),
    ], string='Catchment Area', compute='_compute_catalog_catchment_area', store=True)

    @api.depends('default_code')
    def _compute_catalog_catchment_area(self):
        for product in self:
            code = (product.default_code or '').lower()
            if code.endswith('_hanoi') or '_hanoi_' in code:
                product.catalog_catchment_area = 'hanoi'
            elif code.endswith('_tphcm') or '_tphcm_' in code:
                product.catalog_catchment_area = 'tphcm'
            else:
                product.catalog_catchment_area = False
    
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
