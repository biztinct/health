# -*- coding: utf-8 -*-
from odoo import models, fields, api

class SaleOrder(models.Model):
    _inherit = 'sale.order'
    
    booking_id = fields.Many2one('booking.model', 'Related Booking')
    use_advanced_pricing = fields.Boolean('Use Advanced Pricing', 
                                         compute='_compute_use_advanced_pricing')
    advanced_pricing_details = fields.Text('Pricing Calculation Details')
    
    @api.depends('pricelist_id.use_advanced_pricing')
    def _compute_use_advanced_pricing(self):
        """Check if order uses advanced pricing"""
        for order in self:
            order.use_advanced_pricing = order.pricelist_id.use_advanced_pricing
    
    def action_recalculate_advanced_prices(self):
        """Recalculate prices using advanced pricing engine"""
        self.ensure_one()
        
        if not self.use_advanced_pricing:
            return
        
        for line in self.order_line:
            line._compute_advanced_price()
        
        return True

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'
    
    base_price = fields.Float('Base Price', readonly=True)
    price_calculation_log = fields.Text('Price Calculation Log')
    applied_rules = fields.Text('Applied Rules')
    
    @api.depends('product_id', 'product_uom_qty', 'order_id.booking_id')
    def _compute_advanced_price(self):
        """Compute price using advanced pricing engine"""
        for line in self:
            if not line.order_id.use_advanced_pricing:
                continue
            
            if not line.order_id.pricelist_id.advanced_engine_id:
                continue
            
            engine = line.order_id.pricelist_id.advanced_engine_id
            
            context_data = {
                'order_id': line.order_id.id,
                'partner_id': line.order_id.partner_id.id,
                'date_order': line.order_id.date_order
            }
            
            if line.order_id.booking_id:
                booking = line.order_id.booking_id
                context_data['booking'] = {
                    'id': booking.id,
                    'distance': booking.distance,
                    'appointment_time': booking.appointment_time.hour if booking.appointment_time else 0,
                    'is_holiday': booking.is_holiday,
                }
            
            price = engine.calculate_price(
                line.product_id.id,
                line.product_uom_qty,
                line.order_id.partner_id.id,
                context_data
            )
            
            line.price_unit = price
            line.base_price = line.product_id.list_price