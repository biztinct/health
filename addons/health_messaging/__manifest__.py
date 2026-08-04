# -*- coding: utf-8 -*-
{
    'name': 'Health Visit Messaging',
    'summary': 'Booking confirmations + visit reminders over Zalo ZNS with '
               'email and staff-call-activity fallback (dry-run by default)',
    'description': """
Visit messaging cascade: ZNS → email → staff call-activity for booking
confirmations, 24h/2h reminders and cancellation notices.

SAFETY: the master switch (health_messaging.enabled) is OFF and simulation
mode (health_messaging.dry_run) is ON by default — installing this module
changes nothing and sends nothing until an operator switches it on.
""",
    'version': '19.0.1.0.1',
    'category': 'Healthcare',
    'author': 'health19',
    'depends': ['health_fieldservice', 'health_base', 'health_zalo', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'security/health_messaging_security.xml',
        'security/catchment_global_rules.xml',
        'data/ir_sequence.xml',
        'data/mail_templates.xml',
        'data/ir_cron.xml',
        'views/health_outbound_message_views.xml',
        'views/health_fieldservice_order_views.xml',
        'views/res_config_settings_views.xml',
        'views/health_messaging_menus.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
