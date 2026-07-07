# health_incident — Incident / Adverse Event Management

Adverse-event capture, investigation workflow (reported → under_review →
investigation → actions_assigned → closed), corrective actions with
deadline activities, notifiable-incident register (AU SIRS-style,
generic), fall-incident → Morse reassessment hook, and a PWA
"Report Incident" quick-capture flow with an offline queue
(`client_mutation_id` idempotency). Born-FHIR: `health.incident` maps
1:1 to `AdverseEvent` (+ a derived standing `Flag` for open fall /
severity ≥4 incidents); `health.incident.action` maps to `Task`.

## PHI note (future encryption candidate)

The narrative fields on `health.incident` — `description`,
`immediate_actions`, `investigation_notes`, `root_cause`,
`contributing_factors`, `witnesses` and `location` — are **plain
(unencrypted) module-local fields**. Unlike partner / clinical-note
narratives (encrypted computed fields, ORM-only), incident narratives
are not yet covered by the platform PHI-encryption pattern. They are
flagged as candidates for the phi-encryption rollout; do not add new
integrations that assume raw SQL access to these columns.

## Integration touchpoints

- `health.fall.risk` (health_base): fall incidents schedule a Morse
  reassessment activity for the facility head nurse (no assessment row
  is auto-created — assessments need a human).
- `health.fieldservice.order`: `order_id` context link (FHIR encounter).
- `health_emar` (later): medication_error incidents should become
  creatable from a refused/not-given administration — note only, no
  code here.
- PWA: scripts injected via QWeb inheritance of `health_pwa.app_shell`;
  every deploy requires the health_pwa version bump (3 places in
  `pwa_templates.xml`).
- Configurable notifiable types: comma-separated incident_type codes in
  the `health_incident.notifiable_types` system parameter (severity 4-5
  always defaults notifiable; onchange/create-default only, never a
  hard constraint).
