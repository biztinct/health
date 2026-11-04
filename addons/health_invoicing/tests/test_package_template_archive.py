# -*- coding: utf-8 -*-
"""An Owner can archive a package template without Inventory rights.

stock's product.product.write reads the variant's restocking rules when
`active` changes; an Owner has no Inventory rights, so archiving a package
template from Master Data › Package Templates failed (UAT 2026-11-04).
"""
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestPackageTemplateArchive(TransactionCase):

    def test_owner_archives_a_package_template(self):
        owner = new_test_user(self.env, login='uat_pkg_owner',
                              groups='base.group_user,health_base.group_healthcare_owner')
        tmpl = self.env['product.template'].create({
            'name': 'UAT archive package', 'type': 'healthcare_package',
            'healthcare_service_count': 3, 'list_price': 1500000,
        })
        Orderpoint = self.env['stock.warehouse.orderpoint'] if 'stock.warehouse.orderpoint' in self.env else None
        if Orderpoint is not None:
            self.assertFalse(Orderpoint.with_user(owner).has_access('read'),
                             'the case needs a user without stock rights')
        tmpl.with_user(owner).action_archive()
        self.assertFalse(tmpl.active)
        tmpl.with_user(owner).action_unarchive()
        self.assertTrue(tmpl.active)
