# Handover: Condition / Diagnosis Spine (`health_condition`)

Read `docs/strategy/HANDOVER-CONVENTIONS.md` FIRST (deploy §2, safety §4, gotchas §5 —
especially §5.27 search-skips-archived, §5.32 HttpCase poisoning, §5.45 one-odoo-process,
§5.47 compose-export ACL omission).

## 0. Scope and binding non-goals

**The gap:** diagnoses exist only as (a) free text (`health.clinical.note.diagnosis`,
PHI-encrypted) and (b) the ICD-10 m2m sidecar `condition_code_ids` on notes. There is NO
per-diagnosis record — no problem list, no FHIR Condition resource in the facade (the VN
adapter fakes bundle-only `cond-<note>-<code>` entries), nothing BHYT-4210 can read
per-claim diagnosis codes from.

**Build (ONE new module `health_condition`):**
1. `health.condition` — the patient problem list: ONE record per (patient, ICD-10 code),
   evidence-linked to the notes that assert it.
2. A sync hook on `health.clinical.note` (`_inherit` INSIDE health_condition) that
   converges EVERY sidecar write path (AI-coding approve, manual tags, future scribe)
   into problem-list records. **Additive-only** — sync never deletes or resolves.
3. A backfill (`post_init_hook`) promoting existing sidecar rows.
4. A `Condition` FHIR serializer registered into the health_fhir_core REGISTRY from this
   module (clone the CodeSystem downstream-registration pattern). It joins `$everything`
   automatically via the compartment convention.
5. Backend list/form/search views + menu + catchment security (clone health_incident).

**Binding NON-goals:**
- NO edit to `health_ai_coding` (its approve write flows through the note-write hook —
  verified single writer, ai_code_suggestion.py:441), `health_fhir_adapter_vn` (its
  bundle uses a FIXED `BUNDLE_RESOURCE_TYPES` list, fhir_adapter_vn.py:64 — a real
  Condition serializer does NOT duplicate its synthetic entries; switching the VN bundle
  to real Conditions is a FUTURE phase), `health_fhir_core` (registry-driven — zero core
  edits), `health_emr` (do NOT add `condition_code_ids` to the EMR locked-fields set —
  retro-coding a FINALIZED note is the whole point of ai_coding; the narrative is sealed,
  the coded sidecar is deliberately post-finalize-writable metadata).
- NO write API for Condition (facade stays read-only). NO BHYT wiring yet (Phase-2 4210
  will READ this model). NO PWA (no PWA assets → NO version bump). NO pip installs.
- NO automatic clinical-status transitions (resolve/inactivate is a HUMAN act in the
  backend form; sync only creates/reactivates/links).

## 1. Verified plumbing facts (do NOT re-derive)

- Sidecar: `condition_code_ids` M2M `medical.code`, relation
  `clinical_note_condition_code_rel` (`note_id`,`code_id`), domain
  `[('system_id.code','=','icd10')]` — health_fhir_terminology/models/health_clinical_note.py:14-19.
- SOLE production writer: `health.ai.code.suggestion.action_approve()` →
  `rec.note_id.sudo().write({'condition_code_ids': [(4, rec.code_id.id)]})` —
  health_ai_coding/models/ai_code_suggestion.py:429-451 (per-row savepoint). Reject
  (453-461) never touches the sidecar. Manual writes come through the many2many_tags
  widget on the note form (health_fhir_terminology/views/health_clinical_note_views.xml:13-15).
  Both paths are `write()` on the note → ONE hook catches all.
- Note model: `health.clinical.note` (health_fieldservice/models/health_clinical_note.py:4-77).
  Patient = `note.order_id.patient_id` (order_id required, cascade). `author_id`
  (res.users, default uid). EMR fields (health_emr/models/health_clinical_note.py:80-114):
  `emr_state` draft/final, seal, addendum chain.
- `medical.code`: `code` (e.g. 'I10'), `display`, `display_vi`, `display_name` compute =
  `[code] display_vi_or_display`, `system_id.code=='icd10'`, `.get('icd10','I10')`
  helper — health_fhir_terminology/models/medical_code.py:18-97. ICD-10 FHIR uri =
  `http://hl7.org/fhir/sid/icd-10`.
- Serializer conventions (clone AdverseEvent, health_fhir_core/serializers/adverse_event.py:28-88):
  class attrs `resource_type`/`odoo_model`/`search_params` ('patient' via
  `fso_common.patient_ref_domain('<field>')`, dates via `date_param_domain(...)`),
  `base_domain(env)`, `patient_ids_of(records)`, `to_fhir(record)`; `serialize_batch`
  inherited (uses `fetch` — no `self.env` in to_fhir, use `record.env`).
- Downstream registration precedent (CLONE EXACTLY):
  health_fhir_terminology/serializers/__init__.py:18-24 — instantiate, assign
  `REGISTRY[resource_type]`, call `clear_capability_cache()`, at import time; module
  top-level `__init__.py` imports `serializers`.
- `$everything` compartment = every REGISTRY serializer with a `patient`/`subject`
  search param (health_fhir_core/serializers/everything.py:43-63); the coverage-guard
  test (test_fhir_everything.py:179-201 + NON_COMPARTMENT_RESOURCES:33-36) will
  FORCE the new serializer to carry a `patient` param — it does, so NO allowlist edit.
- DocumentReference serializes `health.clinical.note`
  (health_fhir_core/serializers/document_reference.py:30-31) → Condition
  `evidence.detail` can reference `DocumentReference/<note_id>` (same compartment, no
  new leak surface).
- Security precedent to clone: health_incident CSV role ladder + catchment record rules
  (health_incident/security/health_incident_security.xml:14-31) + its
  `catchment_province_id` compute from the client partner.
- No test asserts an exact facade resource count (Phase-2 relaxed to >=19; grep-verified
  2026-07-19). Capability goes 20 → 21.

## 2. Architecture

### 2.1 Model `health.condition` (models/health_condition.py)

`_name='health.condition'`, `_inherit=['mail.thread','mail.activity.mixin']`,
`_order='recorded_date desc, id desc'`, `_rec_name` via compute
(`display_name = code display_vi-first + patient`).

Fields:
- `patient_id` M2O res.partner, required, index, ondelete='restrict'.
- `code_id` M2O medical.code, required, ondelete='restrict',
  domain `[('system_id.code','=','icd10')]`.
- `clinical_status` Selection active/inactive/resolved, default 'active', tracking.
- `verification_status` Selection provisional/confirmed, default 'confirmed', tracking.
  (Everything reaching the sidecar is human-asserted — manual tag or human-approved AI.)
- `recorded_date` Date (first assertion; from the first evidence note's create_date),
  readonly-ish (set by sync/backfill; editable by doctors for corrections).
- `last_asserted_date` Date (latest evidence assertion), readonly.
- `note_ids` M2M health.clinical.note, relation `health_condition_note_rel`
  (`condition_id`,`note_id`) — the evidence links.
- `recorder_id` M2O res.users, readonly (first asserting note's author_id).
- `catchment_province_id` M2O, compute/store from patient (clone the health_incident
  compute exactly — same field path).
- `active` Boolean default True (archive = remove from working problem list; NEVER
  unlink in normal flows).

`init()`: UNIQUE index on `(patient_id, code_id)` (Odoo 19 does NOT materialize
`_sql_constraints` — conventions §5). This is the idempotency backstop for the sync.

Access: nurse/receptionist read; doctor/head_nurse create+write; manager/admin
create+write; owner all incl. unlink; unlink for NOBODY else (archive instead). Record
rules: catchment pair + owner-all (clone incident). The sync hook itself runs `sudo()`
(system-derived records), so ACLs bind humans, not the hook.

### 2.2 Sync hook (models/health_clinical_note.py — `_inherit` in THIS module)

Override `create` + `write` on `health.clinical.note`: after `super()`, if
`condition_code_ids` was in vals, call `self._sync_health_conditions()`.

`_sync_health_conditions()` — ADDITIVE-ONLY, idempotent, `sudo()`:
```
for note in self (skip notes with no order_id.patient_id):
    for code in note.condition_code_ids:
        cond = health.condition.sudo().with_context(active_test=False).search(
            [('patient_id','=',patient.id), ('code_id','=',code.id)], limit=1)
        if not cond:
            create({patient, code, recorded_date=note.create_date.date(),
                    last_asserted_date=same, recorder_id=note.author_id.id,
                    note_ids=[(4, note.id)]})
        else:
            link note (4, note.id) if missing;
            last_asserted_date = max(existing, note.create_date.date());
            if not cond.active or cond.clinical_status != 'active':
                reactivate: active=True, clinical_status='active'
                (a fresh clinical assertion of a resolved/archived problem re-opens
                it — message_post the reactivation reason with the note reference)
```
Rules: removal of a code from a note does NOT unlink evidence and does NOT touch the
condition (additive-only; corrections are human acts on the condition form).
`recorded_date`/`recorder_id` NEVER move after creation (first-assertion provenance).
The AI approve path calls note.write under `sudo()` per-row savepoints — the hook must
not raise on a healthy path; if the unique index races (two workers, same new pair),
let the savepoint retry semantics of the caller apply (do NOT wrap in bare except).

### 2.3 Backfill (post_init_hook in __init__.py, hooks.py)

Iterate existing sidecar pairs (ORM: search notes with `condition_code_ids != False`,
then reuse `_sync_health_conditions()` on them in batches of ~200) — NOT raw SQL, so
recorded_date/recorder/evidence provenance is identical to the live path. Idempotent
(re-running creates nothing new — assert in a test). Log the created count. On vietuat
expect a SMALL number (seed patient 533 + AI-approved codes) — report the real count
honestly.

### 2.4 Serializer (serializers/condition.py + serializers/__init__.py)

Clone the CodeSystem registration pattern EXACTLY (import-time REGISTRY assignment +
`clear_capability_cache()`; top-level `__init__.py` imports serializers).

```python
class ConditionSerializer(FHIRSerializer):
    resource_type = 'Condition'
    odoo_model = 'health.condition'
    search_params = {
        'patient': {'type': 'reference',
                    'domain': fso_common.patient_ref_domain('patient_id')},
        'code': {'type': 'token',
                 'domain': lambda v: [('code_id.code', '=', v)]},
        'clinical-status': {'type': 'token',
                            'domain': lambda v: [('clinical_status', '=', v)]},
        'recorded-date': {'type': 'date',
                          'domain': date_param_domain('recorded_date')},
    }
```
(Verify `date_param_domain` handles a Date — not Datetime — column; if it emits a
datetime literal, Odoo compares fine, but confirm with a test on `recorded-date=ge...`.)

`base_domain` → `[]` (archived conditions are naturally excluded by `search()` —
conventions §5.27 — which is the CORRECT facade semantics: the working problem list).
`patient_ids_of` → `records.mapped('patient_id').ids`.

`to_fhir(record)`:
- `id` str(record.id), `meta.lastUpdated` from write_date (mirror AdverseEvent).
- `clinicalStatus`: coding system
  `http://terminology.hl7.org/CodeSystem/condition-clinical`, code =
  record.clinical_status (active/inactive/resolved are all valid codes).
- `verificationStatus`: system
  `http://terminology.hl7.org/CodeSystem/condition-ver-status`, code =
  record.verification_status.
- `code`: coding `[{system 'http://hl7.org/fhir/sid/icd-10', code, display}]`,
  `text` = display_vi or display (Vietnamese-first — mirror the VN adapter's
  fhir_adapter_vn.py:105-133 shapes).
- `subject`: `Patient/<patient_id>` + display name.
- `recordedDate`: recorded_date isoformat.
- `evidence`: `[{'detail': [{'reference': 'DocumentReference/<note_id>'} ...]}]`
  (only notes still linked; same-compartment refs).
- Omit `recorder` (res.users doesn't map to a facade Practitioner cleanly — v1 skip).
Must validate against `fhir.resources` Condition (test).

New OAuth scope `system/Condition.read` is auto-derived from the registry — existing
tokens need the scope GRANTED (admin action) before external per-resource reads; note
it in the report. `$everything` (Patient-scope) includes Condition with no grant.

### 2.5 Views + menu (views/)

List (patient, code display_name, clinical_status badge, recorded_date,
last_asserted_date, evidence count), form (statusbar clinical_status; header buttons
"Mark Resolved"/"Reactivate" doctor+; CHATTER AT BOTTOM full-width — user convention;
evidence notes as readonly list), search (filters active/resolved, group by
patient/code/status). Menu "Chẩn đoán / Diagnoses" under `health_base.menu_healthcare_root`
sequence 29, visible nurse+. Mono flat colors, hf-wt-ico icons if any (user conventions).

### 2.6 Sanctioned edits (exhaustive)

| Module | Files | What |
|---|---|---|
| **health_condition (NEW)** | everything in it | the module |

NOTHING outside the new module. health_fhir_core / health_fhir_terminology /
health_ai_coding / health_fhir_adapter_vn / health_emr / health_fieldservice: READ-ONLY.

## 3. Safety rails (binding)

- Sync is `sudo()` but ONLY creates/links/reactivates `health.condition` — it must
  never write the note, the sidecar, or any clinical/accounting model.
- Facade reads: NO sudo anywhere in the serializer; record rules + consent gate apply
  exactly as for every other PHI resource (the registry machinery does this — add
  nothing, bypass nothing).
- Ship the CSV ACL for every healthcare group (do NOT repeat the health.fall.risk
  no-ACL mistake — §5.47).
- No PWA assets → no PWA version bump. HttpCase not needed (no new route) — plain
  TransactionCase; keep `--no-http` OUT only if you add HttpCase (conventions).

## 4. Tests (~13, tests/test_condition.py — no HttpCase needed)

1. Sidecar write on a note creates the condition (fields: patient, code, recorded_date
   = note create date, recorder = note author, evidence linked, active/confirmed).
2. Idempotency: same code from a SECOND note → still ONE condition, 2 evidence notes,
   last_asserted_date advanced, recorded_date/recorder UNCHANGED.
3. Full AI path: create `health.ai.code.suggestion` + `action_approve()` → condition
   exists (proves the sudo approve write flows through the hook; no ai_coding edit).
4. Approve on a FINALIZED note (emr_state='final') still creates the condition
   (retro-coding post-finalize is preserved).
5. Additive-only: removing the code from the note leaves the condition + evidence.
6. Reactivation: archive + resolve a condition, assert the code on a new note →
   active + clinical_status 'active' again.
7. Backfill: pre-seed sidecar rows, run the hook fn → created; run again → zero new.
8. Unique index exists (SQL catalog check) + duplicate create raises.
9. `to_fhir` validates against fhir.resources Condition (both status values, vi text).
10. Registry: 'Condition' in REGISTRY, capability lists it, coverage-guard test file
    of health_fhir_core still passes (run its suite too).
11. `$everything` on a coded patient includes the Condition entry
    (call `build_everything_bundle` directly, mode 'include').
12. Search domains: patient param scopes to the right patient; `code=I10` filters;
    archived condition NOT in facade search (working problem list).
13. Record rules: cross-catchment head-nurse sees nothing; owner sees all.

## 5. Deploy + verify (conventions §2)

- scp → /tmp → sudo cp → chown odoo:odoo; stop server; ONE process only (§5.45):
  `-d vietuat -i health_condition -u health_fhir_core --test-enable
  --test-tags /health_condition,/health_fhir_core,/health_fhir_terminology,/health_fhir_adapter_vn
  --stop-after-init --workers 0 --no-http`; restart; curl login.
- Confirm by `odoo.tests.result` line + EXIT:0 (NOT just HTTP:200).
- Live probes (read-only): `/fhir/r4/metadata` lists Condition (21 resources);
  backfill count logged; one real coded patient's `$everything` shows the Condition
  entries (log-only mode; do NOT toggle consent_enforced — §5.48 restart tax).
- Evidence pack: metadata excerpt, one Condition resource JSON, backend problem-list
  screenshot(s) per browser-QA rule, backfill count. QA fixtures cleaned BEFORE/AFTER
  the deploy, never during (§5.45); fresh-cursor verify (§5.34).

## 6. Report back (docs/strategy/reports/condition-spine-report.md)

Numbered test results, backfill real count, deviations with reasons, the scope-grant
note for existing OAuth clients, any new gotcha for the ledger (§5.49+), commit hash.

---
**Kickoff (paste into Opus):**
Implement the phase specified in docs/strategy/handovers/condition-spine.md. Read
docs/strategy/HANDOVER-CONVENTIONS.md first. Build the NEW module health_condition
ONLY — §2.6 is the exhaustive sanction list; health_ai_coding, health_fhir_core,
health_fhir_adapter_vn, health_emr are READ-ONLY. The sync hook is additive-only and
the §3 rails are binding. Full self-verification per §5 incl. the evidence pack, then
commit the report per §6 and report back.
