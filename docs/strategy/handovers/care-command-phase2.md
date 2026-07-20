# Care Command — Phase 2 Handover: "Live Channels" (Zalo send repair + VoIP on Odoo 19 + workspace hardening)

**For:** Opus implementation session · **Designed/reviewed by:** Fable
**Read first:** `docs/strategy/HANDOVER-CONVENTIONS.md` (whole ledger; §5.45, §5.51–5.55 are from this stream)
**Phase-1 spec (context + verified plumbing you may reuse):** `docs/strategy/handovers/care-command-phase1.md`
**Phase-1 state:** `health_care_command` 19.0.1.0.1 live on vietuat, 0 failed of 17, reviewed PASS-WITH-FIXES (fixes shipped in 469c7f44).

## 1. Why this phase

Phase 1 shipped the unified work layer, but on vietuat the wall runs on 167 lead-anchored
conversations only: outbound Zalo is broken **upstream** (unregistered `zalo.api.client` model,
ledger §5.54), and `health_voip24h` cannot even install on Odoo 19 (removed
`res.groups.category_id`). Phase 2 lights up the channels: repair the Zalo send seam, make VoIP
installable and ingested, and harden the workspace paths the Phase-1 review flagged as
scale/concurrency debt.

## 2. Scope (deliverables)

1. **health_zalo send repair** (upstream fix — explicitly IN scope this phase, exactly two sites):
   replace `self.env['zalo.api.client']` with the real service seam.
2. **health_voip24h Odoo-19 compatibility** so it installs on vietuat.
3. **New bridge module `health_care_command_voip`** (`auto_install: True`, depends
   `[health_care_command, health_voip24h]`): the `voip.call.log` ingestion hook + call backfill.
   `health_care_command` itself keeps VoIP as a soft dependency (D1 stays).
4. **Workspace hardening in health_care_command:** airtight claim guard, `read_group` counts,
   wire the chat-list search box, complete vi.po (incl. JS/QWeb strings).
5. Tests T18–T25; deploy to vietuat per §7.

## 3. Binding NON-goals

- **NO behavior change in health_zalo beyond the two model-lookup sites** (§4.1). No API-shape,
  webhook, token, or template changes. No edits to `zalo_api.py` itself.
- **NO real outbound message to any real customer.** Zalo send is proven by unit tests with
  `requests.request` mocked. If `zalo.config` on vietuat has no connected OA (expected), report
  that; do NOT create/modify any config/credential/webhook record.
- **NO VoIP credential/webhook setup.** Make the module install and the hook ingest; whether a
  VOIP24h account is wired is an ops matter — report the `voip.config` state honestly.
- **NO AI, NO clinical content, NO new channels (WhatsApp/FB/TG/webchat stay disabled)** — all
  Phase-1 §3 rails remain in force.
- **NO composer templates / watchlist / supervisor ticker** — Phase 3.
- Sidebar/menu stay ungated (parity with `item_crm_dashboard` — accepted Phase-1 review LOW-4).

## 4. Verified plumbing (do not re-derive)

### 4.1 Zalo send break (§5.54) — the exact fix
- `addons/health_zalo/models/zalo_message.py:166` — `api_service = self.env['zalo.api.client']`
  inside `action_send_message()`; then calls `api_service.send_text_message(self.conversation_id.config_id, message_data)`
  and `api_service.send_image_message(...)`.
- `addons/health_zalo/models/zalo_config.py:288` — same lookup inside `action_test_connection()`,
  then `api_service.get_oa_profile(self)`.
- The real seam: `get_api_client(env)` at `addons/health_zalo/services/zalo_api.py:354` returning
  `ZaloAPIClient` (plain class, `__init__(self, env)`). Method signatures match the call sites:
  `send_text_message(self, config, message_data)` (:182), `send_image_message(self, config, user_id, image_url)` (:195).
- Import precedent: `addons/health_zalo/services/token_manager.py:4` does
  `from .zalo_api import get_api_client`. From `models/`, use
  `from ..services.zalo_api import get_api_client`.
- **Fix = at both sites:** `api_service = get_api_client(self.env)`. Nothing else. Note
  `action_send_message` already wraps everything in try/except → `state='failed'` +
  `error_message` + UserError re-raise — keep that intact.

### 4.2 VoIP O19 break
- `addons/health_voip24h/security/voip24h_security.xml:14` and `:23` set
  `<field name="category_id" ref="module_category_voip24h"/>` on `res.groups` — the field was
  removed in Odoo 19. **Both records ALREADY carry
  `privilege_id ref="health_base.res_groups_privilege_healthcare"`** (:15, :24) — the modern
  pattern, same as `health_crm/security/health_crm_security.xml:14`. Fix = delete the two
  `category_id` lines (keep the `ir.module.category` record — harmless, minimal diff).
- Views scanned: **no `attrs=`, no `states=`, no `<tree`** anywhere in `health_voip24h/views/` —
  but the module has never loaded on O19, so install may surface more breaks. Fix each one
  minimally + additively, and LIST every extra change in your report (do not silently adapt).
- `voip.call.log` field map + webhook chain: Phase-1 handover §4 (voip.call.log :17,:46,:52,:66,
  :166,:172; call_handler.py:67, :202-206 popup bus).

### 4.3 What already lights up by itself
The Phase-1 code reads VoIP defensively via `if 'voip.call.log' in self.env` at
`health_care_command/models/care_conversation.py:611` (timeline) and in the backfill
(`health_care_command/hooks.py`). The moment the model exists, timeline + backfill work.
**Only live ingestion is missing** — that is the bridge module's hook.

### 4.4 Phase-1 seams you will extend
- Hook pattern to clone: `health_care_command/models/hooks.py` — super() first, then
  `try: with self.env.cr.savepoint(): ... except Exception: _logger.exception(...)` (§5.55 —
  MANDATORY, the savepoint is not optional).
- Upsert: `care.conversation._find_or_create_for(anchor, signal)`
  (`models/care_conversation.py:250`) — anchors `partner_id`/`lead_id`/`phone_normalized`;
  signal `missed_call: True` sets the sticky flag; `set_status='waiting'` clears missed+unread.
- Backfill: the single logged helper in `health_care_command/hooks.py` (log line
  `care_command backfill: created zalo=… call=… email=… lead=…`) — already call-aware and
  idempotent; the bridge `post_init_hook` re-invokes it (creates the call-leg records).
- Claim: `action_claim` at `models/care_conversation.py:763-785` (search-then-write — replace
  per §5.3 below).
- Workspace: `get_workspace_data` `models/care_conversation.py:407-427` (uncapped ORM loops —
  replace per §5.4).

## 5. Design

### 5.1 Bridge module `health_care_command_voip`
```
health_care_command_voip/
  __manifest__.py    # auto_install: True, depends [health_care_command, health_voip24h],
                     # post_init_hook re-running the existing backfill
  models/hooks.py    # VoipCallLogHook(_inherit='voip.call.log') create-hook
  tests/             # T21, T22
```
Hook rules (mirror the Phase-1 hooks exactly, incl. savepoint):
- Anchors: `partner_id`, `lead_id`, `phone_normalized` = the log's normalized caller number.
- Incoming missed/abandoned → signal `{channel:'call', inbound:True, set_status:'needs_reply',
  missed_call:True, unread:'keep', event_at:call_date}`.
- Incoming answered → `{channel:'call', inbound:True, event_at:call_date, unread:'keep'}` —
  no status change (an answered call is not awaiting a reply; don't invent state).
- Outgoing → `{channel:'call', inbound:False, set_status:'waiting', unread:'zero'}` (the
  upsert's waiting branch clears `missed_call_unhandled`).
- No live-ringing wall hero this phase (the popup bus exists in health_voip24h already;
  forwarding it to the wall is Phase 3 with the ticker). Do not touch call_handler.

### 5.2 Zalo send repair — tests prove the wiring
With `unittest.mock.patch('requests.request')` (the only HTTP seam in `_make_request`):
success JSON → `action_send_message()` ends `state='sent'` with `zalo_message_id` stored;
non-200/exception → `state='failed'`, `error_message` set, `UserError` raised. Token retrieval
(`config.get_valid_token`) must also be mocked/stubbed — do NOT hit real token refresh.

### 5.3 Airtight claim (review LOW-6)
In `action_claim`, replace the search-then-write guard with a row lock that keeps ORM
write/tracking intact:
```python
self.env.cr.execute(
    "SELECT id FROM care_conversation WHERE id = %s AND owner_id IS NULL FOR UPDATE SKIP LOCKED",
    (conv_id,))
if not self.env.cr.fetchone():
    return {"claimed": False, ...}   # lost the race or already owned — existing path
rec.write({"owner_id": self.env.uid})  # still ORM → chatter/tracking preserved
```
`take_over` keeps its manager gate and stays last-writer (deliberate override is the feature).

### 5.4 Workspace scalability (review LOW-9) + search
- Channel counts + status counts + team load via `read_group` (one query each), not ORM loops.
- Tile/list payload capped at 400 conversations ordered `urgency desc, last_event_at desc`;
  when capped, include `{"capped": true, "total": N}` in the payload (no silent truncation —
  same honesty rule as PWA cache-hygiene).
- Wire the chat-list search input (currently `disabled`, `care_command.xml:106`): new optional
  `query` param on `get_workspace_data`; server-side `['|','|','|', name ilike, phone_normalized
  ilike, email_normalized ilike, lead_id.name ilike]` on top of the company domain; debounce
  300ms client-side. Group gate + company scope unchanged.

### 5.5 vi.po completion (review LOW-8)
Cover all `_()` strings in Python, and make JS labels translatable: `CHANNELS`/`LIST_SECTIONS`
label values through `_t` (`@web/core/l10n/translation`), QWeb chrome text as translatable
terms. Update `i18n/vi.po` by hand for every new/missing msgid (ledger §29 family — no
machine-generated placeholder translations; natural Vietnamese).

## 6. Tests (extend the Phase-1 suite numbering)

- **T18** (health_zalo): send repair success path — mocked `requests.request` + stubbed token →
  `state='sent'`, `zalo_message_id` set, conversation `update_last_message` called.
- **T19** (health_zalo): send failure path — non-200 → `state='failed'` + UserError; and
  `action_test_connection` reaches `get_oa_profile` without KeyError (mocked).
- **T20** (voip): module installs — `group_voip_user`/`group_voip_manager` exist with
  `privilege_id`; smoke-create a `voip.call.log`.
- **T21** (bridge): missed incoming log → conversation `needs_reply` + `missed_call_unhandled`
  + urgency includes the +10 term; answered → timeline `call` event, status untouched;
  outgoing → `waiting`, missed flag cleared.
- **T22** (bridge): hook exception isolation — patch `_find_or_create_for` to raise; the
  `voip.call.log` create still succeeds (mirror T13, savepoint in force).
- **T23** (care_command): claim lost-race path — pre-owned conversation → `claimed: False`;
  fresh → `claimed: True` and chatter tracking recorded.
- **T24** (care_command): `get_workspace_data(query=...)` filters by name/phone/email/lead name;
  empty query = unfiltered; still company-scoped.
- **T25** (care_command): capped payload — >cap fixture (create cheaply, e.g. 401 minimal rows)
  → `capped: True`, `total` correct, counts still exact (read_group, not the capped list).

Test rules: assert codes not display text (§5.50); wrap any reused CRM action in the
`cr.commit` patch (§5.53); mock `action_send_message` NOWHERE in T18/T19 (the point is the real
path below it); no HttpCase (§5.32 stays irrelevant).

## 7. Deploy (vietuat — ledger §5.45: never concurrent odoo-bin)

1. scp + install per the standard workflow (`.claude` memory flow): modules touched =
   `health_zalo`, `health_voip24h`, `health_care_command`, `health_care_command_voip`.
2. Upgrade command (one run):
   `-u health_zalo,health_care_command -i health_voip24h --test-enable
   --test-tags /health_care_command,/health_care_command_voip --stop-after-init --no-http`
   (bridge auto-installs with voip; T18/T19 live in health_care_command's test module if adding
   a test file to health_zalo is heavier than the diff — your call, report which).
3. Verify: service 5 procs + /web/login 200; `health_voip24h` + bridge `installed` in
   `ir_module_module`; backfill log line shows the call leg; **grep today's (UTC) log for the
   test result — never trust a stale line** (this bit the Phase-1 review).
4. Reality check (report, don't fix): `voip.config` records + credentials state; `zalo.config`
   state (`connected`?); counts of `voip.call.log` rows. Expected: all zero/none — say so.
5. Bump `health_care_command` version to 19.0.2.0.0; bridge starts at 19.0.1.0.0.

## 8. Report back

1. Test transcript (today's timestamped result line) + per-test mapping T18–T25.
2. Every extra O19-compat change health_voip24h needed beyond the two `category_id` lines.
3. Where T18/T19 live (health_zalo tests vs care_command test module) and why.
4. Reality check results (§7.4).
5. Any deviation, declared with evidence — never silently adapted.
6. Proposed new ledger entries if you hit fresh gotchas (do not edit the ledger yourself).

**Kickoff line for the Opus session:**
Implement `docs/strategy/handovers/care-command-phase2.md` (Care Command Phase 2 — Live
Channels: Zalo send repair + VoIP on Odoo 19 + bridge ingestion + workspace hardening). Read
`docs/strategy/HANDOVER-CONVENTIONS.md` first (§5.45, §5.51–5.55 especially). Follow the
handover exactly: two-site zalo fix only, voip `category_id` removal + minimal install fixes,
new `health_care_command_voip` bridge with savepoint hooks, airtight claim + read_group +
search + vi.po in `health_care_command`, tests T18–T25 green, deploy to vietuat per §7
(including the §7.4 reality check), report back per §8. No real outbound messages, no
credential/webhook changes.
