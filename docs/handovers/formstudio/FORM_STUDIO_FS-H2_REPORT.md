# FORM STUDIO — FS-H2 report (the Client and Contact screens)

Written 2026-11-03 by the Opus implementer. Handover: `FORM_STUDIO_FS-H2_CLIENT_CONTACT.md`.

## In one paragraph (for the owner)

The **Studio** button now sits in the top bar of every **Client** record and every **Contact**
record, next to the save buttons. Pressing it opens the same Studio as on Incidents, but drawn
the way these two screens look: the Overview cards side by side, then a place to add a new
card, then the other tabs (greyed, read-only). A field can go into one of the existing cards
(for example "Lift access" into Identity) or into a new card of its own (for example "Care
preferences"); the new card appears at the end of the Overview, before "Recent visits", looks
exactly like the cards around it, and folds into "Not filled yet" when it is empty, like every
other card. Dropdown choices can now have a Vietnamese name each, and a Vietnamese reader sees
them. Settings now has a **Form Studio** tile that opens the field list. It is **live on
carejiox, the golden template and hhh**; nothing was published and no field was created on
the live databases. One thing you should know: on today's live system only the **Owner** role
can open both the Client and the Contact screens — the Admin role is refused on both by older
access settings that this work did not touch (details under "Findings").

## Standing rules (stated back)

- **White-label:** no "Odoo" in anything a user sees. The core's sources and `vi.po` are
  scanned by test 12a (re-run over the FS-H2 files, test 27); both `vi.po` msgstr scanned
  (test 16). New user strings checked by hand.
- **Generic core:** `biz_form_studio` names no product, no `health_`, no clinic/nurse/patient;
  everything about the Client and Contact screens lives in `health_form_studio`.
- **Plain copy;** `x_fs_` names never shown (they appear only in a hidden attribute the fold
  tray reads — see D12).
- **Design:** flat `--bzk-*` / `--vuf-*` tokens; `ic()` icons; no gradient, no emoji, no
  `font-family` (12d). No new glyph was needed in `kit_icons.js`.
- **Vietnamese** for every new string, generated from `odoo-bin i18n export` on the clone and
  filled in (biz_form_studio 304 entries, health_form_studio 41; none empty).
- **Chatter untouched; host models untouched** (no field, rule or business logic changed).
- **Shared-module edits:** only `health_theme/static/src/js/ws_fold_tray.js` (+ the
  `health_theme` version bump 19.0.5.9.0 → 19.0.5.9.1). `kit_icons.js` not touched. Nothing in
  `health_fieldservice`, `health_crm`, `health_landing`, `health_cms_sidebar`: the hooks are
  template extensions, an inherited view and a `patch()` shipped by `health_form_studio`.
- **Rehearsed on a clone** `carejiox_fs2` (tenant slug → `nowhere_fs2_1`, 107 jobs off, mail
  servers off (0 active), new `database.uuid`, private tree `/odoo/fs2/addons` first on the
  path, `--db-filter=^carejiox_fs2$`, `systemd-run` unit `fs2-web` on 8199/8197). Never `-t`
  on the live box. `fs.studio.validate_all` after every upgrade on every database.
- **Live:** Studio opened only; nothing published, no field created (0 layouts, 0 drafts,
  0 `x_fs_` fields on all three after the work).
- **Commits** on 19.0, not pushed.

## Files

`addons/biz_form_studio/` (→ 19.0.1.1.0)
- `models/fs_host.py` — `pack_page`, `pack_tail`, constraint `_check_ws`.
- `models/fs_layout.py` — anchors per kit (`ANCHORS`), `pack_end` writer (`_ws_pack`,
  `_ws_card`), `data-fs-fields` attribute on open Workspace cards, placeholder "—" on Workspace
  fields, `fs_<id>`-collides-with-a-field guard, `_clean_sections(…, host)`.
- `models/fs_studio.py` — Workspace schematic reader (header card, pack markers, card titles),
  leaner `fields` payload, `pack_page`/`pack_tail` in `get_studio`, Vietnamese option names
  (`_write_options_vi`, create and update), `can_use()`, `_write_vi` also clears the 'stable'
  cache.
- `models/ir_model_fields.py` — Studio dropdowns built with a callable selection (D3).
- `static/src/xml/studio_button.xml` — named template `biz_form_studio.StudioButton`, called
  from the `web.FormView` extension.
- `static/src/js/studio/studio_editor.js`, `xml/studio/studio_editor.xml`,
  `scss/studio.scss` — Workspace mode, Vietnamese option inputs.
- `i18n/vi.po`, `tests/test_fs_core.py` (tests 17–27).

`addons/health_form_studio/` (→ 19.0.1.1.0) — depends now also on `health_fieldservice`,
`health_crm`, `health_landing` (installed on all three DBs, checked).
- `data/fs_hosts.xml` — Client and Contact hosts. `models/fs_host.py` — 23 new texts.
- `views/crm_contact_tray.xml` — the fold tray on the Contact Overview.
- `static/src/xml/ws_headers.xml`, `scss/ws_headers.scss` — button in both top bars.
- `static/src/xml/admin_settings.xml`, `js/admin_settings.js` — Settings tile.
- `i18n/vi.po`, `tests/test_fs_health.py` (23-Incident half, 28–32).

`addons/health_theme/static/src/js/ws_fold_tray.js` — contract 7 (discovery), `__manifest__.py`.

## Tests (§5)

Full run on the clone (no `-u`, ledger §5.275): `1 failed, 0 error(s) of 372 tests` —
biz_access 312, biz_form_studio 46, biz_kit 18, health_base i18n G1/G2 9, health_crm 17,
health_fieldservice 42, health_form_studio 22, health_incident 22, health_theme 16 (per-module
counts include sub-tests); 2 HttpCase classes started, 0 `setUpClass` errors. The one failure is
pre-existing (below). After the last small edits (editor CSS, header card): Studio suites +
incident + theme + i18n `0 failed, 0 error(s) of 85 tests`.

| # | Test | Result | What it proves |
|---|---|---|---|
| 17 | `test_17_pack_end_draws_a_workspace_card` | PASS | last child of the pack is `div.vu-detail-card.ws-card.fs-card[name=fs_p1]`, `data-fs-fold="1"`, `data-fs-fields="a,b"` in field order, icon `clipboard-list`, title text, `group` with both fields, `required="1"` only on the required one, placeholder "—"; the view's xpath is the pack, `inside` |
| 18 | `test_18_with_a_tail_cards_go_before_it_in_order` | PASS | pack order `first_card, second_card, fs_p1, fs_p2, fsx_tail`; every xpath is `…/widget[@name='fsx_tail']`, `before` |
| 19 | `test_19_places_that_do_not_exist_on_the_kit_are_refused` | PASS | `before_notebook` and `sheet_end` refused on ws; `pack_end` refused on vu; a ws host without `pack_page` and a vu host with one → ValidationError |
| 20 | `test_20_a_field_in_an_open_card_marks_the_card` | PASS | two xpaths (`…/group` inside, card `attributes`); combined card holds `email, a` and `data-fs-fields=a`, no `data-fs-fold`; a closed card refuses |
| 21 | `test_21_vietnamese_card_title_reaches_the_form` | PASS | the title TEXT node reads "Ưu tiên chăm sóc" under vi_VN and "Care preferences" under en_US; the English source unchanged |
| 22 | `test_22_the_schematic_reads_the_pack` | PASS | kinds `std(header), notebook, pack, std, std, pack_end, std(tab), zone`; titles from the card text; `open` per host; Studio's `fs_` card skipped; `has_notebook` False, `pack_page` returned |
| 23 | `test_23_the_fields_payload_holds_only_what_is_drawn` + overlay `test_23_incident_payload_keeps_every_field_it_draws` | PASS | standard entries == names in the cards (Workspace form and base partner form), every Studio field present; Incident payload still holds every field its schematic lists, `state` still locked |
| 24 | `test_24_a_broken_pack_switches_the_layout_off` | PASS | pack tab renamed underneath → `validate_all` lists it, `state='broken'`, reason kept, view inactive, form still draws |
| 25 | `test_25_a_section_named_like_a_field_is_refused` | PASS | id `vis` on `ir.model.fields` (has `fs_vis`) → "already taken"; `vix` accepted |
| 26 | `test_26_dropdown_options_in_vietnamese` | PASS | rows EN under en_US, VI under vi_VN, EN fallback; `fields_get` under vi_VN returns the VI label; `get_studio` returns `label_vi`; update adds/clears/sets VI names. **Failed before D3** (debranding override) |
| 27 | `test_27_one_button_template_for_every_header` + 12a–12f | PASS | one `t-name="biz_form_studio.StudioButton"` with the one button, called once from `web.FormView`; gates run over every FS-H2 core file |
| 28 | `test_28_both_hosts_resolve_against_todays_forms` | PASS | both hosts resolve (`_for` on the view), kit ws, pack exists once, every open card is in the pack, every locked field exists, zones exist, every reason/title in `HOST_TEXT`; Client tail exists; base partner form is no host; VI reasons and names |
| 29 | `test_29_end_to_end_on_the_client` | PASS | clinic admin: probe true; text (Staff), dropdown with VI option, yes/no; card before `ws_client_visits`, Identity carries `data-fs-fields`; VI card title; Staff field readable by a healthcare-base user, AccessError for an internal user outside staff; v2 then rollback(v1) → v1's arch; base partner form untouched |
| 30 | `test_30_timing_on_the_client` | PASS (logged) | in-process: create 0.49 s, publish 0.09 s — HTTP numbers below |
| 31 | `test_31_end_to_end_on_the_contact` (+31b) | PASS | a plain clinic admin gets probe False on Contact (no crm.lead write — §5.277); clinic admin + sales: tray widget in the combined arch exactly once, right after the pack; field into `reached_card`, card `fs_plan1` last in the pack; zones People + Contact history; switch reads "Mobile app". 31b: head nurse has no Studio on either record, `can_use` False |
| 32 | `test_32_probe_and_schematic_over_http` (HttpCase) | PASS | over JSON-RPC: probe true for Client and Contact views, false for the base partner form; `get_studio` Client: kit ws, one pack marker `profile_overview`, the five cards open, payload < 120 fields |

**Pre-existing failure (not caused by this phase):**
`health_fieldservice.tests.test_ws_client_form.TestWsClientForm.test_05_workspace_skeleton`
asserts the rail's first widget is `ws_client_shortcuts`; the client form's own XML now starts
the rail with `ws_rail_fold` (`ops_client_profile_form_views.xml:599-617`). The test reads the
view's own arch, which no FS-H2 file touches.

### `res.partner` timing (test 30, clone, 2 workers, over HTTP as the Owner)

| Step | Run 1 | Run 2 (new connection per call) |
|---|---|---|
| create a field | 0.42 s | 0.72 s |
| first `fields_get` after it | 0.08 s | 0.49 s, then 0.02–0.07 s |
| first request on the OTHER worker (registry reload, logged "Registry loaded in 1.493s") | — | 1.70 s |
| publish | 0.16 s | 0.34 s |
| first `get_views` after publish | 0.11 s | 0.12 s |
| delete the field (typed DELETE) | 1.40 s | 1.40 s |

Far under the 10 s line; nothing was optimised.

## Browser QA (§6) — evidence in `fs_h2_shots/`

Personas on the clone: **Owner** `fs2.qa.owner` (Owner role groups), **VI Owner**
`fs2.qa.owner.vi`, **Doctor** `fs2.qa.doctor`, **CRM** `fs2.qa.crm` (staff, not admin),
**Nurse/head nurse** `fs2.qa.nurse`, **Admin** `fs2.qa.admin` (Admin role groups — see D1).
1440 px unless stated. Served bundle checked first (`biz_form_studio.StudioButton`,
`data-fs-fold`, `o_fs_settings_tile`, `fs-pack` present; no CSS error).

| Step | Persona | Result | Evidence |
|---|---|---|---|
| 11 | Owner | Operations › Clients › An Xu: **Studio** in the screen's own top bar, left of the save indicator (indicator appears beside it when the record changes); Incident still shows its button right after the cog | `11a`, `11b`, `11c` |
| 12 | Owner | Header card (read-only), "Overview" pack as a 2-column grid of the five cards (all "Open card"), "Add a section", "Other tabs" (dimmed), the People area locked; no "Above the tabs / At the bottom" | `12a`, `12b`, `12c` |
| 13 | Owner | Dropdown dragged onto "Add a section": "Preferred time slot" / "Khung giờ ưu tiên", options Morning/Buổi sáng, Afternoon/Buổi chiều, Evening/Buổi tối; section "Care preferences" / "Ưu tiên chăm sóc" (place line "In the Overview tab, after the standard cards."); Yes/No dragged into Identity: "Lift access" / "Có thang máy"; publish sheet listed 3 changes | `13a`–`13d` |
| 14 | Owner | Card drawn last in the pack, before Recent visits; border, radius, padding, title size/weight/case/colour identical to Commission (computed styles compared); Lift access inside Identity | `14a` |
| 15 | Owner | Fresh load: Identity (4 fields) and Care preferences (1 field) both chips in "Not filled yet". Lift access ticked + saved → after reload Identity stays open. Unticked + saved → after reload Identity folds again (on the same page it stays open by the tray's rule 4) | `15a`, `15b`, `15c` |
| 16 | VI Owner | Form: card title "ƯU TIÊN CHĂM SÓC", label "Khung giờ ưu tiên", dropdown Buổi sáng / Buổi chiều / Buổi tối, chips "Giấy tờ 4 trường", "Ưu tiên chăm sóc 1 trường"; editor in Vietnamese with the option names | `16a`, `16b` |
| 17 | Owner | Contact (UAT20261029 existing client conversion): Studio in its top bar; "Referral code" into "How they reached us", "Visits wanted per week" in new card "Care plan wishes"; the tray appears only for the empty Studio card. **Pixel compare** before/after with no Studio card: 0 differing pixels below the top bar (diff box limited to y 17–121: the Studio button and the app-name text in the navbar) | `17a`, `17b`, `17c`, `17d` |
| 18 | Doctor / CRM | Doctor: no Studio button on Incident (new incident), and the Doctor cannot open Clients at all (bounced back to Clinical) nor Contacts (no access). CRM (staff): no Studio on Contact, Referral code shown; on the Client the served form arch holds the Staff field and NOT the Admins field, `fields_get` lists the Staff field only (the CRM role cannot open a client record — §5.277) | `18a`, `18b` |
| 19 | Owner, 820 px | Client Overview: every card at the same x/width (one column), no horizontal scroll; editor stacked (palette, screen, settings), pack one column, no overlap (`scrollWidth == clientWidth`) | `19a`, `19b` |
| 20 | Owner / head nurse | Settings › Settings: "Form Studio" tile after Field Requirements, opens the field library (6 fields, three screens); head nurse sees Company Profile, Pricing Engines, Field Requirements only, `can_use` false | `20a`, `20b`, `20c` |
| Live | temporary Owner sign-in | carejiox.com: client An Xu shows Studio, editor opens with the five cards (nothing changed); Contact 4002 shows Studio, Overview pack height 319 px and the tray 0 px as on the clone. hhh.carejiox.com (no clients or contacts there): new unsaved Client and Contact show Studio; editor opens; nothing saved (0 partners/leads created) | `L11`, `L11b`, `L12`, `L12b`, `L17`, `L17b` |

Console: no errors from this work. Pre-existing warning on the client and contact screens:
"The widget: date don't support the type datetime". On live, one 403 on the very first
navigation to `/web/login` in the test browser (the same URL answers 200 to `curl` and to
`fetch`); not related.

Live clean-up: temporary user `fs2.qa.live.20261103` (carejiox id 10113 / partner 37998;
hhh id 12 / partner 20) deleted after checking it created nothing and no audit table held a
row for it; fresh psql shows 0 users and 0 partners of that name on both.

## Deploy (§7)

1. Clone `carejiox` → `carejiox_fs2` (pg_dump/pg_restore + filestore copy), neutralised as
   above, `-u biz_form_studio,health_form_studio,health_theme` with the private tree, tests,
   QA, timing, `validate_all` → `{'checked': 2, 'broken': []}`.
2. Backups `/var/backups/fs2/{carejiox,carejiox_template,hhh}.dump` (19 / 13 / 14 MB,
   readable by `pg_restore -l`).
3. Staged from the commit with `git archive` (0 `._` files) to `/tmp/<module>` →
   `carejiox-deploy -d -m biz_form_studio,health_form_studio,health_theme` (exit 0, http 200,
   1 m 16 s), `-D carejiox_template -m …` (exit 0, 200), `-D hhh -m …` (exit 0, 200).
4. All three: `biz_form_studio 19.0.1.1.0`, `health_form_studio 19.0.1.1.0`,
   `health_theme 19.0.5.9.1` installed; Contact tray view active; `validate_all` →
   `{'checked': 0, 'broken': []}`, 0 layouts, 0 `x_fs_` fields, hosts Client/Contact/Incident.
   **Template jobs: 0 active** after the upgrade (nothing to switch off this time).
5. `/web/login` 200 on carejiox.com and hhh.carejiox.com (public and Host-header local); live
   bundle serves the new symbols.
6. Clone dropped with its filestore, private tree, `fs2-web` unit, staging files, tunnel.
   Only the three backups remain in `/var/backups/fs2/`.

## Deviations

- **D1 — QA as the Owner, not the Admin role.** A user holding exactly the Admin role's groups
  is refused on the Clients list (invoices) and on every contact, so the Admin role cannot
  reach either screen on today's master (§5.277). The Owner role holds the clinic-admin group
  plus sales access and opens both. Studio's own gate is unchanged (clinic admin + write
  access to the record type).
- **D2 — `crm.lead.mobile` is not locked:** the field does not exist in this version
  (test 28 found it). The Contact host locks 17 fields.
- **D3 — Studio dropdowns use a callable selection** (`ir_model_fields.py::_fs_options`)
  reading the option rows in the reader's language. Without it the Vietnamese option names
  never reached the form: `web_debranding` replaces `get_field_selection` and ignores the
  rows (§5.273). Option rows stay the source of truth; values are unchanged.
- **D4 — the handover's translation format for options** (`{'vi_VN': {en: vi}}`) is for
  xml-translated fields; option names are plain translated text, so it is `{'vi_VN': vi}`
  (and `False` to remove).
- **D5 — Settings tile gate:** `canManageAccess` AND `fs.studio.can_use()` (new, never
  raises) — an access manager who is not Studio's gate would otherwise see a tile that leads
  to a refusal. The tile icon is `ic('wandSparkles')` on theme tokens instead of an inline
  font icon and hex pair; the trailing chevron keeps the tiles' existing font-icon pattern.
- **D6 — card icon `clipboard-list`:** "layers" is not in the Workspace section-icon set
  (`backend_02_chatter_components.scss`), `clipboard-list` is.
- **D7 — fields in Workspace cards get `placeholder="—"`** (not binary/yes-no), so an empty
  value reads as a dash like the cards around it.
- **D8 — editor details:** zones (People, Contact history) drawn after the other tabs; the
  "New section" pill hidden inside the half-width pack cards (the title needs the room; the
  blue frame and "custom" chips mark them); other tabs dimmed (opacity .72); the Header card
  leaves out the picture field.
- **D9 — FS-H1's `test_get_studio_shape` changed:** it asserted `name` in the payload; the
  partner form's title row is not a card, so with the leaner payload `name` is correctly
  absent. It now asserts standard names == names in the cards.
- **D10 — test 24 renames the tab with SQL:** an ORM write of the base form re-checks the
  layout's view against it and refuses, which is not what an upgrade does.
- **D11 — test 25 uses `ir.model.fields`** (`fs_vis`): no product model has an `fs_` field.
- **D12 — tray details:** a discovered card with no field the reader may read folds without a
  chip; Studio fields unioned into a configured card are filtered to readable ones. The card's
  `data-fs-fields` attribute lists the technical names of all its Studio fields, including
  ones the reader may not see (names only; the field node and value are removed by the
  server).
- **D13 — "clear it → folds again" happens on the next load:** the tray's rule 4 keeps a card
  open for the rest of the page once it held a value (by design, unchanged).
- **D14 — QA 18 split:** the Doctor cannot open Clients or Contacts at all, so "staff field
  shows / admins field does not" was proven with the CRM persona (served arch and
  `fields_get` on the Client; the Contact UI) — see §5.277 for why not on the Client UI.
- **D15 — QA 20 "head nurse"** = Nurse role + head-nurse group (no Head-nurse role exists).
- **D16 — pixel compare via the same deep link** before and after (the default Contacts list
  filter hid that record).
- **D17 — tests 31/32 use a clinic admin who also has the "all leads" sales group** (the
  Owner's pair); test 31 also asserts a plain clinic admin gets no Studio on the Contact.
- **D18 — tests and QA personas created on the clone only;** live used one temporary Owner
  sign-in per database, removed.

## Verified plumbing — drift found

All anchors used held: `ops-header-right/t[@t-if='canEdit']`
(`ops_client_profile_form.xml:19-23`), `crm-form-header-right/t[@t-if='canEdit']`
(`crm_contact_form.xml:19-23`), the Field Requirements tile (`admin_settings.xml:48-55`), the
packs and tails (`ops_client_profile_form_views.xml:160-241`, `crm_center_views.xml:200-240`),
`people_panel` (:614 / :332), `contact_history` (:369), `ws_fold_tray.js` line map, plain-div
attributes surviving (`view_compiler.js:394-402`), `ws_workspace.scss:887-1125` (the empty
tray paints 0 px). New: `crm.lead` has no `mobile` field; `ir.model.fields.selection.name` is
`translate=True` (plain text); `web_debranding` overrides `get_field_selection` without
`super()` (§5.273); `_get_fields_cached` is a 'stable' cache (§5.274); `hasclass()` is
registered globally by `ir_ui_view.py:133`, so the writer can check `//…/div[hasclass(…)]`
with plain lxml.

## Findings for the owner (not fixed — outside this phase)

- **Access:** the Admin role cannot open Clients or Contacts; the CRM role cannot open a
  client; the Doctor is bounced from Clients (§5.277).
- **White-label:** the Settings landing's "General Settings" tile (shown to the platform
  administrator only) says "Odoo system-wide configuration"
  (`health_landing/static/src/xml/admin_settings.xml`) — not a sanctioned file here.
- **Reload in Studio:** reloading the browser while in the editor shows "Open a screen that
  supports Studio and press Studio." (the editor's screen is not in the address); going back
  to the record and pressing Studio again works.
- The Client layout is drawn wherever the default client form opens full-page (a booking's
  client link, contacts), as expected; the Studio button only shows on the Workspace header
  and the standard control panel, never in a dialog.

## New ledger entries (HANDOVER-CONVENTIONS §5)

§5.273 the debranding layer ignores translated option names; Studio dropdowns are callables ·
§5.274 translated labels live in the 'stable' cache · §5.275 `-u` with `--test-enable` runs only
the upgraded modules' suites; `-u health_theme` does not cascade · §5.276 no `--` in XML
comments (BEM class names) · §5.277 the Admin role cannot open the Client or Contact screens.

## What FS-H3 (Booking + list columns) needs from the engine

1. **Booking host:** `OpsBookingFormController` also hides the control panel
   (`ops_booking_form.scss:36`) — `t-call="biz_form_studio.StudioButton"` from its header the
   same way; read its arch for the pack page/tail and the open cards before declaring the host.
2. **List columns:** a list-view writer next to `_render_arch` (one extension per list view,
   `optional="hide"` columns, never PHI — `list_ok`), plus the list host data. Studio
   dropdowns are callables now (D3): check list grouping/filters on a callable selection
   (`group_expand`, search panel) before shipping.
3. **Editor address:** put `model`, `view_id`, `res_id` in the action's URL state so a reload
   reopens the same screen.
4. **Personas:** decide with the owner who should hold Studio on Booking given §5.277; the
   gate needs write access to the record type.
5. **Payload:** keep the leaner `fields`; a Booking schematic will add its own markers if it is
   a pack form.
6. **Test runs:** upgrade, then run all suites without `-u` (§5.275).

## Commits

- `e3e21596` — Form Studio (health19): FS-H2 Workspace cards for the Client and Contact screens
- (this report, the ledger entries and the evidence) — the commit after it.

## Evidence folder `docs/handovers/formstudio/fs_h2_shots/`

11a_clone_owner_client_studio_button_in_top_bar · 11b_clone_client_studio_button_beside_save_indicator_dirty ·
11c_clone_owner_incident_button_still_beside_cog · 12a_clone_editor_client_workspace_schematic_1440 ·
12b_clone_editor_client_pack_and_new_section_zone · 12c_clone_editor_after_refinements_pack_card_and_dimmed_tabs ·
13a_clone_new_dropdown_with_vietnamese_option_names · 13b_clone_section_care_preferences_no_position_control ·
13c_clone_lift_access_in_identity_card · 13d_clone_publish_sheet ·
14a_clone_client_care_preferences_card_before_recent_visits ·
15a_clone_client_tray_identity_and_care_preferences_folded · 15b_clone_lift_access_set_identity_stays_open_after_reload ·
15c_clone_lift_access_cleared_identity_folds_again · 16a_clone_vi_owner_card_title_label_and_options_in_vietnamese ·
16b_clone_vi_editor_options_with_vietnamese_names · 17a_clone_contact_overview_before_change ·
17b_clone_contact_overview_after_change_no_studio_card · 17c_clone_editor_contact_workspace_schematic ·
17d_clone_contact_tray_appears_for_empty_studio_card · 18a_clone_doctor_incident_no_studio_button ·
18b_clone_crm_staff_contact_no_studio_button_field_shown · 19a_clone_client_820px_studio_card_one_column ·
19b_clone_editor_820px_stacked_no_overlap · 20a_clone_owner_settings_landing_form_studio_tile ·
20b_clone_tile_opens_field_library · 20c_clone_head_nurse_settings_landing_no_form_studio_tile ·
L11_live_carejiox_client_studio_button · L11b_live_hhh_new_client_studio_button ·
L12_live_carejiox_editor_client_schematic · L12b_live_hhh_editor_client_schematic ·
L17_live_carejiox_contact_studio_button_overview_unchanged · L17b_live_hhh_new_contact_studio_button (all `.png`).
