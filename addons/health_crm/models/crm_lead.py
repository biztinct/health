# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


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

    # Healthcare relationships
    patient_id = fields.Many2one(
        'res.partner', 
        string='Patient',
        domain=[('is_patient', '=', True)],
        help='Linked patient record if converted'
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

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to set healthcare-specific defaults"""
        # Handle both single dict and list of dicts
        if not isinstance(vals_list, list):
            vals_list = [vals_list]
            
        for vals in vals_list:
            # Generate unique contact code if not provided
            if not vals.get('unique_contact_code'):
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
        
        return super().create(vals_list)
    
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

    def _get_or_create_patient(self):
        """Get existing patient or create new one from lead"""
        if self.patient_id:
            return self.patient_id
        
        # Try to find existing patient by partner  
        if self.partner_id and self.partner_id.is_patient:
            return self.partner_id
        
        # Create new patient
        patient_vals = {
            'name': self.contact_name or self.name,
            'email': self.email_from,
            'phone': self.phone,
            'mobile': self.mobile,
            'is_patient': True,
            'preferred_contact_method': 'phone',
            'country_id': self.country_id.id if self.country_id else self.env.ref('base.vn', raise_if_not_found=False).id,
        }
        
        # Copy relevant lead data to patient record
        if self.healthcare_lead_source:
            patient_vals['comment'] = f"Original lead source: {dict(self._fields['healthcare_lead_source'].selection).get(self.healthcare_lead_source, self.healthcare_lead_source)}"
        
        # Add address if available
        if self.street:
            patient_vals.update({
                'street': self.street,
                'street2': self.street2,
                'city': self.city,
                'zip': self.zip,
                'state_id': self.state_id.id if self.state_id else False,
                'country_id': self.country_id.id if self.country_id else False,
            })
        
        patient = self.env['res.partner'].create(patient_vals)
        
        # Create healthcare relationships from lead data
        self._create_healthcare_relationships(patient)
        
        return patient

    def _create_healthcare_relationships(self, patient):
        """Create healthcare relationships from lead data"""
        self.ensure_one()
        
        # Create caregiver relationship
        if self.primary_caregiver_id:
            self.env['health.client.relation'].create({
                'client_id': patient.id,
                'representative_id': self.primary_caregiver_id.id,
                'role': 'caregiver',
                'is_primary': True,
                'can_make_medical_decisions': True,
                'can_receive_medical_info': True,
                'can_schedule_appointments': True,
            })
        
        # Create secondary caregiver relationship
        if self.secondary_caregiver_id:
            self.env['health.client.relation'].create({
                'client_id': patient.id,
                'representative_id': self.secondary_caregiver_id.id,
                'role': 'caregiver',
                'is_primary': False,
                'can_make_medical_decisions': False,
                'can_receive_medical_info': True,
                'can_schedule_appointments': False,
            })
        
        # Create payer relationship
        if self.primary_payer_id:
            self.env['health.client.relation'].create({
                'client_id': patient.id,
                'representative_id': self.primary_payer_id.id,
                'role': 'payer',
                'is_primary': True,
                'financial_responsibility': 100.0,
            })
        
        # Create referrer relationship
        if self.referrer_id:
            self.env['health.client.relation'].create({
                'client_id': patient.id,
                'representative_id': self.referrer_id.id,
                'role': 'referrer',
                'is_primary': True,
            })
        
        # Create emergency contact relationship
        if self.emergency_contact_id:
            self.env['health.client.relation'].create({
                'client_id': patient.id,
                'representative_id': self.emergency_contact_id.id,
                'role': 'emergency_contact',
                'is_primary': True,
                'can_receive_medical_info': True,
            })

    def _get_appointment_type(self):
        """Get appointment type based on service interest"""
        domain = []
        if self.service_interest:
            domain = [('name', 'ilike', self.service_interest.replace('_', ' '))]
        
        appointment_type = self.env['health.appointment.type'].search(domain, limit=1)
        
        if not appointment_type:
            # Return default appointment type
            appointment_type = self.env['health.appointment.type'].search([], limit=1)
        
        return appointment_type

    def _get_won_stage(self):
        """Get the 'won' stage for healthcare CRM"""
        won_stage = self.env['crm.stage'].search([
            ('is_won', '=', True),
            '|', ('team_ids', '=', False), ('team_ids', 'in', self.team_id.id)
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
        
        # Create field service order (booking)
        fso_vals = {
            'patient_id': patient.id,
            'name': f"Booking from Lead: {self.name}",
            'description': self.service_requirements or self.description or f"Service booking for {self.service_interest}",
            'priority': self.clinical_priority,
            'lead_id': self.id,
        }
        
        # Add appointment type if available
        appointment_type = self._get_appointment_type()
        if appointment_type:
            fso_vals['appointment_type_id'] = appointment_type.id
        
        fso = self.env['health.fieldservice.order'].create(fso_vals)
        
        # Update lead
        self.write({
            'patient_id': patient.id,
            'health_contact_outcome': 'service_booked',
            'contact_outcome': 'service_booked',
            'booking_status': 'confirmed',
            'stage_id': self._get_won_stage().id,
        })
        
        # Return action to open the created booking
        return {
            'type': 'ir.actions.act_window',
            'name': _('Field Service Order'),
            'res_model': 'health.fieldservice.order',
            'res_id': fso.id,
            'view_mode': 'form',
            'target': 'current',
        }