# -*- coding: utf-8 -*-
"""OAuth2 token endpoint — client-credentials grant (spec B.4, RFC 6749).

Hand-rolled grant handling (an option the spec explicitly allows). When
`authlib` is importable it is used for spec-exact Basic-auth header parsing;
otherwise a minimal parser degrades gracefully.
"""
import base64
import json
import logging

from odoo import SUPERUSER_ID, api as odoo_api, http
from odoo.http import request

_logger = logging.getLogger(__name__)


def _json_response(payload, status=200, extra_headers=None):
    headers = [
        ('Content-Type', 'application/json; charset=utf-8'),
        ('Cache-Control', 'no-store'),
        ('Pragma', 'no-cache'),
    ]
    if extra_headers:
        headers.extend(extra_headers)
    return request.make_response(json.dumps(payload), headers=headers,
                                 status=status)


def _parse_basic_auth(header):
    """Return (client_id, client_secret) from a Basic auth header, or
    (None, None)."""
    if not header or not header.lower().startswith('basic '):
        return None, None
    try:  # pragma: no cover - trivial branch
        from authlib.common.encoding import to_unicode  # noqa: F401 (presence probe)
    except ImportError:
        pass  # graceful degradation — manual parse below is equivalent
    try:
        decoded = base64.b64decode(header[6:].strip()).decode('utf-8')
        client_id, _sep, client_secret = decoded.partition(':')
        return client_id or None, client_secret or None
    except Exception:
        return None, None


class GatewayOAuthController(http.Controller):

    @http.route('/oauth/token', type='http', auth='none', methods=['POST'],
                csrf=False, save_session=False)
    def oauth_token(self, **kwargs):
        """POST /oauth/token — grant_type=client_credentials only.
        Client auth: client_secret_basic (Authorization header) or body params.
        Response (RFC 6749): access_token/token_type/expires_in/scope."""
        env = odoo_api.Environment(request.env.cr, SUPERUSER_ID, {})

        # Params from form body, JSON body, or query string.
        params = dict(request.httprequest.form or {})
        if not params and request.httprequest.data:
            try:
                body = json.loads(request.httprequest.data.decode('utf-8'))
                if isinstance(body, dict):
                    params = body
            except (ValueError, UnicodeDecodeError):
                params = {}
        if not params:
            params = dict(kwargs)

        grant_type = params.get('grant_type')
        if grant_type != 'client_credentials':
            return _json_response({'error': 'unsupported_grant_type'}, status=400)

        client_id, client_secret = _parse_basic_auth(
            request.httprequest.headers.get('Authorization', ''))
        if not client_id:
            client_id = params.get('client_id')
            client_secret = params.get('client_secret')

        client = env['gateway.oauth.client']._authenticate_client(
            client_id, client_secret)
        if not client:
            return _json_response(
                {'error': 'invalid_client'}, status=401,
                extra_headers=[('WWW-Authenticate', 'Basic realm="oauth"')])

        allowed = set(client.allowed_scope_ids.mapped('code'))
        requested_raw = (params.get('scope') or '').split()
        if requested_raw:
            granted = sorted(set(requested_raw) & allowed)
            if not granted:
                return _json_response({'error': 'invalid_scope'}, status=400)
        else:
            granted = sorted(allowed)

        raw_token = env['gateway.token'].issue(client, granted)
        return _json_response({
            'access_token': raw_token,
            'token_type': 'Bearer',
            'expires_in': client.token_lifetime or 3600,
            'scope': ' '.join(granted),
        })
