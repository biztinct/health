# SAAS H2b — retire the old access app: one lane, one job field, a top bar for the administrator only

Read FIRST: `docs/handovers/SAAS_PORT_PROGRAM.md` (decisions, plumbing, rails, ledger H1–H21 — H14–H21
are H2a's and describe the modules you now finish), then `SAAS_H2A_HEALTH_ACCESS_OVERLAY.md` and the
H2a report's §11 (the list of legacy readers), then `from_payobook/ACCESS_P6_GENERIC_RETIRE.md` +
`ACCESS_CLOSEOUT.md` §4.2 (the uninstall recipe, the backups-first rule, the 4 orphan
`ir_config_parameter` rows an uninstall leaves behind — ledger F8) and ACCESS_PROGRAM ledger D10
(the per-user diff is the proof), F7 (orphan `odoo-bin` before an upgrade).

Design bar (verbatim, binding): **"Extreme WOW, intuitive, out-of-this-world experience, best in
class."** H2b's hero is subtraction: a nurse signs in and sees ONE navigation — the left menu — with
nothing technical above it; the staff record says what somebody's job is in one field; and the
Access home is the only place "who can do what" lives. Zero dead-ends: every role lands on a working
home screen on the first click after sign-in (T12 proves it per role).

White-label rule (binding): "Odoo" never in a user-visible string. Plain English; no permission-group
names on screen.

---

## 0. Owner decision that shapes this phase (2026-09-04)

**"Hide the top bar from everyone but the platform administrator."** The left menu becomes the only
navigation for every role; the framework's application bar shows only for `base.group_system`
holders (today: one person). Consequence accepted by the owner: Owners, Operations Manager, Doctors
and everybody else lose the technical apps they could reach through the bar; anything a role
genuinely needs from there must be on the left menu FIRST. The H2 design session measured the
coverage (program-doc plumbing §"Top bar coverage", below): the product apps whose screens are NOT
on the left menu today are Analytics' technical children (Sources, Datasets, Pipeline Editor…),
Zalo (Conversations/Messages/Settings), VoIP24h (6 screens), Workflow Automations (2), Training's
author screens (5), CRM Center's channel-audit/watchlist screens, Employee Development (17,
`hr_development_ai`), AI Performance Coaching (1). The stock apps (Website, Sales, Project,
Purchase, Inventory, Timesheets, eLearning, Calendar, Contacts, Discuss, To-do, Link Tracker) are
NOT added to the left menu; they were visible to the Operations Manager only by omission.

The H2a `hidden_menu_ids` per-role machinery stays in `biz_access` (generic, Payobook will use it)
but this product runs the bar in **administrator-only mode** (§3.1); the migrated lists become inert
and are left in place. The Screens-lens top-bar editor promised for H2b is therefore NOT built —
record it as a Payobook-side debt in the ledger.

## 1. Scope

1. `biz_access`: top-bar mode setting (§3.1). Nothing else generic changes.
2. `health_access`: the **job field** (§3.2), the **clinic-admin group swap** (§3.3), the rail's
   single lane (§3.4), the left-menu additions for screens that only the bar reached (§3.5), the
   admin surfaces re-homed off `health_user_admin` (§3.6), and the migration that carries the data
   across BEFORE the old app goes (§3.7).
3. Every module in the seam map re-pointed (§3.8) and `access_roles` dropped from every manifest;
   the four unguarded test suites rewritten; `health_user_admin` deleted from the repo.
4. Uninstall `access_roles` and `health_user_admin` — rehearsed fully on a clone, then live **only
   after the owner says go** (§4: this phase has a hard STOP between rehearsal and live).
5. Tests (§5), commits (§6), ledger from H22, report (§7).

## 2. Binding NON-goals

- No new lenses, no top-bar editor, no changes to `biz_kit`.
- No server/nginx/DNS work (H3). No tenancy modules (H4).
- Do not touch the 6 no-role users' access, `dhanoi`'s stray branch-manager group, or the
  `qa_catch_*` accounts beyond what the migration does to everybody; list them again.
- Do not delete audit rows, hand-overs, or the H2a `hidden_menu_ids` data.
- Do not run the live uninstall without the owner's explicit go (relayed by the session lead after
  your rehearsal report). Rail R9.

## 3. Architecture

### 3.1 `biz_access` — top-bar mode

Two settings read through `ir.config_parameter` (F24: search the row, `.value`, never `get_param`
for "present but empty"):
- `biz_access.topbar_mode`: `by_role` (default — today's H2a behaviour) | `admin_only`.
- `biz_access.topbar_home_xmlids`: comma-separated menu xml-ids that stay visible to everybody in
  `admin_only` mode (roots only; their children are NOT shown — the product's own navigation shows
  the rest).

`ir.ui.menu._visible_menu_ids` in `admin_only` mode, for a user without `base.group_system`:
`super()` ∩ {the home roots that resolve}. Empty setting → keep exactly one root: the first root
the user could see anyway (so nobody is left with a blank screen — zero dead-ends), and log a
warning naming the setting. `_biz_access_forget` (the cache seam H2a built) must also fire when
either setting is written (`ir.config_parameter.write/create/unlink` override or the existing
invalidation hook — verify how the core clears `_visible_menu_ids`' ormcache on this build).
Plain role form: the "Top-bar screens hidden" tab shows a one-line note when the mode is
`admin_only` ("The top bar is shown to the platform administrator only; this list is not used.").

`health_access/data/config.xml` (`noupdate="1"`): `topbar_mode = admin_only`,
`topbar_home_xmlids = health_cms_sidebar.menu_cms_root`. **T12 decides whether that root is the
right home**: it opens `ops_command_center`; every role must be able to open it without an access
error. If a role cannot, ship a `health_access` root menu `menu_home` (sequence 0, `web_icon` the
product icon from `health_landing/static/description/icon.png`) whose action is
`health_landing.action_health_landing_dashboard` (verify it opens for every role) and point the
setting at that instead. Report which.

### 3.2 The job field — classification is not permission

Today `res.users.access_role_id` (one role per person) is BOTH the permission source and the way the
product knows who is a doctor, a nurse or an operations manager (`is_doctor_role`, `is_nurse_role`,
`is_om_role`, `access_role_display` — 60+ readers, seam map). Bundles cannot answer "what is this
person" — an Owner holds the Doctor bundle. So the classification becomes its own field:

- `biz.access.role` (extended in `health_access`): `clinical_kind` Selection `doctor | nurse |
  operations_manager | other`, default `other`, label "What this role is, clinically". Migration
  sets it ONCE by today's rule (`'doctor' in name`, `'nurse' in name`, `'operations manager' in
  name`) — the nine roles: Doctor→doctor, Nurse→nurse, Operations Manager→operations_manager,
  everything else `other`. Shown on the role form and on the role card ("Counts as: a nurse").
- `res.users.job_role_id` M2o `biz.access.role` (`ondelete='restrict'`, active roles only),
  label **"Job"**, help "The role this person is employed as. It decides what the schedule, the
  pickers and the dashboards call them. Their permissions are the roles they HOLD, on the Access
  home." `hr.employee.job_role_id` mirrors it exactly as `access_role_id` does today
  (`_compute`/`_inverse` :51–63 in `health_base/models/hr_employee.py`), `hr.employee.public` exposes
  the display/flags as today (:29–47).
- The four derived fields KEEP THEIR NAMES (so 60+ readers change nothing) and recompute from the
  job: `is_doctor_role = job_role_id.clinical_kind == 'doctor'`, `is_nurse_role == 'nurse'`,
  `is_om_role == 'operations_manager'`, `access_role_display = job_role_id.name` (label "Role").
  `@api.depends('job_role_id', 'job_role_id.clinical_kind', 'job_role_id.name')`.
- **Writing the job grants the bundle** (parity with the old sync, D-ledger A4/A5 semantics):
  `res.users.write` in `health_access` — when `job_role_id` changes and the caller may manage
  (`biz.access.can_manage()` or system), `biz.access.remove(old_job, user)` (the safe removal that
  keeps groups other held roles still need; swallow its "nothing would change" refusal) then
  `biz.access.grant(new_job, user, reason="job set on the staff record")`. A caller who may NOT
  manage cannot write the field (server-side, plain refusal). The new-person wizard sets it. A
  person action `set_job` on the passport ("Change their job") lists active roles with a
  `clinical_kind`.
- Where these fields live: `job_role_id` + the four computes move from `health_base` into
  **`health_access`** (`health_base` must not depend on `biz_access` — it is the root of the tree).
  Readers in `health_base` itself (`health_facility.manager_id` domain `is_om_role`,
  `res_users_views.xml` qualifiers) still compile because the fields exist on the model at runtime
  — but a view in `health_base` naming a field added by `health_access` breaks on a database
  without `health_access`. Therefore: those two view fragments move to `health_access` (inherit
  views), and `health_facility.manager_id`'s domain becomes a `domain=` set by `health_access`
  through a view inherit (the Python field loses the domain). Same treatment for every other
  module below `health_access` in the graph that names the four fields in XML: `health_fieldservice`
  (`healthcare_staff_views.xml:17,64–70`), `health_crm` (wizards read them in Python — Python
  reads are fine as long as the field exists at runtime; guard with `hasattr` only where the module
  can be installed without `health_access`, and say which you guarded). **Decide the dependency
  direction once and write it in the ledger**: `health_access` depends on `health_fieldservice`
  (it already depends on `health_cms_sidebar`, which depends on it), so `health_fieldservice`
  XML that names the fields must move UP into `health_access` as view inherits, while
  `health_fieldservice` PYTHON that reads the flags stays (runtime attribute; add
  `'is_doctor_role' in self.env['hr.employee']._fields` guards ONLY in code paths that can run
  before `health_access` loads — installation-time computes).

### 3.3 The clinic-administrator group swap

`health_user_admin.group_health_user_admin` (9 holders, implies `health_base.group_healthcare_admin`)
disappears with its module. `health_access` ships `group_clinic_admin` ("Healthcare: Clinic
administrator", same privilege, same `implied_ids`, comment rewritten in plain English). Migration:
every holder of the old group joins the new one; the `user-admin` ability's group becomes the new
group (write `group_ids`; the bundles recompute; T4 proves every current holder of Admin/Owner/
Operations Manager still holds them in full). `register_manager_groups` /
`registerAccessManagerGroups` → the new group. The record rule `rule_hide_system_admins` is
recreated in `health_access` on the new group (same domain). The old `rule_tenant_admin_safe_roles`
is not needed: `biz.access.role` refuses forbidden groups by constraint.

### 3.4 The rail: one lane

`health_cms_sidebar`: drop `role_ids`, `effective_role_ids` (item) and `role_ids` (section), their
view fields, and `access_roles` from the manifest; `_sidebar_visible_items` keeps ONLY the bundle
lane, `is_admin = base.group_system` (the old admin group is gone — the 7 holders who were not
Owners are listed in the report as a visible change: they now see the rail their roles open).
`health_access`'s `biz_role_ids` fields stay where they are (their rel tables carry the live gates —
do not rename a field that holds data). `HealthCmsRail._legacy_note` → always `''`; the H2a guarded
readers (`_old_roles`, `_bundles_for`, `_carry_menu_hides`, `_also_write_the_older_lane`) stay
guarded and become no-ops once the model is gone (leave them — a template built from this code
must still install; delete nothing that is already safe).

### 3.5 Left-menu additions (the price of hiding the bar)

New `cms.sidebar.item` rows in `health_access/data/cms_sidebar_items.xml` (`noupdate="1"`, gates
written by the hook with `ref('health_access.role_*')` — the roles have xml-ids now), placed in the
sections the owner's rail already uses:
- **Analytics** (section of item 105): sub-items "Explore", "Datasets", "Sources", "Pipelines",
  "Dashboards & schedules", "Semantic model", "Access rules", "AI providers", "Refresh jobs",
  "Glossary", "Import data" — gated to the four Analytics roles (Owner, Operations Manager, Branch
  Manager, Accountant) exactly as `biz_bi_cms` gates the leaf. Icons `fa fa-*` in the rail's style.
- **Care Command** (CRM section): "Channel audit", "Channel messages", "Watchlist phrases" (Owner,
  CRM), "Platform applications" is already there as "Channels (setup)" — verify, do not duplicate.
- **Zalo**: "Conversations", "Messages", "Zalo settings" under CRM (Owner, CRM, Operations Manager).
- **VoIP**: one parent "Voice" with children All calls / Missed calls / Recordings / Extensions /
  Sync call history / Configuration under OPS (Owner, Operations Manager).
- **Workflow automations**: "First-visit offers", "Timecard mismatches" under OPS (Owner, OM).
- **Training** author screens: Lessons / Stations / Learner progress / Learning events / Training
  wording under ADMIN (Owner, Admin).
- **Employee Development** (`hr_development_ai`) and **AI Performance Coaching**: ONE item each
  under OPS ("Employee development", "Coaching") gated to Branch Manager + Owner, opening the app's
  root action; do not enumerate its 17 children — that app has its own dashboard.
Use each menu's action xml-id (query `ir.model.data` for the action ids listed in the program doc's
coverage table); if an action has no xml-id, reference it by `action_tag`. Every new item's action
must open for every role it is gated to (T13).

### 3.6 Admin surfaces re-homed

- `health_landing.view_admin_users_list` becomes a **standalone** list view (copy the columns it
  inherited, `job_role_id` instead of `access_role_id`, keep `js_class`), so the uninstall's view
  cascade cannot delete it. `health_access` overrides `health_landing.action_admin_users`
  (`view_ids` form → a `health_access` copy of `view_health_users_form` with `job_role_id`;
  `search_view_id` → a `health_access` copy of the search view) in a data file loaded at `-u
  health_access`, i.e. BEFORE the uninstall step. `health_landing/views/admin_center_views.xml`
  loses its refs to `health_user_admin.*` (the standalone list needs none).
- `admin_model_navigator.js`: the People group's tabs become Users (unchanged) + **"Access &
  roles"** (client action `biz_access.action_biz_access_home`, highlight when `action.tag ===
  'biz_access_home'`); `RING0_TAB_IDS` → the new tab is gated on
  `biz_access.group_access_manager` OR `health_access.group_clinic_admin` (read the manage gate
  from `@biz_access/js/access_palette` `ACCESS_MANAGE_GATE`, do not restate it). `admin_settings.js`
  same gate. `action_admin_roles` / `action_admin_role_mgmt` deleted; `health_flow` steps
  `admin-access-roles` / `admin-role-management` → one step opening the Access home.
- `health_user_admin` is deleted from the repo (`git rm -r addons/health_user_admin`) in the same
  commit that removes the last reference to it; `health_web_leads/__manifest__.py` — check whether
  it really depends on it (the seam map says the comment at :90 explains a dependency ON
  health_user_admin) and drop it.

### 3.7 The migration — runs while the old app is still installed

`health_access/migrations/19.0.<next>/post-migrate.py` (and the same body callable from
`reseed`, guarded, for a database that never had the old app):
1. Job: `UPDATE res_users SET job_role_id = <bundle id> FROM <mapping old role id → bundle id>`
   — read the mapping by NAME through `health_access.role_*` xml-ids and `access_role.name`, by
   SQL (`to_regclass('access_role')` guard), because the old MODEL may already be gone on a
   re-run. `hr_employee.job_role_id` follows through the compute (recompute explicitly).
2. `clinical_kind` on the nine roles by the substring rule; every other role `other`.
3. The group swap (§3.3).
4. Analytics: add abilities `analytics-view` (`biz_bi.group_bi_viewer` — verify the xml-id in
   `biz_bi/security`) and `analytics-build` (`biz_bi.group_bi_creator`) to the catalogue; add
   `analytics-build` to Owner / Operations Manager / Branch Manager / Accountant; grant the group
   to any current holder of those bundles who lacks it (the `biz_bi_cms` hook already gave it to
   them — expect 0). `biz_bi_cms/hooks.py` + `models/res_users.py` role-name sync are deleted;
   the leaf gate becomes data with `ref()`.
5. `health_cms_coverage/hooks.py` ROLE_GATES by name → `ref('health_access.role_*')` data +
   hook writes `biz_role_ids` (the legacy `role_ids` write goes).
6. `health_field_requirements`: `role_ids` → `biz.access.role` (new rel table; copy the rows by
   the mapping — the seam map says the old rel has 0 rows, so this is a schema move); evaluation
   by `user.job_role_id in rule.role_ids`; `available_roles` from `biz.access.role`.
7. Write the **per-user before/after diff** (D10, same harness as H2a's `diff.py`): rail per
   entry (expect: zero losses; gains only the §3.5 items for the roles named), top bar (expect:
   everybody but the platform administrator drops to the home root — list the count per role),
   flags per employee (`is_doctor_role`, `is_nurse_role`, `is_om_role`, `access_role_display` —
   expect IDENTICAL for all 96 employees and 73 users), bundle holding per user (identical).

### 3.8 The seam map, re-pointed (every row from the H2 design session's map)

| Module | Change |
|---|---|
| `health_base` | manifest drops `access_roles`; `hr_employee.py` :30–72 and `res_users.py` :66–80 lose `access_role_id` and the four computes (moved to `health_access` §3.2); `health_facility.py:138` domain moved to a view inherit in `health_access`; `res_users_views.xml:16–19` fragment moved; migrations `19.0.1.3.0` and `19.0.1.3.8` get a `to_regclass('access_role')` / `'access.role' in env` guard at the top (they never re-run on this DB; a fresh DB skips them — the guard is for honesty); `tests/test_sh2_group_implication.py` :167–179 re-asserted against `health_access.role_doctor` holders; `data/menu_access.xml:23` comment reworded |
| `health_fieldservice` | `healthcare_staff_views.xml:64–70` field → `job_role_id` via a `health_access` view inherit (the base view keeps the label column on `access_role_display`); `health_staff_assignment.migrate_booking_staff_roles` :1493–1608 → sets `job_role_id` through the facade (grant) using `health_access.role_nurse/role_doctor`; `health_clinical_note.py:75–83` and `health_fieldservice_order.py:3888–3930` read `job_role_id.name` / `access_role_display` (unchanged strings); doctor/nurse domains unchanged |
| `health_emr` | `health_clinical_note.py:216–226` `_role_name_of` → `user.job_role_id.name` → employee display → `'Staff'` (same strings, so sealed hashes still verify — T9) |
| `health_cms_sidebar` | §3.4; `tests/test_role_inheritance.py` rewritten on `biz_role_ids` + holders |
| `health_cms_coverage` | §3.7 step 5; its test uses the CRM bundle |
| `biz_bi_cms` | §3.7 step 4; manifest gains `health_access`; tests rewritten |
| `health_field_requirements` | §3.7 step 6; manifest `access_roles` → `biz_access` (+ `health_access` if it uses the job field) |
| `health_learn` | `learn_intent.py:276` → `base.group_system` or the manage gate ⇒ `'owner'`; `fixture.js:565` comment; `test_coach.py` comment |
| `health_catchment_backfill` | hook domain → `('job_role_id.clinical_kind', '=', 'doctor')`; test on the bundles |
| `health_migration` | `migration_runner.py:1607` unchanged call (the FS method's new body) |
| `health_pwa` | `api.py:2209–2211` unchanged (field names kept) — assert in a test |
| `health_roster`, `health_crm`, `health_telemonitoring` | readers unchanged; `test_telemonitoring.py:127` sets `job_role_id` to the OM bundle instead of writing the flag |
| `health_landing`, `health_flow`, `health_web_leads` | §3.6 |
| `health_user_admin` | deleted; its tests' INTENTS live on in `health_access/tests` (ring guards: a clinic admin cannot grant a bundle reaching `group_system` — impossible by constraint, assert it; cannot deactivate the platform administrator; the create-person whitelist) |

After the code change: `grep -rn "access\.role\b\|access_roles\|access_role_id\|role\.management" addons --include='*.py' --include='*.xml' --include='*.js' --include='*.csv'` must return ONLY `health_access`'s guarded migration readers and comments that explain history. Show the output.

## 4. Rehearsal → STOP → live

**Rehearsal on `vietuat_h2b`** (clone as H1/H2a): deploy all touched modules to the shared tree
(they are inert until upgraded — but NOTE: `health_base`'s new Python is loaded by the LIVE registry
at its next restart even without `-u` (F2). Because the fields move from `health_base` to
`health_access` and `health_access` is installed on live, the live registry after a restart has the
fields from `health_access` — still complete. Confirm by reasoning in the report and by the clone
run; and keep the live service UN-restarted between the file copy and the live upgrade window.)
On the clone, in this order, each with its own log under `/tmp/h2b/`:
1. `-u health_access,health_base,health_cms_sidebar,health_fieldservice,health_emr,health_cms_coverage,biz_bi_cms,health_field_requirements,health_learn,health_catchment_backfill,health_landing,health_flow,health_web_leads,biz_access` (one run; migration writes the diff).
2. Tests: `--test-tags` naming EVERY module above plus `/health_access,/biz_access,/biz_kit`.
3. Uninstall from a shell: `env['ir.module.module'].search([('name','in',['health_user_admin','access_roles'])]).button_immediate_uninstall()` — `health_user_admin` first if the ORM does not order it; then delete the orphan `access_roles.*` `ir_config_parameter` rows (F8) and report their keys.
4. A fresh registry load with `--stop-after-init` and the "Some modules are not loaded" grep empty (F7's skipped check); the diff re-run AFTER the uninstall (the before-side is the H2a snapshot taken at step 1); `pg_restore -l`-style table count before/after (expect 23 tables + `res_users.access_role_id` gone, as ACCESS P6 measured).
5. Serve on 8169 + Chrome (T12–T14). Drop the clone.

**STOP.** Write the report (§7) with the rehearsal evidence and end your turn. The session lead
asks the owner. You will be resumed with the word to go live (or not).

**Live** (only on resume, and only with the go): F7 check for an orphan `odoo-bin`; backup
`/var/backups/saas_h2/vietuat_pre_h2b_<UTC>.dump` + `pg_restore -l`; `vietuat-deploy -d -m <the
list above>`; shell uninstall of the two modules (stop/start through `vietuat-deploy -s` around the
shell — never a bare `service` call); orphan params; the diff on live; T12 per role on live (the
validator pattern from H2a — Owner bundle, then archived); 15-minute error watch; boot time
before/after. Rollback = the dump, owner's call.

## 5. Numbered test cases

1. `topbar_mode=admin_only`: a nurse's `_visible_menu_ids` == the home root only; the administrator's
   unchanged; empty `topbar_home_xmlids` keeps exactly one root and logs the warning; `by_role`
   mode still passes H2a's T6 synthetic cases.
2. Job field: `res.users.job_role_id` mirrors to `hr.employee.job_role_id` both ways (compute +
   inverse); the four derived fields recompute from `clinical_kind`; `hr.employee.public` exposes
   display/flags as before.
3. Writing the job grants the bundle and safely removes the previous one (a user with a second
   held role keeps the groups it needs); a non-manager cannot write `job_role_id` (plain refusal).
4. Group swap: every former holder of the old admin group holds `group_clinic_admin`; the `user-admin`
   ability points at the new group; every holder of Admin / Owner / Operations Manager still holds
   the bundle in full; `rule_hide_system_admins` hides the administrator from a clinic admin's user
   list.
5. Rail single lane: `get_sidebar_data` for the three synthetic users (nurse-only / owner /
   no-role) + `@api.model` marker; the old-group `is_admin` branch is gone (a user with the old
   group and no bundle sees only ungated entries — construct with a throwaway group).
6. Coverage + Analytics gates now by `ref()`: the CRM bundle holder sees the CRM leaves; the four
   Analytics roles carry `analytics-build`; a fresh install (no old app) seeds the same gates.
7. Field requirements: a rule on the Nurse bundle applies to a user whose JOB is Nurse and not to
   an Owner who merely holds the Nurse bundle; `available_roles` lists bundles.
8. Migration parity on the CLONE (the diff): rail losses 0; flags identical for every employee and
   user; holding identical; top bar per role = home root only (counts listed); job set for all 67
   users who had a role; the 6 no-role users unchanged.
9. Sealed notes: pick 3 finalised clinical notes on the clone; their integrity check passes after
   the migration (the role string resolves to the same words).
10. Uninstall on the clone: registry loads, 0 skipped modules, 0 `ir_model_data` rows left for the
    two modules, tables dropped counted, orphan params deleted, no view/cron/menu orphaned
    (`ir_ui_view` with a missing `inherit_id`, `ir_cron` on a missing model, `ir_ui_menu` with a
    missing action — three SQL checks, all zero); `health_landing.view_admin_users_list` still
    exists and renders.
11. Full suites green: every module in §4 step 1's list, plus `/biz_access,/biz_kit`. Quote the
    `odoo.tests.result` line.
12. Chrome on the clone, **once per role** (create throwaway users holding exactly one bundle each:
    Nurse, Doctor, Accountant, CRM, Operations Manager, Owner, Admin, Branch Manager): sign in →
    the first screen after sign-in renders without an error dialog; the top bar shows no app
    switcher entries beyond the home root; the left menu is the role's. Screenshot each landing.
13. Every §3.5 new left-menu item opens (no access error) for every role it is gated to — driven
    by RPC as those users (`ir.actions.act_window` `read` + the model's `check_access`), not only
    by eye.
14. Admin surfaces: Users tab lists people with the Job column; "Access & roles" tab opens the
    home; the Settings tile gates on the manage gate; `health_flow`'s step opens the home.
15. Live (on resume only): T8 + T10 + T12 (for two roles: Nurse, Owner) + the 15-minute watch +
    boot time before/after + the repo↔server tree hashes for every touched module.

## 6. Commits (explicit staging, no push)

1. `feat(biz_access): top-bar mode — administrator-only with named home roots`
2. `feat(health_access): the job field, clinic-administrator group, single-lane rail, left-menu coverage for bar-only screens, retirement migration`
3. `refactor(access): re-point every module off access_roles — health_base, fieldservice, emr, cms_sidebar, cms_coverage, biz_bi_cms, field_requirements, learn, catchment_backfill, landing, flow, web_leads` (one commit; it is one change)
4. `chore(access): remove health_user_admin from the repository`
5. `docs(saas): H2b handover, ledger H22+, rehearsal diff, screenshots` (and a 6th after the live step: `docs(saas): H2b live — access_roles retired`)

## 7. Report back (rehearsal report first; live addendum on resume)

1. **Owner summary, 6 lines, screen words**: what a nurse/doctor/owner sees now, what nobody lost,
   the two visible changes (top bar administrator-only; the 6 non-Owner old-admin-group holders now
   see their roles' rail), what will be uninstalled on go and what the rollback is.
2. Per numbered test with evidence; T8's diff totals; T12's per-role landing screen names.
3. The `odoo.tests.result` line(s); the install/upgrade log ERROR grep.
4. The seam grep output after re-pointing (must be only guarded readers + history comments).
5. The home root decision (§3.1) and why.
6. Dependency-direction decision (§3.2) and every place you had to guard a read.
7. Uninstall measurements on the clone (tables, columns, xmlids, orphans, params).
8. Backup path/objects; memory; live-service check (the live service untouched during rehearsal).
9. Ledger entries (from H22); commit hashes; clone dropped; serve unit stopped.
10. Decisions the handover did not cover; the exact live runbook you will execute on go (commands
    in order) so the owner sees what "go" means.
