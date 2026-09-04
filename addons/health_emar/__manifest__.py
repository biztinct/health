# -*- coding: utf-8 -*-
{
    'name': 'Healthcare eMAR',
    'version': '19.0.1.3.2',
    'category': 'Healthcare/Clinical',
    'summary': 'Medication orders, administration records, schedules and PWA '
               'med checklist (FHIR MedicationRequest/MedicationAdministration)',
    'author': 'VAFHS Development Team',
    'website': 'https://www.vafhs.com',
    'license': 'LGPL-3',
    'depends': [
        'health_base',
        'health_fieldservice',
        # views/pwa_shell_inherit.xml inherits `health_pwa.app_shell` to put the
        # medication round on the field app. Reaching another module's view
        # without depending on it works only while the load order happens to
        # be kind; on a fresh install the graph decides, and this one dies with
        # "External ID not found in the system: health_pwa.app_shell".
        # health_forms and health_telehealth inherit the same view and are fine
        # because they reach health_pwa transitively — this was the only module
        # of the thirteen that did not.
        'health_pwa',
    ],
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
