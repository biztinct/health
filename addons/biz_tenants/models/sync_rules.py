# -*- coding: utf-8 -*-
"""The decisions behind "in step with master", lifted out so a test can reach them.

WHY THIS FILE EXISTS AT ALL (rail R6). Everything the feature actually DOES
happens against another database on the cluster — a registry opened by hand, a
module installed, a version read back. None of that is reachable from a test
suite, and a test that mocked it would only assert that the mock was called. So
every judgement is a pure function here, and the call sites in `service.py` are
left holding two reads and a write.

THE ONE THAT MATTERS MOST IS `norm_version` (ledger F1). Before it, the split
was computed on module NAMES only: a customer sitting two versions behind on a
part of the product they already had was reported as "in step", in green, on a
screen whose whole job is to say otherwise. One customer sat like that for a
fortnight.

NOTHING HERE IMPORTS THE FRAMEWORK. That is the point: the file is reachable
from a plain unit test with no registry, and it cannot grow a database access by
accident.
"""
from datetime import date

from .tenants_common import is_never, never_reason

#: How many dotted parts a version string has once the framework has stamped its
#: series on the front. `19.0.1.7.0` is the series `19.0` plus our own `1.7.0`.
_SERIES_PARTS = 5


def norm_version(v):
    """A version string as an int-tuple that can be compared across databases.

    THE TRAP THIS EXISTS FOR (ledger F1/F8). The version a database records for
    a module carries the framework series on the front — `19.0.1.7.0` — while
    the version written in the module's own file is `1.7.0`. Comparing the two
    as strings says they differ; comparing them as TEXT says `1.10.0` is older
    than `1.9.0`. Both answers are wrong and both are silent.

    The series is stripped only when the string has five or more parts, so a
    plain `1.7.0` is never mistaken for a series-prefixed one. Anything that is
    not a whole number counts as 0, which makes `19.0.1.7.0-rc1` an answer
    rather than a crash.
    """
    if not v:
        return (0,)
    parts = str(v).strip().split('.')
    if len(parts) >= _SERIES_PARTS:
        parts = parts[2:]
    out = []
    for p in parts:
        p = p.strip()
        out.append(int(p) if p.isdigit() else 0)
    return tuple(out) or (0,)


def _versions(mapping):
    """Accept either `{name: version}` or a bare list of names."""
    if mapping is None:
        return {}
    if isinstance(mapping, dict):
        return dict(mapping)
    return {n: '' for n in mapping}


def sync_diff(master_modules, tenant_modules):
    """What one customer's system is missing OR behind on, split four ways.

    Returns:
      * `to_install` — sorted names the master has and this system has not.
      * `to_update`  — `[{'module','have','want'}]`, sorted by name: present on
        both, older here.
      * `held_back`  — sorted names, on EITHER side, that a customer never gets.
        Read off both lists on purpose: a system that somehow already holds one
        must not be quietly upgraded either.
      * `ahead`      — what the customer has NEWER than the master. Reported so
        nobody is surprised by it, and never touched: taking a part of the
        product back is not a sync.
    """
    master = _versions(master_modules)
    tenant = _versions(tenant_modules)
    held, to_install, to_update, ahead = [], [], [], []
    for name in set(master) | set(tenant):
        if is_never(name):
            held.append(name)
            continue
        if name not in master:
            continue                     # theirs alone — never our business
        if name not in tenant:
            to_install.append(name)
            continue
        have, want = norm_version(tenant[name]), norm_version(master[name])
        if want > have:
            to_update.append({'module': name, 'have': tenant[name] or '',
                              'want': master[name] or ''})
        elif have > want:
            ahead.append({'module': name, 'have': tenant[name] or '',
                          'want': master[name] or ''})
    return {
        'to_install': sorted(to_install),
        'to_update': sorted(to_update, key=lambda r: r['module']),
        'held_back': sorted(held),
        'ahead': sorted(ahead, key=lambda r: r['module']),
    }


def sync_split(master_state, tenant_state):
    """What is behind on one customer's system, split in two.

    `(to_install, held_back)`, both sorted lists of names. The narrow shape,
    kept because it is the one the older callers and their tests ask for; new
    code asks `sync_diff`, which also answers the version question.
    """
    master = set(_versions(master_state))
    tenant = set(_versions(tenant_state))
    diff = sync_diff({n: '' for n in master}, {n: '' for n in tenant})
    held = [n for n in diff['held_back'] if n in master and n not in tenant]
    return diff['to_install'], sorted(held)


def held_back_rows(names, labels=None):
    """`[{'module','label','reason'}]` — for the screen, with the reason on it."""
    labels = labels or {}
    return [{'module': n, 'label': labels.get(n, n), 'reason': never_reason(n)}
            for n in sorted(names or ())]


def release_state(snapshot, tenant_modules):
    """Is this system on the release, behind it, or nowhere near it?

      * `on`     — it has every part of the release, at that version or newer.
      * `behind` — it has most of them, but something is missing or older.
      * `none`   — it holds less than half. A system nobody has ever brought in
                   step, or one that is not ours at all; calling that "behind"
                   would put it one button-press away from an install nobody has
                   thought about.

    Parts a customer never gets are ignored on both sides — a release contains
    the whole master, including the platform's own, so that the person reading
    it sees what the master runs rather than an edited version of it.
    """
    snap = {n: v for n, v in _versions(snapshot).items() if not is_never(n)}
    have = _versions(tenant_modules)
    if not snap:
        return 'none'
    present = [n for n in snap if n in have]
    if len(present) * 2 < len(snap):
        return 'none'
    for name, want in snap.items():
        if name not in have or norm_version(have[name]) < norm_version(want):
            return 'behind'
    return 'on'


def master_behind_files(rows):
    """The master's own parts whose files on the server are newer than itself.

    RAIL R3 LIVES OR DIES HERE. Python and template code reach every database
    the moment the server restarts, because they share one directory of files;
    only data, screens and table changes wait to be applied per database
    (ledger F2). So a master whose files have moved on but which has not applied
    them yet is a master running a MIXTURE — and cutting a release from it, or
    measuring a customer against it, would ship that mixture to everybody.

    `rows` is `[(name, version_this_database_has, version_in_the_file)]`.
    Returns the sorted names where the file is newer. Empty is the good answer.
    """
    out = []
    for name, in_db, on_disk in rows or ():
        if not on_disk:
            continue
        if norm_version(on_disk) > norm_version(in_db):
            out.append(name)
    return sorted(out)


def release_name(today=None, existing=None):
    """The name of a release cut today: `2026.09.04`, then `-2`, `-3`, …

    Dated rather than numbered, because the only question anybody ever asks of
    a release name is "how old is this?".
    """
    today = today or date.today()
    base = '%04d.%02d.%02d' % (today.year, today.month, today.day)
    taken = set(existing or ())
    if base not in taken:
        return base
    n = 2
    while '%s-%d' % (base, n) in taken:
        n += 1
    return '%s-%d' % (base, n)


def template_cron_plan(active_ids, recorded):
    """Which of the template's scheduled jobs to switch off, and what to write
    down so a new customer gets them back.

    THE TEMPLATE IS NOT A SYSTEM THAT RUNS. It sits cold on a small box, and a
    scheduled job is exactly the thing that would wake it up and keep a whole
    registry resident for a customer who does not exist. So everything is
    switched off there and the list of what WAS on is written down;
    provisioning turns that list back on inside the clone and clears it.

    ⚠ INSTALLING OR UPGRADING ANYTHING ON THE TEMPLATE SWITCHES ITS JOBS BACK
    ON (ledger F9), because their records reload with `active` true. So this is
    not a build-time chore — it runs after EVERY touch of the template.

    `recorded` is the comma-separated list already written down. Returns
    `(to_disable, new_param)`. Everything active is switched off — an already
    recorded job that is running again still has to go off — while the written
    list only GAINS what it does not already hold, in the order it was found.
    """
    recorded_ids, seen = [], set()
    for chunk in (recorded or '').split(','):
        chunk = chunk.strip()
        if chunk.isdigit() and int(chunk) not in seen:
            recorded_ids.append(int(chunk))
            seen.add(int(chunk))
    to_disable, appended = [], []
    for raw in active_ids or ():
        i = int(raw)
        if i not in to_disable:
            to_disable.append(i)
        if i not in seen:
            seen.add(i)
            appended.append(i)
    new_param = ','.join(str(i) for i in recorded_ids + appended)
    return to_disable, new_param


def log_lines_of_interest(lines, dbname, since, ignore=()):
    """Split a log tail into the errors that matter and the ones that are noise.

    THE EXACT QUERY (ledger F27), AND THE SHAPE IS SIX FIELDS AND NOT FIVE:

        2026-09-04 10:00:00,001 2994560 ERROR hhh odoo.modules: what happened
        └── date ─┘└─ time,ms ─┘└─ pid ─┘└lvl┘└db┘└─ logger ─┘

    The DATE and the TIME are two whitespace-separated fields, which is the
    whole trap: splitting on four spaces puts the process id where the level
    should be, every line fails the level test, and the reader reports a
    perfectly healthy nought for a system that is on fire.

    A line counts when the level is ERROR or CRITICAL, the database column is
    this one, and the timestamp is at or after `since`. **The server's clock is
    UTC and the framework stores UTC, so the two compare as strings with no
    arithmetic** — the day this box moves to a local zone, that comparison is
    what quietly stops working, which is why it is said here.

    THE IGNORE LIST IS NOT A DELETE (ledger F25). This box writes noise on some
    registry loads, and a gate that cries wolf on every run is a gate the owner
    learns to click past. Ignored lines come back in their own list and are
    counted; they are never dropped. The LOGGER NAME is kept in the stored line
    — it is the only part that says which piece of the product complained.

    Returns `{'errors': [...], 'ignored': [...]}`.
    """
    out = {'errors': [], 'ignored': []}
    since = str(since or '')[:19]
    ignore = [i for i in (ignore or ()) if i]
    for raw in lines or ():
        line = raw.rstrip('\n')
        parts = line.split(' ', 5)
        if len(parts) < 6:
            continue
        stamp = ('%s %s' % (parts[0], parts[1]))[:19]
        level, db = parts[3], parts[4]
        if level not in ('ERROR', 'CRITICAL'):
            continue
        if db != dbname:
            continue
        if since and stamp < since:
            continue
        low = line.lower()
        if any(needle in low for needle in ignore):
            out['ignored'].append(line)
        else:
            out['errors'].append(line)
    return out


def log_lines_by_database(lines, dbnames, since, ignore=()):
    """The same question, asked of MANY systems in ONE pass over the tail.

    ⚠ THE SWEEP MUST READ THE LOG ONCE, NOT ONCE PER CUSTOMER (ledger F39).
    `log_lines_of_interest` reads a twenty-megabyte tail to answer about ONE
    system, which is right for a rollout's health gate — one system, once, at
    the moment it matters. The alert sweep asks about every live customer plus
    the platform's own system every quarter of an hour, and doing that one
    database at a time is twenty megabytes of reading per customer per sweep on
    a machine with two gigabytes of memory.

    Same shape, same rule, same ignore list. Returns
    `{dbname: {'errors': [...], 'ignored': [...]}}` with an entry for every
    name asked about, so a system with nothing wrong answers an empty pair
    rather than being missing.
    """
    wanted = set(dbnames or ())
    out = {db: {'errors': [], 'ignored': []} for db in wanted}
    if not wanted:
        return out
    since = str(since or '')[:19]
    ignore = [i for i in (ignore or ()) if i]
    for raw in lines or ():
        line = raw.rstrip('\n')
        parts = line.split(' ', 5)
        if len(parts) < 6:
            continue
        stamp = ('%s %s' % (parts[0], parts[1]))[:19]
        level, db = parts[3], parts[4]
        if level not in ('ERROR', 'CRITICAL'):
            continue
        if db not in wanted:
            continue
        if since and stamp < since:
            continue
        low = line.lower()
        key = 'ignored' if any(n in low for n in ignore) else 'errors'
        out[db][key].append(line)
    return out
