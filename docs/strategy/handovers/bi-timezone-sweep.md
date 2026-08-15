# Phase BG-2 handover — biz_bi timezone sweep (closes the BG-1 flags)

Stream: **BI hardening**, final phase. Prereq: BG-1 (`4c1a64dc`,
`b408fc5d`) — full biz_bi suite green on vietuat. Read
`docs/strategy/HANDOVER-CONVENTIONS.md` (ledger through §5.158 —
§5.107 caller-tz and the new BG-1 entries are the core context), then
`docs/strategy/reports/bi-green-suite-report.md` (the three flagged
tz defects and the `test_relative_filter` root cause), then this.
Sanction: `addons/biz_bi/**` + report/evidence paths + ledger appends.
Path-scoped `git add`.

## 1. What this phase is

BG-1 fixed Excel export datetimes but flagged three siblings it could
not touch. One rule, applied everywhere: **datetimes are STORED in UTC
and PRESENTED in the viewing user's timezone (`env.user.tz` server-side
/ the same tz client-side), and relative-date windows are computed in
that user tz then converted to UTC bounds before hitting UTC columns.**

1. **On-screen datetime display** — `formats.js` parses the engine's
   naive `YYYY-MM-DD HH:MM:SS` string with `new Date(...)`, which
   browsers treat as LOCAL time, so the screen shows the raw UTC
   wall-clock relabeled as local — screen and (correct) export
   disagree; near UTC midnight even the DATE is wrong on screen.
   Fix at the single `formatDimensionValue` choke point: treat the
   engine's naive datetime as UTC (append `Z` / parse as UTC) before
   locale formatting. Date-only values (grain truncations, date
   columns) must NOT shift — a `2026-08-14` date is a calendar date,
   not midnight UTC (classic off-by-one trap; test both).
2. **Relative-date windows** — the engine computes windows (`today`,
   `last_7_days`, `this_month`, …) in the CALLER's tz context
   inconsistently vs the UTC columns they filter (BG-1's
   `test_relative_filter` failed 22:00–24:00 UTC). Make it explicit
   in `_compile_filter_op`/the RELATIVE_RANGES resolution: window
   boundaries = user-tz calendar boundaries converted to UTC instants
   for datetime columns; plain calendar dates for date columns. "Today"
   for a VN user must mean VN-today. Pin with tests that force a tz
   (`with_context`/user tz) at a simulated near-midnight instant
   (freeze via a patched `fields.Datetime.now` or the module's own
   seam — no sleeping until midnight).
3. **Snapshot XLSX + schedule emails** — `_build_snapshot_xlsx` writes
   raw UTC datetimes; reuse the BG-1 export tz conversion (extract a
   shared helper rather than duplicating). ALSO: BG-1's create-path
   fix means dashboards created with `schedule_enabled=True` that
   NEVER sent will now start sending on the next cron run. Audit
   vietuat for such dashboards (`schedule_enabled=True` +
   `next_send` freshly backfilled + no prior snapshot audit rows) and
   report the list; do NOT mass-send surprises — if any exist, set
   their `next_send` to the next natural occurrence in the future
   (never a catch-up burst) and say exactly what you set.

## 2. Binding non-goals

- No API/config-shape changes, no biz_bi_cms edits, no ai_egress, no
  PWA. The >2000-distinct label lookup and widget fetch size stay
  deferred. No timezone SELECTOR UI — the user's Odoo tz is the truth.
- Do not convert stored data; presentation and window computation only.

## 3. Facts

- Export tz conversion (BG-1) lives in the controller layer — read it
  before extracting the shared helper. Engine `RELATIVE_RANGES` is
  mirrored JS↔python (RT-1 pinned the vocabulary). `formats.js`
  `formatDimensionValue` is the single client choke point (grain
  formats table at :73). Test superuser resolves to Europe/Brussels
  (§5.107). Full suite is green — keep it green (that's the gate now,
  no six-name comparisons).

## 4. Tests

Extend `tests/` (post_install): user-tz relative window at a frozen
near-midnight instant (datetime column) for at least `today`,
`last_7_days`, `this_month`; date-column windows unshifted; snapshot
xlsx datetime cell in user tz; a JS-side contract test is not feasible
here — cover the client fix via QA evidence (computed DOM text vs the
known UTC value for a VN-tz user). Full biz_bi suite green (verbatim
line).

## 5. Deploy + report-back

Conventions §2 + §5.130, `-u biz_bi`, vietuat. Evidence →
`docs/strategy/reports/bi-timezone-sweep-evidence/`: same record's
datetime shown on-screen (VN-tz persona) and in the export, matching;
a `today` filter at the current instant returning VN-today rows;
the schedule-audit list + what was set. Fixtures cleaned +
fresh-cursor verified. Report →
`docs/strategy/reports/bi-timezone-sweep-report.md`: files,
deviations, verbatim green line, the dashboard-schedule audit result,
new gotchas (§5.159+). Self-review; commit on 19.0, push (`RHealth19`).

## Kickoff line

Implement the phase specified in docs/strategy/handovers/bi-timezone-sweep.md.
