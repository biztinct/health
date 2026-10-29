# -*- coding: utf-8 -*-
from odoo import models, fields, api

class ProductPricelist(models.Model):
    _inherit = 'product.pricelist'

    use_advanced_pricing = fields.Boolean('Use Advanced Pricing Engine', default=False, tracking=True)
    advanced_engine_id = fields.Many2one('advanced.pricing.engine', 'Advanced Pricing Engine', tracking=True)
    discount_on_base_only = fields.Boolean(
        'Discount on Base Price Only', default=False, tracking=True,
        help='Apply the quote line discount to catalogue price × quantity; keep adjustments unchanged.')

    # Advanced pricing is handled in sale.order.line._compute_advanced_price()
    # This keeps the Catalog functionality working while still applying our pricing rules
