# -*- coding: utf-8 -*-
"""The Google Ads acquisition card, contributed through the Center's seam.

Google Ads is NOT a conversation channel: there is no
`care.channel.connection` row for it, no `CHANNEL_SELECTION` key, no reply
transport and no composer. It is an acquisition source, and the only thing it
shares with the eight chat channels is the place a tenant goes to set things
up. `_center_extra_cards()` exists so it can appear there without pretending
to be something it is not.
"""
from odoo import api, models


class CareChannelConnectionGoogleAds(models.Model):
    _inherit = 'care.channel.connection'

    @api.model
    def _center_extra_cards(self):
        cards = super()._center_extra_cards()
        cards.append(self.env['google.ads.account']._center_card_payload())
        return cards
