# Handover: Portal "My Health" — problem list + recent vitals in My Care (Phase 4E)

Read `docs/strategy/HANDOVER-CONVENTIONS.md` first (§2 deploy, §3 rails, §5
gotchas). This phase edits **`health_portal` ONLY** — §2.1 below is the
exhaustive sanction list.

## §0 Why / scope

The My Care portal MVP (4A visits, 4B records, 4C consents, 4D balance) is
live. Since then the platform shipped `health_condition` (the per-patient
ICD-10 problem list) and has long had structured vitals
(`health.observation`). Neither is visible to the patient: the portal's
records section shows only free-text note sections. This phase adds ONE new
portal section — **"Sức khỏe của tôi" (My Health)** — showing the patient's
active diagnoses (Vietnamese-first) and their recent vital-sign readings.

Same security doctrine as 4B (model docstring precedent at
`health_portal/models/health_portal_access.py:205-207`): a patient reading
their OWN record is their right — NOT gated by `data_sharing` consent (which
governs external sharing). Sudo reads hard-scoped to the one `patient_id`.

**Binding non-goals**
- NO risk communication to patients: never render `is_abnormal`,
  `alert_level`, NEWS2 scores, twin risk bands, or threshold breaches.
  Raw values + units only; risk interpretation stays with the care team.
- NO writes from the portal (conditions and vitals are read-only here).
- NO edits to `health_condition`, `health_vitals`, `health_twin`,
  `health_telemonitoring`, or any module other than `health_portal`.
- NO patient messaging (deferred: needs the family-thread bridge).
- NO PWA assets → NO PWA version bump (this is the portal website surface,
  not health_pwa).

## §1 Verified plumbing facts (do NOT re-derive)

Portal module (all live at 19.0.1.3.0, deployed == git):
- Route + guard pattern: `controllers/portal_public.py:40-47` (`_guard`
  returns `(access, None)` or `(None, neutral)`), route shape `:49-56`
  (auth='public', GET, website=False, csrf=False, `_record_access` then
  render). Clone exactly.
- Render-context precedent: `models/health_portal_access.py:204-231`
  (`_records` / `_records_ctx`). VN wall-clock offset `_VN_OFFSET` at `:25`
  (+7h, no DST). Given-name helper `:180-184`.
- Cross-module field-guard precedent `:211-212` (`if 'emr_state' not in
  Note._fields`) — NOT needed this phase; we take hard `depends` instead
  (both modules are installed on vietuat and the portal already hard-depends
  on health_emr for 4B).
- Access log: `_record_access(section, ip)` at `:109-121` — call with
  section `'health'`.
- Template shell: `views/portal_templates.xml:55` (`t-out="0"` shared
  shell); hub nav link precedent `:82`; records list/detail templates
  `:153-205` are the visual clone source (self-contained mobile CSS, mono
  teal, VN-first).
- Manifest: `__manifest__.py:6` version `19.0.1.3.0` → bump `19.0.1.4.0`;
  depends list at `:9`.
- Tests: `tests/test_portal.py` — `PortalFixtures` mixin `:16`,
  TransactionCase + HttpCase classes all `@tagged('post_install',
  '-at_install')`. HttpCase present → deploy WITHOUT `--no-http`.

`health.condition` (health_condition, live 19.0.1.0.0):
- Fields (`models/health_condition.py`): `patient_id` (res.partner),
  `code_id` (medical.code, ICD-10), `clinical_status`
  (active/inactive/resolved), `recorded_date` (Date), `active` (archive =
  removed from working list). Label source: `code_id.display_vi` first, then
  `code_id.display`, plus `code_id.code` (clone `_compute_display_name`
  `:112-120`).
- Default `search()` already excludes archived (`active=False`) rows.

`health.observation` (health_vitals):
- Fields (`models/health_observation.py:22-96`): `client_id` (the patient),
  `vitals_type_id` → `health.vitals.type` (`name_vi` at
  `health_vitals_type.py:19`, `unit_display` `:32`, `value_type` `:36`,
  `decimals` `:48`), `value_quantity` (Float), `value_text`,
  `effective_datetime` (Datetime, ordered desc), panel structure
  `parent_id`/`child_ids` `:77-83` (e.g. BP panel row with
  systolic/diastolic children), `state` `:84-91`
  (preliminary/final/amended/entered_in_error).
- Clinical-risk fields to NEVER render: `is_abnormal` `:92`, `alert_level`
  `:94`.

## §2 Build

### §2.1 Sanctioned edits (exhaustive)
- `addons/health_portal/__manifest__.py` — version 19.0.1.4.0; depends +=
  `health_condition`, `health_vitals`.
- `addons/health_portal/controllers/portal_public.py` — ONE new route
  `/my/care/<string:token>/health` (GET), guard + `_record_access('health',
  ...)` + render, exact clone of `portal_records`.
- `addons/health_portal/models/health_portal_access.py` — new render-context
  methods (below). No changes to existing methods.
- `addons/health_portal/views/portal_templates.xml` — new
  `portal_health` template + one hub nav link ("Sức khỏe của tôi →")
  next to the records link.
- `addons/health_portal/tests/test_portal.py` — new test classes/cases.
- `addons/health_portal/i18n/vi.po` — new strings.
Anything else, including every other module: READ-ONLY.

### §2.2 Model methods (on `health.portal.access`)
- `_conditions()`: `env['health.condition'].sudo().search([('patient_id','=',
  self.patient_id.id), ('clinical_status','=','active')], order='recorded_date
  desc, id desc')` — default active_test already drops archived rows; the
  status filter keeps the working problem list only (resolved/inactive not
  shown v1).
- `_conditions_rows()`: per row → `{'code': code.code, 'label': display_vi or
  display or '', 'since': recorded_date VN-formatted '%d/%m/%Y' or ''}`.
- `_vitals()`: `env['health.observation'].sudo().search([('client_id','=',
  self.patient_id.id), ('state','in',('final','amended')), ('parent_id','=',
  False)], order='effective_datetime desc, id desc', limit=20)` — top-level
  rows only; preliminary and entered_in_error excluded.
- `_vitals_rows()`: per row → type label (`name_vi or name`), value:
  numeric types formatted with `vitals_type_id.decimals`
  (`'%.*f' % (decimals, value_quantity)`), text types → `value_text`;
  panels (has `child_ids`) render the children joined inline, e.g.
  `120/80 mmHg` for BP — generically: join child values with `/` when the
  children share a unit, else `; `-join `label value unit` pairs (keep it
  simple and deterministic; a plain per-child listing is acceptable if the
  slash-join gets fiddly — declare which you shipped). Include VN wall-clock
  `'%d/%m/%Y %H:%M'` from `effective_datetime + _VN_OFFSET` and
  `unit_display`.
- `_health_ctx()`: `{'patient_name', 'token', 'conditions': ..., 'vitals':
  ...}` — clone `_records_ctx` shape.

### §2.3 Template
`portal_health`: two sections — "Chẩn đoán đang theo dõi" (active
diagnoses: code chip + Vietnamese label + "từ dd/mm/yyyy") and "Sinh hiệu
gần đây" (recent vitals: label, value + unit, datetime). Empty-state lines
for each ("Chưa có chẩn đoán được ghi nhận." / "Chưa có sinh hiệu được ghi
nhận."). All values `t-esc` (no raw HTML). Visual language identical to the
records templates (same shell, same card CSS).

## §3 Safety rails (binding)
- Every new read is sudo BUT filtered by `self.patient_id.id` in the same
  search call — no post-filtering, no browse-by-id from request params.
- The route takes NOTHING but the token — no record ids in the URL this
  phase (list-only page).
- No `is_abnormal` / `alert_level` / NEWS2 / threshold data in context or
  template (grep your own diff for these names before finishing).
- Neutral-page behavior for invalid/revoked/expired tokens must be
  byte-identical to the other sections (reuse `_guard`, add nothing).
- Never log the token; `_record_access` section string is `'health'`.

## §4 Tests (numbered; extend `test_portal.py`, reuse `PortalFixtures`)
1. `_conditions_rows` shows the patient's active condition (Vietnamese-first
   label) and NOT another patient's.
2. Resolved AND archived conditions are excluded.
3. `_vitals_rows` shows the patient's final observation with unit +
   VN-formatted datetime, and NOT another patient's.
4. `entered_in_error` and `preliminary` observations are excluded; amended
   included.
5. BP-style panel row renders its children's values (whichever join you
   shipped) and children do not ALSO appear as top-level rows.
6. Context contains no `is_abnormal`/`alert_level` keys anywhere (assert on
   the rendered rows' dict keys).
7. HttpCase: valid token → /health renders 200 with the condition label and
   a vitals value; unknown token → neutral page (byte-identical to hub
   neutral).
8. Hub HTML contains the new nav link.

## §5 Deploy + verify (conventions §2; §5.45 one-odoo-process rule)
- `-u health_portal --test-enable --test-tags /health_portal --stop-after-init
  --workers 0` — NO `--no-http` (HttpCase). Expect the existing ~20 portal
  tests + new ones, 0 failed; then restart + HTTP:200.
- Confirm by `odoo.tests.result` line + EXIT:0, never HTTP alone.
- Browser evidence pack (process commit c489ad1e): real-data screenshots of
  the /health section for Demo Patient 861 (the only patient with real
  conditions: I10 + E11) — conditions render in Vietnamese; vitals list
  shows real observations if 861 has any, else the empty-state (report
  which). Also one neutral-page shot. Commit under
  `docs/strategy/reports/portal-my-health-evidence/`.
- Data-honesty: report the REAL counts rendered for 861 (expect 2
  conditions; vitals count unknown — do not seed prod data to make the
  screenshot prettier; the empty state is an acceptable, honest screenshot).

## §6 Report back
`docs/strategy/reports/portal-my-health-report.md`: what shipped, deviations
(each declared), test tally verbatim, evidence pack, the real 861 render
counts, and any gotcha proposed for the ledger.

---
Kickoff (paste into the Opus session):

Implement the phase specified in docs/strategy/handovers/portal-my-health.md.
Read docs/strategy/HANDOVER-CONVENTIONS.md first. Edit health_portal ONLY —
§2.1 is the exhaustive sanction list; health_condition, health_vitals and
every other module are READ-ONLY. The §3 rails are binding (no risk fields to
patients, sudo always patient-scoped in-search, token-only route). Full
self-verification per §5 including the browser evidence pack on real data,
then commit the report per §6 and report back.
