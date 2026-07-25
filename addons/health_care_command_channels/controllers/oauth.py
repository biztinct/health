# -*- coding: utf-8 -*-
"""Public OAuth callback — a thin HTTP shell (architecture §7.3).

All decision logic lives in ``care.channel.oauth.session._handle_callback`` so
a TransactionCase can cover it (ledger §5.32: this module ships zero HttpCase,
because an HttpCase's side effects run on a separate cursor and poison later
TransactionCase suites in the same run).

Posture, per the §5.61 webhook rules and the voip24h precedent:

* ``type='http'`` (never jsonrpc), ``auth='public'``, ``save_session=False``,
  GET only;
* rate-limited on the caller IP through ``gateway.rate.counter`` before any
  database lookup;
* unknown / used / expired / mismatched state all render the SAME page — no
  oracle;
* the response NEVER echoes ``state``, ``code`` or any other parameter.
"""
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class ChannelHubOauthController(http.Controller):

    def _rate_limited(self):
        ip = request.httprequest.remote_addr or 'unknown'
        try:
            allowed, _retry = request.env['gateway.rate.counter'].sudo().hit(
                'chub:cb:%s' % ip)
            return not allowed
        except Exception as exc:  # noqa: BLE001 — never fail the page on the counter
            _logger.warning('Channel callback rate counter error: %s', exc)
            return False

    def _page(self, template, channel=False):
        icp = request.env['ir.config_parameter'].sudo()
        return request.render(template, {
            'channel': channel or '',
            'origin': icp.get_param('web.base.url') or '',
        })

    @http.route('/channel_hub/oauth/callback/<string:provider>', type='http',
                auth='public', website=False, methods=['GET'], csrf=False,
                save_session=False)
    def oauth_callback(self, provider, **params):
        if self._rate_limited():
            return self._page('health_care_command_channels.oauth_generic')
        result = request.env['care.channel.oauth.session'].sudo()._handle_callback(
            provider, params)
        outcome = result.get('outcome')
        if outcome == 'ok':
            return self._page('health_care_command_channels.oauth_success',
                              result.get('channel'))
        if outcome == 'denied':
            return self._page('health_care_command_channels.oauth_denied',
                              result.get('channel'))
        return self._page('health_care_command_channels.oauth_generic')
