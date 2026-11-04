# -*- coding: utf-8 -*-
"""UAT 2026-11-04, round 5 item 4 (PBNK1/2026/00007, BK4056).

(a) A cancelled payment's PAY record follows (status "Payment Cancelled") and
    the booking's Total Paid / payment count, and the invoice's "Payments"
    count, use only payments that stand: BK4056 showed Total Paid 420,000 ₫
    and the invoice "2 Payments" for 210,000 ₫ received.
(b) Cancelling a payment works through the normal cancel — its own draft
    journal entry no longer has to be marked Deleted first — for a Finance
    user who is not the Owner. Posted entries keep every protection.
"""
from odoo import fields
from odoo.tests import TransactionCase, new_test_user, tagged

GROUPS = ','.join([
    'base.group_user', 'account.group_account_invoice',
    'health_base.group_healthcare_finance',
    'health_invoicing.group_health_invoicing_user',
    'health_invoicing.group_health_invoicing_manager',
])


@tagged('post_install', '-at_install')
class TestPaymentCancel(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ICP = cls.env['ir.config_parameter'].sudo()
        ICP.set_param('vietnamese_tax.red_invoice_enabled', 'False')  # no e-invoice step
        facility = cls.env['health.facility'].search([('catchment_province_id', '!=', False)], limit=1)
        cls.province = facility.catchment_province_id
        cls.patient = cls.env['res.partner'].with_context(skip_auto_geocode=True).create({
            'name': 'Payment Cancel Probe', 'is_patient': True,
            'catchment_province_id': cls.province.id, 'primary_facility_id': facility.id})
        cls.fso = cls.env['health.fieldservice.order'].create({
            'patient_id': cls.patient.id, 'facility_id': facility.id,
            'scheduled_datetime': fields.Datetime.now()})
        product = cls.env['product.product'].search([('sale_ok', '=', True)], limit=1)
        cls.invoice = cls.env['account.move'].create({
            'move_type': 'out_invoice', 'partner_id': cls.patient.id,
            'invoice_date': fields.Date.today(),
            'fieldservice_order_id': cls.fso.id,
            'invoice_line_ids': [(0, 0, {'product_id': product.id, 'quantity': 1,
                                         'price_unit': 210000.0, 'tax_ids': [(6, 0, [])]})]})
        cls.invoice.action_post()
        cls.fso.invoice_id = cls.invoice
        cls.finance = new_test_user(cls.env, login='paycancel_finance', groups=GROUPS)
        cls.finance.write({'catchment_province_id': cls.province.id})

    def _pay(self):
        wizard = self.env['account.payment.register'].with_user(self.finance).with_context(
            active_model='account.move', active_ids=self.invoice.ids).create({})
        wizard.action_create_payments()
        return self.env['account.payment'].search(
            [('invoice_ids', 'in', self.invoice.ids)], order='id desc', limit=1)

    def _refresh(self):
        self.env.invalidate_all()
        return self.fso, self.invoice

    def test_a_cancelled_payment_stops_counting(self):
        self.assertFalse(self.finance.has_group('health_base.group_healthcare_owner'))
        first = self._pay()
        fso, invoice = self._refresh()
        tx = self.env['health.payment.transaction'].search([('payment_id', '=', first.id)])
        self.assertEqual(len(tx), 1, 'posting created the PAY record')
        self.assertEqual(fso.total_paid_amount, 210000.0)
        self.assertEqual(invoice.payment_count, 1)

        # (b) reset + cancel, as Finance, with no Deleted mark on the entry
        first.with_user(self.finance).action_draft()
        self.assertEqual(first.move_id.state, 'draft')
        self.assertFalse(first.move_id.deleted)
        first.with_user(self.finance).action_cancel()
        self.assertEqual(first.state, 'canceled')

        fso, invoice = self._refresh()
        self.assertEqual(tx.status, 'cancelled', 'the PAY record follows the payment')
        self.assertEqual(fso.total_paid_amount, 0.0)
        self.assertEqual(fso.payment_transaction_count, 0)
        self.assertEqual(invoice.payment_count, 0)

        # a new payment counts once
        second = self._pay()
        fso, invoice = self._refresh()
        self.assertNotEqual(second, first)
        self.assertEqual(fso.total_paid_amount, 210000.0)
        self.assertEqual(fso.payment_transaction_count, 1)
        self.assertEqual(invoice.payment_count, 1)
        action = invoice.open_payments()
        self.assertEqual(action.get('res_id'), second.id, 'the Payments button opens only the standing one')

    def test_b_reset_to_draft_also_stops_counting(self):
        payment = self._pay()
        payment.with_user(self.finance).action_draft()
        fso, _invoice = self._refresh()
        self.assertEqual(fso.total_paid_amount, 0.0, 'a draft payment is not money received')
        # re-post as the system: this persona has no client-record rule (the
        # live Accountant role reaches clients through its other groups)
        payment.action_post()
        fso, _invoice = self._refresh()
        self.assertEqual(fso.total_paid_amount, 210000.0)
