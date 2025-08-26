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
    
    # Create healthcare categories if they don't exist
    cr.execute("""
        INSERT INTO res_partner_category (name, color, parent_id, create_uid, create_date, write_uid, write_date)
        SELECT 'Patient', 1, NULL, 1, NOW(), 1, NOW()
        WHERE NOT EXISTS (SELECT 1 FROM res_partner_category WHERE name='Patient')
    """)
    
    cr.execute("""
        INSERT INTO res_partner_category (name, color, parent_id, create_uid, create_date, write_uid, write_date)
        SELECT 'Healthcare Staff', 2, NULL, 1, NOW(), 1, NOW()
        WHERE NOT EXISTS (SELECT 1 FROM res_partner_category WHERE name='Healthcare Staff')
    """)
    
    cr.execute("""
        INSERT INTO res_partner_category (name, color, parent_id, create_uid, create_date, write_uid, write_date)
        SELECT 'Healthcare Facility', 3, NULL, 1, NOW(), 1, NOW()
        WHERE NOT EXISTS (SELECT 1 FROM res_partner_category WHERE name='Healthcare Facility')
    """)
    
    print("Healthcare base migration completed - database schema fixed")