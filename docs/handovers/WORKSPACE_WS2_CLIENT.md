# WORKSPACE — WS-2: the client screen on the Workspace kit

Status: HANDOVER to Opus (written 2026-09-29 by Fable, after WS-1 reported and was reviewed).
Programme: `WORKSPACE_PROGRAM.md`. Visual target: `design-poc/record-screens.html` →
**Option B · Workspace**, screen **Client**. Read first: `HANDOVER-CONVENTIONS.md` (incl. the
WS-1 ledger entries §5.245-§5.248), `WORKSPACE_WS1_BOOKING.md` (the kit's contracts — K1-K5 are
reused as-is), `WORKSPACE_WS1_REPORT.md` (especially "Notes for WS-2"), then this file.

## 0. Standing rules
Identical to WS-1 §0 (white-label, plain copy, flat tokens, masked SVG icons, chatter bottom,
no business-logic change, exhaustive sanctions, clone rehearsal, H77/H102/§5.215/§5.216/§5.228,
commit on 19.0 with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`, do NOT push).
Version bumps: `health_fieldservice` 19.0.2.9.0 → **19.0.2.10.0**, `health_crm` 19.0.1.10.1 →
**19.0.1.11.0**, `health_invoicing` 19.0.1.3.3 → **19.0.1.4.0**, `health_theme` 19.0.5.4.0 →
**19.0.5.5.0** only if you touch it.

**Reviewer's fix already live (do not undo):** commit `e650506b` — the booking glance price is
`service_fee_vnd + total_price` (base_price is 0 on every booking) and the zero-price warning
fires only in `confirmed`/`assigned`.

## 1. Scope

| # | Item | Sanctioned files |
|---|---|---|
| C0 | **Show the notes & history feed at the bottom** of the booking and client screens (owner-approved concept shows it; it was hidden in May 2026 only because it then sat in a side column — "steals width"). Remove the two `display:none !important` chatter rules; add `<chatter/>` to the client arch (it has none; `res.partner` is a mail thread). Style it to the page's content width, full width, below `.ws-page`. | `health_fieldservice/static/src/scss/ops_booking_form.scss` (lines ~6-14 only), `ops_client_profile_form.scss` (the matching block), `views/ops_client_profile_form_views.xml` |
| C1 | Client ops form restructured onto the kit (`class="ws-workspace"`), hero in the arch, Next step banner, packed Overview cards with fold tray, right rail | `health_fieldservice/views/ops_client_profile_form_views.xml` — ONLY `view_health_patient_form_ops` |
| C2 | Controller chrome: stop drawing the old identity header (`ph-header`), the six KPI tiles (`ph-kpis`) and the right sidebar (`ops-cp-sidebar` + `ops-content-with-sidebar` wrapper). Keep the breadcrumb bar and the save indicator. Controller JS methods stay (other modules patch them). | `health_fieldservice/static/src/xml/ops_client_profile_form.xml`; `static/src/js/ops_client_profile_form.js` only if a now-unused call must go (e.g. `_loadProfileData` on mount — keep it if anything still reads `profileState`) |
| C3 | Client widgets: `ws_client_glance` (mode `glance` / `attention`), `ws_client_next` (Next step banner content), `ws_client_visits` (recent visits list), `ws_client_shortcuts` (Shortcuts panel from a registry) — one shared data loader | new `health_fieldservice/static/src/js/ws_client_panels.js` + `static/src/xml/ws_client_panels.xml`; manifest |
| C4 | Data: extend the read-only `res.partner.get_client_profile_data` with `next_visit` (the soonest booking in `confirmed`/`assigned` with `scheduled_datetime >= now`: `{id, name, scheduled_datetime}` or `false`) and `last_visit` (latest `completed`/`completed_pending_invoice`/`closed`: same shape). No writes, no new stored fields. | `health_fieldservice/models/res_partner.py` (that method only) |
| C5 | health_crm: the Main Contact picker moves from the controller template into the rail's People panel via its arch extension; its controller-template extension is deleted | `health_crm/views/ops_client_inherit.xml` (view 5428), delete `health_crm/static/src/xml/ops_client_profile_header.xml` + `static/src/js/ops_client_profile_header.js` and their two lines in `health_crm/__manifest__.py`; `health_crm/i18n/vi_VN.po` (check the real catalogue filename) |
| C6 | health_invoicing: its Shortcuts entries (package purchase with the rich dialog, create invoice, invoices, packages, payments) register into the `ws_client_shortcuts` registry; `client_package_patch.js` stays only if the controller method is still reachable, otherwise it is replaced by the registry entry | `health_invoicing/static/src/js/client_package_patch.js`, manifest, its `vi_VN.po` |
| C7 | Client styles; retire dead `ph-*`/`ops-cp-sidebar*`/`ph-kpi*` rules — BUT `health_crm/static/src/xml/crm_contact_form.xml` + `crm_contact_form.scss` also use `ph-*` classes (the CRM contact screen, WS-3): grep every class across `addons/` before deleting; shared ones stay | `health_fieldservice/static/src/scss/ops_client_profile_form.scss`, `ops_client_profile.scss` |
| C8 | Vietnamese for every new string | the four modules' `vi_VN.po` |
| T | Tests | new `health_fieldservice/tests/test_ws_client_form.py` |

**Non-goals (binding):** the CRM contact screen (WS-3); the client LIST; the booking screen
beyond C0; reordering or grouping the client's 18 tabs (keep all, same order — underline tabs
scroll); a client stage bar (**no journey on the client screen** — the client has no stage
field; the concept's stages were illustrative, owner is told so); satisfaction ratings (the
stat is hard-coded 0 today — do not show it); new stored fields; the booking/visit list in the
Bookings tab.

## 2. Verified plumbing (2026-09-29 — do not re-derive)

**Surface.** `health_fieldservice.view_health_patient_form_ops` (`res.partner`, priority 0,
`js_class="ops_client_profile_form"`, arch class `ops-client-profile-form`),
`views/ops_client_profile_form_views.xml:5-475`, opened by
`action_ops_client_profile_form`. Controller `static/src/js/ops_client_profile_form.js`
(150 lines): on mount calls `res.partner.get_client_profile_data([id])` →
`{profile:{id,name,initials,patient_code,phone,email,address,age_gender,patient_status,
is_vip,is_referrer,category_name}, stats:{total_visits,active_packages,total_spent,
outstanding,satisfaction(=0 always),referrals}, …timeline of bookings with id,name,
date_label…}` (`models/res_partner.py` ~:200-290). Chrome template
`static/src/xml/ops_client_profile_form.xml` (207 lines): breadcrumb → `ph-header`
(identity + call/SMS/email) → `ph-kpis` (6 tiles) → `ops-content-with-sidebar` [form container
| `aside.ops-cp-sidebar` with Create Booking + 7 quick actions calling `doPartnerAction(method)` /
`openPackagePurchase()`].

**Arch today:** header (Delete, Restore, Archive, Unarchive); hidden `active, deleted,
patient_status, is_patient, source_type`; sheet: hidden `name, patient_code_display,
age_display`; banners (deleted, archived, **allergies** — clinical safety, keep prominent);
notebook pages `profile_overview` (Personal Information 11 fields | Other Information 11
fields), `bookings_journey` (4 stat tiles `bj-journey-stats`, `vu_booking_timeline` widget,
`booking_ids` list, hidden `timeline_html`), `address_info`, `intake_notes`,
`insurance_billing`, `active_packages`, `healthcare_relationships`, `clinical_notes`,
`financial_summary` (4 tiles + `invoice_ids`). No `<chatter/>`.

**Live extensions (inherit_id = this view, carejiox):**

| View | Module | Anchor that MUST still resolve |
|---|---|---|
| 5102 | health_invoicing | `//page[@name='active_packages']//p[contains(@class,'text-muted')]` (replaced by package stats + `vu_active_packages`); `//page[@name='financial_summary']//div[@class='bj-bookings-section']` (exact class string! package summary + recent payments after it) |
| 5428 | health_crm | `//sheet/div[@class='alert alert-danger']` (exact class; a `d-none` div with `allowed_main_contact_ids`, `main_contact_phone`, `main_contact_id` before it) — **you rewrite this view in C5** |
| 5530 | health_twin | `//notebook` inside (Trends) |
| 5531 | health_cms_clinical | `//notebook` inside (Alert Thresholds, Consents) |
| 5536 | health_bhyt | `//notebook` inside (BHYT) |
| 5611 / 5614 / 5615 / 5617 / 5618 | careplan / family_messages / self_booking / condition / portal | `//notebook` inside (Care Plans, Family, Booking Links, Diagnoses, Portal Access) |

Note `//sheet/div[@class='alert alert-danger']` is a DIRECT child of `<sheet>` with the exact
class string — there are two such divs today (deleted banner, allergies banner); the xpath
takes the first. After C1 the banners may move inside `.ws-main`; since you rewrite 5428 in
C5 anyway, point it at the new People panel (`//div[@name='people_panel']`) and drop the
dependency on the banner.

**JS extensions of the controller:** `health_crm/static/src/js/ops_client_profile_header.js`
(adds `Field` to the controller's components + `mainContactFieldInfo` getter) and
`…/xml/ops_client_profile_header.xml` (t-inherit of `OpsClientProfileFormView`, xpath
`//div[hasclass('ph-actions')]` before). **If C2 removes `.ph-actions` and this template
extension still loads, the whole backend's templates fail to build** — C2 and C5 ship in the
same file copy, in one `-d` invocation. `health_invoicing/static/src/js/client_package_patch.js`
patches `openPackagePurchase()` to open `PackageWizardDialog` (`patientId`, `onDone`).

**Where the shortcut methods live** (an arch `type="object"` button naming a method the model
lacks fails view validation — hence the registry in C3/C6):
`action_open_quick_booking_owl`, `action_open_recurring_booking`, `action_view_fso_orders`,
`get_client_profile_data` → health_fieldservice; `action_view_appointments` → health_base;
`action_create_standard_invoice`, `action_view_invoices`, `action_view_service_packages`,
`action_view_payment_transactions`, `action_create_prepaid_package` → health_invoicing.

**Fields:** `commission_due_to` is a Selection on `res.partner` (health_base:181) labelled
"Commission Duration" in this arch — a wrong label; fix it to the field's own string
(drop the `string=` override). `last_visit_date` is computed+stored in health_fieldservice;
`next_visit_date` is a plain base field nobody maintains reliably — do NOT show it, use C4's
`next_visit`. `registration_date` = "Client since". `avatar_128` gives the initials avatar
(same look as the booking hero's `many2one_avatar`).

**Tests pinning this view:** `health_cms_coverage/tests/test_cms_consolidation.py` (client
tabs exist and render via lazy widgets) and `health_cms_clinical/tests/test_cms_clinical.py`
(read it — it references this view). Keep both green.

**QA records (carejiox):** client **533** (WS-1 used it for before/after shots); Bùi T from
the owner's screenshot (search `name ilike 'Bùi T'`, code `01 001512026`, outstanding 1.1M);
find one with an allergy, one archived, one with an active package, one with no bookings.

## 3. Design

**Arch skeleton** (the kit's K1 classes; mirror WS-1's booking arch and §5.245 scoping):

```
<form string="Client Profile" js_class="ops_client_profile_form" class="ops-client-profile-form ws-workspace">
<header> Delete / Restore / Archive / Unarchive — all four get class ws-more </header>
hidden deps unchanged
<sheet>
 hidden name/patient_code_display/age_display
 <div class="ws-page">
  <div class="ws-main">
   <div class="ws-hero">
     avatar_128 (widget image, 48px round) | title: name (readonly display), patient_code_display chip (mono),
     status chip from patient_status (Active green / Inactive grey), patient_category_id chip, "Referrer" chip
     when is_referrer, "Deceased" chip when deceased | facts: phone · vietnamese_address (1 line, ellipsis,
     full text in title attr) · email · age_display + gender_id
     (each chip its own translation term — §5.246)
   </div>
   deleted / archived / allergies banners (same conditions; allergies styled as a --vuf-danger-bg strip
   with an alert icon — never folded, never moved below the fold)
   <div class="ws-next"><widget name="ws_client_next"/></div>
   <notebook>
    <page name="profile_overview" string="Overview">   (string changes from "Profile Overview")
      <div class="ws-pack">
        personal_card  "Personal"   : title, first_name, middle_name, last_name, vietnamese_name, birth_date, gender_id, deceased
        contact_card   "Contact"    : phone (required stays), mobile (invisible stays), email
        care_card      "Care"       : patient_category_id, catchment_province_id (required), primary_facility_id (same domain),
                                      intake_referring_doctor_id, source_type, source_details, referral_source (same invisibles)
        identity_card  "Identity"   : national_id, profession (string Occupation), ethnicity
        commission_card "Commission": commission_due_to
        <widget name="ws_client_visits"/>   (Recent visits card)
      </div>
      <widget name="ws_fold_tray" options="{'cards': {'identity_card': [...], 'commission_card': ['commission_due_to']}}"/>
    </page>
    every other page unchanged, same order, same names
   </notebook>
  </div>
  <div class="ws-rail">
    <widget name="ws_client_glance" mode="glance"/>
    <div class="ws-panel" name="people_panel"> People: client phone with Call / SMS / Email icon buttons
         (tel:/sms:/mailto: — reuse the controller's existing behaviour; plain <a> is fine);
         health_crm inserts the Main Contact picker + phone here (C5) </div>
    <widget name="ws_client_glance" mode="attention"/>
    <widget name="ws_client_shortcuts"/>
  </div>
 </div>
</sheet>
<chatter/>
</form>
```

**`ws_client_next`** (one card, same look as the booking banner): rules in order, first match:
1. `stats.outstanding > 0` → icon money, "%s is unpaid." / hint "Across past visits." /
   button "View invoices" (runs the registry entry `invoices` if registered, else hidden).
2. no `next_visit` and `patient_status == 'active'` → "No visit is booked." / hint
   "Last visit %s." (relative, or "No visits yet.") / primary button "New booking"
   (`action_open_quick_booking_owl`).
3. `next_visit` → "Next visit %s." (weekday, date, time) / hint booking name / buttons
   "Open booking" (open that FSO in the ops booking form — reuse
   `health.fieldservice.order.action_open_ops_booking_detail` via orm call on that id) and
   "New booking".
4. inactive client, nothing else → "This client is inactive." / "New booking".

**`ws_client_glance`** `glance` rows: Visits (`total_visits`; quiet when 0), Last visit
(relative day), Next visit (relative day + time, "None booked" quiet), Client since
(`registration_date`, month + year), Spent (`total_spent`, quiet 0), Outstanding (hidden 0,
`is-bad` > 0), Packages (`active_packages`, quiet 0), Referrals (quiet 0). Money formatted
with the company currency like the booking widget (reuse its formatter — move it to a shared
module in health_fieldservice if needed, sanctioned). `attention` rules: allergies set → bad
"Has allergies: %s" (truncate 80 chars); `insurance_expiry` < today → warn "Insurance expired
on %s."; outstanding > 0 → bad "%s is unpaid."; phone missing → warn "No phone number."

**`ws_client_visits`**: last 5 bookings from the loader's timeline (or C4 if the timeline lacks
state — extend C4 to return `recent_visits: [{id,name,scheduled_datetime,service_type_label,
state,state_label}]`, 5 rows, newest first). Row: mono booking name, date, service, state chip
(same colours as the booking hero); click → open the booking in the ops booking form. Footer
link "All bookings" → the Bookings tab (switch notebook page) — if switching tabs from a widget
is not clean, call `action_view_fso_orders` instead. Empty → "No visits yet." with "New
booking".

**Shared loader:** one `get_client_profile_data` call per record load, memoised by
`resId` + record `write_date`, reused by all four widgets and invalidated by the controller's
existing `saveButtonClicked` reload. No widget calls the RPC on its own.

**`ws_client_shortcuts`**: `registry.category("ws_client_shortcuts")` entries
`{key, label (_t), icon, sequence, run(env, partnerId), isAvailable?(env)}`. health_fieldservice
registers: `new_booking` (quick booking), `recurring` (recurring booking), `bookings`
(`action_view_fso_orders`), `appointments` if different. health_invoicing registers:
`package` (opens `PackageWizardDialog` in patient mode, `onDone` reloads the record + loader),
`invoice_new`, `invoices`, `packages`, `payments`. Methods are called with the orm and the
returned action is run with the action service, exactly like `doPartnerAction` (keep its
friendly warning on failure).

**Controller chrome (C2):** after removal the page is: breadcrumb bar → form container. The
controller's `profileState`/`_loadProfileData` may stay if the shared loader reuses it; if the
loader lives in the widgets, remove the controller's mount-time RPC so the data is fetched once.

**Bookings / Financial tabs:** restyle `.bj-journey-stats` under `.ws-workspace` into the slim
stats line (label over value, hairline separators, no big icons) — CSS only; the invoicing
xpath needs the `bj-bookings-section` class string untouched.

**C0 feed:** below `.ws-page`, the kit's content width, one white card, composer on top. On the
booking screen verify the chatter's "Send message / Log note / Activities" works and that the
sticky rail stops above it.

**Copy → Vietnamese** (check existing terms first): Overview / Tổng quan, Personal / Cá nhân,
Contact / Liên hệ, Care / Chăm sóc, Identity / Giấy tờ, Commission / Hoa hồng, Recent visits /
Lượt thăm gần đây, All bookings / Tất cả lịch hẹn, No visits yet / Chưa có lượt thăm,
No visit is booked / Chưa có lịch hẹn, Next visit %s / Lượt thăm tiếp theo %s, New booking /
Đặt lịch mới, Open booking / Mở lịch hẹn, View invoices / Xem hóa đơn, %s is unpaid / Còn nợ %s,
Client since / Khách hàng từ, Spent / Đã chi, Referrals / Giới thiệu, Has allergies / Có dị ứng,
Insurance expired on %s / Bảo hiểm hết hạn ngày %s, No phone number / Chưa có số điện thoại,
This client is inactive / Khách hàng không còn hoạt động, Call / Gọi, Email.

## 4. Safety rails
1. Every §2 anchor resolves; every inheriting view applies (combined arch builds).
2. Field set of the combined arch after ⊇ before (commit the "before" list, as WS-1 did).
3. Header buttons: names/invisible/groups identical; all four carry `ws-more`.
4. The backend template bundle builds: after deploy, load any backend page and confirm no
   "Missing template"/"Invalid XPath" error in the console, and the client screen opens.
5. Allergies banner visible without scrolling on a client with allergies (QA screenshot).
6. `git diff --stat`: Python changes limited to `get_client_profile_data` and tests.
7. SCSS rules from WS-1 §4.6 (compiler traps, flat colours).

## 5. Tests (`test_ws_client_form.py`, `@tagged('post_install','-at_install')`)
1. Anchors of §2 resolve on the own arch (5102's two, and C5's new people_panel).
2. Combined arch contains every extension page (`twin_trends_ops`, `vitals_thresholds_ops`,
   `consents_ops`, `bhyt_ops`, `careplans_ops`, `family_ops`, `booking_links_ops`,
   `diagnoses_ops`, `portal_access_ops` — each if its module is installed) and
   `main_contact_id` inside `div[@name='people_panel']`.
3. Field-set superset vs the committed "before" list.
4. Header buttons table identical; `ws-more` on all four.
5. Skeleton: `ws-workspace` class, one ws-page/ws-main/ws-rail, the four client widgets,
   `ws_fold_tray` keys exist as `div[@name]` and fields exist on res.partner, `<chatter`
   present, no `string="Commission Duration"`.
6. `get_client_profile_data` returns `next_visit`/`last_visit` (and `recent_visits` if added):
   fixture client with one future confirmed booking and one completed booking → correct ids;
   a client with none → `False`/`[]`. (Fixtures per conventions §6; delete after.)
7. The chrome template no longer contains `ph-kpis`, `ph-header`, `ops-cp-sidebar`; no asset
   in any installed module t-inherits `OpsClientProfileFormView` with an xpath on a class that
   no longer exists (grep test over `addons/*/static/src/xml`).
8. The two booking/client chatter-hide rules are gone (source test).
9. i18n G1/G2 green; the 8b-style database check for the new terms; no "Odoo" in new strings.
10. Existing `health_cms_coverage` and `health_cms_clinical` tests unchanged and green.
Suites: health_fieldservice, health_crm, health_invoicing, health_cms_coverage,
health_cms_clinical, health_theme on the clone.

## 6. Browser QA (clone, then live) → `docs/handovers/workspace_ws2_shots/`
Real path: left menu **Operations › Clients** → client list → click the row.
1. Bùi T (owner's screenshot) at 1440: hero, Next step "1.1M ₫ is unpaid" (or whatever is true
   now), rail glance, People with Main Contact picker (change it on the clone and save; on live
   open the dropdown only), Needs attention, Shortcuts. Side-by-side with the concept.
2. Client with allergies — banner above the fold.
3. Client with no bookings; an inactive/archived client; a client with an active package
   (Package shortcut opens the rich dialog — close it without buying).
4. Fold tray: open "Identity" chip, fill national ID on the clone, save, reload → stays open.
5. More menu (Delete/Archive) — open, dismiss.
6. Recent visits row → opens the booking screen; back.
7. Tabs: Bookings (slim stats line), Financial Summary (invoicing's additions render), Care
   Plans, Diagnoses, Trends, BHYT open.
8. Notes feed at the bottom on the client AND on booking BK3831: post a log note on the CLONE
   only; on live just show it rendered.
9. 1100px and 820px; the CRM contact screen unchanged (WS-3 not started); a Vietnamese user.
Pixel pass as in WS-1.

## 7. Deploy
As WS-1 §7: clone `carejiox_ws2`, backups to `/var/backups/ws2/`, then ONE copy of all touched
modules and `carejiox-deploy -d -m health_fieldservice,health_crm,health_invoicing[,health_theme]`
on the master, then `-D carejiox_template`, then `-D hhh` (and any live tenant), switch the
template's jobs back off (WS-1 saw them come back on), `/web/login` 200 on each host, bundle
compiled, live QA §6 1, 2, 5, 7, 8 (view only), 9. Drop the clone + filestore.

## 8. Report → `docs/handovers/WORKSPACE_WS2_REPORT.md` (commit + paste)
As WS-1 §8, plus: the Shortcuts registry entries per module, the loader's call count per page
load (must be 1), and concrete kit notes for WS-3 (CRM contact: `crm_contact_form.xml` shares
`ph-*` classes — list which).
