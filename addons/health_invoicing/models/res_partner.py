# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class Partner(models.Model):
    _inherit = 'res.partner'
    
    # Smart Button Counts
    service_package_count = fields.Integer(
        'Package Count',
        compute='_compute_invoicing_counts',
        help='Number of service packages for this patient'
    )
    
    payment_transaction_count = fields.Integer(
        'Payment Count',
        compute='_compute_invoicing_counts',
        help='Number of payment transactions for this patient'
    )
    
    # Financial Summary Fields
    total_invoiced = fields.Monetary(
        'Total Invoiced',
        compute='_compute_financial_summary',
        currency_field='currency_id',
        help='Total amount invoiced to this patient'
    )
    
    total_paid = fields.Monetary(
        'Total Paid',
        compute='_compute_financial_summary',
        currency_field='currency_id',
        help='Total amount paid by this patient'
    )
    
    total_due = fields.Monetary(
        'Total Due',
        compute='_compute_financial_summary',
        currency_field='currency_id',
        help='Outstanding amount due from this patient'
    )
    
    # Package Summary Fields
    active_packages_count = fields.Integer(
        'Active Packages',
        compute='_compute_package_summary',
        help='Number of active service packages'
    )
    
    total_prepaid_value = fields.Monetary(
        'Total Prepaid Value',
        compute='_compute_package_summary',
        currency_field='currency_id',
        help='Total value of all prepaid packages'
    )
    
    remaining_prepaid_value = fields.Monetary(
        'Remaining Prepaid Value',
        compute='_compute_package_summary',
        currency_field='currency_id',
        help='Remaining value in prepaid packages'
    )
    
    # Recent Transactions
    recent_payment_ids = fields.One2many(
        'health.payment.transaction',
        'patient_id',
        string='Recent Payments',
        domain=[],
        help='Recent payment transactions for this patient'
    )
    
    # Active Package Details for Display
    active_service_packages = fields.One2many(
        'health.service.package',
        'patient_id',
        string='Active Service Packages',
        domain=[('state', '=', 'active')],
        help='Active service packages with visit tracking'
    )
    
# NOTE: Payment analytics fields will be added in Phase 4b after base module upgrades successfully
    # This ensures clean database column creation without ORM conflicts
    
    # Computed Methods
    @api.depends('is_patient')
    def _compute_invoicing_counts(self):
        for partner in self:
            if partner.is_patient:
                partner.service_package_count = self.env['health.service.package'].search_count([
                    ('patient_id', '=', partner.id)
                ])
                partner.payment_transaction_count = self.env['health.payment.transaction'].search_count([
                    ('patient_id', '=', partner.id)
                ])
            else:
                partner.service_package_count = 0
                partner.payment_transaction_count = 0
    
    @api.depends('is_patient')
    def _compute_financial_summary(self):
        for partner in self:
            if partner.is_patient:
                # Get invoices for this patient
                invoices = self.env['account.move'].search([
                    ('partner_id', '=', partner.id),
                    ('move_type', 'in', ['out_invoice', 'out_refund']),
                    ('state', '=', 'posted')
                ])
                
                partner.total_invoiced = sum(invoices.mapped('amount_total_signed'))
                partner.total_paid = sum(invoices.mapped('amount_total')) - sum(invoices.mapped('amount_residual'))
                partner.total_due = sum(invoices.mapped('amount_residual'))
            else:
                partner.total_invoiced = 0.0
                partner.total_paid = 0.0
                partner.total_due = 0.0
    
    @api.depends('is_patient')
    def _compute_package_summary(self):
        for partner in self:
            if partner.is_patient:
                packages = self.env['health.service.package'].search([
                    ('patient_id', '=', partner.id)
                ])
                
                active_packages = packages.filtered(lambda p: p.state == 'active')
                partner.active_packages_count = len(active_packages)
                partner.total_prepaid_value = sum(packages.mapped('package_price'))
                partner.remaining_prepaid_value = sum(active_packages.mapped(lambda p: p.remaining_services * p.price_per_service))
            else:
                partner.active_packages_count = 0
                partner.total_prepaid_value = 0.0
                partner.remaining_prepaid_value = 0.0
    
    # Action Methods for Smart Buttons
    def action_view_service_packages(self):
        """View service packages for this patient"""
        self.ensure_one()
        
        if not self.is_patient:
            raise UserError(_('Service packages are only available for patients.'))
        
        return {
            'name': _('Service Packages'),
            'type': 'ir.actions.act_window',
            'res_model': 'health.service.package',
            'domain': [('patient_id', '=', self.id)],
            'view_mode': 'list,form',
            'target': 'current',
            'context': {
                'default_patient_id': self.id,
                'create': True,
            }
        }
    
    def action_view_payment_transactions(self):
        """View payment transactions for this patient"""
        self.ensure_one()
        
        if not self.is_patient:
            raise UserError(_('Payment transactions are only available for patients.'))
        
        return {
            'name': _('Payment Transactions'),
            'type': 'ir.actions.act_window',
            'res_model': 'health.payment.transaction',
            'domain': [('patient_id', '=', self.id)],
            'view_mode': 'list,form',
            'target': 'current',
            'context': {
                'default_patient_id': self.id,
                'create': True,
            }
        }
    
    def action_view_outstanding_invoices(self):
        """View outstanding invoices for this patient"""
        self.ensure_one()
        
        return {
            'name': _('Outstanding Invoices'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'domain': [
                ('partner_id', '=', self.id),
                ('move_type', 'in', ['out_invoice', 'out_refund']),
                ('state', '=', 'posted'),
                ('amount_residual', '>', 0)
            ],
            'view_mode': 'list,form',
            'target': 'current',
        }
    
    # Action Methods for Invoice Creation
    def action_create_prepaid_package(self):
        """Launch prepaid package creation wizard"""
        self.ensure_one()
        
        if not self.is_patient:
            raise UserError(_('Prepaid packages can only be created for patients.'))
        
        return {
            'name': _('Create Prepaid Service Package'),
            'type': 'ir.actions.act_window',
            'res_model': 'health.prepaid.package.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_patient_id': self.id,
                'default_currency_id': self.env.company.currency_id.id,
            }
        }
    
    def action_create_standard_invoice(self):
        """Launch standard invoice creation"""
        self.ensure_one()
        
        if not self.is_patient:
            raise UserError(_('Invoices can only be created for patients.'))
        
        return {
            'name': _('Create Standard Invoice'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_partner_id': self.id,
                'default_move_type': 'out_invoice',
                'default_invoice_origin': f'Manual invoice for {self.name}',
            }
        }
    
    def action_collect_payment(self):
        """Launch payment collection wizard"""
        self.ensure_one()
        
        if not self.is_patient:
            raise UserError(_('Payment collection is only available for patients.'))
        
        if self.total_due <= 0:
            raise UserError(_('No outstanding amount to collect for this patient.'))
        
        return {
            'name': _('Collect Payment'),
            'type': 'ir.actions.act_window',
            'res_model': 'health.payment.collection.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_patient_id': self.id,
                'default_amount': self.total_due,
                'default_currency_id': self.env.company.currency_id.id,
            }
        }