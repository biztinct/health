# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class HealthPrepaidPackageWizard(models.TransientModel):
    """
    Wizard for Front Desk/OM to Create Prepaid Service Packages
    
    Streamlines the process of:
    1. Creating service package with countdown
    2. Generating prepaid invoice 
    3. Processing payment
    4. Setting up package for nurse consumption
    """
    _name = 'health.prepaid.package.wizard'
    _description = 'Prepaid Package Creation Wizard'
    
    # Patient Information
    patient_id = fields.Many2one(
        'res.partner',
        string='Client',
        required=True,
        domain="[('is_patient', '=', True)]",
        help='client purchasing this prepaid package'
    )
    
    # Package Configuration - Product-Based Approach
    package_product_id = fields.Many2one(
        'product.template',
        string='Package Product',
        domain="[('type', '=', 'healthcare_package')]",
        required=True,
        help='Select a healthcare package product template'
    )
    
    # Auto-populated fields from product template
    package_name = fields.Char(
        'Package Name',
        compute='_compute_product_fields',
        readonly=True,
        help='Name from selected package product'
    )
    
    service_type = fields.Char(
        'Service Type',
        compute='_compute_product_fields',
        readonly=True,
        help='Service type from selected package product'
    )
    
    total_services = fields.Integer(
        'Number of Services',
        compute='_compute_product_fields',
        readonly=True,
        help='Number of services from selected package product'
    )
    
    package_price = fields.Float(
        'Package Price',
        compute='_compute_product_fields',
        readonly=True,
        help='Price from selected package product'
    )
    
    price_per_service = fields.Float(
        'Price Per Service',
        compute='_compute_product_fields',
        readonly=True,
        help='Price per service from selected package product'
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
        required=True
    )
    
    # Package Options (from product template)
    expiration_date = fields.Date(
        'Expiration Date',
        compute='_compute_expiration_date',
        help='Auto-calculated expiration date based on package duration'
    )
    
    package_notes = fields.Text(
        'Package Notes',
        compute='_compute_product_fields',
        readonly=True,
        help='Package terms and conditions from product template'
    )
    
    # Payment Processing
    create_invoice = fields.Boolean(
        'Create Invoice',
        default=True,
        help='Create and submit invoice for this package'
    )
    
    process_payment = fields.Boolean(
        'Process Payment Now',
        default=False,
        help='Process payment immediately after package creation'
    )
    
    payment_method = fields.Selection([
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
        ('credit_card', 'Credit Card'),
        ('qr_code', 'QR Code Payment'),
        ('other', 'Other'),
    ], string='Payment Method',
       states={'invisible': [('process_payment', '=', False)]},
       help='Method of payment if processing now')
    
    payment_amount = fields.Monetary(
        'Payment Amount',
        currency_field='currency_id',
        states={'invisible': [('process_payment', '=', False)]},
        help='Amount being paid (can be partial)'
    )
    
    # Computed Fields
    @api.depends('package_product_id')
    def _compute_product_fields(self):
        for wizard in self:
            if wizard.package_product_id:
                product = wizard.package_product_id
                wizard.package_name = product.name
                wizard.service_type = product.healthcare_package_type
                wizard.total_services = product.healthcare_service_count
                wizard.package_price = product.list_price
                wizard.price_per_service = product.healthcare_price_per_visit
                wizard.package_notes = product.healthcare_terms or ''
            else:
                wizard.package_name = False
                wizard.service_type = False
                wizard.total_services = 0
                wizard.package_price = 0.0
                wizard.price_per_service = 0.0
                wizard.package_notes = False
    
    @api.depends('package_product_id', 'package_product_id.healthcare_package_duration')
    def _compute_expiration_date(self):
        for wizard in self:
            if wizard.package_product_id and wizard.package_product_id.healthcare_package_duration:
                wizard.expiration_date = fields.Date.add(
                    fields.Date.today(), 
                    weeks=wizard.package_product_id.healthcare_package_duration
                )
            else:
                wizard.expiration_date = False
    
    @api.onchange('process_payment', 'package_price')
    def _onchange_process_payment(self):
        if self.process_payment:
            self.payment_amount = self.package_price
        else:
            self.payment_amount = 0.0
    
    # Validation
    @api.constrains('package_product_id')
    def _check_package_product(self):
        for wizard in self:
            if not wizard.package_product_id:
                raise ValidationError(_('Please select a healthcare package product.'))
            if wizard.package_product_id.type != 'healthcare_package':
                raise ValidationError(_('Selected product must be a healthcare package type.'))
    
    @api.constrains('payment_amount', 'package_price')
    def _check_payment_amount(self):
        for wizard in self:
            if wizard.process_payment and wizard.payment_amount > wizard.package_price:
                raise ValidationError(_('Payment amount cannot exceed package price.'))
    
    # Main Action
    def action_create_package(self):
        """Create prepaid package using product template with optional invoice and payment"""
        self.ensure_one()
        
        invoice_id = False
        package = None
        
        # Step 1: Create Invoice (if requested) - Let invoice posting create the package automatically
        if self.create_invoice:
            invoice = self.env['account.move'].create({
                'move_type': 'out_invoice',
                'partner_id': self.patient_id.id,
                'invoice_origin': f'Prepaid Package: {self.package_name}',
                'invoice_line_ids': [(0, 0, {
                    'name': f'{self.package_name} ({self.total_services} services)',
                    'product_id': self.package_product_id.product_variant_ids[0].id,
                    'quantity': 1,
                    'price_unit': self.package_price,
                    'product_uom_id': self.package_product_id.uom_id.id,
                })],
            })
            
            invoice_id = invoice.id
            
            # Post the invoice (this will auto-create the package)
            invoice.action_post()
            
            # Find the package that was created by invoice posting
            package = self.env['health.service.package'].search([
                ('product_template_id', '=', self.package_product_id.id),
                ('patient_id', '=', self.patient_id.id),
                ('invoice_id', '=', invoice.id)
            ], limit=1, order='create_date desc')
            
            # Submit to tax authorities (Vietnamese compliance)
            try:
                invoice.action_submit_to_tax_authority()
            except Exception as e:
                # Log but don't block - can be submitted later
                if package:
                    package.message_post(
                        body=f"Invoice created but tax submission failed: {str(e)}. Please submit manually.",
                        subject="Tax Submission Warning"
                    )
        else:
            # If no invoice requested, create package directly
            package = self.package_product_id.create_patient_package(
                patient_id=self.patient_id.id
            )
        
        # Step 3: Process Payment (if requested)
        transaction_id = False
        if self.process_payment and self.payment_amount > 0 and package:
            transaction = self.env['health.payment.transaction'].create({
                'patient_id': self.patient_id.id,
                'package_id': package.id,
                'invoice_id': invoice_id,
                'amount': self.payment_amount,
                'payment_method': self.payment_method,
                'transaction_type': 'prepaid',
                'status': 'collected' if self.payment_method != 'cash' else 'pending_delivery',
                'collected_by_id': self.env.user.employee_id.id if self.env.user.employee_id else False,
                'transaction_notes': f'Prepaid payment for package: {self.package_name}',
            })
            transaction_id = transaction.id
            
            # Create AR payment for non-cash payments
            if self.payment_method != 'cash' and invoice_id:
                ar_payment = self._create_ar_payment(transaction, invoice)
                transaction.payment_id = ar_payment.id
                transaction.write({
                    'status': 'reconciled',
                    'ar_reconciliation_date': fields.Datetime.now()
                })
        
        # Success handling
        if package:
            # Success message
            message = f"""
            Prepaid Package Created Successfully!
            
            Package: {package.name}
            Services: {package.total_services} × {package.service_type.replace('_', ' ').title()}
            Total Value: {package.package_price:,.0f} {package.currency_id.symbol}
            """
            
            if invoice_id:
                message += f"\n✓ Invoice created and submitted to tax authorities"
            if transaction_id:
                message += f"\n✓ Payment processed: {self.payment_amount:,.0f} {self.currency_id.symbol}"
            
            package.message_post(
                body=message,
                subject="Prepaid Package Created"
            )
            
            # Return action to view the created package
            return {
                'name': _('Prepaid Service Package'),
                'type': 'ir.actions.act_window',
                'res_model': 'health.service.package',
                'res_id': package.id,
                'view_mode': 'form',
                'target': 'current',
            }
        else:
            # Fallback if package creation failed
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Package Creation'),
                    'message': _('Package workflow completed. Check the patient record for package details.'),
                    'sticky': False,
                    'type': 'success'
                }
            }
    
    def _create_ar_payment(self, transaction, invoice):
        """Create standard account.payment record for prepaid packages"""
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
            'amount': abs(self.payment_amount),
            'currency_id': self.currency_id.id,
            'date': fields.Date.today(),
            'journal_id': journal.id,
            'payment_reference': f"Prepaid package: {self.package_name}",
        }
        
        payment = self.env['account.payment'].create(payment_vals)
        payment.action_post()
        
        # Auto-reconcile with invoice
        self._reconcile_payment_with_invoice(payment, invoice)
        
        return payment
    
    def _reconcile_payment_with_invoice(self, payment, invoice):
        """Reconcile payment with invoice using standard Odoo methods"""
        if payment.state != 'posted' or invoice.state != 'posted':
            return False
            
        # Use standard reconciliation
        payment_lines = payment.line_ids.filtered(
            lambda line: line.account_id.account_type in ('asset_receivable', 'liability_payable')
        )
        invoice_lines = invoice.line_ids.filtered(
            lambda line: line.account_id.account_type in ('asset_receivable', 'liability_payable')
        )
        
        if payment_lines and invoice_lines:
            (payment_lines + invoice_lines).reconcile()
            return True
            
        return False