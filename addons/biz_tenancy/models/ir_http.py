# -*- coding: utf-8 -*-
"""The platform's message rides in with the page, not after it.

WHY NOT JUST ASK THE SERVER FROM THE BROWSER. Because then the top of every
page would be empty for the length of a round trip and the bar would drop in a
beat late — on every navigation, for every person, for ever. A warning that
arrives after somebody has started typing is a worse warning than none. So the
state travels in `session_info`, which the page already carries, and the bar is
drawn on the first paint with no request of its own.

The 60-second poll (`/biz_tenancy/state`) exists for the OTHER case: a tab that
has been open for an hour when the platform sends something.
"""
import logging

import werkzeug.exceptions

from odoo import fields, models
from odoo.exceptions import AccessDenied
from odoo.http import request

from .support import is_screen_path

_logger = logging.getLogger(__name__)

#: ⚠ WHERE THE PAUSED DOOR IS NOT, AND EVERY LINE OF THIS LIST IS THERE FOR A
#: REASON SOMEBODY WOULD OTHERWISE MEET AS A LOOP OR A BLANK PAGE.
#:
#:   * the paused page itself, or the redirect would loop for ever;
#:   * the sign-in and sign-out pages, so the recovery account can get in and
#:     so the person who was redirected can sign out;
#:   * the assets and images the paused page is DRAWN FROM — a door that is
#:     served without its own stylesheet is a wall of unstyled text;
#:   * `/biz_tenancy/state`, which is how a tab that is ALREADY OPEN finds out
#:     it has been paused and takes itself to the page. Without it a paused
#:     system's people would carry on working in the tab they had open until
#:     they happened to navigate.
#:
#: Prefix matching, and the list is deliberately short: anything not on it is
#: shut.
PAUSED_OPEN_PREFIXES = (
    '/biz_tenancy/',
    '/web/login',
    '/web/session/logout',
    '/web/session/destroy',
    '/web/session/authenticate',
    '/web/reset_password',
    '/web/assets',
    '/web/static',
    '/web/image',
    '/web/binary',
    '/web/health',
    '/websocket',
    '/longpolling',
    '/favicon.ico',
)

#: Where a paused system's people are sent.
PAUSED_PAGE = '/biz_tenancy/paused'


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    # =====================================================================
    #  THE SUPPORT SESSION'S TWO EDGES, AND THE PAUSED DOOR
    # =====================================================================
    @classmethod
    def _pre_dispatch(cls, rule, args):
        """Close a session whose time has run out, note the screen, and — for
        a paused system — turn everybody but the recovery account away.

        ⚠ THIS RE-RAISES `ReadOnlySqlTransaction` DELIBERATELY (ledger F62's
        second half). Most pages in this product are served on a read-only
        cursor; both things below WRITE. The framework knows how to recover —
        `_serve_db` catches that error and runs the whole request again on a
        read/write cursor — and swallowing it here would silently lose the end
        of a support session, which is the one moment this whole feature exists
        for. So nothing is caught but the errors that are genuinely ours.
        """
        super()._pre_dispatch(rule, args)
        cls._biz_paused_door(rule)
        try:
            cls._biz_support_tick()
        except Exception as e:                               # noqa: BLE001
            if type(e).__name__ == 'ReadOnlySqlTransaction':
                raise
            _logger.warning("biz_tenancy: the support session could not be "
                            "kept up to date on this request", exc_info=True)

    # =====================================================================
    #  THE PAUSED DOOR
    # =====================================================================
    @classmethod
    def _biz_paused_door(cls, rule):
        """A paused system's people meet a calm page instead of their work.

        THE DATA IS UNTOUCHED. This is a door, not a deletion: nothing is
        archived, nothing is dropped, and the moment somebody lets them back in
        on the platform the very next request goes straight through.

        ⚠ FAIL OPEN, ALWAYS — AND SAY WHY IN THE LOG LINE (ledger F53). A
        broken settings row, a half-installed module, a system with no platform
        link yet: none of those may be allowed to shut a working system out of
        its own records. The only thing that closes this door is the platform
        saying so. And the reason goes in the MESSAGE rather than only in a
        traceback, because this is the one place in the product where a silent
        failure means an OPEN DOOR, and the line is the only thing anybody
        greps on a live box.
        """
        try:
            cls._biz_paused_decide(rule)
        except (werkzeug.exceptions.HTTPException, AccessDenied):
            # The door doing its job. Never swallowed.
            raise
        except Exception as exc:                             # noqa: BLE001
            if type(exc).__name__ == 'ReadOnlySqlTransaction':
                raise
            _logger.warning(
                "biz_tenancy: the paused door could not read this system's "
                "standing (%r); THE REQUEST WAS LET THROUGH. This is the "
                "fail-open path and it is deliberate — but if these lines are "
                "here, a paused system is not actually paused.",
                exc, exc_info=True)

    @classmethod
    def _biz_paused_decide(cls, rule):
        """Who gets through a paused system's door, and who does not.

        ⚠ `request.env.uid` FIRST, AND `request.session.uid` ONLY AS A
        FALLBACK (ledger F53, and this is the trap that cost the most).
        A route declared `auth='none'` runs with an environment whose uid is
        None EVEN WHEN SOMEBODY IS SIGNED IN — so `request.env.user` is an
        EMPTY RECORDSET and `has_group()` on it raises
        `ValueError: Expected singleton`. On the platform this was ported from
        that exception was caught by the fail-open handler above, which let
        EVERY REQUEST THROUGH, silently, on every page. And `/odoo` on this
        build is exactly such a route — the redirect to this product's own
        prefix — so the door was open on the first hop of every navigation.
        The session still knows who it is, so the user is browsed explicitly.

        THREE THINGS STILL GET IN:
          * the recovery account, whose login is mirrored onto this system
            precisely so this check does not need the platform to be reachable;
          * an active support session, so somebody from the platform can go in
            and fix whatever caused the pause;
          * anybody holding the platform's own administrator permission, which
            on a customer's system is normally nobody at all (the two-ring rule
            sees to that).
        """
        if not request:
            return
        uid = request.env.uid or request.session.uid
        if not uid:
            # Nobody is signed in. The sign-in page is not behind this door —
            # somebody has to be able to get in and see the message.
            return
        path = request.httprequest.path or ''
        if path.startswith(PAUSED_OPEN_PREFIXES):
            return
        env = request.env
        if 'biz.tenancy' not in env:
            return
        state = env['biz.tenancy'].sudo().access_state()
        if state['access'] != 'paused':
            return
        user = env['res.users'].sudo().browse(uid).exists()
        if not user:
            return
        recovery = env['biz.tenancy'].sudo().recovery_login()
        if recovery and (user.login or '').strip().lower() == recovery:
            return
        try:
            # ⚠ SEARCHED ON THE uid THIS METHOD ALREADY RESOLVED, NOT THROUGH
            # `current()` — WHICH IS F53 ONE LAYER DOWN. `current()` reads
            # `env.uid`, and on an `auth='none'` route that is None even though
            # somebody is signed in: it would answer "no session" and lock the
            # operator who came in to fix the problem out of the problem. The
            # door has already worked out who this is; it asks about them.
            if env['biz.support.session'].sudo().search_count(
                    [('state', '=', 'active'), ('user_id', '=', uid)]):
                return
        except Exception:                                    # noqa: BLE001
            _logger.debug("biz_tenancy: could not read the support session at "
                          "the paused door", exc_info=True)
        if user.has_group('base.group_system'):
            return
        # An `http` request is a PAGE: send them somewhere that explains
        # itself. Anything else is a call from a page that is already open —
        # refuse it by name, and that tab's own poll will move it along.
        if (rule.endpoint.routing.get('type') or 'http') == 'http':
            werkzeug.exceptions.abort(request.redirect(PAUSED_PAGE))
        raise AccessDenied(state['access_text'])

    @classmethod
    def _biz_support_tick(cls):
        """One write, and only when there is something to write."""
        if not (request and request.session.uid):
            return
        Session = request.env['biz.support.session'].sudo()
        session = Session.current()
        if not session:
            return
        if session.expires_at and session.expires_at <= fields.Datetime.now():
            session.finish('expired')
            # The door is shut, so whoever was holding it open is signed out
            # in the same breath. Leaving them signed in with the record closed
            # would make the record a lie.
            request.session.logout(keep_db=True)
            return
        # ⚠ ONLY A PAGE SOMEBODY NAVIGATED TO IS A SCREEN (ledger F66, and one
        # more turn of it found on a live customer's system).
        #
        # A path filter alone is not enough. `/website/translations` has no
        # file extension and is not on any deny list, so it went onto a
        # customer's own record as a screen somebody opened — which it is not;
        # it is a fetch the page makes for itself. Naming every such route in a
        # list is a list that will always be one release behind.
        #
        # The browser already says which is which. `Sec-Fetch-Dest: document`
        # means "this request IS the page in the address bar"; anything the
        # page fetches for itself says `empty`, `script`, `style` or `image`.
        # It is a rule about the KIND of request rather than about a set of
        # names, so it cannot go stale. A browser too old to send the header
        # falls back to the path rule, which is the old behaviour.
        req = request.httprequest
        dest = req.headers.get('Sec-Fetch-Dest') or 'document'
        if req.method == 'GET' and dest == 'document' and is_screen_path(req.path):
            session.note_screen(req.path)

    @classmethod
    def _post_logout(cls):
        """Signing out ends a support session, whatever else happens.

        A CLASSMETHOD, because the framework's own is one — an instance method
        here would shadow it with a different calling convention and the whole
        sign-out path would break for everybody.
        """
        try:
            # ⚠ `request.env.uid`, NOT `request.session.uid`. The framework
            # CLEARS the session before it calls this, so the session's own uid
            # is already gone by the time anybody here could read it — and the
            # symptom would be a session that quietly never closed.
            uid = request and request.env and request.env.uid
            if uid:
                request.env['biz.support.session'].sudo().search(
                    [('state', '=', 'active'),
                     ('user_id', '=', uid)]).finish('signout')
        except Exception as e:                               # noqa: BLE001
            # Same rule as `_pre_dispatch` above (ledger F62): the read-only
            # error is the framework asking to run the request again, and
            # swallowing it here loses the end of a support session.
            if type(e).__name__ == 'ReadOnlySqlTransaction':
                raise
            _logger.warning("biz_tenancy: a support session may not have been "
                            "closed on sign-out", exc_info=True)
        return super()._post_logout()

    def session_info(self):
        info = super().session_info()
        # Nothing for a visitor who is not signed in: there is no page with our
        # chrome on it to put a bar at the top of.
        if not (request and request.session.uid):
            return info
        try:
            info['biz_tenancy'] = self.env['biz.tenancy'].state()
        except Exception:                                    # noqa: BLE001
            # A damaged settings row must never stop somebody signing in. The
            # browser reads a missing key as "no message, no release".
            _logger.warning("biz_tenancy: could not read the platform state "
                            "for this session", exc_info=True)
        return info
