# Channel Center — Phase CC-F report (Email + Calls)

**Shipped 2026-07-26, commit `7a4a9b02`, `health_care_command_channels`
19.0.6.0.0 + `health_voip24h` 19.0.2.0.1, live on vietuat.**
Implemented by Opus (Fable's budget was exhausted), with the review gate
retained and run independently afterwards.

The catalogue closes: all eight channels are now implemented. Two of them
still read "Not available yet" and one reads "receive only" — and that is the
result, not a shortfall.

## 1. What shipped

### Email — a real build that orchestrates Odoo's own OAuth

`google_gmail` and `microsoft_outlook` were already installed and already ship
working XOAUTH2 mixins: they mint the consent URL, run a CSRF-checked
callback, store the refresh token and renew the access token before every SMTP
and IMAP login. CC-F **orchestrates** them. Re-implementing that dance on our
own OAuth engine would have added a second, weaker door to the same mailbox —
so this phase took the boundary (which platform app, which mailbox, what is
proven, what the tenant sees) and left the protocol where core supports it.

- **The third credential plane, resolved explicitly.** The mixins read their
  client id and secret from `ir.config_parameter`. `channel.platform.app`
  stays the operator-facing truth and is mirrored **into** those keys, one
  way, never back (T143 asserts both directions).
- **The connection owns its servers.** An `ir.mail_server` (SMTP) and a
  `fetchmail.server` (IMAP) carry a `care_connection_id`. That ownership is
  load-bearing, not cosmetic — see §3.1.
- **`inbound_ok` latches.** Nothing writes it to anything but `pass`.
- **Email chat is untouched**: `mail.message` and core `action_send_email`,
  zero `care.channel.message` rows, zero core edits.

### Calls — receive-only, and the card says so

VoIP24h's documentation is unreachable from outside Vietnam and every path in
`services/voip24h_api.py` is an unevidenced guess. So this phase calls nothing
of theirs.

- Their `/voip24h/webhook` was **adopted, not rewritten** — it was already the
  fail-closed posture §5.61 tells every other module to clone. CC-F adds only
  routing: resolve the connection, honour `_may_ingest()`, `_note_inbound()`,
  audit the drops. **No new public route.**
- `voip.config` became a facade: the webhook secret is read from the encrypted
  connection first, an idempotent migration encrypt-copies the three plaintext
  secrets, nothing is deleted.
- `required_checks` is `webhook_verified` + `inbound_ok` and nothing else. A
  check that would need an API round trip is a demand we have no way to test.
- `docs/strategy/voip24h-contract-capture.md` lists what a human on a
  Vietnamese connection must capture before outbound could exist.

## 2. Deviations

| # | Deviation | Why |
|---|---|---|
| **D1** | Sign-in uses the **mixin's** authorization URL and callback, not our OAuth engine. | Sanctioned by the handover (§3.2). It is the supported path and it already handles refresh. |
| **D2** | The mail + fetchmail servers are created **before** the sign-in, not after it. | Forced. The mixin's consent URL puts `{"model","id","csrf_token"}` in its `state`, so the rows must already have ids. The handover's §3.2 ordering assumed our own engine. |
| **D3** | The email refresh token lives on the **core server rows** (`base.group_system` Char columns), not in our AES-GCM `*_enc` columns. | The mixin can only read its own field. Copying the token would create a second plaintext-equivalent store for no gain. Called out honestly: this is the one credential in the phase that is *not* encrypted at rest, and it is core's own storage. |
| **D4** | Channel-owned mail servers are **excluded from the default-sender search** (`_find_mail_server_allowed_domain`). | Safety, see §3.1. Consequence: a connected mailbox is used for the connection test and for explicit sends, but Care Command's ordinary reply path still uses the deployment's default server. Routing replies per company is **not** in this phase. |
| **D5** | `_sync_from_connection` **creates** a `voip.config` when none exists (the CC-D zalo facade only updated one). | `process_call_event` resolves the config by `account_id` and `voip.call.log.voip_config_id` is required. Without it a tenant would finish the stepper, see events arrive, watch the card turn Connected — and get zero call logs. |
| **D6** | The web-chat stepper branches were re-keyed from `mode === 'one_click'` to `isWebchat` even though web chat is still the only one-click channel. | Same class of bug as §5.82, one channel away. Cheap now, invisible later. |

## 3. Three things the handover had wrong or missing

### 3.1 Creating one `ir.mail_server` would have hijacked all outgoing mail

`_find_mail_server`'s **step 4 returns `mail_servers[0]` even when no
`from_filter` matched**. vietuat has **zero** `ir.mail_server` rows, so the
first mailbox any clinic connected through this self-service wizard would have
become the sender of every outgoing email in the database — invoices, password
resets, other tenants' notifications. Closed with core's own
`_find_mail_server_allowed_domain` hook, verified live to compose with (not
replace) core's existing clause. A high `sequence` alone would **not** have
been enough; it reorders the fallback, it does not remove the record from it.
Ledgered as **§5.79**.

### 3.2 The CDR cron ships active — the handover said none ships

Three crons ship in `data/voip24h_cron.xml`, all `active=True`, and `ir_cron`
id 133 is enabled on vietuat right now. It has simply never *done* anything,
because it selects on `auto_sync_enabled = True AND state = 'connected'` and
there are zero `voip.config` rows. That made D5's create the dangerous line of
the phase: `auto_sync_enabled` **defaults True**, so a row written with model
defaults would have started calling `https://api.voip24h.vn/v1/calls/history`
— an invented path — every fifteen minutes. The row is created `draft`, with
auto-sync off, and with `api_key`/`api_secret` deliberately **empty**
(T152b asserts exactly this). Ledgered as **§5.81**.

**Correction found in the self-review (see §7).** The first version of this
report — and the commit message — claimed `_check_credentials()` was what kept
every unverified endpoint unreachable. That was **not true**:
`services/cdr_sync.py:27` constructs `VoIP24hAPI(config)` directly, and
`cron_sync_call_history` calls it **without** `_check_credentials()` (the
interactive button and the wizard both do check). So the only thing protecting
a Center-created row was the cron's domain — two editable booleans away from
letting it through. Fixed by moving the guard into `sync_call_history` itself,
where every caller inherits it (T150d).

### 3.3 The stepper trap CC-E half-fixed

CC-E re-keyed the Zalo screens off `mode === 'oauth_popup'` because email was
about to join that mode. The other side was still open: `call` joining
`guided_secret` would have asked a clinic for a "Bot key" and pointed it at
@BotFather. Every stepper branch is now keyed on a channel, asserted
structurally in T155b. Ledgered as **§5.82**.

Also **§5.80**: an Odoo `fields.Integer` is an int4, and a nines-sentinel in a
fixture poisoned the transaction and errored seven tests whose messages named
none of the cause.

## 4. Forced test edits (§5.62's family)

Four pre-existing assertions encoded "call is not implemented", which is
precisely what this phase changes. The engine is the deliverable; the tests
moved, each with a `FORCED EDIT (CC-F)` comment saying why:

- `test_center.py` T97 — `call.implemented` False → True, plus the new notice.
- `test_center.py` T104 — `call` left the `unimplemented` list and joined the
  positive idempotence loop.
- `test_meta_center.py` T139 — same as T97.

`email` stayed in every "refused" list: it is implemented but not *available*,
because no platform app exists. That distinction is the point.

## 5. Verification

`--workers=0` (§5.75). **EXIT:0, HTTP:200,
`0 failed, 0 error(s) of 127 tests`**, zero `FAIL:` / `ERROR:` lines. Channels
went 100 → 130 test methods.

Live webhook curls (temporary config, deleted afterwards): unknown account
`200 {"status":"ignored"}`, missing signature `403`, wrong signature `403`
(identical body — no oracle), bad JSON `400`, valid HMAC `200 success`.

Browser pass from the **login page** through the CMS sidebar as the real `crm`
user (§5.69): Email reads "Not available yet", Calls carries the receive-only
sentence on the card without opening anything, and the Calls stepper shows its
own copy. Zero console errors. Screenshots and full output in
`channel-center-phaseF-evidence/`.

## 6. Data honesty

0 platform apps · 0 `voip.config` · 0 `voip.call.log` · 0 `fetchmail.server` ·
0 `ir.mail_server` · 0 call connections · 0 email connections. The facade
migration reports `{'created': 0, 'existing': 0, 'copied': 0}` and is
idempotent on re-run.

**Neither half of CC-F has ever carried real traffic**, and no test in this
phase reached a network. Email is proven against Odoo's real mixin computation
(the consent URL is built, not mocked) and against a real `message_process`
round trip; the only mocked call is `ir.mail_server.send_email`. Calls is
proven against real HTTP requests to the live route.

## 7. Review gate — findings and fixes

The methodology's review gate was run after the fact because the implementer
and the designer were the same session this time. Two findings, both mine, both
fixed in the same commit with the suite re-run (**EXIT:0,
`0 failed, 0 error(s) of 129`**, channels 130 → 132 methods):

**F1 (MED, correctness) — two independent answers to "which connection owns
this account", and they can disagree.** The webhook router resolves by
`account_id` (company-agnostic, which is right — the provider addresses us by
account). `voip.config._channel_connection()` resolved by **company**. Where a
company's Calls connection has claimed account *Y* and an event arrives for
account *X*, the config would hand back the *Y* connection and verify *X*'s
event with *Y*'s secret — and gate ingest on *Y*'s state. Fail-closed, so not
an accepted-forgery hole, but wrong. Fixed three ways: `_channel_connection`
now resolves by account id first, **refuses** to fall back to a connection that
has claimed a different account, and the controller passes the connection it
actually routed to into both the verifier and the gate so there is only one
answer. T150c.

**F2 (MED, and it invalidated a claim in this report) — the cron path into the
unverified VoIP24h API had no credential gate.** See the correction in §3.2.
Fixed by moving `_check_credentials()` into `sync_call_history`. T150d.

An independent review subagent was launched three times; the first two died on
API-capacity errors (529) and the third was still running when this report was
written. Its findings, if any, will be applied on top. **That is a real gap in
this phase's assurance and is stated rather than glossed:** the review that
found F1 and F2 was the author's own, which is exactly the arrangement the
methodology exists to avoid.

## 8. Blocked on a human

1. **The VoIP24h contract capture** — `docs/strategy/voip24h-contract-capture.md`.
   Someone on a Vietnamese connection must fill it in. Until then outbound
   calling, CDR sync and recording download stay unimplementable, and
   `voip24h_api.py` stays untouched: it is not "nearly right", it is
   unverified.
2. **A Google CASA assessment** — Gmail's IMAP/SMTP scope
   (`https://mail.google.com/`) is restricted, so Google requires a security
   assessment before a production app may use it. Multi-week, like Meta's App
   Review. Microsoft 365 has no equivalent gate.
3. **Seeding a `google` or `microsoft` platform app** — until an operator does,
   the email card correctly refuses.

**Do not read this report as "Email works" or "Calls works."** Email is
software-complete against mocks and cannot be exercised without a platform
app. Calls can receive and cannot send, by design.
