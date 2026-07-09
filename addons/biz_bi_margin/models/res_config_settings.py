# -*- coding: utf-8 -*-
"""Costing-assumption settings for the margin view (handover §2.4).

These three numbers are the inputs the operational data lacks. Margin quality
depends on them — the Settings block labels them explicitly as ASSUMPTIONS.
"""
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    margin_default_hourly_cost_vnd = fields.Float(
        string='Default Hourly Labor Cost (VND)',
        config_parameter='health_bi_margin.default_hourly_cost_vnd',
        default=45000)
    margin_monthly_hours = fields.Float(
        string='Monthly Working Hours',
        config_parameter='health_bi_margin.monthly_hours', default=208)
    margin_cost_per_km_vnd = fields.Float(
        string='Travel Cost per km (VND)',
        config_parameter='health_bi_margin.cost_per_km_vnd', default=3000)
