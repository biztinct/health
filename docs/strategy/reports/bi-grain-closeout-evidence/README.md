# BG-3 browser evidence pack — grain buckets in the viewer's calendar

Driven on **https://care.biztinct.com** (vietuat) after the deploy, from
`/web/login` by clicking — no deep links. Two throwaway personas, both cloned
from the live `om` account's group set plus `biz_bi.group_bi_creator` (the
Analytics sidebar leaf is gated on the Operations-Manager `access.role`):

| persona | uid | Odoo timezone | browser timezone |
|---|---|---|---|
| `bg3_vn_qa` | 8680 | `Asia/Ho_Chi_Minh` | `Australia/Sydney` |
| `bg3_utc_qa` | 8681 | `UTC` | `Australia/Sydney` |

The browser is left in a **third** zone on purpose (§5.161): a screen that
agrees with the persona while the machine says something else is proof; a
screen that agrees with both proves nothing.

Both personas hit ledger **§5.161** on their first login — Odoo's
`_update_last_login` overwrote the deliberately-set `tz` with the browser
cookie's `Australia/Sydney`. Repaired the documented way: written back
**through the authenticated session**, the service restarted, and the value
read back **inside the session that took the measurement** before every
screenshot (`user_context.tz` = `Asia/Ho_Chi_Minh` / `UTC` respectively).

## Staged fixture (deleted afterwards — see "Cleanup")

Three `crm.lead` rows, `create_date` back-dated by raw SQL around the
July/August 2026 boundary:

| lead | `create_date` (UTC, as stored) | VN wall clock | VN month | UTC month |
|---|---|---|---|---|
| BG3QA Boundary A | `2026-07-31 10:00:00` | 31 Jul 17:00 | July | July |
| BG3QA Boundary B | `2026-07-31 18:30:00` | **1 Aug 01:30** | **August** | **July** |
| BG3QA Boundary C | `2026-08-10 06:00:00` | 10 Aug 13:00 | August | August |

B is the discriminator: the same stored instant belongs to a different month
on each reader's calendar.

---

## 1. Month-grain chart — VN persona vs UTC persona

Path (identical for both): `/web/login` → CMS sidebar **ANALYTICS → Analytics**
→ **Create Report** → **CRM Leads** → **Open in advanced builder** → Explore →
drag *Created On* to **Axis** (grain `month`, the default), *Opportunity* to
**Values** (`count`), *Opportunity* to **Filters** (`like_i` = `BG3QA`).

| | Jul 2026 | Aug 2026 |
|---|---|---|
| **VN reader** (`05-vn-month-grain-chart.png`) | **1** | **2** |
| **UTC reader** (`06-utc-month-grain-chart.png`) | **2** | **1** |

Each reader holds a row the other does not, so this cannot pass by a window
merely being wide. The raw envelopes, read in-session from each persona's own
browser (`POST /bi/query`, same payload, same dataset, same filter):

```
VN  tz=Asia/Ho_Chi_Minh  rows=[["2026-07-01T00:00:00",1],["2026-08-01T00:00:00",2]]  meta.cache="miss"
UTC tz=UTC               rows=[["2026-07-01T00:00:00",2],["2026-08-01T00:00:00",1]]  meta.cache="miss"
```

Two further things this shows:

* **The label is un-shifted** (BG-2's rule still holds): the bucket the VN
  reader is served is the naive local truncation `2026-08-01T00:00:00` and it
  renders as `Aug 2026`, not shifted back into July by the client formatter —
  a grained column is not an instant.
* **Cache segregation**: both readers' identical request is a `miss`. The
  timezone is part of the cache key (BG-2 D1), so the second reader can never
  be served the first one's cut.

`01-vn-hub.png` is the Analytics hub the drive starts from.

## 2. Records path → "Open in advanced builder" carries the state

`02-vn-wizard-records-columns.png` — the wizard's **Records list** step with
three columns ticked, in order: **1 Opportunity, 2 Created On, 3 Stage**, date
range **This month**.

`03-vn-wizard-records-preview.png` — the preview. Top row is
`BG3QA Boundary B | 01 Aug 26 01:30 | Initial Contact`: the row stored at
`2026-07-31 18:30 UTC` is inside the Vietnamese reader's "this month" and
displays in their wall clock (BG-2's window + formatter, unchanged).

`04-vn-explore-records-after-escape.png` — **the same click, one screen
later**: Explore opens in **Records** mode (segmented control on `Records`),
with the identical three columns in the identical order and the
`Created On / relative / This month` filter chip carried across. Before BG-3
this landed in Summary with an empty canvas.

Read back from the page after the escape:

```
mode      : Records (active)
columns   : ["Opportunity", "Created On", "Stage"]
filters   : Created On · relative · this_month
first rows: BG3QA Boundary B | 01 Aug 26 01:30 | Initial Contact
            BG3QA Boundary C | 10 Aug 26 13:00 | Initial Contact
```

## 3. Records dashboard tile fetches what it draws

`07-vn-records-tile-dashboard.png` — a saved Records chart (`limit` 5000, 483
rows visible to this persona) dropped on a new dashboard through
**Add to Dashboard**.

`tile-limit-override.json` is the tile's own `/bi/query` exchange:

```
request : {"requests":[{"chart_id":282,"extra_filters":[],"limit_override":201}]}
response: 201 rows, meta.total_count = 483, meta.mode = "detail"
rendered: 200 rows + "Showing the first 200 of 483 rows — open in Explore or
          export for the full set."
```

201 = the 200 the tile renders plus one row to *know* there are more, so the
overflow line is true without a second query. The saved chart's own limit is
untouched (Explore still previews 483), and the server refuses any override
that would GROW a limit or that arrives on an aggregate request
(`test_09`/`test_10`/`test_12`).

## 4. Console

`list_console_messages` across every screen of the drive returned exactly one
entry, on both personas:

```
[issue] A form field element should have an id or name attribute
```

a pre-existing Chrome DevTools accessibility issue on the Odoo login/backend
forms, present before this phase. **Zero errors, zero warnings, zero failed
requests.** Two unrelated floating widgets (the health_learn *Care Coach*
drawer and the Zalo chat panel) overlay the Explore configuration panel and
swallowed several clicks; they were hidden with `style.display='none'` for the
rest of the drive. That is a QA-driving workaround, not a product change — but
it is a real usability collision on a 1600×1200 viewport and is reported.

## 5. Gold verification (`gold-verification.txt`)

Captured live, timestamped `2026-08-14 01:44:51 UTC`. `pg_matviews` holds
**zero** rows on this database, silver views select **raw columns**
(`t14.invoice_date AS f_1092`), and no view or matview definition contains
`date_trunc` or `time zone`. Grain is applied only at query time, so **gold
needed no refresh** and the migration does not attempt one.

The same query records a pre-existing, unrelated defect: dataset **10 (Visit
Margin)** is `storage_mode = gold` with a *healthy* refresh job
(`last_refresh 2026-08-13 15:43:34`) and **no `bi_gold_10` matview** — see the
report §7.

## 6. Cleanup (§5.34 / §5.128 / §5.142)

Raw uid-scoped `DELETE`s **first** (a `bi.audit.log` row is append-only with a
required `user_id` FK, so the persona is otherwise undeletable, and an ORM
unlink that a later SQL error rolls back still prints as done), then the ORM
unlinks, then a verification from **psql — a different process** from the
`odoo-bin shell` that did the deleting:

```
DELETE FROM bi_audit_log   WHERE user_id IN (8680,8681);   -- 16 rows
DELETE FROM bi_query_cache WHERE dataset_id = 7;           --  1 row

qa_users 0 | qa_leads 0 | qa_charts 0 | qa_dashboards 0
qa_widgets 0 | qa_audit 0 | qa_partners 0 | cache_rows 0
```

Nothing this pass created remains on the deployment.
