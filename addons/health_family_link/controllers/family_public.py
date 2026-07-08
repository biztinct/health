import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class FamilyPublicController(http.Controller):
    """A5 — public, mobile, READ-ONLY family visit page (no website dep).

    Clones health_workflow_auto/controllers/offer_public.py conventions:
    auth='public', sudo confined to the route, gateway.rate.counter reuse.
    GET only — the page is read-only; there is no state-changing route, so the
    POST-only rule that bit the offer page does not arise here. Invalid,
    expired, revoked, cancelled and consent-withdrawn all render the SAME
    neutral page (no existence oracle, no stale PHI).
    """

    def _rate_limited(self):
        ip = request.httprequest.remote_addr or 'unknown'
        try:
            allowed, _retry = request.env['gateway.rate.counter'].sudo().hit(
                'family:%s' % ip)
            return not allowed
        except Exception as exc:  # noqa: BLE001 — never fail the page on counter error
            _logger.warning('Family link rate counter error: %s', exc)
            return False

    def _neutral(self):
        return request.render('health_family_link.family_neutral', {})

    @http.route('/family/visit/<string:token>', type='http', auth='public',
                website=False, methods=['GET'], csrf=False)
    def family_page(self, token, **kwargs):
        if self._rate_limited():
            return self._neutral()
        link = request.env['health.family.link'].sudo().search(
            [('token', '=', token)], limit=1)
        # Invalid / revoked / expired -> identical neutral page.
        if not link or link.state == 'revoked' or link._is_expired():
            return self._neutral()
        ctx = link._page_context()
        if ctx.get('mode') == 'neutral':
            return self._neutral()
        return request.render('health_family_link.family_page', ctx)
