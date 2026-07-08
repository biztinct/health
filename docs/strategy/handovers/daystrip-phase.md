# Handover: Day-Strip + "On My Way" — `health_pwa_daystrip`

Read `docs/strategy/HANDOVER-CONVENTIONS.md` FIRST (definition of done =
its §8; gotcha ledger 16 entries — read all). This is the deferred
"day-strip redesign" phase, scoped to the vertical that pays twice:
the nurse taps **"Đang đến (On my way)"** on her next visit and the
family's public page flips to "nurse is on the way" with an honest ETA
— plus swipe verbs and a visual day strip that make the Today screen
faster between visits. UX-side sibling of health_pwa_ergo; EVV-side
sibling of the family link.

## 0. Scope (one new module `health_pwa_daystrip`)

1. **`travel_start` / `travel_cancel` EVV event types** (selection_add
   inherit) posted from the PWA through the EXISTING EVV endpoints and
   offline queue.
2. **Family page "on the way" state**: `health.family.link`
   `_page_context()` inherit + template inherit — upcoming visit with a
   fresh `travel_start` renders "Điều dưỡng đang trên đường" and, when
   computable, "khoảng X phút" from haversine distance.
3. **PWA Today-screen layer** (`daystrip.js` + `daystrip.css`, shell
   inherit): "On my way" verb on today's cards, swipe-to-reveal action
   row (Call / On my way), and a horizontal day-strip timeline header
   above the existing day list with a now-marker.

⇒ **PWA bump required: 1.6.0 → 1.7.0** in all 5 places + manifest
(conventions §3); deploy health_pwa alongside.

**Non-goals (binding):** live GPS position streaming / watchPosition
(one tap = one event; no tracking); route optimization (health_routes
is a later module); replacing the today-view component or its
week/month views; any "nurse on the way" ZNS send (page-only this
phase); reading any eMAR/clinical data. **app.js edits are capped at
the two whitelisted one-liners in §2.5 — nothing else in app.js.**

## 1. Verified plumbing facts (do not re-derive; refs verified Jul 2026)

- **Today screen**: `today-view` component registered app.js:865;
  day-view booking list ~L3012–3071; card classes `.booking-card`,
  `.booking-card-header`, `.booking-patient-section`,
  `.booking-service-row`; header/segmented control `.bk-sub`,
  `.bk-today` L2977, `.bk-seg` L2992–2997. Bookings load via
  `loadBookingsForDate()` (app.js:1003–1060) from
  `GET /health_pwa/api/assignments/today?date=` (api.py:1398) — payload
  has `fso_id, patient_name, patient_phone, scheduled_time,
  scheduled_datetime, status, scheduled_duration, location, priority`.
- **Existing swipe precedent**: app.js:1473–1505 raw
  touchstart/touchend, 30px horizontal threshold, drives date
  prev/next. Quasar v2.14.0 full bundle from CDN
  (pwa_templates.xml:29); v-touch directives NOT in use.
- **EVV**: model `health.evv.event`
  (health_evv/models/health_evv_event.py) — `event_type` Selection at
  L71–77 (`checkin/checkout/signature/task_attest/photo`); hash chain
  = SHA256 canonical payload (L192–236) with `prev_hash` →
  `chain_hash`; the canonical recipe already includes `event_type` as
  data, so a NEW type does NOT break the chain. Geofence
  `_compute_distance` (L144–171) haversines device vs
  `partner_latitude/longitude` with `partner.geofence_radius_m`
  (default 150 m). Endpoints: `POST /health_pwa/api/fso/<id>/evv/event`
  (evv_api.py:195–237), batch `POST /health_pwa/api/evv/push`
  (L242–314, offline queue), config GET L142–190. `geo_utils` exposes
  `haversine_km`.
- **Family page**: pure server QWeb, no JS
  (health_family_link/controllers/family_public.py; `_page_context()`
  health_family_link.py:229–277 returns mode
  upcoming/arrived/completed/neutral). `_wall()` is the tz helper.
- **Shell-inherit precedent**: health_pwa_ergo
  `views/pwa_shell_inherit.xml` (css after health.css, js after
  router.js, `?v=#{pwa_asset_version}`); the SW runtime-caches
  versioned same-origin static — do not touch the SW.
- **Globals precedent**: `window.healthOnetap` (onetap-service.js) and
  `window.healthErgo` (ergo.js) — injected modules never edited app.js.
- **Ergo compat**: respect `--touch-target` (64px under
  `html.vu-glove`) and provide `html.vu-sunlight` rules (pure #000/#fff,
  2px borders, no shadows) for every new element.
- **Version places**: pwa_templates.xml L9 (`pwa_asset_version`), L246
  (manifest config `version`), L365 (`PWA_SW_VERSION`), L854
  (`CACHE_VERSION`) + the manifest per conventions §3.
- **FSO**: `estimated_end_datetime` = scheduled + duration
  (health_fieldservice_order.py:735–740); patient geo on
  `partner_latitude/partner_longitude`. FSO states have no
  'on_my_way' — and we are NOT adding one (an EVV event is the record).

## 2. Architecture

### 2.1 EVV event types (`models/evv_event.py`)

`selection_add` on `health.evv.event.event_type`:
`('travel_start', 'Travel Start')`, `('travel_cancel', 'Travel
Cancel')` (+ `ondelete: cascade` each). Then INSPECT AND REPORT:
(a) whether evv_api.py validates event_type against a hardcoded list —
if yes, extend it the least-invasive way (a module-level tuple you can
monkeypatch is not acceptable; an inherit hook or a controller inherit
is); (b) whether geofence evaluation / `distance_m` flags apply to all
types — travel events are posted AWAY from the patient's home, they
must not create geofence violations (expected: geofence logic is
checkin/checkout-scoped; verify, don't assume); (c) whether EVV stage
gates (FSO transitions requiring events) or any report/dashboard
enumerates event types (grep) — travel events must not satisfy or
break any gate. GPS lat/lng ride along like any event; chain and
canonical payload untouched by design (verify one live event's
`chain_valid`).

### 2.2 Family page "on the way" (`models/family_link.py` inherit)

Override `_page_context()`: call super; if `mode == 'upcoming'`, look
up the fso's latest `travel_start`/`travel_cancel` event (search
health.evv.event by fso_id, the two types, order desc, limit 1). If it
is a `travel_start` **fresher than 3 hours** (staleness guard — a
forgotten tap must not show "on the way" all day): set `mode:
'on_the_way'`, keep the upcoming fields, and add `eta_text`:
- both the event lat/lng AND patient partner_latitude/longitude
  present → `haversine_km` / 25 km/h urban speed → minutes, rounded UP
  to the nearest 5, floor 5 → "khoảng X phút (about X min)";
- otherwise `eta_text = ''` and the template shows only "Điều dưỡng
  đang trên đường (Your nurse is on the way)".
No fake precision, no new FSO fields, no polling model. `arrived` /
`completed` modes take precedence automatically (super returns them
before the hook looks at anything).

Template inherit on `health_family_link.family_page`: an
`on_the_way` block styled like the arrived block + — ONLY in this
mode — `<meta http-equiv="refresh" content="120"/>` so the family's
open tab updates itself (the page is JS-free; keep it that way).
Neutral-page behavior, rate limiting, and the consent gate are
untouched (schedule-level info only — same class as `upcoming`).

### 2.3 `static/src/js/daystrip.js` (window global, plain JS — no Vue)

`window.healthDaystrip` with three responsibilities:

1. **"On my way" verb**: on today's day list, each `.booking-card`
   whose status is confirmed/assigned gets the verb (see 2.5 for how
   cards are identified). Tap → `navigator.geolocation.getCurrentPosition`
   (graceful null on deny/timeout, 5 s cap) → POST the `travel_start`
   event through the SAME code path the EVV queue uses (reuse
   health_evv's queue/client JS if it exposes one — inspect
   evv-queue.js; if it does not expose a reusable API, post to
   `/health_pwa/api/fso/<id>/evv/event` online and fall back to the
   offline batch queue format). While active: the verb flips to "Hủy
   (Cancel)" → posts `travel_cancel`. One active travel per staff at a
   time (starting a second visit's travel auto-cancels the first —
   client-side, and state it in the report).
2. **Swipe-to-reveal**: horizontal swipe left on a card reveals an
   action row (Gọi (Call) via `tel:` from patient_phone, Đang đến (On
   my way)); swipe right or tap-outside closes it. Reveal-only —
   swiping must NEVER trigger an action directly (gloved-hand
   accidental swipes; glove mode doubles the reveal row height via
   `--touch-target`). Do not fight the existing L1473 date-swipe:
   card swipes must stopPropagation, and the reveal threshold must be
   ≥40px horizontal with vertical tolerance (scrolling wins).
3. **Day strip header**: a self-rendered horizontal timeline
   (06:00–20:00) inserted above the day list: one block per booking
   (positioned by scheduled_time/duration, colored by status token —
   flat mono, reuse `--st-*` vars), a "now" marker line, tap a block →
   smooth-scroll to its card. Data comes from the SAME
   `/health_pwa/api/assignments/today` response — do NOT re-fetch:
   read it by wrapping `window.fetch` for that URL (cache the last
   response) or a MutationObserver on the rendered list; report which
   seam you chose and why. Re-render on date change and on
   `visibilitychange`.

Self-contained DOM, inline currentColor SVG, NO emoji, vi-first labels
with en gloss, ergo-compatible CSS (explicit `html.vu-glove` /
`html.vu-sunlight` sections in daystrip.css — ergo.css precedent).

### 2.4 `views/pwa_shell_inherit.xml`

daystrip.css after health.css (after ergo.css if present — xpath on
health.css link works regardless of install order; verify cascade with
ergo installed), daystrip.js after router.js, both
`?v=#{pwa_asset_version}`.

### 2.5 The ONLY allowed app.js edits (health_pwa, whitelisted)

1. Add `:data-fso-id="booking.fso_id"` (and `:data-fso-status`) to the
   day-view `.booking-card` element (~L3027) so daystrip.js can address
   cards without guessing by index.
2. IF (and only if) the day strip needs the bookings array and the
   fetch-wrap seam proves unreliable: expose the today payload with a
   one-line `window.__pwaToday = data;` inside `loadBookingsForDate`.
Total ≤ 3 lines, each quoted verbatim in the report. Anything more =
redesign the approach, not the cap. Plus the version bump.

## 3. Module skeleton

`__manifest__.py` depends `['health_pwa', 'health_evv',
'health_family_link']`. No new models (two inherits), no crons, no
config params, no ACL additions (health.evv.event ACLs already cover
the new types; verify the PWA nurse user can post them through the
existing endpoint). `i18n/vi.po` for manifest + any server-rendered
strings (JS strings are vi-first hardcoded, PWA precedent).

## 4. Tests (`tests/test_daystrip.py`)

1. `travel_start` event via the EVV endpoint (HttpCase or direct model
   create mirroring health_evv's own tests): created, `chain_valid`,
   sequence/hash chain intact with mixed types
   (checkin→travel_start→checkout), no geofence violation flagged.
2. Stage gates / one-tap eligibility unaffected by travel events
   (complete an FSO that has travel events — reuse
   health_workflow_auto test helpers).
3. Family `_page_context`: upcoming + fresh travel_start →
   `mode='on_the_way'`; +3h-old travel_start → plain upcoming;
   travel_cancel after start → plain upcoming; in_progress FSO →
   'arrived' wins; ETA math (known lat/lng pair → expected "khoảng X
   phút", missing coords → empty eta_text).
4. Public page renders the on-the-way block + meta refresh ONLY in
   that mode (assert response body; neutral/consent behavior
   regression-checked by re-running `/health_family_link`).
5. Shell HttpCase: daystrip.css/js served at `?v=1.7.0`, version
   strings 1.7.0 (the 5-place guard), ergo assets still served.
6. Static CSS pin: `html.vu-glove` rules exist in daystrip.css.

Tag `post_install`; HttpCase present ⇒ NO `--no-http`.

## 5. Deploy & verify

- `-i health_pwa_daystrip -u health_pwa --test-tags
  /health_pwa_daystrip,/health_family_link,/health_evv` (you inherit
  into both — prove no regression).
- **Browser QA on care.biztinct.com is REQUIRED this phase** (ergo
  precedent): log in as a nurse on a phone-sized viewport; screenshot
  the day strip, the swipe reveal, the On-my-way verb before/after
  tap; then open the family token page for that FSO and screenshot the
  on-the-way state. Describe what a real phone should show.
- Verify offline: queue a travel_start with the network cut (devtools
  offline), reconnect, confirm it lands with `origin='offline_sync'`
  and a valid chain.
- health_pwa diff = version bump + the ≤3 whitelisted lines ONLY
  (paste `git diff --stat` + the exact lines).
- vi.po, conventions §8, commit+push on 19.0.

## 6. Report-back extras

(a) answers to the three EVV inspection questions in §2.1 (controller
whitelist / geofence scoping / hardcoded enumerations found); (b) the
data seam you chose for the day strip (fetch-wrap vs observer vs
window hook) and why; (c) the exact app.js lines changed (verbatim);
(d) screenshots list from browser QA; (e) how the one-active-travel
rule behaves across two open tabs; (f) any new ledger-grade gotcha
(explicitly flagged).
