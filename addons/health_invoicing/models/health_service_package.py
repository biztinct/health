# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class HealthServicePackage(models.Model):
    """
    Prepaid Service Packages for Healthcare Services
    
    Allows front desk/OM to create prepaid packages for patients:
    - Physiotherapy: 7 sessions for $700
    - Blood pressure monitoring: 12 visits for $1200
    - Diabetes management: Monthly package
    """
    _name = 'health.service.package'
    _description = 'Healthcare Service Package'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'
    _rec_name = 'display_name'
    
    # Core Package Information
    name = fields.Char(
        'Package Name',
        required=True,
        readonly=True,
        tracking=True,
        help='Name for this service package (e.g., "7-Session Physiotherapy Package")'
    )
    
    display_name = fields.Char(
        'Display Name',
        compute='_compute_display_name',
        store=True
    )
    
    @api.depends('name', 'patient_id', 'total_services', 'service_type')
    def _compute_display_name(self):
        for package in self:
            if package.patient_id and package.name:
                package.display_name = f"{package.patient_id.name} - {package.name}"
            else:
                package.display_name = package.name or "New Package"
    
    # Patient and Service Information
    patient_id = fields.Many2one(
        'res.partner',
        string='Client',
        required=True,
        domain="[('is_patient', '=', True)]",
        tracking=True,
        help='client who purchased this package'
    )
    patient_phone = fields.Char('Phone', related='patient_id.phone', readonly=True)
    patient_national_id = fields.Char('National ID', related='patient_id.national_id', readonly=True)
    
    service_type = fields.Selection([
        ('physiotherapy', 'Physiotherapy'),
        ('blood_pressure_monitoring', 'Blood Pressure Monitoring'),
        ('diabetes_management', 'Diabetes Management'),
        ('home_visit', 'Home Visit'),
        ('clinic_visit', 'Clinic Visit'),
        ('consultation', 'Consultation'),
        ('emergency', 'Emergency Care'),
        ('follow_up', 'Follow-up Care'),
        ('preventive', 'Preventive Care'),
        ('rehabilitation', 'Rehabilitation'),
        ('vaccination', 'Vaccination'),
        ('diagnostic', 'Diagnostic Services'),
        ('other', 'Other Service'),
    ], string='Service Type', required=True, tracking=True,
       help='Type of healthcare service included in this package')
    
    # Package Quantities and Pricing
    total_services = fields.Integer(
        'Total Services',
        required=True,
        default=1,
        tracking=True,
        help='Total number of services included in this package'
    )
    
    consumed_services = fields.Integer(
        'Services Used',
        default=0,
        tracking=True,
        help='Number of services already consumed from this package'
    )
    
    remaining_services = fields.Integer(
        'Services Remaining',
        compute='_compute_remaining_services',
        store=True,
        help='Services remaining in this package'
    )
    
    @api.depends('total_services', 'consumed_services')
    def _compute_remaining_services(self):
        for package in self:
            package.remaining_services = package.total_services - package.consumed_services
    
    # Pricing Information
    package_price = fields.Monetary(
        'Package Price',
        currency_field='currency_id',
        required=True,
        tracking=True,
        help='Total price paid for this package'
    )
    
    price_per_service = fields.Monetary(
        'Price Per Service',
        currency_field='currency_id',
        compute='_compute_price_per_service',
        store=True,
        help='Calculated price per individual service'
    )
    
    @api.depends('package_price', 'total_services')
    def _compute_price_per_service(self):
        for package in self:
            if package.total_services > 0:
                package.price_per_service = package.package_price / package.total_services
            else:
                package.price_per_service = 0.0
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
        required=True
    )
    
    # Package Status and Lifecycle
    state = fields.Selection([
        ('active', 'Active'),
        ('exhausted', 'Services Exhausted'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
    ], string='Status', default='active', tracking=True,
       help='Current status of this service package')
    
    # Dates and Expiration
    purchase_date = fields.Datetime(
        'Purchase Date',
        default=fields.Datetime.now,
        required=True,
        tracking=True,
        help='Date when this package was purchased'
    )
    
    expiration_date = fields.Date(
        'Expiration Date',
        help='Optional expiration date for this package'
    )
    
    # Invoice Integration
    invoice_id = fields.Many2one(
        'account.move',
        string='Prepaid Invoice',
        help='Invoice generated when this package was purchased'
    )
    
    # Product Integration
    product_template_id = fields.Many2one(
        'product.template',
        string='Package Product Template',
        domain="[('type', '=', 'healthcare_package')]",
        help='Product template this package is based on'
    )
    
    invoice_line_id = fields.Many2one(
        'account.move.line',
        string='Invoice Line',
        help='Invoice line that created this package instance'
    )
    
    # Package Notes (Manual Flexibility as Requested)
    package_notes = fields.Text(
        'Package Notes',
        help='Manual notes about this package - service details, special conditions, etc.'
    )
    
    # Service Consumption Tracking (Using FSOs directly via M2M)
    fso_ids = fields.Many2many(
        'health.fieldservice.order',
        'health_fso_package_rel',
        'package_id',
        'fso_id',
        string='Service Orders',
        help='Bookings linked to this package'
    )
    
    consumption_count = fields.Integer(
        'Service Orders',
        compute='_compute_consumption_count',
        help='Number of FSOs that consumed from this package'
    )
    
    booking_count = fields.Integer(
        'Bookings',
        compute='_compute_booking_count',
        help='Number of FSO bookings linked to this package'
    )
    
    # Legacy field for backward compatibility (will be removed)
    consumption_ids = fields.One2many(
        'health.prepaid.service',
        'package_id',
        string='Service Consumption (DEPRECATED)',
        help='Legacy consumption records - use fso_ids instead'
    )
    
    @api.depends('fso_ids')
    def _compute_consumption_count(self):
        for package in self:
            package.consumption_count = len(package.fso_ids)
    
    def _compute_booking_count(self):
        for package in self:
            package.booking_count = len(package.fso_ids)
    
    # Constraints and Validations
    @api.constrains('total_services', 'consumed_services')
    def _check_service_counts(self):
        for package in self:
            if package.total_services < 1:
                raise ValidationError(_('Total services must be at least 1.'))
            if package.consumed_services < 0:
                raise ValidationError(_('Consumed services cannot be negative.'))
            if package.consumed_services > package.total_services:
                raise ValidationError(_('Cannot consume more services than available in package.'))
    
    @api.constrains('package_price')
    def _check_package_price(self):
        for package in self:
            if package.package_price <= 0:
                raise ValidationError(_('Package price must be positive.'))
    
    # Product Integration Methods
    @api.onchange('product_template_id')
    def _onchange_product_template_id(self):
        """Auto-populate package details from selected product template"""
        if self.product_template_id:
            template = self.product_template_id
            
            # Only auto-populate if fields are empty (don't overwrite user changes)
            if not self.name or self.name == 'New Package':
                self.name = template.name
            
            if not self.service_type:
                self.service_type = template.healthcare_package_type
                
            if not self.total_services:
                self.total_services = template.healthcare_service_count
                
            if not self.package_price:
                self.package_price = template.list_price
                
            if not self.package_notes:
                self.package_notes = template.healthcare_terms or f"Package based on product: {template.name}"
                
            if not self.expiration_date and template.healthcare_package_duration:
                self.expiration_date = fields.Date.add(fields.Date.today(), weeks=template.healthcare_package_duration)
    
    @api.model_create_multi
    def create(self, vals_list):
        """Auto-populate from product template on creation"""
        for vals in vals_list:
            if vals.get('product_template_id'):
                template = self.env['product.template'].browse(vals['product_template_id'])
                
                # Auto-populate missing fields from template
                if not vals.get('name'):
                    patient_name = ""
                    if vals.get('patient_id'):
                        patient = self.env['res.partner'].browse(vals['patient_id'])
                        patient_name = f" - {patient.name}"
                    vals['name'] = f"{template.name}{patient_name}"
                
                if not vals.get('service_type'):
                    vals['service_type'] = template.healthcare_package_type
                
                if not vals.get('total_services'):
                    vals['total_services'] = template.healthcare_service_count
                    
                if not vals.get('package_price'):
                    vals['package_price'] = template.list_price
                    
                if not vals.get('package_notes'):
                    vals['package_notes'] = template.healthcare_terms or f"Package based on product: {template.name}"
                    
                if not vals.get('expiration_date') and template.healthcare_package_duration:
                    vals['expiration_date'] = fields.Date.add(fields.Date.today(), weeks=template.healthcare_package_duration)
        
        return super().create(vals_list)
    
    # Business Logic Methods
    def action_consume_service_legacy(self, fso_id=None, quantity=1):
        """DEPRECATED: Legacy method for consuming services (now handled by FSO completion)"""
        self.ensure_one()
        
        if self.state != 'active':
            raise UserError(_('Cannot consume services from inactive package.'))
        
        if self.remaining_services < quantity:
            raise UserError(_('Not enough services remaining in package.'))
        
        # Direct consumption without creating separate consumption record
        self.consumed_services += quantity
        
        # Check if package is exhausted
        if self.remaining_services == 0:
            self.state = 'exhausted'
            try:
                self.message_post(
                    body=f"Package exhausted - all {self.total_services} services have been used.",
                    subject="Package Services Exhausted"
                )
            except Exception:
                pass  # Silently fail - no email notifications required

        # Log the consumption
        try:
            self.message_post(
                body=f"Manual service consumption: {quantity} service(s) consumed from package.",
                subject="Manual Service Consumption"
            )
        except Exception:
            pass  # Silently fail - no email notifications required
        
        return True
    
    def action_view_consumptions(self):
        """View service orders that consumed from this package"""
        self.ensure_one()
        return {
            'name': _('Service Orders - Package Consumption'),
            'type': 'ir.actions.act_window',
            'res_model': 'health.fieldservice.order',
            'domain': [('package_ids', 'in', [self.id])],
            'view_mode': 'list,form',
            'target': 'current',
            'context': {'default_patient_id': self.patient_id.id}
        }
    
    def action_refund_package(self):
        """Process refund for unused services"""
        self.ensure_one()
        
        if self.remaining_services <= 0:
            raise UserError(_('No services remaining to refund.'))
        
        refund_amount = self.remaining_services * self.price_per_service
        
        # Create refund invoice (credit note)
        refund_invoice = self.env['account.move'].create({
            'move_type': 'out_refund',
            'partner_id': self.patient_id.id,
            'invoice_origin': f'Refund: {self.name}',
            'invoice_line_ids': [(0, 0, {
                'name': f'Refund for {self.remaining_services} unused services - {self.name}',
                'quantity': self.remaining_services,
                'price_unit': self.price_per_service,
            })],
        })
        
        self.state = 'refunded'
        try:
            self.message_post(
                body=f"Package refunded for {self.remaining_services} unused services. Refund amount: {refund_amount}",
                subject="Package Refunded"
            )
        except Exception:
            pass  # Silently fail - no email notifications required
        
        return {
            'name': _('Refund Invoice'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': refund_invoice.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def action_create_booking(self):
        """Create FSO booking from this package"""
        self.ensure_one()
        
        if self.state != 'active':
            raise UserError(_('Cannot create bookings for inactive packages.'))
        
        if self.remaining_services <= 0:
            raise UserError(_('No remaining services in this package to book.'))
        
        # Map package service types to FSO service types
        service_type_mapping = {
            'physiotherapy': 'rehabilitation',
            'blood_pressure_monitoring': 'diagnostic', 
            'diabetes_management': 'follow_up',
            'home_visit': 'home_visit',
            'clinic_visit': 'clinic_visit',
            'consultation': 'consultation',
            'emergency': 'emergency',
            'follow_up': 'follow_up',
            'preventive': 'preventive',
            'rehabilitation': 'rehabilitation',
            'vaccination': 'vaccination',
            'diagnostic': 'diagnostic',
            'other': 'consultation',  # Default mapping for 'other'
        }
        
        mapped_service_type = service_type_mapping.get(self.service_type, 'consultation')
        
        return {
            'name': _('Create Service Booking'),
            'type': 'ir.actions.act_window',
            'res_model': 'health.fieldservice.order',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_patient_id': self.patient_id.id,
                'default_package_id': self.id,
                'default_service_type': mapped_service_type,
                'default_service_category': 'medical',  # Default category
                'create_from_package': True,
            }
        }
    
    def action_view_bookings(self):
        """View all FSO bookings linked to this package"""
        self.ensure_one()
        
        return {
            'name': _('Package Bookings'),
            'type': 'ir.actions.act_window',
            'res_model': 'health.fieldservice.order',
            'domain': [('package_ids', 'in', [self.id])],
            'view_mode': 'list,form',
            'target': 'current',
            'context': {
                'default_patient_id': self.patient_id.id,
            }
        }