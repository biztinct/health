# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class HealthFSOCashCollectionWizard(models.TransientModel):
    """
    Wizard for Operations Manager to collect cash from nurse
    """
    _name = 'health.fso.cash.collection.wizard'
    _description = 'FSO Cash Collection Wizard'

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

    lead_staff_id = fields.Many2one(
        'hr.employee',
        related='fso_id.lead_staff_id',
        string='Nurse/Staff Who Collected Cash',
        readonly=True
    )

    total_price = fields.Monetary(
        string='Total Amount',
        compute='_compute_total_price',
        currency_field='currency_id',
        readonly=True
    )

    @api.depends('fso_id', 'fso_id.invoice_id', 'fso_id.sale_order_id')
    def _compute_total_price(self):
        for wiz in self:
            if wiz.fso_id and wiz.fso_id.invoice_id:
                wiz.total_price = abs(
                    wiz.fso_id.invoice_id.amount_total_signed
                    or wiz.fso_id.invoice_id.amount_total or 0.0
                )
            elif wiz.fso_id and wiz.fso_id.sale_order_id:
                wiz.total_price = wiz.fso_id.sale_order_id.amount_total or 0.0
            else:
                wiz.total_price = 0.0

    currency_id = fields.Many2one(
        'res.currency',
        related='fso_id.currency_id',
        readonly=True
    )

    cash_amount = fields.Monetary(
        string='Cash Amount Received',
        required=True,
        currency_field='currency_id',
        help='Amount of cash received from nurse'
    )

    collection_date = fields.Datetime(
        string='Collection Date & Time',
        default=fields.Datetime.now,
        required=True
    )

    collection_notes = fields.Text(
        string='Collection Notes',
        help='Additional notes about cash collection'
    )

    collected_by_user_id = fields.Many2one(
        'res.users',
        string='Collected By',
        default=lambda self: self.env.user,
        readonly=True
    )

    @api.model
    def default_get(self, fields_list):
        """Pre-populate wizard with FSO data"""
        res = super().default_get(fields_list)

        fso_id = self.env.context.get('default_fso_id')
        if fso_id:
            fso = self.env['health.fieldservice.order'].browse(fso_id)
            # Pre-fill cash amount: prefer invoice amount, fallback to sale order, then total_price
            amount = 0.0
            if fso.invoice_id:
                amount = abs(fso.invoice_id.amount_total_signed or fso.invoice_id.amount_total or 0.0)
            elif fso.sale_order_id:
                amount = fso.sale_order_id.amount_total or 0.0
            else:
                amount = fso.total_price or 0.0
            res['cash_amount'] = amount

        return res

    def action_confirm_cash_collection(self):
        """Confirm cash collection and return to dashboard"""
        self.ensure_one()

        # Validate cash amount
        if self.cash_amount <= 0:
            raise UserError(_('Cash amount must be greater than zero.'))

        # Update FSO with cash collection data
        self.fso_id.write({
            'cash_received_by_om': True,
            'payment_received_date': self.collection_date,
        })

        # Post message to chatter
        self.fso_id.message_post(
            body=_('<strong>Cash Collected by Operations Manager</strong><br/>'
                   'Amount: %s %s<br/>'
                   'Collected from: %s<br/>'
                   'Collected by: %s<br/>'
                   'Date: %s<br/>'
                   'Notes: %s') % (
                self.cash_amount,
                self.currency_id.symbol,
                self.lead_staff_id.name if self.lead_staff_id else 'N/A',
                self.collected_by_user_id.name,
                self.collection_date.strftime('%Y-%m-%d %H:%M'),
                self.collection_notes or 'No additional notes'
            ),
            subject='Cash Collection Confirmed',
            message_type='notification'
        )

        # Close the FSO if in completed_pending_invoice state
        if self.fso_id.state == 'completed_pending_invoice':
            self.fso_id.action_close_fso()

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
