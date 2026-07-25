# Channel Connection Center — Architecture, Trust Boundaries & Phase Plan

**Status:** DESIGN (Fable, 2026-07-25). Supersedes the credential-entry assumption of
`care-command-phase6.md` (the adapter/webhook/identity/message spine of that handover is
PRESERVED and folded into Phase CC-B below; its "ops enters tokens, system-only ACL,
everything ships draft" posture is REPLACED by tenant self-service).
**Read with:** `docs/strategy/HANDOVER-CONVENTIONS.md` (§5.61 webhook posture is binding
everywhere; §5.36 settings-toggle trap; §5.4 unconditional guards; §5.32/§5.48
config-param caches; §5.55 savepoint ingest; §29/§5.58 vi.po markers).

The goal: **Care Command → Settings → Channels**, where a tenant administrator connects
Zalo/ZNS, WhatsApp, Facebook Messenger, Telegram, Email, Calls (VoIP24h) and Web Chat
by signing in with the provider directly — no Health19 implementor, no provider
passwords, no tenant ever seeing a platform app secret.

---

## 1. Current state (verified 2026-07-25, all file:line checked on branch 19.0)

### 1.1 Care Command spine (health_care_command 19.0.4.0.0, P5 live)

- All 8 channel keys shipped: `CHANNEL_SELECTION` at
  `health_care_command/models/care_conversation.py:43-52` —
  `zalo, call, email, zns, whatsapp, fb, telegram, webchat`. **`fb` = Facebook
  Messenger specifically** (label "Messenger", JS "FB MSGR" `care_command.js:21`).
  Instagram is NOT a channel key and is out of scope (documented extension, §13).
- Channel truth model: `channel_primary` (:97-99), `channel_declared` (:102-104),
  `channel_effective` stored compute (:107-110, compute :244-250),
  `has_channel_activity` (:114). `MODE_TO_CHANNEL` :58-66.
- **Dock gating seam already exists**: `_channel_keys()` :547-552 → `active_channels`
  payload :645 → JS dock active state (`care_command.js:249-254`). The Connection
  Center flips dock icons on/off purely server-side.
- Identity matching: `_find_or_create_for(anchor, signal)` :343-442, precedence
  `zalo_conversation_id → partner_id → lead_id → phone_normalized → email_normalized`,
  fill-never-overwrite. `init()` partial unique index :161-171; `_check_anchor`
  :173-186; `_safe_phone` :292-301.
- Send paths that work today: `action_send_zalo` :1081-1105 (delegates to
  `zalo.message.action_send_message`), `action_send_email` :1126-1166. Capabilities
  are inline at :756-759 (`can_reply_zalo/can_reply_email`) — no `_capabilities()`
  extraction yet, no `_apply_signal()` extraction yet (phase6 core touches still to do).
- **No message-id dedupe exists anywhere** (idempotency today is set-not-increment
  unread semantics only). `zalo.message.zalo_message_id` is indexed but not unique and
  never searched on ingest.
- Settings surface: NONE in core. Manager-only menu `menu_care_command_config`
  ("Care Command Setup", `views/care_command_admin_views.xml:88-92`) is the natural
  parent for "Channels". `res.config.settings` precedent lives in
  `health_care_command_ai/models/res_config_settings.py:13-48` (explicit
  `set_values` writing `"True"/"False"` strings — §5.36).
- Frontend: ONE OWL component `CareCommand` (`static/src/js/care_command.js:35`),
  exported at :568 (AI module patches it — `.sendbtn` / `.crail-tabs` class names are
  load-bearing seams). Assets: `web.assets_backend` only; no public bundle exists.
- Security: reuses `health_crm.group_health_crm_user/_manager`; `_ensure_access()`
  :507-510; global company rules `security/care_command_security.xml:7-26`; reads are
  sudo-after-group-gate (documented posture :11-16).
- Tests: 46 TransactionCase across the 3 care_command modules, zero HttpCase, global
  T-numbering (phase6 reserved T50–T69; Connection Center phases start at **T70**).
- `care.reply.template.channel` selection still only `any/zalo/call/email/zns`
  (`care_reply_template.py:24-35`) — gap for the 4 new channels.
- ⚠️ The phase6 handover's line citations into `care_conversation.py` are STALE
  (file grew in P5). Corrected positions are the ones cited above.

### 1.2 health_zalo — works, but is a security repair case

Config: `zalo.config` model (per-company, `models/zalo_config.py`) — plaintext
`app_id/app_secret/oa_id/access_token/refresh_token/webhook_secret` behind
field-`groups='base.group_system'` only. **Defects verified:**

| # | Defect | Where |
|---|--------|-------|
| Z1 | `app_secret` has `tracking=True` → secret values copied into `mail.tracking.value` on every change (leak path that bypasses field groups) | zalo_config.py:54-60 |
| Z2 | Webhook fails OPEN 3 ways (no config/secret → accept; missing header → accept; wrong formula — HMAC(webhook_secret, re-serialized JSON) matches nothing Zalo actually sends) | controllers/webhook.py:117-156 |
| Z3 | `with_delay()` with no queue_job addon → AttributeError swallowed → **all inbound webhook events silently dropped while returning 200** | controllers/webhook.py:46, 51-54 |
| Z4 | No `ir.rule` anywhere → cross-company read of config/conversations/messages | security/ |
| Z5 | `api_base_url` writable by `group_zalo_manager` → token-exfil vector (next refresh posts app_id+refresh_token to attacker host) | ir.model.access.csv:3 + services/zalo_api.py:140 |
| Z6 | OAuth: no PKCE (Zalo v4 REQUIRES S256); state persisted forever, never cleared, not bound to user/session; `oauth_code` persisted permanently; naive `datetime.now()` vs UTC expiry skew | zalo_config.py:188-235, 228/251 vs :318 |
| Z7 | No inbound idempotency (`zalo_message_id` stored, never deduped) | zalo_message.py:292-293 |
| Z8 | Token endpoints wrong: exchange posts to `{api_base_url}/v4/access_token` (real: `oauth.zaloapp.com/v4/oa/access_token` with `secret_key` HEADER); refresh omits the secret_key header entirely | services/zalo_api.py:97-160 |
| Z9 | Dead/demo hazards: auto-created "Demo Zalo Config (Testing)"; broken `zalo.link.user.wizard` button; `action_enable_webhook` is a TODO that flips a boolean | res_partner.py:104-136, :187; zalo_config.py:345-377 |

**Frozen public API (blast radius for any refactor):** 9 modules call
`from odoo.addons.health_zalo.services.zalo_api import get_api_client` +
`env['zalo.config'].search([('active','=',True)], limit=1)` +
`send_zns_notification(config, phone, template_id, params)` (error-dict contract), and
every ZNS test in the repo patches `ZaloAPIClient.send_zns_notification` or
`zalo.message.action_send_message`. These signatures MUST keep working verbatim.
ZNS template ids live in per-module `ir.config_parameter`s (8 modules) — unchanged.

### 1.3 health_voip24h — the security precedent (and a guided-wizard case)

- `voip.config` per-company; `api_key/api_secret` (`groups='base.group_system'`,
  deliberately NOT tracked — voip_config.py:43-51), computed `webhook_url` :179-184,
  company record rule (voip24h_security.xml:46-52).
- **The fail-closed verifier to clone everywhere:** `_verify_webhook_signature`
  voip_config.py:422-442 (no secret → False + loud log; no header → False;
  HMAC-SHA256 over raw bytes; `sha256=` prefix stripped; `hmac.compare_digest`).
  Controller posture `controllers/webhook.py:24-90`: `type='http'`, raw
  `get_data()` first, `su=True` only after, generic non-oracle responses,
  200-after-verification to stop retry storms.
- Auth against VoIP24h: NOT OAuth — key+secret exchanged for a short-lived bearer;
  `_ensure_authenticated` re-logins on expiry (services/voip24h_api.py:48-95). So
  VoIP24h is definitionally a **guided-secret-entry** channel.
- ⚠️ **Endpoint honesty problem**: the module's endpoints
  (`api.voip24h.vn/v1`, `/auth/login`, `/calls/*`) do NOT match VoIP24h's publicly
  visible SDK pattern (`GraphModule.getAccessToken`, `call/find`, `call/findone`).
  The official reference `docs-sdk.voip24h.vn` is geo-blocked outside VN. The
  VoIP24h phase (CC-F) therefore STARTS with fetching the real docs from the UAT
  server (VN IP) and reconciling; no claim of live VoIP24h connectivity is made
  until then.
- Gaps: no unique index on `account_id` (webhook routing key), no replay protection.

### 1.4 Reusable platform pieces (verified)

| Need | Reuse | Where |
|------|-------|-------|
| Reversible encryption at rest | `phi_crypto` recipe — AES-256-GCM, HKDF from `HEALTH_PHI_KEY` env var (fallback `database.secret`), versioned token prefix; live non-PHI precedent: `health_family_messages` body_enc | health_phi_encryption/models/phi_crypto.py:33-116 |
| Show-once + hash-only secrets | `gateway.oauth.client._hash_secret/_verify_secret/action_regenerate_secret` (sticky notification, plaintext never stored); `gateway.token` sha256-hash-lookup with `init()` unique index | health_api_gateway/models/gateway_oauth_client.py:50-112, gateway_token.py:32-79 |
| Public-endpoint rate limiting | `gateway.rate.counter.hit(key_ref)` — atomic ON CONFLICT upsert → (allowed, retry_after) | gateway_rate_counter.py:36-70 |
| Append-only audit (lightest tier) | `health.consent.check.log` — flat model, unconditional `write/unlink` raise, no su escape, `sudo().create()` in try/except | health_consent/models/health_consent_check_log.py:39-52 |
| Outbound signed webhooks + outbox | `integration_outbox` (FOR UPDATE SKIP LOCKED) + `webhook_delivery` (signature over exact bytes, backoff, auto-deactivate) | health_api_gateway/models/ |
| Consent gate for real sends | `env['health.consent'].check_consent(partner, type, …)` — never raises; composite gate precedent `health_family_messages/models/health_family_link.py:18-34` | health_consent/models/health_consent.py:523-585 |
| Email OAuth transport | Odoo 19 built-ins `google_gmail` / `microsoft_outlook` — XOAUTH2 mixins on ir.mail_server/fetchmail.server, client in `ir.config_parameter`, refresh handling incl. Microsoft rotation | odoo/addons/{google_gmail,microsoft_outlook} (branch 19.0) |
| Cron shape | health_consent/data/ir_cron.xml (noupdate=1, state=code, user_root, staggered nextcall) | — |
| Settings page shape | xpath into `//app[@name='health_base']`; §5.36 set_values override | health_care_command_ai + health_telehealth precedents |

**No vault/secret-store abstraction exists in the repo — the credential layer in §5 is
net-new, assembled from the pieces above.**

### 1.5 Tenancy & personas (verified)

Deployment reality: effectively **single-company-per-DB** (SaaS tenant = database, so
"per-deployment platform credentials" and "per-DB config" coincide; environments
dev/staging/prod are separate DBs and therefore separate platform records naturally).
`company_id` + record rules still enforced everywhere (care_command precedent) so
multi-company installs stay safe.

| Persona | Group | Powers in the Channel Center |
|---------|-------|------------------------------|
| Tenant administrator | `health_user_admin.group_health_user_admin` (SaaS-safe: implies healthcare_admin, cannot see `base.group_system` users) | connect/reconnect/test/disconnect own-company channels; never reads tokens; never sees platform secrets |
| Care Command manager | `health_crm.group_health_crm_manager` | same connection management rights as tenant admin (they run the desk day-to-day) |
| Ordinary agent | `health_crm.group_health_crm_user` | read-only status chips (Connected/Action required/…); no credential fields, no connect actions |
| Platform operator | `base.group_system` | ONLY role that can read/write `channel.platform.app` records (per-deployment provider apps) |

---

## 2. Gap assessment

1. **No connection framework** — 3 unrelated config surfaces exist (`zalo.config`,
   `voip.config`, Odoo mail servers); 4 channels have nothing; none is self-service.
2. **No secret hygiene** — plaintext columns, one live tracking-leak (Z1), no
   encryption at rest, no show-once UX, tokens readable by any base.group_system form.
3. **No OAuth engine** — the only OAuth flow (Zalo) lacks PKCE, state binding/expiry/
   single-use, and posts through the wrong host; nothing generic exists.
4. **No webhook framework** — one good controller (voip24h), one fail-open trap
   (zalo), none for Meta/Telegram/webchat; no replay handling, no dedupe framework.
5. **No readiness/health model** — "state=connected" booleans at best; nothing
   distinguishes authorized vs resource-selected vs webhook-verified vs outbound-proven;
   no expiry alerts, no permission-loss detection.
6. **No tenant-facing UI** — all existing config is admin form views behind
   base.group_system fields.
7. **Care Command honesty** — dock shows all 8 keys as known; `_channel_keys()`
   override that reflects real connections is designed (phase6 §5.3) but not built.

---

## 3. Provider capability matrix

Verified against official provider documentation 2026-07-25 (research citations in the
per-phase handovers). Legend: ✅ automatable by our software · 👤 tenant clicks inside
provider surfaces · 🔧 one-time platform-operator action · ❌ does not exist.

| Capability | WhatsApp Cloud | FB Messenger | Zalo OA / ZNS | Telegram | Gmail | Microsoft 365 | VoIP24h | Web Chat |
|---|---|---|---|---|---|---|---|---|
| Authorization method | Embedded Signup **v4** (FB JS SDK popup, `config_id`, code TTL 30 s) | FB Login for Business (`config_id`) | OAuth v4, **PKCE S256 required** | ❌ OAuth — BotFather token paste + `getMe` | OAuth2 XOAUTH2 (Odoo built-in) | OAuth2 `/common` multi-tenant (Odoo built-in) | API key+secret → bearer (guided entry) | none (our own widget) |
| Platform app needed | 🔧 Meta Business app + Business Verification + App Review (2 perms, screencasts) + ES configuration | 🔧 same Meta app, second FLB configuration + 3 page perms | 🔧 Zalo app (developers.zalo.me) + OA API product + app review | ❌ (none) | 🔧 Google Cloud OAuth client + consent screen + **restricted-scope verification + annual CASA** | 🔧 Entra multi-tenant app + publisher verification | ❌ (per-tenant credentials only) | ❌ |
| Delegated per tenant | Business (BISU) token, **never expires** by default | Page token via `/me/accounts`, **no expiry** (long-lived path) | OA access token 25 h + refresh 3 mo **single-use rotation** | bot token (static until /token revoke) | refresh token (6-mo-unused expiry; 100/client/account cap) | refresh token 90-day sliding, **rotates every use** | api_key/api_secret (portal/support-issued) | n/a |
| Resource selection | WABA + phone number (from `WA_EMBEDDED_SIGNUP` event + `/{waba}/phone_numbers`) ✅ | Page picker from `/me/accounts` ✅ | OA fixed by grant; `oa_id` in callback + `getoa` confirm ✅ | bot fixed by token; `getMe` shows name ✅ | mailbox = authorizing account ✅ | mailbox = authorizing account ✅ | PBX account (entered) 👤 | n/a |
| Webhook registration | ✅ `POST /{waba}/subscribed_apps` (+ optional per-WABA `override_callback_uri`); app-level URL 🔧 once | ✅ `POST /{page}/subscribed_apps`; app-level URL 🔧 once; route by page_id | ❌ API — **portal-only, ONE URL per app** 🔧 once; route by `oa_id` in payload | ✅ `setWebhook` per bot with `secret_token` | n/a (IMAP poll via fetchmail) | n/a (IMAP poll) | portal/support-set 👤 (signature scheme UNVERIFIED — geo-blocked docs) | n/a |
| Webhook verification | `X-Hub-Signature-256` HMAC-SHA256(app secret, raw bytes) | same | `X-ZEvent-Signature` `mac=sha256(appId+rawBody+timestamp+**per-OA secret**)` (plain SHA-256, not HMAC) | `X-Telegram-Bot-Api-Secret-Token` echo + path secret | n/a | n/a | assume unsigned until docs verified; secret-in-path fallback | n/a (rate-limited public routes) |
| Outbound restrictions | 24 h CS window; outside → approved templates (auto-review ≤24 h); opt-in required for business-initiated | 24 h window; **only HUMAN_AGENT tag survives (7 d)** — CONFIRMED_EVENT_UPDATE etc. dead since 2026-04-27 | 48 h window, 8 free consultation replies; beyond → paid tiers or ZNS templates (human review 2–3 d, ZCA-funded, verified OA) | 1 msg/s/chat, 30/s global; user must /start first | send limits per Google | SMTP AUTH may be tenant-disabled; send-rate param | telephony (no messaging window) | our rules |
| Tenant-side approvals | payment method on WABA 👤; display-name review 👤; business verification of THEIR business 👤 | page admin rights 👤 | OA yellow-tick verification 👤; ZCA funding for ZNS 👤 | none | consent screen shows OUR verified brand | tenant may require admin consent 👤 | contract with VoIP24h 👤 | none |
| Test facility | Meta test WABA + test number (5 recipients) ✅ | test users/pages ✅ | sandbox limited; use dev-mode app ✅ | real bot free ✅ | send-to-self ✅ | send-to-self ✅ | unknown until docs | built-in demo page ✅ |
| Healthcare notes | Policy allows unless local law prohibits PHI on channel (VN: keep clinical detail out; deep-link to tokenized portal — existing rails) | same posture | ZNS healthcare templates fit "customer care"; stricter OA category review for healthcare | cloud chats not E2E — keep PHI out of payloads, deep-link | mailbox is tenant's own | same | n/a | PHI never in widget; anonymous until identified |

**Unverifiable-by-software gates are surfaced as PENDING TASKS in the UI, never as
errors** (Meta business verification, display-name review, ZNS template approval, OA
yellow tick, Google CASA, Microsoft publisher verification).

---

## 4. Authorization principle — two credential planes

**Plane 1 — Platform credentials** (`channel.platform.app`, §5.1): one record per
provider per deployment DB. Meta app id/secret + 2 ES/FLB config_ids, Zalo app id/secret,
Google client, Microsoft client. Entered ONCE by the platform operator
(base.group_system) per environment. Tenants NEVER see, enter, or receive these.
Absence of a platform app renders the channel card "Not available yet — contact
Health19" (honest, not an error).

**Plane 2 — Tenant authorizations** (`care.channel.connection`, §5.2): what the tenant
grants by signing in with the provider — tokens, resource ids (Page/WABA/phone/OA/
mailbox/bot), granted scopes, expiry, webhook state. Company-scoped, encrypted at rest,
never returned to any browser after capture.

Trust boundaries:

```
 tenant admin browser ──(popup)──► provider consent UI          (password typed HERE only)
        │                                   │
        │ opens stepper                     │ redirect w/ code+state
        ▼                                   ▼
 OWL Channel Center ◄──poll/postMessage── /channel_hub/oauth/callback  (public, state-gated)
        │                                   │ server-side code→token exchange
        ▼                                   ▼
 care.channel.connection ◄────────── channel_crypto AES-GCM at rest
        ▲                                   ▲
 agents: status only                 platform operator: channel.platform.app only
 provider ──signed raw-bytes──► /channel_hub/webhook/* (fail-closed, §5.61 posture)
```

---

## 5. Data model (new module `health_care_command_channels`)

All models `_description`'d, company-scoped where tenant-owned, `init()` unique
indexes per §5.1 gotcha. ⚠️ Names below are binding for Phase CC-A.

### 5.1 `channel.platform.app` — Plane-1 record (platform operator only)
`provider` Selection [meta, zalo, google, microsoft] (unique per provider via init()
index), `client_id` Char, `client_secret_enc` Text (channel_crypto), `extra_json` Text
(ES config_id, FLB config_id, meta verify_token…, json.dumps), `active`,
`environment_note` Char. **ACL: base.group_system rwcu ONLY; no other group has read.**
No tracking on any field. Secret entry via `action_set_secret` (write-only, §7.2).
Telegram/VoIP24h/webchat need no row (no platform app exists for them).

### 5.2 `care.channel.connection` — Plane-2 tenant connection
One per (channel, company) active — partial unique init() index. Fields:
- `channel` Selection (all 8 keys), `company_id` (required, default, index), `active`
- `state` Selection: `not_connected → authorizing → select_resource → configuring →
  testing → ready | action_required | expiring | error | disabled | legacy`
  (legacy = migrated-but-unconverted, §10)
- resource: `resource_external_id` Char (PSID-page id / phone_number_id / oa_id /
  bot id / mailbox / PBX account), `resource_secondary_id` Char (WABA id),
  `resource_display_name` Char — the card subtitle
- credentials (ALL via channel_crypto, §7.1): `access_token_enc`, `refresh_token_enc`,
  `provider_secret_enc` (per-OA Zalo webhook secret / TG bot token / VoIP api_secret),
  plus `secret_hint` Char ("••••1234") and `has_credentials` Bool for UI
- `granted_scopes` Char (space-separated as provider reports), `token_expires_at`
  Datetime (UTC ONLY — fields.Datetime), `refresh_lock` (see §7.4)
- webhook: `webhook_state` Selection [none, pending, subscribed, verified, failing],
  `webhook_path_secret` Char (Telegram/VoIP URL path), `last_webhook_at` Datetime
- health: `last_inbound_at`, `last_outbound_at`, `health_status` Selection [healthy,
  action_required, expiring, permission_lost, webhook_failing, provider_down],
  `next_health_check_at`, `consecutive_failures` Int, `last_error_redacted` Char
- **ACL:** tenant-admin + crm-manager rwcu, crm-user read; company record rule; BUT all
  `*_enc` fields carry `groups='base.group_system'` AND are excluded from views —
  defense in depth; reads/writes of secrets happen only in server sudo paths (§7.2).
  No `tracking=True` on ANY credential-adjacent field (Z1 lesson).

### 5.3 `care.channel.oauth.session` — single-use authorization attempt
`connection_id`, `company_id`, `user_id`, `provider`, `state_hash` Char (sha256 of the
random state; raw state returned once to the browser — gateway.token pattern),
`pkce_verifier_enc` Text, `redirect_target` Char (validated against allowlist §7.3),
`expires_at` (now+10 min), `used_at`, `outcome` Selection [pending, ok, denied,
expired, error]. init() unique index on state_hash. Cron purges >24 h.

### 5.4 `care.channel.readiness.check` — explicit readiness, never one boolean
`connection_id` (ondelete cascade), `check_key` Selection: `authorization_valid,
scopes_granted, resource_selected, webhook_configured, webhook_verified, outbound_ok,
inbound_ok, token_fresh, provider_approvals`, `status` [pass, fail, pending, n_a],
`detail_redacted` Char, `checked_at`. Unique (connection_id, check_key).
`state == 'ready'` is DERIVED: every check the adapter's capabilities declare as
required is `pass` (n_a allowed). **A connection is never Ready because a record
exists** — the anti-"configured≠connected" rule.

### 5.5 `care.channel.audit` — append-only ops audit
Clone of health.consent.check.log posture (unconditional write/unlink raise, no su
escape). Fields: `company_id`, `connection_id`, `user_id`, `event` Char (connect_start,
callback_ok, callback_denied, resource_selected, webhook_subscribed, test_ok/fail,
reconnect, disconnect, secret_rotated, refresh_ok/fail, health_transition),
`detail_redacted` Char, `ts`. **No secret, token fragment, URL query, or provider
payload ever enters `detail_redacted`** — write through a `_redact()` helper that
truncates + strips anything matching token/secret/key/code/signature params.

### 5.6 Message spine (from phase6, rebased)
`care.channel.identity` and `care.channel.message` exactly as care-command-phase6.md
§2.2–2.3, with `account_id` renamed `connection_id` → FK to `care.channel.connection`.
The `_ingest_inbound` funnel, conversation extension (`channel_identity_id` anchor,
`action_send_channel`, `_capabilities`, timeline merge) and the declared core touches
(extract `_apply_signal` + `_capabilities`, `_channel_keys()` override, 2 JS edits)
carry over UNCHANGED (Phase CC-B).

## 6. Adapter interface

`services/adapters.py` — registry `CHANNEL_ADAPTERS = {}` + `@register_adapter(key)`.

```python
class BaseChannelAdapter:                     # __init__(env, connection)
    # ---- declaration (drives the UI stepper + readiness set) ----
    def authorization_capabilities(self) -> dict:
        # {"mode": "oauth_popup"|"embedded_signup"|"guided_secret"|"one_click",
        #  "needs_platform_app": bool, "resource_selection": bool,
        #  "webhook_auto": bool, "supports_refresh": bool, "supports_revoke": bool,
        #  "required_checks": [check_keys...], "guide_steps": [...i18n keys]}
    # ---- authorization ----
    def begin_authorization(self, session) -> dict      # url or wizard descriptor
    def handle_callback(self, session, params) -> dict  # exchange, store, next step
    def list_resources(self) -> list[dict]              # [{id, name, kind, meta}]
    def connect_resource(self, resource_id) -> None
    # ---- plumbing ----
    def register_webhook(self) -> dict
    def verify_webhook(self, raw_body, headers) -> bool  # FAIL CLOSED (§5.61)
    def test_connection(self) -> dict                    # synthetic-only, §7.6
    def refresh_authorization(self) -> None              # under refresh lock §7.4
    def revoke_authorization(self) -> None               # best-effort provider revoke
    def health_check(self) -> dict                       # cheap; drives §8
    # ---- messaging (CC-B) ----
    def parse_inbound(self, payload) -> list[dict]
    def send_message(self, identity, text) -> dict
```

No provider is forced into OAuth: Telegram/VoIP24h declare `guided_secret`, webchat
`one_click`, email delegates to the Odoo mixins, Meta declares `embedded_signup`.
All HTTP via `requests` with explicit timeout; `api_base_override` honored for tests;
logging = event types + ids ONLY (no bodies/phones/tokens).

## 7. Security architecture (binding)

### 7.1 `services/channel_crypto.py` — dedicated secret encryption
Self-contained ~60-line clone of the phi_crypto recipe (do NOT import its private
functions; do NOT reuse the PHI subkey): same root sources (`HEALTH_PHI_KEY` env var,
fallback HKDF from `database.secret`), HKDF info **`b'health19-channel-secret-v1'`**,
AES-256-GCM, token prefix **`chs$1$`**. Difference from phi_crypto: `decrypt()`
**RAISES** on InvalidTag/garbage (a corrupted token must never be silently sent to a
provider — phi_crypto's marker-string behavior is a hazard here). `is_encrypted()`
prefix test. Key cache per-DB, `clear_key_cache()` for tests.

### 7.2 Secret handling rules
- Write path: `connection.action_set_secret(field, value)` / platform
  `action_set_secret` — server methods that encrypt+write via sudo, store
  `secret_hint = '••••' + value[-4:]`, audit `secret_rotated`, and return nothing.
  Raw secrets never live in a persisted form field; wizard fields are TransientModel,
  `store=False` semantics, never logged.
- Read path: ONLY server-side adapter code via an internal `_get_secret(field)` (sudo,
  decrypt, never returned by any @api.model the client can call). RPC surface returns
  `has_credentials` + `secret_hint` only. `fields_get`/export leak prevention: `*_enc`
  fields `groups='base.group_system'` + never in any view; tests assert a
  crm-manager `read()`/`export_data()` cannot see them (T-block).
- No `tracking=True` on secret fields, no secrets in chatter/mail, no secrets in URLs
  (Telegram path secret is a routing credential by design — random 32-byte, revocable,
  never displayed after creation), no secrets in exceptions (`UserError` texts are
  fixed strings + redacted hints).

### 7.3 OAuth engine rules
State: `secrets.token_urlsafe(32)`, stored hashed (§5.3), single-use
(`used_at` set inside the same savepoint that processes the callback), 10-min expiry,
bound to (company, user, provider, connection, redirect_target). PKCE S256 ALWAYS when
the provider supports it (Zalo: required; Google/Microsoft: on; Meta ES: n/a — code
flow via JS SDK + server exchange). Redirect targets validated against an allowlist:
`{web.base.url}` + explicit `channel_hub.allowed_redirect_hosts` param — no open
redirects. Callback controller: `type='http'`, `auth='public'`, GETs only, rejects
unknown/used/expired state with a GENERIC page (no oracle), rate-limited via
`gateway.rate.counter`. Popup completion page posts `{channel, ok}` via
`window.opener.postMessage` with targetOrigin = our own base URL and ALSO renders a
"return to Health19" link (popup-blocked / opener-gone fallback); the OWL stepper
polls connection state every 2 s while an oauth.session is pending, so a closed popup
never loses progress (resume = re-enter stepper, session recreated).

### 7.4 Token refresh locking (Zalo single-use rotation is the forcing case)
`refresh_authorization()` runs inside `SELECT … FOR UPDATE NOWAIT` on the connection
row (skip if locked — another worker is refreshing); the NEW refresh token is persisted
via a **separate cursor commit BEFORE first use** of the new access token (a crash
between rotation and persist otherwise burns the 3-month grant). Cron + on-demand
refresh share the same method. Failures increment `consecutive_failures`; refresh-token
death ⇒ `state=action_required` + tenant-admin activity (§8).

### 7.5 Webhook rules (§5.61 everywhere)
Every inbound route: `type='http'`, `auth='public'`, `csrf=False`,
`save_session=False`, raw `request.httprequest.get_data()` FIRST, verify BEFORE
`env(su=True)` escalation, generic non-oracle responses, 200-after-verification.
Verification per provider (matrix §3): Meta HMAC-SHA256 raw bytes; Zalo
`sha256(app_id + raw_body + timestamp + oa_secret)` with ±5 min timestamp window
(replay guard) — resolve the per-OA secret by parsing `oa_id` from the body, then
verify, then process; Telegram path-secret + header-secret both compare_digest;
VoIP24h per verified docs (or secret-path fallback). Missing platform app, missing
connection, missing secret ⇒ REJECT (fail closed). Dedupe: partial unique
`(connection_id, external_message_id)` (phase6 §2.3) + savepoint ingest (§5.55).
Rate counter on all public routes.

### 7.6 Test sends are synthetic ONLY
`test_connection()` never touches patient data: WhatsApp/FB/Telegram/Zalo → provider
"get me/profile" API calls (no message to a human) plus, where a human test is wanted,
a message TO THE CONNECTING ADMIN's own identity only, body fixed:
"✔ Health19 configuration test — no action needed / Kiểm tra cấu hình Health19".
Email → send to the connected mailbox itself. Webchat → demo page. Real patient
messaging keeps its existing consent gates (`check_consent`, §1.4) untouched.

## 8. Connection health

Cron `_cron_channel_health` every 30 min (staggered nextcall): due connections
(`next_health_check_at <= now`) run `adapter.health_check()` → update readiness checks
+ `health_status`; backoff on failure (30 m → 2 h → 8 h, cap; `consecutive_failures`);
provider outage ⇒ `provider_down` WITHOUT flipping `state` (transient ≠ broken).
Token expiry sweep: `token_expires_at` within 7 d ⇒ `expiring` + ONE
`mail.activity` to tenant admins ("Reconnect Zalo — expires in N days"; credentials
never in the note); within 0 ⇒ `action_required`. Permission loss (Meta 190/10 errors,
revoked grants) detected on health check or live send-failure ⇒ `permission_lost`.
`_channel_keys()` reflects ONLY `state == 'ready'` connections (+ base 4 live rails),
so the dock, composer capabilities and workspace stay honest.

## 9. UX design — Channel Connection Center

Entry: Care Command gear → "Channels" + menuitem under `menu_care_command_config`
(tenant-admin + crm-manager). One OWL client action `channel_center` (new component,
same flat-mono/hf-wt-ico/no-gradient rules; NOT a patch of CareCommand).

**Catalogue**: one card per channel key (8): provider icon, name, status chip
(Not connected / Connecting… / Action required / Expiring soon / Error / Disabled /
Connected), connected-resource line ("OA: Phòng khám Việt Úc" / "Page: …" /
"+84 90… • WABA …" / "@vietuc_bot" / "lienhe@vietuc.vn"), last inbound/outbound
relative times, ONE primary action (Connect / Continue setup / Fix / Reconnect / Open).
Channels without a platform app: chip "Not available yet", card explains "Health19 is
completing provider approval for this channel" (honest pending state).

**Stepper** (per card, 4 steps max, one primary action per screen, VI+EN, no
OAuth/scope/webhook/callback words in primary copy — "Sign in with Zalo", "Choose your
Page", "We're connecting things…", "Send a test"). Structure driven by
`authorization_capabilities()`:
1. *Sign in / Get your key* — OAuth popup button, or guided-secret screens (Telegram:
   deep-link `https://t.me/BotFather` + one-instruction-per-screen + paste field that
   masks on blur and validates via `getMe` before anything is stored, showing the
   detected bot name for confirmation; VoIP24h: direct portal link + "where to find it"
   illustration + masked paste + validate-before-save).
2. *Choose what to connect* — resource radio list (Pages, WABA phone numbers; skipped
   when the grant fixes the resource — Zalo OA, mailbox, bot).
3. *We set things up* — automatic: webhook subscribe where the API allows; where
   portal-only (Zalo webhook URL, VoIP24h), a guided checklist: official link, exact
   screen name, copy-button for our URL (visible "Copied ✓"), then an automatic
   validation probe ("Waiting for Zalo to confirm… ✓ received").
4. *Test & finish* — synthetic test (§7.6) + success page saying exactly what now
   works ("New Zalo messages will appear in Care Command") + what's still pending
   (template approvals etc. as PENDING tasks with provider links).

Connected-card secondary actions: Test, Reconnect, Change account/resource,
Disconnect (confirmation modal spells out operational impact: "New WhatsApp messages
will stop arriving in Care Command. Conversation history stays."), expandable
"Technical details" (webhook URL, subscription state, scopes — still no secrets).
Accessibility: full keyboard path, aria-labels, focus trap in modals; mobile: cards
stack, stepper full-screen. Retry safety: every action idempotent server-side (state
machine + single-use sessions + unique indexes) — double-click can never create a
second subscription or connection.

## 10. Migration & compatibility (binding)

- `zalo.config` rows: post_init creates a `care.channel.connection` per active config
  in `state='legacy'` — tokens COPIED (encrypted) but the legacy module keeps
  operating them until the tenant completes a guided "Upgrade connection" re-auth
  (PKCE). NOTHING is deleted or invalidated; `health_zalo` keeps working throughout.
  The 9-module ZNS contract (`get_api_client` + `zalo.config` search +
  `send_zns_notification`) is preserved verbatim — CC-D makes `zalo.config` a facade
  whose token fields are fed by the framework connection when one is ready, legacy
  fields otherwise.
- `voip.config` rows: same `legacy` treatment in CC-F.
- Email: existing `ir.mail_server`/`fetchmail.server` untouched; the Center creates/
  links records through the Odoo mixins rather than replacing them.
- The 4 new channels have nothing to migrate.
- Adapters are feature-flagged: no platform app row (or `active=False`) ⇒ channel
  card shows "Not available yet"; installing the module changes NOTHING visible until
  the operator seeds platform apps (except webchat/Telegram, which need none).
- Existing unrelated working-tree changes are untouched (Opus rule: only sanctioned
  files).

## 11. Phase plan (one Opus session each; handovers issued per-cycle)

| Phase | Scope | Ships visibly |
|-------|-------|---------------|
| **CC-A** | Framework core: module skeleton, channel_crypto, platform.app, connection, oauth.session, readiness, audit, health cron, generic OAuth controller, adapter registry + capability contract, security (groups/rules/ACL), settings hook, T70–T89 | Backend only (Settings menu stub) |
| **CC-B** | Message spine + 4 adapters (= old phase6 T50–T69 rebased): identity, message store, ingest funnel, conversation ext + core touches, Meta/TG/webchat webhook controllers, send paths | WhatsApp/FB/TG/webchat rails (draft until connected) |
| **CC-C** | Channel Connection Center UI: catalogue + stepper OWL app, webchat one-click enable (origins, embed snippet, live preview, verify-installation), Telegram guided wizard, connect/test/disconnect/reconnect actions, vi.po, browser evidence | Tenant-facing Center; webchat + Telegram fully self-service E2E |
| **CC-D** | Zalo/ZNS refactor: framework adapter w/ correct OAuth v4 + PKCE + rotation locking, NEW fail-closed webhook route (old `/zalo/webhook` becomes 410 shim), per-OA secret verify, zalo.config facade + legacy migration, ZNS readiness card (template approval surfaced separately from chat readiness), Z1–Z9 repairs | Zalo self-service connect; ZNS honesty |
| **CC-E** | Meta onboarding: ES v4 + FLB configs, JS SDK popup, code exchange, WABA/phone + Page selection, subscribed_apps, pending-approval task UI (business verification, display name, templates), template-message send path for WA | WhatsApp + Messenger self-service (software-complete; live pending Meta approvals) |
| **CC-F** | Email OAuth (wrap google_gmail/microsoft_outlook into the stepper, mailbox confirm, outbound+inbound validated separately, SMTP/IMAP guided fallback) + VoIP24h guided wizard (AFTER doc verification from VN IP; endpoint reconciliation sanctioned) + health monitoring polish + admin notifications + docs | Email + Calls self-service; monitoring complete |

Test numbering: CC-A T70–T89, CC-B keeps T50–T69, CC-C T90+, then continue.

## 12. One-time platform-operator checklist (external approvals — NOT software)

| # | Action | Where / prereq | Blocking for |
|---|--------|-------------|--------------|
| 1 | Meta Business-type app + business portfolio; Business Verification | developers.facebook.com | WA/FB beyond 10-customer trickle |
| 2 | App Review: `whatsapp_business_management`, `whatsapp_business_messaging`, `pages_messaging`, `pages_manage_metadata`, `pages_show_list` (screencasts) | Meta dashboard | WA/FB live traffic |
| 3 | Two FLB configurations (ES v4 for WA; login config for FB) → config_ids into `channel.platform.app.extra_json` | Meta dashboard | CC-E |
| 4 | App-level webhook URLs + verify tokens (WA + Messenger products) | Meta dashboard | CC-E |
| 5 | Zalo app @ developers.zalo.me, OA API product, register callback URL + webhook URL, app review to Live | developers.zalo.me | CC-D |
| 6 | Google Cloud OAuth client, consent screen publish, brand verification, **restricted-scope verification + CASA** (4–12 weeks; budget lab fee) — or decision to ship gmail.send-only later | console.cloud.google.com | CC-F Gmail |
| 7 | Entra multi-tenant app registration + publisher verification (MPN) | entra.microsoft.com | CC-F M365 |
| 8 | Fetch docs-sdk.voip24h.vn from VN IP; reconcile endpoints; confirm webhook signature scheme with VoIP24h | UAT server | CC-F VoIP |
| 9 | Set `HEALTH_PHI_KEY` on every environment if not already (channel_crypto shares the root) | server env | CC-A |

## 13. Limitations (verified, declared)

- Zalo webhook URL is per-APP and portal-only — tenants share one endpoint; routing by
  `oa_id`. Zalo refresh-token loss (3-mo idle or rotation crash) ⇒ tenant must re-auth.
- ZNS template approval is a human Zalo review (2–3 d) and needs a funded ZCA + verified
  OA — surfaced as pending tasks, never automatable.
- Telegram bots cannot be created programmatically — guided BotFather wizard is the
  ceiling; a "manager bot" that creates bots does not exist in the official API.
- Messenger: no per-page webhook override; outside-24 h messaging now effectively
  HUMAN_AGENT (7 d) or Messenger utility templates.
- Meta unverified-business cap: 10 tenant onboardings / 7 days until verification.
- Gmail full IMAP/SMTP needs restricted-scope + CASA; until then Gmail card is
  "Not available yet" (M365 + SMTP/IMAP fallback are unaffected).
- Microsoft tenants can require admin consent; surfaced as a pending task with the
  admin-consent URL.
- VoIP24h: credential issuance is support-assisted; webhook signature scheme unverified
  until §12.8 — treated as guided + unsigned-with-path-secret until proven better.
- Instagram messaging is a separable Meta permission set — explicitly OUT of scope;
  would be a new channel key + approved extension.
- Webchat floods land as triageable conversations (rate-limited, capped) — declared
  residual risk (phase6 §6 stands).

## 14. Rollout & rollback

Install order CC-A→CC-F on vietuat, each phase reviewed before the next (methodology).
Module is NOT auto_install; installing changes nothing until platform apps are seeded.
Rollback per phase = uninstall module (connections/audit dropped — acceptable pre-GA;
legacy zalo/voip configs untouched by design), or `active=False` on platform app rows
to feature-flag a provider off instantly. The old `/zalo/webhook` shim keeps answering
410 after CC-D so Zalo retries die fast; re-enabling legacy = reinstalling health_zalo
route (documented in CC-D).

## 15. Honest readiness statement (design-time)

| Channel | After software complete | External gate remaining |
|---------|------------------------|-------------------------|
| Web Chat | Ready end-to-end | none |
| Telegram | Ready end-to-end | none (tenant creates bot) |
| Zalo chat | Ready | tenant OA verification; platform app review |
| ZNS | Send path ready | ZCA funding + per-template human approval |
| WhatsApp | Ready | Meta business verification, app review, display name, tenant payment method |
| Messenger | Ready | Meta app review |
| Email (M365) | Ready | publisher verification; some tenants' admin consent |
| Email (Gmail) | Ready (code) | restricted-scope verification + CASA |
| Calls (VoIP24h) | Guided wizard ready | VN-IP doc verification; provider credential issuance per tenant |
