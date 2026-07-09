{
    'name': 'Health Routes (Travel-Feasible Days)',
    'version': '19.0.1.0.0',
    'category': 'Healthcare',
    'summary': 'Tier 4: make nurse days travel-feasible — a distance cache, a '
               'transition checker, a nightly feasibility sweep, a timeline '
               'drop warning, a slot-proposer guard and a road-based family '
               'ETA. Warnings-only: nothing blocks, nothing auto-moves.',
    'author': 'Biztinct',
    'description': """
Travel-Feasible Days (health_routes) — v1
=========================================

Today the platform schedules back-to-back visits across town as if teleporting.
This module connects the plumbing that already exists (``driving_distance()``
with a Google→OSRM→approx fallback, the unused matrix travel/buffer fields,
``validate_drop``'s message channel) to judge whether a nurse's day is actually
travel-feasible — WITHOUT blocking or moving anything (that is v2).

* ``health.route.leg`` — a symmetric distance cache (every routed pair goes
  through it; external routers are slow and rate-limited). Travel is treated as
  symmetric in v1 (A→B and B→A share one cache row).
* ``health.route.transition`` — the ONE shared transition checker (gap ≥
  travel + buffer?) plus a nightly sweep that stores a warn/critical row per
  infeasible consecutive-visit pair and raises ONE ops activity per infeasible
  staff-day. Online visits carry no travel and are skipped entirely.
* Timeline soft warning — ``validate_drop`` appends a travel note; never blocks.
* Slot-proposer guard — drops travel-CRITICAL slots (both first-visit offers
  and client self-booking inherit this for free).
* Family ETA — the daystrip "on the way" ETA switches from 25 km/h haversine to
  cached road minutes (falls back to super on unknown).

An ``unknown`` transition (coords + districts both missing) never produces a
row or a warning — it must not cry wolf. No PWA change (all server-side).
""",
    'depends': [
        'health_workflow_auto',
        'health_pwa_daystrip',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/health_routes_security.xml',
        'data/routes_config_params.xml',
        'data/routes_cron.xml',
        'views/route_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'installable': True,
    'application': False,
    'sequence': 160,
    'license': 'LGPL-3',
}
