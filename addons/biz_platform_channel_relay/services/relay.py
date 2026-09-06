# -*- coding: utf-8 -*-
"""The two things the relay does to a verified Meta batch: split it, ship it.

``split_payload`` is a PURE function — no environment, no records, no I/O — so
the boundary that decides which clinic's messages leave this machine can be
tested on its own, exhaustively, without a database. That is deliberate: it is
the one function in this module whose failure would ship one clinic's patient
messages to another clinic's server.

``forward`` is the transport. It posts over the loopback interface with the
customer's hostname in a ``Host:`` header, exactly the way
``biz.tenants._probe`` asks this machine for a customer's page — so the request
never leaves the box, never depends on DNS or a certificate, and measures the
application rather than the internet.
"""
import logging

import requests

_logger = logging.getLogger(__name__)

# A worker must never hang on a slow customer. Meta's own client timeout is
# short and we answer it 200 regardless of what happens here, so a slow
# customer becomes a queued delivery rather than a blocked webhook.
RELAY_TIMEOUT = 8

# Where the forwards go. Loopback by default; the parameter exists for the
# tests and for the day the fleet outgrows one machine.
FORWARD_BASE_PARAM = 'channel_relay.forward_base'

WEBHOOK_PATH = '/care_channels/meta/%s/webhook'

USER_AGENT = 'carejiox-relay/1'

# Bucket kinds returned by the classifier handed to ``split_payload``.
LOCAL = 'local'
UNKNOWN = 'unknown'
TENANT = 'tenant'


class RelayError(Exception):
    """A forward that did not land. Its str() is stored redacted, never raw."""


def split_payload(channel, payload, classify):
    """Cut one verified Meta batch into per-owner sub-payloads.

    ``classify(resource_external_id)`` returns ``(kind, slug)`` where ``kind``
    is ``'local'``, ``'unknown'`` or ``'tenant'`` and ``slug`` is the customer's
    short name for the last of those (``None`` otherwise). A tuple rather than a
    bare string because a customer's short name is ``[a-z0-9]{1,40}`` and could
    itself be the word ``local``.

    Returns ``{'local': sub | None, 'unknown': sub | None,
    'tenants': {slug: sub}}`` where ``sub`` is
    ``{'object': <the batch's object>, 'entry': [...]}`` carrying ONLY the
    entries (Messenger) or the entries reduced to only the changes (WhatsApp)
    that belong to that owner.

    Rules, all of them load-bearing:

    * an entry whose every change belongs to somebody else is DROPPED — an
      empty ``changes`` list would tell a customer that an event they own
      arrived when none did;
    * an entry with no routable id is dropped, because nothing can own it (the
      same entries ``_meta_resource_ids`` already ignores);
    * the input payload is never mutated: every entry that survives is a copy,
      so the caller can still capture the original.
    """
    out = {LOCAL: None, UNKNOWN: None, 'tenants': {}}
    buckets = {}
    for entry in (payload or {}).get('entry') or []:
        if not isinstance(entry, dict):
            continue
        if channel == 'fb':
            resource_id = entry.get('id')
            if resource_id is None:
                continue
            key = classify(str(resource_id))
            buckets.setdefault(key, []).append(_copy(entry))
            continue
        # WhatsApp addresses us per CHANGE, so one entry can carry two
        # customers' numbers and must be cut in half.
        per_owner = {}
        for change in entry.get('changes') or []:
            if not isinstance(change, dict):
                continue
            metadata = (change.get('value') or {}).get('metadata') or {}
            phone_number_id = metadata.get('phone_number_id')
            if not phone_number_id:
                continue
            per_owner.setdefault(classify(str(phone_number_id)), []).append(
                _copy(change))
        for key, changes in per_owner.items():
            rebuilt = {k: _copy(v) for k, v in entry.items() if k != 'changes'}
            rebuilt['changes'] = changes
            buckets.setdefault(key, []).append(rebuilt)

    for (kind, slug), entries in buckets.items():
        sub = {'object': (payload or {}).get('object'), 'entry': entries}
        if kind == TENANT:
            out['tenants'][slug] = sub
        else:
            out[kind] = sub
    return out


def _copy(value):
    """A deep-enough copy that the caller's payload cannot be edited by us."""
    if isinstance(value, dict):
        return {k: _copy(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_copy(v) for v in value]
    return value


def forward_base(env):
    """Where a forward is posted. Loopback unless a parameter says otherwise."""
    base = (env['ir.config_parameter'].sudo().get_param(FORWARD_BASE_PARAM)
            or '').strip().rstrip('/')
    if base:
        return base
    return 'http://127.0.0.1:%s' % env['biz.tenants']._http_port()


def forward(env, tenant, channel, body, signature):
    """POST one customer's share to that customer's own webhook route.

    ``body`` is bytes and ``signature`` the ``sha256=…`` header computed over
    exactly those bytes with the platform application's secret — the customer's
    route recomputes it and would refuse anything else, which is what keeps the
    boundary honest rather than trusted.

    Returns True, or raises :class:`RelayError`. **A 403 means the customer's
    copy of the secret is missing or stale** — it is queued like any other
    failure, and the credentials push fixes it before the retry lands.
    """
    url = '%s%s' % (forward_base(env), WEBHOOK_PATH % channel)
    headers = {
        'Host': tenant.host,
        'Content-Type': 'application/json',
        'X-Hub-Signature-256': signature,
        'X-Forwarded-Proto': 'https',
        'User-Agent': USER_AGENT,
    }
    try:
        response = requests.post(url, data=body, headers=headers,
                                 timeout=RELAY_TIMEOUT)
    except requests.RequestException as exc:
        raise RelayError('network error: %s' % exc) from exc
    status = getattr(response, 'status_code', 0)
    if not status or status >= 300:
        # The body is not read and not stored: a customer's error page is
        # their business, and it is exactly the kind of text that carries
        # things we must never keep here.
        raise RelayError('HTTP %s' % status)
    return True
