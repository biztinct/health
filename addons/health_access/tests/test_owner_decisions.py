# -*- coding: utf-8 -*-
"""The owner's decisions of 2026-11-03: Owners export lists, the Admin role is
called Office Admin, the demo login is off."""
from odoo.tests import TransactionCase, tagged

from ..hooks import (ADMIN_ROLE_NAME, EXPORT_ABILITY, FRESH_ROLE_ABILITIES,
                     OLD_ADMIN_ROLE_NAME, grant_export, rename_admin_role,
                     retire_demo_login, role_by_name)


@tagged('post_install', '-at_install')
class TestOwnerDecisions(TransactionCase):

    def test_owners_may_export_lists(self):
        self.assertIn(EXPORT_ABILITY, FRESH_ROLE_ABILITIES['Owner'])
        ability = self.env['biz.access.ability'].sudo().with_context(
            active_test=False).search([('technical_key', '=', EXPORT_ABILITY)])
        self.assertEqual(len(ability), 1, 'the export ability is written down once')
        self.assertEqual(ability.group_ids, self.env.ref('base.group_allow_export'))
        grant_export(self.env)                       # idempotent
        owner = role_by_name(self.env, 'Owner')
        self.assertIn(ability, owner.ability_ids)
        self.assertIn(self.env.ref('base.group_allow_export'), owner.group_ids)
        self.assertEqual(grant_export(self.env), 0, 'a second run adds nothing')
        # No other seeded role carries it.
        for name in ('Operations Manager', 'Nurse', 'Doctor', 'Accountant',
                     'CRM', ADMIN_ROLE_NAME):
            role = role_by_name(self.env, name)
            if role:
                self.assertNotIn(ability, role.ability_ids, name)

    def test_the_admin_role_is_called_office_admin(self):
        self.assertFalse(role_by_name(self.env, OLD_ADMIN_ROLE_NAME),
                         'no role is still called by the old name')
        role = role_by_name(self.env, ADMIN_ROLE_NAME)
        self.assertTrue(role)
        self.assertEqual(role, self.env.ref('health_access.role_admin'),
                         'the fixed name underneath did not change')
        self.assertEqual(rename_admin_role(self.env), 0, 'nothing left to rename')
        if self.env['res.lang'].sudo().search_count(
                [('code', '=', 'vi_VN'), ('active', '=', True)]):
            vi = role.with_context(lang='vi_VN').name or ''
            self.assertNotEqual(vi.strip(), 'Quản trị viên',
                                'the Vietnamese name moved with the English one')

    def test_the_demo_login_is_off(self):
        user = self.env['res.users'].sudo().with_context(
            active_test=False).search([('login', '=', 'demo')], limit=1)
        if user:
            self.assertFalse(user.active, 'the demo login is switched off')
        self.assertEqual(retire_demo_login(self.env), 0,
                         'nothing left to switch off')
