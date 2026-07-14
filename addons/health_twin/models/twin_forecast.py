# -*- coding: utf-8 -*-
"""Digital-twin deterioration FORECAST kernel — pure functions, no ORM.

Transparent trajectory extrapolation (report IF-016): fit an ordinary
least-squares line to recent (time, risk-score) points and project it forward.
Every output is explainable from the input points — NO ML, NO LLM. The caller
(health.twin.risk) supplies the points and config; this module does only math.

Points are (x_days, score) where x is days relative to NOW: x = 0 is now,
x < 0 is the past (e.g. a point 2 days old is x = -2.0). Score is 0-100.

This block is copied verbatim from twin-phase4.md §2.1 ('kernel — use as-is').
"""

# kernel — use as-is
def _clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def fit(points):
    """Ordinary least-squares fit of score = a + b*x over `points`
    (list of (x_days, score)). Returns (slope_b, intercept_a, r2, n) or
    None when the fit is degenerate (fewer than 2 points, or all points at
    the same x so the slope is undefined). slope_b is score-units per DAY."""
    n = len(points)
    if n < 2:
        return None
    mx = sum(x for x, _y in points) / n
    my = sum(y for _x, y in points) / n
    sxx = sum((x - mx) ** 2 for x, _y in points)
    if sxx <= 0.0:                      # no time spread → slope undefined
        return None
    sxy = sum((x - mx) * (y - my) for x, y in points)
    syy = sum((y - my) ** 2 for _x, y in points)
    b = sxy / sxx
    a = my - b * mx
    # r2: fraction of score variance explained. A perfectly flat series
    # (syy == 0) is fully explained by a zero slope → r2 = 1.0.
    r2 = 1.0 if syy <= 0.0 else _clamp((sxy * sxy) / (sxx * syy), 0.0, 1.0)
    return (b, a, r2, n)


def confidence(fit_result, cfg):
    """'none' | 'low' | 'medium' | 'high' from the fit. `cfg` carries
    min_points / min_r2. 'none' means do not trust the projection at all."""
    if not fit_result:
        return 'none'
    b, _a, r2, n = fit_result
    if n < cfg['min_points']:
        return 'none'
    if r2 >= 0.7 and n >= cfg['min_points'] + 2:
        return 'high'
    if r2 >= cfg['min_r2']:
        return 'medium'
    return 'low'


def project(points, cfg):
    """Fit + project to +horizon_days. Returns a dict:
      {'has_forecast': bool, 'score': int(0-100), 'slope': float(pts/day),
       'r2': float, 'confidence': str, 'n': int}
    has_forecast is False (and score echoes the latest observed value) when the
    fit is degenerate or confidence is 'none' — the caller must NOT escalate on
    a no-forecast."""
    latest = points[-1][1] if points else 0     # points are time-ascending
    fr = fit(points)
    conf = confidence(fr, cfg)
    if not fr or conf == 'none':
        return {'has_forecast': False, 'score': int(round(latest)),
                'slope': 0.0, 'r2': 0.0, 'confidence': 'none',
                'n': len(points)}
    b, a, r2, n = fr
    projected = _clamp(a + b * cfg['horizon_days'], 0.0, 100.0)
    return {'has_forecast': True, 'score': int(round(projected)),
            'slope': b, 'r2': r2, 'confidence': conf, 'n': n}


def eta_days(current_score, slope, target_threshold):
    """Days until a rising trend crosses `target_threshold`, or None when it
    never will (slope <= 0, or already at/above the target). Explainable:
    (target - current) / slope."""
    if slope <= 0.0 or current_score >= target_threshold:
        return None
    return (target_threshold - current_score) / slope
