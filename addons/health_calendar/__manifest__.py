{
    'name': 'Healthcare Calendar & Appointments v2.0',
    'version': '18.0.4.0.0',
    'category': 'Healthcare',
    'summary': 'AI-Powered appointment booking and predictive scheduling system for VAFHS',
    'description': """
Healthcare Calendar & Appointment Management v2.0
================================================

AI-POWERED appointment booking and predictive scheduling system designed for Vietnam-Australia 
Family Health Service (VAFHS) healthcare operations.

🤖 NEW V2.0 AI FEATURES:
* Machine Learning-powered appointment optimization
* Predictive no-show probability calculations
* AI-driven staff scheduling recommendations
* Smart appointment time suggestions based on patient history
* Predictive demand forecasting for capacity planning
* Automated schedule optimization with ML algorithms
* Real-time appointment outcome predictions
* Advanced patient satisfaction forecasting

📋 CORE FEATURES:
* Exceptional patient portal booking experience (inspired by Calendly, Zocdoc)
* Mobile-first responsive design for seamless booking on any device
* Vietnamese & English bilingual support
* Advanced scheduling with real-time availability
* Home visit logistics with travel time calculation
* Staff availability management and automatic AI assignments
* Multiple appointment types (Clinic, Home Visit, Telemedicine)
* Online payment integration readiness
* SMS/Email appointment confirmations with risk alerts
* Automated reminders and follow-ups
* Calendar synchronization (Google, Outlook)
* Patient self-service booking portal
* Professional booking widget for website/social media integration

🧠 ML-ENHANCED WORKFLOW:
* Online booking → AI optimization → Confirmation → Smart staff assignment → 
  Predictive monitoring → Service delivery → AI feedback analysis → Follow-up

⚡ AUTOMATED INTELLIGENCE:
* Daily cron jobs for schedule optimization
* Weekly ML model training with latest data
* Hourly prediction updates for real-time insights
* No-show risk alerts for proactive patient engagement

This v2.0 module revolutionizes healthcare scheduling with artificial intelligence
while maintaining seamless integration with VAFHS clinical and billing systems.

📦 PACKAGE REQUIREMENTS:
CORE (Required for AI features):
* scikit-learn>=1.3.0 - Machine learning algorithms ✅
* pandas>=2.0.0 - Data manipulation ✅  
* numpy>=1.24.0 - Numerical computing ✅

OPTIONAL (Fallbacks implemented):
* python-fhir - Healthcare standards (uses internal structures)
* socketio - Real-time updates (uses standard Odoo notifications)

The system gracefully handles missing optional packages and provides full functionality
with just the core ML stack installed.
    """,
    'author': 'I Am Dream Catcher Ltd',
    'website': 'https://vafhs.com',
    'license': 'LGPL-3',
    'depends': [
        'health_base',  # Required for base health.patient model
        'calendar',
        'portal',
        'website',
        'mail',
        'contacts',
    ],
    'data': [
        # Security
        'security/health_calendar_security.xml',
        'security/ir.model.access.csv',
        
        # Data
        'data/health_calendar_data.xml',
        'data/health_predictive_cron.xml',
        
        # Views - Backend (actions first, then menus that reference them)
        'views/health_appointment_views.xml',
        'views/health_patient_views.xml',
        'views/health_appointment_type_views.xml',
        'views/health_predictive_scheduling_views.xml',
        'views/health_calendar_menus.xml',
        
        # Views - Portal & Website
        'views/booking_portal_templates.xml',
    ],
    'demo': [
        'data_demo/health_staff_demo.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'health_calendar/static/src/css/staff_availability_calendar.css',
            'health_calendar/static/src/js/calendar_utils.js',
            # Temporarily disable model - causing JS loading errors
            # 'health_calendar/static/src/js/staff_availability_model.js',
            # Temporarily disable bridge to isolate issue
            # 'health_calendar/static/src/js/assignment_calendar_bridge.js',
            'health_calendar/static/src/js/staff_availability_calendar.js',
        ],
        'web.assets_frontend': [
            'health_calendar/static/src/css/booking_portal.css',
            'health_calendar/static/src/js/booking_portal.js',
        ],
        'website.assets_frontend': [
            'health_calendar/static/src/css/booking_portal.css',
            'health_calendar/static/src/js/booking_portal.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'sequence': 15,
    'post_init_hook': 'post_init_hook',
}