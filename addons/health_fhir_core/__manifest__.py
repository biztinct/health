# -*- coding: utf-8 -*-
{
    'name': 'Health FHIR R4 Facade (read-only)',
    'summary': 'Read-only FHIR R4 facade over health19 clinical/operational models',
    'version': '19.0.1.2.0',
    'category': 'Healthcare',
    'author': 'health19',
    'depends': [
        'health_api_gateway', 'health_base', 'health_crm', 'health_fieldservice',
        # Phase 2 — clinical-spine source modules (now the mandatory core).
        'health_vitals', 'health_careplan', 'health_emar', 'health_forms',
        'health_incident', 'health_consent',
    ],
    'external_dependencies': {'python': ['fhir.resources']},  # pip: fhir.resources (R4B, pydantic v2)
    'data': ['security/ir.model.access.csv', 'data/fhir_data.xml'],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
