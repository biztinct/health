# -*- coding: utf-8 -*-
"""UAT round 11, item 3: only cash a nurse/doctor collected in the field is
"Cash Pending Delivery"; cash taken at the office is received at once."""
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestCashCustody(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['ir.config_parameter'].sudo().set_param('vietnamese_tax.red_invoice_enabled', 'False')
        facility = cls.env['health.facility'].search([('catchment_province_id', '!=', False)], limit=1)
        cls.patient = cls.env['res.partner'].with_context(skip_auto_geocode=True).create({
            'name': 'R11 custody probe', 'is_patient': True,
            'catchment_province_id': facility.catchment_province_id.id,
            'primary_facility_id': facility.id})
        cls.cash = cls.env['account.journal'].search(
            [('type', '=', 'cash'), ('company_id', '=', cls.env.company.id)], limit=1)
        cls.nurse_user = new_test_user(cls.env, login='r11.custody.nurse')
        cls.nurse = cls.env['hr.employee'].create({
            'name': 'R11 custody nurse', 'user_id': cls.nurse_user.id,
            'is_healthcare_staff': True})
        cls.office_user = new_test_user(cls.env, login='r11.custody.office')
        cls.office = cls.env['hr.employee'].create({
            'name': 'R11 custody office', 'user_id': cls.office_user.id})
        cls.Txn = cls.env['health.payment.transaction']

    def _txn(self, user=None, **vals):
        Txn = self.Txn.with_user(user).sudo() if user else self.Txn
        base = {'patient_id': self.patient.id, 'amount': 100000, 'payment_method': 'cash',
                'transaction_type': 'immediate', 'status': 'pending_delivery'}
        base.update(vals)
        return Txn.create(base)

    def _payment(self, user):
        payment = self.env['account.payment'].with_user(user).sudo().create({
            'payment_type': 'inbound', 'partner_type': 'customer',
            'partner_id': self.patient.id, 'amount': 90000, 'journal_id': self.cash.id})
        payment.action_post()
        return payment

    def test_1_office_cash_is_not_pending(self):
        txn = self._txn(user=self.office_user, collected_by_id=self.office.id)
        self.assertEqual(txn.status, 'collected')
        txn = self._txn(user=self.office_user)
        self.assertNotEqual(txn.status, 'pending_delivery')

    def test_2_field_cash_stays_pending(self):
        self.assertEqual(self._txn(collected_by_id=self.nurse.id).status, 'pending_delivery')
        self.assertEqual(self._txn(user=self.nurse_user).status, 'pending_delivery')

    def test_3_payment_wizard_write_path(self):
        # The payment wizard writes "pending delivery" on the PAY record the
        # posted payment created: kept for a nurse's cash, not for the office's.
        office_pay = self._payment(self.office_user)
        office_txn = self.Txn.search([('payment_id', '=', office_pay.id)])
        office_txn.write({'status': 'pending_delivery', 'transaction_notes': 'x'})
        self.assertEqual(office_txn.status, 'reconciled')
        self.assertEqual(office_txn.transaction_notes, 'x', 'the other values are written')
        nurse_pay = self._payment(self.nurse_user)
        nurse_txn = self.Txn.search([('payment_id', '=', nurse_pay.id)])
        nurse_txn.write({'status': 'pending_delivery'})
        self.assertEqual(nurse_txn.status, 'pending_delivery')

    def test_3b_collector_named_in_the_same_write(self):
        office_pay = self._payment(self.office_user)
        txn = self.Txn.search([('payment_id', '=', office_pay.id)])
        txn.write({'status': 'pending_delivery', 'collected_by_id': self.nurse.id})
        self.assertEqual(txn.status, 'pending_delivery', 'the office recorded a nurse\'s cash')

    def test_4_mixed_write(self):
        office = self._txn(user=self.office_user, status='collected')
        field = self._txn(collected_by_id=self.nurse.id, status='collected')
        (office | field).write({'status': 'pending_delivery'})
        self.assertEqual(office.status, 'collected')
        self.assertEqual(field.status, 'pending_delivery')
