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

## 10. Round 8 (5 Nov 2026, AR-01 blocker; coded + tested locally, deploy when the lead says)
**Invoices lost the line discount.** Cause: `advanced_pricing` `sale.order.line._prepare_invoice_line`
(pre-existing, not the round-6 code) folded every base-only discount into a net unit price with 0%
(INV/2026/00028: 180,000 / 0%; 00003–00016 from 29 Oct the same; only 00002 kept 10%).
Lead ruling (an invoice line must multiply out; no custom accounting totals):
- **No rule adjustment** (unit price = catalogue price): the invoice line keeps the quote's unit
  price, Discount % and reason — 200,000 × 1 at 10% = 180,000 (standard line math).
- **Rule adjustment + discount** (TC-05/TC-08): folded as before (qty × unit = line total,
  Discount 0) and the Discount Reason reads "10% discount on the catalogue price (450,000 ₫):
  <reason>" (VI "Giảm 10% trên giá danh mục (450.000 ₫): …"). Rule-only lines unchanged.
- No new invoice columns, no override of line/tax/move totals. health_invoicing keeps a reason
  advanced_pricing already wrote. Invoice total = quote total in every case. Both office and
  nurse-app completion invoices go through `sale.order._create_invoices`. Posted invoices
  (incl. 00028) untouched.

## 11. Round 9 (6 Nov 2026, AR-06 blockers; coded + tested locally, deploy when the lead says)
1. **AR log refund row on the wrong booking.** `health.ar.transaction.log._create_from_payment`
   tried reconciled invoices, then the wizard's invoices, then **the client's latest invoice**,
   and only last the payment's own booking — a refund (nothing reconciled) landed on the newest
   booking (row 1557: BK4107 instead of BK4087). Now `_payment_own_booking`: the payment's
   booking → its PAY record's → the PAY record's invoice's → the one booking of the invoices it
   paid → the Register Payment wizard's invoices → **empty**; never the latest booking.
   Data (health_invoicing 19.0.1.4.5 migration, dry-run on live): of 24 payment/refund rows only
   **1557 → BK4087** changes, and (lead ruling) **row 1465** (PCSH1/2026/00009, PAY01364, invoice
   INV/2026/00017 without a booking) loses its unconfirmed BK3833 (empty).
   Same rule for the automatic PAY record (`account.payment._create_health_payment_transaction`):
   the payment's own booking first, then the invoices it paid / the Register Payment invoices;
   no "client's latest invoice" fallback for booking or invoice — empty if nothing gives one.
   Existing PAY records: none has a booking that neither its payment nor its invoice confirms.
   Four auto-created PAY records point at an invoice their payment is no longer reconciled with
   (PAY01349 → INV/2026/00002/BK3834, PCSH1/2026/00001; PAY01371, PAY01372, PAY01379 →
   INV/2026/00025/BK4056, PBNK1/2026/00007): all explained by a later refund / cancel undoing the
   reconciliation, not a guess as far as the data shows. Not changed.
2. **Export file names** read "AR Transaction Log (health.ar.transaction.log).xlsx". biz_debranding
   now names every list export (xlsx and csv) after the readable name only, in the user's
   language: "AR Transaction Log.xlsx".

## 12. Round 10 (6 Nov 2026 — owner approved all seven; nobody is recording, so code AND deploy)
Found by the recording helpers on 5–6 Nov (videos are done and stay valid). Rules of §0 apply
(white-label, Vietnamese for every new string, PWA version bump if health_pwa changes, never
loosen a rule, local commits only). One `carejiox-deploy` call for all modules at the end, then
browser-verify each item on carejiox.com. Do NOT touch posted invoices, payments, journal entries,
source bookings BK3832–BK3848, or Form Studio (the lead records FM-03 with it right after you).
Tell the lead before you deploy and when the site is back.

1. **New user's time zone renamed.** A user created with `Asia/Ho_Chi_Minh` (Settings › People ›
   Access & roles › People › Add a person) shows `Asia/Saigon` after the first sign-in, on the user
   AND the linked staff record (3 of 3 new users; nurse_hn keeps Asia/Ho_Chi_Minh). Chromium's
   `Intl` reports `Asia/Saigon` for Vietnam, so something writes the BROWSER zone over the chosen
   one on first sign-in (find it: web client tz sync, PWA, a login hook, or employee tz sync).
   Fix: never overwrite a zone the user already has; when a browser zone is stored (user had
   none), store the canonical name (`Asia/Saigon` → `Asia/Ho_Chi_Minh`; generic alias→canonical
   if cheap). Data: switch existing users/employees from Asia/Saigon to Asia/Ho_Chi_Minh (list
   them in the report). Test.
2. **Switching a user off leaves the staff record active**, so a switched-off nurse still counts as
   staff (pickers, rosters, assignment lists). Owner rule: switching a user off archives their
   linked staff record(s) (same company); switching the user back on restores the staff records
   that were archived BECAUSE of it (not ones archived for other reasons — mark the cause). Must
   not open the HR departure wizard or need HR rights the switching user lacks. Apply on every
   path that switches a user off (Access & roles screen, archive action, write active=False).
   Data: list active staff records whose only linked user is switched off; archive them (the
   recording helpers' test users UAT Video User … were archived by hand already). Never touch the
   platform admin / system users. Tests.
3. **Audit Log shows times in world time (UTC).** Settings › Records › Audit Log: for date-time
   fields (e.g. booking "Scheduled Date & Time") the From/To values show raw UTC
   ("2026-11-12 02:00:00" for 09:00 Vietnam). Show them in the viewer's time zone, same format the
   rest of the app uses; stored values stay as they are. The Activity history screen also says
   its times are UTC — show local time and drop/adjust that text. Date-only fields unchanged.
4. **Empty contact list text.** The empty Contacts list (CRM) says "Create an opportunity to start
   playing with your pipeline." Replace with plain words for this screen, e.g. "No contacts yet.
   Press New to record a call, chat or walk-in." (VI too). Check the other CRM/contact screens a
   clinic user can reach for the same stock pipeline text and fix those too; nothing that says
   "Odoo".
5. **Booking Services card goes stale after a distance change.** Booking › Overview: after the
   OM edits Driving Distance (round-6 input) and saves, the Services card keeps the old distance
   chip and total (e.g. 6 km, 600,000 ₫) until a reload, while the price card already shows the
   new figure. Refresh the Services card on the same event (any other card that shows price or
   distance too).
6. **History note shows raw code.** The booking note "Post-service price recalculated…" shows
   `<br/>`, `<ul><li>` as text (escaped). Post it so it renders (Markup / proper body). Data: fix
   existing notes of this kind so they render (list how many); no other notes.
7. **Money log shows "NURSE_CASH" for a payment the Owner recorded.** Receivables › AR
   Transactions: a cash payment recorded by the Owner/Finance in the office gets posting path
   `NURSE_CASH`. (a) Work out the path from who actually received the cash (nurse app vs office
   user) — do not guess; (b) the screen must never show raw codes: show readable labels
   EN/VI (e.g. "Cash collected by nurse", "Cash received at the office", "Bank transfer",
   "Hand-in: nurse → Operations Manager"). Keep the stored code if other code relies on it.
   Data: correct existing AR log rows whose code is provably wrong (log rows only; never journal
   entries/payments); list them.

Report back per §4 (+ exact screen path per item, data rows changed, tests run). Ledger §5.347+.
Write the results as "### Round 10 results" below this section.

### Round 10 results (6 Nov 2026, deployed 11:10–11:17 AEDT and browser-checked on carejiox.com)
1. **Time zone kept — fixed.** Cause: the core sign-in writes the browser's zone on a user's FIRST
   sign-in even when one was chosen; Chromium calls Vietnam "Asia/Saigon". Now the chosen zone is kept;
   a user with none gets the browser's zone under its proper name (Asia/Ho_Chi_Minh). Checked: a person
   added with Asia/Ho_Chi_Minh (browser reported Asia/Saigon) still has Asia/Ho_Chi_Minh on the user and
   the staff record after signing in. Data: users uat_video_1122, uat_video_1132 and their two staff
   records moved to Asia/Ho_Chi_Minh (no other Asia/Saigon rows). Tests `health_access:TestFirstSignInTimeZone`.
2. **Switch off = staff record archived — fixed.** Every way a login is switched off (Settings › People ›
   Access & roles › person › Switch off, Archive, any plain change) archives their staff record(s) in
   the same company, as the system (no departure form, no HR right needed), with the reason "Their login
   was switched off." in the archive log. Switching back on restores only staff records archived this way
   (marker "Archived with their login"). Platform admins and built-in logins are never touched. Data: 10
   staff records archived (37 Tran Thi Lan, 38 Le Hoang Nam, 39 Pham Duc Anh, 40 Vo Thi Mai, 41 Hoang
   Minh Tuan, 42 Do Thanh Ha, 44 Nguyen Thi Huong, 45 Tran Quoc Bao, 437 DS QA Nurse, 1383 QA PWA Nurse
   Emp); Marc Demo (built-in demo login) left alone. Tests `health_access:TestSwitchOffArchivesStaff`.
3. **Audit Log times — fixed.** Settings › Records › Audit Log: From/To of date-time fields show the
   viewer's time and the app's usual format (BK4116 "Actual End Time": stored 2026-11-05 13:39:29 now
   reads "Nov 5, 8:39 PM", same as the When column). Stored values unchanged; date-only and other values
   unchanged; an export still gives the stored UTC text. Settings › Records › Activity history: times in
   local time; the note now reads "Times are shown in your time zone. …" (VI too). Test
   `health_base:TestAuditLogTimes`.
4. **Empty contact list text — fixed.** CRM › Contacts › All contacts, empty: "No contacts yet." /
   "Press New Contact to record a call, chat or walk-in." (the button is labelled "New Contact"; VI
   "Chưa có liên hệ nào." / "Bấm Liên hệ mới …"). Same text on every other contact screen without its own
   help; CRM › Activities empty: "No follow-ups to do." / "Plan a follow-up on a contact and it appears
   here." Also: every stock empty-list help that named the framework ("… helps you track …" on stock
   Contacts/Customers/Vendors/Opportunities) now uses the product name. Tests
   `health_crm:TestEmptyContactsHelp`, `biz_debranding:TestEmptyHelp`.
5. **Services card after a distance change — fixed.** Booking › Overview: the Services card reloads after
   each save of the booking. Checked as om_hcm on BK4043: 6 → 15 km → saved: the card showed "Home Visit
   Distance: 15.0 km" at once; back to 6 → "6.0 km" (this visit has no distance charge, so the total
   stayed 200.000 ₫). BK4043 is back to 6 km; my test left two history notes ("Distance changed from 6.00
   to 15.00 km" and back); the "set by hand" marker was cleared again. The price/attention cards already
   read the saved record. JS only, no test.
6. **History note shows raw code — fixed.** "Post-service price recalculated …" is posted as HTML ("Applied
   rules:" then a bullet list; VI "Quy tắc đã áp dụng:"). Data: 6 notes rebuilt (3 quotes S04552,
   S04555, S04592 + 3 bookings BK4077, BK4080, BK4104; message ids 175908/09, 175942/43, 176600/01); no
   other notes. Checked on BK4077's history. Test `advanced_pricing:TestPostServiceNote`.
7. **Money log codes — fixed.** Finance › AR Transactions › Posting Path now shows words, never codes:
   "Cash collected by nurse", "Cash received at the office", "Cash refunded by nurse/at the office",
   "Bank transfer", "Hand-in: nurse → Operations Manager", "Booking invoice", "Booking credit note",
   "Invoice", "Credit note", "Other" (all VI). Who took the cash: the collector the office named, else the
   payment record's collector, else whoever recorded the payment (the nurse app records as the nurse).
   Stored codes kept (new code OFFICE_CASH; the raw field is now called "Posting Code"). Data: 12 log rows
   NURSE_CASH → OFFICE_CASH (1436, 1437, 1438, 1455, 1457, 1459, 1460, 1463, 1465, 1553, 1557, 1577 — all
   recorded by uat_owner with no nurse collector); 4 nurse rows unchanged (1469, 1537, 1539, 1575). No
   journal entry, payment or PAY record touched. Note: the payment wizard still marks every cash payment
   record "Cash Pending Delivery", office cash included (not changed). Test
   `health_invoicing:TestArLogPostingPath`.

**Tests:** first run 246 of 248 passed — the 2 were test-setup mistakes (a test client without an area;
two staff records for one login), fixed and re-run: 20 of 20 (round-10 classes + TestArLogBooking +
TestCashHandoverLog). Also green in the first run: all of `health_access` and `biz_debranding`,
TestUatRound6Base, TestOfficeDiscount. Post-upgrade check: 1 layout, 0 broken.
**For recorders:** new verification login "UAT Video User R10 11060019" (uat_r10_11060019) was created,
signed in once and switched off (its staff record is archived) — same pattern as the earlier UAT Video
Users. New labels: Posting Path words above; Activity history note text; empty Contacts text.
Ledger §5.347–§5.353.

## 13. Round 11 (6 Nov 2026 — owner approved all three; nobody is recording, code AND deploy)
Rules of §0 apply. Form Studio (biz_form_studio / health_form_studio) MAY be changed this round
(item 2 only). One deploy for all modules, browser-verify, local commits, ledger §5.354+.

1. **"You do not have access to this fields."** The round-6 plain refusal message builds
   "this <model name>" from the model's description; for plural/technical descriptions (seen on
   `ir.model.fields` as uat_owner via RPC; check the others) the sentence is ungrammatical. Make
   every refusal read correctly in EN and VI: a singular noun where the model's user-facing name
   is a proper record name ("this booking", "this client"), else a neutral sentence ("You do not
   have access to this information. Ask your administrator if you need it." / VI). Scan all
   models a clinic user can hit for plural or technical descriptions; no "Odoo", no technical
   model name. Tests.
2. **Form Studio: closing the editor after "Delete field" leaves an empty draft and one hidden
   server error.** Seen twice in FM-03 (Client form, uat_owner): after Delete field the server
   republishes (bar "Version N · No changes yet", Publish disabled); pressing × then shows "Your
   changes are kept as a draft until you publish them.", stores an `fs.layout.draft` with no real
   change, and the record's `web_read` asks for the deleted field once ("Invalid field
   'x_fs_preferred_visit_time' on 'res.partner'", nothing on screen). Fix: (a) never store a draft
   (and never show that toast) when the sections equal the published layout; delete a stale draft
   in that case; (b) after a field was deleted (or anything was published) leaving the editor
   must clear the view caches the same way publish does, so the record never asks for a deleted
   field. Also check other open tabs of the same user after a delete (registry_invalidated path).
   Tests in the Studio suites; re-run FM-03-style flow in a browser (create, publish, delete,
   close: no draft row, no error).
3. **Cash taken at the office shows "Cash Pending Delivery".** Every cash payment's PAY record
   (payment transaction / custody record, Finance › Payments) starts in "Cash Pending Delivery",
   even when an office user (Owner / Finance / OM at the desk) records it — so it looks as if a
   nurse still holds it, and it may sit in Operations › Collections › Pending Delivery. Rule: only
   cash COLLECTED BY A NURSE/DOCTOR in the field (nurse app, or a payment whose collector is field
   staff) is "pending delivery" until handed in; cash recorded by an office user is received at the
   office at once (pick the existing state that means that, else add one with a plain label EN/VI,
   e.g. "Received at office"), never listed under Pending Delivery, no hand-in needed. Use the same
   "who received the cash" rule you used for the round-10 posting path. Data: correct existing PAY
   records recorded by office users that still say Cash Pending Delivery (dry-run list first; custody
   state only — never journal entries, payments, invoices or AR log amounts). Tests; browser check as
   finance/owner (record cash at the office → not pending) and that nurse cash still goes pending
   (do not create a new nurse payment on live for this: use the tests, and existing records).

Write "### Round 11 results" below this section.

### Round 11 results (6 Nov 2026, deployed 12:15–12:30 AEDT and browser-checked on carejiox.com)
1. **"this fields" — fixed.** A refusal no longer uses the record type's technical description. Known
   records are named: booking, client (a client contact), contact, quote, invoice (customer invoices),
   payment, payment record, staff record, clinical note, facility, incident, user account (VI: lịch hẹn,
   khách hàng, liên hệ, báo giá, hóa đơn, …). Everything else gets: "You do not have access to this
   information. Ask your administrator if you need it." (also "You cannot change / add / delete this
   information."; VI "Bạn không có quyền truy cập thông tin này. …"). Checked: uat_owner on field
   definitions → "You cannot change this information. …"; nurse_hn on an HCMC booking → "You do not have
   access to this booking. …". System administrators keep the technical text. No data. Tests
   `biz_errors:TestPlainAccessErrors`.
2. **Form Studio empty draft + hidden error — fixed.** After Delete field the Care-card placement is left
   empty; the editor counted it as a change. The editor and the server now compare only what is drawn
   (sections with fields): closing with × after a delete stores no draft and shows no "kept as a draft"
   message; an older draft that no longer differs is removed (on save and on delete). Leaving the editor
   after a delete clears the cached screens like Publish does, and every open tab of every staff member
   is told (via the live-update channel) to read the screens again. Checked as uat_owner on Nguyễn Văn
   An's Client form (Studio › Text in Care › Add field › Publish › Studio › field › Delete this field ›
   DELETE › ×): bar "No changes yet", only the toast "Field deleted. 0 records had a value.", 0 draft rows,
   no server error in this tab or in a second open tab that then opened another client. Note: the Client
   layout is now at **version 8** (my two probe runs: fields "R11 probe field" / "… two", both deleted).
   One empty draft from my first run was deleted by hand. Tests `biz_form_studio:TestFsLayouts`
   (new test_11c), TestFsFields, TestFsWorkspace; `/health_form_studio` 25/25.
3. **Office cash "Cash Pending Delivery" — fixed.** Only cash a nurse/doctor took in the field is "Cash
   Pending Delivery" (round-10 rule: the collector named on the record, else the payment's own evidence,
   else whoever records it). Cash recorded by an office user is received at once: "Payment Collected", then
   "Reconciled in AR" once its payment is posted (the state an office transfer gets) — never in
   Operations › Collections (Cash Pending Delivery), no hand-in. Prepaid-package cash taken at the office
   now gets its cash payment at once (before, every cash package waited for a hand-in to be paid).
   Data (custody state only): PAY01355, 01357, 01359, 01360, 01363, 01364 → Reconciled in AR (all recorded
   by uat_owner, payment posted). **Left as they are:** PAY01366–PAY01370 (om_hn, prepaid packages on the
   trial invoices INV/2026/00020–00024): no accounting payment exists yet — the hand-in is what creates it,
   so changing their state would leave those invoices unpaid with nothing to pay them. Lead/owner to decide
   (hand them in, or cancel the trial invoices). PAY01365 (nurse_hn) stays pending. Checked as uat_owner:
   Operations › Collections lists PAY01365 and the five prepaid ones only; Finance › All payments shows
   PAY01355 … 01363 "Reconciled in AR". I did not record a new office cash payment on live: every open
   invoice belongs to recorded AR test data (balances would change); the office/nurse paths are covered by
   `health_invoicing:TestCashCustody` (5 tests), and TestCashHandoverLog (fixture now names the nurse as
   collector, as the business flow does).

**Tests:** all green after fixes — biz_errors (all), biz_form_studio TestFsLayouts/TestFsFields/TestFsWorkspace
(28), health_form_studio (25), health_invoicing TestCashCustody, TestCashHandoverLog, TestArLogPostingPath,
TestArLogBooking. Along the way: TestCashHandoverLog failed once on my first version of the rule (a collector
set in the same save was ignored — fixed in code, not in the test); three Form Studio nurse-app version
checks failed because the box still had OLD test files of health_form_studio, health_pwa_daystrip,
health_scribe, health_pwa_ergo, health_pwa_family (pins 1.21.2; repo has 1.21.6) — deployed those test files
(only the tests differed). Ledger §5.354–§5.357.
