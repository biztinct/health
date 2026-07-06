# -*- coding: utf-8 -*-
"""Gateway middleware: ``@api_route`` decorator, ``_gateway_authenticate``,
audit helper, OpenAPI + docs endpoints.

Interface contract (health_fhir_core imports these):
- ``from odoo.addons.health_api_gateway.controllers.gateway import api_route``
- ``from odoo.addons.health_api_gateway.controllers.gateway import _gateway_authenticate``
- ``log_api_access(env, ...)`` helper
"""
import functools
import ipaddress
import json
import logging
import time

import werkzeug.exceptions

from odoo import SUPERUSER_ID, _, api as odoo_api, fields, http
from odoo.exceptions import AccessDenied, AccessError, UserError, ValidationError
from odoo.http import request
from odoo.modules.registry import Registry

from ..api_registry import build_openapi, register_route

_logger = logging.getLogger(__name__)

GATEWAY_TOKEN_PREFIX = 'hg_'


class ApiError(Exception):
    """Raised by /api/v1 handlers to return an error envelope."""

    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


# ---------------------------------------------------------------------------
# Envelope — same shape as HealthPWAAPIController._prepare_json_response
# (health_pwa/controllers/api.py:41) so PWA client code ports 1:1.
# ---------------------------------------------------------------------------
def _envelope_response(data=None, error=None, status_code=200, extra_headers=None):
    response_data = {
        'success': error is None,
        'timestamp': fields.Datetime.now().isoformat(),
    }
    if error is not None:
        response_data['error'] = error
    else:
        response_data['data'] = data
    headers = [
        ('Content-Type', 'application/json; charset=utf-8'),
        ('Cache-Control', 'no-cache, no-store, must-revalidate'),
        ('Access-Control-Allow-Origin', '*'),
        ('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS'),
        ('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Requested-With'),
    ]
    if extra_headers:
        headers.extend(extra_headers)
    return request.make_response(
        json.dumps(response_data, default=str, ensure_ascii=False, indent=2),
        headers=headers,
        status=status_code,
    )


def _su_env():
    """Superuser environment on the request cursor (routes are auth='none',
    so request.env.uid may be None)."""
    return odoo_api.Environment(request.env.cr, SUPERUSER_ID, {})


def _client_ip():
    forwarded = request.httprequest.headers.get('X-Forwarded-For', '')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.httprequest.remote_addr or ''


def _ip_allowed(ip, allowlist):
    """`allowlist`: comma-separated CIDRs; empty = any."""
    if not (allowlist or '').strip():
        return True
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    for cidr in allowlist.split(','):
        cidr = cidr.strip()
        if not cidr:
            continue
        try:
            if addr in ipaddress.ip_network(cidr, strict=False):
                return True
        except ValueError:
            continue
    return False


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
def _gateway_authenticate(req):
    """Resolve the Bearer credential of `req` (odoo.http.request).

    Returns ``(user, scopes: set)`` — scope names include patterns like
    'booking.read' and 'system/Patient.read' — or raises
    ``werkzeug.exceptions.Unauthorized``.

    Resolution order (spec B.3):
    - ``hg_`` prefixed token -> gateway.token store
    - otherwise -> Odoo res.users.apikeys (guarded: implementations differ)
    - session cookie fallback for ``/api/v1/pwa/*`` routes only
    """
    env = _su_env()
    req.gateway_auth = {'auth_kind': None, 'key_ref': None, 'rate_key': None}

    header = req.httprequest.headers.get('Authorization', '')
    token = ''
    if header.lower().startswith('bearer '):
        token = header[7:].strip()

    if token.startswith(GATEWAY_TOKEN_PREFIX):
        resolved = env['gateway.token'].sudo().resolve(token)
        if not resolved:
            raise werkzeug.exceptions.Unauthorized(
                _('Invalid or expired access token'))
        user = env['res.users'].browse(resolved['user_id'])
        req.gateway_auth.update({
            'auth_kind': 'oauth',
            'key_ref': resolved.get('client_code') or str(resolved.get('client_id')),
            'rate_key': 'oauth:%s' % (resolved.get('client_code')
                                      or resolved.get('client_id')),
        })
        return user, resolved['scope_names']

    if token:
        user, scopes, key_ref = _check_odoo_apikey(env, token)
        if user is not None:
            req.gateway_auth.update({
                'auth_kind': 'apikey',
                'key_ref': key_ref,
                'rate_key': 'apikey:%s' % key_ref,
            })
            return user, scopes
        raise werkzeug.exceptions.Unauthorized(_('Invalid API key'))

    # Session cookie fallback — /api/v1/pwa/* routes only (PWA migration path)
    path = req.httprequest.path or ''
    if path.startswith('/api/v1/pwa/'):
        session_uid = req.session.uid if req.session else None
        if session_uid:
            user = env['res.users'].browse(session_uid)
            if user.exists() and user.active:
                req.gateway_auth.update({
                    'auth_kind': 'session',
                    'key_ref': 'session',
                    'rate_key': 'session:%s' % session_uid,
                })
                return user, {'pwa.read', 'pwa.write'}

    raise werkzeug.exceptions.Unauthorized(_('Missing Bearer credentials'))


def _check_odoo_apikey(env, token):
    """VERIFY-fallback per spec: use core res.users.apikeys._check_credentials
    when present (signatures vary across Odoo versions — guarded), then load
    gateway fields (active, ip allowlist, scopes, expiry) from the key row.

    Returns (user, scopes, key_ref) or (None, None, None)."""
    Apikeys = env['res.users.apikeys'].sudo()
    uid = None
    if hasattr(Apikeys, '_check_credentials'):
        for kwargs in ({'scope': 'rpc', 'key': token}, {'key': token}):
            try:
                uid = Apikeys._check_credentials(**kwargs)
                break
            except TypeError:
                continue
            except (AccessDenied, Exception):
                uid = None
                break
    if not uid:
        return None, None, None

    # Locate the specific key row: core stores an 8-char `index` prefix.
    key = Apikeys.browse()
    if 'index' in Apikeys._fields:
        key = Apikeys.search([('index', '=', token[:8]),
                              ('user_id', '=', uid)], limit=1)
    if not key:
        key = Apikeys.search([('user_id', '=', uid)], limit=1)

    if key:
        if 'gateway_active' in key._fields and not key.gateway_active:
            return None, None, None
        expiration = getattr(key, 'expiration_date', False) \
            or getattr(key, 'expiry_date', False)
        if expiration and expiration <= fields.Datetime.now():
            return None, None, None
        if not _ip_allowed(_client_ip(), getattr(key, 'ip_allowlist', '') or ''):
            return None, None, None

    user = env['res.users'].browse(uid)
    if not user.exists() or not user.active:
        return None, None, None
    scopes = set(key.scope_ids.mapped('code')) if key else set()
    return user, scopes, str(key.id) if key else 'apikey'


def _scopes_satisfied(required, granted):
    """Any-of scope check. `system/*.read` in the grant satisfies any
    `system/<Type>.read` requirement (SMART wildcard)."""
    if not required:
        return True
    granted = set(granted or ())
    for scope in required:
        if scope in granted:
            return True
        if (scope.startswith('system/') and scope.endswith('.read')
                and 'system/*.read' in granted):
            return True
    return False


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------
def log_api_access(env, user_id=None, client=None, route=None, method=None,
                   model=None, record_ids=None, patient_ids=None, status=None,
                   latency_ms=None, ip=None, auth_kind=None):
    """Helper for other modules (health_fhir_core) to append audit rows."""
    return env['api.audit.log'].sudo().log_access(
        user_id=user_id, client=client, route=route, method=method,
        model=model, record_ids=record_ids, patient_ids=patient_ids,
        status=status, latency_ms=latency_ms, ip=ip, auth_kind=auth_kind)


def _write_audit_row(dbname, values):
    """Write the audit row with a FRESH cursor so it survives request
    rollback (spec B.3 step 8)."""
    try:
        with Registry(dbname).cursor() as cr:
            env = odoo_api.Environment(cr, SUPERUSER_ID, {})
            env['api.audit.log'].log_access(**values)
    except Exception:
        _logger.exception('Failed to write api.audit.log row for %s',
                          values.get('route'))


# ---------------------------------------------------------------------------
# @api_route decorator (spec B.3)
# ---------------------------------------------------------------------------
def api_route(path, methods=('GET',), scopes=(), summary='', request_model=None,
              response_model=None, tags=(), auth='gateway'):
    """Gateway route decorator. Wraps ``odoo.http.route(type='http',
    auth='none', csrf=False, save_session=False)`` and, in order:
    authenticate -> scope check -> rate check -> switch env to the service
    user -> parse/validate JSON body -> call handler -> envelope -> audit.

    The handler returns the ``data`` dict (or raises :class:`ApiError`);
    POST/PUT bodies are passed as the ``payload`` kwarg.
    """
    method_list = [m.upper() for m in methods]

    def decorator(fn):
        register_route({
            'path': path,
            'methods': method_list,
            'scopes': tuple(scopes),
            'summary': summary or (fn.__doc__ or '').strip().split('\n')[0],
            'request_model': request_model,
            'response_model': response_model,
            'tags': tuple(tags),
            'fn_qualname': fn.__qualname__,
        })

        @functools.wraps(fn)
        def wrapper(ctrl, *args, **kwargs):
            start = time.monotonic()
            status_code = 200
            request.gateway_audit = {}
            auth_info = {}
            user = None
            try:
                if auth == 'gateway':
                    try:
                        user, granted = _gateway_authenticate(request)
                    except werkzeug.exceptions.Unauthorized as exc:
                        status_code = 401
                        return _envelope_response(
                            error=exc.description or _('Unauthorized'),
                            status_code=401)
                    auth_info = getattr(request, 'gateway_auth', {}) or {}
                    if not _scopes_satisfied(scopes, granted):
                        status_code = 403
                        return _envelope_response(
                            error=_('Token is missing a required scope (%s)',
                                    ', '.join(scopes)),
                            status_code=403)
                    allowed, retry_after = _su_env()['gateway.rate.counter'].hit(
                        auth_info.get('rate_key') or 'anonymous')
                    if not allowed:
                        status_code = 429
                        return _envelope_response(
                            error=_('Rate limit exceeded'),
                            status_code=429,
                            extra_headers=[('Retry-After', str(retry_after))])
                    # Switch to the service user so record rules apply.
                    request.update_env(user=user.id)

                if request.httprequest.method in ('POST', 'PUT', 'PATCH'):
                    raw = request.httprequest.data
                    try:
                        payload = json.loads(raw.decode('utf-8')) if raw else {}
                    except (ValueError, UnicodeDecodeError):
                        status_code = 400
                        return _envelope_response(
                            error=_('Request body is not valid JSON'),
                            status_code=400)
                    error = _validate_payload(payload, request_model)
                    if error:
                        status_code = 422
                        return _envelope_response(error=error, status_code=422)
                    kwargs['payload'] = payload

                data = fn(ctrl, *args, **kwargs)
                return _envelope_response(data=data, status_code=200)
            except ApiError as exc:
                status_code = exc.status_code
                return _envelope_response(error=exc.message,
                                          status_code=exc.status_code)
            except (UserError, ValidationError, AccessError) as exc:
                status_code = 400 if not isinstance(exc, AccessError) else 403
                return _envelope_response(
                    error=str(exc), status_code=status_code)
            except Exception as exc:
                status_code = 500
                _logger.exception('Unhandled error in %s', path)
                return _envelope_response(error=str(exc), status_code=500)
            finally:
                audit = getattr(request, 'gateway_audit', {}) or {}
                _write_audit_row(request.db, {
                    'user_id': user.id if user is not None else None,
                    'client': auth_info.get('key_ref'),
                    'route': request.httprequest.path,
                    'method': request.httprequest.method,
                    'model': audit.get('model'),
                    'record_ids': audit.get('record_ids'),
                    'patient_ids': audit.get('patient_ids'),
                    'status': status_code,
                    'latency_ms': int((time.monotonic() - start) * 1000),
                    'ip': _client_ip(),
                    'auth_kind': auth_info.get('auth_kind'),
                })

        return http.route(path, type='http', auth='none', csrf=False,
                          methods=method_list, save_session=False)(wrapper)
    return decorator


def _validate_payload(payload, request_model):
    """Validate a parsed JSON body against the request schema. Supports
    pydantic v2 models and plain JSON-schema dict fragments (required keys
    only). Returns an error message or None."""
    if request_model is None:
        return None
    if not isinstance(payload, dict):
        return _('Request body must be a JSON object')
    validator = getattr(request_model, 'model_validate', None)
    if callable(validator):  # pydantic v2 class
        try:
            validator(payload)
            return None
        except Exception as exc:
            return str(exc)
    if isinstance(request_model, dict):
        missing = [key for key in request_model.get('required', [])
                   if payload.get(key) in (None, '')]
        if missing:
            return _('Missing required field(s): %s', ', '.join(missing))
    return None


def _audit_touch(model=None, record_ids=None, patient_ids=None):
    """Handlers call this to enrich the audit row of the current request."""
    audit = getattr(request, 'gateway_audit', None)
    if audit is None:
        audit = request.gateway_audit = {}
    if model:
        audit['model'] = model
    if record_ids is not None:
        audit['record_ids'] = record_ids
    if patient_ids is not None:
        audit['patient_ids'] = patient_ids


# ---------------------------------------------------------------------------
# OpenAPI + human docs
# ---------------------------------------------------------------------------
# v1 simplification of the spec's bundled Scalar/Redoc: a self-contained
# vanilla-JS page (no CDN assets — debranding posture) that fetches
# /api/v1/openapi.json and renders a readable endpoint list.
_DOCS_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>health19 API Docs</title>
<style>
  :root { --ink:#1f2933; --muted:#616e7c; --line:#e4e7eb; --accent:#0b6e4f; }
  * { box-sizing:border-box; }
  body { margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
         color:var(--ink); background:#fafbfc; }
  header { padding:24px 32px; background:#ffffff; border-bottom:1px solid var(--line); }
  h1 { margin:0; font-size:20px; font-weight:600; }
  header p { margin:6px 0 0; color:var(--muted); font-size:13px; }
  main { max-width:960px; margin:0 auto; padding:24px 32px 64px; }
  .ep { background:#ffffff; border:1px solid var(--line); border-radius:6px;
        margin-bottom:12px; padding:14px 18px; }
  .row { display:flex; align-items:center; gap:12px; flex-wrap:wrap; }
  .method { font-family:ui-monospace,Menlo,monospace; font-size:12px; font-weight:700;
            padding:2px 8px; border-radius:4px; color:#ffffff; background:var(--accent); }
  .method.post { background:#8d3b00; }
  .path { font-family:ui-monospace,Menlo,monospace; font-size:14px; }
  .summary { color:var(--muted); font-size:13px; margin-top:6px; }
  .scopes { margin-top:6px; font-size:12px; color:var(--muted); }
  .scopes code { background:#eef1f4; padding:1px 6px; border-radius:3px;
                 font-size:11px; margin-right:4px; }
  #status { color:var(--muted); font-size:14px; }
</style>
</head>
<body>
<header>
  <h1>health19 API Gateway</h1>
  <p>OpenAPI 3.1 &middot; <a href="/api/v1/openapi.json">/api/v1/openapi.json</a>
     &middot; auth: Bearer API key or OAuth2 client-credentials via POST /oauth/token</p>
</header>
<main>
  <p id="status">Loading endpoint list…</p>
  <div id="endpoints"></div>
</main>
<script>
(function () {
  fetch('/api/v1/openapi.json').then(function (r) { return r.json(); }).then(function (spec) {
    var container = document.getElementById('endpoints');
    document.getElementById('status').textContent =
      (spec.info && spec.info.title ? spec.info.title : 'API') + ' — endpoints';
    var paths = Object.keys(spec.paths || {}).sort();
    paths.forEach(function (p) {
      Object.keys(spec.paths[p]).forEach(function (m) {
        var op = spec.paths[p][m];
        var div = document.createElement('div');
        div.className = 'ep';
        var scopes = [];
        (op.security || []).forEach(function (s) {
          (s.oauth2ClientCredentials || []).forEach(function (sc) { scopes.push(sc); });
        });
        div.innerHTML =
          '<div class="row"><span class="method ' + m + '">' + m.toUpperCase() +
          '</span><span class="path"></span></div>' +
          '<div class="summary"></div>' +
          (scopes.length ? '<div class="scopes">scopes: ' +
            scopes.map(function (sc) { return '<code></code>'; }).join('') + '</div>' : '');
        div.querySelector('.path').textContent = p;
        div.querySelector('.summary').textContent = op.summary || '';
        var codes = div.querySelectorAll('.scopes code');
        scopes.forEach(function (sc, i) { if (codes[i]) codes[i].textContent = sc; });
        container.appendChild(div);
      });
    });
  }).catch(function () {
    document.getElementById('status').textContent = 'Failed to load /api/v1/openapi.json';
  });
})();
</script>
</body>
</html>"""


class GatewayController(http.Controller):

    @http.route('/api/v1/openapi.json', type='http', auth='public',
                methods=['GET'], csrf=False, save_session=False)
    def openapi_json(self, **kwargs):
        doc = build_openapi(request.env)
        return request.make_response(
            json.dumps(doc, ensure_ascii=False),
            headers=[('Content-Type', 'application/json; charset=utf-8'),
                     ('Cache-Control', 'public, max-age=300'),
                     ('Access-Control-Allow-Origin', '*')])

    @http.route('/api/docs', type='http', auth='public',
                methods=['GET'], csrf=False, save_session=False)
    def api_docs(self, **kwargs):
        return request.make_response(
            _DOCS_HTML,
            headers=[('Content-Type', 'text/html; charset=utf-8'),
                     ('Cache-Control', 'public, max-age=300')])
