# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class HealthPaymentTransaction(models.Model):
    """
    Enhanced Payment Transaction Tracking
    
    Tracks all payment transactions with detailed information:
    - Nurse payment collection (Pay Now/Pay Later)
    - Payment methods with photo proof
    - Cash handling workflow (nurse → OM)
    - Payment status and reconciliation
    """
    _name = 'health.payment.transaction'
    _description = 'Healthcare Payment Transaction'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'transaction_date desc'
    _rec_name = 'display_name'

    # Archive support — set active=False to hide records from all views
    active = fields.Boolean(default=True)

    # Core Transaction Information
    name = fields.Char(
        'Transaction Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New Transaction'),
        help='Unique transaction reference number'
    )
    
    display_name = fields.Char(
        'Display Name',
        compute='_compute_display_name',
        store=True
    )
    
    @api.depends('name', 'patient_id', 'amount', 'payment_method')
    def _compute_display_name(self):
        for transaction in self:
            if transaction.patient_id and transaction.amount:
                method_label = dict(transaction._fields['payment_method'].selection).get(transaction.payment_method, '')
                transaction.display_name = f"{transaction.patient_id.name} - {transaction.amount:,.0f} VND ({method_label})"
            else:
                transaction.display_name = transaction.name
    
    # Patient and Service Links
    patient_id = fields.Many2one(
        'res.partner',
        string='Client',
        required=True,
        domain="[('is_patient', '=', True)]",
        tracking=True,
        help='client who made the payment'
    )
    patient_phone = fields.Char('Phone', related='patient_id.phone', readonly=True)
    
    fso_id = fields.Many2one(
        'health.fieldservice.order',
        string='Booking',
        help='FSO associated with this payment'
    )
    
    invoice_id = fields.Many2one(
        'account.move',
        string='Invoice',
        help='Invoice associated with this payment'
    )
    
    package_id = fields.Many2one(
        'health.service.package',
        string='Service Package',
        help='Service package if this is a prepaid payment'
    )
    
    # Payment Details
    amount = fields.Monetary(
        'Payment Amount',
        currency_field='currency_id',
        required=True,
        tracking=True,
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
        ('prepaid', 'Prepaid Service'),
        ('other', 'Other'),
    ], string='Payment Method', required=True, tracking=True,
       help='Method used for payment')
    
    # Transaction Timing
    transaction_date = fields.Datetime(
        'Transaction Date',
        default=fields.Datetime.now,
        required=True,
        tracking=True,
        help='Date and time when payment was collected'
    )
    
    # Transaction Status and Workflow
    transaction_type = fields.Selection([
        ('immediate', 'Pay Now - Immediate'),
        ('deferred', 'Pay Later - Deferred'),
        ('prepaid', 'Prepaid Service'),
        ('refund', 'Refund'),
    ], string='Transaction Type', required=True, tracking=True,
       help='Type of payment transaction')
    
    status = fields.Selection([
        ('collected', 'Payment Collected'),
        ('pending_delivery', 'Cash Pending Delivery'),
        ('delivered_to_om', 'Cash Delivered to OM'),
        ('reconciled', 'Reconciled in AR'),
        ('failed', 'Payment Failed'),
        ('refunded', 'Refunded'),
    ], string='Payment Status', default='collected', tracking=True,
       help='Current status of this payment')
    
    # Staff Information
    collected_by_id = fields.Many2one(
        'hr.employee',
        string='Collected By',
        domain="[('is_healthcare_staff', '=', True)]",
        compute='_compute_collected_by',
        store=True,
        readonly=False,
        tracking=True,
        help='Healthcare staff who collected this payment'
    )
    
    received_by_om_id = fields.Many2one(
        'hr.employee',
        string='Received by OM',
        domain="[('is_healthcare_staff', '=', True)]",
        tracking=True,
        help='Operations Manager who received cash payment'
    )
    
    def _get_current_employee(self):
        """Get current user's employee record if they are healthcare staff"""
        employee = self.env['hr.employee'].search([
            ('user_id', '=', self.env.user.id),
            ('is_healthcare_staff', '=', True)
        ], limit=1)
        return employee.id if employee else False

    @api.depends('received_by_om_id')
    def _compute_collected_by(self):
        for rec in self:
            if rec.received_by_om_id and not rec.collected_by_id:
                rec.collected_by_id = rec.received_by_om_id
            elif not rec.collected_by_id:
                # Fall back to current user's employee
                rec.collected_by_id = rec._get_current_employee()
    
    # Payment Proof and Documentation
    payment_proof_attachment_ids = fields.Many2many(
        'ir.attachment',
        'payment_transaction_attachment_rel',
        'transaction_id',
        'attachment_id',
        string='Payment Proof',
        help='Photos or documents proving payment (e.g., bank transfer screenshots)'
    )
    
    proof_count = fields.Integer(
        'Proof Documents',
        compute='_compute_proof_count',
        help='Number of proof documents attached'
    )
    
    @api.depends('payment_proof_attachment_ids')
    def _compute_proof_count(self):
        for transaction in self:
            transaction.proof_count = len(transaction.payment_proof_attachment_ids)
    
    # Notes and Additional Information
    transaction_notes = fields.Text(
        'Transaction Notes',
        help='Additional notes about this payment transaction'
    )
    
    nurse_override_reason = fields.Text(
        'Nurse Override Reason',
        help='Reason provided by nurse if payment amount was overridden'
    )
    
    original_invoice_amount = fields.Monetary(
        'Original Invoice Amount',
        currency_field='currency_id',
        help='Original invoice amount before any nurse override'
    )
    
    # Cash Delivery Workflow
    cash_delivery_date = fields.Datetime(
        'Cash Delivered Date',
        tracking=True,
        help='Date when cash was delivered to Operations Manager'
    )
    
    om_receipt_number = fields.Char(
        'OM Receipt Number',
        help='Electronic receipt number issued by OM upon cash receipt'
    )
    
    # Standard Odoo AR Integration
    payment_id = fields.Many2one(
        'account.payment',
        string='AR Payment Record',
        help='Standard Odoo payment record for AR integration',
        copy=False,
        tracking=True
    )
    
    cit_move_id = fields.Many2one(
        'account.move',
        string='CIT Journal Entry',
        help='Cash in Transit journal entry (Debit CIT, Credit AR) created when nurse collects cash',
        copy=False,
    )
    
    ar_reconciled = fields.Boolean(
        'AR Reconciled',
        related='payment_id.is_reconciled',
        store=True,
        help='Whether this payment has been reconciled in Accounts Receivable'
    )
    
    ar_reconciliation_date = fields.Datetime(
        'AR Reconciliation Date',
        help='Date when payment was reconciled in AR system'
    )
    
    # Create sequence for transaction reference
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New Transaction')) == _('New Transaction'):
                vals['name'] = self.env['ir.sequence'].next_by_code('health.payment.transaction') or _('New Transaction')
        return super().create(vals_list)
    
    # Constraints and Validations
    @api.constrains('amount')
    def _check_amount(self):
        for transaction in self:
            if transaction.amount <= 0:
                raise ValidationError(_('Payment amount must be positive.'))
    
    @api.constrains('transaction_date', 'cash_delivery_date')
    def _check_dates(self):
        for transaction in self:
            if transaction.cash_delivery_date and transaction.transaction_date:
                if transaction.cash_delivery_date < transaction.transaction_date:
                    raise ValidationError(_('Cash delivery date cannot be before transaction date.'))
    
    # Business Logic Methods
    def action_mark_cash_delivered(self):
        """Mark cash payment as delivered to OM"""
        self.ensure_one()
        
        if self.payment_method != 'cash':
            raise UserError(_('Only cash payments need delivery confirmation.'))
        
        if self.status != 'pending_delivery':
            raise UserError(_('Payment is not pending delivery.'))
        
        # Launch delivery confirmation wizard
        return {
            'name': _('Confirm Cash Delivery'),
            'type': 'ir.actions.act_window',
            'res_model': 'health.cash.delivery.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_transaction_id': self.id}
        }
    
    def action_create_ar_payment(self):
        """Create standard Odoo payment record for AR integration"""
        self.ensure_one()
        
        if self.payment_id:
            raise UserError(_('AR payment record already exists.'))
        
        if self.transaction_type == 'prepaid':
            raise UserError(_('Prepaid consumption does not create separate AR payment.'))
        
        # Use standard payment registration wizard for proper AR integration
        return {
            'name': _('Register Payment'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.payment.register',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_model': 'account.move',
                'active_ids': [self.invoice_id.id] if self.invoice_id else [],
                'default_amount': abs(self.amount),
                'default_partner_id': self.patient_id.id,
            }
        }
    
    def action_view_proof_documents(self):
        """View attached proof documents"""
        self.ensure_one()
        return {
            'name': _('Payment Proof Documents'),
            'type': 'ir.actions.act_window',
            'res_model': 'ir.attachment',
            'domain': [('id', 'in', self.payment_proof_attachment_ids.ids)],
            'view_mode': 'kanban,list,form',
            'target': 'current',
        }
    
    def action_view_invoice(self):
        """Open the related invoice in form view"""
        self.ensure_one()

        if not self.invoice_id:
            raise UserError(_('No invoice is associated with this payment transaction.'))

        return {
            'name': _('Invoice'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.invoice_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_payment(self):
        """Open the related AR payment in form view"""
        self.ensure_one()

        if not self.payment_id:
            raise UserError(_('No AR payment record is associated with this transaction.'))

        return {
            'name': _('AR Payment'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.payment',
            'res_id': self.payment_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_create_refund(self):
        """Create refund transaction"""
        self.ensure_one()

        if self.status == 'refunded':
            raise UserError(_('Payment is already refunded.'))

        # Create refund transaction
        refund = self.create({
            'patient_id': self.patient_id.id,
            'fso_id': self.fso_id.id if self.fso_id else False,
            'invoice_id': self.invoice_id.id if self.invoice_id else False,
            'package_id': self.package_id.id if self.package_id else False,
            'amount': -self.amount,  # Negative amount for refund
            'payment_method': self.payment_method,
            'transaction_type': 'refund',
            'status': 'collected',
            'collected_by_id': self.env.user.employee_id.id,
            'transaction_notes': f'Refund for transaction {self.name}',
        })

        # Update original transaction status
        self.status = 'refunded'

        return {
            'name': _('Refund Transaction'),
            'type': 'ir.actions.act_window',
            'res_model': 'health.payment.transaction',
            'res_id': refund.id,
            'view_mode': 'form',
            'target': 'current',
        }