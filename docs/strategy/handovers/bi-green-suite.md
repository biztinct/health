# Phase BG-1 handover — biz_bi green suite + deferred-fix sweep

Stream: **BI hardening** (quiet-time cleanup; closes debts recorded in
the AH-3 and RT-1/RT-2 reports). Read
`docs/strategy/HANDOVER-CONVENTIONS.md` first (ledger is current
through §5.153 — §5.130/§5.133/§5.137–§5.143 directly apply), then the
failure analyses in `docs/strategy/reports/analytics-hub-phase3-report.md`
(the six names + first diagnosis) and
`docs/strategy/reports/records-table-phase1-report.md` (the §5.133
refinement: three of the six are better explained by vietuat's
res.partner "own partner only" rule). Sanction: `addons/biz_bi/**` +
report/evidence paths + ledger appends. `biz_bi_cms` ONLY for §4.3's
banner dedupe consumer. Path-scoped `git add`.

## 1. What this phase is

Five debts, one phase:

1. **Green the biz_bi suite on vietuat** — the six failures
   (`TestRls.test_column_mask_null` error,
   `TestPipeline.test_dataset_reads_clean_view`,
   `TestQueryEngine.test_compare_request_runs`,
   `TestRls.test_rls_users_never_share_cache`,
   `TestRls.test_row_rule_filters_rows`,
   `TestSnapshot.test_snapshot_xlsx_builds`) are FIXTURE fragility
   against real-data databases, not product bugs (they fail closed).
   Definition of success: `0 failed, 0 error(s)` for the FULL biz_bi
   suite on vietuat — a real milestone; every future phase stops
   comparing failure names against a doc.
2. **Excel datetimes in the user's timezone** — RT-1 exports datetime
   cells in UTC; VN users read them 7h off. Convert with the user's tz
   (`self.env.user.tz or 'UTC'`, standard pytz localize→astimezone)
   at the export layer only; the on-screen table already goes through
   the client's formatter — verify both agree in QA.
3. **Wizard truncation-notice dedupe** — add a `suppressOverflowRow`
   optional prop to `DataTable` (default False, dashboard/Explore
   unchanged), and pass it from the wizard's records preview
   (`biz_bi_cms/static/src/components/wizard/`) which shows its own
   banner (RT-2 report D2).
4. **AI audit attribution** — `bi.ai._log` records uid 1 when the
   sudo'd provider path runs (AH-3 report, deferred). The log call
   must record the REAL user (capture `self.env.uid` before any sudo
   scope; pass it explicitly). Prove with a creator-persona nlq call.
5. **NLQ count hint** — "leads by source"-style prompts pick a revenue
   measure. Add one deterministic line to `NLQ_SYSTEM_PROMPT`
   (`models/bi_ai.py`): when the prompt asks "how many / number of /
   <entity> by <dimension>" with no explicit amount wording, prefer
   `agg: "count"` on any field over a monetary measure. Prompt-only
   change; the validator already constrains output. NOTE: `bi_ai.py`
   now routes through `odoo.addons.ai_egress.egress` — read that
   module's contract first and do not bypass or weaken it.

## 2. Binding non-goals

- NO product-behavior changes beyond §1.2–§1.5. Fixing the six tests
  must NOT weaken assertions to pass (§5.62 spirit): make fixtures
  self-contained/robust, keep what each test proves. If any of the six
  turns out to be a REAL product bug after reproduction, fix the
  product minimally and flag it prominently in the report.
- NO reruns/edits of other modules' suites; no ai_egress changes; no
  new config surface; RT deferred items NOT in §1 stay deferred
  (>2000-distinct labels, widget fetch size).

## 3. Known diagnosis (verify by reproducing, then fix)

- `tests/common.py` (BiCase) builds a dataset over live `res.partner`
  joined to `res.country`: vietuat has ~77 partners with latitudes
  polluting aggregates, `res_country.name` is translated jsonb
  (`Vietnam` vs `Việt Nam`) so name-keyed row rules match nothing, and
  a deployment `res.partner` "own partner only" ir.rule filters
  fixture rows for non-admin test users. Likely fix directions (pick
  what reproduction supports): filter every fixture query to the
  `BI Test %` rows it created (several already do — extend the
  pattern); key row rules on ids/codes instead of translated names;
  give test users whatever record-rule bypass the PRODUCT would give
  equivalent real users rather than editing deployment rules. Tests
  must pass on BOTH a bare dev DB and vietuat.
- Reproduce first on vietuat (scoped tags per failing class), fix,
  then the full-suite gate.

## 4. Tests & proof

- Full biz_bi suite on vietuat: `0 failed, 0 error(s)` (verbatim
  line; also quote the scoped runs). biz_bi_cms suite stays green
  (verbatim line — §4.3 touches its wizard).
- New/updated tests: tz export (a datetime cell equals the user-tz
  wall clock — xlsx cell inspection like RT-1's), suppressOverflowRow
  (component-level or QA-evidenced), audit attribution (nlq as
  creator → audit row uid == creator, mock `_complete_validated`).
- NLQ hint: evidence via one live nlq round trip ("how many bookings
  by service type" or the user's literal "leads by source") showing
  `agg: count` chosen — plus the materialized chart screenshot.

## 5. Deploy + report-back

Deploy per conventions §2 + §5.130 check, `-u biz_bi,biz_bi_cms`,
vietuat. Browser evidence →
`docs/strategy/reports/bi-green-suite-evidence/`: the NLQ count case,
an Excel export whose datetime column reads VN wall-clock (cell dump),
the wizard records preview with a single truncation notice, audit row
uid proof. Fixtures cleaned + fresh-cursor verified (§5.128/§5.142 —
raw scoped DELETEs FIRST). Report →
`docs/strategy/reports/bi-green-suite-report.md` (committed): files,
deviations, verbatim result lines (the green full-suite line is the
headline), per-test root cause table for the six, new gotchas
(§5.154+). Self-review before reporting; commit on 19.0 and push
(remote is `RHealth19`).

## Kickoff line

Implement the phase specified in docs/strategy/handovers/bi-green-suite.md.
