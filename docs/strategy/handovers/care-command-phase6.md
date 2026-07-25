# Care Command — Phase 6 Handover: "Channel Adapters" (WhatsApp · FB Messenger · Telegram · Web Chat)

> **⚠️ SUPERSEDED (2026-07-25) — do not kick off as-is.** The Channel Connection
> Center design (`channel-center-architecture.md`) replaces this handover's
> ops-enters-credentials posture with tenant self-service. The adapter/webhook/
> identity/message spine below is PRESERVED and will be re-issued as **Phase CC-B**
> (rebased onto `care.channel.connection` from Phase CC-A, which must land first —
> see `channel-center-phaseA.md`). Line citations into care_conversation.py are
> STALE post-P5; corrected positions are in channel-center-architecture.md §1.1.

**For:** Opus implementation session (AFTER Phase 5 is live + reviewed — this module
builds on the Phase-5 Selection values, `_channel_keys()` hook and `active_channels`
payload) · **Designed/reviewed by:** Fable
**Read first:** `docs/strategy/HANDOVER-CONVENTIONS.md` (§5.45, §5.50–5.61 — **§5.61 is
the load-bearing one**: the Zalo webhook is a TRAP precedent; clone the voip24h posture).
**New module:** `health_care_command_channels` 19.0.1.0.0 (depends
`health_care_command`, `health_api_gateway`; NOT auto_install — installing is an ops
decision). Declared core touches to `health_care_command` → 19.0.4.1.0 (exact list §5).

## 1. Why & philosophy (binding)

The dock's WhatsApp / FB Messenger / Telegram / Web Chat entries become real channels on
the SAME spine (`care.conversation._find_or_create_for`) the live channels already use.
Sovereignty of posture: everything ships **credential-less and draft** — the Meta pair
(WhatsApp Cloud API + FB Send API) needs a Meta business app that only ops can provision
(same situation as the Zalo OA token); Telegram needs one bot token; Web Chat is our own
widget. All four are fully built and simulated-webhook-tested now; nothing real flows
until ops wires credentials. **No real outbound message to any external service from
tests or deploy verification — every adapter HTTP call is mocked.**

## 2. Scope (deliverables)

```
addons/health_care_command_channels/
├── __manifest__.py                    # depends: health_care_command, health_api_gateway
├── models/
│   ├── care_channel_account.py        # ONE config model, all 4 channels
│   ├── care_channel_identity.py       # (account, external_id) peer registry
│   ├── care_channel_message.py        # ONE message store + _ingest_inbound funnel
│   ├── care_conversation_ext.py       # _inherit: anchor, send, timeline, capabilities
│   └── care_reply_template_ext.py     # nothing needed if P5 shipped all 8 values — verify, else selection_add
├── services/adapters.py               # registry + 4 adapter classes
├── controllers/{meta.py, telegram.py, webchat.py}
├── security/{ir.model.access.csv, channel_security.xml}
├── views/{care_channel_views.xml, webchat_templates.xml}
├── static/src/webchat/{widget.js, widget.css}   # dependency-free vanilla JS
├── i18n/vi.po                         # §5.58 markers
└── tests/test_channels.py             # T50–T69
```

### 2.1 `care.channel.account` — ONE config model
Fields: `name` (req), `channel` Selection [whatsapp, fb, telegram, webchat] (req, index),
`company_id` (req, default env.company, index), `active`, `state` Selection
[draft, connected, disabled] default draft, `webhook_enabled` Bool default False;
Meta shared: `meta_app_secret`, `meta_verify_token`, `meta_access_token`,
`wa_phone_number_id` (WA), `fb_page_id` (FB); Telegram: `tg_bot_token`,
`tg_webhook_secret`; Webchat: `wc_allowed_origins` (comma list, '' = same-origin),
`wc_greeting`; ops: `api_base_override` (test/staging endpoint), `last_error` (redacted).
- `init()`: partial unique index — ONE active account per (channel, company) (clone
  care_conversation.py:113-123).
- Verifiers (ALL fail closed — §5.61): `_verify_meta_signature(raw_body, header)` exact
  clone of health_voip24h/models/voip_config.py:422-442 (no secret → False, strip
  `sha256=`, `hmac.compare_digest`); `_meta_verify_challenge(mode, token, challenge)`
  (returns challenge only if mode=="subscribe" AND compare_digest against
  meta_verify_token; unconfigured → refuse); `_verify_telegram(path_secret,
  header_secret)` (compare_digest both; header checked when present).
- `_get_adapter()` → registry lookup; `action_test_connection()` per channel (Graph
  `GET /me`, Telegram `getMe`, webchat no-op) — for ops later, mocked in tests;
  Telegram `action_register_webhook` calls `setWebhook` with the secret URL +
  `secret_token` (mocked in tests).
- **ACL: base.group_system ONLY (rwcu).** Accounts hold tokens — no CRM read; all
  runtime reads are server-side sudo, so secrets can never leak via read()/export.

### 2.2 `care.channel.identity` — external peer registry
`account_id` (req, index, ondelete restrict), `channel` (related stored),
`external_id` Char (req, index — WA msisdn/wa_id, FB PSID, TG chat_id, webchat uuid4),
`display_name`, `company_id` (related stored), `last_seen_at`.
`init()`: unique (account_id, external_id). CRM users read-only.

### 2.3 `care.channel.message` — ONE message store (zalo.message shape, generalized)
`account_id` (req, index), `channel` (related stored), `identity_id` (req, index),
`conversation_id` (index, ondelete set null), `external_message_id` (index; wamid… / FB
mid / f"{chat_id}:{message_id}" / webchat uuid), `direction` [incoming, outgoing] (req),
`message_type` [text, image, file, location, other] default text, `body` Text,
`attachment_url/name/mime` (metadata ONLY — no media download v1), `raw_payload` Text
(json.dumps), `state` [received, queued, sent, delivered, read, failed] (index),
`error_message`, `event_at` (req, index), `company_id` (related stored).
- `init()`: partial unique (account_id, external_message_id) WHERE external_message_id
  IS NOT NULL → webhook-redelivery dedupe (Meta redelivers aggressively).
- CRM user/manager read-only; create/write via sudo paths only.
- **`_ingest_inbound(account, event)` — the single funnel** (event = normalized dict
  from adapter.parse_webhook: external_id, external_message_id, text, display_name,
  message_type, attachment?, event_at, raw):
  1. dedupe on (account, external_message_id) → return existing (idempotent);
  2. upsert identity (display_name, last_seen_at);
  3. create message row (incoming, received);
  4. inside `self.env.cr.savepoint()` (§5.55) with `with_company(account.company_id)`:
     ```python
     anchor = {"channel_identity_id": ident.id}
     if account.channel == "whatsapp":
         anchor["phone_normalized"] = Care._safe_phone(event["external_id"])
     Care._find_or_create_for(anchor, {
         "channel": account.channel, "inbound": True, "event_at": event["event_at"],
         "set_status": "needs_reply", "unread": 1,
         "watch_hits": Care._match_watchlist(event.get("text"))})
     ```
  5. link `conversation_id` on the row.
  Outbound rows mirror the zalo outgoing signal (hooks.py:58-65): inbound False,
  set_status waiting, unread "zero".

### 2.4 Conversation extension (`care_conversation_ext.py`, `_inherit`)
- `channel_identity_id` m2o (index, ondelete set null) — the ONE new anchor, mirroring
  the zalo_conversation_id precedent (care_conversation.py:52-55) + partial unique index
  in extension `init()` (:113-123 pattern).
- `_check_anchor` override (:125-138): accept `channel_identity_id` as a valid sole
  anchor (FB/TG/webchat have no phone/email/partner at first contact).
- `_compute_display_name_c` extension: fall back to `channel_identity_id.display_name`.
- `_find_or_create_for` override: identity-first lookup (company-scoped), then super().
  WhatsApp passes phone too → merges into an existing phone-anchored thread, then
  backfills `channel_identity_id` if empty. Idempotency contract (T1-style) must hold.
- `_detail_timeline` override: super() + interleave `care.channel.message` events for
  the identity, re-sort by ts, re-cap 100.
- `_snippet` override: latest inbound channel message body (120-char, precedent
  :591-615).
- **`action_send_channel(conv_id, channel, text)`** (@api.model):
  `_ensure_access()` → `_guarded(conv_id)` → validate channel matches
  `rec.channel_identity_id.channel` AND an active+connected account exists for
  (channel, rec.company_id) → `account._get_adapter().send_text(identity, text)` →
  outgoing message row → `rec.write({status: waiting, unread_count: 0, last_event_at:
  now})` → return a timeline bubble dict matching `action_send_zalo`'s contract
  (care_conversation.py:974-978). Adapter failure → message state failed + redacted
  error + clean UserError (never blocks manual work). **NO auto-send of any kind; the
  only send trigger is this human composer call.**
- `_capabilities()` extension (core seam §5): `caps["ext_reply_channel"] = <channel>`
  when identity + active connected account exist, else absent.

### 2.5 Adapters (`services/adapters.py`)
```python
CHANNEL_ADAPTERS = {}          # channel -> class; @register_adapter("whatsapp") …
class BaseChannelAdapter:      # __init__(env, account)
    def parse_webhook(self, payload) -> list[dict]: ...
    def send_text(self, identity, text) -> dict: ...   # {"external_message_id","state"} or raises
```
- WhatsApp: `POST https://graph.facebook.com/v21.0/{wa_phone_number_id}/messages`
  (Bearer meta_access_token). Parse `entry[].changes[].value.messages[]`; `statuses`
  events (delivered/read) update the outgoing row's state by external_message_id.
- FB: `POST .../me/messages?access_token=…` (`recipient.id` = PSID,
  `messaging_type: RESPONSE`). Parse `entry[].messaging[]`.
- Telegram: `POST https://api.telegram.org/bot{token}/sendMessage`. Parse
  `update.message` (chat.id, message_id, text, from.first_name).
- Webchat: **no HTTP** — creating the outgoing row IS delivery (state sent); the
  widget's poll picks it up.
- All HTTP via `requests` with explicit timeout; honor `api_base_override`. Logging:
  event types + ids ONLY — never bodies, phones, or names (no PHI in logs).

### 2.6 Controllers — §5.61 posture everywhere
All routes `type='http'`, `auth='public'`, `csrf=False`, `save_session=False`, raw body
via `request.httprequest.get_data()`, thin shells (verify → model call) so
TransactionCase covers everything below header plumbing. `env(su=True)` only AFTER
verification; generic responses (no account-existence oracle — clone
health_voip24h/controllers/webhook.py:66-70). **Inline processing — NO with_delay
(§5.61c: no queue_job addon exists), NO jsonrpc routes (Meta signs raw bytes).**
- `GET /care_channels/meta/<channel>/webhook` (channel ∈ whatsapp|fb): Meta handshake.
  Gotcha: `hub.mode`/`hub.verify_token`/`hub.challenge` contain DOTS — read via
  `request.httprequest.args.get('hub.challenge')`, NOT kwargs. Success → challenge as
  plaintext 200; anything else (incl. no account/token) → 403.
- `POST /care_channels/meta/<channel>/webhook`: verify `X-Hub-Signature-256` over raw
  bytes → 403 on mismatch/missing/unconfigured; then json.loads, adapter.parse_webhook,
  per-event `_ingest_inbound` in savepoints; ALWAYS 200 after verification (retry-storm
  control, voip precedent webhook.py:87-90).
- `POST /care_channels/telegram/webhook/<path_secret>`: `_verify_telegram(path_secret,
  X-Telegram-Bot-Api-Secret-Token header)`; fail closed; 200 after verification.
- Webchat (every route first hits `gateway.rate.counter.hit(...)` per-IP — clone
  health_family_link/controllers/family_public.py:20-31 — message route also
  per-session; blocked → 429):
  - `POST /care_channels/webchat/start` {session?} → reuse known uuid or server-side
    uuid4 + identity ("Web visitor ‹uuid[:8]›"); optional pre-chat {name, phone} (name →
    display_name; phone → passed as phone_normalized anchor at first message). Returns
    {session, greeting}.
  - `POST /care_channels/webchat/message` {session, text}: unknown session → generic
    404 (no oracle); text stripped, 2000-char cap, plain text (escape on render).
  - `GET /care_channels/webchat/poll?session&after_id` → `[{id, direction, body, ts}]`
    both directions (multi-tab consistency). **Short-polling 3–5 s with backoff — NO
    bus/long-poll v1** (anonymous bus auth is a large surface; polling is bounded by
    the rate counter).
  - `GET /care_channels/webchat/demo` → standalone QWeb page embedding the widget (no
    `website` dependency — family_link precedent).
- Widget: `static/src/webchat/widget.js` — vanilla JS, no Odoo assets; embed =
  `<script src=".../widget.js" data-origin="https://host">`; launcher bubble + panel,
  localStorage session, fetch + poll loop, exponential backoff when tab hidden/idle.
  CORS: `Access-Control-Allow-Origin` ONLY for origins in `wc_allowed_origins`.
- Daily GC cron: unlink webchat identities/conversations with zero inbound messages
  older than 7 days.

## 3. Binding NON-goals

- **No credentials, provider config, or webhook registration on vietuat** — all accounts
  ship draft; `action_test_connection`/`action_register_webhook` are for ops later.
- **No real external HTTP from tests or deploy verification** — mock `requests`
  everywhere.
- **No media download** (attachment metadata only), **no Meta template messages** (24 h
  customer-care window means late free-form replies get API-rejected — surface the API
  error verbatim; templates are a future phase), **no bus/websocket webchat**, **no
  queue**, **no supervisor features**, **no AI** (the AI module composes separately).
- **No zalo webhook repair** and no health_zalo edits.
- **No auto-merge of FB/TG identities with phone/email threads** (no phone in their
  payloads) — merging stays a human action; declared limitation.
- No PWA involvement.

## 4. Verified plumbing (do not re-derive)

- Upsert + signal shape: care_conversation.py:288-378; savepoint hook pattern
  hooks.py:27-36 (§5.55); watchlist `_match_watchlist` care_conversation.py:254-271;
  `_safe_phone` :236-244 (normalize_vn_phone).
- Anchor precedent: zalo_conversation_id :52-55 + partial unique :113-123;
  `_check_anchor` :125-138.
- Fail-closed HMAC to clone: health_voip24h/models/voip_config.py:422-442; raw http
  route + generic responses: health_voip24h/controllers/webhook.py:24-90.
- **Anti-precedent (§5.61)**: health_zalo/controllers/webhook.py:20 (jsonrpc),
  :46 (with_delay — would crash, no queue_job addon), :130-140 (fails open). Do not
  copy anything from it.
- Rate counter: health_api_gateway `gateway.rate.counter.hit()`
  (models/gateway_rate_counter.py:37-54) as used by
  health_family_link/controllers/family_public.py:20-31.
- Send-return contract: `action_send_zalo` care_conversation.py:955-978.
- Phase-5 seams this module consumes (verify they landed as specced before coding):
  all-8 Selection values on the three channel fields, `_channel_keys()` hook +
  `active_channels` payload, `channel_effective` filtering, `has_channel_activity`
  (your ingest signals carry `channel` → it flips True automatically).

## 5. Declared core touches (`health_care_command` → 19.0.4.1.0 — complete list, nothing else)

1. **Extract `_apply_signal(self, anchor, signal)`** from `_find_or_create_for`'s update
   branch (care_conversation.py:330-377) — pure refactor, zero behavior change; lets the
   extension apply signal semantics to identity-resolved records without duplication.
2. **Extract `_capabilities(self)`** returning the dict at :631-634;
   `get_conversation_detail` calls it. (Extension override adds `ext_reply_channel`.)
3. **`_channel_keys()` override seam**: the module overrides it so `active_channels`
   reflects reality — base 4 + each new channel that has an active account (draft
   accounts → dock icon stays inactive; honest).
4. **JS (channel-agnostic only)**: `sendChannel` getter (care_command.js:408-415) gains
   `if (caps.ext_reply_channel) return caps.ext_reply_channel;` as the first branch;
   `sendMessage` (:425-446) routes channels other than zalo/email to
   `orm.call("care.conversation", "action_send_channel", [id, ch, text])`. The core
   never names the 4 channels beyond labels it already ships. Keep `.sendbtn` /
   `.crail-tabs` classes and the exported class intact (AI-module seams).

## 6. Security

- Webhooks fail closed everywhere; `hmac.compare_digest` only; generic error responses;
  `with_company(account.company_id)` so conversations land in the account's company.
- ACLs: account = system-only; message/identity = CRM read-only + company record rules;
  all creation via sudo server paths.
- `raw_payload` lives in the DB behind ACLs; NEVER in the logger.
- Webchat abuse: per-IP + per-session rate windows, 2000-char cap, uuid4
  unguessability, no existence oracles, GC cron; flooded junk lands as triageable
  conversations and the WORKSPACE_CAP protects the UI — declared residual risk.

## 7. Tests (T50–T69, tests/test_channels.py, TransactionCase ONLY — §5.32/§5.61; canonical simulated payload dicts checked into the test file; `requests` mocked everywhere)

- **T50** Meta HMAC: valid sig accepted; wrong sig / missing header / NO configured
  secret all rejected (fail closed).
- **T51** Meta GET handshake: correct verify_token returns challenge; wrong/missing
  token or no account refuses.
- **T52** Telegram: path secret + header secret verified via compare_digest; fail
  closed with no secret/account.
- **T53** WhatsApp inbound (simulated Cloud API payload): identity + message row +
  conversation with `channel_primary="whatsapp"`, phone anchored via normalize_vn_phone,
  needs_reply, unread ≥ 1, `has_channel_activity=True`.
- **T54** Redelivery idempotency: same external_message_id twice → one row, one
  conversation, no double unread bump.
- **T55** FB inbound (PSID): conversation created with ONLY `channel_identity_id`
  anchor — `_check_anchor` override passes; display name from profile.
- **T56** Telegram inbound (chat_id): identity-anchored; `f"{chat_id}:{message_id}"`
  dedupe key.
- **T57** WhatsApp merge: existing phone-anchored conversation + first WA inbound with
  same normalized phone → SAME conversation, identity backfilled, no duplicate.
- **T58** Webchat lifecycle: start → identity uuid; message → conversation
  `channel_primary="webchat"`; unknown session refused generically.
- **T59** Webchat poll cursor: agent `action_send_channel` reply appears with
  `id > after_id`; earlier ids excluded.
- **T60** Outbound per channel (mocked requests.post): outgoing/sent row with external
  id captured; conversation → waiting + unread 0; HTTP error → UserError + state failed.
- **T61** Capabilities: `ext_reply_channel` present when identity + active connected
  account; absent when account draft/disabled/missing (composer degrades honestly to
  email/zalo logic).
- **T62** Access: plain user AccessError on `action_send_channel`; CRM user succeeds;
  CRM user CANNOT read `care.channel.account`.
- **T63** Multi-company: company-2 account → ingest lands conversation in company-2;
  company-1 `get_workspace_data` doesn't list it.
- **T64** Watchlist: inbound matching an active care.watch.phrase sets
  watch_flag/terms.
- **T65** Host isolation: ingest raising inside savepoint does not abort the
  surrounding transaction.
- **T66** Rate limit: counter block path returns the 429/limited outcome for
  `webchat:msg:<session>` beyond the window.
- **T67** `_channel_keys()` override: active WA account → "whatsapp" in
  active_channels; draft-only → excluded (base 4 always present).
- **T68** Timeline merge: `_detail_timeline` interleaves channel messages, sorted,
  capped at 100.
- **T69** WA status events: delivered/read transitions the outgoing row by
  external_message_id; unknown id ignored quietly.

## 8. Deploy (vietuat — §5.45) & report-back

1. Standard flow; `-i health_care_command_channels -u health_care_command`. Versions:
   channels 19.0.1.0.0, core 19.0.4.1.0.
2. One test run over `/health_care_command_channels,/health_care_command,/health_care_command_voip,/health_care_command_ai`
   with `--no-http` (TransactionCase only). Fresh TODAY-UTC result line by YOUR pid.
3. Data honesty in the report: 0 accounts configured (all channels draft — dock icons
   for the 4 stay inactive via `_channel_keys()`), webhook URLs to hand ops
   (`/care_channels/meta/whatsapp/webhook`, `/care_channels/meta/fb/webhook`,
   `/care_channels/telegram/webhook/<secret>`, webchat demo at
   `/care_channels/webchat/demo`), and what each channel needs to go live (Meta business
   app + tokens; TG bot token; widget embed).
4. Browser checks for Fable: demo webchat page end-to-end on vietuat (widget → ops
   inbox → reply → poll), dock honesty (4 new icons inactive with no accounts), AI
   module still patching.

**Kickoff line for the Opus session:**
Implement `docs/strategy/handovers/care-command-phase6.md` (Care Command Phase 6 —
Channel Adapters: new module `health_care_command_channels` with WhatsApp/FB
Messenger/Telegram/Web Chat on the care.conversation spine — one account model, one
identity registry, one message store, adapter registry, fail-closed raw-http webhooks,
anonymous webchat widget). Read `docs/strategy/HANDOVER-CONVENTIONS.md` first —
**§5.61 especially: clone the voip24h webhook posture, never the Zalo one**. Follow the
handover exactly: declared core touches only (§5 list), TransactionCase-only T50–T69
with all `requests` mocked and simulated payload fixtures, no credentials/live external
calls ever, deploy to vietuat per §8, report webhook URLs + data honesty + deviations.
