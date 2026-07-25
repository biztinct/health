# Channel Center — Phase CC-A Handover: Connection Framework Core

**For:** Opus implementation session · **Designed/reviewed by:** Fable (2026-07-25)
**Read first:** `docs/strategy/HANDOVER-CONVENTIONS.md` (§5.1 init-index, §5.4
unconditional guards, §5.36 settings falsy-unlink, §5.55 savepoints, §5.61 webhook
posture, §29/§5.58 vi.po) **and** `docs/strategy/handovers/channel-center-architecture.md`
(the binding design — model names, state machines, trust boundaries live THERE; this
handover adds the implementation-grade detail for Phase A only).
**New module:** `health_care_command_channels` **19.0.1.0.0** (depends:
`health_care_command`, `health_api_gateway`; NOT auto_install). **Zero core touches
this phase** — the phase6 core-touch list (extract `_apply_signal`/`_capabilities`,
`_channel_keys()` override, JS edits) belongs to CC-B, NOT here.

## 1. Why & scope (binding)

This phase builds the provider-neutral connection framework ONLY: crypto, the two
credential planes, the OAuth engine, readiness/health/audit, the adapter registry with
capability declarations, security, and a stub Settings surface. **No messaging, no
per-provider adapters beyond capability stubs, no OWL Center UI, no webhook message
processing, no migration of zalo/voip configs.** Nothing user-visible changes in Care
Command (dock untouched). Every external HTTP is mocked in tests; no credentials ever
touch vietuat in this phase.

## 2. Deliverables

```
addons/health_care_command_channels/
├── __manifest__.py                       # version 19.0.1.0.0
├── models/
│   ├── channel_platform_app.py           # Plane 1
│   ├── care_channel_connection.py        # Plane 2 + readiness derivation
│   ├── care_channel_oauth_session.py
│   ├── care_channel_readiness_check.py
│   ├── care_channel_audit.py
│   └── res_config_settings.py            # allowed_redirect_hosts param only
├── services/
│   ├── channel_crypto.py                 # §3 below — write FIRST, test FIRST
│   └── adapters.py                       # registry + BaseChannelAdapter + 8 stubs
├── controllers/oauth.py                  # /channel_hub/oauth/callback/<provider>
├── security/{ir.model.access.csv, channel_hub_security.xml}
├── views/{channel_connection_views.xml, platform_app_views.xml, menus.xml}
├── data/ir_cron.xml                      # health cron + session purge cron
├── i18n/vi.po                            # §29 + §5.58 markers (clone health_voip24h style)
└── tests/{test_crypto.py, test_framework.py, test_oauth_engine.py}   # T70–T89
```

## 3. `services/channel_crypto.py` (write + test before any model)

Self-contained; do NOT import from health_phi_encryption (no new dependency, no
private-function coupling). ~60 lines:

```python
TOKEN_PREFIX = 'chs$1$'
_HKDF_INFO = b'health19-channel-secret-v1'
_HKDF_SALT = b'health19-phi'          # same salt family as phi_crypto, distinct info
```
- Root key: env `HEALTH_PHI_KEY` (base64, ≥32 bytes, ValueError if shorter) else HKDF
  from `ir.config_parameter` `database.secret` — clone the recipe shape of
  `health_phi_encryption/models/phi_crypto.py:40-63` (READ it; copy the logic, not the
  import). Derive ONE 32-byte AES subkey with the info above (cryptography lib HKDF,
  SHA-256). Per-DB cache dict + `clear_key_cache(dbname=None)`.
- `encrypt(env, plaintext) -> str`: falsy/non-str pass through; idempotent on
  `chs$1$` prefix; AES-256-GCM, 12-byte `os.urandom` nonce,
  `'chs$1$' + b64encode(nonce + ct_with_tag)`.
- `decrypt(env, token) -> str`: value without the prefix passes through unchanged
  (migration tolerance); on InvalidTag/b64 garbage **RAISE ValueError** (deliberate
  divergence from phi_crypto's marker-return — a corrupted secret must never flow to a
  provider silently).
- `is_encrypted(value) -> bool`.

## 4. Models — implementation-grade spec

Model names, fields, states: EXACTLY architecture §5.1–§5.5. Additional binding
details:

### 4.1 `channel.platform.app`
- `init()`: `CREATE UNIQUE INDEX IF NOT EXISTS channel_platform_app_provider_uniq ON
  channel_platform_app (provider) WHERE active` (§5.1 gotcha — no _sql_constraints).
- `action_set_secret(secret)` — `@api.model`-NOT; instance method, `ensure_one`,
  callable only by group_system (explicit `self.env.user.has_group` check + ACL),
  writes `client_secret_enc = channel_crypto.encrypt(...)`, sets
  `secret_hint = '••••' + secret[-4:]`, audits `secret_rotated`, returns
  `display_notification` "Secret stored". The form NEVER has a client_secret field;
  use a TransientModel wizard `channel.platform.app.secret.wizard` with a `password="1"`
  Char, `action_apply` calls `action_set_secret` then closes.
- `_get_secret(self)` — internal, decrypt via sudo; NEVER exposed over RPC (name-mangle
  by convention: methods starting `_` are not RPC-callable in Odoo — rely on that +
  test T74).
- No mail.thread inheritance (nothing to track — Z1 lesson), `_description` set.

### 4.2 `care.channel.connection`
- `init()`: partial unique `(channel, company_id) WHERE active` — clone
  care_conversation.py:161-171 shape.
- State transitions via ONE method `_transition(new_state, reason=None)` that
  validates against an allowed-transitions dict, audits `health_transition`, and is
  the ONLY writer of `state` (plus a `write()` guard: direct RPC writes of
  `state`/`*_enc`/`granted_scopes`/`resource_*` by non-system users raise UserError —
  §5.4/§5.37-corollary posture; user-editable fields whitelist: `active` only).
- `action_set_secret(field_key, secret)` — field_key ∈ {access_token, refresh_token,
  provider_secret}; group-gated to tenant-admin/crm-manager + company check; encrypts,
  hints, audits. `_get_secret(field_key)` internal as above.
- `_required_checks()` → asks the adapter's `authorization_capabilities()`
  ["required_checks"]; `_recompute_ready()`: if state in (testing, ready,
  action_required, expiring) and all required checks pass → `ready`; any required fail
  → stay/fall to `action_required` (never silently to error). Called from readiness
  check writes.
- `readiness_summary()` @api.model-style instance JSON for future UI: list of
  {check_key, status, detail} — NO secrets, NO raw provider errors (redaction helper
  §4.5).
- Company record rule (both directions) cloned from
  `health_care_command/security/care_command_security.xml:7-26`; ACL per architecture
  §5.2 (tenant admin group = `health_user_admin.group_health_user_admin` — add
  `health_user_admin` to depends? NO — soft-reference: grant the ACL rows to
  `health_crm.group_health_crm_manager` and `base.group_system` only in THIS phase, and
  add the user-admin ACL in CC-C when the UI lands; document this deferral in the
  report).

### 4.3 `care.channel.oauth.session`
- `create_for(connection, redirect_target)` @api.model: validates redirect_target
  (§4.6), generates `state = secrets.token_urlsafe(32)` + optional PKCE verifier
  (`secrets.token_urlsafe(64)`, challenge = S256 per RFC 7636), stores
  `state_hash = sha256(state)`, `pkce_verifier_enc`, `expires_at = now + 10min`,
  returns `{state, code_challenge}` — the ONLY time raw state leaves the server.
- `_consume(state)` @api.model: hash lookup; None if unknown/`used_at`/expired
  (single generic outcome — no oracle); sets `used_at` immediately in the same
  transaction BEFORE any provider HTTP (single-use even on later failure).
- init() unique index on state_hash. Purge cron: sessions older than 24 h unlinked
  nightly.

### 4.4 `care.channel.readiness.check`
Unique (connection_id, check_key) init() index. `upsert_check(connection, key, status,
detail=None)` helper (ON CONFLICT-free: search+write/create — volumes are tiny), calls
`connection._recompute_ready()` after write. `detail` passes through `_redact()`.

### 4.5 `care.channel.audit` + redaction
Clone health_consent_check_log posture verbatim (unconditional write/unlink raise —
health_consent/models/health_consent_check_log.py:39-52). `log(company_id, event,
connection=None, user=None, detail=None)` classmethod: `sudo().create` inside
try/except (never breaks caller). `_redact(text)` in a shared `services/redact.py`-
level helper or on the audit model: truncate 300 chars; regex-strip values of keys
matching `(?i)(token|secret|key|code|signature|password|authorization)[=:]\S+` →
`<redacted>`; strip full URLs' query strings. EVERY detail string in the module flows
through it (grep-able rule for review).

### 4.6 Redirect-target allowlist
`_allowed_redirect(url)`: allow relative paths starting `/`; absolute only if host ∈
{urlparse(web.base.url).netloc} ∪ comma-list param
`channel_hub.allowed_redirect_hosts` (default empty). Reject others with False (caller
raises UserError with a FIXED string).

### 4.7 `res.config.settings`
One field: `channel_hub_allowed_redirect_hosts` (config_parameter
`channel_hub.allowed_redirect_hosts`). Char — the §5.36 trap is Boolean/Integer-
specific; still add the health_care_command_ai-style comment noting why no override is
needed for Char. View: xpath into `//app[@name='health_base']`, block
`channel_hub_settings`, gated `base.group_system`.

## 5. Adapter registry (`services/adapters.py`)

`CHANNEL_ADAPTERS` dict + `@register_adapter(key)` + `get_adapter(env, connection)`.
`BaseChannelAdapter` with the FULL interface from architecture §6 — every method
`raise NotImplementedError` except `authorization_capabilities()`. Ship 8 stub
adapter classes (one per channel key) whose ONLY implemented member is
`authorization_capabilities()` returning the real declared capabilities (matrix §3 of
the architecture doc):

| key | mode | needs_platform_app | webhook_auto | supports_refresh | required_checks |
|-----|------|--------------------|--------------|------------------|-----------------|
| whatsapp | embedded_signup | True | True | False (BISU no-expiry) | authorization_valid, scopes_granted, resource_selected, webhook_configured, outbound_ok, provider_approvals |
| fb | oauth_popup | True | True | False | authorization_valid, scopes_granted, resource_selected, webhook_configured, outbound_ok |
| zalo | oauth_popup | True | False (portal) | True (single-use rotation) | authorization_valid, resource_selected, webhook_configured, webhook_verified, outbound_ok, token_fresh |
| zns | (capability of zalo — adapter declares `parent_channel: 'zalo'`, required_checks adds provider_approvals) | True | False | True | authorization_valid, provider_approvals |
| telegram | guided_secret | False | True | False | authorization_valid, resource_selected, webhook_configured, outbound_ok |
| email | oauth_popup (delegated to Odoo mixins in CC-F) | True | n/a | True | authorization_valid, resource_selected, outbound_ok, inbound_ok |
| call | guided_secret | False | False | False | authorization_valid, resource_selected, webhook_configured, inbound_ok |
| webchat | one_click | False | n/a | False | resource_selected, inbound_ok |

(Stubs are the contract the UI + later phases build against; exact dict keys per
architecture §6 docstring. `zns.parent_channel` is how the UI later shows ZNS readiness
as a sub-card of Zalo.)

## 6. OAuth callback controller (`controllers/oauth.py`)

`GET /channel_hub/oauth/callback/<string:provider>` — `type='http'`, `auth='public'`,
`save_session=False`. Sequence:
1. `gateway.rate.counter.hit(f'chub:cb:{ip}')` (clone
   health_family_link/controllers/family_public.py:20-31) → 429 page when blocked.
2. `state = request.httprequest.args.get('state')`; missing → generic error page.
3. `session = env(su=True)['care.channel.oauth.session']._consume(state)` → None ⇒
   SAME generic error page (no oracle: unknown == used == expired).
4. provider mismatch vs session.provider ⇒ generic page.
5. `error`/`denied` params ⇒ session.outcome='denied', audit, friendly "You cancelled
   — nothing was connected" page.
6. Else: `adapter.handle_callback(session, params)` inside `cr.savepoint()` — in THIS
   phase only the mock/test adapter implements it; real ones come in CC-D/E/F. Outcome
   'ok' → success page.
7. Response pages: minimal QWeb (no website dep — family_link precedent), containing
   `window.opener && window.opener.postMessage({channelHub: true, ok: <bool>,
   channel: <key>}, <web.base.url origin>)` + a visible VI/EN "Return to Health19"
   link. NEVER echo state/code/params into the page.

## 7. Crons (`data/ir_cron.xml`, noupdate=1, health_consent shape)

1. `_cron_channel_health` (30 min): connections `next_health_check_at <= now AND state
   not in (not_connected, disabled, legacy)` → `adapter.health_check()` in per-record
   savepoint; NotImplementedError ⇒ skip quietly (stubs); failure backoff 30m→2h→8h via
   `consecutive_failures`; expiry sweep per architecture §8 (7-day warning activity to
   the connection's company tenant admins — `mail.activity` on the connection record,
   summary fixed-string, NO credential text).
2. `_cron_purge_oauth_sessions` (daily 02:40): unlink sessions `create_date < now-24h`.

Token refresh lock scaffold (`refresh_authorization` is per-provider, later phases):
implement `_with_refresh_lock(callable)` on connection NOW — `SELECT id FROM
care_channel_connection WHERE id=%s FOR UPDATE NOWAIT` in a try/except
psycopg2.errors.LockNotAvailable ⇒ return 'locked'; new-refresh-token persist via
separate cursor (clone the fresh-cursor idiom from
health_api_gateway/controllers/gateway.py:240-249) — unit-tested with a fake callable
(T85), used for real in CC-D.

## 8. Security file specifics

- Groups: NO new groups this phase. ACL rows:
  `channel.platform.app` → base.group_system rwcu ONLY (no other rows).
  `care.channel.connection` → crm_manager rwc (no unlink; disconnect is a state, not a
  delete), crm_user r, system rwcu.
  `oauth.session`/`readiness.check`/`audit` → system rwcu?? NO: audit r for
  crm_manager (they can view history), create via sudo only (no create ACL needed for
  sudo); session NO acl rows except system (server-only model); readiness r for
  crm_user+manager.
- Record rules: company rules on connection, readiness (via connection_id.company_id),
  audit (company_id), session (company_id) — clone care_command_security.xml.
- `*_enc` fields: `groups='base.group_system'` on field definitions AND absent from
  all views.

## 9. Binding NON-goals (this phase)

- NO care_command core edits (no `_channel_keys()` override — dock unchanged).
- NO provider HTTP implementations, NO webhook message routes, NO messaging models.
- NO OWL UI beyond standard backend list/form views (list of connections showing
  state/health chips via badges; platform app form for operators) hung under
  `health_care_command.menu_care_command_config` (menuitem "Channels (setup)" gated
  crm_manager; platform apps menuitem gated base.group_system).
- NO migration of zalo.config/voip.config (CC-D/CC-F).
- NO pip installs (cryptography 49 already on server — §1 conventions).
- NO health_user_admin dependency (deferred to CC-C — §4.2 note).

## 10. Tests (T70–T89, TransactionCase only, @tagged post_install/-at_install)

test_crypto.py:
- **T70** roundtrip: encrypt→prefix chs$1$→decrypt equals; idempotent re-encrypt;
  falsy passthrough.
- **T71** tamper: flip one ciphertext byte → decrypt RAISES ValueError; non-prefixed
  value passes through unchanged.
- **T72** key isolation: channel token is NOT decryptable by phi_crypto (import
  health_phi_encryption if installed else skipTest) and vice versa — proves distinct
  subkeys.

test_framework.py:
- **T73** platform app: unique-active-per-provider index fires (§5.3 pre-check
  pattern: expect IntegrityError inside savepoint or pre-check ValidationError);
  secret wizard stores encrypted + hint set + plaintext absent from DB row
  (`cr.execute` raw read asserts `chs$1$` prefix).
- **T74** secret non-exposure: crm_manager `read()` on connection raises/omits `*_enc`
  (AccessError on field or field absent), `export_data(['access_token_enc'])` denied;
  `readiness_summary()` output contains no `chs$1$` substring anywhere.
- **T75** connection state machine: allowed transitions pass + audited; disallowed
  (`not_connected → ready`) raises; direct RPC `write({'state': 'ready'})` as
  crm_manager raises UserError (write-guard).
- **T76** one-active-connection-per-channel-company: second active (whatsapp,
  company) blocked; archived one allowed.
- **T77** readiness derivation: seed required checks per stub capabilities → all pass
  ⇒ state ready; flip one to fail ⇒ action_required; n_a counts as satisfied only when
  not in required set. `_recompute_ready` never fires from not_connected.
- **T78** audit append-only: write() and unlink() both raise for admin (uid 1 — §5.4);
  `log()` inside a raising caller doesn't break the caller (savepoint).
- **T79** redaction: `_redact('access_token=abc123 https://x.y/cb?code=zzz&state=s')`
  contains no abc123/zzz/s; 300-char truncation.
- **T80** company isolation: company-2 connection invisible to company-1 crm_manager
  (search + browse AccessError via record rule).
- **T81** adapter registry: all 8 keys registered; capabilities dicts carry required
  keys; unknown key raises; zns declares parent_channel zalo.

test_oauth_engine.py:
- **T82** session create: raw state returned once; DB stores hash only (raw grep on
  column); PKCE challenge = RFC7636 S256 of verifier (recompute + compare).
- **T83** consume single-use: first consume ok + used_at set; second returns None;
  expired (backdate expires_at) returns None; unknown returns None — all three
  indistinguishable.
- **T84** callback controller logic via direct method call (no HttpCase — §5.32):
  denied params → outcome denied + audit row; consumed-state reuse → generic outcome;
  provider mismatch → generic. (Controller thin-shell rule: put the logic in a model
  method `care.channel.oauth.session._handle_callback(provider, params)` so
  TransactionCase covers it; the controller is 10 lines of header plumbing.)
- **T85** refresh lock: `_with_refresh_lock` runs callable under row lock; simulated
  concurrent lock (second cursor NOWAIT) returns 'locked' without raising; fresh-cursor
  persist helper writes a value that survives `cr.rollback()` of the outer tx (assert
  via new cursor read; clean up after).
- **T86** redirect allowlist: relative ok; own-host absolute ok; foreign host False;
  host added via config param → ok.
- **T87** health cron: due connection with stub adapter (NotImplementedError) skips
  quietly + reschedules; forced failing fake adapter increments consecutive_failures
  + backoff grows; token_expires_at in 5 days ⇒ health_status expiring + ONE activity
  created (idempotent on second run).
- **T88** session purge cron: >24 h session unlinked, fresh one kept.
- **T89** settings param: allowed hosts write/read via res.config.settings roundtrip.

All `requests` usage mocked (there should be none executed in this phase); no real
HTTP. Fixture note: create test companies + crm users per care_command test file
patterns (test_care_command.py:50-126).

## 11. Deploy (vietuat — conventions §2/§5.45) & report-back

1. Standard copy + `-i health_care_command_channels` with
   `--test-tags /health_care_command_channels` `--no-http` (TransactionCase only).
   Then a second run `--test-tags /health_care_command,/health_care_command_ai,/health_care_command_voip`
   proving zero regression (no core files touched — this run is the proof).
2. Report: files list, deviations, verbatim test result lines (both runs), the §4.2
   ACL deferral note, any new gotcha for the ledger.
3. Data honesty: 0 platform apps, 0 connections on vietuat after deploy; menus visible
   to manager/system only; dock/care-command behavior UNCHANGED (state that you
   verified the workspace loads).
4. NO browser evidence pack needed beyond a screenshot of the two new backend menus
   (backend-only phase, §8.1).

**Kickoff line for the Opus session:**
Implement `docs/strategy/handovers/channel-center-phaseA.md` (Channel Center Phase
CC-A — new module `health_care_command_channels` connection framework core:
channel_crypto AES-GCM secret layer, channel.platform.app + care.channel.connection +
oauth.session + readiness + append-only audit, adapter registry with capability stubs
for all 8 channels, fail-closed OAuth callback engine with hashed single-use state +
PKCE, health/purge crons, security). Read `docs/strategy/HANDOVER-CONVENTIONS.md` AND
`docs/strategy/handovers/channel-center-architecture.md` first. Zero edits to
health_care_command core or health_zalo/health_voip24h; TransactionCase-only T70–T89;
no real HTTP or credentials anywhere; deploy to vietuat per §11 and report per §11.
