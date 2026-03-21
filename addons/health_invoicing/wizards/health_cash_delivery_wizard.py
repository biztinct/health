# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class HealthCashDeliveryWizard(models.TransientModel):
    """
    Cash Delivery Confirmation Wizard
    
    Handles the critical cash workflow from INVOICING.md:
    Nurse collects cash → Nurse delivers to OM → OM confirms receipt
    """
    _name = 'health.cash.delivery.wizard'
    _description = 'Cash Delivery Confirmation Wizard'
    
    transaction_id = fields.Many2one(
        'health.payment.transaction',
        string='Payment Transaction',
        required=True,
        readonly=True,
        help='Cash transaction being delivered to OM'
    )
    
    patient_name = fields.Char(
        'Patient',
        related='transaction_id.patient_id.name',
        readonly=True
    )
    
    cash_amount = fields.Monetary(
        'Cash Amount',
        related='transaction_id.amount',
        readonly=True,
        help='Amount of cash being delivered'
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        related='transaction_id.currency_id',
        readonly=True
    )
    
    collected_by = fields.Char(
        'Originally Collected By',
        related='transaction_id.collected_by_id.name',
        readonly=True
    )
    
    # OM Information
    om_employee_id = fields.Many2one(
        'hr.employee',
        string='Operations Manager',
        required=True,
        domain="[('is_healthcare_staff', '=', True)]",
        help='Operations Manager receiving the cash'
    )
    
    delivery_date = fields.Datetime(
        'Delivery Date & Time',
        default=fields.Datetime.now,
        required=True,
        help='When cash is being delivered to OM'
    )
    
    # Receipt Information
    generate_receipt = fields.Boolean(
        'Generate Electronic Receipt',
        default=True,
        help='Generate electronic receipt for cash delivery'
    )
    
    om_receipt_number = fields.Char(
        'OM Receipt Number',
        help='Electronic receipt number (auto-generated if empty)'
    )
    
    # Verification
    amount_verified = fields.Boolean(
        'Amount Verified',
        help='OM has verified the cash amount matches the transaction'
    )
    
    cash_condition_notes = fields.Text(
        'Cash Condition Notes',
        placeholder="Notes about cash condition, denomination, any issues...",
        help='Any notes about the physical cash condition'
    )
    
    # Process Options
    auto_reconcile_ar = fields.Boolean(
        'Auto-Reconcile in AR',
        default=True,
        help='Automatically reconcile this payment in Accounts Receivable'
    )
    
    create_bank_deposit = fields.Boolean(
        'Create Bank Deposit Record',
        default=True,
        help='Create bank deposit record for cash banking'
    )
    
    @api.onchange('om_employee_id')
    def _onchange_om_employee(self):
        if self.om_employee_id and not self.om_receipt_number:
            # Auto-generate receipt number
            sequence = self.env['ir.sequence'].next_by_code('health.om.receipt') or '0001'
            date_part = fields.Date.today().strftime('%Y%m%d')
            self.om_receipt_number = f"OM-{self.om_employee_id.id or 'EMP'}-{date_part}-{sequence}"
    
    @api.constrains('cash_amount')
    def _check_cash_amount(self):
        for wizard in self:
            if wizard.cash_amount <= 0:
                raise ValidationError(_('Cash amount must be positive.'))
    
    @api.constrains('amount_verified')
    def _check_amount_verified(self):
        for wizard in self:
            if not wizard.amount_verified:
                raise ValidationError(_('Operations Manager must verify the cash amount before confirming delivery.'))
    
    def action_confirm_cash_delivery(self):
        """Confirm cash delivery to Operations Manager"""
        self.ensure_one()
        
        if self.transaction_id.status != 'pending_delivery':
            raise UserError(_('Transaction is not pending delivery.'))
        
        if self.transaction_id.payment_method != 'cash':
            raise UserError(_('Only cash payments require delivery confirmation.'))
        
        # Process cash delivery - simplified approach
        update_vals = {
            'received_by_om_id': self.om_employee_id.id,
            'cash_delivery_date': self.delivery_date,
            'om_receipt_number': self.om_receipt_number,
            'status': 'delivered_to_om',
        }
        
        # Add notes if provided
        if self.cash_condition_notes:
            current_notes = self.transaction_id.transaction_notes or ""
            update_vals['transaction_notes'] = current_notes + f"\n\nCash Delivery Notes: {self.cash_condition_notes}"
        
        self.transaction_id.write(update_vals)
        
        # Auto-reconcile if requested - use standard payment registration
        ar_payment = None
        if self.auto_reconcile_ar and self.transaction_id.invoice_id:
            ar_payment = self._create_standard_payment()
        
        # Create bank deposit record if requested
        if self.create_bank_deposit:
            self._create_bank_deposit_record(ar_payment)
        
        # Generate comprehensive success message
        success_message = f"""
        Cash Delivery Confirmed Successfully!
        
        💰 Amount: {self.cash_amount:,.0f} {self.currency_id.symbol}
        👤 Delivered to: {self.om_employee_id.name}
        🧾 OM Receipt: {self.om_receipt_number}
        📅 Delivery Time: {self.delivery_date.strftime('%d/%m/%Y %H:%M')}
        """
        
        if self.auto_reconcile_ar:
            success_message += "\n✅ Payment reconciled in Accounts Receivable"
        
        if self.create_bank_deposit:
            success_message += "\n🏦 Bank deposit record created"
        
        # Post success message
        try:
            self.transaction_id.message_post(
                body=success_message,
                subject="Cash Delivered to Operations Manager"
            )
        except Exception:
            pass  # Silently fail - no email notifications required
        
        # Return to transaction form
        return {
            'name': _('Cash Delivery Completed'),
            'type': 'ir.actions.act_window',
            'res_model': 'health.payment.transaction',
            'res_id': self.transaction_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def _create_standard_payment(self):
        """Create payment record to settle Cash in Transit when OM receives cash.
        
        CRMv2 flow:
        - Step 1 (nurse collects): Debit CIT → Credit AR (already done)
        - Step 2 (OM receives - HERE): Debit Cash → Credit CIT
        
        If no CIT entry exists (legacy transactions), fall back to standard
        payment: Debit Cash → Credit AR.
        """
        # Check if this transaction has a CIT entry to settle
        cit_move = self.transaction_id.cit_move_id if hasattr(self.transaction_id, 'cit_move_id') else False
        
        if cit_move:
            # New CRMv2 flow: Debit Cash, Credit CIT
            return self._create_cit_settlement_entry(cit_move)
        else:
            # Legacy fallback: standard Debit Cash → Credit AR
            return self._create_legacy_cash_payment()

    def _create_cit_settlement_entry(self, cit_move):
        """Create journal entry: Debit Cash → Credit CIT (OM receives cash from nurse)."""
        cit_account = self.env.ref(
            'health_invoicing.account_cash_in_transit_nurse', raise_if_not_found=False
        )
        if not cit_account:
            return self._create_legacy_cash_payment()

        # Get the cash account from the Cash journal
        cash_journal = self.env['account.journal'].search([
            ('type', '=', 'cash'),
            ('company_id', '=', self.env.company.id)
        ], limit=1)
        if not cash_journal:
            raise UserError(_('No Cash journal found. Please configure one in Accounting settings.'))

        # Use the cash journal's default debit account
        cash_account = cash_journal.default_account_id
        if not cash_account:
            raise UserError(_('Cash journal has no default account configured.'))

        amount = abs(self.transaction_id.amount)

        # Use a miscellaneous journal for the CIT settlement
        misc_journal = self.env['account.journal'].search([
            ('type', '=', 'general'),
            ('company_id', '=', self.env.company.id),
        ], limit=1)
        if not misc_journal:
            misc_journal = cash_journal  # Fallback to cash journal

        # Create journal entry: Debit Cash, Credit CIT
        move_vals = {
            'move_type': 'entry',
            'journal_id': misc_journal.id,
            'date': self.delivery_date.date() if self.delivery_date else fields.Date.today(),
            'ref': f'Cash handover to OM: {self.transaction_id.name}',
            'line_ids': [
                (0, 0, {
                    'name': f'Cash received from nurse: {self.transaction_id.name}',
                    'account_id': cash_account.id,
                    'partner_id': self.transaction_id.patient_id.id,
                    'debit': amount,
                    'credit': 0.0,
                }),
                (0, 0, {
                    'name': f'CIT settled - nurse cash delivered: {self.transaction_id.name}',
                    'account_id': cit_account.id,
                    'partner_id': self.transaction_id.patient_id.id,
                    'debit': 0.0,
                    'credit': amount,
                }),
            ],
        }

        settlement_move = self.env['account.move'].create(move_vals)
        settlement_move.action_post()

        # Update transaction status
        self.transaction_id.write({
            'status': 'reconciled',
            'ar_reconciliation_date': fields.Datetime.now()
        })

        # Log to AR Transaction Log
        ARLog = self.env.get('health.ar.transaction.log')
        if ARLog is not None:
            try:
                # Get booking from the transaction's FSO link
                txn = self.transaction_id
                fso = txn.fso_id if hasattr(txn, 'fso_id') and txn.fso_id else None
                patient = txn.patient_id if txn.patient_id else None
                crm = fso.crm_lead_id if fso and hasattr(fso, 'crm_lead_id') else None
                ARLog._log_move_posting(
                    settlement_move, event_type='handover',
                    booking=fso,
                    partner=patient,
                    crm_lead=crm,
                )
            except Exception:
                pass

        return settlement_move

    def _create_legacy_cash_payment(self):
        """Legacy fallback: Create standard payment (Debit Cash → Credit AR)."""
        # Get appropriate cash journal
        cash_journal = self.env['account.journal'].search([
            ('type', '=', 'cash'),
            ('company_id', '=', self.env.company.id)
        ], limit=1)
        
        if not cash_journal:
            raise UserError(_(
                'No Cash journal found in the system.\n\n'
                'To fix this, go to:\n'
                'Accounting → Configuration → Journals → Create\n'
                'Set Type = "Cash" and configure the default accounts.\n\n'
                'The AR payment cannot be created without a Cash journal.'
            ))
        
        # Create standard account.payment record
        payment_vals = {
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': self.transaction_id.patient_id.id,
            'amount': abs(self.transaction_id.amount),
            'currency_id': self.transaction_id.currency_id.id,
            'date': self.delivery_date.date(),
            'journal_id': cash_journal.id,
        }
        
        payment = self.env['account.payment'].create(payment_vals)
        payment.action_post()
        
        # Link to transaction and update status to reconciled
        self.transaction_id.write({
            'payment_id': payment.id,
            'status': 'reconciled',
            'ar_reconciliation_date': fields.Datetime.now()
        })
        
        # Auto-reconcile with invoice if exists
        if self.transaction_id.invoice_id:
            self._reconcile_payment_with_invoice(payment, self.transaction_id.invoice_id)
        
        return payment
    
    def _reconcile_payment_with_invoice(self, payment, invoice):
        """Reconcile payment with invoice using standard Odoo methods"""
        # In Odoo 19, account.payment.state may be 'in_process' after posting,
        # but the underlying journal entry (move_id) has state='posted'.
        # Check the move state instead of the payment state.
        payment_move = payment.move_id
        if not payment_move or payment_move.state != 'posted' or invoice.state != 'posted':
            return False
            
        # Use standard reconciliation on the journal entry lines
        payment_lines = payment_move.line_ids.filtered(
            lambda line: line.account_id.account_type in ('asset_receivable', 'liability_payable')
                         and not line.reconciled
        )
        invoice_lines = invoice.line_ids.filtered(
            lambda line: line.account_id.account_type in ('asset_receivable', 'liability_payable')
                         and not line.reconciled
        )
        
        if payment_lines and invoice_lines:
            (payment_lines + invoice_lines).reconcile()
            return True
            
        return False
    
    def _create_bank_deposit_record(self, ar_payment):
        """Create bank deposit record for cash banking workflow"""
        if not ar_payment:
            return False
        
        # Find cash journal
        cash_journal = self.env['account.journal'].search([
            ('type', '=', 'cash'),
            ('company_id', '=', self.env.company.id)
        ], limit=1)
        
        if not cash_journal:
            return False
        
        # Create bank deposit entry (simplified)
        bank_deposit_vals = {
            'name': f'Cash Deposit - {self.om_receipt_number}',
            'journal_id': cash_journal.id,
            'date': self.delivery_date.date(),
            'ref': f'Cash collection from {self.transaction_id.collected_by_id.name}',
            'line_ids': [(0, 0, {
                'name': f'Cash deposit - {self.transaction_id.display_name}',
                'debit': self.cash_amount,
                'credit': 0.0,
                'account_id': cash_journal.default_account_id.id,
            })],
        }
        
        try:
            deposit_move = self.env['account.move'].create(bank_deposit_vals)
            deposit_move.action_post()

            # Link to transaction
            try:
                self.transaction_id.message_post(
                    body=f"Bank deposit created: {deposit_move.name}",
                    subject="Bank Deposit Created"
                )
            except Exception:
                pass  # Silently fail - no email notifications required

            return deposit_move
        except Exception as e:
            # Log error but don't block the main process
            try:
                self.transaction_id.message_post(
                    body=f"Bank deposit creation failed: {str(e)}. Please create manually.",
                    subject="Bank Deposit Error"
                )
            except Exception:
                pass  # Silently fail - no email notifications required
            return False