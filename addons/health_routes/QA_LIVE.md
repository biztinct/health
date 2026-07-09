# health_routes — Live verification (vietuat)

Server-side module (no PWA / no customer-facing page), so verification is on
the live `vietuat` DB via the odoo shell rather than the browser. The backend
views (Route Feasibility list/search, Distance Cache list, the Settings block)
are load-validated by the successful `-i/-u health_routes` upgrade — Odoo parses
and field-checks every view arch at install, so a malformed view fails the
deploy (this one returned EXIT:0). Chrome DevTools MCP was not connectable this
session; no PWA bump was needed to verify (handover §5).

Config switches on vietuat: `health_routes.use_external_router = False`
(UAT must not hammer public OSRM — the approx tier is used), `enabled = True`,
`buffer_minutes = 10`, `horizon_days = 7`, `leg_ttl_days = 30`.

## Demo (staff `ds_qa_nurse`, emp 437, catchment province 1)

Two back-to-back home visits for demo clients 861 / 862 (coords set ~24 km
apart in HCMC), 10-minute gap — a teleport the schedule can't actually make:

- **FSOs** 2373 (near) → 2374 (far), both `confirmed`, both assigned to emp 437.

### Nightly sweep → critical transition row

    RT_ROW 10  status=critical  gap=10.0 min  travel=63.6 min  buffer=10.0  method=approx

`travel 63.6 min` = 31.8 km (1.3× the 24.46 km straight line) ÷ 30 km/h. Gap
10 min < travel → **critical**. (`ok`/`unknown` transitions are not stored.)

### One ops activity on the second FSO

    RT_ACT 601  assignee=crm (operations-manager group, first user)
    summary: "DS QA Nurse — infeasible route on 2026-07-10 (1 critical transition(s))"
    note:    "Infeasible route: Demo Patient …(Near) → Demo Patient …(Far):
              needs ~64 min travel, only 10 min gap"

Dedup verified: a second sweep of the same day leaves exactly one row and one
activity (no duplicate).

### Timeline drop warning (validate_drop channel)

    RT_DROP_WARN: "Cần ~64 phút di chuyển, chỉ còn 10 phút
                   (needs ~64 min travel, only 10 min gap)"

Appended to `res['message']`; `ok` stays True, `hard_block` stays False — a
nudge, never a block.

### Distance-cache row (method 'approx')

    RT_LEG 31  km=31.8  minutes=63.6  method=approx

`use_external_router` stayed False, so the leg was computed by the local
straight-line approximation (no network) and cached.
