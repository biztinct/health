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

#: Which parts of the product this system has, as one JSON object written by
#: the platform. There is exactly one spelling of this key in the product.
P_FEATURES = 'biz_tenancy.features'

#: ⚠ THE CUSTOMER'S OWN SWITCH, AND THE ONLY SETTING ON THIS LIST THEY OWN
#: RATHER THAN READ (SAAS H4c §3.5). Everything else here is written by the
#: platform; this one is written by the customer, on their own About screen,
#: and the platform READS it and refuses its own support door when it is off.
#: A door somebody else can open without asking is not support, it is access.
P_SUPPORT_ALLOWED = 'biz_tenancy.support_allowed'

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


def read_feature_details(raw):
    """Which parts of the product this system has, with their words. PURE.

    ⚠ THE TWO DIRECTIONS THIS FAILS IN ARE DIFFERENT ON PURPOSE, AND BOTH SAY
    WHY (ledger F53).

      * **ABSENT means everything is on.** A system nobody has told anything to
        must not lose half its product overnight because a setting has not
        arrived yet. Fail OPEN, and quietly — there is nothing wrong.
      * **UNREADABLE means everything is OFF.** A settings value that is not
        valid JSON is a value somebody or something has damaged, and the honest
        answer to "which parts has this customer bought?" is then "I do not
        know". Guessing "all of them" hands out a product nobody may have paid
        for, silently and for as long as the damage lasts. Fail CLOSED — and
        say so in the log, at WARNING, with the reason in it, because a
        fail-anything guard that swallows its reason is a decision nobody can
        find.

    Returns `{key: {'on': bool, 'name': str, 'blurb': str}}` plus a `_state`
    entry saying which of the three answers this is: `open`, `read` or
    `closed`. The caller reads `_state` to know whether "nothing off" means
    "nothing off" or "could not tell".
    """
    if not raw:
        return {'_state': 'open'}
    try:
        data = json.loads(raw)
    except (ValueError, TypeError) as e:
        _logger.warning(
            "biz_tenancy: the feature settings on this system could not be "
            "read (%s is not valid JSON: %s). Every part of the product is "
            "treated as SWITCHED OFF until the platform sends a readable "
            "value. This is the fail-closed path and it is deliberate: "
            "guessing that everything is on would hand out a product nobody "
            "may have bought.", P_FEATURES, e)
        return {'_state': 'closed'}
    if not isinstance(data, dict):
        _logger.warning(
            "biz_tenancy: the feature settings on this system are not a set "
            "of switches (%s holds a %s). Every part of the product is "
            "treated as SWITCHED OFF until the platform sends a readable "
            "value.", P_FEATURES, type(data).__name__)
        return {'_state': 'closed'}
    out = {'_state': 'read'}
    for key, val in data.items():
        if not isinstance(key, str) or not key or key.startswith('_'):
            continue
        if isinstance(val, dict):
            out[key] = {'on': bool(val.get('on', True)),
                        'name': str(val.get('name') or key),
                        'blurb': str(val.get('blurb') or '')}
        else:
            out[key] = {'on': bool(val), 'name': key, 'blurb': ''}
    return out


def read_features(raw):  # noqa: D401
    """The same answer, as `{key: bool}`. PURE.

    An empty dict means "nothing is switched off" — which is what BOTH the
    absent case and a settings value with every switch on look like, and is
    the right answer for both. The damaged case is the one that differs, and
    it comes back as `{'__unreadable__': False}` so that a caller reading only
    this shape still fails closed rather than reading "nothing is off".
    """
    detail = read_feature_details(raw)
    if detail.get('_state') == 'closed':
        return {'__unreadable__': False}
    return {k: v['on'] for k, v in detail.items() if k != '_state'}


def features_signature(detail):
    """ONE STRING THAT CHANGES ONLY WHEN THE ANSWER CHANGES (ledger F47).

    The browser has to notice a switch moving, and the obvious way — watch the
    map — repaints once a minute for ever, because the map is rebuilt from a
    fresh read every poll and a reactive sees a new object rather than a new
    answer. So the browser watches this, and the rail is only redrawn when the
    string differs.
    """
    if not isinstance(detail, dict):
        return ''
    state = detail.get('_state') or 'open'
    off = sorted(k for k, v in detail.items()
                 if k != '_state' and isinstance(v, dict) and not v['on'])
    return '%s|%s' % (state, ','.join(off))


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
            # ⚠ A SIGNATURE, NOT THE MAP (ledger F47). The browser watches this
            # one string and redraws the left menu only when it moves; watching
            # the map would repaint the whole menu once a minute for ever,
            # because a fresh read is a fresh object.
            'features_sig': features_signature(
                read_feature_details(self._text(P_FEATURES))),
            'support_allowed': self.support_allowed(),
            'support': self._support_state(),
        }

    def _support_state(self):
        """The rose bar's answer: is somebody from the platform in here now?

        READ ONLY, and it runs on every page load of every person on this
        system, so it is one indexed search and nothing else. Closing an
        expired session is a WRITE and belongs somewhere a write is allowed
        (`ir.http._pre_dispatch`), not here.
        """
        session = self.env['biz.support.session'].current()
        if not session:
            return None
        return {
            'id': session.id,
            'reason': session.reason,
            'who': session.operator_name or session.platform_name or '',
            'platform': session.platform_name or self.brand(),
            'opened_at': (session.opened_at.strftime(_STAMP)
                          if session.opened_at else ''),
            'expires_at': (session.expires_at.strftime(_STAMP)
                           if session.expires_at else ''),
            'minutes': session.minutes,
            # True for the person the door was opened FOR, false for everybody
            # else on the system — who see the same bar and cannot end it,
            # because ending somebody else's session is the customer's own
            # button on their own screen and not a chrome control.
            'is_operator': session.user_id.id == self.env.uid,
        }

    # ------------------------------------------------- which parts we have
    @api.model
    def feature_details(self):
        """`{key: {'on','name','blurb'}}` plus `_state`. The whole answer."""
        return read_feature_details(self._text(P_FEATURES))

    @api.model
    def features(self):
        """`{key: bool}`. Absent = everything on; damaged = everything off."""
        return read_features(self._text(P_FEATURES))

    @api.model
    def features_off(self):
        """The keys that are switched off. A SET, for the gates.

        THE ONE PLACE ANY GATE ASKS. Every rule in the product that hides
        something because a part is not switched on reads this and nothing
        else, so there is one answer and one place to change it.
        """
        detail = self.feature_details()
        if detail.get('_state') == 'closed':
            # Fail closed: we could not tell, so nothing extra is on. The keys
            # are unknown, so the caller is told to hide everything gated.
            return {'*'}
        return {k for k, v in detail.items()
                if k != '_state' and not v['on']}

    @api.model
    def feature_on(self, key):
        """Is this part of the product switched on here?

        The one question a gate asks, in one call, safe to ask anywhere: a
        part nobody has ever mentioned is ON, and a damaged setting is OFF.
        """
        if not key:
            return True
        off = self.features_off()
        return not ('*' in off or key in off)

    @api.model
    def feature_label(self, key):
        """What the customer calls this part, or the key if nobody said."""
        detail = self.feature_details()
        row = detail.get(key)
        return (row or {}).get('name') or key

    # ------------------------------------ the door onto a switched-off part
    @api.model
    def feature_of_action(self, action_id, action=None):
        """Which part of the product does this screen belong to? `''` = none.

        THE SEAM, AND IT IS EMPTY HERE ON PURPOSE. This module has no idea
        what a screen is for; a product overlay overrides this and answers out
        of its own navigation. With nothing overriding it every screen is
        open, which is the honest answer for a system nobody has described.
        """
        return ''

    @api.model
    def feature_block(self, action_id, action=None):
        """The page to show INSTEAD, when a screen's part is switched off.

        ⚠ THE HOT PATH IS THE FIRST TWO LINES, and it has to be, because this
        runs on every screen anybody opens on every system this module is on.
        With nothing switched off — which is every customer, every day, until
        somebody decides otherwise — it is one cached settings read and a
        return.

        NEVER A 404 AND NEVER A TRACEBACK. A part that is not switched on is
        not an error: somebody followed a link, or kept a tab open, or has a
        bookmark from before. They get a page in the product's own voice
        telling them what it is and who to ask.
        """
        off = self.features_off()
        if not off:
            return None
        try:
            key = self.feature_of_action(action_id, action)
        except Exception:                                    # noqa: BLE001
            _logger.warning("biz_tenancy: could not tell which part of the "
                            "product a screen belongs to; it is left open.",
                            exc_info=True)
            return None
        if not key or not ('*' in off or key in off):
            return None
        detail = self.feature_details().get(key) or {}
        name = detail.get('name') or key
        return {
            'type': 'ir.actions.client',
            'tag': 'biz_tenancy_feature_off',
            'name': name,
            'target': 'current',
            'params': {
                'feature': key,
                'label': name,
                'blurb': detail.get('blurb') or '',
                'brand': self.brand(),
                'support_email': self._text(P_SUPPORT_EMAIL).strip(),
                'unreadable': self.feature_details().get('_state') == 'closed',
            },
        }

    # -------------------------------------------- the customer's own switch
    @api.model
    def support_allowed(self):
        """May the people who run the platform come in to help?

        DEFAULTS TO YES, and it is a real default rather than an oversight: a
        customer who has never been asked expects the people they bought the
        product from to be able to look at it when they ring up about a
        problem. Turning it off is a decision they take, on their own screen,
        and the platform's door then refuses BY NAME.
        """
        raw = self._row(P_SUPPORT_ALLOWED)
        if raw is None or raw == '':
            return True
        return str(raw).strip().lower() not in ('0', 'false', 'no', 'off')

    @api.model
    def may_change_support(self):
        """Who, on THIS system, may change that switch. A SEAM (ledger H6).

        ⚠ THE OBVIOUS GATE IS THE WRONG ONE HERE, AND A LIVE SCREEN IS WHAT
        SAID SO. The framework's own administrator permission is exactly what a
        customer's administrator DOES NOT HOLD — that is the two-ring rule, and
        it is the whole reason a customer's administrator cannot reach the
        platform's controls. Gating this on it made the one setting a customer
        owns unusable by the customer: they opened their own About screen and
        were told only an administrator could change it, while being the
        administrator.

        So the default is the framework's tier — right for a product that has
        no other — and a product overlay widens it to whatever it calls the
        people who run one of its systems.
        """
        user = self.env.user
        return bool(self.env.su or user._is_admin()
                    or user.has_group('base.group_system')
                    or user.has_group('base.group_erp_manager'))

    @api.model
    def set_support_allowed(self, allowed):
        """Written by the CUSTOMER, on their own About screen.

        The only setting on this model anybody here writes. It is theirs.
        """
        self.env['ir.config_parameter'].sudo().set_param(
            P_SUPPORT_ALLOWED, '1' if allowed else '0')
        _logger.info("biz_tenancy: support access was switched %s on this "
                     "system by uid %s", 'on' if allowed else 'off',
                     self.env.uid)
        return self.support_allowed()
