# -*- coding: utf-8 -*-
"""The platform's call-back addresses: the ones the phone supplier calls for
everybody.

These replace the two v3 receivers ON THIS SYSTEM ONLY. A customer system never
has this module installed, so the routing map it serves is the parent's,
unchanged — and even if it were installed there, the customer list does not
exist there, the routing table stays empty, and every call falls straight
through to the parent.

The posture is the parent's, kept deliberately:

* ``type='http'`` and both GET and POST, because the supplier demonstrates GET
  and offers POST and we accept whichever really arrives;
* the cheap refusals — too big, too fast — happen BEFORE any lookup, so a
  delivery storm cannot be turned into database work;
* an address nobody answers to gets the parent's flat refusal, identical to the
  one a wrong token gets, so this route is not an oracle for which clinics live
  behind this platform.

What is new is one step in the middle: before the platform tries to handle a
call itself, it asks who the call belongs to, and hands it over if the answer is
somebody else.
"""
import logging

from odoo import http
from odoo.http import request

from odoo.addons.health_voip24h.controllers.webhook import (
    MAX_BODY_BYTES, MAX_QUERY_CHARS, VoIP24hReceiverController, _answer,
    _rate_limited,
)

from ..services import relay

_logger = logging.getLogger(__name__)


class VoipRelayReceiverController(VoIP24hReceiverController):

    @http.route('/voip24h/v3/cdr/<string:receiver_id>/<string:token>',
                type='http', auth='public', methods=['GET', 'POST'],
                csrf=False, save_session=False, sitemap=False)
    def receive_cdr(self, receiver_id, token, **kwargs):
        handed = self._relay('cdr', receiver_id)
        if handed is not None:
            return handed
        return super().receive_cdr(receiver_id, token, **kwargs)

    @http.route('/voip24h/v3/events/<string:receiver_id>/<string:token>',
                type='http', auth='public', methods=['GET', 'POST'],
                csrf=False, save_session=False, sitemap=False)
    def receive_events(self, receiver_id, token, **kwargs):
        handed = self._relay('state', receiver_id)
        if handed is not None:
            return handed
        return super().receive_events(receiver_id, token, **kwargs)

    # ------------------------------------------------------------------

    def _relay(self, feed, receiver_id):
        """Hand this call to the customer it belongs to, or return None.

        None means "not somebody else's" — the parent then handles it exactly as
        it did before this module existed, refusals included. Never raises: a
        relay that breaks must degrade into the system that was already there,
        not into a 500 that makes the phone supplier re-send everything.
        """
        http_request = request.httprequest

        # --- the same cheap refusals, before any lookup -----------------
        # Repeated from the parent on purpose. Without them the platform would
        # do the routing work, open a database and build a hand-off for a body
        # the destination is going to refuse for its size anyway.
        if len(http_request.query_string or b'') > MAX_QUERY_CHARS:
            return _answer(413, {'status': 'too_large'})
        if (http_request.content_length or 0) > MAX_BODY_BYTES:
            return _answer(413, {'status': 'too_large'})
        if _rate_limited(receiver_id):
            _logger.warning('voip relay: rate limit hit (address %s)',
                            receiver_id)
            return _answer(429, {'status': 'slow_down'})

        try:
            # Read the request ONCE, here, before anything else touches it.
            delivery = relay.capture(http_request)
            hotline = relay.peek_hotline(http_request) if feed == 'cdr' else ''
            env = request.env(su=True)
            kind, tenant = env['voip.relay.router']._classify(
                receiver_id, hotline)
        except Exception:  # noqa: BLE001 — degrade to the system underneath
            _logger.exception('voip relay: routing failed (address %s) — the '
                              'call is handled locally', receiver_id)
            return None

        if kind != relay.TENANT or not tenant:
            # Ours, or nobody's. Either way the parent answers — and for
            # nobody's that is the flat refusal it already gives.
            return None

        try:
            status, body = env['voip.relay.router']._hand_over(
                tenant, feed, delivery)
        except Exception:  # noqa: BLE001 — never a 500 to the supplier
            _logger.exception('voip relay: handing a %s call-back to %s failed',
                              feed, tenant.slug)
            return _answer(503, {'status': 'unavailable'})
        return self._passthrough(status, body)

    @staticmethod
    def _passthrough(status, body):
        """The customer's own answer, given back to the phone supplier.

        A dict came from this module (a queued hand-off); a string came from the
        customer's system and is passed on as the JSON it already is, so that
        ``accepted``, ``duplicate``, ``quarantined`` and ``denied`` keep meaning
        exactly what they mean when the supplier calls a clinic directly.
        """
        if isinstance(body, dict):
            return _answer(status, body)
        text = (body or '').strip() or '{}'
        return request.make_response(
            text, status=status,
            headers=[('Content-Type', 'application/json; charset=utf-8'),
                     ('Content-Length', str(len(text.encode('utf-8'))))])
