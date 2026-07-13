# Design: Patient Portal ("My Care") — tokenized, per-patient

**Stream:** Phase 4 of the FHIR/VNeID/Circular-13 arc, but really its own product
surface. **Designer + implementer:** Opus in-session, with the retained review
gate. Read `docs/strategy/HANDOVER-CONVENTIONS.md` first. **User decisions
(2026-07-13):** auth = **tokenized "My Care"** (no login); **BHYT/4210 deferred**;
MVP = **all four** areas (visits, records, consents, booking/messages/balance).

## §0 What this is (and is not)

A single **per-patient** tokenized page — `/my/care/<token>` — that unifies the
patient-facing experience. Distinct from the existing **per-visit** tokens
(family_link/self_booking/telehealth): those show one visit to whoever holds a
visit link; this is the **patient's own** standing access to *their whole care
record*. The token (sent to the patient's phone via ZNS/SMS) IS the
authentication — possession = the patient (or their delegate).

**NOT in scope:** patient `res.users`/passwords, Odoo portal `/my/*` users,
VNeID/Zalo OIDC (deferred — the tokenized model is the upgrade base for them
later), BHYT/4210, FHIR profile pack.

## §0.1 Security model (binding — this exposes a whole record via a bearer token)

- Token: `secrets.token_urlsafe(32)` (256-bit), **unique index materialized in
  `init()`** (§5.1), `copy=False`, never logged (clone family_link:59-63).
- State: `active | revoked`; ops can **revoke** and **rotate** (rotate = new
  token, old dies). Optional `expires_at` (config TTL, default none = standing
  link; render-time check like family_link `_is_expired`).
- **Rate limiting**: `gateway.rate.counter` per-IP AND per-token (clone
  family_messages dual throttle) — this page is more sensitive than a per-visit
  page, so throttle harder.
- **Scope**: the token resolves to exactly ONE `patient_id`; every read is
  `sudo()` but **domain-scoped to that patient_id** — never a global query. No
  cross-patient traversal.
- **PHI discipline**: no PHI in logs; neutral pages for revoked/expired/unknown
  tokens (no existence oracle, clone family_link's neutral-page rule).
- **Audit**: every portal hit logs to `health.portal.access.log` (append-only:
  token ref, patient, section, ip, ts) — the "who saw the record" trail.
- **Records sensitivity (Phase 4B)**: showing full finalized notes via a bearer
  link is the patient's right to their own record, BUT consider a lightweight
  **phone-OTP step** gating the records section (deferred call — 4A ships
  without it; revisit at 4B). Draft notes are NEVER shown (only `emr_state=final`).
- **Consent grant/withdraw (Phase 4C)** is a real mutation from a public page —
  POST with the token, `self_granted=True`, `method='digital'`, logged; a
  withdraw immediately affects the Phase-2 FHIR consent gate.

## §1 Verified plumbing facts (do NOT re-derive)

1. Tokenized-page precedent to CLONE: `health_family_link/controllers/
   family_public.py:33-46` (`@http.route('/family/visit/<string:token>',
   auth='public', csrf=False)`, GET, rate-limit then render). Model
   `health_family_link/models/health_family_link.py`: token gen :59-63
   (`secrets.token_urlsafe(24)`, unique index), `_is_expired` :171-173 (render-
   time), state rendering :168-277 (neutral pages, given-name-only staff,
   wall-clock dates, PHI-sanitized 200-char summary).
2. Rate limiter: `gateway.rate.counter` (health_api_gateway) keyed per-IP;
   family_messages uses dual per-IP + per-token throttle (clone that).
3. Records: `health.clinical.note.emr_state` ('draft'|'final', health_emr).
   Finalized notes carry signed_by_id/signed_datetime/content_hash. FSO link:
   `order_id.patient_id`. The DocumentReference serializer
   (health_fhir_core) already compiles a note into a text document — reuse its
   `compile_text(note)` for a download.
3b. Patient's notes: `res.partner` → `health.fieldservice.order` (patient_id)
    → `clinical_note_ids`. Query notes by
    `[('order_id.patient_id','=',pid),('emr_state','=','final')]`.
4. Consent: `health_consent` — `check_consent(partner, type)`,
   `consent_type` ∈ {service, data_sharing, photography, emergency_treatment,
   marketing}; grant via `action_grant()`, withdraw via `action_withdraw()`;
   `self_granted` Boolean, `method` ∈ {verbal, written, digital_signature}.
   Capture is staff-only today (CAPTURE_GROUPS) — 4C adds the patient-facing
   grant/withdraw (self_granted, method='digital_signature').
5. Visits: `health.fieldservice.order` — name, patient_id, state
   (draft→…→closed/cancelled), scheduled_datetime, lead_staff_id,
   facility_id, actual_start/end. Clone family_link's per-state rendering but
   over the patient's WHOLE timeline (upcoming = future/confirmed/assigned;
   history = completed/closed).
6. Booking: `health_self_booking` — `/booking/self/<token>` (invite model
   `health.selfbook.invite`). Messages: `health_family_messages`
   (`/family/visit/<token>/message`, `health.family.thread`). Balance:
   `health.service.package` (patient_id, total_services, remaining_services,
   state). 4D surfaces/links these in the hub.
7. NO existing patient login / OAuth-authcode / auth_oidc / auth_oauth /
   health_portal module. gateway OAuth is client-credentials only. So the
   portal is greenfield on the tokenized pattern.
8. `res.partner` patient fields: is_patient, patient_code, first/last/middle
   name, mobile, birth_date, gender, primary_facility_id, national_id.
9. New module conventions (§4): `health.*`, mail.thread on the access model
   (token issuance/revoke audit), catchment rule N/A (public controller reads
   sudo scoped by token→patient). Version 19.0.1.0.0. Ship i18n/vi.po. Flat
   mono colors, hf-wt-ico or inline (public page — self-contained CSS, VN-first
   copy). §5.1 unique index in init().
10. ZNS send (issuing the token link to the patient): `health_messaging` /
    `health_zalo` ZNS — **BUT safety rails: health_messaging.enabled=False,
    dry_run=True on vietuat**; the issue-token action must respect the same
    dry-run discipline (build the link, don't actually send on vietuat).

## §2 Architecture — module `health_portal`

- **`health.portal.access`** (mail.thread): patient_id (req, unique — one
  standing token per patient), token (init() unique index), state, expires_at
  (optional), last_access_datetime, access_count; actions
  `action_rotate_token`, `action_revoke`, `action_reactivate`; `_portal_url()`
  compute; a backend action on the patient form "Issue/Copy My Care link"
  (dry-run-safe — shows/copies the URL; ZNS send gated by the messaging rails).
- **`health.portal.access.log`** (append-only, no unlink): access_id, patient,
  section, ip, ts. §5.32-style — write via sudo from the controller.
- **Controller `PortalController`** (`controllers/portal_public.py`,
  auth='public', csrf=False): `_resolve(token)` → access record or neutral
  page; rate-limit; log; render. Routes per sub-phase (below). Shared
  `_patient_ctx(access)` builds the safe display context (sudo, scoped to
  patient_id, PHI-sanitized).
- **Templates** (`views/portal_templates.xml`): a hub shell + per-section
  fragments; self-contained CSS (mono, VN-first), responsive, no external
  assets.
- **Sub-phases:**
  - **4A (this build)** — module + access model + log + `/my/care/<token>`
    hub + **My Visits** (upcoming + history timeline) + backend issue/rotate/
    revoke + tests. The security foundation everything else rides on.
  - **4B — My Records**: `/my/care/<token>/records` list of finalized notes +
    `/my/care/<token>/records/<note_id>` view + `.../download` (text/PDF via
    the DocumentReference compile_text). emr_state=final only. (Revisit OTP.)
  - **4C — My Consents**: `/my/care/<token>/consents` view + POST grant/withdraw
    (self_granted, digital). Feeds the Phase-2 gate.
  - **4D — Book/Messages/Balance**: surface self_booking invite (or issue one),
    family messages thread, and package balance in the hub.

## §3 Phase 4A detail + tests

Model `health.portal.access`:
- `_sql`-free unique index on token in `init()` (§5.1); also a unique index /
  constraint on patient_id (one standing access per patient — rotate replaces).
- `action_rotate_token`: set token = new urlsafe(32) (allowed; token not
  content-locked); keep same record. `action_revoke`: state='revoked'.
- Token default `secrets.token_urlsafe(32)`, copy=False, index, groups-limited
  read (ops+).
Controller:
- `GET /my/care/<string:token>`: rate-limit (per-ip + per-token); `_resolve`;
  if not active/expired → neutral page (HTTP 200, generic "link not available",
  no oracle); else log access(section='hub') + render hub with My Visits.
- `_visits_ctx(patient)`: sudo search FSOs `[('patient_id','=',pid)]` split
  upcoming (state in confirmed/assigned/in_progress AND scheduled>=today) vs
  history (completed/closed), given-name-only staff, wall-clock datetimes,
  facility phone. NO clinical PHI on the visits list (that's 4B/records).
Backend: patient form button "Issue My Care link" → create-or-get access →
return the URL (dry-run-safe; no auto-send on vietuat).

**Tests (health_portal/tests, mix TransactionCase + HttpCase):**
1. token unique + `init()` index exists; one access per patient (rotate keeps
   the record, changes token; old token 404s).
2. `GET /my/care/<good token>` → 200, shows the patient's upcoming + history
   visits; a DIFFERENT patient's visits are NOT present (scope isolation).
3. revoked token → neutral page (200, no PHI, no "exists" oracle);
   unknown/garbage token → same neutral page.
4. expired token (backdated expires_at) → neutral page.
5. rate-limit: N rapid hits from one IP → throttled (mirror family_link's rate
   test if one exists).
6. access log row written per hit (append-only; unlink blocked).
7. no clinical PHI (diagnosis/notes) leaks onto the visits page (assert absent).
8. issue-link backend action creates/returns the access + URL; does NOT send
   ZNS on vietuat (rails).

Browser QA (chrome-devtools, care.biztinct.com): issue a link for a demo
patient, open `/my/care/<token>`, verify the visits render, mono styling,
VN copy, mobile width, console clean; revoke → neutral page. **Revert QA state
(fresh cursor §5.34): revoke/delete the demo access token after.**

## §4 Deploy
Conventions §2. `-i health_portal`. Tags `/health_portal`. HttpCase ⇒ no
`--no-http`. Result from log, login 200, and hit `/my/care/<token>` → 200.
Safety rails (fact-10) binding — no real ZNS sends.

## §5 Sub-phase plan (context)
4A foundation+visits (this) → review → 4B records → 4C consents → 4D
booking/messages/balance. Each: build → deploy → independent review → next.
Later (deferred): Zalo login on top of the token model; VNeID OIDC when the
govt endpoint opens; records-section OTP; BHYT/4210; FHIR profile pack.
