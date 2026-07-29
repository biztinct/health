# CC-G — Platform Go-Live Console: implementation report

**Date:** 2026-07-29 · **Module:** `health_care_command_channels` **19.0.7.0.0** ·
**Branch:** 19.0 · **Server:** vietuat (live) · **Handover:**
`docs/strategy/handovers/channel-center-phaseG.md`

---

## 1. What shipped

### G1 — truthful availability

| File | Change |
|---|---|
| `services/adapters.py` | `BaseChannelAdapter.platform_ready()`; `required_platform_keys` added to `OPTIONAL_CAPABILITY_KEYS`; declared on `WhatsAppAdapter` (`es_config_id`, `verify_token`) and `MessengerAdapter` (`flb_config_id`, `verify_token`); `EmailAdapter.platform_ready()` → `bool(available_providers())`; `meta_app_identity()` helper |
| `models/channel_center.py` | `_center_platform_available(caps, channel)` now asks the adapter, `try/except ValueError → False`; all four call sites rewired; `get_adapter` imported |

`platform_ready()` reads no connection — it is called with `new()` probes and with a bare
channel-key string. Ready means: client id present **and** secret stored **and** every
`required_platform_keys` entry non-empty, for **any** declared provider (email declares
two; either one suffices).

### G2 — the Go-live tab

`models/channel_platform_app.py`: three non-stored computes (`oauth_redirect_uri`,
`webhook_urls`, `go_live_checklist`), `_adapter_requirements()` (reads the registry, so a
channel that starts requiring a new key appears on the checklist automatically),
`action_generate_verify_token()` (load → update → dump, sibling keys preserved,
regeneration refused while Meta holds the old value), and the audit/notification
plumbing. `views/platform_app_views.xml`: a "Go live" notebook page carrying the computed
values, the preflight fields and both buttons. No `tracking=True` anywhere on this model,
and no ACL change — it stays `base.group_system`, 1/1/1/1.

### G3 — preflight

Stored `preflight_status` / `preflight_at` / `preflight_detail` (plain columns, no
tracking). `action_preflight()` dispatches: **meta** runs Meta's documented app-access-token
call and reads the app's own name back; **zalo / google / microsoft** return
`unverifiable` with the reason in a sentence and make **no** network call. Persist first,
notify after — the button never raises on a provider refusal. The app token is used and
discarded. Manual only; no cron ships (§5.81).

### G4 — bookkeeping

38 new `vi.po` entries (26 python-code, 6 field labels, 4 selection values, 5 view
terms; the existing `Done` entry gained a second marker + occurrence rather than a
duplicate msgid); manifest 19.0.7.0.0 + a CC-G section; architecture §11 gains a CC-G row.

Full file list:

```
services/adapters.py                    models/channel_center.py
models/channel_platform_app.py          models/care_channel_audit.py  (2 event tags)
views/platform_app_views.xml            i18n/vi.po
__manifest__.py                         tests/test_platform_go_live.py   (new, T156–T169)
tests/__init__.py                       tests/common_spine.py            (forced fixture edit)
tests/test_oauth_engine.py              tests/test_call_center.py        (forced fixture edits)
docs/strategy/handovers/channel-center-architecture.md
docs/strategy/HANDOVER-CONVENTIONS.md   (new §5.95)
docs/strategy/reports/channel-center-phaseG-report.md
docs/strategy/reports/channel-center-phaseG-evidence/service-pass.md
```

## 2. Report-back items (handover §8)

**(a) All four `_center_platform_available` call sites rewired.** Grep after the change —
one definition, four callers, no bare `(caps)` form left:

```
$ grep -n "_center_platform_available" models/channel_center.py
468:    def _center_platform_available(self, caps, channel):
523:            available = self._center_platform_available(caps, channel)
711:        if not self._center_platform_available(caps, channel):
880:        if not self._center_platform_available(caps, conn.channel):
972:        if not self._center_platform_available(caps, conn.channel):
$ grep -rn "_center_platform_available(caps)" .        # (no matches)
```

**(b) Which validator enforces the capability key set — nobody did.** `CAPABILITY_KEYS`
has `tests/test_framework.py::test_81` behind it (it asserts every REQUIRED key is
present). `OPTIONAL_CAPABILITY_KEYS` was referenced **nowhere but its own definition** —
a docstring in constant form, so a typo'd `required_platform_key` would have declared no
requirement at all and silently re-opened the hole this phase closes. The diff line:

```python
-OPTIONAL_CAPABILITY_KEYS = ('parent_channel', 'platform_providers')
+OPTIONAL_CAPABILITY_KEYS = ('parent_channel', 'platform_providers',
+                            'required_platform_keys')
```

T169 (added, +1 beyond the handover's T156–T168) turns it into a contract: every
adapter's declared keys must be a subset of `CAPABILITY_KEYS | OPTIONAL_CAPABILITY_KEYS`,
and a `required_platform_keys` on a channel that claims `needs_platform_app: False` is a
failure.

**(c) The requests idiom reused for the Meta preflight.** `BaseChannelAdapter._get`
(adapters.py) — the module's single HTTP helper — instantiated with **no connection**
(`BaseChannelAdapter(env, None)`; `_get` reads none). It carries the module-wide
`HTTP_TIMEOUT = 15`, raises `ChannelSendError` with the status + provider text, and is
the exact call the existing test mocks (`adapters.requests.get`) already intercept.
*Deviation:* the handover specified a 10 s timeout; introducing a second timeout constant
for one call would have made "how long may a provider hold a worker" a two-answer
question. 15 s, one constant, declared.

**(d) Test tally.** `0 failed, 0 error(s) of 128 tests`, `EXIT:0`, `HTTP:200` — verbatim:

```
2026-07-29 08:54:54,006 odoo.tests.stats:  health_care_command_channels: 150 tests 25.88s 24751 queries
2026-07-29 08:54:54,006 odoo.tests.result: 0 failed, 0 error(s) of 128 tests when loading database 'vietuat'
EXIT:0
HTTP:200
```

The 14 CC-G methods **ran** (§5.83 — a count of failures is not evidence):

```
$ grep -ao "Starting TestPlatformGoLive\.[a-z0-9_]*" /tmp/gb/ccg3.log
test_156_empty_row_is_not_availability      test_163_meta_preflight_pass
test_157_requirements_light_up_one_at_a_time test_164_meta_preflight_failure_is_persisted
test_158_zalo_complete_row_is_available     test_165_unverifiable_providers_call_nobody
test_159_email_matches_the_adapter          test_166_computed_urls
test_160_non_platform_channels_unaffected   test_167_non_system_user_is_refused
test_161_no_secret_in_the_console           test_168_tenant_persona_reads_the_catalogue
test_162_verify_token_generator             test_169_capability_keys_are_declared
$ grep -ac "Starting Test[A-Za-z0-9]*\.test_" /tmp/gb/ccg3.log
128                     # 114 pre-existing + 14 new
```

That check earned its keep on the **first** green run: `0 failed of 114` with
`EXIT:0` — and **none of my tests in it**, because `tests/__init__.py` had no
`from . import test_platform_go_live`. A perfect-looking result line over a suite that
does not exist is exactly §5.83's failure mode, and only the executed-method count says
so.

**(e) Steps 2–3 evidence:** `docs/strategy/reports/channel-center-phaseG-evidence/service-pass.md`.
Service-side, **not screenshots** — see §5 below.

**(f) Where the handover drifted from reality:** one place, §2's claim that
`required_platform_keys` must be added "to whatever validator enforces the key set" —
there is no such validator (item b). Every file:line reference in §2 was accurate.

## 3. Deviations from the handover design

**D1 — `oauth_redirect_uri` is per-provider truth, not one template.** The handover
specified `{base}/channel_hub/oauth/callback/{provider}` for all four. That is right for
meta and zalo, and **wrong for google and microsoft**: CC-F deliberately orchestrates
Odoo's own mixins, which own their redirect URIs
(`google_gmail/models/google_gmail_mixin.py:55` → `/google_gmail/confirm`,
`microsoft_outlook/models/microsoft_outlook_mixin.py:57` → `/microsoft_outlook/confirm`;
verified on the server, not assumed). Printing ours would be a paste Google Cloud Console
accepts and the first real sign-in refuses — days later, tenant-side, which is the exact
failure mode §1 of the handover says this tab exists to prevent. T166 asserts the real
strings, and the Meta webhook URLs are built from the controller's own route rule so a
renamed route cannot leave the tab lying.

**D2 — the Meta preflight keeps `HTTP_TIMEOUT` (15 s), not a new 10 s constant.** See
item (c).

**D3 — T167 accepts `UserError` *or* `AccessError`.** The handover asked for
`AccessError` on both buttons. Both carry an explicit `has_group('base.group_system')`
gate (the `action_set_secret` precedent — these methods are RPC-reachable by name), and a
model-level gate fires **before** the ACL (§5.39), so the honest assertion is the
try/except pair of §5.70 — the same shape T120 and T138 already use for their plain-user
cases. The `read()` half of T167 asserts `AccessError` exactly as specified.

**D4 — one extra test (T169).** Item (b).

**D5 — three forced fixture edits in pre-existing test files.** Sanctioned by nothing in
the handover, and unavoidable; each is commented in place:

- `tests/common_spine.py` — the shared `meta` platform app now carries `es_config_id` and
  `flb_config_id` alongside the verify token. It meant "the operator has finished this
  app" (T97/T139 assert both Meta cards are available against it) and under a gate that
  asks what the adapter refuses without, a fixture has to say so. §5.62's family.
- `tests/test_oauth_engine.py` and `tests/test_call_center.py` — two **live-data**
  collisions that have nothing to do with CC-G's code; see §4.

## 4. The 20-minute hang, and what it cost

The first test run stopped advancing at `test_85_refresh_lock_and_fresh_persist` and sat
there — with the HTTP service **down**, because `service odoo-server start` is downstream
of `odoo-bin` in the §2 deploy command. `pg_blocking_pids()` named the blocker in one
query:

```
2148801 active  Lock/transactionid  INSERT INTO care_channel_connection ('webchat', 1, 'ready' …)
2148795 idle in transaction         ← the test transaction; blocks the INSERT, waits on it
```

At 05:55 UTC that morning — three hours before the run — somebody drove the Channel
Center on vietuat and left an **active** `call` and `webchat` connection on company 1.
The shared fixture archives live connections inside the test transaction so its own rows
can take the partial unique index slot `(channel, company_id) WHERE active`; that frees
the ORM slot but **not the index entry**, so test_85's independent-cursor INSERT of an
active webchat row waited on our uncommitted UPDATE while we waited on it. PostgreSQL
reports no deadlock (the outer session is merely *idle in transaction*) and vietuat runs
`lock_timeout = 0`, so the wait was indefinite.

The same live rows red-lit `test_151b` and `test_152` a different way: health_voip24h's
migration looks for an existing Calls connection with `active_test=False` — correctly
(§5.27) — so the archive does not hide it, and "0 created, 1 already present" failed an
assertion about code that is fine.

Fixes, both in the fixtures: the committed fixture row is now inserted `active = false`
(it is outside the index; the flag proved nothing about the token write under test) on a
cursor that sets `SET LOCAL lock_timeout` like every other fresh cursor in the module,
and the two voip tests run on `company2`, created inside the transaction, where the
deployment has no rows by construction. **Ledger §5.95 added.**

## 5. Browser pass, and the one screenshot still owed

The user supplied the `crm` login after the first draft of this report, so §7 steps 2–3
are now a real browser pass from the login page through the CMS sidebar — no deep links,
zero console messages on every screen (`channel-center-phaseG-evidence/`, shots 01–05).

The evidence that matters is an md5: the Center with **zero** platform apps, the Center
with an **empty** `zalo` row, and the Center after cleanup are **pixel-identical**
(`b85fb266…`). An incomplete platform application changes nothing a tenant can see —
which is precisely what G1 exists to guarantee, and precisely what was NOT true before
this phase, where that same empty row lit the Zalo and ZNS cards and offered a Connect
that could only fail. The one frame that differs (`1efeb5c1…`) is the completed row
lighting the card up, which is the non-goal "may only tighten" holding.

**Still owed: one screenshot — the Go-live tab itself.** That form is
`base.group_system`; `crm` is deliberately not a system administrator (which is what
makes it valid tenant evidence), and granting it that group would change a live user's
privileges and destroy the persona. Every value the tab renders is proven service-side
in the pack — redirect URI, both webhook URLs, the checklist rows, the generator, and a
real Graph round trip that returned `HTTP 400 Invalid Client ID` → `fail` persisted with
no raise and no secret in the detail. Only the rendering is unverified. **An admin login
closes it in one pass.**

## 6. Observations worth a reviewer's attention

**Selection labels do not reach the UI in Vietnamese anywhere on vietuat — including
core's own.** The CC-G catalogue entries are correctly shaped and the values ARE in the
database:

```
ir_model_fields_selection.name → {'en_US': 'Not checked', 'vi_VN': 'Chưa kiểm tra'}
field.selection_ids read under lang=vi_VN → [('none', 'Chưa kiểm tra'), …]
```

but the path the UI uses returns English, for this module's pre-existing entries (shipped
CC-A) and for `res.partner.company_type` alike:

```
env['ir.model.fields'].with_context(lang='vi_VN').get_field_selection('res.partner','company_type')
    → [('person', 'Person'), ('company', 'Company')]
res.partner.fields_get(['company_type'])['selection'] under lang=vi_VN → English
```

`_description_selection` routes through `ir.model.fields._get_fields_cached`, an
`ormcache(cache='stable')` keyed on `self.env.lang`. This is core-wide, pre-existing, and
independent of CC-G — but if it is what it looks like, **no Selection label in this
deployment is translated**, which is a large silent i18n hole (§5.85's family, one layer
further down) and deserves its own investigation. I did not chase it inside a feature
phase, and I did not paper over it by giving selection labels a bogus `code:` occurrence,
which §5.85 warns against explicitly. Field labels and view terms DO translate correctly
(verified: `Kiểm tra trước`, `URI chuyển hướng`, `Chạy thật` in the view arch).

**Python translations verified live:** `get_python_translations('health_care_command_channels',
'vi_VN')` → 232 entries, including the new ones.

## 7. Non-goals honoured

No provider-approval automation; no tenant-visible change beyond cards lighting up only
when truly ready (the unavailable-card copy in `channel_center.xml` is untouched); no new
OAuth engine, mixin patch, webhook change or VoIP/Calls/Telegram/Webchat edit; no ZNS
attestation; `care.channel.connection`'s readiness vocabulary and `_recompute_ready` are
untouched — preflight is Plane-1 operator tooling and writes nothing on a connection; and
`_center_platform_available` only ever tightened (a complete row lights the same cards it
always did — proven live in the evidence pack, step 3b).
