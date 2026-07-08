import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class TelePublicController(http.Controller):
    """Public, mobile, READ-ONLY telehealth waiting-room page (no website dep).

    Clones health_family_link/controllers/family_public.py conventions:
    auth='public', sudo confined to the route, gateway.rate.counter reuse,
    GET only. Invalid, expired, cancelled all render the SAME neutral page
    (no existence oracle). The room URL is served ONLY in the live ('open')
    state — that URL-gating is the page's whole security story.
    """

    def _rate_limited(self):
        ip = request.httprequest.remote_addr or 'unknown'
        try:
            allowed, _retry = request.env['gateway.rate.counter'].sudo().hit(
                'tele:%s' % ip)
            return not allowed
        except Exception as exc:  # noqa: BLE001 — never fail the page on counter error
            _logger.warning('Telehealth rate counter error: %s', exc)
            return False

    def _neutral(self):
        return request.render('health_telehealth.tele_neutral', {})

    @http.route('/tele/visit/<string:token>', type='http', auth='public',
                website=False, methods=['GET'], csrf=False)
    def tele_page(self, token, **kwargs):
        if self._rate_limited():
            return self._neutral()
        session = request.env['health.telehealth.session'].sudo().search(
            [('patient_token', '=', token)], limit=1)
        # Invalid / cancelled / expired -> identical neutral page.
        if not session or session.state == 'cancelled' or session._is_expired():
            return self._neutral()
        ctx = session._page_context()
        if ctx.get('mode') == 'neutral':
            return self._neutral()
        return request.render('health_telehealth.tele_page', ctx)
