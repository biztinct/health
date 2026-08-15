# -*- coding: utf-8 -*-
{
    'name': 'Healthcare Care Plans',
    'version': '19.0.1.1.0',
    'category': 'Healthcare/Clinical',
    'summary': 'Care plans with goals, interventions and per-visit task '
               'checklists (FHIR CarePlan/Goal/Task)',
    'author': 'VAFHS Development Team',
    'website': 'https://www.vafhs.com',
    'license': 'LGPL-3',
    # Depends on health_vitals because goals target observation types
    # (clinical spec §1.2.2). health_pwa added on top of the spec list:
    # the PWA checklist scripts are injected by inheriting the
    # health_pwa.app_shell QWeb template (health_evv / health_vitals
    # pattern) — no health_pwa file is modified.
    'depends': ['health_base', 'health_fieldservice', 'health_vitals',
                'health_pwa'],
    'data': [
        'security/health_careplan_security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence.xml',
        'data/ir_cron.xml',
        'views/health_careplan_views.xml',
        'views/health_careplan_task_views.xml',
        'views/health_fieldservice_order_views.xml',
        'views/health_careplan_menus.xml',
        'views/ops_careplan_tabs.xml',
        'views/pwa_shell_inherit.xml',
    ],
    # NB: careplan-service.js / careplan-components.js are PWA scripts loaded
    # by plain <script> tags in pwa_shell_inherit.xml, NOT by a bundle. These
    # two are backend-only and belong in web.assets_backend.
    'assets': {
        'web.assets_backend': [
            'health_careplan/static/src/js/client_careplans_widget.js',
            'health_careplan/static/src/xml/client_careplans_widget.xml',
            'health_careplan/static/src/js/booking_visit_tasks_widget.js',
            'health_careplan/static/src/xml/booking_visit_tasks_widget.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
