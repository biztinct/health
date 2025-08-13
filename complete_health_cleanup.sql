-- Complete cleanup of health module database traces
-- Run this to completely remove all health module references

BEGIN;

-- 1. Remove all health module entries from ir_module_module
DELETE FROM ir_module_module WHERE name LIKE 'health_%';

-- 2. Remove all ir_model_data entries for health modules (this fixes the duplicate key error)
DELETE FROM ir_model_data WHERE module LIKE 'health_%';

-- 3. Remove health models from ir_model
DELETE FROM ir_model WHERE model LIKE 'health.%';

-- 4. Remove health model fields
DELETE FROM ir_model_fields WHERE model LIKE 'health.%';

-- 5. Remove health security rules
DELETE FROM ir_rule WHERE model_id IN (
    SELECT id FROM ir_model WHERE model LIKE 'health.%'
);

-- 6. Remove health access rights
DELETE FROM ir_model_access WHERE model_id IN (
    SELECT id FROM ir_model WHERE model LIKE 'health.%'
);

-- 7. Remove health views
DELETE FROM ir_ui_view WHERE model LIKE 'health.%';

-- 8. Remove health actions
DELETE FROM ir_actions_act_window WHERE res_model LIKE 'health.%';

-- 9. Remove health menus
DELETE FROM ir_ui_menu WHERE action LIKE '%health%' OR name LIKE '%Health%';

-- 10. Remove health sequences
DELETE FROM ir_sequence WHERE code LIKE 'health.%';

-- 11. Remove any remaining health data records
DELETE FROM ir_model_data WHERE name LIKE '%health%' OR model LIKE 'health.%';

-- 12. Remove health mail templates
DELETE FROM mail_template WHERE model LIKE 'health.%';

-- 13. Remove health scheduled actions
DELETE FROM ir_cron WHERE name LIKE '%health%';

-- 14. Clean up any partner extensions that might conflict
DELETE FROM ir_model_fields WHERE name IN ('is_patient', 'patient_code', 'is_healthcare_staff') AND model = 'res.partner';

-- 15. Clean up any employee extensions that might conflict  
DELETE FROM ir_model_fields WHERE name IN ('is_healthcare_staff', 'healthcare_role', 'staff_code') AND model = 'hr.employee';

COMMIT;