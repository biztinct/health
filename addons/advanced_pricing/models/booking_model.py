# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import datetime

class BookingModel(models.Model):
    _name = 'booking.model'
    _description = 'Booking for Healthcare/Services'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'appointment_time desc'
    
    name = fields.Char('Booking Reference', required=True, 
                      default=lambda self: self.env['ir.sequence'].next_by_code('booking.model'))
    
    partner_id = fields.Many2one('res.partner', 'Patient/Customer', required=True)
    patient_category = fields.Selection([
        ('regular', 'Regular'),
        ('vip', 'VIP'),
        ('emergency', 'Emergency'),
    ], string='Patient Category', default='regular')
    
    appointment_time = fields.Datetime('Appointment Time', required=True)
    duration = fields.Float('Duration (hours)', default=1.0)
    
    service_type = fields.Selection([
        ('consultation', 'Consultation'),
        ('home_visit', 'Home Visit'),
        ('emergency', 'Emergency Service'),
    ], string='Service Type', required=True, default='consultation')
    
    service_ids = fields.Many2many('product.product', string='Services')
    
    distance = fields.Float('Distance (km)')
    is_holiday = fields.Boolean('Holiday Appointment', compute='_compute_is_holiday')
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('done', 'Completed'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', tracking=True)
    
    sale_order_ids = fields.One2many('sale.order', 'booking_id', string='Related Orders')
    
    @api.depends('appointment_time')
    def _compute_is_holiday(self):
        """Check if appointment is on a holiday"""
        for booking in self:
            if booking.appointment_time:
                # Simplified: consider weekends as holidays
                booking.is_holiday = booking.appointment_time.weekday() >= 5
            else:
                booking.is_holiday = False
    
    def action_create_quotation(self):
        """Create a quotation for this booking"""
        self.ensure_one()
        
        sale_order = self.env['sale.order'].create({
            'partner_id': self.partner_id.id,
            'booking_id': self.id,
            'date_order': fields.Datetime.now(),
        })
        
        for service in self.service_ids:
            self.env['sale.order.line'].create({
                'order_id': sale_order.id,
                'product_id': service.id,
                'product_uom_qty': 1.0,
            })
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Quotation',
            'res_model': 'sale.order',
            'res_id': sale_order.id,
            'view_mode': 'form',
            'target': 'current',
        }