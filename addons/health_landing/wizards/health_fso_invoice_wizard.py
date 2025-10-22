# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class HealthFSOInvoiceWizard(models.TransientModel):
    """
    Wizard for viewing invoice details and creating invoice from FSO Dashboard
    """
    _name = 'health.fso.invoice.wizard'
    _description = 'FSO Invoice Wizard'

    fso_id = fields.Many2one(
        'health.fieldservice.order',
        string='Booking',
        required=True,
        ondelete='cascade'
    )

    patient_id = fields.Many2one(
        'res.partner',
        related='fso_id.patient_id',
        string='Client',
        readonly=True
    )

    invoice_id = fields.Many2one(
        'account.move',
        related='fso_id.invoice_id',
        string='Invoice',
        readonly=True
    )

    sale_order_id = fields.Many2one(
        'sale.order',
        related='fso_id.sale_order_id',
        string='Healthcare Quote',
        readonly=True
    )

    has_invoice = fields.Boolean(
        string='Has Invoice',
        compute='_compute_has_invoice'
    )

    has_quote = fields.Boolean(
        string='Has Quote',
        compute='_compute_has_quote'
    )

    invoice_state = fields.Selection(
        related='fso_id.invoice_state',
        string='Invoice Status',
        readonly=True
    )

    quote_state = fields.Selection(
        related='fso_id.quote_state',
        string='Quote Status',
        readonly=True
    )

    base_price = fields.Monetary(
        related='fso_id.base_price',
        string='Base Service Price',
        readonly=True
    )

    total_price = fields.Monetary(
        related='fso_id.total_price',
        string='Total Price',
        readonly=True
    )

    currency_id = fields.Many2one(
        'res.currency',
        related='fso_id.currency_id',
        readonly=True
    )

    invoice_submitted = fields.Boolean(
        related='fso_id.invoice_submitted',
        string='Invoice Submitted',
        readonly=True
    )

    @api.depends('invoice_id')
    def _compute_has_invoice(self):
        for wizard in self:
            wizard.has_invoice = bool(wizard.invoice_id)

    @api.depends('sale_order_id')
    def _compute_has_quote(self):
        for wizard in self:
            wizard.has_quote = bool(wizard.sale_order_id)

    def action_view_invoice(self):
        """View existing invoice"""
        self.ensure_one()

        if not self.invoice_id:
            raise UserError(_('No invoice has been created for this booking yet.'))

        return {
            'name': _('Invoice - %s') % self.fso_id.name,
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.invoice_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_quote(self):
        """View healthcare quote"""
        self.ensure_one()

        if not self.sale_order_id:
            raise UserError(_('No quote has been created for this booking yet.'))

        return {
            'name': _('Healthcare Quote - %s') % self.fso_id.name,
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': self.sale_order_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_create_quote(self):
        """Create new healthcare quote"""
        self.ensure_one()

        if self.sale_order_id:
            # Quote already exists, open it
            return self.action_view_quote()

        # Create quote using FSO method
        return self.fso_id.action_create_quote()

    def action_create_invoice(self):
        """Create invoice from quote"""
        self.ensure_one()

        if self.invoice_id:
            # Invoice already exists, open it
            return self.action_view_invoice()

        if not self.sale_order_id:
            raise UserError(_('Please create a quote first before creating an invoice.'))

        # Create invoice using FSO method
        return self.fso_id.action_create_final_invoice()

    def action_close(self):
        """Close wizard and return to dashboard"""
        return self._return_to_dashboard()

    def _return_to_dashboard(self):
        """Return to FSO dashboard after saving"""
        return {
            'type': 'ir.actions.client',
            'tag': 'health_landing.fso_hub_spoke_action',
            'params': {
                'fso_id': self.fso_id.id,
                'fso_name': self.fso_id.name,
            }
        }
