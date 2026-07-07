{
    'name': 'Health H0 Workflow Automations',
    'version': '19.0.1.0.0',
    'category': 'Healthcare',
    'summary': 'H0 ops quick-wins: one-tap completion, Red Invoice batch, '
               'timecard auto-fill, first-visit offer',
    'author': 'Biztinct',
    # A1 (handover): shipped module is health_messaging (not health_messaging_auto);
    # health_api_gateway added for A5 rate limiting. All verified installed on vietuat.
    'depends': [
        'health_fieldservice',
        'health_pwa',
        'health_redinvoice',
        # NB: pb_hr_workforce (the spec's timecard/OT reader) is NOT installed on
        # vietuat and this module never calls it — it only WRITES standard
        # hr.attendance, which pb_hr_workforce reads back when present. Depending
        # on it would force a payroll-module install on UAT, so it is left as a
        # soft (runtime-optional) dependency. hr_attendance is the real target.
        'health_messaging',
        'health_api_gateway',
        'crm',
        'hr_attendance',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/health_workflow_auto_security.xml',
        'data/workflow_config_params.xml',
        'data/workflow_cron.xml',
        'views/visit_offer_views.xml',
        'views/timecard_mismatch_views.xml',
        'views/attendance_views.xml',
        'views/res_config_settings_views.xml',
        'views/offer_templates.xml',
        'views/workflow_menus.xml',
        'views/pwa_shell_inherit.xml',
    ],
    'assets': {
        'web.assets_backend': [],
    },
    'installable': True,
    'application': False,
    'sequence': 145,
    'license': 'LGPL-3',
}
