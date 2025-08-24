# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class HealthContact(models.Model):
    """
    Healthcare Contact extending standard res.partner functionality
    Adds Vietnamese healthcare-specific fields and relationships
    """
    _inherit = 'res.partner'

    # CRITICAL: Client Requirements - Contact Table Fields
    unique_contact_id = fields.Char(
        'Unique Contact ID',
        help='Sequential contact ID per city (from Excel requirement)',
        copy=False
    )
    
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
    
    lead_followup_required = fields.Boolean(
        'Lead Follow-up Required',
        help='Auto-calculated from Excel requirement'
    )
    
    booking_status = fields.Selection([
        ('no_booking', 'No Booking'),
        ('pending', 'Booking Pending'),
        ('confirmed', 'Booking Confirmed'),
        ('completed', 'Booking Completed'),
        ('cancelled', 'Booking Cancelled')
    ], string='Booking Status', help='From Excel: Booking Status [Compulsory]', required=True, default='no_booking')

    # Vietnamese healthcare-specific identification (from Excel CMF table)
    cccd_number = fields.Char(
        'CCCD Number', 
        help='Vietnamese Citizen Identification Card Number (from Excel CMF)'
    )
    
    ethnicity = fields.Char(
        'Dân tộc', 
        help='Vietnamese Ethnicity (from Excel CMF)'
    )
    
    kinship_title = fields.Char(
        'Kinship Title', 
        help='Vietnamese Honorific Title (from Excel CMF)'
    )
    
    preferred_name = fields.Char(
        'Preferred Name',
        help='Name the person prefers to be called (from Excel CMF)'
    )

    # Vietnamese address structure fields
    vietnamese_address_line1 = fields.Char(
        'Named Area',
        help='Khu vực đặt tên'
    )
    
    vietnamese_address_line2 = fields.Char(
        'Apartment Number',
        help='Số căn hộ'
    )
    
    vietnamese_address_line3 = fields.Char(
        'Building Name',
        help='Tên tòa nhà'
    )
    
    house_number = fields.Char(
        'House Number',
        help='Số nhà'
    )
    
    sub_alley_number = fields.Char(
        'Sub-Alley Number',
        help='Số ngách'
    )
    
    alley_number = fields.Char(
        'Alley Number',
        help='Số ngõ'
    )
    
    ward_commune = fields.Char(
        'Ward/Commune',
        help='Phường/Xã'
    )

    # Healthcare relationship flags
    is_patient = fields.Boolean(
        'Is Patient',
        help='This contact is a patient'
    )
    
    is_caregiver = fields.Boolean(
        'Is Caregiver',
        help='This contact is a caregiver'
    )
    
    is_payer = fields.Boolean(
        'Is Payer',
        help='This contact is responsible for payments'
    )
    
    is_referrer = fields.Boolean(
        'Is Referrer',
        help='This contact refers patients'
    )

    # Healthcare relationships - as caregiver
    caregiver_client_ids = fields.One2many(
        'health.related.party',
        'caregiver_id',
        string='Clients (as Caregiver)',
        domain=[('relationship_type', '=', 'caregiver')],
        help='Clients this person cares for'
    )

    # Healthcare relationships - as payer
    payer_client_ids = fields.One2many(
        'health.related.party',
        'payer_id',
        string='Clients (as Payer)',
        domain=[('relationship_type', '=', 'payer')],
        help='Clients this person pays for'
    )

    # Healthcare relationships - as referrer
    referrer_client_ids = fields.One2many(
        'health.related.party',
        'referrer_id',
        string='Clients (as Referrer)',
        domain=[('relationship_type', '=', 'referrer')],
        help='Clients this person referred'
    )

    # Healthcare communication preferences
    preferred_contact_method = fields.Selection([
        ('phone', 'Phone'),
        ('email', 'Email'),
        ('zalo', 'Zalo'),
        ('facebook', 'Facebook'),
        ('sms', 'SMS'),
        ('in_person', 'In Person'),
    ], string='Preferred Contact Method', default='phone')

    zalo_number = fields.Char(
        'Zalo Number',
        help='Zalo contact number'
    )

    facebook_profile = fields.Char(
        'Facebook Profile',
        help='Facebook profile URL or username'
    )

    # Healthcare lead source tracking
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

    # Geographic and service preferences
    service_area_ids = fields.Many2many(
        'health.service.area',
        string='Service Areas',
        help='Geographic areas this contact is associated with'
    )

    gps_coordinates = fields.Char(
        'GPS Coordinates',
        help='GPS coordinates for home visits'
    )

    distance_from_clinic = fields.Float(
        'Distance from Clinic (km)',
        help='Distance from nearest clinic'
    )

    # Healthcare-specific notes
    healthcare_notes = fields.Text(
        'Healthcare Notes',
        help='General healthcare-related notes'
    )

    emergency_contact_name = fields.Char(
        'Emergency Contact Name'
    )

    emergency_contact_phone = fields.Char(
        'Emergency Contact Phone'
    )

    emergency_contact_relationship = fields.Char(
        'Emergency Contact Relationship'
    )

    @api.model
    def create(self, vals):
        """Override create to set Vietnamese defaults"""
        # Set Vietnam as default country for healthcare contacts
        if not vals.get('country_id'):
            vietnam = self.env.ref('base.vn', raise_if_not_found=False)
            if vietnam:
                vals['country_id'] = vietnam.id
        
        return super().create(vals)

    def get_formatted_vietnamese_address(self):
        """Get formatted Vietnamese address"""
        self.ensure_one()
        
        address_parts = []
        
        # Building/Apartment info
        if self.vietnamese_address_line2:  # Apartment number
            address_parts.append(f"Căn hộ {self.vietnamese_address_line2}")
        
        if self.vietnamese_address_line3:  # Building name
            address_parts.append(self.vietnamese_address_line3)
        
        if self.vietnamese_address_line1:  # Named area
            address_parts.append(self.vietnamese_address_line1)
        
        # Street address
        street_parts = []
        if self.house_number:
            street_parts.append(self.house_number)
        
        if self.sub_alley_number:
            street_parts.append(f"Ngách {self.sub_alley_number}")
        
        if self.alley_number:
            street_parts.append(f"Ngõ {self.alley_number}")
        
        if self.street:
            street_parts.append(self.street)
        
        if street_parts:
            address_parts.append(', '.join(street_parts))
        
        # Administrative divisions
        if self.ward_commune:
            address_parts.append(f"Phường/Xã {self.ward_commune}")
        
        if self.city:
            address_parts.append(self.city)
        
        if self.state_id:
            address_parts.append(self.state_id.name)
        
        return ', '.join(address_parts) if address_parts else ''

    def action_create_healthcare_lead(self):
        """Create a healthcare lead for this contact"""
        self.ensure_one()
        
        lead_vals = {
            'name': f'Healthcare Lead - {self.name}',
            'partner_id': self.id,
            'contact_name': self.name,
            'email_from': self.email,
            'phone': self.phone,
            'mobile': self.mobile,
            'street': self.street,
            'street2': self.street2,
            'city': self.city,
            'zip': self.zip,
            'state_id': self.state_id.id if self.state_id else False,
            'country_id': self.country_id.id if self.country_id else False,
            'team_id': self.env.ref('health_crm.healthcare_crm_team', raise_if_not_found=False).id,
            'vietnamese_channel': 'referral',  # Default for manual creation
        }
        
        lead = self.env['crm.lead'].create(lead_vals)
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Healthcare Lead'),
            'res_model': 'crm.lead',
            'res_id': lead.id,
            'view_mode': 'form',
            'target': 'current',
        }

    @api.depends('caregiver_client_ids', 'payer_client_ids', 'referrer_client_ids')
    def _compute_healthcare_relationship_counts(self):
        """Compute healthcare relationship counts"""
        for partner in self:
            partner.caregiver_count = len(partner.caregiver_client_ids)
            partner.payer_count = len(partner.payer_client_ids)
            partner.referrer_count = len(partner.referrer_client_ids)

    caregiver_count = fields.Integer(
        'Caregiver Count',
        compute='_compute_healthcare_relationship_counts',
        help='Number of clients this person cares for'
    )

    payer_count = fields.Integer(
        'Payer Count',
        compute='_compute_healthcare_relationship_counts',
        help='Number of clients this person pays for'
    )

    referrer_count = fields.Integer(
        'Referrer Count',
        compute='_compute_healthcare_relationship_counts',
        help='Number of clients this person referred'
    )