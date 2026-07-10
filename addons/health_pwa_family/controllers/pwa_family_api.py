# -*- coding: utf-8 -*-
"""Nurse-facing PWA family-messaging endpoints (visit context).

All three routes are `auth='user'` and run sudo ONLY AFTER an explicit
employee-scope check: the caller must be a staff member assigned to THIS order
(any state but cancelled). Nurses have no ACL on the thread/message models by
design (backend inbox stays ops-only), so the scope check is the security
boundary. Everything goes dark when `health_family_messages.enabled` is off.
No PHI in logs (ids only); family bodies are rendered client-side via
textContent.
"""
import json
import logging

from odoo import http, fields, _
from odoo.exceptions import UserError, ValidationError
from odoo.http import request

_logger = logging.getLogger(__name__)


class PwaFamilyController(http.Controller):

    # ------------------------------------------------------------------
    # Helpers duplicated verbatim from health_pwa/controllers/api.py
    # (conventions §4: duplicate, don't cross-import controllers).
    # ------------------------------------------------------------------
    def _check_api_access(self):
        if not request.env.user or request.env.user.id == \
                request.env.ref('base.public_user').id:
            return False
        try:
            request.env['res.partner'].check_access_rights('read')
            return True
        except Exception:  # noqa: BLE001 — access probe, deny on any failure
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
            ],
            status=status_code)

    # ------------------------------------------------------------------
    # Scope + gate helpers
    # ------------------------------------------------------------------
    def _messaging_enabled(self):
        return request.env['ir.config_parameter'].sudo().get_param(
            'health_family_messages.enabled', 'False') in ('True', 'true', '1')

    def _scoped_order(self, order_id):
        """Return the order IFF the caller's employee is assigned to it (any
        assignment state but cancelled), else None. Resolve the employee by
        user_id search (the api.py:2075 precedent — user.employee_id is
        company-context dependent), then sudo the assignment read (§5.24)."""
        employee = request.env['hr.employee'].sudo().search(
            [('user_id', '=', request.env.user.id)], limit=1)
        if not employee:
            return None
        order = request.env['health.fieldservice.order'].sudo().browse(order_id)
        if not order.exists():
            return None
        assigned = request.env['health.staff.assignment'].sudo().search_count([
            ('fso_id', '=', order.id),
            ('staff_id', '=', employee.id),
            ('state', '!=', 'cancelled'),
        ])
        return order if assigned else None

    def _thread_dict(self, thread):
        msgs = thread.message_ids.sorted('create_date')
        rows = []
        for m in msgs:
            when = ''
            if m.create_date:
                when = fields.Datetime.context_timestamp(
                    thread, m.create_date).strftime('%d/%m %H:%M')
            rows.append({
                'direction': m.direction,
                'body': m.body or '',
                'author': m.author_label or '',
                'when': when,
            })
        return {
            'thread_id': thread.id,
            'relation': thread.relation_id.display_name or '',
            'messages': rows,
        }

    def _json_body(self):
        try:
            return json.loads(request.httprequest.data or b'{}')
        except (ValueError, TypeError):
            return {}

    # ------------------------------------------------------------------
    # GET — the visit's family threads
    # ------------------------------------------------------------------
    @http.route('/health_pwa/api/fso/<int:order_id>/family_messages',
                type='http', auth='user', methods=['GET'], csrf=False)
    def api_family_messages(self, order_id, **kwargs):
        if not self._check_api_access():
            return self._prepare_json_response(
                error=_('Access denied'), status_code=403)
        try:
            order = self._scoped_order(order_id)
            if not order or not self._messaging_enabled():
                # Not assigned / master switch off ⇒ the JS renders nothing.
                return self._prepare_json_response(
                    data={'enabled': False, 'threads': []})
            patient = order.patient_id
            threads = request.env['health.family.thread'].sudo().search(
                [('patient_id', '=', patient.id)])
            eligible = request.env['health.family.link'].sudo(
            )._eligible_relations(order)
            enabled = bool(threads or eligible)
            return self._prepare_json_response(data={
                'enabled': enabled,
                'can_update': bool(eligible),
                # The order-detail screen is offline-first (ledger §31) — the
                # panel JS gets the order context from HERE, not the FSO GET.
                'order_id': order.id,
                'order_state': order.state or '',
                'threads': [self._thread_dict(t) for t in threads],
            })
        except Exception as exc:  # noqa: BLE001
            _logger.exception('Family messages GET failed for order %s: %s',
                              order_id, exc)
            return self._prepare_json_response(
                error=_('Internal error'), status_code=500)

    # ------------------------------------------------------------------
    # POST — nurse reply to one thread
    # ------------------------------------------------------------------
    @http.route('/health_pwa/api/fso/<int:order_id>/family_messages/reply',
                type='http', auth='user', methods=['POST'], csrf=False)
    def api_family_reply(self, order_id, **kwargs):
        if not self._check_api_access():
            return self._prepare_json_response(
                error=_('Access denied'), status_code=403)
        try:
            order = self._scoped_order(order_id)
            if not order:
                return self._prepare_json_response(
                    error=_('Not assigned to this visit'), status_code=403)
            if not self._messaging_enabled():
                return self._prepare_json_response(
                    error=_('Messaging is disabled'), status_code=403)
            data = self._json_body()
            try:
                thread_id = int(data.get('thread_id') or kwargs.get('thread_id'))
            except (TypeError, ValueError):
                return self._prepare_json_response(
                    error=_('Invalid thread'), status_code=400)
            body = data.get('body') or kwargs.get('body') or ''
            thread = request.env['health.family.thread'].sudo().browse(thread_id)
            # Spoof guard: the thread must belong to THIS visit's patient.
            if not thread.exists() or \
                    thread.patient_id.id != order.patient_id.id:
                return self._prepare_json_response(
                    error=_('Thread not found for this visit'), status_code=403)
            try:
                thread._post_team_reply(body, request.env.user, fso=order)
            except (UserError, ValidationError) as exc:
                return self._prepare_json_response(
                    error=str(exc), status_code=400)
            return self._prepare_json_response(data={
                'thread_id': thread.id,
                'message': self._thread_dict(thread)['messages'][-1],
            })
        except Exception as exc:  # noqa: BLE001
            _logger.exception('Family reply POST failed for order %s: %s',
                              order_id, exc)
            return self._prepare_json_response(
                error=_('Internal error'), status_code=500)

    # ------------------------------------------------------------------
    # POST — FB-047 one-tap post-visit family update (fan-out)
    # ------------------------------------------------------------------
    @http.route('/health_pwa/api/fso/<int:order_id>/family_messages/update',
                type='http', auth='user', methods=['POST'], csrf=False)
    def api_family_update(self, order_id, **kwargs):
        if not self._check_api_access():
            return self._prepare_json_response(
                error=_('Access denied'), status_code=403)
        try:
            order = self._scoped_order(order_id)
            if not order:
                return self._prepare_json_response(
                    error=_('Not assigned to this visit'), status_code=403)
            if not self._messaging_enabled():
                return self._prepare_json_response(
                    error=_('Messaging is disabled'), status_code=403)
            data = self._json_body()
            body = data.get('body') or kwargs.get('body') or ''
            Message = request.env['health.family.message'].sudo()
            # Validate the body ONCE up front so an over-cap update is refused
            # before any fan-out row is created.
            try:
                text = Message._sanitize_body(body)
            except (UserError, ValidationError) as exc:
                return self._prepare_json_response(
                    error=str(exc), status_code=400)
            if not text:
                return self._prepare_json_response(
                    error=_('Please write an update first.'), status_code=400)
            relations = request.env['health.family.link'].sudo(
            )._eligible_relations(order)
            if not relations:
                return self._prepare_json_response(data={
                    'sent': 0,
                    'message': _('No eligible family recipients for this '
                                 'patient.'),
                })
            Thread = request.env['health.family.thread'].sudo()
            sent = 0
            for relation in relations:
                thread = Thread._get_or_create(order.patient_id, relation)
                if thread.state != 'active':
                    # Ops closed this channel — skip it, don't abort the fan-out.
                    continue
                # mark_read=False: a one-tap update is NOT the nurse reading the
                # thread — it must not drain the ops inbox unread state or the
                # other nurses' bell rows.
                message = thread._post_team_reply(
                    text, request.env.user, fso=order,
                    send_zns=False, mark_read=False)
                thread._send_update_zns(message, relation, order)
                sent += 1
            return self._prepare_json_response(data={
                'sent': sent,
                'message': _('Update sent to %s family recipient(s).') % sent,
            })
        except Exception as exc:  # noqa: BLE001
            _logger.exception('Family update POST failed for order %s: %s',
                              order_id, exc)
            return self._prepare_json_response(
                error=_('Internal error'), status_code=500)
