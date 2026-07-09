# biz_bi_margin — Live verification (vietuat)

Backend/BI-only module. The `bi_margin_visit` view, its dataset (gold) and the
"Visit Margin" dashboard are seeded by the post_init hook; all load-validated
by a clean `-i biz_bi_margin` (EXIT:0). Verified through the odoo shell.

## Row parity (handover §6e)

    VIEW_ROWS      975
    COMPLETED_FSO  975   (state IN completed / completed_pending_invoice / closed)

Exact match — one row per completed FSO, no gap.

## Data-coverage honesty (handover §5 / §6b) — READ THIS

    labor_source:  scheduled 912  |  actuals 63  |  attendance 0
    travel_km > 0:            910 / 975
    revenue_total_vnd > 0:     13 / 975   (revenue_source: quote 972, package 3)

* **Labor is 100% an assumption.** ZERO completed visits have PWA-check-in
  attendance rows, so the margin's labor time is scheduled-duration (93.5%) or
  actual start/end (6.5%), costed at the default hourly rate (almost no staff
  carry an hr.version wage). Fixing this = drive PWA check-in adoption.
* **Revenue is recorded on only 13 of 975 visits.** The other 962 have no
  linked quote amount / package value, so they show as pure cost. The margin
  dashboard's headline is therefore dominated by cost until revenue linkage
  (sale orders / packages on completed FSOs) is closed — the real finance gap.

## Margin extremes — spot-check confirms the math is correct

    TOP    FSO 1669  rev 2,600,000  cost 5,365      margin +2,594,635
    BOTTOM FSO 768   rev 0          cost 52,341,030 margin −52,341,030

FSO 768's cost is **travel**, not labor: labor_cost = 270,000 (scheduled 360 min
÷ 60 × 45,000 default) — correct; travel_cost = 52,071,030 from a garbage
`travel_distance` (~17,000 km — a geocoding outlier) × 3,000/km. The view
computes rate × distance faithfully; the loss list surfaces exactly these
bad-data / unrecovered-cost visits, which is the point. (Data cleanup of
travel_distance + revenue linkage are ops follow-ups, not view bugs.)

## Seeded objects (handover §6c)

    dataset 10  "Visit Margin"  state=published  storage=gold  certified=True
    silver bi_silver_10  ✓        gold bi_gold_10  ✓ (975 rows)
    refresh job 1  interval=1440 (daily)
    dashboard 7  "Visit Margin"  9 widgets  workspace=Finance
    seed marker biz_bi_margin.seeded = 1

The dataset lives in the EXISTING `biz_bi_health.workspace_finance` workspace,
inheriting its finance/manager sharing (no new ACL). Costing assumptions:
default_hourly_cost_vnd=45000, monthly_hours=208, cost_per_km_vnd=3000.
