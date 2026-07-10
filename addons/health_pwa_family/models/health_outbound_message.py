# -*- coding: utf-8 -*-
"""FB-047: add the human post-visit family-update purpose to the shipped rails.

The update ping rides ``health.outbound.message`` exactly like the family_link
purposes and the reply purpose: the template id lives in an ir.config_parameter
that defaults empty, so installing changes nothing and no phantom rows appear.
"""
from odoo import fields, models


class HealthOutboundMessage(models.Model):
    _inherit = 'health.outbound.message'

    purpose = fields.Selection(
        selection_add=[('family_update', 'Family Update (post-visit)')],
        ondelete={'family_update': 'cascade'})
