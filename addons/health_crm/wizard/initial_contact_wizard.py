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
    
    # Province (renamed from Primary Facility)
    province_id = fields.Many2one(
        'health.province',
        string='Province',
        required=True,
        help='Vietnamese province or city for this contact'
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
        """Set default province from user's facility if available"""
        defaults = super().default_get(fields_list)
        user = self.env.user
        if hasattr(user, 'facility_id') and user.facility_id:
            # Try to get province from user's facility
            if hasattr(user.facility_id, 'province_id') and user.facility_id.province_id:
                defaults['province_id'] = user.facility_id.province_id.id
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
                'province_code': self.province_id.id,
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
        
        # Return action to open the Contact Details form
        return {
            'type': 'ir.actions.act_window',
            'name': _('Contact Details'),
            'res_model': 'crm.lead',
            'res_id': lead.id,
            'view_mode': 'form',
            'view_id': self.env.ref('health_crm.view_healthcare_opportunity_form').id,
            'target': 'current',
            'context': {
                'form_view_initial_mode': 'edit',
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
                'province_code': self.province_id.id if self.province_id else False,
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
            # Update existing lead and open it
            self.existing_contact_id.write({
                'contact_datetime': self.contact_datetime,
                'mode_of_contact': self.mode_of_contact,
                'contact_type': 'repeat',
                'contact_status': 'active',
            })
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
                'province_code': self.province_id.id if self.province_id else False,
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
