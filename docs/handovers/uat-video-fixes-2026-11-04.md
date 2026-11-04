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
