{
    'name': 'Healthcare Calendar & Appointments',
    'version': '18.0.1.0.0',
    'category': 'Healthcare',
    'summary': 'Advanced appointment booking and scheduling system for VAFHS',
    'description': """
Healthcare Calendar & Appointment Management
===========================================

State-of-the-art appointment booking and scheduling system designed for Vietnam-Australia 
Family Health Service (VAFHS) healthcare operations.

Key Features:
* Exceptional patient portal booking experience (inspired by Calendly, Zocdoc)
* Mobile-first responsive design for seamless booking on any device
* Vietnamese & English bilingual support
* Advanced scheduling with real-time availability
* Home visit logistics with travel time calculation
* Staff availability management and automatic assignments
* Multiple appointment types (Clinic, Home Visit, Telemedicine)
* Online payment integration readiness
* SMS/Email appointment confirmations
* Automated reminders and follow-ups
* Calendar synchronization (Google, Outlook)
* Patient self-service booking portal
* Professional booking widget for website/social media integration

Appointment Workflow:
* Online booking → Confirmation → Staff assignment → Service delivery → Follow-up

This module transforms the patient experience with world-class booking capabilities
while maintaining full integration with VAFHS clinical and billing systems.
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
        
        # Views - Backend (actions first, then menus that reference them)
        'views/health_appointment_views.xml',
        'views/health_patient_views.xml',
        'views/health_appointment_type_views.xml',
        'views/health_calendar_menus.xml',
        
        # Views - Portal & Website
        'views/booking_portal_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
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