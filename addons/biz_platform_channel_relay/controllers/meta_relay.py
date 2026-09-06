# -*- coding: utf-8 -*-
"""The platform's Meta webhook: the one address Meta calls for everybody.

It replaces the POST half of the customer-side route ON THIS SYSTEM ONLY (this
module never reaches a customer). The posture is the parent's, unchanged:

* ``type='http'`` — Meta signs the RAW bytes and only a raw route keeps them;
* the raw body is read FIRST, the signature checked, and only then does the
  request escalate to ``su``;
* an unknown channel, a missing secret or a wrong signature is the same
  bodyless 403;
* **from the moment the signature checks out the answer is 200**, whatever
  happens downstream. A non-2xx makes Meta redeliver the whole batch for every
  customer in it and, sustained, gets the application's Messenger webhook
  switched off for all of them — so failures become queued deliveries here,
  never error codes to Meta.

The GET handshake is NOT overridden: Meta's dashboard check is answered by the
parent, against this system's own verify token, and still writes its one
``webhook_handshake`` audit row.
"""
import json
import logging

from odoo import http
from odoo.http import request

from odoo.addons.health_care_command_channels.controllers.meta import (
    META_CHANNELS, MetaWebhookController,
)
from odoo.addons.health_care_command_channels.services.webhook_verify import (
    verify_meta,
)

_logger = logging.getLogger(__name__)


class RelayMetaWebhookController(MetaWebhookController):

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
            _logger.warning('channel relay: meta webhook signature rejected '
                            '(%s)', channel)
            return self._text('', 403)

        # Verified: escalate only now, and answer 200 from here on.
        env = request.env(su=True)
        try:
            payload = json.loads(raw_body or b'{}')
        except ValueError:
            _logger.warning('channel relay: meta webhook with invalid JSON '
                            '(%s)', channel)
            return self._text('')
        if not isinstance(payload, dict):
            return self._text('')
        try:
            counts = env['channel.relay.router']._route_meta(
                channel, raw_body, payload)
            _logger.info('channel relay: meta %s webhook %s', channel, counts)
        except Exception:  # noqa: BLE001 — 200 after verification, always
            _logger.exception('channel relay: meta webhook processing failed '
                              '(%s)', channel)
        return self._text('')
