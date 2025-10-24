# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


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
    health_contact_outcome = fields.Selection([
        ('service_booked', 'Service Booked'),
        ('pending_follow_up', 'Pending Follow-up'),
        ('rejected', 'Rejected'),
        ('no_response', 'No Response'),
        ('not_qualified', 'Not Qualified'),
        ('future_opportunity', 'Future Opportunity'),
    ], string='Healthcare Outcome', help='Outcome of healthcare contact')

    # Clinical priority classification
    clinical_priority = fields.Selection([
        ('routine', 'Routine'),
        ('urgent', 'Urgent'),
        ('emergency', 'Emergency'),
        ('preventive', 'Preventive'),
    ], string='Clinical Priority', default='routine',
       help='Clinical urgency classification')

    # Vietnamese healthcare channels (extends standard utm_source)
    vietnamese_channel = fields.Selection([
        ('zalo', 'Zalo'),
        ('facebook', 'Facebook'),
        ('linkedin', 'LinkedIn'),
        ('website', 'Website'),
        ('phone', 'Phone Call'),
        ('referral', 'Referral'),
        ('walk_in', 'Walk-in'),
        ('advertisement', 'Advertisement'),
        ('word_of_mouth', 'Word of Mouth'),
    ], string='Vietnamese Channel', help='Specific Vietnamese contact channel')

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
    
    contact_outcome = fields.Selection([
        ('service_booked', 'Service Booked'),
        ('pending_follow_up', 'Pending Follow-up'), 
        ('rejected', 'Rejected'),
        ('no_response', 'No Response'),
        ('booking_lost', 'Booking Lost')
    ], string='Contact Outcome', help='From Excel: Contact Outcome field')
    
    booking_status = fields.Selection([
        ('no_booking', 'No Booking'),
        ('pending', 'Booking Pending'),
        ('confirmed', 'Booking Confirmed'),
        ('completed', 'Booking Completed'),
        ('cancelled', 'Booking Cancelled')
    ], string='Booking Status', help='From Excel: Booking Status [Compulsory]', default='no_booking')
    
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
    
    # Secondary caregiver (Caregiver 2 ID)
    secondary_caregiver_id = fields.Many2one(
        'res.partner',
        string='Secondary Caregiver',
        domain=[('is_caregiver', '=', True)],
        help='Secondary caregiver for this lead (Caregiver 2 ID)'
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

    @api.constrains('contact_relationship_type', 'client_name')
    def _check_client_name_required(self):
        """Validate that client_name is provided when contact is not the client"""
        for record in self:
            if record.contact_relationship_type != 'client' and not record.client_name:
                raise ValidationError(_(
                    'Client Name is required when you are not the client yourself. '
                    'Please provide the name of the actual client/patient.'
                ))

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

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to set healthcare-specific defaults"""
        # Handle both single dict and list of dicts
        if not isinstance(vals_list, list):
            vals_list = [vals_list]
            
        for vals in vals_list:
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
        
        # Create records and handle relationships
        records = super().create(vals_list)
        
        # Process relationship logic for each record
        for record in records:
            record._process_contact_relationship()
        
        return records
    
    def write(self, vals):
        """Override write to handle relationship changes"""
        result = super().write(vals)
        
        # If relationship fields were changed, reprocess relationships
        if any(field in vals for field in ['contact_relationship_type', 'client_name', 'name']):
            for record in self:
                record._process_contact_relationship()
        
        return result
    
    def _generate_unique_contact_code(self, vals):
        """Generate unique contact code based on city"""
        # Get city from vals or use default
        city = vals.get('city', 'HCM')  # Default to Ho Chi Minh City
        
        # Get the last contact code for this city
        last_lead = self.search([
            ('city', '=', city),
            ('unique_contact_code', '!=', False)
        ], order='unique_contact_code desc', limit=1)
        
        if last_lead and last_lead.unique_contact_code:
            # Extract number from last code (format: CITY-NNNN)
            try:
                last_number = int(last_lead.unique_contact_code.split('-')[-1])
                new_number = last_number + 1
            except (ValueError, IndexError):
                new_number = 1
        else:
            new_number = 1
        
        # Generate code in format: CITY-NNNN
        city_code = city[:3].upper() if city else 'HCM'
        return f"{city_code}-{new_number:04d}"

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
                # No client found - create new patient
                patient = self._get_or_create_patient(self.client_name)
            
            self.patient_id = patient.id
            
            # Create representative record
            representative = self._create_representative()
            
            # Create relationship
            self._create_health_relationship(patient, representative)
            
            # Populate appropriate relationship field
            self._populate_relationship_field(representative)

    def _get_or_create_patient(self, patient_name=None):
        """Create or get patient record"""
        if not patient_name:
            patient_name = self.name
            
        # Check if patient already exists
        existing_patient = self.env['res.partner'].search([
            ('name', '=', patient_name),
            ('is_patient', '=', True)
        ], limit=1)
        
        if existing_patient:
            return existing_patient
        
        # Create new patient
        patient_vals = {
            'name': patient_name,
            'is_patient': True,
            'is_company': False,
            'customer_rank': 1,
        }
        
        # Copy contact info from lead if contact is the client
        if self.contact_relationship_type == 'client':
            patient_vals.update({
                'phone': self.phone,
                'mobile': self.mobile,
                'email': self.email_from,
                'street': self.street,
                'city': self.city,
                'zip': self.zip,
                'country_id': self.country_id.id if self.country_id else False,
            })
        
        return self.env['res.partner'].create(patient_vals)

    def _create_representative(self):
        """Create representative record from lead contact info"""
        rep_vals = {
            'name': self.name,  # Contact name is the representative
            'is_representative': True,
            'is_company': False,
            'phone': self.phone,
            'mobile': self.mobile,
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
            'healthcare_proxy': 'healthcare_proxy',
            'client_representative': 'client_representative',
            'family_member': 'family_member',
            'friend': 'friend',
            'professional': 'professional',
        }
        
        relation_vals = {
            'client_id': patient.id,
            'representative_id': representative.id,
            'role': role_mapping.get(self.contact_relationship_type, 'client_representative'),
            'is_primary': True,  # First relationship of this type is primary
            'can_schedule_appointments': True,  # Default permission
            'can_receive_medical_info': self.contact_relationship_type in ['legal_guardian', 'healthcare_proxy', 'emergency_contact'],
        }
        
        return self.env['health.client.relation'].create(relation_vals)

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
        won_stage = self.env['crm.stage'].search([
            ('is_won', '=', True),
            '|', ('team_id', '=', False), ('team_id', '=', self.team_id.id)
        ], limit=1)
        
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
            'target': 'new',
            'context': {
                'default_res_id': self.id,
                'default_res_model': 'crm.lead',
                'default_summary': f'Follow-up on healthcare lead: {self.name}',
                'default_note': self.follow_up_notes,
                'default_date_deadline': self.next_follow_up_date or fields.Date.today(),
            }
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
        """Convert lead to field service order/booking"""
        self.ensure_one()
        
        if not self.service_interest:
            raise UserError(_('Please specify the service interest before converting to booking.'))
        
        # Create or get patient record
        patient = self._get_or_create_patient()
        
        # Map clinical priority to FSO priority (text -> numeric string)
        priority_mapping = {
            'routine': '0',      # Low
            'preventive': '1',   # Normal  
            'urgent': '2',       # High
            'emergency': '4',    # Emergency
        }
        fso_priority = priority_mapping.get(self.clinical_priority, '1')  # Default to Normal
        
        # Create field service order (booking)
        fso_vals = {
            'patient_id': patient.id,
            'name': patient.name,
            'patient_notes': self.service_requirements or self.description or f"Service booking for {self.service_interest}",
            'priority': fso_priority,
            'crm_lead_id': self.id,
        }
        
        # Map service interest to FSO service type selection
        if self.service_interest:
            service_type_mapping = {
                'home_visit': 'home_visit',
                'clinic_visit': 'clinic_visit', 
                'consultation': 'consultation',
                'emergency': 'emergency',
                'follow_up': 'follow_up',
                'preventive': 'preventive',
                'rehabilitation': 'rehabilitation',
                'telemedicine': 'telemedicine',
                'vaccination': 'vaccination',
                'diagnostic': 'diagnostic',
            }
            fso_vals['service_type'] = service_type_mapping.get(self.service_interest, 'consultation')
        
        fso = self.env['health.fieldservice.order'].create(fso_vals)
        
        # Update lead
        self.write({
            'patient_id': patient.id,
            'health_contact_outcome': 'service_booked',
            'contact_outcome': 'service_booked',
            'booking_status': 'confirmed',
            'stage_id': self._get_won_stage().id,
        })
        
        # Return action to open the created FSO booking form
        return {
            'type': 'ir.actions.act_window',
            'name': _('Booking'),
            'res_model': 'health.fieldservice.order',
            'res_id': fso.id,
            'view_mode': 'form',
            'target': 'current',
        }