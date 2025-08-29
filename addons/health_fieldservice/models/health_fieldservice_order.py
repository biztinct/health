# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
import json
import pytz
import logging

_logger = logging.getLogger(__name__)


class HealthFieldServiceOrderUnified(models.Model):
    """
    UNIFIED Healthcare Field Service Order (Booking + Assignment + Scheduling)
    
    This replaces the separate appointment, assignment, and FSO models with
    a single comprehensive booking system that matches client requirements.
    
    CLIENT WORKFLOW: Lead → Contact → BOOKING → Assignment → Service → Invoice
    TECHNICAL: FSO = BOOKING (complete service order from start to finish)
    """
    _name = 'health.fieldservice.order'
    _description = 'Healthcare Field Service Order (Unified Booking System)'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _order = 'scheduled_datetime desc, priority desc, create_date desc'
    _rec_name = 'display_name'
    
    # ============================================================================
    # CORE IDENTIFICATION & DISPLAY
    # ============================================================================
    
    name = fields.Char(
        'Booking Reference', 
        required=True, 
        copy=False, 
        readonly=True,
        default=lambda self: _('New Booking'),
        tracking=True,
        help='Unique booking reference number'
    )
    
    display_name = fields.Char(
        'Display Name', 
        compute='_compute_display_name', 
        store=True,
        help='Computed display name for views'
    )
    
    @api.depends('name', 'patient_id', 'service_type', 'scheduled_datetime')
    def _compute_display_name(self):
        """Compute rich display name for views"""
        for record in self:
            if record.patient_id and record.service_type:
                service_name = dict(record._fields['service_type'].selection).get(record.service_type, '')
                date_str = record.scheduled_datetime.strftime('%m/%d %H:%M') if record.scheduled_datetime else 'Unscheduled'
                record.display_name = f"{record.name} - {record.patient_id.name} ({service_name}) - {date_str}"
            else:
                record.display_name = record.name or 'New Booking'
    
    # ============================================================================
    # PATIENT & CUSTOMER INFORMATION (From Client Requirements)
    # ============================================================================
    
    patient_id = fields.Many2one(
        'res.partner',
        string='Patient',
        required=True,
        tracking=True,
        domain=[('is_patient', '=', True)],
        help='Patient receiving the healthcare service'
    )
    
    customer_id = fields.Many2one(
        'res.partner',
        string='Customer/Payer',
        tracking=True,
        help='Customer responsible for payment (may be different from patient)'
    )
    
    # Patient Quick Info (for easy access)
    patient_code = fields.Char('Patient ID', related='patient_id.patient_code', readonly=True)
    patient_phone = fields.Char('Patient Phone', related='patient_id.mobile', readonly=True)
    patient_email = fields.Char('Patient Email', related='patient_id.email', readonly=True)
    patient_age = fields.Char('Patient Age', related='patient_id.age_display', readonly=True)
    
    # ============================================================================
    # SERVICE DETAILS (Core Booking Information)
    # ============================================================================
    
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
    ], string='Service Type', required=True, tracking=True,
       help='Type of healthcare service requested')
    
    service_category = fields.Selection([
        ('medical', 'Medical Care'),
        ('nursing', 'Nursing Care'), 
        ('therapy', 'Therapy'),
        ('diagnostic', 'Diagnostic'),
        ('emergency', 'Emergency'),
        ('wellness', 'Wellness Check'),
    ], string='Service Category', tracking=True)
    
    appointment_type_id = fields.Many2one(
        'health.service.type',
        string='Appointment Type',
        tracking=True,
        help='Specific appointment type with pricing and duration'
    )
    
    # Service Requirements & Notes
    symptoms = fields.Text('Symptoms/Chief Complaint', help='Patient\'s reported symptoms or reason for visit')
    service_requirements = fields.Text('Service Requirements', help='Specific requirements for this service')
    patient_notes = fields.Text('Patient Notes', help='Additional notes from patient')
    special_requirements = fields.Text('Special Requirements', help='Accessibility, equipment, or other special needs')
    
    # Clinical Priority (From Client Requirements)
    priority = fields.Selection([
        ('0', 'Low'),
        ('1', 'Normal'),
        ('2', 'High'), 
        ('3', 'Urgent'),
        ('4', 'Emergency')
    ], string='Priority', default='1', tracking=True)
    
    urgency_level = fields.Selection([
        ('routine', 'Routine'),
        ('urgent', 'Urgent'),
        ('emergency', 'Emergency'),
        ('critical', 'Critical'),
    ], string='Clinical Urgency', default='routine', tracking=True)
    
    # ============================================================================
    # SCHEDULING & TIMING (Integrated Appointment Scheduling)
    # ============================================================================
    
    # Primary scheduling fields
    scheduled_datetime = fields.Datetime(
        'Scheduled Date & Time',
        tracking=True,
        help='When the service is scheduled to be performed'
    )
    
    scheduled_date = fields.Date(
        'Scheduled Date',
        compute='_compute_scheduled_date',
        inverse='_inverse_scheduled_date',
        store=True,
        tracking=True
    )
    
    scheduled_time = fields.Float(
        'Scheduled Time',
        compute='_compute_scheduled_time', 
        inverse='_inverse_scheduled_time',
        store=True,
        help='Time in 24-hour format (e.g., 14.5 for 2:30 PM)'
    )
    
    @api.depends('scheduled_datetime')
    def _compute_scheduled_date(self):
        for record in self:
            if record.scheduled_datetime:
                record.scheduled_date = record.scheduled_datetime.date()
            else:
                record.scheduled_date = False
    
    @api.depends('scheduled_datetime')
    def _compute_scheduled_time(self):
        for record in self:
            if record.scheduled_datetime:
                local_dt = record.scheduled_datetime
                record.scheduled_time = local_dt.hour + local_dt.minute / 60.0
            else:
                record.scheduled_time = 0.0
    
    @api.depends('assignment_ids')
    def _compute_assignment_count(self):
        """Compute the number of staff assignments for this FSO"""
        for record in self:
            record.assignment_count = len(record.assignment_ids)
    
    @api.depends('invoice_id')
    def _compute_invoice_count(self):
        """Compute the number of invoices related to this FSO"""
        for record in self:
            # Count related invoices (main invoice_id plus any other invoices)
            invoice_count = 0
            if record.invoice_id:
                invoice_count += 1
            # Also count any additional invoices linked to this FSO
            additional_invoices = self.env['account.move'].search([
                ('fieldservice_order_id', '=', record.id),
                ('id', '!=', record.invoice_id.id if record.invoice_id else False)
            ])
            invoice_count += len(additional_invoices)
            record.invoice_count = invoice_count
    
    @api.depends('assignment_ids.staff_id')
    def _compute_assigned_staff(self):
        """Compute assigned staff from assignment records"""
        for record in self:
            staff_ids = record.assignment_ids.mapped('staff_id.id')
            record.assigned_staff_ids = [(6, 0, staff_ids)]
    
    @api.depends('assignment_ids.staff_id', 'assignment_ids.assignment_role')
    def _compute_lead_staff(self):
        """Compute lead staff from assignment records"""
        for record in self:
            lead_assignment = record.assignment_ids.filtered(lambda a: a.assignment_role == 'lead')
            record.lead_staff_id = lead_assignment.staff_id if lead_assignment else False
    
    def _inverse_scheduled_date(self):
        for record in self:
            if record.scheduled_date and record.scheduled_time:
                # Combine date and time
                hours = int(record.scheduled_time)
                minutes = int((record.scheduled_time - hours) * 60)
                dt = datetime.combine(record.scheduled_date, datetime.min.time().replace(hour=hours, minute=minutes))
                record.scheduled_datetime = dt
    
    def _inverse_scheduled_time(self):
        for record in self:
            if record.scheduled_date and record.scheduled_time:
                # Combine date and time
                hours = int(record.scheduled_time)
                minutes = int((record.scheduled_time - hours) * 60)
                dt = datetime.combine(record.scheduled_date, datetime.min.time().replace(hour=hours, minute=minutes))
                record.scheduled_datetime = dt
    
    # Duration and timing
    estimated_duration = fields.Float(
        'Estimated Duration (Hours)',
        default=1.0,
        help='Estimated duration of the service in hours'
    )
    
    duration_minutes = fields.Integer(
        'Duration (Minutes)',
        compute='_compute_duration_minutes',
        inverse='_inverse_duration_minutes',
        store=True,
        help='Duration in minutes for easier scheduling'
    )
    
    @api.depends('estimated_duration')
    def _compute_duration_minutes(self):
        for record in self:
            record.duration_minutes = int(record.estimated_duration * 60)
    
    def _inverse_duration_minutes(self):
        for record in self:
            record.estimated_duration = record.duration_minutes / 60.0
    
    estimated_end_datetime = fields.Datetime(
        'Estimated End Time',
        compute='_compute_estimated_end_datetime',
        store=True
    )
    
    @api.depends('scheduled_datetime', 'estimated_duration')
    def _compute_estimated_end_datetime(self):
        for record in self:
            if record.scheduled_datetime and record.estimated_duration:
                record.estimated_end_datetime = record.scheduled_datetime + timedelta(hours=record.estimated_duration)
            else:
                record.estimated_end_datetime = False
    
    # ============================================================================
    # STAFF ASSIGNMENT (Integrated Assignment Management)
    # ============================================================================
    
    # Computed staff assignment fields (from Assignment Model)
    assigned_staff_ids = fields.Many2many(
        'hr.employee',
        string='Assigned Staff',
        compute='_compute_assigned_staff',
        store=False,
        help='All staff members assigned to this service (computed from assignments)'
    )
    
    # Primary staff members
    lead_staff_id = fields.Many2one(
        'hr.employee',
        string='Lead Staff',
        compute='_compute_lead_staff',
        store=False,
        help='Primary staff member responsible for this service (computed from assignments)'
    )
    
    primary_doctor_id = fields.Many2one(
        'hr.employee',
        string='Primary Doctor',
        domain=[('is_healthcare_staff', '=', True), ('job_title', 'ilike', 'doctor')],
        tracking=True
    )
    
    primary_nurse_id = fields.Many2one(
        'hr.employee',
        string='Primary Nurse', 
        domain=[('is_healthcare_staff', '=', True), ('job_title', 'ilike', 'nurse')],
        tracking=True
    )
    
    # ============================================================================
    # Staff Assignment Management (Assignment Model)
    # ============================================================================
    
    assignment_ids = fields.One2many(
        'health.staff.assignment',
        'fso_id',
        string='Staff Assignments',
        help='Individual staff assignments for this FSO'
    )
    
    assignment_count = fields.Integer(
        'Assignment Count',
        compute='_compute_assignment_count',
        help='Number of staff assignments for this FSO'
    )
    
    # Invoice-related computed fields
    invoice_count = fields.Integer(
        'Invoice Count',
        compute='_compute_invoice_count',
        help='Number of invoices related to this FSO'
    )
    
    lead_assignment_id = fields.Many2one(
        'health.staff.assignment',
        string='Lead Assignment',
        domain="[('fso_id', '=', id), ('assignment_role', '=', 'lead')]",
        help='Primary assignment (lead staff member)'
    )
    
    # Assignment metadata
    assignment_date = fields.Datetime('Assignment Date', tracking=True, help='When staff were assigned')
    assigned_by_id = fields.Many2one('res.users', string='Assigned By', tracking=True)
    
    # AI Assignment Integration
    ai_assignment_score = fields.Float(
        'AI Assignment Score',
        help='AI-calculated score for assignment quality'
    )
    
    ai_assignment_factors = fields.Text(
        'AI Assignment Factors',
        help='JSON data of factors considered by AI assignment engine'
    )
    
    # ============================================================================
    # LOCATION & SERVICE DELIVERY
    # ============================================================================
    
    service_location = fields.Selection([
        ('home', 'Patient Home'),
        ('clinic', 'Clinic'),
        ('hospital', 'Hospital'),
        ('nursing_home', 'Nursing Home'),
        ('office', 'Office'),
        ('online', 'Online/Telemedicine'),
        ('other', 'Other Location'),
    ], string='Service Location', required=True, default='home', tracking=True)
    
    # Facility Information
    facility_id = fields.Many2one(
        'health.facility',
        string='Healthcare Facility',
        domain=[('active', '=', True)],
        help='Facility where service will be provided (for clinic/hospital visits)'
    )
    
    # Home Visit Address (Client Requirement)
    service_address = fields.Text(
        'Service Address',
        help='Complete address where service will be provided'
    )
    
    visit_address = fields.Text(
        'Visit Address',
        help='Detailed address for home visits'
    )
    
    gps_coordinates = fields.Char(
        'GPS Coordinates',
        help='GPS coordinates for navigation to service location'
    )
    
    # Travel Information
    travel_distance = fields.Float('Travel Distance (km)', help='Distance to service location')
    travel_time_minutes = fields.Integer('Travel Time (Minutes)', help='Estimated travel time')
    travel_fee = fields.Monetary('Travel Fee', help='Additional fee for travel')
    
    # Online/Telemedicine
    online_meeting_url = fields.Char('Online Meeting URL', help='Video consultation link')
    online_platform = fields.Selection([
        ('zoom', 'Zoom'),
        ('teams', 'Microsoft Teams'),
        ('google', 'Google Meet'),
        ('custom', 'Custom Platform'),
    ], string='Online Platform')
    
    # ============================================================================
    # EQUIPMENT & RESOURCES (From FSO Requirements)
    # ============================================================================
    
    required_equipment_ids = fields.Many2many(
        'health.portable.equipment',
        'fso_required_equipment_rel',
        'fso_id', 'equipment_id',
        string='Required Equipment',
        help='Medical equipment required for this service'
    )
    
    assigned_equipment_ids = fields.Many2many(
        'health.portable.equipment',
        'fso_assigned_equipment_rel', 
        'fso_id', 'equipment_id',
        string='Assigned Equipment',
        help='Equipment actually assigned and available'
    )
    
    equipment_checklist_complete = fields.Boolean(
        'Equipment Checklist Complete',
        help='All required equipment has been checked and confirmed available'
    )
    
    supplies_required = fields.Text('Required Supplies', help='Medical supplies needed for service')
    supplies_checklist = fields.Text('Supplies Checklist', help='Checklist of supplies prepared')
    
    # ============================================================================
    # WORKFLOW & STATUS MANAGEMENT  
    # ============================================================================
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('assigned', 'Assigned'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('closed', 'Closed'),
        # Legacy states for existing data compatibility
        ('cancelled', 'Cancelled'),
        ('no_show', 'Patient No Show'),
        ('rescheduled', 'Rescheduled'),
    ], string='Status', default='draft', tracking=True, required=True)
    
    stage_id = fields.Many2one(
        'health.fieldservice.stage',
        string='Stage',
        tracking=True,
        group_expand='_read_group_stage_ids',
        help='Current stage in the service delivery workflow'
    )
    
    team_id = fields.Many2one(
        'health.fieldservice.team',
        string='Service Team',
        tracking=True,
        help='Team responsible for this service'
    )
    
    # ============================================================================
    # BOOKING & CUSTOMER INTERACTION (Client Requirements)
    # ============================================================================
    
    booking_source = fields.Selection([
        ('portal', 'Patient Portal'),
        ('website', 'Website Booking'),
        ('phone', 'Phone Call'),
        ('walk_in', 'Walk-in'),
        ('staff', 'Staff Created'),
        ('facebook', 'Facebook'),
        ('zalo', 'Zalo'),
        ('referral', 'Referral'),
        ('crm_lead', 'CRM Lead'),
    ], string='Booking Source', default='staff', tracking=True)
    
    booking_date = fields.Datetime('Booking Date', default=fields.Datetime.now, readonly=True)
    booking_user_id = fields.Many2one('res.users', string='Booked By', default=lambda self: self.env.user)
    
    # Lead Integration (Client Workflow: Lead → Contact → Booking)
    crm_lead_id = fields.Many2one(
        'crm.lead',
        string='CRM Lead',
        help='CRM lead that generated this booking'
    )
    
    # Confirmation tracking
    confirmation_date = fields.Datetime('Confirmation Date', readonly=True)
    confirmed_by_id = fields.Many2one('res.users', string='Confirmed By', readonly=True)
    confirmation_method = fields.Selection([
        ('phone', 'Phone Call'),
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('zalo', 'Zalo'),
        ('in_person', 'In Person'),
    ], string='Confirmation Method')
    
    # ============================================================================
    # INVOICING & BILLING (Client Priority: Auto Invoice Generation)
    # ============================================================================
    
    # Auto-generated invoice (Client Requirement: "Draft invoices are created when a booking is assigned")
    invoice_id = fields.Many2one(
        'account.move',
        string='Generated Invoice',
        readonly=True,
        help='Auto-generated invoice for this service'
    )
    
    invoice_state = fields.Selection(
        related='invoice_id.state',
        string='Invoice Status',
        readonly=True
    )
    
    # Pricing Information
    base_price = fields.Monetary('Base Service Price', help='Base price for the service')
    total_price = fields.Monetary('Total Price', compute='_compute_total_price', store=True)
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    
    # Additional charges
    travel_charge = fields.Monetary('Travel Charge', help='Additional charge for travel/distance')
    urgency_charge = fields.Monetary('Urgency Charge', help='Additional charge for urgent services')
    equipment_charge = fields.Monetary('Equipment Charge', help='Charge for special equipment')
    after_hours_charge = fields.Monetary('After Hours Charge', help='Charge for after-hours service')
    
    @api.depends('base_price', 'travel_charge', 'urgency_charge', 'equipment_charge', 'after_hours_charge')
    def _compute_total_price(self):
        for record in self:
            record.total_price = (
                record.base_price + 
                record.travel_charge + 
                record.urgency_charge + 
                record.equipment_charge + 
                record.after_hours_charge
            )
    
    # Payment tracking
    payment_status = fields.Selection([
        ('pending', 'Payment Pending'),
        ('partial', 'Partially Paid'),
        ('paid', 'Fully Paid'),
        ('overpaid', 'Overpaid'),
        ('refunded', 'Refunded'),
    ], string='Payment Status', compute='_compute_payment_status')
    
    # Insurance Information
    has_insurance = fields.Boolean('Has Insurance', compute='_compute_has_insurance', store=True)
    insurance_provider = fields.Char('Insurance Provider', related='patient_id.insurance_provider')
    insurance_claim_id = fields.Many2one('health.insurance.claim', string='Insurance Claim')
    
    # ============================================================================
    # SERVICE EXECUTION & CLINICAL NOTES
    # ============================================================================
    
    # Service execution timing
    actual_start_datetime = fields.Datetime('Actual Start Time', tracking=True)
    actual_end_datetime = fields.Datetime('Actual End Time', tracking=True)
    actual_duration = fields.Float('Actual Duration (Hours)', compute='_compute_actual_duration', store=True)
    
    @api.depends('actual_start_datetime', 'actual_end_datetime')
    def _compute_actual_duration(self):
        for record in self:
            if record.actual_start_datetime and record.actual_end_datetime:
                delta = record.actual_end_datetime - record.actual_start_datetime
                record.actual_duration = delta.total_seconds() / 3600.0
            else:
                record.actual_duration = 0.0
    
    # Clinical Documentation
    clinical_notes = fields.Html('Clinical Notes', help='Clinical observations and notes from service provider')
    treatment_performed = fields.Text('Treatment Performed', help='Detailed description of treatment provided')
    medications_prescribed = fields.Text('Medications Prescribed', help='Medications prescribed during service')
    
    # Patient condition and assessment
    patient_condition_before = fields.Text('Patient Condition (Before)', help='Patient condition before service')
    patient_condition_after = fields.Text('Patient Condition (After)', help='Patient condition after service')
    vital_signs = fields.Text('Vital Signs', help='Recorded vital signs during service')
    
    # Follow-up requirements
    follow_up_required = fields.Boolean('Follow-up Required')
    follow_up_date = fields.Date('Follow-up Date')
    follow_up_notes = fields.Text('Follow-up Notes')
    
    # Service quality and completion
    service_rating = fields.Selection([
        ('1', '1 - Poor'),
        ('2', '2 - Fair'),
        ('3', '3 - Good'),
        ('4', '4 - Very Good'),
        ('5', '5 - Excellent'),
    ], string='Service Rating', help='Patient rating of service quality')
    
    completion_notes = fields.Text('Completion Notes', help='Notes about service completion')
    
    # ============================================================================
    # COMMUNICATION & COORDINATION
    # ============================================================================
    
    # Communication log (from existing FSO communication model)
    communication_ids = fields.One2many(
        'health.fieldservice.communication',
        'fieldservice_order_id',
        string='Communications',
        help='All communications related to this service order'
    )
    
    last_communication_date = fields.Datetime(
        'Last Communication',
        compute='_compute_last_communication',
        store=True
    )
    
    @api.depends('communication_ids.create_date')
    def _compute_last_communication(self):
        for record in self:
            if record.communication_ids:
                record.last_communication_date = max(record.communication_ids.mapped('create_date'))
            else:
                record.last_communication_date = False
    
    # Quick communication flags
    patient_contacted = fields.Boolean('Patient Contacted', help='Patient has been contacted about this service')
    staff_notified = fields.Boolean('Staff Notified', help='Assigned staff have been notified')
    reminders_sent = fields.Boolean('Reminders Sent', help='Appointment reminders have been sent')
    
    # ============================================================================
    # VIETNAMESE COMPLIANCE & INTEGRATION
    # ============================================================================
    
    # Vietnamese regulatory requirements
    moh_submission_required = fields.Boolean('MOH Submission Required', help='Requires Ministry of Health submission')
    moh_submission_date = fields.Datetime('MOH Submission Date')
    moh_reference = fields.Char('MOH Reference Number')
    
    # MISA Integration
    misa_synced = fields.Boolean('MISA Synced', help='Synced with MISA accounting system')
    misa_sync_date = fields.Datetime('MISA Sync Date')
    misa_reference = fields.Char('MISA Reference')
    
    # Vietnamese address components
    vietnamese_address_components = fields.Text('Vietnamese Address Components', help='Structured Vietnamese address')
    
    # ============================================================================
    # COMPUTED FIELDS & SMART FIELDS
    # ============================================================================
    
    @api.depends('invoice_id', 'invoice_id.payment_state')
    def _compute_payment_status(self):
        for record in self:
            if not record.invoice_id:
                record.payment_status = 'pending'
            elif record.invoice_id.payment_state == 'paid':
                record.payment_status = 'paid'
            elif record.invoice_id.payment_state == 'partial':
                record.payment_status = 'partial'
            else:
                record.payment_status = 'pending'
    
    @api.depends('patient_id.insurance_provider')
    def _compute_has_insurance(self):
        for record in self:
            record.has_insurance = bool(record.patient_id.insurance_provider)
    
    # Smart button counts
    communication_count = fields.Integer('Communication Count', compute='_compute_communication_count')
    
    @api.depends('communication_ids')
    def _compute_communication_count(self):
        for record in self:
            record.communication_count = len(record.communication_ids)
    
    # ============================================================================
    # ONCHANGE METHODS & BUSINESS LOGIC
    # ============================================================================
    
    @api.onchange('patient_id')
    def _onchange_patient_id(self):
        """Auto-populate customer and address when patient is selected"""
        if self.patient_id:
            # Set customer to patient if not already set
            if not self.customer_id:
                self.customer_id = self.patient_id
            
            # Auto-populate service address for home visits
            if self.service_location == 'home' and self.patient_id.street:
                address_parts = [
                    self.patient_id.street,
                    self.patient_id.street2,
                    self.patient_id.city,
                    self.patient_id.state_id.name if self.patient_id.state_id else '',
                    self.patient_id.zip,
                ]
                self.service_address = ', '.join(filter(None, address_parts))
    
    @api.onchange('service_type')
    def _onchange_service_type(self):
        """Set defaults based on service type"""
        if self.service_type == 'emergency':
            self.priority = '4'
            self.urgency_level = 'emergency'
        elif self.service_type == 'telemedicine':
            self.service_location = 'online'
        elif self.service_type in ['home_visit', 'follow_up']:
            self.service_location = 'home'
        elif self.service_type == 'clinic_visit':
            self.service_location = 'clinic'
    
    @api.onchange('appointment_type_id')
    def _onchange_appointment_type_id(self):
        """Auto-populate duration and pricing from appointment type"""
        if self.appointment_type_id:
            if self.appointment_type_id.duration_minutes:
                self.duration_minutes = self.appointment_type_id.duration_minutes
            if self.appointment_type_id.price:
                self.base_price = self.appointment_type_id.price
    
    @api.onchange('urgency_level', 'priority')
    def _onchange_urgency_priority(self):
        """Calculate urgency charges"""
        if self.urgency_level in ['urgent', 'emergency', 'critical'] or self.priority in ['3', '4']:
            if self.base_price:
                if self.urgency_level == 'critical' or self.priority == '4':
                    self.urgency_charge = self.base_price * 1.0  # 100% surcharge
                elif self.urgency_level == 'emergency' or self.priority == '3':
                    self.urgency_charge = self.base_price * 0.5  # 50% surcharge
                else:
                    self.urgency_charge = self.base_price * 0.25  # 25% surcharge
    
    # ============================================================================
    # CRUD METHODS & AUTOMATION
    # ============================================================================
    
    @api.model_create_multi
    def create(self, vals_list):
        """Create FSO with auto-generated reference and invoice"""
        for vals in vals_list:
            # Generate sequence number
            if vals.get('name', _('New Booking')) == _('New Booking'):
                vals['name'] = self.env['ir.sequence'].next_by_code('health.fieldservice.order') or _('New Booking')
            
            # Set customer to patient if not specified
            if vals.get('patient_id') and not vals.get('customer_id'):
                vals['customer_id'] = vals['patient_id']
        
        orders = super().create(vals_list)
        
        # Post-creation automation
        for order in orders:
            # Send notifications
            order._send_booking_notifications()
            # Note: Invoice generation removed - now manual per Invoicing.md requirements
        
        return orders
    
    def write(self, vals):
        """Handle state changes and automation triggers"""
        result = super().write(vals)
        
        # Handle state transitions
        if 'state' in vals:
            self._handle_state_change(vals['state'])
        
        # Staff assignment is now handled through assignment_ids relationship
        
        # Handle scheduling
        if 'scheduled_datetime' in vals and vals['scheduled_datetime']:
            self._handle_scheduling()
        
        return result
    
    def _handle_state_change(self, new_state):
        """Handle automation based on state changes"""
        for record in self:
            if new_state == 'assigned':
                # Set assignment date
                record.assignment_date = fields.Datetime.now()
                # Notify assigned staff
                record._notify_assigned_staff()
            
            elif new_state == 'in_progress':
                # Set actual start time if not set
                if not record.actual_start_datetime:
                    record.actual_start_datetime = fields.Datetime.now()
            
            elif new_state == 'completed':
                # Set actual end time if not set
                if not record.actual_end_datetime:
                    record.actual_end_datetime = fields.Datetime.now()
                # Send completion notifications
                record._send_completion_notifications()
                # Note: Invoice creation is now manual per Invoicing.md workflow
            
            elif new_state == 'closed':
                # Final state - archive or cleanup actions
                pass
    
    def _handle_staff_assignment(self):
        """Handle automation when staff is assigned (through assignment model)"""
        for record in self:
            # Auto-advance state to 'assigned' if assignments exist and in draft state
            if record.assignment_ids and record.state == 'draft':
                record.state = 'assigned'
    
    def _handle_scheduling(self):
        """Handle automation when service is scheduled"""
        for record in self:
            # Keep state as 'assigned' when scheduling - no additional state needed
            pass
    
    # ============================================================================
    # INVOICE GENERATION & BILLING (Client Priority)
    # ============================================================================
    
    def action_create_final_invoice(self):
        """Create final invoice after service completion (per Invoicing.md workflow)"""
        self.ensure_one()
        
        # Validate state - can only invoice completed services
        if self.state != 'completed':
            raise UserError(_('Invoice can only be created for completed services.'))
        
        if self.invoice_id:
            raise UserError(_('Invoice already exists for this service order.'))
        
        # Create billing record first (intermediate step)
        billing = self.env['health.service.billing'].create_from_fieldservice_order(self.id)
        billing.action_mark_ready_to_invoice()
        
        # Generate final invoice
        invoice_result = billing.action_generate_invoice()
        
        # Update FSO with invoice link
        self.invoice_id = billing.invoice_id.id
        
        # Return wizard for payment workflow (Pay Now/Pay Later)
        return self._open_payment_workflow_wizard(billing.invoice_id)
    
    def _open_payment_workflow_wizard(self, invoice):
        """Open payment workflow wizard (Pay Now/Pay Later) per Invoicing.md"""
        return {
            'name': _('Payment Workflow'),
            'type': 'ir.actions.act_window',
            'res_model': 'health.payment.workflow.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_fso_id': self.id,
                'default_invoice_id': invoice.id,
                'default_amount_total': invoice.amount_total,
            }
        }
    
    def _create_invoice_lines(self, invoice):
        """Create detailed invoice lines for the service"""
        lines_to_create = []
        
        # Main service line
        if self.base_price:
            lines_to_create.append({
                'move_id': invoice.id,
                'name': f'{dict(self._fields["service_type"].selection)[self.service_type]} - {self.patient_id.name}',
                'quantity': self.estimated_duration or 1,
                'price_unit': self.base_price / (self.estimated_duration or 1),
                'healthcare_service_category': 'consultation',
            })
        
        # Travel charges
        if self.travel_charge:
            lines_to_create.append({
                'move_id': invoice.id,
                'name': f'Travel Charge ({self.travel_distance} km)',
                'quantity': 1,
                'price_unit': self.travel_charge,
                'healthcare_service_category': 'transportation',
            })
        
        # Urgency charges
        if self.urgency_charge:
            lines_to_create.append({
                'move_id': invoice.id,
                'name': 'Urgency Surcharge',
                'quantity': 1,
                'price_unit': self.urgency_charge,
                'healthcare_service_category': 'treatment',
            })
        
        # Equipment charges
        if self.equipment_charge:
            lines_to_create.append({
                'move_id': invoice.id,
                'name': 'Equipment Usage',
                'quantity': 1,
                'price_unit': self.equipment_charge,
                'healthcare_service_category': 'equipment',
            })
        
        # After hours charges
        if self.after_hours_charge:
            lines_to_create.append({
                'move_id': invoice.id,
                'name': 'After Hours Service',
                'quantity': 1,
                'price_unit': self.after_hours_charge,
                'healthcare_service_category': 'treatment',
            })
        
        # Create invoice lines
        for line_vals in lines_to_create:
            self.env['account.move.line'].create(line_vals)
    
    def _finalize_invoice(self):
        """Finalize invoice when service is completed"""
        self.ensure_one()
        
        if self.invoice_id and self.invoice_id.state == 'draft':
            # Update invoice with actual service details
            self.invoice_id.write({
                'staff_time_hours': self.actual_duration or self.estimated_duration,
                # Add any final adjustments based on actual service
            })
    
    # ============================================================================
    # COMMUNICATION & NOTIFICATIONS
    # ============================================================================
    
    def _send_booking_notifications(self):
        """Send notifications when booking is created"""
        for record in self:
            # Notify patient
            record._notify_patient_booking_created()
            # Notify internal team
            record._notify_team_new_booking()
    
    def _send_confirmation_notifications(self):
        """Send notifications when booking is confirmed"""
        for record in self:
            # Send confirmation to patient
            record._notify_patient_booking_confirmed()
    
    def _notify_assigned_staff(self):
        """Notify staff when they are assigned (through assignment model)"""
        for record in self:
            for assignment in record.assignment_ids:
                if assignment.staff_id:
                    record._send_staff_assignment_notification(assignment.staff_id)
    
    def _send_completion_notifications(self):
        """Send notifications when service is completed"""
        for record in self:
            # Notify patient of completion
            record._notify_patient_service_completed()
            # Internal completion notifications
            record._notify_team_service_completed()
    
    def _notify_patient_booking_created(self):
        """Notify patient that booking has been created"""
        # Implementation depends on communication preferences
        pass
    
    def _notify_team_new_booking(self):
        """Notify internal team of new booking"""
        # Implementation for internal notifications
        pass
    
    def _notify_patient_booking_confirmed(self):
        """Notify patient that booking is confirmed"""
        # Implementation for patient confirmation
        pass
    
    def _send_staff_assignment_notification(self, staff):
        """Send notification to assigned staff"""
        # Implementation for staff notifications
        pass
    
    def _notify_patient_service_completed(self):
        """Notify patient that service is completed"""
        # Implementation for completion notifications
        pass
    
    def _notify_team_service_completed(self):
        """Notify team that service is completed"""
        # Implementation for team notifications
        pass
    
    # ============================================================================
    # AI ASSIGNMENT ENGINE INTEGRATION
    # ============================================================================
    
    def action_ai_assign_staff(self):
        """Trigger AI-powered staff assignment (creates assignment records)"""
        self.ensure_one()
        
        # Call AI assignment engine
        ai_engine = self.env['health.ai.assignment.engine']
        assignment_result = ai_engine.assign_optimal_staff(self)
        
        if assignment_result.get('success'):
            # Create assignment records for each recommended staff member
            for i, staff_id in enumerate(assignment_result['staff_ids']):
                role = 'lead' if staff_id == assignment_result.get('lead_staff_id') else 'support'
                self.env['health.staff.assignment'].create({
                    'fso_id': self.id,
                    'staff_id': staff_id,
                    'assignment_role': role,
                    'assignment_date': self.scheduled_datetime or fields.Datetime.now(),
                    'planned_start_time': self.scheduled_datetime,
                    'assignment_status': 'assigned',
                    'state': 'assigned'
                })
            
            # Update FSO with AI metadata
            self.write({
                'ai_assignment_score': assignment_result['score'],
                'ai_assignment_factors': json.dumps(assignment_result['factors']),
                'state': 'assigned'
            })
        
        return assignment_result
    
    def action_assign_staff_to_fso(self, staff_id, assignment_role='support'):
        """Create individual staff assignment for this FSO (called by drag-drop)"""
        self.ensure_one()
        
        # Check if staff is already assigned
        existing_assignment = self.assignment_ids.filtered(lambda a: a.staff_id.id == staff_id)
        if existing_assignment:
            return {'warning': f'Staff member already assigned with role: {existing_assignment.assignment_role}'}
        
        # Create new assignment
        assignment = self.env['health.staff.assignment'].create({
            'fso_id': self.id,
            'staff_id': staff_id,
            'assignment_role': assignment_role,
            'assignment_date': self.scheduled_datetime or fields.Datetime.now(),
            'planned_start_time': self.scheduled_datetime,
            'assignment_status': 'assigned',
            'state': 'assigned'
        })
        
        # Update FSO state if needed
        if self.state == 'draft':
            self.state = 'assigned'
        
        return {'success': True, 'assignment_id': assignment.id}
    
    # ============================================================================
    # ACTION METHODS FOR UI
    # ============================================================================
    
    def action_confirm_booking(self):
        """Confirm the booking"""
        self.ensure_one()
        self.write({
            'state': 'confirmed',
            'confirmation_date': fields.Datetime.now(),
            'confirmed_by_id': self.env.user.id,
        })
    
    def action_start_service(self):
        """Start the service execution"""
        self.ensure_one()
        self.write({
            'state': 'in_progress',
            'actual_start_datetime': fields.Datetime.now(),
        })
    
    def action_complete_service(self):
        """Complete the service"""
        self.ensure_one()
        self.write({
            'state': 'completed',
            'actual_end_datetime': fields.Datetime.now(),
        })

    def action_close_fso(self):
        """Close the FSO after completion (final state)"""
        self.ensure_one()
        self.write({
            'state': 'closed',
        })
    
    def action_cancel_booking(self):
        """Cancel the booking"""
        self.ensure_one()
        self.write({
            'state': 'cancelled',
        })
        
        # Archive draft invoice if exists
        if self.invoice_id and self.invoice_id.state == 'draft':
            self.invoice_id.button_cancel()
    
    def action_reschedule_booking(self):
        """Reschedule the booking"""
        self.ensure_one()
        return {
            'name': _('Reschedule Booking'),
            'type': 'ir.actions.act_window',
            'res_model': 'health.fieldservice.order',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {'form_view_initial_mode': 'edit', 'force_detailed_view': True}
        }
    
    def action_view_invoice(self):
        """View the generated invoice"""
        self.ensure_one()
        if not self.invoice_id:
            raise UserError(_('No invoice has been generated for this booking.'))
        
        return {
            'name': _('Generated Invoice'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.invoice_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def action_view_all_invoices(self):
        """View all invoices related to this FSO"""
        self.ensure_one()
        
        # Find all invoices related to this FSO
        invoice_ids = []
        if self.invoice_id:
            invoice_ids.append(self.invoice_id.id)
        
        # Search for additional invoices
        additional_invoices = self.env['account.move'].search([
            ('fieldservice_order_id', '=', self.id)
        ])
        invoice_ids.extend(additional_invoices.ids)
        
        if not invoice_ids:
            raise UserError(_('No invoices have been generated for this booking.'))
        
        if len(invoice_ids) == 1:
            # Single invoice - open form view
            return {
                'name': _('Invoice'),
                'type': 'ir.actions.act_window',
                'res_model': 'account.move',
                'res_id': invoice_ids[0],
                'view_mode': 'form',
                'target': 'current',
            }
        else:
            # Multiple invoices - open list view
            return {
                'name': _('Invoices for %s') % self.name,
                'type': 'ir.actions.act_window',
                'res_model': 'account.move',
                'domain': [('id', 'in', invoice_ids)],
                'view_mode': 'list,form',
                'target': 'current',
            }
    
    # action_create_invoice_anytime method temporarily removed
    # Use "Create Invoice" after service completion or Healthcare Invoicing menu
    
    def action_view_communications(self):
        """View communications related to this booking"""
        self.ensure_one()
        return {
            'name': _('Communications'),
            'type': 'ir.actions.act_window',
            'res_model': 'health.fieldservice.communication',
            'view_mode': 'tree,form',
            'domain': [('fieldservice_order_id', '=', self.id)],
            'context': {'default_fieldservice_order_id': self.id},
        }
    
    # ============================================================================
    # STAFF ASSIGNMENT MANAGEMENT
    # ============================================================================
    
    def action_assign_staff_to_fso(self, staff_id, assignment_role='support'):
        """Create individual staff assignment for this FSO (called by drag-drop)"""
        self.ensure_one()
        
        # Check if staff already assigned
        existing = self.assignment_ids.filtered(lambda a: a.staff_id.id == staff_id)
        if existing:
            raise UserError(_("Staff member is already assigned to this FSO"))
        
        # Create assignment
        assignment = self.env['health.staff.assignment'].create({
            'fso_id': self.id,
            'staff_id': staff_id,
            'assignment_role': assignment_role,
            'planned_start_time': self.scheduled_datetime,
            'planned_end_time': self.scheduled_datetime + timedelta(hours=1) if self.scheduled_datetime else False,
            'assignment_status': 'assigned'
        })
        
        # If this is first assignment or role is lead, set as lead
        if not self.lead_assignment_id or assignment_role == 'lead':
            self.lead_assignment_id = assignment
            
        return assignment
    
    def action_view_assignments(self):
        """View all staff assignments for this FSO"""
        self.ensure_one()
        return {
            'name': _('Staff Assignments'),
            'type': 'ir.actions.act_window',
            'res_model': 'health.staff.assignment',
            'view_mode': 'tree,form',
            'domain': [('fso_id', '=', self.id)],
            'context': {'default_fso_id': self.id},
        }
    
    # ============================================================================
    # UTILITY METHODS
    # ============================================================================
    
    def _get_default_stage(self):
        """Get default stage for new FSO"""
        stage = self.env['health.fieldservice.stage'].search([('sequence', '=', 1)], limit=1)
        return stage.id if stage else False
    
    @api.model
    def _read_group_stage_ids(self, stages, domain, order):
        """Return all stages for kanban view"""
        return self.env['health.fieldservice.stage'].search([], order=order)
    
    def name_get(self):
        """Custom name display"""
        result = []
        for record in self:
            if record.patient_id:
                name = f"{record.name} - {record.patient_id.name}"
                if record.scheduled_datetime:
                    name += f" ({record.scheduled_datetime.strftime('%m/%d %H:%M')})"
            else:
                name = record.name
            result.append((record.id, name))
        return result
    
    def action_manual_assign_staff(self):
        """Open manual staff assignment wizard"""
        self.ensure_one()
        
        return {
            'name': _('Assign Staff to Service'),
            'type': 'ir.actions.act_window',
            'res_model': 'health.staff.assignment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_fso_id': self.id,
                'default_service_type': self.service_type,
                'default_scheduled_datetime': self.scheduled_datetime,
                'default_patient_id': self.patient_id.id,
            }
        }
    
    def action_view_invoice(self):
        """View the generated invoice"""
        self.ensure_one()
        
        if not self.invoice_id:
            raise UserError(_('No invoice has been generated for this service order yet.'))
        
        return {
            'name': _('Service Invoice'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.invoice_id.id,
            'view_mode': 'form',
            'target': 'current',
        }