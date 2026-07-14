# health_twin — Phase 1 implementation report (Deterioration Worklist)

**Kickoff:** `Implement the phase specified in docs/strategy/handovers/twin-phase1.md.`
**Server:** vietuat (care.biztinct.com), Odoo 19 CE. **Branch:** 19.0.
**Scope:** one new backend module, NO shared-module edits, NO PWA bump.

---

## 1. What was built (file list)

New module `addons/health_twin` (19.0.1.0.0):

```
health_twin/
  __manifest__.py                         depends: health_telemonitoring,
                                          health_vitals, health_fieldservice,
                                          health_base, mail
  __init__.py
  models/
    __init__.py
    twin_config.py                        config helpers (clone of tm_config,
                                          prefix health_twin.)
    twin_score.py                         VERBATIM scoring kernel (§2.2 block)
    health_twin_risk.py                   health.twin.risk model + recompute
                                          engine + cron + smart-button actions
    health_ews_score.py                   _inherit hook: recompute on new NEWS2
    health_monitor_alert.py               _inherit hook: recompute on alert
                                          create + state-change (never-block)
    res_config_settings.py                twin_enabled / twin_sweep_enabled
                                          (§5.36 set_values override)
  security/
    ir.model.access.csv                   read nurse..manager; write/create/
                                          unlink only admin+owner
    twin_security.xml                     catchment + owner ir.rules
  data/
    twin_config_params.xml                weights, thresholds, decay, caps
    twin_cron.xml                         6-hourly sweep cron
  views/
    health_twin_risk_views.xml            list + form + search + action
    res_config_settings_views.xml         settings block
    twin_menus.xml                        Clinical Intelligence → Deterioration
                                          Worklist
  i18n/vi.po                              Vietnamese catalog (every entry with
                                          #. module: header, §5.29)
  tests/
    __init__.py
    test_twin.py                          21 tests (kernel + engine + hooks +
                                          cron + settings + ACL)
```

Reports/evidence:
```
docs/strategy/reports/twin-phase1-report.md          (this file)
docs/strategy/reports/twin-phase1-evidence/          (README, 4 screenshots,
                                                      console-log.txt)
```

The scoring kernel in `twin_score.py` is the handover §2.2 "kernel — use
as-is" block, copied verbatim.

---

## 2. Test results (verbatim)

Install + tests on vietuat (`-i health_twin --test-enable --test-tags
/health_twin --stop-after-init --no-http --workers 0`):

```
2026-07-14 06:30:25,471 ... odoo.tests.result: 0 failed, 0 error(s) of 21 tests when loading database 'vietuat'
```

Server healthy after restart: `curl localhost:8069/web/login → HTTP:200`.

The 21 tests cover handover §4 cases 1-16 (case 1 — the kernel — is split into
6 sub-tests): kernel band/decay/cap/normalization/boundaries; recompute for
live-high-NEWS2, alert-only, no-signals, decayed-NEWS2; upsert single-row;
staleness from an old completed visit; both event hooks (new NEWS2, alert
state-change); cron gate + candidate-union + batch-cap; default filter;
ACL + catchment isolation; never-block; §5.36 settings roundtrip; factors_json
validity; catchment compute.

Note: the first run showed `0 failed, 1 error` — `test_12_acl` expected
`AccessError` on a nurse write/unlink, but the engine-only Python guard
(cloned from `health.ews.score`) fires *before* the ACL and raises
`UserError` (exactly as telemonitoring's `test_22_append_only` documents). The
test was corrected to expect `UserError` for the guarded write/unlink and
`AccessError` for create (no Python guard → ACL). Re-run: 0 failed of 21. No
module code changed for this fix.

---

## 3. Deviations from the handover design (with reasons)

**D1 — "single critical alert → high/critical band" (handover §4 test 3) is
arithmetically impossible under the specified weights; test asserts the real
outcome.**
The kernel + config are binding (kernel verbatim; weights `w_alert=0.35`, band
thresholds moderate/high/critical = 25/50/75, all per §2.6). A lone open
critical alert gives `alert_component=100`, everything else 0 → composite =
`100·0.35 = 35` (or ~40 with the no-visit staleness sentinel) → band
**moderate**, never high. I kept the kernel and every config constant exactly
as specified and wrote `test_03_alert_only` to assert what the math produces:
`alert_points == 100`, `open_critical_count == 1`, and `risk_band != 'low'`
(i.e. the alert *does* drive the score off baseline). This is the smallest
deviation that preserves the interface contract (no kernel/weight/threshold
change). Flagged here so the reviewer can decide whether the alert weight
should be raised in a later tuning pass — that is a config change, not a code
change.

**D2 — four component-point fields added to the model
(`news2_points/alert_points/trend_points/staleness_points`, Integer).**
The handover §2.1 field list does not name them, but §2.4 requires the form to
show "each component + its contribution". Rather than parse `factors_json` in
XML, I snapshot the four 0-100 component values as stored Integers and render
them plainly in the "Factor breakdown" group. This is additive (a new module,
everything sanctioned by §2.7) and changes no interface. `factors_json` still
carries the full machine breakdown as specified.

**D3 — QA/evidence menu-reachability caveat (not a code deviation).**
On vietuat the default post-login landing is the custom **"Viet UC CMS"**
workspace (`/bizapp/action-1417`), whose curated sidebar surfaces only a
subset of clinical menus and does **not** list the new "Deterioration
Worklist" (nor the sibling Telemonitoring menus — same pre-existing behaviour).
The menu **is** correctly registered under `health_base.menu_healthcare_
clinical` and renders in the standard `/odoo` Healthcare menu bar under
**Clinical Intelligence → Deterioration Worklist** (evidence
`00-menu-path.png`). The evidence pack was therefore driven from the `/odoo`
web client (the real menu path), not the CMS sidebar. No handover requirement
covers adding the item to the custom CMS sidebar; if care managers live in the
CMS workspace, surfacing it there is a separate, easily-added follow-up (a
`bizapp` sidebar entry) — noted, not built.

No other deviations. No shared-module files were touched; the ews/alert hooks
are `_inherit` classes inside `health_twin`. No PWA bump (backend-only). No
pip installs.

---

## 4. read_group aggregation notes (handover §6c)

The bulk signal gather (`_gather_signals`) uses `_read_group` exactly as the
handover prescribed — no aggregation forced a deviation:
- open alerts by `(client_id, severity)` and open trend alerts by `client_id`
  (`rule like 'trend_%'`);
- last completed visit via `scheduled_datetime:max` grouped by `patient_id`
  over `_COMPLETED_STATES`;
- current NEWS2 via `search([('client_id','in',ids),('superseded','=',False)])`
  mapped by client (latest-wins guard against the theoretically-impossible
  duplicate).

The cron candidate union is three `_read_group`s (non-superseded scores ∪ open
alerts ∪ completed FSOs within `twin_stale_horizon_days`), deduped into a set,
`is_patient`-filtered, capped at `twin_sweep_batch_cap` with a logged drop
count (no silent caps).

---

## 5. QA risk-row values before cleanup + deletion proof

QA patient **ZZ QA Twin Patient** (id 8702), seeded with a high-NEWS2 capture
(rr 30 / spo2 90 / sbp 88 / hr 70 / temp 36.5). Twin risk row **id 42**:

| field | value |
|---|---|
| composite_score | **90** |
| risk_band | **critical** |
| news2_total / news2_band | 9 / high |
| open_alert_count / open_critical_count | 1 / 1 |
| trend_alert_count | 0 |
| days_since_last_visit | 999 (no completed visit) |
| news2_points / alert_points / trend_points / staleness_points | 100 / 100 / 0 / 100 |
| catchment | Hà Nội |

Composite check: `100·0.5 + 100·0.35 + 0·0.1 + 100·0.05 = 90` → critical
(≥75). ✔

Cleanup (FK order: activities → twin → alert → ews.score → observations → FSO
→ patient → QA user) committed, then **fresh-cursor** re-count in a separate
`odoo-bin shell` (§5.34):

```
twin_rows=0  alerts=0  scores=0  obs=0  fso=0  patient=0  qa_user=0
total_twin_rows_remaining=0
```

---

## 6. Browser evidence pack

`docs/strategy/reports/twin-phase1-evidence/` — driven from the real menu path
(Healthcare → Clinical Intelligence → Deterioration Worklist), user
`twin_qa_owner` (owner). Screens: `00-menu-path.png` (menu),
`01-worklist-ranked-list.png` (ranked list, default Critical+High filter,
band grouping, the Critical row), `02-risk-form-breakdown.png` (factor
breakdown + 3 smart buttons + machine JSON), `03-smart-button-open-alerts.png`
(Open Alerts dynamic action). Console **clean** on every screen
(`console-log.txt`). See the pack README for the click-by-click path.

---

## 7. Deferred (noted, not built — per §0 non-goals)

- Trend/trajectory **charts** (FA-004 sibling phase).
- Risk **history / time-series** (one row per patient, overwritten this phase).
- Predictive/ML, what-if simulation, LLM summaries, family trajectory (IF-032).
- Auto-booking/dispatch, ZNS/SMS/email off this surface.
- CMS-sidebar surfacing of the worklist (see D3) — a `bizapp` follow-up.

---

## 8. New gotcha for the ledger (§5 candidate)

**§5.39 — an engine-only Python `write()`/`unlink()` guard fires BEFORE the
ACL, so a group with `perm_write=0/perm_unlink=0` gets `UserError`, not
`AccessError`; only the un-guarded op (`create`) surfaces the raw ACL
`AccessError`.** `health.twin.risk` (like `health.ews.score`) blocks non-su
writes with a Python guard in `write()`/`unlink()`. For a nurse holding
`perm_write=0`, the guard's `UserError` pre-empts the ACL's `AccessError`
(the override runs before `super().write()` where `check_access` lives). A
test asserting "user cannot write" must therefore expect `UserError` for any
Python-guarded model and reserve `AccessError` for operations with no Python
guard (here, `create`). This is the same split telemonitoring's
`test_22_append_only` already encodes; recording it so it is not re-discovered
per module. (Ledger §5.8 still applies: `assertRaises` takes a single
exception class, so the two cases need separate blocks.)

---

## 9. Next phase

The ranked worklist + transparent factor breakdown is the seed row of the
per-client twin. Natural next slices (all build on this same
`health.twin.risk` row): FA-004 trajectory charts, risk **history** table,
what-if simulation, IF-032 family trajectory view. None started.
