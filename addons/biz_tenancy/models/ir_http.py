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

from odoo import fields, models
from odoo.http import request

from .support import is_screen_path

_logger = logging.getLogger(__name__)


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    # =====================================================================
    #  THE SUPPORT SESSION'S TWO EDGES
    # =====================================================================
    @classmethod
    def _pre_dispatch(cls, rule, args):
        """Close a session whose time has run out, and note the screen.

        ⚠ THIS RE-RAISES `ReadOnlySqlTransaction` DELIBERATELY (ledger F62's
        second half). Most pages in this product are served on a read-only
        cursor; both things below WRITE. The framework knows how to recover —
        `_serve_db` catches that error and runs the whole request again on a
        read/write cursor — and swallowing it here would silently lose the end
        of a support session, which is the one moment this whole feature exists
        for. So nothing is caught but the errors that are genuinely ours.
        """
        super()._pre_dispatch(rule, args)
        try:
            cls._biz_support_tick()
        except Exception as e:                               # noqa: BLE001
            if type(e).__name__ == 'ReadOnlySqlTransaction':
                raise
            _logger.warning("biz_tenancy: the support session could not be "
                            "kept up to date on this request", exc_info=True)

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
