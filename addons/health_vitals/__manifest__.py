# -*- coding: utf-8 -*-
{
    'name': 'Healthcare Structured Vitals',
    'version': '19.0.1.0.0',
    'category': 'Healthcare/Clinical',
    'summary': 'LOINC-coded observations, vital-sign catalog, per-client '
               'alert thresholds, trending (FHIR Observation)',
    'author': 'VAFHS Development Team',
    'website': 'https://www.vafhs.com',
    'license': 'LGPL-3',
    # health_pwa added on top of the spec list: the PWA entry sheet /
    # sparkline scripts are injected by inheriting the
    # health_pwa.app_shell QWeb template (health_evv pattern) — no
    # health_pwa file is modified.
    'depends': ['health_base', 'health_fieldservice', 'health_pwa'],
    'data': [
        'security/health_vitals_security.xml',
        'security/ir.model.access.csv',
        'data/health_vitals_type_data.xml',
        'views/health_vitals_type_views.xml',
        'views/health_observation_views.xml',
        'views/health_vitals_threshold_views.xml',
        'views/health_clinical_note_views.xml',
        'views/res_partner_views.xml',
        'views/health_vitals_menus.xml',
        'views/pwa_shell_inherit.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
