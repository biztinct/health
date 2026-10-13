{
    'name': 'Healthcare Compliance Assurance',
    'version': '19.0.1.0.1',
    'category': 'Healthcare',
    'author': 'Biztinct',
    'summary': 'Scoped evidence register, rights requests, retention holds and integration readiness',
    'depends': ['health_emr', 'health_consent', 'health_phi_encryption',
                'health_cms_sidebar', 'health_access', 'health_bhyt', 'health_scribe', 'health_ai_coding', 'biz_bi'],
    'data': ['security/ir.model.access.csv', 'views/compliance_views.xml',
             'data/compliance_register.xml', 'data/sidebar.xml'],
    'installable': True,
    'license': 'LGPL-3',
}
