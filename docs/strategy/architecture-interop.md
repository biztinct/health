# Interoperability & Architecture Strategy

**Section: Interop, Standards & Platform Architecture — health19 (Odoo 19 CE)**

> Current state (from audit): **zero** FHIR/HL7/SNOMED/ICD/LOINC/DICOM support. The only API surface is the PWA-scoped REST controller (`health_pwa/controllers/api.py`, ~2,300 lines, session-auth, no OpenAPI/versioning/keys/rate limits). Clinical data is largely free-text (`health.clinical.note`), and integrations (Viettel SInvoice, MISA, Zalo, VoIP24h) are point-to-point. This section defines the canonical interoperability layer that turns health19 from a Vietnamese home-care app into an ASEAN-grade, standards-native care platform — without rewriting the Odoo core.

**Design thesis:** one **canonical FHIR R4 layer** inside the platform; every country integration (VN MOH, VSS/BHXH, Singapore NEHR, Indonesia SATUSEHAT, Australia MHR/NDIS) is a thin **adapter** that transforms canonical FHIR → national profile + transport. New clinical models (care plans, vitals, eMAR — recommended elsewhere in this report) are **born-FHIR**: their Odoo schema is designed from the FHIR resource inward, so serialization is trivial and lossless.

---

## 1. FHIR R4 Gateway with Country Adapters

### 1.1 Canonical resource mapping (existing + planned models)

The facade never exposes Odoo IDs semantics directly; each mapped record gets a stable FHIR `id` (Odoo id) plus `identifier[]` entries (internal ref, national ID/VNeID, insurance number). All mappings live in one place: a **serializer registry** (`health_fhir_core/serializers/`), one class per resource.

| Odoo model / field source | FHIR R4 resource(s) | Mapping notes |
|---|---|---|
| `res.partner` (client, `health.patient.category`, `primary_facility_id`) | **Patient** | name (vi diacritics preserved), telecom (phone/Zalo as `ContactPoint` with `system=other`, `use` extension), address w/ `health.province`/catchment → `address.district/state`, `generalPractitioner` → assigned staff, `managingOrganization` → facility. National ID/VNeID/BHYT card as `identifier[]` with proper `system` URIs (e.g. `https://vneid.gov.vn/id`). |
| `health.client.relation` (kinship: caregiver/payer/referrer/guardian) | **RelatedPerson** (+ `Patient.contact`) | `relationship` coded with HL7 v3 RoleCode (GUARD, ECON, etc.); payer relations additionally surface on Account/Coverage (below). Keeps the existing D3 relationship graph as the UI; FHIR is the export shape. |
| `health.fieldservice.order` (FSO) | **Encounter** + **ServiceRequest** + **Appointment** | One FSO ⇒ three linked resources: `Appointment` (planned slot; status map: draft→proposed, confirmed→booked, cancelled→cancelled), `Encounter` (actual visit; assigned→planned, in_progress→in-progress, completed/closed→finished; `class=HH` home health from v3 ActCode), `ServiceRequest` (the order itself; service lines → `ServiceRequest.code` + `orderDetail`). Check-in/out GPS timestamps → `Encounter.period` + a `geolocation` extension on `Encounter.location`. Recurring flag → `Appointment.recurrenceTemplate` (R5 backport as extension) or a series `basedOn` chain. |
| `health.clinical.note` (+ FSO clinical notes, photos) | **Observation** / **DocumentReference** / **Composition** | Today (free text): serialize as `DocumentReference` (note text as base64 `text/plain` or rendered PDF attachment) + a `Composition` per visit bundling all notes/photos of that Encounter. Phase 2: structured fields (vitals, wound stage, injection counts) split out as coded `Observation`s while the narrative stays in `Composition.section.text`. Photos → `DocumentReference` w/ `content.attachment` (or `Media`/`DocumentReference` per profile). |
| `health.service.package` / `health.prepaid.service` (visit countdown), `health.insurance.provider`, payer relations | **Coverage** + **Account** (+ **ChargeItem**/**Invoice**) | Package = `Coverage` (`type` = self-pay/private/corporate/government; `costToBeneficiary` for copay) linked to an `Account` per client; remaining-visit countdown → `Coverage.extension[remaining-units]`. `health.payment.transaction` + Odoo invoices → FHIR `Invoice`/`PaymentReconciliation` for payer-facing exports (NDIS, BHYT claims later). |
| `health.staff.assignment` (+ skills matrix `health.staff.skill`) | **PractitionerRole** | Links Practitioner↔Organization↔Location↔specialty (`health.medical.specialty` → `PractitionerRole.specialty`); availability matrix → `PractitionerRole.availability`; assignment on an FSO → `Encounter.participant` + `Appointment.participant`. |
| `hr.employee` (via `healthcare_facility_id`) | **Practitioner** | `qualification[]` from skills/certs; CCHN practising-licence number (VN) as `identifier` with system `https://moh.gov.vn/cchn`. Keep `Practitioner` free of employment data (that stays in PractitionerRole). |
| `health.facility` (+ catchment/province/timezone) | **Location** + **Organization** | `Organization` = legal entity (multi-company aware); `Location` = physical site w/ `position` (lat/lng), timezone extension, `partOf` chains for rooms later. Catchment provinces → `Location.extension[catchment-area]` referencing an administrative-area ValueSet. |
| `health.appointment` (clinic bookings) | **Appointment** + **Slot**/**Schedule** | The roster/staff-schedule timeline (action 1536) becomes the source of `Schedule` + `Slot` — this is what later powers portal self-booking against FHIR `Slot` search. |
| `health.medication`, `health.medication.safety` (RxNorm/OpenFDA) | **Medication** + **DetectedIssue** | Existing RxNorm codes drop straight into `Medication.code` (`system=http://www.nlm.nih.gov/research/umls/rxnorm`); interaction-check results → `DetectedIssue`. |
| `health.fall.risk` (Morse) | **Observation** (panel) + **RiskAssessment** | Morse total → `RiskAssessment.prediction`; the six Morse items → member `Observation`s with LOINC 59461-4 et al. First proof that a scored assessment round-trips cleanly. |
| **Future: care plan model** | **CarePlan** + **Goal** + **Task** | Design the new model born-FHIR: `careplan.activity` rows ARE `CarePlan.activity`; goals table = `Goal` (target `Observation` codes + due dates); per-visit tasks pushed to PWA = FHIR `Task`. `health.clinical.protocol` (JSON action steps) becomes `PlanDefinition`, instantiated via `$apply` semantics. |
| **Future: structured vitals** | **Observation** (LOINC-coded) | One row = one Observation: code (LOINC), value+UCUM unit, effectiveDateTime, performer, device. Use the FHIR **vital-signs profile** codes verbatim (§2.3) so the Odoo model needs no translation layer. |
| **Future: medications/eMAR** | **MedicationRequest** + **MedicationAdministration** + **MedicationStatement** | Order = MedicationRequest (dosage as structured `Dosage`, not text); each PWA administration tick = MedicationAdministration (status: completed/not-done + `statusReason` for refusals — an aged-care audit requirement). |
| **Future: incidents** | **AdverseEvent** + **Flag** | Incident model → AdverseEvent; standing alerts (falls risk, infection, DNR) → `Flag` on Patient — this is what NEHR/SATUSEHAT expect for alerts. |
| `health.portable.equipment` | **Device** | Equipment issued to client → `Device` + `DeviceUseStatement`. |

### 1.2 Gateway architecture

```
                     ┌──────────────────────────────────────────────┐
  EHR / payer /      │  API GATEWAY  (edge: Traefik or Kong, §4)    │
  national platform ─►  /api/v1/*  (business REST)                  │
                     │  /fhir/r4/* (FHIR facade)                    │
                     └───────┬──────────────────────────────────────┘
                             │ OAuth2 / API key / SMART scopes
                 ┌───────────▼───────────┐        ┌────────────────────┐
                 │ health_fhir_core      │        │ health_api_gateway │
                 │ (Odoo addon)          │        │ (OpenAPI, keys,    │
                 │ · FHIR controllers    │        │  webhooks, audit)  │
                 │ · serializer registry │        └────────────────────┘
                 │ · search-param mapper │
                 │ · validation (fhir.   │   outbox events (§6.1)
                 │   resources pydantic) │◄──────────────────────────┐
                 └───────────┬───────────┘                           │
        ┌────────────────────┼──────────────────────┐        ┌──────┴───────┐
        ▼                    ▼                      ▼        │ Odoo models  │
 health_fhir_terminology  country adapters      $export bulk │ (FSO, notes, │
 (§2: SNOMED/ICD/LOINC)   vn / sg / id / au     (ndjson jobs)│  vitals…)    │
                          (§3)                               └──────────────┘
```

**Implementation choices (Odoo 19 CE-aware):**

- **In-process facade, not a sidecar.** Build `health_fhir_core` as an Odoo addon with `http.Controller` routes at `/fhir/r4/<resource>`. Rationale: record rules, `access_roles` field/record security, and multi-company scoping already live in the ORM — a sidecar (HAPI FHIR JPA, etc.) would need to re-implement all of it. A standalone HAPI server remains an option later purely as a *validation/terminology* utility, never as the source of truth.
- **Library: `fhir.resources` (pydantic v2, R4B)** for parse/validate/serialize of every payload — construct `fhir.resources.patient.Patient(...)` in serializers; `model_validate()` inbound. Add `fhirpathpy` for search-parameter evaluation on complex params, and `fhir-py` (client) inside country adapters for outbound calls.
- **Capabilities**: implement `GET /fhir/r4/metadata` (CapabilityStatement generated from the serializer registry — resources, interactions, search params it actually supports), read/vread, search with `_lastUpdated`, `_count`+cursor paging (map to ORM `search()` with `write_date`), `_include`/`_revinclude` for the core graph (Patient→Encounter→Observation), batch/transaction `Bundle` POST (Phase 3 for writes).
- **Search params**: a declarative table per resource → ORM domain, e.g. `Patient.birthdate → partner.dob`, `Encounter.date → fso.scheduled_date`, `Encounter.patient → fso.partner_id`. Reject unsupported params with `OperationOutcome` (strict handling) rather than silently ignoring — national platforms test for this.
- **Writes**: Phase 1 is read-only (`GET` only + `$export`). Phase 3 enables conditional create/update for a whitelist (Patient demographics, Appointment booking, DocumentReference inbound referrals) routed through the same wizards/constraints as the UI (call model methods, never `sudo().write()` raw).
- **Subscriptions/webhooks**: implement FHIR R4B **Subscriptions backport** (topic-based): `SubscriptionTopic`s for `encounter-complete`, `patient-updated`, `observation-created`, `careplan-updated`. Storage = `fhir.subscription` model; delivery = rest-hook channel with HMAC-SHA256 signature header, retries w/ exponential backoff via job queue (§6.2), driven off the transactional outbox (§6.1) so no event is lost to a rollback. The same machinery powers plain business webhooks in §4.
- **Bulk export `$export`**: system-level and `Group/$export` (a Group = a facility's clients or a payer cohort). Async pattern per the FHIR Bulk Data spec: `202 Accepted` + polling location; background job streams **NDJSON** files per resource type to an `ir.attachment`-backed (or S3-backed) staging area; expire after 24 h. This single feature covers: NEHR batch submission, SATUSEHAT backfill, payer data feeds, *and* becomes a better ingestion path for `biz_bi`'s silver layer than direct SQL.
- **SMART on FHIR direction**: expose the gateway as a SMART-capable server incrementally — Phase 1 ships OAuth2 **client-credentials** with SMART *backend services* (RFC 7523 JWT client assertion, `system/*.read` scopes) because that's what B2G and partner integrations need first; Phase 3 adds the EHR-launch/standalone-launch flows (`launch/patient` context, `patient/*.read` scopes) so third-party SMART apps (e.g., a med-review app, a telehealth widget) can launch inside the workspace shell with patient context. Use **`authlib`** for the OAuth2/OIDC server pieces on top of Odoo's auth; publish `/.well-known/smart-configuration`.

---

## 2. Terminology Service

### 2.1 Architecture: local-first, server-optional

Ship a small terminology addon (`health_fhir_terminology`) with two layers:

1. **Local code tables** (Odoo models): `medical.coding.system` (URI, version) and `medical.code` (system_id, code, display, display_vi, parent_id, is_active, synonyms). Bulk-loaded from release files via CLI importers. This covers 95 % of runtime needs (picklists, validation, display) with zero external dependency — important for offline PWA and data-sovereignty deployments.
2. **Optional external terminology server** behind the FHIR `$validate-code` / `$expand` / `$lookup` operations: **Snowstorm** (SNOMED International's open-source server, Elasticsearch-based) for full SNOMED ECL queries, or CSIRO **Ontoserver** where commercially licensed (it's the AU national terminology server — useful for the Australia adapter). The facade proxies `/fhir/r4/CodeSystem/$lookup` etc. to whichever backend is configured, defaulting to local tables.

### 2.2 Code systems and how each is used

| System | Scope in health19 | Licensing / local reality |
|---|---|---|
| **ICD-10** | Diagnoses on Encounter/Condition; **the primary system for Vietnam** — MOH mandates ICD-10 coding in medical records and BHXH (social insurance) claims use ICD-10. Load the **Vietnamese MOH ICD-10 translation** (published by MOH/KCB portal) into `medical.code.display_vi` alongside WHO English. | WHO ICD-10 freely usable; VN translation is public-sector. Plan ICD-11 as a second version row, not a migration. |
| **SNOMED CT** | Problem list, procedures, wound/skin findings, allergies — the *interlingua* for SG/AU exports. | Member-country licensing: Singapore, Australia, Indonesia, Malaysia are SNOMED members; **Vietnam is not** — so SNOMED is optional per deployment, and VN installs run ICD-10 + local codes only. Store SNOMED as *additional* codings, never the sole code, so a VN record remains valid without it. |
| **LOINC** | All structured vitals and future labs. Hard-code the vital-signs core: 85354-9 BP panel (8480-6 systolic / 8462-4 diastolic), 8867-4 heart rate, 9279-1 resp rate, 8310-5 body temp, 2708-6/59408-5 SpO₂, 29463-7 weight, 8302-2 height, 39156-5 BMI, 15074-8 glucose. | Free (Regenstrief licence, registration only). Also used by SATUSEHAT and NEHR for labs. |
| **RxNorm** | Already in `health.medication.safety` for interaction checks — promote it to the canonical `Medication.code`. | Free (NLM). |
| **VN drug registry (DAV)** | Map RxNorm ↔ Vietnam Drug Administration visa/registration numbers (`số đăng ký`) via a crosswalk table on `health.medication` (`dav_reg_no` field) — required for VN e-prescription (Decision 4210 / national prescription database formats) and for printing compliant labels. | Public registry data. Same pattern later for IDN (BPOM) and SG (HSA). |
| **UCUM** | Units on every Observation value (`mm[Hg]`, `Cel`, `kg`, `/min`). | Free. |
| **HL7 v3 / FHIR core vocab** | Encounter class, RoleCode relationships, Appointment status, marital status, etc. | Free, ships with `fhir.resources`. |

### 2.3 Adding codes without disrupting current text fields

Non-destructive **"coding sidecar"** pattern, applied uniformly:

- Never remove or repurpose an existing text field. Add parallel coded fields: e.g. on `health.clinical.note` add `condition_code_ids` (m2m → `medical.code`), on the future vitals model the code IS the row type; on FSO add `service_code_id` mapping service products → a local `health-service` CodeSystem (published at `/fhir/r4/CodeSystem/health19-services`) with optional SNOMED procedure mappings.
- **AI-assisted retro-coding**: reuse the existing multi-provider AI framework (`hr_development_ai/ai_providers/provider_factory.py`) to suggest ICD-10/SNOMED codes from free-text notes — suggestions land in a review queue (`suggested_code_ids` + confirm action), never auto-committed. Runs on Ollama locally for data-sovereignty deployments. This converts years of legacy narrative into coded data without forcing nurses to change how they write today.
- UI: coded pickers are typeahead widgets over `medical.code` (Vietnamese display first, English secondary), added to the VU form engine as a reusable field widget so every module gets the same component.
- Serializers emit `CodeableConcept` with `text` = original free text and zero-or-more `coding[]` — so an uncoded legacy record is still a *valid* FHIR resource, and coding density becomes a measurable quality KPI (a `biz_bi` gold dataset: % encounters with coded diagnosis, per facility).

---

## 3. Country Adapters

**Pattern:** every adapter is an addon `health_fhir_adapter_<cc>` implementing a common interface:

```python
class CountryAdapter(models.AbstractModel):
    _name = "fhir.country.adapter"
    def transform(self, bundle):   # canonical FHIR Bundle -> national payload
    def transport(self, payload):  # auth + protocol + submit, returns receipt
    def reconcile(self, receipt):  # ack/error mapping back onto source records
```

Adapters consume **outbox events** (§6.1), pull the canonical Bundle from the facade internally (same serializers, no second mapping), transform, submit, and write a `fhir.submission.log` row (status, national receipt ID, error payload) chatter-linked to the source FSO/patient. Retries and dead-letter via the job queue.

### 3.1 Vietnam (`health_fhir_adapter_vn`) — first and deepest

- **Regulatory anchors:** Circular **46/2018/TT-BYT** (legal basis for EMR — bệnh án điện tử — replacing paper records, security/backup/retention requirements) and Circular **54/2017/TT-BYT** (IT maturity criteria for health facilities, 7 levels + "advanced"; EMR capability is graded within it). Target: ship an **"EMR-readiness pack"** — a compliance checklist report mapping health19 features to Circular 54 criteria levels (audit trail, user auth, backup, HIS/LIS/RIS interfaces, digital signature) so VietUc and future VN customers can self-assess and evidence level attainment. Digital-signature requirement → integrate VNPT-CA / Viettel-CA USB-token or remote signing for note finalization (same vendor relationship pattern as the existing **Viettel SInvoice** integration).
- **Insurance/claims (BHXH/VSS):** the giám định BHYT gateway consumes **XML per Decision 4210/QĐ-BYT** (checkout-time claim tables: XML1 demographics, XML2 drugs, XML3 services…), not FHIR. The VN adapter therefore has a second transform target: canonical Bundle → 4210 XML. Mostly relevant when clinic services bill BHYT; home-care private-pay flows are unaffected. Build as `transform_bhyt()` alongside `transform_fhir()`.
- **LGSP / national data direction:** MOH's stated direction is national health data exchange over the NGSP/LGSP government service bus with provincial DOH nodes, and FHIR-based pilots for the national EHR (hồ sơ sức khỏe điện tử). Concretely: keep transport pluggable (SOAP-over-LGSP vs REST) and ship a **VN FHIR profile pack** (StructureDefinitions constraining Patient to require national ID, Encounter to require facility MOH code `mã cơ sở KCB`) so we're submission-ready the day provincial endpoints open. Sales angle: almost no home-care competitor in VN can say "LGSP-ready".
- **VNeID:** national digital identity is being wired into health (insurance card in VNeID, identity-verified check-in). Adapter reserves `identifier` slot + a portal login direction: "Login with VNeID" (OIDC) for the future patient portal — capture `vneid_verified` on `res.partner` now (Boolean + verification date) so records are ready.
- **Precedent to reuse:** `health_redinvoice` (Viettel SInvoice — note the `/services/einvoiceapplication/api/` Basic-Auth pattern) and MISA sync fields prove the org already runs B2G/vendor integrations; lift its credential-config + submission-log UX as the template for `fhir.submission.log`.

### 3.2 Singapore (`health_fhir_adapter_sg`)

- **NEHR (Synapxe):** contribution to the National Electronic Health Record is done by onboarded systems via Synapxe's integration gateways; historically CDA/HL7-v2 event-based submission, with FHIR-based APIs expanding (HealthX/Synapxe FHIR direction). Practically for a community/home-care provider: submit **encounter summaries, medications, alerts/allergies, and discharge-style documents**. Adapter output: canonical Bundle → NEHR submission package (start with Composition/DocumentReference-shaped summary; conform to Synapxe onboarding spec once in the vendor program). Mandatory prerequisite work: **Healthcare Services Act (HCSA) licensing categories** and **Cyber & Data Security Guidelines** — feeds the compliance section; interop-relevant piece is the audit-log completeness (§4) and PHI encryption (§6.5).
- **Identity:** NRIC/FIN as `identifier` (system `http://ns.electronichealth.sg/id/nric` style URI), Singpass/Corppass OIDC for portal login = same pluggable-OIDC slot as VNeID.

### 3.3 Indonesia (`health_fhir_adapter_id`) — the ASEAN reference implementation

- **SATUSEHAT** (Kemenkes) is a **native FHIR R4 platform**: OAuth2 client-credentials, mandated resource flows (Patient lookup by NIK → Encounter → Condition w/ ICD-10 → Observation w/ LOINC → MedicationRequest), sandbox + production onboarding, and regulatory mandate for facilities to report. This is the *easiest* adapter because it is closest to canonical: `transform()` is mostly (a) look up SATUSEHAT IHS patient/practitioner IDs (their master patient index) and swap references, (b) apply their profiles, (c) POST bundles with their OAuth2 token. **Build the ID adapter second (right after VN read-only), because passing SATUSEHAT sandbox conformance is the cheapest external proof that the canonical layer is correct** — then market "SATUSEHAT-certified" for Indonesia expansion.
- KFA (Kamus Farmasi & Alat Kesehatan) drug codes → same crosswalk table pattern as VN DAV (§2.2).

### 3.4 Australia (`health_fhir_adapter_au`)

- **My Health Record:** B2G document upload (Shared Health Summary / Event Summary as CDA today, FHIR gateway maturing) requires conformant-software registration, HPI-I/HPI-O/IHI identifiers (Healthcare Identifiers Service) and NASH PKI certificates. Adapter scope v1: generate **Event Summaries** from completed Encounters; consume via the FHIR **AU Core / AU Base profiles** (store `ihi` on partner, `hpii` on employee). Use Ontoserver for AU terminology binding (AMT for medicines instead of/alongside RxNorm — the crosswalk table absorbs this).
- **NDIS:** the NDIA **partner APIs** (Digital Partnership Program) cover participant plan/budget lookup and **bulk payment requests** — this is a *claims/billing* adapter more than clinical: map service bookings + completed FSOs → NDIS support-item codes (load the NDIS Support Catalogue as a `medical.coding.system`!) → payment request batches; reconcile remittance back onto invoices (extends `health_invoicing` AR flows).
- **My Aged Care:** B2G web-service channel for providers (referrals in, service updates out) — inbound referral → draft client + draft FSO pipeline is the flagship flow (extends `health_crm` contact-first intake).
- AU adapter is the biggest and latest; sequence after product-market entry decision.

---

## 4. Enterprise API Gateway

Two layers: an **edge gateway** and an **Odoo addon** (`health_api_gateway`) that owns identity, contracts, and audit.

- **Edge:** deploy **Traefik** (already sensible for the current single-VM UAT) or **Kong OSS/Apache APISIX** (when multi-tenant SaaS): TLS termination, IP allowlists for B2G partners, coarse rate limiting, request-size caps. Odoo CE has no built-in throttling — do not attempt rate limiting purely in Python workers.
- **AuthN/AuthZ:**
  - **API keys**: extend Odoo 19's built-in `res.users.apikeys` with a `scope` model (`api.key.scope`: e.g. `fhir.read`, `booking.write`, `webhook.manage`) and per-key expiry, facility restriction, and IP binding. Keys map to a dedicated *service user* per integration so `access_roles` record rules apply naturally.
  - **OAuth2 client credentials** (via **`authlib`**): `oauth.client` model (client_id/secret hash, allowed scopes, JWKS for SMART backend-services JWT assertion), token endpoint `/oauth/token`, access tokens as short-lived JWTs validated in a request middleware (`ir.http._authenticate` extension). SMART scopes (`system/Patient.read`) enforce per-resource access inside the FHIR facade.
- **Versioning:** everything new under `/api/v1/...`; FHIR under `/fhir/r4/...` (the FHIR version *is* the version). Deprecation policy: N-1 supported 12 months, `Sunset` + `Deprecation` headers.
- **OpenAPI 3.1 spec generation:** introduce a route decorator `@api_route(path, methods, request_schema, response_schema, scopes, summary)` wrapping `http.route`, with pydantic models as schemas; a generator walks the registry and emits `/api/v1/openapi.json` + a self-hosted Redoc/Scalar page at `/api/docs` (no CDN — bundle assets, per debranding posture). **Migrate the PWA controller incrementally**: wrap existing `/health_pwa/api/*` handlers with the decorator (schemas first, behavior untouched) so the PWA surface becomes documented, versioned (`/api/v1/pwa/...` aliases), and key-capable without breaking deployed PWAs (old paths kept as aliases until PWA version bump).
- **Webhooks (business-level):** `webhook.subscription` model (target URL, event types, secret, active, failure counter) sharing the outbox dispatcher with FHIR Subscriptions (§1.2): HMAC-SHA256 `X-Health19-Signature`, at-least-once delivery, exponential backoff (1m→1h, 24h dead-letter), replay button in UI, per-endpoint delivery log. Event catalog v1: `fso.completed`, `fso.cancelled`, `patient.created`, `invoice.posted`, `payment.received`, `assignment.changed`.
- **Audit logging:** `api.audit.log` (append-only table, no unlink ACL): timestamp, key/client id, user, route, resource type+id, action, response code, latency, source IP, and — for FHIR reads of PHI — the patient id touched (this is the NEHR/HCSA and Circular-54 audit requirement in one stroke). Partitioned by month; surfaced as a `biz_bi` dataset (API usage dashboards for free). PHI never in the log body.

---

## 5. DICOM Readiness (Pragmatic Stance)

**We are not building a PACS.** Home care + clinic imaging needs are: reference studies done elsewhere, view them, attach them to the record.

- **Store references, not pixels:** new `medical.imaging.study` model ≈ FHIR **ImagingStudy**: study/series UIDs, modality, `endpoint` (DICOMweb base URL), performed date, linked Encounter/patient. FHIR facade serves `ImagingStudy` natively.
- **DICOMweb as the only imaging protocol we speak:** QIDO-RS (query), WADO-RS (retrieve/render) against *external* PACS. No DIMSE/C-STORE listener in scope.
- **Orthanc integration option** (recommended for clinics that own a small ultrasound/X-ray): Orthanc is open-source, single-binary, with a DICOMweb plugin — deploy alongside Odoo, point modalities at it, and health19 auto-registers studies via Orthanc's REST change feed → `medical.imaging.study` rows. Python: **`pydicom`** only for metadata parsing of uploaded files (patient matching), never for storage; **`requests` + DICOMweb** (or `dicomweb-client`) for QIDO/WADO calls.
- **Viewing:** embed **OHIF viewer** (self-hosted, no CDN) launched with the study's DICOMweb URL, inside a workspace tab; PWA gets WADO-RS **rendered** JPEG frames (server-side rendered thumbnails cached as attachments for offline).
- Non-DICOM photos (wound photos from the PWA) stay as `DocumentReference`/attachments — do not force them into DICOM.

---

## 6. Broader Architecture Changes

### 6.1 Transactional outbox + event bus
Single most important plumbing change. New table `integration.outbox` (event_type, aggregate model+id, canonical payload ref, created_at, dispatched_at, status), written **in the same DB transaction** as the business change (via model hooks on the ~10 event-bearing models). A dispatcher (job-queue worker or 30 s cron with `FOR UPDATE SKIP LOCKED`) fans out to: FHIR Subscriptions, business webhooks, country adapters, and `biz_bi` incremental refresh triggers. Guarantees: no event lost to rollback, at-least-once delivery, strict per-aggregate ordering. Kafka/NATS is *not* needed at current scale — Postgres outbox first; the dispatcher interface makes a broker swap-in a Phase-3+ option for multi-region.

### 6.2 Background jobs
Adopt **OCA `queue_job`** (Odoo 19 branch) instead of ad-hoc crons: named channels (`root.fhir`, `root.adapters`, `root.export`, `root.ai`) with per-channel concurrency, retries, and a failure UI. Migrate the AI assignment engine's daily crons and any adapter submissions onto it. $export, retro-coding AI runs, and NDJSON generation are all jobs.

### 6.3 Read-model separation
`biz_bi`'s silver/gold medallion already separates analytics reads — extend it: (a) silver ingestion switches to consuming the **outbox stream + $export NDJSON** instead of wide ORM reads (cheaper, and identical shape to what external consumers get — one serialization to test); (b) add **FHIR-shaped gold datasets** (encounters, coded-diagnosis density, med administration compliance) so BI dashboards and regulatory reporting read the same numbers; (c) heavy FHIR searches (`Patient/$everything`, population queries) can be served from a read replica Postgres via a facade flag, keeping the primary for transactions.

### 6.4 Multi-region & data residency (ASEAN posture)
**Region = deployment cell**: one full stack (Odoo + Postgres + Orthanc + terminology cache) per country/regulatory zone; PHI never crosses the cell boundary. VN data stays in VN (Decree 13/2023 personal-data rules + Circular 46 retention), SG in SG (HCSA), ID in ID (SATUSEHAT expects local processing), AU in AU. What *is* shared cross-region: the codebase/modules, de-identified benchmarking aggregates (opt-in, k-anonymized, computed in-cell and exported as aggregates only), and the terminology content pipeline. Central control plane = deployment/config only (the `health_user_admin` SaaS-tenant pattern generalizes to per-cell admin). LLM calls in sovereignty-sensitive cells default to **Ollama in-cell** (framework already supports it).

### 6.5 Field-level PHI encryption
Application-layer envelope encryption for a defined field set (national IDs, insurance numbers, clinical narrative, GPS traces): Python **`cryptography`** AES-256-GCM with per-record data keys wrapped by a master key in KMS (cloud) or HashiCorp Vault/file-HSM (on-prem VN). Implement as a field mixin (`fields.Char` subclass encrypting at `convert_to_column`); searchable fields get a blind index (HMAC) column. Trade-off stated honestly: encrypted fields lose LIKE-search and SQL reporting — so scope deliberately (IDs + narrative, not codes/dates), and BI reads pseudonymized silver anyway. Plus baseline `pgcrypto`/disk encryption and encrypted backups (a Circular 54 line item).

### 6.6 Consent-aware access as a cross-cutting layer
The consent-management model (recommended in the clinical section) becomes an *enforcement* layer here: FHIR **Consent** resources per patient (scopes: treatment, data-sharing-national, data-sharing-family, research/AI, marketing-Zalo). Enforcement points: (a) FHIR facade filters resources by active Consent before serialization (deny-by-default for `data-sharing-national` → adapters skip un-consented patients and log why); (b) portal/family access checks `data-sharing-family`; (c) the AI framework checks `research/AI` before sending any PHI to a cloud LLM (Ollama-local exempt); (d) Zalo/ZNS sends check marketing consent. One `check_consent(patient, purpose)` API used everywhere, cached per request.

### 6.7 PWA offline sync hardening
Current PouchDB/IndexedDB 30-day sync needs conflict discipline before third parties write to the same records via API: (a) add a monotonic `sync_revision` (server bump on every write) + `client_mutation_id` for idempotent replay; (b) conflict policy per model — **field-level last-writer-wins** for operational fields, **append-only** for clinical notes/vitals/med-administrations (clinical data is never overwritten, conflicting edits become two entries flagged for review), **server-wins** for pricing/billing; (c) tombstones for deletes with 30-day retention matching the sync window; (d) a visible conflict-review queue in the PWA rather than silent merges. This is a prerequisite for Phase-3 FHIR *writes*.

### 6.8 Module packaging
```
health_fhir_core          # facade, serializers, subscriptions, $export
health_fhir_terminology   # code tables, importers, $lookup/$expand, coding widgets
health_api_gateway        # OpenAPI, OAuth2/keys/scopes, webhooks, audit log
health_integration_bus    # outbox, dispatcher, queue_job channels  (dependency of the two above)
health_fhir_adapter_vn / _sg / _id / _au   # one addon per country, installable independently
health_imaging            # ImagingStudy, DICOMweb client, OHIF embed (optional)
```
Rule: `health_fhir_core` depends only on `health_base` + clinical models; adapters depend on core; **no existing module gains a dependency on FHIR** (serializers reach into models, not vice-versa) — VN customers who never install an adapter carry zero overhead. All AGPL-safe pure-Python deps (`fhir.resources`, `authlib`, `fhirpathpy`, `cryptography`).

---

## 7. Phased Implementation

| Phase | Scope | Deliverables | Rough effort |
|---|---|---|---|
| **Phase 1 — Read-only FHIR facade + API gateway** | `health_integration_bus` (outbox + queue_job), `health_fhir_core` read-only (Patient, RelatedPerson, Practitioner, PractitionerRole, Organization, Location, Encounter, Appointment, ServiceRequest, DocumentReference, Coverage, CapabilityStatement, `$export`), `health_api_gateway` (OpenAPI decorator + generated docs, API keys w/ scopes, OAuth2 client-credentials, audit log, business webhooks on 6 events, edge gateway config), PWA controller wrapped into `/api/v1` | External systems can *read* everything and subscribe to business webhooks; API is documented, keyed, audited. Demo: Postman collection pulling a patient's full visit history over FHIR. | **~10–12 engineer-weeks** (2 devs × 5–6 wks): facade 4–5 wks, gateway 3–4 wks, outbox/jobs 2 wks, hardening/docs 1 wk |
| **Phase 2 — Terminology + born-FHIR clinical models** | `health_fhir_terminology` (ICD-10 VN+EN, LOINC vitals set, UCUM, RxNorm promotion, DAV crosswalk, coding widgets, AI retro-coding queue via existing provider factory); new vitals/care-plan/eMAR/incident models built born-FHIR (models owned by the clinical workstream; FHIR serializers + LOINC bindings owned here); Observation/CarePlan/Goal/MedicationRequest/MedicationAdministration/RiskAssessment/Flag resources go live; consent enforcement layer v1; PHI field encryption for ID fields; coding-density BI dataset | Structured, coded clinical data flowing from the PWA; facade coverage jumps from admin data to clinical data. | **~12–16 engineer-weeks** interop share (terminology 4–5 wks, serializers for new models 3–4 wks, consent layer 2–3 wks, encryption mixin 2 wks, AI coding queue 2 wks) — clinical model build costed in the clinical section |
| **Phase 3 — Country adapters, subscriptions, SMART, writes** | FHIR Subscriptions (rest-hook) + `SubscriptionTopic`s; conditional writes for whitelisted resources (Appointment booking, Patient demographics, inbound DocumentReference) on top of hardened PWA sync (§6.7); SMART app-launch flows + `/.well-known/smart-configuration`; **adapter #1 VN** (profile pack, LGSP-ready transport, 4210-XML transform for BHYT, CA-signing hook, Circular-54 readiness report), **adapter #2 Indonesia SATUSEHAT sandbox→production conformance** (the external correctness proof); SG/AU adapters scoped-but-deferred to market entry; DICOMweb/`health_imaging` if clinic imaging demand confirmed | Nationally submission-ready in VN, SATUSEHAT-conformant, SMART-capable; third-party apps can launch in-context. | **~16–20 engineer-weeks** (subscriptions+writes 4–5 wks, SMART 2–3 wks, VN adapter 5–6 wks incl. certification cycles, ID adapter 3–4 wks, imaging 2 wks optional); B2G onboarding calendars (Synapxe/NDIA/MOH) run in parallel and gate go-live, not build |

**Sequencing rationale:** Phase 1 monetizes immediately (enterprise clients and partners ask "do you have an API?" — answer becomes a documented yes) and de-risks everything after it, because the outbox + serializer registry is the substrate all later work rides on. Phase 2 is where competitive distance opens: coded, FHIR-native home-care clinical data is something no VN competitor and few ASEAN competitors have. Phase 3 converts that into regulatory moats per country, cheapest-proof-first (SATUSEHAT), deepest-market-first (VN).
