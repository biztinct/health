# health_forms — Configurable Clinical Forms / Assessments Engine

Versioned, scored clinical assessment forms rendered in the Odoo backend
(OWL widget `health_form_renderer`) and the nurse PWA (plain-JS runner
injected into `health_pwa.app_shell`) from **one shared JSON schema**
(design spec `docs/strategy/design-clinical-modules.md` §4.2). Born-FHIR:
templates map 1:1 to `Questionnaire`, instances to
`QuestionnaireResponse` (serializers land later in `health_fhir_core`).

## What ships

- `health.form.template` / `health.form.question` — authoring; compiled
  `schema_json`; draft → published → retired; published templates are
  immutable (`action_new_version` copies to draft v+1).
- `health.form.instance` — the response; pins `schema_snapshot` +
  `template_version` at creation so it renders identically forever;
  `action_complete` validates required/bounds/visible_if, scores, and
  extracts coded observations into `health_vitals`
  (`health.observation.create_coded(..., source='form')`, linked back via
  `form_instance_id`); head-nurse amendment re-scores and marks the
  previous observations `entered_in_error`.
- Seeded instruments (published v1, `noupdate="1"`): **PAIN** (0–10),
  **BARTHEL** (ADL, 10 items), **MNA_SF** (nutrition, 6 items),
  **BRADEN** (pressure injury, 6 subscales), **AMTS** (cognition,
  11 boolean items). Assessment observation types: `barthel_total`,
  `mna_sf_total`, `braden_total` (LOINC 38228-3), `amts_total`
  (`local:` codes use system `health19-assessments`; bind LOINC at
  terminology-pack time).
- PWA API under `/health_pwa/api/...` (templates, per-visit forms,
  idempotent submit with base64 media + `client_uuid`, patient history +
  trend).

## Morse fall risk — convergence path (documented only, NOT this phase)

`health.fall.risk` (Morse, LOINC 59461-4) **stays in `health_base`
untouched**. Planned convergence when scheduled:

1. Author a `MORSE` v1 template mirroring the six Morse items with the
   standard option scores and bands.
2. Backfill `health.form.instance` rows from existing `health.fall.risk`
   records (one instance per assessment, answers mapped item-by-item,
   `schema_snapshot` pinned to MORSE v1, totals re-extracted as
   `59461-4` observations).
3. Deprecate the bespoke `health.fall.risk` model (read-only, then
   removed) once reporting has moved to form instances.

No code in this module references `health.fall.risk`.
