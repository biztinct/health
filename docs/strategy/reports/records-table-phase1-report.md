# Phase RT-1 report — biz_bi Records table + Excel export

Implements `docs/strategy/handovers/records-table-phase1.md`.
Deployed to **vietuat** (`-u biz_bi`), evidence pack in
`docs/strategy/reports/records-table-phase1-evidence/`.

---

## 1. What shipped

A Table chart in Explore now has a `Records | Summary` switch. In **Records**
mode the table itself is the drop target: drag any field onto it and it
becomes a column, one row per underlying record, honouring every filter, RLS
row rule, static filter and multi-company predicate that the aggregate path
honours. Columns reorder by dragging headers, remove with a hover ×, and sort
by clicking. Either mode exports to a real `.xlsx` — saved chart or not —
with a server-side row ceiling and an audit row.

Two security/honesty items came with it: the `mask_mode='null'` column rule
now empties a field used as a **dimension** as well as a measure (it did not
before — §3.9), and the export writes record **names** where the column
stores ids (it wrote raw ids before — §3.6).

### Files

**Changed**

| File | What changed |
|------|--------------|
| `addons/biz_bi/models/bi_query_engine.py` | `mode: 'detail'`; `_dimension_expr()` (nulled fields → `NULL::text` in both roles and both modes); `_count_detail_rows()` for the honest total; `run(request, hard_cap=None)` with `hard_cap` popped from the payload and folded into the cache key; `export_row_cap()`; `_json_safe_row` hardened for raw record columns; top-N disabled in detail mode |
| `addons/biz_bi/models/bi_chart.py` | `config_json.mode` + `slots.columns`; `_to_query_request` builds a detail request from the ordered column list (dedupe keep-first), aggregate path byte-identical (no `mode` key at all) |
| `addons/biz_bi/controllers/main.py` | new `POST /bi/export/xlsx` (`csrf=True`); the existing GET route switched to the post-label envelope and the shared writer; `_build_xlsx` / `_write_cell` / `_sheet_name`; freeze panes, autofilter, real Excel dates and numbers, the capped notice row, richer audit payload |
| `addons/biz_bi/static/src/components/explore/explore_action.js` | Records state (`tableMode`, `recordColumns`, `recordSort`), column add/move/remove/sort, gallery collapse, truncation getter, Excel download, config round-trip |
| `addons/biz_bi/static/src/components/explore/explore_templates.xml` | `biz_bi.RecordsTable`, `biz_bi.ExportButton`, the segmented control, the banner, the preview restructure, the DataTable overflow row |
| `addons/biz_bi/static/src/components/explore/data_table.js` | memoised formatting getter + optional `maxRows` render cap with an honest overflow row |
| `addons/biz_bi/static/src/components/dashboard/dashboard_templates.xml` | one attribute: `maxRows="200"` on the widget's `DataTable` |
| `addons/biz_bi/static/src/scss/biz_bi.scss` | `.bi-segmented`, `.bi-truncation`, `.bi-export-btn`, `.bi-ico-xlsx`, `.bi-records-*`, the caret, `.bi-table-overflow`, a `prefers-reduced-motion` block |
| `addons/biz_bi/i18n/vi_VN.po` | 134 → 157 entries (+23; `Records` and `Others` carry both the JS and the Python marker) |
| `addons/biz_bi/tests/__init__.py`, `addons/biz_bi/__manifest__.py` | register the new suite; version 19.0.1.3.0 → 19.0.1.4.0 |
| `docs/strategy/HANDOVER-CONVENTIONS.md` | ledger §5.137–§5.140 |

**New**

* `addons/biz_bi/static/src/components/explore/records_table.js` — the
  drag-native Records table (its own component, so the dashboard's DataTable
  path is untouched).
* `addons/biz_bi/tests/test_detail_mode.py` — 11 tests
  (`TestDetailMode` ×7, `TestExportXlsx` ×4, the latter an `HttpCase`).
* `docs/strategy/reports/records-table-phase1-evidence/` — the pack.

**Migration:** none. `mode` and `slots.columns` default off, `biz_bi.export_row_cap`
falls back to 20 000 when absent, and no column or index changed — an existing
`config_json` compiles to exactly the request it compiled to yesterday. Stated
per handover §3.10.

**Not touched:** `biz_bi_cms` (no wizard/hub change), `dashboard_action.js`
(zero lines — verified), any PWA asset (nothing PWA-facing, so no §3 version bump).

---

## 2. Test results — verbatim

**Scoped** (`--test-tags /biz_bi:TestDetailMode,/biz_bi:TestExportXlsx`),
`/tmp/rt1/scoped3.log`, `EXIT:0`:

```
2026-08-07 09:11:49,538 2425651 INFO vietuat odoo.tests.stats: biz_bi: 15 tests 4.23s 2394 queries 
2026-08-07 09:11:49,538 2425651 INFO vietuat odoo.tests.result: 0 failed, 0 error(s) of 11 tests when loading database 'vietuat' 
```

**Full biz_bi suite** (`--test-tags /biz_bi`), `/tmp/rt1/full3.log`, `EXIT:1`:

```
2026-08-07 09:12:38,361 2425750 INFO vietuat odoo.tests.stats: biz_bi: 103 tests 15.53s 8455 queries 
2026-08-07 09:12:38,361 2425750 ERROR vietuat odoo.tests.result: 5 failed, 1 error(s) of 79 tests when loading database 'vietuat' 
```

The six are **exactly** the six documented in
`analytics-hub-phase3-report.md:207-212`, no more and no others:
`TestRls.test_column_mask_null` (error), `TestPipeline.test_dataset_reads_clean_view`,
`TestQueryEngine.test_compare_request_runs`, `TestRls.test_rls_users_never_share_cache`,
`TestRls.test_row_rule_filters_rows`, `TestSnapshot.test_snapshot_xlsx_builds`.

The HttpCases really ran (§2's own check): `grep -ac "Starting TestExportXlsx"`
→ **4**, `grep -ac "ERROR: setUpClass"` → **0**. §5.130's concurrent-run check
(`pgrep -c -f '^python3 /odoo/odoo-server/odoo-bin'` → 0) was taken immediately
before every `service stop`.

After the final restart: `ss -lntp | grep -c :8069` → **1**,
`curl localhost:8069/web/login` → **HTTP:200**.

**A refinement to §5.133's diagnosis, worth recording.** The AH-3 report
attributes all six to the jsonb `res_country.name` and the 77 latitude-bearing
partners. Reading the tracebacks on this run, three of them (the RLS ones) have
a second, simpler cause that also explains the `IndexError`: vietuat's live
`res.partner` record rules pin a plain internal user to their **own** partner
("User: Own Partner Record"), so the restricted user in those tests sees zero
of `common.py`'s three fixture rows —
`IndexError: list index out of range` on `result['rows'][0][0]`, and
`None != 30.0`. It still fails **closed**. It is also why this phase's own
tests install a scoped, transaction-local permissive partner rule
(`_allow_all_partners`) before asserting anything about RLS: without it the
assertions would be vacuously true. The pre-existing suite was left untouched.

---

## 3. The §3.9 masking fix — before / after, measured

Full transcript in `records-table-phase1-evidence/masking-fix-before-after.txt`.
Both runs are the *same* probe script through `odoo-bin shell` on vietuat,
against a throwaway dataset, ending in `cr.rollback()`.

A non-admin BI viewer with a `mask_mode='null'` column rule on the **Name**
field, asking for Name as a **dimension**:

| | BEFORE (HEAD) | AFTER (shipped) |
|---|---|---|
| aggregate rows | `[["MASKPROBE Alpha",10.0],["MASKPROBE Beta",20.0],["MASKPROBE Gamma",30.0],["MaskProbe Reader",null]]` | `[[null, 60.0]]` |
| `columns_meta[0]` | no `nulled` key | `"nulled": true` |
| detail rows | *mode silently ignored, answered as aggregate, values in full* | `[[null,10.0],[null,20.0],[null,30.0],[null,null]]` |
| detail meta | — | `"mode":"detail","total_count":4,"export_cap":20000` |

Every masked value was leaving the database before, in the role the feature
was about to make the primary one. Now the column is a typed `NULL::text`
constant in the SELECT **and** in the GROUP BY, so the aggregate collapses to
one NULL-keyed group — the values are gone *and* so is their cardinality —
while the untouched measure still sums to 60.0. `GROUP BY NULL::text` was
verified in psql before the code was written. Pinned by
`test_detail_nulls_masked_dimension`, which asserts both halves.

---

## 4. The export path — the two things asked about

**Cells carry names, not ids.** Both routes build the workbook from the
envelope *after* `_attach_relation_labels`, and `_write_cell` looks the raw
value up in `column['value_labels'] / ['selection_labels']` before any other
branch. In `records-export.xlsx` (the file the button produced, audit row
1576) the `Catchment Area` column — a many2one storing ids 1 and 2 — reads
`TPHCM` / `Hà Nội`. Dates are real Excel dates (`yyyy-mm-dd`), money a real
number (`#,##0.00`), header frozen, autofilter over the used range. Asserted
in `test_export_xlsx_post` both ways: the label must be present **and**
`str(country.id)` must be absent from every string cell. The saved-chart GET
route is covered separately by
`test_export_xlsx_get_saved_chart_uses_labels`.

**`hard_cap` can never come from the client.** It is a Python keyword argument
on `run()`; the first thing `run()` does is `request = dict(request); request.pop('hard_cap', None)`,
and the POST controller pops it again before it ever gets there. The ceiling
is read server-side from `ir.config_parameter` **`biz_bi.export_row_cap`**
(default 20 000). Proven three ways: `test_export_row_cap_is_server_side_only`
POSTs `hard_cap: 999999` **and** `limit: 999999` with the parameter at `2` and
asserts the audit row says `rows: 2, capped: true`; the same shape was driven
in the browser with the parameter at `5` (`records-export-capped.xlsx` — five
rows and a bold "Showing first 5 of 1271 rows" notice); and the clamp is part
of the cache key, so a client cannot prime the cache at one ceiling and have
the export serve it back at another.

---

## 5. Deviations from the handover, and why

1. **`hard_cap` is folded into the cache key** (handover §4.1 said "cache:
   unchanged path"). Without it a client could `POST /bi/query` with
   `limit: 20000`, get a 5 000-row envelope cached under that key, and then
   have the export return those 5 000 rows as if they were 20 000. One line,
   only active when `hard_cap` is passed, so ordinary preview keys are
   byte-identical to before.
2. **The saved-chart GET export now runs at the export cap too**, not at the
   chart's saved `limit` (§4.3 only specified this for the POST route). An
   export that silently hands you 500 of 3 000 rows is precisely the silent
   cap this phase exists to remove; top-N charts are unaffected because
   `spec['limit'] = min(top_n.n, spec['limit'])` still applies.
3. **The Explore Records table is its own component** (`records_table.js`)
   rather than an interactive mode of `DataTable`. §4.4 does not prescribe the
   file layout, and this keeps the dashboard/Summary renderer literally
   untouched by the drag UX — which is what made "zero changes to
   `dashboard_action.js`" true.
4. **`DataTable` gained a `maxRows` render cap and the dashboard template
   passes 200.** §2 said dashboard widgets "keep working untouched … expected:
   zero" changes; they did *not* keep working (see §6), and the smallest fix
   that restores them is one attribute in `dashboard_templates.xml`.
   `dashboard_action.js` is still untouched, and the cap is never silent — the
   widget's last row states the overflow against `meta.total_count`.
5. **The truncation banner was staged by lowering `MAX_ROWS`, not the cap
   param** (§6 asked for the latter). They are different numbers: the export
   cap does not affect `meta.truncated`, which compares `total_count` against
   the preview clamp. No dataset here reaches 5 000 rows, so the deployed
   constant was temporarily set to 3 and restored (grep-verified).
6. **A sheet-name sanitiser** was added at self-review (not in the handover) —
   see §6, it is a 500 on user input.
7. **`_json_safe_row` hardened.** Detail mode selects raw columns, so a
   `bytea`/`uuid`/`interval` from a `sql_view` source can now reach JSON
   serialisation; bytes become `None`, anything else non-scalar becomes `str`.
8. **`test_sheet_name_is_sanitised`** is a 12th test not in the handover's
   list of 8 (the handover's 8 are all present).

---

## 6. Bugs found during the phase — all fixed, all ledgered

1. **The export ceiling was 1, not 20 000** (§5.137). `int(get_param(key))`
   where the key does not exist: `get_param` returns `False`, `int(False)` is
   `0`, no exception, and `max(1, 0)` capped every export at a single row. The
   `try/except (TypeError, ValueError)` around it looked exhaustive and was
   not. Caught only because a test asserted an exact row count.
2. **Header reorder was silently rejected** (§5.138). `effectAllowed="move"`
   on the header drag versus `dropEffect="copy"` in the shared `dragover`
   handler — the browser declines such a drop with no event and no message.
   Caught by driving the real drag in the browser; a handler unit test would
   have passed, because the handler is never called.
3. **A saved Records widget froze the dashboard** (§5.139). Same component,
   same data: 50 rows → 1.8 s, 500 rows → 133 s, 1 271 rows → the page never
   recovered. It is the GridStack tile, not the table (the identical component
   renders 1 271 rows instantly full-width in Explore). Fixed with a memoised
   formatting getter plus the `maxRows=200` render cap and an honest overflow
   row: the same dashboard now renders in **982 ms**.
4. **A chart named `Q1: Revenue [VN]` would 500 the export** (§5.140).
   `xlsxwriter.add_worksheet()` raises on `[ ] : * ? / \`. Sanitised and
   unit-tested; the browser pack's final export was deliberately titled
   `RT1 QA: Booking Records [final]` and produced sheet
   `RT1 QA- Booking Records -final-`.

---

## 7. i18n

`i18n/vi_VN.po`, 134 → **157** entries. Loader-verified on the server per
§5.134 (`get_web_translations(...)["messages"]` indexed directly, never
`len()` on the `ReadonlyDict`) — full output in
`records-table-phase1-evidence/i18n-loader-check.txt`:

```
WEB messages: 151  PY messages: 8
MISSING: []
```

All 17 new JavaScript strings and all 8 Python strings resolve to Vietnamese.
`Records` and `Others` are single entries carrying **both** `#. odoo-javascript`
and `#. odoo-python` markers with both occurrences, which is how one msgid
serves both catalogues without a duplicate entry. Shape checked with polib:
157/157 have `#. module: biz_bi`, a code marker and a `#:` occurrence; zero
duplicates, zero untranslated.

Note: the Explore QWeb templates are `static/src` component templates, not
`ir.ui.view` records, so their literal text is not translatable at all — that
is why every new user-visible string is a `_t()` in JS bound through
`t-esc`, not inline template text. (The pre-existing "Save" / "Add to
Dashboard" / slot labels are still inline English; out of scope here, worth a
follow-up ticket.)

---

## 8. Browser evidence

`docs/strategy/reports/records-table-phase1-evidence/` — README with the
click-by-click path, 18 screenshots, both exported workbooks plus a
cell-by-cell dump, the console log per screen (zero errors), the i18n loader
output, the masking before/after, the verbatim test lines and the QA-fixture
cleanup with fresh-cursor proof.

Driven as a throwaway Operations-Manager **BI-creator** persona cloned from
the live `om` account (`group_bi_modeler` and `group_bi_admin` both False),
from `/web/login` through the CMS sidebar, the hub and the wizard's
"Open in advanced builder" — no deep links. Three personas were used, one per
re-drive after a fix; all three and everything they created are deleted, and
the deletion is verified from psql, a different process from the shell that
did it (§5.34 / §5.128).

---

## 9. Deferred / known limitations

* **`MAX_LABEL_LOOKUP = 2000`.** A many2one column with more than 2 000
  distinct values in the result set gets no `value_labels`, so a large export
  of such a column would fall back to raw ids. Pre-existing privacy/perf
  control, untouched here — but it is the one remaining path by which an
  export can show ids. Worth an explicit decision in RT-2 (e.g. resolve labels
  in batches for exports only, still per-reader).
* **A saved Records widget still fetches its full `limit` (5 000) over the
  wire** even though the tile renders 200. Cheap in JSON terms at today's
  volumes; if dashboards get several Records widgets, give the widget request
  its own smaller limit and keep `total_count` for the overflow row.
* **Datetime columns export in UTC** (the value the engine returns) while the
  on-screen table renders them through the browser's locale. Pure `date`
  columns are identical in both. Not addressed; flag if users compare.
* **No virtualization, no drill-through, no CSV, no scheduled exports** —
  all explicit non-goals.
* **RT-2** (the "Just show me the records" look in the guided wizard) is
  untouched, as instructed.

---

## 10. New ledger entries

Appended to `docs/strategy/HANDOVER-CONVENTIONS.md`:

* **§5.137** — `int(get_param(...))` is a silent 0 for an absent key
  (`get_param` defaults to `False`); the read-side twin of §5.36.
* **§5.138** — an HTML5 drop is rejected outright when `dropEffect` and
  `effectAllowed` disagree, with no event and no message; pick the effect from
  `dataTransfer.types` in `dragover`, and verify drag UIs with the real CDP
  drag helper.
* **§5.139** — a plain table in a GridStack tile is super-linear in row count
  (50 → 1.8 s, 500 → 133 s, 1 271 → never); memoise the formatting getter and
  bound the rendered node count, honestly.
* **§5.140** — `xlsxwriter.add_worksheet()` raises on `[ ] : * ? / \`, and a
  sheet name is usually user input.
