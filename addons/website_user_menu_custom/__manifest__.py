# -*- coding: utf-8 -*-
{
    'name': 'Website User Menu Customization',
    'version': '18.0.1.0.0',
    'category': 'Website',
    'summary': 'Customize website user menu to show only Profile and Logout',
    'description': """
Website User Menu Customization
================================
Hides unwanted menu items from the website user dropdown menu:
- Documentation
- Support
- Shortcuts
- Onboarding
- My Odoo.com account

Keeps only:
- My Profile
- Log out
    """,
    'author': 'VAFHS',
    'website': 'https://vafhs.com',
    'license': 'LGPL-3',
    'depends': ['website', 'portal'],
    'data': [
        'views/portal_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'website_user_menu_custom/static/src/css/user_menu.css',
            'website_user_menu_custom/static/src/js/user_menu_filter.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
