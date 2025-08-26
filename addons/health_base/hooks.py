# -*- coding: utf-8 -*-

def post_init_hook(env):
    """
    Post-installation hook to ensure database schema consistency
    
    This prevents the 'column res_partner.is_caregiver does not exist' error
    by ensuring all healthcare fields are properly created in database.
    """
    
    # Force update of res.partner model to ensure all fields are created
    env['res.partner']._auto_init()
    
    # Verify critical healthcare fields exist
    critical_fields = [
        'is_patient', 'is_healthcare_staff', 'is_healthcare_facility', 
        'is_emergency_contact', 'is_caregiver', 'is_payer', 'is_referrer'
    ]
    
    partner_model = env['res.partner']
    for field_name in critical_fields:
        if field_name not in partner_model._fields:
            raise ValueError(f"Critical healthcare field {field_name} not found in res.partner model")
    
    # Ensure healthcare categories exist
    categories = [
        ('Patient', 1),
        ('Healthcare Staff', 2), 
        ('Healthcare Facility', 3),
    ]
    
    for name, color in categories:
        existing = env['res.partner.category'].search([('name', '=', name)])
        if not existing:
            env['res.partner.category'].create({
                'name': name,
                'color': color,
            })
    
    # Create external identifiers for categories (for other modules to reference)
    for name in ['Patient', 'Healthcare Staff', 'Healthcare Facility']:
        category = env['res.partner.category'].search([('name', '=', name)], limit=1)
        if category:
            xml_id = f"{name.lower().replace(' ', '_')}_category"
            existing_id = env['ir.model.data'].search([
                ('module', '=', 'health_base'),
                ('name', '=', xml_id)
            ])
            if not existing_id:
                env['ir.model.data'].create({
                    'module': 'health_base',
                    'name': xml_id,
                    'model': 'res.partner.category', 
                    'res_id': category.id,
                })
    
    print("Health Base post-init hook completed - schema verified")