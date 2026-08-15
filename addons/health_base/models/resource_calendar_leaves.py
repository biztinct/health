# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class HealthcareCalendarLeaves(models.Model):
    """
    Extend Odoo's standard resource.calendar.leaves for healthcare pricing

    This model adds healthcare-specific holiday classification and pricing multipliers
    to the standard Odoo time-off/public holiday system.

    Use Cases:
    - TET holidays with 3x pricing
    - National holidays with 2x pricing
    - Regional holidays (province-specific)
    - Observances (no pricing impact)
    """
    _inherit = 'resource.calendar.leaves'

    # Healthcare-specific holiday classification
    holiday_type_id = fields.Many2one(
        'health.lookup.value',
        string='Holiday Type',
        domain="[('category_code', '=', 'holiday_type'), ('active', '=', True)]",
        ondelete='restrict',
        tracking=True,
        help='Type of public holiday for pricing rules and scheduling')
    # Companion for view expressions and domains: an Odoo view attribute
    # (invisible=, decoration-, domain=) cannot traverse a many2one, and
    # this keeps every existing comparison a one-word change.
    holiday_type_code = fields.Char(
        related='holiday_type_id.code', string='Holiday Type Code', readonly=True)

    price_multiplier = fields.Float(
        'Price Multiplier',
        default=1.0,
        help='Pricing multiplier for this holiday (e.g., 3.0 for TET = 3x normal price)',
        tracking=True
    )

    province_id = fields.Many2one(
        'res.country.state',
        string='Province/State',
        help='Leave blank for national holidays, or specify province for regional holidays',
        tracking=True
    )

    is_pricing_holiday = fields.Boolean(
        'Apply to Pricing',
        default=True,
        help='Include this holiday in pricing calculations (TET, National holidays = True, Observances = False)',
        tracking=True
    )

    @api.constrains('price_multiplier')
    def _check_price_multiplier(self):
        """Validate price multiplier is positive"""
        for leave in self:
            if leave.price_multiplier < 0:
                raise ValidationError(_('Price multiplier must be positive'))
