# health_telemonitoring — Phase 1: NEWS2 early-warning + deterioration triage inbox

Phase 1 of the **telemonitoring → twin** arc (strategy report: recommended next
group now health_emr is complete; records FA-025 priority 4.45, AI-013, feeding
IF-016/IF-001 later). Motto: **"every nurse visit becomes a screening event."**

Read `HANDOVER-CONVENTIONS.md` first — §2 deploy, §3 PWA bump, §5 gotcha
ledger, §6 fixtures, §7 interfaces. This doc contains all plumbing facts you
need, pre-verified with file:line references — **do not re-derive them**.

---

## 0. Scope and binding non-goals

**Build (one new module + sanctioned edits):**
1. New module `addons/health_telemonitoring` (19.0.1.0.0).
2. Two new vitals-catalog types seeded from THIS module: ACVPU consciousness
   + supplemental-O₂ flow.
3. `res.partner.news2_spo2_scale2` flag (hypercapnic/COPD patients) + patient
   form checkbox.
4. `health.ews.score` — NEWS2 computed automatically at every vitals capture.
5. `health.monitor.alert` — deterioration **triage inbox** fed by (a) NEWS2
   bands, (b) existing per-client threshold breaches (mirror), (c) a nightly
   baseline/trend cron (4 statistical rules, pure Python — no LLM).
6. Backend views/menus + settings block.
7. PWA: ACVPU picker + O₂ toggle in the existing vitals entry sheet, NEWS2
   band chip in the post-save banner (sanctioned `health_vitals` edits only).
8. Tests + `i18n/vi.po`.

**Binding NON-goals (do not build, do not scaffold):**
- NO device registry / device ingestion API / wearables (that is Phase 2).
- NO ZNS, SMS, email, or family-facing notification of any kind. The
  messaging rails stay untouched (`health_messaging.enabled=False`,
  `dry_run=True` on vietuat — do not flip anything).
- NO LLM/Ollama narrative summaries (later phase).
- NO FHIR serializer for `health.ews.score` (later; note: NEWS2 total has no
  settled LOINC in our catalog — deliberately deferred).
- NO ECharts/BI dashboards, NO biz_bi datasets, NO health_twin anything.
- NO changes to `health.vitals.threshold` semantics — existing behaviour must
  be preserved bit-for-bit (test 14 proves super() still runs).

---

## 1. Verified plumbing facts (do not re-derive)

All paths relative to `addons/`.

**health_vitals (v19.0.1.0.0, depends health_base/health_fieldservice/health_pwa):**
- `health.observation` — `health_vitals/models/health_observation.py:22`;
  `@api.model_create_multi create()` at `:171-172`; threshold check
  `_check_thresholds()` `:242` runs inside create (`:186`), escalation
  `_escalate_threshold_breach(threshold)` `:294` (actions none/chatter/
  activity/activity_author; failures caught `:271-275` — never block save).
  Append-only unlink guard `:209-221`. Trend index (client, type, datetime)
  `:108-116`. `get_trend(client_id, vitals_type_id, date_from=None, …)`
  `:444` excludes `entered_in_error` (TREND_STATES = final+amended).
- Public interfaces (conventions §7): `create_coded(patient_id, loinc_code,
  value, uom=None, fso_id=None, effective_datetime=None, performer_id=None,
  source='manual', note=None)` `:352`; `create_panel(client_id,
  panel_type_code, components, …)` `:398`. NOTE: `source` is **not a stored
  field** — it is folded into the note text (`:387-390`). Do not add one.
- `health.vitals.type` — `health_vitals/models/health_vitals_type.py:12`;
  `get_by_code(code)` `:80-94` resolves LOINC OR short code;
  `value_type` ∈ quantity/string/panel; `plausible_min/max` hard-validate
  quantity input. Catalog seeds (`health_vitals/data/health_vitals_type_data.xml`):
  `bp_sys` 8480-6, `bp_dia` 8462-4 (children of `bp_panel` 85354-9), `hr`
  8867-4, `rr` 9279-1, `temp` 8310-5, `spo2` 2708-6, `spo2_po` 59408-5
  (PWA default), `weight` 29463-7, `height`, `bmi`, `glucose`, `pain`.
  **ACVPU and O₂ do NOT exist — you seed them (§2.1).**
- BP panel children are REAL `health.observation` rows with type `bp_sys` /
  `bp_dia` (`create_panel` creates parent + child rows) — so "latest bp_sys
  in window" is a plain search, no panel traversal needed.
- `health.vitals.threshold` — `health_vitals/models/health_vitals_threshold.py:17`;
  severity warning/critical; `escalation_action` selection `:36-42`.
- Security: catchment ir.rules at `health_vitals/security/health_vitals_security.xml:9-28`
  (pattern: `['&', ('catchment_province_id','=',user.catchment_province_id.id),
  ('catchment_province_id','!=',False)]` + owner rule) — **clone for both new
  models**. `catchment_province_id` on observation is computed+stored from
  client — clone that compute too.
- PWA controller — `health_vitals/controllers/api.py`:
  `POST /health_pwa/api/fso/<id>/vitals` builds `created` recordset (loose
  items via `Observation.create`, BP via `create_panel`, children added to
  `created`), then returns `_prepare_json_response(data={'created_ids':
  created.ids, 'alerts': [self._serialize_alert(o) …]})` (`:198-204`;
  `_serialize_alert` `:81`). String-type observations already flow:
  `vals['value_text'] = str(item.get('value'))` for `value_type=='string'`
  — so ACVPU capture needs **zero** controller change; only the response
  gains an `ews` key (§2.6).
- PWA JS — `health_vitals/static/src/js/vitals-components.js`:
  `ENTRY_CODES = ['hr','rr','temp','spo2_po','weight','pain']` `:83`; fields
  rendered in loop `:195`; save path calls `this._showAlerts(result.alerts)`
  `:273`, method at `:284`. Types catalog cached 24 h in localStorage by
  `vitals-service.js` (`health_vitals_types`); offline outbox + auto-flush
  already handled — do not touch `vitals-service.js`.
- PWA assets injected via `health_vitals/views/pwa_shell_inherit.xml` with
  `?v=#{pwa_asset_version}` → **§3 PWA version bump applies** to this phase.

**Precedents to clone:**
- Triage queue: `health_ai_coding/models/ai_code_suggestion.py:51-100`
  (states + `action_approve` `:429` with approver-group gate `:412-418`);
  list badges + `search_default` context
  `health_ai_coding/views/ai_code_suggestion_views.xml:9-11,114-115`; menu
  under `health_base.menu_healthcare_clinical`
  (`health_ai_coding/views/ai_coding_menus.xml:4-12`).
- mail.activity: `activity_schedule(activity_type_id=env.ref(
  'mail.mail_activity_data_todo').id, summary=…, user_id=…)` — precedent
  `health_messaging/models/health_outbound_message.py:301-323`; facility-
  manager-user resolution: clone the `_escalate_threshold_breach` lookup in
  `health_vitals/models/health_observation.py:313-324`.
- Config gate + settings UI: `health_workflow_auto/models/res_config_settings.py`
  (`config_parameter=` fields) + `health_workflow_auto/views/res_config_settings_views.xml`
  (inherit `health_base.res_config_settings_view_form_health`, add
  `<block>` inside `//app[@name='health_base']`); noupdate=1 param seeds
  `health_workflow_auto/data/workflow_config_params.xml`. Param naming:
  `health_telemonitoring.<key>`.
- Cron with per-record savepoint + batch cap:
  `health_workflow_auto/models/timecard_mismatch.py:104+` (savepoint per
  record `:129+`), cap pattern `health_ai_coding/models/ai_code_suggestion.py:313`.
- Patient form inherit: `health_vitals/views/res_partner_views.xml:9`
  inherits `health_base.view_health_patient_form` (button_box + notebook
  xpaths) — read that file for its view id and add your checkbox INTO the
  page health_vitals adds there (your module depends on health_vitals, so
  inheriting its partner view is clean).

---

## 2. Architecture

New module `health_telemonitoring`, `depends`: `['health_vitals',
'health_fieldservice', 'health_base', 'mail']` (health_pwa arrives
transitively via health_vitals; do NOT list web/biz_bi).

### 2.1 Catalog seeds (data/telemonitoring_vitals_type_data.xml)

Two `health.vitals.type` records (regular data, not noupdate — same as
health_vitals seeds):

| xml id | code | loinc_code | name | value_type | unit | plausible | notes |
|---|---|---|---|---|---|---|---|
| `vitals_type_acvpu` | `acvpu` | `67775-7` | Level of consciousness (ACVPU) | `string` | — | — | value_text one of A/C/V/P/U |
| `vitals_type_o2_flow` | `o2_flow` | `3151-8` | Supplemental oxygen flow rate | `quantity` | ucum `L/min`, display `L/min` | 0–60, decimals 1 | 0 or absent = breathing air |

`is_fhir_vital_sign=False` for both, `sequence` after pain. Vietnamese
`name_vi`: `Mức độ ý thức (ACVPU)` / `Lưu lượng oxy hỗ trợ`.

### 2.2 res.partner extension (models/res_partner.py)

`news2_spo2_scale2` Boolean, default False, `tracking=True`, string
"NEWS2 SpO₂ Scale 2 (hypercapnic)", help text naming COPD/target 88–92 %.
View: checkbox on the patient form inside the health_vitals-added notebook
page (§1 last bullet), visible/editable per that page's existing group
gating (do not invent new groups).

### 2.3 `health.ews.score` (models/health_ews_score.py)

System-generated, append-only. `_order = 'score_datetime desc, id desc'`.

Fields:
- `client_id` M2O res.partner, required, index, ondelete='restrict',
  domain is_patient.
- `order_id` M2O health.fieldservice.order, index, ondelete='set null'.
- `score_datetime` Datetime, required, index (= anchor, §2.5).
- Component value snapshot: `rr_value`, `spo2_value`, `sbp_value`,
  `hr_value` Float; `temp_value` Float (1 dp); `acvpu_value` Char(1);
  `on_oxygen` Boolean; `spo2_scale` Selection [('1','Scale 1'),('2','Scale 2')].
- Component subscores (Integer): `rr_score`, `spo2_score`, `o2_score`,
  `bp_score`, `hr_score`, `temp_score`, `consciousness_score`.
- `total` Integer, index. `band` Selection
  [('low','Low'),('low_medium','Low-Medium'),('medium','Medium'),('high','High')],
  index.
- `defaulted_consciousness` Boolean — True when ACVPU was not recorded in
  the window and 'A' was assumed (honesty flag, shown in UI).
- `superseded` Boolean default False, index.
- `observation_ids` M2M health.observation (evidence — the rows actually used).
- `catchment_province_id` computed+stored from client (clone observation's
  compute), `company_id`.

No mail.thread (system rows). Guards: `unlink()` raises UserError unless
admin/system (clone `health_observation.py:209-221`); `write()` allows only
`superseded` (+ mail/system fields) after create — everything else raises.
Rows are created **sudo by the engine only**; ACL gives clinical groups
read-only (§2.9).

### 2.4 NEWS2 kernel — use as-is

Put in `models/news2.py` as module-level pure functions. **kernel — use
as-is** (RCP NEWS2 tables; boundaries are inclusive as written):

```python
# kernel — use as-is
ACVPU_VALUES = ('A', 'C', 'V', 'P', 'U')


def news2_component_scores(rr, spo2, on_oxygen, sbp, hr, temp,
                           acvpu='A', scale2=False):
    """Pure NEWS2 (RCP, Dec 2017) component scoring. All args numeric
    except acvpu (one of ACVPU_VALUES) and booleans. Returns dict with the
    seven component scores. Raises ValueError on invalid acvpu."""
    if acvpu not in ACVPU_VALUES:
        raise ValueError('invalid ACVPU value: %r' % (acvpu,))
    s = {}
    # Respiration rate (breaths/min)
    if rr <= 8:
        s['rr_score'] = 3
    elif rr <= 11:
        s['rr_score'] = 1
    elif rr <= 20:
        s['rr_score'] = 0
    elif rr <= 24:
        s['rr_score'] = 2
    else:
        s['rr_score'] = 3
    # SpO2 (%)
    if not scale2:
        if spo2 <= 91:
            s['spo2_score'] = 3
        elif spo2 <= 93:
            s['spo2_score'] = 2
        elif spo2 <= 95:
            s['spo2_score'] = 1
        else:
            s['spo2_score'] = 0
    else:
        # Scale 2 (hypercapnic respiratory failure, target 88-92%)
        if spo2 <= 83:
            s['spo2_score'] = 3
        elif spo2 <= 85:
            s['spo2_score'] = 2
        elif spo2 <= 87:
            s['spo2_score'] = 1
        elif spo2 <= 92:
            s['spo2_score'] = 0
        elif on_oxygen and spo2 <= 94:
            s['spo2_score'] = 1
        elif on_oxygen and spo2 <= 96:
            s['spo2_score'] = 2
        elif on_oxygen:
            s['spo2_score'] = 3
        else:
            s['spo2_score'] = 0   # >=93 on air, scale 2
    # Air or oxygen
    s['o2_score'] = 2 if on_oxygen else 0
    # Systolic blood pressure (mmHg)
    if sbp <= 90:
        s['bp_score'] = 3
    elif sbp <= 100:
        s['bp_score'] = 2
    elif sbp <= 110:
        s['bp_score'] = 1
    elif sbp <= 219:
        s['bp_score'] = 0
    else:
        s['bp_score'] = 3
    # Pulse (bpm)
    if hr <= 40:
        s['hr_score'] = 3
    elif hr <= 50:
        s['hr_score'] = 1
    elif hr <= 90:
        s['hr_score'] = 0
    elif hr <= 110:
        s['hr_score'] = 1
    elif hr <= 130:
        s['hr_score'] = 2
    else:
        s['hr_score'] = 3
    # Temperature (°C)
    if temp <= 35.0:
        s['temp_score'] = 3
    elif temp <= 36.0:
        s['temp_score'] = 1
    elif temp <= 38.0:
        s['temp_score'] = 0
    elif temp <= 39.0:
        s['temp_score'] = 1
    else:
        s['temp_score'] = 2
    # Consciousness (ACVPU: any non-Alert scores 3)
    s['consciousness_score'] = 0 if acvpu == 'A' else 3
    return s


def news2_band(scores):
    """(total, band) from a component-score dict.
    Bands: 0-4 low; any single component == 3 -> low_medium;
    5-6 medium; >=7 high."""
    total = sum(scores.values())
    if total >= 7:
        band = 'high'
    elif total >= 5:
        band = 'medium'
    elif max(scores.values()) >= 3:
        band = 'low_medium'
    else:
        band = 'low'
    return total, band
```

### 2.5 Scoring engine (trigger + window assembly)

In `models/health_observation.py` (telemonitoring's inherit of
`health.observation`):

- Override `create()` (`@api.model_create_multi`, call super first) and
  `write()` (only when `value_quantity` or `value_text` changes — this is
  the amendment path, base flips state to 'amended'). After the base call,
  invoke `self.env['health.ews.score'].sudo()._score_from_observations(records)`
  wrapped in `try/except Exception: _logger.exception(...)` — **scoring must
  never block a vitals save** (clone the base's escalation guard style
  `health_observation.py:271-275`).
- Gate: skip entirely unless config `health_telemonitoring.ews_enabled`
  (default True).

`_score_from_observations(observations)` on `health.ews.score`:
1. Consider only rows with `state in ('final','amended')` and
   `vitals_type_id.code in RELEVANT` where
   `RELEVANT = {'rr','spo2','spo2_po','bp_sys','hr','temp','acvpu','o2_flow'}`.
   Group by `client_id`.
2. Per client: `anchor = max(effective_datetime)` of that client's relevant
   triggering rows; window `[anchor - W, anchor]`,
   `W = int(param 'health_telemonitoring.ews_window_minutes', 60)` minutes.
3. Pick the LATEST final/amended observation in-window per component
   (one search per component, ordered `effective_datetime desc, id desc`,
   limit 1): `rr`; `spo2` = latest across BOTH `spo2` and `spo2_po`;
   `sbp` = `bp_sys`; `hr`; `temp`. **All five required** — if any missing,
   log debug and skip (no score).
4. `acvpu`: latest in-window `acvpu` row; take
   `(value_text or '').strip().upper()[:1]`; if missing/invalid → `'A'`
   with `defaulted_consciousness=True`.
5. `on_oxygen`: latest in-window `o2_flow` with `value_quantity > 0` → True.
6. `scale2 = client.news2_spo2_scale2`; store `spo2_scale`.
7. Compute via kernel; supersede: search existing scores for the client,
   `superseded=False`, `score_datetime >= anchor - W` → write
   `superseded=True` (sudo). Then create the new row (sudo):
   snapshot values, subscores, total, band, `score_datetime=anchor`,
   `order_id` = the anchor observation's `order_id`, `observation_ids` =
   the rows used (components + acvpu + o2 rows actually read).
8. After create: hand off to alerts — `self.env['health.monitor.alert']
   .sudo()._raise_for_ews(score)` (§2.7), same never-block guard.

### 2.6 PWA response + entry sheet (sanctioned health_vitals edits)

**Controller** `health_vitals/controllers/api.py` — in the POST
`/health_pwa/api/fso/<id>/vitals` handler, just before
`_prepare_json_response` (`:198`), add:

```python
ews_payload = None
if 'health.ews.score' in request.env and created:
    score = request.env['health.ews.score'].sudo().search(
        [('observation_ids', 'in', created.ids),
         ('superseded', '=', False)],
        order='id desc', limit=1)
    if score:
        ews_payload = {
            'total': score.total,
            'band': score.band,
            'defaulted_consciousness': score.defaulted_consciousness,
        }
```
and include `'ews': ews_payload` in `data`. (Registry guard keeps
health_vitals installable without telemonitoring.)

**Entry sheet** `health_vitals/static/src/js/vitals-components.js`:
- Do NOT extend `ENTRY_CODES` (`:83`). After the numeric fields loop
  (`:195`), render two extra controls ONLY if the cached types catalog
  contains codes `acvpu` / `o2_flow` (graceful when telemonitoring is not
  installed):
  - ACVPU: a 5-button segmented row (A C V P U), optional — untouched ⇒ no
    observation sent. Label vi: "Ý thức (ACVPU)".
  - O₂: a toggle "Đang thở oxy" revealing a numeric flow input (L/min,
    default 2, min 0.5, max 60). Toggle on ⇒ send `{code:'o2_flow',
    value:<flow>}`; off ⇒ send nothing.
- Post-save: extend the result handling around `_showAlerts` (`:273,284`) —
  if `result.ews` present, render a NEWS2 chip ABOVE threshold alerts:
  `NEWS2: <total> — <band label>`; band colors flat mono (low: existing
  success green token, low_medium: amber, medium: orange, high: red — reuse
  the palette already used for warning/critical banners in this file; no
  gradients). If `defaulted_consciousness`, append "(ý thức mặc định A)".
- Vietnamese-first labels like the rest of the sheet.

**Version bumps:** `health_vitals/__manifest__.py` → `19.0.1.1.0`. PWA
asset version per conventions §3: read the CURRENT value from
`health_pwa/views/pwa_templates.xml`, bump minor, update ALL 5 places +
`health_pwa/__manifest__.py` + the co-resident PIN TESTS
(health_pwa_daystrip, health_scribe, health_pwa_family) in the same change.

### 2.7 `health.monitor.alert` — triage inbox (models/health_monitor_alert.py)

`_inherit = ['mail.thread']`, `_order = 'create_date desc'`.

Fields: `client_id` (M2O partner, required, index, ondelete='restrict'),
`order_id` (M2O FSO, set null), `rule` Selection
`[('ews_high','NEWS2 high'),('ews_medium','NEWS2 medium'),
('ews_single3','NEWS2 single-parameter 3'),('threshold','Threshold breach'),
('trend_hr_drift','Resting HR drift'),('trend_sbp_drift','Systolic BP drift'),
('trend_spo2_decline','SpO2 decline'),('trend_weight_loss','Weight loss')]`
(required, index), `severity` Selection warning/critical (required, index),
`state` Selection `[('new','New'),('acknowledged','Acknowledged'),
('resolved','Resolved'),('dismissed','Dismissed')]` default 'new', index,
`tracking=True`; `title` Char required; `body` Text (human-readable
evidence); `evidence_json` Text (machine evidence for future sparklines);
`vitals_type_id` M2O optional; `ews_score_id` M2O `health.ews.score`
optional; `observation_ids` M2M; `ack_user_id`/`ack_date`,
`closed_user_id`/`closed_date`, `close_note` Text;
`catchment_province_id` computed+stored from client; `company_id`.

Creation is **sudo, engine-only**. Open-dedup helper:

```python
def _open_exists(self, client_id, rule, vitals_type_id=False):
    dom = [('client_id', '=', client_id), ('rule', '=', rule),
           ('state', 'in', ('new', 'acknowledged'))]
    if vitals_type_id:
        dom.append(('vitals_type_id', '=', vitals_type_id))
    return bool(self.search_count(dom))
```

Raisers (each: dedup-check → create → escalate-if-critical):
- `_raise_for_ews(score)`: band high → rule `ews_high`, severity critical;
  band medium → `ews_medium`, warning; band low_medium → `ews_single3`,
  warning; band low → nothing. Title e.g. "NEWS2 7 — cao — Nguyễn Văn A";
  body lists component values+subscores; link `ews_score_id`,
  `observation_ids`, `order_id`.
- `_raise_for_threshold(observation, threshold)`: rule `threshold`,
  severity = threshold.severity, `vitals_type_id` set (dedup includes it).
- Trend raisers from the cron (§2.8).

Escalation: when `severity == 'critical'` and param
`health_telemonitoring.activity_on_critical` (default True) → schedule a
mail.activity (todo) on the **client** for the facility-manager user
(clone the resolution in `health_vitals/models/health_observation.py:313-324`),
summary = alert title, wrapped in the never-block guard.

**Threshold mirror:** in the telemonitoring `health.observation` inherit,
override `_escalate_threshold_breach(self, threshold)`: `res =
super()._escalate_threshold_breach(threshold)` FIRST (existing behaviour
untouched), then `_raise_for_threshold(self, threshold)` under the
never-block guard, return res.

Lifecycle methods (group gates INSIDE the method, ai_coding style
`ai_code_suggestion.py:412-429`):
- `action_acknowledge()` — any of nurse/head_nurse/doctor/ops-manager/
  manager/admin; state new→acknowledged, stamp ack_user/date.
- `action_resolve()` — head_nurse/doctor/manager/admin only; →resolved,
  stamp closed_*.
- `action_dismiss()` — same closer groups; requires non-empty `close_note`
  else `UserError`; →dismissed.
- All raise UserError on wrong start state.

### 2.8 Nightly trend cron (models + data/telemonitoring_cron.xml)

`ir.cron` "Telemonitoring: nightly deterioration trend sweep", model
`health.monitor.alert`, method `cron_trend_sweep()`, daily, `noupdate="1"`,
nextcall ~19:30 UTC (= 02:30 ICT). Gate: param
`health_telemonitoring.trend_enabled` (default True) — return early when off.

`cron_trend_sweep()`:
1. Candidates: `read_group` over `health.observation`
   (state final/amended, `effective_datetime >= now-28d`,
   `vitals_type_id.code in ('hr','bp_sys','spo2','spo2_po','weight')`)
   grouped by `client_id`, keep those with ≥
   `trend_min_points` (param, default 5) rows, ordered by client id,
   capped at `trend_batch_cap` (param, default 200). If capped, `_logger.info`
   how many were dropped (no silent caps).
2. Per client, inside `with self.env.cr.savepoint():` + per-client
   try/except-log (clone `timecard_mismatch.py:129+`):
   pull series via `env['health.observation'].get_trend(...)`
   (`health_observation.py:444`) for the trailing 28 days, split at 7 days
   ago into RECENT (last 7d) and PRIOR (28d→7d ago), medians via
   `statistics.median`. Rules (skip a rule when either side has <3 points,
   except weight — see below; all params are config, defaults shown):
   - `trend_hr_drift` (warning): median(HR recent) − median(HR prior)
     ≥ `hr_drift_bpm` (15).
   - `trend_sbp_drift` (warning): abs(median(SBP recent) − median(SBP
     prior)) ≥ `sbp_drift_mmhg` (20). SBP series = code `bp_sys`.
   - `trend_spo2_decline` (critical): SpO₂ series = union of `spo2` and
     `spo2_po` merged by datetime; median(recent) ≤ median(prior) −
     `spo2_drop_pp` (3) AND median(recent) < 94.
   - `trend_weight_loss` (warning): within the last 14 days, earliest and
     latest weight ≥ 5 days apart, and
     `(w_first - w_last)/w_first * 7/days_between * 100 ≥
     weight_loss_pct_per_week` (2.0).
3. Each firing: `_open_exists(client, rule)` dedup, then create alert with
   `body` (values + medians + threshold, human-readable, Vietnamese-first)
   and `evidence_json` = `json.dumps({'points': [[iso, v], …],
   'median_recent': x, 'median_prior': y, 'threshold': z},
   sort_keys=True)`.

No `datetime.now()` traps here — use `fields.Datetime.now()` /
`fields.Date` helpers throughout (ledger §5.35 discipline).

### 2.9 Security (security/)

- `ir.model.access.csv`: `health.ews.score` — read for
  `health_base.group_healthcare_base`; create/write/unlink 0 (engine is
  sudo); full for admin group. `health.monitor.alert` — read+write for
  `group_healthcare_nurse` and up (write needed for the state buttons;
  method gates enforce WHO may transition), create 0, unlink admin only.
- `telemonitoring_security.xml`: catchment + owner ir.rules for BOTH models,
  cloned verbatim-in-shape from
  `health_vitals/security/health_vitals_security.xml:9-28`.

### 2.10 Views + menus (views/)

- `health_ews_score_views.xml`: list (datetime, client, total, band badge —
  decoration-danger high / decoration-warning medium+low_medium,
  defaulted_consciousness icon column, superseded filter default-off), form
  (readonly, component table, evidence observations list), search (band
  filters, group by client). No create/edit from UI (`create="0"
  edit="0"` on list).
- `health_monitor_alert_views.xml`: list `create="0"`
  (decoration-danger `severity=='critical' and state in ('new','acknowledged')`,
  decoration-muted resolved/dismissed; badges on severity/state/rule), form
  with header buttons Acknowledge/Resolve/Dismiss (invisible per state,
  Dismiss requires filling `close_note` on the form first), chatter at
  bottom full-width (house rule), evidence tab (body, observations,
  ews_score link). Search: `search_default_state_new` +
  `search_default_group_client` in the action context (clone
  `ai_code_suggestion_views.xml:114-115`); filters My catchment handled by
  ir.rule anyway.
- `telemonitoring_menus.xml`: root menu **Telemonitoring** under
  `health_base.menu_healthcare_clinical` sequence 45; children
  "Deterioration Alerts" (the inbox — sequence 10) and "NEWS2 Scores"
  (sequence 20).
- `res_partner_views.xml`: scale-2 checkbox (§2.2).
- `res_config_settings_views.xml`: block "Telemonitoring" with
  `tm_ews_enabled`, `tm_trend_enabled`, `tm_ews_window_minutes`,
  `tm_activity_on_critical` (Integer/Boolean fields with
  `config_parameter=…`, workflow_auto precedent). Trend thresholds stay
  param-only (no UI) this phase.
- `data/telemonitoring_config_params.xml` (`noupdate="1"`): ews_enabled=True,
  ews_window_minutes=60, trend_enabled=True, trend_batch_cap=200,
  trend_min_points=5, hr_drift_bpm=15, sbp_drift_mmhg=20, spo2_drop_pp=3,
  weight_loss_pct_per_week=2.0, activity_on_critical=True.

### 2.11 Sanctioned edits (exhaustive — everything else is read-only)

| Module | File | What may change |
|---|---|---|
| health_telemonitoring | (new module) | everything |
| health_vitals | `controllers/api.py` | add `ews` key to the POST vitals response (§2.6 block) — nothing else |
| health_vitals | `static/src/js/vitals-components.js` | ACVPU picker, O₂ toggle, NEWS2 chip (§2.6) |
| health_vitals | `__manifest__.py` | version → 19.0.1.1.0 |
| health_pwa | `views/pwa_templates.xml`, `__manifest__.py` | §3 version bump ONLY |
| health_pwa_daystrip / health_scribe / health_pwa_family | version PIN TESTS | pin value only |

NO edits to health_fieldservice, health_messaging, health_base python,
health_emr, health_careplan, health_forms.

---

## 3. Safety rails (binding)

- `health_messaging.enabled=False`, `health_messaging.dry_run=True`,
  `health_family_messages.enabled=False`,
  `health_workflow_auto.timecard_sync_enabled=False` — verify-only; never
  flip. ZNS template params stay `''`.
- No pip installs on the server. `statistics` is stdlib.
- vietuat has REAL patient data/phones — no test messages of any kind.
- Scoring + alert raising must NEVER block or roll back a vitals save
  (guards specified above; test 21 proves it).
- QA fixtures on vietuat: clean up per §5.34 — verify deletions in a FRESH
  shell/cursor before claiming clean.

---

## 4. Tests (tests/test_telemonitoring.py, @tagged('post_install','-at_install'))

Fixtures per conventions §6 (catchment province + facility + patient;
FSO needs facility+patient+scheduled_datetime). Trend histories: set
`effective_datetime` directly (it is a plain field — no SQL backdating
needed; do NOT confuse with the §5.33 write_date trap).

1. Kernel boundaries — loop the RCP table edges: RR 8/9/11/12/20/21/24/25;
   SpO₂ scale1 91/92/93/94/95/96; scale2 83/84/85/87/88/92 + on-O₂
   93/94/95/96/97 + on-air 93; O₂ on/off; SBP 90/91/100/101/110/111/219/220;
   HR 40/41/50/51/90/91/110/111/130/131; temp 35.0/35.1/36.0/36.1/38.0/38.1/
   39.0/39.1; ACVPU A/C/V/P/U. Assert exact component scores.
2. Bands: totals 0→low, 4→low, 5→medium, 7→high; single component 3 with
   total 3 → low_medium. Invalid ACVPU raises ValueError.
3. E2E capture: full set via `create_coded` ×4 (`rr`,`hr`,`temp`,`spo2_po`)
   + `create_panel` bp → exactly one non-superseded score; correct
   total/band; `observation_ids` populated; `order_id` set; snapshot values
   match.
4. Missing component (no temp) → no score created.
5. No ACVPU row → score has `acvpu_value='A'`, `defaulted_consciousness=True`.
6. `o2_flow` 2.0 → `on_oxygen=True`, `o2_score=2`.
7. Scale 2: patient flag on, SpO₂ 91 on air → spo2_score 0 (scale1 would be
   3); `spo2_scale='2'` stored.
8. Second capture 10 min later → first score `superseded=True`, one current.
9. Amendment: write `value_quantity` on the HR row → new score created,
   previous superseded (write-path trigger works).
10. `ews_enabled=False` param → capture creates NO score.
11. Band high → alert `ews_high` critical + mail.activity on client for
    facility manager (activity_on_critical default True).
12. Band medium → `ews_medium` warning, NO activity.
13. Band low_medium → `ews_single3` warning. Band low → no alert.
14. Threshold mirror: breaching `health.vitals.threshold`
    (escalation_action='activity') → BOTH the pre-existing activity
    (super() ran) AND a `threshold` inbox alert with `vitals_type_id` set.
15. Open-dedup: second high score while `ews_high` alert open (new/ack) →
    no second alert; after `action_resolve()` a new high score DOES raise
    a fresh alert.
16. Trend HR drift: prior-21d HR history median 70, recent-7d median 90 →
    `trend_hr_drift` warning with evidence_json medians.
17. Trend weight loss ≥2 %/week over ≥5-day span → `trend_weight_loss`.
18. Trend SpO₂ decline: prior 97, recent 92 → `trend_spo2_decline` critical.
19. `trend_enabled=False` → cron creates nothing; batch cap: set
    `trend_batch_cap=1` with 2 eligible clients → 1 processed (assert the
    drop is logged is optional).
20. Lifecycle: acknowledge stamps ack_*; dismiss without `close_note` raises
    UserError; nurse user CAN acknowledge but CANNOT resolve (UserError);
    head-nurse resolve works.
21. Never-block: monkeypatch `_score_from_observations` to raise →
    observation create still succeeds, no score, exception logged.
22. Append-only: nurse `unlink()` on score and on alert raises; alert
    create by non-sudo nurse denied (ACL).
23. HttpCase `TestTelemonitoringHttp`: authenticate as nurse, POST
    `/health_pwa/api/fso/<id>/vitals` with full set incl.
    `{'code':'acvpu','value':'V'}` and `{'code':'o2_flow','value':2}` →
    response `data.ews.total/band` correct (consciousness 3 + o2 2 included).
    Per ledger §5.32: pin OFF `health_workflow_auto.timecard_sync_enabled`
    (and any other side-effect switches you rely on absent) in setUp,
    restore in tearDown. Deploy note: HttpCase present ⇒ do NOT pass
    `--no-http`, keep `--workers 0`.

---

## 5. Deploy / verify (conventions §2)

- `scp` → `/tmp` → `sudo cp` → `chown odoo:odoo` for: `health_telemonitoring`
  (new), `health_vitals`, `health_pwa`, + the three pin-test modules.
- Stop server, port-wait, then:
  `-i health_telemonitoring -u health_vitals,health_pwa,health_pwa_daystrip,health_scribe,health_pwa_family
  --test-enable --test-tags /health_telemonitoring,/health_vitals,/health_pwa,/health_pwa_daystrip,/health_scribe,/health_pwa_family
  --stop-after-init --workers 0` (NO `--no-http` — HttpCase present).
- Result line from `/var/log/odoo/odoo-server.log` via
  `sudo grep -a 'odoo.tests.result'`; restart; curl `/web/login` → 200.
- Verify served PWA shell shows the new asset version.

## 6. Report back

Standard §8 items, plus: (a) the current→new PWA version numbers, (b) the
one non-superseded score count for your QA patient BEFORE you clean up,
(c) confirmation QA fixtures were deleted and re-verified in a fresh cursor
(§5.34), (d) any place the entry-sheet DOM made the ACVPU/O₂ controls
awkward (I will browser-QA the sheet on care.biztinct.com at review).

Kickoff line: `Implement the phase specified in docs/strategy/handovers/telemonitoring-phase.md.`
