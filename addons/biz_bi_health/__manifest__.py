# -*- coding: utf-8 -*-
{
    'name': 'BIZ BI — Healthcare Seed Content',
    'version': '19.0.1.0.0',
    'category': 'Analytics',
    'summary': 'Curated VAFHS datasets and dashboards for the BIZ BI platform',
    'description': """
Seed content bridging the generic BIZ BI platform to the VAFHS healthcare
domain: workspaces, curated bilingual datasets (bookings, revenue, CRM,
staff workload), glossary terms and two starter dashboards.
""",
    'author': 'VAFHS Development Team',
    'website': 'https://vafhs.com',
    'license': 'LGPL-3',
    'depends': [
        'biz_bi',
        'health_fieldservice',
        'health_invoicing',
        'health_crm',
        'hr',
        'account',
        'crm',
    ],
    'data': [
        'data/bi_health_workspaces.xml',
        'data/bi_health_glossary.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'sequence': 146,
}
