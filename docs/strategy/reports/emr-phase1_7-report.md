# health_emr Phase 1.7 — PWA "Notes to sign" reminder — Implementation Report

**Branch:** 19.0 · **Server:** vietuat (care.biztinct.com) · **Date:** 2026-07-16
**PWA asset version:** 1.17.0 → **1.18.0**
**Handover:** `docs/strategy/handovers/emr-phase1_7-pwa-sign-reminder.md`

## 1. What was built

A read-only, online-only nudge that surfaces each field nurse's OWN unsigned
draft clinical notes as a "Notes to sign" home card in the PWA, deep-linking each
row into the booking modal's **existing** Phase-1.5 Finalize & Sign button. No new
model, no new cron, no change to any finalize/seal/immutability machinery.

### Files changed (all within the handover §2.3 sanctioned set)

| File | Change |
|---|---|
| `health_pwa/controllers/api.py` | NEW `GET /health_pwa/api/clinical_notes/unsigned` — defensive, author-scoped, read-only endpoint |
| `health_pwa/static/src/js/app.js` | "Notes to sign" home card (today-view) + `loadUnsignedNotes()` fetch on mount + re-fetch after finalize + `openUnsignedNote()` row→`openBooking` wiring + `noteAgeLabel()` relative time + 3 VN fallback strings |
| `health_pwa/data/pwa_config.xml` | version param ×2 → 1.0.97 |
| `health_pwa/views/pwa_templates.xml` | asset version ×5 → 1.18.0 |
| `health_pwa/__manifest__.py` | version → 19.0.1.0.35 |
| `health_pwa/tests/test_pwa_sign_reminder.py` | NEW HttpCase (7 tests) |
| `health_pwa/tests/__init__.py` | register new test module |
| `health_pwa_daystrip/tests/test_daystrip.py` | pin assert 1.17.0 → 1.18.0 |
| `health_scribe/tests/test_scribe.py` | pin assert 1.17.0 → 1.18.0 |
| `health_pwa_family/tests/test_pwa_family.py` | pin assert 1.17.0 → 1.18.0 |

## 2. Endpoint — read-only + author-scoped (handover report-back c)

`GET /health_pwa/api/clinical_notes/unsigned` (`type='http'`, `auth='user'`,
`methods=['GET']`, `csrf=False`). Frame cloned from the Phase-1.5 finalize
endpoint: `_check_api_access()` → 403; defensive `if 'emr_state' not in
Note._fields:` → empty payload (health_pwa keeps NO hard dep on health_emr).

**The domain, verbatim:**
```python
drafts = Note.search([
    ('author_id', '=', request.env.user.id),
    ('emr_state', '=', 'draft'),
], limit=100)
```
The `author_id = request.env.user.id` pin means the `.sudo()` read can only ever
return the caller's OWN drafts — she authored them, so she already saw the
patient. The endpoint writes nothing. It returns navigation context only
(`note_id`, `order_id`, `patient_name`, `scheduled_datetime`, `age_hours`,
`overdue`) — **no note CONTENT / PHI body**. Overdue = `age_hours >=
health_emr.reminder_hours` (Phase-1.6 config, default 24, read defensively).
Sort: overdue-first, then oldest `write_date` first. Capped at 100 with a
`_logger.warning` if hit.

## 3. Test results (verbatim)

Full 4-module run (HttpCase present → `--no-http` OFF), test-tags
`/health_pwa,/health_pwa_daystrip,/health_scribe,/health_pwa_family`:

```
2026-07-16 02:20:33  ERROR  odoo.tests.result: 1 failed, 0 error(s) of 94 tests
    FAIL: TestPwaSignReminder.test_07_requires_auth
    AssertionError: 303 not found in (302, 401, 403)
```
`test_07` asserted the unauthenticated redirect status too narrowly — Odoo 19's
`auth='user'` login redirect is **303** (See Other), not 302. The endpoint was
correctly gated (it *did* redirect to login, exposing no payload); only the test
assertion was wrong. Widened to `(302, 303, 401, 403)` + `assertNotEqual(200)`.
Re-run of health_pwa alone:

```
2026-07-16 02:23:38  INFO  odoo.tests.result: 0 failed, 0 error(s) of 40 tests
```
`/web/login` → **HTTP 200** after restart. The daystrip/scribe/family pin tests
passed in the 94-test run (only `test_07` failed there), confirming the 1.18.0
bump agrees across all served-asset assertions.

The 7 sign-reminder tests: (1) lists own draft w/ correct shape + no PHI body;
(2) finalized note excluded; (3) other author's draft excluded (author-scoping);
(4) overdue flag by backdated write_date, fresh + overdue both listed;
(5) ordering overdue-first then oldest; (6) empty → `{notes:[],count:0}` 200;
(7) unauthenticated → login redirect (no payload).

## 4. Version bump (handover report-back b)

New PWA asset version **1.18.0**. All 4 bump sites + 3 pin tests agree:
- `__manifest__.py` → `19.0.1.0.35`
- `pwa_config.xml` → `1.0.97` (×2: the `ir.config_parameter` record + `set_param` eval)
- `pwa_templates.xml` → `1.18.0` (×5: `pwa_asset_version` t-set, `version:`,
  `PWA_SW_VERSION`, the SW comment line, `CACHE_VERSION`) — bumped ALL per
  conventions §3, not just the asset t-set
- pin tests daystrip / scribe / family → `1.18.0`

`grep -rn 1.17.0` across the four modules returns nothing. Served-asset version
confirmed by the passing pin-test HttpCases (they fetch the shell and assert
`*.js?v=1.18.0`).

## 5. Browser evidence pack (handover report-back a)

`docs/strategy/reports/emr-phase1_7-evidence/` — real-user path (login →
`/health_pwa` home, NOT a deep link):
- `01-home-notes-to-sign-card.png` — the card: title "Notes to sign", count **1**,
  orange **"1 overdue"** badge, row = ⚠ + "QA Sign Patient" + "2 days ago" + chevron.
- `02-note-detail-finalize-button.png` — tapping the row → booking modal →
  Clinical Notes → the draft note → the existing **Finalize & Sign** button.
- `console-log.md` — network shows my `…/clinical_notes/unsigned` → **200**; the
  only console errors are the **pre-existing** §5.24 `/api/current_user` 500 (a
  fixture artifact — bare QA employee lacks role flags; NOT touched by this
  phase). Finalize was NOT pressed (button-presence is the evidence; skipping the
  irreversible sign kept fixture deletion clean).

## 6. Report-back items

- **(d) open-specific-note-in-modal helper?** No such helper exists — I fell back
  to the handover's sanctioned path: the row opens the shared booking modal via
  `emit('navigate', 'order', {id})` → `openBooking()` bridge, and the nurse taps
  the (already-listed) note. No new note screen was built. One real-world nuance
  surfaced: the modal's **Clinical Notes** button (which reaches the note detail +
  Finalize button) only renders once the visit is `in_progress` — i.e. the true
  nurse flow is card → modal → Start Service → Clinical Notes → note → Finalize.
  For a not-yet-started booking the row still deep-links correctly to the modal;
  the finalize button becomes reachable at the point the nurse is actually
  delivering the visit (which is exactly when she'd sign). No code change needed —
  this is the pre-existing Phase-1.5 modal contract.
- **(e) QA cleanup fresh-cursor confirmation:** seeded nurse 3350 / employee 3551 /
  patient 9390 / FSO 6223 / assignment 5013 / draft note 1483; all deleted and
  re-verified `exists=False` in a SEPARATE odoo-bin shell cursor (§5.34);
  `qa_sign_nurse` login gone. No finalized note was created, so nothing was left
  undeletable.
- **(f) New gotcha:** Odoo 19's `auth='user'` HTTP route returns **303 (See
  Other)** for an unauthenticated request's login redirect, not 302 — a test
  asserting the deny status must include 303 (proposed ledger §5.44 below).

## 7. Deviations from the handover

1. **i18n:** added the 3 new user-visible strings ("Notes to sign", "overdue",
   "Patient") to the `APP_VI_FALLBACK_TRANSLATIONS` block in `app.js` rather than
   `i18n/vi.po` — matching the Phase-1.5 EMR precedent (its finalize strings live
   there too, not in any `.po`). Handover §2.3 explicitly allowed "i18n/vi.po (or
   the app.js fallback strings per PWA idiom)". Relative-time words are built
   inline in `noteAgeLabel()` (VN-first, no catalog pluralization).
2. **Card CSS:** the sanctioned-edit table does NOT list any `.css` file, so the
   card is styled with **inline flat-mono styles** in the app.js template (neutral
   card + `#1565C0` count pill + `#FB8C00` overdue/warning accent — no gradients,
   per [[feedback_mono_colors]]) rather than new CSS classes. Keeps the change
   strictly within sanctioned files.
3. **test_07 assertion widened** to accept 303 (see §3/§6f) — a test correction,
   not a design change.

No other deviations. No health_emr / health_fieldservice / health_scribe (beyond
the pin test) code touched. No new model/cron/ACL/offline-action-type.

## 8. Proposed gotcha ledger addition

> **§5.44 — Odoo 19 `auth='user'` HTTP routes answer an unauthenticated request
> with a 303 (See Other) login redirect, not 302.** A test that asserts an
> endpoint "requires auth" by checking the deny status code must include 303
> (`assertIn(status, (302, 303, 401, 403))`) — the framework redirects
> unauthenticated `type='http'` requests to `/web/login` with **303**, and
> `url_open(..., allow_redirects=False)` sees that raw status. Asserting only 302
> RED-lights a correctly-gated endpoint (hit live in
> `test_pwa_sign_reminder.test_07`, first run).
