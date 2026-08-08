# Phase RT-2 handover — "Just show me the records" in the guided wizard

Stream: **Records Table**, final phase. Prereq: RT-1 live (`cd8e97ce`).
Read `docs/strategy/HANDOVER-CONVENTIONS.md` (ledger through §5.140 is
recent and directly relevant — especially §5.137 int(get_param),
§5.138 dropEffect, §5.139 table-in-tile cost, §5.140 sheet names), then
`docs/strategy/reports/records-table-phase1-report.md`, then this doc.

## 1. What this phase is

Give non-technical creators the records feature inside the hub's guided
Create Report wizard (`biz_bi_cms`): a **"Chart | Records list"** choice
on step 2 — Records list = tick the columns you want, keep the date
range, preview the rows, export to Excel, save it to a dashboard. No
drag-and-drop needed here; the wizard stays the friendly path, Explore
stays the power path.

## 2. Binding non-goals

- ONLY `addons/biz_bi_cms/**` + report/evidence paths + ledger appends.
  `biz_bi` is DONE — zero edits (everything RT-2 needs shipped in RT-1;
  if you believe a seam is missing, re-read the RT-1 report first, then
  record it as a blocker rather than editing biz_bi).
- No AI on the records path (nlq is chart-shaped; the AI box stays on
  the chart path only).
- No drag-reorder in the wizard column picker beyond simple ↑/↓ or
  chip-drag if trivial; no per-column sort UI; no column search beyond
  the folder grouping; no pivot/summary options here.
- RT-1's deferred items stay deferred (label lookup >2000 distinct,
  UTC datetimes, widget fetch size).

## 3. Verified plumbing facts (do not re-derive — all shipped in RT-1)

- Engine detail mode: request `{mode:'detail', dimensions:[{field_id}],
  measures:[], filters, sort, limit}`; grain ignored; envelope carries
  `meta.total_count` + `meta.truncated`; `value_labels` attached
  per-reader; nulled columns come back NULL with `'nulled': true`.
- Saved shape: `config_json` `{version:1, chart_type:'table',
  mode:'detail', slots:{columns:[{field_id}], x/values/series: []},
  filters, sort, limit, display}` — `bi.chart._to_query_request`
  derives the request; dashboard global filters still apply.
- Export: `POST /bi/export/xlsx` (`csrf`), body `request_json` +
  `title`; server ceiling `biz_bi.export_row_cap` (default 20000,
  §5.137 guard); returns xlsx with names-not-ids, frozen header,
  autofilter, honest overflow row; audit-logged. Client pattern:
  fetch → blob → `a.download` (see Explore's implementation).
- Renderer: `DataTable` accepts `maxRows` (dashboard passes 200 —
  §5.139 is why; the wizard preview MUST also pass a cap, use 100).
- Wizard internals (AH-2/AH-3): `report_wizard.js` state machine
  (step 1 dataset cards → step 2 build → step 3 preview/save),
  `get_builder_metadata` fields with role/folder, save flow =
  `orm.create("bi.chart", ...)` (LIST — destructure) +
  `bi.dashboard.add_chart` via `get_wizard_targets()`.
- Six pre-existing biz_bi full-suite failures (names in the AH-3
  report) — irrelevant here if biz_bi is untouched, but the
  biz_bi_cms suite (24 tests as of AH-3) must stay green.

## 4. Build spec (all in `addons/biz_bi_cms`)

### 4.1 Step 2 — the path choice
Top of the build card: segmented **Chart | Records list** (default
Chart, which is exactly today's UI — zero regression). Choosing
Records list swaps the pickers for:
- **Column checklist**: visible fields grouped by folder (reuse the
  metadata the wizard already loads), checkbox per field; ticking
  appends a chip to an ordered **"Your columns"** row above; chips
  have × and ↑/↓ (or drag if trivial — remember §5.138 dropEffect).
  Pre-tick nothing; require ≥1 column to continue.
- **Date range** chip row stays exactly as-is (same filter applies).
- Chart gallery hidden on this path.
- Step indicator/back/advanced-escape behavior unchanged; the
  advanced escape passes the dataset as today (Explore will open in
  its default mode — acceptable, note it).

### 4.2 Step 3 — preview & save (records variant)
- Preview: `DataTable` with `maxRows: 100` over a detail-mode query
  (`limit: 1000` request); banner when `meta.truncated` OR
  total_count > rendered: "Showing first 100 of N records — the
  saved report and Excel export include more" (exact honest copy).
- **Excel button** beside the preview (same POST/blob pattern as
  Explore, title = report name).
- Name default: "<Dataset> records" (translated); dashboard target
  UI unchanged; save writes the RT-1 config shape verbatim
  (`chart_type:'table'`, `mode:'detail'`, ordered `slots.columns`,
  date filter, `sort: []`, `limit: 5000`).
- After save → dashboard as today; the tile renders via the RT-1
  dashboard path (200-row cap) — verify in QA, change nothing.

### 4.3 Styling / i18n
`.bi-wizard` additions only; flat mono, tokens, reduced-motion; vi
strings for every new label in `i18n/vi.po`, loader-verified (§5.134).

## 5. Tests (`biz_bi_cms/tests/test_wizard_records.py`, post_install)

1. `test_records_config_shape` — build the exact config the wizard
   saves; `_to_query_request` yields mode detail + ordered columns;
   engine returns record rows; extra_filters (dashboard global date)
   still append.
2. `test_records_save_flow` — creator saves a records chart to a NEW
   dashboard via `get_wizard_targets` path; widget exists;
   `get_dashboard_data` includes it.
3. `test_records_column_order_preserved` — columns saved [c,a,b] come
   back [c,a,b] through the round trip.
4. Existing biz_bi_cms suite stays green (quote the result line).

## 6. Deploy + report-back

- Deploy per conventions §2 + §5.130 check, `-u biz_bi_cms`, vietuat.
  Verbatim `odoo.tests.result` line for biz_bi_cms.
- Browser evidence →
  `docs/strategy/reports/records-table-phase2-evidence/`: real path
  login → CMS → ANALYTICS → Analytics → ＋ Create Report → dataset →
  step 2 "Records list" → tick 4+ columns incl. a lookup field
  (names must render, not ids) → reorder one → date range chip →
  step 3 preview + truncation banner (stage honestly) → Excel
  download shown (names visible) → save to new dashboard → tile
  renders with CMS chrome. Both languages for step 2 (vi_VN labels).
  Console logs; audit row ids; fixtures deleted + fresh-cursor
  verified (§5.128 scoped DELETE for audit rows).
- Report → `docs/strategy/reports/records-table-phase2-report.md`
  (committed): files, deviations, verbatim tests, anything deferred,
  new gotchas (§5.141+). Self-review before reporting: re-read every
  file against this spec; re-verify deployed behavior independently.

## Kickoff line

Implement the phase specified in docs/strategy/handovers/records-table-phase2.md.
