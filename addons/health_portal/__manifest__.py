# -*- coding: utf-8 -*-
{
    'name': 'Health Patient Portal — My Care',
    'summary': 'Tokenized per-patient My Care portal (visits; records/consents '
               'follow) at /my/care/<token>',
    'version': '19.0.1.2.0',
    'category': 'Healthcare',
    'author': 'health19',
    'depends': ['health_fieldservice', 'health_api_gateway', 'health_emr',
                'health_consent', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/portal_templates.xml',
        'views/health_portal_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
