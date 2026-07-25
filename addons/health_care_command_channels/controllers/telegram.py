# -*- coding: utf-8 -*-
"""Telegram inbound webhook.

Telegram has no signature: the credential is the unguessable secret in the URL
path (registered with ``setWebhook``), echoed back in the
``X-Telegram-Bot-Api-Secret-Token`` header. ONE stored value serves both, so a
rotation revokes the URL and the header together.

Same §5.61 posture as the Meta route: raw http, verify before ``su``, generic
answers, 200 after verification.
"""
import json
import logging

from odoo import http
from odoo.http import request

from ..services.webhook_verify import verify_telegram

_logger = logging.getLogger(__name__)


class TelegramWebhookController(http.Controller):

    @staticmethod
    def _text(body='', status=200):
        return request.make_response(
            body, status=status,
            headers=[('Content-Type', 'text/plain; charset=utf-8')])

    @http.route('/care_channels/telegram/webhook/<string:path_secret>',
                type='http', auth='public', methods=['POST'], csrf=False,
                save_session=False, website=False)
    def telegram_webhook(self, path_secret, **kwargs):
        raw_body = request.httprequest.get_data()
        connection = request.env['care.channel.connection'].sudo().search([
            ('channel', '=', 'telegram'),
            ('webhook_path_secret', '=', path_secret),
        ], limit=1)
        header = request.httprequest.headers.get(
            'X-Telegram-Bot-Api-Secret-Token')
        if not verify_telegram(connection, path_secret, header):
            # Unknown secret and wrong header are the same answer: the route is
            # not an oracle for guessing live webhook paths.
            _logger.warning('care_channels: telegram webhook rejected')
            return self._text('', 403)

        env = request.env(su=True)
        try:
            payload = json.loads(raw_body or b'{}')
        except ValueError:
            _logger.warning('care_channels: telegram webhook with invalid JSON')
            return self._text('')
        if not isinstance(payload, dict):
            return self._text('')
        try:
            counts = env['care.channel.message']._dispatch_connection(
                connection.with_env(env), payload)
            _logger.info('care_channels: telegram webhook %s', counts)
        except Exception:  # noqa: BLE001 — 200 after verification, always
            _logger.exception('care_channels: telegram webhook processing failed')
        return self._text('')
