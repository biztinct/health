# Handover: AI Retro-Coding Queue — `health_ai_coding`

Read `docs/strategy/HANDOVER-CONVENTIONS.md` FIRST (definition of done =
its §8; gotcha ledger 18 entries — read all). This is Tier 4's AI
retro-coding queue: an LLM reads the free-text of clinical notes and
SUGGESTS ICD-10 codes into a human review queue; a clinician approves
or rejects; approved codes land on the note's existing coded sidecar
(`condition_code_ids`) — the field Circular 13/2025 EMR export already
reads. The value: vietuat has months of free-text diagnoses with an
empty coded sidecar, and every future note gets coded the same lazy
way. **The AI only ever suggests. A human click is the only thing that
writes a code.**

## 0. Scope (one new module `health_ai_coding`)

1. **`health.ai.code.suggestion`** — the review queue (note × code ×
   confidence × evidence, suggested/approved/rejected).
2. **Nightly sweep** over un-coded clinical notes: consent-gated,
   redacted, LLM-called (JSON mode), validated against the ICD-10
   catalog, deduped, capped.
3. **Review UI** for doctors/head nurses: list grouped by state,
   one-click approve/reject + batch approve; approve appends the code
   to `clinical_note.condition_code_ids`.
4. **Append-only AI audit log** (bi.ai.log clone) storing the exact
   redacted prompt + raw response per call.

**No PWA change ⇒ NO PWA bump.**

**Non-goals (binding):** auto-applying codes (never — not even at
confidence 1.0); coding anything but ICD-10 conditions (no procedures,
no meds); a FHIR Condition serializer (health_fhir_core has none —
separate phase); surfacing suggestions on ANY public page, PWA screen,
or API; building a new LLM provider layer (reuse biz_bi's); editing
biz_bi / health_fhir_terminology / health_consent files; prompt-tuning
UI; fine-tuning.

## 1. Verified plumbing facts (do not re-derive; refs verified Jul 2026)

- **LLM layer to reuse**: `biz_bi/models/bi_ai.py` — `bi.ai.provider`
  model (L32-189): fields provider (anthropic/openai/**ollama**),
  endpoint, model_name, api_key (Fernet-encrypted), max_tokens,
  temperature, timeout_s; ONE method to call:
  `provider._complete(system, user_message, force_json=True)` →
  raw text; JSON mode is provider-native (OpenAI response_format,
  Ollama format=json, L166/L185). Errors raise (UserError on missing
  key; HTTP errors propagate) — YOUR loop wraps them. Ollama is the
  data-sovereignty path (endpoint e.g. http://localhost:11434).
- **Audit precedent**: `bi.ai.log` (bi_ai.py:454-473) — append-only,
  request_json/response_json/duration_ms/accepted; clone the shape.
- **ICD-10 catalog**: `medical.code`
  (health_fhir_terminology/models/medical_code.py:18-166) —
  `get(system_code, code)` → recordset or empty (L: helper), unique
  (system_id, code) index, `display_vi`, typeahead `name_search`.
  System short code is `'icd10'`. Catalog is CSV-imported
  (wizards/medical_code_import.py); a starter set ships in
  data/codes_icd10_starter.xml — on vietuat check the live row count
  and report it (the sweep must not assume a full catalog).
- **The target field**: `health.clinical.note.condition_code_ids` M2M
  → medical.code, domain icd10
  (health_fhir_terminology/models/health_clinical_note.py:11-19) —
  the "coded sidecar to free-text diagnosis". Source text fields on
  the note (health_fieldservice/models/health_clinical_note.py:4-77):
  `diagnosis` (Text), `clinical_notes` (Html — strip),
  `treatment_performed`, `patient_condition_after`.
- **PHI**: those fields are transparently AES-encrypted at rest
  (health_phi_encryption) — ORM reads decrypt; no code change needed,
  but it means note text IS live PHI: the redaction step (§2.3) and
  the log-access rules are load-bearing.
- **Consent**: `env['health.consent'].check_consent(partner,
  'data_sharing')` (health_consent.py — never raises, appends to the
  check log; 'data_sharing' is the MEDICAL_INFO type). Gate per note's
  patient; False → note is SKIPPED silently (no suggestion, no
  phantom row about the patient; the check log row is the evidence).
- **Batch pattern**: per-record savepoints + attempt counters —
  health_workflow_auto/models/redinvoice_batch.py (L63-94). Cron XML
  template: health_workflow_auto/data/workflow_cron.xml. Cron
  nextcall times are UTC — 20:00 UTC = 03:00 ICT (the routes phase
  hit this).
- **Groups**: approvers = `health_base.group_healthcare_doctor` +
  `group_healthcare_head_nurse` (health_security.xml; note doctor
  does NOT imply nurse — give ACLs to both explicitly, the routes
  phase hit this gap). Record-rule template: catchment pair via the
  note's FSO patient (family-link security files).

## 2. Architecture

### 2.1 `health.ai.code.suggestion`

| field | notes |
|---|---|
| note_id | m2o health.clinical.note, required, index, ondelete cascade |
| fso_id / patient_id | related (note.order_id / its patient), stored for grouping+rules |
| code_id | m2o medical.code, required (validated icd10) |
| confidence | Float 0-1 (from the model; display as %) |
| evidence | Char ≤200 — the note fragment that triggered the code (redacted text only) |
| state | suggested / approved / rejected |
| reviewed_by / reviewed_at | set on approve/reject |
| log_id | m2o health.ai.coding.log (the call that produced it) |
One suggestion per (note, code): search-first; codes ALREADY on
`note.condition_code_ids` are never suggested. `action_approve` (also
multi on selection): append code to the note's sidecar `[(4, id)]`,
state approved, stamp reviewer — inside try/except per record so one
bad note doesn't kill a batch approve. `action_reject`: state + stamp
only. NO unlink below manager. Approve/reject restricted to
doctor+head-nurse (+manager up) at BOTH the button and a
`check_access` guard in the method (server-side, not just view).

### 2.2 Sweep (`cron_ai_coding_sweep`, nightly 20:00 UTC = 03:00 ICT)

Scope: notes with (diagnosis OR clinical_notes) non-empty AND
`condition_code_ids = False` AND no prior suggestion rows AND
`ai_attempts < 3`, ordered newest first, capped at
`health_ai_coding.batch_cap` (default 25) per run. Add
`ai_attempts` (Integer) + `ai_last_attempt` on the note via inherit —
the ONLY clinical-note schema touch. Per note, inside a savepoint:
1. consent gate (§1) — False → mark attempted, continue;
2. build the redacted prompt (§2.3);
3. `_complete(system, user, force_json=True)` via the configured
   provider; parse JSON; malformed → attempt++, continue (raw
   response still logged);
4. validate each `{code, confidence, evidence}` item via
   `medical.code.get('icd10', code)` — unknown codes are DROPPED
   (count them in the log row), no fuzzy rescue in v1;
5. create suggestion rows (search-first dedup) + ONE log row.
A provider/connection error marks the attempt and moves on — the
sweep must end green with Ollama down (that is vietuat's reality).

### 2.3 Redaction (load-bearing, keep it dumb and testable)

`_redact(text, patient)` — plain string ops, no NLP: replace the
patient's name (and each name token ≥3 chars), phone, mobile, email,
street/vietnamese_address values with `[BN]` / `[SĐT]` / `[EMAIL]` /
`[ĐC]`; collapse whitespace; truncate to
`health_ai_coding.max_prompt_chars` (default 4000). Html fields
through `html2plaintext` first. The SAME redacted string goes to the
LLM and into the log — the un-redacted note text must never leave the
note. (This is pseudonymization, not anonymization — say so in the
module description; the sovereignty default below is the real
control.)

### 2.4 Provider + sovereignty config

`health_ai_coding.provider_id` → a `bi.ai.provider` id (Settings
selector, biz_bi dep). HARD RULE: if the chosen provider's
`provider != 'ollama'` and `health_ai_coding.allow_cloud` (default
**False**) is not set, the sweep refuses (one warning log line, no
calls). `health_ai_coding.enabled` default **False** — installing
changes nothing until ops flips it. System prompt: fixed in code
(vi+en; "suggest ICD-10 codes present in the text; JSON array of
{code, confidence 0-1, evidence ≤20 words verbatim from the text};
[] when nothing is codable; never invent codes").

### 2.5 `health.ai.coding.log` (bi.ai.log clone)

note_id, provider_id, request_json (system+user, redacted),
response_json (raw), duration_ms, suggested_count, dropped_codes,
error. Append-only (write/unlink blocked incl. for admin — bi
precedent), READ manager+ only (the prompt text is still
pseudonymized PHI). Suggestions reference their log row.

### 2.6 Review UI

List view default-filtered state=suggested, grouped by note/patient,
columns: patient, note date, code display ([code] display_vi),
confidence (percentpie or progressbar), evidence, buttons
Approve/Reject; multi-select header button "Approve selected". Form
view shows the note's free text alongside (readonly) — the clinician
judges against the source. Menu under the clinical area next to
Clinical Notes (inspect where health_fieldservice puts them). A
smart-button/count on the clinical note form ("AI codes: N pending").
Flat mono styling, no emoji.

## 3. Module skeleton

Depends `['biz_bi', 'health_fhir_terminology', 'health_consent',
'health_fieldservice']`. Config params per §2.4 + batch_cap +
max_prompt_chars. ACLs: suggestions read nurse+ (they see their
visits' rows via catchment rule), write/approve doctor+head-nurse+,
unlink manager+; log read manager+ only. vi.po.

## 4. Tests (`tests/test_ai_coding.py`)

Mock at `bi.ai.provider._complete` (patch the method; never a real
HTTP call). Cases:
1. Gate matrix: enabled=False → sweep does nothing; consent False →
   note skipped + attempted, zero suggestion rows; cloud provider +
   allow_cloud=False → refused, zero calls (assert the mock was NOT
   called).
2. Redaction: patient name/phone/address absent from the captured
   prompt (assert on the mock's call args AND on the log row);
   html stripped; truncation at max_prompt_chars.
3. Happy path: mocked JSON with 2 valid + 1 bogus code → 2 suggestion
   rows, bogus dropped and counted in the log, note ai_attempts
   untouched by success (or reset — your call, report it).
4. Robustness: malformed JSON → attempt++, no crash, log row with
   error; provider raising → same; savepoint isolation (note 2 of 3
   poisoned → 1 and 3 still processed); attempts ≥3 → excluded.
5. Dedup: re-sweep creates nothing new; a code already on
   condition_code_ids is never suggested; (note, code) unique via
   search-first.
6. Approve: doctor approves → code lands in condition_code_ids +
   state/reviewer stamped; plain nurse calling action_approve →
   AccessError (server-side guard, not just view); batch approve with
   one failing row → others succeed.
7. Reject: state only, sidecar untouched.
8. Log immutability: write/unlink on a log row raises even as admin.
9. Batch cap respected (cap=2, 3 eligible notes → 2 processed).

## 5. Deploy & verify

- `-i health_ai_coding --test-tags /health_ai_coding` (+ re-run
  `/health_fieldservice`? NO — too broad; instead re-run
  `/health_family_link` which reads clinical notes, proving the
  ai_attempts inherit broke nothing). Port-wait loop after stop;
  read results from the logfile and check the timestamp is YOUR run.
- Live verify on vietuat: report the medical.code icd10 row count;
  check for a usable bi.ai.provider (Ollama is NOT expected on the
  server) — with none, demo = flip enabled on, run the sweep, show it
  ending green with attempt-marked notes and a clean error log row,
  then flip enabled OFF; hand-seed one suggestion on a demo note and
  screenshot/describe the review list + an approve landing the code
  in condition_code_ids. Final switch positions: `enabled=False`,
  `allow_cloud=False`, provider unset or Ollama.
- vi.po, conventions §8, commit+push on 19.0.

## 6. Report-back extras

(a) final param positions + icd10 catalog count on vietuat; (b) the
demo note/suggestion ids + the approve trail (sidecar before/after);
(c) the exact system prompt shipped; (d) redaction test evidence (one
captured prompt, quoted); (e) whether ai_attempts resets on success
and why; (f) any new ledger-grade gotcha (explicitly flagged).
