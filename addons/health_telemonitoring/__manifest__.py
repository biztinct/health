# -*- coding: utf-8 -*-
{
    'name': 'Healthcare Telemonitoring (NEWS2 + Deterioration Triage)',
    'version': '19.0.2.2.0',
    'category': 'Healthcare/Clinical',
    'summary': 'NEWS2 early-warning scoring at every vitals capture + a '
               'deterioration triage inbox (NEWS2 bands, threshold mirror, '
               'nightly statistical trend sweep). Every nurse visit becomes '
               'a screening event.',
    'author': 'VAFHS Development Team',
    'website': 'https://www.vafhs.com',
    'license': 'LGPL-3',
    # health_pwa arrives transitively via health_vitals (do NOT list web).
    'depends': [
        'health_vitals',
        'health_fieldservice',
        'health_api_gateway',
        'health_base',
        'mail',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/telemonitoring_security.xml',
        'data/telemonitoring_config_params.xml',
        'data/telemonitoring_scopes.xml',
        'data/telemonitoring_vitals_type_data.xml',
        'data/telemonitoring_cron.xml',
        'views/health_ews_score_views.xml',
        'views/health_monitor_alert_views.xml',
        'views/health_monitor_device_views.xml',
        'views/res_partner_views.xml',
        'views/res_config_settings_views.xml',
        'views/telemonitoring_menus.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
