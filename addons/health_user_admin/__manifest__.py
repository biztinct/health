{
    'name': 'Healthcare User Administration',
    'version': '19.0.1.11.0',
    'category': 'Healthcare',
    'summary': 'SaaS-safe user and role management for healthcare tenants',
    'description': """
Healthcare User Administration
==============================

Provides a self-contained user management interface for SaaS tenants:
- Create and deactivate users without Settings access
- Assign access roles (from the access_roles module)
- Role management with granular permissions
- Safeguards preventing system-admin group assignment

Tenant admins get full user/role control without the ability to:
- Install or remove modules
- Access database management
- Modify technical settings
- Grant themselves system administrator privileges
    """,
    'author': 'Biztinct',
    'website': 'https://www.biztinct.com',
    'depends': [
        'health_base',
        'health_fieldservice',
        'access_roles',
        'hr',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'security/ir_rules.xml',
        'views/health_create_user_wizard_views.xml',
        'views/health_user_views.xml',
        'views/health_user_actions.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'health_user_admin/static/src/js/user_list_controller.js',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'LGPL-3',
}
