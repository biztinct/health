# -*- coding: utf-8 -*-
{
    'name': 'Health Patient Portal — My Care',
    'summary': 'Tokenized per-patient My Care portal (visits; records/consents '
               'follow) at /my/care/<token>',
    'version': '19.0.1.4.1',
    'category': 'Healthcare',
    'author': 'health19',
    'depends': ['health_fieldservice', 'health_api_gateway', 'health_emr',
                'health_consent', 'health_invoicing', 'health_self_booking',
                'health_condition', 'health_vitals',
                'mail'],
    'data': [
        'security/ir.model.access.csv',
        'security/catchment_rules.xml',
        'views/portal_templates.xml',
        'views/health_portal_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
