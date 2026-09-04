# -*- coding: utf-8 -*-
"""The decisions behind a rollout, lifted out so a test can reach them.

Rail R6, and the third file in this family after `provision_rules.py` and
`sync_rules.py`. Everything a rollout DOES happens on somebody else's system —
restore a copy, install parts of the product, read a log, drop the copy again —
and not one of those is reachable from a test suite. So the judgements live
here, pure, and the worker next door is left holding the acts.

The one that earns its keep is `advance()`. It is the whole state machine of a
rollout — which system goes next, whether the watch period is over, whether the
whole thing should stop — as a function of a plain dictionary and the time. The
worker calls it; the tests hammer it; nobody has to start a rollout on a real
customer to find out what it will do at three in the morning.

NOTHING HERE IMPORTS THE FRAMEWORK.
"""
from datetime import datetime, timedelta, timezone

try:                                                       # pragma: no cover
    from zoneinfo import ZoneInfo
except ImportError:                                        # pragma: no cover
    ZoneInfo = None

#: The rings, in the order they happen, and the ORDER IS THE WHOLE SAFETY
#: ARGUMENT: a practice run on a throwaway copy, then the blank system new
#: customers are made from, then ONE customer on their own, then the few who
#: agreed to be early, then everybody. Nothing jumps this queue.
RING_ORDER = ('rehearsal', 'template', 'canary', 'early', 'everyone')

#: The three a customer can actually be put in. `rehearsal` and `template` are
#: not places a customer sits; they are things the platform does to itself.
CUSTOMER_RINGS = ('canary', 'early', 'everyone')

#: What each ring is called on screen, said the way a person would say it.
RING_LABEL = {
    'rehearsal': "Practice run",
    'template': "The blank system",
    'canary': "First customer",
    'early': "Early group",
    'everyone': "Everyone else",
}

#: One line each, for the tooltip on the ring. Written for somebody who runs a
#: clinic business, not for somebody who ships software.
RING_MEANING = {
    'rehearsal': ("A practice run on a throwaway copy of a customer's system. "
                  "Nobody sees it, nobody is affected by it, and the copy is "
                  "deleted afterwards whatever happens. If the update is going "
                  "to break, it breaks here."),
    'template': ("The blank system every new customer is created from. It goes "
                 "next, so a customer who signs up tomorrow starts on the new "
                 "version rather than on the old one."),
    'canary': ("The first real customer to get it — one, on their own, with a "
               "watch period afterwards. If something is wrong, one customer "
               "meets it instead of all of them."),
    'early': ("Customers happy to receive changes a day or two before the "
              "rest."),
    'everyone': ("The rest of the customers, once the earlier rings have been "
                 "quiet for the watch period."),
}

#: Rings that wait afterwards, and how long by default. The practice run and the
#: blank system have no watch period: nobody is using either of them.
WATCH_RINGS = ('canary', 'early')
DEFAULT_WATCH = {'canary': 24, 'early': 48}

#: A window nobody typed. 22:00 for three hours is when a clinic is closed in
#: every country this product is sold in.
DEFAULT_START_HOUR = 22
DEFAULT_HOURS = 3
DEFAULT_TZ = 'Asia/Ho_Chi_Minh'

#: A task that says it is running and has been saying so for longer than this
#: was interrupted — the machine was restarted mid-update, most likely. It is
#: not left spinning for ever; the rollout stops and says so.
STUCK_MINUTES = 90

#: How far ahead the warning to a customer's own people looks.
PRE_NOTICE_HOURS = 24


# =============================================================================
# 1. TIME — and every function here exists because the alternative is a lie
# =============================================================================
def _zone(tz):
    """The time zone, or UTC when the name is missing or unknown.

    A customer whose zone cannot be read is updated at 22:00 UTC rather than
    not at all. That is the wrong hour for them; it is not a rollout that
    silently stops.
    """
    if not tz or ZoneInfo is None:
        return timezone.utc
    try:
        return ZoneInfo(str(tz))
    except Exception:                                      # noqa: BLE001
        return timezone.utc


def parse_stamp(text):
    """`'2026-09-04 22:00:00'` as a naive datetime, or None. Never raises."""
    if not text:
        return None
    if isinstance(text, datetime):
        return text
    raw = str(text).strip().replace('T', ' ')
    for shape in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d'):
        try:
            return datetime.strptime(raw[:len(datetime.now().strftime(shape))],
                                     shape)
        except ValueError:
            continue
    return None


def _aware(dt):
    """A moment as UTC-aware. The framework hands out naive UTC.

    ⚠ AN UNSET DATE FIELD READS AS `False`, NOT `None` (ledger F23). Every
    empty Datetime the data layer hands over is the boolean, so a plain
    `if dt is None` lets it straight through and the next line asks a boolean
    for its `tzinfo`. It broke the state machine of the product this was
    ported from the first time a ring finished. FALSY OF ANY SHAPE means
    "there is no such moment".
    """
    if not dt:
        return None
    if isinstance(dt, str):
        dt = parse_stamp(dt)
    if not dt:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _naive(dt):
    """Back to the naive UTC the framework stores."""
    aware = _aware(dt)
    if aware is None:
        return None
    return aware.astimezone(timezone.utc).replace(tzinfo=None)


def _clean_window(start_hour, hours):
    start = int(start_hour if start_hour not in (None, False, '')
                else DEFAULT_START_HOUR)
    span = int(hours if hours not in (None, False, '') else DEFAULT_HOURS)
    return start % 24, max(1, min(24, span))


def window_open(now_utc, tz, start_hour, hours):
    """Is this customer's quiet window open right now, WHERE THEY ARE?

    The window is a wall-clock band in the customer's own zone, so it survives
    daylight saving with no arithmetic at all: we ask what time it is THERE and
    compare the hour. A band that runs past midnight (22:00 for three hours)
    wraps, which is the case everybody gets wrong.
    """
    start, span = _clean_window(start_hour, hours)
    local = _aware(now_utc).astimezone(_zone(tz))
    mins = local.hour * 60 + local.minute
    a, b = start * 60, start * 60 + span * 60
    if b <= 24 * 60:
        return a <= mins < b
    return mins >= a or mins < (b - 24 * 60)


def next_window(now_utc, tz, start_hour, hours):
    """When their window opens next, as naive UTC.

    Now, if it is already open. Otherwise today's opening if that is still
    ahead of them, else tomorrow's. Built from the LOCAL wall clock and then
    converted, so on the two days a year a zone shifts, "22:00" still means
    22:00 to the person it is being done for.
    """
    start, span = _clean_window(start_hour, hours)
    if window_open(now_utc, tz, start, span):
        return _naive(now_utc)
    zone = _zone(tz)
    local = _aware(now_utc).astimezone(zone)
    todays = local.replace(hour=start, minute=0, second=0, microsecond=0)
    if todays <= local:
        todays = todays + timedelta(days=1)
        # Re-attach the zone to the NEW wall clock. Adding a day to an aware
        # datetime keeps the OLD offset, which is an hour out on the day a zone
        # shifts; re-stating the wall clock is what makes this safe.
        todays = datetime(todays.year, todays.month, todays.day, start, 0,
                          tzinfo=zone)
    return _naive(todays)


def to_local(dt, tz):
    """A UTC moment as the naive wall clock in `tz`. FOR SAYING IT OUT LOUD.

    ⚠ Ledger F32. `render_range` formats whatever it is handed and will
    happily print a lie: handing it UTC printed "tonight 15:00–18:00" on a
    screen whose very next line said "their time". This is the conversion that
    has to happen first, and the zone has to be NAMED beside the result.
    """
    aware = _aware(dt)
    if aware is None:
        return None
    return aware.astimezone(_zone(tz)).replace(tzinfo=None)


def window_bounds(now_utc, tz, start_hour, hours):
    """`(opens, closes)` for the next window, as naive UTC."""
    start, span = _clean_window(start_hour, hours)
    opens = next_window(now_utc, tz, start, span)
    zone = _zone(tz)
    local_open = _aware(opens).astimezone(zone)
    local_close = local_open + timedelta(hours=span)
    return opens, _naive(local_close)


def render_range(start, end, now=None):
    """A window as a sentence: "tonight 22:00–01:00", "Fri 5 Sep 22:00–01:00".

    ⚠ IT FORMATS WHAT IT IS HANDED AND KNOWS NOTHING ABOUT ZONES. Hand it the
    reader's own wall clock (`to_local(...)`) and name the zone beside it, or
    it will print somebody else's evening as this one. All three arguments have
    to be in the SAME clock; that is the whole contract.
    """
    start = parse_stamp(start) if not isinstance(start, datetime) else start
    end = parse_stamp(end) if not isinstance(end, datetime) else end
    if not start:
        return ''
    now = (parse_stamp(now) if now and not isinstance(now, datetime)
           else now) or datetime.utcnow()
    day = start.date()
    delta = (day - now.date()).days
    if delta == 0:
        when = "tonight" if start.hour >= 17 else "today"
    elif delta == 1:
        when = "tomorrow night" if start.hour >= 17 else "tomorrow"
    elif delta == -1:
        when = "last night" if start.hour >= 17 else "yesterday"
    else:
        when = start.strftime('%a %-d %b') if hasattr(start, 'strftime') else ''
    if not end:
        return '%s %s' % (when, start.strftime('%H:%M'))
    return '%s %s–%s' % (when, start.strftime('%H:%M'),
                             end.strftime('%H:%M'))


def say_window(start, end, now, tz):
    """The whole honest phrase, zone and all: "tonight 22:00–01:00 · their
    time · Asia/Ho_Chi_Minh".

    ONE FUNCTION SO THERE IS ONE PLACE TO GET IT WRONG. Ledger F32 was a
    correctly-converted window printed without its zone beside it, which reads
    exactly like an unconverted one.
    """
    text = render_range(start, end, now)
    if not text:
        return ''
    return '%s · their time · %s' % (text, tz or DEFAULT_TZ)


# =============================================================================
# 2. THE PLAN
# =============================================================================
def plan_tasks(release, tenants, rehearsal_source, template_db=''):
    """Every step of one rollout, in the order they will happen.

    `release` is `{'id', 'name'}`. `tenants` is a list of dicts carrying
    `id, name, slug, state, ring`. `rehearsal_source` is the customer whose
    latest copy the practice run is restored from, or None.

    Returns `{'tasks', 'excluded', 'warnings', 'release'}`.

    THE PRACTICE RUN IS FIRST AND IT IS NOT OPTIONAL (rail R4). A release that
    has not been practised on a copy is a release nobody has ever seen applied,
    and the first system to find out would be a real clinic's.

    A customer still being set up, or one closed down, is left out WITH A
    REASON. Silence about a customer who did not get the update is the failure
    this list exists to prevent.
    """
    tasks, excluded, warnings = [], [], []
    seq = 0

    def add(ring, target_db, label, tenant_id=None, source_tenant_id=None):
        nonlocal seq
        seq += 10
        tasks.append({
            'sequence': seq, 'ring': ring, 'target_db': target_db,
            'label': label, 'tenant_id': tenant_id,
            'source_tenant_id': source_tenant_id,
        })

    if rehearsal_source:
        add('rehearsal', '%s-staging' % rehearsal_source['slug'],
            "%s (practice copy)" % rehearsal_source['name'],
            source_tenant_id=rehearsal_source['id'])
    else:
        warnings.append(
            "There is no customer with a copy to practise on, so this rollout "
            "would start at the blank system.")

    if template_db:
        add('template', template_db, "The blank system")

    ranked = {r: [] for r in CUSTOMER_RINGS}
    for t in tenants or ():
        state = t.get('state')
        if state == 'decommissioned':
            excluded.append({'id': t.get('id'), 'name': t.get('name'),
                             'reason': "Closed down — a system on its way out "
                                       "is never updated."})
            continue
        if state in ('draft', 'provisioning'):
            excluded.append({'id': t.get('id'), 'name': t.get('name'),
                             'reason': "Still being set up — it will be created "
                                       "on the new version anyway."})
            continue
        if state == 'error':
            excluded.append({'id': t.get('id'), 'name': t.get('name'),
                             'reason': "This customer already needs attention. "
                                       "Put that right first, then update them "
                                       "on their own."})
            continue
        ring = t.get('ring') or 'everyone'
        if ring not in ranked:
            ring = 'everyone'
        ranked[ring].append(t)

    for ring in CUSTOMER_RINGS:
        for t in sorted(ranked[ring],
                        key=lambda r: (r.get('name') or '').lower()):
            add(ring, t.get('slug'), t.get('name'), tenant_id=t.get('id'))

    if not any(ranked[r] for r in CUSTOMER_RINGS):
        warnings.append("No customers are being updated — there are none live "
                        "yet. The practice run and the blank system still run.")
    elif not ranked['canary']:
        warnings.append("No customer is marked as the first one, so the first "
                        "real customer to get this is in the early group. "
                        "Marking one means a problem is met by one customer "
                        "instead of several.")
    return {'tasks': tasks, 'excluded': excluded, 'warnings': warnings,
            'release': release}


def eligible(task, now_utc):
    """May this waiting step run at this moment?

    Three ways to be yes: somebody pressed "Run now", it is one of the two
    rings nobody is looking at, or the customer's own quiet window is open
    where they are.
    """
    if task.get('run_now'):
        return True
    if task.get('ring') in ('rehearsal', 'template'):
        return True
    return window_open(now_utc, task.get('tz'),
                       task.get('maintenance_start'),
                       task.get('maintenance_hours'))


# =============================================================================
# 3. THE HEALTH GATE
# =============================================================================
#: Log lines that are always there and never mean an update went wrong. Each is
#: a substring, matched without regard to case, and each is here because
#: somebody looked at it and decided it was noise. They are still RECORDED on
#: the step; they simply do not stop a rollout (ledger F25).
#:
#: Empty on this platform on purpose: nothing on this box writes a line of that
#: kind today, and a list seeded with somebody else's noise would quietly
#: swallow a real error the day one of those strings appeared here for a real
#: reason. The setting `biz_tenants.health_ignore` is where lines are added,
#: and it is read on every run so it needs no deploy.
DEFAULT_LOG_IGNORE = ()


def filter_errors(lines, ignore=None):
    """Split log lines into the ones that matter and the ones that always fire.

    Returns `(kept, ignored)`. An empty or missing `ignore` means nothing is
    ignored, so the strict behaviour is always one empty setting away.
    """
    patterns = [str(p).strip().lower() for p in (ignore or ()) if str(p).strip()]
    kept, skipped = [], []
    for line in (lines or ()):
        text = str(line).lower()
        (skipped if any(p in text for p in patterns) else kept).append(line)
    return kept, skipped


def health_verdict(probe_code, skipped, error_lines):
    """Did the system survive its update? `(ok, plain-English reason)`.

    Three questions, asked worst first, because the first "no" is the one worth
    reading. `probe_code` is an HTTP status, 0 for no answer at all, and None
    when there was nothing to ask (the blank system has no address). `skipped`
    is -1 when the framework could not tell us — which is reported as such and
    never as a green nought.
    """
    lines = [str(x) for x in (error_lines or ())]
    if probe_code == 0:
        return False, "Their address did not answer after the update."
    if probe_code not in (None, 0) and int(probe_code) >= 500:
        return False, ("Their address answered with an error (%s) after the "
                       "update." % probe_code)
    skipped = -1 if skipped is None else int(skipped)
    if skipped > 0:
        return False, ("%s part%s of the product said it was installed but did "
                       "not load afterwards."
                       % (skipped, '' if skipped == 1 else 's'))
    if lines:
        return False, ("%s error%s in the log while it was being updated."
                       % (len(lines), '' if len(lines) == 1 else 's'))
    if skipped < 0:
        return True, "Whether anything was skipped could not be determined."
    return True, ''


def watch_hours_for(ring, watch_hours=None):
    """How long to sit and watch after a ring. 0 for the rings nobody uses."""
    if ring not in WATCH_RINGS:
        return 0
    hours = (watch_hours or {}).get(ring, DEFAULT_WATCH.get(ring, 24))
    try:
        return max(0, int(hours))
    except (TypeError, ValueError):
        return DEFAULT_WATCH.get(ring, 24)


# =============================================================================
# 4. THE STATE MACHINE
# =============================================================================
def _ring_tasks(snapshot, ring):
    return [t for t in snapshot.get('tasks', ()) if t.get('ring') == ring]


def _next_ring_with_tasks(snapshot, ring):
    try:
        idx = RING_ORDER.index(ring)
    except ValueError:
        return None
    for nxt in RING_ORDER[idx + 1:]:
        if _ring_tasks(snapshot, nxt):
            return nxt
    return None


def advance(snapshot, now_utc):
    """What should the worker do at this instant? THE WHOLE STATE MACHINE.

    `snapshot` is a plain dict:
        state, current_ring, ring_done_at, watch_skipped, watch_hours,
        watch_health (a list of `{'name', 'ok', 'reason'}` re-checks taken
        during the watch period), and `tasks`: a list of
        `{id, ring, state, run_now, tz, maintenance_start, maintenance_hours,
          started_at, error, label}`.

    Returns one of:
        ('run', task)            run this step now
        ('wait', until_utc)      nothing to do until then
        ('ring_done', ring)      every step in this ring has finished
        ('advance_ring', ring)   move to this ring
        ('done',)                the whole rollout is over
        ('pause', reason)        stop, and this is what a person must read

    ONE STEP AT A TIME, ALWAYS. Not because the machine could not manage two,
    but because a rollout that has gone wrong should have gone wrong on one
    customer.

    ⚠ IT ONLY EVER LOOKS AT THE CURRENT RING (ledger F30). "Run now" on a
    customer in a later ring is therefore a silent no-op here, which is why the
    caller refuses it BY NAME and points at the button that does what the
    person meant.
    """
    now = _aware(now_utc)
    tasks = list(snapshot.get('tasks') or ())
    if not tasks:
        return ('done',)

    ring = snapshot.get('current_ring') or RING_ORDER[0]
    mine = _ring_tasks(snapshot, ring)

    # A ring with nothing in it is not a ring to sit in.
    if not mine:
        nxt = _next_ring_with_tasks(snapshot, ring)
        return ('advance_ring', nxt) if nxt else ('done',)

    # 1. Anything that has already failed stops everything. That is the whole
    #    point of the ordering: one customer met the problem, and the next one
    #    does not.
    failed = [t for t in mine if t.get('state') == 'failed']
    if failed:
        return ('pause', failed[0].get('error')
                or ("%s could not be updated."
                    % (failed[0].get('label') or 'A customer')))

    # 2. Something already running. Either it is genuinely in flight — a step
    #    is minutes, not seconds — or the process died holding it, and a
    #    rollout that waits for ever is worse than one that says so.
    running = [t for t in mine if t.get('state') == 'running']
    if running:
        started = _aware(running[0].get('started_at')) or now
        if now - started > timedelta(minutes=STUCK_MINUTES):
            return ('pause',
                    "The update of %s started %s minutes ago and never "
                    "finished. Check the machine, then try it again or leave "
                    "it behind."
                    % (running[0].get('label') or 'a customer',
                       int((now - started).total_seconds() // 60)))
        return ('wait', _naive(min(started + timedelta(minutes=STUCK_MINUTES),
                                   now + timedelta(minutes=5))))

    # 3. Anything left to run in this ring?
    queued = [t for t in mine if t.get('state') in ('waiting', 'due', 'queued')]
    if queued:
        for t in queued:
            if eligible(t, now):
                return ('run', t)
        whens = [next_window(now, t.get('tz'), t.get('maintenance_start'),
                             t.get('maintenance_hours')) for t in queued]
        return ('wait', min(whens))

    # 4. The ring is finished. Stamp it, then serve the watch period.
    done_at = _aware(snapshot.get('ring_done_at'))
    if not done_at:
        return ('ring_done', ring)

    hours = watch_hours_for(ring, snapshot.get('watch_hours'))
    if hours and not snapshot.get('watch_skipped'):
        # A customer who went quiet during the watch period is the reason the
        # watch period exists. One bad re-check stops the rollout where it is.
        for probe in (snapshot.get('watch_health') or ()):
            if not probe.get('ok'):
                return ('pause',
                        "%s stopped looking healthy during the watch period: %s"
                        % (probe.get('name') or 'A customer',
                           probe.get('reason') or 'unknown'))
        until = done_at + timedelta(hours=hours)
        if now < until:
            return ('wait', _naive(until))

    nxt = _next_ring_with_tasks(snapshot, ring)
    return ('advance_ring', nxt) if nxt else ('done',)


# =============================================================================
# 5. WHAT A CUSTOMER'S OWN PEOPLE ARE TOLD
# =============================================================================
def notice_for(phase, brand=''):
    """The message on a customer's own bar, before and during their update.

    Two phases and no others. `pre` goes up the evening before; `now` goes up
    while the work is happening and comes down when it is over.

    ⚠ THE PRODUCT'S NAME COMES FROM THE SETTING AND IS NEVER WRITTEN HERE. This
    module runs whichever product it is installed beside, and a sentence with
    somebody else's brand in it is worse than one with none.
    """
    name = (brand or '').strip() or "The system"
    if phase == 'pre':
        return {
            'kind': 'maintenance',
            'text': ("%s is being updated inside this window. It pauses for a "
                     "minute or two. You do not need to do anything." % name),
        }
    if phase == 'now':
        return {
            'kind': 'maintenance',
            'text': ("%s is being updated right now. A minute or two — this "
                     "page keeps working when it is done." % name),
        }
    raise ValueError("a rollout only sends two kinds of message")
