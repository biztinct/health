{
    'name': 'Healthcare Base',
    'version': '18.0.1.1.0',
    'category': 'Healthcare',
    'summary': 'Foundation module for VAFHS Healthcare Management System with Clinical Intelligence',
    'description': """
Healthcare Base Module v4.0
===========================

Enhanced foundation module for Vietnam-Australia Family Health Service (VAFHS) healthcare management system.

Key Features:
* Healthcare-specific data models and lookup codes
* Vietnamese localization support
* Professional mobile-responsive design
* Multi-language support (Vietnamese & English)
* Security and access controls
* Clinical intelligence foundation
""",
    'author': 'VAFHS Development Team',
    'website': 'https://www.vafhs.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'portal',
    ],
    'external_dependencies': {
        'python': ['requests'],
    },
    'data': [
        'security/health_security.xml',
        'security/ir.model.access.csv',
        'data/health_data.xml',
        'data/res_country_state_data.xml',
        'data/menu_access.xml',
        'views/health_lookup_views.xml',
        'views/health_facility_views.xml',
        'views/health_patient_views.xml',
        'views/health_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'health_base/static/src/css/health_base.css',
            'health_base/static/src/js/health_base.js',
            'health_base/static/src/js/address_autocomplete_widget.js',
            'health_base/static/src/xml/address_autocomplete_widget.xml',
            'health_base/static/src/scss/address_autocomplete_widget.scss',
            'health_base/static/src/js/address_map_widget.js',
            'health_base/static/src/xml/address_map_widget.xml',
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
    # 'post_init_hook': 'hooks.post_init_hook',  # Disabled for development
}
