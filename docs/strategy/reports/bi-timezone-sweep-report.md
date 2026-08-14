# Phase BG-2 report — biz_bi timezone sweep

Implements `docs/strategy/handovers/bi-timezone-sweep.md`.
Deployed to **vietuat** (`-u biz_bi`), branch `19.0`.
Module: **`addons/biz_bi`** `19.0.1.5.0` → **`19.0.1.6.0`**.
Evidence pack: `docs/strategy/reports/bi-timezone-sweep-evidence/`.

---

## 1. The headline

```
2026-08-14 00:44:16,630 2580129 INFO vietuat odoo.tests.stats: biz_bi: 126 tests 19.72s 10728 queries 
2026-08-14 00:44:16,630 2580129 INFO vietuat odoo.tests.result: 0 failed, 0 error(s) of 96 tests when loading database 'vietuat' 
```

`/tmp/bg2/bi3.log`, **`EXIT:0`**. The gate BG-1 set — the full `biz_bi` suite
green — is held: **96** executed methods against BG-1's 85, i.e. the eleven new
ones and not one lost. `grep -ac "ERROR: setUpClass"` → **0**, so the
`TestExportXlsx` HttpCase really ran (§5.83/§5.90); the executed-method count
equals the result line's count. After the final restart
`curl localhost:8069/web/login` → **HTTP:200**, and the deployed tree was
compared file by file against the repo afterwards (`__pycache__` excluded):
identical.

---

## 2. One rule, four surfaces

> Datetimes are STORED in UTC and PRESENTED in the viewing user's timezone;
> relative-date windows are computed in that timezone and converted to UTC
> instants before they touch a UTC column; calendar values never move.

The rule now lives in exactly one place, `addons/biz_bi/bi_tz.py`, and the
distinction it turns on is a single predicate:

```python
def column_is_instant(column):
    return column.get('type') == 'datetime' and not column.get('grain')
```

An **instant** is re-read in the reader's zone. A `date` column and every
grain truncation are **calendar labels** and never shift — shifting
`DATE_TRUNC('month')`'s `2026-04-01 00:00` for a UTC-5 reader would rename the
April bucket "March". The predicate is mirrored in `formats.js` as
`columnIsInstant`, and `test_11` asserts the mirrored expression character for
character so the two cannot drift apart silently.

**§1.1 — the screen.** `formatDimensionValue` fed the engine's naive string
straight to `new Date(...)`. That is wrong in two opposite directions at once:
`new Date("2026-08-13 18:30:00")` is parsed as **browser-local** (a UTC wall
clock relabelled), while `new Date("2026-08-13")` is parsed as **UTC
midnight** (a day early for every negative offset). Both paths are gone. A
date-only value is pinned with `new Date(text + "T00:00:00Z")` and rendered
with `timeZone: "UTC"`, so it reads as the very day it says in every zone on
earth; an instant is parsed as UTC and rendered with `timeZone: user.tz`.
Using the user's **Odoo** preference rather than the browser's zone is what
makes the screen and the export the same answer — and the evidence pack proves
it by leaving the browser in `Australia/Sydney` throughout.

**§1.2 — the windows.** `relative_bounds` still returns half-open calendar
boundaries and `RELATIVE_RANGES` is untouched (RT-1 pinned that vocabulary).
What is new is `window_bounds_for_field(start, end, field)`, applied in
`_compile_filter_op` to both `relative` and `date_range`: for a `datetime`
column each boundary becomes the UTC instant at which that local day begins;
for a `date` column the plain dates go in unchanged; and a boundary that
already carries a clock — the dashboard drill-down passes real bucket edges
like `2026-04-01 00:00:00` — is left exactly as it is. `relative_today()`
replaces the direct `fields.Date.context_today` call so that the window and
the conversion resolve the zone through one code path and cannot disagree
about which zone is in force (a test env pinning `tz='UTC'` moves both).

**§1.3 — the second writer.** `_build_snapshot_xlsx` wrote every non-measure
cell as `str(value)`, i.e. the raw naive-UTC ISO string, and never went near
the export writer. It now shares `cell_value`/`column_is_instant` and writes
real datetime cells with a number format. The dashboard-schedule audit is §4.

---

## 3. Files

| File | Δ | What changed |
|---|---|---|
| `biz_bi/bi_tz.py` | **new**, 141 | the shared rule: `user_tz_name` / `user_timezone` / `to_user_tz` / `day_start_utc` / `as_calendar_date` / `column_is_instant` / `parse_engine_datetime` / `cell_value` |
| `biz_bi/controllers/main.py` | +16/−31 | `_export_tz` / `_to_user_tz` / `_parse_date` delegate to it; `_write_cell` uses `cell_value` + `column_is_instant` |
| `biz_bi/models/bi_query_engine.py` | +65/−5 | `_tz` / `_relative_now` (the test seam) / `relative_today` / `window_bounds_for_field`; both date operators converted; the tz threaded into the cache key |
| `biz_bi/models/bi_query_cache.py` | +9/−4 | `make_key(..., tz=None)` |
| `biz_bi/models/bi_dashboard.py` | +30/−5 | `_build_snapshot_xlsx` writes datetime cells in the reader's zone |
| `biz_bi/static/src/core/formats.js` | +99/−4 | `columnIsInstant`, `parseEngineDate`, `calendarPartsIn`, `viewerTimeZone`; every render carries an explicit `timeZone` |
| `biz_bi/tests/common.py` | +60 | `excel_serial` / `xlsx_numbers` / `xlsx_strings` promoted to module level; `f_date_localization` (a real calendar-date column) added to the fixture |
| `biz_bi/tests/test_detail_mode.py` | +6/−44 | the three xlsx readers now delegate to `common.py` |
| `biz_bi/tests/test_timezone.py` | **new**, 395 | `TestTimezoneWindows` ×8 + `TestTimezoneWorkbooks` ×3 |
| `biz_bi/tests/__init__.py` | +1 | registers it |
| `biz_bi/__manifest__.py` | +1/−1 | version → `19.0.1.6.0` |
| `docs/strategy/HANDOVER-CONVENTIONS.md` | +73 | ledger §5.159–§5.162 |

Plus this report and `docs/strategy/reports/bi-timezone-sweep-evidence/`
(README + 5 screenshots + 1 workbook + 6 evidence text files).

**Migration:** none. No column, index, data record or seed changed. The query
cache key changes shape, so live entries miss once and are replaced; that is
the intended effect and needs no script (rows expire on a 60 s TTL for a live
dataset).

**i18n:** untouched, and correctly so — the phase adds no user-visible string.
The client change alters how an existing value is *formatted*, not what text
is emitted; no `_()` or `_t()` was added anywhere. Nothing to loader-verify.

**PWA:** no PWA asset, app shell or shell-injecting module touched, so
conventions §3 does not apply and `health_pwa` was not bumped.

---

## 4. The dashboard-schedule audit (§1.3) — what was found, what was set

**Found: nothing. Set: nothing.** In full, because "nothing" is the kind of
answer that has to be shown rather than asserted
(`bi-timezone-sweep-evidence/schedule-audit.txt`, timestamped
2026-08-14 00:44:56 UTC):

| id | dashboard | schedule_enabled | next_send | last_sent |
|---|---|---|---|---|
| 1 | Operations Overview | f | — | — |
| 2 | Revenue & Receivables | f | — | — |
| 5 | Báo cáo hoạt động điều hành | f | — | — |
| 6 | BI Usage Analytics | f | — | — |
| 7 | Visit Margin | f | — | — |
| 9 | Monthly Revenue by Facility | f | — | — |
| 10 | Facility Analytics | f | — | — |

All seven rows of `bi_dashboard` (raw SQL, no `active` filter, so archived rows
would appear too — none is archived). Zero have `schedule_enabled`; every
`next_send` and `last_sent` is NULL; `bi_dashboard_recipients_rel` holds **0**
rows; and `bi_audit_log` holds **0** `snapshot_email` rows in its entire
history. The cron is live and harmless: `ir_cron` **96**, active, hourly, last
ran 00:04:26, next 00:59:56 — it selects
`schedule_enabled AND next_send != False AND next_send <= now`, which is the
empty set.

So **no `next_send` was written by this phase**, no catch-up burst was
possible, and no dashboard was touched. Two notes a reviewer should have:

* BG-1's `create()` fix only fills `next_send` for dashboards created *after*
  it shipped. The pre-existing seven were created between 2026-07-02 and
  2026-08-06 with `schedule_enabled` false, so they were never candidates in
  either direction. The exposure the handover was right to worry about is
  **future** — a dashboard created programmatically with the schedule on will
  now correctly queue — and it is bounded: `_process_snapshot_queue` sends at
  most one email per due dashboard per run and immediately advances
  `next_send` via `_compute_next_send`, which loops `while candidate <= now`,
  so a stale `next_send` produces one send, never a backlog replay.
* The audit was re-run after the browser drive (`qa-fixture-cleanup.txt`, last
  column): still zero. This pass created no scheduled sender of its own.

---

## 5. Tests

`biz_bi/tests/test_timezone.py`, all `post_install`. Every window is measured
from a **frozen** instant — `_relative_now` exists as a seam precisely so a
near-midnight or month-end case is testable at 09:00 on a Tuesday instead of by
waiting for 23:59 (§5.107's flake class, engineered away rather than tolerated).

| # | Test | What it pins |
|---|---|---|
| 01 | `window_bounds_convert_only_for_a_datetime_column` | VN `[2026-03-05, 2026-03-06)` → `[2026-03-04 17:00, 2026-03-05 17:00)` UTC for a datetime column; **unchanged** for a date column; **unchanged** for a bound that already carries a clock; identity in value for a UTC reader |
| 02 | `today_is_the_readers_day_not_the_utc_one` | three partners backdated across the boundary; VN "today" returns {Beta, Gamma}, UTC "today" returns {Alpha, Beta}. **Each reader has a row the other does not**, so it cannot pass by the window merely being wide |
| 03 | `last_7_days_moves_with_the_reader` | same two-way discrimination on a rolling window |
| 04 | `this_month_at_a_month_boundary` | frozen at 2026-03-31 18:00 UTC, where the reader is already in April and UTC is not |
| 05 | `a_date_column_never_shifts` | the off-by-one trap in the other direction: the WINDOW still follows the reader's calendar, the BOUNDARIES stay plain dates, and no row is nudged by seven hours |
| 06 | `two_timezones_never_share_a_cached_answer` | key inequality, then miss → hit → **miss** across a tz change, with different rows |
| 07 | `tz_helpers` | `to_user_tz`, `day_start_utc`, `as_calendar_date` (an instant reads as `None`), context-before-user tz resolution |
| 08 | `only_an_ungrained_datetime_is_an_instant` | the predicate and `cell_value`, including the month bucket that must not move |
| 09 | `export_shifts_an_instant_and_leaves_a_bucket_alone` | one workbook, three columns: month grain unshifted, instant shifted, date untouched |
| 10 | `snapshot_email_workbook_reads_in_the_users_timezone` | the second writer, VN and UTC copies |
| 11 | `client_formatter_mirrors_the_instant_rule` | the JS contract, asserted on expressions with operators in them so a comment cannot satisfy it (§5.72), plus `assertNotIn('new Date(value)')` |

A JS test tier does not exist in this module, so §1.1 is covered by 11 plus the
browser evidence — including a check that the **served, minified bundle**
contains the new symbols and no longer contains the old constructor (§5.147).

---

## 6. Deviations from the handover

**D1 — the phase writes the TIMEZONE into the query cache key.** Not asked
for. Without it the fix is not observable end to end: two readers in different
zones send an identical request, must get different rows, and would be served
each other's day for the cache's TTL with `meta.cache: 'hit'` as the only
trace. One optional argument on `make_key`, no API shape change (the cache is
internal and has no other caller in the repo). Ledger §5.160.

**D2 — the conversion is applied to `date_range`, not only to `relative`.**
§1.2 names relative windows. `date_range` is where `shift_filters_previous`
lands *every* relative window it shifts for a previous-period comparison, so
converting only one of them would leave the current and comparison windows
seven hours out of step with each other — a worse bug than the one being
fixed. Bounds that already carry a time (dashboard drill-down) are explicitly
left alone, so the drill path is unchanged.

**D3 — a grain truncation no longer shifts in the EXPORT either.** BG-1's
`_write_cell` shifted any `type == 'datetime'` cell, grain buckets included.
Once §1.1 makes the screen treat a bucket as a calendar label, leaving the
export shifting it would put the two back into disagreement for negative-offset
readers — which is the exact failure this phase exists to end. One predicate
now governs all three writers. A grained cell is also written with the
`yyyy-mm-dd` format rather than `yyyy-mm-dd hh:mm:ss`, since a month bucket has
no meaningful clock.

**D4 — a Records-mode datetime now shows its TIME on screen.** The handover
scopes §1.1 to parsing. But the export writes `yyyy-mm-dd hh:mm:ss` and the
table showed a bare date, so "the screen and the export agree" was not
checkable by a user, and the half that used to be wrong was invisible. Time is
shown only where `columnIsInstant` is true and no grain is set, which in
practice is Records mode alone: Explore defaults a date dimension's grain to
`month` the moment it is dropped (`explore_action.js:362`), so no chart axis
label changes.

**D5 — `_export_tz` resolves context-tz before `user.tz`.** It read
`env.user.tz` only. `fields.Date.context_today` reads the context first, and
the phase's whole argument is that the window and the presentation resolve one
zone; two resolutions would diverge in exactly the environment that pins one
(a test env, a cron run `with_context(tz=…)`). In an HTTP request the two are
the same value, because `res.users.context_get` puts the user's tz in the
context — so no live behaviour changes, and the pre-existing
`test_export_tz_helpers` still passes unmodified.

**D6 — the snapshot workbook reads in the SENDING environment's timezone**
(the cron user's), not the recipient's. That is the literal reuse the handover
asked for and it matches what `_send_snapshot` already does for the date in the
mail's own subject (`fields.Date.context_today(self)`). It is not ideal — a
recipient in another zone reads the sender's clock — but choosing per-recipient
or per-owner rendering is a design decision the handover did not sanction, and
it is moot today: zero dashboards have a schedule and zero have recipients
(§4). Flagged in §8 rather than decided here.

**D7 — three xlsx readers moved from `TestExportXlsx` to `tests/common.py`.**
The new snapshot suite needs the identical pair and one copy is one behaviour
(the same reasoning as BG-1's D4). The old names survive as `staticmethod`
aliases so no existing test body changed.

Everything else follows the handover literally: `RELATIVE_RANGES` untouched, no
timezone selector UI, no stored data converted, no `biz_bi_cms` / `ai_egress` /
PWA edit, the >2000-distinct label lookup and widget fetch size still deferred,
no other module's suite re-run or edited, path-scoped `git add`.

---

## 7. Browser evidence — the three things the handover asked to see

Full pack in `bi-timezone-sweep-evidence/README.md`. Driven from `/web/login`
by clicking, as a throwaway creator persona (`bg2_qa`, uid 8625,
`group_bi_creator` only — modeler and admin both False), **with the browser
itself left in `Australia/Sydney` on purpose**: a screen that agrees with the
persona while the machine says something else is proof, a screen that agrees
with both proves nothing.

1. **The same record, three ways** (`datetime-screen-vs-export.txt`).
   `2026-08-13 18:30:00` in PostgreSQL reads `14 Aug 26 01:30` on screen and
   `46248.0625` = `2026-08-14 01:30` in the workbook the **Excel** button
   produced. Four rows, two of them crossing midnight, every one exactly
   UTC+7. The screen values are computed DOM text; the export values are raw
   `<v>` serials out of `sheet1.xml` (a date is a number in xlsx, which is how
   an export can be seven hours wrong while every string assertion passes).
2. **A "today" filter returning VN-today rows**
   (`today-filter-two-readers.txt`, screenshots 04 and 05). At 00:51 UTC the
   VN reader's "Today" returns 5 rows including the one stored at
   `2026-08-13 18:30 UTC` (01:30 *this morning* in Vietnam) and excluding the
   one stored at `2026-08-14 18:00 UTC` (tomorrow there). The same wizard for
   the same account after switching to UTC returns 6 rows with those two
   exclusions swapped. `bi_audit_log` corroborates from the server side —
   `rows: 5` then `rows: 6` — and, because `run()` returns on a cache hit
   *before* it writes its audit row, the second row existing at all is the
   proof that the second reader's query was a cache miss (D1).
3. **The schedule audit** (`schedule-audit.txt`, and §4 above) — the whole
   table, timestamped, plus the cron row; nothing found and nothing set.

Console: zero errors, zero warnings across the drive (`console-log.txt`; the
six entries are two pre-existing DevTools a11y issues, twice, and two
informational logs from other modules).

QA fixtures — a persona, four backdated audit rows, the session's own audit
rows and the captured workbook — are deleted and verified gone **from a
different process** (`qa-fixture-cleanup.txt`), raw uid-scoped `DELETE`s first
because `bi.audit.log` is append-only with a required user FK (§5.128) and
because an ORM unlink a later SQL error rolls back still prints as done
(§5.142). No chart and no dashboard was ever saved. `bi_query_cache` is
deliberately not cleaned: it has no `create_uid` at all, so there is no uid to
scope a delete to, and its rows expire on a 60 s TTL.

---

## 8. Deferred, and what a reader should know

* **The snapshot email renders in the cron user's timezone** (D6). Worth one
  small decision — per-recipient is impossible (recipients are `res.partner`
  and may have no user), per-**owner** is one line and probably right — but it
  is a design change and it affects nobody today.
* **Grain buckets are still cut in UTC.** This phase fixed how a bucket is
  LABELLED (it never shifts); it did not change where `DATE_TRUNC` puts the
  boundary. A Vietnamese user's "August" therefore still starts at 00:00 UTC
  on 1 August, i.e. 07:00 local, so seven hours of rows sit in the previous
  bucket. Fixing it means `DATE_TRUNC(grain, col AT TIME ZONE 'UTC' AT TIME
  ZONE <user tz>)`, which changes every cached envelope and every gold
  materialisation — a phase of its own, with the same "which half did you fix"
  discipline §5.159 asks for.
* **`shift_filters_previous` truncates a drill-down `date_range` to whole
  days** (`fields.Date.to_date` on a `2026-04-01 00:00:00` string). Pre-existing
  and untouched; harmless for month/quarter comparisons, imprecise for a day
  drill.
* **The >2000-distinct label lookup and the widget fetch size** remain
  deferred from RT-1, as the handover requires.
* **The guided picker still cannot represent "count of a dimension field"**
  (BG-1 §7) — unrelated, still worth a ticket.

---

## 9. New ledger entries

Appended to `docs/strategy/HANDOVER-CONVENTIONS.md` in this same commit
(§5.108 — a gotcha that lives only in a report does not exist for the next
phase):

* **§5.159** — a timezone story has four halves, and the client formatter is
  the one that silently disagrees; JS's two string forms are wrong in opposite
  directions; the fix is one predicate mirrored python↔JS with a test on the
  mirrored expression.
* **§5.160** — a per-reader window makes the timezone part of the cache key;
  anything the answer depends on that is not in the request payload belongs in
  the key.
* **§5.161** — §5.158's mechanism found and cited: `_update_last_login`
  overwrites `res.users.tz` from the browser cookie on an account's first
  login even when the tz is already set (the guard is an `or`). Plus the
  evidence-design corollary: leave the browser in a different zone on purpose.
* **§5.162** — an Excel serial is a float, so a datetime assertion needs a
  tolerance; and `datetime.fromisoformat('2026-03-04')` succeeds, so a parser
  that tries the datetime form first turns every calendar date into an instant.

---

## 10. Commit

Branch `19.0`, pushed to `RHealth19`. Path-scoped to `addons/biz_bi/`,
`docs/strategy/HANDOVER-CONVENTIONS.md` and
`docs/strategy/reports/bi-timezone-sweep-*`. The working tree carried
extensive unrelated changes from another session throughout and none of them
is in this commit; neither are the repo's tracked `.pyc` files, which a local
syntax check had touched and which were restored to `HEAD` before staging.
`docs/strategy/handovers/bi-timezone-sweep.md` is untracked in the working tree
and outside the sanctioned paths, so — as in BG-1 — the commit does not add it.
