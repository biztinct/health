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
    
    # Link to Client Representative (FROM EXCEL REQUIREMENTS)
    client_representative_id = fields.Many2one(
        'health.client.representative',
        string='Client Representative',
        help='From Excel: client_representative_id - Person representing this lead'
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
        }
        
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
        
        return self.env['res.partner'].create(patient_vals)

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