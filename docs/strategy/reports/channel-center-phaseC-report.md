# Channel Center CC-C — Implementation Report

**Phase:** Channel Connection Center, Phase CC-C (the Center UI + self-service
web chat and Telegram)
**Handover:** `docs/strategy/handovers/channel-center-phaseC.md`
**Implemented by:** Opus 5 · **Date:** 2026-07-25 · **Target:** vietuat
**Module:** `health_care_command_channels` 19.0.2.0.0 → **19.0.3.0.0** (only)

---

## 1. What was built

```
health_care_command_channels/                        (→ 19.0.3.0.0)
├── models/
│   ├── channel_center.py            NEW  center_overview / center_begin /
│   │                                     center_telegram_validate /
│   │                                     center_telegram_register_webhook /
│   │                                     center_webchat_enable / _settings /
│   │                                     center_test / center_disconnect /
│   │                                     center_reconnect + the translated
│   │                                     chip/check/guide vocabulary + the ONE
│   │                                     embed-snippet + ?v= implementation
│   └── care_channel_connection.py   +    AMENDMENT F1 (_recompute_ready),
│                                         CENTER_GROUPS + _center_group_ok /
│                                         _check_center_access, gate on
│                                         set_settings
├── services/adapters.py             +    BaseChannelAdapter._get,
│                                         TelegramAdapter.validate_token
│                                         (getMe) + register_webhook
│                                         (setWebhook), platform_providers
│                                         declaration on the 5 platform-app
│                                         channels
├── static/src/center/
│   ├── channel_center.js            NEW  OWL client action `channel_center`
│   ├── channel_center.xml           NEW  catalogue + stepper/manage modal
│   ├── channel_center.css           NEW  hf-wt-ico CSS-mask icon set (plain
│   │                                     CSS — §5.51)
│   └── channel_center.scss          NEW  flat mono layout, no gradients
├── static/src/webchat/widget.js     +    poll switched GET → POST
├── controllers/webchat.py           +    poll route POST + body parsing;
│                                         _widget_version / embed snippet now
│                                         delegate to the model (one impl)
├── views/channel_center_views.xml   NEW  ir.actions.client + menu (seq 10,
│                                         tenant-admin + crm-manager)
├── data/cms_sidebar_items_channel_center.xml  NEW  the CMS-shell entry point
│                                         (D11 — the backend menu alone is
│                                         unreachable for these users)
├── security/ir.model.access.csv     +    5 tenant-admin rows (connection RWC,
│                                         no unlink; readiness/audit/identity/
│                                         message read; platform.app NOTHING)
├── i18n/vi.po                       +    CC-C strings — and the §5.67 repair
│                                         of the whole file (see §4)
├── __manifest__.py                  +    19.0.3.0.0, depends health_user_admin,
│                                         assets bundle, CC-C description
└── tests/
    ├── test_center.py               NEW  T96–T105
    └── common_spine.py              +    mock_get (getMe), _mock_http
```

### What the phase actually changes for a user

A tenant administrator (or a Care Command manager) now has **Care Command Setup
→ Channel Center**: eight cards, honest status chips, and a stepper that takes
web chat and Telegram from nothing to working without a developer, a shell or a
support ticket. The other six cards say what they are waiting for and offer no
button that could only fail.

Nothing else moves. With zero connections `_channel_keys()` still returns
`('zalo', 'call', 'email', 'zns')`, the dock is unchanged, and the composer
behaves exactly as before.

### The two self-service flows, end to end

**Web chat (one click).** `center_begin` → paste the website addresses (each
validated: scheme + host only, https unless localhost, no path/query/credentials
— a `javascript:` scheme, a bare hostname and a plain-http public host are all
refused) → `center_webchat_enable` stores them, writes `resource_selected=pass`,
moves to `testing` and hands back the embed snippet with its `?v=` stamp and the
demo URL → the card says "Waiting for the first message…" until a real widget
message arrives, and the ingest funnel's `inbound_ok` is what flips it to
**Connected**. No one asserts readiness anywhere in that chain.

**Telegram (guided BotFather wizard).** `center_begin` → BotFather deep link →
paste the key → `center_telegram_validate` calls `getMe` **before storing
anything** (an invalid key leaves no secret, no resource, no state move and no
readiness row) → on success the key is encrypted (`chs$1$`), the bot id and
`@handle` are stored, two checks pass and the state moves to `configuring` →
`center_telegram_register_webhook` mints a 32-byte path secret **once**, refuses
outright if `web.base.url` is not https, calls `setWebhook` with
`allowed_updates=["message"]` and the same value as `secret_token` → the tenant
messages the bot, the webhook proves itself, and `center_test` sends the
synthetic body *"Health19 connection test — please ignore."* (§7.6 — never
patient data) which proves `outbound_ok` and derives **ready**. The dock lights
at that moment and not before.

### Security properties actually implemented

- **Every Center endpoint is group-gated in the method**, not only by ACL: they
  all write through `sudo()._internal()`, so there is no ACL underneath them
  (§5.37 corollary). `CENTER_GROUPS` = system + crm-manager + tenant-admin, plus
  a company check on every resolved connection.
- **`set_settings` gained the same gate.** It was a public RPC method writing
  through `sudo()._internal()`, so any logged-in user who could read a
  connection could have re-pointed the web chat's CORS allowlist. Found while
  wiring the Center; fixed here (declared as deviation D6).
- **No credential material in any payload.** `center_overview` carries no token,
  no ciphertext, not even `secret_hint`; T97 dumps the whole thing to JSON and
  asserts the seeded secrets are absent.
- **The pasted key is validated before it is stored and zeroed after.** Server
  side, nothing is written until `getMe` answers; client side the token is
  cleared from component state on BOTH the success and the failure path, never
  logged, never re-displayed.
- **The tenant-admin plane stops at plane 2.** `channel.platform.app` gets no
  ACL row for the group at all, and a direct `write({'state': 'ready'})` raises
  the model guard (T98).
- **Disconnect never deletes and never wipes a credential** — re-enabling does
  not re-prompt for the bot key (T103 proves the round trip).
- **The widget's poll is a POST** (sanctioned CC-B touch-up): the session id is
  the visitor's bearer credential for their own thread and no longer lands in
  proxy access logs, browser history or `Referer`. Same response shape, same
  rate-limit keys, still a CORS *simple* request.

---

## 2. Amendment F1 — the §5.66 lockout, closed

`_recompute_ready` now distinguishes a required check that **failed** from one
that simply **has not happened yet**:

| situation | before | after |
|---|---|---|
| any required check `fail` | `action_required` | `action_required` (unchanged) |
| all required `pass` | `ready` | `ready` (unchanged) |
| some required missing, state `testing` | **`action_required` → not ingestable → channel stranded** | stays `testing` (ingestable, not sendable) |
| some required missing, state `ready`/`expiring` | `action_required` | `action_required` (unchanged) |

T96 stages the exact sequence from the ledger: a web-chat connection in
`testing` with only `resource_selected=pass`, then a simulated first inbound
(`_note_inbound` → `webhook_verified` + `inbound_ok`), and asserts it reaches
`ready` **without ever passing through `action_required`** (checked against the
audit trail, not just the final state) — then that a genuine `fail` from
`testing` still demotes and still stops ingest. §5.66 is marked RESOLVED in the
ledger.

---

## 3. Deviations from the handover (all declared)

| # | Handover said | Shipped | Why |
|---|---|---|---|
| **D1** | overview picks "the newest active **non-disabled** row" | the newest **active** row, disabled included | Disconnect is a state, not a delete, so the row a tenant must reconnect is precisely the disabled one. Hiding it would render the card "Not connected", and `center_begin` would then try to create a second active row and hit the partial unique index. The card renders `disabled` honestly with a "Turn back on" action. |
| **D2** | `resource_label = '@' + username` | `resource_display_name` | §5.59: no `resource_label` field exists on `care.channel.connection` (architecture §5.2 names it `resource_display_name`). |
| **D3** | on setWebhook ok ⇒ `webhook_state='configured'` | `webhook_state='subscribed'` | §5.59 again: `WEBHOOK_STATES` is `none/pending/subscribed/verified/failing` — `configured` is not a valid value. `subscribed` is the architecture's own word for "we registered it"; the first real update then moves it to `verified` via `_note_inbound`. |
| **D4** | `available` = "an active `channel.platform.app` row for the provider" | same, driven by a new **`platform_providers`** capability on the adapters | Nothing mapped a channel key to a provider; the alternative was a hard-coded map in the Center, which is exactly the coupling `authorization_capabilities()` exists to avoid. Optional key, same pattern as the existing `parent_channel`; `email` declares `['google', 'microsoft']` (either makes it offerable). T81 is unaffected. |
| **D5** | "Extend the CC-A company record rules' group lists to include the tenant-admin group" | no rule change — a comment explaining why | The CC-A rules are **global** (no `groups` field), so they already bind every persona including the new one. A group-bound rule would be strictly weaker. |
| **D6** | (not in the sanction list) | `set_settings` is now group-gated | It writes through `sudo()._internal()` and was RPC-reachable by any user with read access — the Center made it load-bearing (it stores the CORS allowlist), so it could not ship ungated. Same gate as every other public writer on the model. |
| **D7** | (not in the sanction list) | `action_set_secret`'s group gate now includes the tenant-admin group | T98 requires a tenant admin to complete the Telegram happy path, which stores the bot key. Without this the persona the phase exists for could not finish its own wizard. |
| **D8** | T101 "simulated inbound update (controller-level with header secret)" | `_dispatch_connection` + a direct `verify_telegram(conn, secret, secret)` / wrong-header assertion | This module ships **zero HttpCase** by design (§5.32, CC-A/CC-B precedent). The header verifier is asserted directly and the ingest path through the funnel; only the ten-line HTTP shell is not re-driven. |
| **D9** | (addition) | `center_webchat_settings` | Re-opening an already-enabled web chat has to show the tenant their current origins and snippet; the alternative was making the browser reconstruct them. |
| **D10** | (addition, forced) | the whole `i18n/vi.po` rewritten with `#:` occurrence lines | See §4 — without them the file is inert, so "vi.po covering user-visible strings" could not be satisfied by adding entries alone. |
| **D11** | menuitem under `menu_care_command_config` only | that menuitem **plus** a `cms.sidebar.item` (new `data/cms_sidebar_items_channel_center.xml`, new `health_cms_sidebar` dependency) | **Forced by the browser pass.** The backend menuitem is correct and completely unreachable from the CMS shell these users live in (§7.1) — the Center could only be opened by deep link, which the DoD explicitly forbids as evidence. Architecture §9 always specified two entries ("Care Command gear → Channels **+** menuitem"); this is the CMS-shell equivalent of the gear. Ungated like the sibling Care Command item, with the server gate rendering as an honest inline message. |

---

## 4. Two defects found live that the handover did not anticipate

### 4.1 The entire Vietnamese catalogue was inert (new ledger §5.67)

T105's runtime spot-check (`_('Connected')` under `lang='vi_VN'`) came back
`'Connected'`. Cause: Odoo's `PoFileReader.__iter__` yields one row **per entry
occurrence** (`odoo/tools/translate.py:849`) and has no fallback branch — an
entry with a correct `#. module:` comment (§29) and a correct `#. odoo-python`
marker (§5.58) but **no `#:` reference line** produces zero rows and is never
loaded. `health_care_command_channels/i18n/vi.po` had 182 entries and **0
occurrences**: every CC-A and CC-B Vietnamese string had been dead since it
shipped, silently.

Fixed by giving every entry a real reference — `#: code:addons/<mod>/<file>:0`
for code strings (located by searching the sources, so the paths are honest) and
`#: model:ir.model.fields.selection,name:…` / `#: model:ir.ui.menu,name:…` for
the 24 label entries (xmlids verified against `ir_model_data` first). Also
de-duplicated six msgids that existed twice. Result on vietuat: **118 Python +
48 web translations now load** (previously 0), and the selection labels
translate too.

T105 now guards it: every block must carry `\n#: `, and every block with a code
marker must carry `#: code:addons/health_care_command_channels/`.

**This is repo-wide.** `grep -c '^#:' addons/*/i18n/*.po` returns 0 for every
hand-written catalog in the project — health_care_command, health_voip24h and
the rest are all inert for the same reason. Ledgered as §5.67 with the fix
recipe; repairing the other modules is out of this phase's sanction.

### 4.2 One CSS rule un-styled the whole backend (new ledger §5.68)

`width: min(560px, 100%)` on the stepper modal — ordinary CSS — makes Odoo's
libsass raise `Internal Error: Incompatible units: '%' and 'px'` (SASS has its
own `min()`). The failure is **not scoped to the file**: `assetsbundle` logs one
WARNING and emits the bundle with *all* scss dropped. Measured on vietuat while
it was deployed: `web.assets_web.min.css` fell from 2.19 MB to 40 KB and
`.o_care_command` disappeared from it — **Care Command was rendering unstyled
because of a rule in a different addon**.

No test catches this: nothing in the suite compiles an asset bundle, and the run
was green throughout. Found by explicitly compiling the scss on the server and
checking a *sibling* selector, not just my own. Fixed with
`width:100%; max-width:560px`; verified by recompiling (`sass.compile` OK,
12,978 bytes) and regenerating the bundle: 2,189,484 bytes with
`.o_channel_center .cc-card`, `.o_channel_center .ic-plug` **and** the
`.o_care_command` control all present.

The stale-bundle attachments were cleared once during diagnosis
(`ir.attachment` rows under `/web/assets/`) — a cache, regenerated on demand and
verified regenerated afterwards.

---

## 5. Test results (verbatim, vietuat, final run)

```
2026-07-25 22:48:57,565 2032895 INFO vietuat odoo.tests.stats: health_care_command: 38 tests 7.81s 6510 queries
2026-07-25 22:48:57,566 2032895 INFO vietuat odoo.tests.stats: health_care_command_ai: 8 tests 1.74s 1522 queries
2026-07-25 22:48:57,566 2032895 INFO vietuat odoo.tests.stats: health_care_command_channels: 68 tests 13.54s 11996 queries
2026-07-25 22:48:57,566 2032895 INFO vietuat odoo.tests.stats: health_care_command_voip: 6 tests 0.52s 397 queries
2026-07-25 22:48:57,566 2032895 INFO vietuat odoo.tests.result: 0 failed, 0 error(s) of 102 tests when loading database 'vietuat'
EXIT:0   HTTP:200
```

56 test methods in this module: CC-A 20 + CC-B 26 + **CC-C 10 (T96–T105)**; 102
counted with the Care Command regression family (which is untouched this phase —
zero edits to `health_care_command`). TransactionCase only, **zero HttpCase**,
zero real HTTP, zero credentials.

| test | what it proves |
|---|---|
| T96 | amendment F1: `testing` survives missing checks, reaches `ready` without ever being demoted; a real `fail` still demotes and still stops ingest |
| T97 | 8 cards in dock order, no secret material in the JSON dump, honest `available` (meta app present ⇒ WhatsApp/Messenger offerable; no zalo/google app ⇒ not), archiving the platform app flips it instantly, ZNS renders under Zalo, company isolation |
| T98 | tenant admin runs the web-chat happy path; cannot forge `state`/`resource_external_id` (UserError, guard before ACL — §5.39); no `channel.platform.app` access (AccessError); audit read-only; a plain CRM user is refused |
| T99 | `getMe` refusal stores **nothing** (asserted with `try/except`, never `assertRaises` — §5.8/§5.65); a malformed paste never reaches the network; success stores `chs$1$` ciphertext with the plaintext absent from the column and from the return value |
| T100 | http base URL ⇒ UserError with **no call made**; https ⇒ correct URL, `secret_token` == path secret, `allowed_updates=['message']`, `webhook_state='subscribed'`, state `testing`; re-registration keeps the same secret |
| T101 | full self-service arc to `ready`; the dock stays dark while proving; the header verifier accepts the right token and rejects a wrong one; the test body is synthetic |
| T102 | origin validation (5 rejection classes), normalisation + de-duplication, snippet carries `?v=`, first real widget message ⇒ `ready` and the dock lights; the poll route is POST |
| T103 | disconnect stops ingest (`webhook_ignored` audit) and the composer refuses honestly; reconnect re-proves to `ready` **without re-entering the key** |
| T104 | `center_begin` idempotent (one row); the six unimplemented channels refuse cleanly and create nothing |
| T105 | vi.po structure (module comments, occurrences, code markers, no duplicate msgids) + two strings actually translated at runtime under `lang='vi_VN'` |

---

## 6. Data honesty on vietuat

Full transcript: `docs/strategy/reports/channel-center-phaseC-evidence/server-state.txt`.

- **0 platform apps, 0 connections, 0 identities, 0 messages, 0 readiness
  checks, 0 sessions** (counted `active_test=False`, §5.27, re-verified on a
  fresh cursor after the browser QA — §5.34). **19 `care.channel.audit` rows**:
  2 from CC-B plus 17 from this QA pass. That is designed behaviour, not
  residue — the table is append-only with no `su` escape and `connection_id` is
  `ondelete='set null'` precisely so deleting a connection cannot erase its
  history (§5.30). No secret, token fragment or provider payload is in any of
  them.
- `_channel_keys()` → `('zalo', 'call', 'email', 'zns')`: the four adapter dock
  icons stay dark for every real user, exactly as before this phase.
- The live catalogue is honest with itself: **Telegram and Web chat are the only
  two cards offering a Connect button**; Zalo/ZNS/WhatsApp/Messenger/Email read
  "not available yet" (no platform app), Calls reads "available in an upcoming
  update" (no platform app needed, but the flow is CC-F).
- Menu `CRM Center/Care Command Setup/Channel Center`, sequence 10, gated to CRM
  Manager + Healthcare: User Administrator. Tenant-admin ACL exactly as
  designed, **0 grants on `channel.platform.app`**.
- All three crons still registered and active.
- No pip installs. No PWA involvement (backend assets only), so no PWA version
  bump was due.

### Ops item: `web.base.url` — RESOLVED during this phase

`web.base.url` was `http://care.biztinct.com`, which the Telegram wizard
refuses by design (it will not register a non-https webhook) and which made the
embed snippet a mixed-content trap (CC-B's flag). **The user set it to
`https://care.biztinct.com` on 2026-07-25 23:19**; verified live from a running
worker — the demo page now emits an https snippet, and the wizard's guard
passes. No code change was involved, and none was warranted.

---

## 7. Browser evidence

Full pack (12 screenshots + click-by-click transcript):
`docs/strategy/reports/channel-center-phaseC-evidence/navigation.md`.
Driven as `crm` (a Healthcare CRM Manager, not a system administrator) on
care.biztinct.com. **Console clean on every screen, both tabs, across all
navigations.**

Proven live, from the real entry point:

- **Catalogue** — 8 channels, honest chips: four say "Health19 is completing
  provider approval", Calls says "Available in an upcoming update", ZNS renders
  inside Zalo's card, and only Telegram and Web chat offer Connect.
- **Web chat end to end** — enable → snippet (https, `?v=19.0.3.0.0`,
  `Copied ✓`) → demo page → visitor message → **card flips to Connected on its
  own poll** → Care Command's WEB CHAT dock icon lights (the other three stay
  dark) → reply from the composer → arrives in the visitor's widget. Every
  widget poll in the network panel is a **POST**.
- **Telegram end to end against a local stub** (`api_base_override` →
  `127.0.0.1:8899`; no real bot, nothing left the box): BotFather screen →
  malformed key refused with the field zeroed and **no network call** → real
  key validated by `getMe`, bot handle shown, token zeroed, ciphertext in the
  column → `setWebhook` → **the real public webhook route** (wrong header 403,
  unknown secret 403, correct 200 + ingested) → synthetic test reply → 4/4
  Connected.
- **Amendment F1 proven live**: after the proving inbound the connection stayed
  in `testing` ("Almost there") instead of being demoted out of ingest.
- **§5.65 proven by accident**: the first test send hit a stub with no
  `sendMessage`, and the failed message row, the redacted reason and the
  `send_failed` audit all survived the `UserError` on the independent cursor —
  with `authorization_valid` correctly left alone (a transient refusal is not a
  lost grant).
- **Manage + disconnect** — readiness checklist in plain words, technical
  details with no secrets, and the confirmation copy verbatim from §9; the
  credential survives disconnect so reconnect never re-prompts.

### 7.1 A reachability defect the browser pass found — and fixed

The first attempt could not reach the Center **at all** as a real user. Users
land in the `/bizapp` CMS shell; `/odoo` redirects back into it; and the
shell's app switcher offers only *Viet UC CMS* and *Workflow Automations* — so
"CRM Center → Care Command Setup → Channel Center" is unreachable even though
the menu is correct and visible to that user server-side. That is the ledger
§5.41 sibling trap, and it meant **the phase's entire deliverable was
unreachable for the persona it was built for**. Only a deep link worked.

Fixed with `data/cms_sidebar_items_channel_center.xml` — a `cms.sidebar.item`
directly after Care Command in the CRM section (declared as deviation D11). Two
further traps were hit and fixed while doing it, both caught by driving the
sidebar rather than reading the model:

- seeding it as a **child** of Care Command turned Care Command itself into a
  non-navigating accordion (`cms_sidebar.js:124` — items with children become
  expandable groups, only leaves navigate). It is a sibling instead, and Care
  Command was re-verified as still navigating;
- **removing `parent_id` from the XML did not unset it** — an Odoo data update
  only writes the fields it names, so the item stayed a hidden child through a
  whole deploy. It now carries `<field name="parent_id" eval="False"/>`.

---

## 8. Deferred / next

- **CC-D** (Zalo/ZNS refactor), **CC-E** (Meta onboarding), **CC-F** (Email +
  VoIP24h + monitoring polish) — the six remaining cards are structure-only by
  design, and their `guide_steps` titles already render so a tenant can see what
  connecting will involve.
- `oauth_popup` / `embedded_signup` stepper screens: `center_begin` refuses them
  with the honest "not available yet" until their phase lands.
- **The repo-wide `.po` repair (§5.67)**: every other module's hand-written
  Vietnamese catalog is inert for the same reason. Out of this phase's sanction;
  worth a dedicated sweep.
- **The CMS-sidebar reachability gap is wider than this phase** (§7.1): the
  telemonitoring and twin menus have the same problem (ledger §5.41), and every
  future backend surface aimed at CMS-shell users needs a sidebar item seeded
  alongside its menuitem. Worth making it a line in the handover template.
- No media download, no Meta template messages, no bus/websocket, no new public
  routes, no queue, no AI — all still binding non-goals.
