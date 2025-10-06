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

    # Computed fields for relationship counts (Section 2.2)
    relationship_total_count = fields.Integer(
        string='Total Relationships',
        compute='_compute_relationship_counts',
        store=False
    )

    total_caregivers = fields.Integer(
        string='Total Caregivers',
        compute='_compute_relationship_counts',
        store=False
    )

    total_payers = fields.Integer(
        string='Total Payers',
        compute='_compute_relationship_counts',
        store=False
    )

    total_referrers = fields.Integer(
        string='Total Referrers',
        compute='_compute_relationship_counts',
        store=False
    )

    total_emergency_contacts = fields.Integer(
        string='Total Emergency Contacts',
        compute='_compute_relationship_counts',
        store=False
    )

    total_legal_guardians = fields.Integer(
        string='Total Legal Guardians',
        compute='_compute_relationship_counts',
        store=False
    )

    # Representative-side counts (how many patients I support in each role)
    caregiver_patient_count = fields.Integer(
        string='Patients I Care For',
        compute='_compute_representative_counts',
        store=False
    )

    payer_patient_count = fields.Integer(
        string='Patients I Pay For',
        compute='_compute_representative_counts',
        store=False
    )

    referrer_patient_count = fields.Integer(
        string='Patients I Referred',
        compute='_compute_representative_counts',
        store=False
    )

    emergency_contact_patient_count = fields.Integer(
        string='Patients I\'m Emergency Contact For',
        compute='_compute_representative_counts',
        store=False
    )

    legal_guardian_patient_count = fields.Integer(
        string='Patients I\'m Legal Guardian For',
        compute='_compute_representative_counts',
        store=False
    )

    @api.depends('client_relationships', 'client_relationships.role')
    def _compute_relationship_counts(self):
        """Compute relationship counts by role (patient-side: my representatives)"""
        for partner in self:
            relationships = partner.client_relationships
            partner.relationship_total_count = len(relationships)
            partner.total_caregivers = len(relationships.filtered(lambda r: r.role == 'caregiver'))
            partner.total_payers = len(relationships.filtered(lambda r: r.role == 'payer'))
            partner.total_referrers = len(relationships.filtered(lambda r: r.role == 'referrer'))
            partner.total_emergency_contacts = len(relationships.filtered(lambda r: r.role == 'emergency_contact'))
            partner.total_legal_guardians = len(relationships.filtered(lambda r: r.role == 'legal_guardian'))

    @api.depends('representative_relationships', 'representative_relationships.role')
    def _compute_representative_counts(self):
        """Compute relationship counts by role (representative-side: patients I support)"""
        for partner in self:
            relationships = partner.representative_relationships
            partner.caregiver_patient_count = len(relationships.filtered(lambda r: r.role == 'caregiver'))
            partner.payer_patient_count = len(relationships.filtered(lambda r: r.role == 'payer'))
            partner.referrer_patient_count = len(relationships.filtered(lambda r: r.role == 'referrer'))
            partner.emergency_contact_patient_count = len(relationships.filtered(lambda r: r.role == 'emergency_contact'))
            partner.legal_guardian_patient_count = len(relationships.filtered(lambda r: r.role == 'legal_guardian'))

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

    # Section 2.2 - Relationship Smart Button Actions
    def action_view_all_relationships(self):
        """View all relationships for this partner"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('All Relationships - %s') % self.name,
            'res_model': 'health.client.relation',
            'view_mode': 'list,form',
            'domain': [('client_id', '=', self.id)],
            'context': {'default_client_id': self.id},
        }

    def action_view_my_caregivers(self):
        """View caregiver relationships"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('My Caregivers - %s') % self.name,
            'res_model': 'health.client.relation',
            'view_mode': 'list,form',
            'domain': [('client_id', '=', self.id), ('role', '=', 'caregiver')],
            'context': {'default_client_id': self.id, 'default_role': 'caregiver'},
        }

    def action_view_my_payers(self):
        """View payer relationships"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('My Payers - %s') % self.name,
            'res_model': 'health.client.relation',
            'view_mode': 'list,form',
            'domain': [('client_id', '=', self.id), ('role', '=', 'payer')],
            'context': {'default_client_id': self.id, 'default_role': 'payer'},
        }

    def action_view_my_referrers(self):
        """View referrer relationships"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('My Referrers - %s') % self.name,
            'res_model': 'health.client.relation',
            'view_mode': 'list,form',
            'domain': [('client_id', '=', self.id), ('role', '=', 'referrer')],
            'context': {'default_client_id': self.id, 'default_role': 'referrer'},
        }

    def action_view_my_emergency_contacts(self):
        """View emergency contact relationships"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('My Emergency Contacts - %s') % self.name,
            'res_model': 'health.client.relation',
            'view_mode': 'list,form',
            'domain': [('client_id', '=', self.id), ('role', '=', 'emergency_contact')],
            'context': {'default_client_id': self.id, 'default_role': 'emergency_contact'},
        }

    def action_view_my_legal_guardians(self):
        """View legal guardian relationships"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('My Legal Guardians - %s') % self.name,
            'res_model': 'health.client.relation',
            'view_mode': 'list,form',
            'domain': [('client_id', '=', self.id), ('role', '=', 'legal_guardian')],
            'context': {'default_client_id': self.id, 'default_role': 'legal_guardian'},
        }

    def action_view_relationship_network(self):
        """Open the D3.js relationship network graph view"""
        import logging
        _logger = logging.getLogger(__name__)

        self.ensure_one()
        _logger.info(f"=== action_view_relationship_network called for partner ID: {self.id}, name: {self.name} ===")

        action = {
            'type': 'ir.actions.act_window',
            'name': _('Relationship Network - %s') % self.name,
            'res_model': 'res.partner',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('health_crm.view_relationship_network_form').id,
            'target': 'new',
        }
        _logger.info(f"=== Returning action: {action} ===")
        return action

    # Section 2.2 - Relationship Hierarchy Widget (Org Chart Style)
    def get_relationship_hierarchy(self):
        """
        Get relationship hierarchy data for organization chart-style display.
        Returns a structured dict with relationships grouped by role.

        Structure matches Odoo's hr_department_chart pattern:
        - 'self': Current partner info
        - 'as_patient': Relationships where this person is the patient
        - 'as_representative': Relationships where this person is the representative
        """
        self.ensure_one()

        def _format_relationship_card(relation):
            """Format a relationship record into a card data structure"""
            # Determine if we're looking at the client or representative side
            partner = relation.representative_id if relation.client_id.id == self.id else relation.client_id

            # Format relationship type for display
            relationship_type_display = ''
            if relation.relationship_type:
                relationship_type_display = relation.relationship_type.replace('_', ' ').title()

            return {
                'id': partner.id,
                'name': partner.name,
                'role': relation.role,
                'relationship_type': relationship_type_display,
                'is_primary': relation.is_primary,
                'start_date': relation.start_date.isoformat() if relation.start_date else None,
                'end_date': relation.end_date.isoformat() if relation.end_date else None,
                'can_make_medical_decisions': relation.can_make_medical_decisions,
                'financial_responsibility': relation.financial_responsibility,
                'relation_id': relation.id,
            }

        # Build hierarchy structure
        hierarchy = {
            'self': {
                'id': self.id,
                'name': self.name,
                'is_patient': self.is_patient,
                'is_representative': self.is_representative,
                'patient_code': self.patient_code if self.is_patient else None,
                'total_relationships': len(self.client_relationships) + len(self.representative_relationships),
            },
            'as_patient': {},
            'as_representative': {},
        }

        # Patient-side: My representatives (people who support me)
        if self.is_patient and self.client_relationships:
            # Group by role
            for role_key, role_label in [
                ('caregiver', 'Caregivers'),
                ('payer', 'Payers'),
                ('referrer', 'Referrers'),
                ('emergency_contact', 'Emergency Contacts'),
                ('legal_guardian', 'Legal Guardians'),
                ('healthcare_proxy', 'Healthcare Proxies'),
                ('client_representative', 'Representatives'),
                ('family_member', 'Family Members'),
                ('friend', 'Friends'),
                ('professional', 'Professional Providers'),
            ]:
                relations = self.client_relationships.filtered(lambda r: r.role == role_key)
                if relations:
                    hierarchy['as_patient'][role_key] = {
                        'label': role_label,
                        'count': len(relations),
                        'cards': [_format_relationship_card(r) for r in relations],
                    }

        # Representative-side: Patients I support
        if self.is_representative and self.representative_relationships:
            # Group by role
            for role_key, role_label in [
                ('caregiver', 'Patients I Care For'),
                ('payer', 'Patients I Pay For'),
                ('referrer', 'Patients I Referred'),
                ('emergency_contact', 'Emergency Contact For'),
                ('legal_guardian', 'Legal Guardian For'),
                ('healthcare_proxy', 'Healthcare Proxy For'),
                ('client_representative', 'Patients I Represent'),
                ('family_member', 'Family Members'),
                ('friend', 'Friends'),
                ('professional', 'Professional Clients'),
            ]:
                relations = self.representative_relationships.filtered(lambda r: r.role == role_key)
                if relations:
                    hierarchy['as_representative'][role_key] = {
                        'label': role_label,
                        'count': len(relations),
                        'cards': [_format_relationship_card(r) for r in relations],
                    }

        return hierarchy


