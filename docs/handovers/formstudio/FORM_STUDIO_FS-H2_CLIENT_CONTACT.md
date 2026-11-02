# FORM STUDIO — FS-H2: the Client and Contact Workspace screens

Handover from Fable (design) to Opus (implementation). Written 2026-11-03 after the FS-H1 report.
Read in this order before touching code:

1. `docs/strategy/HANDOVER-CONVENTIONS.md` — §2 deploy, §5 ledger (especially §5.52, §5.114, §5.126,
   §5.127, §5.147, §5.148, §5.178, §5.192, §5.200, §5.210, §5.215, §5.216, §5.228, §5.249, §5.250,
   §5.262, §5.264 and the eight FS-H1 entries §5.265–§5.272).
2. `docs/handovers/formstudio/FORM_STUDIO_FS-H1_CORE.md` §0 (standing rules — they ALL bind here too)
   and §3 (the engine contract as designed).
3. `docs/handovers/formstudio/FORM_STUDIO_FS-H1_REPORT.md` — what was actually built, deviations D1–D23.
   The code is the truth where the two differ.
4. `docs/handovers/formstudio/FS-H2_PLUMBING_NOTES.md` — verified file:line facts for this phase.
   **Do not re-derive them; re-check a line number before you anchor on it.**
5. The engine as shipped: `addons/biz_form_studio/models/fs_layout.py` (writer, validator),
   `fs_studio.py` (`_base_cards` :261, `_field_info` :359, `get_studio` :427), `fs_host.py`,
   `static/src/js/studio/studio_editor.js` (`defaultAnchor` :184, `sectionsAt` :189, `cardsBefore` /
   `cardsTabs` :203-218, `setSectionAnchor` :769), `static/src/xml/studio/studio_editor.xml` (:453-456
   the position control), `studio_button.js` / `studio_button.xml`.
6. The two screens: `addons/health_fieldservice/views/ops_client_profile_form_views.xml` (:156-242 the
   Overview pack and tray) and `addons/health_crm/views/crm_center_views.xml` (:196-241 the Overview pack).
7. The fold tray: `addons/health_theme/static/src/js/ws_fold_tray.js` + `xml/ws_fold_tray.xml`.

## 0. Standing rules (restated; §0 of FS-H1_CORE is binding in full)

- **White-label:** "Odoo" never in anything a user can see (test 12a / 16 keep scanning).
- **Generic core:** `biz_form_studio` names no product, no `health_`, no clinic/nurse/patient/Carejiox.
  Everything about the Client or Contact screen lives in `health_form_studio`.
- **Plain copy** in user words; `x_fs_` names never shown.
- **Design:** flat `--bzk-*` / `--vuf-*` tokens, `ic()` icons (add glyphs to `biz_kit/static/src/js/kit_icons.js`
  only), no gradients, no emoji, no `font-family` (test 12d), no font-awesome except the sidebar contract.
- **Vietnamese** for every new string, in both `vi.po` files, generated from the framework's export.
- **Chatter** untouched. **Host models** get no business-logic change.
- **Shared-module edits sanctioned for this phase, and ONLY these:**
  - `addons/health_theme/static/src/js/ws_fold_tray.js` (+ its xml if a template change is unavoidable) — the fold-tray seam §3.4.
  - `addons/biz_kit/static/src/js/kit_icons.js` — new glyphs only.
  - Nothing in `health_fieldservice`, `health_crm`, `health_landing`, `health_cms_sidebar`. Every hook into
    their screens is a `t-inherit` / inherited view / `patch()` shipped by `health_form_studio`.
- **Rehearse on a clone** (`carejiox_fs2`, same recipe as FS-H1: slug pointed at nowhere, jobs and mail
  off, new `database.uuid`, private addons tree first on the path, `--db-filter=^carejiox_fs2$`,
  `systemd-run`). Never `-t` on the live box. Layout validator (`fs.studio.validate_all`) after every
  upgrade on every DB.
- **Live has 0 layouts and 0 `x_fs_` fields** (FS-H1 report). Keep it that way: on live you may open
  Studio and the library; you publish nothing and create no field.
- **Commits** on 19.0, plain-sentence messages, each ending
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. **Do not push.**

## 1. Scope

**Goal.** An Owner or Admin opens the **Client** record or the **Contact** record, presses **Studio** in the
screen's own top bar, adds fields and sections exactly as on the Incident screen, and the result is drawn
as Workspace cards inside the Overview tab — folding into the "Not filled yet" tray like every other card
when empty. The same person can give a dropdown's options Vietnamese labels.

**In scope**
1. Engine (generic, `biz_form_studio`): the Workspace writer (`pack_end` anchor, card markup, fold
   attributes), the Workspace schematic reader, the editor's Workspace mode, the shared Studio button
   template, Vietnamese option labels, a leaner `fields` payload.
2. Overlay (`health_form_studio`): the Client and Contact hosts (open cards, locked fields, zones, lock
   reasons in Vietnamese), the Studio button in both custom headers, the Contact fold tray, the Form
   Studio tile on the Settings landing (if `health_landing` is present), vi.po.
3. The fold-tray seam in `health_theme`.
4. Tests 17–32, browser QA 11–20, clone rehearsal, live upgrade on `carejiox`, `carejiox_template`, `hhh`.

**Binding non-goals (do NOT build)**
- No list columns, no search filters, no export reach (FS-H3 / FS-H4).
- No encryption of custom fields, no PWA / family portal reach (FS-H4). The PHI switch keeps FS-H1's
  honest copy ("exports, reports and the app follow from a later release").
- No moving, hiding, renaming or re-labelling of **standard** fields, and no help text on them.
  (Standard field rows refuse writes; a view-attribute route exists but is a later decision for the owner.)
- No Studio on Booking (FS-H3), no Studio inside dialogs, no Studio on the base partner form or any
  other `res.partner` / `crm.lead` form: only the two Workspace forms named in §2.
- No change to which fields fold on the two screens today (the static tray configuration stays as is;
  Studio only ADDS to it).
- No wiring of the validator into `carejiox-deploy` (FS-H5).
- No re-ordering Studio cards among the standard cards: Studio cards go at the END of the Overview pack
  (before the "Recent visits" widget on Client). Order among Studio cards is editable.

## 2. Verified plumbing (from FS-H2_PLUMBING_NOTES.md — re-check lines, do not re-derive)

| Fact | Where |
|---|---|
| Client form xmlid `health_fieldservice.view_health_patient_form_ops`, priority 0, primary. It is the DEFAULT `res.partner` form everywhere. `js_class="ops_client_profile_form"`, class `ws-workspace` | `ops_client_profile_form_views.xml:5-11` |
| Client Overview page `profile_overview` :160 → ONE `div.ws-pack` :161 (no `name`) → cards `personal_card` :163, `contact_card` :180, `care_card` :192, `identity_card` :213, `commission_card` :225, then `<widget name="ws_client_visits"/>` :236 as LAST child. Tray :239-241 with `identity_card` and `commission_card` | same file |
| Card markup: `div.vu-detail-card.ws-card[name] > div.vu-card__title (div.vu-section__icon[data-icon] + div TITLE) + group > field*` | :163-178 |
| Notebook is NOT `//sheet/notebook` (sheet :51 → `.ws-page` :65 → `.ws-main` :66 → notebook :156) → `has_notebook` is False on both Workspace forms | same file |
| Contact form xmlid `health_crm.view_crm_contact_form_crm_center`, priority 50, primary, `js_class="crm_contact_form_view"`, class `ws-workspace`; Overview page `overview` :200 → `div.ws-pack` :201 → `contact_card` :203, `reached_card` :216, `status_card` :228; **no tray, no trailing widget**; NO chatter by design | `crm_center_views.xml:76-241, 362-368` |
| Both controllers extend `FormController` → the FS-H1 `patch(FormController.prototype)` already gives them `fsCanEdit`, `fsIcon`, `openFormStudio` | `health_fieldservice/static/src/js/ops_client_profile_form.js:10`, `health_crm/static/src/js/crm_contact_form.js:17` |
| Both templates hide the stock control panel by CSS, so the FS-H1 button is invisible. Header right slots: `div.ops-header-right` (`ops_client_profile_form.xml:19-23`), `div.crm-form-header-right` (`crm_contact_form.xml:19-23`) — each holds `<t t-if="canEdit"><FormStatusIndicator …/></t>` | those xml files |
| Fold tray: `cards` prop optional; `get cards()` :71; `formRoot` :133; `cardEl(name)` = FIRST `[name="…"]` in the form (field roots and tab links also carry `name`); `sync()` :142 toggles `ws-card--folded`, reads `.vu-card__title` text; `cardIsEmpty` :91 (`every`; unknown field = empty; invalid never folds) | `health_theme/static/src/js/ws_fold_tray.js` |
| Plain-div attributes survive form compilation (`data-*` included) | `web/static/src/views/view_compiler.js:394-402` |
| Forms have no RNG schema (FS-H1 report) → `data-fs-*` attributes pass `_check_xml` | — |
| `.ws-pack` masonry `columns: 2 340px`, children `break-inside: avoid`; `.ws-card--folded {display:none !important}`; card chrome applies to `.ws-pack > .vu-detail-card` | `ws_workspace.scss:887-1004` |
| `fs.host._for` matches the view id or its one-level primary copy; `probe` never raises | `fs_host.py:70`, `fs_studio.py:243` |
| Writer today: anchors `card` (`//div[@name='X']/group` inside for kit ws), `before_notebook`, `sheet_end`; `_clean_sections` :62 validates kinds; `_render_arch` :129 | `fs_layout.py` |
| `_base_cards` walks `group` / `notebook` / `div.oe_title` / plain `div`,`span`; a page becomes ONE tab card with all its fields; Studio's own groups vanish because they hold no std fields | `fs_studio.py:261-356` |
| `_field_info` returns EVERY std field of the model (hundreds on `res.partner`) | `fs_studio.py:359` |
| Settings landing tile markup + gates; add a tile via `t-inherit` + `patch(AdminSettings.prototype)`; gate on `canManageAccess` | `health_landing/static/src/xml/admin_settings.xml:12-55`, `js/admin_settings.js:24-53` |
| Locked field names (exact) for `res.partner` and `crm.lead` | FS-H2_PLUMBING_NOTES §"Locked fields" |
| Selection records: `ir.model.fields.selection.name` is translatable (`translate=True`); writes under a vi context replace the vi copy (§5.270) → write EN under `lang='en_US'`, VI via `update_field_translations('name', {'vi_VN': {...}})` | `base/models/ir_model.py` (check the field def), §5.270 |

## 3. Architecture

### 3.1 `fs.host` — two new fields (core)

```python
pack_page = fields.Char(help="Workspace forms only: the tab whose card pack receives new sections.")
pack_tail = fields.Char(help="Workspace forms only: a widget at the end of the pack that new "
                             "sections are placed before. Empty: sections go last.")
```
Validation (`_check_ws`): kit `ws` requires `pack_page`; kit `vu` must leave both empty.

### 3.2 The Workspace writer (`fs_layout.py`)

New anchor kind **`pack_end`** (allowed only when `host.kit == 'ws'`). `before_notebook` and `sheet_end`
are **refused** for kit `ws` in `_clean_sections` ("The layout could not be read. Reload Studio.") — a
Workspace screen has exactly two places: inside an open card, or a new card at the end of the pack.

Rendering a `pack_end` section:
```xml
<xpath expr="//page[@name='profile_overview']/div[hasclass('ws-pack')]/widget[@name='ws_client_visits']" position="before">
  <div class="vu-detail-card ws-card fs-card" name="fs_a1b2c3" data-fs-fold="1" data-fs-fields="x_fs_a,x_fs_b">
    <div class="vu-card__title">
      <div class="vu-section__icon" data-icon="layers"/>
      <div>Section title</div>
    </div>
    <group>
      <field name="x_fs_a"/>
      <field name="x_fs_b" required="1"/>
    </group>
  </div>
</xpath>
```
- When `pack_tail` is empty (Contact): `expr="//page[@name='overview']/div[hasclass('ws-pack')]"` with
  `position="inside"`.
- One xpath per Studio section, in section order, so the order on screen is the order in Studio.
- The title `<div>` text is the EN title; the VI title goes through `_write_title_translations` exactly
  like a group `string` (check that `update_field_translations` on `arch_db` picks up element TEXT the way
  it picks up `string` attributes — it does for translatable text nodes; prove it in test 21).
- `data-icon="layers"` reuses the Workspace icon mechanism the static cards use (`vu-section__icon`).
  Check how `data-icon` is resolved (a CSS mask map in health_theme); if "layers" is not in that map,
  pick one that is and note it.
- **`data-fs-fields`** lists the section's `x_fs_` names in order; **`data-fs-fold="1"`** marks the card
  as one the tray may fold. Both are read by §3.4.

Rendering a `card` section on kit `ws` (dropping Studio fields INTO an open standard card) — two xpaths:
```xml
<xpath expr="//div[@name='identity_card']/group" position="inside">
  <field name="x_fs_c"/>
</xpath>
<xpath expr="//div[@name='identity_card']" position="attributes">
  <attribute name="data-fs-fields">x_fs_c</attribute>
</xpath>
```
The attributes xpath lets the tray union the Studio field into the card's emptiness test (§3.4), so a
card never folds while a Studio field in it holds a value.

Keep `_render_arch` deterministic; `_validate_one` needs no change beyond the new kind.

### 3.3 The Workspace schematic reader (`fs_studio._base_cards`)

For kit `ws`, when a notebook page contains `div[hasclass('ws-pack')]`:
- emit `{'kind': 'pack', 'key', 'name': <page name>, 'title': <page string>}` as a marker,
- then one card per `div.vu-detail-card[@name]` child: `kind 'std'`, `name`, `title` = text of
  `.vu-card__title` (the LAST `div` child's text, stripped), `open` = name in `host.sections`,
  `tab: False`, `fields` = `collect(card)`; **skip** cards whose `name` starts with `fs_` (Studio's own,
  present in the combined arch),
- then `{'kind': 'pack_end', 'key'}`.
Other pages stay tab cards as today. The hero (`div.ws-hero`) fields appear as a read-only "Header" card
if `collect` finds any; otherwise nothing. `get_studio` returns `host.pack_page` and `pack_tail`.

**Leaner `fields` payload** (both kits): `_field_info` returns std entries only for names that appear in
`cards` (the schematic shows nothing else). Custom `x_fs_` entries unchanged. On `res.partner` this cuts
the payload from hundreds of fields to ~40. Test 23 asserts the Incident payload still has every field
the Incident schematic shows.

### 3.4 The fold-tray seam (`health_theme/static/src/js/ws_fold_tray.js`) — sanctioned edit

- `this.discovered = useState({})`.
- In `sync()`, scan `this.root.el.closest('.tab-pane') || this.formRoot` for `[data-fs-fold="1"][name]`
  → `{name: fields}` where `fields` = `data-fs-fields` split on `,` (fallback: `.o_field_widget[name]`
  inside the card). Also scan `[data-fs-fields]:not([data-fs-fold])` (open standard cards that received
  Studio fields) → union those names into the STATIC card's list.
- Write `this.discovered` only when the JSON differs (no `onPatched` loop).
- `get cards()` = static cards with Studio names unioned, plus discovered Studio cards.
- `chips` and the template unchanged (one chip per folded card; the chip label is the card's
  `.vu-card__title` text, so a Vietnamese title shows in Vietnamese).
- `cardEl(name)` is unchanged, hence the rule: a Studio card's `name` is `fs_<sectionid>` and
  `SECTION_ID_RE` already forbids it from matching any field or page name. Add a guard in
  `_clean_sections`: refuse a section id whose `fs_<id>` equals an existing field name on the model.
- Cost: one-frame flash on first mount; accept it. Bump `health_theme` version.

### 3.5 The Studio button on the custom headers

Core: move the button body out of the `web.FormView` xpath into a named template
`biz_form_studio.StudioButton` (props: none; it reads `fsCanEdit`, `fsIcon`, `openFormStudio` from the
calling component) and `t-call` it from the FS-H1 xpath, so the overlay can `t-call` the same markup.

Overlay (`health_form_studio/static/src/xml/ws_headers.xml`):
```xml
<t t-inherit="health_fieldservice.OpsClientProfileFormView" t-inherit-mode="extension">
  <xpath expr="//div[hasclass('ops-header-right')]" position="inside">
    <t t-call="biz_form_studio.StudioButton"/>
  </xpath>
</t>
<t t-inherit="health_crm.CrmContactFormView" t-inherit-mode="extension">
  <xpath expr="//div[hasclass('crm-form-header-right')]" position="inside">
    <t t-call="biz_form_studio.StudioButton"/>
  </xpath>
</t>
```
Placement: FIRST in the right slot (before the save indicator), `position="inside"` prepends? No —
`inside` appends. Use `//div[hasclass('ops-header-right')]/t[@t-if='canEdit']` `position="before"` so the
button sits left of the save indicator. Visually: `btn-secondary`, same height as the indicator; check
`.ops-top-header` / `.crm-form-header` CSS for alignment and add a small rule in
`health_form_studio/static/src/scss/ws_headers.scss` if needed (tokens only).

Both `health_fieldservice` and `health_crm` become dependencies of `health_form_studio` (they are
installed on every DB — verify with `ir.module.module` on the clone before relying on it).

### 3.6 The editor's Workspace mode (`studio_editor.js` / `.xml`)

- `defaultAnchor` → `'pack_end'` when `host.kit === 'ws'`.
- `sectionsAt('pack')` = sections with anchor `pack_end`; `cardsBefore` / `cardsTabs` get a sibling
  `cardsPack` = cards between the `pack` and `pack_end` markers; the schematic for kit `ws` draws:
  the Header card (read-only, if any) → the Overview pack as a 2-column grid of standard cards (open
  ones accept drops, closed ones dimmed with the FS-H1 reason) → Studio cards → the "New section" drop
  zone → the remaining tabs (read-only). Reuse the FS-H1 card components; only the container differs.
- The position control (`studio_editor.xml:453-456`, "Above the tabs" / "At the bottom") is hidden for
  kit `ws` and replaced by a static line "In the Overview tab, after the standard cards".
- `moveSection` works within `pack_end` peers as it does today.
- Everything else (palette, settings panel, publish sheet, history, DELETE) unchanged.

### 3.7 Vietnamese dropdown option labels (core)

- `fs.field.meta` gets nothing new; the VI label lives on the selection record's translation.
- The editor's option list gets a second input per option ("Tên tiếng Việt") shown when `lang` or the
  VI language is active (reuse the `title_vi` pattern).
- `create_field` / `update_field` option specs accept `{value?, label, label_vi?, retired?}`.
  `_apply_options` writes EN under `with_context(lang='en_US')` and then
  `selection.update_field_translations('name', {'vi_VN': {label_en: label_vi}})` for each option with a VI
  label (§5.270). `_field_info` returns `label_vi` per option (read `with_context(lang='vi_VN').name`,
  empty when it equals the EN label).
- Test 26 proves a Vietnamese reader sees the VI option on the form (`fields_get` under `lang='vi_VN'`).

### 3.8 Overlay data (`health_form_studio`)

`data/fs_hosts.xml` — two new records (noupdate="0"):

**Client** — `fs_host_client`: name "Client", model `res.partner`,
`base_view_xmlid health_fieldservice.view_health_patient_form_ops`, kit `ws`, `pack_page profile_overview`,
`pack_tail ws_client_visits`, `pwa_label "Nurse app"`,
sections = `[{name: personal_card, title: Personal}, {contact_card, Contact}, {care_card, Care},
{identity_card, Identity}, {commission_card, Commission}]`,
locked_fields (reasons in plain words, each added to `HOST_TEXT` with a VI translation):
- `name` "Identifies the client everywhere." · `first_name` / `middle_name` / `last_name` / `vietnamese_name`
  "Builds the client's name." · `birth_date` "Used for age, consent and insurance." · `phone` / `mobile` /
  `email` "Used to reach the client and by the messaging channels." · `catchment_province_id` "Decides which
  team can see this client." · `primary_facility_id` "Links the client to their facility." · `national_id` /
  `cccd_number` "Stored encrypted by the system." · `insurance_number` "Used on insurance claims." ·
  `patient_category_id` "Drives pricing." · `gender_id` "Used on clinical records."
locked_zones = `[{name: people_panel, title: "People", reason: "Drawn by the system."}]` (the rail panel
`div.ws-panel--people[name=people_panel]` :614 — verify it carries `name`; if the hero has a `name`, add it
as "Header", else leave it).

**Contact** — `fs_host_contact`: name "Contact", model `crm.lead`,
`base_view_xmlid health_crm.view_crm_contact_form_crm_center`, kit `ws`, `pack_page overview`, no
`pack_tail`, `pwa_label` empty (the mobile app does not show contacts: the PWA switch should read "Mobile
app" and the FS-H1 honest copy applies),
sections = `[{contact_card, Contact}, {reached_card, "How they reached us"}, {status_card, Status}]`,
locked_fields: `name` / `contact_name` "Identifies the contact." · `phone` / `mobile` / `email_from`
"Used to reach the contact." · `stage_id` / `contact_status` / `contact_outcome` "Drives the contact
workflow." · `user_id` / `team_id` "Decides who works this contact." · `catchment_province_id` /
`district_id` / `facility_id` "Decides which team can see this contact." · `mode_of_contact_id` "Used in
channel reports." · `patient_id` "Links the contact to a client." · `campaign_id` / `medium_id` /
`source_id` "Written by the website and ads tracking."
locked_zones = `[{name: people_panel, title: "People", reason: "Drawn by the system."}, {name:
contact_history, title: "Contact history", reason: "Drawn by the system."}]`.

`views/crm_contact_tray.xml` — inherited view on `health_crm.view_crm_contact_form_crm_center`
(`mode="extension"`, priority 100, this is OVERLAY DATA not a Studio layout):
```xml
<xpath expr="//page[@name='overview']/div[hasclass('ws-pack')]" position="after">
  <widget name="ws_fold_tray"/>
</xpath>
```
With no static `cards` it shows nothing until a Studio card is discovered (root gets `ws-fold-tray--empty`).
Confirm the empty tray paints no gap (check `.o_widget_ws_fold_tray` / `--empty` CSS :1071-1125).

`models/fs_host.py` — extend `HOST_TEXT` with every new reason and zone title above.

**Settings tile** (`static/src/xml/admin_settings.xml` + `js/admin_settings.js` in the overlay): `t-inherit`
`health_landing.AdminSettings` (check the exact template name in `health_landing/static/src/xml/admin_settings.xml`)
adding a tile "Form Studio" / "Add fields to the Client, Contact and Incident screens" after the Field
Requirements tile, `t-on-click="openFormStudio"`, gated `t-if="canManageAccess"`; `patch(AdminSettings.prototype,
{ openFormStudio() { doAction('biz_form_studio.action_fs_library', {clearBreadcrumbs: true}) } })`. The tile
icon follows the tile pattern (inline fa icon IS the pattern there — keep the pattern, note it). `health_landing`
becomes a dependency only if it is installed on all three DBs (it is — verify).

`i18n/vi.po` both modules regenerated from the export.

Bump versions: `biz_form_studio` 19.0.1.1.0, `health_form_studio` 19.0.1.1.0, `health_theme` patch bump.

## 4. Safety rails

- A `pack_end` section whose page or pack is missing fails in `_render_arch` with a UserError BEFORE any
  view write; `_validate_one` switches the layout off, never the screen (FS-H1 behaviour, prove on ws in
  test 24).
- A Studio card id colliding with a field or page name is refused in `_clean_sections` (§3.4).
- Registry rebuild on `res.partner`: measure (§5 test 30) and report; if `create_field` + first next
  request exceeds 10 s on the clone with 2 workers, say so in the report — do not optimise blind.
- The Client form is the default partner form. A Studio layout on it is drawn wherever that form is
  opened full-page (a Booking's client link, Contacts app, etc.) — expected, say it in the report. The
  Studio BUTTON only appears on the Workspace controller's header (+ the stock control panel where it is
  visible). Dialogs never.
- Nothing is published on live. The clone is destroyed after QA (filestore, private tree, units, tunnel).

## 5. Tests (numbered; add to `biz_form_studio/tests/test_fs_core.py` and `health_form_studio/tests/test_fs_health.py`)

Core (a generic ws host built in the test on a plain model with a hand-written Workspace-shaped form, as
FS-H1 did for its generic cases — or `res.partner` with a test view; no product words):
- **17** `pack_end` section renders the card markup of §3.2 (class, name, `data-fs-fold`, `data-fs-fields`
  in field order, title text, group with fields) placed `inside` the pack when `pack_tail` is empty.
- **18** With `pack_tail` set, the xpath is `…/widget[@name=tail]` `position="before"`.
- **19** `before_notebook` / `sheet_end` refused on kit `ws`; `pack_end` refused on kit `vu`;
  kit `ws` without `pack_page` refused by the constraint.
- **20** `card` anchor on kit `ws` emits BOTH xpaths (field inside `/group`, `data-fs-fields` attribute).
- **21** A VI section title on a `pack_end` card reaches `get_combined_arch()` under `lang='vi_VN'`
  (text node translation) and the EN arch is unchanged.
- **22** `_base_cards` on a Workspace arch: `pack` marker, one card per named `vu-detail-card` with the
  title text and `open` flag, Studio's own `fs_` cards skipped, `pack_end` marker, later tabs as tab cards.
- **23** Leaner payload: `fields` holds exactly the std names present in `cards` + every `x_fs_` field; the
  FS-H1 Incident payload still contains every field its schematic lists.
- **24** Break the pack (rename the page in a test copy of the base view) → `validate_all` switches the
  layout off with a reason; the base form still renders.
- **25** Section id `fs_<id>` equal to an existing field name is refused.
- **26** Dropdown options with `label_vi`: EN names under `en_US`, VI names under `vi_VN`; a reader under
  `vi_VN` gets the VI label from `fields_get`; an option without VI falls back to EN.
- **27** Source gates 12a–12f still pass over the new files (run the FS-H1 gate tests).

Overlay:
- **28** Both hosts resolve (`_base_view` non-empty, kit `ws`, `pack_page` exists in the combined arch,
  every open card name exists as `div[@name]` in it, every locked field exists on the model, `pack_tail`
  exists on Client); `HOST_TEXT` covers every reason and zone title; a VI reader gets VI reasons.
- **29** End to end on `res.partner`: clinic admin creates a text field and a dropdown, publishes one
  `pack_end` section and one field into `identity_card`; the combined Client arch holds the card and the
  attribute; a plain user with `group_healthcare_base` reads a Staff field; a user outside staff gets
  AccessError; rollback to v1 restores v1's arch.
- **30** Timing on `res.partner` (clone, logged not asserted): `create_field` wall time, `publish` wall time,
  first `fields_get` after each. Report the numbers.
- **31** End to end on `crm.lead`: same as 29 with `reached_card`; the overlay tray view is in the combined
  arch exactly once.
- **32 (HttpCase)** Over JSON-RPC as the clinic admin: `probe` is true for (`res.partner`, Client view id)
  and for (`crm.lead`, Contact view id), false for (`res.partner`, the base partner form id);
  `get_studio` for the Client returns `host.kit == 'ws'`, the `pack` marker, five open cards.
- Re-run the FS-H1 suite in full (biz_form_studio, health_form_studio, health_incident, biz_access,
  biz_kit, health_theme if it has tests, health_fieldservice, health_crm) — green is the gate.

## 6. Browser QA (clone, three personas as in FS-H1: Admin-role user, Doctor, Vietnamese admin; 1440 and 820 px)

- **11** Client record: **Studio** button sits in the screen's own top bar left of the save indicator;
  the Incident screen still shows its button where it was.
- **12** Open Studio: schematic shows Header (if any), the five Overview cards (all droppable), the new
  section drop zone, then the other tabs dimmed. No "Above the tabs / At the bottom" control.
- **13** Add "Preferred time slot" (dropdown with 3 options + VI labels) into a new section "Care
  preferences" / "Ưu tiên chăm sóc"; add "Lift access" (yes/no) into **Identity**. Publish.
- **14** Back on the Client Overview: the new card is drawn at the end of the pack before Recent visits,
  styled like its neighbours (title, icon, read-first inputs); "Lift access" sits in Identity.
- **15** Fold behaviour: on a client with Identity empty and no Studio values, Identity AND the new card
  appear as chips in "Not filled yet"; set "Lift access" → Identity stays open; clear it → folds again.
- **16** Vietnamese admin: the section title, the field labels and the dropdown options read in Vietnamese
  on the form and in Studio; the tray chip reads the VI title.
- **17** Contact record: Studio button in its top bar; add a field into "How they reached us" and a new
  section; the new tray appears only when a Studio card is empty; with no Studio card the Overview looks
  exactly as before (pixel-compare against a pre-change screenshot).
- **18** Doctor persona: no Studio button on Client, Contact or Incident; a Staff field shows; an
  Admins-only field does not.
- **19** 820 px: the editor's three columns do not overlap (FS-H1 fix holds for the ws schematic); the
  Studio card packs to one column on the Client Overview.
- **20** Settings landing: the Form Studio tile opens the library; a Head-nurse persona does not see it.
- Console clean on every step. Evidence PNGs to `docs/handovers/formstudio/fs_h2_shots/`.
- Live (after upgrade): steps 11, 12 and 17's first half on `carejiox.com` and `hhh.carejiox.com` on an
  existing Client and Contact — **open only, publish nothing**.

## 7. Deploy

1. Clone `carejiox` → `carejiox_fs2` (FS-H1 recipe). Install order there: `-m biz_form_studio,health_form_studio`
   plus `-m health_theme` (fold tray), then `validate_all`, tests §5, QA §6.
2. Backups of all three DBs to `/var/backups/fs2/`.
3. Live: `carejiox-deploy -d` (copy the four changed modules: biz_form_studio, health_form_studio,
   health_theme, biz_kit if touched) then `-m biz_form_studio,health_form_studio,health_theme` on
   `carejiox`, `-D carejiox_template …`, `-D hhh …`. Exit 0 and `/web/login` 200 each. Check the template's
   jobs are still OFF afterwards (FS-H1 found 7 switched on by a run — switch off again if so and say so).
4. `fs.studio.validate_all` on each DB (expect 0 layouts). Bundle serves the new JS/CSS (hash changed).
5. Destroy the clone and every transient.

## 8. Report back (`docs/handovers/formstudio/FORM_STUDIO_FS-H2_REPORT.md`)

Same shape as the FS-H1 report: one plain paragraph for the owner; rules restated; test table 17–32 with
the assertion each proves; QA 11–20 with persona and PNG names; deploy log; deviations numbered D1…;
plumbing drift found; new ledger entries appended to `docs/strategy/HANDOVER-CONVENTIONS.md` (§5.273+);
the `res.partner` timing numbers; the pixel-compare result for the unchanged Contact Overview; what FS-H3
(Booking + list columns) needs from the engine. Commit code and report separately. Do not push.
