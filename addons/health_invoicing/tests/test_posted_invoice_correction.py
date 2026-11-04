# -*- coding: utf-8 -*-
"""Owner ruling 2026-11-04 (UAT video item 17): an Operations Manager must not
reset or delete a POSTED customer invoice; Finance (the Accountant role) and
the Owner keep both. Posted invoices are also sent as e-invoices.

The role bundles overlap on this build (the Operations Manager role carries
Finance; the Accountant role carries the Operations Manager group), so the
rule is: Owner, or Finance without the Healthcare Manager group.
"""
from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, new_test_user, tagged

ACCOUNTING = 'base.group_user,account.group_account_invoice'


@tagged('post_install', '-at_install')
class TestPostedInvoiceCorrection(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ops_manager = new_test_user(cls.env, login='uatfix_om', groups=','.join([
            ACCOUNTING, 'health_base.group_healthcare_operations_manager',
            'health_base.group_healthcare_manager', 'health_base.group_healthcare_finance']))
        cls.accountant = new_test_user(cls.env, login='uatfix_acct', groups=','.join([
            ACCOUNTING, 'health_base.group_healthcare_finance',
            'health_base.group_healthcare_operations_manager']))
        cls.owner = new_test_user(cls.env, login='uatfix_owner', groups=','.join([
            ACCOUNTING, 'health_base.group_healthcare_owner']))
        cls.partner = cls.env['res.partner'].create({'name': 'UAT Fix Invoice Client'})
        product = cls.env['product.product'].search([('sale_ok', '=', True)], limit=1) \
            or cls.env['product.product'].create({'name': 'UAT Fix Service', 'type': 'service'})
        cls.product = product

    def _posted(self):
        move = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'invoice_date': fields.Date.today(),
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product.id, 'quantity': 1, 'price_unit': 100.0,
                'tax_ids': [(6, 0, [])],
            })],
        })
        move.action_post()
        return move

    def test_01_flag_per_person(self):
        move = self._posted()
        self.assertFalse(move.with_user(self.ops_manager).health_can_correct_posted)
        self.assertTrue(move.with_user(self.accountant).health_can_correct_posted)
        self.assertTrue(move.with_user(self.owner).health_can_correct_posted)

    def test_02_operations_manager_cannot_reset_a_posted_invoice(self):
        move = self._posted()
        with self.assertRaises(UserError):
            move.with_user(self.ops_manager).button_draft()
        self.assertEqual(move.state, 'posted')

    def test_03_finance_and_owner_can(self):
        for user in (self.accountant, self.owner):
            move = self._posted()
            move.with_user(user).button_draft()
            self.assertEqual(move.state, 'draft', user.login)

    def test_04_form_hides_the_buttons_on_the_flag(self):
        arch = self.env['account.move'].get_view(
            self.env.ref('account.view_move_form').id, 'form')['arch']
        self.assertIn('health_can_correct_posted', arch)
        from lxml import etree
        doc = etree.fromstring(arch)
        for name in ('button_draft', 'action_open_delete_wizard'):
            buttons = doc.xpath("//header/button[@name='%s']" % name)
            self.assertTrue(buttons, name)
            for button in buttons:
                self.assertIn('health_can_correct_posted', button.get('invisible') or '', name)
