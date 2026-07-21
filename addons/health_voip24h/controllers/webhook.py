# -*- coding: utf-8 -*-

import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class VoIP24hWebhookController(http.Controller):
    """
    Webhook receiver for VoIP24h real-time events.

    Handles incoming webhooks for call events (started, answered, ended,
    missed, recording.available).

    VoIP24h posts plain JSON (no JSON-RPC envelope), so this is a raw
    ``type='http'`` route: parse the body ourselves, validate the HMAC
    signature against the raw bytes, and answer with plain JSON.
    """

    @http.route('/voip24h/webhook', type='http', auth='public',
                methods=['POST'], csrf=False, save_session=False)
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

            raw_body = request.httprequest.get_data()
            try:
                event_data = json.loads(raw_body) if raw_body else {}
            except ValueError:
                return self._json_response({'status': 'error', 'message': 'Invalid JSON'}, 400)

            if not isinstance(event_data, dict) or not event_data:
                return self._json_response({'status': 'error', 'message': 'Empty payload'}, 400)

            _logger.info('Received VoIP24h webhook: %s', event_data.get('event_type'))

            # Public route → escalate deliberately; every lookup below is
            # scoped by the account_id carried in the payload.
            env = request.env(su=True)

            config = env['voip.config'].search([
                ('account_id', '=', event_data.get('account_id')),
            ], limit=1)
            if not config:
                # Do not leak which accounts exist — generic answer, 200 so
                # the provider stops retrying.
                _logger.warning('VoIP24h webhook for unknown account %r',
                                event_data.get('account_id'))
                return self._json_response({'status': 'ignored'})

            if not config.webhook_enabled:
                return self._json_response({'status': 'ignored', 'message': 'Webhook disabled'})

            signature = (
                request.httprequest.headers.get('X-Voip24h-Signature')
                or request.httprequest.headers.get('X-Signature')
            )
            if not config._verify_webhook_signature(raw_body, signature):
                _logger.warning('VoIP24h webhook signature mismatch for %s', config.name)
                return self._json_response(
                    {'status': 'error', 'message': 'Invalid signature'}, 403)

            result = process_call_event(env, event_data)
            return self._json_response(result)

        except Exception as e:
            _logger.error('Webhook processing error: %s', e, exc_info=True)
            # Still return 200 OK to prevent webhook retry storms
            return self._json_response({'status': 'error', 'message': 'Internal error'})

    @staticmethod
    def _json_response(payload, status=200):
        return request.make_json_response(payload, status=status)
