# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class HealthClientSearchWizard(models.TransientModel):
    """
    Client Search Wizard - Shows matching clients for selection
    """
    _name = 'health.client.search.wizard'
    _description = 'Client Search Wizard'
    
    search_term = fields.Char('Search Term', readonly=True)
    source_lead_id = fields.Many2one(
        'crm.lead',
        string='Source Lead',
        readonly=True
    )
    source_initial_wizard_id = fields.Many2one(
        'health.initial.contact.wizard',
        string='Source Initial Contact Wizard',
        readonly=True
    )
    line_ids = fields.One2many(
        'health.client.search.line',
        'wizard_id',
        string='Search Results',
    )
    
    def _return_to_initial_wizard(self):
        """Return action to reopen the initial contact wizard"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('New Contact'),
            'res_model': 'health.initial.contact.wizard',
            'res_id': self.source_initial_wizard_id.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {'form_view_initial_mode': 'edit'},
        }
    
    def action_select_client(self, partner_id, partner_name):
        """
        Called when user selects a client from the search results.
        Updates the source's client_name field.
        """
        self.ensure_one()
        
        if self.source_initial_wizard_id and partner_id:
            # Update the initial contact wizard with the selected client name AND partner reference
            self.source_initial_wizard_id.write({
                'client_name': partner_name,
                'selected_client_id': partner_id,
            })
            # Reopen the initial wizard (Odoo replaces dialogs, doesn't stack them)
            return self._return_to_initial_wizard()
        elif self.source_lead_id and partner_id:
            # Update the lead with the selected client name
            self.source_lead_id.write({
                'client_name': partner_name,
            })
            # Return to the lead form
            return {
                'type': 'ir.actions.act_window',
                'name': _('Contact Details'),
                'res_model': 'crm.lead',
                'res_id': self.source_lead_id.id,
                'view_mode': 'form',
                'target': 'current',
                'context': {'form_view_initial_mode': 'edit'},
            }
        
        return {'type': 'ir.actions.act_window_close'}
    
    def action_cancel(self):
        """
        Cancel and return to the source form.
        """
        self.ensure_one()
        
        if self.source_initial_wizard_id:
            # Reopen the initial wizard (Odoo replaces dialogs, doesn't stack them)
            return self._return_to_initial_wizard()
        elif self.source_lead_id:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Contact Details'),
                'res_model': 'crm.lead',
                'res_id': self.source_lead_id.id,
                'view_mode': 'form',
                'target': 'current',
                'context': {'form_view_initial_mode': 'edit'},
            }
        else:
            return {'type': 'ir.actions.act_window_close'}


class HealthClientSearchLine(models.TransientModel):
    """
    Individual client search result line
    """
    _name = 'health.client.search.line'
    _description = 'Client Search Line'
    
    wizard_id = fields.Many2one(
        'health.client.search.wizard',
        string='Wizard',
        required=True,
        ondelete='cascade',
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Partner',
        required=True,
    )
    name = fields.Char('Name')
    phone = fields.Char('Phone')
    email = fields.Char('Email')
    code = fields.Char('Client Code')
    
    def action_select(self):
        """
        Select this client and update the source lead.
        """
        self.ensure_one()
        return self.wizard_id.action_select_client(self.partner_id.id, self.name)
    
    def write(self, vals):
        """Sync phone/email changes back to the partner record"""
        res = super().write(vals)
        for line in self:
            if line.partner_id:
                partner_vals = {}
                if 'phone' in vals:
                    partner_vals['phone'] = vals['phone']
                if 'email' in vals:
                    partner_vals['email'] = vals['email']
                if partner_vals:
                    line.partner_id.write(partner_vals)
        return res
