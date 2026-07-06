# -*- coding: utf-8 -*-
{
    'name': 'Health FHIR R4 Facade (read-only)',
    'summary': 'Phase-1 read-only FHIR R4 facade over health19 clinical/operational models',
    'version': '19.0.1.0.0',
    'category': 'Healthcare',
    'author': 'health19',
    'depends': ['health_api_gateway', 'health_base', 'health_crm', 'health_fieldservice'],
    'external_dependencies': {'python': ['fhir.resources']},  # pip: fhir.resources (R4B, pydantic v2)
    'data': ['security/ir.model.access.csv'],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
