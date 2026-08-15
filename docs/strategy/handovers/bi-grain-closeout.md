# Phase BG-3 handover — grain buckets in the viewer's calendar + BI closeout

Stream: **BI hardening**, closeout. Prereqs: BG-1/BG-2 live (full biz_bi
suite green — that line is the regression gate). Read
`docs/strategy/HANDOVER-CONVENTIONS.md` (ledger through §5.162), then
`docs/strategy/reports/bi-timezone-sweep-report.md` (the BG-2 tz rule,
`bi_tz.py`, the deferred grain-cut item and its cache/gold warning),
then `docs/strategy/reports/records-table-phase1-report.md` (label
lookup, tile cap, export machinery). Sanction: `addons/biz_bi/**`,
`addons/biz_bi_cms/**` ONLY for §4.4's wizard-escape param,
report/evidence paths, ledger appends. Path-scoped `git add`.

## 1. What this phase is

Four items, one QA drive:

1. **Grain buckets cut in the viewer's calendar** — today
   `DATE_TRUNC('month', col)` splits datetime columns at UTC
   boundaries, so a VN April starts 7h early; BG-2 fixed the labels,
   this fixes where the cut lands.
2. **Complete relation labels** — columns with >2000 distinct ids
   export raw ids (`MAX_LABEL_LOOKUP`); resolve labels for every id
   actually present instead.
3. **Records tile fetch cap** — a saved Records widget fetches its
   full 5000-row limit though the dashboard tile renders 200.
4. **Wizard escape carries Records state** — "Open in advanced
   builder" from the wizard's Records path opens Explore in Summary
   with the columns lost.

## 2. Binding non-goals

- No timezone selector UI (`env.user.tz` is the truth, per BG-2).
- No stored-data conversion; SQL expression + presentation only.
- Week-start semantics stay PostgreSQL's (`DATE_TRUNC('week')` =
  Monday); no locale week configuration.
- Snapshot recipient-tz (BG-2 D6) and the zero-dataset staging stay
  parked. No other biz_bi_cms edits beyond §4.4.

## 3. Design + facts

### 3.1 Grain cut (`models/bi_query_engine.py`)
Rule (extends BG-2's): a grain truncation of a **datetime** column is
computed on the viewer's local wall clock —
`DATE_TRUNC(grain, (col AT TIME ZONE 'UTC') AT TIME ZONE <user_tz>)`
— and the naive result IS the calendar label BG-2 already renders
un-shifted. **date** columns truncate as today (already calendar).
Requirements:
- tz string validated against pytz (reuse/extend `bi_tz.py`; invalid
  or missing → 'UTC'); passed as a bound SQL VALUE, never an
  identifier/format-string (trust-boundary rules at the file header).
- Every grain site: SELECT/GROUP BY (`_build_sql:357-361`), the
  drill-down `grain_overrides` path, compare requests, and any
  filter-on-truncated-value path — find them all; the expression must
  be identical everywhere in a query or GROUP BY breaks.
- Consistency with BG-2's relative windows (both now user-tz
  calendars): a `this_month` filter + month grain must select and
  bucket the same rows — add a test asserting exactly that at a
  near-boundary frozen instant.
- **Cache**: reader tz is already in the cache key (BG-2), so
  segregation is correct; add a migration that TRUNCATEs
  `bi_query_cache` on upgrade so no pre-BG-3 envelope (old cut) can
  be served inside its TTL. `post-` stage is fine (own table —
  §5.135 only forces `end-` for other modules' registries).
- **Gold**: VERIFY, don't assume, how `bi_gold.py`/silver views treat
  datetime columns. If the matview stores raw datetimes and grain is
  applied at query time, gold needs nothing (state that with the
  evidence). If any grain/truncation is baked at materialization,
  refresh affected matviews in the migration and say which.
- Cross-user semantics are per-viewer by design (same as "today");
  note it in the report, don't fight it.

### 3.2 Complete labels (`_attach_relation_labels`)
Replace the >`MAX_LABEL_LOOKUP` skip with chunked resolution of ALL
distinct ids present in the rows (chunks of 1000 via `search` so
record rules keep applying; accumulate `str(id) -> display_name`).
The existing row caps (5000 preview / `biz_bi.export_row_cap`) bound
the work. Keep the constant as the chunk size or delete it — no
silent skip remains. Perf guard: one test with ~2500 distinct
partners asserting completeness and a sane query count (no per-id
query).

### 3.3 Tile fetch cap (`/bi/query` + dashboard)
Dashboard batch entries for saved charts gain optional
`limit_override` (int). Server: honored ONLY when the chart's derived
request is detail mode AND `limit_override < saved limit` (a client
can shrink, never grow — same posture as `hard_cap`). Dashboard
sends 201 for Records widgets (200 rendered + 1 to detect overflow);
`meta.total_count` still powers the honest overflow row. Explore and
the wizard preview unchanged.

### 3.4 Wizard escape with state (`explore_action.js` + `report_wizard.js`)
Explore boot (`explore_action.js:91-98`) learns
`params.records_config = {columns: [field_ids], filters: [...]}`:
after `selectDataset`, seed `tableMode='records'`,
`chartType='table'`, recordColumns from metadata by field_id (drop
unknown ids silently), filters into the filter slots. The wizard's
records path passes it (chart path unchanged: `dataset_id` only).

## 4. Tests (full biz_bi suite must stay green — verbatim line)

1. Frozen instant month-boundary: row at `2026-03-31 18:00 UTC` lands
   in the VN viewer's April bucket and the UTC viewer's March bucket;
   labels agree with BG-2 rendering; date-column grain unchanged.
2. `this_month` filter + month grain congruence (§3.1).
3. Grain override (drill-down) uses the same tz cut.
4. Cache: VN and UTC viewers get different envelopes for the same
   request (existing key mechanics — assert via distinct results).
5. Labels: 2500-distinct completeness + chunking (§3.2); the
   unreadable-comodel fallback still holds.
6. `limit_override`: shrink honored in detail mode, grow ignored,
   aggregate ignored.
7. Records escape roundtrip: config in → Explore state (JS not unit-
   testable here — cover via QA evidence; server-side nothing new).

## 5. Deploy + report-back

Conventions §2 + §5.130, `-u biz_bi,biz_bi_cms`, vietuat. Migration
runs (cache truncate; gold action per §3.1 verification). Browser
evidence → `docs/strategy/reports/bi-grain-closeout-evidence/`:
month-grain chart as VN persona vs UTC persona with a staged
near-boundary row (clean up after); a Records dashboard tile network
request showing the 201 limit; wizard → Records list → escape →
Explore opens with the same columns in Records mode. Console logs;
fixtures cleaned + fresh-cursor verified (§5.128/§5.142). Report →
`docs/strategy/reports/bi-grain-closeout-report.md`: files,
deviations, verbatim green line, the gold verification result, new
gotchas (§5.163+). Self-review; commit on 19.0, push (`RHealth19`).

## Kickoff line

Implement the phase specified in docs/strategy/handovers/bi-grain-closeout.md.
