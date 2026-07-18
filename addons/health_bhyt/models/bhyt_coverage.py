# -*- coding: utf-8 -*-
"""BHYT coverage-split kernel — pure functions, no ORM.

Transparent đồng-chi-trả split: for a BHYT-eligible amount and the patient's
coverage rate, return (bhyt_covered, patient_copay) in whole VND. A service not
on the BHYT list (service_covered=False) is 100% the patient's. Every number is
explainable from the inputs — NO ML, NO hidden rules. Referral (đúng/trái
tuyến) and annual ceilings are a later refinement; Phase 1 is the core split.

Copied verbatim from bhyt-claims-phase1-spine.md §2.2 ('kernel — use as-is').
Money: the caller passes round_to (VND=1) and the kernel rounds each output so
covered + copay == the rounded eligible amount exactly (no lost/created đồng).
"""

# kernel — use as-is
def _round(amount, round_to):
    if round_to <= 0:
        round_to = 1
    # Half-up to the nearest `round_to` (VND đồng). amount is a float VND value.
    return int((amount + round_to / 2.0) // round_to) * round_to


def coverage_split(eligible_amount, coverage_rate, round_to=1,
                   service_covered=True):
    """(eligible_amount VND float, coverage_rate 0..100, round_to int,
    service_covered bool) -> (bhyt_covered int, patient_copay int).

    Invariant: bhyt_covered + patient_copay == _round(eligible_amount) always
    (the copay is the REMAINDER after rounding the covered part — money is
    never created or lost to rounding)."""
    total = _round(max(0.0, eligible_amount), round_to)
    if not service_covered or coverage_rate <= 0:
        return (0, total)
    rate = min(100.0, max(0.0, coverage_rate))
    covered = _round(eligible_amount * rate / 100.0, round_to)
    if covered > total:
        covered = total
    return (covered, total - covered)


def claim_totals(lines):
    """Aggregate a list of per-line dicts
    {'eligible': float, 'rate': float, 'round_to': int, 'covered_service': bool}
    into whole-VND totals. Splits EACH line then sums (never split the sum — a
    per-line rate/eligibility differs). Returns
    {'total': int, 'bhyt': int, 'patient': int}; bhyt + patient == total."""
    tot = bhyt = pat = 0
    for ln in lines:
        c, p = coverage_split(ln['eligible'], ln['rate'],
                              ln.get('round_to', 1),
                              ln.get('covered_service', True))
        tot += c + p
        bhyt += c
        pat += p
    return {'total': tot, 'bhyt': bhyt, 'patient': pat}
