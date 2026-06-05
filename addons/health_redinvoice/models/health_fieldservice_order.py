# -*- coding: utf-8 -*-

from odoo import fields, models, _
from odoo.exceptions import UserError


class HealthFieldserviceOrder(models.Model):
    _inherit = 'health.fieldservice.order'

    # Mirror the linked invoice's red-invoice state so the booking form can
    # show/hide the Red Invoice button.
    red_invoice_state = fields.Selection(
        related='invoice_id.red_invoice_state',
        string='Red Invoice State', readonly=True)

    def action_open_red_invoice(self):
        """Open the Red Invoice PDF of this booking's linked invoice."""
        self.ensure_one()
        invoice = self.invoice_id
        if not invoice or invoice.red_invoice_state != 'issued':
            raise UserError(_('No issued Red Invoice is linked to this booking.'))
        return invoice.action_open_red_invoice_pdf()
