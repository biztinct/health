# -*- coding: utf-8 -*-
{
    'name': 'Health VoIP24h Integration',
    'version': '19.0.3.2.0',
    'category': 'Healthcare/Telephony',
    'summary': 'Call history, live call notifications and browser calling over VoIP24h',
    'description': """
Health VoIP24h Integration
===========================

Three capabilities that are enabled independently, because they depend on
different things and one working proves nothing about the others:

**Call history** — completed call records arrive on an authenticated call-back
address, land in a durable inbox, and are reconciled into one row per customer
interaction with its legs preserved. Recording links are recorded as metadata;
nothing is fetched on sight.

**Live awareness** — ringing/answered/ended events, delivered to the people
entitled to see them on their own notification channel. There is no global bus
topic: an obscure channel name is not access control.

**Browser phone** — dial, answer, reject, hang up, mute, hold, guarded
transfer and guarded keypad tones, through the supplier's WebRTC SDK running in
an isolated frame, with one owning browser per extension enforced in the
database.

What this module will not do
----------------------------
Every provider endpoint without a documented contract is refused rather than
guessed: fetching past calls, listing extensions and dialling from the server
are each behind an explicit "confirmed" flag that only a human who captured the
contract can set. An unknown value from the phone system becomes a visible
``unknown``, never a default ``answered``. A call-back is acknowledged only
after it is durably stored.

Contracts implemented from the supplier's documentation: v3 authentication,
v3 completed-call subscription (register and remove), the completed-call
delivery payload, the live-event delivery payload, and the WebRTC SDK surface.
    """,
    'author': 'I Am Dream Catcher Ltd',
    'website': 'https://www.vafhs.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'web',
        'mail',
        'contacts',
        'crm',
        'hr',
        'health_base',
        'health_crm',
        'bus',
    ],
    'data': [
        # Security
        'security/voip24h_security.xml',
        'security/ir.model.access.csv',

        # Data
        'data/voip24h_data.xml',
        'data/voip24h_cron.xml',

        # Wizards (before views: the config form and menus reference the action)
        'wizard/voip_sync_wizard_views.xml',

        # Views
        'views/voip_config_views.xml',
        'views/voip_call_session_views.xml',
        'views/voip_call_log_views.xml',
        'views/voip_call_recording_views.xml',
        'views/voip_extension_views.xml',
        'views/voip_sdk_host.xml',
        'views/res_partner_views.xml',
        'views/crm_lead_views.xml',
        'views/voip_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            # Plain CSS first: libsass mangles data-URI mask icons inside
            # .scss and takes the whole bundle down with them (ledger §5.51).
            'health_voip24h/static/src/css/voip_phone_icons.css',
            'health_voip24h/static/src/scss/voip_phone_panel.scss',
            'health_voip24h/static/src/scss/voip_dashboard.scss',

            'health_voip24h/static/src/js/voip_phone_service.js',
            'health_voip24h/static/src/js/voip_phone_panel.js',
            'health_voip24h/static/src/js/click_to_dial_widget.js',

            'health_voip24h/static/src/xml/voip_phone_panel.xml',
            'health_voip24h/static/src/xml/click_to_dial_widget.xml',
        ],
        # NOT in the backend bundle: sdk_host_bridge.js runs inside the
        # isolated SDK frame alongside the supplier's legacy globals (jQuery
        # 1.9, adapter.js 0.15.5). Putting those in the Odoo bundle would
        # replace the framework's own JavaScript dependencies everywhere.
    },
    'external_dependencies': {
        'python': ['requests', 'cryptography'],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
