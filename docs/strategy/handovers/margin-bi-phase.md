# Handover: Margin-per-Visit BI — `biz_bi_margin`

Read `docs/strategy/HANDOVER-CONVENTIONS.md` FIRST (definition of done =
its §8; gotcha ledger 21 entries — read all). This is Tier 5's
margin-per-visit analytics on the SHIPPED biz_bi platform: for every
completed visit, revenue minus direct cost (labor + travel +
commission), rolled up by service type / staff / facility / client /
month on seeded BI dashboards. The inputs only recently became real:
labor time from the EVV chain and the attendance sync, travel from
health_routes' leg cache, revenue from quotes/packages/invoices. No
competitor in this segment shows ops "which visits lose money" — this
is the finance moat phase.

**Respect the LOCKED biz_bi architecture** (silver=live view,
gold=materialized; join graph from a root; every identifier through
`SQL.identifier()`; RLS + company filter server-side; seed via
idempotent post_init hook — biz_bi_health/hooks.py is the canonical
precedent). Do not modify biz_bi core.

## 0. Scope (one new module `biz_bi_margin`)

1. **`bi_margin_visit` SQL view** — ONE ROW PER COMPLETED FSO with
   revenue, labor, travel, commission, margin columns (pre-aggregated
   so the BI join graph never fans out over multi-staff attendance).
2. **Cost-rate config** — the two numbers the data lacks: hourly labor
   cost fallback + per-km travel cost (with per-employee contract wage
   override when available).
3. **BI dataset** rooted on the view + dimension joins, seeded like
   biz_bi_health does (post_init, idempotent, certified).
4. **"Visit Margin" dashboard** seeded in the Finance workspace
   (biz_bi_health creates it — depend on it): KPI row + margin trend +
   per-service/staff/facility breakdowns + a "loss-making visits" list.

**No PWA change ⇒ NO PWA bump.** Backend/BI only.

**Non-goals (binding):** payroll-grade costing (no payslip math — v1
is rate × time with clearly-labeled assumptions); modifying biz_bi /
biz_bi_health existing files or datasets; per-visit overhead
allocation (facility rent etc. — v2); multi-currency (VND only,
biz_bi is single-currency per dataset); margin on quotes/leads (only
completed visits); any write-back to FSOs.

## 1. Verified plumbing facts (do not re-derive; refs verified Jul 2026)

- **Platform**: `bi.dataset` join graph (biz_bi/models/bi_dataset.py:
  256-710) — silver view `bi_silver_<id>` compiled at publish, gold
  `bi_gold_<id>` materialized via `bi.refresh.job` (bi_gold.py, serial
  advisory-lock queue, REFRESH CONCURRENTLY, auto-indexes). Sources:
  `bi.source` supports `type='sql_view'` with the `bi_*` name pattern
  (bi_source.py) — that is this module's mechanism. one2many edges set
  `has_fanout` and the engine guards measures — the pre-aggregated
  view avoids the whole problem.
- **Seeder precedent**: biz_bi_health/hooks.py:57-393 — post_init
  `HealthSeeder`: idempotency check first (L70-73), create dataset →
  root node → `action_scan_fields()` → child nodes + `bi.relationship`
  (cardinality many2one) → curate fields (visibility/labels/roles/
  `format_json` `{'currency':'VND'}`) → `action_publish()`. Root node
  must declare `company_field_id` before publish (bi_dataset.py:
  502-521). Workspaces (Operations/Finance/Growth) are created by
  biz_bi_health — search for the Finance one by name, don't recreate.
- **Revenue**: FSO `service_fee_vnd` = computed from
  `sale_order_id.amount_total` (health_fieldservice_order.py:
  1042-1045); `travel_fee` (L897) is charged revenue, not cost;
  package visits: `package_service_value` (health_invoicing FSO
  L130-136) values consumption at `price_per_service`; realized
  invoice via `invoice_id` + `is_invoiced` (health_invoicing FSO
  L23-34). Revenue precedence for the view (report any deviation):
  package_service_value when packages consumed, else
  service_fee_vnd, plus travel_fee. Add `revenue_source` column
  ('package'/'quote') — finance will ask.
- **Labor time** (per staff, per visit): `hr.attendance` rows with
  `fso_id` + `attendance_source='pwa_visit'`
  (health_workflow_auto/models/hr_attendance_sync.py:11-18) —
  check_in/out mirror actual start/end. Fallback when no attendance:
  `actual_end_datetime - actual_start_datetime`; fallback:
  `scheduled_duration`. Also surface `evv_verified_units` (health_evv
  FSO L43-48, 0.25h-floored verified hours) as its own column —
  the honest number for billing disputes; label which column the
  margin uses (attendance).
- **Labor rate**: NOTHING on hr.employee has a cost. `hr.contract`
  exists (om_hr_payroll via pb_hr_workforce) with `wage` (monthly
  VND). Rate = `wage / health_bi_margin.monthly_hours` (config,
  default 208) when an active contract exists, else config
  `default_hourly_cost_vnd` (default e.g. 45000 — pick something
  defensible, it's a config). INSPECT hr.contract's actual fields/
  state values before writing the SQL (don't guess; report what you
  found). Multi-staff visits sum each assigned staff's attendance
  minutes × their rate.
- **Travel**: FSO `travel_distance` (km) + `travel_time_minutes`
  (L897-898, filled by `_update_travel_distance` facility→patient).
  Travel cost v1 = `travel_distance × health_bi_margin.cost_per_km_vnd`
  (config, default 3000) + travel TIME cost = travel_time_minutes ×
  the same hourly labor rate (the nurse is paid while driving). The
  richer inter-visit legs (health.route.leg) are NOT per-FSO
  attributable in v1 — do not join them; note it as v2.
- **Commission**: FSO `commission_amount` (L1047-1053) — a direct
  cost line.
- **Completed visit** = `state IN ('completed',
  'completed_pending_invoice', 'closed')` (L45-55).
- **Currency/company**: single-company VND; the view must still carry
  `company_id` (root `company_field_id` requirement).
- **noupdate gotcha** (memory + conventions): seed XML with
  noupdate=1 won't re-apply on upgrade — all programmatic seeding in
  the hook with its own idempotency marker.

## 2. Architecture

### 2.1 The view (`data/bi_margin_visit_view.sql` executed in init/hook)

`CREATE OR REPLACE VIEW bi_margin_visit AS` — one row per completed
FSO. Columns (all *_vnd numeric):
fso_id, name, company_id, completed_date (date of actual_end,
fallback scheduled), facility_id, patient_id, service_type,
lead_staff_id, state, is_invoiced, revenue_source,
revenue_service_vnd, revenue_travel_vnd, revenue_total_vnd,
labor_minutes (summed attendance; fallback chain per §1),
labor_source ('attendance'/'actuals'/'scheduled'),
evv_verified_hours, labor_cost_vnd, travel_km, travel_cost_vnd,
commission_vnd, cost_total_vnd, margin_vnd,
margin_pct (NULL when revenue 0 — never divide by zero).
Rates read from `ir_config_parameter` INSIDE the SQL via scalar
subqueries with COALESCE defaults (so a config change is live on the
next query — no rebuild). Per-employee rate: LEFT JOIN the active
contract, `COALESCE(wage/monthly_hours, default_hourly)`.
The view is registered as a `bi.source` (`type='sql_view'`) by the
hook. Grant nothing directly — BI's engine reads it as the odoo user;
the DATASET's workspace ACL is the access control (Finance
workspace = finance/manager groups; verify how biz_bi_health's
Finance workspace is shared and mirror it).

### 2.2 Dataset

Root = the view source (company_field_id = company_id). Child nodes,
all many2one joins: facility (health.facility), patient
(res.partner), lead staff (hr.employee). Curate: measures
(revenue_total_vnd, labor_cost_vnd, travel_cost_vnd, commission_vnd,
cost_total_vnd, margin_vnd sum-agg + margin_pct avg-agg,
`{'currency':'VND'}` formats), dimensions (service_type,
completed_date as the date role, facility/patient/staff names,
revenue_source, labor_source), hide raw ids. `is_certified=True`.
Gold refresh job: daily (margin is a morning-report number, not
realtime) — create via the hook with the documented `bi.refresh.job`
fields.

### 2.3 Dashboard seed ("Visit Margin", Finance workspace)

Per biz_bi_health's dashboard seeding pattern (inspect how it builds
charts/dashboards in the hook — reuse its helper style): KPI cards
(visits, revenue, total cost, margin, margin %), margin_vnd by month
(line), margin by service_type (bar), margin by facility (bar),
bottom-20 visits by margin_vnd (table incl. patient/staff/date —
the "loss list"). Flat mono chart palette (platform default).

### 2.4 Config (`res_config_settings`, self_booking pattern)

`health_bi_margin.default_hourly_cost_vnd` (45000),
`.monthly_hours` (208), `.cost_per_km_vnd` (3000). A Settings block
labeling them explicitly as COSTING ASSUMPTIONS (vi+en help strings —
finance must know margin quality depends on these).

## 3. Module skeleton

`biz_bi_margin` depends `['biz_bi', 'biz_bi_health',
'health_invoicing', 'health_workflow_auto', 'health_evv']`
(workflow_auto ships the attendance fso_id column; evv ships
evv_verified_units; routes NOT required — travel fields are on core
FSO). post_init hook + idempotency marker param
(`biz_bi_margin.seeded`). vi.po. No new ACLs beyond what the hook
creates through biz_bi's own models.

## 4. Tests (`tests/test_bi_margin.py`)

1. View math: seed one completed FSO with known quote (500k), one
   attendance row (120 min), staff contract wage 8,320,000/208h
   (=40k/h → 80k labor), travel_distance 10 km (30k) +
   travel_time_minutes 30 (20k), commission 50k → assert one view row
   with margin_vnd = 500000 − 80000 − 30000 − 20000 − 50000 = 320000
   and margin_pct 64.0 (SELECT through the cursor).
2. Fallback chain: no attendance → actuals; no actuals → scheduled;
   labor_source column matches. No contract → default hourly.
3. Package visit: revenue_source='package',
   revenue = package_service_value.
4. Zero-revenue visit → margin_pct NULL (no division error).
5. Non-completed FSOs absent from the view; multi-staff visit sums
   both attendances.
6. Hook idempotency: run post_init twice → one dataset, one
   dashboard, marker set; dataset published, silver view exists
   (`SELECT 1 FROM bi_silver_<id> LIMIT 0` doesn't raise).
7. Config change reflects without republish (update cost_per_km →
   view row changes on next SELECT).
8. Rate-config parse safety: junk in the param → COALESCE default
   (no SQL error).

## 5. Deploy & verify

- `-i biz_bi_margin --test-tags /biz_bi_margin,/biz_bi` (prove the
  platform suite still green). Port-wait loop; logfile results; YOUR
  timestamp.
- Live verify on vietuat: the dataset publishes, the dashboard
  renders in the BI explorer (screenshot/describe), and quote REAL
  numbers: total completed visits in the view, how many have
  attendance-sourced labor vs fallback, how many have travel_distance
  populated, top + bottom margin visits (ids + numbers). This data
  honesty matters: if 90% of rows fall back to scheduled-duration
  labor, say so — it tells ops what to fix (PWA check-in adoption).
- vi.po, conventions §8, commit+push on 19.0.

## 6. Report-back extras

(a) the hr.contract fields/states you found and the exact rate SQL;
(b) the data-coverage numbers from §5 (labor_source and travel
coverage split); (c) the seeded dataset/dashboard ids + workspace
sharing you mirrored; (d) revenue-precedence deviations if any;
(e) view row count vs completed-FSO count (must match — explain any
gap); (f) any new ledger-grade gotcha (explicitly flagged).
