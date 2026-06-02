# Advanced Pricing — Rule Calculation Test Results

**Date:** 2026-06-02 · **Engine:** Viet Uc Pricing Engine · **Env:** UAT (`vietuat`) · 85 approved/active rules

## How this was tested

The engine's public entry point `advanced.pricing.engine.calculate_price()` is decorated `@api.model`, so it
**cannot be exercised over RPC** (the call gets an empty engine recordset → no rules). Testing therefore used:

1. **Per-rule harness (RPC):** the rule methods `evaluate_condition()` and `apply_action()` are normal record
   methods, so each rule was driven directly with crafted contexts (match / no-match / boundary) against a
   product whose template matches the rule. "Expected" was derived independently from each rule's documented
   semantics. This isolates one rule at a time (no level-ordering noise).
2. **End-to-end (real records):** existing FSO-linked quotes were inspected for lines where the engine actually
   changed the price (`price_unit ≠ base_price`), confirming the full `calculate_price` orchestration + the
   reactive breakdown render the correct totals on real data.

## Summary

- **24 / 24** per-rule scenarios now behave **correctly** (after the fix below).
- **1 engine bug — FIXED:** overnight after-hours window (e.g. `20:00–06:00`) used to never match; now matches
  correctly at night and not during the day (re-verified — see "Bug" section).
- End-to-end price application **works** (verified on 5 real orders).
- All action types (add / fixed / multiply / discount / per-unit) compute correctly.

## Per-rule test matrix

| # | Scenario | Representative rule | Base (đ) | Context | Expected | Actual | Result |
|--|----------|---------------------|---------:|---------|---------|--------|:------:|
| 1 | Action **add** (home visit) | bs_040 Hanoi +200,000 | 300,000 | service_location=home | match → 500,000 | 500,000 | ✅ |
| 2 | Action **fixed** (wound≥2) | đd_010 Hanoi fixed 100,000 | 350,000 | wound_count=2 | match → 100,000 | 100,000 | ✅ |
| 3 | Action **multiply** (holiday) | Any Service Hanoi ×3 | 200,000 | is_holiday=true | match → 600,000 | 600,000 | ✅ |
| 4 | Action **multiply** (bilingual) | Any Service Hanoi ×1.5 | 200,000 | requires_bilingual_provider=true | match → 300,000 | 300,000 | ✅ |
| 5 | Action **discount** (multi-client) | Any Service Hanoi −10% | 200,000 | is_multi_client_same_location=true | match → 180,000 | 180,000 | ✅ |
| 6 | Action **per_unit** distance | Any nursing Hanoi 10,000/km >8km | 200,000 | distance=12 | match → 240,000 | 240,000 | ✅ |
| 7 | Distance **in-band** (8–15km) | đd nursing Hanoi +50,000 | 200,000 | distance=mid | match → 250,000 | 250,000 | ✅ |
| 8 | Distance **below** band | (same) | 200,000 | distance=min−1 | no match | no match | ✅ |
| 9 | Distance **above** band | (same) | 200,000 | distance=max+1 | no match | no match | ✅ |
| 10 | Distance **≥ min** | bs_060 Hanoi +600,000 (≥10km) | 1,500,000 | distance≥min | match → 2,100,000 | 2,100,000 | ✅ |
| 11 | Distance **< min** | (same) | 1,500,000 | distance<min | no match | no match | ✅ |
| 12 | Wound **< 2** | đd_010 Hanoi (wound≥2) | 350,000 | wound_count=1 | no match | no match | ✅ |
| 13 | Injection **≥ 2** | đd_060 Hanoi fixed 50,000 | 150,000 | injection_count=2 | match → 50,000 | 50,000 | ✅ |
| 14 | Injection **< 2** | (same) | 150,000 | injection_count=1 | no match | no match | ✅ |
| 15 | IV fluid **≥ 2** | đd_060 HCMC +150,000 | 250,000 | iv_fluid_count=2 | match → 400,000 | 400,000 | ✅ |
| 16 | Medication **≥ 2** | đd_060 HCMC +50,000 | 250,000 | medication_count=2 | match → 300,000 | 300,000 | ✅ |
| 17 | Home-service **no-match** | bs_040 Hanoi (home) | 300,000 | service_location=clinic | no match | no match | ✅ |
| 18 | After-hours-or-weekend (via **weekend**) | bs_010 Hanoi +150,000 | 200,000 | is_weekend=true | match → 350,000 | 350,000 | ✅ |
| 19 | After-hours-or-weekend (via **after-hours**) | (same) | 200,000 | is_after_hours=true | match → 350,000 | 350,000 | ✅ |
| 20 | After-hours-or-weekend **neither** | (same) | 200,000 | neither | no match | no match | ✅ |
| 21 | Hour window 20:00–24:00 **match** | bs_010 HCMC +100,000 | 200,000 | hour=21 | match → 300,000 | 300,000 | ✅ |
| 22 | Hour window **no-match** | (same) | 200,000 | hour=18 | no match | no match | ✅ |
| 23 | **Region mismatch** | đd_010 HCMC home +50,000 | 350,000 | region=Hanoi | no match | no match | ✅ |
| 24 | **Overnight** window 20:00–06:00 | bs_010 Hanoi +250,000 (after 20:00 / before 6am) | 200,000 | after-hours, hour∈{20,22,2,5,23} | match → 450,000 | match (fixed) | ✅ (was ❌, now fixed) |

## End-to-end verification (real orders, full `calculate_price` + reactive breakdown)

| Order | Product | Base (đ) | Final (đ) | Applied rule | Result |
|-------|---------|---------:|----------:|--------------|:------:|
| S00106 | đd_040_tphcm Remove cosmetic wound sutures | 250,000 | 350,000 | "Is Service at home" +100,000 | ✅ |
| S00104 / S00095 / S00093 | đd_040_tphcm (same) | 250,000 | 350,000 | home-visit surcharge | ✅ |
| S00062 | đd_070_tphcm Intramuscular injection | 90,000 | 320,000 | home + distance + hour surcharges | ✅ |

The Pricing Breakdown panel renders these correctly (e.g. S00106 shows `Home Visit | After Hours … Is Service
at home +100,000 đ … Total 350,000 đ`) and now **auto-refreshes** (computed field) with **SVG icons** (no emoji).

## Bug — FIXED

**Overnight after-hours window never matched (wrap-around midnight).**
Rules whose window crosses midnight set `appointment_hour_min=20`, `appointment_hour_max=6`. The old check in
`advanced.pricing.rule._evaluate_fso_conditions()` was a plain range test (`hour >= 20` **and** `hour <= 6`),
which no hour can satisfy, so the Hanoi night doctor/nursing surcharges (**bs_010, bs_020, đd_240**, the
"after 20:00 / before 6am" `seq 20` rules, +150,000–250,000 đ) never fired.

**Fix applied** (`_evaluate_fso_conditions`): when `appointment_hour_max < appointment_hour_min`, treat it as a
wrap-around window and match `hour >= min OR hour <= max`; otherwise use the same-day range. Non-wrapping
windows (e.g. HCMC 20:00–24:00) are unaffected.

**Re-verified after fix** (rule id 417, Hanoi 20:00–06:00):
- Matches at hours **20, 22, 02, 05, 23** ✅
- Correctly does **not** match at **10, 18** ✅
- Same-day rule (id 481, HCMC 20:00–24:00) still matches 21/23, not 10/18 — no regression ✅

## Other observations (not failures)

- **Most quotes show "No adjustments"** because their product is a Hanoi item priced against HCMC-only rules
  (region mismatch) or the visit is at a clinic, not because rules are broken — verified by scenarios 17 & 23
  and the 5 adjusted orders above.
- **`fixed` actions replace the running price** mid-chain. If a `Set Fixed Price` rule (e.g. wound≥2 fixed
  100,000) fires after an `Add Amount` rule in the same chain, prior surcharges are discarded. This appears
  intended (fixed = override) but is worth confirming with the business for products that mix `add` and
  `fixed` rules (e.g. đd_010/đd_060/đd_070).

## Artifacts
- Per-rule raw results: produced by the RPC harness (24 scenarios + targeted confirmations).
- Engine call path: `evaluate_condition` / `apply_action` (rule), `calculate_price` (engine, `@api.model`).
