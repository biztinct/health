# -*- coding: utf-8 -*-
{
    'name': 'Health FHIR Adapter — Vietnam',
    'summary': 'Vietnam EMR export (Circular 13/2025): patient FHIR bundle, '
               'ICD-10 Conditions, VN profile validation, readiness report',
    'version': '19.0.1.0.0',
    'category': 'Healthcare',
    'author': 'health19',
    'depends': [
        'health_fhir_adapter_base', 'health_fhir_terminology',
        'health_consent', 'health_fieldservice',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/health_facility_views.xml',
        'views/res_partner_views.xml',
        'views/vn_emr_readiness_views.xml',
        'views/fhir_adapter_vn_menus.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
