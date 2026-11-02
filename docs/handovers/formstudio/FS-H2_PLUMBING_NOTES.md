# FS-H2 plumbing notes (verified 2026-11-03, read-only research) — input to `FORM_STUDIO_FS-H2_CLIENT_CONTACT.md`

Paths relative to `addons/`. Re-check file:line before coding.

## Corrections to the programme document
- The Client Workspace form xmlid is **`health_fieldservice.view_health_patient_form_ops`**
  (`health_fieldservice/views/ops_client_profile_form_views.xml:5`, priority 0, primary, no inherit).
  `ops_client_profile_form` is only its `js_class` / controller / template name.
- The Contact form `health_crm.view_crm_contact_form_crm_center` (`health_crm/views/crm_center_views.xml:76`,
  priority 50, primary) has **no `ws_fold_tray`** (comment :197-199). A Studio card there needs the
  tray added by the inherited view: `<widget name="ws_fold_tray"/>` after
  `//page[@name='overview']/div[hasclass('ws-pack')]`.
- **All three Workspace controllers hide the stock control panel** (`.o_control_panel { display:none
  !important }` — `ops_client_profile_form.scss:24-26`, `crm_contact_form.scss:24`,
  `ops_booking_form.scss:36`). Their templates copy `Layout` + `CogMenu` but nothing of it is
  visible. The FS-H1 Studio button (control-panel slot) will therefore be INVISIBLE on Client /
  Contact / Booking. H2 must add the button to the custom header (`.ops-header-right`,
  `health_fieldservice/static/src/xml/ops_client_profile_form.xml:30,54-55`;
  `.crm-form-header-right`, `health_crm/static/src/xml/crm_contact_form.xml:31,55-56`) via
  `t-inherit` template extensions shipped by `health_form_studio` (no shared-module edit).

## Client form structure (`ops_client_profile_form_views.xml`)
- `<form string="Client Profile" js_class="ops_client_profile_form" class="ops-client-profile-form ws-workspace">` :10-11;
  header :21-46; sheet :51; `.ws-page` :65; `.ws-main` :66; `ws_compact_bar` :70; `.ws-hero` :75-125;
  banners :130/136/143; `.ws-next` :149 (`ws_client_next`); notebook :156-595; `.ws-rail` :599-617
  (`ws_rail_fold`, `ws_client_shortcuts`, `ws_client_glance` ×2, `div.ws-panel--people[name=people_panel]` :614);
  `<chatter/>` :621.
- Pages: `profile_overview` :160, `bookings_journey` :245, `address_info` :320, `intake_notes` :370,
  `insurance_billing` :415, `active_packages` :449, `healthcare_relationships` :464,
  `clinical_notes` :478, `financial_summary` :537.
- ONE `.ws-pack` (:161, no `name`), in Overview. Cards (`div.vu-detail-card.ws-card[name]`):
  | card | lines | title | fields |
  |---|---|---|---|
  | `personal_card` | :163-178 | Personal | title, first_name, middle_name, last_name, vietnamese_name, birth_date, gender_id, deceased |
  | `contact_card` | :180-190 | Contact | phone (required=1), mobile (invisible), email |
  | `care_card` | :192-211 | Care | patient_category_id, catchment_province_id (required=1), primary_facility_id, intake_referring_doctor_id, source_type, source_details, referral_source |
  | `identity_card` | :213-223 | Identity | national_id, profession, ethnicity |
  | `commission_card` | :225-233 | Commission | commission_due_to |
  Last child of `.ws-pack` = `<widget name="ws_client_visits"/>` (:236) → `position="inside"` lands after Recent visits.
- Fold tray :239-241 (sibling after the pack): `{'identity_card': ['national_id','profession','ethnicity'], 'commission_card': ['commission_due_to']}`.
- Inheriting views (all `//notebook` inside unless noted): health_cms_clinical `views/ops_profile_tabs.xml:13`;
  health_self_booking `views/ops_client_booking_links_tab.xml:14`; health_twin `views/res_partner_views.xml:27`;
  health_careplan `views/ops_careplan_tabs.xml:12`; health_bhyt `views/res_partner_views.xml:35` (adds
  `insurance_number` string "BHYT Card No." :53); health_portal `views/ops_client_portal_tab.xml:8`;
  health_condition `views/ops_client_diagnoses_tab.xml:16`; health_family_messages `views/ops_client_family_tab.xml:9`;
  health_invoicing `views/res_partner_views.xml:156` (`//page[@name='active_packages']//p[...]` replace :164,
  `//page[@name='financial_summary']//div[@class='bj-bookings-section']` after :193); health_crm
  `views/ops_client_inherit.xml:30` (`//div[@name='people_panel']` inside :35). None touch `.ws-pack` or a card.

## Contact form structure (`crm_center_views.xml`)
- `<form string="Contact" js_class="crm_contact_form_view" class="ws-workspace">` :81; header :84-112;
  sheet :113; `.ws-page` :119; `.ws-main` :120; `ws_compact_bar` :124; `.ws-hero` :130-181;
  `ws_journey` :184; `.ws-next` :192 (`ws_contact_next`); notebook :196-321; `.ws-rail` :327-359
  (`ws_rail_fold`, `ws_contact_glance` ×2, `div[name=people_panel]` :332 with user_id :337, patient_id :346);
  `div.ws-history[name=contact_history]` :369 outside `.ws-page`; NO chatter by design (:362-368).
- Pages: `overview` :200, `client_details` :243, `address` :263, `relationships` :288, `more_details` :304
  (the last four = plain nested groups, not cards).
- ONE `.ws-pack` :201. Cards: `contact_card` :203-214 (name required, phone, email_from,
  contact_relationship_type); `reached_card` :216-226 (mode_of_contact_id, contact_datetime,
  catchment_province_id); `status_card` :228-237 (contact_status readonly, contact_outcome).
- Inheriting: health_web_leads `views/crm_lead_views.xml:185` (`//page[@name='more_details']` after → page
  `web_attribution`); health_google_ads `views/crm_lead_views.xml:85` inherits THAT view.

## Controllers
- Client `OpsClientProfileFormController` (`health_fieldservice/static/src/js/ops_client_profile_form.js:10`,
  template `health_fieldservice.OpsClientProfileFormView`, registered :149).
- Contact `CrmContactFormController` (`health_crm/static/src/js/crm_contact_form.js:17`, template
  `health_crm.CrmContactFormView`, registered :137).
- Booking `OpsBookingFormController` (`ops_booking_form.js:8`, `OpsBookingFormView`).
- All three in `VU_NO_HERO_JS_CLASS` (`vu_form_compiler.js:32-43`); engine skin applies, hero skipped.

## Fold tray (`health_theme/static/src/js/ws_fold_tray.js`, `xml/ws_fold_tray.xml`)
- `extractProps: ({options}) => ({cards: options.cards || {}})` :187-189; `cards` optional :58; `get cards()` :71-73.
- `formRoot = this.root.el?.closest(".o_form_renderer")` :133-135; `cardEl(name) = form.querySelector([name="…"])`
  :137-140 (FIRST `[name]` anywhere — field roots and tab links carry `name` too → Studio card names `fs_<id>`
  must never equal a field or page name).
- `cardIsEmpty(fieldNames)` :91-102 (`every`; unknown field = empty; invalid field never folds;
  `isEmptyValue` :34-52); `foldedNames` :106-120; `onMounted/onPatched → sync()` :67-68; `sync()` :142-164
  toggles `ws-card--folded`, reads `.vu-card__title` text :155; `opened` useState keyed `${recordKey}:${card}`
  :64/:88/:167; `seen` Map :65/:79-85; `recordKey = String(resId||"new")` :75-77. Template: one
  `button.ws-fold-tray__chip` per folded card; root gets `ws-fold-tray--empty` when none (xml :5-17).
- **Seam (K-change, sanctioned file = this one only):** `this.discovered = useState({})`; in `sync()` scan
  `this.root.el.closest('.tab-pane') || formRoot` for `[data-fs-fold="1"][name]`; field list from
  `data-fs-fields="x_a,x_b"` written by the Studio writer (plain-div attributes survive compilation —
  `web/static/src/views/view_compiler.js:394-402`), fallback `.o_field_widget[name]`; write `discovered` only
  on change (no onPatched loop); `get cards()` = `{...discovered, ...props.cards}` with Studio field names
  UNIONED into existing static cards (else `identity_card` can fold while a Studio field in it has a value);
  `chips` unchanged. Cost: one-frame flash on first mount.

## Workspace CSS (`health_theme/static/src/scss/ws_workspace.scss`)
- Scope `$ws: ".o_form_view.ws-workspace .o_form_renderer.vu-form"` :30. `.ws-pack` :887-897
  (`columns: 2 340px`; children `display:block; width:100%; break-inside:avoid`). `.ws-card--folded {display:none !important}` :899.
  Card chrome `:is(.ws-card, .ws-pack > .vu-detail-card)` :901-1004; title rules :914-938 → an `fs-card`
  that is a direct `.ws-pack` child with `vu-detail-card ws-card` is fully styled; `fs-card` has no CSS yet.
  Read-first inputs :1009-1066; tray :1071-1122; wrapper `.o_widget_ws_fold_tray` :1125.
- Group flattening `vu_form_engine.scss:379-389`; empty `vu-sec` hidden :373-376.
- `vu-detail-card__edit-trigger` is pure CSS (`inline_edit.scss:24-51`), hidden on ws cards (:911) — omit.

## Locked fields (exact names)
- res.partner: `name, phone, email, street, street2, city, state_id, zip, country_id, vat` (core);
  `mobile` `health_base/models/res_partner.py:84`; `first_name/middle_name/last_name` :81-83; `birth_date` :85;
  `catchment_province_id` :230 (THE catchment field; rules `health_base/security/catchment_global_rules.xml:34-38`);
  `primary_facility_id` :237; `national_id` :254 (encrypted compute in `health_phi_encryption/models/res_partner.py:78`);
  `cccd_number` `health_crm/models/res_partner.py:17` (encrypted :82); `insurance_number`
  `health_base/models/res_partner.py:170` (BHYT; health_bhyt adds `bhyt_beneficiary_code`
  `health_bhyt/models/res_partner.py:24`); address shown = `vietnamese_address` (Text :279).
  In the Client arch: name (invisible :52 + read-only hero :83), phone, mobile (invisible), birth_date,
  catchment_province_id (required), primary_facility_id, national_id, insurance_number (:425 + BHYT tab).
- crm.lead (`crm/models/crm_lead.py`): `user_id` :108, `team_id` :115, `stage_id` :134, `contact_name` :171,
  `email_from` :180, `phone` :190, `mobile` :193, `campaign_id/medium_id/source_id` :240-242. health_crm:
  `catchment_province_id` :733 (seeds contact code :1313-1319; rules `health_crm/security/catchment_global_rules.xml:36`),
  `district_id` :751, `facility_id` :707, `contact_status` :372, `mode_of_contact_id` :590, `patient_id` :226.
  In the Contact arch: name, phone, email_from, catchment_province_id (hero :171, reached_card :224, address :268),
  user_id (rail), street/zip (address tab :274/:281).

## Settings tile (`health_landing`)
- Markup `static/src/xml/admin_settings.xml:12-55` (`div.admin-settings-tile[t-on-click] > .admin-tile-icon
  (inline style bg/color, fa icon) + .admin-tile-label + .admin-tile-desc + i.fa-chevron-right.admin-tile-arrow`);
  Field Requirements :48-55. JS `static/src/js/admin_settings.js` (client action `admin_settings` :68; gates
  :24-32 `canManageAccess` via `ACCESS_MANAGE_GATE`, `isSystemAdmin`; `openFieldRequirements` :49-53
  `doAction("health_landing.action_admin_field_req", {clearBreadcrumbs:true})`). Action
  `health_landing/views/admin_center_menus.xml:13-16`. Add a tile from the overlay via `t-inherit` +
  `patch(AdminSettings.prototype)`; gate it on `canManageAccess` (clinic admin implies access manager).

## IA hooks (`health_cms_ia/hooks.py`)
- `MOVE` :174-279 `{item: (section, parent|None, seq)}` (Settings rows :252-278); `EXACT` :335-354; `EXTRA` :357-363;
  applied by `consolidate_ia` :852-875 (post_init + migrations). `apply_moves` :552-574 touches ONLY `MOVE` keys —
  an unknown item is left alone. `apply_gates` :734-782 gives an ungated item in a managed section the area roles
  (`AREA_ROLES[S_ADMIN] = (OWNER, ADMIN)` :321). The H1 sidebar row survives; it must ship its own `biz_role_ids`
  (test_05d `health_cms_ia/tests/test_consolidated_menu.py:363-377`) and a unique `(section, parent, seq)`
  (test_02c :254-269): free top-level S_ADMIN seqs 65 / 75 / 85; P_MASTER children use 10-90.

## PHI (`health_phi_encryption/models/res_partner.py`) — for FS-H4
- `PARTNER_PHI_MAP` :15-27 (`exposed → (enc col, bidx col|None)`), `_phi_map` class attr :33;
  `_compute_phi_fields` :89-93 / `_inverse_phi_fields` :95-101; `_phi_bidx_domain` :104-138. Only hook =
  override `_phi_map` in an `_inherit`; `@api.depends(*PARTNER_PHI_MAP.values())` :89 frozen at import; each new
  field needs compute/inverse + `_enc`/`_bidx` columns. Same pattern `health_clinical_note.py:21` (`NOTE_PHI_MAP`).
  → Runtime-created manual fields cannot join this set without a dynamic layer: FS-H4 must design "PHI custom
  field = stored encrypted token in the manual column" (encrypt/decrypt in a `create/write/read` override keyed on
  `fs.field.meta.phi`), not via `_phi_map`.

## Catchment scope / other arch processors
- `health_catchment_scope/models/ir_ui_view.py:32-46` post-processes SEARCH arches only (no form impact; no `get_view` override).
- `health_field_requirements/models/ir_ui_view.py:19-25` reads `model_access_rights` AFTER `super()` pops it → **dead
  hook**: requirement rules do NOT mark fields required in the arch (server-side create/write enforcement still
  works via `base_model_override.py`). Pre-existing; report to owner as a Field Requirements defect (visual asterisk
  missing), not a Studio problem.
- `health_tenant_workspace/models/base.py:52` `get_view` debrands strings only.

## Actions / sidebar
- Clients row `health_cms_sidebar/data/cms_sidebar_items_ops.xml:25-33` (`item_ops_clients`, noupdate=1) →
  `health_fieldservice.action_ops_client_list_native` (`ops_client_list_views.xml:91-101`, pins form
  `view_health_patient_form_ops`); also `action_ops_client_profile_form` (`ops_client_profile_form_views.xml:627-633`).
- Contacts row `cms_sidebar_items_crm.xml:14-23` → `health_crm.action_crm_contact_list_native` (defined TWICE in
  `crm_center_views.xml` :416 and :496 — the second adds calendar); `action_crm_contact_form_native` :430.

## Other surprises
- The client form is priority 0 → default res.partner form everywhere (`action_crm_client_list` :449 relies on it).
- Client form has no editable `name`; required catchment/phone are view-level `required="1"`.
- `ops_booking_form.xml:15` calls `navigateTo('dashboard')` but the controller defines no `navigateTo` (latent bug, unrelated).
- `GLOBAL_SCOPED_MODELS` (`catchment_scope.py:60`) is unused.
