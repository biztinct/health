# -*- coding: utf-8 -*-
"""EVV PWA endpoints (spec A.4).

Matches health_pwa conventions exactly: type='http', auth='user',
csrf=False, manual json.loads(request.httprequest.data), and the same
response envelope {success, timestamp, data|error}. The envelope/auth
helpers are deliberately DUPLICATED from
health_pwa/controllers/api.py (instantiating HealthPWAAPIController is
not allowed per spec).
"""
import base64
import hashlib
import json
import logging

from odoo import _, fields, http
from odoo.http import request

_logger = logging.getLogger(__name__)

MAX_PUSH_BATCH = 200

EVENT_CONTEXT_KEYS = (
    'event_datetime', 'lat', 'lng', 'accuracy_m', 'device_uuid',
    'client_event_uuid', 'client_hash', 'payload')


class HealthEVVController(http.Controller):
    """EVV endpoints under the PWA API namespace."""

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
    def _get_order(self, order_id):
        order = request.env['health.fieldservice.order'].browse(order_id)
        if not order.exists():
            return None
        return order

    def _read_json_body(self):
        try:
            return json.loads(request.httprequest.data or b'{}')
        except (ValueError, TypeError):
            return None

    def _event_vals_from_body(self, body, employee):
        return {
            'event_type': body.get('event_type'),
            'event_datetime': (body.get('event_datetime')
                               or fields.Datetime.now()),
            'lat': body.get('lat') or 0.0,
            'lng': body.get('lng') or 0.0,
            'accuracy_m': body.get('accuracy_m') or 0.0,
            'staff_id': employee.id,
            'device_uuid': body.get('device_uuid') or '',
            'client_event_uuid': body.get('client_event_uuid') or '',
            'payload': body.get('payload') or {},
            'origin': body.get('origin') or 'online',
        }

    def _evv_context(self, body):
        """Context keys consumed by the FSO action_start/complete hooks."""
        return {
            'evv_lat': body.get('lat') or 0.0,
            'evv_lng': body.get('lng') or 0.0,
            'evv_accuracy': body.get('accuracy_m') or 0.0,
            'evv_device_uuid': body.get('device_uuid') or '',
            'evv_client_uuid': body.get('client_event_uuid') or '',
            'evv_client_hash': body.get('client_hash') or '',
            'evv_event_datetime': body.get('event_datetime') or '',
            'evv_payload': body.get('payload') or {},
            'evv_origin': body.get('origin') or 'online',
        }

    def _maybe_start_service(self, order, body):
        """Side effect (spec A.4): checkin on an assigned/confirmed visit
        starts it through the existing workflow. checkout never
        auto-completes (completion needs notes/quote)."""
        if order.state in ('assigned', 'confirmed'):
            try:
                order.with_context(**self._evv_context(body)) \
                    .action_start_service()
            except Exception as exc:  # noqa: BLE001 — EVV never blocks
                _logger.warning(
                    'EVV auto start-service failed for FSO %s: %s',
                    order.id, exc)

    def _serialize_event(self, event, duplicate=False, client_hash=None):
        return {
            'event_id': event.id,
            'sequence': event.sequence,
            'chain_hash': event.chain_hash,
            'inside_geofence': event.inside_geofence,
            'distance_m': round(event.distance_m or 0.0, 1),
            'duplicate': duplicate,
            'hash_match': (client_hash == event.payload_hash
                           if client_hash else True),
        }

    # ------------------------------------------------------------------
    # GET /health_pwa/api/fso/<id>/evv/config
    # ------------------------------------------------------------------
    @http.route('/health_pwa/api/fso/<int:order_id>/evv/config',
                type='http', auth='user', methods=['GET'], csrf=False)
    def evv_config(self, order_id, **kwargs):
        if not self._check_api_access():
            return self._prepare_json_response(
                error=_('Access denied'), status_code=403)
        try:
            order = self._get_order(order_id)
            if not order:
                return self._prepare_json_response(
                    error=_('Order not found'), status_code=404)
            partner = order.patient_id
            lat = partner.partner_latitude or 0.0
            lng = partner.partner_longitude or 0.0
            enabled = bool(partner.geofence_enabled and lat and lng)
            events = order.evv_event_ids
            accuracy_max = float(
                request.env['ir.config_parameter'].sudo().get_param(
                    'health_evv.default_accuracy_max_m', '100'))
            employee = request.env.user.employee_id
            return self._prepare_json_response(data={
                'fso_id': order.id,
                'geofence': {
                    'lat': lat,
                    'lng': lng,
                    'radius_m': partner.geofence_radius_m or 150,
                    'enabled': enabled,
                },
                'checked_in': bool(events.filtered(
                    lambda event: event.event_type == 'checkin')),
                'checked_out': bool(events.filtered(
                    lambda event: event.event_type == 'checkout')),
                'signature_done': bool(events.filtered(
                    lambda event: event.event_type == 'signature')),
                'server_time': fields.Datetime.now().strftime(
                    '%Y-%m-%dT%H:%M:%SZ'),
                # Additive keys: staff_id is part of the canonical hash
                # recipe; scheduled_end drives client-side exit-watch
                # resumption; accuracy_max_m mirrors the server config.
                'staff_id': employee.id if employee else 0,
                'accuracy_max_m': accuracy_max,
                'scheduled_end': (
                    order.estimated_end_datetime.strftime(
                        '%Y-%m-%dT%H:%M:%SZ')
                    if order.estimated_end_datetime else None),
            })
        except Exception as exc:  # noqa: BLE001
            return self._prepare_json_response(
                error=str(exc), status_code=500)

    # ------------------------------------------------------------------
    # POST /health_pwa/api/fso/<id>/evv/event
    # ------------------------------------------------------------------
    @http.route('/health_pwa/api/fso/<int:order_id>/evv/event',
                type='http', auth='user', methods=['POST'], csrf=False)
    def evv_event(self, order_id, **kwargs):
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
            if not body.get('event_type') or not body.get('client_event_uuid'):
                return self._prepare_json_response(
                    error=_('event_type and client_event_uuid are required'),
                    status_code=400)
            employee = request.env.user.employee_id
            if not employee:
                return self._prepare_json_response(
                    error=_('Current user has no linked employee'),
                    status_code=400)

            Event = request.env['health.evv.event']
            client_hash = body.get('client_hash') or None
            duplicate = bool(Event.search_count([
                ('fso_id', '=', order.id),
                ('client_event_uuid', '=', body['client_event_uuid']),
            ]))
            event = Event.append_event(
                order, self._event_vals_from_body(body, employee),
                client_hash=client_hash)
            if not duplicate and body.get('event_type') == 'checkin':
                self._maybe_start_service(order, body)
            return self._prepare_json_response(
                data=self._serialize_event(
                    event, duplicate=duplicate, client_hash=client_hash))
        except Exception as exc:  # noqa: BLE001
            _logger.exception('EVV event append failed for FSO %s', order_id)
            return self._prepare_json_response(
                error=str(exc), status_code=500)

    # ------------------------------------------------------------------
    # POST /health_pwa/api/evv/push  (batch offline queue flush)
    # ------------------------------------------------------------------
    @http.route('/health_pwa/api/evv/push',
                type='http', auth='user', methods=['POST'], csrf=False)
    def evv_push(self, **kwargs):
        if not self._check_api_access():
            return self._prepare_json_response(
                error=_('Access denied'), status_code=403)
        try:
            body = self._read_json_body()
            if body is None:
                return self._prepare_json_response(
                    error=_('Invalid JSON body'), status_code=400)
            events = body.get('events') or []
            if not isinstance(events, list):
                return self._prepare_json_response(
                    error=_('events must be a list'), status_code=400)
            if len(events) > MAX_PUSH_BATCH:
                return self._prepare_json_response(
                    error=_('Batch too large (max %s events)') % MAX_PUSH_BATCH,
                    status_code=400)
            employee = request.env.user.employee_id
            if not employee:
                return self._prepare_json_response(
                    error=_('Current user has no linked employee'),
                    status_code=400)

            Event = request.env['health.evv.event']
            Order = request.env['health.fieldservice.order']
            # Process grouped by FSO in device event_datetime order.
            events = sorted(events, key=lambda item: (
                item.get('fso_id') or 0, item.get('event_datetime') or ''))
            accepted, duplicates, results = 0, 0, []
            for item in events:
                uuid_ = item.get('client_event_uuid') or ''
                result = {'client_event_uuid': uuid_}
                try:
                    with request.env.cr.savepoint():
                        order = Order.browse(int(item.get('fso_id') or 0))
                        if not order.exists():
                            raise ValueError(_('Order not found'))
                        if not item.get('event_type') or not uuid_:
                            raise ValueError(_(
                                'event_type and client_event_uuid are '
                                'required'))
                        client_hash = item.get('client_hash') or None
                        duplicate = bool(Event.search_count([
                            ('fso_id', '=', order.id),
                            ('client_event_uuid', '=', uuid_)]))
                        vals = self._event_vals_from_body(item, employee)
                        vals['origin'] = item.get('origin') or 'offline_sync'
                        event = Event.append_event(
                            order, vals, client_hash=client_hash)
                        if duplicate:
                            duplicates += 1
                        else:
                            accepted += 1
                            if item.get('event_type') == 'checkin':
                                self._maybe_start_service(order, item)
                        result.update(self._serialize_event(
                            event, duplicate=duplicate,
                            client_hash=client_hash))
                except Exception as exc:  # noqa: BLE001 — one bad event
                    # never aborts the batch (own savepoint).
                    result['error'] = str(exc)
                results.append(result)
            return self._prepare_json_response(data={
                'accepted': accepted,
                'duplicates': duplicates,
                'results': results,
            })
        except Exception as exc:  # noqa: BLE001
            _logger.exception('EVV push failed')
            return self._prepare_json_response(
                error=str(exc), status_code=500)

    # ------------------------------------------------------------------
    # POST /health_pwa/api/fso/<id>/evv/signature
    # ------------------------------------------------------------------
    @http.route('/health_pwa/api/fso/<int:order_id>/evv/signature',
                type='http', auth='user', methods=['POST'], csrf=False)
    def evv_signature(self, order_id, **kwargs):
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
            image_b64 = body.get('image_base64') or ''
            if image_b64.startswith('data:'):
                image_b64 = image_b64.split(',', 1)[-1]
            if not image_b64 or not body.get('client_event_uuid'):
                return self._prepare_json_response(
                    error=_('image_base64 and client_event_uuid are '
                            'required'), status_code=400)
            employee = request.env.user.employee_id
            if not employee:
                return self._prepare_json_response(
                    error=_('Current user has no linked employee'),
                    status_code=400)
            try:
                png_bytes = base64.b64decode(image_b64)
            except Exception:
                return self._prepare_json_response(
                    error=_('Invalid base64 image'), status_code=400)
            png_sha256 = hashlib.sha256(png_bytes).hexdigest()

            attachment = request.env['ir.attachment'].create({
                'name': 'EVV-Signature-%s.png' % (order.name or order.id),
                'res_model': 'health.fieldservice.order',
                'res_id': order.id,
                'type': 'binary',
                'datas': image_b64,
                'mimetype': 'image/png',
            })
            order.write({
                'evv_signature_attachment_id': attachment.id,
                'evv_signer_name': body.get('signer_name') or '',
                'evv_signer_relationship': (
                    body.get('signer_relationship') or 'other'),
                'evv_signed_at': fields.Datetime.now(),
            })

            payload = {
                'signer_name': body.get('signer_name') or '',
                'signer_relationship': (
                    body.get('signer_relationship') or 'other'),
                'attachment_id': attachment.id,
                'png_sha256': png_sha256,
            }
            vals = self._event_vals_from_body(body, employee)
            vals.update(event_type='signature', payload=payload)
            event = request.env['health.evv.event'].append_event(
                order, vals, client_hash=body.get('client_hash') or None)
            return self._prepare_json_response(data={
                'attachment_id': attachment.id,
                'event_id': event.id,
            })
        except Exception as exc:  # noqa: BLE001
            _logger.exception('EVV signature failed for FSO %s', order_id)
            return self._prepare_json_response(
                error=str(exc), status_code=500)

    # ------------------------------------------------------------------
    # GET /health_pwa/api/fso/<id>/evv/report
    # ------------------------------------------------------------------
    @http.route('/health_pwa/api/fso/<int:order_id>/evv/report',
                type='http', auth='user', methods=['GET'], csrf=False)
    def evv_report(self, order_id, **kwargs):
        if not self._check_api_access():
            return self._prepare_json_response(
                error=_('Access denied'), status_code=403)
        try:
            order = self._get_order(order_id)
            if not order:
                return self._prepare_json_response(
                    error=_('Order not found'), status_code=404)
            events = order.evv_event_ids.sorted(
                key=lambda event: (event.sequence, event.id))
            signature = None
            if order.evv_signature_attachment_id:
                signature = {
                    'signer_name': order.evv_signer_name or '',
                    'relationship': order.evv_signer_relationship or '',
                    'attachment_url': '/web/content/%s'
                                      % order.evv_signature_attachment_id.id,
                }
            return self._prepare_json_response(data={
                'verified': order.evv_verified,
                'verified_units': order.evv_verified_units,
                'chain_valid': order.evv_chain_valid,
                'events': [{
                    'sequence': event.sequence,
                    'event_type': event.event_type,
                    'event_datetime': event.event_datetime.strftime(
                        '%Y-%m-%dT%H:%M:%SZ') if event.event_datetime else '',
                    'inside_geofence': event.inside_geofence,
                    'distance_m': round(event.distance_m or 0.0, 1),
                    'accuracy_m': round(event.accuracy_m or 0.0, 1),
                    'chain_hash': event.chain_hash,
                } for event in events],
                'signature': signature,
            })
        except Exception as exc:  # noqa: BLE001
            return self._prepare_json_response(
                error=str(exc), status_code=500)
