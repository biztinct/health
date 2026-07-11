import json
import logging

from odoo import http, fields, _
from odoo.http import request

_logger = logging.getLogger(__name__)


class OneTapController(http.Controller):
    """E.2 — PWA one-tap completion endpoints.

    Kept in this module so health_pwa is never edited (conventions §4). The
    _check_api_access / _prepare_json_response helpers and the invoice/payment
    tail are DUPLICATED from health_pwa/controllers/api.py per the handover
    ruling A4 (duplication convention), with source lines named inline.
    """

    # -- helpers duplicated from health_pwa/controllers/api.py:29-63 ----------
    def _check_api_access(self):
        """Check if user has API access to health modules."""
        if not request.env.user or request.env.user.id == request.env.ref('base.public_user').id:
            return False
        try:
            request.env['res.partner'].check_access_rights('read')
            return True
        except Exception:
            return False

    def _prepare_json_response(self, data=None, error=None, status_code=200):
        """Standardized JSON response (envelope identical to health_pwa)."""
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
                ('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Requested-With'),
            ],
            status=status_code,
        )

    # -- scope helper ---------------------------------------------------------
    def _employee_assigned_to(self, order):
        """Return the caller's employee IFF assigned to THIS order (any state
        but cancelled), else None. Mirrors the health_pwa_family `_scoped_order`
        / api_fso_detail (§2.3) pattern: resolve the employee via sudo user_id
        search (§5.24 — user.employee_id is company-context dependent and reads
        trip the public-profile guard), then sudo the assignment read.

        This is a WRITE money path (confirms the SO, posts an invoice, may
        create a payment transaction), so there is NO ACL fallback: assignment
        is REQUIRED. Before this, both routes ran only `_check_api_access`
        (partner-read) then browsed with the caller's ACL, so ANY internal user
        could one-tap-complete ANY order — the hole this closes."""
        employee = request.env['hr.employee'].sudo().search(
            [('user_id', '=', request.env.user.id)], limit=1)
        if not employee:
            return None
        assigned = request.env['health.staff.assignment'].sudo().search_count([
            ('fso_id', '=', order.id),
            ('staff_id', '=', employee.id),
            ('state', '!=', 'cancelled'),
        ])
        return employee if assigned else None

    # -- GET eligibility ------------------------------------------------------
    @http.route('/health_pwa/api/fso/<int:order_id>/onetap_eligible',
                type='http', auth='user', methods=['GET'], csrf=False)
    def onetap_eligible(self, order_id, **kwargs):
        if not self._check_api_access():
            return self._prepare_json_response(error='Access denied', status_code=403)
        # Scope + sudo (§2.5): read sudo AFTER an explicit assignment check so a
        # minimal nurse gets their own visit and non-assignees are refused.
        order = request.env['health.fieldservice.order'].sudo().browse(order_id)
        if not order.exists():
            return self._prepare_json_response(error='Order not found', status_code=404)
        if not self._employee_assigned_to(order):
            return self._prepare_json_response(error='Access denied', status_code=403)
        elig = order.onetap_eligibility()
        return self._prepare_json_response(data={
            'eligible': elig['eligible'],
            'reason': elig['reason'],
        })

    # -- POST one-tap complete ------------------------------------------------
    @http.route('/health_pwa/api/fso/<int:order_id>/complete_onetap',
                type='http', auth='user', methods=['POST'], csrf=False)
    def complete_onetap(self, order_id, **kwargs):
        if not self._check_api_access():
            return self._prepare_json_response(error='Access denied', status_code=403)
        try:
            body = json.loads(request.httprequest.data or b'{}')
        except (ValueError, TypeError):
            body = {}
        service_notes = body.get('service_notes', '')
        payment_choice = body.get('payment_choice', 'pay_later')
        payment_method = body.get('payment_method')

        # Scope + sudo (§2.5): assignment required, then the completion +
        # invoice/payment tail all run on the sudo order so a minimal nurse
        # (no sale/account rights) can actually complete their own visit.
        order = request.env['health.fieldservice.order'].sudo().browse(order_id)
        if not order.exists():
            return self._prepare_json_response(error='Order not found', status_code=404)
        employee = self._employee_assigned_to(order)
        if not employee:
            return self._prepare_json_response(error='Access denied', status_code=403)

        elig = order.onetap_eligibility()
        if not elig['eligible']:
            if elig['reason'] == 'needs_review':
                # Quote changed since confirmation — PWA routes to quote screen.
                return self._prepare_json_response(data={
                    'completed': False,
                    'needs_review': True,
                    'changed': elig['changed'],
                })
            return self._prepare_json_response(data={
                'completed': False,
                'needs_review': False,
                'reason': elig['reason'],
            })

        # Complete the visit (auto-verify quote + placeholder note + complete).
        order.action_one_tap_complete(service_notes=service_notes)

        # ---- invoice / payment tail --------------------------------------
        # DUPLICATED from health_pwa/controllers/api.py:823-885 (handover A4).
        # For one-tap we always attempt invoicing per the existing rules.
        create_invoice_now = True
        message = _('Service completed')
        should_create_invoice = create_invoice_now and order.sale_order_id
        if should_create_invoice:
            sale_order_total = order.sale_order_id.amount_total or 0.0
            if sale_order_total <= 0.0:
                should_create_invoice = False
                message = _('Service completed - No invoice created (zero amount)')

        if should_create_invoice:
            if order.sale_order_id.state in ['draft', 'sent']:
                order.sale_order_id.action_confirm()
            if not order.invoice_id:
                invoices = order.sale_order_id._create_invoices()
                if invoices:
                    order.invoice_id = invoices[0] if len(invoices) == 1 else invoices
                    order.invoice_id.action_post()

        if payment_choice == 'pay_now' and payment_method and order.invoice_id:
            try:
                transaction_vals = {
                    'patient_id': order.patient_id.id if order.patient_id else False,
                    'fso_id': order.id,
                    'invoice_id': order.invoice_id.id if order.invoice_id else False,
                    'amount': order.invoice_id.amount_total if order.invoice_id else 0.0,
                    'payment_method': payment_method,
                    'transaction_type': 'immediate',
                    'status': 'collected' if payment_method != 'cash' else 'pending_delivery',
                    'collected_by_id': employee.id,
                    'transaction_notes': service_notes or (
                        'Payment collected on one-tap completion - %s' % payment_method),
                }
                if 'health.payment.transaction' in request.env:
                    request.env['health.payment.transaction'].sudo().create(transaction_vals)
                    message = _('Service completed - %s payment collected') % payment_method.replace("_", " ").title()
                else:
                    message = _('Service completed - %s payment noted') % payment_method.replace("_", " ").title()
            except Exception as e:  # noqa: BLE001
                _logger.warning('Could not create payment transaction: %s', e)
                message = _('Service completed - %s payment noted') % payment_method.replace("_", " ").title()
        elif payment_choice == 'pay_later' and order.invoice_id:
            message = _('Service completed - Invoice will be sent for later payment')
        elif not order.invoice_id:
            if 'zero amount' not in message:
                message = _('Service completed - No payment required')
        # ---- end duplicated tail -----------------------------------------

        return self._prepare_json_response(data={
            'completed': True,
            'state': order.state,
            'verified_quote': True,
            'message': message,
        })
