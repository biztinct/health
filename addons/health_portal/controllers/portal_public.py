# -*- coding: utf-8 -*-
"""Public "My Care" patient portal controller.

Clones health_family_link/controllers/family_public.py: auth='public', GET,
gateway.rate.counter throttle, identical NEUTRAL page for invalid / revoked /
expired / unknown tokens (no existence oracle, no PHI). This page is per-patient
(the whole record), so the throttle is dual (per-IP AND per-token).
"""
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class MyCarePortalController(http.Controller):

    def _rate_limited(self, token):
        ip = request.httprequest.remote_addr or 'unknown'
        try:
            counter = request.env['gateway.rate.counter'].sudo()
            ip_allowed, _r1 = counter.hit('portal_ip:%s' % ip)
            tok_allowed, _r2 = counter.hit('portal_tok:%s' % (token or '')[:64])
            return not (ip_allowed and tok_allowed)
        except Exception as exc:  # never fail the page on a counter error
            _logger.warning('Portal rate counter error: %s', exc)
            return False

    def _neutral(self):
        return request.render('health_portal.portal_neutral', {})

    def _resolve(self, token):
        access = request.env['health.portal.access'].sudo().search(
            [('token', '=', token)], limit=1)
        if not access or access.state != 'active' or access._is_expired():
            return None
        return access

    @http.route('/my/care/<string:token>', type='http', auth='public',
                website=False, methods=['GET'], csrf=False)
    def portal_hub(self, token, **kwargs):
        if self._rate_limited(token):
            return self._neutral()
        access = self._resolve(token)
        if not access:
            return self._neutral()
        access._record_access('hub', request.httprequest.remote_addr)
        return request.render('health_portal.portal_hub', access._hub_context())
