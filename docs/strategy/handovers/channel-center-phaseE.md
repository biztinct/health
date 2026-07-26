# Channel Center — Phase CC-E: Meta (WhatsApp + Messenger)

**Fable → Opus handover, 2026-07-26.** Read `HANDOVER-CONVENTIONS.md` first
(§5.8, §5.32, §5.34, §5.55, §5.58, §5.61–§5.74 — **§5.74 is new and this
phase's most expensive trap**), then `channel-center-architecture.md` §3
(provider matrix), §4 (platform plane), §7 (secrets/OAuth/webhooks), §11–§12,
then the CC-A/B/C/D reports. This phase makes **Meta the second and third
self-service channels** on the framework CC-A–CC-D built.

## 0. Read this before you plan anything

**Meta cannot be proven live on vietuat this phase, and that is expected.**
A Meta connection needs a Business-type app, Business Verification, App
Review of five permissions with screencasts, and two Facebook-Login-for-
Business configurations — a multi-week human process (operator checklist
§12.1–§12.4) that has not started. There are **0 `channel.platform.app` rows
on vietuat** (verified 2026-07-26).

So CC-E ships **software-complete, provably correct against mocks, and
honestly dark** — exactly as CC-D shipped Zalo. Do NOT seed a placeholder
platform app to make a screenshot possible: a fake app id is the same
manufactured-credential lie CC-D just deleted from health_zalo (Z9), and the
Center already renders "Not available yet" correctly when the plane is empty
(that honesty is itself the deliverable, asserted by T97). If you find
yourself wanting to invent a credential to demo something, stop and report.

## 1. Scope

1. **WhatsApp Embedded Signup (ES v4)**: JS SDK popup → code → exchange →
   WABA + phone-number selection → `POST /{waba}/subscribed_apps` → send test.
2. **Messenger (FLB)**: login popup → code → long-lived page tokens via
   `/me/accounts` → Page picker → `POST /{page}/subscribed_apps`.
3. **Pending-approval surfacing**: business verification, display-name review
   and template approval are *provider* states, not our errors — they render
   as `provider_approvals` checks with plain-language copy, never as failures.
4. **WhatsApp template send path**: outside the 24 h customer-service window,
   only an approved template may go out — the composer must know this and say
   so rather than letting a send fail at Meta.
5. Center steppers for both channels; `CENTER_IMPLEMENTED_CHANNELS` gains
   `whatsapp` and `fb`.

**Binding non-goals:** no Instagram (a separable permission set, architecture
§12 — explicitly out), no Email/VoIP24h (CC-F), no changes to the existing
Meta webhook controller's verification (CC-B shipped it fail-closed and CC-D
did not touch it), no new public routes, no edits to `health_care_command`,
no real Meta credentials anywhere, no placeholder platform app.

## 2. Verified plumbing facts — do NOT re-derive

### 2.1 What already exists and works (verified 2026-07-26)
- **The Meta webhook is already live and fail-closed**: `controllers/meta.py`
  — `/care_channels/meta/<string:channel>/webhook`, GET handshake (:44) and
  POST (:66), `type='http'`, raw bytes, platform-plane HMAC **before** tenant
  routing. CC-B built it; T50/T93 cover it. **Do not rewrite it.** Your job is
  to make connections exist for it to route to.
- **Both adapters are registered stubs** with correct capabilities:
  `WhatsAppAdapter` (`services/adapters.py:318+`, `mode=MODE_EMBEDDED_SIGNUP`,
  `platform_providers=['meta']`, `webhook_auto=True`, required checks incl.
  `scopes_granted` + `provider_approvals`) and `MessengerAdapter` (:415+,
  `mode=MODE_OAUTH_POPUP`). **Both already implement `parse_inbound` and
  `send_message` (CC-B).** CC-E adds only the *onboarding* half:
  `authorize_url` / `handle_callback` / resource listing / `subscribe_webhook`.
- **The OAuth engine is proven** (CC-D was its first real consumer): hashed
  single-use state + PKCE, `create_for` returns the raw state exactly once,
  `_handle_callback(provider, params)` burns the state then calls
  `adapter.handle_callback(session, params)` inside a savepoint, and renders
  generic non-oracle pages. Callback route `/channel_hub/oauth/callback/meta`
  needs **no new code** — the `<provider>` segment already routes.
- **Platform plane**: `channel.platform.app` provider `meta` exists
  (`channel_platform_app.py:34`); `extra_json` (:58) is the sanctioned home
  for the two **non-secret** config ids, read via `_get_extra(key, default)`
  (:125). `_get_for_provider('meta')` + `_get_secret()` are the accessors.
  Keys to use: `es_config_id` (WhatsApp) and `flb_config_id` (Messenger).
- **Center endpoint pattern** (clone exactly): `@api.model` +
  `_center_group_ok()` on entry points, `_center_get(conn_id)` →
  `_check_center_access()` (group + company) before any sudo write. T107/T120
  are the spoof-test precedents — **every** new `conn_id` endpoint needs one.
- **Adapter HTTP helpers**: `_get`, `_post`, `_form_post` (CC-D) all raise
  `ChannelSendError` and are the ONLY place adapters touch the network —
  `mock_get`/`mock_post` patch exactly there, so no test can escape the box.
- **`_is_auth_failure(error)`** (CC-D, `adapters.py`) already classifies
  transient-vs-auth failures. Reuse it; do not write a second classifier.

### 2.2 §5.74 — the trap that will bite this phase
CC-D's review found that `_with_refresh_lock` (now an **advisory** lock) and
`_persist_refreshed_tokens` (independent cursor) deadlocked when combined,
losing the very grant they protected. Both are now correct **and Meta must
use them the same way**: Meta long-lived tokens do not expire by default, so
CC-E's rotation surface is smaller — but if you touch any token-writing path,
route it through `_persist_refreshed_tokens` (which now sets
`SET LOCAL lock_timeout`) and read single-use material through
`_committed_secret`. Never re-introduce a row lock around a fresh-cursor
write. T125/T126 are the pattern.

### 2.3 Meta provider facts (verified 2026-07-25, architecture §3)
- **Graph v21.0** is pinned in `adapters.py:47`; **Embedded Signup v4** is
  current (v2 dies 2026-10-15).
- **WhatsApp ES**: the JS SDK returns an **authorization code**; exchange it
  at `GET /v21.0/oauth/access_token` with `client_id`/`client_secret`/`code`
  → a **Business Integration System User (BISU) token that never expires**.
  Then `GET /v21.0/debug_token` for granted scopes, `GET /{business}/owned_whatsapp_business_accounts`
  or the ES response for the WABA, `GET /{waba}/phone_numbers` for the number
  picker, `POST /{waba}/subscribed_apps` to register the webhook.
- **Messenger FLB**: same code-exchange, then `GET /me/accounts` for pages,
  each carrying a **non-expiring page access token**; `POST /{page}/subscribed_apps`
  with the field list. Route inbound by `page_id` (CC-B's controller already
  does — verify the resource id it looks for matches what you store).
- **Outbound rules that must reach the UI**: WhatsApp 24 h customer-service
  window, outside which only an approved template may send; Messenger 24 h
  window with **only `HUMAN_AGENT` (7 d) surviving** since 2026-04-27 — the
  other tags are dead and must not be offered.
- **Unverified-business cap**: 10 tenant onboardings per 7 days.
- **PKCE**: not applicable to Meta's server-side code exchange (`code_verifier`
  is not accepted). The engine's state is still single-use and mandatory —
  pass the verifier through unused rather than disabling PKCE storage.

### 2.4 vietuat data honesty (verified 2026-07-26)
0 platform apps, 1 connection (the CC-D zalo `legacy` row, no credentials),
0 identities, 0 messages. Nothing in CC-E changes any of that. Say so.

## 3. Server work

- `services/adapters.py` — `WhatsAppAdapter` + `MessengerAdapter` gain:
  `authorize_url(session, state, ...)` (FLB dialog URL for Messenger; for
  WhatsApp the ES popup is SDK-driven so this returns the config payload the
  JS needs, not a redirect), `handle_callback(session, params)` (exchange →
  `debug_token` scope read → store token → `scopes_granted` check),
  `list_resources()` (WABA+numbers / pages), `select_resource(external_id)`,
  `subscribe_webhook()` (`POST /{id}/subscribed_apps`), `health_check()`.
  A missing/incomplete scope set ⇒ `scopes_granted` **fail** with the
  plain-language list of what Meta withheld — never a silent partial connect.
- `models/channel_center.py` — `center_meta_start(channel)` (returns app id +
  the right config id + state; **never the app secret**),
  `center_meta_exchange(conn_id, code)` (ES path — the SDK hands the code to
  the browser, so this endpoint takes it; gate it exactly like
  `center_telegram_validate` and treat the code as credential material:
  never log it, never echo it), `center_meta_resources(conn_id)`,
  `center_meta_select(conn_id, external_id)`, `center_meta_subscribe(conn_id)`.
  Add `whatsapp`/`fb` to `CENTER_IMPLEMENTED_CHANNELS`.
- **Approvals as first-class state**: a new `_center_approvals(conn)` returning
  plain-language rows (business verification, display name, templates) derived
  from `debug_token` + WABA fields — rendered on the card, never as an error
  dialog. `provider_approvals` stays `pending` until Meta says otherwise.
- `static/src/center/` — ES needs the **Meta JS SDK**, which is an external
  script: load it only on the WhatsApp stepper, never in the base bundle, and
  the stepper must degrade to an honest "this needs Meta's popup, which your
  browser blocked" message. No SDK call may receive the app secret.

## 4. Tests (T127–T140, `tests/test_meta_center.py`)
All HTTP mocked; §5.8 try/except for nothing-stored paths; §5.70 for dual-class
raises; §5.74 patterns if any token write is touched.
T127 ES start payload (app id + es_config_id, **no secret**, state single-use).
T128 code exchange happy path (token encrypted `chs$1$` at SQL level, scopes
recorded, nothing echoed). T129 exchange refusals store nothing. T130 partial
scopes ⇒ `scopes_granted` fail + honest list, connection NOT ready.
T131 WABA/number listing + selection writes resource fields.
T132 `subscribed_apps` success ⇒ `webhook_configured` pass; failure ⇒ redacted
evidence + no state lie. T133 Messenger `/me/accounts` page picker + per-page
token stored encrypted. T134 inbound routes to the right connection by
`phone_number_id` / `page_id` (reuse CC-B's `_dispatch_meta`).
T135 24 h window: outside it, the composer refuses a free-form send and offers
the template path; `HUMAN_AGENT` is the only Messenger tag offered.
T136 approvals render as pending, never as failure; `provider_approvals`
never auto-passes. T137 no-platform-app ⇒ both cards "Not available yet" and
`center_begin` refuses (this is the vietuat state — assert it directly).
T138 spoof: plain CRM user + cross-company on every new endpoint (clone T120).
T139 catalogue still 8 cards in dock order with correct availability.
T140 regression: Zalo/Telegram/webchat steppers unaffected.

## 5. Deploy + evidence
Service `odoo-server`, conf `/etc/odoo-server.conf`, addons
`/odoo/odoo-server/addons/`. **Stop the service AND drain workers before
`odoo-bin`** (`until` loop on the process count — a lingering worker gives
`Address already in use`, EXIT:1, and no tests), then
`--http-port=8169 --logfile=/tmp/cce_run.log`. Green = EXIT:0 + zero
`FAIL: `/`ERROR: Test` + per-module stats lines; a missing
`odoo.tests.result` line alone is NOT a failure on this build. Evidence:
the test tally, live curls showing the Meta webhook still refuses unsigned
POSTs (403) and answers the GET handshake correctly, the catalogue as the
real `crm` user's own RPC returns it, and Vietnamese runtime checks.
**Browser pass: a login now exists (`crm`, ask the user for the password —
do NOT create or reset an account).** With no platform app the Meta steppers
cannot be driven, so the honest browser evidence is the *catalogue* showing
both cards correctly "Not available yet" — capture that, from the login page
through the CMS shell (§5.69), and say plainly that the stepper itself is
unproven pending operator provisioning.

## 6. Report back
Deviations (D-numbered) with reasons; data-honesty table; what remains blocked
on Meta's human processes (be specific — which of §12.1–§12.4); ledger entries
added; test tally; evidence paths. Do not claim WhatsApp or Messenger "works".

---
**Kickoff line:** Implement `docs/strategy/handovers/channel-center-phaseE.md`
(Channel Center Phase CC-E — Meta: WhatsApp Embedded Signup v4 + Messenger
FLB onboarding, WABA/phone and Page pickers, `subscribed_apps` webhook
registration, approvals-as-state, the 24 h window + template send path,
T127–T140). Read HANDOVER-CONVENTIONS.md (§5.8/§5.32/§5.34/§5.58/§5.61–§5.74
— §5.74 especially), architecture §3/§4/§7/§12, and the CC-A/B/C/D reports
first. Meta cannot be proven live (0 platform apps, business verification not
started) — ship software-complete and honestly dark, and never seed a
placeholder credential. All HTTP mocked; deploy + evidence per §5; report
deviations and data honesty.
