# -*- coding: utf-8 -*-
{
    'name': 'Healthcare eMAR',
    'version': '19.0.1.3.0',
    'category': 'Healthcare/Clinical',
    'summary': 'Medication orders, administration records, schedules and PWA '
               'med checklist (FHIR MedicationRequest/MedicationAdministration)',
    'author': 'VAFHS Development Team',
    'website': 'https://www.vafhs.com',
    'license': 'LGPL-3',
    'depends': ['health_base', 'health_fieldservice'],
    'data': [
        'security/health_emar_security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence.xml',
        'data/ir_cron.xml',
        'data/health_medication_notgiven_reason_data.xml',
        'views/health_medication_views.xml',
        'views/health_medication_order_views.xml',
        'views/health_medication_administration_views.xml',
        'views/health_fieldservice_order_views.xml',
        'views/res_partner_views.xml',
        'views/health_emar_menus.xml',
        'views/pwa_shell_inherit.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
