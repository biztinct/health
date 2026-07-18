# health_fhir_core — Patient `$everything` (whole-record clinical export)

The `/fhir/r4` facade already serves 18 R4 resource types (Patient, Encounter,
Observation, DocumentReference, …) via per-resource `read`/`search`, all
consent-gated. What it CANNOT do is hand a receiving system a patient's WHOLE
clinical record in one interoperable, single-consent call — the standard FHIR
**`Patient/$everything`** operation. That is the real "born-FHIR clinical
export" gap and the Circular-13 EMR-handoff / referral use case: a facility or
the MOH pulls the complete record once, under one `data_sharing` consent
decision, instead of walking every resource type by hand.

This phase adds that operation by COMPOSING the existing serializers — no new
resource serializers, no new clinical models. It is an extension of the FACADE
+ the serializer BASE, not a new module.

Read `HANDOVER-CONVENTIONS.md` first (§4, §5 ledger; §5.45 no-concurrent-
odoo-bin-during-upgrade; §5.38 gateway readonly-cursor if you touch any write).
All plumbing below is pre-verified from a live scout — do not re-derive.

---

## 0. Scope and binding non-goals

**Build (health_fhir_core only — extend the facade):**
1. A gather helper that, given a patient id, iterates `REGISTRY` and reuses each
   serializer's EXISTING `search_params['patient']['domain']('Patient/<id>')`
   callable (the same convention `fhir.adapter.vn.build_patient_bundle` uses —
   §1) to collect "this patient's records of type X". NO new per-serializer
   hook.
2. `GET /fhir/r4/Patient/<id>/$everything` — a new controller route that
   gathers the patient's compartment across all PHI serializers, applies the
   EXISTING consent gate as ONE whole-record decision, and returns a `searchset`
   Bundle (Patient resource first, then the compartment). Supports `_since`
   (lastUpdated filter), `_type` (restrict resource types), `_count` +
   cursor pagination.
3. CapabilityStatement: declare the `$everything` operation on Patient.
4. Audit: one `api.audit.log` export row + the `data_sharing` consent-check log
   for the whole-record release.
5. Tests + (no user-facing strings → vi.po only if any). Bump health_fhir_core.

**Binding NON-goals:**
- NO new resource serializers (Condition/Procedure/etc. are a later phase — the
  diagnosis `Condition` gap needs a per-diagnosis record model + the AI-coding
  write path; out of scope here).
- NO new clinical models, NO writes to any clinical/accounting data (read-only
  export). NO change to the per-resource read/search routes' behavior.
- NO bypass of the consent gate or record rules — `$everything` must be AT
  LEAST as strict as the per-resource facade (one PHI leak here dumps a whole
  record). NO `_include`/`_revinclude` cross-references beyond the compartment.
- NO outbound submission / adapter / VSS / BHYT. NO PWA. NO pip (fhir.resources
  already installed). NO messaging.

---

## 1. Verified plumbing facts (do not re-derive) — from the live scout

All in `health_fhir_core/` unless noted.

- **Serializer registry:** `serializers/__init__.py:30-54` — `REGISTRY = {s.resource_type: s}`
  over instantiated serializers. 18 registered. The facade resolves
  `REGISTRY.get(rtype)`.
- **Serializer base** (`serializers/base.py:264-433`): a serializer declares
  `resource_type`, `odoo_model`, `search_params`, and implements
  `base_domain(env)`, `to_fhir(record)`, `patient_ids_of(records)`. Helpers:
  `self.meta(record)`, `self.reference(type,id,display=None)`,
  `serialize_batch(records)`, `read_record(env, rid)`, `search_records`,
  `search_bundle`.
- **`patient_ids_of(records)` (the PHI contract):** returns res.partner ids the
  records carry; `[]` for non-PHI (Organization/Location/Practitioner). This is
  EXACTLY the set of serializers that belong in a patient compartment: **a
  serializer is in the patient compartment iff `patient_ids_of` is non-empty.**
- **Consent gate** (`serializers/base.py:221-258`): `consent_enforced(env)`
  reads `health_fhir_core.consent_enforced` (default False = log-only);
  `consent_allowed_records(env, serializer, records, enforced)` keeps a record
  only if EVERY patient it carries has active `data_sharing` consent
  (`health.consent.check_consent(pid,'data_sharing')`, ctx
  `consent_check_source='fhir_facade'` → writes a `health.consent.check.log`).
  Non-PHI (`patient_ids_of==[]`) never gated. Deny-by-default when enforced.
- **Facade controller** (`controllers/fhir.py:42-96`): `fhir_search` +
  `fhir_read`, `type='http', auth='none'`, authenticated via
  `_authenticate(serializer)` → `health_api_gateway._gateway_authenticate` +
  scope check (`system/<Resource>.read` or `system/*.read`); runs under
  `request.env(user=user.id)` so RECORD RULES apply; `_fhir_response(...)`,
  `FHIRNotFound`/`FHIRNotSupported` → OperationOutcome. Audit via
  `api.audit.log` (fhir.py:141).
- **search_bundle** (`base.py:389-433`): builds a `searchset` Bundle with
  `entry[].fullUrl/resource/search.mode`, `total`, cursor `next` link; applies
  a `record_filter` (the consent gate) to the page before serialization and
  adjusts `total` down. **Reuse this shape for the $everything bundle.**
- **Cursor pagination:** `_count` default 50 max 200; `_cursor=<last_id>`
  (base.py:360-382). `_lastUpdated` is a supported date param on every resource
  via `build_domain` (base.py:316-336, maps to `write_date`).
- **CapabilityStatement** (`capability.py:20-75`): built dynamically from
  `REGISTRY`; each resource lists interactions + searchParam. **Add the
  `$everything` operation to the Patient entry here** (a
  `rest.resource[].operation[]` with `{'name':'everything',
  'definition':'http://hl7.org/fhir/OperationDefinition/Patient-everything'}`).
- **PRIOR ART — the compartment is ALREADY gathered elsewhere (reuse the
  convention, do NOT reinvent):** `fhir.adapter.vn.build_patient_bundle(patient)`
  (`health_fhir_adapter_vn`) already collects a patient's whole compartment
  (Patient + Encounter/Observation/CarePlan/Goal/Med*/QR/AdverseEvent/Flag/
  Consent/DocumentReference + synthetic ICD-10 Condition entries) for OUTBOUND
  VN MOH submission (export button → attachment + `fhir.submission.log`). It
  does this by calling **each serializer's OWN `search_params['patient']['domain']('Patient/<id>')`
  callable** to get the canonical patient-forward domain — no per-field
  guessing. **`$everything` is the READ-facade analog** (a consumer pulls it via
  GET, consent-gated, paginated) — it must be COUNTRY-NEUTRAL (health_fhir_core
  only) and MUST NOT call or edit the VN adapter, but it MUST reuse the same
  `search_params['patient']['domain']` convention. So:
  - **The patient compartment = every REGISTRY serializer that has a
    `search_params['patient']` entry** (Patient/Encounter/Appointment/
    ServiceRequest/Observation/DocumentReference/CarePlan/Goal/Task/
    MedicationRequest/MedicationAdministration/QuestionnaireResponse/
    AdverseEvent/Flag/Consent). Its forward domain =
    `serializer.search_params['patient']['domain']('Patient/%d' % pid)`.
  - Non-PHI (Organization/Location/Practitioner/Questionnaire-template) have NO
    `'patient'` param → excluded automatically. This set matches the
    non-empty-`patient_ids_of` set (asserted by a test, §4.3).
  - **Do NOT add a new `compartment_domain` hook** — reuse the existing
    `search_params['patient']['domain']` convention (the same one
    build_patient_bundle relies on). If a serializer's patient param is named
    differently (e.g. `'subject'`), the completeness test (§4.3) catches it;
    handle by checking `'patient'` then `'subject'` in the gather helper.
- **Optional-field guard convention** (`document_reference.py:84`,
  `patient.py:115`): `if 'field' in record._fields:` — keep it; no hard dep on
  health_emr/health_ai_coding/health_zalo.
- **Tests:** `tests/test_fhir_core.py` / `test_fhir_phase2.py` /
  `test_fhir_consent.py`; each resource validated via `_validate(resource)` →
  `fhir.resources` (pydantic R4B) round-trip; consent tests toggle
  `consent_enforced`.

---

## 2. Architecture

health_fhir_core (bump the minor version). No new module, no new depends.

### 2.1 Compartment gather helper (a function in health_fhir_core — NO base hook)

A small helper (module function or a `@staticmethod`, e.g. in a new
`serializers/everything.py` or on the controller) that reuses the EXISTING
convention — no per-serializer edit:
```python
def patient_compartment(env, patient_id):
    """Yield (serializer, domain) for every REGISTRY resource in the patient's
    compartment, reusing each serializer's own patient search-param domain
    callable (the convention fhir.adapter.vn.build_patient_bundle relies on)."""
    ref = 'Patient/%d' % patient_id
    for rtype in sorted(REGISTRY):
        s = REGISTRY[rtype]
        spec = s.search_params.get('patient') or s.search_params.get('subject')
        if not spec:
            continue                      # non-PHI / template → not in compartment
        yield s, spec['domain'](ref)
```
The caller composes `s.base_domain(env) + domain + since` and searches under the
user env. Patient itself is included (its `patient` param maps `Patient/<id>` →
`[('id','=',pid)]`). **Sanity rail (test §4.3):** every serializer with a
non-empty `patient_ids_of` MUST expose a `patient`/`subject` search param — else
its PHI would be silently missing from `$everything`. Assert this over REGISTRY
so a future serializer that forgets the param is caught.

### 2.2 The operation route (controllers/fhir.py)

```
GET /fhir/r4/Patient/<int:rid>/$everything
```
- `type='http', auth='none', methods=['GET'], csrf=False`. In Odoo a `$` in a
  path works as a literal; register the route as
  `'/fhir/r4/Patient/<int:rid>/$everything'` (verify the werkzeug rule accepts
  `$`; if not, use `<string:op>` and dispatch on `op=='$everything'`).
- Auth: `_authenticate(REGISTRY['Patient'])` (needs `system/Patient.read` or
  `system/*.read` — a whole-record read is a Patient-scope read). Run under
  `request.env(user=user.id)` (record rules apply — a caller who can't see the
  patient gets nothing).
- Resolve the patient via `REGISTRY['Patient'].read_record(env, rid)`; if none
  (or record-rule-hidden) → `FHIRNotFound` (no existence reveal).
- **ONE consent decision for the whole record:** compute
  `enforced = consent_enforced(env)`; if enforced and NOT
  `check_consent(rid, 'data_sharing')` → return an EMPTY searchset Bundle (or
  `FHIRNotFound` — pick FHIRNotFound to avoid confirming the record exists
  without consent; match the per-resource read's 404-on-deny behavior). Always
  write the consent-check log (ctx `consent_check_source='fhir_everything'`) —
  the release audit trail. In log-only mode, proceed (nothing withheld) but the
  log still records the release.
- **Gather:** iterate `REGISTRY` (deterministic order — Patient first, then
  sorted); for each serializer, `dom = s.compartment_domain(env, patient.id)`;
  skip if `None`; `recs = env[s.odoo_model].search(base_domain + dom + since +
  order id, limit=…)`. Apply `_type` filter (only the requested resource
  types). Serialize via `s.serialize_batch(recs)`. (Records already run under
  the user env → record-rule-scoped; the single consent decision above already
  gated the patient, so per-record consent re-check is redundant but harmless —
  do NOT double-log; gate once.)
- **Bundle:** `resourceType:'Bundle', type:'searchset', total:<count>,
  entry:[{fullUrl, resource, search:{mode: 'match' for the patient/'include'
  for the rest}}]`, Patient entry first. `_since` = `_lastUpdated`-style
  `write_date >=`. `_count`/cursor: bound the TOTAL entries (default cap, e.g.
  200; if exceeded, add a `next` link — a simple approach: a global cursor over
  a stable (resource_type, id) ordering, or cap + document the cap in the
  bundle via an OperationOutcome `information` entry. Keep v1 simple: a hard cap
  with a logged/oo-noted truncation is acceptable if you DECLARE it — never
  silently truncate a medical record).
- Audit: one `api.audit.log` row (action `Patient/$everything`, patient id,
  entry count) mirroring fhir.py:141.

### 2.3 CapabilityStatement (capability.py)

Add to the Patient resource entry an `operation`:
```python
'operation': [{'name': 'everything',
               'definition': 'http://hl7.org/fhir/OperationDefinition/Patient-everything'}]
```
(Only on Patient; leave other resources unchanged.)

### 2.4 Sanctioned edits (exhaustive)

| Module | File | What may change |
|---|---|---|
| health_fhir_core | controllers/fhir.py (the `$everything` route + the gather/bundle logic), serializers/everything.py OR a helper (the `patient_compartment` gather §2.1), capability.py (Patient operation), tests/ (new test_fhir_everything.py), __manifest__.py (version). serializers/base.py ONLY if a shared `serialize`/bundle helper is cleaner — NO per-resource serializer edits (the `patient` search-param convention already exists on each). | as listed |

NO new module. NO per-resource serializer edits. NO clinical/accounting model
change. NO edit to health_api_gateway (reuse `_gateway_authenticate`) or
health_fhir_adapter_vn (the VN outbound analog stays untouched). NO PWA.

---

## 3. Safety rails (binding)

- **At least as strict as the per-resource facade.** Runs under the caller's
  env (record rules) AND the consent gate. A whole-record export is the highest
  PHI-leak blast radius in the system — the consent decision is mandatory and
  logged; deny → no record (FHIRNotFound, no existence reveal). Never widen
  beyond the patient's own compartment.
- **Read-only.** No writes to any clinical/consent/accounting model except the
  append-only `health.consent.check.log` (via the existing gate) + the
  `api.audit.log` export row. NO pip.
- **No silent truncation of a medical record.** If pagination/caps drop
  resources, DECLARE it (a `next` link or an OperationOutcome `information`
  entry in the bundle) — a consumer must never believe a truncated record is
  complete.
- **Optional-dep guards** (`'field' in _fields`) preserved — health_fhir_core
  keeps no hard dep on health_emr/ai_coding/zalo.
- **Every emitted resource validates** against fhir.resources (test rail).
- QA fixtures cleaned + fresh-cursor verified (§5.34); do QA cleanup
  before/after the deploy, never during (§5.45).

## 4. Tests (tests/test_fhir_everything.py; ~10, TransactionCase +/or HttpCase)

Seed one patient with a spread: an FSO (Encounter), 2 observations, a finalized
clinical note (DocumentReference), a careplan — plus a SECOND patient in another
catchment to prove isolation.

1. `$everything` returns a `searchset` Bundle with the Patient resource FIRST +
   the patient's Encounter/Observation/DocumentReference entries; `total`
   matches; every entry validates via fhir.resources.
2. Compartment correctness: the bundle contains ONLY this patient's records —
   the second patient's resources are absent.
3. Compartment coverage: every REGISTRY serializer with non-empty
   `patient_ids_of` exposes a `patient` (or `subject`) search param (guards a
   future serializer whose PHI would silently miss `$everything`).
4. Non-PHI excluded: Organization/Practitioner/Questionnaire do NOT appear.
5. Consent enforced (`consent_enforced=True`): patient WITHOUT `data_sharing`
   consent → `$everything` denies (FHIRNotFound / empty) AND a
   `health.consent.check.log` row (source `fhir_everything`) is written; WITH
   consent → full bundle. Log-only mode → full bundle + log row.
6. Record-rule isolation: a user who can't see the patient (cross-catchment)
   → FHIRNotFound (no existence reveal).
7. `_type=Observation,Encounter` → only those types in the bundle.
8. `_since=<datetime>` → only resources with `write_date >=` it.
9. `_count`/cap: seed > cap resources → the bundle DECLARES truncation (next
   link or OO information entry), never silently drops.
10. CapabilityStatement: `/fhir/r4/metadata` lists the `everything` operation on
    Patient.

## 5. Deploy / verify (conventions §2)

- `-u health_fhir_core --test-enable --test-tags /health_fhir_core
  --stop-after-init [--no-http unless you add HttpCase] --workers 0`. Confirm by
  the `odoo.tests.result` line + EXIT:0 (§5.45), restart, `/web/login` 200,
  and `GET /fhir/r4/metadata` 200 showing the operation.
- **Evidence pack (§8.1)** to `docs/strategy/reports/fhir-everything-evidence/`:
  a real `curl` (with a valid `system/*.read` token — reuse the gateway token
  flow) of `GET /fhir/r4/Patient/<qa_id>/$everything` showing the Bundle
  (Patient + Encounter + Observation + DocumentReference), the metadata
  operation, and a consent-enforced DENY on an unconsented QA patient. Redact
  PHI in the committed sample (use the QA fixture patient, then delete it +
  fresh-cursor verify §5.34). No real-patient record in the evidence.

## 6. Report back

Standard §8 (report → `docs/strategy/reports/fhir-everything-report.md`), plus:
(a) the evidence pack (bundle + metadata + consent-deny); (b) the exact list of
resource types that appeared in a real QA patient's `$everything` (proves the
compartment composition); (c) confirmation the consent gate fired ONCE and
logged (source `fhir_everything`), and that a cross-catchment caller got
FHIRNotFound; (d) how truncation is declared if the cap is hit; (e) QA cleanup
fresh-cursor confirmation; (f) any new gotcha (esp. whether werkzeug accepted
the literal `$` in the route or you dispatched on a `<string:op>`).

Kickoff line: `Implement the phase specified in docs/strategy/handovers/fhir-everything-export.md.`
