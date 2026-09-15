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
  mutate service is reachable at all. ``fetch_campaign_days`` is the one read
  whose query is not a bare constant, and the only thing interpolated into it
  is two ``datetime.date`` objects the method formats itself.
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
import datetime
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

# GA3. The campaign metadata query and the daily metrics query, both fixed.
# `Q_DAYS` carries two `%s` placeholders filled from `datetime.date` OBJECTS
# formatted by `fetch_campaign_days` — never from a caller's string, so the
# read-only posture at the top of this file still holds: there is no path from
# an RPC to arbitrary GAQL.
#
# `metrics.conversions` is read WITHOUT any conversion-action segment on
# purpose (design §7.2): segmenting the primary metrics table by conversion
# action repeats every cost row once per action and multiplies spend.
Q_CAMPAIGNS = ('SELECT campaign.id, campaign.name, campaign.status, '
               'campaign.advertising_channel_type FROM campaign')
Q_DAYS = ('SELECT campaign.id, segments.date, metrics.impressions, '
          'metrics.clicks, metrics.cost_micros, metrics.conversions '
          'FROM campaign '
          "WHERE segments.date BETWEEN '%s' AND '%s'")

# A single fetch never asks for more than this many days (design §7.2 —
# bounded query dates). The rolling window is 30 and the backfill walks in
# chunks of 30, so anything past a year is a programming error, not a request.
MAX_WINDOW_DAYS = 366

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


def _as_int(value):
    """An int64 that arrived as a STRING, as an int. Junk reads 0.

    No clamping here — the int4 question belongs to the cache model
    (ledger §5.80), and the honest answer at this layer is what Google sent.
    """
    try:
        return int(str(value).strip() or 0)
    except (TypeError, ValueError):
        return 0


def _as_float(value):
    """``metrics.conversions`` is fractional and may arrive as a number OR a
    string. Junk reads 0.0."""
    try:
        return float(value if value not in (None, '') else 0.0)
    except (TypeError, ValueError):
        return 0.0


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
    # GA3 — the reporting reads.
    # ------------------------------------------------------------------
    def list_campaigns(self, customer_id, login_customer_id=None):
        """Every campaign on this advertising account, as typed dicts.

        ``id`` stays a STRING: a Google campaign id exceeds 2**53 and one
        ``int()`` anywhere in the chain silently renames a campaign.
        """
        rows = self._search(customer_id, Q_CAMPAIGNS,
                            login_customer_id=login_customer_id)
        out = []
        for row in rows:
            raw = (row or {}).get('campaign') or {}
            campaign_id = str(_pick(raw, 'id') or '')
            if not campaign_id:
                continue
            out.append({
                'id': campaign_id,
                'name': str(_pick(raw, 'name') or ''),
                'status': str(_pick(raw, 'status') or ''),
                'advertising_channel_type': str(
                    _pick(raw, 'advertisingChannelType',
                          'advertising_channel_type') or ''),
            })
        return out

    def fetch_campaign_days(self, customer_id, date_from, date_to,
                            login_customer_id=None):
        """One row per (campaign, account-local day) in the window.

        ``date_from`` / ``date_to`` are ``datetime.date`` OBJECTS — the client
        formats them itself, so no caller string ever reaches the query. A
        window that is inverted or longer than :data:`MAX_WINDOW_DAYS` is
        refused with ``GoogleAdsError('bad_window')`` rather than silently
        truncated.

        ``cost_micros`` comes back as the EXACT STRING Google sent: it is an
        int64 and the caller stores it byte for byte (rail R3). Impressions and
        clicks are parsed to ``int`` here and clamped by the cache model, which
        is where int4 lives (§5.80).
        """
        date_from = self._as_date(date_from)
        date_to = self._as_date(date_to)
        if date_to < date_from \
                or (date_to - date_from).days > MAX_WINDOW_DAYS:
            raise GoogleAdsError('bad_window')
        query = Q_DAYS % (date_from.strftime('%Y-%m-%d'),
                          date_to.strftime('%Y-%m-%d'))
        rows = self._search(customer_id, query,
                            login_customer_id=login_customer_id)
        out = []
        for row in rows:
            row = row or {}
            campaign = row.get('campaign') or {}
            segments = row.get('segments') or {}
            metrics = row.get('metrics') or {}
            campaign_id = str(_pick(campaign, 'id') or '')
            day = self._as_day(_pick(segments, 'date'))
            if not campaign_id or not day:
                continue
            out.append({
                'campaign_id': campaign_id,
                'date': day,
                'impressions': _as_int(_pick(metrics, 'impressions')),
                'clicks': _as_int(_pick(metrics, 'clicks')),
                # The string, untouched — validated by the writer.
                'cost_micros': str(
                    _pick(metrics, 'costMicros', 'cost_micros') or '0'),
                'conversions': _as_float(_pick(metrics, 'conversions')),
            })
        return out

    @staticmethod
    def _as_date(value):
        """A ``datetime.date``, or ``bad_window``. A ``datetime`` is narrowed
        to its date — never parsed from a string."""
        if isinstance(value, datetime.datetime):
            return value.date()
        if isinstance(value, datetime.date):
            return value
        raise GoogleAdsError('bad_window')

    @staticmethod
    def _as_day(value):
        """``segments.date`` ("2026-09-01") as a date, or False."""
        text = str(value or '')[:10]
        try:
            return datetime.date.fromisoformat(text)
        except ValueError:
            return False
