# Phase AH-3 handover — Analytics Hub polish + hardening (final)

Stream: **Analytics Hub**. Prereqs: AH-1 (`4ac63f38`) + AH-2 (`7f24d50c`)
live on vietuat. Read `docs/strategy/HANDOVER-CONVENTIONS.md` (now
including §5.127–§5.130), then both phase reports
(`docs/strategy/reports/analytics-hub-phase{1,2}-report.md`), then this.

## 1. What this phase is

Close every open item from the two reports and finish the stream:

1. **AI for creators** — the wizard's AI box is currently hidden from
   its entire target audience (probe honestly answers False because
   `bi.ai.provider` ACL starts at `group_bi_modeler`).
2. Two flagged `biz_bi` core fixes (narrow, sanctioned below).
3. **Writable-dashboard targeting** in wizard step 3 (today the UI
   catches AccessError after the fact).
4. **Recents hygiene** — `get_hub_data` recents can reference deleted /
   inaccessible dashboards.
5. **First-run + degraded states** — no published datasets, zero
   dashboards anywhere, empty workspace grid.
6. **Pixel-level polish pass** over hub + wizard (multiple iterations,
   computed-style driven, both `en` and `vi_VN` sessions).
7. Final vi.po sweep + evidence + reports.

## 2. Binding non-goals

- NO new features beyond the list above: no compose_report surface, no
  chart editing in the wizard, no dashboard management UI, no sharing,
  no TV mode, no workspace admin.
- NO ACL widening on `bi.ai.provider` (the fix is sudo-scoped lookup,
  §4.1 — API keys and provider rows must remain unreadable to
  creators).
- Sanction list: `addons/biz_bi_cms/**`, the report/evidence paths,
  ledger appends in `docs/strategy/HANDOVER-CONVENTIONS.md`, and in
  `addons/biz_bi` ONLY the two exact edits of §4.1/§4.2 — nothing else
  in biz_bi, nothing in any other module. Path-scoped `git add` (other
  sessions' unstaged changes are present).

## 3. Verified plumbing facts (do not re-derive)

- Probe chain: `bi.ai.is_available()` (`biz_bi/models/bi_ai.py:262-265`)
  → `env['bi.ai.provider'].get_default()` (`:111-123`) → `_is_usable()`.
  `nlq_chart` (`:267-277`) does `dataset.check_access('read')` as the
  real user FIRST, then `_complete_validated` → `_complete` (`:125`)
  which re-resolves the provider via `get_default()` and reads
  `_api_key()` server-side only; the RPC returns only the validated
  config. AI calls are audit-logged via `_log` (`:440`).
- `biz_bi_cms/models/bi_ai.py` (AH-1) already overrides
  `is_available()` to catch AccessError → False. After §4.1 that catch
  becomes vestigial but harmless — keep it as defense-in-depth.
- Explore's unguarded probe: `explore_action.js:88-90` —
  `this.orm.call("bi.ai", "is_available", []).then(...)` with no
  `.catch` (§5.127c).
- "Can edit this dashboard" is already computed server-side:
  `bi_dashboard.py:213-216` — `(owner_id == user AND has creator) OR
  has modeler` — reuse this exact predicate for the writable list; do
  not invent a second definition.
- Recents source: `bi.audit.log.get_recents()`
  (`bi_audit_log.py:57-72`), raw SQL over dashboard_view events — it
  does NOT check the dashboard still exists or is readable.
  `get_hub_data` (biz_bi_cms `models/bi_workspace.py`) passes it
  through.
- Wizard/hub component + style layout: see the AH-2 report file list.
  Relative-range vocabulary is shared JS↔python
  (`test_01b_relative_range_vocabulary_is_shared` pins it).
- vi strings: `i18n/vi.po` has 79 entries, loader-verified. Vietnamese
  labels run ~30-40% longer than English — the pixel pass must be
  driven in BOTH languages.
- §5.130 applies to every deploy in this phase: check for concurrent
  odoo-bin runs before `service stop`; a 502 burst during browser QA
  may be another session's restart — re-drive, don't misattribute.

## 4. Build spec

### 4.1 AI for creators (`addons/biz_bi/models/bi_ai.py` — sanctioned edit 1)
In `is_available()` and in `_complete()` (the two `get_default()` call
sites), resolve the provider as
`self.env['bi.ai.provider'].sudo().get_default()`, each with a one-line
comment: provider config is server-side infrastructure; invoking AI
must not require reading provider records. NOTHING else changes:
`nlq_chart`'s `dataset.check_access('read')` stays as the real user,
the ACL table is untouched, responses still return only validated
configs, `_log` still records. If `_log`/`get_recents`-style
attribution would record the superuser because of the sudo scope,
keep attribution on the REAL user (check how `_log` derives the user;
scope the sudo to the provider recordset only, never `self`).
Result to verify live: a plain creator sees the AI box and a real
`nlq_chart` round-trip succeeds (AH-2 proved the provider works).

### 4.2 Explore probe guard (`addons/biz_bi/static/src/components/explore/explore_action.js` — sanctioned edit 2)
Append `.catch(() => { this.state.aiAvailable = false; })` to the
`is_available` probe at `:88-90`. One-liner; no other Explore changes.

### 4.3 Writable dashboards (biz_bi_cms)
Thin `@api.model` helper on `bi.dashboard` (in biz_bi_cms):
`get_wizard_targets()` → `[{id, name}]` of dashboards the user may add
to, computed with the SAME predicate as `bi_dashboard.py:213-216`
(record-rule-visible AND (owner+creator OR modeler)). Wizard step 3
uses it instead of the raw `searchRead`; keep the AccessError catch as
a fallback. If the list is empty, preselect "New dashboard".

### 4.4 Recents hygiene (biz_bi_cms `get_hub_data`)
Filter recents to dashboard ids that still exist AND are visible under
record rules (one `search` on the collected ids); drop the rest. Test
covers a deleted and a foreign-workspace dashboard.

### 4.5 First-run + degraded states
- Hub, zero dashboards anywhere (fresh tenant): the workspace grid
  collapses to a single friendly first-run card — short copy + the
  Create Report CTA (creator) or "Ask your administrator to set up
  Analytics" (non-creator).
- Wizard step 1, zero published datasets: empty state with honest copy
  ("No data sources are published yet") instead of a blank grid; CTA
  disabled from the hub is NOT acceptable — the hub CTA stays enabled
  and the wizard explains.
- Verify (don't rebuild) the AH-1 AccessError fallback still renders.

### 4.6 Pixel polish pass (the WOW pass — iterate, don't one-shot)
Run at least THREE audit→fix→re-audit cycles with chrome-devtools on
care.biztinct.com, per the pixel-validation discipline:
- Surfaces: hub landing (full grid, search-active, recents), wizard
  steps 1/2/3 (including AI box visible, grain chips, disabled gallery
  tooltips, preview loading/empty/error), first-run card.
- Checks per cycle (evaluate_script computed styles + screenshots):
  spacing rhythm (consistent 8px-multiple paddings/gaps), alignment
  (card grids, chip rows, step indicator), typography hierarchy,
  color/contrast (WCAG AA on all text incl. muted captions and
  disabled states), border-radius consistency, hover/focus-visible
  states on every interactive element, skeleton fidelity.
- Both languages: repeat key screens under `vi_VN` (longer strings must
  not wrap ugly, truncate with title-attr where needed).
- Two widths minimum: ~1440 desktop and ~1024 narrow; the wizard must
  remain fully usable at 1024.
- Keyboard: the wizard is operable by Tab/Enter/Escape (Escape closes;
  focus lands on step content on advance). No custom trap framework —
  sensible tabindex + autofocus is enough.
- Log each cycle's findings + fixes in the evidence pack (before/after
  screenshots).

### 4.7 i18n + ledger + docs
- vi.po: cover every new string; re-verify with the loader.
- Append any new gotcha to the ledger (§5.131+).
- Update `addons/biz_bi_cms/__manifest__.py` description if the module
  summary drifted. Version bump to `19.0.1.2.0` + migration dir only
  if a data/schema step needs it (none is expected — say so in the
  report if you skip it).

## 5. Tests (extend biz_bi_cms tests, tag `post_install`)

1. `test_ai_available_for_creator` — a plain creator (no modeler) gets
   `is_available() == True` when a usable provider exists; False when
   none. (Fixture: create a provider in-test; check how AH-2's AI tests
   fixture it, or mock `_is_usable`.)
2. `test_nlq_permission_shape` — as a creator, `nlq_chart` on a dataset
   they may read does NOT raise AccessError at the provider layer
   (mock `_complete_validated` to avoid a live LLM call); on a dataset
   they may NOT read it raises before any provider access.
3. `test_wizard_targets` — owner-creator sees own + open dashboards,
   not a foreign member-scoped one; modeler sees all; predicate matches
   `can_edit` semantics.
4. `test_recents_pruned` — a deleted dashboard id and a foreign one are
   absent from `get_hub_data()['recents']`.
5. Existing 13 tests still green.

## 6. Deploy + report-back

- Deploy per conventions §2 with §5.130's concurrent-run check;
  upgrade set is `-u biz_bi_cms,biz_bi` (biz_bi has a py+js edit).
  Verbatim `odoo.tests.result` lines for BOTH modules' test tags —
  biz_bi's own suite must stay green after §4.1/§4.2.
- Browser evidence pack →
  `docs/strategy/reports/analytics-hub-phase3-evidence/`: (a) creator
  persona sees + successfully uses the AI box end-to-end (the AH-2
  blocked screenshot now unblocked); (b) writable-targets list vs the
  old full list; (c) first-run card on a persona with an empty slate
  (fixture workspace, then cleaned per §5.34/§5.128 — remember audit
  rows need the scoped DELETE); (d) the three pixel cycles with
  before/after shots incl. `vi_VN` and 1024px; (e) console logs per
  screen. Fixtures deleted + fresh-cursor verified.
- Report → `docs/strategy/reports/analytics-hub-phase3-report.md`
  (committed): file list, deviations, verbatim test lines, pixel-cycle
  changelog, confirmation the sudo scope leaks nothing (what the RPC
  returns for a creator), anything deferred, new gotchas.

## Kickoff line

Implement the phase specified in docs/strategy/handovers/analytics-hub-phase3.md.
