# Browser evidence — console + network (care.biztinct.com, PWA asset 1.18.0)

Real-user path (NOT a deep link): logged in at `/web/login` as the QA nurse →
navigated to `/health_pwa` (#/today home) → the **"Notes to sign"** card
rendered on mount → tapped the row → booking modal opened (openBooking bridge)
→ Start Service state → **Clinical Notes** → tapped the draft note → the
existing **Finalize & Sign** button (Phase 1.5) rendered. Mobile viewport 430×860.

## Screenshots
- `01-home-notes-to-sign-card.png` — home card: title "Notes to sign", count **1**,
  orange **"1 overdue"** badge, row = ⚠ warning glyph + "QA Sign Patient" +
  "2 days ago" + chevron.
- `02-note-detail-finalize-button.png` — note detail reached from the card row,
  showing the unchanged **Finalize & Sign** button (Draft note, Staff role).

## Network (XHR/fetch) — my endpoint is clean
```
GET /health_pwa/api/clinical_notes/unsigned            → 200   (this phase)
GET /health_pwa/api/clinical_notes/unsigned (re-open)  → 200
GET /health_pwa/api/fso/6223                           → 200
GET /health_pwa/api/user/profile                       → 200
GET /health_pwa/api/current_user                       → 500   (PRE-EXISTING, not this phase)
```

## Console errors observed (both PRE-EXISTING — flagged per DoD)
```
[error] Failed to load resource: 500  (GET /health_pwa/api/current_user)
[error] Failed to load current user: The fields
        "access_role_id,is_duty_doctor,is_head_nurse,is_om_role", which you are
        trying to read, are not available for employee public profiles.
```
This is the §5.24 public-profile guard on the **pre-existing** `/api/current_user`
endpoint (NOT touched by Phase 1.7). It fired because the QA-fixture `hr.employee`
was created bare (no role flags / `access_role_id`) — the endpoint reads those
fields without `.sudo()`, so a freshly-minted employee trips the guard. A
properly-provisioned production nurse has those fields set. My Phase-1.7 endpoint
(`/api/clinical_notes/unsigned`) returned **200** and the card rendered its data
correctly; the 500 did not affect it. No new console error was introduced by this
phase.

## QA fixture cleanup (§5.34, fresh-cursor verified)
Seeded: nurse user 3350 + employee 3551 + patient 9390 + FSO 6223 + assignment
5013 + draft note 1483. All deleted, then re-checked in a SEPARATE odoo-bin shell
cursor: every id `exists=False`, `qa_sign_nurse` login gone. No note was
finalized (the immutable seal was never created), so nothing was left undeletable.
