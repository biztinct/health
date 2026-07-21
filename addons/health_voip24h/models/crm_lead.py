# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class CRMLead(models.Model):
    """Extend crm.lead with VoIP call tracking"""
    _inherit = 'crm.lead'

    voip_call_log_ids = fields.One2many(
        'voip.call.log',
        'lead_id',
        string='Call Logs',
    )
    voip_call_count = fields.Integer(
        string='Call Count',
        compute='_compute_voip_call_count',
    )
    voip_last_call_date = fields.Datetime(
        string='Last Call',
        compute='_compute_voip_call_count',
        store=True,
    )

    @api.depends('voip_call_log_ids.call_date')
    def _compute_voip_call_count(self):
        for lead in self:
            lead.voip_call_count = len(lead.voip_call_log_ids)
            lead.voip_last_call_date = max(lead.voip_call_log_ids.mapped('call_date')) if lead.voip_call_log_ids else False

    def action_view_call_logs(self):
        """View all call logs for this lead"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Call Logs - {self.name}',
            'res_model': 'voip.call.log',
            'view_mode': 'list,form,kanban',
            'domain': [('lead_id', '=', self.id)],
            'context': {'default_lead_id': self.id}
        }

    def action_call_lead(self):
        """Call the lead via VoIP"""
        self.ensure_one()

        # Get VoIP configuration
        config = self.env['voip.config'].get_active_config()
        if not config:
            raise UserError(_('VoIP is not configured. Please contact your administrator.'))

        # Check if call functionality is enabled
        if not config.enable_call_functionality:
            raise UserError(_('Call functionality is disabled. Please contact your administrator.'))

        if not config.enable_outgoing_calls:
            raise UserError(_('Outgoing calls are disabled. Please contact your administrator.'))

        # Determine phone number to call
        # NOTE: crm.lead has no `mobile` field in this Odoo 19 build
        phone_to_call = self.phone or self.partner_id.mobile or self.partner_id.phone
        if not phone_to_call:
            raise UserError(_('No phone number available for this lead.'))

        config.initiate_user_call(phone_to_call)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Call Initiated'),
                'message': _('Calling %s...') % phone_to_call,
                'type': 'info',
                'sticky': False,
            }
        }
