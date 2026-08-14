# BG-1 browser evidence pack — biz_bi green suite + deferred-fix sweep

Driven on **https://care.biztinct.com** (vietuat) on 2026-08-14 between 00:04
and 00:14 UTC, in an isolated browser context (`bg1qa`), as a throwaway
**Operations-Manager-role BI creator** created for this pass and deleted
afterwards (`qa-fixture-cleanup.txt`): **`bg1_qa`, uid 8603**.

Persona shape, cloned from the live `om` account (uid 29): `base.group_user` +
the `health_base.group_healthcare_*` ladder + **`biz_bi.group_bi_creator`**,
`access_role_id = 2` (Operations Manager). `has_group('biz_bi.group_bi_modeler')`
and `…group_bi_admin` are both **False** — no masking bypass, no RLS bypass.
Everything below is what a real creator sees.

Every screen was reached by **clicking**, from the login page. No deep link,
no hand-typed URL.

```
/web/login → (log in) → /bizapp shell → sidebar ANALYTICS ▸ Analytics
   → Create Report → step 1: "CRM Leads"
   → step 2: type "leads by source" → Build it for me      (NLQ #1)
   → step 1 again: "Bookings & Service Orders"
   → step 2: "how many bookings by service type" → Build it for me   (NLQ #2)
   → Back → Records list → tick Client / Scheduled Date & Time /
        Total Price / Status → Preview
   → step 3: ONE truncation notice + Excel + the 100-row preview
   → Excel  (POST /bi/export/xlsx → 200, 1 271 rows, 30 KB workbook)
```

---

## 1. The walk

| # | File | What it shows |
|---|------|---------------|
| 01 | `01-login.png` | the real entry point |
| 02 | `02-shell-sidebar.png` | the CMS shell as this persona; **ANALYTICS ▸ Analytics** is in the sidebar |
| 03 | `03-analytics-hub.png` | the Analytics hub — four workspaces, no dashboard of this user's own yet |
| 04 | `04-wizard-nlq-ask.png` | step 2 on **CRM Leads** with the literal ask *"leads by source"* typed into the AI box (the box AH-3 opened to creators) |
| 05 | `05-nlq-chart-count.png` | the materialised chart. The proposal is `agg: "count"` on Contact Source, so the y-axis is a **row count** (0…1), not a revenue measure — the exact case §1.5 exists for. The bars are thin because this creator's catchment is unset, which is honest and unrelated |
| 06 | `06-nlq-step2-breakdown.png` | Back on step 2: the AI's break-down-by landed on **Contact Source**, while "What do you want to measure?" reads *— choose —* because the guided picker cannot represent "count of a dimension field" (see report §7) |
| 07 | `07-nlq-bookings-count-chart.png` | the same hint on a dataset with volume: *"how many bookings by service type"* → **"Number of Bookings by Service Type"**, y-axis to 1 500, Home Visit ≈ 1 200. A count, not Total Price |
| 08 | `08-records-columns-picked.png` | Records list, four columns ticked in order: Client, Scheduled Date & Time, Total Price, Status |
| 09 | `09-records-preview-single-notice.png` | step 3: **one** notice — *"Showing first 100 of 1,271 records — the saved report and Excel export include more."* — above the fold, next to Excel |
| 10 | `10-records-table-bottom-no-second-notice.png` | the same table scrolled to its **last** row. Before this phase RT-1's `DataTable` wrote a second, differently-worded overflow row here. `document.querySelectorAll('.bi-table-overflow').length` → **0**, `.bi-wizard-banner` → **1** |

## 2. The Excel export, and its datetimes

`bg1-browser-export.xlsx` and `bg1-browser-export-vn.xlsx` are the bytes the
**Excel button** produced, twice, for the same report. They were captured from
the same authenticated session by wrapping `window.fetch` and posting the
response bytes back as an `ir.attachment` (83508 / 83509) — the headless
context does not persist downloads — then read out of the filestore. Both are
1 header + **1 271 data rows** (audit rows 2289 / 2290 / 2292, `rows: 1271`,
`capped: false`), i.e. the whole result set, not the 100 the preview draws.

The only difference between the two files is the **reader's timezone**, and
that is the point: `excel-datetime-tz.txt` puts them side by side against what
PostgreSQL actually stores. `2026-04-27 02:30:00` UTC reads `12:30` for a
Sydney reader and `09:30` for a Vietnamese one; before this phase both files
carried `02:30`.

*(Why two files: the persona was created with `tz = Asia/Ho_Chi_Minh`, and the
web client overwrote it with the browser's own zone at login — worth knowing,
and written up in the report. The second export followed the user setting
their timezone back through the ordinary `res.users.write` the Preferences
dialog makes. Both files are genuine and together they prove the cell follows
the reader, which one file could not.)*

## 3. Attribution, and the gate

`ai-audit-attribution.txt` — `bi.audit.log` `ai_request` rows **2283 / 2285**
carry `user_id 8603`, the human who asked, not uid 1; `bi.ai.log` 46 / 47 the
same, with the AI's own proposal in `response_json` (`"agg": "count"` in both);
and `ai.egress.log` 84 / 85 show the ai_egress gate ran on its allow path
(`schema` / `openai` / `local=f` / `allowed=t`, no findings). The gate was not
bypassed, weakened or edited.

## 4. Console

`console-log.txt` — the whole drive produced **zero** console errors and zero
warnings; the only two entries are pre-existing DevTools a11y *issues* about a
form field without an `id`, on the CMS shell.

## 5. Server-side rows, and cleanup

`server-side-rows.txt` lists what the pass created; `qa-fixture-cleanup.txt`
deletes it and proves it gone **from a different process** than the one that
did the deleting (§5.34). Raw uid-scoped `DELETE`s ran FIRST, in their own
committed transaction, because `bi.audit.log` / `bi.ai.log` are append-only
with a `required` user FK (§5.128) and because an ORM unlink that a later SQL
error rolls back still prints as done (§5.142).

## 6. Tests

`test-results.txt` — the reproduction run with all seven tracebacks, then the
two green suite lines, then the executed-method count and list (§5.83/§5.90),
then the post-restart health check.
