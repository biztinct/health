# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import datetime, timedelta


class HealthcareServiceBilling(models.Model):
    """
    Healthcare Service Billing Integration
    
    FROM CLIENT REQUIREMENTS:
    - Auto-invoice creation from Field Service Orders (FSO)
    - Appointment-based billing workflow
    - Healthcare-specific billing rules and rates
    - Insurance claim processing integration
    """
    _name = 'health.service.billing'
    _description = 'Healthcare Service Billing'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    active = fields.Boolean('Active', default=True, tracking=True)

    name = fields.Char(
        'Billing Reference',
        required=True,
        default=lambda self: _('New Billing')
    )
    
    # Source service records
    fieldservice_order_id = fields.Many2one(
        'health.fieldservice.order',
        string='Booking',
        help='FSO that generated this billing'
    )
    
    appointment_id = fields.Many2one(
        'health.appointment',
        string='Appointment',
        help='Appointment that generated this billing'
    )
    
    # Patient and customer information
    patient_id = fields.Many2one(
        'res.partner',
        string='Client',
        domain=[('is_patient', '=', True)],
        required=True,
        help='client receiving the service'
    )
    
    customer_id = fields.Many2one(
        'res.partner',
        string='Customer',
        required=True,
        help='client)'
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
                 'patient_id.catchment_province_id',
                 'patient_id.primary_facility_id.catchment_province_id',
                 'customer_id.catchment_province_id',
                 'customer_id.primary_facility_id.catchment_province_id')
    def _compute_catchment_province_id(self):
        for billing in self:
            patient_catchment = billing.patient_id._get_health_catchment_province() if billing.patient_id else False
            customer_catchment = billing.customer_id._get_health_catchment_province() if billing.customer_id else False
            billing.catchment_province_id = (
                billing.fieldservice_order_id.catchment_province_id
                or patient_catchment
                or customer_catchment
                or False
            )
    
    # Service details
    service_type = fields.Selection([
        ('home_visit', 'Home Visit'),
        ('clinic_visit', 'Clinic Visit'),
        ('consultation', 'Consultation'),
        ('emergency', 'Emergency Care'),
        ('follow_up', 'Follow-up Care'),
        ('preventive', 'Preventive Care'),
        ('rehabilitation', 'Rehabilitation'),
        ('equipment_rental', 'Equipment Rental'),
        ('supplies', 'Medical Supplies'),
    ], string='Service Type', required=True)
    
    service_date = fields.Datetime(
        'Service Date',
        required=True,
        default=fields.Datetime.now
    )
    
    service_duration_hours = fields.Float(
        'Service Duration (Hours)',
        help='Total duration of healthcare service'
    )
    
    # Billing amounts
    base_service_amount = fields.Monetary(
        'Base Service Amount',
        required=True,
        help='Base amount for the healthcare service'
    )
    
    equipment_rental_amount = fields.Monetary(
        'Equipment Rental Amount',
        help='Amount for equipment rental'
    )
    
    supplies_amount = fields.Monetary(
        'Medical Supplies Amount',
        help='Amount for medical supplies used'
    )
    
    travel_expense_amount = fields.Monetary(
        'Travel Expenses',
        help='Travel expenses for home visits'
    )
    
    urgency_surcharge_amount = fields.Monetary(
        'Urgency Surcharge',
        help='Additional charge for urgent/emergency services'
    )
    
    total_amount = fields.Monetary(
        'Total Amount',
        compute='_compute_total_amount',
        store=True,
        help='Total billing amount'
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id
    )
    
    # Insurance processing
    has_insurance = fields.Boolean(
        'Has Insurance Coverage',
        help='client has insurance coverage for this service'
    )
    
    insurance_provider_id = fields.Many2one(
        'res.partner',
        string='Insurance Provider',
        domain=[('is_company', '=', True)]
    )
    
    insurance_coverage_percentage = fields.Float(
        'Insurance Coverage %',
        help='Percentage covered by insurance'
    )
    
    insurance_covered_amount = fields.Monetary(
        'Insurance Covered Amount',
        compute='_compute_insurance_amounts',
        store=True
    )
    
    patient_responsibility_amount = fields.Monetary(
        'Patient Responsibility',
        compute='_compute_insurance_amounts',
        store=True
    )
    
    # Billing status
    billing_status = fields.Selection([
        ('draft', 'Draft'),
        ('ready_to_invoice', 'Ready to Invoice'),
        ('invoiced', 'Invoiced'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled'),
    ], string='Billing Status', default='draft', tracking=True)
    
    # Generated invoice
    invoice_id = fields.Many2one(
        'account.move',
        string='Generated Invoice',
        help='Invoice generated from this billing'
    )
    
    invoice_date = fields.Date(
        'Invoice Date',
        help='Date when invoice was generated'
    )
    
    # Staff tracking
    staff_ids = fields.Many2many(
        'hr.employee',
        string='Staff Members',
        help='Healthcare staff involved in service delivery'
    )
    
    equipment_description = fields.Text(
        'Equipment Used',
        help='Description of medical equipment used during service'
    )
    
    # Time tracking for staff billing
    staff_time_ids = fields.One2many(
        'health.staff.time.tracking',
        'billing_id',
        string='Staff Time Tracking'
    )
    
    # Service location
    service_location = fields.Selection([
        ('patient_home', 'Patient Home'),
        ('clinic', 'Clinic'),
        ('hospital', 'Hospital'),
        ('nursing_home', 'Nursing Home'),
        ('other', 'Other Location'),
    ], string='Service Location', required=True)
    
    service_address = fields.Text(
        'Service Address',
        help='Address where service was provided'
    )
    
    travel_distance_km = fields.Float(
        'Travel Distance (km)',
        help='Distance traveled for home visits'
    )
    
    # Vietnamese compliance fields
    vietnamese_service_code = fields.Char(
        'Vietnamese Service Code',
        help='Official Vietnamese healthcare service code'
    )
    
    moh_reporting_required = fields.Boolean(
        'MOH Reporting Required',
        help='Service requires Ministry of Health reporting'
    )

    @api.depends('base_service_amount', 'equipment_rental_amount', 'supplies_amount', 
                 'travel_expense_amount', 'urgency_surcharge_amount')
    def _compute_total_amount(self):
        """Compute total billing amount"""
        for billing in self:
            billing.total_amount = (
                billing.base_service_amount +
                billing.equipment_rental_amount + 
                billing.supplies_amount +
                billing.travel_expense_amount +
                billing.urgency_surcharge_amount
            )

    @api.depends('total_amount', 'insurance_coverage_percentage')
    def _compute_insurance_amounts(self):
        """Compute insurance coverage and patient responsibility amounts"""
        for billing in self:
            if billing.has_insurance and billing.insurance_coverage_percentage:
                billing.insurance_covered_amount = billing.total_amount * (billing.insurance_coverage_percentage / 100)
                billing.patient_responsibility_amount = billing.total_amount - billing.insurance_covered_amount
            else:
                billing.insurance_covered_amount = 0.0
                billing.patient_responsibility_amount = billing.total_amount

    @api.model
    def create_from_fieldservice_order(self, fso_id):
        """Create billing record from Field Service Order"""
        fso = self.env['health.fieldservice.order'].browse(fso_id)
        
        if not fso:
            raise UserError(_('Booking not found.'))
        
        # Calculate service amounts based on FSO
        billing_vals = {
            'name': f'Billing - {fso.name}',
            'fieldservice_order_id': fso.id,
            'patient_id': fso.patient_id.id,
            'customer_id': fso.customer_id.id if fso.customer_id else fso.patient_id.id,
            'service_type': fso.service_type or 'home_visit',
            'service_date': fso.scheduled_date,
            'service_duration_hours': fso.estimated_duration,
            'service_location': 'patient_home' if fso.service_type == 'home_visit' else 'clinic',
            'service_address': fso.service_address,
            'travel_distance_km': fso.travel_distance,
            'staff_ids': [(6, 0, fso.assigned_staff_ids.ids)],
            'equipment_description': ', '.join(fso.required_equipment_ids.mapped('name')) or 'Standard medical equipment',
        }
        
        # Calculate amounts
        billing_vals.update(self._calculate_fso_amounts(fso))
        
        # Check insurance
        if hasattr(fso.patient_id, 'has_health_insurance') and fso.patient_id.has_health_insurance:
            billing_vals.update({
                'has_insurance': True,
                'insurance_provider_id': fso.patient_id.insurance_provider_id.id if fso.patient_id.insurance_provider_id else False,
                'insurance_coverage_percentage': fso.patient_id.insurance_coverage_percentage or 0.0,
            })
        
        billing = self.create(billing_vals)
        
        # Create staff time tracking entries
        self._create_staff_time_tracking(billing, fso)
        
        return billing

    def _calculate_fso_amounts(self, fso):
        """Calculate billing amounts from FSO"""
        amounts = {}
        
        # Base service amount - get from service type pricing
        service_product = self._get_service_product(fso.service_type)
        if service_product:
            amounts['base_service_amount'] = service_product.list_price * (fso.estimated_duration or 1)
        else:
            amounts['base_service_amount'] = 1000000.0  # Default VND amount
        
        # Equipment rental - simplified for now
        # TODO: Implement proper equipment cost calculation
        if fso.required_equipment_ids:
            amounts['equipment_rental_amount'] = 100000.0  # Default VND equipment charge
        else:
            amounts['equipment_rental_amount'] = 0.0
        
        # Travel expenses for home visits
        if fso.service_type == 'home_visit' and fso.travel_distance:
            travel_rate = 5000.0  # VND per km
            amounts['travel_expense_amount'] = fso.travel_distance * travel_rate
        else:
            amounts['travel_expense_amount'] = 0.0
        
        # Urgency surcharge
        if fso.priority in ('urgent', 'emergency'):
            base_amount = amounts.get('base_service_amount', 0)
            surcharge_rate = 0.5 if fso.priority == 'urgent' else 1.0
            amounts['urgency_surcharge_amount'] = base_amount * surcharge_rate
        else:
            amounts['urgency_surcharge_amount'] = 0.0
        
        amounts['supplies_amount'] = 0.0  # Will be updated when supplies are recorded
        
        return amounts

    def _get_service_product(self, service_category):
        """Get product template for healthcare service"""
        domain = [
            ('categ_id.name', 'ilike', 'healthcare'),
            ('name', 'ilike', service_category or 'consultation'),
        ]
        return self.env['product.template'].search(domain, limit=1)

    def _create_staff_time_tracking(self, billing, fso):
        """Create staff time tracking entries"""
        for staff_assignment in fso.assignment_ids:
            self.env['health.staff.time.tracking'].create({
                'billing_id': billing.id,
                'employee_id': staff_assignment.staff_id.id,
                'estimated_hours': fso.estimated_duration,
                'hourly_rate': staff_assignment.staff_id.hourly_cost or 50000.0,  # Default VND rate
                'service_date': fso.scheduled_date,
            })

    @api.model
    def create_from_appointment(self, appointment_id):
        """Create billing record from Appointment"""
        appointment = self.env['health.appointment'].browse(appointment_id)
        
        if not appointment:
            raise UserError(_('Appointment not found.'))
        
        billing_vals = {
            'name': f'Billing - {appointment.name}',
            'appointment_id': appointment.id,
            'patient_id': appointment.patient_id.id,
            'customer_id': appointment.patient_id.partner_id.id,
            'service_type': 'clinic_visit',
            'service_date': appointment.start_datetime,
            'service_duration_hours': (appointment.duration or 60) / 60.0,
            'service_location': 'clinic',
            'base_service_amount': appointment.appointment_type_id.price or 500000.0,  # Default VND
        }
        
        # Check insurance
        if appointment.patient_id.partner_id.has_health_insurance:
            billing_vals.update({
                'has_insurance': True,
                'insurance_provider_id': appointment.patient_id.partner_id.insurance_provider_id.id,
                'insurance_coverage_percentage': appointment.patient_id.partner_id.insurance_coverage_percentage,
            })
        
        return self.create(billing_vals)

    def action_generate_invoice(self):
        """Generate invoice from billing record"""
        self.ensure_one()
        
        if self.billing_status != 'ready_to_invoice':
            raise UserError(_('Billing must be in "Ready to Invoice" status.'))
        
        if self.invoice_id:
            raise UserError(_('Invoice already generated for this billing.'))
        
        # Create invoice with basic fields only
        invoice_vals = {
            'move_type': 'out_invoice',
            'partner_id': self.customer_id.id,
            'invoice_date': fields.Date.today(),
            'invoice_origin': self.name,
        }
        
        # Healthcare fields temporarily commented out
        # if self.fieldservice_order_id:
        #     invoice_vals['fieldservice_order_id'] = self.fieldservice_order_id.id
        # if self.appointment_id:
        #     invoice_vals['appointment_id'] = self.appointment_id.id    
        # if self.patient_id:
        #     invoice_vals['patient_id'] = self.patient_id.id
        if self.service_type:
            invoice_vals['healthcare_service_type'] = self.service_type
        
        # Create invoice
        invoice = self.env['account.move'].create(invoice_vals)
        
        # Update with additional fields after creation (safer approach)
        additional_vals = {}
        if self.staff_time_ids:
            additional_vals['staff_time_hours'] = sum(self.staff_time_ids.mapped('actual_hours'))
        if self.service_duration_hours:
            additional_vals['equipment_rental_days'] = self.service_duration_hours / 24.0
        if self.travel_distance_km:
            additional_vals['travel_distance_km'] = self.travel_distance_km
        if self.urgency_surcharge_amount:
            additional_vals['urgency_surcharge'] = self.urgency_surcharge_amount
        if self.has_insurance:
            additional_vals.update({
                'has_insurance_claim': self.has_insurance,
                'insurance_provider': self.insurance_provider_id.name if self.insurance_provider_id else False,
                'insurance_coverage_amount': self.insurance_covered_amount or 0.0,
                'patient_responsibility_amount': self.patient_responsibility_amount or 0.0,
            })
        
        if additional_vals:
            invoice.write(additional_vals)
        
        # Create invoice lines
        self._create_invoice_lines(invoice)
        
        # Link invoice to billing
        self.write({
            'invoice_id': invoice.id,
            'invoice_date': invoice.invoice_date,
            'billing_status': 'invoiced',
        })
        
        return {
            'name': _('Generated Invoice'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': invoice.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _create_invoice_lines(self, invoice):
        """Create invoice lines from billing details"""
        lines_to_create = []
        
        # Base service line
        if self.base_service_amount:
            service_product = self._get_service_product(self.service_type)
            lines_to_create.append({
                'move_id': invoice.id,
                'product_id': service_product.product_variant_id.id if service_product else False,
                'name': f'{dict(self._fields["service_type"].selection)[self.service_type]} - Service',
                'quantity': self.service_duration_hours or 1,
                'price_unit': self.base_service_amount / (self.service_duration_hours or 1),
                'healthcare_service_category': 'consultation',
            })
        
        # Equipment rental lines
        if self.equipment_rental_amount:
            lines_to_create.append({
                'move_id': invoice.id,
                'name': f'Medical Equipment Rental - {self.equipment_description or "Standard equipment"}',
                'quantity': 1,
                'price_unit': self.equipment_rental_amount,
                'healthcare_service_category': 'equipment',
            })
        
        # Medical supplies lines
        if self.supplies_amount:
            lines_to_create.append({
                'move_id': invoice.id,
                'name': 'Medical Supplies',
                'quantity': 1,
                'price_unit': self.supplies_amount,
                'healthcare_service_category': 'supplies',
            })
        
        # Travel expenses
        if self.travel_expense_amount:
            lines_to_create.append({
                'move_id': invoice.id,
                'name': f'Travel Expenses ({self.travel_distance_km} km)',
                'quantity': 1,
                'price_unit': self.travel_expense_amount,
                'healthcare_service_category': 'transportation',
            })
        
        # Urgency surcharge
        if self.urgency_surcharge_amount:
            lines_to_create.append({
                'move_id': invoice.id,
                'name': 'Urgency Surcharge',
                'quantity': 1,
                'price_unit': self.urgency_surcharge_amount,
                'healthcare_service_category': 'treatment',
            })
        
        # Staff time lines
        for staff_time in self.staff_time_ids:
            if staff_time.actual_hours and staff_time.hourly_rate:
                lines_to_create.append({
                    'move_id': invoice.id,
                    'name': f'Professional Services - {staff_time.employee_id.name}',
                    'quantity': staff_time.actual_hours,
                    'price_unit': staff_time.hourly_rate,
                    'healthcare_service_category': 'staff_time',
                    'staff_member_id': staff_time.employee_id.id if hasattr(staff_time, 'employee_id') else False,
                    'service_duration_minutes': staff_time.actual_hours * 60,
                })
        
        # Ensure at least one line exists
        if not lines_to_create:
            lines_to_create.append({
                'move_id': invoice.id,
                'name': 'Healthcare Service',
                'quantity': 1,
                'price_unit': 100.0,  # Default price
            })
        
        # Create all invoice lines
        for line_vals in lines_to_create:
            self.env['account.move.line'].create(line_vals)

    def action_mark_ready_to_invoice(self):
        """Mark billing as ready to invoice"""
        self.billing_status = 'ready_to_invoice'

    def action_cancel_billing(self):
        """Cancel billing record"""
        if self.invoice_id and self.invoice_id.state == 'posted':
            raise UserError(_('Cannot cancel billing with posted invoice. Please cancel the invoice first.'))
        
        self.billing_status = 'cancelled'


class HealthStaffTimeTracking(models.Model):
    """Staff time tracking for healthcare billing"""
    _name = 'health.staff.time.tracking'
    _description = 'Healthcare Staff Time Tracking'
    _order = 'service_date desc, employee_id'

    active = fields.Boolean('Active', default=True)

    billing_id = fields.Many2one(
        'health.service.billing',
        string='Billing Record',
        required=True,
        ondelete='cascade'
    )
    
    employee_id = fields.Many2one(
        'hr.employee',
        string='Staff Member',
        required=True
    )

    catchment_province_id = fields.Many2one(
        'health.catchment.province',
        string='Catchment Area',
        related='billing_id.catchment_province_id',
        store=True,
        readonly=True,
        help='Catchment area used for filtering and access control'
    )
    
    service_date = fields.Datetime(
        'Service Date',
        required=True
    )
    
    estimated_hours = fields.Float(
        'Estimated Hours',
        help='Initially estimated service time'
    )
    
    actual_hours = fields.Float(
        'Actual Hours',
        help='Actual time spent on service'
    )
    
    hourly_rate = fields.Monetary(
        'Hourly Rate',
        required=True,
        help='Billing rate per hour for this staff member'
    )
    
    total_amount = fields.Monetary(
        'Total Amount',
        compute='_compute_total_amount',
        store=True
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        related='billing_id.currency_id'
    )
    
    notes = fields.Text(
        'Notes',
        help='Additional notes about time spent'
    )

    @api.depends('actual_hours', 'hourly_rate')
    def _compute_total_amount(self):
        """Compute total amount for staff time"""
        for tracking in self:
            tracking.total_amount = (tracking.actual_hours or 0) * tracking.hourly_rate
