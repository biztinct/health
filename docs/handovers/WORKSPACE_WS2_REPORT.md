# WORKSPACE — WS-2 report: the client screen on the Workspace kit

Implemented and self-reviewed by Opus, 2026-09-29, from `WORKSPACE_WS2_CLIENT.md`.
Status: **done — live on `carejiox`, `carejiox_template` and `hhh`.** Not pushed.

## In plain words

The client screen now opens like the booking screen: the client's name, code, status and
how to reach them on one line; allergies (when there are any) as a red strip right under
it; one blue **Next step** banner that says what is wrong ("1,050,000 ₫ is unpaid.") with
the one button to act on it; the tabs as a simple underline row; the Overview as tightly
packed cards (Personal, Contact, Care, and Identity / Commission folded away while empty)
plus a **Recent visits** card; and a panel on the right that stays in view with **At a
glance**, **People** (the client with Call / SMS / Email, and the main contact you can
change), **Needs attention** and **Shortcuts**. Delete / Archive sit under **More**. The
big identity header, the six count tiles and the old side menu are gone. The notes and
history feed is back at the bottom of the client AND booking screens. Nothing a user may do
changed; the CRM contact screen is untouched (that is WS-3).

## Standing rules (stated back)

- White-label: no "Odoo" in anything a user sees — test 9c (new JS/template strings, the
  client view's text and attributes, and the Vietnamese of every entry this phase touched).
- Flat mono colours from `--vuf-*` tokens; no gradients in the client workspace section
  (test 10); CSS-mask SVG icons only (every icon a panel names has a mask rule — test 10);
  no new font-awesome in markup I wrote (the three kept banners keep their existing `<i>`,
  hidden by CSS, so their translations stay intact — see D6).
- Chatter at the bottom, full width: `<chatter/>` is the form's last child (test 5), and
  both screens' hide rules are gone (test 8).
- No business-logic change: Python limited to `get_client_profile_data` (read-only additions)
  and tests; every header button keeps name / `invisible` / `groups` (test 4).
- Tests never with `carejiox-deploy -t` on live; rehearsed on `carejiox_ws2` (`biz_tenant`
  slug → `nowhere_ws2_<id>`, jobs off after every upgrade), private `--addons-path`
  `/odoo/ws2/addons` first, `--db-filter=^carejiox_ws2$`, `systemd-run` on 8199. Browser
  tab set to `about:blank` before each run (§5.216); clone unit restarted after each push.

## Files

**health_fieldservice** (19.0.2.9.0 → **19.0.2.10.0**)
- `views/ops_client_profile_form_views.xml` — only record `view_health_patient_form_ops`
- new `static/src/js/ws_client_panels.js`, `static/src/xml/ws_client_panels.xml`
  (loader + `ws_client_next`, `ws_client_glance` glance/contact/attention,
  `ws_client_visits`, `ws_client_shortcuts` + registry `ws_client_shortcuts`)
- `static/src/xml/ops_client_profile_form.xml` — chrome: breadcrumb bar + save indicator only
- `static/src/js/ops_client_profile_form.js` — no fetch on mount; `_loadProfileData` and the
  save hook go through the shared loader (methods kept)
- `models/res_partner.py` — `get_client_profile_data` only: `next_visit`, `last_visit`,
  `recent_visits`
- `static/src/scss/ops_client_profile_form.scss` — dead rules removed, WS-2 section added
- `static/src/scss/ops_client_profile.scss` — reduced to the shared breadcrumb rules
- `static/src/scss/ops_booking_form.scss` — the chatter-hide block only (lines 6-14)
- new `static/src/img/ws/*.svg` (9 icons — D2)
- `i18n/vi_VN.po`, `__manifest__.py`, new `tests/test_ws_client_form.py`, `tests/__init__.py`

**health_crm** (19.0.1.10.1 → **19.0.1.11.0**)
- `views/ops_client_inherit.xml` — view 5428 now puts the Main contact picker + phone into
  `div[@name='people_panel']`
- deleted `static/src/js/ops_client_profile_header.js`, `static/src/xml/ops_client_profile_header.xml`
  and their two manifest lines; `i18n/vi_VN.po`

**health_invoicing** (19.0.1.3.3 → **19.0.1.4.0**)
- `static/src/js/client_package_patch.js` — the controller patch became five Shortcuts
  registry entries; `__manifest__.py` (version), `i18n/vi_VN.po`

**health_theme** — not touched (no version bump).

**docs**: this report, `workspace_ws2_shots/` (34 screenshots + `CONSOLE_AND_CHECKS.md`),
ledger §5.249–§5.254, programme status.

Python proof (safety rail 6) — `git diff 99b0e94a --stat -- '*.py'`:
`health_crm/__manifest__.py`, `health_fieldservice/__manifest__.py`,
`health_fieldservice/models/res_partner.py` (+33, inside `get_client_profile_data`),
`health_fieldservice/tests/__init__.py`, `health_invoicing/__manifest__.py`, plus the new
test file.

## Tests (`health_fieldservice/tests/test_ws_client_form.py`, post_install)

| # | What it asserts | Result |
|---|---|---|
| 1 | invoicing's two anchors (incl. the exact `bj-bookings-section` class) and health_crm's `people_panel` resolve on the own arch; one People panel, inside the rail; view 5428 targets it and no longer the banner | PASS |
| 2 | combined arch has every installed extension tab (twin_trends_ops, vitals_thresholds_ops, consents_ops, bhyt_ops, careplans_ops, family_ops, booking_links_ops, diagnoses_ops, portal_access_ops), `main_contact_id` inside People, invoicing's package widget and recent payments | PASS |
| 3 | own-arch field set ⊇ committed "before" list (70 names); each extension's fields ⊇ its "before" list; the nine own pages, same names, same order | PASS |
| 4 | the four header buttons keep `invisible`/`groups`/`confirm`; all four carry `ws-more` | PASS |
| 5 | `ws-workspace`; one ws-page/ws-main/ws-rail/ws-hero/ws-next; the four client widgets (glance modes glance, contact, attention in the rail); tray keys are `div[@name]` holding their fields, fields exist on res.partner; allergies strip in the main column, `invisible="not allergies"`, never in a tab; chatter last; no `Commission Duration`; first tab "Overview" | PASS |
| 6 | `get_client_profile_data`: future confirmed → `next_visit`, completed → `last_visit`, `recent_visits` newest first with state + label; a client with none → `False`/`False`/`[]`; old keys intact | PASS |
| 7 | chrome template has no `ph-kpis`/`ph-header`/`ops-cp-sidebar`/`ops-content-with-sidebar`/`ph-actions`, keeps breadcrumb + save indicator; no template in `addons/*/static/src/**` t-inherits it on a missing class (0 extenders now); health_crm's two files and manifest lines gone; no fetch on mount | PASS |
| 8 | neither stylesheet hides `.o-mail-Form-chatter`/`.o-mail-ChatterContainer`; booking arch still has `<chatter` | PASS |
| 9 | every `_t` / template string of the new files (and health_invoicing's entries) has Vietnamese with the right `code:` occurrence; the arch terms have the view occurrence; "Main contact" in health_crm with its view occurrence; the web catalogue serves "Lượt thăm gần đây", "Chưa có lịch hẹn.", "Mua gói dịch vụ" | PASS |
| 9b | every worded term of the client view and of view 5428 reaches the **database** in Vietnamese (except the placeholder "Tên tiếng Việt", which is Vietnamese already) | PASS |
| 9c | no "Odoo" in new strings, the view, or the Vietnamese this phase touched; matcher self-check | PASS |
| 10 | no `min()/max()/clamp()` outside a custom property in the two client stylesheets; no gradient in the WS-2 section; every icon the panels name has a mask rule | PASS |

Suite runs on the practice copy (verbatim result lines):

- `-u health_fieldservice,health_crm,health_invoicing` with tags health_fieldservice,
  health_crm, health_invoicing, health_cms_coverage, health_cms_clinical:
  `odoo.tests.result: 0 failed, 0 error(s) of 59 tests when loading database 'carejiox_ws2'`
  — stats: health_cms_clinical 5, health_cms_coverage 27, health_crm 4, health_fieldservice 41;
  59 `Starting Test…` lines.
- i18n gate + theme + both Workspace suites (no upgrade):
  `odoo.tests.result: 0 failed, 0 error(s) of 38 tests when loading database 'carejiox_ws2'`
  — stats: health_base 9, health_fieldservice 27, health_theme 16; G1, G1b, G1c, G2, G2b all
  logged `Starting`.
- First run was `1 failed … of 59` — test 9b flagged the already-Vietnamese placeholder; the
  allowlist entry fixed it (no product change).
- `health_invoicing` has **0 tests** (no `tests/` package) — nothing to be green (§5.219).
- `health_cms_coverage` T2/T3/T9 and `health_cms_clinical` pass unchanged (handover test 10).
- The last 2-line fix (`3e5177b4`, the Recent visits date column) came after the final suite
  run; it changes one format call and two CSS properties that no test reads. It was verified
  in the browser on live (Vietnamese), where the bundle rebuilt cleanly.

## Live deploy (one sitting)

1. Backups: `/var/backups/ws2/carejiox-20260929-1544.dump`, `carejiox_template-…`, `hhh-…`.
2. Modules staged in `/tmp` together; `carejiox-deploy -d -m health_fieldservice,health_crm,health_invoicing`
   → EXIT 0 (the chrome-template change and the health_crm deletion reached the tree in the
   same copy); then `-D carejiox_template` → EXIT 0; then `-D hhh` → EXIT 0. The follow-up
   date fix went the same way (`-d -m health_fieldservice`, `-D carejiox_template`, `-D hhh`,
   all EXIT 0).
3. Versions on all three: health_fieldservice 19.0.2.10.0, health_crm 19.0.1.11.0,
   health_invoicing 19.0.1.4.0 (health_theme unchanged 19.0.5.4.0).
4. Scheduled jobs: master 96 → 96, hhh 77 → 77, template 0 → **7** after each upgrade →
   switched off on the template alone → 0.
5. AppleDouble files in the live tree: 0. Asset caches cleared on all three, restart via `-s`.
6. `/web/login`: carejiox.com 200, hhh.carejiox.com 200. No new ERROR/CRITICAL in the server
   log (one pre-existing Zalo access message from the QA persona before the deploy).
7. Bundle compiled (see `CONSOLE_AND_CHECKS.md`).
8. Not served, not touched: `vietuat`, `codex_fb_center_reply` (only `hhh` is a `biz_tenant`).
9. Practice copy dropped with its filestore, private tree, units and tunnel removed.
   Temporary live account deleted (0 rows in `res_users` and `res_partner`).

## Browser QA

| # | Item | Where | Evidence | Result |
|---|---|---|---|---|
| 1 | Bùi T at 1440: hero, Next step "1,050,000 ₫ is unpaid." + View invoices, glance, People with Main contact picker, Needs attention, Shortcuts; side by side with the concept | clone + live | `00_…`, `00b_…`, `01_…`, `01b_…`, `10_live_BEFORE…`, `11_live_AFTER…` | PASS. Main contact: the only allowed contact for Bùi T is Bùi T herself, so "change and save" had nothing to change to — dropdown opened (`02b_…`, live `13_…`), nothing saved on live. "View invoices" opened the client's invoice list on live. |
| 2 | Allergies strip above the fold | clone | `02_…` (An Xu, allergies set on the practice copy) | PASS — top 294 px of 1000. **No client on live has allergies**, so it could not be shown live. |
| 3 | No bookings; archived; active package (Package shortcut → rich dialog, closed) | clone | `03a_…`, `09d_…` (archived, Vietnamese), `03c_…` | PASS. There is no inactive client on either database. |
| 4 | Identity chip → National ID → save → reload → stays open | clone | `04a_…`, `04b_…` | PASS (National ID 001236009999 on the practice copy only) |
| 5 | More menu open, dismiss | clone + live | `05_…`, `12_…` | PASS (Delete, Archive) |
| 6 | Recent visits row → booking screen → back | clone | `06a_…`, `06b_…` | PASS — breadcrumb kept (D3) |
| 7 | Tabs: Bookings (slim line), Financial Summary (invoicing's additions), Care Plans, Diagnoses, Trends, BHYT | clone + live | `07a_…`, `07b_…`, `15_…`; DOM check of all six | PASS, no error dialog |
| 8 | Notes feed on client AND booking BK3831 | clone (log note posted on both) + live (view only) | `08a_…`, `08b_…`, `14_…`, `17_…` | PASS; the pinned rail stops above the feed |
| 9 | 1100 / 820 px; CRM contact screen unchanged; Vietnamese | clone + live | `09a–c`, `16a–b`, `18_…`, `09d_…`, `19_…`, `19b_…` | PASS — no horizontal scroll; rail drops under at 1100 |

Pixel pass (several iterations, measured, `CONSOLE_AND_CHECKS.md`). Fixed along the way: a
render crash (`t-set` vs getter, §5.249); six loader calls → one (§5.250); the Recent visits
title not matching the other card titles; booking names wrapping in the visits list; the
main-contact picker drawn as a boxed input; field chips (code, category) sitting 6 px high;
the archived strip invisible on the canvas colour; the active-tab underline clipped
(§5.251); the chatter card 16 px wider than the page; People's phone disagreeing with the
hero (it read the legacy mobile first); first/last name showing nothing when empty; the
Financial / Bookings stat line showing boxed inputs; Vietnamese dates wrapping ("3 Tháng 4").

## Deviations (each the smallest that keeps the contracts)

- **D1 — a third `ws_client_glance` mode, `contact`**, for the client's own row in People
  (name, phone, Call / SMS / Email). The handover wanted `tel:`/`sms:`/`mailto:` links; an
  arch cannot bind an `href` to a field value, and adding a fifth widget was not sanctioned.
  Same widget, same loader, record data only.
- **D2 — nine new icon files in `health_fieldservice/static/src/img/ws/`** (mail,
  message-square, gift, repeat, list, receipt, banknote, calendar-plus, wallet) with their
  mask rules in the client stylesheet. The kit had no mail / message / gift / repeat / list /
  receipt / money icons; adding them to health_theme would have forced a health_theme upgrade
  (cascades to every dependent module) for icons only this screen uses so far. WS-3 can move
  them into the kit.
- **D3 — "Open booking" and a Recent visits row open the booking with the same act_window the
  booking list uses**, not via `action_open_ops_booking_detail`: that method returns a client
  action that clears the breadcrumbs, so "back" would lose the client (QA 6 asks for back).
  Same destination screen.
- **D4 — `recent_visits` added to C4** (handover allowed it "if the timeline lacks state"):
  the existing `bookings` list has no raw datetime.
- **D5 — the shortcut `run` gets a third argument `ctx = {record, reload}`** so the package
  entry can refresh the screen after a purchase (the handover's "onDone reloads the record +
  loader"). `run(env, partnerId)` still works for entries that ignore it. health_fieldservice
  registers `new_booking`, `recurring`, `bookings`; no `appointments` entry —
  `action_view_appointments` opens the same booking list as `action_view_fso_orders`.
- **D6 — the deleted / archived / allergies banners keep their inner markup byte-for-byte
  (including the `<i class="fa…">` and the text's original indentation)**; only the div's
  classes changed and CSS hides the `<i>` and draws a mask icon. Whitespace is part of the
  translation term (§5.246), so re-indenting would have dropped their Vietnamese on fresh
  databases.
- **D7 — `.po` edits beyond new strings:** (a) "Referrer" said "Đề xuất" ("suggest") — now
  "Người giới thiệu"; (b) "Last visit" said "Chuyến thăm cuối cùng" — now "Lượt thăm gần
  nhất" for the same wording as the other visit rows (also changes the client list's column
  label); (c) health_crm "Main Contact" lost its code occurrence and marker for the deleted
  template (G1b would otherwise flag it).
- **D8 — the hero's address fact gets its full-text tooltip from the glance widget** (a view
  arch cannot bind `title`); the widget sets it on mount/patch inside its own form only.
- **D9 — small additions:** hidden `patient_code`, `age`, `is_referrer`, `avatar_128` fields
  in the arch (for chip conditions and the avatar); `placeholder="—"` on empty-able fields;
  the tab-underline fix scoped to both screens in the client stylesheet (§5.251); the rail
  and chatter shared rules for the booking screen live in the client stylesheet because the
  booking stylesheet was sanctioned for lines 6-14 only.
- **D10 — evidence path exceptions:** the archived client (`09d_…`) was opened by address
  (archived clients are not in the Clients list); `03c_…` and `05_…` were taken on An Xu
  reached by address during the pixel pass. All other shots follow the real path.
- **D11 — the live Vietnamese check used the temporary QA account's own language switch**
  (a change to that throwaway account only, deleted afterwards).

## Removed SCSS selectors (each class grep-checked outside stylesheets, anchored on the attribute boundary — §5.252)

`ops_client_profile_form.scss` (all were scoped to `.ops-client-profile-form-page`): the
chatter-hide block; `.ph-header`, `.ph-identity`, `.ph-avatar`, `.ph-details`, `.ph-name-row`,
`.ph-name`, `.ph-code`, `.ph-tags`, `.ph-tag` (+ `.active/.regular/.vip`), `.ph-contact`,
`.ph-actions`, `.ph-action-btn` (+ `.secondary/.primary`), `.ph-kpis`, `.ph-kpi`,
`.ph-kpi__icon` (+ six `[data-kpi]` masks), `.ph-kpi--bookings/--packages/--spent/--outstanding/--satis/--refer`,
`.ph-kpi__value`, `.ph-kpi__label`, `.oe_title h1`, `.patient-badges`, the old notebook tab
block (`.o_notebook .nav-tabs …`, orange active underline, `.tab-content` padding),
`.ops-content-with-sidebar`, `.ops-cp-sidebar`, `__card` (+ `--primary`), `__card-title`,
`__card-subtitle`, `__btn` (+ `--primary`), `__section-title`, `__action`, `__separator`; the
media blocks for them at 1366 / 1180 / 980 / 680 px; the unused `$crm-accent`.

`ops_client_profile.scss` (global rules): `.ops-client-profile-page`, `.cp-page-body`,
`.ph-header`, `.ph-identity`, `.ph-avatar`, `.ph-details`, `.ph-name-row`, `.ph-name`,
`.ph-code`, `.ph-tags`, `.ph-tag`, `.ph-contact`, `.ph-actions`, `.ph-action-btn`, `.ph-stats`,
`.ph-stat`, `.ph-stat-value`, `.ph-stat-label`, `.cp-tabs`, `.cp-tab`, `.cp-tab-badge`,
`.cp-content-grid`, `.cp-col`, `.cp-card`, `.cp-card-header`, `.cp-card-title`,
`.cp-card-action`, `.cp-card-body`, `.cp-mini-table`, `.cp-package-card`, `.cp-pkg-header`,
`.cp-pkg-name`, `.cp-pkg-status`, `.cp-pkg-progress`, `.cp-pkg-fill`, `.cp-pkg-meta`,
`.cp-payment-item`, `.cp-pay-icon`, `.cp-pay-info`, `.cp-pay-desc`, `.cp-pay-date`,
`.cp-pay-amount`, `.cp-timeline`, `.cp-tl-entry`, `.cp-tl-dot`, `.cp-tl-content`,
`.cp-tl-text`, `.cp-tl-time`.
Kept (still used by the quick-booking, recurring-booking, staff-assignment and
payment-collection screens): `.cp-breadcrumb`, `.cp-sep`, `.cp-current`. Kept in the client
stylesheet: page shell, breadcrumb bar, `.vu-section*`, `.vu-detail-card`, `bj-*` (other tabs).

`ops_booking_form.scss`: the chatter-hide block (lines 6-14) only.

Left in place, now dead, not sanctioned: `health_crm/static/src/scss/ops_client_list_ext.scss`
`.ph-main-contact` / `.ph-mc__*` (styled the deleted header extension).

## Shortcuts registry entries (`registry.category("ws_client_shortcuts")`)

| Module | key | Label | Runs |
|---|---|---|---|
| health_fieldservice | `new_booking` (10) | New booking | `action_open_quick_booking_owl` |
| health_fieldservice | `recurring` (20) | Recurring booking | `action_open_recurring_booking` |
| health_fieldservice | `bookings` (30) | All bookings | `action_view_fso_orders` |
| health_invoicing | `package` (40) | Buy a package | `PackageWizardDialog` (patient mode), `onDone` → reload record + loader |
| health_invoicing | `invoice_new` (50) | Create invoice | `action_create_standard_invoice` |
| health_invoicing | `invoices` (60) | Invoices | `action_view_invoices` (also the Next step "View invoices") |
| health_invoicing | `packages` (70) | Packages | `action_view_service_packages` |
| health_invoicing | `payments` (80) | Payments | `action_view_payment_transactions` |

Method failures show the old sidebar's friendly warning ("Action not available…").

## Loader call count per page load

**1** (measured on the practice copy and on live, including tab switches; +1 after a save,
shared by the panels and the controller). Before §5.250's fix it was 6.

## Concept vs live (QA 1, `00_concept…` vs `11_live_AFTER…`)

| Concept | Live | Why |
|---|---|---|
| Journey Enquiry → First visit → Active client → On a package | No journey | Binding non-goal: the client has no stage field |
| Hero buttons Book visit / Call / Message / ⋯ | Only "More" top right; Call / SMS / Email in People; New booking in Next step and Shortcuts | Handover: header holds only the four lifecycle buttons (under More); contact in People |
| Next step "Send payment link" | "View invoices" | No payment-link action exists; the handover's rule 1 button |
| Initials on navy | The client's own avatar image | Uses `avatar_128` as specified |
| Glance: Outstanding big first; Satisfaction "No rating" | Visits, Last visit, Next visit, Client since, Spent, Outstanding, Packages, Referrals; no Satisfaction | Handover order; satisfaction is a non-goal |
| Tabs: Overview / All details / Activity | All 18 existing tabs, scrolling | Non-goal: tabs kept |
| Cards: Personal, Contact & address, Main contact, Medical, Packages | Personal, Contact, Care, Identity, Commission, Recent visits; main contact in People | Handover card set; address stays on its tab (one line in the hero) |
| Visits: BK codes with dates | Real booking names — many Bùi T bookings are named "New Booking" | Data, shown truthfully |
| "Activity & notes" card | The real notes feed (Send message / Log note / Activity) | Standard feed, restyled to the page width |

Data notes: Bùi T's outstanding is 1,050,000 ₫ today (the concept said 1.1M). "Last visit
179 days ago" (latest completed booking, 3 Apr) while the Bookings tab's older "Last Visit"
stat says Aug 3 — that stat is the stored `last_visit_date`, which is maintained differently;
the handover said to use the new `last_visit`.

## New ledger entries

§5.249 (`t-set` vs getter crashes the form), §5.250 (per-component reactive proxies defeat a
shared memo — `toRaw`), §5.251 (the kit's scrolling tab row clips its underline), §5.252
(`grep -w` treats `-` as a boundary — `crm-ph-*` is not `ph-*`), §5.253 (chrome-devtools
window height is capped — use `emulate`), §5.254 (the package dialog is a `.pw-overlay`, not a
`.modal`).

## Commits (branch 19.0, not pushed)

- `b01a0111` feat(workspace): move the client screen onto the Workspace kit, and show the notes feed
- `3e5177b4` fix(workspace): keep a Recent visits date on one line in every language
- docs commit (this report, evidence, ledger, programme) — see `git log`

## Evidence (`docs/handovers/workspace_ws2_shots/`)

`00_concept_option_b_client.png`, `00b_concept_option_b_client_lower.png`,
`01_clone_BEFORE_bui_t_751.png`, `01_clone_bui_t_top_1440.png`,
`01b_clone_bui_t_bottom_tray_and_notes.png`, `02_clone_allergies_banner_above_fold_an_xu.png`,
`02b_clone_main_contact_dropdown_open.png`, `03a_clone_client_with_no_bookings_864.png`,
`03c_clone_package_shortcut_rich_dialog.png`, `04a_clone_identity_chip_opened_national_id_typed.png`,
`04b_clone_after_save_reload_identity_stays_open.png`, `05_clone_more_menu_open.png`,
`06a_clone_recent_visit_opens_booking_bk3831.png`, `06b_clone_back_to_client.png`,
`07a_clone_tab_bookings_slim_line.png`, `07b_clone_tab_financial_summary_slim_line.png`,
`08a_clone_client_notes_feed_log_note_posted.png`, `08b_clone_booking_bk3831_notes_feed_log_note_posted.png`,
`09a_clone_1100px.png`, `09b_clone_1100px_rail_below.png`, `09c_clone_820px.png`,
`09d_clone_vietnamese_archived_client_200.png`, `10_live_BEFORE_bui_t_old_screen.png`,
`11_live_AFTER_bui_t_top_1440.png`, `12_live_more_menu_open.png`,
`13_live_main_contact_dropdown_open_only.png`, `14_live_bui_t_bottom_notes_feed.png`,
`15_live_tab_bookings_slim_line.png`, `16a_live_1100px.png`, `16b_live_820px.png`,
`17_live_booking_bk3831_notes_feed_view_only.png`, `18_live_crm_contact_screen_unchanged.png`,
`19_live_vietnamese_bui_t.png`, `19b_live_vietnamese_recent_visits_one_line.png`,
`CONSOLE_AND_CHECKS.md`.

## Not done / open (plainly)

- **Allergies strip on live**: no client on the live database has allergies recorded, so it
  was proven on the practice copy only.
- **Main contact change on live/clone**: Bùi T has no other allowed contact (no
  representatives), so the picker could only be opened, not changed.
- **Owner question — the Financial Summary tab contradicts the new panel.** Its old stat
  line shows the accounting "credit" figure as "Total Paid" and "debit" as "Outstanding"
  (An Xu: Total Paid 19,504,985 ₫, Outstanding 0 ₫), while the new At a glance and Next step
  say 19,504,985 ₫ is unpaid. The labels predate this phase and the tab's fields were out of
  scope; relabelling (or swapping) them is a one-line change that needs a yes.
- Pre-existing, other modules, not changed: the package dialog does not close on Escape
  (§5.254); "Gender" is still English for a Vietnamese reader (field label); the old
  Vietnamese for "ALLERGIES:" reads "Tâm dị ứng" (existing term; overwrite is off, so fixing
  it needs a translation pass); the required-field asterisks drawn by the field-requirement
  script disappear after switching tabs until the next load; `.ph-main-contact` rules in
  health_crm are now dead (unsanctioned file).
- Nothing else in the definition of done is outstanding.

## Kit notes for WS-3 (CRM contact screen)

1. **The CRM contact screen does not share the client's `ph-*` classes** — it uses its own
   `crm-ph-*` prefix (`crm-ph-identity`, `crm-ph-avatar`, `crm-ph-details`, `crm-ph-name-row`,
   `crm-ph-code`, `crm-ph-name`, `crm-ph-status-badge`, `crm-ph-meta`, `crm-ph-actions`,
   `crm-ph-action-btn`, plus `crm-hdr-status-*`, `crm-more-toggle`) in
   `health_crm/static/src/xml/crm_contact_form.xml` + `crm_contact_form.scss`. Nothing WS-2
   removed touched it (live check `18_…`). Its header is an OWL controller template with its
   own RPC (`headerState`), exactly the client's old shape: move identity into the arch hero,
   stop the chrome drawing it, keep breadcrumb + save.
2. **Copy the WS-2 panel pattern, not the booking one**: one shared loader keyed by
   `toRaw(record.model)` + resId + `write_date` (§5.250), widgets refreshed in `onWillRender`,
   a reactive version bus for "refresh after an action", and a Shortcuts registry
   (`ws_client_panels.js` is the template — its loader, `runPartnerMethod` and
   `openBooking` helpers are exported).
3. **Icons**: the nine in `health_fieldservice/static/src/img/ws/` (mail, message-square,
   gift, repeat, list, receipt, banknote, calendar-plus, wallet) plus phone / package /
   shield-check from the kit are what a contact screen needs; consider moving them into
   `health_theme`'s `$ws-icons` list when WS-3 touches health_theme anyway.
4. **Kit fixes worth folding into `ws_workspace.scss` in WS-3** (they live in the client
   stylesheet today, scoped to client + booking): the tab-row `padding-bottom: 1px`
   (§5.251); field widgets used as `.ws-chip` need `display:inline-flex; flex-direction:row;
   align-items:center; margin:0` and a block inner span; a card title nested in a header row
   is not styled by the kit's `> .vu-card__title` rule; the Shortcuts row's first-span rule
   blanks a mask icon's colour.
5. **Titles**: give card titles block children (`<div class="vu-section__icon" data-icon=…/><div>Title</div>`)
   so each title is a plain translation term; keep any re-used text's whitespace identical
   (D6).
6. **People panel**: the `contact` mode renders a person row with icon links; a lead's
   "Linked client" / "Handled by" rows can reuse `.ws-person` markup.
7. **The contact has a real stage** (`contact_status`), so `ws_journey` can run on it
   (`state_field="contact_status"`) — unlike the client.
