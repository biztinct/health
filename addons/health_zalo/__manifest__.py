# -*- coding: utf-8 -*-
{
    'name': 'Health Zalo Integration',
    'version': '18.0.1.0.0',
    'category': 'Healthcare/Communication',
    'summary': 'Zalo Official Account integration for patient messaging and notifications',
    'description': """
Health Zalo Integration Module
================================
Integrates Zalo Official Account messaging into the Healthcare system.

Key Features:
* Real-time chat interface with Zalo users
* Zalo contact integration with patients and partners
* Webhook support for incoming messages
* OAuth 2.0 authentication with automatic token refresh
* Notification system for incoming Zalo messages
* Call and chat actions from contact records
* Message history and conversation management
* Attachment support (images, files)
* Template-based notifications via ZNS (Zalo Notification Service)

Technical Stack:
* Zalo Official Account API v2.0
* OAuth 2.0 for authentication
* Webhooks for real-time updates
* Odoo bus.bus for live notifications
* Owl.js chat widget component
    """,
    'author': 'I Am Dream Catcher Ltd',
    'website': 'https://www.iamdreamcatcher.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'web',
        'mail',
        'contacts',
        'health_base',
        'health_crm',
        'bus',
    ],
    'data': [
        # Security
        'security/zalo_security.xml',
        'security/ir.model.access.csv',

        # Data
        'data/zalo_data.xml',

        # Views
        'views/zalo_config_views.xml',
        'views/zalo_conversation_views.xml',
        'views/zalo_message_views.xml',
        'views/res_partner_views.xml',
        'views/health_patient_views.xml',
        'views/crm_lead_views.xml',
        'views/zalo_menus.xml',
        'views/zalo_templates.xml',

        # Wizards
        'wizard/zalo_wizard_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'health_zalo/static/src/js/zalo_chat_widget.js',
            'health_zalo/static/src/js/zalo_bus_service.js',
            'health_zalo/static/src/xml/zalo_chat_widget.xml',
            'health_zalo/static/src/scss/zalo_chat.scss',
        ],
    },
    'external_dependencies': {
        'python': ['requests'],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
