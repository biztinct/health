# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.addons.health_base.models.phone_utils import normalize_vn_phone


def _selection_health_contact_outcome(model):
    return [
        ('service_booked', model.env._('Service Booked')),
        ('pending_follow_up', model.env._('Pending Follow-up')),
        ('rejected', model.env._('Rejected')),
        ('no_response', model.env._('No Response')),
        ('not_qualified', model.env._('Not Qualified')),
        ('future_opportunity', model.env._('Future Opportunity')),
    ]


def _selection_clinical_priority(model):
    return [
        ('routine', model.env._('Routine')),
        ('urgent', model.env._('Urgent')),
        ('emergency', model.env._('Emergency')),
        ('preventive', model.env._('Preventive')),
    ]


def _selection_vietnamese_channel(model):
    return [
        ('zalo', model.env._('Zalo')),
        ('facebook', model.env._('Facebook')),
        ('linkedin', model.env._('LinkedIn')),
        ('website', model.env._('Website')),
        ('phone', model.env._('Phone Call')),
        ('referral', model.env._('Referral')),
        ('walk_in', model.env._('Walk-in')),
        ('advertisement', model.env._('Advertisement')),
        ('word_of_mouth', model.env._('Word of Mouth')),
    ]


def _selection_contact_outcome(model):
    return [
        ('service_booked', model.env._('Service Booked')),
        ('pending_follow_up', model.env._('Pending Follow-up')),
        ('rejected', model.env._('Rejected')),
        ('no_response', model.env._('No Response')),
        ('booking_lost', model.env._('Booking Lost')),
    ]


def _selection_contact_status(model):
    return [
        ('active', model.env._('Initial Contact')),
        ('booking', model.env._('Booking')),
        ('lead', model.env._('Lead')),
        ('lost_booking', model.env._('Lost Booking')),
        ('spam', model.env._('Spam Call')),
    ]


def _selection_contacting_on_behalf(model):
    return [
        ('self', model.env._('Self')),
        ('other', model.env._('Another Person')),
    ]


def _selection_mode_of_contact(model):
    return [
        ('phone', model.env._('Phone Call')),
        ('zalo', model.env._('Zalo')),
        ('facebook', model.env._('Facebook')),
        ('email', model.env._('Email')),
        ('website', model.env._('Website')),
        ('chatbox', model.env._('Chatbox')),
        ('walk_in', model.env._('Walk-in')),
    ]


def _selection_escalated_to(model):
    return [
        ('head_nurse', model.env._('Head Nurse')),
        ('om', model.env._('Operations Manager')),
        ('duty_doctor', model.env._('Duty Doctor')),
        ('other', model.env._('Other')),
    ]


class HealthLead(models.Model):
    """
    Healthcare CRM Lead extending standard Odoo CRM functionality
    Inherits from crm.lead to leverage all standard CRM features
    """
    _inherit = 'crm.lead'

    # Healthcare-specific service interest
    service_interest = fields.Selection([
        ('home_visit', 'Home Visit'),
        ('clinic_visit', 'Clinic Visit'),
        ('consultation', 'Consultation'),
        ('follow_up', 'Follow-up Care'),
        ('emergency', 'Emergency Care'),
        ('preventive', 'Preventive Care'),
        ('rehabilitation', 'Rehabilitation'),
        ('palliative', 'Palliative Care'),
    ], string='Service Interest', help='Type of healthcare service the lead is interested in')

    # Healthcare contact outcome
    health_contact_outcome = fields.Selection(
        _selection_health_contact_outcome,
        string='Healthcare Outcome',
        help='Outcome of healthcare contact',
    )

    # Clinical priority classification
    clinical_priority = fields.Selection(
        _selection_clinical_priority,
        string='Clinical Priority',
        default='routine',
        help='Clinical urgency classification',
    )

    # Vietnamese healthcare channels (extends standard utm_source)
    vietnamese_channel = fields.Selection(
        _selection_vietnamese_channel,
        string='Vietnamese Channel',
        help='Specific Vietnamese contact channel',
    )

    # Contact relationship identification
    contact_relationship_type = fields.Selection([
        ('client', 'Client'),
        ('caregiver', 'Caregiver'),
        ('payer', 'Payer'),
        ('referrer', 'Referrer'),
        ('emergency_contact', 'Emergency Contact'),
        ('legal_guardian', 'Legal Guardian'),
        ('healthcare_proxy', 'Healthcare Proxy'),
        ('client_representative', 'Client Representative'),
        ('family_member', 'Family Member'),
        ('friend', 'Friend'),
        ('professional', 'Professional Care Provider'),
    ], string='I am the:', default='client',
       help='client')
    
    client_name = fields.Char(
        string='Client Name',
        help='client (when you are not the client yourself)'
    )

    # Display-only: the client this contact belongs to. If the contact is the
    # client themselves -> their own name; otherwise (payer/caregiver/guardian…)
    # the linked client resolved from patient_id or health.client.relation.
    related_client_name = fields.Char(
        string='Client Name',
        compute='_compute_related_client_name',
        help='The client this contact belongs to — themselves if they are the '
             'client, otherwise the linked client (payer/caregiver/guardian…).'
    )

    # Healthcare relationships
    patient_id = fields.Many2one(
        'res.partner', 
        string='Client',
        domain=[('is_patient', '=', True)],
        help='client record if converted'
    )
    
    appointment_ids = fields.One2many(
        'health.appointment', 
        'lead_id', 
        string='Appointments',
        help='Appointments generated from this lead'
    )

    # Service requirements
    service_requirements = fields.Text(
        'Service Requirements',
        help='Specific healthcare service requirements and notes'
    )

    # Lead qualification fields
    has_health_insurance = fields.Boolean('Has Health Insurance')
    insurance_provider = fields.Char('Insurance Provider')
    preferred_language = fields.Selection([
        ('vietnamese', 'Vietnamese'),
        ('english', 'English'),
        ('both', 'Both'),
    ], string='Preferred Language', default='vietnamese')

    # Geographic preferences
    preferred_service_area = fields.Many2one(
        'health.service.area',
        string='Preferred Service Area'
    )
    
    distance_from_clinic = fields.Float(
        'Distance from Clinic (km)',
        help='Distance from nearest clinic'
    )

    # Follow-up management
    next_follow_up_date = fields.Datetime('Next Follow-up Date')
    follow_up_notes = fields.Text('Follow-up Notes')
    follow_up_count = fields.Integer('Follow-up Count', default=0)
    
    # Booking tracking
    last_booking_date = fields.Date(
        'Last Booking Date',
        compute='_compute_last_booking_date',
        store=True,
        help='Date of last completed booking for this lead\'s client'
    )
    booking_within_30_days = fields.Boolean(
        'Recent Booking',
        compute='_compute_last_booking_date',
        store=True,
        help='True if last booking was within 30 days'
    )
    
    # Rejection and outcome tracking
    reason_if_rejected = fields.Text(
        'Reason if Rejected', 
        help='Detailed reason if the lead was rejected or lost'
    )
    
    # Computed duration fields
    day_open = fields.Integer(
        'Days Open',
        compute='_compute_days_open',
        store=True,
        help='Number of days since the lead was created'
    )

    day_close = fields.Integer(
        'Days to Close',
        compute='_compute_days_close',
        store=True,
        help='Number of days from creation to close (if closed)'
    )

    # Duplicate/similar leads count for merge functionality
    duplicate_lead_count = fields.Integer(
        'Duplicate Leads',
        compute='_compute_duplicate_lead_count',
        help='Number of similar/duplicate leads found'
    )

    # Phone duplicate detection for confirmation dialog
    phone_duplicate_lead_id = fields.Many2one(
        'crm.lead', string='Existing Contact with Same Phone',
        compute='_compute_phone_duplicate', store=False,
        help='If set, an existing contact/lead with the same phone number was found'
    )
    phone_duplicate_name = fields.Char(
        'Duplicate Contact Name', compute='_compute_phone_duplicate', store=False,
    )
    phone_duplicate_code = fields.Char(
        'Duplicate Contact Code', compute='_compute_phone_duplicate', store=False,
    )

    # CRITICAL: FROM EXCEL REQUIREMENTS - Lead Management Table
    next_action_at = fields.Datetime(
        'Next Action At',
        help='From Excel: next_action_at [Compulsory] - When next action should be taken'
    )
    
    # Additional Excel Requirements - Missing Fields
    unique_contact_code = fields.Char(
        'Unique Contact Code',
        help='Sequential contact number per city (from Excel requirement)',
        copy=False
    )
    
    # Moved from res.partner - Lead-specific contact tracking fields
    contact_datetime = fields.Datetime(
        'Contact Date/Time',
        help='Auto-record with override capability (from Excel)',
        default=fields.Datetime.now
    )
    
    contact_outcome = fields.Selection(
        _selection_contact_outcome,
        string='Contact Outcome',
        help='From Excel: Contact Outcome field',
    )

    # =========================================================================
    # CONTACT-FIRST CRM FIELDS (New Contact Flow Requirements)
    # =========================================================================
    
    # Contact Status - tracks the lifecycle of a contact in the sales pipeline
    contact_status = fields.Selection(
        _selection_contact_status,
        string='Contact Status',
        default='active',
        help='Status of this contact in the sales pipeline',
        tracking=True,
    )
    
    # Spam caller flag - computed from contact_status for visual tagging
    is_spam_caller = fields.Boolean(
        string='Is Spam Caller',
        compute='_compute_is_spam_caller',
        store=True,
        help='Indicates if this contact has been marked as spam. Used for visual tagging.'
    )
    
    @api.depends('contact_status')
    def _compute_is_spam_caller(self):
        """Compute spam caller status based on contact_status"""
        for record in self:
            record.is_spam_caller = record.contact_status == 'spam'
    
    # =========================================================================
    # CALENDAR VIEW FIELDS
    # =========================================================================
    
    calendar_color = fields.Integer(
        'Calendar Color',
        compute='_compute_calendar_fields',
        store=True,
        help='Color for calendar entry based on activity status'
    )
    
    calendar_display_name = fields.Char(
        'Activity',
        compute='_compute_calendar_fields',
        store=True,
        help='Display name for calendar entry showing lead name and activity type'
    )
    
    calendar_date = fields.Datetime(
        'Calendar Date',
        compute='_compute_calendar_fields',
        store=True,
        help='Date for calendar display - uses earliest activity date, next_action_at, or create_date'
    )
    
    calendar_entry_type = fields.Selection([
        ('activity', 'Activity'),
        ('lead', 'Lead'),
    ],
        string='Calendar Entry Type',
        compute='_compute_calendar_fields',
        store=True,
        help='Type of calendar entry - Activity or Lead'
    )
    
    calendar_date_end = fields.Datetime(
        'Calendar End Date',
        compute='_compute_calendar_fields',
        store=True,
        help='End date for calendar display - 1 hour after start for duration-based display'
    )
    
    calendar_all_day = fields.Boolean(
        'All Day Event',
        compute='_compute_calendar_fields',
        store=True,
        default=True,
        help='Flag to indicate if this is an all-day event'
    )
    
    @api.depends('partner_id', 'patient_id')
    def _compute_last_booking_date(self):
        """
        Compute the last booking date from FSO orders linked to this lead's client.
        Also sets a flag if the booking was within 30 days.
        """
        FSO = self.env['health.fieldservice.order']
        today = fields.Date.today()
        thirty_days_ago = fields.Date.subtract(today, days=30)
        
        for record in self:
            last_booking = None
            within_30_days = False
            
            # Find most recent completed booking for this client
            client_id = record.patient_id.id or record.partner_id.id
            if client_id:
                booking = FSO.search([
                    ('patient_id', '=', client_id),
                    ('state', '=', 'completed'),
                    ('actual_end_datetime', '!=', False),
                ], order='actual_end_datetime desc', limit=1)
                
                if booking and booking.actual_end_datetime:
                    last_booking = booking.actual_end_datetime.date()
                    within_30_days = last_booking >= thirty_days_ago
            
            record.last_booking_date = last_booking
            record.booking_within_30_days = within_30_days

    @api.depends('name', 'activity_ids', 'activity_ids.activity_type_id', 'activity_ids.date_deadline', 'contact_status', 'next_action_at', 'create_date')
    def _compute_calendar_fields(self):
        """
        Compute calendar color, display name, entry type, and date based on activity status.
        
        Color Legend (Odoo calendar color indices):
        1 = Red (Overdue activities)
        2 = Orange (Activities due today)
        3 = Yellow (Lead without activities - needs attention)
        4 = Light Blue (Lead with future activities scheduled)
        5 = Green (Booking status)
        7 = Magenta (New leads/Active status)
        9 = Purple (Lost booking)
        
        Entry Types:
        - 'activity': Has scheduled activities (shown by activity date)
        - 'lead': No activities (shown by next_action_at or create_date)
        """
        today = fields.Date.today()
        
        for record in self:
            # Determine calendar display name and date
            activity_type = ''
            activity_icon = ''
            calendar_date = record.next_action_at  # Default to next_action_at
            entry_type = 'lead'  # Default to lead
            
            if record.activity_ids:
                entry_type = 'activity'
                # Get the nearest activity (sorted by date)
                sorted_activities = record.activity_ids.filtered(lambda a: a.date_deadline).sorted('date_deadline')
                if sorted_activities:
                    nearest_activity = sorted_activities[0]
                    if nearest_activity.activity_type_id:
                        activity_name = nearest_activity.activity_type_id.name
                        # Add icon based on activity type
                        activity_icons = {
                            'Call': '📞',
                            'Email': '📧',
                            'Meeting': '🤝',
                            'To-Do': '✅',
                            'Upload Document': '📄',
                        }
                        activity_icon = activity_icons.get(activity_name, '📋')
                        activity_type = f"{activity_icon} {activity_name}"
                    
                    # Convert activity date to datetime for calendar
                    if nearest_activity.date_deadline:
                        try:
                            activity_datetime = fields.Datetime.from_string(f"{nearest_activity.date_deadline} 09:00:00")
                            if activity_datetime:
                                if not calendar_date or activity_datetime < calendar_date:
                                    calendar_date = activity_datetime
                        except:
                            pass
            
            # Fallback to create_date if no other date is set (ensures ALL leads appear)
            if not calendar_date and record.create_date:
                calendar_date = record.create_date
            
            # Format: "Client name - Activity" (e.g., "Dec3 - 📞 Call") or "Client name [Lead]"
            client_name = record.name or 'Unnamed'
            if activity_type:
                record.calendar_display_name = f"{client_name} - {activity_type}"
            elif entry_type == 'lead':
                record.calendar_display_name = f"👤 {client_name}"
            else:
                record.calendar_display_name = client_name
                
            record.calendar_date = calendar_date
            record.calendar_entry_type = entry_type
            
            # Determine calendar color based on activity status
            if record.activity_ids:
                # Check for overdue activities
                overdue = any(act.date_deadline and act.date_deadline < today for act in record.activity_ids)
                due_today = any(act.date_deadline and act.date_deadline == today for act in record.activity_ids)
                
                if overdue:
                    record.calendar_color = 1  # Red - Overdue
                elif due_today:
                    record.calendar_color = 2  # Orange - Due today
                else:
                    record.calendar_color = 4  # Light Blue - Future activities
            else:
                # No activities - color by contact status
                if record.contact_status == 'booking':
                    record.calendar_color = 5  # Green - Booking
                elif record.contact_status == 'lead':
                    record.calendar_color = 3  # Yellow - Lead needs attention
                elif record.contact_status == 'lost_booking':
                    record.calendar_color = 9  # Purple - Lost
                elif record.contact_status == 'active':
                    record.calendar_color = 7  # Magenta - New/Active
                else:
                    record.calendar_color = 0  # Default
            
            # Compute end date for all-day event display (enables background colors)
            # Set as all-day events for better visual display
            record.calendar_all_day = True
            if calendar_date:
                # For all-day events, end date should be the same day
                # This creates an all-day block with background color
                record.calendar_date_end = calendar_date
            else:
                record.calendar_date_end = False
    
    # On behalf tracking - who is the contact calling for
    contacting_on_behalf = fields.Selection(
        _selection_contacting_on_behalf,
        string='Contacting On Behalf Of',
        default='self',
        help='Whether the caller is contacting for themselves or someone else',
    )
    
    # Mode of contact - how did the contact reach us
    mode_of_contact = fields.Selection(
        _selection_mode_of_contact,
        string='Mode of Contact',
        default='phone',
        help='How the contact reached out to us',
    )
    
    # Escalation tracking fields
    escalated_to = fields.Selection(
        _selection_escalated_to,
        string='Escalated To',
       help='Person/role this contact was escalated to')
    
    escalation_datetime = fields.Datetime(
        'Escalation Date/Time',
        help='When the contact was escalated'
    )
    
    escalation_notes = fields.Text(
        'Escalation Notes',
        help='Notes about why the contact was escalated'
    )
    
    # Telemedicine/Consultation referral
    referred_to_duty_doctor = fields.Boolean(
        'Referred to Duty Doctor',
        default=False,
        help='Contact was referred for telemedicine consultation'
    )
    
    referral_datetime = fields.Datetime(
        'Referral Date/Time',
        help='When the telemedicine referral was made'
    )
    
    referral_notes = fields.Text(
        'Referral Notes',
        help='Details provided for the telemedicine referral'
    )
    
    # Tags for contact categorization
    contact_tag_ids = fields.Many2many(
        'crm.tag',
        'crm_lead_contact_tag_rel',
        'lead_id', 'tag_id',
        string='Contact Tags',
        help='Tags to categorize this contact'
    )
    
    # Reason for Contact - link to lookup table
    reason_for_contact_id = fields.Many2one(
        'health.contact.reason',
        string='Reason for Contact',
        help='Primary reason why this person contacted us'
    )
    
    # On behalf of another person - link to partner or enter new name
    other_person_id = fields.Many2one(
        'res.partner',
        string='On Behalf Of Client',
        help='If contacting on behalf of another, select the client here',
        domain="[('is_patient', '=', True)]"
    )
    
    other_person_name = fields.Char(
        'Other Person Name',
        help='If the person is not in the system, enter their name here'
    )
    
    # Address field for contact
    street_address = fields.Text(
        'Address',
        help='Contact address'
    )
    
    # Spam caller tracking - mark phone as spam
    is_spam_caller = fields.Boolean(
        'Spam Caller',
        default=False,
        help='This phone number is marked as spam'
    )
    
    booking_status = fields.Selection([
        ('no_booking', 'No Booking'),
        ('pending', 'Booking Pending'),
        ('confirmed', 'Booking Confirmed'),
        ('completed', 'Booking Completed'),
        ('cancelled', 'Booking Cancelled')
    ], string='Booking Status', help='From Excel: Booking Status [Compulsory]', default='no_booking')

    booking_lost_reason = fields.Text(
        string='Booking Lost Reason',
        help='Reason why the booking was lost'
    )

    # Healthcare lead source tracking (moved from res.partner)
    healthcare_lead_source = fields.Selection([
        ('facebook_ad', 'Facebook Advertisement'),
        ('zalo_marketing', 'Zalo Marketing'),
        ('website_form', 'Website Contact Form'),
        ('phone_inquiry', 'Phone Inquiry'),
        ('referral_patient', 'Patient Referral'),
        ('referral_doctor', 'Doctor Referral'),
        ('walk_in', 'Walk-in'),
        ('health_fair', 'Health Fair'),
        ('community_outreach', 'Community Outreach'),
    ], string='Healthcare Lead Source')
    
    contact_type = fields.Selection([
        ('new', 'New Contact'),
        ('repeat', 'Repeat Contact'),
    ], string='Contact Type', 
       help='Whether this is a new or repeat contact')
    
    contact_reason_id = fields.Many2one(
        'health.contact.reason',
        string='Contact Reason',
        help='Reason for the initial contact (Sales/OM purposes)'
    )
    
    facility_id = fields.Many2one(
        'health.facility',
        string='Healthcare Facility',
        help='Associated healthcare facility for this lead'
    )
    
    lead_followup_required = fields.Boolean(
        'Lead Follow-up Required',
        default=False,
        help='Whether this lead requires follow-up action'
    )
    
    lead_reason_id = fields.Many2one(
        'health.lead.reason', 
        string='Lead Reason',
        help='Reason for this lead/opportunity (different from contact reason)'
    )
    
    # Province lookup for Vietnamese locations
    province_code = fields.Many2one(
        'health.province',
        string='Province/City',
        help='Vietnamese province or city for this lead'
    )
    
    # Catchment Province for service area assignment
    catchment_province_id = fields.Many2one(
        'health.catchment.province',
        string='Catchment Province',
        help='Catchment province/area for this lead'
    )

    # Vietnamese Address Fields
    named_area = fields.Char('Named Area', help='Khu vực đặt tên')
    apartment_number = fields.Char('Apartment Number', help='Số căn hộ')
    building_name = fields.Char('Building Name', help='Tên tòa nhà')
    house_number = fields.Char('House Number', help='Số nhà')
    sub_alley_number = fields.Char('Sub-Alley Number', help='Số ngách')
    alley_number = fields.Char('Alley Number', help='Số ngõ')
    ward_commune = fields.Char('Ward/Commune', help='Phường/Xã')
    # District (Quận/Huyện) — dropdown from the Vietnamese district master,
    # filtered by the chosen City (= catchment province). The standard `city`
    # Char stays populated (derived as "<District>, <City>") so address
    # formatting / lead→client sync keep working unchanged.
    district_id = fields.Many2one(
        'health.vietnamese.district', string='District',
        domain="[('province_name', '=', catchment_province_name)]",
        help='Quận/Huyện — filtered by the selected City (catchment province).')
    catchment_province_name = fields.Char(
        related='catchment_province_id.name', string='City Name', store=False,
        help='Helper for the District domain (the City = catchment province).')
    full_vietnamese_address = fields.Char(
        'Home Address',
        help='Complete home address'
    )

    # Secondary caregiver (Caregiver 2 ID)
    secondary_caregiver_id = fields.Many2one(
        'res.partner',
        string='Secondary Caregiver',
        domain=[('is_caregiver', '=', True)],
        help='Secondary caregiver for this lead (Caregiver 2 ID)'
    )
    
    # Whether the representative should be primary for their role
    is_primary_representative = fields.Boolean(
        'Primary Representative',
        default=False,
        help='Whether this representative should be the primary contact for their role'
    )
    
    # Healthcare relationships for leads
    primary_caregiver_id = fields.Many2one(
        'res.partner',
        string='Primary Caregiver',
        domain=[('is_caregiver', '=', True)],
        help='Primary caregiver for this lead'
    )
    
    primary_payer_id = fields.Many2one(
        'res.partner', 
        string='Primary Payer',
        domain=[('is_payer', '=', True)],
        help='Primary person/entity responsible for payments'
    )
    
    referrer_id = fields.Many2one(
        'res.partner',
        string='Referrer',
        domain=[('is_referrer', '=', True)],
        help='Person who referred this lead'
    )
    
    emergency_contact_id = fields.Many2one(
        'res.partner',
        string='Emergency Contact',
        domain=[('is_emergency_contact', '=', True)],
        help='Emergency contact for this lead'
    )
    
    client_representative_id = fields.Many2one(
        'res.partner',
        string='Client Representative',
        domain=[('is_representative', '=', True)],
        help='Person representing the client'
    )
    
    # Lead Status from Excel (extends standard CRM stage)
    lead_status = fields.Selection([
        ('new', 'New'),
        ('contacted', 'Contacted'),
        ('qualified', 'Qualified'),
        ('proposal', 'Proposal'),
        ('negotiation', 'Negotiation'),
        ('won', 'Won'),
        ('lost', 'Lost'),
    ], string='Lead Status', help='From Excel: Lead Status field')
    
    # Contact source tracking (FROM EXCEL REQUIREMENTS)
    contact_source = fields.Selection([
        ('inbound_call', 'Inbound Call'),
        ('outbound_call', 'Outbound Call'),
        ('email_inquiry', 'Email Inquiry'),
        ('website_form', 'Website Form'),
        ('social_media', 'Social Media'),
        ('referral', 'Referral'),
        ('advertisement', 'Advertisement'),
        ('event', 'Event/Fair'),
        ('walk_in', 'Walk-in'),
    ], string='Contact Source', help='From Excel: How the contact was initiated')

    @api.constrains('contact_relationship_type', 'client_name', 'patient_id')
    def _check_client_name_required(self):
        """Validate that the actual client is identified when the contact is not
        the client themselves. Either a free-text Client Name OR a linked Client
        (patient_id) satisfies this — the contact form now collects only the
        Client relation and auto-derives client_name from it."""
        for record in self:
            if record.contact_relationship_type != 'client' \
                    and not record.client_name and not record.patient_id:
                raise ValidationError(_(
                    'A Client is required when you are not the client yourself. '
                    'Please select (or create) the actual client/patient.'
                ))

    @api.onchange('patient_id')
    def _onchange_patient_id_sync_client_name(self):
        """Keep the (hidden) free-text client_name in sync with the linked Client
        so backend patient-creation/search/booking flows that read client_name
        keep working when the form only exposes the Client relation."""
        for record in self:
            if record.patient_id and not record.client_name:
                record.client_name = record.patient_id.name

    @api.depends('patient_id', 'contact_relationship_type', 'name', 'client_name', 'partner_id')
    def _compute_related_client_name(self):
        """Resolve the client this contact belongs to, for list display.
        1. patient_id set (converted)  -> authoritative client name
        2. contact IS the client       -> their own name
        3. representative (payer/…)     -> client via health.client.relation
        4. fallback                     -> free-text client_name captured at intake
        """
        Relation = self.env['health.client.relation']
        for lead in self:
            if lead.patient_id:
                lead.related_client_name = lead.patient_id.name
            elif lead.contact_relationship_type == 'client':
                lead.related_client_name = lead.name or (lead.partner_id.name or False)
            else:
                rel = Relation.search(
                    [('representative_id', '=', lead.partner_id.id)], limit=1
                ) if lead.partner_id else False
                lead.related_client_name = (rel.client_id.name if rel else False) or lead.client_name or False

    @api.depends('create_date')
    def _compute_days_open(self):
        """Compute number of days since lead was created"""
        for record in self:
            if record.create_date:
                today = fields.Date.today()
                create_date = record.create_date.date()
                record.day_open = (today - create_date).days
            else:
                record.day_open = 0

    @api.depends('create_date', 'date_closed')
    def _compute_days_close(self):
        """Compute number of days from creation to close"""
        for record in self:
            if record.create_date and record.date_closed:
                # Ensure both dates are date objects for consistent comparison
                create_date = record.create_date.date() if hasattr(record.create_date, 'date') else record.create_date
                close_date = record.date_closed.date() if hasattr(record.date_closed, 'date') else record.date_closed
                record.day_close = (close_date - create_date).days
            else:
                record.day_close = 0

    @api.depends('name', 'email_from', 'phone')
    def _compute_duplicate_lead_count(self):
        """Compute number of similar/duplicate leads based on name, email, or phone"""
        for record in self:
            if not record.id:
                record.duplicate_lead_count = 0
                continue

            domain = [('id', '!=', record.id), ('type', '=', 'opportunity')]

            # Build OR conditions for matching
            or_domains = []
            if record.email_from:
                or_domains.append([('email_from', '=ilike', record.email_from)])
            if record.phone:
                or_domains.append([('phone', '=', record.phone)])
            if record.name and len(record.name) > 3:
                or_domains.append([('name', '=ilike', record.name)])

            if or_domains:
                # Combine all OR conditions
                full_domain = domain + ['|'] * (len(or_domains) - 1) + [item for sublist in or_domains for item in sublist]
                record.duplicate_lead_count = self.search_count(full_domain)
            else:
                record.duplicate_lead_count = 0

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to set healthcare-specific defaults"""
        # Handle both single dict and list of dicts
        if not isinstance(vals_list, list):
            vals_list = [vals_list]
            
        for vals in vals_list:
            # Validate & normalize the Vietnamese phone AT LEAD CREATION TIME, so a
            # bad number is rejected here with a clear message rather than slipping
            # through to the booking save (where the lead→client conversion fails).
            for fname in self._vn_phone_fields_present:
                if vals.get(fname):
                    vals[fname] = normalize_vn_phone(vals[fname])

            # Derive the denormalized `city` string from District + City parts.
            self._vn_apply_city_from_parts(vals)

            # Generate unique contact code only for opportunities
            if not vals.get('unique_contact_code') and vals.get('type') == 'opportunity':
                vals['unique_contact_code'] = self._generate_unique_contact_code(vals)
            
            # Set default team to healthcare team if not specified
            if not vals.get('team_id'):
                healthcare_team = self.env.ref('health_crm.healthcare_crm_team', raise_if_not_found=False)
                if healthcare_team:
                    vals['team_id'] = healthcare_team.id
            
            # Set Vietnamese as default country if not specified
            if not vals.get('country_id') and not vals.get('partner_id'):
                vietnam = self.env.ref('base.vn', raise_if_not_found=False)
                if vietnam:
                    vals['country_id'] = vietnam.id
        
        # Create records and conditionally handle relationships
        records = super().create(vals_list)
        
        for record in records:
            if record._should_process_relationship():
                record._process_contact_relationship()
        
        return records
    
    # =========================================================================
    # Vietnamese phone validation — enforced AT LEAD CREATION TIME
    # =========================================================================
    # The lead's phone (and mobile) must already be a valid VN number on the
    # lead itself, so it never reaches the lead→client conversion (booking save)
    # as garbage. create()/write() normalize; this constraint is the safety net
    # for any other write path (imports, direct ORM writes, etc.).
    _VN_PHONE_FIELDS = ('phone', 'mobile')

    @property
    def _vn_phone_fields_present(self):
        """`_VN_PHONE_FIELDS` filtered to fields that actually exist on this
        registry. Some Odoo builds drop `mobile` from crm.lead, so iterating the
        raw tuple and doing self['mobile'] would KeyError."""
        return tuple(f for f in self._VN_PHONE_FIELDS if f in self._fields)

    @api.constrains('phone', 'mobile')
    def _check_vn_phone(self):
        for lead in self:
            for fname in self._vn_phone_fields_present:
                if lead[fname]:
                    normalize_vn_phone(lead[fname])  # raises ValidationError if invalid

    @api.onchange('phone', 'mobile')
    def _onchange_normalize_vn_phone(self):
        """Live-format the phone/mobile in the contact form (e.g. 938038028 ->
        0938038028) and warn immediately when an entry is not a valid number —
        so the user is corrected while typing the lead, not at booking save."""
        invalid = []
        for fname in self._vn_phone_fields_present:
            value = self[fname]
            if value:
                try:
                    self[fname] = normalize_vn_phone(value)
                except ValidationError:
                    invalid.append(value)
        if invalid:
            return {'warning': {
                'title': _("Invalid phone number"),
                'message': _(
                    "%s is not a valid phone number.\n\n"
                    "Enter a 9-digit number (a leading 0 is added automatically) "
                    "or a 10-digit number starting with a single 0."
                ) % ", ".join(invalid),
            }}

    # =========================================================================
    # District / City — derive the denormalized `city` string from the parts
    # =========================================================================
    def _vn_apply_city_from_parts(self, vals):
        """Derive `city` from district_id + catchment_province_id when those are
        set and `city` isn't explicitly provided (direct city writes honored)."""
        if 'city' in vals:
            return vals
        if 'district_id' not in vals and 'catchment_province_id' not in vals:
            return vals
        District = self.env['health.vietnamese.district']
        Province = self.env['health.catchment.province']
        if 'district_id' in vals:
            dname = District.browse(vals['district_id']).name if vals['district_id'] else False
        else:
            dname = self.district_id.name if self else False
        if 'catchment_province_id' in vals:
            pname = Province.browse(vals['catchment_province_id']).name if vals['catchment_province_id'] else False
        else:
            pname = self.catchment_province_id.name if self else False
        composed = self.env['res.partner']._vn_compose_city(dname, pname)
        if composed:
            vals['city'] = composed
        return vals

    @api.onchange('district_id', 'catchment_province_id')
    def _onchange_vn_city_parts(self):
        for lead in self:
            composed = lead.env['res.partner']._vn_compose_city(
                lead.district_id.name, lead.catchment_province_id.name)
            if composed:
                lead.city = composed
            # Drop a District that no longer belongs to the chosen City.
            if lead.district_id and lead.catchment_province_id \
                    and lead.district_id.province_name != lead.catchment_province_id.name:
                lead.district_id = False

    # =========================================================================
    # CRITICAL: Override phone/email sync to prevent contact→client contamination
    # =========================================================================
    # In standard Odoo CRM, lead.phone syncs back to partner_id.phone via
    # _inverse_phone. But in healthcare CRM, the caller (contact) can be a
    # different person than the client (partner_id). A caregiver's phone
    # should NOT overwrite the patient's phone.

    def _inverse_phone(self):
        """Override to prevent syncing contact phone to client partner.
        
        Only sync phone to partner if the caller IS the client.
        When a caregiver calls, lead.phone is the caregiver's phone,
        NOT the client's phone - so it must NOT be written to partner.
        """
        for lead in self:
            if lead.contact_relationship_type == 'client' or not lead.contact_relationship_type:
                # Caller IS the client - safe to sync phone to partner
                if lead._get_partner_phone_update(force_void=False):
                    lead.partner_id.phone = lead.phone
            # else: caller is NOT the client - do NOT sync phone
    
    def _inverse_email_from(self):
        """Override to prevent syncing contact email to client partner.
        
        Same logic as _inverse_phone - only sync when caller IS the client.
        """
        for lead in self:
            if lead.contact_relationship_type == 'client' or not lead.contact_relationship_type:
                # Caller IS the client - safe to sync email to partner
                if lead._get_partner_email_update(force_void=False):
                    lead.partner_id.email = lead.email_from
            # else: caller is NOT the client - do NOT sync email
    
    def _compute_phone(self):
        """Override to prevent partner phone from overwriting contact phone.
        
        When a caregiver calls, lead.phone should stay as the caregiver's phone,
        NOT be replaced by the client's (partner's) phone.
        """
        for lead in self:
            if lead.contact_relationship_type == 'client' or not lead.contact_relationship_type:
                # Caller IS the client - standard behavior
                if lead.partner_id.phone and lead._get_partner_phone_update():
                    lead.phone = lead.partner_id.phone
            # else: caller is NOT the client - keep the contact's phone
    
    def _compute_email_from(self):
        """Override to prevent partner email from overwriting contact email."""
        for lead in self:
            if lead.contact_relationship_type == 'client' or not lead.contact_relationship_type:
                # Caller IS the client - standard behavior  
                if lead.partner_id.email and lead._get_partner_email_update():
                    lead.email_from = lead.partner_id.email
            # else: caller is NOT the client - keep the contact's email

    def write(self, vals):
        """Override write to handle relationship changes and sync contact_status."""

        # Keep the phone format valid on every edit too (same rule as create).
        for fname in self._vn_phone_fields_present:
            if vals.get(fname):
                vals[fname] = normalize_vn_phone(vals[fname])

        # Derive the denormalized `city` string from District + City parts.
        if ('district_id' in vals or 'catchment_province_id' in vals) and 'city' not in vals:
            self[:1]._vn_apply_city_from_parts(vals)

        # Server-side sync: when contact_outcome changes, also update contact_status
        # This is required because contact_status is readonly in the form view,
        # so onchange-set values are NOT included in the save payload by Odoo.
        if 'contact_outcome' in vals and 'contact_status' not in vals:
            outcome_to_status = {
                'service_booked': 'booking',
                'pending_follow_up': 'lead',
                'rejected': 'lost_booking',
                'no_response': 'lead',
                'booking_lost': 'lost_booking',
            }
            new_status = outcome_to_status.get(vals['contact_outcome'])
            if new_status:
                vals['contact_status'] = new_status
            # Also sync health_contact_outcome for consistency
            if 'health_contact_outcome' not in vals:
                vals['health_contact_outcome'] = vals['contact_outcome']
        
        result = super().write(vals)
        
        # If relationship fields were changed, reprocess relationships only when conditions are met
        if any(field in vals for field in ['contact_relationship_type', 'client_name', 'name', 'contact_outcome', 'health_contact_outcome', 'stage_id']):
            for record in self:
                if record._should_process_relationship():
                    record._process_contact_relationship()
        
        return result
    
    @api.onchange('health_contact_outcome')
    def _onchange_health_contact_outcome(self):
        """
        Sync contact_status when health_contact_outcome changes.
        NOTE: health_contact_outcome is invisible on all forms, so this
        only fires from programmatic changes. The user-facing onchange
        is _onchange_contact_outcome below.
        """
        if not self.health_contact_outcome:
            return
        
        # Map health_contact_outcome values to contact_status
        outcome_to_status = {
            'service_booked': 'booking',      # Client Acquired → Booking status
            'pending_follow_up': 'lead',      # Continue Follow-up → Lead status
            'rejected': 'lost_booking',       # Rejected → Lost Booking status
            'no_response': 'lead',            # No Response → Keep as Lead
            'not_qualified': 'lost_booking',  # Not Qualified → Lost Booking status
            'future_opportunity': 'lead',     # Future Opportunity → Keep as Lead
        }
        
        new_status = outcome_to_status.get(self.health_contact_outcome)
        if new_status and self.contact_status != new_status:
            self.contact_status = new_status
            # Also sync contact_outcome for consistency
            self.contact_outcome = self.health_contact_outcome
    
    @api.onchange('contact_outcome')
    def _onchange_contact_outcome(self):
        """
        Sync contact_status when the user changes the visible Contact Outcome
        dropdown on the Lead Info form. This is the primary user-facing onchange.
        Also syncs health_contact_outcome for consistency.
        """
        if not self.contact_outcome:
            return
        
        # Map contact_outcome values to contact_status
        outcome_to_status = {
            'service_booked': 'booking',      # Service Booked → Booking status
            'pending_follow_up': 'lead',      # Pending Follow-up → Lead status
            'rejected': 'lost_booking',       # Rejected → Lost Booking status
            'no_response': 'lead',            # No Response → Keep as Lead
            'booking_lost': 'lost_booking',   # Booking Lost → Lost Booking status
        }
        
        new_status = outcome_to_status.get(self.contact_outcome)
        if new_status and self.contact_status != new_status:
            self.contact_status = new_status
            # Also sync health_contact_outcome for consistency
            self.health_contact_outcome = self.contact_outcome

    @api.onchange('phone')
    def _onchange_phone_duplicate(self):
        """Check if the entered phone number matches an existing contact/lead.
        If so, show a warning asking user to use existing or continue creating new."""
        if not self.phone or len(self.phone) < 5:
            return

        # Search for existing leads/contacts with the same phone
        domain = [('phone', '=', self.phone), ('type', '=', 'opportunity')]
        if self.id:
            domain.append(('id', '!=', self.id))

        existing = self.search(domain, limit=1)
        if existing:
            return {
                'warning': {
                    'title': _('⚠️ Existing Contact Found'),
                    'message': _(
                        'An existing contact with this phone number was found:\n\n'
                        '  • Name: %s\n'
                        '  • Code: %s\n'
                        '  • Status: %s\n\n'
                        'You can use the "Use Existing Contact" button near the phone field '
                        'to navigate to the existing record, or continue to create a new contact.'
                    ) % (
                        existing.name,
                        existing.unique_contact_code or 'N/A',
                        dict(existing._fields['contact_status']._description_selection(existing.env)).get(
                            existing.contact_status, existing.contact_status or 'N/A'
                        ),
                    ),
                }
            }

    @api.depends('phone')
    def _compute_phone_duplicate(self):
        """Compute whether an existing contact/lead has the same phone number."""
        for record in self:
            if not record.phone or len(record.phone) < 5:
                record.phone_duplicate_lead_id = False
                record.phone_duplicate_name = False
                record.phone_duplicate_code = False
                continue

            domain = [('phone', '=', record.phone), ('type', '=', 'opportunity')]
            if record.id:
                domain.append(('id', '!=', record.id))

            existing = self.search(domain, limit=1)
            record.phone_duplicate_lead_id = existing.id if existing else False
            record.phone_duplicate_name = existing.name if existing else False
            record.phone_duplicate_code = existing.unique_contact_code if existing else False

    def action_navigate_to_phone_duplicate(self):
        """Navigate to the existing contact/lead that has the same phone number."""
        self.ensure_one()
        if not self.phone_duplicate_lead_id:
            raise UserError(_('No duplicate contact found.'))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Existing Contact'),
            'res_model': 'crm.lead',
            'res_id': self.phone_duplicate_lead_id.id,
            'view_mode': 'form',
            'views': [[False, 'form']],
            'context': {'form_view_ref': 'health_crm.view_healthcare_opportunity_form'},
            'target': 'current',
        }
    
    def _generate_unique_contact_code(self, vals):
        """
        Generate unique contact code using the same format as client IDs.
        Format: PP 00000YYYY where:
        - PP = province code from catchment province (first 2 chars)
        - 00000 = sequential number (5 digits with leading zeros)
        - YYYY = current year
        
        This shares the same sequence as patient codes so that when a lead
        converts to a client, the same code is used.
        """
        from datetime import datetime
        
        # Get catchment province from vals or use default
        catchment_province_id = vals.get('catchment_province_id')
        catchment_province = None
        
        if catchment_province_id:
            catchment_province = self.env['health.catchment.province'].browse(catchment_province_id)
        
        # Get province code from catchment province
        if catchment_province and catchment_province.code:
            province_code = catchment_province.code[:2] if len(catchment_province.code) >= 2 else catchment_province.code
        else:
            # Default to '99' if no catchment province specified
            province_code = '99'
        
        # Get current year
        current_year = datetime.now().year
        
        # Use the SAME sequence code as patient IDs (shared between leads and patients)
        sequence_code = f'patient.{province_code}.{current_year}'
        
        # Check if sequence exists, if not create it
        sequence = self.env['ir.sequence'].sudo().search([
            ('code', '=', sequence_code)
        ], limit=1)
        
        if not sequence:
            # Create new sequence for this province/year combination
            sequence = self.env['ir.sequence'].sudo().create({
                'name': f'Client/Lead ID - Province {province_code} - {current_year}',
                'code': sequence_code,
                'implementation': 'standard',
                'prefix': '',
                'padding': 5,  # 5 digits with leading zeros
                'number_increment': 1,
                'number_next': 1,
            })
        
        # Get next sequence number
        seq_number = sequence.next_by_id()
        
        # Format: PP 00000YYYY (note the space)
        contact_code = f'{province_code} {seq_number}{current_year}'
        
        return contact_code

    def _process_contact_relationship(self):
        """Process contact relationship and create patient/representative records - ONLY for opportunities"""
        self.ensure_one()
        
        # Skip healthcare relationship processing for leads
        if self.type == 'lead':
            return
        
        if self.contact_relationship_type == 'client':
            # Contact is the client - create/find patient using contact name
            patient = self._get_or_create_patient()
            self.patient_id = patient.id
        else:
            # Contact is a representative - handle client and representative separately
            if not self.client_name:
                return  # Validation will catch this

            # Try to reuse the existing patient_id; if it was auto-created from the lead name,
            # rename it to the intended client_name to avoid a second patient record.
            patient = self.patient_id
            if patient:
                if self.client_name and patient.name != self.client_name:
                    patient = patient.with_context(skip_name_constraint=True)
                    patient.write({'name': self.client_name})
            else:
                # Check for existing clients with same name
                existing_patients = self.env['res.partner'].search([
                    ('name', '=', self.client_name),
                    ('is_patient', '=', True)
                ])

                if len(existing_patients) > 1:
                    # Multiple clients found - show wizard and exit (wizard will complete the process)
                    self._show_client_selection_wizard(existing_patients)
                    return
                elif len(existing_patients) == 1:
                    # Single client found - use it
                    patient = existing_patients[0]
                else:
                    # No client found - create new patient using the client_name (not lead name)
                    patient = self._get_or_create_patient(self.client_name)

            self.patient_id = patient.id

            # Create/find representative record
            representative = self._create_or_get_representative()

            # Create relationship (avoid duplicates)
            self._create_health_relationship(patient, representative)

            # Populate appropriate relationship field
            self._populate_relationship_field(representative)

    def _should_process_relationship(self):
        """Only create clients when the lead is effectively won/client acquired."""
        self.ensure_one()
        return self.contact_outcome == 'service_booked' or self.health_contact_outcome == 'service_booked' or (self.stage_id and self.stage_id.is_won)

    def _get_or_create_patient(self, patient_name=None, patient_vals=None, force_create=False):
        """Create or get patient record. Transfers unique_contact_code as patient_code only when contact IS the client.
        force_create=True skips the dedup lookups and always creates a fresh client."""
        patient_vals = patient_vals or {}
        if not patient_name:
            patient_name = self.name

        if not force_create:
            # Check if patient already exists by unique_contact_code first (if available)
            # Only do this lookup when the lead contact IS the client (not a representative)
            if self.unique_contact_code and self.contact_relationship_type == 'client':
                existing_patient = self.env['res.partner'].search([
                    ('patient_code', '=', self.unique_contact_code),
                    ('is_patient', '=', True)
                ], limit=1)
                if existing_patient:
                    return existing_patient

            # Check if patient already exists by name
            existing_patient = self.env['res.partner'].search([
                ('name', '=', patient_name),
                ('is_patient', '=', True)
            ], limit=1)

            if existing_patient:
                return existing_patient

        # Create new patient
        # Get Regular Patient category
        regular_category = self.env.ref('health_base.patient_category_regular', raise_if_not_found=False)

        # Determine whether to transfer lead's code or generate new one
        # Only transfer code when the lead contact IS the client (same person)
        # If contact is a representative (caregiver, family, etc.), patient should get its own code
        should_transfer_code = self.contact_relationship_type == 'client'
        
        create_vals = {
            'name': patient_name,
            'is_patient': True,
            'is_company': False,
            'customer_rank': 1,
            'catchment_province_id': self.catchment_province_id.id if self.catchment_province_id else False,
            'primary_facility_id': self.facility_id.id if self.facility_id else False,
            'active': True,
            'patient_status': 'active',
            'patient_category_id': regular_category.id if regular_category else False,
        }
        
        # Only transfer the lead's unique_contact_code when contact IS the client
        # When contact is a representative, let the patient generate its own code
        if should_transfer_code and self.unique_contact_code:
            create_vals['patient_code'] = self.unique_contact_code

        # Always copy the home-visit address — it represents the CLIENT's home
        # (captured on the contact for home visits), regardless of who the contact is.
        create_vals.update({
            'street': self.street,
            'city': self.city,
            'zip': self.zip,
            'country_id': self.country_id.id if self.country_id else False,
            'state_id': self.state_id.id if self.state_id else False,
            'province_code': self.province_code.code if self.province_code else False,
            'named_area': self.named_area,
            'apartment_number': self.apartment_number,
            'building_name': self.building_name,
            'house_number': self.house_number,
            'sub_alley_number': self.sub_alley_number,
            'alley_number': self.alley_number,
            'ward_commune': self.ward_commune,
            'district_id': self.district_id.id if self.district_id else False,
            # City = catchment province; carry it so the client's District domain
            # and the derived `city` string stay consistent.
            'catchment_province_id': self.catchment_province_id.id if self.catchment_province_id else False,
            # Note: vietnamese_address is computed automatically in res.partner
        })
        # Copy phone/email only when the contact IS the client (otherwise they
        # belong to the representative/payer, not the client).
        if self.contact_relationship_type == 'client':
            create_vals.update({
                'phone': self.phone,
                'email': self.email_from,
            })

        # Wizard-supplied values must be part of the initial create so
        # configurable required-field checks see them before blocking the save.
        # Accept any real res.partner field supplied by trusted server-side
        # callers so future field-requirement additions only need the wizard to
        # capture and pass the new field value.
        partner_fields = self.env['res.partner']._fields
        create_vals.update({
            key: value
            for key, value in patient_vals.items()
            if key in partner_fields and value
        })

        return self.env['res.partner'].create(create_vals)

    def _create_or_get_representative(self):
        """Create or reuse representative record from lead contact info"""
        rep_domain = [
            ('name', '=', self.name),
            ('is_representative', '=', True),
            ('is_company', '=', False),
        ]
        existing_rep = self.env['res.partner'].search(rep_domain, limit=1)
        if existing_rep:
            return existing_rep

        rep_vals = {
            'name': self.name,  # Contact name is the representative
            'is_representative': True,
            'is_company': False,
            'phone': self.phone,
            'email': self.email_from,
            'street': self.street,
            'city': self.city,
            'zip': self.zip,
            'country_id': self.country_id.id if self.country_id else False,
        }
        return self.env['res.partner'].create(rep_vals)

    def _create_health_relationship(self, patient, representative):
        """Create health.client.relation record"""
        # Map our relationship type to health.client.relation role
        role_mapping = {
            'caregiver': 'caregiver',
            'payer': 'payer', 
            'referrer': 'referrer',
            'emergency_contact': 'emergency_contact',
            'legal_guardian': 'legal_guardian',
            'healthcare_proxy': 'legal_guardian',       # Healthcare proxy → Legal Guardian (closest match)
            'client_representative': 'client_representative',
            'family_member': 'client_representative',   # Family member → Client Representative
            'friend': 'client_representative',           # Friend → Client Representative
            'professional': 'referrer',                  # Professional → Referrer
        }

        # Avoid duplicate relations for the same pair/role
        existing_relation = self.env['health.client.relation'].search([
            ('client_id', '=', patient.id),
            ('representative_id', '=', representative.id),
        ], limit=1)
        if existing_relation:
            return existing_relation

        # Map role and check for existing primary
        mapped_role = role_mapping.get(self.contact_relationship_type, 'client_representative')
        
        # Check if a primary already exists for this client+role
        existing_primary = self.env['health.client.relation'].search([
            ('client_id', '=', patient.id),
            ('role', '=', mapped_role),
            ('is_primary', '=', True),
            ('active', '=', True),
        ], limit=1)
        
        # Determine if this should be primary:
        # 1. If user explicitly marked as primary in initial contact, honor that
        # 2. If no existing primary exists, set as primary by default
        # 3. Otherwise, set as non-primary to avoid constraint error
        should_be_primary = self.is_primary_representative or not bool(existing_primary)
        
        relation_vals = {
            'client_id': patient.id,
            'representative_id': representative.id,
            'role': mapped_role,
            'is_primary': False,  # Create as non-primary first to avoid constraint
            'can_schedule_appointments': True,  # Default permission
            'can_receive_medical_info': self.contact_relationship_type in ['legal_guardian', 'healthcare_proxy', 'emergency_contact'],
        }

        relation = self.env['health.client.relation'].create(relation_vals)
        
        # If should be primary, use action_set_as_primary() to safely swap designation
        if should_be_primary:
            relation.action_set_as_primary()
        
        return relation

    def _populate_relationship_field(self, representative):
        """Populate the appropriate relationship field in the lead"""
        field_mapping = {
            'caregiver': 'primary_caregiver_id',
            'payer': 'primary_payer_id', 
            'referrer': 'referrer_id',
            'emergency_contact': 'emergency_contact_id',
            'client_representative': 'client_representative_id',
            'legal_guardian': 'primary_caregiver_id',  # Legal guardians are primary caregivers
            'healthcare_proxy': 'primary_caregiver_id',  # Healthcare proxies are primary caregivers
            'family_member': 'client_representative_id',  # Family members are client representatives
            'friend': 'client_representative_id',  # Friends are client representatives
            'professional': 'referrer_id',  # Professionals are referrers
        }
        
        field_name = field_mapping.get(self.contact_relationship_type)
        if field_name and hasattr(self, field_name):
            setattr(self, field_name, representative.id)

    def _show_client_selection_wizard(self, patients):
        """Show wizard to select from multiple patients with same name"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Select Client'),
            'res_model': 'health.client.selection.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_lead_id': self.id,
                'default_client_name': self.client_name,
                'default_patient_ids': [(6, 0, patients.ids)],
                'active_id': self.id,
            },
        }

    def action_convert_to_appointment(self):
        """Convert lead directly to healthcare appointment"""
        self.ensure_one()
        
        if not self.service_interest:
            raise UserError(_('Please specify the service interest before converting to appointment.'))
        
        # Create or get patient record
        patient = self._get_or_create_patient()
        
        # Create appointment
        appointment_vals = {
            'patient_id': patient.id,
            'lead_id': self.id,
            'appointment_type_id': self._get_appointment_type().id,
            'name': f"Appointment from Lead: {self.name}",
            'priority': self.clinical_priority,
            'notes': self.service_requirements or self.description,
        }
        
        appointment = self.env['health.appointment'].create(appointment_vals)
        
        # Update lead
        self.write({
            'patient_id': patient.id,
            'health_contact_outcome': 'service_booked',
            'contact_outcome': 'service_booked',
            'booking_status': 'confirmed',
            'stage_id': self._get_won_stage().id,
        })
        
        # Return action to open appointment
        return {
            'type': 'ir.actions.act_window',
            'name': _('Healthcare Appointment'),
            'res_model': 'health.appointment',
            'res_id': appointment.id,
            'view_mode': 'form',
            'target': 'current',
        }



    def _get_won_stage(self):
        """Get the 'won' stage for healthcare CRM"""
        stage_model = self.env['crm.stage']
        domain = [('is_won', '=', True)]
        if 'team_id' in stage_model._fields and self.team_id:
            domain = [
                ('is_won', '=', True),
                '|', ('team_id', '=', False), ('team_id', '=', self.team_id.id),
            ]
        won_stage = stage_model.search(domain, limit=1)
        
        if not won_stage:
            won_stage = self.env['crm.stage'].search([('is_won', '=', True)], limit=1)
        
        return won_stage

    def action_schedule_follow_up(self):
        """Schedule follow-up activity"""
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Schedule Follow-up'),
            'res_model': 'mail.activity',
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'new',
            'context': {
                'default_res_id': self.id,  # mail.activity still uses singular res_id
                'default_res_model': 'crm.lead',
                'default_summary': f'Follow-up on healthcare lead: {self.name}',
                'default_note': self.follow_up_notes,
                'default_date_deadline': self.next_follow_up_date or fields.Date.today(),
            }
        }

    def action_view_lead_activities(self):
        """Open a list view of activities for this lead in a modal.
        When the activity list is closed, returns to the Lead Info modal.
        """
        self.ensure_one()
        
        # Build the "return to Lead Info" action to use as close_action
        lead_info_view = self.env.ref('health_landing.view_lead_client_info_modal', raise_if_not_found=False)
        return_action = {
            'type': 'ir.actions.act_window',
            'name': _('%s - Lead Info') % self.name,
            'res_model': 'crm.lead',
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(lead_info_view.id if lead_info_view else False, 'form')],
            'target': 'new',
            'context': {'form_view_initial_mode': 'edit'},
        }
        
        # Get the ir.model record for crm.lead (needed for mail.activity creation)
        crm_lead_model = self.env['ir.model']._get('crm.lead')
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Activities for: %s') % self.name,
            'res_model': 'mail.activity',
            'view_mode': 'list,form',
            'target': 'new',
            'domain': [
                ('res_model', '=', 'crm.lead'),
                ('res_id', '=', self.id),
            ],
            'context': {
                'default_res_model_id': crm_lead_model.id,
                'default_res_model': 'crm.lead',
                'default_res_id': self.id,
            },
            'close_action': return_action,
        }

    def action_schedule_new_activity(self):
        """Open the activity scheduling wizard for this lead.
        Used as an alternative to the non-functional 'New' button
        in the mail.activity list view within modals.
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Schedule Activity for: %s') % self.name,
            'res_model': 'mail.activity.schedule',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_model': 'crm.lead',
                'active_id': self.id,
                'active_ids': [self.id],
                'default_res_model': 'crm.lead',
                'default_res_ids': [self.id],
                'dialog_size': 'medium',
            },
        }


    @api.depends('appointment_ids')
    def _compute_appointment_count(self):
        """Compute number of appointments from this lead"""
        for lead in self:
            lead.appointment_count = len(lead.appointment_ids)

    appointment_count = fields.Integer(
        'Appointment Count',
        compute='_compute_appointment_count',
        help='Number of appointments generated from this lead'
    )

    def action_convert_to_booking(self):
        """BOOKING button - Opens the OWL Quick Booking wizard for this contact.
        The wizard resolves the client: it dedups against existing clients
        (popup) or, if none, the client is auto-created when the booking is saved.
        Only passes a client up-front when one is already linked."""
        self.ensure_one()
        client = self._booking_client()
        ctx = {
            'default_lead_id': self.id,
            'active_center': 'crm_center',
        }
        if client:
            ctx['active_id'] = client.id
            ctx['default_patient_id'] = client.id
        return {
            'type': 'ir.actions.client',
            'tag': 'ops_quick_booking',
            'name': _('Quick Booking'),
            'target': 'current',
            'context': ctx,
        }

    def _booking_client(self):
        """The client (res.partner is_patient) already linked to this contact,
        via patient_id or a selected partner_id. Empty recordset if none."""
        self.ensure_one()
        if self.patient_id:
            return self.patient_id
        if self.partner_id and self.partner_id.is_patient:
            return self.partner_id
        return self.env['res.partner']

    def get_contact_booking_context(self):
        """Identity data the quick-booking wizard needs to resolve the client."""
        self.ensure_one()
        client = self._booking_client()
        addr_fields = ['house_number', 'alley_number', 'sub_alley_number', 'street',
                       'ward_commune', 'named_area', 'building_name', 'apartment_number',
                       'city', 'zip']
        address = {f: self[f] for f in addr_fields if self._fields.get(f) and self[f]}
        return {
            'lead_id': self.id,
            'client_name': self.client_name or self.name or '',
            'phone': self.phone or '',
            'email': self.email_from or '',
            'patient_id': client.id if client else False,
            'patient_name': client.name if client else '',
            'address': address,
        }

    @api.model
    def search_clients_for_contact(self, name=None, phone=None, email=None):
        """Return existing client (is_patient) cards matching name/phone/email,
        for the booking dedup popup."""
        leaves = []
        if name and len(name.strip()) >= 2:
            leaves.append(('name', 'ilike', name.strip()))
        if phone and len(str(phone).strip()) >= 4:
            leaves.append(('phone', 'ilike', str(phone).strip()))
            leaves.append(('mobile', 'ilike', str(phone).strip()))
        if email and '@' in (email or ''):
            leaves.append(('email', 'ilike', email.strip()))
        if not leaves:
            return []
        domain = ['&', ('is_patient', '=', True)] + ['|'] * (len(leaves) - 1) + leaves
        partners = self.env['res.partner'].search(domain, limit=15)
        return [{
            'id': p.id,
            'name': p.name or '',
            'patient_code': p.patient_code or '',
            'phone': p.phone or p.mobile or '',
            'email': p.email or '',
            'address': (p.vietnamese_address or '').strip() if hasattr(p, 'vietnamese_address') else '',
            'national_id': p.national_id or '' if hasattr(p, 'national_id') else '',
        } for p in partners]

    def _resolve_booking_client(self, force_new=False, address=None, facility_id=False):
        """Find-or-create the client for a booking made from this contact, set
        self.patient_id and return it. `address` (dict of Vietnamese fields) is
        the home-visit address captured in the wizard — applied to the lead so it
        seeds the client. `force_new` creates a fresh client (user chose 'create
        new' past the dedup) bypassing the name lookup. `facility_id` is the
        booking facility, used to seed the client's catchment province / facility
        when the contact itself has none (patients require a catchment province
        to generate a valid Patient ID)."""
        self.ensure_one()
        existing = self._booking_client()
        if existing:
            if not self.patient_id:
                self.patient_id = existing.id
            return existing
        if address:
            addr_fields = ['house_number', 'alley_number', 'sub_alley_number', 'street',
                           'ward_commune', 'named_area', 'building_name', 'apartment_number',
                           'district_id', 'catchment_province_id', 'city', 'zip']
            vals = {k: address.get(k) for k in addr_fields if address.get(k)}
            if vals:
                self.write(vals)
        # Patients require a catchment province; fall back to the booking
        # facility's province/facility when the contact doesn't have one.
        if facility_id and (not self.catchment_province_id or not self.facility_id):
            facility = self.env['health.facility'].browse(facility_id)
            if facility.exists():
                seed = {}
                if not self.catchment_province_id and facility.catchment_province_id:
                    seed['catchment_province_id'] = facility.catchment_province_id.id
                if not self.facility_id:
                    seed['facility_id'] = facility.id
                if seed:
                    self.write(seed)
        name = (self.client_name or self.name or '').strip()
        if not name:
            return self.env['res.partner']
        patient = self._get_or_create_patient(name, force_create=force_new)
        self.patient_id = patient.id
        return patient

    def action_convert_to_client(self):
        """Convert lead to client without creating a booking"""
        self.ensure_one()

        patient = self._get_or_create_patient()

        vals = {
            'patient_id': patient.id,
            'booking_status': 'no_booking',
            'stage_id': self._get_won_stage().id,
        }

        if not self.contact_outcome:
            vals['contact_outcome'] = 'pending_follow_up'
        if not self.health_contact_outcome:
            vals['health_contact_outcome'] = 'pending_follow_up'

        self.write(vals)

        action = self.env['ir.actions.act_window']._for_xml_id('health_crm.action_healthcare_opportunities')
        action['effect'] = {
            'fadeout': 'slow',
            'message': _('Congratulations! Client %s created.') % patient.name,
            'type': 'rainbow_man',
        }
        return action

    def action_booking_lost(self):
        """Open wizard to capture booking lost reason"""
        self.ensure_one()

        return {
            'name': _('Booking Lost Reason'),
            'type': 'ir.actions.act_window',
            'res_model': 'health.crm.booking.lost.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_lead_id': self.id,
            }
        }

    def action_merge_similar_leads(self):
        """Show similar/duplicate leads for merging"""
        self.ensure_one()

        # Build domain to find similar leads
        domain = [('id', '!=', self.id), ('type', '=', 'opportunity')]
        or_domains = []

        if self.email_from:
            or_domains.append([('email_from', '=ilike', self.email_from)])
        if self.phone:
            or_domains.append([('phone', '=', self.phone)])
        if self.name and len(self.name) > 3:
            or_domains.append([('name', '=ilike', self.name)])

        if or_domains:
            full_domain = domain + ['|'] * (len(or_domains) - 1) + [item for sublist in or_domains for item in sublist]
        else:
            full_domain = domain

        return {
            'name': _('Similar Leads - Select to Merge'),
            'type': 'ir.actions.act_window',
            'res_model': 'crm.lead',
            'view_mode': 'list,form',
            'domain': full_domain,
            'context': {
                'default_type': 'opportunity',
                'search_default_type': 'opportunity',
            },
            'help': '''<p class="o_view_nocontent_smiling_face">
                No similar leads found
            </p><p>
                Select multiple leads from the list and use the "Merge" action to combine them.
            </p>'''
        }

    # =========================================================================
    # CONTACT-FIRST FLOW ACTION METHODS
    # =========================================================================

    def action_mark_spam_and_home(self):
        """
        HOME button - Mark contact as spam/junk and return to dashboard.
        Called when user clicks Home without logging a Lead or Booking.
        Also marks the phone number as spam for future detection.
        """
        self.ensure_one()
        
        # Only mark as spam if no lead or booking was logged
        if self.contact_status == 'active':
            self.write({
                'contact_status': 'spam',
                'contact_outcome': 'rejected',
                'is_spam_caller': True,  # Tag this caller as spam
            })
            
            # Also mark other leads with same phone as potential spam
            if self.phone:
                other_leads = self.search([
                    ('phone', '=', self.phone),
                    ('id', '!=', self.id),
                    ('is_spam_caller', '=', False),
                ])
                if other_leads:
                    other_leads.write({'is_spam_caller': True})
        
        # Return to Health Flow dashboard
        return {
            'type': 'ir.actions.client',
            'tag': 'health_flow_dashboard',
        }

    def action_mark_spam(self):
        """Mark contact as spam — stays on the current view (no navigation)."""
        self.ensure_one()
        if self.contact_status != 'spam':
            self.write({
                'contact_status': 'spam',
                'contact_outcome': 'rejected',
                'is_spam_caller': True,
            })
            if self.phone:
                other_leads = self.search([
                    ('phone', '=', self.phone),
                    ('id', '!=', self.id),
                    ('is_spam_caller', '=', False),
                ])
                if other_leads:
                    other_leads.write({'is_spam_caller': True})
            self.env.cr.commit()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Marked as Spam'),
                'message': _('%s marked as spam.', self.name),
                'type': 'warning',
                'sticky': False,
                'next': {
                    'type': 'ir.actions.client',
                    'tag': 'soft_reload',
                },
            }
        }

    def action_log_as_lead(self):
        """Log Activity button — mark contact as Lead and open activity wizard."""
        self.ensure_one()
        self.write({
            'contact_status': 'lead',
            'contact_outcome': 'pending_follow_up',
            'health_contact_outcome': 'pending_follow_up',
        })
        self.invalidate_recordset(['contact_status', 'contact_outcome', 'health_contact_outcome'])
        self.env.cr.commit()

        return {
            'type': 'ir.actions.act_window',
            'name': _('Log Activity for: %s') % self.name,
            'res_model': 'mail.activity.schedule',
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'new',
            'context': {
                'active_model': 'crm.lead',
                'active_id': self.id,
                'active_ids': [self.id],
                'default_res_model': 'crm.lead',
                'default_res_ids': [self.id],
                'dialog_size': 'medium',
            },
        }

    def action_log_note(self):
        """
        LOG NOTE button - Add an internal note via chatter.
        Opens the message composer for internal notes.
        """
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Log Note'),
            'res_model': 'mail.compose.message',
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'new',
            'context': {
                'default_res_ids': [self.id],  # Odoo 19 uses res_ids (list)
                'default_model': 'crm.lead',
                'default_composition_mode': 'comment',
                'default_is_internal': True,
            }
        }

    def action_search_client_by_name(self):
        """
        Search for existing clients by the client_name field.
        Opens a popup with matching clients to select from.
        """
        self.ensure_one()
        
        search_term = self.client_name
        if not search_term or len(search_term) < 2:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Search'),
                    'message': _('Please enter at least 2 characters in Client Name to search.'),
                    'type': 'warning',
                    'sticky': False,
                }
            }
        
        # Search for clients (res.partner with is_patient=True)
        partners = self.env['res.partner'].search([
            ('is_patient', '=', True),
            '|', '|',
            ('name', 'ilike', search_term),
            ('phone', 'ilike', search_term),
            ('email', 'ilike', search_term),
        ], limit=15)
        
        if not partners:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No Clients Found'),
                    'message': _('No existing clients match "%s". You can continue with this name.') % search_term,
                    'type': 'info',
                    'sticky': False,
                }
            }
        
        # Create search wizard with results
        wizard = self.env['health.client.search.wizard'].create({
            'search_term': search_term,
            'source_lead_id': self.id,
        })
        
        # Add client lines
        for p in partners:
            self.env['health.client.search.line'].create({
                'wizard_id': wizard.id,
                'partner_id': p.id,
                'name': p.name,
                'phone': p.phone or '',
                'email': p.email or '',
                'code': p.patient_code or '',
            })
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Select Client'),
            'res_model': 'health.client.search.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {'form_view_initial_mode': 'edit'},
        }


    def action_refer_telemedicine(self):
        """
        TELEMEDICINE button - Refer contact to Duty Doctor for telemedicine consultation.
        Records the referral and notifies the duty doctor.
        """
        self.ensure_one()
        
        self.write({
            'referred_to_duty_doctor': True,
            'referral_datetime': fields.Datetime.now(),
        })
        
        # Create a note about the referral
        self.message_post(
            body=_('Contact referred for Telemedicine consultation to Duty Doctor.'),
            message_type='notification',
            subtype_xmlid='mail.mt_note',
        )
        
        # Open a form to add referral notes
        return {
            'type': 'ir.actions.act_window',
            'name': _('Telemedicine Referral Notes'),
            'res_model': 'crm.lead',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'focus_field': 'referral_notes',
            }
        }

    def action_escalate_consultation(self):
        """
        CONSULTATION button - Transfer contact for consultation.
        Options: Duty Doctor, Head Nurse, or Operations Manager.
        """
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Transfer for Consultation'),
            'res_model': 'health.escalation.wizard',
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'new',
            'context': {
                'default_lead_id': self.id,
                'default_escalation_type': 'consultation',
            }
        }

    def action_escalate_contact(self):
        """
        ESCALATE button - Escalate contact to Head Nurse or OM for further processing.
        Different from consultation - this transfers the entire contact.
        """
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Escalate Contact'),
            'res_model': 'health.escalation.wizard',
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'new',
            'context': {
                'default_lead_id': self.id,
                'default_escalation_type': 'transfer',
            }
        }

    def action_open_cancellation(self):
        """
        CANCELLATION button - Open cancellation form.
        Only available when contact_status is 'booking'.
        """
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Record Cancellation'),
            'res_model': 'health.booking.cancellation.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_lead_id': self.id,
            }
        }

    def action_reschedule_booking(self):
        """
        RESCHEDULE button - Open booking calendar for rescheduling.
        Only available when contact_status is 'booking'.
        """
        self.ensure_one()
        
        # Find related booking
        booking = self.env['health.fieldservice.order'].search([
            ('crm_lead_id', '=', self.id)
        ], limit=1)
        
        if booking:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Reschedule Booking'),
                'res_model': 'health.fieldservice.order',
                'res_id': booking.id,
                'view_mode': 'form',
                'target': 'current',
                'context': {
                    'reschedule_mode': True,
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No Booking Found'),
                    'message': _('No booking found for this contact.'),
                    'type': 'warning',
                    'sticky': False,
                }
            }

    def action_send_message(self):
        """
        SEND MESSAGE button - Open message composer.
        Allows sending email/SMS to the contact.
        """
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Send Message'),
            'res_model': 'mail.compose.message',
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'new',
            'context': {
                'default_res_ids': [self.id],  # Odoo 19 uses res_ids (list) instead of res_id
                'default_model': 'crm.lead',
                'default_composition_mode': 'comment',
                'default_partner_ids': [(4, self.partner_id.id)] if self.partner_id else [],
            }
        }

    def action_open_followup_wizard(self):
        """
        Open the Follow-up Activities wizard.
        Used for navigation back from activity view.
        """
        return {
            'type': 'ir.actions.act_window',
            'name': _('Follow-up Activities'),
            'res_model': 'health.followup.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'form_view_initial_mode': 'edit'},
        }

    def action_open_lead_hub(self):
        """
        Open hub-and-spoke dashboard for this lead.
        Used by Dashboard button in calendar popup.
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'health_landing_lead_hub',
            'name': f'Lead Hub: {self.name}',
            'params': {
                'lead_id': self.id,
                'lead_name': self.name,
            },
        }

    def action_open_client_dashboard(self):
        """
        Open the Client Dashboard (Patient Hub) for the client associated with this lead.
        If the lead has a partner_id (client was created from this lead), open that client's dashboard.
        """
        self.ensure_one()
        
        # Find the client/partner to display
        client = self.partner_id
        
        if not client:
            # No client found - show notification
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'No Client Associated',
                    'message': 'This lead does not have an associated client yet.',
                    'type': 'warning',
                    'sticky': False,
                }
            }
        
        # Open the Client Dashboard (Patient Hub) for this client
        # Pass source_lead_id so Back returns to the lead dashboard
        return {
            'type': 'ir.actions.client',
            'tag': 'health_landing_patient_hub',
            'name': f'Client Dashboard: {client.name}',
            'params': {
                'patient_id': client.id,
                'patient_name': client.name,
                'source_lead_id': self.id,
            },
        }

    def action_execute_activity(self):
        """
        Execute action based on the lead's current activity type.
        Used by Activity button in calendar popup.
        
        Actions:
        - Call: Opens Zalo call (tel: link with phone number)
        - Email: Opens email compose wizard
        - To-Do: Opens To-Do activity list
        - Meeting: Opens calendar view
        """
        self.ensure_one()
        
        # Get the next activity
        if not self.activity_ids:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No Activity'),
                    'message': _('This lead has no scheduled activities.'),
                    'type': 'info',
                    'sticky': False,
                }
            }
        
        # Get the nearest activity
        nearest_activity = self.activity_ids.sorted('date_deadline')[0]
        activity_type = nearest_activity.activity_type_id.name if nearest_activity.activity_type_id else ''
        
        if activity_type == 'Call':
            # Open Zalo call via phone number
            phone = self.phone or self.mobile
            if phone:
                # Return action that opens tel: link (Zalo will handle)
                return {
                    'type': 'ir.actions.act_url',
                    'url': f'tel:{phone}',
                    'target': 'new',
                }
            else:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('No Phone Number'),
                        'message': _('This lead has no phone number configured.'),
                        'type': 'warning',
                        'sticky': False,
                    }
                }
        
        elif activity_type == 'Email':
            # Open email compose wizard
            return {
                'type': 'ir.actions.act_window',
                'name': _('Compose Email'),
                'res_model': 'mail.compose.message',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_model': 'crm.lead',
                    'default_res_ids': [self.id],
                    'default_composition_mode': 'comment',
                    'default_partner_ids': [self.partner_id.id] if self.partner_id else [],
                    'default_email_to': self.email_from,
                },
            }
        
        elif activity_type == 'To-Do':
            # Open To-Do activity view (activity kanban)
            return {
                'type': 'ir.actions.act_window',
                'name': _('To-Do Activities'),
                'res_model': 'crm.lead',
                'view_mode': 'activity,list,form',
                'domain': [('id', '=', self.id)],
                'target': 'current',
            }
        
        elif activity_type == 'Meeting':
            # Open calendar view
            calendar_view = self.env.ref(
                'health_crm.view_crm_lead_followup_calendar',
                raise_if_not_found=False
            )
            return {
                'type': 'ir.actions.act_window',
                'name': _('Meeting Calendar'),
                'res_model': 'crm.lead',
                'view_mode': 'calendar,list,form',
                'domain': [('calendar_date', '!=', False)],
                'view_id': calendar_view.id if calendar_view else False,
                'target': 'current',
            }
        
        else:
            # Default: open lead form
            return {
                'type': 'ir.actions.act_window',
                'name': _('Lead'),
                'res_model': 'crm.lead',
                'view_mode': 'form',
                'res_id': self.id,
                'target': 'current',
            }

    def action_schedule_activity_wizard(self):
        """
        Open the activity scheduling wizard for this lead.
        Used by the Activity button in the Recent Client Follow-up list.
        """
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': _('Schedule Activity for: %s') % self.name,
            'res_model': 'mail.activity.schedule',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_model': 'crm.lead',
                'active_id': self.id,
                'active_ids': [self.id],
                'default_res_model': 'crm.lead',
                'default_res_ids': [self.id],
                'dialog_size': 'medium',
            },
        }

    # =========================================================================
    # CRM CENTER — CONTACT TIMELINE
    # =========================================================================

    def get_contact_timeline(self):
        """Return a unified, sorted list of historical events for this contact."""
        self.ensure_one()
        events = []

        if self.create_date:
            channel = ''
            if self.mode_of_contact:
                channel = dict(
                    self._fields['mode_of_contact']._description_selection(self.env)
                ).get(self.mode_of_contact, '')
            events.append({
                'type': 'created',
                'date': self.create_date.strftime('%Y-%m-%d %H:%M:%S'),
                'title': _('Contact Created'),
                'detail': _(channel) if channel else _('New Contact'),
                'icon': 'fa-plus-circle',
            })

        status_field = self.env['ir.model.fields']._get('crm.lead', 'contact_status')
        if status_field:
            trackings = self.env['mail.tracking.value'].search([
                ('field_id', '=', status_field.id),
                ('mail_message_id.model', '=', 'crm.lead'),
                ('mail_message_id.res_id', '=', self.id),
            ], order='create_date asc')
            for tv in trackings:
                old_val = _(tv.old_value_char) if tv.old_value_char else ''
                new_val = _(tv.new_value_char) if tv.new_value_char else ''
                events.append({
                    'type': 'status',
                    'date': tv.create_date.strftime('%Y-%m-%d %H:%M:%S'),
                    'title': new_val or _('Status Change'),
                    'detail': '%s → %s' % (old_val, new_val) if old_val else new_val,
                    'icon': 'fa-exchange',
                })

        if self.escalation_datetime:
            target = ''
            if self.escalated_to:
                target = dict(
                    self._fields['escalated_to']._description_selection(self.env)
                ).get(self.escalated_to, '')
            events.append({
                'type': 'escalation',
                'date': self.escalation_datetime.strftime('%Y-%m-%d %H:%M:%S'),
                'title': _('Escalated'),
                'detail': _('To %s', _(target)) if target else _('Escalated'),
                'icon': 'fa-arrow-up',
            })

        if self.referral_datetime and self.referred_to_duty_doctor:
            events.append({
                'type': 'escalation',
                'date': self.referral_datetime.strftime('%Y-%m-%d %H:%M:%S'),
                'title': _('Referred'),
                'detail': _('To Duty Doctor'),
                'icon': 'fa-user-md',
            })

        activities = self.env['mail.activity'].search([
            ('res_model', '=', 'crm.lead'),
            ('res_id', '=', self.id),
        ], order='date_deadline asc')
        for act in activities:
            act_type_name = act.activity_type_id.name if act.activity_type_id else _('Activity')
            icon_map = {'Call': 'fa-phone', 'Email': 'fa-envelope', 'Meeting': 'fa-users', 'To-Do': 'fa-check-square'}
            events.append({
                'type': 'activity',
                'date': act.date_deadline.strftime('%Y-%m-%d 00:00:00') if act.date_deadline else '',
                'title': act_type_name,
                'detail': act.summary or act.note or '',
                'icon': icon_map.get(act_type_name, 'fa-clock-o'),
                'done': False,
            })

        done_msgs = self.env['mail.message'].search([
            ('model', '=', 'crm.lead'),
            ('res_id', '=', self.id),
            ('subtype_id.name', 'ilike', 'Activity Done'),
        ], order='date asc')
        for msg in done_msgs:
            events.append({
                'type': 'activity',
                'date': msg.date.strftime('%Y-%m-%d %H:%M:%S') if msg.date else '',
                'title': _('Activity Done'),
                'detail': msg.body and msg.body[:80] or '',
                'icon': 'fa-check',
                'done': True,
            })

        fso_domain = [('state', 'not in', ['cancelled'])]
        if self.patient_id:
            fso_domain.append(('patient_id', '=', self.patient_id.id))
        elif hasattr(self, 'crm_lead_id'):
            fso_domain.append(('crm_lead_id', '=', self.id))
        else:
            fso_domain = [('id', '=', 0)]

        bookings = self.env['health.fieldservice.order'].search(fso_domain, order='create_date asc')
        booking_model = self.env['health.fieldservice.order']
        state_labels = dict(
            booking_model._fields['state']._description_selection(self.env)
        )
        service_type_labels = dict(
            booking_model._fields['service_type']._description_selection(self.env)
        )
        for bk in bookings:
            stype = ''
            if bk.service_type:
                stype = service_type_labels.get(bk.service_type, '')
            events.append({
                'type': 'booking',
                'date': bk.create_date.strftime('%Y-%m-%d %H:%M:%S') if bk.create_date else '',
                'title': bk.name or _('Booking'),
                'detail': '%s — %s' % (
                    _(stype),
                    _(state_labels.get(bk.state, bk.state or '')),
                ) if stype else _(state_labels.get(bk.state, '')),
                'icon': 'fa-calendar',
                'booking_id': bk.id,
            })

        events.sort(key=lambda e: e.get('date', ''))
        return events

    # =========================================================================
    # CRM CENTER — CONTACT HEADER
    # =========================================================================

    def get_contact_header_data(self, lead_id=None):
        if lead_id:
            lead = self.env['crm.lead'].browse(lead_id)
        else:
            lead = self
        lead.ensure_one()

        name = lead.name or ''
        initials = ''.join(
            p[0] for p in name.split() if p
        )[:2].upper() or '??'

        channel = ''
        if lead.mode_of_contact:
            channel = dict(
                self._fields['mode_of_contact']._description_selection(self.env)
            ).get(lead.mode_of_contact, '')

        return {
            'id': lead.id,
            'name': name,
            'initials': initials,
            'code': lead.unique_contact_code or '',
            'phone': lead.phone or '',
            'email': lead.email_from or '',
            'contact_status': lead.contact_status or 'active',
            'channel': _(channel) if channel else '',
            'province': lead.catchment_province_id.name if lead.catchment_province_id else '',
        }

    # =========================================================================
    # CRM CENTER DASHBOARD
    # =========================================================================

    @api.model
    def get_crm_dashboard_data(self, period='month', date_from=None, date_to=None):
        from datetime import datetime as dt, timedelta, time as dt_time

        today = fields.Date.context_today(self)
        now = fields.Datetime.now()
        Lead = self.env['crm.lead']

        week_start = today - timedelta(days=today.weekday())
        month_start = today.replace(day=1)

        # Parse custom From/To (YYYY-MM-DD) when provided
        custom_from = custom_to = None
        if period == 'custom':
            try:
                custom_from = dt.strptime(date_from, '%Y-%m-%d').date() if date_from else None
                custom_to = dt.strptime(date_to, '%Y-%m-%d').date() if date_to else None
            except (ValueError, TypeError):
                custom_from = custom_to = None

        # Nominal period_start (used for trend comparison windows)
        if period == 'today':
            period_start = today
        elif period == 'week':
            period_start = week_start
        elif period == 'custom' and custom_from:
            period_start = custom_from
        else:  # 'month' and 'all'
            period_start = month_start

        period_start_dt = fields.Datetime.to_string(dt.combine(period_start, dt_time.min))
        today_start_dt = fields.Datetime.to_string(dt.combine(today, dt_time.min))
        tomorrow_start_dt = fields.Datetime.to_string(dt.combine(today + timedelta(days=1), dt_time.min))
        week_start_dt = fields.Datetime.to_string(dt.combine(week_start, dt_time.min))

        # Reusable create_date clause applied to period-scoped aggregates.
        # 'all' => no date bound; 'custom' => between From/To; else >= period start.
        if period == 'all':
            period_clause = []
        elif period == 'custom':
            period_clause = []
            if custom_from:
                period_clause.append(('create_date', '>=',
                    fields.Datetime.to_string(dt.combine(custom_from, dt_time.min))))
            if custom_to:
                period_clause.append(('create_date', '<',
                    fields.Datetime.to_string(dt.combine(custom_to + timedelta(days=1), dt_time.min))))
        else:
            period_clause = [('create_date', '>=', period_start_dt)]

        # --- KPIs ---
        contacts_today = Lead.search_count([('create_date', '>=', today_start_dt)])
        # Pending follow-ups = actions required for the current day: a follow-up
        # is scheduled on or before end-of-today (today + not-yet-actioned overdue).
        pending_followups = Lead.search_count([
            ('contact_status', '=', 'lead'),
            ('next_follow_up_date', '!=', False),
            ('next_follow_up_date', '<', tomorrow_start_dt),
        ])
        active_leads = Lead.search_count([('contact_status', '=', 'lead')])
        bookings_this_week = Lead.search_count([
            ('contact_status', '=', 'booking'),
            ('create_date', '>=', week_start_dt),
        ])

        period_total = Lead.search_count(period_clause)
        period_bookings = Lead.search_count(
            [('contact_status', '=', 'booking')] + period_clause)
        period_spam = Lead.search_count(
            [('contact_status', '=', 'spam')] + period_clause)
        conversion_rate = (period_bookings / period_total * 100) if period_total else 0
        spam_rate = (period_spam / period_total * 100) if period_total else 0

        kpis = {
            'contacts_today': contacts_today,
            'pending_followups': pending_followups,
            'active_leads': active_leads,
            'bookings_this_week': bookings_this_week,
            'conversion_rate': round(conversion_rate, 1),
            'spam_rate': round(spam_rate, 1),
        }

        # --- Trends (vs previous equivalent period) ---
        period_days = (today - period_start).days + 1
        prev_end = period_start - timedelta(days=1)
        prev_start = prev_end - timedelta(days=period_days - 1)
        prev_start_dt = fields.Datetime.to_string(dt.combine(prev_start, dt_time.min))
        prev_end_dt = fields.Datetime.to_string(dt.combine(prev_end + timedelta(days=1), dt_time.min))

        prev_contacts = Lead.search_count([
            ('create_date', '>=', prev_start_dt), ('create_date', '<', prev_end_dt),
        ])
        prev_leads = Lead.search_count([
            ('contact_status', '=', 'lead'),
            ('create_date', '>=', prev_start_dt), ('create_date', '<', prev_end_dt),
        ])
        prev_bookings = Lead.search_count([
            ('contact_status', '=', 'booking'),
            ('create_date', '>=', prev_start_dt), ('create_date', '<', prev_end_dt),
        ])

        def trend_pct(current, previous):
            if not previous:
                return 100.0 if current else 0.0
            return round((current - previous) / previous * 100, 1)

        if period in ('all', 'custom'):
            # No meaningful prior window to compare against
            trends = {k: 0 for k in kpis}
        else:
            trends = {
                'contacts_today': trend_pct(contacts_today, prev_contacts // max(period_days, 1)),
                'pending_followups': 0,
                'active_leads': trend_pct(active_leads, prev_leads),
                'bookings_this_week': trend_pct(bookings_this_week, prev_bookings),
                'conversion_rate': 0,
                'spam_rate': 0,
            }

        # --- Sparklines (last 7 days) ---
        sparklines = {k: [] for k in kpis}
        for i in range(6, -1, -1):
            d = today - timedelta(days=i)
            d_start = fields.Datetime.to_string(dt.combine(d, dt_time.min))
            d_end = fields.Datetime.to_string(dt.combine(d + timedelta(days=1), dt_time.min))
            day_domain = [('create_date', '>=', d_start), ('create_date', '<', d_end)]

            day_total = Lead.search_count(day_domain)
            sparklines['contacts_today'].append(day_total)
            sparklines['pending_followups'].append(Lead.search_count(
                day_domain + [('contact_status', '=', 'lead')]
            ))
            sparklines['active_leads'].append(Lead.search_count(
                day_domain + [('contact_status', '=', 'lead')]
            ))
            sparklines['bookings_this_week'].append(Lead.search_count(
                day_domain + [('contact_status', '=', 'booking')]
            ))
            day_bookings = Lead.search_count(day_domain + [('contact_status', '=', 'booking')])
            sparklines['conversion_rate'].append(
                round(day_bookings / day_total * 100, 1) if day_total else 0
            )
            day_spam = Lead.search_count(day_domain + [('contact_status', '=', 'spam')])
            sparklines['spam_rate'].append(
                round(day_spam / day_total * 100, 1) if day_total else 0
            )

        # --- Status breakdown ---
        status_breakdown = []
        status_selections = self._fields['contact_status']._description_selection(self.env)
        for status_val, _label in status_selections:
            count = Lead.search_count(
                [('contact_status', '=', status_val)] + period_clause)
            status_breakdown.append({
                'status': status_val,
                'label': _(_label),
                'count': count,
                'percent': round(count / period_total * 100, 1) if period_total else 0,
            })

        # --- Channel breakdown ---
        channel_breakdown = []
        channel_selections = self._fields['vietnamese_channel']._description_selection(self.env)
        for ch_val, ch_label in channel_selections:
            count = Lead.search_count(
                [('vietnamese_channel', '=', ch_val)] + period_clause)
            if count > 0:
                channel_breakdown.append({
                    'channel': ch_val,
                    'label': _(ch_label),
                    'count': count,
                })
        channel_breakdown.sort(key=lambda x: x['count'], reverse=True)

        # --- Recent contacts ---
        recent = Lead.search([], order='create_date desc', limit=5)
        recent_contacts = []
        for lead in recent:
            time_diff = now - lead.create_date
            if time_diff.days > 0:
                time_ago = _("%s days ago", time_diff.days)
            else:
                hours = time_diff.seconds // 3600
                if hours > 0:
                    time_ago = _("%s hours ago", hours)
                else:
                    mins = time_diff.seconds // 60
                    time_ago = _("%s minutes ago", max(mins, 1))

            recent_contacts.append({
                'id': lead.id,
                'name': lead.name or '',
                'code': lead.unique_contact_code or '',
                'phone': lead.phone or '',
                'contact_status': lead.contact_status or 'active',
                'province': lead.catchment_province_id.name if lead.catchment_province_id else '',
                'channel': _(
                    dict(channel_selections).get(lead.vietnamese_channel, '')
                ) if lead.vietnamese_channel else '',
                'time_ago': time_ago,
            })

        # --- Upcoming bookings ---
        upcoming = Lead.search([
            ('contact_status', '=', 'booking'),
        ], order='create_date desc', limit=5)
        FSO = self.env['health.fieldservice.order']
        upcoming_bookings = []
        for lead in upcoming:
            time_diff = now - lead.create_date
            if time_diff.days > 0:
                time_ago = _("%s days ago", time_diff.days)
            else:
                hours = time_diff.seconds // 3600
                if hours > 0:
                    time_ago = _("%s hours ago", hours)
                else:
                    mins = time_diff.seconds // 60
                    time_ago = _("%s minutes ago", max(mins, 1))

            # Linked booking record + its scheduled appointment date
            booking = FSO.search(
                [('crm_lead_id', '=', lead.id)],
                order='scheduled_datetime desc', limit=1,
            )
            scheduled = ''
            if booking and booking.scheduled_datetime:
                scheduled = fields.Datetime.context_timestamp(
                    self, booking.scheduled_datetime).strftime('%b %d, %I:%M %p')

            upcoming_bookings.append({
                'id': lead.id,
                'name': lead.name or '',
                'code': lead.unique_contact_code or '',
                'contact_status': 'booking',
                'province': lead.catchment_province_id.name if lead.catchment_province_id else '',
                'channel': _(
                    dict(channel_selections).get(lead.vietnamese_channel, '')
                ) if lead.vietnamese_channel else '',
                'time_ago': time_ago,
                'booking_id': booking.id if booking else False,
                'scheduled': scheduled,
            })

        # --- Monthly summary (always current month regardless of period) ---
        month_start_dt_str = fields.Datetime.to_string(dt.combine(month_start, dt_time.min))
        monthly_summary = {
            'new_contacts': Lead.search_count([('create_date', '>=', month_start_dt_str)]),
            'converted': Lead.search_count([
                ('contact_status', '=', 'booking'),
                ('create_date', '>=', month_start_dt_str),
            ]),
            'lost': Lead.search_count([
                ('contact_status', '=', 'lost_booking'),
                ('create_date', '>=', month_start_dt_str),
            ]),
            'active_pipeline': active_leads,
        }

        return {
            'kpis': kpis,
            'trends': trends,
            'sparklines': sparklines,
            'status_breakdown': status_breakdown,
            'channel_breakdown': channel_breakdown,
            'recent_contacts': recent_contacts,
            'upcoming_bookings': upcoming_bookings,
            'monthly_summary': monthly_summary,
        }

    @api.model
    def action_create_from_crm_wizard(self, vals):
        lead_vals = {
            'name': vals.get('name', ''),
            'phone': vals.get('phone') or False,
            'email_from': vals.get('email_from') or False,
            'mode_of_contact': vals.get('mode_of_contact') or False,
            'catchment_province_id': vals.get('catchment_province_id') or False,
            'contact_relationship_type': vals.get('contact_relationship_type') or False,
            'client_name': vals.get('client_name') or False,
            'service_interest': vals.get('service_interest') or False,
            'clinical_priority': vals.get('clinical_priority', 'routine'),
            'reason_for_contact_id': vals.get('reason_for_contact_id') or False,
            'contact_status': 'active',
            'type': 'opportunity',
        }
        # Home-visit address captured in the wizard (Vietnamese fields)
        for f in ('house_number', 'alley_number', 'sub_alley_number', 'street',
                  'ward_commune', 'named_area', 'building_name', 'apartment_number',
                  'city', 'zip'):
            if vals.get(f):
                lead_vals[f] = vals[f]
        if vals.get('contact_datetime'):
            lead_vals['contact_datetime'] = vals['contact_datetime']
        else:
            lead_vals['contact_datetime'] = fields.Datetime.now()

        selected_client_id = vals.get('selected_client_id')
        if selected_client_id:
            lead_vals['partner_id'] = selected_client_id

        lead = self.create(lead_vals)

        zalo_number = vals.get('zalo_number')
        if zalo_number and lead.partner_id and hasattr(lead.partner_id, 'zalo_user_id'):
            if not lead.partner_id.zalo_user_id:
                lead.partner_id.zalo_user_id = zalo_number

        return {
            'res_id': lead.id,
            'res_model': 'crm.lead',
            'name': lead.name,
            'code': lead.unique_contact_code or '',
        }

    # =========================================================================
    # NEW CONTACT WIZARD — RPC METHODS
    # =========================================================================

    @api.model
    def check_contact_duplicates(self, vals):
        """Check for duplicate contacts by phone and/or email across leads and partners.
        Also checks for known spam callers."""
        import re
        phone = vals.get('phone', '')
        email = vals.get('email', '')

        phone_normalized = re.sub(r'[^\d]', '', phone) if phone else ''

        lead_matches = []
        partner_matches = []
        is_spam = False
        spam_lead_name = False

        # Search crm.lead by phone OR email
        lead_domain = []
        if phone_normalized:
            lead_domain.append(('phone', 'ilike', phone_normalized[-9:]))
        if email:
            if lead_domain:
                lead_domain = ['|'] + lead_domain + [('email_from', '=ilike', email)]
            else:
                lead_domain = [('email_from', '=ilike', email)]

        if lead_domain:
            leads = self.search(lead_domain, limit=10)
            for lead in leads:
                lead_matches.append({
                    'id': lead.id,
                    'name': lead.name,
                    'code': lead.unique_contact_code or '',
                    'phone': lead.phone or '',
                    'email': lead.email_from or '',
                    'status': lead.contact_status or '',
                })

        # Search res.partner by phone OR email
        partner_domain = []
        if phone_normalized:
            partner_domain.append(('phone', 'ilike', phone_normalized[-9:]))
        if email:
            if partner_domain:
                partner_domain = ['|'] + partner_domain + [('email', '=ilike', email)]
            else:
                partner_domain = [('email', '=ilike', email)]

        if partner_domain:
            partners = self.env['res.partner'].search(partner_domain, limit=10)
            for p in partners:
                partner_matches.append({
                    'id': p.id,
                    'name': p.name,
                    'code': p.patient_code or '',
                    'phone': p.phone or '',
                    'email': p.email or '',
                    'patient_status': p.patient_status if hasattr(p, 'patient_status') else '',
                })

        # Spam check
        if phone_normalized:
            spam_lead = self.search([
                ('phone', 'ilike', phone_normalized[-9:]),
                ('contact_status', '=', 'spam'),
            ], limit=1)
            if spam_lead:
                is_spam = True
                spam_lead_name = spam_lead.name

        return {
            'lead_matches': lead_matches,
            'partner_matches': partner_matches,
            'is_spam': is_spam,
            'spam_lead_name': spam_lead_name,
        }

    @api.model
    def search_contacts_for_wizard(self, search_term):
        """Search contacts, leads, and clients by name with bidirectional associations."""
        if not search_term or len(search_term) < 2:
            return {'contacts': [], 'leads': [], 'clients': []}

        # Step 1: Search clients (res.partner with is_patient=True)
        matching_partners = self.env['res.partner'].search([
            ('is_patient', '=', True),
            '|', '|',
            ('name', 'ilike', search_term),
            ('phone', 'ilike', search_term),
            ('email', 'ilike', search_term),
        ], limit=15)

        all_client_ids = set(matching_partners.ids)

        # Step 2: Search leads
        matching_leads = self.search([
            '|', '|',
            ('name', 'ilike', search_term),
            ('phone', 'ilike', search_term),
            ('email_from', 'ilike', search_term),
        ], limit=30)

        directly_matching_lead_ids = set(matching_leads.ids)
        associated_lead_ids = set()

        # Step 3: Find associated leads for matching clients
        if matching_partners:
            assoc_leads = self.search([
                ('patient_id', 'in', matching_partners.ids),
            ], limit=30)
            associated_lead_ids.update(assoc_leads.ids)

        all_lead_ids = directly_matching_lead_ids | associated_lead_ids

        # Step 4: Find associated clients for matching leads
        for lead in matching_leads:
            if lead.patient_id and lead.patient_id.id not in all_client_ids:
                all_client_ids.add(lead.patient_id.id)

        # Step 5: Build clients list
        all_partners = self.env['res.partner'].browse(list(all_client_ids))
        clients_list = []
        for p in all_partners:
            assoc_leads_for_client = self.search([
                ('patient_id', '=', p.id)
            ], limit=5)
            clients_list.append({
                'id': p.id,
                'name': p.name,
                'phone': p.phone or '',
                'email': p.email or '',
                'code': p.patient_code or '',
                'associated_lead_count': len(assoc_leads_for_client),
                'associated_leads': [
                    {'id': l.id, 'name': l.name, 'code': l.unique_contact_code or ''}
                    for l in assoc_leads_for_client
                ],
            })

        # Step 6: Build leads/contacts lists
        all_leads = self.browse(list(all_lead_ids))
        contacts_list = []
        leads_list = []

        for lead in all_leads:
            associated_client = None
            if lead.patient_id:
                associated_client = {
                    'id': lead.patient_id.id,
                    'name': lead.patient_id.name,
                    'code': lead.patient_id.patient_code or '',
                    'phone': lead.patient_id.phone or lead.patient_id.mobile or '',
                }

            record = {
                'id': lead.id,
                'name': lead.name,
                'phone': lead.phone or '',
                'email': lead.email_from or '',
                'code': lead.unique_contact_code or '',
                'status': lead.contact_status,
                'associated_client': associated_client,
                'relationship_type': lead.contact_relationship_type or '',
                'client_name': lead.client_name or '',
            }

            if lead.id in associated_lead_ids:
                leads_list.append(record)
            elif lead.contact_status == 'lead':
                leads_list.append(record)
            elif lead.contact_status in ['active', False, '']:
                contacts_list.append(record)

        return {
            'contacts': contacts_list[:10],
            'leads': leads_list[:10],
            'clients': clients_list,
        }

    @api.model
    def search_clients_for_wizard(self, search_term):
        """Search for existing clients (res.partner with is_patient=True) by name/phone/email."""
        if not search_term or len(search_term) < 2:
            return []

        partners = self.env['res.partner'].search([
            ('is_patient', '=', True),
            '|', '|',
            ('name', 'ilike', search_term),
            ('phone', 'ilike', search_term),
            ('email', 'ilike', search_term),
        ], limit=15)

        return [{
            'id': p.id,
            'name': p.name,
            'phone': p.phone or '',
            'email': p.email or '',
            'code': p.patient_code or '',
        } for p in partners]

    @api.model
    def action_create_spam_from_wizard(self, vals):
        """Create a lead marked as spam/junk from the new contact wizard."""
        lead_vals = {
            'name': vals.get('name', 'Unknown'),
            'phone': vals.get('phone') or False,
            'email_from': vals.get('email_from') or False,
            'catchment_province_id': vals.get('catchment_province_id') or False,
            'mode_of_contact': vals.get('mode_of_contact') or False,
            'contact_datetime': fields.Datetime.now(),
            'contact_status': 'spam',
            'contact_outcome': 'rejected',
            'type': 'opportunity',
        }
        self.create(lead_vals)
        return True

    def action_mark_contact_spam(self):
        """Mark this contact as spam."""
        self.ensure_one()
        self.write({
            'contact_status': 'spam',
            'contact_outcome': 'rejected',
        })
        return True

    def wizard_log_activity(self, activity_type_id, summary, date_deadline):
        """Create a mail.activity on this lead from the wizard inline panel."""
        self.ensure_one()
        vals = {
            'res_id': self.id,
            'res_model_id': self.env['ir.model']._get('crm.lead').id,
            'summary': summary or _('Follow-up'),
            'date_deadline': date_deadline or fields.Date.today(),
            'user_id': self.env.uid,
        }
        if activity_type_id:
            vals['activity_type_id'] = activity_type_id
        else:
            todo_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
            if todo_type:
                vals['activity_type_id'] = todo_type.id
        self.env['mail.activity'].create(vals)
        return True

    def wizard_post_note(self, note_body):
        """Post an internal note on this lead from the wizard inline panel."""
        self.ensure_one()
        self.message_post(
            body=note_body,
            message_type='comment',
            subtype_xmlid='mail.mt_note',
        )
        return True
