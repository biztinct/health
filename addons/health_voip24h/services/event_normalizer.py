# -*- coding: utf-8 -*-
"""Turn what the phone system actually sends into something we can reason about.

Two feeds, both documented as GET, both with real ambiguities. This module's
job is to be exact about what arrived and honest about what it could not
understand — never to fill a gap with a plausible value. Three rules run
through all of it:

1. **An unknown value is quarantined, never defaulted.** The old parser
   defaulted an unknown call type to ``answered`` and a missing date to
   ``now``. Both invent a successful call that never happened.
2. **The raw value survives.** Every interpreted field keeps the original
   beside it, because the interpretation is ours and may be wrong.
3. **A number is not a duration and a duration is not a billing amount.**
   Numeric fields are bounded and a negative one is a data-quality flag.

Parser versions are stamped on every event so a later fix can be told apart
from the original reading.
"""

import hashlib
import json
import logging
import re
from datetime import datetime

from . import phone_ident
from .voip24h_api import parse_provider_datetime

_logger = logging.getLogger(__name__)

PARSER_FEED_A = 'A2'
PARSER_FEED_B = 'B2'

# Feed A: the five documented dispositions, and nothing else.
DISPOSITION_MAP = {
    'ANSWERED': ('answered', 'answered', 'completed'),
    'NO ANSWER': ('no_answer', 'missed', 'no_answer'),
    'NO_ANSWER': ('no_answer', 'missed', 'no_answer'),
    'MISSED': ('no_answer', 'missed', 'no_answer'),
    'BUSY': ('busy', 'busy', 'busy'),
    'FAILED': ('failed', 'failed', 'failed'),
}

# Feed A `type`. The vendor's field description misspells all three
# ("Outbount, Inbounf, Local"); the observed samples use the correct lowercase
# spellings, so those are what is matched — case-insensitively, and with the
# typos accepted rather than silently mapped to a default.
TYPE_MAP = {
    'inbound': 'incoming',
    'inbounf': 'incoming',
    'outbound': 'outgoing',
    'outbount': 'outgoing',
    'local': 'internal',
}

# Feed B states. Matched case-insensitively; the raw token is always kept.
# The vendor's own table labels Ring, Up and Hangup all as "Ring", which is
# plainly a copy-paste error, so the mapping below follows the state NAMES and
# the captures are what will confirm it (gate G05).
STATE_MAP = {
    'ring': 'ringing',
    'up': 'answered',
    'hangup': 'ended_pending_cdr',
    'cdr': 'final_cdr',
}

MAX_FIELD_LEN = 512
MAX_NUMERIC = 60 * 60 * 24 * 7   # a week of seconds: anything above is junk


def _text(value, limit=MAX_FIELD_LEN):
    if value is None:
        return ''
    if isinstance(value, (list, tuple)):
        value = value[0] if value else ''
    return str(value).strip()[:limit]


def _int_or_none(value):
    """A non-negative integer, or None. Zero and unknown are DIFFERENT.

    ``billsec=0`` on a NO ANSWER is a fact (nobody talked). A missing billsec
    is not zero and must never become one, because an analytics denominator
    built from invented zeros is wrong in a direction nobody notices.
    """
    text = _text(value, 32)
    if text == '':
        return None
    try:
        number = int(float(text))
    except (TypeError, ValueError):
        return None
    if number < 0 or number > MAX_NUMERIC:
        return None
    return number


def _fingerprint(config_id, feed, parts):
    """A hash of what the message MEANS.

    Deliberately excludes: the callback auth value, HTTP ordering and encoding
    differences, our receipt time, and the volatile token inside a recording
    URL. A provider that re-signs a recording link has not made a second call,
    and treating it as one would put a duplicate in the patient's timeline.
    """
    payload = json.dumps([config_id, feed, parts], sort_keys=True,
                         ensure_ascii=False, default=str)
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def _recording_urls(data):
    """The three (or four) distinct recording links, kept apart.

    ``play``, ``eplay`` and ``download`` are different endpoints and the
    sample carries a fourth, ``recording``, that the field table does not
    mention. None of them is a proven audio file — the sample's own filename
    ends ``.gsm`` and the URL may equally serve a playback wrapper — so they
    are recorded as candidates and validated later.
    """
    urls = {}
    for key in ('play', 'eplay', 'download', 'recording'):
        value = _text(data.get(key), 2048)
        if value:
            urls[key] = value
    return urls


# ----------------------------------------------------------------------
# Feed A — completed call records
# ----------------------------------------------------------------------

def normalise_final_record(config, data):
    """One completed-call delivery -> canonical dict.

    Never raises: an unreadable message becomes a quarantined event with a
    reason, which is a visible unresolved record rather than a lost one.
    """
    provider_cdr_id = _text(data.get('id'))
    callid = _text(data.get('callid'))
    delivery_id = _text(data.get('msgid'), 64)

    raw_type = _text(data.get('type'), 32)
    direction = TYPE_MAP.get(raw_type.lower())

    raw_disposition = _text(data.get('disposition'), 32).upper()
    raw_status = _text(data.get('status'), 64)
    mapped = DISPOSITION_MAP.get(raw_disposition)

    call_date, date_quality = parse_provider_datetime(
        _text(data.get('calldate'), 64), config.provider_timezone)

    billsec = _int_or_none(data.get('billsec'))
    duration = _int_or_none(data.get('duration'))

    src = _text(data.get('src'), 64)
    dst = _text(data.get('dst'), 64)
    did = _text(data.get('did'), 64)

    quality = []
    quarantine = None

    if not provider_cdr_id and not callid:
        quarantine = 'no_identifier'
    if direction is None:
        quarantine = quarantine or 'unknown_direction'
        quality.append('type=%s' % raw_type)
    if mapped is None:
        # Not a guess and not a failure: an unrecognised disposition becomes a
        # visible `unknown` outcome. `abandoned`, `voicemail` and `cancelled`
        # are NOT inferred from these five values — no supplied document
        # establishes them.
        quality.append('disposition=%s' % raw_disposition)
    if date_quality != 'ok':
        quarantine = quarantine or 'bad_call_date'
        quality.append('calldate=%s' % date_quality)

    # `disposition` is authoritative within this profile; a conflicting
    # `status` raises a flag rather than winning.
    if mapped and raw_status and raw_status.upper() != raw_disposition:
        quality.append('status/disposition disagree')

    # Derived, and labelled as derived. Not "verified queue waiting time".
    wait = None
    if duration is not None and billsec is not None and duration >= billsec:
        wait = duration - billsec
    elif duration is not None and billsec is not None:
        quality.append('duration < billsec')

    parties = phone_ident.resolve_parties(src, dst, direction or 'unknown')

    outcome, call_type, call_status = mapped or ('unknown', 'unknown', 'unknown')

    canonical = {
        'provider_cdr_id': provider_cdr_id,
        'callid': callid,
        'direction': direction or 'unknown',
        'raw_type': raw_type,
        'disposition_raw': raw_disposition,
        'status_raw': raw_status,
        'note': _text(data.get('note'), 1024),
        'outcome': outcome,
        'call_type': call_type,
        'call_status': call_status,
        'call_date': call_date,
        'src': src,
        'dst': dst,
        'did': did,
        'billsec': billsec,
        'duration': duration,
        'wait_seconds': wait,
        'external_peer': parties['peer'],
        'internal_extension': parties['internal_extension'],
        'recording_urls': _recording_urls(data),
        'data_quality': quality,
    }

    fingerprint = _fingerprint(config.id, 'cdr', {
        'cdr': provider_cdr_id,
        'callid': callid,
        'calldate': _text(data.get('calldate'), 64),
        'src': src,
        'dst': dst,
        'disposition': raw_disposition,
        'billsec': billsec,
        'duration': duration,
        'type': raw_type,
        # Recording URLs deliberately absent — see _fingerprint.
    })

    return {
        'fingerprint': fingerprint,
        'delivery_id': delivery_id,
        'canonical_type': 'final_cdr',
        'raw_state_token': 'cdr',
        'provider_time': call_date,
        'parser_version': PARSER_FEED_A,
        'quarantine_reason': quarantine,
        'data': canonical,
    }


# ----------------------------------------------------------------------
# Feed B — live state events with a nested final record
# ----------------------------------------------------------------------

def _decode_nested_cdr(value):
    """The nested ``cdr`` object, however it turns out to be encoded.

    V2's second setup declares ``cdr`` an Object and delivers by GET, and does
    not say how an object is encoded in a query string. Three encodings are
    accepted — JSON text, bracketed ``cdr[source]=…`` parameters (handled by
    the caller, which passes an already-assembled dict), and a plain
    ``key: value`` block — and anything else is reported as unreadable rather
    than half-parsed. Returns ``(dict, reason)``.
    """
    if value in (None, ''):
        return {}, None
    if isinstance(value, dict):
        return value, None
    text = _text(value, 4096)
    if text.startswith('{'):
        try:
            parsed = json.loads(text)
            return (parsed, None) if isinstance(parsed, dict) else ({}, 'cdr_not_object')
        except ValueError:
            return {}, 'cdr_unreadable'
    # `source: 916635328 destination: 0919840943 …` — the shape the vendor's
    # own table prints. Parsed only for the keys the document names.
    known = ('source', 'destination', 'starttime', 'answertime', 'endtime',
             'duration', 'billsec', 'disposition')
    found = {}
    for key in known:
        match = re.search(r'%s\s*[:=]\s*([^\s,;]+)' % key, text)
        if match:
            found[key] = match.group(1)
    if found:
        return found, None
    return {}, 'cdr_unreadable'


def normalise_state_event(config, data):
    """One live-event delivery -> canonical dict."""
    uniqueid = _text(data.get('uniqueid'))
    linkedid = _text(data.get('linkedid'))
    callid = _text(data.get('callid'))
    channel = _text(data.get('channel'), 128)
    extend = _text(data.get('extend'), 32)
    raw_state = _text(data.get('state'), 32)
    phone = _text(data.get('phone'), 64)
    raw_type = _text(data.get('type'), 32)

    canonical_state = STATE_MAP.get(raw_state.lower())
    direction = TYPE_MAP.get(raw_type.lower())

    quality = []
    quarantine = None
    if not uniqueid and not callid and not linkedid:
        quarantine = 'no_identifier'
    if canonical_state is None:
        # Persisted, visible, and inert. Never mapped to answered.
        quarantine = quarantine or 'unknown_state'
        quality.append('state=%s' % raw_state)

    nested, nested_reason = _decode_nested_cdr(data.get('cdr'))
    if nested_reason:
        quality.append(nested_reason)
        if canonical_state == 'final_cdr':
            quarantine = quarantine or nested_reason

    cdr = {}
    if nested:
        start, start_q = parse_provider_datetime(
            _text(nested.get('starttime'), 64), config.provider_timezone)
        answer, _answer_q = parse_provider_datetime(
            _text(nested.get('answertime'), 64), config.provider_timezone)
        end, _end_q = parse_provider_datetime(
            _text(nested.get('endtime'), 64), config.provider_timezone)
        billsec = _int_or_none(nested.get('billsec'))
        duration = _int_or_none(nested.get('duration'))
        raw_disposition = _text(nested.get('disposition'), 32).upper()
        mapped = DISPOSITION_MAP.get(raw_disposition)
        if raw_disposition and mapped is None:
            quality.append('disposition=%s' % raw_disposition)
        if start_q not in ('ok', 'missing'):
            quality.append('starttime=%s' % start_q)
        # Cross-check the stated durations against the stated times, and keep
        # BOTH. Rewriting one from the other would destroy the only evidence
        # that something is off.
        #
        # On the vendor's own sample the two are off by exactly one second in
        # both pairs (09:25:50 -> 09:28:00 is 130s against a stated 129;
        # 09:25:58 -> 09:28:00 is 122s against a stated billsec of 121). That
        # is consistent inclusive/exclusive rounding, not a contradiction, so
        # the tolerance below is 2 seconds. Flagging a one-second rounding on
        # every call would make the data-quality flag meaningless, which is
        # the fastest way to have it ignored.
        for label, stated, first, last in (
                ('duration', duration, start, end),
                ('talk time', billsec, answer, end)):
            if stated is None or not first or not last:
                continue
            measured = int((last - first).total_seconds())
            if abs(measured - stated) > 2:
                quality.append('%s %s vs measured %s'
                               % (label, stated, measured))
        cdr = {
            'source': _text(nested.get('source'), 64),
            'destination': _text(nested.get('destination'), 64),
            'start_time': start,
            'answer_time': answer,
            'end_time': end,
            'billsec': billsec,
            'duration': duration,
            'disposition_raw': raw_disposition,
            'outcome': (mapped or ('unknown', 'unknown', 'unknown'))[0],
            'call_type': (mapped or ('unknown', 'unknown', 'unknown'))[1],
            'call_status': (mapped or ('unknown', 'unknown', 'unknown'))[2],
        }
        src, dst = cdr['source'], cdr['destination']
    else:
        src = dst = ''

    if direction and (src or dst or phone):
        parties = phone_ident.resolve_parties(src or phone, dst or phone,
                                              direction)
    else:
        parties = {'external': phone or None, 'internal_extension': extend or None,
                   'peer': phone_ident.normalise_peer(phone)}

    canonical = {
        'uniqueid': uniqueid,
        'linkedid': linkedid,
        'callid': callid,
        'channel': channel,
        'extension_number': extend,
        'state': canonical_state or 'unknown',
        'raw_state': raw_state,
        'direction': direction or 'unknown',
        'raw_type': raw_type,
        'phone': phone,
        'cdr': cdr,
        'external_peer': parties['peer'],
        'internal_extension': parties['internal_extension'] or extend or None,
        'data_quality': quality,
    }

    provider_time = cdr.get('end_time') or cdr.get('start_time')

    fingerprint = _fingerprint(config.id, 'state', {
        'uniqueid': uniqueid,
        'linkedid': linkedid,
        'callid': callid,
        'state': raw_state.lower(),
        'extend': extend,
        'type': raw_type,
        'phone': phone,
        'cdr': {k: str(v) for k, v in sorted(cdr.items())} if cdr else None,
    })

    return {
        'fingerprint': fingerprint,
        'delivery_id': '',   # feed B carries no msgid
        'canonical_type': canonical_state or 'unknown',
        'raw_state_token': raw_state,
        'provider_time': provider_time,
        'parser_version': PARSER_FEED_B,
        'quarantine_reason': quarantine,
        'data': canonical,
    }


_REDACT_KEYS = ('auth', 'token', 'password', 'secret')


# ----------------------------------------------------------------------
# Storing and re-reading a normalised message
# ----------------------------------------------------------------------
#
# The inbox stores JSON, and JSON has no datetime. Writing them out with
# ``default=str`` and reading them back as strings is the quiet version of
# this bug: every string is truthy, every string compares, and the reducer's
# ``call_date + timedelta(...)`` blows up only on the branch that has a
# duration — so most messages look fine and a few crash. The keys below are
# converted explicitly in both directions.

_DATETIME_KEYS = ('call_date', 'start_time', 'answer_time', 'end_time')
_ISO = '%Y-%m-%d %H:%M:%S'


def _dt_out(value):
    return value.strftime(_ISO) if isinstance(value, datetime) else value


def _dt_in(value):
    if not value or isinstance(value, datetime):
        return value or None
    try:
        return datetime.strptime(str(value)[:19], _ISO)
    except ValueError:
        return None


def dump_normalised(normalised, payload=None):
    """Serialise a normalised message for the inbox. JSON-safe, lossless."""
    data = dict(normalised.get('data') or {})
    for key in _DATETIME_KEYS:
        if key in data:
            data[key] = _dt_out(data[key])
    if isinstance(data.get('cdr'), dict):
        cdr = dict(data['cdr'])
        for key in _DATETIME_KEYS:
            if key in cdr:
                cdr[key] = _dt_out(cdr[key])
        data['cdr'] = cdr
    body = {
        'fingerprint': normalised.get('fingerprint'),
        'delivery_id': normalised.get('delivery_id'),
        'canonical_type': normalised.get('canonical_type'),
        'raw_state_token': normalised.get('raw_state_token'),
        'provider_time': _dt_out(normalised.get('provider_time')),
        'parser_version': normalised.get('parser_version'),
        'quarantine_reason': normalised.get('quarantine_reason'),
        'data': data,
    }
    if payload is not None:
        body['payload'] = payload
    return json.dumps(body, ensure_ascii=False)


def load_normalised(text):
    """Read one back, with its datetimes as datetimes again."""
    try:
        body = json.loads(text or '{}')
    except ValueError:
        return {}
    if not isinstance(body, dict):
        return {}
    data = body.get('data') or {}
    for key in _DATETIME_KEYS:
        if key in data:
            data[key] = _dt_in(data[key])
    if isinstance(data.get('cdr'), dict):
        for key in _DATETIME_KEYS:
            if key in data['cdr']:
                data['cdr'][key] = _dt_in(data['cdr'][key])
    body['data'] = data
    body['provider_time'] = _dt_in(body.get('provider_time'))
    return body


# ----------------------------------------------------------------------
# Redaction
# ----------------------------------------------------------------------


def redact(data):
    """A storable copy: no auth values, recording links reduced to their host.

    Recording URLs carry single-use-looking query tokens. Keeping the host
    tells an operator where the media lives; keeping the token would put a
    credential in a table that many people can read.
    """
    out = {}
    for key, value in (data or {}).items():
        lowered = str(key).lower()
        if any(marker in lowered for marker in _REDACT_KEYS):
            out[key] = '***'
            continue
        if lowered in ('play', 'eplay', 'download', 'recording'):
            text = _text(value, 2048)
            match = re.match(r'^(https?://[^/]+/[^?]*)', text)
            out[key] = (match.group(1) + '?…') if match else '***'
            continue
        if isinstance(value, dict):
            out[key] = redact(value)
        else:
            out[key] = _text(value, 1024)
    return out
