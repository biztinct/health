# Handover: Travel-Feasible Days — `health_routes`

Read `docs/strategy/HANDOVER-CONVENTIONS.md` FIRST (definition of done =
its §8; gotcha ledger 17 entries — read all). This is Tier 4's
`health_routes` in its v1 shape: make nurse days TRAVEL-FEASIBLE.
Today the platform schedules back-to-back visits across town as if
teleporting: nothing checks the gap between consecutive visits against
real travel time, the timeline lets ops drop an assignment anywhere,
and the family-page ETA assumes 25 km/h straight-line. All the pipes
exist (`driving_distance()` with Google→OSRM→approx fallback, matrix
`travel`/`buffer` fields nobody fills, `validate_drop`'s message
channel) — this module connects them. **v1 is warnings-only: nothing
blocks, nothing auto-moves.**

## 0. Scope (one new module `health_routes`)

1. **Distance cache** `health.route.leg` — every routed pair goes
   through it (external routers are slow and rate-limited).
2. **Transition checker** — the one shared function: for two
   consecutive visits, is the gap ≥ travel + buffer?
3. **Nightly feasibility sweep** (cron) over the next 7 days → per-day
   transition records + ONE ops activity per infeasible staff-day.
4. **Timeline soft warning** — `validate_drop` inherit appends a
   travel warning to its message; never hard-blocks.
5. **Slot proposer guard** — `_propose_slots_for_partner` inherit
   drops slots that would create a travel-CRITICAL transition.
6. **Family ETA upgrade** — the daystrip "on the way" ETA switches
   from 25 km/h haversine to cached road minutes (fallback to super).

**No PWA change ⇒ NO PWA bump** (everything is server-side; the family
page is server QWeb; the daystrip ETA override is Python).

**Non-goals (binding):** route OPTIMIZATION / re-ordering / suggested
sequences (v2 — v1 only judges the schedule as-is); any hard block on
booking/confirm/drop; map UI/tiles; live position tracking; per-staff
vehicle profiles; editing geo_utils.py or any shipped module's files
(all touches are inherits in THIS module); paid-API onboarding (Google
key stays optional — the existing fallback chain is the contract).

## 1. Verified plumbing facts (do not re-derive; refs verified Jul 2026)

- **Routing already exists**: `health_base/models/geo_utils.py` —
  `haversine_km(o_lat,o_lon,d_lat,d_lon)` (L48-56);
  `driving_distance(env, o_lat,o_lon,d_lat,d_lon)` (L102-120) returns
  `{'km','minutes','method':'google'|'osrm'|'approx'}` or None: tries
  Google DistanceMatrix (config `health_base.google_maps_api_key`,
  L59-82) → public OSRM (L85-99) → approx = 1.3× haversine @ 30 km/h.
  All helpers catch exceptions. **In test mode external requests raise
  "verboten"** (seen live in health_base geocode tests) → the chain
  lands on deterministic 'approx' — write your tests against that.
- **Coordinates**: patient `partner_latitude/longitude` (auto-geocoded
  via Photon on create/address-edit, res_partner.py:1148-1348, skips
  under `skip_auto_geocode`); facility `latitude/longitude`
  (health_facility.py:64-66); FSO has `travel_distance` +
  `travel_time_minutes` (L889-895, filled by `_update_travel_distance`
  L1759-1797 — facility→patient only, NOT visit-to-visit); coords can
  be MISSING — every path in this module must degrade to "unknown"
  (no warning row), never crash and never fake a number.
- **Day sequence**: FSOs for staff+date via
  `assignment_ids.staff_id` / `assigned_staff_ids`, ordered
  `scheduled_datetime`; per-FSO: `scheduled_datetime` (UTC),
  `scheduled_duration` (min), `estimated_end_datetime` (computed,
  L728-740), patient coords, `service_location`. **Skip
  `service_location == 'online'` visits entirely** (telehealth — no
  travel; they neither produce nor break transitions; the visit before
  and after an online visit form a direct pair).
- **Timeline API**: `health.staff.assignment.validate_drop(staff_id,
  start_iso, end_iso, assignment_id=None)`
  (health_staff_assignment.py:1493-1516) returns `{ok, hard_block,
  reason, message, overlap}` — the message field is the warning
  channel; the schedule UI (action 1536) already displays it.
- **Matrix**: `health.staff.availability.matrix` has
  `travel_time_from_previous` / `travel_time_to_next` (Float HOURS,
  health_staff_availability.py:107-116) and `buffer_before/after`
  (minutes) — shipped but never written. Statuses include
  `travel`/`buffer` (L35-43) — do NOT create travel/buffer rows in v1
  (that edits live scheduling data); only FILL the two float fields on
  rows that have an `fso_id`, as inert data.
- **Slot proposer**: `health.visit.offer._propose_slots_for_partner`
  (health_workflow_auto/models/visit_offer.py:123-191) — used by both
  offers and self-booking; returns slot dicts. No travel awareness
  today.
- **Family ETA**: `health_pwa_daystrip/models/health_family_link.py`
  `_travel_eta_text(event)` (L46-64) — 25 km/h haversine; override
  target.
- **Cron + ops-activity precedents**:
  health_workflow_auto/data/workflow_cron.xml (4 crons, the XML
  template); timecard mismatch model for the "detect → record →
  surface" pattern (health_workflow_auto/models/timecard_mismatch.py,
  15-min gap threshold, partial-unique open rows, auto-close);
  activity fallback precedent in crm_lead `_launch_first_visit_offer`.
- **District travel data** (fallback tier): `health.vietnamese.district`
  has `travel_zone` + `average_travel_time` minutes
  (health_base/models/health_lookup.py:234-264) — use as the
  coords-missing fallback ONLY when BOTH endpoints have districts:
  same district → its average_travel_time, different → max of the two.
  No districts either → unknown, no row.

## 2. Architecture

### 2.1 `health.route.leg` (distance cache)

| field | notes |
|---|---|
| o_lat/o_lng/d_lat/d_lng | Floats ROUNDED to 4 dp (≈11 m) — the cache key; unique index on the 4-tuple in `init()` |
| km / minutes / method | from `driving_distance()`; method incl. 'district'/'unknown' for the fallback tiers |
| computed_at | Datetime; entries older than `health_routes.leg_ttl_days` (default 30) are recomputed on next lookup (lazy — no cleanup cron) |

One accessor `leg_minutes(o_lat,o_lng,d_lat,d_lng)` — search-first,
then `driving_distance()`, then store. Symmetric pairs: normalize the
key so A→B and B→A share a row (v1 treats travel as symmetric — state
this in the module description). ALL module lookups go through it;
`health_routes.use_external_router=False` (config) skips straight to
the approx formula (no network, still cached).

### 2.2 The transition checker (one shared function)

`_check_transition(prev_fso, next_fso)` → dict `{gap_min, travel_min,
buffer_min, status}` with status:
- `ok`: gap ≥ travel + buffer
- `warn`: travel ≤ gap < travel + buffer
- `critical`: gap < travel
- `unknown`: either endpoint has no usable coords/district (produce NO
  stored row/warning — an unknown must never cry wolf)
gap = next.scheduled_datetime − prev.estimated_end_datetime (UTC math
end-to-end, no tz conversion needed); buffer = config
`health_routes.buffer_minutes` default 10. Endpoint of a visit =
patient coords; origin of the day's first visit is NOT checked in v1
(no facility-departure modeling — non-goal creep guard).

### 2.3 `health.route.transition` + nightly sweep

Stored row per checked transition: staff_id, date, prev_fso_id,
next_fso_id, gap_min, travel_min, status (warn/critical only — ok and
unknown are not stored), sweep batch stamp. Recompute per (staff,
date) = unlink that day's rows, re-create (idempotent; the
timecard-mismatch partial-unique pattern is NOT needed since we own
the whole day's rows). Cron `cron_route_feasibility_sweep` daily 03:00
(workflow_cron.xml template), horizon `health_routes.horizon_days`
default 7, scope = staff having ≥2 non-online FSOs that day. For each
staff-day with ≥1 `critical` row: ONE `mail.activity` on the FIRST
critical transition's next FSO, summary listing all that day's
critical pairs, assigned to the FSO's facility ops user or the cron
user (inspect what timecard/crm activities use; dedup: skip if an
open activity of this type already exists on that FSO). Bonus (cheap,
optional): write `travel_time_from_previous/to_next` (HOURS) onto the
matched matrix rows (`fso_id` set) during the sweep; skip silently if
rows absent.

### 2.4 Timeline soft warning (`validate_drop` inherit)

Post-super; only when `res.get('ok')` and not `hard_block`: find the
would-be neighbors of the dropped window among that staff's non-online
FSOs that date, run `_check_transition` on the affected pairs (with
the dropped assignment's own FSO), and on warn/critical APPEND to
`res['message']`: "Cần ~X phút di chuyển, chỉ còn Y phút (needs ~X min
travel, only Y min gap)". Whole inherit wrapped try/except → on ANY
exception return super's result untouched (the timeline must never
break because OSRM is down). Never set hard_block.

### 2.5 Slot proposer guard (`_propose_slots_for_partner` inherit)

Post-super over the returned slot list: for each slot, check the
transitions it would create against the slot staff's existing
non-online FSOs that day; DROP slots whose either transition is
`critical` (keep `warn` — availability beats perfection when slots
are scarce). try/except → on exception return super's list untouched.
Both offers and self-booking inherit the improvement for free — state
that in the report. (Matrix rows carry the slot's date/time; the
staff's day is queried per slot-date — batch the day queries, this
runs on a public page path. Budget: the whole post-filter must add
< ~1s for 6 slots with a warm leg cache; measure and report.)

### 2.6 Family ETA upgrade (`_travel_eta_text` override)

In this module (depends health_pwa_daystrip): try
`health.route.leg.leg_minutes(event GPS → patient coords)`; when it
returns real road minutes (method != 'unknown'), render the same
"khoảng X phút (about X min)" string with the same round-up-to-5 /
floor-5 rules; on None/unknown/exception → `return super()...`
(the 25 km/h estimate). No template change.

## 3. Module skeleton & config

Depends: `['health_workflow_auto', 'health_pwa_daystrip']` (pulls
fieldservice/pwa/evv/family transitively — all installed on vietuat).
Config (res_config_settings, self_booking pattern):
`health_routes.enabled` (True — warnings are passive),
`buffer_minutes` (10), `horizon_days` (7), `leg_ttl_days` (30),
`use_external_router` (**False on vietuat** — leave it off: UAT must
not hammer public OSRM; the approx tier is fine for demo. State the
switch position in the report). ACL: transitions/legs read nurse+,
write system flows + manager; no unlink below manager; catchment rule
pair on transitions (staff-keyed — mirror an existing staff-scoped
rule; legs are pure geometry, no catchment needed).

## 4. Tests (`tests/test_routes.py`)

Mock at the `driving_distance` boundary (or rely on the deterministic
'approx' tier — but then pin the formula's expected minutes in the
assert). Cases:

1. Transition math: ok / warn / critical / unknown (missing coords →
   no row), online visits excluded (a home→online→home day checks the
   home pair directly).
2. Leg cache: second identical lookup hits the cache (patch
   driving_distance with a call counter); 4-dp rounding + symmetric
   normalization share one row; TTL expiry recomputes.
3. Sweep: seed a staff-day with a teleport pair → critical row + ONE
   activity; re-run sweep → still one row set, no duplicate activity;
   fix the schedule → re-sweep clears the rows.
4. validate_drop: infeasible drop → ok stays True, hard_block stays
   False, message contains the travel warning; patched
   `_check_transition` raising → super result byte-identical.
5. Proposer guard: seed matrix + an existing visit far away → the
   conflicting slot disappears from `_propose_slots_for_partner`;
   exception path returns super's list; re-run `/health_workflow_auto`
   AND `/health_self_booking` (both consume the proposer).
6. Family ETA: leg cache hit → road minutes rendered; unknown → super
   fallback (re-run `/health_pwa_daystrip`).
7. `use_external_router=False` → no requests call (patch requests.get
   with a bomb), approx still cached.
8. Ledger §5.17 matrix-isolation rules apply to every proposer test.

## 5. Deploy & verify

- `-i health_routes --test-tags /health_routes,/health_workflow_auto,
  /health_self_booking,/health_pwa_daystrip` (three consumer suites
  must stay green). Port-wait loop after stop; read results from
  /var/log/odoo/odoo-server.log and verify the timestamp is YOUR run
  (both in the deploy memory).
- Live verify on vietuat: run the sweep on demo data (staff with two
  distant demo visits — create them on clients 861-864), show the
  critical transition row + the ops activity + the timeline drop
  warning text; show a leg-cache row with method 'approx'
  (use_external_router stays False). No PWA bump to verify.
- vi.po, conventions §8, commit+push on 19.0.

## 6. Report-back extras

(a) final `health_routes.*` positions (use_external_router must be
False on vietuat); (b) demo staff/FSO ids + the exact warning strings
rendered (timeline + activity); (c) proposer-guard timing measurement
(6 slots, warm cache); (d) whether you filled the matrix travel
fields (bonus) and on how many rows; (e) the activity assignee rule
you implemented and its precedent; (f) any new ledger-grade gotcha
(explicitly flagged).
