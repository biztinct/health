# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    tm_ews_enabled = fields.Boolean(
        string='NEWS2 Scoring',
        config_parameter='health_telemonitoring.ews_enabled', default=True)
    tm_trend_enabled = fields.Boolean(
        string='Nightly Trend Sweep',
        config_parameter='health_telemonitoring.trend_enabled', default=True)
    tm_ews_window_minutes = fields.Integer(
        string='Scoring Window (minutes)',
        config_parameter='health_telemonitoring.ews_window_minutes',
        default=60)
    tm_activity_on_critical = fields.Boolean(
        string='Activity on Critical Alert',
        config_parameter='health_telemonitoring.activity_on_critical',
        default=True)
