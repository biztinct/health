# -*- coding: utf-8 -*-
{
    'name': 'Care Command — Channel Connection Framework',
    'version': '19.0.3.0.0',
    'category': 'Healthcare/CRM',
    'summary': 'Provider-neutral channel connections + the WhatsApp / Messenger / '
               'Telegram / Web chat message spine',
    'description': """
Channel Connection Center — Phase CC-A (framework core)
=======================================================

The provider-neutral plumbing the Channel Connection Center is built on.
**Nothing user-visible changes in Care Command**: installing this module adds
two backend setup menus and nothing else. The dock, workspace and composer are
untouched.

What ships here:

- ``services/channel_crypto.py`` — AES-256-GCM secret encryption at rest with a
  dedicated subkey (token prefix ``chs$1$``), self-contained (no coupling to
  health_phi_encryption). ``decrypt()`` RAISES on corruption — a corrupted
  secret must never be handed to a provider.
- **Two credential planes**: ``channel.platform.app`` (per-deployment provider
  apps, platform-operator only) and ``care.channel.connection`` (per-company
  tenant authorizations).
- ``care.channel.oauth.session`` — single-use, hashed-state, PKCE-S256
  authorization attempts with a 10-minute expiry.
- ``care.channel.readiness.check`` — explicit readiness. A connection is NEVER
  "Ready" because a record exists; ``ready`` is derived from every check the
  channel's adapter declares as required.
- ``care.channel.audit`` — append-only ops audit, every detail string redacted.
- ``services/adapters.py`` — the adapter registry + capability contract, with
  declaration-only stubs for all 8 channel keys.
- Fail-closed public OAuth callback (``/channel_hub/oauth/callback/<provider>``)
  — rate-limited, non-oracle, never echoes state/code.
- Health + session-purge crons.

Channel Connection Center — Phase CC-B (message spine + 4 adapters)
===================================================================

The four chat channels become real rails on the SAME ``care.conversation``
spine the live channels already use:

- ``care.channel.identity`` — the external peer registry (wa_id / PSID /
  Telegram chat id / web-chat session), and the one anchor a first contact has.
- ``care.channel.message`` — one message store for all four channels, with a
  partial unique index on ``(connection_id, external_message_id)`` so a
  redelivered webhook lands once.
- ``_ingest_inbound`` — the single funnel: dedupe → identity → message row →
  conversation upsert inside ``cr.savepoint()`` → readiness wiring.
- Fail-closed raw-http webhooks for Meta (WhatsApp + Messenger) and Telegram,
  multi-tenant routed by the resource id in the payload, plus the anonymous
  web-chat widget on rate-limited public routes.
- ``action_send_channel`` — the ONE outbound trigger: a human pressing send.
- Traffic drives truth: an inbound event proves the webhook, a successful send
  proves outbound, a 401 costs the connection its ``authorization_valid``
  check — which is what the dock, the counts and the composer read.

Channel Connection Center — Phase CC-C (the Center itself)
==========================================================

The tenant-facing Center: one OWL client action with a catalogue of all eight
channels and a four-step stepper, plus the server endpoints behind it.

- ``center_overview`` / ``center_begin`` / ``center_test`` /
  ``center_disconnect`` / ``center_reconnect`` — every write through
  ``sudo()._internal()``, every failure a redacted ``UserError``, and no
  credential material in any return value.
- **Web chat is one click**: allowed website addresses, an embed snippet with
  a ``?v=`` cache stamp, and the first real widget message finishes the setup.
- **Telegram is a guided wizard**: BotFather → paste the key → validated with
  ``getMe`` before anything is stored → ``setWebhook`` (https only) → the
  tenant messages the bot → a synthetic reply proves outbound.
- Readiness stays DERIVED. Amendment F1 closes the lockout in which the first
  proving inbound demoted a ``testing`` connection to ``action_required`` —
  which is not ingestable — and stranded the channel mid-setup.
- Tenant administrators (``health_user_admin.group_health_user_admin``) get
  connection read/write/create (never unlink), read on readiness/audit/
  identity/message, and NOTHING on ``channel.platform.app``: the platform
  plane stays with the platform operator.

Non-goals of this phase: no OAuth popup or code exchange (CC-D/E), no Meta JS
SDK, no Zalo repair, no email/VoIP wizard, no bus/websocket, no new public
routes, no real provider call anywhere in the tests, no credentials on any
server.
    """,
    'author': 'I Am Dream Catcher Ltd',
    'website': 'https://vafhs.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'web',
        'mail',
        'health_care_command',
        'health_api_gateway',
        # CC-C: the Center's audience. The tenant-admin ACL rows and the
        # Center menu both reference health_user_admin.group_health_user_admin,
        # so the dependency is hard from this phase on (CC-A deferred it).
        'health_user_admin',
        # CC-C: the CMS shell is where these users actually are, and the
        # backend menuitem alone is unreachable from it (see the sidebar seed).
        'health_cms_sidebar',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/channel_hub_security.xml',
        'views/oauth_templates.xml',
        'views/webchat_templates.xml',
        'views/platform_app_views.xml',
        'views/channel_connection_views.xml',
        'views/channel_message_views.xml',
        'views/res_config_settings_views.xml',
        'views/channel_center_views.xml',
        'views/menus.xml',
        'data/ir_cron.xml',
        'data/cms_sidebar_items_channel_center.xml',
    ],
    'assets': {
        'web.assets_backend': [
            # plain CSS first (data-URI mask icons — libsass mangles them
            # inside .scss, ledger §5.51)
            'health_care_command_channels/static/src/center/channel_center.css',
            'health_care_command_channels/static/src/center/channel_center.scss',
            'health_care_command_channels/static/src/center/channel_center.js',
            'health_care_command_channels/static/src/center/channel_center.xml',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': False,
    'sequence': 126,
}
