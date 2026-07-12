# Phase handover: emr-record-spine — legally-valid EMR notes (finalize + sign-off + immutability + integrity seal)

**Stream:** FHIR gateway + VNeID identity + **Circular 13/2025/TT-BYT EMR compliance**.
**Designer + implementer:** Opus 4.8 (self-handover — I design, code, then submit to an
independent review agent per the retained review gate). Read
`docs/strategy/HANDOVER-CONVENTIONS.md` in FULL first (§3 PWA version bump,
§4 sanctioned edits, §5.1/§5.4 unconditional-guard + evidence-lock precedent,
§5.32 HttpCase pin). This is **Phase 1 of the stream**; the holistic plan is §6.

---

## §0 Why this phase first (scope rationale)

The scout established that the FHIR + VN-export + audit + consent + terminology
infrastructure is already live and correct. The narrow, real Circular-13 gaps
are: (1) clinical notes are **fully mutable — no finalization, no signature, no
immutability** (`health.clinical.note` in health_fieldservice has no `state`,
no `signed_by`, no write/unlink guard); (2) no digital-signature (VNPT-CA);
(3) consent is validated in the VN export but not enforced in the read facade;
(4) no BHYT 4210 XML; (5) VNeID is a manual Boolean, no OIDC.

Circular 13/2025 (bệnh án điện tử) is fundamentally a **legally-valid,
signed, immutable medical record** mandate. Without finalization + immutability,
health19 has editable scratch notes, not an EMR — so this is the **foundation
every later piece attaches to**: the CA digital signature (Phase 3) signs a
*finalized* record + its integrity hash; consent-gating and profile validation
assume a stable record. Hence this is Phase 1, and it is buildable with **zero
external dependencies** (the CA vendor integration is deliberately deferred).

## §0.1 Scope (binding)

A NEW module **`health_emr`** that `_inherit`s `health.clinical.note` and adds:

1. **Finalization state machine** — `emr_state` Selection `draft → final`
   (default `draft`), with `action_finalize()` capturing `signed_by_id`
   (res.users), `signed_role` (snapshot Char), `signed_datetime`.
2. **Immutability after finalize** — a `write()` guard locking the clinical
   content + signature fields once `emr_state == 'final'` (clone the
   `health.consent` evidence-lock: `EMR_LOCKED_FIELDS`, filtered to non-draft,
   NO superuser escape — §5.4); `unlink()` draft-only for everyone incl.
   superuser (finalized records are archived, never deleted).
3. **Tamper-evident integrity seal** — at finalize, compute a `content_hash`
   (sha256 over a deterministic canonical serialization of the locked content
   fields + note id + signer + signed_datetime) and store it read-only. This
   is the anchor the Phase-3 CA signature signs. Clone the deterministic-hash
   discipline from `fhir.adapter.vn` (sha256, stable key order) and the
   append-only spirit of the EVV hash chain.
4. **Addendum mechanism (correction without overwrite)** — `amends_note_id`
   self-reference (Many2one to health.clinical.note). A finalized note is
   immutable; a correction is a NEW note with `amends_note_id` set to the
   original (which stays locked). This is the legally-required "never
   overwrite clinical data, append corrections" rule (architecture §6.7).
   FHIR reflects it as `DocumentReference.relatesTo{code:'appends'}`.
5. **FHIR reflection** — the health_fhir_core DocumentReference serializer
   emits `docStatus` (`preliminary` for draft, `final` for finalized) and
   `relatesTo` for addenda, and lists the signer as `authenticator`. Because
   health_fhir_core must NOT depend on health_emr, the serializer reads the
   new fields **defensively** (`if 'emr_state' in note._fields`) — exactly the
   pattern already used there for `if 'employee_id' in user._fields`.
6. **Backend UI** — finalize button + signed banner on the note form;
   finalized notes render content read-only. Ops list shows an
   EMR-status column.
7. **PWA — SPLIT to Phase 1.5 (NOT this phase).** Scope refinement: the
   point-of-care "Finalize & sign" affordance (endpoint + app.js UI + read-only
   render + PWA version bump + browser QA) is its own immediate follow-up so the
   security-critical backend lands and is reviewed on its own, and the complex
   app.js change gets a dedicated careful pass. Finalization will be
   ONLINE-ONLY there (offline edits drafts; signing is server-authoritative).
   **Phase 1 ships NO health_pwa change and needs NO PWA version bump.**

### §0.2 Binding NON-goals
- NO VNPT-CA / Viettel-CA digital signature yet (Phase 3) — the `content_hash`
  is the anchor it will later sign; ship a `signature_ref` placeholder field
  (Char, empty now) so Phase 3 adds no schema churn.
- NO offline finalization/signing.
- NO consent-gating of the read facade (Phase 2).
- NO change to the note-CREATE paths (PWA api.py/sync.py create drafts as
  today; `emr_state` defaults to draft — those five call sites are untouched).
- NO edit to health_fieldservice's note model file beyond what an `_inherit`
  in health_emr requires (i.e. health_fieldservice stays untouched;
  health_emr owns all additions).
- `health.clinical.note` free-text fields are NEVER removed (§4.11).

## §1 Verified plumbing facts (do NOT re-derive)

1. `health.clinical.note` is defined in
   `health_fieldservice/models/health_clinical_note.py` — current fields:
   `order_id`(m2o req, ondelete cascade), `author_id`(m2o res.users, default
   uid, readonly), `author_name`/`author_role`, the content fields
   `clinical_notes`(Html), `diagnosis`/`treatment_performed`/
   `medications_prescribed`/`vital_signs`/`patient_condition_before`/
   `patient_condition_after`(Text), the four `*_count` Integers,
   `image_ids`(m2m ir.attachment), `display_name`. **NO state/sign/lock.**
   Note: `clinical_notes` + the narrative Texts are **PHI-encrypted computes**
   in health_phi_encryption (decrypt transparently via ORM) — the hash reads
   them through the ORM (never raw SQL), same as `fhir.adapter.vn`.
2. Immutability precedent to CLONE — `health_consent/models/health_consent.py`:
   `EVIDENCE_LOCKED_FIELDS` tuple; `write()` (≈:333-349) does
   `locked=[f for f in EVIDENCE_LOCKED_FIELDS if f in vals]; if locked:
   frozen=self.filtered(lambda c: c.state!='draft'); if frozen: raise
   UserError(...)`; `unlink()` (≈:353+) `frozen=self.filtered(state!='draft');
   if frozen: raise`. The docstrings note the NO-superuser-escape rationale
   (uid 1 forces su=True) — replicate verbatim in spirit.
3. Notes are created (as drafts, no change needed) from
   `health_pwa/controllers/sync.py:920` (offline replay) and
   `health_pwa/controllers/api.py:800,850,966,1018`. Whitelisted-field creates;
   `emr_state` default draft slots in with zero edits to these.
4. DocumentReference serializer =
   `health_fhir_core/serializers/document_reference.py`:
   `odoo_model='health.clinical.note'`, `to_fhir(note)` hardcodes
   `status:'current'`, `type.text='Clinical visit note'`, subject=Patient,
   context.encounter=order. It ALREADY reads fields defensively
   (`if 'employee_id' in user._fields`). Add `docStatus`/`relatesTo`/
   `authenticator` guarded by `'emr_state' in note._fields`. `to_fhir` has NO
   `self.env` — use `note.env` (base serializer pattern, base.py:225-262).
   `patient_ids_of` returns `records.mapped('order_id.patient_id').ids`.
5. Serializer registry = `health_fhir_core/serializers/__init__.py` REGISTRY
   dict `{resource_type: instance}`. Editing the DocumentReference serializer
   needs NO registry change (same instance). Capability count tests: adding a
   FIELD to an existing resource does NOT change the resource count, so no
   capability-count test breaks (unlike adding a resource — the §807135fd
   gotcha).
6. FHIR `DocumentReference.docStatus` valueset (R4): `preliminary | final |
   amended | entered-in-error`. `relatesTo.code`: `replaces | transforms |
   signs | appends`. Use `docStatus=preliminary|final` and
   `relatesTo.code=appends` for addenda.
7. Deterministic-hash precedent = `health_fhir_adapter_vn/models/
   fhir_adapter_vn.py` (sha256 over sorted resources, timestamp EXCLUDED from
   the hash). Mirror: exclude volatile/unstamped fields; hash a fixed key
   order; store the hash + an explicit `hash_version` Char for future
   algorithm changes.
8. Current PWA version **1.14.0** / manifest health_pwa **19.0.1.0.31**. Version
   spots: `health_pwa/views/pwa_templates.xml` :9,:246,:365,:851,:854; pin
   suites health_pwa_daystrip/health_scribe/health_pwa_family test files. This
   phase bumps to **1.15.0** / **19.0.1.0.32** (PWA JS changes for the finalize
   affordance).
9. New module conventions (§4): `health.*` namespace, `_description`,
   mail.thread + mail.activity.mixin on user-facing records, `tracking=True`
   on `emr_state`/signature fields; own `health_emr_user`/`_manager` groups
   OR reuse `health_base.group_healthcare_*` (finalize = nurse+; unlink/admin
   = head_nurse+). New module version starts `19.0.1.0.0`. Ship `i18n/vi.po`.
10. §5.1 — materialize any unique index in `init()`. (Likely none needed here;
    `amends_note_id` is a plain m2o. If a per-note single-final constraint is
    wanted it's state logic, not a DB index.)

## §2 Sanctioned edits (exhaustive)

| File / module | What |
|---|---|
| `health_emr/` (NEW module) | manifest (depends health_fieldservice, health_base; version 19.0.1.0.0), models/health_clinical_note.py (`_inherit`, all new fields + state machine + write/unlink guards + hash + action_finalize + addendum), security/ir.model.access.csv (+ record rule reuse), views (form inherit: finalize button/banner/read-only, list column), i18n/vi.po, tests/ |
| `health_fhir_core/serializers/document_reference.py` | ADD defensive `docStatus` + `relatesTo` (addenda) + `authenticator` (signer) — guarded by `'emr_state' in note._fields`. Nothing else. |
| `health_emr/tests/test_emr.py` | FHIR reflection test (guarded + lazy-import — coupling lives with health_emr; health_fhir_core stays independent) |

**Phase 1.5 (deferred, NOT this phase):** `health_pwa/controllers/api.py`
(finalize endpoint), `health_pwa/static/src/js/app.js` (affordance + read-only
render + VN strings), `pwa_templates.xml`/`__manifest__.py` + pin suites
(version bump). No health_pwa change in Phase 1.

Everything else READ-ONLY. health_fieldservice's note model file is NOT edited
(health_emr inherits it). health_phi_encryption untouched (its computes serve
the hash through the ORM).

## §2.1 Architecture detail

`action_finalize()` (on health.clinical.note via health_emr):
```
ensure the note is draft (else UserError 'already finalized');
require content present (at least one clinical field non-empty);
set emr_state='final', signed_by_id=env.user, signed_role=<snapshot>,
    signed_datetime=now();
content_hash = sha256(canonical_json({id, order_id, author_id,
    <each locked content field, ORM-read>, signed_by_id, signed_role,
    signed_datetime.isoformat()}));  hash_version='v1';
post a mail.thread message 'Finalized & signed by <user> at <ts>' (tracking).
```
`EMR_LOCKED_FIELDS` = the seven narrative/text fields + four counts +
`image_ids` + signature fields. `write()` guard: if any locked field in vals
AND record is `final` → UserError. State/addendum fields stay writable through
actions only. `amends_note_id`: settable only on a DRAFT note, and only
pointing at a `final` note of the SAME `order_id.patient_id` (constrain).

## §3 Tests (health_emr/tests, TransactionCase unless noted)

1. **finalize sets state+signer+hash**: create draft note → action_finalize →
   emr_state final, signed_by_id=uid, signed_datetime set, content_hash
   non-empty + 64 hex chars, mail message posted.
2. **immutability**: finalized note → write on a locked field raises UserError;
   write on a NON-locked field (e.g. an ops annotation if any) allowed; a DRAFT
   note writes freely.
3. **no superuser escape**: same write as SUPERUSER_ID still raises (uid 1 su).
4. **unlink guard**: finalized note unlink raises; draft note unlink ok.
5. **hash determinism + tamper-evidence**: finalize two notes with identical
   content → different hashes (different id/signer/ts); recomputing the hash
   over the stored locked content EQUALS content_hash (seal verifies); mutating
   a locked field via raw SQL then recomputing DIFFERS (tamper detectable).
6. **addendum**: create draft addendum with amends_note_id→finalized note ok;
   amends_note_id pointing at a DRAFT note raises; cross-patient raises;
   original stays locked/unchanged.
7. **finalize guards**: empty note (no content) → finalize raises; double
   finalize → raises.
8. **FHIR docStatus** (in health_fhir_core/tests, guarded): finalized note →
   DocumentReference.docStatus=='final' + authenticator present; draft →
   'preliminary'; addendum → relatesTo[0].code=='appends'.
9. **PWA finalize endpoint** (HttpCase): assigned nurse finalizes own note →
   200 + state final; a NON-assigned nurse → denied, no state change (G1).
   §5.32: this does NOT complete a visit, so no timecard pin needed — but
   VERIFY the finalize path doesn't trip the E.4 hook; pin if it does.

Browser QA (chrome-devtools MCP, care.biztinct.com, `ds_qa_nurse`): finalize a
note in the PWA → signed chip + read-only; version 1.15.0 served; console clean;
**revert QA state in a FRESH cursor (§5.34)**.

## §4 Deploy

Conventions §2. New module: `-i health_emr -u health_fhir_core`.
Test tags `/health_emr,/health_fhir_core`. Also upgrade the modules that
create notes so their suites exercise the model with mail.thread + emr_state
added: add `-u health_fieldservice,health_pwa` and their tags to catch any
regression from the mixin. HttpCase present ⇒ NO `--no-http`. Result line from
the log (`grep -a`), matched to my timestamp. Restart + login 200.
**Safety rails (fact-11) remain binding. No PWA version bump this phase.**

## §5 Report-back (self-review agent)

Independent review agent verifies: sanction-exact file list; health_fieldservice
note model byte-unchanged; the write/unlink guards have NO superuser escape
(the single most important security property — an EMR whose signed records can
be silently altered is worse than none); hash determinism + tamper-detection;
DocumentReference defensive guard doesn't break when health_emr absent;
independent test re-run; PWA 1.15.0 served; QA state reverted (fresh cursor);
fact-11 params intact.

## §6 Holistic stream plan (context — not this phase)

- **Phase 1 — EMR record spine** (THIS): finalize + sign-off + immutability +
  integrity seal + addendum + FHIR docStatus + PWA finalize. Zero external deps.
- **Phase 2 — Consent-gated facade + identity/audit completeness**: wire
  `check_consent()` into health_fhir_core read/search (deny-by-default for
  national data-sharing per architecture §6.6), update the readiness wizard to
  cite Circular **13/2025** explicitly (currently Circular 54), harden VNeID
  capture beyond the Boolean.
- **Phase 3 — Digital signature (VNPT-CA / Viettel-CA)**: legal e-signature
  over the Phase-1 `content_hash`; remote-signing/USB-token, cloning the
  Viettel SInvoice vendor pattern (`signature_ref` fills in). **Open question
  to confirm before Phase 3: which CA vendor the customer uses.**
- **Phase 4 (market/portal-gated, deferred)**: BHYT Decision-4210 XML claims;
  VN FHIR StructureDefinition profile pack; VNeID OIDC "Login with VNeID"
  (needs the patient portal, which doesn't exist yet).
