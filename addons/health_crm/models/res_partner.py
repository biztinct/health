# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class HealthContact(models.Model):
    """
    Healthcare Contact extending standard res.partner functionality
    Adds Vietnamese healthcare-specific fields and relationships
    """
    _inherit = 'res.partner'

    # CRITICAL: Client Requirements - Contact Table Fields
    # Note: Lead-specific fields (contact_outcome, booking_status, etc.) moved to crm.lead model

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

    # Note: healthcare_lead_source moved to crm.lead model

    # Healthcare role flags for relationship management
    is_patient = fields.Boolean(
        string='Is Patient',
        default=False,
        help='This person is a patient/client who receives healthcare services'
    )
    
    is_representative = fields.Boolean(
        string='Is Representative',
        default=False,
        help='This person can represent or support patients/clients'
    )
    
    is_caregiver = fields.Boolean(
        string='Is Caregiver',
        default=False,
        help='This person provides caregiving services'
    )
    
    is_payer = fields.Boolean(
        string='Is Payer',
        default=False,
        help='This person or entity is responsible for payments'
    )
    
    is_referrer = fields.Boolean(
        string='Is Referrer',
        default=False,
        help='This person refers patients to our services'
    )
    
    is_emergency_contact = fields.Boolean(
        string='Is Emergency Contact',
        default=False,
        help='This person serves as an emergency contact'
    )
    
    is_healthcare_provider = fields.Boolean(
        string='Is Healthcare Provider',
        default=False,
        help='This person is a healthcare professional or provider'
    )

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

    # Healthcare relationships - as client/patient
    client_relationships = fields.One2many(
        'health.client.relation',
        'client_id',
        string='My Representatives',
        help='People who represent or support me'
    )
    
    # Healthcare relationships - as representative
    representative_relationships = fields.One2many(
        'health.client.relation', 
        'representative_id',
        string='Clients I Represent',
        help='Clients/patients I represent or support'
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to set Vietnamese defaults"""
        # Handle both single dict and list of dicts
        if not isinstance(vals_list, list):
            vals_list = [vals_list]
            
        for vals in vals_list:
            # Set Vietnam as default country for healthcare contacts
            if not vals.get('country_id'):
                vietnam = self.env.ref('base.vn', raise_if_not_found=False)
                if vietnam:
                    vals['country_id'] = vietnam.id
        
        return super().create(vals_list)

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
            'preferred_language': 'vietnamese',  # Default for Vietnamese healthcare
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


