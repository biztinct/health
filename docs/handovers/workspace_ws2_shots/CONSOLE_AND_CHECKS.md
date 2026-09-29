# WS-2 evidence — navigation path, console, and measured checks

## Navigation path

Every client shot (practice copy and live) starts from the left menu: **Operations → Clients**
→ the client list → click the row (search box used to find An Xu and the no-bookings demo
client). The booking shots come from the client's **Recent visits** row (practice copy) or from
**Operations → Bookings** → the calendar event → Open (live). Two exceptions, stated: the
archived client (`09d_…`) was opened by address because archived clients are hidden from the
Clients list, and some iteration loads during the pixel pass were reloads of an already-open
client (not used as evidence of a path).

Personas: practice copy = `owner` (Owner role, password set on the copy only). Live = a
temporary account `ws2.qa` built from the real Operations Manager ("Tran OM") groups, area
Hà Nội. Deleted after QA: `res_users` 0 rows, `res_partner` 0 rows (psql, fresh session);
`bi_audit_log` / `bi_ai_log` held no rows for it.

## Loader calls (must be 1 per record load)

Measured with `performance.getEntriesByType('resource')` on `get_client_profile_data`:

| Situation | Calls |
|---|---|
| Open Bùi T from the list (practice copy and live) | 1 |
| Then switch to Bookings and back to Overview | still 1 |
| Save after filling National ID | +1 (the panels and the controller share it) |
| First build, before the fix in ledger §5.250 | 6 (one per panel + tab switch refetch) |

## Console (browser)

Practice copy, client screen, errors/warnings filter after the final push: one pre-existing
warning — `The widget: date don't support the type datetime` (the Bookings tab's
`last_visit_date` / `registration_date` stat fields use `widget="date"` on datetime fields;
untouched arch). No errors. One error seen during the build and fixed (ledger §5.249).

Live after deploy: no error dialog on the client screen, any of its tabs (Bookings, Financial
Summary, Care Plans, Diagnoses, Trends, BHYT), the booking screen, or the CRM contact screen.

## Measured checks (1440 × 1000 unless stated)

| Check | Result |
|---|---|
| Hero chips (code, status, category) | 24 px high, text centred (child top/bottom 231/243 in a 225–249 chip) |
| Allergies strip | top 294 px, bottom 338 px of a 1000 px window — above the fold |
| Rail vs notes feed | rail bottom 587 px, feed top 619 px on the booking screen: the pinned rail stops above the feed |
| Feed width | left/right 188/1388 px = `.ws-page` 188/1388 px (booking); same rule on the client |
| Active tab underline | visible after the fix (the 18-tab row clipped it by 1 px, ledger §5.251) |
| Horizontal scroll at 1100 / 820 px | 0 / 0 (the tab row scrolls inside itself) |
| Rail at 1100 px | static, three panels per row under the main column |
| Main contact dropdown | opens on top (`elementFromPoint` inside the list) |
| Recent visits dates in Vietnamese | one line ("3 thg 4") after the fix |

## Bundle (live, after deploy)

`web.assets_web` regenerated in a shell on `carejiox`: CSS 2,455,021 bytes, no CSS error
header; contains `.ops-client-profile-form-page.ws-workspace`, `.ws-person__role`, the
unrelated `.o_care_command` and the kit's `.ws-journey`. JS contains the
`ws_client_shortcuts` registry and "Buy a package", and no longer contains
`ops_client_profile_header` (health_crm's deleted template extension).
