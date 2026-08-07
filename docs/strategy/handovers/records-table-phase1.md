# Phase RT-1 handover — biz_bi Records Table + Excel export (Explore)

Stream: **Records Table** (follow-on to Analytics Hub). Read
`docs/strategy/HANDOVER-CONVENTIONS.md` first (deploy §2, ledger —
§5.127–§5.136 are all recent and relevant), then this doc. All work is in
`addons/biz_bi/**` (this IS a core biz_bi feature) + report/evidence
paths + ledger appends. Nothing else. Path-scoped `git add` (unrelated
unstaged changes are present).

## 1. What this phase is

Today the Table chart aggregates: "revenue by catchment" gives 2 rows.
Users want a **Records view**: drag any fields in as columns — as many
as they like, appended after the last column — and see one row per
underlying record, honoring all filters, with an **Excel export** button.

Deliverables:
1. Engine **detail mode** — record-level SELECT, no GROUP BY, same
   trust boundary (RLS, static filters, multi-company, masking).
2. **Records / Summary toggle** on the Table chart type in Explore,
   with a drag-native column UX (drop fields directly onto the table,
   insertion caret, reorder by dragging headers, per-header sort).
3. **Excel export** of exactly what the table shows (works for BOTH
   modes, saved or unsaved), preview capped at 5k with an honest
   "showing X of Y" banner, export capped at 20k (configurable),
   audit-logged.
4. Close a pre-existing masking hole this feature would widen (§3.9).

Phase RT-2 (later, separate handover): a "Just show me the records"
look in the hub's guided wizard. Do NOT build wizard/hub changes now.

## 2. Binding non-goals

- NO wizard/hub changes (`biz_bi_cms` untouched).
- NO virtualization/infinite scroll — the 5k preview cap makes the
  existing sticky-header table fine.
- NO row-level drill-through to Odoo records, NO inline editing, NO
  column formulas, NO CSV (xlsx only), NO scheduled exports.
- NO new security groups; export permission = "can run the query"
  (same as today's saved-chart export), always audited.
- Dashboard widgets keep working untouched: a saved Records chart
  renders through the same DataTable path via config_json; do not
  modify dashboard_action.js beyond what that requires (expected: zero
  — verify and state it).

## 3. Verified plumbing facts (do not re-derive)

1. Engine: `_resolve_request` (`bi_query_engine.py:170`) browses fields,
   validates grain/agg, builds `columns_meta` with refs `d0../m0..`;
   `_build_sql` (`:346-394`) ALWAYS emits GROUP BY when dimensions
   exist and aggregates every measure via `ALLOWED_AGGS`; `MAX_ROWS =
   5000` (`:30`); `run()` (`:103`) handles cache (per-user labels are
   attached AFTER cache via `_attach_relation_labels`, `:160-205` —
   keep that ordering in detail mode too, it's a privacy control).
2. `_build_where` (`:420-450`) is the single choke point for request
   filters + dataset static filters + RLS row rules + multi-company.
   Detail mode MUST go through it unchanged.
3. **Masking hole (§3.9, fix in this phase)**: `_resolve_request`
   applies `_nulled_field_ids` only to MEASURES (`:251`,
   `_build_sql:365-366` emits `SQL("NULL")`). A `mask_mode='null'`
   field used as a DIMENSION is returned in full today. In records
   mode that becomes whole-column egress. Fix: null the expression for
   nulled fields in BOTH roles and BOTH modes, and mark the column
   `'nulled': True` in columns_meta so the UI can show a "policy"
   hint. `_masked_field_ids` (hide) already blocks at `browse_field`.
4. Sort: `_build_order` orders by ref — read it before reusing; detail
   mode needs per-column sort `[{ref:'d3', dir:'asc'}]`.
5. Chart save format: `config_json` `{version:1, chart_type, slots:{x,
   values, series}, filters, sort, limit, display}` built by
   `explore_action.js:466-483`; server derives requests via
   `bi.chart._to_query_request` (`bi_chart.py:55-98`) — saved charts
   never send raw field lists (`controllers/main.py:52-90` docstring).
6. Export today: `GET /bi/export/xlsx?chart_id=` (`controllers/main.py:11-50`)
   — xlsxwriter, header format, number format, audit `'export'` log.
   It writes RAW dimension values (`str(value)`) — ids, not names, and
   no value_labels handling: the new export must fix that (use the
   post-label envelope).
7. Frontend: `DataTable` (`data_table.js`) formats via the single
   `formatDimensionValue`/`formatFull` choke point; `value_labels` on a
   column already maps ids→names (added for the catchment fix).
   Explore state/slots/drag: `explore_action.js:61-99` (state),
   `:252-320` (drag/drop + `slotAccepts` + `addToSlot`), gallery
   `CHART_REQUIREMENTS`/`checkCompatibility` in `chart_recommender.js`.
   `orm.create` returns a LIST (§ the 5e91455e bug).
8. i18n file is `i18n/vi_VN.po` (biz_bi) — extend it; loader-verify
   (§5.134: `get_web_translations(...)["messages"]`, ReadonlyDict).
9. biz_bi's full suite has **6 pre-existing failures** on vietuat,
   proven by pristine baseline (names listed in
   `docs/strategy/reports/analytics-hub-phase3-report.md:207-212`).
   Your gate: scoped tags green + full run shows EXACTLY those six.
10. Migration staging: touching other modules' registries needs `end-`
    not `post-` (§5.135). This phase should need NO migration (new
    request/config keys default off; no schema backfill) — say so.

## 4. Build spec

### 4.1 Engine detail mode (`models/bi_query_engine.py`)
Request gains `mode: 'detail'` (default `'aggregate'`, anything else →
UserError). In `_resolve_request` + `_build_sql` when detail:
- Every requested field (the client sends them all in `dimensions`;
  `measures` must be empty — validate) becomes a plain selected column
  `d<i>`: no GROUP BY, no aggregation. Numeric fields keep
  `role='measure'` in columns_meta so the client right-aligns/formats
  them, but carry no `agg`.
- `grain` is IGNORED in detail mode (records show the real date);
  strip it during resolution.
- Nulled fields (§3.9) select `SQL("NULL")` and set `'nulled': True`.
- Calculated fields compile with `allow_aggregates=False`; a
  calculated field whose expression uses aggregates → UserError
  naming the field.
- WHERE chain untouched. ORDER BY from request sort (any ref, asc/
  desc); default: first column asc for determinism. LIMIT/OFFSET as
  today (MAX_ROWS still 5000).
- **Honest total**: in detail mode also run `SELECT COUNT(*)` with the
  same FROM/WHERE (no group/order/limit) → `meta.total_count`;
  `meta.truncated` = `total_count > len(rows)`. Aggregate mode
  unchanged.
- `run(request, hard_cap=None)`: new optional kwarg replacing MAX_ROWS
  for the limit clamp — used ONLY by the export controller
  server-side. Never taken from the client payload: pop/ignore any
  'hard_cap' arriving in the request dict.
- Cache: unchanged path (key already includes the full request).
  Labels still attached post-cache.

### 4.2 Chart config + request derivation (`models/bi_chart.py`)
`config_json` gains `mode` and `slots.columns` (ordered
`[{field_id}]`). `_to_query_request`: when `mode == 'detail'`, build
`dimensions` from `slots.columns` (dedupe by field_id, keep first),
`measures=[]`, pass `mode`, `sort`, `limit` through; extra_filters
still append (dashboard global filters must keep working on a saved
Records widget). Aggregate path byte-identical to today.

### 4.3 Export (`controllers/main.py`)
- New `POST /bi/export/xlsx` (`type='http'`, `auth='user'`,
  `csrf=True`): body `request_json` (a raw engine request) and
  `title`. Validates like `/bi/query` does; runs
  `engine.run(request, hard_cap=export_cap)` where `export_cap =
  int(ir.config_parameter 'biz_bi.export_row_cap' or 20000)`
  (sudo read of the param only). Uses the returned envelope — i.e.
  AFTER `_attach_relation_labels` — so cells contain **names, not
  ids**; same for the existing saved-chart GET route (switch it to the
  post-label envelope too; that's a one-line consequence of §3.6).
- Cell writing: measures → `write_number` with `format_json`-derived
  num format (`#,##0` when decimals 0); dates/datetimes → real Excel
  dates (`add_format({'num_format': 'yyyy-mm-dd'})`); selection/
  relation labels via the same mapping the client uses
  (`value_labels` / `_selection_labels_for`); None → ''. Freeze the
  header row (`freeze_panes(1, 0)`), autofilter over the used range —
  it's the "open it and it just works" Excel feel.
- If `total_count > export_cap`: still export cap rows, and write a
  final bold row "Showing first N of M rows — refine filters for the
  full set" (honest, §"no silent caps").
- Audit: `'export'` log with `{'format':'xlsx', 'mode', 'rows',
  'columns', 'capped'}`.
- Client: fetch → blob → `a.download` (POST can't `window.open`);
  filename from chart name or "Records - <dataset>".

### 4.4 Explore UX (`static/src/components/explore/`)
State: `tableMode: 'summary'|'records'` (component state; persisted in
config as `mode`), `recordColumns: [chip]` (ordered), kept SEPARATE
from aggregate slots so toggling back restores the previous chart
exactly.

- **Toggle**: segmented control `Records | Summary` rendered only when
  `chartType === 'table'`, above the preview. Switching to Records the
  first time seeds columns from current slots (x + series + values
  order); switching back restores the stashed aggregate slots.
- **Drag-native table**: in Records mode the TABLE ITSELF is the drop
  target. Dragging a field over the header row shows an insertion
  caret between columns (compute index from header midpoints); drop
  inserts there. Drop anywhere on the body/empty area appends after
  the last column — the user's literal ask. Field-well double-click
  appends too. Header chips: drag to reorder (same caret), hover ×
  to remove, click cycles sort ▲/▼/none (sets request sort, refresh).
  `slotAccepts` logic does not apply — ANY visible field is a valid
  column (measures included, raw).
- **Empty state**: friendly full-width drop target: "Drag any fields
  here — one row per record" + subline about filters still applying.
- **Honest banner**: when `meta.truncated`, a slim bar above the
  table: "Showing 5,000 of 12,340 — refine filters or export up to
  20,000". Styled info, not error.
- **Export button**: toolbar icon+label "Excel" next to the row-count
  footer, visible for the Table chart in BOTH modes; busy spinner
  while the blob downloads; error → notification. Works unsaved.
- **Filters well stays** — records honor the same FILTERS chips
  (nothing to change; they ride the same request).
- FILTERS/gallery interplay: in Records mode the chart gallery
  collapses to just Table highlighted (other types disabled with
  reason "Switch to Summary for charts"); `recommendChartType` is
  bypassed. Save/Add-to-Dashboard keep working (config carries mode;
  dashboard renders DataTable with the same envelope contract —
  verify a saved Records widget on a dashboard during QA).
- Styling: `.bi-table-*` additions in `biz_bi.scss` — flat mono, the
  caret a 2px accent bar, `prefers-reduced-motion` respected, no
  ancestor overflow traps. Header sticky (already), first render
  skeleton unchanged.

### 4.5 i18n
All new strings through `_t`; extend `i18n/vi_VN.po`; loader-verify
(§5.134 pitfall).

## 5. Tests (extend `addons/biz_bi/tests/`, tag `post_install`)

New `test_detail_mode.py` (BiCase gives 3 partners, country m2o,
latitude measure, create_date):
1. `test_detail_returns_record_rows` — 3 fields (name, country_id,
   latitude) in detail mode → 3 rows, no aggregation, latitude raw;
   columns_meta refs d0..d2 with correct roles.
2. `test_detail_total_count_and_truncation` — with `limit=2`:
   2 rows, `meta.total_count == 3`, `truncated` True; without limit:
   not truncated.
3. `test_detail_respects_where_chain` — a request filter AND an RLS
   row rule both reduce the rows (clone the fixture usage from
   test_rls.py's row-rule test).
4. `test_detail_nulls_masked_dimension` — `mask_mode='null'` rule on
   the name field: detail rows carry None for it, columns_meta says
   nulled; AND (regression for §3.9) aggregate mode with that field
   as a dimension now also returns NULL-grouped output, not values.
5. `test_detail_relation_labels` — country_id column gets
   `value_labels` on the envelope (cache miss AND hit).
6. `test_detail_rejects_measures_and_grain` — measures non-empty →
   UserError; grain silently stripped (assert no DATE_TRUNC crash and
   raw dates come back).
7. `test_chart_roundtrip_detail` — config_json with mode+columns →
   `_to_query_request` → engine runs; extra_filters append.
8. HttpCase `test_export_xlsx_post` (remember §2 conventions: no
   `--no-http`, `--workers=0`) — POST as a BI user: 200, xlsx magic
   bytes `PK`, an audit row with mode/rows/columns; cap: set
   `biz_bi.export_row_cap=2`, assert capped flag + the notice row
   present (openpyxl is available? if not, parse with zipfile +
   sheet1 xml contains the notice string).
9. Full biz_bi suite: green EXCEPT exactly the six §3.9-listed
   pre-existing names (quote both result lines).

## 6. Deploy + report-back

- Deploy per conventions §2 (with the §5.130 concurrent-run check),
  `-u biz_bi`, db `vietuat`. Verbatim `odoo.tests.result` lines
  (scoped run + full run).
- Browser evidence pack →
  `docs/strategy/reports/records-table-phase1-evidence/`, real path:
  CMS → Analytics → hub → Create Report → advanced builder (or
  ANALYTICS → Analytics → open Explore via escape hatch) → Bookings
  dataset → Table → Records toggle → drag Client, Scheduled Date,
  Catchment Area, Total Price onto the table INCLUDING one drop after
  the last column and one header reorder → screenshot each state →
  sort by a header → truncation banner staged (lower the cap param
  temporarily, restore after) → Excel export clicked, the downloaded
  file's first rows shown (names not ids visible) → save chart → add
  to a dashboard → dashboard shows the records widget with CMS chrome.
  Console logs per screen; server-side: the export audit row by id;
  QA fixtures deleted + fresh-cursor verified (§5.34/§5.128).
- Report → `docs/strategy/reports/records-table-phase1-report.md`
  (committed): files, deviations, verbatim test lines, the §3.9 fix
  confirmation (aggregate-mode nulled-dimension before/after), export
  cap param name, any new gotcha (ledger §5.137+).
- Self-review before reporting: re-read every file against this spec;
  re-verify deployed behavior from the server log / live browser; do
  not trust your own earlier claims.

## Kickoff line

Implement the phase specified in docs/strategy/handovers/records-table-phase1.md.
