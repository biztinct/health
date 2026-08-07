# Phase RT-2 report — "Just show me the records" in the guided wizard

Implements `docs/strategy/handovers/records-table-phase2.md`.
Deployed to **vietuat** (`-u biz_bi_cms`), branch `19.0`.
Module: **`addons/biz_bi_cms`** `19.0.1.1.0` → **`19.0.1.2.0`**.
Evidence pack: `docs/strategy/reports/records-table-phase2-evidence/`.

---

## 1. What shipped

Step 2 of the hub's Create Report wizard now opens with a **`Chart | Records
list`** segmented control. `Chart` is the default and is the pre-RT-2 screen
plus that one control — zero regression. `Records list` swaps the
measure / break-down-by / split-by pickers and the chart gallery for:

* an ordered **"Your columns"** chip row (position number, ‹ › to reorder,
  × to remove), and
* an **"Available columns"** checklist grouped by the dataset's own folders,
  each folder collapsible, nothing pre-ticked.

The **Date range** chip row is untouched and shared by both paths, because
the same filter applies to a records list. Step 3 then shows an honest
banner, an **Excel** button and a 100-row preview of a detail-mode query,
and Save writes RT-1's records shape — `chart_type: 'table'`,
`mode: 'detail'`, an ordered `slots.columns`, `sort: []`, `limit: 5000` — so
a wizard-made records report and an Explore-made one are the same
`bi.chart` row, and the dashboard renders it through RT-1's unchanged path
at its 200-row cap.

`biz_bi` was **not** touched — verified with `git status` before the commit
(empty for `addons/biz_bi`). No PWA asset, app shell or shell-injecting
module was touched either, so conventions §3 does not apply.

### Files

| File | Δ | What changed |
|---|---|---|
| `static/src/components/wizard/report_wizard.js` | +311 | `buildMode` / `recordColumns` / `closedFolders` / `exporting` state; `isRecords`, `modeEntries`, `setBuildMode`; `columnFolders`, `isFolderOpen`/`toggleFolder`, `isColumnPicked`/`toggleColumn`/`removeColumn`/`moveColumn`; records branches in `afterChange`, `defaultName`, `canPreview`, `buildRequest`, `buildConfigJson`, `rendererKind`, `saveReport`; `previewMaxRows`, `recordsTruncation`, `exportTitle`, `exportExcel`; six new inline SVG icons |
| `static/src/components/wizard/report_wizard.xml` | +130/−13 | the segmented control, the picked-columns row, the folder checklist, `t-if="!isRecords"` on the three pickers / the AI box / the divider / the gallery, the step-3 preview bar (banner + Excel), `maxRows="previewMaxRows"` on `DataTable` |
| `static/src/components/wizard/report_wizard.scss` | +224 | `.bi-wizard-modes/-mode`, `.bi-wizard-records`, `.bi-wizard-picked/-pickchip*`, `.bi-wizard-folders/-folder*/-checklist/-checkrow`, `.bi-wizard-previewbar/-banner/-export`; the new controls added to the shared focus-ring list; a `prefers-reduced-motion` line for the folder caret |
| `tests/test_wizard_records.py` | **new**, 275 | `TestWizardRecords`, 3 methods, `post_install` |
| `tests/test_wizard_flow.py` | +15/−5 | `test_06`'s hard-coded version literal now reads the manifest (deviation D1) |
| `tests/__init__.py` | +1 | registers the new suite |
| `__manifest__.py` | +12/−2 | version `19.0.1.2.0`, a description paragraph for the Records path |
| `i18n/vi.po` | 85 → **104** entries | the 19 new user-visible strings |
| `docs/strategy/HANDOVER-CONVENTIONS.md` | +3 entries | §5.141–§5.143 |

**Migration:** none. `buildMode` defaults to `"chart"`, every existing
`bi.chart` compiles to exactly the request it compiled to yesterday, and no
column, index or data record changed.

---

## 2. Test results — verbatim

Final deploy, `/tmp/rt2/deploy4.log`, `EXIT:0`:

```
2026-08-07 10:23:56,615 2431905 INFO vietuat odoo.tests.stats: biz_bi_cms: 29 tests 7.56s 5581 queries 
2026-08-07 10:23:56,615 2431905 INFO vietuat odoo.tests.result: 0 failed, 0 error(s) of 21 tests when loading database 'vietuat' 
```

**21** methods executed, up from AH-3's 18; the three new ones are
`TestWizardRecords.test_records_config_shape`,
`test_records_save_flow` and `test_records_column_order_preserved`, and no
pre-existing method was dropped. The full list, the two earlier runs and the
one red run that preceded them are in
`records-table-phase2-evidence/test-results.txt`.
`grep -ac "FAIL:\|ERROR:\|CRITICAL"` over the final log: **0**.
§5.130's concurrent-run check read 0 immediately after every `service stop`.

After the final restart: `ss -lntp | grep -c :8069` → **1**,
`curl localhost:8069/web/login` → **HTTP:200** (re-confirmed after the QA
cleanup). Deployed files byte-compared against the repo afterwards, both
directions: identical.

Mapping to handover §5: 1 → `test_records_config_shape`,
2 → `test_records_save_flow`, 3 → `test_records_column_order_preserved`,
4 → the 18 pre-existing methods, all still green.

`test_records_config_shape` also pins the two things the handover's §3 says
must hold and a test is the only cheap way to keep holding: that a records
`config_json` compiles to `mode: 'detail'` with **no** `grain` key on any
dimension, and that a dashboard global filter still appends on that path.

---

## 3. Deviations from the handover, with reasoning

**D1 — `tests/test_wizard_flow.py::test_06` was edited (in-module, forced).**
This is the §5.62 class, the same one AH-2's D3 hit. `test_06` asserted
`module.latest_version == '19.0.1.1.0'`, a literal that goes red on the next
phase that bumps the manifest, for no defect. It now reads the version out of
`__manifest__.py` and asserts the DATABASE is at the version this checkout
DECLARES — which is the condition the assertion was actually about (it is
what makes a migration directory named for that version run). Everything else
in `test_06` — the migration directory, the role-gate convergence, the leaf's
`role_ids` — is untouched. The alternative was not bumping the version at all,
which would have made an upgrade of a materially changed module invisible.

**D2 — the truncation banner and `DataTable`'s own overflow row both appear,
and I kept both.** §4.2 specifies a banner whose condition (`meta.truncated`
OR `total_count > rendered`) turns out to be *exactly* the condition under
which RT-1's `DataTable` already writes "Showing the first 100 of 1,229 rows
…" as its last row — the handover predates that row being in the renderer.
Removing the duplication would mean either dropping the banner the spec asks
for or editing `biz_bi`, which §2 forbids. Keeping both is also the better
answer: the table's statement is at the **bottom of a 100-row scroll area**,
and the banner is above the fold next to the Excel button, i.e. where the
user decides. Screens 11 and 16 show both.

**D3 — three constants, not one.** §4.2 gives `maxRows: 100` and
`limit: 1000` for the preview and `limit: 5000` for the save; I named them
`RECORDS_PREVIEW_MAX_ROWS`, `RECORDS_PREVIEW_LIMIT` and
`RECORDS_SAVED_LIMIT` with a comment explaining why they are three different
numbers, because "1000" and "5000" fifty lines apart is how the next reader
makes them agree by mistake. Values exactly as specified.

**D4 — the export sends the PREVIEW request (limit 1000), not a widened
one.** §4.2 says "same POST/blob pattern as Explore, title = report name" and
does not say what limit to send. The POST route overwrites `payload['limit']`
with the server-side `export_row_cap` before it runs anything
(`biz_bi/controllers/main.py:63`), so sending the preview request is both
correct and the smallest thing that can be sent. Proven, not assumed: the
workbook has **1,229** data rows against a preview that fetched 1,000
(`export-first-rows.txt`, audit rows 1641/1642/1673 all `rows: 1229`).

**D5 — reorder is ‹ › (a button pair), not drag.** §2 allows "simple ↑/↓ or
chip-drag if trivial"; a second HTML5 drag surface is not trivial (§5.138 is
the reason), and the chips flow left→right, so left/right chevrons match the
gesture and the tooltip. Handover §4.1's "↑/↓" is satisfied in substance:
one click moves a column one place, the ends are disabled rather than
wrapping.

**D6 — the checklist has no per-folder search, and folders default OPEN.**
§2 forbids "column search beyond the folder grouping", which I read as
forbidding a search box; the folders therefore have to be browsable, so they
open by default and `closedFolders` records the exceptions.

**D7 — a mode switch clears `chartId` but keeps the pickers.** Not specified.
Clearing `chartId` is required: a saved chart is one shape or the other, and
reusing the id would rewrite a chart into a shape its dashboard tile is not
expecting. Keeping the pickers means Records → Chart → Records does not lose
the columns somebody ticked.

**D8 — a pixel pass after the first evidence drive.** Two things the first
pack showed: the reorder chevrons pointed up/down against left/right
tooltips, and the folder cards were a CSS `grid` so a one-field folder beside
the twenty-field `Dates` folder left a ~250 px hole. Fixed (chevrons; a
multi-column flow), redeployed, and screens 01–16 were **all re-driven from
`/web/login`** on the fixed build.

Everything else follows §4 literally: the default path, the ≥1-column gate,
the shared date-range row, the hidden gallery, the unchanged step
indicator / back / advanced-escape behaviour (the escape still passes only
`dataset_id`, so Explore opens in its default Summary mode — noted, as §4.1
asks), `DataTable` with `maxRows: 100` over a `limit: 1000` detail query, the
exact banner copy, the `"<Dataset> records"` default name, the unchanged
dashboard-target UI, the verbatim RT-1 config shape, and every binding
non-goal in §2 (no AI on the records path, no drag-reorder, no per-column
sort, no pivot/summary options, no `biz_bi` edit, RT-1's deferred items still
deferred).

---

## 4. Bugs and traps found during the phase

1. **The envelope's column key is `label`, not `name`** (now §5.143). The
   first deploy went red on one test with a bare `KeyError: 'name'`.
   `bi.field.name` is renamed to `label` in `columns_meta`. The test now
   asserts `field_id` order for identity and `label` order for display.
2. **A cleanup script's own log is not evidence** (now §5.142).
   `DELETE FROM bi_query_cache WHERE create_uid = …` raised
   `UndefinedColumn` — the model sets `_log_access = False` — which aborted
   the whole transaction and rolled back the three `unlink()`s that had
   already printed as done. Only §5.34's fresh-cursor check catches that.
3. **A `lang` write is not picked up by a fresh login** (now §5.141), and
   whether it is picked up is a coin toss: the identical shell write + logout
   + login produced Vietnamese for the first QA persona and English for the
   second twenty minutes later, because the second had already been cached by
   the worker that served the login. A service restart fixed it. This is the
   one that could silently put an English screenshot in a "both languages"
   evidence pack.
4. **§5.122 fired once** — `service odoo-server restart` reported success
   with no process and no listener; the documented
   stop → `rm -f /var/run/odoo-server.pid` → start brought it back. Recorded
   in `console-log.txt` rather than attributed to this phase's code.

---

## 5. i18n

`i18n/vi.po`, 85 → **104** entries (+19). Loader-verified on the server per
§5.134 (`get_web_translations(...)["messages"]` indexed directly, never
`len()` on the `ReadonlyDict`) — full output in
`records-table-phase2-evidence/i18n-loader-check.txt`:

```
WEB messages: 102  PY messages: 0
MISSING: []
```

All 19 new strings resolve to Vietnamese. `msgfmt --check` passes. Proven in
the browser too (screens 15/16), including the interpolated banner and its
Vietnamese thousands separator: *"Đang hiển thị 100 bản ghi đầu tiên trong
tổng số 1.271 — báo cáo đã lưu và tệp Excel xuất ra bao gồm nhiều hơn."*

`Excel` is translated to `Excel` on purpose — a product name still needs an
entry to exist, or the loader reports it missing.

Not translated, and correctly so: the folder names and some field labels are
`bi.field` **data** on this deployment, not code strings.

---

## 6. Browser evidence

`docs/strategy/reports/records-table-phase2-evidence/` — README with the
click-by-click path, 16 screenshots, the exported workbook plus a
cell-by-cell dump, the console log, the i18n loader output, the created rows
by id with the verbatim `config_json`, the verbatim test lines, and the
QA-fixture cleanup with fresh-cursor proof.

Driven as throwaway Operations-Manager **BI-creator** personas cloned from
the live `om` account (`group_bi_modeler` and `group_bi_admin` both False),
from `/web/login` through the CMS sidebar every time. No deep link.

Three results worth pulling out of the pack:

* **Lookup columns render names, everywhere.** `Client`, `Catchment Area`
  and `Status` are ids in the database and read `An Xu` / `Hà Nội` /
  `Completed` in the preview, in the dashboard tile and in the workbook. No
  string cell in the 1,230-row sheet is `1` or `2`.
* **The banner needed no staging.** RT-1 had to lower a deployed constant;
  here the render cap (100) is below every dataset, and the vi_VN drive with
  no date filter also produced the genuine engine truncation
  (`meta.truncated`, 1,000 fetched of 1,271).
* **The wizard is deterministic across builds.** The two charts it saved, on
  two different builds, have character-for-character identical
  `config_json`.

QA fixtures: two personas, two charts, one dashboard, two widgets, 15 audit
rows and 5 device logs — all deleted, the audit rows through the raw scoped
`DELETE` §5.128 forces, and the deletion verified from psql, a different
process from the shell that did it.

---

## 7. Deferred / not done

* **RT-1's three deferred items stay deferred**, as §2 requires:
  `MAX_LABEL_LOOKUP = 2000` (a >2,000-distinct-value many2one column still
  exports raw ids), datetime columns export in UTC, and a saved records
  widget still fetches its full `limit` over the wire while rendering 200.
* **The advanced escape opens Explore in Summary mode.** §4.1 permits this
  and asks for it to be noted: the hatch passes `dataset_id` only, so a
  half-built records list is not carried into Explore's Records mode. Making
  it lossless needs either a new Explore action param or a chart saved first
  — a `biz_bi` decision.
* **No records path in the AI box**, by §2. `nlq_chart` is chart-shaped.
* **No per-column sort in the wizard.** A records report saves with
  `sort: []`; Explore is where you sort one.
* **The duplicated truncation statement** (D2) is a cosmetic debt that only
  a `biz_bi` change can pay off cleanly — give `DataTable` a
  `suppressOverflowRow` prop, or move the row into a slot the host fills.

---

## 8. New ledger entries

Appended to `docs/strategy/HANDOVER-CONVENTIONS.md` in this same commit
(§5.108: a gotcha that lives only in a phase report does not exist for the
next phase):

* **§5.141** — a `res.users.lang` written from a separate `odoo-bin shell` is
  not honoured by a fresh LOGIN in the running workers, and whether it is
  honoured is a coin toss (it depends on whether that worker had already
  cached the user). Restart, and assert the language in the page before
  screenshotting.
* **§5.142** — not every Odoo table has `create_uid`/`write_uid`
  (`_log_access = False`), and a raw `DELETE` against one that does not will
  roll back the ORM `unlink()`s your cleanup script has already printed as
  done. Check `information_schema.columns`; put the raw SQL first.
* **§5.143** — a `bi.query.engine` envelope names its columns `label`, not
  `name`; `column['name']` is a bare `KeyError`.

---

## 9. Commit

Branch `19.0`, path-scoped to `addons/biz_bi_cms/`,
`docs/strategy/HANDOVER-CONVENTIONS.md` and
`docs/strategy/reports/records-table-phase2*` — the working tree carried
unrelated unstaged changes from another session throughout, and none of them
are in this commit.
