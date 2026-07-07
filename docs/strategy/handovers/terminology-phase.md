# Handover: Terminology Service — `health_fhir_terminology`

Read `docs/strategy/HANDOVER-CONVENTIONS.md` FIRST. Definition of done is
its §8. Spec source: `docs/strategy/architecture-interop.md` §2
(local-first terminology). This phase is the prerequisite for the
Circular 13/2025 EMR export (ICD-10 coded diagnoses are the Vietnam MOH
mandate).

## 0. Scope

One NEW module `addons/health_fhir_terminology`:

1. Local code tables: `medical.coding.system` + `medical.code`.
2. Bulk import wizard (CSV) for ICD-10 and any other system — idempotent
   upsert, chunked.
3. Seed data: the coding systems, the LOINC vital-signs core (13 codes),
   ~30 common home-care ICD-10 codes (WHO English + Vietnamese display).
4. Coding sidecar on clinical notes: `condition_code_ids` m2m (ICD-10
   picker, Vietnamese-first typeahead via `name_search` — NO custom OWL
   widget this phase).
5. Read-only FHIR terminology endpoints on the existing facade auth:
   `CodeSystem` (search+read via the registry), `CodeSystem/$lookup`,
   `ValueSet/$expand` (local tables only).

**Non-goals (do NOT build):** external terminology servers
(Snowstorm/Ontoserver proxy), SNOMED content, AI retro-coding /
suggested-code review queue (separate AI phase), PWA coding UI (⇒ **no
PWA version bump**), FHIR Condition resource, ICD-11, claims/4210 XML,
FSO `service_code_id`.

## 1. Models

### 1.1 `medical.coding.system`

| Field | Type | Notes |
|---|---|---|
| name | Char, required | e.g. "ICD-10 (WHO + MOH VN)" |
| uri | Char, required | canonical system URI (see seeds) — unique via `init()` index |
| code | Char, required | short key: `icd10`, `loinc`, `ucum`, `rxnorm`, `snomed`, `health19-services` — unique via `init()` index |
| version | Char | free text, e.g. "2019" |
| description | Text | |
| active | Boolean, default True | SNOMED seeded inactive (VN is not a SNOMED member) |
| code_count | Integer compute (non-stored) | search_count of codes |

### 1.2 `medical.code`

| Field | Type | Notes |
|---|---|---|
| system_id | m2o medical.coding.system, required, ondelete='restrict', index | |
| code | Char, required, index | e.g. `I10`, `8867-4` |
| display | Char, required | English display |
| display_vi | Char | Vietnamese display (MOH translation) |
| parent_id | m2o medical.code | hierarchy (ICD-10 chapter/block), ondelete='set null' |
| synonyms | Char | semicolon-separated alternates, searched by name_search |
| active | Boolean, default True | never unlink imported codes; archive |

- `init()`: `CREATE UNIQUE INDEX IF NOT EXISTS medical_code_system_code_uidx
  ON medical_code (system_id, code)` (conventions §5.1 — `_sql_constraints`
  are not materialized). Pre-check duplicates in `create()` before
  `super()` and raise ValidationError (conventions §5.3).
- `display_name` compute: `"[<code>] <display_vi or display>"` —
  Vietnamese-first per spec §2.3.
- `name_search` override: match against code (=ilike prefix), display,
  display_vi, and synonyms (ilike each), OR-combined, limit respected.
  This IS the typeahead — standard `many2many_tags` widgets get
  Vietnamese-first search for free.
- Optional helper `get(system_code, code)` → browse record or empty
  (mirrors `health.vitals.type.get_by_code` ergonomics).

## 2. Import wizard (`medical.code.import`)

TransientModel + form view, menu under the module's Configuration menu.

- Fields: `system_id` (required), `file` (Binary, required),
  `filename`, `delimiter` (default `,`), `has_header` (default True),
  result fields (`created_count`, `updated_count`, `skipped_count`,
  `error_text`).
- CSV columns (fixed order): `code,display,display_vi,parent_code,synonyms`.
  Only `code` + `display` mandatory per row.
- Behaviour: decode utf-8-sig (Excel BOM); iterate rows; **idempotent
  upsert** keyed on (system_id, code) — existing rows get display/
  display_vi/synonyms updated, never duplicated; unknown `parent_code`
  resolved in a SECOND pass (parents may appear after children in the
  file); malformed rows are counted + reported in `error_text`
  (first 20), never abort the whole import; create in batches of 1000
  vals (one `create()` call per batch — the ORM handles it).
- Return an action re-opening the wizard form showing the counts.
- Report-back requirement: document in your final report where the full
  code files come from — WHO ICD-10 releases (icd.who.int) and the
  Vietnam MOH ICD-10 translation (KCB portal / Circular guidance) — the
  module ships the importer, NOT the full licensed content.

## 3. Seed data (`data/`, noupdate="1")

- `coding_systems.xml`: icd10 (`http://hl7.org/fhir/sid/icd-10`), loinc
  (`http://loinc.org`), ucum (`http://unitsofmeasure.org`), rxnorm
  (`http://www.nlm.nih.gov/research/umls/rxnorm`), snomed
  (`http://snomed.info/sct`, **active=False**), health19_services
  (`urn:health19:services`).
- `codes_loinc_vitals.xml`: the 13 LOINC vital-signs core codes from
  spec §2.2 (85354-9, 8480-6, 8462-4, 8867-4, 9279-1, 8310-5, 2708-6,
  59408-5, 29463-7, 8302-2, 39156-5, 15074-8 + pain 72514-3) with
  Vietnamese displays.
- `codes_icd10_starter.xml`: ~30 common home-care/geriatric ICD-10 codes
  (I10, I11, I25, I50, I63, I69.3, E11, E78, F03, F32, G20, G30, J18,
  J44, M17, M54, M81, N18, N39.0, L89, R26, R32, Z74.0, …) with both
  displays — enough for demo + tests; full load via the importer.

## 4. Coding sidecar

- FIRST locate the `health.clinical.note` model (search addons/ — it is
  an existing model; likely health_base or health_fieldservice) and
  inherit it in this module: add `condition_code_ids` m2m →
  `medical.code`, relation table `clinical_note_condition_code_rel`,
  domain `[('system_id.code', '=', 'icd10')]`, string "Coded Diagnoses
  (ICD-10)".
- View inherit: add the field with `widget="many2many_tags"` near the
  diagnosis/assessment text field of the note form (inspect the existing
  form view; chatter stays at bottom). Do NOT touch the existing
  free-text fields (non-destructive sidecar, spec §2.3) — some are
  PHI-encrypted compute fields; you only ADD the m2m.
- No other models get coded fields this phase.

## 5. FHIR terminology endpoints

Module depends on `health_fhir_core` and plugs into its plumbing:

1. **CodeSystem serializer** registered in the REGISTRY (follow the
   Phase 2 registration pattern in
   `health_fhir_core/serializers/__init__.py` — since the registry
   tuple lives in health_fhir_core, register from this module by
   importing REGISTRY and adding the instance at import time of this
   module's `serializers` package; verify capability cache is cleared
   or rebuilt lazily — inspect `clear_capability_cache()` usage):
   - `resource_type='CodeSystem'`, `odoo_model='medical.coding.system'`,
     base_domain `[('active','=',True)]`, search_params: `url` (token →
     uri), `name` (token → code).
   - to_fhir: `{resourceType, id, url: uri, version, name: code,
     title: name, status: 'active', content: 'fragment',
     count: <code_count>}` — do NOT inline concept[] (ICD-10 is 14k+
     rows); `content: 'fragment'` signals partial representation.
2. **Operations controller** (own `controllers/terminology.py`, reusing
   `_gateway_authenticate` + OperationOutcome helpers exactly like
   `health_fhir_core/controllers/fhir.py`):
   - `GET /fhir/r4/CodeSystem/$lookup?system=<uri>&code=<code>` →
     `Parameters` resource `{name, display, designation[] (vi)}`;
     404 OperationOutcome when unknown. Scope: `system/CodeSystem.read`.
   - `GET /fhir/r4/ValueSet/$expand?url=<system-uri>&filter=<text>&count=<n≤50>`
     → dynamically-built `ValueSet` with `expansion.contains[]`
     (`{system, code, display}`), filter via the same name_search
     matching, default count 20, max 50. Scope: `system/ValueSet.read`.
   - Route registration order gotcha: `$lookup` under
     `/fhir/r4/CodeSystem/...` must not be shadowed by health_fhir_core's
     `/fhir/r4/<rtype>/<int:rid>` — `$lookup` is not an int so the
     existing converter won't match it; VERIFY with a live curl anyway
     and note the result.

## 6. Security & module plumbing

- `depends`: `health_base`, `health_fhir_core`, + whichever module owns
  `health.clinical.note` (verify; avoid duplicates if already in the
  chain).
- ACL: `medical.coding.system` / `medical.code`: read for
  `health_base.group_healthcare_base`, write/create for
  `health_healthcare_admin`-level groups (follow an existing
  reference-data ACL, e.g. health.vitals.type in health_vitals);
  unlink admin-only. Wizard: create/write for the same admin groups.
  No record rules (reference data, not client-scoped — no catchment).
- Menus: "Terminology" config menu (systems, codes, import wizard) —
  place under the existing health configuration/settings menu tree that
  health_vitals or health_base uses (inspect + match).
- `i18n/vi.po` for all user-visible strings (wizard labels, menus,
  field strings).
- No PWA files, no PWA bump.

## 7. Tests (`tests/test_terminology.py`)

Conventions §6 apply. Direct-call tests, `@tagged('post_install',
'-at_install')`:

1. Seeds: 6 systems exist; snomed inactive; ≥13 LOINC + ≥25 ICD-10 codes.
2. Unique guard: creating a duplicate (system, code) raises
   ValidationError (pre-check, not IntegrityError).
3. `name_search`: 'I10' matches by code; a Vietnamese fragment of a
   seeded display_vi matches; a synonym matches.
4. Importer: build a small CSV in-memory (base64) with 5 rows incl. one
   child-before-parent pair and one malformed row → assert
   created/updated/skipped counts, parent resolved, re-import updates
   display without duplicating.
5. Clinical-note sidecar: create a note (inspect existing tests of the
   owning module for required fixture fields), set condition_code_ids,
   read back.
6. CodeSystem serializer: to_fhir validates via
   `health_fhir_core.serializers.base.validate_resource`; REGISTRY
   contains 'CodeSystem'; capability lists 20 resources.
7. $lookup/$expand logic: call the underlying python helpers directly
   (factor the lookup/expand payload builders as model or controller
   static methods so they are testable without HTTP) — known code,
   unknown code, vi filter.

## 8. Deploy & verify

- `-i health_fhir_terminology --test-tags /health_fhir_terminology`
  (plus `/health_fhir_core` to prove the facade still passes: run both).
- Live smoke (public metadata): metadata now lists 20 types incl.
  CodeSystem. With no token, `$lookup` must return the same
  401/OperationOutcome behaviour as other facade routes (curl and note
  status code).
- Server log check per conventions §2; login 200.

## 9. Report-back extras

(a) which module owns `health.clinical.note` and the exact view you
inherited; (b) how CodeSystem registration into health_fhir_core's
REGISTRY was wired (import order) and proof the capability cache picks
it up; (c) ICD-10/MOH data sourcing instructions for the full import;
(d) confirmation Phase 1+2 FHIR tests still green (quote both result
lines).
