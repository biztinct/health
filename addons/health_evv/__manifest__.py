# -*- coding: utf-8 -*-
{
    'name': 'Health EVV — Electronic Visit Verification',
    'version': '19.0.1.0.0',
    'category': 'Healthcare',
    'summary': 'EVV-grade visit verification: geofenced check-in/out, '
               'hash-chained tamper-evident event log, signature capture, '
               'verified units.',
    'depends': ['health_base', 'health_fieldservice', 'health_pwa'],
    'data': [
        'security/evv_security.xml',
        'security/ir.model.access.csv',
        'data/evv_cron.xml',
        'views/evv_event_views.xml',
        'views/fso_evv_views.xml',
        'views/res_partner_views.xml',
        'views/pwa_shell_inherit.xml',
        'report/evv_verification_report.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
