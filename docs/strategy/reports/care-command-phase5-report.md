# Care Command — Phase 5 "Surface Truth" — Implementation Report

**Module:** `health_care_command` → **19.0.4.0.0** (migration-triggering bump)
**Deployed:** vietuat · **By:** Opus (implementer) · Handover by Fable
**Kickoff:** `docs/strategy/handovers/care-command-phase5.md`

## 1. What was built (file list)

**Backend — `models/care_conversation.py`**
- `CHANNEL_SELECTION` (8 values: zalo/call/email/zns/whatsapp/fb/telegram/webchat)
  shared by all three channel fields; `MODE_TO_CHANNEL` map.
- Extended `channel_primary` to the 8-value Selection (meaning unchanged: last
  real traffic). New `channel_declared` (Selection, fill-never-overwrite),
  `channel_effective` (stored+indexed compute `channel_primary or
  channel_declared or False`, `@api.depends`), `has_channel_activity`
  (Boolean, indexed, default False).
- `_find_or_create_for`: create + update branches now set
  `has_channel_activity=True` whenever a `channel` key is present, and set
  `channel_declared` from a `declared_channel` key (create: set; update:
  fill-never-overwrite). `channel_primary` is **never** written from a lead.
- `get_workspace_data(view="attention")`: whitelisted view param
  (attention/leads/all, unknown→attention); channel filter + all counts moved
  to `channel_effective`; `_channel_keys()` hook; payload adds
  `active_channels`, `leads_count {total,needs}`, `view` echo.
- `_workspace_row`: `channel` = `channel_effective or "none"`, adds
  `channel_live` = `bool(channel_primary)`.
- `get_conversation_detail`: adds `channel_effective`.
- `_reply_templates`: keys off `channel_effective`.
- `_backfill_channel_truth()`: idempotent, returns a summary dict.

**Backend — `models/hooks.py`**: `CrmLeadHook._care_ingest_lead` passes
`declared_channel = MODE_TO_CHANNEL.get(lead.mode_of_contact)` (imported from
`care_conversation`). No `channel` key → no faked traffic.

**Migration** — `migrations/19.0.4.0.0/post-migration.py`: 5-line shim calling
the model method; logs per-channel breakdown.

**Frontend** — `static/src/js/care_command.js`, `.../xml/care_command.xml`,
`.../scss/care_command.scss`:
- Default `view: "chat"`; `_autoSelectInitial()` opens the topmost
  needs-mine (else needs-un) row after the first load only.
- Dock keys renamed to Selection values (`wa→whatsapp`, `tg→telegram`,
  `web→webchat`); `active` derived from payload `active_channels` via the
  `channels` getter; `--ch-*` scss vars renamed to match.
- Leads bucket on the wall (full-width strip, reachable even when attention is
  empty) and pinned under the chat list; leads-mode back affordance + header
  note both surfaces; `listView` state → server `view`.
- Declared-only glyph muted/hollow via `.ch-declared` (reduced opacity, no fill
  ring; mono/flat).

**Tests** — `tests/test_care_command.py`: T39–T46 added; T14 updated to read
`channel_effective`; T24/T25 updated for the attention-first default (see §3).

**i18n** — `i18n/vi.po`: new field labels (odoo-python) + Leads/bucket/header
strings (odoo-javascript) with the required markers (§5.58).

## 2. Test results (verbatim)

First run surfaced 2 pre-existing tests broken by the new default view (T24,
T25 — my new T39–T46 all passed); after the test-only fix, the re-run is fully
green (pid 1960100, 2026-07-22 00:37 UTC):

```
odoo.tests.result: 0 failed, 0 error(s) of 46 tests when loading database 'vietuat'
```

(46 = health_care_command + health_care_command_voip bridge + health_care_command_ai.)
Server healthy after restart: `/web/login` HTTP:200.

Backfill (log line, first deploy):
```
post-migration: care_command Phase-5 backfill: has_channel_activity set on 0
rows; channel_declared derived per channel = {'call': 167}
```

## 3. Deviations from the handover

1. **T24 + T25 updated (forced, beyond the "count-shape" sanction).** The
   handover sanctioned updating "tests that assert the 4-key counts shape". Two
   OTHER pre-existing tests also broke — not on counts, but because the new
   **attention-first default** (`view="attention"`) hides no-activity rows, and
   both tests' fixtures are lead-anchored/dormant (T24 searches a lead conv; T25
   creates cap+1 dormant rows). Fix: both now pass `view="all"`, preserving
   their original intent (search correctness / cap honesty). This is an
   unavoidable consequence of the default-screen change — declared, minimal.
2. No other deviations. AI patch seams (`.sendbtn`, `.crail-tabs`,
   `sendChannel`/`sendMessage`, the `@health_care_command/js/care_command`
   export) untouched; the AI bridge reads only `canReply`/`state.selected`.

## 4. Data honesty (post-backfill, vietuat)

- **167 conversations, 100% lead-anchored, 0 with real channel traffic.**
- Backfill flipped `has_channel_activity` on **0** rows (no traffic exists to
  flag) and derived `channel_declared` on **all 167** — every one `call`,
  because every existing lead's `mode_of_contact` sits at its default `phone`.
- Therefore **attention ≈ 0 / leads = 167**. This is HONEST and EXPECTED: the
  live surface will stay attention-empty until ops actually wires inbound
  channels (Zalo/email webhooks etc.). The Leads bucket now carries the 167 so
  they are one click away instead of flooding the wall.

## 5. Browser-check list for Fable (reviewer selective re-drive)

Open Care Command from the CMS sidebar (Care Intelligence → Care Command):
1. **Chat-first default** — lands on the chat screen (not the wall).
2. **Auto-select** — topmost *Needs reply — mine* row opens automatically;
   if none mine, topmost unclaimed; if attention is empty, "Pick a
   conversation" empty state (expected here since attention≈0).
3. **Leads bucket** — pinned "Leads · 167" row under the chat sections and a
   full-width strip on the wall; clicking switches to the leads view with a
   "← Live conversations / Live wall" back affordance + header note.
4. **Dock** — all 8 channels active; `fb`/`webchat` filters in the leads/all
   view return the backfilled declared leads (all declared `call` currently, so
   the **Calls** filter is the populated one on live data).
5. **Muted declared glyph** — leads render a hollow/faded channel glyph
   (declared, no traffic); real-traffic rows render solid (none live yet).
6. **AI module** — with AI on, the Draft button + brief card still patch in
   cleanly (seams unchanged).

## 6. Proposed ledger entries (§5)

- **§5.62 (proposed)** — *An attention-first default `view` silently hides every
  no-activity row, so any pre-existing test whose fixtures are lead-anchored or
  directly-created-without-`has_channel_activity` breaks even though it never
  touched the changed field.* Care-command Phase 5 flipped the default surface
  from "all open" to `has_channel_activity=True`; T24 (search) and T25 (cap)
  both RED-lit on the first run because their fixtures carry no activity and the
  new default excluded them. Fix the TEST (pass `view="all"`), not the engine —
  the default is correct. Rule: when a phase adds a default-narrowing domain
  clause to a workspace/list service, grep every existing test that calls it
  with no explicit scope and confirm its fixtures satisfy the new default.
