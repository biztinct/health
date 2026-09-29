# WORKSPACE — WS-3 report: the contact screen on the Workspace kit (programme closed)

Implemented and self-reviewed by Opus, 2026-09-29, from `WORKSPACE_WS3_CONTACT.md`.
Status: **done — live on `carejiox`, `carejiox_template` and `hhh`.** Not pushed.

## In plain words

The CRM contact screen now looks and works like the booking and client screens. At the
top: the contact's initials, name, code and status, with phone, how they reached us, the
area and the first-contact time on one line. Under it, a journey — New, Following up,
Booked, Client — which greys out with its own label when a booking was cancelled or the
call was spam. Then one **Next step** banner that says what to do ("No outcome recorded
yet.", "Follow-up was due 57 days ago.", "Appointment scheduled.") with the button that
fits (Book, Log activity, Open client). The Overview tab packs the old loose fields into
three cards (Contact, How they reached us, Status). The panel on the right stays in view:
**At a glance** (days since first contact, status, follow-up, last booking, duplicates,
priority), **People** (who handles the contact, the linked client or "Not linked yet") and
**Needs attention**. Book, Log activity and Escalate sit top right; Mark as spam, Delete
and Archive are under **More**. The contact history stays at the bottom, full width.

The same pass tidied the shared kit (one background colour and one set of chips, rows and
icons on all three screens), relabelled the booking Pricing card's "Total Price 0 ₫" as
**Extra charges total**, and fixed the known wrong or missing Vietnamese.

## Standing rules (stated back)

- White-label: no "Odoo" in anything a user sees — test 07c (new JS/template strings, the
  contact view's text and attributes, the Vietnamese this phase touched, the X2 strings).
- Flat mono colours from `--vuf-*` tokens only; no gradients (test 09); CSS-mask SVG icons
  (the three inline header buttons get mask icons from CSS; no new font-awesome written).
- Notes/history at the bottom, full width: the contact history block sits under the page,
  across its full width. (The notes feed was tried and reverted — deviation D2.)
- No business-logic change: no model Python; the four actions call the same methods; every
  lifecycle button keeps its name/`invisible`/`groups` (test 03).
- Tests never with `carejiox-deploy -t` on live; rehearsed on `carejiox_ws3` (`biz_tenant`
  slug → `nowhere_ws3_1`, jobs off after every upgrade, private addons tree first on the
  path, `--db-filter=^carejiox_ws3$`, `systemd-run` on 8199). QA tab parked on
  `about:blank` before runs (one run waited on it first — §5.216 — and was released).

## Files

**health_crm** (19.0.1.11.0 → **19.0.1.12.1**)
- `views/crm_center_views.xml` — only record `view_crm_contact_form_crm_center`
- `static/src/xml/crm_contact_form.xml` — chrome: breadcrumb bar + save indicator only
- `static/src/js/crm_contact_form.js` — no header RPC on mount (methods kept)
- new `static/src/js/ws_contact_panels.js`, `static/src/xml/ws_contact_panels.xml`
- `static/src/scss/crm_contact_form.scss` — dead header rules out, contact section in (D5)
- `__manifest__.py`, `i18n/vi_VN.po`, new `tests/test_ws_contact_form.py`, `tests/__init__.py`

**health_theme** (19.0.5.4.0 → **19.0.5.5.0**)
- `static/src/js/ws_journey.js`, `static/src/xml/ws_journey.xml` — `terminal`, multi-alias doc
- `static/src/scss/ws_workspace.scss` — kit fixes (K) and shared pieces
- `static/src/scss/vu_icons.scss` — the nine icons registered
- `static/src/img/lucide/` — nine icons moved in (git rename)
- `__manifest__.py`, `i18n/vi_VN.po` (journey labels)

**health_fieldservice** (19.0.2.10.0 → **19.0.2.10.1**)
- `views/health_fieldservice_order_views.xml` — `total_price` `string="Extra charges total"` (X1)
- `static/src/scss/ops_client_profile_form.scss` — the rules that moved into the kit removed
- `static/src/img/ws/` — emptied (icons moved)
- `i18n/vi_VN.po`, `__manifest__.py`

**Catalogues only (X2):** `health_invoicing/i18n/vi_VN.po`, `advanced_pricing/i18n/vi_VN.po`,
`health_careplan/i18n/vi.po`, `health_family_link/i18n/vi.po`, `health_telehealth/i18n/vi.po`,
`health_base/i18n/vi_VN.po`.

**docs:** this report, `workspace_ws3_shots/` (37 screenshots, two journey captures, the
translation-fix script, `CONSOLE_AND_CHECKS.md`), ledger §5.255–§5.259, programme status.

Python proof (safety rail 5) — `git diff affc82af --stat -- '*.py'`: the three
`__manifest__.py`, `health_crm/tests/__init__.py`, and the new test file. Nothing else.

## Tests (`health_crm/tests/test_ws_contact_form.py`, post_install)

| # | What it asserts | Result |
|---|---|---|
| 01 (h1) | `//page[@name='more_details']` resolves once; combined arch has `web_attribution` right after More Details with its fields, and the Google Ads fields | PASS |
| 02 (h2) | own-arch field set ⊇ committed "before" list (46 names); every field exists on crm.lead | PASS |
| 03 (h3) | lifecycle four: same `invisible`/`groups`, no `confirm`, all `ws-more`; Book / Log activity / Escalate / Mark as spam are object buttons naming the controller's methods, Spam alone under More, `invisible="not id"`, no groups, not primary; no `action_mark_spam_and_home`; controller still has the methods | PASS |
| 04 (h4) | `ws-workspace`; one ws-page/ws-main/ws-rail/ws-hero/ws-next; journey attrs (state field, steps, terminal, aliases, date fields exist); glance + attention in the rail; one Next step widget; People with `user_id` and `patient_id`; `contact_timeline` once and outside `.ws-page`; no chatter; pages `overview` + the four old ones in order; no ribbons | PASS |
| 05 (h5) | chrome template has no `crm-profile-header`/`crm-ph-`/`headerState`/actions, keeps breadcrumb + save indicator; no header RPC on mount; nothing under `addons/*/static/src` t-inherits `CrmContactFormView` | PASS |
| 06 (h6) | every value of `contact_status` (enumerated from the field) is a step, an alias or a terminal | PASS |
| 07 (h7) | X1 label; X2 msgstrs in each owning catalogue with the occurrence the screen needs; every `_t`/template string of the new files has Vietnamese with its code occurrence; the arch terms have the view occurrence; journey labels in health_theme; web catalogue serves "Chưa ghi nhận kết quả.", "Mở hồ sơ khách hàng", "Đang theo dõi" | PASS |
| 07b (h7) | every worded term of the contact view reaches the **database** in Vietnamese ("Email" allowed — it is the Vietnamese word) | PASS |
| 07c (h7) | no "Odoo" in new strings, the view, touched Vietnamese, X2; matcher self-check | PASS |
| 08 (rail 4) | the journey keeps the literal "Cancelled" chip and the no-`terminal` path; the booking arch names no terminal | PASS |
| 09 (rail 5) | no `min()/max()/clamp()` outside a custom property and no gradient in the contact stylesheet and the kit; every icon the screen names has a mask rule and an SVG | PASS |
| h8 | health_web_leads W2/W3, WS-1 and WS-2 test files | PASS (in the suite runs below) |

Suite runs on the practice copy (verbatim result lines):

- Baseline, untouched copy: `odoo.tests.result: 0 failed, 0 error(s) of 253 tests when loading database 'carejiox_ws3'` (crm 4, fieldservice 41, google_ads 156, theme 16, web_leads 88).
- First run with the change: `odoo.tests.result: 1 failed, 0 error(s) of 264 tests …` — 07b flagged "Email" (already the Vietnamese word); allow-listed, no product change.
- Final: `odoo.tests.result: 0 failed, 0 error(s) of 264 tests when loading database 'carejiox_ws3'` — health_crm 17, health_fieldservice 41, health_google_ads 156, health_theme 16, health_web_leads 88; 264 `Starting Test…` lines, all 11 new methods among them.
- i18n gate + theme: `odoo.tests.result: 0 failed, 0 error(s) of 77 tests when loading database 'carejiox_ws3'` — G1, G1b, G1c, G2, G2b all logged `Starting`.
- After the revert (D2): `odoo.tests.result: 0 failed, 0 error(s) of 221 tests when loading database 'carejiox_ws3'` — health_crm 17, health_google_ads 156, health_web_leads 88 (the revert touched health_crm only).

## Live deploy (one sitting)

1. Backups: `/var/backups/ws3/carejiox-20260929-1725.dump`, `carejiox_template-…`, `hhh-…`.
2. The one changed catalogue of a module not being upgraded (`health_base/i18n/vi_VN.po`) was
   copied into the tree first (D6). Then `carejiox-deploy -d -m health_theme,health_fieldservice,health_crm,health_invoicing,advanced_pricing,health_careplan,health_family_link,health_telehealth -x ws3_master.py`
   → exit 0 (the controller template and the arch in the same copy and run); the script
   applied the corrected Vietnamese (§5.256) and created the QA account. Then
   `-D carejiox_template` and `-D hhh`, same modules, `-x ws3_i18n_fix.py` → exit 0 each.
3. Live QA found D2; fix `7fb8805f` shipped the same way (`-d -m health_crm`, then
   `-D carejiox_template`, `-D hhh`) → exit 0 each.
4. Versions on all three: health_theme 19.0.5.5.0, health_fieldservice 19.0.2.10.1,
   health_crm 19.0.1.12.1.
5. Scheduled jobs: master 96 → 96, hhh 77 → 77, template 0 → **7** after each upgrade →
   switched off on the template alone → **0**.
6. AppleDouble files in the tree: 0. Asset caches cleared on all three; restart via `-s`.
7. `/web/login`: carejiox.com 200, hhh.carejiox.com 200. No new ERROR/CRITICAL (the only
   "modules not loaded" line of the day belongs to another stream's clone, 05:49).
8. Bundle compiled (see `CONSOLE_AND_CHECKS.md`).
9. X2 on every database: the booking/client views' Vietnamese contains the new wording and
   no longer the English term (psql check on carejiox, hhh, carejiox_template).
10. Practice copy dropped with its filestore, private tree, units, tunnel and staging files.
    Temporary live account deleted (0 rows in `res_users` and `res_partner`).

## Browser QA

| # | Item | Where | Evidence | Result |
|---|---|---|---|---|
| 1 | QA Phone Check (2528) at 1440 vs the concept | clone + live | `00_…`, `01_clone_BEFORE_…`, `03a_…`, `11_live_AFTER_…` | PASS |
| 2 | One contact per status | clone: New `04a`, Lead with overdue follow-up `04b`, Appointment + linked client `04c` (Open client → client screen `04d`), Cancelled `04e`, Spam `04f`; live: New `11`, Appointment `14a` | PASS. No contact is "Existing client"/"Service used"/"Thinking"/"To be contacted again" on either database; those map by alias (test 06). |
| 3 | Book, Log activity, Escalate, Mark as spam on fixtures | clone | `05a–05e`; table in `CONSOLE_AND_CHECKS.md` | PASS — same result as the old call for each |
| 3 | More menu opened only | live | `12_…` | PASS (Mark as spam, Delete, Archive) |
| 4 | Tabs incl. Web Attribution; history at the bottom | clone + live | `06a_…`, `13_…` | PASS — all six tabs open, no error dialog |
| 5 | 1100 / 820 px | clone + live | `07a–07c`, `15a–15b` | PASS — no sideways scroll; rail under the page at 1100 |
| 5 | Vietnamese user | clone + live | `08a`, `16a` | PASS |
| 5 | Booking Pricing card "Extra charges total" / "Tổng phụ phí" | clone | `08c_…` | PASS |
| 5 | X2 strings before/after | clone (+ live client label, + psql on all DBs) | `02a`/`02b` → `08b`/`08c`/`08d`, `16b` | PASS |
| 6 | Three screens side by side | clone | `09a–09c` | PASS after two kit fixes (canvas, chip colour) and the contact bar height; remaining differences below |

Pixel pass (measured, `CONSOLE_AND_CHECKS.md`): fixed along the way — the code chip was
invisible on the canvas (§5.257); the three screens had three canvas greys; the contact's
breadcrumb bar sat 4 px short of the other two; the history card's gap to the page did not
match the feed's; the stopped (cancelled / spam) Next step cards were blue while the
booking's cancelled card is red; the Legacy Record card on the booking had an empty icon
square (WS-1 open item — the kit now has an `archive` title glyph).

## Deviations (each the smallest that keeps the contracts)

- **D1 — the shared "loader" makes no server call.** Everything the contact panels show is
  on the record, so the loader is a memoised facts builder keyed on the client loader's own
  key (`profileKey`, imported from `ws_client_panels.js` with `dayDiff`/`relativeDay`) — one
  build per record load, zero RPCs. A third mode, `avatar`, of `ws_contact_glance` draws the
  hero initials (the handover allowed the glance widget to render it).
- **D2 — no notes feed on the contact screen.** Checking the timeline showed it lists no
  notes and fails for everyone but a system administrator, so I added `<chatter/>` below
  it. On live it opened an error dialog for the CRM desk (followers read refused, §5.255).
  Reverted in `7fb8805f` and redeployed within the sitting; the handover's default (timeline
  only, no chatter) is what is live, and its hide rule is back.
- **D3 — the four contact buttons carry `invisible="not id"`** ("always" in the handover):
  the old header was drawn only for a saved contact; this keeps exactly that.
- **D4 — no header button is primary** (Book in the concept is blue): the Next step banner
  owns the one primary button on all three screens (WS-1 rule); Book is primary there
  when it is the next step.
- **D5 — `health_crm/static/src/scss/crm_contact_form.scss` edited** (not listed in §1):
  the dead header rules had to leave, and the contact needs a few rules of its own (Next
  step glyphs and tones, the history card, header-button mask icons, bar height 52 px).
- **D6 — `health_base/i18n/vi_VN.po` reached the live tree by a file copy, not `-m`**: an
  upgrade of health_base cascades through every module; the file is where the next
  upgrade and the translation script read it.
- **D7 — X2 went further than listed**, each a clear error on the three screens or their
  one line away: "Book" said "Cuốn sách" (a book) on the contact screen and CRM lists → "Đặt
  lịch"; the client list's "Gender" said "Làn giới" → "Giới tính"; "Mode of Contact" was
  English on the contact card (stale occurrence, §5.256) → "Phương thức liên hệ".
- **D8 — the kit took more than the four named fixes**, all moved out of the client
  stylesheet so the contact could share them: chip tones, People rows, state chips, links,
  "loading" rows, the widget-drawn Next step rules, the notes-feed card, an `info` alert, a
  history card, one canvas colour, and title glyphs for phone / user / message-square /
  archive.
- **D9 — Next step for a New contact that already has an outcome** (not in the rules): "Following
  up." / "No follow-up date set." / Book.
- **D10 — the controller's `saveButtonClicked` override was removed**: it only re-ran the
  header RPC. All other methods (Book, Log, Escalate, Spam, `_loadHeaderData`, labels) stay.
- **D11 — evidence path exceptions**: `02a`/`02b` and the journey captures were opened by the
  web client's own action call; the live Vietnamese check switched the temporary account's
  own language.

## Removed SCSS selectors

`health_crm/static/src/scss/crm_contact_form.scss` (each class grep-checked outside
stylesheets, anchored on the attribute boundary — §5.252): `.crm-profile-header`,
`.crm-ph-identity`, `.crm-ph-avatar`, `.crm-ph-details`, `.crm-ph-name-row`, `.crm-ph-code`,
`.crm-ph-name`, `.crm-ph-status-badge`, `.crm-ph-meta` (+ `span`, `i`), `.crm-ph-actions`,
`.crm-ph-action-btn` (+ `.primary`, `.secondary`, `.danger`), `.crm-more-toggle` (+ `.open`).
Kept: `.crm-hdr-status-*` (the kept `getStatusClass()` still builds that class name), the
page shell, breadcrumb bar and the chatter-hide rule.

`health_fieldservice/static/src/scss/ops_client_profile_form.scss` (moved to the kit, not
lost): the two icon lists and loops, the phone title glyph, `.ws-chip.o_field_widget` and the
chip tones, `.ws-next:not(:has(.vu-action-card))` / `.ws-next > .o_widget`, the Recent visits
head/title block, `.ws-state*`, `.ws-link`, `.ws-panel--people > .o_widget`, `.ws-person`,
`__body`, `__role`, `__name`, `__sub`, `__acts`, `.ws-icon-btn`, `.ws-row.is-loading`, the
Shortcuts icon override, and the whole "shared by the client AND the booking" block (tab
underline room, notes-feed card).

## Per-action before/after status (practice copy)

| Action | Old controller call | New header button | Same? |
|---|---|---|---|
| Mark as spam | lead, no outcome → spam, rejected; stays | lead, no outcome → spam, rejected; stays, notice | yes |
| Log activity | lead → lead, pending follow-up; activity dialog | same; dialog; form reloads after | yes |
| Escalate | no change; escalation wizard | no change; escalation wizard | yes |
| Book | no change; Quick Booking | no change; Quick Booking | yes |

## Vietnamese before/after (X2)

| String | Screen | Owner catalogue | Before | After |
|---|---|---|---|---|
| Pay Quote | booking header | health_invoicing | Thu nhập (income) | Thanh toán báo giá |
| ALLERGIES: | client strip | health_fieldservice | Tâm dị ứng: | DỊ ỨNG: |
| Gender | client Personal card | health_base | Gender (English) | Giới tính |
| Pricing (tab) | booking | advanced_pricing | Pricing | Giá |
| Visit Tasks (tab) | booking | health_careplan | Visit Tasks | Nhiệm vụ theo lần khám |
| Family Updates (tab) | booking | health_family_link | Family Updates | Cập nhật cho gia đình |
| Telehealth (tab) | booking | health_telehealth | Telehealth | Khám từ xa |
| Staff Overview | booking Shortcuts | health_fieldservice | Staff Overview | Tổng quan nhân viên |
| Extra charges total (X1) | booking Pricing card | health_fieldservice | "Giá tổng" (for Total Price) | Tổng phụ phí |
| Book | contact header, CRM lists | health_crm | Cuốn sách (a book) | Đặt lịch |
| Gender (column) | client list | health_fieldservice | Làn giới | Giới tính |
| Mode of Contact | contact card | health_crm | Mode of Contact | Phương thức liên hệ |

## Concept vs live (QA 1, `00_concept…` vs `11_live_AFTER…`)

| Concept | Live | Why |
|---|---|---|
| Status chip "Initial contact" | "New" | The field's own label, one source of truth (handover) |
| Journey New → Initial contact → Qualified → Booked → Client | New → Following up → Booked → Client | Handover's steps on `contact_status` |
| Buttons on the hero row, Book blue | Top-right row, neutral; Book blue in Next step | Kit statusbar; one primary per screen (D4) |
| "54 days since the first call…" + "Record call outcome" | "No outcome recorded yet." + Book / Log activity | Handover rule 1; no "record outcome" action exists beyond Log activity |
| Glance: Calls logged, Bookings, Outcome | Since first contact, Status, Follow-up, Last booking, Duplicates, Priority | Handover rows |
| People: Handled by + chat icon, Linked client "+" | Handled by, Linked client (link) / Not linked yet | Handover People; no chat action |
| Tabs Overview / All details / Activity | Overview + the five existing tabs | Non-goal: tabs kept |
| "Not filled yet" Referral / Notes | none | No Overview card can be fully empty, so no tray (handover) |
| "Activity & notes" feed with composer | "History" timeline (says "No history yet" for most people) | D2; §5.255 |
| Be Vietnam Pro | product font | as WS-1/WS-2 |

## New ledger entries

§5.255 (a chatter on crm.lead is refused for CRM staff; the history widget is refused for
non-admins), §5.256 (targeted translation overwrite recipe; stale occurrence after a
lookup conversion), §5.257 (three canvases, invisible neutral chip; side-by-side measure),
§5.258 (contacts list access error across areas), §5.259 (rail fly-out click sequence).

## Commits (branch 19.0, not pushed)

- `b538ae2f` feat(workspace): move the contact screen onto the Workspace kit, and share the kit's fixes across all three screens
- `7fb8805f` fix(workspace): the contact screen keeps its own history, without the notes feed
- docs commit (this report, evidence, ledger, programme) — see `git log`

## Evidence (`docs/handovers/workspace_ws3_shots/`)

`00_concept_option_b_contact.png`, `01_clone_BEFORE_contact_2528.png`,
`02a_clone_vi_BEFORE_booking_bk3831.png`, `02b_clone_vi_BEFORE_client_bui_t_gender_allergies.png`,
`03a_clone_contact_2528_top_1440.png`, `03b_clone_contact_2528_bottom_history_and_notes_feed_LATER_REVERTED.png`,
`04a_clone_new_1218.png`, `04b_clone_lead_followup_overdue_374.png`,
`04c_clone_appointment_linked_client_2527.png`, `04d_clone_open_client_lands_on_client_screen.png`,
`04e_clone_cancelled_262.png`, `04f_clone_spam_485.png`, `05a_clone_more_menu_open_248.png`,
`05b_clone_mark_as_spam_done_248.png`, `05c_clone_log_activity_dialog_234.png`,
`05d_clone_escalate_wizard_374.png`, `05e_clone_book_opens_quick_booking_374.png`,
`06a_clone_tab_web_attribution_2528.png`, `07a_clone_1100px_spam_485.png`,
`07b_clone_1100px_rail_below_feed_LATER_REVERTED.png`, `07c_clone_820px_top.png`,
`08a_clone_vi_contact_2528.png`, `08b_clone_vi_AFTER_booking_bk3831.png`,
`08c_clone_vi_AFTER_booking_pricing_card_extra_charges_total.png`,
`08d_clone_vi_AFTER_client_bui_t_gender_allergies.png`, `09a_clone_side_by_side_booking_bk3831.png`,
`09b_clone_side_by_side_client_bui_t.png`, `09c_clone_side_by_side_contact_2528.png`,
`11_live_AFTER_contact_2528_top_1440.png`, `12_live_more_menu_open_only.png`,
`13_live_contact_2528_bottom_history.png`, `14a_live_appointment_2527.png`,
`14b_live_contacts_list_search_access_error_preexisting.png`, `15a_live_1100px.png`,
`15b_live_820px.png`, `16a_live_vi_contact_2528.png`, `16b_live_vi_client_gender_label.png`,
`journey_booking_BEFORE.html`, `journey_booking_AFTER.html`, `ws3_i18n_fix.py`,
`CONSOLE_AND_CHECKS.md`.

## Programme closed

All three record screens — booking, client and contact — now run on one Workspace kit:
the same canvas colour, the same header row (quiet buttons, rare ones under More), the same
identity line (avatar or initials, name, code chip, status chip, one line of facts), the
same Next step banner (one sentence, one primary button, red when a booking is cancelled),
the same underline tabs, the same packed read-first cards, the same pinned right rail (At a
glance rows that go grey at zero, People rows, Needs attention alerts) and the same
full-width block at the bottom. Measured side by side they start at the same lines (header
162 px, identity 218 px). What still differs, by design or by data: the client has no
journey (it has no stage field); the booking and client show a notes feed at the bottom
while the contact shows its own history (a feed there is refused for CRM staff); the
contact's history says "No history yet" for everyone but a system administrator until its
one-line access fix is made; the booking's tab row is 1 px taller than the other two (43 vs
42 px, left); the Web Attribution and other older tabs keep their older card style.

## Not done / open (plainly)

- **Live per-status coverage was limited by data and access**: the live CRM persona sees one
  area; in TPHCM there is one New contact, two Appointment contacts and one Cancelled
  contact whose list row itself errors (§5.258). Overdue lead, cancelled and spam were shown
  on the practice copy only. No contact anywhere is "Existing client" or "Service used".
- **The contact history is empty for almost everyone** (pre-existing, §5.255): needs a
  one-line change in `crm.lead.get_contact_timeline` (read tracking values as the system).
  Your call whether to schedule it; it is a code change, not a screen change.
- **Contacts list error across areas** (pre-existing, §5.258) — list screen, out of scope.
- Still English or poor for a Vietnamese reader, pre-existing and not on the X2 list: the
  "I am the" choices ("Client"), "Reschedule" → "Lắp đặt lại lịch trình", "View Quote" →
  "Xem trích dẫn", "Clinical" tab → "Tiêm nghiệm lâm sàng", and the client LIST buttons
  "Book" → "Cuốn sách", "Log Activity" → "Hoạt động nhật ký" (health_fieldservice).
- The booking screen's live X2 look was proven on the practice copy and by database checks,
  not with a live screenshot: the CRM-desk persona has no Bookings entry.
- Nothing else in the definition of done is outstanding.
