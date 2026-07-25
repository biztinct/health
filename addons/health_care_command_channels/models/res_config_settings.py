# -*- coding: utf-8 -*-
"""One setting: extra hosts an OAuth return may land on (handover §4.7)."""
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    channel_hub_allowed_redirect_hosts = fields.Char(
        string='Additional return hosts',
        config_parameter='channel_hub.allowed_redirect_hosts',
        help='Comma-separated hostnames, in addition to this instance\'s own '
             'base URL, that a channel authorization may return to. Empty by '
             'default — leave it empty unless the Channel Center is embedded '
             'in another front end.')

    # No set_values() override is needed here: the §5.36 trap (core set_param()
    # UNLINKS a parameter written with a falsy value, so a default-True Boolean
    # can never be switched off) is specific to Boolean/Integer. A Char cleared
    # to an empty string also unlinks the parameter — which is exactly the
    # intended meaning here ("no extra hosts"), and the reader defaults to the
    # empty allowlist. Add the override the moment a Boolean lands on this page.
