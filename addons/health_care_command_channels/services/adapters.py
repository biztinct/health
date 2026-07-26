# -*- coding: utf-8 -*-
"""Channel adapter registry + capability contract (architecture §6).

Phase CC-A ships the *contract* only: ``BaseChannelAdapter`` with every
operation raising ``NotImplementedError``, plus one declaration-only stub per
channel key whose sole implemented member is
:meth:`~BaseChannelAdapter.authorization_capabilities`. Those declarations are
real (they come from the verified provider matrix, architecture §3) and are
already load-bearing: they drive ``care.channel.connection._required_checks()``
and therefore the readiness derivation, and they are what the CC-C stepper UI
will be written against.

Phase CC-B fills in ``parse_inbound`` / ``send_message`` for the four chat
channels (WhatsApp, Messenger, Telegram, Web chat). Everything else — OAuth,
resource selection, webhook registration, refresh — stays declaration-only
until CC-D/CC-E/CC-F.

Messaging rules that hold for every adapter here:

* HTTP goes through ``requests`` with an explicit timeout, and ``api_base_override``
  is honoured so tests and staging never reach a real provider;
* logging is event types + ids ONLY — never a body, a phone number, a name or a
  token (no PHI, no credentials, in any log line);
* ``parse_inbound`` filters the payload down to THIS connection's resource id:
  one provider webhook can carry entries for several tenants, and an adapter
  must never ingest another tenant's traffic;
* a failed send RAISES; the caller turns that into a failed message row, a
  redacted error and a clean UserError. Silence is never an option.
"""
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import requests

from odoo import fields, tools
from odoo.exceptions import UserError

from . import channel_crypto

_logger = logging.getLogger(__name__)

# Every provider call is bounded: a hung provider must not hold a worker.
HTTP_TIMEOUT = 15

GRAPH_BASE = 'https://graph.facebook.com'
GRAPH_VERSION = 'v21.0'
TELEGRAM_BASE = 'https://api.telegram.org'

# Zalo (CC-D, verified 2026-07-25 — architecture §3/§7, handover §2.6).
# Authorization and token exchange live on oauth.zaloapp.com; everything else
# (getoa, messaging, ZNS) on openapi.zalo.me. health_zalo's `api_base_url`
# pointed BOTH at openapi.zalo.me, which is why its token calls never worked
# (defect Z8).
ZALO_OAUTH_BASE = 'https://oauth.zaloapp.com'
ZALO_OPENAPI_BASE = 'https://openapi.zalo.me'
ZALO_PERMISSION_PATH = '/v4/oa/permission'
ZALO_TOKEN_PATH = '/v4/oa/access_token'
ZALO_GETOA_PATH = '/v2.0/oa/getoa'
ZALO_CALLBACK_PATH = '/channel_hub/oauth/callback/zalo'
ZALO_WEBHOOK_PATH = '/care_channels/zalo/webhook'
# The access token lives ~25 h; refresh this far ahead of the wire so a cron
# tick that lands late still has a working grant to renew.
ZALO_REFRESH_AHEAD_HOURS = 3

# Provider message types we map onto our own small set.
_WA_TYPE_MAP = {'text': 'text', 'image': 'image', 'document': 'file',
                'audio': 'file', 'video': 'file', 'sticker': 'image',
                'location': 'location'}


def _utc_from_unix(value):
    """Provider epoch seconds → naive UTC datetime (what fields.Datetime stores).

    Returns None for anything unusable rather than guessing: the ingest funnel
    then falls back to "now", which is honest, while a silently-wrong 1970
    timestamp would sort the message to the top of every timeline forever.
    """
    if not value:
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc).replace(
            tzinfo=None)
    except (TypeError, ValueError, OSError, OverflowError):
        return None


class ChannelSendError(Exception):
    """A provider refused or failed to accept an outbound message."""


# key -> adapter class
CHANNEL_ADAPTERS = {}

# Authorization modes an adapter may declare.
MODE_OAUTH_POPUP = 'oauth_popup'
MODE_EMBEDDED_SIGNUP = 'embedded_signup'
MODE_GUIDED_SECRET = 'guided_secret'
MODE_ONE_CLICK = 'one_click'

VALID_MODES = {MODE_OAUTH_POPUP, MODE_EMBEDDED_SIGNUP, MODE_GUIDED_SECRET,
               MODE_ONE_CLICK}

# The readiness check keys an adapter may require (mirrors the Selection on
# care.channel.readiness.check — keep the two in sync).
CHECK_KEYS = (
    'authorization_valid', 'scopes_granted', 'resource_selected',
    'webhook_configured', 'webhook_verified', 'outbound_ok', 'inbound_ok',
    'token_fresh', 'provider_approvals',
)

# Keys every authorization_capabilities() dict must carry.
CAPABILITY_KEYS = (
    'mode', 'needs_platform_app', 'resource_selection', 'webhook_auto',
    'supports_refresh', 'supports_revoke', 'required_checks', 'guide_steps',
)

# Optional declarations (CC-C): ``parent_channel`` (zns renders inside zalo's
# card) and ``platform_providers`` — WHICH channel.platform.app provider(s)
# would have to exist for a needs_platform_app channel to be offerable at all.
# The Center reads it to answer "Not available yet" honestly instead of
# offering a Connect button that could only fail (architecture §4, §9).
OPTIONAL_CAPABILITY_KEYS = ('parent_channel', 'platform_providers')


def register_adapter(key):
    """Class decorator: register an adapter under a care.conversation channel key."""
    def _wrap(cls):
        cls._channel_key = key
        CHANNEL_ADAPTERS[key] = cls
        return cls
    return _wrap


def get_adapter(env, connection):
    """Instantiate the adapter for ``connection`` (a care.channel.connection).

    Raises ``ValueError`` for a channel key with no registered adapter — a
    missing adapter is a programming error, never a silently degraded channel.
    """
    key = getattr(connection, 'channel', None) or connection
    cls = CHANNEL_ADAPTERS.get(key)
    if cls is None:
        raise ValueError('No channel adapter registered for %r' % (key,))
    return cls(env, connection)


class BaseChannelAdapter:
    """Provider-neutral adapter interface.

    Every method except :meth:`authorization_capabilities` raises
    ``NotImplementedError`` in this phase; the connection health cron treats
    that as "nothing to check yet" and skips quietly (handover §7).
    """

    _channel_key = None

    def __init__(self, env, connection):
        self.env = env
        self.connection = connection

    # ------------------------------------------------------------------
    # Declaration — drives the stepper UI and the readiness set
    # ------------------------------------------------------------------
    def authorization_capabilities(self) -> dict:
        """{"mode", "needs_platform_app", "resource_selection", "webhook_auto",
        "supports_refresh", "supports_revoke", "required_checks", "guide_steps"}
        """
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Authorization
    # ------------------------------------------------------------------
    def begin_authorization(self, session) -> dict:
        raise NotImplementedError

    def handle_callback(self, session, params) -> dict:
        raise NotImplementedError

    def list_resources(self) -> list:
        raise NotImplementedError

    def connect_resource(self, resource_id) -> None:
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Plumbing
    # ------------------------------------------------------------------
    def register_webhook(self) -> dict:
        raise NotImplementedError

    def verify_webhook(self, raw_body, headers) -> bool:
        # FAIL CLOSED (ledger §5.61): the base class can never say "verified".
        return False

    def test_connection(self) -> dict:
        raise NotImplementedError

    def refresh_authorization(self) -> None:
        raise NotImplementedError

    def revoke_authorization(self) -> None:
        raise NotImplementedError

    def health_check(self) -> dict:
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Messaging (CC-B)
    # ------------------------------------------------------------------
    def parse_inbound(self, payload) -> list:
        raise NotImplementedError

    def send_message(self, identity, text) -> dict:
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Shared HTTP plumbing
    # ------------------------------------------------------------------
    def _api_base(self, default):
        return (getattr(self.connection, 'api_base_override', '')
                or default).rstrip('/')

    def _get(self, url, *, params=None, headers=None):
        """GET with a timeout; same error contract as :meth:`_post`.

        Used by the credential-validation calls the Center makes before it
        stores anything (Telegram ``getMe``).
        """
        try:
            resp = requests.get(url, params=params, headers=headers,
                                timeout=HTTP_TIMEOUT)
        except requests.RequestException as exc:
            raise ChannelSendError('network error: %s' % exc) from exc
        if resp.status_code >= 300:
            raise ChannelSendError('HTTP %s: %s' % (resp.status_code,
                                                    (resp.text or '')[:300]))
        try:
            return resp.json() or {}
        except ValueError:
            return {}

    def _post(self, url, *, json_body=None, params=None, headers=None):
        """POST with a timeout; raise ``ChannelSendError`` on anything but 2xx.

        The error text carries the status code and the provider's own message
        so the readiness model can tell a 401 (grant lost) from a 500 (provider
        wobble) — the caller redacts it before it is stored or shown.
        """
        try:
            resp = requests.post(url, json=json_body, params=params,
                                 headers=headers, timeout=HTTP_TIMEOUT)
        except requests.RequestException as exc:
            raise ChannelSendError('network error: %s' % exc) from exc
        if resp.status_code >= 300:
            # Body may carry a token in an echoed request — the caller redacts.
            raise ChannelSendError('HTTP %s: %s' % (resp.status_code,
                                                    (resp.text or '')[:300]))
        try:
            return resp.json() or {}
        except ValueError:
            return {}

    def _form_post(self, url, *, data=None, headers=None):
        """``application/x-www-form-urlencoded`` POST.

        OAuth token endpoints take a form body, not JSON — Zalo's
        ``/v4/oa/access_token`` refuses anything else, and the app secret
        travels in a HEADER (never in the URL, never in the body).
        """
        try:
            resp = requests.post(url, data=data, headers=headers,
                                 timeout=HTTP_TIMEOUT)
        except requests.RequestException as exc:
            raise ChannelSendError('network error: %s' % exc) from exc
        if resp.status_code >= 300:
            raise ChannelSendError('HTTP %s: %s' % (resp.status_code,
                                                    (resp.text or '')[:300]))
        try:
            return resp.json() or {}
        except ValueError:
            return {}

    # ------------------------------------------------------------------
    # Failure classification — a transient wobble must not tear a working
    # grant down, and a lost grant must not be papered over as a wobble.
    # ------------------------------------------------------------------
    @staticmethod
    def _is_auth_failure(error):
        text = str(error or '').lower()
        if 'network error' in text or 'timed out' in text:
            return False
        if any(marker in text for marker in ('http 5', 'internal server')):
            return False
        return True


class _StubAdapter(BaseChannelAdapter):
    """Declaration-only adapter: capabilities are real, operations are not."""

    _capabilities = {}

    def authorization_capabilities(self) -> dict:
        # Copy so a caller can never mutate the class declaration.
        caps = dict(self._capabilities)
        caps['required_checks'] = list(caps.get('required_checks', ()))
        caps['guide_steps'] = list(caps.get('guide_steps', ()))
        return caps


# ---------------------------------------------------------------------------
# The 8 channel declarations (verified provider matrix, architecture §3)
# ---------------------------------------------------------------------------

@register_adapter('whatsapp')
class WhatsAppAdapter(_StubAdapter):
    """WhatsApp Cloud API via Meta Embedded Signup v4. The business (BISU)
    token does not expire by default, hence supports_refresh=False."""
    _capabilities = {
        'mode': MODE_EMBEDDED_SIGNUP,
        'needs_platform_app': True,
        'platform_providers': ['meta'],
        'resource_selection': True,      # WABA + phone number picker
        'webhook_auto': True,            # POST /{waba}/subscribed_apps
        'supports_refresh': False,
        'supports_revoke': True,
        'required_checks': ['authorization_valid', 'scopes_granted',
                            'resource_selected', 'webhook_configured',
                            'outbound_ok', 'provider_approvals'],
        'guide_steps': ['channel_hub.guide.whatsapp.signin',
                        'channel_hub.guide.whatsapp.number',
                        'channel_hub.guide.whatsapp.connecting',
                        'channel_hub.guide.whatsapp.test'],
    }

    # -- messaging (CC-B) ----------------------------------------------
    def parse_inbound(self, payload):
        """Cloud API webhook → normalised events for THIS phone number.

        Meta batches: one POST can carry several entries, and on a shared app
        several tenants' numbers. Everything whose ``phone_number_id`` is not
        ours is skipped, not ingested.
        """
        events = []
        mine = self.connection.resource_external_id
        for entry in (payload or {}).get('entry') or []:
            for change in entry.get('changes') or []:
                value = change.get('value') or {}
                metadata = value.get('metadata') or {}
                if mine and metadata.get('phone_number_id') != mine:
                    continue
                names = {}
                for contact in value.get('contacts') or []:
                    profile = contact.get('profile') or {}
                    if contact.get('wa_id'):
                        names[contact['wa_id']] = profile.get('name')
                for message in value.get('messages') or []:
                    wa_id = message.get('from')
                    mtype = _WA_TYPE_MAP.get(message.get('type'), 'other')
                    text = (message.get('text') or {}).get('body') or ''
                    attachment = {}
                    for key in ('image', 'document', 'audio', 'video'):
                        media = message.get(key)
                        if isinstance(media, dict):
                            attachment = {
                                'name': media.get('filename') or key,
                                'mime': media.get('mime_type'),
                                # Media ids only — v1 downloads nothing.
                                'url': media.get('id'),
                            }
                            text = text or media.get('caption') or ''
                    events.append({
                        'kind': 'message',
                        'external_id': wa_id,
                        'external_message_id': message.get('id'),
                        'peer_name': names.get(wa_id),
                        'message_type': mtype,
                        'text': text,
                        'attachment': attachment,
                        'event_at': _utc_from_unix(message.get('timestamp')),
                        'raw': message,
                    })
                for status in value.get('statuses') or []:
                    events.append({
                        'kind': 'status',
                        'external_message_id': status.get('id'),
                        'status': status.get('status'),
                        'error': json.dumps(status.get('errors'))
                                 if status.get('errors') else None,
                    })
        _logger.info('care_channels: whatsapp inbound %s event(s) on connection %s',
                     len(events), self.connection.id)
        return events

    def send_message(self, identity, text):
        conn = self.connection
        token = conn._get_secret('access_token')
        if not token or not conn.resource_external_id:
            raise ChannelSendError('whatsapp connection is not configured')
        url = '%s/%s/%s/messages' % (self._api_base(GRAPH_BASE), GRAPH_VERSION,
                                     conn.resource_external_id)
        data = self._post(url, json_body={
            'messaging_product': 'whatsapp',
            'recipient_type': 'individual',
            'to': identity.external_id,
            'type': 'text',
            'text': {'preview_url': False, 'body': text},
        }, headers={'Authorization': 'Bearer %s' % token})
        messages = data.get('messages') or [{}]
        return {'external_message_id': messages[0].get('id'), 'state': 'sent'}


@register_adapter('fb')
class MessengerAdapter(_StubAdapter):
    """Facebook Messenger via FB Login for Business. Page tokens obtained
    through the long-lived path do not expire."""
    _capabilities = {
        'mode': MODE_OAUTH_POPUP,
        'needs_platform_app': True,
        'platform_providers': ['meta'],
        'resource_selection': True,      # Page picker from /me/accounts
        'webhook_auto': True,            # POST /{page}/subscribed_apps
        'supports_refresh': False,
        'supports_revoke': True,
        'required_checks': ['authorization_valid', 'scopes_granted',
                            'resource_selected', 'webhook_configured',
                            'outbound_ok'],
        'guide_steps': ['channel_hub.guide.fb.signin',
                        'channel_hub.guide.fb.page',
                        'channel_hub.guide.fb.connecting',
                        'channel_hub.guide.fb.test'],
    }

    # -- messaging (CC-B) ----------------------------------------------
    def parse_inbound(self, payload):
        """Messenger webhook → normalised events for THIS page."""
        events = []
        mine = self.connection.resource_external_id
        for entry in (payload or {}).get('entry') or []:
            if mine and str(entry.get('id')) != str(mine):
                continue
            for item in entry.get('messaging') or []:
                message = item.get('message') or {}
                if not message or message.get('is_echo'):
                    # Echoes are our OWN outbound coming back; ingesting them
                    # would double every agent reply.
                    continue
                sender = (item.get('sender') or {}).get('id')
                attachment = {}
                mtype = 'text'
                for att in message.get('attachments') or []:
                    mtype = {'image': 'image', 'file': 'file',
                             'location': 'location'}.get(att.get('type'), 'other')
                    payload_att = att.get('payload') or {}
                    attachment = {'url': payload_att.get('url'),
                                  'name': att.get('type'),
                                  'mime': None}
                events.append({
                    'kind': 'message',
                    'external_id': sender,
                    'external_message_id': message.get('mid'),
                    # Messenger sends no profile name in the webhook; the
                    # Graph profile call is a CC-E enrichment, not a v1 need.
                    'peer_name': None,
                    'message_type': mtype,
                    'text': message.get('text') or '',
                    'attachment': attachment,
                    'event_at': _utc_from_unix(
                        (item['timestamp'] / 1000) if item.get('timestamp')
                        else None),
                    'raw': item,
                })
        _logger.info('care_channels: fb inbound %s event(s) on connection %s',
                     len(events), self.connection.id)
        return events

    def send_message(self, identity, text):
        conn = self.connection
        token = conn._get_secret('access_token')
        if not token:
            raise ChannelSendError('messenger connection is not configured')
        url = '%s/%s/me/messages' % (self._api_base(GRAPH_BASE), GRAPH_VERSION)
        data = self._post(
            url,
            params={'access_token': token},
            json_body={
                'recipient': {'id': identity.external_id},
                'messaging_type': 'RESPONSE',
                'message': {'text': text},
            })
        return {'external_message_id': data.get('message_id'), 'state': 'sent'}


@register_adapter('zalo')
class ZaloAdapter(_StubAdapter):
    """Zalo OA. OAuth v4 with mandatory PKCE S256; access token 25 h and a
    single-use rotating refresh token — hence token_fresh is a required check
    and the refresh lock (connection._with_refresh_lock) matters here first.
    Webhook URL is portal-only (one per app), so webhook_auto is False."""
    _capabilities = {
        'mode': MODE_OAUTH_POPUP,
        'needs_platform_app': True,
        'platform_providers': ['zalo'],
        'resource_selection': False,     # the OA is fixed by the grant
        'webhook_auto': False,           # developers.zalo.me portal, one URL/app
        'supports_refresh': True,
        'supports_revoke': False,
        'required_checks': ['authorization_valid', 'resource_selected',
                            'webhook_configured', 'webhook_verified',
                            'outbound_ok', 'token_fresh'],
        'guide_steps': ['channel_hub.guide.zalo.signin',
                        'channel_hub.guide.zalo.webhook',
                        'channel_hub.guide.zalo.verify',
                        'channel_hub.guide.zalo.test'],
    }

    # ------------------------------------------------------------------
    # Plumbing
    # ------------------------------------------------------------------
    def _oauth_base(self):
        return self._api_base(ZALO_OAUTH_BASE)

    def _openapi_base(self):
        return self._api_base(ZALO_OPENAPI_BASE)

    def _platform_app(self):
        """The deployment's Zalo app (plane 1). Absent ⇒ refuse, never guess."""
        app = self.env['channel.platform.app'].sudo()._get_for_provider('zalo')
        if not app or not app.client_id:
            raise ChannelSendError(
                'the Zalo platform application is not configured')
        return app

    def _app_secret(self, app=None):
        secret = (app or self._platform_app())._get_secret()
        if not secret:
            raise ChannelSendError(
                'the Zalo platform application has no secret')
        return secret

    def _base_url(self):
        return (self.env['ir.config_parameter'].sudo()
                .get_param('web.base.url') or '').strip().rstrip('/')

    def _redirect_uri(self):
        return '%s%s' % (self._base_url(), ZALO_CALLBACK_PATH)

    def webhook_url(self):
        """The ONE webhook URL for this deployment (portal-only, one per app)."""
        return '%s%s' % (self._base_url(), ZALO_WEBHOOK_PATH)

    # ------------------------------------------------------------------
    # Authorization — OAuth v4 with MANDATORY PKCE S256
    # ------------------------------------------------------------------
    def authorize_url(self, session, state, code_challenge):
        """The URL the tenant's popup opens.

        ``state`` and ``code_challenge`` are passed IN rather than read off
        ``session``: the raw state exists exactly once, in the return value of
        ``oauth.session.create_for`` (the row stores only its sha256), so it
        cannot be recovered from the record — which is the point of hashing it.
        No secret material of any kind goes into this URL; the app id is public.
        """
        app = self._platform_app()
        if not state or not code_challenge:
            raise ChannelSendError('zalo requires a state and a PKCE challenge')
        params = {
            'app_id': app.client_id,
            'redirect_uri': self._redirect_uri(),
            'code_challenge': code_challenge,
            'state': state,
        }
        return '%s%s?%s' % (self._oauth_base(), ZALO_PERMISSION_PATH,
                            urlencode(params))

    def handle_callback(self, session, params):
        """Exchange the authorization code, learn who we are, record readiness.

        Called by ``care.channel.oauth.session._handle_callback`` inside a
        savepoint, AFTER the single-use state has been burned.
        """
        conn = self.connection
        code = (params or {}).get('code') or (params or {}).get('oa_code')
        if not code:
            raise ChannelSendError('the Zalo callback carried no code')
        verifier = session._get_pkce_verifier()
        if not verifier:
            raise ChannelSendError(
                'this authorization attempt has no PKCE verifier')
        app = self._platform_app()
        data = self._form_post(
            '%s%s' % (self._oauth_base(), ZALO_TOKEN_PATH),
            data={
                'app_id': app.client_id,
                'grant_type': 'authorization_code',
                'code': code,
                'code_verifier': verifier,
            },
            headers={'secret_key': self._app_secret(app)})
        tokens = self._read_token_response(data)

        # Persist BEFORE anything else touches the wire: Zalo's refresh token
        # is single-use, so a token we hold but never stored is a dead OA.
        self._store_tokens(**tokens)

        oa = self._fetch_oa(tokens['access_token'])
        conn.sudo()._internal().write({
            'resource_external_id': oa['id'],
            'resource_display_name': oa['name'] or oa['id'],
        })
        Check = self.env['care.channel.readiness.check']
        for key in ('authorization_valid', 'resource_selected', 'token_fresh'):
            Check.upsert_check(conn.sudo(), key, 'pass')
        try:
            conn.sudo()._transition('configuring',
                                    reason='zalo authorization complete')
        except UserError:
            # Already past this point (a re-authorization of a live OA): the
            # state machine refusing a backwards move is not a failure here.
            _logger.info('care_channels: zalo connection %s stays in %s after '
                         'authorization', conn.id, conn.state)
        self._sync_legacy_config(oa)
        # NOTHING about the grant is returned: the engine renders a generic
        # page and the browser learns the outcome by re-reading the Center.
        return {'ok': True, 'next_step': 'webhook'}

    # ------------------------------------------------------------------
    # Refresh — single-use rotation under the row lock
    # ------------------------------------------------------------------
    def refresh_authorization(self):
        """Rotate the grant. Returns ``'locked'`` when another worker is on it.

        Two concurrent refreshes would burn the 3-month grant: Zalo issues a
        NEW refresh token on every use and invalidates the old one the moment
        it answers.
        """
        return self.connection.sudo()._with_refresh_lock(self._do_refresh)

    def _do_refresh(self):
        conn = self.connection
        # The COMMITTED token, not this snapshot's: the refresh lock is
        # advisory (CC-D review), so nothing forces a serialisation error on a
        # transaction that started before another worker rotated. Spending a
        # single-use token twice is how a 3-month grant dies.
        refresh_token = conn.sudo()._committed_secret('refresh_token')
        if not refresh_token:
            raise ChannelSendError('this Zalo connection has no refresh token')
        app = self._platform_app()
        Audit = self.env['care.channel.audit']
        Check = self.env['care.channel.readiness.check']
        try:
            data = self._form_post(
                '%s%s' % (self._oauth_base(), ZALO_TOKEN_PATH),
                data={
                    'app_id': app.client_id,
                    'grant_type': 'refresh_token',
                    'refresh_token': refresh_token,
                },
                headers={'secret_key': self._app_secret(app)})
            tokens = self._read_token_response(data)
        except ChannelSendError as exc:
            # The OLD refresh token is untouched — we wrote nothing. Only an
            # auth-class refusal costs the connection its token_fresh check; a
            # network wobble must not tear a working channel down.
            Audit._log('refresh_fail', connection=conn, detail=exc)
            if self._is_auth_failure(exc):
                Check.upsert_check(conn.sudo(), 'token_fresh', 'fail',
                                   detail=exc)
            raise
        self._store_tokens(**tokens)
        Check.upsert_check(conn.sudo(), 'token_fresh', 'pass')
        Audit._log('refresh_ok', connection=conn, detail='zalo token rotated')
        return {'ok': True,
                'token_expires_at': tokens.get('token_expires_at')}

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------
    def health_check(self):
        conn = self.connection
        if not conn.sudo().access_token_enc:
            return {'ok': False, 'error': 'zalo connection is not authorized'}
        expires = conn.token_expires_at
        if expires and expires <= fields.Datetime.now() + timedelta(
                hours=ZALO_REFRESH_AHEAD_HOURS):
            try:
                self.refresh_authorization()
            except ChannelSendError as exc:
                return {'ok': False, 'error': str(exc)}
            conn.invalidate_recordset(['access_token_enc', 'token_expires_at'])
        try:
            oa = self._fetch_oa(conn.sudo()._get_secret('access_token'))
        except ChannelSendError as exc:
            return {'ok': False, 'error': str(exc)}
        return {'ok': True, 'resource': oa['id']}

    def verify_webhook(self, raw_body, headers):
        # Imported here: webhook_verify imports nothing from this module, and
        # a module-level import would still be a needless cycle risk.
        from .webhook_verify import verify_zalo
        return verify_zalo(self.connection, raw_body, headers)

    # ------------------------------------------------------------------
    # Shared internals
    # ------------------------------------------------------------------
    def _read_token_response(self, data):
        """Zalo answers 200 with an error BODY as readily as it answers 4xx."""
        data = data or {}
        access = data.get('access_token')
        if not access:
            raise ChannelSendError('zalo refused the token request: %s' % (
                data.get('error_description') or data.get('error_name')
                or data.get('message') or data.get('error') or 'unknown error'))
        try:
            expires_in = int(data.get('expires_in') or 0)
        except (TypeError, ValueError):
            expires_in = 0
        return {
            'access_token': access,
            'refresh_token': data.get('refresh_token') or None,
            'token_expires_at': (fields.Datetime.now()
                                 + timedelta(seconds=expires_in)
                                 if expires_in else None),
        }

    def _store_tokens(self, access_token=None, refresh_token=None,
                      token_expires_at=None, granted_scopes=None):
        """Persist rotated credentials, fresh cursor first.

        ``_persist_refreshed_tokens`` commits on an independent cursor so a
        rotation survives a later rollback of the request transaction. Under
        ``--test-enable`` that cursor cannot see a record the test transaction
        created (ledger §5.63), so the write happens in-transaction instead —
        the same either/or the CC-B send-failure writer uses, and what lets the
        suites assert on the stored ciphertext.
        """
        conn = self.connection
        persisted = False
        if not (tools.config.get('test_enable') or tools.config.get('test_file')):
            persisted = conn.sudo()._persist_refreshed_tokens(
                access_token=access_token, refresh_token=refresh_token,
                token_expires_at=token_expires_at,
                granted_scopes=granted_scopes)
        if persisted:
            return True
        vals = {}
        if access_token is not None:
            vals['access_token_enc'] = channel_crypto.encrypt(
                self.env, access_token)
        if refresh_token is not None:
            vals['refresh_token_enc'] = channel_crypto.encrypt(
                self.env, refresh_token)
        if token_expires_at is not None:
            vals['token_expires_at'] = token_expires_at
        if granted_scopes is not None:
            vals['granted_scopes'] = granted_scopes
        if vals:
            conn.sudo()._internal().write(vals)
        return bool(vals)

    def _fetch_oa(self, access_token):
        """``getoa`` — the OA's own id and name. This IS resource selection:
        the grant fixes which Official Account we were given."""
        data = self._get('%s%s' % (self._openapi_base(), ZALO_GETOA_PATH),
                         headers={'access_token': access_token})
        if data.get('error'):
            raise ChannelSendError('zalo refused the profile call: %s'
                                   % (data.get('message') or data.get('error')))
        payload = data.get('data') or {}
        oa_id = str(payload.get('oa_id') or '')
        if not oa_id:
            raise ChannelSendError('zalo returned no OA identity')
        return {'id': oa_id, 'name': payload.get('name') or ''}

    def _sync_legacy_config(self, oa):
        """Hand the news to health_zalo, if it is installed.

        SOFT reference on purpose: health_zalo depends on THIS module, never
        the other way round, so the framework must work with or without it.
        """
        env = self.env
        if 'zalo.config' not in env:
            return False
        try:
            return env['zalo.config'].sudo()._sync_from_connection(
                self.connection, oa_id=oa.get('id'), oa_name=oa.get('name'))
        except Exception:  # noqa: BLE001 — the legacy bridge is never fatal
            _logger.exception('care_channels: zalo legacy config sync failed '
                              'for connection %s', self.connection.id)
            return False


@register_adapter('zns')
class ZnsAdapter(_StubAdapter):
    """ZNS is a capability OF the Zalo OA connection, not a separate sign-in:
    ``parent_channel`` is how the Center renders it as a sub-card of Zalo.
    Template approval is a human Zalo review — surfaced as provider_approvals,
    never as an error."""
    _capabilities = {
        'mode': MODE_OAUTH_POPUP,
        'parent_channel': 'zalo',
        'needs_platform_app': True,
        'platform_providers': ['zalo'],
        'resource_selection': False,
        'webhook_auto': False,
        'supports_refresh': True,
        'supports_revoke': False,
        'required_checks': ['authorization_valid', 'provider_approvals'],
        'guide_steps': ['channel_hub.guide.zns.templates'],
    }


@register_adapter('telegram')
class TelegramAdapter(_StubAdapter):
    """No OAuth exists: the tenant creates a bot in BotFather and pastes the
    token (guided_secret). setWebhook is fully automatable."""
    _capabilities = {
        'mode': MODE_GUIDED_SECRET,
        'needs_platform_app': False,
        'resource_selection': False,     # the bot is fixed by the token
        'webhook_auto': True,            # setWebhook with secret_token
        'supports_refresh': False,
        'supports_revoke': True,
        'required_checks': ['authorization_valid', 'resource_selected',
                            'webhook_configured', 'outbound_ok'],
        'guide_steps': ['channel_hub.guide.telegram.botfather',
                        'channel_hub.guide.telegram.paste',
                        'channel_hub.guide.telegram.connecting',
                        'channel_hub.guide.telegram.test'],
    }

    # -- guided-secret onboarding (CC-C) --------------------------------
    def validate_token(self, token):
        """``getMe`` — the ONLY honest way to know a pasted token is real.

        Takes the token as an ARGUMENT rather than reading the connection:
        the Center validates before it stores anything, so a token that turns
        out to be wrong never touches the database.

        Returns ``{'id', 'username', 'first_name'}``; raises
        ``ChannelSendError`` on refusal, network failure or a reply with no
        bot identity in it.
        """
        token = (token or '').strip()
        if not token:
            raise ChannelSendError('telegram token is empty')
        url = '%s/bot%s/getMe' % (self._api_base(TELEGRAM_BASE), token)
        data = self._get(url)
        if not data.get('ok'):
            raise ChannelSendError('telegram refused: %s'
                                   % data.get('description'))
        result = data.get('result') or {}
        if not result.get('id'):
            raise ChannelSendError('telegram returned no bot identity')
        return {
            'id': str(result['id']),
            'username': result.get('username') or '',
            'first_name': result.get('first_name') or '',
        }

    def register_webhook(self, url=None, secret_token=None):
        """``setWebhook`` — Telegram is the one channel we can wire ourselves.

        ``allowed_updates`` is narrowed to ``message``: we ingest nothing else,
        and asking for less is the smaller blast radius. The caller owns the
        URL (it holds the path secret) and the https check.
        """
        token = self.connection._get_secret('provider_secret')
        if not token:
            raise ChannelSendError('telegram bot token is not configured')
        if not url or not secret_token:
            raise ChannelSendError('telegram webhook url is not configured')
        api_url = '%s/bot%s/setWebhook' % (self._api_base(TELEGRAM_BASE), token)
        data = self._post(api_url, json_body={
            'url': url,
            'secret_token': secret_token,
            'allowed_updates': ['message'],
        })
        if not data.get('ok', True):
            raise ChannelSendError('telegram refused: %s'
                                   % data.get('description'))
        _logger.info('care_channels: telegram webhook registered on '
                     'connection %s', self.connection.id)
        return {'ok': True}

    # -- messaging (CC-B) ----------------------------------------------
    def parse_inbound(self, payload):
        """One Telegram ``Update`` → at most one event.

        The connection is already resolved by the URL path secret, so there is
        no per-tenant filtering to do here.
        """
        message = (payload or {}).get('message') or \
            (payload or {}).get('edited_message') or {}
        chat = message.get('chat') or {}
        if not chat.get('id') or not message.get('message_id'):
            return []
        sender = message.get('from') or {}
        name = ' '.join(p for p in (sender.get('first_name'),
                                    sender.get('last_name')) if p) \
            or sender.get('username')
        mtype = 'text'
        attachment = {}
        if message.get('photo'):
            mtype = 'image'
            attachment = {'name': 'photo', 'url': None, 'mime': None}
        elif message.get('document'):
            mtype = 'file'
            doc = message['document']
            attachment = {'name': doc.get('file_name'),
                          'mime': doc.get('mime_type'), 'url': None}
        elif message.get('location'):
            mtype = 'location'
        _logger.info('care_channels: telegram inbound 1 event on connection %s',
                     self.connection.id)
        return [{
            'kind': 'message',
            'external_id': str(chat['id']),
            'external_message_id': '%s:%s' % (chat['id'],
                                              message['message_id']),
            'peer_name': name,
            'message_type': mtype,
            'text': message.get('text') or message.get('caption') or '',
            'attachment': attachment,
            'event_at': _utc_from_unix(message.get('date')),
            'raw': message,
        }]

    def send_message(self, identity, text):
        token = self.connection._get_secret('provider_secret')
        if not token:
            raise ChannelSendError('telegram bot token is not configured')
        url = '%s/bot%s/sendMessage' % (self._api_base(TELEGRAM_BASE), token)
        data = self._post(url, json_body={'chat_id': identity.external_id,
                                          'text': text})
        if not data.get('ok', True):
            raise ChannelSendError('telegram refused: %s'
                                   % data.get('description'))
        result = data.get('result') or {}
        chat_id = (result.get('chat') or {}).get('id', identity.external_id)
        message_id = result.get('message_id')
        return {
            'external_message_id': ('%s:%s' % (chat_id, message_id)
                                    if message_id else None),
            'state': 'sent',
        }


@register_adapter('email')
class EmailAdapter(_StubAdapter):
    """Gmail / Microsoft 365 via the Odoo XOAUTH2 mixins (CC-F). Inbound is an
    IMAP poll rather than a webhook, so inbound_ok is proven separately from
    outbound_ok and webhook_auto is meaningless (False)."""
    _capabilities = {
        'mode': MODE_OAUTH_POPUP,
        'needs_platform_app': True,
        # Either provider makes the card offerable; CC-F picks per tenant.
        'platform_providers': ['google', 'microsoft'],
        'resource_selection': False,     # the mailbox IS the authorizing account
        'webhook_auto': False,           # n/a — IMAP poll
        'supports_refresh': True,
        'supports_revoke': True,
        'required_checks': ['authorization_valid', 'resource_selected',
                            'outbound_ok', 'inbound_ok'],
        'guide_steps': ['channel_hub.guide.email.signin',
                        'channel_hub.guide.email.mailbox',
                        'channel_hub.guide.email.test'],
    }


@register_adapter('call')
class CallAdapter(_StubAdapter):
    """VoIP24h: API key + secret exchanged for a short-lived bearer — a guided
    credential entry, not OAuth. Webhook registration is portal/support-side.
    Outbound messaging does not exist for telephony, so inbound_ok (call events
    arriving) is the proof of life, not outbound_ok."""
    _capabilities = {
        'mode': MODE_GUIDED_SECRET,
        'needs_platform_app': False,
        'resource_selection': False,     # the PBX account is typed in
        'webhook_auto': False,           # portal/support-set
        'supports_refresh': False,
        'supports_revoke': False,
        'required_checks': ['authorization_valid', 'resource_selected',
                            'webhook_configured', 'inbound_ok'],
        'guide_steps': ['channel_hub.guide.call.credentials',
                        'channel_hub.guide.call.webhook',
                        'channel_hub.guide.call.test'],
    }


@register_adapter('webchat')
class WebChatAdapter(_StubAdapter):
    """Our own widget: nothing to authorize with anyone. One click enables it;
    readiness is "an origin is configured" + "a message arrived"."""
    _capabilities = {
        'mode': MODE_ONE_CLICK,
        'needs_platform_app': False,
        'resource_selection': False,
        'webhook_auto': False,           # n/a — our own public route
        'supports_refresh': False,
        'supports_revoke': False,
        'required_checks': ['resource_selected', 'inbound_ok'],
        'guide_steps': ['channel_hub.guide.webchat.enable',
                        'channel_hub.guide.webchat.embed',
                        'channel_hub.guide.webchat.verify'],
    }

    # -- messaging (CC-B) ----------------------------------------------
    def parse_inbound(self, payload):
        """The widget posts through our own route, which already normalised
        the event — this exists so every channel has the same shape."""
        payload = payload or {}
        session = (payload.get('session') or '').strip()
        text = (payload.get('text') or '').strip()
        if not session or not text:
            return []
        return [{
            'kind': 'message',
            'external_id': session,
            'external_message_id': payload.get('external_message_id')
            or uuid.uuid4().hex,
            'peer_name': payload.get('peer_name'),
            'message_type': 'text',
            'text': text,
            'attachment': {},
            'event_at': None,
            # No raw payload: it is our own request body, and storing it would
            # duplicate the message text for no benefit.
            'raw': None,
        }]

    def send_message(self, identity, text):
        """No HTTP exists: creating the outgoing row IS delivery. The widget's
        next poll picks it up."""
        _logger.info('care_channels: webchat outbound on connection %s',
                     self.connection.id)
        return {'external_message_id': uuid.uuid4().hex, 'state': 'sent'}
