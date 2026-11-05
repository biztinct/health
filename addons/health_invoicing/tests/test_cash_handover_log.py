# -*- coding: utf-8 -*-
"""UAT round 6, item 4 (docs/handovers/uat-video-fixes-2026-11-04.md §8):
the nurse → Operations Manager cash hand-in (Mark Cash Delivered to OM ›
Confirm Cash Receipt) writes ONE row in the AR transaction log — amount, from
the nurse, to the OM, time, receipt, source payment and invoice — and never a
customer payment or a change to the invoice balance. carejiox has no separate
"cash held by staff" account (the nurse-app cash already sits in the Cash
journal), so the row carries no journal entry.
"""
from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestCashHandoverLog(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ICP = cls.env['ir.config_parameter'].sudo()
        ICP.set_param('vietnamese_tax.red_invoice_enabled', 'False')  # no e-invoice step
        facility = cls.env['health.facility'].search([('catchment_province_id', '!=', False)], limit=1)
        cls.patient = cls.env['res.partner'].with_context(skip_auto_geocode=True).create({
            'name': 'Hand-in Probe Client', 'is_patient': True,
            'catchment_province_id': facility.catchment_province_id.id,
            'primary_facility_id': facility.id})
        cls.fso = cls.env['health.fieldservice.order'].create({
            'patient_id': cls.patient.id, 'facility_id': facility.id,
            'scheduled_datetime': fields.Datetime.now()})
        product = cls.env['product.product'].search([('sale_ok', '=', True)], limit=1)
        cls.invoice = cls.env['account.move'].create({
            'move_type': 'out_invoice', 'partner_id': cls.patient.id,
            'invoice_date': fields.Date.today(),
            'fieldservice_order_id': cls.fso.id,
            'invoice_line_ids': [(0, 0, {'product_id': product.id, 'quantity': 1,
                                         'price_unit': 500000.0, 'tax_ids': [(6, 0, [])]})]})
        cls.invoice.action_post()
        cls.fso.invoice_id = cls.invoice
        Emp = cls.env['hr.employee']
        cls.nurse = Emp.create({'name': 'Hand-in Probe Nurse', 'is_healthcare_staff': True})
        cls.om = Emp.create({'name': 'Hand-in Probe OM', 'is_healthcare_staff': True})
        cash = cls.env['account.journal'].search(
            [('type', '=', 'cash'), ('company_id', '=', cls.invoice.company_id.id)], limit=1)
        # Pay Now › Cash in the nurse app: a standard cash payment, then the
        # PAY record waits for the hand-in.
        wizard = cls.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=cls.invoice.ids).create(
            {'journal_id': cash.id} if cash else {})
        wizard.action_create_payments()
        cls.payment = cls.env['account.payment'].search(
            [('invoice_ids', 'in', cls.invoice.ids)], order='id desc', limit=1)
        cls.txn = cls.env['health.payment.transaction'].search(
            [('payment_id', '=', cls.payment.id)], limit=1)
        cls.txn.write({'payment_method': 'cash', 'status': 'pending_delivery',
                       'collected_by_id': cls.nurse.id, 'fso_id': cls.fso.id,
                       'invoice_id': cls.invoice.id})

    def _hand_in(self, auto_reconcile):
        wizard = self.env['health.cash.delivery.wizard'].create({
            'transaction_id': self.txn.id,
            'om_employee_id': self.om.id,
            'om_receipt_number': 'R6-HANDIN-0001',
            'amount_verified': True,
            'auto_reconcile_ar': auto_reconcile,
            'create_bank_deposit': False,
        })
        wizard.action_confirm_cash_delivery()

    def _rows(self):
        return self.env['health.ar.transaction.log'].search(
            [('cash_record_id', '=', self.txn.id), ('event_type', '=', 'handover')])

    def test_1_hand_in_is_logged_once_with_who_when_receipt(self):
        self.assertTrue(self.txn, 'posting the cash payment made the PAY record')
        payments_before = self.env['account.payment'].search_count([])
        residual_before = self.invoice.amount_residual
        self._hand_in(auto_reconcile=False)   # as AR-03 records it
        row = self._rows()
        self.assertEqual(len(row), 1)
        self.assertEqual(row.amount, self.txn.amount)
        self.assertEqual(row.handed_over_by_id, self.nurse)
        self.assertEqual(row.received_by_id, self.om)
        self.assertEqual(row.receipt_reference, 'R6-HANDIN-0001')
        self.assertEqual(row.transaction_datetime, self.txn.cash_delivery_date)
        self.assertEqual(row.payment_id, self.payment)
        self.assertEqual(row.invoice_id, self.invoice)
        self.assertEqual(row.partner_id, self.patient)
        self.assertEqual(row.status, 'posted')
        self.assertFalse(row.move_id, 'no journal entry: no separate staff-cash account')
        # Never a customer payment, never a balance change.
        self.assertEqual(self.env['account.payment'].search_count([]), payments_before)
        self.invoice.invalidate_recordset()
        self.assertEqual(self.invoice.amount_residual, residual_before)
        # Logging again (any path) keeps one row.
        self.env['health.ar.transaction.log']._log_cash_handover(self.txn)
        self.assertEqual(len(self._rows()), 1)

    def test_2_auto_reconcile_path_also_logs_once(self):
        payments_before = self.env['account.payment'].search_count([])
        self._hand_in(auto_reconcile=True)
        self.assertEqual(len(self._rows()), 1)
        self.assertEqual(self.env['account.payment'].search_count([]), payments_before)
