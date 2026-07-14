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

    def set_values(self):
        # Core set_param() UNLINKS a parameter whose value is falsy, and
        # tm_config.get_bool then falls back to the hardcoded default
        # (True) — so a default-True kill-switch saved as False would
        # silently snap back on. Persist explicit strings instead.
        super().set_values()
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('health_telemonitoring.ews_enabled',
                      'True' if self.tm_ews_enabled else 'False')
        icp.set_param('health_telemonitoring.trend_enabled',
                      'True' if self.tm_trend_enabled else 'False')
        icp.set_param('health_telemonitoring.activity_on_critical',
                      'True' if self.tm_activity_on_critical else 'False')
        icp.set_param('health_telemonitoring.ews_window_minutes',
                      str(self.tm_ews_window_minutes
                          if self.tm_ews_window_minutes > 0 else 60))
