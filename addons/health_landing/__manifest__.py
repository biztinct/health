# -*- coding: utf-8 -*-
{
    'name': 'Healthcare Landing Dashboard',
    'version': '19.0.1.1.3',
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
        'health_user_admin',
        'advanced_pricing',
        'health_field_requirements',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/landing_dashboard_views.xml',
        'views/landing_menus.xml',
        'views/viet_uc_landing_views.xml',
        'views/viet_uc_menus.xml',
        'views/patient_list_extension.xml',
        'views/hub_spoke_modal_views.xml',
        'views/lead_hub_views.xml',
        'views/fso_dashboard_wizard_views.xml',
        'views/fso_dashboard_button.xml',
        'views/fso_new_wizards_views.xml',

        # Admin Center
        'views/admin_center_views.xml',
        'views/admin_center_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            # Admin Center
            'health_landing/static/src/scss/admin_sidebar.scss',
            'health_landing/static/src/scss/admin_dashboard.scss',
            'health_landing/static/src/scss/admin_navigator.scss',
            'health_landing/static/src/scss/admin_settings.scss',
            'health_landing/static/src/js/admin_sidebar.js',
            'health_landing/static/src/xml/admin_sidebar.xml',
            'health_landing/static/src/js/admin_dashboard.js',
            'health_landing/static/src/xml/admin_dashboard.xml',
            'health_landing/static/src/js/admin_model_navigator.js',
            'health_landing/static/src/xml/admin_model_navigator.xml',
            'health_landing/static/src/js/admin_settings.js',
            'health_landing/static/src/xml/admin_settings.xml',
            # Landing dashboard
            'health_landing/static/src/css/landing_dashboard.css',
            'health_landing/static/src/css/viet_uc_landing.css',
            'health_landing/static/src/css/hub_spoke_widget.css',
            'health_landing/static/src/css/fso_hub_spoke_widget.css',
            'health_landing/static/src/js/landing_dashboard.js',
            'health_landing/static/src/js/viet_uc_landing.js',
            'health_landing/static/src/js/hub_spoke_widget.js',
            'health_landing/static/src/js/lead_hub_spoke_widget.js',
            'health_landing/static/src/js/fso_hub_spoke_widget.js',
            'health_landing/static/src/js/patient_spoke_modal.js',
            'health_landing/static/src/js/patient_hub_action.js',
            'health_landing/static/src/js/lead_hub_action.js',
            'health_landing/static/src/js/fso_hub_action.js',
            'health_landing/static/src/xml/landing_templates.xml',
            'health_landing/static/src/xml/viet_uc_templates.xml',
            'health_landing/static/src/xml/hub_spoke_widget.xml',
            'health_landing/static/src/xml/lead_hub_spoke_widget.xml',
            'health_landing/static/src/xml/fso_hub_spoke_widget.xml',
            'health_landing/static/src/xml/patient_spoke_modal.xml',
            'health_landing/static/src/xml/patient_hub_action.xml',
            'health_landing/static/src/xml/lead_hub_action.xml',
            'health_landing/static/src/xml/fso_hub_action.xml',
        ],
    },
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': True,
    'auto_install': False,
}
