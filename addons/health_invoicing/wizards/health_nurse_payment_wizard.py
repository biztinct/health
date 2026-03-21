# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class HealthNursePaymentWizard(models.TransientModel):
    """
    Nurse Payment Collection Wizard - "Pay Now or Pay Later"
    
    Critical workflow when nurse completes FSO:
    1. System generates final invoice
    2. Nurse prompted: "Pay Now" or "Pay Later"
    3. If Pay Now: Payment method selection & collection
    4. If Pay Later: Creates AR entry for later collection
    5. Invoice submitted to Vietnamese Tax Authorities
    """
    _name = 'health.nurse.payment.wizard'
    _description = 'Nurse Payment Collection Wizard'
    
    # FSO and Service Information
    fso_id = fields.Many2one(
        'health.fieldservice.order',
        string='Booking',
        required=True,
        readonly=True,
        help='Completed field service order requiring payment'
    )
    
    patient_id = fields.Many2one(
        'res.partner',
        string='Client',
        related='fso_id.patient_id',
        readonly=True,
        help='client who received the service'
    )
    
    nurse_id = fields.Many2one(
        'hr.employee',
        string='Nurse/Staff',
        default=lambda self: self._get_current_nurse(),
        readonly=True,
        help='Healthcare staff collecting payment'
    )
    
    # Invoice Information
    calculated_amount = fields.Monetary(
        'Calculated Invoice Amount',
        currency_field='currency_id',
        compute='_compute_calculated_amount',
        store=True,
        help='Auto-calculated amount based on FSO services and time'
    )
    
    final_amount = fields.Monetary(
        'Final Invoice Amount',
        currency_field='currency_id',
        required=True,
        help='Final amount to invoice (nurse can adjust if needed)'
    )
    
    amount_adjustment = fields.Monetary(
        'Amount Adjustment',
        currency_field='currency_id',
        compute='_compute_amount_adjustment',
        help='Difference from calculated amount (if nurse adjusted)'
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
        required=True
    )
    
    # Payment Decision
    payment_choice = fields.Selection([
        ('pay_now', 'Pay Now - Collect Payment Immediately'),
        ('pay_later', 'Pay Later - Send Invoice for Later Collection'),
    ], string='Payment Option', required=True,
       help='Choose how to handle payment for this service')
    
    # Pay Now Options
    payment_method = fields.Selection([
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
        ('credit_card', 'Credit Card'),
        ('qr_code', 'QR Code Payment'),
        ('prepaid', 'Prepaid Service Package'),
        ('other', 'Other Method'),
    ], string='Payment Method',
       states={'invisible': [('payment_choice', '!=', 'pay_now')]},
       help='client will use to pay')
    
    # Prepaid Service Consumption
    prepaid_package_id = fields.Many2one(
        'health.service.package',
        string='Use Prepaid Package',
        domain="[('patient_id', '=', patient_id), ('state', '=', 'active'), ('remaining_services', '>', 0)]",
        states={'invisible': [('payment_method', '!=', 'prepaid')]},
        help='Consume services from prepaid package'
    )
    
    services_to_consume = fields.Integer(
        'Services to Consume',
        default=1,
        states={'invisible': [('payment_method', '!=', 'prepaid')]},
        help='Number of services to consume from package'
    )
    
    # Payment Proof (for non-cash payments)
    payment_proof_required = fields.Boolean(
        'Payment Proof Required',
        compute='_compute_payment_proof_required',
        help='Whether payment proof is required'
    )
    
    payment_proof_attachment_ids = fields.Many2many(
        'ir.attachment',
        'nurse_payment_attachment_rel',
        'wizard_id',
        'attachment_id',
        string='Payment Proof',
        states={'invisible': [('payment_proof_required', '=', False)]},
        help='Photos/documents proving payment (bank transfers, cards, etc.)'
    )
    
    # Nurse Notes
    nurse_notes = fields.Text(
        'Nurse Notes',
        help='Additional notes about service delivery or payment collection'
    )
    
    nurse_override_reason = fields.Text(
        'Amount Adjustment Reason',
        states={'invisible': [('amount_adjustment', '=', 0)]},
        help='Reason for adjusting the calculated amount'
    )
    
    # Invoice Creation Options
    create_invoice_now = fields.Boolean(
        'Create Invoice Now',
        default=True,
        help='Create and submit invoice immediately'
    )
    
    def _get_current_nurse(self):
        """Get current user's employee record if they are healthcare staff"""
        employee = self.env['hr.employee'].search([
            ('user_id', '=', self.env.user.id),
            ('is_healthcare_staff', '=', True)
        ], limit=1)
        return employee.id if employee else False
    
    # Computed Methods
    @api.depends('fso_id')
    def _compute_calculated_amount(self):
        for wizard in self:
            if wizard.fso_id:
                # Calculate amount based on FSO services, time, and equipment
                amount = 0.0

                # Base service amount from appointment type or sale order
                if wizard.fso_id.sale_order_id and wizard.fso_id.sale_order_id.order_line:
                    # Use sale order line items for amount calculation
                    amount += sum(line.price_subtotal for line in wizard.fso_id.sale_order_id.order_line)
                elif wizard.fso_id.appointment_type_id:
                    # Fallback to appointment type base price
                    amount += wizard.fso_id.appointment_type_id.price or 0.0
                
                # Equipment charges
                for equipment in wizard.fso_id.required_equipment_ids:
                    amount += equipment.rental_cost or 0.0
                
                wizard.calculated_amount = amount
                wizard.final_amount = amount  # Initialize final amount
            else:
                wizard.calculated_amount = 0.0
                wizard.final_amount = 0.0
    
    @api.depends('calculated_amount', 'final_amount')
    def _compute_amount_adjustment(self):
        for wizard in self:
            wizard.amount_adjustment = wizard.final_amount - wizard.calculated_amount
    
    @api.depends('payment_method')
    def _compute_payment_proof_required(self):
        for wizard in self:
            wizard.payment_proof_required = wizard.payment_method in ['bank_transfer', 'credit_card', 'qr_code']
    
    @api.onchange('payment_choice')
    def _onchange_payment_choice(self):
        if self.payment_choice == 'pay_later':
            self.payment_method = False
            self.prepaid_package_id = False
    
    @api.onchange('prepaid_package_id')
    def _onchange_prepaid_package(self):
        if self.prepaid_package_id:
            # Auto-calculate amount from prepaid package
            self.final_amount = self.prepaid_package_id.price_per_service * self.services_to_consume
    
    # Validation
    @api.constrains('final_amount')
    def _check_final_amount(self):
        for wizard in self:
            if wizard.final_amount < 0:
                raise ValidationError(_('Invoice amount cannot be negative.'))
    
    @api.constrains('payment_method', 'payment_proof_attachment_ids')
    def _check_payment_proof(self):
        for wizard in self:
            if (wizard.payment_choice == 'pay_now' and 
                wizard.payment_proof_required and 
                not wizard.payment_proof_attachment_ids):
                raise ValidationError(_(
                    'Payment proof is required for %s payments. Please take a photo/screenshot as proof.'
                ) % dict(wizard._fields['payment_method'].selection)[wizard.payment_method])
    
    @api.constrains('prepaid_package_id', 'services_to_consume')
    def _check_prepaid_consumption(self):
        for wizard in self:
            if wizard.payment_method == 'prepaid' and wizard.prepaid_package_id:
                if wizard.services_to_consume > wizard.prepaid_package_id.remaining_services:
                    raise ValidationError(_(
                        'Cannot consume %d services. Package "%s" only has %d services remaining.'
                    ) % (wizard.services_to_consume, wizard.prepaid_package_id.name, 
                         wizard.prepaid_package_id.remaining_services))
    
    # Main Actions
    def action_process_payment(self):
        """Main action - processes payment based on nurse selection"""
        self.ensure_one()

        if not self.fso_id:
            raise UserError(_('No Booking specified.'))

        # Validate payment method selection when "Pay Now" is chosen
        if self.payment_choice == 'pay_now':
            if not self.payment_method:
                raise UserError(_(
                    'Please select a Payment Method before collecting payment.\n\n'
                    'Available options:\n'
                    '• Cash\n'
                    '• Bank Transfer\n'
                    '• Credit Card\n'
                    '• QR Code Payment\n'
                    '• Prepaid Service Package\n'
                    '• Other Method'
                ))

        # Create invoice first (returns False if amount is zero)
        invoice = self._create_invoice()

        # Process payment based on choice (only if invoice was created)
        transaction = False
        if invoice:
            if self.payment_choice == 'pay_now':
                transaction = self._process_pay_now(invoice)
            else:
                transaction = self._process_pay_later(invoice)

        # Find Completed stage
        completed_stage = self.env['health.fieldservice.stage'].search([
            ('state', '=', 'completed'),
            ('active', '=', True)
        ], order='sequence', limit=1)

        if not completed_stage:
            raise UserError(_('No Completed stage found. Please configure booking stages properly.'))

        # Mark FSO as completed
        update_vals = {
            'state': 'completed',
            'stage_id': completed_stage.id,
            'actual_end_datetime': fields.Datetime.now(),
        }

        # Only set invoice fields if invoice was created
        if invoice:
            update_vals['invoice_id'] = invoice.id
            update_vals['is_invoiced'] = True

        self.fso_id.write(update_vals)

        # Success message and return action
        return self._return_success_action(invoice, transaction)
    
    def _create_invoice(self):
        """Create invoice for the FSO - convert quote to invoice if exists

        Returns:
            account.move: Created invoice, or False if invoice not needed (zero amount)
        """

        # Check if invoice should be created based on amount
        # Skip invoice creation if final amount is zero (similar to prepaid services)
        if self.final_amount <= 0.0:
            return False

        # If FSO has a quote/sale order, create invoice from it (preferred method)
        if self.fso_id.sale_order_id and self.fso_id.sale_order_id.order_line:
            sale_order = self.fso_id.sale_order_id

            # Check sale order total - skip invoice if zero
            if sale_order.amount_total <= 0.0:
                return False

            # Confirm the sale order if it's still in draft/sent state
            if sale_order.state in ['draft', 'sent']:
                sale_order.action_confirm()

            # Use Odoo's standard method to create invoice from sale order
            invoice = sale_order._create_invoices()

            if not invoice:
                raise UserError(_('Failed to create invoice from quote. Please contact support.'))

            # If multiple invoices were created, use the first one
            if len(invoice) > 1:
                invoice = invoice[0]

            # Link FSO origin
            invoice.write({
                'invoice_origin': f'FSO: {self.fso_id.name}, SO: {sale_order.name}',
            })

        else:
            # Fallback: Create invoice manually if no quote exists
            service_type_label = dict(self.fso_id._fields['service_type'].selection).get(
                self.fso_id.service_type, 'Healthcare Service'
            )

            service_description = f"{service_type_label}"
            if self.fso_id.appointment_type_id:
                service_description = f"{self.fso_id.appointment_type_id.name}"

            if self.fso_id.actual_duration:
                service_description += f" ({self.fso_id.actual_duration:.1f}h)"

            invoice_lines = [(0, 0, {
                'name': service_description,
                'quantity': 1,
                'price_unit': self.final_amount,
                'product_uom_id': self.env.ref('uom.product_uom_unit').id,
            })]

            # Create invoice manually
            invoice = self.env['account.move'].create({
                'move_type': 'out_invoice',
                'partner_id': self.patient_id.id,
                'invoice_origin': f'FSO: {self.fso_id.name}',
                'invoice_line_ids': invoice_lines,
            })
        
        # Post invoice and submit to tax authorities
        # CRMv2: Override income account to Service Revenue – Healthcare
        sr_account = self.env.ref(
            'health_invoicing.account_service_revenue', raise_if_not_found=False
        )
        if sr_account:
            for line in invoice.invoice_line_ids:
                if line.account_id and line.account_id.account_type in ('income', 'income_other'):
                    line.account_id = sr_account.id

        invoice.action_post()
        
        # Vietnamese tax submission (only if Red Invoice is enabled)
        red_invoice_enabled = self.env['ir.config_parameter'].sudo().get_param(
            'vietnamese_tax.red_invoice_enabled', 'True'
        ) == 'True'
        if red_invoice_enabled:
            try:
                invoice.action_submit_to_tax_authority()
            except Exception as e:
                # Log warning but don't block the process
                try:
                    invoice.message_post(
                        body=f"Invoice created but tax submission failed: {str(e)}. Please submit manually.",
                        subject="Tax Submission Warning"
                    )
                except Exception:
                    pass  # Silently fail - no email notifications required
        
        return invoice
    
    def _process_pay_now(self, invoice):
        """Process immediate payment collection"""
        if self.payment_method == 'prepaid':
            # Consume prepaid service
            consumption = self.prepaid_package_id.action_consume_service(
                fso_id=self.fso_id.id,
                quantity=self.services_to_consume
            )
            
            # CRMv2 Scenario B: Service delivered (prepaid) → Debit UR, Credit SR
            # Reclassify revenue from Unearned Revenue to Service Revenue
            self._create_ur_to_sr_reclassification(invoice)
            
            # Create transaction record for prepaid consumption
            transaction = self.env['health.payment.transaction'].create({
                'patient_id': self.patient_id.id,
                'fso_id': self.fso_id.id,
                'invoice_id': invoice.id,
                'package_id': self.prepaid_package_id.id,
                'amount': self.final_amount,
                'payment_method': 'prepaid',
                'transaction_type': 'prepaid',
                'status': 'reconciled',
                'collected_by_id': self.nurse_id.id,
                'transaction_notes': self.nurse_notes or f'Prepaid service consumed - {self.fso_id.name}',
            })
        else:
            # Regular payment collection
            # Non-cash payments (credit card, bank transfer, QR code) are
            # reconciled immediately — no physical cash delivery needed.
            # Cash payments go through pending_delivery → delivered_to_om flow.
            is_cash = self.payment_method == 'cash'
            transaction = self.env['health.payment.transaction'].create({
                'patient_id': self.patient_id.id,
                'fso_id': self.fso_id.id,
                'invoice_id': invoice.id,
                'amount': self.final_amount,
                'payment_method': self.payment_method,
                'transaction_type': 'immediate',
                'status': 'pending_delivery' if is_cash else 'reconciled',
                'collected_by_id': self.nurse_id.id,
                'transaction_notes': self.nurse_notes or f'Payment collected on completion - {self.fso_id.name}',
                'nurse_override_reason': self.nurse_override_reason if self.amount_adjustment != 0 else False,
                'original_invoice_amount': self.calculated_amount if self.amount_adjustment != 0 else False,
                'payment_proof_attachment_ids': [(6, 0, self.payment_proof_attachment_ids.ids)],
                'ar_reconciliation_date': fields.Datetime.now() if not is_cash else False,
            })
            
            if is_cash:
                # CRMv2 Scenario E: Nurse receives cash
                # Entry 1 (invoice posting already did): Debit AR → Credit SR
                # Entry 2 (here): Debit CIT → Credit AR
                # This settles the AR immediately but tracks cash as "in transit"
                self._create_cit_journal_entry(transaction, invoice)
            else:
                # Create account.payment for non-cash payments immediately
                # and reconcile with invoice — goes straight to Reconciled in AR
                ar_payment = self._create_ar_payment(transaction, invoice)
                transaction.payment_id = ar_payment.id
        
        return transaction
    
    def _process_pay_later(self, invoice):
        """Process deferred payment (Pay Later)"""
        # Create transaction record for Pay Later
        transaction = self.env['health.payment.transaction'].create({
            'patient_id': self.patient_id.id,
            'fso_id': self.fso_id.id,
            'invoice_id': invoice.id,
            'amount': self.final_amount,
            'payment_method': 'cash',  # Default assumption for Pay Later
            'transaction_type': 'deferred',
            'status': 'collected',  # Invoice created, payment pending
            'collected_by_id': self.nurse_id.id,
            'transaction_notes': self.nurse_notes or f'Pay Later - Invoice sent to patient - {self.fso_id.name}',
            'nurse_override_reason': self.nurse_override_reason if self.amount_adjustment != 0 else False,
            'original_invoice_amount': self.calculated_amount if self.amount_adjustment != 0 else False,
        })
        
        return transaction
    
    def _return_success_action(self, invoice, transaction):
        """Return success action based on payment method"""
        # Handle zero-amount services (no invoice created)
        if not invoice:
            message = _(
                'Service Completed Successfully!\n\n'
                '✅ Service Amount: %s %s (Zero)\n'
                '📋 No invoice created (zero amount service)\n\n'
                'Service marked as completed - No payment required.'
            ) % (f'{self.final_amount:,.0f}', self.currency_id.symbol)
        elif self.payment_choice == 'pay_now':
            if self.payment_method == 'cash':
                message = _(
                    'Payment Collected Successfully!\n\n'
                    '💰 Cash collected: %s %s\n'
                    '⚠️  Please deliver cash to Operations Manager\n\n'
                    'Service completed and invoice submitted to Tax Authorities.'
                ) % (f'{self.final_amount:,.0f}', self.currency_id.symbol)
            elif self.payment_method == 'prepaid':
                remaining = self.prepaid_package_id.remaining_services
                message = _(
                    'Prepaid Service Consumed!\n\n'
                    '🎁 Package: %s\n'
                    '✅ Services consumed: %d\n'
                    '📊 Services remaining: %d\n\n'
                    'Service completed and invoice submitted to Tax Authorities.'
                ) % (self.prepaid_package_id.name, self.services_to_consume, remaining)
            else:
                message = _(
                    'Payment Collected Successfully!\n\n'
                    '💳 Payment method: %s\n'
                    '💰 Amount: %s %s\n\n'
                    'Service completed and invoice submitted to Tax Authorities.'
                ) % (dict(self._fields['payment_method'].selection)[self.payment_method],
                     f'{self.final_amount:,.0f}', self.currency_id.symbol)
        else:
            message = _(
                'Invoice Sent to Patient!\n\n'
                '📧 Invoice amount: %s %s\n'
                '📋 Patient will receive invoice for later payment\n\n'
                'Service completed and invoice submitted to Tax Authorities.'
            ) % (f'{self.final_amount:,.0f}', self.currency_id.symbol)
        
        # Post message to FSO
        try:
            self.fso_id.message_post(
                body=message,
                subject="Service Completed & Payment Processed"
            )
        except Exception:
            pass  # Silently fail - no email notifications required
        
        # Return to FSO form with reload to update UI
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
            'params': {
                'next': {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Service Completed'),
                        'message': message,
                        'type': 'success',
                        'sticky': False,
                    }
                }
            }
        }
    
    def _create_ar_payment(self, transaction, invoice):
        """Create standard account.payment record for non-cash payments"""
        # Get appropriate journal based on payment method
        journal_type_map = {
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
        
        # Create standard account.payment record
        payment_vals = {
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': self.patient_id.id,
            'amount': abs(self.final_amount),
            'currency_id': self.currency_id.id,
            'date': fields.Date.today(),
            'journal_id': journal.id,
        }
        
        payment = self.env['account.payment'].create(payment_vals)
        payment.action_post()
        
        # Auto-reconcile with invoice
        self._reconcile_payment_with_invoice(payment, invoice)
        
        return payment
    
    def _reconcile_payment_with_invoice(self, payment, invoice):
        """Reconcile payment with invoice using standard Odoo methods"""
        # In Odoo 19, account.payment.state may be 'in_process' after posting,
        # but the underlying journal entry (move_id) has state='posted'.
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

    def _create_cit_journal_entry(self, transaction, invoice):
        """CRMv2 Scenario E: Nurse receives cash → Debit CIT, Credit AR.

        Creates a journal entry that:
        - Debits Cash in Transit – Nurse (asset) — cash is with the nurse
        - Credits Accounts Receivable — AR is settled from the client's perspective
        Then reconciles the AR line with the invoice so the invoice shows as Paid.
        """
        cit_account = self.env.ref(
            'health_invoicing.account_cash_in_transit_nurse', raise_if_not_found=False
        )
        if not cit_account:
            return False

        # Get the AR account from the invoice
        ar_lines = invoice.line_ids.filtered(
            lambda l: l.account_id.account_type == 'asset_receivable'
        )
        if not ar_lines:
            return False
        ar_account = ar_lines[0].account_id

        amount = abs(self.final_amount)

        # Use a miscellaneous journal for the CIT entry
        misc_journal = self.env['account.journal'].search([
            ('type', '=', 'general'),
            ('company_id', '=', self.env.company.id),
        ], limit=1)
        if not misc_journal:
            return False

        # Create journal entry: Debit CIT, Credit AR
        move_vals = {
            'move_type': 'entry',
            'journal_id': misc_journal.id,
            'date': fields.Date.today(),
            'ref': f'Nurse cash collection: {self.fso_id.name}',
            'line_ids': [
                (0, 0, {
                    'name': f'Cash in Transit - Nurse: {self.fso_id.name}',
                    'account_id': cit_account.id,
                    'partner_id': self.patient_id.id,
                    'debit': amount,
                    'credit': 0.0,
                }),
                (0, 0, {
                    'name': f'AR settled by nurse cash: {self.fso_id.name}',
                    'account_id': ar_account.id,
                    'partner_id': self.patient_id.id,
                    'debit': 0.0,
                    'credit': amount,
                }),
            ],
        }

        cit_move = self.env['account.move'].create(move_vals)
        cit_move.action_post()

        # Store the CIT move on the transaction for the cash delivery wizard
        transaction.write({
            'cit_move_id': cit_move.id,
        })

        # Reconcile the AR credit line with the invoice's AR debit line
        # so the invoice shows as "Paid"
        cit_ar_lines = cit_move.line_ids.filtered(
            lambda l: l.account_id.account_type == 'asset_receivable'
                      and not l.reconciled
        )
        invoice_ar_lines = invoice.line_ids.filtered(
            lambda l: l.account_id.account_type == 'asset_receivable'
                      and not l.reconciled
        )
        if cit_ar_lines and invoice_ar_lines:
            try:
                (cit_ar_lines + invoice_ar_lines).reconcile()
            except Exception:
                pass  # Don't block on reconciliation failure

        # Log to AR Transaction Log
        ARLog = self.env.get('health.ar.transaction.log')
        if ARLog is not None:
            try:
                ARLog._log_move_posting(
                    cit_move, event_type='payment',
                    booking=self.fso_id,
                    partner=self.patient_id,
                    crm_lead=self.fso_id.crm_lead_id if self.fso_id and hasattr(self.fso_id, 'crm_lead_id') else None,
                )
            except Exception:
                pass

        return cit_move

    def _create_ur_to_sr_reclassification(self, invoice):
        """CRMv2 Scenario B: Create UR → SR reclassification journal entry.

        When a prepaid service is consumed, revenue must be moved from
        Unearned Revenue (liability) to Service Revenue (income).
        This entry: Debit UR, Credit SR for the consumed amount.
        """
        ur_account = self.env.ref(
            'health_invoicing.account_unearned_revenue', raise_if_not_found=False
        )
        sr_account = self.env.ref(
            'health_invoicing.account_service_revenue', raise_if_not_found=False
        )
        if not ur_account or not sr_account:
            return False

        # Use the price_per_service from the package × consumed quantity
        amount = 0.0
        if self.prepaid_package_id and self.prepaid_package_id.price_per_service:
            amount = self.prepaid_package_id.price_per_service * self.services_to_consume
        if not amount:
            amount = self.final_amount

        # Find a miscellaneous journal for the reclassification entry
        misc_journal = self.env['account.journal'].search([
            ('type', '=', 'general'),
            ('company_id', '=', self.env.company.id),
        ], limit=1)
        if not misc_journal:
            return False

        # Create the reclassification journal entry
        move_vals = {
            'move_type': 'entry',
            'journal_id': misc_journal.id,
            'date': fields.Date.today(),
            'ref': f'Prepaid revenue recognition: {self.fso_id.name}',
            'line_ids': [
                (0, 0, {
                    'name': f'UR→SR: Prepaid service consumed - {self.fso_id.name}',
                    'account_id': ur_account.id,
                    'partner_id': self.patient_id.id,
                    'debit': amount,
                    'credit': 0.0,
                }),
                (0, 0, {
                    'name': f'UR→SR: Service revenue recognized - {self.fso_id.name}',
                    'account_id': sr_account.id,
                    'partner_id': self.patient_id.id,
                    'debit': 0.0,
                    'credit': amount,
                }),
            ],
        }

        reclass_move = self.env['account.move'].create(move_vals)
        reclass_move.action_post()

        # Log to AR Transaction Log
        ARLog = self.env.get('health.ar.transaction.log')
        if ARLog is not None:
            try:
                ARLog._log_move_posting(
                    reclass_move, event_type='service_delivery',
                    booking=self.fso_id,
                    partner=self.patient_id,
                    crm_lead=self.fso_id.crm_lead_id if self.fso_id and hasattr(self.fso_id, 'crm_lead_id') else None,
                )
            except Exception:
                pass  # Don't block service delivery on logging failure

        return reclass_move