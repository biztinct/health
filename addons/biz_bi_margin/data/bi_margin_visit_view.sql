-- bi_margin_visit — ONE ROW PER COMPLETED FSO (handover §2.1).
-- Revenue − direct cost (labor + travel + commission) = margin.
-- Rates are read LIVE from ir_config_parameter via scalar subqueries with
-- COALESCE defaults and a numeric-safe cast (junk → default, never an error),
-- so a config change is reflected on the next query without a rebuild.
--
-- Environment realities on vietuat (see the module report):
--  * hr.contract does NOT exist (Odoo 19) — the per-employee wage comes from
--    the active hr.version (monthly VND); most staff have no wage → default.
--  * FSO has no company_id — single-company VND, so it is a constant column.
--  * lead_staff_id is a non-stored compute — primary_nurse_id is the stored
--    equivalent used as the lead dimension and the fallback labor rate.
CREATE OR REPLACE VIEW bi_margin_visit AS
WITH cfg AS (
    SELECT
        COALESCE((SELECT CASE WHEN value ~ '^\s*[0-9]+(\.[0-9]+)?\s*$'
                              THEN trim(value)::numeric END
                  FROM ir_config_parameter
                  WHERE key = 'health_bi_margin.default_hourly_cost_vnd'),
                 45000) AS default_hourly,
        COALESCE(NULLIF((SELECT CASE WHEN value ~ '^\s*[0-9]+(\.[0-9]+)?\s*$'
                                     THEN trim(value)::numeric END
                         FROM ir_config_parameter
                         WHERE key = 'health_bi_margin.monthly_hours'), 0),
                 208) AS monthly_hours,
        COALESCE((SELECT CASE WHEN value ~ '^\s*[0-9]+(\.[0-9]+)?\s*$'
                              THEN trim(value)::numeric END
                  FROM ir_config_parameter
                  WHERE key = 'health_bi_margin.cost_per_km_vnd'),
                 3000) AS cost_per_km
),
-- Per-visit attendance: summed minutes, plus cost at each worker's own rate.
att AS (
    -- GREATEST(…, 0): a corrected/buggy attendance row with check_out
    -- before check_in must not produce NEGATIVE labor minutes/cost.
    SELECT a.fso_id,
           SUM(GREATEST(EXTRACT(EPOCH FROM (a.check_out - a.check_in)), 0)
               / 60.0) AS minutes,
           SUM((GREATEST(EXTRACT(EPOCH FROM (a.check_out - a.check_in)), 0)
                / 3600.0)
               * COALESCE(
                   (SELECT v.wage FROM hr_version v
                    WHERE v.employee_id = a.employee_id AND v.active
                      AND v.wage > 0
                      AND (v.contract_date_end IS NULL
                           OR v.contract_date_end >= CURRENT_DATE)
                    ORDER BY v.contract_date_start DESC NULLS LAST
                    LIMIT 1) / (SELECT monthly_hours FROM cfg),
                   (SELECT default_hourly FROM cfg))) AS cost
    FROM hr_attendance a
    WHERE a.fso_id IS NOT NULL
      AND a.check_in IS NOT NULL AND a.check_out IS NOT NULL
    GROUP BY a.fso_id
),
base AS (
    SELECT
        o.id AS id,
        o.id AS fso_id,
        o.name AS name,
        o.facility_id, o.patient_id, o.service_type, o.state,
        o.primary_nurse_id AS lead_staff_id,
        o.is_invoiced,
        COALESCE(o.actual_end_datetime::date, o.scheduled_datetime::date)
            AS completed_date,
        CASE WHEN o.is_package_service THEN 'package' ELSE 'quote' END
            AS revenue_source,
        (CASE WHEN o.is_package_service THEN COALESCE(o.package_service_value, 0)
              ELSE COALESCE(o.service_fee_vnd, 0) END) AS revenue_service_vnd,
        COALESCE(o.travel_fee, 0) AS revenue_travel_vnd,
        COALESCE(o.evv_verified_units, 0) AS evv_verified_hours,
        COALESCE(o.travel_distance, 0) AS travel_km,
        COALESCE(o.commission_amount, 0) AS commission_vnd,
        -- lead staff hourly rate (active hr.version wage, else default)
        COALESCE(
            (SELECT v.wage FROM hr_version v
             WHERE v.employee_id = o.primary_nurse_id AND v.active
               AND v.wage > 0
               AND (v.contract_date_end IS NULL
                    OR v.contract_date_end >= CURRENT_DATE)
             ORDER BY v.contract_date_start DESC NULLS LAST
             LIMIT 1) / (SELECT monthly_hours FROM cfg),
            (SELECT default_hourly FROM cfg)) AS lead_rate,
        att.minutes AS att_minutes,
        att.cost AS att_cost,
        o.actual_start_datetime, o.actual_end_datetime, o.scheduled_duration,
        o.travel_time_minutes,
        (SELECT cost_per_km FROM cfg) AS cost_per_km
    FROM health_fieldservice_order o
    LEFT JOIN att ON att.fso_id = o.id
    WHERE o.state IN ('completed', 'completed_pending_invoice', 'closed')
),
calc AS (
    SELECT b.*,
        CASE WHEN b.att_minutes IS NOT NULL THEN b.att_minutes
             WHEN b.actual_start_datetime IS NOT NULL
                  AND b.actual_end_datetime IS NOT NULL
                  THEN EXTRACT(EPOCH FROM (b.actual_end_datetime
                                           - b.actual_start_datetime)) / 60.0
             ELSE COALESCE(b.scheduled_duration, 0) END AS labor_minutes,
        CASE WHEN b.att_minutes IS NOT NULL THEN 'attendance'
             WHEN b.actual_start_datetime IS NOT NULL
                  AND b.actual_end_datetime IS NOT NULL THEN 'actuals'
             ELSE 'scheduled' END AS labor_source,
        (b.revenue_service_vnd + b.revenue_travel_vnd) AS revenue_total_vnd,
        (b.travel_km * b.cost_per_km
         + COALESCE(b.travel_time_minutes, 0) / 60.0 * b.lead_rate)
            AS travel_cost_vnd
    FROM base b
),
calc2 AS (
    SELECT c.*,
        CASE WHEN c.att_cost IS NOT NULL THEN c.att_cost
             ELSE (c.labor_minutes / 60.0) * c.lead_rate END AS labor_cost_vnd
    FROM calc c
)
SELECT
    id, fso_id, name,
    (SELECT id FROM res_company ORDER BY id LIMIT 1) AS company_id,
    completed_date, facility_id, patient_id, service_type, lead_staff_id,
    state, is_invoiced, revenue_source,
    round(revenue_service_vnd::numeric, 2) AS revenue_service_vnd,
    round(revenue_travel_vnd::numeric, 2) AS revenue_travel_vnd,
    round(revenue_total_vnd::numeric, 2) AS revenue_total_vnd,
    round(labor_minutes::numeric, 2) AS labor_minutes,
    labor_source,
    round(evv_verified_hours::numeric, 2) AS evv_verified_hours,
    round(labor_cost_vnd::numeric, 2) AS labor_cost_vnd,
    round(travel_km::numeric, 2) AS travel_km,
    round(travel_cost_vnd::numeric, 2) AS travel_cost_vnd,
    round(commission_vnd::numeric, 2) AS commission_vnd,
    round((labor_cost_vnd + travel_cost_vnd + commission_vnd)::numeric, 2)
        AS cost_total_vnd,
    round((revenue_total_vnd
           - (labor_cost_vnd + travel_cost_vnd + commission_vnd))::numeric, 2)
        AS margin_vnd,
    CASE WHEN revenue_total_vnd > 0
         THEN round(((revenue_total_vnd
                      - (labor_cost_vnd + travel_cost_vnd + commission_vnd))
                     / revenue_total_vnd * 100)::numeric, 2)
         ELSE NULL END AS margin_pct
FROM calc2;
