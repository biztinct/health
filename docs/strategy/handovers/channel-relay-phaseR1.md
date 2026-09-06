# R1 — Channel Relay: one Meta app for every customer

**Read with:** `docs/strategy/HANDOVER-CONVENTIONS.md` (binding — §1 multi-database box,
§2 deploy/test procedure incl. the H77 `systemd-run` rule, §4 sanctioned edits, §5.32 HttpCase
posture, §5.61 fail-closed webhooks, §5.63 fresh cursors under test, §5.95 archive-never-delete
fixtures, H32 `--db-filter`, H102 clone-of-platform writes on real customers) and
`docs/strategy/handovers/channel-center-architecture.md` (§4 two credential planes,
§7 secrets/OAuth posture, §13 one webhook per app). `docs/SAAS_RUNBOOK.md` for the
three-database release ritual.

**Modules:**

| Module | Role | Ships to | Version |
|---|---|---|---|
| `biz_platform_channel_relay` (NEW) | the hub — lives on the master only | master `carejiox` ONLY (never-listed by the `biz_platform` prefix, `health_tenancy/models/registrations.py:NEVER_PREFIXES`) | 19.0.1.0.0 |
| `health_channel_relay` (NEW) | the client — one override on every customer | every database (auto-included by the `health_` prefix; inert on the master) | 19.0.1.0.0 |
| `health_care_command_channels` (EDIT) | three small seams, listed in §6 | every database | 19.0.11.2.0 → **19.0.11.3.0** |

---

## 1. Why this phase exists (plain words first)

Meta allows **exactly one webhook address per product per app** (one for WhatsApp, one for
Messenger) and demands an **exact-match list of sign-in return addresses**. Our platform is one
database per customer on its own subdomain (`hhh.carejiox.com`, …), each expecting Meta to call
*its own* address. So today one Meta app can serve one customer's inbox, and every new customer
would need either a second Meta app (a second App Review, weeks) or the operator editing the Meta
console by hand.

R1 makes one Meta app serve every customer:

1. **Incoming messages** — Meta calls the master's existing webhook address. The master looks at
   which Page / WhatsApp number the event is for, finds the customer who connected it, and hands
   that customer *only their own entries*, re-signed with the app secret, to that customer's own
   webhook route. The customer's code does not change: it verifies the signature exactly as if
   Meta had called it.
2. **Sign-in** — every customer's Messenger sign-in returns to the master's single callback
   address; the master reads the customer's short name out of the `state` and bounces the browser
   to that customer's own callback, which finishes the sign-in as it does today.
3. **Credentials** — the master pushes the Meta app id, secret and config ids into every live
   customer's database (encrypted with *that* database's key), so each customer can exchange
   codes and verify signatures without any human ever pasting a secret twice.

Scope in one line: **a new customer connects WhatsApp or Messenger by pressing Connect and signing
in; nobody opens the Meta console.** (Except once, for the JS-SDK domain — §8 step 6.)

## 2. Binding non-goals

- **No change to what Meta is told.** The operator pastes the SAME three addresses into the Meta
  app as today (master redirect URI, master WhatsApp webhook, master Messenger webhook) plus
  `carejiox.com` as an App Domain / JS-SDK domain. Go-Live Studio steps 1–7 on the master are
  untouched.
- **Meta only.** Zalo, Google, Microsoft, Telegram, email, webchat, VoIP are out of scope. (Zalo
  has the same one-URL limit; a later phase may reuse the relay.)
- **No per-WABA `override_callback_uri`** (Meta's WhatsApp-only webhook override). One mechanism
  for both products; the override is a documented future optimisation, not R1.
- **No hub-hosted Embedded Signup page.** WhatsApp sign-in stays on the customer's page with the
  FB JS SDK. Whether Meta's "Allowed Domains for the JavaScript SDK" accepts a parent domain for
  subdomains is UNKNOWN (§8 step 6 is the empirical check); if it refuses, that is R2's problem
  and this handover says so.
- **No UI in the Channel Center or the Go-Live Studio.** The relay's operator surface is two
  plain backend list views on the master (§4.7). No OWL.
- **No cross-database ORM writes from a public route.** Public routes read the route table and
  forward over HTTP; only the reconcile cron and the operator button open a customer's registry.
- **Never store or log a message body in plaintext on the master**, and never store one at all
  except in the retry queue, encrypted, for a failed delivery (§4.5).
- **No edit** to `biz_tenants`, `biz_tenancy`, `health_tenancy`, `health_api_gateway`, nginx, or
  the Meta app itself.

## 3. Verified plumbing — DO NOT RE-DERIVE

### 3.1 Live facts (checked 2026-09-06 on VietUcUAT)

- Databases: `carejiox` (master, https://carejiox.com), `carejiox_template`, `hhh`
  (https://hhh.carejiox.com, `biz.tenant` state `live`). Routing is `dbfilter = ^%d$`.
- Master `channel_platform_app`: `meta` row client_id `4376606219260542`, secret ending `33d9`,
  `extra_json = {"verify_token": "…"}` (no `es_config_id` / `flb_config_id` yet — Studio step 6
  pending). Also a `zalo` row. **`hhh` has 0 platform app rows.**
- `hhh` params: `web.base.url=https://hhh.carejiox.com`, `biz_tenancy.slug=hhh`,
  `biz_tenancy.platform_url=https://carejiox.com`. Master: `web.base.url=https://carejiox.com`.
- Installed on `hhh`: `health_care_command_channels`, `health_api_gateway`, `health_tenancy`,
  `biz_tenancy` — NOT `biz_tenants`. Master has all five.
- **`HEALTH_PHI_KEY` is NOT set** in the service environment → `channel_crypto._get_key()`
  derives the key from each database's own `database.secret`
  (`services/channel_crypto.py:54-72`). **A `chs$1$` token from the master cannot be decrypted on
  `hhh`.** Credentials must be encrypted inside the target database's own environment.
- Server `workers = 2` prefork; test runs need `--workers=0` on a spare port with the service UP
  (conventions §2 / H77).

### 3.2 The Meta webhook route (customer side, unchanged)

- `controllers/meta.py:44-72` GET handshake → `meta_challenge(app, mode, token, challenge)`
  (`services/webhook_verify.py:75-90`) against the local `channel.platform.app` meta row's
  `verify_token`; logs audit `webhook_handshake`.
- `controllers/meta.py:74-104` POST: reads `raw_body = request.httprequest.get_data()`, checks
  `X-Hub-Signature-256` with `verify_meta(app, raw_body, header)` (`webhook_verify.py:58-72` —
  HMAC-SHA256 over the RAW bytes with the app secret, `sha256=` prefix tolerated, lower-cased),
  then `env(su=True)['care.channel.message']._dispatch_meta(channel, payload)`; **always 200
  after verification**. `META_CHANNELS = ('whatsapp', 'fb')`.
- `care_channel_message.py:294-317 _meta_resource_ids(channel, payload)`: fb → `entry[].id`;
  whatsapp → `entry[].changes[].value.metadata.phone_number_id`. Order-stable dedupe.
- `:320-350 _dispatch_meta`: per resource id → `care.channel.connection._find_for_resource`
  (`care_channel_connection.py:706-719`, company-agnostic, `channel` + `resource_external_id`);
  unknown → `care.contact.capture._capture('unknown_resource', channel, resource_external_id=…,
  raw=self._dump(payload))`; known → `_dispatch_connection(connection, payload)` (`:352-`).
- Adapters filter by their own resource in `parse_inbound` (`adapters.py:1289-1345` whatsapp
  `metadata.phone_number_id != mine → skip`; `:1572-1614` fb `entry.id != mine → skip`), so a
  sub-payload containing only that tenant's entries is exactly what they expect.
- Dedupe on redelivery: unique index `(connection_id, external_message_id)`
  (`care_channel_message.py:11,105`).
- Traffic → truth: `_note_inbound` (`care_channel_connection.py:741-763`) flips
  `webhook_verified` + `inbound_ok` to pass on the first real inbound. **A customer never needs
  Meta's GET handshake** — the Center already says "stays pending until a real signed event
  arrives" (`channel_center.py:1045`).
- Webhook subscription is app-level: `_subscribe(node_id, token, fields_csv)` POSTs
  `/{id}/subscribed_apps` (`adapters.py:831-840`); whatsapp `:1133-1145` (WABA), fb `:1515-1530`
  (`messages,messaging_postbacks`). No callback URL is sent → Meta delivers to the app's URL =
  the master.

### 3.3 Sign-in (customer side)

- `channel_center.py:1081-1130 center_meta_start`: `Session.create_for(conn, provider='meta')`
  → `adapter.authorize_url(session, state, code_challenge)`.
- `care_channel_oauth_session.py:138-180 create_for`: `state = secrets.token_urlsafe(32)` (`:155`),
  stored as `state_hash = sha256(state)`; `:182-223 _consume(state)` hashes whatever arrives.
  **The state string is opaque to everything except `_consume`** → a prefix survives end to end.
- Messenger: `adapters.py:1396-1415 authorize_url` builds `dialog/oauth?client_id&config_id&
  redirect_uri=self._redirect_uri()&response_type=code&state`; `:759-783 exchange_code` sends the
  SAME `redirect_uri` (`_exchange_with_redirect = True`). `_redirect_uri()` = `:688-689`
  (`web.base.url + META_CALLBACK_PATH`), `META_CALLBACK_PATH = '/channel_hub/oauth/callback/meta'`
  (`:64`).
- WhatsApp Embedded Signup: NO redirect. The FB JS SDK popup returns the code to the customer's
  page (`authorize_url` `:977-999` returns `{app_id, config_id, state, sdk_url}`; `:1001-1050
  handle_callback`; `_exchange_with_redirect = False`). The page's domain must be allowed for the
  JS SDK in the Meta app — see §8 step 6.
- Callback controller: `controllers/oauth.py:46-61`
  `ChannelHubOauthController.oauth_callback(provider, **params)` — rate-limited by
  `gateway.rate.counter.hit('chub:cb:<ip>')`, delegates to
  `care.channel.oauth.session._handle_callback(provider, params)`, renders one of three pages,
  never echoes params. Its class is importable:
  `from odoo.addons.health_care_command_channels.controllers.oauth import ChannelHubOauthController`.
- Platform app compute: `channel_platform_app.py:266-280 _compute_go_live_urls` and
  `channel_golive.py:913-` `_golive_urls` build the redirect from `web.base.url` +
  `OAUTH_REDIRECT_PATHS`.

### 3.4 Credentials

- `channel.platform.app` (`channel_platform_app.py:117-`): `provider`, `client_id`,
  `client_secret_enc` (groups=base.group_system), `secret_hint`, `extra_json`, `active`; partial
  unique index one active row per provider (`:175-179`); `get_extra(key)`; `_get_secret()` (`:530`,
  server-side decrypt); `action_set_secret` (`:496`) is gated on `has_group('base.group_system')`
  — **do not call it from a cross-database env; write `client_secret_enc` with
  `channel_crypto.encrypt(tenant_env, plaintext)` + `secret_hint` directly under sudo** (the same
  two writes `action_set_secret` makes at `:510-515`), then audit `secret_rotated`.
- `care.channel.audit._log(event, connection=None, company_id=None, user=None, detail=None,
  channel=None)` (`care_channel_audit.py:99-129`), never raises, redacts detail. `KNOWN_EVENTS`
  is a set at `:29` — unknown tags are logged, not refused.
- `services/redact.py:redact(value)` — use on every stored error string.

### 3.5 The platform (cockpit) — read-only seams the hub may CALL

- Tenant list: `env['biz.tenant']` (`biz_tenants/models/tenant.py:33-57`): `slug` (= database
  name = first hostname label), `name`, `state` in draft/provisioning/trial/live/paused/
  pending_deletion/error/decommissioned. **Route and push only for `state in ('live', 'trial')`.**
- `env['biz.tenants']` (`biz_tenants/models/service.py:112`, `_name = 'biz.tenants'`): `_apex()` (`:133`,
  → `tenants_common.apex(env)`), `_tenant_host(slug)` (`:146-148`, `<slug>.<apex>`),
  `_tenant_url(slug)` (`:150`), `_http_port()` (`:143`), `_pg_cursor(dbname)` (`:158-176`,
  autocommit READ-ONLY raw cursor via `odoo.sql_db.db_connect`), `_tenant_env(dbname)` (`:228-248`,
  `@contextmanager`, full `api.Environment(cr, SUPERUSER_ID, {})` on `Registry(dbname)`, commits
  and `signal_changes()` on exit — **use this for every write into a customer database**; it is
  the sanctioned door, rail R5), `_probe(host)` (`:250-`, loopback `127.0.0.1:<port>` with a
  `Host:` header — clone this transport for forwarding).
- `tenants_common.P_APEX = 'biz_tenants.apex_domain'`; `T_SLUG = 'biz_tenancy.slug'`;
  `T_PLATFORM_URL = 'biz_tenancy.platform_url'` (set on every customer at provision,
  `service.py:704-736`).
- `_step_configure` (`service.py:694-`) is where a NEW customer's params are written. **Not
  edited in R1** — the hub's reconcile cron (§4.6) reaches a new customer within 10 minutes, and
  the operator button reaches it now.

### 3.6 Test conventions

- `health_care_command_channels/tests/common.py:ChannelHubCase` (TransactionCase): archives every
  live `care.channel.connection` and `channel.platform.app` row inside the test transaction
  (§5.95) — clone this in both new modules' `tests/common.py`.
- The one HttpCase precedent in the family: `tests/test_golive.py` header (TestCursor, asserts on
  DELTAS of `care.channel.audit`). Clone its shape for the relay's HttpCase.
- Mocks: patch `requests.post` with a PLAIN FUNCTION (§5.76 — `autospec` breaks binding).

## 4. Architecture

### 4.1 Naming

Nothing user-visible may say "Odoo". Provider names (Meta, WhatsApp, Messenger) are fine. In every
`string=`/`help=`/view label say **"customer"** (not tenant) and **"the platform"** (not hub/master).
Internal identifiers use `relay`, `tenant`, `hub` freely.

### 4.2 Hub data model (`biz_platform_channel_relay`)

```
channel.relay.tenant            one row per customer the relay serves
  slug            Char required, unique (index in init()), = biz.tenant.slug
  name            Char (customer's name, copied at reconcile)
  active          Boolean default True  (archived when the tenant leaves live/trial)
  host            Char computed, not stored: service._tenant_host(slug)
  credentials_pushed_at   Datetime
  pushed_secret_hint      Char   (last 4 the master pushed — compare with master's secret_hint)
  in_step         Boolean computed: pushed_secret_hint == master meta app secret_hint
                  AND pushed extra_json keys ⊇ master's
  route_count     Integer computed (count of routes)
  last_forward_at Datetime
  pending_count   Integer computed (deliveries state='pending')
  last_error      Char (redacted)

channel.relay.route             who owns which provider resource
  tenant_id       Many2one channel.relay.tenant, required, ondelete=cascade, index
  channel         Selection [('whatsapp','WhatsApp'),('fb','Messenger')] required
  resource_external_id  Char required index   (phone_number_id | page id)
  seen_at         Datetime
  UNIQUE (channel, resource_external_id) — partial index in init() (§5.1: _sql_constraints inert)
  + create/write pre-check raising ValidationError (§5.3)

channel.relay.delivery          a forward that did not land, kept to retry
  tenant_id, channel   as above
  body_enc        Text  (channel_crypto.encrypt on the MASTER env; cleared when delivered
                         or purged)
  signature       Char  (the sha256=… header we computed)
  attempts        Integer default 0
  next_at         Datetime index
  state           Selection pending / delivered / dead   default pending, index
  last_error      Char (redacted)
  delivered_at    Datetime
  entry_count     Integer  (how many entries were inside — for the operator, never the content)
```

ACL: all three models `base.group_system` full access, nobody else. No record rules. **No
`tracking=True` anywhere** (Z1).

### 4.3 Hub webhook router — `controllers/meta_relay.py`

```python
from odoo.addons.health_care_command_channels.controllers.meta import MetaWebhookController

class RelayMetaWebhookController(MetaWebhookController):
    @http.route('/care_channels/meta/<string:channel>/webhook', type='http',
                auth='public', methods=['POST'], csrf=False, save_session=False, website=False)
    def meta_webhook(self, channel, **kwargs):
        ...
```

Same path, same decorator values, same posture as the parent (`controllers/meta.py:74-104`): read
raw body first; `channel not in META_CHANNELS → 403`; `verify_meta` → 403 on failure; **200 from
here on, whatever happens**. The GET handshake is NOT overridden.

After verification, in `env(su=True)`, call `env['channel.relay.router']._route_meta(channel,
raw_body, payload)` (an AbstractModel so a TransactionCase covers it, exactly as
`_handle_callback` is model code and the controller is a shell — §5.32 posture). `_route_meta`
never raises out (wrap like the parent's try/except with `_logger.exception`). It returns a
counter dict for one log line: `{'local': n, 'forwarded': n, 'queued': n, 'unknown': n}`.

`_route_meta` algorithm:

1. `ids = env['care.channel.message']._meta_resource_ids(channel, payload)`.
2. Classify each id: **local** if `care.channel.connection._find_for_resource(channel, id)` hits
   (the master is also a clinic); else **routed** if a `channel.relay.route` row (active tenant)
   exists; else **unknown**.
3. If any unknown: `env['channel.relay.tenant']._maybe_resync(reason='unknown resource')` (throttled
   — at most once per 60 s, timestamp in param `channel_relay.last_resync_at`; the sync reads every
   live/trial tenant through `_pg_cursor`, §4.6) and classify the unknown ids once more.
4. Split the payload — `services/relay.py:split_payload(channel, payload, classify)` returns
   `{'local': sub, 'unknown': sub, 'tenants': {slug: sub}}` where `sub` is
   `{'object': payload.get('object'), 'entry': [...]}` holding ONLY the entries (fb) / the entries
   with only the changes (whatsapp) that belong to that bucket. An entry with no surviving changes
   is dropped. Pure function, no env — unit-tested in isolation.
5. **local**: for each local resource id → `_dispatch_connection(connection, sub_local)` (exists;
   `care_channel_message.py:352`). Never pass the full payload to a local dispatch: its
   `not_ingestable` branch captures `_dump(payload)` and would copy other customers' messages into
   the master's Unrouted queue.
6. **unknown**: `care.contact.capture._capture('unknown_resource', channel,
   resource_external_id=id, raw=env['care.channel.message']._dump(sub_unknown))` — the existing
   behaviour, unchanged, on the master's Unrouted screen.
7. **tenants**: for each slug → `body = json.dumps(sub, separators=(',', ':')).encode()`,
   `signature = 'sha256=' + hmac.new(secret, body, sha256).hexdigest()` where `secret` is the
   master meta app's `_get_secret()`; `services/relay.py:forward(env, tenant, channel, body,
   signature)` (§4.5). Success → `tenant.last_forward_at = now`, audit `relay_forwarded`
   (detail `'<slug> <channel> <n> entries'`). Failure → create `channel.relay.delivery`
   (body encrypted with `channel_crypto.encrypt(env, body.decode())`), audit `relay_failed`
   with the redacted error and the slug. Both audit writes use `su` env, `channel=channel`.

Nothing from the payload — no phone number, no wa_id, no text — may appear in a log line, an
audit detail, or a `last_error`. Counts and slugs only.

### 4.4 Hub sign-in router — `controllers/oauth_relay.py`

```python
class RelayOauthController(ChannelHubOauthController):
    @http.route('/channel_hub/oauth/callback/<string:provider>', type='http', auth='public',
                website=False, methods=['GET'], csrf=False, save_session=False)
    def oauth_callback(self, provider, **params):
        if provider == 'meta':
            slug = request.env['channel.relay.tenant'].sudo()._slug_from_state(params.get('state'))
            if slug:
                if self._rate_limited():
                    return self._page('health_care_command_channels.oauth_generic')
                url = '%s%s?%s' % (tenant_url, META_CALLBACK_PATH,
                                   request.httprequest.query_string.decode('latin-1'))
                audit relay_routed_signin (detail = slug only)
                return werkzeug.utils.redirect(url, 302)   # pass EVERY param verbatim
        return super().oauth_callback(provider, **params)
```

`_slug_from_state(state)`: `None` unless `state` is a str containing `~`; `slug = state.split('~',
1)[0]`; must match `^[a-z0-9]{1,40}$` AND be an ACTIVE `channel.relay.tenant` row (that table is
the allowlist — nothing else may be redirected to; an open redirect on an OAuth callback is a
phishing primitive, §7.3). The master's own sign-ins carry no `~` → `super()` handles them locally.
Never log or store `code`/`state`; the audit detail is the slug and nothing else.

`tenant_url` = `env['biz.tenants']._tenant_url(slug)` — always https, always the platform
address (customer-owned domains do not exist yet, `biz.tenant.domain` kind `platform` only).

### 4.5 Forwarding transport and the retry queue — `services/relay.py` + cron

`forward(env, tenant, channel, body, signature)`:

- `base = icp.get_param('channel_relay.forward_base') or 'http://127.0.0.1:%s' % service._http_port()`
  — loopback, cloned from `_probe`; the param exists for tests and for a future second box.
- `requests.post(base + '/care_channels/meta/%s/webhook' % channel, data=body, headers={
  'Host': tenant.host, 'Content-Type': 'application/json', 'X-Hub-Signature-256': signature,
  'X-Forwarded-Proto': 'https', 'User-Agent': 'carejiox-relay/1'}, timeout=RELAY_TIMEOUT)` with
  `RELAY_TIMEOUT = 8` (a worker must never hang on a slow customer; Meta's own client timeout is
  short and we answer Meta 200 regardless).
- 2xx → True. Anything else (status ≥ 300, `requests.RequestException`) → raise
  `RelayError('HTTP <code>' | 'network error: …')`. **A 403 from the customer means their copy of
  the secret is missing or stale** — it is queued like any other failure; the reconcile cron fixes
  the secret and the retry lands.

Retry cron `ir.cron` "Channel relay: retry deliveries", every 1 minute, `_cron_retry()`:
`state='pending' AND next_at <= now`, oldest first, limit 200 per run; decrypt body, re-use the
stored signature, `forward()`; success → `delivered`, `body_enc=False`, `delivered_at=now`;
failure → `attempts += 1`, `next_at = now + BACKOFF[min(attempts, len-1)]` with
`BACKOFF = (60, 300, 900, 3600, 6*3600, 12*3600)`; after `attempts >= 8` (≈ 24 h) → `dead`,
body KEPT for the operator's Retry button. Purge cron daily: delivered older than 7 days and dead
older than 7 days are unlinked (body gone with the row). Each delivery runs in its own savepoint;
one bad row never stops the run. `relay_failed`/`relay_forwarded` audit on each transition.

Why we own the retry instead of answering Meta 5xx: a non-2xx makes Meta retry the WHOLE batch
(duplicates for the customers it did reach — dedupe absorbs that, but every retry re-runs every
customer) and, worse, **Messenger disables the app's webhook after sustained failures** — one
broken customer would switch off every customer's inbox. Always 200 after verification, and the
queue is ours.

### 4.6 Reconcile — the route table and the credentials push (`models/relay_tenant.py`)

`channel.relay.tenant._reconcile(push_credentials=True)` — `@api.model`, used by the 10-minute
cron "Channel relay: reconcile customers", by `_maybe_resync` (routes only, `push=False`) and by
the operator button (§4.7). Requires `biz.tenants.service` (import guarded like
`health_tenancy/models/registrations.py`'s top — but this module DEPENDS on `biz_tenants`, so an
unguarded import is fine; guard only against a missing `biz.tenant` model in tests).

1. **Tenants**: for every `biz.tenant` with `state in ('live','trial')` ensure an active
   `channel.relay.tenant` (create/reactivate, copy `name`); archive rows whose tenant is not in
   that set. The master itself never gets a row.
2. **Routes** (every tenant, via `service._pg_cursor(slug)` — READ ONLY, autocommit):
   `SELECT channel, resource_external_id FROM care_channel_connection WHERE active AND
   resource_external_id IS NOT NULL AND channel IN ('whatsapp','fb')`. Guard on the table existing
   (a customer behind on modules) — skip with a warning, never fail the run. Upsert routes; delete
   routes for that tenant no longer returned. If two tenants return the same
   `(channel, resource_external_id)`: keep the FIRST seen, record
   `last_error = "Page/number <id> is connected by two customers: <a>, <b>"` on the second, and
   audit `relay_failed` — never let routing become a coin flip. Set `seen_at`.
3. **Credentials** (only when `push_credentials`): read the master's active `meta` platform app
   (`_get_for_provider('meta')`); if it has no `client_id` or no secret → skip with a warning. For
   each tenant, `with service._tenant_env(slug) as tenv:` — a full env on the customer's registry:
   - find the customer's active `channel.platform.app` meta row (`_get_for_provider`), create one
     if absent (`provider='meta'`);
   - write `client_id`, `extra_json` (copy the master's whole extra_json string — verify_token,
     es_config_id, flb_config_id travel together; a customer's own extra keys do not exist, this
     row is platform property), `client_secret_enc = channel_crypto.encrypt(tenv, secret)`
     (**`tenv`, not `self.env`** — §3.1: per-database keys), `secret_hint` exactly as
     `action_set_secret` computes it (`:514`), `environment_note = 'Pushed by the platform'`;
     skip the write entirely when `client_id`, `extra_json` and `secret_hint` already match
     (no needless secret churn, no audit noise);
   - set `tenv` param `channel_hub.oauth_redirect_base` = the platform URL
     (`service._platform_url()`), so the customer's Messenger sign-in returns to the master (§6.2);
   - audit `secret_rotated` on the customer (detail `'pushed by the platform'`) when the secret
     changed;
   - on the master row: `credentials_pushed_at = now`, `pushed_secret_hint`, clear `last_error`.
   Any exception for one tenant → `last_error = redact(exc)`, audit `relay_failed`, continue with
   the next. `_tenant_env` commits on the customer side; the master's own writes commit with the
   cron. A registry load costs ~11 MB (SAAS H4a) — acceptable every 10 min for a handful of
   customers; note it in the report if the fleet grows.

`_maybe_resync(reason)`: if `now - last_resync_at < 60 s` return False; else set the param and run
`_reconcile(push_credentials=False)` inside a savepoint; never raise.

### 4.7 Operator surface (master only, `base.group_system`)

Two list views + one form each, under `health_care_command_channels.menu_channel_platform_app`'s
parent menu (read `views/menus.xml:1-30` for the parent xmlid), sequence after it:

- **"Customer relay"** — `channel.relay.tenant` list: Customer, Address, In step (boolean),
  Credentials pushed, Routes, Last message forwarded, Waiting to retry, Last problem. Header
  buttons: **"Send the Meta app to every customer now"** (server action →
  `_reconcile(push_credentials=True)`, then a `display_notification` with counts) and **"Re-read
  who owns which Page and number"** (`_reconcile(False)`).
- **"Relay deliveries"** — `channel.relay.delivery` list filtered to pending/dead by default:
  Customer, Channel, Entries, Attempts, Next try, State, Last problem. Row button **"Retry now"**
  (`action_retry_now` → `next_at = now`, `state='pending'`). No field ever shows the body.

Plain-English labels; the help text on `in_step` says what it means in words the operator uses
("This customer holds the same Meta app id and secret as the platform").

### 4.8 The client — `health_channel_relay`

Depends on `health_care_command_channels`, `biz_tenancy`. One model file:

```python
class CareChannelOauthSession(models.Model):
    _inherit = 'care.channel.oauth.session'

    @api.model
    def _mint_state(self):
        state = super()._mint_state()
        slug = (self.env['ir.config_parameter'].sudo().get_param('biz_tenancy.slug') or '').strip()
        if slug and re.fullmatch(r'[a-z0-9]{1,40}', slug):
            return '%s~%s' % (slug, state)
        return state
```

That is the whole client. On the master `biz_tenancy.slug` is unset → plain state → the hub
handles the master's own sign-ins locally. `~` is not in the urlsafe-base64 alphabet, so the split
is unambiguous. A `post_init_hook` is NOT needed: the redirect base param is pushed by the hub.

## 5. Safety rails

1. **Signature before anything** — the relay POST verifies with the master's secret exactly as
   the parent does, and re-signs each split with the same secret. A customer's route stays
   fail-closed: no secret → 403 → queued.
2. **Only the customer's own entries leave the master.** `split_payload` is the boundary; T3–T6
   assert no foreign entry survives. Whole-body forwarding is forbidden (it would ship one
   customer's PHI to another's server).
3. **Redirect allowlist = active `channel.relay.tenant` rows.** Nothing else, ever. The slug regex
   is defence in depth, not the gate.
4. **No PHI on the master except encrypted, in the retry queue, for a failed delivery**; cleared
   on delivery; purged in 7 days. `_dump` of unknown-resource captures is existing behaviour and
   holds only entries nobody owns.
5. **Never `_tenant_env` from a public route** — registries are loaded by the cron/button only.
6. **Every audit detail is slug + channel + counts.** No ids of people, no message text, no
   codes, no states, no tokens.
7. **Cross-database env writes only through `service._tenant_env`** (rail R5) and reads through
   `_pg_cursor`; never `odoo.sql_db` directly.
8. **Public routes are not oracles**: same generic 403/200 as the parent; a request for an unknown
   slug in `state` falls through to the parent's generic page.
9. A clone of the master used for rehearsal MUST have its `biz_tenant` rows neutralised first
   (H102) or the reconcile cron will push credentials onto the real `hhh`.

## 6. Sanctioned edits to `health_care_command_channels` (exhaustive)

1. `models/care_channel_oauth_session.py` — extract `_mint_state()` (`@api.model`, returns
   `secrets.token_urlsafe(32)`) and call it from `create_for` at `:155`. Docstring: "the string is
   opaque to everything but `_consume`; a client may prefix it".
2. `services/adapters.py:688-689 _MetaAdapterBase._redirect_uri` — `base =
   icp.get_param('channel_hub.oauth_redirect_base') or self._base_url()`; strip/rstrip('/').
   Both `authorize_url` and `exchange_code` already go through it.
3. `models/channel_platform_app.py:266-271 _compute_go_live_urls` and
   `models/channel_golive.py:913- _golive_urls` — for provider `meta` only, the redirect uses the
   same param when set (so a customer's row shows the platform address, and the master — where
   the param is never set — is unchanged).
4. `models/care_channel_audit.py:29 KNOWN_EVENTS` += `'relay_forwarded', 'relay_failed',
   'relay_routed_signin', 'relay_pushed'` with a two-line comment.
5. `__manifest__.py` version → `19.0.11.3.0`; a release note line in the description.
6. `i18n/vi.po` — msgids for any NEW translatable string you add in these files (there should be
   none; the param has no label).

Nothing else in that module changes. Do not touch `controllers/meta.py`, `controllers/oauth.py`,
`care_channel_message.py`, `care_channel_connection.py`.

## 7. Test cases (numbered; every one runs green before deploy)

`biz_platform_channel_relay/tests/` — TransactionCase `RelayCase` clones `ChannelHubCase`'s
archiving setup and creates a master meta app with a known secret via `action_set_secret` (the
test user holds `base.group_system` as in `common.py:64-67`). `biz.tenant` rows are created by the
test (`slug`, `name`, `state='live'`); `_pg_cursor`/`_tenant_env`/`requests.post` are patched with
plain functions.

- **T1** `split_payload` fb: three entries for pages A (local), B (tenant x), C (unknown) →
  buckets hold exactly one entry each, `object` preserved, input dict not mutated.
- **T2** `split_payload` whatsapp: one entry with two changes for phone numbers P1 (tenant x) and
  P2 (tenant y) → each tenant sub-payload has one entry with ONE change; the other change is
  absent (assert by phone_number_id AND by absence of the other's `messages`).
- **T3** an entry whose every change belongs elsewhere is dropped (no empty `changes` lists).
- **T4** `_route_meta` with a routed page: `requests.post` mock receives `Host = <slug>.<apex>`,
  body = compact JSON of the sub-payload only, header `X-Hub-Signature-256` equal to
  `sha256=HMAC(master secret, body)`; counter `forwarded == 1`; audit `relay_forwarded` delta +1
  with the slug in `detail_redacted` and NO page id / sender id in it.
- **T5** local + tenant in one batch: the local connection ingests (assert via the existing
  `care.channel.message` row or a patched `_dispatch_connection` receiving a payload with ONLY
  the local entry), and the forward body contains only the tenant's entry.
- **T6** unknown id → `care.contact.capture` row `unknown_resource` with the unknown sub-payload
  only; `_maybe_resync` called once (patched) and NOT again within 60 s on a second call.
- **T7** forward failure (mock raises `requests.ConnectionError`) → a `channel.relay.delivery`
  pending row with `body_enc` starting `chs$1$`, `entry_count`, `attempts 0`, `next_at` ≈ now;
  audit `relay_failed`; `_route_meta` still returns (never raises).
- **T8** forward 403 → same as T7 (queued), `last_error` contains `403` and nothing else from the
  response body beyond redaction.
- **T9** `_cron_retry`: pending row → mock success → `delivered`, `body_enc False`,
  `delivered_at` set; the re-sent body equals the decrypted original and carries the stored
  signature.
- **T10** backoff: 3 consecutive failures → `attempts 3`, `next_at` ≈ now + 900 s; after 8 → `dead`
  and `body_enc` still present.
- **T11** purge: delivered 8 days ago and dead 8 days ago are unlinked; pending is not.
- **T12** `_reconcile(False)` creates `channel.relay.tenant` for live/trial tenants only, archives
  one that became `paused`, upserts routes from the mocked SQL rows, deletes a route that
  disappeared, and on a duplicate resource across two tenants keeps the first and writes
  `last_error` on the second.
- **T13** `_reconcile(True)` with a mocked `_tenant_env` yielding a real env on the SAME test
  database (acceptable stand-in: the mock yields `self.env` and the test asserts the writes on the
  local `channel.platform.app` row after archiving the master's own row in the mock context — or
  yields an env whose `channel.platform.app` is a fresh row): client_id, extra_json, secret_hint
  copied; `client_secret_enc` decrypts (with the SAME env's key in this stand-in) to the master's
  plaintext; `channel_hub.oauth_redirect_base` param written; `credentials_pushed_at` set;
  `in_step True`. A second run makes NO further write (patch `write` and count).
- **T14** `_reconcile(True)` when the master has no secret → no push, warning, no exception.
- **T15** `_slug_from_state`: `'hhh~abc'` with an active relay tenant `hhh` → `'hhh'`;
  `'zzz~abc'` (no tenant) → None; `'abc'` → None; `'HHH~x'` → None; `'../~x'` → None;
  `None`/`123` → None.
- **T16 (HttpCase)** POST `/care_channels/meta/fb/webhook` with a body for a routed page and a
  correct signature → 200, and the patched `requests.post` was called once with the split body
  (patch at `odoo.addons.biz_platform_channel_relay.services.relay.requests.post`); a wrong
  signature → 403 and no call; a body for an unknown page → 200 and a capture row. Assert audit
  DELTAS.
- **T17 (HttpCase)** GET `/channel_hub/oauth/callback/meta?code=X&state=hhh~abc` with an active
  relay tenant → 302 `Location` = `https://hhh.<apex>/channel_hub/oauth/callback/meta?code=X&state=hhh~abc`
  (verbatim query); with `state=abc` → 200 and the parent's generic page; the redirect audit
  detail contains `hhh` and NOT `X`.

`health_channel_relay/tests/`:

- **T18** with `biz_tenancy.slug = 'hhh'`: `create_for` returns state `hhh~…`, stored
  `state_hash = sha256(full state)`, `_consume(full state)` returns the session; with the slug
  unset the state has no `~`; with slug `'Bad Slug'` no prefix.

`health_care_command_channels` (existing suites must stay green):

- **T19** `_redirect_uri()` returns `<param>/channel_hub/oauth/callback/meta` when
  `channel_hub.oauth_redirect_base` is set and the `web.base.url` form otherwise; `exchange_code`'s
  mocked `_get` receives the same value; `_compute_go_live_urls` for meta follows it and zalo does
  not.
- **T20** the whole `/health_care_command_channels` suite passes (baseline count in the report).

## 8. Deploy + verify (ONE sitting — rail R3: new code in the shared tree + master upgraded +
customer not upgraded = 500 for the customer)

0. **Rehearse on a practice copy first** (`docs/SAAS_RUNBOOK.md` §"practice copy"): clone
   `carejiox` → `carejiox_r1`, **neutralise its `biz_tenant` rows** (`UPDATE biz_tenant SET
   state='draft'`) and switch its crons off (H102/H78), install both new modules + upgrade the
   channels module with tests, via the `systemd-run` form on ports 8199/8299 with
   `--db-filter='^carejiox_r1$'` and its own logfile (H77 — never `carejiox-deploy -t`). Read
   `odoo.tests.result`; confirm `Starting .*Http` count > 0. Drop the copy when green.
1. `scp -qr biz_platform_channel_relay health_channel_relay health_care_command_channels VietUcUAT:/tmp/`
   (after `ssh VietUcUAT 'rm -rf /tmp/{those}'`).
2. Master: `carejiox-deploy -d -i biz_platform_channel_relay,health_channel_relay -m health_care_command_channels`.
3. Template: `carejiox-deploy -D carejiox_template -i health_channel_relay -m health_care_command_channels`,
   then `sudo -u postgres psql -d carejiox_template -Atc "select count(*) from ir_cron where active"`
   → must be 0 (switch off again if not).
4. `hhh`: `carejiox-deploy -D hhh -i health_channel_relay -m health_care_command_channels`.
   Then `curl -s -o /dev/null -w '%{http_code}' -H 'Host: hhh.carejiox.com' http://127.0.0.1:8069/web/login` → 200.
5. On the master, press **"Send the Meta app to every customer now"** (or run `_reconcile(True)`
   via `carejiox-deploy -x`). Verify on `hhh`: `select provider, client_id, secret_hint,
   extra_json from channel_platform_app` matches the master; param
   `channel_hub.oauth_redirect_base = https://carejiox.com`.
6. **Meta console (the operator, plain steps in the report):** in the Meta app, under Facebook
   Login for Business → Settings, keep the master's redirect URI (already there); under App
   settings → Basic add `carejiox.com` to **App Domains**; under Facebook Login → Settings turn
   on **Login with the JavaScript SDK** and add `carejiox.com` and `hhh.carejiox.com` to **Allowed
   Domains for the JavaScript SDK**. Then test WhatsApp's Connect on `hhh` — note whether the
   JS SDK accepted `hhh.carejiox.com` only because it was listed explicitly (try removing it after
   the first success and pressing Connect again; report which). This decides R2.
7. **Live proofs** (all from `hhh`'s Channel Center, as `owner@hhh.carejiox.com`): Messenger
   Connect → the popup returns through `carejiox.com` → lands on `hhh` → Page picker shows pages
   (needs `flb_config_id` on the master — Studio step 6; if it is still empty, prove the redirect
   hop with a synthetic `state` via T17's URL against the live master instead and say so).
   WhatsApp Connect likewise when `es_config_id` exists. Send a real message to the connected
   Page/number → master log shows `relay … forwarded 1`, `hhh` audit shows `inbound_ok`, the
   conversation appears in `hhh`'s Care Command, and NOTHING appears in the master's Unrouted
   queue.
8. Every step above that could not be proven live (App Review pending, config ids empty) goes in
   the report as "not proven, because …", never as done.

## 9. Report back

- Test counts per module and the baseline count of the channels suite before/after.
- The exact SQL rows on `hhh` after the push (client_id, hint, extra keys — never the secret).
- Which Meta console screens were touched and the JS-SDK subdomain finding (step 6).
- Registry-load cost observed for `_tenant_env` on the box (`free -m` before/after a reconcile).
- Any place where the plan and the code disagreed, and what you did (deviation list, D1…).
- New ledger entries for `HANDOVER-CONVENTIONS.md` §5 (number them after the last existing §5.x),
  written in the ledger's voice, for every trap you hit.
- Anything user-visible you added: list every string, confirm none says "Odoo".
