import logging

from odoo import http, fields, _
from odoo.http import request

_logger = logging.getLogger(__name__)


class OfferPublicController(http.Controller):
    """E.5 — public, mobile first-visit offer pages (no website dependency)."""

    def _rate_limited(self):
        """10 req/min/IP guard via the shipped gateway rate counter (A5).

        Reuses gateway.rate.counter.hit() (atomic ON CONFLICT upsert). See the
        report deviation note: the effective per-minute ceiling is the gateway's
        global config, not a per-call 10 — the counter has no per-call limit arg.
        """
        ip = request.httprequest.remote_addr or 'unknown'
        try:
            allowed, _retry = request.env['gateway.rate.counter'].sudo().hit(
                'offer:%s' % ip)
            return not allowed
        except Exception as exc:  # noqa: BLE001 — never fail the page on counter error
            _logger.warning('Offer rate counter error: %s', exc)
            return False

    def _neutral_expired(self):
        """Same neutral page for invalid / expired / over-limit (no oracle)."""
        return request.render('health_workflow_auto.offer_expired', {})

    def _get_offer(self, token):
        return request.env['health.visit.offer'].sudo().search(
            [('token', '=', token)], limit=1)

    @http.route('/booking/offer/<string:token>', type='http', auth='public',
                website=False, methods=['GET'], csrf=False)
    def offer_page(self, token, **kwargs):
        if self._rate_limited():
            return self._neutral_expired()
        offer = self._get_offer(token)
        if not offer or offer.state != 'sent' or (
                offer.expires_at and offer.expires_at < fields.Datetime.now()):
            return self._neutral_expired()
        return request.render('health_workflow_auto.offer_page', {
            'offer': offer,
            'slots': offer.slot_ids.sorted('index'),
        })

    @http.route('/booking/offer/<string:token>/accept/<int:slot_index>',
                type='http', auth='public', website=False,
                methods=['GET', 'POST'], csrf=False)
    def offer_accept(self, token, slot_index, **kwargs):
        if self._rate_limited():
            return self._neutral_expired()
        offer = self._get_offer(token)
        if not offer:
            return self._neutral_expired()

        result = offer.accept_slot(slot_index)
        if result.get('ok'):
            fso = result['fso']
            slot = result['slot']
            return request.render('health_workflow_auto.offer_confirmed', {
                'offer': offer,
                'fso': fso,
                'slot': slot,
                'staff_first_name': (slot.staff_id.name or '').split(' ')[-1]
                if slot.staff_id else '',
            })
        reason = result.get('reason')
        if reason in ('expired', 'invalid_slot', 'already_accepted'):
            return self._neutral_expired()
        # infeasible / create_failed -> re-offer the remaining slots.
        return request.render('health_workflow_auto.offer_page', {
            'offer': offer,
            'slots': offer.slot_ids.sorted('index'),
            'notice': _('That time is no longer available — please pick another.'),
        })
