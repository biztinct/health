# -*- coding: utf-8 -*-
"""Empty-list help never names the framework (UAT round 10, item 4)."""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestEmptyHelp(TransactionCase):

    def test_stock_help_is_debranded(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'biz_debranding.brand_name', 'Viet Uc Care')
        out = self.env['res.partner'].get_empty_list_help(
            '<p class="o_view_nocontent_smiling_face">Create a Contact</p>'
            '<p>Odoo helps you track all activities related to your contacts.</p>')
        self.assertNotIn('Odoo', str(out))
        self.assertIn('Viet Uc Care helps you track', str(out))

    def test_help_without_the_name_is_untouched(self):
        src = '<p>No records yet</p>'
        self.assertIn('No records yet',
                      str(self.env['res.partner'].get_empty_list_help(src)))
