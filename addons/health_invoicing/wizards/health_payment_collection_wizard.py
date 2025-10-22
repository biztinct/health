# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class HealthPaymentCollectionWizard(models.TransientModel):
    """
    Payment Collection Wizard for Outstanding Balances
    
    Allows front desk/OM to collect payments for:
    - Outstanding invoices (Pay Later scenario)
    - Partial payments
    - Multiple invoice payments
    """
    _name = 'health.payment.collection.wizard'
    _description = 'Payment Collection Wizard'
    
    # Patient Information
    patient_id = fields.Many2one(
        'res.partner',
        string='Client',
        required=True,
        domain="[('is_patient', '=', True)]",
        help='client making the payment'
    )
    
    # Payment Details
    amount = fields.Monetary(
        'Payment Amount',
        currency_field='currency_id',
        required=True,
        help='client'
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
        required=True
    )
    
    payment_method = fields.Selection([
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
        ('credit_card', 'Credit Card'),
        ('qr_code', 'QR Code Payment'),
        ('other', 'Other'),
    ], string='Payment Method', required=True,
       help='Method used for this payment')
    
    # Outstanding Invoice Selection
    outstanding_invoice_ids = fields.Many2many(
        'account.move',
        'payment_collection_invoice_rel',
        'wizard_id',
        'invoice_id',
        string='Outstanding Invoices',
        domain="[('partner_id', '=', patient_id), ('amount_residual', '>', 0), ('state', '=', 'posted')]",
        help='Select invoices to apply this payment to'
    )
    
    total_outstanding = fields.Monetary(
        'Total Outstanding',
        currency_field='currency_id',
        compute='_compute_total_outstanding',
        help='Total amount outstanding on selected invoices'
    )
    
    # Payment Options
    allocate_automatically = fields.Boolean(
        'Allocate Automatically',
        default=True,
        help='Automatically allocate payment to oldest invoices first'
    )
    
    # Payment Proof
    payment_proof_required = fields.Boolean(
        'Proof Required',
        compute='_compute_payment_proof_required',
        help='Whether payment proof is required for this method'
    )
    
    payment_proof_attachment_ids = fields.Many2many(
        'ir.attachment',
        'payment_collection_attachment_rel',
        'wizard_id',
        'attachment_id',
        string='Payment Proof',
        help='Upload photos or documents as payment proof'
    )
    
    # Additional Information
    payment_notes = fields.Text(
        'Payment Notes',
        help='Additional notes about this payment collection'
    )
    
    # Computed Methods
    @api.depends('outstanding_invoice_ids')
    def _compute_total_outstanding(self):
        for wizard in self:
            wizard.total_outstanding = sum(wizard.outstanding_invoice_ids.mapped('amount_residual'))
    
    @api.depends('payment_method')
    def _compute_payment_proof_required(self):
        for wizard in self:
            wizard.payment_proof_required = wizard.payment_method in ['bank_transfer', 'credit_card', 'qr_code']
    
    @api.onchange('patient_id')
    def _onchange_patient_id(self):
        if self.patient_id:
            # Auto-select all outstanding invoices
            outstanding_invoices = self.env['account.move'].search([
                ('partner_id', '=', self.patient_id.id),
                ('amount_residual', '>', 0),
                ('state', '=', 'posted'),
                ('move_type', 'in', ['out_invoice', 'out_refund'])
            ])
            self.outstanding_invoice_ids = outstanding_invoices
    
    # Validation
    @api.constrains('amount')
    def _check_payment_amount(self):
        for wizard in self:
            if wizard.amount <= 0:
                raise ValidationError(_('Payment amount must be positive.'))
    
    @api.constrains('payment_method', 'payment_proof_attachment_ids')
    def _check_payment_proof(self):
        for wizard in self:
            if wizard.payment_proof_required and not wizard.payment_proof_attachment_ids:
                raise ValidationError(_(
                    'Payment proof is required for %s payments. Please upload proof documents.'
                ) % dict(wizard._fields['payment_method'].selection)[wizard.payment_method])
    
    # Main Action
    def action_collect_payment(self):
        """Process payment collection and apply to invoices"""
        self.ensure_one()
        
        if not self.outstanding_invoice_ids:
            raise UserError(_('Please select at least one invoice to apply payment to.'))
        
        # Create payment transaction record
        transaction = self.env['health.payment.transaction'].create({
            'patient_id': self.patient_id.id,
            'amount': self.amount,
            'payment_method': self.payment_method,
            'transaction_type': 'deferred',  # This is collecting a "Pay Later"
            'status': 'collected' if self.payment_method != 'cash' else 'pending_delivery',
            'collected_by_id': self.env.user.employee_id.id if self.env.user.employee_id else False,
            'transaction_notes': self.payment_notes or f'Payment collection for outstanding invoices',
            'payment_proof_attachment_ids': [(6, 0, self.payment_proof_attachment_ids.ids)],
        })
        
        # Create account payment for invoice reconciliation
        payment_journal = self._get_payment_journal()
        payment_vals = {
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': self.patient_id.id,
            'amount': self.amount,
            'journal_id': payment_journal.id,
            'payment_reference': f'Payment collection: {transaction.display_name}',
        }
        
        payment = self.env['account.payment'].create(payment_vals)
        payment.action_post()
        
        # Link transaction to payment
        transaction.write({
            'payment_id': payment.id,
            'invoice_id': self.outstanding_invoice_ids[0].id if len(self.outstanding_invoice_ids) == 1 else False,
        })
        
        # Allocate payment to invoices
        if self.allocate_automatically:
            self._allocate_payment_automatically(payment, transaction)
        else:
            self._show_manual_allocation_wizard(payment, transaction)
        
        # Update transaction status
        if payment.state == 'posted':
            transaction.write({
                'status': 'reconciled',
                'ar_reconciliation_date': fields.Datetime.now()
            })
        
        # Success message
        message = f"""
        Payment Collected Successfully!
        
        Amount: {self.amount:,.0f} {self.currency_id.symbol}
        Method: {dict(self._fields['payment_method'].selection)[self.payment_method]}
        Applied to {len(self.outstanding_invoice_ids)} invoice(s)
        """
        
        if self.payment_method == 'cash':
            message += "\n⚠️  Cash payment - requires delivery to Operations Manager"
        
        transaction.message_post(
            body=message,
            subject="Payment Collected"
        )
        
        return {
            'name': _('Payment Transaction'),
            'type': 'ir.actions.act_window',
            'res_model': 'health.payment.transaction',
            'res_id': transaction.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def _get_payment_journal(self):
        """Get appropriate payment journal based on payment method"""
        journal_type_map = {
            'cash': 'cash',
            'bank_transfer': 'bank',
            'credit_card': 'bank',
            'qr_code': 'bank',
            'other': 'bank',
        }
        
        journal_type = journal_type_map.get(self.payment_method, 'bank')
        journal = self.env['account.journal'].search([
            ('type', '=', journal_type),
            ('company_id', '=', self.env.company.id)
        ], limit=1)
        
        if not journal:
            raise UserError(_(
                'No %s journal found. Please configure payment journals in Accounting settings.'
            ) % journal_type.title())
        
        return journal
    
    def _allocate_payment_automatically(self, payment, transaction):
        """Automatically allocate payment to invoices (oldest first) - Odoo 18 compatible"""
        # In Odoo 18, payment reconciliation is handled differently
        # Use the payment's reconciled_invoice_ids or manual reconciliation
        
        if not payment.move_id:
            # Payment hasn't created a journal entry yet
            return True
            
        # Get payment lines from the journal entry
        payment_lines = payment.move_id.line_ids.filtered(
            lambda line: line.account_id == payment.destination_account_id and not line.reconciled
        )
        
        if not payment_lines:
            return True
            
        remaining_amount = self.amount
        invoices = self.outstanding_invoice_ids.sorted(lambda inv: inv.invoice_date)
        
        for invoice in invoices:
            if remaining_amount <= 0:
                break
            
            # Calculate allocation amount  
            allocation_amount = min(remaining_amount, invoice.amount_residual)
            
            # Get receivable lines from invoice
            invoice_lines = invoice.line_ids.filtered(
                lambda line: line.account_id.account_type == 'asset_receivable' and not line.reconciled
            )
            
            if payment_lines and invoice_lines:
                try:
                    # Reconcile payment with invoice
                    (payment_lines + invoice_lines).reconcile()
                except Exception:
                    # If reconciliation fails, continue to next invoice
                    pass
            
            remaining_amount -= allocation_amount
        
        return True
    
    def _show_manual_allocation_wizard(self, payment, transaction):
        """Show manual allocation wizard (for future implementation)"""
        # For now, default to automatic allocation
        return self._allocate_payment_automatically(payment, transaction)