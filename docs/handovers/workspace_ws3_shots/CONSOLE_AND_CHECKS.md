# WS-3 evidence — navigation path, console, and measured checks

## Navigation path

Every contact shot starts from the left menu: **CRM → Contacts** (hover the CRM
area, click it, then click Contacts in the tab column — ledger §5.259) → the contacts
list → "All Dates" → type the name in the search box → click the row. Contacts reached
from another contact went back through the screen's own "Contacts" breadcrumb. The
Vietnamese booking shots on the practice copy came from **Operations → Bookings** → list
view → search BK3831 → row; the client from **Operations → Clients** → search → row.
Exceptions, stated: `02a`/`02b` (the BEFORE Vietnamese shots) and the booking-journey
markup captures were opened with the web client's own action call (they record what the
screen looked like, not a path); iteration reloads during the pixel pass are not evidence.

Personas: practice copy = `owner` (password set on the copy only). Live = a temporary
account `ws3.qa` built from the real CRM desk's groups ("CRM" user, 8 groups) with area
TPHCM, created and deleted through `carejiox-deploy -x`: `res_users` 0 rows, `res_partner`
0 rows afterwards (psql, fresh session); `bi_audit_log` / `bi_ai_log` held none.

## Shots taken before a later change (said here so nobody reads them as final)

- `03b_…_LATER_REVERTED`, `07b_…_LATER_REVERTED`: show the notes feed under the contact
  history. It was removed after the live check found it refused for CRM staff (ledger
  §5.255, commit `7fb8805f`). Live `13_…` is the final bottom of the screen.
- `04e_…` (cancelled) and `04f_…` (spam) show the Next step banner in blue; it was then
  toned like the booking's cancelled banner (red) and neutral grey for spam — `07a_…`
  shows the final spam banner.

## Console (browser)

- Contact screen, practice copy and live: one error per open, pre-existing —
  `Timeline load error: RPC_ERROR` + a 403: the history widget reads
  `mail.tracking.value`, which only a system administrator may read (ledger §5.255).
  It shows "No history yet"; no dialog.
- Live, CRM persona, first deploy: an error DIALOG "Failed to write field
  crm.lead.message_partner_ids" caused by the notes feed this phase had added — fixed and
  redeployed; re-checked: no dialog, only the pre-existing timeline error.
- Live, contacts LIST, searching a TPHCM contact whose linked client is in Hà Nội: an
  access dialog from the list (pre-existing, ledger §5.258) — `14b_…`.

## Journey on the booking (safety rail 4)

`journey_booking_BEFORE.html` (practice copy, old code) and the same capture after P5
compared string for string in the browser: identical for BK3831 (confirmed) and booking
779 (cancelled). `journey_booking_AFTER.html` records the result.

## Per-action check (practice copy; "old" = the call the old controller made, "new" = the header button)

| Action | Old path (fixture, before → after) | New button (fixture, before → after) | Screen after |
|---|---|---|---|
| Mark as spam | 250: lead / – → spam / rejected, spam caller ✓ | 248: lead / – → spam / rejected | stays on the contact, "Marked as Spam" notice, journey grey + "Spam Call" |
| Log activity | 252: lead / – → lead / pending follow-up | 234: lead / – → lead / pending follow-up | activity dialog; the form reloads when it closes |
| Escalate | 255: unchanged | 374: unchanged (lead / pending follow-up) | escalation wizard (closed without sending) |
| Book | 257: unchanged | 374: unchanged | Quick Booking screen |

## Measured checks (1440 × 1000 unless stated)

| Check | Result |
|---|---|
| Hero chips (code, status) | 24 px high, text centred (inner 12 px, 6 px above and below) |
| Initials in the 48 px circle | centred within 0.5 px |
| Overview cards | 16 px apart (masonry) |
| Header / hero / journey / Next step tops, three screens | 162 / 218 / 294 / 354 on booking and client; contact 158 / 214 before the bar fix, 162 / 218 after |
| Page, history and feed edges | 188 → 1388 px on the contact (same line as `.ws-page`) |
| Horizontal scroll at 1100 / 820 px | 0 / 0 (clone and live); rail static under the main column at 1100 |
| Canvas colour | rgb(244, 246, 251) on all three screens |

## Bundle (live, after deploy)

`web.assets_web.min.css` 2,459,396 bytes, starts with an `@import` (no CSS error header),
contains `.crm-contact-form-page.ws-workspace`, `.ws-person__role`, `.ws-journey` and the
unrelated `.o_care_command`. `web.assets_web.min.js` contains `ws_contact_next` and
`terminalLabel`, and no longer `crm-profile-header`.
