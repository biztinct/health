# twin-phase3 browser evidence pack

Phase: health_twin 19.0.3.0.0 — Risk History & Trajectory (backend surface, NO PWA).
Server: vietuat via https://care.biztinct.com. Logged in as an Operations-Manager
CMS user (owner-scope sees all catchments). All shots taken from the REAL user path.

## Screens

### 1. Deterioration Worklist — trend arrows (`01`, `02`)
Real path: CMS sidebar → **CLINICAL › Care Intelligence › Deterioration Worklist**
(action `health_twin.action_health_twin_risk`).

- `01-worklist-high-worsening.png` — the worklist as it opens with the default
  `high + critical` + group-by-band filter. The seeded worsening patient appears
  under **High** with the new **TREND** and **SCORE Δ** columns (score 62, Δ 42).
- `02-worklist-both-arrows.png` — after removing the band filter + group-by so both
  seeded QA patients show flat:
  - **ZZQA Twin Worsening** → RISK BAND `High`, **TREND `Worsening`** (red badge),
    SCORE Δ `42` (red).
  - **ZZQA Twin Improving** → RISK BAND `Low`, **TREND `Improving`** (green badge),
    SCORE Δ `-58` (green).

> Presentation note: the trend column renders as a colour-decorated **badge**
> (Worsening=danger/red, Improving=success/green, Stable/New=muted) plus a
> colour-decorated **Score Δ** magnitude — house-consistent with the existing
> `risk_band` badge, no emoji. The handover's "red up-arrow / green down-arrow"
> intent is carried by badge colour + the signed delta (a literal per-cell FA
> glyph would need a custom list widget; the badge is the flat-mono house pattern).

### 2. Client chart — Risk Score trajectory panel (`03`, `04`)
Real path: CMS sidebar → **Clients** → open a client → **Trends** tab
(`/bizapp/action-1430/<patient_id>`, ops profile view — surfaces per ledger §5.41).

- `03-trends-risk-panel.png` — the Trends tab: the five vitals panels + NEWS2 all
  "No readings yet" (the QA patient has ONLY risk-history rows, no observations),
  and the new **Risk Score** panel at the end of the grid.
- `04-risk-trajectory-chart.png` — the **Risk Score** ECharts panel rendered: a
  rising line `15 → 28 → 45 → 62` over the window with band zones (green 0–24,
  amber 25–49, red 50–100) matching the worklist band thresholds. The generic
  twin_trend_charts widget rendered the new `risk` panel with **no widget change**.

## Console
`list_console_messages(error, warn)` on the Trends screen → **no messages** (clean).
`evaluate_script` confirmed the `.twin-chart-host[data-key="risk"]` canvas rendered
(368×220).

## QA data lifecycle (§5.34)
Seeded 2 QA patients (ids 8809 worsening / 8810 improving) + 4 risk-history points
each, directly via `odoo-bin shell` (create → `flush_all` → `cr.commit`), verified
in a SEPARATE shell (scores `[15,28,45,62]` / `[78,60,30,12]`). After the shots,
deleted history + snapshots + partners, then re-confirmed in a FRESH cursor:
`PARTNERS 0 / TWIN 0 / HIST 0 / ZZQA_LEFT 0`. No QA data left on vietuat.
