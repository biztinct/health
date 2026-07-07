# -*- coding: utf-8 -*-
"""FHIR terminology operations: CodeSystem/$lookup + ValueSet/$expand.

Reuses health_fhir_core's gateway auth + OperationOutcome plumbing exactly.
The `$lookup` / `$expand` literals are not int-convertible, so they are not
shadowed by health_fhir_core's `/fhir/r4/<rtype>/<int:rid>` read route
(verified with a live curl — see the phase report)."""

import json
import logging

import werkzeug.exceptions

from odoo import http
from odoo.exceptions import AccessDenied, AccessError
from odoo.http import request

from odoo.addons.health_api_gateway.controllers.gateway import (
    _gateway_authenticate,
)
from odoo.addons.health_fhir_core.serializers.base import (
    FHIRError, FHIRBadRequest, FHIRForbidden, FHIRNotFound, FHIRUnauthorized,
)

_logger = logging.getLogger(__name__)

FHIR_MIME = 'application/fhir+json; charset=utf-8'
BLANKET_READ_SCOPE = 'system/*.read'


class HealthTerminologyController(http.Controller):

    @http.route('/fhir/r4/CodeSystem/$lookup', type='http', auth='none',
                methods=['GET'], csrf=False)
    def codesystem_lookup(self, **kwargs):
        try:
            user = self._authenticate('system/CodeSystem.read')
            env = request.env(user=user.id)  # record rules apply
            system = kwargs.get('system')
            code = kwargs.get('code')
            if not system or not code:
                raise FHIRBadRequest(
                    "Both 'system' and 'code' parameters are required")
            payload = env['medical.code'].fhir_lookup(system, code)
            if payload is None:
                raise FHIRNotFound(
                    'No code %r found in system %r' % (code, system))
            return self._fhir_response(payload)
        except FHIRError as error:
            return self._error_response(error)

    @http.route('/fhir/r4/ValueSet/$expand', type='http', auth='none',
                methods=['GET'], csrf=False)
    def valueset_expand(self, **kwargs):
        try:
            user = self._authenticate('system/ValueSet.read')
            env = request.env(user=user.id)  # record rules apply
            url = kwargs.get('url')
            if not url:
                raise FHIRBadRequest("The 'url' parameter is required")
            payload = env['medical.code'].fhir_expand(
                url, filter_text=kwargs.get('filter'),
                count=kwargs.get('count') or 20)
            if payload is None:
                raise FHIRNotFound('Unknown ValueSet system url %r' % url)
            return self._fhir_response(payload)
        except FHIRError as error:
            return self._error_response(error)

    # ------------------------------------------------------------------
    # Auth / responses (mirrors health_fhir_core/controllers/fhir.py)
    # ------------------------------------------------------------------
    def _authenticate(self, scope):
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
        if scope not in scopes and BLANKET_READ_SCOPE not in scopes:
            raise FHIRForbidden('Token is missing scope %s' % scope)
        return user

    def _fhir_response(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False, default=str)
        return request.make_response(
            body, headers=[('Content-Type', FHIR_MIME)], status=status)

    def _error_response(self, error):
        _logger.info('FHIR terminology %s error: %s',
                     error.status, error.diagnostics)
        return self._fhir_response(error.to_operation_outcome(),
                                   status=error.status)
