# -*- coding: utf-8 -*-
"""Meta (WhatsApp Cloud API + Messenger) inbound webhooks.

§5.61 posture throughout, cloned from health_voip24h and deliberately NOT from
health_zalo:

* ``type='http'`` — Meta signs the RAW request bytes, and only a raw route
  preserves them (a jsonrpc route re-serialises the JSON and the HMAC can never
  match);
* the raw body is read FIRST, verified, and only then does the request escalate
  to ``su``;
* a missing platform app, a missing secret or a missing header REJECTS —
  fail-closed, no exceptions;
* after verification the answer is always 200, whatever the payload contained,
  so a poisoned event cannot trigger an infinite Meta retry storm;
* responses are generic: nothing tells a caller whether a phone number, page or
  tenant exists here.

Both channels share one platform app, hence one signature check per request
BEFORE tenant routing: the signature proves the sender is Meta, not which
tenant the payload belongs to.
"""
import json
import logging

from odoo import http
from odoo.http import request

from ..services.webhook_verify import meta_challenge, verify_meta

_logger = logging.getLogger(__name__)

META_CHANNELS = ('whatsapp', 'fb')


class MetaWebhookController(http.Controller):

    @staticmethod
    def _text(body='', status=200):
        return request.make_response(
            body, status=status,
            headers=[('Content-Type', 'text/plain; charset=utf-8')])

    @http.route('/care_channels/meta/<string:channel>/webhook', type='http',
                auth='public', methods=['GET'], csrf=False,
                save_session=False, website=False)
    def meta_handshake(self, channel, **kwargs):
        """Meta's subscription handshake.

        ``hub.mode`` / ``hub.verify_token`` / ``hub.challenge`` contain DOTS,
        so they never arrive as Python kwargs — they must be read off
        ``request.httprequest.args``.
        """
        if channel not in META_CHANNELS:
            return self._text('', 403)
        args = request.httprequest.args
        app = request.env['channel.platform.app'].sudo()._get_for_provider('meta')
        challenge = meta_challenge(app, args.get('hub.mode'),
                                   args.get('hub.verify_token'),
                                   args.get('hub.challenge'))
        if not challenge:
            _logger.info('care_channels: meta handshake refused (%s)', channel)
            return self._text('', 403)
        return self._text(challenge)

    @http.route('/care_channels/meta/<string:channel>/webhook', type='http',
                auth='public', methods=['POST'], csrf=False,
                save_session=False, website=False)
    def meta_webhook(self, channel, **kwargs):
        raw_body = request.httprequest.get_data()
        if channel not in META_CHANNELS:
            return self._text('', 403)
        app = request.env['channel.platform.app'].sudo()._get_for_provider('meta')
        signature = request.httprequest.headers.get('X-Hub-Signature-256')
        if not verify_meta(app, raw_body, signature):
            _logger.warning('care_channels: meta webhook signature rejected (%s)',
                            channel)
            return self._text('', 403)

        # Verified: escalate only now, and answer 200 from here on.
        env = request.env(su=True)
        try:
            payload = json.loads(raw_body or b'{}')
        except ValueError:
            _logger.warning('care_channels: meta webhook with invalid JSON (%s)',
                            channel)
            return self._text('')
        if not isinstance(payload, dict):
            return self._text('')
        try:
            counts = env['care.channel.message']._dispatch_meta(channel, payload)
            _logger.info('care_channels: meta %s webhook %s', channel, counts)
        except Exception:  # noqa: BLE001 — 200 after verification, always
            _logger.exception('care_channels: meta webhook processing failed (%s)',
                              channel)
        return self._text('')
