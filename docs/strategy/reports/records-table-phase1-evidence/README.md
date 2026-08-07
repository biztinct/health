# RT-1 browser evidence pack — Records table + Excel export

Driven on **https://care.biztinct.com** (vietuat) on 2026-08-07 between
07:44 and 09:30 UTC, in isolated browser contexts, as throwaway
**Operations-Manager-role BI-creator personas** created for this pass and
deleted afterwards (`qa-fixture-cleanup.txt`).

Persona shape (cloned from the live `om` account, uid 29, so the pass runs as
the population AH-1 actually granted): `base.group_user` +
`health_base.group_healthcare_*` ladder + **`biz_bi.group_bi_creator`**,
`access_role_id = 2` (Operations Manager), `catchment_province_id = 1`.
`has_group('biz_bi.group_bi_modeler')` and `…group_bi_admin` are both **False**
— i.e. no masking or RLS bypass.

Every screen was reached by **clicking**, from the login page:

```
/web/login → (log in) → /bizapp shell → sidebar ANALYTICS ▸ Analytics
   → Create Report → step 1: "Bookings & Service Orders"
   → "Open in advanced builder"  (the sanctioned escape hatch)
   → chart-type gallery ▸ Table → segmented control ▸ Records
   → drag Client / Catchment Area / Scheduled Date / Total Price onto the table
   → drag a header to reorder → click a header to sort
   → Excel → name the chart → Save → Add to Dashboard → the dashboard
```

No deep link anywhere. The only hand-typed URL is `/bizapp/action-1723`,
and only to re-enter a screen already reached by clicking, after a
service restart between builds.

---

## 1. The walk

| # | File | What it shows |
|---|------|---------------|
| 01 | `01-login.png` | the real entry point |
| 02 | `02-shell-sidebar.png` | the CMS shell; ANALYTICS ▸ Analytics is in the sidebar for this role |
| 03 | `03-analytics-hub.png` | the Analytics hub (unchanged by this phase — `biz_bi_cms` untouched) |
| 04 | `04-explore-bookings.png` | Explore, opened from the wizard's "Open in advanced builder", Bookings dataset preselected |
| 05 | `05-table-summary-toggle.png` | picking **Table** reveals the `Records | Summary` segmented control; Summary is the default, so nothing changes for existing users |
| 06 | `06-records-empty-state.png` | Records mode: the friendly full-width drop target, and the chart gallery collapsed to Table only (18 of 19 types disabled, title "Switch to Summary for charts") |
| 07 | `07-records-one-column-client.png` | after dragging **Client** from the field well onto the empty table — 1,271 record rows, one per booking |
| 08 | `08-drop-on-body-appends-after-last.png` | **Scheduled Date** dropped on the table BODY → appended **after the last column** (the literal ask) |
| 09 | `09-insertion-caret.png` | the insertion caret: a 2 px accent bar in the gap before "Total Price" while a field hovers the header row |
| 10 | `10-header-reorder.png` | a **header dragged to reorder** — "Catchment Area" moved from last to second |
| 11 | `11-sort-total-price-desc.png` | clicking the "Total Price" header cycles ▲ then ▼; rows re-sorted 160,000 first |
| 12 | `12-saved-and-add-to-dashboard.png` | "Chart saved." + the Add-to-Dashboard picker |
| 13 | `13-dashboard-records-widget.png` | the saved **Records** chart as a dashboard widget, full CMS chrome, `dashboard_action.js` unchanged |
| 14 | `14-dashboard-widget-overflow-row.png` | the widget scrolled to its foot: *"Showing the first 200 of 1,271 rows — open in Explore or export for the full set."* |
| 15 | `15-hub-recents-with-new-dashboard.png` | the hub picked the new dashboard up |
| 16 | `16-truncation-banner-staged.png` | the honest truncation banner (**staged**, see §3) |
| 17 | `17-summary-mode-aggregate.png` | Summary mode: the same Table chart aggregating (2 rows, 730,000 / 720,000) |
| 18 | `18-records-seeded-from-slots.png` | switching that chart to Records **seeds the columns from the slots** and shows 1,271 record rows; switching back restored the aggregate chart byte-for-byte |

Screens 01–05 were captured on the first deployed build; 06–18 on the
**shipped** build (every UI file byte-identical to the committed source —
`md5sum` compared, deployed vs repo). The two bugs found mid-pass
(header-reorder drop rejected; dashboard tile freeze) were fixed and the
affected screens re-driven from the login page on the fixed build.

### Drag realism

Screens 07, 08, 10 are **real HTML5 drags** performed by the CDP
`Input.dispatchDragEvent` path (chrome-devtools `drag`), i.e. the browser's
own drag machinery, not synthetic clicks. Only two things are dispatched by
hand, and both are noted where they appear:

* screen 09 — the caret is a *mid-drag* state and the drag helper is atomic,
  so a genuine `dragover` DragEvent (with a real `DataTransfer` carrying
  `bi/field`) is dispatched at a chosen `clientX` on the header row, the
  component's own handler runs, and the screenshot is of the resulting DOM;
* screen 13/14 and 18 — the four column drags are dispatched as a real
  `dragstart`/`dragover`/`drop` sequence for speed. The outcomes are
  identical to the CDP drags on 07/08/10.

---

## 2. Excel export

`records-export.xlsx` is the file the **Excel button** produced (the click is
in the server log — `POST /bi/export/xlsx … 200` at 09:18:53 — and in audit
row **1576**: `{"mode":"detail","rows":1271,"capped":false,"format":"xlsx",
"columns":4}`). The bytes were captured by replaying the identical POST from
the same authenticated session, because the headless browser context does not
persist downloads to disk.

`export-first-rows.txt` dumps both workbooks cell-by-cell with number formats.
The headline: **`Catchment Area` reads "TPHCM" / "Hà Nội", not `1` / `2`** —
the many2one ids the column actually stores. Dates are real Excel dates
(`yyyy-mm-dd`), money is a real number (`#,##0.00`), header row frozen,
autofilter over the used range.

The sheet name in that file is `RT1 QA- Booking Records -final-`, sanitised
from the chart name the user typed, `RT1 QA: Booking Records [final]` —
`xlsxwriter` **raises** on `[ ] : * ? / \` in a sheet name, so before the
sanitiser that chart name would have 500'd the export.

`records-export-capped.xlsx` is the same button with
`ir.config_parameter biz_bi.export_row_cap = 5`: 5 rows plus a bold final row
*"Showing first 5 of 1271 rows — refine filters for the full set."*, audit
`{"rows":5,"capped":true}`. **The POST body deliberately carried
`hard_cap: 999999` and `limit: 999999`; the server ignored both.**

---

## 3. Staged conditions (both reverted)

1. **Truncation banner** (screen 16). No dataset on this deployment reaches
   the 5,000-row preview clamp (the biggest is Bookings at 1,271), so
   `meta.truncated` cannot fire naturally. It was staged by temporarily
   editing the DEPLOYED `MAX_ROWS = 5000` → `3` and setting
   `biz_bi.export_row_cap = 5`, then restarting. The banner rendered from the
   real envelope: *"Showing 3 of 1,271 — refine filters, or export up to 5
   rows."* Both were reverted: `MAX_ROWS` is back to 5000 in the deployed file
   (grep-verified) and the config parameter row is deleted (0 rows).
   The handover asked for this to be staged by "lowering the cap param"; the
   export cap and the preview clamp turned out to be two different numbers, so
   the deviation is recorded in the report.
2. **Dashboard tile freeze** — diagnosed by SQL-editing the saved chart's
   `config_json.limit` (50 → 500 → 5000) and timing the render. The chart was
   deleted in cleanup.

---

## 4. Console

`console-log.txt` — zero errors, zero warnings, zero unhandled rejections on
every screen. The only entries are Chrome's own pre-existing a11y advisory
about Odoo core inputs lacking `id`/`name`.

## 5. Server-side rows and cleanup

`qa-fixture-cleanup.txt` — what each pass created, the raw scoped `DELETE`
that `bi.audit.log` forces (§5.128), and the fresh-cursor (psql) proof that
nothing is left.
