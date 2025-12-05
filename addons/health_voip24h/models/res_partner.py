# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    """Extend res.partner with VoIP fields and functionality"""
    _inherit = 'res.partner'

    # VoIP Integration
    voip_call_log_ids = fields.One2many(
        'voip.call.log',
        'partner_id',
        string='Call Logs',
    )
    voip_call_count = fields.Integer(
        string='Call Count',
        compute='_compute_voip_stats',
    )
    voip_last_call_date = fields.Datetime(
        string='Last Call Date',
        compute='_compute_voip_stats',
        store=True,
    )
    voip_total_talk_time = fields.Integer(
        string='Total Talk Time (minutes)',
        compute='_compute_voip_stats',
    )

    # Preferred Contact Method
    voip_preferred_number = fields.Char(
        string='Preferred Call Number',
        help='Preferred number for outgoing calls',
    )
    voip_do_not_call = fields.Boolean(
        string='Do Not Call',
        default=False,
        help='Flag to prevent outgoing calls',
    )

    @api.depends('voip_call_log_ids')
    def _compute_voip_stats(self):
        for partner in self:
            logs = partner.voip_call_log_ids
            partner.voip_call_count = len(logs)
            if logs:
                partner.voip_last_call_date = max(logs.mapped('call_date'))
                partner.voip_total_talk_time = sum(logs.mapped('talk_duration_seconds')) // 60
            else:
                partner.voip_last_call_date = False
                partner.voip_total_talk_time = 0

    def action_view_call_logs(self):
        """View all call logs for this contact"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Call Logs - {self.name}',
            'res_model': 'voip.call.log',
            'view_mode': 'list,form,kanban',
            'domain': [('partner_id', '=', self.id)],
            'context': {'default_partner_id': self.id}
        }

    def action_call_voip(self):
        """Initiate VoIP call (click-to-dial)"""
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

        # Check do not call flag
        if self.voip_do_not_call:
            raise UserError(_('This contact is marked as "Do Not Call".'))

        # Determine phone number to call
        phone_to_call = self.voip_preferred_number or self.mobile or self.phone
        if not phone_to_call:
            raise UserError(_('No phone number available for this contact.'))

        # TODO: Implementation for click-to-dial
        # Call VoIP24h API to initiate call
        # from ..services.voip24h_api import VoIP24hAPI
        # api = VoIP24hAPI(config)
        # result = api.initiate_call(extension, phone_to_call)

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
