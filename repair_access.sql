-- ==================================================================
-- SQL Script to Repair FSO Access Rules
-- Run this in your Odoo database (e.g., via pgAdmin or psql)
-- ==================================================================

BEGIN;

-- 1. Hard Delete the restrictive "FSO Sales User Access" rule
-- This rule is blaming for the access error.
DELETE FROM ir_rule WHERE name = 'FSO Sales User Access';

-- 2. Hard Delete the obsolete "FSO Operations Manager Access" rule
-- This rule was restrictive and should have been removed.
DELETE FROM ir_rule WHERE name = 'FSO Operations Manager Access';

-- 3. Hard Delete the "FSO Head Nurse Access" rule (temporarily, to clear bad state)
DELETE FROM ir_rule WHERE name = 'FSO Head Nurse Access';

-- 4. Ensure the "FSO Field Service Manager Full Access" rule exists and is correct
-- First, delete it to be safe (we will recreate it)
DELETE FROM ir_rule WHERE name = 'FSO Field Service Manager Full Access';

-- Re-insert the Manager Full Access Rule
-- We need to find the group ID for 'Healthcare: Operations Manager'
-- and the model ID for 'health.fieldservice.order'

DO $$
DECLARE
    manager_group_id INTEGER;
    model_id INTEGER;
    rule_id INTEGER;
BEGIN
    -- Get Group ID (Handle JSONB translated field by casting to text)
    SELECT id INTO manager_group_id FROM res_groups WHERE name::text LIKE '%Healthcare: Operations Manager%' LIMIT 1;
    
    -- Get Model ID
    SELECT id INTO model_id FROM ir_model WHERE model = 'health.fieldservice.order' LIMIT 1;

    IF manager_group_id IS NOT NULL AND model_id IS NOT NULL THEN
        -- Insert Rule
        INSERT INTO ir_rule (name, model_id, domain_force, perm_read, perm_write, perm_create, perm_unlink, active, create_date, write_date, create_uid, write_uid)
        VALUES (
            'FSO Field Service Manager Full Access', 
            model_id, 
            '[(1, "=", 1)]', -- Full Access Domain
            true, true, true, true, -- Permissions
            true, -- Active
            NOW(), NOW(), 1, 1
        ) RETURNING id INTO rule_id;

        -- Link Rule to Group
        INSERT INTO rule_group_rel (rule_group_id, group_id) VALUES (rule_id, manager_group_id);
        
        RAISE NOTICE 'Recreated Manager Full Access Rule (ID: %)', rule_id;
    ELSE
        RAISE NOTICE 'Could not find Group or Model. Skipping Manager Rule creation.';
    END IF;
END $$;

COMMIT;
