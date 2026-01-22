# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # Map Provider Configuration
    health_map_provider = fields.Selection([
        ('openstreetmap', 'OpenStreetMap (Free)'),
        ('google', 'Google Maps (Requires API Key)'),
    ], string='Map Provider', default='openstreetmap',
       config_parameter='health_base.map_provider',
       help='Choose the map provider for displaying patient addresses')

    health_google_maps_api_key = fields.Char(
        string='Google Maps API Key',
        config_parameter='health_base.google_maps_api_key',
        help='Enter your Google Maps API key. Required for Google Maps display and driving distance calculations.'
    )

    @api.onchange("group_product_pricelist")
    def _onchange_group_sale_pricelist(self):
        # Override base warning about deactivating pricelists.
        return
