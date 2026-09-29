# WS-1 evidence — console logs, path, and measured checks

Navigation path used for every booking shot (clone and live): sign in → left menu
**Operations** → **Bookings** → list layout → search box → click the booking row.
No deep links on the booking screen. (The only deep links tried were to the
*standard* booking form for safety rail 5; an Operations Manager cannot open it at all —
see the report.)

Personas: clone = `owner` (Owner role; password set on the clone only). Live = a temporary
account `ws1.qa` holding exactly the groups and job role of the real "Tran OM" Operations
Manager, area Hà Nội. Deleted after QA (res_users and res_partner rows: 0, checked with psql).

## Console (browser) — booking screen

Clone, BK3831 after the final push, errors/warnings filter: **no messages**.
All messages on that load (info/debug only, all pre-existing):

    [debug] web_debranding: field_upgrade.js loaded (Odoo 19 compatibility mode)
    [log]   Zalo Bus Service initialized
    [issue] A form field element should have an id or name attribute (count: 3)
    [issue] No label associated with a form field (count: 2)
    [issue] Incorrect use of <label for=FORM_ELEMENT> (count: 11)

The `ConnectionLostError` / `ERR_CONNECTION_RESET` lines preserved from earlier loads are
my own restarts of the practice server between iterations, not application errors.

Live after deploy (every state opened): no error dialog, no failed request.

## Measured checks (clone, 1440 × 1000)

| Check | Result |
|---|---|
| Hero chips height | 24 px, 24 px |
| Smallest gap between stacked cards | 16 px |
| Clipped text inside the workspace | none |
| Label column x / value column x | 207 / 373 (left), 645 / 811 (right) — one line each |
| Rail panel widths | 320 × 4 |
| Horizontal scroll at 1100 / 820 px | 0 / 0 (tab row scrolls inside itself by design) |
| Rail position at 1100 px form width | static, below the main column |
| Client profile header buttons, live, before vs after | byte-identical HTML (482 chars) |
| Client profile screenshot, live, before vs after | identical apart from the hover lift under the pointer |

## Bundle (live, after deploy)

`/web/assets/1562d7e/web.assets_web.min.css` — 2,455,550 bytes, starts with
`@import url("/health_landing/static/src/css/./landing_dashboard.css");` (no CSS-error
header); contains `.ws-journey`, `.ops-booking-form-page.ws-workspace`, and the unrelated
`.o_care_command` rules. The JS bundle contains `ws_fold_tray` and `ws_booking_glance`.
