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
from datetime import datetime, timezone

import requests

_logger = logging.getLogger(__name__)

# Every provider call is bounded: a hung provider must not hold a worker.
HTTP_TIMEOUT = 15

GRAPH_BASE = 'https://graph.facebook.com'
GRAPH_VERSION = 'v21.0'
TELEGRAM_BASE = 'https://api.telegram.org'

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
