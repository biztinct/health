# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class HealthFollowUpWizard(models.TransientModel):
    """
    Follow-up Activities Window
    
    This wizard provides a dedicated window for managing follow-up activities
    with menu items for different actions.
    
    Menu Items:
    a. Log as Lead (in calendar)
    b. Log planned activity (in calendar)
    c. Show all current leads (sorted by planned follow-up date)
    d. Show all current planned activities (sorted by date)
    e. Show Calendar (all leads & activities)
    f. Recent Client Follow-up
    g. Visit Satisfaction Follow-up (placeholder)
    """
    _name = 'health.followup.wizard'
    _description = 'Follow-up Activities Window'

    # =========================================================================
    # SEARCH / FILTER FIELDS
    # =========================================================================
    
    client_id = fields.Many2one(
        'res.partner',
        string='Search Client',
        domain="[('is_patient', '=', True)]",
        help='Search and select a client to view their follow-ups'
    )
    
    contact_id = fields.Many2one(
        'crm.lead',
        string='Search Contact',
        domain="[('contact_status', '=', 'contact')]",
        help='Search and select a contact to view their follow-ups'
    )
    
    lead_filter_id = fields.Many2one(
        'crm.lead',
        string='Search Lead',
        domain="[('contact_status', '=', 'lead')]",
        help='Search and select a lead to view their follow-ups'
    )
    
    # If opened from a contact form, retain context
    context_lead_id = fields.Many2one(
        'crm.lead',
        string='Current Contact',
        help='Contact from which this window was opened'
    )
    
    # =========================================================================
    # FILTER ONCHANGE - MUTUALLY EXCLUSIVE FILTERS
    # =========================================================================
    
    @api.onchange('client_id')
    def _onchange_client_id(self):
        """When client is selected, clear other filters to avoid ambiguity"""
        if self.client_id:
            self.contact_id = False
            self.lead_filter_id = False
    
    @api.onchange('contact_id')
    def _onchange_contact_id(self):
        """When contact is selected, clear other filters to avoid ambiguity"""
        if self.contact_id:
            self.client_id = False
            self.lead_filter_id = False
    
    @api.onchange('lead_filter_id')
    def _onchange_lead_filter_id(self):
        """When lead is selected, clear other filters to avoid ambiguity"""
        if self.lead_filter_id:
            self.client_id = False
            self.contact_id = False
    
    # =========================================================================
    # MENU ACTIONS
    # =========================================================================
    
    def _get_or_create_lead_for_client(self):
        """
        Find existing lead for client, or create a follow-up lead.
        This allows activities to be scheduled on leads (not directly on clients)
        while maintaining a seamless user experience.
        
        Search priority:
        1. Leads where partner_id matches client
        2. Leads where patient_id matches client  
        3. Leads where client_name matches client's name
        """
        if not self.client_id:
            return False
        
        Lead = self.env['crm.lead']
        
        # Search for leads linked to this client via multiple fields
        # Use OR conditions to find leads by partner_id, patient_id, or client_name
        lead = Lead.search([
            '|', '|',
            ('partner_id', '=', self.client_id.id),
            ('patient_id', '=', self.client_id.id),
            ('client_name', '=ilike', self.client_id.name),
        ], limit=1, order='create_date desc')
        
        if not lead:
            # No existing lead found - create new follow-up lead
            lead = Lead.create({
                'name': f"Follow-up: {self.client_id.name}",
                'partner_id': self.client_id.id,
                'patient_id': self.client_id.id,
                'contact_status': 'lead',
                'type': 'opportunity',
                'phone': self.client_id.phone,
                'email_from': self.client_id.email,
            })
        
        return lead
    
    def action_log_lead_calendar(self):
        """
        Menu a: Log as Lead (in calendar)
        Opens a new lead form with calendar scheduling.
        Requires a Contact to be selected first.
        """
        self.ensure_one()
        
        # Check if a contact has been selected
        if not self.contact_id and not self.context_lead_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No Contact Selected'),
                    'message': _('Please select a Contact first to log as a lead.'),
                    'type': 'warning',
                    'sticky': False,
                }
            }
        
        context = {
            'default_type': 'opportunity',
            'default_contact_status': 'lead',
        }
        
        # Pre-fill from selected contact
        if self.contact_id:
            context.update({
                'default_partner_id': self.contact_id.partner_id.id if self.contact_id.partner_id else False,
                'default_name': self.contact_id.name,
                'default_phone': self.contact_id.phone,
                'default_email_from': self.contact_id.email_from,
            })
        elif self.client_id:
            context.update({
                'default_partner_id': self.client_id.id,
                'default_name': self.client_id.name,
                'default_phone': self.client_id.phone,
                'default_email_from': self.client_id.email,
            })
        elif self.context_lead_id:
            context.update({
                'default_partner_id': self.context_lead_id.partner_id.id if self.context_lead_id.partner_id else False,
                'default_name': self.context_lead_id.name,
                'default_phone': self.context_lead_id.phone,
                'default_email_from': self.context_lead_id.email_from,
            })
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Log New Lead'),
            'res_model': 'crm.lead',
            'view_mode': 'form',
            'target': 'current',
            'context': context,
        }
    
    def action_log_activity_calendar(self):
        """
        Menu b: Log planned activity (in calendar)
        Opens the activity scheduling wizard.
        
        For clients: finds or creates an associated lead to attach the activity.
        For contacts/leads: uses the selected record directly.
        """
        self.ensure_one()
        
        # Determine which record to schedule activity on
        res_id = False
        res_model = 'crm.lead'
        lead_name = None
        
        # Priority: Contact > Lead > Client (via associated lead) > Context lead
        if self.contact_id:
            res_id = self.contact_id.id
            lead_name = self.contact_id.name
        elif self.lead_filter_id:
            res_id = self.lead_filter_id.id
            lead_name = self.lead_filter_id.name
        elif self.client_id:
            # Client selected - find or create associated lead
            lead = self._get_or_create_lead_for_client()
            if lead:
                res_id = lead.id
                lead_name = lead.name
        elif self.context_lead_id:
            res_id = self.context_lead_id.id
            lead_name = self.context_lead_id.name
        
        if res_id:
            # Open the mail.activity.schedule wizard
            return {
                'type': 'ir.actions.act_window',
                'name': _('Schedule Activity on: %s') % lead_name if lead_name else _('Schedule Activity'),
                'res_model': 'mail.activity.schedule',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'active_model': res_model,
                    'active_id': res_id,
                    'active_ids': [res_id],
                    'default_res_model': res_model,
                    'default_res_ids': [res_id],
                    'dialog_size': 'medium',
                    'followup_wizard_id': self.id,
                },
            }
        
        # If no specific record, show warning
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('No Record Selected'),
                'message': _('Please select a Client, Contact, or Lead first to schedule an activity.'),
                'type': 'warning',
                'sticky': False,
            }
        }

    
    def action_show_all_leads(self):
        """
        Menu c: Show all current leads (sorted by planned follow-up date)
        Selection shows lead follow-up form.
        """
        self.ensure_one()
        
        # Build domain
        domain = [('contact_status', '=', 'lead')]
        
        if self.client_id:
            domain.append(('partner_id', '=', self.client_id.id))
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('All Current Leads'),
            'res_model': 'crm.lead',
            'view_mode': 'list,form',
            'domain': domain,
            'context': {
                'search_default_my_activities': 1,
                'default_order': 'activity_date_deadline asc',
            },
            'target': 'current',
        }
    
    def action_show_all_activities(self):
        """
        Menu d: Show all current planned activities (sorted by date)
        Opens the crm.lead activity view showing leads with their activities.
        """
        self.ensure_one()
        
        # Domain for leads with activities
        domain = [('activity_ids', '!=', False)]
        
        # Filter by specific contact or lead if selected
        if self.contact_id:
            domain = [('id', '=', self.contact_id.id)]
        elif self.lead_filter_id:
            domain = [('id', '=', self.lead_filter_id.id)]
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('All Planned Activities'),
            'res_model': 'crm.lead',
            'view_mode': 'activity,list,form',
            'domain': domain,
            'target': 'current',
            'context': {'search_default_activities': 1},
        }
    
    def action_show_calendar(self):
        """
        Menu e: Show Calendar (displays all current leads and activities)
        Uses the custom calendar view with color-coding based on activity status.
        """
        self.ensure_one()
        
        # Base domain: show leads with calendar_date set (either next_action_at or activity date)
        domain = [('calendar_date', '!=', False)]
        
        # Filter by client if selected
        if self.client_id:
            domain.append(('partner_id', '=', self.client_id.id))
        
        # Filter by specific contact or lead if selected
        if self.contact_id:
            domain = [('id', '=', self.contact_id.id)]
        elif self.lead_filter_id:
            domain = [('id', '=', self.lead_filter_id.id)]
        
        # Get the custom calendar view
        calendar_view = self.env.ref('health_crm.view_crm_lead_followup_calendar', raise_if_not_found=False)
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Follow-up Calendar'),
            'res_model': 'crm.lead',
            'view_mode': 'calendar,list,form',
            'domain': domain,
            'view_id': calendar_view.id if calendar_view else False,
            'views': [
                (calendar_view.id if calendar_view else False, 'calendar'),
                (False, 'list'),
                (False, 'form'),
            ],
            'target': 'current',
        }
    
    def action_recent_client_followup(self):
        """
        Menu f: Recent Client Follow-up
        Shows leads with contact_status='booking' for follow-up.
        These are leads that have converted to bookings.
        """
        self.ensure_one()
        
        # Find leads that have been converted to bookings
        domain = [
            ('contact_status', '=', 'booking'),
        ]
        
        # If client selected, filter by partner
        if self.client_id:
            domain.append('|')
            domain.append(('partner_id', '=', self.client_id.id))
            domain.append(('patient_id', '=', self.client_id.id))
        
        # Get the custom list view with activity button
        list_view = self.env.ref(
            'health_crm.view_crm_lead_recent_followup_tree',
            raise_if_not_found=False
        )
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Recent Client Follow-up'),
            'res_model': 'crm.lead',
            'view_mode': 'list,form',
            'domain': domain,
            'views': [
                (list_view.id if list_view else False, 'list'),
                (False, 'form'),
            ],
            'context': {
                'search_default_booking': 1,
            },
            'target': 'current',
        }
    
    def action_visit_satisfaction_followup(self):
        """
        Menu g: Visit Satisfaction Follow-up (placeholder)
        Shows recent clients without follow-up phone calls.
        """
        self.ensure_one()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Coming Soon'),
                'message': _('Visit Satisfaction Follow-up feature is coming soon.'),
                'type': 'info',
                'sticky': False,
            }
        }
