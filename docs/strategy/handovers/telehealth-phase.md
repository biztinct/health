# Handover: Telehealth v1 — `health_telehealth`

Read `docs/strategy/HANDOVER-CONVENTIONS.md` FIRST (definition of done =
its §8; gotcha ledger now has 17 entries — read all). This is Tier 3
continuing: video visits for the `telemedicine` service type that
ALREADY exists end-to-end in booking (service_type `telemedicine` →
`service_location='online'`) but currently books a visit nobody can
join. v1 = a room per online visit, nurse/doctor joins from the PWA or
backend, patient joins through a tokenized no-login **waiting-room
page** that only reveals the video link while the visit is live.

## 0. Scope (one new module `health_telehealth`)

1. **`health.telehealth.session`** — one session per online FSO
   (room slug + patient token + lifecycle), created at booking confirm,
   opened at service start, closed at completion.
2. **Patient waiting-room page** `/tele/visit/<token>` (GET-only,
   family-link clone) that gates the room URL on the visit being live.
3. **ZNS purpose `telehealth_join`** through the shipped rails at
   confirm (the link is the waiting room, so it can go out early).
4. **Nurse "Join video" action** in the PWA (daystrip-precedent JS, no
   app.js edits at all this time) + a backend button on the FSO form.
5. **EVV fix**: online visits are geofence-exempt for verification
   (today `evv_verified` can NEVER be true for an online visit — a real
   shipped defect this module owns the fix for).

⇒ **PWA bump required: 1.7.0 → 1.8.0** + manifest `.20 → .21`
(conventions §3); deploy health_pwa alongside (bump-only diff).

**Non-goals (binding):** recording/storing video (PHI + infra decision
— later phase; do NOT create attachment plumbing); self-hosted Jitsi /
JWT auth (config already points at a base URL so ops can self-host
later without code); multi-party/family join; payments changes; edits
to app.js (zero lines this phase — the daystrip fetch-wrap precedent
covers the need); any change to health_messaging/health_family_link/
health_self_booking existing files.

## 1. Verified plumbing facts (do not re-derive; refs verified Jul 2026)

- **Booking already models online visits**: FSO `service_location`
  Selection incl. `'online'`
  (health_fieldservice/models/health_fieldservice_order.py:855-861);
  service_type incl. `('telemedicine', 'Telemedicine/Online')`
  (L20-32); quick-booking maps telemedicine→online
  (wizard/health_quick_booking_wizard.py:91-98). FSO ALREADY HAS
  `online_meeting_url` (Char) + `online_platform` (zoom|teams|google|
  custom) at L879-906 — nothing fills them today; this module does
  (platform 'custom').
- **Lifecycle hooks**: `action_confirm_booking` (L2121-2165),
  `action_start_service` (L2528-2573, sets `actual_start_datetime`,
  state in_progress), `action_complete_service` (L2756-2842). EVV
  inherits start/complete (health_evv/models/
  health_fieldservice_order.py:142-178) — your inherits go post-super,
  try/except-wrapped (family-link precedent: a telehealth failure must
  never block booking/start/complete).
- **EVV defect to fix**: `evv_verified` computes from
  `checkin.inside_geofence AND checkout.inside_geofence`
  (health_evv/models/health_fieldservice_order.py:72-100 —
  `_compute_evv_status`); geofence compares against the patient's home
  coords, so an online visit can never verify. Fix by inherit: when
  `service_location == 'online'`, verification requires the
  checkin+checkout events but treats geofence as satisfied. Inspect
  the exact compute before writing; re-run `/health_evv`.
- **Doctor identity**: `primary_doctor_id` (FSO L771-776, domain
  is_doctor_role) and `assigned_doctor_ids` via health.staff.assignment
  `assignment_role='doctor'` (L778-789); `lead_staff_id` = first 'lead'
  assignment. The join page shows the lead staff OR primary doctor
  given name — pick whichever is set (doctor first).
- **Token-page conventions**: family_public.py (GET-only lifecycle,
  rate key, neutral page), selfbook_public.py, offer_public.py.
  `gateway.rate.counter.hit('tele:<ip>')` returns `(allowed, retry)`.
- **Send rails**: copy `health_family_link/models/health_family_link.py
  ::_send_zns` (L294-359) verbatim-adapted: enabled→skipped before
  dry_run→simulated; empty template param → NO row; `_safe_phone`
  try/except (ledger §5.15); purpose via selection_add
  (health_family_link/models/outbound_message.py precedent).
- **PWA seam (daystrip precedent, commit 1e6cee67)**:
  `health_pwa_daystrip/static/src/js/daystrip.js` wraps `window.fetch`
  for `/health_pwa/api/assignments/today` and injects card actions via
  the `data-fso-id` attribute that now exists on every booking card.
  The today payload's `location` field = `fso.service_location or
  service_address` (health_pwa/controllers/api.py:1521) — so
  `location === 'online'` identifies telemedicine cards client-side
  with NO server change.
- **Consent**: types are service/data_sharing/photography/
  emergency_treatment/marketing (health_consent.py:74-82);
  `check_consent(patient, 'service')` never raises, logs evidence. No
  video-specific type; 'service' covers the consult itself (no
  recording in v1 ⇒ no data_sharing gate needed).
- **Config pattern**: health_self_booking/models/res_config_settings.py
  (module-prefixed `config_parameter` fields).

## 2. Architecture

### 2.1 `health.telehealth.session`

| field | notes |
|---|---|
| fso_id | m2o FSO, required, index, ondelete cascade; one session per FSO (search-first get-or-create) |
| room_slug | Char = `'vu-%s-%s' % (fso_id, secrets.token_urlsafe(12))`, generated once |
| patient_token | Char required index, `secrets.token_urlsafe(24)`, unique index in `init()` (ledger §5.1) |
| state | pending / open / closed / cancelled |
| opened_at / closed_at | Datetime, set by the start/complete hooks |
| expires_at | scheduled end + 24h (family-link `_link_expiry` math); render-time check, no cron |
| outbound_message_id | m2o health.outbound.message |

`room_url` (computed, not stored) = `<base>/<room_slug>` with base
from config `health_telehealth.video_base_url` (default
`https://meet.jit.si`). On session create, also write the FSO's
existing `online_meeting_url` = room_url and `online_platform =
'custom'` so every existing backend view shows the link — that is the
ONLY FSO write. The room URL is a capability URL: never log it at
info level; unguessable slug is the v1 access control (self-host +
JWT is the documented upgrade path, put that sentence in the manifest
description).

### 2.2 Triggers (FSO inherit, all post-super + try/except)

- `action_confirm_booking`: if `service_location == 'online'` →
  get-or-create session (state pending) +
  `check_consent(patient, 'service')` (log-only; do NOT block) +
  `_send_join_zns()` — purpose `telehealth_join`, dedup
  `telejoin-<session_id>`, params `{patient_name, visit_date
  (wall-clock, pytz — ledger's most-hit bug), staff_name (doctor-or-
  lead given name), link}` where link = the WAITING-ROOM page URL,
  never the room URL.
- `action_start_service`: session (if any) → state open, opened_at.
- `action_complete_service` / cancellation path: state closed/
  cancelled, closed_at. Inspect how cancellation lands on FSO
  (`state='cancelled'` write vs a method) and hook the cheapest
  reliable seam; report which.

### 2.3 Patient waiting room `/tele/visit/<token>` (GET-only)

Clone family_public.py exactly (rate key `tele:<ip>`; invalid/expired/
cancelled/over-limit → the SAME neutral page). Render by session+FSO
state:
- pending (upcoming): patient name, date + time window (wall-clock),
  doctor/staff given name, "Video sẽ mở khi bác sĩ bắt đầu (the video
  opens when the doctor starts)" + facility phone;
  `<meta http-equiv="refresh" content="60"/>` so the page flips by
  itself when the visit starts (daystrip meta-refresh precedent).
- open (in_progress): one big Join button → `room_url`
  (`target="_blank" rel="noopener"`), plus "having trouble? call
  <facility phone>". **The room URL appears in the HTML ONLY in this
  state** — assert that in tests (the URL-gating is the page's whole
  security story).
- closed/completed: "Buổi khám đã kết thúc" thank-you body, NO summary
  (that is the family page's job), no room URL.
Server QWeb, self-contained inline CSS, flat mono, inline currentColor
SVG, NO emoji, vi-first with en gloss, phone-first layout.

### 2.4 Nurse side

- **PWA**: `telehealth.js` + small CSS via shell inherit (after
  router.js / after health.css, `?v=#{pwa_asset_version}`). Reuse the
  daystrip reveal-row seam: for cards where the today payload's
  `location === 'online'`, inject a "Vào video (Join video)" action.
  Tapping calls a NEW endpoint in THIS module
  `GET /health_pwa/api/fso/<id>/tele/join` (auth='user', same
  session-auth style as the module's PWA endpoints — inspect
  health_workflow_auto/controllers/onetap_api.py for the auth/access
  precedent) which returns `{url}` only when the caller is assigned
  staff and state is in_progress-or-confirmable; JS `window.open`s it.
  Do NOT put the room URL in any cached/offline payload.
- **Backend**: a "Join Video" button on the FSO form (invisible unless
  session open) + a sessions list/form view under the Workflow/Bookings
  menu area (read ops+, no unlink below manager; catchment rule pair —
  family-link security template).

### 2.5 EVV exemption fix

Inherit the EVV FSO compute so online visits verify on event presence
alone (geofence treated as satisfied; distance data stays recorded).
Keep it surgical: override `_compute_evv_status` (or the smallest
helper it calls), branch ONLY on `service_location == 'online'`.
Re-run `/health_evv` to prove nothing else moved.

## 3. Config (`res_config_settings.py`, self_booking pattern)

- `health_telehealth.video_base_url` (default `https://meet.jit.si`)
- `health_telehealth.zns_template_join` (empty default → no rows)
- `health_telehealth.enabled` (Boolean default **True** — session
  creation is inert paperwork; sends still ride
  `health_messaging.enabled`/`dry_run` which are OFF/dry on vietuat)

## 4. Tests (`tests/test_telehealth.py`)

1. Confirm an online FSO → session pending, FSO.online_meeting_url
   filled, ZNS row `simulated` under dry_run (and: empty template
   param → zero rows; enabled=False → skipped) — rails matrix.
2. Confirm a HOME FSO → no session, no rows (scoping).
3. Double confirm → one session, one row (dedup + search-first).
4. Waiting-room page: pending render has date/staff and does NOT
   contain room_slug/room_url (assert absence — the gate); start
   service → page contains the Join URL; complete → closed body, URL
   gone again; bogus/expired/cancelled → identical neutral page
   (HTTP render path, not flags — the family-phase lesson).
5. Meta refresh present in pending AND open-only states per your
   choice — assert whichever you implement.
6. `/health_pwa/api/fso/<id>/tele/join`: assigned nurse in_progress →
   url; unassigned user → denied/empty; draft state → empty.
7. EVV: online FSO with checkin+checkout outside geofence →
   `evv_verified` True; home FSO unchanged (re-run `/health_evv`).
8. Consent check logged at confirm (a health.consent.check.log row
   exists; log-only, confirm succeeds without consent).
9. Timezone: 02:00 UTC + Asia/Ho_Chi_Minh → page/params say 09:00.
10. Hook resilience: patch `_send_join_zns` to raise → confirm still
    succeeds.

Fixtures per conventions §6 + ledger §5.17's matrix-isolation note.
HttpCase present ⇒ NO `--no-http`; use the port-wait loop after stop
(`for i in $(seq 1 30); do ss -ltn | grep -q ":8069 " || break;
sleep 2; done`) — odoo-bin logs to the conf logfile, read results from
/var/log/odoo/odoo-server.log and check the timestamp is YOUR run.

## 5. Deploy & verify

- `-i health_telehealth -u health_pwa --test-tags
  /health_telehealth,/health_evv,/health_pwa_daystrip` (you touch the
  EVV compute and share the PWA card row with daystrip — prove both).
- **Browser QA on care.biztinct.com REQUIRED, with committed evidence
  this time**: save screenshots (or a screenshots.md with exact
  descriptions if binaries are unwanted in git) covering: the Join
  action on an online card, the waiting-room page pending → open flip
  (start the demo visit), the Join button target. Note: real Jitsi
  loading is NOT required — asserting the correct meet URL opens is
  enough on UAT.
- Live demo (safe under dry_run): book a telemedicine FSO for a demo
  client (861-864), confirm → show session + simulated row + waiting
  room; start → show the page flip + PWA join; complete → closed page.
  Leave `health_messaging.enabled` OFF; state final switch positions.
- health_pwa diff = version bump ONLY (paste `git diff --stat`).
- vi.po, conventions §8, commit+push on 19.0.

## 6. Report-back extras

(a) final switch/param positions incl. video_base_url; (b) demo ids +
page text at each state + the exact room URL produced (redact the slug
tail); (c) the cancellation seam you hooked and why; (d) the EVV
compute override diff (prove surgical); (e) the tele/join endpoint's
auth/access check summary; (f) any new ledger-grade gotcha (explicitly
flagged).
