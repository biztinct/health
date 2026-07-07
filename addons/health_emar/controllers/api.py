# -*- coding: utf-8 -*-
"""eMAR PWA endpoints (spec §3.7).

Matches health_pwa conventions exactly: type='http', auth='user',
csrf=False, manual json.loads(request.httprequest.data), and the same
response envelope {success, timestamp, data|error}. The envelope/auth
helpers are deliberately DUPLICATED from health_pwa/controllers/api.py
(existing convention — api.py and sync.py both do it). No health_pwa
file is touched.
"""
import json
import logging
from datetime import datetime, timedelta

import pytz

from odoo import _, fields, http
from odoo.exceptions import UserError, ValidationError
from odoo.http import request

_logger = logging.getLogger(__name__)


class HealthEmarPWAController(http.Controller):
    """Per-visit medication checklist endpoints under the PWA API
    namespace."""

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

    def _parse_datetime(self, value):
        """ISO string (optionally suffixed Z / with offset) → naive UTC."""
        if not value:
            return False
        try:
            raw = str(value).replace('Z', '+00:00')
            parsed = datetime.fromisoformat(raw)
            if parsed.tzinfo:
                parsed = parsed.astimezone(pytz.utc).replace(tzinfo=None)
            return parsed
        except ValueError:
            return False

    def _serialize_administration(self, admin):
        order = admin.order_id
        dose = ''
        if order.dose_quantity:
            dose = ('%g %s' % (order.dose_quantity,
                               order.dose_unit or '')).strip()
        return {
            'id': admin.id,
            'order_id': order.id,
            'medication_name': admin.medication_id.name or '',
            'medication_name_vi': admin.medication_id.vietnamese_name or '',
            'dose': dose,
            'route': order.route or '',
            'planned_datetime': (admin.planned_datetime.isoformat()
                                 if admin.planned_datetime else None),
            'state': admin.state,
            'is_prn_dose': admin.is_prn_dose,
            'instructions': order.instructions or '',
            'reason_id': admin.reason_id.id or None,
            'notes': admin.notes or '',
        }

    def _serialize_order(self, order):
        dose = ''
        if order.dose_quantity:
            dose = ('%g %s' % (order.dose_quantity,
                               order.dose_unit or '')).strip()
        return {
            'id': order.id,
            'medication_name': order.medication_id.name or '',
            'medication_name_vi': order.medication_id.vietnamese_name or '',
            'dose': dose,
            'route': order.route or '',
            'frequency': order.frequency or '',
            'is_prn': order.is_prn,
            'prn_reason': order.prn_reason or '',
            'start_date': (fields.Date.to_string(order.start_date)
                           if order.start_date else None),
            'end_date': (fields.Date.to_string(order.end_date)
                         if order.end_date else None),
            'state': order.state,
            'instructions': order.instructions or '',
            'interaction_severity': order.interaction_severity,
        }

    def _serialize_reasons(self):
        reasons = request.env['health.medication.notgiven.reason'].search([])
        return [{
            'id': reason.id,
            'code': reason.code,
            'name': reason.name,
            'name_vi': reason.name_vi or '',
            'applies_to': reason.applies_to,
        } for reason in reasons]

    # ------------------------------------------------------------------
    # GET /health_pwa/api/fso/<id>/medications — per-visit checklist
    # ------------------------------------------------------------------
    @http.route('/health_pwa/api/fso/<int:order_id>/medications',
                type='http', auth='user', methods=['GET'], csrf=False)
    def fso_medications(self, order_id, **kwargs):
        if not self._check_api_access():
            return self._prepare_json_response(
                error='Access denied', status_code=403)
        try:
            fso = request.env['health.fieldservice.order'].browse(order_id)
            if not fso.exists():
                return self._prepare_json_response(
                    error='Booking not found', status_code=404)
            Admin = request.env['health.medication.administration']
            # Slots linked to this visit...
            admins = Admin.search([('fso_id', '=', fso.id)])
            # ...plus the client's unlinked planned slots due in the
            # visit window: the visit's local date, expanded by the
            # configurable slack (design decision — checklist covers
            # planned datetimes within the visit window ± slack).
            slack_hours = float(
                request.env['ir.config_parameter'].sudo().get_param(
                    'health_emar.visit_window_slack_hours', '2') or 2)
            if fso.scheduled_date:
                tz_name = fso.booking_timezone or 'Asia/Ho_Chi_Minh'
                try:
                    tz = pytz.timezone(tz_name)
                except pytz.UnknownTimeZoneError:
                    tz = pytz.timezone('Asia/Ho_Chi_Minh')
                day_start = tz.localize(datetime.combine(
                    fso.scheduled_date, datetime.min.time()))
                window_start = (day_start - timedelta(hours=slack_hours)) \
                    .astimezone(pytz.utc).replace(tzinfo=None)
                window_stop = (day_start + timedelta(days=1,
                                                     hours=slack_hours)) \
                    .astimezone(pytz.utc).replace(tzinfo=None)
                admins |= Admin.search([
                    ('client_id', '=', fso.patient_id.id),
                    ('fso_id', '=', False),
                    ('state', '=', 'planned'),
                    ('planned_datetime', '>=', window_start),
                    ('planned_datetime', '<', window_stop),
                ])
            admins = admins.sorted('planned_datetime')
            prn_orders = request.env['health.medication.order'].search([
                ('client_id', '=', fso.patient_id.id),
                ('state', '=', 'active'),
                ('is_prn', '=', True),
            ])
            return self._prepare_json_response(data={
                'administrations': [
                    self._serialize_administration(admin)
                    for admin in admins],
                'prn_orders': [{
                    'id': order.id,
                    'medication_name': order.medication_id.name or '',
                    'medication_name_vi':
                        order.medication_id.vietnamese_name or '',
                    'dose': ('%g %s' % (order.dose_quantity,
                                        order.dose_unit or '')).strip()
                            if order.dose_quantity else '',
                    'route': order.route or '',
                    'prn_reason': order.prn_reason or '',
                } for order in prn_orders],
                'reasons': self._serialize_reasons(),
            })
        except Exception as e:
            _logger.exception('eMAR fso medications failed')
            return self._prepare_json_response(
                error=str(e), status_code=500)

    # ------------------------------------------------------------------
    # POST /health_pwa/api/administrations/<id>/record — one-tap tick
    # ------------------------------------------------------------------
    @http.route('/health_pwa/api/administrations/<int:admin_id>/record',
                type='http', auth='user', methods=['POST'], csrf=False)
    def record_administration(self, admin_id, **kwargs):
        if not self._check_api_access():
            return self._prepare_json_response(
                error='Access denied', status_code=403)
        try:
            body = self._read_json_body()
            if body is None:
                return self._prepare_json_response(
                    error='Invalid JSON body', status_code=400)
            admin = request.env['health.medication.administration'] \
                .browse(admin_id)
            if not admin.exists():
                return self._prepare_json_response(
                    error='Administration not found', status_code=404)
            status = body.get('status')
            if status not in ('given', 'not_given', 'refused'):
                return self._prepare_json_response(
                    error='Invalid status (given|not_given|refused)',
                    status_code=400)
            # Offline-replay idempotency: recording an already-recorded
            # slot with the same status is a success no-op; a different
            # status is a conflict (409-style error in the envelope).
            if admin.state != 'planned':
                if admin.state == status:
                    return self._prepare_json_response(data={
                        'admin_id': admin.id,
                        'state': admin.state,
                        'message': 'Already recorded',
                    })
                return self._prepare_json_response(
                    error='Conflict: administration already recorded '
                          'as %s' % admin.state,
                    status_code=409)
            notes = body.get('notes') or None
            if status == 'given':
                admin.action_record_given(
                    actual_datetime=self._parse_datetime(
                        body.get('actual_datetime')) or None,
                    dose_given=body.get('dose_given') or None,
                    witness_id=body.get('witness_id') or None,
                    notes=notes)
            elif status == 'not_given':
                admin.action_record_not_given(
                    body.get('reason_id'), notes=notes)
            else:
                admin.action_record_refused(
                    body.get('reason_id'), notes=notes)
            return self._prepare_json_response(data={
                'admin_id': admin.id,
                'state': admin.state,
                'message': 'Administration recorded',
            })
        except (UserError, ValidationError) as e:
            return self._prepare_json_response(
                error=str(e), status_code=400)
        except Exception as e:
            _logger.exception('eMAR record administration failed')
            return self._prepare_json_response(
                error=str(e), status_code=500)

    # ------------------------------------------------------------------
    # POST /health_pwa/api/fso/<id>/medications/prn — ad-hoc PRN dose
    # ------------------------------------------------------------------
    @http.route('/health_pwa/api/fso/<int:order_id>/medications/prn',
                type='http', auth='user', methods=['POST'], csrf=False)
    def create_prn_dose(self, order_id, **kwargs):
        if not self._check_api_access():
            return self._prepare_json_response(
                error='Access denied', status_code=403)
        try:
            body = self._read_json_body()
            if body is None:
                return self._prepare_json_response(
                    error='Invalid JSON body', status_code=400)
            fso = request.env['health.fieldservice.order'].browse(order_id)
            if not fso.exists():
                return self._prepare_json_response(
                    error='Booking not found', status_code=404)
            med_order = request.env['health.medication.order'].browse(
                int(body.get('order_id') or 0))
            if not med_order.exists():
                return self._prepare_json_response(
                    error='Medication order not found', status_code=404)
            admin = request.env['health.medication.administration'] \
                .create_prn_dose(med_order, fso=fso)
            return self._prepare_json_response(
                data=self._serialize_administration(admin))
        except (UserError, ValidationError) as e:
            return self._prepare_json_response(
                error=str(e), status_code=400)
        except Exception as e:
            _logger.exception('eMAR PRN dose failed')
            return self._prepare_json_response(
                error=str(e), status_code=500)

    # ------------------------------------------------------------------
    # GET /health_pwa/api/patients/<id>/medication_orders
    # ------------------------------------------------------------------
    @http.route('/health_pwa/api/patients/<int:patient_id>/medication_orders',
                type='http', auth='user', methods=['GET'], csrf=False)
    def patient_medication_orders(self, patient_id, **kwargs):
        if not self._check_api_access():
            return self._prepare_json_response(
                error='Access denied', status_code=403)
        try:
            patient = request.env['res.partner'].browse(patient_id)
            if not patient.exists():
                return self._prepare_json_response(
                    error='Patient not found', status_code=404)
            orders = request.env['health.medication.order'].search([
                ('client_id', '=', patient.id)])
            return self._prepare_json_response(data={
                'orders': [self._serialize_order(order)
                           for order in orders],
            })
        except Exception as e:
            _logger.exception('eMAR patient orders failed')
            return self._prepare_json_response(
                error=str(e), status_code=500)
