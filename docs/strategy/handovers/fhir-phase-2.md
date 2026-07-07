# Handover: FHIR Phase 2 — Clinical-Spine Resources on the R4 Facade

Read `docs/strategy/HANDOVER-CONVENTIONS.md` FIRST. Definition of done is
its §8. This phase extends the existing `health_fhir_core` module — you
are NOT creating a new module and NOT creating any new Odoo models. It is
pure read-only serializer work on an established pattern, plus tests.

## 0. Scope

Add **11 read-only FHIR R4 resources** to the existing facade, sourced
from the shipped clinical-spine modules:

| # | Resource | Source model | Module |
|---|---|---|---|
| 1 | Observation | health.observation | health_vitals |
| 2 | CarePlan | health.careplan | health_careplan |
| 3 | Goal | health.careplan.goal | health_careplan |
| 4 | Task | health.careplan.task | health_careplan |
| 5 | MedicationRequest | health.medication.order | health_emar |
| 6 | MedicationAdministration | health.medication.administration | health_emar |
| 7 | Questionnaire | health.form.template | health_forms |
| 8 | QuestionnaireResponse | health.form.instance | health_forms |
| 9 | AdverseEvent | health.incident | health_incident |
| 10 | Flag | health.fall.risk | health_base (verify location) |
| 11 | Consent | health.consent | health_consent |

**Non-goals (do NOT build):** write/create endpoints, `_history`,
terminology service, country adapters (SATUSEHAT/NEHR), PlanDefinition,
MedicationStatement, subscription/webhook changes, PWA changes (⇒ **no
PWA version bump** this phase).

## 1. How the existing facade works (follow it exactly)

- `health_fhir_core/serializers/__init__.py` builds `REGISTRY` — a dict of
  singleton serializer instances keyed by `resource_type`. Add your 11 new
  serializer instances to that tuple; **everything else (controller
  routing, CapabilityStatement, scope names `system/<Resource>.read`,
  audit logging) picks them up automatically from the registry.**
- Each serializer subclasses `FHIRSerializer` (`serializers/base.py`) and
  defines: `resource_type`, `odoo_model`, `search_params`
  (`{name: {'type': ..., 'domain': callable}}`), `base_domain(env)`,
  `to_fhir(record)`, `patient_ids_of(records)`.
- Reuse the existing helpers exactly: `self.meta(record)`,
  `self.reference(rtype, rid, display=)`, `date_param_domain(field)`, and
  the patient-reference param helper used by the FSO serializers
  (see `serializers/fso_common.py` / `encounter.py` — parse both
  `Patient/123` and `123` forms). Do not invent parallel helpers.
- Study `serializers/patient.py` and `serializers/encounter.py` before
  writing anything; match their code style, optional-field guards
  (only emit keys when data exists), and identifier conventions.
- Search runs as the token's service user, so record rules apply; every
  read/search is audited with `patient_ids_of(records)`.

## 2. Binding decisions (do not deviate)

1. **Manifest depends** — add the six spine modules to
   `health_fhir_core/__manifest__.py` depends: `health_vitals`,
   `health_careplan`, `health_emar`, `health_forms`, `health_incident`,
   `health_consent`. Rationale: the spine is now the mandatory product
   core (7/7 shipped); conditional soft-registration is not worth the
   complexity. Bump the module version minor (e.g. `…1.0.x` → `…1.1.0`).
2. **IDs** — resource `id` = str(odoo record id), consistent with Phase 1.
3. **References** — `subject`/`patient` → `Patient/<client_id>`.
   `encounter` → `Encounter/<fso_id>` **only when the FSO qualifies for
   the Encounter resource** (reuse the exact state list from
   `encounter.py` `base_domain` — a draft FSO must not produce a dangling
   Encounter reference; omit the key instead).
4. **Coding systems** (use these URIs verbatim):
   - LOINC: `http://loinc.org`; UCUM: `http://unitsofmeasure.org`
   - RxNorm: `http://www.nlm.nih.gov/research/umls/rxnorm`
   - DAV registry identifier system: `https://dav.gov.vn/so-dang-ky`
   - Local code systems: `urn:health19:incident-types`,
     `urn:health19:consent-types`, `urn:health19:careplan-category`,
     `urn:health19:not-done-reason`, `urn:health19:flag-types`
5. **PHI restraint** — narrative free-text fields flagged as PHI stay OUT
   of resources unless the mapping table below says otherwise (e.g.
   incident `investigation_notes`, `root_cause` are NOT exported;
   `description` is). Never emit `signature`/attachment binary content —
   metadata only.
6. **No new user-visible strings** ⇒ no vi.po changes needed. No views.
7. All serializer output must validate against `fhir.resources` (R4B,
   pydantic) via the existing `validate_resource()` — the tests enforce
   this for every resource.

## 3. Per-resource specification

Conventions for the tables: "→" is the FHIR path; omit any element whose
source is empty. All resources get `meta` via `self.meta(record)`.

### 3.1 Observation ← health.observation

- `base_domain`: `[('state', '!=', False)]` equivalent — all rows; panels
  and components both serialize (see below).
- `search_params`: `patient` (reference → `client_id`), `date`
  (`date_param_domain('effective_datetime')`), `status` (token → state,
  translate hyphens: `entered-in-error` → `entered_in_error`), `code`
  (token → `('vitals_type_id.loinc_code', '=', value)`).
- Mapping:
  - status: preliminary→`preliminary`, final→`final`, amended→`amended`,
    entered_in_error→`entered-in-error`
  - `code` → CodeableConcept: coding `{system: loinc, code:
    record.loinc_code, display: vitals_type_id.name}`; `text` =
    vitals_type name.
  - `category`: when `vitals_type_id.is_fhir_vital_sign` emit the standard
    vital-signs category coding
    (`http://terminology.hl7.org/CodeSystem/observation-category`,
    code `vital-signs`).
  - subject → Patient ref; encounter per binding decision 3 (from
    `order_id`); performer → `[{display: performer_id.name}]`;
    effectiveDateTime → `effective_datetime` (use the existing
    `fhir_instant` helper); method → `{'text': method}` if set;
    device → `{'display': device}` if set.
  - **Value & panels**: if `vitals_type_id.value_type == 'panel'` the row
    has NO value — emit `component[]` instead: one component per
    `child_ids` observation, each `{code: <child LOINC CodeableConcept>,
    valueQuantity: {...}}`. For non-panel rows: quantity →
    `valueQuantity {value, unit: unit_display, system: UCUM URI, code:
    ucum_unit}`; string → `valueString`.
  - Child observations that have a `parent_id` still serialize as
    standalone Observations too (they're reachable by search) — that is
    fine and intended; do not suppress them.
- `patient_ids_of` → `records.mapped('client_id').ids`

### 3.2 CarePlan ← health.careplan

- `base_domain`: all (active records; the ORM hides archived by default).
- `search_params`: `patient`, `status` (token, see map), `date`
  (`date_param_domain('period_start')`).
- Mapping: status: draft→`draft`, active→`active`,
  under_review→`active`, completed→`completed`, cancelled→`revoked`;
  `intent` = `'plan'` (constant); title, description (strip to plain text
  or pass HTML into `description` as text — use `html2plaintext`);
  category → CodeableConcept with local system
  `urn:health19:careplan-category`, code = category; subject → Patient;
  period `{start: period_start, end: period_end}`; author →
  `{display: author_id.name}`; goal → list of
  `self.reference('Goal', g.id)` for goal_ids; `activity[]` → one entry
  per careplan_activity_ids with
  `detail {status: <map>, code: {text: name},
  description: html2plaintext(instructions)}` — activity status map:
  not_started→`not-started`, scheduled→`scheduled`,
  in_progress→`in-progress`, completed→`completed`,
  cancelled→`cancelled`.

### 3.3 Goal ← health.careplan.goal

- `search_params`: `patient` (via `careplan_id.client_id` — domain
  `('careplan_id.client_id', '=', id)`), `lifecycle-status` (token).
- Mapping: lifecycleStatus: proposed→`proposed`, active→`active`,
  on_hold→`on-hold`, completed→`completed`, cancelled→`cancelled`;
  achievementStatus (if set) → CodeableConcept system
  `http://terminology.hl7.org/CodeSystem/goal-achievement`, code map:
  in_progress→`in-progress`, improving→`improving`, worsening→`worsening`,
  achieved→`achieved`, not_achieved→`not-achieved`;
  description `{text: name}`; subject → Patient (`client_id` related);
  priority (if set) → CodeableConcept system
  `http://terminology.hl7.org/CodeSystem/goal-priority`, code
  `high-priority|medium-priority|low-priority`; `target[]` (single
  entry when vitals_type_id set): `measure` = LOINC CodeableConcept from
  vitals_type, `detailRange {low: {value: target_value_min, unit,
  system, code}, high: {...}}` (omit missing bounds), `dueDate`.
- `patient_ids_of` → `records.mapped('careplan_id.client_id').ids`

### 3.4 Task ← health.careplan.task

- `search_params`: `patient` (via `careplan_id.client_id`), `status`
  (token per map), `encounter` (reference → `fso_id`).
- Mapping: status: pending→`requested`, done→`completed`,
  not_done→`failed`; `intent` = `'order'` (constant);
  statusReason (when not_done) → CodeableConcept
  `{coding: [{system: urn:health19:not-done-reason, code:
  not_done_reason}], text: not_done_note or selection label}`;
  code `{text: name}`; description = html2plaintext(instructions);
  `for` → Patient ref; encounter per binding decision 3 (from `fso_id`);
  `executionPeriod.end` = completed_datetime (if set);
  `owner` → `{display: completed_by_id.name}` (if set);
  basedOn → `[self.reference('CarePlan', careplan_id.id)]`.

### 3.5 MedicationRequest ← health.medication.order

- `base_domain`: all. `search_params`: `patient`, `status`.
- Mapping: status: draft→`draft`, active→`active`, on_hold→`on-hold`,
  completed→`completed`, cancelled→`cancelled`; `intent` = `'order'`;
  medicationCodeableConcept: text = medication display name, plus RxNorm
  coding when `medication_id.rxnorm_code` set, plus identifier-style
  coding is NOT valid here — instead put DAV number into
  `medicationCodeableConcept.coding` with the DAV system when
  `dav_reg_no` set; subject → Patient; requester →
  `{display: prescriber_id.name or prescriber_name}` (if either);
  authoredOn = create_date date; `dosageInstruction[]` (single entry):
  `text` = instructions (or synthesized "dose unit route frequency"),
  `patientInstruction` = instructions, `route {text: route}`,
  `timing {code: {text: frequency}}`,
  `asNeededBoolean` = is_prn (only when True; when prn_reason set use
  `asNeededCodeableConcept {text: prn_reason}` INSTEAD of the boolean —
  they are mutually exclusive in R4),
  `doseAndRate [{doseQuantity: {value: dose_quantity,
  unit: dose_unit}}]`, and bounds:
  `timing.repeat.boundsPeriod {start: start_date, end: end_date}`.

### 3.6 MedicationAdministration ← health.medication.administration

- `base_domain`: `[('state', '!=', 'planned')]` — a planned slot is not
  an event yet and MUST NOT appear on the facade.
- `search_params`: `patient` (related client_id — domain on
  `('client_id', '=', id)` works, the related field is stored via order;
  if not stored use `('order_id.client_id', '=', id)` — VERIFY store
  status first), `status` (token per map), `date`
  (`date_param_domain('actual_datetime')`).
- Mapping: status: given→`completed`, not_given→`not-done`,
  refused→`not-done`, cancelled→`stopped`; statusReason (for
  not_given/refused) → `[{text: reason_id.name or 'refused'}]`;
  medicationCodeableConcept as in 3.5 (via `medication_id`);
  subject → Patient; context per binding decision 3 (from `fso_id`);
  effectiveDateTime = actual_datetime (fallback planned_datetime);
  performer → `[{actor: {display: nurse_id.name}}]` plus a second entry
  for witness_id when set; request →
  `self.reference('MedicationRequest', order_id.id)`;
  dosage `{dose: {value: dose_given, unit: dose_unit}}` when dose_given;
  note → `[{text: notes}]` when set.

### 3.7 Questionnaire ← health.form.template

- `base_domain`: `[('state', 'in', ['published', 'retired'])]` (drafts
  are not public contract).
- `search_params`: `name` (token → `('code', '=', value)`), `status`.
- Mapping: status: published→`active`, retired→`retired`;
  name = code; title = name; version = str(version);
  description = html2plaintext(description);
  date = published_date; `item[]` from `question_ids` — for each
  question emit `{linkId: <question key/code — inspect the
  health.form.question model for the exact key field used in
  schema_json>, text: <question label>, type: <map the question type to
  FHIR item type: number→'decimal' or 'integer' per question config,
  choice→'choice', text→'string', boolean→'boolean', photo/signature→
  'attachment'>}`; for choice questions include
  `answerOption [{valueCoding: {code, display}}]` from the question's
  options. Inspect `health.form.question` and one `schema_json` sample
  first; keep linkIds identical to the schema keys so
  QuestionnaireResponse items correlate.

### 3.8 QuestionnaireResponse ← health.form.instance

- `base_domain`: all. `search_params`: `patient`, `status` (map),
  `authored` (`date_param_domain('completed_datetime')`),
  `questionnaire` (reference → `template_id`).
- Mapping: status: draft→`in-progress`, completed→`completed`,
  amended→`amended`, cancelled→`stopped`;
  questionnaire = canonical-ish reference string
  `"Questionnaire/<template_id.id>"` (R4 type is canonical — a plain
  string, NOT a Reference object); subject → Patient; encounter per
  binding decision 3 (from `order_id`); authored = completed_datetime;
  author → `{display: performer_id.name}`;
  `item[]`: iterate the questions in `schema_snapshot` (NOT the live
  template — the snapshot is the pinned contract); for each question key
  present in `answers_json`: `{linkId: key, text: <question label from
  snapshot>, answer: [<one answer object>]}` — answer typing: bool →
  `valueBoolean`; int/float → `valueDecimal`; choice → `valueString`
  (the stored choice value); free text → `valueString`;
  attachment answers (`{"attachment_id": ...}`) → SKIP the question
  entirely (PHI restraint, no binary). Guard everything — malformed
  answers must yield an omitted item, never an exception.

### 3.9 AdverseEvent ← health.incident

- **R4 AdverseEvent.subject is mandatory (1..1)** →
  `base_domain`: `[('client_id', '!=', False)]` — staff-only incidents
  are NOT exposed on the facade. State this in a code comment.
- `search_params`: `patient`, `date`
  (`date_param_domain('incident_datetime')`), `severity` (token →
  `('severity', '=', value)` accepting the raw 1–5 code).
- Mapping: `actuality`: near_miss→`potential`, all other types→`actual`;
  `event` → CodeableConcept `{coding: [{system:
  urn:health19:incident-types, code: incident_type}], text: <selection
  label>}`; subject → Patient; date = incident_datetime;
  detected = incident_datetime; recordedDate = reported_datetime;
  severity → CodeableConcept system
  `http://terminology.hl7.org/CodeSystem/adverse-event-severity`, code:
  severity 1-2→`mild`, 3→`moderate`, 4-5→`severe`;
  recorder → `{display: reporter_id.name}`; encounter per binding
  decision 3 (from `order_id`).
  Do NOT export description/investigation_notes/root_cause/
  contributing_factors/immediate_actions (PHI narrative — restraint
  rule) — the facade exposes the event's facts, not the narrative.

### 3.10 Flag ← health.fall.risk

- FIRST inspect the model (search `health.fall.risk` under
  addons/health_base or the clinical module) for exact field names —
  expect: client/patient m2o, assessment date, Morse total score, a
  risk-level selection with a high band. Adapt the names below.
- `base_domain`: assessments in the model's HIGH risk band only.
- `search_params`: `patient`, `status` is computed (see below) so do NOT
  offer it as a search param.
- Mapping: status: `active` if this record is the patient's most recent
  fall-risk assessment (`search_count` newer-for-same-patient == 0),
  else `inactive`; category → CodeableConcept
  (`http://terminology.hl7.org/CodeSystem/flag-category`, code
  `clinical`); code → CodeableConcept `{coding: [{system:
  urn:health19:flag-types, code: 'falls-risk'}], text: 'High falls risk
  (Morse <score>)'}`; subject → Patient; period.start = assessment date.
- `patient_ids_of` accordingly.

### 3.11 Consent ← health.consent

- `base_domain`: `[('state', '!=', 'draft')]` (drafts are not evidence).
- `search_params`: `patient`, `status` (token: active→active;
  `inactive` → domain `('state', 'in', ['withdrawn', 'expired'])`).
- Mapping: status: active→`active`, withdrawn→`inactive`,
  expired→`inactive`; scope → CodeableConcept
  (`http://terminology.hl7.org/CodeSystem/consentscope`): service &
  emergency_treatment→`treatment`, data_sharing & photography &
  marketing→`patient-privacy`; category → `[CodeableConcept {coding:
  [{system: urn:health19:consent-types, code: consent_type}]}]`;
  patient → Patient ref; dateTime = effective_date (as date-time — use
  the existing date→instant convention from Phase 1 or emit as
  `provision.period` only; VERIFY `fhir.resources` validation accepts a
  plain date for dateTime — if not, convert to midnight UTC instant);
  performer → `[{display: verbal_witness_id.name}]` or grantor
  `granted_by_partner_id.name` when not self_granted;
  `provision {period: {start: effective_date, end: expiry_date}}`;
  when scope_note set add `provision.purpose`? NO — put it in
  `provision` as nothing standard fits; instead emit extensionless
  narrative: skip scope_note (restraint rule).
  sourceAttachment: metadata ONLY when evidence exists —
  `{contentType: 'image/png', title: 'digital signature'}` for
  digital_signature method; omit data.

## 4. Files to touch

```
health_fhir_core/
├── __manifest__.py            # depends += 6 spine modules; version bump
├── serializers/__init__.py    # register 11 new serializer instances
├── serializers/observation.py         (new)
├── serializers/careplan.py            (new — CarePlan + Goal + Task classes OK in one file)
├── serializers/medication.py          (new — MedicationRequest + MedicationAdministration)
├── serializers/questionnaire.py       (new — Questionnaire + QuestionnaireResponse)
├── serializers/adverse_event.py       (new — AdverseEvent + Flag)
├── serializers/consent.py             (new)
└── tests/test_fhir_phase2.py          (new — see §5)
```

capability.py, controllers/fhir.py, security: NO changes needed (registry-
driven). If capability.py hardcodes anything resource-specific, fix it to
stay registry-driven rather than special-casing.

## 5. Tests (tests/test_fhir_phase2.py)

Mirror `test_fhir_core.py` structure exactly: `TransactionCase`,
`@tagged('post_install', '-at_install')`, direct serializer calls (no
HTTP), `validate_resource()` on every emitted dict.

Fixtures (search-first-create-fallback; see conventions §6):
- Patient partner (requires `catchment_province_id`), facility, FSO in an
  Encounter-qualifying state (`facility_id + patient_id +
  scheduled_datetime` required).
- Observation: use
  `env['health.observation'].create_coded(patient.id, '8867-4', 72)`
  (heart rate) — the interface exists precisely for this. For the panel
  test use `create_panel` with BP systolic/diastolic (LOINC 8480-6 /
  8462-4) and assert `component[]` has 2 entries.
- CarePlan/Goal/Activity/Task: create a plan with one goal
  (vitals_type via `env['health.vitals.type'].get_by_code('hr')`) and
  one every_visit activity; confirming/activating compiles tasks on the
  FSO (activation requires ≥1 goal). Check the health_careplan tests for
  the exact activation calls.
- MedicationRequest/Administration: create a `health.medication` +
  order. GOTCHAS: the table has a `date_check` constraint
  (end_date ≥ start_date); activation requires
  dose_quantity/dose_unit/route/frequency/start_date, runs an
  interaction check, and uses a separate-cursor persistence path — in
  tests, prefer creating the order and writing state directly OR follow
  the exact pattern used in health_emar's own tests (read them first).
  Administration: create with planned_datetime, then mark given —
  planned rows must NOT appear in `search_records` (assert that).
- Questionnaire/Response: `search` for the seeded published PAIN
  template (`code='PAIN', state='published'`); create an instance,
  answer, complete it (see health_forms tests for the completion call).
- AdverseEvent: incident WITH client_id; also create one staff-only
  incident (no client) and assert it is EXCLUDED from search.
- Flag: create a high-band fall-risk record; assert status `active`;
  create a newer low/medium one for the same patient? — no: create a
  newer HIGH one and assert the older flips to `inactive`.
- Consent: create + grant (verbal auto-defaults the witness) and assert
  status `active`; withdrawn asserts `inactive`. Remember consent
  evidence-lock: never write locked fields post-grant in fixtures.
- Capability: assert `build_capability(env)` now lists **19** resources
  including all 11 new ones with their search params.
- Reference integrity: for one Observation linked to a draft FSO, assert
  NO `encounter` key is emitted.

## 6. Deploy & verify (conventions §2)

- Deploy `health_fhir_core` only. Upgrade command tags:
  `-u health_fhir_core --test-tags /health_fhir_core` (runs Phase 1 +
  Phase 2 tests — both must be green).
- No PWA bump (no PWA-facing change). No pip installs.
- Live smoke (no token needed): `curl -s
  http://localhost:8069/fhir/r4/metadata | python3 -c "import
  sys,json; d=json.load(sys.stdin);
  print(sorted(r['type'] for r in d['rest'][0]['resource']))"`
  → must list all 19 types.
- Note in your report: OAuth clients need the new
  `system/<Resource>.read` scopes granted before external parties can
  read the new resources (admin action, not code — just state it).

## 7. Report-back extras for this phase

Besides conventions §8 item 6, explicitly report: (a) the exact field
names you found on `health.fall.risk` and `health.form.question` and how
you mapped them; (b) any place `fhir.resources` validation forced a
mapping change; (c) confirmation that Phase 1's 8 resources still
serialize (the old tests prove this — quote their result line too).
