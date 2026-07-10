# Handover: PWA Reliability — shared booking modal, dead-route removal, sync fix (`health_pwa` hardening, PWA 1.11.0)

Read `docs/strategy/HANDOVER-CONVENTIONS.md` FIRST (definition of done =
its §8; gotcha ledger 31 entries — §31 is this phase's origin story, read
it twice). This phase pays down the health_pwa debt that the pwa-family
review dug up with live evidence. Every fact in §1 was verified on
2026-07-10 against commit 5c9e4e91 — do not re-derive.

## 0. Scope

1. **One shared booking modal, all roads lead to it.** The booking-detail
   modal is the nurse's ONLY visit surface (the `#/order/<id>` screen is a
   commented-out corpse). Promote the modal so every entry point opens it,
   delete the corpse, and make the dead ends live again: orders list, past
   bookings list, the bell card (restore "Xem (View)"), push-notification
   taps, and `#/order/<id>` deep links.
2. **Fix incremental sync** — it has NEVER worked: the sync metadata write
   409s on every run, so every sync is a full 735-change pull.
3. **Sudo/scope the base `api_fso_detail`** — it reads FSO + sale.order
   with the caller's ACL, so a minimal nurse gets errors instead of data.
4. Small polish while in there: "UNKNOWN" status chips in the orders
   lists; log the 500-order sync cap instead of silently truncating.

**Non-goals (binding):** reviving the order-detail SCREEN (the modal IS
the interface — the corpse gets deleted, not resurrected); router
rewrite; offline-first redesign; new features of any kind; touching
health_pwa_family's panel logic (it must keep working UNCHANGED — see the
binding constraint in §2.1); Vue upgrade; the deprecated
`check_access_rights` cleanup (platform-wide, later).

## 1. Verified plumbing facts (do not re-derive; verified 2026-07-10 @ 5c9e4e91)

- **The dead screen (ledger §31)**: `health_pwa/static/src/js/app.js:5109`
  opens the `/* LEGACY CODE - Order Detail View Component */` block — the
  ENTIRE `order-detail-view` component (~1,600 lines incl. `.order-details`
  markup) is commented out since 2025-11-09; `#/order/<id>` renders an
  unresolved `<order-detail-view>` tag (blank page). Verify component
  registration via `app._context.components` in the console, never grep.
- **Orphaned callers that dead-end there today**: orders-view `viewOrder`
  (app.js:4863) and past-bookings-view `viewOrder` (app.js:5026) both
  `emit('navigate','order',{id})`; deep links `#/order/<id>` route there
  at boot (initial-route handling ~app.js:391) and via popstate (~:430).
  The bell family_message card had a View button doing the same — removed
  in review (this phase restores it, pointed at the modal).
- **The modal today**: markup at app.js:3192 (`.booking-detail-modal`,
  content `.booking-detail-modal-content`, footer `.modal-footer`) lives
  INSIDE today-view's template (today-view spans ~917-4348), driven by
  `selectedBookingId`/`selectedBookingDetail` refs and
  `fetchBookingDetail(bookingId)` (app.js:1646) which fetches
  `GET /health_pwa/api/fso/<id>` on every open. That is why only the
  today screen can open it.
- **health_pwa_family's panel keys on that fetch** (BINDING): fammsg.js
  wraps the bare per-id GET and injects into
  `.booking-detail-modal-content` before `.modal-footer`. Whatever you
  refactor, the shared modal MUST (a) fetch `GET /health_pwa/api/fso/<id>`
  on every open and (b) keep those two class names — or you break the
  family panel. Its suite (`/health_pwa_family`, 19 tests) plus a manual
  modal-panel check are part of YOUR definition of done.
- **Sync bug**: `utils/sync-manager.js:28-37` — `saveSyncMetadata()` puts
  `{_id:'sync_metadata', ...}` with NO `_rev` → PouchDB 409 on every run
  after the first ("Failed to save sync metadata" in every session's
  console) → `lastSyncTime` never persists → `performSync` always does a
  FULL pull (the "Received 735 changes" line on every single sync).
  Fix: get-then-put with `_rev` (classic Pouch upsert; `.get` catch 404 ⇒
  no `_rev`).
- **Non-sudo detail API**: `api_fso_detail` (health_pwa/controllers/
  api.py:395) reads the FSO and its sale.order with the CALLER's ACL —
  a nurse without catchment/sale-order read gets an error page instead of
  their own visit. Pattern to apply: the health_pwa_family precedent —
  explicit assignment-scope check FIRST, then sudo reads
  (health_pwa_family/controllers/pwa_family_api.py `_scoped_order`;
  employee via sudo `user_id` search, NOT `user.employee_id`).
- **"UNKNOWN" chips**: orders/past-bookings `getStatusLabel` fall through
  to `_t('Unknown')` (app.js:4859/5022) for real states their displayMap
  misses (live evidence: confirmed bookings render "UNKNOWN" chips).
  Compare with today-view's fuller map (~app.js:1544-1563) and unify —
  ONE shared top-level status-label helper (the `parseOdooDateTime`
  hoist in 5c9e4e91 is the precedent: shared helpers live at file
  top-level, ledger §31 tail).
- **Sync cap**: the orders pull stores at most 500 rows ("Updated 500
  orders records locally") — do not redesign; just `console.warn` when
  the cap is hit so truncation is visible.
- **SW push clicks**: `notificationclick` handler in
  health_pwa/views/pwa_templates.xml:1153 — accept/decline actions post
  to the assignments API; check the default-click branch (it opens/
  focuses a client window) and point family_message-type notifications
  (data `{type:'family_message', fso_id}`) at the deep link that now
  opens the modal. NOTE: pwa_templates.xml view arch changes need
  `-u health_pwa` to land (t-set/SW live in DB view archs).
- **Version pins**: PWA is **1.10.3**. This phase bumps **1.11.0** in the
  5 pwa_templates.xml spots + `__manifest__.py` + pin tests in
  health_pwa_daystrip/tests/test_daystrip.py,
  health_scribe/tests/test_scribe.py, and
  health_pwa_family/tests/test_pwa_family.py (three co-resident pin
  suites now — all hard-assert the version).
- **Boot/init**: `app.mount('#vue-app')` at app.js:820 runs BEFORE the
  `registerComponents` body (Vue resolves lazily per render — works, keep
  it); initial-route handling navigates from the hash after
  `loadUserData()`.

## 2. Architecture

**Sanctioned edits (exhaustive — conventions §4; nothing else in
`health_pwa` or any other shared module may change):**

- `health_pwa/static/src/js/app.js` — modal extraction to a shared root
  component (§2.1), deletion of the `/* LEGACY */ order-detail-view`
  comment block, the shared status-label helper (§2.4), restoring the
  bell card's "Xem (View)" button, re-pointing `viewOrder`/route
  handling at the shared modal.
- `health_pwa/static/src/js/utils/sync-manager.js` — the
  `saveSyncMetadata` `_rev` fix + the 500-cap warn (§2.2, §2.4).
- `health_pwa/controllers/api.py` — `api_fso_detail` scope-check + sudo
  ONLY (§2.3); no other endpoint changes.
- `health_pwa/views/pwa_templates.xml` — the SW `notificationclick`
  family_message branch (§2.1) + the 1.11.0 bump (5 spots).
- `health_pwa/__manifest__.py` — version bump.
- Pin tests: `health_pwa_daystrip/tests/test_daystrip.py`,
  `health_scribe/tests/test_scribe.py`,
  `health_pwa_family/tests/test_pwa_family.py` — version strings only.

### 2.1 Shared booking modal

- Extract the modal (template block at app.js:3192 + its state/handlers:
  `selectedBookingId`, `selectedBookingDetail`, `isLoadingDetail`,
  `detailError`, `fetchBookingDetail`, `startService`, `cancelVisit`,
  clinical-notes/invoice/next-visit sub-modal state it drags along) into
  a proper `booking-detail-modal` app-level component registered like the
  views, rendered ONCE at the root template (outside the per-route
  v-else-if chain), driven by a small root-level API:
  `openBooking(fsoId)` / `closeBooking()` exposed to views via provide or
  root methods. Today-view keeps its current behavior by calling
  `openBooking` (its card tap handlers change from local refs to the
  shared call). This is the surgical heart of the phase — move, don't
  rewrite; keep every class name and handler behavior byte-compatible
  where possible (the EVV/scribe/telehealth flows all hang off this
  modal's buttons).
- **Binding**: the shared modal still calls
  `GET /health_pwa/api/fso/<id>` on every open and keeps
  `.booking-detail-modal-content` + `.modal-footer` (the family panel's
  seam, §1).
- Re-point the dead ends: orders-view/past-bookings `viewOrder` →
  `openBooking(id)` (stay on the list, modal overlays — no route change);
  bell family_message card gets "Xem (View)" back → `openBooking(fso_id)`;
  `navigate('order', {id})` and the `#/order/<id>` initial route → render
  today-view AND `openBooking(id)` (deep links + push taps land somewhere
  real); SW `notificationclick` default branch opens
  `/health_pwa#/order/<fso_id>` for family_message pushes (which now
  works via the mapping above).
- DELETE the `/* LEGACY */ order-detail-view` comment block wholesale
  (~1,600 lines) — it is unreachable text that costs parse time and
  poisons grep (ledger §31). Nothing references the component once the
  route mapping above is in.

### 2.2 Sync metadata fix

`saveSyncMetadata`: read the existing doc first (catch 404), carry its
`_rev` into the put. Then verify live that the SECOND sync of a session
pulls only the delta (console "Received N changes" with small N), not
735. Do NOT change the sync cadence or scope.

### 2.3 api_fso_detail scope + sudo

Clone the `_scoped_order` pattern: resolve employee (sudo user_id
search), require a non-cancelled assignment on the order (managers/admin
group check may bypass — mirror however the endpoint's CURRENT audience
is broader, verify who calls it: the booking modal for the nurse's own
bookings — assignment scope is right). Then perform the FSO/sale.order
reads with sudo. Response shape must stay byte-identical (the modal and
fammsg.js consume it).

### 2.4 Status labels + cap warning

One top-level `getBookingStatusLabel(state)` map used by today/orders/
past-bookings (superset of today-view's map; VN-first labels as today).
`console.warn('health_pwa sync: order cap hit (500) — older orders not
cached offline')` when the pull returns the cap.

## 3. Tests

Server-side (`/health_pwa_family` + pin suites must stay green; add to
health_pwa's own test file if one exists, else the pin suites):
1. Version pins 1.11.0 (3 co-resident suites + shell HttpCase).
2. `api_fso_detail`: assigned nurse (minimal groups, NO sale-order ACL)
   gets 200 + data; unassigned nurse refused; response keys unchanged
   (snapshot the current key set in the test).
3. The full existing suites: `-u health_pwa,health_pwa_family,
   health_pwa_daystrip,health_scribe --test-tags /health_pwa_family,
   /health_pwa_daystrip,/health_scribe` (HttpCase ⇒ NO --no-http).

**Browser QA REQUIRED with committed evidence** (real nurse session,
phone viewport, care.biztinct.com):
4. Today → tap booking → modal opens (unchanged behavior), Start
   Service/EVV buttons present.
5. Orders list → tap row → modal opens over the list (was a blank page).
   Past bookings same.
6. `#/order/<id>` deep link cold-load → today + modal auto-open (was
   blank).
7. Bell family_message card → View → modal opens (temporarily enable
   messaging for one QA thread like the 5c9e4e91 review did — create via
   shell, clean up after, re-darken, report counts).
8. Family panel still injects into the shared modal (the §2.1 binding
   constraint) — with messaging enabled, thread visible + reply works.
9. Console: NO "Failed to save sync metadata"; second sync pulls a
   delta, not 735.
10. No "UNKNOWN" chips on the orders list for normal states.

## 4. Deploy & verify

- Standard flow; `-u health_pwa,health_pwa_family,health_pwa_daystrip,
  health_scribe` (pwa_templates.xml arch changes REQUIRE the upgrade);
  port-wait; results from the server logfile with YOUR timestamp;
  login 200.
- PWA 1.11.0 greps (5 spots) + all three pin tests updated.
- `health_family_messages.enabled` back to False after QA; params pasted.
- vi.po if any new user-facing strings; conventions §8; commit+push 19.0.

## 5. Report-back extras

(a) the modal-extraction diff summary — what moved, what stayed, any
behavior you could NOT keep byte-compatible (list each); (b) proof the
family panel still works in the shared modal (screenshot); (c) the
delta-sync console evidence (before/after lines); (d) who can call
`api_fso_detail` now vs before; (e) the deleted-corpse line count and
that `app._context.components` still lists all views; (f) any new
ledger-grade gotcha (explicitly flagged); (g) live QA data cleanup
counts + params re-darkened.
