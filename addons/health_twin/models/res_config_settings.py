# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    twin_enabled = fields.Boolean(
        string='Deterioration Risk Engine',
        config_parameter='health_twin.twin_enabled', default=True)
    twin_sweep_enabled = fields.Boolean(
        string='Nightly Risk Sweep',
        config_parameter='health_twin.twin_sweep_enabled', default=True)
    twin_history_enabled = fields.Boolean(
        string='Risk Trajectory History',
        config_parameter='health_twin.history_enabled', default=True)
    twin_forecast_enabled = fields.Boolean(
        string='Deterioration Forecast',
        config_parameter='health_twin.forecast_enabled', default=True)

    def set_values(self):
        # §5.36: core set_param() UNLINKS a parameter whose value is falsy,
        # and twin_config.get_bool then falls back to the hardcoded default
        # (True) — so a default-True kill-switch saved as False would
        # silently snap back on. Persist explicit strings instead.
        super().set_values()
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('health_twin.twin_enabled',
                      'True' if self.twin_enabled else 'False')
        icp.set_param('health_twin.twin_sweep_enabled',
                      'True' if self.twin_sweep_enabled else 'False')
        icp.set_param('health_twin.history_enabled',
                      'True' if self.twin_history_enabled else 'False')
        icp.set_param('health_twin.forecast_enabled',
                      'True' if self.twin_forecast_enabled else 'False')
