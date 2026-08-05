# -*- coding: utf-8 -*-
"""GL-3 — the delegation page. The module's only unauthenticated READ surface.

Everything on the other public routes in this module is a provider talking to
us with a signature we can check. This one is a human with a link, and the link
is the whole credential — so the posture is written out here rather than left
to be inferred:

* **One dead end, four causes.** An unknown token, a revoked invitation, an
  expired one and a provider whose platform application has been archived all
  render the SAME bytes with the SAME 200 status. Nothing on this route tells a
  guesser whether a token ever existed, which step it was for, or whether this
  deployment runs a go-live at all.
* **Rate-limited before the database is touched** (``chub:inv:<ip>``, the
  ``controllers/oauth.py`` counter), so guessing costs more than it can win.
* **The page is READ-ONLY except for its own receipt.** The only writes the
  route can cause are ``view_count`` / ``last_viewed_at`` on the row that was
  opened, the audit row that records the opening, and the rate counter. In
  particular the verify token is never MINTED here: a public route that can
  change what Meta must hold is a public route that can break the handshake.
* **No secrets, ever.** The page renders the step's own words and the values
  Health19 publishes anyway — our redirect address, our webhook addresses, the
  verify token both sides must hold identically. The client secret is pasted by
  a logged-in operator and appears on no page this file can render.
* **No session, no cookie, no index.** ``save_session=False`` (so nothing is
  ever Set-Cookie'd), ``X-Robots-Tag: noindex``, and ``Referrer-Policy:
  no-referrer`` — the token is in the PATH, so without that header the provider
  console would receive it in the ``Referer`` of the deep link (the link itself
  also carries ``rel="noopener noreferrer"``; both, because either one alone is
  one browser quirk away from leaking the credential).
"""
import logging

from markupsafe import Markup

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class GoliveInviteController(http.Controller):

    # ------------------------------------------------------------------
    # Plumbing
    # ------------------------------------------------------------------
    def _rate_limited(self):
        """Cloned from ``ChannelHubOauthController._rate_limited`` (D3), with
        this route's own key prefix so a burst here cannot lock out an OAuth
        callback and vice versa."""
        ip = request.httprequest.remote_addr or 'unknown'
        try:
            allowed, _retry = request.env['gateway.rate.counter'].sudo().hit(
                'chub:inv:%s' % ip)
            return not allowed
        except Exception as exc:  # noqa: BLE001 — never fail the page on it
            _logger.warning('Go-Live invite rate counter error: %s', exc)
            return False

    @staticmethod
    def _respond(html):
        """One response shape for both pages.

        ``make_response`` rather than ``request.render`` for two reasons: a
        QWeb template whose root is ``<html>`` is served with no doctype and
        renders in quirks mode (ledger §5.64a — ``Markup + Markup``, never
        ``str + Markup``, which would escape the doctype), and the security
        headers below need to be set the same way on both branches.
        """
        return request.make_response(
            Markup('<!DOCTYPE html>\n') + html,
            headers=[('Content-Type', 'text/html; charset=utf-8'),
                     ('Cache-Control', 'no-store'),
                     ('X-Robots-Tag', 'noindex, nofollow, noarchive'),
                     ('Referrer-Policy', 'no-referrer')])

    def _dead_end(self):
        """The ONE page for every failure. Rendered with an EMPTY context on
        purpose: nothing about the request may reach these bytes, or the four
        causes stop being indistinguishable."""
        return self._respond(request.env['ir.qweb']._render(
            'health_care_command_channels.golive_invite_dead', {}))

    # ------------------------------------------------------------------
    # The route
    # ------------------------------------------------------------------
    @http.route('/channels/golive/<string:token>', type='http', auth='public',
                methods=['GET'], csrf=False, save_session=False, website=False,
                readonly=False)
    def golive_invite(self, token, **params):
        # (1) rate limit FIRST — before any lookup, so the cost of guessing is
        #     paid before the database is asked anything at all.
        if self._rate_limited():
            return self._dead_end()

        # (2) hash and search. `_resolve` never compares in Python and never
        #     logs the token.
        invite = request.env['channel.golive.invite'].sudo()._resolve(token)

        # (3) missing / revoked / expired — the same dead end, the same status.
        if not invite or not invite._is_live():
            return self._dead_end()

        # The page speaks the language and company of the operator who sent it:
        # the recipient is that operator's colleague, not our anonymous public
        # user, whose language is whatever the database defaults to.
        lang = invite.invited_by_id.sudo().lang or request.env.lang
        App = request.env['channel.platform.app'].sudo().with_context(lang=lang)
        values = App._golive_invite_values(invite)
        # ...and so is an archived platform application (fourth cause).
        if not values:
            return self._dead_end()

        # (4) only NOW does anything move, and only these two things.
        invite._register_view()
        request.env['care.channel.audit']._log(
            'golive_invite_viewed',
            detail='%s/%s invite %s' % (invite.provider, invite.step_key,
                                        invite.id))
        return self._respond(
            request.env['ir.qweb'].with_context(lang=lang)._render(
                'health_care_command_channels.golive_invite_page', values))
