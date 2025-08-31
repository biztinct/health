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
    
    # Prepaid Package Integration (REPLACING health.prepaid.service model)
    package_id = fields.Many2one(
        'health.service.package',
        string='Service Package',
        domain="[('patient_id', '=', patient_id), ('state', '=', 'active'), ('remaining_services', '>', 0)]",
        help='Prepaid service package to consume from (if any)'
    )
    
    is_package_service = fields.Boolean(
        'Package Service',
        compute='_compute_is_package_service',
        store=True,
        help='True if this FSO consumes from a prepaid package'
    )
    
    package_consumption_quantity = fields.Integer(
        'Services Consumed',
        default=1,
        help='Number of services consumed from the package (default: 1)'
    )
    
    package_service_value = fields.Monetary(
        'Package Service Value',
        currency_field='currency_id',
        compute='_compute_package_service_value',
        store=True,
        help='Value of services consumed from package'
    )
    
    # Legacy field for backward compatibility (will be removed)
    prepaid_consumption_ids = fields.One2many(
        'health.prepaid.service',
        'fso_id',
        string='Prepaid Consumptions (DEPRECATED)',
        help='Legacy prepaid service consumptions - use package_id instead'
    )
    
    @api.depends('package_id')
    def _compute_is_package_service(self):
        for fso in self:
            fso.is_package_service = bool(fso.package_id)
    
    @api.depends('package_id', 'package_consumption_quantity')
    def _compute_package_service_value(self):
        for fso in self:
            if fso.package_id and fso.package_consumption_quantity:
                fso.package_service_value = fso.package_id.price_per_service * fso.package_consumption_quantity
            else:
                fso.package_service_value = 0.0
    
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
    
    # Package Service Consumption Methods
    def action_consume_package_service(self):
        """Consume services from package when FSO is completed"""
        self.ensure_one()
        
        if not self.package_id:
            return False
        
        if self.package_consumption_quantity <= 0:
            return False
        
        if self.package_id.remaining_services < self.package_consumption_quantity:
            raise UserError(_(
                'Cannot consume %d services from package "%s". Only %d services remaining.'
            ) % (self.package_consumption_quantity, self.package_id.name, self.package_id.remaining_services))
        
        # Consume services from package (direct consumption without separate model)
        self.package_id.consumed_services += self.package_consumption_quantity
        
        # Check if package is exhausted
        if self.package_id.remaining_services == 0:
            self.package_id.state = 'exhausted'
            self.package_id.message_post(
                body=f"Package exhausted by FSO {self.name} - all {self.package_id.total_services} services consumed.",
                subject="Package Services Exhausted"
            )
        else:
            self.package_id.message_post(
                body=f"FSO {self.name} consumed {self.package_consumption_quantity} service(s). "
                     f"{self.package_id.remaining_services} services remaining.",
                subject="Package Service Consumed"
            )
        
        # Record consumption in FSO message
        self.message_post(
            body=f"Consumed {self.package_consumption_quantity} service(s) from package '{self.package_id.name}'. "
                 f"Service value: {self.package_service_value:,.0f} {self.currency_id.symbol}",
            subject="Package Service Consumed"
        )
        
        return True
    
    @api.onchange('package_id')
    def _onchange_package_id(self):
        """Auto-fill service details when package is selected"""
        if self.package_id:
            # Auto-set service type if it matches
            if self.package_id.service_type in dict(self._fields.get('service_type', fields.Selection([])).selection):
                self.service_type = self.package_id.service_type
    
    def write(self, vals):
        """Override write to consume package services when FSO stage changes"""
        result = super().write(vals)
        
        # Auto-consume package services when FSO is completed
        if 'stage' in vals and vals['stage'] in ['completed', 'done']:
            for fso in self:
                if fso.package_id and not fso.is_invoiced:
                    fso.action_consume_package_service()
        
        return result