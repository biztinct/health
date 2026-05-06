from odoo import models, fields, api, _


class ContactActionWizard(models.TransientModel):
    _name = 'health.contact.action.wizard'
    _description = 'Contact Action Selector'

    lead_id = fields.Many2one('crm.lead', required=True)
    lead_name = fields.Char(related='lead_id.name', readonly=True)

    def action_new_booking(self):
        return self.lead_id.action_convert_to_booking()

    def action_escalate(self):
        return self.lead_id.action_escalate_contact()

    def action_consultation(self):
        return self.lead_id.action_escalate_consultation()

    def action_send_message(self):
        return self.lead_id.action_send_message()

    def action_log_activity(self):
        return self.lead_id.action_schedule_follow_up()

    def action_notes(self):
        return self.lead_id.action_log_note()

    def action_mark_spam(self):
        return self.lead_id.action_mark_contact_spam()

    def action_other(self):
        return {
            'type': 'ir.actions.client',
            'tag': 'health_landing_lead_hub',
            'params': {
                'lead_id': self.lead_id.id,
                'lead_name': self.lead_id.name,
            },
        }
