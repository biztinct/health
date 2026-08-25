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
import json
import logging
import time

_logger = logging.getLogger(__name__)

VERIFY_TOKEN_KEY = 'verify_token'

# Zalo signs `app_id + raw_body + timestamp + oa_secret` with a plain SHA-256
# (NOT an HMAC — the secret is concatenated, not keyed). The per-OA secret is
# tenant material from the app's portal page; the app id is platform material.
ZALO_SIGNATURE_HEADER = 'X-ZEvent-Signature'
# Older Zalo examples described the timestamp as a header.  The current OA
# webhook contract puts it in the signed JSON body instead.  Keep the header
# name only as a compatibility fallback for events which pre-date that change.
ZALO_TIMESTAMP_HEADER = 'X-ZEvent-Timestamp'
# Replay window (architecture §7.5). Widened, never disabled, through
# `channel_hub.zalo_webhook_skew_seconds` — a deployment whose clock drifts is
# an ops problem, not a reason to ship a code change.
ZALO_DEFAULT_SKEW_SECONDS = 300
ZALO_SKEW_PARAM = 'channel_hub.zalo_webhook_skew_seconds'


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


def _zalo_timestamp_ok(env, raw_timestamp):
    """A timestamp inside the replay window, in seconds OR milliseconds.

    Zalo sends epoch milliseconds; the header is part of the signed string, so
    an attacker cannot move it — but a captured, still-valid request could
    otherwise be replayed forever.
    """
    try:
        value = int(str(raw_timestamp).strip())
    except (TypeError, ValueError):
        return False
    if value > 10 ** 11:          # milliseconds
        value = value // 1000
    try:
        skew = int(env['ir.config_parameter'].sudo().get_param(
            ZALO_SKEW_PARAM) or ZALO_DEFAULT_SKEW_SECONDS)
    except (TypeError, ValueError):
        skew = ZALO_DEFAULT_SKEW_SECONDS
    skew = max(skew, 60)
    return abs(time.time() - value) <= skew


def _zalo_signed_timestamp(raw_body, headers):
    """Return the timestamp Zalo appends to the signature input.

    Current OA webhook payloads carry a top-level ``timestamp`` property and
    send only ``X-ZEvent-Signature`` as a signature-related header.  Because
    the JSON bytes themselves are part of the digest, using that property for
    the replay check does not weaken the boundary.  The header fallback keeps
    compatibility with the older contract without letting a header override a
    timestamp that is present in the signed body.
    """
    try:
        payload = json.loads(raw_body or b'{}')
    except (TypeError, ValueError):
        payload = None
    if isinstance(payload, dict) and 'timestamp' in payload:
        return str(payload.get('timestamp') or '').strip()
    headers = headers or {}
    return str(headers.get(ZALO_TIMESTAMP_HEADER)
               or headers.get(ZALO_TIMESTAMP_HEADER.lower()) or '').strip()


def verify_zalo(connection, raw_body, headers, platform_app=None):
    """``X-ZEvent-Signature: mac=<hex>`` over the RAW request bytes.

    ``mac = sha256(app_id + raw_body + timestamp + per_OA_webhook_secret)``
    (handover §2.6). Every missing piece — no platform app, no per-OA secret,
    no header, no timestamp, a stale timestamp, a wrong mac — returns False.
    The caller answers all of them with the same bodyless 403, so the route is
    not an oracle for which OA exists here.

    This is the antithesis of what it replaces: health_zalo's webhook accepted
    events when no secret was configured, accepted them when no header was
    sent, and hashed RE-SERIALISED JSON that could never match anything Zalo
    signs (defect Z2, ledger §5.61).
    """
    if not connection:
        return False
    env = connection.env
    app = platform_app if platform_app is not None else \
        env['channel.platform.app'].sudo()._get_for_provider('zalo')
    app_id = (app.client_id or '') if app else ''
    if not app_id:
        _logger.warning('Zalo webhook rejected: no platform application id')
        return False
    try:
        secret = connection.sudo()._get_secret('provider_secret') or ''
    except Exception:  # noqa: BLE001 — a corrupt secret must reject, not 500
        _logger.warning('Zalo webhook rejected: connection %s secret could '
                        'not be read', connection.id)
        return False
    if not secret:
        _logger.warning('Zalo webhook rejected: connection %s has no webhook '
                        'secret (signature validation cannot run)',
                        connection.id)
        return False
    headers = headers or {}
    provided = (headers.get(ZALO_SIGNATURE_HEADER)
                or headers.get(ZALO_SIGNATURE_HEADER.lower()) or '').strip()
    timestamp = _zalo_signed_timestamp(raw_body, headers)
    if not provided or not timestamp:
        return False
    if provided.lower().startswith('mac='):
        provided = provided[len('mac='):]
    provided = provided.strip().lower()
    if not _zalo_timestamp_ok(env, timestamp):
        _logger.warning('Zalo webhook rejected: timestamp outside the replay '
                        'window')
        return False
    payload = (app_id.encode() + (raw_body or b'') + str(timestamp).encode()
               + secret.encode())
    expected = hashlib.sha256(payload).hexdigest()
    return hmac.compare_digest(expected, provided)
