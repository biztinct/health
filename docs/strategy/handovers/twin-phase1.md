# health_twin — Phase 1: Deterioration Worklist (the "trending down" triage)

First slice of **health_twin**, the H3 care-intelligence capstone. The
telemonitoring spine now PRODUCES the signals (NEWS2 scores, deterioration
alerts, device readings) but they only surface as raw per-record lists. This
phase turns them into ONE ranked, cross-patient **"clients trending down this
morning" worklist** for care managers — a per-client risk snapshot
(`health.twin.risk`) recomputed from the shipped signals by a transparent,
explainable heuristic (NO ML, NO LLM). It is the seed of the per-client twin:
later phases add trajectory charts (FA-004), what-if simulation, and family
trajectory views (IF-032) on top of this same row.

Read `HANDOVER-CONVENTIONS.md` first (§2 deploy, §5 ledger esp. §5.36 the
settings-toggle rule + §5.1 indexes + §5.4 unconditional guards, §6 fixtures,
§8/§8.1 evidence-pack + selective review). All plumbing facts below are
pre-verified — do not re-derive.

---

## 0. Scope and binding non-goals

**Build (one new module, NO shared-module edits):**
1. New module `addons/health_twin` (19.0.1.0.0).
2. `health.twin.risk` — one row per patient: composite risk score + band +
   a transparent breakdown of the contributing factors + evidence links.
3. A verbatim **scoring kernel** (pure functions, weights from config).
4. Recompute engine: a config-gated cron sweep (per-patient savepoints,
   batch cap) + event hooks that recompute one client when a NEW
   `health.ews.score` or `health.monitor.alert` lands (via `_inherit` in
   THIS module — never-block).
5. The **worklist**: backend list ordered by risk, band-colored, with the
   "high+critical" default filter, catchment/band grouping, and a readonly
   form showing the factor breakdown + smart buttons to the patient / open
   alerts / latest NEWS2 score.
6. Settings toggle(s) (§5.36-safe), config params, security, tests, vi.po.

**Binding NON-goals (do not build, do not scaffold):**
- NO trend/trajectory CHARTS (that is the FA-004 sibling phase) — this phase
  is the ranked worklist + factor breakdown only, no ECharts, no biz_bi.
- NO predictive/ML model, NO what-if simulation, NO LLM summaries — the
  score is a transparent weighted heuristic (report FB-064 "deliberately
  transparent heuristics rather than opaque ML"). Later twin phases.
- NO risk HISTORY / time-series — one row per patient, overwritten on
  recompute (a history table is a later twin phase; note it, don't build).
- NO PWA changes (this is a care-manager backend surface) — so NO §3 PWA
  bump, no PWA deploy.
- NO edits to health_telemonitoring / health_vitals / health_fieldservice
  files. The ews/alert hooks live in `health_twin` via `_inherit`.
- NO ZNS/SMS/email/messaging; NO auto-booking/dispatch (that is the other
  deferred telemonitoring phase). The worklist is read/triage only.
- NO pip installs.

---

## 1. Verified plumbing facts (do not re-derive)

All paths relative to `addons/`.

**Signals to aggregate (Phase 1/2 of telemonitoring, all shipped):**
- `health.ews.score` (`health_telemonitoring/models/health_ews_score.py`):
  fields `client_id` (M2O res.partner), `total` (Integer), `band` Selection
  `low/low_medium/medium/high`, `score_datetime` (Datetime),
  `superseded` (Boolean), `catchment_province_id`. The CURRENT NEWS2 for a
  client = the one row with `superseded=False` (there is exactly one; the
  engine supersedes older in-window rows). Created by the Phase-1 engine's
  observation hook.
- `health.monitor.alert` (`health_telemonitoring/models/health_monitor_alert.py`):
  fields `client_id`, `rule` Selection (`ews_high/ews_medium/ews_single3/
  threshold/trend_hr_drift/trend_sbp_drift/trend_spo2_decline/
  trend_weight_loss`), `severity` (`warning/critical`), `state`
  (`new/acknowledged/resolved/dismissed`). OPEN = `state in ('new',
  'acknowledged')`. Trend alerts = `rule like 'trend_%'`.
- Aggregate these with `read_group` on `client_id` — there is NO reverse
  One2many on res.partner for either (do not add one; do not edit those
  modules). Example:
  `env['health.monitor.alert'].read_group([('client_id','in',ids),
  ('state','in',('new','acknowledged'))], ['client_id','severity'],
  ['client_id','severity'], lazy=False)`.

**Patient + visit facts:**
- `res.partner`: `is_patient` (Boolean), `catchment_province_id`,
  `primary_facility_id`, and `_get_health_catchment_province()`
  (`health_base/models/res_partner.py:201`) — clone the Phase-1 catchment
  compute verbatim.
- Last completed visit: `health.fieldservice.order`
  (`health_fieldservice/models/health_fieldservice_order.py`): `patient_id`
  (:272), `scheduled_datetime` (:397), `state` (:941) Selection incl.
  `confirmed/assigned/in_progress/completed/completed_pending_invoice/
  closed`. COMPLETED = `state in ('completed','completed_pending_invoice',
  'closed')` (verified pattern at :3770). "days since last visit" =
  now − max(scheduled_datetime) over that client's completed FSOs
  (no completed visit → treat as a large sentinel, e.g. 999, but do NOT let
  it dominate — small weight, see kernel).

**Precedents to clone (from the telemonitoring modules you just reviewed):**
- Config helper: `health_telemonitoring/models/tm_config.py`
  (get_bool/get_int/get_float, namespaced, default-fallback). Clone as
  `health_twin/models/twin_config.py` with prefix `health_twin.`.
- Settings §5.36 rule: any default-True Boolean setting MUST persist explicit
  `'True'/'False'` via a `set_values()` override — copy the pattern from
  `health_telemonitoring/models/res_config_settings.py`.
- Catchment + owner ir.rules: clone shape from
  `health_telemonitoring/security/telemonitoring_security.xml`.
- Cron sweep with per-record savepoint + batch cap + logged drop:
  `health_telemonitoring/models/health_monitor_alert.py::cron_trend_sweep`.
- Append/engine-sudo model discipline (unique index in init() §5.1,
  system-only writes): `health.ews.score` in
  `health_telemonitoring/models/health_ews_score.py`.
- Menu parent: `health_base.menu_healthcare_clinical` (labelled "Clinical
  Intelligence") — put the worklist under it.

---

## 2. Architecture

New module `health_twin` 19.0.1.0.0. `depends`: `['health_telemonitoring',
'health_vitals', 'health_fieldservice', 'health_base', 'mail']` (health_pwa
NOT needed — no PWA surface).

### 2.1 `health.twin.risk` (models/health_twin_risk.py)

One row per patient, engine-maintained, `_order = 'composite_score desc,
id desc'`.

Fields:
- `patient_id` M2O res.partner, required, index, ondelete='cascade',
  domain is_patient. **Unique index on (patient_id) in `init()`** (§5.1) —
  one snapshot per patient.
- `composite_score` Integer (0–100), index — the ranking key.
- `risk_band` Selection `[('low','Low'),('moderate','Moderate'),
  ('high','High'),('critical','Critical')]`, index.
- Factor snapshot (for the transparent breakdown the worklist shows):
  - `news2_total` Integer, `news2_band` Char (store the band code as text —
    it is a snapshot, not a live relation), `news2_at` Datetime,
    `ews_score_id` M2O health.ews.score ondelete='set null' (link to the
    current non-superseded score, if any).
  - `open_alert_count` Integer, `open_critical_count` Integer,
    `trend_alert_count` Integer.
  - `days_since_last_visit` Integer, `last_visit_at` Datetime.
- `factors_json` Text — the machine breakdown
  (`json.dumps({'components': {...}, 'weights': {...}, 'raw': …},
  sort_keys=True)`) for auditability/debugging.
- `computed_at` Datetime.
- `catchment_province_id` computed+stored from patient (clone Phase-1
  compute), `company_id`.
- No `mail.thread` (system rows, overwritten — no chatter/history this phase).

Guards: `write()` and `unlink()` — engine/admin only (clone the ews.score
shape; unconditional §5.4). Users never create/write/unlink (ACL §2.5).

### 2.2 Scoring kernel — use as-is (models/twin_score.py)

Pure module-level functions, no ORM. **kernel — use as-is** (weights/
thresholds are passed in from config so the kernel stays pure and testable):

```python
# kernel — use as-is
NEWS2_BAND_POINTS = {'high': 100, 'medium': 55, 'low_medium': 25,
                     'low': 0, '': 0}


def news2_component(band, age_hours, decay_hours):
    """Points 0-100 from the current NEWS2 band, linearly decayed to 0 as the
    score ages past `decay_hours` (a two-week-old 'high' must not dominate a
    live picture). age_hours/decay_hours are floats; decay_hours > 0."""
    base = NEWS2_BAND_POINTS.get(band or '', 0)
    if base == 0:
        return 0.0
    if age_hours <= 0:
        return float(base)
    if age_hours >= decay_hours:
        return 0.0
    return base * (1.0 - age_hours / decay_hours)


def alert_component(open_critical, open_warning):
    """Points 0-100 from open (new/acknowledged) alerts. Critical dominates;
    warnings add sub-linearly and are capped so a pile of warnings can't
    outweigh one critical."""
    crit = 100 if open_critical >= 1 else 0
    warn = min(60, 20 * open_warning)
    return float(max(crit, warn))


def trend_component(open_trend):
    """Points 0-100 from open trend_* alerts (slow deterioration signal)."""
    return float(min(100, 40 * open_trend))


def staleness_component(days_since_visit, threshold_days):
    """Small 0-100 signal: a client not seen for a while, WITH other signals,
    warrants attention. 0 until `threshold_days`, then ramps to 100 over the
    next `threshold_days` again. Kept low-weight by the caller."""
    if days_since_visit <= threshold_days:
        return 0.0
    over = days_since_visit - threshold_days
    return float(min(100, 100.0 * over / max(1, threshold_days)))


def composite(components, weights):
    """Weighted average of the four components → int 0-100. `components` and
    `weights` are dicts keyed news2/alert/trend/staleness. Weights need not
    sum to 1; they are normalized here so config changes can't push the score
    out of range."""
    keys = ('news2', 'alert', 'trend', 'staleness')
    wsum = sum(max(0.0, weights.get(k, 0.0)) for k in keys) or 1.0
    total = sum(components.get(k, 0.0) * max(0.0, weights.get(k, 0.0))
                for k in keys)
    return int(round(total / wsum))


def clinical_floor(score, open_critical, thresholds):
    """An OPEN CRITICAL deterioration alert IS critical by definition — the
    weighted average must never bury it below the critical band. A lone
    critical alert scores only ~35 under typical weights (a weighted average
    dilutes one strong signal). Applied AFTER `composite`: floor at the
    critical threshold when a critical alert is open; a higher weighted score
    (more signals stacked) still ranks above the floor, preserving order."""
    if open_critical >= 1:
        return max(int(round(score)), int(thresholds['critical']))
    return int(round(score))


def band_for(score, thresholds):
    """(score, {'critical':c,'high':h,'moderate':m}) → band code.
    thresholds are inclusive lower bounds; below 'moderate' → 'low'."""
    if score >= thresholds['critical']:
        return 'critical'
    if score >= thresholds['high']:
        return 'high'
    if score >= thresholds['moderate']:
        return 'moderate'
    return 'low'
```

Engine applies the floor between `composite` and `band_for`:
`score = clinical_floor(composite(components, weights), open_critical,
thresholds)` — so an open critical alert always bands critical (fixes the
weighted-average dilution where a lone critical alarm scored only ~35 →
'moderate'). The raw weighted components remain in `factors_json` for
transparency.

### 2.3 Recompute engine (models/health_twin_risk.py)

`_recompute_for_patients(self, patients)` (sudo, engine-only):
1. Gate: skip entirely unless `twin_config.get_bool(env,'twin_enabled',True)`.
2. Load weights + thresholds + decay/staleness params from config (all
   `health_twin.*`, defaults in §2.6).
3. For the given patients, gather signals **in bulk** (read_group / search,
   NOT per-patient queries in a loop):
   - current non-superseded `health.ews.score` per client (search
     `[('client_id','in',ids),('superseded','=',False)]`, map by client);
   - open-alert counts by (client, severity) and open trend counts by client
     via read_group;
   - last completed FSO datetime per client via read_group max on
     `scheduled_datetime`.
4. Per patient, compute the four components via the kernel, then `composite`
   and `band_for`; assemble the factor snapshot + `factors_json`.
5. **Upsert** the single row (search existing by patient_id; write if present
   else create — both sudo). Stamp `computed_at`.
   Wrap the per-patient body so one bad patient can't abort the batch
   (per-patient savepoint in the cron path; the hook path recomputes a single
   client and is itself never-block-guarded by its caller).

`cron_twin_sweep()` (@api.model): config-gated (`twin_sweep_enabled`,
default True); candidate patients = those with ANY signal — union of
(clients with a non-superseded ews.score) ∪ (clients with an open alert) ∪
(clients with a completed FSO in the last `twin_stale_horizon_days`, default
30). Cap at `twin_sweep_batch_cap` (default 500), log the dropped count
(no silent caps). Per-patient savepoint. Daily-ish cron (every 6h is fine).
**Also prune**: a `health.twin.risk` row whose patient no longer has any
signal AND whose `composite_score` is 0 may be deleted to keep the worklist
clean (optional; if simpler, just recompute to 0/low and let the default
filter hide it).

Event hooks (models/health_ews_score.py + models/health_monitor_alert.py in
THIS module):
- `class HealthEwsScore(models.Model): _inherit='health.ews.score'` — override
  `create()` (call super first), then
  `self.env['health.twin.risk'].sudo()._recompute_for_patients(
  records.mapped('client_id'))` inside `try/except Exception: _logger`
  (never-block — a twin recompute must never break vitals capture).
- `class HealthMonitorAlert(models.Model): _inherit='health.monitor.alert'` —
  same on `create()` AND on `write()` when `state` changes (acknowledge/
  resolve/dismiss changes open-counts). Never-block guarded, config-gated.

### 2.4 Worklist views (views/health_twin_risk_views.xml)

- **List** (`create="0" edit="0"`, `default_order` by composite desc):
  columns patient, risk_band (badge — decoration-danger critical,
  decoration-warning high, else muted), composite_score (progressbar or
  plain), news2_total+news2_band, open_alert_count, open_critical_count,
  days_since_last_visit, computed_at. Decoration-danger on
  `risk_band=='critical'`.
- **Search**: filters "Critical" (`risk_band=='critical'`), "High"
  (`risk_band=='high'`), "Has open critical" (`open_critical_count>0`),
  "Has open alert" (`open_alert_count>0`), "Stale >Nd"
  (`days_since_last_visit>threshold`); group-by risk_band, catchment.
  Action context: `search_default_high=1, search_default_critical=1`
  (the "trending down this morning" default is high+critical) +
  `search_default_group_band=1`.
- **Form** (readonly snapshot): the factor breakdown laid out plainly
  (each component + its contribution), `factors_json` in a collapsible
  debug section, and header **smart buttons**: "Patient" (open res.partner),
  "Open Alerts" (act_window health.monitor.alert domain
  `[('client_id','=',patient_id),('state','in',('new','acknowledged'))]`),
  "Latest NEWS2" (open ews_score_id). No create/edit.
- Menu: `views/twin_menus.xml` — "Deterioration Worklist" under
  `health_base.menu_healthcare_clinical`, sensible sequence.

### 2.5 Security (security/)

- `ir.model.access.csv`: `health.twin.risk` — read for
  `health_base.group_healthcare_nurse` and up (nurses benefit from the
  triage view; it is catchment-scoped by ir.rule); create/write/unlink 0 for
  everyone except admin/owner (engine writes sudo). Follow the exact group
  ladder used in `health_telemonitoring/security/ir.model.access.csv`.
- `twin_security.xml`: catchment + owner ir.rules (clone shape).

### 2.6 Config + settings (data/ + models/res_config_settings.py)

- Params (`data/twin_config_params.xml`, noupdate=1):
  `twin_enabled=True`, `twin_sweep_enabled=True`, `twin_sweep_batch_cap=500`,
  `twin_stale_horizon_days=30`, `twin_news2_decay_hours=336` (14 days),
  `twin_staleness_threshold_days=10`,
  weights `twin_w_news2=0.5`, `twin_w_alert=0.35`, `twin_w_trend=0.1`,
  `twin_w_staleness=0.05`,
  band thresholds `twin_band_moderate=25`, `twin_band_high=50`,
  `twin_band_critical=75`.
- `res_config_settings.py`: expose `twin_enabled` + `twin_sweep_enabled` as
  Booleans (default True) — **MUST** ride a `set_values()` override that
  persists explicit `'True'/'False'` strings (§5.36; clone
  health_telemonitoring). Weights/thresholds stay param-only (no UI).
- `data/twin_cron.xml` (noupdate=1): the sweep cron (every 6h).

### 2.7 Sanctioned edits (exhaustive)

| Module | File | What may change |
|---|---|---|
| health_twin | (all) | new module — everything |

NO edits to any other module. The ews/alert hooks are `_inherit` classes
INSIDE health_twin — they do not touch the telemonitoring files. No PWA, no
health_pwa bump.

---

## 3. Safety rails (binding)

- Messaging rails stay off; no pip; real patient data on vietuat.
- Twin recompute must NEVER block or roll back a vitals capture or an alert
  transition (the hooks are never-block-guarded; test 13).
- All recompute writes are sudo + engine-only; users get read-only,
  catchment-scoped.
- QA fixtures created for tests/QA are deleted and re-verified in a fresh
  cursor (§5.34).

## 4. Tests (tests/test_twin.py, @tagged('post_install','-at_install'); ~16)

Fixtures per §6 (province+facility+patient; FSO needs facility+patient+
scheduled_datetime). To create signals, use the Phase-1 public paths:
`health.observation.create_coded/create_panel` to drive a NEWS2 score, and
create `health.monitor.alert` rows sudo for alert-count cases.

1. Kernel: `news2_component` — band→points, decay (age 0 → full, age ≥ decay
   → 0, half-decay → half); `alert_component` (1 critical → 100; 2 warnings →
   40; 4 warnings capped 60; critical beats warnings); `trend_component`
   (cap); `staleness_component` (0 under threshold, ramps after);
   `composite` (weight normalization keeps 0-100); `band_for` boundaries.
2. Recompute: a patient with a live `high` NEWS2 → row with high/critical
   band, news2_total/at/ews_score_id populated, composite in range.
3. Open critical alert with no NEWS2 → alert_component drives a
   high/critical band.
4. No signals at all → composite 0 / band low (or no row if you prune).
5. Decay: a `high` NEWS2 dated 20 days ago (past decay) contributes ~0 →
   band low unless other signals.
6. Upsert: two recomputes for the same patient → still exactly ONE row
   (unique index), values refreshed, computed_at advances.
7. Staleness: last completed visit 25 days ago, staleness threshold 10 →
   non-zero staleness component (small weight, doesn't alone reach high).
8. Event hook: creating a new ews.score recomputes that patient's twin row
   (assert the row appears/updates after `create_coded` completes a set).
9. Event hook: acknowledging→resolving an open critical alert drops
   open_critical_count on recompute (state-change hook fires).
10. Cron sweep: gate off (`twin_sweep_enabled=False`) → no rows; batch cap 1
    with 2 eligible patients → 1 processed, drop logged; candidate union
    (a patient with ONLY a completed recent visit is a candidate).
11. Worklist default filter shows high+critical, hides low.
12. ACL: nurse reads; nurse cannot write/create/unlink (AccessError);
    catchment isolation (a nurse in province A can't see province B's row).
13. Never-block: monkeypatch `_recompute_for_patients` to raise → creating an
    ews.score / alert still succeeds, exception logged.
14. Settings §5.36 roundtrip: save `twin_enabled=False` via
    `res.config.settings.set_values()` → `twin_config.get_bool` returns False
    (param persisted as 'False', not unlinked) → recompute is a no-op; toggle
    back on.
15. factors_json is valid JSON with the component + weight breakdown.
16. Catchment compute: the risk row's `catchment_province_id` matches the
    patient's.

## 5. Deploy / verify (conventions §2)

- Backend-only: `scp` health_twin → `/tmp` → `sudo cp`/chown; stop server,
  port-wait; `-i health_twin --test-enable --test-tags /health_twin
  --stop-after-init --workers 0` (NO `--no-http` if you add any HttpCase;
  none is required — worklist is backend, cover it with the evidence pack).
  NO other module upgraded, NO PWA bump.
- Result line from the log; restart; curl `/web/login` → 200.
- **Browser evidence pack (DoD item 5 / §8.1)** to
  `docs/strategy/reports/twin-phase1-evidence/`: driven from the REAL path —
  log in (a head-nurse/ops user), Healthcare → **Clinical Intelligence** →
  **Deterioration Worklist**; screenshot the ranked list (with the
  high+critical default filter) and a risk form showing the factor
  breakdown + smart buttons; capture the console (clean). Seed one QA patient
  with a high NEWS2 so the worklist has a visible row; DELETE all QA rows
  after and fresh-cursor verify (§5.34).

## 6. Report back

Standard §8 (report committed to
`docs/strategy/reports/twin-phase1-report.md`), plus: (a) the evidence pack,
(b) the QA-patient risk-row values before cleanup + confirmation of deletion
in a fresh cursor, (c) any place the read_group aggregation forced a
deviation, (d) any new gotcha.

Kickoff line: `Implement the phase specified in docs/strategy/handovers/twin-phase1.md.`
