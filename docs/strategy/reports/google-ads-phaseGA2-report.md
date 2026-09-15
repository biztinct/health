# GA2 — Google Ads: reporting sign-in, encrypted credentials, read-only client, account discovery — implementation report

Handover: `docs/strategy/handovers/google-ads-phaseGA2.md`
Design: `docs/strategy/google-ads-channel-design.md` §7.1, §7.2, §9, §12
Conventions: `docs/strategy/HANDOVER-CONVENTIONS.md`
Previous phase: `docs/strategy/reports/google-ads-phaseGA1-report.md`

---

## 0. Outcome in one line

A clinic operator can now press **Connect Google account**, be sent to Google
with the right permission and the right return address, and — once a real
Google application and developer token exist — choose the advertising account
and have this system prove it can read it. Everything is built, deployed to all
three databases and covered by 52 new tests. **Live sign-in is unverified**,
because no real Google credential exists yet (§7).

---

## 1. Deployment

| Item | Value |
|---|---|
| Start commit | `03103e07` (Make VoIP24h setup fail-safe) — the tip of `19.0` when this phase began |
| This phase's commit | the ONE commit named `feat(google-ads): GA2 — …`, the tip of `19.0`. Not pushed (the orchestrator pushes at the end of the programme). |

| Database | health_google_ads |
|---|---|
| carejiox | **19.0.2.0.0 installed** |
| carejiox_template | **19.0.2.0.0 installed** |
| hhh | **19.0.2.0.0 installed** |

- `carejiox_template` active `ir_cron` count after the ritual: **0**.
  The upgrade DID re-activate one — **cron id 79, `Google Ads: purge sign-in
  sessions`, this phase's own** (§5.178's shape, this time correctly
  attributed). Re-disabled with `UPDATE ir_cron SET active = false` and
  re-verified at **0** after every subsequent template upgrade.
- `carejiox_template`: **0** `google_ads_platform_config` rows, **0**
  `google_ads_account` rows, **0** `google_ads_oauth_session` rows. Same on
  `hhh` and on `carejiox` after QA teardown.
- `"some depends are not loaded" / "Some modules are not loaded"` grep: **no
  entry dated 2026-09-15**. The only hit in the whole log is the historical
  2026-09-06 line for `carejiox_r1`, which predates GA1.
- `/web/login` after the final restart: **HTTP 200** for `Host: carejiox.com`
  and **HTTP 200** for `Host: hhh.carejiox.com`.
- The practice clones `vietuat` and `codex_fb_center_reply` were **not**
  touched, upgraded or tested against. No `service odoo-server` or `pkill` was
  run by hand; every step went through `carejiox-deploy`.

---

## 2. Files

### New in `addons/health_google_ads` (19.0.1.0.0 → 19.0.2.0.0)

```
services/google_ads_client.py            API_VERSION v25, GoogleAdsError,
                                         _http_get/_http_post_json/_http_post_form,
                                         GoogleAdsClient (read-only, fixed queries)
models/google_ads_platform_config.py     google.ads.platform.config +
                                         google.ads.platform.secret.wizard
models/google_ads_oauth_session.py       google.ads.oauth.session (+ purge cron)
models/care_channel_oauth_session.py     the _handle_callback dispatch override
models/google_ads_select_wizard.py       google.ads.account.select (+ .line)
views/google_ads_platform_config_views.xml
views/google_ads_select_wizard_views.xml
data/ir_cron.xml                         one daily purge job, noupdate=1
tests/test_platform_config.py            GA2-T01, T02, T16, T17
tests/test_oauth.py                      GA2-T03 … T06, T14, T15
tests/test_discovery.py                  GA2-T07 … T09
tests/test_client.py                     GA2-T10 … T13
```

### Edited in `addons/health_google_ads`

- `models/google_ads_account.py` — eight new fields, `EVIDENCE_FIELDS` extended
  by eight names, `_internal()`, `_check_company_scope()`,
  `_reporting_access_token()` (advisory lock), `_provider_vals`,
  `_validate_reporting_access`, `_discover_reporting_candidates`,
  `_reporting_messages` / `_reporting_message_for` / `_reporting_failure`,
  `_google_client`, and the five public actions. The Center card's reporting
  label map and tone map.
- `views/google_ads_account_views.xml` — the Campaign reporting page (buttons
  per state, the read-only paragraph, Connection + Advertising account groups),
  the statusbar's visible states, `login_customer_id` made readonly.
- `security/ir.model.access.csv` — 14 new rows (§5 below).
- `data/cms_sidebar_items_google_ads.xml` — one new ADMIN leaf.
- `__manifest__.py`, `i18n/vi.po` (+110 entries), `tests/common.py`,
  `tests/__init__.py`, `models/__init__.py`, `services/__init__.py`.

**No other module was edited.** In particular `health_care_command_channels`
was not touched: the callback seam is the ORM override alone (§3, D1).

---

## 3. Deviations

### D1 — the `_handle_callback` dispatch worked, with no channels edit at all *(the handover's main open question)*

`health_google_ads/models/care_channel_oauth_session.py` inherits
`care.channel.oauth.session` and overrides `_handle_callback(provider,
params)`: `provider == 'google_ads'` goes to our own session model, everything
else `super()`s. The public route, its rate limiting and its four rendered
pages are reused untouched, the relay hub still bounces only `meta`, and the
suites drive the callback **through the dispatcher** rather than around it
(`test_oauth.py::_callback`). Proven live in the browser pass, step 11.

### D2 — the reporting-failure answer has two shapes, not one

The handover asks for the evidence write AND a `UserError` on every failure.
Those two cannot both hold: ledger §5.65 — a `UserError` from an RPC rolls back
the very write that explains it. So:

* `needs_reconnect` (the grant is gone; the account MUST end up in
  `action_required`) → the state is written and a **sticky warning
  notification** is returned. The write survives, the operator still sees the
  message. Proven live: browser step 13, statusbar *Action required*,
  *Last Error Code* `invalid_client`.
* every other failure (nothing durable has changed) → evidence written, then
  `UserError` as specified. The docstring says plainly that an RPC's rollback
  takes that evidence with the error.

Interfaces are unchanged; `GA2-T08c` and `GA2-T11` assert both shapes.

### D3 — the advisory-lock kernel gained a savepoint

The §4.4 kernel is otherwise verbatim (only `_http_post_form` is reached
through the client module, see D4). Added: the two lock statements run inside
`with self.env.cr.savepoint():`. A lock timeout **aborts the PostgreSQL
transaction**, so without it the caller's `except GoogleAdsError('busy')`
inherits a transaction in which every later statement — including the evidence
write that explains the failure — dies with *"current transaction is aborted"*.
Rolling back to the savepoint restores a usable transaction; `RELEASE` on the
happy path hands the lock up to the parent, so the mutual exclusion is
identical. `GA2-T12` takes the lock from a real second connection and then
keeps using the test transaction, which is only possible because of this.

**The psycopg2 class used is `psycopg2.errors.LockNotAvailable`** — verified on
the server before relying on it (`python3 -c "import psycopg2.errors as e;
print(e.LockNotAvailable)"` → `<class 'psycopg2.errors.LockNotAvailable'>`), so
the `exc.pgcode == '55P03'` fallback was not needed.

### D4 — HTTP primitives are called through the client module

`google_ads_client._http_post_form(...)`, not a bare `_http_post_form` imported
into the model. A `from X import Y` binding cannot be reached by
`patch.object(google_ads_client, '_http_post_form', fn)`, and §7 of the
handover requires exactly that patch (§5.76: plain functions, never
`autospec`). Inside the client module itself the bare name is a module global
and resolves at call time, so it is left as written.

### D5 — the card label map lives in `google_ads_account.py`

The handover's §5 file list says `models/channel_center.py (label map only)`.
That file is four lines of seam; the reporting label map is in
`_center_card_payload()` in `models/google_ads_account.py` (GA1's D-free
structure). Edited there; `channel_center.py` needed no change.

### D6 — `login_customer_id` became internal-write-only and readonly

Handover §4.3 puts it in the internal-write-only set. It was a typeable field
in GA1. It is now written only by the account-selection step and shown
readonly, with the reasoning in the view: *an id typed into a form establishes
no access at all* (design §7.1). No GA1 test wrote it, so nothing broke.

### D7 — the URL-bar screenshot is a network capture instead

Handover §8 asks for a screenshot of the URL bar on `accounts.google.com`.
Google 302s off the authorization URL instantly, so the landing URL no longer
carries `redirect_uri`, and the CDP screenshot API captures the page, not the
browser chrome. The evidence pack instead carries the **full authorization
request read out of the browser's own network log**
(`10b-authorization-url.txt`) plus the Google refusal screen
(`10-google-signin-invalid-client.png`). That is strictly more than a URL bar
would have shown.

### D8 — one fix found by driving the screen (`_with_reload` on the secret wizard)

Storing a secret left the form showing *"Sign-in secret — to do"*, because the
checklist and both hints are non-stored computes and the wizard answered with a
notification alone — it reads as a failure. Fixed with the same `_with_reload`
posture the account's buttons already use, redeployed to all three databases,
and re-driven (evidence step 07).

### D9 — one stray file removed from the server's addons tree

`/odoo/odoo-server/addons/health_care_command/i18n/._vi.po` — a 163-byte macOS
AppleDouble artifact dated 2026-09-10, **not in the repo**, left by an earlier
`scp`. It made `health_base`'s i18n gate **unrunnable**: `test_g1c` failed on
it and `test_g1b`, `test_g2`, `test_g2b` all ERRORed trying to read it as
UTF-8. Deleted from the server (no module edit — the file exists in no
module's source); the gate then ran clean. It is the only `._*` file under the
addons tree; 20-odd `.DS_Store` files remain and are harmless because nothing
parses them.

---

## 4. Tests

### 4.1 The master run, verbatim

```bash
ssh VietUcUAT 'carejiox-deploy -m health_google_ads,health_care_command_channels,health_web_leads \
  -t /health_google_ads,/health_web_leads,/health_care_command_channels'
```

Result lines (PID 3458691):

```
2026-09-15 04:13:11,923 3458691 INFO carejiox odoo.tests.stats: health_care_command_channels: 264 tests 54.96s 40219 queries
2026-09-15 04:13:11,924 3458691 INFO carejiox odoo.tests.stats: health_google_ads: 117 tests 32.07s 18974 queries
2026-09-15 04:13:11,924 3458691 INFO carejiox odoo.tests.stats: health_web_leads: 88 tests 18.75s 13622 queries
2026-09-15 04:13:11,924 3458691 ERROR carejiox odoo.tests.result: 2 failed, 0 error(s) of 395 tests when loading database 'carejiox'
```

Executed-METHOD count (§5.83/§5.90, scoped to the run's PID per §5.92):

```bash
sudo grep -a "3458691" /var/log/odoo/odoo-server.log | grep -ac "Starting Test.*\.test_"
395
```

**395 executed methods = 395 reported tests**, so nothing silently failed to
run. Per module: `health_care_command_channels` 220, `health_google_ads` 101,
`health_web_leads` 74, plus `health_cron` and `health_strip_and_state`.
This phase's own 52 methods (`test_ga2*`) all ran and **none is among the
failures**:

```bash
sudo grep -ao "3458691.*Starting Test[A-Za-z0-9]*\.test_ga2[a-z0-9_]*" … | wc -l   # 52
sudo grep -a "3458691" … | grep -aiE "FAIL:|ERROR:" | grep -ac ga2                # 0
```

### 4.2 The two failures are NOT this phase's — proved with a pristine baseline

```
FAIL: TestCallCenter.test_153_the_calls_card_is_receive_only_and_says_so
FAIL: TestChannelCenter.test_97_center_overview
```

Both assert `'cannot verify'` appears in the Calls card's notice. Commit
**`03103e07` "Make VoIP24h setup fail-safe"** (authored today at 13:23 +1000,
in a different work stream) rewrote `_center_call_notice` in
`health_care_command_channels/models/channel_center.py` to

> *"…need a separate VoIP24h API contract, which is not configured here — so we
> do not offer them. Confirm the webhook contract with VoIP24h before the
> appointment."*

and updated `tests/test_call_center.py` only partially, leaving these two
assertions on the old wording.

**Baseline run** (§5.133 recipe): GA1's `health_google_ads` restored onto the
server from `git archive faee5a2f`, same three tags, same database:

```
2026-09-15 03:44:19,355 3440360 ERROR carejiox odoo.tests.result: 2 failed, 0 error(s) of 343 tests when loading database 'carejiox'
  FAIL: TestCallCenter.test_153_the_calls_card_is_receive_only_and_says_so
  FAIL: TestChannelCenter.test_97_center_overview
```

Identical count, identical names, with GA2's code absent. GA2 then re-deployed:
same two, plus 52 new green methods. **GA2 regresses nothing.**

**Not fixed here, deliberately**: this session's instructions say *"Edit ONLY
health_google_ads … Do not edit health_care_command_channels"*, and that file
belongs to a work stream that touched it minutes ago. The fix is two string
literals:

```
health_care_command_channels/tests/test_center.py:133
health_care_command_channels/tests/test_call_center.py (test_153)
  assertIn('cannot verify', …)  →  assertIn('not configured here', …)
```

### 4.3 The vi.po gate

```bash
ssh VietUcUAT 'carejiox-deploy -m health_base -t /health_base:TestI18nCatalogueShape,/health_base:TestI18nCatalogueLoads'
2026-09-15 03:52:44,567 3446585 INFO carejiox odoo.tests.result: 0 failed, 0 error(s) of 5 tests when loading database 'carejiox'
```

110 entries added to `health_google_ads/i18n/vi.po` (100 → 210 msgids, **0
duplicates**): 56 python strings with `#. odoo-python` + a
`#: code:addons/health_google_ads/…:0` occurrence, 31 field labels, 5 model
names, 6 selection values, 15 view-arch terms and one three-occurrence entry
for the new menu / action / sidebar leaf. It took the run in §4.2's first
attempt to expose D9 — without removing that stray file the gate could not run
at all.

### 4.4 The GA2 test table

| ID | File | Covered by |
|---|---|---|
| T01 | `test_platform_config.py` | `test_ga2_t01a` … `t01g` — encryption, hints, the short-secret rule, ACL, the two setters' gate, empty refusal, the one-active rule, `_ready()` |
| T02 | `test_platform_config.py` | `test_ga2_t02`, `t02b` — the Center payload and an operator `read()` carry none of the fixture values nor `chs$1$`; `access_token_enc` is unreadable without `base.group_system` |
| T03 | `test_oauth.py` | `t03a` (no application → `UserError`, state unmoved, no session), `t03b` (every authorization parameter, the hashed state, PKCE encrypted), `t03c` (an http return address is refused) |
| T04 | `test_oauth.py` | `t04a` unknown, `t04b` replay, `t04c` expired + labelled, `t04d` our state on provider `meta` → generic and our session untouched |
| T05 | `test_oauth.py` | `t05a` denied → `not_connected`; `t05b` a cancelled RECONNECT leaves a working account `connected` |
| T06 | `test_oauth.py` | `t06a` tokens encrypted, expiry = now+expires_in−60, `authorized_by`, `select_account`, the exchange carried the verifier the challenge was minted from and the same return address; `t06b` HTTP 400 → nothing stored; `t06c` `no_refresh_token`; `t06d` a re-consent keeps ours; `t06e` `scope_missing` |
| T07 | `test_discovery.py` | `t07a` M+D walked, C2 (manager) and C3 (hidden) dropped, C4 kept with its CANCELED status; `t07b` `login-customer-id` present on the children call and absent on direct ones; `t07c` the wizard lines; `t07d` no grant → no listing |
| T08 | `test_discovery.py` | `t08a` a manager is refused; `t08b` C1 binds with manager context, `provider_name`/VND/timezone filled, `last_sync_success_at` still empty; `t08c` 403 `USER_PERMISSION_DENIED` → `UserError`, state unmoved, code recorded; `t08d` a non-ten-digit id never builds a URL |
| T09 | `test_discovery.py` | `t09` — refused, the message names neither the other company nor the other record, the other row untouched, Google never asked |
| T10 | `test_client.py` | `t10a` valid token → zero calls; `t10b` one refresh, `expires_in` honoured, ours preserved; `t10c` a rotated token replaces ours; `t10d` no grant at all |
| T11 | `test_client.py` | `t11` — `invalid_grant` → `action_required`, `last_error_code`, `customer_id` kept, **`website_status` still `receiving`** (a real Google-attributed enquiry is created first), and a warning rather than an exception |
| T12 | `test_client.py` | `t12` — a REAL `self.registry.cursor()` takes `pg_try_advisory_xact_lock`; the contended refresh raises `busy` inside the 5 s lock timeout and makes no token call; after the rollback the same call refreshes exactly once |
| T13 | `test_client.py` | `t13a` three pages followed; `t13b` `MAX_PAGES` → `too_many_pages`; `t13c` 429/503/network retryable; `t13d` one forced refresh then `needs_reconnect`, exactly two search calls and one refresh; `t13e` an echoed bearer token never survives into `detail_redacted`; `t13f` the read-only surface; `t13g` the pinned version and its sunset |
| T14 | `test_oauth.py` | `t14a` four token fields cleared, `customer_id`/`provider_name`/timezone/connector kept, **zero HTTP calls**; `t14b` reconnect → `authorizing`, and a fresh callback restores `connected` directly |
| T15 | `test_oauth.py` | `t15a` all five public actions refuse a plain `group_health_crm_user`; `t15b` company 2's operator is refused on company 1's account |
| T16 | `test_platform_config.py` | `t16a` the return address; `t16b` the purge cron drops a raw-SQL-backdated session and keeps a live one |
| T17 | `test_platform_config.py` | `t17` — `fields_get` of all five new models carries no forbidden brand name |

---

## 5. Security surface added

| Model | Who | Perms |
|---|---|---|
| `google.ads.platform.config` | `base.group_system` only | r/w/c/u |
| `google.ads.platform.secret.wizard` | `base.group_system` only | r/w/c/u |
| `google.ads.oauth.session` | `base.group_system` only | r/w/c/u |
| `google.ads.account.select` (+ `.line`) | CRM manager, clinic admin, healthcare admin, owner, system | r/w/c/u (TransientModel) |

Field-level: `client_secret_enc`, `developer_token_enc`, `pkce_verifier_enc`,
`access_token_enc`, `refresh_token_enc` all carry
`groups='base.group_system'`. Every `*_enc` value is a `chs$1$` AES-GCM token
(the channel recipe, per-database key — §5.172: a token encrypted on
`carejiox` cannot be decrypted on `hhh`, and GA2 never copies one across).

---

## 6. Self-review against handover §6 rails

| Rail | Implemented | Proven by |
|---|---|---|
| R1 tokens/secrets never readable | yes | `groups=` on all five `*_enc` fields; GA2-T01c/T01d (ACL + setter gate), T02/T02b (payload and operator-read dumps contain none of the fixture values nor `chs$1$`); browser step 09 shows the token fields absent for the operator persona |
| R2 the callback trusts only a consumed state | yes | GA2-T04 a–d: unknown / replayed / expired / wrong-provider all render generic, the replay never reaches Google; browser step 11 shows the live page. `code` is used once inside the exchange and is never written to a field |
| R3 provider text through `redact()` | yes | `GoogleAdsError.detail_redacted` is the only place it goes, and GA2-T13e feeds a body echoing a bearer token and asserts it does not survive |
| R4 ids are strings, no URL from anything else | yes | `GoogleAdsClient._customer_id` normalises before any URL or header; GA2-T08d and T13's `bad_customer_id` |
| R5 a manager is never the data row; a bound customer is refused anonymously | yes | GA2-T08a (validation refuses `manager=True`), T07a (the client filters managers out of the listing), T09 (the message names nobody) |
| R6 `needs_reconnect` touches nothing but reporting | yes | GA2-T11 asserts `website_status` is still `receiving` before and after; browser step 13 shows *Website Leads* unchanged while the statusbar moves to *Action required* |
| R7 disconnect clears our tokens only, no revoke | yes | GA2-T14a: four fields cleared, everything else kept, **zero HTTP calls**; browser step 15 |
| R8 fixed hosts, TLS default, timeout on every call | yes | `ADS_HOST` / `TOKEN_URL` / `AUTH_URL` are module constants, `timeout=HTTP_TIMEOUT` on all three primitives, no method takes a query string; GA2-T13f/T13g |
| R9 no blocking sleep | yes | there is no `sleep` in the module (`grep` clean); the only wait is PostgreSQL's own 5 s `lock_timeout` |
| R10 template: no config row, no tokens, cron count 0 | yes | §1 — 0/0/0 rows on `carejiox_template`, active cron count 0 after every upgrade of it |

**Rails I could not prove:** none by test. What is **unproven by live
evidence** is the half that needs a real Google credential: that a genuine
sign-in returns a refresh token, that discovery lists a real hierarchy, and
that validation passes against a real advertising account. §7 says what is
needed. Everything up to Google's front door is proven live (browser steps
10, 13).

---

## 7. What is live, and what is not

| Capability | Live status right now | Why |
|---|---|---|
| **Website leads** | *Setup needed* (no account exists on any database) | unchanged by GA2 |
| **Campaign reporting** | *Not connected* on every database | there is no platform application row anywhere: the QA one was deleted. With one in place, the flow runs as far as Google's sign-in screen — verified — and no further without a real application id |
| **Google lead forms** | *Unavailable for healthcare ads* | Google's policy, unchanged by GA2 |
| **Card chip (aggregate)** | *Setup needed* | needs a real website lead AND connected reporting |

**Verified live:** the authorization request (exact return address, adwords
scope, offline + consent, PKCE S256, one-time state), Google receiving and
answering it, the public callback page, a real call to
`https://oauth2.googleapis.com/token`, the refusal mapping to plain words and
`action_required`, and disconnect.

**Unverified, for lack of credentials:** a completed sign-in, the account
listing, and validation against a real advertising account. §5.182 applies and
is respected — stored credentials are not treated as proof of a completed
callback anywhere in this code.

### Pinned API version

| Item | Value |
|---|---|
| Version | **v25** (`google_ads_client.API_VERSION`) |
| Released | 2026-07-22 |
| **Sunset** | **August 2027** (`google_ads_client.API_SUNSET`, asserted by GA2-T13g) |
| Source | https://developers.google.com/google-ads/api/docs/sunset-dates, read 2026-09-15 |
| Status | newest RELEASED version, not deprecated. v25.1 / v25.2 / v26 are listed as upcoming; v25.1 shares v25's sunset month, v26 (October 2026) sunsets November 2027 |

### Return addresses an operator must register with Google

One per system address, exact, no wildcards:

```
https://carejiox.com/channel_hub/oauth/callback/google_ads
https://hhh.carejiox.com/channel_hub/oauth/callback/google_ads
```

(`carejiox_template` computes `http://localhost:8069/…` because it is a blank
template with no public address; a new clinic gets its own address the moment
`web.base.url` is set, and the platform screen shows whichever database it is
opened in.)

---

## 8. Gotchas — candidates for conventions §5

### §5.185 — a lock timeout ABORTS the transaction, so the `except` branch that records it cannot write anything

`SET LOCAL lock_timeout` + `pg_advisory_xact_lock` is the §5.74-sanctioned way
to serialise a refresh. What §5.74 does not say is what the timeout *does* to
the transaction: PostgreSQL cancels the statement and the session enters the
aborted state, so the `except psycopg2.errors.LockNotAvailable:` handler runs
inside a transaction where every later statement fails with *"current
transaction is aborted, commands ignored until end of transaction block"* —
including the evidence write whose entire job is to explain the failure, and
including anything the caller does afterwards. Wrap the lock acquisition in
`with cr.savepoint():`: a rollback to the savepoint restores a usable
transaction, and `RELEASE` on the success path hands the lock up to the parent
unchanged, so the mutual exclusion is identical. The symptom without it is a
second, unrelated-looking error in the caller. (GA2, §4.4 kernel.)

### §5.186 — a macOS AppleDouble `._file` in the addons tree can make a repo-wide test gate unrunnable, and it is in no module's source

`/odoo/odoo-server/addons/health_care_command/i18n/._vi.po`, 163 bytes, left by
somebody's `scp` on 2026-09-10. `health_base`'s i18n gate enumerates
`i18n/*.po` **on disk**, so it picked the file up, failed
`test_g1c_filename_is_a_language_odoo_reads` on it, and then ERRORed three more
tests trying to decode it as UTF-8 — four reds that belong to no module and
appear in no diff. `git ls-files` shows nothing, which is exactly what makes it
hard to attribute. Check `sudo find /odoo/odoo-server/addons -name "._*"`
before believing an i18n or asset gate is broken, and prefer `rsync
--exclude='._*'` or a `tar` without extended attributes when copying from a
Mac. (GA2 deploy.)

### §5.187 — a wizard that answers with a notification leaves every non-stored compute on the parent form stale, and the screen then reads as a failure

`google.ads.platform.config.checklist` and the two secret hints are non-stored
computes. The secret wizard stored the value correctly and returned a
notification; the form behind it still said *"Sign-in secret — to do"* and both
hints were still empty. An operator's only reasonable reading is *it did not
work* — and they press it again. Every wizard whose parent shows derived state
must return the `params['next']` reload the same way an action button does
(`_with_reload`). Nothing in the test suite could see this: the computes are
correct, and only a browser shows the screen a second after the click.
(GA2, found in the browser pass; D8.)

### §5.188 — a concurrent work stream's commit lands in YOUR test run, and a baseline is the only way to say so

Two `health_care_command_channels` tests were red in this phase's run against
code this phase never touched — commit `03103e07`, authored 40 minutes earlier
in another stream, changed a notice string and left two assertions on the old
wording. On a shared box with a shared addons tree the honest tool is §5.133's
pristine baseline: restore the previous version of YOUR module from
`git archive <prev-commit>`, run the same tags, and compare counts AND failure
names. Two runs, ten minutes, and the difference between "GA2 broke the
channels module" and "GA2 regresses nothing" is settled with evidence rather
than argument. (GA2.)

---

## 9. Owner inputs still needed, in plain words

Nothing below blocks the phase. All of it blocks the first real Google
connection.

1. **A Google sign-in application.** Someone with access to the clinic's Google
   Cloud account needs to create a "web application" sign-in, switch on the
   Google Ads API for it, and register these two exact return addresses on it:
   `https://carejiox.com/channel_hub/oauth/callback/google_ads` and
   `https://hhh.carejiox.com/channel_hub/oauth/callback/google_ads`. That
   produces two values — an ID and a secret — which go on the *Google Ads
   application* screen once each.
2. **A Google Ads access token, and what level it is.** Google issues this
   separately, from the Google Ads API Centre. If it is still at "test accounts
   only", this system can read test accounts and nothing else — worth knowing
   before anyone tries.
3. **Which Google login manages the clinic's ads.** That is the account the
   operator will sign in with. If an agency runs the ads, it is the agency's
   manager account, and the person signing in must be able to see the clinic's
   advertising account underneath it.
4. **The advertising account number(s).** Ten digits, shown at the top right in
   Google Ads (it looks like `123-456-7890`). If Hanoi and Ho Chi Minh City are
   advertised separately, each needs its own entry here.

Still open from GA1 and unchanged: which website forms serve which city, and
whether the website can send an ad's details at all (the piece that carries
them has never been installed).
