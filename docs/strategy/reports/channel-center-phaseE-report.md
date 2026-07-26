# Channel Center — Phase CC-E report (Meta: WhatsApp + Messenger)

**Opus → Fable, 2026-07-26.** Handover:
`docs/strategy/handovers/channel-center-phaseE.md`. Commit `15b3a919` on
branch `19.0`. Module `health_care_command_channels` **19.0.5.0.0**, live on
vietuat. Evidence pack:
`docs/strategy/reports/channel-center-phaseE-evidence/`.

**Status: software-complete, provably correct against mocks, honestly dark.**
WhatsApp and Messenger do not work on vietuat and this report never says they
do. There are **0 `channel.platform.app` rows** on the server, so both cards
read "Not available yet", `center_begin` refuses, and the steppers cannot be
driven at all. No placeholder credential was seeded anywhere.

---

## 1. What was built

| File | Change |
|---|---|
| `services/adapters.py` | `_MetaAdapterBase` (platform lookup, code exchange, `debug_token`, `subscribed_apps`, approval cache, `_store_tokens`); `WhatsAppAdapter` + `MessengerAdapter` gain their whole onboarding half; `meta_window_state()`; `_meta_error()`, `_meta_approval_status()`; `MessengerAdapter.send_message` gains `tag=` |
| `models/channel_center.py` | `center_meta_start / _exchange / _resources / _select / _subscribe / _approvals / _templates`; `_center_meta`, `_center_approvals`, `_center_window`; approval + window vocabularies; real WhatsApp/Messenger stepper copy; `center_test` respects the window; `CENTER_IMPLEMENTED_CHANNELS` += `whatsapp`, `fb`; `IMPLEMENTED_MODES` += `embedded_signup` |
| `models/care_conversation_ext.py` | `_channel_window()` + RPC `channel_send_window`; `channel_templates`; `action_send_channel_template`; `action_send_channel` refuses / tags per the window; `_capabilities()` gains `ext_window` |
| `models/care_channel_audit.py` | two event tags: `webhook_failed`, `approvals_refreshed` |
| `static/src/center/channel_center.js` | on-demand Meta SDK loader, ES `FB.login` wrapper, `WA_EMBEDDED_SIGNUP` postMessage listener (origin-checked), FLB popup, resource picker, subscribe, approvals; `_watchPopup` generalised; channel predicates |
| `static/src/center/channel_center.xml` | `oauth_popup` branches re-scoped to `isZalo`; four Meta screens + footer buttons; approval rows on the card and in the manage panel |
| `static/src/center/channel_center.scss` | picker + approval-status styles |
| `tests/test_meta_center.py` | **new** — T127–T140 |
| `tests/common_spine.py` | canonical payload timestamps are now relative to now |
| `tests/test_center.py` | T104 forced edit (below) |
| `i18n/vi.po` | +64 entries; 185 python + 75 web translations live |
| `__manifest__.py` | 19.0.4.0.0 → 19.0.5.0.0 + CC-E description |

No new public route. No edit to `health_care_command`. No edit to the CC-B Meta
webhook controller. No Instagram.

---

## 2. Deviations

**D1 — `center_meta_exchange` takes the state, and burns it.** The handover's
signature was `center_meta_exchange(conn_id, code)`, but T127 requires the
authorization state to be single-use and nothing else in the ES path consumes
it (the SDK returns its code to the *browser*, so no OAuth callback fires).
Shipped as `(conn_id, code, state, resource_hint=None)`: the state is
`_consume`d, and an unknown / used / expired / foreign state is ONE generic
refusal — "This sign-in has expired" — so the endpoint is not an oracle. Without
this the state would have been decorative.

**D2 — the Messenger user token lives in `refresh_token_enc`.** `access_token`
is what `send_message` spends, and a user token cannot send as a Page — but the
Page picker needs the user token again on every re-list. Meta has no refresh
token at all (`supports_refresh: False` for both channels, the long-lived path
does not expire), so the column is otherwise dead. The user token goes there,
encrypted identically, and `access_token_enc` stays EMPTY until a Page is
chosen — which is why an un-picked Messenger connection correctly refuses to
send. Named misleadingly; the alternative was a schema change for one slot.

**D3 — `get_extra`, not `_get_extra`.** The handover cited
`_get_extra(key, default)` at `channel_platform_app.py:125`. The method is
public: `get_extra`. Used as it exists (ledger §5.59).

**D4 — `resource_hint` added to the exchange.** The ES popup announces its
`waba_id` / `phone_number_id` through `postMessage`; both are public provider
ids, both are validated `isdigit()` server-side before touching a Graph path,
and both are only a HINT — the authoritative WABA list still comes from
`debug_token`'s granular scopes. Without it, a grant whose granular scopes come
back empty would leave the picker with nothing to list.

**D5 — two audit event tags added** (`webhook_failed`, `approvals_refreshed`).
`event` is a Char precisely so a later adapter can add one; adding them to
`KNOWN_EVENTS` only keeps the log clean.

**D6 — `provider_approvals` is never `fail`.** T136 says approvals "render as
pending, never as failure". Implemented literally for the *readiness check*:
it moves between `pending` and `pass` only, and passes ONLY when Meta itself
reports every item approved. The per-item ROW still tells the truth (a
`DECLINED` display name reads `fail` with "Meta declined the display name.
Choose another one…"). Reason: a `fail` on a required check drops the
connection to `action_required`, which is **not ingestable** — so a display-name
review the tenant can still win would lock the channel out of the traffic that
proves it. That is exactly the §5.66 trap in a new costume.

### Forced test edits (declare-or-lie, ledger §5.62's family)

**F1 — `test_center.T104`.** `whatsapp` and `fb` left its `unimplemented` list.
They ARE implemented from CC-E on, and the shared fixture seeds a `meta`
platform app, so `center_begin` on them now succeeds. T104 now asserts that
positively (idempotent, one row, correct mode) instead of asserting a refusal
that is no longer true.

**F2 — the canonical CC-B payload timestamps became relative.**
`wa_payload` / `fb_payload` / `tg_payload` carried a fixed epoch
(2026-01-21). Harmless while nothing depended on *when* a message arrived —
but Meta's 24 h window makes recency semantic, and a six-month-old fixture
inbound now correctly closes the window and refuses a free-form reply. Default
is "5 minutes ago", computed at call time; T135 passes `ts` explicitly where it
wants an old message. No test asserted on the literal value (grep-verified
before changing it).

---

## 3. Test results (verbatim, vietuat, final run)

```
2026-07-26 07:08:34,348 INFO vietuat odoo.tests.stats: health_care_command_channels: 99 tests 18.75s 17640 queries
2026-07-26 07:08:34,348 INFO vietuat odoo.tests.result: 0 failed, 0 error(s) of 83 tests when loading database 'vietuat'
EXIT:0   HTTP:200
```

Regression, the untouched Care Command family:

```
2026-07-26 07:03:41,454 INFO vietuat odoo.tests.stats: health_care_command: 38 tests 7.68s 6513 queries
2026-07-26 07:03:41,454 INFO vietuat odoo.tests.stats: health_care_command_ai: 8 tests 1.76s 1522 queries
2026-07-26 07:03:41,454 INFO vietuat odoo.tests.stats: health_care_command_voip: 6 tests 0.53s 397 queries
2026-07-26 07:03:41,454 INFO vietuat odoo.tests.result: 0 failed, 0 error(s) of 46 tests when loading database 'vietuat'
EXIT:0
```

Regression, health_zalo (CC-D's co-consumer):

```
2026-07-26 07:04:47,451 INFO vietuat odoo.tests.stats: health_zalo: 10 tests 2.41s 1965 queries
2026-07-26 07:04:47,451 INFO vietuat odoo.tests.result: 0 failed, 0 error(s) of 8 tests when loading database 'vietuat'
EXIT:0
```

**105 test methods in the module** (CC-A 20 + CC-B 26 + CC-C 12 + CC-D 17 +
**CC-E 14**). TransactionCase only, **zero HttpCase** (§5.32), zero real HTTP,
zero credentials. Run with `--workers=0` (§5.75).

| test | what it proves |
|---|---|
| T127 | ES start payload = app id + `es_config_id` + single-use state and **no secret**; FLB dialog URL carries `config_id`, `response_type=code`, our redirect and no secret; the state burns exactly once; a platform app with no configuration id refuses rather than opening a dialog that could only fail |
| T128 | exchange happy path: secret server-to-server, **no `redirect_uri` on the ES exchange**, `debug_token` called with the APP token; the grant lands as `chs$1$` ciphertext at SQL level with the plaintext absent; scopes recorded; WABAs from hint ∪ granular scopes; the phone hint is a hint, NOT a selection; nothing echoed to the browser |
| T129 | refusals store NOTHING: a refused exchange never goes on to inspect a token it never got, state unmoved, no credential, no readiness row; a replayed state and an unknown state are the same refusal; an empty code never reaches the network; Messenger has no paste-a-code door |
| T130 | a partial grant is `authorization_valid` pass + `scopes_granted` **fail** with the withheld scope readable in the detail; from `testing` with everything else proven the connection lands in `action_required`, and the dock stays dark |
| T131 | WABA/number listing across the granted WABAs; a number that is not on the account is refused with nothing written; selection writes `resource_external_id` = phone_number_id and `resource_secondary_id` = WABA, and that id is exactly what `_find_for_resource` routes on |
| T132 | `subscribed_apps` posts to the **WABA** with the token; a refusal leaves `webhook_state` at `none`, writes `webhook_configured` fail + a redacted `last_error_redacted` (no token in it) + a `webhook_failed` audit; success ⇒ `subscribed`, check pass, state `testing` |
| T133 | Messenger: the user token is held in `refresh_token_enc` and **nothing can send yet**; `/me/accounts` picker returns pages with every token stripped; a page the account does not administer is refused; selecting stores the PAGE token as `chs$1$`; the subscription targets the PAGE with `subscribed_fields=messages,messaging_postbacks` |
| T134 | inbound routes by `phone_number_id` / `page_id` to the right tenant, another company's connection receives nothing, an unowned id is `unknown` — and the ids CC-E's picker writes are the ids CC-B's `_meta_resource_ids` reads |
| T135 | inside 24 h both channels reply freely (`messaging_type: RESPONSE`, no tag); outside it WhatsApp refuses free-form **before the network** and the template path works (`type: template`, name, language, body parameters); Messenger gets `MESSAGE_TAG` + `HUMAN_AGENT` and a retired tag is refused by US; past 7 days nothing goes out; a channel with no provider window answers open |
| T136 | approvals pending ⇒ pending rows, `provider_approvals` pending, no demotion to `action_required`; a DECLINED display name reads `fail` in the ROW but still `pending` on the check; ONLY Meta reporting every item approved flips it to pass; Meta unreachable is pending and never raises at the UI |
| T137 | **the vietuat state, asserted directly**: no platform app ⇒ both cards `available=False`, `primary_action=unavailable`, label "Not available yet", state `not_connected` — while `implemented=True`, because conflating "the software is missing" with "the app is missing" is how a card lies; `center_begin` and `center_meta_start` both refuse; nothing is created; the adapter refuses rather than guessing |
| T138 | spoof: cross-company `conn_id` refused on all seven new endpoints; a plain CRM user refused on all of them; nothing moved, no credential landed, no session created; the `*_enc` columns are not even in a tenant admin's `fields_get` |
| T139 | catalogue still 8 cards in dock order; both Meta cards available+implemented with 4 stepper screens that each carry real BODY copy (not CC-C's title-only structure); modes `embedded_signup` / `oauth_popup`; no secret and no `config_id` in the payload |
| T140 | Telegram, web chat and Zalo/ZNS untouched; a Telegram send is unaffected by the window plumbing; the CC-B Meta webhook route is still raw-http/POST/public/no-csrf/no-session |

### The red run, and what it caught

First run: **2 failed, 2 error(s)** — all four mine, no regression anywhere
else. Cause was a test-harness bug, not product code: `_mock_graph` patched
`BaseChannelAdapter._get/_post` with `autospec=True`, and a Meta flow is
several stages long so a test re-arms the mock between stages. **A second
`autospec` patch builds its spec from the FIRST patch's mock**, quietly stops
binding `self`, and every later call returns an empty reply — a listing mocked
with two rows came back with none. Fixed by patching with plain functions
(`patch.object(cls, name, func)`), which are ordinary descriptors and stack
correctly however many times they are applied. Documented in the helper's
docstring.

---

## 4. Live evidence

`docs/strategy/reports/channel-center-phaseE-evidence/`:

- **`live-routes.txt`** — the CC-B Meta webhook is still fail-closed after this
  phase: the GET handshake refuses all three challenge shapes and every POST
  (unsigned, bogus signature, either channel, an unknown channel key) is the
  same **`HTTP 403, 0 bytes`**. The `meta` OAuth callback answers 200 and
  echoes neither the state nor the code.
  *Honest note: with 0 platform apps the handshake can only ever refuse — an
  endpoint that echoed a challenge with no verify token configured would let
  anyone point their own Meta app at our inbox. The positive handshake path is
  covered by `meta_challenge` + CC-B's suite, not by a live curl.*
- **`server-state.txt`** — the data-honesty table, read from psql.
- **`browser-pass.md` + 4 screenshots** — login → `/bizapp` → sidebar → Channel
  Center as the real `crm` user, both Meta cards reading "Not available yet"
  with disabled buttons, the RPCs refusing from the browser, Meta's SDK absent
  from the page, and the Telegram stepper proving the channel-scoping refactor
  leaked no Zalo or Meta copy.

---

## 5. Data honesty

| Fact | Before CC-E | After CC-E |
|---|---|---|
| `channel.platform.app` rows | 0 | **0** |
| `care.channel.connection` rows | 1 (`zalo:legacy`) | **1 (`zalo:legacy`)** |
| WhatsApp / Messenger connections | 0 | **0** |
| `care.channel.identity` | 0 | **0** |
| `care.channel.message` | 0 | **0** |
| `care.channel.oauth.session` | 0 | **0** |
| Real WhatsApp messages sent or received | 0 | **0** |
| Real Messenger messages sent or received | 0 | **0** |
| Meta approvals actually read from Graph | 0 | **0** |

Nothing in CC-E changed any of that, and nothing was invented to make it look
otherwise. Every Graph call in this phase has only ever been made against a
mock in the test suite.

QA fixture: clicking Telegram → Connect during the browser pass created
connection 2242; it was deleted and the removal verified from psql (§5.34).
Two append-only `care.channel.audit` rows from that click survive with
`connection_id` NULL — by design (§5.30/§5.4), and declared rather than hidden.

---

## 6. What remains blocked on Meta's human processes

From the operator checklist (architecture §12) — none of this is software:

| # | Blocking action | Status | What it unblocks |
|---|---|---|---|
| §12.1 | Meta Business-type app + business portfolio + **Business Verification** | **not started** | anything beyond a 10-tenant/7-day trickle; without the app there is no `channel.platform.app` row at all, which is why both cards are dark |
| §12.2 | **App Review** of `whatsapp_business_management`, `whatsapp_business_messaging`, `pages_messaging`, `pages_manage_metadata`, `pages_show_list` — with screencasts | **not started** | live traffic on either channel. Until it passes, `debug_token` returns a short scope list and CC-E correctly writes `scopes_granted` = fail |
| §12.3 | Two Login-for-Business configurations (ES v4 for WhatsApp, a login config for Messenger) → their ids into `channel.platform.app.extra_json` as `es_config_id` / `flb_config_id` | **not started** | the sign-in itself. `config_id()` refuses without them rather than opening a dialog that could only fail |
| §12.4 | App-level webhook URLs + verify tokens for the WhatsApp and Messenger products | **not started** | inbound. The route exists and is fail-closed; the `verify_token` goes in the same `extra_json` |

Tenant-side gates that stay pending even after all four (surfaced as approval
rows, never as errors): the tenant's own business verification, WhatsApp
display-name review, per-template Meta approval, and a payment method on the
WABA.

**Once §12.1–§12.4 are done, the operator seeds one row** — provider `meta`,
`client_id`, `action_set_secret(...)`, and
`extra_json = {"verify_token": …, "es_config_id": …, "flb_config_id": …}` —
and both cards go live with no code change. That is the whole feature-flag.

---

## 7. New gotchas for the ledger (§5)

**§5.76 — a second `mock.patch(..., autospec=True)` on an already-patched
method silently stops binding `self`.** `create_autospec` builds its spec from
the CURRENT attribute, which on a re-patch is the first patch's mock; the
result accepts anything, returns the mock's default, and never reaches your
`side_effect` with the arguments you expect. Symptom: a call you mocked with
data comes back empty, only in the tests that re-arm the mock mid-flow (CC-E:
4 red tests, all "a listing with two rows returned none"). Multi-stage provider
flows re-arm constantly. Patch with a PLAIN FUNCTION —
`patch.object(cls, '_get', func)` where `func(self, …)` — which is an ordinary
descriptor and stacks correctly any number of times.

**§5.77 — a fixture timestamp becomes semantic the moment a phase adds a time
window, and the breakage lands in tests that never mention time.** CC-B's
canonical WhatsApp/Messenger payloads carried a fixed epoch six months in the
past. CC-E added Meta's 24 h customer-service window, and every pre-existing
`action_send_channel` test on those channels would have started refusing —
correctly. Rule: when a phase makes recency load-bearing, grep every shared
fixture for an absolute timestamp and make it relative to now, keeping an
explicit override for the tests that WANT an old event. Sibling of §5.62
(default-narrowing) and §5.50 (fixtures inheriting live values).

**§5.78 — a readiness check that can go `fail` is a traffic kill switch;
provider-review state must not be wired to one.** `_recompute_ready` sends any
failed *required* check to `action_required`, which is not in
`INGESTABLE_STATES` — so wiring "Meta declined your display name" to
`provider_approvals = fail` would stop the inbound traffic on a channel whose
review the tenant can still win, and there would be nothing left to prove it
with when they do. Keep provider-review state in the row a human reads, and let
the required check move only between `pending` and `pass`. Same family as
§5.66, one layer up: §5.66 was "the state that means *being proven* must
survive its own evidence arriving"; this is "a state a human controls elsewhere
must not be able to close the door".

---

## 8. Definition of done

| # | Item | Status |
|---|---|---|
| 1 | Module tests pass on vietuat; earlier modules still pass | ✅ 0 failed / 0 error of 83; care_command family 0/46; health_zalo 0/8 |
| 2 | `/web/login` HTTP 200 after the final restart | ✅ |
| 3 | PWA version bump | n/a — nothing PWA-facing changed |
| 4 | `vi.po` covering user-visible strings | ✅ +64 entries; 185 python + 75 web live; §29/§5.58/§5.67 shape asserted by T105 |
| 5 | Browser evidence pack committed | ✅ `channel-center-phaseE-evidence/` — real-user path from the login page; QA fixture deleted + fresh-cursor verified |
| 6 | Committed and pushed on `19.0` | ✅ `15b3a919` (push pending your go-ahead) |
| 7 | Report committed alongside | ✅ this file |

---

## 9. For the reviewer — where to look hardest

1. **`_MetaAdapterBase._store_tokens`** (`adapters.py`) — the §5.74 surface.
   Meta tokens do not rotate, so nothing here is single-use, but it uses the
   CC-D-hardened `_persist_refreshed_tokens` and takes **no row lock anywhere**.
   Worth confirming there is no path that combines a lock with the fresh cursor.
2. **`MessengerAdapter.select_resource`** — the one place a per-Page credential
   is read out of a provider reply and written. T133 asserts the token never
   reaches a return value; a second pair of eyes on the whole path is cheap.
3. **`center_meta_exchange`** — the only new endpoint that takes credential
   material (an authorization code) straight from a browser. Gate order is
   `_center_meta` → `_center_get` → `_check_center_access` → channel → code →
   state; the code is never logged, echoed or stored.
4. **`_center_window` / `action_send_channel`** — the refusal is now BEFORE the
   network for two channels. If the window logic is wrong in the closed
   direction, agents silently cannot reply. T135 stages every branch, but the
   arithmetic is worth reading once.
5. **The stepper's channel-scoping** (`channel_center.xml`) — Messenger and
   Zalo share `mode == 'oauth_popup'`, so every branch was re-keyed to
   `isZalo` / `isMeta`. Zalo's stepper cannot be driven on vietuat (no Zalo
   platform app either), so that surface is proven only by reading the diff
   plus the Telegram drive that shows nothing leaked.
