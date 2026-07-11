# Phase handover — PWA sync delta + scope (health_pwa, PWA 1.12.0)

Read `docs/strategy/HANDOVER-CONVENTIONS.md` FIRST (deploy workflow §2, PWA
version discipline §3, sanctioned-edits rule §4, gotcha ledger §5 — §5.24,
§5.27 and §5.32 bite directly in this phase).

## §0 Scope

The pwa-reliability phase fixed the CLIENT half of incremental sync (the
PouchDB `_rev` 409; the client now persists `lastSyncTime` and sends
`?since=`). The SERVER half was explicitly deferred: `/health_pwa/sync/changes`
ignores `since` (hard-coded 30-day window, "TEMPORARY DEBUG"), team scoping is
commented out, and the patient pull is entirely unscoped. This phase finishes
the job:

1. **Re-enable `since`** on `/health_pwa/sync/changes` — robust parse of the
   client's JS ISO timestamps, fallback to the 30-day window on absence/garbage
   or `force_full`.
2. **Explicit sync scope** (the §2.3 pattern: explicit grant check, THEN sudo
   reads). Today the FSO pull leans on record rules — too NARROW for a minimal
   nurse (the nurse rule is catchment-gated, so a nurse without
   `catchment_province_id` syncs ZERO orders) and the patient pull has no
   scoping at all (ANY internal user's device caches EVERY patient's
   `allergies` + `medical_history`). After this phase: orders by explicit
   grants G1–G4 (below), patients only for in-scope orders, all payload reads
   sudo so minimal nurses actually get their own visits offline.
3. **Removals**: changed-but-out-of-scope, archived, and hard-deleted orders
   are emitted as `{id, is_deleted: true}` records — the client ALREADY
   honors this flag (verified fact 7), so removals need no client protocol
   change. Hard deletes get a tiny tombstone model + `unlink` hook.
4. **Push scope**: `/health_pwa/sync/push` currently browses with the caller
   env and lets any internal user write `stage_id` on any record-rule-writable
   order — and the client push queue has ZERO producers repo-wide (verified
   fact 10), so this is pure dead attack surface. Require assignment (G1),
   sudo the whitelisted writes, and DROP `stage_id` from the whitelist.
5. **Client**: server-authoritative sync watermark (device clocks drift), a
   one-time scope-purge cache migration (existing devices hold the unscoped
   patient cache — that purge is the actual privacy remediation in the field),
   keep the 500-cap warning.
6. **Gate `/health_pwa/sync/debug`** to `base.group_system`.
7. PWA **1.12.0** per conventions §3.

**Non-goals (binding):**
- NO UI changes of any kind; no app.js edits except none are sanctioned.
- NO change to existing response envelope shapes — new keys are additive only
  (`watermark`), existing keys keep their meaning.
- NO record-rule or ACL changes in health_fieldservice/health_base.
- NO patient tombstones / patient removals in v1 (the one-time purge +
  scoped re-pull covers legacy caches; natural staleness accepted).
- NO pagination framework; the 500 cap stays (with scoping a nurse's delta is
  tiny; keep the client console warning).
- Do NOT delete the push endpoint (future offline-writes ride it) — scope it.
- Do NOT move `TestFsoDetailScope` out of health_pwa_family; it stays where
  it is.
- Deprecated-API cleanup (`check_access_rights` in `_check_sync_access`)
  stays out of scope.

## §1 Verified facts — do NOT re-derive

1. **The stub**: `health_pwa/controllers/sync.py:113-114` hard-codes
   `last_sync = now - 30d` ("TEMPORARY DEBUG"); the real `since` parsing is
   commented at :120-133 (it handled the JS `Z` suffix, `T`, millis — reuse
   that logic, hardened). `force_full` kwarg read at :111.
2. **Team scoping**: user teams found at sync.py:136-138 via
   `health.fieldservice.team.search([('member_ids','in',[user.id])])` —
   `member_ids` are USERS. The FSO team filter is commented out at :261-266.
3. **FSO pull** (sync.py:268) searches with the CALLER env → record rules
   apply. The nurse rule
   (`health_fieldservice/security/health_fieldservice_security.xml:24-40`)
   requires `user.catchment_province_id` to be set AND grants
   assignment/primary-doctor/primary-nurse orders; ops-manager rule (:43-53)
   = own catchment; owner rule (:54-64) = everything. A minimal nurse without
   catchment therefore syncs ZERO orders today (same failure class §2.3 of
   the pwa-reliability phase fixed for the detail endpoint).
4. **Patient pull** (sync.py:199) searches `res.partner` with the caller env
   and there are NO health record rules on res.partner → every internal user
   pulls every patient, payload includes `allergies`, `medical_history`,
   phones, addresses (sync.py:204-231). This is the PHI hole this phase
   closes.
5. **Envelope**: `_prepare_sync_response` (sync.py:27-50) MERGES the data
   dict into the top-level response (no nested `data` key) — additive keys
   are safe; `success`/`timestamp`/`server_time` are reserved.
6. **Scope-check precedent to CLONE**:
   `health_workflow_auto/controllers/onetap_api.py:53-74`
   `_employee_assigned_to` — employee via **sudo `user_id` search** (§5.24),
   then sudo `health.staff.assignment` search on
   `fso_id` / `staff_id` / `state != 'cancelled'`.
7. **Client already handles removals**:
   `health_pwa/static/src/js/utils/sync-manager.js:239-248` — a record with
   `is_deleted: true` is removed from the local PouchDB. The `is_deleted`
   field already exists (always `False`) in every pull payload.
8. **Client watermark bug**: sync-manager.js:75 and :110 set
   `lastSyncTime = new Date().toISOString()` — the DEVICE clock. A fast
   device clock makes the next `since` skip real changes. The pull response
   is parsed at :180-191; `data.watermark` should win when present.
9. **PouchDB handles**: created once at `app.js:185-190` into a shared
   `databases` object (`patients`, `orders`, `teams`, `serviceTypes`,
   `facilities`, `sync`); sync-manager holds the SAME object as `this.db`.
   For the purge migration, bulk-delete docs (allDocs → remove) — do NOT
   `db.destroy()`, it invalidates the shared handles.
10. **Push pipeline is producer-less**: `queueChange` /
    `updateFieldServiceOrder` / `updatePatient` have zero callers repo-wide
    (only their definitions in sync-manager.js). The server side
    (sync.py:429-528) browses with caller env at :484 and whitelists
    `stage_id` at :495-502.
11. **FSO `active` field exists**
    (`health_fieldservice/models/health_fieldservice_order.py:107`) and
    §5.27 applies: a default `search()` SKIPS archived rows — the changed-set
    query MUST run `with_context(active_test=False)` or archived orders
    silently vanish from the delta instead of emitting removals.
12. **health_pwa module shape**: `models/` exists (`pwa_config.py` is the
    pattern for new model files); there is NO `tests/` directory yet (that is
    why `TestFsoDetailScope` lives in health_pwa_family). This phase CREATES
    `health_pwa/tests/`.
13. **PWA version now**: 1.11.1 in 5 spots in
    `health_pwa/views/pwa_templates.xml`, manifest `19.0.1.0.26` (post-review
    fix f-commit of the reliability phase). This phase
    → **1.12.0** / `19.0.1.0.27` + the three co-resident pin suites
    (health_pwa_daystrip, health_scribe, health_pwa_family) in the SAME
    change.
14. **vietuat params** (leave untouched): `health_family_messages.enabled` =
    False, `health_messaging.enabled` = False, `health_messaging.dry_run` =
    True, ZNS template params `''`. No pip installs on the server.

## §2 Architecture

### Sanctioned edits (exhaustive — conventions §4)

- `health_pwa/controllers/sync.py` — everything described below.
- `health_pwa/models/pwa_sync_tombstone.py` (NEW) + `models/__init__.py`
  (one import line).
- `health_pwa/security/ir.model.access.csv` — one line for the tombstone
  model (system-only CRUD; controllers read it sudo).
- `health_pwa/static/src/js/utils/sync-manager.js` — watermark + purge
  migration + (keep) cap warning.
- `health_pwa/views/pwa_templates.xml` + `health_pwa/__manifest__.py` —
  version bump ONLY.
- `health_pwa/tests/` (NEW directory) — `__init__.py` + `test_sync_scope.py`.
- Pin tests: the version-pin assertion files in health_pwa_daystrip,
  health_scribe, health_pwa_family (1.11.1 → 1.12.0) — nothing else in
  those modules.
- **Everything else is read-only** — explicitly including `app.js`,
  `health_pwa/controllers/api.py`, and all of health_fieldservice.

### §2.1 Scope grants (server, computed sudo — the heart of the phase)

One helper on the controller, `_sync_scope()`, computed ONCE per request:

- `employee`: sudo `hr.employee` search by `user_id` (fact 6 / §5.24).
- **G1 assignment**: orders with a non-cancelled `health.staff.assignment`
  for `employee`.
- **G2 team**: `order.team_id` in the caller's member teams (fact 2).
- **G3 catchment (managers)**: only if the user is in
  `health_base.group_healthcare_operations_manager` → orders with
  `catchment_province_id == user.catchment_province_id` (and it is set);
  if in `health_base.group_healthcare_owner` → all orders. Mirrors the
  existing record rules (fact 3) so no manager/owner loses audience.
- **G4 primary**: `primary_doctor_id.user_id` or `primary_nurse_id.user_id`
  == caller (mirrors the nurse rule's other branches so no one is narrowed).

Two derived sets:
- `in_scope(orders)` — batch partition of a changed-order recordset against
  G1–G4 (ONE assignment search with `('fso_id','in',ids)`, set logic in
  Python; no per-record queries).
- `scope_horizon_ids` — sudo search of orders matching G1–G4 with
  `scheduled_datetime >= now - 90d`, used only to derive the patient scope.
  `patient_scope_ids = set(horizon_orders.mapped('patient_id').ids)`.

### §2.2 The delta pull (`sync_get_changes` rewrite, envelope-compatible)

1. Capture `watermark = fields.Datetime.now()` FIRST (before any query).
2. Parse `since` (fact 1's commented logic, hardened: strip `Z`, `T`,
   millis; any parse failure → 30-day fallback; `force_full` → 30-day
   fallback). Never 500 on a bad `since`.
3. Changed-order query: sudo + `with_context(active_test=False)` (fact 11),
   domain `write_date >= since OR create_date >= since`, order
   `write_date desc`, limit 2000 (raw candidates).
4. Partition: `active AND in_scope` → upsert records (cap 500, keep the
   existing per-record dict shape from sync.py:273-308 EXACTLY — sudo reads);
   `NOT active OR NOT in_scope` → removal `{'id': id, 'is_deleted': True}`
   appended to the same `records` list (ids only, no other data — never leak
   fields of out-of-scope orders).
5. Tombstones (§2.3): append `{'id': res_id, 'is_deleted': True}` for
   tombstones with `stamp >= since` (on the 30-day fallback window, use
   `stamp >= now - 30d` — idempotent, harmless).
6. Patients: `changed_patients` = sudo res.partner search
   (`is_patient` + write/create since) FILTERED to `patient_scope_ids`,
   UNION the patients of the in-scope changed orders from step 4 (a newly
   assigned order must bring its patient even if the partner row is
   untouched). Same per-record dict shape (sync.py:204-231), sudo reads.
7. Teams / service types / facilities: unchanged logic, but run the reads
   sudo after the same `since` (they are reference data; teams are already
   member-scoped at sync.py:325-326).
8. Response: existing keys unchanged (`changes`, `total_changes`,
   `last_sync`, `current_time`, `debug_info`) + NEW top-level
   `watermark` (ISO string of step 1). Drop nothing.
9. Keep the two `_logger.info` summary lines (they were load-bearing for
   diagnosing this in production); remove the leftover `import logging`
   inside functions — module-level logger.

### §2.3 Tombstones (hard deletes only)

New model `health.pwa.sync.tombstone` in
`health_pwa/models/pwa_sync_tombstone.py`:
`res_model` (char, required), `res_id` (integer, required, indexed),
`stamp` (datetime, default now, indexed). Plus a thin
`_inherit = 'health.fieldservice.order'` class in the SAME file overriding
`unlink()`: before `super()`, `sudo()` a `create_multi` of tombstones for
`self.ids` with `res_model='health.fieldservice.order'`. Add an
`@api.autovacuum` method on the tombstone model deleting rows older than
90 days. ACL: one `ir.model.access.csv` line, `base.group_system` only
(controller reads run sudo). NOTE §5.30: cascades bypass unlink() — an FSO
deleted via a parent cascade would skip the hook; acceptable v1 (FSOs are
not cascade children of anything routinely deleted), state this in your
report if you find otherwise.

### §2.4 Push scope (`sync_push_changes` + `_process_fso_updates` +
`_process_patient_updates`)

- FSO items: resolve the order sudo, require G1 assignment (clone fact 6's
  helper verbatim), on failure append the EXISTING per-item error shape
  (`success: False`, error 'Access denied') — the envelope and statistics
  keys stay identical. On success write the whitelist SUDO. Whitelist loses
  `stage_id` (fact 10 — no producer, pure attack surface); keep
  patient_notes / completion_notes / duration_actual / service_lat /
  service_lng.
- Patient items: require `patient.id in patient_scope_ids`, then sudo write
  of the existing 3-field whitelist (phone / mobile / next_visit_date).

### §2.5 Debug + status endpoints

- `/health_pwa/sync/debug`: after `_check_sync_access()`, additionally
  require `request.env.user.has_group('base.group_system')` → else the
  standard 403 envelope.
- `/health_pwa/sync/status`: replace the hard-coded `'pwa_version': '1.0.96'`
  (sync.py:622) with the installed health_pwa version read sudo from
  `ir.module.module` — one line, shape unchanged.

### §2.6 Client (sync-manager.js ONLY)

- Watermark: in `performSync`/`performFullSync` step 3, prefer the pull
  response's `watermark` over `new Date().toISOString()`. Plumb it by having
  `pullServerChanges` return the parsed response body (it currently returns
  nothing) — a fallback to the device clock stays for old servers.
- One-time scope purge: in the constructor after `loadSyncMetadata()`, check
  `localStorage.getItem('health_pwa_scope_v')`; if not `'2'`: bulk-delete
  ALL docs in `this.db.orders` and `this.db.patients` (allDocs →
  remove loop — do NOT destroy(), fact 9), set `lastSyncTime = null`, save
  metadata, set the flag to `'2'`. Wrap in try/catch; on failure log and do
  NOT set the flag (retry next load). This is what actually removes the
  unscoped patient cache from devices in the field.
- Keep the 500-cap console warning as is.

## §3 Tests (health_pwa/tests/test_sync_scope.py — NEW; HttpCase, §5.32 aware)

Fixtures per conventions §6 (patients need `catchment_province_id`; clone
the `_fixture` pattern from health_workflow_auto/tests/test_workflow_auto.py).
No test in this suite completes a visit, so no §5.32 param pinning should be
needed — if you DO drive a completing side-effect, pin per §5.32.

1. **since parsing**: authenticated GET with a JS-style
   `since=2026-07-10T00:00:00.000Z` → 200, only the order changed after that
   instant returns; `since=garbage` → 200 (30-day fallback), no 500.
2. **Minimal-nurse scope (the headline)**: nurse user, NO catchment, NO
   sale/account ACLs, assigned to order A; order B (other staff) and patient
   B changed in-window. Delta returns order A + patient A; order B appears
   ONLY as absent (not in records) and patient B is ABSENT — assert both the
   presence and the absence. Assert patient payload for A includes the
   PHI fields (proving sudo reads work for the minimal nurse).
3. **Team grant**: user is member of order C's team, no assignment → C
   included.
4. **Manager audience preserved**: ops-manager user with catchment X sees
   changed orders in X, not in Y; owner sees both.
5. **Removals**: (a) cancel nurse's assignment on order A (bumps
   write_date) → next delta for that nurse emits `{id: A, is_deleted: true}`
   and no data fields; (b) archive an in-scope order → is_deleted; (c)
   unlink an order → tombstone row exists → is_deleted in the next delta.
6. **Push scope**: unassigned nurse pushes patient_notes on order B → item
   `success: False`, order unchanged; assigned minimal nurse pushes
   patient_notes on A → `success: True`, value written (sudo path);
   a pushed `stage_id` is IGNORED (not written, not an error).
7. **Debug gate**: nurse GET /health_pwa/sync/debug → 403; admin → 200.
8. **Watermark**: pull response contains `watermark`, parseable, >= the
   test's start time.

Plus: the three co-resident pin suites updated to 1.12.0 (same change as the
bump), and the full suite set green on vietuat.

### Browser QA (chrome-devtools MCP on care.biztinct.com — MANDATORY per
conventions; hard-reload with ignoreCache, §5.32 second corollary)

9. Served shell shows v1.12.0; console clean.
10. First load after deploy: purge migration runs (localStorage
    `health_pwa_scope_v` = '2'), full scoped re-pull happens, today screen
    renders.
11. Trigger sync twice (the ⟳ action at app.js:452): second request carries
    `?since=` and returns a small `total_changes`; response has `watermark`.
12. IndexedDB spot-check: `health_patients` row count is the scoped set for
    the logged-in user, not the full patient table.
13. Offline toggle (DevTools) → today list still renders from cache.

## §4 Deploy (conventions §2 — verbatim workflow)

scp → /tmp/fixdeploy → sudo cp with odoo ownership for: health_pwa,
health_pwa_daystrip, health_scribe, health_pwa_family. Then:

```
sudo -u odoo /odoo/odoo-server/odoo-bin -c /etc/odoo-server.conf -d vietuat \
  -u health_pwa,health_pwa_family,health_pwa_daystrip,health_scribe \
  --test-enable \
  --test-tags /health_pwa,/health_pwa_family,/health_pwa_daystrip,/health_scribe \
  --stop-after-init --workers 0
```

HttpCase tests ⇒ do NOT pass `--no-http`. Then restart, `/web/login` → 200,
quote the `odoo.tests.result` line verbatim.

## §5 Report back

(a) File list + diffstat. (b) Verbatim test-result line. (c) For the QA nurse
AND an admin session: sync payload `total_changes` + patient count BEFORE
(from logs/first pull) vs AFTER delta+scope — the numbers are the proof.
(d) Who could pull the full patient table before vs after (one sentence).
(e) Purge-migration evidence from browser QA (localStorage flag + IndexedDB
count). (f) Any deviation + reasoning. (g) Any new gotcha, flagged for §5.
(h) Confirm params in fact 14 untouched.

---

**Kickoff line** (prepend to `docs/strategy/KICKOFF-TEMPLATE.md` prompt):
`Implement the phase specified in docs/strategy/handovers/pwa-sync-delta-phase.md.`
Phase-specific guard: health_pwa edits are in scope ONLY as listed in §2
"Sanctioned edits"; `app.js` and `controllers/api.py` are READ-ONLY this
phase; existing response envelope shapes are binding.
