# Phase handover — Offline visit actions (health_pwa, PWA 1.13.0)

Read `docs/strategy/HANDOVER-CONVENTIONS.md` FIRST (deploy §2, PWA version
discipline §3, sanctioned edits §4, gotcha ledger §5 — §5.1, §5.24, §5.32 and
§5.33 bite directly in this phase).

## §0 Scope

A field nurse on rural 3G currently cannot do ANYTHING to a visit while
offline: the Start button and clinical-notes save are straight `fetch`es that
fail into an error toast. Meanwhile the push pipeline the pwa-sync-delta
phase just scoped and repaired (`/health_pwa/sync/push`) still has ZERO
producers, and health_evv already ships the exact offline pattern we need
(client queue + `client_event_uuid` idempotent replay). This phase makes the
two highest-value visit actions work offline:

1. **Offline visit START** — tapping Start while offline queues an action
   (with a client UUID + the device's claimed timestamp), optimistically
   marks the booking in-progress locally, and replays idempotently at the
   next sync. The server re-validates the state guard at replay and honors
   the CLAIMED start time (clamped) so timecards/EVV stay honest.
2. **Offline CLINICAL NOTES** — saving the notes form offline queues the
   note payload and replays it as a `health.clinical.note` create.
3. **Action replay infrastructure**: an additive `actions` key in the
   existing push envelope + a `health.pwa.action.receipt` model cloning the
   health_evv idempotency seam (unique index + search-first replay), G1
   assignment required, per-item results.
4. **Ref-based push acknowledgement**: every queued doc gets a `client_ref`
   echoed back per result item so the client clears exactly what succeeded
   (the current index-based mapping misaligns when models interleave —
   verified fact 12).
5. PWA **1.13.0** per conventions §3.

**Non-goals (binding):**
- **NO offline COMPLETE.** Completion requires `clinical_notes_submitted` +
  `invoice_submitted` (raises UserError otherwise, fact 4) and drives the
  invoice/payment money tail — it stays online-only. Do not add it.
- NO offline image upload (notes photos stay online-only; the queued note
  carries text fields only).
- NO new EVV event types and NO wiring of EVV checkin/checkout to
  start/complete — travel events already queue offline via health_evv's own
  queue (fact 7); leave that pipeline alone.
- NO changes to `/health_pwa/sync/changes` (the pull) beyond nothing — the
  delta/scope work is done and reviewed.
- NO changes to the existing field-write push whitelists or their scope
  checks.
- NO conflict-resolution UI. A rejected action (state conflict) surfaces as
  a toast + detail refetch, nothing more.
- Existing response envelope shapes are binding; new keys are additive only.

## §1 Verified facts — do NOT re-derive

1. **Start flow today**: modal Start → `POST /health_pwa/api/fso/<id>/start`
   (`health_pwa/controllers/api.py:709-738`; state guard `assigned` or
   `confirmed` at :721) → model `action_start_service()`
   (`health_fieldservice/models/health_fieldservice_order.py:2522-2567`):
   writes `state='in_progress'` + `actual_start_datetime=now()` (:2547-2548)
   and resolves the 'In Progress' stage (:2527-2541). Offline: fetch throws →
   error toast, nothing queued.
2. **Clinical notes today**: `POST /health_pwa/api/fso/<id>/clinical_notes`
   (api.py:986-1028) creates a `health.clinical.note` from a text-field
   payload (clinical_notes, diagnosis, treatment_performed,
   medications_prescribed, vital_signs, patient_condition_before/after,
   injection_count, medication_count, wound_count, iv_fluid_count — create at
   :1002-1018) and returns `{note_id, clinical_notes_submitted,
   clinical_note_count, message}`. Images ride a SEPARATE multipart endpoint
   (:1081-1119) — online-only, out of scope.
3. **FSO state machine**: Selection at
   health_fieldservice_order.py:45-55 (`draft, confirmed, assigned,
   in_progress, completed, completed_pending_invoice, cancelled, closed`).
   START requires state ∈ {assigned, confirmed} (api.py:721).
4. **Why complete is online-only**: `action_complete_service`
   (health_fieldservice_order.py:2750-2836) raises UserError unless
   `clinical_notes_submitted` AND `invoice_submitted` (:2754-2768), and the
   PWA complete endpoint (api.py:818-935) runs the invoice/payment tail.
5. **The idempotency seam to CLONE — health_evv**:
   `health_evv/models/health_evv_event.py` — unique index materialized in
   `init()` (:128-139, §5.1: `CREATE UNIQUE INDEX IF NOT EXISTS` on
   `(fso_id, client_event_uuid)`); `append_event()` (:256-331): search-first
   by uuid → return existing; else `SELECT … FOR UPDATE` on the FSO row,
   re-search, create. Multiple replays of one uuid return one record.
   Second precedent: health_consent `client_mutation_id` partial unique
   index (`WHERE client_mutation_id IS NOT NULL AND != ''`).
6. **Scope helper to reuse**: `_employee_assigned_to(order)` already lives
   in `health_pwa/controllers/sync.py:68-84` (sudo employee-by-user_id §5.24
   + non-cancelled assignment). The push route is sync.py:617-660
   (type='jsonrpc', params via kwargs); `_process_fso_updates` :662,
   `_process_patient_updates` :735 — clone their per-item result shape
   (`{type, id, success, updated_fields|error}`).
7. **EVV travel events already queue offline** via
   `window.healthEvvQueue.enqueue()`
   (health_pwa_daystrip/static/src/js/daystrip.js:186-221), flushed on
   online/visibilitychange. GPS capture precedent:
   `navigator.geolocation.getCurrentPosition` wrapper at daystrip.js:161-180
   (5s timeout, may resolve null). Do not touch; cited as prior art only.
8. **Client queue mechanics** (health_pwa/static/src/js/utils/sync-manager.js):
   `queueChange` :406 (doc `_id = 'pending_<model>_<id>_<Date.now()>'`,
   fields model/recordId/operation/data/timestamp/retryCount);
   `getPendingChanges` :352 (allDocs prefix scan `pending_`→`pending_￰`
   — KEY order, not guaranteed time order); `groupChangesByModel` :374;
   `clearPushedChanges` :391 (**index-based**: `results[i]` ↔ `changes[i]`).
   `pushPendingChanges` :140-183 now sends the JSON-RPC params envelope and
   reads `rpc.result` (fixed in 6f110029).
9. **Push runs BEFORE pull** in both `performSync` and `performFullSync`
   (step 1 vs step 2) — queued actions replay before the delta lands, so the
   pulled state already reflects them. Both paths `await this.migrationDone`
   first (the scope-purge gate) — new code must not bypass those methods.
10. **Offline detection**: `window.healthPWA.isOnline` (app.js:150),
    online/offline listeners app.js:216-227,
    `state.isOnline` reaches today-view as the `is-online` prop. The SW
    never caches POSTs (pwa_templates.xml fetch handler).
11. **§5.32 applies to the tests**: `action_start_service` fires
    health_workflow_auto's `_attendance_open` timecard hook (E.4), gated by
    `health_workflow_auto.timecard_sync_enabled` (code-default True; False
    on vietuat). An HttpCase that STARTS a visit MUST pin that param off in
    setUp via `addCleanup` (clone `TestOneTapEndpointScope.setUp`,
    health_workflow_auto/tests/test_workflow_auto.py) or it poisons
    `TestTimecardSync` later in the same run.
12. **Index-mapping latent bug**: server results are flattened
    fso-then-patients while the client's flat pending list is in allDocs KEY
    order — with mixed models the index mapping misaligns. Dormant today
    (no producers); this phase fixes it with `client_ref` (see §2.4) BEFORE
    the first real producers land.
13. **Version now**: PWA 1.12.1 in 5 spots in
    `health_pwa/views/pwa_templates.xml`, manifest `19.0.1.0.28`. This phase
    → **1.13.0** / `19.0.1.0.29` + the three co-resident pin suites
    (daystrip / scribe / pwa_family) in the same change.
14. **vietuat safety params** (untouched): `health_family_messages.enabled`
    False, `health_messaging.enabled` False, `health_messaging.dry_run`
    True, ZNS params `''`. No pip installs on the server.

## §2 Architecture

### Sanctioned edits (exhaustive — conventions §4)

- `health_pwa/controllers/sync.py` — the `actions` processing (§2.2-§2.3)
  + `client_ref` echo in the existing per-item results (§2.4). Nothing else
  in the pull path.
- `health_pwa/models/pwa_action_receipt.py` (NEW) + one import line in
  `models/__init__.py`.
- `health_pwa/security/ir.model.access.csv` — one line for the receipt
  model (base.group_system only; controller reads/writes run sudo).
- `health_pwa/static/src/js/utils/sync-manager.js` — `queueAction()` +
  action grouping + ref-based `clearPushedChanges` (§2.4-§2.5).
- `health_pwa/static/src/js/app.js` — ONLY: (a) the modal Start handler's
  offline branch, (b) the clinical-notes save handler's offline branch,
  (c) a small "Chờ đồng bộ / Pending sync" pending-state indicator on the
  affected booking card/modal, (d) new entries in
  `APP_VI_FALLBACK_TRANSLATIONS`. No other app.js changes — the shared
  modal, bridge, one-tap, and status-label code are all READ-ONLY.
- `health_pwa/views/pwa_templates.xml` + `__manifest__.py` — version bump
  ONLY.
- `health_pwa/tests/test_offline_actions.py` (NEW) + `tests/__init__.py`
  import line.
- Pin tests in health_pwa_daystrip / health_scribe / health_pwa_family
  (1.12.1 → 1.13.0) — nothing else in those modules.
- **Everything else read-only** — explicitly including
  `health_pwa/controllers/api.py` (duplicate the note-create body per the
  A4 duplication convention, naming source lines, rather than editing
  api.py), health_fieldservice, health_evv, health_pwa_daystrip JS.

### §2.1 The receipt model (clone of the EVV seam — fact 5)

`health.pwa.action.receipt` in `health_pwa/models/pwa_action_receipt.py`:
- `fso_id` (Many2one health.fieldservice.order, required, index,
  ondelete='cascade'), `action_type` (Char, required — 'start_service' |
  'save_clinical_notes'), `client_action_uuid` (Char(64), required),
  `claimed_at` (Datetime), `staff_id` (Many2one hr.employee),
  `state` (Selection applied/rejected), `reject_reason` (Char),
  `result_json` (Text — the exact per-item result payload returned).
- Unique index in `def init(self)` (§5.1):
  `CREATE UNIQUE INDEX IF NOT EXISTS health_pwa_action_receipt_uniq ON
  health_pwa_action_receipt (fso_id, action_type, client_action_uuid)`.
- `@api.autovacuum` GC of receipts older than 90 days (clone the tombstone
  model's `_gc_tombstones`, same file pattern).

### §2.2 Server replay (`sync_push_changes`)

Additive envelope key: `changes.actions = [{action_type, fso_id,
client_action_uuid, client_ref, claimed_at, payload{}}]`. Process the
actions list FIRST (before field_service_orders/patients), in the order
received, each item isolated in its own `with request.env.cr.savepoint()`
so one bad action cannot poison the batch. Per item:

1. Validate `action_type` ∈ the two known types; `client_action_uuid`
   non-empty ≤64 chars — else per-item error (existing shape, fact 6).
2. Resolve order sudo; `.exists()` else 'Order not found'.
3. **G1 required**: `_employee_assigned_to(order)` — on failure return the
   per-item 'Access denied' error and do NOT create a receipt (an
   unauthorized caller must not be able to squat a uuid).
4. **Idempotent replay** (clone fact 5's append_event shape): sudo search
   receipt by (fso_id, action_type, client_action_uuid) → if found, return
   `json.loads(result_json)` as the item result (success and rejected
   replays are BOTH replayed verbatim — a rejected action stays rejected).
   Else `SELECT id FROM health_fieldservice_order WHERE id=%s FOR UPDATE`,
   re-search, then apply.
5. Apply `start_service`: guard `order.state in ('assigned','confirmed')` —
   on failure record a REJECTED receipt (reject_reason='state_conflict')
   and return the per-item error `{…, success: False, error:
   'state_conflict', state: order.state}`. On pass:
   `order.sudo().action_start_service()`, then clamp-and-write the claimed
   time: parse `claimed_at` with the `_parse_since`-style hardened parser;
   if it parses AND `now - 48h <= claimed_at <= now + 5min` write
   `actual_start_datetime = claimed_at`, else keep the server time and note
   `'claimed_at_clamped'` in the receipt's result_json. Record APPLIED
   receipt; item result `{type:'action', action_type, id: fso_id,
   client_ref, success: True, state: 'in_progress'}`.
6. Apply `save_clinical_notes`: no state guard beyond order existence + G1
   (mirrors the online endpoint). Whitelist the payload to EXACTLY the
   field set of fact 2 (ignore unknown keys silently), duplicate the
   `health.clinical.note` create body from api.py:1002-1018 (A4 convention
   — name the source lines in a comment), sudo. Record APPLIED receipt;
   result includes `note_id`.
7. Every action item result carries `client_ref` echoed verbatim (§2.4).

The existing statistics keys count action items too (they are appended to
the same `results` list) — shapes unchanged.

### §2.3 What replay must NOT do

No invoice creation, no payment transactions, no EVV events, no state
transitions other than assigned/confirmed → in_progress, no writes outside
`action_start_service`'s own writes + the clamped `actual_start_datetime` +
the clinical-note create. The timecard hook firing inside
`action_start_service` is expected and correct (it is the same code path as
the online button; on vietuat the switch is off anyway).

### §2.4 Ref-based acknowledgement (fixes fact 12 before producers exist)

- Client: every queued doc (existing `queueChange` docs AND new action docs)
  gains `clientRef: doc._id`. `groupChangesByModel` passes `client_ref`
  through on each item (additive key — the server ignores unknown keys on
  field-write items today).
- Server: `_process_fso_updates` / `_process_patient_updates` / the action
  processor echo `client_ref` in each per-item result when the incoming
  item carried one (additive response key).
- Client `clearPushedChanges`: build a map `client_ref → result`; clear a
  pending doc iff its result has `success: True` OR the result is a
  **rejected action replay** (`error: 'state_conflict'` / 'Access denied' —
  the receipt makes retrying pointless; surface a toast + refetch instead).
  Keep the index-based path as fallback ONLY when no result in the batch
  has a `client_ref` (old-server compatibility).

### §2.5 Client producers (app.js modal + sync-manager.js)

- `queueAction(actionType, fsoId, payload)` in sync-manager.js: doc
  `_id = 'pending_action_<Date.now()>_<uuid>'` with
  `{model: 'health.pwa.action', actionType, recordId: fsoId,
  clientActionUuid: crypto.randomUUID(), clientRef: _id,
  claimedAt: new Date().toISOString(), data: payload, timestamp, retryCount:0}`.
  `getPendingChanges` sorts the combined list by `timestamp` ascending
  before grouping (fact 8 — allDocs key order is not time order).
- Modal Start handler (app.js): when `!navigator.onLine` (use the same
  source the modal already reads — the `is-online` prop / `state.isOnline`):
  `queueAction('start_service', id, {})`, optimistically set the modal's
  existing started-state (`serviceStartedForBooking`) and patch the local
  PouchDB orders doc (`state:'in_progress', pendingSync:true` — reuse the
  update pattern in sync-manager's `updateLocalData`), toast
  `_t('Saved offline — will sync when online')`. Online path unchanged.
- Clinical-notes save handler: when offline, `queueAction(
  'save_clinical_notes', id, {<the fact-2 text fields from the form>})`,
  keep the notes text in the form state, show the pending badge + the same
  toast. Online path unchanged.
- Pending indicator: a small badge (`Chờ đồng bộ` / `Pending sync`) on the
  booking card + modal header while a queued action for that fso exists;
  cleared when the queue drains (listen after `performSync` resolves — the
  today list already reloads post-sync). Mono colors, hf-wt-ico/CSS only —
  no emoji, no gradients.
- On a `state_conflict`/'Access denied' ack: toast
  `_t('Could not sync offline action — refreshed')` + `fetchBookingDetail`.
- All four new user-visible strings go into `APP_VI_FALLBACK_TRANSLATIONS`
  (VN-first, clone the one-tap entries at app.js:3-12).

## §3 Tests (health_pwa/tests/test_offline_actions.py — HttpCase; §5.32 PIN
`health_workflow_auto.timecard_sync_enabled` OFF in setUp via addCleanup,
fact 11; fixtures per conventions §6, clone test_sync_scope.py's base)

1. **Replay start**: push an action for the assigned minimal nurse
   (no sale/account ACLs) on an `assigned` order with
   `claimed_at = now - 10min` → 200, item success, order `in_progress`,
   `actual_start_datetime` == claimed_at (to the second), APPLIED receipt
   row exists.
2. **Idempotency**: push the SAME uuid again → item success, identical
   result payload, `actual_start_datetime` unchanged, still exactly ONE
   receipt row.
3. **State conflict**: second uuid on the now-in_progress order →
   `success: False, error: 'state_conflict'`, state unchanged, REJECTED
   receipt; replaying that same rejected uuid returns the same rejection.
4. **Scope**: an unassigned internal nurse pushes an action on the order →
   per-item 'Access denied', NO receipt row created, state unchanged.
5. **Clamp**: `claimed_at` 3 days in the past (and a second case: garbage)
   → visit starts, `actual_start_datetime` is the SERVER time (not the
   claim), receipt notes the clamp.
6. **Notes replay**: queued notes action creates the `health.clinical.note`
   with exactly the whitelisted fields; an unknown key in the payload is
   ignored (not an error, not written).
7. **client_ref echo**: every result item for items sent with `client_ref`
   carries it back verbatim; a mixed batch (one action + one field-write +
   one patient-write) returns refs that map each result to its item
   regardless of order.
8. **Batch isolation**: a batch [bad action (state_conflict), good notes
   action] → the good one still applies.
Plus the three pin suites bumped to 1.13.0 in the same change.

### Browser QA (chrome-devtools MCP on care.biztinct.com — MANDATORY;
hard-reload with ignoreCache, §5.32 second corollary)

9. Shell serves v1.13.0, console clean.
10. DevTools offline → open an assigned QA booking → tap Start → offline
    toast + pending badge + modal shows started state; Network tab shows NO
    failed POST spam.
11. Back online → sync runs → server state `in_progress` (verify via psql
    or the backend form), badge cleared, receipt row on the server; delta
    pull reflects the state without a full reload.
12. Offline notes save → online → `health.clinical.note` exists with the
    text; note count in the modal updates after sync.
13. Revert ALL QA state afterwards (order back to `assigned`,
    `actual_start_datetime` cleared, QA note + receipts deleted, QA
    attendance rows checked — report counts).

## §4 Deploy (conventions §2 verbatim; HttpCase ⇒ NO --no-http)

scp → /tmp/fixdeploy → sudo cp + chown odoo for: health_pwa,
health_pwa_daystrip, health_scribe, health_pwa_family. Then stop server +
port-wait and:

```
sudo -u odoo /odoo/odoo-server/odoo-bin -c /etc/odoo-server.conf -d vietuat \
  -u health_pwa,health_pwa_family,health_pwa_daystrip,health_scribe \
  --test-enable \
  --test-tags /health_pwa,/health_pwa_family,/health_pwa_daystrip,/health_scribe \
  --stop-after-init --workers 0
```

NOTE: odoo logs to `/var/log/odoo/odoo-server.log` (stdout only carries
docutils noise; the log contains binary junk — use
`sudo grep -a 'odoo.tests.result' … | tail -1` and match YOUR timestamp).
Then restart, `/web/login` → 200, quote the result line verbatim.

## §5 Report back

(a) File list + diffstat. (b) Verbatim test-result line. (c) The receipt
table row counts after your QA (and that QA data was reverted, item 13).
(d) Exactly which app.js lines changed (the sanction is narrow — prove it).
(e) Browser-QA evidence for items 10-12 (what you saw, network panel
notes). (f) Deviations + reasons. (g) Any new gotcha, flagged for §5.
(h) Confirm fact-14 params untouched.

---

**Kickoff line** (prepend to `docs/strategy/KICKOFF-TEMPLATE.md` prompt):
`Implement the phase specified in docs/strategy/handovers/pwa-offline-actions-phase.md.`
Phase-specific guard: health_pwa edits are in scope ONLY as listed in §2
"Sanctioned edits"; `controllers/api.py` is READ-ONLY (duplicate per A4,
never edit); offline COMPLETE and EVV wiring are explicitly out of scope;
existing envelope shapes are binding, new keys additive only.
