# Phase AH-2 handover — `biz_bi_cms` Guided Create Report wizard

Stream: **Analytics Hub**. Prereq: Phase AH-1 (module `biz_bi_cms`, hub
landing, sidebar wiring) is live. Read
`docs/strategy/HANDOVER-CONVENTIONS.md` first, then
`docs/strategy/reports/analytics-hub-phase1-report.md` (what actually
shipped), then this doc.

## 1. What this phase is

Replace the Phase-1 "＋ Create Report" CTA target (which currently opens
the raw Explore builder) with a **guided 3-step report wizard** inside the
hub — the consolidation of Explore for non-technical creators:

1. *What do you want to look at?* — pick a dataset from friendly cards.
2. *Describe or build* — an "Ask in your own words" AI box (when
   available) OR simplified pickers: one measure, one group-by, optional
   split-by, optional date range. Chart type auto-recommended,
   overridable from a compact gallery.
3. *Preview & save* — live preview, name it, pick/create a dashboard,
   one Save button → chart created + added + navigate to the dashboard.

An "Open in advanced builder" escape hatch (→ existing Explore) exists on
steps 2–3. The existing Explore/Home/backend app remain untouched.

Plus three carry-overs from the Phase-1 report:

- **Version bump to `19.0.1.1.0`** and a `migrations/19.0.1.1.0/` post
  script re-running `apply_role_gates` + `grant_creator_group` (the
  1.0.0 script never ran — Odoo only runs migrations when the installed
  version is BELOW the module version, and the module installed at
  1.0.0).
- **Auto-grant for new/re-roled users**: additive `_inherit` of
  `res.users` inside `biz_bi_cms` — when `access_role_id` is set (create
  or write) to a role whose name is in `hooks.ANALYTICS_ROLE_NAMES`,
  `Command.link` `biz_bi.group_bi_creator` (add-only, never remove;
  reuse the hook's logic — do not duplicate the role list). Phase-1
  measured this gap live: a user created after install had no BI group.
- **Ledger update**: append the Phase-1 report's proposed **§5.127**
  (granted-group latent-ACL gotcha) plus its two smaller gotchas
  (bi.audit.log makes QA personas undeletable; `.po` occurrences work
  for arbitrary business models) to
  `docs/strategy/HANDOVER-CONVENTIONS.md`, keeping that file's numbering
  and style. Source text: `docs/strategy/reports/analytics-hub-phase1-report.md`.

## 2. Binding non-goals

- NO edits outside `addons/biz_bi_cms/**` + the report/evidence paths +
  the sanctioned §5 ledger append in
  `docs/strategy/HANDOVER-CONVENTIONS.md`. (Explore needs nothing — it
  already accepts `params.dataset_id`/`chart_id` — biz_bi stays
  untouched; the flagged `.catch()` cleanup in `explore_action.js`
  stays OPEN, do not do it.)
- NO drag-and-drop in the wizard; NO multi-measure combos; NO manual
  filter builder beyond the single optional date-range chip row; NO
  editing of existing charts here (edit continues to route to Explore
  via the dashboard's existing edit path).
- NO `compose_report` (AI whole-dashboard) surface in this phase.
- NO new server models; at most thin `@api.model` helpers on existing
  models inside biz_bi_cms.

## 3. Verified plumbing facts (do not re-derive)

All in `addons/biz_bi/`:

- **Dataset list**: `searchRead("bi.dataset", [["state","=","published"]],
  ["name","description","is_certified","storage_mode"])` — exactly what
  Explore does (`explore_action.js:83-87`).
- **Metadata**: `bi.dataset.get_builder_metadata()`
  (`models/bi_dataset.py:570-600`) → `{id, name, description,
  storage_mode, is_certified, freshness_at, fields:[{id, name,
  description, data_type, role, default_agg, folder, node, format,
  selection_labels, glossary}]}`. Masked + non-visible fields already
  removed. Skip `role === "id"` fields in pickers (Explore does,
  `explore_action.js:228`).
- **Field roles**: measures have `role === "measure"` (aggregate with
  `default_agg`, fallback `sum`); group-by/split-by candidates are the
  non-measure, non-id fields; date fields are `data_type` date/datetime
  (check the exact literals in `bi_field.py`) and take a `grain`
  (default `"month"`, options `["year","quarter","month","week","day"]`,
  `explore_action.js:40`).
- **Recommendation**: `import { checkCompatibility, recommendChartType }
  from "@biz_bi/core/chart_recommender"` —
  `recommendChartType(dims, measures)`, `checkCompatibility(type, dims,
  measures)` → `{ok, reason}` (`core/chart_recommender.js:31,48`).
  Explore's chip shapes: dims = `[{id, grain?, ...field}]`, measures =
  `[{id, agg, ...field}]`.
- **Preview**: `bi_data` service (`services/bi_data_service.js`) —
  `this.biData.query(request)` where request =
  `{dataset_id, dimensions:[{field_id, grain?}], measures:[{field_id,
  agg}], filters:[{field_id, op, value}], sort, limit}` — clone
  Explore's `buildRequest()` semantics (`explore_action.js:402-426`),
  including the `sort: [{ref:"m0", dir:"desc"}]` default except for
  line charts, `limit: 500`.
- **Renderers**: `ChartRenderer` (props `{envelope, config}` where config
  = `{chart_type, display:{}}`), `KpiCard`, `DataTable`, `PivotTable` —
  import from `@biz_bi/components/explore/...`; pick renderer by the
  same `rendererKind` logic (`explore_action.js:445-456`): kpi/table/
  pivot/chart.
- **Config JSON (save format)**: clone `buildConfigJson()`
  (`explore_action.js:466-483`) EXACTLY: `{version:1, chart_type,
  slots:{x:[{field_id, grain}], values:[{field_id, agg}],
  series:[{field_id, grain}]}, filters:[{field_id, op, value}],
  sort:[], limit:500, display:{}}`. Wizard mapping: group-by → `x[0]`,
  measure → `values[0]`, split-by → `series[0]`, date range →
  `filters[0]`.
- **Date-range filter format**: read `defaultOpFor`
  (`explore_action.js:322`), `RELATIVE_RANGES`
  (`core/range_labels.js`) and the filter-chip markup in
  `explore_templates.xml` for the exact `{op, value}` a relative date
  range uses — replicate it verbatim; do NOT invent a format.
- **AI**: `orm.call("bi.ai", "is_available", [])`;
  `orm.call("bi.ai", "nlq_chart", [datasetId, prompt])` → `{config}` or
  `{error}` (`models/bi_ai.py:262-277`); config may carry `name`.
  Materialize it into wizard state the way Explore's
  `materializeConfig` does (`explore_action.js` ~140-162: map each
  `field_id` back to a metadata field to build chips; unknown field →
  drop + warn). AI errors → non-blocking warning notification, stay on
  step 2.
- **Save + add**: `orm.create("bi.chart", [{name, dataset_id,
  chart_type, config_json}])` — **returns a LIST, destructure** (the
  `5e91455e` bug). Then `orm.call("bi.dashboard", "add_chart",
  [[dashboardId], chartId])`; new dashboard via `orm.create(
  "bi.dashboard", [{name}])` (also a list). Then
  `doAction({type:"ir.actions.client", tag:"biz_bi.dashboard",
  params:{dashboard_id}})` — chrome persists (Phase-1
  `match_action_tags`). Reference flow: `explore_action.js:485-537`.
- **Dashboard choices for step 3**: `searchRead("bi.dashboard", [],
  ["name"])` — record rules scope it to what the user may see; creators
  may only WRITE their own + fully-open ones, so on `add_chart`
  AccessError, surface a clear notification ("You can't edit that
  dashboard — create your own") rather than crashing.
- Cross-module JS imports work via `@biz_bi/...` aliases (standard Odoo
  asset module names).
- **AI availability probe is already safe for creators**: Phase 1 added
  `biz_bi_cms/models/bi_ai.py` — `is_available()` returns `False` on
  `AccessError` (creators can't read `bi.ai.provider`). The wizard can
  call it without a guard; `ai_available` is also already in
  `get_hub_data()`'s payload and hub component state.
- Phase-1 realities (from its report): `ROLE_GATES` in `hooks.py` is
  keyed by leaf xml-id; `res.users` role field is `access_role_id`
  (`access_roles/models/res_users.py:30`); ANALYTICS section sequence
  is 37 (crm 10, ops 20, finance 30, clinical 32, interop 35, admin 40).

## 4. Build spec (all inside `addons/biz_bi_cms`)

### 4.1 `ReportWizard` component (`static/src/components/wizard/`)
`report_wizard.js` / `report_wizard.xml` / `report_wizard.scss`. A
full-viewport overlay (fixed, above the hub content, below dialogs)
mounted by the hub when `state.wizardOpen`. Props: `{onClose}`.
Internal state: `{step: 1|2|3, datasets, datasetId, metadata,
measure, agg, groupBy, grain, splitBy, dateField, dateRange, chartType,
userPickedType, envelope, loading, chartName, aiPrompt, aiBusy,
dashboards, targetDashboardId, newDashboardName, saving}`.

**Chrome**: top bar with 3 step indicators (numbered dots + labels,
clickable only backwards), a close ✕ (confirm-free — state is cheap),
and on steps 2–3 a quiet "Open in advanced builder" link →
`doAction({tag:"biz_bi.explore", params:{dataset_id}})` (after save use
`params:{chart_id}`), then `onClose()`.

**Step 1 — dataset cards**: grid of published datasets — name,
description, "Certified" badge when `is_certified`. One dataset →
auto-advance. Click → load `get_builder_metadata`, precompute field
groups (measures / dimensions / date fields), pick the first date field
as `dateField` default, go to step 2.

**Step 2 — describe or build**:
- If AI available: prominent "Ask in your own words" box (textarea +
  submit, busy state). Success → materialize config into wizard state
  (measure/groupBy/splitBy/chartType/name), jump to step 3.
- Manual pickers (always visible, under an "or build it yourself"
  divider when AI is shown): **Measure** (required — measure-role
  fields; picking sets `agg = default_agg || "sum"`), **Group by**
  (required — non-measure fields; date field ⇒ grain chips, default
  month), **Split by** (optional), **Date range** (optional — only if a
  date field exists: chip row from `RELATIVE_RANGES` + "All time"
  default).
- Chart type: auto via `recommendChartType` on every change unless
  `userPickedType`; compact gallery strip (subset is fine: bar,
  bar_stacked, line, area, donut, kpi, table, pivot — keep it
  approachable; incompatible types disabled with `checkCompatibility`
  reason as tooltip).
- "Preview →" button enabled once measure + group-by are set (kpi needs
  only measure — allow empty group-by when chartType is kpi).
- Live mini-preview on this step is NOT required; step 3 is the preview.

**Step 3 — preview & save**:
- Big renderer (same rendererKind switch as Explore) fed by a debounced
  (400ms) `bi_data.query` of the built request; loading skeleton;
  friendly empty/error state ("No data for this combination yet").
- Name input (prefilled from AI `config.name` when present; otherwise a
  sensible default like "<Measure> by <Group by>"), dashboard target:
  radio list of writable dashboards + "New dashboard" option with name
  input (default "My dashboard").
- **Save report** button: create chart (destructure!), resolve/create
  dashboard, `add_chart`, success notification, `onClose()`, navigate to
  the dashboard. Errors: notification, stay on step (no partial
  navigation); if the chart got created but `add_chart` failed, keep the
  chartId so retry doesn't duplicate.

### 4.2 Hub integration (`hub_action.js`)
- CTA + per-workspace "Create one" links now set `wizardOpen = true`
  (creator-gated as in Phase 1).
- After the wizard navigates to a dashboard, the hub unmounts naturally
  (action switch) — no extra work.

### 4.3 Styling
Same rules as Phase 1: `.bi-wizard` namespace, vu.theme tokens, flat mono
colors, inline-SVG icons (no font-awesome in the body), skeleton loaders,
no `overflow` traps around the pickers (native selects or simple custom
lists are fine; if custom dropdowns, no ancestor containment). The step
transitions should feel premium: subtle slide/fade (CSS only,
`prefers-reduced-motion` respected).

### 4.4 i18n
Every string through `_t`; extend `i18n/vi.po` with all wizard strings.

## 5. Tests (`tests/test_wizard_flow.py`, tag `post_install`)

Server-side proof of the wizard's contract (the JS itself is covered by
the browser evidence pack):

1. `test_wizard_config_roundtrip` — build a config_json exactly as the
   wizard would ({version:1, slots x/values/series, filters relative
   date, sort [], limit 500, display {}}) on a seeded dataset; create a
   `bi.chart` with it; assert `_to_query_request()` succeeds and the
   engine returns an envelope (clone whatever biz_bi's own chart tests
   do — read `addons/biz_bi/tests/`).
2. `test_wizard_save_flow` — as a creator user: create chart + new
   dashboard + `add_chart`; assert one widget row exists, dashboard
   `get_dashboard_data` includes it; re-running `add_chart` with the
   same chart doesn't crash.
3. `test_creator_cannot_add_to_foreign_dashboard` — creator A saves a
   chart, tries `add_chart` on a dashboard owned by B (member-scoped
   workspace): AccessError raised (this is the case the UI must catch).
4. `test_nlq_unavailable_is_clean` — with no usable AI provider,
   `bi.ai.is_available()` is False (wizard hides the box; no crash).
5. `test_auto_grant_on_role_assign` — creating a user with a gated
   `access_role_id`, and separately writing a gated role onto an
   existing ungated user, both add `group_bi_creator`; assigning an
   ungated role adds nothing and removes nothing; re-assigning is
   idempotent.
6. `test_migration_reruns_gates` (or prove via the upgrade log) — after
   `-u biz_bi_cms` at `19.0.1.1.0`, a pre-existing gated-role user
   created before the upgrade holds `group_bi_creator` (the 1.0.0
   migration-never-ran gap is closed).

## 6. Deploy + report-back

- Deploy per conventions §2 (`-u biz_bi_cms`, db `vietuat`). Verbatim
  `odoo.tests.result` line.
- Browser evidence pack →
  `docs/strategy/reports/analytics-hub-phase2-evidence/`: real path =
  CMS → Analytics → ＋ Create Report → step 1 (screenshot) → pick
  dataset → step 2 (screenshot; if AI is configured on vietuat also
  drive one AI ask; if not, note it and drive manual) → pick measure +
  group-by → step 3 preview (screenshot) → name + New dashboard → Save
  → lands on the dashboard WITH sidebar chrome (screenshot) → the new
  chart/dashboard/widget row ids from the server. Then delete the QA
  fixtures and re-verify in a fresh cursor. Console logs per screen.
  Also screenshot the advanced-builder escape hatch landing in Explore
  with chrome intact.
- Report → `docs/strategy/reports/analytics-hub-phase2-report.md`
  (committed): file list, deviations, verbatim tests, the exact
  date-range `{op, value}` format you found, whether AI was live on
  vietuat, any new gotcha.

## Kickoff line

Implement the phase specified in docs/strategy/handovers/analytics-hub-phase2.md.
