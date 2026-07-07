# -*- coding: utf-8 -*-
"""Incident PWA endpoints (clinical spec §5.7).

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


def _selection_labels(record, field_name):
    return dict(
        record._fields[field_name]._description_selection(record.env))


class HealthIncidentPWAController(http.Controller):
    """Incident endpoints under the PWA API namespace."""

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

    def _serialize_incident(self, incident):
        return {
            'id': incident.id,
            'name': incident.name,
            'incident_type': incident.incident_type,
            'severity': incident.severity,
            'client_name': incident.client_id.name or '',
            'state': incident.state,
            'incident_datetime': (
                incident.incident_datetime.strftime('%Y-%m-%dT%H:%M:%SZ')
                if incident.incident_datetime else None),
            'description': incident.description or '',
        }

    def _create_photo_attachments(self, incident, photos):
        """photos: [{'base64': ..., 'filename': ...}] → ir.attachment
        rows linked through the evidence m2m."""
        Attachment = request.env['ir.attachment']
        attachment_ids = []
        for index, photo in enumerate(photos or []):
            datas = (photo or {}).get('base64')
            if not datas:
                continue
            # Strip data-URI prefix if the client sent one.
            if ',' in datas[:64] and datas.strip().startswith('data:'):
                datas = datas.split(',', 1)[1]
            attachment = Attachment.create({
                'name': (photo.get('filename')
                         or 'incident_photo_%s_%s.jpg'
                         % (incident.id, index + 1)),
                'type': 'binary',
                'datas': datas,
                'res_model': 'health.incident',
                'res_id': incident.id,
                'mimetype': photo.get('mimetype') or 'image/jpeg',
            })
            attachment_ids.append(attachment.id)
        if attachment_ids:
            # sudo(): nurses can create incidents but have no write
            # ACL — linking the just-captured photos is part of the
            # report action, not an edit.
            incident.sudo().write(
                {'attachment_ids': [(4, aid) for aid in attachment_ids]})
        return attachment_ids

    # ------------------------------------------------------------------
    # POST /health_pwa/api/incidents
    # ------------------------------------------------------------------
    @http.route('/health_pwa/api/incidents',
                type='http', auth='user', methods=['POST'], csrf=False)
    def incident_create(self, **kwargs):
        if not self._check_api_access():
            return self._prepare_json_response(
                error=_('Access denied'), status_code=403)
        try:
            body = self._read_json_body()
            if body is None:
                return self._prepare_json_response(
                    error=_('Invalid JSON body'), status_code=400)
            Incident = request.env['health.incident']

            # Offline-queue idempotency: a replayed mutation must not
            # create a duplicate (acceptance #8).
            mutation_id = body.get('client_mutation_id')
            if mutation_id:
                existing = Incident.search(
                    [('client_mutation_id', '=', mutation_id)], limit=1)
                if existing:
                    return self._prepare_json_response(data={
                        'incident_id': existing.id,
                        'name': existing.name,
                        'message': _('Incident already recorded '
                                     '(duplicate mutation ignored)'),
                    })

            incident_type = body.get('incident_type')
            description = (body.get('description') or '').strip()
            if not incident_type or not description:
                return self._prepare_json_response(
                    error=_('incident_type and description are '
                            'required'), status_code=400)

            vals = {
                'incident_type': incident_type,
                'severity': str(body.get('severity') or '2'),
                'description': description,
                'immediate_actions': body.get('immediate_actions') or False,
                'location': body.get('location') or False,
                'witnesses': body.get('witnesses') or False,
                # PWA-created incidents start in 'reported' (binding
                # design decision) — the model default.
            }
            if body.get('client_id'):
                client = request.env['res.partner'].browse(
                    int(body['client_id']))
                if not client.exists():
                    return self._prepare_json_response(
                        error=_('Client not found'), status_code=404)
                vals['client_id'] = client.id
            if body.get('order_id'):
                order = request.env['health.fieldservice.order'].browse(
                    int(body['order_id']))
                if not order.exists():
                    return self._prepare_json_response(
                        error=_('Order not found'), status_code=404)
                vals['order_id'] = order.id
            if body.get('incident_datetime'):
                vals['incident_datetime'] = fields.Datetime.to_datetime(
                    body['incident_datetime'].replace(
                        'T', ' ').replace('Z', ''))
            if mutation_id:
                vals['client_mutation_id'] = mutation_id

            incident = Incident.create(vals)
            attachment_ids = self._create_photo_attachments(
                incident, body.get('photos'))
            return self._prepare_json_response(data={
                'incident_id': incident.id,
                'name': incident.name,
                'message': _('Incident %(name)s recorded '
                             '(%(photos)s photo(s) attached)',
                             name=incident.name,
                             photos=len(attachment_ids)),
            })
        except (UserError, ValidationError) as exc:
            return self._prepare_json_response(
                error=str(exc), status_code=400)
        except Exception as exc:  # noqa: BLE001
            _logger.exception('Incident creation failed')
            return self._prepare_json_response(
                error=str(exc), status_code=500)

    # ------------------------------------------------------------------
    # GET /health_pwa/api/incidents/mine
    # ------------------------------------------------------------------
    @http.route('/health_pwa/api/incidents/mine',
                type='http', auth='user', methods=['GET'], csrf=False)
    def incidents_mine(self, **kwargs):
        if not self._check_api_access():
            return self._prepare_json_response(
                error=_('Access denied'), status_code=403)
        try:
            limit = min(int(kwargs.get('limit', 20)), 100)
            offset = max(int(kwargs.get('offset', 0)), 0)
            domain = [('reporter_id', '=', request.env.uid)]
            Incident = request.env['health.incident']
            total_count = Incident.search_count(domain)
            incidents = Incident.search(
                domain, order='incident_datetime desc',
                limit=limit, offset=offset)
            return self._prepare_json_response(data={
                'incidents': [self._serialize_incident(incident)
                              for incident in incidents],
                'total_count': total_count,
                'has_more': offset + len(incidents) < total_count,
            })
        except Exception as exc:  # noqa: BLE001
            return self._prepare_json_response(
                error=str(exc), status_code=500)

    # ------------------------------------------------------------------
    # GET /health_pwa/api/incidents/types
    # ------------------------------------------------------------------
    @http.route('/health_pwa/api/incidents/types',
                type='http', auth='user', methods=['GET'], csrf=False)
    def incident_types(self, **kwargs):
        if not self._check_api_access():
            return self._prepare_json_response(
                error=_('Access denied'), status_code=403)
        try:
            Incident = request.env['health.incident']
            incident_vi = Incident.with_context(lang='vi_VN')
            labels_en = _selection_labels(Incident, 'incident_type')
            labels_vi = _selection_labels(incident_vi, 'incident_type')
            severities_en = _selection_labels(Incident, 'severity')
            severities_vi = _selection_labels(incident_vi, 'severity')
            return self._prepare_json_response(data={
                'types': [{
                    'code': code,
                    'label': labels_en.get(code, code),
                    'label_vi': labels_vi.get(code, code),
                } for code, _label in Incident._fields[
                    'incident_type'].selection],
                'severities': [{
                    'code': code,
                    'label': severities_en.get(code, code),
                    'label_vi': severities_vi.get(code, code),
                } for code, _label in Incident._fields[
                    'severity'].selection],
            })
        except Exception as exc:  # noqa: BLE001
            return self._prepare_json_response(
                error=str(exc), status_code=500)
