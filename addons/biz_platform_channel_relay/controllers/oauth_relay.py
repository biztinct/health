# -*- coding: utf-8 -*-
"""The platform's single sign-in return address, for everybody's Messenger.

Meta's application holds ONE return address per login configuration and it is
matched exactly — no wildcards, no subdomains. So every customer's Messenger
sign-in comes back here, and this route sends the browser on to the customer it
belongs to.

How it knows which customer: the customer's own system puts ``<slug>~`` in
front of the opaque sign-in ticket it mints (ledger §5.173). Meta hands that
string back untouched, and it is passed on untouched — the customer's own
callback hashes the WHOLE string, so nothing about the sign-in changes.

**The prefix is routing, never trust.** The address the browser is sent to comes
from the list of customers this platform relays for, and from nowhere else; a
short name that names no active customer falls through to the platform's own
handling, which renders the same page every unknown ticket gets. An open
redirect on a sign-in callback is a phishing primitive.
"""
import logging

import werkzeug.utils

from odoo import http
from odoo.http import request

from odoo.addons.health_care_command_channels.controllers.oauth import (
    ChannelHubOauthController,
)
from odoo.addons.health_care_command_channels.services.adapters import (
    META_CALLBACK_PATH,
)

_logger = logging.getLogger(__name__)


class RelayOauthController(ChannelHubOauthController):

    def _rate_limited(self):
        """One hit per request, however many times the chain asks.

        The relay branch checks the counter before its lookup and then hands a
        sign-in it does not own to the parent, which checks the counter again —
        so without this the platform's own sign-ins would spend two of their
        budget for every one request. Memoised on the request; a failure to
        stash it costs an extra count, never an error.
        """
        try:
            cached = getattr(request, '_relay_rate_checked', None)
            if cached is not None:
                return cached
        except Exception:  # noqa: BLE001
            return super()._rate_limited()
        result = super()._rate_limited()
        try:
            request._relay_rate_checked = result
        except Exception:  # noqa: BLE001
            pass
        return result

    @http.route('/channel_hub/oauth/callback/<string:provider>', type='http',
                auth='public', website=False, methods=['GET'], csrf=False,
                save_session=False)
    def oauth_callback(self, provider, **params):
        if provider == 'meta':
            # The counter comes FIRST, before any database lookup — the parent
            # route does the same (controllers/oauth.py:50), and a limiter that
            # runs after a query is a limiter that does not protect the query.
            if self._rate_limited():
                return self._page('health_care_command_channels.oauth_generic')
            slug = request.env['channel.relay.tenant'].sudo()._slug_from_state(
                params.get('state'))
            if slug:
                url = '%s%s' % (
                    request.env['biz.tenants'].sudo()._tenant_url(slug),
                    META_CALLBACK_PATH)
                query = request.httprequest.query_string.decode('latin-1')
                if query:
                    url = '%s?%s' % (url, query)
                # The detail is the short name and nothing else: never the
                # code, never the ticket, never a parameter of any kind.
                request.env(su=True)['care.channel.audit']._log(
                    'relay_routed_signin', detail=slug)
                return werkzeug.utils.redirect(url, 302)
        return super().oauth_callback(provider, **params)
