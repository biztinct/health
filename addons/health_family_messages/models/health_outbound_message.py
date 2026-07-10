# -*- coding: utf-8 -*-
"""Add the family reply purpose to the shipped outbound-message rails.

The reply ping rides ``health.outbound.message`` exactly like the family_link
purposes: template id lives in an ir.config_parameter that defaults empty, so
installing changes nothing and no phantom rows appear.
"""
from odoo import fields, models


class HealthOutboundMessage(models.Model):
    _inherit = 'health.outbound.message'

    purpose = fields.Selection(
        selection_add=[('family_message_reply', 'Family Message Reply')],
        ondelete={'family_message_reply': 'cascade'})
