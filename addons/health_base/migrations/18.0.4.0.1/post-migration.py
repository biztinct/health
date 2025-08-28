# -*- coding: utf-8 -*-

def migrate(cr, version):
    """
    Migration to fix database schema inconsistencies for res.partner healthcare fields
    
    This fixes the issue where uninstalling health_crm left database in inconsistent state
    where Odoo expects healthcare classification fields but they don't exist in database.
    """
    
    # Check if healthcare classification fields exist, create them if missing
    healthcare_fields = [
        ('is_patient', 'boolean', 'FALSE'),
        ('is_healthcare_staff', 'boolean', 'FALSE'), 
        ('is_healthcare_facility', 'boolean', 'FALSE'),
        ('is_emergency_contact', 'boolean', 'FALSE'),
        ('is_caregiver', 'boolean', 'FALSE'),
        ('is_payer', 'boolean', 'FALSE'),
        ('is_referrer', 'boolean', 'FALSE'),
        ('patient_code', 'varchar', 'NULL'),
        ('first_name', 'varchar', 'NULL'),
        ('last_name', 'varchar', 'NULL'),
        ('middle_name', 'varchar', 'NULL'),
        ('birth_date', 'date', 'NULL'),
        ('age', 'integer', '0'),
        ('gender', 'varchar', 'NULL'),
        ('patient_category_id', 'integer', 'NULL'),
        ('blood_group', 'varchar', "'unknown'"),
        ('allergies', 'text', 'NULL'),
        ('medical_history', 'text', 'NULL'),
        ('emergency_contact_relation', 'varchar', 'NULL'),
        ('primary_caregiver_id', 'integer', 'NULL'),
        ('primary_payer_id', 'integer', 'NULL'),
        ('primary_referrer_id', 'integer', 'NULL'),
        ('insurance_provider', 'varchar', 'NULL'),
        ('insurance_number', 'varchar', 'NULL'),
        ('insurance_expiry', 'date', 'NULL'),
        ('payment_method', 'varchar', "'cash'"),
        ('patient_status', 'varchar', "'new'"),
        ('registration_date', 'timestamp', 'NULL'),
        ('last_visit_date', 'timestamp', 'NULL'),
        ('next_visit_date', 'timestamp', 'NULL'),
        ('source_type', 'varchar', 'NULL'),
        ('source_details', 'varchar', 'NULL'),
        ('referral_source', 'varchar', 'NULL'),
        ('primary_facility_id', 'integer', 'NULL'),
        ('facility_id', 'integer', 'NULL'),
        ('license_number', 'varchar', 'NULL'),
        ('license_expiry', 'date', 'NULL'),
        ('vietnamese_name', 'varchar', 'NULL'),
        ('national_id', 'varchar', 'NULL'),
    ]
    
    for field_name, field_type, default_value in healthcare_fields:
        # Check if column exists
        cr.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='res_partner' 
            AND column_name=%s
        """, (field_name,))
        
        if not cr.fetchone():
            # Column doesn't exist, create it
            if field_type == 'boolean':
                cr.execute(f"""
                    ALTER TABLE res_partner 
                    ADD COLUMN {field_name} boolean DEFAULT {default_value}
                """)
            elif field_type == 'varchar':
                default_clause = f"DEFAULT {default_value}" if default_value != 'NULL' else ''
                cr.execute(f"""
                    ALTER TABLE res_partner 
                    ADD COLUMN {field_name} varchar {default_clause}
                """)
            elif field_type == 'text':
                cr.execute(f"""
                    ALTER TABLE res_partner 
                    ADD COLUMN {field_name} text
                """)
            elif field_type == 'integer':
                default_clause = f"DEFAULT {default_value}" if default_value != 'NULL' else ''
                cr.execute(f"""
                    ALTER TABLE res_partner 
                    ADD COLUMN {field_name} integer {default_clause}
                """)
            elif field_type == 'date':
                cr.execute(f"""
                    ALTER TABLE res_partner 
                    ADD COLUMN {field_name} date
                """)
            elif field_type == 'timestamp':
                cr.execute(f"""
                    ALTER TABLE res_partner 
                    ADD COLUMN {field_name} timestamp
                """)
            
            print(f"Created missing column: res_partner.{field_name}")
    
    # Create healthcare categories if they don't exist - using ORM to avoid SQL issues
    try:
        from odoo import registry, api, SUPERUSER_ID
        
        # Use ORM instead of raw SQL to avoid JSON field issues
        with api.Environment.manage():
            env = api.Environment(cr, SUPERUSER_ID, {})
            
            # Create Patient category
            if not env['res.partner.category'].search([('name', '=', 'Patient')]):
                env['res.partner.category'].create({
                    'name': 'Patient',
                    'color': 4,
                })
                print("Created Patient category")
            
            # Create Healthcare Staff category
            if not env['res.partner.category'].search([('name', '=', 'Healthcare Staff')]):
                env['res.partner.category'].create({
                    'name': 'Healthcare Staff', 
                    'color': 2,
                })
                print("Created Healthcare Staff category")
                
            # Create Healthcare Facility category
            if not env['res.partner.category'].search([('name', '=', 'Healthcare Facility')]):
                env['res.partner.category'].create({
                    'name': 'Healthcare Facility',
                    'color': 6,
                })
                print("Created Healthcare Facility category")
    
    except Exception as e:
        print(f"Warning: Could not create partner categories using ORM: {e}")
        # Fallback: Try simpler SQL approach
        try:
            cr.execute("""
                INSERT INTO res_partner_category (name, color, create_uid, create_date, write_uid, write_date)
                SELECT 'Patient', 4, 1, NOW(), 1, NOW()
                WHERE NOT EXISTS (SELECT 1 FROM res_partner_category WHERE name='Patient')
            """)
        except Exception as sql_error:
            print(f"Warning: Could not create Patient category: {sql_error}")
    
    print("Healthcare base migration completed - database schema fixed")