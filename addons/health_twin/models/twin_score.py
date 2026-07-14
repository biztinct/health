# -*- coding: utf-8 -*-
"""Digital-twin risk scoring kernel — pure module-level functions, no ORM.

Transparent, explainable heuristic (report FB-064): a weighted average of four
components (NEWS2, open alerts, trend alerts, visit staleness), each mapped to
0-100 then combined with config-driven weights and banded by config-driven
thresholds. NO ML, NO LLM. Weights/thresholds are passed in from config so the
kernel stays pure and testable.

This block is copied verbatim from twin-phase1.md §2.2 ("kernel — use as-is").
"""

# kernel — use as-is
NEWS2_BAND_POINTS = {'high': 100, 'medium': 55, 'low_medium': 25,
                     'low': 0, '': 0}


def news2_component(band, age_hours, decay_hours):
    """Points 0-100 from the current NEWS2 band, linearly decayed to 0 as the
    score ages past `decay_hours` (a two-week-old 'high' must not dominate a
    live picture). age_hours/decay_hours are floats; decay_hours > 0."""
    base = NEWS2_BAND_POINTS.get(band or '', 0)
    if base == 0:
        return 0.0
    if age_hours <= 0:
        return float(base)
    if age_hours >= decay_hours:
        return 0.0
    return base * (1.0 - age_hours / decay_hours)


def alert_component(open_critical, open_warning):
    """Points 0-100 from open (new/acknowledged) alerts. Critical dominates;
    warnings add sub-linearly and are capped so a pile of warnings can't
    outweigh one critical."""
    crit = 100 if open_critical >= 1 else 0
    warn = min(60, 20 * open_warning)
    return float(max(crit, warn))


def trend_component(open_trend):
    """Points 0-100 from open trend_* alerts (slow deterioration signal)."""
    return float(min(100, 40 * open_trend))


def staleness_component(days_since_visit, threshold_days):
    """Small 0-100 signal: a client not seen for a while, WITH other signals,
    warrants attention. 0 until `threshold_days`, then ramps to 100 over the
    next `threshold_days` again. Kept low-weight by the caller."""
    if days_since_visit <= threshold_days:
        return 0.0
    over = days_since_visit - threshold_days
    return float(min(100, 100.0 * over / max(1, threshold_days)))


def composite(components, weights):
    """Weighted average of the four components → int 0-100. `components` and
    `weights` are dicts keyed news2/alert/trend/staleness. Weights need not
    sum to 1; they are normalized here so config changes can't push the score
    out of range."""
    keys = ('news2', 'alert', 'trend', 'staleness')
    wsum = sum(max(0.0, weights.get(k, 0.0)) for k in keys) or 1.0
    total = sum(components.get(k, 0.0) * max(0.0, weights.get(k, 0.0))
                for k in keys)
    return int(round(total / wsum))


def clinical_floor(score, open_critical, thresholds):
    """An OPEN CRITICAL deterioration alert IS critical by definition — the
    weighted average must never bury it below the critical band. A lone
    critical alert scores only ~35 under typical weights (a weighted average
    dilutes one strong signal), which would rank a live critical alarm as
    'moderate'. Applied AFTER `composite`: floor the score at the critical
    threshold when a critical alert is open, so it always lands in the
    critical band while a higher weighted score (more signals stacked) still
    ranks it above the floor, preserving order within the band."""
    if open_critical >= 1:
        return max(int(round(score)), int(thresholds['critical']))
    return int(round(score))


def band_for(score, thresholds):
    """(score, {'critical':c,'high':h,'moderate':m}) → band code.
    thresholds are inclusive lower bounds; below 'moderate' → 'low'."""
    if score >= thresholds['critical']:
        return 'critical'
    if score >= thresholds['high']:
        return 'high'
    if score >= thresholds['moderate']:
        return 'moderate'
    return 'low'
