# -*- coding: utf-8 -*-
{
    'name': 'Healthcare CMS — Clinical Intelligence Surfacing',
    'version': '19.0.1.0.0',
    'category': 'Healthcare/Clinical',
    'summary': 'Surfaces the shipped clinical-intelligence layer on the /bizapp '
               'CMS: a "Care Intelligence" sidebar group (Deterioration '
               'Worklist, Deterioration Alerts, Monitoring Devices, NEWS2 '
               'Scores) plus Alert Thresholds + Consents tabs on the ops '
               'client profile. Pure data + view glue — no python, no models.',
    'author': 'VAFHS Development Team',
    'website': 'https://www.vafhs.com',
    'license': 'LGPL-3',
    'depends': [
        'health_cms_sidebar',
        'health_telemonitoring',
        'health_twin',
        'health_vitals',
        'health_consent',
        'health_fieldservice',
    ],
    'data': [
        'data/cms_sidebar_items.xml',
        'views/ops_profile_tabs.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
