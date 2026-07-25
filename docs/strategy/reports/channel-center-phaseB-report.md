# Channel Center CC-B — Implementation Report

**Phase:** Channel Connection Center, Phase CC-B (message spine + 4 adapters)
**Handover:** `docs/strategy/handovers/channel-center-phaseB.md`
(implements `care-command-phase6.md` §2.2–§2.6/§5/§7 as amended by phaseB §2)
**Implemented by:** Opus 5 · **Date:** 2026-07-25 · **Target:** vietuat
**Modules:** `health_care_command_channels` 19.0.1.0.0 → **19.0.2.0.0**,
`health_care_command` 19.0.4.0.0 → **19.0.4.1.0**

---

## 1. What was built

```
health_care_command_channels/                       (→ 19.0.2.0.0)
├── models/
│   ├── care_channel_identity.py      NEW  external peer registry (wa_id/PSID/chat id/session)
│   ├── care_channel_message.py       NEW  ONE message store + _ingest_inbound funnel
│   │                                      + multi-tenant webhook routing + web-chat service + GC cron
│   ├── care_conversation_ext.py      NEW  channel_identity_id anchor, identity-first upsert,
│   │                                      timeline/snippet merge, _capabilities, action_send_channel,
│   │                                      _channel_keys() company gating
│   ├── care_reply_template_ext.py    NEW  selection_add for the 4 channels
│   ├── care_channel_connection.py    +    settings_json / api_base_override, SENDABLE_STATES,
│   │                                      INGESTABLE_STATES, _find_sendable/_find_for_resource,
│   │                                      _note_inbound/_note_outbound/_note_send_failure,
│   │                                      _persist_send_failure (fresh cursor)
│   ├── care_channel_oauth_session.py +    §2.10: _consume is now one atomic UPDATE … RETURNING
│   └── care_channel_audit.py         +    webhook_ignored / send_failed event tags
├── services/
│   ├── webhook_verify.py             NEW  verify_meta / meta_challenge / verify_telegram (fail closed)
│   └── adapters.py                   +    parse_inbound + send_message for whatsapp/fb/telegram/webchat
├── controllers/{meta,telegram,webchat}.py            NEW  raw-http fail-closed webhooks + widget routes
├── static/src/webchat/{widget.js,widget.css}         NEW  dependency-free vanilla widget
├── views/{webchat_templates,channel_message_views}.xml  NEW  demo page + read-only ops surfaces
├── security/  + identity & message ACLs (CRM read-only) + 2 company record rules
├── data/ir_cron.xml  + daily web-chat session GC
└── tests/{common_spine,test_channels,test_channel_wiring}.py   T50–T69 + T90–T94

health_care_command/                                 (→ 19.0.4.1.0 — the §3 list, nothing else)
├── models/care_conversation.py   _apply_signal() extracted; _capabilities() extracted
├── static/src/js/care_command.js sendChannel honours caps.ext_reply_channel;
│                                 sendMessage routes non-zalo/email to action_send_channel
└── tests/test_care_command.py    T42/T43 relaxed (forced — see deviation D6)
```

### What the phase actually changes for a user

Nothing, until somebody connects a channel. With zero connections
`_channel_keys()` returns the base four rails, the four adapter dock icons stay
dark, `ext_reply_channel` is absent and the composer degrades to its existing
zalo/email logic. That is the point of the phase: **traffic, not configuration,
is what makes a channel real.**

### Security properties actually implemented

- **Every webhook fails closed.** No platform app, no secret, no header, wrong
  signature, unknown Telegram path secret → reject. Verification runs over the
  RAW request bytes on a `type='http'` route, BEFORE any `su` escalation, and
  every rejection is the same generic answer (T50–T52, T93).
- **Meta's app secret is platform-plane.** One signature check per request,
  before tenant routing — the signature proves the sender is Meta, not which
  tenant the payload belongs to. Tenant resolution is by `phone_number_id` /
  page id afterwards, company-agnostic, then `with_company` for the ingest.
- **A verified webhook for a non-ingestable connection is dropped** with a 200
  and a `webhook_ignored` audit row: a disabled channel must not keep filling
  the inbox (T91d).
- **Redelivery is structurally idempotent**: partial unique
  `(connection_id, external_message_id)`, pre-checked in the funnel so the index
  never fires and poisons the webhook transaction (T54, T56).
- **The spine upsert runs in `cr.savepoint()`** — a database-level failure while
  touching `care.conversation` loses neither the message row nor the host
  transaction (T65 drives a real `SELECT 1/0`, not a Python raise).
- **One outbound trigger only**: a human pressing send. No auto-reply, no bot,
  no queue anywhere in the module.
- **Adapters never ingest another tenant's traffic**: `parse_inbound` filters on
  the connection's own resource id before anything is created.
- **No credentials, no real HTTP.** Every test mocks `requests.post`; nothing in
  this phase can reach Meta or Telegram. Zero credentials exist on vietuat.
- **CRM users read messages and identities, never credentials**; `*_enc` columns
  stay `base.group_system` + out of every view (T62).

---

## 2. Deviations from the handover (all declared)

| # | Handover said | Shipped | Why |
|---|---|---|---|
| **D1** | `care.channel.identity.display_name` Char | `peer_name` Char (raw) + `display_name` **stored compute** = `peer_name or external_id` | `display_name` is a built-in Odoo field (`compute='_compute_display_name'`). Redefining it as a plain stored Char merges with the base definition and can silently inherit the compute, dropping every write. The documented contract (`identity.display_name`) is unchanged. |
| **D2** | phase6 §2.6: pre-chat phone “passed as phone_normalized anchor at first message” | added `care.channel.identity.peer_phone` to carry it | There was nowhere to keep a volunteered phone between `/start` and the first message. It only ever feeds the phone anchor; it is never treated as provider-asserted identity. |
| **D3** | T55 “display name from profile” (Messenger) | display name is the PSID | The Messenger webhook carries no profile name; fetching one is a Graph `/{psid}` call, i.e. CC-E enrichment. Inventing a name would be dishonest; the PSID is what we actually know. |
| **D4** | Failed send → “message state failed + redacted error + clean UserError” | evidence is written on an **independent cursor** (`_persist_send_failure`), with the in-transaction twin as the fallback | A `UserError` from an RPC rolls the whole transaction back, so the failed row, the redacted reason and the lost `authorization_valid` check would all vanish exactly when they matter. Same idiom as health_emar `_persist_interaction_result` (ledger §5.12): fresh cursor first, bounded `lock_timeout`, skipped under `--test-enable` (a second cursor cannot see records the test transaction created — ledger §5.63), so exactly one failure path runs in each context. |
| **D5** | §2.6 CORS “from `wc_allowed_origins`” | same, plus the widget posts `Content-Type: text/plain` | Keeps every widget request a CORS *simple* request, so there is no preflight to mishandle on a public route. |
| **D6** | (not in the sanction list) | `health_care_command/tests/test_care_command.py` T42/T43 relaxed | **Forced.** Both P5 tests hard-assert all 8 channels in `active_channels` / `channel_counts`; dock honesty cannot ship without that changing (ledger §5.62 — the engine is right, the test is naïve; §5.49 precedent for a forced test edit). They now assert against `_channel_keys()` itself plus “the base four are always present”, so they hold with or without this module installed. |
| **D7** | (addition) | read-only backend list views + menu for `care.channel.message` / `care.channel.identity` | An operator needs to answer “did anything arrive at all” without a shell. `raw_payload` appears in no view. |
| **D8** | (addition, found in QA) | web-chat assets are served with a `?v=<module version>` stamp | Odoo serves `/<module>/static/…` with `max-age=604800` and no revalidation, so an unversioned embed would pin a stale widget on visitor browsers for a week after every upgrade. |

**Not needed (as the handover anticipated):** core touch #3. `_channel_keys()`
already existed as a hook at `care_conversation.py:547-552`; the override lives
entirely in the extension and the core file was not touched for it.

---

## 3. Test results (verbatim, vietuat, this pid)

```
2026-07-25 12:18:05,429 2021353 INFO vietuat odoo.tests.stats: health_care_command: 38 tests 7.89s 6511 queries
2026-07-25 12:18:05,429 2021353 INFO vietuat odoo.tests.stats: health_care_command_ai: 8 tests 1.72s 1522 queries
2026-07-25 12:18:05,429 2021353 INFO vietuat odoo.tests.stats: health_care_command_channels: 55 tests 10.69s 9723 queries
2026-07-25 12:18:05,429 2021353 INFO vietuat odoo.tests.stats: health_care_command_voip: 6 tests 0.52s 397 queries
2026-07-25 12:18:05,429 2021353 INFO vietuat odoo.tests.result: 0 failed, 0 error(s) of 91 tests when loading database 'vietuat'
EXIT:0   HTTP:200
```

91 = CC-A's 20 + CC-B's 25 (T50–T69, T90–T94) + the 46-test Care Command
regression set. TransactionCase only, **zero HttpCase** (§5.32), zero real HTTP,
zero credentials.

**Three genuine defects the first red run caught**, all fixed:

1. T42/T43 (deviation D6) — the §5.62 blast radius was wider than “tests that
   assert counts”: any pre-existing test naming a channel key breaks when the
   dock stops claiming all eight.
2. T90 hit `care_channel_message_conn_extid_uniq` because the mocked Telegram
   reply returned the same `message_id` twice — the dedupe index doing its job
   on a lazy fixture.
3. (Browser, below) the demo page's embed snippet was served as a live
   `<script>` element.

---

## 4. Browser evidence (`docs/strategy/reports/channel-center-phaseB-evidence/`)

End-to-end on care.biztinct.com, driven from the real entry point: demo page →
launcher → server-minted session + greeting → visitor message → **ops inbox as
the real `crm` user** (`get_workspace_data` → `get_conversation_detail` →
`action_send_channel`, the exact RPCs the composer calls) → the reply arrives in
the widget on the next poll. Console clean on the final run.

Two defects were found by that pass and fixed (both in `navigation.md` with the
console output that exposed them):

- **An XML-escaped `<script>` inside a QWeb template arch is served RAW.** The
  “embed snippet” loaded the widget a second time with `data-origin="…"`, which
  built a broken stylesheet URL. Fixed with `t-out` (escaped at render time), a
  `__h19WebchatLoaded` guard and a strict `data-origin` validator.
- **A QWeb template rooted at `<html>` is served with no doctype** → quirks
  mode. Fixed by rendering through `ir.qweb._render` and prepending
  `Markup('<!DOCTYPE html>')`; the first attempt used `str + Markup` and shipped
  a literal `&lt;!DOCTYPE html&gt;` (ledger §5.20, hit live again).

**Not in the pack:** the backend dock/composer/AI-patch screenshots. No login
credential for care.biztinct.com is available in this session (same as CC-A) and
I would not create or reset a privileged account to take a screenshot. The same
facts are proven server-side (`server-state.txt`) and through the real-CRM-user
transcript. Say the word with a login and I will take them.

---

## 5. Data honesty on vietuat

- After QA cleanup: **0 platform apps, 0 connections, 0 identities, 0 messages,
  0 readiness checks, 0 sessions** (counted `active_test=False`, ledger §5.27).
  2 `care.channel.audit` rows survive from the QA connection — the table is
  append-only and `connection_id` is `ondelete='set null'`, which is the
  designed behaviour, not residue.
- `_channel_keys()` therefore returns `('zalo', 'call', 'email', 'zns')`: the
  four adapter dock icons are dark for every real user, exactly as before this
  phase. Care Command's wall, counts and composer are otherwise unchanged.
- The QA fixtures (one web-chat connection, two identities, three messages, two
  conversations) were deleted and the deletion verified on a **fresh cursor**
  (§5.34). The demo page now renders its honest “not enabled yet” panel.
- Three crons registered and active: connection health (30 min), session purge
  (02:40), web-chat session GC (03:10).
- No pip installs. No PWA involvement (`care_command.js` is a backend asset), so
  no PWA version bump was due.

### Webhook URLs to hand ops

| Channel | URL | Credential it needs |
|---|---|---|
| WhatsApp Cloud | `https://care.biztinct.com/care_channels/meta/whatsapp/webhook` | Meta platform app (`channel.platform.app` provider `meta`): app secret via `action_set_secret`, `verify_token` in `extra_json`; per-tenant `resource_external_id` = phone_number_id, access token |
| Messenger | `https://care.biztinct.com/care_channels/meta/fb/webhook` | same app; per-tenant `resource_external_id` = page id + page token |
| Telegram | `https://care.biztinct.com/care_channels/telegram/webhook/<path_secret>` | bot token in `provider_secret_enc`, 32-byte `webhook_path_secret` (same value is the `setWebhook` `secret_token`) |
| Web chat | `https://care.biztinct.com/care_channels/webchat/demo` + the embed snippet on that page | none — one connection row and an `allowed_origins` setting |

**Ops config note:** `web.base.url` on vietuat is `http://care.biztinct.com`, so
the generated embed snippet says `http://` on an https site — a mixed-content
trap for a tenant who copy-pastes it. Fix the parameter, not the code.

---

## 6. New gotchas for the ledger (§5)

> **§5.64 — an XML-escaped `<script>` (or any markup) written as literal text
> inside a QWeb template arch is served to the browser RAW, as a live
> element.** The CC-B web-chat demo page printed its embed snippet as
> `<code>&lt;script src="…" data-origin="…"&gt;&lt;/script&gt;</code>`. Odoo
> served that as an actual `<script>` tag: the widget loaded twice, and the
> second instance read `data-origin="…"` (a literal ellipsis) and built
> `/care_channels/webchat/…/widget.css`, which 404'd with a MIME-type console
> error — the symptom pointed at the stylesheet, the cause was the snippet.
> Show markup as text with `t-out`/`t-esc` on a value passed from Python, never
> as escaped entities in the arch. Corollaries paid for in the same fix:
> (a) a QWeb template whose root is `<html>` is served with **no doctype**, so
> the browser renders in quirks mode — prepend one in the controller with
> `Markup('<!DOCTYPE html>') + html` (`str + Markup` ESCAPES the doctype and
> ships `&lt;!DOCTYPE html&gt;` — ledger §5.20 again);
> (b) Odoo serves `/<module>/static/…` with `Cache-Control: max-age=604800` and
> no revalidation, so any **embeddable** asset needs a `?v=<module version>`
> stamp or visitor browsers keep the old copy for a week (the PWA §3 rule,
> generalised); (c) any script meant to be embedded by third parties needs an
> idempotence guard and must validate its own `data-*` inputs.

> **§5.65 — a UserError from an RPC rolls back the evidence of the failure it is
> reporting; write that evidence on an independent cursor FIRST.** `action_send_channel`
> must both raise (so the agent sees a clean error) and remember (failed message
> row, redacted reason, `authorization_valid = fail` for a 401 so the connection
> falls to `action_required`). In-transaction writes cannot do both. Pattern:
> `_persist_send_failure` opens `Registry(db).cursor()`, sets
> `SET LOCAL lock_timeout = '2s'`, writes, commits, and returns True; the caller
> only writes in-transaction when it returns False. It returns False under
> `--test-enable` deliberately (§5.63: a second cursor cannot see the test
> transaction's records), which is what lets the suites assert on the same
> evidence. Test-side corollary: assert on that evidence with `try/except
> UserError`, **never** `assertRaises` — Odoo wraps it in a savepoint and rolls
> back every write made before the raise (§5.8).

> **§5.66 — derived readiness + a state-gated ingest can lock a channel out of
> the traffic that would prove it.** `INGESTABLE_STATES` is
> `{ready, expiring, testing, configuring}` (handover §2.3), but readiness is
> DERIVED: the first inbound on a `testing` connection whose required checks are
> not all `pass` demotes it to `action_required` — which is not ingestable, so
> later traffic is dropped until a human finishes setup. Implemented as
> specified and flagged for CC-C: the stepper must complete its checks (or park
> the connection in `configuring`) before pointing a provider at us. The
> alternative — letting `action_required` ingest — reopens the "a disabled
> channel keeps filling the inbox" hole the gate exists to close.

---

## 7. Deferred / next

- **CC-C** (Channel Connection Center UI) owns: the one-click web-chat enable
  (origins, embed snippet, live preview), the Telegram guided wizard, the
  tenant-admin ACL row, and the §5.66 stepper ordering above.
- `care.channel.connection.settings_json` / `api_base_override` are written by
  server paths only (`set_settings`, which refuses credential-shaped keys); they
  are deliberately NOT in `USER_WRITABLE`, so CC-C must go through actions.
- No Zalo / email / VoIP adapter work (CC-D/E/F); `parse_inbound` and
  `send_message` still raise `NotImplementedError` for those four keys.
- No media download, no Meta template messages, no bus/websocket web chat, no
  auto-merge of FB/Telegram identities with phone threads — all binding
  non-goals, all still true.
- Telegram header check: the `X-Telegram-Bot-Api-Secret-Token` header is
  verified **when present** (phase6 T52 semantics). The 32-byte path secret is
  the credential; a present-but-wrong header is a hard reject.
