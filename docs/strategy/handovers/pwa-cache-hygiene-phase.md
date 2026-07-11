# Phase handover: pwa-cache-hygiene — device PHI GC + ACL tightening + honest cap semantics

Implementer: Opus 4.8. Designer/reviewer: Fable. Read
`docs/strategy/HANDOVER-CONVENTIONS.md` in FULL first (especially §3 version
bump, §4 sanctioned edits, §5.1, §5.32, §5.33, §5.34). This phase closes the
PWA hardening arc's recorded backlog. It is deliberately SMALL — do not grow
it.

## §0 Scope (binding)

Four items, nothing else:

1. **Client-side patient GC** — cached patient docs whose id is no longer
   referenced by any cached order are deleted after each successful sync.
   This is the actual fix for "de-scoped PATIENTS linger on devices"
   (pwa-sync-delta backlog). Server-side patient removals are deliberately
   NOT built: de-scoping happens without any patient-row write (a nurse is
   de-assigned, an order ages past the 90-day horizon — §5.33-class), so a
   write-window removal feed would miss the main case. Orders already get
   correct removals (G-scoped, §5.33-fixed); the order cache is therefore
   authoritative and patients follow it referentially.
2. **`health.pwa.staff.notification` ACL tightening** — the current grant is
   `base.group_user` 1,1,1,1 on a model storing `patient_name` (PHI-adjacent):
   any internal user can CRUD everyone's notifications. Every code path
   (verified, §1 fact 6) uses `.sudo()`, so tighten to `base.group_system`.
3. **Honest cap semantics** — when the 500-upsert cap fires in
   `_get_fso_changes`, the response says so (`capped: true`, additive key),
   the capped selection prefers clinically relevant orders
   (`scheduled_datetime desc`) instead of write_date order, and the client
   SKIPS patient GC on a capped sync (order absence is not proof of de-scope
   when the pull was truncated). This interlock is BINDING — GC without it
   deletes valid patients on owner/ops devices (ds_qa_nurse holds the Owner
   group → scope = all 1,266 orders → cap fires today, live).
4. **Deprecated `check_access_rights` → `check_access`** at the three sites
   in §1 fact 8 (Odoo 19 deprecation cleanup; behavior identical).

**Binding non-goals:** NO server-side patient removal records; NO tombstones
for res.partner; NO new UI (no toast/badge for capped — a `console.warn` is
enough); NO change to the 500/2000 cap VALUES; NO offline-COMPLETE, images,
EVV wiring; envelope changes additive-only (old clients must keep working
against the new server and vice versa). `api.py` and `pwa.py` may be edited
ONLY for the one-line fact-8 swap each.

## §1 Verified plumbing facts (do NOT re-derive)

1. `_get_patient_changes` = `sync.py:351-384`; domain at :363-369
   (`id in patient_scope_ids` + is_patient + since-window), `limit=500` at
   :370. It NEVER emits `is_deleted` for patients.
2. `_sync_scope` = `sync.py:99-169`; `patient_scope_ids` at :152-159 =
   patients of in-grant orders with `scheduled_datetime >= now-90d`.
3. `_get_fso_changes` = `sync.py:425-509`: candidates `limit=2000` at :447
   (ordered `write_date desc`), upsert cap 500 via `continue` at :480-481
   (removals UNCAPPED), out-of-scope removals `{'id': …, 'is_deleted': True}`
   at :485-486, tombstone removals at :493-500.
4. Client stores patients in PouchDB `this.db.patients`, orders in
   `this.db.orders`; doc `_id` = String(odoo id) (`sync-manager.js:325`,
   `storage-manager.js:138,286`). Order docs reference their patient as the
   integer field `patient_id` (`storage-manager.js:204,257-259`).
5. `applyServerChanges` = `sync-manager.js:270-303` (patients applied at
   :273, orders at :286; cap console.warn at :279-285);
   `updateLocalData` = `sync-manager.js:305-354` and ALREADY honors
   `is_deleted` for both models (:314-318). The one-time scope-purge
   migration (:230-268) is not ongoing GC — there is NO existing patient GC.
6. `health.pwa.staff.notification` model =
   `models/pwa_staff_notification.py` (fields incl. `patient_name` :25).
   ACL = `security/ir.model.access.csv:6` (`base.group_user,1,1,1,1`).
   ALL access paths are sudo: `api.py:2154-2186` (read/update),
   `health_fieldservice/models/health_fieldservice_order.py:2333,2410,3111`
   (create), `health_family_messages/models/health_family_thread.py:229,301`
   (search/update). No backend view/menu/action exposes the model. Verified:
   tightening the ACL breaks nothing.
7. `backgroundSync` (sync-manager.js) dispatches
   `health-pwa-sync-completed` after `performSync` resolves (9c00205c fix);
   `performSync`/`performFullSync` `await this.migrationDone` after setting
   `syncInProgress` — run GC INSIDE performSync after `applyServerChanges`,
   not in an event listener (listeners must stay read-only consumers).
8. Deprecated call sites: `sync.py:48`, `pwa.py:434`, `api.py:36` — each is
   `request.env['res.partner'].check_access_rights('read')` inside an
   endpoint access gate. Odoo 19 replacement:
   `request.env['res.partner'].check_access('read')` (on an empty recordset
   this performs the model-level check). VERIFY once in odoo shell on the
   server before assuming (§5.34 recipe — separate invocation).
9. Current PWA version **1.13.1** / manifest **19.0.1.0.30**. Version spots:
   `pwa_templates.xml` :9, :246, :365, :851, :854. Pin suites:
   `health_pwa_daystrip/tests/test_daystrip.py:304-306`,
   `health_scribe/tests/test_scribe.py:405-407`,
   `health_pwa_family/tests/test_pwa_family.py:420-422`. This phase bumps to
   **1.14.0** / **19.0.1.0.31** (sync-manager.js content changes ⇒ §3 rule).
10. Test bases to extend: `test_sync_scope.py` `SyncScopeBase` (:22-106,
    helpers `_patient` :88, `_order` :96, `_assign` :105, `_changes`
    :109-118, `_data_ids`/`_removal_ids` :128-134). §5.32 pin pattern:
    `test_offline_actions.py:26-31` — NOT needed here unless a test starts a
    visit (none should).
11. fact-14 safety params (BINDING, real patient phones):
    `health_family_messages.enabled=False`, `health_messaging.enabled=False`,
    `health_messaging.dry_run=True`, `health_workflow_auto.
    timecard_sync_enabled=False` (`onetap_enabled=True` is live — leave it).
    NO pip installs.

## §2 Sanctioned edits (exhaustive) + architecture

| File | What may change |
|---|---|
| `health_pwa/controllers/sync.py` | (a) extract the two cap literals into module constants `FSO_CANDIDATE_LIMIT = 2000`, `FSO_UPSERT_CAP = 500` and use them at :447/:480; (b) when the upsert cap triggers, set `capped: True` on the fso changes block (additive key, alongside `records`); (c) apply the cap to the in-scope data records sorted by `scheduled_datetime desc` (removals stay uncapped and unsorted); (d) the :48 fact-8 swap |
| `health_pwa/controllers/api.py` | ONLY the :36 fact-8 swap |
| `health_pwa/controllers/pwa.py` | ONLY the :434 fact-8 swap |
| `health_pwa/static/src/js/utils/sync-manager.js` | new `gcOrphanPatients()` + its invocation inside `performSync` (and `performFullSync`) AFTER `applyServerChanges` succeeds; capped-flag plumbing (read `changes.field_service_orders.capped`, keep the console.warn, skip GC when capped) |
| `health_pwa/security/ir.model.access.csv` | staff-notification line → `base.group_system,1,1,1,1` |
| `health_pwa/tests/test_cache_hygiene.py` | NEW — §3 tests |
| `health_pwa/views/pwa_templates.xml`, `health_pwa/__manifest__.py` | version bump only (fact 9) |
| 3 pin-suite test files | version assertion bump only |

Anything else in health_pwa (app.js included) and every other module:
READ-ONLY. No i18n changes expected (no new user-visible strings — if you
add one, it goes in `i18n/vi_VN.po` like last phase, and say so).

**`gcOrphanPatients()` design (binding):**
```
1. Guard: only run when this sync's pull was NOT capped and
   applyServerChanges completed without throwing.
2. referenced = Set(allDocs of db.orders → doc.patient_id, non-null)
3. For each doc in db.patients.allDocs: if Number(doc._id) not in
   referenced → db.patients.remove(doc). Wrap per-doc in try/catch
   (conflict-safe); count and console.log a one-line summary.
4. Never throw out of GC — a GC failure must not fail the sync.
```
Cap-sort note for sync.py (c): sort ONLY the in-scope upsert candidates by
`scheduled_datetime desc` before applying `FSO_UPSERT_CAP`; keep the
existing candidate WINDOW queries untouched (both write-date windows from
the §5.33 fix stay exactly as they are).

## §3 Tests (test_cache_hygiene.py, TransactionCase unless noted) + QA

1. **ACL deny**: minimal nurse (`new_test_user`, nurse group) calling
   `env['health.pwa.staff.notification'].with_user(nurse).search([])`
   raises AccessError; `create` too.
2. **Bell still works** (HttpCase): nurse authenticates, the api.py
   notification endpoint (:2154 route) returns success — sudo path
   unaffected by the ACL change.
3. **capped flag emitted**: monkeypatch `FSO_UPSERT_CAP` to 2 (patch the
   module attribute, `addCleanup` restore), give a nurse 4 assigned orders,
   call `/health_pwa/sync/changes` → exactly 2 data records, `capped is
   True`, and the 2 records are the two LATEST by `scheduled_datetime`.
4. **capped absent when under cap**: same fixture unpatched → `capped` key
   falsy/absent, 4 records.
5. **removals uncapped under cap**: with cap patched to 1 and one order
   cancelled+de-assigned (out of scope), the removal still arrives alongside
   the 1 capped data record.
6. **fact-8 swap smoke**: nurse hits `/health_pwa/sync/changes` and the
   pwa.py/api.py gated routes → all still 200 (no AttributeError from the
   deprecated-API swap).
7. **No patient data leak unchanged**: reuse `SyncScopeBase`-style fixtures
   to assert patients outside `patient_scope_ids` still never appear —
   regression net around the cap-sort edit.

Browser QA (chrome-devtools MCP on care.biztinct.com, per
`feedback_browser_qa`; use `ds_qa_nurse` — NOTE it holds Owner, so it is
also your capped-device test subject):
8. ds_qa_nurse sync → console shows the cap warn AND "GC skipped (capped)"
   path taken; patients db NOT emptied.
9. A true minimal nurse (create a temp QA login, **revert it after — §5.34:
   verify the revert in a fresh cursor, do not trust the shell that made
   it**): sync → patients db contains exactly the patients referenced by
   cached orders; remove one assignment server-side, re-sync → order removal
   arrives and its now-unreferenced patient doc is GC'd.
10. Version 1.14.0 served everywhere (ignoreCache reload), console clean
    otherwise, login 200.

## §4 Deploy

Conventions §2 exactly. Modules: `-u health_pwa,health_pwa_daystrip,
health_scribe,health_pwa_family --test-tags /health_pwa,/health_pwa_daystrip,
/health_scribe,/health_pwa_family`. HttpCase tests exist ⇒ **no `--no-http`**.
Result line from `/var/log/odoo/odoo-server.log` via `sudo grep -a
'odoo.tests.result'`, matched to YOUR timestamp. Restart, login 200.

## §5 Report back

(a) file list + diffstat; (b) test result line verbatim; (c) which QA login
you used for item 9 and PROOF its state was reverted (fresh-cursor readout,
§5.34); (d) the exact `check_access` shell verification output (fact 8);
(e) deviations + reasons; (f) any new gotcha for the §5 ledger; (g) fact-11
params untouched confirmation.

---

**Kickoff line for the Opus session:**

> Read `docs/strategy/KICKOFF-TEMPLATE.md` and then implement
> `docs/strategy/handovers/pwa-cache-hygiene-phase.md` end-to-end. Guard
> line for this phase: edits are limited to the §2 sanctioned-edits table —
> `api.py`/`pwa.py` each admit exactly ONE one-line deprecated-API swap and
> nothing else; the GC-skip-when-capped interlock in §0 item 3 is binding;
> QA state you create on vietuat must be reverted and the revert verified in
> a FRESH cursor (conventions §5.34) before you report done.
