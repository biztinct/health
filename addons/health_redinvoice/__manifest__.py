{
    'name': 'Healthcare Red Invoice Integration',
    'version': '19.0.1.0.3',
    'summary': 'Vietnam Viettel SInvoice (Red Invoice) integration for healthcare invoicing',
    'category': 'Accounting',
    'author': 'I Am Dream Catcher Ltd',
    'license': 'LGPL-3',
    'depends': [
        'account',
        'health_invoicing',
        'health_fieldservice',  # booking (field service order) red-invoice button
        'base_setup',  # for res.config.settings base view in CE
    ],
    'data': [
        'security/redinvoice_security.xml',
        'security/ir.model.access.csv',
        'views/redinvoice_request_views.xml',
        'views/account_move_views.xml',
        'views/fieldservice_order_views.xml',
        'views/redinvoice_pdf_preview_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'health_redinvoice/static/src/css/redinvoice_icons.css',
            'health_redinvoice/static/src/js/pdf_frame_field.js',
            'health_redinvoice/static/src/xml/pdf_frame_field.xml',
        ],
    },
    'installable': True,
    'application': False,
}
