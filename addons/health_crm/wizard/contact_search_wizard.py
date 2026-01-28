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
        Opens the appropriate form based on record type.
        """
        if record_type == 'client':
            # Open client form (res.partner)
            return {
                'type': 'ir.actions.act_window',
                'name': _('Client Details'),
                'res_model': 'res.partner',
                'res_id': record_id,
                'view_mode': 'form',
                'views': [(self.env.ref('health_base.view_health_patient_form').id, 'form')],
                'target': 'current',
            }
        else:
            # Open lead/contact form (crm.lead)
            return {
                'type': 'ir.actions.act_window',
                'name': _('Contact Details'),
                'res_model': 'crm.lead',
                'res_id': record_id,
                'view_mode': 'form',
                'views': [(self.env.ref('health_crm.view_healthcare_opportunity_form').id, 'form')],
                'target': 'current',
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
    
    def action_select(self):
        """Select this record and open the appropriate form"""
        self.ensure_one()
        return self.wizard_id.action_select_record(self.record_type, self.record_id)
