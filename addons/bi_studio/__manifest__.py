# -*- coding: utf-8 -*-
{
    'name': 'BI Studio',
    'version': '19.0.1.0.0',
    'category': 'Analytics',
    'summary': 'Power BI-class analytics platform with semantic datasets and visual report designer',
    'description': """
BI Studio — Business Intelligence for Odoo
=============================================

A comprehensive analytics platform inspired by Power BI and Tableau:

**Layer 1 — Data Source Explorer**
- Browse Odoo models with business-friendly names
- Curated Business Domains (Finance, Healthcare, HR, Sales, BFSI)
- Automatic field scanning with relational traversal
- Advanced mode for power users

**Layer 2 — Semantic Dataset Builder**
- Select fields across related models
- Define report grain (one row per Invoice, per Line, per Customer)
- Save reusable datasets with filters and aggregations
- Live data preview

**Layer 3 — Visual Report Designer**
- Drag-and-drop chart builder
- Apache ECharts rendering (15+ chart types)
- Auto chart type suggestions
- Field slots: X-Axis, Y-Axis, Color, Size, Tooltip, Filter

**Layer 4 — Output & Delivery**
- Interactive dashboards with GridStack layout
- Excel export (table, grouped, pivot, multi-sheet)
- PDF export
- Scheduled email reports
    """,
    'author': 'VAFHS Development Team',
    'website': 'https://vafhs.com',
    'depends': [
        'web',
        'base',
        'mail',
    ],
    'data': [
        'security/bi_studio_security.xml',
        'security/ir.model.access.csv',
        'data/bi_business_domain_data.xml',
        'views/bi_dataset_views.xml',
        'views/bi_visual_views.xml',
        'views/bi_report_page_views.xml',
        'views/bi_studio_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            # Apache ECharts
            'bi_studio/static/src/lib/echarts.min.js',
            # GridStack
            'bi_studio/static/src/lib/gridstack/gridstack-all.js',
            'bi_studio/static/src/lib/gridstack/gridstack.min.css',
            # Components
            'bi_studio/static/src/components/**/*.js',
            'bi_studio/static/src/components/**/*.xml',
            'bi_studio/static/src/components/**/*.scss',
            # Styles
            'bi_studio/static/src/scss/*.scss',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': True,
    'license': 'LGPL-3',
}
