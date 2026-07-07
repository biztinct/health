# -*- coding: utf-8 -*-
"""Clinical forms PWA endpoints (spec §4.8).

Matches health_pwa conventions exactly: type='http', auth='user',
csrf=False, manual json.loads(request.httprequest.data), and the same
response envelope {success, timestamp, data|error}. The envelope/auth
helpers are deliberately DUPLICATED from health_pwa/controllers/api.py
(existing convention — api.py and sync.py both do it).
"""
import base64
import json
import logging

from odoo import _, fields, http
from odoo.http import request

_logger = logging.getLogger(__name__)


class HealthFormsPWAController(http.Controller):
    """Clinical forms endpoints under the PWA API namespace."""

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
            return json.loads(
                request.httprequest.data.decode('utf-8')
                if request.httprequest.data else '{}')
        except (ValueError, TypeError, UnicodeDecodeError):
            return None

    def _get_order(self, order_id):
        order = request.env['health.fieldservice.order'].browse(order_id)
        return order if order.exists() else None

    def _serialize_instance(self, instance, with_answers=True):
        data = {
            'id': instance.id,
            'template_code': instance.template_code,
            'template_version': instance.template_version,
            'state': instance.state,
            'total_score': instance.total_score,
            'score_label': instance.score_label or '',
            'score_label_vi': instance.score_label_vi or '',
            'completed_datetime': (
                instance.completed_datetime.isoformat()
                if instance.completed_datetime else None),
        }
        if with_answers:
            data['answers'] = instance.answers_json or {}
        return data

    def _decode_media_answers(self, instance_name, answers):
        """Rewrite {"base64": ..., "filename": ...} media answers into
        {"attachment_id": id} (photo/signature — §4.8 submit contract).
        Returns (answers, attachment_ids)."""
        attachment_ids = []
        rewritten = {}
        for key, value in (answers or {}).items():
            if isinstance(value, dict) and value.get('base64'):
                image_b64 = value['base64']
                if image_b64.startswith('data:'):
                    image_b64 = image_b64.split(',', 1)[-1]
                # Validate the base64 payload before storing.
                base64.b64decode(image_b64)
                attachment = request.env['ir.attachment'].create({
                    'name': value.get('filename')
                            or 'FORM-%s-%s.png' % (instance_name, key),
                    'type': 'binary',
                    'datas': image_b64,
                    'mimetype': value.get('mimetype') or 'image/png',
                })
                attachment_ids.append(attachment.id)
                rewritten[key] = {'attachment_id': attachment.id}
            else:
                rewritten[key] = value
        return rewritten, attachment_ids

    def _observation_alerts(self, instance):
        alerts = []
        try:
            for observation in instance.observation_ids:
                if getattr(observation, 'alert_level', 'none') in (
                        'warning', 'critical'):
                    alerts.append({
                        'loinc_code': observation.loinc_code,
                        'value': observation.value_quantity,
                        'alert_level': observation.alert_level,
                        'message': observation.display_name,
                    })
        except Exception as exc:  # noqa: BLE001 — alerts are informative
            _logger.warning(
                'health_forms: could not serialize observation alerts '
                'for instance %s: %s', instance.id, exc)
        return alerts

    # ------------------------------------------------------------------
    # GET /health_pwa/api/forms/templates
    # ------------------------------------------------------------------
    @http.route('/health_pwa/api/forms/templates',
                type='http', auth='user', methods=['GET'], csrf=False)
    def forms_templates(self, service_type_id=None, **kwargs):
        if not self._check_api_access():
            return self._prepare_json_response(
                error=_('Access denied'), status_code=403)
        try:
            service_type_ids = None
            if service_type_id:
                service_type_ids = [int(service_type_id)]
            templates = request.env[
                'health.form.template'].get_templates_for_service(
                    service_type_ids)
            return self._prepare_json_response(
                data={'templates': templates})
        except Exception as exc:  # noqa: BLE001
            return self._prepare_json_response(
                error=str(exc), status_code=500)

    # ------------------------------------------------------------------
    # GET /health_pwa/api/fso/<id>/forms
    # ------------------------------------------------------------------
    @http.route('/health_pwa/api/fso/<int:order_id>/forms',
                type='http', auth='user', methods=['GET'], csrf=False)
    def fso_forms(self, order_id, **kwargs):
        if not self._check_api_access():
            return self._prepare_json_response(
                error=_('Access denied'), status_code=403)
        try:
            order = self._get_order(order_id)
            if not order:
                return self._prepare_json_response(
                    error=_('Order not found'), status_code=404)
            Template = request.env['health.form.template']
            domain = [('state', '=', 'published'), ('is_latest', '=', True)]
            if order.appointment_type_id:
                domain += ['|', ('service_type_ids', '=', False),
                           ('service_type_ids', 'in',
                            order.appointment_type_id.ids)]
            else:
                domain += [('service_type_ids', '=', False)]
            templates = Template.search(domain, order='name')
            instances = request.env['health.form.instance'].search(
                [('order_id', '=', order.id)], order='create_date desc')
            return self._prepare_json_response(data={
                'applicable_templates': [{
                    'id': template.id,
                    'code': template.code,
                    'name': template.name,
                    'name_vi': template.name_vi or '',
                    'category': template.category,
                } for template in templates],
                'instances': [self._serialize_instance(instance)
                              for instance in instances],
            })
        except Exception as exc:  # noqa: BLE001
            return self._prepare_json_response(
                error=str(exc), status_code=500)

    # ------------------------------------------------------------------
    # POST /health_pwa/api/fso/<id>/forms/submit
    # ------------------------------------------------------------------
    @http.route('/health_pwa/api/fso/<int:order_id>/forms/submit',
                type='http', auth='user', methods=['POST'], csrf=False)
    def fso_forms_submit(self, order_id, **kwargs):
        if not self._check_api_access():
            return self._prepare_json_response(
                error=_('Access denied'), status_code=403)
        try:
            body = self._read_json_body()
            if body is None:
                return self._prepare_json_response(
                    error=_('Invalid JSON body'), status_code=400)
            order = self._get_order(order_id)
            if not order:
                return self._prepare_json_response(
                    error=_('Order not found'), status_code=404)
            template = request.env['health.form.template'].browse(
                int(body.get('template_id') or 0))
            if not template.exists():
                return self._prepare_json_response(
                    error=_('Template not found'), status_code=404)

            Instance = request.env['health.form.instance']
            client_uuid = (body.get('client_uuid') or '').strip()
            if client_uuid:
                # Idempotent offline replay: same client_uuid returns the
                # already-created instance, never a duplicate.
                existing = Instance.search(
                    [('client_uuid', '=', client_uuid)], limit=1)
                if existing:
                    data = self._serialize_instance(existing)
                    data.update({
                        'instance_id': existing.id,
                        'duplicate': True,
                        'observation_alerts':
                            self._observation_alerts(existing),
                    })
                    return self._prepare_json_response(data=data)

            answers, attachment_ids = self._decode_media_answers(
                '%s-%s' % (template.code, order.name or order.id),
                body.get('answers') or {})
            instance = Instance.create({
                'template_id': template.id,
                'client_id': order.patient_id.id,
                'order_id': order.id,
                'answers_json': answers,
                'client_uuid': client_uuid or False,
                'attachment_ids': [(6, 0, attachment_ids)],
            })
            for attachment_id in attachment_ids:
                request.env['ir.attachment'].browse(attachment_id).write({
                    'res_model': 'health.form.instance',
                    'res_id': instance.id,
                })
            instance.action_complete()
            return self._prepare_json_response(data={
                'instance_id': instance.id,
                'total_score': instance.total_score,
                'score_label': instance.score_label or '',
                'score_label_vi': instance.score_label_vi or '',
                'observation_alerts': self._observation_alerts(instance),
            })
        except Exception as exc:  # noqa: BLE001
            _logger.exception(
                'health_forms: submit failed for FSO %s', order_id)
            return self._prepare_json_response(
                error=str(exc), status_code=500)

    # ------------------------------------------------------------------
    # GET /health_pwa/api/patients/<id>/forms
    # ------------------------------------------------------------------
    @http.route('/health_pwa/api/patients/<int:patient_id>/forms',
                type='http', auth='user', methods=['GET'], csrf=False)
    def patient_forms(self, patient_id, template_code=None, limit=50,
                      **kwargs):
        if not self._check_api_access():
            return self._prepare_json_response(
                error=_('Access denied'), status_code=403)
        try:
            patient = request.env['res.partner'].browse(patient_id)
            if not patient.exists():
                return self._prepare_json_response(
                    error=_('Patient not found'), status_code=404)
            domain = [('client_id', '=', patient.id)]
            if template_code:
                domain.append(('template_code', '=', template_code))
            instances = request.env['health.form.instance'].search(
                domain, order='create_date desc', limit=int(limit))
            data = {
                'instances': [self._serialize_instance(instance)
                              for instance in instances],
            }
            if template_code:
                trend_instances = instances.filtered(
                    lambda i: i.state in ('completed', 'amended')
                    and i.completed_datetime).sorted('completed_datetime')
                data['trend'] = [{
                    't': instance.completed_datetime.isoformat(),
                    'v': instance.total_score,
                } for instance in trend_instances]
            return self._prepare_json_response(data=data)
        except Exception as exc:  # noqa: BLE001
            return self._prepare_json_response(
                error=str(exc), status_code=500)
