# Care Command — Phase 5 Handover: "Surface Truth" (lead channel honesty · attention-first surface · chat-first default)

**For:** Opus implementation session · **Designed/reviewed by:** Fable
**Read first:** `docs/strategy/HANDOVER-CONVENTIONS.md` (§5.45, §5.48, §5.50–5.61)
**Module:** `health_care_command` core only → version **19.0.4.0.0** (a version bump that
triggers a migration — see §6). No new module this phase.
**Prior phases:** P1–P4 live on vietuat, all reviewed (core 19.0.3.0.0, voip bridge
19.0.1.1.0, AI module 19.0.1.0.1).

## 1. Why this phase (user-observed defects, verified)

Live use surfaced three problems:

1. **167 channel-less lead cards flood the wall.** `CrmLeadHook._care_ingest_lead`
   (models/hooks.py:93-103) sends a signal with **no `channel` key**, so `channel_primary`
   stays NULL. Every dock icon filters `channel_primary = 'x'`
   (care_conversation.py:467) → 0 rows; "ALL" shows everything. As lead volume grows, the
   live surface drowns in dormant leads.
2. **Wrong default screen.** The action opens on the wall (`state.view: "wall"`,
   care_command.js:47) with no auto-selection; the user wants the chat screen first with
   the topmost **Needs reply — mine** conversation already open.
3. **Half the dock is dead.** `wa/fb/tg/web` are `active: false` placeholders
   (care_command.js:16-19) with no Selection values behind them.

User decisions (binding): derive a channel from the lead's `mode_of_contact` **without
faking traffic**, make the default surface attention-based with dormant leads collapsed
behind a "Leads" bucket, default to the chat screen, and wire all 8 dock channels (the 4
new Selection values land NOW so Phase 6's adapters need no selection_add).

## 2. Scope (deliverables)

### 2.1 Channel truth model (three fields, one principle: never fake traffic)

On `care.conversation` (care_conversation.py):

- **Extend `channel_primary`** (:63-66) with `("whatsapp", "WhatsApp"), ("fb", "Messenger"),
  ("telegram", "Telegram"), ("webchat", "Web chat")`. Its meaning is UNCHANGED: last real
  inbound/outbound traffic. Only hooks that pass `channel` in the signal ever write it
  (verified: zalo/email hooks + voip bridge do; CrmLeadHook does not).
- **New `channel_declared`** — same Selection (all 8 values). "How the lead SAID they
  contacted us" — derived from `crm.lead.mode_of_contact`, never from traffic.
- **New `channel_effective`** — same Selection, `compute="_compute_channel_effective"`,
  `store=True, index=True`, `@api.depends("channel_primary", "channel_declared")`:
  `channel_primary or channel_declared or False`. **All dock filtering + channel counts
  move to this field.**
- **New `has_channel_activity`** — Boolean, default False, index=True. True the moment any
  signal carrying a `channel` key touches the conversation. This is the attention/leads
  discriminator (NOT channel_primary NULL-ness, which backfill would pollute).

### 2.2 Upsert + hook changes

- `_find_or_create_for` (:288-378): new signal key **`declared_channel`**.
  - Create branch (:313-328): `if channel:` also set `has_channel_activity = True`;
    `if signal.get("declared_channel"):` set `channel_declared`.
  - Update branch (:330-377): `if channel:` (existing :351-352) also
    `upd["has_channel_activity"] = True`; declared is **fill-never-overwrite**:
    `if signal.get("declared_channel") and not rec.channel_declared`.
- `CrmLeadHook._care_ingest_lead` (hooks.py:93-103): add the mapping and pass
  `"declared_channel": MODE_TO_CHANNEL.get(lead.mode_of_contact)` in the signal.
  ```python
  MODE_TO_CHANNEL = {
      "phone": "call", "zalo": "zalo", "email": "email",
      "facebook": "fb", "website": "webchat", "chatbox": "webchat",
      # walk_in: no channel — stays None
  }
  ```
  `mode_of_contact` Selection verified at health_crm/models/crm_lead.py:530-535 (values
  phone/zalo/facebook/email/website/chatbox/walk_in, default "phone"). Keep the existing
  early return when the lead has neither phone nor email (hooks.py:97-98) — unchanged.
- No other hook changes. The zalo/email/voip hooks are correct as-is (their `channel` key
  now additionally flips `has_channel_activity` via the upsert).

### 2.3 Workspace service (`get_workspace_data`, :458-535)

- New param **`view="attention"`** (`"attention" | "leads" | "all"`):
  - `attention` (default): `list_domain += [("has_channel_activity", "=", True)]`
  - `leads`: `[("has_channel_activity", "=", False)]`
  - `all`: no clause.
- Channel filter (:467) moves to **`channel_effective`**.
- Counts (:488-502): replace the hard-coded tuple with a new hook
  ```python
  @api.model
  def _channel_keys(self):
      return ("zalo", "call", "email", "zns", "whatsapp", "fb", "telegram", "webchat")
  ```
  and `_read_group` on **`channel_effective`** (both total and needs passes). Channel
  counts stay computed over the full `open_domain` (view-agnostic — the dock badge answers
  "how much traffic exists", not "how much is in the current view").
- Payload additions:
  - `"active_channels": list(self._channel_keys())` (Phase 6 overrides `_channel_keys` to
    reflect connected adapter accounts; in Phase 5 all 8 are filterable),
  - `"leads_count": {"total": …, "needs": …}` — search_counts over
    `open_domain + [("has_channel_activity", "=", False)]` (and `+ status=needs_reply`),
  - `"view": view` (echo, so the UI state can't drift from the server's).
- `capped`/`total` (:483-484, :524-525) automatically stay per-view honest since
  `list_domain` includes the view clause — no change needed, but T-test it.

### 2.4 Row/detail payloads

- `_workspace_row` (:549-571): `"channel"` becomes `self.channel_effective or "none"`
  (the "none" fallback + neutral-glyph comment at :554-556 stays true for
  walk-in/unmapped leads); ADD `"channel_live": bool(self.channel_primary)` so the UI can
  distinguish real traffic from declared-only.
- `get_conversation_detail` (:618-636): add `"channel_effective": rec.channel_effective
  or "none"` alongside the existing `channel_primary` key. Capabilities dict UNCHANGED
  (send routing keeps its email/zalo logic this phase — a declared-fb lead with an email
  still honestly says "Sends via Email"; adapters come in Phase 6).
- `_reply_templates` (:639-643): key off `self.channel_effective or "any"` instead of
  `channel_primary` (a declared-zalo lead should get zalo chips). One-line change.
- `_snippet` (:591-615) unchanged (declared-only leads simply return "").

### 2.5 Migration/backfill (the 167 existing conversations)

New `addons/health_care_command/migrations/19.0.4.0.0/post-migration.py` calling ONE
idempotent model method (put the logic in the model so it's unit-testable — the migration
file itself is a 5-line shim building an Environment and calling it):

```python
@api.model
def _backfill_channel_truth(self):
    # 1. real traffic → has_channel_activity
    self.sudo().search([("channel_primary", "!=", False),
                        ("has_channel_activity", "=", False)]) \
        .write({"has_channel_activity": True})
    # 2. lead-anchored, no declared channel yet → derive from mode_of_contact
    for conv in self.sudo().search([("lead_id", "!=", False),
                                    ("channel_declared", "=", False)]):
        declared = MODE_TO_CHANNEL.get(conv.lead_id.mode_of_contact)
        if declared:
            conv.write({"channel_declared": declared})
```
(Loop is fine at this scale — ~170 rows; a read_group-batched write is acceptable too.)
`channel_effective` is stored-computed → Odoo computes it for all rows when the field is
added at upgrade; the backfill writes then trigger recompute via depends. Report the
backfill result counts per declared channel (§7 report-back).

### 2.6 UI — chat-first, attention-first, honest glyphs (care_command.js + care_command.xml + scss)

- **Default screen**: `view: "chat"` (care_command.js:47). The wall stays one click away
  via the existing wall button / `toWall()` (:282-286).
- **Auto-select**: after the FIRST successful `load()` (onWillStart path :76-78 — not the
  60 s poll :81, not after user actions), if `state.view === "chat"` and nothing is
  selected: select `sectionRows("needs_mine")[0]` else `sectionRows("needs_un")[0]`
  (grouping :239-252; rows already arrive in `_order` = urgency desc, last_event desc, so
  index 0 IS the topmost). If both empty, keep the current "Pick a conversation" empty
  state. Use `selectConv(id)` (:287-291).
- **View toggle (Leads bucket)**: new state `listView: "attention"` passed as `view` to
  the server (:102-106). Two surfaces:
  - Wall: a collapsed bucket strip/tile at the end of the wall — "Leads · N" (N =
    `leads_count.total`, with the needs sub-count) — clicking it switches
    `listView = "leads"` (reload); in leads mode show a clear "← Live wall" affordance
    and a header note that these are contacts not yet reached on any channel.
  - Chat list: same collapsed "Leads · N" row pinned under the live sections; clicking
    swaps the list to the leads view with the same back affordance. (Sections logic
    :239-252 is untouched — leads-view rows still group by status.)
- **Dock**: rename keys to server values — `wa→whatsapp`, `tg→telegram`, `web→webchat`
  (`fb` already matches) at care_command.js:16-19 — the dock key is passed VERBATIM as
  the channel filter (:103) and matched against `_workspace_row().channel`, so keys MUST
  equal Selection values. `active` now derives from the payload's `active_channels`
  (keep the static array for label/icon/color; compute activation in a getter). All 8
  are active in Phase 5. Update the 4 CSS vars if the renamed keys are referenced in
  scss/xml (`--ch-wa` etc. — grep and align).
- **Declared-only glyph**: where tiles/rows render the channel glyph, add class
  `ch-declared` when `!c.channel_live` → muted/hollow treatment in scss (reduced opacity
  + no fill ring; mono, flat — per the standing mono-colors rule). Real traffic renders
  exactly as today.
- **AI-module seams are load-bearing**: `care_command_ai.xml` xpaths target
  `//button[hasclass('sendbtn')]` and `//div[hasclass('crail-tabs')]`, and
  `patch(CareCommand.prototype)` imports from `@health_care_command/js/care_command`.
  Do NOT rename those classes, the export, or the patched method names
  (`sendChannel`/`sendMessage` stay as-is this phase).

## 3. Binding NON-goals

- **No adapters, webhooks, or send-path changes** — Phase 6. The composer's zalo/email
  logic (care_command.js:408-446, care_conversation.py:631-634) is untouched.
- **`channel_primary` is never written from a lead** — declared ≠ traffic, permanently.
- **No urgency re-scoring** (`_compute_urgency_score` untouched), no wall re-ranking, no
  AI, no core AI-purity violation (grep AI = 0 stays).
- **No zalo webhook repair** (§5.61 documents the trap; repairing health_zalo is a
  separate future item — do not touch it here).
- No new menus/actions; no PWA involvement; no health_crm edits (read
  `mode_of_contact` only).

## 4. Verified plumbing (do not re-derive; cite these in your report)

- `channel_primary` Selection :63-66; anchors + `init()` partial-unique precedent
  :46-57/:113-123; `_check_anchor` :125-138.
- `_find_or_create_for` :288-378 (create :313-328, update :330-377, channel overwrite
  :351-352, `_resolve_unread` :380-389).
- `get_workspace_data` :458-535 (channel filter :467, mine :468-471, search :472-482,
  cap :483-484, hard-coded counts tuple :488, team :504-520, payload :522-535).
- `_workspace_row` :537-571 (`"channel"` :556); `_reason_line` :573-589; `_snippet`
  :591-615; `get_conversation_detail` :618-636; `_reply_templates` :639-643.
- Hooks: CrmLeadHook :80-103 (savepoint wrapper :86-90, early return :97-98);
  MailMessageHook hot-path guard :112-118; zalo hook passes `channel: "zalo"`
  (hooks.py:48-65); voip bridge passes `channel: "call"`
  (health_care_command_voip/models/hooks.py:67-98).
- JS: CHANNELS :11-20, LIST_SECTIONS :23-29, state init :44-66, load() :99-119 (params
  :102-106), getters :214-237, sectionRows :239-252, tileClass :258-264, chan() fallback
  :266-271, navigation :276-309.
- `crm.lead.mode_of_contact` health_crm/models/crm_lead.py:530-535;
  `contact_status` :312-318.
- AI patch seams: health_care_command_ai/static/src/js/care_command_ai.js:11-13; xml
  xpaths on `.sendbtn`/`.crail-tabs`.

## 5. Safety rails

- All new service params validated server-side (`view` whitelist → default to
  "attention" on unknown values; never interpolate into domains).
- Backfill is idempotent (re-running writes nothing new) and touches ONLY the two new
  fields — never `channel_primary`, never status/unread/owner.
- §5.55: hook edits stay inside the existing savepoint wrappers. §5.56: if a test needs
  tracking flushed, use the existing `_flush_tracking` helper. §5.57: `_read_group`
  returns tuples. §5.60: no local named `context`.
- vi.po: every new user-visible string gets `#. odoo-python` / `#. odoo-javascript`
  markers (§5.58) — including "Leads", the bucket labels, and the leads-view header note.

## 6. Tests (extend tests/test_care_command.py; TransactionCase only, continue stream numbering)

- **T39 declared derivation**: lead created with `mode_of_contact="facebook"` + phone →
  conversation has `channel_declared="fb"`, `channel_effective="fb"`,
  `channel_primary=False`, `has_channel_activity=False`. A `walk_in` lead →
  all three channel fields falsy.
- **T40 traffic wins**: same conversation receives a zalo inbound signal →
  `channel_primary="zalo"`, `channel_effective="zalo"`, `has_channel_activity=True`;
  `channel_declared` unchanged ("fb"). Declared never overwrites back.
- **T41 view domains**: one traffic conversation + one declared-only lead →
  `get_workspace_data()` (default) lists only the traffic one and
  `leads_count == {"total": 1, "needs": 1}`; `view="leads"` lists only the lead;
  `view="all"` lists both; unknown view value behaves as attention.
- **T42 filter on effective**: `channel="fb"` returns the declared-only lead;
  `channel_counts["fb"]["total"] >= 1` (counts read channel_effective).
- **T43 payload contract**: `active_channels` contains all 8 keys; counts dict has all 8;
  `view` echoed; row payload for the declared-only lead has `channel="fb"`,
  `channel_live=False`; after traffic `channel_live=True`. (Assert enum keys, not labels
  — §5.50.)
- **T44 backfill**: create legacy-shaped rows via ORM (a lead-anchored conversation with
  `channel_declared=False`, and a conversation with `channel_primary="zalo"`,
  `has_channel_activity=False` written directly), run `_backfill_channel_truth()` →
  derived/flag values correct; run it AGAIN → no further writes (idempotent).
- **T45 templates via effective**: declared-zalo lead (no traffic) →
  `_reply_templates()` returns zalo + "any" chips.
- **T46 cap honesty per view**: with WORKSPACE_CAP monkeypatched low (addCleanup-pinned,
  §5.32-style hygiene), the leads view reports `capped=True/total` for the leads set,
  independent of the attention set.
- Update any existing tests that assert the 4-key counts shape.
- JS behaviors (chat-first default, auto-select, bucket toggle, muted glyph) are
  Fable-browser-QA items — do not attempt JS unit tests.

## 7. Deploy (vietuat — §5.45) & report-back

1. Standard flow (scp → /tmp → sudo cp/chown; stop service first — §5.45 no concurrent
   odoo-bin). Module: `-u health_care_command`. Version 19.0.4.0.0 (the migrations/
   folder must sit under the NEW version number or it won't run).
2. One test run: `--test-enable --test-tags /health_care_command,/health_care_command_voip,/health_care_command_ai --stop-after-init --no-http --workers 0`
   (bridge + AI suites guard against regressions from the payload changes). Quote YOUR
   run's pid + fresh TODAY-UTC result line (§5.45 log-rotation trap).
3. Verify the migration ran: log line + psql counts of
   `channel_declared`/`has_channel_activity` (report the per-channel breakdown of the
   ~167 backfilled rows).
4. Report per template: deviations, data honesty (how many conversations are
   attention vs leads after backfill — expect attention ≈ 0 until ops wires channels,
   which is HONEST and expected; say so plainly), proposed ledger entries, and the
   browser-check list for Fable (default chat screen + auto-selected needs-mine row,
   Leads bucket counts, fb/webchat dock filters returning the backfilled leads, muted
   declared glyphs, AI module still patching cleanly).

**Kickoff line for the Opus session:**
Implement `docs/strategy/handovers/care-command-phase5.md` (Care Command Phase 5 —
Surface Truth: channel_declared/channel_effective/has_channel_activity truth model +
mode_of_contact derivation + backfill migration, attention-first workspace with Leads
bucket, chat-first default screen with needs-mine auto-select, all-8 dock wiring). Read
`docs/strategy/HANDOVER-CONVENTIONS.md` first (§5.45, §5.48, §5.50–5.61). Follow the
handover exactly: never write channel_primary from a lead, keep the AI-module patch
seams intact, T39–T46 green plus updated count-shape tests, deploy to vietuat per §7,
report deviations + backfill counts. No adapters/webhooks/send changes (Phase 6), no
zalo webhook repair, no credential changes.
