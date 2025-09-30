{
    'name': 'Healthcare Theme',
    'summary': 'Professional healthcare color palette for Odoo 18 CE',
    'description': '''
        This module provides a professional, AA-accessible healthcare theme
        with calming teal/blue-teal colors optimized for medical workflows.

        Colors:
        - Primary: #0F6D66 (Teal - calming, medical)
        - Secondary: #2E6F89 (Blue-Teal - trust, professionalism)
        - Success: #176B47 (Medical green)
        - Warning: #946200 (Caution amber)
        - Danger: #C0332A (Alert red)
    ''',
    'version': '18.0.1.0.0',
    'category': 'Themes/Backend',
    'license': 'LGPL-3',
    'author': 'VAFHS Healthcare System',
    'website': 'https://vafhs.com',
    'depends': [
        'web',
    ],
    'data': [
        'views/webclient_templates.xml',
    ],
    'assets': {
        'web._assets_primary_variables': [
            ('prepend', 'health_theme/static/src/scss/primary_variables.scss'),
        ],
        'web.assets_backend': [
            'health_theme/static/src/scss/backend.scss',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
