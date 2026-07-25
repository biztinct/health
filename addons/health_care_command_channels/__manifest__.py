# -*- coding: utf-8 -*-
{
    'name': 'Care Command — Channel Connection Framework',
    'version': '19.0.1.0.0',
    'category': 'Healthcare/CRM',
    'summary': 'Provider-neutral channel connection core: encrypted credentials, '
               'OAuth engine, readiness model, adapter registry',
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

Non-goals of this phase: no messaging, no provider HTTP, no webhook message
routes, no Center UI, no migration of the legacy zalo/voip configs.
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
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/channel_hub_security.xml',
        'views/oauth_templates.xml',
        'views/platform_app_views.xml',
        'views/channel_connection_views.xml',
        'views/res_config_settings_views.xml',
        'views/menus.xml',
        'data/ir_cron.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
    'sequence': 126,
}
