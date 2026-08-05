# Phase GL-1 — Go-Live Studio server framework (health_care_command_channels)

Read `docs/strategy/HANDOVER-CONVENTIONS.md` FIRST and follow it exactly.
Design context: `docs/strategy/handovers/golive-studio-design.md`.

## Scope

Server plumbing only, entirely inside **`health_care_command_channels`**:

1. Structured, translatable go-live step declarations for **meta** and
   **zalo** on `channel.platform.app`.
2. A `channel.golive.progress` model (operator convenience state).
3. Three operator-gated RPC methods: `golive_state`, `golive_submit`,
   `golive_mark`.
4. Webhook-handshake proof logging in `care.channel.audit` (new event tag),
   from the Meta challenge handler and the Zalo webhook.
5. Tests + vi.po entries for every new string.

**Binding non-goals:** NO UI (GL-2), NO invites/public pages (GL-3), NO
google/microsoft/voip24h steps (GL-4), no changes to any tenant-facing
endpoint's behaviour, no new menus, no other module touched. The existing
raw form, `PROVIDER_EXTERNAL_STEPS` and `_render_go_live_checklist` keep
working — the ONLY sanctioned change there is sourcing the meta/zalo `<ol>`
items from the new declarations (see §D4).

Module version: bump `__manifest__.py` `19.0.7.0.1 → 19.0.8.0.0`. No PWA
assets touched ⇒ no PWA version bump.

## Verified plumbing — do NOT re-derive, trust these lines

- `channel.platform.app` (models/channel_platform_app.py): `action_set_secret(secret)` :507 (the ONLY secret write path; encrypts, hints, audits); `_get_secret()` :541 server-only; `action_preflight()` :416 (meta = real credentials check via `meta_app_identity`, persists `preflight_status/at/detail`, returns a notification action, NEVER raises on provider refusal); `action_generate_verify_token()` :373 (meta-only; **merges** into `extra_json`, refuses if one exists); `get_extra(key)` :249; `_validate_extra_json` :240; computed `oauth_redirect_uri` / `webhook_urls` :285 from `OAUTH_REDIRECT_PATHS`/`WEBHOOK_PATHS`; `_go_live_rows()` :301 (client id, secret, per-adapter `required_platform_keys`, email addon); `_get_for_provider(provider)` :546; one-active-app-per-provider partial unique index in `init()` :194 with pre-check `_check_provider_unique` :210; `_require_operator()` :487 (base.group_system, raises UserError); `_notify()` :495.
- Required extra keys (adapters.py): WhatsApp `('es_config_id', 'verify_token')` :954, Messenger `('flb_config_id', 'verify_token')` :1375, Zalo none :1653 (`platform_providers ['zalo']`). Constants `META_ES_CONFIG_KEY`/`META_FLB_CONFIG_KEY` at adapters.py:65-66, `VERIFY_TOKEN_KEY = 'verify_token'` at services/webhook_verify.py:29. `platform_ready()` (adapters.py:437-462) = client_id + secret + every required key ⇒ finishing these steps lights tenant cards with zero glue.
- Meta handshake: `meta_handshake` controllers/meta.py:47-64 — GET, public; success path is the `return self._text(challenge)` at :64 (only reached when `meta_challenge` matched the stored verify token). Refusals at :55 and :61-63 must stay exactly as they are (bodyless 403 / logged info).
- Zalo webhook: `zalo_webhook` controllers/zalo.py:68-87 — the verified-success boundary is line 78 comment "Verified: escalate only now". Refusal semantics (indistinguishable 403s) must not change.
- Audit: `care.channel.audit._log(event, connection=None, company_id=None, user=None, detail=None, channel=None)` (care_channel_audit.py:86) — savepoint-wrapped, never raises, redacts detail. `KNOWN_EVENTS` set at :29-45. Append-only guards are unconditional.
- Translatable-steps pattern to clone: `channel.center._center_guide_texts()` (models/channel_center.py:264-435) — a `@api.model` method returning dicts of `_()` strings. This translates correctly; static module-level lists would not (selection-translation ledger rule).
- Tests live in `tests/`, spine helpers in `tests/common.py` / `tests/common_spine.py`; existing platform-app tests in `tests/test_platform_go_live.py` (extend, don't fork, if a helper fits). HttpCase classes MUST be `@tagged('post_install', '-at_install')` and the §2 deploy command (no `--no-http`, `--workers=0`) is mandatory for them to actually run.

## D1 — Step declarations

New file `models/channel_golive.py` (add to `models/__init__.py`). Put the
declarations on `channel.platform.app` via `_inherit` there (keeps the raw
model file at its current size):

```python
@api.model
def _golive_steps(self):
    """Ordered go-live steps per provider. All copy through _() at call
    time (translation rule). Keys are stable API for the GL-2 UI —
    never rename one after ship."""
    return {'meta': [...7 steps...], 'zalo': [...5 steps...]}
```

Step shape (every field always present; empty list/False where n/a):

```python
{
  'key': 'create_app',            # stable
  'kind': 'do',                   # do | wait  ("we-check" is expressed via verify)
  'title': _('Create the app'),
  'body': _('...plain language, guide-texts voice...'),
  'console': 'https://developers.facebook.com/apps/creation/',
                                   # may contain '{app_id}' — resolved in golive_state
  'console_label': _('Open the Meta App Dashboard'),
  'copy_values': [],               # list of keys: 'oauth_redirect_uri' | 'webhook_urls' | 'verify_token'
  'inputs': [{'name': 'client_id', 'label': _('App ID'),
              'secret': False,
              'regex': r'^\d{10,20}$',
              'error': _('A Meta App ID is a long number — copy it from the top of the app dashboard.')}],
  'verify': 'manual',              # manual | preflight | handshake
  'est': _('about 10 minutes'),
}
```

**Meta (7):**
1. `create_app` (do/manual) — console `https://developers.facebook.com/apps/creation/`; body: Business-type app; input `client_id` (regex `^\d{10,20}$`).
2. `store_secret` (do/**preflight**) — console `https://developers.facebook.com/apps/{app_id}/settings/basic/`; input `client_secret` (`secret: True`, regex `^\S{16,128}$`, error says where "Show" is).
3. `business_verification` (**wait**/manual) — console `https://business.facebook.com/settings/security-center`; body: 1–3 weeks, may bounce for more documents; markable "submitted".
4. `app_review` (**wait**/manual) — console `https://developers.facebook.com/apps/{app_id}/app-review/permissions/`; body lists the 5 permissions verbatim: whatsapp_business_management, whatsapp_business_messaging, pages_show_list, pages_messaging, pages_manage_metadata.
5. `webhooks` (do/**handshake**) — console `https://developers.facebook.com/apps/{app_id}/webhooks/`; `copy_values: ['oauth_redirect_uri', 'webhook_urls', 'verify_token']`; body: paste both product webhook URLs + the verify token, click "Verify and save" — *this screen turns green the moment Meta's check reaches us*.
6. `config_ids` (do/manual) — inputs `es_config_id` + `flb_config_id` (regex `^\d{5,30}$` each); body explains Embedded Signup (WhatsApp) + Login for Business (Messenger) configurations.
7. `done` (wait/manual, computed — see D3) — celebration copy.

**Zalo (5):** 1 `create_app` (do/manual, console `https://developers.zalo.me`, body: create app + link the Official Account) → 2 `credentials` (do/preflight-shaped but verify `manual` — Zalo has no credentials-only check; inputs `client_id` regex `^\d{6,30}$` + `client_secret` secret regex `^\S{8,128}$`) → 3 `oauth_redirect` (do/manual, copy_values `['oauth_redirect_uri']`, console `https://developers.zalo.me/app`) → 4 `webhook` (do/**handshake**, copy_values `['webhook_urls']`; body says out loud: Zalo allows ONE webhook URL per app and every tenant OA shares it; the step completes when the first verified Zalo event arrives) → 5 `done`.

Copy discipline: clone the `_center_guide_texts` voice — short sentences,
"Your Facebook password is only ever typed on Meta's own page", honest waits.
No emoji.

## D2 — Progress model

In the same new file:

```python
class ChannelGoliveProgress(models.Model):
    _name = 'channel.golive.progress'
    _description = 'Go-Live Studio Progress'
    provider = fields.Selection(PROVIDERS, required=True, index=True)
    steps_json = fields.Text(default='{}')   # {step_key: {'marked': true, 'marked_on': 'YYYY-MM-DD'}}
    active = fields.Boolean(default=True)
```

One row per provider: clone the platform-app pattern — partial unique index
in `init()` + `_check_provider_unique`-style pre-check (ledger §5.3: check
BEFORE super(), clean ValidationError, never an IntegrityError). Validate
`steps_json` is a JSON object on write (clone `_validate_extra_json`).
ACL (`security/ir.model.access.csv`): one line, `base.group_system`, no
unlink needed (`perm_unlink` 0). No menus, no views — this model is Studio
state only. **No `tracking=True` anywhere in this phase** (Z1 rule).

## D3 — RPC surface (on `channel.platform.app`, in the new file)

All three: `@api.model`, first line `self._require_operator()`.

`golive_state()` → for each provider in `('meta', 'zalo')`:

```python
{'provider': 'meta',
 'app_id': int | False,            # channel.platform.app id if a row exists
 'client_id': '...' | False,
 'secret_hint': '••••abcd' | False,
 'preflight': {'status': 'pass', 'at': '...', 'detail': '...'},
 'values': {'oauth_redirect_uri': ..., 'webhook_urls': ...,   # computed fields
            'verify_token': ...,                              # get_extra — meta only
            'es_config_id': ..., 'flb_config_id': ...},       # meta only
 'last_handshake_at': '...' | False,   # newest care.channel.audit webhook_handshake row for this provider (meta: channel in whatsapp/fb; zalo: channel zalo)
 'progress': {...},                    # parsed steps_json ({} when no row)
 'channels': ['whatsapp', 'fb'],       # adapters with this provider in platform_providers
 'platform_ready': {'whatsapp': True, ...},   # each adapter's platform_ready()
 'steps': [ {**declaration, 'console': resolved,   # '{app_id}' filled from client_id, or False if unknown yet
             'status': 'done'|'todo'|'waiting'|'fail'} ]}
```

**Derived truth (the core rule — steps_json can never say "done" for a step
whose artifact is missing):**
- `create_app` done ⇔ `client_id` set. `store_secret`/`credentials` done ⇔
  `has_secret` AND (verify != preflight OR `preflight_status == 'pass'`);
  `fail` when `preflight_status == 'fail'`.
- `verify == 'handshake'` done ⇔ `last_handshake_at` truthy.
- `config_ids` done ⇔ both extras non-empty.
- `wait` steps: `waiting` once marked in progress (echo `marked_on`), `todo`
  otherwise — except `done` (final step): done ⇔ every required platform key
  present AND secret AND client_id (i.e. `_go_live_rows()` all true).
- Everything else falls back to the progress mark.

**Never in the payload:** any secret, `client_secret_enc`, decrypted
anything. `secret_hint` and `verify_token` are the ceiling (the verify token
is non-secret plane by design — it already lives in the visible
`extra_json`).

`golive_submit(provider, step_key, payload)` → routes writes through the
existing paths, creating the platform-app row on first submit
(`_get_for_provider` → `create({'provider': provider})` if empty):
- Validate `provider in ('meta','zalo')`, step exists, every payload key is a
  declared input for that step; check each value against the declared regex →
  `ValidationError` with the declared `error` string on mismatch. Reject
  unknown keys.
- `client_id` → plain `write`.
- `client_secret` → `app.action_set_secret(value)` (NEVER any other path);
  then, if the step's verify is `preflight`, call `app.action_preflight()`.
  Both already audit.
- `es_config_id` / `flb_config_id` → **merge** into `extra_json` (clone the
  read-modify-write at channel_platform_app.py:393-403 — losing a sibling key
  dark-cards a channel). Also: if meta and no verify token exists yet, call
  `action_generate_verify_token()` here (first extra-write is the natural
  mint point; guard with `get_extra(VERIFY_TOKEN_KEY)` to respect its
  refuse-if-exists rule).
- Return the refreshed `golive_state()` (the UI always repaints from truth).

`golive_mark(provider, step_key, marked)` → only valid for steps whose
declaration is `kind == 'wait'` or `verify == 'manual'` (refuse otherwise —
derived steps cannot be hand-marked); upsert the progress row, set/clear
`{'marked': bool, 'marked_on': fields.Date.to_string(today)}`. Return
refreshed `golive_state()`.

## D4 — Handshake logging + checklist unification

1. `KNOWN_EVENTS` (care_channel_audit.py:29): add `'webhook_handshake'` with
   a one-line comment (GL-1).
2. controllers/meta.py `meta_handshake`: immediately before the success
   `return self._text(challenge)` (:64), log
   `request.env(su=True)['care.channel.audit']._log('webhook_handshake',
   channel=channel, detail='meta dashboard handshake ok')`. Success path
   ONLY — a failed guess must stay an unlogged 403 (no audit-spam oracle,
   and `_log` on the public success path is safe because `_log` never
   raises). Response bytes/status must be byte-identical to today.
3. controllers/zalo.py `zalo_webhook`: at the verified boundary (:78, before
   dispatch), log `webhook_handshake` with `channel='zalo'` **only if no
   prior `webhook_handshake` row with channel 'zalo' exists** (search
   limit 1 on the indexed `event` field; every verified event would
   otherwise spam the audit). Dispatch behaviour unchanged.
4. `_render_go_live_checklist` (channel_platform_app.py:358): for providers
   present in `_golive_steps()`, build the external-steps `<ol>` from the new
   declarations' titles instead of `PROVIDER_EXTERNAL_STEPS`; google/
   microsoft keep the old dict until GL-4. Delete the meta/zalo entries from
   `PROVIDER_EXTERNAL_STEPS` in the same change (one source of truth).

## Safety rails (binding)

- No `tracking=True` on any field this phase touches (Z1 leak path).
- Secrets: `action_set_secret` is the only write, `_get_secret` stays
  server-only, nothing secret in any RPC return or audit detail (the redact
  layer is belt; do not rely on it — never pass a secret into `detail`).
- `extra_json` writes are merge-never-replace, validated JSON-object.
- Public webhook routes: zero change to status codes, response bodies,
  refusal indistinguishability, or the parse-before-verify order in zalo.py.
- `_require_operator()` on all three RPCs — they are RPC-reachable by name,
  ACLs alone are not the story.
- `_sql_constraints` are not materialised on Odoo 19 — unique via `init()`
  partial index + pre-check, exactly like channel_platform_app.py:194/:210.

## Tests — `tests/test_golive.py` (TransactionCase unless noted)

1. Non-system user calling each of the three RPCs → UserError; system user →
   no error.
2. Fresh DB `golive_state()`: meta has 7 steps / zalo 5, every status `todo`,
   `app_id` False, `values.oauth_redirect_uri` non-empty (computed even
   before a row exists — build it from `OAUTH_REDIRECT_PATHS` in that case),
   `console` False for `{app_id}` templates.
3. `golive_submit('meta','create_app',{'client_id':'abc'})` →
   ValidationError (regex), no row created.
4. Valid `client_id` submit creates the ONE platform-app row; a second submit
   updates it (no duplicate; `_check_provider_unique` untriggered).
5. Secret submit: with `meta_app_identity` monkeypatched to return an app
   name → `has_secret` True, `secret_hint` set, `preflight_status == 'pass'`,
   state's `store_secret` step `done`, and the returned state contains **no**
   secret material (assert the serialized payload lacks the submitted
   string).
6. Preflight refusal path: patch `meta_app_identity` to raise
   `ChannelSendError('bad')` → no exception to the caller,
   `preflight_status == 'fail'`, step status `fail`, detail redacted.
7. `config_ids` submit with a pre-seeded `verify_token` in `extra_json`:
   both ids land, token untouched (merge proof); without a token: token
   auto-minted once, second submit does not remint.
8. `golive_mark` on `business_verification` → `waiting` + `marked_on`
   echoed; `golive_mark` on `store_secret` → UserError/ValidationError
   (derived steps refuse hand-marks). Unmark works.
9. Derived-truth override: audit row
   `_log('webhook_handshake', channel='whatsapp')` seeded → meta `webhooks`
   step `done` with `last_handshake_at` set, even with empty steps_json.
10. `unknown payload key / unknown step / unknown provider` → ValidationError.
11. (HttpCase, `@tagged('post_install','-at_install')`) Meta handshake GET
    with the correct verify token → 200, challenge echoed, exactly one
    `webhook_handshake` audit row (channel matches); wrong token → 403 and
    NO audit row.
12. (HttpCase) Two verified Zalo webhook POSTs (reuse the signing helper
    pattern from tests/test_zalo_center.py) → exactly ONE zalo
    `webhook_handshake` row; dispatch still ran for both (message count).
13. `_render_go_live_checklist` for a meta row still renders an `<ol>` whose
    items equal the `_golive_steps()['meta']` titles; google still renders
    from `PROVIDER_EXTERNAL_STEPS`.

## i18n

Add every new `_()` string to `i18n/vi.po` with proper `#. odoo-python`
comment blocks; run `msgfmt --check-format`. (The malformed-po problem lives
in health_zalo, not here — do not "fix" other modules.)

## Deploy + verify (conventions §2 verbatim)

`scp` the module → `sudo cp` → upgrade with
`-u health_care_command_channels --test-enable
--test-tags /health_care_command_channels --workers=0` (NO `--no-http`),
own `--logfile`, then restart and curl-check. Confirm the HttpCases actually
started (`grep -ac "Starting .*Http"`). Pre-existing known reds elsewhere
(`test_compare_request_runs`, health_zalo po) are not yours.

## Self-review protocol (MANDATORY — no separate reviewer on this stream)

After tests pass, before reporting:
1. Re-read every file you changed, top to bottom, against this document —
   check each D-section and each safety rail explicitly, one by one.
2. Confirm on the SERVER (not the repo) that the deployed copy matches
   (`diff` a spot file), the service restarted, `/web/login` answers, and
   the audit table has your test rows only where expected.
3. Grep your diff for: `tracking=True`, any secret in a return/detail/log,
   any change to a webhook route's response semantics. All three must be
   clean.
4. Report honestly: full `odoo.tests.result` lines, anything skipped,
   any deviation from this doc with its reason. Do not round up.

## Report back

- The exact `golive_state()` JSON of a fully-exercised meta provider (GL-2
  builds against it — it becomes the contract).
- Test result lines (13/13 expected) + HttpCase start counts.
- Any deviation, with reason, and anything about the Zalo signing helper
  that GL-2/GL-3 should know.

## Kickoff line (paste into the Opus session)

Implement phase GL-1 exactly as specified in
`docs/strategy/handovers/golive-studio-phaseGL1.md` (read
`docs/strategy/HANDOVER-CONVENTIONS.md` first, entirely). Work only inside
`addons/health_care_command_channels`. When done, run the full test list on
UAT per §2, then execute the Self-review protocol section and report back
per the Report back section.
