# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)


class VoIP24hAPIController(http.Controller):
    """
    Internal API controller for VoIP functionality.

    Provides endpoints for click-to-dial, call logs, and statistics.
    """

    @http.route('/voip24h/click_to_dial', type='json', auth='user', methods=['POST'])
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
            from ..services.voip24h_api import VoIP24hAPI

            # Get active configuration
            config = request.env['voip.config'].get_active_config()
            if not config:
                return {'error': 'No VoIP configuration found. Please contact your administrator.'}

            # Check if outgoing calls are enabled
            if not config.can_make_outgoing_calls():
                return {'error': 'Outgoing calls are disabled. Please contact your administrator.'}

            # Initialize API client
            api = VoIP24hAPI(config)

            # Get extension to use
            if extension_id:
                extension = request.env['voip.extension'].browse(extension_id)
                if not extension or extension.voip_config_id.id != config.id:
                    return {'error': 'Invalid extension selected'}
                from_extension = extension.extension_number
            else:
                # Use user's default extension
                user = request.env.user
                if user.voip_extension_id and user.voip_extension_id.voip_config_id.id == config.id:
                    from_extension = user.voip_extension_id.extension_number
                else:
                    return {'error': 'No extension configured for current user. Please contact your administrator.'}

            # Initiate the call via API
            result = api.initiate_call(from_extension, phone_number)

            if result.get('success'):
                _logger.info(f'Call initiated from {from_extension} to {phone_number}')
                return {
                    'status': 'success',
                    'call_id': result.get('call_id'),
                    'message': f'Calling {phone_number}...'
                }
            else:
                return {'error': result.get('error', 'Failed to initiate call')}

        except Exception as e:
            _logger.error(f'Click-to-dial error: {e}', exc_info=True)
            return {'error': str(e)}

    @http.route('/voip24h/get_config', type='json', auth='user', methods=['POST'])
    def get_config(self, **kwargs):
        """Get VoIP configuration for frontend"""
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
            _logger.error(f'Get config error: {e}', exc_info=True)
            return {'error': str(e)}
