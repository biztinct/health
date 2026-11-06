# -*- coding: utf-8 -*-
"""UAT round 10, item 7: the AR log tells a nurse's cash from the office's,
and the screen shows plain words instead of the stored code."""
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestArLogPostingPath(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['ir.config_parameter'].sudo().set_param('vietnamese_tax.red_invoice_enabled', 'False')
        cls.Log = cls.env['health.ar.transaction.log']
        facility = cls.env['health.facility'].search([('catchment_province_id', '!=', False)], limit=1)
        cls.patient = cls.env['res.partner'].with_context(skip_auto_geocode=True).create({
            'name': 'R10 path probe', 'is_patient': True,
            'catchment_province_id': facility.catchment_province_id.id,
            'primary_facility_id': facility.id})
        company = cls.env.company
        cls.cash = cls.env['account.journal'].search(
            [('type', '=', 'cash'), ('company_id', '=', company.id)], limit=1)
        cls.bank = cls.env['account.journal'].search(
            [('type', '=', 'bank'), ('company_id', '=', company.id)], limit=1)
        cls.nurse_user = new_test_user(cls.env, login='r10.path.nurse')
        cls.nurse = cls.env['hr.employee'].create({
            'name': 'R10 path nurse', 'user_id': cls.nurse_user.id,
            'is_healthcare_staff': True})
        cls.office_user = new_test_user(cls.env, login='r10.path.office')
        cls.office = cls.env['hr.employee'].create({
            'name': 'R10 path office', 'user_id': cls.office_user.id})

    def _pay(self, user=None, journal=None, ptype='inbound', **ctx):
        Payment = self.env['account.payment']
        if user:
            Payment = Payment.with_user(user).sudo()
        payment = Payment.with_context(**ctx).create({
            'payment_type': ptype, 'partner_type': 'customer',
            'partner_id': self.patient.id, 'amount': 120000,
            'journal_id': (journal or self.cash).id})
        payment.action_post()
        return self.Log.search([('payment_id', '=', payment.id)], order='id desc', limit=1)

    def test_1_office_cash_is_not_nurse_cash(self):
        row = self._pay(user=self.office_user)
        self.assertEqual(row.posting_path, 'OFFICE_CASH')
        self.assertEqual(row.posting_path_label, 'Cash received at the office')

    def test_2_nurse_cash(self):
        row = self._pay(user=self.nurse_user)
        self.assertEqual(row.posting_path, 'NURSE_CASH')
        self.assertEqual(row.posting_path_label, 'Cash collected by nurse')

    def test_3_office_records_cash_a_nurse_collected(self):
        row = self._pay(user=self.office_user, health_cash_collected_by=self.nurse.id)
        self.assertEqual(row.posting_path, 'NURSE_CASH')

    def test_4_bank_and_refund_words(self):
        if self.bank:
            row = self._pay(journal=self.bank)
            self.assertEqual(row.posting_path, 'BANK_TRANSFER')
            self.assertEqual(row.posting_path_label, 'Bank transfer')
        refund = self._pay(user=self.office_user, ptype='outbound')
        self.assertEqual(refund.event_type, 'refund')
        self.assertEqual(refund.posting_path_label, 'Cash refunded at the office')

    def test_5_no_raw_code_on_screen(self):
        words = self.Log._posting_path_words
        cases = {
            ('HANDOVER→NURSE_CASH→OM', 'handover'): 'Hand-in: nurse → Operations Manager',
            ('DELIVERY→STANDARD', 'invoice'): 'Booking invoice',
            ('DELIVERY→STANDARD', 'credit_note'): 'Booking credit note',
            ('DELIVERY→PREPAID', 'invoice'): 'Booking invoice (prepaid package)',
            ('INVOICE→STANDARD', 'invoice'): 'Invoice',
            ('REFUND→STANDARD', 'credit_note'): 'Credit note',
            ('NURSE_CASH', 'refund'): 'Cash refunded by nurse',
            ('SOMETHING_NEW', 'payment'): 'Other',
        }
        for (code, event), expected in cases.items():
            self.assertEqual(words(code, event), expected, code)
            self.assertNotIn('_', words(code, event))
        vi = self.Log.with_context(lang='vi_VN')
        if self.env['res.lang']._lang_get('vi_VN'):
            self.assertEqual(vi._posting_path_words('OFFICE_CASH', 'payment'),
                             'Tiền mặt nhận tại văn phòng')
