# -*- coding: utf-8 -*-
{
    'name': 'Health VoIP24h Integration',
    'version': '19.0.2.0.0',
    'category': 'Healthcare/Telephony',
    'summary': 'VoIP24h call logging, analytics, and telephony integration for VAFHS',
    'description': """
Health VoIP24h Integration
===========================

Comprehensive VoIP24h integration module that captures call logs, recordings,
and metadata via API integration.

Key Features:
-------------
* Call Detail Record (CDR) tracking and synchronization
* Automatic call log retrieval every 15 minutes
* Call recordings download and playback
* Click-to-dial from contact/lead forms
* Real-time incoming call popups
* Professional analytics dashboard
* Automatic contact/lead matching
* Call functionality control (enable/disable calling features)
* Activity management for missed calls

Master Switch:
--------------
* Enable/disable calling functionality while maintaining data collection
* Granular controls for outgoing calls and incoming popups
* Full call logs, recordings, and analytics continue when calling is disabled
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

        # Wizards (before views: config form + menus reference the wizard action)
        'wizard/voip_sync_wizard_views.xml',

        # Views
        'views/voip_config_views.xml',
        'views/voip_call_log_views.xml',
        'views/voip_call_recording_views.xml',
        'views/voip_extension_views.xml',
        'views/res_partner_views.xml',
        'views/crm_lead_views.xml',
        'views/voip_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            # JavaScript
            'health_voip24h/static/src/js/click_to_dial_widget.js',
            'health_voip24h/static/src/js/call_popup_service.js',

            # XML Templates
            'health_voip24h/static/src/xml/click_to_dial_widget.xml',
            'health_voip24h/static/src/xml/call_popup.xml',

            # SCSS
            'health_voip24h/static/src/scss/voip_dashboard.scss',
            'health_voip24h/static/src/scss/call_popup.scss',
        ],
    },
    'external_dependencies': {
        'python': ['requests'],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
