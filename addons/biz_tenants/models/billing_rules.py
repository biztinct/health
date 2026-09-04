# -*- coding: utf-8 -*-
"""Every judgement about money, a month, and where a customer stands.

WHY THIS FILE EXISTS AND WHAT IS DELIBERATELY NOT IN IT (rail R6). Everything
below is a pure function over plain values: no records, no cursor, no clock of
its own. That is not tidiness — it is the only way the arithmetic that decides
what a customer is charged can be TESTED at all, because the numbers it works
from live on somebody else's database and the invoice it produces is a PDF.
`billing_service.py` next door does the reading, the writing and the rendering;
this file makes the decisions and can be run in a shell.

⚠ THE SIX WAYS TO PRICE A CUSTOMER ARE THREE STRUCTURES AND A METER KEY, NOT
SIX NAMED STRUCTURES — AND THAT IS RAIL R11 RATHER THAN A SIMPLIFICATION.
The owner's ruling is that any of the four numbers the platform measures can
price a plan, plus a flat price and a flat price by band. Writing those four out
as `per_patient` / `per_visit` / … would put ONE INDUSTRY'S VOCABULARY into a
module whose whole purpose is to be lifted into the next product (ledger H12,
H68, and the neutrality test that enumerates exactly those words). So the
structure is `flat`, `per_unit` or `flat_tier`, and a `per_unit` or `flat_tier`
plan NAMES the meter it reads out of the product's own registry. Six ways to
price, none of them named after somebody's industry, and the screen reads the
meter's own label — which is the product's word, in the product's language.

MONEY IS ROUNDED BY THE CURRENCY, NEVER BY PYTHON. The dong has no decimal
places at all, so `round(x, 2)` on a dong figure produces a number no bank
statement will ever show and a total that does not equal the sum of its lines.
Every amount here goes through `round_money`, which is handed the currency's own
rounding step.
"""
from datetime import date, timedelta

# =============================================================================
# The vocabulary
# =============================================================================

#: The three price STRUCTURES. Combined with a meter key they are the owner's
#: six ways to price a customer.
PRICE_KINDS = ('flat', 'per_unit', 'flat_tier')

PRICE_KIND_LABEL = {
    'flat': "One price a month, whatever they use",
    'per_unit': "A price for each one, every month",
    'flat_tier': "One price a month, by size band",
}

#: What an invoice can be. `overdue` is NOT one of them: it is a fact about a
#: date, computed wherever it is read, and a state that has to be swept into
#: existence is a state that is wrong between sweeps. The handover's four.
INVOICE_STATES = ('draft', 'issued', 'paid', 'cancelled')

INVOICE_STATE_LABEL = {
    'draft': "Not sent yet",
    'issued': "Issued, waiting for payment",
    'paid': "Paid",
    'cancelled': "Cancelled",
}

#: Where a customer stands. The first five are the platform's own lifecycle
#: (H4a); the last three are this phase's.
TENANT_STATES = ('draft', 'provisioning', 'live', 'error', 'decommissioned',
                 'trial', 'paused', 'pending_deletion')

#: THE STATES IN WHICH A CUSTOMER IS STILL A CUSTOMER — has a system, is copied
#: every night, is kept in step, is measured and is invoiced. A paused customer
#: is very much on this list: their people cannot get in, and that is exactly
#: when losing their copies would be unforgivable.
SERVING_STATES = ('live', 'trial', 'paused', 'pending_deletion')

#: Which moves are allowed, and every one of them is a person pressing
#: something. The pairs left out are the point: nothing comes back from
#: `decommissioned`, because that system is gone (H4c's `reopen` starts them
#: again from the beginning rather than moving them out of it).
STATE_MOVES = {
    ('draft', 'trial'),
    ('live', 'trial'),               # they were put on a trial after the fact
    ('trial', 'live'),               # "They are paying now"
    ('trial', 'paused'),
    ('trial', 'pending_deletion'),
    ('live', 'paused'),
    ('live', 'pending_deletion'),
    ('paused', 'live'),              # "Let them back in"
    ('paused', 'trial'),             # let back in while still on a trial
    ('paused', 'pending_deletion'),
    ('pending_deletion', 'live'),    # "Do not close them after all"
    ('pending_deletion', 'trial'),
    ('pending_deletion', 'paused'),
    ('error', 'paused'),
    ('error', 'live'),
}

#: How long a customer's data is kept after somebody schedules its removal.
#: NOTHING REMOVES IT WHEN THE CLOCK RUNS OUT. The clock is a promise to the
#: customer and a reminder to the owner; the removal itself is still the
#: closing-down button with its typed confirmation.
DEFAULT_RETENTION_DAYS = 60

#: The invoicing calendar, all overridable as settings.
DEFAULT_DUE_DAYS = 14
DEFAULT_REMINDER_DAYS = (3, 10)
DEFAULT_SUSPEND_AFTER_DAYS = 21
DEFAULT_TRIAL_DAYS = 30
#: A customer sees the countdown on their own screen for this many days at the
#: end of a trial.
TRIAL_WARN_DAYS = 10
#: The share of a seat limit at which the customer is warned rather than
#: refused.
SEAT_NEAR_PCT = 0.9

#: The settings a customer's own system is told about where they stand. Kept
#: here — beside the payload that fills them — rather than in the service, so a
#: provisioning step and a push cannot drift apart on a spelling.
T_ACCESS = 'biz_tenancy.access'
T_ACCESS_TEXT = 'biz_tenancy.access_text'
T_TRIAL_ENDS = 'biz_tenancy.trial_ends'
T_PLAN_NAME = 'biz_tenancy.plan_name'
T_PLAN_LINE = 'biz_tenancy.plan_line'
T_SEAT_LIMIT = 'biz_tenancy.seat_limit'
T_SEAT_MODEL = 'biz_tenancy.seat_model'
T_USAGE = 'biz_tenancy.usage'
T_NEXT_INVOICE = 'biz_tenancy.next_invoice'
#: The one account that still gets in while a customer is paused. Mirrored onto
#: their own system so their door can decide for itself — a locked door that
#: needs the platform to be reachable is a locked door that locks the
#: platform's own engineer out on the day the platform is broken.
T_RECOVERY = 'biz_tenancy.recovery_login'


# =============================================================================
# Money
# =============================================================================

def round_money(amount, rounding=0.01):
    """Round to the currency's own step. 1.0 for the dong, 0.01 for a dollar.

    Not `round(x, 2)`: an amount with two decimal places in a currency that has
    none is a number that cannot be paid, and a subtotal rounded differently
    from its lines is a total that does not add up on the customer's screen.
    """
    try:
        step = float(rounding or 0.01)
    except (TypeError, ValueError):
        step = 0.01
    if step <= 0:
        step = 0.01
    try:
        value = float(amount or 0.0)
    except (TypeError, ValueError):
        return 0.0
    # +1e-9 defeats the classic binary-floating-point near-miss (2.675/0.01)
    # without moving any figure a person could notice.
    return round(round(value / step + 1e-9) * step, 10)


def decimals_for(rounding=0.01):
    """How many decimal places that rounding step implies. 1.0 -> 0."""
    try:
        step = float(rounding or 0.01)
    except (TypeError, ValueError):
        step = 0.01
    if step >= 1:
        return 0
    places = 0
    while step < 1 and places < 6:
        step *= 10
        places += 1
    return places


def money(amount, symbol='', rounding=0.01, position='after'):
    """"12,400,000 ₫" — a figure somebody can read out loud.

    Thousands separators always, the symbol always, and the number of decimal
    places the CURRENCY says rather than the number Python defaults to.
    """
    places = decimals_for(rounding)
    value = round_money(amount, rounding)
    text = '{:,.{p}f}'.format(value, p=places)
    sym = (symbol or '').strip()
    if not sym:
        return text
    return ('%s%s' % (sym, text)) if position == 'before' else ('%s %s' % (text, sym))


def unit_words(label):
    """A meter's own label, fit to sit in the middle of a sentence.

    ⚠ THE LABEL IS THE PRODUCT'S WORDS AND IT IS WRITTEN FOR A COLUMN HEADING,
    so it arrives capitalised — "People in care". Dropped into a sentence that
    reads "30,000 ₫ for each People in care" it announces that the sentence was
    assembled by a programme. Only the FIRST letter is touched, and only when
    the second is lower case: an initialism or a proper noun the product chose
    is left exactly as it was written.
    """
    text = (label or '').strip()
    if len(text) < 2 or not text[0].isupper() or not text[1].islower():
        return text
    return text[0].lower() + text[1:]


def qty_text(qty):
    """A quantity without a pointless ".0" behind it."""
    try:
        value = float(qty or 0)
    except (TypeError, ValueError):
        return '0'
    if abs(value - round(value)) < 1e-9:
        return '{:,}'.format(int(round(value)))
    return '{:,.2f}'.format(value)


# =============================================================================
# Periods
# =============================================================================

def month_start(day):
    """The first of the month `day` falls in."""
    return date(day.year, day.month, 1)


def month_end(period):
    """The last day of the month that starts at `period`."""
    if period.month == 12:
        nxt = date(period.year + 1, 1, 1)
    else:
        nxt = date(period.year, period.month + 1, 1)
    return nxt - timedelta(days=1)


def next_month(period):
    if period.month == 12:
        return date(period.year + 1, 1, 1)
    return date(period.year, period.month + 1, 1)


def prev_month(period):
    if period.month == 1:
        return date(period.year - 1, 12, 1)
    return date(period.year, period.month - 1, 1)


MONTH_NAMES = ('January', 'February', 'March', 'April', 'May', 'June', 'July',
               'August', 'September', 'October', 'November', 'December')


def period_label(period):
    """"September 2026"."""
    if not period:
        return ''
    return '%s %d' % (MONTH_NAMES[period.month - 1], period.year)


def month_closed(period, today):
    """Is the month that starts at `period` over?

    An invoice raised mid-month is an invoice for a month that has not finished
    happening, and the numbers on it will be wrong by whatever comes next. It is
    allowed — the owner may genuinely want to invoice early — but it is allowed
    on purpose, with a warning, rather than by accident.
    """
    return bool(period and today and today > month_end(period))


def months_back(period, count):
    """`[period, the one before it, …]`, newest first. For the month strip."""
    out, cur = [], period
    for _i in range(max(1, int(count or 1))):
        out.append(cur)
        cur = prev_month(cur)
    return out


# =============================================================================
# What a plan charges
# =============================================================================

def pick_tier(tiers, value):
    """The band a customer of this size falls in, or None.

    Bands are "up to N". THE LAST BAND IS OPEN-ENDED however small its number
    is, because a plan whose top band is "up to 300" must still be able to
    invoice the customer who took on their 301st — silently charging nothing
    would be worse than charging the top band.

    ⚠ THE COMPARISON IS `<=`, NOT `<`. "Up to 100" includes 100. Getting that
    wrong moves exactly one customer a band and nobody notices for a year.
    """
    rows = sorted([t for t in (tiers or []) if t is not None],
                  key=lambda t: (t.get('up_to') or 0))
    if not rows:
        return None
    for tier in rows:
        if value <= (tier.get('up_to') or 0):
            return tier
    return rows[-1]


def price_for(plan, readings, unavailable=None):
    """The lines one customer's invoice carries this month, and why.

    `readings` is `{meter key: number}` as the platform MEASURED it at the time
    — never a number recomputed today (§3.3). `unavailable` is the set of keys
    that were not measurable at all, which is a different answer from nought.

    Returns `{'lines', 'problem', 'nothing_to_bill', 'explain'}`. A `problem` is
    a sentence for the person looking at the preview — a plan with no bands, a
    plan that does not say how it charges — and it is never an exception,
    because one broken plan must not stop the other eleven invoices from being
    previewed.

    `explain` is the arithmetic IN WORDS: "236 people in care × 30,000 ₫, 50
    included → 5,580,000 ₫". It is the whole point of the preview screen.
    """
    plan = plan or {}
    kind = plan.get('price_kind')
    name = (plan.get('name') or '').strip() or 'Plan'
    rounding = plan.get('rounding') or 0.01
    symbol = plan.get('symbol') or ''
    position = plan.get('position') or 'after'
    price = float(plan.get('price') or 0.0)
    key = (plan.get('meter_key') or '').strip()
    unit_label = unit_words(plan.get('meter_label') or key or '')
    unavailable = set(unavailable or ())

    def fmt(value):
        return money(value, symbol, rounding, position)

    if kind == 'flat':
        amount = round_money(price, rounding)
        return {
            'lines': [{
                'label': '%s — one month' % name,
                'detail': "One price a month, whatever they use.",
                'qty': 1.0, 'unit_price': price, 'amount': amount,
            }],
            'problem': '', 'nothing_to_bill': False,
            'explain': "One price a month → %s" % fmt(amount),
        }

    if kind in ('per_unit', 'flat_tier') and not key:
        return {'lines': [], 'nothing_to_bill': True, 'explain': '', 'problem': (
            "The %s plan does not say which number it charges on. Pick one on "
            "the plan." % name)}

    if kind in ('per_unit', 'flat_tier') and key in unavailable:
        return {'lines': [], 'nothing_to_bill': True, 'explain': '', 'problem': (
            "“%s” could not be measured on this system for that "
            "month, so there is nothing to charge on. It is left out rather "
            "than charged as nought." % (unit_label or key))}

    measured = int((readings or {}).get(key) or 0)

    if kind == 'per_unit':
        included = max(0, int(plan.get('included') or 0))
        minimum = float(plan.get('minimum') or 0.0)
        chargeable = max(0, measured - included)
        raw = round_money(chargeable * price, rounding)
        amount = raw
        floored = False
        if minimum and amount < minimum:
            amount = round_money(minimum, rounding)
            floored = True
        detail_bits = ["%s %s" % (qty_text(measured), unit_label or key)]
        if included:
            detail_bits.append("%s included" % qty_text(included))
        if minimum:
            detail_bits.append("least %s a month" % fmt(minimum))
        explain = "%s %s × %s" % (qty_text(measured), unit_label or key,
                                  fmt(price))
        if included:
            explain += ", %s included" % qty_text(included)
        explain += " → %s" % fmt(raw)
        if floored:
            explain += ", brought up to the %s minimum → %s" % (fmt(minimum),
                                                                fmt(amount))
        return {
            'lines': [{
                'label': '%s — %s' % (name, unit_label or key),
                'detail': ', '.join(detail_bits) + '.',
                'qty': float(chargeable), 'unit_price': price,
                'amount': amount,
            }],
            'problem': '',
            # A minimum is exactly the thing that makes a quiet month billable,
            # so "nothing to bill" is about the AMOUNT and not about the count.
            'nothing_to_bill': amount <= 0,
            'explain': explain,
        }

    if kind == 'flat_tier':
        tier = pick_tier(plan.get('tiers'), measured)
        if not tier:
            return {'lines': [], 'nothing_to_bill': True, 'explain': '',
                    'problem': (
                        "The %s plan charges one price by size band, and it has "
                        "no bands yet. Add at least one on the plan." % name)}
        up_to = int(tier.get('up_to') or 0)
        band = ('up to %s' % qty_text(up_to)) if up_to else 'any size'
        amount = round_money(tier.get('price') or 0.0, rounding)
        return {
            'lines': [{
                'label': '%s — one month (%s %s)' % (name, band,
                                                     unit_label or key),
                'detail': "%s %s measured for the month."
                          % (qty_text(measured), unit_label or key),
                'qty': 1.0, 'unit_price': float(tier.get('price') or 0.0),
                'amount': amount,
            }],
            'problem': '', 'nothing_to_bill': False,
            'explain': "%s %s falls in the “%s” band → %s"
                       % (qty_text(measured), unit_label or key, band,
                          fmt(amount)),
        }

    return {'lines': [], 'nothing_to_bill': True, 'explain': '', 'problem': (
        "The %s plan does not say how it charges. Pick a price structure on "
        "the plan." % name)}


def invoice_totals(lines, vat_rate=0.0, rounding=0.01):
    """Subtotal, tax and total — each rounded by the currency, in that order.

    The subtotal is rounded BEFORE the tax is worked out, so the tax on the
    invoice is the tax on the number printed above it. Doing it the other way
    round produces a total that is off by one dong and an argument nobody can
    win.
    """
    subtotal = round_money(sum(float(l.get('amount') or 0.0)
                               for l in (lines or [])), rounding)
    try:
        pct = float(vat_rate or 0.0)
    except (TypeError, ValueError):
        pct = 0.0
    vat_amount = round_money(subtotal * pct / 100.0, rounding)
    return {
        'subtotal': subtotal,
        'vat_rate': pct,
        'vat_amount': vat_amount,
        'total': round_money(subtotal + vat_amount, rounding),
    }


# =============================================================================
# What happens to an invoice as the days pass
# =============================================================================

def due_date_for(issued_on, due_days=DEFAULT_DUE_DAYS):
    if not issued_on:
        return None
    return issued_on + timedelta(days=int(due_days or DEFAULT_DUE_DAYS))


def overdue_days(invoice, today):
    """How many days past its due date, or 0. PURE, and it never guesses."""
    inv = invoice or {}
    if (inv.get('state') or 'draft') != 'issued':
        return 0
    due = inv.get('due_on')
    if not due or not today:
        return 0
    return max(0, (today - due).days)


def next_state(invoice, today, reminder_days=DEFAULT_REMINDER_DAYS,
               suspend_after=DEFAULT_SUSPEND_AFTER_DAYS):
    """One invoice, one day, one decision.

    Returns `{'days_overdue', 'remind', 'reminder_no', 'suspend_candidate'}`.

    ⚠ THE REMINDERS ARE COUNTED, NOT TIMED. `reminder_count` on the record is
    what decides whether the +3 note has already gone, so a job that runs twice
    on the same morning — or a box that was switched off for a week — raises
    each reminder exactly once rather than one per run or none at all.
    """
    inv = invoice or {}
    out = {'days_overdue': 0, 'remind': False, 'reminder_no': 0,
           'suspend_candidate': False}
    days = overdue_days(inv, today)
    if days <= 0:
        return out
    out['days_overdue'] = days
    sent_count = int(inv.get('reminder_count') or 0)
    steps = sorted(int(d) for d in (reminder_days or ()))
    due_now = [i + 1 for i, d in enumerate(steps) if days >= d]
    if due_now and sent_count < due_now[-1]:
        out['remind'] = True
        out['reminder_no'] = sent_count + 1
    if suspend_after and days >= int(suspend_after):
        out['suspend_candidate'] = True
    return out


def invoice_number(prefix, year, seq):
    """"CX-2026-0001" — readable, sortable, and unique inside a year.

    A SEQUENCE PER YEAR (§3.4), read off the invoices that exist rather than
    off a sequence record: a sequence bumped inside a transaction that is then
    rolled back leaves a gap, and a gap in an invoice book is a question from
    an auditor with no good answer.
    """
    pre = (prefix or 'INV').strip() or 'INV'
    if not year:
        return '%s-%04d' % (pre, int(seq or 1))
    return '%s-%d-%04d' % (pre, int(year), int(seq or 1))


# =============================================================================
# Trials, seats and the retention clock
# =============================================================================

def trial_phase(trial_ends, today, warn_days=TRIAL_WARN_DAYS):
    """Where a trial stands: `none`, `ok`, `ending` or `ended`.

    An unset date reads as `False` on this framework rather than `None`
    (ledger F23), so the test is falsiness and never identity.
    """
    if not trial_ends or not today:
        return {'phase': 'none', 'days_left': 0}
    days = (trial_ends - today).days
    if days < 0:
        return {'phase': 'ended', 'days_left': days}
    if days <= int(warn_days or TRIAL_WARN_DAYS):
        return {'phase': 'ending', 'days_left': days}
    return {'phase': 'ok', 'days_left': days}


def trial_sentence(days_left, brand=''):
    """The countdown, in the words somebody reads on their own screen."""
    who = (brand or '').strip() or 'this system'
    if days_left is None:
        return ''
    if days_left < 0:
        return "Your trial of %s has ended." % who
    if days_left == 0:
        return "Your trial of %s ends today." % who
    if days_left == 1:
        return "Your trial of %s ends tomorrow." % who
    return "Your trial of %s ends in %d days." % (who, int(days_left))


def seat_verdict(limit, count, near_pct=SEAT_NEAR_PCT):
    """`ok`, `near` or `full` — and a limit of nought means no limit at all."""
    try:
        limit = int(limit or 0)
    except (TypeError, ValueError):
        limit = 0
    try:
        count = int(count or 0)
    except (TypeError, ValueError):
        count = 0
    if limit <= 0:
        return {'verdict': 'ok', 'limit': 0, 'count': count, 'left': -1,
                'pct': 0}
    left = limit - count
    pct = int(round(min(count, limit) * 100.0 / limit))
    if count >= limit:
        return {'verdict': 'full', 'limit': limit, 'count': count, 'left': 0,
                'pct': 100}
    if count >= limit * float(near_pct or SEAT_NEAR_PCT):
        return {'verdict': 'near', 'limit': limit, 'count': count,
                'left': left, 'pct': pct}
    return {'verdict': 'ok', 'limit': limit, 'count': count, 'left': left,
            'pct': pct}


def seat_refusal(limit, count, plan_name='', contact=''):
    """Why the account was not created, and what to do about it.

    ZERO DEAD ENDS: the sentence names the number, the plan and who can change
    it. "Limit reached" on its own is a wall.
    """
    plan = (plan_name or '').strip()
    who = (contact or '').strip()
    text = ("Your plan%s allows %s people with a login and you already have "
            "%s." % ((' (%s)' % plan) if plan else '',
                     qty_text(limit), qty_text(count)))
    text += (" Ask for a larger plan, or switch off somebody who has left, and "
             "this will let you carry on.")
    if who:
        text += " Get in touch at %s." % who
    return text


def retention_verdict(delete_after, today):
    """Where a customer scheduled for closing stands. NOTHING EVER DELETES.

    Returns `{'phase': 'none'|'waiting'|'due', 'days_left': int}`. `due` means
    the platform may now OFFER the button; it has never meant that anything
    happens on its own, and nothing in this programme ever will.
    """
    if not delete_after or not today:
        return {'phase': 'none', 'days_left': 0}
    days = (delete_after - today).days
    return {'phase': 'due' if days <= 0 else 'waiting', 'days_left': days}


# =============================================================================
# Moving a customer from one standing to another
# =============================================================================

def state_transition(frm, to):
    """Is this move allowed? Returns `(ok, reason)`."""
    words = lambda s: str(s or '').replace('_', ' ')          # noqa: E731
    if frm == to:
        return False, "They are already %s." % words(to)
    if to not in TENANT_STATES:
        return False, "There is no such standing."
    if frm == 'decommissioned':
        return False, ("That customer has been closed down — there is no "
                       "system left to change. Start them again from their own "
                       "record instead.")
    if (frm, to) in STATE_MOVES:
        return True, ''
    return False, ("A customer cannot go from %s to %s." % (words(frm),
                                                            words(to)))


def access_payload(state, reason='', trial_ends=None, plan_name='',
                   plan_line='', seat_limit=0, brand=''):
    """What a customer's own system is told about where they stand.

    Every value is a STRING, because that is all a settings row holds. `open`
    and `paused` are the only two answers to "may these people in": a customer
    on a trial is open, a customer scheduled for closing is open, and there is
    deliberately no third door.
    """
    access = 'paused' if state == 'paused' else 'open'
    text = (reason or '').strip()
    if access == 'paused' and not text:
        who = (brand or '').strip() or 'the people who run this system'
        text = ("Your access is paused. Please get in touch with %s." % who)
    return {
        'access': access,
        'access_text': text if access == 'paused' else '',
        'trial_ends': trial_ends.isoformat() if trial_ends else '',
        'plan_name': plan_name or '',
        'plan_line': plan_line or '',
        'seat_limit': str(int(seat_limit or 0)),
    }
