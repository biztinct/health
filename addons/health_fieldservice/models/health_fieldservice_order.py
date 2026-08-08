# -*- coding: utf-8 -*-

from markupsafe import Markup
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from odoo.addons.health_base.models import geo_utils
from datetime import datetime, timedelta
import json
import pytz
import logging
import copy

_logger = logging.getLogger(__name__)


def _selection_labels(record, field_name):
    return dict(record._fields[field_name]._description_selection(record.env))


def _selection_service_type(model):
    return [
        ('home_visit', model.env._('Home Visit')),
        ('clinic_visit', model.env._('Clinic Visit')),
        ('consultation', model.env._('Consultation')),
        ('emergency', model.env._('Emergency Care')),
        ('follow_up', model.env._('Follow-up Care')),
        ('preventive', model.env._('Preventive Care')),
        ('rehabilitation', model.env._('Rehabilitation')),
        ('telemedicine', model.env._('Telemedicine/Online')),
        ('vaccination', model.env._('Vaccination')),
        ('diagnostic', model.env._('Diagnostic Services')),
    ]


def _selection_priority(model):
    return [
        ('0', model.env._('Low')),
        ('1', model.env._('Normal')),
        ('2', model.env._('High')),
        ('3', model.env._('Urgent')),
        ('4', model.env._('Emergency')),
    ]


def _selection_fso_state(model):
    # Labels follow the legacy booking-status wording (Trạng thái lịch hẹn).
    return [
        ('draft', model.env._('Draft')),
        ('confirmed', model.env._('New Booking')),
        ('assigned', model.env._('Assigned')),
        ('in_progress', model.env._('In Progress')),
        ('completed', model.env._('Completed')),
        ('completed_pending_invoice', model.env._('Completed - Pending Invoice')),
        ('cancelled', model.env._('Cancelled')),
        ('closed', model.env._('Closed')),
    ]


def _selection_service_location(model):
    # Labels follow the legacy service-location wording (Dịch vụ tại).
    return [
        ('home', model.env._('At Home')),
        ('clinic', model.env._('At Clinic')),
        ('hospital', model.env._('Hospital')),
        ('nursing_home', model.env._('Nursing Home')),
        ('office', model.env._('Office')),
        ('online', model.env._('Telemedicine')),
        ('other', model.env._('Other Location')),
    ]


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
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin', 'health.lifecycle.mixin']
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

    active = fields.Boolean(
        default=True,
        help='If unchecked, the booking is archived.'
    )
    
    @api.depends('name', 'patient_id')
    def _compute_display_name(self):
        """Compute clean display name for views - format: Client Name (Booking ID)"""
        for record in self:
            if record.patient_id and record.name:
                record.display_name = f"{record.patient_id.name} ({record.name})"
            else:
                record.display_name = record.name or 'New Booking'

    calendar_name = fields.Char(
        compute='_compute_calendar_name', store=True)

    @api.depends('patient_id', 'patient_id.name', 'patient_id.patient_code')
    def _compute_calendar_name(self):
        for record in self:
            if record.patient_id:
                code = record.patient_id.patient_code or ''
                record.calendar_name = f"{record.patient_id.name} ({code})" if code else record.patient_id.name
            else:
                record.calendar_name = record.name or 'New Booking'

    def _get_service_type_label(self):
        """Get the human-readable label for service type"""
        self.ensure_one()
        service_type_dict = _selection_labels(self, 'service_type')
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
        # deleted=False is explicit because booking tables run with
        # deleted_test=False in the context (to show Delete requests), and
        # that context would otherwise leak into this dropdown's name_search.
        domain=[('is_patient', '=', True), ('deleted', '=', False)],
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
    patient_national_id = fields.Char('National ID', related='patient_id.national_id', readonly=True)
    patient_address_display = fields.Text('Client Address', related='patient_id.vietnamese_address', readonly=True)
    
    # Catchment Province for staff filtering
    patient_catchment_province_id = fields.Many2one(
        'health.catchment.province',
        string='Client Catchment Province',
        related='patient_id.catchment_province_id',
        store=True,
        help='Catchment province of the client - used to filter staff with matching healthcare facility'
    )

    catchment_province_id = fields.Many2one(
        'health.catchment.province',
        string='Catchment Area',
        compute='_compute_catchment_province_id',
        store=True,
        readonly=True,
        help='Catchment area used for filtering and access control'
    )

    @api.depends('patient_id.catchment_province_id', 'patient_id.primary_facility_id.catchment_province_id',
                 'facility_id.catchment_province_id')
    def _compute_catchment_province_id(self):
        for record in self:
            patient_catchment = record.patient_id._get_health_catchment_province() if record.patient_id else False
            record.catchment_province_id = (
                patient_catchment
                or record.facility_id.catchment_province_id
                or False
            )

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
    
    service_type = fields.Selection(
        _selection_service_type,
        string='Service Type', required=True, tracking=True, default='home_visit',
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
    category_of_service_id = fields.Many2one(
        'product.category',
        string='Category of Service',
        help='Service category from the pricelist for this catchment area'
    )
    required_equipment = fields.Text('Required Equipment', help='Equipment or supplies required for this service')
    intake_notes = fields.Text('Intake Notes', help='Additional intake assessment notes')

    # Clinical Priority (From Client Requirements)
    priority = fields.Selection(
        _selection_priority,
        string='Priority', default='1', tracking=True)
    
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

    booking_timezone = fields.Char(
        'Booking Timezone',
        compute='_compute_booking_timezone',
        store=True,
        readonly=False,
        help='Timezone for this booking. Derived from facility timezone, '
             'falls back to catchment province timezone.'
    )

    @api.depends('facility_id', 'facility_id.timezone', 'patient_catchment_province_id',
                 'patient_catchment_province_id.timezone')
    def _compute_booking_timezone(self):
        """Compute booking timezone from facility, fallback to catchment province."""
        for record in self:
            if record.facility_id and record.facility_id.timezone:
                record.booking_timezone = record.facility_id.timezone
            elif record.patient_catchment_province_id and record.patient_catchment_province_id.timezone:
                record.booking_timezone = record.patient_catchment_province_id.timezone
            else:
                record.booking_timezone = record.booking_timezone or 'Asia/Ho_Chi_Minh'

    def _get_booking_tz(self):
        """Helper: return the effective timezone string for this booking."""
        self.ensure_one()
        return self.booking_timezone or 'Asia/Ho_Chi_Minh'
    
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

    @api.depends('scheduled_datetime', 'booking_timezone')
    def _compute_scheduled_date(self):
        for record in self:
            if record.scheduled_datetime:
                utc_dt = pytz.UTC.localize(record.scheduled_datetime)
                bk_tz = pytz.timezone(record._get_booking_tz())
                local_dt = utc_dt.astimezone(bk_tz)
                record.scheduled_date = local_dt.date()
            else:
                record.scheduled_date = False
    
    @api.depends('scheduled_datetime', 'booking_timezone')
    def _compute_scheduled_time(self):
        for record in self:
            if record.scheduled_datetime:
                utc_dt = pytz.UTC.localize(record.scheduled_datetime)
                bk_tz = pytz.timezone(record._get_booking_tz())
                local_dt = utc_dt.astimezone(bk_tz)
                record.scheduled_time = local_dt.hour + local_dt.minute / 60.0
            else:
                record.scheduled_time = 0.0

    @api.depends('scheduled_datetime', 'booking_timezone')
    def _compute_scheduled_month(self):
        """Compute month-year label for kanban grouping"""
        for record in self:
            if record.scheduled_datetime:
                utc_dt = pytz.UTC.localize(record.scheduled_datetime)
                bk_tz = pytz.timezone(record._get_booking_tz())
                local_dt = utc_dt.astimezone(bk_tz)
                record.scheduled_month = local_dt.strftime('%B %Y')
            else:
                record.scheduled_month = 'Unscheduled'

    @api.depends('assignment_ids')
    def _compute_assignment_count(self):
        """Compute the number of staff assignments for this FSO"""
        for record in self:
            record.assignment_count = len(record.assignment_ids.filtered(lambda a: a.state != 'template'))

    @api.depends('assigned_staff_ids', 'assigned_doctor_ids')
    def _compute_has_staff_assigned(self):
        """Compute if staff or doctors have been assigned"""
        for record in self:
            record.has_staff_assigned = bool(record.assigned_staff_ids or record.assigned_doctor_ids)
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
    
    @api.depends('assignment_ids.staff_id', 'assignment_ids.assignment_role', 'assignment_ids.staff_id.is_doctor_role')
    def _compute_assigned_staff(self):
        """Compute assigned staff from assignment records"""
        for record in self:
            # sudo the role read: is_doctor_role derives from access_role_id, a
            # private employee field non-HR users (e.g. nurses) cannot read, which
            # would otherwise break this compute whenever they load bookings.
            staff_ids = record.assignment_ids.filtered(
                lambda a: a.state != 'template'
                and a.assignment_role != 'doctor'
                and a.staff_id
                and not a.staff_id.sudo().is_doctor_role
            ).mapped('staff_id.id')
            record.assigned_staff_ids = [(6, 0, staff_ids)]

    def _inverse_assigned_staff(self):
        """Create/update staff assignments when assigned_staff_ids is modified"""
        for record in self:
            current_staff_ids = set(record.assignment_ids.filtered(
                lambda a: a.state != 'template' and a.assignment_role != 'doctor'
            ).mapped('staff_id.id'))
            new_staff_ids = set(record.assigned_staff_ids.ids)

            # Staff to add - create new assignments
            staff_to_add = new_staff_ids - current_staff_ids
            for staff_id in staff_to_add:
                staff = self.env['hr.employee'].browse(staff_id)
                # Skip doctors here (handled separately via assigned_doctor_ids)
                if staff.is_doctor_role:
                    continue

                # Enforce single lead: first non-doctor is lead, subsequent are support
                existing_lead = record.assignment_ids.filtered(
                    lambda a: a.state != 'template' and a.assignment_role == 'lead'
                )
                role = 'lead' if not existing_lead else 'support'

                new_assignment = self.env['health.staff.assignment'].create({
                    'fso_id': record.id,
                    'staff_id': staff_id,
                    'assignment_date': record.scheduled_datetime or fields.Datetime.now(),
                    'assignment_role': role,
                    'assignment_status': 'assigned',
                    'state': 'draft',
                    'assignment_type': record._get_assignment_type(),
                    'priority': record.priority or '1',
                })

                # For confirmed bookings, notify new staff about the assignment
                if record.state in ('confirmed', 'assigned', 'in_progress'):
                    try:
                        record._send_staff_assignment_notification(staff, new_assignment)
                    except Exception as e:
                        _logger.warning('Failed to send reassignment notification: %s', e)

            # Staff to remove - delete assignments
            staff_to_remove = current_staff_ids - new_staff_ids
            if staff_to_remove:
                assignments_to_remove = record.assignment_ids.filtered(
                    lambda a: a.state != 'template' and a.staff_id.id in staff_to_remove
                )
                assignments_to_remove.unlink()

    @api.depends('assignment_ids.staff_id', 'assignment_ids.assignment_role')
    def _compute_lead_staff(self):
        """Compute lead staff from assignment records"""
        for record in self:
            # Filter for lead assignments - get the staff member from the first one
            lead_assignment = record.assignment_ids.filtered(
                lambda a: a.state != 'template' and a.assignment_role == 'lead'
            )

            # Extract the first lead staff member if it exists
            if lead_assignment:
                first_assignment = lead_assignment[0]
                if first_assignment and first_assignment.staff_id:
                    record.lead_staff_id = first_assignment.staff_id
                else:
                    record.lead_staff_id = False
            else:
                record.lead_staff_id = False

    @api.depends('assignment_ids.staff_id', 'assignment_ids.assignment_role', 'assignment_ids.staff_id.job_title', 'primary_doctor_id')
    def _compute_assigned_doctors(self):
        """Compute assigned doctors from staff assignments or primary_doctor_id"""
        for record in self:
            doctor_ids = []

            # First check if primary_doctor_id is set
            if record.primary_doctor_id:
                doctor_ids.append(record.primary_doctor_id.id)

            # Look for doctors in assignments - check assignment_role first, then job_title
            # sudo the job_title read (private employee field, unreadable by nurses)
            doctor_assignments = record.assignment_ids.filtered(
                lambda a: a.state != 'template' and a.staff_id and (
                    a.assignment_role == 'doctor' or
                    (a.staff_id.sudo().job_title and 'doctor' in a.staff_id.sudo().job_title.lower())
                )
            )
            doctor_ids.extend(doctor_assignments.mapped('staff_id.id'))

            # Remove duplicates while preserving order
            unique_doctor_ids = list(dict.fromkeys(doctor_ids))
            record.assigned_doctor_ids = [(6, 0, unique_doctor_ids)]

    def _inverse_assigned_doctors(self):
        """Create/update doctor assignments when assigned_doctor_ids is modified"""
        for record in self:
            current_doctor_ids = set(record.assignment_ids.filtered(
                lambda a: a.state != 'template' and a.assignment_role == 'doctor'
            ).mapped('staff_id.id'))
            new_doctor_ids = set(record.assigned_doctor_ids.ids)

            # Doctors to add - create new assignments
            doctors_to_add = new_doctor_ids - current_doctor_ids
            for doctor_id in doctors_to_add:
                self.env['health.staff.assignment'].create({
                    'fso_id': record.id,
                    'staff_id': doctor_id,
                    'assignment_date': record.scheduled_datetime or fields.Datetime.now(),
                    'assignment_role': 'doctor',
                    'assignment_status': 'assigned',
                    'state': 'draft',
                    'assignment_type': record._get_assignment_type(),
                    'priority': record.priority or '1',
                })

            # Doctors to remove - delete assignments
            doctors_to_remove = current_doctor_ids - new_doctor_ids
            if doctors_to_remove:
                assignments_to_remove = record.assignment_ids.filtered(
                    lambda a: a.state != 'template' and a.assignment_role == 'doctor' and a.staff_id.id in doctors_to_remove
                )
                assignments_to_remove.unlink()

    def _inverse_scheduled_date(self):
        for record in self:
            if record.scheduled_date and record.scheduled_time:
                # Combine date and time with proper timezone handling
                hours = int(record.scheduled_time)
                minutes = int((record.scheduled_time - hours) * 60)
                
                # Create naive datetime first
                naive_dt = datetime.combine(record.scheduled_date, datetime.min.time().replace(hour=hours, minute=minutes))
                
                bk_tz = pytz.timezone(record._get_booking_tz())
                local_dt = bk_tz.localize(naive_dt)
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
                
                bk_tz = pytz.timezone(record._get_booking_tz())
                local_dt = bk_tz.localize(naive_dt)
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
        inverse='_inverse_assigned_staff',
        store=False,
        readonly=False,
        domain=[
            ('is_healthcare_staff', '=', True),
            ('employment_status', '=', 'active'),
            ('is_nurse_role', '=', True),
        ],
        help='All staff members assigned to this service (editable - creates/updates assignments)'
    )

    # Primary staff members
    lead_staff_id = fields.Many2one(
        'hr.employee',
        string='Lead Staff',
        compute='_compute_lead_staff',
        store=False,
        help='Primary staff member responsible for this service (computed from assignments with lead role)'
    )

    primary_doctor_id = fields.Many2one(
        'hr.employee',
        string='Primary Doctor',
        domain=[('is_healthcare_staff', '=', True), ('is_doctor_role', '=', True), ('employment_status', '=', 'active')],
        tracking=True
    )

    assigned_doctor_ids = fields.Many2many(
        'hr.employee',
        'fso_assigned_doctor_rel',
        'fso_id', 'doctor_id',
        string='Assigned Doctors',
        compute='_compute_assigned_doctors',
        inverse='_inverse_assigned_doctors',
        store=False,
        readonly=False,
        domain=[('is_healthcare_staff', '=', True), ('is_doctor_role', '=', True), ('employment_status', '=', 'active')],
        help='Doctors assigned from staff assignments (editable - creates/updates assignments with doctor role)'
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

    has_staff_assigned = fields.Boolean(
        'Has Staff Assigned',
        compute='_compute_has_staff_assigned',
        store=True,
        help='Whether staff or doctors have been assigned to this booking'
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
    
    service_location = fields.Selection(
        _selection_service_location,
        string='Service Location',
        required=True,
        default='home',
        tracking=True,
    )
    
    # Facility Information
    facility_id = fields.Many2one(
        'health.facility',
        string='Healthcare Facility',
        required=True,
        domain="[('active', '=', True), ('catchment_province_id', '=', patient_catchment_province_id)]",
        help='Facility where service will be provided. Timezone for booking is derived from this facility.'
    )

    @api.onchange('patient_catchment_province_id')
    def _onchange_patient_catchment_province(self):
        """Reset facility when catchment province changes (domain filter will update)"""
        if self.facility_id and self.facility_id.catchment_province_id != self.patient_catchment_province_id:
            self.facility_id = False
    
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
    state = fields.Selection(
        _selection_fso_state,
        string='Status', default='draft', tracking=True, required=True,
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

    is_rescheduled = fields.Boolean(
        'Rescheduled', default=False, copy=False, tracking=True,
        help='Set when the appointment date/time is moved after the booking was '
             'confirmed. Surfaces a "Rescheduled" tag on the booking.')

    operations_manager_id = fields.Many2one(
        'hr.employee', string='Operations Manager',
        related='facility_id.facility_manager_id', readonly=True,
        help='Operations manager of the facility handling this booking.')

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
    
    # Enhanced cancellation fields for Contact-First flow
    cancelled_by_client = fields.Char(
        'Cancelled By (Client Side)',
        help='Name of person on client side who cancelled'
    )
    
    cancellation_reported_by = fields.Char(
        'Reported By',
        help='Name of person who reported the cancellation'
    )
    
    cancellation_reporter_position = fields.Char(
        'Reporter Position',
        help='Position/role of person who reported cancellation'
    )
    
    last_visiting_staff_id = fields.Many2one(
        'hr.employee',
        string='Last Person Who Visited',
        help='For repeat clients - last staff member who visited this client'
    )

    # =========================================================================
    # COMMISSION & SERVICE FEE FIELDS (Contact-First Flow Requirements)
    # =========================================================================
    
    service_fee_vnd = fields.Monetary(
        'Service Fee',
        compute='_compute_service_fee_vnd',
        store=True,
        help='Total service amount from the linked quote',
        tracking=True,
    )
    
    # Commission tracking fields
    commission_due_to = fields.Many2one(
        'res.partner',
        string='Commission Due To',
        help='Person or entity who receives commission for this booking'
    )
    
    commission_percentage = fields.Float(
        'Commission %',
        help='Percentage of booking value as commission'
    )
    
    commission_duration = fields.Char(
        'Commission Duration',
        help='Duration for which commission is payable (e.g., "First 3 months")'
    )
    
    commission_amount = fields.Monetary(
        'Commission Amount',
        compute='_compute_commission_amount',
        store=True,
        help='Calculated commission amount: commission % of service fee',
    )

    @api.depends('sale_order_id', 'sale_order_id.amount_total')
    def _compute_service_fee_vnd(self):
        for record in self:
            record.service_fee_vnd = record.sale_order_id.amount_total if record.sale_order_id else 0.0

    @api.depends('service_fee_vnd', 'commission_percentage')
    def _compute_commission_amount(self):
        for record in self:
            if record.service_fee_vnd and record.commission_percentage:
                record.commission_amount = record.service_fee_vnd * (record.commission_percentage / 100)
            else:
                record.commission_amount = 0.0
    
    # Invoice authorization tracking (Nurses/Doctors cannot raise invoice)
    invoice_authorized = fields.Boolean(
        'Invoice Authorized',
        default=True,
        help='Whether the booking creator is authorized to raise invoices'
    )
    
    invoice_notification_sent = fields.Boolean(
        'OM Invoice Notification Sent',
        default=False,
        help='Whether notification was sent to OM for invoice creation'
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

    quote_state = fields.Selection(
        related='sale_order_id.state',
        string='Quote Status',
        readonly=True
    )

    quote_line_ids = fields.One2many(
        related='sale_order_id.order_line',
        string='Quote Lines',
        readonly=True,
    )

    def get_services_packages_display_data(self):
        self.ensure_one()
        currency = self.currency_id
        result = {
            'has_quote': bool(self.sale_order_id),
            'has_packages': False,
            'services': [],
            'service_count': 0,
            'total_amount': 0,
            'currency_symbol': currency.symbol or 'đ',
            'currency_position': currency.position or 'after',
            'packages': [],
        }

        if self.sale_order_id:
            so = self.sale_order_id
            for line in so.order_line.filtered(lambda l: not l.display_type):
                rules = []
                base = line.price_unit
                try:
                    rules = line._pricing_rule_chips()
                    base = line.base_price or line.product_id.list_price or line.price_unit
                except Exception:
                    rules = []
                result['services'].append({
                    'name': line.product_id.name or line.name or '',
                    'qty': line.product_uom_qty,
                    'price': line.price_subtotal,
                    'base': base,
                    'rules': rules,
                })
            result['service_count'] = len(result['services'])
            result['total_amount'] = so.amount_total
            # Booking-condition chips (Home Visit, After Hours, Distance, Holiday…)
            try:
                bd = so._build_pricing_breakdown_data() or {}
                result['factors'] = bd.get('factors', []) if bd else []
            except Exception:
                result['factors'] = []

        if hasattr(self, 'package_ids') and self.package_ids:
            result['has_packages'] = True
            for pkg in self.package_ids:
                total = pkg.total_services or 1
                consumed = pkg.consumed_services or 0
                remaining = pkg.remaining_services
                pct = min(100, (consumed / total) * 100) if total > 0 else 100
                if remaining == 0:
                    color, rem_cls = 'red', 'zero'
                elif remaining <= 2:
                    color, rem_cls = 'amber', 'low'
                else:
                    color, rem_cls = 'green', 'plenty'
                result['packages'].append({
                    'name': pkg.name or 'Package',
                    'total': total,
                    'consumed': consumed,
                    'remaining': remaining,
                    'state': pkg.state or 'active',
                    'pct': round(pct, 1),
                    'color': color,
                    'remaining_class': rem_cls,
                })

        return result

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
    parking_charge = fields.Monetary('Parking Charge', help='Parking/access fee (gửi xe)')

    @api.depends('base_price', 'travel_charge', 'urgency_charge', 'equipment_charge', 'after_hours_charge', 'parking_charge')
    def _compute_total_price(self):
        for record in self:
            record.total_price = (
                record.base_price +
                record.travel_charge +
                record.urgency_charge +
                record.equipment_charge +
                record.after_hours_charge +
                record.parking_charge
            )
    
    # Payment tracking
    payment_status = fields.Selection([
        ('pending', 'Unpaid'),
        ('partial', 'Partial Payment'),
        ('paid', 'Paid'),
        ('refunded', 'Refunded'),
    ], string='Payment Status', compute='_compute_payment_status')
    
    # Insurance Information
    has_insurance = fields.Boolean('Has Insurance', compute='_compute_has_insurance', store=True)
    insurance_provider = fields.Char('Insurance Provider', related='patient_id.insurance_provider')
    
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

    @api.depends('clinical_note_ids')
    def _compute_clinical_notes_status(self):
        for record in self:
            record.clinical_notes_submitted = bool(record.clinical_note_ids)
            record.clinical_note_count = len(record.clinical_note_ids)


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

    # Clinical Notes (One2many — each note is an immutable record)
    clinical_note_ids = fields.One2many(
        'health.clinical.note', 'order_id',
        string='Clinical Notes',
    )
    clinical_note_count = fields.Integer(
        compute='_compute_clinical_notes_status', store=True,
    )

    # Legacy flat fields kept for DB compatibility (no longer used in UI)
    clinical_notes = fields.Html('Clinical Notes (Legacy)')
    treatment_performed = fields.Text('Treatment Performed (Legacy)')
    medications_prescribed = fields.Text('Medications Prescribed (Legacy)')
    patient_condition_before = fields.Text('Patient Condition Before (Legacy)')
    patient_condition_after = fields.Text('Patient Condition After (Legacy)')
    vital_signs = fields.Text('Vital Signs (Legacy)')
    clinical_image_ids = fields.Many2many(
        'ir.attachment', 'health_fso_clinical_image_rel',
        'fso_id', 'attachment_id', string='Clinical Images (Legacy)',
    )

    # Post-service procedure counts (also stored on sale.order for pricing engine)
    injection_count = fields.Integer('Injections Given', default=1,
        help='Number of injections administered during this visit (first included in base price)')
    medication_count = fields.Integer('Medications Given', default=1,
        help='Number of medications administered during this visit (first included in base price)')
    wound_count = fields.Integer('Wounds Treated', default=1,
        help='Number of wounds treated during this visit (first included in base price)')
    iv_fluid_count = fields.Integer('IV Fluid Bags', default=0,
        help='Number of IV fluid bags used during this visit')
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

    clinical_notes_submitted = fields.Boolean(
        'Clinical Notes Submitted',
        compute='_compute_clinical_notes_status',
        store=True,
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
    
    @api.onchange('scheduled_datetime')
    def _onchange_scheduled_datetime_duration(self):
        """Preserve scheduled_duration default when scheduled_datetime changes."""
        if not self.scheduled_duration or self.scheduled_duration < 1:
            self.scheduled_duration = 60

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
        """Create FSO with auto-generated reference and default stage.
        Booking number is NOT generated at creation - it is assigned when
        the booking moves to 'confirmed' (Booked) state.
        """
        for vals in vals_list:
            if vals.get('name', _('New Booking')) == _('New Booking'):
                vals['name'] = _('New Booking')
            
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
            # Check invoice authorization (Nurses/Doctors cannot raise invoices)
            order._check_invoice_authorization()
            # Compute one-way driving distance (facility -> client) for pricing/display
            order._update_travel_distance()

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
        
        # Capture old scheduled_datetime before write (for reschedule notifications)
        old_scheduled = {}
        if 'scheduled_datetime' in vals and vals['scheduled_datetime']:
            for record in self:
                if record.scheduled_datetime:
                    old_scheduled[record.id] = record.scheduled_datetime

        result = super().write(vals)

        # Flag a genuine reschedule: the appointment moved on a booking that was
        # already confirmed. Draft bookings are still being planned, so moving
        # them is not a reschedule.
        if old_scheduled and 'is_rescheduled' not in vals:
            moved_ids = [
                record.id for record in self
                if old_scheduled.get(record.id)
                and record.scheduled_datetime
                and record.scheduled_datetime != old_scheduled[record.id]
                and record.state in ('confirmed', 'assigned', 'in_progress')
                and not record.is_rescheduled
            ]
            if moved_ids:
                self.browse(moved_ids).write({'is_rescheduled': True})

        if 'active' in vals:
            assignments = self.with_context(active_test=False).mapped('assignment_ids')
            if assignments:
                assignments.write({'active': vals['active']})

        # Deleted bookings must vanish from staff schedules the same way
        # archived ones do; a restore brings the assignments back.
        if 'deleted' in vals:
            assignments = self.with_context(active_test=False).mapped('assignment_ids')
            if assignments:
                assignments.write({'active': not vals['deleted']})

        # Handle state transitions
        if 'state' in vals:
            self._handle_state_change(vals['state'])

        # Handle scheduling
        if 'scheduled_datetime' in vals and vals['scheduled_datetime']:
            self._handle_scheduling()
            # Resync all linked assignments' planned times to match the new FSO datetime
            from datetime import timedelta as td
            for record in self:
                new_dt = record.scheduled_datetime
                if new_dt and record.assignment_ids:
                    duration_minutes = record.scheduled_duration or 60
                    new_end = new_dt + td(minutes=duration_minutes)
                    non_template = record.assignment_ids.filtered(lambda a: a.state != 'template')
                    if non_template:
                        non_template.with_context(skip_multi_assignment_update=True).write({
                            'assignment_date': new_dt,
                            'planned_start_time': new_dt,
                            'planned_end_time': new_end,
                        })
                        _logger.info(
                            'Resynced %d assignments for %s to %s',
                            len(non_template), record.name, new_dt,
                        )
            # Notify assigned staff about rescheduling
            for record in self:
                if record.state in ('assigned', 'confirmed') and record.assignment_ids:
                    for assignment in record.assignment_ids.filtered(lambda a: a.state in ('assigned', 'confirmed') and a.staff_id):
                        record._send_staff_reschedule_notification(
                            assignment.staff_id,
                            old_datetime=old_scheduled.get(record.id) if old_scheduled else None,
                        )

        # Auto-advance to 'confirmed' (Booked) when draft booking has a quote with items
        for record in self:
            if record.state == 'draft' and record.sale_order_id and record.sale_order_id.order_line:
                confirmed_stage = self.env['health.fieldservice.stage'].search([
                    ('state', '=', 'confirmed'),
                    ('active', '=', True)
                ], order='sequence', limit=1)
                if confirmed_stage:
                    record.stage_id = confirmed_stage
                    record.state = 'confirmed'
                    if not record.name or record.name == _('New Booking'):
                        record.name = self.env['ir.sequence'].next_by_code('health.fieldservice.order') or _('New Booking')

        # NOTE: FSO does NOT auto-advance to 'assigned' when staff is added.
        # It stays in 'confirmed' (Booked) until the nurse confirms the assignment
        # via the PWA. The advance happens in health_staff_assignment.write()
        # when assignment state changes to 'confirmed' (nurse accepted).

        # Recompute one-way driving distance when facility/client changed.
        if not self.env.context.get('skip_travel_recompute') and \
                any(k in vals for k in ('facility_id', 'patient_id')):
            for record in self:
                record._update_travel_distance()

        return result

    def _update_travel_distance(self):
        """Compute & store the one-way driving distance (facility -> client) on
        the booking. Feeds advanced-pricing (sale.order.fso_distance) + display.
        No-op when either endpoint lacks coordinates. When the booking's facility
        is the client's primary facility, reuse the client's already-computed
        distance (avoids a redundant routing call)."""
        for fso in self:
            fac, pat = fso.facility_id, fso.patient_id
            if not (fac and pat):
                continue
            km = mins = None
            if (pat.primary_facility_id and pat.primary_facility_id.id == fac.id
                    and pat.clinic_drive_distance_km):
                km, mins = pat.clinic_drive_distance_km, pat.clinic_drive_minutes
            elif (fac.latitude and fac.longitude
                  and pat.partner_latitude and pat.partner_longitude):
                res = geo_utils.driving_distance(
                    self.env, fac.latitude, fac.longitude,
                    pat.partner_latitude, pat.partner_longitude)
                if res:
                    km, mins = res['km'], res['minutes']
            if km is None:
                continue
            fso.with_context(skip_travel_recompute=True).write({
                'travel_distance': km,
                'travel_time_minutes': int(round(mins or 0)),
            })
            # Refresh distance-based pricing on an existing advanced-pricing quote
            # (skipped during bulk backfill of historical bookings).
            if self.env.context.get('skip_quote_recalc'):
                continue
            so = fso.sale_order_id
            if so and getattr(so, 'use_advanced_pricing', False) and \
                    hasattr(so, 'action_post_service_recalc'):
                try:
                    so.action_post_service_recalc()
                except Exception as e:  # noqa: BLE001
                    _logger.info('Quote recalc after distance update failed: %s', e)

    def _handle_state_change(self, new_state):
        """Handle automation based on state changes"""
        for record in self:
            if new_state == 'assigned':
                # Set assignment date
                record.assignment_date = fields.Datetime.now()
                # NOTE: Do NOT re-notify staff here. The staff was already notified
                # when the assignment was created via create(). This state change happens
                # when the nurse ACCEPTS, so sending another push would be duplicate.
            
            elif new_state == 'in_progress':
                # Set actual start time if not set
                if not record.actual_start_datetime:
                    record.actual_start_datetime = fields.Datetime.now()
            
            elif new_state == 'completed':
                # Set actual end time if not set
                if not record.actual_end_datetime:
                    record.actual_end_datetime = fields.Datetime.now()
                record._update_patient_last_visit_date()
                record._update_patient_next_visit_date()
                # Send completion notifications
                record._send_completion_notifications()
                # (template-assignment cleanup removed — health_schedule_canvas §2.4
                # retired the template mechanism; nothing creates template rows now.)
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
        
        # Auto-recalculate pricing with post-service procedure counts
        # This updates the quote with actual injection/medication/wound counts
        quote = self.sale_order_id
        if hasattr(quote, 'action_post_service_recalc') and quote.use_advanced_pricing:
            import logging
            _logger = logging.getLogger(__name__)
            _logger.info('Auto post-service recalc for FSO %s before invoicing', self.name)
            quote.action_post_service_recalc()
        
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
                'name': f'{_selection_labels(self, "service_type")[self.service_type]} - {self.patient_id.name}',
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
                    record._send_staff_assignment_notification(assignment.staff_id, assignment)
    
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
                        body=Markup(_('📋 <strong>Quote Required:</strong> This booking needs a healthcare quote before it can be confirmed. Use the "Create Quote" smart button to add services and pricing.')),
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

    def _update_patient_last_visit_date(self):
        self.ensure_one()
        if not self.patient_id:
            return
        end_dt = self.actual_end_datetime or fields.Datetime.now()
        if not self.patient_id.last_visit_date or end_dt > self.patient_id.last_visit_date:
            self.patient_id.write({'last_visit_date': end_dt})

    def _check_confirmation_requirements(self):
        """
        Check if booking meets requirements to be confirmed.
        Requirements: MUST have a quote with at least one line item.
    """
        self.ensure_one()

        has_quote_with_items = (
            self.sale_order_id and
            self.sale_order_id.order_line and
            len(self.sale_order_id.order_line) > 0
        )

        if not has_quote_with_items:
            error_msg = _(
                'Booking cannot be confirmed. You must create a Quote with at least one service/product line item.'
            )
            return False, error_msg

        return True, None

    def action_confirm_booking(self):
        """Confirm booking and move to confirmed stage"""
        self.ensure_one()

        if not self.scheduled_datetime:
            raise UserError(_('Please set the Scheduled Date & Time before confirming the booking.'))

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

        # Generate booking number on confirmation
        write_vals = {'stage_id': confirmed_stage.id}
        if not self.name or self.name == _('New Booking'):
            write_vals['name'] = self.env['ir.sequence'].next_by_code('health.fieldservice.order') or _('New Booking')

        # Move to confirmed stage (validation will happen in write method)
        try:
            self.write(write_vals)

            # Post confirmation message
            quote_or_package = self.sale_order_id.name if self.sale_order_id else self.name
            try:
                self.message_post(
                    body=Markup(_('✅ <strong>Booking Confirmed:</strong> Booking moved to %s stage. %s is ready for service delivery.')) % (confirmed_stage.name, quote_or_package),
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
        
        # Create empty sales order (fso_id links back to this booking)
        quote_vals = {
            'partner_id': self.patient_id.id,
            'origin': self.name,
            'pricelist_id': pricelist.id,
            'fso_id': self.id,
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
    
    def _send_staff_assignment_notification(self, staff, assignment=None):
        """Send push notification to assigned staff member"""
        self.ensure_one()
        try:
            # Find the user linked to this employee
            if not staff.user_id:
                _logger.info('Staff %s has no linked user - skipping push notification', staff.name)
                return

            push_config = self.env['health.pwa.config'].sudo().get_push_config()
            if not push_config:
                return

            # Determine user language preference (lang is a related field from partner)
            user_lang = getattr(staff.user_id, 'lang', None) or getattr(staff.user_id.partner_id, 'lang', None) or 'vi_VN'
            is_en = user_lang.startswith('en')

            # Build notification content
            patient_name = self.patient_id.name if self.patient_id else ('Unknown' if is_en else 'Không rõ')
            scheduled = ''
            if self.scheduled_datetime:
                # Format in a user-friendly way
                dt = fields.Datetime.context_timestamp(self, self.scheduled_datetime)
                scheduled = dt.strftime('%d/%m/%Y %H:%M')

            service_type = ''
            if hasattr(self, 'service_type') and self.service_type:
                service_type = _selection_labels(self, 'service_type').get(self.service_type, self.service_type)

            if is_en:
                title = '📋 New Booking Assignment'
                body_parts = []
                if patient_name:
                    body_parts.append(f'Patient: {patient_name}')
                if scheduled:
                    body_parts.append(f'Date: {scheduled}')
                if service_type:
                    body_parts.append(f'Service: {service_type}')
                body = '\n'.join(body_parts) or 'A new booking has been assigned to you.'
            else:
                title = '📋 Lịch hẹn mới'
                body_parts = []
                if patient_name:
                    body_parts.append(f'Bệnh nhân: {patient_name}')
                if scheduled:
                    body_parts.append(f'Ngày: {scheduled}')
                if service_type:
                    body_parts.append(f'Dịch vụ: {service_type}')
                body = '\n'.join(body_parts) or 'Bạn được phân công một lịch hẹn mới.'

            push_config.send_push_notification(
                user_id=staff.user_id.id,
                title=title,
                body=body,
                data={
                    'type': 'assignment',
                    'fso_id': self.id,
                    'assignment_id': assignment.id if assignment else None,
                    'url': f'/health_pwa#/booking/{self.id}',
                },
                tag=f'booking-assigned-{self.id}',
            )
        except Exception as e:
            _logger.warning('Failed to send assignment push notification: %s', e)

    def _send_staff_cancellation_notification(self, staff):
        """Send push notification to staff when their booking is cancelled.
        Also creates a bell queue notification for the PWA panel.
        """
        self.ensure_one()
        try:
            if not staff.user_id:
                return

            patient_name = self.patient_id.name if self.patient_id else 'Unknown'

            # Format date in booking timezone
            tz_name = self.booking_timezone or 'Asia/Ho_Chi_Minh'
            try:
                import pytz
                local_tz = pytz.timezone(tz_name)
            except Exception:
                import pytz
                local_tz = pytz.timezone('Asia/Ho_Chi_Minh')

            scheduled_str = ''
            if self.scheduled_datetime:
                dt_local = pytz.utc.localize(self.scheduled_datetime).astimezone(local_tz)
                scheduled_str = dt_local.strftime('%d/%m/%Y %H:%M')

            # Language-aware content
            user_lang = getattr(staff.user_id, 'lang', None) or getattr(staff.user_id.partner_id, 'lang', None) or 'vi_VN'
            is_en = user_lang.startswith('en')

            if is_en:
                title = '❌ Booking Cancelled'
                body_parts = [f'Patient: {patient_name}']
                if scheduled_str:
                    body_parts.append(f'Date: {scheduled_str}')
            else:
                title = '❌ Lịch hẹn đã hủy'
                body_parts = [f'Bệnh nhân: {patient_name}']
                if scheduled_str:
                    body_parts.append(f'Ngày: {scheduled_str}')
            body = '\n'.join(body_parts)

            # Create bell queue notification
            self.env['health.pwa.staff.notification'].sudo().create({
                'user_id': staff.user_id.id,
                'fso_id': self.id,
                'notification_type': 'cancelled',
                'patient_name': patient_name,
                'fso_name': self.name,
                'message': body,
            })

            # Send push notification
            push_config = self.env['health.pwa.config'].sudo().get_push_config()
            if push_config:
                push_config.send_push_notification(
                    user_id=staff.user_id.id,
                    title=title,
                    body=body,
                    data={
                        'type': 'booking_cancelled',
                        'fso_id': self.id,
                        'url': f'/health_pwa#/today',
                    },
                    tag=f'booking-cancelled-{self.id}',
                )
        except Exception as e:
            _logger.warning('Failed to send cancellation push notification: %s', e)

    def _send_staff_reschedule_notification(self, staff, old_datetime=None):
        """Send push notification to staff when their booking is rescheduled.
        Also creates a bell queue notification for the PWA panel.
        """
        self.ensure_one()
        try:
            if not staff.user_id:
                return

            # Format dates in booking timezone
            tz_name = self.booking_timezone or 'Asia/Ho_Chi_Minh'
            try:
                import pytz
                local_tz = pytz.timezone(tz_name)
            except Exception:
                import pytz
                local_tz = pytz.timezone('Asia/Ho_Chi_Minh')

            old_dt_str = ''
            if old_datetime:
                old_dt_local = pytz.utc.localize(old_datetime).astimezone(local_tz)
                old_dt_str = old_dt_local.strftime('%d/%m/%Y %H:%M')

            new_dt_str = ''
            if self.scheduled_datetime:
                new_dt_local = pytz.utc.localize(self.scheduled_datetime).astimezone(local_tz)
                new_dt_str = new_dt_local.strftime('%d/%m/%Y %H:%M')

            patient_name = self.patient_id.name if self.patient_id else 'Unknown'

            # Determine user language preference
            user_lang = getattr(staff.user_id, 'lang', None) or getattr(staff.user_id.partner_id, 'lang', None) or 'vi_VN'
            is_en = user_lang.startswith('en')

            if is_en:
                title = '🔄 Booking Rescheduled'
                body_parts = [f'Patient: {patient_name}']
                if old_dt_str:
                    body_parts.append(f'Old: {old_dt_str}')
                if new_dt_str:
                    body_parts.append(f'New: {new_dt_str}')
            else:
                title = '🔄 Lịch hẹn đã đổi'
                body_parts = [f'Bệnh nhân: {patient_name}']
                if old_dt_str:
                    body_parts.append(f'Cũ: {old_dt_str}')
                if new_dt_str:
                    body_parts.append(f'Mới: {new_dt_str}')
            body = '\n'.join(body_parts)

            # Create bell queue notification
            self.env['health.pwa.staff.notification'].sudo().create({
                'user_id': staff.user_id.id,
                'fso_id': self.id,
                'notification_type': 'rescheduled',
                'patient_name': patient_name,
                'fso_name': self.name,
                'message': body,
                'old_datetime': old_dt_str,
                'new_datetime': new_dt_str,
            })

            # Send push notification
            push_config = self.env['health.pwa.config'].sudo().get_push_config()
            if push_config:
                push_config.send_push_notification(
                    user_id=staff.user_id.id,
                    title=title,
                    body=body,
                    data={
                        'type': 'booking_rescheduled',
                        'fso_id': self.id,
                        'url': f'/health_pwa#/booking/{self.id}',
                    },
                    tag=f'booking-rescheduled-{self.id}',
                )
        except Exception as e:
            _logger.warning('Failed to send reschedule push notification: %s', e)

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
    
    def action_edit_patient_address(self):
        """Open modal to edit the linked patient's Vietnamese address fields."""
        self.ensure_one()
        if not self.patient_id:
            raise UserError(_('No client is linked to this booking.'))
        return self.patient_id.action_edit_vietnamese_address()
    
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

    def _check_invoice_authorization(self):
        """
        Check if the booking creator (current user) is authorized to raise invoices.
        
        Business Rule: Nurses and Doctors cannot raise invoices.
        When they create a booking, the Operations Manager should be notified
        that invoice creation is required.
        
        This is called automatically on booking creation.
        """
        self.ensure_one()
        user = self.env.user
        
        # Check if user is in healthcare staff group (Nurses/Doctors)
        # These users cannot create invoices
        is_healthcare_staff = user.has_group('health_fieldservice.group_healthcare_staff')
        is_nurse = user.has_group('health_fieldservice.group_healthcare_nurse') if hasattr(self.env, 'group_healthcare_nurse') else False
        is_doctor = user.has_group('health_fieldservice.group_healthcare_doctor') if hasattr(self.env, 'group_healthcare_doctor') else False
        
        # Also check employee job title if groups don't exist
        if not (is_nurse or is_doctor):
            if user.employee_id:
                job_title = (user.employee_id.job_title or '').lower()
                is_nurse = 'nurse' in job_title
                is_doctor = 'doctor' in job_title or 'bác sĩ' in job_title
        
        # If user is Nurse or Doctor, they cannot raise invoices
        if is_nurse or is_doctor or is_healthcare_staff:
            # Mark booking as not authorized for invoice by creator
            self.write({
                'invoice_authorized': False,
            })
            
            # Notify Operations Manager
            self._notify_om_invoice_required()
            
            _logger.info(
                'FSO %s: Created by healthcare staff (%s), OM notified for invoice creation',
                self.name, user.name
            )
        else:
            # Regular staff can create invoices
            self.write({
                'invoice_authorized': True,
            })

    def _notify_om_invoice_required(self):
        """
        Send notification to Operations Manager that a booking was created
        by a Nurse/Doctor and requires OM to create the invoice.
        """
        self.ensure_one()
        
        # Get operations manager group
        ops_group = self.env.ref('health_base.group_healthcare_operations_manager', raise_if_not_found=False)
        if not ops_group:
            _logger.warning('Operations Manager group not found for invoice notification')
            return
        
        # Get all operations managers
        ops_managers = ops_group.users
        
        if not ops_managers:
            _logger.warning('No Operations Managers found for invoice notification')
            return
        
        # Create activity for each operations manager
        activity_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        if not activity_type:
            _logger.warning('Todo activity type not found')
            return
        
        for manager in ops_managers:
            self.activity_schedule(
                activity_type_id=activity_type.id,
                summary=_('Invoice Required: %s') % self.name,
                note=_("""
                    <p><strong>Booking Created by Healthcare Staff - Invoice Required</strong></p>
                    <ul>
                        <li><strong>Booking:</strong> %(name)s</li>
                        <li><strong>Patient:</strong> %(patient)s</li>
                        <li><strong>Service:</strong> %(service)s</li>
                        <li><strong>Created By:</strong> %(user)s (%(job)s)</li>
                        <li><strong>Created:</strong> %(date)s</li>
                    </ul>
                    <p><em>This booking was created by a Nurse/Doctor who is not authorized to raise invoices. 
                    Please ensure the quote and invoice are created for this booking.</em></p>
                """) % {
                    'name': self.name,
                    'patient': self.patient_id.name if self.patient_id else 'Not assigned',
                    'service': self._get_service_type_label(),
                    'user': self.env.user.name,
                    'job': self.env.user.employee_id.job_title if self.env.user.employee_id else 'Healthcare Staff',
                    'date': fields.Datetime.now().strftime('%Y-%m-%d %H:%M'),
                },
                user_id=manager.id,
                date_deadline=fields.Date.today(),
            )
        
        # Mark notification as sent
        self.write({
            'invoice_notification_sent': True,
        })
        
        # Post note in chatter
        self.message_post(
            body=Markup(_(
                '<p><strong>Invoice Authorization Notice</strong></p>'
                '<p>This booking was created by %(user)s (Healthcare Staff). '
                'Operations team has been notified to handle invoice creation.</p>'
            )) % {'user': self.env.user.name},
            message_type='notification',
            subtype_xmlid='mail.mt_note',
        )

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
                body=Markup(
                    '<p><strong>Service Completed by Part-Time Staff</strong></p>'
                    '<p>Assigned staff: %s (Part-Time)</p>'
                    '<p>Operations team has been notified to create invoice.</p>'
                ) % self.lead_staff_id.name,
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

        # Mandatory validation: Invoice/Quote must exist
        if not self.invoice_submitted:
            raise UserError(_(
                'Invoice or Quote is required before completing the service.\n\n'
                'Please create a quote with service items or assign an invoice.'
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
            ) % _selection_labels(self, 'state').get(self.state))

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
                body=Markup(_('✅ <strong>Booking Closed:</strong> Cash collected by Operations Manager. Booking moved to Closed stage.')),
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
    
    def action_open_lead_dashboard(self):
        """Open the linked lead.

        Was the Lead Hub-Spoke dashboard, which is retired — nothing routes to
        it any more. Opens the CRM Center contact form instead, the same one
        Contacts and Lead Analysis open, so a lead looks the same wherever you
        reach it from.
        """
        self.ensure_one()

        if not self.crm_lead_id:
            raise UserError(_('No lead is linked to this booking.'))

        form = self.env.ref('health_crm.view_crm_contact_form_crm_center',
                            raise_if_not_found=False)
        return {
            'type': 'ir.actions.act_window',
            'name': self.crm_lead_id.name or _('Lead'),
            'res_model': 'crm.lead',
            'res_id': self.crm_lead_id.id,
            'view_mode': 'form',
            'views': [(form.id if form else False, 'form')],
            'target': 'current',
        }
    
    def action_open_ops_booking_detail(self):
        """Open the OPS booking detail view for this booking."""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'ops_booking_detail',
            'context': {'active_id': self.id},
        }

    def action_open_reschedule_wizard(self):
        """Open the OWL reschedule wizard as a client action."""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'ops_reschedule_booking',
            'name': _('Reschedule Booking'),
            'target': 'current',
            'context': {
                'active_id': self.id,
                'active_center': self.env.context.get('active_center', 'ops_center'),
            },
        }

    def action_open_reschedule_calendar(self):
        """Open calendar view to reschedule this booking (legacy fallback)."""
        return self.action_open_reschedule_wizard()

    def get_reschedule_data(self):
        """Return booking data needed by the OWL reschedule wizard."""
        self.ensure_one()
        import pytz
        tz_name = self.booking_timezone or 'Asia/Ho_Chi_Minh'
        try:
            local_tz = pytz.timezone(tz_name)
        except Exception:
            local_tz = pytz.timezone('Asia/Ho_Chi_Minh')

        current_date = ''
        current_hour = 7.0
        if self.scheduled_datetime:
            local_dt = pytz.utc.localize(self.scheduled_datetime).astimezone(local_tz)
            current_date = local_dt.strftime('%Y-%m-%d')
            current_hour = local_dt.hour + local_dt.minute / 60.0

        assigned_staff = []
        for assignment in self.sudo().assignment_ids.filtered(
            lambda a: a.state not in ('cancelled', 'template')
        ):
            staff = assignment.staff_id
            if staff:
                assigned_staff.append({
                    'id': staff.id,
                    'name': staff.name,
                    'job_title': staff.job_title or '',
                    'initials': ''.join([p[0] for p in (staff.name or '').split() if p][:2]).upper(),
                })

        # Same filter as the booking wizard (get_quick_booking_staff):
        # nurses/support staff only (exclude doctors), scoped to this
        # booking's facility, with a fallback to all staff when nobody is
        # linked to the facility.
        Emp = self.env['hr.employee'].sudo()
        facility_clause = []
        if self.facility_id:
            facility_clause = [('healthcare_facility_id', '=', self.facility_id.id)]
            if not Emp.search_count([
                ('is_healthcare_staff', '=', True),
                ('employment_status', '=', 'active'),
            ] + facility_clause):
                facility_clause = []

        staff_list = []
        employees = Emp.search([
            ('is_healthcare_staff', '=', True),
            ('employment_status', '=', 'active'),
            # nurse-only: staff must hold the Nurse access role.
            ('is_nurse_role', '=', True),
        ] + facility_clause, order='name')
        for emp in employees:
            staff_list.append({
                'id': emp.id,
                'name': emp.name,
                'job_title': emp.job_title or '',
                'initials': ''.join([p[0] for p in (emp.name or '').split() if p][:2]).upper(),
            })

        return {
            'booking_id': self.id,
            'booking_name': self.name or '',
            'patient_name': self.patient_id.name if self.patient_id else '',
            'patient_id': self.patient_id.id if self.patient_id else False,
            'service_type': _selection_labels(self, 'service_type').get(self.service_type, self.service_type or ''),
            'facility_name': self.facility_id.name if self.facility_id else '',
            'facility_id': self.facility_id.id if self.facility_id else False,
            'current_date': current_date,
            'current_hour': current_hour,
            'duration_hours': (self.scheduled_duration or 60) / 60.0,
            'state': self.state,
            'assigned_staff': assigned_staff,
            'assigned_staff_ids': [s['id'] for s in assigned_staff],
            'staff_list': staff_list,
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

        # Find the cancelled stage
        cancelled_stage = self.env['health.fieldservice.stage'].search([
            ('state', '=', 'cancelled'),
            ('active', '=', True)
        ], order='sequence', limit=1)

        write_vals = {
            'state': 'cancelled',
            'cancellation_reason_id': cancellation_reason_id,
            'cancelled_by': self.env.user.id,
            'cancellation_date': fields.Datetime.now(),
            'cancellation_notes': cancellation_notes,
        }
        if cancelled_stage:
            write_vals['stage_id'] = cancelled_stage.id

        self.write(write_vals)

        # Cancel all related staff assignments and notify staff
        if self.assignment_ids:
            for assignment in self.assignment_ids.filtered(lambda a: a.state not in ('cancelled', 'completed')):
                # Notify staff before cancelling their assignment
                if assignment.staff_id:
                    self._send_staff_cancellation_notification(assignment.staff_id)
                assignment.write({'state': 'cancelled'})

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

    @api.model
    def action_reschedule_from_wizard(self, booking_id, new_date, new_time_hour, new_staff_ids, duration_hours=None):
        """Reschedule a booking from the OWL reschedule wizard.
        Handles date/time change, staff reassignment, and notifications."""
        fso = self.browse(booking_id)
        if not fso.exists():
            return {'success': False, 'error': _('Booking not found.')}

        from datetime import timedelta
        import pytz

        tz_name = fso.booking_timezone or 'Asia/Ho_Chi_Minh'
        try:
            local_tz = pytz.timezone(tz_name)
        except Exception:
            local_tz = pytz.timezone('Asia/Ho_Chi_Minh')

        old_datetime = fso.scheduled_datetime
        old_staff_ids = set(fso.assignment_ids.filtered(
            lambda a: a.state not in ('cancelled', 'template')
        ).mapped('staff_id.id'))

        hour = int(new_time_hour)
        minute = int(round((new_time_hour - hour) * 60))
        from datetime import datetime as dt_class
        naive_local = dt_class.strptime(new_date, '%Y-%m-%d').replace(hour=hour, minute=minute)
        local_dt = local_tz.localize(naive_local)
        utc_dt = local_dt.astimezone(pytz.utc).replace(tzinfo=None)

        write_vals = {'scheduled_datetime': utc_dt}
        if duration_hours:
            write_vals['scheduled_duration'] = int(duration_hours * 60)

        fso.write(write_vals)

        new_staff_set = set(new_staff_ids) if new_staff_ids else set()
        staff_changed = new_staff_set != old_staff_ids

        if staff_changed and new_staff_set:
            removed_staff = old_staff_ids - new_staff_set
            added_staff = new_staff_set - old_staff_ids

            for assignment in fso.assignment_ids.filtered(
                lambda a: a.state not in ('cancelled', 'template') and a.staff_id.id in removed_staff
            ):
                staff = assignment.staff_id
                assignment.write({'state': 'cancelled'})
                try:
                    if staff.user_id:
                        self.env['health.pwa.staff.notification'].sudo().create({
                            'user_id': staff.user_id.id,
                            'fso_id': fso.id,
                            'notification_type': 'cancelled',
                            'patient_name': fso.patient_id.name if fso.patient_id else '',
                            'fso_name': fso.name,
                            'message': _('You have been unassigned from booking %s', fso.name),
                        })
                except Exception:
                    pass

            for staff_id in added_staff:
                staff = self.env['hr.employee'].sudo().browse(staff_id)
                if not staff.exists():
                    continue
                duration_mins = fso.scheduled_duration or 60
                end_dt = fso.scheduled_datetime + timedelta(minutes=duration_mins)
                self.env['health.staff.assignment'].create({
                    'fso_id': fso.id,
                    'staff_id': staff_id,
                    'assignment_date': fso.scheduled_datetime,
                    'planned_start_time': fso.scheduled_datetime,
                    'planned_end_time': end_dt,
                    'state': 'assigned',
                })
                fso._send_staff_reschedule_notification(staff, old_datetime=old_datetime)

            for assignment in fso.assignment_ids.filtered(
                lambda a: a.state not in ('cancelled', 'template') and a.staff_id.id in (old_staff_ids & new_staff_set)
            ):
                pass

        tz_str = local_tz
        new_local = pytz.utc.localize(fso.scheduled_datetime).astimezone(local_tz)
        formatted_date = new_local.strftime('%d/%m/%Y')
        formatted_time = new_local.strftime('%H:%M')

        return {
            'success': True,
            'booking_id': fso.id,
            'booking_name': fso.name,
            'patient_name': fso.patient_id.name if fso.patient_id else '',
            'new_date': formatted_date,
            'new_time': formatted_time,
            'staff_changed': staff_changed,
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
        
        # Create sales order with FSO data (fso_id links back to this booking)
        quote_vals = {
            'partner_id': self.patient_id.id,
            'origin': self.name,
            'pricelist_id': pricelist.id,
            'fso_id': self.id,
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
            'views': [[view_id, 'form']],  # Required by Odoo 19 web framework for action preprocessing
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
                    'name': f'{_selection_labels(self, "service_type")[self.service_type]} - {self.patient_id.name}',
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
        product_name = f'Healthcare Service - {_selection_labels(self, "service_type")[self.service_type]}'
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
        
        # Create sales order (fso_id links back to this booking)
        quote_vals = {
            'partner_id': self.patient_id.id,
            'origin': self.name,
            'pricelist_id': pricelist.id,
            'fso_id': self.id,
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
            'domain': [('fso_id', '=', self.id), ('state', '!=', 'template')],
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
    def _read_group_stage_ids(self, stages, domain=None, order=None):
        """Return all active stages for kanban view, ordered by sequence"""
        return self.env['health.fieldservice.stage'].search([('active', '=', True)], order=order or 'sequence')
    
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

        # The "template assignment" DB-row hack was removed (health_schedule_canvas
        # §2.4). default_fso_id / default_assignment_date in the action context
        # below now reach the create dialog directly (web_timeline _onAdd context
        # merge), so no placeholder row is needed.

        # Open timeline view focused on appointment date with DAY view
        # Convert UTC datetime to user timezone for proper timeline focus
        import pytz
        user_tz = pytz.timezone(self.env.user.tz or 'UTC')
        appointment_datetime_utc = self.scheduled_datetime or fields.Datetime.now()

        # Convert to user timezone
        appointment_datetime_local = pytz.UTC.localize(appointment_datetime_utc).astimezone(user_tz)
        appointment_date = appointment_datetime_local.strftime('%Y-%m-%d')

        _logger.info("📅 TIMEZONE CONVERSION:")
        _logger.info("   User Timezone: %s", self.env.user.tz or 'UTC')
        _logger.info("   UTC DateTime: %s", appointment_datetime_utc)
        _logger.info("   Local DateTime: %s", appointment_datetime_local)
        _logger.info("   Timeline Focus Date: %s", appointment_date)

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
            'default_assignment_date': appointment_datetime_utc,  # Used by template default_get()
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
            'domain': [('state', '!=', 'template')],  # Show all assignments (all bookings) to see staff availability
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
        """Open the Client form as modal dashboard"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Client Dashboard — %s') % self.patient_id.name,
            'res_model': 'res.partner',
            'res_id': self.patient_id.id,
            'view_mode': 'form',
            'view_id': self.env.ref('health_base.view_health_patient_form').id,
            'target': 'new',
        }

    def action_open_client_form(self):
        """Open the client/patient form view (OPS profile)"""
        self.ensure_one()
        if not self.patient_id:
            raise UserError(_('No client is linked to this booking.'))
        try:
            view_id = self.env.ref('health_fieldservice.view_health_patient_form_ops').id
        except Exception:
            view_id = self.env.ref('health_base.view_health_patient_form').id
        return {
            'type': 'ir.actions.act_window',
            'name': self.patient_id.name,
            'res_model': 'res.partner',
            'res_id': self.patient_id.id,
            'view_mode': 'form',
            'view_id': view_id,
            'target': 'current',
        }

    def action_open_new_booking_wizard(self):
        """Open the OWL Quick Booking wizard pre-filled with this booking's client"""
        self.ensure_one()
        patient_id = self.patient_id.id if self.patient_id else False
        return {
            'type': 'ir.actions.client',
            'tag': 'ops_quick_booking',
            'name': _('Quick Booking'),
            'target': 'current',
            'context': {
                'active_id': patient_id,
                'default_patient_id': patient_id,
            },
        }

    def action_open_duplicate_booking_wizard(self):
        """Open the duplicate booking wizard pre-filled with this booking's data"""
        self.ensure_one()
        duration_hours = (self.scheduled_duration or 60) / 60.0
        return {
            'type': 'ir.actions.act_window',
            'name': _('Duplicate Booking'),
            'res_model': 'health.duplicate.booking.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_source_fso_id': self.id,
                'default_booking_duration': duration_hours,
            },
        }

    def action_open_staff_timeline_modal(self):
        """Open staff assignment timeline as a modal overlay"""
        self.ensure_one()
        import pytz
        user_tz = pytz.timezone(self.env.user.tz or 'UTC')
        appointment_datetime_utc = self.scheduled_datetime or fields.Datetime.now()
        appointment_datetime_local = pytz.UTC.localize(appointment_datetime_utc).astimezone(user_tz)
        appointment_date = appointment_datetime_local.strftime('%Y-%m-%d')

        # Template-row hack removed (health_schedule_canvas §2.4) — the context
        # defaults below reach the create dialog directly now.

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

        return {
            'name': _('Staff Assignment — %s') % appointment_date,
            'type': 'ir.actions.act_window',
            'res_model': 'health.staff.assignment',
            'view_mode': 'timeline,list,form',
            'views': views if views else False,
            'target': 'new',
            'domain': [('state', '!=', 'template')],
            'context': {
                'default_fso_id': self.id,
                'default_assignment_date': appointment_datetime_utc,
                'default_staff_id': False,
                'date': appointment_date,
                'initial_date': appointment_date,
                'dialog_size': 'extra-large',
            },
        }

    # =========================================================================
    # Operations Dashboard Data Methods
    # =========================================================================

    @api.model
    def get_ops_dashboard_data(self, date_from=False, date_to=False, facility_id=False):
        """Single RPC returning all ops dashboard data for the given date range.
        date_from/date_to are ISO date strings (or False). When both are False,
        no date bound is applied (All Dates). A single day = same from/to."""
        from datetime import datetime, timedelta
        import pytz

        tz = pytz.timezone(self.env.user.tz or 'Asia/Ho_Chi_Minh')

        # day_start/day_end are always defined (used by the staff-roster section);
        # they default to today when a range side is missing (All Dates).
        today = fields.Date.context_today(self)
        df = fields.Date.from_string(date_from) if date_from else today
        dt2 = fields.Date.from_string(date_to) if date_to else today
        day_start = tz.localize(datetime.combine(df, datetime.min.time())).astimezone(pytz.utc).replace(tzinfo=None)
        day_end = tz.localize(datetime.combine(dt2, datetime.max.time())).astimezone(pytz.utc).replace(tzinfo=None)

        base_domain = [('state', '!=', 'cancelled')]
        if date_from:
            base_domain.append(('scheduled_datetime', '>=', day_start))
        if date_to:
            base_domain.append(('scheduled_datetime', '<=', day_end))
        if facility_id:
            base_domain.append(('facility_id', '=', facility_id))

        all_fsos = self.search(base_domain, order='scheduled_datetime asc')

        total = len(all_fsos)
        needs_staff = len(all_fsos.filtered(lambda f: not f.has_staff_assigned and f.state in ('draft', 'confirmed')))
        active_now = len(all_fsos.filtered(lambda f: f.state == 'in_progress'))
        completed = len(all_fsos.filtered(lambda f: f.state in ('completed', 'completed_pending_invoice', 'closed')))
        total_revenue = sum(all_fsos.mapped('total_price'))

        service_breakdown = {}
        for fso in all_fsos:
            st = fso.service_type or 'other'
            service_breakdown[st] = service_breakdown.get(st, 0) + 1

        urgent_needs = len(all_fsos.filtered(
            lambda f: not f.has_staff_assigned and f.state in ('draft', 'confirmed') and f.priority in ('3', '4')
        ))
        normal_needs = needs_staff - urgent_needs

        kpis = {
            'total_today': total,
            'needs_assignment': needs_staff,
            'urgent_needs': urgent_needs,
            'normal_needs': normal_needs,
            'active_now': active_now,
            'completed_today': completed,
            'revenue_today': total_revenue,
            'service_breakdown': service_breakdown,
        }

        booking_fields = [
            'id', 'name', 'state', 'priority', 'service_type',
            'scheduled_datetime', 'scheduled_duration', 'estimated_end_datetime',
            'has_staff_assigned', 'service_location',
        ]
        bookings = []
        for fso in all_fsos:
            patient_name = fso.patient_id.name if fso.patient_id else ''
            # sudo the employee read: non-HR dashboard users get the public
            # profile, and reading the lead-staff name otherwise pulls restricted
            # role fields via prefetch -> AccessError.
            lead = fso.lead_staff_id.sudo()
            lead_staff_name = lead.name if lead else ''
            lead_staff_id = lead.id if lead else False
            facility_name = fso.facility_id.name if fso.facility_id else ''
            catchment = fso.catchment_province_id.name if fso.catchment_province_id else ''
            appointment_type = fso.appointment_type_id.name if fso.appointment_type_id else ''

            sched_local = ''
            sched_time = ''
            if fso.scheduled_datetime:
                local_dt = pytz.utc.localize(fso.scheduled_datetime).astimezone(tz)
                sched_local = local_dt.strftime('%Y-%m-%d %H:%M')
                sched_time = local_dt.strftime('%H:%M')

            bookings.append({
                'id': fso.id,
                'name': fso.name or '',
                'state': fso.state,
                'priority': fso.priority,
                'service_type': fso.service_type or '',
                'service_type_name': appointment_type,
                'scheduled_datetime': sched_local,
                'scheduled_time': sched_time,
                'scheduled_duration': fso.scheduled_duration or 60,
                'has_staff_assigned': fso.has_staff_assigned,
                'service_location': fso.service_location or '',
                'patient_name': patient_name,
                'patient_id': fso.patient_id.id if fso.patient_id else False,
                'lead_staff_name': lead_staff_name,
                'lead_staff_id': lead_staff_id,
                'facility_name': facility_name,
                'catchment_name': catchment,
                'total_price': fso.total_price or 0,
            })

        # Staff roster: read with sudo so non-HR dashboard users (e.g. CRM /
        # Operations roles that are not HR officers) can see role/duty flags.
        # Odoo otherwise serves them the employee *public* profile, which hides
        # access_role_id/is_om_role/is_head_nurse/is_duty_doctor -> AccessError.
        Employee = self.env['hr.employee'].sudo()
        staff_domain = [('is_healthcare_staff', '=', True), ('employment_status', '=', 'active')]
        if facility_id:
            staff_domain.append(('healthcare_facility_id', '=', facility_id))
        staff_members = Employee.search(staff_domain, order='name asc')

        Assignment = self.env['health.staff.assignment'].sudo()
        role_labels = {
            'Admin': self.env._('Admin'),
            'Doctor': self.env._('Doctor'),
            'Duty Doctor': self.env._('Duty Doctor'),
            'Head Nurse': self.env._('Head Nurse'),
            'Nurse': self.env._('Nurse'),
            'Operations Manager': self.env._('Operations Manager'),
        }
        staff_list = []
        for emp in staff_members:
            day_assignments = Assignment.search([
                ('staff_id', '=', emp.id),
                ('planned_start_time', '>=', day_start),
                ('planned_start_time', '<=', day_end),
                ('state', 'not in', ['cancelled', 'template']),
            ])

            duty = emp._get_duty_status(day=df, day_assignments=day_assignments)
            status = duty['code']

            next_available = ''
            if status == 'busy':
                active_assignment = day_assignments.filtered(lambda a: a.state == 'in_progress')[:1]
                if active_assignment and active_assignment.planned_end_time:
                    local_end = pytz.utc.localize(active_assignment.planned_end_time).astimezone(tz)
                    next_available = local_end.strftime('%H:%M')

            staff_list.append({
                'id': emp.id,
                'name': emp.name or '',
                'role': role_labels.get(
                    emp.access_role_display,
                    emp.access_role_display or '',
                ),
                'status': status,
                'status_label': duty['label'],
                'today_assignments': len(day_assignments),
                'next_available': next_available,
                'initials': ''.join([p[0].upper() for p in (emp.name or 'U').split()[:2]]),
                'color_index': emp.color or 0,
            })

        timeline_blocks = []
        assignments = self.env['health.staff.assignment'].search([
            ('planned_start_time', '>=', day_start),
            ('planned_start_time', '<=', day_end),
            ('state', 'not in', ['cancelled', 'template']),
        ], order='planned_start_time asc')

        for asgn in assignments:
            start_hour = 8
            end_hour = 8
            if asgn.planned_start_time:
                local_start = pytz.utc.localize(asgn.planned_start_time).astimezone(tz)
                start_hour = local_start.hour + local_start.minute / 60.0
            if asgn.planned_end_time:
                local_end = pytz.utc.localize(asgn.planned_end_time).astimezone(tz)
                end_hour = local_end.hour + local_end.minute / 60.0

            fso = asgn.fso_id
            timeline_blocks.append({
                'id': asgn.id,
                'fso_id': fso.id if fso else False,
                'staff_id': asgn.staff_id.id if asgn.staff_id else False,
                'patient_name': fso.patient_id.name if fso and fso.patient_id else '',
                'service_type': fso.service_type if fso else '',
                'start_hour': round(start_hour, 2),
                'end_hour': round(end_hour, 2),
                'state': asgn.state,
                'fso_state': fso.state if fso else '',
            })

        return {
            'kpis': kpis,
            'bookings': bookings,
            'staff': staff_list,
            'timeline_blocks': timeline_blocks,
        }

    def action_quick_assign_staff(self, staff_id):
        """Inline staff assignment from dashboard/queue. Creates assignment and updates state."""
        self.ensure_one()
        if not staff_id:
            return False

        Employee = self.env['hr.employee']
        staff = Employee.browse(staff_id)
        if not staff.exists():
            return False

        existing = self.env['health.staff.assignment'].search([
            ('fso_id', '=', self.id),
            ('staff_id', '=', staff_id),
            ('state', 'not in', ['cancelled', 'template']),
        ], limit=1)
        if existing:
            return {'success': True, 'message': _('Staff already assigned')}

        self.env['health.staff.assignment'].create({
            'fso_id': self.id,
            'staff_id': staff_id,
            'assignment_role': 'lead' if not self.has_staff_assigned else 'support',
            'state': 'assigned',
        })

        if self.state in ('draft', 'confirmed'):
            self._handle_staff_assignment()

        return {'success': True, 'message': _('Staff assigned successfully')}

    @api.model
    def create_booking_from_wizard(self, vals):
        """Create a booking from the OWL booking wizard.
        Accepts dict with booking_date, booking_time, booking_timezone for
        local-to-UTC conversion."""
        import pytz
        from datetime import datetime

        booking_date = vals.pop('booking_date', False)
        booking_time = vals.pop('booking_time', False)
        booking_tz = vals.pop('booking_timezone', 'Asia/Ho_Chi_Minh')
        vals.pop('booking_notes', None)
        vals.pop('service_notes', None)

        if booking_date and booking_time is not False:
            if isinstance(booking_date, str):
                booking_date = fields.Date.from_string(booking_date)
            hours = int(booking_time)
            minutes = int(round((booking_time - hours) * 60))
            naive_local = datetime.combine(booking_date, datetime.min.time()).replace(
                hour=hours, minute=minutes
            )
            tz = pytz.timezone(booking_tz)
            local_dt = tz.localize(naive_local)
            utc_dt = local_dt.astimezone(pytz.utc).replace(tzinfo=None)
            vals['scheduled_datetime'] = utc_dt

        booking = self.create(vals)
        return booking.id

    @api.model
    def get_ops_calendar_data(self, start_date, end_date, staff_id=False, service_type=False):
        domain = [
            ('scheduled_datetime', '>=', start_date),
            ('scheduled_datetime', '<=', end_date),
            ('state', '!=', 'cancelled'),
        ]
        if staff_id:
            domain.append(('lead_staff_id', '=', int(staff_id)))
        if service_type:
            domain.append(('service_type', '=', service_type))

        bookings = self.search(domain, order='scheduled_datetime asc')
        events = []
        for b in bookings:
            events.append({
                'id': b.id,
                'name': b.name or '',
                'patient_name': b.patient_id.name if b.patient_id else '',
                'service_type': b.service_type or 'home_visit',
                'state': b.state or 'draft',
                'has_staff': b.has_staff_assigned,
                'staff_name': b.lead_staff_id.name if b.lead_staff_id else '',
                'start_dt': fields.Datetime.to_string(b.scheduled_datetime) if b.scheduled_datetime else '',
                'duration': b.scheduled_duration or 60,
                'priority': b.priority or '1',
            })

        staff = self.env['hr.employee'].search_read(
            [('is_healthcare_staff', '=', True), ('employment_status', '=', 'active')],
            ['name'],
            order='name asc',
        )

        return {'events': events, 'staff': staff}

    def get_booking_detail_data(self):
        """Single RPC returning all booking detail data for the OWL component."""
        self.ensure_one()
        b = self

        service_type_label = _selection_labels(b, 'service_type').get(b.service_type, b.service_type or '')
        state_label = _selection_labels(b, 'state').get(b.state, b.state or '')
        priority_label = _selection_labels(b, 'priority').get(b.priority, '') if b.priority else ''
        service_location_label = dict(
            b._fields['service_location']._description_selection(b.env)
        ).get(b.service_location, '') if b.service_location else ''
        booking_source_label = dict(b._fields['booking_source'].selection).get(b.booking_source, '') if b.booking_source else ''

        dur_mins = b.scheduled_duration or 60
        dur_label = f"{dur_mins // 60}h" if dur_mins >= 60 else f"{dur_mins}min"
        if dur_mins >= 60 and dur_mins % 60:
            dur_label = f"{dur_mins // 60}h {dur_mins % 60}min"

        time_range = ''
        time_slot = ''
        if b.scheduled_datetime:
            start = b.scheduled_datetime
            end = b.estimated_end_datetime
            start_str = start.strftime('%H:%M')
            end_str = end.strftime('%H:%M') if end else ''
            date_str = start.strftime('%b %d, %Y')
            time_range = f"{date_str} • {start_str}"
            time_slot = start_str
            if end_str:
                time_range += f" — {end_str}"
                time_slot += f" — {end_str}"

        # Patient info with stats
        p = b.patient_id
        patient_initials = ''
        if p and p.name:
            parts = p.name.split()
            patient_initials = ''.join(x[0] for x in parts if x)[:2].upper()

        patient_stats = {'total_visits': 0, 'active_packages': 0, 'pending_payments': 0, 'satisfaction': 0}
        if p:
            try:
                patient_stats['total_visits'] = self.search_count([
                    ('patient_id', '=', p.id), ('state', 'in', ['completed', 'completed_pending_invoice', 'closed'])
                ])
                patient_stats['active_packages'] = self.env['health.prepaid.package'].search_count([
                    ('partner_id', '=', p.id), ('state', '=', 'active')
                ]) if 'health.prepaid.package' in self.env else 0
                patient_stats['pending_payments'] = self.search_count([
                    ('patient_id', '=', p.id), ('state', '=', 'completed_pending_invoice')
                ])
                ratings = self.search([
                    ('patient_id', '=', p.id), ('service_rating', '!=', False)
                ]).mapped(lambda r: int(r.service_rating) if r.service_rating else 0)
                ratings = [r for r in ratings if r > 0]
                patient_stats['satisfaction'] = round(sum(ratings) / len(ratings), 1) if ratings else 0
            except Exception:
                pass

        patient = {
            'id': p.id if p else False,
            'name': p.name or '' if p else '',
            'initials': patient_initials,
            'code': p.patient_code or '' if p else '',
            'phone': p.mobile or p.phone or '' if p else '',
            'email': p.email or '' if p else '',
            'address': b.patient_address_display or '',
            'age': p.age_display or '' if p else '',
            'stats': patient_stats,
        }

        # Staff info
        staff = None
        if b.lead_staff_id:
            s = b.lead_staff_id
            s_initials = ''
            if s.name:
                s_parts = s.name.split()
                s_initials = ''.join(x[0] for x in s_parts if x)[:2].upper()
            staff = {
                'id': s.id,
                'name': s.name or '',
                'initials': s_initials,
                'role': s.job_title or s.job_id.name if s.job_id else '',
            }

        # Suggested staff (top 3 by availability)
        suggested_staff = []
        if not b.has_staff_assigned:
            try:
                healthcare_staff = self.env['hr.employee'].search([
                    ('is_healthcare_staff', '=', True),
                    ('employment_status', '=', 'active'),
                ], limit=10, order='name asc')
                COLORS = ['#1565C0', '#43A047', '#7c3aed', '#E53935', '#FB8C00', '#00897B']
                for idx, emp in enumerate(healthcare_staff[:3]):
                    emp_initials = ''.join(x[0] for x in emp.name.split() if x)[:2].upper() if emp.name else 'U'
                    today_count = self.search_count([
                        ('lead_staff_id', '=', emp.id),
                        ('scheduled_datetime', '>=', fields.Date.today().strftime('%Y-%m-%d 00:00:00')),
                        ('scheduled_datetime', '<=', fields.Date.today().strftime('%Y-%m-%d 23:59:59')),
                        ('state', 'not in', ['cancelled', 'closed']),
                    ])
                    score = max(60, 95 - idx * 12 - today_count * 3)
                    suggested_staff.append({
                        'id': emp.id,
                        'name': emp.name or '',
                        'initials': emp_initials,
                        'color': COLORS[idx % len(COLORS)],
                        'role': emp.job_title or '',
                        'today_bookings': today_count,
                        'score': score,
                        'available': today_count < 5,
                    })
            except Exception:
                pass

        # Workflow steps
        state_order = ['draft', 'confirmed', 'assigned', 'in_progress', 'completed', 'completed_pending_invoice', 'closed']
        state_labels = {
            'draft': self.env._('Created'),
            'confirmed': self.env._('Confirmed'),
            'assigned': self.env._('Staff Assigned'),
            'in_progress': self.env._('In Progress'),
            'completed': self.env._('Completed'),
            'completed_pending_invoice': self.env._('Invoiced'),
            'closed': self.env._('Closed'),
        }
        current_idx = state_order.index(b.state) if b.state in state_order else 0
        steps = []
        display_states = ['draft', 'confirmed', 'assigned', 'in_progress', 'completed', 'completed_pending_invoice']
        for i, st in enumerate(display_states):
            if i < current_idx:
                status = 'completed'
            elif i == current_idx:
                status = 'active'
            else:
                status = 'pending'
            steps.append({'key': st, 'label': state_labels.get(st, st), 'status': status, 'number': i + 1})

        # Payment summary with line items
        payment_lines = []
        if b.base_price:
            svc_desc = f"Service Fee ({service_type_label}"
            if dur_label:
                svc_desc += f" — {dur_label}"
            svc_desc += ")"
            payment_lines.append({'label': svc_desc, 'amount': b.base_price})
        if b.travel_charge:
            payment_lines.append({'label': 'Travel Surcharge', 'amount': b.travel_charge})
        if b.urgency_charge:
            payment_lines.append({'label': 'Urgent Priority Fee', 'amount': b.urgency_charge})
        if b.equipment_charge:
            payment_lines.append({'label': 'Equipment Charge', 'amount': b.equipment_charge})
        if b.after_hours_charge:
            payment_lines.append({'label': 'After Hours Fee', 'amount': b.after_hours_charge})

        total_amount = b.sale_order_id.amount_total if b.sale_order_id else b.total_price or 0
        payment = {
            'total': total_amount,
            'lines': payment_lines,
            'invoice_state': b.invoice_state or 'none',
            'has_invoice': bool(b.invoice_id),
            'invoice_id': b.invoice_id.id if b.invoice_id else False,
        }

        # Assigned staff list
        assigned_staff = []
        for emp in b.assigned_staff_ids:
            emp_initials = ''.join(x[0] for x in emp.name.split() if x)[:2].upper() if emp.name else 'U'
            assigned_staff.append({
                'id': emp.id,
                'name': emp.name or '',
                'initials': emp_initials,
                'role': emp.job_title or '',
            })

        # Clinical notes
        clinical_notes = []
        try:
            for note in b.clinical_note_ids.sorted('create_date', reverse=True)[:10]:
                clinical_notes.append({
                    'id': note.id,
                    'date': note.create_date.strftime('%b %d, %Y • %H:%M') if note.create_date else '',
                    'author': note.create_uid.name if note.create_uid else '',
                    'content': note.name or note.note or '',
                })
        except Exception:
            pass

        # Equipment
        equipment = []
        try:
            for eq in b.assigned_equipment_ids:
                equipment.append({'id': eq.id, 'name': eq.name or ''})
        except Exception:
            pass

        # Activity timeline (chatter messages)
        timeline = []
        try:
            messages = self.env['mail.message'].search([
                ('res_id', '=', b.id),
                ('model', '=', 'health.fieldservice.order'),
                ('message_type', 'in', ['comment', 'notification']),
            ], order='date desc', limit=15)
            for msg in messages:
                timeline.append({
                    'id': msg.id,
                    'body': msg.body or '',
                    'date': msg.date.strftime('%b %d, %Y • %H:%M') if msg.date else '',
                    'author': msg.author_id.name if msg.author_id else '',
                    'subtype': msg.subtype_id.name if msg.subtype_id else 'Note',
                })
        except Exception:
            pass

        # Execution timing
        execution = {
            'actual_start': b.actual_start_datetime.strftime('%b %d, %Y • %H:%M') if b.actual_start_datetime else '',
            'actual_end': b.actual_end_datetime.strftime('%b %d, %Y • %H:%M') if b.actual_end_datetime else '',
            'duration_display': b.actual_duration_display or '',
            'duration_hours': round(b.actual_duration, 2) if b.actual_duration else 0,
            'timer_active': b.service_timer_active or False,
        }

        # Quote info
        quote = {
            'id': b.sale_order_id.id if b.sale_order_id else False,
            'name': b.sale_order_id.name if b.sale_order_id else '',
            'state': b.sale_order_id.state if b.sale_order_id else '',
        }

        # Doctors
        primary_doctor = None
        if b.primary_doctor_id:
            d = b.primary_doctor_id
            d_initials = ''.join(x[0] for x in d.name.split() if x)[:2].upper() if d.name else 'DR'
            primary_doctor = {'id': d.id, 'name': d.name or '', 'initials': d_initials, 'role': d.job_title or 'Doctor'}

        assigned_doctors = []
        for doc in b.assigned_doctor_ids:
            doc_initials = ''.join(x[0] for x in doc.name.split() if x)[:2].upper() if doc.name else 'DR'
            assigned_doctors.append({'id': doc.id, 'name': doc.name or '', 'initials': doc_initials, 'role': doc.job_title or 'Doctor'})

        primary_nurse = None
        if b.primary_nurse_id:
            n = b.primary_nurse_id
            n_initials = ''.join(x[0] for x in n.name.split() if x)[:2].upper() if n.name else 'RN'
            primary_nurse = {'id': n.id, 'name': n.name or '', 'initials': n_initials, 'role': n.job_title or 'Nurse'}

        # Clinical details
        urgency_label = dict(b._fields['urgency_level'].selection).get(b.urgency_level, '') if b.urgency_level else ''
        clinical = {
            'symptoms': b.symptoms or '',
            'diagnosis': b.diagnosis or '',
            'goal_of_care': b.goal_of_care or '',
            'intake_notes': b.intake_notes or '',
            'service_requirements': b.service_requirements or '',
            'urgency_level': b.urgency_level or '',
            'urgency_label': urgency_label,
            'referring_doctor': b.referring_doctor_id.name if b.referring_doctor_id else '',
            'referring_doctor_id': b.referring_doctor_id.id if b.referring_doctor_id else False,
            'injection_count': b.injection_count or 0,
            'medication_count': b.medication_count or 0,
            'wound_count': b.wound_count or 0,
            'iv_fluid_count': b.iv_fluid_count or 0,
            'clinical_notes_submitted': b.clinical_notes_submitted,
            'clinical_note_count': b.clinical_note_count or 0,
        }

        # Follow-up
        follow_up = {
            'required': b.follow_up_required or False,
            'date': b.follow_up_date.strftime('%b %d, %Y') if b.follow_up_date else '',
            'date_raw': b.follow_up_date.isoformat() if b.follow_up_date else '',
            'notes': b.follow_up_notes or '',
        }

        # Equipment & supplies
        required_equipment_list = []
        try:
            for eq in b.required_equipment_ids:
                required_equipment_list.append({'id': eq.id, 'name': eq.name or ''})
        except Exception:
            pass

        equipment_data = {
            'assigned': equipment,
            'required': required_equipment_list,
            'required_text': b.required_equipment or '',
            'supplies_required': b.supplies_required or '',
            'supplies_checklist': b.supplies_checklist or '',
            'checklist_complete': b.equipment_checklist_complete or False,
        }

        # Location details
        location = {
            'type': b.service_location or '',
            'type_label': service_location_label,
            'facility': b.facility_id.name if b.facility_id else '',
            'facility_id': b.facility_id.id if b.facility_id else False,
            'address': b.service_address or b.visit_address or '',
            'gps': b.gps_coordinates or '',
            'travel_distance': b.travel_distance or 0,
            'travel_time': b.travel_time_minutes or 0,
            'online_url': b.online_meeting_url or '',
            'online_platform': b.online_platform or '',
        }

        # Communication & coordination
        communication = {
            'patient_contacted': b.patient_contacted or False,
            'staff_notified': b.staff_notified or False,
            'reminders_sent': b.reminders_sent or False,
            'last_communication': b.last_communication_date.strftime('%b %d, %Y • %H:%M') if b.last_communication_date else '',
            'communication_count': b.communication_count or 0,
        }

        # Compliance
        compliance = {
            'moh_required': b.moh_submission_required or False,
            'moh_date': b.moh_submission_date.strftime('%b %d, %Y') if b.moh_submission_date else '',
            'moh_reference': b.moh_reference or '',
            'misa_synced': b.misa_synced or False,
            'misa_date': b.misa_sync_date.strftime('%b %d, %Y') if b.misa_sync_date else '',
            'misa_reference': b.misa_reference or '',
        }

        # Financial extras
        payment_status_label = dict(b._fields['payment_status'].selection).get(b.payment_status, '') if b.payment_status else ''
        financial = {
            'payment_status': b.payment_status or '',
            'payment_status_label': payment_status_label,
            'has_insurance': b.has_insurance or False,
            'insurance_provider': b.insurance_provider or '',
            'invoice_submitted': b.invoice_submitted or False,
            'invoice_authorized': b.invoice_authorized or False,
            'service_fee_vnd': b.service_fee_vnd or 0,
            'commission_due_to': b.commission_due_to.name if b.commission_due_to else '',
            'commission_percentage': b.commission_percentage or 0,
            'commission_amount': b.commission_amount or 0,
            'travel_fee': b.travel_fee or 0,
        }

        # Service rating
        rating_label = dict(b._fields['service_rating'].selection).get(b.service_rating, '') if b.service_rating else ''

        # Cancellation info
        cancellation = {}
        if b.state == 'cancelled':
            cancellation = {
                'reason': b.cancellation_reason_id.name if b.cancellation_reason_id else '',
                'notes': b.cancellation_notes or '',
                'date': b.cancellation_date.strftime('%b %d, %Y • %H:%M') if b.cancellation_date else '',
                'cancelled_by': b.cancelled_by.name if b.cancelled_by else '',
                'cancelled_by_client': b.cancelled_by_client or '',
            }

        # Confirmation info
        confirmation_method_label = dict(b._fields['confirmation_method'].selection).get(b.confirmation_method, '') if b.confirmation_method else ''

        return {
            'booking': {
                'id': b.id,
                'name': b.name or '',
                'state': b.state or 'draft',
                'state_label': state_label,
                'priority': b.priority or '1',
                'priority_label': priority_label,
                'service_type': b.service_type or '',
                'service_type_label': service_type_label,
                'service_category': b.service_category or '',
                'service_location': b.service_location or '',
                'service_location_label': service_location_label,
                'time_range': time_range,
                'date_label': b.scheduled_datetime.strftime('%b %d, %Y') if b.scheduled_datetime else '',
                'time_label': time_slot,
                'duration_label': dur_label,
                'duration_minutes': dur_mins,
                'facility': b.facility_id.name if b.facility_id else '',
                'has_staff': b.has_staff_assigned,
                'special_requirements': b.special_requirements or '',
                'patient_notes': b.patient_notes or '',
                'booking_source': booking_source_label,
                'booking_source_key': b.booking_source or '',
                'package': b.package_id.name if hasattr(b, 'package_id') and b.package_id else '',
                'referral_source': b.booking_source or '',
                'created_date': b.create_date.strftime('%b %d, %Y at %H:%M') if b.create_date else '',
                'created_by': b.create_uid.name if b.create_uid else '',
                'booked_by': b.booking_user_id.name if b.booking_user_id else '',
                'confirmation_date': b.confirmation_date.strftime('%b %d, %Y at %H:%M') if b.confirmation_date else '',
                'confirmed_by': b.confirmed_by_id.name if b.confirmed_by_id else '',
                'confirmation_method': confirmation_method_label,
                'timezone': b.booking_timezone or '',
                'service_rating': b.service_rating or '',
                'service_rating_label': rating_label,
                'completion_notes': b.completion_notes or '',
                'team': b.team_id.name if b.team_id else '',
                'appointment_type': b.appointment_type_id.name if b.appointment_type_id else '',
            },
            'patient': patient,
            'staff': staff,
            'primary_doctor': primary_doctor,
            'assigned_doctors': assigned_doctors,
            'primary_nurse': primary_nurse,
            'suggested_staff': suggested_staff,
            'assigned_staff': assigned_staff,
            'steps': steps,
            'payment': payment,
            'clinical': clinical,
            'clinical_notes': clinical_notes,
            'follow_up': follow_up,
            'equipment': equipment_data,
            'location': location,
            'execution': execution,
            'communication': communication,
            'compliance': compliance,
            'financial': financial,
            'cancellation': cancellation,
            'quote': quote,
            'timeline': timeline,
        }

    def get_payment_collection_data(self):
        """Single RPC returning all data needed for the payment collection OWL wizard."""
        self.ensure_one()
        b = self

        patient_initials = ''
        if b.patient_id and b.patient_id.name:
            parts = b.patient_id.name.split()
            patient_initials = ''.join(x[0] for x in parts if x)[:2].upper()

        time_str = ''
        if b.scheduled_datetime:
            time_str = b.scheduled_datetime.strftime('%b %d, %Y')

        service_label = _selection_labels(b, 'service_type').get(b.service_type, '') if b.service_type else ''

        breakdown_parts = []
        if b.base_price:
            breakdown_parts.append(f"Service: {b.base_price:,.0f}")
        if b.travel_charge:
            breakdown_parts.append(f"Travel: {b.travel_charge:,.0f}")
        if b.urgency_charge:
            breakdown_parts.append(f"Urgent: {b.urgency_charge:,.0f}")
        if b.equipment_charge:
            breakdown_parts.append(f"Equipment: {b.equipment_charge:,.0f}")
        if b.after_hours_charge:
            breakdown_parts.append(f"After-hours: {b.after_hours_charge:,.0f}")

        amount_due = b.total_price or 0
        if b.invoice_id and b.invoice_id.amount_residual:
            amount_due = b.invoice_id.amount_residual

        staff_options = []
        try:
            employees = self.env['hr.employee'].search([
                ('department_id.name', 'ilike', 'health'),
            ], limit=20, order='name')
            if not employees:
                employees = self.env['hr.employee'].search([], limit=20, order='name')
            for emp in employees:
                staff_options.append({'id': emp.id, 'name': emp.name or ''})
        except Exception:
            pass

        return {
            'booking': {
                'id': b.id,
                'name': b.name or '',
                'service_type_label': service_label,
                'date_label': time_str,
            },
            'patient': {
                'id': b.patient_id.id if b.patient_id else False,
                'name': b.patient_id.name or '' if b.patient_id else '',
                'initials': patient_initials,
            },
            'amount': {
                'due': amount_due,
                'breakdown': ' + '.join(breakdown_parts),
                'base_price': b.base_price or 0,
                'travel_charge': b.travel_charge or 0,
                'urgency_charge': b.urgency_charge or 0,
                'equipment_charge': b.equipment_charge or 0,
                'after_hours_charge': b.after_hours_charge or 0,
                'total_price': b.total_price or 0,
                'invoice_residual': b.invoice_id.amount_residual if b.invoice_id else 0,
            },
            'staff_options': staff_options,
            'has_invoice': bool(b.invoice_id),
            'invoice_id': b.invoice_id.id if b.invoice_id else False,
        }

    def action_process_owl_payment(self, payment_method, amount, collected_by_id=False, bank_name='', transfer_ref='', notes='', receipt_type='retail'):
        """Process payment from the OWL payment collection wizard."""
        self.ensure_one()

        if amount <= 0:
            return {'success': False, 'error': 'Payment amount must be positive.'}

        journal_type = 'cash' if payment_method == 'cash' else 'bank'
        journal = self.env['account.journal'].search([
            ('type', '=', journal_type),
            ('company_id', '=', self.env.company.id),
        ], limit=1)
        if not journal:
            return {'success': False, 'error': f'No {journal_type} journal found. Configure in Accounting settings.'}

        try:
            payment_ref_parts = [f'Payment for {self.name}']
            if bank_name:
                payment_ref_parts.append(f'Bank: {bank_name}')
            if transfer_ref:
                payment_ref_parts.append(f'Ref: {transfer_ref}')

            payment_vals = {
                'payment_type': 'inbound',
                'partner_type': 'customer',
                'partner_id': self.patient_id.id,
                'amount': amount,
                'journal_id': journal.id,
                'payment_reference': ' | '.join(payment_ref_parts),
            }
            payment = self.env['account.payment'].create(payment_vals)
            payment.action_post()

            if self.invoice_id and self.invoice_id.state == 'posted':
                try:
                    payment_lines = payment.move_id.line_ids.filtered(
                        lambda l: l.account_id == payment.destination_account_id and not l.reconciled
                    )
                    invoice_lines = self.invoice_id.line_ids.filtered(
                        lambda l: l.account_id.account_type == 'asset_receivable' and not l.reconciled
                    )
                    if payment_lines and invoice_lines:
                        (payment_lines + invoice_lines).reconcile()
                except Exception:
                    pass

            note_body = f"Payment collected: {amount:,.0f} VND via {payment_method}"
            if collected_by_id:
                collector = self.env['hr.employee'].browse(collected_by_id)
                if collector.exists():
                    note_body += f" by {collector.name}"
            if notes:
                note_body += f" — {notes}"
            try:
                self.message_post(body=note_body, subject="Payment Collected")
            except Exception:
                pass

            return {'success': True, 'payment_id': payment.id}

        except Exception as e:
            return {'success': False, 'error': str(e)}

    @api.model
    def _catchment_area_key(self, name):
        """Map a province/city/facility name to a product catchment-area key
        ('hanoi' / 'tphcm'), matching product.product.catalog_catchment_area.
        Returns '' when the region is unknown."""
        name = (name or '').lower()
        if 'hanoi' in name or 'ha noi' in name or 'hà nội' in name:
            return 'hanoi'
        if ('chi minh' in name or 'hcm' in name or 'tphcm'
                in name or 'ho chi minh' in name or 'hồ chí minh' in name):
            return 'tphcm'
        return ''

    @api.model
    def _resolve_facility_catchment_area(self, facility_id):
        """Map a facility to a product catchment-area key ('hanoi' / 'tphcm'),
        matching product.product.catalog_catchment_area. Returns '' when the
        facility/region is unknown so callers fall back to the full catalog."""
        if not facility_id:
            return ''
        fac = self.env['health.facility'].browse(facility_id)
        if not fac.exists():
            return ''
        return self._catchment_area_key(
            (fac.catchment_province_id.name if fac.catchment_province_id else '')
            or fac.city or fac.name or ''
        )

    @api.model
    def _resolve_booking_catchment_province(self, patient=False, lead_id=False):
        """The catchment area a booking belongs to when the caller passed no
        facility: the client's own area, else the contact's (a client created
        from a crm.lead does not exist yet), else the booking user's area.
        Drives BOTH the preselected facility and the service catalog, so the
        picker never offers another region's services."""
        Province = self.env['health.catchment.province']
        province = Province
        if patient and patient.exists():
            province = (getattr(patient, 'catchment_province_id', Province)
                        or getattr(patient.primary_facility_id, 'catchment_province_id', Province))
        # crm is not a dependency of this module — only read the lead when the
        # CRM layer is actually installed.
        if not province and lead_id and 'crm.lead' in self.env:
            lead = self.env['crm.lead'].sudo().browse(int(lead_id))
            if lead.exists():
                province = getattr(lead, 'catchment_province_id', Province) or Province
        if not province:
            province = getattr(self.env.user, 'catchment_province_id', Province) or Province
        return province

    @api.model
    def _default_facility_for_province(self, province):
        """First active facility in a catchment area, for preselection."""
        if not province:
            return False
        fac = self.env['health.facility'].sudo().search([
            ('active', '=', True),
            ('catchment_province_id', '=', province.id),
        ], order='name', limit=1)
        return fac.id if fac else False

    @api.model
    def get_quick_booking_products(self, facility_id=False, patient_id=False, lead_id=False):
        """Return just the service catalog + categories scoped to a facility's
        catchment area, for refreshing the Add Services list when the user
        changes the Facility in the quick booking wizard."""
        data = self.get_recurring_booking_options(
            patient_id=patient_id, facility_id=facility_id, lead_id=lead_id)
        return {
            'products': data.get('products', []),
            'product_categories': data.get('product_categories', []),
        }

    @api.model
    def get_recurring_booking_options(self, patient_id=False, facility_id=False, lead_id=False):
        """Return option lists for the recurring booking OWL wizard.
        When facility_id is provided, staff/doctor lists are limited to that facility."""
        service_types = [
            {'key': 'home_visit', 'label': 'Home Visit'},
            {'key': 'clinic_visit', 'label': 'Clinic Visit'},
            {'key': 'consultation', 'label': 'Consultation'},
            {'key': 'follow_up', 'label': 'Follow-up'},
            {'key': 'telemedicine', 'label': 'Telemedicine'},
            {'key': 'preventive', 'label': 'Preventive Care'},
            {'key': 'rehabilitation', 'label': 'Rehabilitation'},
        ]
        # What the CALLER asked for, as opposed to a facility we derive below
        # from the client's profile — only the former survives the area check.
        explicit_facility_id = facility_id

        patient = {}
        preferred_staff_id = False
        patient_rec = self.env['res.partner']
        if patient_id:
            p = self.env['res.partner'].browse(patient_id)
            if p.exists():
                patient_rec = p
                initials = ''
                if p.name:
                    parts = p.name.split()
                    initials = ''.join(x[0] for x in parts if x)[:2].upper()
                addr = (p.vietnamese_address or '').strip() if hasattr(p, 'vietnamese_address') else ''
                if not addr:
                    addr = ', '.join(filter(None, [
                        p.street, p.street2, p.city,
                        p.state_id.name if p.state_id else '', p.zip,
                    ]))
                patient = {
                    'id': p.id,
                    'name': p.name or '',
                    'code': p.patient_code or '',
                    'initials': initials,
                    'address': addr,
                    'address_empty': not bool(addr),
                }
                if hasattr(p, 'preferred_staff_id') and p.preferred_staff_id:
                    preferred_staff_id = p.preferred_staff_id.id
                # Resolve a default facility from the client when none was passed
                if not facility_id:
                    pf = (getattr(p, 'primary_facility_id', False)
                          or getattr(p, 'facility_id', False))
                    if pf:
                        facility_id = pf.id

        # THE BOOKING'S CATCHMENT AREA IS THE CLIENT'S — the facility is only a
        # carrier of that area. Resolve the area first (client → contact → user);
        # it drives the facility choices, the preselected facility AND the
        # service catalog, so the three can never disagree and put a booking on
        # another region's price list.
        Facility = self.env['health.facility']
        booking_province = self._resolve_booking_catchment_province(patient_rec, lead_id)
        if not booking_province and facility_id:
            booking_province = Facility.browse(facility_id).catchment_province_id
        # A facility derived from the client's profile loses to the client's own
        # area (profiles do drift); a facility the caller passed explicitly is
        # kept, so reopening an existing booking never silently moves it.
        if booking_province and facility_id and not explicit_facility_id:
            if Facility.browse(facility_id).catchment_province_id != booking_province:
                facility_id = self._default_facility_for_province(booking_province) or facility_id
        if not facility_id:
            facility_id = self._default_facility_for_province(booking_province) or facility_id

        # Facility choices are HARD-LIMITED to the booking's area.
        facilities = []
        try:
            fac_domain = [('active', '=', True)]
            if booking_province:
                fac_domain.append(('catchment_province_id', '=', booking_province.id))
            found = Facility.search(fac_domain, order='name', limit=50)
            if not found and booking_province:
                # Area with no facility configured — offer all rather than
                # leaving the user unable to book at all.
                found = Facility.search([('active', '=', True)], order='name', limit=50)
            # An explicitly requested facility stays selectable even if it sits
            # outside the area, so an existing booking keeps its own facility.
            if facility_id and facility_id not in found.ids:
                found |= Facility.browse(facility_id).exists()
            facilities = sorted(
                ({'id': f.id, 'name': f.name or ''} for f in found),
                key=lambda f: f['name'],
            )
        except Exception:
            pass

        # Last resort when no area is known at all.
        if not facility_id and facilities:
            facility_id = facilities[0]['id']

        # Optional facility scope: limit staff/doctors to the facility.
        # Graceful fallback: if no staff are linked to the facility (data not
        # configured), show all active staff so booking isn't blocked.
        facility_clause = []
        if facility_id:
            # healthcare_facility_id is the single facility link for staff
            facility_clause = [('healthcare_facility_id', '=', facility_id)]
            if not self.env['hr.employee'].sudo().search_count([
                ('is_healthcare_staff', '=', True),
                ('employment_status', '=', 'active'),
            ] + facility_clause):
                facility_clause = []

        staff_list = []
        try:
            employees = self.env['hr.employee'].sudo().search([
                ('is_healthcare_staff', '=', True),
                ('employment_status', '=', 'active'),
                # nurse-only: staff must hold the Nurse access role.
                ('is_nurse_role', '=', True),
            ] + facility_clause, order='name', limit=100)
            for emp in employees:
                emp_initials = ''
                if emp.name:
                    parts = emp.name.split()
                    emp_initials = ''.join(x[0] for x in parts if x)[:2].upper()
                staff_list.append({
                    'id': emp.id,
                    'name': emp.name or '',
                    'job_title': emp.job_title or '',
                    'initials': emp_initials,
                    'is_preferred': emp.id == preferred_staff_id,
                })
            if preferred_staff_id:
                staff_list.sort(key=lambda s: (not s['is_preferred'], s['name']))
        except Exception:
            pass

        packages = []
        try:
            PkgModel = self.env.get('health.service.package')
            if PkgModel is not None and patient_id:
                pkgs = self.env['health.service.package'].search([
                    ('patient_id', '=', patient_id),
                    ('state', '=', 'active'),
                    ('remaining_services', '>', 0),
                ])
                for pkg in pkgs:
                    packages.append({
                        'id': pkg.id,
                        'name': pkg.name or '',
                        'service_type': pkg.service_type or '',
                        'total_services': pkg.total_services or 0,
                        'remaining_services': pkg.remaining_services or 0,
                        'expiration_date': pkg.expiration_date.strftime('%Y-%m-%d') if pkg.expiration_date else '',
                    })
        except Exception:
            pass

        doctor_list = []
        try:
            doctors = self.env['hr.employee'].sudo().search([
                ('is_healthcare_staff', '=', True),
                ('is_doctor_role', '=', True),
                ('employment_status', '=', 'active'),
            ] + facility_clause, order='name', limit=100)
            for doc in doctors:
                doctor_list.append({
                    'id': doc.id,
                    'name': doc.name or '',
                    'specialization': doc.job_title or '',
                })
        except Exception:
            pass

        products = []
        categ_ids = set()
        # Scope the service catalog to the booking facility's catchment area so
        # staff only see services that belong to that region (Hanoi vs HCMC).
        # Region-agnostic services (no _hanoi/_tphcm suffix) always show.
        catchment_clause = []
        # Region from the booking facility; when the area is known but has no
        # facility configured, still scope the catalog by that area.
        region = (self._resolve_facility_catchment_area(facility_id)
                  or self._catchment_area_key(booking_province.name if booking_province else ''))
        if region:
            catchment_clause = ['|',
                                ('catalog_catchment_area', '=', region),
                                ('catalog_catchment_area', '=', False)]
        try:
            service_products = self.env['product.product'].search([
                ('type', '=', 'service'),
                ('sale_ok', '=', True),
            ] + catchment_clause, order='categ_id, name', limit=200)
            for prod in service_products:
                categ_name = ''
                categ_id = False
                parent_categ_name = ''
                if prod.categ_id:
                    categ_id = prod.categ_id.id
                    categ_name = prod.categ_id.name or ''
                    categ_ids.add(categ_id)
                    if prod.categ_id.parent_id:
                        parent_categ_name = prod.categ_id.parent_id.name or ''
                products.append({
                    'id': prod.id,
                    'name': prod.name or '',
                    'price': prod.list_price or 0,
                    'default_code': prod.default_code or '',
                    'categ_name': categ_name,
                    'categ_id': categ_id,
                    'parent_categ_name': parent_categ_name,
                })
        except Exception:
            pass

        product_categories = []
        if categ_ids:
            try:
                for cat in self.env['product.category'].browse(list(categ_ids)):
                    product_categories.append({
                        'id': cat.id,
                        'name': cat.name or '',
                        'parent_name': cat.parent_id.name if cat.parent_id else '',
                        'product_count': sum(1 for p in products if p['categ_id'] == cat.id),
                    })
                product_categories.sort(key=lambda c: c['name'])
            except Exception:
                pass

        return {
            'service_types': service_types,
            'facilities': facilities,
            'patient': patient,
            'staff_list': staff_list,
            'packages': packages,
            'preferred_staff_id': preferred_staff_id,
            'doctor_list': doctor_list,
            'products': products,
            'product_categories': product_categories,
            'default_facility_id': facility_id or (facilities[0]['id'] if facilities else False),
        }

    @api.model
    def get_recurring_preview(self, patient_id, pattern, selected_days, start_date, occurrences, time_hour):
        """Generate preview dates for recurring booking with conflict detection."""
        from datetime import date as date_cls
        preview = []
        if not start_date or not selected_days:
            return preview

        try:
            if isinstance(start_date, str):
                start = datetime.strptime(start_date, '%Y-%m-%d').date()
            else:
                start = start_date
        except Exception:
            return preview

        day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        interval = 1
        if pattern == 'biweekly':
            interval = 2

        dates = []
        current = start
        max_iterations = 365
        iteration = 0
        week_num = 0
        last_week = None

        while len(dates) < occurrences and iteration < max_iterations:
            current_week = current.isocalendar()[1]
            if last_week is not None and current_week != last_week:
                week_num += 1
            last_week = current_week

            if pattern == 'daily':
                dates.append(current)
            elif pattern in ('weekly', 'biweekly'):
                if current.weekday() in selected_days:
                    if pattern == 'weekly' or (week_num % interval == 0):
                        dates.append(current)
            elif pattern == 'monthly':
                if current.day == start.day:
                    dates.append(current)

            current += timedelta(days=1)
            iteration += 1

        existing_fsos = {}
        if patient_id and dates:
            try:
                fsos = self.search([
                    ('patient_id', '=', patient_id),
                    ('scheduled_datetime', '>=', datetime.combine(dates[0], datetime.min.time())),
                    ('scheduled_datetime', '<=', datetime.combine(dates[-1], datetime.max.time())),
                    ('state', 'not in', ['cancelled']),
                ])
                for fso in fsos:
                    if fso.scheduled_datetime:
                        d = fso.scheduled_datetime.date()
                        existing_fsos.setdefault(d, []).append(fso.name or '')
            except Exception:
                pass

        hours = int(time_hour)
        minutes = int(round((time_hour - hours) * 60))
        time_str = f"{hours:02d}:{minutes:02d}"

        for i, d in enumerate(dates):
            conflict_bookings = existing_fsos.get(d, [])
            preview.append({
                'num': i + 1,
                'date': d.strftime('%b %d, %Y'),
                'day': day_names[d.weekday()],
                'time': time_str,
                'conflict': bool(conflict_bookings),
                'conflict_names': conflict_bookings[:2],
            })

        return preview

    @api.model
    def action_create_recurring_from_owl(self, patient_id, service_type, duration_hours, time_hour, facility_id, pattern, selected_days, start_date, occurrences, notes='', product_lines=None, staff_id=False, doctor_id=False, package_id=False, assigned_staff_ids=None, draft_only=False):
        """Create recurring FSO bookings from the OWL wizard.
        Creates bookings with quotes, confirms them, and assigns staff — all in one step.
        If draft_only=True, creates bookings in draft state without confirming or assigning staff."""
        if not patient_id or not service_type or not facility_id:
            return {'success': False, 'error': 'Missing required fields.'}

        preview = self.get_recurring_preview(patient_id, pattern, selected_days, start_date, occurrences, time_hour)
        if not preview:
            return {'success': False, 'error': 'No booking dates generated.'}

        try:
            if isinstance(start_date, str):
                start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
            else:
                start_dt = start_date
        except Exception:
            return {'success': False, 'error': 'Invalid start date.'}

        import pytz
        facility = self.env['health.facility'].browse(facility_id)
        tz_name = 'Asia/Ho_Chi_Minh'
        if facility.exists() and hasattr(facility, 'timezone') and facility.timezone:
            tz_name = facility.timezone
        tz = pytz.timezone(tz_name)

        hours = int(time_hour)
        minutes = int(round((time_hour - hours) * 60))

        interval = 2 if pattern == 'biweekly' else 1
        dates = []
        current = start_dt
        max_iterations = 365
        iteration = 0
        week_num = 0
        last_week = None

        while len(dates) < occurrences and iteration < max_iterations:
            current_week = current.isocalendar()[1]
            if last_week is not None and current_week != last_week:
                week_num += 1
            last_week = current_week

            if pattern == 'daily':
                dates.append(current)
            elif pattern in ('weekly', 'biweekly'):
                if current.weekday() in selected_days:
                    if pattern == 'weekly' or (week_num % interval == 0):
                        dates.append(current)
            elif pattern == 'monthly':
                if current.day == start_dt.day:
                    dates.append(current)

            current += timedelta(days=1)
            iteration += 1

        created_ids = []
        for d in dates:
            local_dt = datetime.combine(d, datetime.min.time()).replace(hour=hours, minute=minutes)
            local_dt = tz.localize(local_dt)
            utc_dt = local_dt.astimezone(pytz.UTC).replace(tzinfo=None)

            vals = {
                'patient_id': patient_id,
                'service_type': service_type,
                'facility_id': facility_id,
                'scheduled_datetime': utc_dt,
                'scheduled_duration': int(duration_hours * 60),
                'intake_notes': notes or '',
            }
            fso = self.create(vals)
            created_ids.append(fso.id)

        fso_records = self.browse(created_ids)
        quote_summary = {}

        if product_lines and len(product_lines) > 0:
            patient = self.env['res.partner'].browse(patient_id)
            pricelist = patient.property_product_pricelist if hasattr(patient, 'property_product_pricelist') else False
            summary_lines = []

            for fso_rec in fso_records:
                quote_vals = {
                    'partner_id': patient_id,
                    'origin': fso_rec.name or '',
                    # Link the quote to this booking so advanced pricing can read
                    # its conditions (time, location, service type, distance, etc.).
                    'fso_id': fso_rec.id,
                }
                if pricelist:
                    quote_vals['pricelist_id'] = pricelist.id
                quote = self.env['sale.order'].create(quote_vals)

                for pl in product_lines:
                    product = self.env['product.product'].browse(pl.get('product_id'))
                    if not product.exists():
                        continue
                    qty = pl.get('qty', 1)
                    price_unit = product.list_price or 0
                    if pricelist:
                        try:
                            price_unit = pricelist._get_product_price(product, qty) or price_unit
                        except Exception:
                            pass

                    self.env['sale.order.line'].create({
                        'order_id': quote.id,
                        'product_id': product.id,
                        'name': product.name or '',
                        'product_uom_qty': qty,
                        'price_unit': price_unit,
                    })

                fso_rec.sale_order_id = quote.id

                # Recalculate line prices from this booking's conditions
                # (advanced pricing) — each booking is priced on its own
                # date/time, so per-quote recalculation is required.
                try:
                    quote.order_line._compute_advanced_price()
                except Exception:
                    pass

            first_quote = fso_records[:1].sale_order_id
            if first_quote:
                for line in first_quote.order_line:
                    summary_lines.append({
                        'name': line.product_id.name or line.name or '',
                        'qty': line.product_uom_qty,
                        'unit_price': line.price_unit,
                        'subtotal': line.price_subtotal,
                    })
                quote_summary = {
                    'lines': summary_lines,
                    'total_per_booking': first_quote.amount_total,
                    'total_all': first_quote.amount_total * len(created_ids),
                }

        if not draft_only:
            # Confirm bookings, assign doctor/package/staff
            for fso_rec in fso_records:
                if package_id and hasattr(fso_rec, 'package_ids'):
                    try:
                        fso_rec.write({'package_ids': [(4, package_id)]})
                    except Exception:
                        pass
                if doctor_id:
                    try:
                        fso_rec.write({'primary_doctor_id': doctor_id})
                    except Exception:
                        pass

                try:
                    fso_rec.action_confirm_booking()
                except Exception:
                    pass

                # Create staff assignments
                staff_to_assign = assigned_staff_ids or []
                if staff_id and staff_id not in staff_to_assign:
                    staff_to_assign = [staff_id] + list(staff_to_assign)
                for sid in staff_to_assign:
                    try:
                        role = 'lead' if sid == staff_id else 'support'
                        existing = self.env['health.staff.assignment'].search([
                            ('fso_id', '=', fso_rec.id),
                            ('staff_id', '=', sid),
                            ('state', 'not in', ['cancelled', 'template']),
                        ], limit=1)
                        if not existing:
                            self.env['health.staff.assignment'].create({
                                'fso_id': fso_rec.id,
                                'staff_id': sid,
                                'assignment_role': role,
                                'state': 'draft',
                            })
                    except Exception:
                        pass

        return {
            'success': True,
            'count': len(created_ids),
            'ids': created_ids,
            'quote_summary': quote_summary,
        }

    @api.model
    def finalize_recurring_bookings(self, fso_ids, staff_id=False, doctor_id=False, package_id=False):
        """Confirm recurring bookings, assign staff/doctor/package.
        Creates assignments in draft state so booking stays confirmed
        until the nurse confirms the assignment."""
        if not fso_ids:
            return {'success': False}

        fso_records = self.browse(fso_ids)

        for fso_rec in fso_records:
            if package_id and hasattr(fso_rec, 'package_ids'):
                try:
                    fso_rec.write({'package_ids': [(4, package_id)]})
                except Exception:
                    pass

            if doctor_id:
                try:
                    fso_rec.write({'primary_doctor_id': doctor_id})
                except Exception:
                    pass

            try:
                fso_rec.action_confirm_booking()
            except Exception:
                pass

            if staff_id:
                try:
                    existing = self.env['health.staff.assignment'].search([
                        ('fso_id', '=', fso_rec.id),
                        ('staff_id', '=', staff_id),
                        ('state', 'not in', ['cancelled', 'template']),
                    ], limit=1)
                    if not existing:
                        self.env['health.staff.assignment'].create({
                            'fso_id': fso_rec.id,
                            'staff_id': staff_id,
                            'assignment_role': 'lead',
                            'state': 'draft',
                        })
                except Exception:
                    pass

        return {'success': True}

    @api.model
    def cancel_recurring_bookings(self, fso_ids):
        """Delete FSOs, their quotes, and staff assignments created by recurring wizard."""
        if not fso_ids:
            return {'success': False}

        fso_records = self.browse(fso_ids).exists()
        for fso in fso_records:
            if fso.sale_order_id:
                try:
                    fso.sale_order_id.action_cancel()
                    fso.sale_order_id.unlink()
                except Exception:
                    try:
                        fso.sale_order_id.unlink()
                    except Exception:
                        pass
            try:
                self.env['health.staff.assignment'].search([('fso_id', '=', fso.id)]).unlink()
            except Exception:
                pass
        try:
            fso_records.unlink()
        except Exception:
            return {'success': False, 'error': 'Failed to delete bookings.'}

        return {'success': True}

    # =====================================================================
    # QUICK BOOKING OWL WIZARD
    # =====================================================================

    @api.model
    def get_quick_booking_options(self, patient_id=False, facility_id=False, lead_id=False):
        """Return option lists for the quick booking OWL wizard.
        Reuses recurring booking logic; staff/doctors are scoped to the
        client's (or given) facility. `lead_id` carries the contact's catchment
        area for a client that will only be created when the booking is saved."""
        return self.get_recurring_booking_options(
            patient_id=patient_id, facility_id=facility_id, lead_id=lead_id)

    @api.model
    def get_quick_booking_staff(self, facility_id=False):
        """Return staff + doctor lists scoped to a facility, for when the user
        changes the Facility in the quick booking wizard."""
        Emp = self.env['hr.employee'].sudo()
        facility_clause = []
        if facility_id:
            # healthcare_facility_id is the single facility link for staff
            facility_clause = [('healthcare_facility_id', '=', facility_id)]
            # Fallback to all staff when none are linked to this facility
            if not Emp.search_count([
                ('is_healthcare_staff', '=', True),
                ('employment_status', '=', 'active'),
            ] + facility_clause):
                facility_clause = []

        staff_list = []
        for emp in Emp.search([
            ('is_healthcare_staff', '=', True),
            ('employment_status', '=', 'active'),
            # nurse-only: staff must hold the Nurse access role.
            ('is_nurse_role', '=', True),
        ] + facility_clause, order='name', limit=100):
            initials = ''.join(x[0] for x in (emp.name or '').split() if x)[:2].upper()
            staff_list.append({
                'id': emp.id,
                'name': emp.name or '',
                'job_title': emp.job_title or '',
                'initials': initials,
                'is_preferred': False,
            })

        doctor_list = []
        for doc in Emp.search([
            ('is_healthcare_staff', '=', True),
            ('is_doctor_role', '=', True),
            ('employment_status', '=', 'active'),
        ] + facility_clause, order='name', limit=100):
            doctor_list.append({
                'id': doc.id,
                'name': doc.name or '',
                'specialization': doc.job_title or '',
            })

        return {'staff_list': staff_list, 'doctor_list': doctor_list}

    @api.model
    def preview_quick_booking_pricing(self, vals):
        """Preview condition-based pricing for the quick booking quote, before
        the booking/quote exists. Builds a pricing context from the wizard inputs
        and runs the advanced-pricing engine per line. Returns adjusted unit prices.
        Falls back to list price when no engine/rules apply."""
        product_lines = vals.get('product_lines') or []
        if not product_lines:
            return {'lines': [], 'total': 0.0}

        partner_id = vals.get('patient_id') or False
        partner = self.env['res.partner'].browse(partner_id) if partner_id else self.env['res.partner']
        pricelist = partner.property_product_pricelist if partner and hasattr(partner, 'property_product_pricelist') else False

        # Resolve a pricing engine (pricelist engine first, else global default)
        engine = False
        if pricelist and getattr(pricelist, 'advanced_engine_id', False):
            engine = pricelist.advanced_engine_id
        else:
            try:
                config = self.env['advanced.pricing.config'].get_config()
                engine = config.default_engine_id
            except Exception:
                engine = False

        # Build the booking context the pricing rules evaluate against
        time_hour = vals.get('time_hour', 9.0) or 0.0
        appointment_hour = int(time_hour)
        weekday = None
        date_obj = None
        try:
            from datetime import datetime as _dt
            if vals.get('date'):
                date_obj = _dt.strptime(vals['date'], '%Y-%m-%d').date()
                weekday = date_obj.weekday()
        except (ValueError, TypeError):
            weekday = None

        # Public-holiday multiplier (TET/national) — same source the confirmed
        # quote uses, so the live preview matches the final price.
        holiday_info = {'is_holiday': False, 'holiday_type': False, 'multiplier': 1.0}
        if date_obj is not None:
            try:
                holiday_info = self.env['sale.order']._check_holiday(date_obj)
            except Exception:
                pass

        # One-way clinic→home driving distance already stored on the client,
        # so distance-based rules preview correctly before the booking exists.
        distance = 0.0
        if partner and getattr(partner, 'clinic_drive_distance_km', 0):
            distance = partner.clinic_drive_distance_km or 0.0

        base_context = {
            'partner_id': partner_id,
            'appointment_hour': appointment_hour,
            'service_type': vals.get('service_type'),
            'service_location': vals.get('service_location'),
            'is_weekend': weekday in (5, 6) if weekday is not None else False,
            'is_after_hours': appointment_hour < 7 or appointment_hour >= 19,
            'is_holiday': holiday_info.get('is_holiday', False),
            'holiday_type': holiday_info.get('holiday_type', False),
            'holiday_multiplier': holiday_info.get('multiplier', 1.0) or 1.0,
            'distance': distance,
            'urgency': 'normal',
            'priority': '1',
        }

        # Plain-language factor chips describing the booking conditions in play
        factors = self._quick_booking_pricing_factors(base_context)

        lines = []
        total = 0.0
        for pl in product_lines:
            product = self.env['product.product'].browse(pl['product_id'])
            if not product.exists():
                continue
            qty = pl.get('qty', 1)
            base_price = product.list_price or 0.0
            if pricelist:
                try:
                    base_price = pricelist._get_product_price(product, qty)
                except Exception:
                    pass
            unit_price = base_price
            rules = []
            if engine:
                ctx = dict(base_context)
                code = product.default_code or ''
                ctx['region'] = 'HCMC' if '_tphcm' in code else ('Hanoi' if '_hanoi' in code else '')
                try:
                    unit_price = engine.calculate_price(product.id, qty, partner_id, ctx)
                    rules = engine.explain_applied_rules(product.id, partner_id, qty, ctx)
                except Exception:
                    unit_price = base_price
            lines.append({
                'product_id': product.id,
                'unit_price': unit_price,
                'base_price': base_price,
                'adjusted': abs((unit_price or 0) - (base_price or 0)) > 0.001,
                'rules': rules,
            })
            total += (unit_price or 0) * qty

        return {'lines': lines, 'total': total, 'factors': factors}

    @api.model
    def _quick_booking_pricing_factors(self, ctx):
        """Build the highlighted condition chips (Home Visit, After Hours,
        Weekend, Distance, Holiday) shown next to the auto-priced quote."""
        factors = []
        loc = ctx.get('service_location')
        if loc == 'home':
            factors.append({'key': 'home', 'label': 'Home Visit'})
        elif loc == 'clinic':
            factors.append({'key': 'clinic', 'label': 'Clinic Visit'})
        if ctx.get('distance'):
            factors.append({'key': 'pin', 'label': 'Distance: %.1f km' % ctx['distance']})
        if ctx.get('is_after_hours'):
            factors.append({'key': 'moon', 'label': 'After Hours'})
        if ctx.get('is_weekend'):
            factors.append({'key': 'calendar', 'label': 'Weekend'})
        if ctx.get('is_holiday'):
            factors.append({'key': 'flag', 'label': 'Holiday (%s)' % (ctx.get('holiday_type') or 'Public')})
        return factors

    @api.model
    def check_slot_availability(self, patient_id, date_str, facility_id, staff_ids=None):
        """Check 30-min slot availability for a given date.
        Returns slots with conflict info for staff and patient."""
        from datetime import datetime as dt_cls, timedelta
        import pytz

        if not date_str:
            return {'slots': []}

        try:
            check_date = dt_cls.strptime(date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            return {'slots': []}

        tz_name = 'Asia/Ho_Chi_Minh'
        if facility_id:
            facility = self.env['health.facility'].browse(facility_id)
            if facility.exists() and hasattr(facility, 'timezone') and facility.timezone:
                tz_name = facility.timezone
        tz = pytz.timezone(tz_name)

        day_start_local = tz.localize(dt_cls.combine(check_date, dt_cls.min.time()))
        day_end_local = day_start_local + timedelta(days=1)
        day_start_utc = day_start_local.astimezone(pytz.UTC).replace(tzinfo=None)
        day_end_utc = day_end_local.astimezone(pytz.UTC).replace(tzinfo=None)

        patient_bookings = []
        if patient_id:
            patient_bookings = self.search([
                ('patient_id', '=', patient_id),
                ('scheduled_datetime', '>=', day_start_utc),
                ('scheduled_datetime', '<', day_end_utc),
                ('state', 'not in', ['cancelled', 'rejected']),
            ])

        staff_bookings = {}
        if staff_ids:
            assignments = self.env['health.staff.assignment'].search([
                ('staff_id', 'in', staff_ids),
                ('state', 'not in', ['cancelled', 'template']),
                ('fso_id.scheduled_datetime', '>=', day_start_utc),
                ('fso_id.scheduled_datetime', '<', day_end_utc),
                ('fso_id.state', 'not in', ['cancelled', 'rejected']),
            ])
            for a in assignments:
                fso = a.fso_id
                if not fso or not fso.scheduled_datetime:
                    continue
                sid = a.staff_id.id
                if sid not in staff_bookings:
                    staff_bookings[sid] = []
                utc_dt = pytz.UTC.localize(fso.scheduled_datetime)
                local_dt = utc_dt.astimezone(tz)
                duration = fso.scheduled_duration or 60
                staff_bookings[sid].append({
                    'start': local_dt.hour + local_dt.minute / 60.0,
                    'end': local_dt.hour + local_dt.minute / 60.0 + duration / 60.0,
                    'name': a.staff_id.name or '',
                    'booking': fso.name or '',
                })

        patient_ranges = []
        for bk in patient_bookings:
            if not bk.scheduled_datetime:
                continue
            utc_dt = pytz.UTC.localize(bk.scheduled_datetime)
            local_dt = utc_dt.astimezone(tz)
            duration = bk.scheduled_duration or 60
            start_h = local_dt.hour + local_dt.minute / 60.0
            patient_ranges.append({
                'start': start_h,
                'end': start_h + duration / 60.0,
                'booking': bk.name or '',
            })

        slots = []
        for h in range(7, 21):
            for m in (0, 30):
                hour_f = h + m / 60.0
                time_str = f'{h:02d}:{m:02d}'

                conflicts = []
                patient_conflict = False

                for pr in patient_ranges:
                    if pr['start'] <= hour_f < pr['end']:
                        patient_conflict = True
                        conflicts.append({
                            'type': 'patient',
                            'booking': pr['booking'],
                        })
                        break

                if staff_ids:
                    for sid in staff_ids:
                        for sb in staff_bookings.get(sid, []):
                            if sb['start'] <= hour_f < sb['end']:
                                conflicts.append({
                                    'type': 'staff',
                                    'name': sb['name'],
                                    'booking': sb['booking'],
                                })
                                break

                slots.append({
                    'time': time_str,
                    'hour': hour_f,
                    'available': len(conflicts) == 0,
                    'patient_conflict': patient_conflict,
                    'conflicts': conflicts,
                })

        return {'slots': slots}

    @api.model
    def action_create_from_quick_booking_owl(self, vals):
        """Create a single FSO booking from the quick booking OWL wizard.
        If vals.draft_only=True, creates booking in draft state without confirming."""
        import pytz

        patient_id = vals.get('patient_id')
        service_type = vals.get('service_type', 'home_visit')
        duration_hours = vals.get('duration_hours', 2)
        time_hour = vals.get('time_hour', 9.0)
        date_str = vals.get('date')
        facility_id = vals.get('facility_id')
        notes = vals.get('notes', '')
        product_lines = vals.get('product_lines') or []
        staff_id = vals.get('staff_id') or False
        doctor_id = vals.get('doctor_id') or False
        package_id = vals.get('package_id') or False
        assigned_staff_ids = vals.get('assigned_staff_ids') or []
        lead_id = vals.get('lead_id') or False
        draft_only = vals.get('draft_only', False)

        # Auto-create / resolve the client from the contact when none was selected
        # (booking opened from a contact with only a client name).
        if not patient_id and lead_id:
            lead = self.env['crm.lead'].browse(lead_id)
            if lead.exists():
                try:
                    client = lead._resolve_booking_client(
                        force_new=bool(vals.get('create_new_client')),
                        address=vals.get('client_address') or None,
                        facility_id=facility_id,
                    )
                except (UserError, ValidationError) as e:
                    return {'success': False, 'error': e.args[0] if e.args else str(e)}
                patient_id = client.id if client else False

        if not patient_id or not date_str:
            return {'success': False, 'error': 'Missing required fields (client, date).'}

        try:
            from datetime import datetime as dt_cls
            check_date = dt_cls.strptime(date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            return {'success': False, 'error': 'Invalid date format.'}

        facility = self.env['health.facility'].browse(facility_id)
        tz_name = 'Asia/Ho_Chi_Minh'
        if facility.exists() and hasattr(facility, 'timezone') and facility.timezone:
            tz_name = facility.timezone
        tz = pytz.timezone(tz_name)

        hours = int(time_hour)
        minutes = int(round((time_hour - hours) * 60))
        from datetime import datetime as dt_cls2
        local_dt = dt_cls2.combine(check_date, dt_cls2.min.time()).replace(hour=hours, minute=minutes)
        local_dt = tz.localize(local_dt)
        utc_dt = local_dt.astimezone(pytz.UTC).replace(tzinfo=None)

        location_map = {
            'home_visit': 'home', 'clinic_visit': 'clinic', 'consultation': 'clinic',
            'telemedicine': 'online', 'emergency': 'home', 'follow_up': 'home',
            'preventive': 'clinic', 'rehabilitation': 'clinic', 'vaccination': 'clinic',
            'diagnostic': 'clinic',
        }
        service_location = vals.get('service_location') or location_map.get(service_type, 'home')
        service_address = (vals.get('service_address') or '').strip()

        fso_vals = {
            'patient_id': patient_id,
            'service_type': service_type,
            'facility_id': facility_id,
            'scheduled_datetime': utc_dt,
            'scheduled_duration': int(duration_hours * 60),
            'intake_notes': notes or '',
            'service_location': service_location,
        }
        if service_address:
            fso_vals['service_address'] = service_address
        if lead_id:
            fso_vals['crm_lead_id'] = lead_id
        fso = self.create(fso_vals)

        quote_summary = {}
        if product_lines and len(product_lines) > 0:
            patient = self.env['res.partner'].browse(patient_id)
            pricelist = patient.property_product_pricelist if hasattr(patient, 'property_product_pricelist') else False

            so_vals = {
                'partner_id': patient_id,
                'origin': fso.name or '',
                # Link to the FSO so advanced pricing auto-applies the booking
                # conditions (time, location, service type, priority, distance).
                'fso_id': fso.id,
                'order_line': [],
            }
            if pricelist:
                so_vals['pricelist_id'] = pricelist.id

            for pl in product_lines:
                product = self.env['product.product'].browse(pl['product_id'])
                if not product.exists():
                    continue
                qty = pl.get('qty', 1)
                price = product.list_price or 0
                if pricelist:
                    try:
                        price = pricelist._get_product_price(product, qty)
                    except Exception:
                        pass
                so_vals['order_line'].append((0, 0, {
                    'product_id': product.id,
                    'product_uom_qty': qty,
                    'price_unit': price,
                }))

            if so_vals['order_line']:
                so = self.env['sale.order'].create(so_vals)
                fso.write({'sale_order_id': so.id})
                # Recalculate line prices from the booking conditions (advanced pricing)
                try:
                    so.order_line._compute_advanced_price()
                except Exception:
                    pass
                # Plain-language pricing breakdown (which rules fired + why),
                # so the confirmation shows the same explanation as the live quote.
                breakdown = {}
                try:
                    breakdown = so._build_pricing_breakdown_data() or {}
                except Exception:
                    breakdown = {}
                bd_lines = breakdown.get('lines', {}) if breakdown else {}
                summary_lines = [{
                    'name': line.product_id.name or '',
                    'qty': line.product_uom_qty,
                    'unit_price': line.price_unit,
                    'subtotal': line.price_subtotal,
                    'base_price': line.base_price or line.product_id.list_price or 0,
                    'rules': bd_lines.get(str(line.id), {}).get('rules', []),
                } for line in so.order_line]
                quote_summary = {
                    'lines': summary_lines,
                    'total_per_booking': so.amount_total,
                    'total_all': so.amount_total,
                    'factors': breakdown.get('factors', []) if breakdown else [],
                }

        if not draft_only:
            if package_id and hasattr(fso, 'package_ids'):
                try:
                    fso.write({'package_ids': [(4, package_id)]})
                except Exception:
                    pass
            if doctor_id:
                try:
                    fso.write({'primary_doctor_id': doctor_id})
                except Exception:
                    pass

            try:
                fso.action_confirm_booking()
            except Exception:
                pass

            all_staff = list(assigned_staff_ids)
            if staff_id and staff_id not in all_staff:
                all_staff = [staff_id] + all_staff
            for sid in all_staff:
                try:
                    role = 'lead' if sid == staff_id else 'support'
                    existing = self.env['health.staff.assignment'].search([
                        ('fso_id', '=', fso.id),
                        ('staff_id', '=', sid),
                        ('state', 'not in', ['cancelled', 'template']),
                    ], limit=1)
                    if not existing:
                        self.env['health.staff.assignment'].create({
                            'fso_id': fso.id,
                            'staff_id': sid,
                            'assignment_role': role,
                            'state': 'draft',
                        })
                except Exception:
                    pass

        service_type_dict = _selection_labels(self, 'service_type')
        service_label = service_type_dict.get(service_type, service_type or '')
        staff_name = ''
        if staff_id:
            try:
                emp = self.env['hr.employee'].browse(staff_id)
                staff_name = emp.name or ''
            except Exception:
                pass

        date_display = local_dt.strftime('%d %b %Y, %H:%M')

        if lead_id:
            lead = self.env['crm.lead'].browse(lead_id)
            if lead.exists():
                lead.write({'contact_outcome': 'service_booked'})

        return {
            'success': True,
            'booking_id': fso.id,
            'booking_name': fso.name or '',
            'patient_name': fso.patient_id.name or '',
            'service_label': service_label,
            'date_display': date_display,
            'facility_name': facility.name or '',
            'staff_name': staff_name,
            'quote_summary': quote_summary,
        }

    def get_service_in_progress_data(self):
        """Single RPC returning all data for the Service In-Progress OWL component."""
        self.ensure_one()
        b = self

        # Patient
        p = b.patient_id
        patient_initials = ''
        if p and p.name:
            parts = p.name.split()
            patient_initials = ''.join(x[0] for x in parts if x)[:2].upper()
        patient = {
            'id': p.id if p else False,
            'name': p.name or '' if p else '',
            'initials': patient_initials,
            'age_gender': (p.age_display or '') if p else '',
        }

        # Staff
        staff = None
        if b.lead_staff_id:
            s = b.lead_staff_id
            s_init = ''
            if s.name:
                s_parts = s.name.split()
                s_init = ''.join(x[0] for x in s_parts if x)[:2].upper()
            staff = {
                'id': s.id,
                'name': s.name or '',
                'initials': s_init,
                'role': s.job_title or (s.job_id.name if s.job_id else ''),
                'phone': s.work_phone or s.mobile_phone or '',
            }

        service_label = _selection_labels(b, 'service_type').get(b.service_type, '') if b.service_type else ''
        priority_label = _selection_labels(b, 'priority').get(b.priority, '') if b.priority else ''

        # Timer
        start_iso = ''
        start_display = ''
        if b.actual_start_datetime:
            start_iso = b.actual_start_datetime.isoformat()
            start_display = b.actual_start_datetime.strftime('%H:%M')
        est_dur = b.scheduled_duration or 60
        est_end = ''
        if b.actual_start_datetime:
            end_dt = b.actual_start_datetime + timedelta(minutes=est_dur)
            est_end = end_dt.strftime('%H:%M')

        # Checklist from protocol steps
        checklist = []
        try:
            if b.clinical_protocol_id:
                for step in b.clinical_protocol_id.step_ids.sorted('sequence'):
                    checklist.append({
                        'id': step.id,
                        'name': step.name or '',
                        'required': step.is_required if hasattr(step, 'is_required') else False,
                        'done': False,
                        'time': '',
                    })
        except Exception:
            pass
        if not checklist:
            checklist = [
                {'id': 1, 'name': 'Patient identity verification', 'required': False, 'done': False, 'time': ''},
                {'id': 2, 'name': 'Review medical history & allergies', 'required': False, 'done': False, 'time': ''},
                {'id': 3, 'name': 'Record vital signs', 'required': True, 'done': False, 'time': ''},
                {'id': 4, 'name': 'Physical examination', 'required': True, 'done': False, 'time': ''},
                {'id': 5, 'name': 'Medication review & administration', 'required': False, 'done': False, 'time': ''},
                {'id': 6, 'name': 'Patient education & instructions', 'required': False, 'done': False, 'time': ''},
                {'id': 7, 'name': 'Post-visit summary & follow-up plan', 'required': True, 'done': False, 'time': ''},
            ]

        # Booking info
        booking = {
            'id': b.id,
            'name': b.name or '',
            'state': b.state or '',
            'service_type_label': service_label,
            'priority_label': priority_label,
            'priority': b.priority or '1',
            'address': b.patient_address_display or '',
            'special_requirements': b.special_requirements or '',
        }

        # Payment
        payment = {
            'base_price': b.base_price or 0,
            'travel_charge': b.travel_charge or 0,
            'urgency_charge': b.urgency_charge or 0,
            'total_price': b.total_price or 0,
            'has_invoice': bool(b.invoice_id),
            'invoice_id': b.invoice_id.id if b.invoice_id else False,
        }

        # Advanced-pricing breakdown of the linked quote: per service line, the
        # base price, the rules that fired (plain language) and the final price —
        # so the nurse sees WHY the price is what it is while delivering service.
        quote_breakdown = {}
        so = b.sale_order_id
        if so and getattr(so, 'use_advanced_pricing', False):
            try:
                bd = so._build_pricing_breakdown_data() or {}
            except Exception:
                bd = {}
            if bd:
                bd_lines = bd.get('lines', {})
                quote_breakdown = {
                    'factors': bd.get('factors', []),
                    'lines': [{
                        'name': info.get('name', ''),
                        'base': info.get('base', 0),
                        'final': info.get('final', 0),
                        'qty': info.get('qty', 1),
                        'subtotal': info.get('subtotal', 0),
                        'rules': info.get('rules', []),
                    } for info in bd_lines.values()],
                    'total': so.amount_total or 0,
                }
        payment['quote_breakdown'] = quote_breakdown

        # Timeline
        timeline = []
        try:
            messages = self.env['mail.message'].search([
                ('res_id', '=', b.id),
                ('model', '=', 'health.fieldservice.order'),
                ('message_type', 'in', ['comment', 'notification']),
            ], order='date desc', limit=10)
            for msg in messages:
                timeline.append({
                    'body': msg.body or '',
                    'date': msg.date.strftime('%H:%M') if msg.date else '',
                    'author': msg.author_id.name if msg.author_id else '',
                })
        except Exception:
            pass

        return {
            'booking': booking,
            'patient': patient,
            'staff': staff,
            'timer': {
                'start_iso': start_iso,
                'start_display': start_display,
                'est_duration_minutes': est_dur,
                'est_end': est_end,
            },
            'checklist': checklist,
            'payment': payment,
            'timeline': timeline,
        }

    def get_staff_assignment_data(self):
        """Single RPC for the Staff Assignment OWL wizard."""
        self.ensure_one()
        b = self

        service_label = _selection_labels(b, 'service_type').get(b.service_type, '') if b.service_type else ''
        priority_label = _selection_labels(b, 'priority').get(b.priority, '') if b.priority else ''

        time_range = ''
        date_label = ''
        if b.scheduled_datetime:
            start = b.scheduled_datetime
            end = b.estimated_end_datetime
            date_label = start.strftime('%b %d, %Y')
            time_range = start.strftime('%H:%M')
            if end:
                time_range += f" — {end.strftime('%H:%M')}"

        patient_name = b.patient_id.name or '' if b.patient_id else ''
        patient_initials = ''
        if patient_name:
            parts = patient_name.split()
            patient_initials = ''.join(x[0] for x in parts if x)[:2].upper()

        booking = {
            'id': b.id,
            'name': b.name or '',
            'patient_name': patient_name,
            'patient_initials': patient_initials,
            'patient_id': b.patient_id.id if b.patient_id else False,
            'service_type_label': service_label,
            'date_label': date_label,
            'time_range': time_range,
            'address': b.patient_address_display or '',
            'priority': b.priority or '1',
            'priority_label': priority_label,
        }

        staff_list = []
        try:
            # Same nurse-only + facility scope as the booking/recurring/
            # reschedule flows, so the staff picker is consistent everywhere.
            facility_clause = []
            if b.facility_id:
                facility_clause = [('healthcare_facility_id', '=', b.facility_id.id)]
                if not self.env['hr.employee'].sudo().search_count([
                    ('is_healthcare_staff', '=', True),
                    ('employment_status', '=', 'active'),
                ] + facility_clause):
                    facility_clause = []
            employees = self.env['hr.employee'].sudo().search([
                ('is_healthcare_staff', '=', True),
                ('employment_status', '=', 'active'),
                # nurse-only: staff must hold the Nurse access role.
                ('is_nurse_role', '=', True),
            ] + facility_clause, order='name', limit=30)

            scheduled_date = b.scheduled_datetime.date() if b.scheduled_datetime else fields.Date.today()

            for emp in employees:
                initials = ''
                if emp.name:
                    p = emp.name.split()
                    initials = ''.join(x[0] for x in p if x)[:2].upper()

                today_count = 0
                try:
                    today_count = self.search_count([
                        ('lead_staff_id', '=', emp.id),
                        ('scheduled_datetime', '>=', datetime.combine(scheduled_date, datetime.min.time())),
                        ('scheduled_datetime', '<=', datetime.combine(scheduled_date, datetime.max.time())),
                        ('state', 'not in', ['cancelled']),
                    ])
                except Exception:
                    pass

                score = max(50, 95 - (today_count * 8))

                staff_list.append({
                    'id': emp.id,
                    'name': emp.name or '',
                    'initials': initials,
                    'role': emp.job_title or (emp.job_id.name if emp.job_id else ''),
                    'today_bookings': today_count,
                    'score': score,
                })
        except Exception:
            pass

        staff_list.sort(key=lambda x: x['score'], reverse=True)
        suggestions = staff_list[:3]
        others = staff_list[3:7]

        schedule_blocks = []
        if suggestions:
            for s in suggestions[:3]:
                blocks = []
                try:
                    fsos = self.search([
                        ('lead_staff_id', '=', s['id']),
                        ('scheduled_datetime', '>=', datetime.combine(scheduled_date, datetime.min.time())),
                        ('scheduled_datetime', '<=', datetime.combine(scheduled_date, datetime.max.time())),
                        ('state', 'not in', ['cancelled']),
                    ], order='scheduled_datetime')
                    for fso in fsos:
                        if fso.scheduled_datetime and fso.estimated_end_datetime:
                            blocks.append({
                                'start_hour': fso.scheduled_datetime.hour + fso.scheduled_datetime.minute / 60.0,
                                'end_hour': fso.estimated_end_datetime.hour + fso.estimated_end_datetime.minute / 60.0,
                                'name': fso.name or '',
                                'type': 'existing',
                            })
                except Exception:
                    pass
                schedule_blocks.append({
                    'staff_id': s['id'],
                    'staff_name': s['name'],
                    'blocks': blocks,
                })

        proposed_block = None
        if b.scheduled_datetime and b.estimated_end_datetime:
            proposed_block = {
                'start_hour': b.scheduled_datetime.hour + b.scheduled_datetime.minute / 60.0,
                'end_hour': b.estimated_end_datetime.hour + b.estimated_end_datetime.minute / 60.0,
                'name': b.name or '',
            }

        return {
            'booking': booking,
            'suggestions': suggestions,
            'others': others,
            'schedule_blocks': schedule_blocks,
            'proposed_block': proposed_block,
        }
