# -*- coding: utf-8 -*-
"""Zalo OA inbound webhook — ONE route for the whole deployment.

Zalo's developer portal allows exactly one webhook URL per app (architecture
§13), so every tenant OA on this platform app arrives here and is routed by the
``oa_id`` in the payload. That forces the one place in this codebase where a
parse precedes a verification: we cannot know WHICH per-OA secret to check the
signature against until we know which OA the event is for.

The order is therefore, strictly:

1. read the RAW bytes (they are what Zalo signed — a ``type='jsonrpc'`` route
   re-serialises the JSON and the mac can never match: defect Z2/§5.61);
2. parse the JSON ONLY to lift ``oa_id`` out of it — nothing else in the body
   is trusted or used before step 4;
3. resolve the connection for that ``oa_id``;
4. verify ``sha256(app_id + raw + timestamp + per-OA secret)`` over the RAW
   bytes with THAT connection's secret;
5. only now escalate to ``su`` and ingest.

Every refusal in steps 1-4 is the same bodyless **403**: a missing header, an
unknown OA, a connection with no secret and a wrong mac are indistinguishable
to the caller. After verification the answer is always 200 — Zalo retries hard,
and a poisoned event must not become a retry storm.

Ingest deliberately feeds the LEGACY ``zalo.message`` pipeline (handover §2.3):
Care Command's timeline and ops send path read those rows today, and this phase
takes over the security boundary, not the storage.
"""
import json
import logging

from odoo import http
from odoo.http import request

from ..services.webhook_verify import verify_zalo

_logger = logging.getLogger(__name__)


class ZaloWebhookController(http.Controller):

    @staticmethod
    def _text(body='', status=200):
        return request.make_response(
            body, status=status,
            headers=[('Content-Type', 'text/plain; charset=utf-8')])

    @staticmethod
    def _oa_id(raw_body):
        """The routing key, and NOTHING else, out of an unverified body."""
        try:
            payload = json.loads(raw_body or b'{}')
        except ValueError:
            return None, None
        if not isinstance(payload, dict):
            return None, None
        oa_id = payload.get('oa_id')
        if not oa_id:
            recipient = payload.get('recipient')
            if isinstance(recipient, dict):
                oa_id = recipient.get('id')
        return (str(oa_id) if oa_id else None), payload

    @http.route('/care_channels/zalo/webhook', type='http', auth='public',
                methods=['POST'], csrf=False, save_session=False,
                website=False)
    def zalo_webhook(self, **kwargs):
        raw_body = request.httprequest.get_data()
        oa_id, payload = self._oa_id(raw_body)
        connection = request.env['care.channel.connection'].sudo()\
            ._find_for_resource('zalo', oa_id) if oa_id else None
        if not verify_zalo(connection, raw_body,
                           request.httprequest.headers):
            _logger.warning('care_channels: zalo webhook rejected')
            return self._text('', 403)

        # Verified: escalate only now, and answer 200 from here on.
        env = request.env(su=True)
        connection = connection.with_env(env)
        # GL-1: Zalo has no dashboard handshake — the FIRST verified event is
        # the proof that the operator pasted our one webhook URL correctly.
        # Logged once for the deployment: every later verified event would
        # otherwise fill the audit with the same fact. Dispatch is untouched.
        audit = env['care.channel.audit']
        if not audit.sudo().search_count(
                [('event', '=', 'webhook_handshake'), ('channel', '=', 'zalo')],
                limit=1):
            audit._log('webhook_handshake', connection=connection,
                       channel='zalo', detail='first verified zalo event')
        try:
            counts = env['care.channel.message']._dispatch_zalo(
                connection, payload)
            _logger.info('care_channels: zalo webhook %s', counts)
        except Exception:  # noqa: BLE001 — 200 after verification, always
            _logger.exception('care_channels: zalo webhook processing failed')
        return self._text('')
