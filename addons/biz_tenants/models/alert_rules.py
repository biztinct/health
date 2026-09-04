# -*- coding: utf-8 -*-
"""What counts as a problem, how the platform says so, and what the world reads.

Same shape as `rollout_rules.py` and for the same reason (rail R6): everything
this feature DOES happens somewhere a test cannot go — a customer's system, a
mail account, a file the web server hands out. So every JUDGEMENT lives here,
pure, with no import of the framework at all, and what is left at the call site
is a read, a write and a send.

THE FIVE JUDGEMENTS.
  * `readings_to_alerts` — a plain dict of measurements in, a list of problems
    out. Nothing else in the platform decides what is wrong.
  * `reconcile` — what is new, what is still going on, what is over.
  * `should_notify` — has this one earned a message yet.
  * `digest_lines` — the morning summary's words.
  * `status_state` / `render_status_page` — the public page.

EVERY ALERT CARRIES ITS NEXT STEP. Not "disk 87% full" — "the disk is 87% full;
old copies are the usual cause, remove some on a customer's Copies tab". An
alert that hands somebody a number and leaves them to work out the rest is an
alert they learn to scroll past.

AND NOTHING HERE NAMES A CUSTOMER ON THE PUBLIC PAGE. `status_state()` is the
ONE DOOR between what the platform knows and what the world reads, and it
copies only kinds, levels and durations across it. A test feeds it a state full
of customer names and asserts that none of them come out.

WHITE-LABEL. Not one sentence in this file names a product, a company or the
software underneath. The brand arrives as an argument; a test asserts that the
word "odoo" appears in no string any of these functions can produce.
"""
import html
from datetime import datetime, timedelta

# =============================================================================
# 1. KINDS, SEVERITIES, THRESHOLDS
# =============================================================================

#: Every kind of problem the platform knows how to notice. The order is the
#: order they are looked for, which is also the order they read in a summary.
ALERT_KINDS = (
    'tenant_unreachable',       # a customer's address did not answer
    'tenant_errors',            # a customer's system logged errors
    'backup_missing',           # no copy has ever been taken, or the last failed
    'backup_stale',             # no recent copy
    'backup_small',             # a copy was written and it is not a real one
    'cert_missing',             # no certificate of their own
    'cert_expiring',
    'disk_low',
    'memory_low',
    'capacity_full',            # no room for another customer
    'rollout_stopped',
    'status_page_unwritable',
    'mail_not_configured',      # the platform cannot reach a person at all
    # ⚠ THE TWO THAT ARE NOT FAULTS. A support session is an ACT: somebody
    # from this platform went into a customer's system. It is raised on the
    # PRESS OF THE BUTTON and not by the sweep (ledger F67), because a
    # thirty-minute session ended after two is over before the sweep ever
    # looks — and the owner would hear nothing at all about somebody being
    # inside a live customer's system.
    'support_session',
    'support_refused',          # somebody tried, and the customer said no
)

SEVERITIES = ('critical', 'warning', 'info')
SEVERITY_ORDER = {'info': 0, 'warning': 1, 'critical': 2}

#: What each kind is called on screen, in the words of the thing it is about.
KIND_LABEL = {
    'tenant_unreachable': "A customer cannot be reached",
    'tenant_errors': "A customer's system is logging errors",
    'backup_missing': "A customer has no copy at all",
    'backup_stale': "A customer has no recent copy",
    'backup_small': "A copy was taken and it is not a real one",
    'cert_missing': "A customer's address is not secured",
    'cert_expiring': "A certificate is running out",
    'disk_low': "The machine is running out of disk",
    'memory_low': "The machine is running out of memory",
    'capacity_full': "No room for another customer",
    'rollout_stopped': "A release stopped part-way",
    'status_page_unwritable': "The public page cannot be written",
    'mail_not_configured': "Nothing can be emailed from this platform",
    'support_session': "Somebody from this platform went into a customer's system",
    'support_refused': "A customer refused support access",
}

#: Which glyph the screen draws. Named from the shared icon set, so a kind
#: added later without an entry still draws something rather than nothing.
KIND_ICON = {
    'tenant_unreachable': 'activity',
    'tenant_errors': 'alert',
    'backup_missing': 'archive',
    'backup_stale': 'archive',
    'backup_small': 'archive',
    'cert_missing': 'lock',
    'cert_expiring': 'lock',
    'disk_low': 'hardDrive',
    'memory_low': 'gauge',
    'capacity_full': 'gauge',
    'rollout_stopped': 'pause',
    'status_page_unwritable': 'globe',
    'mail_not_configured': 'bellOff',
    'support_session': 'shield',
    # `lock` and not a crossed-out shield: the shared icon set has no such
    # glyph, and a name it does not know draws nothing at all.
    'support_refused': 'lock',
}

#: Kinds the sweep NEVER resolves on its own, because no reading can see them.
#:
#: Everything the sweep MEASURES is resolved by the sweep — `mail_not_configured`
#: included, which clears the moment an outgoing mail account exists.
#:
#: ⚠ THE TWO SUPPORT KINDS ARE HERE BECAUSE THEY ARE ACTS AND NOT FAULTS
#: (ledger F67). They are raised on the press of a button and closed when the
#: door is shut, both by the code that does those things. The sweep does not
#: measure them at all, so if they were not on this list the very first sweep
#: after a session started would decide it had cleared and close it — fifteen
#: minutes of a thirty-minute session, quietly resolved.
SELF_MANAGED_KINDS = ('support_session', 'support_refused')

#: Every number this file judges by, in one place, each overridable as a
#: setting. They are ARGUMENTS and not constants so a test can sit exactly on
#: the edge of each one, and so an operator can move one without a deploy.
DEFAULT_THRESHOLDS = {
    # Disk. Copies and a working clinic both write here.
    'disk_free_pct': 12,
    'disk_free_gb': 4.0,
    'disk_critical_pct': 5,
    # Memory, as MemAvailable in MB.
    'mem_available_mb': 250,
    'mem_critical_mb': 120,
    # Copies. The nightly job runs at 19:30, so 30 hours means one was missed.
    'backup_stale_hours': 30,
    # Certificates. A customer's own renews itself; the notice is short.
    'cert_days': 14,
    'cert_critical_days': 5,
    # Error lines from one system inside the sweep's own window.
    'error_lines': 3,
    # How old the public page may get before it is a problem.
    'status_page_minutes': 15,
}

#: How long a copy has to be to be a copy at all. Ledger H70: a threshold taken
#: from an incident has to EXCLUDE the incident's own number. The wreckage was
#: a 9 MB archive with five files in it, so `files < 5` would have passed the
#: very archive it was written for.
BACKUP_MIN_FILES = 20


def _th(thresholds=None):
    """The thresholds, with anything not given falling back to the default."""
    out = dict(DEFAULT_THRESHOLDS)
    for key, val in (thresholds or {}).items():
        if key in out and val not in (None, ''):
            out[key] = val
    return out


def _alert(key, kind, severity, title, text, tenant_id=None):
    return {'key': key, 'kind': kind, 'severity': severity,
            'title': title, 'text': text, 'tenant_id': tenant_id}


def _plural(n, word):
    """"for 1 hour", never "for 1 hours". A screen that cannot count to one is
    a screen that announces it was written by a programme rather than by a
    person."""
    return 'for %d %s%s' % (n, word, '' if n == 1 else 's')


def _hours_since(then, now):
    if not then or not now:
        return None
    return (now - then).total_seconds() / 3600.0


# =============================================================================
# 2. READINGS -> ALERTS
# =============================================================================
def readings_to_alerts(readings, thresholds=None):
    """Every problem the platform can currently see, in one list.

    `readings` is a plain dict — see `_gather_readings()` next door for the
    shape. A MISSING KEY MEANS "NOT MEASURED" and is skipped rather than
    guessed at: a reading nobody took must never raise an alarm, and must never
    silence one either.
    """
    t = _th(thresholds)
    now = (readings or {}).get('now') or datetime.utcnow()
    out = []
    for row in (readings or {}).get('tenants') or ():
        out.extend(_tenant_alerts(row, t, now))
    out.extend(_platform_alerts(readings or {}, t, now))
    order = {k: i for i, k in enumerate(ALERT_KINDS)}
    out.sort(key=lambda a: (order.get(a['kind'], 99), a['key']))
    return out


def _tenant_alerts(row, t, now):
    """One customer's problems. `row` is a reading, not a record."""
    out = []
    if (row.get('state') or '') != 'live':
        return out
    name = row.get('name') or row.get('slug') or 'a customer'
    slug = row.get('slug') or str(row.get('id') or '')
    tid = row.get('id')

    # --- is their address answering at all
    if row.get('health') == 'down':
        out.append(_alert(
            'tenant_unreachable:%s' % slug, 'tenant_unreachable', 'critical',
            "%s cannot be reached" % name,
            "Their address did not answer when this machine asked it for a "
            "page, so nobody at %s can sign in. What to do next: open them on "
            "the Customers screen and press Refresh, which asks again. If it "
            "is still not answering, the machine itself needs looking at — and "
            "if it comes to it, last night's copy can be put back."
            % name, tid))

    # --- copies. A clinic without one is the worst state to be in.
    if row.get('last_backup_failed'):
        out.append(_alert(
            'backup_missing:%s' % slug, 'backup_missing', 'critical',
            "The last copy of %s failed" % name,
            "The last attempt to copy %s did not finish, and the reason is on "
            "their Copies tab. What to do next: open them and press \"Copy "
            "now\". If it fails again, the usual cause is the machine running "
            "out of disk." % name, tid))
    elif row.get('last_backup_small'):
        out.append(_alert(
            'backup_small:%s' % slug, 'backup_small', 'critical',
            "The last copy of %s is not a real copy" % name,
            "A copy of %s was written, but the attachments archive inside it "
            "is far too small to be right — putting it back would give them a "
            "system with no documents in it. What to do next: open them, go to "
            "Copies, press \"Copy now\", and check that both of the two sizes "
            "it records are sensible." % name, tid))
    else:
        age = _hours_since(row.get('last_backup_at'), now)
        if age is None:
            out.append(_alert(
                'backup_missing:%s' % slug, 'backup_missing', 'critical',
                "%s has never been copied" % name,
                "There is no copy of %s anywhere on this machine, so there is "
                "nothing to put back if anything goes wrong with them. What to "
                "do next: open them and press \"Copy now\", then check the "
                "nightly job is switched on." % name, tid))
        elif age > t['backup_stale_hours']:
            out.append(_alert(
                'backup_stale:%s' % slug, 'backup_stale', 'critical',
                "%s has no recent copy" % name,
                "%s has not been copied %s. The nightly copy runs at 19:30. "
                "What to do next: open them and press \"Copy now\", then check "
                "the nightly job ran last night."
                % (name, _plural(int(age), 'hour')), tid))

    # --- their certificate
    if row.get('cert_state') == 'none':
        out.append(_alert(
            'cert_missing:%s' % slug, 'cert_missing', 'warning',
            "%s's address has no certificate of its own" % name,
            "A browser going to their address is being handed a certificate "
            "issued for a different name, and it warns every visitor away. "
            "What to do next: open them on the Customers screen and run the "
            "\"Secure the address\" step again.", tid))
    else:
        days = row.get('cert_days_left')
        if isinstance(days, int) and 0 <= days < t['cert_days']:
            sev = 'critical' if days < t['cert_critical_days'] else 'warning'
            out.append(_alert(
                'cert_expiring:%s' % slug, 'cert_expiring', sev,
                "%s's certificate runs out in %d days" % (name, days),
                "After that a browser warns every one of their people away "
                "from the site. It normally renews itself with a fortnight to "
                "spare. What to do next: nothing yet — if it is still counting "
                "down tomorrow, reissue it with the certificate section of the "
                "platform runbook.", tid))

    # --- their system complaining in the log
    lines = row.get('error_lines') or 0
    if lines >= t['error_lines']:
        out.append(_alert(
            'tenant_errors:%s' % slug, 'tenant_errors', 'warning',
            "%s is logging errors" % name,
            "%d errors came from %s in the last quarter of an hour. That is "
            "usually one screen or one scheduled job failing rather than the "
            "whole system. What to do next: open them on the Customers screen "
            "— the last few lines are on their Overview, and they name the "
            "part of the product that complained." % (lines, name), tid))
    return out


def _platform_alerts(r, t, now):
    """Everything about the machine rather than about one customer."""
    out = []

    # --- disk
    disk = r.get('disk') or {}
    free_pct = disk.get('free_pct')
    free_gb = disk.get('free_gb')
    if free_pct is not None and (
            free_pct < t['disk_free_pct']
            or (free_gb is not None and free_gb < t['disk_free_gb'])):
        sev = 'critical' if free_pct < t['disk_critical_pct'] else 'warning'
        out.append(_alert(
            'disk_low', 'disk_low', sev,
            "This machine is running out of disk",
            "%s%% free (%s GB). Copies and a working customer system both write "
            "to this disk, and a full disk stops both. What to do next: the usual cause "
            "is kept copies — open a customer's Copies tab and remove some old "
            "ones, or move them off this machine."
            % (free_pct, ('%.1f' % free_gb) if free_gb is not None else '?')))

    # --- memory
    mem = r.get('memory') or {}
    avail = mem.get('available_mb')
    total = mem.get('total_mb') or 0
    if avail is not None and avail < t['mem_available_mb']:
        sev = 'critical' if avail < t['mem_critical_mb'] else 'warning'
        out.append(_alert(
            'memory_low', 'memory_low', sev,
            "This machine is running out of memory",
            "%d MB free of %d MB. When memory runs out the whole platform "
            "restarts and everybody using it is signed out. What to do next: "
            "remove any practice copies, which each hold a system's worth of "
            "memory — and if this keeps happening, the machine needs to be "
            "made bigger. There is a one-page guide for that in "
            "docs/SAAS_RESIZE_RUNBOOK.md." % (int(avail), int(total))))

    # --- capacity, which is the same numbers asked a different question
    cap = r.get('capacity') or {}
    if cap.get('level') == 'full':
        out.append(_alert(
            'capacity_full', 'capacity_full', 'warning',
            "There is no room for another customer",
            "%s Nothing is broken and nobody is affected. What to do next: "
            "the next customer sold cannot be set up until this machine is "
            "made bigger — the one-page guide is docs/SAAS_RESIZE_RUNBOOK.md."
            % (cap.get('reason') or '')))

    # --- outgoing mail. NOT NOISE: it is the honest statement that this
    #     platform cannot reach a human, and it stays open until it can.
    mail = r.get('mail') or {}
    if mail and not mail.get('can_send'):
        out.append(_alert(
            'mail_not_configured', 'mail_not_configured', 'warning',
            "Nothing can be emailed from this platform",
            "%s Until then, everything the platform would have sent you is "
            "written down here on the Alerts screen instead, and nothing is "
            "lost. What to do next: connect an outgoing mail account, then "
            "press \"Send a test email\" on this screen to prove it works."
            % (mail.get('reason') or "There is no outgoing mail account.")))

    # --- a rollout that stopped
    roll = r.get('rollout') or {}
    if roll.get('state') == 'paused':
        out.append(_alert(
            'rollout_stopped', 'rollout_stopped', 'warning',
            "Release %s stopped part-way" % (roll.get('release') or ''),
            "%s Customers after the one it stopped on are still on the old "
            "release. What to do next: open the Rollout screen, read the reason "
            "on the ring that stopped, then either put it right and press "
            "Continue, or call the rollout off."
            % (roll.get('reason')
               or 'It stopped and is waiting for a person.')))

    # --- the public page
    sp = r.get('status_page') or {}
    if sp and not sp.get('writable', True):
        out.append(_alert(
            'status_page_unwritable', 'status_page_unwritable', 'warning',
            "The public page cannot be written",
            "%s Anybody checking the public address is reading an old page or "
            "none at all. What to do next: on the machine, create that folder "
            "and let this application write to it."
            % (sp.get('reason') or '')))
    return out


# =============================================================================
# 3. RECONCILING WHAT WE ALREADY KNEW
# =============================================================================
def reconcile(open_alerts, fresh, now):
    """What is new, what is still true, and what is over.

    Returns `(to_create, to_bump, to_resolve)`:
      * `to_create` — alert dicts nothing open matches, first and last sighting
        stamped;
      * `to_bump` — `(id, values)` for one that is still going on: its count
        goes up and its wording is refreshed, because the numbers inside it
        (days left, error count) move while the problem stays the same;
      * `to_resolve` — ids of alerts nothing measures any more.

    ONE ROW PER PROBLEM, EVER. The key is the identity: `backup_stale:hhh` is
    the same problem tonight as it was this morning, and saying so twice an hour
    is how somebody learns to ignore the sender.
    """
    fresh_by_key = {}
    for f in fresh or ():
        fresh_by_key.setdefault(f['key'], f)
    open_by_key = {}
    for a in open_alerts or ():
        if (a.get('state') or 'open') in ('open', 'acknowledged'):
            open_by_key.setdefault(a['key'], a)

    to_create, to_bump, to_resolve = [], [], []
    for key in sorted(fresh_by_key):
        f = fresh_by_key[key]
        known = open_by_key.get(key)
        if not known:
            row = dict(f)
            row.update({'first_seen': now, 'last_seen': now, 'count': 1,
                        'state': 'open'})
            to_create.append(row)
            continue
        to_bump.append((known['id'], {
            'last_seen': now,
            'count': int(known.get('count') or 0) + 1,
            'severity': f['severity'],
            'subject': f['title'],
            'body_text': f['text'],
        }))
    for key in sorted(open_by_key):
        a = open_by_key[key]
        if key in fresh_by_key:
            continue
        if a.get('kind') in SELF_MANAGED_KINDS:
            continue
        to_resolve.append(a['id'])
    return to_create, to_bump, to_resolve


def should_notify(alert, now, interval_critical=2, interval_warning=6):
    """Has this alert earned a message right now?

    The rules, in order, each there for a reason somebody lived:
      * an acknowledged alert never speaks again — acknowledging IS "I know";
      * a resolved one never speaks as a reminder;
      * one that has never been spoken always speaks;
      * one that got WORSE since it was spoken speaks again immediately,
        whatever the interval says — "the thing I told you about is now urgent"
        is new information;
      * otherwise it waits out its interval, in hours, by severity.

    An interval of 0 or less means "never remind", which is the setting
    somebody wants the week they are already looking at a known problem.
    """
    if not alert:
        return False
    if (alert.get('state') or 'open') != 'open':
        return False
    last = alert.get('spoken_at')
    if not last:
        return True
    sev = alert.get('severity') or 'warning'
    was = alert.get('spoken_severity') or sev
    if SEVERITY_ORDER.get(sev, 1) > SEVERITY_ORDER.get(was, 1):
        return True
    hours = interval_critical if sev == 'critical' else interval_warning
    try:
        hours = float(hours)
    except (TypeError, ValueError):
        hours = 6.0
    if hours <= 0:
        return False
    return (now - last) >= timedelta(hours=hours)


#: The three words, and they are the whole of ledger F68. An `info` alert
#: announced as "something needs your attention" is crying wolf about the one
#: thing that must never be scrolled past.
SEVERITY_WORD = {
    'critical': "Needs attention now",
    'warning': "Worth a look",
    'info': "For information",
}


def worst_severity(alerts):
    """The loudest severity in a group, or `info` for an empty one."""
    worst = 'info'
    for a in alerts or ():
        sev = (a.get('severity') if isinstance(a, dict) else a) or 'info'
        if SEVERITY_ORDER.get(sev, 0) > SEVERITY_ORDER.get(worst, 0):
            worst = sev
    return worst


def digest_lines(open_alerts, now=None):
    """The morning summary, one line each, worst first.

    An empty list when nothing is open — the caller writes the reassuring
    sentence, because only the caller knows how many customers there are to be
    reassuring about.
    """
    now = now or datetime.utcnow()
    rows = [a for a in (open_alerts or ())
            if (a.get('state') or 'open') in ('open', 'acknowledged')]
    rows.sort(key=lambda a: (-SEVERITY_ORDER.get(a.get('severity'), 1),
                             a.get('first_seen') or now, a.get('key') or ''))
    out = []
    for a in rows:
        word = SEVERITY_WORD.get(a.get('severity'), "Worth a look")
        age = _hours_since(a.get('first_seen'), now)
        if age is None:
            when = ''
        elif age < 1:
            when = ' — started less than an hour ago'
        elif age < 48:
            when = ' — going on for %d hours' % int(age)
        else:
            when = ' — going on for %d days' % int(age / 24)
        seen = a.get('count') or 1
        seen_txt = '' if seen <= 1 else ', seen %d times' % seen
        ack = (' (you have said you know about this)'
               if a.get('state') == 'acknowledged' else '')
        out.append('%s: %s%s%s%s'
                   % (word, a.get('subject') or a.get('title') or '',
                      when, seen_txt, ack))
    return out


def digest_headline(open_alerts, live_count):
    """The summary's own first line — and it obeys the severity floor (F68).

    A morning with nothing worse than an `info` in it is announced "For
    information", never "something needs your attention".
    """
    rows = [a for a in (open_alerts or ())
            if (a.get('state') or 'open') in ('open', 'acknowledged')]
    if not rows:
        return ("All clear",
                "Nothing is open. All %d customer%s are healthy."
                % (live_count, '' if live_count == 1 else 's'))
    worst = worst_severity(rows)
    if worst == 'info':
        return ("For information",
                "%d thing%s worth knowing across %d customer%s. Nothing needs "
                "you." % (len(rows), '' if len(rows) == 1 else 's',
                          live_count, '' if live_count == 1 else 's'))
    if worst == 'warning':
        return ("Worth a look",
                "%d thing%s open across %d customer%s. None of it is urgent."
                % (len(rows), '' if len(rows) == 1 else 's',
                   live_count, '' if live_count == 1 else 's'))
    return ("Needs attention now",
            "%d thing%s open across %d customer%s, and at least one of them is "
            "urgent." % (len(rows), '' if len(rows) == 1 else 's',
                         live_count, '' if live_count == 1 else 's'))


# =============================================================================
# 4. CAPACITY
# =============================================================================
def capacity_verdict(mem_total_mb, mem_available_mb, live_tenants,
                     cost_per_tenant_mb, reserve_mb=400):
    """How many more customers this machine can safely hold.

    ⚠ `cost_per_tenant_mb` IS A POLICY, NOT A MEASUREMENT (ledger F34). The
    measurement on this machine is about 11 MB: that is the resident memory the
    application gained when a real customer's system was first opened, across
    the three processes that serve it. It is not what a customer COSTS. Sessions,
    asset caches and the working set of a busy clinic are the rest, and they are
    transient and unmeasurable at rest — so the setting carries the measured
    figure plus a deliberate allowance, and it is a setting precisely so it can
    be re-weighed as customers arrive.

    `reserve_mb` is what must be left alone: the database server, the operating
    system, and enough head for one clinic's busy morning to spike into.
    Spending it is how a machine with "plenty free" dies at nine on a Monday.

    Room = (free − reserve) ÷ cost, never below nought. Levels: `full` at no
    room left, `warn` at one, `ok` above that. The refusal on new customers
    reads this and nothing else.

    ⚠ AND IT IS NOT SIZED FROM THE REGISTRY CACHE (ledger F6). That cache is
    derived from `limit_memory_soft` and is not a real bound; asked, it would
    answer "room for over a hundred customers" on a machine with room for two.
    """
    total = float(mem_total_mb or 0)
    avail = float(mem_available_mb or 0)
    cost = float(cost_per_tenant_mb or 0)
    if cost <= 0:                 # never divide by a setting somebody cleared
        cost = 60.0
    reserve = float(reserve_mb or 0)
    spare = avail - reserve
    headroom = max(0, int(spare // cost))
    level = 'ok'
    if headroom <= 0:
        level = 'full'
    elif headroom <= 1:
        level = 'warn'
    if level == 'full':
        reason = ("This machine cannot safely hold another customer. %d MB of "
                  "memory is free and %d MB of that has to stay free for the "
                  "database and the operating system."
                  % (int(avail), int(reserve)))
    elif level == 'warn':
        reason = ("Room for %d more customer%s. Each one is allowed about "
                  "%d MB and %d MB is free. Plan the resize before the next "
                  "sale." % (headroom, '' if headroom == 1 else 's',
                             int(cost), int(avail)))
    else:
        reason = ("Room for %d more customers. %d MB of memory is free, each "
                  "customer is allowed about %d MB, and %d MB is kept back for "
                  "the database and the operating system."
                  % (headroom, int(avail), int(cost), int(reserve)))
    return {
        'level': level,
        'headroom': headroom,
        'reason': reason,
        'mem_total_mb': int(total),
        'mem_available_mb': int(avail),
        'cost_per_tenant_mb': int(cost),
        'reserve_mb': int(reserve),
        'live_tenants': int(live_tenants or 0),
    }


# =============================================================================
# 5. THE PUBLIC PAGE
# =============================================================================
#: The three things the public page reports on, in the order they are read.
COMPONENTS = (
    'Signing in',
    'Using the system',
    'Customer sites',
)

#: ok < maintenance < degraded < down. PLANNED WORK RANKS BELOW A FAULT on
#: purpose: a page that shouts the same colour for "we told you about this" and
#: "something broke" teaches its readers nothing.
LEVEL_ORDER = {'ok': 0, 'maintenance': 1, 'degraded': 2, 'down': 3}

#: What each kind of problem is called IN PUBLIC. NO CUSTOMER IS EVER NAMED,
#: and the phrasing is deliberately about the SERVICE rather than about the
#: incident: the reader is a nurse wondering whether to keep working.
_PUBLIC_PHRASE = {
    'tenant_unreachable': ('Customer sites', 'down',
                           'A customer site was unreachable'),
    'tenant_errors': ('Using the system', 'degraded',
                      'Errors while using the system'),
    'disk_low': ('Signing in', 'degraded', 'Reduced capacity on the platform'),
    'memory_low': ('Signing in', 'degraded', 'Reduced capacity on the platform'),
    'cert_missing': ('Signing in', 'degraded', 'A certificate problem'),
    'cert_expiring': ('Signing in', 'ok', 'A certificate renewal'),
    # Everything below is real and is nobody else's business: a copy that did
    # not run, a page that would not write, a release that stopped, a mail
    # account nobody has connected. None of them are visible to a customer and
    # none of them colour the public page.
    'backup_missing': (None, 'ok', 'A scheduled copy did not complete'),
    'backup_stale': (None, 'ok', 'A scheduled copy did not complete'),
    'backup_small': (None, 'ok', 'A scheduled copy did not complete'),
    'capacity_full': (None, 'ok', ''),
    'rollout_stopped': (None, 'ok', ''),
    'status_page_unwritable': (None, 'ok', ''),
    'mail_not_configured': (None, 'ok', ''),
}


def _worse(a, b):
    return a if LEVEL_ORDER.get(a, 0) >= LEVEL_ORDER.get(b, 0) else b


def status_state(open_alerts, notices, incidents, now, maintenance=False,
                 updated_at=None, tz=''):
    """Everything the platform knows, reduced to what the world may read.

    ⚠ THIS FUNCTION IS THE BOUNDARY, AND IT IS THE ONLY ONE. On the way in:
    alerts that name customers, a rollout that names the customer it is on,
    notices addressed to one clinic. On the way out: three component names,
    three levels, the notices somebody deliberately made public, and last
    week's incidents as durations. A test feeds it names and asserts that not
    one of them comes out the other side.

    `maintenance` is true while a rollout is walking across the customer rings —
    planned work, which is a different colour from a fault and says so.

    ⚠ THE PAGE HAS NO READER TO ASK WHAT TIME IT IS (ledger F38). Every moment
    that reaches this function must already have been converted to `tz`, and
    `tz` is NAMED on the page, because a file on disk cannot convert anything
    for anybody.
    """
    levels = {name: 'ok' for name in COMPONENTS}
    live = [a for a in (open_alerts or ())
            if (a.get('state') or 'open') in ('open', 'acknowledged')]
    for a in live:
        comp, lvl, _phrase = _PUBLIC_PHRASE.get(a.get('kind'),
                                                (None, None, None))
        if not comp or lvl == 'ok':
            continue
        # A warning about one customer is not a degraded service for everybody;
        # only something urgent is allowed to colour a component.
        if a.get('severity') != 'critical':
            continue
        levels[comp] = _worse(levels[comp], lvl)
    if maintenance:
        levels['Customer sites'] = _worse(levels['Customer sites'],
                                          'maintenance')

    overall = 'ok'
    for lvl in levels.values():
        overall = _worse(overall, lvl)

    pub_notices = []
    for n in (notices or ()):
        pub_notices.append({
            'kind': n.get('kind') or 'info',
            'text': n.get('text') or '',
            'range': n.get('range') or '',
        })

    rows = []
    for inc in (incidents or ()):
        comp, lvl, phrase = _PUBLIC_PHRASE.get(
            inc.get('kind'), (None, None, 'A service issue'))
        # ⚠ IF IT WAS NEVER VISIBLE TO THE WORLD WHILE IT WAS HAPPENING, IT IS
        # NOT AN INCIDENT AFTERWARDS. Found live: a copy that did not run is
        # deliberately given no component above — nobody outside can see it —
        # and it still turned up in "the last seven days" as
        # "A scheduled copy did not complete for 1 minutes", because the
        # incident list was reading only the PHRASE and not the component. A
        # page that reports things its own service section says are fine is a
        # page that reads as noise.
        if not phrase or not comp or lvl == 'ok':
            continue
        mins = int(inc.get('minutes') or 0)
        if mins <= 0:
            length = 'briefly'
        elif mins < 60:
            length = _plural(mins, 'minute')
        elif mins < 60 * 36:
            length = _plural(max(1, int(round(mins / 60.0))), 'hour')
        else:
            length = _plural(max(1, int(round(mins / 1440.0))), 'day')
        rows.append({'when': str(inc.get('ended') or '')[:10],
                     'what': '%s %s' % (phrase, length)})

    return {
        'level': overall,
        'headline': {
            'ok': 'Everything is working',
            'maintenance': 'Planned update in progress',
            'degraded': 'Something is not working properly',
            'down': 'A major problem',
        }[overall],
        'components': [{'name': n, 'level': levels[n]} for n in COMPONENTS],
        'notices': pub_notices,
        'incidents': rows,
        'tz': tz or '',
        'updated_at': updated_at or (now.strftime('%Y-%m-%d %H:%M')
                                     if isinstance(now, datetime) else str(now)),
    }


_LEVEL_WORD = {
    'ok': 'Working',
    'maintenance': 'Planned update',
    'degraded': 'Not working properly',
    'down': 'Not working',
}
_LEVEL_COLOR = {
    'ok': '#1E9E6A',
    'maintenance': '#2563EB',
    'degraded': '#D97706',
    'down': '#DC2668',
}


def render_status_page(state, brand='', tz='', stale_minutes=None):
    """The whole public page as one self-contained file.

    NO EXTERNAL REQUEST OF ANY KIND — no font, no script from elsewhere, no
    image — because the page's entire job is to be readable on the day the
    application is not. The web server hands it off disk and never touches the
    application, which is exactly why it carries no branding this file invented
    and no name of any software.

    IT CHECKS ITS OWN FRESHNESS. The file carries the moment it was written, in
    a NAMED zone; a few lines of script compare that with the reader's own
    clock and say so when it is more than a quarter of an hour old. A page that
    quietly stops updating is worse than none at all, so it is made to admit it.
    """
    state = state or {}
    level = state.get('level') or 'ok'
    e = html.escape
    updated = state.get('updated_at') or ''
    zone = tz or state.get('tz') or ''
    stale = int(stale_minutes if stale_minutes is not None
                else DEFAULT_THRESHOLDS['status_page_minutes'])
    name = (brand or '').strip() or 'Service'

    comps = []
    for c in state.get('components') or ():
        lvl = c.get('level') or 'ok'
        colour = _LEVEL_COLOR.get(lvl, _LEVEL_COLOR['ok'])
        comps.append(
            '<li class="c"><span class="n">%s</span>'
            '<span class="s" style="color:%s"><i style="background:%s"></i>%s'
            '</span></li>'
            % (e(c.get('name') or ''), colour, colour,
               e(_LEVEL_WORD.get(lvl, 'Working'))))

    notices = []
    for n in state.get('notices') or ():
        when = ((' <span class="w">%s</span>' % e(n['range']))
                if n.get('range') else '')
        notices.append('<div class="note %s"><p>%s%s</p></div>'
                       % (e(n.get('kind') or 'info'), e(n.get('text') or ''),
                          when))

    incidents = []
    for i in state.get('incidents') or ():
        incidents.append('<li><span class="d">%s</span>%s</li>'
                         % (e(i.get('when') or ''), e(i.get('what') or '')))
    if not incidents:
        incidents.append('<li class="none">Nothing has gone wrong in the last '
                         'seven days.</li>')

    return """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<link rel="icon" href="data:,"/>
<title>%(brand)s status</title>
<style>
:root{--ink:#12151a;--dim:#5b6470;--line:#e4e7ec;--bg:#f7f8fa;--card:#fff;--accent:#1565C0}
@media (prefers-color-scheme:dark){:root{--ink:#e9edf2;--dim:#98a2b0;--line:#232a33;--bg:#0f1319;--card:#171c23}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
 font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
 -webkit-font-smoothing:antialiased}
.wrap{max-width:680px;margin:0 auto;padding:56px 20px 72px}
.brand{display:flex;align-items:center;gap:10px;font-weight:700;letter-spacing:-.02em;
 color:var(--accent);font-size:17px;margin-bottom:34px}
.brand b{width:10px;height:10px;border-radius:3px;background:var(--accent);display:block}
.hero{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:26px 24px;
 display:flex;align-items:center;gap:16px}
.hero .dot{width:14px;height:14px;border-radius:50%%;background:%(color)s;flex:none;
 box-shadow:0 0 0 5px %(color)s22}
.hero h1{margin:0;font-size:22px;letter-spacing:-.02em;font-weight:650}
.hero .sub{color:var(--dim);font-size:13px;margin-top:3px}
.note{background:var(--card);border:1px solid var(--line);border-left:3px solid var(--accent);
 border-radius:12px;padding:14px 18px;margin-top:14px}
.note.maintenance{border-left-color:#2563EB}
.note p{margin:0;font-size:14px}
.note .w{color:var(--dim);font-size:13px;margin-left:6px}
h2{font-size:12px;text-transform:uppercase;letter-spacing:.09em;color:var(--dim);
 margin:34px 0 10px;font-weight:600}
ul{list-style:none;margin:0;padding:0;background:var(--card);border:1px solid var(--line);
 border-radius:12px;overflow:hidden}
li{padding:13px 18px;border-top:1px solid var(--line);font-size:14px}
li:first-child{border-top:0}
.c{display:flex;align-items:center;justify-content:space-between;gap:12px}
.c .s{font-size:13px;font-weight:560;display:flex;align-items:center;gap:7px}
.c .s i{width:7px;height:7px;border-radius:50%%;display:block}
li .d{color:var(--dim);font-variant-numeric:tabular-nums;margin-right:12px}
li.none{color:var(--dim)}
.foot{margin-top:30px;color:var(--dim);font-size:12.5px;text-align:center}
#stale{display:none;margin-top:14px;background:#D9760615;border:1px solid #D9760655;
 color:#D97706;border-radius:10px;padding:11px 14px;font-size:13.5px}
</style></head>
<body>
<div class="wrap">
  <div class="brand"><b></b>%(brand)s</div>
  <div class="hero">
    <span class="dot"></span>
    <div><h1>%(headline)s</h1>
    <div class="sub">The live status of this service.</div></div>
  </div>
  %(notices)s
  <div id="stale">This page has not refreshed for a while, so it may be out of
  date. If something is not working for you, please contact your
  administrator.</div>
  <h2>Services</h2>
  <ul>%(components)s</ul>
  <h2>The last seven days</h2>
  <ul>%(incidents)s</ul>
  <div class="foot">Updated <span id="when">%(updated)s</span> %(tz)s ·
  This page is served separately from the system it reports on, so it stays up
  when that does not.</div>
</div>
<script>
(function(){
  var el = document.getElementById("when");
  var t = Date.parse("%(iso)s");
  if (isNaN(t)) { return; }
  function check(){
    var mins = (Date.now() - t) / 60000;
    document.getElementById("stale").style.display = mins > %(stale)d ? "block" : "none";
  }
  check(); setInterval(check, 30000);
})();
</script>
</body></html>
""" % {
        'brand': e(name),
        'color': _LEVEL_COLOR.get(level, _LEVEL_COLOR['ok']),
        'headline': e(state.get('headline') or 'Everything is working'),
        'notices': '\n  '.join(notices),
        'components': ''.join(comps),
        'incidents': ''.join(incidents),
        'updated': e(updated),
        'tz': e(zone),
        # The moment as an absolute instant, so the reader's own browser can
        # work out how old the page is whatever zone either of them is in.
        'iso': e(state.get('updated_iso') or ''),
        'stale': stale,
    }
