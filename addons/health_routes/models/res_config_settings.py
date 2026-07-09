# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Warnings are passive → default ON.
    rt_enabled = fields.Boolean(
        string='Enable Travel-Feasibility Warnings',
        config_parameter='health_routes.enabled', default=True)
    rt_buffer_minutes = fields.Integer(
        string='Travel Buffer (minutes)',
        config_parameter='health_routes.buffer_minutes', default=10,
        help='Minutes of slack added on top of travel time before a '
             'transition is considered comfortably feasible.')
    rt_horizon_days = fields.Integer(
        string='Feasibility Sweep Horizon (days)',
        config_parameter='health_routes.horizon_days', default=7)
    rt_leg_ttl_days = fields.Integer(
        string='Distance Cache TTL (days)',
        config_parameter='health_routes.leg_ttl_days', default=30)
    # OFF on vietuat — UAT must not hammer public OSRM; the approx tier is fine.
    rt_use_external_router = fields.Boolean(
        string='Use External Router (Google/OSRM)',
        config_parameter='health_routes.use_external_router', default=False,
        help='When off, distances use the local straight-line approximation '
             '(no network). Leave off unless a Google key is configured.')
