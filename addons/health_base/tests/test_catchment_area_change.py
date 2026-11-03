# -*- coding: utf-8 -*-
"""A user's new catchment area applies at once, not after a restart.

ir.rule caches each user's evaluated domain and core only drops it for group
or company changes. The catchment rules read user.catchment_province_id, so
before res.users.write cleared the cache a staff user moved to a new area kept
the old area's visibility (UAT 2026-11-04: the CRM account could not open the
contact it had just created in its new area).
"""
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestCatchmentAreaChange(TransactionCase):

    def test_new_area_applies_without_restart(self):
        Area = self.env['health.catchment.province']
        area_a = Area.create({'name': 'UAT change A'})
        area_b = Area.create({'name': 'UAT change B'})
        partner_b = self.env['res.partner'].create({'name': 'UAT area B partner',
                                                    'catchment_province_id': area_b.id})
        user = new_test_user(self.env, login='uat_area_change',
                             groups='base.group_user,health_base.group_healthcare_base,'
                                    'health_base.group_healthcare_receptionist')
        user.catchment_province_id = area_a
        Partner = self.env['res.partner'].with_user(user)
        self.assertFalse(Partner.search([('id', '=', partner_b.id)]),
                         'an area A user must not see an area B record')
        user.catchment_province_id = area_b
        self.assertEqual(Partner.search([('id', '=', partner_b.id)]), partner_b,
                         'after moving to area B the user sees it without a restart')
