# SAAS H2a — `health_access`: the clinic overlay on the Access home, live BESIDE the old app

Read FIRST: `docs/handovers/SAAS_PORT_PROGRAM.md` (decisions, plumbing, rails R1–R13, design bar,
ledger H1–H13), then `SAAS_H1_KIT_ACCESS_CORE.md` §3.3 (the rail provider protocol as built — the
final shape is in H1's report §5 and in `addons/biz_access/models/access_common.py`), then the
Payobook precedents this phase clones: `from_payobook/ACCESS_P1_ROLE_BUNDLES.md` (one ability per
group, roles rebuilt as bundles, migration invisible), `ACCESS_PROGRAM.md` ledger D1–D10 (the role
lane on a live menu, the per-user before/after diff, `(4, ref)` never `(6, 0)`), E1 (Rail A seams),
H1–H2 (catalogue seeded mid-cascade).

Design bar (verbatim, binding): **"Extreme WOW, intuitive, out-of-this-world experience, best in
class."** H2a's hero: the Access home opens on the LIVE product with the clinic's nine roles
already written down in plain English, every left-menu entry showing who opens it, and a nurse's
passport drawn as the exact menu that nurse sees — on the day it ships, before anybody has typed
anything. Zero dead-ends, plain language, motion with purpose, Lucide via `ic()`, no emoji, no
gradients. Chrome validation mandatory.

White-label rule (binding): "Odoo" never in a user-visible string. Plain English in the screen's
vocabulary; no permission-group names on screen.

---

## 0. What H2a is, and what it is not

The old access app (Cybrosys `access_roles`) is load-bearing on the live database (ledger H5):
one assigned role per user, 79 gated left-menu entries, 2,488 hidden top-bar menus, a
developer-mode flag, and the tenant-admin user wizard built on top of it. **H2a puts the new
Access home beside it, additive only.** After H2a: every old role exists as a plain-English bundle
with an xml-id; every left-menu gate is written on BOTH lanes; the top-bar hiding is enforced
natively as well as by the old app; developer mode is blocked for everyone but the platform
administrator; the People lens can add a person, deactivate, reset a password and open the staff
record; and the Access home is one click from the ADMIN section. Nothing is removed, nothing a
user could do yesterday is refused today, and a per-user before/after diff proves it. **H2b**
(next phase) re-points the 292 code references, uninstalls `access_roles` and `health_user_admin`,
and drops the legacy lane.

## 1. Scope

1. New module `addons/health_access` — depends `['biz_access', 'health_base', 'health_cms_sidebar',
   'health_landing', 'hr']`. **NOT** on `access_roles` or `health_user_admin` (every read of the old
   model is guarded `'access.role' in env` / `'access_role_id' in fields` — this module must still
   install on the day they are gone).
2. Clinic vocabulary: areas, **one ability per permission group in use** (§3.1), the nine roles as
   bundles (§3.2) with stable xml-ids, holders reconciled.
3. The `cms.sidebar` rail provider + the bundle lane on `cms.sidebar.item`/`.section` +
   `get_sidebar_data` reading both lanes as an OR + the `CMS_SIDEBAR:RELOAD` bus seam (§3.3).
4. Generic in `biz_access`: top-bar menu gating by role (`hidden_menu_ids` + `ir.ui.menu` override,
   §3.4); Rail A debug block (§3.5); person-action and people-action slots on the People lens (§3.6).
5. `health_access` migration of the old app's data into the new: roles, holders, rail gates,
   menu hides — idempotent, guarded, with a written per-user diff (§3.7).
6. The new-person wizard on the People lens (§3.6), the rail item under ADMIN, `registerHome`,
   `register_manager_groups` for the clinic's admin tier.
7. Tests (§5): parity tests are the phase's proof.
8. Rehearsal on a scratch clone `vietuat_h2`, then **deploy to the live database** (§4) — after a
   backup, through the wrapper (add an `-i` option to it), with Chrome validation on the live site.
9. Commits (§6), ledger entries from H14, report (§7).

## 2. Binding NON-goals

- Nothing uninstalled. No code reference to `access.role` outside `health_access`'s guarded
  migration is touched (H2b). No manifest loses `access_roles` (H2b).
- The legacy lane keeps working exactly as today: `user.access_role_id` + `role_ids` on items and
  sections are still read. The new lane is added, never substituted.
- No top-bar EDITOR in the Screens lens (H2b). H2a enforces + migrates + shows the list on the
  plain role form.
- No changes to `health_user_admin` (it stays installed and untouched); the old "Users & Roles"
  rail item stays. H2a adds a NEW item.
- No `biz_tenancy`/`biz_tenants`. No changes to server config, nginx, DNS (H3).
- `is_chatter` (hide chatter for Branch Manager + Accountant) is NOT reproduced — record it as an
  owner-visible change in the report; it is cosmetic and the chatter is bottom-mounted anyway.
- Do not "fix" the seam map's data smells (the Owner user who lacks one group, the six users with
  no role) beyond what §3.7 says; list them.

## 3. Architecture

### 3.1 Vocabulary — areas and abilities (`health_access/hooks.py`, registered via `register_areas` / `register_catalogue`)

Areas (key → label): `clinical` → "Clinical care", `front_desk` → "Front desk & CRM",
`operations` → "Operations", `finance` → "Finance", `admin` → "Administration", default `clinical`.

**One ability per group** (ACCESS P1's rule: the migration is exact only when every group a role
carried is an ability of its own). Seed these `(technical_key, area, sequence, name, description,
(group_xmlid,))` — write each description yourself in the catalogue voice: one sentence, what it
lets someone do AND what it does not; no module names, no "Odoo":

| key | area | group | name |
|---|---|---|---|
| sign-in | admin | base.group_user | Sign in and use the basics |
| care-base | clinical | health_base.group_healthcare_base | See the clinic's patients and visits |
| reception | front_desk | health_base.group_healthcare_receptionist | Work the front desk |
| nursing | clinical | health_base.group_healthcare_nurse | Give nursing care |
| head-nursing | clinical | health_base.group_healthcare_head_nurse | Lead the nursing team |
| doctoring | clinical | health_base.group_healthcare_doctor | Practise as a doctor |
| sales | front_desk | health_base.group_healthcare_sales | Sell services and follow up leads |
| ops-manage | operations | health_base.group_healthcare_operations_manager | Run daily operations |
| finance-work | finance | health_base.group_healthcare_finance | Work the clinic's finances |
| care-manage | operations | health_base.group_healthcare_manager | Manage the care team |
| care-admin | admin | health_base.group_healthcare_admin | Administer the clinic's records |
| records-custody | admin | health_base.group_healthcare_custodian | Archive and restore records |
| ownership | admin | health_base.group_healthcare_owner | Own the clinic's data |
| patient-portal | clinical | health_base.group_healthcare_patient | Use the patient portal |
| crm-work | front_desk | health_crm.group_health_crm_user | Work enquiries and bookings |
| crm-manage | front_desk | health_crm.group_health_crm_manager | Manage enquiries and bookings |
| invoicing-work | finance | health_invoicing.group_health_invoicing_user | Raise and send invoices |
| invoicing-manage | finance | health_invoicing.group_health_invoicing_manager | Manage invoicing |
| insurance-claims | finance | health_invoicing.group_insurance_claims | Process insurance claims |
| misa-sync | finance | health_invoicing.group_misa_integration | Run the accounting sync |
| tax-compliance | finance | health_invoicing.group_vietnamese_tax_compliance | Keep tax records compliant |
| red-invoice | finance | health_redinvoice.group_health_redinvoice_manager | Issue red invoices |
| accounting-invoices | finance | account.group_account_invoice | Work in the accounting ledger |
| staff-records | operations | hr.group_hr_user | Manage staff records |
| sales-all-leads | front_desk | sales_team.group_sale_salesman_all_leads | See every lead |
| sales-manage | front_desk | sales_team.group_sale_manager | Manage the sales team |
| coaching-branch | operations | hr_development_ai.group_bfsi_branch_manager | Coach as a branch manager |
| user-admin | admin | health_user_admin.group_health_user_admin | Add people and give out roles |

`ensure_catalogue` skips a missing xml-id with a log line (P1 behaviour) — `hr_development_ai`
and `health_user_admin` may be absent on a fresh database. Add every OTHER custom group that a live
`access.role` carries and this table missed: the migration (§3.7) must refuse to run if any group
on any old role has no ability (it logs the xml-id and raises), so the table is complete by
construction — run it on the clone first and extend the table until it passes. Rail B: none of
these may reach `base.group_system`/`group_erp_manager` (the harness test proves it against the
REGISTERED catalogue now that one exists).

### 3.2 The nine roles as bundles

Seed (create-only, E3) `biz.access.role` records named exactly as the old ones — **Owner,
Operations Manager, Branch Manager, Banker, Nurse, Doctor, Accountant, Admin, CRM** — each with
`ability_ids` = the abilities whose group is in the old role's group set (H0 table in the program
doc lists them; read the LIVE rows in the migration, never the table), area from the majority of
its abilities, description one honest sentence each (write them), and an xml-id
`health_access.role_<slug>` written into `ir.model.data` (`noupdate=1`) so every later data file
and hook can `ref()` a role — this is what ends the "roles have no xml-id" python-gating in
`health_cms_coverage` and `biz_bi_cms`. **Banker** (0 users, `base.group_user` only) is created
**archived** — a live role of nothing but sign-in would be held by everybody and would open every
gate it sits on. **Admin**'s bundle is `sign-in` + `user-admin`; register
`health_user_admin.group_health_user_admin` through `register_manager_groups` (server) and
`registerAccessManagerGroups` (browser) so the clinic's administrators can grant, take back and edit
gates — the two-ring rule (memory `project_access_two_ring`) keeps `base.group_system` with the
platform administrator alone.

Seeding happens in `post_init_hook` AND in a migration for every future catalogue change (A2);
`biz.access.reseed_catalogue()` is the re-run door.

### 3.3 The `cms.sidebar` rail provider and the bundle lane

`health_access/models/cms_sidebar.py`:
- `cms.sidebar.section` gains `biz_role_ids` (m2m `biz.access.role`, `health_access_section_role_rel`,
  `section_id`, `role_id`); `cms.sidebar.item` gains `biz_role_ids` (`health_access_item_role_rel`)
  and `effective_biz_role_ids` (compute, same union-inheritance as `_compute_effective_role_ids`
  :62–91 — own ∪ section ∪ parent ∪ parent's section; `compute_sudo`).
- `get_sidebar_data` override: **two lanes, read as an OR** (D1). Visible when: admin; OR the
  entry has no gate on EITHER lane; OR the legacy rule passes (unchanged code path); OR the user
  holds ANY effective biz role in full (`rail_state` from `access_common` with `group_ids=[]`,
  `restricted=False`, `role_ids=effective_biz_role_ids`, `held=user.all_group_ids`, `role_groups`
  from active roles — D2 both helpers). Admin = `base.group_system` OR the old admin group when it
  still exists (guarded `env.ref(..., raise_if_not_found=False)`). Keep the method's `@api.model`
  (F46 — add a test on the marker).
- The provider `HealthCmsRail(RailProvider)`, key `cms_sidebar`, registered at import time
  (`register_rail(HealthCmsRail())`): `sections()` → cms sections (+ optional `role_ids` =
  section's `biz_role_ids`, extend the protocol with that optional key and say so); `entries()` →
  items with `parent_id`, `icon` (the stored `fa fa-*` string — the mini rail already renders it),
  `group_ids=[]`, `restricted=False`, `role_ids=biz_role_ids` (raw, archived included);
  `visibility_for(user)` → EXACTLY what `get_sidebar_data` would draw for that user (share one
  private helper, never two copies — C1), items `on|hidden`, sections `on|hidden`; writes:
  `set_roles` → `biz_role_ids` `(6, 0, ids)`, `set_active`, `reorder` → `sequence` in tens,
  `set_restricted` → `UserError(_("This left menu has no locked preview; an entry is either shown
  or hidden."))`; `advanced_action()` → `health_cms_sidebar.action_cms_sidebar_item` (verify the
  xml-id in `views/cms_sidebar_menus.xml`); `reload_event()` → `"CMS_SIDEBAR:RELOAD"`.
- `health_cms_sidebar/static/src/js/cms_sidebar.js`: add `useBus(this.env.bus, "CMS_SIDEBAR:RELOAD",
  () => this._loadSidebarData())` — the ONE change to that module (D7: a bus event, not an import).
  Bump its manifest version; it is in the test scope (F49).
- The Screens lens must now show the health rail with the legacy gates VISIBLE as read-only
  context: per entry, if the legacy lane names roles and the bundle lane does not, show a quiet
  note "Also opened by the older gate: Owner, CRM" (facade `_legacy_note` seam from H1 exists —
  use it through a provider-supplied optional `legacy_note` string on the entry dict). After the
  migration both lanes agree, so the note is empty everywhere on day one; it exists for the day
  somebody edits only one lane before H2b.

### 3.4 Generic: top-bar menus by role (`biz_access`)

- `biz.access.role.hidden_menu_ids` — m2m `ir.ui.menu`, "Top-bar screens this role does not see",
  shown on the plain role form as a tab (list, no_create, grouped by root in the display).
- `biz_access/models/ir_ui_menu.py` overrides `_visible_menu_ids(debug)`: `super()` first; return
  it untouched when the user has `base.group_system`; collect the ACTIVE roles the user holds in
  full (`rail_state`'s holding rule) **whose `hidden_menu_ids` is non-empty**; when none →
  unchanged; else hidden = **intersection** of their lists, each list first expanded to every
  descendant menu; subtract. Why intersection: a menu is hidden only when every role the person
  holds hides it — holding more never shows less, which is the same monotonic rule the rail uses.
  Roles with an EMPTY list have no opinion (this is what keeps "Admin" from opening everything to
  every Owner — §3.7). Menus that arrive with a future module are visible by default, exactly as
  today. Cache: `super()` is ormcached by the core; the override recomputes per call — measure the
  cost on the clone (one page load) and, if above 50 ms, cache on `(uid, debug, lang)` and
  invalidate from `biz.access.role.write`/`res.users.write` the way the core invalidates menus
  (find `_invalidate` in the server's `ir_ui_menu.py` :75–240). Add a test that the marker/caching
  does not break `load_menus`.
- No editor in the Screens lens yet (H2b). The facade's `role_detail` gains `hidden_menus:
  [{root, names}]` so the role card's "opens" column can say "Does not see 8 top-bar apps" with a
  hover list — one honest line, no new lens.

### 3.5 Generic: Rail A — developer mode is the platform administrator's (`biz_access/models/ir_http.py`)

Clone Payobook E1 onto THIS build's seams (`web/models/ir_http.py` `_handle_debug` :46,
`_pre_dispatch` :57, `session_info` :79/:133/:193 — program doc): in `_pre_dispatch`, after
`super()`, if `request.session.debug` and the session's user (read `request.session.uid`, browse
with sudo — the env may not be on the user yet, E1a) lacks `base.group_system`, set
`request.session.debug = ''`. Second seam (E1b): the login page copies `?debug=` into the page and
can render a superuser button — close it in `ir.qweb._prepare_environment` or wherever this build's
`web.login` reads `debug` (verify; report what you found). Neither `biz_theme` nor `biz_deroute`
exists here; `health_theme/models/ir_http.py` and `health_fieldservice/models/ir_http.py` only
extend `session_info`, so `biz_access` may inherit `ir.http` directly. Setting to switch it off:
`biz_access.debug_block` (`'off'` disables; anything else = on). Test: an HttpCase where a plain
user opens `/bizapp?debug=1` and `session_info()['bundle_params']` carries no `debug`, and the
administrator's does.

### 3.6 Generic: person actions on the People lens; health: the wizard and the actions

`biz_access` facade gains two server-driven slots (no JS registry; the overlay overrides methods):
- `people_actions()` → `[{id, label, icon, action_xmlid, context?}]` for the People lens header;
  default `[]`. The browser draws them as kit buttons and opens the action; on `onClose` it
  re-reads `people()`.
- `person_actions(user_id)` → `[{id, label, icon, kind: 'run'|'open', confirm?: sentence,
  danger?: bool}]` for the passport; `run_person_action(action_id, user_id)` dispatches to
  `_person_action_<id>(user)` and returns `{'ok', 'message', 'action'?}`; every dispatch re-checks
  `can_manage()` and refuses `base.group_system` holders and self where the old code did.

`health_access` provides:
- `health.access.new.person` (TransientModel) — a faithful copy of `health_user_admin`'s wizard
  (`wizard/health_create_user_wizard.py`, its view) with `role_id` → `biz.access.role`
  (`domain=[('active','=',True)]`, `no_create`), the qualifiers (`is_duty_doctor` shown when the
  role carries the `doctoring` ability, `is_head_nurse` when it carries `nursing`/`head-nursing` —
  by ABILITY KEY, not by name substring), company/lang/tz, catchment province, facility,
  employment status/type; `action_create` creates the user through `biz.access`-safe means (a
  whitelist like `action_saas_create_user`, `_dangerous_subset` re-implemented over
  `all_implied_ids`), grants the role through `biz.access.grant()` (audited), and creates the
  `hr.employee` exactly as the old wizard does. **While the old app is installed** it ALSO sets
  `user.access_role_id` to the same-named old role when one exists (guarded) — the two lanes stay
  in step until H2b. Registered through `people_actions()` as "Add a person" (`icon: 'userPlus'`).
- `person_actions`: `deactivate` (archive; refuses system admins and self), `activate`,
  `reset_password` (refuses system admins unless self; uses the standard reset mail path and says
  plainly when no mail server exists — there is none today, decision 5), `open_staff` (opens the
  `hr.employee` form, kind `open`). Copy the refusals' wording from `res_users_saas.py` :123–156.
- `registerHome("health_landing.action_admin_dashboard")` in `health_access`'s palette file.
- Rail item: `cms.sidebar.item` "Access & roles" in `section_admin`, sequence 25 (right after
  "Users & Roles"), `icon` `fa fa-key`, `action_xmlid` `biz_access.action_biz_access_home`,
  `match_action_tags` `biz_access_home`, gated on `biz_role_ids` = Owner + Admin. The data file
  can only `ref()` roles that exist, and the hook creates them — so the ITEM ships ungated in XML
  and the hook writes the gate (§3.7 does this for every entry anyway), and a test asserts the
  gate is present after install.

### 3.7 The migration (`health_access/hooks.py` `migrate_legacy(env)` — post_init + `reseed` door)

Idempotent, guarded (`'access.role' in env` else "nothing to migrate", log + return), each step
writes a summary line, and the whole thing produces `docs/handovers/saas_h2_shots/migration_diff.md`
on the clone (write the diff to `/tmp/h2/` on the server and copy it into the repo):
1. **Roles** (§3.2). Refuse (raise, name the xml-id) if any group on any old role has no ability.
2. **Holders**: for every active internal user with `access_role_id`, if they do not hold the new
   bundle in full, `biz.access.grant(role, user, reason="carried over from the previous access
   app")` — adds ONLY missing groups (A4 semantics). Expected: exactly 1 Owner user gains
   something (H0 found one mismatch); list them.
3. **Rail gates**: every item/section with legacy `role_ids` gets `biz_role_ids` = the mapped
   bundles (`(6, 0, …)` on OUR field only — never touch `role_ids`). Write the new ADMIN rail item's
   gate here too.
4. **Menu hides**: for each `role.management` profile linked to a role (`access_role_role_management_rel`),
   `hidden_menu_ids` = the profile's `ir_ui_menu_role_management_rel` menus **compressed to the
   top-most hidden ancestors** (drop a menu whose parent is also hidden) and restricted to active
   menus; profiles linked to no role are skipped; the "Tenant Admin" profile hides nothing so Admin's
   list stays empty (= no opinion); Doctor has no profile → empty. Skip the `Access Role` root
   (id 716) — it disappears with the old app.
5. **The per-user diff** (D10): for EVERY active internal user, before (old rule alone) vs after
   (both lanes): rail visibility per entry (`get_sidebar_data` as that user), and top-bar visibility
   (`_visible_menu_ids` as that user). Expected result: **zero entries lost by anybody, zero menus
   lost by anybody**; gains allowed only for users who hold MORE than one bundle (Owners: CRM Center
   with Care Command + Care Command Setup, Zalo, Workflow Automations — by intersection with Nurse,
   whose groups every Owner carries). Print the gains per user. Anything lost = a failed phase.

## 4. Rehearsal, then live

**Clone** `vietuat_h2` exactly as H1 §4 (dump/restore, `web.base.url`, a validator login with
`base.group_system` on the CLONE only). Deploy the modules to the shared addons tree (inert until
installed). Install on the clone: `-i health_access` (`biz_kit,biz_access` come with it), tests over
`/biz_kit,/biz_access,/health_access,/health_cms_sidebar,/health_theme` (F49: every module edited).
Serve on 8169, tunnel, Chrome (§5 T12), then drop the clone.

**Live** (rail R9 — this IS the live customer database; do it exactly like this and stop at the
first surprise):
1. `free -m`, `ps aux | grep '[o]doo-bin'` (only the service, ~5 processes), no other session's work.
2. Backup: `sudo -u postgres pg_dump -Fc -Z1 vietuat -f /var/backups/saas_h2/vietuat_pre_h2a_<UTC>.dump`
   (`sudo mkdir -p /var/backups/saas_h2` first) and `pg_restore -l` it; the filestore is untouched
   by this phase so it is not copied — say so.
3. Add `-i` to the deploy wrapper: `.agent/workflows/vietuat-deploy.sh` gains `-i <modules>` (adds
   `-i $INSTALL` to the odoo-bin args; `-m` may be empty when `-i` is given); install the new copy
   to `/usr/local/bin/vietuat-deploy` with `sudo install -m 755`. Commit it with H2a.
4. `vietuat-deploy -d -i health_access -m health_cms_sidebar` (the `-d` copies both from `/tmp`;
   scp `biz_kit`, `biz_access`, `health_access`, `health_cms_sidebar` to `/tmp` first — the wrapper's
   `-d` loop iterates the `-m` AND `-i` lists, make sure it does).
5. Wrapper prints `http=200 procs=~5`; then `sudo grep -a "health_access" /var/log/odoo/odoo-server.log | tail`
   for the migration summary lines; run the diff report on live (read-only; it is the same code
   path that ran on the clone) and confirm **zero losses**.
6. Chrome on `https://care.biztinct.com` (§5 T13). Login: use the owner's already-signed-in Chrome
   if it is running with the remote-debugging port; otherwise create `h2.validator@local` on live
   with the **Owner** bundle granted through the Access home (NOT `base.group_system` — the
   two-ring rule), validate, then archive that user and end its session; say so in the report.
7. 15-minute log watch: `sudo grep -aE " ERROR vietuat | CRITICAL vietuat " /var/log/odoo/odoo-server.log | tail`
   must show nothing new.

Rollback if step 5 or 6 fails: `vietuat-deploy` cannot uninstall; the honest rollback is
`pg_restore` of the step-2 dump (owner's call — stop and report, do not restore on your own).

## 5. Numbered test cases

1. Catalogue completeness: every group on every live `access.role` maps to exactly one ability;
   the migration refuses when one is missing (test with a throwaway old role carrying an unmapped
   group — skip when `access.role` is absent).
2. Rail B over the REGISTERED clinic catalogue: no ability reaches a forbidden group.
3. Roles: nine bundles exist with xml-ids `health_access.role_*`; Banker archived; `group_ids` of
   each equals the old role's group set exactly (set equality, per role).
4. Holders: after migration every active user with `access_role_id` holds the same-named bundle in
   full; the audit trail shows the carried-over grants with the reason sentence.
5. Rail parity (the D10 test): for every active internal user, `get_sidebar_data()` before/after is
   identical except for the new "Access & roles" item (Owner/Admin holders gain it, nobody else
   sees it) — run on the clone against real data; also a synthetic TransactionCase with three
   fabricated users (nurse-only, owner, no-role).
6. Menu parity: for every active internal user, `_visible_menu_ids()` after == before (both engines
   active) — real data on the clone; synthetic case: a role with a compressed hidden list hides the
   whole subtree; a user holding two listed roles sees the intersection; an unlisted role changes
   nothing; the system administrator is never affected.
7. Provider: `visibility_for(user)` == what `get_sidebar_data()` draws, for the three synthetic
   users; `set_roles` fires `CMS_SIDEBAR:RELOAD` in the facade's return; `reorder` writes tens;
   `set_restricted` raises the plain refusal.
8. `get_sidebar_data` keeps `@api.model` (F46 marker test) and the OR of lanes: a nurse-only user
   sees an entry gated ONLY on the bundle lane to Nurse; a user with `access_role_id` Nurse and no
   groups (legacy lane) still sees legacy-gated entries.
9. Rail A: HttpCase — plain user with `?debug=1` gets no `debug` in `session_info`; admin keeps it;
   with `biz_access.debug_block = off` the plain user keeps it.
10. New person wizard: as a user holding Admin (no `group_system`), create a nurse with catchment
    + facility → user active, employee created with facility/catchment, holds the Nurse bundle,
    `access_role_id` set to the old Nurse while the old app is installed; refuses a duplicate login;
    a role carrying a forbidden group cannot exist, so assert the wizard's role picker domain
    excludes archived roles.
11. Person actions: deactivate refuses the system administrator and self; reset password reports
    the missing mail server in plain words; open_staff returns an act_window on the employee.
12. Chrome on the CLONE (`docs/handovers/saas_h2_shots/clone_*.png`): (a) ADMIN section shows
    "Access & roles"; (b) Roles lens with the nine roles, "Nurse" card opened: opens column lists
    the real entries (Care Command? no — the ones the rail gates to Nurse), abilities in plain
    words, 44 holders; (c) People lens: a real nurse's passport = their real left menu (compare
    with `get_sidebar_data` as that user); (d) Screens lens: the health rail drawn with role chips,
    change a gate on a throwaway entry and watch the live rail reload without a page refresh;
    (e) "Add a person" opens the wizard; (f) role form → the "Top-bar screens hidden" tab for Nurse
    lists the compressed roots; (g) `getComputedStyle` `--bzk-primary` = `#1565C0`.
13. Chrome on LIVE after deploy (`live_*.png`): (a) sign in, ADMIN → "Access & roles" opens the
    home in the health palette; (b) Roles lens: nine roles, holder counts match the H0 table
    (Owner 6, Nurse 44, Doctor 10 …); (c) a nurse's passport; (d) Screens lens read-only tour — do
    NOT change a live gate; (e) as the validator, `?debug=1` is stripped; (f) console clean.
14. Live health: `/web/login` 200 before/after; 15-minute error watch clean; the H1 `vietuat_h1`
    lesson — the clone `vietuat_h2` dropped and `h2-serve` stopped.

## 6. Commits (explicit staging, no push)

1. `feat(biz_access): top-bar menus by role, developer-mode rail, person-action slots on the People lens`
2. `feat(health_access): clinic overlay — vocabulary, nine roles as bundles, cms.sidebar rail provider, legacy migration, new-person wizard`
3. `feat(health_cms_sidebar): reload the rail on CMS_SIDEBAR:RELOAD` + `chore(deploy): -i on vietuat-deploy`
4. `docs(saas): H2a handover, ledger H14+, migration diff, screenshots`

## 7. Report back

1. **Owner summary, 6 lines, screen words**: what people see today that they did not yesterday;
   what nobody lost (with the diff's zero); the one visible change (chatter hiding gone for two
   roles, developer mode gone for everyone but the platform administrator); what is still the old
   app's (until H2b).
2. Per numbered test: pass/fail + evidence. T5/T6 quote the diff totals (users × entries, users ×
   menus, losses = 0, gains listed).
3. `odoo.tests.result` lines (clone run, and the live wrapper run if tests were on).
4. The catalogue as seeded (keys + groups) and any group you had to add to §3.1's table.
5. The migration summary lines from the LIVE log, verbatim.
6. Protocol extensions you made (`role_ids` on sections, `legacy_note` on entries, anything else).
7. Rail A: which seams you overrode on this build (file:line), and what the login page did with
   `?debug=`.
8. Menu-override cost measured (ms per `load_menus` on the clone) and whether you cached.
9. Backup path + `pg_restore -l` object count; memory readings; live-service check.
10. Ledger entries appended (from H14). Commit hashes. Clone dropped, serve unit stopped,
    validator archived if created.
11. Decisions you made that this handover did not cover — and the list H2b needs: every place the
    legacy lane is still read (you will have seen them while writing the provider).
