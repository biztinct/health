# -*- coding: utf-8 -*-
"""UAT round 10, items 1 and 2.

1. The first sign-in no longer replaces a chosen time zone with the browser's
   ("Asia/Saigon"); a user with none gets the browser's under its IANA name.
2. Switching a login off archives their staff record; switching it back on
   restores only the staff records archived because of it — whichever path
   switched it, and without HR rights.
"""
from unittest.mock import MagicMock, patch

from odoo.tests import TransactionCase, new_test_user, tagged

from odoo.addons.health_access.models.res_users import canonical_tz


def _fake_request(tz):
    req = MagicMock()
    req.cookies = {'tz': tz}
    req.httprequest.environ = {'REMOTE_ADDR': '127.0.0.1'}
    req.httprequest.remote_addr = '127.0.0.1'
    return req


@tagged('post_install', '-at_install')
class TestFirstSignInTimeZone(TransactionCase):

    def _sign_in(self, user, password):
        with patch('odoo.addons.base.models.res_users.request',
                   _fake_request('Asia/Saigon')):
            self.env['res.users']._login(
                {'type': 'password', 'login': user.login, 'password': password},
                {'interactive': False})
        user.invalidate_recordset(['tz'])

    def test_canonical_names(self):
        self.assertEqual(canonical_tz('Asia/Saigon'), 'Asia/Ho_Chi_Minh')
        self.assertEqual(canonical_tz('Asia/Calcutta'), 'Asia/Kolkata')
        self.assertEqual(canonical_tz('Asia/Ho_Chi_Minh'), 'Asia/Ho_Chi_Minh')
        self.assertEqual(canonical_tz('Not/AZone'), 'Not/AZone')
        self.assertFalse(canonical_tz(False))

    def test_a_chosen_zone_survives_the_first_sign_in(self):
        password = 'R10-tz-pass-1!'
        user = new_test_user(self.env, login='r10.tz.kept', password=password,
                             tz='Asia/Ho_Chi_Minh')
        employee = self.env['hr.employee'].create(
            {'name': 'R10 tz kept', 'user_id': user.id})
        self.assertFalse(user.login_date, 'never signed in')
        self._sign_in(user, password)
        self.assertEqual(user.tz, 'Asia/Ho_Chi_Minh')
        employee.invalidate_recordset(['tz'])
        self.assertEqual(employee.tz, 'Asia/Ho_Chi_Minh')

    def test_no_zone_gets_the_browser_zone_by_its_iana_name(self):
        password = 'R10-tz-pass-2!'
        user = new_test_user(self.env, login='r10.tz.none', password=password)
        user.partner_id.tz = False
        self._sign_in(user, password)
        self.assertEqual(user.tz, 'Asia/Ho_Chi_Minh')


@tagged('post_install', '-at_install')
class TestSwitchOffArchivesStaff(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # An access manager WITHOUT HR rights: the Access home's switch-off
        # must not need them.
        cls.keeper = cls.env['res.users'].create({
            'name': 'R10 keeper', 'login': 'r10.keeper@example.test',
            'group_ids': [(4, cls.env.ref('base.group_user').id),
                          (4, cls.env.ref('biz_access.group_access_manager').id)]})
        cls.nurse = cls.env['res.users'].create({
            'name': 'R10 nurse', 'login': 'r10.nurse@example.test',
            'group_ids': [(4, cls.env.ref('base.group_user').id)]})
        cls.staff = cls.env['hr.employee'].create(
            {'name': 'R10 nurse', 'user_id': cls.nurse.id})

    def test_switch_off_and_on_from_the_access_home(self):
        self.assertFalse(self.keeper.has_group('hr.group_hr_user'))
        self.env['biz.access'].with_user(self.keeper).run_person_action(
            'deactivate', self.nurse.id)
        self.assertFalse(self.nurse.active)
        self.assertFalse(self.staff.active, 'the staff record is archived')
        self.assertTrue(self.staff.archived_with_login)
        self.env['biz.access'].with_user(self.keeper).run_person_action(
            'activate', self.nurse.id)
        self.assertTrue(self.nurse.active)
        self.assertTrue(self.staff.active, 'the staff record is back')
        self.assertFalse(self.staff.archived_with_login)

    def test_archive_action_and_plain_write(self):
        result = self.nurse.action_archive()
        self.assertFalse(self.staff.active)
        self.assertFalse(isinstance(result, dict)
                         and result.get('res_model') == 'hr.departure.wizard',
                         'no departure wizard')
        self.nurse.action_unarchive()
        self.assertTrue(self.staff.active)
        self.nurse.write({'active': False})
        self.assertFalse(self.staff.active)

    def test_staff_archived_for_another_reason_stays_archived(self):
        # One staff record per login and company (hr rule), so: HR archived
        # the staff record first, then the login is switched off and on.
        self.staff.write({'active': False})
        self.nurse.write({'active': False})
        self.assertFalse(self.staff.archived_with_login, 'not archived by the switch-off')
        self.nurse.write({'active': True})
        self.assertFalse(self.staff.active, 'not archived because of the login, so not restored')

    def test_platform_accounts_are_never_touched(self):
        admin = self.env['res.users'].create({
            'name': 'R10 sysadmin', 'login': 'r10.sys@example.test',
            'group_ids': [(4, self.env.ref('base.group_system').id)]})
        admin_staff = self.env['hr.employee'].create(
            {'name': 'R10 sysadmin', 'user_id': admin.id})
        admin.write({'active': False})
        self.assertTrue(admin_staff.active)
