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
    
    lead_id = fields.Many2one(
        'crm.lead',
        string='Search Contact',
        help='Search and select a contact/lead to view their follow-ups'
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
        """When client is selected, clear lead filter to avoid ambiguity"""
        if self.client_id:
            self.lead_id = False
    
    @api.onchange('lead_id')
    def _onchange_lead_id(self):
        """When lead is selected, clear client filter to avoid ambiguity"""
        if self.lead_id:
            self.client_id = False
    
    # =========================================================================
    # MENU ACTIONS
    # =========================================================================
    
    def action_log_lead_calendar(self):
        """
        Menu a: Log as Lead (in calendar)
        Opens a new lead form with calendar scheduling.
        """
        self.ensure_one()
        
        context = {
            'default_type': 'opportunity',
            'default_contact_status': 'lead',
        }
        
        # Pre-fill from selected client
        if self.client_id:
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
        After scheduling (or discarding), returns to this wizard.
        """
        self.ensure_one()
        
        # Determine which record to schedule activity on
        res_id = False
        res_model = 'crm.lead'
        
        if self.lead_id:
            res_id = self.lead_id.id
        elif self.context_lead_id:
            res_id = self.context_lead_id.id
        
        if res_id:
            # Open the mail.activity.schedule wizard
            # Use active_model and active_ids for proper wizard context
            # The activity wizard will open as a popup
            return {
                'type': 'ir.actions.act_window',
                'name': _('Schedule Activity'),
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
                    # Store wizard ID to return to after activity scheduling
                    'followup_wizard_id': self.id,
                },
            }
        
        # If no specific record, show warning
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('No Contact Selected'),
                'message': _('Please select a Contact/Lead first to schedule an activity.'),
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
        
        # Filter by specific lead if selected
        if self.lead_id:
            domain = [('id', '=', self.lead_id.id)]
        
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
        
        # Filter by specific lead if selected
        if self.lead_id:
            domain = [('id', '=', self.lead_id.id)]
        
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
        Shows recent clients with selected service.
        """
        self.ensure_one()
        
        # Find recent bookings that need follow-up
        # (completed in last 30 days without follow-up activity)
        thirty_days_ago = fields.Date.subtract(fields.Date.today(), days=30)
        
        domain = [
            ('state', '=', 'completed'),
            ('actual_end_datetime', '>=', thirty_days_ago),
        ]
        
        if self.client_id:
            domain.append(('patient_id', '=', self.client_id.id))
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Recent Clients for Follow-up'),
            'res_model': 'health.fieldservice.order',
            'view_mode': 'list,form',
            'domain': domain,
            'context': {
                'search_default_needs_followup': 1,
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
