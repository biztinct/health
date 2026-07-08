import logging

from odoo import http, _
from odoo.http import request

_logger = logging.getLogger(__name__)


class SelfBookingPublicController(http.Controller):
    """A5 — public, mobile client rebook page (no website dependency).

    Clones health_workflow_auto/controllers/offer_public.py conventions:
    auth='public', sudo confined to the route, gateway.rate.counter reuse.
    GET renders the slot list; the state-changing accept is POST-only (a
    booking side effect must never ride a GET — chat-app link previews and
    mail scanners follow GET links). Invalid / expired / revoked / over-limit
    all render the SAME neutral page (no existence oracle).
    """

    def _rate_limited(self):
        ip = request.httprequest.remote_addr or 'unknown'
        try:
            allowed, _retry = request.env['gateway.rate.counter'].sudo().hit(
                'selfbook:%s' % ip)
            return not allowed
        except Exception as exc:  # noqa: BLE001 — never fail the page on counter error
            _logger.warning('Self-booking rate counter error: %s', exc)
            return False

    def _neutral(self):
        return request.render('health_self_booking.selfbook_neutral', {})

    def _get_invite(self, token):
        return request.env['health.selfbook.invite'].sudo().search(
            [('token', '=', token)], limit=1)

    def _render_state(self, invite, notice=None):
        ctx = invite._page_context()
        if notice:
            ctx['notice'] = notice
        return request.render('health_self_booking.selfbook_page', ctx)

    @http.route('/booking/self/<string:token>', type='http', auth='public',
                website=False, methods=['GET'], csrf=False)
    def selfbook_page(self, token, **kwargs):
        if self._rate_limited():
            return self._neutral()
        invite = self._get_invite(token)
        # Invalid / revoked / expired -> identical neutral page. A booked
        # invite keeps rendering its summary until expiry.
        if not invite or invite.state == 'revoked' or invite._is_expired():
            return self._neutral()
        return self._render_state(invite)

    # POST-only: a booking side effect must never ride a GET.
    @http.route('/booking/self/<string:token>/accept/<int:slot_index>',
                type='http', auth='public', website=False,
                methods=['POST'], csrf=False)
    def selfbook_accept(self, token, slot_index, **kwargs):
        if self._rate_limited():
            return self._neutral()
        invite = self._get_invite(token)
        if not invite or invite.state == 'revoked' or invite._is_expired():
            return self._neutral()

        result = invite.accept_slot(slot_index)
        if result.get('ok') or result.get('reason') == 'already_booked':
            # Double-POST: second request sees state='booked' under the lock
            # and re-renders the booked page (idempotent, no second FSO).
            return self._render_state(invite)
        reason = result.get('reason')
        if reason in ('expired', 'invalid_slot'):
            return self._neutral()
        # infeasible / create_failed -> a stale slot; re-render with a notice
        # (the snapshot still shows the other slots).
        return self._render_state(invite, notice=_(
            'Khung giờ này không còn trống — vui lòng chọn giờ khác. '
            '(That time is no longer available — please pick another.)'))
