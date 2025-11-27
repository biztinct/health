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
        'sales_team',  # CRM Teams functionality - required for menu actions
        'health_base',  # CRITICAL: Must load first - defines res.partner extensions (is_caregiver, etc.)
        'health_fieldservice',  # Appointment integration (appointments are in fieldservice module)
    ],
    'data': [
        # Security
        'security/health_crm_security.xml',
        'security/ir.model.access.csv',
        
        # Data
        'data/health_crm_teams.xml',  # MUST load first - defines teams referenced by stages
        'data/health_crm_stages.xml',
        'data/utm_sources_vietnamese.xml',
        'data/health_contact_reasons.xml',  # Load contact reasons data
        'data/health_lead_reasons.xml',     # Load lead reasons data
        'data/health_provinces.xml',        # Load province data
        
        # Views - CRM Extensions
        'views/health_client_relation_views.xml',
        'views/relationship_network_view.xml',  # Section 2.2 Option B - D3.js network graph
        'views/res_partner_relation_views.xml',  # Section 2.2 relationship dashboard
        'views/health_lookup_views.xml',    # Contact and lead reason views
        'views/crm_lead_views.xml',
        'views/res_partner_views.xml',
        'views/health_crm_menus.xml',
        'views/booking_lost_wizard_views.xml',

        # Wizards
        'wizard/client_selection_wizard_views.xml',
        'wizard/relationship_add_wizard_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            # D3.js library (local copy with LICENSE)
            'health_crm/static/lib/d3/d3.min.js',
            # Test widget (for debugging)
            'health_crm/static/src/js/test_widget.js',
            'health_crm/static/src/xml/test_widget.xml',
            # Relationship graph widget (D3.js network visualization)
            'health_crm/static/src/js/relationship_graph_widget.js',
            'health_crm/static/src/xml/relationship_graph_widget.xml',
            'health_crm/static/src/scss/relationship_graph_widget.scss',
            # Relationship hierarchy widget (Org chart style)
            'health_crm/static/src/components/relationship_hierarchy/relationship_hierarchy.js',
            'health_crm/static/src/components/relationship_hierarchy/relationship_hierarchy.xml',
            'health_crm/static/src/components/relationship_hierarchy/relationship_hierarchy.scss',
        ],
    },
    # 'demo': [
    #     'demo/health_crm_demo.xml',
    # ],
    'installable': True,
    'auto_install': False,
    'application': False,  # Extends existing CRM
    'sequence': 120,
}