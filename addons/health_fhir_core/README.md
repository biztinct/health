# health_fhir_core — FHIR R4 Facade (read-only, Phase 1)

Read-only FHIR R4 (4.0.1) facade over the health19 home-care platform.
Spec: `docs/strategy/design-platform-services.md` §C and
`docs/strategy/architecture-interop.md` §1.1.

## Endpoints

| Route | Verb | Behavior |
|---|---|---|
| `/fhir/r4/metadata` | GET | CapabilityStatement (public, no PHI) — generated from the serializer registry |
| `/fhir/r4/<Resource>` | GET | search → `Bundle{type: searchset}` with cursor paging |
| `/fhir/r4/<Resource>/<id>` | GET | read → resource, or 404 `OperationOutcome` |

Responses use `Content-Type: application/fhir+json; charset=utf-8`. All errors
are `OperationOutcome` (401 `login`, 403 `forbidden`, 404 `not-found`,
400 `invalid` / `not-supported`). Unsupported search params are **strictly
rejected** with 400 — never silently ignored.

## Resources and search parameters

| Resource | Odoo model | Search params (plus `_lastUpdated`, `_count`, `_cursor`) |
|---|---|---|
| Patient | `res.partner` (`is_patient`) | `identifier`, `name`, `telecom`, `phone`, `birthdate` |
| Practitioner | `hr.employee` (`healthcare_facility_id` set) | `identifier`, `name` |
| Organization | `health.facility` | `name`, `identifier` |
| Location | `health.facility` | `name`, `organization` |
| Encounter | `health.fieldservice.order` (assigned → closed) | `patient`, `date`, `status` |
| Appointment | `health.fieldservice.order` (all states) | `patient`, `date`, `status` |
| ServiceRequest | `health.fieldservice.order` | `patient`, `status` |
| DocumentReference | `health.clinical.note` | `patient`, `encounter`, `date` |

One FSO ⇒ three linked resources: `Appointment` (planned slot, incl.
draft→proposed / confirmed→booked / cancelled→cancelled), `Encounter` (the
actual visit, `class=HH`, only from `assigned` onwards) and `ServiceRequest`
(the order, sale-quote lines as `orderDetail[]`). `Encounter.appointment` and
`ServiceRequest.encounter` cross-link them, all sharing the FSO id.

Stable FHIR `id` = Odoo record id. `identifier[]` carries the internal refs
(`urn:health19:*`) plus the VNeID slot (`https://vneid.gov.vn/id`) when
`national_id` is set (decrypts transparently via the ORM;
**exact-match search only** — it is a blind-indexed encrypted field).

## Pagination

`_count` (default 50, max 200) + `_cursor=<last id>`; results are ordered
`id asc` and `Bundle.link[rel=next]` carries the next cursor until exhaustion.

## Auth, scoping, audit

- Tokens are authenticated by `health_api_gateway`
  (`_gateway_authenticate`); routes themselves are `auth='none'`.
- Required scope: `system/<Resource>.read` (or blanket `system/*.read`).
- Queries run **as the token's service user** — existing record rules
  (catchment scoping) apply. Only audit-log writes use sudo.
- Every read/search is logged to `api.audit.log` including the subject
  `patient_ids`.

**Recommendation:** create a dedicated `fhir_readonly` service user per
integration partner, restricted to the relevant facilities/catchments via the
standard access roles, and issue its gateway token with only the scopes the
partner needs.

## Validation

`serializers.base.validate_resource(dict)` constructs the corresponding
`fhir.resources` (pydantic v2, R4B) class. Tests validate every serialized
resource this way. Optional runtime validation of responses can be enabled
with the config parameter `health_fhir_core.validate_responses = 1`.

## Notes

- Odoo datetimes (naive UTC) serialize with an explicit `+00:00` offset.
  Vietnamese diacritics are preserved (`ensure_ascii=False`).
- `DocumentReference.content[]` image entries point at Odoo
  `/web/content/<id>` URLs, which require separate Odoo authentication
  (also stated in the CapabilityStatement description).
- No models, no UI — the facade is stateless; nothing else may depend on
  this module (architecture §6.8).
