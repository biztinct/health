# -*- coding: utf-8 -*-
"""Retired Zalo routes — the 410 shim (CC-D).

These three URLs are kept, deliberately, and answer **410 Gone**. Deleting the
controller would give 404s that Zalo (and any monitoring pointed at them) would
keep retrying; a 410 says "this endpoint is permanently gone" and the retry
dies fast.

What replaced them, and why the old ones could not simply be patched:

* ``/zalo/webhook`` was a ``type='jsonrpc'`` route (defect Z2) — the HMAC was
  computed over RE-SERIALISED JSON, which can never match a signature taken
  over the raw request bytes — and it failed OPEN three separate ways: no
  config, no secret and no header all returned "valid". On top of that it
  dispatched through ``with_delay()`` with no queue_job addon installed, so
  the ``AttributeError`` was swallowed and **every inbound event was dropped
  while the caller was told 200 OK** (defect Z3). The replacement is
  ``/care_channels/zalo/webhook`` in health_care_command_channels: a raw
  ``type='http'`` route that verifies ``sha256(app_id + raw_body + timestamp +
  per-OA secret)`` over the exact bytes, fails closed on every missing piece,
  and ingests synchronously.
* ``/zalo/webhook/test`` was an unauthenticated liveness echo — a free
  "is Health19 here" probe with nothing behind it.
* ``/zalo/oauth/callback`` was the PKCE-less legacy OAuth flow (defect Z6:
  no code challenge, a state bound to nobody that lived forever, an
  authorization code persisted permanently). It is replaced by
  ``/channel_hub/oauth/callback/zalo``, whose state is hashed, single-use and
  ten minutes old at most.

Re-enabling the legacy behaviour is a code change (revert this file), which is
exactly the friction it should have.
"""
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

GONE = ('This Zalo endpoint has been retired. Configure Zalo from Care '
        'Command Setup → Channel Center.')


class ZaloWebhookController(http.Controller):
    """Every handler answers 410 with no detail: a retired endpoint must not
    describe the deployment behind it."""

    @staticmethod
    def _gone():
        return request.make_response(
            GONE, status=410,
            headers=[('Content-Type', 'text/plain; charset=utf-8')])

    @http.route('/zalo/webhook', type='http', auth='public',
                methods=['POST', 'GET'], csrf=False, save_session=False,
                website=False)
    def webhook_handler(self, **kwargs):
        _logger.info('health_zalo: legacy /zalo/webhook called — 410')
        return self._gone()

    @http.route('/zalo/webhook/test', type='http', auth='public',
                methods=['GET'], csrf=False, save_session=False, website=False)
    def webhook_test(self, **kwargs):
        return self._gone()

    @http.route('/zalo/oauth/callback', type='http', auth='public',
                methods=['GET'], csrf=False, save_session=False, website=False)
    def oauth_callback(self, **kwargs):
        _logger.info('health_zalo: legacy /zalo/oauth/callback called — 410')
        return self._gone()
