# -*- coding: utf-8 -*-
{
    'name': 'Healthcare Landing Dashboard',
    'version': '18.0.1.0.0',
    'category': 'Healthcare',
    'summary': 'Modern landing dashboard with icon-driven navigation for VAFHS Healthcare System',
    'description': """
Healthcare Landing Dashboard
=============================

Professional, visually stunning landing dashboard for the Vietnam-Australia Family Health Service
healthcare management system.

Features:
---------
* Modern card-based layout with Font Awesome icons
* Two-level navigation: Main dashboard → Submenu dashboard → Action windows
* Responsive design (desktop, tablet, mobile)
* Color-coded modules matching hierarchy widget theme
* Smooth hover animations and transitions
* Breadcrumb navigation
* Professional typography and spacing

Modules:
--------
* Patient Management
* CRM (Customer Relationship Management)
* Field Service
* Service Packages
* Billing & Invoicing
* Facilities
* Configuration

Design inspired by modern SaaS applications with emphasis on usability and visual appeal.
    """,
    'author': 'I Am Dream Catcher Ltd',
    'website': 'https://vafhs.com',
    'license': 'LGPL-3',
    'depends': [
        'web',
        'health_base',
        'health_crm',
        'health_fieldservice',
        'health_invoicing',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/landing_dashboard_views.xml',
        'views/landing_menus.xml',
        'views/patient_list_extension.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'health_landing/static/src/css/landing_dashboard.css',
            'health_landing/static/src/css/hub_spoke_widget.css',
            'health_landing/static/src/js/hub_spoke_widget.js',
            'health_landing/static/src/js/patient_spoke_modal.js',
            'health_landing/static/src/js/patient_hub_action.js',
            'health_landing/static/src/js/landing_dashboard.js',
            'health_landing/static/src/xml/hub_spoke_widget.xml',
            'health_landing/static/src/xml/patient_spoke_modal.xml',
            'health_landing/static/src/xml/patient_hub_action.xml',
            'health_landing/static/src/xml/landing_templates.xml',
        ],
    },
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': True,
    'auto_install': False,
}
