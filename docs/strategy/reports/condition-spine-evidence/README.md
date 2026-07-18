# Condition-Spine — Browser + API Evidence Pack

Deployed to **vietuat** (care.biztinct.com), health_condition 19.0.1.0.0.
Backend-only phase (no PWA assets → no PWA version bump).

## Screenshots
- `01-problem-list.png` — the **Diagnoses** list (menu: Healthcare → Diagnoses),
  showing the two backfilled problem-list entries for *Demo Patient - Hanoi*:
  `[E11] Đái tháo đường típ 2` and `[I10] Tăng huyết áp vô căn (nguyên phát)`,
  both **Active / Confirmed**, recorded Jul 8, evidence count 1.
- `02-condition-form.png` — the Condition form for the I10 record:
  **Mark Resolved / Mark Inactive** header buttons + Active/Inactive/Resolved
  statusbar; **Diagnosis** group (Patient, ICD-10 Code, Verification Status)
  and **Provenance** group (Recorded Date, Last Asserted, Recorder = Viet Uc
  Care, Catchment Area = TPHCM, all readonly); **Evidence Notes** tab listing
  the single asserting note (Demo Patient BK1326, Jul 8 10:27); **chatter at
  bottom full-width** — "Condition / Diagnosis (Problem List) created".

## Real-user navigation path
Healthcare backend → top menu **Diagnoses** (`health_condition.action_health_condition`,
under `health_base.menu_healthcare_root`, seq 29) → list → click a row → form.
NOT a deep link — the menu is the normal entry point.

## Console
`list_console_messages(error,warn)` on the form → **no console messages**.

## Backfill (post_init_hook, first `-i` install)
```
health_condition backfill: 1 coded notes → 2 problem-list records created (2 total now).
```
Honest small number (only the seeded coded note on vietuat carries ICD-10 codes).

## CapabilityStatement (`GET /fhir/r4/metadata`)
21 resources total (was 20); Condition listed with interactions read +
search-type and search params `patient`, `code`, `clinical-status`,
`recorded-date` (+ framework `_lastUpdated`, `_count`).

## Sample Condition FHIR JSON
See `condition-sample.json` — health.condition id 2 (I10) serialized via
`ConditionSerializer.to_fhir`: ICD-10 coding, Vietnamese-first `text`,
`subject` Patient/861, `recordedDate` 2026-07-08, `evidence.detail` →
DocumentReference/104.

## Patient/$everything (patient 861)
`build_everything_bundle` returns 27 entries composing
`{Patient:1, Appointment:9, Condition:2, Consent:2, DocumentReference:1,
Encounter:3, ServiceRequest:9}` — **2 Condition entries (E11, I10)**, all
`subject` Patient/861, picked up automatically by the compartment convention
(zero everything.py edits).
