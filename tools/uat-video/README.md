# UAT video evidence — playbook

Silent, captioned screen recordings that **prove** an acceptance test on the live
system, one MP4 per test plus a combined MP4 with chapters, for the client to keep.
Built and first used for Contacts CT-01..CT-06 on carejiox.com (4 Nov 2026, all
PASS). **Read this whole file before recording anything.** The portable version
(how to set this up in another project) is the `uat-video-evidence` skill in
`~/.claude/skills/`; this file is the carejiox-specific detail.

---

## 1. What the client receives (per test)

`<evidence root>/<ID> <Title>/` (evidence root = `config.js` → `evidenceRoot`, today
`outputs/carejiox-uat-20261029/video-evidence/`):

| File | What it is |
|---|---|
| `<ID> <Title> - PASS.mp4` (or `- FAIL`) | 1920×1080 H.264, silent, ~2 MB per minute |
| `<ID> captions - Vietnamese.srt` | the same captions in Vietnamese; also inside the MP4 as a switchable track |
| `proof-screenshots/NN <label>.png` | one still per check, with the green box |
| `run.json` | every check (label, ok, detail), records created, length, chapters |

Plus, per batch: `<Area> <first> to <last> - all PASS.mp4` (chapters, one per test)
with its own `.srt`, and a dated copy of the results workbook with a
**"Video evidence (on-screen retest)"** column filled in (`sheet.py`).

What the video shows: a title card (criterion, who is signed in, test data, time
recorded), a badge with test id, role and a live Vietnam clock on every frame, a red
pointer with click ripples, a numbered English caption per step, a green box and a
green **✓ PROOF** caption for each expected result, and an end card with
**PASS/FAIL**, every check and the records created.

## 2. The owner's standing decisions (do not re-ask)

- **No voice.** English captions are burned into the picture; Vietnamese is a
  subtitle track. Size target ~2 MB per minute (crf 24, `tune stillimage`).
- **Record the real business flow**, as the person who does it in real life, from
  the screen they would use. If a step cannot be done on screen, that is a
  **defect**: find the real process (templates, master data, the client record),
  ask the owner if unclear, fix and deploy, then record. **Never loosen a rule** to
  make a step pass (I once made a required template optional; the owner reversed
  it). Never edit around a failure. Report on-screen failures honestly.
- **Every proof is an assertion.** The end card says PASS only when every check
  matched on screen. A FAIL video is kept and reported, not hidden.
- **Keep the records the final videos create** on carejiox (the client may look
  them up). **Archive practice-run records** (contacts, bookings, packages,
  templates) once the final run is done. Posted invoices cannot be archived: avoid
  creating them in practice runs, or ask before cancelling.
- **Cash payments are said honestly**: "collected, settled when the cash is handed
  in under Collections" (the invoice stays unpaid until then).
- **White-label:** the word "Odoo" must never be on screen. The kit checks visible
  text at every step and prints `BRAND WORD ON SCREEN` if it is.
- Talk to the owner in plain English (no file paths or code words); tables are fine.
- Work directly (not the phased Fable/Opus handover process) for this stream.

## 3. Setup (once per machine)

```bash
cd tools/uat-video
npm install --cache "$SCRATCHPAD/npmcache"   # ~/.npm has a permissions problem on this Mac
npx playwright install chromium
pip3 install openpyxl                          # for sheet.py
```

- ffmpeg comes from the npm package `ffmpeg-static` (Homebrew is unsupported here).
- `accounts.local.json` (git-ignored, never commit, never print) holds
  `{"<login>": "<password>"}` for: `uat_crm`, `om_hn`, `uat_owner`, `nurse_hn`.
  It already exists on this Mac. Cases read it through `common.pw(login)`.
- `node_modules/`, `scout-out/`, `state.json`, `accounts.local.json` are git-ignored.

## 4. Files

| File | Purpose |
|---|---|
| `config.js` | everything site-specific: URL, time zone, sign-in paths, brand word, evidence root, subtitle language |
| `kit.js` | the recorder: overlays, actions, proofs, encode (rarely needs changing) |
| `run.js` | `node run.js BK-01 [--out <dir>]` records one case |
| `combine.js` | `node combine.js "<name>" "<test folder>" ...` joins tests with chapters |
| `sheet.py` | fills the Video evidence column from `run.json` files |
| `rpc.py` | look up / archive live records as a test user (outside the video) |
| `scout.js`, `scout_shots.js`, `scout_pwa.js` | screenshots + visible text of screens, to find what to click |
| `cases/common.js` | users, screen anchors, Quick Booking helpers, dates in Vietnam time |
| `cases/CT-0x.js` | the six Contacts cases: copy their shape |

## 5. Workflow for a batch (e.g. Bookings BK-01..BK-05)

1. **Read the test rows** (criterion, steps, expected, role, earlier results) from
   `outputs/carejiox-uat-20261029/CareJioX_Acceptance_Results_20261104_Video_Evidence.xlsx`,
   sheet "Test Results", header on row 2 (column A "Test ID"). The earlier passes
   were mostly API/data checks; the video must show the same result **on screen**.
   Client test data: `CareJioX_Test_Data_Contact_to_Billing_v20261013_V01.01.xlsx`
   (repo root, sheet Test_Data).
2. **Plan each case as a story**: who does it in real life, from which screen, what
   on-screen fact proves each expected result. Ask the owner (AskUserQuestion, plain
   English, real-world options) about anything that is a business choice.
3. **Scout the screens** before writing: `node scout_shots.js om_hn home=/bizapp/action-1433`
   (screenshots in `scout-out/`), or the chrome-devtools MCP pages already signed in
   (isolated contexts `uatowner`, `uatcrm`, `nursehn`). Find stable anchors: `name=`
   attributes, `.ws-*` classes, button text. Prefer what the user sees.
4. **Write `cases/BK-0x.js`** (template in §7). Short numbered steps, English + Vietnamese
   caption for each step, a `proofVi` entry for every proof label.
5. **Practice run into the scratchpad**: `node run.js BK-01 --out "$SCRATCHPAD/dry"`.
   Watch the console for `RPC ERROR`, `PAGE ERROR`, `PROOF FAILED`, `STEP ERROR`,
   `BRAND WORD ON SCREEN`. On a step error `error.png` shows the screen.
   **Look at the video**, not just the verdict: pull frames with
   `"$(node -p "require('ffmpeg-static')")" -ss 42 -i "<mp4>" -frames:v 1 /tmp/x.png`
   and Read them. Check captions don't cover what is being proved, boxes sit on the
   right thing, nothing is cut off.
   For long cases add a stop switch like CT-06's `CT06_STOP` env to iterate on one part.
6. **Something the screen can't do = a defect.** Fix it in the module, deploy with
   `carejiox-deploy` (see the deploy memory), run the module tests, verify in the
   browser, then go back to 5. Tell the owner what you fixed.
7. **Final run**: `node run.js BK-01` (writes into the evidence root, replacing that
   test's old MP4). It must say PASS. Note the records it printed.
8. **Archive practice records** (`rpc.py`, as `uat_owner`: `write {'active': False}`),
   and **check nothing else got created** (newest rows of the model).
9. **Combine**: `node combine.js "Bookings BK-01 to BK-05 - all PASS" "BK-01 <title>" ...`
   (folder names exactly as created; quote them).
10. **Spreadsheet**: never touch the client's original (may be open in Excel). Write a
    new dated copy **from the latest Video_Evidence copy** so the Contacts rows stay:
    `python3 sheet.py <latest copy>.xlsx <new dated copy>.xlsx --combined "Bookings BK-01 to BK-05 - all PASS.mp4" --notes notes.json`
    (`notes.json` = `{"BK-03": "Process: ..."}` for a sentence on how the business does it).
11. **Commit** tool/case changes locally (never push unless asked). Update memory
    `project_uat_video_evidence.md` and this README with new gotchas.
12. **Report** to the owner in plain English: a table per test (checks, length, size,
    records), what you fixed, anything visible in the video that a client may ask about.

## 6. Kit API (in a case, `kit` is the recorder; `kit.page` is the Playwright page)

| Call | Does |
|---|---|
| `kit.login()` | step 1: sign in as `meta.login` / `meta.role` |
| `kit.switchUser(n, user, pwa)` | sign out, sign in as `user` (`pwa=true` lands in the nurse app, dismissing its notification banner) |
| `kit.step(n, en, vi)` | numbered caption (also a subtitle cue and a brand check) |
| `kit.note(en, vi)` | caption without a number |
| `kit.click(locator, waitMs)` | moves the pointer visibly, clicks, waits |
| `kit.type(locator, text)` | click, select all, type visibly |
| `kit.select(fieldLocator, label)` | selection field: native `<select>` or the searchable menu |
| `kit.datetime(fieldLocator, 'MM/DD/YYYY hh:mm:ss AM')` | date-time picker |
| `kit.area('Operations')` | left rail area switch, then parks the pointer (the rail flyout covers the page while hovered) |
| `kit.proof(locators, label, expect, holdMs)` | green box + ✓ PROOF caption + still + assertion. `expect` = string (case-insensitive contains), RegExp, or `async (text, locators) => bool` |
| `kit.fieldValues([names], scope)` | values of form fields by technical name (inputs, not innerText) |
| `kit.records['Booking'] = 'BK3902'` | shown on the end card and in run.json |
| `kit.hold(ms)` | let the viewer read |
| `kit.brandCheck(where)` | extra white-label check |

`common.js`: `users.crm/omhn/owner`, `pw(login)`, `sidebar(page, name)`, `hero`, `heroChip`,
`heroFact`, `glanceRow`, `people`, `statusCard`, `field(page, name)`, `saveBtn`,
`listRow(page, text)`, `qbGroup/qbFill/qbPickDay/qbPickSlot` (Quick Booking),
`slotsFromNow(minutes)`, `shownTime(date, 'HH:MM')`, `vnAt(days, hh, mm)` (typed + shown
date strings), `phone()` (unique valid VN mobile per run), `tag`, `load()/save()`
(`state.json` hands records from one case to the next).

## 7. Case template

```js
// BK-0x <what the test proves, one line>
const c = require('./common');
const u = c.users.omhn;

module.exports = {
  meta: {
    id: 'BK-0x', title: '<plain title, no colon>', short: '<badge text>',
    title_vi: '<Vietnamese title>',
    criterion: '<the acceptance criterion, plain English>',
    data: '<test data used, incl. client and ids>',
    expected: '<expected result column, verbatim>',
    ...u,                       // login, password, role, role_vi
  },
  proofVi: { '<proof label>': '<Vietnamese>' },
  async run(kit) {
    const p = kit.page;
    await kit.login();
    await kit.step(2, 'Open Operations › Bookings', 'Mở Vận hành › Lịch hẹn');
    await kit.click(c.sidebar(p, 'BOOKINGS'), 2500);
    // ... steps ...
    await kit.proof(c.heroChip(p), '<label>', /confirmed/i);
    kit.records['Booking'] = '...';
  },
};
```

## 8. Rules for good proofs

- Prove **what the expected result says**, on the screen a user would check. One
  proof per expected fact; 4–16 proofs per test.
- Read **input values** with `kit.fieldValues`, never `innerText` (inputs have none).
- Prove a save by the **record id in the URL** (`/action-N/<id>`), not by the form
  still showing what you typed (an unsaved form shows it too).
- Use `.filter({ visible: true })`: forms often hold a hidden duplicate of a field.
- Box the smallest element that shows the fact; long panels make unreadable proofs.
- Labels are short facts in plain English ("Visit 1 reserved: 2 left"), each with a
  Vietnamese line in `proofVi`.
- Times on screen are Vietnam time; build expected strings with `vnAt` / `shownTime`.

## 9. Gotchas already paid for

**Recording / Playwright**
- Overlays are injected with `addInitScript`; their state lives in `sessionStorage`
  so captions survive the full page load after sign-in.
- Frames come from CDP `Page.startScreencast` at `deviceScaleFactor 1.5` (sharp text);
  frame timestamps drive the concat durations, so idle time costs almost nothing.
- MP4 muxer marks the subtitle track default on some players; it is set to 0.
- File and folder names: no `:` etc. (`safeName`), they must open on Windows.
- The caption bar flips to the top when the target is near the bottom.
- `run.js` deletes the old MP4 in that test folder: never point a practice run at
  the evidence root.

**carejiox screens**
- Sign-in submit: `button.btn-primary:has-text("Log in")` (a plain submit hits a search form).
  After sign-out the page may show remembered accounts: click "Use another user".
- Sidebar tab labels are title case in the DOM (upper case by CSS): match case-insensitive (`common.sidebar`).
- Left rail areas open a flyout on hover that covers the page: use `kit.area()`.
- Selection fields are a searchable menu (`.o_select_menu_item`); date-times type as
  `MM/DD/YYYY hh:mm:ss AM` then Enter + Escape.
- Quick Booking: past and locked slots exist; pick with `qbPickSlot(kit, slotsFromNow(90))`.
  The calendar "today" is Vietnam today (fixed 4 Nov). A nurse/lead-staff chip is a
  separate group. A booking with staff stays **Confirmed** until the nurse taps
  **Accept** in the nurse app; the next-step card then reads "Waiting for staff to
  accept" (fixed 4 Nov; before, it wrongly said "Assign Staff").
- Booking cancel: More › Cancel Booking → "Are you sure" Ok → reason + notes → confirm.
- Owner's Clients list (action 1430) searches names; book from a client with `button[name=action_create_fso]`.
- Client record: Quick actions › **Buy a package** (`.pw-card--product`, `.pw-btn--success`);
  **Packages** opens the Active Packages tab (`.ap-card`, "N left").
- Nurse app: a notification banner ("Đóng / Dismiss") closes itself after a few seconds;
  an install prompt ("Để sau Later") may sit hidden. `switchUser(..., true)` handles both.
- Toasts "was updated to release ..." are dismissed after sign-in (`dismissReleaseToast`).
- A non-owner with **no catchment area sees nothing** from the sidebar (fail-closed).
  All test users have Hà Nội.
- Changing a user's area used to need a server restart (fixed: cache cleared on write).

**Data / environment**
- Practice runs create real records on the live site. Archive them; posted invoices
  can't be archived (INV/2026/00020–00023, 1,500,000 ₫ each, unpaid cash, still on
  Nguyễn Văn An — owner has not decided; they show as "7,780,000 ₫ is unpaid" on him).
- Recording late at night VN time limits free slots today; book days ahead instead.
- Deploys: always `carejiox-deploy` (shared server, one lock). Nurse app changes need
  the PWA version bump (5 template pins + test pins).

**Learned recording Bookings / Assignment / Nurse app (4 Nov; details at the top of
`cases/bk_common.js`, `as_common.js`, `mb_common.js`)**
- Contact hero "Book" is `button[data-action=book]`. Add Services: first unit
  `.pcd-add-btn`, more units via the stepper `.pcd-qty-btn`.
- The Bookings menu opens a calendar: click `.o_switch_view.o_list` before a row.
  After Quick Booking the URL is `/bizapp/health.fieldservice.order/<id>/…`.
- "View Invoice" switches the rail to Finance: `kit.area('Operations')` before the next
  booking search. The payment page after Receive Payment has no left menu: go back with
  the top "Invoices" link, then move the pointer off the rail (its flyout covers rows).
- Tag fields: `kit.fieldValues` returns '' (it reads the empty search box) — read text.
- A client's pulsing "New booking" button never settles: click with a fallback
  (`as_common.clickRetry`). Lists re-render after a search: wait for the row.
- Nurse app: after Accept close the panel (bell or ×), the "Notifications Blocked"
  banner returns after every reload, native `alert()`s can't be captured (caption the
  exact text), tall popups scroll (prove one part at a time; a box below the popup
  edge shows nothing).
- Labels known only at run time: add to `kit._proofVi` during the run.
- Before re-recording a test, archive the previous final's bookings (locked slots,
  extra visits in the nurse's day list). Draft quotes and clinical notes cannot be
  archived.
- **Money steps are one-shot.** Completing a visit posts the invoice (and sends a test
  e-invoice); a payment can only be shown once. Practise finance steps on an OLD
  record, stopping at the dialog with Discard (`MB07_STOP`, `MB09_STOP`,
  `MB09_REHEARSE`), rehearse the after-payment navigation view-only, and only then
  take the final. Reversing a test payment (reset to draft + cancel) needs the owner's
  OK every time; a cancelled payment's number is reused by the next one.
- **Recording in parallel (3 helpers, 4 Nov):** separate visit days per batch (BK 1–3
  days ahead, AS 5–9, MB today), separate clients (AS Vũ Thị Khánh; MB the HCMC client
  Đặng Thị Quỳnh with om_hcm/nurse_hcm), own `*_common.js` and state file, own scratch
  folder, never kill processes by name. Helpers never change product code or deploy:
  they report defects; the lead fixes and deploys only when nobody is recording (a
  deploy restarts the site). Several recordings at once make videos longer (slower
  screens), not worse.

## 10. carejiox test identities and data

| Login | Role on screen | Notes |
|---|---|---|
| `uat_crm` | CRM user | area Hà Nội |
| `om_hn` | Operations Manager, Hanoi | books, buys packages, cancels |
| `uat_owner` | Owner | master data, archiving |
| `nurse_hn` | Nurse, Hanoi (employee "Client UAT nurse_hn") | facility HN_PK_PKGDVU; nurse app at `/health_pwa` |
| `doctor_hn` | Doctor, Hanoi | HN_PK_PKGDVU; accepts offers in the nurse app; sees every visit in his area (owner decision) |
| `om_hcm` | Operations Manager, HCMC | |
| `nurse_hcm` | Nurse, HCMC | TPHCM_PK_CSTNVU |

- Main fictional client: **Nguyễn Văn An**, ID `01_0000126`, Hà Nội.
- Price list for the client test data: "Client UAT 20261013 V01.01 (VND)".
- Bookings list: `/bizapp/action-1433` (open a booking at `/bizapp/action-1433/<id>`);
  Contacts `/bizapp/action-1438`; Owner Clients `/bizapp/action-1430`.

## 11. Recorded so far (all PASS, 4 Nov 2026)

Contacts CT-01..06 · Bookings BK-01..05 · Assignment AS-01..03 · Cancellation /
rescheduling CR-01..02 · Nurse app MB-01..10, each with a combined video, and
`CareJioX_Acceptance_Results_20261104_Video_Evidence_v2.xlsx` (latest copy — start the
next batch's sheet from it). Not yet recorded: CH-07, AR-01..06, RP, UM, FM, NA, AU and the
TC-01..17 client cases. The original BK plan is kept below for reference.

### Bookings BK-01..BK-05 — original head start

| Test | Expected (verbatim) | Role | On-screen story to consider |
|---|---|---|---|
| BK-01 single and multiple dates | All requested appointments and date groups are recorded without loss/duplicates. | OM | Book one visit, then a multi-date (recurring) booking from Quick Booking for the same client; list view filtered by client shows each date once with the right Vietnam time, duration, clinic. Earlier pass said the bulk multi-date wizard was "outside this executed method": Quick Booking has a recurring mode now, check it. |
| BK-02 personal details | Every supplied personal, caregiver and referrer value matches. | OM | Open a source client from the test workbook; prove name, ID, birth date, gender, both phones, address; open a linked booking and prove the contact person / caregiver and referrer (e.g. BK3835 designated contact Lê Thu Hà); repeat booking reuses the same client. |
| BK-03 services incl. added at visit | Correct initial and visit-added services persist with the correct units. | OM + nurse | OM books with the initial lines; nurse in the nurse app adds the "Added at visit" line during the visit; OM reopens the quote and proves both lines, quantities, units and the new total (earlier: glucose test, 500,000 → 550,000 on BK3851). |
| BK-04 order / draft invoice | All 17 order totals and 24 line totals equal the client formula outputs. | OM/Finance | Pick 2–3 representative TC cases (holiday, extra unit, distance, base-only discount); prove each line and total equals the workbook value on the quote; VAT zero; parking outside the client total. Do not overwrite totals. |
| BK-05 repeat/new contacts | Each new/repeat booking has a contact; one contact can own multiple bookings. | CRM/OM | New contact → booking; repeat client: new contact → booking reuses the same client; one contact → two bookings on different dates, both linked back (CT-05 already shows contact ↔ booking links: reuse its anchors). |

Ask the owner before recording whether one video per test with the representative
cases is enough, or whether a test must show all 17 cases (much longer).

## 12. Open items (as of 4 Nov 2026)

- Trial invoices INV/2026/00020–00023 on Nguyễn Văn An (see §9).
- CRM-user-only relation rule (`client_id.user_id = me`) is narrower than real use.
- The CT-06 video was recorded before the "Waiting for staff to accept" card.
