# -*- coding: utf-8 -*-
"""What this system knows about the platform it is part of.

TEN SETTINGS, READ AND NEVER WRITTEN. Everything here is a read of
`ir.config_parameter` and a little arithmetic on it. Nothing in this module
writes a setting, calls out, opens a port or holds a connection. The platform
writes; this reads.

THE ONE RULE THAT DECIDES HOW EVERY SETTING IS READ (ledger F24). `get_param`
answers `False` both for a key that is not there AND for a key somebody set to
an empty string, because its body ends in `or default`. Those are different
facts here: "no message" and "the message was cleared" look the same to the
reader but not to the person debugging why a bar will not go away. So anywhere
"set but empty" is meaningful, the row itself is searched and `.value` is read.

AND IT FAILS SAFE, ALWAYS IN THE SAME DIRECTION. A damaged setting shows
nothing rather than taking a page down: a malformed message is not a reason for
somebody to be unable to work.
"""
import json
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

# --------------------------------------------------------------- the contract
#: The ten settings, named in ONE place so the platform and this side cannot
#: drift apart. The platform keeps its own copy of these strings, deliberately:
#: this module is not installed on the platform's own database at the moment it
#: needs to name them.
P_RELEASE = 'biz_tenancy.release'
P_RELEASE_NOTES = 'biz_tenancy.release_notes'
P_RELEASE_AT = 'biz_tenancy.release_at'
P_RELEASES = 'biz_tenancy.releases'
P_NOTICE = 'biz_tenancy.notice'
P_NOTICE_KIND = 'biz_tenancy.notice_kind'
P_NOTICE_FROM = 'biz_tenancy.notice_from'
P_NOTICE_TO = 'biz_tenancy.notice_to'
P_PUSHED_AT = 'biz_tenancy.pushed_at'
P_PLATFORM_URL = 'biz_tenancy.platform_url'
P_SUPPORT_EMAIL = 'biz_tenancy.support_email'

#: NOT part of the contract above and not used by anything yet — the seam the
#: next phase's switches read (handover §3.7). It is declared here so that
#: there is exactly one spelling of it in the product.
P_FEATURES = 'biz_tenancy.features'

#: How a system knows it is a customer rather than the platform: the platform
#: is the one system nobody provisioned, so it is the one without this.
P_SLUG = 'biz_tenancy.slug'

#: The brand the product is sold under. Read, never written, and never
#: defaulted to a literal in a user-visible string — a screen with no brand set
#: says "the system" instead (rail R12).
P_BRAND = 'biz_debranding.brand_name'

#: The two kinds of message, and they are two because they mean different
#: things to whoever reads them: `maintenance` is "something is about to happen
#: to your service", `info` is "here is something worth knowing". Anything else
#: is read as `info` rather than guessed at.
NOTICE_KINDS = ('maintenance', 'info')

#: How many releases the About screen carries. Ten is about two months of
#: shipping — far enough back to answer "when did that change?" and short
#: enough that the page is still one screen of scrolling.
RELEASE_HISTORY = 10

_STAMP = '%Y-%m-%d %H:%M:%S'


# ============================================================== pure functions
#
# Everything below this line is a decision, and every decision is pure so that
# a test can reach it without a registry (rail R6). The model underneath holds
# reads and nothing else.

def notice_phase(starts, ends, now):
    """Where a window stands relative to now: 'before' | 'during' | 'over'.

    All three arguments are `YYYY-MM-DD HH:MM:SS` strings or empty. THE SERVER
    AND THE FRAMEWORK ARE BOTH UTC, so the comparison is a string comparison
    with no arithmetic and no timezone library — and it cannot raise on a value
    somebody hand-edited into the settings table. The day this box moves to a
    local zone, this line is what quietly stops working; it says so here.

    An open-ended window (no end) never ends. A window with no start has always
    started. Both are deliberate: a message with no window at all is a message
    that stands until it is cleared, which is what "info" usually is.
    """
    now = str(now or '')[:19]
    starts = str(starts or '')[:19]
    ends = str(ends or '')[:19]
    if ends and ends <= now:
        return 'over'
    if starts and starts > now:
        return 'before'
    return 'during'


def read_notice(raw_text, kind, starts, ends, now):
    """The message to show right now, or None. PURE.

    A notice carries the moment it stops being true, and the platform is NOT
    expected to come back and clear it: "we are updating between 22:00 and
    01:00" has to leave the screen at 01:00 whether or not anybody remembered.
    So the end is checked here, on every read, on the reader's side.

    `live` is the difference between the two states this bar has: before the
    window it is a warning about something planned, inside it is an explanation
    for something happening now. The words change; the record does not.
    """
    text = (raw_text or '').strip()
    if not text:
        return None
    phase = notice_phase(starts, ends, now)
    if phase == 'over':
        return None
    kind = (kind or '').strip()
    if kind not in NOTICE_KINDS:
        kind = 'info'
    return {
        # A stable identity so that somebody who hides one message still meets
        # the next. The platform does not send an id, so the message itself is
        # the identity — a new message is new text.
        'id': '%s|%s|%s' % (kind, str(starts or '')[:19], text[:120]),
        'kind': kind,
        'text': text,
        'starts_at': str(starts or '')[:19],
        'ends_at': str(ends or '')[:19],
        # Only a maintenance window is ever "happening now". An informational
        # message inside its own window is just a message.
        'live': bool(phase == 'during' and kind == 'maintenance'
                     and (starts or ends)),
    }


def read_releases(raw, current, limit=RELEASE_HISTORY):
    """`[{'name','date','notes'}]`, newest first. PURE, and never raises.

    Damage is read as "no history": a malformed string must never take the
    About screen down, and the release the reader is actually on is carried
    separately anyway, so the useful half survives.

    Sorted on the date and then on the name, both descending, so two releases
    cut on the same day (`2026.09.04` and `2026.09.04-2`) come out in the order
    they happened — the suffix sorts after the bare name, which is why the name
    is reversed too.
    """
    rows = []
    try:
        data = json.loads(raw or '[]')
    except (ValueError, TypeError):
        _logger.warning("biz_tenancy: the release history is not readable; "
                        "showing only the release this system is on.")
        data = []
    if not isinstance(data, list):
        data = []
    for r in data:
        if not isinstance(r, dict):
            continue
        name = (r.get('name') or '').strip()
        if not name:
            continue
        rows.append({
            'name': name,
            'date': str(r.get('date') or '').strip()[:10],
            'notes': (r.get('notes') or '').strip(),
            'current': bool(current) and name == current,
        })
    rows.sort(key=lambda r: (r['date'], r['name']), reverse=True)
    return rows[:max(0, int(limit))]


def read_features(raw):
    """Which parts of the product this system has. PURE. NOT USED YET.

    The seam the next phase's switches read, built now so that the rule it
    obeys is written down once (handover §3.7):

      * ABSENT means everything is on. A system nobody has told anything to
        must not lose half its product overnight because a setting has not
        arrived yet.
      * UNREADABLE means the same thing — but it SAYS SO in the log, with the
        reason. A guard that fails open and swallows its reason is a door that
        opened silently, which is exactly the fault F53 was (ledger).

    Returns `{key: bool}`; an empty dict means "nothing is switched off".
    """
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        _logger.warning(
            "biz_tenancy: the feature settings could not be read (%s is not "
            "valid JSON), so every part of the product stays switched on. "
            "This is the fail-open path and it is deliberate.", P_FEATURES)
        return {}
    if not isinstance(data, dict):
        _logger.warning(
            "biz_tenancy: the feature settings are not a set of switches, so "
            "every part of the product stays switched on.")
        return {}
    return {k: bool(v.get('on', True) if isinstance(v, dict) else v)
            for k, v in data.items() if isinstance(k, str) and k}


class BizTenancy(models.AbstractModel):
    _name = 'biz.tenancy'
    _description = 'Platform link'

    # ------------------------------------------------------------------ reads
    def _row(self, key):
        """The setting's OWN value, `None` when there is no row at all — F24.

        This is the whole reason `get_param` is not used anywhere in this file.
        "Nobody has ever said" and "somebody cleared it" are different answers,
        and only one of them means the platform is working.
        """
        row = self.env['ir.config_parameter'].sudo().search(
            [('key', '=', key)], limit=1)
        if not row:
            return None
        return row.value or ''

    def _text(self, key):
        """The setting as a string, empty for either kind of absence."""
        return self._row(key) or ''

    @api.model
    def brand(self):
        """The product's name, as this system's owner set it.

        NEVER a literal fallback with a product name in it (rail R12). A system
        with no brand set is described as "the system", which is true of every
        product this module will ever be installed on.
        """
        return self._text(P_BRAND).strip() or self.env._("the system")

    @api.model
    def state(self):
        """Everything the browser needs, in one dict, read in one go.

        Called from `session_info`, so it runs on EVERY page load of EVERY user
        on this system. It is therefore a handful of settings reads and nothing
        else; it must never raise; and it must be safe for somebody with no
        permissions at all, because it is chrome rather than data.
        """
        now = fields.Datetime.now().strftime(_STAMP)
        release = self._text(P_RELEASE).strip()
        return {
            'brand': self.brand(),
            'release': release,
            'release_notes': self._text(P_RELEASE_NOTES),
            'release_at': self._text(P_RELEASE_AT).strip()[:10],
            'releases': read_releases(self._text(P_RELEASES), release),
            'notice': read_notice(
                self._text(P_NOTICE), self._text(P_NOTICE_KIND),
                self._text(P_NOTICE_FROM), self._text(P_NOTICE_TO), now),
            'pushed_at': self._text(P_PUSHED_AT).strip(),
            'platform_url': self._text(P_PLATFORM_URL).strip(),
            'support_email': self._text(P_SUPPORT_EMAIL).strip(),
            # Used only to word a sentence on the About screen. Nothing is
            # hidden or shown on the strength of it.
            'is_platform': not self._text(P_SLUG).strip(),
        }

    @api.model
    def features(self):
        """`{key: bool}` — the seam the next phase's gates read. Absent = on."""
        return read_features(self._text(P_FEATURES))
