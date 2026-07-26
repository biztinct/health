# Channel Center — Phase CC-D: Zalo/ZNS onto the framework

**Fable → Opus handover, 2026-07-26.** Read `HANDOVER-CONVENTIONS.md` first
(§5.8, §5.32, §5.34, §5.42, §5.55, §5.58, §5.61–§5.70 — §5.70 is new), then
`channel-center-architecture.md` §1.2 (Z1–Z9), §7 (secrets/OAuth/webhooks) and
§11, then the CC-A/CC-B/CC-C reports. This phase makes **Zalo the first
OAuth-popup channel in the Connection Center**, replaces health_zalo's
fail-open security boundary with the framework's fail-closed one, and makes
`zalo.config` a facade over `care.channel.connection` — while the 10-module
ZNS contract keeps working **verbatim**.

## 1. Scope

1. **ZaloAdapter for real** (OAuth v4 + PKCE, token exchange/refresh with the
   `secret_key` header, single-use refresh rotation under the CC-A lock).
2. **New fail-closed webhook** `/care_channels/zalo/webhook` (ONE per
   deployment — Zalo's portal allows one URL per app; route by `oa_id`,
   verify per-OA secret over raw bytes). Old `/zalo/webhook` becomes a 410
   shim.
3. **`zalo.config` becomes a facade**: tokens live encrypted on the linked
   connection; `get_api_client` / active-config search /
   `send_zns_notification` signatures unchanged.
4. **Legacy migration**: one `state='legacy'` connection per active
   `zalo.config`; nothing deleted, nothing invalidated.
5. **Z1–Z9 repairs** in health_zalo (list in §4.6 — some are fixed by
   replacement, not by patching).
6. **Center UI**: the Zalo stepper goes live (sign-in popup → portal-guided
   webhook checklist → say-hello test), and the ZNS sub-card renders honest
   readiness (template config counts + traffic-proven send).
7. **CC-A deferred rider**: live NOWAIT refresh-lock contention smoke on the
   server (§5.63 made it unstageable in TransactionCase).

**Binding non-goals:** no Meta (CC-E), no Email/VoIP24h (CC-F), no ZNS
template designer or approval automation, no edits to any of the 10 ZNS
consumer modules (list in §2.4), no deletion/rename of any `zalo.config`
column, no real Zalo credentials in any test, no new public routes beyond the
one webhook + the 410 shim.

## 2. Verified plumbing facts — do NOT re-derive

### 2.1 The framework side (all verified 2026-07-26)
- OAuth engine (CC-A): `care.channel.oauth.session.create_for(connection,
  redirect_target=None, provider=None, …)` at
  `models/care_channel_oauth_session.py:139` mints hashed single-use state +
  PKCE verifier; `_get_pkce_verifier()` :225; `_handle_callback(provider,
  params)` :234 consumes state, then calls
  `connection.sudo()._get_adapter().handle_callback(session, params)` inside
  a savepoint (:266-269) — **that method is what you implement**. Callback
  route `/channel_hub/oauth/callback/<provider>` already exists
  (`controllers/oauth.py:46`, http/public/GET/`save_session=False`) and
  renders generic non-oracle pages. `NotImplementedError` from the adapter is
  already handled (:270-279) — deleting that branch is not needed and not
  sanctioned.
- Token store: `SECRET_FIELDS` maps `access_token`/`refresh_token`/
  `provider_secret` to `*_enc` columns (`care_channel_connection.py:121-127`);
  `_with_refresh_lock` (FOR UPDATE NOWAIT in a savepoint) :726-736;
  `_persist_refreshed_tokens(access_token, refresh_token, token_expires_at,
  granted_scopes)` :742+ **persists on a fresh cursor** — this is the
  single-use-rotation safety and you must route every refresh through it.
  Expiry cron horizon query :856 flips `expiring` + one mail.activity (CC-A).
- Adapter stubs: `ZaloAdapter` (`services/adapters.py:442-462`) already
  declares `mode=MODE_OAUTH_POPUP`, `platform_providers=['zalo']`,
  `required_checks=[authorization_valid, resource_selected,
  webhook_configured, webhook_verified, outbound_ok, token_fresh]`.
  `ZnsAdapter` :465+ declares `parent_channel='zalo'` — the Center already
  renders it as a sub-card of Zalo's connection and refuses
  `center_begin('zns')` ("part of the Zalo connection", T104 asserts this —
  keep it passing).
- Center gating: `CENTER_IMPLEMENTED_CHANNELS` and `IMPLEMENTED_MODES` in
  `models/channel_center.py:55-61`. CC-D adds `'zalo'` and
  `MODE_OAUTH_POPUP`; **both** gates must pass, so whatsapp/fb (also
  oauth_popup) stay honestly "Available in an upcoming update".
- Every `center_*` endpoint pattern: `_center_group_ok()` on @api.model
  entries, `_center_get(conn_id)` → `_check_center_access()` (group +
  company) before any sudo write. Clone it exactly; T107 is the spoof-test
  precedent for new conn_id endpoints.
- TRANSITIONS now allows `disabled` from every in-flight state and
  `authorizing` from mid-setup states (CC-C review fix 6cacb76f) — your
  stepper can rely on disconnect/restart working mid-flow.
- §5.70 (NEW): Odoo's `assertRaises` cannot take an exception tuple — use
  `try/except (A, B)` when either class is legitimate.

### 2.2 health_zalo (verified 2026-07-25/26; Z-table with file:line in architecture §1.2)
- Old webhook: `/zalo/webhook` is **`type='jsonrpc'`** auth=public
  (`controllers/webhook.py:20`) — fails open three ways (Z2) and drops all
  events via a swallowed `with_delay` AttributeError while returning 200
  (Z3). Also `/zalo/webhook/test` (GET, :56) and `/zalo/oauth/callback`
  (:65 — the PKCE-less legacy flow, Z6).
- `ZaloAPIClient` (`services/zalo_api.py:12`): token exchange posts to
  `{config.api_base_url}/v4/access_token` (:108) and
  `refresh_access_token(config)` (:130) posts to the same wrong URL with
  **no `secret_key` header** (Z8). `send_zns_notification(config, phone,
  template_id, template_data)` :297 (error-dict contract);
  `get_api_client(env)` :354.
- `zalo.config`: per-company, plaintext `access_token`/`refresh_token`
  columns, `app_secret` has `tracking=True` (Z1 — leaks into
  `mail.tracking.value`), no ir.rule anywhere in the module (Z4),
  `api_base_url` writable by `group_zalo_manager` (Z5 — token-exfil via next
  refresh), demo-config auto-create + broken wizard buttons (Z9), no inbound
  dedupe on `zalo_message_id` (Z7 — indexed, NOT unique, live dupes possible:
  pre-check, don't add a unique index).
- health_zalo `__manifest__.py` depends do NOT include the channels module —
  **CC-D adds `health_care_command_channels` to them** (the facade is real,
  permanent coupling; both installed on vietuat).

### 2.3 Care Command's zalo surface — DO NOT MOVE IT
`care_conversation.py` (health_care_command, core): `_detail_timeline`
:846-854 reads **`zalo.message`** rows; the ops send path :1118-1125 creates
a `zalo.message` and delegates to the existing `action_send_message`. **CC-D
keeps zalo chat storage and the ops timeline on the `zalo.message` rails.**
The framework takes over the *boundary* (webhook verification, OAuth,
secrets) — the new webhook controller verifies fail-closed, then feeds the
legacy pipeline synchronously (create `zalo.message` etc. the way the old
handler did, minus `with_delay`), plus `connection._note_inbound()` for
traffic-truth. No `care.channel.message` rows for zalo chat, no core edits
to `_detail_timeline`.

### 2.4 The frozen ZNS contract (10 consumer modules — untouchable)
`get_api_client(env)` + `env['zalo.config'].search([('active','=',True)],
limit=1)` + `send_zns_notification(config, phone, template_id, params)`
error-dict, consumed by: health_workflow_auto, health_self_booking,
health_telehealth, health_schedule_drag, health_family_messages,
health_voip24h (×2 files), health_pwa_family, health_messaging,
health_family_link. Every one patches `ZaloAPIClient.send_zns_notification`
in its tests. Signatures survive verbatim; their template ids stay in
per-module `ir.config_parameter`s.

### 2.5 vietuat live state (data honesty, verified 2026-07-26)
Exactly **one** `zalo.config` row: id=3, active, has `app_id` and `oa_id`,
**NO access_token, NO refresh_token**. So: migration creates exactly one
`legacy` connection with `has_credentials=False`; Zalo/ZNS sends are already
dead on vietuat today and stay dead until someone completes the new sign-in —
say so in the report, don't "fix" it.

### 2.6 Zalo provider facts (verified 2026-07-25 — architecture §3/§7)
- Authorize: `https://oauth.zaloapp.com/v4/oa/permission?app_id=…&redirect_uri=…&code_challenge=<S256>&state=…` (PKCE S256 **required**).
- Token exchange: POST `https://oauth.zaloapp.com/v4/oa/access_token`,
  `secret_key: <app_secret>` **header**, form body `app_id`,
  `grant_type=authorization_code`, `code`, `code_verifier`.
- Refresh: same URL + header, `grant_type=refresh_token`. Access token ~25 h;
  refresh token **single-use** (a new one comes back every time), 3-month
  life. Persist-before-anything: a refresh you don't store is a dead OA.
- OA identity: GET `https://openapi.zalo.me/v2.0/oa/getoa` with
  `access_token` header → oa id + name (this is `resource_selected`).
- Webhook signature: `X-ZEvent-Signature: mac=<hex>` where
  `hex = sha256(app_id + raw_body + X-ZEvent-Timestamp + oa_webhook_secret)`
  — plain SHA-256 over the concatenation, **per-OA secret** (from the app's
  portal page), compare with `hmac.compare_digest`. Webhook URL is
  portal-only, one per app.

## 3. Design decisions (binding)

- **D-plane split**: `channel.platform.app` provider `zalo` holds `app_id` +
  `secret_key` (operator-seeded, system-only — the framework model already
  supports it). The **per-OA webhook secret** is tenant material →
  `provider_secret` on the connection (pasted in the webhook step). Tokens →
  `access_token`/`refresh_token` on the connection.
- **Facade direction**: `zalo.config` gains `connection_id` (Many2one, new
  column, nothing dropped). `ZaloAPIClient` token reads go through the config
  facade: when `connection_id` is set and holds credentials, tokens come from
  the connection (decrypted); otherwise the legacy plaintext columns keep
  working (transitional, and the vietuat row has no tokens anyway). Refresh:
  when connection-linked, `refresh_access_token` routes through
  `_with_refresh_lock` + the corrected endpoint + `_persist_refreshed_tokens`
  and ALSO mirrors the new access token into the legacy columns so old code
  paths that read `config.access_token` directly stay correct. ZNS success/
  failure calls `connection._note_outbound()` / `_note_send_failure()` —
  traffic-truth flips `outbound_ok` and the ZNS sub-card goes honest for free.
- **Webhook routing order** (the one place parse precedes verify, by
  necessity): read raw bytes → parse JSON **only** to extract `oa_id` →
  resolve connection by `channel='zalo'`, `resource_external_id=oa_id`
  (INGESTABLE check after verify) → verify signature over the RAW bytes with
  that connection's per-OA secret → only then decode/ingest. Missing header,
  unknown oa_id, no secret, bad mac: **all the same bodyless 403** (no
  oracle). After verification: 200 always, per-event savepoints (§5.55),
  `webhook_ignored` audit when not ingestable, `zalo_message_id` pre-check
  dedupe (Z7).
- **410 shim**: health_zalo's controller class keeps the three routes but the
  handlers return plain 410 ("gone") with no body detail — Zalo retries die
  fast, nothing fails open, and `/zalo/oauth/callback` 410s too (the legacy
  flow is retired; Z6). Do it by editing health_zalo's controller in place —
  do not delete the file (the 410 IS the shim).
- **center_test for zalo** replies to the newest zalo-anchored
  `care.conversation` via the EXISTING ops send path (§2.3), not a new
  adapter send — same synthetic body as CC-C, same "somebody must message
  the OA first" refusal, and it must respect that `zalo.message`'s send path
  raises its own errors (wrap → §5.65 evidence-first, redacted UserError).
- **ZNS honesty on the sub-card**: `provider_approvals` check is `pending`
  until the first successful ZNS send flips it to `pass` (traffic-proven,
  automatic — no attestation button). The sub-card also shows how many of
  the consumer-module template params are configured (count of set
  `ir.config_parameter`s from the known key list — read-only honesty line).
- **Migration** runs in health_zalo (it owns the legacy rows and now depends
  on the framework): `post_init`-guarded-idempotent OR a
  `migrations/<new version>/post-migrate.py` — for each active `zalo.config`
  with no `connection_id`: create `care.channel.connection`
  {channel='zalo', company, state='legacy',
  resource_external_id=config.oa_id, resource_display_name=config.name},
  link it back. If the config HAS legacy plaintext tokens, encrypt-copy them
  onto the connection (then the legacy columns stay as-is — nothing wiped
  this phase). Re-running creates nothing (T116).

## 4. Server work

### 4.1 `services/adapters.py` — ZaloAdapter implementation
`authorize_url(session)` (build §2.6 URL from the platform app + session's
state/challenge; raise ChannelSendError if no platform app), `handle_callback
(session, params)` (exchange per §2.6 with `session._get_pkce_verifier()`;
on success `_persist_refreshed_tokens(...)`, GET getoa → write
resource_external_id/display_name via `_internal()`, upsert
authorization_valid/resource_selected/token_fresh = pass, transition
authorizing→configuring; return `{'ok': True}` shape the engine expects),
`refresh(...)` (inside `_with_refresh_lock` from the connection's cron hook —
follow the hook signature CC-A's cron calls). Never put a token in an
exception message; the `secret_key` header value must never appear in a URL
(the redactor's `_KV_RE` covers `secret_key=` KV forms — add a T79 probe
anyway).

### 4.2 `services/webhook_verify.py` — `verify_zalo(connection, raw, headers)`
Signature per §2.6, fail-closed on every missing piece, compare_digest,
returns bool. Golden-vector unit test (T112) with a fixture secret.

### 4.3 `controllers/zalo.py` (NEW, clone telegram.py's shape)
`/care_channels/zalo/webhook`, `type='http'`, POST, auth=public, csrf=False,
`save_session=False`; §3 routing order; per-event savepoints; feeds the
legacy `zalo.message` pipeline (§2.3) + `_note_inbound()` +
webhook_state='verified' + `webhook_verified` check upsert.

### 4.4 `models/channel_center.py` — zalo endpoints
`center_zalo_authorize(conn_id)` → `_center_get` gate, oauth.session
`create_for`, return `{'url': …}` (state/verifier NEVER returned);
`center_zalo_set_webhook_secret(conn_id, secret)` → gate,
`action_set_secret('provider_secret', secret)`, upsert `webhook_configured`
pass (the tenant has done their half; `webhook_verified` stays pending until
real traffic), transition configuring→testing when appropriate + show the
exact webhook URL to paste into the portal (`web.base.url` must be https —
same refusal as Telegram's). Add `'zalo'` to CENTER_IMPLEMENTED_CHANNELS,
`MODE_OAUTH_POPUP` to IMPLEMENTED_MODES, and real `_center_guide_texts` copy
for the four zalo steps + the ZNS lines (VI strings in vi.po with `#:`
occurrences — §5.67, and T105-style runtime assertions).

### 4.5 `static/src/center/` — popup + checklist
Connect → `center_zalo_authorize` → `window.open(url)` (popup blocked ⇒ show
the URL as a clickable link — no silent failure); on popup close or focus
return, re-`load()` (the 15 s poll already exists). Webhook step: copyable
URL line + secret paste field (`type="password"`, zeroed in `finally` —
clone the Telegram idiom) + "Waiting for Zalo to confirm…" line that flips
when `webhook_verified` goes pass (the poll sees it). ZNS sub-card: template
count + provider_approvals chip. Flat mono, hf-wt-ico only, VI+EN.

### 4.6 health_zalo edits (each one small, all sanctioned)
manifest: `+health_care_command_channels` dep, version bump;
`models/zalo_config.py`: `connection_id` field, facade token reads, **remove
`tracking=True` from `app_secret`** (Z1) + one-time cleanup: delete
`mail.tracking.value` rows attached to that field (log the count); remove
the demo-config auto-create + dead wizard buttons (Z9); legacy OAuth methods
raise UserError pointing at the Center (Z6). `services/zalo_api.py`: correct
endpoints + `secret_key` header (Z8), facade reads, locked refresh (§3).
`controllers/webhook.py`: 410 shim (Z2/Z3). `security/`: ir.rule
company-scoping on zalo.config/conversation/message (global, clone the
channels module's posture — Z4) + `api_base_url` writable only by system
(field `groups=` or a write-guard — Z5). Migration hook (§3).

## 5. Tests (T108–T120, `tests/test_zalo_center.py` + additions)
All HTTP mocked via `mock_get`/`mock_post` (they patch adapters.requests.*;
health_zalo's own `requests` calls need an equivalent patch point — patch
`ZaloAPIClient`'s session/requests at its module). No real credential
anywhere; §5.8 try/except for every nothing-stored assertion; §5.70 for any
dual-class raise.

- **T108** authorize URL: S256(verifier)==challenge, state present, app_id
  from the platform app, no secret material in the returned URL beyond
  app_id.
- **T109** callback happy path: `secret_key` header + `code_verifier`
  asserted on the mocked POST; tokens land encrypted (SQL `chs$1$` assert,
  clone T99's); getoa mocked → resource fields; checks pass; state
  configuring; no token in the engine's return.
- **T110** callback refusals: exchange 4xx → nothing stored; reused state →
  generic; denied → denied outcome (engine already does this — assert the
  zalo adapter path doesn't break it).
- **T111** refresh rotation: mocked refresh → NEW refresh token persisted
  (fresh-cursor — assert after invalidate), legacy columns mirrored;
  failure → old refresh token intact, token_fresh fail only on auth-class
  errors.
- **T112** verify_zalo golden vector + refusal matrix (missing header, wrong
  mac, wrong timestamp, unknown oa_id at controller level, no platform app).
- **T113** inbound: verified event → `zalo.message` row (legacy pipeline) +
  `_note_inbound` + webhook_verified pass; **same `zalo_message_id` twice →
  one row** (Z7).
- **T114** 410 shim: all three legacy routes answer 410 (route-table
  assert like T102's `original_routing`; live curls in evidence).
- **T115** facade contract: `get_api_client` + active-config search +
  `send_zns_notification` signature intact; connection-linked config reads
  the connection's token; ZNS success flips provider_approvals +
  outbound_ok; ZNS failure → `_note_send_failure`, error-dict unchanged.
- **T116** migration idempotent: one legacy connection per active config,
  re-run creates nothing, plaintext-token config gets encrypted copies,
  nothing deleted.
- **T117** Z1: `app_secret` untracked — writing it creates no
  mail.tracking.value.
- **T118** Z4/Z5: cross-company zalo.config read refused; `api_base_url`
  write refused for zalo manager.
- **T119** Center flow: begin('zalo') → authorizing; authorize returns url;
  after mocked callback → configuring; set_webhook_secret stores encrypted +
  testing; first verified inbound → per F1 stays/promotes correctly; ZNS
  sub-card honesty; begin('zns') still refused.
- **T120** spoof: plain CRM user refused on every new endpoint; cross-company
  conn_id refused (clone T107 with the two new endpoints).

## 6. Deploy + evidence (§9-style)
scp → `/odoo/odoo-server/addons/` (service `odoo-server`, conf
`/etc/odoo-server.conf`, **stop service + drain workers before odoo-bin, use
`--http-port=8169 --logfile=/tmp/…`** — the port clash and the swallowed-
stdout traps are both real, see the CC-C review report). Upgrade
`health_care_command_channels,health_zalo` with `--test-enable`. Green =
EXIT:0 + zero `FAIL: `/`ERROR: Test` + per-module stats lines (a missing
`odoo.tests.result` line alone is NOT a failure on this build). Evidence:
live curls (`/care_channels/zalo/webhook` bad-mac → bodyless 403; the three
legacy routes → 410), the NOWAIT contention smoke (two concurrent
`odoo-bin shell` processes calling `_with_refresh_lock` on a fixture
connection — capture the "already locked" log line, then DELETE the fixture
§5.34-clean), migration proof (the one vietuat config → one legacy
connection, fresh-cursor counts), Center browser pass **only if the user
gives you a login — ask FIRST; if none is provided, stop and report, do not
fabricate**. Data honesty per §2.5. `web.base.url` is https and frozen —
if you find it otherwise, stop and report, don't chase it.

## 7. Report back
Deviations (D-numbered) with reasons; data-honesty table; any Z-item you
could not close and why; the §5-ledger entries you add; test tally; evidence
paths. Do not claim ZNS works on vietuat — it cannot until a human completes
the new Zalo sign-in with real OA credentials.

---
**Kickoff line:** Implement `docs/strategy/handovers/channel-center-phaseD.md`
(Channel Center Phase CC-D — Zalo/ZNS: real ZaloAdapter OAuth v4+PKCE with
locked single-use refresh, fail-closed `/care_channels/zalo/webhook` +
legacy 410 shims, zalo.config facade + legacy migration, Z1–Z9 repairs,
Center zalo stepper + honest ZNS sub-card, T108–T120). Read
HANDOVER-CONVENTIONS.md (§5.8/§5.32/§5.34/§5.55/§5.61–§5.70), architecture
§1.2/§3/§7, and the CC-A/B/C reports first. The 10-module ZNS contract is
untouchable; all HTTP mocked; deploy + evidence per §6; report deviations
and data honesty.
