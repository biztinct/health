# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import json
import requests
from datetime import datetime


class MISAIntegration(models.Model):
    """
    MISA Accounting System Integration
    
    FROM CLIENT REQUIREMENTS (Invoicing.md):
    - MISA is the Vietnamese accounting software standard
    - Real-time synchronization of invoices and payments
    - Vietnamese tax compliance through MISA
    - Healthcare-specific accounting categories
    """
    _name = 'misa.integration'
    _description = 'MISA Accounting Integration'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    active = fields.Boolean('Active', default=True, tracking=True)

    name = fields.Char(
        'Integration Name',
        required=True,
        default='MISA Integration'
    )
    
    # MISA connection configuration
    misa_server_url = fields.Char(
        'MISA Server URL',
        required=True,
        help='MISA accounting system server URL'
    )
    
    misa_database_name = fields.Char(
        'MISA Database Name',
        required=True,
        help='MISA database name for this company'
    )
    
    misa_username = fields.Char(
        'MISA Username',
        required=True,
        help='Username for MISA system access'
    )
    
    misa_password = fields.Char(
        'MISA Password',
        help='Password for MISA system access'
    )
    
    misa_api_key = fields.Char(
        'MISA API Key',
        help='API key for MISA integration'
    )
    
    # Integration status
    connection_status = fields.Selection([
        ('disconnected', 'Disconnected'),
        ('connecting', 'Connecting'),
        ('connected', 'Connected'),
        ('error', 'Connection Error'),
    ], string='Connection Status', default='disconnected', tracking=True)
    
    last_sync_date = fields.Datetime(
        'Last Sync Date',
        help='Date of last successful synchronization'
    )
    
    sync_frequency = fields.Selection([
        ('manual', 'Manual'),
        ('hourly', 'Hourly'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
    ], string='Sync Frequency', default='daily',
       help='How often to sync with MISA')
    
    auto_sync_enabled = fields.Boolean(
        'Auto Sync Enabled',
        default=True,
        help='Enable automatic synchronization with MISA'
    )
    
    # Vietnamese healthcare-specific mappings
    healthcare_account_mappings = fields.Text(
        'Healthcare Account Mappings',
        help='JSON mapping of healthcare services to MISA account codes'
    )
    
    vietnamese_tax_mappings = fields.Text(
        'Vietnamese Tax Mappings',
        help='JSON mapping of tax codes between Odoo and MISA'
    )
    
    # Sync statistics
    total_invoices_synced = fields.Integer(
        'Total Invoices Synced',
        default=0,
        help='Total number of invoices synchronized to MISA'
    )
    
    total_payments_synced = fields.Integer(
        'Total Payments Synced', 
        default=0,
        help='Total number of payments synchronized to MISA'
    )
    
    sync_errors_count = fields.Integer(
        'Sync Errors Count',
        default=0,
        help='Number of synchronization errors'
    )
    
    # Error tracking
    last_error_message = fields.Text(
        'Last Error Message',
        help='Last synchronization error message'
    )
    
    last_error_date = fields.Datetime(
        'Last Error Date',
        help='Date of last synchronization error'
    )

    @api.model
    def get_default_healthcare_mappings(self):
        """Get default healthcare service to MISA account mappings"""
        return {
            'home_visit': '511001',  # Healthcare Services - Home Visit
            'clinic_visit': '511002',  # Healthcare Services - Clinic Visit
            'consultation': '511003',  # Healthcare Services - Consultation
            'emergency': '511004',  # Healthcare Services - Emergency
            'equipment_rental': '512001',  # Medical Equipment Rental
            'medical_supplies': '512002',  # Medical Supplies
            'staff_professional': '513001',  # Professional Staff Services
            'transportation': '514001',  # Medical Transportation
            'facility_usage': '515001',  # Healthcare Facility Usage
        }

    @api.model
    def get_default_tax_mappings(self):
        """Get default Vietnamese tax code mappings"""
        return {
            'VAT_10': 'GTGT10',  # 10% VAT in MISA
            'VAT_8': 'GTGT08',   # 8% VAT in MISA
            'VAT_5': 'GTGT05',   # 5% VAT in MISA
            'VAT_0': 'GTGT00',   # 0% VAT in MISA
            'EXEMPT': 'KGTGT',   # VAT Exempt in MISA
        }

    def action_test_connection(self):
        """Test connection to MISA system"""
        self.ensure_one()
        
        try:
            self.connection_status = 'connecting'
            
            # Test MISA connection (mock implementation)
            result = self._test_misa_connection()
            
            if result.get('success'):
                self.connection_status = 'connected'
                message = _('MISA connection successful!')
                message_type = 'success'
            else:
                self.connection_status = 'error'
                self.last_error_message = result.get('error', 'Unknown error')
                self.last_error_date = fields.Datetime.now()
                message = _('MISA connection failed: %s') % self.last_error_message
                message_type = 'danger'
                
        except Exception as e:
            self.connection_status = 'error'
            self.last_error_message = str(e)
            self.last_error_date = fields.Datetime.now()
            message = _('MISA connection error: %s') % str(e)
            message_type = 'danger'
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': message,
                'type': message_type,
            }
        }

    def _test_misa_connection(self):
        """Test connection to MISA API (mock implementation)"""
        # Mock MISA connection test
        # In production, this would connect to actual MISA API
        
        if not self.misa_server_url or not self.misa_username:
            return {'success': False, 'error': 'Missing MISA connection parameters'}
        
        # Simulate connection test
        import random
        if random.random() > 0.1:  # 90% success rate for demo
            return {
                'success': True,
                'version': 'MISA eInvoice 2023.1',
                'database': self.misa_database_name,
            }
        else:
            return {
                'success': False,
                'error': 'MISA server not responding - please check network connection'
            }

    def action_sync_all_invoices(self):
        """Manually sync all pending invoices to MISA"""
        self.ensure_one()
        
        if self.connection_status != 'connected':
            raise UserError(_('MISA connection must be established before syncing.'))
        
        # Find invoices that need syncing
        pending_invoices = self.env['account.move'].search([
            ('state', '=', 'posted'),
            ('move_type', 'in', ('out_invoice', 'out_refund')),
            ('misa_sync_status', 'in', ('not_synced', 'sync_error')),
        ])
        
        success_count = 0
        error_count = 0
        
        for invoice in pending_invoices:
            try:
                if invoice._sync_to_misa():
                    success_count += 1
                else:
                    error_count += 1
            except Exception as e:
                error_count += 1
                invoice.misa_sync_error = str(e)
        
        self.total_invoices_synced += success_count
        self.sync_errors_count += error_count
        self.last_sync_date = fields.Datetime.now()
        
        message = _('MISA sync completed: %d invoices synced, %d errors') % (success_count, error_count)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': message,
                'type': 'success' if error_count == 0 else 'warning',
            }
        }

    def action_sync_all_payments(self):
        """Manually sync all pending payments to MISA"""
        self.ensure_one()
        
        if self.connection_status != 'connected':
            raise UserError(_('MISA connection must be established before syncing.'))
        
        # Find payments that need syncing 
        pending_payments = self.env['account.payment'].search([
            ('state', '=', 'posted'),
            ('healthcare_payment_type', '!=', False),
            ('vietnamese_receipt_number', '!=', False),
        ])
        
        success_count = 0
        error_count = 0
        
        for payment in pending_payments:
            try:
                if self._sync_payment_to_misa(payment):
                    success_count += 1
                else:
                    error_count += 1
            except Exception as e:
                error_count += 1
        
        self.total_payments_synced += success_count
        self.sync_errors_count += error_count
        self.last_sync_date = fields.Datetime.now()
        
        message = _('MISA payment sync completed: %d payments synced, %d errors') % (success_count, error_count)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': message,
                'type': 'success' if error_count == 0 else 'warning',
            }
        }

    def _sync_payment_to_misa(self, payment):
        """Sync individual payment to MISA"""
        try:
            # Prepare MISA payment data
            misa_payment_data = {
                'RefType': 'RC',  # Receipt
                'RefNo': payment.name,
                'RefDate': payment.date.strftime('%Y-%m-%d'),
                'CustomerID': payment.partner_id.ref or payment.partner_id.id,
                'CustomerName': payment.partner_id.name,
                'Amount': payment.amount,
                'Currency': payment.currency_id.name,
                'PaymentMethod': payment.vietnamese_payment_method or 'cash_vnd',
                'VietnameseReceiptNo': payment.vietnamese_receipt_number,
                'HealthcareType': payment.healthcare_payment_type,
                'PatientID': payment.patient_id.id if payment.patient_id else None,
            }
            
            # Mock MISA payment sync
            result = self._mock_misa_payment_sync(misa_payment_data)
            
            return result.get('success', False)
            
        except Exception as e:
            return False

    def _mock_misa_payment_sync(self, payment_data):
        """Mock MISA payment sync - replace with actual MISA API"""
        import random
        import time
        
        time.sleep(0.2)  # Simulate API call
        
        if random.random() > 0.05:  # 95% success rate
            return {
                'success': True,
                'misa_id': f"MISARC{random.randint(100000, 999999)}",
            }
        else:
            return {
                'success': False,
                'error': 'MISA payment validation failed'
            }

    def action_setup_healthcare_mappings(self):
        """Setup default healthcare account mappings for MISA"""
        self.ensure_one()
        
        default_mappings = self.get_default_healthcare_mappings()
        self.healthcare_account_mappings = json.dumps(default_mappings, indent=2)
        
        default_tax_mappings = self.get_default_tax_mappings()
        self.vietnamese_tax_mappings = json.dumps(default_tax_mappings, indent=2)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': _('Healthcare account mappings configured successfully.'),
                'type': 'success',
            }
        }

    def get_misa_account_code(self, healthcare_service_type):
        """Get MISA account code for healthcare service type"""
        if not self.healthcare_account_mappings:
            self.action_setup_healthcare_mappings()
        
        try:
            mappings = json.loads(self.healthcare_account_mappings)
            return mappings.get(healthcare_service_type, '511000')  # Default healthcare account
        except:
            return '511000'  # Default fallback

    def get_misa_tax_code(self, odoo_tax_code):
        """Get MISA tax code for Odoo tax code"""
        if not self.vietnamese_tax_mappings:
            self.action_setup_healthcare_mappings()
        
        try:
            mappings = json.loads(self.vietnamese_tax_mappings)
            return mappings.get(odoo_tax_code, 'GTGT10')  # Default 10% VAT
        except:
            return 'GTGT10'  # Default fallback

    @api.model
    def cron_auto_sync_misa(self):
        """Cron job for automatic MISA synchronization"""
        active_integrations = self.search([
            ('auto_sync_enabled', '=', True),
            ('connection_status', '=', 'connected'),
        ])
        
        for integration in active_integrations:
            try:
                integration.action_sync_all_invoices()
                integration.action_sync_all_payments()
            except Exception as e:
                integration.last_error_message = str(e)
                integration.last_error_date = fields.Datetime.now()
                integration.sync_errors_count += 1


class MISASyncLog(models.Model):
    """MISA synchronization log for tracking"""
    _name = 'misa.sync.log'
    _description = 'MISA Sync Log'
    _order = 'create_date desc'

    active = fields.Boolean('Active', default=True)

    name = fields.Char(
        'Log Entry',
        required=True
    )
    
    sync_type = fields.Selection([
        ('invoice', 'Invoice Sync'),
        ('payment', 'Payment Sync'),
        ('customer', 'Customer Sync'),
        ('product', 'Product Sync'),
    ], string='Sync Type', required=True)
    
    record_model = fields.Char(
        'Record Model',
        help='Odoo model being synced'
    )
    
    record_id = fields.Integer(
        'Record ID',
        help='ID of record being synced'
    )
    
    misa_id = fields.Char(
        'MISA ID',
        help='ID assigned in MISA system'
    )
    
    sync_status = fields.Selection([
        ('success', 'Success'),
        ('error', 'Error'),
        ('warning', 'Warning'),
    ], string='Sync Status', required=True)
    
    error_message = fields.Text(
        'Error Message',
        help='Error message if sync failed'
    )
    
    sync_date = fields.Datetime(
        'Sync Date',
        default=fields.Datetime.now,
        required=True
    )
    
    integration_id = fields.Many2one(
        'misa.integration',
        string='MISA Integration',
        required=True
    )
