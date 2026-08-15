# -*- coding: utf-8 -*-
"""Consent PWA endpoints (clinical spec §6.7).

Matches health_pwa conventions exactly: type='http', auth='user',
csrf=False, manual json.loads(request.httprequest.data), and the same
response envelope {success, timestamp, data|error}. The envelope/auth
helpers are deliberately DUPLICATED from health_pwa/controllers/api.py
(existing convention — api.py and sync.py both do it).

Soft enforcement note (spec §6.8.1): this module does NOT patch the
existing /health_pwa/api/fso/<id>/upload_image route (owned by
health_pwa). The PWA client checks status.photography before opening
the camera for clinical photos; server-side hard enforcement lands
with the api-gateway phase.
"""
import base64
import json
import logging

from odoo import _, fields, http
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request

_logger = logging.getLogger(__name__)

CONSENT_TYPES = ('service', 'data_sharing', 'photography',
                 'emergency_treatment', 'marketing')


class HealthConsentPWAController(http.Controller):
    """Consent endpoints under the PWA API namespace."""

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

    def _serialize_consent(self, consent):
        if consent.self_granted:
            granted_by = 'self'
        else:
            granted_by = {
                'name': consent.granted_by_partner_id.name or '',
                'role': consent.granted_by_role or '',
            }
        return {
            'id': consent.id,
            'name': consent.name,
            'consent_type': consent.consent_type_code,
            'state': consent.state,
            'method': consent.method,
            'effective_date': (
                fields.Date.to_string(consent.effective_date)
                if consent.effective_date else None),
            'expiry_date': (
                fields.Date.to_string(consent.expiry_date)
                if consent.expiry_date else None),
            'granted_by': granted_by,
            'scope_note': consent.scope_note or '',
        }

    def _selection_labels(self, field_name):
        """[(value, label_en, label_vi)] for a health.consent
        selection field."""
        Consent = request.env['health.consent']
        selection_en = Consent._fields[field_name] \
            ._description_selection(Consent.env)
        ConsentVi = Consent.with_context(lang='vi_VN')
        selection_vi = dict(ConsentVi._fields[field_name]
                            ._description_selection(ConsentVi.env))
        return [{
            'value': value,
            'label': label,
            'label_vi': selection_vi.get(value, label),
        } for value, label in selection_en]

    # ------------------------------------------------------------------
    # GET /health_pwa/api/patients/<id>/consents
    # ------------------------------------------------------------------
    @http.route('/health_pwa/api/patients/<int:patient_id>/consents',
                type='http', auth='user', methods=['GET'], csrf=False)
    def patient_consents(self, patient_id, **kwargs):
        if not self._check_api_access():
            return self._prepare_json_response(
                error=_('Access denied'), status_code=403)
        try:
            patient = request.env['res.partner'].browse(patient_id)
            if not patient.exists():
                return self._prepare_json_response(
                    error=_('Patient not found'), status_code=404)
            consents = request.env['health.consent'].search([
                ('client_id', '=', patient.id),
            ], order='create_date desc')
            status = request.env['health.consent'].with_context(
                consent_check_source='pwa').check_consents(
                    patient.id, list(CONSENT_TYPES))
            relations = request.env['health.client.relation'].search([
                ('client_id', '=', patient.id),
            ])
            return self._prepare_json_response(data={
                'consents': [self._serialize_consent(consent)
                             for consent in consents],
                'status': status,
                'relations': [{
                    'id': relation.id,
                    'representative_name':
                        relation.representative_id.name or '',
                    'role': relation.role,
                    'relationship_type':
                        relation.relationship_type or '',
                } for relation in relations],
            })
        except Exception as exc:  # noqa: BLE001
            return self._prepare_json_response(
                error=str(exc), status_code=500)

    # ------------------------------------------------------------------
    # POST /health_pwa/api/patients/<id>/consents
    # ------------------------------------------------------------------
    @http.route('/health_pwa/api/patients/<int:patient_id>/consents',
                type='http', auth='user', methods=['POST'], csrf=False)
    def patient_consent_create(self, patient_id, **kwargs):
        if not self._check_api_access():
            return self._prepare_json_response(
                error=_('Access denied'), status_code=403)
        try:
            body = self._read_json_body()
            if body is None:
                return self._prepare_json_response(
                    error=_('Invalid JSON body'), status_code=400)
            patient = request.env['res.partner'].browse(patient_id)
            if not patient.exists():
                return self._prepare_json_response(
                    error=_('Patient not found'), status_code=404)
            Consent = request.env['health.consent']
            # Idempotent offline replay (interop §6.7): same
            # client_mutation_id → return the existing record, no-op.
            mutation_id = (body.get('client_mutation_id') or '').strip()
            if mutation_id:
                existing = Consent.search([
                    ('client_mutation_id', '=', mutation_id),
                ], limit=1)
                if existing:
                    return self._prepare_json_response(data={
                        'consent_id': existing.id,
                        'name': existing.name,
                        'state': existing.state,
                        'message': _('Consent already recorded '
                                     '(idempotent replay)'),
                    })
            consent_type = body.get('consent_type')
            if consent_type not in CONSENT_TYPES:
                return self._prepare_json_response(
                    error=_('Invalid consent_type: %s') % consent_type,
                    status_code=400)
            vals = {
                'client_id': patient.id,
                'consent_type_id': request.env['health.lookup.value']
                ._default_for('consent_type', consent_type),
                'method': body.get('method') or 'verbal',
                'self_granted': bool(body.get('self_granted', True)),
                'scope_note': body.get('scope_note') or False,
                'notes': body.get('notes') or False,
                'client_mutation_id': mutation_id or False,
            }
            if body.get('granted_by_relation_id'):
                vals['granted_by_relation_id'] = int(
                    body['granted_by_relation_id'])
            if body.get('effective_date'):
                vals['effective_date'] = body['effective_date']
            if body.get('expiry_date'):
                vals['expiry_date'] = body['expiry_date']
            signature_b64 = body.get('signature_base64')
            if signature_b64:
                # Validate the base64 payload before storing.
                base64.b64decode(signature_b64)
                vals['signature'] = signature_b64
            consent = Consent.create(vals)
            # One round trip: draft → active (supersede semantics
            # apply inside action_grant).
            consent.action_grant()
            return self._prepare_json_response(data={
                'consent_id': consent.id,
                'name': consent.name,
                'state': consent.state,
                'message': _('Consent granted'),
            })
        except (UserError, ValidationError, AccessError) as exc:
            return self._prepare_json_response(
                error=str(exc), status_code=400)
        except Exception as exc:  # noqa: BLE001
            _logger.exception(
                'Consent creation failed for patient %s', patient_id)
            return self._prepare_json_response(
                error=str(exc), status_code=500)

    # ------------------------------------------------------------------
    # POST /health_pwa/api/consents/<id>/withdraw
    # ------------------------------------------------------------------
    @http.route('/health_pwa/api/consents/<int:consent_id>/withdraw',
                type='http', auth='user', methods=['POST'], csrf=False)
    def consent_withdraw(self, consent_id, **kwargs):
        if not self._check_api_access():
            return self._prepare_json_response(
                error=_('Access denied'), status_code=403)
        try:
            body = self._read_json_body()
            if body is None:
                return self._prepare_json_response(
                    error=_('Invalid JSON body'), status_code=400)
            consent = request.env['health.consent'].browse(consent_id)
            if not consent.exists():
                return self._prepare_json_response(
                    error=_('Consent not found'), status_code=404)
            reason = (body.get('reason') or '').strip()
            if not reason:
                return self._prepare_json_response(
                    error=_('Withdrawal reason is required'),
                    status_code=400)
            consent.with_context(
                withdrawal_reason=reason).action_withdraw()
            return self._prepare_json_response(data={
                'consent_id': consent.id,
                'state': consent.state,
            })
        except (UserError, ValidationError, AccessError) as exc:
            return self._prepare_json_response(
                error=str(exc), status_code=400)
        except Exception as exc:  # noqa: BLE001
            _logger.exception(
                'Consent withdrawal failed for %s', consent_id)
            return self._prepare_json_response(
                error=str(exc), status_code=500)

    # ------------------------------------------------------------------
    # GET /health_pwa/api/consents/types
    # ------------------------------------------------------------------
    @http.route('/health_pwa/api/consents/types',
                type='http', auth='user', methods=['GET'], csrf=False)
    def consent_types(self, **kwargs):
        if not self._check_api_access():
            return self._prepare_json_response(
                error=_('Access denied'), status_code=403)
        try:
            return self._prepare_json_response(data={
                'types': self._selection_labels('consent_type'),
                'methods': self._selection_labels('method'),
            })
        except Exception as exc:  # noqa: BLE001
            return self._prepare_json_response(
                error=str(exc), status_code=500)
