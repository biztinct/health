# health_twin — Phase 1 browser evidence pack (Deterioration Worklist)

Real-user drive of the care-manager backend worklist. The worklist ranks
clients by a transparent deterioration-risk score computed from the shipped
telemonitoring signals (current NEWS2 band, open alerts, open trend alerts,
visit recency). No ML, no LLM.

## User + entry point
- User: **twin_qa_owner** — `base.group_user` +
  `health_base.group_healthcare_owner` (owner sees all catchments). Created
  for QA, **deleted after** (fresh-cursor confirmed removed).
- Standard `/odoo` web client (the Healthcare app renders the full menu bar
  here; the `/bizapp` "Viet UC CMS" landing has its own curated sidebar — see
  the caveat in the report §Deviations).

## Navigation (click-by-click — the REAL menu path, not a deep link)
1. Apps → **Healthcare**.
2. Top menu **Clinical Intelligence** → **Deterioration Worklist**
   → `00-menu-path.png` (the new menu item is registered under Clinical
   Intelligence, above the Telemonitoring section).
3. The worklist opens with its default context: **"Critical or High"** filter
   + **group-by Risk Band** → `01-worklist-ranked-list.png`. The QA patient
   sits in the **Critical (1)** group: risk **90** (progressbar), NEWS2 **9 /
   high**, open alerts **1**, open critical **1**, days since last visit
   **999**, computed Jul 14 4:33 PM. The whole row is `decoration-danger` red.
4. Click the patient row → readonly **risk form** → `02-risk-form-breakdown.png`:
   - Header smart buttons **Patient**, **Open Alerts (1)**, **NEWS2 (9)**.
   - RISK: score 90 (progressbar), band **Critical**, catchment **Hà Nội**.
   - SIGNALS: NEWS2 9 / high, open alerts 1, open critical 1, open trend 0,
     days since last visit 999.
   - **FACTOR BREAKDOWN (points → weighted contribution)**: NEWS2 **100/100**,
     Open Alerts **100/100**, Trend **0/100**, Staleness **100/100**.
   - **MACHINE BREAKDOWN (debug)**: the raw `factors_json` (components +
     weights + raw inputs).
5. Click the **Open Alerts** smart button (dynamic-domain action) → filters to
   the patient's open alert "NEWS2 9 — cao — ZZ QA Twin Patient", rule NEWS2
   high, severity Critical, status New → `03-smart-button-open-alerts.png`.

## Console
Clean — **no errors, no warnings** on any screen (`console-log.txt`).

## QA fixture (seeded then deleted)
- Patient **ZZ QA Twin Patient** (id 8702), FSO 5933, high-NEWS2 capture
  (rr 30 / spo2 90 / sbp 88 / hr 70 / temp 36.5 → NEWS2 total 9, band high →
  auto critical alert). Twin risk row id 42.
- **Risk-row values before cleanup**: composite_score **90**, risk_band
  **critical**, news2_total 9 / band high, open_alert_count 1,
  open_critical_count 1, trend_alert_count 0, days_since_last_visit 999,
  news2_points 100, alert_points 100, trend_points 0, staleness_points 100,
  catchment Hà Nội.
- **Cleanup**: all QA rows + the QA user deleted; fresh-cursor re-count
  (separate shell, §5.34) = `twin_rows=0 alerts=0 scores=0 obs=0 fso=0
  patient=0 qa_user=0`.
