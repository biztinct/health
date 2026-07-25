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

Deliberately no provider HTTP anywhere in this file — CC-D/CC-E/CC-F implement
the real adapters by subclassing/replacing these stubs.
"""
import logging

_logger = logging.getLogger(__name__)

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


@register_adapter('fb')
class MessengerAdapter(_StubAdapter):
    """Facebook Messenger via FB Login for Business. Page tokens obtained
    through the long-lived path do not expire."""
    _capabilities = {
        'mode': MODE_OAUTH_POPUP,
        'needs_platform_app': True,
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


@register_adapter('zalo')
class ZaloAdapter(_StubAdapter):
    """Zalo OA. OAuth v4 with mandatory PKCE S256; access token 25 h and a
    single-use rotating refresh token — hence token_fresh is a required check
    and the refresh lock (connection._with_refresh_lock) matters here first.
    Webhook URL is portal-only (one per app), so webhook_auto is False."""
    _capabilities = {
        'mode': MODE_OAUTH_POPUP,
        'needs_platform_app': True,
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


@register_adapter('email')
class EmailAdapter(_StubAdapter):
    """Gmail / Microsoft 365 via the Odoo XOAUTH2 mixins (CC-F). Inbound is an
    IMAP poll rather than a webhook, so inbound_ok is proven separately from
    outbound_ok and webhook_auto is meaningless (False)."""
    _capabilities = {
        'mode': MODE_OAUTH_POPUP,
        'needs_platform_app': True,
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
