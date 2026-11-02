# FORM STUDIO — FS-H3 report (the Booking screen, list columns, the editor that survives a reload)

Written 2026-11-03 by the Opus implementer. Handover: `FORM_STUDIO_FS-H3_BOOKING_LISTS.md`.

## In one paragraph (for the owner)

The **Studio** button is now in the top bar of every **Booking**, beside the save buttons, just
like on Clients and Contacts. Studio shows the booking the way it looks: the Overview cards side
by side (Visit, Location details, Care team, Pricing and Additional charges take new fields;
Notes and the cards other parts of the system add are shown but closed), then a place for a new
card, then the other tabs, greyed. A new card lands at the end of the Overview, after Notes, and
folds into "Not filled yet" while empty. New this time on every screen: a field can be switched
on as a **column of that screen's list** (Bookings, Clients, Contacts, Incidents). It then shows
right after the last column (after "Priority" on Bookings), dropdowns as coloured labels, money
with its currency, in Vietnamese for Vietnamese readers, and only to people allowed to see the
field. Everyone can hide such a column for themselves; the publish screen warns that publishing
a column resets people's saved column choices for that list. Long text, files and health
information can never be columns. **Reloading the browser inside Studio now brings the same
screen back**, unpublished changes included. The "Dashboard" link at the top of a Booking now
works (it did nothing before). It is **live on carejiox, the golden template and hhh**; nothing
was published and no field was created on the live systems. Who holds Studio on Bookings today:
the **Owner** and the **Operations Manager**. The Admin role sees the Bookings list but cannot
open a booking (an older access setting about invoices, not touched here).

## Standing rules (stated back)

- **White-label:** no "Odoo" in anything a user sees; both `vi.po` scanned (test 16), core
  sources and catalogue scanned (12a, re-run over the FS-H3 files by test 43); new strings
  checked by hand.
- **Generic core:** `biz_form_studio` names no product, no `health_`, no clinic/nurse/patient.
  "Bookings", "Nurse app" and every Booking fact live in `health_form_studio` data.
- **Plain copy;** `x_fs_` names never shown.
- **Design:** flat `--bzk-*` tokens, `ic()` icons (no new glyph needed: `table`, `minusCircle`
  were already in `kit_icons.js`), no gradient, no emoji, no `font-family` (12d).
- **Vietnamese** for every new string, generated from `odoo-bin i18n export` on the clone and
  filled in (biz_form_studio 331 entries, health_form_studio 57; none empty).
- **Chatter untouched; host models untouched** (no field, rule or business logic changed).
- **Shared-module edits:** only `health_fieldservice/static/src/js/ops_booking_form.js`
  (`navigateTo`, own commit) and the `health_fieldservice` version bump. The Client controller
  already had `navigateTo` and is untouched. `kit_icons.js` not touched. Nothing else outside
  the two Studio modules.
- **Rehearsed on a clone** `carejiox_fs3` (tenant slug → `nowhere_fs3_1`, 107 jobs off, mail
  servers and fetchmail off, new `database.uuid`, private tree `/odoo/fs3/addons` first on the
  path, `--db-filter=^carejiox_fs3$`, `systemd-run` on 8199/8197). Never `-t` on the live box.
  `fs.studio.validate_all` after every upgrade on every database. Suites run without `-u` after
  upgrading (§5.275).
- **Live:** Studio opened only; nothing published, no field created (0 layouts, 0 drafts,
  0 `x_fs_` fields on all three afterwards).
- **Commits** on 19.0, plain sentences, not pushed.

## Files

`addons/biz_form_studio/` (→ 19.0.1.2.0)
- `models/fs_common.py` — `card_title()` (title text in any tag, icon and pencil skipped),
  `has_class()`, `NO_LIST_TYPES`.
- `models/fs_host.py` — `list_view_xmlid`, `list_anchor`, `list_name` (translatable),
  constraint `_check_list_pair`, `_list_view()`, `_list_title()`, `_section_problems()`
  (open card without a field group), `_list_problems()`, `_check_sections()`, `_check_list()`.
- `models/fs_field_meta.py` — `list_ok` default off; forced off for health information, files,
  long text; `_list_reason()`.
- `models/fs_layout.py` — `list_view_id`, history `list_arch`, `_column_names`,
  `_render_list_arch`, `_write_list_view`, `_empty_list_view`; `_publish` draws the list before
  writing anything; `_validate_one` re-draws the list ("The list changed: …"); `_switch_off`
  turns both views off; writer refuses a card without a group.
- `models/fs_studio.py` — reader uses `card_title`, a card is open only with a group, hidden
  tabs skipped; `get_studio` returns `host.list_title`, per field `list_ok`/`list_reason`, per
  type `list_reason`; `create_field` / `update_field` column rules; switching a placed field's
  column republishes (lists only); `validate_all` returns `hosts` problems.
- `static/src/js/studio/studio_editor.js`, `xml/studio/studio_editor.xml`,
  `scss/studio.scss` — address state, column switch, publish-sheet column lines and warning,
  "Move to section…" uses the screen's card titles.
- `static/tests/tours/studio_reload.js` (+ `web.assets_tests`), `i18n/vi.po`,
  `tests/test_fs_core.py` (33–44).

`addons/health_form_studio/` (→ 19.0.1.2.0)
- `data/fs_hosts.xml` — Booking host; list, anchor and list name on all four hosts.
- `models/fs_host.py` — 10 new lock reasons in `HOST_TEXT`.
- `static/src/xml/ws_header_client.xml`, `ws_header_contact.xml`, `ws_header_booking.xml` —
  one file per top bar (replaces `ws_headers.xml`, see D8).
- `static/src/xml/admin_settings.xml` — tile text names Booking too.
- `i18n/vi.po`, `tests/test_fs_health.py` (45–48).

`addons/health_fieldservice/` (→ 19.0.2.12.4) — `static/src/js/ops_booking_form.js`
`navigateTo` (side fix, own commit).

## Tests (§5)

Full run on the clone after upgrading, no `-u` (§5.275): **388 tests** — biz_access 312,
biz_form_studio 64, biz_kit 18, health_base i18n 9, health_crm 17, health_fieldservice 42,
health_form_studio 30, health_incident 22, health_theme 16 (per-module counts include
sub-tests). After the fixes below, the final runs: Studio suites + incident + theme + i18n
**0 failed, 0 error(s) of 101 tests**; health_crm + health_fieldservice + health_form_studio
**3 failed of 65**, all three pre-existing (below). biz_access and biz_kit had no failure.

| # | Test | Result | What it proves |
|---|---|---|---|
| 33 | `test_33_titles_are_read_whatever_their_tags` | PASS | `card_title` reads a `<span>` title, a `<div>` title and a mixed one ("Care team"); the pencil beside the title is ignored; through `get_studio` a span-titled card reads "Visit" |
| 34 | `test_34_an_open_card_without_a_field_group_is_refused` | PASS | `_check_sections` raises naming `note_card`; `validate_all` lists it under `hosts`; the schematic shows it closed; publishing into it → "cannot take fields"; the card with a group takes the field |
| 35 | `test_35_the_list_writer` | PASS | one xpath `//field[@name='email']` `after`; columns in section then field order; `optional="show"`; dropdown `widget="badge"`, text no widget; a switched-off field is no column; combined list `name, email, code, slot, phone` |
| 36 | `test_36_what_is_never_a_column` | PASS | health information, file, long text: switch forced off whatever is asked (also via `update_field`), a direct write refused; reasons "Health information is never a column." / "Files cannot be list columns." / "Long text cannot be a list column."; an unplaced switched-on field is no column; taking a field off the screen removes its column |
| 37 | `test_37_who_may_see_a_column` | PASS | an Admins-only column is absent from the list a plain user receives (`get_views`) and present for an administrator |
| 38 | `test_38_no_column_keeps_an_empty_switched_off_view` | PASS | no column → list view `<data/>`, inactive; switching the column on republishes (version +1), same view id, active; off again → inactive |
| 39 | `test_39_history_and_going_back_keep_the_list` | PASS | history keeps `list_arch` per version; going back to 1 → v3 with v1's form AND list arch; numbering 1, 2, 3 |
| 40 | `test_40_a_list_that_moved_switches_the_whole_layout_off` | PASS | anchor renamed by SQL → layout broken, reason contains "list", form and list views both off; the list still draws `name, website, phone`; the host problem names `email` |
| 41 | `test_41_the_host_declares_a_real_list` | PASS | list without anchor / anchor without list → ValidationError; a form given as the list → "not a list"; an anchor not in the list → refused naming it |
| 42 | `test_42_the_editor_learns_the_list` | PASS | `list_title` = list's own title, then the host's `list_name`, then '' with no list; per-field `list_ok` / `list_reason`; per-type `list_reason` |
| 43 | `test_43_the_gates_cover_the_fs_h3_files` | PASS | 12a–12f run over every FS-H3 file; the editor calls `updateActionState(screen)` and reads `params.fs_model/fs_view/fs_res`; the list writer anchors by name |
| 44 | `test_44_a_reload_opens_the_same_screen` (HttpCase) | PASS then SKIP | ran: the router's reserved keys contain `model` and none of `fs_*`; the reload address answers 200; `get_studio` over HTTP returns the screen. Then `start_tour` skipped: "websocket-client module is not installed" (no Chrome either, §5.284). The browser round trip is QA 28 |
| 45 | `test_45_the_booking_host_resolves_against_todays_form` | PASS | kit ws, money ok, no tail, ONE pack, the five cards each with a group, Notes has none and is not declared, every locked field exists, Counters zone exists, every reason in `HOST_TEXT` (VI checked), the schematic reads span titles and opens exactly the five; all FOUR lists resolve (view, type, anchor once); `validate_all` reports no host problem |
| 46 | `test_46_end_to_end_on_the_booking` | PASS | Owner persona: long text (Staff, column refused), dropdown (Staff, VI options, column), money (Admins, column); text into Care team, card "Visit preferences" last in the pack after Notes; foreign cards still in the pack; list: dropdown then money right after Priority, dropdown as badge, money no widget, no text column; a nurse (Staff) gets the dropdown column not the money one, the Owner both; an outsider cannot read bookings at all; Vietnamese option in the list's field description; v2 drops the money column; going back restores v1's form and list arch |
| 47 | `test_47_a_column_on_each_of_the_other_lists` | PASS | Client, Contact, Incident: the column sits right after `total_assignments` / `user_id` / `open_action_count`; each list draws through `get_views`; the default partner list (the Clients list) carries the Client column |
| 48 | `test_48_probe_and_schematic_over_http` (HttpCase) | PASS | over JSON-RPC as the Owner: probe true on the Booking form, false on the old booking form; `get_studio`: kit ws, title "Booking", `list_title` "Bookings", money ok, one pack `overview`, the five open cards, zone `button_box` |

**Pre-existing failures (not caused by this phase):**
- `health_fieldservice…test_ws_client_form.TestWsClientForm.test_05_workspace_skeleton` — same
  as in the FS-H2 report (the rail now starts with `ws_rail_fold`).
- `health_crm…test_ws_contact_form.TestWsContactForm.test_05_chrome_template_lost_the_profile_header`
  and `health_fieldservice…test_ws_client_form.TestWsClientForm.test_07_chrome_template_lost_the_old_header_and_nothing_hangs_on_it`
  — both forbid any extension of the Contact / Client top-bar templates. FS-H2's Studio button
  extends both and is on the live tree since 2026-11-03 (checked: the live
  `health_form_studio/static/src/xml/ws_headers.xml` trips both). FS-H2's rehearsal could not
  see it (its clone tree held neither module, §5.282). This phase split the button into one file
  per bar, so the useful half of `test_07` (every extension hangs on a class that exists) now
  passes; the two "nobody extends it" assertions need a sanctioned test edit in
  `health_crm` / `health_fieldservice`.

Fixed during this phase (found by the suites): test 46's first "outside Staff" persona could not
read bookings at all (`get_views` checks model access, §5.283) — the check now compares a nurse
(Staff) with the Owner and an Admins-only column.

## Browser QA (§6) — evidence in `fs_h3_shots/`

Personas on the clone (each holding exactly one role's permissions): **Owner** `fs3.qa.owner`,
**VI Owner** `fs3.qa.owner.vi`, **Admin**, **CRM**, **Nurse**, **Doctor**, **Operations
Manager**, **Branch Manager**, **Accountant**. 1440 px unless stated. Path: sign-in by `fetch`,
then the left menu (Operations › Bookings › list › booking).

| Step | Persona | Result | Evidence |
|---|---|---|---|
| 21 | Owner / Ops Manager | Booking BK3852: **Studio** in the top bar, left of the save indicator (same order as Client); the Operations Manager has it too; Contact (4002) and Client (An Xu) unchanged | `21a`, `21b`, `21c` |
| 22 | Owner | Header card (read-only); Overview pack: Visit, Location Details, Care team, Pricing, Additional charges "Open card"; Legacy Record and Payment Summary "Standard" (closed); Notes "Standard" (closed); other tabs dimmed (the hidden Communication tab no longer listed, D9); Counters "Locked — Drawn by the system." | `22a`, `22b`, `22c` |
| 23 | Owner | Long text "Parking instructions" (Staff) dragged into Care team: column switch disabled, "Long text cannot be a list column."; Dropdown "Preferred nurse gender" with Female/Nữ, Male/Nam, No preference/Không yêu cầu, column on; Money "Key safe deposit", column on; section "Visit preferences" / "Mong muốn khi thăm". Publish sheet: 4 changes, "Column added: Preferred nurse gender (Bookings list)", "Column added: Key safe deposit (Bookings list)" and the reset warning; a later draft shows "Column removed: …" (lines all 35 px high) | `23a`–`23d` |
| 24 | Owner | Overview: "Visit preferences" last, after Notes; border, radius, padding, title size/weight/case/colour identical to Care team (computed styles); Care team holds Parking instructions; the empty new card folds into "Not filled yet" (chip "Visit preferences 2 fields"). After entering Female and 200,000 ₫ and saving, the card stays open | `24a` |
| 25 | Owner / VI Owner | Bookings list (second view of the Bookings screen): PREFERRED NURSE GENDER and KEY SAFE DEPOSIT right after PRIORITY; dropdown as a badge "Female", money "200,000 ₫"; the column chooser lists both; hiding Key safe deposit survives a reload; Group by "Preferred nurse gender" → "Female (1)". VI Owner: headers "GIỚI TÍNH ĐIỀU DƯỠNG MONG MUỐN", "TIỀN ĐẶT CỌC HỘP CHÌA KHÓA", badge "Nữ", group header "Nữ (1)", chooser in Vietnamese; the editor's switch reads "Hiện thành cột trong danh sách Lịch hẹn" | `25a`–`25f` |
| 26 | Owner / VI Owner | Client An Xu: Text "Gate code" (Staff, column on) into Identity, published; Clients list shows GATE CODE after the (hidden by default) Bookings column, i.e. after Last Visit on screen; VI header "MÃ CỔNG" | `26a`, `26b` |
| 27 | Nurse / Admin / Owner | The CRM role has no Bookings entry, so the Staff check used the Nurse: Bookings list shows the Staff dropdown and the Everyone money column, NOT the Admins-only "Internal booking code" (the Owner sees all three). Nurse: no Studio button on a client record. Admin role: sees the Bookings list, refused on opening a booking ("Journal Entry (account.move)") | `27a`, `27b`, `27c` |
| 28 | Owner | Reload inside the editor (with an unpublished draft): the same Booking screen comes back with the "changes that are not published" sheet; "Continue your draft" restores the section and both fields. Address: `…/action-biz_form_studio.studio?fs_model=health.fieldservice.order&fs_view=5015&fs_res=9688`. Browser Back from the editor returns to BK3852 | `28a` |
| 29 | Owner | Booking header "Dashboard" → Operations Command Center, no error; Client header "Dashboard" also works (unchanged) | `29a` |
| 30 | Owner, 820 px | Bookings list scrolls inside itself (list 1,455 px in a 684 px box), the page does not (820 = 820); Overview cards one column at the same x and width, Studio card included; editor stacked (palette, screen, settings), no overflow | `30a`, `30b`, `30c` |
| Live | temporary Owner sign-in | carejiox.com: booking BK3852 shows Studio, the editor opens with the same cards, address carries the screen; closed without changes. hhh.carejiox.com (no bookings): new unsaved booking shows Studio, editor opens (Payment Summary only — the legacy card's module is not installed there); nothing saved (0 bookings afterwards). No console message on live | `L21`, `L21b`, `L22`, `L22b` |

Timing on the clone (2 workers, over HTTP as the Owner, Booking): create a field 0.32 s, first
read of its label 0.08 s (then 0.02 s), open Studio 0.12 s, publish 0.24 s, first form + list
load after publish 0.14 s, delete a field (typed DELETE) 1.56 s.

Console: no errors from this work. Pre-existing warning on bookings: "The widget: date don't
support the type datetime". Live: one 403 on the very first navigation to `hhh…/web/login` in
the test browser (also seen in FS-H2; the sign-in by `fetch` works).

Live clean-up: temporary user `fs3.qa.live.20261103` (carejiox id 10114 / partner 37999; hhh
id 13 / partner 21). Before deleting, every table with a `create_uid` was counted for it: only
sign-in traces (1 login log, 12 live-update rows, the welcome chat: 1 channel, 2 members,
1 message). Those and the user and partner were deleted; fresh queries show 0 of each.

## Deploy (§7)

1. Clone `carejiox` → `carejiox_fs3`, neutralised as above, `-u biz_form_studio,
   health_form_studio,health_fieldservice` with the private tree (exit 0, 1 m 27 s),
   `validate_all` → `{'checked': 0, 'broken': [], 'hosts': []}`, all four hosts resolve.
   `health_roster` checked: **uninstalled on carejiox, carejiox_template and hhh** (no stop).
2. Backups `/var/backups/fs3/{carejiox,carejiox_template,hhh}.dump` (19.3 / 13.2 / 14.4 MB,
   readable by `pg_restore -l`).
3. Before deploying, the server's `health_fieldservice`, `biz_form_studio`,
   `health_form_studio`, `biz_kit` were compared file by file with the repo: identical except
   three `.DS_Store` files in the server's `health_fieldservice` (gone after the copy).
   Staged from the commit with `git archive` (0 `._` files) → `carejiox-deploy -d -m
   biz_form_studio,health_form_studio,health_fieldservice` (odoo-bin exit 0, http 200,
   2 m 9 s), `-D carejiox_template -m …` (exit 0, 200), `-D hhh -m …` (exit 0, 200).
4. All three: `biz_form_studio 19.0.1.2.0`, `health_form_studio 19.0.1.2.0`,
   `health_fieldservice 19.0.2.12.4` installed; `validate_all` → `{'checked': 0, 'broken': [],
   'hosts': []}`; 0 layouts, 0 drafts, 0 `x_fs_` fields; hosts Contact/Booking/Incident/Client
   with list names Contacts/Bookings/Incidents/Clients, no problems.
   **Template jobs: 7 came back on** (all seven are the phone module's, §5.178) →
   `UPDATE ir_cron SET active=false` → 0.
5. `/web/login` 200 on carejiox.com and hhh.carejiox.com; the live bundle serves the new code
   (the Booking top bar shows Studio and the editor writes `fs_model` into the address).
6. Clone dropped with its filestore, private tree, `fs3-web` unit, logs, staging files and the
   tunnel. Only the three backups remain in `/var/backups/fs3/`.

## Deviations

- **D1 — `fs.host.list_name`** (translatable) added beside `list_view_xmlid` / `list_anchor`:
  two of the lists have no title of their own and "the Booking list list" reads badly. Order:
  host's word, else the list's own title, else the screen's name. Overlay: Bookings / Clients /
  Contacts / Incidents (VI Lịch hẹn / Khách hàng / Liên hệ / Sự cố).
- **D2 — the column switch now starts OFF for a new field.** In FS-H1 it meant "may be offered";
  now it means "is a column for everyone", and every column added resets people's saved column
  choices. Existing switches keep their stored value (live has no Studio fields).
- **D3 — a money column brings the currency field with it, hidden** (`column_invisible`):
  without it the list shows no currency (§5.280). Written always (deterministic arch); a list
  that already reads the currency reads it twice, harmlessly. No widget is added (test 35/46).
- **D4 — going back re-draws the old version's placement with today's column switches**
  (deleted fields left out, as FS-H1 D18), rather than pasting the stored list arch. With the
  switches unchanged the result equals the stored arch (tests 39, 46); it never shows a column
  whose switch is now off or whose field is gone.
- **D5 — switching a placed field's column (on or off) republishes at once**, mirroring FS-H1's
  "Required" (it republishes the form; this republishes form and list). Only layouts whose
  screen has a list; the version number goes up; a chatter line says "is now / is no longer a
  list column". A field not yet on the screen only stores the switch.
- **D6 — test 44's browser half is skipped on this server** (§5.284); the server half runs
  first and passed; QA 28 is the proof of the reload.
- **D7 — test 46 personas** (see Tests): the Staff check is a nurse against the Owner with an
  Admins-only money column; the dropdown is Staff; an outsider is refused bookings outright.
- **D8 — the Studio buttons for the three top bars are one file per bar**
  (`ws_header_client.xml`, `ws_header_contact.xml`, `ws_header_booking.xml`, replacing FS-H2's
  `ws_headers.xml`), so each screen's own guard test checks each file against its own bar.
- **D9 — tabs that are always hidden** (`invisible="1"`, Booking's "Communication") are no
  longer drawn in the schematic.
- **D10 — "Move to section…" names open cards by the title the screen shows** (Vietnamese for a
  Vietnamese reader) and lists only cards the schematic found open.
- **D11 — the reset warning shows when any column is added OR removed** (a removal resets saved
  choices too — proven: a column hidden by the Owner came back after the next publish).
- **D12 — Notes is shown as a closed "Standard" card with no extra reason line**; the editor has
  no per-card reason line for closed cards (FS-H1 shape). The two cards other modules add are
  closed too (Legacy Record exists only on carejiox).
- **D13 — `validate_all` returns a new key `hosts`** (problems per host, logged as warnings,
  never raised). Callers that read only `checked` / `broken` are unaffected.
- **D14 — the Settings tile reads "Add fields to the Booking, Client, Contact and Incident
  screens"** (one new string, translated).
- **D15 — `health_fieldservice` upgraded with `-m` on all three databases** as the handover says
  (its code was identical to the repo first); the deploy also removed three stray `.DS_Store`
  files from the live tree.

## Verified plumbing — drift found

All §2 facts held at the cited lines (ORDER_VIEWS :995-1002, :1060-1458; the pack, the seven
named cards, Notes without a group, the tray map; `ops_booking_form.xml:15` and `:22-25`;
`ops_booking_form.scss:36-38`; lists `ops_booking_list_views.xml:5-28`,
`ops_client_list_views.xml:5-27`, `crm_center_views.xml:5-32`, `health_incident_views.xml:152-171`).
Additions:
- Fact 9: the Booking controller had no `navigateTo`; the Client controller has it
  (`ops_client_profile_form.js:92-99`, route `health_fieldservice.action_ops_command_center`,
  the same one the Operations menu uses). Fixed on Booking only.
- Fact 14: the action manager wraps the prop as `(newState) => updateActionState(controller,
  newState)` (`action_service.js:1042-1044`) and pushes the URL only once mounted (:619-626);
  setting the state before mount is enough (§5.278).
- `get_views` checks read access on the model (`ir_ui_view.py:3153`) — §5.283.
- A money column needs its currency field in the list (§5.280).
- `legacy_audit_card` exists only where `health_migration` is installed (carejiox only).
- `health_roster` is uninstalled on all three databases (fact 9's broken template patch is
  dormant; reported, not touched).
- The two top-bar guard tests (§5.282).

## Which roles can open Bookings (who holds Studio there)

Measured on the clone with one user per role (exact role permissions), through the menu and
the record:

| Role | Bookings in the menu | Opens a booking | Studio on Bookings |
|---|---|---|---|
| Owner | yes | yes | **yes** |
| Operations Manager | yes | yes | **yes** |
| Admin | yes | **refused** (invoice access, §5.277 family) | in theory, not in practice |
| Nurse | yes | yes | no |
| Doctor | yes | read only | no |
| CRM | no | (has the access, no menu entry) | no |
| Accountant | no | — | no |
| Branch Manager | no | no | no |

## Known limits (honest)

- Studio dropdown values are not checked against their options when written by code (callable
  selections skip that check, fact 15); Studio's own screens only offer listed options. A check
  on write is FS-H5 work.
- The "no value" group of a Studio dropdown shows as "(15)" with no "None" label in Group by.
- A field above another being taken off the screen shows the other as "Move …" in the publish
  sheet (FS-H1 compares positions).
- Columns use the field's label; there is no separate column title.

## New ledger entries (HANDOVER-CONVENTIONS §5)

§5.278 a client action keeps its screen in the address only under its own keys and only once
mounted · §5.279 Workspace card titles are written differently per screen; a card without a
group can never be open · §5.280 a money column needs its currency field · §5.281 the i18n export
reads every copy of a module on the path · §5.282 two guard tests red since FS-H2; private trees
decide what repo-walking tests read · §5.283 who can open a booking; `get_views` checks model
access · §5.284 browser tours never run on this box.

## What FS-H4 (health information reach) needs from the engine

1. **Exports:** `web/controllers/export.py:360-398` drops fields whose description says
   `exportable=False`. The engine already builds every Studio field in one place
   (`biz_form_studio/models/ir_model_fields.py::_instanciate_attrs`); setting
   `attrs['exportable'] = False` there for fields marked health information (read `fs_field_meta.phi`
   by plain SQL, like `fs_vis`, because it runs during the registry build) takes them out of the
   export dialog for everybody. Saved export lists that already name the field are a blocker
   today (`field_references`); they would also need a sweep when a field is switched to health
   information.
2. **Lists:** already done — health information is never a column (test 36), and switching a
   placed field to health information removes its column at once (D5).
3. **Nurse app:** the app's sync builds fixed dictionaries —
   `health_pwa/controllers/sync.py::_patient_record` (:329) for clients and `::_fso_record`
   (:395) for bookings — so no Studio field reaches the app today. A "show in the nurse app"
   switch (`fs.field.meta.pwa`) would hook there, read-only, and must skip health information.
4. **BI:** the BI dataset field scan must skip `x_fs_` fields marked health information (the
   flag lives on `fs.field.meta.phi`; `fs.studio.library()` already lists them per screen).
5. **Encryption on Client:** a health-information Studio field on `res.partner` would need the
   `health_phi_encryption` token/blind-index path at creation time; the engine's
   `create_field` is the single door (one hook after the field row is created).
6. **Access gaps to decide first:** the Admin role cannot open bookings or clients (§5.277,
   §5.283) and two guard tests need a sanctioned edit (§5.282).

## Commits

- `24a962f8` — Form Studio (health19): FS-H3 Booking screen, list columns and an editor that
  survives a reload
- `6d186211` — Booking and Client screens: make the Dashboard breadcrumb link work
- (this report, the ledger entries and the evidence) — the commit after it.

## Evidence folder `docs/handovers/formstudio/fs_h3_shots/`

21a_clone_owner_booking_studio_button_in_top_bar · 21b_clone_operations_manager_booking_studio_button ·
21c_clone_contact_studio_button_unchanged · 22a_clone_editor_booking_schematic_1440 ·
22b_clone_editor_booking_pack_foreign_cards_closed_notes_closed ·
22c_clone_editor_booking_other_tabs_dimmed_counters_locked · 23a_clone_long_text_column_switch_disabled ·
23b_clone_dropdown_column_switch_on · 23c_clone_publish_sheet_columns_and_reset_warning ·
23d_clone_publish_sheet_column_removed_line · 24a_clone_booking_overview_care_team_field_and_tray ·
25a_clone_bookings_list_before · 25b_clone_bookings_list_two_columns_after_priority ·
25c_clone_column_chooser_lists_both · 25d_clone_group_by_dropdown_en ·
25e_clone_vi_owner_list_columns_badge_group_in_vietnamese · 25f_clone_vi_owner_editor_column_switch_in_vietnamese ·
26a_clone_clients_list_gate_code_after_bookings_column · 26b_clone_vi_owner_clients_list_header_in_vietnamese ·
27a_clone_nurse_bookings_list_staff_column_no_admin_column · 27b_clone_nurse_client_record_no_studio_button ·
27c_clone_admin_role_refused_on_a_booking_invoices · 28a_clone_reload_in_editor_same_screen_draft_kept ·
29a_clone_booking_dashboard_breadcrumb_opens_command_center · 30a_clone_820px_bookings_list_scrolls_inside ·
30b_clone_820px_booking_overview_studio_card_one_column · 30c_clone_820px_editor_stacked ·
L21_live_carejiox_booking_studio_button · L21b_live_hhh_new_booking_studio_button ·
L22_live_carejiox_editor_booking_schematic · L22b_live_hhh_editor_booking_schematic (all `.png`).
