# -*- coding: utf-8 -*-

from odoo import models, api


class MailActivity(models.Model):
    _inherit = 'mail.activity'

    @api.model_create_multi
    def create(self, vals_list):
        """Override to auto-update CRM lead fields when an activity is scheduled.
        
        When an activity is logged/scheduled on a CRM lead:
        - Sets contact_outcome to 'pending_follow_up'
        - Sets lead_followup_required to True
        - Sets next_follow_up_date to the activity's due date
        
        These changes cascade via the existing write() logic to:
        - Set contact_status to 'lead'
        """
        activities = super().create(vals_list)
        
        # Find activities that were created for crm.lead
        lead_activities = activities.filtered(
            lambda a: a.res_model == 'crm.lead'
        )
        
        for activity in lead_activities:
            try:
                lead = self.env['crm.lead'].browse(activity.res_id)
                if lead.exists():
                    update_vals = {}
                    # Set contact outcome to pending follow-up
                    if lead.contact_outcome != 'pending_follow_up':
                        update_vals['contact_outcome'] = 'pending_follow_up'
                    # Set lead follow-up required
                    if not lead.lead_followup_required:
                        update_vals['lead_followup_required'] = True
                    # Set next follow-up date from activity due date
                    # date_deadline is Date, next_follow_up_date is Datetime
                    if activity.date_deadline:
                        from datetime import datetime
                        followup_datetime = datetime.combine(
                            activity.date_deadline, datetime.min.time()
                        )
                        update_vals['next_follow_up_date'] = followup_datetime
                    
                    if update_vals:
                        lead.write(update_vals)
            except Exception:
                # Don't let activity creation fail due to lead update issues
                pass
        
        return activities
