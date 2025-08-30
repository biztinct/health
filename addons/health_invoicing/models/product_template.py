# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    """
    Enhance Product Template to support Healthcare Service Packages
    
    This allows healthcare packages to be treated as regular products that can:
    - Be added to invoices alongside syringes, bandages, etc.
    - Use standard Odoo product features (pricing, taxes, discounts)
    - Be managed in the standard product catalog
    - Support package-specific fields (visit count, service type, etc.)
    """
    _inherit = 'product.template'
    
    # Enhanced Product Type Selection
    type = fields.Selection(
        selection_add=[('healthcare_package', 'Healthcare Package')],
        ondelete={'healthcare_package': 'cascade'},
        help="Healthcare Package: Prepaid service packages with visit/session tracking"
    )
    
    # Healthcare Package Configuration
    healthcare_package_type = fields.Selection([
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
    ], string='Package Service Type',
       help='Type of healthcare service included in this package')
    
    healthcare_service_count = fields.Integer(
        'Number of Services/Visits',
        default=1,
        help='Total number of services or visits included in this package'
    )
    
    healthcare_price_per_visit = fields.Monetary(
        'Price Per Service',
        currency_field='currency_id',
        compute='_compute_healthcare_price_per_visit',
        store=True,
        help='Calculated price per individual service/visit'
    )
    
    healthcare_service_location = fields.Selection([
        ('home', 'Patient Home'),
        ('clinic', 'Clinic Visit'),
        ('remote', 'Remote/Telemedicine'),
        ('flexible', 'Flexible Location'),
    ], string='Service Location',
       default='flexible',
       help='Where services in this package are typically delivered')
    
    healthcare_package_duration = fields.Integer(
        'Package Duration (Weeks)',
        default=12,
        help='Validity period for this package in weeks'
    )
    
    healthcare_terms = fields.Text(
        'Package Terms & Conditions',
        help='Terms, conditions, and service details for this package'
    )
    
    # Computed Fields
    is_healthcare_package = fields.Boolean(
        'Is Healthcare Package',
        compute='_compute_is_healthcare_package',
        store=True,
        help='True if this product is a healthcare service package'
    )
    
    healthcare_package_instances_count = fields.Integer(
        'Active Package Instances',
        compute='_compute_healthcare_package_instances_count',
        help='Number of active patient package instances for this product'
    )
    
    @api.depends('type')
    def _compute_is_healthcare_package(self):
        for product in self:
            product.is_healthcare_package = (product.type == 'healthcare_package')
    
    @api.depends('list_price', 'healthcare_service_count')
    def _compute_healthcare_price_per_visit(self):
        for product in self:
            if product.is_healthcare_package and product.healthcare_service_count > 0:
                product.healthcare_price_per_visit = product.list_price / product.healthcare_service_count
            else:
                product.healthcare_price_per_visit = 0.0
    
    def _compute_healthcare_package_instances_count(self):
        for product in self:
            if product.is_healthcare_package:
                product.healthcare_package_instances_count = self.env['health.service.package'].search_count([
                    ('product_template_id', '=', product.id),
                    ('state', 'in', ['active', 'exhausted'])
                ])
            else:
                product.healthcare_package_instances_count = 0
    
    # Constraints and Validations
    @api.constrains('healthcare_service_count', 'list_price')
    def _check_healthcare_package_values(self):
        for product in self:
            if product.is_healthcare_package:
                if product.healthcare_service_count < 1:
                    raise ValidationError(_('Healthcare packages must include at least 1 service/visit.'))
                if product.list_price <= 0:
                    raise ValidationError(_('Healthcare package price must be positive.'))
    
    # Onchange Methods
    @api.onchange('type')
    def _onchange_type_healthcare_package(self):
        """Set defaults when healthcare package is selected"""
        if self.type == 'healthcare_package':
            # Set healthcare package defaults if not set
            if not self.healthcare_package_type:
                self.healthcare_package_type = 'other'
            if not self.healthcare_service_count:
                self.healthcare_service_count = 1
            if not self.healthcare_package_duration:
                self.healthcare_package_duration = 12
            
            # Set service-related defaults if available
            if hasattr(self, 'invoice_policy'):
                self.invoice_policy = 'order'  # Invoice based on ordered quantity
            if hasattr(self, 'service_type'):
                self.service_type = 'manual'   # Manually set quantities
                
        elif self._origin.type == 'healthcare_package':
            # Clear healthcare fields when changing away from package
            self.healthcare_package_type = False
            self.healthcare_service_count = 0
            self.healthcare_service_location = False
            self.healthcare_package_duration = 0
            self.healthcare_terms = False
    
    # Business Logic Methods
    def action_view_package_instances(self):
        """View active package instances for this product template"""
        self.ensure_one()
        
        if not self.is_healthcare_package:
            return {'type': 'ir.actions.act_window_close'}
        
        return {
            'name': _('Package Instances'),
            'type': 'ir.actions.act_window',
            'res_model': 'health.service.package',
            'domain': [('product_template_id', '=', self.id)],
            'view_mode': 'list,form',
            'target': 'current',
            'context': {
                'default_product_template_id': self.id,
                'search_default_active': 1,
            }
        }
    
    def create_patient_package(self, patient_id, invoice_line_id=None):
        """Create a patient-specific package instance from this product template"""
        self.ensure_one()
        
        if not self.is_healthcare_package:
            raise ValidationError(_('Cannot create package instance from non-package product.'))
        
        if not patient_id:
            raise ValidationError(_('Patient is required to create package instance.'))
        
        # Create package instance with template data
        package_vals = {
            'name': f"{self.name} - {self.env['res.partner'].browse(patient_id).name}",
            'product_template_id': self.id,
            'patient_id': patient_id,
            'service_type': self.healthcare_package_type,
            'total_services': self.healthcare_service_count,
            'package_price': self.list_price,
            'expiration_date': fields.Date.add(fields.Date.today(), weeks=self.healthcare_package_duration) if self.healthcare_package_duration else False,
            'package_notes': self.healthcare_terms or f"Package based on product: {self.name}",
            'state': 'active',
        }
        
        if invoice_line_id:
            package_vals['invoice_line_id'] = invoice_line_id
        
        package = self.env['health.service.package'].create(package_vals)
        
        return package
    
    # Override standard methods for healthcare packages
    def write(self, vals):
        """Update existing package instances when template changes"""
        result = super().write(vals)
        
        # If this is a healthcare package and key fields changed, log message
        healthcare_fields = ['healthcare_service_count', 'healthcare_package_type', 'list_price']
        if any(field in vals for field in healthcare_fields):
            for product in self.filtered('is_healthcare_package'):
                active_packages = self.env['health.service.package'].search([
                    ('product_template_id', '=', product.id),
                    ('state', '=', 'active')
                ])
                
                if active_packages:
                    product.message_post(
                        body=f"Template updated. {len(active_packages)} active package instances may be affected. "
                             f"Consider reviewing patient packages for consistency.",
                        subject="Healthcare Package Template Updated"
                    )
        
        return result