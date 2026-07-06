# -*- coding: utf-8 -*-
"""FHIR R4 HTTP facade (§C.4) — read + search only.

Auth is delegated to health_api_gateway's ``_gateway_authenticate`` (token →
(user, scopes)); routes are therefore ``auth='none'`` (metadata is public — no
PHI). All data queries run in an environment bound to the authenticated user
so existing record rules (catchment scoping) apply; only the audit-log write
uses sudo.
"""

import json
import logging

import werkzeug.exceptions

from odoo import http
from odoo.exceptions import AccessDenied, AccessError
from odoo.http import request

from odoo.addons.health_api_gateway.controllers.gateway import _gateway_authenticate

from ..capability import build_capability
from ..serializers import REGISTRY
from ..serializers.base import (
    FHIRError, FHIRForbidden, FHIRNotFound, FHIRUnauthorized,
    validate_resource, validation_enabled,
)

_logger = logging.getLogger(__name__)

FHIR_MIME = 'application/fhir+json; charset=utf-8'
BLANKET_READ_SCOPE = 'system/*.read'


class HealthFHIRController(http.Controller):

    # ------------------------------------------------------------------
    # Routes
    # ------------------------------------------------------------------

    @http.route('/fhir/r4/metadata', type='http', auth='public',
                methods=['GET'], csrf=False)
    def fhir_metadata(self, **kwargs):
        """CapabilityStatement — generated from the registry, no PHI."""
        statement = build_capability(request.env, self._base_url())
        return self._fhir_response(statement)

    @http.route('/fhir/r4/<string:rtype>', type='http', auth='none',
                methods=['GET'], csrf=False)
    def fhir_search(self, rtype, **kwargs):
        try:
            serializer = self._serializer_or_404(rtype)
            user = self._authenticate(serializer)
            env = request.env(user=user.id)  # record rules apply
            params = self._query_params()
            bundle, records = serializer.search_bundle(
                env, params, self._base_url())
            if validation_enabled(env):
                self._runtime_validate(bundle)
            self._audit(env, user, serializer, records, status=200)
            return self._fhir_response(bundle)
        except FHIRError as error:
            return self._error_response(error, rtype=rtype)

    @http.route('/fhir/r4/<string:rtype>/<int:rid>', type='http', auth='none',
                methods=['GET'], csrf=False)
    def fhir_read(self, rtype, rid, **kwargs):
        try:
            serializer = self._serializer_or_404(rtype)
            user = self._authenticate(serializer)
            env = request.env(user=user.id)  # record rules apply
            record = serializer.read_record(env, rid)
            if not record:
                raise FHIRNotFound(
                    'No %s resource with id %s' % (rtype, rid))
            resource = serializer.serialize_batch(record)[0]
            if validation_enabled(env):
                self._runtime_validate(resource)
            self._audit(env, user, serializer, record, status=200)
            return self._fhir_response(resource)
        except FHIRError as error:
            return self._error_response(error, rtype=rtype)

    # ------------------------------------------------------------------
    # Auth / audit
    # ------------------------------------------------------------------

    def _serializer_or_404(self, rtype):
        serializer = REGISTRY.get(rtype)
        if serializer is None:
            raise FHIRNotFound('Unknown FHIR resource type: %r' % rtype)
        return serializer

    def _authenticate(self, serializer):
        """Gateway token → user; then enforce system/<Type>.read scope."""
        try:
            user, scopes = _gateway_authenticate(request)
        except FHIRError:
            raise
        except AccessDenied as exc:
            raise FHIRUnauthorized(str(exc) or 'Authentication required')
        except AccessError as exc:
            raise FHIRForbidden(str(exc) or 'Access denied')
        except werkzeug.exceptions.Unauthorized as exc:
            raise FHIRUnauthorized(exc.description or 'Authentication required')
        except werkzeug.exceptions.Forbidden as exc:
            raise FHIRForbidden(exc.description or 'Access denied')
        if not user:
            raise FHIRUnauthorized('Authentication required')
        scopes = set(scopes or ())
        if serializer.scope not in scopes and BLANKET_READ_SCOPE not in scopes:
            raise FHIRForbidden(
                'Token is missing scope %s' % serializer.scope)
        return user

    def _audit(self, env, user, serializer, records, status=200):
        """Every read/search is audited (write via sudo, never as the user)."""
        try:
            env['api.audit.log'].sudo().log_access(
                user_id=user.id,
                client=getattr(request, 'api_client', None),
                route=request.httprequest.path,
                method=request.httprequest.method,
                model=serializer.odoo_model,
                record_ids=records.ids,
                patient_ids=serializer.patient_ids_of(records),
                status=status,
            )
        except Exception:  # pragma: no cover — auditing must not break reads
            _logger.exception('FHIR audit logging failed for %s',
                              request.httprequest.path)

    # ------------------------------------------------------------------
    # Responses
    # ------------------------------------------------------------------

    def _base_url(self):
        return request.httprequest.url_root.rstrip('/')

    def _query_params(self):
        """Preserve repeated params: name -> list[str] (e.g. date=ge..&date=le..)."""
        args = request.httprequest.args
        return {name: args.getlist(name) for name in args.keys()}

    def _runtime_validate(self, payload):
        try:
            validate_resource(payload)
        except ImportError:
            _logger.warning('health_fhir_core.validate_responses is enabled '
                            'but fhir.resources is not installed')
        except Exception:
            _logger.exception('FHIR runtime validation failed on %s',
                              payload.get('resourceType'))

    def _fhir_response(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False, default=str)
        return request.make_response(
            body,
            headers=[('Content-Type', FHIR_MIME)],
            status=status,
        )

    def _error_response(self, error, rtype=None):
        _logger.info('FHIR %s error on %s: %s',
                     error.status, rtype or '?', error.diagnostics)
        return self._fhir_response(error.to_operation_outcome(),
                                   status=error.status)
