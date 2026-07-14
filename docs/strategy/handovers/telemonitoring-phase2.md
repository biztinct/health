# health_telemonitoring — Phase 2: Device Hub (registry + ingestion API) + vitals-FAB reachability rider

Phase 2 of the telemonitoring → twin arc. Phase 1 (NEWS2 + triage inbox) is
live and reviewed (report: `docs/strategy/reports/telemonitoring-phase-report.md`).
This phase gives home devices (BP monitors, pulse oximeters, glucometers,
scales — via vendor clouds/aggregator partners) a **server-side door** into
the same `health.observation` stream, where the Phase 1 engines
(thresholds → inbox mirror, NEWS2, nightly trends) pick readings up with
**zero extra wiring**. Plus one small PWA rider fixing a Phase 1 review
finding: the vitals FAB is unreachable from the modal-first Today flow.

Read `HANDOVER-CONVENTIONS.md` first (§2 deploy, §3 PWA bump — the RIDER
makes this phase PWA-facing, §5 ledger esp. §5.36/§5.37, §6 fixtures,
§7 interfaces). All plumbing facts below are pre-verified — do not re-derive.

---

## 0. Scope and binding non-goals

**Build:**
1. `health.monitor.device` — per-patient device registry.
2. `POST /api/v1/telemonitoring/readings` — gateway-authenticated,
   scope-gated, rate-limited, **idempotent** batch ingestion that maps
   readings to `health.observation.create_coded` / `create_panel`.
3. New scope seed `telemonitoring.ingest` (data row — no gateway code edit).
4. Per-device daily flood cap (config param).
5. Backend views: device registry under the Telemonitoring menu + a
   Devices smart-button/tab on the patient form.
6. **Rider (PWA):** make the vitals entry sheet reachable from the shared
   booking modal for in-progress visits (§6).
7. Tests + vi.po additions. Module → 19.0.2.0.0.

**Binding NON-goals:**
- NO device-to-server BLE/LoRa protocol work, NO store-and-forward gateway
  hardware, NO vendor-specific adapters (partners POST our JSON).
- NO wearable-triggered auto-dispatch/booking hook (Phase 3).
- NO changes to the Phase 1 engines (scoring/alerts/trends untouched).
- NO new health_vitals PYTHON edits; NO health_api_gateway code edits
  (scopes are data rows; auth helpers are imported).
- NO ZNS/SMS/email; messaging rails stay disabled. NO pip installs.
- NO FHIR Device resource (later).

---

## 1. Verified plumbing facts (do not re-derive)

**Gateway (health_api_gateway):**
- `_gateway_authenticate(request)` → resolves Bearer: `hg_`-prefixed opaque
  tokens (SHA-256-hashed at rest, `gateway.token.resolve`) OR Odoo API keys;
  returns user + scope set — `controllers/gateway.py:104-164, 288-311`.
  Token issue via client-credentials `POST /oauth/token`
  (`controllers/oauth.py:49-102`); granted = requested ∩
  `gateway.oauth.client.allowed_scope_ids` (`oauth.py:86-93`); lifetime
  `client.token_lifetime or 3600` (`models/gateway_token.py:55-56`).
- Scope check: `_scopes_satisfied(required, granted)` — any-of, SMART
  wildcard support (`gateway.py:212-224`).
- Scope catalog: `api.key.scope` rows (`models/api_key_scope.py`) — `code`
  unique. Existing codes: `patient.read`, `booking.read`, `booking.write`,
  `pwa.read`, `pwa.write`, `system/<Type>.read`. Clients pick scopes via
  `allowed_scope_ids` m2m; API keys via `res.users.apikeys.scope_ids`.
- Rate limit: `env['gateway.rate.counter'].hit(key_ref)` →
  `(allowed: bool, retry_after: int)`; atomic ON CONFLICT upsert; 1-minute
  window; limits from params `gateway.rate_limit_per_min` (120) /
  `_burst` (240) (`models/gateway_rate_counter.py:37-70`).
- Response envelope everywhere: `{'success', 'timestamp', 'data'|'error'}`;
  errors: 401 no/bad token, 403 scope, 404, 422 validation, 429 (+
  Retry-After) — see any endpoint in `controllers/api_v1.py` (12 routes,
  `:130-756`); representative full shape at `:164-223` (auth → scope →
  rate → `request.update_env(user=user.id)` → ORM → audit → serialize).
- After `update_env(user=...)` the ORM runs as the SERVICE USER — record
  rules apply. The service user needs read on patients/devices in scope;
  ingestion creates observations **sudo** with explicit patient scoping
  (see §2.3 — mirrors the PWA vitals controller, which also creates via
  model-level API after its own access check).

**Idempotency precedent (clone this):** `health.pwa.action.receipt`
(`health_pwa/models/pwa_action_receipt.py:1-54`) — unique index
`(fso_id, action_type, client_action_uuid)`; on replay, the stored
`result_json` is returned verbatim; rows immutable; 90-day GC cron.

**Observation API (conventions §7, verified):**
`create_coded(patient_id, loinc_code, value, uom=None, fso_id=None,
effective_datetime=None, performer_id=None, source='manual', note=None)`
(`health_vitals/models/health_observation.py:352`); `create_panel(client_id,
panel_type_code, components, **common)` — `common` whitelist includes
`effective_datetime`, `device`, `method`, `performer_id` (`:398`, whitelist
`:415`). `source` is NOT a stored field — folded into a chatter note
(`:387-390`); `device` IS a Char field on observation (`:68`).
Plausible-range validation happens inside create (`_check_value`) —
out-of-range device readings raise ValidationError; catch per-item.
**Phase 1's create() hook auto-fires thresholds + NEWS2 on every
observation — device readings get the full engine for free.**
- There is NO existing device/equipment model anywhere in health_* —
  greenfield is correct.
- EVV hash-chain (`health_evv/models/health_evv_event.py:256-331`) exists
  as an audit precedent — NOT needed here (observations are already
  append-only evidence; do not build a chain).

**Phase 1 module facts:** `tm_config.get_bool/get_int/get_float`
(`health_telemonitoring/models/tm_config.py`) — reuse for new params;
Telemonitoring menu root `health_telemonitoring.menu_telemonitoring_root`
(under `health_base.menu_healthcare_clinical`); catchment ir.rule pattern in
`security/telemonitoring_security.xml`; §5.36 settings-toggle rule — any new
default-True Boolean setting MUST ride the existing `set_values()` override.

**PWA modal seam (for the rider):**
- FAB today: renders only when `location.hash` matches `#\/orders\/(\d+)`
  (`health_vitals/static/src/js/vitals-components.js` — `currentFsoId()` /
  `syncFab()` near the file end, `:469-497`). The modal-first flow keeps
  the hash at `#/today`, so the FAB never shows there (review finding).
- The shared booking modal: `openBooking(fsoId)` bridge
  (`health_pwa/static/src/js/app.js:300-310`), modal content node
  `.booking-detail-modal-content` (`app.js:3524`). The modal does NOT
  expose the fso id in the DOM.
- Proven detection seam to CLONE: `health_pwa_family/static/src/js/fammsg.js`
  wraps `window.fetch` to spot the booking-detail request + id
  (`fammsg.js:76-99`) and re-renders on modal open/close via a
  MutationObserver (`fammsg.js:338-342`). Verify the exact detail-endpoint
  URL and the status field name in its response before coding; gate the FAB
  on the in-progress status exactly as the modal's own buttons do.

---

## 2. Architecture

`health_telemonitoring` 19.0.2.0.0; `depends` += `health_api_gateway`.

### 2.1 `health.monitor.device` (models/health_monitor_device.py)

- `name` Char required (e.g. "Omron X5 — bà Lan"); `client_id` M2O
  res.partner required, index, ondelete='restrict', domain is_patient.
- `device_type` Selection: bp_monitor / pulse_oximeter / thermometer /
  glucometer / scale / wearable / other (required, index).
- `external_id` Char required — the id the PARTNER sends per reading
  (vendor device serial/uuid). Unique per client is not enough: **unique
  index on (external_id) alone** in `init()` (§5.1 pattern) — partners
  address devices globally.
- `vendor` Char, `model` Char, `notes` Char.
- `state` Selection active/suspended/retired, default active, index,
  tracking. Only `active` devices ingest; suspended/retired → per-item
  rejection (`device_inactive`).
- `reading_count` Integer compute (search_count on observations where
  `device` == the marker string — see §2.3 provenance), non-stored.
- `last_reading_at` Datetime, readonly — engine-stamped on each accepted
  batch (sudo write).
- `catchment_province_id` computed+stored from client (clone Phase 1
  compute), `company_id`. `_inherit = ['mail.thread']`, tracking on state.
- Unlink guard: only admin/owner groups (clone Phase 1 shape) — devices
  with history are retired, not deleted.

### 2.2 Ingestion receipt (models/health_device_receipt.py)

`health.device.receipt` — clone of `health.pwa.action.receipt`:
- `device_id` M2O health.monitor.device required index ondelete='cascade';
  `client_batch_uuid` Char(64) required; `state` Selection
  applied/partial/rejected; `result_json` Text; `received_at` Datetime.
- Unique index `(device_id, client_batch_uuid)` in `init()`.
- Immutable (write raises except system fields); GC cron: delete rows
  older than 90 days (daily, noupdate=1, config-gated
  `receipt_retention_days` default 90).

### 2.3 Ingestion endpoint (controllers/ingest.py)

`POST /api/v1/telemonitoring/readings` — `type='http'`, `auth='public'`,
`csrf=False`, methods POST only (match api_v1.py conventions exactly —
copy the decorator/envelope shape from a `booking.write` endpoint).

Flow (each step mirrors `api_v1.py:164-223`):
1. `_gateway_authenticate(request)` → 401; require scope
   `telemonitoring.ingest` via `_scopes_satisfied` → 403; rate limit via
   `gateway.rate.counter.hit('tm-ingest:%s' % user.id)` → 429 +
   Retry-After.
2. Parse JSON body:
   ```json
   {
     "device_external_id": "OMRON-X5-8842",
     "client_batch_uuid": "9f2c…",           // idempotency key, <=64
     "readings": [
       {"code": "bp_sys", "value": 132, "taken_at": "2026-07-15T02:10:00Z"},
       {"code": "bp_dia", "value": 84,  "taken_at": "2026-07-15T02:10:00Z"},
       {"code": "spo2_po", "value": 95, "taken_at": "2026-07-15T02:11:00Z"}
     ]
   }
   ```
   422 on missing device_external_id / client_batch_uuid / empty or
   non-list readings / batch larger than `ingest_max_batch` (param,
   default 50).
3. Resolve device sudo by `external_id`; unknown → **404 with a neutral
   error** (no existence oracle beyond the partner's own devices);
   non-active → 422 `device_inactive`.
4. Idempotency: search `health.device.receipt` for
   `(device_id, client_batch_uuid)`; hit → return stored `result_json`
   verbatim (200).
5. Flood cap: observations created for this device today ≥
   `ingest_daily_cap_per_device` (param, default 288 = one per 5 min) →
   429-style envelope, NO receipt (partner may retry tomorrow; log).
6. Per-reading mapping, each in its own `cr.savepoint()`:
   - `code` resolved via `health.vitals.type.get_by_code` (accepts short
     code or LOINC); unknown → item rejected `unknown_code`.
   - `taken_at` parsed ISO-8601 (clone `_parse_client_datetime` from the
     health_vitals controller); missing/unparseable → item rejected;
     REJECT readings with `taken_at` in the future (>10 min skew) or older
     than `ingest_max_age_days` (param, default 7) — stale dumps must not
     retro-trigger NEWS2 windows.
   - BP pairing: within one batch, `bp_sys`+`bp_dia` sharing the same
     `taken_at` are combined into ONE `create_panel('bp_panel', …)`;
     unpaired halves go through `create_coded` as-is.
   - Everything else: `create_coded(patient_id=device.client_id.id, code,
     value, effective_datetime=taken_at, source='device',
     note='device:%s' % device.external_id)` — and pass
     `device='%s (%s)' % (device.name, device.external_id)` via the panel
     `common`/observation vals so provenance lands in the observation's
     `device` Char (THE provenance marker; `reading_count` searches it by
     `('device', 'like', '(%s)' % external_id)`).
   - Creation runs **sudo** (service users have no clinical ACLs) — the
     patient scoping is the device registration itself (ops registered the
     device to that patient). `performer_id` = the authenticated service
     user (honest attribution).
   - ValidationError (plausible range) → item rejected `implausible`.
7. Build result: `{'accepted': n, 'rejected': [{'index': i, 'reason':
   '…'}]}`; create the receipt (state applied/partial/rejected as
   all/some/none accepted); stamp `device.last_reading_at`; return 200
   with the envelope.
8. Whole handler wrapped so unexpected errors → 500 envelope + log,
   NO receipt (retry-safe).

NEWS2/threshold/trend engines fire inside the observation create hooks —
do not call them explicitly. NOTE: device batches rarely satisfy the full
5-vital NEWS2 set; that is correct behaviour (no score), thresholds still
mirror per reading.

### 2.4 Scope + params + cron (data/)

- `api.key.scope` seed row: code `telemonitoring.ingest`, name
  "Telemonitoring: ingest device readings" (regular data).
- Params (noupdate=1): `ingest_max_batch=50`,
  `ingest_daily_cap_per_device=288`, `ingest_max_age_days=7`,
  `receipt_retention_days=90`.
- GC cron (daily, noupdate=1) for receipts.
- NO new settings-UI toggles this phase (avoids §5.36 surface); params only.

### 2.5 Security

- ACL: `health.monitor.device` — read nurse+, write head_nurse/ops-manager+
  (registration is an ops act), create ops-manager+, unlink admin/owner
  (guard §2.1). `health.device.receipt` — read ops-manager+, everything
  else engine-sudo only.
- Catchment + owner ir.rules for both models (clone Phase 1 file).

### 2.6 Views/menus

- Device list/form under Telemonitoring menu (sequence 30): list shows
  name/client/type/external_id/state/last_reading_at badges; form with
  state buttons (Suspend/Reactivate/Retire — plain state writes, ops-gated
  by ACL, chatter at bottom).
- Patient form: Devices tab/smart button via the existing
  health_telemonitoring partner-view inherit.
- Receipts: list view reachable from the device form (readonly).

---

## 6. Rider — vitals FAB reachable from the booking modal (PWA)

Fixes Phase 1 review finding (report Part 2, follow-up 1).

Sanctioned edit: `health_vitals/static/src/js/vitals-components.js` ONLY.
Clone the fammsg seam (`health_pwa_family/static/src/js/fammsg.js:76-99`
fetch-wrap + `:338-342` MutationObserver — verify the exact booking-detail
URL pattern and status field in that file before coding):

- Track `modalFsoId` + its status from the intercepted booking-detail
  response; on modal open with an IN-PROGRESS visit, render the existing
  FAB (reuse `syncFab`'s builder; FAB targets `modalFsoId`); on modal
  close or non-in-progress status, remove it unless the `#/orders/<id>`
  hash rule still applies (existing behaviour preserved).
- The entry sheet itself is unchanged; `VitalsEntrySheet.open(fsoId)`
  already takes an explicit id.
- z-index: the FAB (9300) must sit above the modal backdrop — verify
  visually and adjust the FAB's z-index if the modal stacks higher.
- health_vitals → 19.0.1.2.0; **PWA §3 bump** (read current from
  pwa_templates.xml, bump minor, all 5 places + manifest + the 3 pin
  tests in the same change).

### Sanctioned edits (exhaustive)

| Module | File | What may change |
|---|---|---|
| health_telemonitoring | (all) | Phase 2 content + version 19.0.2.0.0 |
| health_vitals | `static/src/js/vitals-components.js` | rider §6 only |
| health_vitals | `__manifest__.py` | version → 19.0.1.2.0 |
| health_pwa | `views/pwa_templates.xml`, `__manifest__.py` | §3 bump ONLY |
| health_pwa_daystrip / health_scribe / health_pwa_family | pin tests | pin value only |

NO edits to health_api_gateway, health_fieldservice, health_pwa JS,
health_vitals python.

---

## 3. Safety rails (binding)

Same as Phase 1: messaging rails stay disabled, no pip, real patient data
on vietuat, §5.34 fresh-cursor QA cleanup. Additionally: ingestion QA on
vietuat must use a QA patient + QA device you create AND delete; never
register a device against a real patient.

## 4. Tests (extend tests/, new file test_device_ingest.py; ~19 cases)

1. Registry: external_id unique index enforced; retire guard (nurse unlink
   raises; admin ok); catchment computed.
2. HttpCase auth ladder: no token → 401; token without
   `telemonitoring.ingest` → 403; with scope → 200. (Issue tokens via the
   gateway test fixtures — clone health_api_gateway's own test setup.)
3. Unknown device_external_id → 404 neutral; suspended device → 422.
4. Happy path: 3-reading batch → 3 observations, correct patient/type/
   value/effective_datetime, `device` Char carries name+(external_id),
   `last_reading_at` stamped, receipt state applied.
5. Idempotent replay: same (device, client_batch_uuid) POSTed twice →
   second returns byte-identical result_json, observation count unchanged.
6. BP pairing: bp_sys+bp_dia same taken_at → ONE panel + 2 children;
   unpaired bp_sys → standalone.
7. Partial: one implausible (HR 500) + one good → state partial, rejected
   list names index+reason, good one persisted.
8. Unknown code / missing taken_at / future taken_at / stale (>7d) →
   rejected with reasons.
9. Batch > ingest_max_batch → 422, no receipt.
10. Daily flood cap: cap param 2, third reading batch same day → 429
    envelope, no receipt, cap logged.
11. Threshold interplay: device reading breaching a health.vitals.threshold
    → is_abnormal + threshold inbox alert (Phase 1 mirror fires).
12. NEWS2 interplay: device batch completing the 5-vital set within the
    window → ews score created (proves the hook chain end-to-end).
13. Receipt immutability + GC cron removes >90d rows (config-gated).
14. Rate limiter path: monkeypatch `hit` to return (False, 30) → 429 +
    Retry-After.
15. Rider (HttpCase or JS-less check): with an in-progress FSO, the
    booking-detail fetch-wrap registers the FAB hook — plus pin tests
    updated. (UI behaviour itself is browser-QA'd at review.)
16. §5.32 discipline: pin off `timecard_sync_enabled` +
    `activity_on_critical` where not asserted.

## 5. Deploy / verify

Conventions §2. `-i` nothing (module exists): `-u health_telemonitoring,
health_vitals,health_pwa,health_pwa_daystrip,health_scribe,health_pwa_family`
with matching test-tags; HttpCase present ⇒ `--workers 0`, NO `--no-http`.
§5.1 smoke-check (browser, go/no-go): modal FAB appears on an in-progress
visit from the Today flow, sheet opens, NEWS2 chip still works; plus one
curl-level ingestion round-trip against a QA device (create → POST → verify
→ delete, fresh-cursor verified).

## 7. Report back

Standard §8 (report committed to
`docs/strategy/reports/telemonitoring-phase2-report.md`), plus: (a) PWA
version from→to, (b) the ingestion QA round-trip transcript (request +
response envelopes), (c) confirmation the QA device/patient/rows were
deleted and fresh-cursor verified, (d) exact URL pattern + status field you
found in fammsg.js for the modal seam (so the conventions can record it).

Kickoff line: `Implement the phase specified in docs/strategy/handovers/telemonitoring-phase2.md.`
