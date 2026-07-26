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

    **CC-F adopted this route rather than rewriting it.** Its verification was
    already the posture the rest of the channel framework was told to clone
    (ledger §5.61): raw bytes, HMAC-SHA256, ``compare_digest``, fail-closed on
    a missing secret, and a generic 200 for an unknown account so the route is
    not an oracle for which clinics exist here. What CC-F adds is routing —
    resolve the Channel Center connection, honour its ingest gate, and let
    real traffic prove the channel — and it adds no new public route.
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

        NOTE the payload shape above is the one this module was written
        against and is NOT confirmed against VoIP24h's own documentation,
        which is unreachable from outside Vietnam. Capturing a real event is
        item 5 of docs/strategy/voip24h-contract-capture.md.
        """
        try:
            from ..services.call_handler import process_call_event
            from ..models.voip_config import verify_voip_signature

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
            account_id = event_data.get('account_id')

            config = env['voip.config'].search([
                ('account_id', '=', account_id),
            ], limit=1)
            # A tenant who set Calls up in the Channel Center is routable even
            # before a legacy config exists.
            connection = env['voip.config']._resolve_channel_connection(account_id)

            if not config and not connection:
                # Do not leak which accounts exist — generic answer, 200 so
                # the provider stops retrying.
                _logger.warning('VoIP24h webhook for unknown account %r',
                                account_id)
                return self._json_response({'status': 'ignored'})

            signature = (
                request.httprequest.headers.get('X-Voip24h-Signature')
                or request.httprequest.headers.get('X-Signature')
            )

            if config:
                # Unchanged legacy gate — but only where the framework is not
                # the authority. A Center-managed connection carries its own
                # on/off switch (its state), and having to keep two of them in
                # step is how one silently wins.
                if not connection and not config.webhook_enabled:
                    return self._json_response(
                        {'status': 'ignored', 'message': 'Webhook disabled'})
                verified = config._verify_webhook_signature(raw_body, signature)
            else:
                secret = connection.sudo()._get_secret('provider_secret')
                verified = verify_voip_signature(secret, raw_body, signature)

            if not verified:
                _logger.warning('VoIP24h webhook signature mismatch for account %r',
                                account_id)
                return self._json_response(
                    {'status': 'error', 'message': 'Invalid signature'}, 403)

            # -- verified from here on --------------------------------------
            if config:
                if config._note_channel_event(event_data.get('event_type')) == 'ignored':
                    return self._json_response({'status': 'ignored'})
                result = process_call_event(env, event_data)
                return self._json_response(result)

            # No legacy config: record the traffic truth and say so plainly.
            # There is no call log to create — `voip.call.log` requires a
            # config — and inventing one here would hide that from the tenant.
            if not connection._may_ingest():
                env['care.channel.audit']._log(
                    'webhook_ignored', connection=connection,
                    detail='call event while %s' % connection.state)
                return self._json_response({'status': 'ignored'})
            connection._note_inbound()
            return self._json_response({'status': 'success'})

        except Exception as e:
            _logger.error('Webhook processing error: %s', e, exc_info=True)
            # Still return 200 OK to prevent webhook retry storms
            return self._json_response({'status': 'error', 'message': 'Internal error'})

    @staticmethod
    def _json_response(payload, status=200):
        return request.make_json_response(payload, status=status)
