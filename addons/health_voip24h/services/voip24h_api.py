# -*- coding: utf-8 -*-
"""VoIP24h REST adapter — V1 authentication and V2 webhook subscription ONLY.

This file was rewritten against the supplied vendor documents. Everything it
does now has a document behind it; everything a document does NOT establish is
absent rather than guessed. The previous version's ``/auth/login``,
``/calls/history``, ``/calls/{id}``, ``/calls/{id}/recording``,
``/calls/initiate`` and ``/extensions`` were conventional REST shapes with no
evidence at all (ledger §5.81 — a valid token plus a live cron is how an
unevidenced endpoint starts getting called every fifteen minutes). They now
live behind :func:`_unverified` and refuse to fire unless the matching
capability flag on the config has been switched on by a human who captured the
contract.

Vendor contracts implemented here
---------------------------------

V1  ``POST https://api.voip24h.vn/v3/authentication``
    body ``{"apiKey", "apiSecret", "isLonglive"}``
    documented success ``{"message": "Success", "status": 1000, "data": {
        "token", "createAt", "expried", "isLonglive"}}``
    OBSERVED success, 2026-09-17 ``{"message": "Success", "status": 200,
        "data": {"token", "createAt", "expired", "isLongLive"}}``
    An unknown key answers HTTP 401 ``{"status": 401,
        "message": "Account does not exist"}``.

V2  ``POST https://api.voip24h.vn/v3/webhook-call-log/``   (trailing slash!)
    ``DELETE https://api.voip24h.vn/v3/webhook-call-log/`` (JSON body ``url``)
    both ``Authorization: Bearer <token>``; success body ``{"status": 200}``

Known contradictions, and how they are handled rather than papered over:

* ``isLonglive`` is declared Boolean but every vendor sample sends the STRING
  ``"true"``. ``voip.config.auth_longlive_wire`` selects which goes on the
  wire; the default is the declared type (JSON boolean) and the string is one
  toggle away for the contract test (gate G01).
* V1's header prose mentions ``Authorization: Bearer <JWT>`` on the *token*
  request while its cURL sample sends only ``Content-Type``. Bootstrap here
  sends no Authorization header. There is no such thing as a bootstrap token
  and inventing one would be a fiction, not a fallback.
* **The live service does not match the document, and the document lost.**
  Captured 2026-09-17: success is ``status: 200``, not ``1000``; the expiry is
  ``expired``, not ``expried``; the flag is ``isLongLive``, not ``isLonglive``.
  Built from the document alone this module REFUSED a successful login. Both
  status values and every spelling are accepted now (``AUTH_OK_STATUSES``,
  ``AUTH_EXPIRY_KEYS``, ``AUTH_LONGLIVE_KEYS``) — the document is what the
  supplier may go back to, the capture is what works today, and neither is
  guessed.
* The expiry carries no timezone. It is read in the config's declared
  provider timezone (``Asia/Ho_Chi_Minh`` for the Vietnamese pilot) and stored
  naive UTC, with the profile used recorded alongside it. A missing or
  unparsable expiry produces a VISIBLE degraded state — never an assumed
  seven-day lifetime.

HTTP status and body ``status`` are separate facts and both are checked.
"""

import json
import logging
import socket
from datetime import datetime, timedelta
from urllib.parse import urlsplit

import requests

from odoo import _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# The only hosts this adapter will ever speak to. A base URL outside the
# allowlist is refused before the first byte leaves, so a mis-typed (or
# maliciously written) ``api_base_url`` cannot turn the server into a
# credential-forwarding proxy.
ALLOWED_API_HOSTS = ('api.voip24h.vn',)

DEFAULT_API_BASE_URL = 'https://api.voip24h.vn/v3'

# V1/V2 body success values. HTTP 200 with one of these absent is a
# provider-level FAILURE, not a success (acceptance A02).
#
# GATE G01 CLOSED 2026-09-17 BY CAPTURING THE LIVE SERVICE, and it does not
# match the document. `Authorization.docx` says a successful authentication
# answers `status: 1000`. The live service answers `status: 200`:
#
#     {"message":"Success","status":200,
#      "data":{"token":"…","createAt":"2026-09-17 10:39:53",
#              "expired":"2026-09-18 10:39:53","isLongLive":false}}
#
# Built from the document alone, this module refused a SUCCESSFUL login. Both
# values are accepted now — 1000 because the supplier published it, 200 because
# it is what they actually send. Neither is a guess; both are evidenced.
AUTH_OK_STATUS = 1000
AUTH_OK_STATUSES = (1000, 200)
WEBHOOK_OK_STATUS = 200

# The same capture showed two field names spelled differently on the wire than
# in the document. Read every spelling rather than picking a side: the document
# is what the supplier may go back to, the capture is what works today.
#   expiry   — documented `expried` (sic), live `expired`
#   longlive — documented `isLonglive`, live `isLongLive`
AUTH_EXPIRY_KEYS = ('expired', 'expried', 'expires', 'expiry')
AUTH_LONGLIVE_KEYS = ('isLongLive', 'isLonglive', 'islonglive')

CONNECT_TIMEOUT = 5.0
READ_TIMEOUT = 15.0
MAX_RESPONSE_BYTES = 256 * 1024


class VoIP24hError(UserError):
    """A sanitised, user-presentable provider failure.

    Never carries a token, an apiSecret or a raw provider body — the operator
    gets a class of failure and a diagnostic code, and the full detail goes to
    the log at debug level with the credentials already stripped.
    """


def _first(body, keys):
    """The first of ``keys`` the provider actually sent, or ''.

    The supplier spells two response fields differently in their document and
    on the wire (`expried`/`expired`, `isLonglive`/`isLongLive`). Reading every
    spelling costs nothing and means a correction on either side — theirs or
    the document's — does not silently stop the token being understood.
    """
    for key in keys:
        value = (body or {}).get(key)
        if value not in (None, ''):
            return value
    return ''


def _sanitise(text, limit=200):
    """Bound and de-secret a provider string before it can reach a user."""
    if not text:
        return ''
    text = str(text)
    for marker in ('apiSecret', 'apiKey', 'Bearer ', 'token'):
        if marker in text:
            return '(provider message withheld: it contained credential text)'
    return text[:limit]


class VoIP24hAPI:
    """Authenticated client for one ``voip.config``.

    The config record is expected to be sudo'd by the caller
    (``voip.config._get_api_client`` does it): ``api_key``/``api_secret`` and
    the token columns are ``base.group_system`` protected.
    """

    def __init__(self, config):
        self.config = config
        self.env = config.env
        self.base_url = (config.api_base_url or DEFAULT_API_BASE_URL).rstrip('/')
        self._check_base_url()
        self.session = requests.Session()
        # Never follow a redirect on an authenticated request: a 30x to another
        # host would hand the Bearer token to whoever controls it.
        self.session.max_redirects = 0

    # ------------------------------------------------------------------
    # Transport
    # ------------------------------------------------------------------

    def _check_base_url(self):
        parts = urlsplit(self.base_url)
        if parts.scheme != 'https':
            raise VoIP24hError(_(
                'The phone system address must start with https://.'))
        if parts.hostname not in ALLOWED_API_HOSTS:
            raise VoIP24hError(_(
                'The phone system address “%s” is not one this server is '
                'allowed to call.') % (parts.hostname or '?'))

    def _headers(self, token=None, with_auth=True):
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
        if with_auth:
            token = token or self._token()
            if token:
                headers['Authorization'] = 'Bearer %s' % token
        return headers

    def _request(self, method, path, *, payload=None, token=None,
                 with_auth=True, allow_reauth=True):
        """One bounded provider call. Returns the decoded JSON body (a dict).

        Raises :class:`VoIP24hError` for every failure class, with a sanitised
        message. A 401 on an authenticated call reauthenticates ONCE and
        retries — and only for the safe/idempotent operations that pass
        ``allow_reauth`` (the caller decides; a subscription DELETE does not).
        """
        url = '%s/%s' % (self.base_url, path.lstrip('/'))
        body = json.dumps(payload) if payload is not None else None
        try:
            response = self.session.request(
                method, url,
                data=body,
                headers=self._headers(token=token, with_auth=with_auth),
                timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
                verify=True,
                allow_redirects=False,
            )
        except requests.exceptions.SSLError as exc:
            _logger.error('VoIP24h TLS failure on %s %s: %s', method, path, exc)
            raise VoIP24hError(_(
                'The secure connection to the phone system could not be '
                'established.')) from exc
        except (requests.exceptions.Timeout, socket.timeout) as exc:
            raise VoIP24hError(_(
                'The phone system did not answer in time.')) from exc
        except requests.exceptions.RequestException as exc:
            _logger.error('VoIP24h transport failure on %s %s: %s',
                          method, path, type(exc).__name__)
            raise VoIP24hError(_(
                'The phone system could not be reached.')) from exc

        if response.status_code in (301, 302, 303, 307, 308):
            raise VoIP24hError(_(
                'The phone system redirected the request; this server does '
                'not follow redirects on an authenticated call.'))

        if response.status_code == 401 and with_auth and allow_reauth:
            _logger.info('VoIP24h returned 401 on %s; reauthenticating once',
                         path)
            self.authenticate()
            return self._request(method, path, payload=payload,
                                 with_auth=with_auth, allow_reauth=False)

        raw = response.content or b''
        if len(raw) > MAX_RESPONSE_BYTES:
            raise VoIP24hError(_('The phone system sent an oversized reply.'))

        try:
            data = json.loads(raw.decode('utf-8')) if raw else {}
        except (ValueError, UnicodeDecodeError) as exc:
            _logger.error('VoIP24h sent a non-JSON body on %s (HTTP %s)',
                          path, response.status_code)
            raise VoIP24hError(_(
                'The phone system sent a reply this server could not read.')
            ) from exc

        if not isinstance(data, dict):
            raise VoIP24hError(_(
                'The phone system sent a reply this server could not read.'))

        if response.status_code >= 400:
            # LOGGED, because the alternative is what happened on 2026-09-17:
            # an operator saw "Account does not exist" on screen and the server
            # log held nothing at all to tell them whether the credential was
            # wrong, the endpoint was wrong, or we were sending the wrong shape.
            # The message is sanitised and the credentials never appear.
            _logger.warning('VoIP24h refused %s %s: HTTP %s %r',
                            method, path, response.status_code,
                            _sanitise(data.get('message')))
            raise VoIP24hError(_(
                'The phone system refused the request (%(code)s): %(msg)s',
                code=response.status_code,
                msg=_sanitise(data.get('message')) or _('no detail given')))

        return data

    # ------------------------------------------------------------------
    # V1 — authentication
    # ------------------------------------------------------------------

    def _token(self):
        return self.config._voip_secret_read('access_token')

    def authenticate(self):
        """Obtain and store a provider token (V1).

        Single-flight per config: two workers renewing at once would each
        invalidate the other's token if the provider rotates on issue (that is
        gate G01, still open), so the critical section is held by a PostgreSQL
        **advisory** transaction lock — never a row lock, because the token is
        persisted from this very transaction and §5.74's self-deadlock is
        exactly what a row lock would produce here.
        """
        self.config._check_credentials()
        with self.config._auth_single_flight() as acquired:
            if not acquired:
                # Someone else is renewing. Re-read: by the time the lock is
                # free their token is committed, and calling the provider
                # again would be the double-renewal we are avoiding.
                self.config.invalidate_recordset(
                    ['access_token_enc', 'token_expires_at'])
                if self.config._token_is_usable():
                    return {'reused': True}
                # Their attempt failed; fall through and try ourselves.
            return self._do_authenticate()

    def _do_authenticate(self):
        longlive = bool(self.config.auth_longlive)
        if self.config.auth_longlive_wire == 'string':
            # The vendor's own samples send the STRING. One toggle, so the
            # contract test can establish which the live service accepts.
            wire_longlive = 'true' if longlive else 'false'
        else:
            wire_longlive = longlive

        payload = {
            'apiKey': self.config.api_key,
            'apiSecret': self.config.api_secret,
            'isLonglive': wire_longlive,
        }
        # Bootstrap carries NO Authorization header. See the module docstring.
        data = self._request('POST', '/authentication', payload=payload,
                             with_auth=False, allow_reauth=False)

        status = data.get('status')
        if status not in AUTH_OK_STATUSES:
            message = _sanitise(data.get('message'))
            self.config._note_auth_failure(
                'status_%s' % status, message)
            _logger.warning('VoIP24h authentication refused for config %s: '
                            'body status %r, message %r', self.config.id,
                            status, message)
            raise VoIP24hError(_(
                'The phone system did not accept these credentials '
                '(%(code)s). %(msg)s', code=status, msg=message))

        body = data.get('data') or {}
        token = body.get('token')
        if not token or not isinstance(token, str):
            self.config._note_auth_failure('no_token', '')
            raise VoIP24hError(_(
                'The phone system accepted the credentials but returned no '
                'access token.'))

        expires_at, expiry_quality = self.config._parse_provider_expiry(
            _first(body, AUTH_EXPIRY_KEYS))

        self.config._store_token(
            token,
            expires_at=expires_at,
            expiry_quality=expiry_quality,
            longlive=bool(_first(body, AUTH_LONGLIVE_KEYS)),
            created_at_raw=body.get('createAt') or '',
        )
        _logger.info('VoIP24h authentication succeeded for config %s '
                     '(expiry quality: %s)', self.config.id, expiry_quality)
        return {'token_stored': True, 'expiry_quality': expiry_quality}

    # ------------------------------------------------------------------
    # V2 — webhook subscription
    # ------------------------------------------------------------------

    def register_call_log_webhook(self, url, method='POST', active=True,
                                  auth_token='', call_type='', disposition=''):
        """Create or update the completed-call subscription (V2).

        The documented path carries a TRAILING SLASH and the vendor's own
        samples are inconsistent about ``param`` being an array or an object;
        the samples show an object and that is what goes on the wire.

        Returns the decoded provider body. A documented ``status: 200`` is the
        success test — the HTTP code alone is not, and a successful response
        proves the subscription was ACCEPTED, never that an event was ever
        delivered (the readiness model keeps those two facts apart).
        """
        if not url or not url.lower().startswith('https://'):
            raise VoIP24hError(_(
                'The address the phone system should call back must be an '
                'https:// address.'))
        if method not in ('GET', 'POST'):
            raise VoIP24hError(_('The callback method must be GET or POST.'))

        payload = {
            'url': url,
            'method': method,
            'active': bool(active),
            'param': {
                'auth': auth_token or '',
                'type': call_type or '',
                'disposition': disposition or '',
            },
        }
        data = self._request('POST', '/webhook-call-log/', payload=payload,
                             allow_reauth=True)
        if data.get('status') != WEBHOOK_OK_STATUS:
            raise VoIP24hError(_(
                'The phone system did not accept the callback registration '
                '(%(code)s): %(msg)s',
                code=data.get('status'),
                msg=_sanitise(data.get('message')) or _('no detail given')))
        return data

    def delete_call_log_webhook(self, url):
        """Remove the completed-call subscription (V2).

        ``allow_reauth`` is False on purpose: a DELETE is not something to
        replay blind after a token refresh — the caller re-runs it knowingly.
        """
        if not url:
            raise VoIP24hError(_('No callback address to remove.'))
        data = self._request('DELETE', '/webhook-call-log/',
                             payload={'url': url}, allow_reauth=False)
        if data.get('status') != WEBHOOK_OK_STATUS:
            raise VoIP24hError(_(
                'The phone system did not accept the callback removal '
                '(%(code)s): %(msg)s',
                code=data.get('status'),
                msg=_sanitise(data.get('message')) or _('no detail given')))
        return data

    # ------------------------------------------------------------------
    # Endpoints no supplied document establishes
    # ------------------------------------------------------------------
    #
    # These exist as ONE refusal rather than five plausible-looking URLs. The
    # capability flag is the only thing that can open them, and opening one
    # means a human captured that contract and wrote it down. Until then the
    # honest implementation of "fetch call history" is to say we cannot.

    def _unverified(self, capability, what):
        raise VoIP24hError(_(
            '%(what)s needs a part of the phone system’s interface that has '
            'not been confirmed for this account yet. An administrator can '
            'turn it on in the phone settings once the supplier has confirmed '
            'it (%(cap)s).', what=what, cap=capability))

    def get_call_history(self, *args, **kwargs):
        if not self.config.history_sync_verified:
            self._unverified('history_sync_verified', _('Downloading past calls'))
        raise VoIP24hError(_(
            'The past-calls interface is marked confirmed but no captured '
            'contract has been implemented for it yet.'))

    def get_extensions(self):
        if not self.config.extension_sync_verified:
            self._unverified('extension_sync_verified',
                             _('Reading the list of extensions'))
        raise VoIP24hError(_(
            'The extension-list interface is marked confirmed but no captured '
            'contract has been implemented for it yet.'))

    def initiate_call(self, from_extension, to_number):
        if not self.config.rest_originate_verified:
            self._unverified('rest_originate_verified',
                             _('Starting a call from the server'))
        raise VoIP24hError(_(
            'The server-dialling interface is marked confirmed but no '
            'captured contract has been implemented for it yet.'))

    def test_connection(self):
        """Prove the credentials, and nothing else.

        Returns a small dict rather than a bare bool so the caller can show
        WHICH fact was established. Authenticating proves exactly one thing:
        the API accepted these credentials. It proves nothing about callbacks,
        recordings or whether a browser can ring.
        """
        result = self.authenticate()
        return {
            'ok': True,
            'reused': bool(result.get('reused')),
            'expiry_quality': result.get('expiry_quality')
                              or self.config.token_expiry_quality,
        }


# ----------------------------------------------------------------------
# Standalone helpers (used by the config model and by tests)
# ----------------------------------------------------------------------

def parse_provider_datetime(value, tzname):
    """``"2024-10-04 16:35:36"`` in ``tzname`` -> naive UTC datetime.

    Returns ``(datetime | None, quality)`` where quality is one of
    ``'ok'`` / ``'missing'`` / ``'unparsable'`` / ``'no_timezone'``. The
    caller decides what to do with a bad one; this function never invents a
    value, and in particular never falls back to "seven days from now".
    """
    if not value:
        return None, 'missing'
    text = str(value).strip()
    parsed = None
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M',
                '%d/%m/%Y %H:%M:%S'):
        try:
            parsed = datetime.strptime(text, fmt)
            break
        except ValueError:
            continue
    if parsed is None:
        try:
            parsed = datetime.fromisoformat(text.replace('Z', '+00:00'))
        except ValueError:
            return None, 'unparsable'
    if parsed.tzinfo is not None:
        from datetime import timezone as _tz
        return parsed.astimezone(_tz.utc).replace(tzinfo=None), 'ok'
    if not tzname:
        return None, 'no_timezone'
    from datetime import timezone as _tz
    try:
        # zoneinfo is stdlib from 3.9 and is what this reads first; pytz is
        # kept as the fallback because Odoo ships it and some deployments
        # carry tz names only pytz knows.
        from zoneinfo import ZoneInfo
        local = parsed.replace(tzinfo=ZoneInfo(tzname))
        return local.astimezone(_tz.utc).replace(tzinfo=None), 'ok'
    except Exception:  # noqa: BLE001 — unknown zone, or no tzdata installed
        pass
    try:
        import pytz
        local = pytz.timezone(tzname).localize(parsed)
        return local.astimezone(pytz.utc).replace(tzinfo=None), 'ok'
    except Exception:  # noqa: BLE001 — an unknown tz name is a config error
        return None, 'no_timezone'


def default_token_expiry(longlive):
    """The DOCUMENTED lifetime, used only as a scheduling hint.

    V1 says false -> 1 day, true -> 7 days. This is never a substitute for a
    parsed ``expried``; it exists so a config whose expiry could not be read
    still schedules a renewal instead of never renewing at all, and the
    ``token_expiry_quality`` field is what tells the operator which of the two
    they are looking at.
    """
    return datetime.utcnow() + timedelta(days=7 if longlive else 1)
