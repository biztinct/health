# Clinical status mappings — Odoo state → FHIR R4 code

**Instrument owner:** clinical lead (signature block at the end).
**Engineering status:** generated from the shipped mapping tables, Phase GC-2
(register item **G17**). **Version of the code it describes:**
`health_fhir_core` 19.0.1.4.0, `health_condition` / `health_fhir_terminology`
as deployed on `vietuat`, 2026-08-02.

---

## What this document is for

Every clinical resource the FHIR facade serves carries a **status** with a
*required* binding — a fixed ValueSet in the R4 specification. Our records do
not have FHIR statuses; they have Odoo workflow states. Somewhere in the
middle a human decided that, for example, an `in_progress` visit is FHIR
`in-progress` but a `completed_pending_invoice` visit is `finished` and not
something else. **Those decisions are clinical, not technical**, and they are
what a receiving system will act on: a partner EMR that reads
`Encounter.status = finished` will close the episode.

This table exists so a clinician can check every one of those decisions in one
pass and sign that they are right.

## How to read it, and what is guaranteed

- **Odoo state** is the literal stored value; **FHIR code** is what the facade
  emits for it. `→` is one-way: the facade is read-only.
- Several Odoo states may map onto one FHIR code (`completed`,
  `completed_pending_invoice` and `closed` are all `finished`). That is
  expected — FHIR's ValueSets are deliberately coarser than an operational
  workflow, and the billing distinction is not a clinical one.
- **Search is the reverse map.** Where a client can filter (`?status=finished`),
  the reverse map is asserted to be consistent with the forward map by the same
  tests. A FHIR code that maps back to several states searches all of them.
- Every FHIR code below is asserted to be a member of its R4 required binding
  by `health_fhir_core/tests/test_fhir_bindings.py` (14 tables). **The values
  in this document cannot drift from the code without a test going red** —
  that test imports the same dictionaries this table was written from.
- A default appears in each table where the serializer falls back for an
  unknown state; it exists so an unmapped future state cannot emit an invalid
  code, not because it is expected to be used.

---

## 1. Encounter — the visit that happened

`health.fieldservice.order.state` → `Encounter.status`
(`serializers/fso_common.py`, `ENCOUNTER_STATUS_MAP`)

Only visits from `assigned` onwards exist as Encounters at all; the scheduling
states are served as Appointments instead (an Encounter that never happened
would be a false clinical record).

| Odoo state | FHIR code | Rationale |
|---|---|---|
| `draft` | `planned` | booked but not staffed — only reachable via Appointment |
| `confirmed` | `planned` | agreed with the family, nobody assigned yet |
| `assigned` | `planned` | staffed, not started: the visit is expected, not underway |
| `in_progress` | `in-progress` | the nurse is with the patient |
| `completed` | `finished` | care delivered |
| `completed_pending_invoice` | `finished` | care delivered; the outstanding step is billing, not clinical |
| `closed` | `finished` | administratively closed after delivery |
| `cancelled` | `cancelled` | the visit did not happen |

Default for an unmapped state: `planned`.

## 2. Appointment — the planned slot

`health.fieldservice.order.state` → `Appointment.status`
(`fso_common.py`, `APPOINTMENT_STATUS_MAP`) — all states, including the ones
Encounter excludes.

| Odoo state | FHIR code | Rationale |
|---|---|---|
| `draft` | `proposed` | offered, not agreed |
| `confirmed` | `booked` | agreed with the family |
| `assigned` | `booked` | agreed and staffed — still a booking |
| `in_progress` | `arrived` | the clinician is at the home; R4's `arrived` is the closest member |
| `completed` | `fulfilled` | the appointment was kept |
| `completed_pending_invoice` | `fulfilled` | kept; billing pending |
| `closed` | `fulfilled` | kept and closed |
| `cancelled` | `cancelled` | called off. **Note:** we do not distinguish a patient no-show (`noshow`) — the operational model has no such state. See the open question below. |

Default: `proposed`.

## 3. ServiceRequest — the order behind the visit

`health.fieldservice.order.state` → `ServiceRequest.status`
(`fso_common.py`, `SERVICE_REQUEST_STATUS_MAP`)

| Odoo state | FHIR code | Rationale |
|---|---|---|
| `draft` | `draft` | not yet an order |
| `confirmed` | `active` | ordered |
| `assigned` | `active` | ordered, being fulfilled |
| `in_progress` | `active` | being fulfilled |
| `completed` | `completed` | fulfilled |
| `completed_pending_invoice` | `completed` | fulfilled |
| `closed` | `completed` | fulfilled |
| `cancelled` | `revoked` | withdrawn after being issued (R4 `revoked`, not `entered-in-error`, which means "should never have existed") |

Default: `active`.

## 4. Observation — vitals and measurements

`health.observation.state` → `Observation.status`
(`serializers/observation.py`, `_STATE_TO_STATUS`)

| Odoo state | FHIR code | Rationale |
|---|---|---|
| `preliminary` | `preliminary` | recorded, not verified |
| `final` | `final` | verified and released |
| `amended` | `amended` | corrected after release |
| `entered_in_error` | `entered-in-error` | retracted; kept for audit, must not be acted on |

Default: `final`.

## 5. CarePlan

`health.careplan.state` → `CarePlan.status` (`serializers/careplan.py`,
`_CAREPLAN_STATUS`)

| Odoo state | FHIR code | Rationale |
|---|---|---|
| `draft` | `draft` | being written |
| `active` | `active` | in force |
| `under_review` | `active` | **still in force while it is reviewed** — a plan under review governs care today; `on-hold` would tell a partner to stop following it |
| `completed` | `completed` | goals concluded |
| `cancelled` | `revoked` | withdrawn |

Default: `active`. Search: `active` matches both `active` and `under_review`.

### 5b. CarePlan activity detail

`health.careplan.activity.status` → `CarePlan.activity.detail.status`

| Odoo state | FHIR code |
|---|---|
| `not_started` | `not-started` |
| `scheduled` | `scheduled` |
| `in_progress` | `in-progress` |
| `completed` | `completed` |
| `cancelled` | `cancelled` |

## 6. Goal

`health.careplan.goal.lifecycle_status` → `Goal.lifecycleStatus`
(`careplan.py`, `_GOAL_LIFECYCLE`)

| Odoo state | FHIR code | Rationale |
|---|---|---|
| `proposed` | `proposed` | suggested, not agreed with the patient/family |
| `active` | `active` | being worked towards |
| `on_hold` | `on-hold` | paused (e.g. an acute admission) |
| `completed` | `completed` | achieved or concluded |
| `cancelled` | `cancelled` | abandoned |

Default: `proposed`. Achievement (`in-progress`/`improving`/`worsening`/
`achieved`/`not-achieved`) is a separate element and is emitted only when the
clinician has set it.

## 7. Task — care-plan tasks

`health.careplan.task.state` → `Task.status` (`careplan.py`, `_TASK_STATUS`)

| Odoo state | FHIR code | Rationale |
|---|---|---|
| `pending` | `requested` | asked for, not yet done |
| `done` | `completed` | performed |
| `not_done` | `failed` | **not performed.** R4 has no "declined by patient" member of TaskStatus; the reason (patient refused / not clinically indicated / no time) is carried in `Task.statusReason` and must be read there — `failed` alone does not mean an error occurred. |

Default: `requested`.

## 8. MedicationRequest — prescriptions

`health.medication.order.state` → `MedicationRequest.status`
(`serializers/medication.py`, `_REQUEST_STATUS`)

| Odoo state | FHIR code | Rationale |
|---|---|---|
| `draft` | `draft` | not issued |
| `active` | `active` | current prescription |
| `on_hold` | `on-hold` | suspended, expected to resume |
| `completed` | `completed` | course finished |
| `cancelled` | `cancelled` | withdrawn |

Default: `active`.

## 9. MedicationAdministration — what was actually given

`health.medication.administration.state` → `MedicationAdministration.status`
(`medication.py`, `_ADMIN_STATUS`)

`planned` rows are never served (a planned dose is not an administration
event); the facade's base domain excludes them.

| Odoo state | FHIR code | Rationale |
|---|---|---|
| `given` | `completed` | administered |
| `not_given` | `not-done` | the dose was not administered; the reason is in `statusReason` |
| `refused` | `not-done` | **the patient refused.** R4 has one code for both; the distinction survives in `statusReason` and must be read there before any clinical inference |
| `cancelled` | `stopped` | the administration was stopped |

Default: `completed`. Search: `not-done` matches both `not_given` and
`refused`.

## 10. QuestionnaireResponse — completed assessment forms

`health.form.instance.state` → `QuestionnaireResponse.status`
(`serializers/questionnaire.py`, `_INSTANCE_STATUS`)

| Odoo state | FHIR code | Rationale |
|---|---|---|
| `draft` | `in-progress` | started, not submitted |
| `completed` | `completed` | submitted |
| `amended` | `amended` | corrected after submission |
| `cancelled` | `stopped` | abandoned before completion |

Default: `in-progress`.

## 11. Questionnaire — the form templates

`health.form.template.state` → `Questionnaire.status` (`questionnaire.py`,
`_TEMPLATE_STATUS`). Drafts are never served — an unpublished template is not
a public contract.

| Odoo state | FHIR code |
|---|---|
| `published` | `active` |
| `retired` | `retired` |

## 12. Consent

`health.consent.state` → `Consent.status` (`serializers/consent.py`,
`_STATUS`). Drafts are never served — a draft consent is not evidence.

| Odoo state | FHIR code | Rationale |
|---|---|---|
| `active` | `active` | in force |
| `withdrawn` | `inactive` | revoked by the patient/family |
| `expired` | `inactive` | lapsed by date |

Default: `inactive` (deny-by-default: an unrecognised consent state must never
read as `active`). Search: `inactive` matches both `withdrawn` and `expired`.

## 13. Flag — standing fall risk

`health.fall.risk` → `Flag.status` (`serializers/adverse_event.py`). Only
HIGH-band Morse assessments become Flags at all.

| Condition | FHIR code | Rationale |
|---|---|---|
| this is the patient's most recent assessment | `active` | the flag reflects current risk |
| a later assessment exists (any band) | `inactive` | superseded — a stale high-risk flag alongside a newer low-risk assessment would be actively misleading |

## 14. Condition — the problem list

`health.condition.clinical_status` → `Condition.clinicalStatus`
(`health_condition/serializers/condition.py`; the Selection *is* the mapping —
the values are stored as FHIR codes).

| Odoo value | FHIR code | Rationale |
|---|---|---|
| `active` | `active` | a current problem |
| `inactive` | `inactive` | not currently active, not formally resolved |
| `resolved` | `resolved` | clinically resolved |

R4's `recurrence`, `relapse` and `remission` are legal members we do not use;
adding one is a model change (a new Selection value), not a mapping change.

---

## Open questions for the clinical lead

These are the places where the mapping is a judgement call and a different
answer is defensible. Please confirm or correct each:

1. **`under_review` care plans are served as `active`** (§5). The alternative
   is `on-hold`, which tells a receiving system to stop acting on the plan.
2. **A cancelled appointment is always `cancelled`, never `noshow`** (§2). If
   the difference matters clinically, it needs an operational state first.
3. **A refused dose and a missed dose are both `not-done`** (§9), separated
   only by `statusReason`. This is forced by R4; the question is whether the
   `statusReason` text we send is clinically sufficient.
4. **A not-done task is `failed`** (§7) — the least-bad member of R4's
   TaskStatus. Confirm this cannot be misread as a clinical incident.
5. **`completed_pending_invoice` is clinically `finished`/`fulfilled`**
   (§1, §2, §3). Confirm that a billing-pending visit should read as complete
   to an external clinical system.

---

## Sign-off

By signing, the clinical lead confirms that each Odoo state → FHIR code
decision above is clinically correct for external exchange, and that the open
questions have been answered.

| | |
|---|---|
| **Name** | ______________________________________ |
| **Role / registration no.** | ______________________________________ |
| **Signature** | ______________________________________ |
| **Date** | ______________________________________ |

Return the signed copy to the regulatory dossier. This closes the operational
half of register item **G17** (§10.11 of
`docs/strategy/hl7-fhir-compliance-response.html`); the engineering half — the
mappings, their tests and this document — closed with Phase GC-2.
