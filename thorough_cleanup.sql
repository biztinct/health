-- THOROUGH cleanup of all health module traces
-- This will completely wipe all health module data

BEGIN;

-- 1. Drop any health-related tables that might exist (be careful with this!)
DO $$ 
DECLARE 
    r RECORD;
BEGIN
    FOR r IN (SELECT tablename FROM pg_tables WHERE tablename LIKE 'health_%') 
    LOOP
        EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(r.tablename) || ' CASCADE';
    END LOOP;
END $$;

-- 2. Remove all health module entries
DELETE FROM ir_module_module WHERE name LIKE 'health_%';

-- 3. Remove ALL ir_model_data entries for health modules
DELETE FROM ir_model_data WHERE module LIKE 'health_%';

-- 4. Remove health models
DELETE FROM ir_model WHERE model LIKE 'health.%';

-- 5. Remove health model fields
DELETE FROM ir_model_fields WHERE model LIKE 'health.%';

-- 6. Remove health security rules
DELETE FROM ir_rule WHERE model_id IN (SELECT id FROM ir_model WHERE model LIKE 'health.%');

-- 7. Remove health access rights
DELETE FROM ir_model_access WHERE model_id IN (SELECT id FROM ir_model WHERE model LIKE 'health.%');

-- 8. Remove health views
DELETE FROM ir_ui_view WHERE model LIKE 'health.%';

-- 9. Remove health actions
DELETE FROM ir_actions_act_window WHERE res_model LIKE 'health.%';

-- 10. Remove health menus
DELETE FROM ir_ui_menu WHERE name LIKE '%Health%' AND name NOT LIKE '%Server Health%';

-- 11. Remove health sequences
DELETE FROM ir_sequence WHERE code LIKE 'health.%' OR code LIKE 'res.partner.patient';

-- 12. Remove health mail templates
DELETE FROM mail_template WHERE model LIKE 'health.%';

-- 13. Remove health scheduled actions
DELETE FROM ir_cron WHERE name LIKE '%health%' OR name LIKE '%Health%';

-- 14. Remove any health-related data records by name pattern
DELETE FROM ir_model_data WHERE name LIKE '%health%' OR name LIKE '%patient%' OR name LIKE '%medical%';

-- 15. Clean up partner and employee field extensions that might conflict
DELETE FROM ir_model_fields WHERE name IN (
    'is_patient', 'patient_code', 'patient_status', 'patient_category_id',
    'is_healthcare_staff', 'healthcare_role', 'staff_code'
) AND model IN ('res.partner', 'hr.employee');

-- 16. Remove any constraint records that might reference health fields
DELETE FROM ir_model_constraint WHERE name LIKE '%health%' OR name LIKE '%patient%' OR name LIKE '%medical%';

-- 17. Clear any cached/related data
DELETE FROM ir_attachment WHERE res_model LIKE 'health.%';

COMMIT;

-- Vacuum to clean up space
VACUUM;