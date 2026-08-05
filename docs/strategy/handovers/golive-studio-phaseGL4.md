# GL-4 — Google + Microsoft go-live flows, Calls truth card (Go-Live Studio, final phase)

Read `docs/strategy/HANDOVER-CONVENTIONS.md` FIRST and follow it exactly.
Then read `docs/strategy/handovers/golive-studio-design.md` (the stream design),
`golive-studio-phaseGL1.md` §Architecture (the step-declaration contract) and
skim `addons/health_care_command_channels/models/channel_golive.py` — GL-4 is
almost entirely *declarations* added to a framework that GL-1..GL-3 built and
proved. Review model for this stream: **no Fable review pass — you run the
self-review protocol at the end and report honestly.**

## Scope

1. **D1** — declare the **google** and **microsoft** go-live flows in
   `_golive_steps()`; retire their `PROVIDER_EXTERNAL_STEPS` entries
   (completing the GL-1 "one source of truth" unification for every provider).
2. **D2** — extend the provider gates and name maps; Studio home renders four
   provider cards.
3. **D3** — flat-mono console illustrations for the two new flows.
4. **D4** — the **Calls (VoIP24h) truth card**: a static, UI-only info card on
   the Studio home. VoIP24h is **not** a Studio flow and must not become one.
5. **D5** — tests T196+, vi.po, deploy, browser QA, self-review, and the
   **thesis verdict** (below).

**Binding non-goals**: no new models, no new controllers, no new RPC methods,
no change to the invite/delegation machinery, no change to
`_golive_step_status()` branches, no VoIP24h platform-app support, no webhook
steps for google/microsoft (they have none — mail is an IMAP poll), no
`mail.template`, no `tracking=True`, nothing outside
`addons/health_care_command_channels`.

**The thesis this phase exists to test** (GL-1's promise): *adding a provider
is declarations only — zero framework change.* GL-3 already identified the
falsifiers. Your report MUST contain a verdict section listing every
framework-file line you touched and why. Expected touches (sanctioned):

- `GOLIVE_PROVIDERS` (channel_golive.py:61) → `('meta', 'zalo', 'google',
  'microsoft')`. Order is the home-screen order — meta first stays.
- `GOLIVE_PROVIDER_NAMES` (:95) → add `'google': 'Google'`,
  `'microsoft': 'Microsoft'`.
- Its JS twin `PROVIDER_NAME` in `static/src/golive/golive_studio.js` — same
  two entries.
- The `_golive_steps()` dict itself (the declarations — the point of the phase).
- `PROVIDER_EXTERNAL_STEPS` (channel_platform_app.py:99) → `{}` (keep the
  constant and the fallback at :353 with a comment saying every provider is
  now declared; deleting the mechanism is NOT sanctioned — GL-5 providers may
  want it).
- Home-grid CSS if four cards need a track tweak.

Anything beyond that list is a falsification — do it if correctness demands
it, but list it in the verdict. Known **non-touches** (verify, don't change):
`INVITE_COPY_KEYS` (:90) already whitelists `oauth_redirect_uri`, which is the
only value these flows delegate; `GOLIVE_HANDSHAKE_CHANNELS` (:66) gets no
entry (no webhook, no handshake); `WEBHOOK_PATHS` stays `[]` for both
(channel_platform_app.py:75-76).

## Verified plumbing facts (do not re-derive)

- `PROVIDERS` already contains google + microsoft
  (channel_platform_app.py:42-47) — the selection, the partial unique index,
  `action_set_secret`, `get_extra`, `_go_live_rows` all already work for them.
- `OAUTH_REDIRECT_PATHS` (:58-63): google = `/google_gmail/confirm`,
  microsoft = `/microsoft_outlook/confirm` — Odoo's own mixins own these
  routes; we print THEIR URIs (comment at :52-57 explains why; deviation D1 of
  CC-G). `_golive_urls()` (channel_golive.py:637) already returns them with no
  row existing.
- `WEBHOOK_PATHS['google'|'microsoft'] = []` (:75-76) → the `webhook_urls`
  value in `golive_state()` is `''` for them. **Do not declare
  `'webhook_urls'` in any google/microsoft `copy_values`** — GL-3 proved a
  copy key with an empty value renders zero blocks, not an explanation.
- `action_preflight` is Meta-only; every other provider gets status
  `unverifiable` (channel_platform_app.py:416, PREFLIGHT_UNVERIFIABLE :121).
  **Therefore google/microsoft `store_secret` steps MUST declare
  `verify: 'manual'`, never `'preflight'`** — the status branch at
  channel_golive.py:798-804 only accepts `preflight_status == 'pass'` when
  `verify == 'preflight'`, so a preflight-declared step would be stranded at
  `todo` forever. With `verify: 'manual'`, `has_secret` alone flips it done —
  which is the honest truth: these credentials are proven at the first real
  mailbox sign-in.
- Status derivation is generic (channel_golive.py:786-817): `create_app` ⇒
  client_id present; `store_secret` ⇒ secret (+preflight rule above); `done` ⇒
  `all_rows_done` from `_go_live_rows()`; `kind: 'wait'` ⇒ mark = waiting;
  `kind: 'do', verify: 'manual'` with no artifact ⇒ mark = done (the Zalo
  redirect-URI step already works this way — clone its UI behaviour, the GL-2
  canvas already has the affordance). **No new branches needed. If you think
  you need one, you have mis-declared a step.**
- `_golive_channels()` (:626) scans adapter `platform_providers` — google and
  microsoft each resolve to `['email']` (adapters.py:2133). `platform_ready()`
  (adapters.py:437-462) lights the tenant Email card when **either** provider
  has a complete app — the flows' copy must say "you only need one of these
  two".
- The email adapter declares NO `required_platform_keys` → `_go_live_rows`
  for google/microsoft is just client_id + secret → the `done` step derives
  from exactly those two.
- Odoo addon dependency: tenant sign-in needs `google_gmail` /
  `microsoft_outlook` installed (`EMAIL_ADDON_MODEL`,
  channel_platform_app.py:118 — model-presence test). The Studio does NOT gate
  on it (the paperwork is real either way) but the `done` step body must state
  it honestly. **Report-back: check whether each addon is installed on
  vietuat** (`env['ir.model'].search([('model','=','google.gmail.mixin')])`
  style) and report what the tenant Email card actually shows.
- VoIP24h: `CallAdapter` has `needs_platform_app: False`
  (adapters.py:2468-2480) — calls never touch `channel.platform.app`;
  the channel is receive-only, proven by inbound traffic, and the API contract
  is uncaptured (`docs/strategy/voip24h-contract-capture.md`). There is no
  operator console paperwork to guide → a *flow* would be an invented lie.
  Hence D4's static truth card.
- Console deep links: **static URLs only for both new providers.** Google's
  console doesn't key on the OAuth client id in a stable public URL, and Entra
  deep links need the *object id* (which we never hold), not the client id —
  a `{app_id}`-templated link would 404 in the operator's face. Never use
  `{app_id}` in google/microsoft `console` templates.
- Delegation works for the new flows for free: the only copy value is
  `oauth_redirect_uri` (already in `INVITE_COPY_KEYS`), the Studio affordance
  keys on `kind == 'do'` + non-empty `copy_values`, and the public page is
  provider-agnostic. One HttpCase proves it (T203).
- Mail-server ops note (NOT work): vietuat has zero `ir.mail_server` rows, so
  invite *delivery* still fails there. Known, accepted, tested via the
  refusal path. Beware §5.79 if anyone adds one.

## D1 — the declarations

Add to `_golive_steps()` (channel_golive.py:325), after `'zalo'`. All copy
through `_()` at call time; clone the existing voice (plain language, honest,
no jargon; the operator is non-technical). Step keys are frozen API — choose
them exactly as below.

**google (5 steps, channels ['email']):**

1. `create_app` · `do` · "Create the sign-in client" — body: open Google
   Cloud Console, create/select a project, enable the **Gmail API**, then
   Credentials → Create credentials → **OAuth client ID**, type **Web
   application**, named after your company. Paste the Client ID here.
   Console: `https://console.cloud.google.com/apis/credentials` (static).
   Input `client_id`, regex `^\S+\.apps\.googleusercontent\.com$`, error:
   "A Google client ID ends in .apps.googleusercontent.com — copy it from the
   Credentials page." `verify: 'manual'`, est ~15 minutes.
2. `store_secret` · `do` · "Store the client secret" — body: the client's
   page shows a Client secret; paste it here, we encrypt it and never show it
   again. Say honestly: Google gives us no harmless way to test these — they
   are proven the first time a clinic connects a mailbox. Input
   `client_secret`, `secret: True`, regex `^\S{10,128}$`.
   **`verify: 'manual'`** (see plumbing fact above). est ~5 minutes.
3. `redirect_uri` · `do` · "Tell Google where to come back" — body: open the
   OAuth client and add this address to **Authorised redirect URIs**.
   `copy_values: ['oauth_redirect_uri']`. `verify: 'manual'`, est ~5 minutes.
4. `consent_screen` · `wait` · "Publish the consent screen" — body: an
   unpublished (testing) screen expires every mailbox's access after 7 days,
   which looks like random sign-outs; publish it (or expect Google's
   verification questions for the gmail scopes — answering them can take
   days). Mark this step once submitted. Console:
   `https://console.cloud.google.com/apis/credentials/consent`.
   `verify: 'manual'`, est "a few days if Google asks questions".
5. `done` · `check` · derived — body: "Email through Gmail is ready to offer.
   Clinics connect their own mailbox from the Channel Center." Note that ONE
   of Google/Microsoft is enough for the Email card, and that clinic sign-in
   uses Odoo's Gmail integration (`google_gmail` addon) which must be
   installed. `verify: 'manual'`, `copy_values: []`, `inputs: []`.

**microsoft (5 steps, channels ['email']):**

1. `create_app` · `do` · "Register the application" — body: in the Microsoft
   Entra admin center open App registrations → New registration; name it
   after your company; for supported account types choose "Accounts in any
   organisational directory and personal Microsoft accounts" unless every
   clinic mailbox lives in your own tenant. Paste the **Application (client)
   ID**. Console: `https://entra.microsoft.com` (static — see plumbing fact:
   never `{app_id}` here). Input `client_id`, regex
   `^[0-9a-fA-F]{8}-([0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}$`, error: "The
   Application (client) ID is a UUID like 12345678-abcd-... — copy it from
   the app's Overview page." `verify: 'manual'`, est ~10 minutes.
2. `redirect_uri` · `do` · "Tell Microsoft where to come back" — body:
   Authentication → Add a platform → **Web** → paste this address.
   `copy_values: ['oauth_redirect_uri']`. `verify: 'manual'`.
3. `permissions` · `do` · "Grant the mailbox permissions" — body: API
   permissions → Add a permission → Microsoft Graph → **Delegated**: add
   `Mail.Send`, `Mail.ReadWrite`, `IMAP.AccessAsUser.All` and
   `offline_access`; then press **Grant admin consent**. `verify: 'manual'`,
   est ~10 minutes.
4. `store_secret` · `do` · "Create and store a client secret" — body:
   Certificates & secrets → New client secret. **Copy the Value column, not
   the Secret ID** (the classic mistake — the Value is shown only once).
   Entra secrets expire (24 months at most): note the expiry date in the
   application's note so future-you finds it. Input `client_secret`,
   `secret: True`, regex `^\S{10,128}$`. **`verify: 'manual'`**.
5. `done` · `check` · derived — mirror of google's, naming the
   `microsoft_outlook` addon.

Then empty `PROVIDER_EXTERNAL_STEPS` (keep constant + fallback per Scope).

## D2 — gates, names, home

`GOLIVE_PROVIDERS`, `GOLIVE_PROVIDER_NAMES`, JS `PROVIDER_NAME` per Scope.
Home journey map now shows four cards; both google and microsoft cards list
the Email channel chip; honest time estimates ("Google: about an hour, plus
days if Google reviews your consent screen"; "Microsoft: about an hour").
Prerequisites line per card ("You'll need: admin access to your Google Cloud
/ Microsoft Entra organisation"). The GL-2 card component is data-driven —
this should be zero component change beyond the name map; if the grid caps at
a bad wrap with 5 items (4 + Calls card), adjust the CSS track sizing.

## D3 — console illustrations

Two new inline flat-mono SVGs in the GL-2 style (~360×200, `role="img"`,
no provider trade dress, no wordmarks — abstracted panels only): the Google
Cloud "Credentials" screen with the client-ID row highlighted, and the Entra
"Certificates & secrets" screen with the **Value** column highlighted (that
illustration IS the not-the-Secret-ID lesson). Reuse across steps of the same
provider where sensible — GL-2 already established per-step illustration
wiring.

## D4 — the Calls truth card

Static, UI-only, declared as a const in `golive_studio.js`, rendered after
the four provider cards. Flat info card (no progress ring, no flow, not
clickable into a canvas): title "Calls (VoIP24h)", body ≈ "No provider app
is needed — clinics connect the phone system from the Channel Center with the
webhook secret from the VoIP24h portal. Receiving calls works today; sending
and call history wait on VoIP24h's API contract, which is still being
captured." One link: opens the Channel Center. Translatable strings via the
standard JS `_t`. **No server change; `_golive_step('call'|'voip24h', ...)`
must keep raising** (pinned by T204).

## D5 — tests (extend `tests/test_golive.py`, same fixtures)

- **T196** declarations shape: for google + microsoft — exactly the 10
  `GOLIVE_STEP_KEYS` per step, unique keys, first key `create_app`, last
  `done`, legal kind/verify values, **no `'preflight'` verify anywhere**, no
  `'webhook_urls'`/`'verify_token'` in any `copy_values`, every `copy_values`
  entry ∈ `INVITE_COPY_KEYS`, **no `{app_id}` in any console template**.
- **T197** `golive_state()` returns the four providers in
  `GOLIVE_PROVIDERS` order; google/microsoft payloads: `channels == ['email']`,
  `values['oauth_redirect_uri']` ends with the mixin paths
  (`/google_gmail/confirm`, `/microsoft_outlook/confirm`),
  `values['webhook_urls'] == ''`, no `verify_token`/meta extra keys present,
  `last_handshake_at is False`.
- **T198** input validation: google accepts
  `123-abc.apps.googleusercontent.com`, rejects `1234567890123`; microsoft
  accepts a UUID, rejects a Meta-style number; both reject on the OTHER
  provider's step (cross-check the regex is per-declaration, not global).
- **T199** google `store_secret` submit: routed through `action_set_secret`
  (secret_hint = last 4, `client_secret_enc` set), **no preflight ran**
  (`preflight_status` still `'none'`), step status `done` on `has_secret`
  alone.
- **T200** the zero-glue thesis end-to-end: complete a google row (client_id
  + secret) with NO microsoft row → google `done` step is `done` and
  `platform_ready()` for the email channel is truthy (assert via the adapter,
  the same call the tenant cards make). Microsoft row absent proves
  either-of-two.
- **T201** checklist unification: `go_live_checklist` for a google row
  renders the declared titles; `PROVIDER_EXTERNAL_STEPS == {}`.
- **T202** `consent_screen` wait-step marks to `waiting` with `marked_on`;
  meta inert-mark regression unchanged (rerun the GL-1 assertion against a
  google `do` step too).
- **T203** (HttpCase, clone T192's harness): invite on google `redirect_uri`
  step — public page renders the sender-language step title (§5.123!), shows
  exactly one copy block (the redirect URI), body contains no `secret`/`chs$`
  material, dead-end for a bogus token still byte-identical to GL-3's four.
- **T204** `_golive_step('call', 'anything')` and `('voip24h', ...)` raise
  ValidationError — the Studio does not drive calls.

All new HttpCases `@tagged('post_install', '-at_install')`. Count started
tests per §5.75/§5.83/§5.90. Expect prior 193 + new ≈ 202-count line; the
GL-2 tour skip (websocket-client) will still appear — pre-existing, note it.

## Deploy

Conventions §2 exactly. Bump `__manifest__.py` → **19.0.11.0.0**. vi.po for
every new string (`msgfmt --check-format`). scp → sudo cp (odoo ownership) →
upgrade `health_care_command_channels` → restart → result line + start counts
from your own logfile, spare `--http-port`, `--workers=0`, no `--no-http`.

## Browser QA (chrome-devtools on care.biztinct.com, real user path)

Screenshots to scratchpad `gl4-qa/`. Both themes + 390×844 mobile on the
home. (1) Home: four provider cards + Calls truth card, no wrap breakage.
(2) Google flow end-to-end with a plausible client id
(`999-test.apps.googleusercontent.com`) + fake secret → watch `create_app`/
`store_secret` derive green with NO preflight badge lying; consent screen
mark → amber waiting. (3) Microsoft flow: UUID paste, permissions step,
Value-not-Secret-ID illustration visible. (4) Delegation: send the google
`redirect_uri` step (expect the honest mail-failure refusal on vietuat — that
IS the pass state), and open a hand-minted invite logged-out to see the
redirect-URI block. (5) The Channel Center tenant view: what the Email card
shows now that a google row is complete — report honestly, including the
addon-installed finding. Pixel-audit over iterations per standing rule.
**Archive every row/app you create** (partial unique index + GL-2's fixture
lesson) and list leftovers in the report.

## Self-review protocol (mandatory, in place of a Fable review)

1. Re-read every changed file top-to-bottom against this spec; walk each
   declaration against the status branches (:786-817) proving no step can
   strand.
2. Independent server verification per conventions §2 — result lines from
   your own logfile, never stdout; fresh-tab login QA.
3. Grep the diff: `t-raw` (0), `tracking=True` (0), `preflight` in new
   declarations (0), `{app_id}` in new console strings (0), secrets in logs
   (0).
4. Honest gaps + the **thesis verdict**: every framework line touched, with
   the reason, and your one-paragraph answer to "was GL-1's 'declarations
   only' promise true?" Plus: addons installed?, tenant Email card behaviour,
   leftover rows, anything GL-5 (a future provider) should know.

## Report back

TL;DR pass/fail · result line + start counts · thesis verdict · T196-T204
outcomes · QA screenshot table with verdicts · deviations (numbered, with
reasons) · leftover artifacts · gotcha-ledger candidates.

## Kickoff line

Implement docs/strategy/handovers/golive-studio-phaseGL4.md (Go-Live Studio
GL-4: Google + Microsoft declared flows, Calls truth card, thesis verdict).
Read docs/strategy/HANDOVER-CONVENTIONS.md first and follow its deploy/test
workflow exactly. Do not commit; report per the handover's Report back
section.
