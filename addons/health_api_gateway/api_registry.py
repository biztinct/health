# -*- coding: utf-8 -*-
"""Plain-python route registry + OpenAPI 3.1 generator (no ORM imports).

The ``@api_route`` decorator (defined in ``controllers/gateway.py`` — that is
where ``health_fhir_core`` imports it from, per the platform interface
contract) registers metadata here at import time; ``build_openapi()`` walks
the registry to produce the OpenAPI 3.1 document served at
``GET /api/v1/openapi.json``.
"""
import re
import time

API_REGISTRY = []
# Each entry: {path, methods, scopes, summary, request_model, response_model,
#              tags, fn_qualname}

_OPENAPI_CACHE = {'ts': 0.0, 'doc': None}
_OPENAPI_CACHE_TTL = 300  # seconds (spec B.3: cached 5 min)

_CONVERTER_RE = re.compile(r'<(?:[a-zA-Z_]+(?:\([^)]*\))?:)?([a-zA-Z_][a-zA-Z0-9_]*)>')


def register_route(meta):
    """Register (or replace, on module reload) one route's metadata."""
    API_REGISTRY[:] = [m for m in API_REGISTRY
                       if not (m['path'] == meta['path']
                               and set(m['methods']) == set(meta['methods']))]
    API_REGISTRY.append(meta)
    _OPENAPI_CACHE['doc'] = None  # invalidate cache


def _openapi_path(odoo_path):
    """Convert an Odoo route path ``/api/v1/bookings/<int:order_id>`` to the
    OpenAPI form ``/api/v1/bookings/{order_id}`` and return
    (path, [param names])."""
    params = _CONVERTER_RE.findall(odoo_path)
    return _CONVERTER_RE.sub(lambda m: '{%s}' % m.group(1), odoo_path), params


ENVELOPE_SCHEMA = {
    'type': 'object',
    'properties': {
        'success': {'type': 'boolean'},
        'timestamp': {'type': 'string', 'format': 'date-time'},
        'data': {'type': 'object'},
        'error': {'type': 'string'},
    },
    'required': ['success', 'timestamp'],
}


def _envelope(data_schema):
    """Wrap a data schema in the standard health19 response envelope."""
    schema = {k: v for k, v in ENVELOPE_SCHEMA.items()}
    props = dict(schema['properties'])
    if data_schema:
        props['data'] = data_schema
    schema = dict(schema, properties=props)
    return schema


ERROR_RESPONSES = {
    '401': {'description': 'Missing/invalid credentials',
            'content': {'application/json': {'schema': ENVELOPE_SCHEMA}}},
    '403': {'description': 'Token lacks a required scope',
            'content': {'application/json': {'schema': ENVELOPE_SCHEMA}}},
    '422': {'description': 'Request body failed validation',
            'content': {'application/json': {'schema': ENVELOPE_SCHEMA}}},
    '429': {'description': 'Rate limited (Retry-After header set)',
            'content': {'application/json': {'schema': ENVELOPE_SCHEMA}}},
}


def _schema_of(model):
    """Accept either a plain dict JSON-schema fragment or a pydantic v2 model
    class; return a JSON-schema dict."""
    if model is None:
        return None
    if isinstance(model, dict):
        return model
    json_schema = getattr(model, 'model_json_schema', None)
    if callable(json_schema):  # pydantic v2 class
        try:
            return json_schema()
        except Exception:
            return {'type': 'object'}
    return {'type': 'object'}


def build_openapi(env=None):
    """Build (and cache for 5 minutes) the OpenAPI 3.1 document."""
    now = time.time()
    if _OPENAPI_CACHE['doc'] is not None and now - _OPENAPI_CACHE['ts'] < _OPENAPI_CACHE_TTL:
        return _OPENAPI_CACHE['doc']

    all_scopes = sorted({s for m in API_REGISTRY for s in (m.get('scopes') or ())})
    servers = []
    if env is not None:
        try:
            base_url = env['ir.config_parameter'].sudo().get_param('web.base.url')
            if base_url:
                servers = [{'url': base_url}]
        except Exception:
            servers = []

    paths = {}
    for meta in API_REGISTRY:
        path, path_params = _openapi_path(meta['path'])
        operations = paths.setdefault(path, {})
        for method in meta['methods']:
            op = {
                'summary': meta.get('summary') or '',
                'tags': list(meta.get('tags') or ()) or ['api'],
                'operationId': '%s_%s' % (method.lower(),
                                          re.sub(r'[^a-zA-Z0-9]+', '_', path).strip('_')),
                'security': [{'bearerApiKey': []},
                             {'oauth2ClientCredentials': list(meta.get('scopes') or ())}],
                'parameters': [
                    {'name': p, 'in': 'path', 'required': True,
                     'schema': {'type': 'integer'}}
                    for p in path_params
                ],
                'responses': {
                    '200': {
                        'description': 'Success envelope',
                        'content': {'application/json': {
                            'schema': _envelope(_schema_of(meta.get('response_model'))),
                        }},
                    },
                },
            }
            op['responses'].update(ERROR_RESPONSES)
            if meta.get('scopes'):
                op['description'] = 'Required scope (any of): %s' % ', '.join(meta['scopes'])
            req_schema = _schema_of(meta.get('request_model'))
            if req_schema and method.upper() in ('POST', 'PUT', 'PATCH'):
                op['requestBody'] = {
                    'required': True,
                    'content': {'application/json': {'schema': req_schema}},
                }
            operations[method.lower()] = op

    doc = {
        'openapi': '3.1.0',
        'info': {
            'title': 'health19 API Gateway',
            'version': '1.0.0',
            'description': (
                'Versioned REST surface over the health19 platform. '
                'Responses use the standard envelope '
                '{"success": bool, "timestamp": iso, "data"|"error": ...}.'
            ),
        },
        'servers': servers,
        'paths': paths,
        'components': {
            'securitySchemes': {
                'bearerApiKey': {
                    'type': 'http',
                    'scheme': 'bearer',
                    'description': ('Odoo API key of a service user, or an opaque '
                                    'gateway token (hg_ prefix) issued by /oauth/token.'),
                },
                'oauth2ClientCredentials': {
                    'type': 'oauth2',
                    'flows': {
                        'clientCredentials': {
                            'tokenUrl': '/oauth/token',
                            'scopes': {s: s for s in all_scopes},
                        },
                    },
                },
            },
        },
    }
    _OPENAPI_CACHE['doc'] = doc
    _OPENAPI_CACHE['ts'] = now
    return doc
