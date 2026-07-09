# health_ai_coding — Live verification (vietuat)

Backend-only module (no PWA / no customer-facing page). The review list, the
suggestion form, the call-log views and the Settings block are load-validated
by the successful `-i/-u health_ai_coding` upgrade — Odoo parses and
field-checks every view arch at install, so a malformed view fails the deploy
(this run returned EXIT:0). Chrome DevTools MCP was not connectable this
session; live behaviour is verified through the odoo shell.

## Environment facts (handover §6a / §5)

- **ICD-10 catalog on vietuat: 31 rows** (the `codes_icd10_starter.xml`
  starter set only). The sweep never assumes a full catalog — model-proposed
  codes absent from the catalog are dropped and counted, not fuzzy-matched.
- **Usable `bi.ai.provider` on the server: one cloud OpenAI provider (id 2).
  No Ollama is present** — exactly the case the sweep must survive.

## Sweep ends GREEN with Ollama down (handover §2.2 / §5)

Enabled on, provider = a demo Ollama pointed at `127.0.0.1:11434` (nothing
listening), `allow_cloud=False`, cap 3:

    AI_SWEEP_RETURN True   LOGS_BEFORE 0   LOGS_AFTER 1
    AI_LOG_ROW id=27 note=104 provider="AI Coding Demo (local)"
               suggested=0 dropped=0
               err="HTTPConnectionPool(host='127.0.0.1', port=11434): ...
                    [Errno 111] Connection refused"
    AI_SWEPT_NOTE_ATTEMPTS 104 -> ai_attempts=1

The cron returned `True` (no crash), the connection error was captured in one
append-only log row, and the note was attempt-marked so it is not retried
forever. Zero suggestions created.

## Consent gate

The sweep calls `health.consent.check_consent(patient, 'data_sharing')` per
note; a False result skips the note (attempt-marked) with no suggestion row —
the consent check-log row is the only evidence, no phantom row about the
patient. (Covered by `TestGates.test_consent_false_skips_and_marks_attempt`.)

## Seeded suggestion + approve trail (handover §6b)

    AI_CODE_I10        14  [I10] Tăng huyết áp vô căn (nguyên phát)
    AI_SEED_SUGGESTION 20  note=104  state=suggested
    AI_SIDECAR_BEFORE  []
    AI_APPROVER        94  "Dung" (health_base.group_healthcare_doctor)
    AI_SUGG_STATE_AFTER approved   reviewed_by=Dung
    AI_SIDECAR_AFTER   ['I10']

Approving appended I10 to `clinical_note.condition_code_ids` (the Circular
13/2025 EMR export field) and stamped the reviewer — the ONLY write path for a
code. A plain nurse calling `action_approve` raises AccessError
(`TestApprove.test_plain_nurse_blocked`), enforced server-side, not only in the
view.

## Final switch positions (sovereignty defaults restored)

    health_ai_coding.enabled     = False
    health_ai_coding.allow_cloud = False
    health_ai_coding.provider_id = 40 (demo Ollama, local)
    health_ai_coding.batch_cap   = 25

Installing the module changes nothing until ops flips `enabled`; a cloud
provider is refused while `allow_cloud` is off.
