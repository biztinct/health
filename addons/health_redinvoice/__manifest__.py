{
    'name': 'Healthcare Red Invoice Integration',
    'version': '18.0.1.0.0',
    'summary': 'Vietnam Viettel SInvoice (Red Invoice) integration for healthcare invoicing',
    'category': 'Accounting',
    'author': 'I Am Dream Catcher Ltd',
    'license': 'LGPL-3',
    'depends': [
        'account',
        'health_invoicing',
        'base_setup',  # for res.config.settings base view in CE
    ],
    'data': [
        'security/redinvoice_security.xml',
        'security/ir.model.access.csv',
        'views/redinvoice_request_views.xml',
        'views/account_move_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'installable': True,
    'application': False,
}
