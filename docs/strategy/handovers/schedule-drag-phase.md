# Handover: Reschedule-by-Drag — `health_schedule_drag`

Read `docs/strategy/HANDOVER-CONVENTIONS.md` FIRST (definition of done =
its §8; gotcha ledger 23 entries — read all). This is the deferred
reschedule-drag phase on the unified staff schedule (action 1536,
web_timeline on `health.staff.assignment`): dragging an assignment
block to a new time/day/staff lane actually RESCHEDULES the booking —
validated, matrix-consistent, multi-staff-coherent, notified.

**Today's behavior is worse than nothing**: web_timeline's `_onMove`
(web_timeline/static/src/views/timeline/timeline_controller.esm.js:
134-171) writes `planned_start_time/planned_end_time` on the ONE
dragged assignment directly — the FSO never moves, sibling
assignments diverge, no validation runs, the availability matrix goes
stale, nobody is notified. Ops dragging a block today silently
corrupts the schedule. This phase makes drag either DO the right
thing or snap back.

## 0. Scope (one new module `health_schedule_drag`)

1. **Server method** `reschedule_from_drag(...)` on
   health.staff.assignment — the one gate every drag goes through.
2. **JS move-interception** on the schedule timeline: validate →
   confirm-if-warned → server reschedule → reload; refusal snaps back.
3. **Patient-notification purpose `booking_rescheduled`** on the
   messaging rails (empty template default = no sends).
4. Matrix consistency: release the stale booked slot, book the new one.

**No PWA change ⇒ NO PWA bump** (backend timeline only; the nurse PWA
learns the new time through its normal sync, and the existing staff
push notification fires — see §1).

**Non-goals (binding):** resize-to-change-duration (drag MOVES only;
lock item resizing if the timeline offers it); creating bookings by
drawing on the timeline; drag on the roster/other timeline views;
recurring-series propagation (single visit only); undo/redo;
cross-facility moves (same-facility staff lanes only — refuse
otherwise); editing web_timeline addon files or any shipped module's
files (JS patches + model inherits live in THIS module).

## 1. Verified plumbing facts (do not re-derive; refs verified Jul 2026)

- **Timeline**: view `health_staff_assignment_timeline_view`
  (health_fieldservice/views/assignment_web_timeline_views.xml:1-92) —
  date_start/date_stop = `planned_start_time/planned_end_time`,
  grouped by `staff_id`. Those two fields are stored computes with
  readonly=False (health_staff_assignment.py:178-191, computes at
  482-502): start prefers `fso_id.scheduled_datetime`, end = start +
  `fso.scheduled_duration`.
- **The golden reuse**: FSO `write()` ALREADY resyncs every
  non-template assignment's planned times when `scheduled_datetime`
  changes (health_fieldservice_order.py:1704-1731) — so the correct
  reschedule primitive is "write the FSO", and multi-staff coherence
  is free. It ALSO already fires the staff push notification
  (`_send_staff_reschedule_notification`, L2365-2442, called at
  L1728 with the pre-write old datetime) and `scheduled_datetime` is
  `tracking=True` (L397-401) so chatter is free too.
- **Validation**: `validate_drop(staff_id, start_iso, end_iso,
  assignment_id=None)` (health_staff_assignment.py:1493-1516) returns
  `{ok, hard_block, reason, message, overlap}`; health_routes inherits
  it to append travel warnings (health_routes/models/
  health_staff_assignment.py:23-53). The schedule JS already calls it
  for unassigned-rail drops and shows toast/confirm UX
  (health_fieldservice/static/src/js/staff_schedule_timeline.esm.js:
  327-354) — mirror that UX exactly.
- **Timezone basis**: this timeline's items live on the REAL-UTC
  basis and validate_drop parses ISO as UTC — documented at
  staff_schedule_timeline.esm.js:46 (and `_sched_parse_iso` at
  health_staff_assignment.py:1283-1298). Do not "fix" what isn't
  broken; pass ISO UTC strings end-to-end. (The vis wall-clock-as-UTC
  gotcha applies to OTHER vis views — this one already normalized.)
- **Move interception point**: web_timeline's controller `_onMove`
  handler (timeline_controller.esm.js:134-171) queues
  `model.write_completed(item.id, data)`. The schedule view uses a
  custom renderer/controller subclass registered by
  staff_schedule_timeline.esm.js — inspect how that view is
  registered (its own view type/registry entry) and OVERRIDE `_onMove`
  in a further subclass registered by THIS module for action 1536's
  view only. If the vis onMove callback contract allows revert
  (callback(null) or not calling back → snap-back), use it; report
  the exact mechanism you found.
- **Matrix**: `book_staff_slot` (health_staff_availability.py:271-318)
  creates booked + buffer rows keyed to fso_id. There is NO release
  method — inspect the rows book_staff_slot creates and write the
  inverse in this module (find rows with that fso_id + status
  booked/buffer and reset/unlink them; report your choice). A visit
  that was never matrix-booked (most legacy ones) must reschedule
  fine with zero matrix rows (both directions no-op).
- **States**: FSO reschedulable ONLY in `confirmed` / `assigned`.
  draft has nothing to protect (allow? NO — draft blocks aren't on
  this timeline anyway; refuse anything not confirmed/assigned,
  incl. in_progress/completed/cancelled).
- **Messaging rails**: purpose `selection_add` +
  `_send_*_zns`-copy precedent = health_family_link
  (models/outbound_message.py + health_family_link.py:294-359);
  params wall-clock via pytz `booking_timezone`; dedup key must
  include the NEW datetime (`resched-<fso>-<YYYYMMDDHHMM>`) so a
  second reschedule of the same visit sends again but a double-fire
  of the same move doesn't. Template param
  `health_schedule_drag.zns_template_rescheduled` (empty → no row).
  Rides `health_messaging.enabled/dry_run` exactly (OFF/dry on
  vietuat — final positions must stay).
- **Permissions**: assignment record rules (health_fieldservice/
  security/health_staff_assignment_security.xml:62-133) let staff
  edit their OWN assignments — a nurse could drag her own block.
  Reschedule is an OPS decision: server-side group guard
  (operations_manager/head_nurse/manager+, ai_coding
  both-layers lesson — though here the view layer can't easily hide
  drag, the SERVER guard is the contract; a non-ops drag gets a
  friendly refusal toast and snap-back).

## 2. Architecture

### 2.1 `reschedule_from_drag(assignment_id, start_iso, end_iso, new_staff_id, confirmed=False)`

`@api.model` on health.staff.assignment (this module's inherit).
Sequence — each step returns a structured dict, never raises for
expected conditions (`{status: 'ok'|'needs_confirm'|'refused',
message, fso_id}`):
1. **Guards**: assignment exists + not template; its FSO state in
   (confirmed, assigned); user in ops groups (else refused); same
   facility when `new_staff_id` differs (else refused);
   duration preserved: end−start must equal the FSO's
   scheduled_duration (the JS sends the dragged block's bounds —
   recompute end server-side from duration and IGNORE the client end,
   so a resize can never smuggle a duration change).
2. **Validate**: `validate_drop(new_staff_id or current staff,
   start_iso, computed_end_iso, assignment_id)` — `hard_block` →
   refused with its message; `ok` with warnings (overlap/travel text)
   and NOT `confirmed` → `needs_confirm` carrying the message (the JS
   re-calls with confirmed=True after the dialog).
3. **Apply** (savepoint):
   a. matrix release for the FSO (§1 inverse, no-op when absent);
   b. staff change first if any: swap THAT assignment's staff_id
      (role preserved) — the other siblings keep their staff;
   c. `fso.write({'scheduled_datetime': start_utc})` — sibling
      resync + staff push + chatter all fire from the shipped write
      path;
   d. matrix re-book via `book_staff_slot` for the (new) lead staff
      (best-effort try/except, routes precedent);
   e. `_send_rescheduled_zns(fso)` — patient's own phone,
      mobile-then-phone, rails-gated, try/except.
4. Return ok + the fso display info for the toast.

### 2.2 JS (`static/src/js/schedule_drag.esm.js`)

Subclass/patch ONLY the staff-schedule view's controller: replace the
assignment-move path (`_onMove`) with: freeze the item (optimistic UI
off — simplest correct v1: immediately snap back visually, then
reload on success), call `reschedule_from_drag`; `needs_confirm` →
the existing ConfirmationDialog pattern (staff_schedule_timeline
precedent) → re-call confirmed; `refused` → danger toast with the
server message; `ok` → success toast + model reload (the resync moves
all sibling blocks correctly — never trust the local item write).
Keep the unassigned-rail drop path untouched. vi-first strings with
en gloss.

### 2.3 Views/config

No new views. Settings block (self_booking pattern) with
`zns_template_rescheduled` only. i18n/vi.po.

## 3. Tests (`tests/test_schedule_drag.py`)

1. State matrix: draft/in_progress/completed/cancelled → refused;
   confirmed + assigned → proceeds.
2. Ops guard: plain nurse (even the assignment's own staff) →
   refused; ops manager → ok (server-side, real users).
3. **Sibling coherence**: 2-staff FSO, drag one block +2h → BOTH
   assignments' planned times AND fso.scheduled_datetime move; roles
   and the other staff unchanged.
4. Duration immunity: client end_iso ≠ start+duration → server uses
   duration; scheduled_duration unchanged after the move.
5. hard_block (outside working hours / on leave) → refused, nothing
   written (assert scheduled_datetime unchanged).
6. needs_confirm on overlap: first call returns needs_confirm +
   message; confirmed=True call applies. Travel warning text present
   when health_routes seeds an infeasible neighbor (reuse its test
   fixtures if importable, else skipTest).
7. Staff-lane change: assignment.staff_id swapped, siblings keep
   theirs; cross-facility target → refused.
8. Matrix: pre-booked slot rows for the fso released + new slot
   booked (and the zero-matrix-rows case no-ops).
9. Rails matrix: dry_run → simulated row with dedup
   `resched-<fso>-<newdt>`; empty template → zero rows; second
   reschedule to a DIFFERENT time → second row; re-fire same move →
   one row.
10. Timezone: 02:00 UTC target renders 09:00 in the ZNS params
    (booking_timezone pytz).
11. Chatter: the FSO has a tracking message after the move (the
    shipped write path — cheap regression pin).

## 4. Deploy & verify

- `-i health_schedule_drag --test-tags /health_schedule_drag,
  /health_fieldservice_timeline_smoke-if-any,/health_routes` (routes
  inherits validate_drop — prove no regression; skip the middle tag
  if none exists). Port-wait loop; logfile results; YOUR timestamp.
- **Browser QA on the live schedule (action 1536) REQUIRED with
  committed evidence** (screenshots or exact-description doc):
  drag→confirm dialog→block moves + sibling moves; a refused drag
  snapping back with the toast; the chatter entry. Note: ormcache/
  worker staleness gotchas from the daystrip QA (ledger §5.17 notes)
  — restart workers after ACL/test-user fiddling.
- Live demo under dry_run: reschedule a demo FSO (clients 861-864),
  show the simulated `booking_rescheduled` row + the staff push
  notification record + both assignments moved. Leave
  `health_messaging.enabled=False`/`dry_run=True`; state final
  positions.
- vi.po, conventions §8, commit+push on 19.0.

## 5. Report-back extras

(a) the exact onMove interception mechanism you found (callback
revert vs manual reload) + the view-registration seam; (b) the matrix
release implementation you chose (reset vs unlink) and why; (c) demo
ids + the confirm-dialog and refusal texts; (d) final switch
positions; (e) whether the nurse-PWA surface showed the new time via
normal sync (observe, don't build); (f) any new ledger-grade gotcha
(explicitly flagged).
