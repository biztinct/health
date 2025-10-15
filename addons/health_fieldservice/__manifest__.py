{
    'name': 'VAFHS Healthcare Field Service & Staff Assignment',
    'version': '18.0.2.2.3',
    'category': 'Healthcare/Field Service',
    'summary': 'Unified field service management and AI staff assignment for healthcare home visits',
    'description': """
        VAFHS Healthcare Field Service & Staff Assignment
        ===============================================
        
        Unified healthcare field service management with AI-powered staff assignment:
        
        Field Service Management:
        - Field Service Orders (FSO) for home visit coordination
        - Automatic FSO generation from confirmed appointments
        - Real-time communication system for field staff
        - Equipment tracking and management
        - Clinical protocol templates with action steps
        - Draft invoice creation for Vietnamese tax compliance
        - Mobile-first interface for field workers
        - GPS tracking and route optimization
        
        AI Staff Assignment:
        - Machine learning-powered staff optimization
        - Intelligent assignment based on skills, location, workload
        - Predictive analytics for assignment success
        - Real-time availability matrix
        - Skills and competency management
        - Service area optimization
        - Staff performance analytics
        
        Workflow:
        1. Patient booking creates unified FSO (Booking = FSO)
        2. FSO created with clinical protocol → AI staff assignment
        3. Staff assigned with equipment → Mobile dispatch notification
        4. Real-time tracking → Status updates via mobile app
        5. Service completion → Finalize invoice → MOH submission
        
        Integration:
        - Unified FSO booking system (no separate appointments)
        - Consolidated field service and staff assignment system
        - Automatic invoice generation for Vietnamese compliance
        - Equipment management for portable medical devices
        
        Vietnamese Healthcare Compliance:
        - Draft invoice creation upon FSO generation
        - Real-time tax authority submission
        - Clinical documentation requirements
        - MOH service delivery tracking
    """,
    'author': 'I Am Dream Catcher Ltd',
    'website': 'https://vafhs.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'account',  # For invoice generation
        'sale',     # For quote/sales order integration
        'hr',
        'contacts',
        'web',
        'health_base',  # Our foundation healthcare module
    ],
    'data': [
        # Security
        'security/health_fieldservice_security.xml',
        'security/health_staff_assignment_security.xml',
        'security/ir.model.access.csv',
        
        # Data
        'data/health_fieldservice_stages.xml',
        'data/health_clinical_protocols.xml',
        'data/ir_sequence.xml',
        'data/health_staff_assignment_data.xml',
        'data/health_ai_assignment_cron.xml',
        'data/report_paperformat.xml',
        'data/moh_server_actions.xml',

        # Reports
        'report/moh_reports.xml',
        'report/moh_report_template.xml',

        # Wizards
        'views/health_staff_assignment_wizard_views.xml',
        'views/health_booking_cancel_wizard_views.xml',

        # Views - Field Service
        'views/health_fieldservice_order_views.xml',
        'views/health_fieldservice_stage_views.xml',
        'views/health_fieldservice_team_views.xml',
        'views/health_portable_equipment_views.xml',
        'views/health_clinical_protocol_views.xml',
        'views/health_fieldservice_communication_views.xml',
        'views/health_quote_views.xml',
        'views/health_fieldservice_menus.xml',
        
        # Views - Staff Assignment  
        'views/health_staff_assignment_views.xml',
        'views/health_ai_assignment_engine_views.xml',
        'views/health_staff_availability_views.xml',
        'views/healthcare_skill_views.xml',
        'views/healthcare_staff_views.xml',
        'views/assignment_dashboard_views.xml',
        'views/assignment_scheduler_grid.xml',
        'views/assignment_web_timeline_views.xml',
        'views/assignment_timeline_views.xml',
        'views/staff_workload_dashboard_views.xml',
        'views/res_partner_views.xml',
        'views/health_staff_assignment_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            # CSS Assets
            'health_fieldservice/static/src/css/healthcare_quote.css',
            'health_fieldservice/static/src/css/service_timer.css',
            'health_fieldservice/static/src/css/assignment_dashboard.css',
            'health_fieldservice/static/src/css/assignment_timeline_view.css',
            'health_fieldservice/static/src/css/scheduler_grid.css',
            'health_fieldservice/static/src/css/staff_workload_dashboard.css',
            'health_fieldservice/static/src/css/web_timeline_custom.css',
            'health_fieldservice/static/src/css/web_timeline_card.css',
            # JavaScript Assets (Restored - was working before analytics uninstall)
            'health_fieldservice/static/src/js/assignment_dashboard.js',
            'health_fieldservice/static/src/js/assignment_kanban.js',
            'health_fieldservice/static/src/js/assignment_timeline_view.js',
            'health_fieldservice/static/src/js/scheduler_grid.js',
            'health_fieldservice/static/src/js/staff_workload_dashboard.js',
            'health_fieldservice/static/src/js/timeline_card_enhancer.js',
            'health_fieldservice/static/src/js/healthcare_quote_save.js',
            'health_fieldservice/static/src/js/healthcare_quote_form.js',
            'health_fieldservice/static/src/js/service_timer.js',
            # XML Templates
            'health_fieldservice/static/src/xml/assignment_dashboard.xml',
            'health_fieldservice/static/src/xml/assignment_timeline_view.xml',
            'health_fieldservice/static/src/xml/staff_workload_dashboard.xml',
            'health_fieldservice/static/src/xml/service_timer.xml',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': False,  # This extends health_base with unified FSO
    'sequence': 110,
}