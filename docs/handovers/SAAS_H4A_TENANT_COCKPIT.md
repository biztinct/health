# SAAS H4a — `biz_tenancy` + `biz_tenants` + `health_tenancy`: creating and running customers

Read FIRST: `docs/handovers/SAAS_PORT_PROGRAM.md` (decisions, plumbing, rails R1–R13, design bar,
ledger H1–H60 — H36–H60 are H3's and describe the server you are building on), then
`docs/SAAS_RUNBOOK.md` (this product's, written in H3 — the operational truth), then
`from_payobook/FLEET_PROGRAM.md` §"Verified plumbing" and the ledger entries this phase leans on:
**F1, F3, F4, F7, F8, F9, F12, F19, F20, F23, F24, F26, F33, F34, F44, F56, F59** and ACCESS **A8,
F6, F7, G8**. Source to port (READ-ONLY, rail R10): `gitlocal/pb_tenants/` and `gitlocal/pb_tenancy/`.

Design bar (verbatim, binding): **"Extreme WOW, intuitive, out-of-this-world experience, best in
class."** H4a's hero moment: **the provisioning screen**. The owner types a clinic's name, presses
one button, and watches six steps complete in front of them with live log lines — ending on a
working address, an administrator's name and a password to hand over. Zero dead-ends: every step
that can fail says what failed, what it left behind, and the one button that continues or undoes it.
Plain language throughout; Lucide via `ic()`; no emoji, no gradients; Chrome validation mandatory.

White-label rule (binding): "Odoo" never in a user-visible string; the product's name comes from a
brand setting, never a literal. Plain English in the screen's vocabulary.

---

## 0. What H4a is

The platform can now host customers (H3), but nothing creates one. H4a builds the cockpit that
does, the agent that lives on each customer's database, and the health-product overlay that tells
the generic pair what this product is. It ends with the pilot customer **`hhh.carejiox.com`** live,
created from the golden template by pressing a button.

**Split:** H4a is provisioning, the fleet, health, backups, keeping customers in step, and releases.
**H4b** (next) is rollout waves, alerts, the capacity guard, the public status page, feature
switches, plans/invoices, and support access with a trail. Build the seams H4b needs (§3.7) but
none of its features.

## 1. Scope

1. `addons/biz_tenancy` — the tenant-side agent, installed on the master, the template and every
   customer. Depends `['web', 'biz_kit']`.
2. `addons/biz_tenants` — the cockpit. Apex only, on the never-list. Depends
   `['web', 'biz_kit', 'biz_tenancy']`.
3. `addons/health_tenancy` — the overlay, installed everywhere (its cockpit-side registrations are
   inert where `biz_tenants` is absent). Depends `['biz_tenancy', 'health_cms_sidebar', 'health_access']`.
4. The six-step provisioning, the fleet screen, per-customer detail (overview / backups / in step /
   danger), backups + restore-to-staging, "In step with master", releases + the nightly drift read.
5. The template gap this phase must close (§3.8): the golden template does **not** carry
   `biz_access.topbar_mode = admin_only`, so a customer cloned today would show every nurse the
   whole top bar.
6. Provision **`hhh`** on the live platform, validate it in Chrome, hand back its administrator
   details in the report (§7.1).
7. Tests (§5), commits (§6), ledger from H61, runbook update, report (§7).

## 2. Binding NON-goals

- No rollout waves, alerts, capacity gauge, status-page writer, feature switches, plans, invoices,
  seat limits, trials, paused door, or support access — all H4b. Do not build "just the model".
- **No custom domains.** H3 proved this build ignores `X-Odoo-dbfilter` (report §6), so
  `biz-domain-attach` refuses by design. The cockpit's Domains tab shows the customer's own
  `<slug>.carejiox.com` and says in one plain sentence that customer-owned domains need a platform
  change first. Do not write a pinning header that does nothing.
- No changes to nginx, the conf, certbot or sudoers beyond calling the three installed scripts
  (H3 owns them). No resize.
- Do not install `biz_tenants` anywhere but the master. Do not install anything on `hhh` by hand
  that the template did not carry.
- Do not touch the Access home, the rail's gating rules, or `health_access`'s catalogue except the
  one config gap in §3.8 and the tenant-admin role read in §3.5.

## 3. Architecture

### 3.1 `biz_tenancy` — the agent on every database

Port `pb_tenancy` minus everything H4b owns. What it is here:

- **Parameters it reads** (all `biz_tenancy.*`, pushed by the cockpit through `_tenant_env`):
  `release`, `release_notes`, `release_at`, `notice`, `notice_kind`, `notice_from`, `notice_to`,
  `pushed_at`, `platform_url`, `support_email`. Read them with a `search` on
  `ir.config_parameter` and `.value`, never `get_param`, wherever "set but empty" is meaningful
  (**F24** — `get_param` answers `False` for absent AND for empty).
- **The notice bar**: an OWL component mounted **after `//NavBar`** (`web.WebClient` extension) —
  **F18**, and confirmed free in this product: only `health_fieldservice` replaces
  `//ActionContainer` and only `health_learn` anchors on `//MainComponentsContainer`. Shows a
  planned-maintenance window before an update and an "being updated right now" state during one.
  Windows are stored UTC and rendered in the **reader's** clock (**F17/F32**: convert explicitly,
  both ways, and name nothing "today" that you have not converted).
- **The poll**: `/biz_tenancy/state`, `type='jsonrpc'` (**F21** — `type='json'` is a deprecated
  alias on this build), `readonly=True`, `auth='user'`. Every 60 s **while the tab is visible**,
  plus immediately when a hidden tab returns after more than 60 s (**F14** — and remember it when
  validating: a background tab does not update).
- **The release stamp + "What's new"**: the customer's own screen listing the releases they have
  received, newest first, with the notes the platform wrote. A toast the first time a new release
  is seen.
- **The About surface**: a client action `biz_tenancy_about` — "About {brand}" — carrying: which
  release this database is on, what changed, who to contact, and (H4b) plan, support access.
  `biz_tenancy` ships the action and the component; the DOOR is the overlay's (§3.5).
- Python: no model inherits. Nothing product-specific. A source-text test (R11) fails on
  `health_`, `pb_`, `Payobook`, `Viet Uc`, `carejiox` and `Odoo` in user-visible copy.

### 3.2 `biz_tenants` — the models

`biz.tenant`: `name`, `slug` (the database name AND the hostname label — one validated field:
`^[a-z][a-z0-9]{1,30}$`, no underscore, not in a reserved list `('postgres','template0','template1')`
nor equal to the apex database or the template), `state`
(`draft|provisioning|live|error|decommissioned`), `contact_name`, `contact_email`, `note`,
`created_on`, `release_id`, `provision_log` (Text, append-only), health cache fields
(`health_state`, `health_checked_at`, `health_detail`), cert fields (`cert_expires_on`,
`cert_state`), `backup_ids`, `meter_ids`. `biz.tenant.backup` (`kind` nightly|manual|final, `path`,
`size`, `taken_at`, `note`). `biz.tenant.domain` (kept, read-only, seeded with the tenant's own
hostname — see the non-goal). `biz.release` (`name` like `2026.09.04-1`, `cut_on`, `notes`,
`module_fingerprint`, `tenant_ids`).

`biz.tenants` **AbstractModel facade** — every RPC starts with `_require_platform_admin()`
(`base.group_system`; this is the platform owner's screen, not a tenant-admin surface). Helpers,
ported with their reasoning:
- `_param(key, default)` on the apex.
- `_pg_cursor(db)` — autocommit psycopg connection for **reads** (**H4-ledger: reads only**).
- `_db_exists(db)`, `_slugs_in_use()`.
- `_tenant_env(db)` — an ORM environment on another database, **commits on success and then calls
  `registry.signal_changes()`** (**F56**, and non-negotiable here: this box is prefork with
  `workers = 2` + gevent, so a write that does not signal is invisible to the other workers — see
  ledger H1).
- `_probe(host)` — HTTPS GET from the box with SNI.
- `_log_line(tenant, text)` — one line, timestamped, appended to `provision_log`; the ONLY record
  of what happened to a customer's database.
- `_human(bytes)`, `_norm_version(v)` (**F8**: normalise the `19.0.` series, compare int tuples).

### 3.3 Provisioning — six steps, resumable, each logged

`PROVISION_STEPS = ('clone', 'configure', 'admin', 'https', 'verify', 'done')`. A tenant carries
the step it reached; the screen offers **Continue** from the first unfinished step and **Undo**
(only while no human has signed in — after that it is Decommission, which is H4b's danger tab
here in a simple form: archive + final backup + drop, with the slug typed to confirm).

1. **clone** — `pg_terminate_backend` on the template (the cron worker connects to it now that
   `db_name` is gone — H3's ledger), then `createdb -O odoo -T carejiox_template <slug>`
   (**`-O odoo` is load-bearing**: H3's runbook found a postgres-owned database looks exactly like
   a routing bug), then copy the filestore directory
   `/odoo/.local/share/Odoo/filestore/carejiox_template` → `…/<slug>` (**F59**: anything touching
   the filestore runs as `odoo` with `HOME=/odoo`). Refuse if the database exists, if the slug is
   reserved, or if free memory is below a floor (read `/proc/meminfo`; the floor is a parameter,
   default 400 MB — the real guard is H4b's).
2. **configure** — through `_tenant_env`: `web.base.url` = `https://<slug>.<apex>`,
   `web.base.url.freeze` = True, `biz_debranding.brand_name` = the tenant's brand (overlay default),
   `biz_access.topbar_mode` = `admin_only` and `topbar_home_xmlids` (§3.8), the `biz_tenancy.*`
   parameters, and **re-enable the crons recorded on the template** in
   `biz_tenants.template_active_crons` — which lives on the **template's own**
   `ir_config_parameter`, not the master's (**F20**), and must be re-read after any upgrade of the
   template because an upgrade switches its crons back on (**F9**).
3. **admin** — the customer's administrator. The template ships `admin` archived and a passwordless
   `platform.recovery@carejiox.com` (H3). This step **creates a new user** (never reuses `admin`):
   name, login (the contact email), a generated password shown ONCE on screen, the tenant-admin
   role granted through `biz.access.grant` so it is audited, and the clinic-administrator group.
   **It must not hold `base.group_system`** — the two-ring rule (memory `project_access_two_ring`,
   ACCESS E3/E6). The role and group come from the overlay (§3.5), resolved by xml-id, never
   hard-coded here.
4. **https** — `sudo /usr/local/bin/biz-tenant-cert <slug>.<apex> <slug>` (H3 installed it and the
   sudoers line). Parse its output; on failure leave the tenant in `error` with the reason and the
   exact command to retry by hand.
5. **verify** — the health probes (§3.4) plus: the site answers 200, the registry loaded with
   **0 skipped modules** (**F7**: skipped = installed-in-the-database − `Registry(db)._init_modules`;
   answer `-1`, never a green 0, when the attribute is missing), the module count matches the
   template's, the Access home has its roles, and the notice bar's poll route answers.
6. **done** — state `live`, stamp the current release, one summary line in the log.

**Rail R1**: every step is a person pressing a button, with a dry run (`preview=True`) that writes
nothing and prints exactly what it would do. **Rail R4** is H4b's (rehearse on a restore) — but the
`verify` step already refuses to mark a tenant live if anything failed.

### 3.4 Fleet, health, backups, in-step, releases

- **Fleet screen**: one row per customer — name, address (a link), state, release, health, size,
  last backup, people with a login. Reads through `_pg_cursor` (SQL), **not** `_tenant_env` — one
  registry load per customer would make a read-only screen the most expensive thing on the box
  (**ACCESS H4**) and on a 2 GB machine it would be the most dangerous too.
- **Health probes** (read-only SQL + one HTTPS probe, cached on the record with a timestamp):
  database size, filestore size, module count, installed-but-not-loaded count, failing crons in the
  last 24 h, last error line for that database in `/var/log/odoo/odoo-server.log` (last ≤ 20 MB of
  the file only — **F27** — timestamps compare as strings because the box and the framework are
  both UTC; keep the logger name, it is the only part that says which piece complained), certificate
  expiry, HTTP status. An **ignore list** parameter `biz_tenants.health_ignore` from the first day
  (**F25**: one noisy line per registry load teaches the owner to click past the gate) — ignored
  lines are still recorded and counted, never deleted.
- **Backups**: `/odoo/backups/tenants/<slug>/<slug>_<kind>_<UTC>.dump` + the filestore tarball;
  `pg_dump -Fc -Z1`; nightly cron keeping the last 14 nightly per customer, manual and final kept
  for ever; **run as `odoo` with `HOME=/odoo`** and **verify the size is plausible** (F59: a backup
  taken with the wrong `HOME` contains no filestore and still says "done" — assert the filestore
  tarball has more than N files and record both sizes).
- **Restore to staging**: `<slug>-staging`, dropped in a `finally` (**F26**: the restore call belongs
  INSIDE the try whose finally drops the copy — a damaged backup must not leave a half-restored
  database on a small box). Refuse if a staging copy already exists.
- **In step with master** — port `sync_rules.py` whole and keep it a **pure function**
  (`sync_split(master_state, tenant_state)`) with its own tests (**R6/F11**). Version-aware
  (**F1/F8**). `update_list()` on the tenant **before** every install (**F3**). After
  `button_immediate_install`, take a **fresh** `_tenant_env` (**F4**). Re-assert the never-list on
  the **literal list about to be written** (**R2**, ACCESS H3) and have a test that proves the
  re-check happens before the install call. Accept exactly three targets: a tenant id, the string
  `template`, or `<slug>-staging` (**F12**). After an install on a tenant, re-seed the access
  catalogue (`biz.access.reseed_catalogue()` — **ACCESS H1**: a catalogue seeded by a
  `post_init_hook` sees only the modules that loaded before it).
- **Releases**: `biz.release` cut from the master's module fingerprint, with notes the owner types.
  Every customer carries a release stamp. A **read-only** nightly cron re-reads every live customer
  and updates the drift figures so the morning screen is honest. **Nothing installs on a schedule,
  ever** — say so on the screen.

### 3.5 `health_tenancy` — the overlay

Registers into `biz_tenants` (server-side registries in `biz_tenants/models/tenants_common.py`,
read at call time — **ACCESS F4** pattern):
- **Brand + addresses**: `register_platform({'brand': 'Viet Uc Care', 'apex': 'carejiox.com',
  'backend_prefix': '/bizapp', 'template_db': 'carejiox_template'})` — every one of them a
  **parameter** with these as defaults (`biz_tenants.brand`, `.apex_domain`, `.backend_prefix`,
  `.template_db`), because the master's own address has already changed once mid-programme.
- **Never-list**: `register_never(('biz_tenants', 'health_tenancy_apex_only'…))` — the modules a
  customer must never receive: **`biz_tenants`** itself, `health_migration`,
  `health_catchment_backfill`, plus the prefix rail `biz_platform*`. **`health_web_leads` cannot be
  excluded** — H3 found `health_learn` and `health_cms_coverage` hard-depend on it, so it is in the
  template. Record that in the report as an owner-visible fact: a new customer gets the web-leads
  screens, inert until someone configures a website connector. Do not try to break the dependency
  in this phase.
- **Meters** (`register_meter(...)`, each `{key, label, unit, sql, table_guard, column_guard}`;
  SQL takes `%(start)s`/`%(end)s`): `patients` "People in care" (`res_partner`, `is_patient AND
  active` — 236 on the master today); `visits` "Visits completed" (`health_fieldservice_order`,
  `state='completed'` in the period); `staff` "Staff with a login" (`res_users`, `active AND NOT
  share` — 73); `invoices` "Invoices issued" (`account_move`, `move_type='out_invoice' AND
  state='posted'` in the period). Every meter **guards on the table and the column existing** and
  answers "not available here" rather than raising. ⚠ **Verify which date column a completed visit
  actually fills** — `actual_end_datetime` gave 0 for this month on the master while 975 orders are
  `completed`; try `scheduled_date`/`booking_date` and use the one that is reliably set, and say in
  the report which you chose and why. A meter that reads 0 on a busy clinic is worse than no meter.
- **The tenant-admin role**: `register_tenant_admin({'role_xmlid': 'health_access.role_owner',
  'group_xmlids': ('health_access.group_clinic_admin',)})`.
- **The home action** the customer's administrator lands on: `health_landing.action_admin_dashboard`
  (verify it opens for the Owner bundle — H2b's T12 proved the CMS root does).
- **Tenant-side**: the ADMIN-section rail item **"About {brand}"** → `biz_tenancy_about`, gated to
  the Owner and Admin roles (`health_access.role_*`), and the master's own ADMIN rail item
  **"Customers"** → the cockpit action, gated to Owner and **only rendered where `biz_tenants` is
  installed** (a rail item whose action does not resolve is a dead door — check the pattern
  `health_cms_coverage` uses for a leaf whose action may be missing, or gate the data file on the
  module and ship it from `biz_tenants` itself; decide and say which).

### 3.6 The cockpit UI

One OWL client action `biz_tenants` (`.bzt-*` CSS, `--bzk-*` tokens, `ic()` icons), views:
`fleet | wizard | detail | sync`. Port `pb_tenants`' shapes and its lessons:
- **F35**: the stylesheet's root blocks — a rule appended after the wrong closing brace compiles to
  nothing and fails silently. Keep each block root-scoped and say in the file which is which.
- **F36**: no `min()` mixing units in SCSS — it kills the whole bundle and the page renders unstyled
  under a red banner.
- **F37**: the kit out-specifies a bare class — a state colour on a kit control needs `.bzk` in
  front of it.
- **F57**: the kit's dialog scrim is `bzk-modal-scrim` (one hyphen); written the BEM way it matches
  nothing and the dialog renders inline with no error. `.bzk-modal__body` carries no padding.
- **F15**: never name a `t-foreach` variable `lt`/`gt`/`amp` — the compiler rewrites it into a
  literal `<` and the whole component dies with a blank screen.
- **F16**: JavaScript built-ins are not in scope inside an OWL template — coerce on the component.
- **F58**: `t-att-x` bound to `true` renders an EMPTY attribute; bind the string.
- **F47**: `useState`'s **return value** is the subscription; `useState(x)` with the result discarded
  watches nothing. Watch a value that only changes when the answer changes.
- **F10**: a keyboard shortcut bound to `window` never fires in this web client — bind `document`
  with `{capture: true}` and bow out for inputs and open dialogs.
The provisioning wizard is the hero (§0): a stepper with live log lines streaming from
`provision_log`, a dry-run toggle, and an end card carrying the address, the administrator's login
and the one-time password with a copy button.

### 3.7 Seams H4b needs (build, do not use)

`biz.tenant.meter` rows written by a snapshot method (H4b meters them monthly); the
`biz_tenancy.features` parameter read by a fail-**closed**-on-parse/open-on-absent helper (**F53**'s
lesson: a fail-open guard that swallows its reason opens a door silently — put the reason in the log
line); `_mail_shell`-style helpers **named for their file** (**F52**: a helper added to a shared
facade is added to every file that shares it — a name collision broke a button two phases old);
`biz_tenants.status_dir` parameter unused for now.

### 3.8 The template gap (found 2026-09-04, close it in this phase)

`carejiox_template` carries `biz_access.topbar_home_xmlids` but **not**
`biz_access.topbar_mode = admin_only` — so a customer cloned today would show every nurse the whole
top bar, the opposite of the owner's decision. Root cause is the **A2** family (a `post_init_hook`
does not fire on `-u`, and a migration does not fire on install). Fix in `health_access` so BOTH
paths set it, add a test that asserts a **fresh** install carries both parameters, deploy the fix to
the master and the template through the wrapper, and prove it on the template with SQL. The
provisioning `configure` step sets them again anyway (belt and braces) — but a template that is
wrong is a template every future customer inherits.

## 4. Order of execution

Rehearse everything on a scratch clone before touching the platform: clone `carejiox` →
`carejiox_h4` (H2b's recipe, and **always `--db-filter=^carejiox_h4$`** on every run — ledger H32:
without it an HttpCase reaches the LIVE database), install the three modules there, run the suite,
Chrome the cockpit through a tunnel, provision a throwaway tenant `h4probe` from the template on
that clone's cockpit, prove the six steps, then drop `h4probe` **and** the clone (**A8**: with
`db_name` gone the cron worker touches every database on the cluster — clone briefly, drop promptly).

Then live, in this order: deploy through `carejiox-deploy` (`-i biz_tenancy,biz_tenants,health_tenancy
-m health_access` for §3.8); upgrade the **template** too (`-D carejiox_template -m health_access -i
biz_tenancy,health_tenancy` — `biz_tenants` never) and **re-record its crons afterwards** (F9);
verify; then provision **`hhh`** with the owner's clinic name (use "HHH Clinic" unless the report
says otherwise) and a contact email the owner can receive — if you do not have one, create the
administrator with the login `owner@hhh.carejiox.com`, hand the password back in the report, and say
plainly that no email was sent because the platform still has no outgoing mail (decision 5).

## 5. Numbered test cases

1. `sync_split` pure tests: names only vs versions (F1/F8 — `1.10.0 > 1.9.0`, the `19.0.` prefix on
   either side), never-list honoured, prefix rail, the three accepted targets (F12), and the
   re-assertion of the never-list on the literal list before the install call.
2. Slug validation: uppercase, underscore, leading digit, over-length, `postgres`, the apex database
   name and the template name are all refused by name; a good slug passes.
3. `_tenant_env` calls `signal_changes()` after its commit (assert on a patched registry — F56).
4. The skipped-modules check answers `-1`, never 0, when `_init_modules` is missing or empty (F7).
5. Parameter reading: a key set to `''` is distinguishable from an absent key (F24); an unset
   Datetime is handled as falsy, not `None` (F23).
6. Meters: each answers on the master; each answers "not available here" against a database missing
   its table/column; the period placeholders bind; the visits meter's date column is the one that is
   actually filled (state your evidence).
7. Provisioning, on the CLONE, against a throwaway slug: dry run writes nothing (prove: the database
   does not exist afterwards); the real run reaches `done`; the log has one line per step; the new
   database's module count equals the template's; **0 skipped**; the administrator holds the Owner
   role and **not** `base.group_system`; `topbar_mode` is `admin_only` on it; the site answers 200.
   Then Undo/decommission removes it and the log says so.
8. Refusals: provisioning an existing slug; provisioning with free memory below the floor
   (patch `/proc/meminfo` reading); `biz_tenants` on the never-list is refused for install onto a
   tenant even if a person names it (R2).
9. Backups: a manual backup writes both files, records both sizes, and a **suspiciously small
   filestore tarball fails the backup** rather than recording it as good (F59). Restore-to-staging
   creates and drops the copy even when the restore raises (F26).
10. Health: the log reader honours the ignore list and still counts ignored lines (F25); a probe on
    a database that does not exist answers "unreachable", never raises.
11. The tenant agent: the poll route answers `jsonrpc` and is readonly; a notice set on the master
    reaches the customer's bar within the poll interval **on a visible tab** (F14 — bring the tab to
    the front before timing anything); the window renders in the reader's clock (F17/F32).
12. §3.8: a **fresh** install of `health_access` on an empty database carries both `topbar_mode` and
    `topbar_home_xmlids`; the live template carries them after the fix (SQL).
13. Neutrality (R11): `biz_tenancy` and `biz_tenants` sources carry no `health_`, `pb_`, `Payobook`,
    `Viet Uc`, `carejiox`, `hhh` or `Odoo` in user-visible copy or imports.
14. Full suites over **every module this phase touches** (F49): `/biz_tenancy,/biz_tenants,
    /health_tenancy,/health_access,/biz_access,/biz_kit,/health_cms_sidebar`.
15. Chrome on the CLONE (`docs/handovers/saas_h4a_shots/clone_*.png`): the fleet screen empty state;
    the wizard's six steps completing with live log lines; the detail screen's four tabs; "In step
    with master" showing the template and the throwaway tenant; a release cut with notes.
16. Chrome on LIVE (`live_*.png`): the cockpit reached from the master's ADMIN rail; **`hhh`
    provisioned end to end** (screenshot each step); `https://hhh.carejiox.com` signs in as its
    administrator and shows the CMS with the health palette and **one** top-bar entry; the About
    screen shows the release; a notice sent from the cockpit appears on `hhh`'s bar and is then
    cleared; `https://hhh.carejiox.com/web/database/manager` → 404; the certificate is trusted.
17. Live health: the master's `/web/login` 200 throughout; memory before/after provisioning `hhh`
    recorded (H3 measured 13.9 MB per database per process, ~42 MB across the three — report what
    a real customer costs); 15-minute error watch clean; no stray `odoo-bin`; the clone dropped.

## 6. Commits (explicit staging, no push)

1. `feat(biz_tenancy): the platform link — release stamp, notices, what's new, the About screen`
2. `feat(biz_tenants): the cockpit — provisioning, fleet, health, backups, in step with master, releases`
3. `feat(health_tenancy): this product's overlay — brand, addresses, never-list, meters, the customer administrator, the doors`
4. `fix(health_access): the top-bar setting must reach a fresh install too` (§3.8)
5. `docs(saas): H4a handover, ledger H61+, runbook update, screenshots`

## 7. Report back

1. **Owner summary (6 lines)** — plus, clearly separated: **`hhh.carejiox.com` is live; its
   administrator's login and one-time password; that no email was sent and why.**
2. Per numbered test with evidence.
3. The `odoo.tests.result` lines; the install/upgrade log ERROR grep.
4. The meter decision (§3.5) — which date column, and the four meters' readings on the master and
   on `hhh`.
5. The provisioning timings per step on live (F33's equivalent: measure, do not guess) and the
   memory a real customer costs.
6. The never-list as registered, and the `health_web_leads` fact in the owner's words.
7. §3.8: what was wrong, the fix, and the proof on the live template.
8. Backups: the paths and both sizes for `hhh`'s first backup.
9. Ledger entries (from H61); commit hashes; clone and throwaway tenant dropped; runbook updated
   with the provisioning procedure as it really runs.
10. Decisions the handover did not cover, and the list of seams H4b will need.
