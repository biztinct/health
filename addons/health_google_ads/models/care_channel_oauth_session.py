# -*- coding: utf-8 -*-
"""Reuse the channels' public OAuth callback for Google Ads — by ORM only.

``/channel_hub/oauth/callback/<string:provider>`` already exists
(health_care_command_channels/controllers/oauth.py:46-71): it is rate-limited,
``auth='public'``, GET-only, echoes nothing, and calls
``care.channel.oauth.session._handle_callback(provider, params)``. The relay
hub (biz_platform_channel_relay) overrides the same route and bounces only
when ``provider == 'meta'``, so every other provider string falls through to
``super().oauth_callback`` and reaches us on every database.

Inheriting the model method is therefore the WHOLE integration: no controller,
no route, and NO edit to health_care_command_channels.
"""
from odoo import api, models


class CareChannelOauthSessionGoogleAds(models.Model):
    _inherit = 'care.channel.oauth.session'

    @api.model
    def _handle_callback(self, provider, params):
        if provider == 'google_ads':
            return self.env['google.ads.oauth.session']._handle_callback(
                params or {})
        return super()._handle_callback(provider, params)
