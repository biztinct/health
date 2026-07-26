# VoIP24h — API contract capture

**Status: BLOCKED on a human with a Vietnamese internet connection.**
Created by Channel Center Phase CC-F, 2026-07-26.

## Why this document exists

`health_voip24h` ships a full API client — `services/voip24h_api.py`, plus
`cdr_sync.py` and a click-to-dial route — and **not one endpoint in it has
ever been verified against VoIP24h's own documentation.** The paths look like
what someone would guess if they had never read the docs:

| Where | Path | Used by |
|---|---|---|
| `voip_config.py:61` | `https://api.voip24h.vn/v1` (default base) | everything |
| `voip24h_api.py:56` | `POST {base}/auth/login` | `authenticate()` |
| `voip24h_api.py:113` | `GET {base}/calls/history` | CDR sync (cron, ACTIVE) |
| `voip24h_api.py:156` | `GET {base}/calls/{id}` | call detail |
| `voip24h_api.py:183` | `GET {base}/calls/{id}/recording` | recording download |
| `voip24h_api.py:232` | `POST {base}/calls/initiate` | click-to-dial |
| `voip24h_api.py:264` | `GET {base}/extensions` | extension sync |

Two facts make this unresolvable from outside Vietnam:

1. **`docs.voip24h.vn` is geo-blocked.** It answers `ECONNREFUSED` from a
   non-VN address (verified 2026-07-26 against `203.162.56.208:443`).
2. **No third party documents it.** A web search returns nothing describing
   the API surface, no SDK, no community wrapper, no Postman collection.

The live data agrees that none of it has ever worked: **0 `voip.config` rows
and 0 `voip_call_log` rows** on vietuat.

CC-F therefore built the calls channel **receive-only** and forbade itself
from writing, "fixing", or designing against any of those paths. Guessing a
contract and shipping code that depends on the guess is how you get a feature
that looks finished and fails silently in production — the same class of
problem as the manufactured demo credentials CC-D deleted.

## What CC-F did instead

* Adopted the **existing** `/voip24h/webhook` route verbatim. Its verification
  was already sound: `type='http'`, raw `get_data()` bytes, HMAC-SHA256,
  `hmac.compare_digest`, fail-closed when no secret is configured, and a
  generic `{"status":"ignored"}` 200 for an unknown account so the route is
  not an oracle for which clinics live here.
* Routed verified events through the framework: connection lookup by
  `account_id`, the `_may_ingest()` gate, `_note_inbound()` traffic-truth, and
  a `webhook_ignored` audit row when a disabled channel's event is dropped.
* Made `voip.config` a facade over the encrypted connection, so the webhook
  secret stops living in a plaintext column.
* Set the channel's required checks to `webhook_verified` + `inbound_ok` —
  the only two things arriving traffic can honestly prove.

**A `voip.config` created by the Channel Center deliberately leaves `api_key`
and `api_secret` empty.** That is a safety mechanism, not an oversight:
`_check_credentials()` refuses to build an API client without them, so every
unverified endpoint above stays unreachable from a Center-created connection —
including the recording download, which would otherwise fire from a real
`recording.available` event.

## What a human on a VN connection must capture

Open <https://docs.voip24h.vn/> (or ask VoIP24h support directly) and fill in
every row below. Paste real values, not paraphrases. **Redact nothing except
actual secrets** — an ellipsis in a path is what makes a capture useless.

### 1. Base URL and versioning
- [ ] Production base URL (is `https://api.voip24h.vn/v1` right at all?)
- [ ] Sandbox / staging base URL, if one exists
- [ ] How the version is expressed (path segment? header? not versioned?)

### 2. Authentication
- [ ] Scheme: static API key header, HTTP Basic, OAuth2, or a login endpoint
      that returns a bearer?
- [ ] If a login endpoint exists: its **exact** path, method, request body and
      response shape
- [ ] The exact header name(s) an authenticated request carries
- [ ] Token lifetime and whether refresh exists
- [ ] Whether the credentials in the portal are per-account or per-extension

### 3. Call history (CDR)
- [ ] Exact path and method
- [ ] Every required query parameter (date range format? timezone? inclusive?)
- [ ] Pagination: page/offset/cursor, the parameter names, the page-size cap
- [ ] Rate limits, and what a throttled response looks like
- [ ] One **real** response body, with 2–3 records (numbers may be masked)

### 4. Recordings
- [ ] Is `recording_url` in the webhook payload directly downloadable, or does
      it need a second authenticated call?
- [ ] The exact download path and its auth header
- [ ] Content type and whether the URL expires

### 5. Webhooks — the highest-value item
- [ ] The full event catalogue (names as VoIP24h spells them). Our code
      assumes `call.started`, `call.answered`, `call.ended`, `call.missed`,
      `recording.available` — **is that the real list?**
- [ ] **One real captured payload per event**, headers included
- [ ] The exact signature header name. We accept `X-Voip24h-Signature` and
      `X-Signature` — is either correct?
- [ ] **What string is signed**: the raw body alone, or body + timestamp, or
      something else? Which hash? Hex or base64? Any `sha256=` prefix?
- [ ] Whether the payload really carries an `account_id`, and under that name
- [ ] Retry policy: how many times, over what window, on which status codes
- [ ] Who sets the webhook URL — the portal, or support?

### 6. Click-to-dial (only if it exists)
- [ ] Does an originate/click-to-dial API exist at all?
- [ ] Exact path, method, body, and what identifies the calling extension
- [ ] What the response says, and how the resulting call correlates with the
      later webhook events (a shared call id?)

### 7. Extensions
- [ ] Is there an API to list extensions, or is it portal-only?

## Until this is filled in

- Outbound calling stays **unimplementable**. So does CDR sync, the recording
  download, and extension sync.
- The Calls card stays **receive-only** and says so.
- `voip24h_api.py` stays **untouched**. It is not "nearly right" — it is
  unverified, and editing it would only make the guesses look considered.

Once captured, the next phase can be scoped honestly: verify each endpoint
against the capture, delete whatever turns out not to exist, and only then
build the outbound half.
