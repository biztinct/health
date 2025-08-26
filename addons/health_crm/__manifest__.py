{
    'name': 'VAFHS Healthcare CRM Integration',
    'version': '18.0.1.0.0',
    'category': 'Healthcare/CRM',
    'summary': 'Healthcare CRM integration inheriting from standard Odoo CRM',
    'description': """
        VAFHS Healthcare CRM Integration
        ===============================
        
        CRM integration for Vietnamese healthcare providers:
        
        Features:
        - Inherits from standard Odoo CRM (crm.lead, res.partner)
        - Healthcare-specific lead qualification stages
        - Vietnamese contact channels (Zalo, Facebook, LinkedIn)
        - Service interest tracking (home visits, clinic visits)
        - Clinical priority classification
        - Vietnamese address structure support
        - Related party management (caregivers, payers, referrers)
        - Lead to appointment conversion workflow
        - Campaign source tracking for healthcare marketing
        
        Integration:
        - Links with health_fieldservice for appointment booking and service delivery
        - Supports health_invoicing for billing workflow
        
        Vietnamese Healthcare Compliance:
        - CCCD number tracking
        - Ethnicity and kinship title support
        - Vietnamese address template (Ngách, Ngõ, Phường/Xã)
        - Multi-provincial operations support
    """,
    'author': 'I Am Dream Catcher Ltd',
    'website': 'https://vafhs.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'crm',  # Standard Odoo CRM - we inherit from this
        'utm',  # UTM campaign tracking
        'health_base',  # CRITICAL: Must load first - defines res.partner extensions (is_caregiver, etc.)
        'health_fieldservice',  # Appointment integration (appointments are in fieldservice module)
    ],
    'data': [
        # Security
        'security/health_crm_security.xml',
        'security/ir.model.access.csv',
        
        # Data
        'data/health_crm_stages.xml',
        'data/health_crm_teams.xml',
        'data/utm_sources_vietnamese.xml',
        
        # Views - CRM Extensions
        'views/crm_lead_views.xml',
        'views/res_partner_views.xml',
        'views/health_client_representative_views.xml',
        'views/health_crm_menus.xml',
    ],
    'demo': [
        'demo/health_crm_demo.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,  # Extends existing CRM
    'sequence': 120,
}