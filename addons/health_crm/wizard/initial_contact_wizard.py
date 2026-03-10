# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class HealthInitialContactWizard(models.TransientModel):
    """
    Initial Contact Popup Wizard
    
    This wizard handles the first step of the Contact-First CRM flow.
    Every incoming call/inquiry starts here to capture basic contact information.
    
    Flow:
    1. User opens this popup from Dashboard → Contacts
    2. System checks for existing contacts (by phone/email)
    3. User can either:
       - Click NEXT → Opens full Contact Details form
       - Click HOME → Marks as spam/junk and returns to dashboard
    """
    _name = 'health.initial.contact.wizard'
    _description = 'Initial Contact Entry Wizard'

    # =========================================================================
    # BASIC CONTACT INFORMATION
    # =========================================================================
    
    name = fields.Char(
        'Contact Name',
        required=True,
        help='Name of the person contacting'
    )
    
    contact_id = fields.Char(
        'Contact ID',
        readonly=True,
        help='Auto-generated or retrieved from existing contact'
    )
    
    contact_type = fields.Selection([
        ('new', 'New Contact'),
        ('repeat', 'Repeat Contact'),
    ], string='Contact Type', default='new', readonly=True,
       help='Automatically determined based on existing contact check')
    
    # Catchment Province (renamed from Province)
    catchment_province_id = fields.Many2one(
        'health.catchment.province',
        string='Catchment Province',
        required=True,
        help='Catchment province/area for this contact'
    )
    
    phone = fields.Char(
        'Phone Number',
        help='Contact phone number'
    )
    
    email = fields.Char(
        'Email',
        help='Contact email address'
    )
    
    mode_of_contact = fields.Selection([
        ('phone', 'Phone Call'),
        ('zalo', 'Zalo'),
        ('facebook', 'Facebook'),
        ('email', 'Email'),
        ('website', 'Website'),
        ('chatbox', 'Chatbox'),
        ('walk_in', 'Walk-in'),
    ], string='Mode of Contact', default='phone', required=True,
       help='How the contact reached out to us')
    
    contact_datetime = fields.Datetime(
        'Contact Date & Time',
        default=fields.Datetime.now,
        required=True,
        help='When the contact was received'
    )
    
    # =========================================================================
    # RELATIONSHIP CONTEXT
    # =========================================================================
    
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
       help='Relationship of the caller to the client/patient')
    
    client_name = fields.Char(
        'Client Name',
        help='Name of the actual client/patient when caller is not the client'
    )
    
    selected_client_id = fields.Many2one(
        'res.partner',
        string='Selected Client',
        domain="[('is_patient', '=', True)]",
        help='The actual client/patient record if selected from search'
    )
    
    # =========================================================================
    # EXISTING CONTACT DETECTION
    # =========================================================================
    
    existing_contact_id = fields.Many2one(
        'crm.lead',
        string='Existing Contact',
        help='If this is a repeat contact, the existing record'
    )
    
    existing_partner_id = fields.Many2one(
        'res.partner',
        string='Existing Client',
        help='If this contact is already a client'
    )
    
    duplicate_found = fields.Boolean(
        'Duplicate Found',
        default=False,
        compute='_compute_duplicate_check',
        store=False,
        help='Whether a duplicate contact was found'
    )
    
    duplicate_message = fields.Char(
        'Duplicate Message',
        compute='_compute_duplicate_check',
        store=False
    )
    
    # Spam caller detection
    is_spam_caller = fields.Boolean(
        'Spam Caller Detected',
        compute='_compute_spam_check',
        store=False,
        help='Whether this phone number is known to be spam'
    )
    
    spam_warning = fields.Char(
        'Spam Warning',
        compute='_compute_spam_check',
        store=False
    )
    
    def _normalize_phone(self, phone):
        """Normalize phone number by removing non-digit characters for comparison."""
        if not phone:
            return ''
        import re
        return re.sub(r'[^\d]', '', phone)
    
    @api.model
    def search_contacts_by_name(self, search_term):
        """
        Search for contacts, leads, and clients by name.
        Returns grouped results for display in popup.
        
        BIDIRECTIONAL ASSOCIATION LOGIC:
        - If a client matches: show in Clients section + show ALL associated leads in Leads section
        - If a lead matches: show in Leads section + show associated client in Clients section
        - This ensures users see the full relationship regardless of which end matches
        """
        if not search_term or len(search_term) < 2:
            return {'contacts': [], 'leads': [], 'clients': []}
        
        # ==========================================
        # Step 1: Search Clients that match directly
        # ==========================================
        matching_partners = self.env['res.partner'].search([
            ('is_patient', '=', True),
            '|', '|',
            ('name', 'ilike', search_term),
            ('phone', 'ilike', search_term),
            ('email', 'ilike', search_term),
        ], limit=15)
        
        # Track all client IDs we'll show (both matching and associated)
        all_client_ids = set(matching_partners.ids)
        
        # =========================================
        # Step 2: Search Leads that match directly
        # =========================================
        lead_domain = [
            '|', '|',
            ('name', 'ilike', search_term),
            ('phone', 'ilike', search_term),
            ('email_from', 'ilike', search_term),
        ]
        matching_leads = self.env['crm.lead'].search(lead_domain, limit=30)
        
        # Track leads by category
        directly_matching_lead_ids = set(matching_leads.ids)
        associated_lead_ids = set()
        
        # ==================================================
        # Step 3: Find associated leads for matching clients
        # These leads should appear in Leads section REGARDLESS of status
        # ==================================================
        if matching_partners:
            assoc_leads = self.env['crm.lead'].search([
                ('patient_id', 'in', matching_partners.ids),
            ], limit=30)
            associated_lead_ids.update(assoc_leads.ids)
        
        # Combine all lead IDs
        all_lead_ids = directly_matching_lead_ids | associated_lead_ids
        
        # ===================================================
        # Step 4: Find associated clients for matching leads
        # These clients should appear in Clients section
        # ===================================================
        for lead in matching_leads:
            if lead.patient_id and lead.patient_id.id not in all_client_ids:
                all_client_ids.add(lead.patient_id.id)
        
        # =========================================
        # Step 5: Build final Clients list
        # =========================================
        all_partners = self.env['res.partner'].browse(list(all_client_ids))
        clients_list = []
        for p in all_partners:
            # Find associated leads for this client
            assoc_leads_for_client = self.env['crm.lead'].search([
                ('patient_id', '=', p.id)
            ], limit=5)
            
            clients_list.append({
                'id': p.id,
                'name': p.name,
                'phone': p.phone or '',
                'email': p.email or '',
                'code': p.patient_code or '',
                'associated_lead_count': len(assoc_leads_for_client),
                'associated_leads': [{'id': l.id, 'name': l.name, 'code': l.unique_contact_code or ''} for l in assoc_leads_for_client],
            })
        
        # ==========================================
        # Step 6: Build final Leads/Contacts lists
        # ==========================================
        all_leads = self.env['crm.lead'].browse(list(all_lead_ids))
        contacts_list = []
        leads_list = []
        
        for lead in all_leads:
            # Find associated client for this lead
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
            }
            
            # Leads associated with matching clients always go to Leads section
            if lead.id in associated_lead_ids:
                leads_list.append(record)
            # Directly matching leads filter by status
            elif lead.contact_status == 'lead':
                leads_list.append(record)
            elif lead.contact_status in ['active', False, '']:
                contacts_list.append(record)
            # Skip other statuses like 'booking', 'lost_booking' for directly matching leads
        
        return {
            'contacts': contacts_list[:10],  # Limit to 10
            'leads': leads_list[:10],  # Limit to 10
            'clients': clients_list,
        }
    
    def action_search_by_name(self):
        """
        Action to search for existing contacts by name.
        Opens a selection dialog with grouped results.
        """
        self.ensure_one()
        if not self.name or len(self.name) < 2:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Search'),
                    'message': _('Please enter at least 2 characters to search'),
                    'type': 'warning',
                    'sticky': False,
                }
            }
        
        results = self.search_contacts_by_name(self.name)
        
        # Build the line data for creating the wizard
        line_vals = []
        
        # Add clients with associated leads info
        for client in results.get('clients', []):
            associated_leads = client.get('associated_leads', [])
            associated_info = ''
            if associated_leads:
                lead_names = [l['name'] for l in associated_leads[:3]]
                if len(associated_leads) > 3:
                    associated_info = f"Leads: {', '.join(lead_names)} (+{len(associated_leads) - 3} more)"
                else:
                    associated_info = f"Leads: {', '.join(lead_names)}"
            
            line_vals.append((0, 0, {
                'record_type': 'client',
                'record_id': client['id'],
                'name': client['name'],
                'phone': client.get('phone', ''),
                'email': client.get('email', ''),
                'code': client.get('code', ''),
                'associated_info': associated_info,
            }))
        
        # Add leads with associated client info
        for lead in results.get('leads', []):
            associated_client = lead.get('associated_client')
            associated_info = ''
            if associated_client:
                associated_info = f"Client: {associated_client['name']}"
            
            client_phone = ''
            if associated_client:
                client_phone = associated_client.get('phone', '')
            
            line_vals.append((0, 0, {
                'record_type': 'lead',
                'record_id': lead['id'],
                'name': lead['name'],
                'phone': lead.get('phone', ''),
                'email': lead.get('email', ''),
                'code': lead.get('code', ''),
                'associated_info': associated_info,
                'client_phone': client_phone,
            }))
        
        # Add contacts with associated client info
        for contact in results.get('contacts', []):
            associated_client = contact.get('associated_client')
            associated_info = ''
            if associated_client:
                associated_info = f"Client: {associated_client['name']}"
            
            client_phone = ''
            if associated_client:
                client_phone = associated_client.get('phone', '')
            
            line_vals.append((0, 0, {
                'record_type': 'contact',
                'record_id': contact['id'],
                'name': contact['name'],
                'phone': contact.get('phone', ''),
                'email': contact.get('email', ''),
                'code': contact.get('code', ''),
                'associated_info': associated_info,
                'client_phone': client_phone,
            }))
        
        # Create the search wizard with lines explicitly saved to database
        search_wizard = self.env['health.contact.search.wizard'].create({
            'search_term': self.name,
            'source_wizard_id': self.id,
            'line_ids': line_vals,
        })
        
        # Return action to open the created wizard
        return {
            'type': 'ir.actions.act_window',
            'name': _('Select Contact'),
            'res_model': 'health.contact.search.wizard',
            'res_id': search_wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }
    
    @api.depends('phone')
    def _compute_spam_check(self):
        """Check if phone number is known spam"""
        for wizard in self:
            wizard.is_spam_caller = False
            wizard.spam_warning = ''
            
            if wizard.phone:
                # Check if any lead with this phone is marked as spam
                spam_lead = self.env['crm.lead'].search([
                    ('phone', '=', wizard.phone),
                    ('is_spam_caller', '=', True),
                ], limit=1)
                
                if spam_lead:
                    wizard.is_spam_caller = True
                    wizard.spam_warning = _(
                        '⚠️ WARNING: This phone number was previously marked as SPAM. '
                        'Previous contact: %s'
                    ) % spam_lead.name
    
    # =========================================================================
    # COMPUTED FIELDS
    # =========================================================================
    
    @api.depends('phone', 'email', 'name')
    def _compute_duplicate_check(self):
        """Check for existing contacts by phone, email, or name"""
        for wizard in self:
            wizard.duplicate_found = False
            wizard.duplicate_message = ''
            
            if not wizard.phone and not wizard.email:
                continue
            
            # Search for existing leads
            domain = []
            if wizard.phone:
                domain = [('phone', '=', wizard.phone)]
            if wizard.email:
                if domain:
                    domain = ['|'] + domain + [('email_from', '=', wizard.email)]
                else:
                    domain = [('email_from', '=', wizard.email)]
            
            if domain:
                existing_lead = self.env['crm.lead'].search(domain, limit=1)
                if existing_lead:
                    wizard.duplicate_found = True
                    wizard.existing_contact_id = existing_lead.id
                    wizard.duplicate_message = _(
                        'Existing contact found: %s (Contact ID: %s)'
                    ) % (existing_lead.name, existing_lead.unique_contact_code or 'N/A')
                    continue
            
            # Search for existing partners (clients)
            partner_domain = []
            if wizard.phone:
                partner_domain = [('phone', '=', wizard.phone)]
            if wizard.email:
                if partner_domain:
                    partner_domain = ['|'] + partner_domain + [('email', '=', wizard.email)]
                else:
                    partner_domain = [('email', '=', wizard.email)]
            
            if partner_domain:
                existing_partner = self.env['res.partner'].search(partner_domain, limit=1)
                if existing_partner:
                    wizard.duplicate_found = True
                    wizard.existing_partner_id = existing_partner.id
                    wizard.duplicate_message = _(
                        'Existing client found: %s (Client ID: %s)'
                    ) % (existing_partner.name, existing_partner.patient_code or 'N/A')
    
    @api.onchange('phone', 'email')
    def _onchange_check_existing(self):
        """Auto-detect existing contacts when phone/email is entered"""
        if self.phone or self.email:
            self._compute_duplicate_check()
            if self.duplicate_found:
                if self.existing_contact_id:
                    self.contact_type = 'repeat'
                    self.contact_id = self.existing_contact_id.unique_contact_code
                    # Pre-fill name if not already set
                    if not self.name and self.existing_contact_id.name:
                        self.name = self.existing_contact_id.name
                elif self.existing_partner_id:
                    self.contact_type = 'repeat'
                    self.contact_id = self.existing_partner_id.patient_code
                    if not self.name and self.existing_partner_id.name:
                        self.name = self.existing_partner_id.name
    
    @api.model
    def default_get(self, fields_list):
        """Set default catchment province from user's assignment if available"""
        defaults = super().default_get(fields_list)
        user = self.env.user
        if hasattr(user, 'catchment_province_id') and user.catchment_province_id:
            defaults['catchment_province_id'] = user.catchment_province_id.id
        return defaults
    
    # =========================================================================
    # WIZARD ACTIONS
    # =========================================================================
    
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
        
        # Create search wizard with results, linking back to this initial contact wizard
        wizard = self.env['health.client.search.wizard'].create({
            'search_term': search_term,
            'source_initial_wizard_id': self.id,
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
    
    def action_next(self):
        """
        NEXT button - Create or update contact and open Contact Details form
        """
        self.ensure_one()
        
        # Validate at least phone or email is provided
        if not self.phone and not self.email:
            raise ValidationError(_('Please provide at least a phone number or email address.'))
        
        # If existing contact found, update it and open
        if self.existing_contact_id:
            lead = self.existing_contact_id
            update_vals = {
                'contact_datetime': self.contact_datetime,
                'mode_of_contact': self.mode_of_contact,
                'contact_type': 'repeat',
                'contact_status': 'active',  # Reactivate if was spam
                'contact_relationship_type': self.contact_relationship_type,
            }
            if self.client_name:
                update_vals['client_name'] = self.client_name
            if self.selected_client_id:
                update_vals['partner_id'] = self.selected_client_id.id
            lead.write(update_vals)
        else:
            # Create new lead/contact
            lead_vals = {
                'name': self.name,
                'phone': self.phone,
                'email_from': self.email,
                'catchment_province_id': self.catchment_province_id.id,
                'mode_of_contact': self.mode_of_contact,
                'contact_datetime': self.contact_datetime,
                'contact_type': 'new',
                'contact_status': 'active',
                'type': 'opportunity',  # Use opportunity type for contacts
                'contact_relationship_type': self.contact_relationship_type,
            }
            if self.client_name:
                lead_vals['client_name'] = self.client_name
            
            # Link to existing partner if found
            if self.selected_client_id:
                lead_vals['partner_id'] = self.selected_client_id.id
            elif self.existing_partner_id:
                lead_vals['partner_id'] = self.existing_partner_id.id
                lead_vals['contact_type'] = 'repeat'
            
            lead = self.env['crm.lead'].create(lead_vals)
        
        # Return action to open the Lead Hub-Spoke Dashboard
        return {
            'type': 'ir.actions.client',
            'tag': 'health_landing_lead_hub',
            'params': {
                'lead_id': lead.id,
                'lead_name': lead.name,
            },
        }
    
    def action_home_mark_spam(self):
        """
        HOME button - Mark as spam/junk and return to dashboard
        
        If NEXT is not clicked, the contact is recorded as a false (junk) contact
        """
        self.ensure_one()
        
        # Create a spam record if any info was entered
        if self.name and (self.phone or self.email):
            lead_vals = {
                'name': self.name,
                'phone': self.phone,
                'email_from': self.email,
                'catchment_province_id': self.catchment_province_id.id if self.catchment_province_id else False,
                'mode_of_contact': self.mode_of_contact,
                'contact_datetime': self.contact_datetime,
                'contact_type': self.contact_type,
                'contact_status': 'spam',  # Mark as spam
                'contact_outcome': 'rejected',
                'type': 'opportunity',
            }
            self.env['crm.lead'].create(lead_vals)
        
        # Return to Health Flow dashboard
        return {
            'type': 'ir.actions.client',
            'tag': 'health_flow_dashboard',
        }
    
    def action_use_existing(self):
        """
        Use the existing contact that was found
        """
        self.ensure_one()
        
        if self.existing_contact_id:
            # Update existing lead but preserve important statuses
            # Don't reset contact_status if it's already set to something meaningful
            update_vals = {
                'contact_datetime': self.contact_datetime,
                'mode_of_contact': self.mode_of_contact,
                'contact_type': 'repeat',
            }
            # Only set contact_status to 'active' if it's currently empty or spam
            # Preserve 'lead', 'booking', 'lost_booking' statuses
            if not self.existing_contact_id.contact_status or self.existing_contact_id.contact_status == 'spam':
                update_vals['contact_status'] = 'active'
            
            self.existing_contact_id.write(update_vals)
            return {
                'type': 'ir.actions.act_window',
                'name': _('Contact Details'),
                'res_model': 'crm.lead',
                'res_id': self.existing_contact_id.id,
                'view_mode': 'form',
                'view_id': self.env.ref('health_crm.view_healthcare_opportunity_form').id,
                'target': 'current',
            }
        elif self.existing_partner_id:
            # Create a new lead linked to this partner
            lead_vals = {
                'name': self.existing_partner_id.name,
                'partner_id': self.existing_partner_id.id,
                'phone': self.phone or self.existing_partner_id.phone,
                'email_from': self.email or self.existing_partner_id.email,
                'catchment_province_id': self.catchment_province_id.id if self.catchment_province_id else False,
                'mode_of_contact': self.mode_of_contact,
                'contact_datetime': self.contact_datetime,
                'contact_type': 'repeat',
                'contact_status': 'active',
                'type': 'opportunity',
            }
            lead = self.env['crm.lead'].create(lead_vals)
            return {
                'type': 'ir.actions.act_window',
                'name': _('Contact Details'),
                'res_model': 'crm.lead',
                'res_id': lead.id,
                'view_mode': 'form',
                'view_id': self.env.ref('health_crm.view_healthcare_opportunity_form').id,
                'target': 'current',
            }
        
        raise UserError(_('No existing contact selected.'))
