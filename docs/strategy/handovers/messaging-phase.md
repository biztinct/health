# Handover: Visit Messaging Cascade — `health_messaging`

Read `docs/strategy/HANDOVER-CONVENTIONS.md` FIRST. Definition of done is
its §8. This is the H0-automation / competitive-parity phase: booking
confirmations + visit reminders over Zalo ZNS with graceful fallback and
staff escalation. No competitor gap hurts VietUc more day-to-day than
silent no-shows.

## 0. Scope

One NEW module `addons/health_messaging`:

1. `health.outbound.message` — unified outbound log + queue (dedup,
   retry, dry-run).
2. Four automated purposes on `health.fieldservice.order`:
   `booking_confirmation` (on confirm), `reminder_24h`, `reminder_2h`
   (cron windows), `cancellation_notice` (on cancel).
3. Channel cascade per send: **ZNS → email → staff call-activity** —
   each step only when the previous is unavailable/failed.
4. Settings block (res.config.settings → ir.config_parameter): master
   enable, **dry_run (DEFAULT TRUE)**, the four ZNS template ids, quiet
   hours.
5. FSO smart button (message count) + outbound-log menu.

**Non-goals:** SMS provider integration (none exists in VN stack yet),
generic cascade-designer UI (steps are code, thresholds are config),
Zalo OA chat channel, marketing/bulk messaging (would need consent
gating — later phase uses `check_consent(partner, 'marketing')`),
patient portal, PWA changes (⇒ **no PWA bump**).

**⚠ SAFETY (binding):** vietuat contains real patient phone numbers.
`health_messaging.dry_run` defaults to **True**: the full pipeline runs
but the ZNS/email calls are skipped and the log row gets state
`simulated`. The live switch is a deliberate manual action later. Tests
must also never hit the network (mock the API boundary — Odoo blocks
external HTTP in tests anyway).

## 1. Existing plumbing to reuse (verified facts — do not re-invent)

- ZNS send: `health_zalo/services/zalo_api.py` →
  `send_zns_notification(config, phone, template_id, template_data)`;
  `config` is a `zalo.config` record; token refresh is handled inside
  (`get_valid_token()`, 5-min buffer + hourly cron). Raises UserError /
  returns error dicts — inspect `_make_request` for the exact failure
  shape and handle BOTH (exception and error-key result).
- Phone normalization: `normalize_vn_phone()` from
  `health_base.models.phone_utils` → `0xxxxxxxxx` or falsy when invalid.
- FSO facts: `scheduled_datetime` (UTC), `booking_timezone` (Char, IANA
  name), `state` selection
  draft/confirmed/assigned/in_progress/completed/completed_pending_invoice/
  cancelled/closed, `patient_id`, `patient_phone` (related mobile),
  `patient_email` (related), `facility_id`, `service_type` (Selection),
  `lead_staff_id`, `assigned_staff_ids`. There is NO existing
  reminder flag/cron anywhere — greenfield.
- Escalation pattern: `activity_schedule(activity_type_id=<todo ref>,
  summary=..., date_deadline=..., user_id=...)` exactly as
  health_incident/health_careplan do (try/except-wrapped, never breaks
  the caller).
- Settings pattern: `res.config.settings` fields with
  `config_parameter='health_messaging.<key>'` (see
  health_base/models/res_config_settings.py).

## 2. `health.outbound.message`

| Field | Type | Notes |
|---|---|---|
| name | Char, sequence `health.outbound.message` (prefix OM) | |
| purpose | Selection: booking_confirmation / reminder_24h / reminder_2h / cancellation_notice | index |
| channel | Selection: zns / email / staff_activity | which step actually ran |
| partner_id | m2o res.partner, required, ondelete='restrict', index | |
| fso_id | m2o health.fieldservice.order, index | |
| phone | Char | normalized, as sent |
| state | Selection: queued / sent / simulated / failed / skipped / escalated | default queued, index |
| error_text | Text | failure detail |
| payload_json | Json | template params actually used |
| sent_at | Datetime | |
| dedup_key | Char, index | e.g. `fso-<id>-reminder_24h` |
| catchment_province_id | computed from partner, stored | conventions §4 rule pair |
| company_id | m2o res.company | |

- `init()`: partial unique index on `dedup_key` (WHERE dedup_key IS NOT
  NULL AND != '') — conventions §5.1; pre-check in `create()` before
  super() per §5.3 (a duplicate dedup_key is NOT an error for callers:
  the queueing helper must search-first and no-op, the constraint is the
  race backstop).
- `action_retry()` on failed rows (manual, re-runs the cascade for that
  row's purpose).
- ACL: read nurse+, create/write via system flows (ops_manager+ for
  manual retry), unlink owner-only draft-style. Catchment rule pair.
  Menu under the health backoffice tree near the incident register.

## 3. The cascade engine (code, not config)

One model-level helper on `health.outbound.message`
(`@api.model process_purpose(fso, purpose)`), called by the cron and the
FSO hooks. Steps:

1. Guards (each produces state `skipped` + reason, never an exception):
   master enable off; FSO state not in (confirmed, assigned) — except
   `cancellation_notice` which fires from cancel; dedup row already
   exists; patient inactive.
2. Quiet hours: if the patient's local time (per FSO `booking_timezone`,
   fallback UTC) is within quiet hours (config, default 21:00–07:00),
   leave the row `queued` — the next cron tick re-picks queued rows
   whose quiet window has passed. (Cron must therefore process BOTH new
   windows and old `queued` rows.)
3. **ZNS step**: needs an active `zalo.config` + the purpose's template
   id (config param) + `normalize_vn_phone(patient_phone)` truthy. In
   dry_run → state `simulated`, store payload, stop. Live → call
   `send_zns_notification`; success → `sent`; failure (exception OR
   error-shaped result) → record error, fall through.
4. **Email step**: patient_email set → send via a module
   `mail.template` (create simple bilingual templates per purpose,
   data/noupdate). dry_run → `simulated`. Success → `sent`
   (channel=email). Failure → fall through.
5. **Escalation step**: `activity_schedule` a call task on
   `lead_staff_id.user_id`, else the facility manager's user (exact
   fallback chain: inspect how health_incident resolves the facility
   manager) — summary "Call patient to confirm visit", deadline =
   scheduled date. State `escalated`, channel=staff_activity.

Template params (all four purposes share the dict shape):
`{'patient_name', 'visit_date', 'visit_time', 'facility_name',
'service_type'}` — **visit_date/visit_time MUST be formatted in the
FSO's `booking_timezone` wall-clock** (pytz localize from the UTC
`scheduled_datetime`; conventions: the vis-timeline +7h class of bug is
the single most-hit timezone mistake in this codebase). `service_type`
uses the selection label (translated, vi first when patient lang is vi).

## 4. Triggers

- **FSO write hook** (inherit in this module): transition INTO
  `confirmed` → `process_purpose(fso, 'booking_confirmation')`;
  transition INTO `cancelled` (from confirmed/assigned only) →
  `cancellation_notice`. Both wrapped try/except (a messaging failure
  must NEVER block the booking workflow — log.exception and continue).
- **Cron** `cron_process_visit_messages` (every 15 minutes, noupdate):
  1. reminder_24h: FSOs state in (confirmed, assigned),
     `scheduled_datetime` between now+23h and now+24h → queue+process.
  2. reminder_2h: same, window now+1h45..now+2h.
  3. re-process rows still `queued` (quiet-hour deferrals).
  Window edges: dedup keys make overlap harmless — prefer slightly
  overlapping windows (e.g. 23h–24h15) over gaps so a delayed cron tick
  cannot silently skip a visit.
  Per-record try/except; one bad record never aborts the batch
  (conventions crons pattern).

## 5. Settings (res.config.settings, `health_messaging.*` params)

| Param | Default | UI label |
|---|---|---|
| enabled | False | Enable visit messaging |
| dry_run | True | Simulation mode (log only, no real sends) |
| zns_template_confirmation / _reminder24 / _reminder2 / _cancellation | '' | ZNS template IDs (from Zalo portal) |
| quiet_start / quiet_end | 21.0 / 7.0 (Float hours) | Quiet hours |

Settings view block titled "Visit Messaging (Zalo ZNS)" in the health
settings page (inspect where health_base's block renders; extend it).
Note `enabled=False` default: installing changes nothing until switched
on — state this in the module description.

## 6. FSO smart button + views

- Inherit FSO form: smart button "Messages (N)" (compute count of
  outbound messages for the order) opening the filtered log list.
- Outbound log: list (purpose, channel, partner, state badge, sent_at),
  form (readonly except retry button), search filters by purpose/state/
  channel + group-bys (conventions §5.10 search grammar).
- Flat mono colors; hf-wt-ico icons if any icon is needed; vi.po for all
  strings incl. the mail templates.

## 7. Tests (`tests/test_health_messaging.py`)

Mock at the service boundary:
`patch.object(type(<zalo api service object>), 'send_zns_notification')`
— inspect how health_zalo's own tests (if any) mock it; otherwise patch
where the cascade imports it. Cases:

1. Confirmation trigger: FSO draft→confirmed creates a log row; dry_run
   default → state `simulated`, payload has tz-correct visit_time
   (fixture: `booking_timezone='Asia/Ho_Chi_Minh'`, scheduled 02:00 UTC
   → visit_time "09:00").
2. Dedup: re-confirming / double cron run → exactly one row per
   (fso, purpose); helper no-ops, no ValidationError leaks to caller.
3. reminder_24h cron window: FSO at now+23.5h queues; FSO at now+30h
   does not; state filter respected (draft/cancelled excluded).
4. Cascade fallback (dry_run OFF via config in-test, ZNS mock raising):
   patient with email → channel=email; patient without email and ZNS
   failing → `escalated` + activity exists on lead staff user.
5. No zalo.config / no template id → ZNS step skipped cleanly, email
   step attempted (no crash).
6. Quiet hours: send at patient-local 23:00 stays `queued`; cron re-run
   with mocked now inside allowed hours processes it (freeze via
   config-param quiet window manipulation rather than clock mocking if
   simpler).
7. Cancellation from confirmed sends; cancellation from draft does not.
8. Invalid phone (normalize returns falsy) + no email → escalated.
9. FSO write hook resilience: cascade helper raising is swallowed
   (patch it to raise; confirm state transition still succeeds).

Fixture note (conventions §6): patients need `catchment_province_id`;
FSO needs facility+patient+scheduled_datetime; confirming may require
quote/stage prerequisites — inspect existing FSO tests (health_evv's
`_make_fso` + write state directly is the established shortcut).

## 8. Deploy & verify

- `-i health_messaging --test-tags /health_messaging`. No PWA bump.
- Live verify (safe because enabled=False + dry_run=True): flip
  `enabled` on via Settings on vietuat, confirm a demo FSO
  (demo clients 861–864 exist), check the smart button shows a
  `simulated` confirmation row with correct wall-clock params, then
  toggle `enabled` back OFF and say so in the report. Do NOT enable
  live mode.
- Conventions §8 throughout (tests green quote, login 200, vi.po,
  commit+push).

## 9. Report-back extras

(a) exact FSO state-transition hook point used (write override vs
action method) and why; (b) the mock boundary used for ZNS in tests;
(c) the demo FSO used for live dry-run verification + the simulated
payload; (d) confirm `enabled` left OFF on vietuat.
