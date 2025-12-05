# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request
import logging
import json

_logger = logging.getLogger(__name__)


class VoIP24hWebhookController(http.Controller):
    """
    Webhook receiver for VoIP24h real-time events.

    Handles incoming webhooks for call events (started, answered, ended, missed, etc.)
    """

    @http.route('/voip24h/webhook', type='json', auth='none', methods=['POST'], csrf=False)
    def handle_webhook(self, **kwargs):
        """
        Handle incoming webhook from VoIP24h.

        Expected payload:
        {
            'event_type': 'call.started|call.answered|call.ended|call.missed|recording.available',
            'account_id': 'voip24h_account_id',
            'call_data': {
                'call_id': '...',
                'direction': 'incoming|outgoing',
                'caller_number': '...',
                'called_number': '...',
                'start_time': '...',
                ...
            }
        }
        """
        try:
            from ..services.call_handler import process_call_event

            # Log webhook receipt
            _logger.info(f'Received VoIP24h webhook: {kwargs.get("event_type")}')

            # Process the event using call_handler service
            result = process_call_event(request.env, kwargs)

            # Always return success response quickly
            return result

        except Exception as e:
            _logger.error(f'Webhook processing error: {e}', exc_info=True)
            # Still return 200 OK to prevent webhook retries
            return {'status': 'error', 'message': str(e)}
