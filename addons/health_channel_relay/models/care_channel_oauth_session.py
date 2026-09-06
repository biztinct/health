# -*- coding: utf-8 -*-
"""Put this system's short name in front of the sign-in ticket.

That is the whole module. The ticket is opaque to everything except
``_consume`` — which hashes whatever comes back and compares it to the hash of
whatever went out — so a prefix survives the round trip untouched and changes
nothing about how the ticket is checked, expired or burned.

``~`` is deliberately outside ``secrets.token_urlsafe``'s alphabet
(``A-Za-z0-9_-``), so the split at the platform can never cut a ticket in the
wrong place.

The short name is checked against the same shape the platform's allowlist
expects before it is used. A system with no short name — the platform itself —
mints the ordinary ticket and is handled locally.
"""
import re

from odoo import api, models

SLUG_PARAM = 'biz_tenancy.slug'
SLUG_RE = re.compile(r'^[a-z0-9]{1,40}$')
SEPARATOR = '~'


class CareChannelOauthSession(models.Model):
    _inherit = 'care.channel.oauth.session'

    @api.model
    def _mint_state(self):
        state = super()._mint_state()
        slug = (self.env['ir.config_parameter'].sudo().get_param(SLUG_PARAM)
                or '').strip()
        if slug and SLUG_RE.match(slug) and SEPARATOR not in state:
            return '%s%s%s' % (slug, SEPARATOR, state)
        return state
