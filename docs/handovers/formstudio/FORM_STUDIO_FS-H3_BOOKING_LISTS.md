# FORM STUDIO — FS-H3: the Booking screen, list columns, and the editor that survives a reload

Handover from Fable (design) to Opus (implementation). Written 2026-11-03 after the FS-H2 report.
Read in this order before touching code:

1. `docs/strategy/HANDOVER-CONVENTIONS.md` — §2 deploy, §5 ledger incl. §5.265–§5.277.
2. `docs/handovers/formstudio/FORM_STUDIO_FS-H1_CORE.md` §0 (standing rules, all binding) and
   `FORM_STUDIO_FS-H2_CLIENT_CONTACT.md` §0 and §3 (the Workspace writer, reader, tray seam, header button).
3. `docs/handovers/formstudio/FORM_STUDIO_FS-H1_REPORT.md` and `FORM_STUDIO_FS-H2_REPORT.md` — what was
   built, deviations. The code is the truth where a design doc differs.
4. The engine as shipped: `addons/biz_form_studio/models/fs_layout.py` (`ANCHORS`, `_ws_pack`, `_ws_card`,
   `_render_arch`, `_write_view`, `_publish`, `_validate_one`), `fs_studio.py` (`_base_cards`, `ws_title`
   :293-301, `_field_info`, `get_studio`, `publish`, `rollback`, `validate_all`), `fs_host.py`,
   `fs_field_meta.py` (`list_ok` :25, `phi` :19), `ir_model_fields.py` (`_fs_options` callable selections),
   `static/src/js/studio/studio_editor.js` (`props.action.params` :90-93, `load()` :132-135, registration :1167),
   `studio_button.js:54-62`, `library.js:98-103`.
5. `addons/health_form_studio/` as shipped (hosts data, `HOST_TEXT`, `ws_headers.xml`, tests).

## 0. Standing rules (FS-H1_CORE §0 binds in full; the short form)

- White-label: "Odoo" never user-visible. Generic core names no product. Plain copy, `x_fs_` never shown.
- Flat tokens, `ic()` icons, no gradients/emoji/`font-family`. Vietnamese for every new string in both `vi.po`.
- Chatter untouched. Host models get no business-logic change.
- **Shared-module edits sanctioned for this phase, and ONLY these:**
  - `addons/health_fieldservice/static/src/js/ops_booking_form.js` and
    `addons/health_fieldservice/static/src/js/ops_client_profile_form.js` — ONLY to add the missing
    `navigateTo` method (§3.6), in its own commit, if the research in §2 holds.
  - `addons/biz_kit/static/src/js/kit_icons.js` — new glyphs only.
  - Nothing else outside `biz_form_studio` / `health_form_studio`.
- Rehearse on a clone `carejiox_fs3` (FS-H1 recipe). Never `-t` on the live box. `fs.studio.validate_all`
  after every upgrade on every DB. Run the suites WITHOUT `-u` after upgrading (§5.275).
- Live has 0 layouts and 0 `x_fs_` fields. On live: open Studio only, publish nothing, create no field.
- Commits on 19.0, plain sentences, each ending `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
  **Do not push.**

## 1. Scope

**Goal.** Studio works on the **Booking** record the way it works on Client and Contact. A field whose
"Show in lists" switch is on becomes a column of that screen's list (Bookings, Clients, Contacts,
Incidents), honouring who-may-see-it. Reloading the browser inside the editor brings the same screen back.

**In scope**
1. Engine: list-column writer + list extension view per layout (publish, rollback, validate), the
   `<span>` title fix in the schematic reader, list rules per type, editor URL state, copy for the
   list switch, publish sheet lines for columns.
2. Overlay: the Booking host (cards, locked fields, zones, reasons in Vietnamese), the Studio button in
   the Booking header, list host data for all four screens, vi.po.
3. Side fix (sanctioned, own commit): the dead "Dashboard" breadcrumb click on the Booking and Client
   Workspace headers (§3.6).
4. Tests 33–48, browser QA 21–30, clone rehearsal, live upgrade on `carejiox`, `carejiox_template`, `hhh`.

**Binding non-goals**
- No search filters or "Group by" entries for custom fields (native "Add custom group" already lists
  stored fields; leave it). No export / PWA / BI / encryption reach (FS-H4).
- No change to which standard columns a list shows, their order, decorations or `default_order`.
- No editable lists; no columns in kanban, calendar or the Booking status tabs.
- No Studio on the legacy booking form (`view_health_fieldservice_order_form`, priority 99), on any
  wizard, dialog, or the assignment dashboard lists.
- No touching `health_roster/static/src/xml/sidebar_inherit.xml` (report only, §2 fact 9).
- No change to the static fold-tray maps of any screen.

## 2. Verified plumbing (research 2026-11-03 — re-check lines before anchoring; do not re-derive)

Booking file `addons/health_fieldservice/views/health_fieldservice_order_views.xml` = **ORDER_VIEWS**.

| # | Fact | Where |
|---|---|---|
| 1 | Booking model `health.fieldservice.order` (inherits mail.thread, portal.mixin, health.lifecycle.mixin). Has `currency_id` (:1256, redefined `health_invoicing/models/health_fieldservice_order.py:78`) → money fields allowed. **No `company_id`.** | `health_fieldservice/models/health_fieldservice_order.py:82-84` |
| 2 | Workspace form `health_fieldservice.view_health_fso_form_ops`: primary, priority 10, `js_class="ops_booking_form"`, class `ws-workspace`; it is the model's DEFAULT form (other primary = priority 99). Pinned by `action_ops_booking_form` (`ops_center_menus.xml:62-69`), `action_ops_booking_list_native` (`ops_booking_list_views.xml:58-61`), `action_crm_bookings_calendar` (`crm_center_views.xml:803-806`) and 8 JS `form_view_ref` callers | ORDER_VIEWS:995-1002 |
| 3 | Sheet :1060; hidden dependency fields :1064-1078; `.ws-page` :1085, `.ws-main` :1086; hero :1096-1174 (no `name`); `.ws-next` :1184-1337 holds seven named hint cards with NO fields; notebook :1342; pages `overview` :1346, `clinical_notes` :1462, `planning` :1503, `execution` :1568, `tracking` :1611, `cancellation` :1624, `completion` :1651, `communication` :1682 (invisible). Inherited pages: `pricing`, `telehealth_ops`, `visit_tasks_ops`, `family_updates_ops` | ORDER_VIEWS |
| 4 | ONE `div.ws-pack` :1347 on `overview`, no `name`. Cards: `visit_card` :1350, `location_details_card` :1369, widget `vu_services_packages` :1389, `care_team_card` :1392, `commission_fees_card` :1410 (title "Pricing"), `additional_charges_card` :1427, `notes_card` :1443 (**no `<group>`**: a nolabel `patient_notes` field directly). **Last child = `notes_card` div → no `pack_tail`.** | ORDER_VIEWS:1347-1452 |
| 5 | **Booking card titles are `<span>`s**: `<span class="vu-detail-card__edit-trigger"/>` first, then `<div class="vu-card__title"><span class="vu-section__icon"/><span>Visit</span></div>`. The reader `ws_title` only reads `div` children → every Booking title comes back EMPTY today | `fs_studio.py:293-301`, ORDER_VIEWS:1350-1356 |
| 6 | Two cards from other modules land inside the pack via `position="after"` on `location_details_card`: `payment_summary_card` (health_invoicing :268, `vu-detail-card` no `ws-card`, invisible unless invoiced/paid) and `legacy_audit_card` (health_migration `legacy_views.xml:16`, invisible unless `legacy_booking_ref`). A test pins them in the pack: `health_fieldservice/tests/test_ws_booking_form.py:261-266`; another fixes the tray map card set :322-326 | those files |
| 7 | Fold tray :1454-1458 with static map care_team / commission_fees / additional_charges / notes. Discovery of `[data-fs-fold="1"]` already works (FS-H2 seam) | ORDER_VIEWS, `ws_fold_tray.js:187-199` |
| 8 | Controller `OpsBookingFormController extends FormController`, template `health_fieldservice.OpsBookingFormView`; header right = `div.ops-header-right > t[@t-if='canEdit'] > FormStatusIndicator` (same shape as Client); `.o_control_panel` hidden by `ops_booking_form.scss:36-38` | `ops_booking_form.js:8-9`, `xml/ops_booking_form.xml:22-25` |
| 9 | Latent: `ops_booking_form.xml:15` `navigateTo('dashboard')` with NO `navigateTo` on the controller or any FormController patch → TypeError on click. `ops_client_profile_form.xml:12` has the same link — check whether its controller defines `navigateTo`. `health_roster/static/src/xml/sidebar_inherit.xml:31-35` patches 11 templates with xpaths that match nothing (would throw at template load if installed) — **report only; check if health_roster is installed on any of the three DBs** | — |
| 10 | Load-bearing booking fields (lock them): `state`, `stage_id`, `scheduled_datetime`, `scheduled_duration`, `estimated_end_datetime`, `assigned_staff_ids`, `lead_staff_id`, `assigned_doctor_ids`, `assignment_ids`, `patient_id`, `service_type`, `category_of_service_id`, `service_location`, `facility_id`, `catchment_province_id`, `patient_catchment_province_id`, `sale_order_id`, `invoice_id`, `service_fee_vnd`, `commission_amount`, `commission_due_to`, `commission_percentage`, `commission_duration`, `base_price`, `total_price`, `travel_charge`, `urgency_charge`, `equipment_charge`, `after_hours_charge`, `parking_charge`, `team_id`, `crm_lead_id`, `actual_start_datetime`, `actual_end_datetime`, `currency_id`, `name`, `priority`, `booking_user_id`, `patient_notes` | research table A5 |
| 11 | Lists actually opened by the sidebar: **Bookings** row → `action_ops_booking_list_native` `calendar,list,form` (users land on the CALENDAR; list second) → `view_health_fso_list_ops` (`ops_booking_list_views.xml:5`, priority 10, `js_class="ops_booking_list_view"` = ListController subclass, native renderer kept; optional cols exist; decorations :13; last visible field `priority` :28, then `has_staff_assigned` column_invisible :30). **Clients** → `view_health_client_list_ops` (`ops_client_list_views.xml:5`, **priority 0 = default partner list everywhere**, js_class, last visible `total_assignments` :27, then `invoice_status` invisible :39). **Contacts** → `view_crm_contact_list_crm_center` (`crm_center_views.xml:5`, priority 50, js_class, last visible `user_id` :32, then `deleted` :51). **Incidents** → `view_health_incident_list` (`health_incident_views.xml:152`, no js_class, last visible `open_action_count` :171, then `deleted` :173). None editable; none define `groupby` | research B8 |
| 12 | Column chooser = core; state in `localStorage` keyed on the list's field names → adding a column RESETS users' saved chooser choices for that list | `web/static/src/views/list/list_renderer.js:142-143,602-608,1181-1199` |
| 13 | Arch post-processors touching lists: `health_field_requirements/models/ir_ui_view.py:19-64` (sets `required` on `//field` for rule fields, all view types), `web_debranding` regex on arch text. Catchment scope = search arches only. No `ListRenderer` patches anywhere | research B9-B10 |
| 14 | Client action URL state: `props.updateActionState(patch)` copies keys into the URL (`action_service.js:613-626`, `makeState` :1810-1835); **`model`, `resId`, `action`, `active_id` are reserved PATH_KEYS** (`router.js:10`) and are NOT copied. On reload `params` = the URL state (:526-536). `doAction` `params` and `context` (except `active_id`) are not saved | research C13 |
| 15 | Callable selections: labels resolved via `_description_selection(env)` in `fields_get`, export, search panel; `group_expand` calls `get_values(env)` with `lang=None`; list cells / badges / group headers read `fields_get().selection` → a callable selection works in lists and group-by. Value validation is SKIPPED on write for callables (`fields_selection.py:228-230`) — accept for now, note it | research D14 |
| 16 | Export: `fields_get(…'exportable')` drops `exportable=False` fields (`web/controllers/export.py:360-398`); nothing strips PHI today (FS-H4 fact) | research B11 |

## 3. Architecture

### 3.1 Schematic reader: titles in any tag (core)
`ws_title` (and anything else reading a card title) returns `''.join(title_node.itertext()).strip()` of
`.vu-card__title`, whatever the child tags, ignoring `.vu-section__icon` content (it has none). Skip
`span.vu-detail-card__edit-trigger`. Test 33.

A card that has NO `<group>` child (Booking `notes_card`) is read as a std card but **cannot be open**:
`fs.host` constraint `_check_sections` refuses an open card whose `div[@name]` has no `group` child
(checked against the combined arch at validation time, not at data load — do it in test 41 and in
`validate_all`'s host pass, raising a clear UserError naming the card).

Cards that lack `ws-card` and come from another module (`payment_summary_card`, `legacy_audit_card`)
are listed as closed std cards with their fields — that is correct behaviour; nothing special.

### 3.2 List columns (core)

**Host declares the list.** `fs.host` gains:
```python
list_view_xmlid = fields.Char(help="The list this screen's records appear in. Empty: no list columns.")
list_anchor = fields.Char(help="Name of the last visible column; new columns go after it.")
```
Constraint: both set or both empty; at validation time the list view must exist, be `type='list'`, and
contain `//field[@name=list_anchor]`.

**Layout keeps a second view.** `fs.layout.list_view_id` (m2o ir.ui.view, ondelete set null). Written in
`_publish` right after the form view, from the SAME transaction; `fs.layout.history` gets `list_arch`.

**Which fields become columns.** Exactly those that are (a) placed in a published section of this
layout AND (b) `fs.field.meta.list_ok` is True. Order = the order they appear in the sections (section
order, then field order). `list_ok` is forced False — and the switch disabled with a reason — for
`phi` (already), `binary` ("Files cannot be list columns") and `text` ("Long text cannot be a list
column"). Everything else may be a column, including Studio dropdowns (callable selections work in list
cells, badges and group headers — fact 15).

**Writer `_render_list_arch(names, host, list_view)`:**
```xml
<data>
  <xpath expr="//list/field[@name='priority']" position="after">
    <field name="x_fs_a" optional="show"/>
    <field name="x_fs_b" optional="show" widget="badge"/>   <!-- selection → badge, as the lists' own status columns do -->
  </xpath>
</data>
```
- Anchor expression is `//field[@name='<list_anchor>']` (there is exactly one such field in a list arch;
  assert it in validation). Never a position number, never a `string`.
- `optional="show"`: the column is visible to everyone who may see the field, and sits in the column
  chooser so anyone can hide it. Say in the publish sheet: "Columns are shown to everyone; each person can
  hide them from the column chooser. Saved column choices for this list are reset by this publish."
  (fact 12 — honest copy.)
- Visibility: nothing extra — `groups` on the field (FS-H1 `_instanciate_attrs`) makes the server drop
  the node for people outside the group, in lists as in forms. Prove it in test 37.
- Money: `widget="monetary"` only when the field is monetary (the core default already); date/datetime
  left to defaults.
- No columns at all → the list view is written with an empty `<data/>` arch and `active=False`
  (never deleted while the layout exists: keeps the id stable for history/rollback).

**`_write_list_view`:** clone of `_write_view` with `type='list'`, key
`biz_form_studio.list.<model>.<company|all>`, `inherit_id=host list view`, `mode='extension'`, priority 200,
written under `lang='en_US'`. No translations needed (column labels come from the field).

**Validator:** `_validate_one` also re-renders the list arch and calls the list view's
`_get_combined_arch()` inside the savepoint; a failure switches the WHOLE layout off (form view and list
view both inactive) with the reason — one switch, one message, never a half state. `validate_all`
also reports hosts whose `list_view_xmlid` / `list_anchor` no longer resolve (as "host" problems, not
layout problems) — logged and returned, not raised.

**Rollback:** restores both arches from history. **Delete field:** `_republish_with` already republishes
without the field → columns follow. **Toggle `list_ok` on a placed field** (`update_field`) →
republish is NOT automatic (FS-H1 rule: "required" republishes; keep the same behaviour for list_ok —
check what FS-H1 did for `required` in `update_field` and mirror it exactly: if it republishes the form,
republish the list too; if it marks the draft dirty, do the same). State which in the report.

**`get_studio`** returns `host.list_title` (the list's `string` or the host title + " list") and per field
`list_ok`, `list_reason` (why the switch is disabled, or ''). **Publish sheet** gains one line per column
change: "Column added: Preferred time slot (Bookings list)" / "Column removed: …" / the reset warning
once when any column is added.

### 3.3 Editor URL state (core)
- Studio editor stores its screen in the URL with `props.updateActionState({ fs_model, fs_view: view_id,
  fs_res: res_id })` once `load()` succeeds. Key `model` is reserved (fact 14), hence `fs_model`.
- On start, read `params.model ?? params.fs_model`, `params.view_id ?? params.fs_view`,
  `params.res_id ?? params.fs_res`. A reload therefore reopens the same screen; the "Open a screen that
  supports Studio" notice remains for a truly empty state.
- Verify `updateActionState` exists on the client-action props in this Odoo build (fact 14 cites
  `action_service.js:613-626`); if a reload still loses state because the editor is opened as an inline
  action (tag, not xmlid), open it via the xmlid `biz_form_studio.action_fs_studio` with the same params
  and check the URL carries them. Test 44 is an HttpCase/tour that reloads.

### 3.4 Booking host (overlay data, `fs_hosts.xml`)
`fs_host_booking`: name "Booking", model `health.fieldservice.order`,
`base_view_xmlid health_fieldservice.view_health_fso_form_ops`, kit `ws`, `pack_page overview`, no
`pack_tail`, `pwa_label "Nurse app"`,
`list_view_xmlid health_fieldservice.view_health_fso_list_ops`, `list_anchor priority`,
sections (open cards) = visit_card "Visit", location_details_card "Location details", care_team_card
"Care team", commission_fees_card "Pricing", additional_charges_card "Additional charges"
(**not** notes_card — no group; **not** the two foreign cards).
locked_fields — every name in fact 10, grouped reasons (plain words, each in `HOST_TEXT` with VI):
- `state`, `stage_id`, `priority` "Drives the booking workflow."
- `scheduled_datetime`, `scheduled_duration`, `estimated_end_datetime` "Used by the schedule, routes and the nurse app."
- `assigned_staff_ids`, `lead_staff_id`, `assigned_doctor_ids`, `assignment_ids`, `team_id` "Decides who does the visit."
- `patient_id`, `crm_lead_id` "Links the booking to the client."
- `service_type`, `category_of_service_id`, `service_location` "Decides the service and its price."
- `facility_id`, `catchment_province_id`, `patient_catchment_province_id` "Decides which team can see this booking."
- `sale_order_id`, `invoice_id`, `currency_id`, `service_fee_vnd`, `commission_amount`, `commission_due_to`,
  `commission_percentage`, `commission_duration`, `base_price`, `total_price`, `travel_charge`,
  `urgency_charge`, `equipment_charge`, `after_hours_charge`, `parking_charge` "Used for quotes, invoices and commission."
- `actual_start_datetime`, `actual_end_datetime` "Written by the nurse app when the visit starts and ends."
- `name`, `booking_user_id` "Identifies the booking."
- `patient_notes` "Shown to the care team in the nurse app."
locked_zones = `[{name: button_box, title: "Counters", reason: "Drawn by the system."}]`. (The people
panel has no `name` on Booking — nothing to declare; the hint cards hold no fields and are skipped.)

**Other hosts get their lists:** Client `health_fieldservice.view_health_client_list_ops` / `total_assignments`;
Contact `health_crm.view_crm_contact_list_crm_center` / `user_id`; Incident
`health_incident.view_health_incident_list` / `open_action_count`. Say in the report that the Client list is
the default partner list, so a Client column shows wherever that list is used (like the form).

### 3.5 Studio button on the Booking header (overlay)
`ws_headers.xml` gets a third extension: `t-inherit="health_fieldservice.OpsBookingFormView"`, xpath
`//div[hasclass('ops-header-right')]/t[@t-if='canEdit']` position before, `t-call="biz_form_studio.StudioButton"`.
Check alignment against the Booking header CSS (`ops_booking_form.scss`) and reuse `ws_headers.scss`.

### 3.6 Side fix: the dead "Dashboard" breadcrumb (sanctioned, own commit)
If and only if the research holds (controller lacks `navigateTo`): add to `OpsBookingFormController`
(and to `OpsClientProfileFormController` if it lacks it too)
```js
navigateTo(target) {
    if (target === "dashboard") { return this.actionService.doAction("<the ops dashboard action xmlid the other breadcrumbs use>", { clearBreadcrumbs: true }); }
}
```
Find the dashboard action the Contact header's `goToDashboard` uses (`crm_contact_form.js`) and the Ops
equivalent (`health_landing` / `ops_center_menus.xml`); use the same mechanism the sibling `goToBookings`
uses. Bump `health_fieldservice` patch version. Commit message: "Booking and Client screens: make the
Dashboard breadcrumb link work". If the Client controller already has it, touch only the Booking one.

### 3.7 Copy (EN → VI in both vi.po)
- Switch label: "Show as a column in the {list} list". Disabled reasons: "Health information is never a
  column." / "Files cannot be list columns." / "Long text cannot be a list column."
- Publish sheet: "Column added: {field} ({list})", "Column removed: {field} ({list})", "Columns are shown to
  everyone who may see the field; each person can hide them from the column chooser. Saved column choices
  for this list are reset by this publish."
- Switched-off layout reason prefix for lists: "The list changed: {reason}".

Bump: `biz_form_studio` 19.0.1.2.0, `health_form_studio` 19.0.1.2.0, `health_fieldservice` patch (if §3.6).

## 4. Safety rails
- A list extension is written only after the form extension succeeded, in the same transaction; any
  failure rolls both back (`_publish` is already one transaction — keep it so).
- The list anchor is a NAME; if it disappears the layout switches off, the list keeps working.
- Never a column for PHI / binary / text; never on a list the host did not declare.
- The foreign Booking cards (fact 6) must still sit in the pack after a Studio publish —
  `test_ws_booking_form.py:261-266` must stay green (run that module's suite).
- Callable-selection writes skip value validation (fact 15): Studio's own UI only offers listed options;
  note it as a known limit for FS-H5 (a `_check` on write).
- `health_roster` template patch (fact 9): check `ir.module.module` state on the clone; if installed,
  STOP and report before deploy (its templates would already be failing on live — unlikely).

## 5. Tests (numbered; core in `test_fs_core.py`, overlay in `test_fs_health.py`)

Core:
- **33** `ws_title` reads a `<span>` title, a `<div>` title and a mixed one; ignores the edit-trigger span.
- **34** A host with an open card that has no `<group>` is refused by the host check with a message naming the card.
- **35** List writer: two placed `list_ok` fields → one xpath `//field[@name=anchor]` `after`, columns in
  section/field order, `optional="show"`, selection gets `widget="badge"`, monetary gets no extra widget.
- **36** PHI, binary and text fields: `list_ok` forced False with the right reason; a `list_ok` field NOT placed
  on the form yields no column; removing it from the form removes the column on republish.
- **37** Visibility: an Admins-only `list_ok` field is absent from the list arch a plain user receives
  (`get_views` as that user) and present for the admin.
- **38** No columns → list view inactive with `<data/>`; adding one reactivates it; the view id is stable.
- **39** History keeps `list_arch`; rollback restores both arches; version numbering unchanged.
- **40** Validator: rename the anchor column in the list arch (SQL, as test 24 did) → the whole layout
  switches off (form AND list views inactive) with a reason containing "list"; the list still renders.
- **41** Host constraint: `list_view_xmlid` without `list_anchor` refused; a non-list view refused; an
  anchor not in the list refused.
- **42** `get_studio` returns `list_title`, per-field `list_ok` / `list_reason`.
- **43** Source gates 12a–12f over the new files.
- **44 (HttpCase)** Editor URL state: open Studio by RPC-driven navigation (or a tour) on a host, reload
  the page, assert the editor is showing the same screen (title present, no "Open a screen…" notice).

Overlay:
- **45** Booking host resolves: kit ws, pack exists once, five open cards each with a `group`, `notes_card`
  not open, every locked field exists on the model, `button_box` zone exists, `HOST_TEXT` covers every
  reason/title (EN and VI), list view + anchor resolve for all FOUR hosts; `money_ok` True on Booking.
- **46** End to end on Booking as the Owner persona: text (Staff) + money + dropdown (VI options); one
  field into `care_team_card`, two in a new `pack_end` card; publish → form arch has the card last in the
  pack AFTER `notes_card`, the foreign cards still inside the pack (`test_ws_booking_form` suite green);
  list arch has the money and dropdown columns after `priority`, NOT the text field if its `list_ok` is off;
  a plain user outside Staff gets neither the field nor the column; rollback restores v1 of both.
- **47** Lists on Client / Contact / Incident: one `list_ok` field each → the column appears after the
  declared anchor in each list's combined arch; the Incident list (no js_class) and the Client list
  (priority 0) both render via `get_views`.
- **48 (HttpCase)** Over JSON-RPC as the Owner: `probe` true for (`health.fieldservice.order`, the ops form
  id), false for the legacy form id; `get_studio` for Booking returns kit ws, five open cards, `list_title`.
- Full suites without `-u` after upgrade (§5.275): biz_form_studio, health_form_studio, health_incident,
  health_fieldservice (incl. `test_ws_booking_form`), health_crm, health_theme, biz_access, biz_kit,
  health_base i18n. Green is the gate (the one pre-existing fail from FS-H2's report may remain; name it).

## 6. Browser QA (clone, Owner + VI Owner + Doctor/CRM/nurse personas as before; 1440 and 820 px)

- **21** Booking record: Studio button in the top bar left of the save indicator; Client and Contact unchanged.
- **22** Studio on Booking: Header card; the pack as cards — Visit, Location details, Care team, Pricing,
  Additional charges open; Notes closed with its reason; the two foreign cards absent or closed (they are
  invisible on this record) — screenshot; other tabs dimmed; Counters zone.
- **23** Add "Parking instructions" (text, Staff) into Care team; add a new card "Visit preferences" with
  "Preferred nurse gender" (dropdown + VI) and "Key safe deposit" (money). Switch "Show as a column in the
  Bookings list" on for the dropdown and the money field; the text field's switch is disabled with the
  long-text reason. Publish sheet lists the two columns and the reset warning. Publish.
- **24** Booking Overview: new card after Notes, same chrome; Care team holds the text field; tray folds the
  empty new card.
- **25** Bookings list (second tab of the Bookings screen): the two columns appear after Priority, the
  dropdown as a badge; the column chooser lists them; hide one → persists on reload; Group by the dropdown
  works with the EN labels; VI Owner sees VI labels in cells, badges, group headers and the chooser.
- **26** Clients list: a Client Studio field with the switch on appears after Total assignments; its
  Vietnamese label in the header for the VI Owner.
- **27** CRM/Staff persona on the Bookings list (if that role may open bookings — check and record): a
  Staff column shows; an Admins-only column does not. Nurse persona: no Studio anywhere.
- **28** Reload inside the editor → same screen comes back (Booking title, cards, draft intact). Browser
  back from the editor returns to the booking.
- **29** Breadcrumb "Dashboard" on Booking and Client headers navigates (no console error) — only if §3.6
  was done.
- **30** 820 px: Booking Overview Studio card one column; editor stacked; the Bookings list scrolls
  horizontally inside the list, not the page.
- Console clean. PNGs to `docs/handovers/formstudio/fs_h3_shots/`.
- Live (after upgrade): steps 21 and 22 on `carejiox.com` (an existing booking if any, else a new unsaved
  one) and `hhh.carejiox.com` — open only, publish nothing.

## 7. Deploy
1. Clone `carejiox` → `carejiox_fs3` (FS-H1 recipe). `-u biz_form_studio,health_form_studio[,health_fieldservice]`
   with the private tree, `validate_all`, suites without `-u`, QA, timing spot-check on Booking (create,
   publish; report).
2. Backups `/var/backups/fs3/` for all three.
3. Live: `carejiox-deploy -d` then `-m biz_form_studio,health_form_studio[,health_fieldservice]` on
   `carejiox`, `-D carejiox_template …`, `-D hhh …`; exit 0 and `/web/login` 200 each; `validate_all` on
   each (0 layouts expected, host list checks all resolve); template jobs still OFF; bundle serves the new
   symbols.
4. Destroy the clone and every transient. Only the backups remain.

## 8. Report back (`docs/handovers/formstudio/FORM_STUDIO_FS-H3_REPORT.md`)
Same shape as FS-H2's: owner paragraph; rules restated; tests 33–48 table; QA 21–30 with personas and
PNGs; deploy log; deviations D1…; plumbing drift; which roles can open Bookings (so the owner knows who
holds Studio there, cf. §5.277); the `health_roster` installed/not finding; new ledger entries §5.278+ in
`docs/strategy/HANDOVER-CONVENTIONS.md`; what FS-H4 (PHI reach: exports, BI, nurse app read-only block,
encryption on Client) needs from the engine — in particular the `exportable` route (fact 16) and where the
PWA sync serialises booking/client fields. Commit code, the side fix, and the report separately. Do not push.
