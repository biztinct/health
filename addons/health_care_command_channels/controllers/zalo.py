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

Every refusal in steps 1-4 is the same bodyless **200 with no ingestion**: a
missing header, an unknown OA, a connection with no secret and a wrong mac are
indistinguishable to the caller, and none of them reaches a single line of
ingest code. After verification the answer is also 200 — Zalo retries hard, and
a poisoned event must not become a retry storm.

The status code is 200 rather than 403 because Zalo's developer console
**refuses to save a webhook address that does not answer its unsigned probe
with 200** ("Your Webhook will only be established when it returns HTTP code
200 OK"). A 403 there is unrecoverable by construction: the probe carries no
``oa_id`` and no signature, so it can never verify, so the address can never be
saved, so no verified event can ever arrive to prove the address was pasted
correctly. The security boundary is unchanged and is where it always was —
``verify_zalo`` gates *ingestion*, never the status code — and a uniform 200
is, if anything, less of an oracle than a uniform 403. Refusals are logged at
WARNING and the first one writes a single ``webhook_probe`` audit row, so a
misconfigured secret is diagnosable here rather than in Zalo's console.

A ``GET`` on the same address answers a bodyless 200 too, so that pasting the
URL into a browser — the first thing every operator does — proves the address
is live instead of returning "Method Not Allowed".

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

    @staticmethod
    def _log_probe():
        """One ``webhook_probe`` row for the whole deployment, ever.

        Written on the REFUSAL path, which is the one place in this module
        that touches ``su`` before verifying anything — deliberately, and with
        nothing from the request in it: a constant event tag and a constant
        detail, no oa_id, no header, no byte of the body. It exists because
        the refusal is now a 200 and would otherwise be invisible to
        everything except the log: this row is how the Connection Center can
        say "Zalo reached this address" while the handshake row (step 4's
        gate) stays reserved for a genuinely VERIFIED event.

        Once-only, like the handshake row: a public route that appends per
        request is an unbounded-growth surface for anyone who finds the URL.
        """
        try:
            audit = request.env(su=True)['care.channel.audit']
            if audit.search_count(
                    [('event', '=', 'webhook_probe'), ('channel', '=', 'zalo')],
                    limit=1):
                return
            audit._log('webhook_probe', channel='zalo',
                       detail='unverified zalo request reached the webhook')
        except Exception:  # noqa: BLE001 — evidence must never break the 200
            _logger.exception('care_channels: zalo probe audit failed')

    @http.route('/care_channels/zalo/webhook', type='http', auth='public',
                methods=['GET'], csrf=False, save_session=False,
                website=False)
    def zalo_webhook_probe(self, **kwargs):
        """Liveness only. Zalo events are POSTs; this exists so that a browser
        (or any provider-side reachability check) sees the address answer
        instead of 405. It reads nothing, writes nothing and says nothing
        about which Official Accounts are connected here."""
        return self._text('OK')

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
            # 200, and NOT ONE LINE further: Zalo's console will not save an
            # address that answers its unsigned probe with anything else, and
            # the address is worthless unsaved. Nothing below this branch runs.
            _logger.warning('care_channels: zalo webhook not verified — '
                            'answered 200, ingested nothing')
            self._log_probe()
            return self._text('')

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
