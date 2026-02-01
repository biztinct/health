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
        
        IMPORTANT: Each person should appear ONLY ONCE:
        - If they are a Client (res.partner with is_patient), show as Client only
        - If they are a Lead (crm.lead with contact_status='lead'), show as Lead only
        - If they are a Contact (crm.lead with contact_status='active'), show as Contact only
        
        We avoid showing the same person multiple times by:
        1. First finding all clients (res.partner)
        
        DEBUG: Adding logging to trace search results
        2. Then finding leads/contacts that:
           - Do NOT have a linked client (patient_id)
           - AND do NOT have a unique_contact_code that matches any client's patient_code
        """
        if not search_term or len(search_term) < 2:
            return {'contacts': [], 'leads': [], 'clients': []}
        
        # Step 1: Search Clients (res.partner with is_patient=True)
        # These are the highest priority - converted contacts
        partners = self.env['res.partner'].search([
            ('is_patient', '=', True),
            '|', '|',
            ('name', 'ilike', search_term),
            ('phone', 'ilike', search_term),
            ('email', 'ilike', search_term),
        ], limit=15)
        
        clients_list = [{
            'id': p.id,
            'name': p.name,
            'phone': p.phone or '',
            'email': p.email or '',
            'code': p.patient_code or '',
        } for p in partners]
        
        # Collect client patient_codes to exclude matching leads/contacts
        client_patient_codes = [p.patient_code for p in partners if p.patient_code]
        client_partner_ids = partners.ids
        
        # Step 2: Search CRM Leads
        lead_domain = [
            '|', '|',
            ('name', 'ilike', search_term),
            ('phone', 'ilike', search_term),
            ('email_from', 'ilike', search_term),
        ]
        
        leads = self.env['crm.lead'].search(lead_domain, limit=30)
        
        # Build sets of client identifiers for exclusion matching
        # A lead should be excluded from results if it matches any client by:
        # - patient_id link
        # - unique_contact_code matching patient_code
        # - name + email/phone matching (for cases where they're the same person)
        client_names_lower = {p.name.lower().strip() for p in partners if p.name}
        client_emails_lower = {p.email.lower().strip() for p in partners if p.email}
        client_phones = {self._normalize_phone(p.phone) for p in partners if p.phone}
        
        # Filter leads to exclude those that are already represented as clients
        contacts_list = []
        leads_list = []
        for lead in leads:
            # Skip if this lead has a linked patient (client)
            if lead.patient_id and lead.patient_id.id in client_partner_ids:
                continue
            
            # Skip if the unique_contact_code matches a client's patient_code
            if lead.unique_contact_code and lead.unique_contact_code in client_patient_codes:
                continue
            
            # Skip if the lead matches a client by name AND (email or phone)
            lead_name = (lead.name or '').lower().strip()
            lead_email = (lead.email_from or '').lower().strip()
            lead_phone = self._normalize_phone(lead.phone)
            
            if lead_name and lead_name in client_names_lower:
                # Name matches a client - check if email or phone also matches
                if (lead_email and lead_email in client_emails_lower) or \
                   (lead_phone and lead_phone in client_phones):
                    continue  # This lead is likely the same person as a client
            
            record = {
                'id': lead.id,
                'name': lead.name,
                'phone': lead.phone or '',
                'email': lead.email_from or '',
                'code': lead.unique_contact_code or '',
                'status': lead.contact_status,
            }
            if lead.contact_status == 'lead':
                leads_list.append(record)
            elif lead.contact_status in ['active', False, '']:
                # Only add to contacts if status is active or not set
                contacts_list.append(record)
            # Skip other statuses like 'booking', 'lost_booking' - those are handled differently
        
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
        
        # Add clients
        for client in results.get('clients', []):
            line_vals.append((0, 0, {
                'record_type': 'client',
                'record_id': client['id'],
                'name': client['name'],
                'phone': client.get('phone', ''),
                'email': client.get('email', ''),
                'code': client.get('code', ''),
            }))
        
        # Add leads
        for lead in results.get('leads', []):
            line_vals.append((0, 0, {
                'record_type': 'lead',
                'record_id': lead['id'],
                'name': lead['name'],
                'phone': lead.get('phone', ''),
                'email': lead.get('email', ''),
                'code': lead.get('code', ''),
            }))
        
        # Add contacts
        for contact in results.get('contacts', []):
            line_vals.append((0, 0, {
                'record_type': 'contact',
                'record_id': contact['id'],
                'name': contact['name'],
                'phone': contact.get('phone', ''),
                'email': contact.get('email', ''),
                'code': contact.get('code', ''),
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
            lead.write({
                'contact_datetime': self.contact_datetime,
                'mode_of_contact': self.mode_of_contact,
                'contact_type': 'repeat',
                'contact_status': 'active',  # Reactivate if was spam
            })
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
            }
            
            # Link to existing partner if found
            if self.existing_partner_id:
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
