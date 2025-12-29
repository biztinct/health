# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    @api.onchange("group_product_pricelist")
    def _onchange_group_sale_pricelist(self):
        # Override base warning about deactivating pricelists.
        return
