# Phase GC-2 — spec-grade search + consent enforcement + terminology tooling

**Implementer:** Opus 5 · **Date:** 2026-08-02 · **Branch:** 19.0
**Handover:** `docs/strategy/handovers/hl7-gap-closure.md` §3
**Register items:** G17 (closed), G5 (engineering closed, gate now enforced),
G8 (engineering half closed)

**Result: 0 failed, 0 error(s) of 118 tests on vietuat, with the consent gate
ENFORCED.** Server healthy (HTTP 200). The live facade declares the new
string-modifier documentation and refuses to serve un-consented patients —
verified with a real gateway token, not a unit test.

---

## 1. Headline: enforcing the gate found eight tests that were not what they
## claimed to be

The handover (§3.5 step 2) said the consent and `$everything` suites "set the
param themselves in-test; green in both modes". **They were not.** After the
flip, `health_fhir_core` went from 0 errors to **8**:

```
2026-08-02 12:24:28 ERROR odoo.tests.result: 0 failed, 8 error(s) of 89 tests
  TestFHIRConformanceGC1.test_15_everything_contains_flag_and_declares_nothing_suppressed
  TestFhirEverything.test_01_bundle_shape_and_validates
  TestFhirEverything.test_02_isolation_other_patient_absent
  TestFhirEverything.test_04_non_phi_excluded
  TestFhirEverything.test_07_type_filter
  TestFhirEverything.test_08_since_filter
  TestFhirEverything.test_09_truncation_declared
  TestFhirEverything.test_11_unauthorized_model_declared
```

All eight raised `FHIRNotFound: No Patient resource with id 16077` — the
engine correctly denying a fixture patient with no `data_sharing` consent.
Only three tests (`test_05a/b/c`) passed `enforced=` explicitly; the rest
inherited it from `consent_enforced(env)`, i.e. **from the deployment's live
configuration**. Their meaning changed when ops changed a parameter.

Fixed in the tests, never the engine (conventions §5.62): every test that is
*not* about consent now pins `enforced=False`, so it proves what its name
says regardless of how the server is configured. `test_06_record_rule_isolation`
was pinned too — it asserts `FHIRNotFound` for a cross-catchment nurse, and
under enforcement it would have passed **for the wrong reason**. A new
`test_05d_default_follows_the_config_parameter` covers the default-resolution
branch that the pinning would otherwise have left untested.

This is the single most valuable thing the phase produced, and it only exists
because §3.5 asked for the suites to be re-run *after* the flip rather than
trusting the claim.

---

## 2. What was built

### B2a — FHIR token syntax (§3.1)

`serializers/base.py`: `token_domain(field, system_uri=None)` copied verbatim
from the handover kernel, plus `token_status_domain(translate, system_uri)`
— status params reverse a map into `('state','in',[…])` and cannot use the
kernel directly, so the wrapper *runs the kernel* over a throwaway field name
and hands the parsed code on. One implementation of the token grammar, not
two.

Applied to: Observation `code` (LOINC asserted) · Condition `code` (ICD-10
asserted) · Condition `clinical-status` · CodeSystem `url` / `name` ·
AdverseEvent `severity` · Questionnaire `name` · and every status param
(Encounter, Appointment, ServiceRequest via `fso_common.status_token_domain`;
CarePlan, Goal, Task via `careplan._reverse_token_domain`; MedicationRequest,
MedicationAdministration via `medication._reverse_status_domain`;
Questionnaire, QuestionnaireResponse, Consent, Observation at their
declaration sites). Patient `identifier` left as-is (F11 — already tolerant
and richer).

`code=http://hl7.org/fhir/sid/icd-10|I10` now matches; a *foreign* system
yields **zero rows via an impossible domain, not a 400** — the spec's answer
(R4 §3.1.1.6.3), and the cheap one.

### B2b — string modifiers + the spec default (§3.2)

`build_domain` splits the param name on `:`. `string`-typed params accept
`:exact` and `:contains`; **anything else — an unknown modifier, a modifier
on a token/date/reference param, `_count:exact` — is a strict 400
`FHIRNotSupported`.**

`string_param_domain(field)` implements R4 string semantics:

| form | domain | meaning |
|---|---|---|
| `name=Ng` | `('name','=ilike','Ng%')` | case-insensitive **starts-with** (default) |
| `name:contains=Văn` | `('name','ilike','Văn')` | anywhere |
| `name:exact=Nguyễn Văn A` | `('name','=','Nguyễn Văn A')` | exact, case-sensitive |

`escape_like()` escapes `%`, `_` and `\` in the caller's value, so a `%` a
client sends is *data*, not a wildcard (previously `name=A%` was a full scan
dressed as a search).

Four string params exist and all four were converted: Patient,
Organization, Practitioner, Location `name`.

### B2c — binding membership (§3.3)

New `tests/test_fhir_bindings.py`: **14 required-binding tables** (the
handover's 13 plus `Questionnaire.status`), asserted by importing the
serializers' actual mapping dicts — never retyped values. Where a reverse
search map exists it is asserted too (emitted status and searchable status are
different dicts and can drift apart). `Flag.status` has no dict, so both
branches are exercised on a real fixture. `Condition.clinicalStatus` reads the
model's Selection, guarded on `'health.condition' in self.env`.

**No violations were found** — every mapping already emitted legal R4 codes.
`test_66` is the drift guard: any future resource exposing a status search
param without a table here fails the suite.

### B2d — the signable mapping table (§3.4)

`docs/conformance/clinical-status-mappings.md` — 14 tables (Odoo state → FHIR
code + rationale), the defaults, the many-to-one collapses, **five explicit
open questions for the clinical lead**, and a signature block. Values match
the code because the B2c tests compare against the same dicts.

### D3 — the consent gate is enforced (§3.5)

Parameter written directly to the database (`noupdate="1"` seed — an XML edit
would not apply, F8) and a **full stop/start** (§5.48 per-worker ormcache).
Runbook: `docs/conformance/consent-enforcement-runbook.md`.

### D4 — terminology load tooling (§3.6)

- `tools/icd10_claml_to_csv.py` — WHO ClaML → importer CSV; stdlib only;
  `--chapter` filter; flattens nested `<Label>` markup; counts and reports
  unhandled elements; `iterparse` + `clear()` so a 50 MB release does not need
  a gigabyte of RAM. **Never touches the network** — a licence is accepted by
  a person.
- `tools/icd10_vi_merge.py` — merges the MOH-KCB translation into
  `display_vi`; auto-detects Vietnamese/English header spellings; matches
  codes case- and dot-insensitively; **unmatched translations are written to a
  sidecar file, never dropped**; untranslated rows counted.
- `addons/health_fhir_terminology/tests/fixtures/icd10_sample_50.csv` — 50
  synthetic rows (`ZZ*`, no WHO content): children before parents, diacritics,
  one malformed row.
- `docs/conformance/icd10-load-runbook.md` — licence, acquisition, conversion,
  wizard steps, expected counters, verification queries, density ownership.

Both scripts were run end-to-end locally against a synthetic ClaML file (§5.3
below) — they are verified working, not merely committed.

---

## 3. Test results (verbatim)

```
# GC-2 code, gate still log-only — 12:19:37
0 failed, 0 error(s) of 117 tests when loading database 'vietuat'   EXIT:0  HTTP:200

# gate ENFORCED, health_fhir_core alone — 12:24:28  ← the finding, §1
0 failed, 8 error(s) of 89 tests when loading database 'vietuat'    EXIT:1  HTTP:200

# gate ENFORCED, after the test fix — 12:27:17  ← the phase result
0 failed, 0 error(s) of 118 tests when loading database 'vietuat'   EXIT:0  HTTP:200
```

Executed-test count for the final run: **118** (`grep -ac "Starting Test.*\.test_"`),
`grep -ac "FAIL:\|ERROR:"` = **0**. All 36 new/changed tests confirmed
executed by name (§5.83/§5.90 — a count of failures is not evidence):

```
TestFHIRSearchGC2.test_31…test_43            (13)  token syntax + string modifiers
TestFHIRBindings.test_51…test_66             (16)  binding membership + drift guard
TestIcd10SampleLoad.test_70…test_73           (4)  ICD-10 load path + idempotence
TestCondition.test_12b_token_system_code_search (1)
TestFhirEverything.test_05d_default_follows_the_config_parameter (1)
TestFHIRConformanceGC1.test_22_capability_matches_the_committed_baseline (regenerated)
```

No test was skipped (`grep -ai skip` shows only unrelated framework noise) —
including `test_62`, the `health.condition`-guarded binding table.

Live capability after deploy:

```
fhirVersion:        4.0.1
software:           {'name': 'health19 / CarejioX', 'version': '19.0.1.4.0'}
rest.documentation: Read-only. Supported string modifiers: :exact, :contains.
resources:          22
```

---

## 4. Consent-enforcement live probe (§3.5 step 3)

Fixtures created in an `odoo-bin shell` (create → `flush_all()` → `commit()`),
then **confirmed from a separate psql connection** before use (§5.34):

```
PROBE_A=16059 (GC2PROBE Consented, active data_sharing consent id 1503)
PROBE_B=16060 (GC2PROBE Unconsented)
CLIENT=170 (QA OAuth client) TOKEN=hg_7acd…62f06a9 scope system/Patient.read
```

With `consent_enforced=True` and a real Bearer token:

```
GET /fhir/r4/Patient?name=GC2PROBE
  → 200, {"total": 1, entry: [Patient/16059]}
    the un-consented 16060 is absent from BOTH `entry` and `total`

GET /fhir/r4/Patient/16060   → 404 {"resourceType":"OperationOutcome",
    "issue":[{"severity":"error","code":"not-found",
              "diagnostics":"No Patient resource with id 16060"}]}
GET /fhir/r4/Patient/16059   → 200
GET /fhir/r4/Patient/99999999 → 404, identical shape — a denial is
    indistinguishable from "no such record", so the facade never confirms
    that a person is a patient here.
```

`health_consent_check_log`, source `fhir_facade` — one row per patient per
request, allowed **and denied**:

```
5202 | 16059 | data_sharing | t | fhir_facade | 12:22:42   (search)
5203 | 16060 | data_sharing | f | fhir_facade | 12:22:42   (search)
5204 | 16060 | data_sharing | f | fhir_facade | 12:22:54   (read → 404)
5205 | 16059 | data_sharing | t | fhir_facade | 12:22:55   (read → 200)
```

**Fixture cleanup + fresh-cursor verification** (psql, new connection):

```
res_partner 16060   → row absent (hard-deleted)
res_partner 16059   → active = f   (archived: FK-restricted by its consent)
health_consent 1503 → active = f   (granted consents are un-deletable audit)
gateway_oauth_client 170 → 0 rows ; gateway_token 279 → 0 rows
```

Note in passing: deleting 16060 also removed its two check-log rows (5203,
5204) — see the findings below.

---

## 5. Deviations from the handover, with reasoning

**D1 — `token_status_domain` added next to the verbatim kernel.** The kernel
`token_domain` maps one value onto one field with `=`; the status params
reverse a table into `('state','in',[…])` and cannot use it. The handover said
"route them through the same helper", so the wrapper *invokes the kernel* for
the grammar and uses only its parsed output. The kernel itself is byte-identical
to the handover block.

**D2 — the capability `documentation` line sits at `rest[0].documentation`,
not on each resource.** §2.3 step 2 does not state the element. R4 defines
`rest.documentation` as "capabilities that apply across all applications",
which is exactly what "Read-only. Supported string modifiers: :exact,
:contains." is; repeating it on 22 resource entries (16 of which have no
string param) would be noise. Live output quoted in §3.

**D3 — Questionnaire `name` is a token, not a string param.** §3.2 lists it
among "the three string params (Patient/Organization/Practitioner/Location/
Questionnaire `name`)" — five names for three params. In the code,
Questionnaire `name` is `{'type': 'token'}` matching the template's stable
`code` exactly. Changing its type would change the CapabilityStatement beyond
the one sanctioned key, so it stays a token and gained token-syntax tolerance
instead. The four genuine string params were all converted.

**D4 — `health_condition` was edited, though §3 does not list it as a
sanctioned module.** §3.1 explicitly requires Condition `code`
(`code_id.code`, ICD-10). Forced: the named work cannot be done inside the
sanctioned modules. Two files: `serializers/condition.py` (search_params only)
and `tests/test_condition.py` (a token test + the `enforced=False` pin).
health_condition was added to the upgrade list for the same reason.

**D5 — T2.2's worked vector was internally inconsistent; the fixtures were
changed, not the semantics.** The handover says to create "Nguyễn Văn A" +
"Văn B" and expect `name=Văn` to match *neither* — but "Văn B" **starts with**
"Văn", so under the starts-with default it must match. Fixtures are now
`Nguyễn Văn Alpha GC2` and `Trần Văn Bravo GC2`, for which every stated
expectation holds exactly. Added `Percent%Escape GC2` / `PercentXEscape GC2`
to prove the wildcard escaping.

**D6 — the sample fixture lives in the module, not `tools/fixtures/`.** Only
`addons/<module>/` is deployed to the server, so a test reading
`tools/fixtures/…` could never run on vietuat — it would silently skip or
error, which §5.83 rejects. Canonical path is
`addons/health_fhir_terminology/tests/fixtures/icd10_sample_50.csv`; the
runbook and both tools reference it there. One copy, and the test genuinely
runs.

**D7 — eight pre-existing tests were changed** (7 in `test_fhir_everything`,
1 in `test_fhir_conformance`, 1 in `test_condition`). Cause and reasoning in
§1. No engine change.

**D8 — AdverseEvent `severity` also routed through `token_domain`.** Not
enumerated in §3.1, but it is a token param, and leaving one token param that
rejects token syntax *is* the G17 defect. Strictly more permissive; no
behaviour lost.

**D9 — additions beyond the numbered tests:** `Questionnaire.status` and
`CarePlan.activity.detail.status` binding tables; the reverse (searchable)
direction of every status map; `test_66` completeness guard;
`test_05d_default_follows_the_config_parameter`; `test_73` (update-in-place,
the other half of idempotence). Additions, never substitutions — every
numbered test T2.1–T2.7 is present.

No other deviations. In particular: the facade is still **read-only**, no new
resource serializer, no `sudo` added anywhere, `health_fhir_adapter_vn`/`_base`
untouched, no `meta.profile`, nothing pip-installed, no test relaxed to pass,
and the only HTML edits are three §10.5 status cells plus one appended §10.10
row.

---

## 6. Findings for the reviewer (not fixed — out of GC-2 scope)

**F1 — FHIR audit rows do not name the API client.** `api_audit_log.key_or_client`
is empty for every `/fhir/r4/*` row. `fhir.py:_audit` passes
`client=getattr(request, 'api_client', None)`, but `_gateway_authenticate`
stores the client on `request.gateway_auth['key_ref']` — the attribute the
controller reads is never set. Every facade read is therefore attributable to
a *user* but not to the *partner integration that made it*, which is the
attribution a breach investigation needs. One line to fix, but it changes
audit semantics, so it belongs to a phase that decides it — GC-3's C3/C5 work
is the natural home.

**F2 — deleting a patient destroys their consent-check evidence.**
`health.consent.check.log.client_id` is `ondelete='cascade'`, so PostgreSQL
removes the rows and the model's append-only `unlink` guard never runs
(ledger §5.30, on the one model where the guarantee matters most). Observed
live in this phase's cleanup: rows 5203/5204 vanished with patient 16060.
Correct for a synthetic QA fixture; wrong as a general property. The runbook
now tells ops to archive patients, never delete them — but that is a
convention, not an enforcement.

---

## 7. Deferred / not in this phase

- **G5 operational half:** capturing real `data_sharing` consents. The gate is
  live and deny-by-default; **with no consents recorded the facade correctly
  serves zero PHI**, and that is the safe direction. §10.11 item.
- **G8 operational half:** WHO licence acceptance, file acquisition, the load,
  and coding density ≥80%. Tooling and runbook are done; nobody but the client
  can accept a licence. G8 therefore reads *In progress*, not Closed.
- **G17 signature:** the mapping table is written and its five open questions
  are explicit; the clinical lead signs. §10.11 item.
- Everything in GC-3 / GC-4.

---

## 8. New gotchas (candidates for conventions §5)

**§5.98 — flipping a deployment config parameter is a default-narrowing
change of the §5.62 class, and the tests it breaks are not the tests about
that feature.** Enforcing `health_fhir_core.consent_enforced` red-lit eight
tests, none of which mentions consent: they test bundle shape, compartment
isolation, `_type`/`_since` filters, truncation and an ACL-suppression path.
They broke because the engine resolves the mode from `ir.config_parameter`
when the caller does not pass one, so *the deployment's configuration was an
implicit test fixture*. Two rules: (a) when a phase flips a parameter, re-run
**every** suite that can reach the code path, not the ones named after the
feature — and treat a handover's claim that "the suites are green in both
modes" as a hypothesis to test, not a fact; (b) a test that lets behaviour
resolve from live configuration is non-deterministic across databases — pin
the mode explicitly and leave exactly one test asserting that the default
reads the parameter. Sharpest edge: `test_06_record_rule_isolation` continued
to PASS under enforcement — for the wrong reason (it asserts `FHIRNotFound`,
which enforcement also raises). A green test can be destroyed by a config
change without ever going red.

**§5.99 — an `ondelete='cascade'` FK into an append-only *audit* model
deletes the evidence and never runs the guard.** The §5.30 mechanism, applied
to compliance logs: `health.consent.check.log` blocks `write`/`unlink` in
Python and is described in its own docstring as evidence, yet deleting the
patient removes the rows at the SQL layer. Any model whose purpose is "prove
what we did with this person's data" needs `ondelete='restrict'` (or
`set null`) on its subject FK, or the retention guarantee is only as strong as
the convention that nobody deletes a patient.

---

## 9. Files

**Changed — `health_fhir_core`:** `serializers/base.py` (token_domain kernel,
token_status_domain, STRING_MODIFIERS, escape_like, string_param_domain,
build_domain modifier parsing) · `serializers/{patient,organization,
practitioner,location}.py` (string params) · `serializers/{observation,
fso_common,careplan,medication,questionnaire,consent,adverse_event}.py` (token
syntax) · `capability.py` (+`rest.documentation`) ·
`conformance/capability_baseline.json` (regenerated) · `tests/__init__.py` ·
`tests/test_fhir_core.py` (2 name searches → `:contains`/prefix) ·
`tests/test_fhir_everything.py` (`enforced=` pins + test_05d) ·
`tests/test_fhir_conformance.py` (`enforced=` pin)

**New — `health_fhir_core`:** `tests/test_fhir_search_gc2.py` ·
`tests/test_fhir_bindings.py`

**Changed — `health_fhir_terminology`:** `serializers/code_system.py` ·
`tests/test_terminology.py` (+`TestIcd10SampleLoad`)
**New:** `tests/fixtures/icd10_sample_50.csv`

**Changed — `health_condition`:** `serializers/condition.py` ·
`tests/test_condition.py`

**New — repo:** `tools/icd10_claml_to_csv.py` · `tools/icd10_vi_merge.py` ·
`docs/conformance/clinical-status-mappings.md` ·
`docs/conformance/consent-enforcement-runbook.md` ·
`docs/conformance/icd10-load-runbook.md` ·
`docs/strategy/reports/gc-2-report.md`

**Tracker:** `docs/strategy/hl7-fhir-compliance-response.html` — §10.5 cells
for G17/G5/G8, one appended §10.10 row.

No PWA asset changed (no version bump needed). No user-visible string changed
— the facade is machine-facing and the new documents are English-language
operational artefacts — so no `vi.po` work and no browser evidence pack
applies to this phase.
