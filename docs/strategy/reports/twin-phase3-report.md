# health_twin — Phase 3: Risk History & Trajectory — implementation report

**Module:** `health_twin` 19.0.2.0.1 → **19.0.3.0.0**
**Scope:** append-only risk trajectory + worklist trend arrows + Risk Score chart
panel + retention GC. Backend only — **NO PWA, no shared-module edits** (per
handover §0). Live on vietuat.

---

## 0. Kickoff-prompt discrepancy (resolved, no scope change)

The kickoff message's task line named `twin-phase3.md`, but its *reading list*
and *Definition-of-Done* were stale boilerplate copied from the
**telemonitoring-phase2** kickoff (they referenced the vitals FAB, a PWA version
bump, an ingestion round-trip, and `telemonitoring-phase2-report.md`).

Repo state resolved it unambiguously: telemonitoring-phase2 is **already shipped**
(`health_telemonitoring` 19.0.2.0.0 with `health_monitor_device.py` /
`health_device_receipt.py` / `ingest.py`, plus its report + evidence pack all
committed), whereas `health_twin` was at 19.0.2.0.1 with **no** history model or
test. I implemented **twin-phase3** (matching the task line and the module state)
per **its own** §5/§6 — which are explicitly backend-only, so the boilerplate
DoD's PWA-bump / vitals-FAB / ingestion items do **not** apply and were correctly
not performed (a PWA bump here would have been an unsanctioned drive-by edit).

---

## 1. What was built (file list)

**New**
- `models/health_twin_risk_history.py` — `health.twin.risk.history` model:
  append-only points; non-unique `(patient_id, computed_at)` index in `init()`;
  engine/admin-only `write()`/`unlink()` guards (unconditional, §5.4, cloned from
  `health.twin.risk`); stored catchment compute; `_maybe_append()` (change-point +
  daily-cap decision); `cron_twin_history_gc()` (config-gated retention prune).
- `tests/test_twin_history.py` — 11 TransactionCase tests.

**Edited**
- `models/health_twin_risk.py` — trajectory fields (`trend_direction`,
  `score_delta`, `previous_score`, `previous_computed_at`); trajectory capture in
  `_upsert_one` (computed from the pre-write `existing` snapshot) + best-effort
  history append in its own savepoint; **Risk Score** panel appended in
  `chart_series` (non-sudo, band-zoned from config thresholds).
- `models/__init__.py` — import the new model.
- `models/res_config_settings.py` — `twin_history_enabled` toggle riding the
  existing §5.36 `set_values()` string-persist override.
- `views/health_twin_risk_views.xml` — worklist `trend_direction` + `score_delta`
  columns (colour-decorated); form trend fields; **Worsening** search filter.
- `views/res_config_settings_views.xml` — the history toggle setting.
- `data/twin_config_params.xml` — `history_enabled`, `history_gc_enabled`,
  `history_min_delta=8`, `history_stable_band=3`, `history_retention_days=365`.
- `data/twin_cron.xml` — daily `cron_twin_history_gc` cron.
- `security/ir.model.access.csv` — 7 ACL rows for the history model (read
  nurse→manager, full admin/owner).
- `security/twin_security.xml` — catchment + owner ir.rules for the history model.
- `i18n/vi.po` — new user-visible strings.
- `__manifest__.py` — version → 19.0.3.0.0.

Widget: **no change needed.** `twin_trend_charts.js` / `.xml` render panels
generically (`t-foreach="state.panels"` keyed on `panel.key`; JS matches
`.twin-chart-host[data-key]`), so the new `risk` panel rendered untouched —
confirmed live (report §3).

---

## 2. Deviations from the handover design

1. **Trend column renders as a colour-decorated badge + signed Score Δ, not a
   literal up/down FA-arrow glyph.** The handover (§2.4) said "red up-arrow /
   green down-arrow / grey dash" but also allowed "a Font-Awesome arrow consistent
   with house style". A per-cell conditional icon in an Odoo list needs a custom
   field widget; the house pattern already in this very view is the colour-
   decorated `badge` (used for `risk_band`). I used `trend_direction` as a
   Worsening=danger / Improving=success / Stable·New=muted badge plus a
   danger/success-decorated `score_delta` magnitude — same information, flat-mono,
   no emoji, zero new JS. Colour + signed delta carry the up/down semantics.
2. **Added the optional `twin_history_enabled` settings toggle** (handover §2.7
   made it optional / §2.8 sanctioned it). It rides the §5.36 `set_values()`
   override so the default-True switch can actually be turned off. No other
   deviation.

No models/fields/interfaces were renamed; no architecture redesigned; no
unsanctioned file touched.

---

## 3. Verbatim test results (vietuat)

Command: `-u health_twin --test-enable --test-tags /health_twin
--stop-after-init --no-http --workers 0` (no HttpCase in this module).

```
2026-07-14 12:31:24,814 ... odoo.tests.result: 0 failed, 0 error(s) of 40 tests when loading database 'vietuat'
```

`EXIT:0`, and after the final restart `curl localhost:8069/web/login` → `HTTP:200`.
(40 = the 29 pre-existing twin tests + the 11 new history tests; the pre-existing
suites still pass.)

The 11 new cases (`TestTwinHistory`): first-point/`new`; band-change→worsening;
improving; stable-no-append; delta-same-band; daily heartbeat; no-flood;
history-disabled; chart risk-panel (3 points oldest-first + zones + window
exclusion); GC cron (gate + prune + survive); append-only + ACL + catchment
isolation.

> First run had 2 RED (test-only, not code): `test_02` and `test_05`. Root cause:
> a patient with **no completed visit** carries the 999-day staleness sentinel →
> `staleness_component(999,10)=100 × 0.05 = +5` constant baseline, so a
> "signal-less" patient scores **5 not 0** (broke `test_02`'s `previous_score==0`)
> and 3 warnings + the +5 crossed 25 into **moderate** (`test_05` got
> `band_change`, not `delta`). Fixed the tests: capture the first score
> dynamically; give the delta patient a recent completed visit to zero staleness.
> The engine code was correct throughout. (New gotcha candidate below.)

---

## 4. Report-back items (handover §6)

**(a) Evidence pack** — committed to `docs/strategy/reports/twin-phase3-evidence/`
(README + 4 screenshots), driven from the real user paths:
- Worklist trend arrows: worsening (High, red "Worsening", Δ 42) + improving
  (Low, green "Improving", Δ −58) both visible.
- Trends tab **Risk Score** panel: rising line 15→28→45→62 with green/amber/red
  band zones; console clean.

**(b) Widget change?** **No** — rendered generically, no JS/XML edit (confirmed the
`risk` canvas rendered live, 368×220).

**(c) History row count for the QA patient** — the change-point rule bounded it as
designed: the worsening QA patient had exactly **4** history points across a
low→moderate→moderate→high walk (first + band_change + delta + band_change), not
one-per-recompute. (For the browser evidence these were seeded directly; the
`_maybe_append` bounding is proven by tests 4/5/6/7 — stable/sub-threshold/same-day
recomputes append nothing; only change-points + one daily heartbeat do.)

**(d) QA cleanup fresh-cursor confirmation** — seeded via `odoo-bin shell`
(create → `flush_all` → `commit`), verified in a separate shell, then deleted and
re-confirmed in a FRESH cursor: `PARTNERS 0 / TWIN 0 / HIST 0 / ZZQA_LEFT 0`.

**(e) New gotcha** — below.

---

## 5. New gotcha discovered (candidate for conventions §5)

**The twin staleness sentinel gives every patient with no completed visit a
constant +5 baseline composite score — a test that expects a "no-signal" patient
to score 0 is wrong.** `_upsert_one` sets `days_since_last_visit = 999`
(`_NO_VISIT_SENTINEL`) when a patient has no completed FSO, and
`staleness_component(999, 10) = 100`, which at the default 0.05 staleness weight
contributes `round(100 × 0.05) = 5` to the composite — so a signal-less patient
lands at score **5 / band low**, not 0, and small added signals cross band
boundaries 5 points "early". Any twin test that drives a patient with a few
alerts and asserts an absolute score / a specific band must EITHER give the
patient a recent completed visit (`UPDATE ... state='completed'` via raw SQL,
§5.9 — zeroes staleness) or account for the +5. This bit `test_02`/`test_05` on
first run (both green after accounting for it). Not a bug — the sentinel is
intentional low-weight attention-nudge; know it perturbs band math in fixtures.

---

## 6. Deferred / not done

Nothing from the twin-phase3 scope deferred. Binding non-goals respected: no
forecasting/ML, no what-if sim, no family view, no snapshot-per-hook (change-point
+ daily cap), no telemonitoring/vitals/PWA edits, no messaging, no pip.

Kickoff line for reference:
`Implement the phase specified in docs/strategy/handovers/twin-phase3.md.`
