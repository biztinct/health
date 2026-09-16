# -*- coding: utf-8 -*-
"""The transport: hand one call-back on to the customer it belongs to.

It posts over the loopback interface with the customer's hostname in a ``Host:``
header, exactly the way ``biz.tenants._probe`` asks this machine for a
customer's page and exactly the way the Meta relay forwards a message batch — so
the request never leaves the box, never depends on DNS or a certificate, and
measures the application rather than the internet.

THE PATH IS FORWARDED BYTE FOR BYTE, and that is the whole security design of
this module. A v3 call-back address is ``/voip24h/v3/<feed>/<receiver>/<token>``
and the token in it IS the credential. Passing it through untouched means:

* the platform never stores, encrypts, decrypts, mints or rotates a customer's
  token — it only ever handles one in flight, in memory, for the length of one
  request;
* the customer's own route does the constant-time token check it already does,
  against its own database, and would refuse anything else. The boundary is
  enforced at the destination rather than trusted at the source.

What counts as delivered
------------------------

**Any answer the customer's system actually gave is the supplier's answer**, and
it is passed back verbatim — 200 accepted, 200 duplicate, 400 malformed, 403
denied. Those are verdicts, not failures, and re-sending them would not change
them. Only "the customer's system could not be reached or broke" — a network
error, a timeout, or a 5xx — becomes a queued hand-off to try again.

That rule is why a rotated token does not silently fill this platform's queue
with dead rows carrying a stale credential: the customer answers 403, the
supplier is told 403, and the operator sees the reason on the customer's row.
"""
import logging

import requests

_logger = logging.getLogger(__name__)

# A worker must never hang on a slow customer. The supplier's own client
# timeout is unknown, so a slow customer becomes a queued hand-off rather than
# a blocked call-back address.
RELAY_TIMEOUT = 8

# Where the hand-offs go. Loopback by default; the parameter exists for the
# tests and for the day the fleet outgrows one machine.
FORWARD_BASE_PARAM = 'voip_relay.forward_base'

USER_AGENT = 'carejiox-voip-relay/1'

# How a call-back was classified.
LOCAL = 'local'
TENANT = 'tenant'
UNKNOWN = 'unknown'

# Answers that mean "could not be reached or broke", and nothing else.
RETRYABLE_STATUS = (500, 502, 503, 504, 507, 508)


class RelayError(Exception):
    """A hand-off that did not land. Its str() is stored redacted, never raw."""


def forward_base(env):
    """Where a hand-off is posted. Loopback unless a parameter says otherwise."""
    base = (env['ir.config_parameter'].sudo().get_param(FORWARD_BASE_PARAM)
            or '').strip().rstrip('/')
    if base:
        return base
    return 'http://127.0.0.1:%s' % env['biz.tenants']._http_port()


def forward(env, host, delivery):
    """Hand one call-back to one customer's own system.

    ``delivery`` is the dict :func:`capture` built: method, path, query string,
    body and content type, all exactly as the supplier sent them.

    Returns ``(status, body_text)`` for any answer the customer's system gave —
    including a refusal, which is a verdict and must reach the supplier. Raises
    :class:`RelayError` only when there was no answer to pass on.
    """
    url = '%s%s' % (forward_base(env), delivery['path'])
    query = delivery.get('query') or ''
    if query:
        url = '%s?%s' % (url, query)
    headers = {
        'Host': host,
        'X-Forwarded-Proto': 'https',
        'User-Agent': USER_AGENT,
    }
    content_type = delivery.get('content_type')
    body = delivery.get('body') or b''
    if content_type and body:
        headers['Content-Type'] = content_type
    try:
        response = requests.request(
            delivery.get('method') or 'GET', url,
            data=body or None, headers=headers, timeout=RELAY_TIMEOUT,
            allow_redirects=False)
    except requests.RequestException as exc:
        raise RelayError('network error: %s' % type(exc).__name__) from exc
    status = getattr(response, 'status_code', 0)
    if not status or status in RETRYABLE_STATUS:
        # The body is not read and not stored: a customer's error page is their
        # business, and it is exactly the kind of text that carries things we
        # must never keep here.
        raise RelayError('HTTP %s' % (status or 'no answer'))
    # A verdict. The body is small and ours by contract ({"status": "..."}),
    # but it is still capped rather than trusted.
    return status, (response.text or '')[:512]


def capture(http_request):
    """Everything about one call-back that has to survive to the destination.

    Read ONCE, here, before anything else touches the request — ``get_data``
    caches in werkzeug, so the local path can still read the same bytes if this
    call-back turns out to belong to the platform's own clinic after all.
    """
    return {
        'method': http_request.method,
        'path': http_request.path,
        'query': (http_request.query_string or b'').decode('latin-1'),
        'body': http_request.get_data() if http_request.method != 'GET' else b'',
        'content_type': (http_request.content_type or '') or None,
    }


def peek_hotline(http_request):
    """The hotline a completed call record arrived on, or ''.

    Deliberately defensive and deliberately shallow. It reads ONE optional
    value and must never raise, never re-decode, and never evaluate anything:
    the full decode, with its duplicate-key refusals, belongs to whichever
    system ends up owning this call — not to the signpost pointing at it.

    Live ringing events carry no hotline. That is not a gap to fill with a
    guess; it is the documented reason hotline routing covers completed call
    records only.
    """
    try:
        if http_request.method == 'GET':
            value = http_request.args.get('did') or ''
        else:
            content_type = (http_request.content_type or '').split(';')[0].strip()
            if content_type != 'application/json':
                value = http_request.form.get('did') or ''
            else:
                import json
                parsed = json.loads((http_request.get_data() or b'{}')
                                    .decode('utf-8') or '{}')
                if not isinstance(parsed, dict):
                    return ''
                value = parsed.get('did') or ''
        return str(value).strip()[:64]
    except Exception:  # noqa: BLE001 — a signpost may never break a call-back
        return ''
