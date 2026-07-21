# -*- coding: utf-8 -*-

import logging

from odoo import http, _
from odoo.exceptions import UserError
from odoo.http import request

_logger = logging.getLogger(__name__)


class VoIP24hAPIController(http.Controller):
    """
    Internal API controller for VoIP functionality.

    Provides endpoints for click-to-dial and frontend configuration.
    """

    @http.route('/voip24h/click_to_dial', type='jsonrpc', auth='user', methods=['POST'])
    def click_to_dial(self, phone_number, extension_id=None, **kwargs):
        """
        Initiate outbound call via click-to-dial.

        Args:
            phone_number: Destination phone number
            extension_id: Optional specific extension to use

        Returns:
            dict: {'status': 'success', 'call_id': '...'}
                  or {'error': 'error message'}
        """
        try:
            config = request.env['voip.config'].get_active_config()
            if not config:
                return {'error': _('No VoIP configuration found. Please contact your administrator.')}

            extension = None
            if extension_id:
                extension = request.env['voip.extension'].browse(int(extension_id)).exists()
                if not extension or extension.voip_config_id.id != config.id:
                    return {'error': _('Invalid extension selected')}

            # initiate_user_call enforces the master/outgoing switches and
            # falls back to the current user's assigned extension.
            result = config.initiate_user_call(phone_number, extension=extension)

            return {
                'status': 'success',
                'call_id': result.get('call_id') if isinstance(result, dict) else None,
                'message': _('Calling %s...') % phone_number,
            }

        except UserError as e:
            return {'error': str(e)}
        except Exception as e:
            _logger.error('Click-to-dial error: %s', e, exc_info=True)
            return {'error': _('Failed to initiate the call. Please contact your administrator.')}

    @http.route('/voip24h/get_config', type='jsonrpc', auth='user', methods=['POST'])
    def get_config(self, **kwargs):
        """Get VoIP configuration flags for the frontend"""
        try:
            config = request.env['voip.config'].get_active_config()

            if not config:
                return {'error': 'No configuration found'}

            return {
                'enable_call_functionality': config.enable_call_functionality,
                'enable_outgoing_calls': config.enable_outgoing_calls,
                'enable_incoming_call_popups': config.enable_incoming_call_popups,
            }

        except Exception as e:
            _logger.error('Get config error: %s', e, exc_info=True)
            return {'error': 'Unable to load VoIP configuration'}
