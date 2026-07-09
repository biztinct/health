# -*- coding: utf-8 -*-
"""Add the reschedule purpose to the shipped messaging log (selection_add
inherit — never edits health_messaging's file; the family_link precedent)."""
from odoo import fields, models


class HealthOutboundMessage(models.Model):
    _inherit = 'health.outbound.message'

    purpose = fields.Selection(
        selection_add=[('booking_rescheduled', 'Booking Rescheduled')],
        ondelete={'booking_rescheduled': 'cascade'},
    )
