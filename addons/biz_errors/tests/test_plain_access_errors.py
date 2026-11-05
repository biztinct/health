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
