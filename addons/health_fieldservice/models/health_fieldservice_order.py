# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
import json
import pytz
import logging
import copy

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
    
    @api.depends('name', 'patient_id')
    def _compute_display_name(self):
        """Compute clean display name for views - format: Client Name (Booking ID)"""
        for record in self:
            if record.patient_id and record.name:
                record.display_name = f"{record.patient_id.name} ({record.name})"
            else:
                record.display_name = record.name or 'New Booking'
    
    def _get_service_type_label(self):
        """Get the human-readable label for service type"""
        self.ensure_one()
        service_type_dict = dict(self._fields['service_type'].selection)
        return service_type_dict.get(self.service_type, self.service_type or 'Unknown Service')

    # ============================================================================
    # CHATTER TRACKING CONTROL
    # ============================================================================

    def _get_hidden_tracking_fields(self):
        """Return field names whose tracking should be hidden from chatter."""
        return {
            name
            for name, field in self._fields.items()
            if getattr(field, 'tracking', False)
        }

    def _filter_tracking_value_ids(self, tracking_value_ids):
        """Filter tracking commands to remove hidden fields."""
        hidden_fields = self._get_hidden_tracking_fields()
        if not tracking_value_ids or not hidden_fields:
            return tracking_value_ids

        filtered_tracking = []
        for tracking_value in tracking_value_ids:
            include = True
            if isinstance(tracking_value, (list, tuple)) and len(tracking_value) >= 3:
                tracking_dict = tracking_value[2]
                if isinstance(tracking_dict, dict):
                    field_id = tracking_dict.get('field_id')
                    if field_id:
                        try:
                            field_record = self.env['ir.model.fields'].browse(field_id)
                            field_name = field_record.name if field_record.exists() else None
                            if field_name and field_name in hidden_fields:
                                include = False
                                _logger.info("FSO chatter filter -> hidden field: %s", field_name)
                        except Exception as e:
                            _logger.warning("FSO chatter filter could not load field %s: %s", field_id, e)
            # Append command only if still included
            if include:
                filtered_tracking.append(tracking_value)

        return filtered_tracking

    def message_post(self, **kwargs):
        """
        Hide tracked value commands for sensitive fields before posting notes.
        """
        if kwargs.get('tracking_value_ids'):
            filtered_tracking = self._filter_tracking_value_ids(kwargs['tracking_value_ids'])
            _logger.info("FSO message_post filtered tracking: kept %s of %s",
                         len(filtered_tracking), len(kwargs['tracking_value_ids']))
            if filtered_tracking:
                kwargs['tracking_value_ids'] = filtered_tracking
            else:
                kwargs.pop('tracking_value_ids', None)
        return super().message_post(**kwargs)

    def _message_log(self, **kwargs):
        """
        Ensure tracked values for hidden fields are stored for Audit Log but
        excluded from chatter.
        """
        hidden_fields = self._get_hidden_tracking_fields()
        original_tracking_ids = kwargs.get('tracking_value_ids', [])
        base_kwargs = dict(kwargs)

        if original_tracking_ids and hidden_fields:
            _logger.info("FSO _message_log received %s tracking commands", len(original_tracking_ids))
            visible_tracking = []
            hidden_tracking = []

            for tracking_value in original_tracking_ids:
                is_hidden = False
                field_name = None
                if isinstance(tracking_value, (list, tuple)) and len(tracking_value) >= 3:
                    tracking_dict = tracking_value[2]
                    if isinstance(tracking_dict, dict):
                        field_id = tracking_dict.get('field_id')
                        if field_id:
                            try:
                                field_record = self.env['ir.model.fields'].browse(field_id)
                                if field_record.exists():
                                    field_name = field_record.name
                            except Exception as e:
                                _logger.warning("FSO _message_log field lookup failed for %s: %s", field_id, e)
                        if field_name and field_name in hidden_fields:
                            is_hidden = True
                            _logger.info("FSO _message_log hiding field: %s", field_name)

                if is_hidden:
                    hidden_tracking.append(tracking_value)
                else:
                    visible_tracking.append(tracking_value)

            message = None
            if visible_tracking:
                visible_kwargs = dict(base_kwargs)
                visible_commands = [copy.deepcopy(cmd) for cmd in visible_tracking]
                for command in visible_commands:
                    if isinstance(command, (list, tuple)) and len(command) >= 3 and command[0] == 0:
                        command[2].pop('mail_message_id', None)
                visible_kwargs['tracking_value_ids'] = visible_commands
                message = super()._message_log(**visible_kwargs)
                _logger.info("FSO _message_log posted visible message %s", message.id)

            if hidden_tracking:
                hidden_kwargs = dict(base_kwargs)
                hidden_commands = [copy.deepcopy(cmd) for cmd in hidden_tracking]
                for command in hidden_commands:
                    if isinstance(command, (list, tuple)) and len(command) >= 3 and command[0] == 0:
                        command[2].pop('mail_message_id', None)
                hidden_kwargs['tracking_value_ids'] = hidden_commands
                hidden_kwargs['message_type'] = 'user_notification'
                hidden_kwargs['partner_ids'] = False
                hidden_kwargs['attachment_ids'] = False
                hidden_kwargs['body'] = hidden_kwargs.get('body') or '<p></p>'

                hidden_message = super()._message_log(**hidden_kwargs)
                hidden_message.sudo().write({
                    'message_type': 'user_notification',
                    'subtype_id': False,
                    'is_internal': True,
                    'body': hidden_message.body or '<p></p>',
                })
                _logger.info("FSO _message_log stored hidden message %s", hidden_message.id)
                if not message:
                    message = hidden_message

            return message

        return super()._message_log(**kwargs)
    
    # ============================================================================
    # PATIENT & CUSTOMER INFORMATION (From Client Requirements)
    # ============================================================================
    
    patient_id = fields.Many2one(
        'res.partner',
        string='Client',
        required=True,
        tracking=True,
        domain=[('is_patient', '=', True)],
        help='client receiving the healthcare service'
    )
    
    customer_id = fields.Many2one(
        'res.partner',
        string='Customer/Payer',
        tracking=True,
        help='client)'
    )
    
    # Patient Quick Info (for easy access)
    patient_code = fields.Char('Patient ID', related='patient_id.patient_code', readonly=True)
    patient_phone = fields.Char('Patient Phone', related='patient_id.mobile', readonly=True)
    patient_email = fields.Char('Patient Email', related='patient_id.email', readonly=True)
    patient_age = fields.Char('Patient Age', related='patient_id.age_display', readonly=True)

    # Booking Creator Tracking (PWA Mobile Booking System)
    created_by_employee_id = fields.Many2one(
        'hr.employee',
        'Created By (Staff)',
        readonly=True,
        help='Healthcare staff member who created this booking via mobile PWA'
    )

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
    ], string='Service Type', required=True, tracking=True, default='home_visit',
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
    symptoms = fields.Text('Symptoms/Chief Complaint', help='client\'s reported symptoms or reason for visit')
    diagnosis = fields.Text('Diagnosis', help='Medical diagnosis (Chuẩn đoán) - MOH compliance field')
    service_requirements = fields.Text('Service Requirements', help='Specific requirements for this service')
    patient_notes = fields.Text('Patient Notes', help='client')
    special_requirements = fields.Text('Special Requirements', help='Accessibility, equipment, or other special needs')

    # Intake Notes Fields (editable at booking level - independent from patient record)
    referring_doctor_id = fields.Many2one(
        'res.partner',
        string='Referring Doctor',
        help='Contact who referred this patient'
    )
    goal_of_care = fields.Text('Goal of Care', help='Primary goal or objective of care for this booking')
    required_equipment = fields.Text('Required Equipment', help='Equipment or supplies required for this service')
    intake_notes = fields.Text('Intake Notes', help='Additional intake assessment notes')

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

    scheduled_month = fields.Char(
        'Scheduled Month',
        compute='_compute_scheduled_month',
        store=True,
        help='Month and year for kanban grouping (e.g., "October 2025")'
    )

    @api.depends('scheduled_datetime')
    def _compute_scheduled_date(self):
        for record in self:
            if record.scheduled_datetime:
                # Convert from UTC storage to user's timezone for date computation
                utc_dt = pytz.UTC.localize(record.scheduled_datetime)
                user_tz = pytz.timezone(self.env.user.tz or 'UTC')
                local_dt = utc_dt.astimezone(user_tz)
                record.scheduled_date = local_dt.date()
            else:
                record.scheduled_date = False
    
    @api.depends('scheduled_datetime')
    def _compute_scheduled_time(self):
        for record in self:
            if record.scheduled_datetime:
                # Convert from UTC storage to user's timezone
                utc_dt = pytz.UTC.localize(record.scheduled_datetime)
                user_tz = pytz.timezone(self.env.user.tz or 'UTC')
                local_dt = utc_dt.astimezone(user_tz)
                record.scheduled_time = local_dt.hour + local_dt.minute / 60.0
            else:
                record.scheduled_time = 0.0

    @api.depends('scheduled_datetime')
    def _compute_scheduled_month(self):
        """Compute month-year label for kanban grouping"""
        for record in self:
            if record.scheduled_datetime:
                # Convert from UTC storage to user's timezone
                utc_dt = pytz.UTC.localize(record.scheduled_datetime)
                user_tz = pytz.timezone(self.env.user.tz or 'UTC')
                local_dt = utc_dt.astimezone(user_tz)
                # Format as "October 2025"
                record.scheduled_month = local_dt.strftime('%B %Y')
            else:
                record.scheduled_month = 'Unscheduled'

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
    
    @api.depends('sale_order_id')
    def _compute_quote_count(self):
        """Compute the number of quotes/sales orders related to this FSO"""
        for record in self:
            # Count quotes/sales orders linked to this FSO
            quote_count = 0
            if record.sale_order_id:
                quote_count += 1
            # Also count any additional quotes linked to this FSO via origin field
            additional_quotes = self.env['sale.order'].search([
                ('origin', '=', record.name),
                ('id', '!=', record.sale_order_id.id if record.sale_order_id else False)
            ])
            quote_count += len(additional_quotes)
            record.quote_count = quote_count
    
    @api.depends('sale_order_id', 'sale_order_id.order_line')
    def _compute_order_line_count(self):
        """Compute the number of order lines in the healthcare quote"""
        for record in self:
            if record.sale_order_id:
                record.order_line_count = len(record.sale_order_id.order_line)
            else:
                record.order_line_count = 0
    
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
            # Filter for lead assignments - get the staff member from the first one
            lead_assignment = record.assignment_ids.filtered(lambda a: a.assignment_role == 'lead')

            # Extract the first lead staff member if it exists
            if lead_assignment:
                # lead_assignment is a recordset, so [0] gets the first assignment record
                # and .staff_id gets the Many2one field (single employee record or False)
                first_assignment = lead_assignment[0]
                if first_assignment and first_assignment.staff_id:
                    record.lead_staff_id = first_assignment.staff_id
                else:
                    record.lead_staff_id = False
            else:
                record.lead_staff_id = False

    @api.depends('assignment_ids.staff_id', 'assignment_ids.staff_id.job_title', 'primary_doctor_id')
    def _compute_assigned_doctor(self):
        """Compute assigned doctor from staff assignments or primary_doctor_id"""
        for record in self:
            # First check if primary_doctor_id is set
            if record.primary_doctor_id:
                record.assigned_doctor_id = record.primary_doctor_id
            else:
                # Look for doctor in assignments
                doctor_assignment = record.assignment_ids.filtered(
                    lambda a: a.staff_id and a.staff_id.job_title and 'doctor' in a.staff_id.job_title.lower()
                )
                record.assigned_doctor_id = doctor_assignment[0].staff_id if doctor_assignment else False

    def _inverse_scheduled_date(self):
        for record in self:
            if record.scheduled_date and record.scheduled_time:
                # Combine date and time with proper timezone handling
                hours = int(record.scheduled_time)
                minutes = int((record.scheduled_time - hours) * 60)
                
                # Create naive datetime first
                naive_dt = datetime.combine(record.scheduled_date, datetime.min.time().replace(hour=hours, minute=minutes))
                
                # Convert to user's timezone then to UTC for storage
                user_tz = pytz.timezone(self.env.user.tz or 'UTC')
                local_dt = user_tz.localize(naive_dt)
                utc_dt = local_dt.astimezone(pytz.UTC)
                
                record.scheduled_datetime = utc_dt.replace(tzinfo=None)  # Store as naive UTC
    
    def _inverse_scheduled_time(self):
        for record in self:
            if record.scheduled_date and record.scheduled_time:
                # Combine date and time with proper timezone handling
                hours = int(record.scheduled_time)
                minutes = int((record.scheduled_time - hours) * 60)
                
                # Create naive datetime first
                naive_dt = datetime.combine(record.scheduled_date, datetime.min.time().replace(hour=hours, minute=minutes))
                
                # Convert to user's timezone then to UTC for storage
                user_tz = pytz.timezone(self.env.user.tz or 'UTC')
                local_dt = user_tz.localize(naive_dt)
                utc_dt = local_dt.astimezone(pytz.UTC)
                
                record.scheduled_datetime = utc_dt.replace(tzinfo=None)  # Store as naive UTC
    
    # Duration and timing
    scheduled_duration = fields.Integer(
        'Scheduled Duration (Minutes)',
        default=60,
        required=True,
        tracking=True,
        help='Scheduled duration of the booking in minutes (used for timeline display and scheduling)'
    )

    estimated_duration = fields.Float(
        'Estimated Duration (Hours)',
        compute='_compute_estimated_duration',
        store=True,
        help='Computed from scheduled_duration for backward compatibility with pricing calculations'
    )

    @api.depends('scheduled_duration')
    def _compute_estimated_duration(self):
        """Compute hours from minutes for backward compatibility"""
        for record in self:
            record.estimated_duration = record.scheduled_duration / 60.0 if record.scheduled_duration else 0.0

    estimated_end_datetime = fields.Datetime(
        'Estimated End Time',
        compute='_compute_estimated_end_datetime',
        store=True
    )

    @api.depends('scheduled_datetime', 'scheduled_duration')
    def _compute_estimated_end_datetime(self):
        for record in self:
            if record.scheduled_datetime and record.scheduled_duration:
                record.estimated_end_datetime = record.scheduled_datetime + timedelta(minutes=record.scheduled_duration)
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

    assigned_doctor_id = fields.Many2one(
        'hr.employee',
        string='Assigned Doctor',
        compute='_compute_assigned_doctor',
        store=False,
        help='Doctor assigned from staff assignments (computed from assignments with doctor role)'
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
        help='Individual staff assignments for this Booking'
    )

    assignment_count = fields.Integer(
        'Assignment Count',
        compute='_compute_assignment_count',
        help='Number of staff assignments for this Booking'
    )

    # Invoice-related computed fields
    invoice_count = fields.Integer(
        'Invoice Count',
        compute='_compute_invoice_count',
        help='Number of invoices related to this Booking'
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
    
    # Backend state for logic (readonly, invisible, domain conditions)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('assigned', 'Assigned'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('completed_pending_invoice', 'Completed - Pending Invoice'),
        ('cancelled', 'Cancelled'),
        ('closed', 'Closed'),
    ], string='Status', default='draft', tracking=True, required=True,
       help='Backend state for workflow logic and field visibility')
    
    # Visual stage for UI (kanban, colors, user experience)
    stage_id = fields.Many2one(
        'health.fieldservice.stage',
        string='Stage',
        tracking=True,
        group_expand='_read_group_stage_ids',
        domain=[('active', '=', True)],
        ondelete='restrict',
        help='Visual stage for kanban and user interface'
    )
    
    # Additional workflow fields
    patient_contact_confirmed = fields.Boolean('Patient Contact Confirmed', default=False,
                                              help='client has been contacted and confirmed the appointment')

    # Cancellation fields
    cancellation_reason_id = fields.Many2one(
        'health.booking.cancellation.reason',
        string='Cancellation Reason',
        tracking=True,
        help='Structured reason for booking cancellation'
    )
    cancelled_by = fields.Many2one(
        'res.users',
        string='Cancelled By',
        readonly=True,
        help='User who cancelled the booking'
    )
    cancellation_date = fields.Datetime(
        'Cancellation Date',
        readonly=True,
        help='Date and time when booking was cancelled'
    )
    cancellation_notes = fields.Text(
        'Cancellation Notes',
        help='Additional notes about the cancellation'
    )

    # Completion fields for part-time workflow
    completion_notes = fields.Text(
        'Completion Notes',
        tracking=True,
        help='Notes about service completion, especially for part-time staff requiring Operations invoicing'
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
    
    # Quote/Sales Order (FSO Quote Integration)
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Healthcare Quote',
        readonly=True,
        tracking=True,
        help='Associated healthcare quote/sales order for this service'
    )
    
    quote_count = fields.Integer(
        'Quote Count',
        compute='_compute_quote_count',
        help='Number of quotes/sales orders related to this Booking'
    )
    
    order_line_count = fields.Integer(
        'Quote Line Count',
        compute='_compute_order_line_count',
        help='Number of order lines in the healthcare quote'
    )

    # Service Package (Alternative to Quote for prepaid services)
    package_id = fields.Many2one(
        'health.service.package',
        string='Service Package',
        tracking=True,
        help='Prepaid service package selected for this booking'
    )

    quote_state = fields.Selection(
        related='sale_order_id.state',
        string='Quote Status',
        readonly=True
    )
    
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
    adjusted_end_datetime = fields.Datetime(
        'Adjusted End Time',
        compute='_compute_adjusted_end_datetime',
        inverse='_inverse_adjusted_end_datetime',
        store=True,
        tracking=True,
        help='Adjusted end time (editable) - defaults to Actual End Time but can be manually adjusted'
    )
    actual_duration = fields.Float('Actual Duration (Hours)', compute='_compute_actual_duration', store=True)
    actual_duration_display = fields.Char('Duration Display', compute='_compute_duration_display', store=True)
    service_timer_active = fields.Boolean('Timer Active', compute='_compute_timer_active', store=True)
    
    @api.depends('actual_start_datetime', 'actual_end_datetime')
    def _compute_actual_duration(self):
        for record in self:
            if record.actual_start_datetime and record.actual_end_datetime:
                delta = record.actual_end_datetime - record.actual_start_datetime
                record.actual_duration = delta.total_seconds() / 3600.0
            else:
                record.actual_duration = 0.0
    
    @api.depends('actual_start_datetime', 'actual_end_datetime')
    def _compute_duration_display(self):
        """Compute human-readable duration display (HH:MM:SS)"""
        for record in self:
            if record.actual_start_datetime and record.actual_end_datetime:
                delta = record.actual_end_datetime - record.actual_start_datetime
                total_seconds = int(delta.total_seconds())
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                seconds = total_seconds % 60
                record.actual_duration_display = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            elif record.actual_start_datetime and not record.actual_end_datetime:
                # Service is running - show "RUNNING"
                record.actual_duration_display = "RUNNING"
            else:
                record.actual_duration_display = "00:00:00"
    
    @api.depends('actual_start_datetime', 'actual_end_datetime', 'state')
    def _compute_timer_active(self):
        """Check if service timer is currently active"""
        for record in self:
            record.service_timer_active = (
                record.actual_start_datetime and
                not record.actual_end_datetime and
                record.state == 'in_progress'
            )

    @api.depends('actual_end_datetime')
    def _compute_adjusted_end_datetime(self):
        """Compute adjusted end time - defaults to actual end time"""
        for record in self:
            if record.actual_end_datetime:
                # Only update if adjusted_end_datetime is not manually set
                if not record.adjusted_end_datetime or record.adjusted_end_datetime == record.actual_end_datetime:
                    record.adjusted_end_datetime = record.actual_end_datetime
            else:
                record.adjusted_end_datetime = False

    def _inverse_adjusted_end_datetime(self):
        """Inverse method to allow manual editing of adjusted_end_datetime"""
        # This method allows the field to be editable
        # The value is already set by the user, so we don't need to do anything here
        pass

    @api.depends('clinical_notes', 'treatment_performed')
    def _compute_clinical_notes_status(self):
        """Check if clinical notes have been submitted"""
        for record in self:
            # Clinical notes are considered submitted if either clinical_notes or treatment_performed has content
            record.clinical_notes_submitted = bool(
                (record.clinical_notes and record.clinical_notes.strip()) or
                (record.treatment_performed and record.treatment_performed.strip())
            )

    @api.depends('invoice_id', 'invoice_id.state', 'sale_order_id', 'sale_order_id.order_line')
    def _compute_invoice_status(self):
        """Check if invoice has been submitted (not draft)"""
        for record in self:
            # Invoice is considered submitted if:
            # 1. An invoice exists and is not in draft state, OR
            # 2. A quote/sale order exists with line items (ready for invoicing)
            has_invoice = record.invoice_id and record.invoice_id.state != 'draft'
            has_quote_with_items = record.sale_order_id and record.sale_order_id.order_line
            record.invoice_submitted = has_invoice or has_quote_with_items

    # Clinical Documentation
    clinical_notes = fields.Html('Clinical Notes', help='Clinical observations and notes from service provider')
    treatment_performed = fields.Text('Treatment Performed', help='Detailed description of treatment provided')
    medications_prescribed = fields.Text('Medications Prescribed', help='Medications prescribed during service')
    
    # Patient condition and assessment
    patient_condition_before = fields.Text('Patient Condition (Before)', help='client condition before service')
    patient_condition_after = fields.Text('Patient Condition (After)', help='client condition after service')
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
    ], string='Service Rating', help='client rating of service quality')
    
    completion_notes = fields.Text('Completion Notes', help='Notes about service completion')

    # Validation status for job completion
    clinical_notes_submitted = fields.Boolean(
        'Clinical Notes Submitted',
        compute='_compute_clinical_notes_status',
        store=True,
        help='True if clinical notes have been entered'
    )

    invoice_submitted = fields.Boolean(
        'Invoice Submitted',
        compute='_compute_invoice_status',
        store=True,
        help='True if invoice has been created and submitted'
    )
    
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
    patient_contacted = fields.Boolean('Patient Contacted', help='client has been contacted about this service')
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
    # STATE-STAGE SYNCHRONIZATION
    # ============================================================================
    
    @api.model
    def _get_default_stage(self):
        """Get default stage for new FSOs - always Draft stage"""
        draft_stage = self.env['health.fieldservice.stage'].search([
            ('state', '=', 'draft'),
            ('active', '=', True)
        ], order='sequence', limit=1)

        if not draft_stage:
            _logger.warning('No Draft stage found! Please configure booking stages.')

        return draft_stage
    
    @api.onchange('stage_id')
    def _onchange_stage_id(self):
        """Auto-sync state when stage changes"""
        if self.stage_id and self.stage_id.state:
            self.state = self.stage_id.state
    
    def _validate_stage_transition(self, new_stage):
        """Validate stage transition requirements"""
        if not new_stage:
            return
        
        errors = new_stage.validate_stage_requirements(self)
        if errors:
            raise UserError('\n'.join(errors))
    
    # ============================================================================
    # ONCHANGE METHODS & BUSINESS LOGIC
    # ============================================================================
    
    @api.onchange('patient_id')
    def _onchange_patient_id(self):
        """Auto-populate customer, address, and intake fields when patient is selected"""
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

            # Auto-populate intake fields from patient record
            # These fields remain independently editable in the FSO
            try:
                self.diagnosis = self.patient_id.intake_diagnosis
                self.referring_doctor_id = self.patient_id.intake_referring_doctor_id
                self.goal_of_care = self.patient_id.intake_goal_of_care
                self.required_equipment = self.patient_id.intake_required_equipment
                self.intake_notes = self.patient_id.intake_notes
            except Exception as e:
                _logger.warning(f"Error copying intake fields from patient: {str(e)}")
    
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
                self.scheduled_duration = self.appointment_type_id.duration_minutes
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
    # HELPER METHODS
    # ============================================================================

    def _get_assignment_type(self):
        """Get assignment type based on service location and priority"""
        assignment_type_map = {
            'home': 'home_visit',
            'clinic': 'clinic_visit',
            'hospital': 'clinic_visit',
            'online': 'consultation',
            'nursing_home': 'home_visit',
            'office': 'consultation',
            'other': 'clinic_visit',
        }

        # Get base type from service location
        assignment_type = assignment_type_map.get(self.service_location, 'clinic_visit')

        # Override with emergency if priority is high
        if self.priority in ['3', '4']:
            assignment_type = 'emergency'

        return assignment_type

    # ============================================================================
    # CRUD METHODS & AUTOMATION
    # ============================================================================

    @api.model_create_multi
    def create(self, vals_list):
        """Create FSO with auto-generated reference and default stage"""
        for vals in vals_list:
            # Generate sequence number
            if vals.get('name', _('New Booking')) == _('New Booking'):
                vals['name'] = self.env['ir.sequence'].next_by_code('health.fieldservice.order') or _('New Booking')
            
            # Set customer to patient if not specified
            if vals.get('patient_id') and not vals.get('customer_id'):
                vals['customer_id'] = vals['patient_id']
            
            # Set default stage if not specified
            if not vals.get('stage_id'):
                default_stage = self._get_default_stage()
                if default_stage:
                    vals['stage_id'] = default_stage.id
                    vals['state'] = default_stage.state
        
        orders = super().create(vals_list)

        # Post-creation automation
        for order in orders:
            # Send notifications
            order._send_booking_notifications()
            # Show quote creation notification for Operations Managers
            order._show_quote_creation_notification()
            # Update patient's next visit date
            order._update_patient_next_visit_date()

        return orders
    
    def write(self, vals):
        """Handle state changes and automation triggers with stage-state synchronization"""
        
        # Handle stage transitions with validation
        if 'stage_id' in vals and vals['stage_id']:
            new_stage = self.env['health.fieldservice.stage'].browse(vals['stage_id'])
            
            # Validate stage requirements for each record
            for record in self:
                record._validate_stage_transition(new_stage)
            
            # Auto-sync state from stage
            if new_stage.state:
                vals['state'] = new_stage.state
        
        result = super().write(vals)

        # Handle state transitions
        if 'state' in vals:
            self._handle_state_change(vals['state'])

        # Handle scheduling
        if 'scheduled_datetime' in vals and vals['scheduled_datetime']:
            self._handle_scheduling()

        # Auto-advance to 'assigned' state when staff is assigned
        for record in self:
            if record.state == 'confirmed' and record.assigned_staff_ids:
                record.state = 'assigned'

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
                # Delete the template assignment for this booking
                template_assignment = self.env['health.staff.assignment'].search([
                    ('state', '=', 'template'),
                    ('fso_id', '=', record.id)
                ])
                if template_assignment:
                    _logger.info("🗑️ DELETING TEMPLATE ASSIGNMENT for completed booking: %s (Template ID: %s)", record.name, template_assignment.id)
                    template_assignment.unlink()
                # Note: Invoice creation is now manual per Invoicing.md workflow
            
            elif new_state == 'closed':
                # Final state - archive or cleanup actions
                pass
    
    def _handle_staff_assignment(self):
        """Handle automation when staff is assigned (through assignment model)"""
        for record in self:
            # Auto-advance state to 'assigned' if assignments exist
            # Also sync stage_id if state is already 'assigned' but stage doesn't match
            if record.assignment_ids and record.state in ['draft', 'confirmed', 'assigned']:
                # Find Assigned stage - use name to be more specific
                assigned_stage = self.env['health.fieldservice.stage'].search([
                    ('state', '=', 'assigned'),
                    ('name', '=', 'Assigned'),
                    ('active', '=', True)
                ], order='sequence', limit=1)

                if not assigned_stage:
                    # Fallback to any stage with state='assigned'
                    assigned_stage = self.env['health.fieldservice.stage'].search([
                        ('state', '=', 'assigned'),
                        ('active', '=', True)
                    ], order='sequence', limit=1)

                if assigned_stage:
                    # Only update if stage is different (avoid infinite recursion)
                    if record.stage_id != assigned_stage:
                        record.write({
                            'stage_id': assigned_stage.id,
                            'state': 'assigned'
                        })
                        _logger.info(f'FSO {record.name} moved to Assigned stage (ID: {assigned_stage.id}, Name: {assigned_stage.name}) after staff assignment')
                else:
                    _logger.error(f'No Assigned stage found for FSO {record.name}')
    
    def _handle_scheduling(self):
        """Handle automation when service is scheduled"""
        for record in self:
            # Keep state as 'assigned' when scheduling - no additional state needed
            pass
    
    # ============================================================================
    # INVOICE GENERATION & BILLING (Client Priority)
    # ============================================================================
    
    def action_create_final_invoice(self):
        """Create final invoice - first opens quote for editing like sale.order"""
        self.ensure_one()
        
        # Validate state - can only invoice completed services
        if self.state != 'completed':
            raise UserError(_('Invoice can only be created for completed services.'))
        
        if self.invoice_id:
            raise UserError(_('Invoice already exists for this service order.'))
        
        # Ensure quote exists first
        if not self.sale_order_id:
            # Create quote if it doesn't exist
            quote = self._create_empty_quote()
            if quote:
                self.sale_order_id = quote.id
            else:
                raise UserError(_('Failed to create quote. Please create a quote first.'))
        
        # Open quote for editing with Create Invoice context
        return self._open_quote_for_invoicing()
    
    def _open_quote_for_invoicing(self):
        """Open quote popup with Create Invoice context"""
        self.ensure_one()
        return {
            'name': _('Review Quote - Create Invoice'),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': self.sale_order_id.id,
            'view_mode': 'form',
            'view_id': self.env.ref('health_fieldservice.view_healthcare_quote_form_custom').id,
            'target': 'new',  # Opens in popup
            'context': {
                'form_view_initial_mode': 'edit',
                'healthcare_context': True,
                'invoicing_mode': True,  # Special flag for invoicing
                'fso_id': self.id,
                'default_fso_id': self.id,
            }
        }
    
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
    
    def _show_quote_creation_notification(self):
        """Show notification about quote creation requirement for Operations Managers"""
        if self.env.user.has_group('health_base.group_healthcare_operations_manager'):
            if not self.sale_order_id:
                # Post informational message to chatter
                try:
                    self.message_post(
                        body=_('📋 <strong>Quote Required:</strong> This booking needs a healthcare quote before it can be confirmed. Use the "Create Quote" smart button to add services and pricing.'),
                        message_type='notification',
                        subtype_xmlid='mail.mt_note'
                    )
                except Exception:
                    pass  # Silently fail - no email notifications required

    def _update_patient_next_visit_date(self):
        """Update patient's next_visit_date with the earliest scheduled FSO date"""
        self.ensure_one()

        if not self.patient_id:
            return

        # Find all scheduled/upcoming FSOs for this patient (excluding completed/cancelled ones)
        upcoming_fsos = self.env['health.fieldservice.order'].search([
            ('patient_id', '=', self.patient_id.id),
            ('state', 'in', ['draft', 'assigned', 'confirmed', 'in_progress']),
            ('scheduled_datetime', '!=', False)
        ], order='scheduled_datetime ASC', limit=1)

        if upcoming_fsos:
            # Update patient's next_visit_date with the earliest scheduled datetime
            next_visit = upcoming_fsos[0].scheduled_datetime
            self.patient_id.write({'next_visit_date': next_visit})
            _logger.info(f'Updated next_visit_date for patient {self.patient_id.name} to {next_visit}')
        else:
            # No scheduled FSO found - clear the next_visit_date
            self.patient_id.write({'next_visit_date': False})

    def _reserve_package_service(self):
        """
        Reserve 1 service from the package when booking is confirmed.
        Decreases remaining_services by 1.
        """
        self.ensure_one()

        if not self.package_id:
            return False

        # Decrease remaining services
        quantity_to_reserve = self.package_consumption_quantity or 1
        self.package_id.consumed_services += quantity_to_reserve

        # Log reservation in package's chatter
        try:
            self.package_id.message_post(
                body=_(
                    '<p><strong>Service Reserved</strong></p>'
                    '<ul>'
                    '<li><strong>Booking:</strong> %s</li>'
                    '<li><strong>Patient:</strong> %s</li>'
                    '<li><strong>Services Reserved:</strong> %d</li>'
                    '<li><strong>Services Remaining:</strong> %d</li>'
                    '</ul>'
                ) % (
                    self.name,
                    self.patient_id.name if self.patient_id else 'N/A',
                    quantity_to_reserve,
                    self.package_id.remaining_services
                ),
                subject=_('Service Reserved - %s') % self.name,
                message_type='notification'
            )
        except Exception as e:
            _logger.warning(f'Could not log package reservation for FSO {self.name}: {str(e)}')

        return True

    def _release_package_service(self):
        """
        Release reserved service back to the package when booking is cancelled.
        Increases remaining_services by 1.
        """
        self.ensure_one()

        if not self.package_id:
            return False

        # Increase available services
        quantity_to_release = self.package_consumption_quantity or 1
        self.package_id.consumed_services -= quantity_to_release

        # Ensure consumed_services doesn't go below 0
        if self.package_id.consumed_services < 0:
            self.package_id.consumed_services = 0

        # Update package state back to active if it was exhausted
        if self.package_id.state == 'exhausted':
            self.package_id.state = 'active'

        # Log release in package's chatter
        try:
            self.package_id.message_post(
                body=_(
                    '<p><strong>Service Released (Booking Cancelled)</strong></p>'
                    '<ul>'
                    '<li><strong>Booking:</strong> %s</li>'
                    '<li><strong>Patient:</strong> %s</li>'
                    '<li><strong>Services Released:</strong> %d</li>'
                    '<li><strong>Services Remaining:</strong> %d</li>'
                    '</ul>'
                ) % (
                    self.name,
                    self.patient_id.name if self.patient_id else 'N/A',
                    quantity_to_release,
                    self.package_id.remaining_services
                ),
                subject=_('Service Released - %s') % self.name,
                message_type='notification'
            )
        except Exception as e:
            _logger.warning(f'Could not log package release for FSO {self.name}: {str(e)}')

        return True

    def _check_confirmation_requirements(self):
        """
        Check if booking meets requirements to be confirmed.
        Requirements: MUST have EITHER:
        1. A quote with at least one line item, OR
        2. A service package selected (with sufficient remaining services)

        Returns: (bool, str) - (is_valid, error_message)
        """
        self.ensure_one()

        has_quote_with_items = (
            self.sale_order_id and
            self.sale_order_id.order_line and
            len(self.sale_order_id.order_line) > 0
        )

        has_package = self.package_id

        if not has_quote_with_items and not has_package:
            error_msg = _(
                'Booking cannot be confirmed. You must complete ONE of the following:\n'
                '• Create a Quote with at least one service/product line item\n'
                '• Select a prepaid Service Package'
            )
            return False, error_msg

        # If package is selected, check that it has sufficient remaining services
        if has_package:
            required_quantity = self.package_consumption_quantity or 1
            if self.package_id.remaining_services < required_quantity:
                error_msg = _(
                    'Cannot confirm booking: Package "%s" does not have sufficient remaining services.\n'
                    'Required: %d service(s)\n'
                    'Available: %d service(s)\n\n'
                    'Please select a different package or create a quote instead.'
                ) % (self.package_id.name, required_quantity, self.package_id.remaining_services)
                return False, error_msg

        return True, None

    def action_confirm_booking(self):
        """Confirm booking and move to confirmed stage"""
        self.ensure_one()

        # Check confirmation requirements
        is_valid, error_message = self._check_confirmation_requirements()
        if not is_valid:
            raise UserError(error_message)

        # Find confirmed stage
        confirmed_stage = self.env['health.fieldservice.stage'].search([
            ('state', '=', 'confirmed'),
            ('active', '=', True)
        ], order='sequence', limit=1)

        if not confirmed_stage:
            raise UserError(_('No confirmed stage found. Please configure stages properly.'))

        # Move to confirmed stage (validation will happen in write method)
        try:
            self.write({'stage_id': confirmed_stage.id})

            # Reserve service from package if booking uses prepaid package
            if self.package_id:
                self._reserve_package_service()

            # Post confirmation message
            quote_or_package = self.sale_order_id.name if self.sale_order_id else self.package_id.name
            try:
                self.message_post(
                    body=_('✅ <strong>Booking Confirmed:</strong> Booking moved to %s stage. %s is ready for service delivery.') % (confirmed_stage.name, quote_or_package),
                    message_type='notification',
                    subtype_xmlid='mail.mt_note'
                )
            except Exception:
                pass  # Silently fail - no email notifications required
        except UserError as e:
            # Re-raise with better context
            raise UserError(_('Cannot confirm booking:\n%s') % str(e))

        return True
    
    def _get_next_stage(self):
        """Get the next stage in sequence"""
        if self.stage_id:
            next_stage = self.env['health.fieldservice.stage'].search([
                ('sequence', '>', self.stage_id.sequence)
            ], order='sequence asc', limit=1)
            return next_stage
        return None
    
    def _notify_patient_booking_confirmed(self):
        """Notify patient that booking is confirmed"""
        # Implementation for patient confirmation
        pass
    
    def _create_empty_quote(self):
        """Create an empty healthcare quote for this FSO"""
        # Get default pricelist
        pricelist = self.env['product.pricelist'].search([('currency_id', '=', self.env.company.currency_id.id)], limit=1)
        if not pricelist:
            pricelist = self.env['product.pricelist'].create({
                'name': 'Healthcare Services Pricelist',
                'currency_id': self.env.company.currency_id.id,
            })
        
        # Create empty sales order
        quote_vals = {
            'partner_id': self.patient_id.id,
            'origin': self.name,
            'pricelist_id': pricelist.id,
            'state': 'draft',
            'note': f'Healthcare Quote for {self._get_service_type_label()} - {self.patient_id.name}',
        }
        
        quote = self.env['sale.order'].create(quote_vals)
        return quote
    
    def _show_quote_notification(self):
        """Show notification to user about adding items to quote"""
        message = _(
            '📋 An empty healthcare quote has been created for this FSO.\n'
            '⚠️ Please add at least one service or product to the quote by clicking the "Quote" smart button.'
        )
        # Post message to chatter for persistent notification
        try:
            self.message_post(
                body=message,
                message_type='notification',
                subtype_xmlid='mail.mt_note'
            )
        except Exception:
            pass  # Silently fail - no email notifications required
    
    def _show_quote_recommendation(self):
        """Show recommendation message for non-OM users"""
        message = _('💡 Consider asking Operations Manager to create a quote for this FSO.')
        try:
            self.message_post(
                body=message,
                message_type='notification',
                subtype_xmlid='mail.mt_note'
            )
        except Exception:
            pass  # Silently fail - no email notifications required
    
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
    
    # action_confirm_booking method moved above with quote validation
    
    def action_start_service(self):
        """Start the service execution - moves booking to In Progress stage"""
        self.ensure_one()

        # Find In Progress stage - use name to be specific and avoid "En Route" or "Arrived"
        in_progress_stage = self.env['health.fieldservice.stage'].search([
            ('state', '=', 'in_progress'),
            ('name', '=', 'In Progress'),
            ('active', '=', True)
        ], order='sequence', limit=1)

        if not in_progress_stage:
            # Fallback to any stage with state='in_progress'
            in_progress_stage = self.env['health.fieldservice.stage'].search([
                ('state', '=', 'in_progress'),
                ('active', '=', True)
            ], order='sequence', limit=1)

        if not in_progress_stage:
            raise UserError(_('No In Progress stage found. Please configure booking stages properly.'))

        _logger.info(f'FSO {self.name}: Starting service, moving to In Progress stage (ID: {in_progress_stage.id}, Name: {in_progress_stage.name})')

        self.write({
            'stage_id': in_progress_stage.id,
            'state': 'in_progress',
            'actual_start_datetime': fields.Datetime.now(),
        })

        # Reload the form view to update UI (statusbar, timer, buttons)
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
            'params': {
                'next': {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Service Started'),
                        'message': _('Booking moved to In Progress stage. Timer started.'),
                        'type': 'success',
                        'sticky': False,
                    }
                }
            }
        }
    
    def _check_invoice_creation_permission(self):
        """Check if assigned staff can create invoice based on employment type"""
        self.ensure_one()
        if not self.lead_staff_id:
            # If no lead staff, allow invoice creation (default behavior)
            return True
        return self.lead_staff_id.can_create_invoices

    def _notify_operations_for_invoicing(self):
        """Notify operations manager that part-time staff completed service and needs invoicing"""
        self.ensure_one()

        # Get operations manager group
        ops_group = self.env.ref('health_base.group_healthcare_operations_manager', raise_if_not_found=False)
        if not ops_group:
            _logger.warning('Operations Manager group not found for notification')
            return

        # Get all operations managers
        ops_managers = ops_group.users

        if not ops_managers:
            _logger.warning('No Operations Managers found for invoicing notification')
            return

        # Create activity for each operations manager
        activity_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        if not activity_type:
            _logger.warning('Todo activity type not found')
            return

        for manager in ops_managers:
            self.activity_schedule(
                activity_type_id=activity_type.id,
                summary=f'Create Invoice for Completed Service: {self.name}',
                note=f"""
                    <p><strong>Service completed by part-time staff - requires Operations invoicing</strong></p>
                    <ul>
                        <li><strong>Booking:</strong> {self.name}</li>
                        <li><strong>Patient:</strong> {self.patient_id.name}</li>
                        <li><strong>Service:</strong> {self._get_service_type_label()}</li>
                        <li><strong>Completed By:</strong> {self.lead_staff_id.name} (Part-Time Staff)</li>
                        <li><strong>Completion Date:</strong> {self.actual_end_datetime.strftime('%Y-%m-%d %H:%M') if self.actual_end_datetime else 'N/A'}</li>
                    </ul>
                    <p><strong>Completion Notes:</strong></p>
                    <p>{self.completion_notes or 'No additional notes provided'}</p>
                    <p><em>Please create and finalize the invoice for this completed service.</em></p>
                """,
                user_id=manager.id
            )

        # Log message in chatter (no email required, just internal note)
        try:
            self.message_post(
                body=f"""
                    <p><strong>Service Completed by Part-Time Staff</strong></p>
                    <p>Assigned staff: {self.lead_staff_id.name} (Part-Time)</p>
                    <p>Operations team has been notified to create invoice.</p>
                """,
                subject='Service Completed - Requires Operations Invoicing',
                message_type='notification'
            )
        except Exception as msg_err:
            # Log the error but don't fail the notification process
            _logger.warning(f'Could not post chatter message for FSO {self.name}: {str(msg_err)}')

    def action_complete_service(self):
        """Complete the service - different workflow for part-time vs full-time staff"""
        self.ensure_one()

        # Mandatory validation: Clinical notes must be submitted
        if not self.clinical_notes_submitted:
            raise UserError(_(
                'Clinical notes are required before completing the service.\n\n'
                'Please fill in at least one of the following:\n'
                '• Clinical Notes\n'
                '• Treatment Performed'
            ))

        # Mandatory validation: Invoice/Quote must exist OR service package must be present (prepaid)
        if not self.invoice_submitted and not self.package_id:
            raise UserError(_(
                'Invoice or Quote is required before completing the service.\n\n'
                'Alternatively, a service package must be assigned if payment is prepaid.\n'
                'Please create a quote with service items or assign a service package.'
            ))

        # Check if staff can create invoice
        if self._check_invoice_creation_permission():
            # Full-time staff: Service completed successfully
            # Move to Completed stage - staff can create invoice and process payment later
            completed_stage = self.env['health.fieldservice.stage'].search([
                ('state', '=', 'completed'),
                ('active', '=', True)
            ], order='sequence', limit=1)

            if not completed_stage:
                _logger.warning('No Completed stage found')

            self.write({
                'stage_id': completed_stage.id if completed_stage else False,
                'state': 'completed',
                'actual_end_datetime': fields.Datetime.now(),
            })

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Service Completed'),
                    'message': _('Service marked as completed. Create invoice and process payment when ready.'),
                    'type': 'success',
                    'sticky': False,
                }
            }
        else:
            # Part-time/casual staff: Move to Completed-Pending Invoice stage
            completion_note = f'Completed by part-time staff ({self.lead_staff_id.name if self.lead_staff_id else "staff"}) - requires Operations invoicing'

            # Find Completed-Pending Invoice stage
            completed_pending_stage = self.env['health.fieldservice.stage'].search([
                ('state', '=', 'completed_pending_invoice'),
                ('active', '=', True)
            ], order='sequence', limit=1)

            if not completed_pending_stage:
                _logger.warning('No Completed-Pending Invoice stage found')
                # Fallback to completed stage
                completed_pending_stage = self.env['health.fieldservice.stage'].search([
                    ('state', '=', 'completed'),
                    ('active', '=', True)
                ], order='sequence', limit=1)

            self.write({
                'stage_id': completed_pending_stage.id if completed_pending_stage else False,
                'state': 'completed_pending_invoice',
                'actual_end_datetime': fields.Datetime.now(),
                'completion_notes': completion_note,
            })

            # NOTE: Invoice is already created by nurse during quote verification
            # No additional notification needed for invoice creation

            # Return notification
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Service Completed'),
                    'message': _('Service completed successfully. Invoice has been created during quote verification.'),
                    'type': 'success',
                    'sticky': False,
                }
            }

    def action_close_fso(self):
        """Close the FSO after completion (final state) - called after cash collection"""
        self.ensure_one()

        # Validate that we're in the right state to close
        if self.state not in ['completed', 'completed_pending_invoice']:
            raise UserError(_(
                'Booking can only be closed from Completed or Completed-Pending Invoice stages.\n'
                'Current stage: %s'
            ) % dict(self._fields['state'].selection).get(self.state))

        # Find Closed stage
        closed_stage = self.env['health.fieldservice.stage'].search([
            ('state', '=', 'closed'),
            ('active', '=', True)
        ], order='sequence', limit=1)

        if not closed_stage:
            raise UserError(_('No Closed stage found. Please configure booking stages properly.'))

        self.write({
            'stage_id': closed_stage.id,
            'state': 'closed',
        })

        # Post message to chatter
        try:
            self.message_post(
                body=_('✅ <strong>Booking Closed:</strong> Cash collected by Operations Manager. Booking moved to Closed stage.'),
                message_type='notification',
                subtype_xmlid='mail.mt_note'
            )
        except Exception:
            pass  # Silently fail - no email notifications required

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Booking Closed'),
                'message': _('Booking has been closed successfully. Cash collection recorded.'),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_cancel_booking(self):
        """Cancel the booking - opens wizard for structured cancellation"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Cancel Booking',
            'res_model': 'health.booking.cancel.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_booking_id': self.id}
        }

    def cancel_with_reason(self, cancellation_reason_id, cancellation_notes):
        """Cancel booking with structured cancellation data"""
        self.ensure_one()

        # Release reserved service from package before cancelling
        if self.package_id:
            self._release_package_service()

        self.write({
            'state': 'cancelled',
            'cancellation_reason_id': cancellation_reason_id,
            'cancelled_by': self.env.user.id,
            'cancellation_date': fields.Datetime.now(),
            'cancellation_notes': cancellation_notes,
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
    
    # ============================================================================
    # QUOTE/SALES ORDER ACTION METHODS
    # ============================================================================
    
    def action_create_quote(self):
        """Create a healthcare quote/sales order for this FSO"""
        self.ensure_one()
        
        # Check if quote already exists
        if self.sale_order_id:
            return self.action_view_quote()
        
        # Create quote and show popup
        quote = self._create_quote_with_lines()
        if quote:
            self.sale_order_id = quote.id
            return self._open_quote_popup(quote)
        else:
            raise UserError(_('Failed to create quote. Please check patient and pricing information.'))
    
    def action_create_and_open_quote(self):
        """Create quote and immediately open in popup (for button click)"""
        return self.action_create_quote()
    
    def action_check_and_open_quote_if_needed(self):
        """Check if quote exists and open popup if needed after FSO save"""
        self.ensure_one()
        if self.env.user.has_group('health_base.group_healthcare_operations_manager'):
            if self.sale_order_id and not self.sale_order_id.order_line:
                # Quote exists but is empty - open it for editing
                return self._open_quote_popup(self.sale_order_id)
        return False
    
    def _create_quote_with_lines(self):
        """Create quote with all necessary lines and validation"""
        # Get default pricelist (first found or create one)
        pricelist = self.env['product.pricelist'].search([('currency_id', '=', self.env.company.currency_id.id)], limit=1)
        if not pricelist:
            pricelist = self.env['product.pricelist'].create({
                'name': 'Healthcare Services Pricelist',
                'currency_id': self.env.company.currency_id.id,
            })
        
        # Create sales order with FSO data
        quote_vals = {
            'partner_id': self.patient_id.id,
            'origin': self.name,
            'pricelist_id': pricelist.id,
            'state': 'draft',
            'note': f'Healthcare Quote for {self._get_service_type_label()} - {self.patient_id.name}',
        }
        
        quote = self.env['sale.order'].create(quote_vals)
        
        # Add service lines to quote if we have pricing info
        self._add_quote_lines(quote)
        
        # Update pricing notes if advanced pricing is enabled
        if hasattr(quote, '_update_pricing_notes') and quote.use_advanced_pricing:
            quote._update_pricing_notes()
        
        return quote
    
    def action_view_quote(self):
        """View the healthcare quote"""
        self.ensure_one()
        if not self.sale_order_id:
            raise UserError(_('No quote has been created for this Booking yet.'))
        
        return self._open_quote_popup(self.sale_order_id)
    
    def action_view_all_quotes(self):
        """View all quotes related to this FSO"""
        self.ensure_one()
        
        # Find all quotes related to this FSO
        quote_ids = []
        if self.sale_order_id:
            quote_ids.append(self.sale_order_id.id)
        
        # Search for additional quotes by origin
        additional_quotes = self.env['sale.order'].search([
            ('origin', '=', self.name)
        ])
        quote_ids.extend(additional_quotes.ids)
        
        if not quote_ids:
            raise UserError(_('No quotes have been created for this Booking yet.'))
        
        if len(quote_ids) == 1:
            return self._open_quote_popup(self.env['sale.order'].browse(quote_ids[0]))
        else:
            # Multiple quotes - open list view
            return {
                'name': _('Quotes for %s') % self.name,
                'type': 'ir.actions.act_window',
                'res_model': 'sale.order',
                'domain': [('id', 'in', quote_ids)],
                'view_mode': 'list,form',
                'target': 'current',
            }
    
    def _open_quote_popup(self, quote):
        """Open quote in popup form to keep FSO visible in background"""
        view_id = self.env.ref('health_fieldservice.view_healthcare_quote_form_custom').id
        action = {
            'name': _('Healthcare Quote - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': quote.id,
            'view_mode': 'form',
            'views': [[view_id, 'form']],  # Required by Odoo 18 web framework for action preprocessing
            'target': 'new',  # Opens in popup
            'context': {
                'form_view_initial_mode': 'edit',
                'healthcare_context': True,
                'fso_id': self.id,
            }
        }
        return action
    
    def _add_quote_lines(self, quote):
        """Add service lines to the quote based on FSO data"""
        # Get or create healthcare service products
        if self.base_price and self.base_price > 0:
            service_product = self._get_or_create_service_product()
            if service_product:
                self.env['sale.order.line'].create({
                    'order_id': quote.id,
                    'product_id': service_product.id,
                    'name': f'{dict(self._fields["service_type"].selection)[self.service_type]} - {self.patient_id.name}',
                    'product_uom_qty': self.estimated_duration or 1,
                    'price_unit': self.base_price / (self.estimated_duration or 1),
                })
        
        # Add additional charges as separate lines
        if self.travel_charge and self.travel_charge > 0:
            travel_product = self._get_or_create_travel_product()
            if travel_product:
                self.env['sale.order.line'].create({
                    'order_id': quote.id,
                    'product_id': travel_product.id,
                    'name': f'Travel Charge ({self.travel_distance} km)',
                    'product_uom_qty': 1,
                    'price_unit': self.travel_charge,
                })
    
    def _get_or_create_service_product(self):
        """Get or create a service product for healthcare services"""
        product_name = f'Healthcare Service - {dict(self._fields["service_type"].selection)[self.service_type]}'
        product = self.env['product.product'].search([('name', '=', product_name)], limit=1)
        if not product:
            product = self.env['product.product'].create({
                'name': product_name,
                'type': 'service',
                'list_price': self.base_price or 0,
                'categ_id': self.env.ref('product.product_category_3').id,  # Services category
            })
        return product
    
    def _get_or_create_travel_product(self):
        """Get or create a travel charge product"""
        product_name = 'Travel Charge'
        product = self.env['product.product'].search([('name', '=', product_name)], limit=1)
        if not product:
            product = self.env['product.product'].create({
                'name': product_name,
                'type': 'service',
                'list_price': 0,  # Variable pricing
                'categ_id': self.env.ref('product.product_category_3').id,  # Services category
            })
        return product
    
    def _auto_create_quote(self):
        """Automatically create quote when FSO is saved (for Operations Manager)"""
        self.ensure_one()
        
        # Only create if no quote exists yet
        if self.sale_order_id:
            return
        
        # Only create if we have basic required data
        if not self.patient_id:
            return
        
        try:
            # Create quote silently in background
            quote = self._create_quote_silent()
            if quote:
                self.sale_order_id = quote.id
                _logger.info(f'Auto-created quote {quote.name} for FSO {self.name}')
        except Exception as e:
            _logger.warning(f'Failed to auto-create quote for FSO {self.name}: {e}')
            # Don't raise exception - quote creation is optional
    
    def _create_quote_silent(self):
        """Create quote silently without UI interaction"""
        # Get default pricelist
        pricelist = self.env['product.pricelist'].search([('currency_id', '=', self.env.company.currency_id.id)], limit=1)
        if not pricelist:
            pricelist = self.env['product.pricelist'].create({
                'name': 'Healthcare Services Pricelist',
                'currency_id': self.env.company.currency_id.id,
            })
        
        # Create sales order
        quote_vals = {
            'partner_id': self.patient_id.id,
            'origin': self.name,
            'pricelist_id': pricelist.id,
            'state': 'draft',
            'note': f'Auto-generated Healthcare Quote for {self._get_service_type_label()} - {self.patient_id.name}',
        }
        
        quote = self.env['sale.order'].create(quote_vals)
        
        # Add basic service lines
        self._add_quote_lines(quote)
        
        # Update pricing notes if advanced pricing is enabled
        if hasattr(quote, '_update_pricing_notes') and quote.use_advanced_pricing:
            quote._update_pricing_notes()
        
        return quote
    
    def action_view_communications(self):
        """View communications related to this booking"""
        self.ensure_one()
        return {
            'name': _('Communications'),
            'type': 'ir.actions.act_window',
            'res_model': 'health.fieldservice.communication',
            'view_mode': 'list,form',
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
            raise UserError(_("Staff member is already assigned to this Booking"))
        
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
            'view_mode': 'list,form',
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
        """Return all active stages for kanban view, ordered by sequence"""
        return self.env['health.fieldservice.stage'].search([('active', '=', True)], order='sequence')
    
    def name_get(self):
        """Custom name display - format: Client Name (Booking ID)"""
        result = []
        for record in self:
            if record.patient_id:
                name = f"{record.patient_id.name} ({record.name})"
            else:
                name = record.name
            result.append((record.id, name))
        return result
    
    def action_manual_assign_staff(self):
        """Open timeline view for manual staff assignment"""
        self.ensure_one()

        _logger.info("=" * 100)
        _logger.info("📋 ACTION_STAFF_ASSIGNMENT TRIGGERED")
        _logger.info("=" * 100)
        _logger.info("Booking: FSO-%s (ID: %s)", self.name, self.id)
        _logger.info("Patient: %s", self.patient_id.name if self.patient_id else "N/A")
        _logger.info("Scheduled DateTime: %s", self.scheduled_datetime)
        _logger.info("=" * 100)

        # Check if template exists for this booking
        existing_template = self.env['health.staff.assignment'].search([
            ('state', '=', 'template'),
            ('fso_id', '=', self.id)
        ], limit=1)

        if not existing_template:
            # Create new template for this booking
            template = self.env['health.staff.assignment'].create({
                'fso_id': self.id,
                'staff_id': False,
                'assignment_date': self.scheduled_datetime or fields.Datetime.now(),
                # planned_start_time and planned_end_time are auto-computed from FSO
                'assignment_status': 'assigned',
                'state': 'template',
                'assignment_type': self._get_assignment_type(),
                'priority': self.priority or '1',
            })
            _logger.info("📌 CREATED NEW TEMPLATE ASSIGNMENT:")
            _logger.info("   Template ID: %s", template.id)
            _logger.info("   FSO ID: %s", self.id)
            _logger.info("   Scheduled DateTime: %s", self.scheduled_datetime)
        else:
            _logger.info("📌 REUSING EXISTING TEMPLATE:")
            _logger.info("   Template ID: %s", existing_template.id)

        # Open timeline view focused on appointment date with DAY view
        # Calculate the appointment day for timeline focus
        appointment_datetime = self.scheduled_datetime or fields.Datetime.now()
        appointment_date = appointment_datetime.strftime('%Y-%m-%d')

        # Get view references for explicit view specification
        timeline_view = self.env.ref('health_fieldservice.health_staff_assignment_timeline_view', raise_if_not_found=False)
        list_view = self.env.ref('health_fieldservice.view_health_staff_assignment_list', raise_if_not_found=False)
        form_view = self.env.ref('health_fieldservice.view_health_staff_assignment_form', raise_if_not_found=False)

        views = []
        if timeline_view:
            views.append((timeline_view.id, 'timeline'))
        if list_view:
            views.append((list_view.id, 'list'))
        if form_view:
            views.append((form_view.id, 'form'))

        # Prepare context with FSO auto-population and DAY view focus
        ctx = {
            'default_fso_id': self.id,  # Auto-populate FSO when creating new assignments
            'default_assignment_date': appointment_datetime,  # Used by template default_get()
            'default_staff_id': False,  # Leave staff unassigned for drag-drop
            'date': appointment_date,  # Timeline focus date (YYYY-MM-DD format)
            'initial_date': appointment_date,  # Timeline focus date (backup key)
        }

        _logger.info("📤 CONTEXT BEING PASSED TO TIMELINE:")
        _logger.info("   default_fso_id: %s", ctx['default_fso_id'])
        _logger.info("   default_assignment_date: %s", ctx['default_assignment_date'])
        _logger.info("   Timeline Focus Date: %s", ctx['date'])
        _logger.info("=" * 100)

        return {
            'name': _('Staff Assignment - %s') % appointment_date,  # Page title with date
            'type': 'ir.actions.act_window',
            'res_model': 'health.staff.assignment',
            'view_mode': 'timeline,list,form',
            'views': views if views else False,
            'target': 'current',
            'domain': [('state', '!=', 'template')],  # Hide template assignments from view
            'context': ctx,
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
    
    def action_auto_open_quote_after_catalog(self):
        """Auto-open Healthcare Quote after returning from catalog"""
        self.ensure_one()

        # Check if we have a quote to open
        if not self.sale_order_id:
            return False

        # Open the Healthcare Quote form immediately
        return {
            'type': 'ir.actions.act_window',
            'name': f'Healthcare Quote - {self.name}',
            'res_model': 'sale.order',
            'res_id': self.sale_order_id.id,
            'view_mode': 'form',
            'view_id': self.env.ref('health_fieldservice.view_healthcare_quote_form_custom').id,
            'target': 'main',  # Open in main window, not dialog
            'context': {
                'from_catalog_redirect': True,
            }
        }

    def action_open_fso_dashboard(self):
        """Open the Booking workflow dashboard"""
        self.ensure_one()

        # Navigate to the client dashboard with booking context
        return {
            'type': 'ir.actions.act_window',
            'name': _('Booking Workflow Dashboard'),
            'res_model': 'res.partner',
            'res_id': self.patient_id.id,
            'view_mode': 'form',
            'view_id': self.env.ref('health_base.view_health_patient_form').id,
            'target': 'current',
            'context': {
                'active_tab': 'address_info',  # Default to first tab
                'booking_id': self.id,  # Pass booking context
            }
        }
