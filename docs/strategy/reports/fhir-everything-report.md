# Patient `$everything` — whole-record clinical export — implementation report

**Module:** `health_fhir_core` 19.0.1.2.0 → **19.0.1.3.0**
**Branch:** 19.0 · **Server:** vietuat · **Date:** 2026-07-18
**Handover:** `docs/strategy/handovers/fhir-everything-export.md`
**Tests:** `health_fhir_core: 54 tests … 0 failed, 0 error(s) of 46 tests` · EXIT:0 · `/web/login` HTTP 200

---

## 1. What was built

A new FHIR `Patient/$everything` operation that returns a patient's **whole
clinical record** in one interoperable, single-consent `searchset` Bundle — the
Circular-13 EMR-handoff / referral use case. It COMPOSES the 18+ existing
per-resource serializers; **no new resource serializers, no new clinical
models, no adapter edit** (country-neutral, lives in health_fhir_core only).

Files (all §2.4-sanctioned):

| File | Change |
|---|---|
| `serializers/everything.py` | **NEW.** `patient_compartment(env, pid)` gather (reuses each serializer's own `search_params['patient']`/`['subject']` domain — the convention `build_patient_bundle` relies on, no per-serializer hook) + `build_everything_bundle(env, pid, params, base_url, enforced)` (consent-gated, `_type`/`_since`/`_count` support, declared truncation & declared authorization-omission). |
| `controllers/fhir.py` | **NEW route** `GET /fhir/r4/Patient/<int:rid>/$everything` — thin wrapper: gateway auth (`system/Patient.read` or `system/*.read`), runs under the caller's env (record rules), one audit row, delegates to `build_everything_bundle`. |
| `capability.py` | Patient resource entry now declares `operation: [{name: everything, definition: …/Patient-everything}]` (only on Patient). |
| `tests/test_fhir_everything.py` | **NEW.** 12 tests (11 numbered cases + coverage invariant). |
| `tests/__init__.py` | register the new suite. |
| `__manifest__.py` | version bump. |

## 2. How the compartment is composed

The patient compartment = **every REGISTRY serializer that exposes a `patient`
(or `subject`) search param**, EXCEPT `Patient` itself (the compartment ROOT,
added explicitly — it has no `patient` param, it *is* the patient). Non-PHI
reference/terminology resources (Organization, Location, Practitioner,
Questionnaire template, **CodeSystem**) have no such param and are excluded
automatically — matching their empty `patient_ids_of`. A real QA patient's
`$everything` returned:

```
Patient (match) · Appointment · CarePlan · Consent · DocumentReference ·
Encounter · Observation ×2 · ServiceRequest        (+ declared Flag omission)
```

`Bundle.total` counts real matches; Patient is entry 0 with `search.mode:match`,
the rest `include`.

## 3. Safety rails (all honoured)

- **One whole-record consent decision, always logged.** `data_sharing` consent
  is checked ONCE per release with `consent_check_source='fhir_everything'`
  (writes `health.consent.check.log`). Under enforcement (`consent_enforced`),
  no consent → **`FHIRNotFound` (404), no existence reveal** — matches the
  per-resource read's deny shape. Log-only mode → full bundle, still audited.
  Live proof: 4 log rows across the consented (result True) and unconsented
  (result False) QA patients.
- **At least as strict as the per-resource facade.** Runs under
  `request.env(user=user.id)` so catchment record rules apply; a cross-catchment
  caller gets `FHIRNotFound` (unit test_06). Never widens beyond the patient's
  own compartment; no `_include`/`_revinclude`.
- **Read-only.** No writes except the append-only consent-check log (via the
  existing gate) + one `api.audit.log` export row. No pip.
- **No silent truncation of a medical record.** A `_count` cap hit appends an
  `OperationOutcome` (`severity:information`, `code:incomplete`) declaring
  `<returned> of <total>`. See §5 for the authorization-omission counterpart.
- Optional-dep guards untouched; every emitted resource validates against
  `fhir.resources` (test rail).

## 4. Test results (verbatim)

```
odoo.tests.stats:  health_fhir_core: 54 tests 3.86s 2242 queries
odoo.tests.result: 0 failed, 0 error(s) of 46 tests when loading database 'vietuat'
EXIT:0 · /web/login HTTP:200
```
The new suite (`test_fhir_everything.py`) covers: bundle shape+validation (1),
compartment isolation vs a second-catchment patient (2), compartment-coverage
invariant (3), non-PHI exclusion (4), consent deny+log / allow / log-only
(5a-5c), record-rule isolation (6), `_type` filter (7), `_since` filter (8),
truncation declaration (9), CapabilityStatement operation (10), and the
authorization-omission declaration (11). The earlier three suites
(test_fhir_core / _phase2 / _consent) still pass.

## 5. Deviations from the handover design (with reasoning)

1. **Patient is special-cased in the gather, not driven by a `patient` search
   param.** The handover §2.1 asserted "Patient itself is included (its
   `patient` param maps `Patient/<id>` → `[('id','=',pid)]`)" — but the live
   Patient serializer has **no `patient` search param** (its params are
   identifier/name/telecom/phone/birthdate). So `patient_compartment` SKIPS
   Patient and the bundle builder adds it explicitly via `read_record` +
   `[('id','=',pid)]`. The compartment-coverage test (3) likewise excludes
   Patient from the "must-have-a-patient-param" set. Net behavior is exactly as
   intended (Patient first, `search.mode:match`).

2. **NEW: declared authorization-omission (`OperationOutcome` `code:suppressed`,
   `severity:warning`).** Discovered live: `health.fall.risk` (the FHIR **Flag**
   model) ships with **no `ir.model.access` row for any group**, so no token
   user can read it — and because `$everything` touches every compartment model
   at once, a single unreadable model 403'd the ENTIRE whole-record export
   (even though the patient had zero Flag rows). The plain `GET /fhir/r4/Flag`
   would 403 identically — it is a pre-existing facade/ACL gap, not new. Rather
   than make `$everything` all-or-nothing fragile, an unreadable compartment
   model is now **skipped and DECLARED** in an OperationOutcome (the
   authorization counterpart of "no silent truncation"): no data leaks, the
   consumer is told the record may be incomplete for its authorization. This is
   within the sanctioned `everything.py` and is strictly safer than the
   alternative. Only the compartment `search_count` is wrapped
   (`except AccessError`); the Patient root is not (a caller who cannot read the
   patient is a real deny).

## 6. Evidence pack

`docs/strategy/reports/fhir-everything-evidence/` (QA fixture patient, deleted /
archived after capture — no real PHI):
- `ev_metadata.json` — CapabilityStatement with the Patient `everything` operation.
- `ev_everything.json` — HTTP 200 `searchset`, `total:9`, Patient-first, Flag
  omission declared (log-only).
- `ev_deny.json` — consent **enforced**, unconsented patient → **HTTP 404**
  `OperationOutcome not-found` (no existence reveal).
- `ev_allow.json` — consent enforced, consented patient → HTTP 200 full bundle.
- `README.md` — the exact token flow, request lines, and what each proves.

Report-back items (handover §6):
- **(a)** evidence pack ✓ (bundle + metadata + consent-deny + consent-allow).
- **(b)** resource types in a real QA `$everything`: Patient, Appointment,
  CarePlan, Consent, DocumentReference, Encounter, Observation, ServiceRequest.
- **(c)** consent gate fired ONCE and logged (source `fhir_everything`, 4 rows,
  result True/False) ✓; cross-catchment caller → `FHIRNotFound` (test_06) ✓.
- **(d)** truncation declared via an `OperationOutcome information/incomplete`
  entry (`_count` cap); authorization-omission via `warning/suppressed`.
- **(e)** QA cleanup fresh-cursor verified: FSO/observations/note/careplan = 0,
  facility/province/employee/service-user/oauth-client deleted. The two QA
  patients were **archived** (not hard-deleted) because their granted
  `data_sharing` consent (active = permanent audit record) and append-only
  `health.consent.check.log` rows FK-restrict deletion **by design** — the
  system intentionally makes those compliance artifacts permanent.
- **(f)** new gotcha: werkzeug **accepted the literal `$`** in the route
  (`/fhir/r4/Patient/<int:rid>/$everything`) — no `<string:op>` fallback needed
  (the 200/404/403 responses all reached the handler). Plus the ormcache /
  Patient-serializer notes in §7.

## 7. New gotchas (for conventions §5)

- **§5.47 (proposed) — `$everything` / any multi-model export is fragile to a
  single model with a missing/failing `ir.model.access`.** `health.fall.risk`
  (FHIR Flag) has NO ACL row for any group; a per-resource read 403s and a
  whole-record pull that touches it 403s the ENTIRE export — even when the
  patient has zero such rows (model ACL is checked before row count). Fix
  pattern: wrap each compartment model's `search_count` in `except AccessError`,
  OMIT the type, and DECLARE it (never silent, never leak). Corollary: the FHIR
  Patient serializer's `serialize_batch` bulk-`fetch`es EVERY stored
  `res.partner` field, including group-gated `credit_limit`/`signup_type`, so a
  non-accounting/non-admin token 403s on **any** Patient serialization (plain
  read included) — a pre-existing facade quirk, out of scope for a per-resource
  serializer non-goal, flagged for the facade owners.
- **§5.48 (proposed) — a `config_parameter` toggle set from a separate
  `odoo-bin shell` is NOT seen by the running HTTP workers until a restart.**
  `consent_enforced` flipped to True via shell did not deny on the live workers
  (each worker's `ir.config_parameter` ormcache still held False); a
  `service odoo-server restart` made the enforced deny fire. For live evidence
  that depends on a config flag, restart after setting it (or set via the
  Settings UI which invalidates in-process). (Companion to §5.32's ORMCACHE
  note.)

## 8. Non-goals respected

No new serializers/models; no writes to clinical/accounting data; no edit to
`health_api_gateway` or `health_fhir_adapter_vn`; no `_include`/`_revinclude`;
no outbound/VSS/BHYT; no PWA; no pip; no messaging. No user-facing strings → no
`vi.po` change.
