# health_schedule_canvas — Live verification (vietuat / care.biztinct.com)

Backend-timeline module (no PWA). The four features are proven by 21 module
tests (0 failed) plus the live evidence below. Simulating a real vis.js
double-click / mouse-drag through DevTools is impractical (same constraint noted
in health_schedule_drag), so the browser QA exercises the exact server gates the
patched controller/renderer invoke, and a shell demo drives the full create.

## Browser QA (care.biztinct.com, action 1536 — Staff Schedule)

Timeline renders: 61 staff rows, facility pills, the state/shading legend, the
Day/Week/Month/Year + 15m/30m/1h scale bars, the unassigned side rail. Loaded
arch confirms the canvas inherit applied:

    create="true"        → vis double-tap fires onAdd (draw-to-create)
    dynamic_range="1"    → windowed fetch active
    js_class="staff_schedule_timeline"

Live RPCs from the page session (the logged-in ops user):

* **can_schedule_create → true** (ops user). Tests confirm nurse → false.
* **schedule_canvas_prefill(staff 54, '2026-07-13 03:00:00')** →
  `{ok:true, can_create:true, date:'2026-07-13', time_hour:10, time_label:'10:00'}`
  — 03:00 UTC → 10:00 ICT (+7), the exact facility-local conversion the
  quick-booking dialog is pre-filled with. (The +7h-bug seam, correct.)
* **get_schedule_overlay** granularity: day scale → **120** 'off' backgrounds;
  `granularity='month'` → **0** 'off' (leave kept). The month overlay thinning.
* **Off-hours toggle** (`.hf-offhours-toggle`): renders in the toolbar,
  default **hidden**; click → "Off-hours: shown" (`localStorage vu_sched_offhours
  = 'shown'`); click → hidden again. Persisted per-user.

## dynamic_range — windowed fetch (measured live)

Emulating the model.load() search_read on live data (1,020 assignments):

    all assignments          1019 rows   81 ms
    windowed (week ± margin)     9 rows   20 ms      → 99% fewer rows, ~4× faster RPC

vis paint scales with item count, so the row reduction is the dominant paint
driver. (Re-timing the pre-patch paint would need a revert; the fetch-volume
before/after is the honest mechanism and is quoted above.)

## Server demo (shell, rolled back) — full draw-create + assign replacement

Draw-create — the exact two calls the dialog makes (staff 195 "CRM", facility 2
HCM, +7), click at 03:00 UTC:

    PREFILL           date=2026-07-12  time_hour=10.0  (03:00 UTC → 10:00 ICT)
    CREATE_RESULT     success=True  booking_id=3113  "12 Jul 2026, 10:00"
    NEW_ASG           planned 2026-07-12 03:00:00  state assigned
    DRAWN_MATCHES_ASG True     (the block lands at the drawn slot)

(NEW_FSO stays `draft` because a productless quick booking can't auto-confirm —
§16; the assignment is still created and appears. Ops refine on the form.)

Assign-from-booking (template mechanism retired, §2.4):

    action_manual_assign_staff()   templates_created = 0
    action context default_fso_id  = 3114
    create-dialog default_get      fso_id = 3114   (== action fso — context reaches
                                                     the dialog natively now)

## Template cleanup on vietuat (§2.4.4)

Orphan `state='template'` assignments removed: **3** active (post_init at install)
+ **47** archived (`active=False` — the fixed hook uses `active_test=False`) =
**50** total. Post-cleanup count: **0**.

## §2.3 items actually needed

Kept: (a) dynamic_range windowed fetch — the 99% win; (b) month overlay thinning
(off 120→0). Month clustering (c) is DISABLED (`ENABLE_MONTH_CLUSTER=false`) —
(a)+(b) carry the load and clusters don't compose cleanly with the custom
background items / drag gate. Full parallelization (d) deferred: the schedule's
facility-filter derives the allowed rows from the overlay, so items can't paint
strictly before it without decoupling that filter (noted, not done).

## Week-switch freeze — found & fixed (post-review browser QA)

User report: Day→Week switches visually, then a spinner runs "for a second" with
no further change. Measured on care.biztinct.com (main-thread block detector):

    BEFORE:  single 18,562 ms main-thread FREEZE on Day→Week; spinner up ~17.4 s
    CAUSE:   the overlay returns ~900 'off' background segments for a 7-day × 60-staff
             window; vis-timeline's background layout is super-linear → an ~18 s
             synchronous render. (Server overlay RPC itself was only ~600 ms — the
             XHR just looked slow because the main thread was frozen.) Day (120 bg)
             never froze. I had thinned only at MONTH and skipped the §2.2 "filter
             backgrounds to visible time" synergy.
    FIX:     _backgroundItems() now (a) in hidden mode drops 'off' segments that sit
             inside a hidden column (invisible anyway — the synergy), and (b) hard-caps
             'off' at 300, dropping them beyond that (shading is decorative). The
             off-hours toggle rebuilds backgrounds in place (no refetch).
    AFTER:   Day→Week freeze 18,562 ms → 289 ms (hidden) / 0 ms (shown); spinner
             17.4 s → ~0.5 s. Month: 0 ms freeze (granularity thinning). Week axis
             Fri 10→17 correct in all cases.

Both StaffScheduleController.prototype patches live together: health_schedule_drag
`_onMove` (reschedule-by-drag) and health_schedule_canvas `_onAdd` (draw-create).
The canvas asset loaded (toggle present) with drag as a dependency; the drag suite
is green in the same test run (0 failed of 49).
