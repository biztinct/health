# Handover — UAT video defect fixes (2026-11-04)

Found while recording Bookings BK-01..05 and Assignment AS-01..03 / CR-01..02 / MB-01
on carejiox.com (see `tools/uat-video/README.md`). Fix them so the blocked tests can be
recorded and the passed ones re-recorded clean. Owner decisions are binding (§1).
Conventions: `docs/strategy/HANDOVER-CONVENTIONS.md` (gotcha ledger; add §5.314+ for
anything new you hit).

## 0. Rules
- **White-label:** no "Odoo" in any user-visible string (labels, toasts, help, .po msgstr).
- **Every new user-visible string gets a Vietnamese entry** in that module's `i18n/vi_VN.po`.
- **Deploy only when the lead says so** (another helper is recording on the live site; a
  deploy restarts it). Until then: code, read, reason, write tests. When told to deploy:
  `cd addons && ssh VietUcUAT "rm -rf /tmp/<m>" && scp -qr <m> VietUcUAT:/tmp/ && ssh VietUcUAT "carejiox-deploy -d -m <mods> -t /<mod>:<TestClass>"`
  (one call for all modules; read errors from the wrapper output / `/var/log/odoo/odoo-server.log`).
- **Nurse app (health_pwa) change ⇒ bump the app version** in the 5 pins of
  `health_pwa/views/pwa_templates.xml` (currently 1.21.2 → 1.21.3) AND the co-resident test
  pins (grep the old version across `addons/*/tests`).
- Live UI = the CMS/workspace views (`view_health_fso_form_ops`, `ws_*` widgets, ops_* OWL),
  not the stock forms. Edit what the screen actually renders (check in the browser).
- `noupdate=1` data does not change on upgrade: use a migration or a data write.
- Never loosen a rule to make something pass. Commit locally at the end (one commit per
  area is fine; never push). Message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Browser-verify every UI fix on carejiox.com after deploy (chrome-devtools MCP, or a
  Playwright script; logins in `tools/uat-video/accounts.local.json` — never print them).

## 1. Owner decisions (binding)
- **Nurse adds a service during the visit in the nurse app** (BK-03). Add an "Add service"
  action to the visit's quote in the nurse app: pick from the client's price list (same
  product search the app already uses for the next-visit form), quantity, and the line is
  added to the visit's quote with advanced pricing recomputed; the quote total updates at
  once. Only while the visit is in progress, only for the assigned staff. Reuse the existing
  mobile quote/update API if it fits (the 29 Oct test added a glucose line through it).
- **Operations Managers must not see "Reset to Draft" / "Delete" on posted invoices**
  (Finance/Owner keep them; posted invoices are also sent as e-invoices).
- Re-recording follows, so visible text matters.

## 2. Defects to fix

### Nurse app (health_pwa)
1. **Accept/Decline bell hidden at viewport ≥ 1024 px** — the notification bell (the only
   place to accept an offer) disappears on wide screens. Must be visible at every width.
2. **Add service during the visit** — §1.
3. **Doctor in the nurse app: access errors** — signed in as doctor_hn,
   `/health_pwa/api/user/profile` fails (health.fieldservice.team) and `/health_pwa/api/fso`
   fails (health.fieldservice.stage). Give the doctor role the read it needs (as nurses
   have), nothing wider.

### Bookings (health_fieldservice unless noted)
4. **Lead Staff keeps a declined nurse** — `_compute_lead_staff` (~line 605 of
   `models/health_fieldservice_order.py`) does not skip cancelled/deferred/template
   assignments like `_compute_assigned_staff` does. After a decline + reassignment to a
   doctor the Care team still shows the declined nurse as Lead Staff.
5. **Reschedule screen lists nurses only** — its staff chips omit doctors; an assigned doctor
   is pre-selected without a chip so he can't be removed. List eligible doctors too
   (same area/facility rules) and show every currently assigned person as a removable chip.
6. **Reschedule leaves no history** — add a booking chatter entry "Rescheduled from <old
   Vietnam date/time> to <new>" (+ staff change if any), in the user's language.
7. **Quick Booking "Doctor (optional)" creates no assignment** — it only writes
   `primary_doctor_id` (see `action_create_from_quick_booking_owl` ~line 5778 and the
   recurring variant ~5180). Create a doctor assignment (role `doctor`) like the staff loop,
   so the doctor gets the offer, "View Assignments" appears and At a glance is consistent.
8. **Recurring booking: no originating contact, no location** — the recurring path
   (`finalize_recurring_bookings` / its create sibling ~line 5180–5260, and the Quick
   Booking recurring mode) must carry `crm_lead_id`, `service_location`/`service_address`
   like the single-booking path.
9. **Client record › Bookings tab timeline card shows UTC** (BK3838 "01:30 PM" instead of
   8:30 PM). Format in the user's time zone (the table below it is already correct).
10. **New client created from a contact gets the contact's number** ("01 597026") instead
    of a client ID in the `01_0000xxx` format. Find where the contact → client path sets
    `patient_code`/ref and use the client sequence. Fix the one live record created by
    BK-05 too (client of contact "UAT-VID BK05 New Client 5238").
11. **Status chip says "New Booking" on a Confirmed booking** (`.ws-hero__state`, list
    column too) while the progress bar says Confirmed. Make the chip follow the state.
12. **At a glance › Price includes parking** (TC-04 shows 500,000; client total 400,000).
    Show the client price; parking is a staff reimbursement (show separately if at all).
13. **Pricing tab shows price-rule numbers ("589", "593")** instead of the rule's name/
    description for extra-unit rules.
14. **Clinic visit shows "Distance: 6.0 km"** in Quick Booking — hide distance for clinic /
    online visits.
15. **Staff Overview drawer shows "NaN:NaN - NaN:NaN"** (seen on BK3852).
16. **Invoice tab named "eInvoice Test"** (health_redinvoice or health_invoicing) → "eInvoice".
17. **OM sees Reset to Draft / Delete on posted invoices** — §1.

### Client data (BK-02)
18. **Second phone not kept** — the client screen has one Phone box; the test-data load
    overwrote the second number. Show a second phone on the CMS client screen (use the
    existing partner field if one fits, e.g. `mobile`; label "Second phone" / "Số điện
    thoại 2") and restore from `CareJioX_Test_Data_Contact_to_Billing_v20261013_V01.01.xlsx`
    (repo root, sheet Test_Data, columns O:Y) for every test client whose second number is
    missing (at least Trần Thị Bình 0900000212, Phạm Thị Dung 0900000414, Bùi Văn Nam
    0900000222 — verify against the sheet). Data writes via `tools/uat-video/rpc.py` as
    uat_owner are fine.
19. **Client Source / Referring doctor empty** although the workbook says "Referred" by Bác
    sĩ Phạm Minh (referrer is present under Healthcare Relationships). Fill Source and
    Referring doctor from the sheet for the test clients (data), and check whether the
    screen should derive them from the relationship.

## 3. Tests
Add regression tests where the logic is server-side (4, 6, 7, 8, 10, 11 if computed, 17):
`TransactionCase`/`HttpCase` in the owning module, tagged `post_install, -at_install`.
Run them with the deploy (`-t`). HttpCase needs `--workers=0` and http (the wrapper does it).
Pre-existing failures elsewhere are not yours; report them.

## 4. Report back
Per defect: fixed / not fixed (why), files touched, test names + result, browser-verified
(what you saw). Anything you think the owner must decide. New ledger entries.

## 5. Round 3 (nurse-app helper, MB; owner decisions binding)
1. **MB-07: the "no future visits" answer is shown nowhere.** Store the visit's
   closing answers on the booking (another visit wanted?, reason/note, who,
   when, who got the follow-up) and show them on the booking (workspace
   Overview) and on the client screen ("No further visits wanted — <reason>,
   <date>, by <nurse>"). Vietnamese for every label.
2. **"Need to Follow up" ticked → nothing happens, app says success.** The task
   goes to the area's Operations Manager (booking's catchment area; fallback
   the Owner). Never report success when no task was created.
3. **Invoice Tax Authority / MISA tab: raw error on every invoice**
   (`'account.move' object has no attribute 'patient_id'`). Use the invoice's
   booking client / partner, clear the stored error, test; never send anything
   to a tax authority or MISA from tests.
4. **"Receive Payment" pre-fills the demo bank account** "BANK134567890 - BNP
   Paribas". Remove it (nothing pre-filled); delete nothing posted.
5. **Invoices search: name + Enter finds nothing** (default field was
   Catchment Area). Client name first.
6. **Nurse app loses the running visit timer after a reload.** Restore from the
   visit's actual start.
7. **Quick Booking: 30-minute duration** (slots, price, end time).
8. **Nurse-app errors that also hit nurses** (patient list, future bookings,
   clinic phone): fix if contained.

9. **Nurse-app updates fail: "Failed to update a ServiceWorker …
   service-worker.js?v=1.21.3: The script resource is behind a redirect"**
   (doctor_hn and nurse_hn). Find why the script URL redirects and fix it so
   updates install reliably, without widening access.

Nurse app version 1.21.3 → 1.21.4. Tests for 1, 2, 3, 7 at least.

## 6. Round 4 (MB-10 helper; code + deploy in one go)
1. **Invoices posted from the nurse app are never sent as e-invoices.** Posted
   under the nurse's user, the automatic issue failed creating the e-invoice
   request (nurses cannot) and the error was only logged (INV/2026/00025, 00019
   stay "Pending"). Run the automatic issue with the rights it needs (nurse
   still recorded as the user), no general nurse access; store a readable
   error on the invoice when it fails. Test with the provider mocked. Do NOT
   issue 00025 or 00019 (00025 is issued on screen in MB-10).
2. **Nurse app: the notifications panel's × does not close it right after
   Accept.** App 1.21.4 → 1.21.5.
3. **Booking › Quote & Invoice: "Invoiced" unticked although the invoice is
   posted** (BK4056 / INV/2026/00025).
Do not touch BK4056, INV/2026/00025 or payment PBNK1/2026/00007.

## 7. Round 5 (owner approved)
1. **Booking › People panel shows the client's second phone** (`mobile`,
   0900000212 for Trần Thị Bình) instead of the main phone (0900000101). Show
   the main phone; the second phone may follow as its own labelled line.
2. **The quote/service dialog shows "Nurse Access: you can only edit
   quantities and discounts" to the Operations Manager and Owner.** Only to
   nurse-role users who are actually restricted.
3. **Quotes show no units** (Wound, Visit, Injection…), only invoices do. Show
   the unit on the booking's Pricing tab, in the quote/service dialog, and in
   the nurse app's "View service" lines (app 1.21.5 → 1.21.6).

4. **Cancelling a customer payment leaves its PAY record counted.** Payment 62
   (PBNK1/2026/00007, PAY01371, 210,000 ₫) was reset and cancelled — the
   lifecycle guard first demanded its draft journal entry (move 2439) be
   marked Deleted — and payment 63 (PAY01372) registered instead: BK4056 shows
   Total Paid 420,000 ₫, INV/2026/00025 "2 Payments". (a) PAY record follows a
   cancel/reset; Total Paid and counts use standing payments only; (b) the
   normal cancel must work without the Deleted mark, posted protections
   unchanged; (c) data: PAY01371 to the state the fixed code gives it. Do not
   touch payment 63 / PAY01372 or the invoice otherwise.

## 8. Round 6 (5 Nov 2026 — owner approved all nine; recorders are PAUSED, so code AND deploy)
Found by the AR / ADMIN / TC-HN / TC-HCM recording helpers. Nobody is recording: deploy
once at the end (one `carejiox-deploy` call for all modules) and browser-verify. Do NOT touch
bookings BK4066/BK4067/BK4068 (AR final takes pending), the source bookings BK3832–BK3848, or
any posted invoice / payment. Rules of §0 apply (white-label, Vietnamese for every new string,
PWA version bump if health_pwa changes, never loosen a rule, local commits only).

1. **Operations Manager / Owner cannot give a line discount in the office.** The workspace
   booking's View Quote dialog and the Pricing tab have no discount input; only the nurse
   app's View service has one (helpers say the quote dialog already has save code for a
   discount but never renders the box). Add an editable Discount % per line for office users
   (OM, Owner, CRM booking roles) while the quote is not yet invoiced; recompute the line and
   totals at once; history note on change. The resulting line MUST equal how the client's
   29 Oct quotes store it — read S04293 (TC-02), S04294 (TC-03), S04296 (TC-05), S04299
   (TC-08), S04303/S04305/S04308 (TC-12/14/17): the workbook formula is
   `qty × base + adjustment − discount% × (qty × base)` (discount on the base only, NOT on
   rule adjustments: e.g. TC-05 đd_240 2×150,000 + 50,000 − 10%×300,000 = 320,000;
   TC-08 đd_060 3×150,000 − 200,000 − 10%×450,000 = 205,000). Prove with tests for those
   two lines and a plain one (TC-02 bs_040 300,000 − 10% = 270,000). Nurse restrictions stay
   as they are.
2. **A booking's driving distance cannot be changed, and 0-km clients get a road distance
   computed.** Booking field `travel_distance` ("Driving Distance") is read-only and seeded
   from the client (`clinic_drive_distance_km`); Trần Thị Bình is 6 km but the workbook's
   TC-05 visit is 0 km (+50,000 ₫ wrongly). Nguyễn Văn An / Phạm Thị Dung are stored 0.00 but
   their bookings show 2.08 / 5.76 km (`_update_travel_distance`, health_fieldservice_order.py
   ~1861). Owner decision: (a) the OM/Owner can set the booking's distance on the booking
   (a visit at another address), pricing recomputes, history note "Distance changed from X
   to Y km"; a later address/geo recompute must not overwrite a manual value; (b) when the
   client has a stored distance that was set on purpose — including 0 — the booking uses it
   instead of a computed road distance. If "0 set on purpose" cannot be told apart from
   "never set" without a new marker, add the marker (e.g. set when the client's distance is
   written by a user/import) — do not treat every 0 as unknown or every 0 as zero blindly;
   explain your choice. Clinic/online visits keep distance 0 for pricing (4 Nov ruling).
3. **HCMC clinic TPHCM_PK_CSTNVU sits in central Vietnam (latitude ≈16.76)**, so Ngô Thanh
   Mai's booking shows "Driving Distance 932 km". Correct the facility's coordinates from its
   own stored street address (geocode it the way the system does; sanity: HCMC ≈ lat 10.7–10.9,
   lon 106.6–106.8). Check the Hanoi clinic too. Do NOT recompute clients' stored distances
   (they are the client's test data) and do not rewrite completed bookings.
4. **Cash hand-in from nurse to Operations Manager is not in the accounting log.** The
   hand-in (Mark Cash Delivered / Confirm Cash Delivery; PAY01351 on 29 Oct is an example)
   records recipient, time and receipt on the cash record but writes no row in the AR
   transaction log that AR-06 shows. Make the hand-in appear in that log: amount, from
   (nurse), to (OM), time, receipt reference, source payment/invoice. If the company's chart
   has separate accounts for cash held by staff vs cash at the front desk, post an internal
   transfer between them; if not, write the log row without a journal entry and say so. It
   must NOT create a customer payment or change any invoice balance. Tests.
5. **Nurses get "doesn't have 'read' access to: User (res.users)" on the messages screen's
   "Search conversations"** (nurse_hn, nurse_hcm). Make the search work for nurses without
   widening their access beyond what the search needs (names/avatars of people they may
   chat with; no other user fields). Test as a nurse user.
6. **MOH report (booking › Print › MOH Report, BK3832):** no clinic anywhere (should show the
   booking's clinic/facility, e.g. HN_PK_PKGDVU name + address); "Doctor" shows "-" though
   the booking's staff is "Client UAT doctor_hn" (use the assigned / lead staff); notes "-"
   (use the visit's completion / clinical summary if one exists, else "-"). The on-screen
   preview header shows "My Company (San Francisco), 8000 Marina Blvd…": use the booking's
   company (VIET UC). The PDF has no text layer — fine, but make sure the HTML preview and PDF
   carry the same content. Nothing is sent to the Ministry.
7. **Audit Log (Settings › Records › Audit Log): the "Record" column is always blank.** Fill
   it with the record's readable name (e.g. "BK3832", "INV/2026/00025") and make it open the
   record where the viewer has access. Existing rows too, if the model + id are stored.
8. **The Owner cannot create a public holiday** (Master Data › Public Holidays,
   resource.calendar.leaves create → access error for uat_owner). Allow the Owner to create/
   edit/archive COMPANY-WIDE holidays (no resource, no calendar), not employees' time off.
   The list currently also shows staff "Time Off" rows (e.g. "Mitchell Admin"): the Public
   Holidays screen must list public holidays only. The fictional holiday id 224 (23 Nov) and
   222 (19 Oct) must stay.
9. **Technical wording a client sees.** (a) Access-refused messages show the technical model
   name "(health.fieldservice.order)" and the "top-secret records … freshly baked cookies"
   joke: for non-admin users replace with a plain message in EN/VI, e.g. "You do not have
   access to this booking. Ask your administrator if you need it." (keep the technical detail
   in the server log; global seam, see biz_debrand). (b) Booking history says "Healthcare
   Field Service Order (Unified Booking System) created": the model's user-facing name should
   be "Booking" (VI "Đặt lịch"/existing term) everywhere a user sees it — check that nothing
   keys on the description string.

Report back per §4, plus the exact screen path for each fix and anything the recorders must
know (new field names/anchors). Ledger §5.332+.

### Round 6 results (5 Nov 2026, deployed and browser-checked on carejiox.com)
1. **Discount — fixed.** Booking › View Quote: each service card has a **Discount** box (%) and,
   when above 0, a **Discount reason** box (required). Booking › **Pricing** tab › new
   **Discounts** table (Service, Qty, Unit, Unit Price, **Discount %**, **Discount Reason**,
   Subtotal), editable by OM / Owner / CRM until the quote has an invoice; the breakdown table
   gains a Discount column when a line has one. History note on the booking: "Discount on
   <service> (<quote>) changed from 0% to 10%." Tests TC-05 320,000 / TC-08 205,000 /
   TC-02 270,000 pass (`advanced_pricing:TestOfficeDiscount`).
2. **Distance — fixed.** Booking › Overview › Location Details › **Driving Distance** is an input
   for OM/Owner (not completed/cancelled/invoiced); after a change it shows "(set by hand)",
   history "Distance changed from 6.00 to 0.00 km", the quote re-prices, and no address/geo
   recompute overwrites it. Client distances written by a person/import are marked "set on
   purpose" (`clinic_distance_method = 'manual'`, 12 test clients) and used even at 0. Existing
   bookings were NOT rewritten (Nguyễn Văn An's open bookings still show 2.08 km, incl.
   BK4066–68): set them by hand if a recording needs it.
3. **HCMC clinics — fixed (data + geocoder).** All three TPHCM clinics (PK_CSTNVU, NS_Thu_Duc,
   NS_Tan_Thuan) were at 16.7558, 106.5725; now 10.7737, 106.7166 (Photon "Ho Chi Minh City",
   their stored street is only "-"). Hanoi clinics checked: 21.0283, 105.8540 (correct). No client
   distance or completed booking recomputed.
4. **Cash hand-in in the AR log — fixed.** Confirm Cash Receipt writes one AR Transaction Log row:
   Event Type **Handover**, Amount, **Handed Over By**, **Received By**, **Receipt**, date/time,
   Payment, Invoice, Posting Path `HANDOVER→NURSE_CASH→OM`, no journal entry (carejiox has no
   separate staff-cash account in use), no payment, no balance change. Search filter
   "Cash Hand-ins". Earlier hand-ins (e.g. PAY01351) were not back-filled.
5. **Nurse "Search conversations" — fixed.** Lists only people the user may see (same area or no
   area); the users rule is unchanged (`health_catchment_scope:TestDiscussSearchScope`).
6. **MOH report — fixed.** Company (VIET UC + address + logo) and **Clinic / Phòng khám** (name +
   address) at the top of the page body; Doctor = booking doctor → assigned doctor → lead staff;
   Notes = completion notes → clinical summary. Preview and PDF share the same body (no layout
   header). The demo "My Company (San Francisco)" text lives in the company's Company Details
   setting and still prints on invoices — owner/data decision.
7. **Audit Log — fixed.** Record shows e.g. "Lý Minh Tâm (BK4072)" (searchable) for all rows;
   new **Open** button opens the record when the viewer may read it.
8. **Public holidays — fixed.** Master Data › Public Holidays lists company-wide holidays only (10,
   incl. ids 222 and 224); the Owner can create, edit and archive them (gear › Archive; filter
   "Archived"); staff time off stays out of reach. Deleting stays with system administrators.
9. **Wording — fixed.** Refusals read "You do not have access to this booking. Ask your
   administrator if you need it." / "Bạn không có quyền truy cập lịch hẹn này…"; the booking
   model is "Booking" / "Lịch hẹn". 123 older history entries keep the old stored text
   "Healthcare Field Service Order (Unified Booking System) created" (not rewritten).
Ledger §5.332–§5.339.

## 9. Round 7 (5 Nov 2026, owner approved; coded + tested, deploy when the lead says)
1. **Mark Cash Delivered to OM › "Operations Manager" picker** offered nurses/doctors (filter
   `is_healthcare_staff`) and "Create …". Now it lists employees whose user holds the
   Healthcare Manager group (= Operations Manager role and above; this leaves out the CRM and
   Accountant roles, which carry the OM group too) in the payment's catchment area (else the
   user's), **plus every Owner** (cash may plausibly go to the Owner), minus system
   administrators (the platform operator). Defaults to the current user when he is one. No
   create / create-and-edit / open. Confirming with anyone else is refused. OM employees keep
   `is_healthcare_staff` False. For PAY01351 (Hà Nội) the list is: Client UAT om_hn, Client UAT
   owner, Nguyen Van Minh (Branch Manager), Owner, Trainer. The round-6 Handover row is unchanged.
2. **HTML report tab title** read the framework name (`web.report_layout` /
   `web.report_preview_layout` fallback). biz_debranding now falls back to the brand name
   ("Viet Uc Care"), else "Report"; a report's own title is kept.
3. **MOH report PDF failed ("PDF creation failed", message showed a server folder path).** Cause:
   the round-6 logo was a `data:` image in the page body; the server's PDF engine (unpatched Qt,
   under the worker memory limit) aborts with std::bad_alloc on ANY `data:` image in a body, even
   1×1 px. Logo now loads from `/logo.png?company=<id>`; the template no longer nests a second
   html container. biz_errors now replaces PDF-engine failures with "The PDF could not be
   created. Please try again in a moment; if it keeps failing, contact support." (VI included;
   full detail in the server log; admins keep it; business messages pass through).
**Status at the owner's pause:** everything above is deployed. The picker also keeps only people
the user can see (an OM cannot read every Owner's employee): live om_hn gets om_hn, Client UAT
owner, Nguyen Van Minh. `TestCashHandoverLog.test_3` fails on its "defaults to me" line (the
test OM user has no employee-read right, so he is filtered out of his own list) — test fixture
or default logic to settle when work resumes; browser check of the picker not completed.
**Resumed and finished (5 Nov):** test fixture fixed (the live OM role has Employees / Officer);
`TestCashHandoverLog` 4/4 green. Browser, as om_hn on PAY01370: the box is pre-filled with
"Client UAT om_hn", the list is Client UAT om_hn / Client UAT owner / Nguyen Van Minh, a typo
shows "No records" (no Create), dialog cancelled — PAY01370 still Cash Pending Delivery. MOH PDF
for BK3832 downloads (1 page); report tab title "Viet Uc Care".
