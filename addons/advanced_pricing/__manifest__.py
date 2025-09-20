# -*- coding: utf-8 -*-
{
    'name': 'Advanced Pricing Engine',
    'version': '18.0.1.0.0',
    'category': 'Sales/Sales',
    'summary': 'Enterprise-grade pricing engine with visual rule builder for Odoo 18 CE',
    'description': """
Advanced Pricing Engine for Odoo 18 CE
=======================================

Features:
* Visual rule builder using Google Blockly
* Multi-level cascading pricing rules
* Dynamic field-based calculations
* Integration with custom booking models
* Real-time price calculations
* Performance optimized with caching
* Complete audit trail and versioning
* REST API for external integrations
    """,
    'author': 'Advanced ERP Solutions',
    'website': 'https://www.advanced-erp.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'sale',
        'product',
        'sale_management',
        'website_sale',
        'web',
    ],
    'data': [
        'security/advanced_pricing_security.xml',
        'security/ir.model.access.csv',
        'views/menu_items.xml',
        'views/pricing_engine_views.xml',
        'views/pricing_rule_views.xml',
        'views/pricing_configuration_views.xml',
        'views/product_pricelist_views.xml',
        'views/sale_order_views.xml',
        'views/booking_views.xml',
        'data/pricing_rule_templates.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'advanced_pricing/static/src/scss/pricing_styles.scss',
            'advanced_pricing/static/src/js/pricing_service.js',
            'advanced_pricing/static/src/js/pricing_calculator.js',
            'advanced_pricing/static/src/js/rule_builder.js',
            'advanced_pricing/static/src/js/pricing_widget.js',
            'advanced_pricing/static/src/xml/pricing_templates.xml',
        ],
    },
    'demo': [
        'data/demo_data.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}