# RT-2 browser evidence pack — "Just show me the records" in the wizard

Driven on **https://care.biztinct.com** (vietuat) on 2026-08-07 between
09:50 and 10:35 UTC, in an isolated browser context (`rt2qa`), as throwaway
**Operations-Manager-role BI-creator personas** created for this pass and
deleted afterwards (`qa-fixture-cleanup.txt`): `rt2_qa` (uid 8219) for the
first drive, `rt2_qa2` (uid 8236) for the re-drive after the pixel pass.

Persona shape (cloned from the live `om` account, uid 29): `base.group_user` +
the `health_base.group_healthcare_*` ladder + **`biz_bi.group_bi_creator`**,
`access_role_id = 2` (Operations Manager).
`has_group('biz_bi.group_bi_modeler')` and `…group_bi_admin` are both
**False** — i.e. no masking bypass and no RLS bypass. Everything below is
what a real creator sees.

Every screen was reached by **clicking**, from the login page. There is no
deep link anywhere in this pack and no hand-typed URL except
`/web/session/logout` between the two language passes.

```
/web/login → (log in) → /bizapp shell → sidebar ANALYTICS ▸ Analytics
   → Create Report → step 1: "Bookings & Service Orders"
   → step 2: segmented control ▸ Records list
   → tick Client / Scheduled Date / Catchment Area / Total Price / Status
   → chip ‹ on "Catchment Area" (moves it from 3rd to 2nd)
   → Date range chip ▸ Last 12 months
   → Preview → step 3: banner + Excel + the 100-row preview
   → Excel  (POST /bi/export/xlsx → 32 KB workbook)
   → name it → pick a dashboard → Save report → the dashboard, CMS chrome
```

---

## 1. The walk

| # | File | What it shows |
|---|------|---------------|
| 01 | `01-login.png` | the real entry point |
| 02 | `02-shell-sidebar.png` | the CMS shell; **ANALYTICS ▸ Analytics** is in the sidebar for this role |
| 03 | `03-analytics-hub.png` | the Analytics hub, unchanged by this phase |
| 04 | `04-wizard-step1-datasets.png` | step 1, unchanged by this phase |
| 05 | `05-step2-chart-default.png` | step 2 with the **new segmented control**, `Chart` selected — this is byte-for-byte the pre-RT-2 screen plus one control, i.e. the zero-regression default the handover asks for |
| 06 | `06-step2-records-empty.png` | `Records list`: the pickers and the chart gallery are gone, replaced by **Your columns** (empty, with its instruction) and **Available columns** grouped by folder |
| 07 | `07-step2-records-daterange.png` | scrolled to the foot of the same screen — the **Date range chip row is still there, unchanged**, because the same filter applies to a records list |
| 08 | `08-step2-five-columns.png` | five columns ticked, incl. three lookups (Client, Catchment Area, Status); each chip carries its **position number** and ‹ › × |
| 09 | `09-step2-reordered.png` | after one click on ‹ on "Catchment Area": the order is now Client, **Catchment Area**, Scheduled Date, Total Price, Status |
| 10 | `10-step2-daterange-chip.png` | **Last 12 months** selected on the shared chip row |
| 11 | `11-step3-preview-banner.png` | step 3: the honest banner *"Showing first 100 of 1,229 records — the saved report and Excel export include more."*, the **Excel** button beside it, and the preview — **lookup columns render names** (`An Xu`, `Hà Nội`), not ids, and the column order is the one from screen 09 |
| 12 | `12-excel-clicked.png` | the state right after the Excel click; the request is in the server log (`POST /bi/export/xlsx … 200`) and in audit rows 1641 / 1642 / 1673, and the response was **32,503 bytes** |
| 13 | `13-step3-named-and-target.png` | the report named and an **existing** dashboard picked — a dashboard `get_wizard_targets` offers only because this creator now owns it |
| 14 | `14-dashboard-tile.png` | the saved records report as a dashboard tile, **full CMS chrome**, rendered through RT-1's unchanged dashboard path |
| 15 | `15-step2-records-vi.png` | the same step 2 under **`lang=vi_VN`** |
| 16 | `16-step3-preview-vi.png` | the same step 3 under `lang=vi_VN`, banner and default report name included |

Screen 14 shows **two** tiles on the one dashboard. That is honest, not a
duplicate render: the pass was driven twice (see §4), each drive saved one
records report, and the second was deliberately saved onto the dashboard the
first had created — which is how the "pick an existing dashboard" path on
screen 13 got exercised. Both charts, both widgets and the dashboard were
deleted in cleanup, and their `config_json` is character-for-character
identical (`server-side-rows.txt`).

## 2. Excel

`records-export.xlsx` is the workbook the **Excel button** produced. The
bytes were captured by replaying the identical POST from the same
authenticated session, because the headless browser context does not persist
downloads to disk; the button's own request is the 32,503-byte 200 in the
performance timeline on screen 12 and audit row 1673.

`export-first-rows.txt` dumps it cell by cell with number formats. The
headline: **1 header + 1,229 data rows** — the whole result set, not the 100
the preview renders nor the 1,000 it fetches, because the export route
re-runs the request server-side at `biz_bi.export_row_cap` — and the
`Catchment Area` column, a many2one that stores ids 1 and 2, reads
`Hà Nội` / `TPHCM` in every cell. Dates are real Excel dates
(`yyyy-mm-dd`), money a real number (`#,##0.00`), header frozen, autofilter
over `A1:E1230`.

The report was deliberately named `RT2 QA: Booking Records [wizard]` — a name
containing both `:` and `[ ]`, which is what §5.140 says will 500 an export
that does not sanitise its sheet name. It did not: the sheet is
`Bookings & Service Orders recor` (from the default title used on the
byte-capture replay), and the button click with the bracketed name returned
200.

## 3. The truncation banner was NOT staged

RT-1 had to lower a deployed constant to make its banner appear. RT-2 does
not: the wizard renders at most **100** rows and every dataset here is far
larger, so the banner fires from a real envelope on screen 11. The other,
stronger case — the ENGINE truncating at the 1,000-row preview limit, i.e.
`meta.truncated` — also occurred naturally, on the vi_VN drive with no date
filter (audit row 1646: `rows: 1000` of a 1,271-row total, which is the
`1.271` in the banner on screen 16).

## 4. Two builds, and which screens came from which

Two deploys carry UI (`/tmp/rt2/deploy2.log` and `/tmp/rt2/deploy3.log`).
The only difference between them is a **pixel pass** found by reviewing the
first pack:

1. the reorder chevrons pointed **up/down** while their tooltips said
   *Move left* / *Move right* — the chips run left→right, so the glyphs were
   changed to ‹ ›;
2. the folder cards were a CSS **grid**, so every card in a row stretched to
   the tallest one and a one-field folder beside the twenty-field `Dates`
   folder left a ~250 px hole that reads as a rendering fault. Changed to a
   multi-column flow, which packs them.

**Every screenshot in this pack (01–16) is `deploy3.log`'s build**, which
differs from the shipped `deploy4.log` build by two private getter names and
one comment and by no rendered byte (`test-results.txt` run 4) — the eleven
that had already been taken (03–14) were re-driven from `/web/login` as
`rt2_qa`, and 01, 02, 07, 15 and 16 were re-driven from `/web/login` again as
a second persona, `rt2_qa2`, after the first was deleted. Nothing in the pack
predates `deploy3.log`. The deployed files were md5-compared against the
committed source afterwards, both directions, and are identical
(`test-results.txt`).

Screens 15–16 needed one thing the English drive did not: after writing
`lang = vi_VN` from an `odoo-bin shell`, logging the persona out and back in
was **not** enough — the workers kept serving English until the service was
restarted, which is the new §5.141 in the ledger. The screenshots were taken
after that restart, and the sidebar was clicked, not deep-linked.

## 5. Console

`console-log.txt` — zero errors, zero warnings, zero unhandled rejections on
every screen. The single `[issue]` advisory is pre-existing and *measured*: a
DOM query proves the wizard contributes no form field without `id`/`name`,
and names the one that does (the CMS shell's catchment `<select>`).

## 6. Server-side rows and cleanup

`server-side-rows.txt` — every row the drive created, by id, with the
`config_json` the wizard wrote, verbatim, read against RT-1's saved shape.

`qa-fixture-cleanup.txt` — the raw scoped `DELETE` that `bi.audit.log` forces
(§5.128) and the fresh-cursor (psql) proof that the persona, its partner, the
two charts, the dashboard, both widgets, the 14 audit rows and the 3 device
logs are all gone, with the other dashboards' widget counts back to their
pre-pass values.

`i18n-loader-check.txt` — the loader output for all 19 new strings.
`test-results.txt` — the verbatim `odoo.tests.result` lines for all three runs.
