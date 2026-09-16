# VoIP24h — implementation report

Date: 17 September 2026
Branch: `19.0`
Design: `docs/strategy/handovers/voip24h-notifications-and-calling-design.md`
Vendor sources: `docs/voip24hdocs/{Authorization,Webhook,Overview WebRTC}.docx`
Deployment target: `VietUcUAT` / database `carejiox` (master)

## 1. What was built

The module was rebuilt around one idea the previous version did not have:
**"we do not know" has to be sayable.** The old parser turned an
unrecognised call type into `answered`, an unrecognised status into
`completed` and a missing call time into `now`; the old webhook returned
HTTP 200 from a blanket `except` with nothing stored; the old REST client
called six endpoints no supplied document describes. Each of those turns an
absence of information into a confident, wrong fact.

Three capabilities, enabled independently because they depend on different
things:

| Capability | What a user gets | What it needs |
|---|---|---|
| Call history | One row per customer interaction, its legs preserved, recording links recorded | The completed-call call-back, authenticated |
| Live awareness | Ringing / answered / ended alerts, to the people entitled to see them | The live-events call-back (supplier-configured) |
| Browser phone | Dial, answer, reject, hang up, mute, hold, guarded transfer and keypad | The WebRTC SDK, SIP credentials, microphone, working media path |

### Modules and files

**`health_voip24h` 19.0.2.0.1 → 19.0.3.0.0** (~12,800 lines of module code)

New:
- `services/voip_crypto.py` — AES-256-GCM at rest, own HKDF subkey
- `services/phone_ident.py` — raw / matching-key / E.164 / dial-string, kept apart
- `services/event_normalizer.py` — both feeds, plus the inbox serialiser
- `services/event_reducer.py` — correlation, state reduction, callbacks, effects
- `services/event_worker.py` — inbox drain and effect delivery
- `services/recording_fetch.py` — SSRF-guarded fetch and Range streaming
- `models/voip_call_session.py` — `voip.call.session` / `.leg` / `.identity`
- `models/voip_call_event.py` — `voip.call.event`, the durable inbox
- `models/voip_client.py` — `voip.call.action` / `.client.lease` / `.call.effect`
- `controllers/phone.py` — the phone panel's authenticated API
- `controllers/recording.py` — authorised playback
- `static/src/js/voip_phone_service.js` — the phone runtime
- `static/src/js/voip_phone_panel.js` + `xml` + `scss` + icons `css`
- `static/src/js/sdk_host_bridge.js` — runs inside the isolated SDK frame
- `views/voip_sdk_host.xml`, `views/voip_call_session_views.xml`

Rewritten: `services/voip24h_api.py`, `services/cdr_sync.py`,
`services/call_handler.py`, `controllers/webhook.py`, `models/voip_config.py`,
`models/voip_extension.py`, `models/voip_call_log.py`,
`models/voip_call_recording.py`, `security/*`, `data/voip24h_cron.xml`,
`views/voip_config_views.xml`, `views/voip_extension_views.xml`,
`views/voip_call_recording_views.xml`, `views/voip_menus.xml`,
`static/src/js/click_to_dial_widget.js`, `wizard/voip_sync_wizard.py`,
`i18n/vi.po` (+156 entries), `tests/test_voip24h.py`.

Deleted: `controllers/api.py`, `static/src/js/call_popup_service.js`,
`static/src/xml/call_popup.xml`, `static/src/scss/call_popup.scss`.

**`health_care_command_voip` 19.0.1.1.0 → 19.0.2.0.0** — `models/hooks.py`
rewritten, `tests/test_bridge.py` fixture repaired.

**`health_care_command` 19.0.4.2.3 → 19.0.4.3.0** — `static/src/js/care_command.js`
only: the global bus topic it subscribed to no longer exists. This is a
**forced** shared-file change (see §6).

## 2. Vendor contracts, as implemented

### Authentication (V1)
`POST https://api.voip24h.vn/v3/authentication` with `apiKey` / `apiSecret` /
`isLonglive`. Body `status` must be `1000`; HTTP status is checked separately.
The vendor's spelling `expried` is preserved in the parser. Bootstrap sends
**no** `Authorization` header — V1's prose mentions one and its own cURL
sample does not, and there is no such thing as a bootstrap token.
`isLonglive` goes on the wire as a JSON boolean (the declared type) with a
one-field switch to the string form every vendor sample actually uses.

`expried` carries no timezone, so it is read in the connection's declared
provider timezone and stored naive UTC, with the *quality* of that reading
recorded: `ok` / `missing` / `unparsable` / `no_timezone`. Anything but `ok`
puts the connection into a visible `degraded` state and schedules renewal on
the documented lifetime — never a silently assumed seven days.

Renewal is single-flight per connection through a PostgreSQL **advisory**
transaction lock, not a row lock: the token is written from the same
transaction that holds it, which is precisely §5.74's self-deadlock.

### Completed-call subscription (V2)
`POST` / `DELETE https://api.voip24h.vn/v3/webhook-call-log/` (trailing slash
preserved), `Authorization: Bearer`, success is body `status: 200`. `param`
goes as an object, as the samples show. Registering refuses outright when a
different address is already registered and nothing has been written in
Registration Notes — replacing another system's call-back silently is how
their call records stop arriving with nobody knowing why.

### The two delivery feeds
Feed A (completed records) and Feed B (live states + nested CDR) are both
parsed. All five documented dispositions map; a sixth value becomes `unknown`
and is flagged. `type` accepts the vendor's own misspellings
(`Outbount`/`Inbounf`) as well as the correct spellings its samples use. The
nested `cdr` object is accepted as JSON text, as bracketed `cdr[source]=…`
parameters, or as the `key: value` block the vendor's table prints; anything
else is reported unreadable rather than half-parsed.

### The SDK (V3)
`initGateWay`, `registerSip`, `isRegistered`, `call`, `answer`, `reject`,
`hangUp`, `toggleMute`/`isMute`, `toggleHold`/`isHold`, `transfer`,
`sendDtmf`. The prose/sample disagreement about `incomingCall` vs
`incomingcall` is resolved at runtime by probing both. There is no
`unregister`, so the panel tears the frame down and **says** that it cannot
sign the extension out of the PBX. `sendDtmf`'s documented once-per-call limit
is honoured rather than shipping a keypad that stops working silently.

## 3. Corrections to the previous implementation

| Area | Was | Now |
|---|---|---|
| REST client | `/auth/login`, `/calls/history`, `/calls/{id}`, `/calls/{id}/recording`, `/calls/initiate`, `/extensions` — all invented | V1/V2 only; each unevidenced endpoint is one explicit refusal behind a `*_verified` flag |
| Webhook ack | 200 from a blanket `except`, nothing stored | 200 only for durably stored / quarantined / duplicate; 503 when storage fails |
| Unknown values | defaulted to `answered` / `completed` / `now` | explicit `unknown`, and a missing call time is refused, never stamped with the sync time |
| Call identity | one `call_id` meaning four different provider ids | four columns plus a namespaced `voip.call.identity` per alias |
| Notifications | global `voip_notifications` bus topic — every caller's number to every signed-in browser | per-recipient channel, identifiers only; details fetched through an authorised call |
| Click-to-dial | posted to an unverified endpoint and showed "Call initiated" | the browser places the call; the button is disabled with a reason when it cannot |
| Contact matching | `like` on the last nine digits, first hit wins | exact key, company-scoped, one match or an explicit `ambiguous` |
| Care bridge | on create, before matching; every outgoing call set `waiting` and zeroed unread | after finalisation and matching, idempotent, and only a call that *connected* closes the obligation |
| Extension ownership | route accepted any `extension_id` in the config | the current user's assigned extension, never a supplied id |
| Company isolation | manager rule `[(1,'=',1)]` with no global rule beneath it | a global company rule on every model; role rules broaden only within it |
| Recording type | defaulted `audio/mpeg` on a `.gsm` file | observed from the response; an HTML wrapper is reported as one |
| Crons | three active, one able to call an unevidenced endpoint every 15 min | history/recording/legacy-activity jobs ship **off**, and the code refuses even if switched on |

## 4. Test results (verbatim, `carejiox`)

Run 3, `carejiox-deploy -d -m health_voip24h,health_care_command_voip -t /health_voip24h,/health_care_command_voip`:

```
health_care_command_voip: 6 tests 0.61s 403 queries
health_voip24h: 84 tests 5.10s 4409 queries
0 failed, 0 error(s) of 70 tests when loading database 'carejiox'

==> odoo-bin exit=0
==> starting odoo
==> http=200 (carejiox.com) procs=4
```

Offline parser smoke (no Odoo, run before each deploy): **47 assertions
passed** covering the §17.1 fixture, all five dispositions, unknown-value
handling, the datetime round-trip, both nested-CDR encodings, state-token
mapping, and every number representation.

### Live HTTP evidence (`carejiox`, real routes, real database)

A disposable connection, extension and operator account were created, driven,
and then removed (§5.34 — teardown verified on a fresh cursor: 0 configs,
0 sessions, 0 events remain, the account is archived with a scrambled
password).

| Check | Request | Result |
|---|---|---|
| W06 wrong token | `GET /voip24h/v3/cdr/<receiver>/<token>WRONG?…` | `403` |
| W06 unknown receiver | `GET /voip24h/v3/cdr/nosuchreceiver/<token>?…` | `403` — the SAME answer, so the route is no oracle |
| W01 valid completed-call GET | the vendor's own query shape | `200 {"status":"accepted"}` |
| W03 duplicate delivery | byte-identical repeat | `200 {"status":"duplicate"}`, one event row |
| W09 unparsable `calldate` | `calldate=soon` | `200 {"status":"accepted"}`, event `quarantined / bad_call_date`, **no call created** |
| W06 parameter pollution | two `disposition` values in one URL | `400 {"status":"malformed"}` |
| Transport | `POST` `application/json` | `200 {"status":"accepted"}`, recorded as `post_json` |
| Oversize body | 300 KB JSON | `413` |

What the two accepted deliveries then became, after the worker drained:

```
sessions
115 | incoming | 0977700099 | +84977700099 | final | no_answer | callback resolved | 14s
116 | outgoing | 0977700099 | +84977700099 | final | answered  | none              | 42s talk / 50s total

call records
cdr:VOIPQA-CDR-1 | feed_a | incoming | missed   | no_answer | "NO ANSWER" | 2026-09-17 02:13:50 | wait 14s | tz Asia/Ho_Chi_Minh
cdr:VOIPQA-CDR-2 | feed_a | outgoing | answered | completed | "ANSWERED"  | 2026-09-17 02:20:00 | wait  8s | tz Asia/Ho_Chi_Minh

events    final_cdr processed | final_cdr quarantined(bad_call_date) | final_cdr processed
effects   care_projection done | activity done | notify:missed_inbound done
          care_projection done | notify:call_recorded done
```

Three things worth reading in that: the missed inbound call raised a call-back
**and one task**; the answered outbound call to the same number **resolved**
it; and the times are stored in UTC having been read as Asia/Ho_Chi_Minh
(`09:13:50` local → `02:13:50` stored), with the zone recorded alongside.

**What these prove and what they do not.** Unit tests prove parsing and state
reduction. They prove nothing about audio. No claim in this report should be
read as evidence that a call can be heard — that is the P-series of the
acceptance matrix and needs a real handset against a real account.

## 5. Defects found by running it (not by reading it)

Four, each caught by the first live run and each worth the ledger:

1. **`_register` is an Odoo internal.** `models.Model._register` is the boolean
   that decides whether a model class joins the registry. A method of that
   name shadows it and every call becomes `True(...)` —
   `TypeError: 'bool' object is not callable`, raised nowhere near the
   definition. 26 tests errored on one name. *Proposed ledger §5.195.*
2. **A write guard ate the one write it existed to permit.** `write()` stripped
   `sip_password_enc` from every `vals` — including the cipher's own write, so
   no password was ever stored and no error was raised. The guard now keys on
   a context flag the internal path sets.
3. **`callid` is not unique.** The final-record upsert fell back to matching on
   it, which merged a ring group's losing leg into the winner's record — two
   pieces of evidence collapsed into one, and a transfer would have lost a leg
   the same way. The fallback now applies only when the record has no provider
   CDR id of its own.
4. **JSON has no datetime.** The inbox serialised with `default=str` and read
   back strings; every string is truthy and comparable, so this only fires on
   the branch that does arithmetic with them. Fixed with an explicit converter
   in both directions, with its own test.

## 6. Deviations from the design, and why

1. **Core owns its own cipher** (`services/voip_crypto.py`) instead of failing
   closed without the Channel Center. The design's rule leaves a standalone
   `health_voip24h` with no credential storage at all, i.e. every
   credential-dependent feature dead. The intent behind it — encrypted at rest,
   no plaintext fallback, acyclic dependencies (§5.71) — is fully met by an
   independently-keyed core cipher, and `_voip_secret_backend()` stays
   overridable: the bridge points it at the connection store wherever a
   Channel Center owns the setup.

2. **Patient-catchment scoping is NOT applied to call records.** A call arrives
   before anyone knows who is on the line; scoping the list by the caller's
   catchment would hide every unmatched and withheld-number call from the desk
   whose job is to ring them back. The clinical boundary is enforced where it
   belongs: on the patient record the call links to, and on recording playback,
   which is its own permission. Stated here because it is a deliberate
   departure, not an omission.

3. **The vendor sample's one-second offsets are NOT flagged.** The design calls
   the sample self-contradictory. It is off by exactly one second in *both*
   pairs (130 measured vs 129 stated; 122 vs 121), which is inclusive/exclusive
   rounding, not a contradiction. The tolerance is 2 seconds; a flag that fires
   on every call is a flag nobody reads. A real contradiction is still flagged,
   and both numbers are always kept — `test_22b` proves both halves.

4. **`health_care_command/static/src/js/care_command.js` was edited** — a shared
   module outside the design's sanctioned list. Forced: removing the global
   `voip_notifications` topic (a disclosure fix the design requires) would have
   left Care Command's ringing hero subscribed to a topic nothing sends to, and
   dark with no error. The change is the channel name, the event name and the
   payload key; nothing else in that file moved. Declared per §4 of the
   conventions.

5. **`health_care_command_voip/tests/test_bridge.py` fixture repaired.** Its
   `get_conversation_detail` assertion failed on `carejiox` for a reason that
   predates this work: `care.conversation._scope_domain` filters by catchment
   area, the fixture patients all carry one, and uid 1 on this deployment has
   no area and is not an owner. The engine is right; the fixture was
   under-specified (§5.62 — fix the test, not the engine). The test user is now
   given its patients' area.

6. **The legacy `/voip24h/webhook` route was not re-pointed at the v3 parsers.**
   Nothing in the supplied documentation produces its shape. Re-pointing it
   would mean accepting an anonymous GET on a route whose whole contract is a
   signed POST. It keeps its fail-closed HMAC and should be retired outright
   once it is established that nothing posts to it. Its one behaviour change:
   an internal error now answers 503, not 200.

## 7. Security posture

- **Callback authentication** is a 256-bit URL token per feed, compared in
  constant time, stored as a digest with the original encrypted for
  re-registration, rotatable with a 24-hour overlap. It is labelled accurately
  in the UI: it proves possession of the address, **not** body integrity or
  freshness. No supplied document describes a signature; requiring the
  previously-invented HMAC headers would refuse every real delivery.
- **Tenant routing** is by receiver id alone. Never a query `db`, never
  `account_id`, never an extension.
- **Refusals are uniform**: an unknown receiver and a wrong token get the same
  403, so the route is not an oracle for which clinics live here.
- **SIP passwords** reach the owning browser — the documented SDK takes them in
  clear, and the code says so rather than claiming otherwise. They are
  encrypted at rest, never readable back through a record read, an export or a
  generic RPC, handed out only to the assigned user over a no-store response,
  and held in a closure rather than on the reactive state object.
- **Recording fetch** enforces https, an exact host allow-list, public-IP-only
  resolution, re-validated redirects, no credential or cookie forwarding,
  bounded time and size, and observed media type. The vendor's own links embed
  `hostname=192.168.2.51` as a query *value*; query text is not a network
  target and is not treated as one.
- **Provider facts refuse a normal RPC write** on both the call log and the
  session. Staff can write notes and an outcome; they cannot mint a completed
  call. The guard is a context key, not `env.su` — §5.4: uid 1 always runs su,
  so an su-based guard is dead code for admin and in every test.

## 8. Operational notes

- Crons shipped **on**: event drain, effect drain, session finalisation, lease
  expiry, token renewal, raw-event retention, recording retention.
  Shipped **off**: past-call polling, recording fetch, legacy missed-call
  activities. §5.178/§5.192 — an upgrade switches the golden template's jobs
  back on; re-check `carejiox_template` after deploying this.
- `/voip24h/v3/cdr/<receiver>/<token>` and `/voip24h/v3/events/<receiver>/<token>`
  are the addresses to give the supplier. **Configure the edge to redact these
  paths from access logs** — the address is the credential.
- Rollback: switch `cdr_ingest_enabled`, `state_ingest_enabled`,
  `webrtc_enabled` and `outbound_enabled` off independently. The inbox keeps
  every message, so nothing is lost while a feed is off and replay is a button.
  Do not delete the provider subscription as a generic disconnect.

## 9. Still open — provider gates

Nothing below blocks what has shipped; each blocks one capability from being
switched on for a real clinic.

| Gate | Needed from VoIP24h | Blocks |
|---|---|---|
| G01 | Bootstrap header requirement; boolean vs string `isLonglive`; expiry timezone; token invalidation on re-issue | Unattended credential renewal |
| G02 | Real POST content type and body; GET encoding; whether `param.auth` is delivered; signature support; source IPs | Turning the call-backs on for a clinic |
| G03 | Retry schedule, acknowledgement contract, timeout, ordering, `msgid` uniqueness | Reliability sign-off |
| G04 | Whether several subscriptions are allowed; who owns the current one | Changing a live subscription |
| G05 | Timed captures proving Ring/Up arrive *during* a call; nested CDR encoding | PBX-wide live alerts |
| G06 | Meaning and scope of `id`, `callid`, `uniqueid`, `linkedid`; transfer and ring-group examples | Cross-feed grouping beyond what is implemented |
| G07 | SDK version and licence; error and terminal callbacks; session ids; disconnect/unregister | Production browser calling |
| G08 | SIP host/user/password; WSS, ICE/TURN, codecs, browsers, firewall paths | Registration and two-way audio |
| G09 | Exact transfer semantics; what "DTMF once" means; multi-registration policy | Transfer and keypad |
| G10 | Which recording URL yields audio; auth, redirects, codec, expiry/refresh | Recording playback |
| G11 | Historical CDR, extension listing and originate contracts, if offered | Past-call sync, extension sync, desk-phone dialling |

## 10. Not done

- **No real call has been placed.** Browser calling is implemented and its
  logic is tested against a mocked SDK surface; it is not proven. G07/G08 have
  to be answered and then P03–P10 run with a handset.
- **No live capture.** Every fixture is invented (§17.1's rule). The contract
  matrix at `docs/voip24hdocs/contract-capture.md` is not written because
  nothing has been captured yet.
- **Recording playback is untested against a real link** for the same reason.
- **The old `design/health-voip24h-implementation.md` and
  `docs/strategy/voip24h-contract-capture.md`** still need supersession links.

Per the design's own rule: **this integration is not complete.** Call logging
and notifications are implemented and unit-proven; actual inbound and outbound
calling is implemented and unproven.
