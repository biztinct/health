# health_emr Phase 1.7 — PWA "Notes to sign" reminder (close the finalize loop)

Phase 1.5 gave the field nurse a **Finalize & Sign** button inside the booking
modal's note detail. Phase 1.6 added a nightly backend backstop that raises a
"sign this note" **`mail.activity`** on the author — but a field nurse lives in
the PWA and **never sees backend activities**, so aging unsigned drafts pile up
invisibly. Phase 1.7 closes the loop: surface each nurse's own **unsigned draft
notes** as a "Notes to sign" card on the PWA home, each row deep-linking into
the booking modal → note detail → the **existing** finalize button.

This is a NUDGE + navigation phase. **No new finalize logic, no new model, no
change to the seal/immutability/authorization machinery** — all of that shipped
in 1.5/1.6 and is reused verbatim.

Read `HANDOVER-CONVENTIONS.md` first (§3 PWA version bump — READ the current
value, don't assume; §8.1 evidence pack; §5.34 fresh-cursor QA cleanup;
`reference_httpcase_no_http` — this phase ships an HttpCase so the deploy test
command MUST keep `--no-http` OFF). All plumbing below is pre-verified — do not
re-derive.

---

## 0. Scope and binding non-goals

**Build (health_pwa only — the Phase-1.5 precedent hosts EMR↔PWA glue here):**
1. ONE endpoint `GET /health_pwa/api/clinical_notes/unsigned` — returns the
   logged-in nurse's OWN draft (`emr_state='draft'`) notes she authored, with
   enough context to deep-link (note_id, order_id, patient name, visit date,
   age). Defensive `emr_state in _fields` guard (health_pwa does NOT depend on
   health_emr — clone the Phase-1.5 endpoint's guard exactly).
2. A **"Notes to sign" card** on the PWA home (app.js): a count + an
   expandable list; each row taps through to that booking's modal note detail
   (where the finalize button already lives). Reuse the existing bell/home-card
   idiom (health_pwa_family's `family_message` card is the precedent) + the
   `openBooking()` bridge.
3. PWA version bump (§3) + the co-resident pin tests. Tests + vi.po.

**Binding NON-goals:**
- NO change to `action_finalize()`, `_compute_content_hash`, the immutability
  guard, `_ensure_can_finalize`, or ANY health_emr model code. This phase does
  not finalize anything itself — it only LISTS drafts and navigates to the
  existing button.
- NO new backend model, NO new cron, NO change to Phase-1.6 automation.
- NO offline queue for this list — it is a read-only nudge, ONLINE-only (like
  the Phase-1.5 finalize endpoint). Do NOT add a `finalize_clinical_notes`
  offline action type (deferred; out of scope).
- NO surfacing of OTHER nurses' notes (a head-nurse co-sign queue is a later,
  separate phase). Author-scoped only — matches Phase 1.6's
  `_create_sign_reminder` which targets the author.
- NO messaging/ZNS, NO push notification (a home card, not a push). NO pip.
- NO edits to health_emr / health_scribe / health_fieldservice / any shared
  module other than the sanctioned health_pwa files + the 3 pin-test bumps.

---

## 1. Verified plumbing facts (do not re-derive)

### health_emr note model (read-only for this phase)
- Model `health.clinical.note`
  (`addons/health_emr/models/health_clinical_note.py`). Fields we READ:
  `emr_state` Selection draft/final (:80), `author_id` M2O res.users (base
  note field — the note's author), `order_id` M2O health.fieldservice.order,
  `signed_by_id`/`signed_datetime` (:86-93), `write_date` (Phase-1.6 sweeps
  drafts by write-date age so an actively-edited draft isn't nagged).
- `order_id.patient_id` is the patient; `order_id.scheduled_datetime` the visit
  time. The note has NO record rule (only ACL); a create-only nurse cannot read
  arbitrary notes via her own env — so the endpoint reads SUDO and FILTERS by
  `author_id = request.env.user.id` (she only ever sees her own). This mirrors
  the Phase-1.5 endpoint which reads note+order sudo and relies on an explicit
  ownership/authorization filter, NOT the record rule.
- Reminder threshold precedent: Phase-1.6 config `health_emr.reminder_hours`
  (default 24) is the age after which a draft is "overdue". Reuse it to mark
  rows overdue (read via `ir.config_parameter.sudo().get_param`, defensively —
  default 24 if health_emr absent). Show ALL the nurse's drafts, flag the
  overdue ones; do not hide fresh ones (she may want to sign immediately).

### health_pwa endpoint pattern (clone Phase 1.5)
- `addons/health_pwa/controllers/api.py`. The Phase-1.5 finalize endpoint
  (`api_fso_finalize_clinical_note`, ~:1040) is the exact template:
  `@http.route('/health_pwa/api/...', type='http', auth='user',
  methods=[...], csrf=False)`, first line `if not self._check_api_access():
  return self._prepare_json_response(error=_('Access denied'),
  status_code=403)`, then the `if 'emr_state' not in note._fields:` defensive
  guard, responses via `self._prepare_json_response(data=…)`. Use `methods=
  ['GET']` here.
- Current nurse → employee: `request.env['hr.employee'].sudo().search(
  [('user_id','=',request.env.user.id)], limit=1)` (pattern at api.py
  `_can_access_order_detail` ~:79). For THIS endpoint you do NOT need the
  employee — author scoping is by `author_id = request.env.user.id` directly
  (the user, not the employee, authors a note).
- Return shape (JSON): `{'notes': [{'note_id', 'order_id', 'patient_name',
  'scheduled_datetime' (iso or null), 'age_hours' (int), 'overdue' (bool)},
  …], 'count': N, 'overdue_count': M}`. Order newest-overdue-first (overdue
  desc, then oldest write_date first so the most-overdue surfaces top).

### health_pwa app.js (the single PWA app)
- `addons/health_pwa/static/src/js/app.js` is the ONLY PWA JS app; the booking
  MODAL is the visit surface (no `#/order` screen). The Phase-1.5 finalize
  button lives in the modal note-detail (`finalizeNote()`, button ~:3868).
- Home cards precedent: health_pwa_family added a `family_message` bell/home
  card to app.js (sanctioned shared-module edit — see [[project_pwa_family]]).
  Clone that card idiom for "Notes to sign".
- Navigation bridge: `openBooking(orderId)` opens the booking modal (the
  pwa-reliability bridge — [[project_pwa_reliability]]). A row tap calls
  `openBooking(order_id)` then reveals that note's detail (where the finalize
  button + Draft/Signed chip from Phase 1.5 already render). If a helper to
  open a specific note within the modal doesn't exist, open the modal and let
  the nurse tap the (already-listed) note — do NOT build a new note screen.
- Fetch on home load + after a successful finalize (re-fetch so a just-signed
  note drops off the card). Material-icons + VN/EN fallback strings per PWA
  idiom (§4, flat-mono, no emoji).

### PWA version bump (§3 — READ current values, they drift)
- `addons/health_pwa/__manifest__.py` version (currently `19.0.1.0.34` — verify).
- `addons/health_pwa/data/pwa_config.xml` `health_pwa.version` in TWO places
  (the `ir.config_parameter` record AND the `set_param` function eval;
  currently `1.0.96` — verify).
- `addons/health_pwa/views/pwa_templates.xml` `pwa_asset_version` (currently
  `1.17.0` — verify; this is the asset cache-bust string the pin tests assert).
- **Bump the asset version to the next minor (1.17.0 → 1.18.0)** and bump the
  manifest + config-param consistently. The three co-resident PIN TESTS
  hard-assert the asset string and MUST bump in the same change:
  `health_pwa_daystrip/tests/test_daystrip.py` (~:304), `health_scribe/tests/
  test_scribe.py` (~:405), `health_pwa_family/tests/test_pwa_family.py` (~:420)
  — each asserts `v=1.17.0`. Update all three to the new value.

---

## 2. Architecture

health_pwa (asset 1.18.0). No new module, no new depends (the endpoint is
defensive so health_pwa keeps NO hard dep on health_emr, exactly like the
Phase-1.5 finalize endpoint).

### 2.1 Endpoint `GET /health_pwa/api/clinical_notes/unsigned`

In `controllers/api.py`, cloning the Phase-1.5 finalize endpoint's frame:
- `auth='user'`, `type='http'`, `methods=['GET']`, `csrf=False`.
- `_check_api_access()` first (403 on fail).
- Defensive: `Note = request.env['health.clinical.note'].sudo()`; if
  `'emr_state' not in Note._fields:` return `{'notes': [], 'count': 0,
  'overdue_count': 0}` (health_emr not installed → empty, no error).
- Query: `Note.search([('author_id','=',request.env.user.id),
  ('emr_state','=','draft')])`. (Author-scoped → she only sees her own; SUDO
  read is safe because the domain pins author to the caller.)
- For each: resolve `order_id`, `order_id.patient_id.name`,
  `order_id.scheduled_datetime`, `age_hours = (now - write_date)` in hours,
  `overdue = age_hours >= reminder_hours`. Build the return dict (§1 shape).
- Sort overdue-first then oldest write_date. Cap the list defensively
  (e.g. limit 100) — a nurse won't realistically have more; log if capped.

### 2.2 PWA "Notes to sign" home card (app.js)

- A reactive `unsignedNotes` ref + `unsignedCount`/`overdueCount`; fetch on
  home mount and after a finalize succeeds.
- Card: a flat-mono card titled "Notes to sign" (VN: "Ghi chú cần ký") with the
  count; hidden entirely when count is 0 (no empty card noise). Overdue rows
  get a subtle attention treatment (a "material-icons" warning glyph + the
  house warning token — NO red gradient, §4/[[feedback_mono_colors]]).
- Each row: patient name + visit date (relative, e.g. "2 days ago") + a chevron;
  tap → `openBooking(row.order_id)` → the modal note detail with the existing
  Finalize & Sign button. After the nurse signs (existing finalize flow), the
  card re-fetches and the row drops off.
- 8-12 VN/EN fallback strings (card title, "cần ký"/"to sign", "quá hạn"/
  "overdue", relative-time words, empty-safe). Material-icons only.

### 2.3 Sanctioned edits (exhaustive)

| Module | File | What may change |
|---|---|---|
| health_pwa | controllers/api.py (NEW `GET …/clinical_notes/unsigned` endpoint ONLY — defensive, author-scoped, read-only), static/src/js/app.js (the "Notes to sign" home card + fetch + row→openBooking wiring; reuse the existing finalize flow, do NOT alter it), data/pwa_config.xml (version param ×2), views/pwa_templates.xml (asset version), __manifest__.py (version), i18n/vi.po (or the app.js fallback strings per PWA idiom), tests | as listed |
| health_pwa_daystrip | tests/test_daystrip.py | version pin assert → new asset value |
| health_scribe | tests/test_scribe.py | version pin assert → new asset value |
| health_pwa_family | tests/test_pwa_family.py | version pin assert → new asset value |

NO health_emr / health_scribe (beyond the pin test) / health_fieldservice code.
NO new model/cron/ACL. NO finalize-logic edit. NO offline action type.

---

## 3. Safety rails (binding)

- **Read-only nudge.** The endpoint performs NO write — it lists drafts. All
  finalization still goes through the unchanged Phase-1.5 button/endpoint
  (which enforces `_ensure_can_finalize` + the seal). This phase cannot sign,
  cannot alter, cannot delete a note.
- **Author-scoped PHI.** The domain pins `author_id = caller` so the sudo read
  can only ever return the caller's OWN notes (she authored them → already saw
  the patient). NEVER widen the domain to other authors or drop the author
  filter. Do not return note CONTENT (narrative/PHI body) in the list — only
  patient name + visit date + age (the minimum to navigate). The content is
  read in the modal under the existing authorized path.
- **Defensive dep.** health_pwa keeps NO hard dependency on health_emr; the
  `emr_state in _fields` guard returns an empty list when absent (clone Phase
  1.5 exactly). Do NOT add health_emr to health_pwa depends.
- **Online-only.** No offline queue (a nudge, not an action). No sync-scope
  change, no service-worker change.
- Flat-mono card, no gradients/emoji (§4). PWA version bumped in all 4 places
  + 3 pin tests (§3). QA fixtures cleaned + fresh-cursor verified (§5.34);
  NEVER finalize a real patient's note for QA (irreversible PHI — Phase 1.5's
  discipline). §5.43 staleness note is twin-only, ignore here.

## 4. Tests (tests/test_pwa_sign_reminder.py; ~7, HttpCase — keep --no-http OFF)

Fixture note: create notes SUDO with an explicit `author_id` (a create-only
nurse can't do the PHI-encryption inverse write — the Phase-1.5 fixture gotcha,
memory [[emr-record-spine]]).

1. Author sees her OWN draft in the list (correct shape: note_id/order_id/
   patient_name/age/overdue).
2. A FINALIZED note of hers is EXCLUDED (only drafts listed).
3. Another author's draft is EXCLUDED (author-scoping — create it with a
   different author_id, assert the caller's list omits it).
4. `overdue` flag: a draft older than `reminder_hours` (backdate write_date via
   raw SQL, §5.9) → overdue=True; a fresh one → overdue=False; both still
   listed.
5. Ordering: overdue-first, then oldest write_date.
6. Defensive/empty: (structural) with health_emr present, a nurse with no
   drafts → `{'notes':[], 'count':0}` (200, not error). [If feasible, note the
   field-absent branch is covered by the guard; don't uninstall to test.]
7. Endpoint requires auth (`_check_api_access`) — unauthenticated/again-403.
8. Version pin: the new asset string is served (the daystrip/scribe/family pin
   tests already cover this once bumped — re-run them).

## 5. Deploy / verify (conventions §2)

- HttpCase present → **keep `--no-http` OFF** ([[reference_httpcase_no_http]]).
  `-u health_pwa,health_pwa_daystrip,health_scribe,health_pwa_family
  --test-enable --test-tags /health_pwa,/health_pwa_daystrip,/health_scribe,
  /health_pwa_family --stop-after-init --workers 0` (upgrade the pin-test
  modules too so their bumped asserts run). Result line; restart; `/web/login`
  200; confirm the new asset version is served
  (`curl … | grep pwa_asset_version` or the served bundle URL).
- **Browser evidence pack (§8.1)** to
  `docs/strategy/reports/emr-phase1_7-evidence/`, from the REAL PWA on
  care.biztinct.com: (1) the home "Notes to sign" card with a count + at least
  one row (seed a QA nurse + a QA booking + a DRAFT note authored by her — a
  DRAFT is safe to seed/delete, unlike a finalized note); (2) tapping a row
  opens the booking modal note detail showing the existing Finalize & Sign
  button (do NOT press it on a real patient; a QA fixture note is fine to sign
  if you then delete the whole fixture). Console clean. Delete QA fixtures +
  fresh-cursor verify (§5.34): nurse/user, booking, note, receipts → 0.

## 6. Report back

Standard §8 (report committed to
`docs/strategy/reports/emr-phase1_7-report.md`), plus: (a) the evidence pack
(card + count + row→modal deep-link); (b) the exact new PWA asset version and
confirmation all 4 bump sites + 3 pin tests agree; (c) confirmation the endpoint
is read-only + author-scoped (quote the domain); (d) whether an
open-specific-note-in-modal helper existed or you fell back to
open-modal-then-tap; (e) QA cleanup fresh-cursor confirmation; (f) any new
gotcha.

Kickoff line: `Implement the phase specified in docs/strategy/handovers/emr-phase1_7-pwa-sign-reminder.md.`
