# -*- coding: utf-8 -*-
"""Care Plan PWA endpoints (clinical spec §1.7).

Matches health_pwa conventions exactly: type='http', auth='user',
csrf=False, manual json.loads(request.httprequest.data), and the same
response envelope {success, timestamp, data|error}. The envelope/auth
helpers are deliberately DUPLICATED from health_pwa/controllers/api.py
(existing convention — api.py and sync.py both do it).
"""
import json
import logging

from odoo import _, fields, http
from odoo.exceptions import UserError, ValidationError
from odoo.http import request

_logger = logging.getLogger(__name__)


class HealthCareplanPWAController(http.Controller):
    """Care plan endpoints under the PWA API namespace."""

    # ------------------------------------------------------------------
    # Helpers copied from health_pwa (envelope/auth conventions)
    # ------------------------------------------------------------------
    def _check_api_access(self):
        """Check if user has API access to health modules."""
        if (not request.env.user
                or request.env.user.id == request.env.ref('base.public_user').id):
            return False
        try:
            request.env['res.partner'].check_access_rights('read')
            return True
        except Exception:
            return False

    def _prepare_json_response(self, data=None, error=None, status_code=200):
        """Prepare standardized JSON response."""
        response_data = {
            'success': error is None,
            'timestamp': fields.Datetime.now().isoformat(),
        }
        if error:
            response_data['error'] = error
        else:
            response_data['data'] = data
        return request.make_response(
            json.dumps(response_data, default=str, ensure_ascii=False,
                       indent=2),
            headers=[
                ('Content-Type', 'application/json; charset=utf-8'),
                ('Cache-Control', 'no-cache, no-store, must-revalidate'),
                ('Access-Control-Allow-Origin', '*'),
                ('Access-Control-Allow-Methods',
                 'GET, POST, PUT, DELETE, OPTIONS'),
                ('Access-Control-Allow-Headers',
                 'Content-Type, Authorization, X-Requested-With'),
            ],
            status=status_code,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _read_json_body(self):
        try:
            return json.loads(request.httprequest.data.decode('utf-8')) \
                if request.httprequest.data else {}
        except (ValueError, TypeError):
            return None

    def _serialize_task(self, task):
        return {
            'id': task.id,
            'name': task.name,
            'instructions': task.instructions or '',
            'state': task.state,
            'sequence': task.sequence,
            'is_prn': task.is_prn,
            'not_done_reason': task.not_done_reason_id.code or None,
            'not_done_note': task.not_done_note or '',
            'completed_by': task.completed_by_id.name or '',
            'completed_at': (
                task.completed_datetime.strftime('%Y-%m-%dT%H:%M:%SZ')
                if task.completed_datetime else None),
            'activity_id': task.activity_id.id,
            'careplan_id': task.careplan_id.id,
            'goal_names': task.activity_id.goal_ids.mapped('name'),
        }

    # ------------------------------------------------------------------
    # GET /health_pwa/api/fso/<id>/careplan_tasks
    # ------------------------------------------------------------------
    @http.route('/health_pwa/api/fso/<int:order_id>/careplan_tasks',
                type='http', auth='user', methods=['GET'], csrf=False)
    def fso_careplan_tasks(self, order_id, **kwargs):
        if not self._check_api_access():
            return self._prepare_json_response(
                error=_('Access denied'), status_code=403)
        try:
            order = request.env['health.fieldservice.order'].browse(order_id)
            if not order.exists():
                return self._prepare_json_response(
                    error=_('Order not found'), status_code=404)
            tasks = order.careplan_task_ids.sorted(
                key=lambda task: (task.sequence, task.id))
            plan = request.env['health.careplan'].search([
                ('client_id', '=', order.patient_id.id),
                ('state', 'in', ('active', 'under_review')),
            ], limit=1) if order.patient_id else \
                request.env['health.careplan']
            prn_activities = plan.careplan_activity_ids.filtered(
                lambda activity: activity.frequency == 'prn'
                and activity.status in ('scheduled', 'in_progress'))
            return self._prepare_json_response(data={
                'tasks': [self._serialize_task(task) for task in tasks],
                'careplan': {
                    'id': plan.id,
                    'name': plan.name,
                    'title': plan.title or '',
                    'category': plan.category_id.code or '',
                } if plan else None,
                'prn_activities': [{
                    'id': activity.id,
                    'name': activity.name,
                    'instructions': activity.instructions or '',
                } for activity in prn_activities],
            })
        except Exception as exc:  # noqa: BLE001
            return self._prepare_json_response(
                error=str(exc), status_code=500)

    # ------------------------------------------------------------------
    # POST /health_pwa/api/careplan_tasks/<id>/update
    # ------------------------------------------------------------------
    @http.route('/health_pwa/api/careplan_tasks/<int:task_id>/update',
                type='http', auth='user', methods=['POST'], csrf=False)
    def careplan_task_update(self, task_id, **kwargs):
        if not self._check_api_access():
            return self._prepare_json_response(
                error=_('Access denied'), status_code=403)
        try:
            body = self._read_json_body()
            if body is None:
                return self._prepare_json_response(
                    error=_('Invalid JSON body'), status_code=400)
            task = request.env['health.careplan.task'].browse(task_id)
            if not task.exists():
                return self._prepare_json_response(
                    error=_('Task not found'), status_code=404)
            state = body.get('state')
            if state == 'done':
                task.action_mark_done()
                message = _('Task marked done')
            elif state == 'not_done':
                task.action_mark_not_done(
                    reason=body.get('not_done_reason'),
                    note=body.get('not_done_note'))
                message = _('Task marked not done')
            elif state == 'pending':
                task.action_reset_pending()
                message = _('Task reset to pending')
            else:
                return self._prepare_json_response(
                    error=_('Invalid state: %s') % state,
                    status_code=400)
            return self._prepare_json_response(data={
                'task_id': task.id,
                'state': task.state,
                'message': message,
            })
        except (UserError, ValidationError) as exc:
            return self._prepare_json_response(
                error=str(exc), status_code=400)
        except Exception as exc:  # noqa: BLE001
            _logger.exception(
                'Care plan task update failed for task %s', task_id)
            return self._prepare_json_response(
                error=str(exc), status_code=500)

    # ------------------------------------------------------------------
    # POST /health_pwa/api/fso/<id>/careplan_tasks/add_prn
    # ------------------------------------------------------------------
    @http.route('/health_pwa/api/fso/<int:order_id>/careplan_tasks/add_prn',
                type='http', auth='user', methods=['POST'], csrf=False)
    def fso_careplan_add_prn(self, order_id, **kwargs):
        if not self._check_api_access():
            return self._prepare_json_response(
                error=_('Access denied'), status_code=403)
        try:
            body = self._read_json_body()
            if body is None:
                return self._prepare_json_response(
                    error=_('Invalid JSON body'), status_code=400)
            order = request.env['health.fieldservice.order'].browse(order_id)
            if not order.exists():
                return self._prepare_json_response(
                    error=_('Order not found'), status_code=404)
            activity = request.env['health.careplan.activity'].browse(
                int(body.get('activity_id') or 0))
            if not activity.exists():
                return self._prepare_json_response(
                    error=_('Activity not found'), status_code=404)
            task = request.env['health.careplan.task'].add_prn_task(
                order, activity)
            return self._prepare_json_response(
                data=self._serialize_task(task))
        except (UserError, ValidationError) as exc:
            return self._prepare_json_response(
                error=str(exc), status_code=400)
        except Exception as exc:  # noqa: BLE001
            _logger.exception(
                'PRN task creation failed for FSO %s', order_id)
            return self._prepare_json_response(
                error=str(exc), status_code=500)

    # ------------------------------------------------------------------
    # GET /health_pwa/api/patients/<id>/careplans
    # ------------------------------------------------------------------
    @http.route('/health_pwa/api/patients/<int:patient_id>/careplans',
                type='http', auth='user', methods=['GET'], csrf=False)
    def patient_careplans(self, patient_id, **kwargs):
        if not self._check_api_access():
            return self._prepare_json_response(
                error=_('Access denied'), status_code=403)
        try:
            patient = request.env['res.partner'].browse(patient_id)
            if not patient.exists():
                return self._prepare_json_response(
                    error=_('Patient not found'), status_code=404)
            plans = request.env['health.careplan'].search([
                ('client_id', '=', patient.id),
                ('state', '!=', 'cancelled'),
            ], order='create_date desc')
            return self._prepare_json_response(data={
                'careplans': [{
                    'id': plan.id,
                    'name': plan.name,
                    'title': plan.title or '',
                    'category': plan.category_id.code or '',
                    'state': plan.state,
                    'period_start': (
                        fields.Date.to_string(plan.period_start)
                        if plan.period_start else None),
                    'period_end': (
                        fields.Date.to_string(plan.period_end)
                        if plan.period_end else None),
                    'adherence_rate': plan.adherence_rate,
                    'goals': [{
                        'name': goal.name,
                        'target': {
                            'min': goal.target_value_min,
                            'max': goal.target_value_max,
                            'unit': goal.target_unit or '',
                        },
                        'latest_value': goal.latest_value,
                        'is_on_target': goal.is_on_target,
                        'due_date': (
                            fields.Date.to_string(goal.due_date)
                            if goal.due_date else None),
                    } for goal in plan.goal_ids],
                } for plan in plans],
            })
        except Exception as exc:  # noqa: BLE001
            return self._prepare_json_response(
                error=str(exc), status_code=500)
