# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import json
import requests
from datetime import datetime, timedelta


def _selection_move_type(model):
    return [
        ('entry', model.env._('Journal Entry')),
        ('out_invoice', model.env._('Customer Invoice')),
        ('out_refund', model.env._('Customer Credit Note')),
        ('in_invoice', model.env._('Vendor Bill')),
        ('in_refund', model.env._('Vendor Credit Note')),
        ('out_receipt', model.env._('Sales Receipt')),
        ('in_receipt', model.env._('Purchase Receipt')),
    ]


def _selection_move_state(model):
    return [
        ('draft', model.env._('Draft')),
        ('posted', model.env._('Posted')),
        ('cancel', model.env._('Cancelled')),
    ]


def _selection_payment_state(model):
    return [
        ('not_paid', model.env._('Not Paid')),
        ('in_payment', model.env._('In Payment')),
        ('paid', model.env._('Paid')),
        ('partial', model.env._('Partially Paid')),
        ('reversed', model.env._('Reversed')),
        ('blocked', model.env._('Blocked')),
        ('invoicing_legacy', model.env._('Invoicing App Legacy')),
    ]


def _selection_status_in_payment(model):
    return _selection_payment_state(model) + [
        ('draft', model.env._('Draft')),
        ('posted', model.env._('Posted')),
        ('sent', model.env._('Sent')),
        ('cancel', model.env._('Cancelled')),
    ]


def _selection_healthcare_service_type(model):
    return [
        ('home_visit', model.env._('Home Visit')),
        ('clinic_visit', model.env._('Clinic Visit')),
        ('consultation', model.env._('Consultation')),
        ('emergency', model.env._('Emergency Care')),
        ('follow_up', model.env._('Follow-up Care')),
        ('preventive', model.env._('Preventive Care')),
        ('rehabilitation', model.env._('Rehabilitation')),
        ('equipment_rental', model.env._('Equipment Rental')),
        ('supplies', model.env._('Medical Supplies')),
    ]


def _selection_tax_authority_status(model):
    return [
        ('draft', model.env._('Draft')),
        ('pending', model.env._('Pending Submission')),
        ('submitted', model.env._('Submitted')),
        ('accepted', model.env._('Accepted')),
        ('rejected', model.env._('Rejected')),
        ('error', model.env._('Submission Error')),
    ]


def _selection_misa_sync_status(model):
    return [
        ('not_synced', model.env._('Not Synced')),
        ('syncing', model.env._('Syncing')),
        ('synced', model.env._('Synced')),
        ('sync_error', model.env._('Sync Error')),
    ]


class HealthcareInvoice(models.Model):
    """
    Healthcare Invoice extending standard Odoo account.move functionality
    Inherits from account.move to leverage all standard accounting features
    
    FROM CLIENT REQUIREMENTS:
    - Vietnamese tax compliance and real-time submission
    - Healthcare service billing automation  
    - MISA accounting system integration
    - Ministry of Health regulatory compliance
    """
    _inherit = 'account.move'

    # Odoo 19 currently exposes static selection metadata in English through
    # fields_get. Callable selections return labels in the active user language.
    move_type = fields.Selection(selection=_selection_move_type)
    state = fields.Selection(selection=_selection_move_state)
    payment_state = fields.Selection(selection=_selection_payment_state)
    status_in_payment = fields.Selection(selection=_selection_status_in_payment)
    full_reconcile_payment_date = fields.Date(string='Payment Date')

    # Archive support — set active=False to hide records from all views
    active = fields.Boolean(default=True)

    # Healthcare service integration
    fieldservice_order_id = fields.Many2one(
        'health.fieldservice.order',
        string='Booking',
        help='Booking that generated this invoice'
    )

    catchment_province_id = fields.Many2one(
        'health.catchment.province',
        string='Catchment Area',
        compute='_compute_catchment_province_id',
        store=True,
        readonly=True,
        help='Catchment area used for filtering and access control'
    )

    @api.depends('fieldservice_order_id.catchment_province_id',
                 'fieldservice_order_id.facility_id.catchment_province_id',
                 'partner_id.catchment_province_id',
                 'partner_id.primary_facility_id.catchment_province_id')
    def _compute_catchment_province_id(self):
        for move in self:
            partner_catchment = move.partner_id._get_health_catchment_province() if move.partner_id else False
            move.catchment_province_id = (
                move.fieldservice_order_id.catchment_province_id
                or partner_catchment
                or move.fieldservice_order_id.facility_id.catchment_province_id
                or False
            )
    
    # appointment_id = fields.Many2one(
    #     'health.appointment',
    #     string='Appointment',
    #     help='Healthcare appointment that generated this invoice'
    # )
    
    # patient_id = fields.Many2one(
    #     'health.patient',
    #     string='Client',
    #     help='client receiving healthcare services'
    # )
    
    healthcare_service_type = fields.Selection(
        _selection_healthcare_service_type,
        string='Healthcare Service Type',
        help='Type of healthcare service billed',
    )

    # Vietnamese tax compliance fields
    vietnamese_tax_code = fields.Char(
        'Vietnamese Tax Code',
        help='Tax code for Vietnamese tax authority submission'
    )
    
    tax_authority_submission_status = fields.Selection(
        _selection_tax_authority_status,
        string='Tax Authority Status',
        default='draft',
        help='Status of real-time submission to Vietnamese Tax Authorities',
    )
    
    tax_submission_date = fields.Datetime(
        'Tax Submission Date',
        help='Date when invoice was submitted to tax authorities'
    )
    
    tax_submission_reference = fields.Char(
        'Tax Submission Reference',
        help='Reference number from tax authority submission'
    )
    
    tax_submission_error = fields.Text(
        'Tax Submission Error',
        help='Error message from tax authority submission'
    )
    

    # MISA integration fields
    misa_invoice_id = fields.Char(
        'MISA Invoice ID',
        help='Invoice ID in MISA accounting system'
    )
    
    misa_sync_status = fields.Selection(
        _selection_misa_sync_status,
        string='MISA Sync Status',
        default='not_synced',
        help='Synchronization status with MISA accounting system',
    )
    
    misa_sync_date = fields.Datetime(
        'MISA Sync Date',
        help='Date when invoice was synced to MISA'
    )
    
    misa_sync_error = fields.Text(
        'MISA Sync Error',
        help='Error message from MISA synchronization'
    )

    # Healthcare insurance and payment tracking
    has_insurance_claim = fields.Boolean(
        'Has Insurance Claim',
        help='This invoice has insurance claim processing'
    )
    
    insurance_provider = fields.Char(
        'Insurance Provider',
        help='Insurance company processing the claim'
    )
    
    insurance_claim_number = fields.Char(
        'Insurance Claim Number',
        help='Insurance claim reference number'
    )
    
    insurance_claim_status = fields.Selection([
        ('pending', 'Pending'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('partial_approved', 'Partially Approved'),
        ('rejected', 'Rejected'),
    ], string='Insurance Claim Status', help='Status of insurance claim processing')
    
    insurance_coverage_amount = fields.Monetary(
        'Insurance Coverage Amount',
        help='Amount covered by insurance'
    )
    
    patient_responsibility_amount = fields.Monetary(
        'Patient Responsibility',
        help='client is responsible for'
    )

    # Ministry of Health compliance
    moh_invoice_code = fields.Char(
        'MOH Invoice Code',
        help='Ministry of Health invoice tracking code'
    )
    
    moh_submission_status = fields.Selection([
        ('not_required', 'Not Required'),
        ('pending', 'Pending Submission'),
        ('submitted', 'Submitted'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
    ], string='MOH Submission Status', default='not_required',
       help='Ministry of Health submission status for regulatory compliance')
    
    moh_submission_date = fields.Datetime(
        'MOH Submission Date',
        help='Date submitted to Ministry of Health'
    )

    # Staff and equipment billing details
    staff_time_hours = fields.Float(
        'Staff Time (Hours)',
        help='Total staff time billed for this service'
    )
    
    equipment_rental_days = fields.Float(
        'Equipment Rental (Days)',
        help='Number of days equipment was rented'
    )
    
    travel_distance_km = fields.Float(
        'Travel Distance (km)',
        help='Travel distance for home visit billing'
    )
    
    urgency_surcharge = fields.Monetary(
        'Urgency Surcharge',
        help='Additional charge for urgent/emergency services'
    )

    # Vietnamese business compliance (FROM EXCEL REQUIREMENTS)
    customer_cccd_number = fields.Char(
        'Customer CCCD Number',
        related='partner_id.cccd_number',
        help='Vietnamese Citizen ID for tax compliance'
    )
    
    customer_tax_code = fields.Char(
        'Customer Tax Code',
        related='partner_id.vat',
        help='Customer tax registration number'
    )

    # VAT Invoice tracking fields (for VAT Invoices Log)
    vat_serial_code = fields.Char(
        'VAT Serial Code (Ký hiệu)',
        help='Yearly serial prefix e.g. 1C26MVU — configured in Settings',
    )
    retail_invoice_number = fields.Char(
        'Retail Invoice Number',
        help='Auto-generated retail invoice number (Hóa Đơn Bán Lẻ)',
        copy=False,
    )

    # Red Invoice configuration toggle (for view visibility)
    red_invoice_enabled = fields.Boolean(
        'Red Invoice Enabled',
        compute='_compute_red_invoice_enabled',
    )

    def _compute_red_invoice_enabled(self):
        """Check if Red Invoice feature is enabled in settings"""
        enabled = self.env['ir.config_parameter'].sudo().get_param(
            'vietnamese_tax.red_invoice_enabled', 'True'
        ) == 'True'
        for record in self:
            record.red_invoice_enabled = enabled

    def _is_red_invoice_enabled(self):
        """Helper: check if Red Invoice is enabled (for use in Python methods)"""
        return self.env['ir.config_parameter'].sudo().get_param(
            'vietnamese_tax.red_invoice_enabled', 'True'
        ) == 'True'

    # Discount tracking fields
    has_discounts = fields.Boolean(
        'Has Discounts',
        compute='_compute_has_discounts',
        help='True if any invoice line has a discount applied'
    )

    total_discount_amount = fields.Monetary(
        'Total Discount Amount',
        compute='_compute_discount_totals',
        currency_field='currency_id',
        store=False,
        help='Total amount discounted across all lines'
    )

    @api.depends('invoice_line_ids.discount')
    def _compute_has_discounts(self):
        """Check if invoice has any discounted lines"""
        for invoice in self:
            invoice.has_discounts = any(
                line.discount > 0 for line in invoice.invoice_line_ids
            )

    @api.depends('invoice_line_ids.discount', 'invoice_line_ids.price_unit', 'invoice_line_ids.quantity')
    def _compute_discount_totals(self):
        """Calculate total discount amount"""
        for invoice in self:
            total_discount = 0.0
            for line in invoice.invoice_line_ids:
                if line.discount > 0:
                    line_subtotal = line.price_unit * line.quantity
                    discount_amount = line_subtotal * (line.discount / 100)
                    total_discount += discount_amount
            invoice.total_discount_amount = total_discount

    @api.model
    def create(self, vals):
        """Override create to handle healthcare invoice automation"""
        vals_list = vals if isinstance(vals, list) else [vals]

        for vals_item in vals_list:
            # Auto-set healthcare service type from FSO
            if vals_item.get('fieldservice_order_id'):
                fso = self.env['health.fieldservice.order'].browse(vals_item['fieldservice_order_id'])
                if fso and not vals_item.get('healthcare_service_type'):
                    vals_item['healthcare_service_type'] = fso.service_category or 'home_visit'

            # Note: patient_id field is not defined on account.move
            # Patient info is accessible via fieldservice_order_id.patient_id if needed

            # Set Vietnamese tax code if not provided
            if not vals_item.get('vietnamese_tax_code'):
                vals_item['vietnamese_tax_code'] = self._generate_vietnamese_tax_code()

        invoice = super().create(vals_list)

        # Schedule tax submission after creation is complete (not during create)
        # This will be handled by the invoice posting process instead

        return invoice

    def write(self, vals):
        """Override write to handle status changes"""
        result = super().write(vals)
        
        # Handle posting - submit to tax authorities (only if Red Invoice enabled)
        if 'state' in vals and vals['state'] == 'posted':
            for invoice in self:
                if invoice.move_type in ('out_invoice', 'out_refund'):
                    # Create healthcare package instances for package products
                    if invoice.move_type == 'out_invoice':
                        invoice._create_healthcare_package_instances()
                    
                    # Only submit to tax/MISA if Red Invoice is enabled
                    if invoice._is_red_invoice_enabled():
                        invoice._submit_to_tax_authorities()
                        invoice._sync_to_misa()

                    # Auto-populate AR Transaction Log
                    try:
                        self.env['health.ar.transaction.log']._create_from_move(invoice)
                    except Exception:
                        pass  # Don't block posting if log creation fails
        
        return result

    def _create_healthcare_package_instances(self):
        """Create healthcare package instances for package products on invoice lines"""
        self.ensure_one()
        
        for line in self.invoice_line_ids:
            # Check if this line contains a healthcare package product
            if (line.product_id and 
                line.product_id.product_tmpl_id and
                line.product_id.product_tmpl_id.type == 'healthcare_package'):
                
                product_template = line.product_id.product_tmpl_id
                
                # Create package instances based on quantity
                for i in range(int(line.quantity)):
                    package = product_template.create_patient_package(
                        patient_id=self.partner_id.id,
                        invoice_line_id=line.id
                    )
                    
                    # Link invoice to first package created
                    if i == 0:
                        package.invoice_id = self.id
                    
                    # Log package creation
                    try:
                        self.message_post(
                            body=f"Healthcare package created: {package.name} ({product_template.healthcare_service_count} services)",
                            subject="Package Instance Created"
                        )
                    except Exception:
                        pass  # Silently fail - no email notifications required

    def _generate_vietnamese_tax_code(self):
        """Generate Vietnamese tax code for invoice"""
        sequence = self.env['ir.sequence'].next_by_code('vietnamese.tax.invoice') or '0000'
        company_tax = self.company_id.vat or 'NOTAX'
        date_part = fields.Date.today().strftime('%Y%m')
        return f"VN{company_tax[-4:]}{date_part}{sequence}"

    def _deactivate_tax_cron_jobs(self):
        """Legacy method - no longer needed since we don't track cron job references"""
        pass

    def _schedule_tax_authority_submission(self):
        """Schedule automatic submission to Vietnamese tax authorities"""
        # Schedule for next business day if configured
        submit_date = fields.Datetime.now() + timedelta(hours=1)
        cron_job = self.env['ir.cron'].create({
            'name': f'Tax Authority Submission: {self.name}',
            'model_id': self.env.ref('account.model_account_move').id,
            'code': f'env["account.move"].browse({self.id})._submit_to_tax_authorities()',
            'nextcall': submit_date,
            'interval_number': 1,
            'interval_type': 'hours',
        })
        # Note: Cron job will run independently - no need to track reference

    def _submit_to_tax_authorities(self):
        """Submit invoice to Vietnamese Tax Authorities (real-time)"""
        self.ensure_one()
        
        # Skip if Red Invoice feature is disabled
        if not self._is_red_invoice_enabled():
            return True
        
        if self.tax_authority_submission_status in ('submitted', 'accepted'):
            return True
        
        try:
            self.tax_authority_submission_status = 'pending'
            
            # Prepare invoice data for tax authority API
            invoice_data = self._prepare_tax_authority_data()
            
            # Get tax authority API configuration
            tax_api_config = self.env['ir.config_parameter'].sudo()
            api_url = tax_api_config.get_param('vietnamese_tax.api_url')
            api_key = tax_api_config.get_param('vietnamese_tax.api_key')
            
            if not api_url or not api_key:
                raise UserError(_('Vietnamese Tax Authority API not configured. Please contact administrator.'))
            
            # Submit to tax authority API (mock implementation - replace with actual API)
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {api_key}',
                'X-Company-Tax-Code': self.company_id.vat,
            }
            
            # Enhanced tax submission with retry logic
            response = self._submit_with_retry(invoice_data, headers)
            
            if response.get('success'):
                # Successful submission
                self.write({
                    'tax_authority_submission_status': 'submitted',
                    'tax_submission_date': fields.Datetime.now(),
                    'tax_submission_reference': response.get('reference_number'),
                })
                
                # Note: Cron jobs will self-manage their lifecycle
                
                # Schedule status check for final acceptance
                self._schedule_tax_submission_check()
                
                # Log successful submission for audit trail
                try:
                    self.message_post(
                        body=f"Invoice successfully submitted to Vietnamese Tax Authority. Reference: {response.get('reference_number')}",
                        subject="Tax Submission Successful"
                    )
                except Exception:
                    pass  # Silently fail - no email notifications required
                
                return True
            else:
                # Handle submission failures
                error_code = response.get('error_code', 'UNKNOWN')
                
                # Determine if we should retry or fail permanently
                if error_code in ['TIMEOUT_ERROR', 'CONNECTION_ERROR', 'HTTP_ERROR']:
                    # Temporary error - schedule retry
                    self._schedule_tax_submission_retry(response.get('error'))
                    self.write({
                        'tax_authority_submission_status': 'pending',
                        'tax_submission_error': f"Temporary error - will retry: {response.get('error')}",
                    })
                else:
                    # Permanent error - requires manual intervention
                    self.write({
                        'tax_authority_submission_status': 'error',
                        'tax_submission_error': response.get('error', 'Unknown error'),
                    })
                    
                    # Create activity for manual review
                    self._create_tax_submission_activity(response.get('error'))
                
                return False
                
        except Exception as e:
            self.write({
                'tax_authority_submission_status': 'error',
                'tax_submission_error': str(e),
            })
            return False

    def _prepare_tax_authority_data(self):
        """Prepare invoice data for Vietnamese Tax Authority submission"""
        return {
            'invoice_number': self.name,
            'invoice_date': self.invoice_date.isoformat(),
            'vietnamese_tax_code': self.vietnamese_tax_code,
            'supplier': {
                'name': self.company_id.name,
                'tax_code': self.company_id.vat,
                'address': self.company_id.street,
                'city': self.company_id.city,
            },
            'customer': {
                'name': self.partner_id.name,
                'tax_code': self.partner_id.vat,
                'cccd_number': self.customer_cccd_number,
                'address': self.partner_id.street,
                'city': self.partner_id.city,
            },
            'healthcare_service': {
                'type': self.healthcare_service_type,
                'patient_id': self.patient_id.id if self.patient_id else None,
                'service_date': self.invoice_date.isoformat(),
            },
            'lines': [{
                'description': line.name,
                'quantity': line.quantity,
                'unit_price': line.price_unit,
                'amount': line.price_subtotal,
                'tax_amount': line.price_total - line.price_subtotal,
            } for line in self.invoice_line_ids],
            'total_amount': self.amount_total,
            'tax_amount': self.amount_tax,
            'currency': self.currency_id.name,
        }

    def _vietnam_tax_authority_api(self, invoice_data, headers):
        """Real-time Vietnamese Tax Authority API integration"""
        import requests
        import json
        
        try:
            # Get tax authority API configuration
            config = self.env['ir.config_parameter'].sudo()
            api_url = config.get_param('vietnamese_tax.api_url')
            api_timeout = int(config.get_param('vietnamese_tax.api_timeout', '30'))
            
            # Primary API: General Department of Taxation (GDT) 
            gdt_endpoint = f"{api_url}/einvoice/submit"
            
            # Prepare payload for Vietnamese tax format
            payload = {
                'einvoice': {
                    'header': {
                        'invoiceType': 'healthcare_service',
                        'invoiceNumber': invoice_data['invoice_number'],
                        'invoiceDate': invoice_data['invoice_date'],
                        'currencyCode': invoice_data['currency'],
                        'companyTaxCode': invoice_data['supplier']['tax_code'],
                    },
                    'seller': {
                        'name': invoice_data['supplier']['name'],
                        'taxCode': invoice_data['supplier']['tax_code'],
                        'address': invoice_data['supplier']['address'],
                        'city': invoice_data['supplier']['city'],
                    },
                    'buyer': {
                        'name': invoice_data['customer']['name'],
                        'taxCode': invoice_data['customer']['tax_code'],
                        'cccdNumber': invoice_data['customer'].get('cccd_number'),
                        'address': invoice_data['customer']['address'],
                        'city': invoice_data['customer']['city'],
                    },
                    'items': [{
                        'description': line['description'],
                        'quantity': line['quantity'],
                        'unitPrice': line['unit_price'],
                        'amount': line['amount'],
                        'vatAmount': line['tax_amount'],
                    } for line in invoice_data['lines']],
                    'summary': {
                        'totalAmount': invoice_data['total_amount'],
                        'vatAmount': invoice_data['tax_amount'],
                        'totalPayable': invoice_data['total_amount'],
                    },
                    'healthcare': {
                        'serviceType': invoice_data['healthcare_service']['type'],
                        'patientId': invoice_data['healthcare_service']['patient_id'],
                        'serviceDate': invoice_data['healthcare_service']['service_date'],
                    }
                }
            }
            
            # Submit to Vietnamese Tax Authority
            response = requests.post(
                gdt_endpoint,
                json=payload,
                headers=headers,
                timeout=api_timeout,
                verify=True  # SSL verification for security
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('status') == 'success':
                    return {
                        'success': True,
                        'reference_number': result.get('referenceNumber'),
                        'submission_id': result.get('submissionId'),
                        'status': 'submitted',
                        'message': result.get('message', 'Invoice submitted successfully'),
                        'tracking_code': result.get('trackingCode'),
                    }
                else:
                    return {
                        'success': False,
                        'error': result.get('error', 'Submission failed'),
                        'error_code': result.get('errorCode'),
                    }
            else:
                return {
                    'success': False,
                    'error': f'HTTP {response.status_code}: {response.text}',
                    'error_code': 'HTTP_ERROR'
                }
                
        except requests.Timeout:
            return {
                'success': False,
                'error': 'Tax authority API timeout - will retry automatically',
                'error_code': 'TIMEOUT_ERROR'
            }
        except requests.ConnectionError:
            return {
                'success': False, 
                'error': 'Cannot connect to tax authority - check internet connection',
                'error_code': 'CONNECTION_ERROR'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Tax submission error: {str(e)}',
                'error_code': 'SYSTEM_ERROR'
            }
    
    def _submit_with_retry(self, invoice_data, headers):
        """Submit with automatic retry logic"""
        config = self.env['ir.config_parameter'].sudo()
        max_retries = int(config.get_param('vietnamese_tax.max_retries', '3'))
        retry_delay = int(config.get_param('vietnamese_tax.retry_delay_seconds', '60'))
        
        for attempt in range(max_retries + 1):
            response = self._mock_tax_authority_api(invoice_data, headers)
            
            # If successful or permanent error, return immediately
            if response.get('success') or response.get('error_code') not in ['TIMEOUT_ERROR', 'CONNECTION_ERROR']:
                return response
            
            # If last attempt, return the error
            if attempt == max_retries:
                return response
            
            # Wait before retry (in actual implementation, would use proper queue/cron)
            # For now, just log the retry attempt
            _logger.warning(f"Tax submission retry {attempt + 1}/{max_retries} for invoice {self.name}")
        
        return response
    
    def _schedule_tax_submission_retry(self, error_message):
        """Schedule automatic retry for failed tax submission"""
        config = self.env['ir.config_parameter'].sudo()
        retry_delay = int(config.get_param('vietnamese_tax.retry_delay_seconds', '60'))
        
        retry_date = fields.Datetime.now() + timedelta(seconds=retry_delay)
        retry_cron = self.env['ir.cron'].create({
            'name': f'Tax Submission Retry: {self.name}',
            'model_id': self.env.ref('account.model_account_move').id,
            'code': f'env["account.move"].browse({self.id})._submit_to_tax_authorities()',
            'nextcall': retry_date,
            'interval_number': 1,
            'interval_type': 'minutes',
            'priority': 5,  # High priority for tax submissions
        })
        # Retry cron job created - will run independently

        # Log retry scheduling
        try:
            self.message_post(
                body=f"Tax submission failed: {error_message}. Automatic retry scheduled in {retry_delay} seconds.",
                subject="Tax Submission Retry Scheduled"
            )
        except Exception:
            pass  # Silently fail - no email notifications required
    
    def _create_tax_submission_activity(self, error_message):
        """Create activity for manual tax submission review"""
        self.activity_schedule(
            activity_type_id=self.env.ref('mail.mail_activity_data_todo').id,
            summary='Tax Submission Failed - Manual Review Required',
            note=f'Invoice {self.name} failed tax submission with error: {error_message}\n\nPlease review and manually submit to Vietnamese Tax Authority.',
            user_id=self.env.user.id,
            date_deadline=fields.Date.today() + timedelta(days=1),
        )
        
    def _mock_tax_authority_api(self, invoice_data, headers):
        """Fallback mock API for development/testing"""
        import random
        import time
        
        # Check if we're in development mode
        config = self.env['ir.config_parameter'].sudo()
        use_mock = config.get_param('vietnamese_tax.use_mock_api', 'True') == 'True'
        
        if not use_mock:
            # Use real API when not in mock mode
            return self._vietnam_tax_authority_api(invoice_data, headers)
        
        # Simulate API processing time
        time.sleep(0.5)
        
        # Mock success response (90% success rate for demo)
        if random.random() < 0.9:
            return {
                'success': True,
                'reference_number': f"TAX{random.randint(100000, 999999)}",
                'submission_id': f"VN{random.randint(1000, 9999)}",
                'status': 'submitted',
                'message': 'Invoice submitted successfully to Vietnamese Tax Authorities (Mock)',
                'tracking_code': f"MOCK{random.randint(10000, 99999)}",
            }
        else:
            return {
                'success': False,
                'error': 'Tax authority validation failed: Invalid customer tax code (Mock)',
                'error_code': 'TAX_VALIDATION_ERROR'
            }

    def _schedule_tax_submission_check(self):
        """Schedule check of tax submission status"""
        check_date = fields.Datetime.now() + timedelta(hours=24)
        check_cron = self.env['ir.cron'].create({
            'name': f'Tax Submission Check: {self.name}',
            'model_id': self.env.ref('account.model_account_move').id,
            'code': f'env["account.move"].browse({self.id})._check_tax_submission_status()',
            'nextcall': check_date,
            'interval_number': 24,
            'interval_type': 'hours',
        })
        # Check cron job created - will run independently

    def _check_tax_submission_status(self):
        """Check status of tax authority submission"""
        self.ensure_one()
        
        if not self.tax_submission_reference:
            return
        
        # Mock status check - replace with actual API
        import random
        
        if random.random() < 0.8:  # 80% acceptance rate
            self.tax_authority_submission_status = 'accepted'
        else:
            self.tax_authority_submission_status = 'rejected'
            self.tax_submission_error = 'Tax authority rejected: Additional documentation required'
        
        # Note: Status check cron job will self-manage its lifecycle

    def _sync_to_misa(self):
        """Synchronize invoice to MISA accounting system"""
        self.ensure_one()
        
        # Skip if Red Invoice (and therefore MISA) is disabled
        if not self._is_red_invoice_enabled():
            return True
        
        if self.misa_sync_status == 'synced':
            return True
        
        try:
            self.misa_sync_status = 'syncing'
            
            # Prepare MISA data format
            misa_data = self._prepare_misa_data()
            
            # Get MISA API configuration
            misa_config = self.env['ir.config_parameter'].sudo()
            misa_url = misa_config.get_param('misa.api_url')
            misa_token = misa_config.get_param('misa.api_token')
            
            if not misa_url or not misa_token:
                self.misa_sync_status = 'not_synced'
                return False
            
            # Sync to MISA (mock implementation)
            response = self._mock_misa_sync(misa_data)
            
            if response.get('success'):
                self.write({
                    'misa_sync_status': 'synced',
                    'misa_sync_date': fields.Datetime.now(),
                    'misa_invoice_id': response.get('misa_id'),
                })
                return True
            else:
                self.write({
                    'misa_sync_status': 'sync_error',
                    'misa_sync_error': response.get('error'),
                })
                return False
                
        except Exception as e:
            self.write({
                'misa_sync_status': 'sync_error',
                'misa_sync_error': str(e),
            })
            return False

    def _prepare_misa_data(self):
        """Prepare invoice data for MISA format"""
        return {
            'RefType': 'SA',  # Sales Invoice
            'RefNo': self.name,
            'RefDate': self.invoice_date.strftime('%Y-%m-%d'),
            'CustomerID': self.partner_id.ref or self.partner_id.id,
            'CustomerName': self.partner_id.name,
            'CustomerTaxCode': self.partner_id.vat,
            'TotalAmount': self.amount_total,
            'TaxAmount': self.amount_tax,
            'Currency': self.currency_id.name,
            'HealthcareService': {
                'ServiceType': self.healthcare_service_type,
                'PatientID': self.patient_id.id if self.patient_id else None,
                'StaffHours': self.staff_time_hours,
                'EquipmentDays': self.equipment_rental_days,
            },
            'Lines': [{
                'ItemCode': line.product_id.default_code,
                'ItemName': line.product_id.name,
                'Description': line.name,
                'Quantity': line.quantity,
                'UnitPrice': line.price_unit,
                'Amount': line.price_subtotal,
            } for line in self.invoice_line_ids],
        }

    def _mock_misa_sync(self, misa_data):
        """Mock MISA synchronization - replace with actual MISA API"""
        import random
        import time
        
        time.sleep(0.3)
        
        if random.random() < 0.95:  # 95% success rate
            return {
                'success': True,
                'misa_id': f"MISA{random.randint(100000, 999999)}",
                'sync_date': fields.Datetime.now().isoformat(),
            }
        else:
            return {
                'success': False,
                'error': 'MISA connection timeout - please retry',
            }

    def action_submit_to_tax_authorities(self):
        """Manual action to submit to tax authorities"""
        if not self._is_red_invoice_enabled():
            raise UserError(_('Vietnamese Red Invoice feature is disabled. Enable it in Settings → Invoicing.'))
        
        for invoice in self:
            if invoice.state != 'posted':
                raise UserError(_('Only posted invoices can be submitted to tax authorities.'))
            
            invoice._submit_to_tax_authorities()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': _('Invoice submission to tax authorities initiated.'),
                'type': 'success',
            }
        }

    def action_sync_to_misa(self):
        """Manual action to sync with MISA"""
        for invoice in self:
            if invoice.state != 'posted':
                raise UserError(_('Only posted invoices can be synced to MISA.'))
            
            invoice._sync_to_misa()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': _('MISA synchronization initiated.'),
                'type': 'success',
            }
        }

    def action_submit_to_moh(self):
        """Submit healthcare invoice to Ministry of Health"""
        self.ensure_one()
        
        if not self.healthcare_service_type:
            raise UserError(_('Healthcare service type must be specified for MOH submission.'))
        
        # Prepare MOH submission data
        moh_data = {
            'invoice_id': self.id,
            'service_type': self.healthcare_service_type,
            'patient_info': {
                'id': self.patient_id.id if self.patient_id else None,
                'name': self.patient_id.name if self.patient_id else None,
            },
            'provider_info': {
                'name': self.company_id.name,
                'license': self.company_id.vat,
            },
            'service_details': {
                'date': self.invoice_date,
                'amount': self.amount_total,
                'staff_hours': self.staff_time_hours,
            }
        }
        
        # Mock MOH submission
        self.moh_submission_status = 'submitted'
        self.moh_submission_date = fields.Datetime.now()
        self.moh_invoice_code = f"MOH{self.id}{fields.Date.today().strftime('%Y%m')}"
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': _('Invoice submitted to Ministry of Health successfully.'),
                'type': 'success',
            }
        }

    @api.constrains('tax_authority_submission_status', 'state')
    def _check_tax_submission_requirements(self):
        """Ensure tax submission compliance"""
        # Skip entirely if Red Invoice is disabled
        if not self._is_red_invoice_enabled():
            return
        
        for invoice in self:
            if (invoice.state == 'posted' and 
                invoice.move_type in ('out_invoice', 'out_refund') and
                invoice.tax_authority_submission_status == 'draft'):
                
                # Auto-submit if configured
                company_auto_submit = self.env['ir.config_parameter'].sudo().get_param(
                    'vietnamese_tax.auto_submit', 'False'
                )
                
                if company_auto_submit == 'True':
                    invoice._submit_to_tax_authorities()

    def action_process_payment(self):
        """Launch payment processing wizard from invoice form"""
        self.ensure_one()
        
        if self.state != 'posted':
            raise UserError(_('Only posted invoices can be processed for payment.'))
        
        if self.payment_state in ['paid', 'in_payment']:
            raise UserError(_('This invoice is already paid or in payment process.'))
        
        # Launch the payment workflow wizard
        return {
            'type': 'ir.actions.act_window',
            'name': _('Process Payment'),
            'res_model': 'health.payment.workflow.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_invoice_id': self.id,
                'default_fso_id': self.fieldservice_order_id.id if self.fieldservice_order_id else False,
                'default_amount': self.amount_residual,
                'default_partner_id': self.partner_id.id,
            }
        }

    def action_post(self):
        """Override to check CRMv2 hard accounting rules (warning only)."""
        result = super().action_post()
        for move in self:
            warnings = move._check_healthcare_posting_rules()
            if warnings:
                warning_text = '<br/>'.join(warnings)
                move.message_post(
                    body=f'⚠️ <b>CRMv2 Posting Rule Warning</b><br/>{warning_text}',
                    subject='Posting Rule Warning',
                    message_type='notification',
                )
        return result

    def _check_healthcare_posting_rules(self):
        """Check CRMv2 hard accounting rules. Returns list of warning messages."""
        self.ensure_one()
        warnings = []

        sr_account = self.env.ref(
            'health_invoicing.account_service_revenue', raise_if_not_found=False
        )
        ur_account = self.env.ref(
            'health_invoicing.account_unearned_revenue', raise_if_not_found=False
        )
        cit_account = self.env.ref(
            'health_invoicing.account_cash_in_transit_nurse', raise_if_not_found=False
        )
        if not sr_account:
            return warnings  # Accounts not configured — skip checks

        sr_id = sr_account.id
        ur_id = ur_account.id if ur_account else 0
        cit_id = cit_account.id if cit_account else 0

        # Collect debit/credit accounts from the move lines
        debit_account_ids = set()
        credit_account_ids = set()
        debit_account_types = set()
        credit_account_types = set()

        for line in self.line_ids:
            if line.debit > 0:
                debit_account_ids.add(line.account_id.id)
                debit_account_types.add(line.account_id.account_type)
            if line.credit > 0:
                credit_account_ids.add(line.account_id.id)
                credit_account_types.add(line.account_id.account_type)

        # Rule 4: When SR is credited, only UR, AR, or CIT may be on the debit side
        if sr_id in credit_account_ids:
            allowed_debit_types = {'asset_receivable'}  # AR
            allowed_debit_ids = {ur_id, cit_id} - {0}
            for acct_id in debit_account_ids:
                acct = self.env['account.account'].browse(acct_id)
                if acct_id not in allowed_debit_ids and acct.account_type not in allowed_debit_types:
                    warnings.append(
                        f'Rule 4: Account "{acct.name}" (type: {acct.account_type}) '
                        f'debited while Service Revenue is credited. '
                        f'Only UR, AR, or CIT should be on the debit side.'
                    )

        # Rule 8: Cash/Bank must NOT directly credit SR
        cash_types = {'asset_cash'}
        if sr_id in credit_account_ids and debit_account_types & cash_types:
            warnings.append(
                'Rule 8: Cash/Bank account is debiting while Service Revenue is credited. '
                'Cash receipt should never directly credit Service Revenue.'
            )

        return warnings

    @api.model
    def _fin_period_range(self, period, date_from=None, date_to=None):
        """Resolve a dashboard period to (date_from, date_to, label).
        None bounds mean unbounded (All Time)."""
        today = fields.Date.today()
        if period == 'today':
            return today, today, _('Today')
        if period == 'week':
            return today - timedelta(days=today.weekday()), today, _('This Week')
        if period == 'month':
            return today.replace(day=1), today, _('This Month')
        if period == 'all':
            return None, None, _('All Time')
        if period == 'custom':
            d_from = fields.Date.to_date(date_from) if date_from else None
            d_to = fields.Date.to_date(date_to) if date_to else None
            return d_from, d_to, _('Custom')
        return today.replace(day=1), today, _('This Month')

    @api.model
    def get_finance_dashboard_data(self, period='month', date_from=None, date_to=None):
        """KPIs, recent payments, invoice breakdown and revenue trend for the
        Finance Dashboard. Period-based metrics honour the selected range;
        snapshot metrics (AR / overdue / packages / pending delivery) are
        always 'as of now'."""
        today = fields.Date.today()
        d_from, d_to, range_label = self._fin_period_range(period, date_from, date_to)

        # ----- Period-bound invoice domain (by invoice_date) -----
        period_domain = [('move_type', '=', 'out_invoice')]
        if d_from:
            period_domain.append(('invoice_date', '>=', d_from))
        if d_to:
            period_domain.append(('invoice_date', '<=', d_to))

        # Revenue (period) — posted customer invoices
        posted_period = self.search(period_domain + [('state', '=', 'posted')])
        revenue = sum(posted_period.mapped('amount_total'))

        # ----- Snapshot: Outstanding AR / Overdue (as of now) -----
        open_invoices = self.search([
            ('move_type', '=', 'out_invoice'), ('state', '=', 'posted'),
            ('payment_state', 'in', ['not_paid', 'partial']),
        ])
        outstanding_ar = sum(open_invoices.mapped('amount_residual'))
        overdue_invoices = open_invoices.filtered(
            lambda inv: inv.invoice_date_due and inv.invoice_date_due < today)
        overdue_amount = sum(overdue_invoices.mapped('amount_residual'))

        # Cash collected (period)
        cash_collected = 0
        PaymentTx = self.env.get('health.payment.transaction')
        if PaymentTx is not None:
            pay_domain = [('status', 'in', ['collected', 'delivered', 'reconciled'])]
            if d_from:
                pay_domain.append(('transaction_date', '>=', fields.Datetime.to_string(
                    datetime.combine(d_from, datetime.min.time()))))
            if d_to:
                pay_domain.append(('transaction_date', '<=', fields.Datetime.to_string(
                    datetime.combine(d_to, datetime.max.time()))))
            cash_collected = sum(PaymentTx.search(pay_domain).mapped('amount'))

        # ----- Snapshot: active packages, pending delivery -----
        active_packages = 0
        packages_remaining_value = 0
        PackageModel = self.env.get('health.service.package')
        if PackageModel is not None:
            pkgs = PackageModel.search([('state', '=', 'active')])
            active_packages = len(pkgs)
            for pkg in pkgs:
                packages_remaining_value += pkg.remaining_services * pkg.price_per_service
        pending_delivery = 0
        if PaymentTx is not None:
            pending_delivery = PaymentTx.search_count([('status', '=', 'pending_delivery')])

        # Recent payments (last 10, always most-recent)
        recent_payments = []
        if PaymentTx is not None:
            payment_method_labels = dict(
                PaymentTx._fields['payment_method']._description_selection(self.env)
            )
            recent_txs = PaymentTx.search([], order='create_date desc', limit=10)
            for tx in recent_txs:
                recent_payments.append({
                    'id': tx.id,
                    'reference': tx.name or '',
                    'patient_name': tx.patient_id.name if tx.patient_id else '',
                    'amount': tx.amount,
                    'method': payment_method_labels.get(
                        tx.payment_method,
                        tx.payment_method or '',
                    ),
                    'status': tx.status or '',
                    'time_ago': self._format_time_ago(tx.create_date),
                })

        # Invoice status breakdown (period)
        all_period = self.search(period_domain)
        total_count = len(all_period) or 1
        status_map = [
            ('draft', self.env._('Draft'), lambda inv: inv.state == 'draft'),
            ('posted', self.env._('Posted'), lambda inv: inv.state == 'posted' and inv.payment_state == 'not_paid'),
            ('paid', self.env._('Paid'), lambda inv: inv.payment_state == 'paid'),
            ('partial', self.env._('Partial'), lambda inv: inv.payment_state == 'partial'),
            ('overdue', self.env._('Overdue'), lambda inv: inv.state == 'posted' and inv.payment_state in ('not_paid', 'partial') and inv.invoice_date_due and inv.invoice_date_due < today),
            ('cancelled', self.env._('Cancelled'), lambda inv: inv.state == 'cancel'),
        ]
        breakdown = []
        for status, label, filter_fn in status_map:
            count = len(all_period.filtered(filter_fn))
            breakdown.append({
                'status': status, 'label': label, 'count': count,
                'percent': round(count / total_count * 100, 1),
            })

        # Red Invoice (Viettel) counts (period) — guarded if module absent
        red_invoice = {'enabled': False, 'issued': 0, 'failed': 0, 'pending': 0, 'cancelled': 0}
        if 'red_invoice_state' in self._fields:
            red_invoice['enabled'] = self.env['ir.config_parameter'].sudo().get_param(
                'vietnamese_tax.red_invoice_enabled', 'True') == 'True'
            red_invoice['issued'] = len(posted_period.filtered(lambda m: m.red_invoice_state == 'issued'))
            red_invoice['failed'] = len(posted_period.filtered(lambda m: m.red_invoice_state == 'failed'))
            red_invoice['pending'] = len(posted_period.filtered(lambda m: m.red_invoice_state in ('pending', 'issuing')))
            red_invoice['cancelled'] = len(posted_period.filtered(lambda m: m.red_invoice_state == 'cancelled'))

        # Revenue trend — last 6 months (independent of the filter)
        revenue_trend = []
        y, m = today.year, today.month
        months = []
        for _i in range(6):
            months.append((y, m))
            m -= 1
            if m == 0:
                m, y = 12, y - 1
        months.reverse()
        for (yy, mm) in months:
            m_start = fields.Date.to_date('%04d-%02d-01' % (yy, mm))
            if mm == 12:
                nxt = fields.Date.to_date('%04d-01-01' % (yy + 1))
            else:
                nxt = fields.Date.to_date('%04d-%02d-01' % (yy, mm + 1))
            m_end = nxt - timedelta(days=1)
            rev = sum(self.search([
                ('move_type', '=', 'out_invoice'), ('state', '=', 'posted'),
                ('invoice_date', '>=', m_start), ('invoice_date', '<=', m_end),
            ]).mapped('amount_total'))
            revenue_trend.append({'label': m_start.strftime('%b'), 'revenue': rev})

        return {
            'period': period,
            'range': {
                'from': fields.Date.to_string(d_from) if d_from else None,
                'to': fields.Date.to_string(d_to) if d_to else None,
                'label': range_label,
            },
            'kpis': {
                'revenue': revenue,
                'outstanding_ar': outstanding_ar,
                'overdue_amount': overdue_amount,
                'cash_collected': cash_collected,
                'active_packages': active_packages,
                'packages_remaining_value': packages_remaining_value,
                'pending_delivery': pending_delivery,
            },
            'recent_payments': recent_payments,
            'invoice_breakdown': breakdown,
            'red_invoice': red_invoice,
            'revenue_trend': revenue_trend,
        }

    def _format_time_ago(self, dt):
        if not dt:
            return ''
        now = fields.Datetime.now()
        delta = now - dt
        minutes = int(delta.total_seconds() / 60)
        if minutes < 1:
            return self.env._('Just now')
        if minutes < 60:
            return self.env._('%s min ago', minutes)
        hours = minutes // 60
        if hours < 24:
            return self.env._('%s hr ago', hours)
        days = hours // 24
        if days < 30:
            return self.env._('%s days ago', days)
        return dt.strftime('%b %d')

    def get_invoice_header_data(self):
        """Return header data for the Finance Invoice Form OWL header."""
        self.ensure_one()
        service_type_labels = dict(
            self._fields['healthcare_service_type']._description_selection(self.env)
        )
        return {
            'name': self.name or '',
            'state': self.state,
            'payment_state': self.payment_state,
            'partner_name': self.partner_id.name if self.partner_id else '',
            'partner_phone': self.partner_id.phone if self.partner_id else '',
            'partner_email': self.partner_id.email if self.partner_id else '',
            'service_type': service_type_labels.get(self.healthcare_service_type, ''),
            'invoice_date': self.invoice_date.strftime('%d %b %Y') if self.invoice_date else '',
            'amount_total': self.amount_total,
            'amount_residual': self.amount_residual,
        }


class HealthcareInvoiceLine(models.Model):
    """Healthcare-specific invoice line extensions"""
    _inherit = 'account.move.line'

    # Healthcare service line details
    healthcare_service_category = fields.Selection([
        ('consultation', 'Medical Consultation'),
        ('treatment', 'Treatment/Procedure'),
        ('medication', 'Medication'),
        ('equipment', 'Medical Equipment'),
        ('supplies', 'Medical Supplies'),
        ('transportation', 'Medical Transportation'),
        ('staff_time', 'Professional Staff Time'),
        ('facility_usage', 'Facility Usage'),
    ], string='Healthcare Service Category')
    
    staff_member_id = fields.Many2one(
        'hr.employee',
        string='Staff Member',
        help='Healthcare staff member who provided the service'
    )
    
    service_duration_minutes = fields.Float(
        'Service Duration (Minutes)',
        help='Duration of healthcare service in minutes'
    )
    
    # Vietnamese healthcare tax classifications
    vietnamese_service_tax_code = fields.Char(
        'Vietnamese Service Tax Code',
        help='Specific tax code for healthcare service in Vietnam'
    )
    
    is_insurance_covered = fields.Boolean(
        'Insurance Covered',
        help='This line item is covered by health insurance'
    )
    
    insurance_coverage_percentage = fields.Float(
        'Insurance Coverage %',
        help='Percentage covered by insurance'
    )

    # Discount tracking and validation
    discount_reason = fields.Char(
        'Discount Reason',
        help='Mandatory reason when discount is applied'
    )

    @api.constrains('discount', 'discount_reason')
    def _check_discount_reason(self):
        """Ensure discount reason is provided when discount > 0"""
        for line in self:
            if line.discount > 0 and not (line.discount_reason and line.discount_reason.strip()):
                raise ValidationError(_(
                    'Discount reason is mandatory when applying discounts!\n\n'
                    'Line: %s\n'
                    'Discount: %.2f%%\n\n'
                    'Please provide a reason in the "Discount Reason" field.'
                ) % (line.name or 'Unnamed', line.discount))
