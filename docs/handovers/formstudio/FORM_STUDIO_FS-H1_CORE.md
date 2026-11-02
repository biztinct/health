# FORM STUDIO — FS-H1: the engine (`biz_form_studio`) + the first host (`health_form_studio` on Incident)

Status: HANDOVER to Opus (written 2026-11-02 by Fable). Programme: `FORM_STUDIO_PROGRAM.md`
(read §0, §3, §5 first; this file overrides it where it says so). Clickable concept:
`FORM_STUDIO_POC.html` (open in Chrome; the "Client record" screen in Studio mode is the look
to clone — palette left, schematic cards centre, field settings right). Read
`docs/strategy/HANDOVER-CONVENTIONS.md` §1–§4, §6, §8 and the ledger entries named in §2 below
before writing code. Continue the ledger after **§5.264**.

## 0. Standing rules (state them back in your report)

- **White-label.** The word "Odoo" never appears in anything a user can see: labels, help,
  placeholders, `_t()` strings, `.po` msgstr, error text. Technical identifiers are fine.
  `biz_form_studio` is a GENERIC module: its sources may not contain "Odoo", "Viet Uc",
  "Việt Úc", "Carejiox", "health_", "clinic", "nurse", "patient" (same gate as
  `biz_access/tests/test_access_generic.py:259`). Everything product-specific lives in
  `health_form_studio`.
- **Plain copy** in the user's words: "field", "card", "this screen", "everyone / staff / admins",
  "Health information", "Publish", "Go back to the previous layout". Never show `x_fs_…`.
- **Design:** flat mono colours from `--bzk-*` (biz_kit) and `--vuf-*` tokens only; Lucide icons
  via `ic()` from `@biz_kit/js/kit_icons` (add glyphs to that registry if missing — the source
  gate at `biz_access/tests/test_access_generic.py:421` is the model to copy); no emoji, no
  font-awesome in markup you write; no gradients. Studio chrome = `--bzk-ink` (navy) bar like the
  POC. Typeface is the product font — write no `font-family`.
- **Vietnamese** for every new string in `biz_form_studio/i18n/vi.po` and
  `health_form_studio/i18n/vi.po` (filename `vi.po`, like the other `biz_*` modules). Each
  entry needs `#. module:`, the code/model marker and a `#:` occurrence (conventions §4,
  ledger §5.58 / §5.67 / §5.84 / §5.129). Run `health_base/tests/test_i18n_catalogues.py`.
- **Chatter stays at the bottom** (the incident form already has `<chatter/>` — never move it).
- **No business-logic change** on any host model. Studio adds fields and views; it never alters
  an existing field, button, `invisible=`, `groups=` or `readonly=` condition.
- **Sanctioned edits are exhaustive** (§1). Shared modules are read-only.
- **Tests:** never `carejiox-deploy -t` on the live box (H77). Rehearse on a clone
  `carejiox_fs1` with `biz.tenant` rows neutralised and jobs off (H78/H102),
  `--db-filter=^carejiox_fs1$` on every manual run. Restart the clone unit after any file push
  (§5.228). Close QA tabs before a test run (§5.216).
- **Browser QA** via chrome-devtools (§5.215); sign in with `fetch` to `/web/session/authenticate`;
  real navigation path (sidebar → Clinical → Incidents → open one), never only a deep link.
  Drive with trusted clicks (§5.126). Verify what was SERVED before diagnosing JS (§5.147/§5.200).
- **Commits** on `19.0`, plain-sentence messages in the repo's style, ending
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. **Do not push.**
- **Deploy** only via `carejiox-deploy` (conventions §2). New modules need `-i` on EVERY
  database: `carejiox`, `carejiox_template`, `hhh`. Template jobs must stay off afterwards
  (§5.178 / §5.192). Owner decision: FS-H1 **goes live** when it passes.

## 1. Scope

| # | Item | Module | Sanctioned files |
|---|---|---|---|
| C1 | Models `fs.host`, `fs.field.meta`, `fs.layout`, `fs.layout.draft`, `fs.layout.history`, `fs.link.target`, facade `fs.studio` | biz_form_studio (NEW) | whole module |
| C2 | Visibility hook: `ir.model.fields._instanciate_attrs` override adding `groups` for `x_fs_` fields | biz_form_studio | `models/ir_model_fields.py` |
| C3 | Layout writer + validator (`fs.layout._render_arch`, `publish`, `validate`, `fs.studio.validate_all`) | biz_form_studio | `models/fs_layout.py` |
| C4 | Studio button on the form's top bar (FormController patch + `web.FormView` template extension) + `form_studio` JS service | biz_form_studio | `static/src/js/studio_button.js`, `static/src/xml/studio_button.xml`, `static/src/js/studio_service.js` |
| C5 | Studio editor client action (`biz_form_studio.studio`): palette, schematic cards, field settings, publish sheet, typed-DELETE sheet, "go back" | biz_form_studio | `static/src/js/studio/*.js`, `static/src/xml/studio/*.xml`, `static/src/scss/studio.scss` |
| C6 | Field library client action (`biz_form_studio.library`): table of custom fields per model, usage, open in Studio | biz_form_studio | `static/src/js/library.js`, `static/src/xml/library.xml` |
| C7 | Security: ACLs, record rules; server gate helper | biz_form_studio | `security/ir.model.access.csv`, `security/fs_security.xml`, `models/fs_studio.py` |
| C8 | Overlay: host data for the Incident form, gate + visibility-group parameters, link targets, sidebar row (Admin section, Owner+Admin), Vietnamese | health_form_studio (NEW) | whole module |
| T | Tests (§5) | both | `biz_form_studio/tests/*.py`, `health_form_studio/tests/*.py` |

**Non-goals (binding):** Client / Contact / Booking hosts and the Workspace-card markup and the
fold-tray hook (FS-H2/H3); list layouts and `fs.list.layout` (FS-H3); PHI consequences beyond
storing the flag, forcing `list_ok=False` and the marker (encryption hook, BI scan, export
exclusion, PWA block = FS-H4); Settings-hub tile in `health_landing` (FS-H2); deploy-wrapper
validator step, nightly cron, template seeding (FS-H5); per-user ("Just me") layouts; editing
standard fields' labels (rename/help of standard fields is FS-H2); moving/hiding standard fields
(FS-H2); formula/computed fields; one2many/many2many types; the family portal; the nurse app.

## 2. Verified plumbing (2026-11-02 — do not re-derive; re-check file:line before coding)

Core paths are the SERVER copy (`ssh VietUcUAT`, `/odoo/odoo-server/…`); repo `addons/web` is
stale for core facts. Repo paths relative to `addons/`.

### 2.1 Manual fields (`odoo/addons/base/models/ir_model.py`)
- `IrModelFields` :503. `state` :543 default `'manual'`. **`groups` (:549) is an unimplemented
  m2m — core never applies it.** → visibility is done by C2 (below), not by writing `groups`.
- `x_` rule is ONLY the SQL constraint `_name_manual_field` :641-644 (`CHECK (state != 'manual'
  OR name LIKE 'x\_%')`); `_check_name` :631 = `check_pg_name` (≤63 chars, `[a-z0-9_]`). Validate
  `x_fs_` + slug yourself before create, or you get an IntegrityError at flush.
- `create()` :996-1038: `registry.clear_cache('stable')`, unknown `relation` → UserError, then
  `flush_all()` → `pool._setup_models__` → `init_models(…, update_custom_fields=True)` (ALTER
  TABLE in `orm/models.py:3194-3225`), then registry signalling → **every worker reloads on
  every field create/write/unlink and on every `ir.model.fields.selection` change** (:1657,
  :1692, :1717). Batch selection options in one `create` of the field with `selection_ids`
  commands; publish writes one field at a time inside ONE transaction.
- `write()` :1040: type change refused by core; one rename at a time.
- `ir.model.fields.selection` :1479 (`field_id`, `value`, `name` translatable, `sequence`;
  unique on field+value; removing a value sets null on non-required fields :1762).
- Many2one: `relation` must exist (`_check_relation` :705); `on_delete` default `'set null'`
  :544; `required` + `set null` refused (:811-818) → a required link field must be created with
  `on_delete='restrict'`.
- **`_instanciate_attrs(field_data)` :~1255-1300 builds the Python field kwargs from the row
  dict and sets NO `groups`** (verified: `grep groups` in that method finds nothing) — the seam
  for C2. `_add_manual_fields` is `odoo/orm/model_classes.py:573`. `_instanciate_attrs` is at
  :1257; the row dict comes from `_get_manual_field_data(model_name)` :1253 →
  `_all_manual_field_data()` (read that method: if it reads every column of the row, use
  `field_data.get('fs_vis')`; otherwise fall back to `self.browse(field_data['id']).sudo().fs_vis`,
  which runs once per registry build and is cheap).
- Caches: `_get_ids` `ormcache(..., cache='stable')` :827; label caches in
  `health_tenant_workspace/models/ir_model_fields.py:63-74` (`get_field_string/help/selection`,
  default cache, no clearing override) are cleared by `_setup_models__` anyway
  (`registry.py:403-405`). Nothing to do; test 7 proves the label shows after a rename.

### 2.2 Views (`odoo/addons/base/models/ir_ui_view.py`)
- Fields: `key` :147, `priority` :148 (default 16), `arch_db` :162, `inherit_id` :169
  (`ondelete='restrict'`), `group_ids` :175, **`mode` :177 default `'primary'` → set
  `mode='extension'` explicitly**, `active` :198.
- Validation: `_check_xml` :424 → `_valid_inheritance` :402. **Selectors on translated
  attributes are refused** (`string`, `help`, `placeholder`, `title`, `confirm`, …:
  `TRANSLATED_ATTRS` `odoo/tools/translate.py:74`; error "View inheritance may not use attribute
  %r as a selector." :409/:420). Anchor only on `@name`, `hasclass()`, element names.
- Combine: `get_combined_arch()` :1037 (string), `_get_combined_arch()` :1041 (etree).
  `apply_inheritance_specs` :938 → `odoo/tools/template_inheritance.py:107`; `position`
  handling `attributes` :233, `inside` :310, `after` :317, `move` :45/:208.
- Use `get_combined_arch()` in tests, never `get_view()` (it strips groups-gated nodes —
  `health_cms_coverage/tests/test_cms_consolidation.py:18-22`).

### 2.3 Web client (server `addons/web/static/src/views/`)
- `FormController` `form/form_controller.js:124`, template `web.FormView`
  (`form/form_controller.xml`) with `Layout` slots `control-panel-create-button`,
  `layout-buttons`, `layout-actions`, `control-panel-additional-actions` (the cog menu),
  `control-panel-status-indicator`. **Put the Studio button here** (template
  `t-inherit="web.FormView" t-inherit-mode="extension"`, precedent
  `mail/static/src/chatter/web/form_controller.xml:4`), gated by a getter added with
  `patch(FormController.prototype, …)`. Do NOT use `StatusBarButtons`: it belongs to
  `FormRenderer` (`form_renderer.js:16,41`), `health_theme` lifts the header into the hero
  (`ws_statusbar_more.js:74-88` `liftStatusBarIntoHero`) and replaces its slot loop
  (`health_theme/static/src/xml/ws_statusbar_more.xml:7`), and forms without `<header>` have
  none.
- The view id the controller renders: `this.env.config.viewId` (also `this.props.resModel`).
- `patch(FormController.prototype, …)` precedents in this repo:
  `health_field_requirements/static/src/js/form_required_popup.js:64`,
  `health_invoicing/static/src/js/package_wizard_patch.js:8`. `useService`, `onWillStart` in
  `setup()` after `super.setup()`.
- Client action registration: `registry.category("actions").add("biz_access_home",
  BizAccessHome)` (`biz_access/static/src/js/access_board.js:2164`); its `ir.actions.client`
  record `biz_access/views/access_views.xml:392-394`. Full-screen client action root: never
  `position:absolute; inset:0` (§5.52) — `display:flex; width:100%; height:100%`.
- A `t-set` named like a component getter kills the form (§5.249); module-level memo keyed on a
  prop object misses (§5.250) — key on `toRaw(...)`.
- A fire-and-forget `orm.call(...).then()` in `onWillStart` with no `.catch` becomes a modal for
  anyone lacking the ACL (§5.127 b/c) — the host probe (`fs.studio.probe`) must never raise:
  it returns `{host: false}` for anyone without access.

### 2.4 Shared kit (`biz_kit`, 19.0.1.1.0, depends `web`)
- Assets: `scss/kit_tokens.scss`, `scss/kit.scss`, `scss/kit_modal.scss`, `js/kit_icons.js`,
  `js/kit_registries.js`, `js/kit_nav.js`, `xml/kit_nav.xml`.
- `import { ic, IC } from "@biz_kit/js/kit_icons"` — `ic(name, size=16)` returns markup;
  unknown name falls back to `IC.circle` (so a missing glyph is SILENT — test 12 checks every
  icon you use exists). `HubBackChip`/`hubBack` from `@biz_kit/js/kit_nav` is the ONLY OWL
  component. Classes: `.bzk-page .bzk-wrap .bzk-h1 .bzk-h2 .bzk-sub .bzk-eyebrow .bzk-card
  .bzk-panel .bzk-panel-h .bzk-table .bzk-tablewrap .bzk-badge .bzk-chip(s) .bzk-seg
  .bzk-segbtn .bzk-btn .bzk-btn-sm .bzk-note .bzk-empty .bzk-busy .bzk-modal*`. Tokens
  `kit_tokens.scss:69-108`: `--bzk-primary(-hover/-strong/-light/-dark) --bzk-ink --bzk-soft
  --bzk-soft2 --bzk-ring --bzk-border --bzk-text --bzk-muted --bzk-line --bzk-line-2 --bzk-bg
  --bzk-surface --bzk-green/rose/amber/cyan/slate(-soft) --bzk-r --bzk-r-sm --bzk-r-lg
  --bzk-pill --bzk-sh --bzk-sh-lg --bzk-scrim --bzk-z-modal`. Everything else (drag/drop,
  property panel, sheets) you build inside `biz_form_studio`.
- Bus: `bus.bus._sendone(target, type, message)` (`addons/bus/models/bus.py:108`; string
  target must be non-guessable; precommit queue). Preferred `bus.listener.mixin._bus_send`.
  **Optional** in H1 (see §3.9).

### 2.5 The test host — `health.incident` (`health_incident`, 19.0.1.1.0, depends health_base, health_fieldservice, health_pwa)
- Model `health_incident/models/health_incident.py:65` (`mail.thread`, `mail.activity.mixin`,
  `health.lifecycle.mixin`); fields :72-175 (`name`, `incident_type`, `severity`, `client_id`,
  `order_id`, `facility_id`, `catchment_province_id`, `reporter_id`, `investigator_id`,
  `location`, `incident_datetime`, `description`, `immediate_actions`, …, `state` :126,
  `active`, `company_id`). **No `currency_id`** → the Money type is unavailable on this host
  (§3.5 rule).
- Form `health_incident.view_health_incident_form` (`views/health_incident_views.xml:5-146`):
  `<header>` :10-37, `button_box` :40, `oe_title`, groups, `<notebook>` (page `name="evidence"`),
  `<chatter/>` :146. **No inheriting views exist.** No `js_class`; not in `VU_NO_HERO_JS_CLASS`
  (`health_theme/static/src/js/vu_form_compiler.js:32`) → full VU engine with auto-hero; every
  inner `<group>` becomes a card (`compileGroup` compiler:165-187) — so a Studio section rendered
  as `<group name="fs_<id>" string="…">` is carded for free.
  **Check whether the arch's `<group>`s carry `name=`** before declaring open sections; if they
  do not, the H1 host declares no open cards and Studio can only ADD sections (fine).
- Action `action_health_incident` :292 (view_mode list,kanban,form,graph,pivot); sidebar row
  `health_cms_sidebar.item_clin_incidents_register`
  (`health_cms_sidebar/data/cms_sidebar_items_clinical.xml:146-154`).
- ACL `health_incident/security/ir.model.access.csv:2-9`: receptionist/nurse read+create,
  head_nurse…admin read/write/create, owner also unlink. Record rules
  `security/health_incident_security.xml:16-28`.
- `health_incident/i18n/vi.po` exists (filename `vi.po`).

### 2.6 Gate, roles, groups
- `health_access.group_clinic_admin` (`health_access/security/health_access_security.xml:32-50`)
  implies `health_base.group_healthcare_admin` + `biz_access.group_access_manager`. Roles reach
  it through the ability `'user-admin'` (`health_access/hooks.py:276-279`; Owner and Admin
  roles :399-427). Group closure is computed at read time (§5.114) — `has_group` is correct.
- Staff group for `vis='staff'` = **`health_base.group_healthcare_base`**
  (`health_base/security/health_security.xml:20`). (`group_healthcare_user` does NOT exist.)
- `base.group_system` = platform admin only; the clinic admin does NOT have it, so
  `ir.model.fields` / `ir.ui.view` writes must run `sudo()` **after** the gate passes
  (`sudo()` keeps `env.uid` — §5.154/§5.210 — so audit rows still say the human).
- `biz.access.role` `biz_access/models/access_role.py:57`; sidebar role gate `biz_role_ids` on
  `cms.sidebar.item` (`health_access/models/cms_sidebar.py:166`); precedent XML
  `health_compliance/data/sidebar.xml:2`
  (`eval="[(6, 0, [ref('health_access.role_admin'), ref('health_access.role_owner')])]"`).
  `cms.sidebar.item` fields `health_cms_sidebar/models/cms_sidebar_item.py:13-59` (`name`,
  `section_id`, `sequence`, `icon` fa class, `action_xmlid`, `action_tag`, `match_action_tags`).
  Example `cms_sidebar_items_admin.xml:79-87` (Field Requirements, seq 90, section_admin).
  `health_cms_ia/hooks.py` `MOVE` :174 `{item: (section, parent|None, seq)}`, `EXACT` :335
  `{item: (roles…)}` — add your row to BOTH dicts? NO: `health_cms_ia` is a shared module
  (read-only this phase). Your row is a plain data record in `health_form_studio` with
  `biz_role_ids` set; verify in QA it shows for Owner/Admin and not for a nurse. If the IA
  hook moves/hides it, report it (FS-H2 sanctions the `health_cms_ia` entry).
- `mail.thread` config-model precedent: `biz_analytics/models/analytics_dashboard.py:14`
  (`tracking=True` on `name`, `active`). No generic audit mixin exists in this repo.

### 2.7 Tests precedents
- `health_cms_coverage/tests/test_cms_consolidation.py:49` (`@tagged('post_install',
  '-at_install')`, `TransactionCase`, `get_combined_arch()` + `etree.xpath`).
- Source gates: `biz_access/tests/test_access_generic.py:259` (forbidden words), `:397`
  `TestSourceGates` (icons in registry :421, implicit string concatenation, OWL loop variable
  names). Clone it for `biz_form_studio`.
- `health_base/tests/test_i18n_catalogues.py` `TestI18nCatalogueShape` :110,
  `TestI18nCatalogueLoads` :165.
- Fixture rules conventions §6 (partners need `catchment_province_id`; tag `post_install`).

## 3. Design

### 3.1 Modules
- **`biz_form_studio`** (NEW, 19.0.1.0.0): depends `['base', 'web', 'mail', 'bus', 'biz_kit']`.
  Generic. Product facts arrive ONLY through: `fs.host` records, `fs.link.target` records and
  three `ir.config_parameter` keys read at call time with safe defaults:
  `biz_form_studio.gate_group` (default `base.group_system`),
  `biz_form_studio.group_staff` (default `base.group_user`),
  `biz_form_studio.group_admin` (default = gate group).
- **`health_form_studio`** (NEW, 19.0.1.0.0): depends `['biz_form_studio', 'health_theme',
  'health_access', 'health_incident', 'health_cms_sidebar']`. Data only in H1 (plus tests):
  the three parameters (`health_access.group_clinic_admin`, `health_base.group_healthcare_base`,
  `health_access.group_clinic_admin`), the Incident host, the link targets, the sidebar row,
  `vi.po`. `noupdate="0"` on all of it (these are OUR records; §5.116 is about business seeds).

### 3.2 Models (`biz_form_studio/models/`)
`fs.host` — `model` (Char, required, index), `base_view_xmlid` (Char, required),
`kit` (Selection `vu|ws`, default `vu`), `sections` (Json: `[{name, title}]` open cards an
admin may drop into; `[]` allowed), `locked_fields` (Json `{field_name: reason}`),
`locked_zones` (Json `[{name, title, reason}]` shown dimmed), `money_ok` (Boolean computed:
`'currency_id' in model._fields`), `active`. Helpers: `_base_view()` (resolve xmlid, sudo),
`_for(model, view_id)` → the host whose base view id == view_id (or whose base view is the
primary parent of view_id when the controller renders an inherited primary view — check
`view.mode`/`inherit_id` chain, one level is enough).

`fs.field.meta` — `field_id` (m2o `ir.model.fields`, required, `ondelete='cascade'`, unique),
`model` (related, stored), `vis` (Selection `all|staff|admin`, default `all`), `phi` (Boolean,
default False), `pwa` (Boolean, default False), `list_ok` (Boolean, default True; forced False
while `phi`), `label_vi` (Char), `help_vi` (Char), `order` (Integer), `created_by` (m2o
res.users), `publish_version` (Integer), `warned_phi` (Boolean: the one-time text/file warning
was shown). Constraint: `phi → not list_ok`.

`fs.layout` — `_inherit = ['mail.thread']`; `model`, `base_view_id` (m2o ir.ui.view,
`ondelete='cascade'`), `company_id` (m2o res.company, optional; H1 writes company-less =
"everyone" layouts — the column exists for H5 tenancy, nothing reads it yet), `sections` (Json),
`version` (Integer, `tracking=True`), `view_id` (m2o ir.ui.view, the generated extension view,
`ondelete='set null'`), `published_by`, `published_at`, `state` (`ok|broken`, `tracking=True`),
`broken_reason` (Text). Unique (model, base_view_id, company_id).

`fs.layout.draft` — `layout_id` (m2o, cascade), `user_id`, `sections` (Json), unique
(layout_id, user_id).

`fs.layout.history` — `layout_id` (cascade), `version`, `sections` (Json), `arch` (Text),
`published_by`, `published_at`. Append-only (`unlink` refused except via cascade).

`fs.link.target` — `model` (Char), `label` (Char, translatable), `active`. The curated list of
models a "Link to a record" field may point at. Core ships NONE; the overlay ships: Staff member
(`hr.employee`), Facility (the model behind `health.fieldservice.order.facility_id` — read it),
Client (`res.partner`), Contact (`crm.lead`), Service or package (`product.product`), Catchment
area (the model behind `catchment_province_id` — read it). Verify each model exists on the
clone before shipping the record.

`fs.studio` — AbstractModel facade; every public method `@api.model`, first line
`self._check_gate(model)`:
- `_check_gate(model)`: `has_group(gate_group)` AND `self.env[model].check_access('write')`
  (verified Odoo 19 names: `check_access(operation)` `odoo/orm/models.py:4097` raises,
  `has_access(operation)` :4114 returns bool; the old `check_access_rights` :4159 still exists
  but is legacy). Raise `AccessError(_("You do not have access to Form Studio for this screen."))`.
- `probe(model, view_id)` → `{host: bool, can_edit: bool}` — **never raises**: catches
  AccessError and returns `{host: False, can_edit: False}`.
- `get_studio(model, view_id)` → `{host:{sections, locked_zones, money_ok}, layout:{id, version,
  sections, state, broken_reason}, draft: sections|null, fields:{name:{label, help, type, std,
  locked, reason, vis, phi, pwa, list_ok, options?, comodel_label?, required}}, link_targets:
  [{model, label}], types: [...], can_publish, history:[{version, published_at, published_by}]}`.
  `fields` = every stored field of the model that is in the combined base arch OR is an
  `x_fs_` field (so admins see standard fields as "locked/standard" chips in the schematic,
  read from `_get_combined_arch` + `fields_get`). Labels through `fields_get` so they are
  debranded/translated.
- `save_draft(layout_id|model+view_id, sections)` (per user).
- `discard_draft(...)`.
- `create_field(model, spec)` → spec `{type, label, help, required, vis, phi, pwa, options:[str],
  comodel, default?}`. Types: `char, text, integer, float, monetary, boolean, date, datetime,
  selection, many2one, binary`. `monetary` refused unless `host.money_ok` (currency_field =
  `currency_id`). `many2one` comodel must be an active `fs.link.target`; `required` m2o →
  `on_delete='restrict'`. Name = `x_fs_` + slug(label) (ASCII via `unicodedata.normalize('NFKD')`
  stripping combining marks, `đ→d`, lowercase, `[^a-z0-9]+→_`, ≤40 chars) with `_2`, `_3` on
  collision; validate `^x_fs_[a-z0-9_]+$` and total length ≤ 63 BEFORE create. Create
  `ir.model.fields.sudo().create({name, model_id, ttype, field_description, help, state:
  'manual', store: True, copied: False, tracking: False, required, relation, on_delete,
  selection_ids: [Command.create({value: slug(opt), name: opt, sequence: i})…]})` inside
  `with self.env.cr.savepoint():`; then the meta row; then `_apply_vis(field)` (writes `fs_vis`
  on the `ir.model.fields` row — see 3.4). Returns `{name, label}`. Text/file types return
  `phi_warning: True` when `not meta.warned_phi` (client shows the one-time note, then calls
  `ack_phi_warning(name)`).
- `update_field(name, spec)`: label, help, required, vis, phi, pwa, list_ok, options (ADD or
  RENAME only; removing a value with existing rows → refuse with the count; offer `retire`:
  `fs.field.meta.retired_values` Json — a retired value is hidden from new picks by the writer
  emitting… nothing in H1: store it, show "retired" in the panel, apply in H2 — say so in the
  UI tooltip "hidden from new picks after the next release"). **Never `ttype`**.
- `field_references(name)` → `[{kind, label, count, url?}]` from: `fs.layout.sections` (which
  layouts place it), `ir.exports.line` (`name` ilike), `ir.filters` (`domain`/`context` ilike
  the field name, same model), plus a hook `_fs_extra_references(field)` returning `[]` in core
  (the overlay extends it for `field.requirement.rule` when installed — H1 overlay implements
  this one because the module is present: `field.requirement.rule` rows whose field name
  matches; check its field names at `health_field_requirements/models/field_requirement_rule.py:16-87`).
- `delete_field(name, confirm)`: `confirm == 'DELETE'` required; refuse while blockers exist
  (references other than layouts); remove from every layout's sections and REPUBLISH those
  layouts (so no view references a field about to vanish — a view referencing a missing field
  breaks the form); then `ir.model.fields.sudo().unlink()` in a savepoint. Return the count of
  records that had a value (computed BEFORE unlink: `search_count([(name,'!=',False)])`) and
  show it in the typed-DELETE sheet beforehand (`field_references` includes
  `{kind:'values', count}`).
- `publish(model, view_id, sections)` → render → write/create view → bump version → history →
  chatter message "Published version N by <user>: +a fields, −b fields, c moved" →
  delete the user's draft → `{version, view_id}`.
- `rollback(layout_id, version)` → republish that history's `sections`.
- `validate_all()` → for every `fs.layout`: re-render against the CURRENT base arch, `_check_xml`
  via a dry run (write the arch into the view inside a savepoint and roll back on error);
  on failure: `view.active=False`, `state='broken'`, `broken_reason`, chatter message, log
  `_logger.error`. Returns `{checked, broken:[…]}`. (Deploy-wrapper + cron wiring = H5; H1
  exposes the method and a test.)

### 3.3 The writer — `fs.layout._render_arch(sections, host)` (deterministic)
`sections = [{id, title, title_vi?, icon?, anchor, fields:[{name, order, span?}]}]` where
`anchor ∈ {{kind:'card', name}, {kind:'sheet_end'}, {kind:'before_notebook'}}` (`card` only
for names in `host.sections`). Output for kit `vu`:
```xml
<data>
  <!-- new section -->
  <xpath expr="//sheet/notebook" position="before">            <!-- before_notebook -->
    <group name="fs_<id>" string="<title>" class="fs-card" data-fs-id="<id>">
      <field name="x_fs_a"/><field name="x_fs_b" widget="…"/>
    </group>
  </xpath>
  <xpath expr="//sheet" position="inside"> … </xpath>          <!-- sheet_end -->
  <!-- into an open host card -->
  <xpath expr="//group[@name='<card>']" position="inside"><field name="x_fs_c"/></xpath>
</data>
```
Rules: `string` on the generated `<group>` = the EN title (translation of titles is `title_vi`
rendered by the client only in H1; the arch stays EN — note it in the report); `//sheet/notebook`
falls back to `sheet_end` when the base arch has no notebook (check with `etree` on the
combined base arch at render time); `groups=` is NOT written on nodes (visibility is ORM-level,
3.4); widgets: `binary` → `widget="binary"`; `many2one` → `options="{'no_create': True}"`;
`text` → plain; `boolean` → default. Every `x_fs_` field referenced must exist on the model
(`model._fields`) or the writer raises before touching the view. The generated view:
`name=f"Form Studio: {model}"`, `key=f"biz_form_studio.{model}.{company or 'all'}"`,
`model`, `inherit_id=base_view_id`, `mode='extension'`, `priority=200`, `type='form'`,
`active=True`, `arch_db=<xml>`, created/written `sudo()`. Writing the arch triggers
`_check_xml` (server-side validation = safety rail 1). Wrap publish in ONE transaction; on any
exception nothing is written (the facade is one RPC).

### 3.4 Visibility (C2) — `biz_form_studio/models/ir_model_fields.py`
```python
class IrModelFields(models.Model):
    _inherit = 'ir.model.fields'
    fs_vis = fields.Char()   # 'all' | 'staff' | 'admin' | False — only on x_fs_ rows
    def _instanciate_attrs(self, field_data):
        attrs = super()._instanciate_attrs(field_data)
        if attrs and field_data.get('name', '').startswith('x_fs_'):
            vis = field_data.get('fs_vis') if 'fs_vis' in field_data else self.browse(field_data['id']).sudo().fs_vis
            xmlid = self.env['fs.studio']._vis_group_xmlid(vis)   # None for 'all'
            if xmlid:
                attrs['groups'] = xmlid
        return attrs
```
`_vis_group_xmlid` reads the config parameters (3.1). `fs.field.meta.vis` write → writes
`field_id.fs_vis` (sudo) → `ir.model.fields.write` rebuilds the registry → `fields_get` hides
the field and `read` raises for non-members: **ORM-enforced**, exactly as §3.5 of the programme
promised. Test 6 proves it. (If `_get_manual_field_data` does not include `fs_vis`, the
`browse` fallback above is used — it runs once per registry build, acceptable.) Changing the
group parameters later needs one touch of each field (write `fs_vis` to itself) — provide
`fs.studio.reapply_visibility()` for the overlay's post-init hook.

### 3.5 Types and rules
| Type | ttype | Extra |
|---|---|---|
| Text | char | size None |
| Long text | text | one-time PHI warning |
| Whole number | integer | |
| Decimal | float | |
| Money | monetary | only when `host.money_ok`; `currency_field='currency_id'` |
| Yes / No | boolean | |
| Date | date | |
| Date and time | datetime | |
| Dropdown | selection | ≥1 option; options add/rename only |
| Link to a record | many2one | comodel from `fs.link.target`; required → restrict |
| File | binary | one-time PHI warning; `widget="binary"` |

Type immutable after creation (UI hides the type control once created). `required` on a custom
field = plain `required=True` on the field (Studio's only "required"); the panel shows a link
"Per-role or per-stage rules: open Field Requirements" (the overlay provides the action xmlid
`health_landing.action_admin_field_req` through a parameter `biz_form_studio.required_rules_action`;
core shows the link only when the parameter is set).

### 3.6 Studio button (C4) and entry
`studio_button.xml`: `t-inherit="web.FormView" t-inherit-mode="extension"`, xpath into
`//t[@t-set-slot='control-panel-additional-actions']` (verify the exact slot node in the server
template) `position="before"`: `<button t-if="fsCanEdit" class="btn btn-secondary o_fs_studio_btn"
t-on-click="openFormStudio" t-att-title="…"><t t-out="fsIcon"/> <span>Studio</span></button>`.
`studio_button.js`: `patch(FormController.prototype, { setup(){ super.setup(); this.fs =
useState({canEdit:false}); const svc = useService('form_studio'); onWillStart(async () => {
this.fs.canEdit = await svc.canEdit(this.props.resModel, this.env.config.viewId); }); },
get fsCanEdit(){…}, get fsIcon(){ return ic('wand-sparkles', 15); }, openFormStudio(){
this.actionService.doAction({type:'ir.actions.client', tag:'biz_form_studio.studio',
params:{model, view_id, res_id: this.model.root.resId}}) } })`. The service memoises
`probe` results per `(model, view_id)` for the session (`Map`), and `probe` never raises. In
dialogs (`this.env.inDialog`) the button is never shown. Skip entirely when `env.config.viewId`
is falsy.

### 3.7 The Studio editor (C5) — client action `biz_form_studio.studio`
Layout (clone POC's Studio mode): top bar (`--bzk-ink`): "Form Studio · <screen name> ·
version N", change counter, **Discard**, **Publish**, **Back to the record** (×). Three columns:
- **Left panel** tabs "New field" (10 type tiles, Money dimmed with reason when `!money_ok`,
  each draggable) / "Fields not shown" (custom fields that exist but are not placed).
- **Centre** schematic: one `fs-card` per host section (open, with a drop zone) + locked zones
  dimmed with their reason + each Studio section (title editable inline, delete section when
  empty, drag to reorder sections among Studio sections only) + "Add a section" button. A
  field chip shows label, type icon, small badges: `custom`, shield when `phi`, eye-off when
  `vis != all`, "nurse app" when `pwa`. Standard fields appear as grey chips with a lock
  (reason tooltip) — not draggable in H1. HTML5 drag-and-drop (as POC); keyboard fallback:
  "Move up / Move down / Move to section…" buttons in the right panel (a11y).
- **Right panel** field settings: Label, Help text, Type (read-only after creation), Options
  editor (selection), Link target (m2o, read-only after creation), Required (switch), Who sees
  it (segmented: Everyone / Staff / Admins), Health information (switch; when on: shield,
  `list_ok` forced off, note "hidden from lists, exports, reports and the nurse app"; on this
  module's screens it also says "encrypted on the Client record only"), Nurse app (switch),
  Show in lists (switch; disabled while PHI), Vietnamese label (text), "Delete this field…"
  (danger) → sheet with references + value count + typed DELETE.
- **Publish sheet**: list of changes (+ fields, − fields, moved, renamed) then "Publish for
  everyone". Success toast "Published. Everyone sees it on their next page load." then
  `doAction` back to the record (`ir.actions.act_window`, `res_model`, `res_id`, `views
  [[view_id,'form']]`) — the form re-fetches its views (the `view_service` cache must be
  cleared: call `this.env.services.view.clearCache?.()` if it exists in Odoo 19, else reload the
  action with `{clearBreadcrumbs:false}` and, if the old arch still shows, `window.location
  .reload()` — measure which is needed and report).
- **History**: "Previous versions" popover → "Go back to version N" → `rollback`.
- Draft autosave: `save_draft` debounced 800 ms; on open, if a draft exists newer than the
  published version offer "Continue your draft / Start from the published layout".
- One-time PHI warning (text/file) as a `bzk-note` in the right panel with "Got it".
- Root: `display:flex; width:100%; height:100%` (§5.52). All strings `_t`.

### 3.8 Field library (C6) — client action `biz_form_studio.library`
Table (`.bzk-table`): Screen (host title = model `_description` via `ir.model.name`), Field
label, Type, Who sees it, Health info, In lists, Nurse app, Filled (count non-empty / total,
via one `read_group` per model — guard with `AccessError` catch → "—"), Created by/when,
button "Open in Studio" (opens the host's Studio with the first record of the model, or the
Studio in "no record" mode: the editor must work without `res_id` — the schematic does not
need record values). Filter by screen. Empty state: "No custom fields yet. Open a Client,
Contact, Booking or Incident screen and press Studio." (that sentence is OVERLAY copy — core
says "Open a screen that supports Studio and press Studio"; the overlay passes its own
sentence via a parameter `biz_form_studio.library_empty_hint`, or core reads host titles
dynamically: "Open one of: <host titles> and press Studio" — do the dynamic one).

### 3.9 Bus (optional)
If `self.env.user._bus_send('biz_form_studio/published', {model, view_id, version})` for every
user is awkward, skip the bus: other open tabs see the new layout on their next load, and the
publishing tab reloads itself. Report which you did.

### 3.10 Security (C7)
- ACL: `fs.host`, `fs.link.target`: read for `base.group_user`; write/create/unlink
  `base.group_system`. `fs.field.meta`, `fs.layout`, `fs.layout.draft`, `fs.layout.history`:
  read for `base.group_user` (the facade filters what is shown), create/write for the gate
  group — but the gate group is a PARAMETER, so ACL rows cannot name it: give create/write/
  unlink to `base.group_system` and perform all facade writes `sudo()` after `_check_gate`.
  `fs.layout.draft`: a record rule `user_id = user.id` for non-system users.
- Every facade method: `_check_gate(model)`; `probe` is the only one that swallows errors.
- `delete_field` and `publish` are `@api.model` and log who did it (`env.uid`, §5.154).

### 3.11 Overlay (C8) — `health_form_studio`
`data/fs_parameters.xml` (3 `ir.config_parameter` + `required_rules_action`); `data/fs_hosts.xml`:
Incident host (`model='health.incident'`, `base_view_xmlid='health_incident.view_health_incident_form'`,
`kit='vu'`, `sections=[…named groups if any…]`, `locked_fields={name: 'Identifies the incident on
every report.', state: 'Drives the incident workflow.', client_id: 'Links the incident to the
client record.', incident_datetime: 'Used for statutory reporting deadlines.'}`,
`locked_zones=[{name:'button_box', title:'Counters', reason:'Drawn by the system.'}]`);
`data/fs_link_targets.xml`; `data/cms_sidebar.xml`: `cms.sidebar.item` "Form Studio" →
`section_admin`, sequence 85 (between Field Requirements 90 and Settings 70? — Settings is
70 and Field Requirements 90: use 88), icon `fa fa-magic` (the `cms.sidebar.item.icon` IS a
font-awesome class by contract — memory rule exception), `action_xmlid =
biz_form_studio.action_fs_library`, `action_tag = biz_form_studio.library`, `biz_role_ids` =
Owner + Admin; `i18n/vi.po`; `hooks.py` `post_init_hook` → `fs.studio.reapply_visibility()`;
tests (§5 T13–T16).

### 3.12 Copy (EN → VI; keep consistent with existing catalogues)
| EN | VI |
|---|---|
| Studio | Studio |
| Form Studio | Form Studio |
| New field / Fields not shown | Trường mới / Trường chưa hiển thị |
| Text, Long text, Whole number, Decimal, Money, Yes / No, Date, Date and time, Dropdown, Link to a record, File | Văn bản, Văn bản dài, Số nguyên, Số thập phân, Tiền, Có / Không, Ngày, Ngày và giờ, Danh sách chọn, Liên kết bản ghi, Tệp |
| Who sees it · Everyone · Staff · Admins | Ai được xem · Mọi người · Nhân viên · Quản trị |
| Health information | Thông tin sức khỏe |
| Do not put health information in a field that is not marked as health information. | Không nhập thông tin sức khỏe vào trường chưa được đánh dấu là thông tin sức khỏe. |
| Show in lists / Nurse app | Hiển thị trong danh sách / Ứng dụng điều dưỡng |
| Required | Bắt buộc |
| Publish / Publish for everyone / Discard / Back to the record | Xuất bản / Xuất bản cho mọi người / Hủy thay đổi / Về bản ghi |
| Published. Everyone sees it on their next page load. | Đã xuất bản. Mọi người sẽ thấy khi tải lại trang. |
| Add a section / Section title | Thêm mục / Tên mục |
| Delete this field… / Type DELETE to confirm / This field has values on %s records. | Xóa trường này… / Gõ DELETE để xác nhận / Trường này có dữ liệu trên %s bản ghi. |
| Previous versions / Go back to version %s | Phiên bản trước / Quay về phiên bản %s |
| Drawn by the system. | Do hệ thống tạo. |
| This layout is switched off because the screen changed. Open Studio to repair it. | Bố cục này đã tắt vì màn hình thay đổi. Mở Studio để sửa. |
| You do not have access to Form Studio for this screen. | Bạn không có quyền dùng Form Studio cho màn hình này. |

## 4. Safety rails
1. Gate on every facade method; `sudo()` only after the gate; `probe` never raises.
2. Name validation before `ir.model.fields.create`; create inside a savepoint; publish is one
   RPC = one transaction.
3. Writer anchors only on `@name`, `//sheet`, `//sheet/notebook`; never `@string`, never
   positional indexes; every referenced field verified to exist on the model.
4. `_check_xml` on every publish (implicit in the view write) + `validate_all()` for upgrades;
   a broken layout deactivates ITSELF, never the base view.
5. Type immutable; options add/rename only; delete requires typed DELETE and zero blockers;
   layouts referencing the field are republished BEFORE the unlink.
6. PHI ⇒ `list_ok=False` + marker; text/file one-time warning (owner decision — must stay).
7. Audit: every publish/rollback/field create/update/delete posts a chatter message on
   `fs.layout` (field events on the layout of that model/view, or on a per-model "catch-all"
   layout row created lazily) naming `env.user`.
8. White-label + generic-source gates as tests.
9. Nothing in the PWA, portal, API, FHIR, exports changes in H1.
10. Assets: no `min()/max()` around `calc()` in plain properties (§5.148); after deploy
    confirm the backend bundle compiled and that the served bundle contains your symbols
    (§5.147/§5.200).

## 5. Tests (numbered; `@tagged('post_install', '-at_install')`)
`biz_form_studio/tests/test_fs_core.py` (use `health.incident` only through the overlay tests;
core tests use `res.partner` as a neutral model with a throwaway `fs.host` on
`base.view_partner_form` created in `setUpClass`):
1. `create_field` char → `ir.model.fields` row `state='manual'`, name `x_fs_<slug>`, column
   exists (`SELECT column_name FROM information_schema.columns`), `fields_get` returns it,
   meta row exists. Vietnamese label "Khung giờ ưu tiên" → slug `x_fs_khung_gio_uu_tien`.
2. Slug collision → `_2`; a 60-char label → name ≤ 63; invalid chars stripped.
3. selection with 3 options → `selection_ids` 3 rows; `update_field` adds a 4th, renames one;
   removing one with existing values is refused with the count.
4. many2one to a model NOT in `fs.link.target` → refused; to a listed one → `relation` set;
   required → `on_delete='restrict'`.
5. monetary on a host without `currency_id` → refused; with (`res.partner` has none — use a
   second throwaway host on `account.move` only if installed, else skip with `skipTest`).
6. **Visibility**: `vis='admin'` → as a user with only `base.group_user` (create one),
   `fields_get()` lacks the field and `read([name])` raises `AccessError`; `vis='all'` →
   visible. (Set the parameters to `base.group_system`/`base.group_user` in the test.)
7. Rename label → `get_field_string` (health_tenant_workspace, if installed) returns the new
   label (cache cleared by the registry rebuild).
8. `publish` with one section of two fields → `ir.ui.view` created (`mode='extension'`,
   `inherit_id`, `priority=200`), `get_combined_arch()` of the base view contains
   `group[@name='fs_<id>']` with both fields; version 1; history row; chatter message; draft gone.
9. Publish again moving a field → version 2; `rollback(1)` → arch equals history 1's arch.
10. `validate_all()` with a layout whose anchor was removed (simulate: write a layout with
    `anchor card 'nope'` directly) → `state='broken'`, view `active=False`, base view still
    renders (`get_combined_arch()` succeeds), reason stored.
11. `delete_field`: without `confirm='DELETE'` refused; with a blocker (an `ir.exports.line`
    for it) refused and named; after removing the blocker → layouts republished without it
    (combined arch lacks the field) THEN field gone (`fields_get` lacks it); the value count
    reported before deletion equals `search_count`.
12. Source gates (`TestSourceGates` clone): no forbidden words in `biz_form_studio` sources
    (list from `biz_access/tests/test_access_generic.py:259`, plus "Carejiox", "clinic",
    "nurse", "patient"); every `ic('…')` name exists in `IC`; no `.then(` without `.catch(`
    in `onWillStart` bodies; no `font-family` in your SCSS.
`health_form_studio/tests/test_fs_health.py`:
13. Parameters resolve to existing groups; host resolves; `fs.link.target` models all exist in
    the registry.
14. Gate: a clinic admin (user in `health_access.group_clinic_admin` only) can `get_studio` on
    the Incident view and `publish`; a head nurse (`health_base.group_healthcare_head_nurse`)
    gets `AccessError` on `get_studio` and `{host: False}` from `probe` (no exception).
15. End-to-end on Incident: create a char + a selection + a link (Staff member) field, publish
    one section; `get_combined_arch()` of `health_incident.view_health_incident_form` contains
    the section; `health.incident.create({...required fields...})` with values in the new
    fields round-trips; `vis='staff'` field invisible to a user with no healthcare group.
16. Sidebar row exists in `section_admin` with Owner+Admin roles; its action resolves;
    i18n: `health_base` `test_i18n_catalogues` green for both new modules; no "Odoo" in any
    `.po` msgstr.
Run: full `biz_form_studio`, `health_form_studio`, `health_incident`, `health_base`
(i18n), `biz_access` (source gates untouched) on the clone. Pre-existing failures: list them
with evidence that they fail on the clone WITHOUT your change too.

## 6. Browser QA (chrome-devtools, clone first, then live) — evidence to `docs/handovers/formstudio/fs_h1_shots/`
Persona A = a user holding exactly `health_access.role_admin` (create on the clone; on live
use a temporary QA user, remove afterwards §5.34, check append-only logs §5.128 first).
Persona B = a nurse. Path every time: sign in → sidebar Clinical → Incidents → open an incident.
1. A: the **Studio** button is in the top bar next to the cog; B: no button. Screenshot both.
2. A: press Studio → editor opens with the Incident schematic, locked chips greyed with
   reasons, palette on the left, empty right panel. 1440 px screenshot + console log.
3. Drag "Dropdown" into "Add a section" → section "Follow-up" → options "Phone call", "Home
   visit", "None"; drag "Text" into the same section → label "Family informed by"; set Who
   sees it = Staff; drag "Link to a record" → Staff member, label "Nurse on duty". Right panel
   screenshots for each.
4. Publish → sheet lists 3 additions → confirm → toast → back on the incident: the new card
   "Follow-up" is a VU card with the three fields, editable; save a value; reload; value
   persists. Screenshot.
5. Sign in as B: the Incident form shows "Follow-up" with the dropdown and the link, but
   NOT "Family informed by" (staff-only … wait: B IS staff → it shows; use Who sees it = Admins
   for the test and verify B does not see it). Screenshot + confirm `fields_get` via console
   `odoo.__WOWL_DEBUG__` or an RPC.
6. Field library from the sidebar (Admin › Form Studio): three rows, Filled counts, "Open in
   Studio" works. B does not see the sidebar row.
7. Delete "Family informed by": sheet shows "values on 1 record", type DELETE → gone from the
   form and the library.
8. Previous versions → go back to version 1 → the form shows version 1's layout.
9. Vietnamese user: the editor and the warning read Vietnamese.
10. Width 1100 px and 820 px: the editor stacks (palette above, settings below); no horizontal
    scroll. Pixel pass: chip heights equal, drop zones aligned, no clipped text.
Live (after install on carejiox): steps 1, 2, 6 (read-only — do NOT publish a layout on live
unless the owner asks), then remove the QA user.

## 7. Deploy (one sitting)
1. Clone `carejiox` → `carejiox_fs1` (+ filestore; neutralise `biz.tenant`, jobs off), restart
   its unit, `-i biz_form_studio,health_form_studio` there, run §5, QA §6 1-10.
2. Backup live: `pg_dump -Fc` of `carejiox`, `carejiox_template`, `hhh` → `/var/backups/fs1/`.
3. `COPYFILE_DISABLE=1 scp` both modules → `carejiox-deploy -d -i biz_form_studio,health_form_studio`
   (master), then `-D carejiox_template -i …`, then `-D hhh -i …`. Template jobs off afterwards
   (§5.178/§5.192).
4. Verify: `/web/login` 200 on carejiox.com and hhh.carejiox.com; backend bundle compiled; served
   bundle contains `o_fs_studio_btn`; live QA §6 1, 2, 6.
5. Drop the clone and its filestore (§5.218).

## 8. Report back (write `docs/handovers/formstudio/FORM_STUDIO_FS-H1_REPORT.md`, commit, paste)
Per test PASS/FAIL with the assertion; suite counts; every deviation from this doc with why
(expected: the exact `check_access` name, the `_get_manual_field_data` branch taken, the
`web.FormView` slot node you anchored on, bus done or skipped, how the form re-fetched its
views after publish); incident arch `<group name>` findings and the host sections you
declared; new ledger entries appended to HANDOVER-CONVENTIONS §5 (after §5.264); commit
hashes; evidence folder listing; what FS-H2 (Client + Contact on the Workspace kit) needs
from the kit or the core — concrete.
