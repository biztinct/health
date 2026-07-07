# -*- coding: utf-8 -*-
{
    'name': 'Healthcare Incident Management',
    'version': '19.0.1.0.0',
    'category': 'Healthcare/Clinical',
    'summary': 'Adverse-event capture, investigation workflow, corrective '
               'actions and incident register (FHIR AdverseEvent/Flag)',
    'author': 'VAFHS Development Team',
    'website': 'https://www.vafhs.com',
    'license': 'LGPL-3',
    # Spec §5.1 lists health_base + health_fieldservice. health_pwa is
    # added on top of the spec list (health_careplan / health_vitals /
    # health_evv precedent): the PWA report-incident scripts are
    # injected by inheriting the health_pwa.app_shell QWeb template —
    # no health_pwa file is modified.
    'depends': ['health_base', 'health_fieldservice', 'health_pwa'],
    'data': [
        'security/health_incident_security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence.xml',
        'views/health_incident_views.xml',
        'views/health_incident_action_views.xml',
        'views/health_incident_menus.xml',
        'views/pwa_shell_inherit.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
