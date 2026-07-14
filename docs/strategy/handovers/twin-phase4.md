# health_twin — Phase 4: Deterioration Forecast (who will get worse *next*?)

Fourth slice of **health_twin** and the payoff of Phase 3. Phase 1 said WHICH
patients are high-risk now; Phase 2 charted their vitals; Phase 3 recorded the
risk **trajectory**. Phase 4 answers the pre-emptive triage question — **which
patients are currently OK but heading into a worse band soon?** — by fitting a
transparent trend line over the risk-history points and projecting it forward.

This is the "predictive engine" the H3 twin is named for, done as **explainable
least-squares extrapolation — NOT ML, NOT LLM**. The forecast is **advisory and
ADDITIVE only**: it can RAISE attention (flag a rising patient) but it must
NEVER lower a current band, reorder anyone below their current-state risk, or
auto-trigger anything. Same spirit as the Phase-1 `clinical_floor` — signals
only ever add attention, never remove it.

Read `HANDOVER-CONVENTIONS.md` first (§5 ledger — esp. §5.36 settings,
§5.40 clinical-floor philosophy, §5.43 staleness-sentinel +5 baseline, §5.4
append-guards; §8.1 evidence pack). All plumbing facts below are pre-verified —
do not re-derive.

---

## 0. Scope and binding non-goals

**Build (health_twin only — NO shared-module edits, NO PWA):**
1. `twin_forecast.py` — a **pure** forecast kernel (no ORM), copied VERBATIM
   from §2.1 below (like `twin_score.py` was in Phase 1). Least-squares slope +
   forward projection + a confidence code. Fully deterministic and testable.
2. Forecast fields on the `health.twin.risk` snapshot: `forecast_score`,
   `forecast_band`, `forecast_slope`, `forecast_confidence`,
   `forecast_horizon_days`, `forecast_eta_days`, `will_escalate`,
   `forecast_json` — computed in `_upsert_one` from the risk history + the live
   score.
3. Worklist: a **Forecast** band column + a **"Rising"** filter
   (`will_escalate = True`) — the pre-emptive money view (not-yet-high but
   predicted to cross soon). Current-state sort is UNCHANGED.
4. Client chart: extend the existing **Risk Score** panel with a forward
   **Forecast** projection segment (now → now+horizon). Widget change only if
   a second series per panel needs support (verify first — likely none).
5. Config params (§5.36-safe if a Boolean UI toggle). Module → 19.0.4.0.0.
6. Tests (kernel unit vectors + model integration) + vi.po.

**Binding NON-goals:**
- NO ML / neural / LLM. The kernel is ordinary least-squares — every number is
  explainable from the points. If you reach for a library beyond Python stdlib
  `math`, STOP (no pip either — §conventions).
- The forecast is **advisory**: it NEVER auto-creates an alert, NEVER triggers
  dispatch / messaging / a workflow, NEVER writes to any model but the snapshot.
- The forecast NEVER LOWERS risk: `will_escalate` can only be True when the
  forecast band is STRICTLY ABOVE the current band. A *falling* forecast leaves
  the current band and the worklist sort untouched (no "this critical patient
  is improving so drop them" — current state always rules the sort).
- NO family-facing forecast (IF-032 is a separate, sensitive decision — never
  surface a prediction to a family here).
- NO what-if simulation (IF-002).
- NO new history/GC table (forecast lives on the snapshot, overwritten each
  recompute). NO edits to health_telemonitoring / health_vitals /
  health_fieldservice / health_pwa / biz_bi. NO PWA (backend surface → NO §3
  PWA bump). NO messaging, NO pip.

---

## 1. Verified plumbing facts (do not re-derive)

All in `addons/health_twin/models/health_twin_risk.py` unless noted.

- **`_upsert_one(patient, cfg, signals)`** assembles `vals` at :523-542, then
  writes the snapshot (`existing.write(vals)` / `self.sudo().create(vals)`) at
  :563-567, then appends history in its own savepoint at :573-580. `score_val`
  (post-clinical-floor composite) is at :504, `band` at :506, `now` (=
  `computed_at`) and `components` (news2/alert/trend/staleness floats) are in
  scope. **Seam for the forecast: compute it AFTER `score_val`/`band` are
  known and fold the fields INTO `vals` BEFORE the write** (so it persists in
  the same write; wrap it never-block, §3).
- **Risk history query precedent** (Phase 3, use the same shape) — in
  `chart_series` at :352-354:
  `self.env['health.twin.risk.history'].search([('patient_id','=',pid),
  ('computed_at','>=',date_from)], order='computed_at')`. History rows have
  `computed_at` (Datetime) + `composite_score` (Integer).
- **`_load_config()` (:394-411)** returns
  `{'weights':…, 'thresholds':{'moderate':25,'high':50,'critical':75},
  'decay_hours':…, 'staleness_threshold':…}`. **Extend it** with a
  `'forecast'` sub-dict (horizon/min_points/lookback/min_r2/min_slope/enabled)
  read via `twin_config.get_int/get_float/get_bool` (prefix `health_twin.`).
- **`band_for(score, thresholds)`** in `twin_score.py:82-91` maps a score →
  band code using the SAME `thresholds` dict — reuse it for `forecast_band`
  (do NOT write a second banding function).
- **Band order** for the "strictly above" test:
  `low < moderate < high < critical`. Use an explicit index map
  `{'low':0,'moderate':1,'high':2,'critical':3}` (define once in the model).
- **`chart_series` Risk Score panel** is appended at :346-365 with
  `band_zones` from `band_moderate`/`band_high` config; `series` is a LIST
  (`[{'name':…, 'points':[[iso,score],…]}]`). The OWL widget
  (`static/src/js/twin_trend_charts.js`) renders each panel's `series` list
  generically — **verify it draws >1 series per panel before relying on it**;
  if it only draws `series[0]`, that's the ONE sanctioned JS edit (loop all
  series). A dashed style for the forecast is OPTIONAL cosmetic — skip if it
  needs more than a trivial change.
- **Worklist list/search views**: `views/health_twin_risk_views.xml`
  (list `view_health_twin_risk_list` :7, form :46, search
  `view_health_twin_risk_search` :144 — the `worsening` filter at :150 is your
  pattern for the new `will_escalate` filter). Add the Forecast column + filter
  here; keep `default_order="composite_score desc"` UNCHANGED (§0 — current
  state rules the sort).
- **Config params** live in `data/twin_config_params.xml` (noupdate=1; Phase-3
  history params at :54-74 are the pattern). **Settings §5.36 `set_values`**
  override is in `models/res_config_settings.py` (Phase-3 `twin_history_enabled`
  is the precedent for a default-True Boolean toggle).
- **Snapshot model** (`health.twin.risk`) field block is near the top of
  `health_twin_risk.py` (the Phase-3 `trend_direction`/`score_delta`/
  `previous_*` fields are your precedent for adding Selection/Integer/Float
  fields). No `init()` change needed (no new index).

---

## 2. Architecture

health_twin 19.0.4.0.0. No new depends. No PWA. All edits inside health_twin.

### 2.1 `twin_forecast.py` — the pure kernel (copy VERBATIM, like twin_score.py)

```python
# -*- coding: utf-8 -*-
"""Digital-twin deterioration FORECAST kernel — pure functions, no ORM.

Transparent trajectory extrapolation (report IF-016): fit an ordinary
least-squares line to recent (time, risk-score) points and project it forward.
Every output is explainable from the input points — NO ML, NO LLM. The caller
(health.twin.risk) supplies the points and config; this module does only math.

Points are (x_days, score) where x is days relative to NOW: x = 0 is now,
x < 0 is the past (e.g. a point 2 days old is x = -2.0). Score is 0-100.

This block is copied verbatim from twin-phase4.md §2.1 ('kernel — use as-is').
"""

# kernel — use as-is
def _clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def fit(points):
    """Ordinary least-squares fit of score = a + b*x over `points`
    (list of (x_days, score)). Returns (slope_b, intercept_a, r2, n) or
    None when the fit is degenerate (fewer than 2 points, or all points at
    the same x so the slope is undefined). slope_b is score-units per DAY."""
    n = len(points)
    if n < 2:
        return None
    mx = sum(x for x, _y in points) / n
    my = sum(y for _x, y in points) / n
    sxx = sum((x - mx) ** 2 for x, _y in points)
    if sxx <= 0.0:                      # no time spread → slope undefined
        return None
    sxy = sum((x - mx) * (y - my) for x, y in points)
    syy = sum((y - my) ** 2 for _x, y in points)
    b = sxy / sxx
    a = my - b * mx
    # r2: fraction of score variance explained. A perfectly flat series
    # (syy == 0) is fully explained by a zero slope → r2 = 1.0.
    r2 = 1.0 if syy <= 0.0 else _clamp((sxy * sxy) / (sxx * syy), 0.0, 1.0)
    return (b, a, r2, n)


def confidence(fit_result, cfg):
    """'none' | 'low' | 'medium' | 'high' from the fit. `cfg` carries
    min_points / min_r2. 'none' means do not trust the projection at all."""
    if not fit_result:
        return 'none'
    b, _a, r2, n = fit_result
    if n < cfg['min_points']:
        return 'none'
    if r2 >= 0.7 and n >= cfg['min_points'] + 2:
        return 'high'
    if r2 >= cfg['min_r2']:
        return 'medium'
    return 'low'


def project(points, cfg):
    """Fit + project to +horizon_days. Returns a dict:
      {'has_forecast': bool, 'score': int(0-100), 'slope': float(pts/day),
       'r2': float, 'confidence': str, 'n': int}
    has_forecast is False (and score echoes the latest observed value) when the
    fit is degenerate or confidence is 'none' — the caller must NOT escalate on
    a no-forecast."""
    latest = points[-1][1] if points else 0     # points are time-ascending
    fr = fit(points)
    conf = confidence(fr, cfg)
    if not fr or conf == 'none':
        return {'has_forecast': False, 'score': int(round(latest)),
                'slope': 0.0, 'r2': 0.0, 'confidence': 'none',
                'n': len(points)}
    b, a, r2, n = fr
    projected = _clamp(a + b * cfg['horizon_days'], 0.0, 100.0)
    return {'has_forecast': True, 'score': int(round(projected)),
            'slope': b, 'r2': r2, 'confidence': conf, 'n': n}


def eta_days(current_score, slope, target_threshold):
    """Days until a rising trend crosses `target_threshold`, or None when it
    never will (slope <= 0, or already at/above the target). Explainable:
    (target - current) / slope."""
    if slope <= 0.0 or current_score >= target_threshold:
        return None
    return (target_threshold - current_score) / slope
```

**Worked vectors (bake these into the kernel unit tests):**
- Rising `[(-6,10),(-4,20),(-2,30),(0,40)]`, horizon 3 → slope **5.0**,
  intercept 40, r2 **1.0**, projected **55**.
- Flat `[(-6,30),(-4,30),(-2,30),(0,30)]` → slope **0.0**, r2 1.0,
  projected **30**, no escalation.
- Falling `[(-6,60),(-4,40),(-2,20),(0,10)]` → slope **-8.5**, projected
  clamped **0**, no escalation.
- Sparse `[(0,40)]` (n=1) → `fit` None → `confidence` 'none' →
  `has_forecast` False.
- `eta_days(40, 5.0, 50)` → **2.0**; `eta_days(40, -1.0, 50)` → None;
  `eta_days(60, 5.0, 50)` → None (already above).

### 2.2 Forecast fields on `health.twin.risk`

- `forecast_score` Integer (projected composite at horizon).
- `forecast_band` Selection (same 4 codes as `risk_band`), index.
- `forecast_slope` Float (score pts/day; digits e.g. (6,2)).
- `forecast_confidence` Selection
  `[('none','None'),('low','Low'),('medium','Medium'),('high','High')]`, index.
- `forecast_horizon_days` Integer (echo of config, for display).
- `forecast_eta_days` Float (days until crossing the NEXT band up; 0.0/False
  when not rising into a higher band).
- `will_escalate` Boolean, index — **the money field**: True IFF
  `has_forecast` AND `forecast_confidence in ('medium','high')` AND
  `forecast_slope >= forecast_min_slope` AND
  band_index(forecast_band) > band_index(current band). Never True on a flat
  or falling trajectory.
- `forecast_json` Char/Text — transparency blob: the points used (count +
  first/last), slope, r2, confidence, horizon, method='ols' (so the form can
  show "why"). Mirror the `factors_json` precedent.

### 2.3 Capture logic in `_upsert_one` (fold into `vals` before the write)

After `score_val`/`band` are computed and BEFORE the snapshot write (:563),
build the point series and project. Wrap it never-block (§3) — a forecast
failure must fall back to a clean no-forecast, never abort the snapshot:
```
fc_vals = self._empty_forecast_vals()          # all-empty defaults
if cfg['forecast']['enabled']:
    try:
        fc_vals = self._compute_forecast(pid, score_val, band, cfg, now)
    except Exception as exc:                    # noqa: BLE001 — never abort
        _logger.warning('Twin forecast failed for patient %s: %s', pid, exc)
vals.update(fc_vals)
```
`_compute_forecast(pid, score_val, band, cfg, now)`:
- Fetch history points in the lookback window, STRICTLY BEFORE `now`
  (so the live point isn't double-counted):
  `hist = history.search([('patient_id','=',pid),
     ('computed_at','>=', now - timedelta(days=lookback)),
     ('computed_at','<', now)], order='computed_at')`
- Build time-ascending points `[(x_days, score)]` where
  `x_days = -(now - h.computed_at).total_seconds()/86400.0` (negative, past),
  then APPEND the live anchor `(0.0, score_val)` LAST. This guarantees the
  current value is always the newest point even when no history row was
  written this recompute.
- `res = twin_forecast.project(points, cfg['forecast'])`.
- `fb = twin_score.band_for(res['score'], cfg['thresholds'])`.
- `escalate = (res['has_forecast']
     and res['confidence'] in ('medium','high')
     and res['slope'] >= cfg['forecast']['min_slope']
     and _BAND_IX[fb] > _BAND_IX[band])`
- `eta` = when escalating, `twin_forecast.eta_days(score_val, res['slope'],
     cfg['thresholds'][ next_band_up_name ])` — the threshold of the band one
     step above the CURRENT band (moderate→high threshold, etc.); else 0.0.
- Return the vals dict for all §2.2 fields (+ `forecast_json`).

`_empty_forecast_vals()` → `forecast_score=score_val`(echo current) /
`forecast_band=band` / `forecast_slope=0.0` / `forecast_confidence='none'` /
`forecast_horizon_days=cfg horizon` / `forecast_eta_days=0.0` /
`will_escalate=False` / `forecast_json='{}'`. So a no-forecast row is
self-consistent (forecast == current, not escalating).

### 2.4 Worklist Forecast column + "Rising" filter

In `views/health_twin_risk_views.xml`:
- Add to the list (after the trend columns): `forecast_band` as a decorated
  badge (danger critical / warning high / info moderate / muted low) +
  `forecast_confidence` (optional="show") + `forecast_eta_days`
  (optional="hide"). Keep flat-mono badges (§4 — no emoji), same house pattern
  as `risk_band`/`trend_direction`.
- Add a search **filter** `rising` string "Rising"
  `domain="[('will_escalate','=',True)]"` next to the `worsening` filter — the
  pre-emptive triage view (not-yet-high but predicted to cross). Do NOT add it
  to the action's `search_default_*` (keep the default = high+critical current
  state); it's a one-click pivot.
- Add the forecast fields to the FORM (a small "Forecast" group next to
  "Risk": band, score, slope /day, confidence, eta, horizon) so the projection
  is inspectable + explainable. Surface `will_escalate` as a decorated boolean.

### 2.5 Risk Score chart — forward projection segment (chart_series :346-365)

When the patient's snapshot has a forecast, append a SECOND series to the
existing `risk` panel: `{'name': _('Forecast'), 'points':
[[now_iso, current_score], [ (now+horizon)_iso, forecast_score ]]}`. Read the
snapshot's `forecast_score`/`forecast_horizon_days` (non-sudo — same
catchment gating as the panel; §3). If the widget only renders `series[0]`,
add a loop over all series (the ONE sanctioned JS edit); a dashed line style
is OPTIONAL — skip if non-trivial. If the widget already draws multiple
series, NO JS change.

### 2.6 Config + settings (data/twin_config_params.xml, noupdate=1)

New params (all `health_twin.`): `forecast_enabled=True`,
`forecast_horizon_days=3`, `forecast_min_points=4`, `forecast_lookback_days=14`,
`forecast_min_r2=0.3`, `forecast_min_slope=1.0`. Load them into a
`cfg['forecast']` sub-dict in `_load_config`. If you expose `forecast_enabled`
in settings, it MUST ride the existing §5.36 `set_values` override
(default-True Boolean; clone `twin_history_enabled`).

### 2.7 Sanctioned edits (exhaustive)

| Module | File | What may change |
|---|---|---|
| health_twin | models/twin_forecast.py (new, verbatim §2.1), models/twin_score.py (NO change — reuse `band_for`), models/health_twin_risk.py (forecast fields + `_load_config` forecast sub-dict + `_compute_forecast`/`_empty_forecast_vals` + `_upsert_one` fold + `chart_series` forecast series + `_BAND_IX` map), models/__init__.py, models/res_config_settings.py (+ optional toggle), data/twin_config_params.xml, views/health_twin_risk_views.xml (forecast columns + Rising filter + form group), static/src/js/twin_trend_charts.js (ONLY if it renders a single series per panel), i18n/vi.po, __manifest__.py (version), tests | as listed |

NO other module. NO security/ACL change (forecast fields are on the existing
`health.twin.risk`, already ACL'd + catchment-ruled). NO PWA bump.

---

## 3. Safety rails (binding)

- **Advisory only.** The forecast writes ONLY the snapshot fields. It NEVER
  creates an alert, NEVER calls dispatch / messaging / a workflow, NEVER writes
  another model. (A future phase may act on it — not this one.)
- **Never lowers risk.** `will_escalate` is strictly-above-current only. The
  worklist `default_order` stays `composite_score desc` — a falling forecast
  changes nothing about who ranks where. Verify with a test (a currently-
  critical, forecast-improving patient still sorts at the top, `will_escalate`
  False).
- **Never-block.** Forecast compute is wrapped (try/except → clean
  no-forecast) so a bad point series can't abort the snapshot write.
- **Non-sudo chart** stays non-sudo (§5.41/Phase-2/3 contract — record-rule
  gated; no PHI leak).
- **Transparent.** `forecast_json` records the points/slope/r2/method so every
  projection is explainable (report FB-064 ethos). NO ML/LLM, NO pip.
- Flat-mono icons/colors (§4). Chatter untouched. QA fixtures cleaned +
  fresh-cursor verified (§5.34) — and note §5.43: give forecast-test patients a
  recent completed visit (or account for the +5 staleness baseline) when
  asserting absolute bands.

## 4. Tests (tests/test_twin_forecast.py; ~11)

**Pure kernel (fast, no ORM) — the §2.1 worked vectors:**
1. `fit` on the rising vector → slope 5.0, intercept 40, r2 1.0.
2. `fit` degenerate: n<2 → None; all-same-x → None; flat → slope 0, r2 1.0.
3. `project` rising horizon 3 → score 55, has_forecast True; falling → clamp 0;
   sparse (n<min_points) → has_forecast False, confidence 'none'.
4. `confidence` bands: high (r2≥0.7 & n≥min+2) / medium (r2≥min_r2) / low / none.
5. `eta_days`: 40→50 @5/day = 2.0; negative slope → None; already above → None.

**Model integration (TransactionCase; freeze/thaw like test_twin_history):**
6. Rising trajectory (seed history low→moderate climbing, current still
   moderate but slope up into high) → snapshot `will_escalate=True`,
   `forecast_band='high'`, `forecast_eta_days>0`, forecast_confidence
   medium/high. (Give the patient a recent visit, §5.43.)
7. Falling trajectory (current critical, history descending) → `will_escalate`
   False, forecast_band ≤ current, and the row STILL sorts by composite (assert
   the currently-critical patient is not de-ranked — read the worklist order).
8. Flat / sparse patient (<min_points history) → has-no-forecast:
   forecast_confidence 'none', forecast_score == composite_score,
   will_escalate False.
9. `forecast_enabled=False` → all forecast fields empty/no-escalate; the rest of
   the snapshot (score/band/trajectory) still computes.
10. Never-escalate-below: a patient whose forecast band would be LOWER than
    current never sets will_escalate (covered by 7, assert explicitly).
11. `chart_series`: a patient with a forecast → the `risk` panel has a second
    series named "Forecast" with 2 points (now, now+horizon); a no-forecast
    patient → single series (no Forecast line).

## 5. Deploy / verify (conventions §2)

- `-u health_twin --test-enable --test-tags /health_twin --stop-after-init
  --no-http --workers 0` (no HttpCase). Result line; restart; `/web/login`
  200. No PWA, no other module upgraded.
- **Browser evidence pack (§8.1)** to
  `docs/strategy/reports/twin-phase4-evidence/`, from the REAL surface:
  (1) the Deterioration Worklist with the **Rising** filter applied showing a
  Forecast band column (seed 1 QA patient with a rising history so
  will_escalate=True — narrate the projection); (2) that patient's Trends tab
  **Risk Score** panel showing the forward Forecast segment past "now"
  (`/bizapp/action-1430/<patient_id>` → Trends); (3) the risk FORM Forecast
  group (band/slope/eta/confidence) proving explainability. Console clean.
  Delete QA rows + fresh-cursor verify (§5.34).

## 6. Report back

Standard §8 (report committed to
`docs/strategy/reports/twin-phase4-report.md`), plus: (a) the evidence pack
(Rising worklist + forecast chart segment + explainable form group), (b) whether
the widget needed a change for the second series or rendered it generically,
(c) the exact projected score/slope/eta for your rising QA patient (proving the
kernel matches the §2.1 vectors on real data), (d) confirmation that a falling
forecast did NOT de-rank a currently-critical patient (the never-lowers rail),
(e) QA cleanup fresh-cursor confirmation, (f) any new gotcha.

Kickoff line: `Implement the phase specified in docs/strategy/handovers/twin-phase4.md.`
