# -*- coding: utf-8 -*-
"""Web chat — our own widget, the only channel with no provider at all.

That makes it the most exposed surface in the module: three anonymous public
routes with no signature to verify. What stands in for a signature:

* ``gateway.rate.counter`` on every route, per IP, plus a second per-session
  window on the message route (health_family_link precedent);
* server-generated uuid4 session ids — a client-chosen id would let a visitor
  claim someone else's thread;
* a 2000-character cap, plain text only (rendered escaped, never as HTML);
* no existence oracle: an unknown session is the same generic answer as a
  disabled channel;
* a daily GC that removes sessions which never said anything.

CORS is opt-in per connection (``settings_json.allowed_origins``); with no
origins configured the widget only works same-origin, which is what the demo
page uses. Bodies are sent as ``text/plain`` by the widget on purpose: that
keeps every request a CORS *simple* request, so there is no preflight to
mishandle.
"""
import json
import logging

from markupsafe import Markup

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

MAX_BODY = 8000
WIDGET_JS = '/health_care_command_channels/static/src/webchat/widget.js'
WIDGET_CSS = '/health_care_command_channels/static/src/webchat/widget.css'


class WebChatController(http.Controller):

    # ------------------------------------------------------------------
    # Plumbing
    # ------------------------------------------------------------------
    def _rate_limited(self, key):
        try:
            allowed, _retry = request.env['gateway.rate.counter'].sudo().hit(key)
            return not allowed
        except Exception as exc:  # noqa: BLE001 — never fail on the counter
            _logger.warning('Web chat rate counter error: %s', exc)
            return False

    @staticmethod
    def _allowed_origins(connection):
        if not connection:
            return []
        raw = connection.get_setting('allowed_origins') or []
        if isinstance(raw, str):
            raw = [part.strip() for part in raw.split(',')]
        return [origin for origin in raw if origin]

    def _cors_headers(self, connection):
        origin = request.httprequest.headers.get('Origin')
        if not origin or origin not in self._allowed_origins(connection):
            return []
        return [('Access-Control-Allow-Origin', origin),
                ('Vary', 'Origin')]

    def _json(self, payload, status=200, connection=None):
        headers = [('Content-Type', 'application/json; charset=utf-8'),
                   ('Cache-Control', 'no-store')]
        headers += self._cors_headers(connection)
        return request.make_response(json.dumps(payload), status=status,
                                     headers=headers)

    def _generic(self, connection=None):
        """One answer for unknown session / disabled channel / bad input."""
        return self._json({'error': 'unavailable'}, status=404,
                          connection=connection)

    @staticmethod
    def _body():
        raw = request.httprequest.get_data()[:MAX_BODY]
        try:
            data = json.loads(raw or b'{}')
        except ValueError:
            return {}
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _widget_version():
        """Cache-busting stamp for the embeddable widget (ledger §5.64b).

        ONE implementation, on the model: CC-C's Channel Center hands the same
        snippet to the tenant, and two copies of a cache-busting rule is how
        they drift apart.
        """
        return request.env['care.channel.connection'].sudo()._widget_version()

    def _ip_key(self, suffix):
        return 'webchat:%s:%s' % (
            suffix, request.httprequest.remote_addr or 'unknown')

    # ------------------------------------------------------------------
    # Routes
    # ------------------------------------------------------------------
    @http.route('/care_channels/webchat/start', type='http', auth='public',
                methods=['POST'], csrf=False, save_session=False, website=False)
    def webchat_start(self, **kwargs):
        Message = request.env['care.channel.message'].sudo()
        connection = Message._webchat_connection()
        if self._rate_limited(self._ip_key('start')):
            return self._json({'error': 'rate_limited'}, status=429,
                              connection=connection)
        if not connection:
            return self._generic()
        body = self._body()
        result = Message._webchat_start(
            session=body.get('session'),
            name=body.get('name'),
            phone=body.get('phone'))
        if not result:
            return self._generic(connection)
        return self._json(result, connection=connection)

    @http.route('/care_channels/webchat/message', type='http', auth='public',
                methods=['POST'], csrf=False, save_session=False, website=False)
    def webchat_message(self, **kwargs):
        Message = request.env['care.channel.message'].sudo()
        connection = Message._webchat_connection()
        body = self._body()
        session = (body.get('session') or '').strip()
        if self._rate_limited(self._ip_key('msg')):
            return self._json({'error': 'rate_limited'}, status=429,
                              connection=connection)
        if session and self._rate_limited('webchat:msg:%s' % session):
            return self._json({'error': 'rate_limited'}, status=429,
                              connection=connection)
        if not connection or not session:
            return self._generic(connection)
        msg = Message._webchat_ingest(session, body.get('text'))
        if not msg:
            return self._generic(connection)
        return self._json({'id': msg.id, 'ok': True}, connection=connection)

    @http.route('/care_channels/webchat/poll', type='http', auth='public',
                methods=['POST'], csrf=False, save_session=False, website=False)
    def webchat_poll(self, **kwargs):
        """POST, not GET (CC-C, CC-B review LOW-3).

        The session id is the visitor's bearer credential for their own thread.
        On a GET it lands in every reverse proxy access log, every browser
        history entry and every Referer header; in a body it does not. Same
        response shape, same rate keys, still a CORS *simple* request because
        the widget posts ``text/plain``.
        """
        Message = request.env['care.channel.message'].sudo()
        connection = Message._webchat_connection()
        body = self._body()
        session = (body.get('session') or '').strip()
        after_id = body.get('after_id') or 0
        if self._rate_limited(self._ip_key('poll')):
            return self._json({'error': 'rate_limited'}, status=429,
                              connection=connection)
        if not connection or not session:
            return self._generic(connection)
        identity = Message._webchat_identity(session)
        if not identity:
            return self._generic(connection)
        return self._json({'messages': Message._webchat_poll(session, after_id)},
                          connection=connection)

    @http.route('/care_channels/webchat/demo', type='http', auth='public',
                methods=['GET'], csrf=False, website=False)
    def webchat_demo(self, **kwargs):
        """Standalone demo page — the widget on a blank host page.

        No ``website`` dependency (health_family_link precedent): a plain QWeb
        template rendered by this controller.
        """
        Message = request.env['care.channel.message'].sudo()
        connection = Message._webchat_connection()
        # The operator's canonical URL first, the requested host as a fallback.
        # NOTE for ops: on vietuat `web.base.url` is still http://…, so the
        # snippet below reads http:// on an https site — a mixed-content trap
        # for a tenant who copy-pastes it. Fix the parameter, not this code.
        base = (request.env['ir.config_parameter'].sudo().get_param(
            'web.base.url') or request.httprequest.host_url or '').rstrip('/')
        stamp = self._widget_version()
        html = request.env['ir.qweb']._render(
            'health_care_command_channels.webchat_demo_page', {
                'enabled': bool(connection),
                'greeting': (connection.get_setting('greeting') or ''
                             if connection else ''),
                'widget_js': '%s?v=%s' % (WIDGET_JS, stamp),
                'widget_css': '%s?v=%s' % (WIDGET_CSS, stamp),
                'embed_snippet': request.env[
                    'care.channel.connection'].sudo()._webchat_embed_snippet(base),
            })
        # Rendered, not `request.render`, for ONE reason: a QWeb template whose
        # root is <html> is served without a doctype, which puts the browser in
        # quirks mode (visible in the CC-B QA console). Markup + Markup, never
        # str + Markup — the latter ESCAPES the left operand and ships a
        # literal "&lt;!DOCTYPE html&gt;" (ledger §5.20, hit live here).
        return request.make_response(
            Markup('<!DOCTYPE html>\n') + html,
            headers=[('Content-Type', 'text/html; charset=utf-8')])
