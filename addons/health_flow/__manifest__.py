# -*- coding: utf-8 -*-
{
    'name': 'Health Flow Dashboard',
    'version': '19.0.1.0.0',
    'category': 'Healthcare',
    'summary': 'Interactive circular workflow dashboard for healthcare operations',
    'description': """
Health Flow Dashboard - Interactive Circular Interface
=======================================================

State-of-the-art interactive circular workflow interface for healthcare operations.

Key Features:
* CRM workflows (Search, Initial Contact, Planned Activities, Calendar)
* Booking management (Calendar, Staff Assignment, Draft, Assigned, Scheduled)
* Invoicing (AR Dashboard, Payment Transactions, Invoices)
* Analytics Dashboard (BI Dashboard direct access)
* Audit Log (System audit direct access)
* Admin Configuration (All system configuration items)

Technical Features:
* Modern circular/radial menu interface
* Smooth animations and transitions
* Click interactions with slide-in panel
* Mobile responsive design
* Built with Odoo 19 OWL framework
    """,
    'author': 'Vietnam-Australia Family Health Service',
    'website': 'https://www.vafhs.com',
    'depends': [
        'health_base',
        'health_crm',
        'health_fieldservice',
        'health_invoicing',
        'advanced_pricing',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/health_flow_menus.xml',
        'views/health_flow_crm_calendar_views.xml',
        'views/health_flow_crm_merge_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'health_flow/static/src/css/health_flow.css',
            'health_flow/static/src/js/health_flow_action.js',
            'health_flow/static/src/xml/health_flow_templates.xml',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
