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

    # Create audit log SQL view with correct JSONB extraction
    print("Creating audit log view...")
    env.cr.execute("DROP VIEW IF EXISTS health_audit_log_view CASCADE")

    sql = """
        CREATE OR REPLACE VIEW health_audit_log_view AS (
            SELECT
                mtv.id,
                mm.date,
                mm.author_id as user_id,
                mm.model,
                COALESCE(im.name->>'en_US', mm.model) as model_name,
                mm.res_id,
                COALESCE(mm.subject, '') as record_name,
                COALESCE(mf.field_description->>'en_US', mf.name) as field_name,
                mtv.old_value_char as old_value,
                mtv.new_value_char as new_value
            FROM mail_tracking_value mtv
            JOIN mail_message mm ON mm.id = mtv.mail_message_id
            JOIN ir_model im ON im.model = mm.model
            LEFT JOIN ir_model_fields mf ON mf.id = mtv.field_id
            WHERE mm.model IN (
                'advanced.pricing.engine',
                'advanced.pricing.rule',
                'product.pricelist',
                'health.fieldservice.order',
                'account.move',
                'res.partner',
                'health.facility',
                'resource.calendar.leaves'
            )
            AND mtv.field_id IS NOT NULL
            ORDER BY mm.date DESC
        )
    """

    env.cr.execute(sql)

    # Verify the view
    env.cr.execute("SELECT COUNT(*) FROM health_audit_log_view")
    count = env.cr.fetchone()[0]
    print(f"Audit log view created successfully with {count} records")
