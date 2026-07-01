# -*- coding: utf-8 -*-
from odoo import models, fields


class HealthFieldserviceOrder(models.Model):
    """Surface the advanced-pricing breakdown of the linked quote directly on the
    booking record, so staff see which rules shaped the price without opening the
    quote."""
    _inherit = 'health.fieldservice.order'

    pricing_breakdown_html = fields.Html(
        string='Pricing Breakdown',
        related='sale_order_id.pricing_breakdown_html',
        readonly=True,
    )
