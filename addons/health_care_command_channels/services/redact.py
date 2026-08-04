# -*- coding: utf-8 -*-
"""The ONE redaction helper (architecture §5.5, handover §4.5).

Every free-text detail string persisted or returned by this module flows
through :func:`redact` — audit rows, readiness-check details,
``last_error_redacted``, cron logs. Grep rule for review: no model in this
module may assign a caller-supplied string to a ``*_redacted``/``detail``
field without calling it.

It is deliberately blunt (a denylist plus a hard truncation) because the input
is arbitrary provider text: an unknown provider error body is far more likely
to carry a bearer token than to carry information we need.
"""
import re

MAX_LEN = 300

# key=value / key: value pairs whose VALUE is credential-ish. Keys and values
# may be quoted — provider error bodies are JSON ({"access_token": "xyz"}), and
# the closing quote must not break the match (CC-A review finding #2).
_KV_RE = re.compile(
    r'(?i)["\']?\b([\w-]*(?:token|secret|key|code|signature|password|authorization)'
    r'[\w-]*)\b["\']?\s*[=:]\s*["\']?[^\s"\',}]+["\']?')

# Everything after a URL's '?' is opaque and frequently carries code/state.
_URL_QS_RE = re.compile(r'(?i)\b(https?://\S+?)\?\S*')

# "Authorization: Bearer <token>" survives the key=value rule (the value is a
# scheme name, the secret is the NEXT word), so it needs its own pass.
_BEARER_RE = re.compile(r'(?i)\b(?:bearer|basic|token)\s+\S+')

# Telegram carries the bot token in the URL PATH (`/bot<id>:<secret>/method`),
# so neither the query-string rule nor key=value catches it — and a requests
# network error stringifies the full URL (CC-B review finding).
_TG_BOT_RE = re.compile(r'(?i)/bot\d+:[\w-]+')

_REDACTED = '<redacted>'


def redact(text, max_len=MAX_LEN):
    """Return ``text`` with credential-shaped values stripped and truncated.

    Falsy input returns ``False`` (so it can be assigned straight to a Char
    field). Non-str input is coerced with ``str()``.

    ``max_len`` exists for the one caller that stores evidence rather than a
    one-line detail — ``care.contact.capture.raw_payload`` keeps up to 8 KB of
    the original event so an operator can see what actually arrived. It changes
    only the truncation: the SAME denylist runs either way, so a longer cap can
    never let a credential through that the default would have caught.
    """
    if not text:
        return False
    if not isinstance(text, str):
        text = str(text)
    # Order matters: the key=value rule would otherwise eat
    # "Authorization: Bearer" and leave the actual token behind.
    text = _URL_QS_RE.sub(r'\1?' + _REDACTED, text)
    text = _TG_BOT_RE.sub('/bot' + _REDACTED, text)
    text = _BEARER_RE.sub(_REDACTED, text)
    text = _KV_RE.sub(_REDACTED, text)
    if len(text) > max_len:
        text = text[:max_len - 1] + '…'
    return text
