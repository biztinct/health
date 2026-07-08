import json
import logging

from odoo import http, fields
from odoo.http import request

_logger = logging.getLogger(__name__)


class TeleApiController(http.Controller):
    """PWA endpoint that hands the room URL to an assigned staff member.

    Kept in this module so health_pwa is never edited (conventions §4). The
    _check_api_access / _prepare_json_response helpers are DUPLICATED from
    health_pwa/controllers/api.py:29-63 per the duplication convention
    (health_workflow_auto/controllers/onetap_api.py precedent). The actual
    access decision lives in FSO._tele_join_url (assigned-staff-or-manager +
    joinable-state gate) so the PWA and the backend button share one rule.
    The room URL is never placed in any cached/offline payload.
    """

    # -- helpers duplicated from health_pwa/controllers/api.py:29-63 ----------
    def _check_api_access(self):
        if not request.env.user or request.env.user.id == request.env.ref(
                'base.public_user').id:
            return False
        try:
            request.env['res.partner'].check_access_rights('read')
            return True
        except Exception:
            return False

    def _prepare_json_response(self, data=None, error=None, status_code=200):
        response_data = {
            'success': error is None,
            'timestamp': fields.Datetime.now().isoformat(),
        }
        if error:
            response_data['error'] = error
        else:
            response_data['data'] = data
        return request.make_response(
            json.dumps(response_data, default=str, ensure_ascii=False, indent=2),
            headers=[
                ('Content-Type', 'application/json; charset=utf-8'),
                ('Cache-Control', 'no-cache, no-store, must-revalidate'),
                ('Access-Control-Allow-Origin', '*'),
                ('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS'),
                ('Access-Control-Allow-Headers',
                 'Content-Type, Authorization, X-Requested-With'),
            ],
            status=status_code,
        )

    @http.route('/health_pwa/api/fso/<int:order_id>/tele/join',
                type='http', auth='user', methods=['GET'], csrf=False)
    def tele_join(self, order_id, **kwargs):
        if not self._check_api_access():
            return self._prepare_json_response(
                error='Access denied', status_code=403)
        order = request.env['health.fieldservice.order'].browse(order_id)
        # Existence is checked with sudo so an assigned nurse who lacks a
        # catchment (and thus fails the FSO read rule, ledger §5 #4) is not
        # spuriously 404'd; _tele_join_url makes the real access decision.
        if not order.sudo().exists():
            return self._prepare_json_response(
                error='Order not found', status_code=404)
        # Empty url => not joinable / not assigned; the PWA shows a soft notice.
        url = order._tele_join_url()
        return self._prepare_json_response(data={'url': url})
