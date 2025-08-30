# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import datetime, timedelta


class HealthcarePayment(models.Model):
    """
    Healthcare Payment extending standard Odoo account.payment functionality
    Inherits from account.payment to leverage all standard payment features
    
    FROM CLIENT REQUIREMENTS:
    - Insurance claim processing and tracking
    - Vietnamese payment method support  
    - Healthcare service payment categorization
    - Split billing between patient and insurance
    """
    _inherit = 'account.payment'

    # Healthcare payment categorization
    healthcare_payment_type = fields.Selection([
        ('patient_direct', 'Direct Patient Payment'),
        ('insurance_primary', 'Primary Insurance Payment'),
        ('insurance_secondary', 'Secondary Insurance Payment'),
        ('government_subsidy', 'Government Healthcare Subsidy'),
        ('corporate_account', 'Corporate Healthcare Account'),
        ('installment', 'Installment Payment'),
        ('deposit', 'Service Deposit'),
        ('refund', 'Service Refund'),
    ], string='Healthcare Payment Type', help='Type of healthcare payment')
    
    # Insurance processing
    insurance_claim_id = fields.Many2one(
        'health.insurance.claim',
        string='Insurance Claim',
        help='Insurance claim associated with this payment'
    )
    
    insurance_provider_id = fields.Many2one(
        'res.partner',
        string='Insurance Provider',
        domain=[('is_company', '=', True)],
        help='Insurance company making the payment'
    )
    
    insurance_policy_number = fields.Char(
        'Insurance Policy Number',
        help='Policy number for insurance claim'
    )
    
    insurance_approval_code = fields.Char(
        'Insurance Approval Code',
        help='Pre-authorization or approval code from insurance'
    )
    
    insurance_coverage_percentage = fields.Float(
        'Insurance Coverage %',
        help='Percentage of service covered by insurance'
    )
    
    patient_copay_amount = fields.Monetary(
        'Patient Co-pay Amount',
        help='Amount patient is responsible for'
    )
    
    # Vietnamese payment methods (FROM CLIENT REQUIREMENTS)
    vietnamese_payment_method = fields.Selection([
        ('cash_vnd', 'Cash (VND)'),
        ('bank_transfer', 'Bank Transfer'),
        ('credit_card', 'Credit Card'),
        ('debit_card', 'Debit Card'),
        ('momo', 'MoMo E-Wallet'),
        ('zalopay', 'ZaloPay'),
        ('vnpay', 'VNPay'),
        ('internet_banking', 'Internet Banking'),
        ('qr_code', 'QR Code Payment'),
        ('installment_card', 'Installment Credit Card'),
    ], string='Vietnamese Payment Method', help='Vietnamese-specific payment methods')
    
    # Payment processing status
    payment_processing_status = fields.Selection([
        ('pending', 'Pending Processing'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
        ('disputed', 'Disputed'),
    ], string='Processing Status', default='pending',
       help='Status of payment processing')
    
    # Vietnamese banking integration
    vietnamese_bank_code = fields.Char(
        'Vietnamese Bank Code',
        help='Bank code for Vietnamese banking system'
    )
    
    vietnamese_transaction_ref = fields.Char(
        'Vietnamese Transaction Reference',
        help='Transaction reference from Vietnamese payment gateway'
    )
    
    # Healthcare service details
    fieldservice_order_id = fields.Many2one(
        'health.fieldservice.order',
        string='Field Service Order',
        help='Field service order this payment is for'
    )
    
    appointment_id = fields.Many2one(
        'health.appointment',
        string='Appointment',
        help='Healthcare appointment this payment is for'
    )
    
    patient_id = fields.Many2one(
        'health.patient',
        string='Patient',
        help='Patient making or benefiting from this payment'
    )
    
    # Payment plan and installments
    is_installment_payment = fields.Boolean(
        'Is Installment Payment',
        help='This payment is part of an installment plan'
    )
    
    installment_plan_id = fields.Many2one(
        'health.payment.plan',
        string='Payment Plan',
        help='Payment plan this installment belongs to'
    )
    
    installment_number = fields.Integer(
        'Installment Number',
        help='Which installment this payment represents'
    )
    
    remaining_installments = fields.Integer(
        'Remaining Installments',
        compute='_compute_remaining_installments',
        help='Number of installments remaining in plan'
    )
    
    # Payment authorization and verification
    requires_authorization = fields.Boolean(
        'Requires Authorization',
        help='Payment requires additional authorization'
    )
    
    authorized_by = fields.Many2one(
        'res.users',
        string='Authorized By',
        help='User who authorized this payment'
    )
    
    authorization_date = fields.Datetime(
        'Authorization Date',
        help='Date and time payment was authorized'
    )
    
    # Vietnamese compliance fields
    vietnamese_receipt_number = fields.Char(
        'Vietnamese Receipt Number',
        help='Official receipt number for Vietnamese tax compliance'
    )
    
    vietnamese_tax_invoice_ref = fields.Char(
        'Vietnamese Tax Invoice Reference',
        help='Reference to related tax invoice'
    )
    
    # Healthcare integration fields
    health_transaction_id = fields.Many2one(
        'health.payment.transaction',
        string='Healthcare Transaction',
        help='Related healthcare payment transaction',
        copy=False
    )
    
    healthcare_payment_method = fields.Selection([
        ('cash', 'Cash'),
        ('bank_card', 'Bank/Card Transfer'),
        ('bank_transfer', 'Bank Transfer'),
        ('online_payment', 'Online Payment'),
    ], string='Healthcare Payment Method',
       help='Payment method as per healthcare workflow')
    
    fso_id = fields.Many2one(
        'health.fieldservice.order',
        string='Field Service Order (Invoicing.md)',
        help='FSO that generated this payment'
    )
    
    # Cash collection workflow (Invoicing.md Case 1)
    cash_held_by_staff = fields.Boolean(
        'Cash Held by Staff',
        help='Cash is held by healthcare staff until clinic visit'
    )
    
    om_receipt_required = fields.Boolean(
        'OM Receipt Required',
        help='Operations Manager must issue electronic receipt'
    )
    
    payment_proof_notes = fields.Text(
        'Payment Proof Notes',
        help='Notes about payment proof/photo taken'
    )
    
    # AR tracking (per Invoicing.md requirements)
    ar_cash_status = fields.Selection([
        ('ar_increase_logged', 'AR Increase Logged'),
        ('cash_received_by_om', 'Cash Received by OM'),
        ('cash_recorded', 'Cash Recorded in System'),
    ], string='AR Cash Status',
       help='Accounts receivable cash processing status per Invoicing.md')
    
    cash_recorded = fields.Boolean(
        'Cash Recorded',
        help='Cash has been recorded in accounting system'
    )
    
    ar_notes = fields.Text(
        'AR Notes',
        help='Accounts receivable processing notes'
    )

    @api.model
    def create(self, vals):
        """Override create to handle healthcare payment automation"""
        # Auto-link patient if FSO or appointment provided
        if vals.get('fieldservice_order_id') and not vals.get('patient_id'):
            fso = self.env['health.fieldservice.order'].browse(vals['fieldservice_order_id'])
            if fso.patient_id:
                vals['patient_id'] = fso.patient_id.id
        
        if vals.get('appointment_id') and not vals.get('patient_id'):
            appointment = self.env['health.appointment'].browse(vals['appointment_id'])
            if appointment.patient_id:
                vals['patient_id'] = appointment.patient_id.id
        
        # Generate Vietnamese receipt number
        if not vals.get('vietnamese_receipt_number'):
            vals['vietnamese_receipt_number'] = self._generate_vietnamese_receipt_number()
        
        payment = super().create(vals)
        
        # Process insurance claim if applicable
        if payment.insurance_claim_id:
            payment._process_insurance_claim()
        
        # Auto-link with healthcare transaction if reference matches
        if payment.ref and not payment.health_transaction_id:
            transaction = self.env['health.payment.transaction'].search([
                ('name', '=', payment.ref)
            ], limit=1)
            if transaction:
                payment.health_transaction_id = transaction.id
                transaction.payment_id = payment.id
        
        return payment

    def _generate_vietnamese_receipt_number(self):
        """Generate Vietnamese receipt number for compliance"""
        sequence = self.env['ir.sequence'].next_by_code('vietnamese.payment.receipt') or '0001'
        company_code = self.company_id.vat[-4:] if self.company_id.vat else 'COMP'
        date_part = fields.Date.today().strftime('%Y%m%d')
        return f"VN{company_code}{date_part}{sequence}"

    def _process_insurance_claim(self):
        """Process insurance claim associated with payment"""
        self.ensure_one()
        
        if not self.insurance_claim_id:
            return
        
        claim = self.insurance_claim_id
        
        # Update claim status based on payment
        if self.state == 'posted':
            claim.claim_status = 'paid'
            claim.payment_date = self.date
            claim.payment_amount = self.amount
        elif self.state == 'cancelled':
            claim.claim_status = 'payment_failed'

    @api.depends('installment_plan_id', 'installment_number')
    def _compute_remaining_installments(self):
        """Compute remaining installments in payment plan"""
        for payment in self:
            if payment.installment_plan_id and payment.installment_number:
                payment.remaining_installments = (
                    payment.installment_plan_id.total_installments - payment.installment_number
                )
            else:
                payment.remaining_installments = 0

    def action_authorize_payment(self):
        """Authorize high-value or special healthcare payments"""
        self.ensure_one()
        
        if not self.requires_authorization:
            raise UserError(_('This payment does not require authorization.'))
        
        self.write({
            'authorized_by': self.env.user.id,
            'authorization_date': fields.Datetime.now(),
        })
        
        # Process the payment after authorization
        if self.state == 'draft':
            self.action_post()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': _('Payment authorized and processed successfully.'),
                'type': 'success',
            }
        }

    def action_process_insurance_payment(self):
        """Process insurance payment with claim validation"""
        self.ensure_one()
        
        if not self.insurance_claim_id:
            raise UserError(_('No insurance claim associated with this payment.'))
        
        claim = self.insurance_claim_id
        
        # Validate insurance claim
        if claim.claim_status not in ('approved', 'partial_approved'):
            raise UserError(_('Insurance claim must be approved before processing payment.'))
        
        # Validate payment amount against approved amount
        if self.amount > claim.approved_amount:
            raise UserError(_('Payment amount cannot exceed approved claim amount.'))
        
        # Process the payment
        self.payment_processing_status = 'processing'
        
        # Mock insurance payment processing
        self._mock_insurance_payment_processing()
        
        self.payment_processing_status = 'completed'
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': _('Insurance payment processed successfully.'),
                'type': 'success',
            }
        }

    def _mock_insurance_payment_processing(self):
        """Mock insurance payment processing - replace with actual insurance API"""
        import time
        time.sleep(1)  # Simulate processing time
        
        # In production, this would integrate with:
        # - Vietnamese insurance company APIs
        # - Healthcare payment networks
        # - Government healthcare subsidy systems

    def action_split_payment(self):
        """Split payment between patient and insurance portions"""
        self.ensure_one()
        
        if not self.patient_copay_amount or not self.insurance_coverage_percentage:
            raise UserError(_('Patient co-pay amount and insurance coverage must be specified for payment split.'))
        
        total_amount = self.amount
        insurance_amount = total_amount * (self.insurance_coverage_percentage / 100)
        patient_amount = total_amount - insurance_amount
        
        # Validate split amounts
        if abs(patient_amount - self.patient_copay_amount) > 0.01:
            raise UserError(_('Patient co-pay amount does not match calculated amount.'))
        
        # Create separate payment records
        insurance_payment_vals = {
            'payment_type': self.payment_type,
            'partner_type': 'customer',
            'partner_id': self.insurance_provider_id.id,
            'amount': insurance_amount,
            'currency_id': self.currency_id.id,
            'date': self.date,
            'communication': f'Insurance portion of {self.communication}',
            'healthcare_payment_type': 'insurance_primary',
            'insurance_claim_id': self.insurance_claim_id.id,
            'patient_id': self.patient_id.id,
            'fieldservice_order_id': self.fieldservice_order_id.id,
            'appointment_id': self.appointment_id.id,
        }
        
        patient_payment_vals = {
            'payment_type': self.payment_type,
            'partner_type': 'customer', 
            'partner_id': self.partner_id.id,
            'amount': patient_amount,
            'currency_id': self.currency_id.id,
            'date': self.date,
            'communication': f'Patient portion of {self.communication}',
            'healthcare_payment_type': 'patient_direct',
            'patient_copay_amount': patient_amount,
            'patient_id': self.patient_id.id,
            'fieldservice_order_id': self.fieldservice_order_id.id,
            'appointment_id': self.appointment_id.id,
            'vietnamese_payment_method': self.vietnamese_payment_method,
        }
        
        insurance_payment = self.create(insurance_payment_vals)
        patient_payment = self.create(patient_payment_vals)
        
        # Cancel original payment
        self.action_cancel()
        
        return {
            'name': _('Split Payments'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.payment',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', [insurance_payment.id, patient_payment.id])],
            'context': {'search_default_group_by_healthcare_payment_type': 1},
        }

    def action_create_installment_plan(self):
        """Create installment payment plan"""
        self.ensure_one()
        
        return {
            'name': _('Create Payment Plan'),
            'type': 'ir.actions.act_window',
            'res_model': 'health.payment.plan',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_patient_id': self.patient_id.id,
                'default_total_amount': self.amount,
                'default_first_payment_id': self.id,
                'default_fieldservice_order_id': self.fieldservice_order_id.id,
                'default_appointment_id': self.appointment_id.id,
            }
        }


class HealthcarePaymentPlan(models.Model):
    """Healthcare payment installment plan management"""
    _name = 'health.payment.plan'
    _description = 'Healthcare Payment Plan'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(
        'Payment Plan Name',
        required=True,
        default=lambda self: _('New Payment Plan')
    )
    
    patient_id = fields.Many2one(
        'health.patient',
        string='Patient',
        required=True,
        help='Patient this payment plan is for'
    )
    
    total_amount = fields.Monetary(
        'Total Amount',
        required=True,
        help='Total amount to be paid through installments'
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id
    )
    
    total_installments = fields.Integer(
        'Total Installments',
        required=True,
        default=3,
        help='Number of installment payments'
    )
    
    installment_amount = fields.Monetary(
        'Installment Amount',
        compute='_compute_installment_amount',
        help='Amount per installment'
    )
    
    first_payment_date = fields.Date(
        'First Payment Date',
        required=True,
        default=fields.Date.today
    )
    
    payment_frequency = fields.Selection([
        ('weekly', 'Weekly'),
        ('biweekly', 'Bi-weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
    ], string='Payment Frequency', default='monthly', required=True)
    
    status = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)
    
    payment_ids = fields.One2many(
        'account.payment',
        'installment_plan_id',
        string='Payments',
        help='Payments made under this plan'
    )
    
    fieldservice_order_id = fields.Many2one(
        'health.fieldservice.order',
        string='Field Service Order',
        help='FSO this payment plan is for'
    )
    
    appointment_id = fields.Many2one(
        'health.appointment',
        string='Appointment',
        help='Appointment this payment plan is for'
    )
    
    @api.depends('total_amount', 'total_installments')
    def _compute_installment_amount(self):
        """Compute amount per installment"""
        for plan in self:
            if plan.total_installments:
                plan.installment_amount = plan.total_amount / plan.total_installments
            else:
                plan.installment_amount = 0.0

    def action_activate_plan(self):
        """Activate payment plan and create scheduled payments"""
        self.ensure_one()
        
        if self.status != 'draft':
            raise UserError(_('Only draft payment plans can be activated.'))
        
        # Create scheduled payments
        self._create_scheduled_payments()
        
        self.status = 'active'
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': _('Payment plan activated successfully.'),
                'type': 'success',
            }
        }

    def _create_scheduled_payments(self):
        """Create scheduled payment records for installment plan"""
        frequency_days = {
            'weekly': 7,
            'biweekly': 14,
            'monthly': 30,
            'quarterly': 90,
        }
        
        interval_days = frequency_days[self.payment_frequency]
        current_date = self.first_payment_date
        
        for installment_num in range(1, self.total_installments + 1):
            payment_vals = {
                'payment_type': 'inbound',
                'partner_type': 'customer',
                'partner_id': self.patient_id.partner_id.id,
                'amount': self.installment_amount,
                'currency_id': self.currency_id.id,
                'date': current_date,
                'communication': f'Installment {installment_num}/{self.total_installments} - {self.name}',
                'healthcare_payment_type': 'installment',
                'is_installment_payment': True,
                'installment_plan_id': self.id,
                'installment_number': installment_num,
                'patient_id': self.patient_id.id,
                'fieldservice_order_id': self.fieldservice_order_id.id,
                'appointment_id': self.appointment_id.id,
                'state': 'draft',  # Keep as draft until actual payment
            }
            
            self.env['account.payment'].create(payment_vals)
            current_date += timedelta(days=interval_days)