# -*- coding: utf-8 -*-
{
    'name': 'Healthcare Clinical Forms',
    'version': '19.0.1.0.0',
    'category': 'Healthcare/Clinical',
    'summary': 'Configurable clinical forms & scored assessments rendered in '
               'backend (OWL) and PWA from one JSON schema '
               '(FHIR Questionnaire/QuestionnaireResponse)',
    'author': 'VAFHS Development Team',
    'website': 'https://www.vafhs.com',
    'license': 'LGPL-3',
    'depends': ['health_base', 'health_fieldservice', 'health_vitals'],
    'data': [
        'security/health_forms_security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence.xml',
        'data/health_vitals_type_assessment_data.xml',
        'data/health_form_template_pain.xml',
        'data/health_form_template_barthel.xml',
        'data/health_form_template_mna.xml',
        'data/health_form_template_braden.xml',
        'data/health_form_template_amts.xml',
        'views/health_form_template_views.xml',
        'views/health_form_instance_views.xml',
        'views/health_fieldservice_order_views.xml',
        'views/health_forms_menus.xml',
        'views/pwa_shell_inherit.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'health_forms/static/src/components/form_renderer/form_renderer.js',
            'health_forms/static/src/components/form_renderer/form_renderer.xml',
            'health_forms/static/src/components/form_renderer/form_renderer.scss',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
