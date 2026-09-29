# WORKSPACE — WS-1 report: the booking screen on the Workspace kit

Implemented and self-reviewed by Opus, 2026-09-29, from `WORKSPACE_WS1_BOOKING.md`.
Status: **done — live on `carejiox`, `carejiox_template` and `hhh`.** Not pushed.

## In plain words

The booking screen now opens as one calm page: the booking number, client, time, length,
facility and area on one line; a journey bar with the dates each stage was reached; one
blue **Next step** banner that says what to do and has the one button to do it; tabs as a
simple underline row; cards that pack tightly, with empty ones folded into a "Not filled
yet" line; and a panel on the right that stays in view with **At a glance**, **People**,
**Needs attention** and **Shortcuts**. Rare buttons (Duplicate, Cancel, Create, Delete,
Archive…) sit under **More**. Nothing a user may do changed, and nothing moved on any
other screen.

## Standing rules (stated back)

- White-label: no "Odoo" in anything a user sees — gated by test 9 (JS strings, templates,
  the booking view's text and attributes, and the Vietnamese of every entry this phase touched).
- Flat mono colours from `--vuf-*` tokens only; no gradients (test 10); CSS-mask SVG icons;
  no new font-awesome in markup I wrote (the hero chips even lost theirs).
- Chatter stays at the bottom, full width (the `<chatter/>` is still the form's last child —
  test 5). See "Concept vs live" about it being hidden on this page.
- No business-logic change: no model/field Python, no button name/method change, every
  `invisible`/`groups`/`confirm`/`readonly` kept (tests 3–4). The only `invisible` written
  new is display-only (the service timer, per the handover; two fact chips hide when empty).
- Tests never with `carejiox-deploy -t` on live; rehearsed on `carejiox_ws1` with
  `biz.tenant` neutralised (`slug = nowhere_ws1`), jobs off after every upgrade,
  `--db-filter=^carejiox_ws1$`, `systemd-run` on port 8199.

## Files

**health_theme** (19.0.5.3.0 → 19.0.5.4.0)
- new `static/src/scss/ws_workspace.scss` — the kit: page grid + pinned rail + container
  ladder, hero, journey, Next step, underline tabs, masonry pack, read-first cards, fold
  tray, rail panels, More menu, CSS-mask icons.
- new `static/src/js/ws_journey.js`, `static/src/xml/ws_journey.xml` (K2)
- new `static/src/js/ws_fold_tray.js`, `static/src/xml/ws_fold_tray.xml` (K3)
- new `static/src/js/ws_statusbar_more.js`, `static/src/xml/ws_statusbar_more.xml` (K4)
- `static/src/scss/vu_form_engine.scss` — `.ws-rail` added to the two §10 selector lists (K5)
- new icons in `static/src/img/lucide/`: plus, more-horizontal, user-plus, play, x-circle,
  house, video, flask-conical, trash, archive, arrow-up (deviation D1)
- `__manifest__.py` (assets + version), `i18n/vi_VN.po`

**health_fieldservice** (19.0.2.8.2 → 19.0.2.9.0)
- `views/health_fieldservice_order_views.xml` — only record `view_health_fso_form_ops`
- new `static/src/js/ws_booking_glance.js`, `static/src/xml/ws_booking_glance.xml`
  (`ws_booking_glance` glance/attention, `ws_booking_hint`)
- `static/src/scss/ops_booking_form.scss` — dead rules removed, booking workspace rules added
- `i18n/vi_VN.po`, `__manifest__.py`, new `tests/test_ws_booking_form.py`, `tests/__init__.py`

**docs**: this report, `workspace_ws1_shots/` (31 screenshots + `CONSOLE_AND_CHECKS.md`),
ledger §5.245–§5.248, programme status.

Python proof (safety rail 4) — `git diff 0127f261 --stat -- '*.py'`: only the two
`__manifest__.py` files, `tests/__init__.py` and the new test file.

## Tests (`health_fieldservice/tests/test_ws_booking_form.py`, post_install)

| # | What it asserts | Result |
|---|---|---|
| 1 | every §2 anchor xpath finds ≥1 node in the view's own arch; the first `currency_id` is still the hidden dependency under `<sheet>` | PASS |
| 2 | combined arch carries `action_prepay_quote`, `payment_summary_card`, `action_tele_join`, `telehealth_ops`, `action_open_red_invoice`, `pricing`, `visit_tasks_ops`, `family_updates_ops`, `legacy_audit_card` (each only when its module is installed); payment + legacy cards land inside the Overview pack; Red Invoice lands in Shortcuts | PASS |
| 3 | own-arch field set ⊇ committed "before" list (84 names); each installed extension's fields ⊇ its committed "before" list (24 names) | PASS |
| 4 | the 12 own + 3 extension header buttons keep identical `invisible`/`groups`/`confirm`; the nine carry `ws-more` and no `oe_highlight`/`btn-primary`; no own header button is primary; Reschedule stays inline | PASS |
| 5 | form class has `ws-workspace`; exactly one `ws-page`/`ws-main`/`ws-rail`/`ws_journey`/`ws_fold_tray`; tray card keys exist as `div[@name]`, their fields exist on the model; journey steps/date fields exist; glance, attention and client card sit in the rail; seven hints; chatter last | PASS |
| 6 | `vu_progress_rail` and `vu-quick-info` gone from this view; `vu_progress_rail` still in the standard form | PASS |
| 7 | the three booking tabs are lazy widgets with no `<field>`; page order unchanged | PASS |
| 8 | every `_t` literal and template string of the new files has a non-empty Vietnamese entry with the right `code:` occurrence; plain arch terms have the view occurrence; the web catalogue serves "Cần chú ý", "Thêm", "Chưa điền" at runtime | PASS |
| 8b | every worded term of the booking view reaches the **database** in Vietnamese (except `min`, `km`, untranslated before this phase) | PASS |
| 9 | no "Odoo" in new JS/template strings, the view's text/attributes, or the Vietnamese of entries this phase touched; matcher self-check | PASS |
| 10 | no `min()/max()/clamp()` outside a custom property in the two stylesheets; no gradients in the kit or in the booking workspace section | PASS |

Suite runs on the practice copy (verbatim result lines):

- Baseline, untouched copy, live code: `odoo.tests.result: 0 failed, 0 error(s) of 41 tests when loading database 'carejiox_ws1'` (health_cms_coverage 27, health_fieldservice 14, health_theme 16 in the stats lines)
- Baseline i18n gate: `0 failed, 0 error(s) of 5 tests`
- After (final): `odoo.tests.result: 0 failed, 0 error(s) of 52 tests when loading database 'carejiox_ws1'` — health_cms_coverage 27, health_fieldservice 27, health_theme 16 (stats lines). The 11 new methods all logged `Starting TestWsBookingForm.test_…`.
- After, i18n gate + dropdown guard: `0 failed, 0 error(s) of 7 tests` (health_base 9 / health_theme 4 in stats; G1, G1b, G1c, G2, G2b, G1, G2 guard)
- `health_invoicing` has **0 tests** (no `tests/` package) — tagged, nothing ran; "green" would be meaningless (ledger §5.219).
- `health_cms_coverage` consolidation tests (T3, T3b, T9): pass unchanged (test 7 of the handover).
- No pre-existing failures to list: the baseline was already 0 failed.

## Live deploy (one sitting)

1. Backups: `/var/backups/ws1/carejiox-20260929-1409.dump`, `carejiox_template-…`, `hhh-…`.
2. `carejiox-deploy -d -m health_theme,health_fieldservice` → EXIT 0; then `-D carejiox_template` → EXIT 0; then `-D hhh` → EXIT 0. No ERROR/CRITICAL in the server log for the window.
3. Versions on all three: `health_theme=19.0.5.4.0`, `health_fieldservice=19.0.2.9.0`.
4. Scheduled jobs: master 96 → 96, hhh 77 → 77, template 0 → **7** after its upgrade → switched off on the template alone → 0.
5. AppleDouble files in the live tree: 0. Asset caches cleared on all three.
6. `/web/login`: carejiox.com 200, hhh.carejiox.com 200. Bundle compiled (see `CONSOLE_AND_CHECKS.md`).
7. Not served, not touched (confirmed): `vietuat` (none of these modules installed) and `codex_fb_center_reply` (nginx drops every host containing "_", no `biz.tenant` row). `carejiox_template` is equally unreachable by hostname but was upgraded as the runbook requires.
8. Practice copy dropped with its filestore; helper script, unit leftovers and tunnel removed. Temporary live QA account deleted (0 rows in `res_users` and `res_partner`).

## Browser QA

| # | Item | Where | Evidence | Result |
|---|---|---|---|---|
| 1 | BK3831: hero, journey (Created Sep 12), Next step "Assign Staff" + hint, glance, attention, tray | clone + live | `01_…`, `11_live_AFTER_…` (+ `00_concept…`, `10_live_BEFORE…`) | PASS — see data note below |
| 2 | "Additional charges" chip → card opens, Travel Charge focused → 50,000 → save → reload → card stays open → back to 0 → save | clone | `02a_…`, `02b_…` | PASS. Before: empty (NULL) / total 0. After: 0 / total 0 (same on screen). |
| 3 | More menu; Cancel Booking asks | clone (confirmed once → the cancellation wizard opened → discarded, booking stayed confirmed, nothing to restore) + live (dismissed) | `03_…`, `03b_…`, `03c_…`, `12_…`, `12b_…` | PASS |
| 4 | draft, assigned, in progress, completed, cancelled | clone + live (Hà Nội records on live) | `04a–e`, `13a–e` | PASS. No `completed_pending_invoice` booking exists on either database. |
| 5 | Pricing, Visit Tasks, Family Updates, Telehealth (and Clinical) open and load, no error | clone | `05a_…`, `05b_…`; DOM check for all five | PASS |
| 6 | 1100 px and 820 px: rail drops under, no horizontal scroll | clone + live | `06a–c`, `14a–b` | PASS (the tab row scrolls inside itself, by design) |
| 7 | other native forms unchanged | live before/after | `07a_…`, `07b_…` | PASS — client profile identical, header HTML byte-identical. See D7 for the standard booking form. |
| 8 | Vietnamese reader | clone | `08a_…` | PASS for every WS-1 string (see "Not done / open") |

Pixel pass (several iterations, measured, `CONSOLE_AND_CHECKS.md`): fixed along the way — the
banner was not laid out (state-system `!important`, ledger §5.247), "Created … by" wrapped into
four lines and then lost a space (§5.247), label rows were double-padded (43 → 32 px), the
driving-distance value sat 8 px left of its column, an empty read-only link showed nothing
instead of "—", and nine tabs wrapped to two lines. Final: chips 24 px, 16 px between cards,
nothing clipped, one label line and one value line per column, rail panels equal.

Data note for QA 1: on both databases BK3831 now has a lead nurse (Nguyễn Như Anh) and a
service fee of 200,000 ₫, and its visit date (20 Sep) has passed. So Care team and Pricing
are not folded, the banner hint reads "The visit time has passed", and "Nobody assigned…" does
not appear — the screen is reporting the record truthfully; it differs from the owner's
screenshot because the record changed, not the screen.

## Deviations (each the smallest that keeps the contracts)

- **D1 — new icon files in `health_theme/static/src/img/lucide/`** (11 SVGs). The handover asks
  for icons the folder did not have ("plus" chips, a masked ellipsis for More, service-type
  icons). Adding them is the only way to meet "CSS-mask SVG, never emoji/font-awesome".
- **D2 — the hero chips are `<div class="ws-chip" data-icon="…">Label</div>`, not
  `<span>` + icon element.** With spans, all ten status/service chips became ONE translation
  term and read English in Vietnamese (ledger §5.246). Same conditions, same texts; their
  font-awesome icons became CSS masks.
- **D3 — booking-only styles scoped `.o_form_view.ops-booking-form-page.ws-workspace`**, not
  `.ops-booking-form-page .ws-workspace`: both classes sit on the same element (§5.245).
- **D4 — `.po` edits beyond "new strings":** (a) the existing msgid "Outstanding" said
  "Tốt nhất" ("best"); the glance needs that msgid, a file holds one msgstr per msgid, so it
  now says "Còn nợ" — this also corrects the client profile's "Outstanding" tile; (b) card
  titles use exact-markup msgids (the file's existing style), including one for the
  re-indented "Location Details" title so fresh databases translate it too; (c) occurrence
  lines were added to existing entries (Today, Staff, Paid, Deleted, Home Visit…) instead of
  duplicating them.
- **D5 — buttons moved to More also lost `btn-success` (Start Service) and the invisible AI
  button lost `oe_highlight`**, so no header button of this view is coloured; the handover's
  "keep it on nothing else" read literally. Extension buttons (Pay Quote `btn-info`,
  Complete Service `btn-success`, Join Video `oe_highlight`) are untouched in the arch; the kit
  paints every header button neutral except a FIRST button that carries `oe_highlight`/`btn-primary`.
- **D6 — small additions for a real layout:** `name=` on the new/renamed cards and on the
  Next step cards (`visit_card`, `confirmed_assign_card`… for styling and future anchors);
  `placeholder="—"` on a few empty-able fields; the facility and area facts hide when empty;
  an extra hint/attention wording for "tomorrow" (so it never says "in 1 days"); the Staff row
  goes quiet grey when nobody is expected yet; the rail scrolls itself if it is taller than the
  window (otherwise sticky would hide its bottom). The Next step "Next Best Action" star icon
  (font-awesome) was dropped with the supertitle text change; the cancelled card's title inline
  style went with the card's.
- **D7 — safety rail 5 for the STANDARD booking form was checked by test 6 and on the practice
  copy, not by a live before/after screenshot**: an Operations Manager cannot open that form on
  live at all (pre-existing permission error, ledger §5.248). The live before/after pair is the
  client profile (a native contact form).
- **D8 — `hhh` "booking screen opens" was proved server-side** (the view loads with the kit
  layout; `hhh` has no bookings to open) rather than by creating an account on a paying
  customer's system.
- **D9 — test file has 11 methods** (the handover's 9 plus 8b, the database-level Vietnamese
  proof that found D2, and 10, a stylesheet guard).

## Removed SCSS selectors (`ops_booking_form.scss`; each class grep-checked in every XML/JS/Py/HTML under `addons/`)

`.vu-booking-hero`, `.vu-hero-left`, `.vu-hero-title-row`, `.vu-hero-title`, `.vu-hero-tags`,
`.vu-hero-right`, `.vu-hero-meta__label`, `.vu-hero-meta__by`, `.vu-quick-info`,
`.vu-quick-info__item` (with its `::before`, `:hover` and five `:has(.vu-qi-*)` accents),
`.vu-quick-info__icon`, `.vu-quick-info__label`, `.vu-quick-info__value`, `.vu-qi-scheduled`,
`.vu-qi-service`, `.vu-qi-duration`, `.vu-qi-facility`, `.vu-qi-catchment`, the
`.vu-col-1, .vu-col-2` layout block, `.vu-action-star`, `.vu-side-card`,
`.vu-side-card__header`, `__body`, `__row`, `__label`, `__empty`, `__empty-icon`, `__value`,
`.vu-fin-header-badge`, `.vu-fin-line`, `.vu-fin-label`, `.vu-fin-amount`, `.vu-fin-total`,
`.vu-fin-total-label`, `.vu-fin-total-amount`, `.vu-fin-status-row`, `.vu-fin-actions`,
`.vu-fin-btn`, `.vu-fin-btn--outline`; and in the media queries `@media (max-width:1280px)
.vu-quick-info`, the `.vu-quick-info` line at 1100px, `.vu-booking-hero` / `.vu-hero-right` /
`.vu-quick-info` at 768px, and `@media (max-width:560px) .vu-quick-info`.
Kept because the class still appears somewhere: `.vu-hero-meta` (engine JS), `.vu-three-col`,
`.vu-col-actions`, `.vu-progress-rail`, `.vu-client-card*`, `.vu-service-tag*`,
`.vu-urgency-*`, `.vu-hero-state-badge`, `.vu-hero-timer`.

## Concept vs live (QA 1, `00_concept…` vs `11_live_AFTER…`)

| Concept | Live | Why |
|---|---|---|
| Next step says "Visit is in 3 days and nobody is assigned." + "3 nurses in Hà Nội are free…" | Title "Assign Staff", the existing sentence, and a live hint ("The visit time has passed" today) | The six cards move verbatim; "nurses free" needs new server data — a binding non-goal |
| Tabs: Overview · All details · Activity | Every existing tab kept (Overview, Pricing, Clinical, Planning, Tracking, Visit Tasks, Family Updates, Telehealth…) | Non-goal: the tab list stays |
| "Activity & notes" feed under the cards | Not shown | The discussion panel is present at the bottom of the form but **hidden on this page by a rule that predates this phase** (`ops_booking_form.scss`, first block). B3 only allowed deleting rules for dead classes, so I left it. Owner question below. |
| People: client + "Care team: Nobody yet [Assign]" | People shows the client card | Handover: the client card moves to People; care team lives in its card + the glance |
| Initials on a navy circle | The client's own avatar (initial on a coloured circle) | Uses the existing avatar field |
| Values as plain text with a pencil on hover | Plain text at rest, tint on hover, ring on focus; drop-down fields keep their small arrow | Real editors, restyled; no new widget |
| Be Vietnam Pro | The product font | Non-goal |
| Labels short | Real field labels, some with the "?" help mark, some wrap in the 40 % column | Field strings are unchanged by design |
| Tabs never overflow | Nine tabs scroll sideways inside the tab row at 1440 px on cancelled bookings | As specified ("scrollable when they overflow"); no fade added |

## New ledger entries

§5.245 (form class lands on the controller root; order-independent scoping), §5.246 (view
translation terms are whole inline runs; database-level proof), §5.247 (state-system
`!important` display; OWL drops inter-element spaces), §5.248 (QA persona = role, stale
workers; the standard booking action fails for Operations Managers).

## Commits (branch 19.0, not pushed)

- `8dffe916` feat(health_theme): add the Workspace kit for record screens
- `cda3b4a2` feat(health_fieldservice): move the booking screen onto the Workspace kit
- docs commit (this report, evidence, ledger, programme) — see `git log`

## Evidence (`docs/handovers/workspace_ws1_shots/`)

`00_concept_option_b_booking.png`, `01_clone_bk3831_top_1440.png`,
`02a_clone_chip_opened_travel_charge_typed.png`, `02b_clone_after_save_reload_card_stays_open.png`,
`03_clone_more_menu_open.png`, `03b_clone_cancel_asks_confirmation.png`,
`03c_clone_cancel_wizard_opened_then_discarded.png`, `04a_clone_draft_2666.png`,
`04b_clone_assigned_3014.png`, `04c_clone_in_progress_BK1328.png`, `04d_clone_completed_BK1527.png`,
`04e_clone_cancelled_BK2749.png`, `05a_clone_tab_pricing.png`, `05b_clone_tab_family_updates.png`,
`06a_clone_1100px_top.png`, `06b_clone_1100px_rail_below.png`, `06c_clone_820px_top.png`,
`07a_live_BEFORE_client_profile_533.png`, `07b_live_AFTER_client_profile_533.png`,
`08a_clone_vietnamese_bk3831_top.png`, `10_live_BEFORE_bk3831_old_screen.png`,
`11_live_AFTER_bk3831_top_1440.png`, `12_live_more_menu_open.png`,
`12b_live_cancel_confirmation_dismissed.png`, `13a_live_draft_2666.png`, `13b_live_assigned_3014.png`,
`13c_live_in_progress_BK1238.png`, `13d_live_completed_BK1527.png`, `13e_live_cancelled_1456.png`,
`14a_live_1100px.png`, `14b_live_820px.png`, `CONSOLE_AND_CHECKS.md`.

## Not done / open (plainly)

- **Nothing in the handover's definition of done is outstanding.**
- Owner question: the concept shows an "Activity & notes" feed; on this screen the discussion
  panel exists but has been hidden by an older style rule. Showing it again is a one-line
  removal — it changes what staff see, so it waits for a yes.
- Still English for a Vietnamese reader on this screen, all **pre-existing, other modules**:
  tab names Pricing / Visit Tasks / Family Updates / Telehealth, "Staff Overview", the unit
  "min". Some older Vietnamese is poor ("Pay Quote" → "Thu nhập", "Assign Staff" → "Đề xuất
  nhân viên"). Out of scope; worth a translation pass.
- The Legacy Record card's icon (`data-icon="archive"`, from the migration module) has no
  icon rule and draws an empty square — pre-existing.
- The More menu stays open behind the Cancel confirmation dialog until the dialog closes
  (core dropdown behaviour; harmless).

## Kit notes for WS-2 (client screen)

1. **Opt-in is two class names**: `class="ws-workspace"` on the `<form>`; skeleton
   `ws-page > ws-main (+ ws-rail)`. The client profile has its own OWL chrome
   (`ops_client_profile_form`, hero + six stat tiles + action sidebar); WS-2 must decide what
   that chrome keeps — the kit's hero/journey/next are arch markup, so the controller template
   should stop rendering its own hero/tiles for the class, or the page shows two headers.
2. **Scope booking-style overrides as `.o_form_view.<js-class-root>.ws-workspace …`** (§5.245);
   the client profile root is the same element as its js_class class.
3. **Every translatable chip or title must be its own term** (§5.246): block element, icon via
   `data-icon` on `.ws-chip` or via the `.vu-section__icon` + exact-markup msgid pattern. Copy
   `test_08b` verbatim for the client view — it is the test that catches this.
4. **Glance/attention/hint are booking-specific widgets** in health_fieldservice; for WS-2 write
   `ws_client_glance` in the same shape (`BookingFacts`-style helper, `_t` placeholders, money
   read only `if name in record.fields and name in record.data`). The rail CSS
   (`.ws-panel`, `.ws-row.is-quiet/.is-warn/.is-bad`, `.ws-alert--warn/--bad`) is generic.
5. **`ws_fold_tray`** works on any `div[@name]` card with `.vu-card__title`; give each card a
   `name=` and list its fields. A card that ever held a value on the page stays open.
6. **`ws_journey`** takes any selection field (`state_field=`), `steps`, `labels` (English, _t'd
   from the health_theme catalogue — add new labels there with a `ws_journey.js` occurrence),
   `date_fields`, `aliases`. The client journey (Enquiry → First visit → Active → Package) is not
   a single selection field today — WS-2 needs a computed state or a different widget.
7. **Header More**: add `ws-more` to header buttons; no other change. Core small screens keep
   their own menu.
8. **Things that bit, carry forward**: state-system `!important` displays on `.vu-show-on-*`
   (§5.247); OWL strips spaces between elements; the engine's `.tab-pane` card is removed only
   for panes that hold a `.ws-pack`; the old per-page chrome rules (FA tab icons, orange tab
   underline) must be neutralised under the new scope; the client profile ALSO carries the
   old 3-column engine layout (`vu-three-col`, patient form) — keep `.ws-rail` in the engine
   compact list (done in K5).
9. **Test fixtures**: capture the client view's "before" field and header-button tables from
   the live view the same way (`get_combined_arch()` in a shell on the clone) — the client view
   has many more inheriting modules (twin, vitals, care plans, portal, BHYT…); enumerate
   `ir_ui_view WHERE inherit_id = <client ops view id>` first.
