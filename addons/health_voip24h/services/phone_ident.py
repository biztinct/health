# -*- coding: utf-8 -*-
"""Telephone numbers: three representations, kept apart on purpose.

A call carries up to four different strings that all look like "the number",
and collapsing them is how an outbound call ends up filed under the clinic's
own trunk:

* **raw** — exactly what the phone system sent. Stored, never rewritten.
* **matching key** — the ``0xxxxxxxxx`` national form the rest of health19
  already matches partners on (``health_base.phone_utils.normalize_vn_phone``).
  This representation is NOT changed by this module: Care Command,
  ``care.conversation.phone_normalized`` and every existing partner match
  depend on it.
* **E.164** — ``+84xxxxxxxxx``, added here for cross-system correlation. It is
  derived only once the country has actually been established, so a number we
  cannot place stays unresolved rather than being forced through a
  Vietnam-only helper.
* **dial string** — what the SDK/PBX is given. Kept separate because the PBX
  may want the national form even where E.164 is the correct identity.

Extensions are not numbers. ``531`` is an extension and must stay one; turning
it into ``0000000531`` or matching it against a patient would be worse than
leaving it unresolved.
"""

import re

from odoo.addons.health_base.models.phone_utils import normalize_vn_phone

# An extension on this PBX: short, digits only. The vendor's own examples use
# three digits (``206``, ``531``). Six is a generous ceiling; anything longer
# is treated as a telephone number.
EXTENSION_MAX_LEN = 6

# Reserved caller-ID strings that mean "no number", not a number.
ANONYMOUS_TOKENS = frozenset({
    'anonymous', 'unknown', 'restricted', 'private', 'unavailable',
    'withheld', 'hidden', 'null', 'none', '', 'x', 'anonymous@anonymous.invalid',
})

KIND_EXTENSION = 'extension'
KIND_NATIONAL = 'national'
KIND_INTERNATIONAL = 'international'
KIND_ANONYMOUS = 'anonymous'
KIND_UNKNOWN = 'unknown'


def classify(value):
    """What kind of thing is this string? Never raises."""
    text = (value or '').strip()
    if not text or text.lower() in ANONYMOUS_TOKENS:
        return KIND_ANONYMOUS
    digits = re.sub(r'\D', '', text)
    if not digits:
        return KIND_ANONYMOUS
    if text.startswith('+') and not digits.startswith('84'):
        return KIND_INTERNATIONAL
    if len(digits) <= EXTENSION_MAX_LEN and not text.startswith('+'):
        return KIND_EXTENSION
    if digits.startswith('84') or len(digits) in (9, 10):
        return KIND_NATIONAL
    if len(digits) > 10:
        return KIND_INTERNATIONAL
    return KIND_UNKNOWN


def matching_key(value):
    """The existing ``0xxxxxxxxx`` partner-matching key, or None.

    Wraps the shared helper in the try/except the ledger requires (§5.15): it
    RAISES on a non-empty invalid number, and inbound caller-ID is routinely
    invalid.
    """
    if classify(value) != KIND_NATIONAL:
        return None
    try:
        return normalize_vn_phone(value)
    except Exception:  # noqa: BLE001 — falsy-on-invalid is the contract here
        return None


def to_e164(value, country_code='VN'):
    """``+84xxxxxxxxx``, or None when the country cannot be established.

    Only ever derived for a number the national helper already accepted, and
    only when the connection's country is the one the helper knows. An
    international string that already starts with ``+`` is kept as-is after
    whitespace and separators are stripped.
    """
    text = (value or '').strip()
    kind = classify(text)
    if kind == KIND_INTERNATIONAL and text.startswith('+'):
        cleaned = '+' + re.sub(r'\D', '', text)
        return cleaned if len(cleaned) >= 8 else None
    if kind != KIND_NATIONAL or country_code != 'VN':
        return None
    key = matching_key(text)
    if not key:
        return None
    return '+84' + key[1:]


def normalise_peer(value, country_code='VN'):
    """Everything we can honestly say about one external party.

    Returns a dict, never raises, and never invents a number::

        {'raw', 'kind', 'key', 'e164', 'is_anonymous', 'is_extension'}
    """
    raw = (value or '').strip()
    kind = classify(raw)
    return {
        'raw': raw,
        'kind': kind,
        'key': matching_key(raw) if kind == KIND_NATIONAL else None,
        'e164': to_e164(raw, country_code) if kind in (
            KIND_NATIONAL, KIND_INTERNATIONAL) else None,
        'is_anonymous': kind == KIND_ANONYMOUS,
        'is_extension': kind == KIND_EXTENSION,
    }


def dial_string(value, country_code='VN'):
    """What to hand the SDK.

    The vendor's own example dials ``0368251254`` — the national form — so
    that is what a Vietnamese number becomes. An extension is dialled as
    typed. An international number keeps its ``+``. Returns None when there is
    nothing safe to dial.
    """
    peer = normalise_peer(value, country_code)
    if peer['is_anonymous']:
        return None
    if peer['is_extension']:
        return re.sub(r'\D', '', peer['raw']) or None
    if peer['key']:
        return peer['key']
    if peer['e164']:
        return peer['e164']
    return None


def resolve_parties(src, dst, direction, country_code='VN'):
    """Which side is the customer, and which is us.

    * incoming — the external party is the source,
    * outgoing — the external party is the destination,
    * internal — neither side is a customer, and no patient conversation is
      ever created from one.
    """
    if direction == 'incoming':
        external, internal = src, dst
    elif direction == 'outgoing':
        external, internal = dst, src
    else:
        return {'external': None, 'internal_extension': None,
                'peer': normalise_peer('', country_code)}
    peer = normalise_peer(external, country_code)
    internal_peer = normalise_peer(internal, country_code)
    return {
        'external': external,
        'internal_extension': (internal_peer['raw']
                               if internal_peer['is_extension'] else None),
        'peer': peer,
    }
