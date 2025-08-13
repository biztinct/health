{
    'name': 'Healthcare Base',
    'version': '18.0.3.0.0',
    'category': 'Healthcare',
    'summary': 'Foundation module for VAFHS Healthcare Management System',
    'description': """
Healthcare Base Module
======================

Foundation module for Vietnam-Australia Family Health Service (VAFHS) healthcare management system.

Key Features:
* Healthcare-specific data models and lookup codes
* Vietnamese localization support
* Professional mobile-first responsive design system
* Security roles and permissions for healthcare staff
* PWA-optimized interface components
* Unified desktop/mobile layouts (no duplication)

This module serves as the foundation for all other health_* modules and must be installed first.
    """,
    'author': 'I Am Dream Catcher Ltd',
    'website': 'https://vafhs.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'contacts',
        'web',
        'mail',
        'calendar',
        'portal',
        'hr',
    ],
    'data': [
        # Security
        'security/health_security.xml',
        'security/ir.model.access.csv',
        
        # Data
        'data/health_data.xml',
        'data/res_country_state_data.xml',
        'data/menu_access.xml',
        
        # Views
        'views/health_patient_views.xml',
        'views/health_lookup_views.xml',
        'views/health_facility_views.xml',
        'views/health_menus.xml',
        
        # Assets (templates only, not asset includes)
        'views/templates.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'health_base/static/src/css/health_base.css',
            'health_base/static/src/js/health_base.js',
        ],
        'web.assets_frontend': [
            'health_base/static/src/css/health_frontend.css',
        ],
    },
    'demo': [
        'demo/health_demo_data.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'sequence': 10,
}