from odoo import fields, models


class HealthOutboundMessage(models.Model):
    """Add the telehealth-join purpose to the shipped messaging log.

    selection_add inherit (never edits health_messaging's file), same
    one-liner precedent as health_family_link/models/outbound_message.py.
    """
    _inherit = 'health.outbound.message'

    purpose = fields.Selection(
        selection_add=[('telehealth_join', 'Telehealth Join Link')],
        ondelete={'telehealth_join': 'cascade'},
    )
