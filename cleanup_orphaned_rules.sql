-- ==================================================================
-- SQL Script to Cleanup Orphaned Global Rules
-- ==================================================================
-- This script identifies and deletes record rules for 'health.%' models
-- that have NO security groups assigned. 
--
-- Context: When a Security Group is deleted, the link to its rules is removed.
-- If a rule was only linked to that group, it becomes "Global" (applies to everyone),
-- which is a major security risk.

DO $$
DECLARE
    rule_rec RECORD;
    deleted_count INTEGER := 0;
BEGIN
    RAISE NOTICE 'Starting cleanup of orphaned rules...';

    FOR rule_rec IN 
        SELECT r.id, r.name, m.model 
        FROM ir_rule r
        JOIN ir_model m ON r.model_id = m.id
        WHERE m.model LIKE 'health.%'  -- Target only Health modules
        AND r.active = true            -- Only active rules
        AND NOT EXISTS (               -- Check if it has NO groups
            SELECT 1 
            FROM rule_group_rel rel 
            WHERE rel.rule_group_id = r.id
        )
    LOOP
        RAISE NOTICE 'DELETING Orphaned Rule: "%" on model "%" (ID: %)', rule_rec.name, rule_rec.model, rule_rec.id;
        
        DELETE FROM ir_rule WHERE id = rule_rec.id;
        deleted_count := deleted_count + 1;
    END LOOP;

    RAISE NOTICE 'Cleanup Complete. Deleted % orphaned rules.', deleted_count;
END $$;
