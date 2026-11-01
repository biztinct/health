# FORM STUDIO (health19) — study, design and handover seed

Written 2026-11-02 by Fable in the Payobook repo session (`/Users/adity/Documents/GitHub/gitlocal`,
branch `19.1`) for the health19 repo (`/Users/adity/Documents/GitHub/health19`, branch `19.0`).
Owner's ask: "do the same study and design [as Payobook's Form Studio] for health19, which has a
similar framework of premium screens; produce the design document for handover and copy the
artefacts needed to implement it."

Status: **DESIGN ONLY. Nothing built. No owner go yet.** Per-phase handovers (`FORM_STUDIO_FS-H1_*.md`
…) are written when the build starts. Read `docs/strategy/HANDOVER-CONVENTIONS.md` before any phase.

Artefacts in this folder:
| File | What |
|---|---|
| `FORM_STUDIO_PROGRAM.md` | this document — verdict, verified plumbing, design, phases, decisions |
| `FORM_STUDIO_POC.html` | clickable concept for health19 (Client record on the Workspace kit, Bookings list, Field library). Published: https://claude.ai/artifact/4vy2Xi8zz2NKDQnYh3VLx4 |
| `from_payobook/PAYOBOOK_FORM_STUDIO_DESIGN.md` | the sibling engineering design (same engine idea; different screen integration) |
| `from_payobook/PAYOBOOK_FORM_STUDIO_POC.html` | the sibling concept page, for comparison |
| Owner report (plain English, Payobook study) | https://claude.ai/artifact/3fUhRHoF2HUXk3yQ9NwkT2 — §2 (best-in-class survey) and §3 (Odoo mechanisms) apply to health19 unchanged |

---

## 0. The one-paragraph verdict

Form Studio is **easier on health19 than on Payobook**. Payobook's premium screens are hand-coded OWL
cockpits with no layout file, so every screen there needs a "custom fields" slot built in code.
health19's premium record screens — the Booking, Client and Contact workspaces, the invoice, and
every clinical record — are **native Odoo form archs** dressed by the VU form engine and the
Workspace kit. That means Studio can work the way Odoo's own Studio does: create a real field
(`ir.model.fields`, `state='manual'`, `x_` prefix) and place it with an **inherited view** that
Studio owns. The engine cards every `<group>` automatically, the fold tray hides empty cards, and the
same inherited-view trick adds `optional=` columns to the native lists. What still needs code is a
short list: the three Workspace screens' fold-tray dicts, the hand-coded boards/wizards/PWA (which
stay curated by design), a column-order default, and the reach into BI, exports and the nurse app.
The engine should be built as a **generic core (`biz_form_studio`) plus a thin health overlay
(`health_form_studio`)**, the same split as access and tenancy, so Payobook can later adopt the core.

---

## 1. Verified plumbing (2026-11-02 — do not re-derive; re-check file:line before coding)

All paths relative to `addons/` unless stated.

### 1.1 Form engine and skins
- VU engine: `health_theme/static/src/js/vu_form_compiler.js` (188 lines), `vu_form_renderer.js`,
  `vu_form_hero_registry.js`, `vu_form_state.js`; SCSS `health_theme/static/src/scss/vu_form_engine.scss`,
  `vu_tokens.scss`. Every native `<form>` gets `.vu-form` at render time.
- `VU_EXCLUDED_MODELS` (`vu_form_renderer.js:16`): `res.config.settings`, `base.module.update`,
  `base.language.install`, `ir.module.module`. Engine off in dialogs, x2many subviews
  (`compiler:122`), `SettingsFormCompiler`, and under the kill-switch (`vu_form_engine` session
  param / localStorage, `renderer:55-63`).
- `VU_NO_HERO_JS_CLASS` (`compiler:32-44`): `fin_invoice_form_view`, `ops_booking_form`,
  `ops_client_profile_form`, `crm_contact_form_view` — skinned, own hero.
- Only `vu-form-native` opt-out: `vu.theme` (`health_theme/views/vu_theme_views.xml:24`). No
  `vu-no-hero` classes in XML.
- **Every inner `<group>` becomes a card**: `compileGroup` (`compiler:165-187`) adds `vu-sec` +
  `vu-ico-<icon>`; `.o_inner_group.vu-sec` → card (`vu_form_engine.scss:354`), hidden when all cells
  empty. Icon by title keyword (`vu_form_hero_registry.js:20-51`).
- **Workspace screens build cards differently**: `<div class="vu-detail-card ws-card" name="…">
  <div class="vu-card__title">…</div><group>…</group></div>` inside `.ws-pack`
  (booking: `health_fieldservice/views/health_fieldservice_order_views.xml:1350-1450`). Groups
  inside `.vu-detail-card` are flattened (`vu_form_engine.scss:381-389`). **An injected section on
  a Workspace screen must copy that `div` + title markup** to look native; a bare titled group still
  cards, in the older style.
- Workspace kit: `ws_workspace.scss`, widgets `ws_journey`, `ws_fold_tray`, `ws_compact_bar`,
  `ws_rail_fold`, `ws_statusbar_more` (all `health_theme/static/src/js/`). `ws_fold_tray` reads a
  **card→fields dict written into the arch options** (booking `:1454`, client
  `health_fieldservice/views/ops_client_profile_form_views.xml:239`); the widget itself is generic.
- **No VU list skin**, no `ListRenderer` patch. Lists = stock + global CSS
  (`backend_02_chatter_components.scss:532`, `backend_04_typography_responsive.scss:48-54`).

### 1.2 The three Workspace record screens (A, native arch + js_class controller)
| Screen | Model | Arch | Controller | Hard-coded lists a new field misses |
|---|---|---|---|---|
| Booking | `health.fieldservice.order` | `health_fieldservice_order_views.xml:1002` (`js_class="ops_booking_form" class="ws-workspace"`, view id 5015 live, `mode=primary`) | `health_fieldservice/static/src/js/ops_booking_form.js` | fold-tray dict `:1454`; glance `ws_booking_glance.js` (curated `record.data` keys) |
| Client | `res.partner` | `health_fieldservice/views/ops_client_profile_form_views.xml:10` — **priority 0, the default form for every `res.partner`** | `ops_client_profile_form.js` | fold-tray dict `:239`; `ws_client_panels.js` |
| Contact | `crm.lead` | `health_crm/views/crm_center_views.xml:81` | `health_crm/static/src/js/crm_contact_form.js` | `ws_contact_panels.js` |

Live extensions of the booking view (7 inheriting views from invoicing, redinvoice, pricing,
migration, careplan, family_link, telehealth) anchor on `div[@name=…]` cards and `//notebook` —
see `WORKSPACE_WS1_BOOKING.md §2`. Those `name=` anchors are stable by contract; Studio must
anchor on the same kind of thing (§3.4).

### 1.3 Existing "custom-field-like" mechanisms (none is a field builder)
- `health_forms` = clinical questionnaire engine (FHIR Questionnaire): `health.form.template`
  (`schema_json`, versioned), `health.form.question` (types at `models/health_form_question.py:11-19`),
  `health.form.instance` (`answers_json` + `schema_snapshot`, `health_form_instance.py:36,50`);
  OWL widget `health_form_renderer` + PWA runners. **Stays a separate world** (answers, not fields).
- `health_field_requirements` = "required" per model/field, global or per `biz.access.role`
  (`job_role_id`), optionally per state. Model `field.requirement.rule`
  (`models/field_requirement_rule.py:16-87`); applied via `ir.ui.view._postprocess_access_rights`
  (`models/ir_ui_view.py:19`) and a `base` create/write override (`models/base_model_override.py:20-42`).
  Dashboard model list curated (`tile_model_map`, `:236`); **field list dynamic from every form arch
  of the model** (`get_model_fields_config`, `:371`) → a Studio field placed in a view appears there
  automatically. Gated `base.group_system`.
- Runtime creation: nothing in custom code creates `ir.model.fields`, uses `state='manual'`,
  `fields.Properties`, `web_studio`, or writes `ir.ui.view.arch` at runtime.
  `health_tenant_workspace/models/ir_model_fields.py` debrands labels (per-model ormcache — **Studio
  must invalidate it on label writes**).
- Properties fields only in vendored stock (`crm.lead.lead_properties`, `project.task`, `product.template`,
  `hr.employee`). None on `res.partner`, `health.fieldservice.order`, any health model. Not used.
- Core models: client = `res.partner` (`health_base/models/res_partner.py:40`; `health.patient` does
  NOT exist despite `design/CLAUDE.md`), contact = `crm.lead`, booking = `health.fieldservice.order`
  (`health_fieldservice/models/health_fieldservice_order.py:82`), care plan `health.careplan`,
  clinical note `health.clinical.note`, incident `health.incident`, roster `health.roster.grid`.

### 1.4 Lists and columns
- Premium lists are native `<list js_class=…>`: `ops_booking_list_view` (3/11 optional),
  `ops_client_list_view` (8/14), `crm_contact_list_view` (6/12), `crm_activity_list_view`,
  `fin_invoice_list_view` (1/10). Controllers only add chrome (`ops_booking_list_view.js`).
- Column chooser = stock optional-columns menu, per browser in localStorage
  (`web/static/src/views/list/list_renderer.js:143,1182`). No `res.users.settings` use, no saved
  views, no filter kit.
- Sidebar Bookings/Clients point at the native lists (`health_cms_sidebar/data/cms_sidebar_items_ops.xml:19,30`);
  `ops_booking_queue` / `ops_client_list` OWL boards are legacy, deep-link only (`fields` arrays
  hard-coded `ops_client_list.js:98`, `ops_booking_queue.js:135`).
- Census (inventory agent): 213 list archs, 88 with `optional=`; 181 full-page form archs (~115 on the
  live menu); 76 dialog/wizard forms (B); ~18 C pages, ~16 D sheets, ~37 F boards, 9 G wizards;
  PWA = 8 Vue screens + ~13 bottom sheets, all curated JSON.

### 1.5 Catalogues a new `x_` field must reach
| Consumer | Today | Studio action |
|---|---|---|
| `biz_bi` datasets | dynamic but manual: `action_scan_fields` (`biz_bi/models/bi_dataset.py:123`) via `_fetch_schema_odoo` (`bi_source.py:172`); skips json/properties/m2m/o2m; seeded datasets curated (`biz_bi_health/hooks.py:146-165`, hides uncurated text dims) | call the scan on publish for datasets on that model; PHI fields excluded |
| `bi_studio`, `biz_analytics`, `synconics` | dynamic (`_fields` / `ir.model.fields`) | nothing |
| `health_field_requirements` | dynamic from form archs | nothing (Studio links to it for per-role rules) |
| Stock Export | dynamic | PHI fields must be excluded (§3.6) |
| `health_api_gateway` (`controllers/api_v1.py:40,61`), FHIR serializers, `health_migration`, PHI encryption set (`health_phi_encryption/models/res_partner.py:53-95`), `health_learn` | curated | out of scope for release 1; PHI flag registers the field with the encryption set (§3.6) |
| PWA (`health_pwa/controllers/api.py`) | curated JSON | FS-H4: a `custom_fields` block on client + booking payloads, read-only |
| `biz_access` | group-level only | field visibility = `ir.model.fields.groups` (§3.5) |

### 1.6 Names, entry points, gating, tokens
- "Studio" taken: BI Studio (`bi_studio`), Theme Studio (`health_theme.theme_studio`), Live Studio
  (`channel_golive_studio`). **"Form Studio" / `form_studio` free.**
- Sidebar rows: `health_cms_sidebar/data/cms_sidebar_items_admin.xml` (Field Requirements `:79`,
  Settings `:89`); placement/gates in `health_cms_ia/hooks.py` (`MOVE` `:264,:276`, `EXACT` `:350`).
  Settings hub tiles hand-coded: `health_landing/static/src/xml/admin_settings.xml:12-48`.
- Gates: `base.group_system` = **platform admin only** (not tenant clinic admins);
  `biz_access.group_access_manager` (`ACCESS_MANAGE_GATE`, `biz_access/static/src/js/access_palette.js:54`);
  `health_access.group_clinic_admin` (`health_access/security/health_access_security.xml:32`,
  implies `health_base.group_healthcare_admin` + access manager); menu roles `health_access.role_owner`
  / `role_admin` (`health_cms_ia/hooks.py:79-80`).
- Tokens: primary `#1565C0` (`--vuf-primary`, `vu_tokens.scss:16`; `--vu-brand-primary`
  `primary_variables.scss:218`), secondary `#42A5F5`, accent `#FB8C00`, hero navy `#0F1E45`, soft
  `#E8F0FB`, ink `#101728`; radius 10/12/16; font Inter → Segoe UI fallback (no @font-face);
  **flat mono colours, no gradients** (`vu_tokens.scss:8`). Prefixes: `vu-*`, `ws-*`, `ops-*`,
  `bzk-*` (biz_kit). Icons: CSS-mask Lucide (`health_theme/static/src/img/lucide/`), biz_kit `kit_icons.js`.
- Multi-DB: master `carejiox`, template `carejiox_template`, tenants (`hhh`, …); shared addons tree;
  deploy only via `carejiox-deploy` (conventions §2); `dbfilter = ^%d$`.

---

## 2. How health19 differs from Payobook, and what it changes

| Topic | Payobook | health19 | Consequence for Form Studio |
|---|---|---|---|
| Premium record screens | hand-coded OWL cockpits/drawers (hard-coded dicts) | native archs + VU engine + Workspace kit | **No per-screen slot.** Studio writes an inherited view; the engine cards it. Only the fold-tray dict needs a hook. |
| List screens | OWL boards, no column model | native lists with `optional=` | Studio adds `<field optional="hide">` by inherited list view; stock chooser does per-user. Column ORDER default = arch order Studio writes. |
| Descriptor precedent | Contract 360 `_TERMS` + `CdEditor` | none needed | drop the "generic field grid" component from the plan |
| Field visibility | groups on field | same, but roles are clinic roles | map `all / staff / admin` → `health_access` groups (§3.5) |
| Sensitive data | pay figures (locked) | **PHI** (encryption, exports, portal) | a `phi` flag with hard consequences (§3.6) |
| Required rules | none | `health_field_requirements` already does per-role/state | Studio's "Required" = plain `required`; link to Field Requirements for the rest. Do not duplicate. |
| Admin identity | tenant admin = `base.group_system` | `base.group_system` = platform only | gate on `health_access.group_clinic_admin` (owner decision 1) |
| Self-service | /my portal (employee) | family portal (`/my/care/<token>`), nurse PWA | custom fields never reach the portal in release 1; PWA read-only in FS-H4 |
| Formula engine | custom fields can feed pay rules | n/a | no "formula_ok"; instead "BI-visible" and "nurse app" toggles |
| Multi-tenant | yes | yes (+ golden template) | template layouts seed new tenants; Studio views are DB records (survive `-u`) |

---

## 3. Architecture

### 3.1 Module split
- **`biz_form_studio`** (generic core; depends `web`, `biz_kit`, `mail`): field service, layout
  writer, Studio overlay UI, Field library, audit. No product strings, no product groups —
  everything product-specific comes through hooks/parameters (same rule as
  `PORT_FROM_PAYOBOOK_TENANCY_AND_ACCESS.md`: generic core + thin overlay).
- **`health_form_studio`** (overlay; depends `biz_form_studio`, `health_theme`, `health_access`,
  `health_fieldservice`, `health_crm`): the locked-field registry for health models, the Workspace
  section markup, the fold-tray hook, PHI integration, PWA block, sidebar/Settings entry, Vietnamese.

### 3.2 Storage — manual `ir.model.fields` (decided for Payobook; same answer here)
`create_field(model, spec)` → `ir.model.fields.create({name:'x_fs_<slug>', model_id, ttype,
field_description, help, state:'manual', store:True, copied:False, selection_ids|relation,
tracking:False, groups})` inside a savepoint. Manual fields on CE: real column, ORM-visible, picked up
by `fields_get`, Export, `health_field_requirements`, dynamic BI. **Type is immutable after publish.**
Rejected: `fields.Properties` (not on `res.partner`/FSO; invisible to `biz_bi`; no per-field groups).

Field metadata (`fs.field.meta`): `field_id` (cascade), `vis` (`all|staff|admin`), `phi` (bool),
`pwa` (bool), `list_ok` (bool), `label_vi`, `help_vi`, `order`, `created_by`, `publish_version`.

### 3.3 Layout = one Studio-owned inherited view per (base view, company)
- `fs.layout` row per (`model`, `base_view_id`, `company_id`): `sections` Json
  `[{id, title, title_vi, icon, anchor:{kind:'card', name:'<div name>'} | {kind:'pack_end'} |
  {kind:'group', xpath:'…'}, fields:[{name, order}]}]`, `version`, `view_id` (the generated
  `ir.ui.view`, `inherit_id = base_view_id`, `mode='extension'`, `priority=200`, `name='Form Studio: <model>'`,
  `key='biz_form_studio.<model>.<company>'`, `active=True`).
- **Writer** (`fs.layout._render_arch()`): deterministic XML from `sections`. For Workspace screens
  (hosts declaring `kit='ws'`), a new section renders as
  `<xpath expr="//div[@class='ws-pack']" position="inside"><div class="vu-detail-card ws-card fs-card"
  name="fs_<id>"><div class="vu-card__title">…</div><group><field name="x_fs_…"/>…</group></div></xpath>`;
  placing into an existing card = `<xpath expr="//div[@name='<card>']//group" position="inside">`.
  For plain VU forms (`kit='vu'`), a new section = `<xpath expr="//sheet/group|//sheet" position="inside">
  <group name="fs_<id>" string="…">…</group></xpath>` (engine cards it). Hiding a standard field =
  `<field name="…" position="attributes"><attribute name="invisible">1</attribute></field>` — **only
  for non-locked fields**; moving a standard field = `position="move"`.
- **Anchor contract**: Studio may anchor only on `div[@name]` cards declared by the host
  (`host.sections`), `//div[@class='ws-pack']`, `//sheet`, `//notebook/page[@name='…']`. Never on
  text, never on `[@string]` (Odoo 19 refuses `string` selectors), never on positional indexes.
- **Draft vs published**: `fs.layout.draft` per user holds unsaved `sections`; Publish renders and
  writes the view in one transaction, bumps `version`, stores the previous arch in `fs.layout.history`
  (one-click "go back"), writes an audit row (`mail.thread` on `fs.layout`), and bus-notifies
  `biz_form_studio/published` so open forms reload.
- **Upgrade safety (the rail that matters most on a shared addons tree)**: a Studio view whose
  anchor disappears after a module upgrade makes the whole form fail to load. Therefore:
  (a) `fs.layout.validate_all()` re-renders and `_check_xml`s every layout; on failure it sets the
  view `active=False`, moves orphaned fields to the `pack_end` section, and logs + emails the clinic
  admin; (b) `carejiox-deploy` gets a post-upgrade step calling `validate_all()` on every DB it
  touched (conventions §2 — add to the wrapper, ledger entry); (c) tests in `health_form_studio`
  pin the host anchors (like `health_cms_coverage/tests/test_cms_consolidation.py` pins tabs).

### 3.4 Hosts (what a screen declares to Studio)
`fs.host` records (data, per overlay): `model`, `base_view_xmlid`, `kit` (`ws|vu`),
`sections` = the open cards `[{name:'<div name>', title}]`, `locked_zones` (names shown dimmed with a
reason), `locked_fields` (see §4), `fold_tray=True/False`, `list_view_xmlid` (+ `list_pinned`,
`list_drawn` columns). Release-1 hosts: Client (`res.partner`, `ops_client_profile_form`), Booking
(`health.fieldservice.order`, `view_health_fso_form_ops`), Contact (`crm.lead`,
`view_crm_contact_form_crm_center`) and their three lists. Later hosts: `health.careplan`,
`health.incident`, `health.clinical.note`, `account.move` (invoice form is a primary inherit of
stock), each a data record + a locked list.

**Fold tray hook (the one kit change)**: extend `ws_fold_tray` to merge cards it discovers in the DOM
with `data-fs-fold="1"` (Studio-rendered cards carry it) into its card→fields map at mount, so the
"Not filled yet" chips include custom cards without editing the arch options dict. Sanctioned file:
`health_theme/static/src/js/ws_fold_tray.js` only.

### 3.5 Visibility → groups
`vis` is materialised to `ir.model.fields.groups` (ORM-enforced): `all` → none; `staff` →
`health_base.group_healthcare_user` (verify exact xmlid in `health_access`); `admin` →
`health_access.group_clinic_admin`. The family portal (`health_portal`, `health_pwa_family`) and
the self-booking pages never render custom fields in release 1 regardless of `vis` (their QWeb is
curated). "View as" in Studio is a client-side preview that hides by rank; the server is the truth.

### 3.6 PHI flag
`phi=True` ⇒ (1) field added to the encryption registry: `health_phi_encryption` exposes a hook
`_phi_extra_fields(model)` read by its `res.partner` set (`models/res_partner.py:53-95`) — add the
hook in the overlay phase, encrypted-at-rest like the curated set; (2) `list_ok` forced False and the
field never emitted to list views; (3) excluded from `biz_bi` scans and from stock Export
(`ir.exports` filter via `fields_get` override for non-admins — verify feasibility in FS-H4; if not
feasible, Export remains admin-only for PHI fields and the report says so); (4) a shield marker in
the UI. Text-type custom fields default to a one-time warning "do not put health information in an
unmarked field".

### 3.7 Lists
- Studio list mode edits `fs.list.layout` per (list view, company): ordered `columns[{name, on, width,
  sort}]`. Writer emits an inherited list view: new custom columns as `<field name="x_fs_…"
  optional="hide|show"/>` positioned after the last column; default order = `position="move"` of
  existing `<field>` nodes (only for non-pinned, non-drawn columns); default sort = `default_order`
  attribute on `<list>`.
- Per-user "Just me" = stock optional-columns menu (localStorage). Cross-device per-user order is a
  later phase (`res.users.settings` key `fs_list_<view>`) — not release 1.
- Pinned/drawn columns per host: Bookings → `name` pinned, `state`/`total_price` drawn; Clients →
  `name` pinned, `catchment_id` drawn; Contacts → `name` pinned, `stage_id` drawn.
- Legacy OWL boards (`ops_booking_queue`, `ops_client_list`) are not hosts; they are deep-link only.

### 3.8 Client (OWL)
- `FormStudioOverlay` (biz_form_studio): mounted by a `useFormStudio(host)` hook in a small
  `FormController` patch that adds the wand button to the statusbar when `host && can_edit`;
  enters Studio mode by rendering the overlay around the live `FormRenderer` (palette left,
  properties right, dashed outline on `.o_form_sheet`), reading `fs.host` + `fs.layout.draft`.
  Drop targets = `.ws-card[name]` / `.o_inner_group.vu-sec` of declared sections; the overlay
  mutates the **draft sections JSON**, never the live DOM; Publish → server renders the view →
  `action.doAction` reload.
- `ListStudio` = same overlay in list mode (Columns panel) mounted by a `ListController` patch.
- `FieldLibrary` client action (Settings › Master data) using `bzk-*` primitives + Lucide from
  `biz_kit`.
- No new fonts; `--vuf-*`/`--bzk-*` tokens only; flat colours; Vietnamese for every string
  (`i18n/vi_VN.po` of each module).

### 3.9 Tenancy
Layouts and manual fields are per database. The golden template's layouts seed every new tenant
(clone). A tenant's own changes never flow back. `biz_tenants` "In step with master" must run
`validate_all()` after each tenant upgrade (same wrapper hook as §3.3).

---

## 4. Locked fields and zones (initial registry — overlay data)

| Host | Locked fields (rename/help only) | Reason shown | Locked zones |
|---|---|---|---|
| Client `res.partner` | `name`, `phone`/`mobile`, `street`+address block, `catchment_id` (or the catchment m2o actually used by `health_catchment_scope`), `vat`/national-id field, BHYT number field, `birthdate` | identity, routing (catchment rules), billing, insurance claims, age-based care rules | Care plan card, Billing card, glance rail, journey, Next-step banner, Clinical / Family / Documents tabs |
| Booking `health.fieldservice.order` | `partner_id`, `scheduled_datetime`, `scheduled_duration`, `state`, `assigned_staff_ids`/`lead_staff_id`, service type/package fields, `total_price`, `currency_id`, `facility_id`, catchment | scheduling, routing, pricing, statutory invoice | Services/Packages, Pricing, Payment summary, Staff assignment, Clinical notes, Telehealth, Visit tasks, Family updates tabs |
| Contact `crm.lead` | `name`, `contact_name`, `phone`/`mobile`, `email_from`, source/medium/campaign fields, `stage_id`, `user_id`, `team_id` | lead-source audit trail (contract priority), pipeline | journey, Next step, activities panel |

Exact field names to be confirmed per model in FS-H2 (grep the three archs; the catchment field is
`health_catchment_scope`'s). Locked zones are the `div[@name]` cards the host does NOT list as open.

---

## 5. Safety rails (engineering form)
1. Server gate on every `fs.*` RPC: `has_group(<overlay gate>)` + `check_access_rights('write')` on
   the target model; never `sudo()` the record writes; `ir.model.fields` create/unlink runs `sudo()`
   only after the gate passes (the admin lacks `base.group_system`).
2. `create_field` refuses outside a quiet window if a long transaction holds the table (check
   `pg_locks` on the model table; message in plain words). `ALTER TABLE ADD COLUMN` on
   `res_partner` is fast but takes an exclusive lock briefly.
3. `delete_field` reference check: `fs.layout` sections, `fs.list.layout`, `biz_bi` dataset fields,
   `ir.exports.line`, `field.requirement.rule`, `ir.filters` domains, `health_phi` registry. Blockers
   named; client-side typed DELETE; server re-checks.
4. Type immutable after publish; options of a Selection may only be added/renamed, never removed
   while values exist (offer "retire" = hidden from new picks).
5. Validator (§3.3) in the deploy wrapper and as a cron (nightly) with email on failure.
6. Audit every publish (who/when/diff) on `fs.layout` chatter + `biz.audit` if present.
7. White-label: no "Odoo" in any user-visible string. Technical name `x_fs_…` never shown.
8. Keep `health_field_requirements` the only place for per-role/state required rules.
9. Never touch the PWA, portal, API, FHIR payload shapes in release 1 beyond the explicit
   `custom_fields` block of FS-H4.

---

## 6. Phases (proposed handovers; sizes are engineering estimates)

| Phase | Ships | Depends on | Size |
|---|---|---|---|
| **FS-H1 Core** | `biz_form_studio`: `fs.field.meta`, `fs.layout(+draft,history)`, `fs.host`, writer, validator, overlay UI, Field library, audit; test host = `health.incident` form (plain VU form, hero) | — | ~1.5 weeks |
| **FS-H2 Client + Contact** | `health_form_studio` overlay: hosts, locked registry, Workspace card markup, fold-tray hook (K-change), gating on clinic admin, sidebar/Settings tile, vi_VN | H1 | ~1 week |
| **FS-H3 Booking + lists** | Booking host; Bookings/Clients/Contacts list hosts; list writer; column defaults | H2 | ~1 week |
| **FS-H4 Reach** | PHI flag + encryption hook; BI scan on publish; Export exclusion; PWA `custom_fields` read-only block on client + booking; Vietnamese label pass; `health_learn` lesson updates | H3 | ~1 week |
| **FS-H5 Hardening + tenants** | deploy-wrapper validator step; template seeding; nightly validator cron; closeout | H4 | ~3 days |
| Later | Care plan, Incident, Clinical note, Invoice hosts; cross-device per-user columns; per-field "family may see" | | 1–2 days each |

Test cases to carry into each handover (numbered there): field create/update/delete incl. blockers;
vis→groups read enforcement for a staff user; PHI consequences; writer output validates against the
live arch (`_check_xml`); fold tray shows custom card; booking's 7 inheriting views still apply after
a Studio view is active; list optional column appears and per-user hide persists; template → new
tenant seeding; validator deactivates a broken layout and emails; no "Odoo" string; vi_VN present.

---

## 7. Owner decisions

**Decided 2026-11-02 (do not re-ask):**
1. **Who may open Studio on a clinic tenant?** → **`health_access.group_clinic_admin`** (owner/admin
   roles). Not `base.group_system`, which is the platform admin on health19.
2. **PHI by default?** → **OFF by default** for every type. The admin switches it on for sensitive
   fields. Keep the one-time warning on text/file fields ("do not put health information in an
   unmarked field") — it is the only guard left, so it must stay.
3. **Build start** → **not yet.** Owner said "stop here for now" (same as Payobook). Do not launch
   FS-H1 until asked.

**Still open (ask when FS-H1 starts):**
3. **Nurse app exposure** — recommended: read-only `custom_fields` block on client + booking in
   FS-H4; editing from the PWA is out of scope.
4. **Family portal** — recommended: never in release 1 (portal pages are curated QWeb).
5. **Order** — recommended: Client + Contact before Booking (booking has 7 inheriting views and the
   densest arch; do it once the writer is proven).
6. **Field Requirements** — keep as the per-role "required" tool and link to it from Studio
   (recommended), or fold its UI into Studio later.

Carry-over from the Payobook study, already decided there and recommended here too: real fields
(not Properties); self-service = see-only.

---

## 8. Ledger candidates for `docs/strategy/HANDOVER-CONVENTIONS.md` (append when FS-H1 lands)
- Studio-owned inherited views are DB records on a shared addons tree: every `-u`/deploy must run
  the layout validator per DB or a broken anchor takes a whole form down.
- Workspace cards are `div.vu-detail-card.ws-card[name]` + `vu-card__title` + `<group>`; a bare
  `<group string>` inside `.ws-pack` cards in the old style. Fold tray reads `data-fs-fold` cards.
- `health_tenant_workspace` caches debranded field labels per model — invalidate on
  `ir.model.fields` label writes.
- `base.group_system` is the platform admin on health19; clinic self-service features gate on
  `health_access` roles.
