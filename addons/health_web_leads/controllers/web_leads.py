# -*- coding: utf-8 -*-
"""``POST /api/v1/web/leads`` — the website-submission capture endpoint.

Thin by design: authenticate → scope → rate limit → parse → hand the payload
to ``web.lead.service.process_submission`` → envelope → audit. All of the
business rules live in the service model so they are testable without HTTP.

WHY NOT ``@api_route`` (ledger §5.38, and the one deviation from the phase
handover): Odoo 17.3+ runs every HTTP request on a READONLY cursor first and
only retries on a read/write cursor if ``psycopg2.errors.ReadOnlySqlTransaction``
propagates all the way up to ``service.model.retrying``. The gateway
decorator wraps its handler in ``except Exception: return 500-envelope``,
which CATCHES that signal — so the retry never fires and the first write in
any decorated endpoint dies as a generic 500. This endpoint's whole purpose is
to write. It therefore declares ``readonly=False`` (read/write cursor from the
start) and IMPORTS the gateway's auth/scope/envelope/audit helpers — the same
documented interface ``health_fhir_core`` and ``health_telemonitoring``
already import, so no gateway code is edited. The route is registered into
the OpenAPI registry by hand for the same reason.
"""
import json
import logging
import time

import werkzeug.exceptions

from odoo import _, http
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request

from odoo.addons.health_api_gateway.api_registry import register_route
from odoo.addons.health_api_gateway.controllers.gateway import (
    ApiError, _client_ip, _envelope_response, _gateway_authenticate,
    _scopes_satisfied, _write_audit_row)

_logger = logging.getLogger(__name__)

REQUIRED_SCOPE = 'web_lead.write'
ROUTE = '/api/v1/web/leads'
# Design §5.1. A contact-form submission is a few kilobytes; anything past
# this is either a bug or an attempt to fill the touchpoint table.
MAX_BODY_BYTES = 64 * 1024

register_route({
    'path': ROUTE,
    'methods': ['POST'],
    'scopes': (REQUIRED_SCOPE,),
    'summary': 'Capture a website contact-form submission as a CRM lead',
    'request_model': {'required': ['submission_id', 'form_id']},
    'response_model': None,
    'tags': ('web leads',),
    'fn_qualname': 'HealthWebLeadsController.capture_web_lead',
})


class HealthWebLeadsController(http.Controller):

    @http.route(ROUTE, type='http', auth='public', methods=['POST'],
                csrf=False, save_session=False, readonly=False)
    def capture_web_lead(self, **kwargs):
        start = time.monotonic()
        status_code = 200
        auth_info = {}
        user = None
        audit = {}
        try:
            # -- 1. Authenticate → scope → rate limit ------------------
            try:
                user, granted = _gateway_authenticate(request)
            except werkzeug.exceptions.Unauthorized as exc:
                status_code = 401
                return _envelope_response(
                    error=exc.description or _('Unauthorized'),
                    status_code=401)
            auth_info = getattr(request, 'gateway_auth', {}) or {}
            if not _scopes_satisfied((REQUIRED_SCOPE,), granted):
                status_code = 403
                return _envelope_response(
                    error=_('Token is missing a required scope (%s)',
                            REQUIRED_SCOPE),
                    status_code=403)
            allowed, retry_after = request.env['gateway.rate.counter'].sudo(
            ).hit(auth_info.get('rate_key') or 'web-leads:anonymous')
            if not allowed:
                status_code = 429
                return _envelope_response(
                    error=_('Rate limit exceeded'), status_code=429,
                    extra_headers=[('Retry-After', str(retry_after))])
            # Run the ORM as the service user so record rules apply.
            request.update_env(user=user.id)

            # -- 2. Parse the body -------------------------------------
            raw = request.httprequest.data or b''
            if len(raw) > MAX_BODY_BYTES:
                status_code = 400
                return _envelope_response(
                    error=_('Request body too large'), status_code=400)
            try:
                payload = json.loads(raw.decode('utf-8')) if raw else {}
            except (ValueError, UnicodeDecodeError):
                status_code = 400
                return _envelope_response(
                    error=_('Request body is not valid JSON'),
                    status_code=400)
            if not isinstance(payload, dict):
                status_code = 422
                return _envelope_response(
                    error=_('Request body must be a JSON object'),
                    status_code=422)
            missing = [key for key in ('submission_id', 'form_id')
                       if not payload.get(key)]
            if missing:
                status_code = 422
                return _envelope_response(
                    error=_('Missing required field(s): %s',
                            ', '.join(missing)),
                    status_code=422)

            # -- 3. Hand off -------------------------------------------
            data = request.env['web.lead.service'].process_submission(payload)
            audit['model'] = 'crm.lead'
            return _envelope_response(data=data, status_code=200)
        except ApiError as exc:
            status_code = exc.status_code
            return _envelope_response(error=exc.message,
                                      status_code=exc.status_code)
        except (UserError, ValidationError, AccessError) as exc:
            # Review M1: without this tier (the decorator has it at
            # gateway.py:334-337) an ORM refusal would surface as a 500 and
            # the WP relay — which re-queues only on 5xx — would retry the
            # same doomed submission forever.
            status_code = 403 if isinstance(exc, AccessError) else 400
            return _envelope_response(error=str(exc), status_code=status_code)
        except Exception:  # noqa: BLE001 — envelope, never a stack page
            status_code = 500
            _logger.exception('web_leads: unhandled error in %s', ROUTE)
            return _envelope_response(error=_('Internal server error'),
                                      status_code=500)
        finally:
            # Same append-only audit row the @api_route decorator writes, on a
            # fresh cursor so it survives a rolled-back request. Bodies are
            # never logged (design §10).
            _write_audit_row(request.db, {
                'user_id': user.id if user is not None else None,
                'client': auth_info.get('key_ref'),
                'route': request.httprequest.path,
                'method': request.httprequest.method,
                'model': audit.get('model'),
                'record_ids': None,
                'patient_ids': None,
                'status': status_code,
                'latency_ms': int((time.monotonic() - start) * 1000),
                'ip': _client_ip(),
                'auth_kind': auth_info.get('auth_kind'),
            })
