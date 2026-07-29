# CC-G — Platform Go-Live Console: truthful availability + operator preflight

**Read with:** `docs/strategy/HANDOVER-CONVENTIONS.md` (binding: §5.3 pre-check-before-super,
§5.4 unconditional guards / no uid-1 tests, §5.61 fail-closed webhooks, §5.65
persist-before-raise, §5.75 `--workers=0`, §29/§5.58 vi.po markers) and
`docs/strategy/handovers/channel-center-architecture.md` (§4 two credential planes,
§12 operator checklist).

**Module:** `health_care_command_channels` → version **19.0.7.0.0**. No migration script
(only new stored columns + non-stored computes).

---

## 1. Why this phase exists

The four "Not available yet" cards (Zalo, Email, WhatsApp, Messenger) are **software-complete**
(CC-D/E/F). They are dark because zero `channel.platform.app` rows exist — and creating those
rows is external paperwork (architecture §12, "NOT software"). CC-G is the software that remains:

1. **The availability gate is too loose.** `_center_platform_available`
   ([channel_center.py:468-484](../../../addons/health_care_command_channels/models/channel_center.py))
   flips a card to available when *any active row exists* for the provider — even one with no
   client id, no secret, no config ids. The moment the operator creates an empty `meta` row to
   start filling it in, WhatsApp + Messenger light up and every Connect can only fail. Email
   already knows better: `EmailAdapter.available_providers()`
   ([adapters.py:2015-2031](../../../addons/health_care_command_channels/services/adapters.py))
   demands addon + client id + secret — but the *card* gate doesn't ask it.
2. **The operator has no in-product go-live surface.** Checklist §12 is markdown. The values it
   needs (redirect URI, webhook URLs, verify token, which extra_json keys) are scattered; a wrong
   paste surfaces days later as a tenant-side failure.
3. **Nothing proves pasted credentials.** For Meta there IS a harmless, documented server-side
   check (app access token). For Zalo/Google/Microsoft there is not — and per the module's own
   ethos we say so instead of pretending.

Scope in one line: **when a card says "Connect", Connect can actually reach the provider's own
screens; and the operator can see exactly what is missing until then.**

## 2. Verified plumbing (do not re-derive)

- Card gate: `_center_platform_available(caps)` — [channel_center.py:468](../../../addons/health_care_command_channels/models/channel_center.py#L468);
  call sites at **:515 (center_overview), :703 (center_begin), :872, :964** (grep before edit —
  the last two are per-channel begin endpoints with `conn` in scope).
- `center_overview` builds a **NewId probe** `self.sudo().new({'channel': …, 'company_id': …})`
  and calls `probe._capabilities()` (:507-512) — so adapters already instantiate fine on probes.
  `_get_adapter` = [care_channel_connection.py:361](../../../addons/health_care_command_channels/models/care_channel_connection.py#L361)
  → `get_adapter(env, connection)` ([adapters.py:314-325](../../../addons/health_care_command_channels/services/adapters.py#L314));
  it also accepts a **bare channel-key string** (`key = getattr(connection, 'channel', None) or connection`).
- Capability key validation: required keys tuple at [adapters.py:293](../../../addons/health_care_command_channels/services/adapters.py#L293),
  `OPTIONAL_CAPABILITY_KEYS = ('parent_channel', 'platform_providers')` at :302. New optional
  keys must be added there or the validator refuses.
- Platform-app needs per channel (all verified):
  - **WhatsApp**: `client_id` + secret + `extra_json.es_config_id` (`META_ES_CONFIG_KEY`,
    adapters.py:62; read via `config_id()` :544-553 which **refuses when absent**).
  - **Messenger**: `client_id` + secret + `extra_json.flb_config_id` (:63, :1273-1278).
  - **Both Meta channels**: `extra_json.verify_token` (`VERIFY_TOKEN_KEY`,
    [webhook_verify.py:29](../../../addons/health_care_command_channels/services/webhook_verify.py#L29)) —
    without it `meta_challenge` 403s the dashboard handshake
    ([meta.py:44-65](../../../addons/health_care_command_channels/controllers/meta.py#L44)), so
    `webhook_verified` can never pass.
  - **Zalo**: `client_id` + secret (`_platform_app` adapters.py:1543-1552).
  - **Email**: delegate to `available_providers()` (addon installed + client id + secret,
    adapters.py:2015-2037). `EMAIL_PLATFORM_PARAMS` mirror keys at :120-121.
- Routes for computed display values: OAuth callback `/channel_hub/oauth/callback/<provider>`
  ([oauth.py:46](../../../addons/health_care_command_channels/controllers/oauth.py#L46)); Zalo
  webhook `/care_channels/zalo/webhook` ([zalo.py:65](../../../addons/health_care_command_channels/controllers/zalo.py#L65));
  Meta webhooks `/care_channels/meta/whatsapp/webhook` + `/care_channels/meta/fb/webhook`
  ([meta.py:44](../../../addons/health_care_command_channels/controllers/meta.py#L44)); Email has
  none (IMAP poll). Base URL: `web.base.url` (see the telegram precedent, channel_center.py:799).
- Graph constants: `GRAPH_BASE = 'https://graph.facebook.com'`, `GRAPH_VERSION = 'v21.0'`
  (adapters.py:50-51). Reuse them — do not hardcode a version.
- `channel.platform.app`: model + secret wizard in
  [channel_platform_app.py](../../../addons/health_care_command_channels/models/channel_platform_app.py)
  (`get_extra` :124, `_get_for_provider` :174, `action_set_secret` :135 — the audit-log idiom to
  clone is at :155-157). Form view `view_channel_platform_app_form` in
  [platform_app_views.xml:53-89](../../../addons/health_care_command_channels/views/platform_app_views.xml#L53).
  ACL is **base.group_system only, 1/1/1/1** (ir.model.access.csv:2) — every new field/button
  inherits that; keep it so.
- **No `tracking=True` on ANY field of this model, ever** (Z1: tracked secrets copy into
  `mail.tracking.value`). This applies to all new CC-G fields too.
- Card copy for unavailable channels lives in
  [channel_center.xml:49-51](../../../addons/health_care_command_channels/static/src/center/channel_center.xml#L49)
  ("Health19 is completing provider approval…") — **unchanged this phase**; it stays accurate
  for the not-yet-configured case and lights up automatically once the gate passes.
- Highest test id in the module today: **T155**. CC-G starts at **T156**.

## 3. Scope

### G1 — Truthful availability (`platform_ready`)

New adapter method, model gate rewired to it.

- `BaseChannelAdapter.platform_ready()` (adapters.py, near `authorization_capabilities`):
  - `not caps['needs_platform_app']` → `True`.
  - Else, for **any** provider in `platform_providers`:
    `app = channel.platform.app.sudo()._get_for_provider(provider)`; ready iff
    `app and app.client_id and app.client_secret_enc and all(app.get_extra(k) for k in required_platform_keys)`.
  - **Binding: `platform_ready` must never read `self.connection`** — it is called with NewId
    probes and (from the model gate) possibly a bare channel string.
- New **optional** capability `required_platform_keys` (tuple of extra_json keys); add the name
  to `OPTIONAL_CAPABILITY_KEYS` (:302) and to whatever validator enforces the key set.
  Declare: `WhatsAppAdapter: ('es_config_id', 'verify_token')`,
  `MessengerAdapter: ('flb_config_id', 'verify_token')`. Zalo/ZNS declare none (client id +
  secret suffice). ZNS keeps `platform_providers: ['zalo']` so its sub-card mirrors Zalo.
- `EmailAdapter.platform_ready()` override → `bool(self.available_providers())`.
- Model gate: `_center_platform_available(caps, channel)` — keep the fast path
  `not caps.get('needs_platform_app') → True`, then
  `get_adapter(self.env, channel).platform_ready()` inside `try/except ValueError → False`.
  Update **all four call sites** (channel key is in scope at each; grep to confirm none missed).
  `center_begin`'s refusal (:703-707) then automatically becomes completeness-aware.

### G2 — Go-Live tab on the platform-app form

All on `channel.platform.app`; operator-only by the existing ACL.

- Non-stored computed fields (readonly, `compute=`, no `store`):
  - `oauth_redirect_uri` Char — `{base}/channel_hub/oauth/callback/{provider}`.
  - `webhook_urls` Text — provider-dependent: zalo → the one Zalo path; meta → both Meta paths;
    google/microsoft → an honest "No webhook — mail arrives by IMAP poll." line.
  - `go_live_checklist` Html — one row per requirement with a plain pass/todo mark (mono colors,
    no emoji, no font-awesome): client id present · secret stored · each `required_platform_keys`
    entry present (union over the provider's channels) · for google/microsoft: Odoo addon
    installed (model-presence test, clone adapters.py:2033-2037). Below the live rows, the
    provider's **external** §12 steps as static text with links
    (developers.facebook.com / developers.zalo.me / console.cloud.google.com /
    entra.microsoft.com) marked plainly as "done outside Health19".
- Button `action_generate_verify_token` (visible only for `provider == 'meta'`): if
  `verify_token` absent from `extra_json`, **merge** it in (`secrets.token_urlsafe(24)`,
  json-load → update → dump — never clobber sibling keys); if present, raise `UserError`
  telling the operator to clear it first (Meta's dashboard still holds the old one). Audit-log
  the event (clone the `action_set_secret` idiom).
- New notebook page "Go live" on `view_channel_platform_app_form` carrying these fields +
  the preflight fields/button from G3.

### G3 — Preflight ("Check this application")

Stored fields on `channel.platform.app` (plain columns, **no tracking**):
`preflight_status` Selection `[('none','Not checked'),('pass','Passed'),('fail','Failed'),('unverifiable','Proven on first sign-in')]`
default `'none'`; `preflight_at` Datetime; `preflight_detail` Char (redacted, never a secret).

Button `action_preflight`, dispatch on provider:

- **meta** (real check — same Graph surface CC-E already speaks):
  1. `GET {GRAPH_BASE}/{GRAPH_VERSION}/oauth/access_token?client_id=…&client_secret=…&grant_type=client_credentials`
     (timeout 10s, follow the module's existing requests/timeout/redact idioms).
  2. On 200: `GET {GRAPH_BASE}/{GRAPH_VERSION}/{client_id}?fields=name` with the returned app
     token → `preflight_status='pass'`, `preflight_detail=<app name>`.
  3. Any refusal/timeout → `'fail'` with `redact()`-ed detail. **Persist first, notify after**
     (§5.65) — the button never raises on a provider failure; it returns a
     `display_notification` either way.
  4. The app access token is used and discarded — never stored, never logged.
- **zalo / google / microsoft**: NO network call. Set `'unverifiable'` with the honest sentence
  "No harmless server-side check exists for this provider — the credentials are proven on the
  first real sign-in." We do not build on undocumented tricks (e.g. token-endpoint
  `invalid_client` discrimination is not a contract).
- Audit-log every preflight (event `'preflight'`, provider + outcome, no detail beyond that).
- Preflight is **manual only** — no cron (§5.81 lesson: shipped crons run).

### G4 — Bookkeeping

- vi.po entries for every new user-visible string, following the §29/§5.58 marker convention
  already used in this module's `i18n/vi.po`.
- Manifest 19.0.7.0.0. Update the architecture doc §11 phase table with a CC-G row on ship.

## 4. Non-goals (binding)

- **No provider-approval automation** — §12 items 1-8 stay human paperwork; CC-G only shows them.
- **No tenant-visible change** beyond cards lighting up when truly ready; the unavailable-card
  copy in channel_center.xml is untouched.
- **No new OAuth engine, no mixin patches, no webhook changes, no VoIP/Calls/Telegram/Webchat
  edits, no ZNS attestation** (architecture §13 stands: template approval has no honest button).
- **Preflight never becomes a readiness check** on `care.channel.connection` — it is Plane-1
  operator tooling; `_recompute_ready` and the check vocabulary are untouched.
- **`_center_platform_available` semantics may only tighten** (available ⇒ was available
  before); nothing that is available today with a *complete* app row may go dark.

## 5. Safety rails

- Everything on `channel.platform.app` stays `base.group_system` (existing ACL); no new ACL
  rows, no groups relaxation, and `center_overview` must keep working for the **tenant persona**
  (Care Command manager, NOT uid 1 — §5.4): the gate path runs entirely under `sudo()` reads.
- No secret in any compute, checklist row, preflight detail, notification, audit row, or log
  line. T97's dump-the-payload assertion pattern is the proof idiom — reuse it (T161).
- JSON merge for `extra_json` writes goes through load→update→dump with the existing
  `_validate_extra_json` still enforced (it runs in `write`, channel_platform_app.py:111-113).
- `platform_ready` failures are availability answers, not exceptions: a broken adapter
  registration (`ValueError`) renders "Not available yet", never a traceback.

## 6. Tests (T156+, `tests/test_platform_go_live.py`, TransactionCase unless noted)

- **T156** — active but EMPTY `meta` row: whatsapp + fb cards `available=False`;
  `center_begin('whatsapp')` raises "not available yet".
- **T157** — meta row + client_id + secret + `verify_token`: whatsapp still unavailable (no
  `es_config_id`); add `es_config_id` → whatsapp available, fb STILL unavailable; add
  `flb_config_id` → fb available.
- **T158** — complete zalo row: zalo card available, `primary_action='connect'` on a fresh
  company; zns card mirrors availability but `center_begin('zns')` still refuses with the
  parent-channel message.
- **T159** — email availability equals `bool(EmailAdapter.available_providers())` in the same
  env (empty rows → False; complete google row → matches the addon-presence truth).
- **T160** — non-platform channels unaffected: telegram/webchat/call cards keep
  `available=True` with zero platform apps.
- **T161** — `json.dumps(center_overview())` + a read of the go-live form fields as system user
  contain neither seeded secret plaintext nor ciphertext (extend the T97 idiom to
  `preflight_detail` + `go_live_checklist`).
- **T162** — verify-token generator: absent → merged in, sibling extra_json keys preserved,
  audit row written; present → `UserError`, value unchanged.
- **T163** — meta preflight pass (mock both HTTP calls, §5.76 plain-function patches): status
  `pass`, detail = app name, `preflight_at` set, audit row; no secret anywhere in the mock-call
  URLs' *stored* traces (detail/audit).
- **T164** — meta preflight refusal (mock 400): status `fail` **persisted**, redacted detail,
  button returns a notification and does not raise.
- **T165** — zalo/google/microsoft preflight: `unverifiable`, and the HTTP layer was never
  called (assert the mock has zero calls).
- **T166** — computed `oauth_redirect_uri` / `webhook_urls` equal the literal route strings
  above with `web.base.url` prefixed.
- **T167** — spoof test: a Care-Command-manager (non-system) user gets `AccessError` on
  `channel.platform.app` read AND on both new buttons (RPC-by-name, the T107/T120/T138
  precedent).
- **T168** — `center_overview()` as the tenant persona with a complete zalo row: no
  `AccessError`, zalo available (proves the gate's sudo reads survive a real non-system caller).

Run: `--workers=0` (§5.75). No HttpCase needed this phase.

## 7. Deploy / verify (vietuat)

1. Standard deploy (scp → /tmp → sudo cp with odoo ownership), `-u health_care_command_channels`,
   restart. **No concurrent odoo-bin during the upgrade** (§5.45).
2. `SELECT count(*) FROM channel_platform_app;` — expected 0 today. Cards must render EXACTLY as
   before (all four still "Not available yet") — CC-G with zero rows is a strict no-op
   tenant-side. Screenshot the Center to prove it.
3. Create a deliberately empty `zalo` row in the UI → the Zalo card must STAY "Not available
   yet" (this is the behavior change). Open the Go-live tab → checklist shows todo rows +
   correct computed URLs. Delete/archive the row afterwards.
4. Report the go-live tab screenshot for one meta row (test values, then archive).

## 8. Report back

- Confirmation that all four `_center_platform_available` call sites were rewired (grep output).
- Which validator enforces the capability key set, and the diff line adding
  `required_platform_keys`.
- The exact requests idiom reused for the Meta preflight (helper + timeout).
- Test tally (expect 0 failed of ~13 new + full module suite re-run), plus step 2-3 screenshots.
- Anything where the handover's file:line drifted from reality.

---

**Kickoff line for the Opus session:**

> Implement CC-G per `docs/strategy/handovers/channel-center-phaseG.md` in
> `addons/health_care_command_channels` (branch 19.0): truthful platform availability
> (`platform_ready` + `required_platform_keys`), the Go-live tab + verify-token generator +
> preflight on `channel.platform.app`, tests T156–T168, version 19.0.7.0.0. Read
> `docs/strategy/HANDOVER-CONVENTIONS.md` first; §5.4, §5.61, §5.65, §5.75 and the no-tracking
> rule on platform-app fields are binding. Deploy to vietuat per §7 and report back per §8.
