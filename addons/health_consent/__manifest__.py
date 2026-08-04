# -*- coding: utf-8 -*-
{
    'name': 'Healthcare Consent Management',
    'version': '19.0.1.1.1',
    'category': 'Healthcare/Clinical',
    'summary': 'Consent capture (verbal/written/digital signature), expiry '
               'lifecycle and check_consent() service API (FHIR Consent)',
    'author': 'VAFHS Development Team',
    'website': 'https://www.vafhs.com',
    'license': 'LGPL-3',
    # health_pwa: views/pwa_shell_inherit.xml extends health_pwa.app_shell
    # to inject the consent PWA assets (careplan/vitals precedent).
    'depends': ['health_base', 'health_crm', 'health_pwa'],
    'data': [
        'security/health_consent_security.xml',
        'security/catchment_check_log_rules.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence.xml',
        'data/ir_cron.xml',
        'views/health_consent_views.xml',
        'views/res_partner_views.xml',
        'views/health_consent_menus.xml',
        'views/pwa_shell_inherit.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
