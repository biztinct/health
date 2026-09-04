# -*- coding: utf-8 -*-
"""What this system has been told about its own standing.

TEN MORE SETTINGS, READ HERE AND WRITTEN NOWHERE.

    biz_tenancy.access          "open" or "paused"
    biz_tenancy.access_text     the sentence shown on the page a paused
                                system's people meet
    biz_tenancy.trial_ends      the last day of the trial, or empty
    biz_tenancy.plan_name       what they pay for, in words
    biz_tenancy.plan_line       the price in one line
    biz_tenancy.seat_limit      how many people with a login, 0 = no limit
    biz_tenancy.seat_model      which record a seat limit counts
    biz_tenancy.usage           what the platform measured, as JSON
    biz_tenancy.next_invoice    one sentence about the next one
    biz_tenancy.recovery_login  the one account that still gets in when paused

⚠ WHY THE RULES ARE COPIED RATHER THAN IMPORTED. The cockpit is the platform's
own screen and is never installed here — the never-list is the whole point of
it. So the two small judgements this system has to make for itself (is the trial
ending, is it at its seat limit) are written out again, in the same words, the
way `read_features` already repeats the platform's own reading. Twenty lines of
arithmetic duplicated is a better trade than a customer's system depending on
the platform's billing code, and a test on the platform side asserts the two
copies agree.

AND IT FAILS OPEN, EVERY TIME. A system that has never been told anything reads
"no answer" as: access is open, there is no trial, there is no limit. That is
the only safe direction — the alternative is a working system locked out of its
own records because a settings row was empty.
"""
import json
import logging
import time

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

P_ACCESS = 'biz_tenancy.access'
P_ACCESS_TEXT = 'biz_tenancy.access_text'
P_TRIAL_ENDS = 'biz_tenancy.trial_ends'
P_PLAN_NAME = 'biz_tenancy.plan_name'
P_PLAN_LINE = 'biz_tenancy.plan_line'
P_SEAT_LIMIT = 'biz_tenancy.seat_limit'
P_SEAT_MODEL = 'biz_tenancy.seat_model'
P_USAGE = 'biz_tenancy.usage'
P_NEXT_INVOICE = 'biz_tenancy.next_invoice'
P_RECOVERY = 'biz_tenancy.recovery_login'

#: A trial is announced on the reader's own screen for this many days at the
#: end of it. The same number the platform counts down by.
TRIAL_WARN_DAYS = 10
#: The share of the limit at which somebody is warned rather than refused.
SEAT_NEAR_PCT = 0.9

#: How long the count is remembered before it is taken again. `state()` runs on
#: EVERY page load of EVERY person, and a count over a table on every one of
#: those is a cost nobody agreed to. Five minutes is far shorter than the time
#: it takes anybody to add enough people to cross a limit.
SEAT_CACHE_SECONDS = 300

#: `{(dbname, model): (taken_at, count)}`. Per process, thrown away on a
#: restart, and a wrong answer costs one bar shown five minutes late.
_SEAT_CACHE = {}


# ============================================================== pure functions

def trial_phase(trial_ends, today, warn_days=TRIAL_WARN_DAYS):
    """`none` / `ok` / `ending` / `ended`, and how many days are left."""
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
    who = (brand or '').strip() or "this system"
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
    """`ok`, `near` or `full`. A limit of nought means no limit at all."""
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
    pct = int(round(min(count, limit) * 100.0 / limit))
    if count >= limit:
        return {'verdict': 'full', 'limit': limit, 'count': count, 'left': 0,
                'pct': 100}
    if count >= limit * float(near_pct or SEAT_NEAR_PCT):
        return {'verdict': 'near', 'limit': limit, 'count': count,
                'left': limit - count, 'pct': pct}
    return {'verdict': 'ok', 'limit': limit, 'count': count,
            'left': limit - count, 'pct': pct}


def seat_refusal(limit, count, plan_name='', contact=''):
    """Why the account was not created, and what to do about it.

    ZERO DEAD ENDS: the sentence names the number, the plan and who to ask.
    "Limit reached" on its own is a wall.
    """
    plan = (' (%s)' % plan_name.strip()) if (plan_name or '').strip() else ''
    who = (contact or '').strip()
    text = ("Your plan%s allows %s people with a login and you already have "
            "%s." % (plan, '{:,}'.format(int(limit or 0)),
                     '{:,}'.format(int(count or 0))))
    text += (" Ask for a larger plan, or switch off somebody who has left, and "
             "this will let you carry on.")
    if who:
        text += " Get in touch at %s." % who
    return text


def read_usage(raw):
    """What the platform measured, from the setting. Damage reads as none."""
    if not raw:
        return {'month': '', 'month_label': '', 'rows': []}
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        _logger.warning("biz_tenancy: the usage figures on this system could "
                        "not be read (%s is not valid JSON). The plan card "
                        "shows no numbers rather than wrong ones.", P_USAGE)
        return {'month': '', 'month_label': '', 'rows': []}
    if not isinstance(data, dict):
        return {'month': '', 'month_label': '', 'rows': []}
    rows = []
    for row in (data.get('rows') or []):
        if not isinstance(row, dict) or not row.get('key'):
            continue
        rows.append({
            'key': str(row.get('key') or ''),
            'label': str(row.get('label') or row.get('key') or ''),
            'unit': str(row.get('unit') or ''),
            'value': int(row.get('value') or 0),
            'available': bool(row.get('available', True)),
            'charged': bool(row.get('charged', False)),
        })
    return {'month': str(data.get('month') or ''),
            'month_label': str(data.get('month_label') or ''),
            'rows': rows}


def standing_signature(access, trial_phase_name, seat, plan_name):
    """ONE STRING THAT CHANGES ONLY WHEN THE ANSWER CHANGES (ledger F47).

    Every screen that has to repaint when the standing moves watches this
    rather than the objects it is built from, which are rebuilt on every read
    and would repaint once a minute for ever.
    """
    return '%s|%s|%s|%s|%s' % (access, trial_phase_name,
                               (seat or {}).get('verdict') or 'ok',
                               (seat or {}).get('count') or 0,
                               plan_name or '')


class BizTenancyStanding(models.AbstractModel):
    """Added to the model the release, the notices and the switches live on."""
    _inherit = 'biz.tenancy'

    # ------------------------------------------------------------------ reads
    @api.model
    def access_state(self):
        """`open` or `paused`, plus the sentence to show. NEVER RAISES."""
        access = (self._text(P_ACCESS) or 'open').strip().lower()
        if access != 'paused':
            access = 'open'
        text = (self._text(P_ACCESS_TEXT) or '').strip()
        if access == 'paused' and not text:
            text = self.env._(
                "Your access is paused. Please get in touch with the people "
                "who run %s.", self.brand())
        return {'access': access, 'access_text': text}

    @api.model
    def is_paused(self):
        return self.access_state()['access'] == 'paused'

    @api.model
    def recovery_login(self):
        """The one account that still gets in while this system is paused.

        Mirrored onto this system on purpose, so the door can decide for
        itself: a locked door that needs the platform to be reachable is a
        locked door that locks the platform's own engineer out on the day the
        platform is broken.
        """
        return (self._text(P_RECOVERY) or '').strip().lower()

    @api.model
    def seat_model(self):
        """Which record a seat limit counts. Empty means "no limit anywhere"."""
        return (self._text(P_SEAT_MODEL) or '').strip()

    @api.model
    def seat_limit(self):
        """⚠ ABSENT AND EMPTY ARE DIFFERENT ANSWERS (ledger F24).

        No row at all means the platform has never said, which is no limit.
        A row set to "0" means somebody deliberately said "no limit", which is
        the same outcome and a different fact — and the day a limit is pushed,
        `get_param`'s `or default` would have hidden the difference between the
        two while somebody debugged why a refusal was not happening.
        """
        raw = self._row(P_SEAT_LIMIT)
        if raw is None or raw == '':
            return 0
        try:
            return max(0, int(str(raw).strip()))
        except (TypeError, ValueError):
            _logger.warning("biz_tenancy: the seat limit on this system is "
                            "not a number (%r); it is read as no limit.", raw)
            return 0

    @api.model
    def seat_count(self, fresh=False):
        """How many records the limit counts, at most every five minutes.

        Straight SQL rather than a search: this runs on every page load and
        must cost one count on one table, not a record set.
        """
        model_name = self.seat_model()
        if not model_name or model_name not in self.env:
            return 0
        table = self.env[model_name]._table
        cache_key = (self.env.cr.dbname, table)
        now = time.time()
        cached = _SEAT_CACHE.get(cache_key)
        if not fresh and cached and now - cached[0] < SEAT_CACHE_SECONDS:
            return cached[1]
        count = 0
        try:
            # `share IS NOT TRUE` where the table has it: a portal account is
            # not a person with a login in the sense anybody is sold on.
            self.env.cr.execute(
                "SELECT count(*) FROM information_schema.columns "
                "WHERE table_name = %s AND column_name = 'share'", (table,))
            has_share = bool((self.env.cr.fetchone() or [0])[0])
            sql = 'SELECT count(*) FROM "%s" WHERE active' % table
            if has_share:
                sql += ' AND share IS NOT TRUE'
            self.env.cr.execute(sql)
            count = int((self.env.cr.fetchone() or [0])[0] or 0)
        except Exception:                                    # noqa: BLE001
            _logger.warning("biz_tenancy: could not count %s on this system",
                            model_name, exc_info=True)
            return cached[1] if cached else 0
        _SEAT_CACHE[cache_key] = (now, count)
        return count

    @api.model
    def seat_state(self, fresh=False):
        """Where this system stands against its limit."""
        limit = self.seat_limit()
        if limit <= 0:
            # No limit means nothing to count, and nothing to count means the
            # cheapest possible answer on every page load.
            return seat_verdict(0, 0)
        return seat_verdict(limit, self.seat_count(fresh=fresh))

    @api.model
    def trial_state(self):
        raw = (self._text(P_TRIAL_ENDS) or '').strip()
        empty = {'phase': 'none', 'days_left': 0, 'ends': '', 'text': ''}
        if not raw:
            return empty
        try:
            ends = fields.Date.to_date(raw)
        except (ValueError, TypeError):
            return empty
        if not ends:
            return empty
        phase = trial_phase(ends, fields.Date.context_today(self))
        return dict(phase, ends=ends.isoformat(),
                    text=(trial_sentence(phase['days_left'], self.brand())
                          if phase['phase'] in ('ending', 'ended') else ''))

    @api.model
    def plan_name(self):
        return (self._text(P_PLAN_NAME) or '').strip()

    # ------------------------------------------------- the one chrome answer
    @api.model
    def state(self):
        """The release, the notices, the switches — and now the standing.

        Still one dict read in one go on every page load. The one addition that
        could cost anything is guarded: the count is only taken when there is a
        limit at all, and it is remembered for five minutes when there is.
        """
        data = super().state()
        access = self.access_state()
        seat = self.seat_state()
        trial = self.trial_state()
        plan = self.plan_name()
        data.update({
            'access': access['access'],
            'access_text': access['access_text'],
            'plan_name': plan,
            'plan_line': (self._text(P_PLAN_LINE) or '').strip(),
            'trial': trial,
            'seat': seat,
            'standing_sig': standing_signature(access['access'],
                                               trial['phase'], seat, plan),
        })
        return data

    # -------------------------------------------------------- the plan card
    @api.model
    def plan_usage(self):
        """Everything the "Plan & usage" card draws. READ-ONLY.

        ⚠ THE NUMBERS COME FROM THE PLATFORM, NOT FROM A SECOND COUNT HERE.
        The platform is the thing that measures, and it measures once a month
        and keeps the answer; a count taken again here would answer a slightly
        different question and the two screens would disagree by one for ever.
        The only number counted here is the seat count, because that one is
        about right NOW rather than about a month.
        """
        usage = read_usage(self._text(P_USAGE))
        limit = self.seat_limit()
        seat = seat_verdict(limit, self.seat_count(fresh=True)) if limit \
            else seat_verdict(0, self.seat_count(fresh=True))
        return {
            'brand': self.brand(),
            'plan_name': self.plan_name(),
            'plan_line': (self._text(P_PLAN_LINE) or '').strip(),
            'trial': self.trial_state(),
            'access': self.access_state(),
            'seat': seat,
            'seat_model': self.seat_model(),
            'usage': usage,
            'next_invoice': (self._text(P_NEXT_INVOICE) or '').strip(),
            'support_email': self._text('biz_tenancy.support_email').strip(),
            'pushed_at': (self._text('biz_tenancy.pushed_at') or '').strip(),
        }

    # --------------------------------------------------------- the seat gate
    @api.model
    def seat_gate(self, adding=1):
        """May this system take on `adding` more? `''` or the refusal sentence.

        THE ONE PLACE THE QUESTION IS ASKED, so the product's own override has
        one line in it and every exemption lives here. Three things pass
        whatever the limit says:

          * the recovery account, which is the platform's way back in;
          * an active support session, because somebody from the platform
            fixing a problem must never be stopped by the problem;
          * a system where no limit has been pushed at all.

        ⚠ AND IT IS COUNTED FRESH. The five-minute cache is right for a bar at
        the top of a page and wrong for a refusal: a limit that lets one extra
        through because a count is four minutes old is a limit somebody will
        find by accident.
        """
        limit = self.seat_limit()
        if limit <= 0:
            return ''
        if self._seat_exempt():
            return ''
        count = self.seat_count(fresh=True)
        if count + max(1, int(adding or 1)) <= limit:
            return ''
        return seat_refusal(limit, count, self.plan_name(),
                            self._text('biz_tenancy.support_email').strip())

    @api.model
    def _seat_exempt(self):
        """The recovery account and an active support session, and nobody else."""
        user = self.env.user
        if not user:
            return False
        recovery = self.recovery_login()
        if recovery and (user.login or '').strip().lower() == recovery:
            return True
        try:
            if self.env['biz.support.session'].sudo().current():
                return True
        except Exception:                                    # noqa: BLE001
            # A missing support table is not a reason to refuse somebody a
            # colleague; the limit itself is unaffected.
            _logger.debug("biz_tenancy: could not read the support session "
                          "while checking the limit", exc_info=True)
        return False
