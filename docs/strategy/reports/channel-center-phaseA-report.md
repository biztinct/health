# Channel Center CC-A — Implementation Report

**Phase:** Channel Connection Center, Phase CC-A (connection framework core)
**Handover:** `docs/strategy/handovers/channel-center-phaseA.md`
**Architecture:** `docs/strategy/handovers/channel-center-architecture.md`
**Implemented by:** Opus 5 · **Date:** 2026-07-25 · **Target:** vietuat
**Module:** `health_care_command_channels` 19.0.1.0.0 (installed, not auto_install)

---

## 1. What was built

```
addons/health_care_command_channels/
├── __manifest__.py                          19.0.1.0.0, depends health_care_command + health_api_gateway
├── __init__.py                              services → models → controllers
├── services/
│   ├── channel_crypto.py                    AES-256-GCM, chs$1$, HKDF info health19-channel-secret-v1
│   ├── redact.py                            the ONE redaction helper (URL query, bearer, key=value, 300-char)
│   └── adapters.py                          registry + BaseChannelAdapter + 8 declaration-only stubs
├── models/
│   ├── channel_platform_app.py              Plane 1 + TransientModel secret wizard
│   ├── care_channel_connection.py           Plane 2: state machine, write guard, readiness, refresh lock, health cron
│   ├── care_channel_oauth_session.py        hashed single-use state, PKCE S256, _handle_callback, purge cron
│   ├── care_channel_readiness_check.py      9 check keys, upsert_check → _recompute_ready
│   ├── care_channel_audit.py                append-only, unconditional guards, _log()
│   └── res_config_settings.py               channel_hub.allowed_redirect_hosts
├── controllers/oauth.py                     /channel_hub/oauth/callback/<provider> (10-line shell)
├── security/{ir.model.access.csv, channel_hub_security.xml}
├── views/{oauth_templates, platform_app_views, channel_connection_views,
│          res_config_settings_views, menus}.xml
├── data/ir_cron.xml                         health (30 min) + session purge (daily 02:40)
├── i18n/vi.po                               §29 `#. module:` + §5.58 `#. odoo-python` markers
└── tests/{common.py, test_crypto.py, test_framework.py, test_oauth_engine.py}   T70–T89
```

**Zero edits outside the new module.** `git status` confirms the only change
this phase adds under `addons/` is the new directory; health_care_command,
health_zalo and health_voip24h are untouched (the 46-test regression run is the
proof — see §4).

### Security properties actually implemented

- **Two credential planes, both encrypted at rest.** No plaintext secret column
  exists anywhere; `T73` reads the raw `channel_platform_app` row in SQL and
  asserts the `chs$1$` prefix with the plaintext absent.
- **No `tracking=True` on any credential-adjacent field** anywhere (defect Z1).
- **`*_enc` fields carry `groups='base.group_system'` and appear in no view.**
  T74 grants the export right first, then proves a crm_manager still cannot
  `read()` or `export_data()` them, and that `readiness_summary()` contains no
  ciphertext.
- **`state` has exactly one writer.** `_transition()` validates an explicit
  transition table and audits every move; every other write path is refused by
  a whitelist guard (`active` + mail's `message_main_attachment_id` only).
  The guard is keyed on an internal **context flag**, not on `self.env.su` —
  uid 1 always runs as su, so an su-based guard would be dead code in tests and
  for admin (ledger §5.4). T75 proves both the crm_manager RPC write and the
  uid-1 write raise.
- **Readiness is derived, never asserted.** `ready` requires every check the
  adapter declares as *required* to be `pass`; `n_a` satisfies nothing that is
  required, failure falls to `action_required` (the tenant must act) and never
  to `error` (the framework broke), and derivation never fires from
  `not_connected` (T77).
- **OAuth engine fixes Z6 structurally**: state returned once and stored hashed,
  PKCE S256 with an encrypted verifier, 10-minute expiry, single use burned
  *before* any provider call, unknown/used/expired/mismatched all one
  indistinguishable outcome, redirect allowlist with no open redirect
  (T82/T83/T84/T86).
- **Append-only audit with no su escape**, `ondelete='set null'` on
  `connection_id` so deleting a connection cannot cascade the history away at
  the SQL layer (ledger §5.30), and `_log()` runs inside `cr.savepoint()` so a
  failed audit write cannot poison the caller's transaction (§5.55, T78).
- **Everything user-supplied is redacted** before it is stored or returned
  (T79), including provider error text on the health path.

---

## 2. Deviations from the handover (all declared)

| # | Handover said | Shipped | Why |
|---|---------------|---------|-----|
| D1 | `care.channel.audit.log(...)` classmethod | **`_log(...)`** | The method creates through `sudo()`. A public name is RPC-callable, so any logged-in user could forge operational evidence into an append-only audit table. Nothing else calls it yet (CC-A is net-new), so no contract breaks. |
| D2 | Connection model implicitly plain | `_inherit = ['mail.thread', 'mail.activity.mixin']` | The expiry warning is a `mail.activity`, and `mail.activity.action_notify()` calls `record.message_notify()` on the assigned record — which only exists on a `mail.thread` model. Without the mixin the §7 expiry warning would crash for any assignee other than the acting user. **No field carries `tracking=True`** (Z1 held). Chatter renders `<chatter/>` at the bottom, full width. |
| D3 | "7-day warning activity to the connection's company tenant admins" (plural) | **ONE** activity, assigned to the lowest-id CRM manager of the company | The handover's own T87 asks for "ONE activity created (idempotent on second run)". One-per-manager is a notification storm on a shared record — on vietuat that would have been one activity *and one notification email* per manager, per expiring connection. `_expiry_activity_user()` is a single seam for CC-F to make routing smarter. |
| D4 | Platform secret wizard field `required=True` | required in the **view**, not on the model | `action_apply()` blanks the plaintext off the transient row immediately after storing it; a model-level `required=True` is a NOT NULL column and refuses that write (hit live, T73 errored). `action_set_secret()` refuses an empty value anyway. |
| D5 | T85: "simulated concurrent lock (second cursor NOWAIT) returns 'locked'" | the contended branch is driven by making the NOWAIT statement raise `psycopg2.errors.LockNotAvailable` | **A genuine two-worker race cannot be staged in a TransactionCase** — see the new gotcha in §6. Part (c) (fresh-cursor persistence) *is* exercised for real, against a committed fixture row, read back on a third cursor with its own snapshot, and deleted in `finally`. |
| D6 | `care.channel.audit.event` implied Selection by the event list | `Char` | Architecture §5.5 specifies Char; a later phase's adapter can add an event tag without a schema change. Unknown tags are logged at INFO but never refused — losing the audit row would be worse than an unrecognised label. |
| D7 | — (addition) | `_get_secret`/`_get_pkce_verifier`/`_transition`/`_log` all underscore-prefixed | Odoo does not expose `_`-prefixed methods over RPC; that is the mechanism keeping the read path server-side, as the handover §4.1 anticipated. |

**ACL deferral (handover §4.2, as instructed):** `health_user_admin` is NOT a
dependency of this module. `care.channel.connection` ACL rows are granted to
`health_crm.group_health_crm_user` (read), `health_crm.group_health_crm_manager`
(read/write/create, **no unlink** — disconnect is a state, not a delete) and
`base.group_system` (all). The tenant-admin group
(`health_user_admin.group_health_user_admin`) gets its ACL row in **CC-C**, when
the Center UI lands. `_expiry_activity_user()` addresses CRM managers for the
same reason.

---

## 3. Adapter capability declarations (the contract CC-B…CC-F build against)

All 8 registered; `authorization_capabilities()` returns the eight required keys
(`mode`, `needs_platform_app`, `resource_selection`, `webhook_auto`,
`supports_refresh`, `supports_revoke`, `required_checks`, `guide_steps`), plus
`parent_channel: 'zalo'` on `zns`. Values are the verified matrix from
architecture §3 verbatim. T81 asserts registration, key completeness, that every
declared check key is a real one, and that the returned dict cannot be mutated
back into the class declaration.

`webhook_auto` is `False` where the architecture says "n/a" (email, webchat) —
the flag answers "can our software register the webhook", and "there is no
webhook" is honestly `False`, not `None`.

---

## 4. Test results (verbatim, vietuat)

Run 1 — the new module (`-u health_care_command_channels --test-tags
/health_care_command_channels --no-http`):

```
2026-07-25 09:48:33,271 INFO vietuat odoo.tests.stats: health_care_command_channels: 26 tests 4.94s 4472 queries
2026-07-25 09:48:33,271 INFO vietuat odoo.tests.result: 0 failed, 0 error(s) of 20 tests when loading database 'vietuat'
EXIT:0   HTTP:200
```

Run 2 — zero-regression proof on the untouched Care Command modules
(`--test-tags /health_care_command,/health_care_command_ai,/health_care_command_voip`):

```
2026-07-25 09:49:18,991 INFO vietuat odoo.tests.stats: health_care_command: 38 tests 7.86s 6465 queries
2026-07-25 09:49:18,991 INFO vietuat odoo.tests.stats: health_care_command_ai: 8 tests 1.72s 1522 queries
2026-07-25 09:49:18,991 INFO vietuat odoo.tests.stats: health_care_command_voip: 6 tests 0.51s 397 queries
2026-07-25 09:49:18,991 INFO vietuat odoo.tests.result: 0 failed, 0 error(s) of 46 tests when loading database 'vietuat'
EXIT:0   HTTP:200
```

T70–T89 coverage: T70/71/72 crypto · T73–T81 + T87 + T89 framework ·
T82–T86 + T88 engine. TransactionCase only, **zero HttpCase** (§5.32), zero real
HTTP, zero credentials. (T87/T89 live in `test_framework.py` rather than a
fourth file — both exercise framework models, and the handover's file split is
indicative, not binding.)

**Three genuine defects were caught by the first red run**, all fixed:
the wizard NOT NULL trap (D4), the export-right false negative in T74 (the
assertion was proving the wrong thing), and a fixture bug where `_conn()`
returned a recordset still carrying the internal context — which silently
disarmed the very write guard T75 exists to test. That last one is worth
remembering: **an Odoo context propagates through every derived recordset, so a
fixture that creates through a bypass context must re-`browse()` before handing
the record to a guard test.**

---

## 5. Data honesty on vietuat

- 0 platform apps, 0 connections, 0 sessions, 0 readiness checks, 0 audit rows
  after deploy (counted with `active_test=False`, ledger §5.27) — installing the
  module genuinely changes nothing until an operator seeds a platform app.
- Both crons registered and active (health 30 min, purge daily 02:40).
- Menus: "Channels (setup)" and "Channel Audit" gated to CRM Manager,
  "Platform Applications" gated to `base.group_system`. Ordinary CRM users see
  none of the three.
- Care Command itself is **unchanged**: no core file touched, dock/wall/composer
  identical, and the 46-test suite is green.
- Full probe transcript: `docs/strategy/reports/channel-center-phaseA-evidence/`.

**One DoD item not done:** the handover §11.4 asks for a screenshot of the two
new backend menus. I could not log in to care.biztinct.com — no credential is
available to me in this session, and I declined to reset a live user's password
or create a privileged QA account just to photograph a menu. The menus are
proven server-side instead (name, parent path and group gating, in
`evidence/server-state.txt`). Say the word and I will take the screenshot with a
login you supply.

---

## 6. New gotcha for the ledger (§5)

> **§5.63 — Odoo opens every database connection at REPEATABLE READ, so a
> TransactionCase can never see another transaction's later commits — which
> makes a two-worker lock race, or any "did my fresh-cursor write really
> commit" assertion made *through the test env*, structurally impossible.**
> `odoo/sql_db.py` imports `ISOLATION_LEVEL_REPEATABLE_READ`; the test
> transaction works from the snapshot it took at setUp. Consequences hit live
> while writing T85: (a) a row INSERTed and committed by a `Registry(db).cursor()`
> during the test is **invisible** to the test transaction, so
> `SELECT … WHERE id=%s FOR UPDATE NOWAIT` matches ZERO rows, takes no lock, and
> the contended branch silently returns the *success* value — the test passes
> the wrong assertion or fails with a baffling `'ran' != 'locked'`; (b) a
> fresh-cursor writer (`Registry(db).cursor()` + ORM write, the gateway audit
> idiom) called on a record created *inside* the test transaction dies with
> `MissingError` — correct production behaviour, useless as a test. Recipes:
> drive the contended branch by patching the cursor to raise
> `psycopg2.errors.LockNotAvailable` (what is under test is your handling, not
> PostgreSQL's NOWAIT); and prove a fresh-cursor write end-to-end by keeping the
> whole round trip outside the test transaction — committed fixture row via one
> cursor, the write, a read-back on a *third* cursor with its own snapshot,
> `DELETE` in `finally`. Related but distinct from §5.32/§5.45/§5.48: those are
> about cross-process state on a live server; this one bites inside a single
> test. (Also confirmed while digging: `TestCursor`/registry test mode is
> entered by **HttpCase only** — `cls.registry_test_mode` in
> `odoo/tests/common.py` — so in a TransactionCase `Registry(db).cursor()` is a
> genuinely separate connection, not a savepoint alias.)

Two smaller notes worth carrying:

- `mail.activity` on a model without `mail.thread` crashes as soon as the
  activity is assigned to someone other than the acting user
  (`action_notify()` → `record.message_notify()`). Inherit the mixin, or assign
  only to `self.env.user`.
- A `res.config.settings` Char backed by `config_parameter` needs **no**
  `set_values()` override: §5.36's unlink-on-falsy trap is Boolean/Integer
  specific, and for a Char an empty value *meaning* "no entries" is exactly what
  the unlink produces. Documented in the model so the next reader does not
  "fix" it.

---

## 7. Deferred / next

- **Tenant-admin ACL row** (`health_user_admin.group_health_user_admin`) → CC-C,
  per handover §4.2.
- **Every adapter operation** beyond `authorization_capabilities()` raises
  `NotImplementedError` by design: the health cron treats that as "nothing to
  check yet" and reschedules quietly, and the OAuth callback reports an honest
  `error` outcome instead of pretending to have connected. Real exchanges land
  in CC-D (Zalo), CC-E (Meta), CC-F (Email + VoIP24h).
- **`_with_refresh_lock` / `_persist_refreshed_tokens`** are built and tested but
  not yet used by any real refresh — CC-D is their first consumer (Zalo's
  single-use rotation is the forcing case).
- Platform-operator checklist item §12.9 (`HEALTH_PHI_KEY` on every environment)
  still stands: channel_crypto shares that root key. Where the variable is
  unset the key derives from `database.secret`, which works but keeps the key
  inside the database backup.
- No pip installs; `cryptography` 49 was already present.
