# -*- coding: utf-8 -*-
"""One route, for the tabs that are already open.

A message sent at 14:00 has to reach somebody who opened their work at 09:00
and has not navigated since. There is no bus channel and no websocket here on
purpose — a channel per system, held open for a message that arrives twice a
month, is not a trade worth making — so the browser asks, once a minute, while
somebody is actually looking at the page.

`auth='user'` and nothing else: the answer is chrome for the person already
signed in, so there is no argument to check and nothing to authorise beyond
"are you inside".
"""
import logging

from odoo import http
from odoo.addons.web.controllers.action import Action
from odoo.http import request

_logger = logging.getLogger(__name__)

#: Where a support link lands.
#:
#: ⚠ NOT `/`, AND THAT WAS FOUND BY WALKING IT. On a system that also serves a
#: public website, `/` is the MARKETING PAGE — so the operator followed their
#: own link, was signed in correctly, and arrived on a home page with a "Sign
#: in" button on it, looking exactly like a link that had not worked. This is
#: the framework's own backend root, and a product that serves its application
#: somewhere else redirects this to it (which is what happens here).
BACKEND_ROOT = '/odoo'


class BizTenancyActionGuard(Action):
    """A screen belonging to a part that is not switched on says so.

    ⚠ THE SERVER DECIDES, NOT THE BROWSER (ledger F48). Hiding an entry on the
    left menu is not the same as closing the door behind it: a bookmark, a tab
    somebody left open last week, a link in a message all reach the screen
    directly. Every one of them comes through here, so this is the one place
    that can answer them all — and it answers with a PAGE rather than a 404 or
    a traceback, because somebody following their own bookmark has done
    nothing wrong.

    It is a subclass of the framework's own controller with the same route, so
    it replaces it rather than running beside it. The cost on the ordinary path
    is `features_off()` — one cached settings read — and a return.
    """

    @http.route()
    def load(self, action_id, context=None):
        result = super().load(action_id, context=context)
        try:
            blocked = request.env['biz.tenancy'].feature_block(action_id,
                                                               result)
        except Exception:                                    # noqa: BLE001
            # A fault in this guard must never stop somebody opening a screen.
            # It is logged with its reason, because a guard that fails quietly
            # is a guard nobody knows has stopped working (ledger F53).
            _logger.warning("biz_tenancy: the switched-off check could not "
                            "run for action %s; the screen was opened.",
                            action_id, exc_info=True)
            return result
        return blocked or result


class BizTenancyController(http.Controller):

    # `type='jsonrpc'` and NOT `type='json'`: the older spelling is a
    # deprecated alias on this framework and logs a line on every boot
    # (ledger F21). `readonly=True` puts the call on a read-only cursor, which
    # is the honest description of a method that reads ten settings.
    @http.route('/biz_tenancy/state', type='jsonrpc', auth='user',
                readonly=True)
    def tenancy_state(self, **kw):
        """What the platform has said, as of this second. Reads nothing else."""
        return request.env['biz.tenancy'].state()

    # =====================================================================
    #  SUPPORT ACCESS
    # =====================================================================
    #
    # ⚠ `readonly=False`, AND IT IS NOT DECORATION (ledger F62). A route
    # declared `auth='none'` is READ-ONLY BY DEFAULT on this framework —
    # `odoo/http.py`: `default_mode = routing.get('readonly', default_auth ==
    # 'none')`. Signing somebody in WRITES (the session token, the last-login
    # stamp, this feature's own row), so without this the door answers "cannot
    # execute INSERT in a read-only transaction".
    #
    # ⚠ AND `authenticate` IS NOT INSIDE A BARE `except Exception`. The
    # framework recovers from a read-only transaction by running the whole
    # request again on a read/write cursor; a blanket catch turns that recovery
    # into "your link has expired" and hides the real fault for a whole test
    # cycle. That is exactly what happened on the platform this was ported from.
    # The address carries `/link/` so that no token can ever be confused with
    # one of the four routes below it. Rule ordering would probably have got
    # this right; "probably" is not a thing to build a sign-in door on.
    @http.route('/biz_tenancy/support/link/<string:token>', type='http',
                auth='none', readonly=False, csrf=False, sitemap=False)
    def support_open(self, token, **kw):
        """One link, one use: sign the operator in for the time box."""
        Session = request.env['biz.support.session'].sudo()
        session, refusal = Session.redeem(token)
        if refusal:
            _logger.info("biz_tenancy: a support link was not accepted — %s",
                         refusal)
            return request.render('biz_tenancy.support_link_refused', {
                'reason': refusal,
                'brand': request.env['biz.tenancy'].sudo().brand(),
            })
        user = session.user_id
        session.open_now()
        # The framework's own way in, and nothing home-made: `finalize` builds
        # the session token the same way every other sign-in on this system
        # does, so a token this route mints is indistinguishable from a real
        # one — including on the day the framework changes how it is computed.
        request.session['pre_login'] = user.login
        request.session['pre_uid'] = user.id
        request.session.finalize(request.env(user=user.id))
        request.update_env(user=user.id)
        session.note_screen(BACKEND_ROOT, "Signed in")
        _logger.info("biz_tenancy: support session %s opened for %s until %s",
                     session.id, user.login, session.expires_at)
        return request.redirect(BACKEND_ROOT)

    @http.route('/biz_tenancy/support/seen', type='jsonrpc', auth='user',
                readonly=False)
    def support_seen(self, path='', name='', **kw):
        """The browser says which screen is on it now.

        ⚠ WHY THE BROWSER AND NOT THE REQUEST SEAM ALONE (ledger F66). This
        product's screens are reached without a page load — the address changes
        and nothing is fetched — so the server sees the FIRST address of a
        session and nothing after it. And the request seam sees an address
        before the page has a NAME, so the first line for every screen would
        read as a path. The browser reports both, and a repeat of the same
        address fills the name in rather than being thrown away.
        """
        session = request.env['biz.support.session'].sudo().current()
        if not session:
            return {'ok': False}
        session.note_screen(path, name)
        return {'ok': True}

    @http.route('/biz_tenancy/support/end', type='jsonrpc', auth='user',
                readonly=False)
    def support_end(self, session_id=None, **kw):
        """Finish it now — from the bar, or from the customer's own screen."""
        Session = request.env['biz.support.session'].sudo()
        if session_id:
            rows = Session.browse(int(session_id)).exists()
        else:
            rows = Session.current()
        if not rows:
            return {'ok': False,
                    'message': "There is nobody in this system right now."}
        by_operator = rows.user_id.id == request.env.uid
        rows.finish('operator' if by_operator else 'customer')
        return {'ok': True,
                'message': ("The session has been ended." if by_operator else
                            "Support access has been ended.")}

    @http.route('/biz_tenancy/support/allow', type='jsonrpc', auth='user',
                readonly=False)
    def support_allow(self, allowed=True, **kw):
        """The customer's own switch, from their own About screen.

        ⚠ NOT SOMETHING THE PLATFORM CAN CHANGE. It is deliberately a route on
        the customer's system with `auth='user'`, so the only way to move it is
        to be signed in here — and the platform's own door reads it and refuses
        by name when it is off.
        """
        if not request.env['biz.tenancy'].may_change_support():
            return {'ok': False,
                    'message': ("Only somebody who administers this system "
                                "can change this. Ask whoever set your "
                                "system up.")}
        state = request.env['biz.tenancy'].set_support_allowed(bool(allowed))
        return {'ok': True, 'allowed': state}

    # =====================================================================
    #  THE PAUSED DOOR'S OWN PAGE
    # =====================================================================
    #
    # ⚠ `auth='none'`, AND IT IS ON THE DOOR'S OWN OPEN LIST. This page is
    # where every refused request is sent, so it must be servable by a request
    # that has just been turned away — and it must not itself be behind the
    # door, or the redirect loops for ever.
    #
    # `readonly=True`: it reads three settings and renders. It writes nothing,
    # so nothing on this path can fail on a read-only cursor.
    @http.route('/biz_tenancy/paused', type='http', auth='none',
                readonly=True, sitemap=False)
    def paused_page(self, **kw):
        """The calm page. It also handles "you are back", on purpose.

        Somebody who was let back in while sitting on this page presses their
        browser's reload before they press anything else, and the honest answer
        at that moment is "your access is back" with a way in — not the same
        locked page one more time.
        """
        tenancy = request.env['biz.tenancy'].sudo()
        state = tenancy.access_state()
        return request.render('biz_tenancy.paused_page', {
            'paused': state['access'] == 'paused',
            'text': state['access_text'],
            'brand': tenancy.brand(),
            'support_email': tenancy._text('biz_tenancy.support_email').strip(),
            'home': BACKEND_ROOT,
            'lang': request.env.context.get('lang') or 'en_US',
        })

    @http.route('/biz_tenancy/plan', type='jsonrpc', auth='user',
                readonly=True)
    def plan_usage(self, **kw):
        """The "Plan & usage" card. Read-only, and asked for only when opened."""
        return request.env['biz.tenancy'].plan_usage()

    @http.route('/biz_tenancy/support/trail', type='jsonrpc', auth='user',
                readonly=True)
    def support_trail(self, **kw):
        """Every time the platform has been in, for the customer to read."""
        return {
            'allowed': request.env['biz.tenancy'].support_allowed(),
            # Sent with the list so the screen can say WHY the switch is not
            # available, instead of offering a button that answers back.
            'may_change': request.env['biz.tenancy'].may_change_support(),
            'sessions': request.env['biz.support.session'].trail(),
        }
