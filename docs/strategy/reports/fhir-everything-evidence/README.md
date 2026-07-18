# Patient `$everything` — evidence pack

Live captures from **vietuat** (health_fhir_core 19.0.1.3.0). All PHI here is a
**QA fixture patient**, deleted after capture (fresh-cursor verified). No real
patient record appears.

## How the token was obtained (gateway client-credentials)
```
POST /oauth/token
  grant_type=client_credentials
  client_id=<QA client>  client_secret=<QA secret>
  scope=system/*.read
→ { "access_token": "hg_…", "token_type": "Bearer", "scope": "system/*.read" }
```
The QA service user was granted `group_healthcare_owner` (record-rule visibility)
plus the accounting-readonly group (a pre-existing Patient-serializer quirk — see
note at the bottom).

## Files

| File | Request | Result |
|---|---|---|
| `ev_metadata.json` | `GET /fhir/r4/metadata` | CapabilityStatement — the Patient resource declares `operation: [{name: everything, definition: …/Patient-everything}]`. |
| `ev_everything.json` | `GET /fhir/r4/Patient/9765/$everything` (log-only, consented QA patient) | HTTP 200 `searchset` Bundle, `total: 9`, 10 entries. |
| `ev_deny.json` | `GET /fhir/r4/Patient/9766/$everything` (consent **enforced**, UNconsented QA patient) | HTTP **404** `OperationOutcome not-found` — deny with **no existence reveal**. |
| `ev_allow.json` | `GET /fhir/r4/Patient/9765/$everything` (consent **enforced**, consented QA patient) | HTTP 200 full Bundle (`total: 9`) — consent lets the whole record through. |

## What the bundle proves (`ev_everything.json`)

Entry composition (order + `search.mode`):
```
Patient           match     ← compartment ROOT, first
Appointment       include
CarePlan          include
Consent           include
DocumentReference include
Encounter         include
Observation       include   (×2)
ServiceRequest    include
OperationOutcome  outcome   ← DECLARED omission (see below)
```
- The whole record is returned in **one** consent-gated call, composed from the
  existing per-resource serializers (no new serializers).
- `Bundle.total = 9` counts the real matches; the 10th entry is the declared
  OperationOutcome, not a resource.

## Consent gate fired ONCE and was logged

`health.consent.check.log` rows with `source = 'fhir_everything'`: **4 rows**
across the two QA patients — `9765` → result **True** (consented), `9766` →
result **False** (unconsented). One whole-record decision per release, always
audited, in both log-only and enforced modes.

## Declared omission (not silent truncation)

`health.fall.risk` (the FHIR **Flag** resource) ships on this DB with **no
`ir.model.access` row for any group**, so no token user can read it. Rather than
hard-fail the entire export with a 403, `$everything` OMITS the unreadable type
and DECLARES it in an `OperationOutcome` (`severity: warning`, `code:
suppressed`) — visible in `ev_everything.json` / `ev_deny.json`:
> "This $everything response OMITS resource types the caller is not authorized
> to read (Flag). … no data was leaked, but a complete export requires broader
> read authorization."

A `_count` cap hit is declared the same way with `severity: information`,
`code: incomplete`.

## Route note (werkzeug + literal `$`)

The route is registered literally as
`/fhir/r4/Patient/<int:rid>/$everything`. werkzeug accepts the literal `$`
(the 403/404/200 responses above all reached the handler — no fallback
`<string:op>` dispatch was needed).

## Pre-existing facade quirk (NOT this phase)

The Patient serializer's `serialize_batch` bulk-`fetch`es every stored
`res.partner` field, including group-gated accounting/signup fields
(`credit_limit`, `signup_type`, …). A token user lacking those groups gets a 403
on **any** Patient serialization — including the plain `GET /fhir/r4/Patient/<id>`
read, confirmed identical. Out of scope here (no per-resource serializer edits);
flagged for the facade owners.
