# Channel Center — Phase CC-F: Email (OAuth) + Calls (VoIP24h)

**Fable → Opus handover, 2026-07-26.** Read `HANDOVER-CONVENTIONS.md` first
(§5.8, §5.32, §5.34, §5.55, §5.58, §5.61–§5.78 — **§5.74, §5.75 and §5.78 are
the ones that will bite this phase**), then `channel-center-architecture.md`
§3 (provider matrix), §4 (platform plane), §7, §12–§13, then the CC-A…CC-E
reports. This is the **last channel phase**: it closes the catalogue.

## 0. The two halves are not symmetrical — read this first

**Email is a real build.** `google_gmail` and `microsoft_outlook` are
**installed on vietuat** (verified 2026-07-26), Odoo ships working XOAUTH2
mixins, and the whole flow can be built and proven against mocks like every
phase before it.

**Calls is not, and must not pretend to be.** VoIP24h's documentation is
genuinely unreachable from outside Vietnam — I verified it myself rather than
taking it on trust: `docs.voip24h.vn` answers `ECONNREFUSED` from a
`203.162.56.x` (VN) address, and no third-party source documents their API.
So **every endpoint in `health_voip24h/services/voip24h_api.py` is unverified
and several look invented** (`{base}/auth/login`, `/calls/history`,
`/calls/{id}/recording`, `/calls/initiate`, `/extensions` — conventional REST
shapes, no evidence any of them exist). The live data agrees that nothing has
ever worked: **0 `voip.config` rows and 0 `voip_call_log` rows on vietuat.**

**Binding rule for the calls half: do not write, "fix", or design against any
VoIP24h HTTP path.** You have no contract, and inventing one is exactly the
manufactured-credential lie CC-D deleted (Z9) wearing a different hat. What
you CAN do is everything that does not depend on their API — see §3.

## 1. Scope

**A. Email — full self-service (the real work)**
1. `EmailAdapter` for real: OAuth via Odoo's own Gmail/Outlook mixins, mailbox
   as resource, outbound through `ir.mail_server`, inbound through
   `fetchmail.server` (IMAP poll — there is no webhook).
2. Center stepper: sign in → confirm the mailbox → send a test → done.
3. Readiness from real traffic: `outbound_ok` on a real send, `inbound_ok` on
   a real fetched message. No attestation buttons.

**B. Calls — adopt what exists, invent nothing**
4. Represent the existing `voip.config` as a `care.channel.connection`
   (the CC-D `zalo.config` facade pattern), so Calls appears in the Center
   with honest state instead of being invisible.
5. Route the **existing** `/voip24h/webhook` through the framework: connection
   lookup, `_may_ingest` gate, `_note_inbound` traffic-truth, audit. Its
   verification is already sound (raw bytes, HMAC-SHA256, `compare_digest`,
   fails closed on a missing secret) — **keep that verifier as-is**.
6. A Center card that tells the truth: "connected" means *we are receiving
   call events*, never "the API works" — because we cannot know that.
7. `docs/strategy/voip24h-contract-capture.md`: the exact list of facts a
   human on a VN connection must capture before CC-G could ever do outbound.

**Binding non-goals:** no new VoIP24h HTTP calls and no edits to
`voip24h_api.py`'s paths; no Instagram/Meta/Zalo work; no new public routes
(you adopt one, you add none); no edits to `health_care_command`; no
placeholder credentials; no changes to the 10-module ZNS contract; **no
touching `google_gmail`/`microsoft_outlook` core addons** — compose, never
patch.

## 2. Verified plumbing facts — do NOT re-derive

### 2.1 Email — what already exists (verified 2026-07-26)
- **Both OAuth addons are installed on vietuat**: `google_gmail` and
  `microsoft_outlook`, state `installed`. **0 `fetchmail.server` rows** — no
  inbound mail is configured today.
- Odoo's seams: `google_gmail/models/google_gmail_mixin.py` →
  `GoogleGmailMixin` (abstract), consumed by both `ir.mail_server` and
  `fetchmail.server`; `ir.mail_server.smtp_authentication` gains the value
  `'gmail'` (`ir_mail_server.py:16`), `fetchmail.server` gains
  `_check_use_google_gmail_service` (`fetchmail_server.py:23`). Microsoft is
  the same shape. **These mixins already do the token dance** — refresh
  included. Your adapter orchestrates them; it does not reimplement OAuth.
- **THE CREDENTIAL-PLANE CONFLICT (design decision, §3.1):** the Odoo mixins
  read `google_gmail_client_id` / `google_gmail_client_secret` from
  **`ir.config_parameter`** (`google_gmail_mixin.py:44-46`), which is a *third*
  credential plane next to our `channel.platform.app` and
  `care.channel.connection`. Resolve it as §3.1 says — do not silently create a
  fourth.
- **Email chat storage STAYS on `mail.message`** — the CC-D §2.3 precedent
  exactly. Core already has it: `_capabilities` sets `can_reply_email`
  (`care_conversation.py:789`), `_detail_timeline` reads `mail.message`
  (:886-945), and `action_send_email` (:1155-1194) posts via `message_post`
  with a validated recipient partner. **CC-F takes the boundary (authorization,
  readiness, the Center card), not the storage.** No `care.channel.message`
  rows for email chat; zero core edits.
- `EmailAdapter` stub (`services/adapters.py:1923-1941`) already declares
  `mode=MODE_OAUTH_POPUP`, `platform_providers=['google','microsoft']`,
  `resource_selection=False`, `webhook_auto=False`, `supports_refresh=True`,
  required checks `authorization_valid, resource_selected, outbound_ok,
  inbound_ok`. It extends `_StubAdapter` — **not** `_MetaAdapterBase`.
- Gmail's IMAP/SMTP scope is **restricted** → Google requires a CASA
  assessment (operator checklist §12.5). Like Meta, that is a human process:
  the card must read honestly until it is done.

### 2.2 Calls — what exists, and what is unknowable
- **The webhook is already good.** `health_voip24h/controllers/webhook.py:24`
  is `type='http'`, `auth='public'`, `csrf=False`, `save_session=False`, reads
  **raw bytes**, and `voip_config.py:422-442` verifies HMAC-SHA256 over those
  raw bytes with `hmac.compare_digest`, **failing closed when no secret is
  configured** and accepting a bare or `sha256=`-prefixed hex. Unknown
  `account_id` → generic `{'status':'ignored'}` 200 (non-oracle, stops
  retries). This is CC-D-grade already — **adopt it, do not rewrite it.**
- Credentials are `group_system`-gated Chars on `voip.config`: `api_key`,
  `api_secret`, `webhook_secret` (`voip_config.py:44-48, 95-99`) — plaintext
  columns, so migrating them onto the encrypted connection is real value.
  `account_id` is the routing key and carries `tracking=True` (fine — not a
  secret; do **not** add tracking to the three that are, per Z1).
- **Unverified/likely-invented**: `api_base_url` default
  `https://api.voip24h.vn/v1` (`voip_config.py:61-63`) and every path in
  `services/voip24h_api.py` (:56, 113, 156, 183, 232, 264). `cdr_sync.py`
  and the click-to-dial route (`controllers/api.py:19`) ride those paths.
  **Leave all of it exactly as it is.** No cron ships for `cdr_sync` today.
- Live state: **0 configs, 0 call logs.** Nothing regresses because nothing
  runs.

### 2.3 Framework rules this phase must obey
- §5.74 — never put a row lock around a fresh-cursor write. Email tokens are
  refreshed **by Odoo's mixins**, so you likely touch no token writer at all;
  if you do, use `_persist_refreshed_tokens` (already `lock_timeout`'d) and
  `_committed_secret` for anything single-use.
- §5.78 — **the one most likely to bite.** A required check that leaves `pass`
  demotes a `ready` connection to `action_required`, which is **not
  ingestable**. Email's `inbound_ok` comes from an IMAP **poll**: a mailbox
  that is simply quiet, or one fetch that fails, must **never** lower an earned
  `inbound_ok`. Latch it, exactly as CC-E's `provider_approvals` now latches.
  A real authorization loss is what `authorization_valid` is for.
- §5.75 — run tests with **`--workers=0`**, or every HttpCase errors in
  `setUpClass` and the run exits 1 with zero failures.
- Center endpoint pattern: `_center_group_ok()` on `@api.model` entries,
  `_center_get(conn_id)` → `_check_center_access()` before any sudo write.
  T107/T120/T138 are the spoof-test precedents — every new `conn_id` endpoint
  needs one.

## 3. Design decisions (binding)

### 3.1 The email credential plane
`channel.platform.app` provider rows `google` and `microsoft` remain the
**operator-facing truth** (client id + secret + `extra_json`). On install/first
use, the adapter **mirrors** them into the `ir.config_parameter` keys the Odoo
mixins read, and never the other way round. Rationale: the mixins are core
code we must not patch, and two writable sources of one secret is how they
drift. If a platform app row is absent, the card reads "Not available yet" —
same honesty as Meta and Zalo, and `center_begin` refuses.

### 3.2 Email flow
Sign-in reuses the **mixin's** authorization URL and callback (that is the
supported path and it already handles refresh) rather than our OAuth engine —
declare this as a deviation; our engine stays the rule for providers we speak
to directly. On success: create/attach an `ir.mail_server` (SMTP, XOAUTH2) and
a `fetchmail.server` (IMAP) owned by the connection, write
`resource_external_id` = the mailbox address, `authorization_valid` +
`resource_selected` pass. `outbound_ok` flips on a real successful send
(`center_test` → a synthetic mail to the tenant's own mailbox — **never a
patient address**). `inbound_ok` flips on the first fetched message, **latched
thereafter** (§5.78).

### 3.3 Calls: "connected" means received, never "the API works"
The Calls card is **receive-only** this phase and must say so in plain words.
`required_checks` for `call` become `webhook_verified` + `inbound_ok` **only** —
drop any check that would need an API call to prove, because we cannot prove
it. The stepper is a guided checklist (paste the webhook URL and secret into
the VoIP24h portal, then wait for a real call), not an OAuth flow. The card
carries one honest line: *"Sending and call history need VoIP24h's API, which
we cannot verify yet."*

### 3.4 The voip.config facade
Same shape as CC-D's zalo facade: soft coupling both ways (**no manifest
dependency edge in either direction** — §5.71: `health_care_command` already
depends on `health_zalo`, and a new edge into `health_voip24h` risks the same
unbuildable loop; verify the graph before adding *any* dep), join on
`(channel='call', company)`, migration triggered from the channels module
because it loads last, idempotent, nothing deleted. Migrate the three
plaintext secrets onto the encrypted connection; leave the legacy columns
readable so existing code keeps working.

### 3.5 The contract-capture doc
`docs/strategy/voip24h-contract-capture.md` — a checklist a non-engineer on a
VN connection can complete: base URL, auth scheme (header? bearer? login
endpoint?), the real CDR/history path and its pagination, the recording
download path and its auth, click-to-dial (if it exists at all), the webhook
event catalogue with a **real captured payload**, the exact signature header
name and the string that is signed, and whether the portal or support sets
the webhook URL. State plainly that until this is filled in, outbound calling
and CDR sync remain unimplementable.

## 4. Tests (T142–T155, `tests/test_email_center.py` + `tests/test_call_center.py`)
All HTTP/IMAP/SMTP mocked; §5.8 try/except for nothing-stored paths; §5.70 no
exception tuples in `assertRaises`; §5.76 patch with plain functions, never a
second `autospec`.

- **T142** no platform app ⇒ email card "Not available yet", `center_begin`
  refuses (this IS vietuat today — assert it).
- **T143** platform app mirrors into the mixin's config params, once, and the
  reverse never happens; the secret never reaches a return value.
- **T144** sign-in success creates the mail + fetchmail servers, sets the
  mailbox as resource, passes `authorization_valid`/`resource_selected`;
  failure stores nothing.
- **T145** `center_test` sends to the tenant's own mailbox, flips
  `outbound_ok`; a send failure writes redacted evidence (§5.65) and does not
  lie about state.
- **T146** first fetched message flips `inbound_ok` → `ready` and lights the
  dock; **T147** a later quiet poll / failed fetch does **NOT** lower it and
  does **NOT** demote a `ready` connection (§5.78 — drive it to `ready` first,
  or the test cannot see the demotion).
- **T148** email chat still flows through `mail.message` + core
  `action_send_email`; zero `care.channel.message` rows for email.
- **T149** revoke/disconnect stops traffic without deleting history or wiping
  credentials; reconnect does not re-ask.
- **T150** calls: the existing verifier still refuses a bad/missing signature
  and an unconfigured secret (port the assertions, prove no regression).
- **T151** a verified call event routes to the right connection, `_note_inbound`
  flips `webhook_verified`+`inbound_ok`, a non-ingestable connection drops it
  with a `webhook_ignored` audit.
- **T152** the calls facade migration is idempotent: one connection per active
  `voip.config`, secrets encrypted onto it, legacy columns untouched, re-run
  creates nothing.
- **T153** the Calls card is honest: receive-only wording present, no check
  requiring an API call, `center_test` refuses with the "we cannot verify
  their API" message rather than calling anything.
- **T154** spoof: plain CRM user + cross-company on every new endpoint.
- **T155** regression: the catalogue is still 8 cards in dock order, and
  telegram/webchat/zalo/whatsapp/fb steppers are unaffected (the `oauth_popup`
  branch is now shared by zalo + email — **re-check the CC-E `isZalo` re-key
  still keys correctly** and email does not inherit Zalo's copy).

## 5. Deploy + evidence
Service `odoo-server`, conf `/etc/odoo-server.conf`, addons
`/odoo/odoo-server/addons/`. Stop the service **and drain workers** before
`odoo-bin` (`until` loop on the process count), then
`--test-enable --stop-after-init --workers=0 --http-port=8169
--logfile=/tmp/ccf_run.log`. Green = EXIT:0 + `0 failed, 0 error(s)` +
zero `FAIL:`/`ERROR: setUpClass`. Evidence: live curls (the VoIP webhook still
403s a bad signature and 200-ignores an unknown account; no new public route
exists), the catalogue as the real `crm` user's own RPC returns it, and a
browser pass from the login page through the CMS sidebar (**login `crm` — ask
the user for the password; never create or reset an account**). With no
platform app the email stepper cannot be driven, so the honest browser
evidence is the *catalogue* showing Email "Not available yet" and Calls
receive-only — capture that and say plainly what is unproven. Data honesty:
0 platform apps, 0 voip configs, 0 call logs, 0 fetchmail servers.

## 6. Report back
Deviations (D-numbered); data-honesty table; ledger entries added; test tally;
evidence paths; and an explicit statement of what remains blocked on a human
(Google CASA assessment, the VoIP24h contract capture). **Do not claim Email
or Calls "works".**

---
**Kickoff line:** Implement `docs/strategy/handovers/channel-center-phaseF.md`
(Channel Center Phase CC-F — Email OAuth via Odoo's Gmail/Outlook mixins with
latched `inbound_ok`, plus Calls as a receive-only VoIP24h facade that adopts
the existing fail-closed webhook and invents NO API paths, plus the
contract-capture doc; T142–T155). Read HANDOVER-CONVENTIONS.md
(§5.61–§5.78 — §5.74/§5.75/§5.78 especially), architecture §3/§4/§7/§12-13,
and the CC-A…CC-E reports first. VoIP24h's docs are unreachable outside
Vietnam (verified) — every endpoint in `voip24h_api.py` is unverified, so do
not write, fix, or design against any VoIP24h HTTP path. Email chat stays on
`mail.message`; zero core edits; all I/O mocked; run tests with `--workers=0`;
deploy + evidence per §5; report deviations and data honesty.
