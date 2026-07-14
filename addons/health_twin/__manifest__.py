# -*- coding: utf-8 -*-
{
    'name': 'Healthcare Digital Twin (Deterioration Worklist)',
    'version': '19.0.1.0.0',
    'category': 'Healthcare/Clinical',
    'summary': 'One ranked, cross-patient "clients trending down" worklist for '
               'care managers — a transparent, explainable per-client risk '
               'snapshot recomputed from the telemonitoring signals (NEWS2 '
               'scores, deterioration alerts, visit recency). No ML, no LLM.',
    'author': 'VAFHS Development Team',
    'website': 'https://www.vafhs.com',
    'license': 'LGPL-3',
    'depends': [
        'health_telemonitoring',
        'health_vitals',
        'health_fieldservice',
        'health_base',
        'mail',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/twin_security.xml',
        'data/twin_config_params.xml',
        'data/twin_cron.xml',
        'views/health_twin_risk_views.xml',
        'views/res_config_settings_views.xml',
        'views/twin_menus.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
