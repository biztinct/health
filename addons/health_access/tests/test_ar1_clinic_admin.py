# -*- coding: utf-8 -*-
"""ACCESS REVAMP AR-1, the clinic's half.

Test 1 of the handover: somebody holding ONLY the Admin role — the clinic
administrator tier and a login, nothing else — is a whole access manager now.
They see every hand-over, take anybody's back, change a role, and the history
spreadsheet carries every row rather than their own.

And the three things this clinic decides on top of the generic rules: Owner is
guarded, "not to yourself" names who to ask, and the job on a staff record —
which gives its role as a side effect — asks those rules FIRST.
"""

import base64
import io
from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from odoo.addons.biz_access.models.access_common import (
    forbidden_in_closure, hidden_logins)


@tagged('post_install', '-at_install')
class TestAr1ClinicAdministrator(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        internal = cls.env.ref('base.group_user')
        cls.clinic_admin = cls.env.ref('health_access.group_clinic_admin')
        cls.team = cls.env.ref('biz_access.group_access_manager')
        cls.admin = Users.create({
            'name': 'AR1 Clinic Admin', 'login': 'ar1.clinic@example.test',
            'group_ids': [(6, 0, [internal.id, cls.clinic_admin.id])]})
        cls.lender = Users.create({
            'name': 'AR1 Lender', 'login': 'ar1.lender@example.test',
            'group_ids': [(6, 0, [internal.id])]})
        cls.borrower = Users.create({
            'name': 'AR1 Borrower', 'login': 'ar1.borrower@example.test',
            'group_ids': [(6, 0, [internal.id])]})
        cls.group = cls.env['res.groups'].create({'name': 'AR1 HA gate'})
        ability = cls.env['biz.access.ability'].create({
            'technical_key': 'ar1-ha-gate', 'name': 'AR1 HA gate',
            'area': 'admin', 'group_ids': [(6, 0, cls.group.ids)]})
        cls.role = cls.env['biz.access.role'].create({
            'name': 'AR1 HA role', 'area': 'admin',
            'description': 'A throwaway role for a test.',
            'ability_ids': [(6, 0, ability.ids)]})
        facade = cls.env['biz.access']
        facade.grant(cls.role.id, cls.lender.id)
        cls.one = facade.with_user(cls.lender).delegate({
            'delegate_user_id': cls.borrower.id, 'profile_ids': [cls.role.id],
            'kind': 'temporary',
            'date_end': fields.Date.today() + timedelta(days=9)})['id']

    def as_admin(self):
        return self.env['biz.access'].with_user(self.admin)

    def test_the_tier_now_carries_the_access_team(self):
        self.assertIn(self.team, self.clinic_admin.implied_ids)
        self.assertTrue(self.admin.has_group('biz_access.group_access_manager'))

    def test_2_the_access_team_is_still_outside_the_forbidden_closure(self):
        self.assertFalse(forbidden_in_closure(self.team, self.env))
        self.assertFalse(forbidden_in_closure(self.clinic_admin, self.env))

    def test_1_sees_every_hand_over(self):
        ids = {r['id'] for r in self.as_admin().handovers('all')['rows']}
        self.assertIn(self.one, ids)
        self.assertIn(self.one,
                      {r['id'] for r in self.as_admin().get_board()[
                          'delegations']})

    def test_1_can_take_back_somebody_elses(self):
        res = self.as_admin().revoke(self.one)
        self.assertTrue(res['ok'])
        self.assertEqual(
            self.env['biz.access.delegation'].browse(self.one).state,
            'revoked')

    def test_1_can_change_a_role(self):
        self.role.with_user(self.admin).write(
            {'description': 'Changed by the clinic administrator.'})
        self.assertEqual(self.role.description,
                         'Changed by the clinic administrator.')

    def test_1_the_history_spreadsheet_has_every_row(self):
        import openpyxl
        res = self.as_admin().export_delegations()
        total = self.env['biz.access.delegation'].search_count([])
        hidden = hidden_logins(self.env)
        gone = self.env['res.users'].with_context(active_test=False).search(
            [('login', 'in', list(hidden))]).ids if hidden else []
        if gone:
            total = self.env['biz.access.delegation'].search_count(
                [('delegator_user_id', 'not in', gone),
                 ('delegate_user_id', 'not in', gone)])
        self.assertEqual(res['rows'], total)
        wb = openpyxl.load_workbook(io.BytesIO(base64.b64decode(
            res['file_b64'])))
        names = {c.value for row in wb.active.iter_rows(min_row=2)
                 for c in row[2:4]}
        self.assertIn('AR1 Lender', names)

    def test_owner_is_guarded_and_the_admin_cannot_give_it(self):
        owner = self.env.ref('health_access.role_owner')
        self.assertTrue(owner.guarded)
        with self.assertRaises(UserError) as caught:
            self.as_admin().grant(owner.id, self.borrower.id)
        self.assertIn(owner.name, str(caught.exception))

    def test_not_to_yourself_names_who_to_ask(self):
        with self.assertRaises(UserError) as caught:
            self.as_admin().grant(self.role.id, self.admin.id)
        self.assertIn('Ask another Owner or Admin', str(caught.exception))

    def test_a_job_that_would_give_yourself_a_role_is_refused_first(self):
        # `sudo()` keeps the uid: the wizard still asks as the administrator.
        wizard = self.env['health.access.set.job'].with_user(
            self.admin).sudo().create(
            {'user_id': self.admin.id, 'job_role_id': self.role.id})
        with self.assertRaises(UserError):
            wizard.action_apply()
        self.assertFalse(self.admin.job_role_id)

    def test_the_platform_recovery_account_is_kept_off_the_lists(self):
        self.assertIn('platform.recovery@carejiox.com',
                      hidden_logins(self.env))

    def test_the_change_job_form_works_for_the_administrator(self):
        """It had no access line, so nobody but the system could save it."""
        wizard = self.env['health.access.set.job'].with_user(self.admin).create(
            {'user_id': self.borrower.id, 'job_role_id': self.role.id})
        wizard.action_apply()
        self.assertEqual(self.borrower.job_role_id, self.role)

    def test_a_plain_colleague_still_cannot_apply_it(self):
        wizard = self.env['health.access.set.job'].with_user(
            self.lender).create({'user_id': self.borrower.id,
                                 'job_role_id': self.role.id})
        with self.assertRaises(UserError):
            wizard.action_apply()
