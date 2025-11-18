# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class HealthPaymentWorkflowWizard(models.TransientModel):
    """
    Payment Workflow Wizard implementing Invoicing.md Cases 1-3
    
    INVOICING.MD WORKFLOW:
    Case 1: Payment on Completion (Pay Now)
    Case 2: Prepaid Services 
    Case 3: Payment After Service (Pay Later)
    """
    _name = 'health.payment.workflow.wizard'
    _description = 'Healthcare Payment Workflow Wizard'
    
    # Source records
    fso_id = fields.Many2one(
        'health.fieldservice.order',
        string='Booking',
        required=True
    )
    
    invoice_id = fields.Many2one(
        'account.move',
        string='Invoice',
        required=True
    )

    # Display information
    patient_name = fields.Char(
        'Patient Name',
        related='fso_id.patient_id.name',
        readonly=True
    )

    @api.model
    def default_get(self, fields_list):
        """Override default_get to auto-populate FSO from invoice"""
        res = super(HealthPaymentWorkflowWizard, self).default_get(fields_list)

        _logger.info("=== Payment Workflow Wizard - default_get ===")
        _logger.info(f"Context: {self.env.context}")
        _logger.info(f"Default values from context: {res}")

        # If invoice_id is provided in context but fso_id is not, get it from invoice
        if 'invoice_id' in res and res.get('invoice_id'):
            if 'fso_id' not in res or not res.get('fso_id'):
                invoice = self.env['account.move'].browse(res['invoice_id'])
                _logger.info(f"Invoice ID: {invoice.id}, Invoice Name: {invoice.name}")
                _logger.info(f"Invoice fieldservice_order_id: {invoice.fieldservice_order_id}")
                _logger.info(f"Invoice fieldservice_order_id.id: {invoice.fieldservice_order_id.id if invoice.fieldservice_order_id else 'None'}")

                if invoice and invoice.fieldservice_order_id:
                    res['fso_id'] = invoice.fieldservice_order_id.id
                    _logger.info(f"✅ Set fso_id to: {res['fso_id']}")
                else:
                    _logger.warning(f"⚠️ Invoice {invoice.name} has NO fieldservice_order_id!")

        _logger.info(f"Final default values: {res}")
        return res

    @api.onchange('invoice_id')
    def _onchange_invoice_id(self):
        """Auto-populate FSO from invoice's fieldservice_order_id"""
        if self.invoice_id and self.invoice_id.fieldservice_order_id:
            self.fso_id = self.invoice_id.fieldservice_order_id

    service_type = fields.Selection([
        ('home_visit', 'Home Visit'),
        ('clinic_visit', 'Clinic Visit'),
        ('consultation', 'Consultation'),
        ('emergency', 'Emergency Care'),
        ('follow_up', 'Follow-up Care'),
        ('preventive', 'Preventive Care'),
        ('rehabilitation', 'Rehabilitation'),
        ('telemedicine', 'Telemedicine/Online'),
        ('vaccination', 'Vaccination'),
        ('diagnostic', 'Diagnostic Services'),
    ], string='Service Type', related='fso_id.service_type', readonly=True)
    
    amount_total = fields.Monetary(
        'Total Amount',
        related='invoice_id.amount_total',
        readonly=True
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        related='invoice_id.currency_id',
        readonly=True
    )
    
    # Payment workflow selection (Invoicing.md Cases)
    payment_workflow = fields.Selection([
        ('pay_now', 'Pay Now - Payment on Completion (Case 1)'),
        ('pay_later', 'Pay Later - Payment After Service (Case 3)'),
        # ('prepaid', 'Prepaid Service (Case 2)'), # Handled separately
    ], string='Payment Workflow', required=True, default='pay_now',
       help='Select payment workflow as per Invoicing.md requirements')
    
    # Pay Now fields (Case 1)
    payment_method = fields.Selection([
        ('cash', 'Cash'),
        ('bank_card', 'Bank/Card Transfer'),
        ('bank_transfer', 'Bank Transfer'),
        ('online_payment', 'Online Payment'),
    ], string='Payment Method',
       help='Method of payment for immediate payment')
    
    payment_amount = fields.Monetary(
        'Payment Amount',
        help='Actual payment amount received'
    )
    
    adjustment_reason = fields.Text(
        'Invoice Adjustment Reason',
        help='Reason for any adjustments made to the invoice'
    )
    
    # Cash handling (per Invoicing.md Case 1)
    cash_held_by_nurse = fields.Boolean(
        'Cash Held by Nurse',
        help='Cash is held by nurse until next clinic visit (per Invoicing.md)'
    )
    
    nurse_receipt_required = fields.Boolean(
        'OM Receipt Required',
        help='Operations Manager must issue electronic receipt upon cash receipt'
    )
    
    # Proof of payment
    payment_proof_required = fields.Boolean(
        'Payment Proof Required',
        help='Photo proof required for bank/card payments'
    )
    
    payment_proof_notes = fields.Text(
        'Payment Proof Notes',
        help='Notes about payment proof/photo taken'
    )
    
    # Pay Later fields (Case 3)
    payment_terms = fields.Many2one(
        'account.payment.term',
        string='Payment Terms',
        help='Payment terms for pay later option'
    )
    
    due_date = fields.Date(
        'Payment Due Date',
        help='Date when payment is due'
    )
    
    # Vietnamese compliance
    tax_submission_required = fields.Boolean(
        'Tax Submission Required',
        default=True,
        help='Invoice must be submitted to Vietnamese Tax Authorities'
    )
    
    offline_submission = fields.Boolean(
        'Offline Submission',
        help='Submission will be done offline due to connectivity issues'
    )
    
    # Audit trail (per Invoicing.md requirements)
    actual_completion_time = fields.Datetime(
        'Actual Completion Time',
        help='Actual time when service was completed'
    )
    
    adjusted_submission_time = fields.Datetime(
        'Adjusted Submission Time', 
        help='Time when invoice will be submitted to Tax Department'
    )
    
    @api.onchange('payment_workflow')
    def _onchange_payment_workflow(self):
        """Set defaults based on payment workflow selection"""
        if self.payment_workflow == 'pay_now':
            self.payment_amount = self.amount_total
            self.payment_method = 'cash'
            self.cash_held_by_nurse = True
            self.nurse_receipt_required = True
        elif self.payment_workflow == 'pay_later':
            self.payment_amount = 0.0
            self.payment_method = False
            self.due_date = fields.Date.add(fields.Date.today(), days=30)
    
    @api.onchange('payment_method')
    def _onchange_payment_method(self):
        """Set requirements based on payment method"""
        if self.payment_method in ('bank_card', 'bank_transfer', 'online_payment'):
            self.payment_proof_required = True
            self.cash_held_by_nurse = False
            self.nurse_receipt_required = False
        elif self.payment_method == 'cash':
            self.payment_proof_required = False  
            self.cash_held_by_nurse = True
            self.nurse_receipt_required = True
    
    def action_process_payment_workflow(self):
        """Process the selected payment workflow (main action)"""
        self.ensure_one()
        
        if self.payment_workflow == 'pay_now':
            return self._process_pay_now_workflow()
        elif self.payment_workflow == 'pay_later':
            return self._process_pay_later_workflow()
        else:
            raise UserError(_('Invalid payment workflow selected.'))
    
    def _process_pay_now_workflow(self):
        """Process Case 1: Payment on Completion (Invoicing.md)"""
        self.ensure_one()
        
        # Validate payment details
        if not self.payment_method:
            raise UserError(_('Payment method is required for Pay Now workflow.'))
        
        if self.payment_amount <= 0:
            raise UserError(_('Payment amount must be greater than zero.'))
        
        # Apply any invoice adjustments (per Invoicing.md: "Nurse edits the invoice")
        if self.adjustment_reason and abs(self.payment_amount - self.amount_total) > 0.01:
            self._apply_invoice_adjustments()
        
        # Post the invoice first
        if self.invoice_id.state == 'draft':
            self.invoice_id.action_post()
        
        # Create payment record
        payment_vals = {
            'payment_type': 'inbound',
            'partner_type': 'customer', 
            'partner_id': self.invoice_id.partner_id.id,
            'amount': self.payment_amount,
            'currency_id': self.currency_id.id,
            'payment_date': fields.Date.today(),
            'ref': f'Payment - {self.invoice_id.name}',
            'journal_id': self._get_payment_journal().id,
            
            # Healthcare specific fields
            'healthcare_payment_method': self.payment_method,
            'fso_id': self.fso_id.id,
            'cash_held_by_staff': self.cash_held_by_nurse,
            'om_receipt_required': self.nurse_receipt_required,
            'payment_proof_notes': self.payment_proof_notes,
        }
        
        # Create and post payment
        payment = self.env['account.payment'].create(payment_vals)
        payment.action_post()
        
        # Reconcile with invoice
        self._reconcile_payment_with_invoice(payment)
        
        # Handle cash collection workflow (per Invoicing.md)
        if self.payment_method == 'cash':
            self._handle_cash_collection_workflow(payment)
        
        # Submit to Vietnamese Tax Authorities (per Invoicing.md)
        if self.tax_submission_required:
            self._submit_to_tax_authorities()
        
        # Update FSO status - Move to Complete stage for Cash payment
        completed_stage = self.env['health.fieldservice.stage'].search([
            ('state', '=', 'completed'),
            ('active', '=', True)
        ], order='sequence', limit=1)

        self.fso_id.write({
            'stage_id': completed_stage.id if completed_stage else False,
            'state': 'completed',  # Move to completed after cash payment
            'payment_status': 'paid',
        })
        
        # Log service completion (per Invoicing.md)
        self._log_service_completion()
        
        return self._return_success_action('Payment processed successfully. Invoice submitted to Tax Department.')
    
    def _process_pay_later_workflow(self):
        """Process Case 3: Payment After Service (Invoicing.md)"""
        self.ensure_one()
        
        # Post the invoice
        if self.invoice_id.state == 'draft':
            self.invoice_id.action_post()
        
        # Set payment terms
        if self.payment_terms:
            self.invoice_id.write({
                'invoice_payment_term_id': self.payment_terms.id,
                'invoice_date_due': self.due_date,
            })
        
        # Submit to Tax Authorities immediately (per Invoicing.md Case 3)
        if self.tax_submission_required:
            self._submit_to_tax_authorities()
        
        # Create AR entry with positive outstanding balance (per Invoicing.md)
        self._create_ar_entry_with_balance()
        
        # Update FSO status - Move to Completed-Pending Invoice stage for Pay Later
        completed_pending_stage = self.env['health.fieldservice.stage'].search([
            ('state', '=', 'completed_pending_invoice'),
            ('active', '=', True)
        ], order='sequence', limit=1)

        self.fso_id.write({
            'stage_id': completed_pending_stage.id if completed_pending_stage else False,
            'state': 'completed_pending_invoice',
            'payment_status': 'pending',
        })
        
        # Log service completion
        self._log_service_completion()
        
        return self._return_success_action('Invoice created and submitted to Tax Department. Outstanding balance recorded in AR.')
    
    def _apply_invoice_adjustments(self):
        """Apply invoice adjustments if nurse made changes"""
        if abs(self.payment_amount - self.amount_total) < 0.01:
            return
        
        # Create adjustment line
        adjustment_amount = self.payment_amount - self.amount_total
        
        if adjustment_amount != 0:
            adjustment_line = self.env['account.move.line'].create({
                'move_id': self.invoice_id.id,
                'name': f'Service Adjustment: {self.adjustment_reason}',
                'quantity': 1,
                'price_unit': adjustment_amount,
                'account_id': self._get_adjustment_account().id,
            })
            
            # Recompute invoice totals
            self.invoice_id._compute_amount()
    
    def _get_payment_journal(self):
        """Get appropriate payment journal based on payment method"""
        if self.payment_method == 'cash':
            journal = self.env['account.journal'].search([
                ('type', '=', 'cash'),
                ('company_id', '=', self.env.company.id)
            ], limit=1)
        else:
            journal = self.env['account.journal'].search([
                ('type', '=', 'bank'), 
                ('company_id', '=', self.env.company.id)
            ], limit=1)
        
        if not journal:
            raise UserError(_('No appropriate payment journal found. Please configure payment journals.'))
        
        return journal
    
    def _get_adjustment_account(self):
        """Get account for invoice adjustments"""
        account = self.env['account.account'].search([
            ('code', 'like', '6%'),  # Revenue adjustment account
            ('company_id', '=', self.env.company.id)
        ], limit=1)
        
        if not account:
            # Fallback to default receivable account
            account = self.env.company.account_default_pos_receivable_account_id
        
        return account
    
    def _reconcile_payment_with_invoice(self, payment):
        """Reconcile payment with invoice"""
        # Get receivable lines
        receivable_lines = self.invoice_id.line_ids.filtered(
            lambda line: line.account_id.account_type == 'asset_receivable'
        )
        payment_lines = payment.line_ids.filtered(
            lambda line: line.account_id.account_type == 'asset_receivable'
        )
        
        # Reconcile
        if receivable_lines and payment_lines:
            (receivable_lines + payment_lines).reconcile()
    
    def _handle_cash_collection_workflow(self, payment):
        """Handle cash collection workflow per Invoicing.md Case 1"""
        # TODO: Create cash collection record for Operations Manager
        # self.env['health.cash.collection'].create({
        #     'payment_id': payment.id,
        #     'fso_id': self.fso_id.id,
        #     'staff_member_id': self.fso_id.lead_staff_id.id,
        #     'amount': self.payment_amount,
        #     'collection_date': fields.Date.today(),
        #     'status': 'held_by_staff',
        #     'notes': 'Cash held by nurse until clinic visit - OM receipt required',
        #     'om_receipt_required': True,
        # })
        
        # Log in AR as increase (per Invoicing.md: "Initial nurse collection logged as AR ↑")
        self._log_ar_cash_collection(payment)
    
    def _log_ar_cash_collection(self, payment):
        """Log AR cash collection per Invoicing.md requirements"""
        # Note: Cash is recorded as AR increase initially, not cash increase
        # Cash increase only happens when OM receives it from nurse
        
        payment.write({
            'ar_cash_status': 'ar_increase_logged',
            'cash_recorded': False,  # Will be True when OM receives cash
            'ar_notes': 'Initial nurse collection - logged as AR increase per Invoicing.md',
        })
    
    def _create_ar_entry_with_balance(self):
        """Create AR entry with outstanding balance (Case 3)"""
        # The invoice posting already creates the AR entry
        # This method can be used for additional AR tracking if needed
        # TODO: Create AR tracking record when model is implemented
        # ar_vals = {
        #     'fso_id': self.fso_id.id,
        #     'invoice_id': self.invoice_id.id,
        #     'customer_id': self.invoice_id.partner_id.id,
        #     'outstanding_amount': self.amount_total,
        #     'due_date': self.due_date,
        #     'status': 'outstanding',
        #     'notes': 'Outstanding balance from Pay Later workflow',
        # }
        # 
        # self.env['health.ar.tracking'].create(ar_vals)
        pass
    
    def _submit_to_tax_authorities(self):
        """Submit invoice to Vietnamese Tax Authorities"""
        try:
            # Set completion time for audit trail
            self.invoice_id.write({
                'healthcare_actual_completion_time': self.actual_completion_time or fields.Datetime.now(),
                'healthcare_adjusted_submission_time': self.adjusted_submission_time or fields.Datetime.now(),
            })
            
            # Call tax submission method from health_invoicing
            success = self.invoice_id._submit_to_tax_authorities()
            
            if not success:
                _logger.warning(f'Tax submission failed for invoice {self.invoice_id.name}')
                
            # Handle offline submission if no internet
            if self.offline_submission:
                self.invoice_id.write({
                    'tax_authority_submission_status': 'pending',
                    'offline_submission_flag': True,
                    'offline_submission_reason': 'No internet connectivity',
                })
                
        except Exception as e:
            _logger.error(f'Tax submission error for invoice {self.invoice_id.name}: {str(e)}')
            # Don't fail the payment workflow due to tax submission issues
    
    def _log_service_completion(self):
        """Log service completion per Invoicing.md requirements"""
        # TODO: Log service completion when model is implemented
        # completion_data = {
        #     'fso_id': self.fso_id.id,
        #     'completion_time': self.actual_completion_time or fields.Datetime.now(),
        #     'invoice_id': self.invoice_id.id,
        #     'payment_workflow': self.payment_workflow,
        #     'payment_method': self.payment_method,
        #     'tax_submitted': self.tax_submission_required,
        #     'offline_submission': self.offline_submission,
        #     'notes': f'Service completed with {self.payment_workflow} workflow',
        # }
        # 
        # self.env['health.service.completion.log'].create(completion_data)
        pass
    
    def _return_success_action(self, message):
        """Return success action with message"""
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': _(message),
                'type': 'success',
                'sticky': False,
            },
            'next': {
                'type': 'ir.actions.act_window_close',
            }
        }
    
    def action_view_invoice(self):
        """View the generated invoice"""
        self.ensure_one()
        return {
            'name': _('Generated Invoice'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.invoice_id.id,
            'view_mode': 'form',
            'target': 'current',
        }