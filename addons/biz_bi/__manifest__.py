# -*- coding: utf-8 -*-
{
    'name': 'BIZ BI Platform',
    'version': '19.0.1.3.0',
    'category': 'Analytics',
    'summary': 'Self-service BI: semantic datasets, drag-and-drop charts, dashboards',
    'description': """
BIZ BI Platform
===============
Power-BI-class analytics inside Odoo Community:

* Semantic layer: business-friendly datasets with parent-child relationships,
  bilingual (EN/VI) field names, measures, dimensions, calculated fields
* Medallion data architecture: live Silver views + materialized Gold views
  with a serial refresh queue and per-dataset freshness tracking
* Drag-and-drop Explore chart builder powered by Apache ECharts
* Flexible dashboard canvas (GridStack) with global filters and TV mode
* Row-level and column-level security on top of Odoo groups
* Pluggable AI providers (Claude / OpenAI / Ollama) for natural-language
  chart and report creation (LLM outputs validated chart configs, never SQL)
""",
    'author': 'VAFHS Development Team',
    'website': 'https://vafhs.com',
    'license': 'LGPL-3',
    'depends': ['web', 'base', 'mail', 'base_setup'],
    'data': [
        'security/biz_bi_security.xml',
        'security/ir.model.access.csv',
        'data/bi_cron.xml',
        'data/bi_ai_provider_data.xml',
        'views/bi_backend_views.xml',
        'views/bi_actions.xml',
        'views/bi_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'biz_bi/static/src/lib/echarts.min.js',
            'biz_bi/static/src/lib/gridstack/gridstack-all.js',
            'biz_bi/static/src/lib/gridstack/gridstack.min.css',
            'biz_bi/static/src/scss/biz_bi.scss',
            'biz_bi/static/src/core/**/*.js',
            'biz_bi/static/src/services/**/*.js',
            'biz_bi/static/src/components/**/*.js',
            'biz_bi/static/src/components/**/*.xml',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'auto_install': False,
    'application': True,
    'sequence': 145,
}
