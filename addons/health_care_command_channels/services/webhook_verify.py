# -*- coding: utf-8 -*-
"""Webhook verifiers — every one of them fails CLOSED (ledger §5.61).

Cloned from ``health_voip24h/models/voip_config.py:422-442``, which is the good
precedent in this repository. The bad one is ``health_zalo``'s webhook, which
accepts events when no secret is configured, verifies re-serialised JSON
instead of the raw bytes, and answers 200 either way — three ways to accept a
forged message. Nothing in this file may repeat any of them.

The rules, applied uniformly:

* the secret is read server-side (never from the request);
* a missing app, missing secret or missing header is a REJECT, never a pass;
* comparison is always ``hmac.compare_digest`` over the RAW request bytes;
* the functions return plain booleans and never raise — a verifier that throws
  on garbage input is a denial-of-service surface on a public route.

Meta's app secret is a PLATFORM-plane credential (``channel.platform.app``):
one signature check per request, BEFORE any tenant routing, because the
signature proves the sender is Meta, not which tenant the payload belongs to.
"""
import hashlib
import hmac
import logging

_logger = logging.getLogger(__name__)

VERIFY_TOKEN_KEY = 'verify_token'


def _app_secret(platform_app):
    if not platform_app:
        return ''
    try:
        return platform_app._get_secret() or ''
    except Exception:  # noqa: BLE001 — a corrupt secret must reject, not 500
        _logger.warning('Platform app %s: secret could not be read',
                        platform_app.id)
        return ''


def verify_meta(platform_app, raw_body, header):
    """``X-Hub-Signature-256`` over the raw bytes, HMAC-SHA256(app secret)."""
    secret = _app_secret(platform_app)
    if not secret:
        _logger.warning('Meta webhook rejected: no platform app secret '
                        'configured (signature validation cannot run)')
        return False
    if not header:
        return False
    provided = header.strip().lower()
    if provided.startswith('sha256='):
        provided = provided[len('sha256='):]
    expected = hmac.new(secret.encode(), raw_body or b'',
                        hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, provided)


def meta_challenge(platform_app, mode, token, challenge):
    """Meta's GET handshake. Returns the challenge string, or None to refuse.

    Unconfigured (no platform app, no verify token) refuses: an endpoint that
    echoes any challenge lets anyone point their own Meta app at our inbox.
    """
    if not platform_app:
        return None
    expected = platform_app.get_extra(VERIFY_TOKEN_KEY) or ''
    if not expected or not token or not challenge:
        return None
    if mode != 'subscribe':
        return None
    if not hmac.compare_digest(str(expected), str(token)):
        return None
    return str(challenge)


def verify_telegram(connection, path_secret, header_secret):
    """Telegram: the URL path secret is the routing credential; the
    ``X-Telegram-Bot-Api-Secret-Token`` header echoes the same value.

    Both are compared with ``compare_digest``. The header is checked WHEN
    PRESENT (phase6 T52 semantics): Telegram only sends it for a webhook we
    registered with ``secret_token``, and the unguessable 32-byte path secret
    is the credential either way — but a header that is present and WRONG is a
    hard reject.
    """
    if not connection:
        return False
    expected = connection.sudo().webhook_path_secret or ''
    if not expected or not path_secret:
        return False
    if not hmac.compare_digest(str(expected), str(path_secret)):
        return False
    if header_secret and not hmac.compare_digest(str(expected),
                                                 str(header_secret)):
        return False
    return True
