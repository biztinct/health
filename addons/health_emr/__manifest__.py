# -*- coding: utf-8 -*-
{
    'name': 'Health EMR — Record Spine',
    'summary': 'Circular 13/2025: clinical-note finalization, clinician '
               'sign-off, immutability and tamper-evident integrity seal',
    'version': '19.0.1.0.0',
    'category': 'Healthcare',
    'author': 'health19',
    'depends': ['health_fieldservice', 'mail'],
    'data': [
        'views/health_clinical_note_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
