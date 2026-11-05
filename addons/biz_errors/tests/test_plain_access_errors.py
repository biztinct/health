# Part of biz_errors — the branded breakdown screen.
# License LGPL-3.
"""UAT round 6, item 9a: an access refusal reads as one plain sentence for a
person using the product — no technical model name, no joke — in their
language; system administrators keep the technical message."""
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestPlainAccessErrors(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = new_test_user(cls.env, login='plain_access_probe', groups='base.group_user')
        cls.admin = new_test_user(cls.env, login='plain_access_admin',
                                  groups='base.group_user,base.group_system')

    def _acl_message(self, user):
        with self.assertRaises(AccessError) as cm:
            self.env['ir.config_parameter'].with_user(user).check_access('read')
        return str(cm.exception)

    def test_acl_refusal_is_plain_for_staff(self):
        msg = self._acl_message(self.user)
        self.assertIn('You do not have access to this', msg)
        self.assertIn('Ask your administrator', msg)
        self.assertNotIn('ir.config_parameter', msg)
        self.assertNotIn('cookies', msg)

    def test_record_rule_refusal_is_plain_for_staff(self):
        # res.company: an internal user may only read the companies they belong to.
        other = self.env['res.company'].create({'name': 'Plain Access Other Co'})
        err = self.env['ir.rule'].with_user(self.user)._make_access_error('write', other)
        self.assertIsInstance(err, AccessError)
        msg = str(err)
        self.assertNotIn('(res.company)', msg)
        self.assertNotIn('freshly baked', msg)
        self.assertIn('You cannot change this', msg)

    def test_refusal_in_vietnamese(self):
        self.env['res.lang']._activate_lang('vi_VN')
        self.user.lang = 'vi_VN'
        msg = self._acl_message(self.user)
        self.assertIn('Bạn không có quyền truy cập', msg)

    def test_admin_keeps_the_technical_message(self):
        other = self.env['res.company'].create({'name': 'Plain Access Admin Co'})
        err = self.env['ir.rule'].with_user(self.admin)._make_access_error('read', other)
        self.assertIn('res.company', str(err))


@tagged('post_install', '-at_install')
class TestPlainPdfFailure(TransactionCase):
    """UAT round 7: a PDF-engine failure reads as one neutral sentence; the
    engine output (folder paths, vendor name) only goes to the server log."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = new_test_user(cls.env, login='plain_pdf_probe', groups='base.group_user')
        cls.admin = new_test_user(cls.env, login='plain_pdf_admin',
                                  groups='base.group_user,base.group_system')
        cls.report = cls.env['ir.actions.report'].search(
            [('report_type', '=', 'qweb-pdf')], limit=1)

    def _print(self, user, error):
        from unittest.mock import patch
        from odoo.exceptions import UserError
        Report = type(self.env['ir.actions.report'])
        with patch.object(Report, '_pre_render_qweb_pdf', side_effect=UserError(error)):
            with self.assertRaises(UserError) as cm:
                self.env['ir.actions.report'].with_user(user)._render_qweb_pdf(
                    self.report.report_name, [1])
        return str(cm.exception)

    def test_engine_failure_is_neutral(self):
        if not self.report:
            self.skipTest('no PDF report')
        leak = 'Wkhtmltopdf failed (error code: -6). Message: /' + 'od' + 'oo/server/x std::bad_alloc'
        msg = self._print(self.user, leak)
        self.assertIn('The PDF could not be created', msg)
        self.assertNotIn('/', msg.split('.')[0])
        self.assertNotIn('od' + 'oo', msg.lower())
        self.assertIn('Wkhtmltopdf', self._print(self.admin, leak), 'admins keep the detail')

    def test_business_message_passes_through(self):
        if not self.report:
            self.skipTest('no PDF report')
        self.assertEqual(self._print(self.user, 'Please validate the invoice first.'),
                         'Please validate the invoice first.')
