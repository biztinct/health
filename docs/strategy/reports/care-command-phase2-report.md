# Care Command — Phase 2 Report: "Live Channels"

**Implementer:** Opus 4.8 · **Date:** 2026-07-21 · **DB:** vietuat
**Handover:** `docs/strategy/handovers/care-command-phase2.md`
**Result:** `0 failed, 0 error(s) of 25 tests` (2026-07-21 01:10:29 UTC), EXIT:0, HTTP:200, 5 procs.

---

## 1. What was built (file list)

### health_zalo — send repair (deliverable #1, exactly two sites, §4.1)
- `models/zalo_message.py` — added `from ..services.zalo_api import get_api_client`;
  `action_send_message()` now does `api_service = get_api_client(self.env)` (was the
  unregistered `self.env['zalo.api.client']`, §5.54). try/except → `state='failed'` intact.
- `models/zalo_config.py` — same import + `action_test_connection()` now uses
  `get_api_client(self.env)` before `get_oa_profile(self)`.
- **No other health_zalo change** (no API-shape, webhook, token, template, or `zalo_api.py` edit).

### health_voip24h — O19 compat (deliverable #2) — ALREADY DONE by the user (commit 4f69932d)
- The O19 migration (category_id→privilege_id, wizard load-order, manifest bump to 19.0.2.0.0,
  tests, vi.po rename, dropped python-dateutil) was authored and committed by the **user
  separately** as `4f69932d feat(voip24h): Odoo 19 migration + full implementation`, and
  deployed to vietuat (installed, 19.0.2.0.0). My working-tree matches that committed HEAD, so
  **I commit nothing for voip24h**. Deliverable #2 was satisfied outside this phase; I verified
  it live (T20–T22 create call logs / read groups and pass). See §4.1.

### health_care_command_voip — NEW bridge module (deliverable #3)
- `__manifest__.py` — `auto_install: True`, `depends: [health_care_command, health_voip24h]`,
  `post_init_hook`, version `19.0.1.0.0`.
- `models/hooks.py` — `VoipCallLogHook(_inherit='voip.call.log')` create-hook: super() first,
  then `_care_ingest_call` inside `try/except` + `cr.savepoint()` (§5.55). Missed/abandoned
  incoming → `needs_reply` + `missed_call`; answered incoming → event-only (no invented
  status); outgoing → `waiting` + missed flag cleared.
- `hooks.py` — `post_init_hook` re-runs the existing (idempotent, call-aware) care_command
  backfill so historic calls surface on install.
- `i18n/vi.po` — header-only (module has no user-visible strings).
- `tests/test_bridge.py` — T20, T21, T22.

### health_care_command — hardening (deliverable #4) + version → 19.0.2.0.0
- `models/care_conversation.py`:
  - `action_claim` — airtight claim (§5.3): existence+company check, then
    `SELECT id … WHERE owner_id IS NULL FOR UPDATE SKIP LOCKED` (flush first), ORM `write`
    on the win so chatter/tracking is preserved; loser gets a clean payload, no exception.
  - `get_workspace_data(channel, mine_only, query=None)` — counts + team via `_read_group`
    (one query each, no ORM loops); tile/list capped at `WORKSPACE_CAP=400` ordered by
    `_order`; payload carries `{"capped": bool, "total": N}` (no silent truncation); new
    `query` param filters `display_name_c / phone_normalized / email_normalized / lead_id.name`
    on top of the company+status+channel+mine scope.
- `static/src/js/care_command.js` — CHANNELS/LIST_SECTIONS labels + the fallback contact label
  through `_t`; `state.search`, `onSearchInput` (300ms debounce), `query` passed to
  `get_workspace_data`.
- `static/src/xml/care_command.xml` — search input wired (removed `disabled`, bound
  `t-att-value`/`t-on-input`).
- `i18n/vi.po` — completed: every Python `_()` term, every JS `_t` label, and the QWeb chrome
  (dock, sections, header strip, care rail, empty/loading states) — natural Vietnamese, each
  entry carries `#. module:` (§29).
- `tests/test_care_command.py` — T18, T19, T23, T24, T25 + a `_flush_tracking` helper.

---

## 2. Test transcript + T18–T25 mapping

`2026-07-21 01:10:29,362 … odoo.tests.result: 0 failed, 0 error(s) of 25 tests`

| Test | Suite | What it proves | Status |
|------|-------|----------------|--------|
| T1–T17 | health_care_command | Phase-1 suite (still green; T4/T11 mock `action_send_message`, so the send-path refactor doesn't perturb them) | ✅ |
| **T18** | health_care_command | zalo send SUCCESS: real `get_api_client`→`ZaloAPIClient` path, mocked `requests.request` + token → `state='sent'`, `zalo_message_id` set, `update_last_message` called | ✅ |
| **T19** | health_care_command | zalo send FAILURE: non-200 → `UserError` + `state='failed'` + `error_message`; and `action_test_connection` reaches `get_oa_profile` with no KeyError | ✅ |
| **T20** | health_care_command_voip | voip installs: `group_voip_user`/`group_voip_manager` carry `privilege_id`; smoke-create a `voip.call.log` | ✅ |
| **T21** | health_care_command_voip | live ingestion: missed→`needs_reply`+`missed_call`+urgency≥50; answered→timeline call event, status untouched; outgoing→`waiting`, missed flag cleared | ✅ |
| **T22** | health_care_command_voip | hook isolation: `_find_or_create_for` raises → `voip.call.log` create still succeeds, no leaked conversation (savepoint) | ✅ |
| **T23** | health_care_command | airtight claim: fresh→`claimed:True` + chatter tracking recorded; pre-owned→`claimed:False` + reports owner, no exception | ✅ |
| **T24** | health_care_command | `get_workspace_data(query=…)` filters by name/phone/email/lead name; empty query unfiltered; still company-scoped | ✅ |
| **T25** | health_care_command | >cap fixture → `capped:True`, `total` correct, `channel_counts.all.total` still exact (read_group, not the capped list) | ✅ |

## 3. Where T18/T19 live (and why)
In **health_care_command's** test module, not a new health_zalo test file: this suite already
carries the `zalo.config` / `zalo.conversation` / `zalo.message` fixtures, so no extra
`--test-tags /health_zalo` was needed and the deploy command stayed as specified.

## 4. Deviations (declared, with evidence)

### 4.1 (BIG) health_voip24h was O19-migrated + committed by the user, outside this phase
The handover premise was "`health_voip24h` cannot even install on Odoo 19". **Reality on
vietuat:** `health_voip24h` is `installed` at **19.0.2.0.0**, fully O19-clean (`privilege_id`,
no `category_id`), `voip.call.log` loads (proven live by T20–T22). The O19 migration (27 files,
+635/−447: category_id→privilege_id, wizard load-order fix, manifest bump, `tests/`,
`vi_VN.po`→`vi.po`, dropped `python-dateutil`) was authored and committed by the **user
separately** as `4f69932d feat(voip24h): Odoo 19 migration + full implementation` on branch
19.0 (this landed mid-session, which is why the voip24h working-tree briefly showed as
uncommitted). HEAD now carries the fix; my working tree matches it.

Consequences:
- Deliverable #2 ("make voip24h installable/ingested on O19") was **satisfied outside this
  phase** by the user's commit. My sanctioned 2-line `category_id` edit was already contained in
  it (redundant), so I commit nothing for voip24h and did not re-deploy it (the server copy is
  identical + already installed — re-touching it would only add deploy risk, §5.45).
- The bridge (`health_care_command_voip`) is what actually lights up live call ingestion on top
  of that migrated module.

### 4.2 Deploy command
Used `-u health_zalo,health_care_command -i health_care_command_voip` (bridge installed
explicitly) instead of the handover's `-i health_voip24h` (voip is already installed, so `-i`
on it is a no-op and would not have triggered the bridge). The bridge's `auto_install:True`
would also have pulled it in; explicit `-i` made the single deploy deterministic.

### 4.3 health_zalo version not bumped
Left at 19.0.1.0.0. The `-u` applied the code fix regardless; the handover sanctioned the code
edit but not a version bump, and bumping now would create a repo↔server version mismatch
needing another deploy for a cosmetic field. Flagged in case a bump is preferred.

## 5. §7.4 Reality check (report, don't fix)

| Item | Finding |
|------|---------|
| `voip.call.log` rows | **0** (total, all time) — no CDRs have ever been ingested |
| `voip.config` records | **0** — VoIP is installed but entirely **un-provisioned** (no account/credentials wired). Purely an ops step. |
| Backfill call leg | `care_command backfill: created zalo=0 call=0 email=0 lead=0` — call=0 is CORRECT (nothing to backfill) |
| `zalo.config` | 1 record ("Demo", **state=draft, no access_token**) — **not connected**. Send repair is proven by unit tests only; there is no connected OA to send through. No config/credential/webhook was created or modified. |
| `care.conversation` | **167** conversations, **all `channel_primary` NULL** (lead-anchored) — the documented "167-lead wall". No channel-primary traffic has flowed. |

**Bottom line:** the plumbing is repaired and installable, but on vietuat there is no VoIP
account and no connected Zalo OA, so the Calls channel is inert (0) and outbound Zalo cannot
send live until ops wires an OA. Exactly as the handover anticipated ("expected: all
zero/none").

## 6. Proposed new ledger entries (do not self-edit the ledger)

- **§5.56 — mail tracking messages post in the PRECOMMIT phase (Odoo 17+); a `TransactionCase`
  never commits, so `flush_all()` alone leaves `owner_id`/`status` tracking INVISIBLE (0
  messages, 0 `mail.tracking.value` rows) even though it works in production.** `_message_track`
  queues the tracking-message post via `self.env.cr.precommit.add(...)`; those callbacks run at
  `cr.commit()`, which tests don't reach. To assert on tracking in a test, run
  `self.env.flush_all(); self.env.cr.precommit.run()` first (the canonical `flush_tracking`
  pattern). Hit live in care-command T23: `assertGreater(len(conv.message_ids), before)` red-lit
  `1 not greater than 1` until precommit was flushed; an odoo-bin shell probe (which also never
  commits) reproduced the false "tracking is silent" reading, and `precommit.run()` turned
  before/after into 1→2 with an `owner_id` tracking value.
- **§5.57 (minor) — `_read_group` is the Odoo 19 grouping API; it returns a list of TUPLES
  `(group_value, *aggregates)`, not dicts.** Group by a Selection → raw string value; group by a
  Many2one → a recordset; request counts with the `"__count"` aggregate
  (`_read_group(domain, ["channel_primary"], ["__count"])`). NULL group values (unset Selection)
  come back as `False` and must be filtered by the caller. Used for the workspace channel/team
  counts (replaced the Phase-1 ORM `filtered()` loops).

## 7. Not verified / limitations
- **No live browser drive of the Care Command UI** (no backend `/odoo` login credentials in this
  session). The UI change is a thin passthrough: the search input → `state.search` →
  `get_workspace_data(query=…)`, whose server logic is proven by **T24**. JS parses clean
  (`node --check`, ES module) and the QWeb template is well-formed XML, so the `assets_backend`
  bundle compiles. Recommend the reviewer's selective browser pass (§8.1) cover the search box +
  translated labels on the live wall.
- No real outbound Zalo/VoIP message was sent (non-goal honored); no credential/webhook/config
  record created or modified.
