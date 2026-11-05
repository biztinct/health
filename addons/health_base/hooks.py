# -*- coding: utf-8 -*-
from .lookup_migration import seed_lookup_values


def post_init_hook(env):
    """
    Post-installation hook to ensure database schema consistency

    This prevents the 'column res_partner.is_caregiver does not exist' error
    by ensuring all healthcare fields are properly created in database.

    Also seeds the client-maintained dropdown vocabularies, so a fresh install
    starts with exactly the options the old hardcoded Selection lists offered.
    """
    seed_lookup_values(env)

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

    # The audit log view has ONE definition: the model's init() (an older
    # copy here once overwrote it on fresh installs; UAT round 6).
    env['health.audit.log.view'].init()
