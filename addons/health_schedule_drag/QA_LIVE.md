# health_schedule_drag — Live verification (vietuat)

Backend-timeline module (no PWA). The reschedule gate + its guards are proven
by 16 module tests (0 failed) plus the live evidence below. Simulating an actual
vis.js mouse-drag through DevTools is impractical, so the browser QA exercises
the exact server gate the patched `_onMove` invokes (the responses that drive
snap-back / confirm-dialog / reload), and the shell demo drives the full apply.

## Browser QA (care.biztinct.com, action 1536 — Staff Schedule)

The unified timeline renders: staff rows with working-hours bands + off-hours /
leave shading, the assignment-state legend, Day/Week/Month/Year, the facility
filter and the unassigned side rail (61 rows, 24 items in view). The
`health_schedule_drag` backend asset is bundled into `web.assets_backend`.

The gate the patched controller calls, invoked live via JSON-RPC from the page:

* **noop** — `reschedule_from_drag(assignment 3062, same start)` →
  `{status:'noop', fso_id:3014}` (dropped where it was → the JS accepts the item,
  no server change).
* **refused** — on assignment 2457 whose booking is `completed` →
  `{status:'refused', message:'Only confirmed or assigned bookings can be
  rescheduled by dragging. This one is completed.'}` — the JS shows this as a
  **danger toast and snaps the block back**.

## Server demo (shell, dry_run) — the full apply

Demo booking (FSO 3014, 2 assignments: DemoLead lead + DemoAsst support),
ops user, dragged 09:00 → 11:00 ICT (02:00 → 04:00 UTC):

    RESULT    ok   "Demo Reschedule Patient rescheduled to Mon 10 Aug 11:00."
    fso.scheduled_datetime   02:00 → 04:00 UTC
    a1 (DemoLead, lead)      planned → 04:00     role lead      (unchanged)
    a2 (DemoAsst, support)   planned → 04:00     role support   (SIBLING MOVED)
    ZNS   purpose=booking_rescheduled  state=simulated (dry_run)
          dedup=resched-3014-202608100400
          params.new_time = 11:00   (04:00 UTC → ICT wall-clock — correct)
    chatter   1 → 2 messages; body "…rescheduled to Mon 10 Aug 11:00."

So the shipped FSO-write path moved BOTH assignments coherently, the explicit
audit note landed on the chatter, and the patient ZNS simulated on the rails.

## Final switch positions (restored)

    health_messaging.enabled = False
    health_messaging.dry_run = True
    health_schedule_drag.zns_template_rescheduled = ''   (empty → no patient send)

## Report-back extras

* **(a) onMove seam:** `patch(StaffScheduleController.prototype, {_onMove})` on
  the shipped exported controller (no addon-file edit); refused → `callback(null)`
  snap-back + danger toast, needs_confirm → ConfirmationDialog then re-call with
  confirmed=true, ok → `callback(null)` + `_reloadTimeline()` (the FSO resync is
  the source of truth, never the local item write).
* **(b) matrix release:** UNLINK the FSO's `booked`+`buffer` rows (both carry
  fso_id) — chosen over a status reset because the rebook re-creates fresh rows;
  the zero-rows case is a clean no-op.
* **(c) demo ids/texts:** FSO 3014, a1 3061 / a2 3062; refusal text above;
  ok-toast "…rescheduled to Mon 10 Aug 11:00."
* **(e) nurse PWA:** the new time flows through the PWA's normal sync (the FSO
  scheduled_datetime moved); no PWA build (observed, not built).
