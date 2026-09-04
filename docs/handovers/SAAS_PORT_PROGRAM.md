# SAAS PORT program — the tenant platform and the Access home, as generic `biz_*` cores in health19

Status: **H0 DONE, H1 DONE 2026-09-04. H2 next.** Spec that started it:
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
| **H2 `health_access` + retire `access_roles`** | cms.sidebar rail provider (bundle lane beside the legacy lane), clinic ability→group catalogue + the 9 roles migrated to bundles, native menu-hide + debug block (Rail A), People lens absorbs `health_user_admin`, uninstall `access_roles` on the live DB (owner sign-off at deploy) | next |
| **H3 Server plumbing** | `dbfilter = ^%d$`, carejiox.com apex + wildcard, nginx blocks (`/web/database` 404, `/status`), per-host HTTP-01 certs, golden template DB, scripts + sudoers, backups dir, stale-DB and shadowed-module cleanup, resize runbook | |
| **H4 `biz_tenancy` + `biz_tenants` + `health_tenancy`** | the tenant agent + the cockpit, parameterised (brand, domain, prefix, never-list, xmlids, meter registry, plan seeds, feature catalogue, status components); pilot tenant `hhh` | may split 4a/4b |
| **H5 Validation** | every FLEET live check re-run on the pilot, Chrome-driven | |

---

## Verified plumbing (H0, 2026-09-04 — do not re-derive)

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
