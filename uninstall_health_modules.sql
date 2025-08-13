-- SQL commands to manually uninstall health modules from database
-- WARNING: Backup your database before running these commands

-- Mark modules as uninstalled
UPDATE ir_module_module 
SET state = 'uninstalled' 
WHERE name IN ('health_base', 'health_calendar', 'health_staff_assignment');

-- Remove module dependencies
DELETE FROM ir_module_module_dependency 
WHERE module_id IN (
    SELECT id FROM ir_module_module 
    WHERE name IN ('health_base', 'health_calendar', 'health_staff_assignment')
);

-- Remove module data records (optional - will clean up demo data)
DELETE FROM ir_model_data 
WHERE module IN ('health_base', 'health_calendar', 'health_staff_assignment');

-- Clear any cached data
DELETE FROM ir_attachment 
WHERE res_model LIKE 'health.%';

-- Remove any scheduled actions related to health modules
DELETE FROM ir_cron 
WHERE ir_cron.id IN (
    SELECT imd.res_id 
    FROM ir_model_data imd 
    WHERE imd.module IN ('health_base', 'health_calendar', 'health_staff_assignment') 
    AND imd.model = 'ir.cron'
);