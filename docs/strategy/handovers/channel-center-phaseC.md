# Channel Center — Phase CC-C Handover: The Connection Center UI

**For:** Opus implementation session (AFTER CC-B review fixes landed) ·
**Designed/reviewed by:** Fable (2026-07-25)
**Read first, in order:**
1. `docs/strategy/HANDOVER-CONVENTIONS.md` — §5.42 (group-gated arch asserts),
   §5.58 (vi.po markers), §5.62 (fixture visibility), §5.63 (REPEATABLE READ),
   §5.64–§5.66 (CC-B's: escaped-markup/doctype/asset-cache, UserError rolls
   back its own evidence, derived-readiness lockout).
2. `docs/strategy/handovers/channel-center-architecture.md` §9 (the UX spec —
   BINDING: catalogue cards, 4-step stepper, copy rules), §5.4, §6, §8, §10.
3. `docs/strategy/reports/channel-center-phaseA-report.md` +
   `channel-center-phaseB-report.md` — what actually exists (guard semantics,
   `_internal()`, readiness upsert, ingest funnel, webchat routes).

**Modules touched:** `health_care_command_channels` → 19.0.3.0.0 ONLY. Zero
edits to `health_care_command` (the dock/composer already honour
`_channel_keys()` and `ext_reply_channel`). Zero edits to health_zalo/voip/PWA.

## 1. Scope

The tenant-facing **Channel Connection Center**: one OWL client action
(catalogue of 8 channel cards + per-channel stepper), the server endpoints that
drive it, the tenant-admin ACL row deferred since CC-A, and TWO channels made
fully self-service end-to-end: **webchat** (one-click enable + embed snippet +
verify-installation) and **Telegram** (guided BotFather wizard: paste → getMe
validate → setWebhook → reply test). WhatsApp/FB/Zalo/ZNS/email/call cards
render honestly (state + "Not available yet" / "Connect" disabled with the
honest pending copy) but their steppers ship as structure only — their
begin/callback flows are CC-D/E/F.

## 2. Verified plumbing (do not re-derive; §5.59 — re-verify line numbers only)

All in `addons/health_care_command_channels/` unless noted:

- `models/care_channel_connection.py`: TRANSITIONS :64-83,
  RECOMPUTE_STATES :87 (`{'testing','ready','action_required','expiring'}`),
  SENDABLE_STATES :92, INGESTABLE_STATES :97 (= SENDABLE ∪
  {testing, configuring}), USER_WRITABLE :129 (`{'active',
  'message_main_attachment_id'}`), `_check_guarded_vals` :267 area,
  `_transition` :314 (single writer, audits), `_get_adapter` :341,
  `_required_checks` :349, `_recompute_ready` :360-377, `action_set_secret`
  :418 (the ONLY tenant secret writer; audits `secret_rotated`), `_get_secret`
  :444 (server-only), `get_setting` :455, `set_settings` :467 (refuses
  credential-shaped keys), `_find_sendable` :493, `_may_ingest` :524,
  `_note_inbound` :543 (writes `webhook_state='verified'` :552).
- `models/care_channel_readiness_check.py`: `upsert_check` :62-86 (redacts
  detail, calls `_recompute_ready`).
- `models/care_conversation_ext.py`: `_channel_keys` company-gated :175-190 —
  a connection reaching `ready` lights the dock with NO further work.
- `services/adapters.py`: registry :73, `get_adapter` :108,
  `authorization_capabilities()` contract (CAPABILITY_KEYS :93-96);
  TelegramAdapter :455-534 (`guided_secret`, `webhook_auto=True`,
  required = authorization_valid, resource_selected, webhook_configured,
  outbound_ok; `send_message` :517 uses `provider_secret` + api_base_override);
  WebChatAdapter :578-624 (`one_click`, required = resource_selected,
  inbound_ok; `send_message` = row-is-delivery).
- `controllers/webchat.py`: public routes :107-160, demo page :162-198
  (embed snippet + `?v=` stamp precedent — REUSE its `_widget_version()` and
  snippet construction, do not re-invent).
- `views/menus.xml`: existing backend menus under
  `health_care_command.menu_care_command_config` (manager-gated).
- Tenant-admin group exists: `health_user_admin.group_health_user_admin`
  (addons/health_user_admin/security/security.xml:4).
- UI rules: mono flat colors, `hf-wt-ico` CSS-mask SVG icons (never emoji/FA),
  VI+EN with no OAuth/scope/webhook/callback words in primary copy.

## 3. Amendment F1 (framework, binding): §5.66 lockout fix

`_recompute_ready` currently demotes a `testing` connection to
`action_required` the moment ANY check is upserted while other REQUIRED checks
are merely *missing* — and `action_required` is not ingestable, so the first
proving inbound can lock a channel out of the traffic that would finish
proving it (ledger §5.66). Change the derivation:

- `failed = [k for k in required if statuses.get(k) == 'fail']` → any `failed`
  ⇒ `action_required` (unchanged, from every RECOMPUTE state).
- All required pass ⇒ `ready` (unchanged).
- Otherwise (some required merely missing/n_a): from `testing` STAY in
  `testing` (no transition — still ingestable, still not sendable); from
  `ready`/`expiring` keep the current demotion (a required check cannot
  "go missing" there except by deletion, which should demote).

Test **T96** stages exactly the §5.66 sequence: webchat connection in
`testing` with only `resource_selected=pass`; simulate first inbound
(`_note_inbound` → webhook_verified/inbound_ok upserts) and assert state
becomes `ready`, never `action_required`; then a `fail` upsert on a required
key from `testing` still demotes. Update the §5.66 ledger entry afterwards:
append "RESOLVED CC-C: testing no longer demotes on missing checks."

## 4. Server endpoints for the Center (all on `care.channel.connection`)

New file `models/channel_center.py` (an `_inherit` extension keeps the state
machine file readable). ALL endpoints: `@api.model` or recordset methods
callable via RPC by the two UI groups (see §6), every write through
`sudo()._internal()` server-side, NEVER a secret in any return value, every
provider HTTP mocked in tests, every failure → `UserError(redact(...))` with
evidence written via the CC-B `_persist_send_failure`/`_note_*` idioms.

1. `center_overview()` (`@api.model`) → list of 8 card dicts for
   `self.env.company`: `{channel, label, state, state_chip, resource_line,
   last_inbound_at, last_outbound_at, health_status, primary_action, available,
   checks: [{key, label, status}], mode, guide_steps}`. `available` =
   adapter's `needs_platform_app` ⇒ an active `channel.platform.app` row for
   the provider exists, else True. NO token/secret/hint fields — assert in
   T97 that `json.dumps(center_overview())` contains none of the seeded secret
   values. One connection per (channel, company): pick the newest active
   non-disabled row; `zns` renders as a sub-card of zalo (`parent_channel`
   capability) and shares its connection.
2. `center_begin(channel)` (`@api.model`) → get-or-create the company's
   connection row in `not_connected`, `_transition('authorizing'…)` per mode,
   return `{connection_id, mode, guide_steps}`. For modes this phase doesn't
   implement (oauth_popup/embedded_signup) raise
   `UserError(_('This channel is not available yet.'))`.
3. Telegram wizard:
   - `center_telegram_validate(conn_id, token)` — server-side `getMe` (mocked
     in tests; `requests.get`, HTTP_TIMEOUT, api_base_override honoured).
     Valid ⇒ `action_set_secret('provider_secret', token)`, write
     `resource_external_id = str(bot id)`, `resource_label = '@'+username`,
     upsert `authorization_valid=pass`, `resource_selected=pass`, transition
     → `configuring`, return `{bot_name, bot_username}` (never the token).
     Invalid/HTTP error ⇒ UserError with redacted reason; nothing stored —
     assert the failed path stores NOTHING (no secret, no state move).
   - `center_telegram_register_webhook(conn_id)` — mint
     `webhook_path_secret` (secrets.token_urlsafe(32)) if unset, call
     `setWebhook` with `url = <base>/care_channels/telegram/webhook/<secret>`
     + `secret_token=<same>` + `allowed_updates=["message"]` (mocked), on ok
     ⇒ `webhook_state='configured'`, upsert `webhook_configured=pass`,
     transition → `testing`. The base URL comes from `web.base.url`; refuse
     with a clear UserError if it is not https (mixed-content trap noted in
     the CC-B report; do NOT silently register an http URL with Telegram —
     Telegram would refuse or worse, downgrade).
   - Step 4 copy (BINDING, Telegram cannot receive bot-initiated first
     contact): "Open Telegram, find @<bot> and send it any message — we'll
     answer here." The first real inbound proves the webhook; the Center's
     `center_test(conn_id)` then replies to that chat (newest
     `care.channel.identity` for the connection) with the synthetic body
     `_('Health19 connection test — please ignore.')` (§7.6: NEVER patient
     data), proving `outbound_ok` → `_recompute_ready` → `ready`. No identity
     yet ⇒ UserError telling the tenant to message the bot first.
4. Webchat one-click:
   - `center_webchat_enable(conn_id, origins)` — validate each origin
     (scheme+host, https-or-localhost, no path/query — reject otherwise),
     `set_settings({'allowed_origins': [...], 'greeting': …})`, write
     `resource_external_id='default'`, upsert `resource_selected=pass`,
     transition → `testing`, return the embed snippet string + demo URL
     (reuse the controller's `_widget_version()`; keep the `?v=` stamp).
   - Verify-installation = the §5.66-fixed flow: the card shows "Waiting for
     the first message…" until a real widget message arrives (inbound_ok →
     ready). `center_overview` already carries the checks, so the UI polls
     overview — no new endpoint.
5. `center_test(conn_id)` — synthetic send per channel (TG above; webchat ⇒
   posts an outgoing row the widget will poll, proving outbound trivially —
   but webchat's required set does not include outbound_ok, so this is a
   nicety, not a gate).
6. **Sanctioned CC-B touch-up (review LOW-3):** switch the widget poll from
   GET-with-query to POST with `{session, after_id}` in the body
   (`controllers/webchat.py:146-160` + `static/src/webchat/widget.js` poll
   call) so the session token stops landing in proxy access logs; same
   response shape, same rate keys. Covered by extending T59's assertions.
7. `center_disconnect(conn_id)` / `center_reconnect(conn_id)` — transition to
   `disabled` / back to `authorizing` (table already allows both), audit; the
   confirmation copy lives client-side per §9 ("New X messages will stop
   arriving in Care Command. Conversation history stays."). Disconnect NEVER
   unlinks and NEVER wipes `*_enc` columns (re-enable must not re-prompt for
   the bot token; rotation is `action_set_secret`'s job).

## 5. The OWL app

New `static/src/center/` (component + xml + css, listed in the manifest's
`web.assets_backend`): `ChannelCenter` client action, tag `channel_center`,
registered via a new `ir.actions.client` + menuitem "Channel Center" under
`health_care_command.menu_care_command_config`, sequence 10 (above the CC-A
raw-model menus), groups = tenant-admin + crm-manager (§6). NOT a patch of the
CareCommand component; same flat-mono/hf-wt-ico rules; VI+EN via standard
`_t`/xml `t-esc` of translated server labels (server sends translated
`state_chip`/`checks[].label` — keep channel labels server-side so vi.po covers
them once).

Catalogue = the §9 card spec; stepper = a modal (chatter-free, focus-trapped)
whose steps come from `guide_steps` + `mode`. Implement fully for
`guided_secret` (Telegram) and `one_click` (webchat); for other modes the
primary button renders the honest pending copy from §9 ("Health19 is
completing provider approval for this channel") when `available` is False, or
"Available in an upcoming update" when the mode is unimplemented. Token paste
field: `type="password"`-style masking, value zeroed from component state
after the validate RPC returns, never logged, never stored client-side.
Embed-snippet screen: read-only `<textarea>` + Copy button with visible
"Copied ✓" (clipboard API with execCommand fallback). Every stepper action
disables its button while the RPC is in flight (double-click safety on top of
the server idempotency).

## 6. Tenant-admin ACL (deferred from CC-A — lands NOW)

`security/ir.model.access.csv` additions for
`health_user_admin.group_health_user_admin`: connection R/W/C (no unlink),
readiness.check R, audit R, platform.app NOTHING (plane-1 stays
base.group_system), identity/message R (the Center shows last-traffic lines;
messages remain behind the record rules' company scope). Extend the CC-A
company record rules' group lists to include the tenant-admin group. The
`_check_guarded_vals` USER_WRITABLE gate already makes raw R/W safe (state/
credential/resource writes are refused outside `_internal()`); T98 asserts a
tenant-admin CAN run the webchat/telegram happy path via the center_* RPCs and
CANNOT `write({'state': 'ready'})` directly (clone the CC-A T75 spoof assert
with the new group).

## 7. Binding NON-goals

No OAuth popup/code exchange (CC-D/E), no Meta JS SDK, no Zalo repair, no
email/voip wizard, no platform-app UI beyond CC-A's backend form, no PWA, no
websocket/bus (overview refresh = poll on an interval while the tab is
visible, 15s, stop when hidden), no new public routes, no changes to the CC-B
webhook controllers or ingest funnel beyond Amendment F1, no real provider
calls anywhere in tests, no real credentials on vietuat.

## 8. Tests (T96–T105, TransactionCase, all HTTP mocked)

- T96 §3 lockout fix (the §5.66 sequence + fail-still-demotes).
- T97 center_overview: 8 cards, no secret material in the JSON dump, honest
  `available` flags (no platform app ⇒ whatsapp/fb/zalo/zns/email unavailable),
  company isolation (company B admin sees B's states only).
- T98 ACL: tenant-admin happy path + direct-write refusal + platform.app
  denied (expect AccessError), audit read-only.
- T99 telegram validate: mocked getMe ok ⇒ secret stored encrypted (column
  value starts `chs$1$`, plaintext nowhere), checks pass, state configuring,
  return has no token; mocked 401 ⇒ UserError, NOTHING stored, state
  unchanged.
- T100 telegram webhook registration: mocked setWebhook ⇒ path secret minted
  once (idempotent re-call keeps it), webhook_configured pass, state testing;
  http base ⇒ UserError, no call made.
- T101 telegram full flow to ready: validate → register → simulated inbound
  update (controller-level with header secret) → center_test reply (mocked
  sendMessage) → state ready, dock `_channel_keys()` gains 'telegram'.
- T102 webchat enable: origin validation (rejects `javascript:`, bare hosts,
  http non-localhost, with-path), settings stored, snippet returned with
  `?v=` stamp, state testing; first `_webchat_ingest` message ⇒ ready.
- T103 disconnect/reconnect: ready → disabled (dock loses the key, ingest
  drops with `webhook_ignored`, send raises the composer UserError) →
  reconnect → re-proves to ready WITHOUT re-entering the token.
- T104 center_begin idempotency: two calls, one connection row.
- T105 vi.po: every new user-facing string has a vi translation with the §5.58
  markers; spot-assert two Center strings via `with context(lang='vi_VN')`.

## 9. Deploy + evidence

- Deploy per the standard scp/cp flow; ONE run:
  `-u health_care_command_channels` with
  `--test-tags /health_care_command_channels,/health_care_command --no-http`
  → expect CC-A 20 + CC-B 26 (incl. T95) + CC-C ~10 + core 46, 0 failed,
  fresh TODAY-UTC lines.
- Browser evidence (chrome-devtools MCP on care.biztinct.com — ASK the user
  for a login FIRST; if none is provided, STOP and report, do not fabricate):
  Center catalogue (8 cards, honest chips), webchat E2E (enable → embed → demo
  page message → card flips Connected → dock icon lights → reply from
  composer), telegram stepper screens through webhook registration with a
  MOCK api_base pointed at a local stub — never a real bot on vietuat.
  Fixtures cleaned fresh-cursor afterwards (§5.34), counts reported.
- Report: deviations, data honesty (0 real connections afterwards unless the
  user opts to keep webchat enabled — ASK in the report), new gotchas.

**Kickoff line for the Opus session:**
Implement `docs/strategy/handovers/channel-center-phaseC.md` (Channel Center
Phase CC-C — the Connection Center UI: OWL catalogue + stepper, center_*
endpoints, §5.66 recompute fix F1, tenant-admin ACL, webchat + Telegram fully
self-service E2E, T96–T105). Read HANDOVER-CONVENTIONS.md (§5.42/§5.58/
§5.62–§5.66), architecture §9, and the CC-A/CC-B reports first. Only
sanctioned files; all HTTP mocked; deploy + browser evidence per §9; report
deviations and data honesty.
