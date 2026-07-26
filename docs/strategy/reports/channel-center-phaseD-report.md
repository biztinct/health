# Channel Center CC-D — Implementation Report

**Phase:** Channel Connection Center, Phase CC-D (Zalo / ZNS onto the framework)
**Handover:** `docs/strategy/handovers/channel-center-phaseD.md`
**Implemented by:** Opus 5 · **Date:** 2026-07-26 · **Target:** vietuat
**Modules:** `health_care_command_channels` 19.0.3.0.0 → **19.0.4.0.0**,
`health_zalo` 19.0.1.0.0 → **19.0.2.0.0**

---

## 0. Read this first — the handover's dependency edge is unbuildable

§2.2 of the handover says: *"health_zalo `__manifest__.py` depends do NOT
include the channels module — CC-D adds `health_care_command_channels` to
them."*

That edge **closes a loop**, and the first deploy proved it:

```
health_zalo → health_care_command_channels → health_care_command → health_zalo
                                             (manifest line 42, pre-existing)

odoo.modules.module_graph: module health_zalo: in a dependency loop, skipped
odoo.modules.module_graph: module health_care_command_channels: its
                           direct/indirect dependency is skipped, skipped
odoo.modules.loading: Some modules have inconsistent states … (20 modules)
```

`health_care_command` has depended on `health_zalo` since it shipped — it
`_inherit`s `zalo.message` (hooks.py:27) and anchors on `zalo.conversation`.
The whole graph was skipped and nothing loaded.

**The coupling is SOFT in both directions instead** (deviation D1). Everything
else in the handover survives; the consequences are D1–D3 below, and they are
the only structural deviations in the phase.

---

## 1. What was built

```
health_care_command_channels/                        (→ 19.0.4.0.0)
├── services/
│   ├── adapters.py               +  ZaloAdapter FOR REAL: authorize_url (v4 +
│   │                                PKCE S256), handle_callback (secret_key
│   │                                header + code_verifier, getoa),
│   │                                refresh_authorization (locked, rotating),
│   │                                health_check, _form_post, _is_auth_failure
│   └── webhook_verify.py         +  verify_zalo — sha256(app_id + raw_body +
│                                    timestamp + per-OA secret) over the RAW
│                                    bytes, replay window, fail-closed
├── controllers/zalo.py           NEW /care_channels/zalo/webhook — ONE route
│                                    per deployment, routed by oa_id
├── models/
│   ├── channel_center.py         +  center_zalo_authorize / center_zalo_info /
│   │                                center_zalo_set_webhook_secret,
│   │                                _center_test_zalo, _center_zns_status,
│   │                                real zalo + zns guide copy, 'zalo' in
│   │                                CENTER_IMPLEMENTED_CHANNELS, oauth_popup
│   │                                in IMPLEMENTED_MODES
│   └── care_channel_message.py   +  _dispatch_zalo — verified event → the
│                                    LEGACY zalo.message pipeline + traffic-truth
├── static/src/center/            +  sign-in popup (blocked-popup fallback),
│                                    portal-guided webhook checklist, honest
│                                    ZNS sub-card lines
├── migrations/19.0.4.0.0/post-migrate.py   NEW  (D2 — see below)
├── hooks.py                      NEW  post_init twin of the migration
├── i18n/vi.po                    +  27 entries (15 python, 12 web)
├── tests/
│   ├── test_zalo_center.py       NEW  T108–T112, T119–T122
│   ├── test_center.py            ~    T104 relaxed to a baseline (forced, D5)
│   └── common.py                 ~    fixtures free the connection slot (D5)
└── __manifest__.py               +  19.0.4.0.0, post_init_hook, CC-D description

health_zalo/                                          (→ 19.0.2.0.0)
├── models/zalo_config.py         ~  FACADE (_effective_access_token /
│                                    _effective_refresh_token / _effective_
│                                    expires_at / _channel_connection),
│                                    app_secret UNTRACKED (Z1), api_base_url
│                                    write-guard (Z5), legacy OAuth + webhook
│                                    buttons retired (Z6/Z9), locked refresh,
│                                    _sync_from_connection,
│                                    _migrate_legacy_connections,
│                                    _drop_app_secret_tracking
├── services/zalo_api.py          ~  correct token endpoint + secret_key HEADER
│                                    (Z8), facade reads, ZNS traffic-truth
├── services/message_handler.py   +  _ingest_verified_event (sync + dedupe, Z7),
│                                    msg_id carried into the three builders
├── controllers/webhook.py        ~  the three routes are 410 shims (Z2/Z3/Z6)
├── models/res_partner.py         ~  demo-config auto-create deleted (Z9),
│                                    action_link_zalo_user deleted (Z9)
├── models/crm_lead.py            ~  demo-config auto-create deleted (Z9)
├── security/zalo_security.xml    +  4 GLOBAL company ir.rules (Z4)
├── views/                        ~  retired buttons removed, api_base_url
│                                    readonly, "connect from the Center" banner
├── i18n/vi_VN.po                 ~  42 §5.58 markers added + 4 new entries
└── tests/test_zalo_cc_d.py       NEW  T113–T118, T123–T124
```

### What actually changes for a user

Nothing yet, and that is honest. On vietuat the Zalo card reads **"Not
available yet"** because no `channel.platform.app` for the provider is seeded —
operator checklist item §12.5, a real app at developers.zalo.me. What DID
change is the security floor underneath it, which was load-bearing and broken:

| before | after |
|---|---|
| `/zalo/webhook` accepted forged events three ways (no config / no secret / no header) and hashed re-serialised JSON | one raw-bytes, fail-closed route; every refusal an identical bodyless 403 |
| every inbound event silently dropped (`with_delay` with no queue_job, `AttributeError` swallowed, 200 returned) | ingested synchronously, deduped on `msg_id` |
| `app_secret` copied verbatim into `mail.tracking.value` on every write | untracked, and the rows that already leaked are deleted |
| no `ir.rule` anywhere — cross-company read of every config, conversation and message | 4 global company rules |
| `api_base_url` writable by any Zalo Manager (token-exfil on the next refresh) | system-administrator only |
| a "Demo Zalo Config (Testing)" with `app_secret='demo'` auto-created on a button press | an honest refusal that points at the Center |
| OAuth with no PKCE, an immortal unbound state, a permanently stored code | the framework's hashed, single-use, 10-minute PKCE-S256 sessions |
| token endpoints that could never have worked (wrong host, secret in the body or absent) | `oauth.zaloapp.com/v4/oa/access_token` with the secret in a header |

---

## 2. Deviations from the handover (all declared)

| # | Handover said | Shipped | Why |
|---|---|---|---|
| **D1** | health_zalo gains a `health_care_command_channels` dependency | **no dependency edge at all**; soft coupling both ways (`'care.channel.connection' in self.env` / `'zalo.config' in env`) | §0 — the edge closes a loop and the module graph is skipped. Verified live, not reasoned about. |
| **D2** | migration runs in health_zalo (post_init or `migrations/<v>/post-migrate.py`) | migration **method** lives on `zalo.config`; the **trigger** lives in `health_care_command_channels` (`migrations/19.0.4.0.0/post-migrate.py` + `post_init_hook`) | Forced by D1's load order. health_zalo loads BEFORE the framework (health_care_command sits between them), so a script over there would run with `care.channel.connection` not yet in the registry. By the time the framework's post-migrate runs, both sides exist. |
| **D3** | `zalo.config` gains `connection_id` (Many2one) | **no new column**; the join key is `(channel='zalo', company_id)` | A Many2one from health_zalo to a later-loaded module cannot be built: Odoo runs an incremental `_setup_models__` after every module it loads (loading.py:185), and the comodel does not exist yet. The key used instead is the framework's OWN uniqueness key — the partial unique index on `(channel, company_id) WHERE active` guarantees it resolves to at most one row. |
| **D4** | refresh mirrors the new access token into the legacy plaintext columns "so old code paths that read `config.access_token` directly stay correct" | **no mirror**; every read goes through the facade | Grep-verified: there is not one reader of `config.access_token` / `.refresh_token` outside the files this phase already edits, so the mirror bought nothing and cost a plaintext token at rest — the exact hygiene problem CC-D exists to fix. All internal readers now call `_effective_access_token()`. |
| **D5** | (not in the sanction list) | `tests/common.py` archives pre-existing connections in `setUpClass`; `test_center.py` T104's two absolute counts are now baseline-relative | **Forced.** The migration lands a live `legacy` zalo connection on every real database. The partial unique index then made `self._conn('zalo')` raise in 7 CC-A tests, and T104's "no rows exist" read a row it never created. The engine is right and the fixtures were naïve — ledger §5.62's family exactly. |
| **D6** | `authorize_url(session)` | `authorize_url(session, state, code_challenge)` | The raw state exists exactly once, in `create_for`'s return value (the row stores only its sha256), so it cannot be recovered from the session record — which is the point of hashing it. Passing it in beats un-hashing it. |
| **D7** | `center_test` for zalo replies "via the EXISTING ops send path" | writes the same `zalo.message` row and calls the same `action_send_message()`, but does NOT route through `care.conversation.action_send_zalo` | That method gates on `health_crm.group_health_crm_user`. Two of the Center's three personas — a platform operator and a tenant administrator — are not in it, so the test button would have refused the very people the Center is for. The rails, the row and the send are identical; only the group gate is not re-imposed. |
| **D8** | (addition) | `services/message_handler.py` carries `msg_id` into its three `message_data` builders | Z7 (dedupe) is impossible without it: the legacy handler never populated `zalo_message_id` at all, so "the same message twice" was undetectable. Three lines, one per builder. |
| **D9** | (addition) | `center_zalo_info(conn_id)` | The webhook step has to show the URL to paste and whether a secret is already stored, on first setup AND on re-entry. The alternative was making the browser reconstruct the URL. |
| **D10** | (addition, forced) | health_zalo's `i18n/vi_VN.po` gains 42 `#. odoo-python` markers | Ledger §5.58 says "fix module by module on next touch". Its 129 entries had correct `#:` occurrences and no code markers, so the whole catalogue was inert. Now 46 python + 17 web translations load where 0 did. |

**Not done, and why:** the ZNS `provider_approvals` check has no attestation
button, as specified — it flips only when Zalo actually accepts a send.

---

## 3. Z1–Z9: what closed, and how it closed

| # | Defect | Closed by | Proof |
|---|---|---|---|
| Z1 | `app_secret` tracked → plaintext into `mail.tracking.value` | `tracking=True` removed + one-time cleanup of the rows that already leaked | T117; live: 0 tracking rows, `field.tracking is False` |
| Z2 | webhook fails OPEN three ways, wrong hash formula, jsonrpc route | **replaced**, not patched: new raw-`http` fail-closed route; the old one is a 410 | T112 refusal matrix, T121 route shape, live curls (7 refusal classes, all bodyless 403) |
| Z3 | `with_delay()` → every event silently dropped while returning 200 | synchronous ingest through `_ingest_verified_event` | T113 (one row lands), T114 (`with_delay` absent from every handler) |
| Z4 | no `ir.rule` anywhere | 4 global company rules | T118; live "Access Denied by record rules … model: zalo.config" |
| Z5 | `api_base_url` writable by a Zalo Manager → token exfil | model write-guard (system only) + readonly in the view | T118 |
| Z6 | OAuth with no PKCE, immortal unbound state, stored code | **retired**: entry points raise and point at the Center; the framework's session engine is the only flow | T123, live 410 on `/zalo/oauth/callback` |
| Z7 | no inbound dedupe on `zalo_message_id` | pre-check (not a unique index — live duplicates may exist and an index firing inside a webhook poisons the transaction) | T113: same `msg_id` twice → one row |
| Z8 | token endpoints wrong (host, header) | `oauth.zaloapp.com/v4/oa/access_token`, `secret_key` header, form body | T109 asserts the URL, the header and `code_verifier`; T111 the same for refresh |
| Z9 | demo-config auto-create, broken wizard button, TODO webhook buttons | all three deleted/retired | T123 |

---

## 4. Test results (verbatim, vietuat, final run)

```
2026-07-26 01:20:07,477 INFO vietuat odoo.tests.stats: health_care_command_channels: 81 tests 16.11s 14275 queries
2026-07-26 01:20:07,477 INFO vietuat odoo.tests.stats: health_zalo: 10 tests 2.26s 1965 queries
2026-07-26 01:20:07,477 INFO vietuat odoo.tests.result: 0 failed, 0 error(s) of 75 tests when loading database 'vietuat'
EXIT:0   HTTP:200
```

Regression on the untouched Care Command family:

```
2026-07-26 01:24:35,419 INFO vietuat odoo.tests.stats: health_care_command: 38 tests 7.64s 6512 queries
2026-07-26 01:24:35,419 INFO vietuat odoo.tests.stats: health_care_command_ai: 8 tests 1.69s 1522 queries
2026-07-26 01:24:35,419 INFO vietuat odoo.tests.stats: health_care_command_voip: 6 tests 0.50s 397 queries
2026-07-26 01:24:35,419 INFO vietuat odoo.tests.result: 0 failed, 0 error(s) of 46 tests when loading database 'vietuat'
EXIT:0   HTTP:200
```

91 test methods in the two changed modules (CC-A 20 + CC-B 26 + CC-C 12 +
**CC-D 17**). TransactionCase only, **zero HttpCase** (§5.32), zero real HTTP,
zero credentials.

| test | what it proves |
|---|---|
| T108 | authorize URL: `S256(verifier) == challenge`, state present, app_id from the platform app, verifier absent, **no secret material and no `secret_key` anywhere in the URL**; no platform app ⇒ refuse |
| T109 | callback happy path: `secret_key` HEADER + `code_verifier` asserted on the mocked form POST, correct URL, tokens land as `chs$1$` ciphertext with the plaintext absent from the column, getoa → resource fields, three checks pass, state `configuring`, and **no token or state in the engine's return** |
| T110 | refusals: exchange 4xx ⇒ nothing stored (no credentials, no resource, no readiness row, state unmoved) and getoa never called; a replayed state is indistinguishable from an unknown one; denied ⇒ `denied` with no exchange; a zalo state answered on meta's callback ⇒ generic |
| T111 | rotation: the NEW refresh token is persisted; a network wobble leaves the old token intact AND `token_fresh` at pass; a provider refusal leaves the old token intact and costs `token_fresh` + a `refresh_fail` audit row; `_with_refresh_lock` runs the callable uncontended |
| T112 | `verify_zalo` golden vector (computed in the test the way the spec words it) + 9 refusal classes: no signature, no timestamp, no headers, wrong mac, one extra body byte, an hour-old replay, unknown OA, a connection with no secret, no platform app |
| T113 | inbound: a verified event becomes ONE `zalo.message` on the legacy rails, `_note_inbound` proves the webhook, and the same `msg_id` twice is still one row |
| T114 | the three legacy routes are `http`/public 410 shims and no handler retains `with_delay`, the fail-open verifier or the old processing call |
| T115 | the frozen contract: `get_api_client`, the active-config search and `send_zns_notification`'s exact signature; the facade reads the connection over the plaintext column and falls back where there is no connection; a ZNS send Zalo accepted flips `provider_approvals` + `outbound_ok`; a 401 costs `authorization_valid` and still raises what the consumers catch |
| T116 | migration: an existing connection is linked, never duplicated; plaintext tokens are encrypt-copied (`chs$1$`) and the legacy columns are left in place; a re-run creates and copies nothing; a company with no connection gets exactly one, in `legacy`, with no invented credentials |
| T117 | Z1: `app_secret` untracked, and a write creates no `mail.tracking.value` (flushed through `cr.precommit.run()` — §5.56, or it passes for the wrong reason) |
| T118 | Z4/Z5: another company's Zalo Manager cannot see or read the config; a Zalo Manager cannot repoint `api_base_url`; a system administrator still can |
| T119 | the Center arc: catalogue → `center_begin` → authorize URL → mocked callback → `configuring` → webhook secret stored as ciphertext with `webhook_verified` still pending → first inbound keeps it in `testing` (amendment F1) → `outbound_ok` derives `ready`; ZNS sub-card honesty; `center_begin('zns')` still refused |
| T120 | spoof: cross-company `conn_id` refused on all four new endpoints; a plain CRM user refused; nothing moved, no credential landed, no session created |
| T121 | the webhook route is `http`/POST/public/no-csrf/no-session, and the routing-key parser never trusts anything but `oa_id` |
| T122 | a non-ingestable zalo connection drops the traffic with a `webhook_ignored` audit and does NOT record it as proof of life |
| T123 | Z6/Z9: the four retired entry points raise; neither call site manufactures a fake config; the broken button is gone; no demo config exists on this database |
| T124 | the post-sign-in bridge sets `state='connected'` (without which the legacy pipeline cannot resolve a config at all) and copies no credential downward |

### Three genuine defects the red runs caught, all fixed

1. **The dependency loop** (§0) — the whole graph skipped, nothing loaded.
2. **Live data vs. naïve fixtures** (D5) — the migration's own `legacy` row
   broke 7 CC-A/CC-C tests that assumed an empty table.
3. **Two source-grep assertions matched their own prose.** T114 and T123
   grepped the whole module for `with_delay` / `Demo Zalo Config` — and hit the
   comments explaining that those things had been removed. Now they read the
   individual handlers and the fake row's fingerprint (`'app_secret': 'demo'`)
   instead. Worth carrying: **a source-grep assertion must target the code, not
   the file — comments about a defect look exactly like the defect.**

---

## 5. Data honesty on vietuat

Full transcript: `docs/strategy/reports/channel-center-phaseD-evidence/`.

- **Zalo and ZNS do not work on vietuat and will not until a human completes
  the new sign-in with real OA credentials.** They did not work before this
  phase either: the one `zalo.config` (id=3) is active with an `app_id` and an
  `oa_id` and **no access token and no refresh token**. Nothing in CC-D
  changes that, and nothing in it pretends otherwise.
- The migration produced **exactly one** connection: id=1207, `zalo`,
  `state='legacy'`, `resource='o'` (the config's real `oa_id` on this server —
  a single character, not normalised or "fixed"), `has_credentials=False`.
  There were no tokens to copy, so none were.
- **0 `channel.platform.app` rows.** The Zalo card therefore reads "Not
  available yet — Health19 is completing provider approval", which is exactly
  true: operator checklist item §12.5 is outstanding.
- 0 readiness checks, 0 identities, 0 `care.channel.message`, 0
  `zalo.message`, 0 `zalo.conversation`. 26 `care.channel.audit` rows
  (append-only with `ondelete='set null'` — designed, not residue).
- `_channel_keys()` still returns `('zalo', 'call', 'email', 'zns')`: the dock
  is untouched by this phase.
- **0 of 12** consumer-module ZNS templates are configured on this server. The
  sub-card says so, in both languages, rather than rounding it to "ready".
- No QA fixture was created at any point — the NOWAIT smoke ran against the
  existing migrated row and rolled back, so there was nothing to clean up
  (§5.34 satisfied by not needing it).
- No pip install. No PWA involvement (backend assets only), so no version bump.
- `web.base.url` is `https://care.biztinct.com`, unchanged.

### Browser evidence — **not done, by your decision**

The DoD's browser pack is absent and the phase is being reported that way. Two
facts made it unobtainable rather than skipped:

1. no login for care.biztinct.com was available in this session;
2. even with one, the Zalo stepper cannot be driven, because the card
   correctly refuses to offer a Connect button with no platform app. Seeding a
   placeholder app to make the screen appear would have manufactured exactly
   the class of fake credential row this phase deleted from health_zalo
   (defect Z9).

You were asked and chose to ship on server-side evidence. What stands in its
place is in the evidence directory: the live 403/410 curl matrix, the live
two-worker lock contention, the migration proof, the catalogue **as the real
`crm` user's own RPC returns it**, and the Vietnamese runtime spot-checks.
When a Zalo app is seeded, the stepper deserves a browser pass before anyone
calls it done.

---

## 6. The CC-A deferred rider — closed

Two `odoo-bin shell` processes, four seconds apart, on the migrated connection:

```
===== SHELL B (the contender) =====
B: result='locked'
INFO vietuat …care_channel_connection: Channel connection 1207 already locked for refresh

===== SHELL A (the holder) =====
A: LOCK HELD, sleeping 10s
A: result='ran'
A: rolled back, nothing written
```

The holder ran; the contender did not wait, did not raise and did not
refresh. Under two workers exactly one rotation happens and the loser is a
no-op — which is the whole reason the lock exists, because Zalo's refresh
token is single use and a second concurrent exchange burns the 3-month grant.
Full method in `evidence/nowait-contention-smoke.txt` (ledger §5.63 explains
why this could never have been a test).

---

## 7. New gotchas for the ledger (§5)

> **§5.71 — a manifest dependency you are told to add may close a loop that is
> invisible from either end.** CC-D's handover specified
> `health_zalo → health_care_command_channels`. The loop is three hops long
> (`… → health_care_command → health_zalo`) and health_care_command's
> dependency on health_zalo is old, undocumented in the channel architecture,
> and load-bearing (`_inherit = 'zalo.message'`). The symptom is not an error
> at the new edge: `module_graph` logs `module <X>: in a dependency loop,
> skipped`, then `its direct/indirect dependency is skipped, skipped` for
> everything downstream, and the run finishes **EXIT:0 with "0 failed, 0
> error(s) of 0 tests"** — a green line that means nothing ran. Before adding
> any dependency edge, walk the target's own `depends` transitively; and treat
> "0 of 0 tests" as a failure signal, never as a pass. Corollaries, both hit in
> the same fix: (a) a **Many2one cannot point at a model from a
> later-loaded module** — Odoo runs an incremental `_setup_models__` after each
> module it loads (`odoo/modules/loading.py:185`), so the comodel must already
> exist; where the modules cannot be ordered, join on the target's own
> uniqueness key instead of an FK; (b) a **migration script belongs in the
> module that loads LAST**, not in the module that owns the data — health_zalo
> could not migrate its own rows because the framework models it migrates them
> into were not in the registry yet.

> **§5.72 — a source-grep test assertion matches the comment that explains the
> defect was removed.** Both of CC-D's "the old hazard is gone" tests failed on
> their first run against correct code: `assertNotIn('with_delay', source)` hit
> the shim's own docstring explaining why `with_delay` was removed, and
> `assertNotIn('Demo Zalo Config', source)` hit the comment describing the fake
> row that had just been deleted. Grep the *callable* (`inspect.getsource(cls.method)`),
> not the module, and assert on a fingerprint that cannot appear in prose — the
> literal `"'app_secret': 'demo'"` rather than the human-readable name of the
> thing. Same family as ledger §31's "grep cannot see block comments": a text
> search over source proves something about the text, not about the program.

> **§5.73 — the one place a webhook must parse before it verifies, and how to
> keep that safe.** Zalo's developer portal allows exactly ONE webhook URL per
> app, so every tenant OA arrives at the same route and the per-OA secret to
> check the signature against is not known until the payload has been read.
> The safe ordering is: read the RAW bytes → `json.loads` **only** to lift the
> routing key (`oa_id`, falling back to `recipient.id`) → resolve the
> connection → verify over the RAW bytes with that connection's secret → only
> then decode and ingest. Nothing else in the body may be touched before the
> verification, the routing key must never reach a log or a response, and every
> refusal (missing header, missing timestamp, unknown OA, connection with no
> secret, wrong mac, unparsable body) must be the same bodyless 403 — otherwise
> the route becomes an oracle for "which Official Accounts live here". Verified
> live: seven distinct refusal classes, all `HTTP 403, 0 bytes`.

---

## 8. Deferred / next

- **A Zalo platform app is the only thing standing between this code and a
  working channel** (operator checklist §12.5: an app at developers.zalo.me
  with the OA API product, the callback URL
  `https://care.biztinct.com/channel_hub/oauth/callback/zalo` registered, the
  webhook URL `https://care.biztinct.com/care_channels/zalo/webhook` set on the
  app page, and app review to Live). Seed it with
  `channel.platform.app.action_set_secret`, then the card offers Connect.
- **The Zalo stepper has never been driven in a browser** (§5). It should be,
  once an app exists.
- **The replay window is 5 minutes**, widenable through
  `channel_hub.zalo_webhook_skew_seconds` without a code change. Zalo's
  timestamp is epoch milliseconds; the verifier accepts seconds too. If real
  traffic is ever rejected with "timestamp outside the replay window", that
  parameter — not the code — is the first thing to look at.
- **The legacy plaintext token columns are not wiped.** The migration copies
  them encrypted and leaves the originals in place, as the handover specified.
  Wiping them is a separate, deliberately reversible decision; on vietuat it is
  moot (both are empty).
- **`zalo.config.oa_id` on vietuat is the single character `'o'`.** That is the
  live value and the migration copied it faithfully into
  `resource_external_id`. It will not match any real webhook payload, so the
  first real sign-in must correct it — `handle_callback` does exactly that from
  `getoa`.
- CC-E (Meta) and CC-F (Email + VoIP24h + monitoring polish) are unchanged.
  `parse_inbound` / `send_message` still raise `NotImplementedError` for email
  and call.
- **The repo-wide `.po` repair (§5.67/§5.58)** is one module further along:
  health_zalo is fixed, the rest are still inert.
