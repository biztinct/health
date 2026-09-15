# -*- coding: utf-8 -*-
"""Read-only Google Ads REST client (design §7.1 / §7.2, handover GA2 §4.5).

**Pinned API version: v25.**  Released 2026-07-22, sunset **August 2027**,
per https://developers.google.com/google-ads/api/docs/sunset-dates (read
2026-09-15: v25 is the newest RELEASED version and is not deprecated; v25.1 /
v25.2 / v26 are listed as upcoming, and v25.1 shares v25's sunset month).
Re-check that page before GA3 widens the query set.

Three postures are load-bearing:

* **No method takes a query string.** Every read runs one of the module-level
  ``Q_*`` constants, so there is no path from an RPC to arbitrary GAQL and no
  mutate service is reachable at all. ``list_campaigns`` /
  ``fetch_campaign_days`` are declared here and raise ``NotImplementedError``
  — GA3 fills them, and the read-only surface is declared exactly once.
* **Fixed hosts.** ``ADS_HOST`` / ``TOKEN_URL`` / ``AUTH_URL`` are constants,
  TLS verification is the requests default, and every call carries
  ``timeout=HTTP_TIMEOUT``.
* **The HTTP primitives are module-level plain functions** so a test can
  replace them with ``patch.object(google_ads_client, '_http_post_json', fn)``
  — ledger §5.76: a second ``autospec`` patch on an already-patched attribute
  silently stops binding ``self``, and a multi-stage provider flow re-arms its
  mocks constantly. Callers OUTSIDE this file reach them through the module
  object (``google_ads_client._http_post_form(...)``), never through a
  ``from X import Y`` binding, which a patch could not reach; inside this file
  the bare name is a module global and resolves at call time, so a patch
  reaches it too.

Ids are strings everywhere: a Google customer id is ten digits and a campaign
id exceeds 2**53, so ``int()`` never appears in this file.
"""
import logging

import requests

from odoo.addons.health_care_command_channels.services.redact import redact

from . import attribution

_logger = logging.getLogger(__name__)

API_VERSION = 'v25'
API_SUNSET = 'August 2027'
ADS_HOST = 'https://googleads.googleapis.com'
AUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
TOKEN_URL = 'https://oauth2.googleapis.com/token'
SCOPE = 'https://www.googleapis.com/auth/adwords'
HTTP_TIMEOUT = 20
MAX_PAGES = 200

CALLBACK_PATH = '/channel_hub/oauth/callback/google_ads'

Q_CUSTOMER = ('SELECT customer.id, customer.descriptive_name, '
              'customer.currency_code, customer.time_zone, customer.manager, '
              'customer.test_account, customer.status FROM customer LIMIT 1')
Q_CHILDREN = ('SELECT customer_client.id, customer_client.descriptive_name, '
              'customer_client.manager, customer_client.level, '
              'customer_client.currency_code, customer_client.time_zone, '
              'customer_client.status, customer_client.hidden '
              'FROM customer_client WHERE customer_client.level <= 5')

# Error codes that mean "the sign-in itself is gone" — the account moves to
# `action_required` and the operator must press Reconnect. Anything else is
# either transient (retryable) or a configuration answer.
RECONNECT_CODES = frozenset({
    'invalid_grant', 'OAUTH_TOKEN_INVALID', 'NOT_ADS_USER',
    'USER_PERMISSION_DENIED_FOR_LOGIN', 'unauthorized_client',
})
RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})


class GoogleAdsError(Exception):
    """One provider failure, already safe to store and to show.

    ``code`` is short and safe (an error enum name or a coarse label); the
    provider's own text only ever reaches ``detail_redacted``, which has been
    through :func:`redact` — a Google error body routinely echoes the request,
    bearer token included.
    """

    def __init__(self, code, http_status=None, request_id=None,
                 retryable=False, needs_reconnect=False, detail=None):
        self.code = code or 'error'
        self.http_status = http_status
        self.request_id = request_id
        self.retryable = bool(retryable)
        self.needs_reconnect = bool(needs_reconnect)
        self.detail_redacted = redact(detail) if detail else False
        super().__init__(self.code)

    def __str__(self):
        return self.code


# ======================================================================
# HTTP plumbing — cloned from health_care_command_channels' adapters
# (services/adapters.py:546-600), with the error type swapped.
# ======================================================================
def _error_from_response(resp):
    """Map one non-2xx response onto a :class:`GoogleAdsError`.

    Two body shapes reach here and they are not the same:

    * the OAuth token endpoint answers ``{"error": "invalid_grant",
      "error_description": "..."}`` — ``error`` is a STRING;
    * the Ads API answers ``{"error": {"code": 403, "status": "...",
      "details": [{"errors": [{"errorCode": {"authorizationError":
      "USER_PERMISSION_DENIED"}, ...}]}]}}`` — ``error`` is a DICT and the
      useful name is three levels down.
    """
    status = resp.status_code
    request_id = resp.headers.get('request-id') if resp.headers else None
    text = resp.text or ''
    body = {}
    try:
        body = resp.json() or {}
    except ValueError:
        body = {}
    err = body.get('error') if isinstance(body, dict) else None
    code = 'http_%s' % status

    if isinstance(err, str) and err:
        code = err[:64]
    elif isinstance(err, dict):
        for detail in err.get('details') or []:
            if not isinstance(detail, dict):
                continue
            for one in detail.get('errors') or []:
                enum = one.get('errorCode') if isinstance(one, dict) else None
                if isinstance(enum, dict) and enum:
                    # {"authorizationError": "USER_PERMISSION_DENIED"}
                    value = next(iter(enum.values()))
                    if value:
                        code = str(value)[:64]
                        break
            if code != 'http_%s' % status:
                break
        else:
            if err.get('status'):
                code = str(err['status'])[:64]

    return GoogleAdsError(
        code,
        http_status=status,
        request_id=request_id,
        retryable=status in RETRYABLE_STATUSES,
        needs_reconnect=(status == 401 or code in RECONNECT_CODES),
        detail='HTTP %s: %s' % (status, text[:300]),
    )


def _json_or_empty(resp):
    try:
        return resp.json() or {}
    except ValueError:
        return {}


def _http_get(url, headers=None, params=None):
    try:
        resp = requests.get(url, headers=headers, params=params,
                            timeout=HTTP_TIMEOUT)
    except requests.RequestException as exc:
        raise GoogleAdsError('network', retryable=True, detail=str(exc)) from exc
    if resp.status_code >= 300:
        raise _error_from_response(resp)
    return _json_or_empty(resp)


def _http_post_json(url, json_body=None, headers=None):
    try:
        resp = requests.post(url, json=json_body, headers=headers,
                             timeout=HTTP_TIMEOUT)
    except requests.RequestException as exc:
        raise GoogleAdsError('network', retryable=True, detail=str(exc)) from exc
    if resp.status_code >= 300:
        raise _error_from_response(resp)
    return _json_or_empty(resp)


def _http_post_form(url, data=None, headers=None):
    """``application/x-www-form-urlencoded`` POST — Google's token endpoint.

    An HTTP 400 whose JSON ``error`` is ``invalid_grant`` comes back as
    ``GoogleAdsError('invalid_grant', needs_reconnect=True)``: the refresh
    token has been revoked or the grant withdrawn, and only a new sign-in
    fixes it.
    """
    try:
        resp = requests.post(url, data=data, headers=headers,
                             timeout=HTTP_TIMEOUT)
    except requests.RequestException as exc:
        raise GoogleAdsError('network', retryable=True, detail=str(exc)) from exc
    if resp.status_code >= 300:
        raise _error_from_response(resp)
    return _json_or_empty(resp)


# ======================================================================
# Shapes
# ======================================================================
def _pick(row, *names):
    for name in names:
        value = row.get(name)
        if value not in (None, ''):
            return value
    return ''


def _customer_dict(raw):
    """The REST payload for one customer, in our own vocabulary.

    Google's REST surface answers in lowerCamelCase; the snake_case spellings
    are accepted too so a fixture written from the GAQL field names is not
    silently empty.
    """
    raw = raw if isinstance(raw, dict) else {}
    return {
        'id': str(_pick(raw, 'id') or ''),
        'name': str(_pick(raw, 'descriptiveName', 'descriptive_name') or ''),
        'currency': str(_pick(raw, 'currencyCode', 'currency_code') or ''),
        'time_zone': str(_pick(raw, 'timeZone', 'time_zone') or ''),
        'manager': bool(raw.get('manager')),
        'test_account': bool(raw.get('testAccount')
                             or raw.get('test_account')),
        'status': str(_pick(raw, 'status') or ''),
    }


class GoogleAdsClient:
    """Read-only access to ONE advertising account's own metadata.

    The developer token is read per call and never kept on the instance: an
    object that lives for the length of a request should not also be a place a
    traceback can print a platform credential from.
    """

    def __init__(self, env, account):
        self.env = env
        self.account = account

    # ------------------------------------------------------------------
    def _config(self):
        config = self.env['google.ads.platform.config']._active()
        if not config or not config._ready():
            raise GoogleAdsError('not_configured')
        return config

    def _headers(self, login_customer_id=None):
        config = self._config()
        headers = {
            'Authorization': 'Bearer %s' % self.account._reporting_access_token(),
            'developer-token': config._get_developer_token(),
            'Content-Type': 'application/json',
        }
        if login_customer_id:
            headers['login-customer-id'] = self._customer_id(
                login_customer_id)
        return headers

    @staticmethod
    def _customer_id(value):
        """Ten digits or nothing — no URL and no header is ever built from an
        unvalidated string (rail R4)."""
        normalised = attribution.norm_customer_id(value)
        if not normalised:
            raise GoogleAdsError('bad_customer_id')
        return normalised

    # ------------------------------------------------------------------
    def _search(self, customer_id, query, login_customer_id=None):
        """Every page of one fixed query. Never a caller-supplied string."""
        cid = self._customer_id(customer_id)
        url = '%s/%s/customers/%s/googleAds:search' % (ADS_HOST, API_VERSION,
                                                       cid)
        results = []
        page_token = None
        refreshed = False
        for _page in range(MAX_PAGES):
            payload = {'query': query}
            if page_token:
                payload['pageToken'] = page_token
            try:
                body = _http_post_json(
                    url, json_body=payload,
                    headers=self._headers(login_customer_id))
            except GoogleAdsError as err:
                if err.http_status == 401 and not refreshed:
                    # One forced refresh, then believe the answer. Clearing
                    # the expiry is what makes the next _headers() call mint a
                    # new access token (§4.4).
                    refreshed = True
                    self.account._internal().write({'token_expires_at': False})
                    continue
                raise
            results.extend(body.get('results') or [])
            page_token = body.get('nextPageToken')
            if not page_token:
                return results
        raise GoogleAdsError('too_many_pages')

    # ------------------------------------------------------------------
    def list_accessible_customers(self):
        """The customer ids this sign-in can reach directly, as strings."""
        url = '%s/%s/customers:listAccessibleCustomers' % (ADS_HOST,
                                                           API_VERSION)
        body = _http_get(url, headers=self._headers())
        out = []
        for name in body.get('resourceNames') or []:
            tail = str(name).rsplit('/', 1)[-1].strip()
            if tail:
                out.append(tail)
        return out

    def get_customer(self, customer_id, login_customer_id=None):
        rows = self._search(customer_id, Q_CUSTOMER,
                            login_customer_id=login_customer_id)
        if not rows:
            return {}
        return _customer_dict((rows[0] or {}).get('customer') or {})

    def list_customer_children(self, manager_id):
        """Every advertising account under ``manager_id``.

        Manager rows and hidden rows are dropped — a manager cannot hold
        campaign data (rail R5) and a hidden one is not the tenant's to read.
        ``status`` is kept so the UI can grey out a paused or cancelled
        account rather than pretend it is not there.
        """
        rows = self._search(manager_id, Q_CHILDREN,
                            login_customer_id=manager_id)
        out = []
        for row in rows:
            raw = (row or {}).get('customerClient') \
                or (row or {}).get('customer_client') or {}
            if raw.get('manager') or raw.get('hidden'):
                continue
            entry = _customer_dict(raw)
            entry['level'] = str(_pick(raw, 'level') or '')
            if entry['id']:
                out.append(entry)
        return out

    # ------------------------------------------------------------------
    # GA3 — declared here so the read-only surface is stated once.
    # ------------------------------------------------------------------
    def list_campaigns(self, customer_id, login_customer_id=None):
        raise NotImplementedError(
            'Campaign metadata arrives in the reporting phase.')

    def fetch_campaign_days(self, customer_id, date_from, date_to,
                            login_customer_id=None):
        raise NotImplementedError(
            'Daily campaign figures arrive in the reporting phase.')
