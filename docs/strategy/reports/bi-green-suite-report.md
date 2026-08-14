# Phase BG-1 report — biz_bi green suite + deferred-fix sweep

Implements `docs/strategy/handovers/bi-green-suite.md`.
Deployed to **vietuat** (`-u biz_bi,biz_bi_cms`), branch `19.0`.
Modules: **`addons/biz_bi`** `19.0.1.4.0` → **`19.0.1.5.0`**,
**`addons/biz_bi_cms`** `19.0.1.2.0` → **`19.0.1.3.0`**.
Evidence pack: `docs/strategy/reports/bi-green-suite-evidence/`.

---

## 1. The headline

```
2026-08-14 00:02:50,894 2574541 INFO vietuat odoo.tests.stats: biz_bi: 111 tests 17.41s 9541 queries 
2026-08-14 00:02:50,894 2574541 INFO vietuat odoo.tests.result: 0 failed, 0 error(s) of 85 tests when loading database 'vietuat' 
```

`/tmp/bg1/final_bi.log`, `EXIT:0`. **The full `biz_bi` suite is green on
vietuat** for the first time since the module shipped — no failure list, no
"the usual six", nothing to compare against a doc.

`biz_bi_cms`, `/tmp/bg1/final_cms.log`, `EXIT:0`:

```
2026-08-14 00:03:13,573 2574569 INFO vietuat odoo.tests.stats: biz_bi_cms: 30 tests 7.42s 5581 queries 
2026-08-14 00:03:13,574 2574569 INFO vietuat odoo.tests.result: 0 failed, 0 error(s) of 22 tests when loading database 'vietuat' 
```

85 executed for `biz_bi` against RT-1's 79 (+3 in `test_detail_mode`, +3 in the
new `test_ai_attribution`); 22 for `biz_bi_cms` against RT-2's 21 (+1). The
executed-method count matches the result line's count in both runs and
`grep -ac "ERROR: setUpClass"` is **0**, so the four `TestExportXlsx` HttpCases
really ran (§5.83/§5.90 — full grep output in
`bi-green-suite-evidence/test-results.txt`).

After the final restart: `ss -lntp | grep -c :8069` → **1**,
`curl localhost:8069/web/login` → **HTTP:200**. Deployed trees compared against
the repo afterwards, file by file, both modules: every source file identical
(`__pycache__` excluded — the repo tracks `.pyc` built by a different Python
than the server's, and none of them is in this commit).

---

## 2. **Two of "the six" were not fixture fragility** — read this part

The handover, following AH-3 and RT-1, states that all six failures are
"FIXTURE fragility against real-data databases, not product bugs (they fail
closed)". Reproduction says otherwise for two of them, and I flag it here
rather than in a table at the bottom.

**(a) `TestSnapshot.test_snapshot_xlsx_builds` was a REAL PRODUCT BUG.** It
failed on `assertTrue(dashboard.next_send)`, and it would have failed on a bare
dev database too. `bi.dashboard.next_send` was maintained by
`_onchange_schedule` and by a `write()` override — and by nothing on the create
path. A dashboard **created** with `schedule_enabled=True` therefore kept
`next_send = False`, and `_process_snapshot_queue` selects on
`('next_send', '!=', False)`: its scheduled email snapshot never went out, and
never said so. The form view hid it completely, because the onchange fills the
field in the client before `create` is called, so only a programmatic create —
an import, `bi.ai.compose_report`, a test — could ever see it. Fixed minimally
with a `create()` override mirroring the existing `write()` one (ledger §5.2's
shape; the entry is now §5.155). The test now also asserts `next_send` is in
the future and that turning the schedule off clears it again.

**(b) `TestPipeline.test_dataset_reads_clean_view` was an arithmetic error in
the test.** It expected `60.75` with the comment `# 10.5+20+30.25` — but the
pipeline under test ends in a filter step that removes the `Gamma` row worth
`30.25`. The clean view holds `10.5`, `20` and a NULL (`'oops'` guarded by the
cast), so the honest answer is **30.5**, on every database that has ever
existed. Corrected, with the arithmetic spelled out, plus a new assertion that
the dataset really is reading `bi_clean_<id>` and not the raw table (which
could not sum `amount_raw` at all — it is text there). Nothing was weakened:
30.5 proves *more* than 60.75 did, because it also proves the filter step ran.

**(c) A SEVENTH failure exists and no report lists it.**
`TestQueryEngine.test_relative_filter` failed in the reproduction run — because
that run happened at **23:49 UTC**. `relative_bounds` resolves "today" through
`fields.Date.context_today`, i.e. the acting user's timezone, and the superuser
that runs tests on vietuat carries **Europe/Brussels** (§5.107), so after 22:00
UTC "today" is already tomorrow and fixtures created seconds earlier fall
outside their own window. Every earlier run of this suite happened in the
morning. Fixed by pinning `tz='UTC'` on `BiCase`'s environment, which also
removes a latent month-end flake in `test_compare_request_runs`.

The other four are the live-data family the reports describe, and all four do
fail closed. Details per test in §3.

---

## 3. Per-test root cause

| Test | Symptom on vietuat | Root cause | Fix |
|---|---|---|---|
| `TestRls.test_row_rule_filters_rows` | `None != 30.0` (both halves) | **two** causes stacked: the engine injects the root model's `ir.rule` into every live query, and vietuat's `res.partner` rule 340 *"User: Own Partner Record"* hides all three fixture rows from a plain internal user; and the rule's own predicate was keyed on `country_a.name`, a **translated jsonb** column the engine reads through `->> <caller language>`, so the literal `"Vietnam"` matches nothing for a non-`en_US` reader | `_allow_all_partners()` (a permissive `res.partner` rule created **inside the transaction**, rolled back with it) + the row rule re-keyed on `res.country.code = 'VN'`, a plain varchar that is the same on every database. Both assertions unchanged |
| `TestRls.test_rls_users_never_share_cache` | `None != 30.0` on the restricted read | same partner rule | same |
| `TestRls.test_column_mask_null` | `IndexError: list index out of range` | same partner rule → **zero** rows came back, and a `mask_mode='null'` measure compiles to a bare `NULL` constant with no aggregate, so an empty input really does produce an empty result rather than one NULL row | same, and the assertion **strengthened**: the three rows must still be there and every value in them must be `None`. An empty result would have proved nothing about the mask |
| `TestQueryEngine.test_compare_request_runs` | `109.2041578 != None` | the fixture chart carried the date filter but **no** scoping filter, so the previous-month SUM ran over the whole of live `res.partner` — 77 partners carry a latitude here, 7 of them created last month | the chart gets the fixture's own `'BI Test'` name filter beside the date filter, and is built through the UTC env; plus a new sanity assertion that the CURRENT window returns 60.0, so the NULL below is the shift working and not an empty filter |
| `TestPipeline.test_dataset_reads_clean_view` | `30.5 != 60.75` | **wrong constant in the test** — 60.75 adds back the row the pipeline's filter step removes. Red on every database, misfiled as live-data fragility | expectation corrected to 30.5 with the arithmetic spelled out, plus an assertion that the source resolves to the clean view |
| `TestSnapshot.test_snapshot_xlsx_builds` | `False is not true` on `next_send` | **product bug** — `next_send` maintained on `write()` and onchange only, so a created-with-schedule dashboard is never queued | `create()` override on `bi.dashboard`; test extended to pin the future timestamp and the clear-on-disable |
| *(7th, undocumented)* `TestQueryEngine.test_relative_filter` | `[] is not true` | §5.107: relative windows resolve in the caller's tz (Europe/Brussels for the test superuser) against UTC columns; only fails 22:00–24:00 UTC | `BiCase` pins `tz='UTC'`, so a window means what `create_date` means at any hour of any day |

**Robust on both a bare dev DB and a real-data DB.** Every fix is either a
scoping filter the fixture already used elsewhere (`'BI Test'`), an
id/code-keyed predicate instead of a translated one, a transaction-local record
rule that is a no-op where the deployment rule does not exist, a corrected
constant, or a UTC pin. None of them depends on a row this database happens to
hold, and none weakens an assertion — three of them tighten one.

---

## 4. The other four items

**§1.2 — Excel datetimes in the user's timezone.** `_export_tz()` resolves
`request.env.user.tz or 'UTC'` (unknown zone → UTC, never a crash) and
`_to_user_tz()` converts naive-UTC → naive-in-that-zone; `_write_cell` applies
it to `type == 'datetime'` columns only. **Pure `date` columns are deliberately
untouched** — a date has no time to shift and moving it would change the day.
Proven in the browser: `bi-green-suite-evidence/excel-datetime-tz.txt` puts the
same report exported by a UTC+10 reader and a UTC+7 reader beside what
PostgreSQL stores; `2026-04-27 02:30:00` UTC reads `12:30` and `09:30`
respectively, and five rows are cross-checked against the FSO table.

*Stated rather than buried:* the on-screen table does **not** agree with the
export in all cases, and the screen is the wrong one. `formatDimensionValue`
does `new Date("2026-04-27T02:30:00")`, which a browser parses as **local**
time, and then renders only the date part — so for an instant after 17:00 UTC
the screen shows one day and the (now correct) export shows the next. The
handover scopes §1.2 to "the export layer only" and §2 forbids product changes
beyond §1.2–§1.5, so the client-side formatter is left alone and written up in
ledger §5.157 and in §7 below. The engine's relative-date windows carry the
same UTC-vs-reader mismatch and are likewise flagged, not changed.

**§1.3 — one truncation notice, not two.** `DataTable` gained
`suppressOverflowRow` (Boolean, optional, default **false**, folded into the
memo key so a toggle cannot serve a stale table). The wizard passes
`suppressOverflowRow="!!recordsTruncation"` — bound to the *same getter* that
decides whether the banner renders, so there is no arrangement in which neither
of them speaks. Explore and the dashboard tile are unchanged. Measured live on
step 3 with 1 271 records: `.bi-wizard-banner` → **1**,
`.bi-table-overflow` → **0** (evidence 09, 10).

**§1.4 — AI audit attribution. The deferred defect does not exist, and this is
the most important correction in the phase.** AH-3 reasoned that
`self.env['bi.audit.log'].sudo().log(...)` makes `log()` read `self.env.uid`
"from the sudo'd recordset" and therefore record uid 1. In Odoo 19 `sudo()`
does **not** change the user — the source says so in as many words
(`odoo/orm/models.py:5946`: *"superuser mode does not change the current user,
and simply bypasses access rights checks"*) — it only sets `su=True`. Measured
before touching anything: `bi_audit_log` held **29** `ai_request` rows at uid 2
(a real person) and 7 at uid 1, and the uid-1 rows are the TEST suite, which
runs as SUPERUSER. The pre-existing code was already correct.

I hardened it anyway, because the handover asks for the uid to be captured and
passed explicitly and because an explicit argument survives a refactor that a
re-read of `env.uid` does not: `_log` now captures `asked_by = self.env.uid`
before anything is sudo'd and passes it to `bi.ai.log.create` and to
`bi.audit.log.log(user_id=…)` (a new optional kwarg, defaulting to the caller's
uid, so all eight other call sites are unchanged). Proven live rather than
argued: `bi.audit.log` rows 2283 / 2285 and `bi.ai.log` 46 / 47 all carry
**uid 8603**, the throwaway creator persona (`ai-audit-attribution.txt`).
Ledger §5.154.

**§1.5 — NLQ count hint.** One rule appended to `NLQ_SYSTEM_PROMPT` only
(`COUNTING BEATS MONEY BY DEFAULT`), conditional on the request naming no
amount — it lists the amount words in English *and* Vietnamese so it cannot
override an explicit "doanh thu"/"revenue" ask. Prompt-only; the validator is
untouched. Two live round trips as the creator persona: the user's literal
*"leads by source"* → `{"agg": "count", "field_id": 1497}` on Contact Source
(evidence 05), and *"how many bookings by service type"* →
**"Number of Bookings by Service Type"**, a count to ~1 200, where a revenue
measure was the failure mode (evidence 07). Both proposals are in
`bi_ai_log.response_json` verbatim.

**ai_egress was neither edited nor bypassed.** `bi_ai.py` still calls
`self.env['ai.egress.log'].guard(user_message, egress.SCHEMA, provider.provider,
provider.endpoint, surface='biz_bi.<kind>')` before any completion, and the
live drive produced `ai.egress.log` rows 84 / 85 on its allow path
(`schema` / `openai` / `local=f` / `allowed=t`, no findings, uid 8603). A new
test also pins that the gate's decision is recorded for the same person, using
a loopback-Ollama provider so it exercises the *local* branch rather than
mocking the gate away.

---

## 5. Files

| File | Δ | What changed |
|---|---|---|
| `biz_bi/tests/common.py` | +42/−1 | `f_country_code`; `_allow_all_partners()` (promoted from `test_detail_mode`, now with the `flush_all()` §5.112 needs); `env_utc` + a UTC-pinned `cls.engine` |
| `biz_bi/tests/test_rls.py` | +17/−4 | `setUp` widens partner visibility; both row rules keyed on the country **code**; the null-mask assertion strengthened |
| `biz_bi/tests/test_query_engine.py` | +20/−3 | `test_compare_request_runs` scoped to the fixture + a current-window sanity assert; a comment on the UTC pin in `test_relative_filter` |
| `biz_bi/tests/test_pipeline.py` | +19/−2 | corrected constant + clean-view assertion; `next_send` assertions extended |
| `biz_bi/tests/test_detail_mode.py` | +120/−16 | duplicate helper removed; `_excel_serial` / `_xlsx_numbers`; **3 new tests** — the tz round trip, the tz helpers, the `DataTable` opt-in |
| `biz_bi/tests/test_ai_attribution.py` | **new**, 113 | `TestAiAttribution` ×3 — audit uid, egress decision uid, the prompt rule |
| `biz_bi/tests/__init__.py` | +1 | registers it |
| `biz_bi/models/bi_dashboard.py` | +16 | **product fix**: `create()` sets `next_send` |
| `biz_bi/models/bi_audit_log.py` | +10/−2 | `log(..., user_id=None)` |
| `biz_bi/models/bi_ai.py` | +16/−2 | `_log` captures the uid before any sudo and passes it to both logs; the `NLQ_SYSTEM_PROMPT` counting rule |
| `biz_bi/controllers/main.py` | +36/−4 | `_export_tz` / `_to_user_tz`; `tz` threaded through `_build_xlsx` → `_write_cell` |
| `biz_bi/static/src/components/explore/data_table.js` | +12/−3 | `suppressOverflowRow` prop, in the memo key |
| `biz_bi/__manifest__.py` | +1/−1 | version → `19.0.1.5.0` |
| `biz_bi_cms/static/src/components/wizard/report_wizard.xml` | +5/−1 | passes `suppressOverflowRow="!!recordsTruncation"` |
| `biz_bi_cms/tests/test_wizard_records.py` | +33 | T4 — the notice is stated once, by the banner |
| `biz_bi_cms/__manifest__.py` | +1/−1 | version → `19.0.1.3.0` |
| `docs/strategy/HANDOVER-CONVENTIONS.md` | +109 | ledger §5.154–§5.158 |

Plus this report and `docs/strategy/reports/bi-green-suite-evidence/`
(README + 10 screenshots + 2 workbooks + 6 evidence text files).

**Migration:** none. No column, index, data record or seed changed; both
version bumps are declarative.

**i18n:** untouched, and correctly so — the phase adds no user-visible string.
The prompt rule is sent to a language model, not rendered; the `DataTable`
overflow sentence is unchanged and still translated; the controller gained no
`_()`. Nothing to loader-verify.

**PWA:** no PWA asset, app shell or shell-injecting module touched, so
conventions §3 does not apply and `health_pwa` was not bumped.

---

## 6. Deviations from the handover

**D1 — §1.4's premise is false, and the item is a hardening rather than a
fix.** Detailed in §4. Reported prominently because a design doc, a phase
report and a handover all carried the same wrong inference.

**D2 — a product change the handover did not sanction: `bi.dashboard.create()`.**
§2 forbids product behaviour changes beyond §1.2–§1.5, *unless* reproduction
shows a real bug, in which case it says to fix minimally and flag prominently.
That is exactly this (§2a). Sixteen lines, mirroring the existing `write()`
override, in the module the phase already owns.

**D3 — a seventh test was fixed.** `test_relative_filter` is not in the
handover's list of six; it was red in the reproduction run and would have
blocked the `0 failed` gate. The fix is one line in the shared fixture and it
also removes a month-end flake from `test_compare_request_runs`.

**D4 — `_allow_all_partners` moved from `test_detail_mode.DetailCase` to
`BiCase`.** The RLS suite needs the identical widening, and one copy is one
behaviour. `biz_bi_cms/tests/test_wizard_records.py` keeps its own third copy:
deleting it is outside the sanction (`biz_bi_cms` is sanctioned for the wizard
consumer only), it is harmless as an override, and it is worth one line of a
future tidy-up.

**D5 — the `test_column_mask_null` and `test_pipeline` assertions were
tightened, not merely repaired.** §2 forbids weakening; strengthening is the
opposite, and in both cases the original assertion could pass vacuously (an
empty result set; a constant that never checked the filter step ran).

**D6 — two workbooks in the evidence pack, not one.** The persona was created
with `tz = Asia/Ho_Chi_Minh` and the browser login overwrote it with the
browser's own zone (§5.158). Rather than delete the first export I kept both:
one file proves a number, two files prove the cell follows the *reader*, which
is the actual contract.

**D7 — the browser evidence includes a second NLQ ask.** The handover offers
"how many bookings by service type" *or* the user's literal "leads by source";
I did both, because the CRM Leads dataset is thin for a catchment-less creator
and a one-bar chart is weak evidence of a count.

Everything else follows the handover literally: no ACL widened, no group
granted, no deployment record rule touched, no new config surface, no
`ai_egress` edit, RT's deferred items (>2000-distinct labels, widget fetch
size) still deferred, no other module's suite re-run or edited, path-scoped
`git add`.

---

## 7. Deferred, and what a reader should know

* **The on-screen datetime formatter is still wrong** where the export is now
  right (§4). One-line class of fix in `formats.js`, out of sanction here.
  It matters most for a `datetime` column rendered near midnight UTC.
* **The engine's relative-date windows resolve in the caller's timezone against
  UTC columns**, so "today" means the UTC day for a Vietnamese user. Not
  touched (a product change with a real blast radius across saved charts and
  caches); ledgered as §5.157. Worth its own small phase with a migration
  thought about cached envelopes.
* **`_build_snapshot_xlsx` (the scheduled email snapshot) still writes
  datetimes as `str(value)`**, i.e. raw UTC, and does not go through the export
  writer at all. §1.2 scopes the fix to "the export layer"; this is a second
  writer, and now that `next_send` actually queues (§2a) those emails will
  start going out for the first time. Small, self-contained follow-up.
* **The guided picker cannot represent "count of a dimension field"**, so an
  AI proposal using `agg: count` on a text column shows *— choose —* in "What
  do you want to measure?" when you step Back (evidence 06). The chart is
  correct and saves correctly; only the round-trip into the simplified picker
  loses it. Pre-existing, unrelated to the prompt change, worth a ticket.
* **`bi_query_cache` cannot be cleaned per-user** — no `create_uid` at all
  (§5.142). QA rows expire on their TTL; noted in the cleanup evidence.
* **The uid-1 rows already in `bi_audit_log`** (7 `ai_request`, 32
  `chart_save`, and others) are historical TEST-suite rows, not a defect.
  Nothing was deleted except this phase's own QA rows.

---

## 8. New ledger entries

Appended to `docs/strategy/HANDOVER-CONVENTIONS.md` in this same commit
(§5.108 — a gotcha that lives only in a report does not exist for the next
phase):

* **§5.154** — `sudo()` does not change `env.uid` in Odoo 19; an attribution
  claim is something to measure with a `GROUP BY`, not to infer from the code
  shape. The uid-1 rows in an audit table are usually your test runs.
* **§5.155** — a stored field maintained by `write()` and an onchange is not
  maintained by `create()`, and a queue that selects on it goes silently quiet;
  the form view hides it because the onchange fills the field before create.
* **§5.156** — a known-failing set inherits its diagnosis, and the inheritance
  is where the real bugs hide: re-derive every failure from its own traceback.
* **§5.157** — relative date windows resolve in the caller's timezone against
  UTC columns; the flaky test is the visible edge, the export and the engine
  are the rest. Say which half of a timezone story you fixed.
* **§5.158** — a `res.users.tz` set from a shell did not survive the persona's
  first browser login; set a user preference through the session that will
  exercise it, and read it back before measuring.

---

## 9. Commit

Branch `19.0`, pushed to `RHealth19`. Path-scoped to `addons/biz_bi/`,
`addons/biz_bi_cms/`, `docs/strategy/HANDOVER-CONVENTIONS.md` and
`docs/strategy/reports/bi-green-suite-*`. The working tree carried unrelated
changes from another session throughout and none of them are in this commit;
neither are the repo's tracked `.pyc` files, which a local syntax check had
touched and which were restored to `HEAD` before staging.
`docs/strategy/handovers/bi-green-suite.md` is untracked in the working tree
and is outside the sanctioned paths, so — as in AH-3 — the commit does not
add it.
