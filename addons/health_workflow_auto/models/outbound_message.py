from odoo import fields, models


class HealthOutboundMessage(models.Model):
    """E.5 — add the first-visit-offer purpose to the shipped messaging log."""
    _inherit = 'health.outbound.message'

    purpose = fields.Selection(
        selection_add=[('visit_offer', 'First-Visit Offer')],
        ondelete={'visit_offer': 'cascade'},
    )
