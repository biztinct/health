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
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, new_test_user, tagged

# As the live Operations Manager role (om_hn): Employees / Officer included.
OM_GROUPS = ('base.group_user,hr.group_hr_user,health_base.group_healthcare_operations_manager,'
             'health_base.group_healthcare_manager')


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
        cls.area = facility.catchment_province_id
        cls.nurse = Emp.create({'name': 'Hand-in Probe Nurse', 'is_healthcare_staff': True})
        # The receiving Operations Manager: an OM user of this area with an
        # employee that is NOT visit staff (UAT round 7).
        om_user = new_test_user(cls.env, login='handin_probe_om', groups=OM_GROUPS)
        om_user.catchment_province_id = cls.area
        cls.om = Emp.create({'name': 'Hand-in Probe OM', 'user_id': om_user.id})
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

    # ------------------------------------------------------------ round 7
    def test_3_recipient_picker_offers_area_oms_and_owners_only(self):
        """Mark Cash Delivered to OM: the "Operations Manager" picker lists the
        area's Operations Managers (default: me) and the Owners — never visit
        staff, never the CRM/Accountant roles, never another area's OM."""
        Emp = self.env['hr.employee']
        other_area = self.env['health.catchment.province'].create(
            {'name': 'Hand-in Other Area', 'code': 'HOA'})
        om_other_user = new_test_user(self.env, login='handin_probe_om_b', groups=OM_GROUPS)
        om_other_user.catchment_province_id = other_area
        om_other = Emp.create({'name': 'Hand-in Probe OM B', 'user_id': om_other_user.id})
        owner_user = new_test_user(self.env, login='handin_probe_owner', groups=(
            'base.group_user,health_base.group_healthcare_owner'))
        owner = Emp.create({'name': 'Hand-in Probe Owner', 'user_id': owner_user.id})
        crm_user = new_test_user(self.env, login='handin_probe_crm', groups=(
            'base.group_user,health_base.group_healthcare_operations_manager'))
        crm_user.catchment_province_id = self.area
        crm = Emp.create({'name': 'Hand-in Probe CRM', 'user_id': crm_user.id})

        sysadmin_user = new_test_user(self.env, login='handin_probe_sysadmin', groups=(
            'base.group_user,base.group_system,health_base.group_healthcare_owner'))
        sysadmin = Emp.create({'name': 'Hand-in Probe Platform', 'user_id': sysadmin_user.id})

        om_user = self.om.user_id
        Wizard = self.env['health.cash.delivery.wizard'].with_user(om_user).with_context(
            default_transaction_id=self.txn.id)
        defaults = Wizard.default_get(['transaction_id', 'om_employee_id'])
        self.assertEqual(defaults.get('om_employee_id'), self.om.id, 'defaults to me')

        offered = self.env['health.cash.delivery.wizard']._cash_recipients(self.txn)
        self.assertIn(self.om, offered)
        self.assertIn(owner, offered)
        for absent in (om_other, self.nurse, crm, sysadmin):
            self.assertNotIn(absent, offered, absent.name)
        self.assertFalse(self.om.is_healthcare_staff, 'OMs are not made visit staff')

        wizard = self.env['health.cash.delivery.wizard'].create({
            'transaction_id': self.txn.id, 'om_employee_id': om_other.id,
            'om_receipt_number': 'R7-WRONG-AREA', 'amount_verified': True,
            'auto_reconcile_ar': False})
        with self.assertRaises(UserError):
            wizard.action_confirm_cash_delivery()

    def test_4_picker_cannot_create_employees(self):
        arch = self.env['health.cash.delivery.wizard'].get_view(view_type='form')['arch']
        self.assertIn("'no_create': True", arch)
        self.assertIn("('id', 'in', om_candidate_ids)",
                      self.env['health.cash.delivery.wizard']._fields['om_employee_id'].domain)
