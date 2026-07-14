# -*- coding: utf-8 -*-
"""NEWS2 scoring kernel (RCP, National Early Warning Score 2, Dec 2017).

Pure module-level functions, no ORM. Boundaries are inclusive as written
in the RCP tables. Mirrored verbatim from the phase handover — do not
refactor.
"""

# kernel — use as-is
ACVPU_VALUES = ('A', 'C', 'V', 'P', 'U')


def news2_component_scores(rr, spo2, on_oxygen, sbp, hr, temp,
                           acvpu='A', scale2=False):
    """Pure NEWS2 (RCP, Dec 2017) component scoring. All args numeric
    except acvpu (one of ACVPU_VALUES) and booleans. Returns dict with the
    seven component scores. Raises ValueError on invalid acvpu."""
    if acvpu not in ACVPU_VALUES:
        raise ValueError('invalid ACVPU value: %r' % (acvpu,))
    s = {}
    # Respiration rate (breaths/min)
    if rr <= 8:
        s['rr_score'] = 3
    elif rr <= 11:
        s['rr_score'] = 1
    elif rr <= 20:
        s['rr_score'] = 0
    elif rr <= 24:
        s['rr_score'] = 2
    else:
        s['rr_score'] = 3
    # SpO2 (%)
    if not scale2:
        if spo2 <= 91:
            s['spo2_score'] = 3
        elif spo2 <= 93:
            s['spo2_score'] = 2
        elif spo2 <= 95:
            s['spo2_score'] = 1
        else:
            s['spo2_score'] = 0
    else:
        # Scale 2 (hypercapnic respiratory failure, target 88-92%)
        if spo2 <= 83:
            s['spo2_score'] = 3
        elif spo2 <= 85:
            s['spo2_score'] = 2
        elif spo2 <= 87:
            s['spo2_score'] = 1
        elif spo2 <= 92:
            s['spo2_score'] = 0
        elif on_oxygen and spo2 <= 94:
            s['spo2_score'] = 1
        elif on_oxygen and spo2 <= 96:
            s['spo2_score'] = 2
        elif on_oxygen:
            s['spo2_score'] = 3
        else:
            s['spo2_score'] = 0   # >=93 on air, scale 2
    # Air or oxygen
    s['o2_score'] = 2 if on_oxygen else 0
    # Systolic blood pressure (mmHg)
    if sbp <= 90:
        s['bp_score'] = 3
    elif sbp <= 100:
        s['bp_score'] = 2
    elif sbp <= 110:
        s['bp_score'] = 1
    elif sbp <= 219:
        s['bp_score'] = 0
    else:
        s['bp_score'] = 3
    # Pulse (bpm)
    if hr <= 40:
        s['hr_score'] = 3
    elif hr <= 50:
        s['hr_score'] = 1
    elif hr <= 90:
        s['hr_score'] = 0
    elif hr <= 110:
        s['hr_score'] = 1
    elif hr <= 130:
        s['hr_score'] = 2
    else:
        s['hr_score'] = 3
    # Temperature (°C)
    if temp <= 35.0:
        s['temp_score'] = 3
    elif temp <= 36.0:
        s['temp_score'] = 1
    elif temp <= 38.0:
        s['temp_score'] = 0
    elif temp <= 39.0:
        s['temp_score'] = 1
    else:
        s['temp_score'] = 2
    # Consciousness (ACVPU: any non-Alert scores 3)
    s['consciousness_score'] = 0 if acvpu == 'A' else 3
    return s


def news2_band(scores):
    """(total, band) from a component-score dict.
    Bands: 0-4 low; any single component == 3 -> low_medium;
    5-6 medium; >=7 high."""
    total = sum(scores.values())
    if total >= 7:
        band = 'high'
    elif total >= 5:
        band = 'medium'
    elif max(scores.values()) >= 3:
        band = 'low_medium'
    else:
        band = 'low'
    return total, band
