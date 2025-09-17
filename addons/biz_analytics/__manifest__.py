# -*- coding: utf-8 -*-
{
    'name': 'Business Analytics Dashboard',
    'version': '18.0.1.0.0',
    'category': 'Analytics',
    'summary': 'State-of-the-art analytics dashboard with drag-and-drop chart builder',
    'description': """
Business Analytics Dashboard
============================

A comprehensive analytics module featuring:
- Drag & drop field selector for creating charts
- Advanced filtering system
- Professional dashboard builder
- Multiple chart types with Chart.js integration
- Real-time data visualization
- Responsive design optimized for all devices

Key Features:
- Interactive chart creation with drag & drop
- Advanced multi-criteria filtering
- Dashboard builder with grid layout
- Export capabilities (PDF, Excel, PNG)
- Theme support (light/dark mode)
- Real-time data refresh
    """,
    'author': 'VAFHS Development Team',
    'website': 'https://vafhs.com',
    'depends': [
        'web',
        'base',
        'mail',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/analytics_data.xml',
        'views/analytics_dashboard_views.xml',
        'views/analytics_dashboard_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'biz_analytics/static/src/components/**/*.js',
            'biz_analytics/static/src/components/**/*.xml',
            'biz_analytics/static/src/js/*.js',
            'biz_analytics/static/src/scss/*.scss',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': True,
    'license': 'LGPL-3',
}