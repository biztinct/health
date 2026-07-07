# -*- coding: utf-8 -*-
{
    'name': 'Health FHIR Terminology',
    'summary': 'Local-first medical terminology (ICD-10/LOINC/…): code tables, '
               'CSV importer, coding sidecar, FHIR CodeSystem/$lookup/$expand',
    'version': '19.0.1.0.0',
    'category': 'Healthcare',
    'author': 'health19',
    'depends': ['health_base', 'health_fieldservice', 'health_fhir_core'],
    'data': [
        'security/ir.model.access.csv',
        'data/coding_systems.xml',
        'data/codes_loinc_vitals.xml',
        'data/codes_icd10_starter.xml',
        'views/medical_coding_system_views.xml',
        'views/medical_code_views.xml',
        'views/medical_code_import_views.xml',
        'views/health_clinical_note_views.xml',
        'views/terminology_menus.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
