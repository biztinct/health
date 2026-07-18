# -*- coding: utf-8 -*-
{
    'name': 'Healthcare Condition / Diagnosis Spine',
    'version': '19.0.1.0.0',
    'category': 'Healthcare/Clinical',
    'summary': 'Per-patient problem list (health.condition) from the ICD-10 '
               'coded-diagnosis sidecar + FHIR Condition resource',
    'author': 'VAFHS Development Team',
    'website': 'https://www.vafhs.com',
    'license': 'LGPL-3',
    # health_fhir_terminology supplies medical.code + the condition_code_ids
    # sidecar (and pulls health_fhir_core's REGISTRY + health_fieldservice's
    # note/FSO). health_ai_coding is the SOLE production writer of the sidecar
    # (action_approve → note.write) — depending on it guarantees load order so
    # the approve path is caught by this module's note-write hook, and makes
    # the AI-approve convergence testable. NO edits to either module (§2.6).
    'depends': [
        'health_fhir_terminology',
        'health_ai_coding',
    ],
    'data': [
        'security/health_condition_security.xml',
        'security/ir.model.access.csv',
        'views/health_condition_views.xml',
        'views/health_condition_menus.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
