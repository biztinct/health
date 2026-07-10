# -*- coding: utf-8 -*-
{
    'name': 'Health PWA - Mobile Progressive Web Application',
    'version': '19.0.1.0.24',
    'category': 'Healthcare/Mobile',
    'summary': 'Progressive Web Application for Healthcare Field Workers with Offline Capabilities',
    'description': """
        Health PWA - Mobile Progressive Web Application
        ==============================================
        
        World-class Progressive Web Application for healthcare field workers with:
        
        Core Features:
        - Full offline functionality with PouchDB synchronization
        - Native device features (camera, GPS, push notifications)
        - Mobile-first responsive design optimized for healthcare workflows
        - Real-time data synchronization when online
        - Cross-platform compatibility (Android/iOS)
        
        Healthcare Integration:
        - Seamless integration with health_base, health_crm, health_fieldservice
        - Patient management and FSO handling on mobile devices
        - Clinical photo capture and GPS tracking for field visits
        - Offline patient data access for field healthcare workers
        
        Technical Architecture:
        - Vue.js 3 with Composition API for modern frontend
        - Quasar Framework for mobile-optimized UI components
        - PouchDB + IndexedDB for robust offline data storage
        - Service Workers for background sync and caching
        - RESTful API integration with Odoo backend
        
        Target Users:
        - Field healthcare workers and nurses
        - Home visit medical staff
        - Mobile clinic operators
        - Healthcare facility staff requiring mobile access
        
        Browser Support:
        - Android Chrome (full features)
        - iOS Safari (with camera workarounds)
        - Firefox Mobile, Edge Mobile
        
        Installation:
        - No app store required - installs directly from browser
        - Works offline immediately after installation
        - Automatic updates via service worker
    """,
    'author': 'I Am Dream Catcher Ltd',
    'website': 'https://vafhs.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'web',
        'mail',
        'health_base',        # Core healthcare models and functionality
        'health_crm',         # CRM contacts and lead management
        'health_fieldservice', # Field service orders and assignments
        'health_invoicing',   # Healthcare billing integration
    ],
    'data': [
        # Security
        'security/ir.model.access.csv',

        # PWA Configuration Data
        'data/pwa_config.xml',
        
        # Views and Templates
        'views/pwa_templates.xml',
        'views/debug_template.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            # PWA Core Files - only include files that exist
            'health_pwa/static/src/css/app.css',
            'health_pwa/static/src/css/mobile.css', 
            'health_pwa/static/src/css/health.css',
            'health_pwa/static/src/js/utils/pwa-utils.js',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': True,  # This is a standalone application
    'sequence': 100,
    'external_dependencies': {
        'python': ['pywebpush'],
    },
}
