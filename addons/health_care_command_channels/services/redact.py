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

# key=value / key: value pairs whose VALUE is credential-ish.
_KV_RE = re.compile(
    r'(?i)\b([\w-]*(?:token|secret|key|code|signature|password|authorization)'
    r'[\w-]*)\s*[=:]\s*\S+')

# Everything after a URL's '?' is opaque and frequently carries code/state.
_URL_QS_RE = re.compile(r'(?i)\b(https?://\S+?)\?\S*')

# "Authorization: Bearer <token>" survives the key=value rule (the value is a
# scheme name, the secret is the NEXT word), so it needs its own pass.
_BEARER_RE = re.compile(r'(?i)\b(?:bearer|basic|token)\s+\S+')

_REDACTED = '<redacted>'


def redact(text):
    """Return ``text`` with credential-shaped values stripped and truncated.

    Falsy input returns ``False`` (so it can be assigned straight to a Char
    field). Non-str input is coerced with ``str()``.
    """
    if not text:
        return False
    if not isinstance(text, str):
        text = str(text)
    # Order matters: the key=value rule would otherwise eat
    # "Authorization: Bearer" and leave the actual token behind.
    text = _URL_QS_RE.sub(r'\1?' + _REDACTED, text)
    text = _BEARER_RE.sub(_REDACTED, text)
    text = _KV_RE.sub(_REDACTED, text)
    if len(text) > MAX_LEN:
        text = text[:MAX_LEN - 1] + '…'
    return text
