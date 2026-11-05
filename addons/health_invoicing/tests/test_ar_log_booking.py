# -*- coding: utf-8 -*-
"""UAT round 9, item 1: an AR transaction log row names the payment's OWN
booking. A refund (nothing reconciled to an invoice) was filed on the
client's NEWEST booking (row 1557: BK4107 instead of BK4087) through a
"client's latest invoice" fallback. Never guess; unresolved stays empty."""
from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestArLogBooking(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['ir.config_parameter'].sudo().set_param('vietnamese_tax.red_invoice_enabled', 'False')
        facility = cls.env['health.facility'].search([('catchment_province_id', '!=', False)], limit=1)
        cls.patient = cls.env['res.partner'].with_context(skip_auto_geocode=True).create({
            'name': 'AR Log Booking Probe', 'is_patient': True,
            'catchment_province_id': facility.catchment_province_id.id,
            'primary_facility_id': facility.id})
        cls.product = cls.env['product.product'].search([('sale_ok', '=', True)], limit=1)
        Booking = cls.env['health.fieldservice.order']
        cls.old = Booking.create({'patient_id': cls.patient.id, 'facility_id': facility.id,
                                  'scheduled_datetime': fields.Datetime.now()})
        cls.inv_old = cls._invoice(cls.old)
        # The client's NEWER booking with its own invoice: the bait.
        cls.new = Booking.create({'patient_id': cls.patient.id, 'facility_id': facility.id,
                                  'scheduled_datetime': fields.Datetime.now()})
        cls.inv_new = cls._invoice(cls.new)
        cls.cash = cls.env['account.journal'].search(
            [('type', '=', 'cash'), ('company_id', '=', cls.inv_old.company_id.id)], limit=1)

    @classmethod
    def _invoice(cls, booking):
        inv = cls.env['account.move'].create({
            'move_type': 'out_invoice', 'partner_id': cls.patient.id,
            'invoice_date': fields.Date.today(), 'fieldservice_order_id': booking.id,
            'invoice_line_ids': [(0, 0, {'product_id': cls.product.id, 'quantity': 1,
                                         'price_unit': 100000.0, 'tax_ids': [(6, 0, [])]})]})
        inv.action_post()
        booking.invoice_id = inv
        return inv

    def _row(self, payment):
        return self.env['health.ar.transaction.log'].search(
            [('payment_id', '=', payment.id)], order='id desc', limit=1)

    def test_1_refund_row_names_the_refunded_booking(self):
        wizard = self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=self.inv_old.ids).create(
            {'journal_id': self.cash.id} if self.cash else {})
        wizard.action_create_payments()
        payment = self.env['account.payment'].search(
            [('invoice_ids', 'in', self.inv_old.ids)], order='id desc', limit=1)
        self.assertEqual(self._row(payment).booking_id, self.old)
        txn = self.env['health.payment.transaction'].search([('payment_id', '=', payment.id)], limit=1)
        txn.fso_id = self.old
        txn.action_create_refund()
        refund_txn = self.env['health.payment.transaction'].search(
            [('transaction_type', '=', 'refund'), ('fso_id', '=', self.old.id)], order='id desc', limit=1)
        row = self._row(refund_txn.payment_id)
        self.assertEqual(row.event_type, 'refund')
        self.assertEqual(row.booking_id, self.old, 'the refunded booking, not the newest one')

    def test_2_unresolvable_booking_stays_empty(self):
        payment = self.env['account.payment'].create({
            'payment_type': 'inbound', 'partner_type': 'customer',
            'partner_id': self.patient.id, 'amount': 50000,
            'journal_id': self.cash.id if self.cash else False})
        payment.action_post()
        self.assertFalse(self._row(payment).booking_id, 'never the client\'s latest booking')
        # Same rule for the PAY record created with it (lead ruling, round 9).
        txn = self.env['health.payment.transaction'].search([('payment_id', '=', payment.id)])
        self.assertTrue(txn, 'the PAY record is still created')
        self.assertFalse(txn.fso_id, 'PAY record: no booking guessed')
        self.assertFalse(txn.invoice_id, 'PAY record: no invoice guessed')

    def test_2b_pay_record_takes_the_payments_own_booking(self):
        payment = self.env['account.payment'].create({
            'payment_type': 'inbound', 'partner_type': 'customer',
            'partner_id': self.patient.id, 'amount': 50000,
            'fieldservice_order_id': self.old.id,
            'journal_id': self.cash.id if self.cash else False})
        payment.action_post()
        txn = self.env['health.payment.transaction'].search([('payment_id', '=', payment.id)])
        self.assertEqual(txn.fso_id, self.old)
        self.assertEqual(self._row(payment).booking_id, self.old)

    def test_3_resolver_order(self):
        Log = self.env['health.ar.transaction.log']
        payment = self.env['account.payment'].create({
            'payment_type': 'outbound', 'partner_type': 'customer',
            'partner_id': self.patient.id, 'amount': 1000,
            'fieldservice_order_id': self.old.id})
        self.assertEqual(Log._payment_own_booking(payment), self.old)
        bare = self.env['account.payment'].create({
            'payment_type': 'outbound', 'partner_type': 'customer',
            'partner_id': self.patient.id, 'amount': 1000})
        self.assertFalse(Log._payment_own_booking(bare))
