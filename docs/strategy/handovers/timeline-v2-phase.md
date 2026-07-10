# Handover: Schedule Timeline v2 — `health_schedule_canvas` (+ web_timeline perf)

Read `docs/strategy/HANDOVER-CONVENTIONS.md` FIRST (definition of done =
its §8; gotcha ledger 26 entries — read all). This phase delivers the
three items the user called out on the live schedule (action 1536):
**draw-to-create** bookings, **off-hours/weekend space compression**,
and **week/month performance**. Unusually for this repo, you MAY edit
`addons/web_timeline` (our OCA fork) directly for the generic perf
work — the user explicitly authorized it. Schedule-specific behavior
still goes in the new module.

## 0. Scope

1. **Draw-to-create** (`health_schedule_canvas`): double-click on a
   staff lane opens the QUICK-BOOKING dialog pre-filled with that
   staff + time; saving creates the FSO + assignment through the
   shipped builder; the timeline reloads with the new block.
2. **Off-hours compression** (`health_schedule_canvas`): vis
   `hiddenDates` hides nights/weekends in Day/Week — but ANY window
   that actually contains a booking stays visible, and a persistent
   toolbar toggle reveals everything (bookings in off-hours are
   legitimate; the user was explicit).
3. **Performance** (`web_timeline` core + canvas): windowed data
   fetch, overlay thinning (the hiddenDates synergy), month-view
   clustering, parallel RPCs. Targets: Week paint < 1.5 s, Month
   < 3 s on vietuat data — measure before/after and report numbers.

**No PWA change ⇒ NO PWA bump.**

**Non-goals (binding):** resize-to-change-duration (still locked —
duration immunity stands); undo/redo; editing the drag gate
(health_schedule_drag) beyond consuming it; group virtualization;
replacing vis; month-view draw-create (day/week only — month cells
are too coarse to pick a time honestly); recurring-series creation.

## 1. Verified plumbing facts (do not re-derive; refs verified Jul 2026)

- **onAdd is already wired**: web_timeline renderer binds vis `onAdd`
  when `create="true"` (timeline_renderer.esm.js:194-197; the view XML
  has create="true", assignment_web_timeline_views.xml:16). Today the
  controller `_onAdd` (timeline_controller.esm.js:221-276) opens a
  raw assignment FormViewDialog with default_planned_* +
  default_staff_id — the WRONG tool (an assignment without a booking
  is meaningless). vis onAdd fires on double-tap; item carries
  {start, group}; `callback(null)` cancels the tentative item (always
  cancel — the real item arrives via reload).
- **Quick-booking builder**: `action_create_from_quick_booking_owl(
  vals)` (health_fieldservice_order.py:5488) accepts patient_id, date,
  time_hour, duration_hours, facility_id, staff_id, service_type…
  and creates FSO (+ assignment when staff_id passed). Find the OWL
  quick-booking dialog component health_fieldservice ships (the
  wizard get_booking_dialog_data RPC feeds it) and how CRM opens it —
  open THAT dialog pre-filled; only if it genuinely cannot be opened
  standalone from backend JS, fall back to a minimal owned dialog
  that collects patient + service and calls the builder. Report which
  path you took and why.
- **Gesture → dialog timezone**: timeline items are REAL-UTC basis
  (staff_schedule_timeline.esm.js:35-101; `toUtcStr` L47-49); the
  builder's `date` + `time_hour` are FACILITY-LOCAL wall clock —
  convert via the facility tz from `get_schedule_meta` (cached at
  L64-76). The +7h class of bug lives exactly here.
- **Refresh precedent**: rail-drop `_onRailDrop` → RPC → `_reloadAll()`
  (staff_schedule_timeline.esm.js:294-354, 373).
- **Off-hours backgrounds**: `get_schedule_overlay`
  (health_staff_assignment.py:1301-1441) emits per-staff-per-day 'off'
  segments + 'leave' — ≈2,700 background items for a 30-staff month.
  Overlay is cached per (window|facility) and debounced 250 ms
  (staff_schedule_timeline.esm.js:128-149, 222-224).
- **vis 7.7.3 is vendored** (web_timeline/static/lib/...) and supports
  `hiddenDates` ({start, end, repeat: 'daily'|'weekly'}) changeable at
  runtime via `setOptions`, and the `cluster` option
  ({maxItems, clusterCriteria...}). Neither is used today
  (timeline_arch_parser.esm.js:25-34 defaults: stack:true etc.).
- **No windowed fetch**: timeline_model.esm.js:55-79 `search_read`s
  ALL records matching the search domain — no visible-range clause,
  no limit. (1,231 assignments today; growing weekly.)
- **Scale buttons**: renderer `_onScale{Day,Week,Month}Clicked`
  (timeline_renderer.esm.js:94-127); the schedule overrides Day to
  06:00-20:00 facility time (staff_schedule_timeline.esm.js:163-176).
- **Working hours source**: `get_schedule_meta` returns facility tz +
  hours; `_check_emp_slot`/overlay derive per-staff working intervals —
  the hiddenDates windows must come from THE SAME source the overlay
  shades, or the two will disagree on screen.

## 2. Architecture

### 2.1 Draw-to-create (`health_schedule_canvas`, JS patch of the schedule controller)

Override `_onAdd` for the staff-schedule view ONLY (patch
StaffScheduleController — the schedule_drag precedent):
1. `callback(null)` immediately (never keep the tentative vis item).
2. Ignore double-clicks on the UNASSIGNED rail group and on non-staff
   groups. Month scale → info toast "Chuyển sang ngày/tuần để tạo
   lịch (switch to day/week to create)".
3. Snap the clicked time to 15 min. Pre-check `validate_drop(staff,
   start, start+60min, null)`: hard_block → do NOT block creation
   (off-hours bookings are legitimate — the user's explicit point);
   instead carry the message into the dialog flow as a visible
   warning line ("Ngoài giờ làm việc — vẫn tiếp tục? (outside working
   hours — continuing anyway)"). This deliberately differs from the
   drag gate: creating off-hours is a choice, moving into off-hours
   unseen is an accident.
4. Open the quick-booking dialog (§1) pre-filled: staff, facility (the
   staff's), date + time_hour (facility-local from the UTC click),
   duration default from the service chosen in the dialog.
5. On save → toast + `_reloadAll()`; on discard → nothing.
Ops-group gate: same `_OPS_GROUPS` server check the drag gate uses —
add a tiny `can_schedule_create()` @api.model (or reuse an existing
rights RPC if the dialog already enforces create rights) so nurses
double-clicking get the friendly refusal toast, not a dialog they
can't complete. Server-side enforcement rides the builder's own ACLs
(it creates FSOs — verify a plain nurse is actually refused by ACL,
and report).

### 2.2 Off-hours compression (`health_schedule_canvas`)

- Build `hiddenDates` dynamically per (scale, window) from
  `get_schedule_meta` working hours: Day/Week hide the common
  non-working band (e.g. 20:00→06:30 facility time, whatever meta
  says) with repeat 'daily'; Week also hides full weekend days
  (repeat 'weekly') when the facility doesn't work weekends per meta.
  Month: no hiddenDates (cells are days).
- **The balance rule**: before applying, scan the loaded items (+
  unassigned rail bookings); any item intersecting a would-be hidden
  window EXEMPTS that specific day's window (drop that hiddenDate
  entry — vis accepts an array of concrete ranges alongside repeats;
  compute concrete per-day ranges for the visible window instead of
  repeats if exemption granularity demands it). Re-evaluate on every
  data reload and window change (setOptions at runtime is supported).
- **Toolbar toggle** "Giờ nghỉ: Ẩn/Hiện (off-hours: hidden/shown)"
  next to the scale buttons, persisted in localStorage
  (`vu_sched_offhours`), default HIDDEN. The ergo pill/persistence
  precedent. When hidden, a thin visual break indicator is what vis
  renders natively — acceptable.
- **Synergy (do not skip)**: when a window is hidden, its 'off'
  background items are pointless — filter overlay backgrounds to
  VISIBLE time only before `setItems`. That alone removes most of the
  ≈2,700 month/week background items.

### 2.3 Performance

(a) **Windowed fetch (web_timeline core, opt-in)**: add view/arch
option `dynamic_range="1"` (arch parser + model): when set, the model
appends `['&', (date_start_field, '<', window_end + margin),
(date_stop_field or date_start_field, '>', window_start - margin)]`
to the search domain (margin = one window width) and the controller
refetches (debounced ~300 ms) on `rangechanged` when the new window
leaves the fetched span. Default OFF so every other timeline view in
the repo behaves exactly as before. The schedule view XML (inherit in
health_schedule_canvas, do not edit the shipped XML) sets the flag.
(b) **Overlay thinning**: §2.2 synergy + month-scale: skip 'off'
backgrounds entirely at month scale (keep 'leave'), server-side param
on get_schedule_overlay — an inherit adding an optional
`granularity` kwarg in the canvas module (do NOT edit the shipped
method signature — add a wrapper RPC if inheritance is awkward;
report).
(c) **Month clustering**: at month scale set vis `cluster:
{maxItems: 3, fitOnDoubleClick: true}` via setOptions; day/week
unclustered. Verify drag/onAdd interplay with clusters (clusters are
not draggable — acceptable at month scale where drag is coarse
anyway; the drag gate still protects if vis allows it).
(d) **Parallelize**: first paint must not await the overlay — paint
items, then apply overlay/hiddenDates when they arrive (they already
arrive debounced; ensure no `await` serializes meta → items →
overlay; Promise.all what can run together).
(e) **Measure**: performance.now() around load→first-paint for Week
and Month on vietuat data, before and after, in the report. If (a)
alone gets Month under target with (b), skip (c) and say so —
complexity budget is real.

## 3. Module skeleton

`health_schedule_canvas` depends `['health_fieldservice',
'health_schedule_drag']` (controller patch layering: canvas patches
must compose with drag's `_onMove` patch — patch() chains, verify
both live together). web_timeline edits: ONLY timeline_model /
timeline_controller / timeline_arch_parser for `dynamic_range`
(+ its README note), nothing schedule-specific in there. No new
models (one optional @api.model rights helper + optional overlay
wrapper). Config: none (the toggle is per-user localStorage). vi.po.

## 4. Tests (`tests/test_schedule_canvas.py` + web_timeline sanity)

Server-side (JS behavior is browser-QA'd):
1. `can_schedule_create` (if built): ops True / nurse False.
2. Builder path from gesture args: facility-local conversion — a
   02:00 UTC click on a +7 facility becomes date=D, time_hour=9.0 in
   the vals (unit-test the conversion helper you ship in JS by
   mirroring it in the model helper, or test the RPC wrapper).
3. Overlay granularity param: month scale returns zero 'off'
   backgrounds, still returns 'leave'; day/week unchanged (re-run
   /health_fieldservice timeline-related tests if any exist +
   /health_schedule_drag + /health_routes to prove the patches
   compose).
4. web_timeline `dynamic_range`: with the flag, the model's domain
   contains the window clause; without it, byte-identical domain
   (regression pin for every other timeline view).
5. hiddenDates builder (ship it as a small pure JS function + mirror
   the exemption logic server-side ONLY if you put it in Python —
   otherwise test via browser QA and say so).

**Browser QA on action 1536 REQUIRED with committed evidence**
(screenshots or exact-description doc): double-click → pre-filled
quick-booking dialog → saved booking appears; off-hours hidden by
default with a booking-containing weekend day visibly EXEMPTED; the
toggle revealing everything; Week/Month before/after timings; drag
(schedule_drag) still working with both patches live.

## 5. Deploy & verify

- `-i health_schedule_canvas -u web_timeline --test-tags
  /health_schedule_canvas,/health_schedule_drag,/health_routes`.
  Port-wait loop; logfile results; YOUR timestamp. web_timeline is a
  static-asset-heavy change — hard-refresh/clear assets in QA.
- Live demo: create a booking by double-click on a demo staff lane
  (clients 861-864), show it on the timeline + the FSO record; show
  an off-hours booking forcing its window visible; paste the
  before/after paint timings.
- vi.po, conventions §8, commit+push on 19.0.

## 6. Report-back extras

(a) which dialog path §2.1 took (shipped quick-booking dialog vs
owned minimal) and why; (b) before/after Week+Month paint timings and
which of §2.3(a-d) you actually needed; (c) the exemption rule's
behavior on the live data (how many hidden windows got exempted);
(d) confirmation the drag patch and canvas patch compose (both
features exercised in one session); (e) any web_timeline upstream
divergence worth noting in its README; (f) any new ledger-grade
gotcha (explicitly flagged).
