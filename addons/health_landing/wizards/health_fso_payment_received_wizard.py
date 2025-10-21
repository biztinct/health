# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class HealthFSOPaymentReceivedWizard(models.TransientModel):
    """
    Wizard for marking payment as received for "Pay Later" bookings
    """
    _name = 'health.fso.payment.received.wizard'
    _description = 'FSO Payment Received Wizard'

    fso_id = fields.Many2one(
        'health.fieldservice.order',
        string='Booking',
        required=True,
        ondelete='cascade'
    )

    patient_id = fields.Many2one(
        'res.partner',
        related='fso_id.patient_id',
        string='Patient',
        readonly=True
    )

    service_type = fields.Selection(
        related='fso_id.service_type',
        string='Service Type',
        readonly=True
    )

    payment_method_display = fields.Char(
        string='Payment Method',
        compute='_compute_payment_method_display',
        readonly=True
    )

    # Editable Fields
    payment_amount = fields.Monetary(
        string='Payment Amount',
        required=True,
        currency_field='currency_id',
        help='Amount received from patient'
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
        required=True
    )

    payment_date = fields.Datetime(
        string='Payment Date',
        default=fields.Datetime.now,
        required=True,
        help='Date when payment was received'
    )

    payment_reference = fields.Char(
        string='Payment Reference',
        help='Bank transaction ID or payment reference number'
    )

    payment_notes = fields.Text(
        string='Payment Notes',
        help='Additional notes about the payment'
    )

    @api.depends('fso_id.payment_method')
    def _compute_payment_method_display(self):
        """Display payment method"""
        for wizard in self:
            if wizard.fso_id.payment_method:
                wizard.payment_method_display = dict(
                    wizard.fso_id._fields['payment_method'].selection
                ).get(wizard.fso_id.payment_method, '')
            else:
                wizard.payment_method_display = _('Not specified')

    @api.model
    def default_get(self, fields_list):
        """Pre-populate wizard with FSO data"""
        res = super().default_get(fields_list)

        fso_id = self.env.context.get('default_fso_id')
        if fso_id:
            fso = self.env['health.fieldservice.order'].browse(fso_id)
            # Pre-populate payment amount from sale order if exists
            if fso.sale_order_id:
                res['payment_amount'] = fso.sale_order_id.amount_total

        return res

    def action_confirm_payment(self):
        """Confirm payment received and return to dashboard"""
        self.ensure_one()

        if self.payment_amount <= 0:
            raise UserError(_('Payment amount must be greater than zero.'))

        # Update FSO with payment received information
        self.fso_id.write({
            'payment_received_date': self.payment_date,
        })

        # Post message to chatter with payment details
        self.fso_id.message_post(
            body=_('Payment received: %s %s on %s. Reference: %s') % (
                self.payment_amount,
                self.currency_id.name,
                self.payment_date.strftime('%Y-%m-%d %H:%M:%S'),
                self.payment_reference or 'N/A'
            ),
            subject='Payment Received',
            message_type='notification'
        )

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
