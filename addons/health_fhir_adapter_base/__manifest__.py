# -*- coding: utf-8 -*-
{
    'name': 'Health FHIR Adapter Base',
    'summary': 'Country-adapter interface + submission audit log for national '
               'EMR export (reusable by VN/SG/ID/AU adapters)',
    'version': '19.0.1.0.0',
    'category': 'Healthcare',
    'author': 'health19',
    'depends': ['health_fhir_core', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'security/fhir_adapter_base_security.xml',
        'data/ir_sequence.xml',
        'views/fhir_submission_log_views.xml',
        'views/fhir_adapter_menus.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
