# -*- coding: utf-8 -*-
"""Every judgement provisioning makes, as a pure function (rail R6).

The act itself — clone a database, copy a file store, ask for a certificate —
happens on a live box and is reachable from no test. So the DECISIONS are here,
they are tested, and the call sites in `service.py` are left holding the acts.

NOTHING HERE IMPORTS THE FRAMEWORK.
"""
import re

#: THE SIX STEPS, in the order they run. A system carries the step it reached,
#: so the screen can offer "continue from here" rather than "start again" — the
#: difference between a half-made customer that can be finished and one that has
#: to be swept up by hand.
#:
#: `done` is a step rather than a state so that the log has a line for it: the
#: one summary sentence somebody reads six months later.
PROVISION_STEPS = (
    ('clone', 'Copy the blank system'),
    ('configure', 'Set its address and its settings'),
    ('admin', 'Create the administrator'),
    ('https', 'Secure the address'),
    ('verify', 'Check everything answers'),
    ('done', 'Hand it over'),
)

STEP_KEYS = tuple(k for k, _l in PROVISION_STEPS)

#: THE SLUG IS TWO THINGS AT ONCE and that is why the rule is this tight: it is
#: the DATABASE NAME and it is the first word of the WEB ADDRESS. So it has to
#: be a legal hostname label (no underscore — the web server drops any hostname
#: carrying one, and that rule is what keeps the template off the internet) and
#: a legal database name at the same time.
SLUG_RE = re.compile(r'^[a-z][a-z0-9]{1,30}$')

#: Names the platform keeps for itself, plus the ones PostgreSQL owns. A slug
#: is refused BY NAME against this list rather than by a pattern, because the
#: reason has to be sayable on screen.
RESERVED_SLUGS = frozenset({
    'postgres', 'template0', 'template1',
    'www', 'mail', 'smtp', 'imap', 'pop', 'ftp', 'admin', 'api', 'app', 'apps',
    'staging', 'demo', 'test', 'dev', 'ns1', 'ns2', 'cdn', 'static', 'assets',
    'portal', 'help', 'docs', 'status', 'vpn', 'git', 'db', 'login', 'auth',
    'secure', 'support', 'billing', 'blog', 'shop', 'webmail', 'autoconfig',
    'autodiscover', 'platform', 'template', 'master',
})

#: A backup with a file store this small is not a backup (ledger F59). There is
#: no `data_dir` in the config, so the file store is `$HOME/.local/share/Odoo`
#: and the service's HOME is `/odoo`. Anything run with a different HOME writes
#: and reads a DIFFERENT, empty file store — and still says "done".
#:
#: THE NUMBER COMES FROM THE INCIDENT: the bad archive was 9 MB with **five**
#: files in it, beside a real one of 219 MB with 1,280. So five has to FAIL, and
#: a threshold of five would have passed it. Twenty is comfortably above the
#: wreckage and far below anything a real system produces — a blank system's
#: attachments folder alone runs to hundreds of files before anybody signs in.
MIN_FILESTORE_FILES = 20
MIN_FILESTORE_BYTES = 64 * 1024


def check_slug(slug, *, taken=(), apex_db='', template_db=''):
    """May this be a customer's short name? `(ok, reason)`, and the reason is
    a sentence somebody can act on.

    `taken` is every database name already on the box plus every slug already
    claimed. `apex_db` and `template_db` are refused BY NAME rather than by
    being in `taken`, because "that is the platform itself" is a different
    sentence from "that name is in use" and the person typing needs the right
    one.
    """
    raw = (slug or '').strip()
    if not raw:
        return False, "Give the customer a short name — it becomes their web address."
    low = raw.lower()
    if raw != low:
        return False, ("Use small letters only. The short name is the first "
                       "word of their web address, and web addresses have no "
                       "capitals.")
    if '_' in raw:
        return False, ("No underscores. A web address cannot contain one, and "
                       "this machine refuses any address that does.")
    if not SLUG_RE.match(raw):
        return False, ("Between 2 and 31 small letters and digits, starting "
                       "with a letter. No spaces, hyphens or punctuation.")
    if apex_db and raw == apex_db:
        return False, ("That is the platform's own system. It cannot also be a "
                       "customer.")
    if template_db and raw == template_db:
        return False, ("That is the blank system every new customer is copied "
                       "from. It cannot also be a customer.")
    if raw in RESERVED_SLUGS:
        return False, "That name is kept for the platform. Pick another."
    if raw.endswith('staging'):
        return False, ("Names ending in \"staging\" are kept for practice "
                       "copies of a customer's system.")
    if raw in {str(t).strip().lower() for t in (taken or ()) if t}:
        return False, "Something on this machine already has that name."
    return True, ''


def free_memory_mb(meminfo_text):
    """Free memory in MB, out of the text of `/proc/meminfo`. PURE.

    `MemAvailable` and NOT `MemFree`: free memory on a busy box is close to
    zero and always has been, because the kernel keeps the rest as cache it
    will hand back the moment anybody asks. A guard reading `MemFree` refuses
    every time; a guard reading `MemAvailable` refuses when it should.

    Returns -1 when the text cannot be read at all — an honest "could not tell"
    rather than a number the caller would treat as a measurement.
    """
    for line in str(meminfo_text or '').split('\n'):
        if line.startswith('MemAvailable:'):
            parts = line.split()
            if len(parts) >= 2 and parts[1].isdigit():
                return int(parts[1]) // 1024
    return -1


def memory_verdict(free_mb, floor_mb):
    """`(ok, reason)` — may another system be created on this machine right now?

    A "could not tell" (-1) is allowed THROUGH with a warning rather than
    refused. This is the soft floor; the real capacity guard is the next
    phase's, and a guard that cannot read the box must not be the thing that
    stops a customer being created.
    """
    if free_mb is None or free_mb < 0:
        return True, ("This machine's free memory could not be read, so the "
                      "check was skipped. Watch it while this runs.")
    if free_mb < floor_mb:
        return False, (
            "This machine has %d MB of memory to spare and the floor is %d MB. "
            "Creating another system now would put every customer on it at "
            "risk. Free some memory — drop any practice copies — or make the "
            "machine bigger, and try again." % (free_mb, floor_mb))
    return True, ''


def backup_verdict(dump_bytes, filestore_bytes, filestore_files):
    """Is what we just wrote actually a backup? `(ok, reason)`. Ledger F59.

    A DUMP ON ITS OWN IS NOT A RESTORE. A restore is the dump PLUS the
    attachments, and both have to come from the same moment. A run started with
    the wrong HOME reads an empty attachments folder, writes a tiny archive and
    reports success — which is the worst possible outcome, because the failure
    is discovered on the day somebody needs the backup.

    So the size is CHECKED rather than recorded, and a suspiciously small file
    store fails the backup instead of being written down as a good one.
    """
    if not dump_bytes or dump_bytes <= 0:
        return False, "The database file came out empty. Nothing was kept."
    if filestore_files < MIN_FILESTORE_FILES:
        return False, (
            "The attachments folder came out with %d files in it, which is not "
            "a real copy — almost certainly taken with the wrong home folder. "
            "A backup without attachments cannot be restored, so this one has "
            "been thrown away rather than recorded as good."
            % filestore_files)
    if filestore_bytes < MIN_FILESTORE_BYTES:
        return False, (
            "The attachments archive is only %d bytes, which is not a real "
            "copy. It has been thrown away rather than recorded as good."
            % filestore_bytes)
    return True, ''


def next_step(reached):
    """The step to run next, or '' when there is nothing left.

    `reached` is the last step that FINISHED. The screen offers this one as
    "continue", which is what turns a failed provisioning into something that
    can be picked up rather than swept up.
    """
    if not reached:
        return STEP_KEYS[0]
    if reached not in STEP_KEYS:
        return STEP_KEYS[0]
    idx = STEP_KEYS.index(reached)
    return STEP_KEYS[idx + 1] if idx + 1 < len(STEP_KEYS) else ''


def step_label(key):
    for k, label in PROVISION_STEPS:
        if k == key:
            return label
    return key or ''


def human_bytes(nbytes):
    """A size a person reads, not a number a machine wrote."""
    n = float(nbytes or 0)
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if n < 1024 or unit == 'TB':
            return ('%d %s' if unit == 'B' else '%.1f %s') % (n, unit)
        n /= 1024.0
    return '%.1f TB' % n


def generated_password(token):
    """A one-time password out of a random token, in a shape somebody can read
    aloud down a telephone.

    THE POINT IS THAT IT IS TYPED ONCE AND CHANGED. It is shown on screen at
    the end of provisioning, never stored anywhere, and never emailed by this
    module. The two dashes are there because a person reading a password out
    needs somewhere to breathe.
    """
    clean = re.sub(r'[^A-Za-z0-9]', '', str(token or ''))[:12]
    while len(clean) < 12:
        clean += '7'
    return '%s-%s-%s' % (clean[:4], clean[4:8], clean[8:12])
