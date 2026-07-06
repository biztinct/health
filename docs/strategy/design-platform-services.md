# health19 Platform Services Spec — EVV, API Gateway, FHIR Facade, Messaging Cascade, H0 Automations, PWA Additions

**Status:** implementation-ready. Target: Odoo 19 CE, branch `19.0`, DB `vietuat`.
**Consumers:** an LLM coding directly from this document. Every model/method/route name below is either (a) verified against the codebase (cited file+line) or (b) newly specified. Unverified assumptions are marked `VERIFY:`.

---

## 0. Verified codebase ground truth (read before coding)

| Fact | Source |
|---|---|
| FSO model `health.fieldservice.order`, states `draft/confirmed/assigned/in_progress/completed/completed_pending_invoice/cancelled/closed` via `_selection_fso_state` | `addons/health_fieldservice/models/health_fieldservice_order.py:45-55,941` |
| FSO action methods: `action_confirm_booking` (L2121), `action_start_service` (L2528, sets `actual_start_datetime`, state→`in_progress`), `action_complete_service` (L2756 — **requires** `clinical_notes_submitted` and `invoice_submitted`, splits full-time→`completed` vs part-time→`completed_pending_invoice` via `_check_invoice_creation_permission()`), `action_ai_assign_staff` (L2458), `action_assign_staff_to_fso(staff_id, assignment_role='support')` (L2489), `cancel_with_reason(reason_id, notes)`, `action_reschedule_from_wizard(...)` (L3069) | same file |
| FSO fields: `patient_id`, `sale_order_id`, `quote_state` (related `sale_order_id.state`, L1144), `quote_line_ids`, `invoice_id`, `actual_start_datetime`/`actual_end_datetime`/`actual_duration` (L1276-1286), `lead_staff_id`, `booking_timezone`, `reminders_sent` (Boolean, exists, unused — no reminder cron exists today), `nurse_notes`, `clinical_note_ids` | same file |
| Client GPS already exists: `res.partner.partner_latitude/partner_longitude` (Float, `health_base/models/res_partner.py:253`), auto-geocoded on write via `photon_geocode()`; helpers `haversine_km()`, `driving_distance(env,...)` in `health_base/models/geo_utils.py` | verified |
| `health.staff.assignment` (`health_staff_assignment.py:55`), `health.staff.assignment.engine` (L2261), `health.staff.availability.matrix` (`health_staff_availability.py:12`; fields `staff_id`, `availability_date` Date, `start_time`/`end_time` Float, `status`, `capacity`, `booked_count`, `remaining_capacity`, `conflict_detected`, `buffer_before/after`, `fso_id`, `assignment_id`, `catchment_province_id`) | verified |
| AI engine `health.ai.assignment.engine` (`health_ai_assignment_engine.py:28`): `_get_optimal_staff_suggestions(fso)` (L352), `_get_available_staff(fso)` (L393), `_calculate_assignment_confidence(appointment, staff)` (L419), `generate_optimal_assignments(target_date=None)` (L312), `optimize_daily_assignments(target_date=None)` (L542) | verified |
| `health.clinical.note` (`health_clinical_note.py:5`): `order_id`, `author_id`, `author_role`, `clinical_notes`, `diagnosis`, `treatment_performed`, `medications_prescribed`, `vital_signs`, `patient_condition_before/after`, `injection_count`, `medication_count`, `wound_count`, `iv_fluid_count`, `image_ids` | verified via PWA serializer `_serialize_clinical_notes` |
| PWA controller class `HealthPWAAPIController` in `health_pwa/controllers/api.py`; auth helper `_check_api_access(self)` (checks non-public user + `res.partner` read); envelope helper `_prepare_json_response(data=None, error=None, status_code=200)` → `{"success": bool, "timestamp": iso, "data": {...}}` or `{"success": false, "timestamp": iso, "error": "..."}` with CORS `*` headers; routes are `type='http'` + `csrf=False` (JSON body parsed manually with `json.loads(request.httprequest.data)`) except a few `type='jsonrpc'` | `api.py:29-63` |
| PWA endpoints (all `auth='user'`): `/health_pwa/api/patients` GET, `/patients/<int:patient_id>` GET, `/fso` GET, `/fso/<int:order_id>` GET, `/fso/<id>/update` jsonrpc POST, `/teams`, `/user/profile`, `/stats/dashboard`, `/fso/<id>/start` POST, `/cancellation_reasons`, `/fso/<id>/cancel` POST, `/fso/<id>/complete` POST, `/fso/<id>/complete_without_quote` POST, `/fso/<id>/clinical_notes` POST, `/fso/<id>/intake_notes` POST, `/fso/<id>/upload_image` POST, `/fso/<id>/quote` GET, `/products/catalog` GET, `/fso/<id>/quote/update` POST, `/fso/<id>/quote/save` POST, `/assignments/today` GET, `/config/clinic-phone`, `/fso/<id>/next_visit_status`, `/fso/<id>/no_future_visit` POST, `/fso/<id>/schedule_next_visit` POST, `/future_bookings`, `/current_user`, `/notifications/pending`, `/notifications/<id>/dismiss` POST, `/assignments/<id>/respond` POST, `/push/vapid-key`, `/push/subscribe` POST, `/push/unsubscribe` POST | `api.py` route grep, lines 131-2283 |
| Sync controller `health_pwa/controllers/sync.py`: `/health_pwa/sync/changes` GET (L103, per-model change feeds `_get_patient_changes`, `_get_fso_changes(since_datetime, user_teams)`, `_get_team_changes`, `_get_service_type_changes`, `_get_facility_changes`), `/health_pwa/sync/push` jsonrpc POST (L429 → `_process_fso_updates(fso_changes)`, `_process_patient_updates(patient_changes)`), `/sync/status` GET, `/sync/reset` jsonrpc, `/sync/debug` GET; envelope `_prepare_sync_response(data=None, error=None, status_code=200)`; access check `_check_sync_access()` | verified |
| PWA models: `health.pwa.push.subscription` (`get_subscription_info()`), `health.pwa.staff.notification` | `health_pwa/models/` |
| PWA JS: `static/src/js/app.js`, `router.js`, `utils/pwa-utils.js`, `utils/storage-manager.js`, `utils/sync-manager.js`. `VERIFY:` audit says Vue3+Quasar with PouchDB in storage-manager — match whatever store API `storage-manager.js` exposes when coding | dir listing |
| **PWA version bump (hard deploy rule):** version string `1.0.99` lives in `health_pwa/views/pwa_templates.xml` at L9 (`<t t-set="pwa_asset_version">1.0.99</t>`), L246 (`version: '1.0.99'`), L365 (`const PWA_SW_VERSION = '1.0.99'`), L854 (`const CACHE_VERSION = '1.0.99'`) (+ comment L851). Bump ALL occurrences on every deploy that touches PWA assets. Manifest `'version': '19.0.1.0.13'` should also be bumped | verified |
| health_pwa manifest depends: `base, web, mail, health_base, health_crm, health_fieldservice, health_invoicing` | `health_pwa/__manifest__.py:52` |
| ZNS send: `ZaloAPIClient.send_zns_notification(self, config, phone, template_id, template_data)` in `health_zalo/services/zalo_api.py:297-316` → `self._make_request('POST', 'message/template', config, data={'phone', 'template_id', 'template_data'})`. Config: `zalo.config` with `get_active_config()`, `get_valid_token()`, cron `cron_refresh_expiring_tokens` hourly. **No ZNS template model exists** (template ids are external). Webhook `/zalo/webhook` (jsonrpc POST, HMAC-SHA256 via `webhook_secret`) handles `user_send_*`, `follow`, `unfollow` via `zalo.message.handler.process_webhook_event(event_data)` | verified |
| VoIP24h: `VoIP24hAPI.initiate_call(self, from_extension, to_number)` → POST `{base}/calls/initiate` (`health_voip24h/services/voip24h_api.py:215-249`). **Click-to-dial only — no TTS/autocall.** Webhook `/voip24h/webhook` handles `call.started/answered/ended/missed`, `recording.available`. Models `voip.config`, `voip.call.log`, `voip.extension`, `voip.call.recording` | verified |
| SMS: no custom gateway; Odoo SMS IAP used once via `account_payment_notification` (`payment._message_sms_with_template()`); `sms.template` xmlid pattern exists there | verified |
| Red invoice: `account.move` extensions in `health_redinvoice/models/account_move.py`: `red_invoice_state` selection = `not_required/pending/issuing/issued/failed/cancelled` (default `pending`), `action_redinvoice_generate` (L80), `_redinvoice_maybe_issue` (L168), `_redinvoice_issue` (L179), `_prepare_redinvoice_payload` (L443), endpoint `f"{base_url}/InvoiceAPI/InvoiceWS/createInvoice/{company.red_supplier_tax_code}"` (L191; per project memory the working base needs the `/services/einvoiceapplication/api/` prefix + Basic Auth). Log model `redinvoice.request` (`redinvoice_request.py:12`): `move_id`, `company_id`, `state`, `endpoint`, `payload`, `response_code`, `response_body`, `error_message`, `retry_count`, methods `mark_sent/mark_success/mark_failed` | verified |
| Workforce: `pb_hr_workforce` — `hr.attendance.timecard` is a **TransientModel API** (`attendance_timecard.py:10`) reading **`hr.attendance`** (`check_in`, `check_out`, `worked_hours`, `employee_id`) + `hr.overtime.config` rules. Timecards are therefore fed by creating `hr.attendance` rows. Also `attendance_live.py`, `shift_planning.py` | verified |
| Kinship: `health.client.relation` (`health_crm/models/health_client_relation.py:16`) — `client_id` (M2O res.partner, domain `is_patient=True`), `representative_id` (M2O res.partner, domain `is_representative=True`), `role` Selection `caregiver/payer/referrer/emergency_contact/legal_guardian/client_representative`, `relationship_type` Selection (spouse/child/parent/...), `is_primary`, `can_make_medical_decisions`, `can_receive_medical_info`, `can_schedule_appointments` Booleans, `priority_order`, `active` | verified |
| CRM lead: `health_crm/models/crm_lead.py` inherits `crm.lead`; qualification/conversion methods = `action_convert_to_booking()` (creates FSO), `action_convert_to_client()` (marks qualified client), `action_log_as_lead()`, `action_schedule_follow_up()`; fields `service_interest`, `clinical_priority`, `contact_status`, `health_contact_outcome` | verified |
| FSO scheduling fields: `scheduled_datetime` (Datetime, required, UTC), `scheduled_date`/`scheduled_time` (computed local via `booking_timezone`), `scheduled_duration` (Integer minutes), `estimated_end_datetime`; patient address display = `patient_id.vietnamese_address`; assignments: `assignment_ids`, `lead_staff_id` (computed), `assignment_role` values `lead/support/doctor/consultant/specialist/trainee`; `health.staff.assignment` also has `actual_start_time`/`actual_end_time` + `assignment_status` (`assigned/confirmed/en_route/arrived/in_progress/completed/cancelled`); res.partner has `is_patient` flag | verified |
| Availability matrix public API: `health.staff.availability.matrix.book_staff_slot(staff_id, appointment_datetime, duration_minutes, fso_id=None, assignment_id=None)`; `status` value for free slots = `'available'` | verified |
| Consent: **no consent model exists anywhere** — §D ships the minimal hook | grep |
| Not installed on server: `authlib`, `fhir.resources` — must be pip-installed (add to deployment requirements before module install) | verified locally |

**Module install order:** `health_api_gateway` → `health_fhir_core`; `health_evv`, `health_messaging_auto`, `health_workflow_auto` independent (all depend on existing modules only + gateway where noted).

---

# A. `health_evv` — EVV-grade visit verification

## A.1 Manifest

```python
{
    'name': 'Health EVV — Electronic Visit Verification',
    'version': '19.0.1.0.0',
    'category': 'Healthcare',
    'depends': ['health_base', 'health_fieldservice', 'health_pwa'],
    'data': [
        'security/evv_security.xml',
        'security/ir.model.access.csv',
        'data/evv_cron.xml',
        'views/evv_event_views.xml',
        'views/fso_evv_views.xml',
        'views/res_partner_views.xml',
        'report/evv_verification_report.xml',
    ],
    'license': 'LGPL-3',
}
```

## A.2 Models

### A.2.1 `res.partner` (inherit) — geofence config
File: `models/res_partner.py`

| name | type | params | purpose |
|---|---|---|---|
| `geofence_radius_m` | Integer | default=150 | Geofence radius (metres) around `partner_latitude/partner_longitude` (existing fields, `health_base/models/res_partner.py:253`) |
| `geofence_enabled` | Boolean | default=True | Allow disabling per client (apartment towers with bad GPS) |

No new geocoding — health_base already geocodes on address write.

### A.2.2 `health.evv.event` — append-only, hash-chained
File: `models/health_evv_event.py`. `_name='health.evv.event'`, `_description='EVV Event'`, `_order='fso_id, sequence, id'`. **No mail.thread** (immutable, high volume).

| name | type | params | purpose |
|---|---|---|---|
| `fso_id` | Many2one | `health.fieldservice.order`, required, index, ondelete='restrict' | Visit |
| `sequence` | Integer | required, readonly | Position in the per-FSO chain (1-based, server-assigned) |
| `event_type` | Selection | `[('checkin','Check-in'),('checkout','Check-out'),('signature','Signature'),('task_attest','Task Attestation'),('photo','Photo')]`, required | |
| `event_datetime` | Datetime | required | Device wall-clock (UTC) at capture |
| `server_datetime` | Datetime | default=now, readonly | Server receipt time (drift detection) |
| `lat` | Float | digits=(10,7) | Device latitude at capture (0.0 allowed for `signature` if GPS off) |
| `lng` | Float | digits=(10,7) | |
| `accuracy_m` | Float | | GPS reported accuracy |
| `distance_m` | Float | compute=`_compute_distance`, store=True | Haversine metres from client geofence centre (uses `haversine_km` from `odoo.addons.health_base.models.geo_utils` × 1000) |
| `inside_geofence` | Boolean | compute, store=True | `distance_m <= partner.geofence_radius_m` and `accuracy_m <= 100` |
| `staff_id` | Many2one | `hr.employee`, required | Acting nurse (`request.env.user.employee_id`) |
| `device_uuid` | Char | size=64 | PWA-generated stable device id (localStorage) |
| `client_event_uuid` | Char | size=64, required, index | Client-generated UUIDv4 — idempotency key (unique constraint with fso_id) |
| `payload` | Json | | Type-specific payload (see A.4); for `signature`: `{signer_name, signer_relationship, attachment_id}`; for `task_attest`: `{task_code, done}`; for `photo`: `{attachment_id, caption}` |
| `payload_hash` | Char | size=64, required, readonly | SHA-256 hex of canonical payload (A.3) |
| `prev_hash` | Char | size=64, required, readonly | `payload_hash` of previous event in this FSO's chain; genesis = 64×'0' |
| `chain_hash` | Char | size=64, required, readonly, index | `sha256(prev_hash + payload_hash)` — the link value |
| `origin` | Selection | `[('online','Online'),('offline_sync','Offline Sync')]`, default='online' | |
| `chain_valid` | Boolean | default=True, readonly | Set False by validator when tampering detected downstream |
| `company_id` | Many2one | `res.company`, default=env.company | multi-company |

SQL constraint: `UNIQUE(fso_id, client_event_uuid)` (idempotent replay) and `UNIQUE(fso_id, sequence)`.

**Immutability:** override `write()` to raise `UserError` for any field except `chain_valid`; override `unlink()` to always raise. ACL grants no write/unlink to anyone (manager included) — corrections are made by appending a new event with `payload={'corrects': <event_id>, ...}`.

Methods:

```python
def _canonical_payload_bytes(self, vals):
    """json.dumps of {fso_id, event_type, event_datetime(iso, 'YYYY-MM-DDTHH:MM:SSZ'),
    lat(round 7), lng(round 7), accuracy_m(round 1), staff_id, device_uuid,
    client_event_uuid, payload(sort_keys)} with sort_keys=True, separators=(',',':'),
    ensure_ascii=False -> utf-8 bytes. THIS EXACT RECIPE IS MIRRORED IN JS (GeofenceService)."""

@api.model
def append_event(self, fso, vals, client_hash=None):
    """Locks the FSO row (SELECT ... FOR UPDATE via self.env.cr.execute on
    health_fieldservice_order id), reads last event (order sequence desc limit 1),
    computes sequence, payload_hash (from _canonical_payload_bytes), prev_hash,
    chain_hash, creates the row. If client_hash is provided and != payload_hash,
    create anyway but set payload['client_hash_mismatch']=client_hash and log warning
    (tamper-evident, not tamper-rejecting). Returns record. Idempotent: if
    (fso_id, client_event_uuid) exists, return existing record unchanged."""

@api.model
def validate_chain(self, fso):
    """Re-derive every payload_hash/prev_hash/chain_hash for fso's events in
    sequence order; returns {'valid': bool, 'first_bad_sequence': int|None}.
    Flags chain_valid=False (direct SQL UPDATE, bypassing write() guard) on bad tail."""
```

### A.2.3 `health.fieldservice.order` (inherit)
File: `models/health_fieldservice_order.py`

| name | type | params | purpose |
|---|---|---|---|
| `evv_event_ids` | One2many | `health.evv.event`, `fso_id` | |
| `evv_event_count` | Integer | compute | smart button |
| `evv_checkin_event_id` / `evv_checkout_event_id` | Many2one | compute (first `checkin` / last `checkout`) | |
| `evv_signature_attachment_id` | Many2one | `ir.attachment` | signature PNG |
| `evv_signer_name` | Char | | |
| `evv_signer_relationship` | Selection | `[('client','Client'),('family','Family Member'),('caregiver','Caregiver'),('other','Other')]` | |
| `evv_signed_at` | Datetime | | |
| `evv_chain_valid` | Boolean | compute=`_compute_evv_status`, store=True | full-chain validity |
| `evv_verified` | Boolean | compute, store=True | see rule below |
| `evv_verified_units` | Float | compute, store=True | verified service hours |

```python
@api.depends('evv_event_ids', 'evv_event_ids.inside_geofence', 'actual_start_datetime', 'actual_end_datetime')
def _compute_evv_status(self):
    """evv_verified = chain valid AND checkin event inside_geofence AND checkout
    event inside_geofence AND signature event exists.
    evv_verified_units = hours between checkin.event_datetime and
    checkout.event_datetime, rounded DOWN to 0.25h, capped at scheduled duration
    + 0.5h; 0.0 when not verified."""

def action_view_evv_events(self):  # smart button
def action_evv_report(self):       # returns report action (A.6)
```

### A.2.4 Wire into existing check-in/out
Inherit `action_start_service` and `action_complete_service` in the same file: after `super()`, if no `checkin`/`checkout` EVV event exists for the FSO and the call carries context keys `evv_lat/evv_lng/evv_accuracy/evv_device_uuid/evv_client_uuid` (set by the controller), call `health.evv.event.append_event`. Desktop-originated transitions produce **no** EVV event (EVV is a PWA-attested layer, not a state gate). **Do not** make `evv_verified` block completion in v1.

## A.3 Hash chain definition

- `payload_hash = SHA256(canonical_bytes)` — recipe in A.2.2.
- `prev_hash` = previous event's `payload_hash` (genesis `"0"*64`).
- `chain_hash = SHA256(hex(prev_hash) + hex(payload_hash))` (concatenate lowercase hex strings, utf-8).
- PWA computes `payload_hash` client-side (WebCrypto `crypto.subtle.digest('SHA-256', ...)`) over the identical canonical JSON and sends it as `client_hash`. Server recomputes; mismatch is recorded, never rejected (offline clocks/floats must not lose data).
- Offline queue keeps client-side `prev_hash` chaining *per device*; server chain is authoritative and re-sequences on sync (device order preserved by `event_datetime` then queue order).

## A.4 Controllers
File: `controllers/evv_api.py`. Class `HealthEVVController(http.Controller)`. **Match `health_pwa` conventions exactly**: `type='http'`, `auth='user'`, `csrf=False`, manual `json.loads(request.httprequest.data)`, respond via a copied `_prepare_json_response` (same envelope `{success, timestamp, data|error}`; import-reuse by instantiating `HealthPWAAPIController` is NOT allowed — duplicate the 20-line helper).

| Route | Method | Purpose |
|---|---|---|
| `/health_pwa/api/fso/<int:order_id>/evv/config` | GET | Geofence config for the visit |
| `/health_pwa/api/fso/<int:order_id>/evv/event` | POST | Append one event (online path) |
| `/health_pwa/api/evv/push` | POST | Batch offline queue flush |
| `/health_pwa/api/fso/<int:order_id>/evv/signature` | POST | Signature capture (creates attachment + event) |
| `/health_pwa/api/fso/<int:order_id>/evv/report` | GET | Verification summary JSON |

**`GET .../evv/config` response `data`:**
```json
{"fso_id": 123, "geofence": {"lat": 10.7769, "lng": 106.7009, "radius_m": 150, "enabled": true},
 "checked_in": false, "checked_out": false, "signature_done": false, "server_time": "2026-07-06T03:00:00Z"}
```
(lat/lng from `order.patient_id.partner_latitude/partner_longitude`; `enabled=false` also when coords are 0.)

**`POST .../evv/event` request:**
```json
{"event_type": "checkin", "event_datetime": "2026-07-06T02:58:11Z", "lat": 10.77691,
 "lng": 106.70092, "accuracy_m": 12.4, "device_uuid": "dev-abc", "client_event_uuid": "uuid4",
 "client_hash": "hex64", "payload": {}}
```
Response `data`: `{"event_id": 1, "sequence": 1, "chain_hash": "hex64", "inside_geofence": true, "distance_m": 23.5, "duplicate": false}`.
Side effects: `event_type=checkin` and `order.state in ('assigned','confirmed')` → call `order.with_context(evv_*).action_start_service()`. `checkout` does **not** auto-complete (completion needs notes/quote per `action_complete_service` L2756) — it only records; the PWA then drives the normal complete flow.

**`POST /health_pwa/api/evv/push` request:** `{"events": [<event dicts as above, each + "fso_id">]}` (≤200/batch). Response `data`: `{"accepted": n, "duplicates": n, "results": [{"client_event_uuid":..., "event_id":..., "sequence":..., "hash_match": true}]}`. Processes in `event_datetime` order grouped by fso; each event in its own savepoint; a failing event is returned in `results` with `"error"` and does not abort the batch.

**`POST .../evv/signature` request:** `{"image_base64": "<png b64, no data: prefix>", "signer_name": "Nguyễn Văn A", "signer_relationship": "family", "lat":..., "lng":..., "accuracy_m":..., "device_uuid":..., "client_event_uuid":..., "client_hash":...}`. Server: create `ir.attachment` `{name: f'EVV-Signature-{order.name}.png', res_model:'health.fieldservice.order', res_id, type:'binary', datas: image_base64, mimetype:'image/png'}`; write FSO signature fields; append `signature` event with `payload={'signer_name','signer_relationship','attachment_id','png_sha256'}` (`png_sha256` = SHA-256 of decoded bytes — binds image to chain). Response `data`: `{"attachment_id":..., "event_id":...}`.

**`GET .../evv/report` response `data`:** `{"verified": true, "verified_units": 2.0, "chain_valid": true, "events": [{sequence, event_type, event_datetime, inside_geofence, distance_m, accuracy_m, chain_hash}], "signature": {"signer_name":..., "relationship":..., "attachment_url": "/web/content/<id>"}}`.

## A.5 PWA client (see also §F)

`GeofenceService.js` (new, `health_pwa/static/src/js/utils/geofence-service.js` — served, like all PWA assets, with `?v=${CACHE_VERSION}`):

- Battery-conscious strategy (document as constants at top of file): (1) on shift start (assignments loaded), `navigator.geolocation.getCurrentPosition` with `enableHighAccuracy:false` every 3 min via `setInterval` while app foregrounded; (2) when coarse fix is within 400 m of the next booking's geofence centre → switch to `watchPosition({enableHighAccuracy:true, maximumAge:10000, timeout:15000})`; (3) drop back to coarse polling when >600 m (hysteresis) or after check-in completes; (4) stop watching entirely when checked-in and inside (resume 15 min before scheduled end for exit detection); (5) everything stops on page hide >10 min (no background geolocation in PWA — document limitation: prompts fire on next app open).
- Enter event → non-blocking prompt sheet "Bạn đã đến nơi — Check in?" (one tap). Exit after check-in → "Check out?" prompt. Never auto-submits without tap (VN labour + trust posture).
- Computes canonical JSON + SHA-256 exactly per A.2.2 recipe; queues to storage when offline.

`SignaturePad.vue` (new component): canvas 3:2, pointer events, undo/clear, `toDataURL('image/png')`, signer name input + relationship select (values mirror A.2.3), submits to signature endpoint; offline → queue as `signature` event with image stored in the local store.

## A.6 Report
QWeb PDF `report/evv_verification_report.xml`: `report_name='health_evv.report_evv_verification'`, model FSO. Contents: visit header (client, staff, scheduled vs actual), map-less event table (type, time, distance, in/out fence, accuracy), signature image, signer, verified units, chain status banner (green "Chain intact — N events" / red "TAMPER DETECTED at seq K"), footer: full `chain_hash` of last event as the visit's verification fingerprint.

## A.7 Cron
`data/evv_cron.xml`: `ir.cron` "EVV: nightly chain validation" — model `health.evv.event`, method:
```python
@api.model
def cron_validate_chains(self, days=2):
    """validate_chain() for every FSO having EVV events with write-window in last
    <days> days; on failure post a mail.activity to the FSO's facility manager
    (reuse pattern of HealthPWAAPIController._create_follow_up_activity, api.py:66)."""
```
Daily 02:30.

## A.8 Security
- Groups (`security/evv_security.xml`): `health_evv.group_evv_user` (implied by whatever nurse group gates PWA — `VERIFY:` reuse the group referenced in `health_pwa/security`, else `base.group_user`), `health_evv.group_evv_manager`.
- ACL: `health.evv.event`: user `1,1,0,0` (read, create only); manager `1,1,0,0` too (immutability absolute). Partner fields inherit partner ACLs.
- Record rule: EVV user sees events of FSOs where they are in `assignment_ids.staff_id` or `lead_staff_id` (mirror the FSO record-rule domain used by health_fieldservice — `VERIFY:` copy exact domain from `health_fieldservice/security`); manager: facility-scoped.

## A.9 Data seeds
None beyond cron. Default radius comes from field default; add `ir.config_parameter` `health_evv.default_accuracy_max_m = 100`.

## A.10 Acceptance criteria
1. Creating checkin→task_attest→checkout→signature events for an FSO yields sequences 1-4 and `validate_chain` returns valid.
2. Direct SQL `UPDATE health_evv_event SET lat=0 WHERE sequence=2` → nightly cron flags `chain_valid=False` on events ≥2 and FSO `evv_chain_valid=False`; report shows tamper banner.
3. Replaying the same `client_event_uuid` (double-tap / sync retry) returns the original event with `duplicate: true`; no second row.
4. Check-in 30 m from a client with radius 150 → `inside_geofence=True`; 300 m → False and FSO `evv_verified=False`.
5. Offline: 5 events queued in the PWA, flushed via `/evv/push` → all accepted, server sequences contiguous, `hash_match=true` for all.
6. Signature POST creates PNG `ir.attachment` linked to the FSO, sets `evv_signer_name/relationship/signed_at`, and the event payload `png_sha256` matches the stored file.
7. `evv_verified_units` for checkin 08:00/checkout 10:07 = 2.0 (floor to 0.25).
8. `write()`/`unlink()` on an event raises UserError for every user including admin.
9. Check-in via `/evv/event` on an `assigned` FSO transitions it to `in_progress` and sets `actual_start_datetime` (via existing `action_start_service`).
10. ORM `read` of events by a nurse not assigned to the FSO returns nothing (record rule).

## A.11 Integration points
- `health_fieldservice/models/health_fieldservice_order.py` → inherit `action_start_service` (L2528), `action_complete_service` (L2756) — append-only hooks, never change super behavior.
- `health_base/models/geo_utils.py` → `haversine_km` for `distance_m`.
- `health_base/models/res_partner.py` → existing `partner_latitude/partner_longitude` (L253) as geofence centre.
- `health_pwa/controllers/api.py` → envelope/auth conventions copied; `_create_follow_up_activity` pattern (L66) for tamper alerts.
- PWA sync: §F payload additions.

---

# B. `health_api_gateway` — keys/OAuth2, /api/v1, OpenAPI, webhooks, audit

## B.1 Manifest

```python
{
    'name': 'Health API Gateway',
    'version': '19.0.1.0.0',
    'depends': ['base', 'web', 'mail', 'health_base', 'health_fieldservice', 'health_pwa', 'health_invoicing'],
    'external_dependencies': {'python': ['authlib', 'pydantic']},
    'data': [
        'security/gateway_security.xml',
        'security/ir.model.access.csv',
        'data/api_scopes.xml',
        'data/gateway_cron.xml',
        'views/api_key_views.xml', 'views/oauth_client_views.xml',
        'views/webhook_views.xml', 'views/audit_log_views.xml',
    ],
    'license': 'LGPL-3',
}
```
Deployment: `pip install authlib pydantic` on UAT **before** upgrade (not currently installed — verified).

## B.2 Models

### B.2.1 `api.key.scope`
| name | type | params | purpose |
|---|---|---|---|
| `code` | Char | required, unique | e.g. `pwa.read`, `booking.read`, `booking.write`, `patient.read`, `webhook.manage`, `system/Patient.read` (FHIR scopes are rows here too — one namespace) |
| `name` | Char | required | |
| `description` | Text | | |

### B.2.2 `res.users.apikeys` (inherit)
Odoo 19 core model. Add:

| name | type | params | purpose |
|---|---|---|---|
| `scope_ids` | Many2many | `api.key.scope` | granted scopes |
| `facility_ids` | Many2many | `health.facility` | empty = all facilities the service user can see |
| `ip_allowlist` | Char | | comma-separated CIDRs; empty = any |
| `gateway_active` | Boolean | default=True | kill-switch without deleting |

`VERIFY:` Odoo 19 apikeys already carry `expiration_date` — do not duplicate; if absent add `expiry_date` Datetime. Keys authenticate as their owning **service user** (create one `res.users` per integration; `access_roles` record rules then apply naturally).

### B.2.3 `gateway.oauth.client`
| name | type | params | purpose |
|---|---|---|---|
| `name` | Char | required | |
| `client_id` | Char | required, unique, default=uuid4 hex | |
| `client_secret_hash` | Char | | passlib pbkdf2 via `odoo.tools.misc`/`crypt_context` pattern; secret shown once on create |
| `allowed_scope_ids` | Many2many | `api.key.scope` | |
| `user_id` | Many2one | `res.users`, required | service user the token acts as |
| `token_lifetime` | Integer | default=3600 | seconds |
| `jwks` | Text | | optional RFC7523 client-assertion public keys (SMART backend services, Phase 3) |
| `active` | Boolean | default=True | |

### B.2.4 `gateway.token` (opaque-token store — simpler than JWT for CE, no shared secret rotation problem)
| `token_hash` Char sha256(token) unique index | `client_id` M2O | `user_id` M2O | `scope_codes` Char (space-sep) | `expires_at` Datetime |

Method `@api.model def issue(self, client, scopes)` → returns raw token `hg_<48 hex>`; `@api.model def resolve(self, raw)` → (user, scopes) or None. Cron purges expired hourly (`data/gateway_cron.xml`).

### B.2.5 `webhook.subscription`
| name | type | params | purpose |
|---|---|---|---|
| `name` | Char | required | |
| `target_url` | Char | required | https only (constraint) |
| `event_codes` | Char | required | space-separated from catalog B.6 |
| `secret` | Char | required, default=32-byte urlsafe token | HMAC key |
| `active` | Boolean | default=True | |
| `failure_count` | Integer | default=0 | consecutive failures; auto-deactivate at 50 + activity to admin |
| `delivery_ids` | One2many | `webhook.delivery` | |

### B.2.6 `webhook.delivery`
| `subscription_id` M2O required | `outbox_id` M2O `integration.outbox` | `state` Selection queued/sent/failed/dead | `attempt` Integer | `next_attempt_at` Datetime | `response_code` Char | `response_body` Text(truncate 2k) | `signature` Char |

### B.2.7 `integration.outbox` (transactional outbox — architecture §6.1, slim v1)
| name | type | params | purpose |
|---|---|---|---|
| `event_code` | Char | required, index | e.g. `booking.completed` |
| `res_model` / `res_id` | Char / Integer | required | aggregate |
| `payload` | Json | required | serialized snapshot at emit time |
| `state` | Selection | `[('pending','Pending'),('dispatched','Dispatched'),('error','Error')]`, default pending, index | |
| `created_at` | Datetime | default=now | |
| `dispatched_at` | Datetime | | |

Written in-transaction by emitter hooks (B.6). Dispatcher cron every 1 min: `SELECT ... FOR UPDATE SKIP LOCKED` on pending rows (raw SQL), fan out to matching `webhook.subscription`s by creating `webhook.delivery` rows, then attempt HTTP (B.7).

### B.2.8 `api.audit.log` (PHI access audit)
`_name='api.audit.log'`, `_log_access=False` for volume; monthly-partition later, plain table now.

| name | type | params | purpose |
|---|---|---|---|
| `ts` | Datetime | default=now, index | |
| `auth_kind` | Selection | apikey/oauth/session | |
| `key_or_client` | Char | | apikey id or oauth client_id (never the secret) |
| `user_id` | Many2one | res.users | |
| `route` | Char | index | |
| `method` | Char | | |
| `status_code` | Integer | | |
| `latency_ms` | Integer | | |
| `ip` | Char | | |
| `resource_type` | Char | | e.g. `Patient`, `health.fieldservice.order` |
| `resource_ids` | Char | | comma ids returned/affected |
| `patient_ids` | Char | index | PHI subjects touched — **required for FHIR reads** |

ACL: read for `group_gateway_admin` only; create via sudo in middleware; **no write/unlink for anyone**. Never log request/response bodies.

## B.3 `@api_route` decorator + OpenAPI

File: `health_api_gateway/api_registry.py` (plain module, no ORM):

```python
API_REGISTRY = []  # [{path, methods, scopes, summary, request_model, response_model, tags, fn_qualname}]

def api_route(path, methods=('GET',), scopes=(), summary='', request_model=None,
              response_model=None, tags=(), auth='gateway'):
    """Wraps odoo.http.route(type='http', auth='none', csrf=False, methods=list(methods),
    save_session=False). The wrapper, in order:
      1. _gateway_authenticate(request)  -> (user, scopes, auth_kind, key_ref) or 401 envelope
      2. scope check (any-of `scopes`)   -> 403 envelope on failure
      3. rate check (B.8)                -> 429 + Retry-After
      4. request.update_env(user=user)   (switch to service user so record rules apply)
      5. parse body via request_model.model_validate_json() when POST/PUT (pydantic) -> 422 envelope on error
      6. call handler(controller, validated=obj, **params)
      7. envelope the return dict exactly like health_pwa: {'success': True, 'timestamp': iso, 'data': ...}
         (errors: {'success': False, 'timestamp': iso, 'error': msg}) — same shape as
         HealthPWAAPIController._prepare_json_response (api.py:41) so PWA client code ports 1:1
      8. write api.audit.log row (sudo, fresh cursor so it survives rollback)
    Registers metadata into API_REGISTRY at import time."""
```

Schemas are pydantic v2 classes in `health_api_gateway/schemas.py`. Generator `build_openapi(env)` walks `API_REGISTRY` → OpenAPI **3.1** dict (securitySchemes: `apiKey` header `Authorization: Bearer <odoo api key>` and `oauth2 clientCredentials tokenUrl /oauth/token`), served at `GET /api/v1/openapi.json` (auth='public', cached 5 min in `tools.ormcache`) and human docs at `GET /api/docs` — self-hosted Scalar/Redoc **bundled into module static/** (no CDN — debranding posture).

**Auth resolution `_gateway_authenticate`:** `Authorization: Bearer <token>`: if token starts `hg_` → `gateway.token.resolve`; else try `res.users.apikeys._check_credentials(scope='rpc')` pattern (`VERIFY:` Odoo 19 apikeys check API — use `env['res.users.apikeys']._check_credentials` equivalent) then load gateway fields (active, ip allowlist, scopes). Session cookie fallback allowed for `/api/v1/pwa/*` routes only (so the existing PWA can migrate without re-auth), mapping to scope set `pwa.*`.

## B.4 OAuth2 token endpoint

`controllers/oauth.py`: `POST /oauth/token` (`type='http'`, `auth='none'`, `csrf=False`), authlib `ClientCredentialsGrant` or hand-rolled (grant_type=client_credentials, client_secret_basic or body). Validates client, intersects requested `scope` with `allowed_scope_ids`, issues via `gateway.token.issue`. Response (RFC 6749): `{"access_token":"hg_...","token_type":"Bearer","expires_in":3600,"scope":"booking.read system/Patient.read"}`. Errors: `{"error":"invalid_client"}` 401 / `{"error":"invalid_scope"}` 400.

## B.5 `/api/v1` wrapped business endpoints (Phase-1 surface)

New controller `controllers/api_v1.py` class `HealthApiV1Controller`. Each handler is thin: re-uses the **same ORM logic** as the PWA handler (extract shared private helpers into the new controller; do NOT modify `health_pwa/controllers/api.py` behavior — old routes stay as-is for deployed PWAs).

| /api/v1 route | Verb | Scope | Wraps (health_pwa/controllers/api.py) |
|---|---|---|---|
| `/api/v1/patients` | GET | `patient.read` | `/health_pwa/api/patients` (L131) |
| `/api/v1/patients/{id}` | GET | `patient.read` | L199 |
| `/api/v1/bookings` | GET | `booking.read` | `/health_pwa/api/fso` (L267) — same filters (state, date range) |
| `/api/v1/bookings/{id}` | GET | `booking.read` | L394 |
| `/api/v1/bookings/{id}/start` | POST | `booking.write` | L671 → `order.action_start_service()` |
| `/api/v1/bookings/{id}/complete` | POST | `booking.write` | L780 (payment_choice/payment_method passthrough) |
| `/api/v1/bookings/{id}/cancel` | POST | `booking.write` | L726 → `order.cancel_with_reason(...)` |
| `/api/v1/bookings/{id}/clinical-notes` | POST | `booking.write` | L948 |
| `/api/v1/bookings/{id}/quote` | GET | `booking.read` | L1084 |
| `/api/v1/assignments/today` | GET | `booking.read` | L1397 |
| `/api/v1/products/catalog` | GET | `booking.read` | L1133 |
| `/api/v1/future-bookings` | GET | `booking.read` | L1941 |

Request/response JSON: identical `data` payloads to the wrapped endpoints (document in pydantic response models field-by-field from the existing serializers, e.g. `_serialize_clinical_notes` api.py:105).

## B.6 Event catalog + emitters

`models/event_emitters.py` — inherits, writes `integration.outbox` rows in-transaction:

| event_code | emitter |
|---|---|
| `booking.created` | `health.fieldservice.order.create()` override |
| `booking.confirmed` | `action_confirm_booking` (L2121) post-super state check |
| `booking.completed` | `action_complete_service` (L2756) post-super (covers both `completed` and `completed_pending_invoice`) |
| `booking.cancelled` | `cancel_with_reason` post-super |
| `booking.rescheduled` | `action_reschedule_from_wizard` (L3069) post-super |
| `patient.created` | `res.partner.create()` when patient (`VERIFY:` patient flag — use the same predicate as PWA `_get_patient_changes`, sync.py:175) |
| `invoice.posted` | `account.move.action_post` (health invoices only: `move_type='out_invoice'` + patient partner) |
| `payment.received` | `health.payment.transaction.create()` (model referenced in api.py:866 — `VERIFY:` module of `health.payment.transaction`, expected health_invoicing) |
| `assignment.changed` | `health.staff.assignment` create/write on staff_id |

Payload shape (uniform): `{"event": "booking.completed", "occurred_at": iso, "model": "health.fieldservice.order", "id": 123, "data": {<compact snapshot: name, state, patient_id, patient_name, scheduled/actual datetimes, facility_id, staff ids>}}`. **No clinical narrative, no phone numbers in webhook payloads** (PHI minimization); consumers fetch details via API with their own scopes.

## B.7 Webhook delivery

Dispatcher cron (1 min) + immediate best-effort kick after commit (`env.cr.postcommit.add`). HTTP POST, headers: `Content-Type: application/json`, `X-Health19-Event: <code>`, `X-Health19-Delivery: <delivery id>`, `X-Health19-Signature: sha256=<hex hmac_sha256(secret, raw_body)>`, timeout 10 s. 2xx → sent. Else retry with backoff `1m, 5m, 30m, 2h, 12h, 24h` then `dead`. UI: replay button (`action_replay` on delivery), per-subscription delivery list view.

## B.8 Rate limiting stance

- **Primary: edge.** Document in module README: Traefik/Nginx in front of Odoo owns real rate limiting (per-IP and per-`Authorization` header bucket). Odoo Python workers must not be the throttle of record (architecture doc §4).
- **App-level fallback (implemented):** fixed-window counter, model-less — `ir.config_parameter` limits (`gateway.rate_limit_per_min` default 120; `gateway.rate_limit_burst` 240) enforced in `_gateway_authenticate` using a per-worker in-memory dict + a shared Postgres advisory approach is overkill: use `tools.cache`-free simple table `gateway.rate.counter` (`key_ref` Char index, `window_start` Datetime, `count` Integer) with `INSERT ... ON CONFLICT (key_ref, window_start) DO UPDATE SET count = count + 1 RETURNING count`; over limit → 429 envelope + `Retry-After`. Cron prunes rows > 1 h nightly. This is correctness-fallback, not DDoS protection — say so in code comment.

## B.9 Security
Groups: `group_gateway_admin` (manage keys/clients/webhooks/read audit), `group_gateway_readonly_docs` (see /api/docs). ACLs: scopes read-all/manage-admin; oauth client admin-only; webhook.subscription admin-only; audit log B.2.8 rules; outbox admin read-only. Record rule: none beyond service-user natural rules (by design — keys act as real users).

## B.10 Data seeds (`data/api_scopes.xml`)
Scope rows: `pwa.read`, `pwa.write`, `patient.read`, `booking.read`, `booking.write`, `invoice.read`, `webhook.manage`, `system/Patient.read`, `system/Practitioner.read`, `system/Organization.read`, `system/Location.read`, `system/Encounter.read`, `system/Appointment.read`, `system/ServiceRequest.read`, `system/DocumentReference.read`, `system/*.read`.

## B.11 Acceptance criteria
1. `POST /oauth/token` with valid client_credentials returns a Bearer token; the token lists only intersected scopes; expired token → 401 envelope.
2. `GET /api/v1/bookings` with a key lacking `booking.read` → 403 `{"success":false,...}`; with scope → same `data` shape as `/health_pwa/api/fso` for the same user.
3. `GET /api/v1/openapi.json` validates against OpenAPI 3.1 meta-schema and contains every B.5 route with request/response schemas; `/api/docs` renders with zero external network requests.
4. Completing an FSO writes one `integration.outbox` row `booking.completed` in the same transaction (rollback test: forced error after complete → no outbox row).
5. Webhook subscriber receives POST with valid `X-Health19-Signature` (HMAC verifiable with stored secret); a 500-returning endpoint is retried on the backoff schedule and lands `dead` after 6 attempts; replay works.
6. Every `/api/v1/*` and `/fhir/r4/*` call creates exactly one `api.audit.log` row incl. latency and (for FHIR) `patient_ids`; log rows cannot be written/unlinked from UI.
7. A key with `facility_ids` set cannot read bookings of other facilities (record rules via service user + facility check).
8. 121st request in one minute with default limits → 429 with `Retry-After`.
9. Old `/health_pwa/api/*` routes behave byte-identically after install (regression: PWA smoke flow start→complete).
10. Requests from an IP outside `ip_allowlist` → 401, audited.

## B.12 Integration points
- `health_pwa/controllers/api.py` — envelope contract (L41-63) copied; wrapped endpoint logic per B.5 table (read-only reuse).
- `health_fieldservice/models/health_fieldservice_order.py` — emitter inherits on `create`, `action_confirm_booking` (L2121), `action_complete_service` (L2756), `cancel_with_reason`, `action_reschedule_from_wizard` (L3069).
- `health_invoicing` — `health.payment.transaction`, `account.move.action_post`.
- `res.users.apikeys` (Odoo core) — inherit B.2.2.

---

# C. `health_fhir_core` — Phase-1 read-only FHIR R4 facade

## C.1 Manifest

```python
{
    'name': 'Health FHIR R4 Facade (read-only)',
    'version': '19.0.1.0.0',
    'depends': ['health_api_gateway', 'health_base', 'health_crm', 'health_fieldservice'],
    'external_dependencies': {'python': ['fhir.resources']},  # pip: fhir.resources (R4B, pydantic v2)
    'data': ['security/ir.model.access.csv'],
    'license': 'LGPL-3',
}
```
No new persisted models except none — the facade is stateless (audit goes to `api.audit.log`). **No existing module gains a dependency on this one** (architecture §6.8).

## C.2 Serializer registry pattern

```
health_fhir_core/
  serializers/__init__.py      # REGISTRY = {'Patient': PatientSerializer(), ...}
  serializers/base.py
  serializers/patient.py practitioner.py organization.py location.py
  serializers/encounter.py appointment.py service_request.py document_reference.py
  controllers/fhir.py
  capability.py
```

`serializers/base.py`:

```python
class FHIRSerializer:
    resource_type: str            # 'Patient'
    odoo_model: str               # 'res.partner'
    scope: str                    # 'system/Patient.read'
    search_params: dict           # name -> {'type': 'token|date|reference|string', 'domain': callable(value)->odoo domain}

    def base_domain(self, env): ...          # which records exist as this resource
    def to_fhir(self, record) -> dict: ...   # builds dict, then validated:
        # fhir.resources.<x>.<X>.model_validate(d) -- construct-and-validate on EVERY response
    def patient_ids_of(self, records) -> list[int]   # for audit log patient_ids
```

Common behaviors in base: FHIR `id` = str(odoo id); `meta.lastUpdated` = `write_date` (UTC, `Z`); `search()` maps `_lastUpdated=[ge|le]ts` → `write_date` domain, `_count` (max 100, default 20) + cursor paging `_cursor=<last id>` (order `id asc`, `('id','>',cursor)`) returning `Bundle.link[rel=next]` with `_cursor`; unsupported search param → HTTP 400 `OperationOutcome` (`issue.code='not-supported'`) — **strict handling**, never silent-ignore (architecture §1.2).

## C.3 Resource mappings (Phase 1, exactly per architecture doc §1.1)

### Patient ← `res.partner`
`base_domain`: `[('is_patient','=',True)]` (confirmed field — same flag `health.client.relation.client_id` domain uses); cross-check against PWA sync `_get_patient_changes` (sync.py:175) domain and unify.
Mapping: `name[0]` = `{text: partner.name}` (vi diacritics preserved); `telecom` = phone/mobile as `{system:'phone'}`, zalo id (`partner.zalo_user_id`, from health_zalo when installed — guard with `if 'zalo_user_id' in partner._fields`) as `{system:'other', value, extension urn:health19:zalo}`; `gender` from partner gender field if present else omit; `birthDate` from `dob` (`VERIFY:` exact field name on res.partner in health_base); `address[0]` from street/city + `state` = province name; `identifier[]`: `{system:'urn:health19:partner', value:str(id)}` + national id/BHYT when fields exist (`VERIFY`); `managingOrganization` = `Reference(Organization/<primary_facility_id.id>)`; `generalPractitioner` omitted v1.

Search params: `identifier` (token → `id` or national-id field), `name` (string → `name ilike`), `telecom`/`phone` (token → phone/mobile normalized ilike), `birthdate` (date), `_lastUpdated`.

### Practitioner ← `hr.employee`
`base_domain`: `[('healthcare_facility_id','!=',False)]` (project memory: employee facility link = `healthcare_facility_id`). Map: `name`, `telecom` (work_phone/work_email), `identifier` `{system:'urn:health19:employee'}`, `qualification[]` from `healthcare_skill` m2m (`VERIFY:` skill field name on hr.employee in `health_fieldservice/models/hr_employee.py`). Search: `identifier`, `name`, `_lastUpdated`.

### Organization ← `health.facility`
Map: `name`, `telecom`, `address`, `identifier` `{system:'urn:health19:facility'}`, `active`. Search: `name`, `identifier`, `_lastUpdated`.

### Location ← `health.facility`
Same records, `Location.position` = facility lat/lng (`VERIFY:` field names on `health_base/models/health_facility.py` — the geocoding pattern matches res.partner), `managingOrganization` = its own Organization, timezone as extension `urn:health19:timezone`. Search: `name`, `organization` (reference), `_lastUpdated`.

### Encounter ← `health.fieldservice.order`
`base_domain`: `[]` (all FSOs). Map: `status` from `state`: draft/confirmed→`planned`, assigned→`planned`, in_progress→`in-progress`, completed/completed_pending_invoice/closed→`finished`, cancelled→`cancelled`; `class` = v3 ActCode `HH`; `subject` = `Reference(Patient/<patient_id.id>)`; `period.start/end` = `actual_start_datetime`/`actual_end_datetime` (fallback scheduled); `participant[]` from `assignment_ids` → `individual=Reference(Practitioner/<staff_id.id>)`; `serviceProvider` = facility; `appointment` = `Reference(Appointment/<same id>)`; extension `urn:health19:evv-verified` bool when health_evv installed (guarded `if 'evv_verified' in order._fields`).
Search: `patient` (reference → `patient_id`), `date` (date, ge/le prefixes → `scheduled_datetime` — confirmed field, Datetime UTC), `status` (token, reverse of map), `_lastUpdated`.

### Appointment ← `health.fieldservice.order`
`status`: draft→`proposed`, confirmed→`booked`, assigned→`booked`, in_progress→`arrived`, completed/…→`fulfilled`, cancelled→`cancelled`; `start/end` = scheduled datetimes; `participant[]` = patient (required) + practitioners, `participant.status='accepted'`. Search: `patient`, `date`, `status`, `_lastUpdated`.

### ServiceRequest ← `health.fieldservice.order` (+ `sale_order_id.order_line`)
`status`: draft→`draft`, cancelled→`revoked`, completed/closed→`completed`, else `active`; `intent='order'`; `code.text` = service type name; `orderDetail[]` = one `CodeableConcept{text: line.name}` per `quote_line_ids` line; `subject`, `encounter`, `authoredOn=create_date`. Search: `patient`, `status`, `_lastUpdated`.

### DocumentReference ← `health.clinical.note`
`status='current'`; `type.text='Clinical visit note'`; `subject` = `Reference(Patient/<order_id.patient_id.id>)`; `context.encounter` = FSO; `date=create_date`; `author` = Practitioner of `author_id` when linked to employee else `display=author_name`; `content[0].attachment` = `{contentType:'text/plain; charset=utf-8', data: base64(compiled text), title: display_name}` where compiled text concatenates the labeled sections (clinical_notes, diagnosis, treatment_performed, medications_prescribed, vital_signs, condition before/after, counts); additional `content[]` entries per `image_ids` as `{contentType: att.mimetype, url: absolute /web/content/<id> — note: requires separate auth, document in CapabilityStatement}`. Search: `patient`, `encounter` (reference → `order_id`), `date` (create_date), `_lastUpdated`.

## C.4 Controller
`controllers/fhir.py` — one controller, routes `type='http'`, `auth='none'`, `csrf=False`; auth/scope/audit/ratelimit via the same `_gateway_authenticate` middleware from health_api_gateway (import the python helper, not HTTP). Scope required: resource-specific `system/<Type>.read` or `system/*.read`.

| Route | Verb | Behavior |
|---|---|---|
| `/fhir/r4/metadata` | GET | CapabilityStatement (C.5). auth='public' (no PHI) |
| `/fhir/r4/<string:rtype>` | GET | search → `Bundle{type:'searchset', total, entry[], link[]}` |
| `/fhir/r4/<string:rtype>/<int:rid>` | GET | read → resource or 404 OperationOutcome |

Responses: `Content-Type: application/fhir+json; charset=utf-8`. Errors are always `OperationOutcome` (401 `login`, 403 `forbidden`, 404 `not-found`, 400 `not-supported`/`invalid`). Unknown `rtype` → 404 OperationOutcome. Every 2xx read/search logs `api.audit.log` with `resource_type`, `resource_ids`, `patient_ids` (from `patient_ids_of`).

## C.5 CapabilityStatement
`capability.py: build_capability(env)` — generated **from the registry** (never hand-list): `status=active`, `kind=instance`, `fhirVersion='4.0.1'`, `format=['application/fhir+json']`, `rest[0].mode='server'`, per resource: `type`, `interaction=[read, search-type]`, `searchParam[]` (name+type from `search_params`, plus `_lastUpdated`, `_count`), security: `service=[{coding:[{system:'http://terminology.hl7.org/CodeSystem/restful-security-service', code:'OAuth'}]}]`. Cached `ormcache`, invalidated on registry import.

## C.6 Security / ACL
No new models. FHIR reads execute as the token's service user → existing record rules scope data. Recommend (README) a `fhir_readonly` service user per partner with facility-limited access_roles.

## C.7 Acceptance criteria
1. `GET /fhir/r4/metadata` returns a CapabilityStatement that `fhir.resources` parses; it lists exactly the 8 resources and their search params.
2. Every serialized resource round-trips `model_validate` with zero validation errors for 50 random real records per type on vietuat data.
3. `GET /fhir/r4/Patient?identifier=123` returns bundle with the partner 123 Patient; `?name=Nguy` matches diacritic names.
4. `GET /fhir/r4/Encounter?patient=Patient/123&date=ge2026-07-01&date=le2026-07-31` maps to the correct ORM domain and pages with `_count=10` + `link[next]` cursor until exhaustion (no overlaps/gaps).
5. Unsupported param `GET /fhir/r4/Patient?foo=1` → 400 OperationOutcome `not-supported`.
6. Token without `system/Patient.read` (but with `system/Encounter.read`) → Patient 403, Encounter 200.
7. FSO state transitions map: an `in_progress` FSO reads back Encounter `in-progress` AND Appointment `arrived`.
8. DocumentReference for a clinical note contains base64 text decoding to all populated sections, and one content entry per image.
9. Every FHIR 2xx creates an `api.audit.log` row whose `patient_ids` contains the subject partner id(s).
10. Facility-restricted service user searching Encounter sees only its facility's FSOs.

## C.8 Integration points
- health_api_gateway: `_gateway_authenticate`, scope rows (B.10), `api.audit.log`.
- Models read (never written): `res.partner`, `hr.employee`, `health.facility`, `health.fieldservice.order`, `health.staff.assignment`, `health.clinical.note`, `sale.order.line` (via `quote_line_ids` related, FSO L1150).
- health_zalo / health_evv fields consumed defensively via `in record._fields` guards.

---

# D. `health_messaging_auto` — reminder & notification cascade

## D.1 Manifest

```python
{
    'name': 'Health Messaging Automation',
    'version': '19.0.1.0.0',
    'depends': ['health_base', 'health_fieldservice', 'health_crm', 'health_zalo', 'sms'],
    # health_voip24h is a SOFT dependency: voice step activates only if installed
    'data': [
        'security/messaging_security.xml', 'security/ir.model.access.csv',
        'data/messaging_cron.xml', 'data/reminder_rule_seed.xml',
        'views/reminder_rule_views.xml', 'views/message_delivery_views.xml',
        'views/client_relation_views.xml',
    ],
    'license': 'LGPL-3',
}
```
`sms` is Odoo core (IAP) — precedent: `account_payment_notification` already uses `_message_sms_with_template()`. `VERIFY:` IAP SMS credits configured on vietuat; if a VN SMS aggregator is preferred later, override `sms.api._send_sms_batch` in a follow-up module — this spec targets stock `sms.sms`.

## D.2 Models

### D.2.1 `health.reminder.rule`
| name | type | params | purpose |
|---|---|---|---|
| `name` | Char | required | |
| `active` | Boolean | default=True | |
| `trigger` | Selection | `[('booking_confirmed','On booking confirmation'),('t_minus','Before scheduled start'),('post_completion','After completion')]`, required | |
| `t_minus_hours` | Float | | for `t_minus` (seed rows: 24 and 2) |
| `applies_facility_ids` | Many2many | `health.facility` | empty=all |
| `quiet_from` / `quiet_to` | Float | default 21.0 / 7.5 | quiet hours in the **booking's** timezone (`fso.booking_timezone`, default `Asia/Ho_Chi_Minh` — pattern from `health_staff_assignment.py:402`); a send landing in quiet hours is deferred to `quiet_to` |
| `channel_line_ids` | One2many | `health.reminder.channel.line` | ordered cascade |
| `dedupe_key` | Char | compute | `f'{trigger}:{t_minus_hours}'` — one delivery chain per (rule, fso) |

### D.2.2 `health.reminder.channel.line`
| name | type | params | purpose |
|---|---|---|---|
| `rule_id` | Many2one | required, ondelete=cascade | |
| `sequence` | Integer | | cascade order (10 ZNS, 20 SMS, 30 voice) |
| `channel` | Selection | `[('zns','Zalo ZNS'),('sms','SMS'),('voice','Voice call')]`, required | |
| `zns_template_id_vi` / `zns_template_id_en` | Char | | external Zalo template ids (no template model exists in health_zalo — ids live here), per client `partner.lang` (`vi_VN`→vi else en) |
| `zns_param_map` | Json | | `{"customer_name":"patient_id.name","booking_date":"scheduled_datetime:%d/%m/%Y","booking_time":"scheduled_datetime:%H:%M","service":"service_interest_display","clinic_phone":"config:clinic_phone"}` — dotted field paths on FSO (`scheduled_datetime` confirmed), `:%fmt` for datetimes rendered in `booking_timezone` (default `Asia/Ho_Chi_Minh`), `config:` for ir.config_parameter |
| `sms_template_id` | Many2one | `sms.template` | model must be `health.fieldservice.order` |
| `escalate_after_min` | Integer | default=30 | wait for delivery confirmation before next line |

### D.2.3 `health.message.delivery` — tracking
| name | type | params | purpose |
|---|---|---|---|
| `rule_id` / `line_id` | Many2one | | source (nullable for snapshot messages) |
| `fso_id` | Many2one | `health.fieldservice.order`, index | |
| `partner_id` | Many2one | required | recipient person |
| `phone` | Char | required | normalized (reuse `health_base/models/phone_utils.py` helpers — `VERIFY:` exact function name) |
| `kind` | Selection | `[('reminder','Reminder'),('family_snapshot','Family Snapshot'),('visit_offer','Visit Offer')]` | |
| `channel` | Selection | zns/sms/voice | |
| `state` | Selection | `[('scheduled','Scheduled'),('sent','Sent'),('delivered','Delivered'),('failed','Failed'),('skipped','Skipped'),('escalated','Escalated')]`, default scheduled, index | |
| `scheduled_at` | Datetime | index | when the queue cron may send it |
| `sent_at` / `delivered_at` | Datetime | | |
| `provider_ref` | Char | | ZNS `msg_id` from send response / `sms.sms` id / voip call_id |
| `error_message` | Text | | |
| `payload_preview` | Text | | rendered params (debug; no more PHI than the message itself) |
| `company_id` | Many2one | default | |

### D.2.4 `health.client.relation` (inherit) — consent hook
| `messaging_consent` | Selection `[('none','No consent'),('zns','Zalo ZNS ok'),('all','Any channel')]`, default `'none'` | family-message opt-in |
| `receives_visit_updates` | Boolean, default=False | recipient flag for the post-visit snapshot |

Public API (the cross-cutting hook the roadmap's future health_consent will re-implement):
```python
@api.model
def check_messaging_consent(self, partner, purpose='family_snapshot') -> bool
```
v1 logic: any active relation row for `representative_id=partner` with `receives_visit_updates` and `messaging_consent != 'none'`. All senders MUST call this — single choke point.

## D.3 Cascade engine

`models/messaging_engine.py`, AbstractModel `health.messaging.engine`:

```python
@api.model
def schedule_for_trigger(self, fso, trigger):
    """For each matching active rule (facility filter, dedupe on existing deliveries
    with same rule+fso): create ONE 'scheduled' delivery for the FIRST channel line.
    scheduled_at: booking_confirmed -> now; t_minus -> scheduled_start - t_minus_hours
    (skipped if already past); apply quiet-hours shift. Recipient = fso.patient_id
    (phone precedence: mobile, phone)."""

@api.model
def cron_process_queue(self):
    """Every 5 min. (a) SEND: deliveries state='scheduled', scheduled_at<=now,
    fso still in ('confirmed','assigned') for reminders -> _send_one(d).
    (b) ESCALATE: state in ('sent','failed'), channel line has a successor,
    and (state=='failed' or (channel=='zns' and not delivered_at and
    now-sent_at > escalate_after_min)): mark 'escalated', create next-line delivery
    scheduled now (quiet-hours checked again). SMS: sms.sms 'error' state -> failed;
    'sent/outgoing' after grace counts as delivered (IAP has no DLR).
    (c) DEAD-END: last line failed -> mail.activity on FSO to facility manager
    (reuse the _create_follow_up_activity pattern, health_pwa api.py:66)."""

def _send_one(self, delivery):
    # zns:
    #   config = self.env['zalo.config'].get_active_config()
    #   from odoo.addons.health_zalo.services.zalo_api import ZaloAPIClient
    #   res = ZaloAPIClient().send_zns_notification(config, delivery.phone,
    #         line.zns_template_id_for(lang), rendered_params)      # zalo_api.py:297
    #   success -> state='sent', provider_ref=res msg_id (VERIFY: response key,
    #   Zalo ZNS returns {'error':0,'message':'Success','data':{'msg_id':...}});
    #   res['error'] != 0 -> state='failed', error_message=res['message']
    # sms:
    #   self.env['sms.sms'].create({'number': phone, 'body': rendered,
    #       'partner_id': ...}).send()   (template render via sms.template on fso)
    # voice: see D.5
```

**ZNS delivery callbacks:** extend the existing webhook — inherit `zalo.message.handler.process_webhook_event` (`health_zalo/services/message_handler.py:20`): new branch for ZNS status events (`VERIFY:` exact Zalo event name for ZNS delivery status — expected `zns.message.status` / `user_received_message`; log-and-inspect on UAT first). Match `data.msg_id` → `provider_ref` → set `delivered/failed` + `delivered_at`. Until verified, the cascade still works via the `escalate_after_min` timeout path (delivery-status driven when available, timer-driven otherwise).

**Trigger wiring** (`models/health_fieldservice_order.py` inherit):
- `action_confirm_booking` post-super → `schedule_for_trigger(order,'booking_confirmed')` and `schedule_for_trigger(order,'t_minus')` (both t-24 and t-2 rules match), then set existing `reminders_sent=True` (field exists, FSO model).
- `action_reschedule_from_wizard` post-super → cancel (`skipped`) pending reminder deliveries, re-schedule.
- `cancel_with_reason` post-super → mark pending deliveries `skipped`.
- `action_complete_service` post-super → family snapshot (D.4).

## D.4 Family post-visit snapshot

`_send_family_snapshot(order)` called post-completion:
1. Recipients: `health.client.relation.search([('client_id','=',order.patient_id.id),('active','=',True),('receives_visit_updates','=',True),('can_receive_medical_info','=',True)])` filtered by `check_messaging_consent(rel.representative_id)` — `can_receive_medical_info` is an existing confirmed Boolean on the relation and acts as the medical-info gate; kinship label from confirmed `role`/`relationship_type` selections. Skip silently if none.
2. Compose from the visit's latest `health.clinical.note`: params `{patient_name, visit_date, staff_name, summary}` where `summary` = first 200 chars of `patient_condition_after or treatment_performed or clinical_notes` **sanitized: no diagnosis, no medications in v1** (family-appropriate).
3. Send ZNS template `ir.config_parameter health_messaging_auto.zns_family_snapshot_template_vi/_en`; create `health.message.delivery` `kind='family_snapshot'` per recipient; no SMS/voice escalation for snapshots (nice-to-have, not critical-path).

## D.5 Voice step feasibility (stated plainly)

`health_voip24h` exposes **click-to-dial only** (`VoIP24hAPI.initiate_call(from_extension, to_number)`, `voip24h_api.py:215`) — there is no TTS/auto-IVR capability in the current integration, so a fully automated voice reminder **is not implementable today**. Implement the `voice` channel as:
- v1 (ships now): create `health.message.delivery` `channel='voice'` `state='sent'` **plus** an urgent `mail.activity` on the FSO assigned to the facility coordinator ("Call client to confirm visit — reminder cascade escalation"), and if health_voip24h installed, render a click-to-dial button on the activity/FSO (existing widget).
- v2 (needs vendor work, out of scope): VoIP24h AutoCall/TTS campaign API — requires commercial enablement + new `VoIP24hAPI.create_autocall(phone, audio_or_tts, callback)` and webhook `call.ended` correlation to set delivered (answered) / failed (no answer ×3). Interface seam left in `_send_one`.

## D.6 Crons (`data/messaging_cron.xml`)
1. `Messaging: process delivery queue` — `health.messaging.engine.cron_process_queue()`, every 5 min.
2. `Messaging: schedule T-minus reminders safety net` — every hour, finds confirmed/assigned FSOs starting within max(t_minus_hours)+1h having no delivery for a matching t_minus rule → `schedule_for_trigger` (covers bookings confirmed before module install / rules added later).

## D.7 Security & seeds
Groups: `group_messaging_manager` (rules config), users read own-facility deliveries. ACLs: rule/line manager-write user-read; delivery user-read create-by-system(sudo), no unlink. Seeds (`reminder_rule_seed.xml`, `noupdate="1"`): Rule "Booking confirmed" (trigger booking_confirmed; lines ZNS→SMS), Rule "T-24h" (t_minus 24; ZNS→SMS), Rule "T-2h" (t_minus 2; ZNS→SMS→voice, escalate_after_min 20). ZNS template-id fields left blank — set on UAT (they are per-OA); **remember `noupdate=1` implies later seed edits need direct DB writes** (project memory).

## D.8 Acceptance criteria
1. Confirming a booking (T-30h out) creates 3 scheduled ZNS deliveries (confirm-now, T-24, T-2) with correct `scheduled_at` in `Asia/Ho_Chi_Minh` math and quiet-hour shifts (a 06:30 slot's T-2 lands 07:30+, not 04:30).
2. ZNS send failure (`error != 0`) escalates to SMS within one cron pass; SMS failure on the T-2 rule escalates to voice = coordinator activity created.
3. ZNS with no delivery status after `escalate_after_min` escalates by timeout; a delivery-status webhook marking `delivered` prevents escalation.
4. Rescheduling a booking voids (`skipped`) all pending reminders and creates fresh ones at the new times; cancelling voids without recreation.
5. Client with `lang=vi_VN` gets `zns_template_id_vi`; en client gets `_en`.
6. Completing a visit sends the family snapshot ONLY to relations with `receives_visit_updates=True` **and** consent ≠ none; zero consent rows → zero sends, delivery row `skipped` is not created (no phantom PHI trail).
7. Snapshot params contain no diagnosis/medication strings.
8. Duplicate trigger fire (double confirm click) creates no duplicate delivery (dedupe on rule+fso+line pending/sent).
9. All sends recorded in `health.message.delivery` with provider_ref; list view filters by state/kind/channel.
10. Module functions with health_voip24h uninstalled (voice lines fall back to activity-only, no ImportError).

## D.9 Integration points
- `health_zalo/services/zalo_api.py` → `ZaloAPIClient.send_zns_notification(config, phone, template_id, template_data)` (L297); `zalo.config.get_active_config()`; webhook extension via `zalo.message.handler.process_webhook_event` (`services/message_handler.py:20`).
- Odoo `sms` → `sms.template`, `sms.sms` (precedent `account_payment_notification/models/account_payment.py`).
- `health_voip24h/services/voip24h_api.py` → `initiate_call` (L215), soft-dep.
- FSO hooks: `action_confirm_booking` L2121, `action_complete_service` L2756, `cancel_with_reason`, `action_reschedule_from_wizard` L3069; existing `reminders_sent` field.
- `health_crm/models/health_client_relation.py` (L16) inherit.

---

# E. `health_workflow_auto` — H0 automations (patches to existing modules)

One glue module so existing modules stay dependency-clean.

## E.1 Manifest
```python
{
    'name': 'Health H0 Workflow Automations',
    'version': '19.0.1.0.0',
    'depends': ['health_fieldservice', 'health_pwa', 'health_redinvoice', 'pb_hr_workforce',
                'health_messaging_auto', 'crm', 'hr_attendance'],
    'data': ['security/ir.model.access.csv', 'data/workflow_cron.xml',
             'views/fso_views.xml', 'views/visit_offer_views.xml', 'views/attendance_views.xml'],
    'license': 'LGPL-3',
}
```

## E.2 (1) Exception-only completion

### Model: `health.fieldservice.order` (inherit), `models/fso_onetap.py`
| name | type | params | purpose |
|---|---|---|---|
| `quote_snapshot_hash` | Char | size=64, readonly, copy=False | SHA-256 of sale order lines at confirmation |
| `quote_is_unchanged` | Boolean | compute (non-stored) | current lines hash == snapshot |

```python
def _quote_lines_hash(self):
    """sha256 of json.dumps(sorted([(l.product_id.id, float(l.product_uom_qty),
    float(l.price_unit), float(l.discount)) for l in self.sale_order_id.order_line]),
    separators=(',',':'))  -- '' when no sale_order_id."""

def action_confirm_booking(self):
    res = super().action_confirm_booking()
    for o in self: o.quote_snapshot_hash = o._quote_lines_hash()
    return res

def action_one_tap_complete(self, service_notes=''):
    """PRECONDITIONS: state=='in_progress'; sale_order_id set; quote_is_unchanged.
    Steps: (1) auto-verify quote: if sale_order_id.state in ('draft','sent'):
    sale_order_id.action_confirm()  [this is exactly what the PWA complete endpoint
    does at api.py:836 — reuse, don't reinvent]; set whatever flag drives
    invoice_submitted (VERIFY: read the invoice_submitted compute in FSO model and
    satisfy its real dependency — likely presence of confirmed quote/invoice).
    (2) if not clinical_notes_submitted: create minimal health.clinical.note
    {'order_id': id, 'clinical_notes': service_notes or 'Visit completed - no exceptions
    reported (one-tap complete)'} — satisfies the hard gate in action_complete_service
    (L2762). (3) call self.action_complete_service(). Returns dict {completed: True}."""
```

### PWA endpoint change (`controllers/onetap_api.py`, same envelope conventions)
`POST /health_pwa/api/fso/<int:order_id>/complete_onetap` — body `{"service_notes": "", "payment_choice": "pay_later"}`.
Response when quote unchanged: run `action_one_tap_complete`, then the invoice/payment tail **identical to** the existing complete endpoint (api.py:823-885 — factor that tail into a helper and call from both if touching health_pwa is approved; otherwise duplicate); `data: {"completed": true, "state": "completed", "verified_quote": true}`.
When changed: HTTP 409-style envelope `data: {"completed": false, "needs_review": true, "changed": {"added": [...], "removed": [...], "qty_changed": [...]}}` — PWA then routes to the existing quote screen (`/health_pwa/api/fso/<id>/quote` flow).
GET support: `GET /health_pwa/api/fso/<int:order_id>/onetap_eligible` → `{"eligible": bool, "reason": str}` (drives showing the one-tap button).

### Acceptance
1. FSO confirmed with 2 lines, untouched → `onetap_eligible=true`; one-tap completes visit, confirms SO, creates+posts invoice per existing rules, state `completed` (full-time) — all in one HTTP call.
2. Any line qty/price/product change after confirm → eligible false with a correct diff; one-tap POST returns `needs_review` and mutates nothing.
3. One-tap on FSO without clinical notes creates the placeholder note (the L2756 gate passes); an existing note is not duplicated.
4. Part-time staff one-tap lands `completed_pending_invoice` exactly like the normal path.
5. `booking.completed` outbox event + family snapshot + timecard fill (E.4) all fire from one-tap identically to normal completion.

## E.3 (2) Nightly Red Invoice batch + retry queue

`models/redinvoice_batch.py`, inherit `account.move` + extend `redinvoice.request`.

New fields on `redinvoice.request`: `next_retry_at` Datetime, `max_retries` Integer default=5.

```python
# account.move
@api.model
def cron_redinvoice_batch_submit(self, batch_limit=200):
    """Nightly 01:30. Domain: state='posted', move_type='out_invoice',
    red_invoice_state in ('pending', 'failed')  [confirmed selection:
    not_required/pending/issuing/issued/failed/cancelled — never touch
    'issuing' (in-flight), 'issued', 'cancelled', 'not_required'],
    company red-invoice-configured (red_supplier_tax_code AND
    red_invoice_api_base set, per the guard inside _redinvoice_issue).
    Per move, in a savepoint:
    call move._redinvoice_issue()   [L179 — existing single-invoice submit;
    it already writes redinvoice.request rows via mark_sent/mark_success/mark_failed].
    On exception: rollback savepoint; ensure a redinvoice.request row exists with
    mark_failed(str(e)); set next_retry_at = now + [5min,30min,2h,6h,24h][retry_count]
    and retry_count += 1. Skip moves whose latest request has
    retry_count >= max_retries (these need the manual action_redinvoice_generate,
    L80). Summary: one ir.logging line + mail.activity to accounting manager when
    failures > 0."""

@api.model
def cron_redinvoice_retry(self):
    """Every 30 min: latest-request-per-move where state='failed',
    retry_count < max_retries, next_retry_at <= now -> same submit path."""
```
Crons in `data/workflow_cron.xml`. Endpoint/prefix/Basic-Auth are whatever `_redinvoice_base_url` (L393) + `_redinvoice_auth_cookies` (L405) already do — **do not re-derive the URL**; project memory: createInvoice needs the `/services/einvoiceapplication/api/` prefix, already handled in the existing code path.

### Acceptance
1. 10 posted eligible invoices → nightly cron issues all; `red_invoice_state` advances exactly as manual `action_redinvoice_generate` would; `redinvoice.request` rows show success.
2. Viettel endpoint down → each failure recorded with response body, `retry_count=1`, `next_retry_at≈+5min`; retry cron progresses the backoff chain; 6th failure stops (manual queue) + activity created.
3. One bad invoice (validation error) does not block the rest of the batch (savepoint isolation).
4. Already-issued and `not_required` invoices are never resubmitted.
5. Batch respects `batch_limit` and is idempotent across overlapping cron runs.

## E.4 (3) Timecards auto-filled from PWA check-in/out

Both sides named exactly: **source** = FSO `actual_start_datetime` / `actual_end_datetime` (set by `action_start_service` L2528 / `action_complete_service` L2795,2825) + per-staff `health.staff.assignment` rows; **target** = **`hr.attendance`** (`check_in`, `check_out`, `employee_id`) — this is what `pb_hr_workforce` timecards (`hr.attendance.timecard.get_timecard_data`, `attendance_timecard.py:15`) and `hr.overtime.config` maths read.

`models/hr_attendance_sync.py`:

`hr.attendance` (inherit): `fso_id` Many2one `health.fieldservice.order` (index, copy=False), `attendance_source` Selection `[('manual','Manual'),('pwa_visit','PWA Visit')]` default manual.

`health.fieldservice.order` (inherit):
```python
def action_start_service(self):
    res = super().action_start_service()
    for o in self: o._attendance_open()
    return res

def _attendance_open(self):
    """For each employee in (lead_staff_id | assignment_ids.staff_id) with a user:
    if the employee has an OPEN hr.attendance (check_out=False) -> do nothing
    (nurse chains visits inside one attendance; per-visit truth stays on the FSO).
    Else create hr.attendance {employee_id, check_in: actual_start_datetime,
    fso_id: id, attendance_source: 'pwa_visit'}."""

def action_complete_service(self):
    res = super().action_complete_service()
    for o in self: o._attendance_close()
    return res

def _attendance_close(self):
    """Close attendances with fso_id=self and check_out=False:
    check_out = actual_end_datetime. Attendances opened manually are untouched."""
```

New model `health.timecard.mismatch`:
| `employee_id` M2O required | `date` Date | `fso_id` M2O | `attendance_id` M2O | `kind` Selection `[('start_gap','Start gap >15m'),('end_gap','End gap >15m'),('missing_attendance','Visit w/o attendance'),('orphan_open','Attendance never closed')]` | `delta_minutes` Float | `state` Selection open/resolved | `resolution` Selection `[('keep_attendance','Keep attendance'),('use_fso','Use visit times')]` | `resolved_by` M2O res.users |

**Reconciliation rule (>15 min):** nightly cron `cron_reconcile_timecards(for_date=yesterday)`: for every `pwa_visit` attendance vs its FSO: `|check_in − actual_start_datetime| > 15min` → `start_gap`; same for end. FSOs completed yesterday whose staff have zero overlapping attendance → `missing_attendance`. Open `pwa_visit` attendances older than 16 h → `orphan_open`, auto-close at FSO `actual_end_datetime` + flag. **Payroll truth = hr.attendance; mismatches only surface for a human** (resolving with `use_fso` writes FSO times onto the attendance and logs on chatter). Only mismatches surface — matches flow silently into `pb_hr_workforce` timecards/OT with zero action.

### Acceptance
1. PWA check-in creates `hr.attendance` (`attendance_source='pwa_visit'`, `fso_id` set) whose `check_in == actual_start_datetime`; completion sets `check_out`.
2. Timecard timeline (`hr.attendance.timecard.get_timecard_data`) shows the visit hours with correct weekend/holiday OT classification untouched.
3. 20-min late manual fix of FSO times → nightly cron opens a `start_gap` mismatch with `delta_minutes=20`; ≤15 min → none.
4. Back-to-back visits within one open attendance create no duplicate attendance rows.
5. Resolving with `use_fso` rewrites the attendance and marks mismatch resolved with resolver identity.

## E.5 (4) Instant first-visit offer at lead qualification

### Trigger
Qualification in health_crm = `crm.lead.action_convert_to_client()` (`health_crm/models/crm_lead.py` — confirmed method; marks the contact a qualified client). Hook: inherit `action_convert_to_client`, post-super → `_launch_first_visit_offer()` when the lead has a partner with phone and no open FSO. Also add manual button `action_send_first_visit_offer` on the lead form (idempotent: skips if an unexpired `sent` offer exists). Do NOT hook `action_convert_to_booking` (that path books explicitly already).

### Slot proposal — reuse the existing engine
```python
def _propose_first_visit_slots(self, lead, count=3, horizon_days=7):
    """Build a transient draft FSO-like context: patient=lead.partner_id,
    facility=partner.primary_facility_id, service from lead.service_interest
    (confirmed Selection: home_visit/clinic_visit/consultation/follow_up/
    emergency/preventive/rehabilitation/palliative; default 'consultation').
    For day in next horizon_days, query health.staff.availability.matrix
    ([('availability_date','=',day), ('status','=','available')  (confirmed value),
    ('remaining_capacity','>',0),
    ('conflict_detected','=',False)] + catchment filter via catchment_province_id
    matching the client's province), rank candidate (staff, start_time) pairs with
    health.ai.assignment.engine._calculate_assignment_confidence(fso_ctx, staff)
    (health_ai_assignment_engine.py:419; engine record =
    env['health.ai.assignment.engine'].search([], limit=1) or created default).
    Return the 3 EARLIEST distinct-day-or-time feasible slots:
    [{'date','start_time','staff_id','staff_name','confidence'}]."""
```

### Model `health.visit.offer`
| `lead_id` M2O crm.lead required | `partner_id` M2O required | `token` Char required unique default=`secrets.token_urlsafe(24)` | `state` Selection `[('sent','Sent'),('accepted','Accepted'),('expired','Expired'),('cancelled','Cancelled')]` | `expires_at` Datetime default=+48h | `slot_ids` O2M `health.visit.offer.slot` | `fso_id` M2O readonly (result) | `delivery_id` M2O health.message.delivery |

`health.visit.offer.slot`: | `offer_id` | `index` Integer 1..3 | `slot_date` Date | `start_time` Float | `staff_id` M2O hr.employee | `taken` Boolean |

### Send
ZNS template `health_messaging_auto.zns_visit_offer_template_vi/_en` (config params) with params `{customer_name, slot1, slot2, slot3, link}` where `link = f'{base_url}/booking/offer/{token}'`; recorded as `health.message.delivery` `kind='visit_offer'` through the D.3 engine (`_send_one`).

### Public controller `controllers/offer_public.py`
| Route | Verb | Auth | Behavior |
|---|---|---|---|
| `/booking/offer/<string:token>` | GET | `public`, website=False | Minimal server-rendered mobile page (inline CSS, mono flat colors, hf-wt-ico icons, no emoji): client name, 3 slot buttons, expiry note. Invalid/expired → friendly expired page |
| `/booking/offer/<string:token>/accept/<int:slot_index>` | POST (form) + GET fallback | `public` | Accept flow below; race-safe |

Accept flow (sudo, row-locked `SELECT ... FOR UPDATE` on offer):
1. Validate token, `state=='sent'`, not expired → else expired page.
2. Re-validate slot feasibility (matrix row still `remaining_capacity>0`); infeasible → page offering the remaining slots.
3. Create FSO: `{patient_id, facility_id, scheduled date/time from slot, service defaults}` (`VERIFY:` minimal required FSO create vals — mirror what `action_create_from_quick_booking_owl(vals)` (L5488) requires; prefer calling that method with an equivalent vals dict to inherit all its defaulting).
4. `fso.action_confirm_booking()` then `fso.action_assign_staff_to_fso(slot.staff_id.id, assignment_role='lead')` (L2489; `'lead'` is a confirmed `assignment_role` selection value: `lead/support/doctor/consultant/specialist/trainee`). Additionally reserve the slot via `health.staff.availability.matrix.book_staff_slot(staff_id, appointment_datetime, duration_minutes, fso_id=fso.id)` (confirmed public method).
5. Offer → `accepted`, `fso_id` set; other slots `taken=False` untouched; lead: post chatter message + (`VERIFY:` optional stage advance).
6. Confirmation page (booking ref, date/time, staff first name) + D.3 confirmation reminders fire naturally from `action_confirm_booking`.

Rate-limit token guessing: 10 req/min/IP on these routes via gateway counter (B.8) with `key_ref=ip`.

### Crons
`Visit offers: expire` hourly — `state='sent'`, `expires_at<now` → `expired` (+ lead activity "offer expired, call client").

### Acceptance
1. Moving a lead (with phone) into the flagged stage creates an offer with 3 feasible earliest slots and one ZNS delivery row; no phone → activity instead, no crash.
2. Slots honor availability matrix (capacity, conflicts, catchment) and are ranked by engine confidence; a fully-booked week yields whatever exists ≤3 with no error.
3. Tapping slot 2 creates a confirmed FSO assigned to that staff, marks offer accepted; the other two links now show "already booked".
4. Double-tap race (two devices) books exactly one FSO (row lock).
5. Expired link renders the expired page; cron expires offers and notifies the lead owner.
6. Booking created via offer triggers the standard reminder cascade (D) automatically.

## E.6 Security
ACLs: `health.visit.offer(+slot)` — sales users rw, public none (controller uses sudo); `health.timecard.mismatch` — HR officer rw, employee read-own record rule. No new groups; reuse `hr_attendance.group_hr_attendance_officer`, `sales_team.group_sale_salesman`.

---

# F. PWA additions summary (across A–E)

## F.1 New JS/Vue units (all under `health_pwa/static/src/js/`, served with `?v=${CACHE_VERSION}`)

| File | For | Notes |
|---|---|---|
| `utils/geofence-service.js` (`GeofenceService`) | A | watchPosition lifecycle + battery strategy (A.5), canonical-JSON + WebCrypto SHA-256 identical to server recipe A.2.2, emits `geofence:enter/exit` events consumed by visit screen |
| `components/SignaturePad.vue` | A | canvas capture → base64 PNG; offline-queueable |
| `components/EvvPromptSheet.vue` | A | bottom sheet: "Check in?" / "Check out?" one-tap on geofence events |
| `components/EvvStatusChip.vue` | A | visit header chip: fence distance, verified state |
| `components/OneTapCompleteSheet.vue` | E.2 | shown when `/onetap_eligible` true: single button + optional notes field; on `needs_review` routes to existing quote screen |
| `utils/evv-queue.js` | A | offline event queue on top of `storage-manager.js` store API (`VERIFY:` its exposed put/get API before coding; PouchDB per audit) |

Visit-offer accept pages are **server-rendered public pages** (E.5), NOT PWA screens. Clinical additions (MedListSheet.vue etc.) are in the clinical spec — excluded here.

## F.2 Local store additions (storage-manager)

- New store/db `evv_events`: docs `{_id: client_event_uuid, fso_id, event_type, event_datetime, lat, lng, accuracy_m, device_uuid, payload, client_hash, prev_client_hash, synced: false, image_b64?: (signatures only)}`.
- New store `evv_config`: per-FSO geofence `{fso_id, lat, lng, radius_m, enabled}` cached from `/evv/config` at sync time.
- `device_uuid` persisted in existing app storage (generate once, `crypto.randomUUID()`).

## F.3 Sync payload changes

- `/health_pwa/sync/changes` (GET, `sync.py:103`): FSO records in `_get_fso_changes` (sync.py:239) gain keys `geofence: {lat, lng, radius_m, enabled}` and `onetap_eligible: bool` — additive keys only; old clients ignore them (backward compatible).
- `/health_pwa/sync/push` (jsonrpc, `sync.py:429`): accept a new optional top-level key `evv_events: [...]` handled by a new `_process_evv_updates(evv_events)` that internally calls `health.evv.event.append_event` per event (same idempotency as `/health_pwa/api/evv/push`; that HTTP batch route remains for foreground flushes). Response mirrors existing per-model result arrays: `{'evv_events': {'accepted': n, 'results': [...]}}`.
- `sync-manager.js`: flush order — evv_events **before** fso status updates (so server-side start/complete hooks see the chain).

## F.4 Service worker (inline in `pwa_templates.xml`, from L851)

- Add the new JS/Vue asset URLs to the precache list (L870-874 block) with `?v=${CACHE_VERSION}`.
- EVV endpoints (`/health_pwa/api/**/evv/**`) must be **network-only** (never cached) — extend the existing API cache strategy's bypass list.
- Register Background Sync: `self.addEventListener('sync', e => { if (e.tag === 'evv-flush') ... })` posting a message to clients to trigger queue flush (actual flush runs in app context where storage-manager lives); app registers `sync` on going offline with pending events. Fallback (iOS, no BG sync): flush on `online` event + app resume.
- No push-payload changes required.

## F.5 Version bump — HARD DEPLOY RULE

Every deploy touching health_pwa assets/templates MUST bump the version string (currently `1.0.99`) in **`health_pwa/views/pwa_templates.xml`** at ALL occurrences:
1. L9 `<t t-set="pwa_asset_version">1.0.99</t>`
2. L246 `version: '1.0.99',`
3. L365 `const PWA_SW_VERSION = '1.0.99';`
4. L854 `const CACHE_VERSION = '1.0.99';` (+ comment L851)

All four literals must stay identical. Also bump `__manifest__.py` `'version'` (currently `19.0.1.0.13`). Deploy per the standard workflow (scp → /tmp → sudo cp with odoo ownership → `-u health_pwa` → restart) against DB `vietuat`.

## F.6 PWA acceptance criteria
1. With the app open and GPS granted, arriving within the radius raises the check-in sheet within 30 s; leaving after check-in raises check-out.
2. Airplane-mode visit: check-in, tasks, signature, check-out all queue; on reconnect everything syncs, server chain validates, no duplicates after forced double-flush.
3. High-accuracy GPS runs only near the fence (log instrumentation shows coarse polling elsewhere).
4. One-tap complete on an unchanged-quote visit: exactly one tap from visit screen to completed state incl. invoice, ≤5 s online.
5. Old cached PWA versions keep working against unchanged `/health_pwa/api/*` routes; after version bump, SW updates within one reload cycle.

---

## G. Cross-cutting notes for the implementing LLM

1. **UI:** mono flat colors only, `hf-wt-ico` CSS-mask SVG icons (never emoji/font-awesome), chatter at bottom full-width on any new form views.
2. **Coding conventions observed in this codebase:** controllers parse bodies with `json.loads(request.httprequest.data.decode('utf-8'))` inside try/except defaulting `{}`; broad `try/except Exception` returning 500 envelopes; `_logger` per file; selection helpers as module-level `_selection_*(model)` functions; timezone default `'Asia/Ho_Chi_Minh'`.
3. **Never** hard-depend new platform modules from existing ones — all wiring is `inherit` inside the new modules.
4. All `VERIFY:` markers are 1-file reads at implementation time; none change the architecture.
5. Pip prerequisites on UAT before install: `authlib`, `pydantic` (v2), `fhir.resources`.
6. This spec implements architecture-interop.md **Phase 1** (gateway + read-only facade + outbox/webhooks) and roadmap Horizon-0 items (reminder cascade, EVV foundation, exception-only completion, red-invoice batch, timecard autofill, instant first-visit offer) + the H1 items `health_api_gateway v1` and read-only FHIR facade.
