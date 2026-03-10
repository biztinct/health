# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class HealthContactSearchWizard(models.TransientModel):
    """
    Contact Search Wizard - Shows grouped search results for contacts, leads, and clients
    """
    _name = 'health.contact.search.wizard'
    _description = 'Contact Search Wizard'
    
    search_term = fields.Char('Search Term', readonly=True)
    source_wizard_id = fields.Many2one(
        'health.initial.contact.wizard',
        string='Source Wizard',
        readonly=True
    )
    
    # Selection lines
    contact_line_ids = fields.One2many(
        'health.contact.search.line',
        'wizard_id',
        string='Contacts',
        domain=[('record_type', '=', 'contact')],
    )
    lead_line_ids = fields.One2many(
        'health.contact.search.line',
        'wizard_id',
        string='Leads',
        domain=[('record_type', '=', 'lead')],
    )
    client_line_ids = fields.One2many(
        'health.contact.search.line',
        'wizard_id',
        string='Clients',
        domain=[('record_type', '=', 'client')],
    )
    
    @api.model
    def default_get(self, fields_list):
        """Populate search results from context"""
        defaults = super().default_get(fields_list)
        
        context = self.env.context
        search_results = context.get('search_results', {})
        
        lines = []
        
        # Add clients
        for client in search_results.get('clients', []):
            lines.append((0, 0, {
                'record_type': 'client',
                'record_id': client['id'],
                'name': client['name'],
                'phone': client.get('phone', ''),
                'email': client.get('email', ''),
                'code': client.get('code', ''),
            }))
        
        # Add leads
        for lead in search_results.get('leads', []):
            lines.append((0, 0, {
                'record_type': 'lead',
                'record_id': lead['id'],
                'name': lead['name'],
                'phone': lead.get('phone', ''),
                'email': lead.get('email', ''),
                'code': lead.get('code', ''),
            }))
        
        # Add contacts
        for contact in search_results.get('contacts', []):
            lines.append((0, 0, {
                'record_type': 'contact',
                'record_id': contact['id'],
                'name': contact['name'],
                'phone': contact.get('phone', ''),
                'email': contact.get('email', ''),
                'code': contact.get('code', ''),
            }))
        
        if lines:
            defaults['line_ids'] = lines
        
        return defaults
    
    # All lines in one field for easier management
    line_ids = fields.One2many(
        'health.contact.search.line',
        'wizard_id',
        string='Search Results',
    )
    
    def action_select_record(self, record_type, record_id):
        """
        Called when user selects a record from the search results.
        Populates the initial wizard with the selected contact's data
        and returns to it.
        """
        if not self.source_wizard_id:
            # No source wizard - fallback to opening the record directly
            if record_type == 'client':
                return {
                    'type': 'ir.actions.act_window',
                    'name': _('Client Details'),
                    'res_model': 'res.partner',
                    'res_id': record_id,
                    'view_mode': 'form',
                    'target': 'current',
                }
            else:
                return {'type': 'ir.actions.act_window_close'}
        
        wizard = self.source_wizard_id
        update_vals = {}
        
        if record_type == 'client':
            # Selected a client (res.partner with is_patient=True)
            partner = self.env['res.partner'].browse(record_id)
            if partner.exists():
                update_vals['name'] = partner.name
                update_vals['phone'] = partner.phone or partner.mobile or ''
                update_vals['email'] = partner.email or ''
                # Client is calling for themselves - set relationship to 'client'
                update_vals['contact_relationship_type'] = 'client'
                update_vals['selected_client_id'] = partner.id
                update_vals['client_name'] = partner.name
                
        elif record_type == 'lead':
            # Selected a lead (crm.lead)
            lead = self.env['crm.lead'].browse(record_id)
            if lead.exists():
                update_vals['name'] = lead.name or ''
                update_vals['phone'] = lead.phone or ''
                update_vals['email'] = lead.email_from or ''
                # Auto-populate relationship from the lead's last interaction
                if lead.contact_relationship_type:
                    update_vals['contact_relationship_type'] = lead.contact_relationship_type
                # Auto-populate client name from the lead
                if lead.client_name:
                    update_vals['client_name'] = lead.client_name
                # If the lead has a partner_id (linked client), set it
                if lead.partner_id:
                    update_vals['selected_client_id'] = lead.partner_id.id
                    if not lead.client_name:
                        update_vals['client_name'] = lead.partner_id.name
                        
        elif record_type == 'contact':
            # Selected a contact (crm.lead in initial/active status)
            lead = self.env['crm.lead'].browse(record_id)
            if lead.exists():
                update_vals['name'] = lead.name or ''
                update_vals['phone'] = lead.phone or ''
                update_vals['email'] = lead.email_from or ''
                # Auto-populate from the contact's data
                if lead.contact_relationship_type:
                    update_vals['contact_relationship_type'] = lead.contact_relationship_type
                if lead.client_name:
                    update_vals['client_name'] = lead.client_name
                if lead.partner_id:
                    update_vals['selected_client_id'] = lead.partner_id.id
                    if not lead.client_name:
                        update_vals['client_name'] = lead.partner_id.name
        
        # Write all updates to the source wizard
        if update_vals:
            wizard.write(update_vals)
        
        # Return to the initial wizard
        return {
            'type': 'ir.actions.act_window',
            'name': _('New Contact'),
            'res_model': 'health.initial.contact.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'views': [(self.env.ref('health_crm.view_initial_contact_wizard_form').id, 'form')],
            'target': 'new',
            'context': {
                'form_view_initial_mode': 'edit',
            },
        }
    
    def action_continue_new(self):
        """
        Continue creating a new contact - returns to the source wizard
        with the search term preserved in the name field.
        """
        self.ensure_one()
        
        if self.source_wizard_id:
            # Return to the source wizard with the name preserved
            return {
                'type': 'ir.actions.act_window',
                'name': _('New Contact'),
                'res_model': 'health.initial.contact.wizard',
                'res_id': self.source_wizard_id.id,
                'view_mode': 'form',
                'views': [(self.env.ref('health_crm.view_initial_contact_wizard_form').id, 'form')],
                'target': 'new',
                'context': {
                    'form_view_initial_mode': 'edit',
                },
            }
        else:
            # Fallback: open a new wizard with the search term as name
            return {
                'type': 'ir.actions.act_window',
                'name': _('New Contact'),
                'res_model': 'health.initial.contact.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_name': self.search_term,
                    'form_view_initial_mode': 'edit',
                },
            }
    
    def action_cancel(self):
        """
        Cancel and return to the source wizard.
        """
        self.ensure_one()
        
        if self.source_wizard_id:
            # Return to the source wizard
            return {
                'type': 'ir.actions.act_window',
                'name': _('New Contact'),
                'res_model': 'health.initial.contact.wizard',
                'res_id': self.source_wizard_id.id,
                'view_mode': 'form',
                'views': [(self.env.ref('health_crm.view_initial_contact_wizard_form').id, 'form')],
                'target': 'new',
                'context': {
                    'form_view_initial_mode': 'edit',
                },
            }
        else:
            # Just close if no source wizard
            return {'type': 'ir.actions.act_window_close'}


class HealthContactSearchLine(models.TransientModel):
    """
    Individual search result line
    """
    _name = 'health.contact.search.line'
    _description = 'Contact Search Line'
    
    wizard_id = fields.Many2one(
        'health.contact.search.wizard',
        string='Wizard',
        ondelete='cascade',
    )
    
    record_type = fields.Selection([
        ('contact', 'Contact'),
        ('lead', 'Lead'),
        ('client', 'Client'),
    ], string='Type', required=True)
    
    record_id = fields.Integer('Record ID', required=True)
    name = fields.Char('Name', required=True)
    phone = fields.Char('Phone')
    email = fields.Char('Email')
    code = fields.Char('Code')
    
    # Associated info - shows linked client (for leads) or linked leads (for clients)
    associated_info = fields.Char('Associated', help='Shows linked client for leads, or linked leads for clients')
    client_phone = fields.Char('Client Phone', help='Phone number of the associated client/patient')
    
    def action_select(self):
        """Select this record and open the appropriate form"""
        self.ensure_one()
        return self.wizard_id.action_select_record(self.record_type, self.record_id)
