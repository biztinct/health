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

    def _guard(self, token):
        """(access, None) on success; (None, neutral_response) otherwise."""
        if self._rate_limited(token):
            return None, self._neutral()
        access = self._resolve(token)
        if not access:
            return None, self._neutral()
        return access, None

    @http.route('/my/care/<string:token>', type='http', auth='public',
                website=False, methods=['GET'], csrf=False)
    def portal_hub(self, token, **kwargs):
        access, resp = self._guard(token)
        if resp:
            return resp
        access._record_access('hub', request.httprequest.remote_addr)
        return request.render('health_portal.portal_hub', access._hub_context())

    @http.route('/my/care/<string:token>/records', type='http', auth='public',
                website=False, methods=['GET'], csrf=False)
    def portal_records(self, token, **kwargs):
        access, resp = self._guard(token)
        if resp:
            return resp
        access._record_access('records', request.httprequest.remote_addr)
        return request.render('health_portal.portal_records',
                              access._records_ctx())

    @http.route('/my/care/<string:token>/records/<int:note_id>', type='http',
                auth='public', website=False, methods=['GET'], csrf=False)
    def portal_record(self, token, note_id, **kwargs):
        access, resp = self._guard(token)
        if resp:
            return resp
        note = access._note_or_false(note_id)
        if not note:
            return self._neutral()
        access._record_access('record:%s' % note_id,
                              request.httprequest.remote_addr)
        return request.render('health_portal.portal_record',
                              access._note_ctx(note))

    @http.route('/my/care/<string:token>/records/<int:note_id>/download',
                type='http', auth='public', website=False, methods=['GET'],
                csrf=False)
    def portal_record_download(self, token, note_id, **kwargs):
        access, resp = self._guard(token)
        if resp:
            return resp
        note = access._note_or_false(note_id)
        if not note:
            return self._neutral()
        access._record_access('download:%s' % note_id,
                              request.httprequest.remote_addr)
        text = access._note_text(note)
        return request.make_response(text, headers=[
            ('Content-Type', 'text/plain; charset=utf-8'),
            ('Content-Disposition',
             'attachment; filename="ho-so-benh-an-%s.txt"' % note_id),
        ])

    # -- My Consents (4C) ----------------------------------------------------
    @http.route('/my/care/<string:token>/consents', type='http', auth='public',
                website=False, methods=['GET'], csrf=False)
    def portal_consents(self, token, **kwargs):
        access, resp = self._guard(token)
        if resp:
            return resp
        access._record_access('consents', request.httprequest.remote_addr)
        return request.render('health_portal.portal_consents',
                              access._consents_ctx())

    @http.route('/my/care/<string:token>/consents/<string:ctype>/withdraw',
                type='http', auth='public', website=False, methods=['POST'],
                csrf=False)
    def portal_consent_withdraw(self, token, ctype, **kwargs):
        access, resp = self._guard(token)
        if resp:
            return resp
        access._portal_withdraw(ctype)
        access._record_access('withdraw:%s' % ctype,
                              request.httprequest.remote_addr)
        return request.redirect('/my/care/%s/consents' % token)

    @http.route('/my/care/<string:token>/consents/<string:ctype>/grant',
                type='http', auth='public', website=False,
                methods=['GET', 'POST'], csrf=False)
    def portal_consent_grant(self, token, ctype, **kwargs):
        access, resp = self._guard(token)
        if resp:
            return resp
        label = access._consent_label(ctype)
        if not label:
            return self._neutral()  # not a patient-managed type
        if request.httprequest.method == 'POST':
            sig = kwargs.get('signature') or ''
            b64 = sig.split(',', 1)[1] if ',' in sig else sig
            if access._portal_grant(ctype, b64.strip()):
                access._record_access('grant:%s' % ctype,
                                      request.httprequest.remote_addr)
                return request.redirect('/my/care/%s/consents' % token)
            # Missing/blank signature — re-render with an error.
            return request.render('health_portal.portal_consent_grant', {
                'token': token, 'ctype': ctype, 'label': label, 'error': True})
        return request.render('health_portal.portal_consent_grant', {
            'token': token, 'ctype': ctype, 'label': label, 'error': False})
