# FORM STUDIO — FS-H1 report (engine + Incident host)

Written 2026-11-03 by the Opus implementer. Handover: `FORM_STUDIO_FS-H1_CORE.md`.

## In one paragraph

An Owner or Admin can now open **Studio** from the top bar of an incident, add fields (text,
long text, numbers, money where the screen has a currency, yes/no, dates, dropdown, link to a
staff member/facility/client/contact/service/catchment area, file), put them in new sections,
choose who sees each one (everyone / staff / admins — enforced by the server, not only hidden),
mark health information, publish for everyone, go back to an earlier version, and delete a field
with a typed DELETE. A field library lives under **Settings › Master data › Form Studio**. Both
modules are **installed on `carejiox`, `carejiox_template` and `hhh`**; `/web/login` answers 200
on carejiox.com and hhh.carejiox.com. Nothing was published on the live databases.

## Standing rules (stated back)

- **White-label:** no "Odoo" in anything a user sees — `biz_form_studio` sources (comments
  included) are scanned by test 12a; both `vi.po` msgstr scanned by test 16.
- **Generic core:** `biz_form_studio` names no product, no `health_`, no "clinic/nurse/patient",
  no "Carejiox/Viet Uc" (test 12a). The nurse-app switch is "Mobile app" in the core and "Nurse
  app" only through the overlay's host data.
- **Plain copy** in the user's words; technical names (`x_fs_…`) never shown.
- **Design:** flat colours from `--bzk-*` tokens (the bar reads `--vuf-hero` when the product
  declares it, else `--bzk-ink`); Lucide icons through `ic()` from `@biz_kit/js/kit_icons`
  (7 glyphs added there); no emoji, no font-awesome in markup (the `cms.sidebar.item.icon`
  exception: `fa fa-magic`); no gradients; no `font-family` (test 12d).
- **Vietnamese** for every new string, generated from the framework's own export.
- **Chatter at the bottom:** the incident form's `<chatter/>` untouched; Studio sections are
  inserted before the tabs or at the end of the sheet, never after the chatter.
- **No business-logic change on the host:** no existing field, button, `invisible`, `groups` or
  `readonly` touched. "Required" is a rule of the screen only (see D1).
- **Sanctioned edits:** both new modules in full; `biz_kit/static/src/js/kit_icons.js` (glyphs,
  §0). No other shared module touched.
- **Tests** never with `-t` on the live box; rehearsed on `carejiox_fs1` (`biz_tenant.slug` →
  `nowhere_fs1_1`, all jobs off, mail servers off, new `database.uuid`, private addons tree first
  on the path, `--db-filter=^carejiox_fs1$`, `systemd-run` on 8199/8197).
- **Commits** on 19.0, not pushed.

## Files

`addons/biz_form_studio/` (NEW, 19.0.1.0.0) — `models/fs_common.py` (names, settings, slug,
visibility group), `models/ir_model_fields.py` (C2), `models/fs_host.py`,
`models/fs_link_target.py`, `models/fs_field_meta.py`, `models/fs_layout.py` (layout, draft,
history, writer, validator — C3), `models/fs_studio.py` (facade — C7), `security/*`,
`views/fs_actions.xml` (two client actions), `static/src/js/studio_service.js` +
`studio_button.js` + `xml/studio_button.xml` (C4), `static/src/js/studio/studio_editor.js` +
`xml/studio/studio_editor.xml` + `scss/studio.scss` (C5), `static/src/js/library.js` +
`xml/library.xml` (C6), `i18n/vi.po` (291 entries), `tests/test_fs_core.py`.

`addons/health_form_studio/` (NEW, 19.0.1.0.0) — `data/fs_parameters.xml`, `data/fs_hosts.xml`,
`data/fs_link_targets.xml`, `data/cms_sidebar.xml`, `models/fs_host.py` (translated lock
reasons), `models/fs_studio.py` (Field Requirements blocker), `hooks.py`, `i18n/vi.po` (20),
`tests/test_fs_health.py`.

`addons/biz_kit/static/src/js/kit_icons.js` — `wandSparkles, type, alignLeft, toggleLeft,
calendarClock, paperclip, gripVertical`.

## Tests (§5) — final clone run

`odoo.tests.result: 0 failed, 0 error(s) of 297 tests when loading database 'carejiox_fs1'` —
biz_form_studio 25, health_form_studio 7 (1 HttpCase, ran), health_incident 20, biz_access 228,
biz_kit 12, health_base i18n G1/G1b/G1c/G2/G2b 5; `ERROR: setUpClass` count 0.

| # | Test | Result | Assertion |
|---|---|---|---|
| 1 | `test_01_create_char_field` | PASS | "Khung giờ ưu tiên" → `x_fs_khung_gio_uu_tien`; row `state='manual'`, `ttype='char'`; column in `information_schema.columns`; in `fields_get`; one meta row, `vis='all'` |
| 2 | `test_02_slug_collision_length_and_characters` | PASS | second "Preferred window" → `x_fs_preferred_window_2`; 60×"A" → ≤63 and `^x_fs_[a-z0-9_]+$`; "  Đơn vị / (kg) #1!! " → `x_fs_don_vi_kg_1` |
| 3 | `test_03_selection_options_add_rename_refuse_removal` | PASS | 3 option rows; update adds "Email" and renames to "Phone" (4 rows); removing an option used by 2 partners → UserError "used on 2 records" |
| 4 | `test_04_link_targets` | PASS | `res.bank` (not listed) refused; `res.country` → `relation='res.country'`, `on_delete='set null'`; required link → `on_delete='restrict'`, `meta.required`, column NOT required |
| 5 | `test_05_money_needs_a_currency` | PASS | `host.money_ok == ('currency_id' in res.partner)`; second host on `account.move` → monetary field with `currency_field='currency_id'` |
| 6 | `test_06_visibility_is_enforced_by_the_orm` | PASS | Admins field has `groups='base.group_system'`; plain internal user: absent from `fields_get`, `read()` raises AccessError; Everyone field readable; switching to Everyone removes the group |
| 6b | `test_06b_required_is_a_rule_of_the_screen` | PASS | `_fields[name].required` False; published node has `required="1"`; a partner created elsewhere is not refused; switching Required off republishes without it |
| 6c | `test_06c_health_information_is_never_a_list_column` | PASS | phi → `list_ok` False; forcing `list_ok` → ValidationError |
| 7 | `test_07_rename_reaches_the_label_cache` | PASS | `get_field_string('res.partner')[name] == 'New label'` right after the rename |
| 7b | `test_07b_type_cannot_change` | PASS | UserError "type cannot be changed" |
| 8 | `test_08_publish_one_section` | PASS | view `mode='extension'`, `inherit_id`=base, `priority=200`; combined arch has `group[@name='fs_sec1']` with both fields, `string='Follow-up'`; version 1; history `[1]`; chatter "Published version 1"; draft gone |
| 8b | `test_08b_stale_version_is_refused` | PASS | publish with `base_version=0` after v1 → "newer version" |
| 8c | `test_08c_writer_refuses_a_field_that_does_not_exist` | PASS | UserError, no view created |
| 9 | `test_09_move_then_go_back` | PASS | v2 after a move; `rollback(1)` → v3 whose arch == history v1 arch == view arch |
| 10 | `test_10_validator_switches_a_broken_layout_off` | PASS | card anchor `nope` → `validate_all()` lists it broken, `state='broken'`, reason stored, view inactive; base combined arch still renders with `//sheet` |
| 11 | `test_11_delete_field` | PASS | `confirm='delete'` refused; export list "Partner sheet" blocks and is named; after removing it: count returned == pre-delete `search_count`, combined arch lacks the field and keeps the other, `fields_get` lacks it, layout republished (v2) |
| 11b | `test_11b_history_is_append_only` | PASS | `unlink` and `write` on history refused |
| — | `test_gate_and_probe`, `test_get_studio_shape` | PASS | plain user: probe `{host: False}`, get_studio/create_field AccessError; probe never raises on a bad model or no view; 11 types, notebook marker, std fields |
| 12 | `TestFsSourceGates` 12a–12f | PASS | no banned/industry word in any core source or its vi.po (comments included); every `ic()`/type icon in the biz_kit registry; no `.then(` without `.catch(` in `onWillStart`; no `font-family`, no `min/max(calc)`, no gradient; no adjacent JS strings, no reserved `t-as`; button anchored on `…additional-actions']/CogMenu`, no StatusBarButtons |
| 13 | `test_13_parameters_host_and_targets_resolve` | PASS | 3 params → existing `res.groups` (gate = clinic admin, staff = healthcare base); Field Requirements action resolves; host resolves from the view; `money_ok` False; sections empty; ≥6 link targets, every model in the registry; the incident arch has no named `<group>` |
| 14 | `test_14_gate_is_the_clinic_admin` | PASS | clinic admin: probe `{host: True, can_edit: True}`, get_studio (title "Incident", zone "Counters", `state` locked), create + publish (version +1), `published_by` = the clinic admin; head nurse: probe `{host: False}`, AccessError on get_studio and publish |
| 14b | `test_14b_clinic_admin_makes_a_dropdown_over_http` (HttpCase) | PASS | over JSON-RPC as the clinic admin: dropdown with 3 options, add + rename (4 options), publish, probe. **Proven to catch the bug:** against the old command-based code it errors with `AccessError` (run `fs1-proof`) |
| 15 | `test_15_end_to_end_on_the_incident` | PASS | dropdown + text (Staff) + link (Staff member) in one section, placed directly before `//sheet/notebook`; incident created with values round-trips; text field has `groups='health_base.group_healthcare_base'`, absent from a plain login's `fields_get`, present for the clinic admin |
| 15b | `test_15b_requirement_rule_blocks_deletion` | PASS | a `field.requirement.rule` on the field → blocker |
| 15c | `test_15c_lock_reasons_read_in_vietnamese` | PASS | `_fs_text('Drawn by the system.')` under vi_VN → "Do hệ thống tạo."; host name "Sự cố" |
| 16 | `test_16_sidebar_row_and_catalogues` | PASS | row in `section_admin`, roles {Admin, Owner}, action tag `biz_form_studio.library`, active; both `vi.po` present, no "Odoo" in any msgstr; plus health_base G1/G1b/G1c/G2/G2b green over a tree holding both modules |

**Pre-existing failure, not caused by this phase:** the repo-wide i18n gate fails against the
LIVE addons tree (run `fs1-t2`: 1 failed, 4 errors) because of
`health_pwa/i18n/._vi_VN.po` — a macOS AppleDouble file dated 2026-10-29 05:44, one of twelve
`._*` files on the live tree (ledger §5.271). Left in place (not sanctioned to delete); the gate
was run green over a tree containing health_base and both new modules (run `fs1-t3`/final).

## Browser QA (§6) — evidence in `fs_h1_shots/`

Personas on the clone: **A** `fs.qa.admin` holding exactly the Admin role's groups (`base.group_user`,
`health_access.group_clinic_admin`, `health_voip24h.group_voip_manager`); **B** `fs.qa.doctor`
(Doctor role — see D15); **VI** `fs.qa.admin.vi` (Admin role, Vietnamese). Path every time:
sign-in by `fetch` → sidebar Clinical → Incidents → INC00171. Trusted clicks and the DevTools
drag tool (real HTML5 drag-and-drop). Served bundle verified first (contains `o_fs_studio_btn`,
`biz_form_studio.studio`, `wandSparkles`, `.fs-studio`; no CSS error).

| Step | Result | Evidence |
|---|---|---|
| 1 | A: Studio button right after the cog; B: none | `01a`, `01b` |
| 2 | Editor with schematic (Status bar, Counters dimmed "Drawn by the system.", Title, Event, Context, Description, Immediate Actions, Tabs), locked chips with reasons, palette, empty right panel; console: no errors/warnings | `02` |
| 3 | Dropdown dragged onto "Add a section" → section "Follow-up", options Phone call / Home visit / None; Text "Family informed by", Who sees it = Admins; Link to a record → Staff member "Nurse on duty" | `03a`, `03b`, `03c` |
| 4 | Publish sheet listed 3 additions + new section → toast → back on the incident: "FOLLOW-UP" VU card above the tabs with the three fields; values saved, persist after reload | `04a`–`04d` |
| 5 | B: card shows Follow-up and Nurse on duty, NOT Family informed by; B's `fields_get` lists only `x_fs_follow_up`, `x_fs_nurse_on_duty` | `05` |
| 6 | Library from Settings › Master data › Form Studio: 3 rows, Filled 1/1, "Open in Studio" opens the editor; B has no Settings section at all | `06a`, `06b` |
| 7 | Delete "Family informed by": sheet "values on 1 records" (wording fixed to "a value on 1 record" afterwards), typed DELETE → gone from the form (layout republished as v2) and from the library | `07a`–`07d` |
| 8 | After a v3 that moved Nurse on duty to "Staffing": Previous versions → Go back to version 1 → published as v4, toast "Fields deleted since then were left out", form shows one Follow-up card again | `08a`, `08b` |
| 9 | VI user: editor, palette, PHI warning ("Không nhập thông tin sức khỏe…") and sheets in Vietnamese; Vietnamese section title "Theo dõi" and labels "Theo dõi tiếp", "Ghi chú theo dõi" show on the form | `09a`–`09e` |
| 10 | 1100 px and 820 px: stacked (palette, screen, settings), no horizontal scroll (`scrollWidth ≤ innerWidth`); chips all 36 px, tiles equal, card heads 48 px, no clipped label | `10a`, `10b` |
| Live 1, 2, 6 | carejiox.com, temporary user with the Admin role: Studio button on a NEW (unsaved) incident — live has 0 incidents — editor opens (no changes made, nothing saved), library shows the empty state naming "Incident"; console clean | `11a`–`11c` |

Console notes: clone — no errors; one `ERR_CONNECTION_RESET` (the bus websocket port was not
tunnelled; QA setup, not product); browser "issues" panel: 3× "Incorrect use of <label for>"
and 1× "form field should have an id or name" on the editor page (accessibility hints, not
errors). Live — no console messages.

Live clean-up: temporary user `fs.qa.live.20261102` (id 10112) and its partner deleted; fresh
psql shows 0 rows in `res_users`/`res_partner`; no restrict-FK rows existed for it
(`health_workspace_audit`, `bi_audit_log`, `health_pwa_staff_notification`, `privacy_log`,
`hr_employee` all 0 — checked before deleting). Live has 0 `fs_layout`, 0 drafts, 0 `x_fs_`
fields, 0 incidents (unchanged).

## Deploy (§7)

1. Clone `carejiox` → `carejiox_fs1` (pg_dump|psql + filestore copy), neutralised, private tree
   `/odoo/fs1/addons`, install + tests + QA as above.
2. Backups: `/var/backups/fs1/{carejiox,carejiox_template,hhh}.dump` (19.3 / 13.1 / 14.4 MB).
3. `COPYFILE_DISABLE=1` tar to `/tmp` (0 `._` files) → `carejiox-deploy -d -i
   biz_form_studio,health_form_studio,biz_kit` (exit 0, http 200), then `-D carejiox_template -i …`
   (exit 0), then `-D hhh -i …` (exit 0). All three report both modules `installed`.
   `biz_kit` is named on `-i` only so the wrapper copies its file: in this framework version `-i`
   of an installed module is a plain load (no upgrade, no cascade) — see D23.
4. Template had **7** active jobs after the run → `UPDATE ir_cron SET active=false` → 0.
5. `/web/login` 200 on carejiox.com and hhh.carejiox.com (public HTTPS and Host-header local);
   live bundle serves the new symbols.
6. Clone dropped with its filestore, private tree, transient units, staging files and tunnel.

## Deviations (with reasons)

- **D1 — "Required" is a rule of the screen** (`required="1"` on the node in the generated view;
  stored in `fs.field.meta.required`; switching it republishes the layouts showing the field)
  instead of `required=True` on the field. A NOT NULL can never be applied to a new column on a
  table with rows (the framework logs an ERROR on every restart trying) and a required column
  would refuse records the mobile app and integrations create — a business-logic change on the
  host (§0). Copy says so. Required links keep `on_delete='restrict'` (test 4). Ledger §5.266.
- **D2 — dropdown options are created/renamed/removed directly on `ir.model.fields.selection`**,
  not as `selection_ids` commands: that model refuses sudo commands and re-runs them as the
  requesting user (found in browser QA; ledger §5.265; HttpCase 14b).
- **D3 — field methods take the model too:** `update_field(model, name, spec)`,
  `field_references(model, name)`, `delete_field(model, name, confirm)`,
  `ack_phi_warning(model, name)` — `x_fs_` names are only unique per model.
- **D4 — `fs.field.meta`:** `order` is called `sequence`; added `required` (D1) and readable
  `string=` labels; `retired_values` kept as specified.
- **D5 — the button is anchored INSIDE the slot, right after the cog**
  (`//t[@t-set-slot='control-panel-additional-actions']/CogMenu`, `position="after"`); "before
  the slot node" would have placed it outside any slot.
- **D6 — visibility:** `_all_manual_field_data` selects `*`, so the branch taken is
  `field_data.get('fs_vis')` (no browse fallback; before the column exists the key is absent →
  no group). Groups are resolved from the three settings by plain SQL at registry build
  (`fs_common.vis_group_xmlid`; `fs.studio._vis_group_xmlid` wraps it); a missing group falls
  back to `base.group_system` (more restrictive). `fs_vis` is passed in the field's create, so a
  new field is built once with its group.
- **D7 — "Mobile app"** in the core, "Nurse app" through `fs.host.pwa_label` (overlay data) —
  the core may not say "nurse". **D8 — `fs.host.name`** (translatable) for the screen title and a
  `_fs_text` hook so lock reasons/zone titles read in Vietnamese (JSON is not translatable).
- **D9 — `data-fs-id` is not written** on the generated `<group>` (a component node passes
  unknown attributes as props); `name="fs_<id>"` identifies it; `class="fs-card"` written.
- **D10 — Vietnamese section titles reach the form:** written as the view's own translation of
  the English title (`update_field_translations('arch_db', …)`), not only shown in Studio; the
  arch source stays English. Field Vietnamese label/help likewise as field translations.
  Option labels have no Vietnamese input in H1.
- **D11 — `check_access` names:** `check_access(operation)` (`odoo/orm/models.py:4097`) used in
  the gate; `has_access` :4114 not needed.
- **D12 — re-fetch after publish:** `rpcBus.trigger("CLEAR-CACHES", "get_views")` then
  `action.restore()` (the form controller re-mounts and re-reads the arch). Measured: the card
  appears at once for the publisher; `window.location.reload()` not needed. For everybody else a
  publish sets `registry_invalidated` so the browser cache is renewed on the next load (§5.269).
- **D13 — bus skipped** (§3.9): other tabs see the layout on their next load.
- **D14 — menu entry under "Master data" next to Field Requirements** (sequence 88) through the
  overlay's install hook when `health_cms_ia.parent_admin_master` exists (cms_ia untouched); plus
  a switched-off entry claiming the editor's tag so the left menu stays on the section the admin
  came from (§5.272). Verified: Owner/Admin see it; Doctor has no Settings section.
- **D15 — persona B is a Doctor,** not a Nurse: the Nurse role does not open Clinical › Incidents
  on this menu (gate: Owner, Admin, Doctor), so the required real path is impossible for a nurse.
  A doctor is equally outside "Admins".
- **D16 — live QA on a new, unsaved incident:** live `carejiox` has no incidents; nothing saved.
- **D17 — honest copy** for Health information and the mobile app: "Kept out of lists and shown
  with a shield. Exports, reports and the mobile app leave it out from a later release." /
  "Shown, read-only, in the mobile app from a later release." — the handover wording claimed
  exclusions that only arrive in FS-H4.
- **D18 — go-back leaves out fields deleted since** that version (and says so); otherwise QA
  step 8 (go back to v1 after deleting a v1 field) could never succeed.
- **D19 — added** `base_version` stale-publish refusal; saved filters and automatic actions as
  delete blockers; `fs.studio.library()` and `first_record()`; field type icons for standard
  html/one2many/many2many fields; Money tile shows "not on this screen" with the reason as tooltip.
- **D20 — library "Filled"** uses one `search_count` per field (AccessError → "—"), not one
  `read_group` per model — same answer, simpler with mixed types.
- **D21 — `fs.layout.history`** refuses `write` as well as `unlink`.
- **D22 — host sections declared:** none. The incident arch's `<group>`s carry no `name=`, so the
  host declares `sections=[]`; Studio adds its own sections (before the tabs by default, or at the
  bottom). Locked: `name`, `state`, `client_id`, `incident_datetime`; locked zone `button_box`.
- **D23 — `biz_kit` deployed with `-i`** (a load, not an upgrade, for an installed module in this
  version — `modules/loading.py:151-156`) to avoid the `-u biz_kit` cascade over every module
  above it. Its only change is the icon file; no data.

## Verified plumbing — drift found

All §2 line numbers held except `_get_ids` (`ir_model.py:828`, handover :827). New facts:
`MODULE_UNINSTALL_FLAG` lives in `odoo/addons/base/models/ir_model.py:36` (not
`odoo/modules/module.py`); `ir.model.fields.selection._allow_sudo_commands = False`
(`ir_model.py:1483`); `FormController.actionService` set at `form_controller.js:160`; no form RNG
(groups take any attribute; component props do not).

## New ledger entries (HANDOVER-CONVENTIONS §5)

§5.265 selection model refuses sudo commands · §5.266 required manual field on a table with rows ·
§5.267 tests that create fields must rebuild the registry after rollback · §5.268 `_()` in nested
functions · §5.269 browsers cache layouts per registry version · §5.270 translated fields written
under a Vietnamese context · §5.271 i18n gate reads health_base's tree; twelve `._*` files on live ·
§5.272 inactive menu entry keeps the CMS shell without lighting anything.

## Known limits (honest)

- Duplicate labels on one screen are allowed (names get `_2`); the framework logs a WARNING
  "Two fields … have the same label".
- Every field create/change and every publish rebuilds the registry on each worker (seconds);
  fine for an admin tool, measure on the Client host (res.partner is large) in FS-H2.
- A Studio view whose anchor disappears during a module UPGRADE fails that upgrade before
  `validate_all()` can run; wiring the validator into the deploy wrapper is FS-H5.
- Option retirement is stored, not yet applied (tooltip says "after the next release").

## Commits

- `8e10b9be` — Form Studio (health19): FS-H1 engine and the Incident screen
- (this report, ledger and evidence) — see the commit after it.

## Evidence folder `docs/handovers/formstudio/fs_h1_shots/`

01a_clone_admin_incident_studio_button · 01b_clone_doctor_incident_no_studio_button ·
02_clone_editor_incident_1440 · 03a_clone_new_dropdown_followup_panel ·
03b_clone_new_text_family_informed_admins · 03c_clone_new_link_nurse_on_duty_staff_member ·
04a_clone_publish_sheet · 04b_clone_back_on_incident_after_publish ·
04c_clone_followup_card_on_incident · 04d_clone_values_saved_after_reload ·
05_clone_doctor_sees_followup_without_admin_field · 06a_clone_field_library_from_sidebar ·
06b_clone_open_in_studio_from_library · 07a_clone_delete_sheet_values_on_1_record ·
07b_clone_delete_typed · 07c_clone_field_deleted_version_2 · 07d_clone_library_after_delete ·
08a_clone_previous_versions_confirm · 08b_clone_form_back_on_version_1_layout ·
09a_clone_vi_editor · 09b_clone_vi_phi_warning_long_text · 09c_clone_vi_section_settings ·
09d_clone_vi_publish_sheet · 09e_clone_vi_form_card_titles_in_vietnamese ·
10a_clone_editor_1100px_stacked · 10b_clone_editor_820px_stacked ·
11a_live_admin_new_incident_studio_button · 11b_live_editor_incident_1440 ·
11c_live_field_library_empty (all `.png`).

## What FS-H2 (Client + Contact on the Workspace kit) needs — concrete

1. **Writer, kit `ws`:** a new section must render as
   `<div class="vu-detail-card ws-card fs-card" name="fs_<id>" data-fs-fold="1"><div
   class="vu-card__title">Title</div><group>…fields…</group></div>` appended inside
   `//div[hasclass('ws-pack')]` (anchor kind `pack_end`, not yet in `_clean_sections`). Today
   `_render_arch` only has the ws branch for dropping into an existing card
   (`//div[@name='<card>']/group`); new sections are bare `<group>`s.
2. **Schematic, kit `ws`:** `fs.studio._base_cards` reads `<group string>`, notebook pages, the
   header and `oe_title`. Workspace cards are `div.vu-detail-card[@name]` whose title is a TEXT
   node in `div.vu-card__title` — add that reader, and declare open cards in `fs.host.sections`
   by those `name`s.
3. **Fold tray hook** (`health_theme/static/src/js/ws_fold_tray.js`, the one sanctioned kit
   change) reading `data-fs-fold="1"` cards.
4. **Studio button placement on js_class forms:** the button lives in `web.FormView`'s control
   panel slot. `ops_client_profile_form` and `crm_contact_form_view` draw their own chrome; check
   the control panel is rendered there, else the overlay needs a slot in those headers.
5. **Hosts:** Client = `res.partner` (default form `ops_client_profile_form`, priority 0);
   `fs.host._for` already accepts a primary view one level down. Contact = `crm.lead`
   (`view_crm_contact_form_crm_center`). Locked-field registry per programme §4.
6. **Standard-field rename/help (H2 scope):** core refuses writes on non-manual
   `ir.model.fields`; do it in the generated arch (`string=` / `help=` attributes on the field
   node via `position="attributes"`), with translations as in D10.
7. **Registry cost:** measure a publish/field create on `res.partner` (largest model) on a clone
   with `workers=2`; consider batching field settings into fewer writes.
8. **Option labels in Vietnamese** (selection names) — needs a VI input per option.
