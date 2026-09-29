# WORKSPACE — WS-1: the booking screen, and the Workspace kit

Status: HANDOVER to Opus (written 2026-09-29 by Fable). Programme: `WORKSPACE_PROGRAM.md`.
Visual target: `design-poc/record-screens.html` → **Option B · Workspace**, screen **Booking**
(open the file in Chrome; it is a self-contained page — the option/screen switchers are at the
top). Read first: `docs/strategy/HANDOVER-CONVENTIONS.md` (§1-§4, §8, and the ledger tail —
continue numbering after the last `§5.2xx` entry), then this file.

## 0. Standing rules (state them back in your report)

- **White-label**: the word "Odoo" never appears in anything a user can see (labels, tooltips,
  `_t()` strings, `.po` msgstr). Technical identifiers are fine.
- **Plain copy** in the screen's words ("booking", "visit", "nurse", "client", "Next step",
  "More", "Not filled yet"). No field technical names on screen.
- **Flat mono colours only** (no gradients, no dual-tone). Colours from `--vuf-*` tokens
  (`health_theme/static/src/scss/vu_tokens.scss`) — no new literal hex outside a token block.
- **Icons**: CSS-mask SVG (`.vu-section__icon[data-icon=…]`, sources in
  `health_theme/static/src/img/lucide/`). Never emoji; no NEW font-awesome in markup you write
  (header `<button icon="fa-…">` attributes are core-rendered — leave them).
- **Chatter stays at the bottom, full width.**
- **No business-logic change.** No Python model/field changes, no button `name`/method change,
  no change to any `invisible=`/`groups=`/`readonly=` condition's meaning. This phase moves and
  restyles; it does not change what a user may do or when.
- **Sanctioned edits are exhaustive** (§1). Shared modules are read-only beyond that list.
- Tests: never `carejiox-deploy -t` on the live box (ledger H77 — it stops the service for the
  whole run). Rehearse on a clone (`carejiox_ws1`) with `biz.tenant` rows neutralised (H102),
  `--db-filter=^carejiox_ws1$` on every manual run, suites via `systemd-run` on a spare port per
  conventions §2. Close QA browser tabs before a test run (§5.216). Restart the clone unit after
  any file push (§5.228).
- Browser: chrome-devtools needs a Chrome on 9222 with a scratch profile (§5.215); sign in with a
  `fetch` to `/web/session/authenticate`. Use a QA user whose password you set on the clone; on
  live use a temporary QA user (Operations Manager role) and remove it afterwards (§5.34).
- Version bumps: `health_theme` 19.0.5.3.0 → **19.0.5.4.0**, `health_fieldservice`
  19.0.2.8.2 → **19.0.2.9.0**. No migration needed (views/assets only) unless you find one is.
- Commits on `19.0`, plain-sentence messages in the repo's style, ending
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. **Do not push.**

## 1. Scope

| # | Item | Module | Sanctioned files |
|---|---|---|---|
| K1 | Workspace layout + skin (`ws_workspace.scss`) — generic, opt-in by `class="ws-workspace"` on the `<form>` | health_theme | new `static/src/scss/ws_workspace.scss`; `__manifest__.py` (asset list + version) |
| K2 | `ws_journey` view widget (segmented journey with stage dates) | health_theme | new `static/src/js/ws_journey.js`, `static/src/xml/ws_journey.xml`; manifest |
| K3 | `ws_fold_tray` view widget ("Not filled yet" chips + fold/unfold of empty cards) | health_theme | new `static/src/js/ws_fold_tray.js`, `static/src/xml/ws_fold_tray.xml`; manifest |
| K4 | Header "More" menu: header buttons carrying class `ws-more` render inside one **More** dropdown on desktop | health_theme | new `static/src/js/ws_statusbar_more.js`, `static/src/xml/ws_statusbar_more.xml`; manifest |
| K5 | Engine compat: the compact side-column field rules also cover `.ws-rail` | health_theme | `static/src/scss/vu_form_engine.scss` — ONLY the §10 selector lists that enumerate `.vu-col-summary, .vu-col-actions, .vu-col-1, .vu-col-3` (add `.ws-rail`); nothing else in that file |
| B1 | Booking ops form restructured onto the kit | health_fieldservice | `views/health_fieldservice_order_views.xml` — ONLY the record `view_health_fso_form_ops` (lines ~995-1817). The standard form (~line 90, also uses `vu_progress_rail`) is NOT touched |
| B2 | `ws_booking_glance` widget (At a glance + Needs attention in the right panel) and `ws_booking_hint` widget (one dynamic sentence inside the Next step banner) | health_fieldservice | new `static/src/js/ws_booking_glance.js`, `static/src/xml/ws_booking_glance.xml`; `__manifest__.py` |
| B3 | Booking styles: new rules for the booking page; delete ONLY rules in `ops_booking_form.scss` whose classes no longer appear in ANY arch/template/JS after B1 (grep the whole `addons/` tree per class before deleting) | health_fieldservice | `static/src/scss/ops_booking_form.scss` |
| B4 | Vietnamese for every new string | health_theme, health_fieldservice | `i18n/vi_VN.po` of each (both modules ship `vi_VN.po` — extend it, never add a second catalogue) |
| T | Tests (§5) | both | new `health_fieldservice/tests/test_ws_booking_form.py` (+ `tests/__init__.py`) |

**Non-goals (binding):** the client and contact screens (WS-2/WS-3); the standard FSO form; the
booking list/queue; the PWA; any other `vu_progress_rail` user; fonts (keep the product font);
dark mode; the summary sentence and Ctrl K command box from the concept; smarter hints that need
new server data (e.g. "3 nurses free" — the concept's line is illustrative; do NOT build it);
the tab list itself (all notebook pages stay, same names, same order after Overview).

## 2. Verified plumbing (2026-09-29 — do not re-derive)

**The surface.** The CMS booking screen is `health_fieldservice.view_health_fso_form_ops`
(live view id 5015, `mode=primary`, `inherit_id=False`, `js_class="ops_booking_form"`),
`health_fieldservice/views/health_fieldservice_order_views.xml:995-1817`. Controller
`static/src/js/ops_booking_form.js` (85 lines; chrome template
`static/src/xml/ops_booking_form.xml` → `health_fieldservice.OpsBookingFormView`: breadcrumb
"Dashboard › Booking Queue › <name>" + save indicator, then the form). The controller is not in
scope and does not need changing.

**Current arch, top to bottom:** `<header>` (13 buttons, 954-1047) → `<sheet>`: hidden deps
(1054-1068) → `div.vu-booking-hero` (name, state badge, lifecycle/urgency badges, priority,
service-type tags, created/by, `service_timer` widget; 1073-1142) → `div.vu-quick-info` (5 big
tiles: scheduled, service type, duration, facility, catchment; 1147-1193) →
`<widget name="vu_progress_rail"/>` (1198) → `<notebook>`: page `overview` holding
`div.vu-three-col` with `vu-col-1` (client card, Staff Assignment card, `commission_fees_card`),
`vu-col-2` (Service Details, `<widget name="vu_services_packages"/>`, `location_details_card`),
`vu-col-actions` (6 state-dependent Next Best Action cards + Quick Actions list), then two
alert banners; pages `clinical_notes`, `planning`, `execution`, `tracking`, `cancellation`,
`completion`, `communication` (invisible) → `</sheet>` → `<chatter/>`.

**Every live extension of this view (from `ir_ui_view` on carejiox, inherit_id=5015):**

| View | Module | Anchor it needs — MUST still resolve after B1 |
|---|---|---|
| 5101 | health_invoicing | `//field[@name='currency_id']` (hidden deps); `//header/button[@name='action_check_and_open_quote_if_needed']` (adds **Pay Quote** + **Complete Service & Collect Payment** after it); `//div[@name='draft_create_quote_card']` (attributes + a button after `action_create_and_open_quote` inside it); `//div[@name='draft_confirm_client_card']` (attributes; replaces its `div[contains(@class,'vu-action-card__subtitle')]`; a button before `action_confirm_booking`); `//div[@name='location_details_card']` (Payment Summary card after it); `//div[@name='quote_invoice_card']//field[@name='invoice_state']`; `//div[@name='staff_assignments_card']`; `//button[@name='action_view_all_invoices']` (2 quick actions after it) |
| 5204 | health_redinvoice | `//button[@name='action_view_all_invoices']` (Red Invoice quick action after it) |
| 5209 | advanced_pricing | `//page[@name='overview']` (Pricing page after it) |
| 5594 | health_migration | `//div[@name='location_details_card']` (Legacy Record card after it) |
| 5612 | health_careplan | `//notebook` inside (Visit Tasks page) |
| 5613 | health_family_link | `//notebook` inside (Family Updates page) |
| 5616 | health_telehealth | `//header` inside (Join Video button); `//notebook` inside (Telehealth page) |

So: keep every `name=` on the divs above, keep the class `vu-action-card__subtitle` on the
draft-confirm card's subtitle div, keep `currency_id` in the hidden deps, keep
`action_check_and_open_quote_if_needed` and `action_view_all_invoices` buttons. Things
inserted "after `location_details_card`" (Payment Summary, Legacy Record) must land somewhere
sensible in the new layout — they will, because `location_details_card` sits in the Overview
pack (§3.B).

**Tests that pin this view today:** `health_cms_coverage/tests/test_cms_consolidation.py`
~:94-107 and ~:297-309 — the booking tab pages must exist and render through a lazy
`<widget>`; `action_tele_join` must be in the combined arch. Keep them green.

**Core header mechanics (Odoo 19, server copy
`/odoo/odoo-server/addons/web/static/src/views/form/form_compiler.js:441-475`):**
`compileHeader` compiles each non-field child into a `ViewButton`, wraps each in
`<t t-set-slot="button_N" isVisible="…">`, and hands the slots to `StatusBarButtons`
(`…/form/status_bar_buttons/status_bar_buttons.{js,xml}`). `StatusBarButtons.visibleSlotNames`
filters on `isVisible`. On `env.isSmall` core already renders the first slot + a Dropdown of the
rest; on desktop it renders all slots inline. The compiled `ViewButton` node carries the arch
`class` in its `className` attribute (a quoted string expression) — that is how you detect
`ws-more`.

**The Form Engine** (`health_theme/static/src/js/vu_form_compiler.js`): every native form gets
`.vu-form` on `.o_form_renderer`; `ops_booking_form` is in `VU_NO_HERO_JS_CLASS` (keeps its own
hero — the engine adds `.vu-no-hero`). Skin: `vu_form_engine.scss` (1187 lines; §3 statusbar =
floating white bar, §6 notebook pills, §10 three-column layout incl. compact side-column field
rules ~:900-960, §10b container-query ladder on `container: vuform`). Tokens: `vu_tokens.scss`
(`--vuf-primary`, `--vuf-ink/muted/faint/line/bg/surface`, `--vuf-ok/warn/danger(+-bg)`,
`--vuf-sp-1..7`, `--vuf-r-sm/md/lg/pill`, `--vuf-sh-*`, `--vuf-state-*`).

**`vu_progress_rail`** (`health_theme/static/src/js/vu_progress_rail.js`) has a bug the new
widget must not copy: state `completed_pending_invoice` matches no step, so every step shows
done. Map it onto `completed`.

**Dates available for the journey** (all on `health.fieldservice.order`): `create_date`
(Created), `confirmation_date` (Confirmed, readonly), `assignment_date` (Assigned),
`actual_start_datetime` (In progress), `actual_end_datetime` (Completed). No "closed" date —
show none. States: `draft, confirmed, assigned, in_progress, completed,
completed_pending_invoice, cancelled, closed`.

**Fields the glance/hint widgets read** (all native to the model unless noted):
`state, scheduled_datetime, scheduled_duration, has_staff_assigned, assigned_staff_ids,
lead_staff_id, total_price, currency_id, sale_order_id, invoice_id, urgency_level, deleted,
active`; and, only when `health_invoicing` is installed, `outstanding_amount`,
`total_paid_amount`, `is_invoiced` (view 5101 already adds them to the arch as hidden fields —
read them only `if (name in record.fields)`; never list them in `fieldDependencies`, the model
lacks them without that module).

**Live QA records (carejiox):** BK3831 = id **9645**, `confirmed`, no staff (the screenshot the
owner complained about). Active counts by state: draft 10 (min id 1674), confirmed 38 (877),
assigned 6 (1670), in_progress 4 (1668), completed 915 (728), cancelled 16 (779). Use one of
each for QA.

**Databases** on the box: `carejiox` (master), `carejiox_template`, `hhh` (tenant), plus
`vietuat`, `codex_fb_center_reply` (not served — confirm with `biz.tenant` and the nginx map
before ignoring them). Addons are shared: the moment files are copied, every served database
runs the new JS/SCSS against its OLD arch until it is upgraded — so upgrade master, template
and every live tenant in one sitting (conventions §2).

**i18n:** both modules ship `i18n/vi_VN.po` (health_fieldservice also has stray
`fieldservice.po.backup` and `vi_VN_correctedpo` — not loaded, leave them). Arch strings need a
`model_terms:ir.ui.view,arch_db:` occurrence; JS `_t` strings need `code:` + `#:` occurrence
(§4, §5.58/§5.67). Run `health_base/tests/test_i18n_catalogues.py` after editing.

## 3. Design

### 3.A The kit (health_theme) — generic, product-agnostic, opt-in

**Opt-in contract.** A form joins by `class="ws-workspace"` on its `<form>` arch element and by
using the kit's class names in its sheet. Nothing changes for any form without that class (the
header "More" behaviour is additionally keyed on buttons carrying `ws-more`).

**K1 — layout (`ws_workspace.scss`).** Sheet skeleton the kit styles:

```
<sheet>
  <div class="ws-page">
    <div class="ws-main">
      <div class="ws-hero">…identity…</div>
      <widget name="ws_journey" …/>
      <div class="ws-next">…one visible Next step card…</div>
      <notebook>… page overview: <div class="ws-pack">cards…</div> <widget name="ws_fold_tray" …/> …</notebook>
    </div>
    <div class="ws-rail">…panel cards…</div>
  </div>
</sheet>
<chatter/>
```

- `.ws-page`: grid `minmax(0,1fr) 320px`, gap `--vuf-sp-5`; lift the sheet max-width like
  §10 does for `.vu-three-col`. Container-query on the form width (`vuform`): below ~1100px the
  rail drops under `.ws-main` and lays its cards out `repeat(auto-fill, minmax(260px,1fr))`.
  The rail is `position: sticky; top: var(--vuf-sp-4)` on wide screens (the owner's concept
  pins it; engine §10's "not sticky" note was about the old rails that ran into the chatter —
  sticky here is bounded by `.ws-page`, which ends above the chatter, so it stops before it;
  verify in QA).
- `.ws-hero`: one row — avatar (initials, 48px circle, `--vuf-hero` background) | title line
  (record name, state chip, tags) over a facts line (icon + text items, `--vuf-muted`, wrap) |
  right-aligned small meta ("Created Sep 12, 10:31 by Owner") and the service timer only while
  it is running. No card chrome; sits on the canvas.
- `.ws-next`: flat `--vuf-primary-soft` banner, 44px `--vuf-primary` icon square, eyebrow
  "NEXT STEP" (uppercase 11px, letter-spaced), one bold sentence, one muted hint line, button(s)
  right. Only one child card is ever visible (the arch's `invisible=` already guarantees that).
- `.ws-pack`: masonry — `columns: 2 340px; column-gap: --vuf-sp-4`; children
  `break-inside: avoid; margin-bottom: --vuf-sp-4; display: block; width: 100%`. This is what
  removes the empty space from the owner's 4th screenshot — cards no longer share row heights.
- `.ws-card` (applied to the existing `vu-detail-card` divs as an extra class): white surface,
  1px `--vuf-line`, radius `--vuf-r-md`, padding 16-18px; title row = small uppercase muted label
  with icon. Inside: label | value grid (label ~40%, `--vuf-muted`, 13px; value 13.5-14px
  weight 500). **Read-first fields**: inputs/selects/many2one inside `.ws-card` render with
  transparent background and no border at rest; on hover a `--vuf-bg` tint; on focus the
  engine's focus ring. Empty values show the placeholder "—" in `--vuf-faint`.
- `.ws-rail .ws-panel` cards: same surface; header label uppercase 11px; rows
  `label … value` with hairline separators; `.is-quiet` value = `--vuf-faint` weight 400;
  `.is-warn`/`.is-bad` = `--vuf-warn`/`--vuf-danger`. Alerts = soft-background rows with an
  icon (`--vuf-warn-bg` / `--vuf-danger-bg`).
- Notebook inside `.ws-main`: underline tabs (text, 2px `--vuf-primary` underline on the active
  tab, no pill track), horizontally scrollable when they overflow — override engine §6 only
  under `.ws-workspace`.
- Statusbar under `.ws-workspace`: no floating white card; a transparent right-aligned row
  above the hero (buttons 36px high, radius `--vuf-r-sm`; the first visible button styled
  primary only if it carries `oe_highlight`/`btn-primary`).

**K2 — `ws_journey` widget.** Props (attrs): `steps` (comma states), `labels` (comma, English
source, `_t` each at render — or pass translated labels through arch text, see §3.C),
`date_fields` (comma, same length, empty entry = no date), `state_field` (default `state`),
`aliases` (e.g. `completed_pending_invoice:completed`). Renders one segment per step: 6px bar
(done = `--vuf-primary`, current = primary with a lighter half, future = `--vuf-line`), label
under it (current bold primary), and a small second line: the step's date as a short local
date ("Sep 12") when set, "Next" for the step right after current, else blank. Cancelled: all
segments grey + a `--vuf-danger` chip "Cancelled" at the end. `fieldDependencies` = the
date fields + state field. Right side of the row: muted "Step 2 of 6".

**K3 — `ws_fold_tray` widget.** Arch:
`<widget name="ws_fold_tray" options="{'cards': {'<div name>': ['field_a','field_b'], …}}"/>`
placed in the same container as the cards it governs. Behaviour:
1. A card is **empty** when every listed field is empty: `false/null/''`, numeric `0`,
   monetary `0`, x2many with 0 records, many2one unset.
2. Empty cards get `ws-card--folded` (display:none) — found with
   `this.formRoot.querySelector('[name="<div name>"]')`, where `formRoot` is the closest
   `.o_form_renderer` of the widget's own element (never `document`).
3. The widget renders `Not filled yet` + one chip per folded card: icon `plus`, the card's
   title (read from the card's `.vu-card__title` text — it is already translated), and
   "N fields". Clicking a chip unfolds that card for this record for the rest of the page's
   life (state kept in the widget, keyed by `record.resId`), scrolls it into view and focuses
   its first input.
4. A card that becomes non-empty while editing stays unfolded. A folded card never hides a
   field that is invalid/required (if the record has a validation error on a listed field,
   unfold).
5. Nothing folded → the widget renders nothing.
6. Re-evaluate on every render (`onPatched` + `onMounted`), idempotently (toggle classes only
   when they change).

**K4 — header More.** `ws_statusbar_more.js`:
- `patch(FormCompiler.prototype, { compileHeader(el, params) { const res = super…; for each
  <t t-set-slot> in res's StatusBarButtons: if its compiled button's className expression
  contains 'ws-more', set attribute wsMore="true" on the slot } })`. Wrap in try/catch that
  falls back to the stock result (the engine's compiler patch does the same).
- `patch(StatusBarButtons.prototype, …)` getters `inlineSlotNames` / `moreSlotNames` over
  `visibleSlotNames` split by `this.props.slots[name].wsMore`.
- Template extension of `web.StatusBarButtons`: on desktop, when `moreSlotNames.length`,
  render the inline slots, then one `Dropdown` whose toggle is a secondary button
  "More" + a masked ellipsis icon, content = one `DropdownItem` per more-slot (clone core's
  small-screen markup: `class="'o-dropdown-item-unstyled-button'"`). When no slot has `wsMore`,
  output is byte-identical to core. Small screens keep core behaviour.
- Buttons with `confirm=` must still confirm from inside the dropdown (core's small-screen path
  proves the ViewButton handles it — verify with Cancel Booking in QA).

**K5** — add `.ws-rail` to the §10 compact-field selector lists in `vu_form_engine.scss` so
fields placed in the rail render naked/stacked like the old side columns.

### 3.B The booking form (health_fieldservice)

**Header** (same 13 buttons, same names/conditions/groups; only classes change). Add
`ws-more` to: `action_manual_assign_staff` and `action_start_service` (they are the Next step
banner's button — the header copy moves to More so it is not shown twice),
`action_open_duplicate_booking_wizard`, `action_cancel_booking`,
`action_open_new_booking_wizard`, `action_open_delete_wizard`, `action_open_restore_wizard`,
`action_open_archive_wizard`, `action_open_unarchive_wizard`. Inline remain:
`action_open_reschedule_wizard`, plus the extension buttons (Pay Quote, Complete Service &
Collect Payment, Join Video — no class, they come from other modules and stay inline). Drop
`oe_highlight`/`btn-primary` from buttons that moved to More (a primary-coloured item inside a
menu reads wrong); keep it on nothing else in the header — the banner owns the one primary.

**Sheet** — build exactly this structure (keep every hidden dep field; keep every field that
exists in the current arch — test 3 checks the field set):

```
<form string="Booking" js_class="ops_booking_form" class="ws-workspace">
<header>…as above…</header>
<sheet>
  <div class="oe_button_box" name="button_box"/>
  …hidden deps unchanged (incl. currency_id)…
  <div class="ws-page">
   <div class="ws-main">
    <div class="ws-hero vu-booking-hero">           (keep the old class too only if B3 grep shows another user)
      avatar: <field name="patient_id" widget="many2one_avatar" readonly="1" options="{'no_open': True}"/> styled round 48px
      title line: <field name="name"/> "·" <field name="patient_id" readonly="1" (open → client)/>, state badge (same decorations),
                  lifecycle + urgency badges (same conditions), service-type tag (one span per type, same conditions,
                  masked icon instead of fa), rescheduled tag, priority stars
      facts line: scheduled_datetime · scheduled_duration + " min" · facility_id · patient_catchment_province_id
                  (readonly, no_open; each with a masked icon: calendar, timeline(clock), building, map-pin)
      meta (right): "Created" create_date "by" booking_user_id; the service_timer field with
                  invisible="not service_timer_active and state != 'in_progress'"
    </div>
    <widget name="ws_journey" steps="draft,confirmed,assigned,in_progress,completed,closed"
            labels="Created,Confirmed,Assigned,In progress,Completed,Closed"
            date_fields="create_date,confirmation_date,assignment_date,actual_start_datetime,actual_end_datetime,"
            aliases="completed_pending_invoice:completed"/>
    <div class="ws-next">
      the six action cards moved here VERBATIM (same names, same invisible, same buttons, same
      vu-action-card__subtitle div) — restyled by .ws-next; add inside each card, after the
      subtitle: <widget name="ws_booking_hint"/>. Their "Next Best Action" supertitle text
      becomes "Next step". The cancelled card keeps its text but drops the inline style=""
      (colour now comes from a class).
      Then the two alert banners that sat at the bottom of Overview (Awaiting Invoice,
      Completion Requirements) — same conditions/groups, restyled as .ws-next__note rows.
    </div>
    <notebook>
      <page string="Overview" name="overview">
        <div class="ws-pack">
          Visit card        = the old Service Details card (vu-detail-card ws-card), title "Visit"
          location_details_card (patient_notes moved OUT to the Notes card)
          (invoicing's Payment Summary + migration's Legacy Record land here via their xpaths)
          <widget name="vu_services_packages"/>   (keep it; wrap nothing around it)
          staff card        name="care_team_card", title "Care team" (same 3 fields)
          commission_fees_card, title "Pricing": service_fee_vnd, commission_due_to,
                              commission_percentage, commission_duration, commission_amount, total_price
          additional_charges_card, title "Additional charges": travel/urgency/equipment/after_hours/parking
          notes_card, title "Notes": patient_notes (nolabel, full width)
        </div>
        <widget name="ws_fold_tray" options="{'cards': {
            'care_team_card': ['assigned_staff_ids','lead_staff_id','assigned_doctor_ids'],
            'commission_fees_card': ['service_fee_vnd','commission_due_to','commission_percentage','commission_duration','commission_amount','total_price'],
            'additional_charges_card': ['travel_charge','urgency_charge','equipment_charge','after_hours_charge','parking_charge'],
            'notes_card': ['patient_notes']}}"/>
      </page>
      …every other page unchanged, same order…
    </notebook>
   </div>
   <div class="ws-rail">
     <div class="ws-panel">  <widget name="ws_booking_glance" mode="glance"/>  </div>
     <div class="ws-panel">  People: the existing client card block (vu-client-card, unchanged fields/buttons,
                             restyled compact: name, phone, address, ID·age, "View full profile") </div>
     <widget name="ws_booking_glance" mode="attention"/>   (renders its own panel, or nothing)
     <div class="ws-panel ws-panel--links"> "Shortcuts": the Quick Actions buttons moved VERBATIM
                             (action_open_client_form … action_open_lead_dashboard, vu_staff_sheet widget,
                             assignment_count field) — redinvoice/invoicing insert after action_view_all_invoices </div>
   </div>
  </div>
</sheet>
<chatter reload_on_follower="True"/>
</form>
```

Notes:
- `patient_id` appears several times — allowed; keep the existing
  `context="{'form_view_ref': 'health_base.view_health_patient_form'}"` on the clickable one.
- The client card previously lived in the Overview page; it now lives in the rail, i.e. on
  every tab. That is intended (People always visible).
- The `vu_quick_info` tiles are removed (their five values now live in the hero facts line).
- `vu_progress_rail` is removed from THIS view only.

**B2 — `ws_booking_glance` widget** (`mode` attr: `glance` | `attention`; `fieldDependencies`
= the native fields in §2). All strings `_t`. Relative day text: "Today", "Tomorrow",
"In N days", "Yesterday", "N days ago" (calendar days in the user's tz).

`glance` rows (label → value, class):
| Row | Value | Class |
|---|---|---|
| Visit | relative day + time, e.g. "In 3 days · 05:30" | `is-warn` if state in (draft, confirmed) and no staff and 0 ≤ days ≤ 3 |
| Staff | lead staff name, "+N" for others; "Nobody yet" | `is-warn` when none and state in (confirmed, assigned) |
| Duration | "2 h" / "90 min" | — |
| Price | total_price formatted with currency; "0 ₫" | `is-quiet` when 0 |
| Paid | total_paid_amount (only if the field exists and is_invoiced) | `is-quiet` when 0 |
| Outstanding | outstanding_amount (only if the field exists) | `is-bad` when > 0, row hidden when 0 |

`attention` rules (each one sentence; panel hidden when none):
1. warn — no staff, state `confirmed`, visit within 3 days (or past): "Nobody assigned and the
   visit is in N days." / "…the visit is today." / "…the visit time has passed."
2. warn — state not in (draft, cancelled) and total_price == 0: "The price is 0 ₫. Check the
   quote before the visit." (currency symbol from the record)
3. bad — outstanding_amount > 0 and state in (completed, completed_pending_invoice, closed):
   "N ₫ is unpaid."
4. warn — state `in_progress` and scheduled end (scheduled_datetime + duration) passed by more
   than 30 minutes: "The visit is running past its planned end."

`ws_booking_hint` (inside each Next step card): one muted line, state-aware, e.g. confirmed:
"Visit in 3 days · nobody assigned yet"; assigned: "Starts in 2 h" / "Due to start now";
draft: "Created 2 days ago"; others: nothing. Pure JS from the same fields.

**B3 — styles.** Booking-only rules in `ops_booking_form.scss` under
`.ops-booking-form-page .ws-workspace` (hero avatar size, service tag colours from
`--vuf-state-*`/tokens, hint line). Remove dead rules only after the grep in §1 B3; list every
removed selector block in the report.

### 3.C Copy (English source → Vietnamese; confirm Vietnamese terms against
`health_base/i18n/vi_VN.po` and `health_fieldservice/i18n/vi_VN.po` and stay consistent)

| English | Vietnamese (proposal) |
|---|---|
| Next step | Bước tiếp theo |
| More | Thêm |
| Not filled yet | Chưa điền |
| %s fields / 1 field | %s trường / 1 trường |
| At a glance | Tổng quan nhanh |
| Needs attention | Cần chú ý |
| People | Người liên quan |
| Shortcuts | Lối tắt |
| Visit / Care team / Pricing / Additional charges / Notes | Lượt thăm / Nhóm chăm sóc / Giá / Phụ phí / Ghi chú |
| Today / Tomorrow / Yesterday / In %s days / %s days ago | Hôm nay / Ngày mai / Hôm qua / Sau %s ngày / %s ngày trước |
| Nobody yet | Chưa có ai |
| Step %s of %s | Bước %s / %s |
| Created, Confirmed, Assigned, In progress, Completed, Closed, Cancelled | reuse the existing state translations |
| the four attention sentences and the hints | translate in the same plain register |

## 4. Safety rails
1. Every anchor in the §2 extension table resolves (test 1) and every inherited view still
   applies on the combined arch (test 2).
2. The set of `<field name>` values in the combined arch after B1 ⊇ the set before (capture the
   "before" set from the live view as a committed fixture list in the test). Nothing silently
   stops loading.
3. Every header button name present before is present after, with identical `invisible`,
   `groups`, `confirm` attributes (test 4).
4. No Python outside `tests/` changes; `git diff --stat` in the report proves it.
5. The kit is inert without `ws-workspace` / `ws-more`: the standard FSO form and one other
   native form (e.g. a res.partner form) look unchanged in QA (screenshot before/after).
6. SCSS: no `min()`/`max()` with mixed units in plain properties (Sass intercepts them — see
   deployment memory; declare as custom properties). After deploy, confirm the backend bundle
   compiled: `curl -sL localhost:8069/web/assets/…/web.assets_web.min.css | head -c 300` must
   not start with a CSS error message.

## 5. Tests (numbered — `health_fieldservice/tests/test_ws_booking_form.py`,
`@tagged('post_install', '-at_install')`)
1. Each anchor xpath from §2 finds exactly ≥1 node in `view_health_fso_form_ops`'s own arch.
2. `get_combined_arch()` succeeds and contains: `action_prepay_quote`, `action_tele_join`,
   `action_open_red_invoice`, page names `pricing`, `visit_tasks_ops`, `family_updates_ops`,
   `telehealth_ops`, divs `payment_summary_card`, `legacy_audit_card` (each only if its module
   is installed — check `ir.module.module`).
3. Field-set superset (§4.2) against the committed "before" list.
4. Header buttons: names + `invisible`/`groups`/`confirm` identical to the committed "before"
   table; the nine `ws-more` buttons carry the class; `oe_highlight` gone from them.
5. The form has `class` containing `ws-workspace`; the sheet contains exactly one `ws-page`,
   one `ws-main`, one `ws-rail`, one `ws_journey` widget, one `ws_fold_tray` widget whose
   `options` card keys all exist as `div[@name]` in the arch and whose field names all exist
   on the model.
6. `vu_progress_rail` and `vu-quick-info` absent from this view; still present in the standard
   form (non-goal guard).
7. The pre-existing `health_cms_coverage` consolidation tests pass unchanged.
8. i18n: `health_base` `test_i18n_catalogues` (G1/G1b/G1c/G2/G2b) green with the new entries.
9. Source gate: no `"Odoo"` in any new/changed user-visible string (grep the new JS/XML/po
   msgstr in a test, `TestSourceGates` style).
Run: full `health_fieldservice`, `health_theme`, `health_cms_coverage`, `health_invoicing`
suites on the clone. Pre-existing failures: list them with evidence that they fail on a
clone WITHOUT your change too.

## 6. Browser QA (chrome-devtools; clone first, then live) — evidence to
`docs/handovers/workspace_ws1_shots/`
Real path every time: sign in → left menu **Operations › Bookings** → the booking queue → click
the booking row. Never a deep link. For each, a 1440px screenshot, and the console log:
1. BK3831 (confirmed, no staff) — hero, journey (Created/Confirmed dated), Next step "Assign
   staff" with the hint, rail At a glance (Visit warn, Staff "Nobody yet"), Needs attention,
   "Not filled yet" chips for Care team / Additional charges / Notes (and Pricing if empty).
   Compare side by side with the concept (Option B · Booking) — list every visible difference
   and why.
2. Click the "Additional charges" chip → card opens, first input focused; type 50,000 in
   Travel charge → save → reload → card is open because it is no longer empty. Then set it back
   to 0 and save (leave the record as found; state the before/after values).
3. The More menu open; Cancel Booking inside it asks for confirmation (dismiss it — do NOT
   cancel a live booking; on the clone, confirm once and restore the state after).
4. A draft, an assigned, an in-progress, a completed and a cancelled booking — one shot each
   (journey + Next step + attention correct for each state; completed_pending_invoice if one
   exists).
5. Tabs: Pricing (advanced_pricing), Visit Tasks, Family Updates, Telehealth open and load.
6. Width 1100px and 820px: rail drops under the main column; no horizontal scroll.
7. Standard FSO form and one res.partner form unchanged (safety rail 5).
8. A Vietnamese-language QA user: the new strings read Vietnamese.
Pixel pass (standing rule): check padding/alignment/colour consistency over several iterations
yourself before calling it done — label baselines line up across cards, chip heights equal,
no card touching another, no text clipped.

## 7. Deploy (one sitting)
1. Clone `carejiox` → `carejiox_ws1` (+ filestore; neutralise `biz.tenant`, jobs off per H78),
   private addons path, run §5 there, QA §6 1-8 there.
2. Backup live: `pg_dump -Fc` of `carejiox`, `carejiox_template`, `hhh` → `/var/backups/ws1/`.
3. `scp` both modules → `carejiox-deploy -d -m health_theme,health_fieldservice` (master; note
   `-u health_theme` cascades to its dependents — expect a long run), then
   `-D carejiox_template`, then `-D hhh` (and any other live tenant). All before you stop.
4. Verify: `/web/login` 200 on carejiox.com and hhh.carejiox.com; bundle compiled (§4.6); live
   QA §6 1, 3 (dismiss only), 4, 6 on carejiox.com; hhh booking screen opens.
5. Drop the clone and its filestore (§5.218).

## 8. Report back (write to `docs/handovers/WORKSPACE_WS1_REPORT.md`, commit, and paste)
Per test: PASS/FAIL with the assertion. Suite counts. The before/after field and button tables.
Every deviation from this doc, with why. Removed SCSS selectors. Concept-vs-live differences
from QA 1. New ledger entries you appended to HANDOVER-CONVENTIONS §5. Commit hashes. The
evidence folder listing. Anything the kit needs changed for the client screen (WS-2) —
concrete, so the next handover can use it.
