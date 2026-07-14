# -*- coding: utf-8 -*-
"""Vitals PWA endpoints (clinical spec §2.7).

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


def _parse_client_datetime(value):
    """'2026-07-07T03:15:00Z' / '2026-07-07 03:15:00' → Datetime."""
    if not value:
        return False
    if isinstance(value, str):
        value = value.replace('Z', '').replace('T', ' ')
    return fields.Datetime.to_datetime(value)


class HealthVitalsPWAController(http.Controller):
    """Vitals endpoints under the PWA API namespace."""

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

    def _serialize_alert(self, observation):
        return {
            'type_code': observation.vitals_type_id.code,
            'value': observation.value_quantity,
            'alert_level': observation.alert_level,
            'message': _(
                '%(name)s %(value)s%(unit)s is %(level)s',
                name=observation.vitals_type_id.name,
                value=observation.value_quantity,
                unit=observation.vitals_type_id.unit_display or '',
                level=observation.alert_level),
        }

    # ------------------------------------------------------------------
    # GET /health_pwa/api/vitals/types
    # ------------------------------------------------------------------
    @http.route('/health_pwa/api/vitals/types',
                type='http', auth='user', methods=['GET'], csrf=False)
    def vitals_types(self, **kwargs):
        if not self._check_api_access():
            return self._prepare_json_response(
                error=_('Access denied'), status_code=403)
        try:
            types = request.env['health.vitals.type'].search(
                [], order='sequence, name')
            return self._prepare_json_response(data={
                'types': [{
                    'id': vtype.id,
                    'code': vtype.code,
                    'loinc_code': vtype.loinc_code,
                    'name': vtype.name,
                    'name_vi': vtype.name_vi or '',
                    'ucum_unit': vtype.ucum_unit or '',
                    'unit_display': vtype.unit_display or '',
                    'value_type': vtype.value_type,
                    'parent_code': vtype.parent_id.code or None,
                    'decimals': vtype.decimals,
                    'plausible_min': vtype.plausible_min,
                    'plausible_max': vtype.plausible_max,
                    'sequence': vtype.sequence,
                } for vtype in types],
            })
        except Exception as exc:  # noqa: BLE001
            return self._prepare_json_response(
                error=str(exc), status_code=500)

    # ------------------------------------------------------------------
    # POST /health_pwa/api/fso/<id>/vitals
    # ------------------------------------------------------------------
    @http.route('/health_pwa/api/fso/<int:order_id>/vitals',
                type='http', auth='user', methods=['POST'], csrf=False)
    def fso_vitals_create(self, order_id, **kwargs):
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
            if not order.patient_id:
                return self._prepare_json_response(
                    error=_('Order has no client'), status_code=400)

            Observation = request.env['health.observation']
            Type = request.env['health.vitals.type']
            clinical_note_id = body.get('clinical_note_id') or False
            created = Observation.browse()

            for item in (body.get('observations') or []):
                code = item.get('code')
                vtype = Type.get_by_code(code) if code else False
                if not vtype:
                    return self._prepare_json_response(
                        error=_('Unknown observation code: %s') % code,
                        status_code=400)
                vals = {
                    'client_id': order.patient_id.id,
                    'vitals_type_id': vtype.id,
                    'order_id': order.id,
                    'clinical_note_id': clinical_note_id,
                    'effective_datetime': (
                        _parse_client_datetime(item.get('effective_datetime'))
                        or fields.Datetime.now()),
                    'body_position': item.get('body_position') or False,
                    'method': item.get('method') or vtype.default_method or '',
                    'device': item.get('device') or '',
                }
                if vtype.value_type == 'string':
                    vals['value_text'] = str(item.get('value') or '')
                else:
                    vals['value_quantity'] = float(item.get('value') or 0.0)
                created |= Observation.create(vals)

            bp = body.get('bp') or {}
            if bp.get('systolic') or bp.get('diastolic'):
                panel = Observation.create_panel(
                    order.patient_id.id, 'bp_panel',
                    [
                        {'code': 'bp_sys', 'value': bp.get('systolic')},
                        {'code': 'bp_dia', 'value': bp.get('diastolic')},
                    ],
                    order_id=order.id,
                    clinical_note_id=clinical_note_id,
                    effective_datetime=(
                        _parse_client_datetime(bp.get('effective_datetime'))
                        or fields.Datetime.now()),
                    body_position=bp.get('body_position') or False,
                    method=bp.get('method') or '',
                    device=bp.get('device') or '',
                )
                created |= panel
                created |= panel.child_ids

            # NEWS2 score (telemonitoring). Registry guard keeps
            # health_vitals installable without health_telemonitoring.
            ews_payload = None
            if 'health.ews.score' in request.env and created:
                score = request.env['health.ews.score'].sudo().search(
                    [('observation_ids', 'in', created.ids),
                     ('superseded', '=', False)],
                    order='id desc', limit=1)
                if score:
                    ews_payload = {
                        'total': score.total,
                        'band': score.band,
                        'defaulted_consciousness': score.defaulted_consciousness,
                    }

            return self._prepare_json_response(data={
                'created_ids': created.ids,
                'alerts': [
                    self._serialize_alert(observation)
                    for observation in created
                    if observation.alert_level != 'none'],
                'ews': ews_payload,
            })
        except (UserError, ValidationError) as exc:
            return self._prepare_json_response(
                error=str(exc), status_code=400)
        except Exception as exc:  # noqa: BLE001
            _logger.exception(
                'Vitals creation failed for FSO %s', order_id)
            return self._prepare_json_response(
                error=str(exc), status_code=500)

    # ------------------------------------------------------------------
    # GET /health_pwa/api/patients/<id>/vitals
    # ------------------------------------------------------------------
    @http.route('/health_pwa/api/patients/<int:patient_id>/vitals',
                type='http', auth='user', methods=['GET'], csrf=False)
    def patient_vitals(self, patient_id, **kwargs):
        if not self._check_api_access():
            return self._prepare_json_response(
                error=_('Access denied'), status_code=403)
        try:
            patient = request.env['res.partner'].browse(patient_id)
            if not patient.exists():
                return self._prepare_json_response(
                    error=_('Patient not found'), status_code=404)
            try:
                limit = int(kwargs.get('limit') or 50)
            except (ValueError, TypeError):
                limit = 50
            domain = [
                ('client_id', '=', patient.id),
                ('state', '!=', 'entered_in_error'),
            ]
            type_code = kwargs.get('type_code')
            if type_code:
                domain.append(('vitals_type_id.code', '=', type_code))
            date_from = _parse_client_datetime(kwargs.get('date_from'))
            if date_from:
                domain.append(('effective_datetime', '>=', date_from))
            observations = request.env['health.observation'].search(
                domain, order='effective_datetime desc, id desc',
                limit=limit)
            thresholds = request.env['health.vitals.threshold'].search([
                ('client_id', '=', patient.id),
                ('active', '=', True),
            ])
            return self._prepare_json_response(data={
                'observations': [{
                    'id': observation.id,
                    'type_code': observation.vitals_type_id.code,
                    'loinc_code': observation.loinc_code,
                    'name': observation.vitals_type_id.name,
                    'value': (observation.value_text
                              if observation.vitals_type_id.value_type
                              == 'string'
                              else observation.value_quantity),
                    'unit': observation.vitals_type_id.unit_display or '',
                    'effective_datetime': (
                        observation.effective_datetime.strftime(
                            '%Y-%m-%dT%H:%M:%SZ')
                        if observation.effective_datetime else ''),
                    'alert_level': observation.alert_level,
                    'performer': observation.performer_id.name or '',
                } for observation in observations],
                'thresholds': [{
                    'type_code': threshold.vitals_type_id.code,
                    'severity': threshold.severity,
                    'min': threshold.min_value,
                    'max': threshold.max_value,
                } for threshold in thresholds],
            })
        except Exception as exc:  # noqa: BLE001
            return self._prepare_json_response(
                error=str(exc), status_code=500)

    # ------------------------------------------------------------------
    # GET /health_pwa/api/patients/<id>/vitals/trend
    # ------------------------------------------------------------------
    @http.route('/health_pwa/api/patients/<int:patient_id>/vitals/trend',
                type='http', auth='user', methods=['GET'], csrf=False)
    def patient_vitals_trend(self, patient_id, **kwargs):
        if not self._check_api_access():
            return self._prepare_json_response(
                error=_('Access denied'), status_code=403)
        try:
            patient = request.env['res.partner'].browse(patient_id)
            if not patient.exists():
                return self._prepare_json_response(
                    error=_('Patient not found'), status_code=404)
            type_code = kwargs.get('type_code')
            vtype = request.env['health.vitals.type'].get_by_code(
                type_code) if type_code else False
            if not vtype:
                return self._prepare_json_response(
                    error=_('Unknown observation code: %s') % type_code,
                    status_code=404)
            try:
                days = int(kwargs.get('days') or 30)
            except (ValueError, TypeError):
                days = 30
            date_from = fields.Datetime.subtract(
                fields.Datetime.now(), days=days)
            points = request.env['health.observation'].get_trend(
                patient.id, vtype.id, date_from=date_from)
            return self._prepare_json_response(data={
                'points': [{
                    't': point['datetime'].replace(' ', 'T') + 'Z',
                    'v': point['value'],
                } for point in points],
                'unit': vtype.unit_display or '',
            })
        except Exception as exc:  # noqa: BLE001
            return self._prepare_json_response(
                error=str(exc), status_code=500)
