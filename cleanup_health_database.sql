-- SQL commands to clean up health module leftovers from database
-- This will remove all traces of health modules from the database
-- IMPORTANT: Backup your database before running these commands!

-- 1. Remove health module records from ir_module_module
DELETE FROM ir_module_module 
WHERE name IN ('health_base', 'health_calendar', 'health_staff_assignment');

-- 2. Remove all data records created by health modules
DELETE FROM ir_model_data 
WHERE module IN ('health_base', 'health_calendar', 'health_staff_assignment');

-- 3. Remove security rules that reference health models
DELETE FROM ir_rule 
WHERE model_id IN (
    SELECT id FROM ir_model 
    WHERE model LIKE 'health.%' OR model LIKE 'res.partner' 
    AND id IN (
        SELECT model_id FROM ir_rule 
        WHERE domain_force LIKE '%is_patient%'
    )
);

-- 4. Remove access rights for health models
DELETE FROM ir_model_access 
WHERE model_id IN (
    SELECT id FROM ir_model 
    WHERE model LIKE 'health.%'
);

-- 5. Remove health model definitions
DELETE FROM ir_model 
WHERE model LIKE 'health.%';

-- 6. Remove health model fields (including is_patient)
DELETE FROM ir_model_fields 
WHERE model LIKE 'health.%' OR name LIKE '%patient%' OR name LIKE '%health%';

-- 7. Remove ir_rule entries that contain is_patient references
DELETE FROM ir_rule 
WHERE domain_force LIKE '%is_patient%';

-- 8. Remove any scheduled actions from health modules
DELETE FROM ir_cron 
WHERE ir_cron.id IN (
    SELECT imd.res_id 
    FROM ir_model_data imd 
    WHERE imd.module IN ('health_base', 'health_calendar', 'health_staff_assignment') 
    AND imd.model = 'ir.cron'
);

-- 9. Remove menu items from health modules
DELETE FROM ir_ui_menu 
WHERE ir_ui_menu.id IN (
    SELECT imd.res_id 
    FROM ir_model_data imd 
    WHERE imd.module IN ('health_base', 'health_calendar', 'health_staff_assignment') 
    AND imd.model = 'ir.ui.menu'
);

-- 10. Remove view definitions from health modules
DELETE FROM ir_ui_view 
WHERE ir_ui_view.id IN (
    SELECT imd.res_id 
    FROM ir_model_data imd 
    WHERE imd.module IN ('health_base', 'health_calendar', 'health_staff_assignment') 
    AND imd.model = 'ir.ui.view'
);

-- 11. Remove action definitions from health modules  
DELETE FROM ir_actions_act_window 
WHERE ir_actions_act_window.id IN (
    SELECT imd.res_id 
    FROM ir_model_data imd 
    WHERE imd.module IN ('health_base', 'health_calendar', 'health_staff_assignment') 
    AND imd.model = 'ir.actions.act_window'
);

-- 12. Clean up any remaining references in ir_model_data
DELETE FROM ir_model_data 
WHERE module IN ('health_base', 'health_calendar', 'health_staff_assignment');

-- 13. Clear the registry cache (this will be done automatically on restart)
-- No SQL needed for this

COMMIT;