{
    'name': 'VAFHS Healthcare Invoicing Integration',
    'version': '18.0.1.0.11',
    'category': 'Healthcare/Accounting',
    'summary': 'Healthcare invoicing integration inheriting from standard Odoo accounting',
    'description': """
        VAFHS Healthcare Invoicing Integration
        =====================================
        
        Vietnamese healthcare invoicing system integrating with standard Odoo accounting:
        
        Features:
        - Inherits from standard Odoo accounting (account.move, account.payment)
        - Vietnamese tax compliance and real-time submission
        - Healthcare service billing automation
        - Integration with MISA accounting system
        - Insurance claim processing and tracking
        - Ministry of Health (MOH) regulatory compliance
        
        Healthcare Service Integration:
        - Auto-invoice creation from Field Service Orders (FSO)  
        - Package service consumption via FSO completion (NEW APPROACH)
        - Reusable healthcare package products in product catalog
        - Appointment-based billing workflow
        - Service-specific invoice templates (home visits, clinic visits)
        - Equipment and supplies billing
        - Staff time tracking and billing
        
        Package Service Architecture (UPDATED):
        - FSO direct package integration (replaces separate consumption model)
        - Service packages as first-class Odoo products
        - Automatic visit countdown via FSO completion
        - Mixed invoice line items (packages + supplies)
        - Patient package tracking in unified Patient Journey
        
        Vietnamese Compliance Features:
        - Real-time VAT submission to Tax Authorities
        - Vietnamese address structure support
        - CCCD and business registration tracking
        - Vietnamese currency and tax rate management
        - Regulatory invoice numbering sequences
        
        Integration Points:
        - Links with health_fieldservice for service delivery billing
        - Connects to health_crm for customer billing information
        - Supports health_compliance for regulatory submissions
        - Integrates with health_calendar for appointment billing
        
        From Client Requirements (Excel CRM_Invoicing_TablesFields):
        - Customer Master File (CMF) billing integration
        - Lead Management to invoice conversion workflow
        - Contact and Client Representative billing authorization
        - Service booking to invoice automation
        
        Vietnamese Healthcare Regulations:
        - Ministry of Health invoice submission
        - Healthcare service taxation compliance
        - Medical equipment billing regulations
        - Professional services tax handling
    """,
    'author': 'I Am Dream Catcher Ltd',
    'website': 'https://vafhs.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'sms',  # SMS notifications for payment reminders
        'account',  # Standard Odoo accounting - we inherit from this
        'account_payment',  # Payment processing
        'account_due_list',  # Enhanced AR due list management
        'account_payment_notification',  # Patient payment reminders via email/SMS
        'partner_time_to_pay',  # Patient payment analytics and trends
        'sale',  # Sales integration for service orders
        'purchase',  # Equipment and supplies purchasing
        'hr_timesheet',  # Staff time tracking
        'health_base',  # CRITICAL: Must load first - defines foundational healthcare models
        'health_fieldservice',  # Field service billing
        'health_crm',  # Customer billing information
    ],
    'data': [
        # Security
        'security/health_invoicing_security.xml',
        'security/ir.model.access.csv',
        
        # Configuration Data
        'data/sequences.xml',
        'data/vietnamese_tax_config.xml',
        
        # Wizards
        'views/health_payment_workflow_wizard_views.xml',
        'views/health_prepaid_package_wizard_views.xml',
        'views/health_payment_collection_wizard_views.xml',
        'views/health_nurse_payment_wizard_views.xml',
        'views/health_cash_delivery_wizard_views.xml',
        
        # Views - Accounting Extensions (Basic implementation first)
        'views/account_move_views.xml',
        'views/res_partner_views.xml',
        'views/health_fieldservice_order_views.xml',
        'views/product_template_views.xml',
        
        # Enhanced Payment System Views
        'views/health_service_package_views.xml',
        'views/health_payment_transaction_views.xml',
        'views/health_prepaid_service_views.xml',
        'views/health_ar_dashboard_views.xml',
        
        # Menus
        'views/health_invoicing_menus.xml',
    ],
    'demo': [
        'demo/health_invoicing_demo.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,  # Extends existing accounting
    'sequence': 130,
}