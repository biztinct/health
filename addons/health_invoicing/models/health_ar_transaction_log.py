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
    active = fields.Boolean('Active', default=True)

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
        'Posting Code',
        readonly=True,
        help='Internal code behind the Posting Path shown on screen.',
    )
    # What the screens show instead of the stored code (UAT round 10, item 7):
    # plain words in the viewer's language. The code stays stored.
    posting_path_label = fields.Char(
        'Posting Path', compute='_compute_posting_path_label')
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

    # Cash hand-in (nurse -> Operations Manager), UAT round 6 item 4. The
    # hand-in moves cash between staff: on carejiox there is no separate
    # "cash held by staff" account (the nurse-app cash payment already sits in
    # the Cash journal), so the row carries no journal entry and changes no
    # balance — it records who, to whom, when and on which receipt.
    handed_over_by_id = fields.Many2one(
        'hr.employee', string='Handed Over By', readonly=True,
        help='Staff member who handed the cash over (cash hand-in rows).')
    received_by_id = fields.Many2one(
        'hr.employee', string='Received By', readonly=True,
        help='Operations Manager who received the cash (cash hand-in rows).')
    receipt_reference = fields.Char(
        'Receipt', readonly=True,
        help='Receipt number given at the cash hand-in.')
    invoice_id = fields.Many2one(
        'account.move', string='Invoice', readonly=True,
        help='Invoice the handed-over cash paid.')
    cash_record_id = fields.Many2one(
        'health.payment.transaction', string='Cash Record', readonly=True,
        index='btree_not_null',
        help='Payment record (PAY…) of the cash that was handed over.')

    @api.model
    def _log_cash_handover(self, txn, move=None):
        """One 'handover' row per cash record when the Operations Manager
        confirms the hand-in. Never creates a payment or touches a balance.
        Reuses (and completes) the row the Cash-in-Transit path already wrote
        for its settlement entry, so the hand-in is logged exactly once."""
        Log = self.sudo()
        txn = txn.sudo()
        row = Log.search([('cash_record_id', '=', txn.id),
                          ('event_type', '=', 'handover')], limit=1)
        if not row and move:
            row = Log.search([('move_id', '=', move.id),
                              ('event_type', '=', 'handover')], limit=1)
        when = txn.cash_delivery_date or fields.Datetime.now()
        booking = txn.fso_id
        vals = {
            'handed_over_by_id': txn.collected_by_id.id or False,
            'received_by_id': txn.received_by_om_id.id or False,
            'receipt_reference': txn.om_receipt_number or False,
            'invoice_id': txn.invoice_id.id or False,
            'cash_record_id': txn.id,
            'payment_id': txn.payment_id.id or False,
        }
        if row:
            row.write(vals)
            return row
        amount = abs(txn.amount or 0.0)
        vals.update({
            'event_type': 'handover',
            'transaction_datetime': when,
            'posting_date': fields.Date.context_today(self, when),
            'company_id': (txn.invoice_id.company_id or txn.payment_id.company_id
                           or self.env.company).id,
            'amount': amount,
            'currency_id': (txn.currency_id or self.env.company.currency_id).id,
            'amount_in_words': _amount_to_vietnamese_words(amount),
            'move_id': move.id if move else False,
            'partner_id': txn.patient_id.id or False,
            'booking_id': booking.id or False,
            'crm_event_id': booking.crm_lead_id.id if booking and 'crm_lead_id' in booking._fields else False,
            'facility_id': booking.facility_id.id if booking else False,
            'prepared_by': self.env.user.id,
            'posting_path': 'HANDOVER→NURSE_CASH→OM',
            'status': 'posted',
        })
        return Log.create(vals)

    @api.depends('posting_path', 'event_type')
    def _compute_posting_path_label(self):
        for rec in self:
            rec.posting_path_label = rec._posting_path_words(
                rec.posting_path, rec.event_type)

    def _posting_path_words(self, code, event_type):
        """Plain words for a stored posting code; never the code itself."""
        _t = self.env._
        refund = event_type == 'refund'
        credit = event_type == 'credit_note'
        if code == 'HANDOVER→NURSE_CASH→OM':
            return _t('Hand-in: nurse → Operations Manager')
        if code == 'NURSE_CASH':
            return _t('Cash refunded by nurse') if refund else _t('Cash collected by nurse')
        if code == 'OFFICE_CASH':
            return (_t('Cash refunded at the office') if refund
                    else _t('Cash received at the office'))
        if code == 'BANK_TRANSFER':
            return _t('Bank transfer refund') if refund else _t('Bank transfer')
        if code == 'DELIVERY→STANDARD':
            return _t('Booking credit note') if credit else _t('Booking invoice')
        if code == 'DELIVERY→PREPAID':
            return (_t('Booking credit note (prepaid package)') if credit
                    else _t('Booking invoice (prepaid package)'))
        if code == 'INVOICE→STANDARD':
            return _t('Invoice')
        if code == 'REFUND→STANDARD':
            return _t('Credit note')
        return _t('Other') if code else ''

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
                # Who actually took the cash (UAT round 10, item 7): a nurse
                # in the field, or somebody at the office. Not every cash
                # payment is a nurse's.
                parts.append('NURSE_CASH' if self._cash_taken_by_field_staff(payment)
                             else 'OFFICE_CASH')
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
    def _is_field_staff_user(self, user):
        """A nurse or doctor who visits clients (their staff record says
        visit staff, or their job is nurse/doctor)."""
        user = user.sudo()
        if not user:
            return False
        if any(user._fields.get(f) and user[f] for f in ('is_nurse_role', 'is_doctor_role')):
            return True
        return bool(self.env['hr.employee'].sudo().with_context(active_test=False).search_count(
            [('user_id', '=', user.id), ('is_healthcare_staff', '=', True)], limit=1))

    @api.model
    def _cash_taken_by_field_staff(self, payment):
        """True when a nurse/doctor took this cash, from the record itself:

        1. the collector the office named when recording it (context
           `health_cash_collected_by`, an employee id);
        2. else the collector on its PAY record(s);
        3. else whoever recorded the payment (the nurse app records as the
           nurse; the office records as the office user).
        """
        Employee = self.env['hr.employee'].sudo().with_context(active_test=False)
        named = self.env.context.get('health_cash_collected_by')
        if named:
            emp = Employee.browse(int(named)).exists()
            if emp:
                return bool(emp.is_healthcare_staff)
        pay = payment.sudo()
        txns = self.env['health.payment.transaction'].sudo().search(
            [('payment_id', '=', pay.id)])
        if 'health_transaction_id' in pay._fields and pay.health_transaction_id:
            txns |= pay.health_transaction_id
        collectors = txns.mapped('collected_by_id')
        if collectors:
            return any(collectors.mapped('is_healthcare_staff'))
        return self._is_field_staff_user(pay.create_uid or self.env.user)

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
    def _payment_own_booking(self, payment):
        Booking = self.env['health.fieldservice.order']
        pay = payment.sudo()
        if 'fieldservice_order_id' in pay._fields and pay.fieldservice_order_id:
            return pay.fieldservice_order_id
        txns = self.env['health.payment.transaction'].sudo().search(
            [('payment_id', '=', pay.id)])
        if pay.health_transaction_id:
            txns |= pay.health_transaction_id
        for candidates in (txns.mapped('fso_id'),
                           txns.mapped('invoice_id.fieldservice_order_id'),
                           pay.reconciled_invoice_ids.mapped('fieldservice_order_id')):
            if len(candidates) == 1:
                return candidates
        if self.env.context.get('active_model') == 'account.move':
            moves = self.env['account.move'].sudo().browse(
                self.env.context.get('active_ids') or []).exists()
            candidates = moves.mapped('fieldservice_order_id')
            if len(candidates) == 1:
                return candidates
        return Booking

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

        # The payment's OWN booking (UAT round 9): the payment's booking, else
        # its PAY record's, else the PAY record's invoice's, else the invoice(s)
        # it paid when they share one booking, else the Register Payment
        # wizard's invoices. Never the client's latest booking: a refund
        # (nothing reconciled) was filed on the client's newest booking
        # (row 1557: BK4107 instead of BK4087). Unresolved stays empty.
        booking = self._payment_own_booking(payment)
        crm_lead = booking.crm_lead_id if booking and 'crm_lead_id' in booking._fields else False
        facility = booking.facility_id if booking and 'facility_id' in booking._fields else False

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
