from odoo import fields, models


class HealthOutboundMessage(models.Model):
    """A1 — add the two family purposes to the shipped messaging log.

    selection_add inherit (never edits health_messaging's file), same
    one-liner precedent as health_workflow_auto/models/outbound_message.py.
    """
    _inherit = 'health.outbound.message'

    purpose = fields.Selection(
        selection_add=[
            ('family_visit_link', 'Family Visit Link'),
            ('family_snapshot', 'Family Post-Visit Snapshot'),
        ],
        ondelete={'family_visit_link': 'cascade',
                  'family_snapshot': 'cascade'},
    )
