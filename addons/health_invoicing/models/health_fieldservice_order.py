# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class HealthFieldserviceOrder(models.Model):
    _inherit = 'health.fieldservice.order'
    
    # Enhanced Invoice Integration
    invoice_id = fields.Many2one(
        'account.move',
        string='Invoice',
        help='Invoice generated for this service order',
        copy=False
    )
    
    is_invoiced = fields.Boolean(
        'Invoiced',
        default=False,
        help='Whether this FSO has been invoiced'
    )
    
    payment_transaction_ids = fields.One2many(
        'health.payment.transaction',
        'fso_id',
        string='Payment Transactions',
        help='Payment transactions for this service order'
    )
    
    payment_transaction_count = fields.Integer(
        'Payment Count',
        compute='_compute_payment_count',
        help='Number of payment transactions'
    )
    
    total_paid_amount = fields.Monetary(
        'Total Paid',
        currency_field='currency_id',
        compute='_compute_payment_summary',
        help='Total amount paid for this service'
    )
    
    outstanding_amount = fields.Monetary(
        'Outstanding Amount',
        currency_field='currency_id',
        compute='_compute_payment_summary',
        help='Outstanding amount if invoice exists'
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id
    )
    
    # Prepaid Package Consumption
    prepaid_consumption_ids = fields.One2many(
        'health.prepaid.service',
        'fso_id',
        string='Prepaid Consumptions',
        help='Prepaid services consumed for this FSO'
    )
    
    @api.depends('payment_transaction_ids')
    def _compute_payment_count(self):
        for fso in self:
            fso.payment_transaction_count = len(fso.payment_transaction_ids)
    
    @api.depends('invoice_id', 'payment_transaction_ids')
    def _compute_payment_summary(self):
        for fso in self:
            fso.total_paid_amount = sum(fso.payment_transaction_ids.mapped('amount'))
            
            if fso.invoice_id:
                fso.outstanding_amount = fso.invoice_id.amount_residual
            else:
                fso.outstanding_amount = 0.0
    
    # Enhanced FSO Completion Workflow
    def action_complete_service_with_payment(self):
        """Complete service and launch payment collection workflow"""
        self.ensure_one()
        
        if self.stage != 'in_progress':
            raise UserError(_('Only services in progress can be completed.'))
        
        if self.is_invoiced:
            raise UserError(_('This service has already been invoiced.'))
        
        # Launch nurse payment collection wizard
        return {
            'name': _('Complete Service - Payment Collection'),
            'type': 'ir.actions.act_window',
            'res_model': 'health.nurse.payment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_fso_id': self.id,
                'default_patient_id': self.patient_id.id,
            }
        }
    
    def action_view_payment_transactions(self):
        """View payment transactions for this FSO"""
        self.ensure_one()
        
        return {
            'name': _('Payment Transactions'),
            'type': 'ir.actions.act_window',
            'res_model': 'health.payment.transaction',
            'domain': [('fso_id', '=', self.id)],
            'view_mode': 'list,form',
            'target': 'current',
            'context': {
                'default_fso_id': self.id,
                'default_patient_id': self.patient_id.id,
            }
        }
    
    def action_view_invoice(self):
        """View invoice for this FSO"""
        self.ensure_one()
        
        if not self.invoice_id:
            raise UserError(_('No invoice has been created for this service order.'))
        
        return {
            'name': _('Service Invoice'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.invoice_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def action_create_manual_invoice(self):
        """Create invoice manually (alternative to nurse workflow)"""
        self.ensure_one()
        
        if self.is_invoiced:
            raise UserError(_('This service has already been invoiced.'))
        
        # Calculate service amount
        amount = 0.0
        if self.service_type_id:
            amount += self.service_type_id.base_price or 0.0
        
        if self.duration_hours and self.service_type_id.hourly_rate:
            amount += self.duration_hours * self.service_type_id.hourly_rate
        
        # Create invoice
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.patient_id.id,
            'invoice_origin': f'FSO: {self.name}',
            'invoice_line_ids': [(0, 0, {
                'name': f'{self.service_type_id.name or "Healthcare Service"} - {self.name}',
                'quantity': 1,
                'price_unit': amount,
                'product_uom_id': self.env.ref('uom.product_uom_unit').id,
            })],
        })
        
        # Link invoice to FSO
        self.write({
            'invoice_id': invoice.id,
            'is_invoiced': True,
        })
        
        return {
            'name': _('Service Invoice'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': invoice.id,
            'view_mode': 'form',
            'target': 'current',
        }