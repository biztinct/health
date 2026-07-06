# health19 — Master Design Document

**Audience:** an implementing AI model (e.g. Opus 4.8) or engineer starting to code. The product thinking is finished — it lives in [`health19-strategy-report.html`](health19-strategy-report.html) (open in a browser). This document and its two companion specs capture everything needed to implement without re-deriving decisions.

**Document set:**

| File | Contents |
|---|---|
| `DESIGN.md` (this file) | Platform context, tech stack, hard conventions, design principles, phasing, cross-cutting standards |
| `design-clinical-modules.md` | Field-level specs: `health_careplan`, `health_vitals`, `health_emar`, `health_forms`, `health_incident`, `health_consent` |
| `design-platform-services.md` | Field-level specs: `health_evv`, `health_api_gateway`, `health_fhir_core`, reminder cascade, H0 automations, PWA additions |
| `architecture-interop.md` | Full FHIR R4 gateway + country adapters + terminology + API gateway + platform architecture (the canonical interop reference) |
| `data/*.json` | The 473 scored recommendations, roadmap, competitor matrix, module/dashboard/redesign lists (machine-readable) |
| `health19-strategy-report.html` | The full interactive strategy report (self-contained; open locally) |

**Reading order for an implementer:** this file top-to-bottom → the companion spec for the module you're building → `architecture-interop.md` §1–2 if the module touches FHIR/coding.

---

## 1. What health19 is

An Odoo 19 **Community Edition** platform for a home care + clinic + field nursing provider (VietUc, Vietnam), covering: home care, community care, nursing services, clinic services, doctor consultations, allied health, aged care, disability support, care packages; private, corporate and government-funded clients; a mobile nursing workforce. Target: scale from small providers to enterprise, Vietnam → ASEAN → global.

**Strategic direction (decided, do not re-litigate):**
1. Build the **clinical spine** (care plans, structured vitals, eMAR, forms, incidents, consent) as Horizon 1 — it is also a regulatory deadline (see §6).
2. New clinical models are **born-FHIR**: Odoo schema designed from the FHIR R4 resource inward so serialization is trivial (`architecture-interop.md` §1.1 has the full mapping table).
3. **Extend proven paradigms** instead of inventing: Blockly (from `advanced_pricing`) for rules; the offline PouchDB sync (from `health_pwa`) for all mobile features; OWL workspace shells (from `health_fieldservice`/`health_invoicing`) for new backend screens; the multi-provider AI factory (from `hr_development_ai`) for all AI features.
4. **Exception-only operations**: automation handles the routine path; humans see only what needs a decision.
5. **Governed AI**: every AI feature routes through a PHI-guard gateway; local-model (Ollama) fallback wherever data sovereignty demands.

---

## 2. Existing platform inventory (what you build on — never duplicate)

### 2.1 Core custom modules

| Module | Key models | What it does |
|---|---|---|
| `health_base` | `res.partner` (patient ext: `is_patient`, `patient_code`, intake fields, emergency contact), `health.facility`, `health.service.type`, `health.patient.category`, `health.medical.specialty`, `health.catchment.province`, `health.fall.risk` (Morse), `health.medication.safety` (RxNorm/OpenFDA interaction check), `health.audit.log` | Foundation: patients, facilities, service catalog, geographic catchments, base clinical lookups |
| `health_fieldservice` | `health.fieldservice.order` (**FSO — the unified booking**; state machine `draft→confirmed→assigned→in_progress→completed→completed_pending_invoice→closed` / `cancelled`), `health.staff.assignment`, `health.staff.availability.matrix`, `health.staff.skill`, `health.clinical.note`, `health.clinical.protocol` (JSON action steps), `health.portable.equipment`, `health.fieldservice.stage/team/communication`, AI assignment engine + 3 crons | Booking + field service engine, ops command center, staff assignment |
| `health_pwa` | `health.pwa.config`, `health.pwa.push.subscription`, `health.pwa.staff.notification` | Nurse field app: Vue 3 + Quasar, PouchDB/IndexedDB offline (30-day sync), check-in/out, GPS, clinical notes + photos, quote verification, payment collection, VAPID web push. Controllers: `controllers/api.py` (~2,300 lines), `controllers/sync.py` |
| `health_crm` | `crm.lead` ext (healthcare qualification), `health.client.relation` (**kinship graph**: caregiver/payer/referrer/guardian roles × relationship types), contact/lead reasons | Contact-first intake; the payer≠patient≠contact reality |
| `health_invoicing` | `health.service.package` (prepaid, visit countdown), `health.payment.transaction`, `health.prepaid.service`, `health.ar.transaction.log`, `account.move`/`sale.order` ext | Auto-invoice on FSO completion, packages, AR dashboard, Finance Center |
| `advanced_pricing` | `advanced.pricing.engine`, `advanced.pricing.rule` (**Google Blockly** visual builder, cascading levels, holiday/TET multipliers, approval workflow, plain-language explain) | The pricing engine and the platform's visual-rules paradigm |
| `health_redinvoice` | `redinvoice.request` | Viettel SInvoice tax e-invoice. API quirk: createInvoice POST needs `/services/einvoiceapplication/api/` prefix + Basic Auth (bare path 405s) |
| `health_roster` | roster grid | Weekly nurses×days drag-drop planning; unified availability-aware staff schedule timeline (web_timeline, action 1536, `validate_drop` API) |
| `health_zalo` | `zalo.config`, `zalo.conversation`, `zalo.message` | Zalo OAuth, webhooks, **ZNS template notifications**, chat hub widget |
| `health_voip24h` | `voip.config`, `voip.call.log`, `voip.call.recording`, `voip.extension` | Click-to-dial, CDR sync (15-min cron), recordings |
| `biz_bi` / `biz_bi_health` | `bi.dataset`, gold/silver pipeline, `bi.ai` | Semantic BI: datasets w/ row/col security, medallion refresh, ECharts explorer, GridStack dashboards, **pluggable LLM chart generation** (Claude/OpenAI/Ollama; metadata-only, never raw rows) |
| `health_theme` | `vu.theme` (56 CSS tokens) | Theme Studio, VU form engine (hero rendering), side sheets, progress rails, docked actions |
| `pb_hr_workforce` | shift templates/planning, OT rules | Shift roster grid, live attendance Kanban, Gantt timecards, payroll variance |
| `hr_development_ai` | `hr.ai.provider.config`, `ai_providers/provider_factory.py` | **Multi-provider AI framework** (Claude/OpenAI/Ollama/Mistral, Fernet-encrypted keys) — reuse for ALL new AI features |
| `access_roles` + `health_user_admin` | role, field/record access | Field-level + record-level RBAC; SaaS-safe tenant admin |
| `health_field_requirements` | `field.requirement` | Role/state-dependent mandatory fields (server + client enforcement) |
| `biz_deroute` | — | Web client served at `/bizapp` (301 from `/odoo`) |

### 2.2 Known integration facts
- Facility links: employee → `healthcare_facility_id`; client → `res.partner.primary_facility_id`.
- Catchment access control: `health.catchment.province` FK appears on staff, clients, bookings, packages — every new client-scoped model must carry it and its record rule (see companion specs).
- Timeline/vis dates: every date handed to vis-timeline must be wall-clock-as-UTC (`keepLocalTime`), else a +7h shift appears.
- `noupdate="1"` seed records (e.g. CMS sidebar) do NOT update on module upgrade — plan data migrations as direct DB writes or migration scripts.

---

## 3. Technology stack

### 3.1 Current (keep)
| Layer | Technology |
|---|---|
| Backend | Odoo 19 **Community** (Python 3.10+, PostgreSQL). Never refer to it as Odoo 17/18. No Enterprise modules. |
| Backend UI | OWL 2 components, QWeb XML views, SCSS with `vu.theme` CSS custom-property tokens |
| Nurse mobile | PWA: Vue 3 (Composition API) + Quasar, PouchDB + IndexedDB, service worker, VAPID web push (pywebpush) |
| BI | biz_bi (ECharts 5, GridStack), silver (live views) / gold (materialized) medallion |
| Rules | Google Blockly (bundled in `advanced_pricing`) |
| AI | Provider factory: Anthropic Claude / OpenAI / Ollama (local) / Mistral; Fernet-encrypted keys; per-company config |
| Comms | Zalo OA + ZNS, VoIP24h, Odoo mail/sms |
| Vietnam compliance | Viettel SInvoice, MISA sync fields, Vietnamese address/kinship structures |

### 3.2 New (approved additions)
| Purpose | Technology | Notes |
|---|---|---|
| FHIR serialization/validation | `fhir.resources` (pip, pydantic-based) | Serializer registry pattern — one class per resource |
| OAuth2 for API gateway | `authlib` | Client-credentials grant; scopes on `res.users.apikeys` |
| Background jobs / outbox | OCA `queue_job` | Transactional outbox for integrations & webhooks (architecture §6.1) |
| Hashing / EVV chain | Python `hashlib` SHA-256 | No new dependency |
| Signature capture | HTML canvas (PWA) → PNG `ir.attachment` | No library needed; keep it dependency-free |
| Geofencing | Browser Geolocation `watchPosition` in PWA | No native app; battery strategy in platform spec |
| Vietnamese ASR (H2) | PhoWhisper (self-hosted) | Only when ambient scribe starts; not H0/H1 |
| Terminology | ICD-10 (with Vietnamese MOH translations) primary; LOINC for vitals; RxNorm (already used); SNOMED optional later | VN is not a SNOMED member — do not block on SNOMED |
| Edge gateway (deploy-time) | Traefik or Kong in front of Odoo for `/api/*`, `/fhir/*` rate limits | App-level fallback counter specified in platform spec |

**Rejected/avoid:** building a PACS (use DICOMweb references, architecture §5); Odoo Enterprise dependencies; native iOS/Android apps (PWA is the strategy); SNOMED as a launch dependency.

---

## 4. Hard project conventions (violations = review rejection)

1. **UI colors:** flat single (mono) colors only. Never gradients or dual-tone. Semantic status colors separate from brand accent. Themeable via `vu.theme` tokens where applicable.
2. **Icons:** `hf-wt-ico` CSS-mask SVG icons. Never emoji, never Font Awesome, in any new UI.
3. **Chatter:** renders at the **bottom, full-width** of form views, never as a side column.
4. **Model naming:** `health.*` namespace, snake_case fields, `_description` on every model, `mail.thread` + `mail.activity.mixin` on user-facing records, `tracking=True` on state/critical fields.
5. **Every client-scoped model** carries `catchment_province_id` (+ record rule) and respects the facility pattern (§2.2).
6. **PWA deploys:** increment the version in `health_pwa/views/pwa_templates.xml` in **3 places** on every health_pwa change. This is a hard rule.
7. **UAT environment:** database is `vietuat` (never `vietuc_uat`/`odoo_vietuc`). Deploy = scp to `/tmp` on server → `sudo cp` with odoo ownership → `-u <module>` upgrade → restart.
8. **i18n:** every user-visible string translatable; ship `vi.po` alongside; client-facing messages (ZNS/SMS) templated per-language with Vietnamese as first-class.
9. **Self-validation:** after UI work, audit padding/alignment/colors in multiple iterations (screenshots) before declaring done — don't wait for human review.
10. **Versioning:** new modules start `19.0.1.0.0`; version bumps on every deployable change.
11. **Free-text compatibility:** never delete existing free-text clinical fields when adding structured models — add alongside, migrate progressively (coding-sidecar pattern, architecture §2.4).

---

## 5. Build plan (what to code, in order)

### Horizon 0 — quick wins (specs in `design-platform-services.md` §E)
Patches to existing modules, no new schema beyond small additions:
1. Exception-only visit completion (auto-verify unchanged quotes; one-tap complete in PWA)
2. Nightly batch Red Invoice submission cron + retry queue
3. Timecards auto-filled from PWA check-in/out → `pb_hr_workforce`
4. Reminder cascade v1 (ZNS → SMS; T-24h/T-2h) — subset of the messaging spec
5. Instant first-visit offer at lead qualification (3 feasible slots via AI assignment engine, one-tap ZNS accept)

### Horizon 1 — clinical spine + platform (the main build)
New modules, in dependency order:

| Order | Module | Spec | Depends on |
|---|---|---|---|
| 1 | `health_vitals` | clinical spec §2 | health_base, health_fieldservice |
| 2 | `health_forms` | clinical spec §4 | health_base, health_fieldservice |
| 3 | `health_careplan` | clinical spec §1 | health_base, health_fieldservice, health_vitals |
| 4 | `health_emar` | clinical spec §3 | health_base, health_fieldservice, (uses health.medication.safety) |
| 5 | `health_incident` | clinical spec §5 | health_base, health_fieldservice |
| 6 | `health_consent` | clinical spec §6 | health_base, health_crm (kinship) |
| 7 | `health_evv` | platform spec §A | health_pwa, health_fieldservice |
| 8 | `health_api_gateway` | platform spec §B | base; wraps health_pwa endpoints |
| 9 | `health_fhir_core` | platform spec §C | health_api_gateway + all above |
| 10 | `health_messaging_auto` | platform spec §D | health_zalo, sms, health_voip24h, health_consent |

Each module lands with: backend models/views/security → PWA additions → seeds → tests → `vi.po`.

### Horizon 2+ (design later, do not build now)
`health_portal_family` (+ Zalo Mini App), `health_telehealth`, `health_routes` (learned travel matrices), ambient scribe (PhoWhisper + LLM), country adapters (SATUSEHAT first), `health_claims` (NDIS), `health_telemonitoring`, `health_twin`. Directional designs: strategy report + `architecture-interop.md` §3, §7.

---

## 6. Regulatory anchors (why the sequence is what it is)

- **Vietnam Circular 13/2025/TT-BYT** (effective 21 Jul 2025) — replaces Circular 46/2018, supersedes §VIII Appendix I of Circular 54/2017. EMR mandatory: hospitals by 30 Sep 2025, **other examination/treatment facilities by 31 Dec 2026** (home-care clinics in scope). EMR must link to citizens' personal ID / VNeID → every patient-identity model must reserve a VNeID identifier slot (see FHIR `identifier[]` mapping).
- **Decision 4210/QD-BYT**: BHYT/VSS insurance XML output formats (H2 adapter).
- **Indonesia SATUSEHAT**: FHIR R4 mandated; onboarding = register Organization/Location/Practitioner/Patient first → our Phase-1 facade resources match exactly.
- **Singapore NEHR** (Synapxe): contribution capability required for market entry.
- **Australia**: NDIS price-guide compliance + incident (SIRS) + medication reporting → `health_incident` and `health_emar` are prerequisites for AU.

---

## 7. Cross-cutting standards

### 7.1 Security
- Reuse existing groups where the companion specs name them; new modules add `<module>_user` / `<module>_manager` groups following the `health_base` security pattern.
- Record rules: catchment-province scoping on client-data models; portal/external access denied by default (H1 has no client-facing surface).
- PHI access audit: `health_api_gateway` middleware logs external reads (append-only), feeding Circular-13 evidence.
- Consent: after `health_consent` lands, sharing features (family snapshot, portal, FHIR export of notes) must call `check_consent()` — the hook signature is in the clinical spec.

### 7.2 Testing & acceptance
- Python unit tests per module (`tests/`, `TransactionCase`) covering: state machines, compute fields, constraint violations, the hash chain (EVV), serializer round-trips (FHIR).
- Each spec ends with acceptance criteria — implement them as tests where feasible.
- PWA: manual test checklist per release (offline → sync → conflict), plus the pixel-validation rule (§4.9).
- FHIR: validate every serialized resource with `fhir.resources` models in tests; `/fhir/r4/metadata` must list exactly the supported resources/params.

### 7.3 Performance
- FHIR search endpoints paginate (Bundle with `link[next]`), default page 50, max 200.
- No N+1 in serializers: batch-read with `read()`/`search_read`, prefetch relations.
- Vitals list/trend views must stay fast at 100k+ rows: index `(patient_id, code_id, effective_datetime)`.
- PWA sync payload additions must stay within the existing 30-day window pattern; new stores follow storage-manager's 5-minute cache convention.

### 7.4 Data migration
- Free-text vitals/medications in `health.clinical.note` remain; an optional backfill wizard (AI retro-coding queue, architecture §2.4) is H2 — do not block H1 on it.
- Morse falls (`health.fall.risk`) stays in `health_base`; `health_forms` ships an equivalent template and a note to converge later.

---

## 8. Where the deeper thinking lives

- Full strategy, competitor analysis, 473 scored recommendations: `health19-strategy-report.html` (interactive; also at https://claude.ai/code/artifact/6147a22b-fd18-45e1-88b6-022b0a0591db)
- Machine-readable recommendation bank (id, title, description, area, tier, scores, priority): `data/recommendations.json`
- Interop & platform architecture in full depth: `architecture-interop.md`
- Roadmap horizons with named items: `data/roadmap.json`
