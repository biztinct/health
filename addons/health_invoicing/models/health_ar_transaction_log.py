# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import uuid


def _amount_to_vietnamese_words(amount):
    """Convert a numeric amount to Vietnamese words.

    Supports amounts up to hàng tỷ (billions).
    Returns e.g. 'ba trăm nghìn đồng' for 300000.
    """
    if amount == 0:
        return 'không đồng'

    ones = ['', 'một', 'hai', 'ba', 'bốn', 'năm', 'sáu', 'bảy', 'tám', 'chín']
    teens = ['mười', 'mười một', 'mười hai', 'mười ba', 'mười bốn', 'mười lăm',
             'mười sáu', 'mười bảy', 'mười tám', 'mười chín']

    def _below_hundred(n):
        if n == 0:
            return ''
        if n < 10:
            return ones[n]
        if n < 20:
            return teens[n - 10]
        ten, one = divmod(n, 10)
        result = ones[ten] + ' mươi'
        if one == 1:
            result += ' mốt'
        elif one == 5:
            result += ' lăm'
        elif one > 0:
            result += ' ' + ones[one]
        return result

    def _below_thousand(n):
        if n == 0:
            return ''
        hundred, remainder = divmod(n, 100)
        parts = []
        if hundred > 0:
            parts.append(ones[hundred] + ' trăm')
        if remainder > 0:
            if hundred > 0 and remainder < 10:
                parts.append('lẻ ' + ones[remainder])
            else:
                parts.append(_below_hundred(remainder))
        return ' '.join(parts)

    # Build groups of thousands
    amount_int = int(round(amount))
    if amount_int == 0:
        return 'không đồng'

    groups = []
    units = ['', 'nghìn', 'triệu', 'tỷ']
    temp = amount_int
    while temp > 0:
        groups.append(temp % 1000)
        temp //= 1000

    parts = []
    for i in range(len(groups) - 1, -1, -1):
        if groups[i] == 0:
            continue
        text = _below_thousand(groups[i])
        if units[i]:
            text += ' ' + units[i]
        parts.append(text)

    return ' '.join(parts) + ' đồng'


class HealthARTransactionLog(models.Model):
    """AR Transaction Log — flat double-entry view for MISA validation.

    Each record represents one accounting event (invoice posting, payment,
    refund, or delivery handover) with both debit and credit accounts in
    a single row.  Auto-populated via hooks on account.move and
    account.payment; not edited by users.
    """
    _name = 'health.ar.transaction.log'
    _description = 'AR Transaction Log'
    _order = 'transaction_datetime desc'
    _rec_name = 'transaction_id'

    # --- Universal fields ---
    transaction_id = fields.Char(
        'Transaction ID',
        required=True,
        readonly=True,
        default=lambda self: str(uuid.uuid4()),
        help='Immutable system ID (UUID)',
        copy=False,
    )
    crm_event_id = fields.Many2one(
        'crm.lead',
        string='CRM Event',
        readonly=True,
        help='Links journal to originating CRM event',
    )
    booking_id = fields.Many2one(
        'health.fieldservice.order',
        string='Booking',
        readonly=True,
        help='Links journal to originating booking',
    )
    event_type = fields.Selection([
        ('payment', 'Payment'),
        ('service_delivery', 'Service Delivery'),
        ('refund', 'Refund'),
        ('handover', 'Handover'),
        ('invoice', 'Invoice'),
        ('credit_note', 'Credit Note'),
    ], string='Event Type', required=True, readonly=True)

    transaction_datetime = fields.Datetime(
        'Transaction DateTime',
        required=True,
        readonly=True,
        default=fields.Datetime.now,
        help='When the event occurred',
    )
    posting_date = fields.Date(
        'Posting Date',
        required=True,
        readonly=True,
        help='Accounting date (usually same day)',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company / Entity',
        required=True,
        readonly=True,
        default=lambda self: self.env.company,
        help='Hanoi vs HCMC',
    )
    company_entity_code = fields.Char(
        'Entity Code',
        compute='_compute_entity_code',
        store=True,
        help='Short code: VAFHS or CSTNVU',
    )

    # Double-entry accounts
    debit_account_id = fields.Many2one(
        'account.account',
        string='Debit Account',
        readonly=True,
    )
    credit_account_id = fields.Many2one(
        'account.account',
        string='Credit Account',
        readonly=True,
    )
    amount = fields.Monetary(
        'Amount',
        currency_field='currency_id',
        required=True,
        readonly=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        readonly=True,
        default=lambda self: self.env.company.currency_id,
    )
    amount_in_words = fields.Char(
        'Amount in Words',
        readonly=True,
        help='Amount in Vietnamese words',
    )

    # Source references
    move_id = fields.Many2one(
        'account.move',
        string='Journal Entry',
        readonly=True,
    )
    payment_id = fields.Many2one(
        'account.payment',
        string='Payment',
        readonly=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Client',
        readonly=True,
    )

    catchment_province_id = fields.Many2one(
        'health.catchment.province',
        string='Catchment Area',
        compute='_compute_catchment_province_id',
        store=True,
        readonly=True,
        help='Catchment area used for filtering and access control'
    )

    @api.depends('booking_id.catchment_province_id',
                 'move_id.catchment_province_id',
                 'payment_id.catchment_province_id',
                 'partner_id.catchment_province_id',
                 'partner_id.primary_facility_id.catchment_province_id')
    def _compute_catchment_province_id(self):
        for log in self:
            partner_catchment = log.partner_id._get_health_catchment_province() if log.partner_id else False
            log.catchment_province_id = (
                log.booking_id.catchment_province_id
                or log.move_id.catchment_province_id
                or log.payment_id.catchment_province_id
                or partner_catchment
                or False
            )

    # Metadata
    prepared_by = fields.Many2one(
        'res.users',
        string='Prepared By',
        readonly=True,
        default=lambda self: self.env.user,
    )
    posting_path = fields.Char(
        'Posting Path',
        readonly=True,
        help='e.g. DELIVERY→PREPAID, DELIVERY→NURSE_CASH',
    )
    status = fields.Selection([
        ('draft', 'Draft'),
        ('posted', 'Posted'),
        ('reversed', 'Reversed'),
    ], string='Status', default='draft', readonly=True)

    # Facility from booking
    facility_id = fields.Many2one(
        'health.facility',
        string='Facility',
        readonly=True,
    )

    @api.depends('company_id')
    def _compute_entity_code(self):
        for rec in self:
            rec.company_entity_code = rec.company_id.name[:10] if rec.company_id else ''

    @api.model
    def _derive_posting_path(self, move=None, payment=None):
        """Derive posting path from payment method + service type."""
        parts = []
        if move and move.fieldservice_order_id:
            parts.append('DELIVERY')
        elif move and move.move_type == 'out_invoice':
            parts.append('INVOICE')
        elif move and move.move_type == 'out_refund':
            parts.append('REFUND')

        if payment:
            journal = payment.journal_id
            if journal and journal.type == 'cash':
                parts.append('NURSE_CASH')
            elif journal and journal.type == 'bank':
                parts.append('BANK_TRANSFER')
            else:
                parts.append('OTHER')
        elif move:
            if move.fieldservice_order_id and move.fieldservice_order_id.package_ids:
                parts.append('PREPAID')
            else:
                parts.append('STANDARD')

        return '→'.join(parts) if parts else 'OTHER'

    @api.model
    def _create_from_move(self, move):
        """Create log entries from a posted account.move."""
        if not move or move.state != 'posted':
            return

        # Determine event type
        if move.move_type == 'out_invoice':
            event_type = 'invoice'
        elif move.move_type == 'out_refund':
            event_type = 'credit_note'
        elif move.move_type == 'entry':
            event_type = 'service_delivery'
        else:
            event_type = 'invoice'

        # Find debit and credit accounts from move lines
        debit_account = False
        credit_account = False
        total_amount = 0.0
        for line in move.line_ids:
            if line.debit > 0 and not debit_account:
                debit_account = line.account_id.id
                total_amount = line.debit
            if line.credit > 0 and not credit_account:
                credit_account = line.account_id.id

        if not total_amount:
            total_amount = abs(move.amount_total)

        # Get booking and CRM link
        booking = move.fieldservice_order_id if hasattr(move, 'fieldservice_order_id') else False
        crm_lead = booking.crm_lead_id if booking and hasattr(booking, 'crm_lead_id') else False
        facility = booking.facility_id if booking and hasattr(booking, 'facility_id') else False

        self.create({
            'crm_event_id': crm_lead.id if crm_lead else False,
            'booking_id': booking.id if booking else False,
            'event_type': event_type,
            'transaction_datetime': fields.Datetime.now(),
            'posting_date': move.date,
            'company_id': move.company_id.id,
            'debit_account_id': debit_account,
            'credit_account_id': credit_account,
            'amount': total_amount,
            'currency_id': move.currency_id.id,
            'amount_in_words': _amount_to_vietnamese_words(total_amount),
            'move_id': move.id,
            'partner_id': move.partner_id.id if move.partner_id else False,
            'prepared_by': self.env.user.id,
            'posting_path': self._derive_posting_path(move=move),
            'status': 'posted',
            'facility_id': facility.id if facility else False,
        })

    @api.model
    def _log_move_posting(self, move, event_type=None, booking=None, partner=None, crm_lead=None):
        """Alias for _create_from_move with optional event_type override.

        Called by nurse_payment_wizard (CIT entries, UR→SR reclassification)
        and cash_delivery_wizard (settlement entries).

        Args:
            move: The posted account.move to log.
            event_type: Override event type (e.g. 'payment', 'handover', 'service_delivery').
            booking: Optional health.fieldservice.order to link (falls back to move.fieldservice_order_id).
            partner: Optional res.partner to link (falls back to move.partner_id).
            crm_lead: Optional crm.lead to link (falls back to booking.crm_lead_id).
        """
        if not move or move.state != 'posted':
            return

        # If caller specifies event_type, use it; otherwise auto-detect
        if event_type:
            # Find debit and credit accounts from move lines
            debit_account = False
            credit_account = False
            total_amount = 0.0
            for line in move.line_ids:
                if line.debit > 0 and not debit_account:
                    debit_account = line.account_id.id
                    total_amount = line.debit
                if line.credit > 0 and not credit_account:
                    credit_account = line.account_id.id

            if not total_amount:
                total_amount = abs(move.amount_total)

            # Use provided context or fall back to auto-detection from the move
            if not booking:
                booking = move.fieldservice_order_id if hasattr(move, 'fieldservice_order_id') else False
            if not crm_lead and booking:
                crm_lead = booking.crm_lead_id if hasattr(booking, 'crm_lead_id') else False
            if not partner:
                partner = move.partner_id if move.partner_id else False
            facility = booking.facility_id if booking and hasattr(booking, 'facility_id') else False

            self.create({
                'crm_event_id': crm_lead.id if crm_lead else False,
                'booking_id': booking.id if booking else False,
                'event_type': event_type,
                'transaction_datetime': fields.Datetime.now(),
                'posting_date': move.date,
                'company_id': move.company_id.id,
                'debit_account_id': debit_account,
                'credit_account_id': credit_account,
                'amount': total_amount,
                'currency_id': move.currency_id.id,
                'amount_in_words': _amount_to_vietnamese_words(total_amount),
                'move_id': move.id,
                'partner_id': partner.id if partner else False,
                'prepared_by': self.env.user.id,
                'posting_path': self._derive_posting_path(move=move),
                'status': 'posted',
                'facility_id': facility.id if facility else False,
            })
        else:
            self._create_from_move(move)

    @api.model
    def _create_from_payment(self, payment):
        """Create log entry from a posted account.payment."""
        if not payment:
            return

        # Determine event type
        if payment.payment_type == 'inbound':
            event_type = 'payment'
        elif payment.payment_type == 'outbound':
            event_type = 'refund'
        else:
            event_type = 'payment'

        # Get debit/credit from the payment move
        debit_account = False
        credit_account = False
        if payment.move_id:
            for line in payment.move_id.line_ids:
                if line.debit > 0 and not debit_account:
                    debit_account = line.account_id.id
                if line.credit > 0 and not credit_account:
                    credit_account = line.account_id.id

        # Try to find booking from reconciled invoices
        booking = False
        crm_lead = False
        facility = False
        if payment.reconciled_invoice_ids:
            for inv in payment.reconciled_invoice_ids:
                if hasattr(inv, 'fieldservice_order_id') and inv.fieldservice_order_id:
                    booking = inv.fieldservice_order_id
                    if hasattr(booking, 'crm_lead_id'):
                        crm_lead = booking.crm_lead_id
                    if hasattr(booking, 'facility_id'):
                        facility = booking.facility_id
                    break

        # Fallback: find invoices from the context (Register Payment wizard source)
        if not booking:
            active_ids = self.env.context.get('active_ids', [])
            active_model = self.env.context.get('active_model', '')
            if active_model == 'account.move' and active_ids:
                invoices = self.env['account.move'].browse(active_ids)
                for inv in invoices:
                    if hasattr(inv, 'fieldservice_order_id') and inv.fieldservice_order_id:
                        booking = inv.fieldservice_order_id
                        if hasattr(booking, 'crm_lead_id'):
                            crm_lead = booking.crm_lead_id
                        if hasattr(booking, 'facility_id'):
                            facility = booking.facility_id
                        break

        # Fallback: find most recent invoice for the same partner that has a booking
        if not booking and payment.partner_id:
            partner_invoices = self.env['account.move'].search([
                ('partner_id', '=', payment.partner_id.id),
                ('move_type', '=', 'out_invoice'),
                ('fieldservice_order_id', '!=', False),
            ], order='id desc', limit=1)
            if partner_invoices:
                booking = partner_invoices.fieldservice_order_id
                if hasattr(booking, 'crm_lead_id'):
                    crm_lead = booking.crm_lead_id
                if hasattr(booking, 'facility_id'):
                    facility = booking.facility_id

        # Fallback: check payment's own fieldservice_order_id
        if not booking and hasattr(payment, 'fieldservice_order_id') and payment.fieldservice_order_id:
            booking = payment.fieldservice_order_id
            if hasattr(booking, 'crm_lead_id'):
                crm_lead = booking.crm_lead_id
            if hasattr(booking, 'facility_id'):
                facility = booking.facility_id

        self.create({
            'crm_event_id': crm_lead.id if crm_lead else False,
            'booking_id': booking.id if booking else False,
            'event_type': event_type,
            'transaction_datetime': fields.Datetime.now(),
            'posting_date': payment.date,
            'company_id': payment.company_id.id,
            'debit_account_id': debit_account,
            'credit_account_id': credit_account,
            'amount': payment.amount,
            'currency_id': payment.currency_id.id,
            'amount_in_words': _amount_to_vietnamese_words(payment.amount),
            'payment_id': payment.id,
            'move_id': payment.move_id.id if payment.move_id else False,
            'partner_id': payment.partner_id.id if payment.partner_id else False,
            'prepared_by': self.env.user.id,
            'posting_path': self._derive_posting_path(payment=payment),
            'status': 'posted',
            'facility_id': facility.id if facility else False,
        })
