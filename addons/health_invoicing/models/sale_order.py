# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class SaleOrderLine(models.Model):
    """Extend sale order line with discount reason field"""
    _inherit = 'sale.order.line'

    # Discount tracking and validation
    discount_reason = fields.Char(
        'Discount Reason',
        help='Mandatory reason when discount is applied to this line'
    )

    @api.constrains('discount', 'discount_reason')
    def _check_discount_reason(self):
        """Ensure discount reason is provided when discount > 0"""
        for line in self:
            # Skip validation for section/note lines
            if line.display_type in ('line_section', 'line_note'):
                continue

            if line.discount > 0 and not (line.discount_reason and line.discount_reason.strip()):
                raise ValidationError(_(
                    'Discount reason is mandatory when applying discounts!\n\n'
                    'Line: %s\n'
                    'Discount: %.2f%%\n\n'
                    'Please provide a reason in the "Discount Reason" field.'
                ) % (line.name or line.product_id.name or 'Unnamed', line.discount))

    def _prepare_invoice_line(self, **optional_values):
        """Override to copy discount_reason to invoice line"""
        res = super()._prepare_invoice_line(**optional_values)

        # Copy discount_reason from sale order line to invoice line
        if self.discount_reason:
            res['discount_reason'] = self.discount_reason

        return res
