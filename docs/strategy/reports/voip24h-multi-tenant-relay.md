# VoIP24h multi-tenant relay — implementation report (V2)

**Date:** 2026-09-17
**Module:** `biz_platform_voip_relay` 19.0.1.0.0 (new)
**Also changed:** `health_voip24h` 19.0.3.0.0 → 19.0.3.1.0
**Supersedes nothing.** Extends `voip24h-implementation-report.md` (V1).

---

## 1. What was asked

> "make sure that it works for hhh.carejiox.com as well … carejiox.com is my
> demo database where it should work but also work in hhh.carejiox.com which
> would be prod data … just as in Zalo and Facebook, i need to set only once as
> carejiox.com but for future clients eg hhh.carejiox.com etc they should use
> this common router and calls should be able to be diverted"

## 2. The plumbing, verified (do not re-derive)

| Fact | Evidence |
|---|---|
| `dbfilter = ^%d$`, `list_db = False`, `proxy_mode = True` | `/etc/odoo-server.conf` |
| The database is the FIRST LABEL of the hostname | `carejiox.com` → `carejiox`; `hhh.carejiox.com` → `hhh` |
| Databases on the cluster | `carejiox`, `carejiox_template`, `hhh`, `vietuat`, `codex_fb_center_reply` |
| `hhh` is in the customer list, `state = live` | `biz_tenant` on `carejiox` |
| nginx passes the real `Host` through | `biz-tenant-hhh.carejiox.com.conf`, `biz-wildcard` |
| A precedent relay already exists for Meta | `biz_platform_channel_relay` 19.0.1.1.0 |
| Cross-database rails | `biz.tenants._pg_cursor` (read only, autocommit), `._tenant_env` (rail R5, commits + `signal_changes()`), `._tenant_host`, `._platform_url`, `._http_port` — `biz_tenants/models/service.py:143-246` |

## 3. Design

One address — `https://carejiox.com/voip24h/v3/{cdr,events}/<receiver>/<token>` —
serves every clinic. The platform classifies each delivery and hands it to the
clinic that owns it, over loopback with that clinic's hostname in a `Host:`
header, so dbfilter selects the destination database exactly as it would for a
browser. The destination's own route is untouched.

### 3.1 The security design: forward the credential, never hold it

The token is in the path. The relay routes on the **public** receiver id and
forwards the path byte for byte. Consequences, all deliberate:

* the platform stores, mints, rotates and decrypts **no** tenant secret;
* the destination does its own constant-time token check against its own
  database, and refuses anything else. The boundary is enforced at the
  destination rather than trusted at the source;
* a receiver id is already in every web-server access log, so caching it on the
  platform adds no exposure.

The one exception is a hand-off that could not be delivered: it rests encrypted
(`voip_crypto`, AES-256-GCM, this database's own key), is never rendered on any
screen, and is erased **on delivery**, not on the purge.

### 3.2 Who a call belongs to — resolution order

1. **A clinic's own call-back address** (`kind = receiver`). Read out of that
   clinic's `voip_config.receiver_id` every ten minutes; unique across the whole
   platform. Nothing in a payload may override it.
2. **This platform's own clinic**, when the address is one of ours — and only
   here is the hotline (`did`) consulted, for the case where several clinics
   share ONE supplier account. If a clinic owns the hotline dialled, the call is
   theirs; otherwise it is ours.
3. **Nobody** → one throttled re-read of the customers (≤ once a minute), then
   the parent route's existing flat refusal.

Live ringing events carry no hotline, so hotline routing covers completed call
records only. That is stated, not papered over with a guess.

### 3.3 What the supplier is told

| Destination said | Supplier gets | Queued? |
|---|---|---|
| 200 `accepted` / `duplicate` / `quarantined` | the same, verbatim | no |
| 400 `malformed`, 403 `denied` | the same, verbatim | **no** — a verdict, not a transport failure |
| 5xx, timeout, connection refused | 202 `accepted` | **yes**, and it is committed before the answer |

Queueing a 403 would fill the platform with rows holding a stale credential that
no retry could fix. Retries back off 1m → 5m → 15m → 1h → 6h → 12h, eight
attempts, then "given up" with the call still replayable by hand. Delivered and
dead rows are purged after seven days.

### 3.4 The other direction

`health_voip24h._callback_base()` (new) reads `voip24h.callback_base`, which the
relay writes into every serving clinic. So the address a clinic publishes to the
supplier is the **platform's**, with that clinic's own receiver id and token
unchanged. https-only and never a bare host — the string is pasted into a third
party's dashboard. Proven identical below the hostname by test 39.

## 4. Test results (live, `carejiox`)

```
biz_platform_voip_relay: 62 tests 2.01s 1162 queries
0 failed, 0 error(s) of 48 tests when loading database 'carejiox'

health_care_command_voip: 6 tests 0.70s 403 queries
health_voip24h: 84 tests 8.90s 4409 queries
0 failed, 0 error(s) of 70 tests when loading database 'carejiox'
```

`odoo-bin exit=0`, `http=200 (carejiox.com) procs=4`.

## 5. Live end-to-end evidence

A temporary connection was created on the **real `hhh` database** through rail
R5, the relay was allowed to discover it by itself, and calls were sent to
`https://carejiox.com` over the public internet.

```
RECONCILE={'customers': 1, 'addresses': 1, 'pushed': 1, 'problems': 0}
TENANT slug=hhh active=True addresses=1 in_step=True host=hhh.carejiox.com
ROUTE receiver hHqQ3GeV8uoTPj7c -> hhh
HHH_REGISTERED_URL=https://carejiox.com/voip24h/v3/cdr/hHqQ3GeV8uoTPj7c/<token>
```

| # | Sent to `carejiox.com` | Answer |
|---|---|---|
| 1 | completed call, hhh's address + key | `200 {"status": "accepted"}` |
| 2 | the identical call again | `200 {"status": "duplicate"}` |
| 3 | hhh's address, wrong key | `403 {"status": "denied"}` |
| 4 | an address nobody answers to | `403 {"status": "denied"}` |
| 5 | live event, cdr key on the events address | `403 {"status": "denied"}` |
| 5b | live event, correct events key | `200 {"status": "accepted"}` |
| 6 | completed call POSTed as JSON | `200 {"status": "accepted"}` |
| 7 | 300 KB body | `413 {"status": "too_large"}` |

3 and 4 are byte-identical, so the address is not an oracle for which clinics
live behind the platform.

What `hhh` made of it, and what `carejiox` did:

```
HHH_EVENT   id=1 feed=cdr   state=processed
HHH_EVENT   id=2 feed=state state=processed
HHH_EVENT   id=3 feed=cdr   state=processed
HHH_SESSION id=1 dir=incoming outcome=answered  live=final   peer=0977712345 did=02873001234 started=2026-09-17 03:15:30 talk=42
HHH_SESSION id=2 dir=incoming outcome=unknown   live=ringing peer=0977712345
HHH_SESSION id=4 dir=outgoing outcome=no_answer live=final   peer=0977712345 did=02873001234 started=2026-09-17 03:20:00 talk=0
HHH_CALLLOG id=1 dir=incoming type=answered date=2026-09-17 03:15:30 src=0977712345 dst=531 did=02873001234
HHH_CALLLOG id=3 dir=outgoing type=missed   date=2026-09-17 03:20:00 src=531 dst=0977712345 did=02873001234

CAREJIOX_EVENTS=0  CAREJIOX_SESSIONS=0  CAREJIOX_CALLLOGS=0  CAREJIOX_CONFIGS=0
RELAY_QUEUE=0
```

`10:15:30` Asia/Ho_Chi_Minh → `03:15:30` UTC: correct. Every record is in `hhh`;
nothing reached the demo data; no hand-off needed queueing.

The fixture was then removed and the routing table re-read, which dropped the
address on its own (`addresses=0`) — test 13 confirmed against the live system:

```
TEARDOWN={'voip.call.effect': 3, 'voip.call.event': 3, 'voip.call.log': 2,
          'voip.call.leg': 1, 'voip.call.identity': 5, 'voip.call.session': 3,
          'voip.config': 1}
HHH_REMAINING configs=0 events=0 sessions=0 logs=0
```

## 6. A defect this work uncovered and fixed

**`hhh` and `carejiox_template` had been running the V1 phone code against a V1
schema.** The 19.0.3.0.0 wave upgraded `carejiox` only, while the files on the
single shared addons tree changed under every database at once. Both sat at
`19.0.2.0.1` and raised `column voip_call_recording.access_mode does not exist`
on any request that touched a recording — in the tenant's log, which is why a
green platform deploy hid it.

Both were upgraded to `19.0.3.1.0`; neither held any phone data, so nothing was
lost. Ledger §5.197.

| Database | `health_voip24h` | `health_care_command_voip` | `biz_platform_voip_relay` |
|---|---|---|---|
| `carejiox` | 19.0.3.1.0 | 19.0.2.0.0 | 19.0.1.0.0 |
| `hhh` | 19.0.3.1.0 | 19.0.2.0.0 | — (platform only) |
| `carejiox_template` | 19.0.3.1.0 | 19.0.2.0.0 | — (platform only) |

`curl` with `Host: carejiox.com` → 200; with `Host: hhh.carejiox.com` → 200.

## 7. Deviations from the obvious design

1. **The relay forwards over HTTP rather than writing cross-database.** The
   rejected alternative — open the tenant's registry and call `_ingest` there —
   would duplicate the route's size limits, rate limit, transport decode and
   token check in a second place, and would put a public route in charge of
   loading arbitrary registries. Forwarding keeps exactly one implementation of
   "what a call-back means", in the module that owns it. It is also what the
   Meta relay already does on this box.
2. **Hotline routing is operator-typed, not derived.** Nothing in a clinic's
   database records which hotlines it owns, so there is nothing to read. Rather
   than infer it from historical `did` values (which would silently claim a
   number the day a clinic dialled it once), it is typed and unique.
3. **`receiver` routes are read; `hotline` routes are typed** — and a re-read
   deletes only the kind it owns. Test 14.
4. **A 4xx from a clinic is never queued** (§3.3, ledger §5.198).
5. **Both feeds are relayed, but only completed calls can be hotline-routed.**
   Live events carry no hotline. Stated rather than guessed.

## 8. Not done

* **No real phone call has been placed, through the relay or otherwise.** The
  V1 report's provider gates G01–G11 are all still open. Everything above is
  the vendor's documented contract exercised against the real receiver — not the
  vendor calling it.
* No clinic is actually configured with supplier credentials on `hhh`; the proof
  fixture was removed. Setting one up is the ordinary connection screen.
* The supplier has not yet been pointed at `carejiox.com`. Once a clinic's
  connection is registered from its own screen, the address it sends is already
  the platform's.
* `biz_platform_voip_relay` has no `i18n/vi.po` yet. Its screens are
  administrator-only and English-only by design for now.
