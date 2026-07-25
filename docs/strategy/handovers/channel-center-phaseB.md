# Channel Center — Phase CC-B Handover: Message Spine + 4 Adapters

**For:** Opus implementation session (AFTER CC-A review fixes landed) ·
**Designed/reviewed by:** Fable (2026-07-25)
**Read first, in order:**
1. `docs/strategy/HANDOVER-CONVENTIONS.md` — §5.55, §5.61, §5.63 especially.
2. `docs/strategy/handovers/channel-center-architecture.md` §5.6/§6/§7.5/§8.
3. `docs/strategy/handovers/care-command-phase6.md` — **this phase implements that
   spec's §2.2–§2.6, §5, §6, §7 (T50–T69) verbatim EXCEPT as amended by §2 below.**
   Its §2.1 `care.channel.account` model is DEAD — `care.channel.connection`
   (CC-A, live) replaces it everywhere.
4. `docs/strategy/reports/channel-center-phaseA-report.md` — what CC-A actually
   built (guard semantics, `_internal()`, readiness upsert API).

**Modules touched:** `health_care_command_channels` → 19.0.2.0.0 (main work);
`health_care_command` → 19.0.4.1.0 (ONLY the §3 core-touch list — identical to
phase6 §5, corrected line numbers below). Nothing else.

## 1. Scope

The 4 dock channels (whatsapp, fb, telegram, webchat) become real rails on the
`care.conversation` spine: identity registry, message store, single ingest funnel,
adapter send/parse, fail-closed webhook controllers, anonymous webchat widget —
exactly phase6's §2.2–§2.6. Everything reads its configuration/credentials from
`care.channel.connection` + `channel.platform.app`. Still NO tenant-facing UI (CC-C),
NO Zalo/email/voip adapters (CC-D/E/F), NO real credentials on vietuat.

## 2. Amendments to the phase6 spec (binding — this list is exhaustive)

1. **Account model replacement.** Everywhere phase6 says `care.channel.account`,
   read `care.channel.connection`. Field mapping:
   | phase6 field | CC-B home |
   |---|---|
   | `meta_app_secret`, `meta_verify_token` | `channel.platform.app` provider `'meta'`: secret via `_get_secret()`, verify_token in `extra_json` (key `verify_token`) |
   | `meta_access_token` | `connection.access_token_enc` via `_get_secret('access_token')` |
   | `wa_phone_number_id` / `fb_page_id` | `connection.resource_external_id` (WABA id → `resource_secondary_id`) |
   | `tg_bot_token` | `connection.provider_secret_enc` |
   | `tg_webhook_secret` | `connection.webhook_path_secret` (ONE value serves both the URL path and the `setWebhook` secret_token header — phase6 T52 semantics unchanged) |
   | `wc_allowed_origins`, `wc_greeting` | NEW `connection.settings_json` Text (json.dumps dict; non-secret per-channel settings; sanctioned schema addition) |
   | `api_base_override` | NEW `connection.api_base_override` Char (sanctioned) |
   | `state` draft/connected/disabled | connection state machine. Define `SENDABLE_STATES = {'ready', 'expiring'}` module-level in `care_channel_connection.py`; "active+connected account exists" → an active connection in SENDABLE_STATES for (channel, company). `webhook_enabled` → `webhook_state != 'none'` is NOT a gate; verification is (fail-closed verifiers don't consult state) |
   Add both new fields to `USER_WRITABLE`? **NO** — they stay server-maintained
   (`_internal()` writes; CC-C UI goes through actions).
2. **Verifiers live in `services/webhook_verify.py`** (not on the model):
   `verify_meta(platform_app, raw_body, header)` (clone voip_config.py:422-442 —
   secret via `platform_app._get_secret()`; missing app/secret/header → False),
   `meta_challenge(platform_app, mode, token, challenge)`,
   `verify_telegram(connection, path_secret, header_secret)`. All
   `hmac.compare_digest`, all fail closed (§5.61). Meta app secret is PLATFORM-plane:
   one signature check per request BEFORE tenant routing.
3. **Multi-tenant webhook routing** (new vs phase6, which assumed one account):
   after signature verification, resolve the connection by payload ids —
   WA: `entry[].changes[].value.metadata.phone_number_id` → connection
   `(channel='whatsapp', resource_external_id=...)` sudo search (company-agnostic),
   then `with_company(connection.company_id)` for ingest; FB: `entry[].id` (page id);
   TG: path secret → connection; webchat: session → identity → connection.
   Unknown resource id → log event-type only, return 200 (generic, no oracle).
   Connection found but NOT in SENDABLE_STATES ∪ {'testing','configuring'} → still
   ingest? **NO — drop with 200 + audit `webhook_ignored`** (a disabled channel must
   not keep filling the inbox; declared behavior).
4. **Readiness/health wiring** (the point of the whole framework):
   - `_ingest_inbound` additionally: `connection._internal().write({'last_inbound_at',
     'last_webhook_at', 'webhook_state': 'verified'})` + `upsert_check(connection,
     'webhook_verified', 'pass')` + `upsert_check(connection, 'inbound_ok', 'pass')`.
   - successful `send_message` → `last_outbound_at` + `upsert_check('outbound_ok',
     'pass')`; provider auth failure (401/190-class) → `upsert_check(
     'authorization_valid', 'fail', detail=redact(...))` (→ action_required via
     `_recompute_ready`).
   All under the internal context; never raise out of the ingest savepoint.
5. **`_channel_keys()` override** (core seam, phase6 §5.3): base live rails
   (`zalo, call, email, zns`) + each of the 4 channels having an active connection in
   SENDABLE_STATES **for the current company** (`self.env.company`).
6. **`care.reply.template.channel`**: P5 did NOT extend it (verified —
   care_reply_template.py:24-35 still any/zalo/call/email/zns). `selection_add` the
   four new keys with `ondelete='set default'`... default is 'any' — use
   `ondelete={'whatsapp': 'set any', ...}`? Odoo 19 selection_add ondelete values:
   use `'set default'`. Declare in report.
7. **Corrected line citations** (phase6's are stale post-P5): `_find_or_create_for`
   care_conversation.py:343-442 (update branch to extract as `_apply_signal`:
   :389-442); anchor precedent :76-87 + partial unique :161-171; `_check_anchor`
   :173-186; `_match_watchlist` :309-327; `_safe_phone` :292-301; capabilities dict
   inline :756-759 (extract as `_capabilities()`); `action_send_zalo` return contract
   :1101-1105; `_channel_keys` :547-552; `sendChannel` care_command.js:406-414;
   `sendMessage` :423-444. Savepoint hook pattern hooks.py:27-36. Verify each before
   editing (§5.59).
8. **Webchat public routes**: unchanged from phase6 §2.6 (rate counter, session
   uuid4, 2000-char cap, poll, demo page, GC cron, CORS from
   `settings_json.allowed_origins`). The "one-click enable" ACTION is CC-C; in CC-B
   a webchat connection is created/enabled via test fixtures and (temporarily) the
   backend list view — creating a webchat connection with `resource_external_id =
   'default'` and transitioning to ready via seeded checks is the CC-C bridge.
9. **New tests T90–T94** on top of phase6's T50–T69 (all TransactionCase, all
   `requests` mocked, canonical simulated payloads in the test file):
   - **T90** send gating: `action_send_channel` succeeds with connection state
     `ready` AND `expiring`; UserError (composer-degrade contract) when
     `disabled`/`action_required`/absent; capability `ext_reply_channel` mirrors it.
   - **T91** traffic→truth: simulated WA inbound flips `last_inbound_at`,
     `webhook_state='verified'`, checks `webhook_verified/inbound_ok` pass; mocked
     send success flips `outbound_ok` + `last_outbound_at`; mocked 401 send flips
     `authorization_valid=fail` and state falls to `action_required`.
   - **T92** `_channel_keys()`: company-scoped — company A ready-whatsapp connection
     activates 'whatsapp' for A only; B unchanged; draft/disabled excluded; base 4
     always present.
   - **T93** platform-plane fail-closed: NO `channel.platform.app` row for meta ⇒
     Meta GET challenge refused AND POST signature verification False even with a
     valid-looking header; telegram with no connection for path secret ⇒ refused.
   - **T94** reply templates: the 4 new selection values legal; `_reply_templates()`
     on a whatsapp-effective conversation returns 'any' + 'whatsapp' rows.
10. **Fold-in from CC-A review (LOW #4, declared here so it lands this phase after
    all):** `care.channel.oauth.session._consume` becomes
    `UPDATE care_channel_oauth_session SET used_at = now() WHERE state_hash = %s AND
    used_at IS NULL AND expires_at > now() RETURNING id` (cross-worker single-use);
    keep the ORM fallback assertions in T83 green.

## 3. Core touches (health_care_command → 19.0.4.1.0 — phase6 §5 list, nothing else)

1. Extract `_apply_signal(self, anchor, signal)` from :389-442 (pure refactor).
2. Extract `_capabilities(self)` from :756-759; `get_conversation_detail` calls it.
3. `_channel_keys()` stays the hook (already exists :547-552) — NO core edit needed
   beyond what phase6 assumed; the override lives in the extension. (If the hook
   signature already suffices, declare "core touch #3 not needed".)
4. JS: `sendChannel` getter first-branch `caps.ext_reply_channel`; `sendMessage`
   routes non-zalo/email to `action_send_channel`. Keep `.sendbtn`/`.crail-tabs`
   and the exported class intact (AI-module seams).

## 4. Binding NON-goals

Phase6 §3 list carries over verbatim (no credentials on vietuat, no real HTTP in
tests, no media download, no Meta templates, no bus webchat, no queue, no AI, no
zalo webhook repair, no auto-merge of FB/TG identities with phone threads, no PWA)
PLUS: no Channel Center UI (CC-C), no tenant-admin ACL row (CC-C), no Zalo/email/
voip adapter work, no `_consume` changes beyond §2.10.

## 5. Tests & deploy

- One run: `-u health_care_command_channels -u health_care_command` with
  `--test-tags /health_care_command_channels,/health_care_command,/health_care_command_voip,/health_care_command_ai`
  `--no-http` — expect CC-A's 20 (+T90-94 → 25) + phase6's T50–T69 (20) + core 46,
  0 failed. Fresh TODAY-UTC result lines.
- Browser evidence (§8.1): webchat demo page end-to-end on vietuat (widget → ops
  inbox → reply → poll), dock honesty (4 icons inactive with no ready connections;
  flip a fixture connection to ready → icon activates), AI module still patching.
  Clean up fixtures fresh-cursor (§5.34).
- Report: deviations, data honesty (0 connections ⇒ dock unchanged for real users),
  webhook URLs for ops, new gotchas.

**Kickoff line for the Opus session:**
Implement `docs/strategy/handovers/channel-center-phaseB.md` (Channel Center Phase
CC-B — message spine + WhatsApp/FB/Telegram/webchat adapters on the care.conversation
spine, implementing care-command-phase6.md §2.2–§2.6/§5/§7 as amended by phaseB §2:
care.channel.connection replaces care.channel.account, platform-plane Meta secrets,
multi-tenant webhook routing, readiness wiring, `_channel_keys()` company gating,
T50–T69 + T90–T94). Read HANDOVER-CONVENTIONS.md (§5.55/§5.61/§5.63), the
architecture doc, phase6, and the CC-A report first. Only sanctioned files; all HTTP
mocked; deploy + browser evidence per §5; report deviations and data honesty.
