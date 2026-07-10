# -*- coding: utf-8 -*-
"""Public family-messaging routes — extend the token page (no login).

We inherit the family_link public controller so the GET route stays on the
same endpoint (overriding the method keeps its route binding) and augment the
render context with the message section. We add a POST-only route for sending
a message (state changes never on GET). Token + state + expiry + consent are
re-checked inside the POST, with the same neutral-page refusal.
"""
import logging

from odoo import http
from odoo.exceptions import ValidationError
from odoo.http import request

from odoo.addons.health_family_link.controllers.family_public import (
    FamilyPublicController,
)

_logger = logging.getLogger(__name__)


class FamilyMessagesPublicController(FamilyPublicController):

    # --- helpers ---------------------------------------------------------
    def _msg_rate_limited(self, token):
        """Coarse per-token AND per-IP throttle via the gateway counter
        (per-minute fixed window). The precise 10/hour cap is enforced on the
        thread itself (rolling message count)."""
        ip = request.httprequest.remote_addr or 'unknown'
        try:
            counter = request.env['gateway.rate.counter'].sudo()
            allowed_ip, _r1 = counter.hit('fammsg-ip:%s' % ip)
            allowed_tok, _r2 = counter.hit('fammsg:%s' % token)
            return not (allowed_ip and allowed_tok)
        except Exception as exc:  # noqa: BLE001 — never fail on counter error
            _logger.warning('Family message rate counter error: %s', exc)
            return False

    def _resolve_link(self, token):
        """Return a live link for the token or None (invalid/expired/revoked)."""
        link = request.env['health.family.link'].sudo().search(
            [('token', '=', token)], limit=1)
        if not link or link.state == 'revoked' or link._is_expired():
            return None
        ctx = link._page_context()
        if ctx.get('mode') == 'neutral':
            return None
        return link

    # --- GET (override — augments the page with the message section) ------
    def family_page(self, token, **kwargs):
        if self._rate_limited():
            return self._neutral()
        link = request.env['health.family.link'].sudo().search(
            [('token', '=', token)], limit=1)
        if not link or link.state == 'revoked' or link._is_expired():
            return self._neutral()
        ctx = link._page_context()
        if ctx.get('mode') == 'neutral':
            return self._neutral()
        ctx.update(link.sudo()._messaging_context())
        return request.render('health_family_link.family_page', ctx)

    # --- POST (send a message) -------------------------------------------
    @http.route('/family/visit/<string:token>/message', type='http',
                auth='public', website=False, methods=['POST'], csrf=False)
    def family_post_message(self, token, **kwargs):
        if self._msg_rate_limited(token):
            return self._neutral()
        link = self._resolve_link(token)
        if not link:
            return self._neutral()
        link = link.sudo()
        # Re-check the messaging gate (master switch + eligibility + consent).
        if not link._messaging_enabled():
            return self._neutral()
        body = (kwargs.get('body') or '').strip()
        if body:
            thread = request.env['health.family.thread'].sudo()._get_or_create(
                link.fso_id.patient_id, link.relation_id)
            try:
                thread.post_family_message(
                    body, fso=link.fso_id,
                    author_label=link.relation_id.display_name)
            except ValidationError:
                # Over-length / invalid — refuse politely; PRG back to the page.
                pass
        # Redirect back to the GET page so a refresh shows the thread (PRG).
        return request.redirect('/family/visit/%s' % token)
