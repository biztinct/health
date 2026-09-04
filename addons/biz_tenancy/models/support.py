# -*- coding: utf-8 -*-
"""Somebody from the platform, inside this system, with a reason and a clock.

THE PROBLEM THIS SOLVES, AND WHY IT IS A MODEL ON THE CUSTOMER'S OWN SYSTEM.
Sooner or later whoever runs the platform has to look at a customer's screen to
answer a question about it. Until now the only ways in were to know somebody's
password or to have kept an account of our own on their system — and both of
those are permanent, invisible and unaccountable. This is the third way: a door
that has to be opened for a stated reason, closes itself, and leaves a record
THE CUSTOMER CAN READ, on their own system, whether or not the platform is
reachable.

The record lives here, not on the platform, for exactly that reason. A trail
kept by the people it is about is not a trail.

FIVE THINGS ARE WRITTEN DOWN, and each of them because its absence would make
the record worth nothing: WHO came in, WHEN, WHY (typed, required, never a
list to pick from), HOW LONG the door was open for, and WHICH SCREENS were
opened.

⚠ AND THE CUSTOMER CAN REFUSE IT ENTIRELY (`biz_tenancy.support_allowed`, on
their own About screen). A door only one side can open is not support, it is
access.

⚠ THE TOKEN IS NEVER STORED. Only its SHA-256 is, so this table is worth
nothing to anybody who reads it — including us. A link that has been used is
refused a second time, by state and by a cleared hash.
"""
import hashlib
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

#: How the trail describes each state, in the CUSTOMER's words.
STATE_WORDS = {
    'issued': "A link was made and has not been used",
    'active': "Somebody is in the system now",
    'ended': "Finished",
    'expired': "The time ran out",
    'refused': "Refused",
}

#: The addresses that are NOT screens (ledger F66). A page load is thirty
#: requests, and a trail of stylesheets and avatars is a record of nothing.
NOT_A_SCREEN = ('/web/', '/mail/', '/bus/', '/websocket', '/longpolling',
                '/biz_tenancy/', '/favicon', '/im_livechat/', '/report/')

#: Longest a door may be held open, whatever anybody asks for. An hour is long
#: enough for any real question and short enough that a forgotten session is a
#: nuisance rather than a standing arrangement.
MAX_MINUTES = 60


def token_hash(token):
    """The only form of a link this system ever keeps. PURE."""
    return hashlib.sha256(str(token or '').encode('utf-8')).hexdigest()


def is_screen_path(path):
    """Is this address a screen somebody opened, or plumbing? PURE.

    ⚠ Ledger F66. The first version of this trail wrote down every stylesheet,
    avatar, translations bundle and websocket upgrade, and the two screens
    somebody actually opened were invisible among thirty-three lines of
    `/web/image`. A trail that records requests is a record of nothing.
    """
    path = str(path or '').strip()
    if not path or not path.startswith('/'):
        return False
    if path.startswith(NOT_A_SCREEN):
        return False
    # Anything with a file extension in its last segment is an asset.
    last = path.rstrip('/').rsplit('/', 1)[-1]
    if '.' in last:
        return False
    return True


class BizSupportSession(models.Model):
    _name = 'biz.support.session'
    _description = 'Somebody from the platform, in this system'
    _order = 'issued_at desc, id desc'

    reason = fields.Char(
        required=True,
        help="Why the platform needed to come in. Typed by the person who "
             "opened the door, never chosen from a list — a reason picked "
             "from a menu is a reason nobody wrote.")
    minutes = fields.Integer(
        default=30, required=True,
        help="How long the door stays open for, in minutes.")
    state = fields.Selection([(k, v) for k, v in STATE_WORDS.items()],
                             default='issued', required=True, index=True)

    #: ⚠ THE HASH, NEVER THE LINK. Cleared the moment the link is used.
    token_sha = fields.Char(index=True)

    issued_at = fields.Datetime(default=fields.Datetime.now, required=True)
    link_expires_at = fields.Datetime(
        help="When an unused link stops working.")
    opened_at = fields.Datetime()
    expires_at = fields.Datetime(help="When the door closes on its own.")
    ended_at = fields.Datetime()
    end_reason = fields.Char()

    operator_name = fields.Char(help="Who, on the platform's side.")
    platform_name = fields.Char(help="The platform, in its own words.")
    platform_url = fields.Char()
    user_id = fields.Many2one(
        'res.users', ondelete='set null',
        help="The account the link signs in as. Never a person's own account.")

    screen_ids = fields.One2many('biz.support.screen', 'session_id')
    screen_count = fields.Integer(compute='_compute_screen_count')

    @api.depends('screen_ids')
    def _compute_screen_count(self):
        for rec in self:
            rec.screen_count = len(rec.screen_ids)

    # =====================================================================
    #  MINTING — called by the platform, through its own single door
    # =====================================================================
    @api.model
    def mint(self, vals):
        """Write down that a link has been made. Returns the row's id.

        THE PLATFORM MAKES THE TOKEN AND SENDS ITS HASH. This system never
        sees the token at all until somebody arrives holding it, which is the
        only arrangement in which the record here cannot be used to get in.
        """
        vals = dict(vals or {})
        minutes = max(1, min(int(vals.get('minutes') or 30), MAX_MINUTES))
        reason = (vals.get('reason') or '').strip()
        if not reason:
            raise ValueError("a support session needs a reason")
        user = self.env['res.users'].sudo().browse(
            int(vals.get('user_id') or 0)).exists()
        row = self.sudo().create({
            'reason': reason[:300],
            'minutes': minutes,
            'token_sha': vals.get('token_sha') or '',
            'operator_name': (vals.get('operator_name') or '')[:120],
            'platform_name': (vals.get('platform_name') or '')[:120],
            'platform_url': (vals.get('platform_url') or '')[:200],
            'user_id': user.id if user else False,
            'link_expires_at': fields.Datetime.add(
                fields.Datetime.now(), minutes=minutes),
        })
        _logger.info("biz_tenancy: a support link was made for %s (%s min): %s",
                     row.operator_name or 'the platform', minutes, row.reason)
        return row.id

    @api.model
    def refuse(self, vals):
        """A door somebody tried to open and this system refused.

        ⚠ THE REFUSAL LEAVES A MARK, and that is the whole point of writing it
        down here rather than only on the platform. A customer who has switched
        support off wants to know when somebody tried, not to be told nothing
        happened.
        """
        vals = dict(vals or {})
        row = self.sudo().create({
            'reason': (vals.get('reason') or 'no reason given').strip()[:300],
            'minutes': max(1, int(vals.get('minutes') or 30)),
            'state': 'refused',
            'operator_name': (vals.get('operator_name') or '')[:120],
            'platform_name': (vals.get('platform_name') or '')[:120],
            'platform_url': (vals.get('platform_url') or '')[:200],
            'ended_at': fields.Datetime.now(),
            'end_reason': (vals.get('refusal')
                           or "This system does not allow support access."),
        })
        _logger.info("biz_tenancy: a support link was REFUSED: %s",
                     row.end_reason)
        return row.id

    # =====================================================================
    #  USING THE LINK
    # =====================================================================
    @api.model
    def redeem(self, token):
        """Find the session this link belongs to, or say why not. ONE USE.

        Returns `(session, reason_it_was_refused)`. The reason is a sentence
        for a person, never a code: somebody holding a link that has expired
        should be told it has expired, not that something went wrong.
        """
        if not token:
            return self.browse(), "This link is not complete."
        row = self.sudo().search(
            [('token_sha', '=', token_hash(token))], limit=1)
        if not row:
            # Deliberately the same sentence for "never existed" and "already
            # used": a link that has been used has its hash cleared, and
            # telling the two apart would tell somebody guessing which of
            # their guesses was once real.
            return self.browse(), ("This link has already been used, or it is "
                                   "not a link this system knows.")
        now = fields.Datetime.now()
        if row.state != 'issued':
            return self.browse(), "This link has already been used."
        if row.link_expires_at and row.link_expires_at < now:
            row.write({'state': 'expired', 'ended_at': now, 'token_sha': '',
                       'end_reason': "The link was never used and ran out."})
            return self.browse(), ("This link ran out before it was used. Ask "
                                   "for a new one.")
        if not row.user_id or not row.user_id.active:
            return self.browse(), ("The account this link signs in as is not "
                                   "available on this system.")
        return row, ''

    def open_now(self):
        """Mark the door open and start the clock. WRITES."""
        self.ensure_one()
        now = fields.Datetime.now()
        self.sudo().write({
            'state': 'active',
            'opened_at': now,
            # ⚠ CLEARED HERE, which is what makes the link single-use. It is
            # cleared in the same write that opens the door, so there is no
            # window in which two people could both arrive holding it.
            'token_sha': '',
            'expires_at': fields.Datetime.add(now, minutes=self.minutes),
        })
        _logger.info("biz_tenancy: a support session is open until %s — %s",
                     self.expires_at, self.reason)
        return self

    def finish(self, reason=''):
        """Close the door. Explicit, at the time box, or on signing out."""
        now = fields.Datetime.now()
        rows = self.sudo().filtered(lambda r: r.state in ('issued', 'active'))
        if not rows:
            return self
        rows.write({
            'state': 'ended' if reason != 'expired' else 'expired',
            'ended_at': now, 'token_sha': '',
            'end_reason': {
                '': "It was finished.",
                'expired': "The time ran out and it closed on its own.",
                'signout': "Whoever was in signed out.",
                'operator': "It was finished by the person who opened it.",
                'customer': "It was ended from this system.",
            }.get(reason, reason),
        })
        _logger.info("biz_tenancy: closed %d support session records "
                     "(%s)", len(rows), reason or 'finished')
        return self

    # =====================================================================
    #  WHAT IS HAPPENING RIGHT NOW
    # =====================================================================
    @api.model
    def current(self):
        """The session this request is inside, or an empty recordset.

        A read, so it is safe on the read-only cursor most pages are served
        on. Closing an expired one is somebody else's job (`sweep`).
        """
        uid = self.env.uid
        if not uid:
            return self.browse()
        return self.sudo().search(
            [('state', '=', 'active'), ('user_id', '=', uid)],
            order='opened_at desc', limit=1)

    @api.model
    def sweep(self):
        """Close anything whose clock has run out. WRITES."""
        now = fields.Datetime.now()
        due = self.sudo().search([('state', '=', 'active'),
                                  ('expires_at', '<=', now)])
        if due:
            due.finish('expired')
        stale = self.sudo().search([('state', '=', 'issued'),
                                    ('link_expires_at', '<=', now)])
        if stale:
            stale.write({'state': 'expired', 'ended_at': now, 'token_sha': '',
                         'end_reason': "The link was never used and ran out."})
        return len(due) + len(stale)

    @api.model
    def pending_count(self):
        """How many doors are open OR waiting to be opened.

        ⚠ `issued` COUNTS (ledger F68). Reading this the instant a button is
        pressed finds a link that has been made and not yet used; treating that
        as "nothing is running" closes the alert about a session that has not
        begun.
        """
        return self.sudo().search_count([('state', 'in', ('issued', 'active'))])

    # =====================================================================
    #  THE TRAIL
    # =====================================================================
    def note_screen(self, path, name=''):
        """Write down a screen that was opened. WRITES.

        ⚠ A REPEAT OF THE SAME ADDRESS FILLS THE NAME IN RATHER THAN BEING
        THROWN AWAY (ledger F66). The request seam sees the address BEFORE the
        page has a name, so the first line for a screen is nameless; the
        browser reports again when the title arrives, and that second report
        has to be allowed to complete the first one.
        """
        self.ensure_one()
        path = str(path or '').split('?')[0].strip()
        if not is_screen_path(path):
            return self.env['biz.support.screen']
        Screen = self.env['biz.support.screen'].sudo()
        row = Screen.search([('session_id', '=', self.id),
                             ('path', '=', path)], limit=1)
        now = fields.Datetime.now()
        name = (name or '').strip()[:120]
        if row:
            vals = {'last_seen': now, 'count': row.count + 1}
            if name and not row.name:
                vals['name'] = name
            row.write(vals)
            return row
        return Screen.create({'session_id': self.id, 'path': path,
                              'name': name, 'first_seen': now,
                              'last_seen': now, 'count': 1})

    # =====================================================================
    #  WHAT THE CUSTOMER READS
    # =====================================================================
    @api.model
    def trail(self, limit=25):
        """Every time the platform has been in, newest first."""
        out = []
        for s in self.sudo().search([], limit=int(limit)):
            out.append({
                'id': s.id,
                'state': s.state,
                'state_label': STATE_WORDS.get(s.state, s.state),
                'reason': s.reason,
                'minutes': s.minutes,
                'who': s.operator_name or s.platform_name or '',
                'platform': s.platform_name or '',
                'issued_at': s.issued_at,
                'opened_at': s.opened_at or None,
                'ended_at': s.ended_at or None,
                'expires_at': s.expires_at or None,
                'end_reason': s.end_reason or '',
                'screens': [{'path': x.path, 'name': x.name or '',
                             'count': x.count, 'first_seen': x.first_seen}
                            for x in s.screen_ids.sorted('first_seen')],
            })
        return out


class BizSupportScreen(models.Model):
    _name = 'biz.support.screen'
    _description = 'A screen opened during a support session'
    _order = 'first_seen, id'

    session_id = fields.Many2one('biz.support.session', required=True,
                                 ondelete='cascade', index=True)
    path = fields.Char(required=True)
    name = fields.Char(help="What the screen was called, once the page said.")
    first_seen = fields.Datetime(default=fields.Datetime.now)
    last_seen = fields.Datetime(default=fields.Datetime.now)
    count = fields.Integer(default=1)

    _one_row_per_screen = models.Constraint(
        'UNIQUE (session_id, path)',
        "One line per screen per session, with a count on it.")
