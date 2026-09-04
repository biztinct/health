# -*- coding: utf-8 -*-
{
    'name': 'Care Command — Channel Connection Framework',
    'version': '19.0.11.2.0',
    'category': 'Healthcare/CRM',
    'summary': 'Provider-neutral channel connections + the WhatsApp / Messenger / '
               'Telegram / Web chat message spine',
    'description': """
Channel Connection Center — Phase CC-A (framework core)
=======================================================

The provider-neutral plumbing the Channel Connection Center is built on.
**Nothing user-visible changes in Care Command**: installing this module adds
two backend setup menus and nothing else. The dock, workspace and composer are
untouched.

What ships here:

- ``services/channel_crypto.py`` — AES-256-GCM secret encryption at rest with a
  dedicated subkey (token prefix ``chs$1$``), self-contained (no coupling to
  health_phi_encryption). ``decrypt()`` RAISES on corruption — a corrupted
  secret must never be handed to a provider.
- **Two credential planes**: ``channel.platform.app`` (per-deployment provider
  apps, platform-operator only) and ``care.channel.connection`` (per-company
  tenant authorizations).
- ``care.channel.oauth.session`` — single-use, hashed-state, PKCE-S256
  authorization attempts with a 10-minute expiry.
- ``care.channel.readiness.check`` — explicit readiness. A connection is NEVER
  "Ready" because a record exists; ``ready`` is derived from every check the
  channel's adapter declares as required.
- ``care.channel.audit`` — append-only ops audit, every detail string redacted.
- ``services/adapters.py`` — the adapter registry + capability contract, with
  declaration-only stubs for all 8 channel keys.
- Fail-closed public OAuth callback (``/channel_hub/oauth/callback/<provider>``)
  — rate-limited, non-oracle, never echoes state/code.
- Health + session-purge crons.

Channel Connection Center — Phase CC-B (message spine + 4 adapters)
===================================================================

The four chat channels become real rails on the SAME ``care.conversation``
spine the live channels already use:

- ``care.channel.identity`` — the external peer registry (wa_id / PSID /
  Telegram chat id / web-chat session), and the one anchor a first contact has.
- ``care.channel.message`` — one message store for all four channels, with a
  partial unique index on ``(connection_id, external_message_id)`` so a
  redelivered webhook lands once.
- ``_ingest_inbound`` — the single funnel: dedupe → identity → message row →
  conversation upsert inside ``cr.savepoint()`` → readiness wiring.
- Fail-closed raw-http webhooks for Meta (WhatsApp + Messenger) and Telegram,
  multi-tenant routed by the resource id in the payload, plus the anonymous
  web-chat widget on rate-limited public routes.
- ``action_send_channel`` — the ONE outbound trigger: a human pressing send.
- Traffic drives truth: an inbound event proves the webhook, a successful send
  proves outbound, a 401 costs the connection its ``authorization_valid``
  check — which is what the dock, the counts and the composer read.

Channel Connection Center — Phase CC-C (the Center itself)
==========================================================

The tenant-facing Center: one OWL client action with a catalogue of all eight
channels and a four-step stepper, plus the server endpoints behind it.

- ``center_overview`` / ``center_begin`` / ``center_test`` /
  ``center_disconnect`` / ``center_reconnect`` — every write through
  ``sudo()._internal()``, every failure a redacted ``UserError``, and no
  credential material in any return value.
- **Web chat is one click**: allowed website addresses, an embed snippet with
  a ``?v=`` cache stamp, and the first real widget message finishes the setup.
- **Telegram is a guided wizard**: BotFather → paste the key → validated with
  ``getMe`` before anything is stored → ``setWebhook`` (https only) → the
  tenant messages the bot → a synthetic reply proves outbound.
- Readiness stays DERIVED. Amendment F1 closes the lockout in which the first
  proving inbound demoted a ``testing`` connection to ``action_required`` —
  which is not ingestable — and stranded the channel mid-setup.
- Tenant administrators (``health_access.group_clinic_admin``) get
  connection read/write/create (never unlink), read on readiness/audit/
  identity/message, and NOTHING on ``channel.platform.app``: the platform
  plane stays with the platform operator.

Channel Connection Center — Phase CC-D (Zalo / ZNS)
===================================================

Zalo becomes the first OAuth-popup channel, and health_zalo's fail-OPEN
security boundary is replaced by the framework's fail-closed one:

- ``ZaloAdapter`` — OAuth v4 with **mandatory PKCE S256**, token exchange and
  refresh against ``oauth.zaloapp.com/v4/oa/access_token`` with the app secret
  in a ``secret_key`` HEADER, ``getoa`` for the OA identity. Zalo's refresh
  token is SINGLE USE, so every rotation runs under the connection's
  ``FOR UPDATE NOWAIT`` lock and is persisted on an independent cursor before
  anything uses it — two concurrent refreshes would burn the 3-month grant.
- ``/care_channels/zalo/webhook`` — ONE route for the deployment (Zalo's
  portal allows one URL per app), routed by ``oa_id`` and verified as
  ``sha256(app_id + raw_body + timestamp + per-OA secret)`` over the RAW
  bytes, with a replay window. Missing header, unknown OA, no secret and a
  wrong mac are all the same bodyless 200 that ingests NOTHING — Zalo's
  console refuses to save an address that answers its unsigned probe with
  anything but 200, and a 403 there made the address unsavable and therefore
  the channel unusable. Verification still gates ingestion; only the status
  code moved. The first refusal writes one ``webhook_probe`` audit row, and
  ``GET`` answers 200 so a browser check proves the address is live.
- The three legacy ``/zalo/*`` routes answer **410 Gone**.
- ``zalo.config`` is a FACADE: tokens live encrypted on the connection, the
  10-module ZNS contract keeps working verbatim, and a successful ZNS send is
  what flips the connection's ``outbound_ok`` / ``provider_approvals``.
- The Center's Zalo stepper (sign-in popup → portal-guided webhook checklist →
  say hello) and an honest ZNS sub-card: how many consumer templates are
  configured, and whether Zalo has ever accepted one.

Channel Connection Center — Phase CC-E (Meta: WhatsApp + Messenger)
====================================================================

The onboarding half of the two Meta adapters CC-B left as message rails:

- **WhatsApp — Embedded Signup v4**: the Center hands the browser the public
  app id, the ES configuration id and a single-use state; Meta's JS SDK (loaded
  ON DEMAND, never in the backend bundle) runs the popup and returns an
  authorization code, which is exchanged server-to-server for a Business
  Integration System User token that does not expire. ``debug_token`` is what
  makes the scope claim honest; a missing permission is a ``scopes_granted``
  FAIL with the plain list of what Meta withheld, never a silent half-connect.
- **Messenger — Facebook Login for Business**: the same code exchange through
  the framework's own OAuth callback, then ``/me/accounts`` for the Page picker.
  The user token is held for the picker and the chosen Page's own non-expiring
  token becomes what the composer spends.
- **Webhook registration** is ours to do: ``POST /{waba}/subscribed_apps`` for
  WhatsApp, ``POST /{page}/subscribed_apps`` (messages + postbacks) for
  Messenger. A refusal writes redacted evidence and leaves ``webhook_state``
  alone — a card that claims a subscription Meta declined is the lie the
  readiness model exists to prevent.
- **Approvals as first-class state**: business verification, display-name
  review and template review are Meta's HUMAN processes. They are read from
  Graph, cached, and rendered as plain-language pending tasks on the card.
  ``provider_approvals`` only ever moves between ``pending`` and ``pass`` —
  never ``fail``, which would strand a channel in ``action_required`` over a
  review it can still win.
- **The outbound windows reach the UI**: WhatsApp's 24 h customer-service
  window (outside it, only an approved template — ``action_send_channel``
  refuses HERE and points at ``action_send_channel_template``), and Messenger's
  24 h window with ``HUMAN_AGENT`` (7 days) as the ONLY surviving tag since
  2026-04-27. Every other Messenger tag is refused by us rather than sent and
  rejected at Meta.

**Honestly dark.** A Meta connection needs a Business-type app, Business
Verification, App Review of five permissions and two Login-for-Business
configurations — multi-week human processes (operator checklist §12.1–§12.4)
that have not started. With no ``channel.platform.app`` for provider ``meta``,
both cards read "Not available yet" and ``center_begin`` refuses. No
placeholder credential is seeded anywhere.

Channel Connection Center — Phase CC-F (Email + Calls): the catalogue closes
=============================================================================

The last two cards, and they are honest in deliberately DIFFERENT ways.

**Email is a real build, orchestrating Odoo's own OAuth.** ``google_gmail``
and ``microsoft_outlook`` already ship working XOAUTH2 mixins that mint the
consent URL, run a CSRF-checked callback, store the refresh token and renew
the access token before every SMTP and IMAP login. CC-F takes the *boundary*,
not the protocol: which platform app, which mailbox, what is proven, what the
tenant sees. Re-implementing the token dance on our own engine would only add
a second, weaker door to the same mailbox.

- A THIRD credential plane exists and is now resolved explicitly: the mixins
  read their client id/secret from ``ir.config_parameter``. The
  ``channel.platform.app`` row stays the operator-facing truth and is mirrored
  INTO those keys, one way, never back — two writable sources of one secret is
  how they drift apart.
- The connection owns an ``ir.mail_server`` (SMTP) and a ``fetchmail.server``
  (IMAP) through a plain Many2one, and that ownership is load-bearing:
  ``_find_mail_server_allowed_domain`` excludes channel-owned servers from the
  default-sender search, so a clinic's mailbox can never become the sender of
  every other email the database emits.
- ``inbound_ok`` **latches** (ledger §5.78). Inbound is an IMAP poll, so a
  quiet mailbox or one failed fetch must never lower it — that would demote a
  live connection to ``action_required``, which is not ingestable.
- Email chat storage stays exactly where it was: ``mail.message`` and core
  ``action_send_email``. No ``care.channel.message`` rows, no core edits.

**Calls is receive-only, and the card says so in words.** VoIP24h's
documentation is unreachable from outside Vietnam (``docs.voip24h.vn`` answers
ECONNREFUSED), no third party documents their API, and every path in
``services/voip24h_api.py`` is a conventional REST shape with no evidence
behind it. So this phase calls NOTHING of theirs:

- their existing ``/voip24h/webhook`` is ADOPTED, not rewritten — it was
  already the fail-closed posture the rest of the framework was told to clone
  (raw bytes, HMAC-SHA256, ``compare_digest``, generic 200 for an unknown
  account). CC-F adds routing: resolve the connection, honour its ingest gate,
  let real traffic prove the channel. No new public route.
- ``voip.config`` becomes a facade like CC-D's ``zalo.config``: the webhook
  secret is read from the encrypted connection first, the three plaintext
  secrets are encrypt-copied by an idempotent migration, and nothing is
  deleted. A config the Center creates leaves ``api_key``/``api_secret``
  EMPTY on purpose — ``_check_credentials`` then refuses to build an API
  client, which is what keeps every unverified endpoint unreachable.
- ``required_checks`` for calls is ``webhook_verified`` + ``inbound_ok`` and
  nothing else: a check that would need an API round trip to satisfy cannot
  be asked of a tenant when we have no way to test it.
- ``docs/strategy/voip24h-contract-capture.md`` lists exactly what a human on
  a Vietnamese connection must capture before outbound calling or CDR sync
  could be built at all.

Non-goals of this phase: no new VoIP24h HTTP call and no edit to any path in
``voip24h_api.py``; no Instagram; no new public route; no edits to
health_care_command or to the google_gmail / microsoft_outlook core addons; no
placeholder credentials; no change to the 10-module ZNS contract; no real
provider call anywhere in the tests.

Channel Connection Center — Phase CC-G (platform go-live console)
==================================================================

The four Meta/Zalo/Google/Microsoft cards are software-complete and honestly
dark. What was left is the operator's half, and it had two holes:

- **A row is not a configuration.** The card gate counted ``channel.platform.
  app`` rows, so the moment an operator created an empty ``meta`` row to start
  filling it in, WhatsApp AND Messenger went "available" and every Connect
  could only fail. ``BaseChannelAdapter.platform_ready()`` now answers that
  question where the knowledge already lived: client id, stored secret, and
  the ``required_platform_keys`` each adapter refuses without (the Embedded
  Signup / Login-for-Business configuration ids, and the webhook verify token
  without which Meta's handshake 403s). Email delegates to its own
  ``available_providers()``, which also demands Odoo's mixin addon. The gate
  may only ever TIGHTEN: a complete row lights the same cards it always did.
- **The go-live paperwork was a markdown checklist.** A "Go live" tab on the
  platform application now shows the redirect URI and webhook URLs this
  deployment actually answers on (per provider — Gmail/Outlook sign in
  through Odoo's own mixins, so their redirect URI is core's, not ours),
  a per-requirement checklist of what is still missing, and the external
  steps that stay human paperwork. A generator mints the Meta webhook verify
  token (merged into ``extra_json``, never clobbering a sibling key, and
  never regenerated silently while Meta's dashboard holds the old one).

**Preflight is honest about its own limits.** "Check this application" runs
Meta's documented app-access-token call and reads the app's own name back —
the only credentials-only check any of the four providers documents. Zalo,
Google and Microsoft return ``unverifiable`` with the reason in words rather
than a trick built on an undocumented error body. A provider refusal is an
answer, not an exception: the outcome is persisted and reported, the button
never raises, the app token is used and discarded, and no secret reaches a
checklist row, a stored detail, an audit row or a log line. Manual only —
no cron ships.

Go-Live Studio — Phase GL-1 (server framework)
===============================================

CC-G's go-live checklist knew what was missing; it could not tell the operator
what to *do*. GL-1 turns the same knowledge into an ordered, translatable
declaration — seven steps for Meta, five for Zalo — each one saying what to do,
where to do it, what to copy out of Health19, what to type back in, roughly how
long it takes, and how we will know it happened.

- ``_golive_steps()`` is the declaration and ``golive_state()`` is the truth.
  A step is ``done`` because the artifact exists — a client id, a stored
  secret, a preflight Meta accepted, a webhook handshake that reached us, a
  configuration id — never because somebody ticked it. Only the steps we
  cannot observe (Business Verification, App Review) are markable, and they
  read ``waiting``, not ``done``.
- ``golive_submit()`` routes every write through the path that already owns
  it: ``action_set_secret`` for the secret, a merge for ``extra_json``,
  ``action_generate_verify_token`` for the token. No second door, and no
  credential material in any return value.
- The webhook handshake is now **evidence**: Meta's dashboard check and the
  first verified Zalo event each write one ``webhook_handshake`` audit row,
  on the success path only, with the routes' bytes and status untouched.

No UI (GL-2), no invitations (GL-3), no Google/Microsoft steps (GL-4).

Go-Live Studio — Phase GL-2 (the Studio itself)
===============================================

The console GL-1's declaration was written for: one full-screen OWL client
action (``channel_golive_studio``), operator-only, with a journey map at home
and a milestone flow per provider.

- **The home screen is a map, not a list.** One card per provider with a
  progress ring over the steps that are really done, the channels it unlocks as
  chips (green only where ``platform_ready`` says so), the honest time estimate
  derived from the declared provider-review waits, and the prerequisites you
  need before you start. A card works with no platform application at all —
  that IS step one.
- **The flow is a rail plus a canvas.** Every step's canvas carries the server's
  own words, a stylised flat-mono DIAGRAM of the console screen it is about (no
  logo, no wordmark, no trade dress — a caption carries the orientation), a deep
  link to the exact page of the provider console, copy chips for every value we
  generate, and paste-back fields that mirror the server's regex so the
  DECLARED explanation appears before a round trip and the identical one after.
- **The proof moments are live.** Storing the Meta secret runs the preflight and
  the canvas answers with the app's real name, or with Meta's refusal in words
  and a "Check again". On a webhook step the Studio polls every five seconds —
  visible tab only, one interval, only while that step is open — and the
  milestone flashes green the moment the provider's check reaches us.
- **A non-operator gets a sentence, not a stack trace.** The refusal card names
  whose console this is; the tenant Channel Center's new operator strip is
  absent for everyone whose probe did not succeed, so that view is byte-identical
  to what CC-G shipped for every clinic.

Entry points: the CMS sidebar's ADMIN section (the surface these users actually
have), a ``base.group_system`` menu item under Care Command Setup, a header
button on the raw platform-application form, and the Center strip.

No invitations (GL-3), no Google/Microsoft/VoIP24h flows (GL-4), and no change
to any GL-1 payload.

Go-Live Studio — Phase GL-3 (delegation)
========================================

The person who can open Meta's App Dashboard is very often not the person with
a Health19 login. GL-3 is the Zoho move: send ONE step to whoever has the
console, as a tokenized page they open logged out.

- ``channel.golive.invite`` stores ``sha256(token)`` and never the token. The
  plaintext exists inside ``golive_invite_send`` for exactly as long as it takes
  to build the URL and render the email body — it is in no return value, no
  audit row and no log line, so a database backup contains no usable link.
  Invitations are revoked, never deleted (``perm_unlink`` 0): a link that was
  handed out is evidence.
- A re-send is a **rotation**. Any live invitation for the same provider and
  step is revoked first, so exactly one link can ever open a given step.
- ``/channels/golive/<token>`` is the module's only unauthenticated read
  surface, and it is a **non-oracle**: an unknown token, a revoked invitation,
  an expired one and an archived platform application all render the same bytes
  with the same 200 status. It is rate-limited per IP before the database is
  touched, sets no cookie, is ``noindex`` and ``no-referrer`` (the token is in
  the path, so the deep link into the provider console must not carry it in a
  ``Referer``), and contains no input element of any kind.
- The page shows the step's own words, the console deep link and the values
  Health19 publishes anyway — our redirect address, our webhook addresses, the
  verify token both sides must hold identically. **Never a secret**, and never
  a write: where the verify token has not been minted yet, the page says so
  rather than minting one, because a public route must not be able to change
  what Meta already holds.
- The email is built in Python from a QWeb view, not a ``mail.template`` record
  (Odoo renders every template at INSTALL, and one that cannot render blocks the
  module). If it cannot be sent, the invitation is revoked on the spot and the
  operator is told to fix the outgoing mail server — a link nobody received is
  a link only a guesser can find.

No Google/Microsoft/VoIP24h flows (GL-4), no change to any GL-1 payload (the
``invites`` key is additive), and no tenant-facing change.

Go-Live Studio — Phase GL-4 (Google, Microsoft, and the truth about Calls)
==========================================================================

The last two provider journeys, and the proof of GL-1's promise: adding a
provider is **declarations only**. Google and Microsoft are different from Meta
in three ways at once — their sign-in runs on Odoo's own Gmail/Outlook mixins
rather than on our OAuth engine, they have no webhook at all, and neither
publishes a credentials-only check — and none of those differences needed a new
status branch, a new model, a new endpoint or a new UI component.

- **Five declared steps each**, in the same voice as Meta's and Zalo's. Google:
  create the OAuth client, store the secret, add the redirect address, publish
  the consent screen (a wait — an unpublished screen expires every mailbox
  after 7 days, which reaches the clinics as random sign-outs), done.
  Microsoft: register the application, add the redirect address, grant the four
  Graph permissions with admin consent, create the client secret — copy the
  **Value** column, never the Secret ID — done.
- **`store_secret` verifies `manual`, deliberately.** ``action_preflight`` is
  Meta-only; every other provider answers ``unverifiable``. A step declared
  ``preflight`` here would sit at "to do" forever, so the honest declaration is
  the one that says what is true: these credentials are proven the first time a
  clinic connects a mailbox.
- **The console links are static.** Google's console does not key on the client
  id in any stable public URL, and an Entra deep link needs the app's *object*
  id, which we never hold — a templated link would 404 in the operator's face.
- **One provider is enough.** The Email card lights when EITHER a google or a
  microsoft application is complete (plus Odoo's own addon), and both cards say
  so rather than implying two go-lives.
- **Calls gets a truth card, not a flow.** ``CallAdapter`` needs no platform
  application: the channel is receive-only, proven by inbound traffic, and
  VoIP24h's API contract is still uncaptured. There is no operator paperwork to
  guide, so the Studio home carries one static card saying exactly that —
  and ``_golive_step('call', …)`` still raises.

``PROVIDER_EXTERNAL_STEPS`` is now empty: every provider's paperwork is
declared exactly once. The constant and its fallback stay for the provider that
arrives with a checklist before it has a flow.
    """,
    'author': 'I Am Dream Catcher Ltd',
    'website': 'https://vafhs.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'web',
        'mail',
        'health_care_command',
        'health_api_gateway',
        # Channel attribution (client requirement 3): connections carry
        # utm.source / utm.medium / utm.campaign defaults. Already transitive
        # (health_crm depends on utm), declared because the reference is hard.
        'utm',
        # CC-C: the Center's audience. The tenant-admin ACL rows and the
        # Center menu both reference health_access.group_clinic_admin,
        # so the dependency is hard from this phase on (CC-A deferred it).
        'health_access',
        # CC-C: the CMS shell is where these users actually are, and the
        # backend menuitem alone is unreachable from it (see the sidebar seed).
        'health_cms_sidebar',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/channel_hub_security.xml',
        'views/oauth_templates.xml',
        'views/webchat_templates.xml',
        # GL-3: the public delegation page + the invitation email body.
        'views/golive_invite_templates.xml',
        # GL-2: BEFORE platform_app_views.xml — that form's header button
        # references this action with %(...)d, resolved as the view loads.
        'views/golive_studio_views.xml',
        'views/platform_app_views.xml',
        'views/channel_connection_views.xml',
        'views/channel_message_views.xml',
        'views/contact_capture_views.xml',
        'views/res_config_settings_views.xml',
        'views/channel_center_views.xml',
        'views/menus.xml',
        'data/ir_cron.xml',
        'data/cms_sidebar_items_channel_center.xml',
        'data/cms_sidebar_items_contact_capture.xml',
        'data/cms_sidebar_items_golive.xml',
    ],
    'assets': {
        'web.assets_backend': [
            # plain CSS first (data-URI mask icons — libsass mangles them
            # inside .scss, ledger §5.51)
            'health_care_command_channels/static/src/center/channel_center.css',
            'health_care_command_channels/static/src/center/channel_center.scss',
            'health_care_command_channels/static/src/center/channel_center.js',
            'health_care_command_channels/static/src/center/channel_center.xml',
            # GL-2 — the Go-Live Studio. Same ordering rule: the plain CSS with
            # the data-URI mask icons FIRST, the scss after it.
            'health_care_command_channels/static/src/golive/golive_studio.css',
            'health_care_command_channels/static/src/golive/golive_studio.scss',
            'health_care_command_channels/static/src/golive/golive_studio.js',
            'health_care_command_channels/static/src/golive/golive_studio.xml',
        ],
        'web.assets_tests': [
            'health_care_command_channels/static/tests/tours/**/*',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'auto_install': False,
    'application': False,
    'sequence': 126,
}
