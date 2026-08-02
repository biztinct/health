# -*- coding: utf-8 -*-
"""FHIR R4 HTTP facade (§C.4) — read + search only.

Auth is delegated to health_api_gateway's ``_gateway_authenticate`` (token →
(user, scopes)); routes are therefore ``auth='none'`` (metadata is public — no
PHI). All data queries run in an environment bound to the authenticated user
so existing record rules (catchment scoping) apply; only the audit-log write
uses sudo.

The three data routes declare ``readonly=False`` even though every one of them
is a GET. An ``auth='none'`` route defaults to readonly in Odoo 19
(http.py:924), and these routes DO write: every read appends an
``api.audit.log`` row. The framework can normally recover — a
``ReadOnlySqlTransaction`` out of a readonly route makes it retry on a
read/write cursor — but ``_audit`` deliberately swallows every exception so
auditing can never break a read, which also swallows the signal the retry
depends on. The transaction is then poisoned and the caller gets a 500. Same
mechanism, same fix, as health_telemonitoring/controllers/ingest.py. This was
invisible on a deployment with no read replica (``cr.readonly`` is False
there, so the writes simply worked) and surfaced the moment GC-3 put an
``HttpCase`` on the route.
"""

import json
import logging

import werkzeug.exceptions

from odoo import http
from odoo.exceptions import AccessDenied, AccessError
from odoo.http import request

from odoo.addons.health_api_gateway.controllers.gateway import (
    _client_ip, _gateway_authenticate,
)

from ..capability import build_capability
from ..serializers import REGISTRY
from ..serializers.base import (
    FHIRError, FHIRForbidden, FHIRNotFound, FHIRUnauthorized,
    consent_allowed_records, consent_enforced,
    validate_resource, validation_enabled, validation_sample_hit,
)
from ..serializers.everything import build_everything_bundle

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
                methods=['GET'], csrf=False, readonly=False)
    def fhir_search(self, rtype, **kwargs):
        try:
            serializer = self._serializer_or_404(rtype)
            user = self._authenticate(serializer)
            env = request.env(user=user.id)  # record rules apply
            params = self._query_params()
            # Consent gate (architecture §6.6): drop un-consented patients'
            # resources from the page before serialization (log-only unless
            # health_fhir_core.consent_enforced). Every check is audited.
            enforced = consent_enforced(env)
            bundle, records = serializer.search_bundle(
                env, params, self._base_url(),
                record_filter=lambda recs: consent_allowed_records(
                    env, serializer, recs, enforced))
            if self._should_validate(env):
                self._runtime_validate(bundle)
            self._audit(env, user, serializer, records, status=200)
            return self._fhir_response(bundle)
        except FHIRError as error:
            return self._error_response(error, rtype=rtype)
        except AccessError as error:
            return self._access_denied_response(error, rtype)

    @http.route('/fhir/r4/Patient/<int:rid>/$everything', type='http',
                auth='none', methods=['GET'], csrf=False, readonly=False)
    def fhir_patient_everything(self, rid, **kwargs):
        """Patient/$everything — the whole clinical record in ONE
        consent-gated searchset Bundle (Patient first, then the patient's
        compartment). Composes the existing serializers; runs under the
        caller's env (record rules) with a single whole-record data_sharing
        consent decision. See serializers/everything.py."""
        try:
            serializer = self._serializer_or_404('Patient')
            user = self._authenticate(serializer)
            env = request.env(user=user.id)  # record rules apply
            params = self._query_params()
            bundle, patient_record = build_everything_bundle(
                env, rid, params, self._base_url())
            if self._should_validate(env):
                self._runtime_validate(bundle)
            self._audit(env, user, serializer, patient_record, status=200)
            return self._fhir_response(bundle)
        except FHIRError as error:
            return self._error_response(error, rtype='Patient')
        except AccessError as error:
            return self._access_denied_response(error, 'Patient')

    @http.route('/fhir/r4/<string:rtype>/<int:rid>', type='http', auth='none',
                methods=['GET'], csrf=False, readonly=False)
    def fhir_read(self, rtype, rid, **kwargs):
        try:
            serializer = self._serializer_or_404(rtype)
            user = self._authenticate(serializer)
            env = request.env(user=user.id)  # record rules apply
            record = serializer.read_record(env, rid)
            if not record:
                raise FHIRNotFound(
                    'No %s resource with id %s' % (rtype, rid))
            # Consent gate: if enforced and the record's patient has no active
            # data_sharing consent, deny as 404 (do not reveal the resource
            # exists). Always audited; a no-op for non-PHI resources.
            if not consent_allowed_records(
                    env, serializer, record, consent_enforced(env)):
                raise FHIRNotFound(
                    'No %s resource with id %s' % (rtype, rid))
            resource = serializer.serialize_batch(record)[0]
            if self._should_validate(env):
                self._runtime_validate(resource)
            self._audit(env, user, serializer, record, status=200)
            return self._fhir_response(resource)
        except FHIRError as error:
            return self._error_response(error, rtype=rtype)
        except AccessError as error:
            return self._access_denied_response(error, rtype)

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
            # _gateway_authenticate stamped the caller's identity on
            # request.gateway_auth — same source the gateway's own audit rows
            # use (GC-2 review, M2: `request.api_client` never existed, so
            # every FHIR audit row had an empty key_or_client).
            auth = getattr(request, 'gateway_auth', {}) or {}
            env['api.audit.log'].sudo().log_access(
                user_id=user.id,
                client=auth.get('key_ref'),
                route=request.httprequest.path,
                method=request.httprequest.method,
                model=serializer.odoo_model,
                record_ids=records.ids,
                patient_ids=serializer.patient_ids_of(records),
                status=status,
                ip=_client_ip(),
                auth_kind=auth.get('auth_kind'),
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

    def _should_validate(self, env):
        """Runtime validation decision for THIS response (control C4 / G10).

        `validate_responses` validates everything (staging); otherwise the
        canary client and the sampling percentage decide. The client label is
        the same one the audit row carries, so "which client drifted" and
        "which client was sampled" are answerable from the same identifier."""
        auth = getattr(request, 'gateway_auth', {}) or {}
        return (validation_enabled(env)
                or validation_sample_hit(env, auth.get('key_ref')))

    def _runtime_validate(self, payload):
        """Detect conformance drift; NEVER surface it to the caller.

        A facade that 500s because its own validator disagrees with it has
        converted a monitoring control into an outage — so every failure is
        logged and swallowed. `FHIR-CONFORMANCE-DRIFT` is the grep key
        (docs/conformance/deploy-smoke.md)."""
        try:
            validate_resource(payload)
        except ImportError:
            _logger.warning('FHIR runtime validation is enabled but '
                            'fhir.resources is not installed')
        except Exception as error:  # noqa: BLE001 — see docstring
            _logger.error('FHIR-CONFORMANCE-DRIFT rtype=%s id=%s: %s',
                          payload.get('resourceType'), payload.get('id'),
                          error)

    def _fhir_response(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False, default=str)
        return request.make_response(
            body,
            headers=[('Content-Type', FHIR_MIME)],
            status=status,
        )

    def _access_denied_response(self, error, rtype):
        """An ORM ``AccessError`` raised INSIDE a search or read is a FHIR
        403, not Odoo's HTML error page.

        ``_authenticate`` already translates the gateway's AccessError, but an
        access failure from the query itself escaped every handler: a token
        whose service user is missing ONE model's ``ir.model.access`` row got
        ``<!doctype html><title>403 Forbidden</title>`` back from a FHIR
        endpoint — unparseable by any FHIR client, and naming the Odoo user in
        the body. Same class of integration-breaking defect as G14/G15, and
        found by the GC-3 deploy smoke on its first authenticated run.

        The diagnostic names the FHIR resource type, never the Odoo model or
        the ACL rule: enough for an integrator to know which scope to ask for,
        nothing about the internals. The full error is logged server-side.
        """
        _logger.info('FHIR 403 (AccessError) on %s: %s', rtype, error)
        return self._error_response(
            FHIRForbidden('Access to %s is not permitted for this token'
                          % rtype),
            rtype=rtype)

    def _error_response(self, error, rtype=None):
        _logger.info('FHIR %s error on %s: %s',
                     error.status, rtype or '?', error.diagnostics)
        return self._fhir_response(error.to_operation_outcome(),
                                   status=error.status)
