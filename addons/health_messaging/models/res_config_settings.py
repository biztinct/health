# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    messaging_enabled = fields.Boolean(
        string='Enable visit messaging',
        config_parameter='health_messaging.enabled',
        help='Master switch. Off by default — installing changes nothing '
             'until switched on.')
    messaging_dry_run = fields.Boolean(
        string='Simulation mode (log only, no real sends)',
        default=True,
        config_parameter='health_messaging.dry_run',
        help='SAFETY: on by default. The full pipeline runs but the real '
             'ZNS/email calls are skipped and rows are marked simulated.')
    messaging_zns_template_confirmation = fields.Char(
        string='ZNS template — Booking confirmation',
        config_parameter='health_messaging.zns_template_confirmation')
    messaging_zns_template_reminder24 = fields.Char(
        string='ZNS template — 24h reminder',
        config_parameter='health_messaging.zns_template_reminder24')
    messaging_zns_template_reminder2 = fields.Char(
        string='ZNS template — 2h reminder',
        config_parameter='health_messaging.zns_template_reminder2')
    messaging_zns_template_cancellation = fields.Char(
        string='ZNS template — Cancellation',
        config_parameter='health_messaging.zns_template_cancellation')
    messaging_quiet_start = fields.Float(
        string='Quiet hours start',
        default=21.0,
        config_parameter='health_messaging.quiet_start')
    messaging_quiet_end = fields.Float(
        string='Quiet hours end',
        default=7.0,
        config_parameter='health_messaging.quiet_end')
