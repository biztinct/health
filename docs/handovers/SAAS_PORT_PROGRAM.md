# SAAS PORT program — the tenant platform and the Access home, as generic `biz_*` cores in health19

Status: **H0 DONE, H1 DONE, H2a DONE, H2b DONE, H3 DONE 2026-09-04 (live — the box is a
platform: carejiox.com, one database per hostname, self-renewing certificates, a golden
template). H4 next.** Operational documents for what H3 built:
`docs/SAAS_RUNBOOK.md` and `docs/SAAS_RESIZE_RUNBOOK.md`. Spec that started it:
`docs/handovers/PORT_FROM_PAYOBOOK_TENANCY_AND_ACCESS.md` (read it; its §1–§3 are the
inventory of what exists on Payobook and why it cannot be copied verbatim). Payobook's own
programme docs sit in `docs/handovers/from_payobook/` — FLEET_PROGRAM.md (rails R1–R8, ledger
F1–F68), ACCESS_PROGRAM.md (rulings, ledger A–H), the closeouts and the runbook. **Every handover
in this programme cites those by number and starts its own `H-` ledger below.**

Cycle: Fable designs a phase handover → Opus builds, tests, self-reviews, reports → Fable updates
this ledger and designs the next. The owner is asked only for destructive steps on the live
customer database or a genuine scope decision.

---

## Owner decisions (binding, 2026-09-04)

1. **Build the generic modules HERE, as `biz_*`, and do not touch the Payobook repo.** Payobook
   will later adopt these modules and migrate its own data onto them. Consequence: we are free to
   choose clean generic names (models `biz.access.*`, tokens `--bzk-*`, CSS `.bza-*`); nothing in
   health19 may reference a `pb_*` module or a `pb.*` model. The Payobook repo
   (`/Users/adity/Documents/GitHub/gitlocal`, branch 19.1 at ad985bd4) is **read-only source
   material** for this programme.
2. **Apex = VietUcUAT** (52.64.215.106). The master is moving from `care.biztinct.com` to
   **`carejiox.com`**; the first tenant will be **`hhh.carejiox.com`**. Every domain-shaped
   parameter must be a setting, never a literal, because the master's own address changes
   mid-programme.
3. **The sold unit is configurable per plan**: active patients / month, completed visits / month,
   staff users / month, or a flat price by size band. The meter collects ALL counts every time
   (the FLEET P5 ruling generalised) — a **meter registry** with product-supplied SQL.
4. **Retire the Cybrosys `access_roles` app in H2.** Menu hiding (2,488 links) and the
   developer-mode block that its 9 profiles do today are rebuilt natively first; the 9 roles become
   role bundles; `health_user_admin`'s flows move onto the People lens.
5. **Brand name decided later; no outgoing mail yet.** The brand is a setting with the
   `biz_debranding.brand_name` value ("Viet Uc Care") as today's default. Everything that sends
   mail is built and stays dark until an account is connected (cockpit checklist row, red, honest).
6. **Never-list for tenants**: the cockpit itself, demo + migration modules, analytics test data,
   the marketing website. Exact module names fixed in H4's design.
7. **Feature catalogue (10 switches)**: Care Command, Telehealth, Family (portal + messages),
   Telemonitoring + Twin, BHYT claims, Red invoice, Analytics, AI (coding + scribe), Voice, Learn.
8. **Machine resize planned into H3** (runbook + capacity guard; the owner schedules the downtime).
9. Phased workflow confirmed for this stream (do not re-ask).

## Phase map

| Phase | Scope | Status |
|---|---|---|
| **H0 Verify** | §5 checklist of the spec against the live servers | DONE — facts below |
| **H1 Kit + Access core** | `biz_kit` (tokens, primitives, Lucide `ic()`, back chip, soft registry keys) + `biz_access` (roles-as-bundles, 4 lenses, builder, "See it as…", hand-overs) as product-neutral modules with a **rail provider** seam instead of the `pb.sidebar.item` inherit; installed and Chrome-validated on a scratch clone `vietuat_h1`; NOT on the live DB | **DONE** — `SAAS_H1_KIT_ACCESS_CORE.md`; 158 tests green, clone dropped |
| **H2a `health_access` overlay (additive, live)** | cms.sidebar rail provider (bundle lane BESIDE the legacy lane, read as an OR), clinic ability→group catalogue + the 9 roles as bundles with xml-ids, native top-bar hiding + debug block (Rail A), People lens gains "Add a person" and the four person actions, rail item under ADMIN. Nothing uninstalled, nothing removed | **DONE 2026-09-04** — `SAAS_H2A_HEALTH_ACCESS_OVERLAY.md`; 233 tests green, per-user diff **0 lost** on the clone AND on live, deployed to `vietuat` |
| **H2b retire `access_roles` + `health_user_admin`** | re-point every code reference, one gate on the left menu, the JOB as its own field, the clinic-administrator group re-homed, the left menu given the screens only the app bar reached, both apps uninstalled. H16 answered by the owner: **the bar above the screen is the platform administrator's alone** | **DONE 2026-09-04** — `SAAS_H2B_RETIRE_ACCESS_ROLES.md`; both apps uninstalled live, 27 tables dropped, 0 roles lost, 0 job flags changed across 73 colleagues |
| **H3 Server plumbing** | `dbfilter = ^%d$`, carejiox.com apex + wildcard, nginx blocks (`/web/database` 404, `/status`), per-host HTTP-01 certs, golden template DB, scripts + sudoers, backups dir, stale-DB and shadowed-module cleanup, resize runbook | **DONE 2026-09-04** — `SAAS_H3_SERVER_PLUMBING.md`; master renamed `vietuat`→`carejiox` in **26 s** of downtime, certbot repaired (snap 5.8.0, both certs now renewing to 2026-12-03), `odoo` reduced from the `sudo` group to three commands, 4 stale databases + 3 orphan filestores removed, `carejiox_template` built from scratch on the **11th attempt** — which found **13 packaging faults across 10 modules** that no existing database could ever have shown, and one live exposure (the template was answering on the public internet, H54). Template: 187 modules, 0 skipped, 71 crons recorded + disabled, 108 MB, **13.9 MB of memory per extra database per process**. Ledger H36–H54 |
| **H4 `biz_tenancy` + `biz_tenants` + `health_tenancy`** | the tenant agent + the cockpit, parameterised (brand, domain, prefix, never-list, xmlids, meter registry, plan seeds, feature catalogue, status components); pilot tenant `hhh` | may split 4a/4b |
| **H5 Validation** | every FLEET live check re-run on the pilot, Chrome-driven | |

---

## Verified plumbing (H0, 2026-09-04 — do not re-derive)

> ⚠ **H3 CHANGED SEVEN OF THESE FACTS. Read this box before you trust anything below it.**
> The H0 survey is kept verbatim because the ledger cites it, but as of 2026-09-04 the live
> box is different in exactly these ways:
>
> | H0 said | It is now |
> |---|---|
> | `52.64.215.106` | **`54.206.18.111`** (EC2 `i-0fb43cd9281f12945`, `t3.small`, + a 2 GB swapfile). The `VietUcUAT` ssh alias is repointed. |
> | database `vietuat` | **`carejiox`** — plus the golden template `carejiox_template`. |
> | `db_name = vietuat`, `dbfilter = ^vietuat$` | **no `db_name`**, `dbfilter = ^%d$`. The cron worker therefore serves EVERY database (H2 reversed, see H36) and a test run on a clone MUST pass `--db-filter`. |
> | two addons paths, `advanced_pricing` in both | **one path**, `/odoo/odoo-server/addons`. `/odoo/custom/addons` is gone. |
> | `vietuat-deploy` | **`carejiox-deploy`**, with a new `-D <db>`. The old name is a symlink for one phase. |
> | `care.biztinct.com`, no wildcard, `/web/database/manager` answers 200 | **`carejiox.com`** (+ `www`), `*.carejiox.com` wildcard block, the old host 301s, `/web/database/` is **404 on every hostname**, `/status` is served from disk, and an unclaimed hostname gets `444`. |
> | `odoo` has `(ALL : ALL) ALL` | three commands, `/etc/sudoers.d/biz-tenants`. It is out of the `sudo` group. |
>
> Also gone: the stale databases `bi_test`, `care`, `care_biztinct`, `vietuc_uat` and the orphan
> filestores `gc3_ci_probe`, `vietuat_h1`, `vietuat_h2`. Operational detail lives in
> `docs/SAAS_RUNBOOK.md`, which is the document to hand somebody who has to run this.

### The box and the service
- `VietUcUAT` (ssh alias; 52.64.215.106, user ubuntu). **1.9 GB RAM, 2 cores, 58 GB disk 24 % used.**
  Ubuntu, PostgreSQL 16 (`shared_buffers` 128 MB, `max_connections` 100).
- Odoo 19 at **`ac6d4f02` (2025-12-03)** in `/odoo/odoo-server` — OLDER than Payobook's `db2cd8c1`
  (2026-06-16). Every FLEET line-number citation into `odoo/http.py`, `ir_http.py`,
  `loading.py` must be re-found here. Confirmed present on this build: `res.groups.all_implied_ids`
  / `all_implied_by_ids` / `all_user_ids` / `privilege_id` (`odoo/addons/base/models/res_groups.py`
  :18–77), `web/models/ir_http.py` `_handle_debug` :46, `_pre_dispatch` :57, `session_info` :79
  (debug at :133/:193), `odoo/http.py` `default_mode = …readonly…` :924, `loading.py`
  `pre_init_hook` :174 / `post_init_hook` :233.
- `/etc/odoo-server.conf`: `workers = 2` (**prefork, not threaded** — Payobook is threaded; every
  registry is loaded per worker, so memory per tenant is ×3 with the gevent process), `db_name =
  vietuat`, `dbfilter = ^vietuat$`, `list_db = False`, `proxy_mode = True`, `logfile =
  /var/log/odoo/odoo-server.log`, `limit_time_real 300`, `limit_memory_soft 600 MB / hard 1.6 GB`,
  `max_cron_threads = 1`, **no `data_dir`** → filestore `/odoo/.local/share/Odoo/filestore/<db>`
  (`vietuat` = 924 MB; F59 applies: `HOME=/odoo` for anything touching attachments).
  **Two addons paths**: `/odoo/odoo-server/addons,/odoo/custom/addons`; `advanced_pricing` exists in
  BOTH (shadowed — H3 cleans it).
- Service: `odoo-server` (LSB script). **Never `systemctl restart`, never `pkill -f odoo-bin`**;
  live upgrades go through `vietuat-deploy` (flock wrapper, `/usr/local/bin/vietuat-deploy`, source
  `.agent/workflows/vietuat-deploy.sh`). Test runs: `--workers=0`, a spare `--http-port`, your own
  `--logfile` (HANDOVER-CONVENTIONS §2). Because `db_name` is set, **the live cron worker only
  serves `vietuat`** — a scratch clone gets no crons (A8 does not bite here; verify once).
- Databases: `vietuat` 260 MB (live, 204 modules, 74 active users) + stale `bi_test`, `care`,
  `care_biztinct`, `vietuc_uat` (+ orphan filestore `gc3_ci_probe`). 67 health_/biz_ modules on disk.
- nginx: `sites-enabled/_` (port 80 catch-all, `server_name _`) + `care.biztinct.com` (443, HTTP-01
  cert by certbot timer, expires 2026-09-25, `/longpolling` → 8072). **`/web/database/manager`
  answers 200** (renders the form, body says disabled) — H3 404s it like Payobook. No `/status`,
  no `/var/www/*-status`, no `/odoo/backups`, no sudoers scripts. `/odoo` → 301 `/bizapp`.
- DNS: `care.biztinct.com` → 52.64.215.106; no wildcard; `vafhs.com` resolves to nothing;
  `carejiox.com` not yet pointed (owner's move).
- Mail: **zero `ir_mail_server` rows, 1,034 `mail_mail` in `exception`**, no `mail.default.from`.
  `web.base.url` = https://care.biztinct.com. `biz_debranding.brand_name` = "Viet Uc Care".

### Access on the live database
- `access.role` (Cybrosys): Owner (6 users, 25 groups), Operations Manager (1, 25), Branch Manager
  (1, 2), Banker (0, 1), Nurse (44, 8), Doctor (10, 2), Accountant (1, 12), Admin (2, 2), CRM (2, 7);
  6 active internal users with no role. `is_privileged` false on all (health_user_admin adds it).
- Rail: **79 of 80 active `cms.sidebar.item` gated** via `access_role_cms_sidebar_item_rel`
  (columns `access_role_id`, `cms_sidebar_item_id`); 1 of 7 sections gated (ADMIN → Owner) via
  `cms_sidebar_section_role_rel(section_id, role_id)`. Sub-items inherit through
  `effective_role_ids` (`health_cms_sidebar/models/cms_sidebar_item.py:62–91`); the visibility rule
  is inline in `get_sidebar_data` :177–210 (admin = `access_roles.access_role_group_administrator`
  sees all; a user with a role sees ungated items + items whose effective roles include it; a user
  without a role sees ungated items only). **No permission-group lane, no `restricted` teaser.**
- **9 `role.management` profiles** (Payobook had 0): 2,488 rows in `ir_ui_menu_role_management_rel`
  (menu hides), `is_debug` on 7 profiles, `is_chatter` on 2; 0 domain rules, 0 field access.
- `base.group_system` = **ash@biztinct.com only**. `health_user_admin.group_health_user_admin` 9
  holders (owner, om, vijay, trainer, ahanoi, ahcmc, dung, qa_catch_owner, qa_catch_staff).
  `access_roles.access_role_group_administrator` 7 holders (ash, minh.nv, vijay, trainer, dung,
  qa_catch_owner, qa_catch_staff).
- `access_roles` dependents (manifests): health_base, health_cms_sidebar, health_field_requirements,
  health_learn, health_user_admin, health_web_leads, biz_bi_cms. 69 code references; the heavy ones
  are `health_user_admin/models/*` (wizard + saas guards), `health_base/migrations/19.0.1.3.8`,
  `biz_bi_cms/hooks.py`, `health_cms_coverage/hooks.py`.

### Repo seams (health19, branch 19.0)
- Backend prefix `/bizapp` (`biz_deroute/biz_deroute_stage/controllers/home.py:8–9`) — same as Payobook.
- Web client: only `health_fieldservice/static/src/xml/ops_webclient_patch.xml` replaces
  `//ActionContainer`; `health_learn/static/src/coach/coach_patch.xml` anchors after
  `//MainComponentsContainer`; **`//NavBar` is untouched** → the tenant banner mounts after it (F18).
- The rail: `health_cms_sidebar` — `cms.sidebar.section` (name translate, technical_key, sequence,
  icon FontAwesome class, active, color, role_ids) and `cms.sidebar.item` (name translate,
  section_id, parent_id, sequence, icon `fa fa-*`, action_xmlid/action_tag, role_ids,
  effective_role_ids, active, match_*). JS `cms_sidebar.js` calls `orm.call("cms.sidebar.item",
  "get_sidebar_data")` once per load and listens to `ACTION_MANAGER:UI-UPDATED` only — **no reload
  bus event exists yet** (H2 adds one, D7 pattern). Rail data files are `noupdate="1"`
  (`cms_sidebar_items_*.xml`, section `section_admin` etc.) — the opposite of Payobook's C2.
- Admin surface: `health_landing` "Admin" tab strip with the soft registry
  `registry.category("health_landing.admin_tabs")` (`admin_model_navigator.js:21–29`); the rail
  item "Users & Roles" is `health_cms_sidebar.item_admin_users` → `health_landing.action_admin_users`.
- Theme: `health_theme` — `primary_variables.scss` (`$vu-*`, primary deep blue `#1565C0`),
  `vu_tokens.scss` (`--vuf-*` on `:root`, derived from `--vu-brand-primary` with fallbacks),
  Lucide via CSS-mask (`vu_icons.scss`, `/health_theme/static/src/img/lucide/*.svg`). No inline-SVG
  `ic()` registry exists. Mono colours only, no gradients (owner rule).
- Tests: `odoo.tests` classes per module; HttpCase needs `--workers=0` AND no `--no-http`
  (reference_httpcase memory). Results: `grep -a "odoo.tests.result" <logfile>`.

---

## Rails (carry over from FLEET R1–R8, plus this programme's)

- R1–R8 verbatim (FLEET_PROGRAM.md). **R2's list is decision 6 above.**
- **R9 Nothing on the live customer database without a phase report and, for anything
  destructive or irreversible, the owner's word.** H1 and H2 build on a scratch clone first.
- **R10 The Payobook repo is never written to.** Copy, adapt, credit by number.
- **R11 Generic cores seed nothing product-specific and import nothing product-specific.** A test in
  every `biz_*` module reads its own sources and fails on "Payobook", "Viet Uc", "health_", "pb_"
  in user-facing copy or imports.
- **R12 White-label.** "Odoo" never in a user-visible string (F43's test pattern); technical ids untouched.
- **R13 Plain English to the owner.** Handovers and commits carry the engineering vocabulary; the
  report's summary section is in the screen's words.

## Design bar (verbatim, binding on every phase)

**"Extreme WOW, intuitive, out-of-this-world experience, best in class."** Not "clean and
functional" — the screen should make someone stop. Every phase must state and satisfy:
- a **hero moment** (a live preview, a diff that animates in, a grid that feels like a spreadsheet,
  a single reassuring sentence in plain language) — name it in the design;
- **zero dead-ends**: every state (empty, loading, error, partial, huge) is designed, every failure
  names its reason and its next step;
- **plain-language over code vocabulary** on every label, toast and summary;
- **motion with purpose** (enter/exit, progress, state change) — never decorative jitter;
- **keyboard + bulk ergonomics** where rows are involved (multi-select, shift-range, paste, undo);
- measured against the best consumer/SaaS tool in that category (Vercel, Linear, Stripe
  dashboards), not against stock Odoo.
Palette/tokens: `--bzk-*` (biz_kit), tinted by the product through `--bzk-brand-*`; promoted
semantics only; never invent a hex. Lucide icons via `ic()`; no emoji, no gradients, no FontAwesome
in new surfaces. Chrome validation mandatory before a phase reports done.

---

## Ledger (H-numbers — every phase appends; gotchas AND rulings)

- **H1** (H0, 2026-09-04) The live box is **prefork (`workers = 2`)**, not threaded like Payobook.
  F56 (`signal_changes` after a cross-DB commit) is not optional here — it is the only way a
  second worker learns about a write — and the capacity arithmetic (F34) must multiply the
  per-tenant registry cost by the number of processes that will load it (2 workers + gevent).
- **H2** (H0) `db_name = vietuat` in the conf means the cron worker touches only that database:
  a scratch clone is cron-free without any of Payobook's A8 hygiene. The moment H3 removes
  `db_name` for `^%d$` routing, every database on the cluster becomes a cron target and A8/R8
  bite in full.
- **H3** (H0) Two addons paths with one module (`advanced_pricing`) in both. Odoo takes the first
  path's copy; the second is dead weight that will confuse a "tree hashes repo↔server" check.
  Removed in H3, never depended on.
- **H4** (H0) The rail here is the inverse of Payobook's: gates are `access.role` rows (a
  third-party model), data files are `noupdate="1"` (an upgrade re-asserts NOTHING, so a gate
  written into XML does not reach a live DB — the reverse of C2), and there is no permission-group
  lane and no locked teaser. The rail provider seam (H1) has to describe the rail as it is, not as
  Payobook's was.
- **H5** (H0) The Cybrosys app is load-bearing on this DB: 2,488 menu hides and a debug flag on 7
  of 9 profiles. Payobook's retirement recipe (ACCESS P6) assumed zero rows; here the retirement
  must first reproduce those two effects natively and prove per user that no menu that was hidden
  becomes visible (the D10 per-user diff, but on `ir.ui.menu` visibility, not the rail).
- **H6** (H1, 2026-09-04) **The rail provider seam, as built.** `biz_access` inherits no menu
  model. `access_common` declares `RailProvider` (a plain class, not a model), `register_rail()` /
  `rail_provider()` hold the ONE registration, and `biz.access.rail` (AbstractModel) is the only
  thing the facade talks to. Every provider method takes `env` as an argument rather than reading
  one off `self`, because a single provider instance serves every database the registry is loaded
  for — an adapter that remembered an environment answers the wrong tenant's question on the
  second database. With nothing registered every read answers empty and every write raises
  `UserError("This system has no left menu the Access home can edit.")`; a silent no-op there
  would report success on a screen where success means "the gate has changed". Protocol as
  shipped: `available / sections / entries / visibility_for / advanced_action / reload_event /
  set_roles / set_active / set_restricted / reorder`. H2's `cms.sidebar` provider codes against it.
- **H7** (H1) **`rail_state(entry, is_admin, held_group_ids, role_groups)` is the whole visibility
  rule, as a pure function**, in `access_common`. The role lane is an ALL (a bundle is a job, not a
  shopping list); the permission lane is an ANY; the FIRST branch counts roles that are WRITTEN,
  not roles that are active, which is what stops archiving the last role on an entry handing it to
  the whole company. `role_groups` holds ACTIVE roles only, so an archived role opens nothing. A
  provider whose product has no rule of its own builds `visibility_for` from it, and the test
  suite's fake provider does exactly that — so the no-drift proofs are proofs about the code the
  product will run, not about a copy written to agree.
- **H8** (H1) **The brand indirection, and the one hole in it that had to be found by hand.** Every
  BRAND token in `bzk-root-vars` is `var(--bzk-brand-X, <default>)`; `health_theme/…/bzk_brand.scss`
  declares the nine `--bzk-brand-*` properties and nothing else, so it is inert without `biz_kit`.
  The hole: `access.scss` re-declares the kit tokens ON THE MODAL SCRIM (a dialog mounts outside
  its opener as often as inside), and those re-declarations were LITERALS — the home in the
  product's colours and its dialogs in the kit's defaults. Every re-declaration of a brand token,
  anywhere, must itself read `var(--bzk-brand-*)`. A `test_static` case now fails on any rule that
  paints a brand colour from the Sass variable.
- **H9** (H1) **Two assertions in the ported suite were data-dependent and only passed on
  Payobook's data.** (a) The People lens sorts with `fold()` (accents folded) and the test re-sorted
  with `.lower()`; on a database of Đặng and Đào that is a different order, and the test was
  demanding the very behaviour the accent-folding test two methods below forbids. (b) Two tests
  asserted a bare user holds ZERO roles — true only where no role is satisfied by a plain login,
  which is exactly the role H2 is about to write. Both now assert the property that actually
  matters (the same folding; a count that MOVES against a bare colleague) rather than a number that
  happens to be right on one database.
- **H10** (H1) **`base.group_system` does not imply the access-team permission, by design — and
  that bites the first administrator who opens the plain forms.** The facade lets an administrator
  through (`_is_admin()` short-circuits every gate) and reads the catalogue with `sudo()`, so the
  Access home works; but `ir.model.access` still refuses `create` on `biz.access.ability` to
  anybody outside `biz_access.group_access_manager`. An administrator can therefore use the home
  and cannot add an ability on its plain form. Deliberate (no `implied_ids` from any application
  group in either direction) but surprising; H2 should put the access team on the clinic's own
  admin tier via `register_manager_groups`.
- **H11** (H1) **Payobook's kit carries two product-specific rules that must never be ported.**
  `import_kit.scss` reserves 236px/168px of page padding for pb_learn's FAB and PayAI's pill via
  `body:has(.lrn-coachhost)` — selectors for hosts that do not exist here. Dropped. `kit.scss` is
  now the primitives and nothing else, plus the back chip's own root-scoped block.
- **H12** (H1) **The copy audit's net was too narrow, and a browser found what it missed.** The
  ported strings passed a scan for product NAMES and still said "Payroll auditor", "Read every pay
  run and payslip" and "give Mai the payroll thing" on screen — one industry's vocabulary is as
  wrong in a generic core as one product's name. `test_access_generic` now also scans every
  user-facing string for `payroll` / `pay run` / `payslip`. Lesson for H2 and H4: the neutrality
  test has to name the WORDS, not just the products.
- **H13** (H1) **`systemd-run` as `sudo -u odoo` fails with "Interactive authentication required".**
  The working form on this box is `sudo systemd-run --unit=… --uid=odoo --setenv=HOME=/odoo …`.
  Worth writing down because the failure looks like a permissions problem with the unit rather than
  with who is asking for it.
- **H14** (H2a, 2026-09-04) **"A role with an empty top-bar list has no opinion" is the wrong
  reading, and only real data says so.** The rule reconciles two roles by INTERSECTION so that
  holding more never shows less; the first version left a role with an empty list OUT of that
  intersection, on the argument that "was never asked" is not "hides nothing". On the clinic's own
  74 people that took **489 top-bar screens off one doctor**: their own job hides nothing, they
  happen to carry the single permission that makes them a branch manager, and the reading that
  ignored the first let the second decide. An absent profile in the OLD app is a POSITIVE fact —
  doctors here see the whole bar — so carrying it as "no opinion" loses it. Now an empty list is
  read as "hides nothing" and takes the intersection with it: the promise becomes exact, and the
  only cost is in the safe direction. **Neither reading was findable without the per-user diff on
  real data** — the synthetic tests passed both.
- **H15** (H2a) **Emptying `request.session.debug` does not close the sign-in page.** Payobook's E1b
  said there was a second seam; this build's is exact: `web_login` builds its template values from a
  QUERY-STRING whitelist (`SIGN_UP_REQUEST_PARAMS`, which contains `debug`), so the
  "Log in as superuser" button renders from the address bar and never reads the session at all. The
  session was correctly cleared and the button came back anyway. Closed in
  `ir.qweb._prepare_environment`, which uses `setdefault` — which is exactly why the controller's
  copy wins — by forcing the template's `debug` back into step with the session. One rule, two
  seams. Found by running it; no amount of reading `_handle_debug` would have shown it.
- **H16** (H2a) ⚠ **OWNER DECISION, BLOCKING H2b.** With the old app retired, the top bar is decided
  by held roles alone — and every Owner, Operations Manager and Branch Manager holds the Doctor and
  Admin jobs, which hide nothing. The forecast in `saas_h2_shots/migration_diff_live.md` says they
  would go from a tidy 68–202 screens to **564–624**, i.e. the whole technical menu (Settings →
  Technical, Apps, every app root). Nurses/Accountant/CRM are unaffected. Two ways out, and only the
  owner can choose: (a) give the Owner, Operations Manager, Doctor and Admin roles their own
  top-bar lists before H2b, or (b) accept that senior staff see the whole bar. Nothing about this
  is live today — both engines run, so the old app still hides their menus.
- **H17** (H2a) **A test fixture may borrow a process-wide registration; it may never decide what
  was in it.** `FakeRailMixin` cleaned up with `register_rail(None)` — correct on a database where
  `biz_access` is the only thing installed, and silently wrong the moment a product registers a real
  provider at import time. The first fake-rail test in the run took the clinic's menu away for the
  rest of the process, and the symptom was a dozen failures in a DIFFERENT module ("no left menu is
  registered"). It now restores the previous provider. Same class of bug as H9: a fixture that was
  right about the world it was written in.
- **H18** (H2a) **The Access home counts who HOLDS a role, not who was ASSIGNED it, and the two
  numbers differ a lot.** H0's table (Owner 6, Nurse 44, Doctor 10) counts `access_role_id`
  assignments; the board counts people who hold every permission in the bundle, transitively —
  Owner 8, Nurse 54, Doctor 20 on live. Both are right. Any later phase quoting a holder count must
  say which question it asked, and a test asserting one of them on real data is a test that will
  break (H9 again).
- **H19** (H2a) **The clinic's left menu gates nothing to Nurse, Doctor or Banker.** All 79 gated
  entries name Owner (50), Admin (41), Operations Manager (18), Accountant (15), CRM (9) or Branch
  Manager (2). So the Nurse card's "opens on the left menu" column is honestly empty, and the 44
  nurses see the 13 ungated entries and nothing else. Not a defect — the data has always said this —
  but it is why the rail lens looks emptier for clinical roles than anybody expects.
- **H20** (H2a) **The older "Create User" wizard is already broken on this database.**
  `health_user_admin`'s wizard writes `hr.employee.employment_type`, a Selection that was replaced by
  the `employment_type_id` lookup pointer; the field no longer exists, so the form fails on both
  render and save. H2a's replacement reads the lookup list with `sudo()` and stores the CODE rather
  than a pointer — the reference lists are readable only by people who maintain them, and somebody
  whose job is adding colleagues is not one of them. Same constraint still applies to the area and
  facility pickers (pre-existing, unchanged): a person holding ONLY the Admin role cannot use them.
- **H22** (H2b, 2026-09-04) ⚠ **A FIELD CANNOT MOVE UP THE DEPENDENCY TREE IF ANYTHING BELOW IT
  NAMES THE FIELD IN AN `@api.depends`.** The plan was to move `is_doctor_role` and its three
  companions out of `health_base` (which may not depend on the Access home) and into
  `health_access`, keeping the names so the sixty-odd readers would not notice. The database
  refused to load at all: `health_fieldservice` names `is_doctor_role` in an `@api.depends`, and a
  dependency is resolved when THAT module's models are set up — before anything above it has been
  imported. `ValueError: Dependency field 'is_doctor_role' not found in model hr.employee`, and the
  whole registry dies. **The shape that works is DECLARE LOW, COMPUTE HIGH**: `health_base` declares
  the four as plain stored fields with no compute, `health_access` re-declares them with the compute
  and the `depends`. Both statements merge, everything below can name them, and a database without
  the overlay simply never computes them. A plain read (`emp.is_doctor_role` in Python) would have
  been fine; it is the DECLARED dependency that has to exist at setup time.
- **H23** (H2b) **An XML update writes only the fields it names, so a view that stops being an
  inherit has to say so out loud.** `health_landing.view_admin_users_list` was an inherit of a view
  in the module being deleted, and was rewritten as a standalone list. The file simply dropped
  `inherit_id` — and the loader refused it: the live row still carried the old parent, so Odoo saw
  an inheriting view whose arch was a whole `<list>`. `<field name="inherit_id" eval="False"/>` is
  the fix, and it is the same rule the rail's `parent_id eval="False"` already lives by (§5.69b).
  Anything an update must CLEAR has to be named with an explicit false.
- **H24** (H2b) **Classification and permission were one field, and separating them is the whole
  phase.** `res.users.access_role_id` answered both "what may this person open" and "what IS this
  person" — the roster, the staff pickers and the dashboards all read `is_doctor_role` off it.
  Bundles cannot answer the second: every Owner holds the Doctor bundle. So the job became its own
  field (`job_role_id`, label "Job"; "Employed as" on the staff record, where `job_id` already owns
  the word), the four derived fields KEPT THEIR NAMES and recompute from
  `job_role_id.clinical_kind`, and the old substring rule (`'doctor' in name`) was applied ONCE by
  the migration and then never again. Writing the job grants the role — the arrow points one way,
  and granting a role on the Access home changes nobody's job.
- **H25** (H2b) **`_visible_menu_ids` in administrator-only mode needs a floor, and the floor is the
  interesting part.** The rule is `super() ∩ {the named home roots}`, which is trivial; what it
  costs to get right is every way the intersection can come out empty — the setting cleared, the
  setting naming a menu this person cannot see, the setting naming something that is not a menu at
  all. Each of those would sign a colleague in to a blank bar. The rule keeps the first root they
  could have seen anyway and logs a warning naming the parameter. And the setting is read with F24's
  `search`-the-row, never `get_param`, because "deliberately empty" and "not set" mean different
  things here and `get_param` cannot tell them apart.
- **H26** (H2b) **A permission group disappears with its module, so a tier has to be re-homed before
  the module goes, not after.** `health_user_admin.group_health_user_admin` had nine holders and was
  named in twenty-two places across four other modules (ACL rows, `groups=` on buttons, tests).
  `health_access.group_clinic_admin` is the same tier under a name this programme owns: the
  migration puts every holder into it and re-points the `user-admin` ABILITY at it, which is the one
  write that moves nine role bundles at once (`group_ids` is computed from the abilities). Nobody is
  removed from the old group — it is about to be deleted with its module, and removing people from
  it first is work with no effect and one more thing to get wrong.
- **H27** (H2b) **Hiding the application bar is only safe if somebody first counts what it was the
  only way into.** Nine applications' screens were reachable through the bar and nowhere else:
  Analytics' eleven technical children, Zalo's three, VoIP's six, two workflow queues, Training's
  five author screens, Care Command's audit/messages/watchlist, Employee Development and Coaching.
  They ship as left-menu entries in the module that OWNS them (`biz_bi_cms` for Analytics,
  `health_access` for the rest, whose `action_xmlid` is a plain string and needs no dependency), and
  the hook SWITCHES OFF any entry whose action does not resolve on this database. An entry that
  opens nothing is a dead end, and a dead end is worse than an absence.
- **H28** (H2b) **The menu's highlight index is last-wins, so giving a screen its own entry means
  taking it off whatever was standing in for it.** "Channels (setup)" answered for the channel
  message store and the ops audit while neither had a door of its own. Both have one now, and
  leaving them declared on the borrower would light up the wrong entry on click. The migration trims
  them; the same trap is why `health_cms_coverage` never re-homes a match target twice.
- **H29** (H2b) ⚠ **ADDING AN ABILITY TO A ROLE MAKES THE ROLE BIGGER, AND HOLDING A ROLE MEANS
  HOLDING ALL OF IT — so a role that grows can drop the people already in it.** "Build reports"
  joined four bundles; everybody without the reporting permission instantly stopped HOLDING those
  bundles and lost every left-menu entry they opened. On the clinic that was one doctor who carries
  the branch-manager permission by accident of history: two entries gone and the role gone with
  them, found by the per-user diff and by nothing else. The first fix tried to grant the permission
  to `role.holders()` AFTER adding the ability — which is empty of exactly the people who needed
  it. The shape that works computes the audience from the role WITHOUT the new ability, which also
  makes the step self-repairing on a database where the ability was added and the grant was not.
  **Any phase that widens a bundle has to grant the new part to whoever held the old one first.**
- **H30** (H2b) **A door on a menu is not the same as permission to walk through it, and the only
  honest way to know is to ask the permissions table.** Putting the screens the application bar used
  to be the only way into onto the left menu produced **34 dead ends** on the first pass: entries
  gated to roles that would be shown them and then refused the data (Zalo's three, VoIP's six,
  three reporting-configuration screens, and one PRE-EXISTING mis-gate — Voice Notes was offered to
  a branch manager who cannot read `health.scribe.job`, and had been since it shipped). The gate is
  now NARROWED to the roles that can read the model behind the action, and an entry no role can open
  is switched OFF, both re-decided on every run so a later permission grant puts the door back. A
  dead end is worse than an absence, and 34 of them would have shipped on eyeballing alone.
- **H31** (H2b) **A record rule attached to a GROUP is ORed with every other group rule, so a rule
  that hides something can be silently defeated by a broader rule on a group the same people hold.**
  The retired application's "a clinic administrator does not see the platform administrator" rule
  has been inert on this database since the catchment work: the tier implies
  `health_base.group_healthcare_admin`, which carries `[(1,'=',1)]` on `res.users`. The rule was
  carried across unchanged (it is right, and it will work the day the catchment rule is narrowed),
  and the test asserts the rule's PRESENCE rather than an effect that was never there. Pre-existing;
  worth a ticket, not a phase.
- **H32** (H2b) **A test suite run without `--db-filter` on this box tests the LIVE database.**
  `dbfilter = ^vietuat$` in the conf means every HttpCase request from a run on a clone resolves to
  `vietuat`, whose schema does not have the clone's new columns: 76 failures that were all one
  routing mistake, and a registry for the live database loaded inside the test process. Nothing was
  written and the live tree was never touched, but the lesson is a rail: **every test run against a
  clone passes `--db-filter=^<clone>$`.** And the only way to know which failures are yours is a
  BASELINE run of the same tags on an untouched clone — 25 failed / 10 errors of 810 here, before a
  line of this phase was applied.
- **H33** (H2b live, 2026-09-04) **The rehearsal predicted the live run exactly, to the row.** Same
  migration counts (2 abilities, 3 roles classified, 68 jobs, 9 administrators moved, 4 roles given
  "build reports" and `dhanoi` the permission behind it, 10 entries gated, 11 switched off), same
  uninstall measurements (1110→1083 tables, 260 external ids to zero, four orphan settings rows,
  zero orphaned views/crons/menus), and the same two people in the before/after diff. **That is what
  a rehearsal on a full clone of the real database buys**, and it is why the clone is dumped from
  the live database rather than from a template: the numbers that mattered here — 68, 9, 1, 46 —
  are all facts about this clinic's data, and not one of them could have been predicted from code.
- **H34** (H2b live) **`vietuat-deploy` gained `-x <script>`, because the recipe for the one thing
  it could not do was "call `service odoo-server` by hand".** Uninstalling a module rewrites the
  registry underneath every worker, so it has to run with the service down — and every runbook that
  said so was teaching people to reach past the wrapper. `-x` runs a python file in `odoo-bin shell`
  inside the wrapper's own lock, with the service stopped and started by the wrapper, after any
  `-m`/`-i` upgrade in the same call and SKIPPED if that upgrade failed. Its stdout is shown rather
  than swallowed. **A rule that has to be broken "just this once" is a rule that will be broken
  twice**; the fix is to give the wrapper the missing verb.
- **H35** (H2b live) **Two facts about this box that a live check has to plan around.** The public
  host was unreachable from the operator's machine while being perfectly healthy from the server
  (`curl` from inside: 200 over HTTPS through nginx; from outside: connection timed out) — so the
  Chrome validation ran over an SSH tunnel to 8069, which is the same live database and the same
  registry, and the report says so rather than claiming a check it did not make. And `dbfilter =
  ^vietuat$` means a tunnel to 8069 resolves to the live database with no extra argument, which is
  convenient here and is the same fact that made H32 dangerous on a clone.
- **H21** (H2a) **The top-bar override costs nothing measurable.** Measured on the clone over six
  real users: `_visible_menu_ids` 12–57 ms with the rule and 14–60 ms without (the difference is
  inside the noise), `load_menus` 25–57 ms end to end. The `ormcache` on the permission set plus the
  framework's own `load_menus` cache is enough; no extra caching was added, and none is warranted.
- **H36** (H3, 2026-09-04) ⚠ **REMOVING `db_name` HANDS EVERY DATABASE ON THE CLUSTER TO THE CRON
  WORKER, AND THE ORDER OF H3's OWN STEPS HAD TO CHANGE BECAUSE OF IT.** `cron_database_list()` is
  literally `config['db_name'] or list_dbs(True)` (`odoo/service/server.py:110`), so the moment the
  conf line goes, the one cron thread enumerates `pg_database`. The handover ran the rename (§4.4)
  before the stale-database cleanup (§4.5); done in that order, five databases become cron targets
  on a 1.9 GB box for the length of the gap. **The cleanup was moved BEFORE the rename** so that
  exactly one database existed at the moment `db_name` disappeared. Nothing about the work changed,
  only when it happened — and the reordering is the kind a phase should make, because it removes a
  risk rather than adding scope. The mitigating detail, worth knowing before anybody panics about
  a half-built template: `IrCron._process_jobs` opens a PLAIN cursor first, checks the base version,
  and returns before touching a `Registry` if no job is due — and `_check_modules_state` raises
  `BadModuleState` while any module is mid-install. A database being built is therefore skipped with
  a warning and costs no memory. The window that matters is the one AFTER the build finishes, which
  is why the crons are switched off in the same run.
- **H37** (H3) **This build does NOT honour `X-Odoo-dbfilter`, so custom domains are not a feature
  yet — and the script that would attach one now refuses.** `db_filter()` (`odoo/http.py:379–408`)
  reads only `config['dbfilter']` and the Host header. The one request header the build does look at
  is `X-Odoo-Database` (`http.py:1780`), and it is checked THROUGH `db_filter()` and sets
  `session.can_save = False` — so it cannot pin a client-owned domain either, in the one direction
  that matters. `biz-domain-attach` therefore exits 3 with the reason and a `CUSTOM_DOMAIN_PINNING`
  switch in `/etc/biz-tenants.conf`, rather than writing a block that would route
  `clinic.example.com` to a database called `clinic`. **A tool that silently does nothing is worse
  than a tool that says no**, and this is the whole difference between the two.
- **H38** (H3) **A server-level `return 301` swallows the certificate renewal, and that is how a
  redirect quietly stops being trusted.** nginx runs a `server`-level `return` in the server rewrite
  phase, which is BEFORE it picks a location — so the `/.well-known/acme-challenge/` location
  certbot inserts at renewal never runs, and about seventy days later every visitor to the old
  address gets a browser warning instead of a redirect. Payobook's blocks are shaped this way and
  have never had to renew a redirect-only host. Every redirect on this box now lives inside
  `location / { return 301 ...; }`, and the proof is a `certbot renew --dry-run` re-run AFTER
  `care.biztinct.com` became a pure redirect: both certificates still simulate green.
- **H39** (H3) **nginx here is 1.18: `http2 on;` is a 1.25 directive and fails `nginx -t`.** Cheap
  to fix, worth writing down because the failure mode is the good one — `nginx -t` refused, so the
  reload never happened and the previous config stayed live. Every generated block uses
  `listen 443 ssl http2;`. The same run proved the other half of that discipline: `nginx -t &&
  systemctl reload` is not synchronous, and a curl fired immediately after a successful reload can
  still be answered by the old workers. Two failed assertions were the reload lag, not the config.
- **H40** (H3) ⚠ **`noupdate="1"` HIDES A WHOLE CLASS OF BREAKAGE UNTIL SOMEBODY INSTALLS FROM
  NOTHING.** The dropdown-vocabularies work (Tier 1) replaced 24 Selection fields with many2one
  pointers and never rewrote the seed data: **182 `<field>` elements across 15 files, 20 distinct
  (model, field) pairs in 4 modules**, all naming columns that no longer exist. Every one of those
  files is `noupdate="1"`, so on any database where the records already existed they are never
  written again and the dead name is never evaluated. A fresh install writes them for the first time
  and dies on the first one (`ValueError: Invalid field 'category' in 'health.symptom'`).
  **The golden template is the first thing in this product's history to install it from nothing, and
  it found this in its second build.** Two lessons, and the second is the reusable one: (a) the fix
  came from `lookup_registry.CONVERSIONS`, which is the authoritative map — nothing was guessed;
  (b) the faults were then found ALL AT ONCE by walking every `<record model=…><field name=…>` in
  all 1,107 xml data files of the module set against the live registry, instead of one failed
  60-second build per fault. **Any phase that installs a product from scratch should run that sweep
  first**; it is twenty lines and it turned an unknown number of build cycles into one.
- **H41** (H3) **The same asymmetry again, one layer down: code that only works on a database that
  has been around.** With the data files fixed, the seeder itself failed —
  `seed_lookup_values` reads `value.with_context(lang='vi_VN').name`, and reading a translated field
  in a language the database does not have raises `KeyError: 'health.lookup.value.name'` out of the
  ORM cache rather than falling back to English. Always true on a brand-new database, never true on
  this clinic's, which added Vietnamese years ago. Guarded on `res.lang` having an active `vi_VN`;
  safe because the seeder is idempotent, so the labels land on the first run after the language is
  installed. **"Works on the master" and "installs" are different claims**, and only a from-nothing
  build can tell them apart.
- **H42** (H3) **A missing `depends` is invisible for as long as something else happens to supply
  it.** `health_theme` inherits `auth_signup.login` and declared only `web` and `base`. Every
  database it had ever run on already had `auth_signup`, pulled in by `website`. On a fresh install
  the data file loads first and the registry dies outright. Same family as H40/H41 and the same
  detector: build it from nothing.
- **H43** (H3) **Ordering inside one module: a data file cannot use what a post-init hook seeds.**
  Once the seed data resolved lookup values with `search=`, health_base's OWN files still found an
  empty table — `post_init_hook` runs after the data. `health.lookup.value._seed_from_registry()`
  already existed for exactly this reason (the demo data has called it since the vocabularies
  shipped); it is now also called from `data/health_lookup_seed.xml`, first in the manifest. Modules
  ABOVE health_base need no equivalent: by the time they load, health_base is fully installed,
  hook and all. **The non-demo half of a fix that already existed for demo data is a good place to
  look whenever a from-scratch build fails and a demo build does not.**
- **H44** (H3) **The odoo account's sudo was granted by GROUP MEMBERSHIP, not by a file.** `sudo -l
  -U odoo` said `(ALL : ALL) ALL` and `grep -rn odoo /etc/sudoers /etc/sudoers.d/` found nothing,
  because `odoo` was simply in the `sudo` group (`id odoo` → `27(sudo)`). `gpasswd -d odoo sudo`
  plus `/etc/sudoers.d/biz-tenants` reduced it to three commands. Nothing in `addons/` shells out at
  all — a grep for `subprocess`, `os.system`, `os.popen` and literal `sudo ` command strings across
  the whole tree returns nothing — so there was nothing to break, and the permission had simply
  never been questioned. **`sudo -l -U <user>` answers "what can they do"; only `id <user>` answers
  "and where does that come from".**
- **H45** (H3) **The deploy wrapper's own health check broke the moment routing became
  hostname-based, and it broke SILENTLY UPWARDS.** It curled `localhost:8069/web/login`, which under
  `dbfilter = ^%d$` asks for a database called `localhost` and gets a 303 to the database selector no
  matter how healthy the service is. It now sends `Host: carejiox.com`. It asks for the APEX rather
  than for the database it just upgraded, on purpose: the golden template's name contains an
  underscore and is therefore unreachable by hostname, and that is a property to preserve rather
  than to work around. **Every "is it up?" probe on this box is now a question about a hostname, not
  about a port.**
- **H46** (H3) **Browser validation on the new domain needed a session, and the honest way to get
  one has a trap in it.** No password was available, so a session was minted server-side for the
  platform administrator and planted as a cookie. It did not work: Odoo sets `session_id` with
  `HttpOnly`, and any visit to the app plants one first, after which `document.cookie` can write a
  shadowed duplicate that the browser reports back and never sends. The way through is to plant the
  cookie from a page the APPLICATION never serves — `/status`, which nginx hands out itself — in a
  fresh browser context. Even that failed once: the status page had no favicon, so the browser's
  implicit `/favicon.ico` request went to the app and planted the HttpOnly cookie anyway. An inline
  `<link rel="icon" href="data:,">` fixed it, and is worth having regardless. **A page served
  entirely by nginx is a genuinely different origin-state from one served by the app, and the
  difference is exactly one favicon wide.**
- **H47** (H3) **Measured: the rename cost 26 seconds.** Stop to first HTTP 200, inside the deploy
  lock, on a 253 MB database with a 950 MB attachment folder — `ALTER DATABASE … RENAME` is a
  catalogue update and `mv` on the filestore is a directory rename within one filesystem, so neither
  is proportional to size. The budget was ten minutes. **The expensive part of a rename is never the
  rename**; it is the config, the nginx blocks and the seventeen places the old name is written
  down, all of which can be prepared while the service is up.
- **H48** (H3) ⚠ **THREE STATIC SWEEPS THAT SHOULD RUN BEFORE ANY FUTURE FROM-SCRATCH BUILD, AND
  THE RULE THAT MAKES THEM WORTH IT.** Building `carejiox_template` took EIGHT attempts, and each
  failed build costs 5–8 minutes of module loading to surface exactly one fault. The faults are all
  one family — *something that is true on a database which already exists, and false on a new one* —
  and all three sweeps are twenty lines each, read-only, and find every instance at once:
  1. **Dead field names in data files.** Walk every `<record model=…><field name=…>` in every xml
     file in every manifest's `data` list, and check the field against a live registry. Found 182
     elements / 20 pairs in one pass (H40). Hidden by `noupdate="1"`.
  2. **Forward references.** Walk each module's own `data` list in order and check that every xml id
     it names is defined earlier. **`ref=` is only one of four ways to name one** — `action=` and
     `parent=` on a menuitem, `%(xmlid)d` interpolated into an attribute, and `ref()` inside an
     `eval=` are the others, and the first version of the sweep read only `ref=`, reported the tree
     clean, and the next build failed anyway. Widened, it found three more.
  3. **Undeclared cross-module dependencies.** Compute each module's TRANSITIVE depends closure from
     the manifests on disk, then check every `<module>.<xmlid>` its data files name against it.
     Found `health_theme`→`auth_signup` and `health_emar`→`health_pwa`. The transitive part is what
     makes it usable rather than noisy: thirteen modules inherit `health_pwa.app_shell` and eleven
     are fine because they reach it through something else.
  **A green sweep is not a green build** — the sweeps are static and cannot see a hook, a compute or
  a translated read (H41, H49 came from running it) — but they turn "one build per fault" into "one
  build per CLASS of fault", and on this box that was the difference between an afternoon and a day.
- **H49** (H3) **The Vietnamese-alias mixin required Vietnamese, and that is the whole product's
  seed data.** `health.vi.alias.mixin` mirrors the `vi_VN` translation of `name` into the legacy
  `name_vi` column for seven lookup models, in BOTH directions. Reading or writing a translated
  field in a language the database does not have raises `KeyError: '<model>.<field>'` out of the ORM
  cache — it does not fall back. So on any new database all seven models die loading their own seed
  data. This is the same fault as H41 one layer down, which is the lesson: H41 was fixed at ONE call
  site (`seed_lookup_values`) and the same bug was sitting in the mixin that the seed data actually
  goes through. **Fix a language-availability fault in the mixin, not at the call site.**
  `biz_bi_health/hooks.py` (`self.vi_active`, set once in `__init__` from `res.lang.get_installed()`)
  is the module that got it right from the start and is the pattern to copy.
- **H50** (H3) ⚠ **THE GOLDEN TEMPLATE IS ENGLISH-ONLY, AND H4 HAS TO DECIDE THAT DELIBERATELY.**
  A fresh install installs no languages; the master has had `vi_VN` for years. With H49's guard the
  template now BUILDS, and it builds with every Vietnamese label absent — so a clinic cloned from it
  would be English-only, on a Vietnamese healthcare product. Deliberately not fixed here: which
  languages a customer gets is a product decision belonging to provisioning, not something a
  server-plumbing phase should quietly bake in. The remedy is two steps and idempotent — install
  `vi_VN`, then re-run `health.lookup.value._seed_from_registry()` — and it must happen either on
  the template or per tenant before the first customer is announced.
- **H51** (H3) **A SQL-view model must be declared AFTER the table it selects from, because Odoo
  initialises a module's models one at a time.** `registry.init_models` is literally
  `for model in models: model._auto_init(); model.init()` — not "every `_auto_init` then every
  `init`" — and the order is the order the classes are defined in. `hr_development_ai` adds
  `branch_id` to both `hr.employee` and `hr.employee.public` in one file with the PUBLIC model
  first, so on a fresh install the view is rebuilt before the column exists:
  `psycopg2.errors.UndefinedColumn: column e.branch_id does not exist`. Stock Odoo never trips on
  this because it keeps `hr.employee.public` in its own later-imported file. Fixed by swapping the
  two classes, with a comment saying why, because the next person to tidy the file alphabetically
  would undo it. **Wherever one module extends both a table and a view over that table, the view
  goes last.**
- **H52** (H3) ⚠ **THE TEMPLATE HAS NO CHART OF ACCOUNTS, AND H4 HAS TO DECIDE THAT TOO.** A fresh
  install loads none, so `health_invoicing`'s three healthcare accounts were the first thing on this
  box ever asked to exist without one — and in Odoo 19 `account.account.code` is company-dependent
  and constrained, so the create failed. **The XML had never set a code on any of the three**, and a
  query against the LIVE database confirms all three carry no code there either: `noupdate="1"` meant
  the rows were written once, before the constraint, and never revalidated. So this was a latent
  fault on the live books as well as a fresh-install one. Codes added. But the bigger fact stands:
  a clinic cloned from this template starts with **no accounts and no journals**. Payobook hit the
  same wall (its runbook loads `generic_coa` before the payroll-account module). Which chart a
  customer gets — `generic_coa`, the Vietnamese `vn`, or none — is a provisioning decision and is
  H4's, not a server-plumbing phase's to bake in. Alongside H50 (no languages), these are the two
  things the template is deliberately missing.
- **H53** (H3) **A fresh install of `health_base` makes outbound geocoding calls.** Six of them,
  taking about eight seconds, while loading `data/health_facility_official.xml` — the facility model
  geocodes an address on create. Harmless here and slow-but-fine on a box with internet, but it
  means **installing the product reaches the network**, which will matter the day one is built
  somewhere egress-restricted or behind a proxy: the install would stall on a timeout per facility
  rather than fail cleanly. Worth a switch before that day rather than after it.
- **H54** (H3) ⚠ **THE GOLDEN TEMPLATE'S "SECOND LOCK" DID NOT EXIST, AND THE TEMPLATE WAS ANSWERING
  ON THE PUBLIC INTERNET.** The design (and Payobook's, and this handover's §3.8) rests on
  "`carejiox_template` cannot be a hostname label, which is the second lock". It is not true on this
  stack: the registrar's `*.carejiox.com` record **resolves `carejiox_template.carejiox.com`**
  (verified against 8.8.8.8), nginx's `*.carejiox.com` server_name **matches a label containing an
  underscore**, and `dbfilter = ^%d$` then maps that label straight to the database. The template
  served `/web/login` — title and all — to anyone who guessed its name, from outside the box.
  The FIRST lock held (archived administrator, passwordless recovery account), so nobody could sign
  in; the surface was still open. Closed with `if ($host ~ "_") { return 444; }` in both wildcard
  server blocks — a database name with an underscore is never a tenant, so a hostname carrying one
  is never legitimate. **Found by the numbered test that asked the question literally instead of
  restating the assumption**, which is the whole argument for writing tests that try the thing
  rather than tests that agree with the design.
- **H55** (H3) ⚠ **`dbfilter = ^%d$` BREAKS EVERY HttpCase ON THIS BOX, AND IT LOOKS LIKE BROKEN
  SECURITY RATHER THAN A BROKEN HARNESS.** An HttpCase calls `http://127.0.0.1:<port>`; the
  application reads the first label of that Host — `127` — finds no such database, and answers 404
  from a request that never reached the app. Three of `health_fieldservice`'s SH1 security tests
  "failed" this way, and their assertion message ("neither /mail/data nor /mail/thread/data exists
  on this build — the exploit probe proved nothing") is a test that was written carefully enough to
  say it could not tell. **The giveaway is in the log: the request line names the database `?`
  instead of the real one.** `carejiox-deploy` now adds `--db-filter=^$DB$` whenever `-t` is given —
  the same pin H32 required for a clone, now required for every run. 5 failed → 0 failed on the same
  tags. **Any harness that reaches the application over HTTP has to name the database from now on.**
- **H56** (H3) **The harness fix then uncovered a live clinical defect that had been sitting there
  since the vocabulary conversion.** With the 404s gone, ten `health_emar` tests still errored on
  `KeyError: 'route'` — `health.medication.order.route` became `route_id`, and
  `ACTIVATE_REQUIRED_FIELDS` was missed. **Activating any medication order on the live database
  raised KeyError.** Same silence as H40, one layer up: XML data files were hidden by
  `noupdate="1"`, this was hidden by tests that had not been run since the conversion. Fixed (a
  Many2one is falsy when unset, so the check means what it always meant) and proven by the ten
  tests. **The lesson is about coverage, not about this bug**: a rename that a sweep of DATA files
  cannot see, and that only a test run can, needs the test run — and this phase is the first thing
  to have run health_emar's suite since the conversion shipped.
- **H57** (H3) **The never-list is not achievable as drafted: `health_learn` and
  `health_cms_coverage` both hard-depend on `health_web_leads`.** So the golden template HAS the
  lead funnel — one customer's marketing-site integration — because Odoo pulls a declared dependency
  in whatever the never-list says. `health_migration` and `health_catchment_backfill` were excluded
  cleanly. **H4 has to either break those two dependencies or accept the funnel in every tenant**,
  and the same trap applies to anything else added to the list later: a never-list is a statement
  about the dependency GRAPH, not about a set of names. The wider module diff is also not the
  never-list: the master carries 24 modules the template does not (`stock`, `purchase`,
  `sale_management`, `base_automation`, **`l10n_vn`**, `theme_default` …) because they are stock
  apps nothing in the product's own set depends on, and 6 the template has that the master lacks.
  **The definitive tenant module set is H4's to fix**, and `l10n_vn` belongs to the same decision as
  the chart of accounts (H52).
- **H58** (H3) **A tenant database must be OWNED BY `odoo`, and the failure looks like a routing
  bug.** `list_dbs` filters on `datdba = current_user` (`odoo/service/db.py:449`), and the
  application connects as the OS user `odoo` because the config sets no `db_user`. A database made
  with `sudo -u postgres createdb -T carejiox_template <slug>` belongs to `postgres`, is therefore
  invisible to the application, and the tenant's address answers **303 to the database chooser**
  rather than a sign-in page — indistinguishable from a `dbfilter` mistake, and nothing in the log
  says "wrong owner". `-O odoo` fixes it; `ALTER DATABASE <slug> OWNER TO odoo;` repairs it after
  the fact. **Found by running the runbook's own tenant-creation procedure end to end on a
  throwaway clone rather than trusting that it was right** — the clone was made, checked (200, its
  own sign-in page, `/web/database/manager` 404, 71 crons re-enabled exactly as recorded, 3.9
  seconds to copy 108 MB) and dropped. The procedure as first written would have failed for the
  first person who followed it. **Write a runbook step, then do the step.**
- **H59** (H3) ⚠ **A BACKTICK IN AN UNQUOTED HEREDOC IS COMMAND SUBSTITUTION, AND THESE SCRIPTS RUN
  AS ROOT.** `biz-tenant-cert` writes its nginx block from `<<EOF` (unquoted, because the hostname
  and certificate path must expand). A comment added during this phase used markdown-style
  backticks around ``listen`` and ``http2 on;`` — so running the script as root printed
  `listen: command not found` and interpolated the (empty) output into a root-owned config file.
  Harmless in effect and completely wrong in principle, in the one file whose entire justification
  is that it validates before it writes. **Neither the 27 guard tests nor `nginx -t` could catch
  it**: the guards stop before the block is written, and the result was valid nginx. Only running
  the script for real did. **No backticks in a generated config, ever** — the rewritten comment
  says so in the file.
- **H60** (H3) **Running the three scripts for real proved the parts nothing else reaches — and
  found that the installed copy was stale.** A full lifecycle on a throwaway hostname
  (`zzcheck.carejiox.com`, no database, dropped afterwards): the odoo user, through sudo, obtained a
  certificate; the block was written; `biz-domain-detach` removed both block and certificate; a
  clean re-create worked; the hostname served **its own** Let's Encrypt certificate with a chain
  that validated without `-k`; and detaching again left nothing behind. The first attempt also
  failed on `unknown directive "http2"` — because the fix made in the repo earlier in this phase had
  never been redeployed to `/usr/local/bin`, and **the script's own rollback removed the bad block
  and left nginx loadable**, which is the safety net doing exactly its job. Two rules out of it:
  redeploy a script the moment you fix it (`BIZ_BIN=/usr/local/bin bash tools/saas/test_scripts.sh`
  tests what is actually installed), and a certificate script is only proven by issuing a
  certificate.
