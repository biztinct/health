# health_twin — Phase 3: Risk History & Trajectory (is this patient rising or falling?)

Third slice of **health_twin**. Phase 1 said WHICH patients are high-risk
(worklist); Phase 2 showed WHAT their vitals look like (trend charts). Phase 3
answers the question a care manager most needs at triage: **is this patient
getting BETTER or WORSE?** It turns the point-in-time risk snapshot into an
append-only trajectory, surfaces a **worsening/improving/stable arrow** on the
worklist, and adds a **Risk Score trajectory panel** to the client chart. This
is the "scrub the timeline" twin vision on OBSERVED history — no forecasting.

Read `HANDOVER-CONVENTIONS.md` first (§5 ledger, esp. §5.36 settings, §5.4
append-guards, §5.41/§5.42 view surfacing & get_view, §8.1 evidence pack). All
plumbing facts below are pre-verified — do not re-derive.

---

## 0. Scope and binding non-goals

**Build (health_twin only — NO shared-module edits, NO PWA):**
1. `health.twin.risk.history` — append-only per-patient risk points captured
   on recompute (change-point + daily cadence, NOT every recompute).
2. Trajectory fields on the `health.twin.risk` snapshot: `trend_direction`
   (worsening/improving/stable/new) + `score_delta` + `previous_*`, computed
   in `_upsert_one` by comparing the new score to the existing snapshot.
3. Worklist: a trend-direction arrow column (red ↑ worsening / green ↓
   improving / grey → stable).
4. Client chart: a **Risk Score** trajectory panel (composite over time,
   band-zone colored) added to `chart_series` — the generic widget renders it.
5. A retention GC cron; config params (settings §5.36-safe if any Boolean UI).
6. Tests + vi.po. Module → 19.0.3.0.0.

**Binding NON-goals:**
- NO forecasting / prediction / ML — the trajectory is OBSERVED history only
  (a predictive EWS is IF-016, a later phase).
- NO what-if simulation (IF-002), NO family "honest trajectory" view (IF-032).
- NO snapshot on EVERY recompute — the hooks fire on every alert/score change;
  history must be change-point + daily-capped or it floods.
- NO edits to health_telemonitoring / health_vitals / health_fieldservice /
  health_pwa / biz_bi. Everything is inside health_twin (the recompute engine,
  chart_series, widget, and views already live here).
- NO PWA (backend surface), so NO §3 PWA bump.
- NO messaging, NO pip.

---

## 1. Verified plumbing facts (do not re-derive)

All in `addons/health_twin/models/health_twin_risk.py` unless noted.

- Recompute entry: `_recompute_for_patients(patients)` (:335) → per-patient
  `_upsert_one(patient, cfg, signals)` (:429) inside a savepoint. Config via
  `_load_config()` (:357). Signals bulk-loaded by `_gather_signals(ids)`
  (:376).
- **`_upsert_one` writes the snapshot at :506-510**:
  `existing = self.sudo().search([('patient_id','=',pid)], limit=1)`; then
  `existing.write(vals)` or `self.sudo().create(vals)`. The `vals` dict is
  assembled at :~488-505 (composite_score, risk_band, the `*_points`,
  factors_json, computed_at). **This is the seam**: `existing` still holds the
  OLD score/band at that point — capture them BEFORE the write to compute the
  trajectory, and append the history point here.
- The score after the Phase-1 clinical floor is `score_val`; band is `band`
  (both computed earlier in `_upsert_one`). `now = fields.Datetime.now()`
  (already in scope as `computed_at`).
- Append-only guard precedent: `health.twin.risk.write()/unlink()`
  `_engine_or_admin()` (:127-146) — clone verbatim for the history model
  (unconditional, §5.4).
- catchment compute precedent: `_compute_catchment_province_id` (:115-121).
- Config helper: `twin_config.get_bool/get_int/get_float`
  (`models/twin_config.py`), prefix `health_twin.`. Settings §5.36 `set_values`
  override already exists in `models/res_config_settings.py` — extend it if you
  add a Boolean UI toggle.
- Cron precedent: `cron_twin_sweep` (config-gated, batch, logged) —
  `data/twin_cron.xml` is where a new GC cron record goes.
- **`chart_series(patient_id, days)` (:226)** returns `{range_days, panels:[…]}`;
  the NEWS2 panel is appended at :324 with `band_zones` = `_NEWS2_BAND_ZONES`.
  The OWL widget (`static/src/js/twin_trend_charts.js`) renders each panel in
  the list GENERICALLY (line/series + optional `bands`/`band_zones`), so a new
  panel dict of the same shape renders with NO (or minimal) widget change —
  verify the widget's panel loop handles an arbitrary `key`; if it hard-codes
  panel keys anywhere, add the `risk` key.
- Worklist list view: `views/health_twin_risk_views.xml` (the list with band
  badges + `search_default_high/critical`). Add the trend-direction column
  there.

---

## 2. Architecture

health_twin 19.0.3.0.0. No new depends. No PWA. All edits inside health_twin.

### 2.1 `health.twin.risk.history` (models/health_twin_risk_history.py)

Append-only points, `_order = 'computed_at desc, id desc'`.
- `patient_id` M2O res.partner, required, index, ondelete='cascade',
  domain is_patient.
- `computed_at` Datetime, required, index (the point time).
- `composite_score` Integer, index; `risk_band` Selection (same 4 codes as
  the snapshot).
- Component snapshot for a rich trajectory: `news2_points`, `alert_points`,
  `trend_points`, `staleness_points` Integer.
- `trigger` Selection `[('band_change','Band change'),('delta','Score move'),
  ('daily','Daily'),('first','First')]` — WHY this point was captured (audit /
  debugging).
- `catchment_province_id` computed+stored (clone), `company_id`.
- Index in `init()` on `(patient_id, computed_at)` (§5.1 — a plain composite
  index, NOT unique: many points per patient).
- `write()`/`unlink()` guarded engine/admin-only (clone `_engine_or_admin`,
  unconditional §5.4). No mail.thread.

### 2.2 Trajectory fields on `health.twin.risk` (snapshot)

Add to `health.twin.risk`:
- `trend_direction` Selection `[('worsening','Worsening'),
  ('improving','Improving'),('stable','Stable'),('new','New')]`, index.
- `score_delta` Integer (new − previous; 0 for new).
- `previous_score` Integer; `previous_computed_at` Datetime.

### 2.3 Capture logic in `_upsert_one` (the seam at :506)

Right before the existing write/create (while `existing` still holds the old
values), compute + fold into `vals`:
```
prev = existing  # may be empty
prev_score = prev.composite_score if prev else None
prev_band = prev.risk_band if prev else None
if prev_score is None:
    direction = 'new'; delta = 0
else:
    delta = score_val - prev_score
    thr = twin_config.get_int(env, 'history_stable_band', 3)  # +/- noise band
    direction = ('worsening' if delta > thr else
                 'improving' if delta < -thr else 'stable')
vals.update({
    'trend_direction': direction,
    'score_delta': delta,
    'previous_score': prev_score or 0,
    'previous_computed_at': prev.computed_at if prev else False,
})
```
Then AFTER the upsert, append a history point (guarded, config-gated), passing
the reason:
```
if twin_config.get_bool(env, 'history_enabled', True):
    self.env['health.twin.risk.history'].sudo()._maybe_append(
        patient.id, score_val, band, components, prev, now)
```
`_maybe_append(patient_id, score, band, components, prev_snapshot, now)`:
- Find the patient's LAST history point (search desc limit 1).
- Decide (change-point + daily cap):
  - no last point → append `trigger='first'`.
  - band changed vs last point → `trigger='band_change'`.
  - `abs(score - last.composite_score) >= history_min_delta` (config,
    default 8) → `trigger='delta'`.
  - last point is on an EARLIER calendar day than `now` (a once-a-day
    heartbeat so a slow drift still leaves a trail) → `trigger='daily'`.
  - else → do NOT append (avoids flooding from frequent hook recomputes).
- On append: create the history row (sudo) with score/band/component points +
  trigger + computed_at=now.
This bounds history to meaningful moves + one point/day, not one-per-hook.

### 2.4 Worklist trend column (views/health_twin_risk_views.xml)

Add a `trend_direction` column to the worklist list with an icon/badge:
worsening = red up-arrow (decoration-danger), improving = green down-arrow
(decoration-success), stable = grey dash, new = muted "new". Use the
`hf-wt-ico` CSS-mask icons or a Font-Awesome arrow consistent with house style
(§4 — no emoji). Add a search filter "Worsening" (`trend_direction=worsening`)
— the highest-value triage view (high-risk AND worsening). Put it early in the
default order consideration (keep `_order` by composite desc; the arrow is a
column, not the sort — but a "Worsening" filter + the existing high/critical
default gives the money view).

### 2.5 Risk trajectory panel in `chart_series` (:226)

After the NEWS2 panel, append a `risk` panel from `health.twin.risk.history`
for the patient over the window:
```
{'key':'risk', 'title': _('Risk Score'), 'unit':'',
 'series':[{'name': _('Risk'), 'points':[[iso, composite_score], …]}],
 'band_zones':[[0, band_moderate-1, 'success'],
               [band_moderate, band_high-1, 'warning'],
               [band_high, 100, 'danger']]}   # thresholds from config
```
Query the history rows `[('patient_id','=',pid),('computed_at','>=',date_from)]`
ordered by computed_at; points `[iso, composite_score]`. Band zones from the
twin band thresholds (moderate/high/critical) so the panel colors match the
worklist bands. Runs under the caller's env (NOT sudo — same record-rule
gating as Phase 2; history is catchment-scoped). If the widget hard-codes
panel keys, add `risk` to its handling; otherwise it renders generically.

### 2.6 Retention GC (data/twin_cron.xml + method)

`cron_twin_history_gc()` (@api.model): config-gated `history_gc_enabled`
(default True); delete history rows older than `history_retention_days`
(config, default 365); per the cron precedent, log the count. Daily.

### 2.7 Config + settings (data/twin_config_params.xml, noupdate=1)

New params: `history_enabled=True`, `history_gc_enabled=True`,
`history_min_delta=8`, `history_stable_band=3`, `history_retention_days=365`.
If you expose `history_enabled` in the settings UI, it MUST ride the existing
§5.36 `set_values` override (default-True Boolean). Weights/thresholds unchanged.

### 2.8 Sanctioned edits (exhaustive)

| Module | File | What may change |
|---|---|---|
| health_twin | models/health_twin_risk_history.py (new), models/health_twin_risk.py (trajectory fields + `_upsert_one` capture + `chart_series` risk panel), models/__init__.py, models/res_config_settings.py (+ optional toggle), data/twin_cron.xml + data/twin_config_params.xml, views/health_twin_risk_views.xml (trend column + filter), static/src/js/twin_trend_charts.js (ONLY if the widget hard-codes panel keys), security/ir.model.access.csv + twin_security.xml (history model ACL+rules), i18n/vi.po, tests | as listed |

NO other module. NO PWA bump.

---

## 3. Safety rails (binding)

- History append must NEVER block a recompute (it is already inside the
  per-patient savepoint + the recompute's own guard; keep `_maybe_append`
  cheap and let the savepoint contain any failure — do not let it raise out of
  `_upsert_one` in a way that aborts the snapshot; wrap if unsure).
- History writes engine-sudo; users read-only, catchment-scoped (clone).
- chart_series stays NON-sudo (record-rule gated — §5.41/Phase-2 contract).
- Flat-mono icons/colors, no gradients (§4). Chatter untouched.
- QA fixtures cleaned + fresh-cursor verified (§5.34). No pip.

## 4. Tests (tests/test_twin_history.py; ~10, TransactionCase)

1. First recompute → one history point, `trigger='first'`, snapshot
   `trend_direction='new'`, score_delta 0.
2. Band change (drive a patient low→critical via signals) → a new history
   point `trigger='band_change'`; snapshot `trend_direction='worsening'`,
   score_delta > 0, previous_* populated.
3. Improving: high→low → `trend_direction='improving'`, delta < 0.
4. Stable within noise band (|delta| ≤ history_stable_band) → `stable`, and NO
   history point appended (sub-threshold, same day, same band).
5. Delta threshold: a score move ≥ history_min_delta but same band → a point
   with `trigger='delta'`.
6. Daily heartbeat: backdate the last history point to yesterday (set
   computed_at directly — plain field), recompute with no material change →
   a `trigger='daily'` point appended (once-a-day trail).
7. No-flood: two recomputes same day, same score/band → exactly ONE extra
   history point at most (the daily rule doesn't double-fire; sub-threshold
   doesn't append).
8. `history_enabled=False` → no history points; snapshot trajectory fields
   still compute (they are cheap and independent of the history table).
9. `chart_series` risk panel: a patient with 3 history points → panels
   includes `key='risk'` with 3 points oldest-first, band_zones set.
10. GC cron: backdate a point > retention, run `cron_twin_history_gc` → pruned;
    a recent point survives; `history_gc_enabled=False` → no-op.
11. Append-only + ACL: nurse `unlink()`/`write()` on a history row raises;
    nurse can READ own-catchment history, not cross-catchment.

## 5. Deploy / verify (conventions §2)

- `-u health_twin --test-enable --test-tags /health_twin --stop-after-init
  --workers 0`. Result line; restart; `/web/login` 200. No PWA, no other
  module upgraded.
- **Browser evidence pack (§8.1)** to
  `docs/strategy/reports/twin-phase3-evidence/`, driven from the REAL surface:
  (1) the Deterioration Worklist showing the trend-direction arrows (seed 2
  QA patients — one worsening, one improving — so both arrows show; or narrate
  what's visible); (2) a client's Trends tab showing the new **Risk Score**
  trajectory panel alongside the vitals panels
  (`/bizapp/action-1430/<patient_id>` → Trends). Screenshot both; console
  clean. Delete QA rows + fresh-cursor verify (§5.34).

## 6. Report back

Standard §8 (report committed to
`docs/strategy/reports/twin-phase3-report.md`), plus: (a) the evidence pack
(worklist arrows + risk trajectory panel), (b) whether the widget needed a
change for the risk panel or rendered it generically, (c) the history row
count for your QA patient (proving the change-point rule bounded it, not
one-per-hook), (d) QA cleanup fresh-cursor confirmation, (e) any new gotcha.

Kickoff line: `Implement the phase specified in docs/strategy/handovers/twin-phase3.md.`
