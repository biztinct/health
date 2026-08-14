# BG-2 browser evidence pack — biz_bi timezone sweep

Driven on **https://care.biztinct.com** (vietuat) on 2026-08-14 between 00:48
and 00:53 UTC, in an isolated browser context (`bg2qa`), as a throwaway
**Operations-Manager-role BI creator** created for this pass and deleted
afterwards (`qa-fixture-cleanup.txt`): **`bg2_qa`, uid 8625**.

Persona shape, cloned from the live `om` account (uid 29): `base.group_user` +
the `health_base.group_healthcare_*` ladder + **`biz_bi.group_bi_creator`**,
`access_role_id = 2` (Operations Manager). `has_group('biz_bi.group_bi_modeler')`
and `…group_bi_admin` are both **False** — no masking bypass, no RLS bypass.

**The browser's own timezone is `Australia/Sydney` (UTC+10) for the whole
drive.** That is not an accident of the QA machine, it is the control: every
value on screen below is `Asia/Ho_Chi_Minh` (UTC+7), so the screen demonstrably
follows the reader's **Odoo** preference and not the machine's clock — which
the pre-BG-2 formatter could not do at all, because `new Date(<naive string>)`
is parsed as browser-local.

Every screen was reached by **clicking**, from the login page. No deep link,
no hand-typed URL.

```
/web/login → (log in) → /bizapp shell → sidebar ANALYTICS ▸ Analytics
   → Create Report → step 1: "BI Usage"
   → step 2: Records list → tick Res Model / When / Event
   → step 3: preview (VN wall clocks)  →  Excel  (POST /bi/export/xlsx → 200)
   → Back → Date range "Today" → Preview            (VN "today", 5 rows)
   → Preferences-equivalent tz write → reload → the identical wizard again
                                                     (UTC "today", 6 rows)
```

---

## 1. The walk

| # | File | What it shows |
|---|------|---------------|
| 01 | `01-login.png` | the real entry point |
| 02 | `02-analytics-hub.png` | the Analytics hub as this persona — four workspaces, no dashboard of its own |
| 03 | `03-records-preview-vn-wallclock.png` | the Records preview. Four fixture rows read `14 Aug 26 10:00 / 14 Aug 26 01:30 / 13 Aug 26 17:00 / 15 Aug 26 01:00` — each exactly UTC+7 of what PostgreSQL stores, two of them on a **different calendar day** from the stored value |
| 04 | `04-today-filter-vn-day.png` | the same wizard with **Date range: Today**. Five rows, including the 18:30-UTC row that is 01:30 **this morning** in Vietnam and excluding the 18:00-UTC row that is tomorrow there |
| 05 | `05-today-filter-utc-reader.png` | the identical request after the reader's timezone was set to UTC. Six rows: the two exclusions swap sides, and every clock on screen loses seven hours |

## 2. The three-way match (handover §5, first evidence item)

`datetime-screen-vs-export.txt` — the same records in PostgreSQL, on screen and
in the workbook, side by side. `bg2-browser-export-vn.xlsx` is the bytes the
**Excel** button produced in this session (10 971 bytes, audit row 2620,
`rows: 376`, `capped: false`), captured by wrapping `window.fetch` and posting
them back as an `ir.attachment` because the headless context does not persist
downloads. The cells are read as raw `<v>` **serials** — a date is a number in
xlsx, which is exactly how an export can be seven hours wrong while every
string assertion passes.

It also records the served-bundle check (§5.147): the minified
`web.assets_web.min.js` the browser actually received contains
`columnIsInstant` and `T00:00:00Z` and no longer contains `new Date(value)`.

## 3. The relative window (handover §5, second evidence item)

`today-filter-two-readers.txt` — one "Today" button, two readers, two honest
answers, with the row each reader gains and the row each reader loses named in
both directions. Server-side corroboration from `bi_audit_log`: the VN query
logged `rows: 5`, the UTC query `rows: 6`. `bi.query.engine.run` returns on a
cache hit **before** it writes its audit row, so the second row existing at all
proves the second reader's request was a cache MISS — the timezone really is
part of the cache key, and nobody was served somebody else's day.

## 4. The dashboard-schedule audit (handover §1.3, third evidence item)

`schedule-audit.txt` — the full `bi_dashboard` table on vietuat, timestamped.
**Zero** of the seven dashboards has `schedule_enabled`; every `next_send` and
`last_sent` is NULL; there are **zero** snapshot recipients and **zero**
`snapshot_email` rows in the entire audit history. The hourly cron (`ir_cron`
96, active, last ran 00:04) therefore selects nothing.

**Nothing was set, because there was nothing to set** — no catch-up burst was
possible and none was prevented by hand. The audit was re-run after the drive
(`qa-fixture-cleanup.txt`, last column) and is still zero.

## 5. The §5.158 mechanism

`tz-preference-mechanism.txt` — BG-1 recorded that a shell-set `res.users.tz`
did not survive the persona's first login and did not explain it. This pass
reproduced it and found the line: `res_users.py:771-774` overwrites `tz` from
the browser cookie when `not user.tz` **or** `not user.login_date`, i.e. on the
first login of any account, even one whose timezone is already set.

## 6. Console

`console-log.txt` — zero errors, zero warnings across the whole drive. The six
entries are two pre-existing DevTools a11y *issues* (twice) and two
informational logs from other modules.

## 7. Server-side rows, cleanup, tests

`server-side-rows.txt` lists what the pass created; `qa-fixture-cleanup.txt`
deletes it and proves it gone **from a different process** than the one that
did the deleting (§5.34), raw uid-scoped `DELETE`s first (§5.128/§5.142).
`test-results.txt` carries the verbatim green suite line, the executed-method
count, and the eighteen methods of the two suites this phase touched.
