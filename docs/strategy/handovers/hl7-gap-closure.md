# HL7/FHIR Gap-Closure — phases GC-1 … GC-4 (Opus implementation handover)

**Design:** Fable, 2026-08-02. **Status doc (live tracker):**
`docs/strategy/hl7-fhir-compliance-response.html` — §9 gap register, §10.5
closure matrix (the version of record), §10.10 status log, §10.11 residual
operational register. **This handover exists to drive every engineering-closable
gap in that register to Closed and leave §10.11 as the only open list.**

Read `docs/strategy/HANDOVER-CONVENTIONS.md` FIRST (deploy workflow §2, gotcha
ledger §5, fixtures §6, definition of done §8). Ledger entries load-bearing for
this work: **§5.47** (compartment ACL fragility + the Patient-prefetch corollary
— GC-1 fixes both), **§5.48** (config-param ormcache is per-worker → restart
after any shell/DB param write), **§5.49** (adding a capability resource moves
the count → grep EVERY module for exact-count asserts), §5.45 (never a second
odoo-bin while the server runs), §5.34/§6 (QA fixtures deleted + re-verified in
a fresh cursor).

**One phase per session.** Implement ONLY the phase named in your kickoff line.
Each phase ends with: tests green on vietuat, the HTML tracker updated (duty
§P.5 of each phase — same commit as the code), report written to
`docs/strategy/reports/<phase>-report.md`, pushed on 19.0.

---

## 0. Mission, phase map, binding non-goals

| Phase | Name | Closes (register refs) |
|---|---|---|
| **GC-1** | Capability truth + integration-breaking defects | G14, G15, G2, G12, G3, G11 (+ baseline for G4/C2) |
| **GC-2** | Spec-grade search + consent enforcement + terminology tooling | G17, G5 (eng), G8 (eng half) |
| **GC-3** | Continuous conformance machinery | G4 (eng), G10 |
| **GC-4** | Assurance prep + scope instruments | G9, G20 (draft), G1-prep; templates for G13/G16/G18 |

**Binding non-goals — ALL phases (violating any of these is a redesign, not a
deviation):**

- The facade stays **read-only**. No create/update/delete/vread/history/
  transaction routes. No new resource serializers (Condition/CodeSystem etc.
  are already registered; you add ZERO new resource types — the only new
  capability *entry* is the operation-only ValueSet row in GC-1).
- **No sudo** in any serializer or in `everything.py` (grep must stay clean).
- **No pip installs on the server** (conventions kickoff rule). `fhir.resources
  8.3.0` is already on vietuat — nothing else is needed. The GC-4 validator jar
  runs on YOUR machine, never the server.
- No changes to `health_fhir_adapter_vn` / `_base` in any phase (the VN export
  path reuses the facade serializers and inherits every fix for free).
- Do not emit `meta.profile` anywhere (that is a post-GC-4 decision after a
  clean VN Core validation — asserting an unvalidated profile is the one thing
  worse than asserting none).
- `docs/strategy/hl7-fhir-compliance-response.html`: you may edit ONLY §10.5
  status cells, the §10.10 log tbody (append above the marker comment, never
  edit existing rows), §10.11 status cells (GC-4 only), and the §0 tally
  sentence (GC-4 only). Nothing else in that file.

---

## 1. Verified plumbing facts — do NOT re-derive (all checked 2026-08-02, commit 55e9ea0b)

| # | Fact | Where |
|---|---|---|
| F1 | Serializer registry = single source for capability/routing/tests; 20 instances in core + CodeSystem (terminology) + Condition (health_condition) register at import → **21 live resource types** | `health_fhir_core/serializers/__init__.py:30-54`; downstream regs in `health_fhir_terminology/serializers/__init__.py`, `health_condition/serializers/__init__.py` |
| F2 | `serialize_batch` prefetches **every stored non-binary field** via `records.fetch([...])` — this is the G14 defect: on `res.partner` it drags group-gated `credit_limit`/`signup_type` → AccessError for any non-accounting service user | `health_fhir_core/serializers/base.py:302-312` |
| F3 | Patient `to_fhir` touches exactly: `name, active, patient_code, national_id (computed-encrypted), insurance_number, phone, mobile, email, zalo_user_id (guarded via `_fields`), gender, birth_date, deceased, street, street2, vietnamese_address, city, zip, district_id, state_id, country_id, primary_facility_id, catchment_province_name, write_date` | `health_fhir_core/serializers/patient.py:58-148` |
| F4 | CapabilityStatement built from REGISTRY; module-level cache keyed on base_url; `clear_capability_cache()`; Patient `$everything` operation is **hard-coded** (the seam A1 replaces); `_count` wrongly appended as a searchParam at line 34 | `health_fhir_core/capability.py:17-47` |
| F5 | `$lookup`/`$expand` routes are LIVE (`401` unauth verified) but **absent from the capability**; scopes `system/CodeSystem.read` / `system/ValueSet.read`; payload builders are `@api.model` on `medical.code` (`fhir_lookup`/`fhir_expand`) — testable without HTTP | `health_fhir_terminology/controllers/terminology.py:33-71` |
| F6 | `health.fall.risk` (model in `health_base/models/health_risk_assessment.py`) has **NO row in any `ir.model.access.csv`** — grep confirmed. `$everything` survives via §5.47 omit-and-declare | ledger §5.47; `everything.py:188-234` |
| F7 | The §5.47 suppression test **mocks** the AccessError (`patch.object(FallRisk, 'search_count', _deny)`) — it does NOT depend on the ACL being absent, so D2 will not break it | `health_fhir_core/tests/test_fhir_everything.py:319-349` |
| F8 | `consent_enforced` is seeded `noupdate="1"` value `False` — editing the XML will NOT flip it on upgrade (noupdate-seed rule); flip = direct DB UPDATE + **restart** (§5.48 per-worker ormcache) | `health_fhir_core/data/fhir_data.xml`; memory `reference_noupdate_seed_cutover` |
| F9 | Runtime validation flag exists, read per-request: `validation_enabled(env)` → controller `_runtime_validate` at `fhir.py:184`; currently unset on vietuat | `base.py:211-218`, `controllers/fhir.py:27,184` |
| F10 | ACL row pattern to mirror for D2 (health.observation): receptionist 1,0,0,0 · nurse 1,1,1,0 · head_nurse 1,1,1,0 · doctor 1,1,1,0 · operations_manager 1,0,0,0 · manager 1,1,1,0 | `health_vitals/security/ir.model.access.csv:2-7` |
| F11 | Token `system\|value` tolerance already exists ONCE (Patient identifier splits on `\|` and matches the value part) — clone that idea, don't invent a second convention | `patient.py:21-30` |
| F12 | Importer: CSV cols `code,display,display_vi,parent_code,synonyms`, idempotent upsert on (system, code), 2-pass parent resolution, malformed rows counted not aborted | `health_fhir_terminology/wizards/medical_code_import.py:15` |
| F13 | Repo remote is GitHub: `https://github.com/biztinct/health.git` (remote name `RHealth19`) — GitHub Actions is available for GC-3/C1 | `git remote -v` |
| F14 | Server: `fhir.resources==8.3.0` installed; DB `vietuat`; `dbfilter=^vietuat$`, `list_db=False`; live capability shows 21 resources, fhirVersion 4.0.1 | verified live 2026-08-02 |
| F15 | Known exact-count asserts already relaxed to `>=`: core phase2 `>=19`, terminology `>=20` (§5.49 history). GC-1 adds the ValueSet entry → count 21→22: **re-grep every module** (`grep -rn "len(listed)" addons/*/tests/`) and relax anything new | ledger §5.49 |

---

## 2. Phase GC-1 — capability truth + integration-breaking defects

**Scope:** the two defects that would break the first partner credential (G14,
G15) and making the CapabilityStatement declare exactly what the server does
(G2, G12, G3, G11), plus the committed capability baseline. **Modules
sanctioned:** `health_fhir_core`, `health_fhir_terminology` (registration +
one test relax if grep finds one), `health_base` (ACL csv ONLY), plus new files
under `docs/conformance/` and the HTML tracker cells. Nothing else.

### 2.1 D1 — Patient prefetch fix (G14)

Add an optional per-serializer prefetch declaration; base behaviour unchanged
when absent.

`base.py` — replace the fetch list inside `serialize_batch` (kernel — use
as-is):

```python
    #: optional explicit prefetch list; None = all stored non-relational-heavy
    #: fields (legacy behaviour). Serializers over models with group-gated
    #: fields (res.partner!) MUST declare this (§5.47 corollary).
    prefetch_fields = None

    def serialize_batch(self, records):
        if records:
            if self.prefetch_fields is not None:
                names = [f for f in self.prefetch_fields
                         if f in records._fields and records._fields[f].store]
            else:
                names = [fname for fname, f in records._fields.items()
                         if f.store and f.type not in (
                             'binary', 'image', 'one2many', 'many2many')]
            records.fetch(names)
        return [self.to_fhir(rec) for rec in records]
```

`patient.py` — declare (kernel — use as-is; computed fields `national_id`,
`catchment_province_name` are intentionally absent — they compute transparently
on access and the store-filter would drop them anyway):

```python
    prefetch_fields = [
        'name', 'active', 'patient_code', 'insurance_number',
        'phone', 'mobile', 'email', 'zalo_user_id', 'gender', 'birth_date',
        'deceased', 'street', 'street2', 'vietnamese_address', 'city', 'zip',
        'district_id', 'state_id', 'country_id', 'primary_facility_id',
        'write_date',
    ]
```

### 2.2 D2 — Flag ACL (G15)

`health_base/security/ir.model.access.csv`: add six rows for
`model_health_fall_risk` mirroring F10 exactly (same groups, same 1/0 matrix,
ids `access_health_fall_risk_<role>`). F7 guarantees the suppression test
survives. Do NOT touch `everything.py` — the §5.47 net stays.

### 2.3 A1 — operations registry + ValueSet entry + nits (G2, G12)

1. `health_fhir_core/serializers/__init__.py`: add module-level
   `OPERATIONS = {'Patient': [{'name': 'everything', 'definition':
   'http://hl7.org/fhir/OperationDefinition/Patient-everything'}]}` and
   `OPERATION_ONLY_RESOURCES = {}` (dict rtype → list of op dicts, for types
   with no serializer).
2. `capability.py`: delete the hard-coded Patient block (F4, lines 40-46);
   for each registry resource attach `OPERATIONS.get(rtype)`; after the
   registry loop, emit one entry per `OPERATION_ONLY_RESOURCES` item with
   `type`, `operation`, and NO `interaction`/`searchParam` keys. Remove the
   `_count` append (keep `_lastUpdated`). Add
   `'documentation': 'Read-only. Supported string modifiers: :exact, :contains.'`
   only in GC-2 (not now — don't pre-declare GC-2 behaviour).
3. `health_fhir_terminology/serializers/__init__.py`: alongside the existing
   CodeSystem registration, append
   `OPERATIONS['CodeSystem'] = [{'name': 'lookup', 'definition':
   'http://hl7.org/fhir/OperationDefinition/CodeSystem-lookup'}]` and
   `OPERATION_ONLY_RESOURCES['ValueSet'] = [{'name': 'expand', 'definition':
   'http://hl7.org/fhir/OperationDefinition/ValueSet-expand'}]`, then
   `clear_capability_cache()` (same pattern the module already uses).
4. searchParam `definition` canonicals — add a `'definition'` key per param
   using EXACTLY this rule set; where a param is not listed, omit the key
   (legal; never guess a canonical):
   - `patient` on Encounter/Observation/CarePlan/Goal/Condition/Consent/
     DocumentReference/Flag/AdverseEvent/ServiceRequest/Task/MedicationRequest/
     MedicationAdministration/QuestionnaireResponse/Appointment →
     `http://hl7.org/fhir/SearchParameter/clinical-patient`
   - `date` on Encounter/Observation/CarePlan/AdverseEvent/Appointment →
     `.../clinical-date`; `code` on Observation/Condition → `.../clinical-code`
   - Patient: identifier→`.../Patient-identifier`, name→`.../Patient-name`,
     birthdate→`.../individual-birthdate`, phone→`.../individual-phone`,
     telecom→`.../individual-telecom`
   - `status` → `.../<Resource>-status` for Encounter, Observation, CarePlan,
     Task, ServiceRequest, MedicationRequest (as `medications-status`),
     MedicationAdministration (as `medications-status`), Appointment,
     QuestionnaireResponse, Consent, Questionnaire
   - Condition: clinical-status→`.../Condition-clinical-status`,
     recorded-date→`.../Condition-recorded-date`;
     Goal lifecycle-status→`.../Goal-lifecycle-status`
   - Organization/Practitioner/Location name→`.../<Resource>-name`;
     identifier→`.../<Resource>-identifier`; Location
     organization→`.../Location-organization`; CodeSystem
     url→`.../CodeSystem-url`, name→`.../CodeSystem-name`;
     DocumentReference encounter→`.../clinical-encounter`,
     date→`.../DocumentReference-date`; QuestionnaireResponse
     authored→`.../QuestionnaireResponse-authored`,
     questionnaire→`.../QuestionnaireResponse-questionnaire`;
     Task encounter→`.../clinical-encounter`; Questionnaire
     name→`.../Questionnaire-name`
   - OMIT for: AdverseEvent severity, Patient's `phone`-as-token nuance stays
     as-is, anything else not listed.

### 2.4 A2 — software element (G3)

In `build_capability`, add:

```python
    'software': {'name': 'health19 / CarejioX', 'version': module_version},
```

where `module_version` = `env['ir.module.module'].sudo().search([('name', '=',
'health_fhir_core')], limit=1).latest_version or 'unknown'` — computed ONCE
before the cache store (cache is per-process; version only changes with an
upgrade+restart, so caching is correct).

### 2.5 A3 — version pinning + equivalence (G11)

1. New repo-root `requirements-fhir.txt`: `fhir.resources==8.3.0` (+ comment
   pointing at the ledger pip-chain gotcha — cryptography/pyOpenSSL).
2. Test asserting resolution: importing `fhir.resources.R4B.patient` succeeds
   AND `importlib.metadata.version('fhir.resources')` startswith `'8.'` — fail
   loudly if a future env resolves differently.
3. New `docs/conformance/r4-r4b-equivalence.md` — commit VERBATIM this claim
   with the table: R4B's substantive changes vs R4 are confined to
   Subscription/SubscriptionStatus/SubscriptionTopic, the Evidence-Based-
   Medicine resources (Evidence, EvidenceVariable, EvidenceReport, Citation),
   and the medication-definition family (MedicinalProductDefinition,
   PackagedProductDefinition, AdministrableProductDefinition, Ingredient,
   ClinicalUseDefinition, ManufacturedItemDefinition, RegulatedAuthorization,
   SubstanceDefinition). None of the 21 served types (list them) is among
   them; their StructureDefinitions are unchanged R4→R4B, so validating with
   R4B classes while declaring `fhirVersion 4.0.1` is sound. Then the pin.

### 2.6 C2 seed — capability baseline + route diff

1. Ship the baseline INSIDE the module (single source; the weekly cron in GC-3
   reads the same file): `health_fhir_core/conformance/capability_baseline.json`
   = the full statement with `date` key REMOVED (add the dir to the module
   package; no manifest `data` entry needed — it's read via
   `odoo.tools.misc.file_open`).
2. Baseline test: `build_capability(env)` minus `date` == the file, byte-exact
   after `json.dumps(..., sort_keys=True)` both sides. Regenerating the file is
   the ONLY sanctioned way to change capability (this is control C2's teeth).
3. Route-diff test (post_install): `self.env['ir.http'].routing_map()`, filter
   rules whose path starts `/fhir/r4`. Assert: (a) every literal `$op` route
   maps to a declared operation on the matching capability entry and vice
   versa (`$everything`→Patient, `$lookup`→CodeSystem, `$expand`→ValueSet);
   (b) every REGISTRY type has an interaction-bearing capability entry and
   every interaction-bearing entry is in REGISTRY; (c) operation-only entries
   (ValueSet) carry no `interaction` key. Both directions — empty diff.

### 2.7 Tests (GC-1)

- T1.1 minimal-privilege Patient read: user with ONLY
  `health_base.group_healthcare_receptionist` (no accounting/admin groups) —
  `REGISTRY['Patient'].serialize_batch(patient_record)` succeeds and the
  resource validates. (This is the G14 regression test; it MUST fail before
  D1 and pass after — verify that ordering locally before deploying.)
- T1.2 same user, `search_bundle` on Patient with `name` param → 200-shape
  bundle, no AccessError.
- T1.3 nurse-group user: `env['health.fall.risk'].search_count([])` does not
  raise; `$everything` bundle for a patient WITH a fall-risk row contains a
  `Flag` entry and NO `suppressed` OperationOutcome naming Flag.
- T1.4 existing suppression test still green (F7 — run, don't skip).
- T1.5 capability declares: Patient.everything, CodeSystem.lookup,
  ValueSet.expand; ValueSet entry has no `interaction`; no resource lists
  `_count` in searchParam; every listed `definition` URL starts with
  `http://hl7.org/fhir/SearchParameter/`.
- T1.6 software element present; version equals
  `ir.module.module.latest_version` for health_fhir_core.
- T1.7 baseline byte-equality test (2.6.2).
- T1.8 route-vs-capability diff test (2.6.3).
- T1.9 full statement still validates via `validate_resource` (R4B
  CapabilityStatement class).
- T1.10 §5.49 sweep: `grep -rn "len(listed)" addons/*/tests/` — relax any
  exact `== 21` to `>= 21` (declare each as a forced deviation).

### 2.8 Deploy + HTML duty + report-back (GC-1)

Deploy per conventions §2: upgrade
`health_base,health_fhir_core,health_fhir_terminology,health_condition`
with tests; quote the `0 failed` line. No PWA impact, no vi.po impact (no
user-visible strings — ACL names and capability text are machine-facing).

**HTML duty (same commit):** §10.5 → G14, G15, G2, G12, G3, G11 status cells
become `<span class="b ok">Closed</span><br><span class="note">2026-08-XX ·
<commit-short></span>`; append §10.10 row (phase `GC-1`, gaps moved, one-line
note). Touch nothing else in the file.

**Report-back:** live capability curl AFTER deploy showing software element +
22 resources + the three operations; confirmation T1.1 failed-before/
passed-after; any §5.49 relaxations; the regenerated baseline path.

---

## 3. Phase GC-2 — spec-grade search + consent enforcement + terminology tooling

**Scope:** G17 (search behaviour, binding tests, signed-mapping instrument),
G5 engineering half (enforce + runbook), G8 engineering half (converters +
sample-verified load path). **Modules sanctioned:** `health_fhir_core`,
`health_fhir_terminology`, new `tools/` scripts, `docs/conformance/`, HTML
cells. **NOT sanctioned:** any change weakening deny-by-default.

### 3.1 B2a — token `system|code` (G17)

Add to `base.py` a helper (kernel — use as-is):

```python
def token_domain(field_name, system_uri=None):
    """FHIR token search: accept `code`, `system|code`, `|code`.
    A non-matching explicit system yields ZERO matches (FHIR semantics:
    not an error), via an impossible domain."""
    def _domain(value):
        raw = (value or '').strip()
        if '|' in raw:
            system, _, code = raw.rpartition('|')
            if system and system_uri and system != system_uri:
                return [('id', '=', 0)]
            raw = code
        return [(field_name, '=', raw)]
    return _domain
```

Apply to: Observation `code` (`vitals_type_id.loinc_code`, system
`http://loinc.org`), Condition `code` (`code_id.code`, system
`http://hl7.org/fhir/sid/icd-10`), CodeSystem `url`/`name` (no system_uri).
Status params: keep bare-value matching but route them through the same helper
with `system_uri=None` so `|value` form works. Patient identifier stays as-is
(F11 — already tolerant, richer than the helper).

### 3.2 B2b — string modifiers + spec default (G17)

In `build_domain`: split incoming param names on `:`; accept modifiers
`exact` and `contains` on `string`-typed params only (anything else →
`FHIRNotSupported`, strict as ever). Semantics: default (no modifier) =
case-insensitive **starts-with** → `(field, '=ilike', escaped + '%')` with
`%`/`_` escaped in the value; `:contains` = `(field, 'ilike', value)`;
`:exact` = `(field, '=', value)` (case-sensitive). Update the three string
params (Patient/Organization/Practitioner/Location/Questionnaire `name`).
Existing tests that searched by substring must switch to prefix or `:contains`
— sanctioned, list each in the report. Add the capability `documentation` line
from §2.3 step 2 NOW (regenerate the baseline in the same commit — the C2 test
will force you to anyway).

### 3.3 B2c — binding-membership tests (G17)

New test module asserting every mapping table's VALUES ⊆ the R4 required set —
tables verbatim (kernel — use as-is):

```
Observation.status ⊆ {registered, preliminary, final, amended, corrected,
  cancelled, entered-in-error, unknown}
Encounter.status ⊆ {planned, arrived, triaged, in-progress, onleave, finished,
  cancelled, entered-in-error, unknown}
Appointment.status ⊆ {proposed, pending, booked, arrived, fulfilled, cancelled,
  noshow, entered-in-error, checked-in, waitlist}
CarePlan.status ⊆ {draft, active, on-hold, revoked, completed,
  entered-in-error, unknown}
Goal.lifecycleStatus ⊆ {proposed, planned, accepted, active, on-hold,
  completed, cancelled, entered-in-error, rejected}
Task.status ⊆ {draft, requested, received, accepted, rejected, ready,
  cancelled, in-progress, on-hold, failed, completed, entered-in-error}
MedicationRequest.status ⊆ {active, on-hold, cancelled, completed,
  entered-in-error, stopped, draft, unknown}
MedicationAdministration.status ⊆ {in-progress, not-done, on-hold, completed,
  entered-in-error, stopped, unknown}
QuestionnaireResponse.status ⊆ {in-progress, completed, amended,
  entered-in-error, stopped}
Consent.status ⊆ {draft, proposed, active, rejected, inactive,
  entered-in-error}
Flag.status ⊆ {active, inactive, entered-in-error}
Condition clinicalStatus code ⊆ {active, recurrence, relapse, inactive,
  remission, resolved}
ServiceRequest.status ⊆ {draft, active, on-hold, revoked, completed,
  entered-in-error, unknown}
```

Import each serializer module's actual mapping dict (`_STATE_TO_STATUS`,
`_*_STATUS_SEARCH`, etc. — find them by grep, do not retype values) and assert
subset. Any violation found = fix the MAPPING (report which), never widen the
allowed set.

### 3.4 B2d — clinical mapping table instrument (G17 → signature is OPS)

Generate `docs/conformance/clinical-status-mappings.md`: one table per
resource — Odoo model, Odoo state field + value, FHIR element, FHIR code,
one-line rationale — sourced from the same dicts as 3.3 (write a throwaway
generator or by hand, but values must match the code; the 3.3 tests are the
drift guard). End with a signature block (name / role / date) for the clinical
lead. Committing the doc closes the engineering half; the signature is §10.11.

### 3.5 D3 — enforce the consent gate (G5)

1. Deploy step (NOT xml — F8): on vietuat,
   `sudo su - postgres -c "psql -d vietuat -c \"UPDATE ir_config_parameter SET
   value='True' WHERE key='health_fhir_core.consent_enforced'\""` then FULL
   stop/start per conventions (§5.48 — workers cache the old value).
2. Re-run on the server: `test_fhir_consent` + `test_fhir_everything` suites
   (they set the param themselves in-test; green in both modes).
3. Live probe with QA fixtures (§5.34/§6 rules — create, probe, delete,
   fresh-cursor verify): synthetic patient WITHOUT data_sharing consent →
   authenticated Patient search must NOT contain them; check one
   `health.consent.check.log` row was written with source `fhir_facade`.
4. New `docs/conformance/consent-enforcement-runbook.md`: how ops records a
   `data_sharing` consent, what a deny looks like (byte-identical to
   not-found), where the check log and api.audit.log live, and the WARNING
   that with zero consents recorded the facade correctly serves zero PHI —
   consent capture is the §10.11 operational tail.

### 3.6 D4 — terminology load tooling (G8 engineering half)

1. `tools/icd10_claml_to_csv.py`: WHO ClaML XML → importer CSV (F12 columns);
   stdlib only; `--chapter` filter option; unknown elements skipped with a
   count.
2. `tools/icd10_vi_merge.py`: merge a MOH-KCB translation table (CSV or XLSX —
   accept CSV only, stdlib; document converting xlsx→csv first) into
   `display_vi` by code match; unmatched codes reported, never dropped.
3. Committed licence-safe fixture: `tools/fixtures/icd10_sample_50.csv` — 50
   SYNTHETIC rows exercising hierarchy (parents after children), diacritics in
   `display_vi`, a malformed row. NOT real WHO content beyond the ~31 codes
   already seeded.
4. Test: run the importer twice on the fixture through
   `medical.code.import` — first pass creates, second pass 0 created /
   0 updated (idempotence), malformed row counted.
5. Runbook section in `docs/conformance/consent-enforcement-runbook.md`? NO —
   separate file `docs/conformance/icd10-load-runbook.md`: licence acceptance,
   file acquisition, conversion commands, wizard steps, expected counts,
   §10.11 ownership.

### 3.7 Tests (GC-2)

T2.1 token helper: bare / `system|code` / wrong-system→empty / `|code`, on
Observation.code and Condition.code. T2.2 string default is starts-with
(create "Nguyễn Văn A" + "Văn B"; search `name=Nguy` matches first only;
search `name=Văn` matches neither; `name:contains=Văn` matches both;
`name:exact` exact-case only). T2.3 unknown modifier `name:fuzzy` → strict
400 FHIRNotSupported. T2.4 all 13 binding subsets (3.3). T2.5 importer
idempotence (3.6.4). T2.6 baseline test forces regeneration (documentation
key). T2.7 consent suites green (existing — run, quote).

### 3.8 Deploy + HTML duty + report-back (GC-2)

Upgrade `health_fhir_core,health_fhir_terminology` with tests. Then the D3
param flip + restart + live probe (3.5). **HTML duty:** G17 → Closed; G5 →
Closed with note `enforced <date> · consent capture = OPS`; G8 → `<span
class="b warn">In progress</span><br><span class="note">tooling done ·
licence + load = OPS</span>`; §10.10 row. **Report-back:** probe transcript
(fixture ids, absent-from-bundle evidence, consent-log row id, fixture
deletion + fresh-cursor verify), every test changed by 3.2, mapping-table path.

---

## 4. Phase GC-3 — continuous conformance machinery

**Scope:** G4 engineering (CI, deploy smoke, weekly cron), G10 (sampled
runtime validation). **Modules sanctioned:** `health_fhir_core`, new
`.github/workflows/`, `tools/`, `docs/conformance/`, HTML cells.

### 4.1 C1 — CI conformance gate

`.github/workflows/fhir-conformance.yml`: on push/PR touching
`addons/health_fhir_*`, `addons/health_condition`, `addons/health_base`, or
the workflow itself. Job: `services: postgres:15` (user/pass odoo);
`container: odoo:19`; steps — checkout; `pip install fhir.resources==8.3.0`;
run `odoo -d ci_test --addons-path=/usr/lib/python3/dist-packages/odoo/addons,addons
-i health_fhir_core,health_fhir_terminology,health_condition --test-enable
--stop-after-init --workers=0 --db_host=postgres --db_user=odoo
--db_password=odoo --log-level=test`; fail on non-zero exit AND grep the log
for `odoo.tests.result.*failed` ≠ 0. The dependency chain will pull the spine
modules from `addons/` automatically — if a dependency is missing IN CI ONLY
(enterprise-ish or data-heavy), skip-list is NOT allowed; instead report the
blocker and deliver the fallback: `tools/ci_fhir_local.sh` running the same
suite against a local odoo checkout + `docs/conformance/ci-runbook.md`. A
partially-green Actions run + fallback script = acceptable GC-3 exit ONLY
with the blocker named in the report.

### 4.2 C3 — post-deploy conformance smoke

`tools/fhir_deploy_smoke.sh` (runs ON the server, localhost:8069, after the
restart step of conventions §2): (1) GET `/fhir/r4/metadata` → assert HTTP
200, `fhirVersion == 4.0.1`, resource count ≥ 22, `software.version` equals
`$1` (passed by the operator; compare and FAIL on mismatch); (2) if
`$FHIR_SMOKE_TOKEN` set: for each interaction-bearing type, GET
`?_count=1` → 200 and `resourceType == Bundle` (reads are audited — that's
fine, it's the audit trail working); (3) exit non-zero on any failure with a
one-line reason. Companion note `docs/conformance/deploy-smoke.md` (when to
run, where the token comes from — the deactivated `smoke_test_client` is
reactivated BY OPS, never by this phase).

### 4.3 C4 — sampled runtime validation (G10)

Extend `validation_enabled(env)` → keep, plus new
`validation_sample_hit(env, client_label)`: params
`health_fhir_core.validate_sample_pct` (int 0–100, default 0, parse
defensively) and `health_fhir_core.validate_canary_client` (string; matches
the authenticated key/client label the gateway already logs). Controller: at
the existing `_runtime_validate` seams, validate when `validation_enabled` OR
canary match OR `random.random()*100 < pct`; wrap so a ValidationError is
**logged and swallowed** (`_logger.error('FHIR-CONFORMANCE-DRIFT rtype=%s id=%s: %s')`)
— NEVER an error to the caller (drift detection must not become an outage).
Tests: pct=100 + a monkeypatched serializer emitting an invalid resource →
response still 200-shaped, one drift line logged (assertLogs); pct=0 → no
validation call (mock counter).

### 4.4 C5 — weekly conformance cron

New model file in health_fhir_core: `models/fhir_conformance.py`, AbstractModel
`fhir.conformance` with `@api.model run_weekly_check()`: (1) rebuild capability
(cleared cache) and compare to the module baseline file (2.6.1) — same
normalization as the test; (2) for each interaction-bearing type, take 1 record
(`search(limit=1)` in a plain env as superuser — internal validation only,
nothing leaves the process) and `validate_resource` it; (3) on ANY failure:
`_logger.error` + create a `mail.activity` on the partner of the user named by
param `health_fhir_core.conformance_owner_login` (fallback: admin) summarizing
failures; on success log one info line `FHIR-CONFORMANCE-OK <n> types`. Cron
record (noupdate, weekly, active) in `data/fhir_data.xml`… **NO — new file**
`data/fhir_conformance_cron.xml` (F8: never touch the existing noupdate seed
file). Add manifest entry. Test: call `run_weekly_check()` directly — green
path logs OK; corrupt-baseline path (feed a tmp wrong baseline via mock)
creates the activity.

### 4.5 Deploy + HTML duty + report-back (GC-3)

Upgrade `health_fhir_core`; run the smoke script end-to-end once (no token
mode + with a token if ops has activated one — otherwise metadata-only, say
so). Push triggers the Actions run — link it in the report. **HTML duty:**
G10 → Closed; G4 → Closed with note `owner naming = OPS (§10.11)`; §10.10
row. **Report-back:** Actions run URL + conclusion (or the named blocker +
fallback evidence), smoke transcript, drift-injection test output, cron
activity screenshot-by-data (the activity row id).

---

## 5. Phase GC-4 — assurance prep + scope instruments

**Scope:** everything that makes the OPERATIONAL closures one-step for their
owners: Touchstone prep (G1), VN Core attempt (G9), the signable instruments
(G20, G13, G18, G16 scope doc), and the final tracker pass that produces the
end-state assessment. **Modules sanctioned:** `health_fhir_core` (seed wizard
only), `tools/`, `docs/conformance/`, HTML (§10.5 cells, §10.10 row, §10.11
statuses, §0 tally sentence).

### 5.1 Conformance seed wizard + Touchstone runbook (G1 prep)

1. `health_fhir_core/wizards/fhir_conformance_seed.py`, TransientModel
   `fhir.conformance.seed`, admin-group only, HARD GUARD: raises unless
   `ir.config_parameter` `health_fhir_core.allow_conformance_seed` == `'1'`
   (never seeded true anywhere — the operator sets it consciously on the
   conformance db only). `action_seed`: creates `FHIRCONF-` prefixed synthetic
   data — 3 patients (one fully populated incl. address/identifiers, one
   minimal, one deceased) + per patient one record for EVERY compartment type
   (clone field recipes from the test setUps in `test_fhir_phase2.py` /
   `test_fhir_everything.py` — they are the known-good creation paths) + a
   data_sharing consent for two of three (the third exercises deny).
   `action_purge`: deletes everything by prefix, archive-not-delete where
   FK-restricted (consent rows — §prior art: QA patients 9765/9766).
2. `docs/conformance/touchstone-runbook.md`: stand up db `fhirconf` on the
   server (conventions §2 install list, THIS wizard, param flip, note that
   `dbfilter=^vietuat$` + `list_db=False` means the operator must serve the
   conformance db explicitly — document the temporary conf change + revert),
   create a dedicated OAuth client with all read scopes, Touchstone account
   steps, which test-script families to execute (R4 basic read/search +
   capability), where results publish, and the §10.10 log-row the operator
   appends afterwards.

### 5.2 D6 — VN Core validation attempt (G9)

Runs on YOUR machine (never the server): `tools/vn_core_validate.sh` —
download `validator_cli.jar` (hapifhir/org.hl7.fhir.core releases), run
`java -jar validator_cli.jar <samples> -version 4.0.1 -ig hl7.fhir.vn.core`
against a directory of sample resources (export via the seed wizard on a
local/dev db, or serialize from a test run — 1 sample JSON per resource type,
committed under `docs/conformance/vn-core-samples/`, synthetic only).
Output → `docs/conformance/vn-core-delta.md`: per-resource table
(resource / VN Core profile exists? / errors / warnings / assessment / action).
If the package or jar cannot be fetched (network/geo), commit the script +
samples + a delta doc stating exactly what was attempted and blocked —
G9 then stays In-progress with the blocker named (do NOT mark Closed).
Reminder: **no `meta.profile` emission** regardless of outcome (§0 non-goal).

### 5.3 The signable instruments (G20, G13, G18, G16)

Four docs under `docs/conformance/` — content drafted COMPLETE so the owner
only signs/sends (each ends with owner/date/signature block):

1. `scope-and-non-goals.md` (G20): entries for FHIR writes, vread/history,
   Bulk `$export`, LGSP live transport (state plainly: `transport()` is a
   file-export stub pending the national platform opening — cite
   `fhir_adapter_vn.py:201-205`), DICOMweb, SG/ID/AU adapters, HL7 v2.x/CDA
   (marked "pending E6 survey"). Each: what/why-not-now/trigger/estimate/
   owner/review-cadence (quarterly).
2. `counterparty-interface-survey.md` (G13): one-page questionnaire — systems
   in use, interface standards required (FHIR version? v2 messages+versions?
   CDA? proprietary?), transport, auth, test-environment availability,
   contact.
3. `vneid-determination-template.md` (G18): determination memo skeleton —
   question, findings, decision (integrate now / defer with trigger), interim
   control (CCCD capture + manual verification procedure reference).
4. `security-review-scope.md` (G16): attack-surface inventory for the pentest
   vendor — enumerate from code, not memory: all `/fhir/r4/*` + `/oauth/*` +
   `/api/v1/*` routes, auth flows, scope model, consent gate, audit models,
   the §5.47 suppression semantics, PHI-encryption boundary. Factual surface
   listing ONLY — no vulnerability speculation in a committed doc.

### 5.4 Final tracker pass — the end-state assessment (the thing the client asked for)

In the SAME commit as 5.1–5.3: §10.5 → G9 per 5.2 outcome; G20/G13/G18 status
note `instrument ready · signature/send = OPS`; G1 → `<span class="b
warn">In progress</span><br><span class="note">prep complete · run = OPS</span>`.
§10.11 → flip every row whose "engineering has provided" artefact now exists
to `<span class="b warn">Ready — waiting on owner</span>`; rows still blocked
externally (G6 counsel, G19 XSD) stay `Waiting`. §10.10 → GC-4 row. §0 tally
sentence → update to state: engineering phases complete; N items Closed; the
remainder enumerated in §10.11 are operational-only. Numbers must be derived
by actually counting the matrix — no drift between the tally and the table.

### 5.5 Tests + deploy + report-back (GC-4)

T4.1 seed wizard: guard param off → raises; on → creates ≥1 record per
compartment type (assert against REGISTRY so it can't silently miss a type);
purge removes/archives all by prefix; fresh-cursor verify. T4.2 seeded
`$everything` on the consented patient validates end-to-end; unconsented
patient (enforced mode in-test) → denied. Deploy: upgrade `health_fhir_core`.
**Report-back:** validator outcome (or exact blocker), sample-set path, the
four instrument docs, the final §10.5/§10.11 state as a table in the report,
and any candidate NEW ledger entries.

---

## 6. Review protocol

After each phase the user reports "opus done" → Fable auto-reviews first
(bulk review in ONE subagent: whole-diff vs this spec + independent server
verification — implementer QA claims are not trusted), personally reads the
risky files (`base.py`, `controllers/fhir.py`, ACL csv, the consent flip,
cron/su usage in 4.4), ships small fixes directly, then issues the next
phase's kickoff. GC-5 (CA signature + BHYT XML + possible VNeID build) is
designed AFTER the GC-4 review, once procurement/XSD/determination land —
it is intentionally NOT in this document.

---

## 7. Kickoff (paste into the Opus session, verbatim)

Implement Phase GC-1 (ONLY §2 of the handover) specified in
docs/strategy/handovers/hl7-gap-closure.md.

Then the canonical block from docs/strategy/KICKOFF-TEMPLATE.md with
`<PHASE-DOC>` = `hl7-gap-closure`.

Subsequent phases (issued one at a time after each review): same line with
GC-2 → §3, GC-3 → §4, GC-4 → §5.
