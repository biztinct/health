# -*- coding: utf-8 -*-

from odoo import models, api, _


class MailActivityScheduleInherit(models.TransientModel):
    """
    Extend mail.activity.schedule to redirect to calendar after saving
    when opened from Follow-up Activities wizard.
    """
    _inherit = 'mail.activity.schedule'

    def action_schedule_activities(self):
        """
        Override to redirect to calendar view after scheduling activity
        when opened from Follow-up Activities wizard.
        """
        # Call parent method first
        result = super().action_schedule_activities()
        
        # Check if we came from the Follow-up Activities wizard
        if self.env.context.get('followup_wizard_id'):
            # Get the custom calendar view
            calendar_view = self.env.ref(
                'health_crm.view_crm_lead_followup_calendar', 
                raise_if_not_found=False
            )
            
            # Return action to open calendar view
            return {
                'type': 'ir.actions.act_window',
                'name': _('Follow-up Calendar'),
                'res_model': 'crm.lead',
                'view_mode': 'calendar,list,form',
                'domain': [('calendar_date', '!=', False)],
                'view_id': calendar_view.id if calendar_view else False,
                'views': [
                    (calendar_view.id if calendar_view else False, 'calendar'),
                    (False, 'list'),
                    (False, 'form'),
                ],
                'target': 'current',
            }
        
        return result
