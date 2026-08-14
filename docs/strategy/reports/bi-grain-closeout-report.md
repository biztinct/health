# Phase BG-3 report — grain buckets in the viewer's calendar + BI closeout

Implements `docs/strategy/handovers/bi-grain-closeout.md`.
Deployed to **vietuat** (`-u biz_bi,biz_bi_cms`), branch `19.0`.
Modules: **`biz_bi`** `19.0.1.6.0` → **`19.0.1.7.0`**,
**`biz_bi_cms`** `19.0.1.3.0` → **`19.0.1.4.0`**.
Evidence pack: `docs/strategy/reports/bi-grain-closeout-evidence/`.

---

## 1. The headline

```
2026-08-14 01:49:52,071 2590442 INFO vietuat odoo.tests.stats: biz_bi: 149 tests 29.80s 18060 queries 
2026-08-14 01:49:52,071 2590442 INFO vietuat odoo.tests.stats: biz_bi_cms: 31 tests 7.60s 5589 queries 
2026-08-14 01:49:52,071 2590442 INFO vietuat odoo.tests.result: 0 failed, 0 error(s) of 134 tests when loading database 'vietuat' 
```

`/tmp/bg3/final.log`, **`EXIT:0`**, run against the exact tree that is
committed (the deployed directories were compared with the repo afterwards,
`__pycache__`/`.pyc` excluded — **byte-identical**, both modules). The
regression gate BG-2 set is held: **134** executed methods against BG-2's 96,
i.e. the phase's new tests and not one lost. `grep -ac "Starting Test.*\.test_"`
→ **134**, equal to the result line's count (§5.83/§5.90);
`grep -ac "ERROR: setUpClass"` → **0**, so both `HttpCase` classes really ran;
`grep -ac "FAIL: \|ERROR: "` → **0**. After the final restart
`ss -lntp | grep -c :8069` → **1** and
`curl localhost:8069/web/login` → **HTTP:200**.

The migration, from the first upgrade run (`/tmp/bg3/deploy.log`):

```
2026-08-14 01:23:51,763 2585928 INFO vietuat odoo.modules.migration: module biz_bi: Running migration [19.0.1.7.0>] post-truncate-query-cache 
2026-08-14 01:23:51,782 2585928 INFO vietuat post-truncate-query-cache: biz_bi BG-3: truncated bi_query_cache — 4 pre-BG-3 envelope(s) dropped so no stale UTC-cut grain bucket can be served 
```

---

## 2. What shipped

### 2.1 The grain cut (§3.1)

One expression, one place:

```python
DATE_TRUNC(%s, (<col> AT TIME ZONE 'UTC') AT TIME ZONE %s)   # grain, zone
```

`_grain_expr(expr, grain, data_type)` in `bi_query_engine.py` is the ONLY
producer of a truncation, and `_dimension_expr` is its only caller — which is
what makes the expression identical at every grain site by construction:
`_build_sql`'s SELECT and GROUP BY share the same `SQL` object, the top-N
"Others" predicate re-derives it through the same function, and the drill-down
`grain_overrides` path and compare requests both arrive as ordinary
`dimensions[].grain` through `bi.chart._to_query_request` (verified by reading
every `grain` reference in the module — there is exactly one `DATE_TRUNC` in
the codebase). A **date** column truncates exactly as before: it is already a
calendar.

**Trust boundary.** The zone is `str(pytz.timezone(user_tz_name(env)))`
(`bi_tz.sql_timezone_name`) — anything the database sees is a name pytz itself
accepted, an unknown or missing preference reads as `'UTC'`, and it is bound as
a **value**. The grain is bound as a value too, even though it is already
validated against `ALLOWED_GRAINS`, so the expression contains no interpolation
at all. `test_03` asserts the property rather than the spelling: the zone name
is **absent** from `query.code` and **present** twice in `query.params`;
`test_04` sends `"Mars/Olympus'); DROP TABLE bi_field; --"` as the context tz
and gets UTC buckets and an intact `bi_field` table.

**Consistency with BG-2's windows.** `test_05` freezes the clock at
`2026-03-31 18:00 UTC` and asks for `this_month` + month grain in one request:
the VN reader gets **one** bucket, April, containing exactly the rows the
filter selected; the UTC reader gets one bucket, March. Filter and grain now
cut the month in the same place, which is the property the phase exists to
create.

**Cross-user semantics are per-viewer by design** (the same posture as
"today"). Two people in different zones legitimately see different months for
the same data; the cache key already carries the zone (BG-2 D1), so nobody is
ever served the other's cut — `test_08` proves miss/hit/miss with different
rows, and both browser personas' identical request came back `cache: "miss"`.

### 2.2 The other end of the round trip (deviation D1, and the phase's real find)

Making the bucket a **local** wall clock silently inverted a rule BG-2 had
written down and pinned with a passing test: *"a bound that already carries a
time — a dashboard drill-down passes real bucket boundaries like
`2026-04-01 00:00:00` — is left exactly as it is."* True while buckets were cut
in UTC; false the moment they were not. Clicking the Vietnamese April bar would
have filtered the **UTC** April: seven hours wrong at both ends, in the one
gesture whose entire purpose is "show me the rows behind THIS bar".

Both ends are fixed:

* server — `window_bounds_for_field` now reads a clock-carrying bound as a
  wall-clock moment in the reader's zone and converts it back
  (`bi_tz.wall_clock_to_utc`, `as_wall_clock_datetime`). Plain dates are
  unchanged (`day_start_utc`), `date` columns are still untouched;
* client — `bucketEnd()` in `dashboard_action.js` parsed the bucket with
  `new Date("2026-04-01T00:00:00")`, i.e. **browser-local** (§5.159d), and then
  did UTC arithmetic, so a drill computed on the QA laptop (Sydney) asked for a
  window ten hours off. It now parses the bucket as UTC, does the calendar
  maths, and hands the naive wall clock back.

`test_06` drills the VN April bucket and asserts it returns exactly the rows
that bucket was built from — and that the same edges mean the UTC April for a
UTC reader. Ledger §5.163.

### 2.3 Complete relation labels (§3.2)

`MAX_LABEL_LOOKUP = 2000` (a silent *skip* above the threshold — RT-1 §9's
"one remaining path by which an export can show ids") is gone. Every distinct
id present in the rows is resolved, in chunks of `LABEL_LOOKUP_CHUNK = 1000`,
through `search` so the comodel's own record rules still decide which ids
resolve, per reader. No silent skip remains anywhere; the work is bounded by
the row caps the engine already applies (5000 preview /
`biz_bi.export_row_cap`). The unreadable-comodel fallback is unchanged and
still tested.

`test_every_id_present_is_labelled_not_just_the_first_2000` builds 2500
distinct partners, asserts all 2500 labels come back correct, and counts the
statements the resolution costs: **< 60** for 2500 ids (a per-id lookup would
be ~2500). The bound is deliberately loose — it asserts the SHAPE of the work,
not a query budget a prefetch change would flip red.

### 2.4 Records tile fetch cap (§3.3)

`bi.query.engine.apply_limit_override(request, limit_override)` — honoured only
when the derived request is **detail** mode **and** the value is strictly
smaller than the saved limit. A client can shrink, never grow; junk (`None`,
`0`, negatives, strings, dicts, JSON `true`) is ignored, never obeyed. Aggregate
requests are left alone on purpose: fewer rows of an aggregate is a different
ANSWER (fewer groups), not a shorter page. `/bi/query` applies it to
chart-derived entries only; raw Explore/wizard requests are untouched.

The dashboard sends `limit_override: 201` for Records widgets
(`widget.config.mode === 'detail'`) — 200 rendered plus one row to *know* there
are more — and `undefined` for everything else, so every other widget's request
and cache key are byte-identical to before. `meta.total_count` still powers the
honest overflow line.

Measured live (evidence §3): the tile's request carries `limit_override: 201`,
the response is 201 rows with `total_count: 483`, and the tile renders 200 plus
*"Showing the first 200 of 483 rows"*. The same chart in Explore still previews
all 483.

### 2.5 Wizard escape carries Records state (§3.4)

`explore_action.js` boot learns `params.records_config = {columns: [field_id],
filters: [{field_id, op, value}]}`: after `selectDataset` (so the metadata
exists), `applyRecordsConfig` seeds `chartType='table'`, `tableMode='records'`,
`recordsSeeded`, the columns resolved from metadata **in the given order** with
unknown ids dropped silently, and the filters into the filter slots. The
wizard's Records path passes it from `openAdvanced()`; the chart path is
unchanged (`dataset_id` only), and a SAVED report still travels as `chart_id`
and is rebuilt from `config_json` as before.

Driven end to end in the evidence pack: three columns ticked in the wizard
(Opportunity, Created On, Stage) + a `This month` date range → Explore opens in
**Records** mode with the same three columns in the same order and the same
filter chip.

---

## 3. Files

| File | Δ | What changed |
|---|---|---|
| `biz_bi/bi_tz.py` | +47 | `sql_timezone_name` (pytz-validated zone name for a SQL bind), `wall_clock_to_utc`, `as_wall_clock_datetime` |
| `biz_bi/models/bi_query_engine.py` | +101/−26 | `_grain_expr`; `_dimension_expr` uses it; `window_bounds_for_field` converts clock-carrying bounds; `apply_limit_override`; `MAX_LABEL_LOOKUP` → chunked complete `_attach_relation_labels` |
| `biz_bi/controllers/main.py` | +8/−3 | `/bi/query` applies `limit_override` to chart-derived requests |
| `biz_bi/static/src/components/dashboard/dashboard_action.js` | +33/−4 | `RECORDS_TILE_FETCH = 201` + `_widgetLimitOverride`; `bucketEnd` does wall-clock arithmetic |
| `biz_bi/static/src/components/explore/explore_action.js` | +44 | `applyRecordsConfig` + the boot hook |
| `biz_bi_cms/static/src/components/wizard/report_wizard.js` | +21/−4 | `openAdvanced` passes `records_config` on the unsaved Records path |
| `biz_bi/migrations/19.0.1.7.0/post-truncate-query-cache.py` | **new**, 34 | truncates `bi_query_cache` on upgrade |
| `biz_bi/tests/test_grain_tz.py` | **new**, 375 | `TestGrainTimezone` ×8, `TestLimitOverride` ×3, `TestLimitOverrideEndpoint` ×1 (HttpCase), `TestRecordsEscapeContract` ×2 |
| `biz_bi/tests/test_relation_labels.py` | +54 | the 2500-distinct completeness + statement-count test |
| `biz_bi/tests/test_timezone.py` | +14/−3 | BG-2's `test_01` clock-carrying assertion updated (D1) |
| `biz_bi/tests/__init__.py`, both `__manifest__.py` | +3/−2 | register the suite; versions |
| `docs/strategy/HANDOVER-CONVENTIONS.md` | +71 | ledger §5.163–§5.166 |

Plus this report and the evidence pack (README + 7 screenshots + 3 evidence
files).

**Migration:** `post-` (biz_bi's own table — §5.135 only forces `end-` for other
modules' registries), guarded with `to_regclass` and a no-op on a fresh
install. It ran once, dropped 4 envelopes, and does not re-run.

**Gold: nothing needed, and here is why** (`gold-verification.txt`, captured
live at `2026-08-14 01:44:51 UTC`, and `bi_dataset.py:391-451` /
`bi_gold.py:62-71`). `_compile_silver_sql` selects **raw columns**
(`t14.invoice_date AS f_1092` — quoted verbatim from the live
`bi_silver_6` definition), and `_publish_gold_for` materialises exactly that
SQL, so a gold matview stores raw datetimes and the grain is applied at query
time against `g.f_<id>`. Measured on the deployment: **zero** matviews contain
`date_trunc`, **zero** contain `time zone`, and the same is true of every
silver view — in fact `pg_matviews` currently holds **zero rows at all**. No
refresh was needed and none was attempted. (The zero-matview finding is itself
a pre-existing defect — §7.)

**i18n:** untouched, correctly. The phase adds no user-visible string: the
tile's overflow line, the truncation banner and every wizard label already
exist and are already translated; `limit_override`, `records_config` and the
grain expression emit no text.

**PWA:** nothing PWA-facing changed, so conventions §3 does not apply and
`health_pwa` was not bumped.

---

## 4. Tests

`biz_bi/tests/test_grain_tz.py` (+ two in existing files), all `post_install`.
Every window is measured from a **frozen** instant via BG-2's `_relative_now`
seam.

| # | Test | What it pins |
|---|---|---|
| 01 | `month_bucket_is_cut_in_the_readers_calendar` | the staged `2026-03-31 18:30 UTC` row is in the VN **April** bucket (`{Mar: 10, Apr: 50}`) and the UTC **March** one (`{Mar: 30, Apr: 30}`); each reader holds a row the other does not; the label is the naive local truncation, un-shifted |
| 02 | `a_date_column_grain_is_untouched` | identical buckets in every zone, and **no** `AT TIME ZONE` in the SQL for a date column |
| 03 | `the_expression_is_identical_in_select_and_group_by` | one truncation in SELECT and one in GROUP BY, same text; the zone absent from `query.code` and present in `query.params` (the trust boundary, asserted as a property) |
| 04 | `an_unknown_zone_falls_back_to_utc` | an injection-shaped context tz gives UTC buckets and leaves the schema intact |
| 05 | `this_month_filter_and_month_grain_agree` | §3.1's congruence at a frozen month boundary — one bucket per reader, the right one |
| 06 | `drilling_into_a_bucket_returns_that_bucket` | the filter-on-truncated-value path: the VN April edges select the VN April rows; the same edges are the UTC April for a UTC reader |
| 07 | `grain_override_uses_the_same_tz_cut` | the drill-down `grain_overrides` path (year → month) is cut in the same calendar |
| 08 | `two_timezones_never_share_a_cached_grain` | miss → hit → miss across a tz change, with different buckets |
| 09 | `shrink_is_honoured_grow_is_ignored` | 201 < 5000 honoured; 5001/20000/999999 ignored; junk ignored; the caller's request not mutated |
| 10 | `an_aggregate_request_is_never_shrunk` | an aggregate keeps its limit |
| 11 | `the_shrunk_limit_reaches_the_query` | fewer rows, `total_count` unaffected, `truncated` true |
| 12 | `dashboard_tile_fetches_what_it_draws` (HttpCase) | end to end through `/bi/query` with a real chart: 3 → 2 rows with `limit_override: 2`, `total_count` 3, and 999999 ignored |
| 13/14 | `TestRecordsEscapeContract` | the JS contracts (Explore seeds from `params.records_config`; the tile sends a shrinking override; `bucketEnd` parses as UTC) asserted on source with operator-bearing fingerprints (§5.72) and DRIVEN in the evidence pack |
| — | `test_every_id_present_is_labelled_not_just_the_first_2000` | 2500 distinct ids, 2500 labels, < 60 statements |

---

## 5. Deviations from the handover

**D1 — a clock-carrying window boundary is now CONVERTED, which changes a
BG-2 test.** §3.1 asks for the grain cut and for "any filter-on-truncated-value
path — find them all". Following that instruction leads to the drill-down,
whose `date_range` quotes a bucket edge back to the server; once the bucket is
a local wall clock, so is the edge. `window_bounds_for_field` therefore no
longer passes such a bound through, and BG-2's `test_01` — which asserted
exactly that pass-through — had to be updated (with its reasoning written into
the test). This is a forced sanction-list deviation of the §5.49 class: there
is no way to move the cut and leave the round trip correct. Ledger §5.163.

**D2 — `bucketEnd()` in `dashboard_action.js` was fixed too.** Not named in the
handover. It is the client half of D1 and it was *already* wrong for every
non-UTC browser (§5.159d); leaving it would have made the drill-down wrong in a
new second way. Six lines, no behaviour change for a UTC browser.

**D3 — the grain string is bound as a VALUE as well as the zone.** The handover
only requires it for the timezone. Binding both leaves the expression with no
interpolation to review at all, and costs nothing (`DATE_TRUNC(%s, …)` is the
same SQL after psycopg2 interpolates a quoted literal). It also makes `test_03`
a clean statement about the whole expression.

**D4 — `apply_limit_override` is a model method, not inline controller code.**
The handover says "Server: honored ONLY when …". Putting the rule on the engine
makes it unit-testable without HTTP and keeps the controller a two-line wiring;
the HttpCase then proves the wiring separately.

**D5 — the label-lookup constant was renamed, not kept.** §3.2 permits either.
`MAX_LABEL_LOOKUP` named a ceiling that no longer exists; `LABEL_LOOKUP_CHUNK`
names what the number now is. Nothing else in the repo referenced it
(grep-verified).

Everything else follows the handover literally: no timezone selector UI, no
stored-data conversion, PostgreSQL week semantics untouched, `RELATIVE_RANGES`
untouched, snapshot recipient-tz (BG-2 D6) and the zero-dataset staging still
parked, no `biz_bi_cms` edit beyond §4.4's `records_config` (plus its test),
path-scoped `git add`.

---

## 6. Browser evidence

`docs/strategy/reports/bi-grain-closeout-evidence/README.md` — the click-by-click
path from `/web/login` through the CMS sidebar (no deep links), seven
screenshots, the tile's real `/bi/query` exchange, the gold verification, the
deploy lines and the fixture cleanup.

Headline numbers, same request, same data, two personas, browser deliberately
in a third zone (`Australia/Sydney`):

| | Jul 2026 | Aug 2026 |
|---|---|---|
| `bg3_vn_qa` (`Asia/Ho_Chi_Minh`) | 1 | **2** |
| `bg3_utc_qa` (`UTC`) | **2** | 1 |

Both personas hit **§5.161** on first login (Odoo overwrote the set `tz` with
the browser cookie's); repaired through the session, service restarted, and the
value read back **inside the session that took the measurement** before every
screenshot.

QA fixtures — two personas, three back-dated `crm.lead` rows, a chart, a
dashboard, a widget and 16 `bi.audit.log` rows — are deleted, raw uid-scoped
`DELETE`s first (§5.128/§5.142), and verified gone from **psql, a different
process** than the shell that deleted them (§5.34): every count zero.

---

## 7. Found, not fixed — and worth a ticket

* **The Visit Margin dataset is dead on this deployment, and its refresh job
  says it is healthy.** `bi.dataset` 10 is `storage_mode='gold'`,
  `state='published'`, job 1 `idle` with `last_refresh 2026-08-13 15:43:34`,
  `is_healthy() → True` — and **`bi_gold_10` does not exist**. Measured, not
  inferred: a records query against it returns `{'error': 'Query failed — see
  server log.'}` and the log says
  `psycopg2.errors.UndefinedTable: relation "bi_gold_10" does not exist`.
  `is_healthy()` reads `state != 'error' and bool(last_refresh)`; nothing checks
  the relation, so the engine routes every query for that dataset to a missing
  table. It also means the *Visit Margin* dashboard tile in the Analytics hub is
  broken for every user today. Not in this phase's sanction; ledger §5.166.
  (How the matview vanished is not established — `biz_bi_margin` uses
  `CREATE OR REPLACE VIEW`, which cannot cascade-drop it.)
* **Two floating widgets overlay Explore's configuration panel** — the
  health_learn *Care Coach* drawer (`lrn-drawer`/`lrn-fab`) and the Zalo chat
  panel — and swallow clicks on the chart-type gallery and the filter chips at
  1600×1200. It cost three wrong diagnoses during QA (ledger §5.165) and a real
  user on that viewport has the same collision.
* **`shift_filters_previous` still truncates a drill-down `date_range` to whole
  days** (BG-2 §8). Unchanged, and now slightly more visible: a previous-period
  comparison of a drilled *day* resolves to that day's local midnight rather
  than the exact bucket edge. Harmless for month/quarter comparisons.
* **The snapshot email still renders in the cron user's timezone** (BG-2 D6) and
  the zero-dataset staging remains parked, both as the handover requires.

---

## 8. New ledger entries

Appended to `docs/strategy/HANDOVER-CONVENTIONS.md` in this same commit
(§5.108 — a gotcha that lives only in a report does not exist for the next
phase):

* **§5.163** — when a value starts being computed in the READER's calendar,
  every boundary the client hands BACK is in that calendar too, and the rule
  you wrote one phase earlier becomes false; plus the client-side mirror
  (`new Date(naive)` is browser-local) and the cache corollary (nothing in the
  request changes when the MEANING of the request changes — truncate the cache
  in the migration).
* **§5.164** — composing an `SQL` object into a `%s` slot substitutes CODE while
  a plain argument stays a PARAMETER: assert on `query.code` + `query.params`,
  never on the format string — and that assertion is the better one anyway.
* **§5.165** — an unrelated module's floating widget silently swallows
  chrome-devtools clicks; `document.elementFromPoint` on the target's own centre
  names the thief in one call, before you reach for §5.126 or doubt the handler.
* **§5.166** — `bi.refresh.job.is_healthy()` is a claim about the job ROW, not
  the materialisation; verify with `to_regclass`, not a status column.

---

## 9. Commit

Branch `19.0`, pushed to `RHealth19`. Path-scoped to `addons/biz_bi/`,
`addons/biz_bi_cms/`, `docs/strategy/HANDOVER-CONVENTIONS.md` and
`docs/strategy/reports/bi-grain-closeout-*`. The working tree carried extensive
unrelated changes from another session throughout and none of them is in this
commit; the repo's tracked `.pyc` files, which a local syntax check touched,
were restored to `HEAD` before staging. `docs/strategy/handovers/` is untracked
in this working tree and outside the sanctioned paths, so — as in BG-1 and
BG-2 — the commit does not add it.
