{
    'name': 'VAFHS Staff Assignment System',
    'version': '18.0.2.1.0',
    'category': 'Healthcare/Staff Management',
    'summary': 'State-of-the-art staff assignment system with intelligent routing and mobile-first UI',
    'description': """
        VAFHS Healthcare Staff Assignment System
        =====================================
        
        Advanced staff assignment system inspired by Uber Driver, DoorDash, and ServiceTitan:
        
        Core Features:
        - Intelligent staff assignment with AI-powered suggestions
        - Multi-role approval workflow (Sales → Ops Manager → Head Nurse → Staff)
        - Real-time availability matrix and conflict detection
        - Geographic optimization for home visits
        - Mobile-first assignment dashboard (Kanban board style)
        - Real-time status tracking with GPS integration
        - Performance analytics and workload balancing
        
        UI/UX Inspiration:
        - Uber Driver app for real-time tracking
        - Monday.com/Asana for drag-and-drop assignment
        - Slack workflow builder for approval processes
        - ServiceTitan for field service management
        
        Vietnamese Healthcare Compliance:
        - MOH staff assignment requirements
        - Healthcare professional licensing validation
        - Audit trail for regulatory compliance
    """,
    'author': 'I Am Dream Catcher Ltd',
    'website': 'https://vafhs.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'calendar',
        'hr',
        'contacts',
        'web',
        'web_timeline',  # Professional timeline/Gantt functionality
        'health_calendar',  # Inherit from our appointment system
    ],
    'data': [
        # Security
        'security/health_staff_assignment_security.xml',
        'security/ir.model.access.csv',
        
        # Data  
        # 'data/health_staff_assignment_data.xml',  # Temporarily commented out for basic installation
        
        # Views - Load order matters
        'views/assignment_dashboard_views.xml',  # Load dashboard views first (contains kanban view referenced by actions)
        'views/assignment_scheduler_grid.xml',   # Visual date/time grid scheduler
        'views/assignment_web_timeline_views.xml',  # Professional web_timeline views (forms, lists)
        'views/assignment_timeline_views.xml',   # Timeline action and menu
        'views/healthcare_skill_views.xml',      # Healthcare skills and service areas
        'views/health_staff_availability_views.xml',  # Staff availability views
        'views/health_staff_assignment_views.xml',
        'views/staff_workload_dashboard_views.xml',  # Visual workload management dashboard
        
        # Extended appointment views (inherit from health_calendar)
        'views/health_appointment_minimal.xml',  # Minimal extension first
        
        # Menus - Load after views
        'views/health_staff_assignment_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'health_staff_assignment/static/src/css/assignment_dashboard.css',
            'health_staff_assignment/static/src/css/scheduler_grid.css',
            'health_staff_assignment/static/src/css/staff_workload_dashboard.css',
            'health_staff_assignment/static/src/css/web_timeline_custom.css',
            'health_staff_assignment/static/src/js/staff_workload_dashboard.js',
            # 'health_staff_assignment/static/src/js/timeline_card_enhancer.js',  # Removed - using model-based HTML content instead
            'health_staff_assignment/static/src/xml/staff_workload_dashboard.xml',
            # Timeline functionality now provided by web_timeline module
            # 'health_staff_assignment/static/src/js/assignment_timeline_view.js',
            # 'health_staff_assignment/static/src/xml/assignment_timeline_view.xml',
            # Other JavaScript temporarily disabled to ensure basic view loads
            # 'health_staff_assignment/static/src/js/assignment_dashboard.js',
            # 'health_staff_assignment/static/src/js/assignment_kanban.js',
            # 'health_staff_assignment/static/src/js/scheduler_grid.js',
            # 'health_staff_assignment/static/src/xml/assignment_dashboard.xml',
        ],
        # 'web.assets_frontend': [
        #     'health_staff_assignment/static/src/css/mobile_assignment.css',
        #     'health_staff_assignment/static/src/js/mobile_assignment.js',
        # ],
    },
    # 'demo': [
    #     'demo/health_staff_assignment_demo.xml',
    # ],
    'installable': True,
    'auto_install': False,
    'application': False,  # This extends health_calendar
    'sequence': 105,
}