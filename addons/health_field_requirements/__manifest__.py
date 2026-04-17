{
    'name': 'Health Field Requirements',
    'version': '19.0.1.1.0',
    'category': 'Healthcare',
    'summary': 'Configure mandatory fields per model, role, and state',
    'description': """
        Configurable Mandatory Fields for Healthcare Models
        ===================================================
        Allows administrators to configure which form fields are mandatory:
        - Globally (all roles) or per-role
        - Always required or per-state (e.g., only when booking is Confirmed)
        - Dual enforcement: server-side (UserError popup) + client-side (red asterisks + inline errors)
        - Visual card-based dashboard for easy configuration
    """,
    'author': 'Biztinct',
    'depends': ['base', 'access_roles'],
    'data': [
        'security/ir.model.access.csv',
        'views/field_requirement_views.xml',
        'views/menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'health_field_requirements/static/src/css/field_requirements_dashboard.css',
            'health_field_requirements/static/src/css/form_required_popup.css',
            'health_field_requirements/static/src/js/field_requirements_dashboard.js',
            'health_field_requirements/static/src/js/form_required_popup.js',
            'health_field_requirements/static/src/xml/field_requirements_dashboard.xml',
            'health_field_requirements/static/src/xml/form_required_popup.xml',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'LGPL-3',
}
