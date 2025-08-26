-- SQL Script to fix healthcare database schema issues
-- Run this if you get "column res_partner.is_caregiver does not exist" errors

-- Healthcare classification boolean fields
ALTER TABLE res_partner ADD COLUMN IF NOT EXISTS is_patient boolean DEFAULT FALSE;
ALTER TABLE res_partner ADD COLUMN IF NOT EXISTS is_healthcare_staff boolean DEFAULT FALSE;  
ALTER TABLE res_partner ADD COLUMN IF NOT EXISTS is_healthcare_facility boolean DEFAULT FALSE;
ALTER TABLE res_partner ADD COLUMN IF NOT EXISTS is_emergency_contact boolean DEFAULT FALSE;
ALTER TABLE res_partner ADD COLUMN IF NOT EXISTS is_caregiver boolean DEFAULT FALSE;
ALTER TABLE res_partner ADD COLUMN IF NOT EXISTS is_payer boolean DEFAULT FALSE;
ALTER TABLE res_partner ADD COLUMN IF NOT EXISTS is_referrer boolean DEFAULT FALSE;

-- Patient identification fields
ALTER TABLE res_partner ADD COLUMN IF NOT EXISTS patient_code varchar;
ALTER TABLE res_partner ADD COLUMN IF NOT EXISTS first_name varchar;
ALTER TABLE res_partner ADD COLUMN IF NOT EXISTS last_name varchar;
ALTER TABLE res_partner ADD COLUMN IF NOT EXISTS middle_name varchar;

-- Healthcare details
ALTER TABLE res_partner ADD COLUMN IF NOT EXISTS birth_date date;
ALTER TABLE res_partner ADD COLUMN IF NOT EXISTS age integer DEFAULT 0;
ALTER TABLE res_partner ADD COLUMN IF NOT EXISTS gender varchar;
ALTER TABLE res_partner ADD COLUMN IF NOT EXISTS patient_category_id integer;
ALTER TABLE res_partner ADD COLUMN IF NOT EXISTS blood_group varchar DEFAULT 'unknown';

-- Medical information
ALTER TABLE res_partner ADD COLUMN IF NOT EXISTS allergies text;
ALTER TABLE res_partner ADD COLUMN IF NOT EXISTS medical_history text;
ALTER TABLE res_partner ADD COLUMN IF NOT EXISTS emergency_contact_relation varchar;

-- Healthcare relationships
ALTER TABLE res_partner ADD COLUMN IF NOT EXISTS primary_caregiver_id integer;
ALTER TABLE res_partner ADD COLUMN IF NOT EXISTS primary_payer_id integer;
ALTER TABLE res_partner ADD COLUMN IF NOT EXISTS primary_referrer_id integer;

-- Insurance and payment
ALTER TABLE res_partner ADD COLUMN IF NOT EXISTS insurance_provider varchar;
ALTER TABLE res_partner ADD COLUMN IF NOT EXISTS insurance_number varchar;
ALTER TABLE res_partner ADD COLUMN IF NOT EXISTS insurance_expiry date;
ALTER TABLE res_partner ADD COLUMN IF NOT EXISTS payment_method varchar DEFAULT 'cash';

-- Patient status and tracking
ALTER TABLE res_partner ADD COLUMN IF NOT EXISTS patient_status varchar DEFAULT 'new';
ALTER TABLE res_partner ADD COLUMN IF NOT EXISTS registration_date timestamp;
ALTER TABLE res_partner ADD COLUMN IF NOT EXISTS last_visit_date timestamp;
ALTER TABLE res_partner ADD COLUMN IF NOT EXISTS next_visit_date timestamp;

-- Source tracking
ALTER TABLE res_partner ADD COLUMN IF NOT EXISTS source_type varchar;
ALTER TABLE res_partner ADD COLUMN IF NOT EXISTS source_details varchar;
ALTER TABLE res_partner ADD COLUMN IF NOT EXISTS referral_source varchar;

-- Facility relationships
ALTER TABLE res_partner ADD COLUMN IF NOT EXISTS primary_facility_id integer;
ALTER TABLE res_partner ADD COLUMN IF NOT EXISTS facility_id integer;

-- Professional details
ALTER TABLE res_partner ADD COLUMN IF NOT EXISTS license_number varchar;
ALTER TABLE res_partner ADD COLUMN IF NOT EXISTS license_expiry date;

-- Vietnamese specific
ALTER TABLE res_partner ADD COLUMN IF NOT EXISTS vietnamese_name varchar;
ALTER TABLE res_partner ADD COLUMN IF NOT EXISTS national_id varchar;

-- Add foreign key constraints if tables exist
DO $$ 
BEGIN
    -- Add foreign key constraints only if target tables exist
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'health_patient_category') THEN
        ALTER TABLE res_partner ADD CONSTRAINT fk_patient_category 
        FOREIGN KEY (patient_category_id) REFERENCES health_patient_category(id);
    END IF;
    
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'health_facility') THEN
        ALTER TABLE res_partner ADD CONSTRAINT fk_primary_facility 
        FOREIGN KEY (primary_facility_id) REFERENCES health_facility(id);
        
        ALTER TABLE res_partner ADD CONSTRAINT fk_facility 
        FOREIGN KEY (facility_id) REFERENCES health_facility(id);
    END IF;
    
    -- Self-referencing constraints for healthcare relationships
    ALTER TABLE res_partner ADD CONSTRAINT fk_primary_caregiver 
    FOREIGN KEY (primary_caregiver_id) REFERENCES res_partner(id);
    
    ALTER TABLE res_partner ADD CONSTRAINT fk_primary_payer 
    FOREIGN KEY (primary_payer_id) REFERENCES res_partner(id);
    
    ALTER TABLE res_partner ADD CONSTRAINT fk_primary_referrer 
    FOREIGN KEY (primary_referrer_id) REFERENCES res_partner(id);
EXCEPTION
    WHEN others THEN
        -- Ignore constraint errors if they already exist
        NULL;
END $$;

-- Create healthcare categories if they don't exist
INSERT INTO res_partner_category (name, color, create_uid, create_date, write_uid, write_date)
SELECT 'Patient', 1, 1, NOW(), 1, NOW()
WHERE NOT EXISTS (SELECT 1 FROM res_partner_category WHERE name='Patient');

INSERT INTO res_partner_category (name, color, create_uid, create_date, write_uid, write_date)
SELECT 'Healthcare Staff', 2, 1, NOW(), 1, NOW()
WHERE NOT EXISTS (SELECT 1 FROM res_partner_category WHERE name='Healthcare Staff');

INSERT INTO res_partner_category (name, color, create_uid, create_date, write_uid, write_date)
SELECT 'Healthcare Facility', 3, 1, NOW(), 1, NOW()
WHERE NOT EXISTS (SELECT 1 FROM res_partner_category WHERE name='Healthcare Facility');

-- Verify all healthcare fields were created
SELECT 
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns 
WHERE table_name = 'res_partner' 
AND column_name IN (
    'is_patient', 'is_healthcare_staff', 'is_healthcare_facility',
    'is_emergency_contact', 'is_caregiver', 'is_payer', 'is_referrer',
    'patient_code', 'first_name', 'last_name'
)
ORDER BY column_name;