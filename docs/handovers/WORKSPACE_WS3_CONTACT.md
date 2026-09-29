# WORKSPACE — WS-3: the contact screen on the Workspace kit (closes the programme)

Status: HANDOVER to Opus (written 2026-09-29 by Fable after WS-2 reported and was reviewed).
Programme: `WORKSPACE_PROGRAM.md`. Visual target: `design-poc/record-screens.html` →
**Option B · Workspace**, screen **Contact**. Read first: `HANDOVER-CONVENTIONS.md` (ledger
tail incl. §5.245-§5.254), `WORKSPACE_WS1_BOOKING.md` (kit contracts K1-K5),
`WORKSPACE_WS1_REPORT.md`, `WORKSPACE_WS2_CLIENT.md`, `WORKSPACE_WS2_REPORT.md` (its "Notes
for WS-3" are binding input), then this file.

## 0. Standing rules
Identical to WS-2 §0. Version bumps: `health_crm` → next minor after WS-2's
(read the manifest), `health_theme` → next minor if touched (K-fixes below touch it),
`health_fieldservice` → next patch (X1/X2), `health_web_leads` / `health_google_ads` only if
touched (they should not be).

**Reviewer's fixes already live (do not undo):** `e650506b` (booking price) and the client
Financial Summary tab: the `credit` tile is now labelled **Outstanding** and the mislabelled
"Total Paid" / `debit` tile is gone (`debit` kept as an invisible field) — commit after this
handover's; read `git log -3 -- addons/health_fieldservice/views/ops_client_profile_form_views.xml`.

## 1. Scope

| # | Item | Sanctioned files |
|---|---|---|
| P1 | CRM contact form onto the kit: `class="ws-workspace"`, hero in the arch, journey, Next step, packed Overview cards + fold tray, rail, contact history full width at the bottom | `health_crm/views/crm_center_views.xml` — ONLY `view_crm_contact_form_crm_center` |
| P2 | Controller chrome: stop drawing `crm-profile-header` (identity + Book / Log Activity / Escalate / Spam). Keep breadcrumb + save indicator. Keep the controller methods (nothing else patches them, but keep them one phase for safety) | `health_crm/static/src/xml/crm_contact_form.xml`, `static/src/js/crm_contact_form.js` (drop the mount-time `get_contact_header_data` call if nothing reads `headerState` any more) |
| P3 | The four actions become arch header buttons calling the SAME methods: `action_convert_to_booking` (Book), `action_log_as_lead` (Log activity), `action_escalate_contact` (Escalate), `action_mark_spam` (Mark as spam, `ws-more`); Delete/Restore/Archive/Unarchive get `ws-more`. Visible exactly when the old buttons were (always); verify each method returns something an object button can run (an action dict or `True`/`None`) — if one returns an action that navigates away where the controller deliberately did not (spam: the controller calls `action_mark_spam`, NOT `action_mark_spam_and_home`), keep that choice | same view |
| P4 | Contact widgets: `ws_contact_glance` (glance / attention) and `ws_contact_next`, sharing one loader built on `ws_client_panels.js`'s pattern (import its helpers — do not copy them) | new `health_crm/static/src/js/ws_contact_panels.js` + `.xml`; manifest |
| P5 | Journey: extend the kit's `ws_journey` with an optional `terminal` attr (comma states rendered like `cancelled`: all segments grey + a chip with that state's selection label) and multi-alias support (`aliases="thinking:lead,recontact:lead,service_used:existing"`). Existing booking usage must render byte-identically | `health_theme/static/src/js/ws_journey.js`, `.xml`, `ws_workspace.scss` |
| K | Kit fixes from the WS-2 report: tab underline clipping, field-chip alignment, titles nested in a header row, Shortcuts icon colour — move them from WS-2's page-specific rules into `ws_workspace.scss` so all three screens share them; move WS-2's nine icons into `health_theme/static/src/img/lucide/` + `vu_icons` if and only if it needs no data migration (health_theme is being upgraded anyway) and update the references | `health_theme` (scss, img, manifest), `health_fieldservice` (references + the rules moved out) |
| X1 | Booking Pricing card: `total_price` shows "Total Price 0 ₫" beside a real price (it is only base_price + extra charges, base_price is 0 everywhere). Relabel it in the booking ops arch with `string="Extra charges total"` (Vietnamese "Tổng phụ phí") | `health_fieldservice/views/health_fieldservice_order_views.xml` — that one attribute |
| X2 | Known wrong/missing Vietnamese on the three screens (report them before/after): "Pay Quote" → "Thu nhập" (means income; use "Thanh toán báo giá"); "ALLERGIES:" → "Tâm dị ứng" (use "DỊ ỨNG:"); "Gender" label English; tab labels Pricing / Visit Tasks / Family Updates / Telehealth / "Staff Overview" English. Fix each in the catalogue of the module that OWNS the string (health_invoicing, health_fieldservice, advanced_pricing, health_careplan, health_family_link, health_telehealth, health_base…); list every file you touch. If a module has no catalogue, create `i18n/vi.po` per conventions §4 | the owning modules' `vi.po`/`vi_VN.po` only |
| T | Tests | new `health_crm/tests/test_ws_contact_form.py` (+ `tests/__init__.py`) |

**Non-goals (binding):** the contacts LIST, the Lead Hub (`health_landing`), the standard
`crm.lead` forms, calendar, any change to what the four actions do, new stored fields, the
"summary sentence" and Ctrl K from the concept, reordering tabs.

## 2. Verified plumbing (2026-09-29 — do not re-derive)

**Surface.** `health_crm.view_crm_contact_form_crm_center` (`crm.lead`, priority 50,
`js_class="crm_contact_form_view"`) in `health_crm/views/crm_center_views.xml:67-202`, opened
by `action_crm_contact_list_native` / `action_crm_contact_form_native`; also referenced by
`health_fieldservice/models/health_fieldservice_order.py:2935`,
`health_landing/models/crm_lead.py:12`, `health_google_ads/models/google_ads_account.py:798`
and `views/google_ads_account_views.xml:342` (they open it — no arch dependency).
`crm_contact_form_view` is in the engine's `VU_NO_HERO_JS_CLASS`
(`health_theme/static/src/js/vu_form_compiler.js:42`).

**Arch today:** header Delete/Restore/Archive/Unarchive; sheet: two `web_ribbon` widgets
(Deleted, Archived); `group string="Contact Information"` (name required, phone, email_from,
mode_of_contact_id, contact_datetime | catchment_province_id, contact_relationship_type,
contact_status readonly, contact_outcome); notebook pages `client_details`, `address`,
`relationships`, `more_details`; `<widget name="contact_timeline"/>` at the end of the sheet.
No `<chatter/>`.

**Controller** `health_crm/static/src/js/crm_contact_form.js` + chrome
`static/src/xml/crm_contact_form.xml` (114 lines): breadcrumb → `crm-profile-header`
(identity from `crm.lead.get_contact_header_data` → `{code, name, initials, contact_status,
phone, email, channel, province}`; buttons Book / Log Activity / Escalate / Spam calling
`action_convert_to_booking`, `action_log_as_lead`, `action_escalate_contact`,
`action_mark_spam` with `[[resId]]`). Methods at `health_crm/models/crm_lead.py` ~:1747,
~:2012, ~:2183, ~:1979. Its `STATUS_LABELS` map says `active → "Initial Contact"` while the
field's selection says `active → "New"` (`crm_lead.py:96-110`) — **the new screen uses the
selection labels only** (one source of truth); the owner's screenshot shows both words on one
screen today.

**Statuses** (`_selection_contact_status`, crm_lead.py:96): `active` New, `booking`
Appointment Scheduled, `lead` Lead, `lost_booking` Cancelled, `spam` Spam Call, `thinking`
Thinking / Considering, `recontact` To Be Contacted Again, `service_used` Service Used,
`existing` Existing Client. Live counts (active records): lead 109, booking 126, spam 58,
active 3, lost_booking 3. Useful fields: `next_follow_up_date` (Datetime),
`last_booking_date` (computed), `contact_datetime`, `patient_id`, `duplicate_lead_count`,
`clinical_priority`, `service_interest_id`, `unique_contact_code`.

**Live extension:** view 5588 `health_web_leads` → `//page[@name='more_details']` after (Web
Attribution page); `health_google_ads/views/crm_lead_views.xml:85` inherits THAT view (5588)
— both must still apply. Test `health_web_leads/tests/test_web_leads_w2.py:504` references
it — keep green.

**QA records:** "QA Phone Check" = crm.lead **2528** (the owner's screenshot); pick one per
status (min ids: lead 234, booking 238, spam 236, lost_booking 262, active 1218), and one
with a web attribution page.

## 3. Design

```
<form string="Contact" js_class="crm_contact_form_view" class="ws-workspace">
<header> Book, Log activity, Escalate (inline) · Mark as spam, Delete, Restore, Archive, Unarchive (ws-more) </header>
hidden active/deleted
<sheet>
 <div class="ws-page">
  <div class="ws-main">
   <div class="ws-hero"> initials avatar (a span from the name — crm.lead has no avatar; the glance
        widget or a tiny ws_initials widget renders it), unique_contact_code chip (mono), name,
        contact_status chip (selection label; colours: New/Lead/Thinking/Recontact brand, Appointment/
        Service used/Existing ok, Cancelled/Spam danger), Deleted / Archived chips replace the ribbons |
        facts: phone · mode_of_contact_id · catchment_province_id · contact_datetime ("First contact Aug 6, 3:58") </div>
   <widget name="ws_journey" state_field="contact_status"
           steps="active,lead,booking,existing" labels="New,Following up,Booked,Client"
           date_fields="contact_datetime,,last_booking_date,"
           aliases="thinking:lead,recontact:lead,service_used:existing"
           terminal="lost_booking,spam"/>
   <div class="ws-next"><widget name="ws_contact_next"/></div>
   <notebook>
    <page name="overview" string="Overview">   (NEW first page — holds what the loose group held)
      <div class="ws-pack">
        contact_card "Contact": name (required), phone, email_from, contact_relationship_type ("I am the")
        reached_card "How they reached us": mode_of_contact_id, contact_datetime, catchment_province_id
        status_card "Status": contact_status (readonly), contact_outcome
      </div>
    </page>
    client_details, address, relationships, more_details (unchanged, same order); web_attribution lands after more_details
   </notebook>
  </div>
  <div class="ws-rail">
    <widget name="ws_contact_glance" mode="glance"/>
    <div class="ws-panel" name="people_panel"> linked client (patient_id, opens the client screen) or
         "Not linked yet — created at first booking"; handled by (user_id) </div>
    <widget name="ws_contact_glance" mode="attention"/>
  </div>
 </div>
</sheet>
contact history: the contact_timeline widget moved OUT of the sheet flow into a full-width block below
.ws-page (same place the chatter sits on the other two screens). Do NOT add <chatter/> if
contact_timeline already shows messages/activities — check it; if it does not, add <chatter/> after it
and say so.
</form>
```

Fold tray on Overview only if a card can be fully empty (contact_card cannot — name is
required); if none can, omit the tray.

**`ws_contact_next`** (first match):
1. `active` (New) and no `contact_outcome` → "No outcome recorded yet." / hint "First contact
   %s." (relative) / buttons "Book" (action_convert_to_booking) + "Log activity".
2. `lead`/`thinking`/`recontact` with `next_follow_up_date` < now → "Follow-up was due %s." /
   "Call back, then record what they need." / "Log activity".
3. `lead`/`thinking`/`recontact` otherwise → "Following up." / next follow-up "%s" or "No
   follow-up date set." / "Book".
4. `booking` → "Appointment scheduled." / "Last booking %s." / "Open client" when `patient_id`.
5. `service_used`/`existing` → "Existing client." / "Open client".
6. `lost_booking` → "Booking cancelled." / no button; `spam` → "Marked as spam." / no button.

**`ws_contact_glance`** `glance`: Since first contact (days; `is-warn` ≥ 7 when status still
New), Status (selection label), Follow-up (relative; `is-warn` when overdue), Last booking
(relative; quiet "None"), Duplicates (`duplicate_lead_count`, quiet 0, `is-warn` > 0 "Possible
duplicates"), Priority (`clinical_priority` label, quiet when empty). `attention`: no outcome
after 7 days (warn); follow-up overdue (warn); duplicates > 0 (warn "%s other contacts share
this phone" — confirm what the count means in the compute before wording it); status spam
(info-grey, not red).

Copy → Vietnamese as in WS-2 (reuse terms). New: Following up / Đang theo dõi, Booked / Đã đặt
lịch, How they reached us / Cách liên hệ, First contact / Liên hệ đầu tiên, No outcome recorded
yet / Chưa ghi nhận kết quả, Follow-up was due %s / Đã quá hạn gọi lại %s, Mark as spam / Đánh
dấu spam, Log activity / Ghi hoạt động, Escalate / Chuyển cấp, Open client / Mở hồ sơ khách hàng,
Not linked yet / Chưa liên kết, Handled by / Người phụ trách, Possible duplicates / Có thể
trùng.

## 4. Safety rails
1. Web Attribution (5588) and Google Ads (inherits 5588) still apply; combined arch builds.
2. Field-set superset vs committed "before" list (every field of today's arch still loads).
3. Header: the 4 lifecycle buttons unchanged except `ws-more`; the 4 new buttons call exactly
   the methods the controller called; clicking each on the CLONE produces the same result the
   old button did (record the before/after `contact_status` per action).
4. `ws_journey` booking output unchanged (test compares the rendered step list for a
   confirmed booking before/after the P5 change, or a unit test on the step builder).
5. No Python outside tests; SCSS compiler traps; flat colours; no "Odoo".
6. X2: each changed msgid's owner module listed; G1/G2 green.

## 5. Tests (`health_crm/tests/test_ws_contact_form.py`)
1. Anchor `//page[@name='more_details']` resolves; combined arch contains `web_attribution`
   (if health_web_leads installed) and the Google Ads additions (if installed).
2. Field-set superset.
3. Header table: names, invisible, groups; `ws-more` on the five; the three inline buttons
   exist with the controller's method names.
4. Skeleton: `ws-workspace`, one ws-page/ws-main/ws-rail, the journey with `terminal` and the
   alias list, the two contact widgets, `people_panel`, `contact_timeline` outside
   `.ws-page`, first notebook page `overview`.
5. Chrome template no longer contains `crm-profile-header`; nothing t-inherits
   `CrmContactFormView` on a removed class.
6. Every value of `_selection_contact_status` maps to a journey step, alias or terminal (so a
   future status can't render blank — the test enumerates the selection).
7. X1 label present; X2 msgstrs present in the owning catalogues; 8b-style DB check for the
   new terms; no "Odoo".
8. `health_web_leads` W2 tests, WS-1 and WS-2 test files still green.
Suites on the clone: health_crm, health_web_leads, health_google_ads, health_theme,
health_fieldservice, health_base i18n.

## 6. Browser QA (clone, then live) → `docs/handovers/workspace_ws3_shots/`
Real path: left menu **CRM › Contacts** → list → click the row.
1. QA Phone Check (2528) at 1440 vs the concept (Contact screen).
2. One contact per status (New, Lead with overdue follow-up if one exists, Appointment,
   Cancelled, Spam, Existing/Service used if any) — journey + Next step + attention correct.
3. On the CLONE: Book, Log activity, Escalate, Mark as spam each once on fixtures → same result
   as the old buttons; on live only open the More menu.
4. Tabs incl. Web Attribution; contact history at the bottom.
5. 1100 / 820 px; Vietnamese user; the booking Pricing card shows "Extra charges total"; the
   X2 strings on their screens in Vietnamese (before/after shots).
6. All three screens side by side at 1440 (booking BK3831, client Bùi T, contact 2528) — the
   header, journey, Next step, rail and card rhythm must match; list any inconsistency and fix
   it in the kit.
Pixel pass as before.

## 7. Deploy
As WS-2 §7 (clone `carejiox_ws3`, backups `/var/backups/ws3/`, one copy, one `-d` invocation
for every touched module on the master, then `-D carejiox_template`, `-D hhh` and any live
tenant; template jobs back off; 200s; bundle compiled; live QA §6 1, 2, 4, 5, 6).

## 8. Report → `docs/handovers/WORKSPACE_WS3_REPORT.md` (commit + paste)
As WS-2 §8, plus the per-action before/after status table (§4.3), the X2 before/after string
table, and a one-paragraph "programme closed" summary: what all three screens now share, and
anything still inconsistent between them.
