# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request
import logging
import json
import hmac
import hashlib

_logger = logging.getLogger(__name__)


class ZaloWebhookController(http.Controller):
    """
    Controller for handling Zalo webhook callbacks.

    Receives incoming message notifications and OAuth callbacks from Zalo.
    """

    @http.route('/zalo/webhook', type='jsonrpc', auth='public', methods=['POST'], csrf=False)
    def webhook_handler(self, **kwargs):
        """
        Handle incoming webhook events from Zalo.

        Zalo sends POST requests with JSON data for message notifications.
        Must respond within 2 seconds to avoid timeouts.
        """
        try:
            # Get request data
            event_data = request.httprequest.get_json()

            if not event_data:
                _logger.warning('Received empty webhook data')
                return {'error': 0, 'message': 'OK'}

            # Log webhook event
            _logger.info(f'Received Zalo webhook: {event_data.get("event_name")}')

            # Validate webhook signature (if configured)
            if not self._validate_webhook_signature(event_data):
                _logger.error('Invalid webhook signature')
                return {'error': -1, 'message': 'Invalid signature'}

            # Process event asynchronously to respond quickly (<2s requirement)
            # Queue the processing to avoid timeout
            request.env['zalo.message.handler'].sudo().with_delay().process_webhook_event(event_data)

            # Respond immediately to Zalo
            return {'error': 0, 'message': 'OK'}

        except Exception as e:
            _logger.error(f'Webhook handler error: {e}', exc_info=True)
            # Still return success to avoid retries
            return {'error': 0, 'message': 'OK'}

    @http.route('/zalo/webhook/test', type='http', auth='public', methods=['GET'], csrf=False)
    def webhook_test(self, **kwargs):
        """
        Test endpoint for webhook verification.

        Zalo may send GET requests to verify the webhook URL.
        """
        return "Webhook endpoint is active"

    @http.route('/zalo/oauth/callback', type='http', auth='public', methods=['GET'], csrf=False)
    def oauth_callback(self, **kwargs):
        """
        Handle OAuth callback from Zalo.

        After user authorizes the app, Zalo redirects here with authorization code.
        """
        try:
            # Get authorization code from URL parameters
            code = kwargs.get('code')
            state = kwargs.get('state')
            error = kwargs.get('error')

            if error:
                _logger.error(f'OAuth error: {error}')
                return request.render('health_zalo.oauth_error', {
                    'error': error,
                    'error_description': kwargs.get('error_description', 'Unknown error'),
                })

            if not code:
                _logger.error('No authorization code received')
                return request.render('health_zalo.oauth_error', {
                    'error': 'no_code',
                    'error_description': 'No authorization code received',
                })

            # Find config by state token
            config = request.env['zalo.config'].sudo().search([
                ('oauth_state', '=', state),
            ], limit=1)

            if not config:
                _logger.error(f'Invalid OAuth state: {state}')
                return request.render('health_zalo.oauth_error', {
                    'error': 'invalid_state',
                    'error_description': 'Invalid OAuth state token (CSRF protection)',
                })

            # Exchange code for tokens
            config.action_exchange_code_for_token(code)

            # Success - redirect to Zalo configuration
            return request.redirect('/web#id=%d&view_type=form&model=zalo.config' % config.id)

        except Exception as e:
            _logger.error(f'OAuth callback error: {e}', exc_info=True)
            return request.render('health_zalo.oauth_error', {
                'error': 'exception',
                'error_description': str(e),
            })

    def _validate_webhook_signature(self, event_data):
        """
        Validate webhook signature using HMAC SHA-256.

        Args:
            event_data: Webhook event data

        Returns:
            Boolean indicating if signature is valid
        """
        # Get active config
        config = request.env['zalo.config'].sudo().get_active_config()

        if not config or not config.webhook_secret:
            # If no secret configured, skip validation
            _logger.warning('No webhook secret configured, skipping signature validation')
            return True

        # Get signature from headers
        signature = request.httprequest.headers.get('X-Zalo-Signature')

        if not signature:
            _logger.warning('No signature in webhook request')
            return True  # Allow for now (Zalo may not send signature)

        # Compute expected signature
        payload = json.dumps(event_data, separators=(',', ':'))
        expected_signature = hmac.new(
            config.webhook_secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        # Compare signatures
        is_valid = hmac.compare_digest(signature, expected_signature)

        if not is_valid:
            _logger.error(f'Signature mismatch: got={signature}, expected={expected_signature}')

        return is_valid
