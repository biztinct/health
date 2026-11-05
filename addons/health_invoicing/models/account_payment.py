# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class HealthcarePayment(models.Model):
    """
    Healthcare Payment extending standard Odoo account.payment functionality
    Inherits from account.payment to leverage all standard payment features
    """
    _inherit = 'account.payment'

    active = fields.Boolean(default=True)

    # Basic healthcare fields only - test if this resolves the '_unknown' error
    healthcare_payment_type = fields.Selection([
        ('patient_direct', 'Direct Patient Payment'),
        ('insurance_primary', 'Primary Insurance Payment'),
        ('insurance_secondary', 'Secondary Insurance Payment'),
        ('government_subsidy', 'Government Healthcare Subsidy'),
        ('corporate_account', 'Corporate Healthcare Account'),
        ('installment', 'Installment Payment'),
        ('deposit', 'Service Deposit'),
        ('refund', 'Service Refund'),
    ], string='Healthcare Payment Type', help='Type of healthcare payment')
    
    patient_id = fields.Many2one(
        'res.partner',
        string='Client',
        domain="[('is_patient', '=', True)]",
        help='client making or benefiting from this payment'
    )
    
    fieldservice_order_id = fields.Many2one(
        'health.fieldservice.order',
        string='Booking',
        help='Booking this payment is for'
    )

    catchment_province_id = fields.Many2one(
        'health.catchment.province',
        string='Catchment Area',
        compute='_compute_catchment_province_id',
        store=True,
        readonly=True,
        help='Catchment area used for filtering and access control'
    )

    @api.depends('fieldservice_order_id.catchment_province_id',
                 'patient_id.catchment_province_id',
                 'patient_id.primary_facility_id.catchment_province_id',
                 'partner_id.catchment_province_id',
                 'partner_id.primary_facility_id.catchment_province_id',
                 'move_id.catchment_province_id')
    def _compute_catchment_province_id(self):
        for payment in self:
            patient_catchment = payment.patient_id._get_health_catchment_province() if payment.patient_id else False
            partner_catchment = payment.partner_id._get_health_catchment_province() if payment.partner_id else False
            payment.catchment_province_id = (
                payment.fieldservice_order_id.catchment_province_id
                or patient_catchment
                or partner_catchment
                or payment.move_id.catchment_province_id
                or False
            )
    
    appointment_id = fields.Many2one(
        'health.appointment',
        string='Appointment',
        help='Healthcare appointment this payment is for'
    )
    
    health_transaction_id = fields.Many2one(
        'health.payment.transaction',
        string='Healthcare Transaction',
        help='Related healthcare payment transaction',
        copy=False
    )

    # ------------------------------------------------------------------
    # Cancel / reset (UAT 2026-11-04, PBNK1/2026/00007)
    # ------------------------------------------------------------------
    def _health_transactions(self):
        return self.env['health.payment.transaction'].sudo().search(
            [('payment_id', 'in', self.ids)])

    def action_cancel(self):
        """A cancel removes the payment's own DRAFT journal entry (standard
        behaviour). The record-lifecycle guard refused that unless the entry
        had first been marked Deleted, so a cancel needed a manual soft
        delete. The draft entry of the payment being cancelled is part of the
        cancel itself: removed after the user's own right to delete it is
        checked, and written to the lifecycle log. Posted entries are not
        touched here — the standard cancel handles them, as the user."""
        draft_moves = self.move_id.filtered(lambda m: m.state == 'draft')
        if draft_moves:
            draft_moves.check_access('unlink')
            reason = _('Draft entry of cancelled payment %s',
                       ', '.join(self.mapped('name')))
            draft_moves.with_context(archive_reason=reason)._health_log_archive('purge')
            draft_moves.sudo().unlink()
        res = super().action_cancel()
        # The PAY record follows: cancelled, never counted as paid.
        self._health_transactions().filtered(
            lambda t: t.status != 'cancelled').write({'status': 'cancelled'})
        return res

    def action_post(self):
        """Override action_post to log payments to AR Transaction Log
        and auto-create health.payment.transaction records."""
        result = super().action_post()
        # A payment posted again after a cancel brings its PAY record back.
        self.filtered(lambda p: p.state in ('paid', 'in_process'))._health_transactions().filtered(
            lambda t: t.status == 'cancelled').write({'status': 'reconciled'})
        for payment in self:
            # Odoo 19 states: draft, in_process, paid, canceled, rejected
            # After action_post, state will be 'in_process' or 'paid' (never 'posted')
            if payment.state in ('paid', 'in_process'):
                # 1) AR Transaction Log
                try:
                    self.env['health.ar.transaction.log']._create_from_payment(payment)
                except Exception as e:
                    _logger.warning(
                        'Failed to create AR transaction log for payment %s: %s',
                        payment.display_name, e,
                    )

                # 2) Auto-create health.payment.transaction if not already linked
                if not payment.health_transaction_id:
                    try:
                        payment._create_health_payment_transaction()
                    except Exception as e:
                        _logger.warning(
                            'Failed to create health payment transaction for payment %s: %s',
                            payment.display_name, e,
                        )
        return result

    def _create_health_payment_transaction(self):
        """Create a health.payment.transaction record from this payment."""
        self.ensure_one()

        # Determine booking and invoice from reconciled invoices
        booking = False
        invoice = False
        patient = self.partner_id

        if self.fieldservice_order_id:
            booking = self.fieldservice_order_id

        if self.reconciled_invoice_ids:
            for inv in self.reconciled_invoice_ids:
                if not invoice:
                    invoice = inv
                if not booking and hasattr(inv, 'fieldservice_order_id') and inv.fieldservice_order_id:
                    booking = inv.fieldservice_order_id
                    break

        # Fallback: find invoices from the context (Register Payment wizard source)
        if not booking or not invoice:
            active_ids = self.env.context.get('active_ids', [])
            active_model = self.env.context.get('active_model', '')
            if active_model == 'account.move' and active_ids:
                ctx_invoices = self.env['account.move'].browse(active_ids)
                for inv in ctx_invoices:
                    if not invoice:
                        invoice = inv
                    if not booking and hasattr(inv, 'fieldservice_order_id') and inv.fieldservice_order_id:
                        booking = inv.fieldservice_order_id
                        break

        # No guessing (UAT round 9, lead ruling): the client's latest invoice
        # is NOT this payment's booking or invoice. What the payment itself
        # does not give stays empty.

        # Fallback: check payment's own fieldservice_order_id (advance payments)
        if not booking and self.fieldservice_order_id:
            booking = self.fieldservice_order_id

        # Fallback: check payment's journal entry for booking link
        if not booking and self.move_id and hasattr(self.move_id, 'fieldservice_order_id') and self.move_id.fieldservice_order_id:
            booking = self.move_id.fieldservice_order_id

        # Determine payment method from journal type
        journal_type = self.journal_id.type if self.journal_id else ''
        if journal_type == 'cash':
            payment_method = 'cash'
        elif journal_type == 'bank':
            payment_method = 'bank_transfer'
        else:
            payment_method = 'other'

        # Determine transaction type
        if self.payment_type == 'inbound':
            transaction_type = 'immediate'
        else:
            transaction_type = 'refund'

        vals = {
            'patient_id': patient.id if patient else False,
            'fso_id': booking.id if booking else False,
            'invoice_id': invoice.id if invoice else False,
            'amount': self.amount,
            'payment_method': payment_method,
            'transaction_type': transaction_type,
            'status': 'reconciled',
            'transaction_date': fields.Datetime.now(),
            'payment_id': self.id,
            'transaction_notes': _('Auto-created from payment %s') % self.display_name,
        }

        # Only create if patient exists (required field on health.payment.transaction)
        if not vals.get('patient_id'):
            _logger.info(
                'Skipping health payment transaction for payment %s — no patient/partner.',
                self.display_name,
            )
            return

        transaction = self.env['health.payment.transaction'].create(vals)
        self.health_transaction_id = transaction.id
        _logger.info(
            'Created health payment transaction %s for payment %s',
            transaction.name, self.display_name,
        )
