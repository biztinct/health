# health_twin — Phase 2: Vitals & NEWS2 Trend Charts (the client trajectory view)

Second slice of **health_twin** (FA-004). Phase 1 gave the worklist ("WHICH
patients are trending down"); this phase gives the trajectory ("WHAT is their
course") — ECharts trend panels on the backend **client chart**: BP, HR, SpO₂,
temperature, weight, and the NEWS2 total over time, with the patient's own
alert-threshold bands overlaid. It is the twin's signature "scrub the timeline"
surface and the visual layer the whole vitals/NEWS2/device spine has been
feeding. health_twin is the right home because it already depends on BOTH the
vitals data (`health.observation`) and the NEWS2 data (`health.ews.score`).

Read `HANDOVER-CONVENTIONS.md` first (§2 deploy, §4 flat-mono/no-gradient +
chatter rules, §5 ledger, §8/§8.1 evidence-pack + selective review). All
plumbing facts below are pre-verified — do not re-derive.

---

## 0. Scope and binding non-goals

**Build (health_twin only, one new backend OWL widget):**
1. An OWL **view-widget** `twin_trend_charts` (ECharts) rendering a
   small-multiples grid of trend panels, mounted on a new **"Trends"** tab of
   the patient form (via health_twin's own inherit of the patient view).
2. One ORM data method `chart_series(patient_id, days)` returning all series
   in a SINGLE call (vitals trends + NEWS2 history + per-client threshold
   bands) — no N round-trips from the browser.
3. A 7/30/90-day range selector (default 30), flat-mono theme colors pulled
   from the health_theme CSS vars, dark-mode aware, per-panel empty states.
4. Tests + vi.po. Module → 19.0.2.0.0; `depends += biz_bi` (ECharts lib).

**Binding NON-goals:**
- NO PWA changes — the PWA already ships SVG sparklines (`renderSparkline` /
  `renderTrend`, health_vitals Phase 1). A fuller PWA trend view is a later
  phase. So NO §3 PWA bump, no PWA deploy.
- NO new charting library — reuse the **biz_bi ECharts** already on
  `web.assets_backend` (do NOT vendor a second copy of echarts.min.js).
- NO predictive/forecast overlay, NO what-if, NO risk-history table (later
  twin phases). This is observed data only.
- NO edits to health_vitals / health_telemonitoring / health_base files. The
  `chart_series` method lives on a health_twin model and READS the other
  models via their public methods / ORM search (no shared-module edits).
- NO native `<graph>` view (those are separate dashboards; FA-004 wants the
  chart embedded IN the client chart — an OWL widget is the only in-form
  precedent).
- NO gradients/dual-tone (house rule §4) — flat mono lines + faint bands.
- NO messaging, NO pip.

---

## 1. Verified plumbing facts (do not re-derive)

All paths relative to `addons/`.

**ECharts (already global):**
- `biz_bi/__manifest__.py:37` bundles `biz_bi/static/src/lib/echarts.min.js`
  on `web.assets_backend` — so `window.echarts` is available to any backend
  module when biz_bi is installed (it is, on vietuat). **Make health_twin
  `depends` on `biz_bi`** so the load order is declared and honest (FA-004:
  "reuses the biz_bi ECharts stack"). Do NOT re-bundle echarts.
- Init pattern (clone): `biz_bi/static/src/components/explore/chart_renderer.js:43-81`
  — `/* global echarts */`; `echarts.init(el, null, {renderer:'canvas'})`;
  `chart.setOption(option, {notMerge:true})`; ResizeObserver; `dispose()` in
  `onWillUnmount`. Copy this lifecycle discipline.

**OWL view-widget pattern (clone):**
- `health_crm/static/src/js/contact_timeline.js:17-34` —
  `registry.category("view_widgets").add("contact_timeline", {Component: …})`,
  mounted in a form via `<widget name="contact_timeline" .../>`. THIS is the
  template for `twin_trend_charts`. (Field-widget precedents:
  `health_base/static/src/js/address_map_widget.js` uses `useRef`,
  `onMounted`, `onWillUnmount`, `loadJS` for an external lib.)
- A view-widget receives `this.props.record`; the patient id is
  `this.props.record.resId`. Use `useService("orm")` for data
  (`orm.call(model, method, args)` / `orm.searchRead(...)`).

**Patient form (attach point):**
- Main view: `health_base.view_health_patient_form`
  (`health_base/views/health_patient_views.xml:9`); `<notebook>` at :177.
- health_twin adds a page via its OWN inherit:
  `<xpath expr="//notebook" position="inside"><page string="Trends"
  name="twin_trends"><widget name="twin_trend_charts"/></page></xpath>`
  (precedent: `health_vitals/views/res_partner_views.xml:9` inherits the same
  view). Guard the page's visibility to `is_patient` if the view is shared
  with non-patient partners (check the existing pages' invisible rules).

**Data sources (all read-only, via ORM — no edits):**
- Vitals trend: `health.observation.get_trend(client_id, vitals_type_id,
  date_from=None, date_to=None, limit=200)`
  (`health_vitals/models/health_observation.py:444`) → `[{'datetime': ISO
  str, 'value': float}, …]` oldest-first, final/amended only. Takes the
  vitals_type_id (int), not the code — resolve codes→ids via
  `health.vitals.type` (search once for all needed codes).
- Vitals catalog: `health.vitals.type.get_by_code(code)` (LOINC or short
  code); codes to chart: `bp_sys`, `bp_dia`, `hr`, `spo2_po` (union with
  `spo2`), `temp`, `weight`, `glucose` (chart glucose only if the patient has
  any). `unit_display` / `name` on the type for axis labels.
- **NEWS2 history**: `health.ews.score` — chart ALL rows for the client
  (superseded rows ARE the history), not just `superseded=False`:
  `search([('client_id','=',id)], order='score_datetime')` → points of
  `{score_datetime, total, band}`. (`health_telemonitoring/models/health_ews_score.py`:
  fields `client_id`, `score_datetime`, `total`, `band`, all indexed.)
- **Threshold bands (per-client, clinically meaningful)**:
  `health.vitals.threshold` (`health_telemonitoring`… actually
  `health_vitals/models/health_vitals_threshold.py`): fields `client_id`,
  `vitals_type_id`, `severity` (warning/critical), `min_value`, `max_value`.
  Overlay each type's warning/critical bounds as ECharts `markLine`/
  `markArea` so a clinician sees where THIS patient's alert lines sit. Types
  with no threshold → no band (that is fine; do not invent generic ranges).

**Theme (flat-mono, dark-aware):**
- `health_theme/static/src/scss/primary_variables.scss:203-354` exposes
  `:root` CSS vars: `--vu-brand-primary` (#1565c0), `--vu-status-success`
  (#176B47), `--vu-status-warning` (#946200), `--vu-status-danger`
  (#C0332A), `--vu-text-secondary`, `--vu-border-soft`, `--vu-surface-card`;
  dark-mode overrides under `[data-theme='dark']`. Read these at render via
  `getComputedStyle(document.documentElement).getPropertyValue('--vu-…')`
  and feed them into the ECharts option, so charts follow the active theme
  (light/dark). NEWS2 band areas: success/warning/danger vars for 0-4 / 5-6 /
  7+. The PWA sparkline palette (`vitals-components.js:76-86`) is the same
  intent — match it.

---

## 2. Architecture

health_twin 19.0.2.0.0; `depends` += `biz_bi`. New files only; NO shared edits.

### 2.1 Data method `chart_series(patient_id, days)`

On a health_twin model — put it on `health.twin.risk` as an `@api.model`
method (it is the twin's data facade). Runs under the CALLING USER's env
(NOT sudo) so observation/score record-rules apply — a manager who can open
the patient chart already has read on their catchment's vitals; a user who
can't see the patient can't reach the form at all. Returns ONE JSON-able dict
(one RPC for the whole tab):

```
{
  'range_days': 30,
  'panels': [
    {'key': 'bp', 'title': 'Blood Pressure', 'unit': 'mmHg',
     'series': [{'name':'Systolic','points':[[iso, v], …]},
                {'name':'Diastolic','points':[[iso, v], …]}],
     'bands': [{'severity':'warning','min':…,'max':…}, …]},   # per-client thresholds
    {'key':'hr', …}, {'key':'spo2', …}, {'key':'temp', …},
    {'key':'weight', …},
    {'key':'news2', 'title':'NEWS2', 'unit':'',
     'series':[{'name':'NEWS2','points':[[iso, total], …]}],
     'band_zones':[[0,4,'success'],[5,6,'warning'],[7,20,'danger']]},
  ],
}
```
- Resolve the vitals-type ids ONCE (single search of health.vitals.type for
  the needed codes); call `get_trend` per type with
  `date_from = now - days`. Skip a panel whose series are all empty AND the
  patient has never had that type (keep BP/HR/SpO₂/temp/weight panels even if
  empty — show an empty state; only drop glucose when absent).
- `days` clamped to one of {7,30,90}; default 30.
- Points as `[iso_string, value]` pairs (ECharts time axis eats them).

### 2.2 The widget (static/src/js/twin_trend_charts.js + .xml + .scss)

`registry.category("view_widgets").add("twin_trend_charts", {Component:
TwinTrendCharts})`. Template `health_twin.TwinTrendCharts`.

- `setup()`: `this.orm = useService("orm")`; `useState({days:30, loading:true,
  panels:[]})`; a `useRef` per panel container (or one container the widget
  fills with N child divs). `onWillStart`/an effect loads
  `this.orm.call('health.twin.risk','chart_series',[resId, this.state.days])`.
- `onMounted` + after each data load: for each panel, `echarts.init` its
  container and `setOption` a **line** chart — time x-axis, value y-axis,
  flat-mono series colors from the CSS vars, threshold `markArea`/`markLine`
  from `bands`, NEWS2 `markArea` zones from `band_zones`, tooltip on, dataZoom
  optional. Keep one echarts instance per panel; store them; `dispose()` all
  in `onWillUnmount`.
- Range buttons 7/30/90 → set `state.days`, re-fetch, re-render (dispose+init
  or `setOption(..., {notMerge:true})`).
- ResizeObserver on the container → `chart.resize()` (clone biz_bi
  ChartRenderer). Guard: only init a chart when its container has non-zero
  size (a hidden notebook tab has zero height until shown — re-init/resize on
  tab-visible; simplest: init lazily when the panel ref first has size, and
  call `resize()` on a ResizeObserver).
- Empty state per panel: if `series` all empty → render a muted "Chưa có dữ
  liệu / No readings yet" placeholder instead of an echarts canvas.
- Flat-mono only, no gradients. Dark-mode: read the CSS vars at render (they
  already flip under `[data-theme='dark']`), so a theme switch on next render
  is correct; a live re-theme without reload is not required this phase.

### 2.3 Assets

Bundle the widget JS/XML/SCSS on `web.assets_backend` in
`health_twin/__manifest__.py` (after biz_bi in the dep graph so echarts is
present). SCSS pulls the `--vu-*` vars; no hardcoded hex except as a fallback.

### 2.4 Sanctioned edits (exhaustive)

| Module | File | What may change |
|---|---|---|
| health_twin | new JS/XML/SCSS widget, views/res_partner_views.xml (Trends tab inherit), models/health_twin_risk.py (`chart_series` method only), __manifest__.py (version + biz_bi dep + assets), i18n/vi.po, tests | everything within health_twin |

NO edits to biz_bi, health_vitals, health_telemonitoring, health_base,
health_pwa. No PWA bump (backend-only).

---

## 3. Safety rails (binding)

- `chart_series` runs under the user env (NOT sudo) — record rules must gate
  which patients' vitals a user can chart (test 4). No PHI leaves the server;
  the widget only renders numbers the user already has ACL to read.
- Flat mono, chatter untouched, no gradients (§4).
- No pip; biz_bi is already installed (the echarts source).
- QA fixtures deleted + fresh-cursor verified (§5.34).

## 4. Tests (tests/test_twin_charts.py; ~8)

Widget rendering is browser-QA'd (evidence pack); the ORM method is
unit-tested:
1. `chart_series` happy path: a patient with a week of HR + BP + SpO₂ +
   temp + weight observations and 3 NEWS2 scores → panels list contains bp/
   hr/spo2/temp/weight/news2, each with the right points count, oldest-first,
   `[iso, value]` shape; NEWS2 panel has all 3 scores incl. superseded ones.
2. Threshold bands: a `health.vitals.threshold` (warning + critical) for the
   patient's HR → the hr panel's `bands` carries both severities' min/max.
3. Range clamp: `chart_series(pid, 999)` clamps to 90; `chart_series(pid, 5)`
   clamps to a valid value (7); default when omitted is 30. Points respect
   the `date_from = now - days` window (an observation older than the window
   is excluded).
4. ACL/record-rule: a nurse in province A calling `chart_series` for a
   province-B patient gets empty/……(record rules exclude the observations) —
   assert no cross-catchment leak (the method is NOT sudo).
5. Empty patient: no observations, no scores → panels still present for the
   core vitals with empty series (so the UI can show empty states); glucose
   panel absent when the patient has no glucose ever.
6. NEWS2 history includes superseded: create two scores (one superseded) →
   both appear in the news2 panel (history), not just the current one.
7. spo2 union: readings under both `spo2` and `spo2_po` merge into one
   SpO₂ panel, time-ordered.
8. §5.32 discipline if any HttpCase is added; otherwise TransactionCase only.

## 5. Deploy / verify (conventions §2)

- Backend-only: `-i` nothing (module exists) → `-u health_twin,biz_bi`?
  NO — only `-u health_twin` (adding biz_bi to depends does not require
  upgrading biz_bi; but the FIRST install of the new dep edge may need
  `-u health_twin` to pick up the manifest change — verify the module
  upgrades cleanly). `--test-enable --test-tags /health_twin
  --stop-after-init --workers 0`. Result line; restart; `/web/login` 200.
- **Browser evidence pack (DoD item 5 / §8.1)** to
  `docs/strategy/reports/twin-phase2-evidence/`, driven from the REAL path:
  log in (a head-nurse/ops user with catchment), Healthcare → Client
  Management → open a patient WITH vitals history → the **Trends** tab →
  screenshot the ECharts panels (BP/HR/SpO₂/temp/weight/NEWS2) with a
  threshold band visible; toggle a range button (30→90) and screenshot;
  **screenshot dark mode** (flip the theme) to prove the CSS-var colors
  follow; capture the console (must be clean — ECharts init errors show
  here). Seed a QA patient with a week of readings + a NEWS2 score + one HR
  threshold so panels + a band are visible; DELETE all QA rows after and
  fresh-cursor verify (§5.34). NOTE the tab-visibility resize gotcha
  explicitly (did the charts size correctly when the tab was first opened, or
  need a resize nudge?).

## 6. Report back

Standard §8 (report committed to
`docs/strategy/reports/twin-phase2-report.md`), plus: (a) the evidence pack
incl. the dark-mode shot, (b) confirmation of the biz_bi/echarts load path
(did depending on biz_bi suffice, or did you need loadJS?), (c) the
tab-visibility/resize handling you settled on, (d) QA cleanup fresh-cursor
confirmation, (e) any new gotcha (OWL view-widget + ECharts + hidden-tab
sizing is fertile ground — flag whatever bit you).

Kickoff line: `Implement the phase specified in docs/strategy/handovers/twin-phase2.md.`
