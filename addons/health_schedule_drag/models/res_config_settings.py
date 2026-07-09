# -*- coding: utf-8 -*-
"""Settings: the reschedule ZNS template id (empty → no patient send)."""
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    schedule_drag_zns_template_rescheduled = fields.Char(
        string='Reschedule ZNS Template',
        config_parameter='health_schedule_drag.zns_template_rescheduled',
        help='Zalo ZNS template id sent to the patient when a booking is '
             'rescheduled by drag. Empty → no patient notification is queued. '
             'Rides health_messaging.enabled / dry_run.')
