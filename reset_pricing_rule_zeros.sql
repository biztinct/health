-- Reset zero values to NULL in pricing rules to avoid restrictive conditions
-- Run this in your PostgreSQL database to fix existing rules

UPDATE advanced_pricing_rule 
SET 
    distance_min = NULL,
    distance_max = NULL,
    appointment_hour_min = NULL,
    appointment_hour_max = NULL,
    service_units_min = NULL,
    service_units_max = NULL
WHERE 
    distance_min = 0.0 
    OR distance_max = 0.0 
    OR appointment_hour_min = 0 
    OR appointment_hour_max = 0
    OR service_units_min = 0 
    OR service_units_max = 0;

-- Check the results
SELECT id, name, distance_min, distance_max, appointment_hour_min, appointment_hour_max, 
       is_after_hours_required, service_units_min, service_units_max
FROM advanced_pricing_rule 
WHERE active = true;