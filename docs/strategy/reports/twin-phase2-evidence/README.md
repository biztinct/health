# health_twin — Phase 2 browser evidence pack (Vitals & NEWS2 Trend Charts)

The `twin_trend_charts` OWL view-widget rendering an ECharts small-multiples
grid of BP / HR / SpO₂ / temperature / weight / NEWS2 trend panels on the
patient chart, with the patient's own alert-threshold band overlaid and NEWS2
score-zone shading — driven by the single `chart_series(patient_id, days)` ORM
data method (one RPC for the whole tab).

## User + seeded data
- User: **twin_qa_trends** (created for QA, **deleted after** — fresh-cursor
  confirmed removed). Given the healthcare nurse/head-nurse groups (the tab is
  `groups="health_base.group_healthcare_nurse"`, mirroring the existing
  health_vitals "Alert Thresholds" tab) and, to load the standard patient
  form past the CMS chat/access polling, temporary system/Zalo groups.
- QA patient: **ZZ QA Twin Trends Patient** (id 8729), Hà Nội catchment.
  Seeded a week+ of BP/HR/SpO₂/temp/weight observations, one **HR warning
  threshold** (min 60 / max 90) for the band overlay, and 7 NEWS2 score rows
  (one current, six superseded — history). All deleted after; fresh-cursor
  verified.

## What the shots show
- `01-trends-light-30d.png` — the six panels at the **30-day** range (default),
  **light** theme. Flat-mono blue lines (no gradients, house rule §4). The
  **Heart Rate** panel shows the dashed **"warning max"** threshold line at 90
  (the patient's own `health.vitals.threshold`). The **Blood Pressure** panel
  carries two series (Systolic + Diastolic) with a legend. **NEWS2** shows the
  score-zone `markArea` shading (0–4 success / 5–6 warning). Per-panel axis
  units (mmHg, bpm, %, °C, kg). Range selector 7d/30d/90d, 30d active.
- `02-trends-dark-90d.png` — the same widget after flipping to the **dark**
  theme and the **90-day** range. The lines flip to the lighter accent-blue
  (`#42A5F5`) and axis labels to white-72%, proving the chart colours are read
  live from the `--vu-*` CSS vars and follow `[data-theme='dark']`. Threshold
  line + NEWS2 zones still render on the dark canvas.
- `console-log.txt` — no widget console errors (light or dark).

## How the widget was exercised (and an honest caveat on the entry point)
The handover §5 asks to drive the Trends tab from **Healthcare → Client
Management → open a patient → Trends**. On vietuat that flow does NOT reach
the tab, for a reason *outside* this phase's sanctioned scope:

- The Trends tab is added (correctly, per the sanctioned-edits table) to
  **`health_base.view_health_patient_form`** — the standard patient form.
  `get_view()` for that view, as the nurse QA user, **does** contain the
  `twin_trends` page and the `twin_trend_charts` widget (server-confirmed).
- But this deployment's **actual** client surface is a *separate, standalone*
  res.partner form, **`health_fieldservice.view_health_patient_form_ops`**
  (js_class `ops_client_profile_form`, **priority 0** → the default patient
  form; the ops client list forces it via `form_view_ref`). That curated view
  has its own nine hand-authored pages and does **not** inherit
  `view_health_patient_form`, so **none** of the standard form's clinical
  inherit pages surface there — not the new Trends tab, and not the
  pre-existing health_vitals "Alert Thresholds" / "Vitals" tabs either. This
  is the already-tracked **CMS-sidebar discoverability gap**; surfacing the
  Trends tab in the ops-profile is a `health_fieldservice` edit, outside this
  phase's sanctioned files. (See the report §Deviations.)
- The standard `view_health_patient_form` also could not be force-opened
  cleanly (a CMS Zalo-chat systray poll raises AccessError and crashes the
  action transition) — it is not a maintained user surface in this build.

So the widget was exercised through its real runtime path instead: the
widget's **own** `_palette()` + `_buildOption()` methods (pulled live from the
`view_widgets` registry — not reimplemented) rendering the live
`chart_series(8729, …)` RPC payload into ECharts canvases, using the widget's
real SCSS classes. This proves the two things that could break at runtime —
the data method over RPC and `window.echarts` availability (5.5.1, from
biz_bi; depending on biz_bi sufficed, **no loadJS needed**) — plus the full
option build (threshold `markLine`, NEWS2 `markArea`, theme-var palette,
per-panel units, empty-state handling). The `chart_series` method itself is
additionally covered by 8 passing unit tests.

## Tab-visibility / resize
The widget inits each ECharts instance in a `useEffect` that runs after the
panel DOM is patched, guards against zero-size hosts (a hidden notebook tab
has zero height until shown), and re-inits skipped charts + resizes live ones
from a rAF-coalesced ResizeObserver — so first-open sizing is correct without
a manual nudge. (In Odoo 19 the Notebook mounts only the active page's
content, so the widget mounts fresh, already visible, when the tab is opened.)
