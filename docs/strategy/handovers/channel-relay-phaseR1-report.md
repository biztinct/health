# R1 — Channel Relay: phase report

**Handover:** `docs/strategy/handovers/channel-relay-phaseR1.md`
**Implemented:** 2026-09-06, branch `19.0`, master `carejiox` on VietUcUAT.
**Status:** shipped to all three databases in one sitting; the two things that
are not proven need Meta's console and are listed in §7.

---

## 1. What was built

| Module | Version | Installed on |
|---|---|---|
| `biz_platform_channel_relay` (NEW) | 19.0.1.0.0 | `carejiox` ONLY |
| `health_channel_relay` (NEW) | 19.0.1.0.0 | `carejiox`, `carejiox_template`, `hhh` |
| `health_care_command_channels` (EDIT) | 19.0.11.2.0 → **19.0.11.3.0** | all three |

### `biz_platform_channel_relay` — the hub

```
__init__.py                          module docstring: why the relay exists, and the six rules
__manifest__.py                      depends: biz_tenants, health_care_command_channels
models/relay_tenant.py               channel.relay.tenant — the customer list, _reconcile,
                                     _maybe_resync, _slug_from_state, the two operator buttons
models/relay_route.py                channel.relay.route — who owns which Page / number,
                                     unique (channel, resource id) in init() + a create/write pre-check
models/relay_delivery.py             channel.relay.delivery — the retry queue, _attempt,
                                     _cron_retry, _cron_purge, action_retry_now
models/relay_router.py               channel.relay.router (AbstractModel) — _route_meta
services/relay.py                    split_payload (pure), forward, RelayError, RELAY_TIMEOUT
controllers/meta_relay.py            POST /care_channels/meta/<channel>/webhook (overrides the parent)
controllers/oauth_relay.py           GET /channel_hub/oauth/callback/<provider> (overrides the parent)
security/ir.model.access.csv         three models, base.group_system, nothing else
views/relay_views.xml                Customer relay + Relay deliveries (list, form, search)
views/menus.xml                      two menus under Care Command Setup, sequence 60 / 70
data/ir_cron.xml                     retry (1 min), reconcile (10 min), purge (daily 03:40)
i18n/vi.po                           37 entries: 7 python, field labels, selections, menus, view terms
tests/common.py, test_relay.py, test_relay_http.py    T1–T17
```

### `health_channel_relay` — the client

```
__init__.py                          module docstring
__manifest__.py                      depends: health_care_command_channels, biz_tenancy
models/care_channel_oauth_session.py _mint_state() → '<slug>~<ticket>'
security/ir.model.access.csv         header only — the module declares no model
i18n/vi.po                           header only — the module has no user-visible string
tests/test_channel_relay.py          T18, T18b, T19, T19b
```

### Sanctioned edits (handover §6) — all six, and nothing else except §5's two forced fixes

1. `models/care_channel_oauth_session.py` — `_mint_state()` extracted (`@api.model`,
   returns `secrets.token_urlsafe(32)`), called from `create_for`.
2. `services/adapters.py` — `_MetaAdapterBase._redirect_uri()` reads
   `channel_hub.oauth_redirect_base` (new constant `OAUTH_REDIRECT_BASE_PARAM`),
   `rstrip('/')`, falls back to `_base_url()`.
3. `models/channel_platform_app.py` — new `_redirect_base(provider)` (meta only),
   used by `_compute_go_live_urls`; `models/channel_golive.py::_golive_urls` uses it too.
4. `models/care_channel_audit.py` — `KNOWN_EVENTS` += `relay_forwarded`,
   `relay_failed`, `relay_routed_signin`, `relay_pushed`, with the two-line comment.
5. `__manifest__.py` — version `19.0.11.3.0` + a release-note section.
6. `i18n/vi.po` — unchanged: the phase added no new translatable string to that module.

---

## 2. Test results

All runs on **`carejiox_r1`**, a full clone of the master taken 2026-09-06, with
its `biz_tenant` rows set to `draft` and every `ir_cron` switched off BEFORE
anything ran (H102 / H78 — a reconcile cron on a clone would push credentials
onto the real `hhh`). Run with the live service UP, via the `systemd-run` form
on ports 8199/8299 with `--db-filter='^carejiox_r1$'`, its own logfile and
`--workers=0` (never `carejiox-deploy -t` on a clone). The new code was placed
in a PRIVATE addons directory (`--addons-path=/odoo/r1/addons,/odoo/odoo-server/addons`)
so the live systems never saw it during the rehearsal (SAAS_RUNBOOK §4).

### Baseline — `/health_care_command_channels`, unmodified code, same clone

```
2026-09-06 13:33:37 ERROR carejiox_r1 odoo.tests.result:
  15 failed, 2 error(s) of 204 tests when loading database 'carejiox_r1'
executed test methods: 204     HttpCase classes started: 6
```

### After — the same suite plus both new modules

```
2026-09-06 13:57:05 ERROR carejiox_r1 odoo.tests.result:
  5 failed, 1 error(s) of 229 tests when loading database 'carejiox_r1'
executed test methods: 229     HttpCase classes started: 10
```

| | baseline | after |
|---|---|---|
| tests executed | 204 | 229 (+25, every new test ran) |
| failed | 15 | 5 |
| errors | 2 | 1 |

**All 25 new tests pass.** T1–T17 (`biz_platform_channel_relay`, 21 methods
across five classes: T12 and T13 each carry a companion `b` case) and T18–T19
(`health_channel_relay`, 4 methods).

### The 6 remaining failures are ALL in the baseline set — none is new

| Test | Cause | In scope? |
|---|---|---|
| `TestChannelAttribution.test_at_01 / _04 / _05 / _07` | `care_conversation_ext.py:234` writes `touchpoint_type=`, a field the dropdown-vocabulary conversion replaced with `touchpoint_type_id`. Same defect class as §5 below, in a path R1 does not touch. | no — reported, not fixed |
| `TestChannelFramework.test_89_settings_param` | `res.config.settings.execute()` raises `KeyError: 'digest.digest.name'` through `health_care_command_ai`'s `set_values()`. | no |
| `TestEmailCenter.test_148_email_chat_stays_on_mail_message` | the `care.conversation` spine no longer owns the email thread in this fixture. | no |

Ten baseline failures and one baseline error were REPAIRED as a side effect of
deviation D3 (below): the whole `TestContactCapture` block.

---

## 3. Deploy + verify (handover §8)

### Step 0 — rehearsal
Clone made, neutralised, both modules installed and the channels module upgraded
with tests, clone dropped, private addons directory removed. Evidence above.

### Steps 1–4 — the three-database release, back to back

```
$ carejiox-deploy -d -i biz_platform_channel_relay,health_channel_relay -m health_care_command_channels
==> odoo-bin exit=0 ; ==> http=200 (carejiox.com) procs=4                       EXIT:0

$ carejiox-deploy -D carejiox_template -i health_channel_relay -m health_care_command_channels
==> odoo-bin exit=0 ; ==> http=200                                              EXIT:0
$ psql -d carejiox_template -Atc "select count(*) from ir_cron where active"  → 3   ⚠
   (health_voip24h's three, woken by the upgrade — see ledger §5.178)
$ psql -d carejiox_template -c "UPDATE ir_cron SET active = false"           → 0   ✔

$ carejiox-deploy -D hhh -i health_channel_relay -m health_care_command_channels
==> odoo-bin exit=0                                                             EXIT:0
$ curl -H 'Host: hhh.carejiox.com'  http://127.0.0.1:8069/web/login  → 200
$ curl -H 'Host: carejiox.com'      http://127.0.0.1:8069/web/login  → 200
```

Versions afterwards:

```
carejiox           biz_platform_channel_relay   19.0.1.0.0    installed
                   health_channel_relay          19.0.1.0.0    installed
                   health_care_command_channels 19.0.11.3.0   installed
carejiox_template  biz_platform_channel_relay   —             uninstalled
                   health_channel_relay          19.0.1.0.0    installed
                   health_care_command_channels 19.0.11.3.0   installed
hhh                biz_platform_channel_relay   —             uninstalled
                   health_channel_relay          19.0.1.0.0    installed
                   health_care_command_channels 19.0.11.3.0   installed
hhh                models named channel.relay.%  → 0 rows
```

The hub is on the master and only the master, as the `biz_platform` prefix on
`health_tenancy`'s never-list guarantees.

### Step 5 — the credentials push

```
$ carejiox-deploy -x /tmp/r1_push.py
R1-RECONCILE: {'customers': 1, 'routes': 0, 'pushed': 1, 'problems': 0}
R1-ROW: hhh True hhh.carejiox.com True 2026-09-06 14:02:04 ••••33d9 verify_token 0 False
```

The resulting rows on `hhh`, read from a fresh `psql` (never the secret):

```
$ psql -d hhh -Atc "select id, provider, client_id, secret_hint, extra_json,
                           environment_note, active, (client_secret_enc is not null),
                           left(client_secret_enc,6) from channel_platform_app"
1|meta|4376606219260542|••••33d9|{ "verify_token": "L3f0SSXIHrRMv-UD0dv_chM02UTSfJEX" }|Pushed by the platform|t|t|chs$1$

$ psql -d hhh -Atc "select key,value from ir_config_parameter
                     where key='channel_hub.oauth_redirect_base'"
channel_hub.oauth_redirect_base|https://carejiox.com

$ psql -d hhh -Atc "select event, detail_redacted from care_channel_audit order by id desc limit 1"
secret_rotated|pushed by the platform
```

The master's own row, for comparison — identical id, identical hint, identical
extra configuration:

```
$ psql -d carejiox -Atc "select provider, client_id, secret_hint, extra_json
                           from channel_platform_app where provider='meta' and active"
meta|4376606219260542|••••33d9|{ "verify_token": "L3f0SSXIHrRMv-UD0dv_chM02UTSfJEX" }
```

`hhh`'s token starts `chs$1$` and was produced inside `hhh`'s own environment —
a token minted on the master would be undecryptable there (§5.172). Nothing in
this report, in any log line, in any audit row or in any `/tmp` file contains
the secret itself.

The master carries NO `channel_hub.oauth_redirect_base` parameter (0 rows) and
neither does the template: the platform's own sign-ins are unchanged.

The 10-minute cron then ran twice on its own and reported
`{'customers': 1, 'routes': 0, 'pushed': 0, 'problems': 0}` — `pushed: 0` is the
skip working: nothing had changed, so no secret was rewritten and no audit row
was added.

### Step 5b — live end-to-end proof of the relay itself (handover §8 step 7's fallback, and more)

`hhh` has no Meta connection yet (Studio step 6 is pending), so there is no real
Page to send a real message to. Instead the whole hop was driven with a
synthetic, correctly-signed batch prepared INSIDE the deployment (recipe now in
ledger §5.179): a route row for a fake Page owned by `hhh`, a compact-JSON body,
and a `sha256=…` header computed with the platform's own secret server-side.

```
== unsigned POST (must be 403, 0 bytes) ==            status=403 bytes=0
== correctly signed POST (must be 200) ==             status=200 bytes=0
== sign-in hop against the live platform ==
   status=302 location=https://hhh.carejiox.com/channel_hub/oauth/callback/meta
                        ?code=R1PROOFCODE&state=hhh~r1proofticket
== a short name nobody relays for (must NOT redirect) == status=200 location=
```

Server log, both sides:

```
14:04:09 carejiox  biz_platform_channel_relay.controllers.meta_relay:
         channel relay: meta webhook signature rejected (fb)
14:04:10 carejiox  biz_platform_channel_relay.controllers.meta_relay:
         channel relay: meta fb webhook {'local': 0, 'forwarded': 1, 'queued': 0, 'unknown': 0}
14:04:10 hhh       health_care_command_channels.models.care_channel_message:
         care_channels: fb webhook for an unknown resource — captured
14:04:10 hhh       health_care_command_channels.controllers.meta:
         care_channels: meta fb webhook {'ingested': 0, 'status': 0, 'ignored': 0, 'unknown': 1}
```

That last pair is the whole phase in two lines: the forward arrived at `hhh`,
and `hhh` accepted OUR signature using ITS OWN pushed copy of the secret,
through its OWN unmodified webhook controller. It is simultaneously the proof
that the credentials push works.

Rows afterwards:

```
hhh    care_contact_capture              1 row, fb / R1PROOF_PAGE, the forwarded sub-payload only
carejiox care_contact_capture where resource_external_id='R1PROOF_PAGE'   → 0
carejiox care_contact_capture (total)                                     → 3 (unchanged)
carejiox care_channel_audit where event like 'relay%':
   relay_routed_signin | hhh
   relay_forwarded     | hhh fb 1 entries
   relay_pushed        | hhh received the platform Meta application
carejiox channel_relay_delivery                                           → 0 (it landed first time)
carejiox channel_relay_tenant  hhh | last_forward_at 14:04:10 | last_error ∅
```

No page id, no sender id, no message text and no sign-in code appears in any
audit detail — short name, channel and count only.

**Cleanup, fresh-cursor verified (§5.34):** the route row, `hhh`'s capture row
and both `/tmp` files were deleted; `channel_relay_route` → 0,
`hhh.care_contact_capture` → 0, `ls /tmp/r1proof.*` → no such file. The audit
rows were deliberately KEPT — they are append-only evidence and they are the
proof.

### Step 7 — memory cost of `_tenant_env`

Measured across one full live reconcile cron run (which enters `_tenant_env` on
`hhh` once): total odoo RSS **881 420 kB → 885 132 kB (+3.6 MB)**, `free -m`
available 649 → 652 MB. That is lower than the runbook's ~11 MB per-registry
figure because the worker already had `hhh`'s registry resident from the webhook
forward. The honest planning number remains the runbook's: a first `_tenant_env`
on a customer costs roughly 11 MB in the process that opens it, once, and the
cron opens every serving customer every ten minutes. **On this box (1 910 MB
total, ~650 MB available) that is fine for a handful of customers and is the
thing to watch first when the fleet grows past ten.** The cheap mitigation, if
it is ever needed, is to push credentials only to customers whose `in_step` is
false rather than entering every customer's environment on every run.

---

## 4. What the owner still has to do — the Meta console, in plain words

None of this is software and none of it can be pressed from here. It is about
fifteen minutes in Meta's own website, once, for the whole platform.

Go to **developers.facebook.com**, sign in, open **our app** (the one whose
application number is `4376606219260542`), and do these four things.

1. **Tell Meta our website belongs to us.**
   Left menu → **App settings** → **Basic**. Find the box called **App Domains**
   and add `carejiox.com`. Press **Save changes** at the bottom.

2. **Turn on signing in from a web page.**
   Left menu → **Facebook Login** → **Settings**. Turn ON the switch called
   **Login with the JavaScript SDK**.

3. **List the addresses that are allowed to show the sign-in box.**
   On that same screen there is a box called **Allowed Domains for the
   JavaScript SDK**. Add BOTH of these, one per line:
   - `carejiox.com`
   - `hhh.carejiox.com`
   Press **Save changes**.

4. **Leave the three addresses that are already there exactly as they are.**
   Under **Facebook Login for Business** → **Settings**, the return address
   `https://carejiox.com/channel_hub/oauth/callback/meta` must stay. Under
   **WhatsApp** → **Configuration** and **Messenger** → **Settings**, the two
   webhook addresses `https://carejiox.com/care_channels/meta/whatsapp/webhook`
   and `https://carejiox.com/care_channels/meta/fb/webhook` must stay. **Do not
   add a second address for the new clinic.** That is the whole point of this
   change: one address now serves every clinic.

**Then the experiment we need an answer to, which decides the next phase.**
After step 3, open `hhh.carejiox.com`, sign in as the clinic's owner, go to the
Channel Center and press **Connect** on WhatsApp. If the Meta window opens and
finishes, come back to the Meta website and **remove `hhh.carejiox.com` from the
Allowed Domains list, leaving only `carejiox.com`**, then press Connect on
`hhh.carejiox.com` again.

- If it still works with only `carejiox.com` listed, **every future clinic needs
  nothing at all in the Meta console** — a new clinic is Connect and sign in.
- If it stops working, **each new clinic needs one line added to that list**,
  and we will build a screen that reminds you to add it. That is a one-line job
  per clinic, not a new application review.

Please tell us which of the two happened.

---

## 5. Deviations

**D1 — an extra field on `channel.relay.tenant`: `pushed_extra_keys`.**
Handover §4.2's field list does not name it, but §4.2 also defines `in_step` as
"pushed hint equals the platform's **AND** pushed extra configuration keys ⊇ the
platform's", and the second half cannot be answered without remembering what was
sent. Without it, the day the operator adds the two sign-in configuration ids to
the platform application (Studio step 6, still pending) every customer would go
on reading "in step" while holding an application that cannot sign anybody in.
The field is a comma-separated key list, never a value.

**D2 — the backoff index.** §4.5 writes
`next_at = now + BACKOFF[min(attempts, len-1)]`, which for `attempts == 3` is
`BACKOFF[3] == 3600`. T10 requires `attempts 3 → next_at ≈ now + 900 s`, which is
`BACKOFF[2]`. Followed the numbered test:
`BACKOFF[min(attempts, len(BACKOFF)) - 1]` with `attempts` already incremented,
giving 60, 300, 900, 3600, 21600, 43200, 43200, 43200 and `dead` at 8 attempts
(≈31 h, the handover's "≈24 h" rounded).

**D3 — FORCED, outside §6: `care_contact_capture._capture` was writing a field
that no longer exists.** The dropdown-vocabulary conversion turned
`care.contact.capture.reason` into `reason_id` and left this writer behind, so
`create()` raised `ValueError: Invalid field 'reason'` — caught by `_capture`'s
own "capturing must never break ingest" guard, which is why nobody noticed. The
unrouted-contact queue has therefore been silently dropping everything on every
database since that conversion. R1's unknown-Page path (§4.3 step 6, T6) lands
in exactly that method, so it could not be left broken. Two lines changed:
`vals['reason_id'] = health.lookup.value._default_for('unrouted_contact_reason',
reason)` and `IMMUTABLE_FIELDS`'s `'reason'` → `'reason_id'`. This repaired ten
failing tests and one erroring test in the baseline, and it is what the live
proof in §3 exercises on `hhh`. Ledger §5.174.

**D4 — FORCED, outside §6: `tests/test_multi_account.py::test_cap_11` made
delta-based.** Once D3 makes captures actually write, `unrouted_count() == 2` is
an assertion about the master's live backlog (it read 5). Changed to
`before + 2` / `before + 1`. Ledger §5.176.

**D5 — T19 lives in `health_channel_relay/tests/`,** not in
`health_care_command_channels/tests/`, so that §6's "nothing else in that module
changes" stays true of its test directory too (D4 is the one forced exception).

**D6 — an unsignable batch is not queued.** §4.3 step 7 does not describe what
happens if the platform application's secret cannot be read at forward time.
`_forward_tenants` logs a warning and forwards nothing rather than queueing,
because a delivery whose signature cannot be computed is one the customer would
refuse forever. Unreachable in practice: the signature check upstream needs the
same secret, so the request would already have been a 403.

**D7 — two search filters dropped from the operator screen.** §4.7 asks for the
columns, which are all there. "In step" and "Waiting to retry" are worked out as
the screen is drawn rather than kept in the table, so they cannot back a search
filter; the columns plus the row colours answer the same question. Ledger §5.177.

**D8 — `health_channel_relay` ships no views, no menus and no cron.** The
deliverable list asks each new module for them; this module is one method
override with no user surface, so there is nothing to put in them. Its
`security/ir.model.access.csv` is a header line only (it declares no model) and
its `i18n/vi.po` is a header only (it emits no translatable string).

**D9 — the rehearsal used a private addons directory.** Handover §8 step 0
implies copying into the shared tree; `docs/SAAS_RUNBOOK.md` §4 says a rehearsal
must give the practice copy its own folder so the live systems never see the new
code. Followed the runbook (`--addons-path=/odoo/r1/addons,/odoo/odoo-server/addons`).

---

## 6. Self-review against §4, §5 and §6

**§4 architecture** — every element implemented as specified except D1, D2, D6,
D7, D8. `split_payload` is a pure function with no environment; `_route_meta`
returns `{'local', 'forwarded', 'queued', 'unknown'}` and never raises out;
`_maybe_resync` is throttled on `channel_relay.last_resync_at` and reads routes
only; `_slug_from_state` gates on the regex AND an active row; the customer
module is the single `_mint_state` override the handover describes.

**§5 safety rails** — walked one by one:

1. *Signature before anything.* `meta_relay.meta_webhook` reads the raw bytes,
   refuses a bad signature with a bodyless 403 before any escalation, and
   answers 200 from that point on. Proved live (403 then 200).
2. *Only the customer's own entries leave the master.* `split_payload` is the
   boundary; T2 asserts the other clinic's number AND its message id are absent
   from the sub-payload; T5 asserts the local dispatch sees only the local entry
   and the forward only the customer's.
3. *Redirect allowlist = active relay tenant rows.* T15 covers eight refusals
   including `../~x`, `HHH~x` and an archived customer; proved live (`zzz~…`
   answered 200 with no `Location`).
4. *No message body on the master except encrypted, in the retry queue.* T7
   asserts the stored body starts `chs$1$`; it is cleared on delivery (T9) and
   purged after seven days (T11). The field is `groups='base.group_system'` and
   appears on no screen.
5. *Never `_tenant_env` from a public route.* `_maybe_resync` calls
   `_reconcile(push_credentials=False)`, which never reaches `_push_credentials`.
   Grep: `_tenant_env` appears in `relay_tenant.py` only.
6. *Every audit detail is short name + channel + counts.* Verified live — three
   rows, contents quoted in §3.
7. *Cross-database only through the service.* `_pg_cursor` for reads,
   `_tenant_env` for writes; `odoo.sql_db` appears nowhere in either new module.
8. *Public routes are not oracles.* Both refusals are byte-identical to the
   parent's.
9. *Clone neutralised before rehearsal.* `UPDATE biz_tenant SET state='draft'`
   and `UPDATE ir_cron SET active=false` ran before the first test run.

**§6 sanctioned edits** — all six done, listed in §1, plus D3 and D4 declared as
forced.

**White-label** — `grep -rn "Odoo\|odoo"` over both new modules returns only:
XML root tags (`<odoo>`), `.po` header lines, `#. odoo-python` markers and one
code comment naming `odoo.sql_db`. No user-visible string in either module, in
any `string=`, `help=`, selection label, menu name, notification, error text or
`.po` msgstr, contains the word. The diff of
`health_care_command_channels` adds no line containing it either. Every new
user-facing string says "customer" and "the platform".

**Every user-visible string this phase adds** (all in
`biz_platform_channel_relay`; the customer module adds none):
menus *Customer relay*, *Relay deliveries*; action names of the same two;
field labels *Short name, Customer, Address, Application sent on, Secret sent,
Settings sent, In step, Pages and numbers, Waiting to retry, Last message
forwarded, Last problem, Channel, Page or number, Last read, Message
(encrypted), Signature, Attempts, Next try, State, Delivered on, Entries*;
selection labels *WhatsApp, Messenger, Waiting, Delivered, Given up*; buttons
*Send the Meta application to every customer now*, *Re-read who owns which Page
and number*, *Retry now*; notifications *The Meta application was sent*, *Pages
and numbers re-read*, *It will be tried again*, *This delivery is back in the
queue.*; the validation message *This page or number is already connected by
another customer (…)*; the two empty-state helps; and the form note *The message
itself is held encrypted until it is delivered, and is never shown on this
screen.* All of them are in `i18n/vi.po`.

---

## 7. Not proven, and why

1. **A real Meta message through a real Page.** `hhh` has no Meta connection:
   the platform application still has no `es_config_id` and no `flb_config_id`
   (Go-Live Studio step 6 is the operator's, and has not been done). The hop was
   proved instead with a synthetic, correctly-signed batch — which exercises the
   identical code path on both sides, including the customer verifying our
   signature — but nothing here proves Meta's own delivery.
2. **The Meta console changes (handover §8 step 6).** Cannot be pressed from
   here. Instructions in §4 above.
3. **Whether the JavaScript SDK accepts a parent domain for subdomains.** This
   is the one empirical question that decides whether R2 exists at all, and only
   the owner can answer it (§4, the experiment).
4. **WhatsApp splitting under real traffic.** T2 and T3 prove the split on the
   canonical payload shape; no real WhatsApp batch has passed through it.
5. **Two customers on one Meta application at once.** There is one customer on
   this platform. The duplicate-claim path, the per-customer split and the
   archive-on-pause path are covered by T12 with mocked customer databases.
6. **The retry queue under a real failure.** T7–T11 cover it; the live proof
   landed first time, so the queue has never held a row in production.
7. **A Vietnamese screen.** The catalogue is present and shaped correctly
   (`#. module:` + marker + `#:` occurrence per entry) but the operator screens
   have not been opened in Vietnamese; the relay screens are platform-operator
   only, and the platform operator works in English.

## 8. Pre-existing defects found and NOT fixed

* **`care_conversation_ext.py:234` writes `touchpoint_type=`**, a field the
  dropdown-vocabulary conversion replaced with `touchpoint_type_id`. The write
  is inside an "analytics must not break ingest" guard, so it fails silently:
  **every conversation's marketing attribution is being lost on every
  database.** Four tests are red on it. Same defect class as D3; out of R1's
  scope, so reported rather than repaired. It is a one-line fix of the same
  shape and should be the next thing someone does.
* `TestChannelFramework.test_89_settings_param` — `res.config.settings.execute()`
  dies with `KeyError: 'digest.digest.name'` through
  `health_care_command_ai/models/res_config_settings.py:39`.
* `TestEmailCenter.test_148_email_chat_stays_on_mail_message` — the
  `care.conversation` spine no longer owns the email thread in that fixture.
* Upgrading the golden template switched `health_voip24h`'s three crons back on
  (ledger §5.178). Switched off again; the runbook check must be run after every
  template upgrade whatever the phase touched.

## 9. Ledger entries added

`docs/strategy/HANDOVER-CONVENTIONS.md` §5.174–§5.179:

* **§5.174** — a converted Selection leaves its WRITERS behind, and an
  exception-guarded writer makes the breakage completely silent.
* **§5.175** — `biz_tenant.slug` is globally unique, so a fixture that "creates a
  customer" collides with the real one.
* **§5.176** — a queue the product fills cannot be asserted with an absolute
  count, and repairing the writer is the day it tells you.
* **§5.177** — a non-stored compute can be a column and a row colour, never a
  search filter.
* **§5.178** — upgrading the golden template switches crons back on, and the ones
  that wake are not the phase's.
* **§5.179** — you cannot forge a provider-signed webhook from outside the
  deployment: the prepare-inside / fire-from-the-shell recipe, with cleanup.

## 10. One thing to watch

`_maybe_resync`'s "at most once every 60 seconds" is stored in an
`ir.config_parameter`, which each HTTP worker caches (ledger §5.48). On this
two-worker box the true bound is therefore *at most once per minute per worker*.
That is still a hard ceiling on how often an unknown Page can make the platform
re-read the customer list, and the re-read is READ ONLY, so it is a note rather
than a defect — but it is worth knowing before anyone tunes the interval down.
