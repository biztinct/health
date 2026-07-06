# Horizon-1 Clinical Modules — Implementation Spec

**Target:** Odoo 19 Community Edition, health19 platform (VietUcUAT, DB `vietuat`).
**Modules specified:** `health_careplan`, `health_vitals`, `health_emar`, `health_forms`, `health_incident`, `health_consent`.
**Audience:** an LLM/engineer coding directly from this document. Every model, field, route and seed below is normative. Where a convention says "as in `<file>`", copy that file's pattern verbatim.

---

## 0. Platform conventions (apply to ALL six modules)

These were extracted from the live codebase and are **mandatory**. Do not invent alternatives.

### 0.1 Module boilerplate

Every `__manifest__.py` uses:

```python
{
    'name': '<Human Name>',
    'version': '19.0.1.0.0',
    'category': 'Healthcare/Clinical',
    'summary': '<one line>',
    'author': 'VAFHS Development Team',
    'website': 'https://www.vafhs.com',
    'license': 'LGPL-3',
    'depends': [...],
    'data': [...],
    'installable': True,
    'application': False,
    'auto_install': False,
}
```

### 0.2 Security groups (defined in `health_base/security/health_security.xml` — reuse, never redefine)

Exact XML ids (all referenced as `health_base.<id>`):

| xml id | role |
|---|---|
| `group_healthcare_base` | Base access |
| `group_healthcare_receptionist` | Receptionist |
| `group_healthcare_nurse` | Nurse |
| `group_healthcare_head_nurse` | Head Nurse (implies nurse) |
| `group_healthcare_doctor` | Doctor |
| `group_healthcare_sales` | Sales |
| `group_healthcare_operations_manager` | Operations Manager |
| `group_healthcare_finance` | Finance |
| `group_healthcare_manager` | Manager (implies ops manager + head nurse + finance) |
| `group_healthcare_admin` | Administrator |
| `group_healthcare_owner` | Owner (full) |
| `group_healthcare_patient` | Patient portal |

`ir.model.access.csv` row id convention (as in `health_base/security/ir.model.access.csv`):
`access_<model_name_underscored>_<group_shortname>,<model.name> <group_shortname>,model_<model_name_underscored>,health_base.group_healthcare_<group>,r,w,c,u`
(Within a module's own CSV the group column must be fully qualified `health_base.group_healthcare_*` since the groups live in another module.)

### 0.3 Catchment province record-rule pattern (copy from `health_fieldservice/security/health_fieldservice_security.xml`)

Every clinical model that carries client data gets a **stored computed** `catchment_province_id`:

```python
catchment_province_id = fields.Many2one(
    'health.catchment.province', string='Catchment Area',
    compute='_compute_catchment_province_id', store=True, readonly=True, index=True,
    help='Catchment area used for filtering and access control')

@api.depends('client_id.catchment_province_id',
             'client_id.primary_facility_id.catchment_province_id')
def _compute_catchment_province_id(self):
    for rec in self:
        rec.catchment_province_id = (
            rec.client_id._get_health_catchment_province() if rec.client_id else False)
```

(`res.partner._get_health_catchment_province()` exists in `health_base/models/res_partner.py`.)

Two record rules per model (adapt groups per module below):

```xml
<record id="rule_<model>_catchment" model="ir.rule">
    <field name="name"><Model>: Healthcare users see own catchment</field>
    <field name="model_id" ref="model_<model_underscored>"/>
    <field name="domain_force">['&amp;', ('catchment_province_id', '=', user.catchment_province_id.id), ('catchment_province_id', '!=', False)]</field>
    <field name="groups" eval="[(4, ref('health_base.group_healthcare_nurse')), (4, ref('health_base.group_healthcare_head_nurse')), (4, ref('health_base.group_healthcare_doctor')), (4, ref('health_base.group_healthcare_operations_manager')), (4, ref('health_base.group_healthcare_manager'))]"/>
</record>
<record id="rule_<model>_owner" model="ir.rule">
    <field name="name"><Model>: Owner sees all</field>
    <field name="model_id" ref="model_<model_underscored>"/>
    <field name="domain_force">[(1, '=', 1)]</field>
    <field name="groups" eval="[(4, ref('health_base.group_healthcare_owner'))]"/>
</record>
```

### 0.4 Model style

- `_inherit = ['mail.thread', 'mail.activity.mixin']` on every header/workflow model; `tracking=True` on state, client, dates and clinically significant fields (as on `health.fieldservice.order`).
- Human-readable `display_name` via stored compute + `_rec_name = 'display_name'` where the record has no natural name (pattern: `health.clinical.note._compute_display_name`).
- Sequences via `data/ir_sequence.xml` records (`code`, `prefix`, padding 5 — pattern: `health_fieldservice/data/ir_sequence.xml`, prefix `BK`), consumed in `create()` via `self.env['ir.sequence'].next_by_code(...)`.
- Vietnamese-facing text fields: `translate=True` and/or a paired `name_vi` Char (pattern: `health.medication.vietnamese_name`).
- Chatter renders **bottom, full-width** (global `health_theme` behavior — nothing to do per module; just include `<chatter/>` in form views).
- UI: flat mono colors, `hf-wt-ico` CSS-mask SVG icons, never emoji/font-awesome in new UI work.
- Buttons that change state are named `action_*` and are idempotent-guarded with `ensure_one()` + `UserError` on illegal transitions.

### 0.5 PWA API conventions (copy from `health_pwa/controllers/api.py`)

Each module ships its own `controllers/api.py` with a fresh `http.Controller` class that **duplicates** the two helpers (this duplication is the existing convention — `api.py` and `sync.py` both do it):

- `_check_api_access(self)`: reject public user; `request.env['res.partner'].check_access_rights('read')` in try/except → bool.
- `_prepare_json_response(self, data=None, error=None, status_code=200)`: envelope `{'success': error is None, 'timestamp': fields.Datetime.now().isoformat(), 'data': ... | 'error': ...}`, `json.dumps(..., default=str, ensure_ascii=False, indent=2)`, headers incl. `Content-Type: application/json; charset=utf-8`, `Cache-Control: no-cache...`, CORS `*`.

Routes: `@http.route('/health_pwa/api/<...>', type='http', auth='user', methods=['GET'|'POST'], csrf=False)`. POST bodies parsed with `json.loads(request.httprequest.data.decode('utf-8')) if request.httprequest.data else {}`. Record-not-found → 404 envelope, access denied → 403, exceptions → 500 with `error=str(e)`.

The clinical modules do **not** depend on `health_pwa` (routes are plain controllers). The Vue/PouchDB frontend changes listed per module are made **inside `health_pwa`** (stores live in `static/src/js/utils/storage-manager.js`, existing stores: `health_patients`, `health_orders`, `health_teams`, `health_service_types`, `health_facilities`, `health_sync_meta`; delta sync via `/health_pwa/sync/changes` `_get_*_changes(since_datetime)` handlers in `controllers/sync.py`). **Every `health_pwa` change requires the version bump in `pwa_templates.xml` (3 places).**

### 0.6 Menus

Parents that already exist:
- Root: `health_base.menu_healthcare_root` ("Healthcare")
- `health_base.menu_healthcare_clinical` ("Clinical Intelligence")
- `health_base.menu_healthcare_patients` ("Client Management")
- Config: `health_base.menu_healthcare_lookups` ("Configuration")
- Field service root: `health_fieldservice.menu_health_fieldservice_root`

New menu items may use either `<menuitem>` (health_base style) or `<record model="ir.ui.menu">` (health_fieldservice style); prefer `<menuitem>`.

### 0.7 Born-FHIR rule

No FHIR code ships in these modules. Schemas are designed so a future `health_fhir_core` serializer maps field→element 1:1 (mapping tables given per module). Selection values use FHIR value-set codes verbatim wherever possible (e.g. eMAR routes, Goal lifecycle). Free-text is never removed — coded fields sit alongside (coding-sidecar pattern).

### 0.8 Existing models referenced (exact names)

- `health.fieldservice.order` (FSO/booking; states `draft, confirmed, assigned, in_progress, completed, completed_pending_invoice, cancelled, closed`; fields used: `patient_id` (res.partner), `facility_id` (health.facility), `scheduled_datetime`, `scheduled_date`, `state`, `service_type` (Selection: home_visit/clinic_visit/consultation/emergency/follow_up/preventive/rehabilitation/telemedicine/vaccination/diagnostic), `clinical_note_ids`, `assignment_ids`)
- `health.clinical.note` (fields: `order_id`, `author_id`, `vital_signs` Text, `image_ids`)
- `health.clinical.protocol` (JSON `action_steps_template`, `service_type_ids` m2m `health.service.type`)
- `health.service.type`, `health.facility`, `health.catchment.province` (all in `health_base`)
- `health.medication`, `health.medication.interaction`, `health.medication.safety` (in `health_base/models/health_medication_safety.py`; `check_drug_interactions(medications)` takes a list of medication *names*)
- `health.fall.risk` (Morse, `health_base/models/health_risk_assessment.py`)
- `health.client.relation` (in `health_crm`; fields `client_id`, `representative_id`, `role` in caregiver/payer/referrer/emergency_contact/legal_guardian/client_representative, `relationship_type`, `is_primary`)
- `health.staff.assignment` (`fso_id`, `staff_id` → hr.employee)
- `res.partner`: `is_patient`, `patient_code`, `primary_facility_id`, `_get_health_catchment_province()`

---

# 1. `health_careplan` — Care Plans, Goals, Interventions, Per-Visit Tasks

## 1.1 `__manifest__.py`

```python
{
    'name': 'Healthcare Care Plans',
    'version': '19.0.1.0.0',
    'category': 'Healthcare/Clinical',
    'summary': 'Care plans with goals, interventions and per-visit task checklists (FHIR CarePlan/Goal/Task)',
    'author': 'VAFHS Development Team',
    'website': 'https://www.vafhs.com',
    'license': 'LGPL-3',
    'depends': ['health_base', 'health_fieldservice', 'health_vitals'],
    'data': [
        'security/health_careplan_security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence.xml',
        'data/ir_cron.xml',
        'views/health_careplan_views.xml',
        'views/health_careplan_task_views.xml',
        'views/health_fieldservice_order_views.xml',
        'views/health_careplan_menus.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
```

Depends on `health_vitals` because goals target observation types (§1.2.2).

## 1.2 Models

### 1.2.1 `health.careplan`

```
_name = 'health.careplan'
_description = 'Care Plan'
_inherit = ['mail.thread', 'mail.activity.mixin']
_order = 'create_date desc'
_rec_name = 'display_name'
```

| field | type | purpose |
|---|---|---|
| `name` | Char, required, readonly, default `'New'`; set in `create()` from sequence `health.careplan` (prefix `CP`) | Plan reference |
| `display_name` | Char, compute stored, depends `name, client_id` → `f"{client.name} ({name})"` | List/breadcrumb label |
| `client_id` | Many2one `res.partner`, required, domain `[('is_patient','=',True)]`, ondelete `restrict`, index, tracking | The client |
| `state` | Selection `[('draft','Draft'),('active','Active'),('under_review','Under Review'),('completed','Completed'),('cancelled','Cancelled')]`, default `draft`, required, tracking | FHIR `CarePlan.status` (draft/active/completed/revoked; under_review is a local sub-state of active) |
| `category` | Selection `[('home_care','Home Care'),('post_acute','Post-Acute'),('chronic','Chronic Disease'),('palliative','Palliative'),('rehabilitation','Rehabilitation'),('other','Other')]`, default `home_care`, tracking | FHIR `CarePlan.category` |
| `title` | Char, translate | Human title, FHIR `CarePlan.title` |
| `description` | Html, translate | FHIR `CarePlan.description` |
| `author_id` | Many2one `res.users`, default `lambda self: self.env.uid`, readonly, tracking | FHIR `CarePlan.author` |
| `facility_id` | Many2one `health.facility`, default from `client_id.primary_facility_id` (onchange), tracking | Managing facility |
| `catchment_province_id` | per §0.3 (depends on `client_id`) | Record rules |
| `protocol_id` | Many2one `health.clinical.protocol`, string 'Based on Protocol' | FHIR `CarePlan.instantiatesCanonical` → PlanDefinition |
| `period_start` | Date, required, default today, tracking | FHIR `CarePlan.period.start` |
| `period_end` | Date, tracking | FHIR `CarePlan.period.end` |
| `review_cycle_days` | Integer, default 90, required | Review cadence |
| `next_review_date` | Date, compute stored (`period_start` or last review + `review_cycle_days`), readonly | Drives review cron |
| `last_review_date` | Date, readonly | Set by `action_confirm_review` |
| `version` | Integer, default 1, readonly | Bumped on each confirmed review |
| `goal_ids` | One2many `health.careplan.goal` `careplan_id` | Goals |
| `activity_ids` | One2many `health.careplan.activity` `careplan_id` | Interventions |
| `task_ids` | One2many `health.careplan.task` `careplan_id` | Compiled per-visit tasks |
| `goal_count` / `activity_count` / `task_count` | Integer, compute (len of o2m) | Smart buttons |
| `adherence_rate` | Float, compute stored via cron write (not @depends), readonly, help 'Done tasks / expected tasks, trailing 30 days' | Drift metric |
| `drift_flag` | Boolean, readonly, tracking | Set by drift cron |
| `active` | Boolean, default True | Archive |
| `company_id` | Many2one `res.company`, default `lambda self: self.env.company` | Multi-company |

SQL constraints:
- `('period_check', "CHECK (period_end IS NULL OR period_end >= period_start)", 'End date must be after start date.')`
- `('review_cycle_positive', 'CHECK (review_cycle_days > 0)', 'Review cycle must be positive.')`

Python constraint `_check_one_active_per_category`: at most one plan in state `active`/`under_review` per (`client_id`, `category`) → `ValidationError`.

### 1.2.2 `health.careplan.goal`

```
_name = 'health.careplan.goal'
_description = 'Care Plan Goal'
_order = 'careplan_id, sequence, id'
```

| field | type | purpose |
|---|---|---|
| `careplan_id` | Many2one `health.careplan`, required, ondelete `cascade`, index | Parent |
| `sequence` | Integer, default 10 | Ordering |
| `name` | Char, required, translate | FHIR `Goal.description.text` |
| `client_id` | Many2one related `careplan_id.client_id`, store=True | FHIR `Goal.subject`; search |
| `lifecycle_status` | Selection `[('proposed','Proposed'),('active','Active'),('on_hold','On Hold'),('completed','Completed'),('cancelled','Cancelled')]`, default `proposed`, required, tracking-not-needed (no chatter on line model) | FHIR `Goal.lifecycleStatus` (codes verbatim, `on_hold` → `on-hold`) |
| `achievement_status` | Selection `[('in_progress','In Progress'),('improving','Improving'),('worsening','Worsening'),('achieved','Achieved'),('not_achieved','Not Achieved')]` | FHIR `Goal.achievementStatus` |
| `vitals_type_id` | Many2one `health.vitals.type`, string 'Target Observation' | FHIR `Goal.target.measure` (LOINC via type) |
| `loinc_code` | Char related `vitals_type_id.loinc_code`, readonly | Convenience |
| `baseline_value` | Float | Baseline measure at plan start |
| `baseline_date` | Date | When baseline taken |
| `target_value_min` | Float | FHIR `Goal.target.detailRange.low` |
| `target_value_max` | Float | FHIR `Goal.target.detailRange.high` |
| `target_unit` | Char related `vitals_type_id.ucum_unit`, readonly | UCUM |
| `due_date` | Date | FHIR `Goal.target.dueDate` |
| `priority` | Selection `[('high','High'),('medium','Medium'),('low','Low')]`, default `medium` | FHIR `Goal.priority` |
| `latest_value` | Float, compute (non-stored): most recent `health.observation` for `client_id` + `vitals_type_id`, state `final` | Progress display |
| `latest_value_date` | Datetime, compute (same query) | Progress display |
| `is_on_target` | Boolean, compute: `target_value_min <= latest_value <= target_value_max` (open bounds allowed) | Progress display |
| `notes` | Text | Free notes |

Compute `_compute_latest_value`: one `read_group`/`search` per goal batch on `health.observation` filtered `client_id`, `vitals_type_id`, `state = 'final'`, order `effective_datetime desc`, limit 1.

### 1.2.3 `health.careplan.activity`

```
_name = 'health.careplan.activity'
_description = 'Care Plan Intervention/Activity'
_order = 'careplan_id, sequence, id'
```

| field | type | purpose |
|---|---|---|
| `careplan_id` | Many2one `health.careplan`, required, ondelete `cascade`, index | Parent |
| `sequence` | Integer, default 10 | Ordering |
| `name` | Char, required, translate | Activity label, FHIR `Task.code.text` |
| `service_type_id` | Many2one `health.service.type` | Informational service linkage; FHIR `CarePlan.activity.detail.code` |
| `goal_ids` | Many2many `health.careplan.goal`, rel `careplan_activity_goal_rel`, domain `[('careplan_id','=',careplan_id)]` | FHIR `activity.detail.goal` |
| `status` | Selection `[('not_started','Not Started'),('scheduled','Scheduled'),('in_progress','In Progress'),('completed','Completed'),('cancelled','Cancelled')]`, default `scheduled`, required | FHIR `activity.detail.status` |
| `frequency` | Selection `[('every_visit','Every Visit'),('daily','Daily'),('weekly','Weekly'),('monthly','Monthly'),('prn','PRN / As Needed')]`, default `every_visit`, required | Compilation rule (§1.4) |
| `frequency_interval` | Integer, default 1, help 'Every N days/weeks/months (ignored for every_visit / prn)' | FHIR `Timing.repeat.period` |
| `times_per_period` | Integer, default 1 | FHIR `Timing.repeat.frequency` |
| `visit_filter` | Selection `[('all','All Visits'),('home_visit','Home Visits Only'),('clinic_visit','Clinic Visits Only')]`, default `all` | Which FSOs receive tasks (matched against `fso.service_type`) |
| `instructions` | Html, translate | Nurse-facing instructions; FHIR `activity.detail.description` |
| `duration_minutes` | Integer | Planning aid |
| `start_date` / `end_date` | Date | Activity window inside plan period |
| `client_id` | Many2one related `careplan_id.client_id`, store=True | Search |

Python constraint: `frequency_interval >= 1`, `times_per_period >= 1`.

### 1.2.4 `health.careplan.task` (per-visit checklist item)

```
_name = 'health.careplan.task'
_description = 'Care Plan Visit Task'
_order = 'fso_id, sequence, id'
_rec_name = 'name'
```

| field | type | purpose |
|---|---|---|
| `careplan_id` | Many2one `health.careplan`, required, ondelete `cascade`, index | Parent plan |
| `activity_id` | Many2one `health.careplan.activity`, required, ondelete `cascade`, index | Source intervention |
| `fso_id` | Many2one `health.fieldservice.order`, required, ondelete `cascade`, index | The visit; FHIR `Task.encounter` |
| `client_id` | Many2one related `careplan_id.client_id`, store=True | Search |
| `catchment_province_id` | per §0.3 (depends `client_id...`) | Record rules |
| `sequence` | Integer, default 10 | Checklist order |
| `name` | Char, required (copied from activity name at compile time) | Snapshot label |
| `instructions` | Html (snapshot of activity instructions at compile time) | Immutable per-visit instructions |
| `state` | Selection `[('pending','Pending'),('done','Done'),('not_done','Not Done')]`, default `pending`, required, index | FHIR `Task.status` (pending→requested, done→completed, not_done→failed w/ statusReason) |
| `not_done_reason` | Selection `[('client_refused','Client Refused'),('client_unavailable','Client Unavailable/Asleep'),('clinical_judgement','Withheld — Clinical Judgement'),('no_supplies','Missing Supplies/Equipment'),('out_of_time','Ran Out of Time'),('other','Other')]` | FHIR `Task.statusReason` |
| `not_done_note` | Char | Free-text reason detail |
| `completed_by_id` | Many2one `res.users`, readonly | Who ticked |
| `completed_datetime` | Datetime, readonly | When ticked |
| `is_prn` | Boolean, default False, readonly | Added ad-hoc from PWA |

SQL constraint: `('uniq_activity_per_fso', 'UNIQUE(activity_id, fso_id)', 'This activity already has a task on this visit.')` — PRN duplicates are allowed by exempting: instead implement as Python constraint that skips `is_prn` records.

### 1.2.5 `health.fieldservice.order` extension (`models/health_fieldservice_order.py`)

```
_inherit = 'health.fieldservice.order'
```

| field | type | purpose |
|---|---|---|
| `careplan_task_ids` | One2many `health.careplan.task` `fso_id` | Visit checklist |
| `careplan_task_count` | Integer compute | Smart button |
| `careplan_task_done_count` | Integer compute | Progress `x/y` badge |
| `has_open_careplan_tasks` | Boolean compute | Completion nudge |

Override `write()`: after super, if `state` changed into `('confirmed', 'assigned')` or `scheduled_datetime` changed while in those states → call `self.env['health.careplan']._compile_tasks_for_orders(self)`.

## 1.3 State machine — `health.careplan`

| transition | button | guard | allowed groups |
|---|---|---|---|
| draft → active | `action_activate` | ≥1 goal AND ≥1 activity; `period_start` set | head_nurse, doctor, manager+ |
| active → under_review | `action_start_review` | — | head_nurse, doctor, manager+ (also auto via cron at `next_review_date`) |
| under_review → active | `action_confirm_review` | — ; side effects: `version += 1`, `last_review_date = today`, recompute `next_review_date` | head_nurse, doctor, manager+ |
| active / under_review → completed | `action_complete` | goal lifecycle statuses updated by user beforehand (no hard guard); sets `period_end = today` if empty | head_nurse, doctor, manager+ |
| draft / active / under_review → cancelled | `action_cancel` | wizard-free; pending tasks on future FSOs are unlinked | head_nurse, doctor, manager+ |
| cancelled → draft | `action_reset_draft` | — | manager+ |

Group enforcement: buttons carry `groups="health_base.group_healthcare_head_nurse,health_base.group_healthcare_doctor,health_base.group_healthcare_manager"`; methods additionally raise `AccessError` via `self.env.user.has_group(...)` check (defense in depth). Nurses (non-head) get read + task ticking only.

## 1.4 Business methods

```python
@api.model
def _compile_tasks_for_orders(self, orders):
```
For each FSO in `orders` (skip states not in confirmed/assigned): find plans `state='active'` (not under_review/draft), `client_id = order.patient_id`, `period_start <= order.scheduled_date`, `period_end` null or `>= order.scheduled_date`. For each activity with `status in ('scheduled','in_progress')`, `visit_filter` matches `order.service_type` (`all` always matches; `home_visit`/`clinic_visit` must equal), activity window contains the date:
- `every_visit`: create task if none exists for (activity, fso).
- `daily`/`weekly`/`monthly`: period length = `frequency_interval` × (1 day / 7 days / 30 days). Create task iff no non-`not_done` task exists for the activity with an FSO `scheduled_date` inside the current period window `[order.scheduled_date - period + 1 day, order.scheduled_date]`, capped at `times_per_period` tasks per window.
- `prn`: never auto-compiled.
Tasks snapshot `name` + `instructions` from the activity. Method is idempotent (re-running creates nothing new). Also delete `pending` tasks whose FSO moved out of the plan window or whose activity was cancelled.

```python
def action_mark_done(self)          # on health.careplan.task
def action_mark_not_done(self, reason=None, note=None)
def action_reset_pending(self)
```
`action_mark_done`: guard state == 'pending' (or 'not_done' → correction allowed), set `state='done'`, `completed_by_id=env.uid`, `completed_datetime=now`. `action_mark_not_done`: requires `not_done_reason`. Any healthcare nurse+ may call (these are the PWA tick actions).

```python
def add_prn_task(self, fso, activity)   # model method on health.careplan.task
```
Creates an `is_prn=True` task for a PRN activity on the given visit.

```python
@api.model
def _cron_careplan_reviews(self):   # daily
```
Plans `state='active'` with `next_review_date <= today` → `action_start_review()` + `activity_schedule` (todo) on `author_id`: "Care plan review due: {client}".

```python
@api.model
def _cron_careplan_drift(self):     # weekly (Mon 03:00)
```
For each `active`/`under_review` plan: window = trailing 30 days; expected = tasks whose FSO `state in ('completed','completed_pending_invoice','closed')` in window; done = those with `state='done'`. `adherence_rate = done/expected` (1.0 if expected == 0). If rate < `float(ir.config_parameter 'health_careplan.drift_threshold' or 0.8)` → `drift_flag = True` + `activity_schedule` on `author_id` "Care plan drift detected ({rate:.0%})"; else `drift_flag = False`. This is the drift-detection hook; keep the computation in one overridable method `_compute_drift(plan, window_start, window_end)`.

`data/ir_cron.xml`: two crons (`Care Plan: Review due`, interval 1 day; `Care Plan: Drift detection`, interval 1 week), `active` True, model `health.careplan`.

## 1.5 Views & menus

- `view_health_careplan_form`: header with statusbar (`draft,active,under_review,completed`) + the `action_*` buttons; button box smart buttons (Goals, Activities, Tasks with counts, client link); sheet groups: client/category/facility/author | period/review-cycle/next-review/version/adherence; notebook pages **Goals** (editable list inline: name, vitals_type_id, baseline_value, target_value_min/max, due_date, lifecycle_status, achievement_status, latest_value, is_on_target), **Interventions** (inline list: name, service_type_id, frequency, frequency_interval, visit_filter, status, instructions), **Description**; `<chatter/>`.
- `view_health_careplan_list`: name, client_id, category, period_start, next_review_date, adherence_rate (percentage widget), drift_flag (boolean), state (badge).
- `view_health_careplan_kanban`: grouped by `state`; card: client, category, goal_count, adherence.
- `view_health_careplan_search`: filters My Plans (`author_id = uid`), Active, Review Due (`next_review_date <= today`), Drift; group by client, category, facility, state.
- `view_health_careplan_task_list` (+ search): fso_id, client_id, name, state, completed_by_id, completed_datetime; filters Pending/Done/Not Done, group by FSO / plan.
- FSO form inherit: new notebook page "Care Plan Tasks" after Clinical Notes page: readonly inline list of `careplan_task_ids` (name, state, not_done_reason, completed_by_id) + smart-button with `careplan_task_done_count`/`careplan_task_count`.
- Menus (`views/health_careplan_menus.xml`): `menu_health_careplan` "Care Plans" under `health_base.menu_healthcare_clinical`, sequence 5, action → careplan kanban/list/form; `menu_health_careplan_tasks` "Visit Tasks" under it, sequence 10 (groups manager+ for the register view).

## 1.6 Security

`security/ir.model.access.csv` matrix (r/w/c/u):

| model | receptionist | nurse | head_nurse | doctor | ops_manager | manager | admin | owner |
|---|---|---|---|---|---|---|---|---|
| health.careplan | 1000 | 1000 | 1110 | 1110 | 1000 | 1110 | 1110 | 1111 |
| health.careplan.goal | 1000 | 1000 | 1110 | 1110 | 1000 | 1110 | 1110 | 1111 |
| health.careplan.activity | 1000 | 1000 | 1110 | 1110 | 1000 | 1110 | 1110 | 1111 |
| health.careplan.task | 1000 | 1110 | 1110 | 1110 | 1000 | 1110 | 1110 | 1111 |

(Nurse gets write on task for ticking, and create because task compilation runs in the FSO-writing user's context — no sudo.)

`security/health_careplan_security.xml`: catchment + owner rules (§0.3) for `health.careplan` and `health.careplan.task` (goal/activity inherit protection via parent access; no client-bearing direct search screens — still add the same two rules for `health.careplan.goal` and `health.careplan.activity` using `careplan_id.catchment_province_id` in the domain).

## 1.7 PWA API (`controllers/api.py`, class `HealthCareplanPWAController`)

| route | method | request | response `data` |
|---|---|---|---|
| `/health_pwa/api/fso/<int:order_id>/careplan_tasks` | GET | — | `{ 'tasks': [{id, name, instructions, state, sequence, is_prn, not_done_reason, not_done_note, completed_by, completed_at, activity_id, careplan_id, goal_names: []}], 'careplan': {id, name, title, category} or null, 'prn_activities': [{id, name, instructions}] }` |
| `/health_pwa/api/careplan_tasks/<int:task_id>/update` | POST | `{"state": "done"|"not_done"|"pending", "not_done_reason": "...", "not_done_note": "..."}` | `{'task_id', 'state', 'message'}` — dispatches to `action_mark_done`/`action_mark_not_done`/`action_reset_pending` |
| `/health_pwa/api/fso/<int:order_id>/careplan_tasks/add_prn` | POST | `{"activity_id": int}` | created task dict (same shape as list item) |
| `/health_pwa/api/patients/<int:patient_id>/careplans` | GET | — | `{'careplans': [{id, name, title, category, state, period_start, period_end, adherence_rate, goals: [{name, target, latest_value, is_on_target, due_date}]}]}` |

PWA frontend (in `health_pwa`): visit detail gets a "Care Tasks" checklist card (tick / not-done with reason picker); tasks are embedded in the FSO sync payload — extend `sync.py::_get_fso_changes` to include `careplan_tasks: [...]` in each order doc (guard with `if 'careplan.task' in request.env`… actually guard `hasattr(order, 'careplan_task_ids')` so health_pwa works without health_careplan). Offline ticks queue as mutations replayed against `/careplan_tasks/<id>/update`. No new PouchDB store (tasks ride inside `health_orders` docs). Bump PWA version (3 places in `pwa_templates.xml`).

## 1.8 FHIR serialization notes (consumed later by `health_fhir_core`)

| Odoo | FHIR |
|---|---|
| `health.careplan` | `CarePlan`; `status`: draft→draft, active/under_review→active, completed→completed, cancelled→revoked; `subject`=Patient(client_id); `period`=period_start/end; `author`; `category`; `title`; `description`; `instantiatesCanonical`=PlanDefinition(protocol_id); `goal`=Goal refs; `activity.reference`→Task per compiled task |
| `health.careplan.goal` | `Goal`; `lifecycleStatus` verbatim (`on_hold`→`on-hold`); `achievementStatus` (`in_progress`→`in-progress` etc.); `description.text`=name; `subject`; `target.measure`=LOINC(vitals_type_id); `target.detailRange`=min/max + UCUM; `target.dueDate`; `priority`; baseline as `Goal.startCodeableConcept` extension or initial Observation reference |
| `health.careplan.activity` | `CarePlan.activity.detail` (code=service_type, status verbatim (`not_started`→`not-started`), scheduledTiming from frequency/interval/times_per_period, description=instructions) |
| `health.careplan.task` | `Task`; `status`: pending→requested, done→completed, not_done→failed (+`statusReason` from not_done_reason); `basedOn`=CarePlan; `encounter`=Encounter(fso_id); `owner`=completed_by; `executionPeriod.end`=completed_datetime |
| `health.clinical.protocol` | `PlanDefinition` (out of scope here; relationship carried by `protocol_id`) |

## 1.9 Data seeds

- `data/ir_sequence.xml`: `health.careplan` sequence, prefix `CP`, padding 5.
- `data/ir_cron.xml`: the two crons (§1.4).
- No content seeds (plans are per-client). Optional demo data omitted.

## 1.10 Acceptance criteria

1. Creating a plan with 2 goals + 2 activities and pressing Activate moves it to `active`; Activate on a plan without goals raises a blocking `UserError`.
2. Confirming/creating an FSO (state → confirmed) for a client with an active plan auto-creates pending `health.careplan.task` rows; re-saving the FSO does not duplicate them.
3. An activity with `frequency='weekly', frequency_interval=1` generates a task on at most one FSO per rolling 7-day window even when the client has daily visits.
4. Marking a task not-done without a reason via the API returns `success:false` with a validation error; with a reason it stores reason + user + timestamp.
5. `GET /health_pwa/api/fso/<id>/careplan_tasks` returns the standard envelope and lists PRN activities separately; posting `add_prn` creates an `is_prn` task.
6. A nurse in catchment A cannot read plans/tasks of catchment B clients (record rule); owner sees all.
7. The review cron flips a plan to `under_review` on `next_review_date` and schedules an activity for the author; `action_confirm_review` bumps `version` and pushes `next_review_date` forward by `review_cycle_days`.
8. The drift cron sets `drift_flag` when trailing-30-day adherence < 0.8 (config-parameter overridable) and clears it otherwise.
9. A second `active` plan for the same client + category is blocked with a `ValidationError`.
10. FSO form shows the Care Plan Tasks page with live done/total counts; chatter stays bottom full-width.

## 1.11 Integration touchpoints

- `health.fieldservice.order.write()` override (compile hook) + `careplan_task_ids` o2m.
- `health.careplan.goal.vitals_type_id` / `latest_value` → `health.vitals` (`health.vitals.type`, `health.observation`).
- `health.careplan.protocol_id` → `health.clinical.protocol` (future PlanDefinition `$apply`).
- PWA: `health_pwa/controllers/sync.py::_get_fso_changes` payload extension; visit-detail Vue screen; version bump.
- Drift activities land on `author_id` via `mail.activity` (standard `mail.mail_activity_data_todo`).

---

# 2. `health_vitals` — Structured LOINC Observations

## 2.1 `__manifest__.py`

```python
{
    'name': 'Healthcare Structured Vitals',
    'version': '19.0.1.0.0',
    'category': 'Healthcare/Clinical',
    'summary': 'LOINC-coded observations, vital-sign catalog, per-client alert thresholds, trending (FHIR Observation)',
    'author': 'VAFHS Development Team',
    'website': 'https://www.vafhs.com',
    'license': 'LGPL-3',
    'depends': ['health_base', 'health_fieldservice'],
    'data': [
        'security/health_vitals_security.xml',
        'security/ir.model.access.csv',
        'data/health_vitals_type_data.xml',
        'views/health_vitals_type_views.xml',
        'views/health_observation_views.xml',
        'views/health_vitals_threshold_views.xml',
        'views/health_clinical_note_views.xml',
        'views/res_partner_views.xml',
        'views/health_vitals_menus.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
```

## 2.2 Models

### 2.2.1 `health.vitals.type` — observation catalog

```
_name = 'health.vitals.type'
_description = 'Vital Sign / Observation Type'
_order = 'sequence, name'
```

| field | type | purpose |
|---|---|---|
| `name` | Char, required, translate | English display (FHIR `code.coding.display`) |
| `name_vi` | Char | Vietnamese display |
| `code` | Char, required | Internal short code (`bp_sys`, `hr`, …) used by PWA and seeds |
| `loinc_code` | Char, required, index | LOINC code (FHIR `code.coding.code`, system `http://loinc.org`) |
| `ucum_unit` | Char | UCUM unit code (`mm[Hg]`, `Cel`, `kg`, `/min`, `%`, `cm`, `mmol/L`) — FHIR `valueQuantity.code` |
| `unit_display` | Char | Human unit (`mmHg`, `°C`, `bpm`) — FHIR `valueQuantity.unit` |
| `value_type` | Selection `[('quantity','Numeric'),('string','Text'),('panel','Panel (no value)')]`, default `quantity`, required | Panels (BP) carry no value themselves |
| `parent_id` | Many2one `health.vitals.type`, string 'Panel' | Component→panel (systolic → BP panel); FHIR `Observation.component` grouping |
| `child_ids` | One2many inverse of parent_id | Panel members |
| `decimals` | Integer, default 0 | Display precision |
| `plausible_min` / `plausible_max` | Float | Hard input-validation range (not clinical alert) |
| `default_method` | Char | e.g. 'oscillometric' |
| `is_fhir_vital_sign` | Boolean, default False | Member of FHIR vital-signs profile (adds category `vital-signs`) |
| `sequence` | Integer, default 10 | Ordering |
| `active` | Boolean, default True | Archive |

SQL constraints: `('uniq_loinc', 'UNIQUE(loinc_code)', 'LOINC code must be unique.')`, `('uniq_code', 'UNIQUE(code)', 'Internal code must be unique.')`.

### 2.2.2 `health.observation` — one row = one observation

```
_name = 'health.observation'
_description = 'Clinical Observation'
_inherit = ['mail.thread']
_order = 'effective_datetime desc, id desc'
_rec_name = 'display_name'
```

| field | type | purpose |
|---|---|---|
| `display_name` | Char, compute stored (`f"{type.name}: {value} {unit} — {client}"`) | Label |
| `client_id` | Many2one `res.partner`, required, domain `[('is_patient','=',True)]`, ondelete `restrict`, index, tracking | FHIR `Observation.subject` |
| `vitals_type_id` | Many2one `health.vitals.type`, required, ondelete `restrict`, index | FHIR `Observation.code` |
| `loinc_code` | Char related `vitals_type_id.loinc_code`, store=True | Search/BI without join |
| `value_quantity` | Float | FHIR `valueQuantity.value` (required when type.value_type = quantity and not a panel) |
| `value_text` | Char | FHIR `valueString` (value_type = string) |
| `ucum_unit` | Char related `vitals_type_id.ucum_unit`, store=True | UCUM |
| `effective_datetime` | Datetime, required, default now, index, tracking | FHIR `effectiveDateTime` |
| `performer_id` | Many2one `res.users`, default `lambda self: self.env.uid` | FHIR `performer` |
| `method` | Char | FHIR `method.text` |
| `body_position` | Selection `[('sitting','Sitting'),('standing','Standing'),('lying','Lying'),('unknown','Unknown')]` | Extension `bodyPosition` |
| `device` | Char | FHIR `device.display` |
| `order_id` | Many2one `health.fieldservice.order`, ondelete `set null`, index | FHIR `encounter` |
| `clinical_note_id` | Many2one `health.clinical.note`, ondelete `set null`, index | Back-compat linkage |
| `parent_id` | Many2one `health.observation`, string 'Panel Observation', ondelete `cascade` | Systolic/diastolic under a BP-panel row; FHIR `Observation.component` / `hasMember` |
| `child_ids` | One2many inverse parent_id | Panel members |
| `state` | Selection `[('preliminary','Preliminary'),('final','Final'),('amended','Amended'),('entered_in_error','Entered in Error')]`, default `final`, required, tracking | FHIR `Observation.status` (`entered_in_error`→`entered-in-error`) |
| `is_abnormal` | Boolean, readonly, index | Set by threshold check |
| `alert_level` | Selection `[('none','None'),('warning','Warning'),('critical','Critical')]`, default `none`, readonly, tracking | Highest breached threshold |
| `catchment_province_id` | per §0.3 (depends `client_id...`) | Record rules |
| `company_id` | Many2one `res.company`, default current | Multi-company |

Constraints:
- Python `_check_value`: quantity types require `value_quantity` set (panels exempt); if `plausible_min/max` defined on type, out-of-range → `ValidationError` ("Value outside plausible range").
- `create()` (batch-safe): after create, call `_check_thresholds()`.
- No unlink for clinical integrity: override `unlink()` → raise `UserError` unless state `entered_in_error` or user in `health_base.group_healthcare_admin`+. Corrections: set `state='entered_in_error'` and re-enter (append-only discipline per interop §6.7).

`action_mark_entered_in_error` (button, nurse+): state → `entered_in_error`.

### 2.2.3 `health.vitals.threshold` — per-client alert thresholds

```
_name = 'health.vitals.threshold'
_description = 'Per-Client Vitals Alert Threshold'
_order = 'client_id, vitals_type_id, severity'
```

| field | type | purpose |
|---|---|---|
| `client_id` | Many2one `res.partner`, required, domain is_patient, ondelete `cascade`, index | Owner |
| `vitals_type_id` | Many2one `health.vitals.type`, required, domain `[('value_type','=','quantity')]` | Which observation |
| `severity` | Selection `[('warning','Warning'),('critical','Critical')]`, default `warning`, required | Alert band |
| `min_value` / `max_value` | Float (either may be unset; at least one required — Python constraint) | Breach bounds |
| `escalation_action` | Selection `[('none','Record Only'),('chatter','Post on Client Chatter'),('activity','Create Activity for Facility Manager'),('activity_author','Create Activity for Care Plan Author')]`, default `activity`, required | What happens on breach |
| `catchment_province_id` | per §0.3 | Record rules |
| `active` | Boolean, default True | Archive |
| `notes` | Char | Rationale |

SQL constraint: `('uniq_threshold', 'UNIQUE(client_id, vitals_type_id, severity)', 'One threshold per client, type and severity.')`.

### 2.2.4 `health.clinical.note` extension

```
_inherit = 'health.clinical.note'
```

| field | type | purpose |
|---|---|---|
| `observation_ids` | One2many `health.observation` `clinical_note_id` | Structured vitals of this note |
| `has_structured_vitals` | Boolean, compute stored (`bool(observation_ids)`), string 'Structured' | The "structured" flag; free-text `vital_signs` **stays untouched** |

### 2.2.5 `res.partner` extension

| field | type | purpose |
|---|---|---|
| `observation_ids` | One2many `health.observation` `client_id` | Smart button + trending from client form |
| `vitals_threshold_ids` | One2many `health.vitals.threshold` `client_id` | Threshold management on client form |
| `observation_count` | Integer compute | Smart button |

## 2.3 Business methods

```python
def _check_thresholds(self):        # on health.observation recordset
```
For each quantity observation: fetch active thresholds (client, type). Critical checked first; if `value_quantity < min_value` or `> max_value` → `is_abnormal=True`, `alert_level=severity`, then execute `escalation_action`:
- `chatter`: `client_id.message_post` (note subtype) "ALERT: {type} {value}{unit} breached {severity} threshold [{min}-{max}]" (plain text, no emoji).
- `activity`: `activity_schedule` todo on `client_id.primary_facility_id.facility_manager_id.user_id` (fallback: skip with `_logger.warning`, same pattern as `api.py::_create_follow_up_activity`).
- `activity_author`: if `health_careplan` installed and client has an active plan → author; else fallback to facility manager. Implement via `if 'health.careplan' in self.env:` guard (no hard dependency).

```python
@api.model
def create_panel(self, client_id, panel_type_code, components, **common):
```
Helper for BP: creates the panel row (`value_type='panel'`) + child component rows in one call; `components = [{'code': 'bp_sys', 'value': 120}, ...]`; `common` carries effective_datetime/order_id/method/body_position/device/clinical_note_id. Returns panel record. Used by the PWA endpoint.

```python
@api.model
def get_trend(self, client_id, vitals_type_id, date_from=None, date_to=None, limit=200):
```
Returns ordered `[{datetime, value}]` for graphs/PWA sparklines (state `final`/`amended` only).

## 2.4 State machine

`health.observation.state`: `final` on creation (nurse-entered point-of-care data); `preliminary` reserved for device/import flows (writable at create); `final → amended` via write of value by head_nurse+ (auto-set in `write()` when `value_quantity` changes on a final record); `→ entered_in_error` via `action_mark_entered_in_error` (nurse+, terminal). No other transitions; no unlink (§2.2.2).

## 2.5 Views & menus

- `view_health_observation_list`: effective_datetime, client_id, vitals_type_id, value_quantity, unit_display (via related), alert_level (badge, decoration-danger for critical, decoration-warning for warning), performer_id, order_id, state. `default_order="effective_datetime desc"`.
- `view_health_observation_form`: statusbar (final/amended/entered_in_error); groups client/type/value/unit | datetime/performer/method/position/device; links order/note/parent; children inline list for panels; `<chatter/>`.
- `view_health_observation_graph`: type `graph`, mode `line`, `<field name="effective_datetime" interval="day"/>`, measure `value_quantity`, group by `vitals_type_id`.
- `view_health_observation_pivot`: rows client, cols type, measure avg value.
- `view_health_observation_search`: filters Abnormal (`is_abnormal`), Critical, Today/This Week (effective_datetime), My Entries; group by client / type / order.
- `view_health_vitals_type_list/form` (Configuration): all catalog fields; child_ids inline.
- `view_health_vitals_threshold_list` (editable bottom) + search.
- `health.clinical.note` form inherit: add page "Structured Vitals" with `observation_ids` inline editable list (vitals_type_id, value_quantity, effective_datetime, body_position) and `has_structured_vitals` badge next to the legacy `vital_signs` field (which is kept and labeled "Vital Signs (free text — legacy)").
- `res.partner` form inherit (on the health client form from `health_base/views/health_patient_views.xml`): smart button "Vitals" (observation_count) opening list+graph filtered by client; new page "Alert Thresholds" with `vitals_threshold_ids` editable list.
- FSO form inherit is NOT needed (observations reachable via clinical note + client), but add smart button "Vitals" on FSO opening observations domain `[('order_id','=',id)]`.
- Menus: `menu_health_vitals` "Vitals & Observations" under `health_base.menu_healthcare_clinical` sequence 8 → action on `health.observation` (list,graph,pivot,form); `menu_health_vitals_types` "Observation Types" under `health_base.menu_healthcare_lookups`; `menu_health_vitals_thresholds` "Vitals Thresholds" under `menu_health_vitals` (head_nurse+).

## 2.6 Security

Access matrix (r/w/c/u):

| model | receptionist | nurse | head_nurse | doctor | ops_manager | finance | manager | admin | owner |
|---|---|---|---|---|---|---|---|---|---|
| health.observation | 1000 | 1110 | 1110 | 1110 | 1000 | 0000 | 1110 | 1110 | 1111 |
| health.vitals.type | 1000 | 1000 | 1000 | 1000 | 1000 | 1000 | 1110 | 1110 | 1111 |
| health.vitals.threshold | 1000 | 1000 | 1110 | 1110 | 1000 | 0000 | 1110 | 1110 | 1111 |

Record rules (§0.3 template) on `health.observation` and `health.vitals.threshold` (both carry `catchment_province_id`). `health.vitals.type` is a global catalog — no rules.

## 2.7 PWA API (`controllers/api.py`, class `HealthVitalsPWAController`)

| route | method | request | response `data` |
|---|---|---|---|
| `/health_pwa/api/vitals/types` | GET | — | `{'types': [{id, code, loinc_code, name, name_vi, ucum_unit, unit_display, value_type, parent_code, decimals, plausible_min, plausible_max, sequence}]}` (reference data → PouchDB) |
| `/health_pwa/api/fso/<int:order_id>/vitals` | POST | `{"observations": [{"code": "hr", "value": 78, "effective_datetime": "...", "body_position": "sitting", "method": "", "device": ""}], "bp": {"systolic": 120, "diastolic": 80}, "clinical_note_id": null}` | `{'created_ids': [...], 'alerts': [{type_code, value, alert_level, message}]}` — BP object routed through `create_panel`; sets `client_id = order.patient_id`, `order_id` |
| `/health_pwa/api/patients/<int:patient_id>/vitals` | GET, params `type_code`, `limit` (default 50), `date_from` | `{'observations': [{id, type_code, loinc_code, name, value, unit, effective_datetime, alert_level, performer}], 'thresholds': [{type_code, severity, min, max}]}` |
| `/health_pwa/api/patients/<int:patient_id>/vitals/trend` | GET, params `type_code`, `days` (default 30) | `{'points': [{t, v}], 'unit': 'mmHg'}` (thin wrapper on `get_trend`) |

PWA frontend (in `health_pwa`): visit screen gets a "Vitals" entry sheet (numeric keypads, BP as paired field, plausible-range client-side validation from the types store, threshold breach shows inline alert banner); client screen gets sparkline trends. New PouchDB store `health_vitals_types` (reference, synced via new `_get_vitals_type_changes` handler in `sync.py`); offline observations queue as outbox mutations replayed to `/fso/<id>/vitals`. Clinical data is **append-only** offline (no edit of synced observations). Bump PWA version (3 places).

## 2.8 FHIR serialization notes

| Odoo | FHIR `Observation` |
|---|---|
| row | one Observation; panels (`value_type='panel'`) emit `component[]` from `child_ids` (BP profile) or `hasMember` |
| `state` | `status` (`entered_in_error`→`entered-in-error`) |
| `vitals_type_id.loinc_code` | `code.coding[0]` system `http://loinc.org`; `is_fhir_vital_sign` → `category` = `vital-signs` |
| `value_quantity` + `ucum_unit` | `valueQuantity{value, unit=unit_display, system=http://unitsofmeasure.org, code=ucum_unit}` |
| `value_text` | `valueString` |
| `effective_datetime` | `effectiveDateTime` (UTC → ISO with offset) |
| `performer_id` | `performer` → Practitioner |
| `client_id` | `subject` → Patient |
| `order_id` | `encounter` → Encounter |
| `method`, `device`, `body_position` | `method.text`, `device.display`, extension `http://hl7.org/fhir/StructureDefinition/observation-bodyPosition` |
| `is_abnormal`/`alert_level` | `interpretation` (`H`/`L` derivable from threshold breach direction; minimally `A` abnormal) |

## 2.9 Data seeds — `data/health_vitals_type_data.xml` (`noupdate="1"`)

| xml id | code | loinc_code | name / name_vi | ucum_unit | unit_display | value_type | parent | plausible | is_fhir_vital_sign |
|---|---|---|---|---|---|---|---|---|---|
| `vitals_type_bp_panel` | bp_panel | 85354-9 | Blood pressure panel / Huyết áp | — | — | panel | — | — | ✓ |
| `vitals_type_bp_systolic` | bp_sys | 8480-6 | Systolic blood pressure / Huyết áp tâm thu | mm[Hg] | mmHg | quantity | bp_panel | 40–300 | ✓ |
| `vitals_type_bp_diastolic` | bp_dia | 8462-4 | Diastolic blood pressure / Huyết áp tâm trương | mm[Hg] | mmHg | quantity | bp_panel | 20–200 | ✓ |
| `vitals_type_heart_rate` | hr | 8867-4 | Heart rate / Nhịp tim | /min | bpm | quantity | — | 20–300 | ✓ |
| `vitals_type_resp_rate` | rr | 9279-1 | Respiratory rate / Nhịp thở | /min | breaths/min | quantity | — | 4–80 | ✓ |
| `vitals_type_body_temp` | temp | 8310-5 | Body temperature / Nhiệt độ | Cel | °C | quantity, decimals 1 | — | 30–45 | ✓ |
| `vitals_type_spo2` | spo2 | 2708-6 | Oxygen saturation in Arterial blood / SpO2 | % | % | quantity | — | 50–100 | ✓ |
| `vitals_type_spo2_pulse_ox` | spo2_po | 59408-5 | Oxygen saturation by Pulse oximetry / SpO2 (máy đo) | % | % | quantity | — | 50–100 | ✓ |
| `vitals_type_weight` | weight | 29463-7 | Body weight / Cân nặng | kg | kg | quantity, decimals 1 | — | 1–400 | ✓ |
| `vitals_type_height` | height | 8302-2 | Body height / Chiều cao | cm | cm | quantity, decimals 1 | — | 30–250 | ✓ |
| `vitals_type_bmi` | bmi | 39156-5 | Body mass index / BMI | kg/m2 | kg/m² | quantity, decimals 1 | — | 8–80 | ✓ |
| `vitals_type_glucose` | glucose | 15074-8 | Glucose [Moles/volume] in Blood / Đường huyết | mmol/L | mmol/L | quantity, decimals 1 | — | 1–50 | — |
| `vitals_type_pain_score` | pain | 72514-3 | Pain severity 0-10 / Mức độ đau | {score} | /10 | quantity | — | 0–10 | — |

(SpO2: default PWA entry uses `spo2_po` 59408-5 — pulse oximetry is what field nurses actually measure; 2708-6 kept for interop inbound.)

## 2.10 Acceptance criteria

1. Module install seeds exactly the 13 catalog rows above with unique LOINC codes; re-upgrade does not duplicate or overwrite manual edits (`noupdate=1`).
2. POSTing the vitals payload with `bp` creates 3 rows (panel + 2 components, components linked via `parent_id`) and responds in the standard `{success, timestamp, data}` envelope.
3. An observation of 250 for heart rate is rejected (plausible range) with a `ValidationError`; 180 is accepted.
4. A client threshold (hr, critical, max 120) causes an observation of 130 to be flagged `alert_level='critical'`, and an activity is created for the facility manager's user; the API response lists the alert.
5. Graph view trends a client's weight over time; `get_trend` excludes `entered_in_error` rows.
6. Free-text `vital_signs` on `health.clinical.note` still saves from the existing PWA endpoint unchanged; a note with structured rows shows `has_structured_vitals = True`.
7. Deleting a final observation as a nurse raises `UserError`; marking entered-in-error works and removes it from trends.
8. Editing the value of a `final` observation as head nurse flips state to `amended` automatically.
9. Catchment record rules hold: nurse in HCM cannot list HN clients' observations.
10. `GET /health_pwa/api/vitals/types` returns all active types incl. `name_vi` and plausible ranges; the PWA caches them in the `health_vitals_types` PouchDB store.

## 2.11 Integration touchpoints

- `health.clinical.note` (+ its PWA save flow — untouched), `health.fieldservice.order.patient_id`.
- `health_careplan.goal.vitals_type_id` + `latest_value` reads `health.observation` (§1).
- `health_forms` extraction creates `health.observation` rows (§4).
- `biz_bi`: `health.observation` is graph/pivot-ready; silver dataset can read `loinc_code`, `value_quantity`, `effective_datetime` (per roadmap Horizon-0 "trending charts in biz_bi").
- Future `health_fhir_core` Observation serializer (§2.8).

---

# 3. `health_emar` — Medication Orders & Administrations (eMAR)

## 3.1 `__manifest__.py`

```python
{
    'name': 'Healthcare eMAR',
    'version': '19.0.1.0.0',
    'category': 'Healthcare/Clinical',
    'summary': 'Medication orders, administration records, schedules and PWA med checklist (FHIR MedicationRequest/MedicationAdministration)',
    'author': 'VAFHS Development Team',
    'website': 'https://www.vafhs.com',
    'license': 'LGPL-3',
    'depends': ['health_base', 'health_fieldservice'],
    'data': [
        'security/health_emar_security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence.xml',
        'data/ir_cron.xml',
        'data/health_medication_notgiven_reason_data.xml',
        'views/health_medication_views.xml',
        'views/health_medication_order_views.xml',
        'views/health_medication_administration_views.xml',
        'views/health_fieldservice_order_views.xml',
        'views/res_partner_views.xml',
        'views/health_emar_menus.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
```

## 3.2 Models

### 3.2.1 `health.medication` extension (catalog lives in `health_base` — extend, don't replace)

```
_inherit = 'health.medication'
```

| field | type | purpose |
|---|---|---|
| `rxnorm_code` | Char, string 'RxNorm RXCUI', index | Canonical code (FHIR `Medication.code`, system `http://www.nlm.nih.gov/research/umls/rxnorm`) |
| `form` | Selection `[('tablet','Tablet'),('capsule','Capsule'),('liquid','Liquid/Syrup'),('injection','Injection'),('patch','Patch'),('cream','Cream/Ointment'),('inhaler','Inhaler'),('drops','Drops'),('suppository','Suppository'),('other','Other')]` | FHIR `Medication.doseForm` |
| `strength` | Char, e.g. '500 mg' | Display strength; FHIR `Medication.ingredient.strength` (text) |
| `dav_reg_no` | Char, string 'DAV Registration No. (số đăng ký)' | VN drug-registry crosswalk (interop §2.2) |

Existing fields reused as-is: `name`, `generic_name`, `brand_name`, `vietnamese_name` (the local vi name), `therapeutic_category`, `contraindications`. **Do not** add a duplicate vi-name field.

### 3.2.2 `health.medication.order`

```
_name = 'health.medication.order'
_description = 'Medication Order'
_inherit = ['mail.thread', 'mail.activity.mixin']
_order = 'create_date desc'
_rec_name = 'display_name'
```

| field | type | purpose |
|---|---|---|
| `name` | Char, readonly, default 'New', sequence `health.medication.order` prefix `MO` | Reference |
| `display_name` | Char compute stored: `f"{medication.name} — {client.name} ({name})"` | Label |
| `client_id` | Many2one `res.partner`, required, domain is_patient, ondelete `restrict`, index, tracking | FHIR `subject` |
| `medication_id` | Many2one `health.medication`, required, ondelete `restrict`, tracking | FHIR `medication` |
| `prescriber_id` | Many2one `res.partner`, string 'Prescriber', tracking, help 'External or internal prescribing doctor (contact record)' | FHIR `requester` (same comodel convention as `health.fieldservice.order.referring_doctor_id`) |
| `prescriber_name` | Char | Free-text fallback when no contact exists |
| `state` | Selection `[('draft','Draft'),('active','Active'),('on_hold','On Hold'),('completed','Completed'),('cancelled','Cancelled')]`, default `draft`, required, tracking | FHIR `MedicationRequest.status` (`on_hold`→`on-hold`) |
| `dose_quantity` | Float, required-for-activate, tracking | FHIR `Dosage.doseAndRate.doseQuantity.value` |
| `dose_unit` | Char, required-for-activate, help 'UCUM or common unit: mg, mL, tablet, IU, puff' | `doseQuantity.unit` |
| `route` | Selection `[('oral','Oral'),('sublingual','Sublingual'),('topical','Topical'),('subcutaneous','Subcutaneous'),('intramuscular','Intramuscular'),('intravenous','Intravenous'),('inhalation','Inhalation'),('rectal','Rectal'),('ophthalmic','Ophthalmic'),('otic','Otic'),('nasal','Nasal'),('other','Other')]`, required-for-activate, tracking | FHIR `Dosage.route` |
| `frequency` | Selection `[('od','Once daily (OD)'),('bd','Twice daily (BD)'),('tds','Three times daily (TDS)'),('qid','Four times daily (QID)'),('q4h','Every 4 hours'),('q6h','Every 6 hours'),('q8h','Every 8 hours'),('q12h','Every 12 hours'),('weekly','Weekly'),('prn','PRN / As needed'),('other','Other — see instructions')]`, required-for-activate, tracking | FHIR `Dosage.timing` |
| `admin_times` | Char, help 'Comma-separated local times HH:MM, e.g. 08:00,20:00. Optional; defaults per frequency.' | Schedule generation |
| `is_prn` | Boolean, compute stored (`frequency == 'prn'`) | PRN flag; FHIR `Dosage.asNeededBoolean` |
| `prn_reason` | Char, required if is_prn (Python constraint) | FHIR `asNeededCodeableConcept.text` |
| `start_date` | Date, required, default today, tracking | FHIR `dispenseRequest.validityPeriod.start` / dosage boundsPeriod |
| `end_date` | Date, tracking | boundsPeriod.end (open = long-term) |
| `instructions` | Text, translate | FHIR `Dosage.patientInstruction` |
| `interaction_warning` | Text, readonly | Result of safety check |
| `interaction_severity` | Selection `[('none','None'),('minor','Minor'),('moderate','Moderate'),('major','Major')]`, default `none`, readonly, tracking | Highest severity found |
| `interaction_ack` | Boolean, tracking | Head-nurse/doctor acknowledgement of major interactions |
| `interaction_ack_by_id` / `interaction_ack_date` | Many2one `res.users` / Datetime, readonly | Audit |
| `administration_ids` | One2many `health.medication.administration` `order_id` | MAR rows |
| `administration_count` | Integer compute | Smart button |
| `catchment_province_id` | per §0.3 | Record rules |
| `company_id` | Many2one `res.company`, default current | Multi-company |
| `active` | Boolean, default True | Archive |

SQL constraint: `('date_check', "CHECK (end_date IS NULL OR end_date >= start_date)", 'End date must be on/after start date.')`, `('dose_positive', "CHECK (dose_quantity IS NULL OR dose_quantity > 0)", 'Dose must be positive.')`.

### 3.2.3 `health.medication.administration`

```
_name = 'health.medication.administration'
_description = 'Medication Administration Record'
_inherit = ['mail.thread']
_order = 'planned_datetime desc, id desc'
_rec_name = 'display_name'
```

| field | type | purpose |
|---|---|---|
| `display_name` | Char compute stored: `f"{medication} {planned local time} — {client}"` | Label |
| `order_id` | Many2one `health.medication.order`, required, ondelete `cascade`, index | Parent order |
| `client_id` | Many2one related `order_id.client_id`, store=True, index | Search |
| `medication_id` | Many2one related `order_id.medication_id`, store=True | Search/display |
| `fso_id` | Many2one `health.fieldservice.order`, ondelete `set null`, index | The visit it is administered in; FHIR `context` |
| `nurse_id` | Many2one `res.users`, readonly (set on recording) | FHIR `performer` |
| `planned_datetime` | Datetime, required, index | Scheduled slot (UTC; generated from `admin_times` in the booking timezone — reuse `fso.booking_timezone` when linked, else facility/catchment tz) |
| `actual_datetime` | Datetime, readonly | When actually given/attempted |
| `state` | Selection `[('planned','Planned'),('given','Given'),('not_given','Not Given'),('refused','Refused'),('cancelled','Cancelled')]`, default `planned`, required, tracking, index | FHIR `MedicationAdministration.status`: given→completed, not_given/refused→not-done (+statusReason), cancelled→stopped |
| `reason_id` | Many2one `health.medication.notgiven.reason`, required when state in (not_given, refused) (Python constraint) | FHIR `statusReason` |
| `dose_given` | Float, default from order dose on recording | FHIR `dosage.dose.value` (may differ from ordered) |
| `dose_unit` | Char related `order_id.dose_unit` store=True | Unit |
| `witness_id` | Many2one `res.users`, string 'Witness' | Double-signoff (high-risk meds); extension |
| `notes` | Text | FHIR `note` |
| `is_prn_dose` | Boolean, default False, readonly | Created ad-hoc for a PRN order |
| `catchment_province_id` | per §0.3 (depends `client_id...` — related through order works: depend on `order_id.client_id...`) | Record rules |

SQL constraint: `('uniq_slot', 'UNIQUE(order_id, planned_datetime)', 'Duplicate administration slot for this order.')` — exempt PRN by giving PRN doses `planned_datetime = actual_datetime` (always unique in practice; keep constraint).

Append-only: override `unlink()` → `UserError` unless state `planned`/`cancelled` or admin+. Recorded administrations (`given/not_given/refused`) are immutable except `notes` (enforce in `write()`).

### 3.2.4 `health.medication.notgiven.reason` (lookup)

```
_name = 'health.medication.notgiven.reason'
_description = 'Medication Not-Given Reason'
_order = 'sequence, name'
```

Fields: `name` Char required translate, `name_vi` Char, `code` Char required unique (sql), `applies_to` Selection `[('refused','Refused'),('not_given','Not Given'),('both','Both')]` default `both`, `sequence` Integer default 10, `active` Boolean default True.

### 3.2.5 `health.fieldservice.order` extension

| field | type | purpose |
|---|---|---|
| `medication_administration_ids` | One2many `health.medication.administration` `fso_id` | Visit med checklist |
| `medication_admin_count` / `medication_admin_done_count` | Integer compute | Smart button / badge (done = state != planned) |

### 3.2.6 `res.partner` extension

`medication_order_ids` One2many `health.medication.order` `client_id`; `medication_order_count` compute; smart button "Medications" on client form.

## 3.3 State machines

### Order (`health.medication.order`)

| transition | button | guard | groups |
|---|---|---|---|
| draft → active | `action_activate` | dose_quantity/dose_unit/route/frequency/start_date set; runs `_run_interaction_check()`; if `interaction_severity == 'major'` and not `interaction_ack` → `UserError` "Acknowledge major interaction first"; on success calls `action_generate_schedule()` for the next horizon | head_nurse, doctor, manager+ |
| active → on_hold | `action_hold` | cancels (`state='cancelled'`) future `planned` administrations | head_nurse, doctor, manager+ |
| on_hold → active | `action_resume` | regenerates schedule from today | head_nurse, doctor, manager+ |
| active → completed | `action_complete` (also auto by cron when `end_date < today` and no planned admins remain) | — | head_nurse, doctor, manager+ |
| draft/active/on_hold → cancelled | `action_cancel` | cancels future planned admins | head_nurse, doctor, manager+ |
| cancelled → draft | `action_reset_draft` | — | manager+ |

`action_acknowledge_interaction` (head_nurse, doctor, manager+): sets `interaction_ack=True`, `interaction_ack_by_id`, `interaction_ack_date`; logged in chatter.

### Administration (`health.medication.administration`)

| transition | method | guard |
|---|---|---|
| planned → given | `action_record_given(actual_datetime=None, dose_given=None, witness_id=None, notes=None)` | order state == active; sets `nurse_id=env.uid`, `actual_datetime` default now, `dose_given` default order dose |
| planned → not_given | `action_record_not_given(reason_id, notes=None)` | reason required, `applies_to in ('not_given','both')` |
| planned → refused | `action_record_refused(reason_id, notes=None)` | reason required, `applies_to in ('refused','both')` |
| planned → cancelled | `action_cancel_slot` | order hold/cancel flows; head_nurse+ |

Recording allowed for nurse+ (the field workforce). All three recording methods are the PWA tick backend.

## 3.4 Business methods

```python
def _run_interaction_check(self):    # on order
```
Collect names: `self.medication_id.name` + names of the client's **other** orders in state active/on_hold. Call `self.env['health.medication.safety'].check_drug_interactions(med_names)` (existing model, takes a list of medication names, returns interaction findings backed by `health.medication.interaction` + RxNorm API). Store a human summary in `interaction_warning`, map highest severity into `interaction_severity` (their selection: minor/moderate/major — map anything unknown to moderate). Never blocks on API failure: wrap in try/except, log warning, set warning text 'Interaction check unavailable'.

```python
def action_generate_schedule(self, date_from=None, date_to=None):   # on order
```
Non-PRN active orders only. Default window: `max(today, start_date)` → `min(start_date+horizon, end_date or ∞)` where horizon = `int(ir.config_parameter 'health_emar.schedule_horizon_days' or 7)`. Slot times: parse `admin_times`; defaults per frequency: od `['08:00']`, bd `['08:00','20:00']`, tds `['08:00','13:00','20:00']`, qid `['06:00','12:00','18:00','22:00']`, q4h/q6h/q8h/q12h evenly from 06:00, weekly `['08:00']` on start_date's weekday, other → no auto slots. Times are wall-clock in the client's timezone (client catchment/facility timezone — reuse the pattern from `health.staff.assignment` lines 400-416: default `'Asia/Ho_Chi_Minh'`), converted to UTC for `planned_datetime`. Idempotent via the unique slot constraint (`SELECT` existing first). After generation call `_link_administrations_to_fso()`.

```python
def _link_administrations_to_fso(self):
```
For each unlinked `planned` administration: find the client's FSO with `state in ('confirmed','assigned','in_progress')` whose `scheduled_date` equals the slot's local date (prefer nearest `scheduled_datetime`); set `fso_id`. Called from schedule generation, from the nightly cron, and from an FSO `write()` hook when `scheduled_datetime`/`state` changes (mirror of the careplan hook).

```python
def create_prn_dose(self, order, fso=None):   # model method on administration
```
For PRN orders from the PWA: creates a slot with `planned_datetime=now`, `is_prn_dose=True`, immediately ready to record.

```python
@api.model
def _cron_emar_maintenance(self):   # nightly 02:00, model health.medication.order
```
(1) `action_generate_schedule()` for all active non-PRN orders (rolling horizon); (2) `_link_administrations_to_fso()`; (3) auto-complete orders past `end_date` with no remaining planned slots; (4) mark overdue: planned slots older than 24h with no linked completed visit stay `planned` (surfaced by the "Missed doses" filter — no auto state change; clinical staff must record not_given explicitly).

## 3.5 Views & menus

- Order form: statusbar draft→active→completed; buttons per §3.3 + `action_acknowledge_interaction` (visible when severity == major, `invisible` otherwise); alert banner div showing `interaction_warning` when set (class `alert alert-warning`, mono flat style); groups client/medication/prescriber | dose/route/frequency/admin_times/PRN | start/end/instructions; page "Administrations" inline readonly list; `<chatter/>`.
- Order list: name, client_id, medication_id, dose display, frequency, start_date, end_date, interaction_severity (badge), state (badge). Search: Active, PRN, Major Interaction, group by client/medication/state.
- Administration list ("MAR register"): planned_datetime, client_id, medication_id, dose_given, state (decoration: success given / danger refused / warning not_given), nurse_id, fso_id, reason_id. Filters: Today, Missed (planned & planned_datetime < now - 24h), Refused, group by client/order/state. Calendar view optional-out-of-scope.
- FSO form inherit: page "Medications" with `medication_administration_ids` readonly list + smart button.
- Client form inherit: "Medications" smart button.
- Reasons list (Configuration, editable).
- Menus: `menu_health_emar` "Medications (eMAR)" under `health_base.menu_healthcare_clinical` sequence 9 with children "Medication Orders" (action orders), "Administration Register" (action administrations), and under `health_base.menu_healthcare_lookups`: "Medication Catalog" (existing `health.medication` action — reuse `health_base` action if exposed, else define one) and "Not-Given Reasons".

## 3.6 Security

| model | receptionist | nurse | head_nurse | doctor | ops_manager | manager | admin | owner |
|---|---|---|---|---|---|---|---|---|
| health.medication.order | 1000 | 1000 | 1110 | 1110 | 1000 | 1110 | 1110 | 1111 |
| health.medication.administration | 1000 | 1110 | 1110 | 1110 | 1000 | 1110 | 1110 | 1111 |
| health.medication.notgiven.reason | 1000 | 1000 | 1000 | 1000 | 1000 | 1110 | 1110 | 1111 |

(Nurses record administrations but cannot author orders — matches "prescriber/head-nurse authors, nurse administers".) Record rules (§0.3) on order + administration. Reason lookup: global, no rules.

## 3.7 PWA API (`controllers/api.py`, class `HealthEmarPWAController`)

| route | method | request | response `data` |
|---|---|---|---|
| `/health_pwa/api/fso/<int:order_id>/medications` | GET | — | `{'administrations': [{id, order_id, medication_name, medication_name_vi, dose: '500 mg', route, planned_datetime, state, is_prn_dose, instructions, reason_id, notes}], 'prn_orders': [{id, medication_name, dose, route, prn_reason}], 'reasons': [{id, code, name, name_vi, applies_to}]}` — administrations = slots linked to this FSO **plus** unlinked planned slots for the client on the visit's local date |
| `/health_pwa/api/administrations/<int:admin_id>/record` | POST | `{"status": "given"|"not_given"|"refused", "actual_datetime": "...", "dose_given": 1.0, "reason_id": 3, "witness_id": null, "notes": ""}` | `{'admin_id', 'state', 'message'}` (dispatch to the three action methods) |
| `/health_pwa/api/fso/<int:order_id>/medications/prn` | POST | `{"order_id": <medication order id>}` | created administration dict — `create_prn_dose` linked to the FSO |
| `/health_pwa/api/patients/<int:patient_id>/medication_orders` | GET | — | `{'orders': [{id, medication_name, dose, route, frequency, is_prn, start_date, end_date, state, instructions, interaction_severity}]}` |

PWA frontend (in `health_pwa`): visit screen gains a "Medications" checklist (given / refused / not-given with reason bottom-sheet; PRN "+ dose" button). Med slots ride inside the `health_orders` PouchDB docs (extend `sync.py::_get_fso_changes` with `medication_administrations: [...]`, guarded by `hasattr`); reasons cached in a new reference store `health_emar_reasons`. Offline recording queues mutations to `/administrations/<id>/record` with `client_mutation_id` idempotency (server: recording an already-recorded slot with same status returns success no-op; different status → 409-style error in envelope). Bump PWA version (3 places).

## 3.8 FHIR serialization notes

| Odoo | FHIR |
|---|---|
| `health.medication` (+`rxnorm_code`, `form`, `dav_reg_no`) | `Medication` (code = RxNorm coding + local coding `health19-medications`; doseForm; DAV number as `identifier` system `https://dav.gov.vn/so-dang-ky`) |
| `health.medication.order` | `MedicationRequest`: `status` verbatim (`on_hold`→`on-hold`), `intent='order'`, `subject`, `requester`=prescriber, `dosageInstruction[0]` = {doseAndRate.doseQuantity(dose_quantity, dose_unit), route (coded local + SNOMED later), timing (frequency→`timing.code` od→QD, bd→BID, tds→TID, qid→QID, q4h..q12h→Q4H.., weekly→WK; boundsPeriod=start/end; admin_times→timeOfDay[]), asNeededBoolean=is_prn, asNeededCodeableConcept.text=prn_reason, patientInstruction=instructions} |
| `health.medication.administration` | `MedicationAdministration`: `status` given→completed, not_given/refused→not-done, cancelled→stopped; `statusReason.text`=reason name (+local code); `effectiveDateTime`=actual_datetime (fallback planned); `performer.actor`=nurse; `context`=Encounter(fso_id); `request`=MedicationRequest(order_id); `dosage.dose`=dose_given+unit; witness as `performer` with function code `witness` |
| interaction findings | `DetectedIssue` (already mapped for `health.medication.safety` in interop doc) |

## 3.9 Data seeds

- `data/ir_sequence.xml`: `health.medication.order` prefix `MO`, padding 5.
- `data/ir_cron.xml`: nightly `eMAR: schedule maintenance` cron (§3.4).
- `data/health_medication_notgiven_reason_data.xml` (`noupdate="1"`): codes `refused_client` (Client refused / Khách hàng từ chối, refused), `asleep` (Client asleep/unavailable / Khách hàng ngủ/vắng mặt, not_given), `nausea` (Nausea or vomiting / Buồn nôn hoặc nôn, both), `npo` (Nil by mouth (NPO) / Nhịn ăn uống, not_given), `unavailable` (Medication unavailable / Không có thuốc, not_given), `clinical_hold` (Withheld — clinical judgement / Tạm ngừng theo đánh giá lâm sàng, not_given), `other` (Other / Khác, both).

## 3.10 Acceptance criteria

1. Activating an order without route/frequency raises `UserError`; a complete order activates, runs the interaction check and generates 7 days of planned slots at the default times for its frequency.
2. A `bd` order with `admin_times='07:30,19:30'` generates exactly 2 slots/day at 07:30/19:30 Asia/Ho_Chi_Minh (stored UTC); regeneration is idempotent (unique constraint, no duplicates).
3. When a client has FSOs on slot dates, slots are linked to the matching FSO and appear in `GET /health_pwa/api/fso/<id>/medications`.
4. Recording `refused` without `reason_id` fails validation; with a reason it stores nurse, actual time, reason and becomes immutable (further writes to state/dose raise `UserError`).
5. A client with an active Warfarin order gets `interaction_severity='major'` on activating an Aspirin order (given a seeded/known interaction row) and activation is blocked until `action_acknowledge_interaction` (visible only to head nurse/doctor/manager) is pressed.
6. `action_hold` cancels future planned slots; `action_resume` regenerates them.
7. PRN orders generate no automatic slots; the PWA PRN endpoint creates an on-demand dose linked to the visit.
8. Nurse group can record administrations but cannot create/activate orders (ACL) — verified via UI and direct ORM.
9. Catchment rules: HCM nurse cannot read HN medication orders/administrations; owner sees all.
10. Nightly cron keeps a rolling 7-day slot horizon and auto-completes orders past end_date.

## 3.11 Integration touchpoints

- `health.medication`, `health.medication.safety.check_drug_interactions(list_of_names)`, `health.medication.interaction` (health_base).
- `health.fieldservice.order` (`medication_administration_ids`, write-hook re-link, `booking_timezone` for local slot times, `state` gating).
- `health.clinical.note.medications_prescribed` (free text) stays; eMAR is the structured sidecar — no migration in this phase.
- PWA `sync.py::_get_fso_changes` extension + new reasons store; PWA version bump.
- Future: `health_fhir_core` MedicationRequest/MedicationAdministration serializers; DAV crosswalk consumed by VN adapter.

---

# 4. `health_forms` — Configurable Clinical Forms / Assessments Engine

## 4.1 `__manifest__.py`

```python
{
    'name': 'Healthcare Clinical Forms',
    'version': '19.0.1.0.0',
    'category': 'Healthcare/Clinical',
    'summary': 'Configurable clinical forms & scored assessments rendered in backend (OWL) and PWA (Vue) from one JSON schema (FHIR Questionnaire/QuestionnaireResponse)',
    'author': 'VAFHS Development Team',
    'website': 'https://www.vafhs.com',
    'license': 'LGPL-3',
    'depends': ['health_base', 'health_fieldservice', 'health_vitals'],
    'data': [
        'security/health_forms_security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence.xml',
        'data/health_form_template_pain.xml',
        'data/health_form_template_barthel.xml',
        'data/health_form_template_mna.xml',
        'data/health_form_template_braden.xml',
        'data/health_form_template_amts.xml',
        'data/health_vitals_type_assessment_data.xml',
        'views/health_form_template_views.xml',
        'views/health_form_instance_views.xml',
        'views/health_fieldservice_order_views.xml',
        'views/health_forms_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'health_forms/static/src/components/form_renderer/form_renderer.js',
            'health_forms/static/src/components/form_renderer/form_renderer.xml',
            'health_forms/static/src/components/form_renderer/form_renderer.scss',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
```

Depends on `health_vitals` for coded-observation extraction.

## 4.2 The shared JSON schema (single source rendered by OWL and Vue)

`health.form.template.schema_json` (compiled, readonly) — exact shape:

```json
{
  "code": "BARTHEL",
  "version": 3,
  "title": "Barthel ADL Index",
  "title_vi": "Chỉ số Barthel ADL",
  "questions": [
    {
      "key": "feeding",
      "type": "selection",
      "label": "Feeding",
      "label_vi": "Ăn uống",
      "required": true,
      "options": [
        {"value": "unable", "label": "Unable", "label_vi": "Không thể", "score": 0},
        {"value": "needs_help", "label": "Needs help", "label_vi": "Cần trợ giúp", "score": 5},
        {"value": "independent", "label": "Independent", "label_vi": "Tự lập", "score": 10}
      ],
      "min": null, "max": null,
      "score_weight": 1.0,
      "loinc_code": null,
      "ucum_unit": null,
      "visible_if": null,
      "help": "", "help_vi": ""
    }
  ],
  "scoring": {
    "method": "sum",
    "bands": [
      {"min": 0,  "max": 40,  "label": "Severe dependence",  "label_vi": "Phụ thuộc nặng",  "color": "#B3261E"},
      {"min": 45, "max": 60,  "label": "Moderate dependence","label_vi": "Phụ thuộc vừa",   "color": "#B26A00"},
      {"min": 65, "max": 100, "label": "Independent/mild",   "label_vi": "Độc lập/nhẹ",     "color": "#1B6E20"}
    ],
    "score_loinc_code": null,
    "score_vitals_type_code": "barthel_total"
  }
}
```

Question `type` ∈ `number | selection | multiselect | text | boolean | date | photo | signature | computed_score`. Semantics:
- `number`: numeric input, `min`/`max` enforce; contributes `value * score_weight` when `score_weight > 0`.
- `selection`: single choice; contributes the chosen option's `score`.
- `multiselect`: answer = array of option values; contributes sum of chosen option scores.
- `boolean`: contributes `options` scores keyed `true`/`false` if provided, else 0.
- `text` / `date`: never scored.
- `photo` / `signature`: answer = `{"attachment_id": <int>}` after upload (base64 in the create payload → `ir.attachment`); never scored.
- `computed_score`: read-only display of the running total; never an input.
- `visible_if`: `{"key": "<other question key>", "operator": "=|!=|in|>=|<=", "value": ...}` — single-condition show/hide (renderers must implement; no nesting in v1).

`scoring.method` ∈ `sum` (sum of contributions) | `none`. `bands` map `total_score` → `score_label` (inclusive bounds; flat mono colors). `score_vitals_type_code` names the `health.vitals.type.code` used for observation extraction of the total.

## 4.3 Models

### 4.3.1 `health.form.template`

```
_name = 'health.form.template'
_description = 'Clinical Form Template'
_inherit = ['mail.thread', 'mail.activity.mixin']
_order = 'name, version desc'
_rec_name = 'display_name'
```

| field | type | purpose |
|---|---|---|
| `name` | Char, required, translate | FHIR `Questionnaire.title` |
| `name_vi` | Char | Vietnamese title |
| `code` | Char, required, index | Family code (`PAIN`, `BARTHEL`, `MNA_SF`, `BRADEN`, `AMTS`); FHIR `Questionnaire.name` |
| `version` | Integer, default 1, readonly, required | FHIR `Questionnaire.version`; unique with code |
| `state` | Selection `[('draft','Draft'),('published','Published'),('retired','Retired')]`, default `draft`, required, tracking | FHIR `Questionnaire.status` (published→active) |
| `category` | Selection `[('assessment','Assessment'),('screening','Screening'),('intake','Intake'),('outcome','Outcome Measure'),('other','Other')]`, default `assessment`, required | Grouping |
| `description` | Html, translate | FHIR `description` |
| `service_type_ids` | Many2many `health.service.type`, rel `health_form_template_service_type_rel` | Which services this form applies to (PWA filtering) |
| `question_ids` | One2many `health.form.question` `template_id` | Authoring rows |
| `scoring_method` | Selection `[('sum','Sum of scores'),('none','No scoring')]`, default `sum` | Compiles into `scoring.method` |
| `scoring_bands_json` | Json | `[{min,max,label,label_vi,color}]` |
| `score_vitals_type_id` | Many2one `health.vitals.type`, string 'Total Score Observation Type' | Extraction target for the total |
| `schema_json` | Json, compute stored, readonly (depends question_ids.*, scoring fields, name…) | The §4.2 document — the ONLY thing renderers read |
| `predecessor_id` | Many2one `health.form.template`, readonly | Previous version |
| `is_latest` | Boolean, compute stored: no other same-code template with higher version in state != retired | Picker filtering |
| `instance_count` | Integer compute | Smart button |
| `published_date` | Date, readonly | Set by `action_publish` |
| `active` | Boolean, default True | Archive |

SQL constraint: `('uniq_code_version', 'UNIQUE(code, version)', 'Version already exists for this form code.')`.

State machine: draft → published (`action_publish`; guard ≥1 question, unique keys — Python validated; sets `published_date`); published → retired (`action_retire`); published templates are **immutable** — `write()` blocks changes to `question_ids`/scoring fields when state == published (raise `UserError` "Create a new version"); `action_new_version` copies the template to a new draft with `version + 1`, `predecessor_id` set. Who: manager+, admin, owner (form authoring is a config activity); head_nurse may publish? No — manager+ only.

### 4.3.2 `health.form.question`

```
_name = 'health.form.question'
_description = 'Clinical Form Question'
_order = 'template_id, sequence, id'
```

| field | type | purpose |
|---|---|---|
| `template_id` | Many2one `health.form.template`, required, ondelete `cascade`, index | Parent |
| `sequence` | Integer, default 10 | Order |
| `key` | Char, required | Answer key (snake_case; Python constraint: unique per template, regex `^[a-z][a-z0-9_]*$`) |
| `question_type` | Selection `[('number','Number'),('selection','Selection'),('multiselect','Multi-select'),('text','Text'),('boolean','Yes/No'),('date','Date'),('photo','Photo'),('signature','Signature'),('computed_score','Computed Score')]`, required | Renderer widget |
| `label` | Char, required, translate | Question text |
| `label_vi` | Char | Vietnamese text |
| `required` | Boolean, default False | Validation |
| `options_json` | Json | `[{value,label,label_vi,score}]` for selection/multiselect/boolean |
| `min_value` / `max_value` | Float | number bounds |
| `score_weight` | Float, default 0.0 | number contribution multiplier |
| `loinc_code` | Char | Per-question coded extraction (numeric/selection-with-scores only) |
| `vitals_type_id` | Many2one `health.vitals.type` | Extraction target for this question (overrides loinc lookup) |
| `ucum_unit` | Char | Unit for extracted observation |
| `visible_if_json` | Json | §4.2 condition |
| `help` | Char, translate | Hint text |

### 4.3.3 `health.form.instance`

```
_name = 'health.form.instance'
_description = 'Clinical Form Instance (Response)'
_inherit = ['mail.thread']
_order = 'create_date desc'
_rec_name = 'display_name'
```

| field | type | purpose |
|---|---|---|
| `name` | Char, readonly, sequence `health.form.instance` prefix `FRM` | Reference |
| `display_name` | Char compute stored `f"{template.name} — {client.name} ({completed date})"` | Label |
| `template_id` | Many2one `health.form.template`, required, ondelete `restrict`, domain `[('state','=','published')]` | FHIR `questionnaire` |
| `template_code` | Char related `template_id.code` store=True | Search |
| `template_version` | Integer, readonly (copied at create) | Version pin |
| `schema_snapshot` | Json, readonly (copied `schema_json` at create) | Renders identically forever, even after template retirement |
| `client_id` | Many2one `res.partner`, required, domain is_patient, ondelete `restrict`, index, tracking | FHIR `subject` |
| `order_id` | Many2one `health.fieldservice.order`, ondelete `set null`, index | FHIR `encounter` |
| `performer_id` | Many2one `res.users`, default uid, readonly | FHIR `author` |
| `answers_json` | Json | `{key: value}`; photo/signature values = `{"attachment_id": id}` |
| `total_score` | Float, readonly | Computed on complete via `_compute_score()` (explicit method, not @depends — answers are Json) |
| `score_label` / `score_label_vi` | Char, readonly | Band labels |
| `state` | Selection `[('draft','Draft'),('completed','Completed'),('amended','Amended'),('cancelled','Cancelled')]`, default `draft`, required, tracking | FHIR `QuestionnaireResponse.status` (completed/amended verbatim, cancelled→stopped) |
| `completed_datetime` | Datetime, readonly | FHIR `authored` |
| `observation_ids` | One2many `health.observation` `form_instance_id` | Extracted coded observations |
| `attachment_ids` | Many2many `ir.attachment`, rel `health_form_instance_attachment_rel` | Photos/signatures |
| `catchment_province_id` | per §0.3 | Record rules |
| `company_id` | Many2one `res.company`, default current | Multi-company |

`health.observation` extension in this module: add `form_instance_id` Many2one `health.form.instance`, ondelete `set null`, index (coding-sidecar; nothing else changes).

State machine: draft → completed (`action_complete`; guards: all `required` visible questions answered, number bounds respected — validated against `schema_snapshot`; side effects: `_compute_score()`, `_extract_observations()`, `completed_datetime=now`); completed → amended (`write` of answers by head_nurse+ re-runs score + re-extracts — previous observations marked `entered_in_error`, new rows created); draft/completed → cancelled (`action_cancel`, head_nurse+). No unlink once completed (override `unlink()` as in §2.2.2). Nurses create + complete instances (point of care).

## 4.4 Business methods

```python
def _compute_score(self):
```
Walk `schema_snapshot.questions` against `answers_json` per §4.2 contribution rules, honoring `visible_if` (hidden questions contribute 0 and are exempt from `required`). Set `total_score`, then resolve band → `score_label`/`score_label_vi`.

```python
def _extract_observations(self):
```
(1) Per question with `vitals_type_id` or `loinc_code` and a numeric contribution (number value, or selected option score): create `health.observation` (client, `vitals_type_id` — resolved by id, else `health.vitals.type` lookup on `loinc_code`; skip with logged warning if unresolved), `value_quantity`, `effective_datetime=completed_datetime`, `performer_id`, `order_id`, `form_instance_id`, state `final`.
(2) Total: if `scoring.score_vitals_type_code` resolves to a `health.vitals.type` → one observation with `value_quantity=total_score`.
Threshold checks (§2.3) fire automatically via `health.observation.create`.

```python
@api.model
def get_templates_for_service(self, service_type_ids=None):
```
Published + `is_latest` templates filtered by `service_type_ids` overlap (empty m2m = applies to all). Returns schema list for PWA.

## 4.5 Renderers

- **Backend (OWL)**: component `health_forms.FormRenderer` registered as a form-view widget `health_form_renderer` bound to `schema_snapshot` + `answers_json` on the instance form; renders questions per type, evaluates `visible_if`, live total-score footer with band color chip (flat mono). Also used read-only when state != draft. Photo/signature in backend render as attachment preview (upload via standard many2many_binary into `attachment_ids`, storing `{"attachment_id"}` into answers).
- **PWA (Vue/Quasar, inside `health_pwa`)**: component `FormRunner.vue` consuming the identical schema JSON from the API/PouchDB; signature question uses the signature-pad canvas component (same one health_consent uses, §6.7); photo uses the existing PWA photo capture. Both renderers implement the §4.2 contract exactly — the schema is the contract, no renderer-specific fields.

## 4.6 Views & menus

- Template form: statusbar draft/published/retired + `action_publish`/`action_retire`/`action_new_version` buttons; sheet: name/name_vi/code/version/category/service_type_ids/score_vitals_type_id/scoring_method; page "Questions" inline editable list (sequence handle, key, question_type, label, label_vi, required, options_json (json widget), min/max, score_weight, loinc_code, vitals_type_id); page "Scoring Bands" (`scoring_bands_json` json widget); page "Preview" (readonly `health_form_renderer` on `schema_json` with empty answers); `<chatter/>`.
- Template list: name, code, version, category, state, is_latest, instance_count. Search: Published, Latest only, group by code/category.
- Instance form: header statusbar + `action_complete`/`action_cancel`; client/template/version/order/performer/completed_datetime/total_score/score_label; body = `health_form_renderer`; page "Extracted Observations" readonly list; `<chatter/>`.
- Instance list: name, template_code, client_id, order_id, total_score, score_label, state, completed_datetime. Graph view: measure `total_score`, axis `completed_datetime`, group by `template_code` (assessment trending). Search: My instances, by template code filters (Pain/Barthel/MNA/Braden/AMTS), group by client/template/state.
- FSO form inherit: page "Assessments" listing instances domain `[('order_id','=',id)]` + button "New Assessment" (context defaults client/order).
- Menus: `menu_health_forms` "Assessments & Forms" under `health_base.menu_healthcare_clinical` sequence 12 → children "Form Instances" (all users) and "Form Templates" (manager+; also mirrored under `health_base.menu_healthcare_lookups`).

## 4.7 Security

| model | receptionist | nurse | head_nurse | doctor | ops_manager | manager | admin | owner |
|---|---|---|---|---|---|---|---|---|
| health.form.template | 1000 | 1000 | 1000 | 1000 | 1000 | 1110 | 1110 | 1111 |
| health.form.question | 1000 | 1000 | 1000 | 1000 | 1000 | 1110 | 1110 | 1111 |
| health.form.instance | 1000 | 1110 | 1110 | 1110 | 1000 | 1110 | 1110 | 1111 |

Record rules (§0.3) on `health.form.instance` only (templates are global config).

## 4.8 PWA API (`controllers/api.py`, class `HealthFormsPWAController`)

| route | method | request | response `data` |
|---|---|---|---|
| `/health_pwa/api/forms/templates` | GET, param `service_type_id` optional | — | `{'templates': [ <full §4.2 schema> + {'id', 'category', 'service_type_ids'} ]}` (reference → PouchDB store `health_form_templates`, synced via new `_get_form_template_changes` in `sync.py`) |
| `/health_pwa/api/fso/<int:order_id>/forms` | GET | — | `{'applicable_templates': [{id, code, name, name_vi, category}], 'instances': [{id, template_code, template_version, state, total_score, score_label, completed_datetime, answers}]}` |
| `/health_pwa/api/fso/<int:order_id>/forms/submit` | POST | `{"template_id": 5, "answers": {"feeding": "needs_help", "pain_score": 7, "wound_photo": {"base64": "...", "filename": "w.jpg"}, "sig": {"base64": "..."}}}` | `{'instance_id', 'total_score', 'score_label', 'score_label_vi', 'observation_alerts': [...]}` — controller decodes base64 media into `ir.attachment`, rewrites answers to `{"attachment_id"}`, creates instance (client from `order.patient_id`), calls `action_complete()` |
| `/health_pwa/api/patients/<int:patient_id>/forms` | GET, params `template_code`, `limit` | — | `{'instances': [...]}` + `{'trend': [{t: completed_datetime, v: total_score}]}` when `template_code` given |

Offline: templates cached; a completed form queues the whole submit payload (photos as base64) with `client_mutation_id`; replay is idempotent (controller may receive an optional `client_uuid` and skip duplicates by searching a `client_uuid` Char field on the instance — add field `client_uuid` Char, readonly, index, unique-if-set Python constraint). Bump PWA version (3 places).

## 4.9 FHIR serialization notes

| Odoo | FHIR |
|---|---|
| `health.form.template` | `Questionnaire`: `name`=code, `title`, `version`, `status` (published→active, retired→retired, draft→draft), `item[]` from questions (`linkId`=key, `text`=label, `type`: number→decimal, selection→choice (+`answerOption` w/ `valueCoding` + ordinalValue extension = score), multiselect→choice `repeats=true`, boolean→boolean, date→date, text→text, photo/signature→attachment, computed_score→display), `item.enableWhen` from visible_if, `code` from loinc_code |
| `health.form.instance` | `QuestionnaireResponse`: `questionnaire`=Questionnaire canonical `{code}|{version}`, `status` (completed/amended verbatim, draft→in-progress, cancelled→stopped), `subject`, `encounter`, `author`, `authored`=completed_datetime, `item[].answer` from answers_json; attachments as `valueAttachment` |
| extracted rows | ordinary `Observation`s (§2.8), `derivedFrom` → QuestionnaireResponse |

## 4.10 Data seeds

`data/health_vitals_type_assessment_data.xml` (`noupdate="1"`) — assessment-score observation types (extends the §2.9 catalog; LOINC where confident, local codes elsewhere — **codes marked `local:` use system `health19-assessments`, bind LOINC at terminology-pack time**):

| code | loinc_code | name |
|---|---|---|
| `barthel_total` | `local:barthel-total` | Barthel ADL Index total score |
| `mna_sf_total` | `local:mna-sf-total` | Mini Nutritional Assessment (SF) score |
| `braden_total` | `38228-3` | Braden scale total score |
| `amts_total` | `local:amts-total` | AMTS score |

(Pain uses `vitals_type_pain_score` 72514-3 from health_vitals. Morse 59461-4 stays with `health.fall.risk`.)

Five templates seeded **published, version 1** (`noupdate="1"`; each file creates the template + question rows). Content spec:

1. **PAIN — Pain Scale (Thang điểm đau)**, category assessment. Questions: `pain_score` number 0–10 required, score_weight 1, vitals_type → pain (72514-3); `pain_location` text; `pain_character` selection (dull/sharp/burning/throbbing/other, no scores). Bands: 0–3 Mild/Đau nhẹ, 4–6 Moderate/Đau vừa, 7–10 Severe/Đau nặng. `score_vitals_type_code` = pain type code (total == the one question).
2. **BARTHEL — Barthel ADL Index (Chỉ số Barthel)**. 10 selection questions with standard scores: feeding (0/5/10), bathing (0/5), grooming (0/5), dressing (0/5/10), bowels (0/5/10), bladder (0/5/10), toilet_use (0/5/10), transfers (0/5/10/15), mobility (0/5/10/15), stairs (0/5/10). All required. Bands: 0–40 Severe dependence, 45–60 Moderate, 65–100 Independent/mild. Total → `barthel_total`.
3. **MNA_SF — Mini Nutritional Assessment SF (Đánh giá dinh dưỡng)**. 6 selections: food_intake_decline (0/1/2), weight_loss (0/1/2/3), mobility (0/1/2), acute_stress (0/2), neuropsych (0/1/2), bmi_band (0/1/2/3). Bands: 0–7 Malnourished, 8–11 At risk, 12–14 Normal. Total → `mna_sf_total`.
4. **BRADEN — Braden Pressure Injury Risk (Nguy cơ loét tì đè)**. 6 selections: sensory_perception (1–4), moisture (1–4), activity (1–4), mobility (1–4), nutrition (1–4), friction_shear (1–3). Bands: 6–12 High risk, 13–14 Moderate, 15–18 Mild, 19–23 No risk. Total → `braden_total` (38228-3).
5. **AMTS — Abbreviated Mental Test Score (Đánh giá nhận thức)**. 10 boolean questions (correct=1/incorrect=0 via boolean option scores): age, time, address_recall_registered (registration step, score 0), year, place, person_recognition, dob, ww_dates→`historic_date` (use VN-appropriate wording "Năm thống nhất đất nước 1975"), head_of_state, count_backwards, address_recall. Bands: 0–6 Cognitive impairment likely, 7–8 Borderline, 9–10 Normal. Total → `amts_total`.

Exact option labels vi/en for all five ship in the seed files; implementer copies validated clinical wording from the cited instruments (structure above is normative; use standard published item scores exactly as listed).

**Morse migration note:** `health.fall.risk` (Morse) remains in `health_base` untouched. Migration path (NOT in this phase): create template code `MORSE` v1 mirroring the six items, backfill instances from `health.fall.risk` rows, then deprecate the bespoke model. Document only.

## 4.11 Acceptance criteria

1. Install seeds 5 published templates + 4 assessment observation types; `schema_json` of each validates against §4.2 (all keys snake_case, options carry scores).
2. A published template rejects edits to questions (`UserError`) and `action_new_version` creates draft v2 with `predecessor_id` set; instances keep rendering from their own `schema_snapshot` after the template is retired.
3. Completing a Barthel instance with all-independent answers yields `total_score == 100` and `score_label == 'Independent/mild'`; an unanswered required question blocks `action_complete`.
4. Completion creates a `barthel_total` `health.observation` linked via `form_instance_id`, and pain-form completion creates a 72514-3 observation that fires a client pain threshold if configured.
5. Amending a completed instance (head nurse) re-scores and marks the previous extracted observations `entered_in_error` while creating fresh ones.
6. `POST /health_pwa/api/fso/<id>/forms/submit` with a base64 photo creates an attachment, stores `{"attachment_id"}` in answers, and returns the score in the standard envelope; replaying the same `client_uuid` does not duplicate.
7. `visible_if` questions hidden by their condition are neither required nor scored (unit test with a conditional question).
8. Templates filtered by `service_type_ids` only appear for matching FSOs in `/fso/<id>/forms`; templates with empty service types appear for all.
9. Backend OWL preview and instance form render every question type including signature (readonly image) without console errors.
10. Catchment rules on instances hold; nurse can create/complete but cannot cancel a completed instance (head nurse can amend/cancel).

## 4.12 Integration touchpoints

- `health.observation` (+ new `form_instance_id` field), `health.vitals.type` (extraction, trend graphs) — §2.
- `health.fieldservice.order` ("Assessments" page, `order_id` link), `health.service.type` (applicability).
- `health.fall.risk` — untouched; documented migration path only.
- PWA: new PouchDB store `health_form_templates`, `FormRunner.vue`, submit outbox; `sync.py` `_get_form_template_changes`; version bump.
- Future `health_fhir_core`: Questionnaire/QuestionnaireResponse serializers (§4.9); `health_careplan` reviews may attach assessments (no code dependency).

---

# 5. `health_incident` — Incident / Adverse Event Management

## 5.1 `__manifest__.py`

```python
{
    'name': 'Healthcare Incident Management',
    'version': '19.0.1.0.0',
    'category': 'Healthcare/Clinical',
    'summary': 'Adverse-event capture, investigation workflow, corrective actions and incident register (FHIR AdverseEvent/Flag)',
    'author': 'VAFHS Development Team',
    'website': 'https://www.vafhs.com',
    'license': 'LGPL-3',
    'depends': ['health_base', 'health_fieldservice'],
    'data': [
        'security/health_incident_security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence.xml',
        'views/health_incident_views.xml',
        'views/health_incident_action_views.xml',
        'views/health_incident_menus.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
```

## 5.2 Models

### 5.2.1 `health.incident`

```
_name = 'health.incident'
_description = 'Incident / Adverse Event'
_inherit = ['mail.thread', 'mail.activity.mixin']
_order = 'incident_datetime desc'
_rec_name = 'display_name'
```

| field | type | purpose |
|---|---|---|
| `name` | Char, readonly, sequence `health.incident` prefix `INC` | Reference |
| `display_name` | Char compute stored `f"{name} — {type label} ({client or 'no client'})"` | Label |
| `incident_type` | Selection `[('fall','Fall'),('medication_error','Medication Error'),('injury','Injury'),('behaviour','Behaviour'),('property','Property Damage/Loss'),('near_miss','Near Miss'),('other','Other')]`, required, tracking, index | Taxonomy; FHIR `AdverseEvent.event` (local CodeSystem `health19-incident-types`) |
| `severity` | Selection `[('1','1 — Negligible'),('2','2 — Minor'),('3','3 — Moderate'),('4','4 — Major'),('5','5 — Catastrophic')]`, required, default `'2'`, tracking, index | FHIR `AdverseEvent.severity` (1-2→mild, 3→moderate, 4-5→severe) |
| `client_id` | Many2one `res.partner`, domain is_patient, ondelete `restrict`, index, tracking (optional — staff-only incidents allowed) | FHIR `subject` |
| `order_id` | Many2one `health.fieldservice.order`, ondelete `set null`, index | The visit; FHIR `encounter` |
| `facility_id` | Many2one `health.facility`, tracking; default: `order_id.facility_id` else `client_id.primary_facility_id` (onchange) | Register slicing |
| `catchment_province_id` | per §0.3, with fallback: if no client, take `facility_id.catchment_province_id` (extend compute depends accordingly) | Record rules |
| `location` | Char | Where it happened; FHIR `location.display` |
| `incident_datetime` | Datetime, required, default now, tracking | FHIR `date` |
| `reporter_id` | Many2one `res.users`, default uid, readonly | FHIR `recorder` |
| `reported_datetime` | Datetime, default now, readonly | FHIR `detected`/`recordedDate` |
| `description` | Text, required | Narrative |
| `immediate_actions` | Text | First response taken; FHIR `mitigation` narrative |
| `witnesses` | Char | Free-text witness names |
| `state` | Selection `[('reported','Reported'),('under_review','Under Review'),('investigation','Investigation'),('actions_assigned','Actions Assigned'),('closed','Closed')]`, default `reported`, required, tracking, index | Workflow |
| `investigator_id` | Many2one `res.users`, tracking | Investigation owner |
| `investigation_notes` | Html | Findings |
| `root_cause` | Text | RCA summary |
| `contributing_factors` | Text | Contributing factors |
| `outcome` | Selection `[('no_harm','No Harm'),('minor_harm','Minor Harm'),('moderate_harm','Moderate Harm'),('severe_harm','Severe Harm'),('death','Death')]`, tracking | FHIR `AdverseEvent.outcome` |
| `notifiable` | Boolean, default False, tracking, index | Regulatory-notifiable flag |
| `notified_authority` | Char | Which authority (Sở Y tế / MOH / other) |
| `notified_date` | Date | When notified |
| `action_ids` | One2many `health.incident.action` `incident_id` | Corrective actions |
| `action_count` / `open_action_count` | Integer compute | Guards + smart button |
| `fall_risk_reassessment_triggered` | Boolean, readonly | §5.4 hook fired |
| `closed_date` | Datetime, readonly | Set on close |
| `closed_by_id` | Many2one `res.users`, readonly | Audit |
| `attachment_ids` | Many2many `ir.attachment`, rel `health_incident_attachment_rel` | Photos/evidence |
| `company_id` | Many2one `res.company`, default current | Multi-company |
| `active` | Boolean, default True | Archive |

No hard constraint ties `notifiable` to severity/type (regulator definitions differ). Onchange only: auto-set `notifiable=True` when severity becomes '4' or '5'.

### 5.2.2 `health.incident.action` (corrective action)

```
_name = 'health.incident.action'
_description = 'Incident Corrective Action'
_inherit = ['mail.thread', 'mail.activity.mixin']
_order = 'due_date, id'
```

| field | type | purpose |
|---|---|---|
| `incident_id` | Many2one `health.incident`, required, ondelete `cascade`, index | Parent |
| `name` | Char, required | Action summary |
| `description` | Text | Detail |
| `assignee_id` | Many2one `res.users`, required, tracking | Owner (gets an `activity_schedule` todo on create with `date_deadline=due_date`) |
| `due_date` | Date, required, tracking | Deadline |
| `state` | Selection `[('open','Open'),('in_progress','In Progress'),('done','Done'),('cancelled','Cancelled')]`, default `open`, required, tracking | Lifecycle |
| `completed_date` | Date, readonly | Set by `action_done` |
| `effectiveness_review` | Text | Post-completion review |
| `catchment_province_id` | related `incident_id.catchment_province_id`, store=True | Record rules |

Buttons: `action_start` (open→in_progress), `action_done` (→done, sets completed_date, marks the mail activity done), `action_cancel_action` (→cancelled).

## 5.3 State machine — `health.incident`

| transition | button | guard | groups |
|---|---|---|---|
| reported → under_review | `action_start_review` | — | head_nurse, ops_manager, manager+ |
| under_review → investigation | `action_start_investigation` | `investigator_id` set | head_nurse, ops_manager, manager+ |
| investigation → actions_assigned | `action_assign_actions` | ≥1 action in state open/in_progress; `root_cause` set | investigator or manager+ |
| actions_assigned → closed | `action_close` | all actions state in (done, cancelled); if `notifiable`: `notified_authority` + `notified_date` set | manager, admin, owner |
| reported/under_review → closed | `action_close_minor` | severity in ('1','2') | head_nurse, manager+ (fast-close of trivial events; `description` already required at create) |
| closed → under_review | `action_reopen` | — | manager, admin, owner |

Side effects on create (`create()` override): if `severity in ('4','5')` → `activity_schedule` todo on the facility manager's user only ("Severe incident reported: {name}"), with the same missing-manager fallback/logging pattern as §2.3. If `incident_type == 'fall'` and `client_id` set → §5.4 hook.

## 5.4 Business methods

```python
def _trigger_fall_risk_reassessment(self):
```
Called from `create()`/`write()` when type becomes `fall` with a client: if not already triggered — `activity_schedule` todo summary "Reassess fall risk (Morse): {client}" on `client_id.primary_facility_id.head_nurse_id` (fallback `facility_manager_id`, then skip+log; both fields exist on `health.facility` per `health_base` rule domains), note links the incident and the client's latest `health.fall.risk` date; set `fall_risk_reassessment_triggered=True`. No new `health.fall.risk` record is auto-created (assessments need a human).

```python
@api.model
def get_register(self, date_from, date_to, domain_extra=None):
```
Returns aggregates for the register dashboards: counts by type × severity × facility, notifiable count, open-actions overdue count. (Used by views/BI later; keep as plain read_group wrapper.)

## 5.5 Views & menus

- Incident form: statusbar (reported → under_review → investigation → actions_assigned → closed) with buttons per §5.3; alert ribbon when `notifiable` (widget `web_ribbon` "NOTIFIABLE"); sheet groups: type/severity/datetime/location | client/order/facility/reporter; Description + Immediate actions; notebook: "Investigation" (investigator, notes, root_cause, contributing_factors, outcome), "Corrective Actions" (inline list: name, assignee_id, due_date, state, completed_date + open-form), "Notification" (notifiable, notified_authority, notified_date), "Evidence" (attachments); `<chatter/>`.
- Incident list (the **register**): name, incident_datetime, incident_type, severity (badge, decoration-danger ≥4), client_id, facility_id, notifiable, state, open_action_count. `default_order="incident_datetime desc"`.
- Kanban grouped by state; graph (count by type / month); pivot (type × severity × facility).
- Search: filters Notifiable, Severe (severity in 4,5), Open (state != closed), Falls, Medication Errors, This Month, Overdue Actions (`action_ids.due_date < today` & state != done); group by type/severity/facility/state/month.
- Actions list view (own menu for "my corrective actions"): name, incident_id, assignee_id, due_date, state; filter My Actions (`assignee_id = uid`), Overdue.
- Menus: `menu_health_incident_root` "Incidents" under `health_base.menu_healthcare_root` sequence 28; children: "Incident Register" (incident action, all healthcare users), "Corrective Actions" (nurse+), "Analysis" (graph/pivot action, manager+).

## 5.6 Security

| model | receptionist | nurse | head_nurse | doctor | ops_manager | finance | manager | admin | owner |
|---|---|---|---|---|---|---|---|---|---|
| health.incident | 1010 | 1010 | 1110 | 1110 | 1110 | 0000 | 1110 | 1110 | 1111 |
| health.incident.action | 1000 | 1100 | 1110 | 1110 | 1110 | 0000 | 1110 | 1110 | 1111 |

(Everyone clinical can **report** (create) incidents; only head_nurse+ edit them. Nurses can write on actions assigned to them — add a record rule: `rule_incident_action_assignee_write`: domain `[('assignee_id','=',user.id)]`, perm_write only, group nurse.) Record rules (§0.3) on both models + owner-all. Additional rule: reporter can always read own reports — `rule_incident_own_reports`: `['|', ('reporter_id','=',user.id), '&', ('catchment_province_id','=',user.catchment_province_id.id), ('catchment_province_id','!=',False)]` replaces the plain catchment rule for the nurse/receptionist groups (staff-only incidents may have no catchment).

## 5.7 PWA API (`controllers/api.py`, class `HealthIncidentPWAController`)

| route | method | request | response `data` |
|---|---|---|---|
| `/health_pwa/api/incidents` | POST | `{"incident_type": "fall", "severity": "3", "client_id": 861, "order_id": 1234, "incident_datetime": "...", "location": "", "description": "...", "immediate_actions": "...", "witnesses": "", "photos": [{"base64": "...", "filename": "..."}]}` | `{'incident_id', 'name', 'message'}` (photos → attachments) |
| `/health_pwa/api/incidents/mine` | GET, params `limit`/`offset` | — | `{'incidents': [{id, name, incident_type, severity, client_name, state, incident_datetime, description}], 'total_count', 'has_more'}` (domain `reporter_id = uid`) |
| `/health_pwa/api/incidents/types` | GET | — | `{'types': [...selection labels vi/en...], 'severities': [...]}` (labels via `_selection_labels` helper pattern from `api.py`) |

PWA frontend: "Report Incident" action on the visit screen and client screen (type picker, severity slider 1–5, photo capture, offline-queued with `client_mutation_id`). No PouchDB read store needed (write-mostly); queue replays POST `/incidents`. Bump PWA version (3 places).

## 5.8 FHIR serialization notes

| Odoo | FHIR |
|---|---|
| `health.incident` | `AdverseEvent`: `actuality` = `actual` (`near_miss` → `potential`); `event` = local coding `health19-incident-types`; `subject`=client (staff-only → subject = Practitioner ref, allowed in R4 via RelatedPerson? — serialize staff-only incidents with `subject` omitted-profile note, flagged for profile decision); `date`=incident_datetime; `detected`/`recordedDate`=reported_datetime; `location.display`; `severity` map 1-2 mild / 3 moderate / 4-5 severe; `outcome` map (`no_harm`→resolved, `death`→fatal, others→ongoing/resolved-with-sequelae per table); `recorder`=reporter; `contributor`=investigator; `mitigation.description`=immediate_actions; `encounter`=order_id |
| standing alert | `Flag`: emit for clients with an open incident of type fall or severity ≥4 — `status=active` while incident open, `code`=incident type, `period.start`=incident_datetime. (Serializer derives Flags; no separate Odoo model.) |
| `health.incident.action` | Local extension / `Task` (owner=assignee, restriction.period.end=due_date, status open→requested, in_progress→in-progress, done→completed, cancelled→cancelled) |

## 5.9 Data seeds

- `data/ir_sequence.xml`: `health.incident` prefix `INC`, padding 5. No other seeds (types are selections, not lookup rows, to keep the taxonomy stable for FHIR coding).

## 5.10 Acceptance criteria

1. A nurse can create an incident from backend and PWA; after creation she can read but not modify it (ACL), while head nurse can.
2. Creating a severity-5 incident schedules an activity for the facility manager's user automatically.
3. A `fall` incident with a client sets `fall_risk_reassessment_triggered` and schedules a "Reassess fall risk" activity for the facility head nurse.
4. `action_start_investigation` without an investigator raises `UserError`; `action_assign_actions` requires root cause + ≥1 open action; `action_close` is blocked while any action is open or (if notifiable) authority/date are empty.
5. `action_close_minor` fast-closes only severity 1–2 incidents.
6. Corrective-action creation schedules a deadline activity for the assignee; `action_done` completes it and stamps `completed_date`; an assignee nurse can update her own action but not others' (record rule).
7. Register list/graph/pivot filter by notifiable, type, severity, month; pivot shows type × severity.
8. POST `/health_pwa/api/incidents` with 2 base64 photos creates the incident + 2 attachments and returns the standard envelope; replayed offline mutation does not duplicate (client_mutation_id honored).
9. Catchment rules hold; reporter always sees own incidents even without a client (staff-only incident).
10. Reopening a closed incident is restricted to manager+.

## 5.11 Integration touchpoints

- `health.fall.risk` (reassessment activity references latest Morse), `health.facility.head_nurse_id` / `facility_manager_id`.
- `health.fieldservice.order` (`order_id` context link), `res.partner` clients.
- `health_emar`: medication_error incidents SHOULD be creatable from a refused/not-given administration later (no code now; note only).
- PWA report flow + offline queue; version bump.
- Future `health_fhir_core`: AdverseEvent + derived Flag serializers; `biz_bi` incident-register gold dataset.

---

# 6. `health_consent` — Consent Management

## 6.1 `__manifest__.py`

```python
{
    'name': 'Healthcare Consent Management',
    'version': '19.0.1.0.0',
    'category': 'Healthcare/Clinical',
    'summary': 'Consent capture (verbal/written/digital signature), expiry lifecycle and check_consent() service API (FHIR Consent)',
    'author': 'VAFHS Development Team',
    'website': 'https://www.vafhs.com',
    'license': 'LGPL-3',
    'depends': ['health_base', 'health_crm'],
    'data': [
        'security/health_consent_security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence.xml',
        'data/ir_cron.xml',
        'views/health_consent_views.xml',
        'views/res_partner_views.xml',
        'views/health_consent_menus.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
```

`health_crm` dependency provides `health.client.relation` for kinship-aware `granted_by`.

## 6.2 Models

### 6.2.1 `health.consent`

```
_name = 'health.consent'
_description = 'Client Consent'
_inherit = ['mail.thread', 'mail.activity.mixin']
_order = 'create_date desc'
_rec_name = 'display_name'
```

| field | type | purpose |
|---|---|---|
| `name` | Char, readonly, sequence `health.consent` prefix `CNS` | Reference |
| `display_name` | Char compute stored `f"{client.name} — {consent_type label}"` | Label |
| `client_id` | Many2one `res.partner`, required, domain is_patient, ondelete `restrict`, index, tracking | FHIR `patient` |
| `consent_type` | Selection `[('service','Service Delivery'),('data_sharing','Data Sharing'),('photography','Photography/Media'),('emergency_treatment','Emergency Treatment'),('marketing','Marketing Communications')]`, required, tracking, index | FHIR `Consent.scope`+`category` (local CodeSystem `health19-consent-types`) |
| `scope_note` | Char, string 'Scope / Limitations' | Free-text narrowing ("photos for clinical record only, no social media") |
| `self_granted` | Boolean, default True, string 'Granted by Client' | Client consented personally |
| `granted_by_relation_id` | Many2one `health.client.relation`, domain `[('client_id','=',client_id)]`, required when not self_granted (Python constraint); onchange filters | Kinship grantor; FHIR `performer` + relationship |
| `granted_by_partner_id` | Many2one related `granted_by_relation_id.representative_id`, store=True, readonly | The person |
| `granted_by_role` | Selection related `granted_by_relation_id.role`, store=True, readonly | caregiver/payer/…/legal_guardian |
| `method` | Selection `[('verbal','Verbal'),('written','Written (paper)'),('digital_signature','Digital Signature')]`, required, tracking | Evidence class |
| `signature` | Binary (image), attachment=True | Digital signature PNG (required for `digital_signature` — Python constraint on grant) |
| `evidence_attachment_ids` | Many2many `ir.attachment`, rel `health_consent_attachment_rel` | Scanned form / photo (required for `written` on grant) |
| `verbal_witness_id` | Many2one `res.users` | Staff who heard verbal consent (default uid when method verbal) |
| `effective_date` | Date, required, default today, tracking | FHIR `provision.period.start` |
| `expiry_date` | Date, tracking | FHIR `provision.period.end` (empty = indefinite) |
| `state` | Selection `[('draft','Draft'),('active','Active'),('withdrawn','Withdrawn'),('expired','Expired')]`, default `draft`, required, tracking, index | FHIR `Consent.status`: active→active, withdrawn→inactive (+ provision), expired→inactive, draft→draft |
| `withdrawal_date` | Date, readonly | Audit |
| `withdrawal_reason` | Char | Required by `action_withdraw` |
| `withdrawn_by_id` | Many2one `res.users`, readonly | Audit |
| `notes` | Text | Free notes |
| `catchment_province_id` | per §0.3 | Record rules |
| `company_id` | Many2one `res.company`, default current | Multi-company |
| `active` | Boolean, default True | Archive |

SQL constraint: `('expiry_check', "CHECK (expiry_date IS NULL OR expiry_date >= effective_date)", 'Expiry must be after effective date.')`.
Python constraint `_check_one_active`: at most one `state='active'` consent per (`client_id`, `consent_type`) — granting a new one requires withdrawing/expiring the old (the PWA/backend "renew" flow: `action_grant` on the new record auto-withdraws the previous active one with reason 'Superseded' — implement this supersede behavior inside `action_grant`, logged in both chatters).

### 6.2.2 `res.partner` extension

| field | type | purpose |
|---|---|---|
| `consent_ids` | One2many `health.consent` `client_id` | Client form page |
| `consent_count` | Integer compute | Smart button |
| `consent_summary` | Char compute (non-stored): e.g. `"service ✓, data_sharing ✗, photography ✓"` — plain text labels, comma list of active types | Quick glance + PWA |

## 6.3 State machine

| transition | trigger | guard | groups |
|---|---|---|---|
| draft → active | `action_grant` | method-specific evidence present (verbal → `verbal_witness_id`; written → ≥1 evidence attachment; digital_signature → `signature`); grantor valid (`self_granted` or relation set); supersedes previous active same-type consent | receptionist, nurse+, manager+ (capture is a front-line task) |
| active → withdrawn | `action_withdraw` | `withdrawal_reason` provided (wizard-free: make field required via context/UserError check); sets withdrawal_date/withdrawn_by | nurse+, manager+ (and the operations desk: receptionist) |
| active → expired | `_cron_expire_consents` (daily) | `expiry_date < today` | system cron |
| draft → cancelled? | not modeled — draft records may be deleted (unlink allowed only in draft; active/withdrawn/expired are immutable audit records — override `unlink()` accordingly; `write()` locks evidence fields after grant) | — |

## 6.4 Business methods — the service API

```python
@api.model
def check_consent(self, partner, consent_type, at_date=None):
    """Return True iff `partner` (res.partner record or id) has an ACTIVE consent
    of `consent_type` covering `at_date` (default today).
    Cheap: single search on (client_id, consent_type, state='active') +
    date-window check. Callers MUST treat False as deny-by-default."""
```

```python
@api.model
def get_consent(self, partner, consent_type):
    """Return the active consent record (or empty recordset) for display/logging."""
```

```python
@api.model
def check_consents(self, partner, consent_types):
    """Batch variant → dict {consent_type: bool} in one search. Used by the FSO/PWA payloads."""
```

These are the cross-cutting enforcement points (interop §6.6). In this phase the module **provides** the API and wires two soft touchpoints (§6.8); the FHIR facade / Zalo / AI-gateway enforcement arrives with those modules.

```python
@api.model
def _cron_expire_consents(self):    # daily 01:00
```
(1) `active` + `expiry_date < today` → `state='expired'` + chatter note. (2) Renewal warning: `active` + `expiry_date == today + 14 days` → `activity_schedule` todo on `client_id.primary_facility_id.facility_manager_id.user_id` "Consent expiring: {client} — {type}".

## 6.5 Views & menus

- Consent form: statusbar draft/active/withdrawn/expired + `action_grant`/`action_withdraw`; sheet: client/consent_type/scope_note | self_granted/granted_by_relation_id (invisible when self_granted, with role+partner readonly display)/method; evidence group: signature (widget `image`, visible when digital), attachments (visible when written), verbal_witness_id (visible when verbal); dates: effective/expiry/withdrawal(+reason, visible when withdrawn); `<chatter/>`.
- List: name, client_id, consent_type, method, granted_by display, effective_date, expiry_date, state (badge). Search: Active, Expiring ≤30d, Withdrawn, by type filters, group by client/type/state.
- Kanban optional-skip. 
- Client form inherit: smart button "Consents" + page "Consents" with `consent_ids` readonly inline list and per-type status chips from `consent_summary`.
- Menus: `menu_health_consent` "Consents" under `health_base.menu_healthcare_patients` sequence 30 → consent list action; "Expiring Consents" filter-action child (manager+).

## 6.6 Security

| model | receptionist | nurse | head_nurse | doctor | ops_manager | finance | manager | admin | owner |
|---|---|---|---|---|---|---|---|---|---|
| health.consent | 1110 | 1110 | 1110 | 1110 | 1110 | 1000 | 1110 | 1110 | 1111 |

(No unlink for anyone below owner; draft-only unlink enforced in Python.) Record rules (§0.3 catchment + owner) on `health.consent`.

## 6.7 PWA API (`controllers/api.py`, class `HealthConsentPWAController`)

| route | method | request | response `data` |
|---|---|---|---|
| `/health_pwa/api/patients/<int:patient_id>/consents` | GET | — | `{'consents': [{id, name, consent_type, state, method, effective_date, expiry_date, granted_by: {name, role} or 'self', scope_note}], 'status': {'service': true, 'data_sharing': false, 'photography': true, 'emergency_treatment': false, 'marketing': false}, 'relations': [{id, representative_name, role, relationship_type}]}` (`status` via `check_consents`; `relations` feed the grantor picker) |
| `/health_pwa/api/patients/<int:patient_id>/consents` | POST | `{"consent_type": "photography", "method": "digital_signature", "self_granted": false, "granted_by_relation_id": 12, "signature_base64": "iVBOR...", "scope_note": "", "effective_date": "2026-07-06", "expiry_date": null, "notes": ""}` | `{'consent_id', 'name', 'state', 'message'}` — decodes signature into `signature`, creates draft, immediately calls `action_grant()` (supersede semantics apply) |
| `/health_pwa/api/consents/<int:consent_id>/withdraw` | POST | `{"reason": "..."}` | `{'consent_id', 'state'}` |
| `/health_pwa/api/consents/types` | GET | — | `{'types': [{value, label, label_vi}], 'methods': [...]}` (selection labels) |

PWA frontend (in `health_pwa`): **signature-pad capture flow** — reusable Vue component `SignaturePad.vue` (canvas, touch, clear/undo, exports PNG base64; the same component is consumed by `health_forms` signature questions, so build it once in `health_pwa/static/src/js/components/`). Consent capture sheet reachable from the client screen and from visit start (if `status.service` is false, PWA shows a non-blocking "Service consent missing" banner with a capture CTA). Consent `status` per client rides inside the `health_patients` PouchDB docs (extend `sync.py::_get_patient_changes` with `consents: {...}` guarded by `hasattr`/model-in-env check). Offline capture queues the POST with `client_mutation_id`. Bump PWA version (3 places).

## 6.8 Soft enforcement touchpoints shipped now

1. **Photography**: `health_consent` does NOT patch the existing `/health_pwa/api/fso/<id>/upload_image` (owned by health_pwa). Instead the PWA client checks `status.photography` before opening the camera for clinical photos and shows the capture CTA. (Server-side hard enforcement lands with the api-gateway phase; document in code comment.)
2. **Marketing**: provide `res.partner.can_send_marketing()` helper → `check_consent(self, 'marketing')`, for `health_zalo`/ZNS flows to adopt (no dependency from here; health_zalo adopts it in its own change).

## 6.9 FHIR serialization notes

| Odoo | FHIR `Consent` |
|---|---|
| `state` | `status`: active→active, draft→draft, withdrawn/expired→inactive |
| `consent_type` | `scope` (service/emergency_treatment→treatment, data_sharing→patient-privacy, photography/marketing→patient-privacy w/ category) + `category` local coding `health19-consent-types` |
| `client_id` | `patient` |
| `granted_by_partner_id` (+role) | `performer` → RelatedPerson; `self_granted` → performer = Patient |
| `method` + `signature`/attachments | `sourceAttachment` (signature PNG or scanned doc); verbal → `sourceReference` omitted + `policyRule.text='verbal'` |
| `effective_date`/`expiry_date` | `provision.period` |
| withdrawal | `status=inactive` + `provision.type='deny'` from withdrawal_date; `Provenance` note (phase 3) |
| `scope_note` | `provision` narrative |

## 6.10 Data seeds

- `data/ir_sequence.xml`: `health.consent` prefix `CNS`, padding 5.
- `data/ir_cron.xml`: daily expiry cron (§6.4).
- No consent-type lookup seeds (types are a fixed Selection for FHIR-stable coding).

## 6.11 Acceptance criteria

1. Granting a `digital_signature` consent without a signature raises `UserError`; with a signature PNG it activates.
2. Granting a new `photography` consent auto-withdraws the previous active one with reason "Superseded", visible in both chatters.
3. `check_consent(client, 'marketing')` returns False for a client with no record, an expired record, and a withdrawn record; True only within an active record's date window.
4. The daily cron expires consents past `expiry_date` and creates a renewal activity 14 days ahead of expiry.
5. `granted_by_relation_id` only offers `health.client.relation` rows of that client; a non-self grant without a relation is blocked.
6. POST consent from the PWA with a base64 signature creates an active consent in one round trip and the standard envelope; the client doc's `consents.status` flips on next sync.
7. Withdraw requires a reason; withdrawn consents lock their evidence fields (writes raise `UserError`).
8. Active/withdrawn/expired consents cannot be unlinked by any group below owner (draft can).
9. Catchment record rules hold on consents.
10. `res.partner.can_send_marketing()` reflects consent state (unit test).

## 6.12 Integration touchpoints

- `health.client.relation` (health_crm) — kinship grantor, roles caregiver/payer/legal_guardian etc.
- `res.partner` clients (`primary_facility_id` for renewal activities).
- Consumers of `check_consent()` (adopt in their own modules, no dependency from here): `health_zalo` (marketing), future `health_fhir_core` facade (data_sharing deny-by-default), future family portal (data_sharing_family — add as a new selection value then), PWA photo flow (photography, client-side now).
- PWA: `SignaturePad.vue` shared component (also used by `health_forms`), `_get_patient_changes` payload extension, version bump.

---

# 7. Cross-module notes for the implementer

1. **Install order / dependency graph**: `health_vitals` → (`health_careplan`, `health_forms`); `health_emar`, `health_incident` independent (both on health_base+health_fieldservice); `health_consent` on health_base+health_crm. No module depends on `health_pwa` or any FHIR module; `health_pwa` gains optional integrations guarded with `hasattr`/`'model' in self.env` checks so it installs with any subset.
2. **One `health_pwa` release** should batch all frontend changes (vitals sheet, med checklist, careplan tasks, FormRunner, incident report, consent/signature pad) — remember the **3-place version bump in `pwa_templates.xml`** and the new PouchDB stores: `health_vitals_types`, `health_form_templates`, `health_emar_reasons`; embedded payload extensions to `health_orders` (careplan tasks, med slots) and `health_patients` (consent status).
3. **Offline discipline** (interop §6.7): clinical writes (observations, administrations, form instances, incidents, consents) are **append-only** — the PWA never edits synced clinical rows, only queues creations/state-recordings with `client_mutation_id`/`client_uuid` idempotency keys; servers no-op on replay.
4. **Timezones**: all Datetime fields stored UTC (Odoo standard); anything shown/scheduled in local wall-clock uses the FSO `booking_timezone` / facility / catchment timezone chain, default `Asia/Ho_Chi_Minh` (pattern in `health.staff.assignment` lines ~400–416).
5. **No FHIR code now**: the mapping tables (§§1.8, 2.8, 3.8, 4.9, 5.8, 6.9) are the contract for `health_fhir_core` serializers later; selection codes were chosen to map verbatim — do not rename selection values without updating the tables.
6. **UI language**: labels use "Client" (not "Patient") in user-facing strings, matching the platform's terminology drift (`patient_id` field names retained for consistency with FSO).
7. **Testing**: each module ships `tests/` with the acceptance criteria above as TransactionCase tests (at minimum the state-machine guards, threshold/interaction/scoring logic, catchment rules via `with_user`).
