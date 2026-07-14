# health_twin — Phase 4: Deterioration Forecast — Implementation Report

**Module:** health_twin `19.0.3.0.0` → `19.0.4.0.0`
**Branch:** 19.0 · **DB:** vietuat · **Server:** VietUcUAT
**Scope:** health_twin ONLY — no shared-module edits, no PWA bump.

Phase 4 answers the pre-emptive triage question — *which patients are currently
OK but heading into a worse band soon?* — by fitting a transparent least-squares
trend line over the Phase-3 risk-history points and projecting it forward. The
forecast is **advisory and ADDITIVE only**: it can RAISE attention
(`will_escalate`) but never lowers a current band, reorders anyone below their
current state, or auto-triggers anything (same spirit as the Phase-1
`clinical_floor`).

---

## 1. What was built (file list)

| File | Change |
|---|---|
| `models/twin_forecast.py` | **NEW** — the pure OLS forecast kernel, copied VERBATIM from handover §2.1 (`fit`/`confidence`/`project`/`eta_days`). No ORM, stdlib only. |
| `models/__init__.py` | import `twin_forecast` (before `health_twin_risk`). |
| `models/health_twin_risk.py` | 8 forecast fields; `_BAND_IX`/`_NEXT_BAND` maps; `_load_config` `forecast` sub-dict; `_empty_forecast_vals` + `_compute_forecast`; never-block fold into `_upsert_one` `vals`; `chart_series` forward Forecast segment. `twin_forecast` import. |
| `models/res_config_settings.py` | `twin_forecast_enabled` Boolean toggle riding the §5.36 `set_values` string-persist override. |
| `data/twin_config_params.xml` | 6 new `health_twin.forecast_*` params (noupdate=1). |
| `views/health_twin_risk_views.xml` | list: Rising + Forecast Band + Forecast Confidence + Forecast ETA cols; search: **Rising** filter next to Worsening; form: **Forecast** group + machine blob in debug group. |
| `views/res_config_settings_views.xml` | Deterioration-forecast setting toggle. |
| `i18n/vi.po` | 13 new user-visible strings (each with `#. module:` per §5.29). |
| `__manifest__.py` | version → `19.0.4.0.0`. |
| `tests/test_twin_forecast.py` | **NEW** — 5 pure-kernel + 6 model-integration tests. |
| `tests/__init__.py` | import `test_twin_forecast`. |

Sanctioned-edit table (handover §2.7) honoured exactly. `twin_score.py`
unchanged (reused `band_for`). **No** security/ACL change, **no** shared-module
edit, **no** PWA bump, **no** pip, **no** JS edit (see §3).

---

## 2. Test results (verbatim)

```
odoo.tests.result: 0 failed, 0 error(s) of 51 tests when loading database 'vietuat'
```

51 = 40 prior (test_twin 16 + charts + history 11 + kernel) **+ 11 new Phase-4
tests**, all green. Server healthy after restart: `/web/login` → **HTTP 200**.
(The Photon/geocoding + "recompute failed" log lines are the standard
external-HTTP-blocked test noise — §6 — and appear in the passing baseline too.)

Phase-4 test coverage:
- **Kernel (5):** rising fit (slope 5, intercept 40, r2 1.0); degenerate (n<2 /
  same-x → None; flat → slope 0, r2 1.0); project rising 55 / falling clamp 0 /
  sparse no-forecast; confidence high/medium/low/none bands; `eta_days`.
- **Model (6):** rising → `will_escalate=True`, forecast_band high, eta>0;
  falling+critical → no escalate, no de-rank (worklist order asserted); sparse →
  confidence none, forecast==composite; `forecast_enabled=False` → snapshot
  still computes, forecast empty; never-escalate-below (forecast band LOWER than
  current → False); `chart_series` forecast segment present iff a forecast.

---

## 3. Report-back items (handover §6)

**(a) Evidence pack** — `docs/strategy/reports/twin-phase4-evidence/`:
- `01-worklist-rising-filter.png` — the Deterioration Worklist with the **Rising**
  filter applied, showing the new **RISING / FORECAST BAND / FORECAST CONFIDENCE**
  columns; QA patient (moderate, score 31) flagged Rising → forecast band **High**.
- `02-trends-risk-forecast.png` — the QA patient's Trends tab **Risk Score** panel:
  the observed **Risk** line (5→14→23→31) plus a second **Forecast** series rising
  from 31 into **57**, crossing past "now" into the red (High) band zone.
- `03-risk-form-forecast-group.png` — the risk FORM **Forecast** group
  (Rising ✓, Band High, Score 57, Slope 8.70, Confidence Medium, ETA 2.18,
  Horizon 3) + the transparent `forecast_json` machine blob.
- Console **clean** on all three screens (no errors/warnings).

**(b) Widget change for the second series?** **NONE.** The OWL widget
(`twin_trend_charts.js`) already renders each panel's `series` list generically —
`_buildOption` does `panel.series.map((s,i) => …)` and shows the legend when
`series.length > 1` (verified at `twin_trend_charts.js:171`, `:226`). The second
Forecast series and its legend rendered with zero JS edit — the ONE sanctioned JS
edit was not needed. (A dashed style was the optional cosmetic; skipped as it
would have required the JS edit.)

**(c) Exact projection on real data (QA patient 8850):**
composite **31 / moderate**; history anchor points `[(-3,5),(-2,14),(-1,23),(0,31)]`;
kernel output **slope 8.70 pts/day, r2 0.9992, projected 57 / high, confidence
medium, eta 2.18 days, horizon 3**; `forecast_json` method `ols`, n_points 4.
The live values match the pure-kernel math exactly (proving the kernel runs
identically on real data).

**(d) Never-lowers rail confirmed.** `test_07_falling_no_derank`: a currently
**critical** patient with a *falling* forecast (slope −3.3, forecast band → high,
below critical) keeps `will_escalate=False` and still sorts ABOVE a moderate
patient under the unchanged `composite_score desc` order — the falling forecast
changed nothing about who ranks where. `will_escalate` is strictly-above-current
only, by construction (`_BAND_IX[fb] > _BAND_IX[band]` AND slope ≥ min_slope AND
confidence ∈ medium/high AND has_forecast).

**(e) QA cleanup fresh-cursor confirmed.** Patient 8850 + its risk row, 3 history
points, 3 trend alerts, and 1 FSO were deleted and re-verified as **0 rows** in a
SEPARATE `odoo-bin shell` invocation with `active_test=False` (§5.34/§5.27).

**(f) New gotcha discovered:** None new to the ledger. Confirmed-in-practice
notes: §5.43 (staleness +5) was handled by giving forecast-test patients a recent
completed visit; the geometry constraint below is design guidance, not a defect.

---

## 4. Deviations from the handover

- **No JS edit** (as anticipated by §2.5/§2.7 "ONLY if it renders a single series
  per panel") — the widget was already multi-series. No dashed style (optional).
- `_empty_forecast_vals` takes `(score_val, band, cfg)` rather than the
  zero-arg signature sketched in §2.3 pseudo-code, because the no-forecast row
  must echo the current score/band and the config horizon (as §2.3 itself
  specifies). Functionally identical to the handover intent.
- **Integration-test geometry note (not a deviation, a design fact):** with a
  3-day horizon a *moderate* current score (max ~31 from alert+trend signals
  without NEWS2) cannot cross into *high* at a realistic slope, so
  `test_06`/`test_11` temporarily set `forecast_horizon_days=7` (rolled back in a
  `finally`) to exercise a rising escalation. The live seed uses the default
  horizon 3 with a steeper recent climb (`[(-3,5),(-2,14),(-1,23),(0,31)]`,
  slope 8.7) so the evidence pack reflects the shipped config unchanged.

---

## 5. Deferred / non-goals honoured

NO ML/LLM (ordinary least-squares, every number explainable). Forecast writes
ONLY the snapshot — no alert/dispatch/messaging/workflow. NO family-facing
forecast (IF-032). NO what-if (IF-002). NO new history/GC table (forecast lives
on the snapshot, overwritten each recompute). NO edits to
telemonitoring/vitals/fieldservice/PWA/biz_bi. NO PWA bump. NO pip.

---

## 6. Config parameters shipped (health_twin.*, noupdate=1)

`forecast_enabled=True`, `forecast_horizon_days=3`, `forecast_min_points=4`,
`forecast_lookback_days=14`, `forecast_min_r2=0.3`, `forecast_min_slope=1.0`.
Kill-switch `forecast_enabled` exposed in Settings via the §5.36-safe
string-persist `set_values` override.
