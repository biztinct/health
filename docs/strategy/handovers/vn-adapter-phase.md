# Handover: Vietnam EMR Export — `health_fhir_adapter_base` + `health_fhir_adapter_vn`

Read `docs/strategy/HANDOVER-CONVENTIONS.md` FIRST. Definition of done is
its §8. Spec source: `docs/strategy/architecture-interop.md` §3/§3.1.
This is the Circular 13/2025 regulatory phase: a facility must be able to
produce a complete, ICD-10-coded, FHIR-R4 EMR bundle per patient before
the 31 Dec 2026 deadline — even though the national LGSP endpoints are
not yet open (transport is therefore file export, not live submission).

## 0. Scope

Two NEW modules:

**`health_fhir_adapter_base`** (small, reusable by future SG/ID/AU adapters):
1. `fhir.country.adapter` AbstractModel — the common interface:
   `transform(bundle)`, `transport(payload)`, `reconcile(receipt)`
   (interop §3), plus `adapter_code`/`adapter_name` attributes.
2. `fhir.submission.log` model — audit trail of every export/submission.

**`health_fhir_adapter_vn`**:
3. Patient EMR **Bundle builder** reusing the facade's REGISTRY
   serializers (one canonical mapping — never a second one).
4. Bundle-only **Condition** entries derived from clinical-note
   `condition_code_ids` (ICD-10 sidecar from the terminology phase).
5. **VN profile validation** — issues list (error/warning) per bundle.
6. New fields: `health.facility.moh_facility_code` (mã cơ sở KCB),
   `res.partner.vneid_verified` + `vneid_verified_date` (interop §3.1
   "capture now").
7. **Export transport**: bundle JSON saved as ir.attachment on a
   submission-log row (state `exported`) + user download.
8. **EMR-readiness report** (Circular 54 criteria checklist, §7 below).

**Non-goals (do NOT build):** live LGSP/NGSP transport, BHYT/Decision-4210
claim XML, VNPT-CA/Viettel-CA digital signature, VNeID OIDC login,
SG/ID/AU adapters, outbox event consumption (no live transport to feed —
the AbstractModel interface is enough for now), FHIR Condition as a
searchable facade resource (bundle-only), PWA changes (⇒ **no PWA bump**).

**Screen impact (small, backend-only):** facility form gains one field,
partner form gains the VNeID pair, patient form/action gets an "Export
EMR Bundle" button + a submission-log menu. No workflow changes.

## 1. `health_fhir_adapter_base`

### 1.1 `fhir.country.adapter` (AbstractModel)

```python
class FhirCountryAdapter(models.AbstractModel):
    _name = 'fhir.country.adapter'
    _description = 'FHIR Country Adapter (interface)'
    adapter_code = None   # e.g. 'vn'
    adapter_name = None

    def transform(self, bundle):   # canonical Bundle dict -> national payload
        raise NotImplementedError()
    def transport(self, payload):  # submit / export, returns receipt dict
        raise NotImplementedError()
    def reconcile(self, receipt):  # map ack/error back onto the log row
        raise NotImplementedError()
```

### 1.2 `fhir.submission.log`

mail.thread. Fields: `name` (sequence `fhir.submission.log`, prefix SUB),
`adapter_code` (Char, required, index), `patient_id` (m2o res.partner,
required, index, ondelete='restrict'), `bundle_sha256` (Char),
`entry_count` (Integer), `state` (draft/exported/submitted/acked/error,
default draft, tracking), `receipt_ref` (Char), `issue_text` (Text —
profile-validation output), `error_text` (Text), `attachment_id` (m2o
ir.attachment, ondelete='set null'), `exported_by_id` (m2o res.users),
`exported_at` (Datetime), `company_id`,
`catchment_province_id` (computed from patient, stored — conventions §4
catchment rule pair applies).

Guards (conventions §5.4 — unconditional, no su escape): rows are audit
evidence — `unlink` allowed only in `draft`; once past draft, only
`state`, `receipt_ref`, `error_text` remain writable (evidence-lock list
pattern from health_consent).

ACL: read nurse+, create/write operations_manager/manager/admin,
unlink owner-only. Menu: under the Health backoffice/reporting menu tree
(inspect where api.audit.log or the incident register menu sits; match).

## 2. VN Bundle builder (`health_fhir_adapter_vn`)

Model `fhir.adapter.vn` inheriting `fhir.country.adapter`
(`_name = 'fhir.adapter.vn'`, `_inherit = 'fhir.country.adapter'`,
`adapter_code = 'vn'`).

### 2.1 `build_patient_bundle(patient)` → dict

- Bundle: `{'resourceType': 'Bundle', 'type': 'collection',
  'timestamp': <now as fhir instant>, 'entry': [...]}` — each entry
  `{'fullUrl': 'urn:health19:<Type>/<id>', 'resource': <dict>}`.
- For each of these facade resource types, collect the patient's records
  with `serializer = REGISTRY[<Type>]`, domain =
  `serializer.base_domain(env) + [(<patient field>, '=', patient.id)]`,
  then `serializer.serialize_batch(records)`: Patient (the patient
  itself via `read_record`), Encounter, Observation, CarePlan, Goal
  (via careplan), MedicationRequest, MedicationAdministration,
  QuestionnaireResponse, AdverseEvent, Flag, Consent, DocumentReference.
  Inspect each serializer's patient search-param domain and reuse the
  same field paths — do NOT guess.
- **Condition entries (bundle-only, ad-hoc)**: for each
  `health.clinical.note` of the patient with `condition_code_ids`, one
  Condition per (note, code):
  `{'resourceType': 'Condition', 'id': 'cond-<note.id>-<code.id>',
  'clinicalStatus': {coding hl7 condition-clinical 'active'},
  'code': {'coding': [{'system': 'http://hl7.org/fhir/sid/icd-10',
  'code': code.code, 'display': code.display}],
  'text': code.display_vi or code.display},
  'subject': Patient ref, 'recordedDate': <note date field — inspect
  the model>}` + encounter ref when the note's FSO qualifies (reuse
  `fso_common.encounter_ref_if_qualifies`). Every Condition must pass
  `validate_resource`.
- Deterministic ordering (stable sha256): sort entries by (resourceType,
  int id where numeric).
- `bundle_sha256` = sha256 of the canonical JSON
  (`json.dumps(bundle, sort_keys=True, ensure_ascii=False)`).

### 2.2 `validate_vn_profile(bundle, patient)` → list[dict]

Each issue: `{'severity': 'error'|'warning', 'code': <short>,
'message': <vi-friendly English>}`. Checks (VN profile pack, interop
§3.1):
- error `patient-no-national-id`: patient has neither `national_id` nor
  `cccd_number` (both are PHI-encrypted computes — plain ORM reads,
  never SQL).
- error `facility-no-moh-code`: the patient's `primary_facility_id` has
  no `moh_facility_code`.
- warning `encounter-uncoded-diagnosis`: patient has clinical notes but
  zero Condition entries (coding-density KPI, spec §2.3).
- warning `no-consent-on-file`: no active `service` consent
  (`env['health.consent'].check_consent(patient, 'service')` — pass
  context `consent_check_source='fhir_vn_export'`).
Errors do NOT block export (the log records them; a facility must see
its gaps) — but they set the log's `issue_text` and are shown in the
result dialog.

### 2.3 Export action (`transport`)

- Server action / button "Export EMR Bundle (VN)" on the patient form
  (groups: operations_manager+). Flow: build bundle → validate profile →
  create `fhir.submission.log` (state `exported`, sha, entry_count,
  issues) → attach the JSON (`ir.attachment`, name
  `emr_vn_<patient_id>_<log name>.json`, res_model the log) → return an
  action opening the log form (download via the attachment).
- PHI note: the JSON contains full PHI by design; access rides the log's
  ACL/catchment rules. Do not put bundles anywhere else.
- `transform(bundle)` for VN phase A is identity (canonical FHIR IS the
  payload); `reconcile(receipt)` marks state per receipt dict — trivial
  implementations, tested, ready for the LGSP day.

## 3. New fields + view inherits

- `health.facility.moh_facility_code`: Char, string "MOH Facility Code
  (mã cơ sở KCB)", help mentions Circular 54/LGSP; form view inherit
  next to `health_license_number` (health_base facility form — inspect).
- `res.partner.vneid_verified` (Boolean) + `vneid_verified_date` (Date):
  partner form inherit in the patient/healthcare tab area (inspect where
  national_id/cccd sit; place adjacent). Readonly-date behaviour: when
  `vneid_verified` toggles True and no date set, default today
  (onchange + create/write server-side mirror per conventions §5.2).

## 4. EMR-readiness report (Circular 54 checklist)

Wizard `vn.emr.readiness` (TransientModel) + QWeb report or HTML field
dialog (pick the simpler; no new report engine). It renders a FIXED
checklist — use EXACTLY these rows and statuses (do not invent
compliance claims):

| Criterion (Circular 54 area) | health19 evidence | Status |
|---|---|---|
| User authentication & role-based access | Odoo auth + healthcare group ladder + record rules | met |
| Audit trail of clinical data access | api.audit.log (append-only) + mail tracking | met |
| Structured EMR content (vitals, meds, care plans, forms) | clinical spine 7/7 modules | met |
| ICD-10 coded diagnoses | health_fhir_terminology sidecar | met (coding density depends on usage) |
| Interoperability / HIS interface readiness | FHIR R4 facade, 20 resources + terminology ops | met |
| EMR export (hồ sơ bệnh án điện tử) | this module's patient bundle export | met |
| PHI protection at rest | health_phi_encryption (AES-GCM field level) | met |
| Patient identity (CCCD/VNeID linkage) | national_id/cccd + vneid_verified capture | partial (VNeID OIDC not integrated) |
| Digital signature on clinical documents | consent digital signature only | gap (VNPT-CA/Viettel-CA integration planned) |
| BHYT claims interface (Decision 4210 XML) | — | gap (planned adapter phase) |
| Backup & retention procedures | server ops (outside application scope) | operational — evidence per deployment |

Report shows per-facility `moh_facility_code` presence and a live coding
-density number (% of clinical notes with ≥1 condition code, last 90
days) — computed, not hardcoded.

## 5. Security, i18n, plumbing

- Depends: base module → `health_fhir_core`, `mail`; VN module →
  `health_fhir_adapter_base`, `health_fhir_terminology`,
  `health_consent`, `health_fieldservice`.
- vi.po for both modules (menus, field strings, report rows, issue
  messages).
- Sequence data (noupdate) for the log. Catchment rule pair on the log.
- No PWA files. No pip installs (hashlib/json are stdlib).

## 6. Tests

`health_fhir_adapter_vn/tests/test_vn_adapter.py` (+ a small base-module
test for the log guards). Conventions §6 fixtures. Cases:

1. Bundle builder: fixture patient with ≥1 qualifying FSO, 1 observation
   (`create_coded`), 1 granted consent, 1 clinical note with 2
   condition codes → bundle contains Patient + those entry types;
   2 Condition entries with ids `cond-<note>-<code>`; every entry passes
   `validate_resource`; entries deterministically ordered (build twice,
   same sha256).
2. Profile validation: patient without national_id/cccd → error present;
   facility without moh_facility_code → error; after setting
   `moh_facility_code` the error disappears.
3. Export action: creates log (state exported, sha256 + entry_count set,
   attachment JSON parses back to the same sha), issues recorded.
4. Log guards: unlink non-draft raises (superuser included); writing a
   locked field post-draft raises; state/receipt writes allowed.
5. Readiness wizard: renders; coding-density figure matches fixture
   (e.g. 1 coded of 2 notes → 50%).
6. VNeID mirror: create partner with vneid_verified=True and no date →
   date defaults (create path, not just onchange).

## 7. Deploy & verify

- `-i health_fhir_adapter_base,health_fhir_adapter_vn --test-tags
  /health_fhir_adapter_base,/health_fhir_adapter_vn` (also re-run
  `/health_fhir_core,/health_fhir_terminology` tags to prove the facade
  is untouched).
- Live verify: open a patient in the backend, run Export EMR Bundle,
  confirm the log + attachment exist and the JSON's `entry` count > 0
  (use an existing demo patient; note which one in the report).
- Login 200; conventions §8 throughout.

## 8. Report-back extras

(a) exact clinical-note date field used for Condition.recordedDate;
(b) the demo patient used for live verification + entry counts by type;
(c) any facade serializer whose patient-domain field path differed from
its search param (list them); (d) confirmation all four FHIR test tags
are green (quote the result lines).
