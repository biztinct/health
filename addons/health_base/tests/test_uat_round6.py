# -*- coding: utf-8 -*-
"""UAT round 6 (docs/handovers/uat-video-fixes-2026-11-04.md §8), health_base side.

  2  a client distance written by a person/import is marked "set on purpose"
  3  a clinic with only a placeholder street geocodes to the city (a place),
     never to a road named after it ("Ho Chi Minh Highway")
  7  Audit Log › Record shows the record's name and opens it
  8  the Owner manages COMPANY-WIDE public holidays (create, edit, archive),
     not staff time off; other staff cannot
"""
from datetime import datetime
from unittest.mock import patch

from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestUatRound6Base(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # The live Owner role also carries Employees / Officer (creating a
        # public holiday books the holiday on every employee's timesheet).
        cls.owner = new_test_user(cls.env, login='r6_owner', groups=(
            'base.group_user,hr.group_hr_user,health_base.group_healthcare_owner'))
        cls.nurse = new_test_user(cls.env, login='r6b_nurse', groups=(
            'base.group_user,health_base.group_healthcare_nurse'))
        cls.facility = cls.env['health.facility'].search(
            [('catchment_province_id', '!=', False)], limit=1)

    # ------------------------------------------------------------ item 2
    def test_2_client_distance_marker(self):
        partner = self.env['res.partner'].with_context(
            skip_auto_geocode=True, skip_distance_recompute=True).create({
            'name': 'R6 Distance Client', 'clinic_drive_distance_km': 0.0})
        self.assertEqual(partner.clinic_distance_method, 'manual')
        self.assertEqual(partner.clinic_distance_display, '0.0 km')
        never = self.env['res.partner'].create({'name': 'R6 Never Set'})
        self.assertFalse(never.clinic_distance_method)
        self.assertEqual(never.clinic_distance_display, '')

    # ------------------------------------------------------------ item 3
    def test_3_placeholder_street_geocodes_the_place(self):
        fac = self.facility
        calls = []

        class _Resp:
            def raise_for_status(self):
                pass

            def json(self):
                return {'features': [{'geometry': {'coordinates': [106.7166008, 10.7737261]}}]}

        def fake_get(url, params=None, headers=None, timeout=None):
            calls.append(params)
            return _Resp()

        with patch('odoo.addons.health_base.models.health_facility.requests.get', fake_get):
            fac.with_context(skip_auto_geocode=True).write({'street': '-', 'street2': False,
                                                             'city': 'Hồ Chí Minh'})
            calls.clear()
            self.assertTrue(fac._geocode_facility_address())
        self.assertEqual(calls[-1].get('osm_tag'), 'place')
        self.assertFalse(calls[-1]['q'].startswith('-'))
        self.assertAlmostEqual(fac.latitude, 10.7737261, places=5)

    # ------------------------------------------------------------ item 7
    def test_7_audit_log_record_name_and_open(self):
        partner = self.env['res.partner'].create({'name': 'R6 Audit Probe'})
        # A tracked change as the chatter stores it (tracking itself is only
        # written at commit time, which a test never reaches).
        field = self.env['ir.model.fields']._get('res.partner', 'mobile')
        self.env['mail.message'].create({
            'model': 'res.partner', 'res_id': partner.id,
            'message_type': 'notification', 'body': '',
            'tracking_value_ids': [Command.create({
                'field_id': field.id, 'old_value_char': '', 'new_value_char': '0900000999'})],
        })
        self.env.flush_all()
        rows = self.env['health.audit.log.view'].search(
            [('model', '=', 'res.partner'), ('res_id', '=', partner.id)])
        self.assertTrue(rows, 'the tracked change is in the audit log')
        self.assertEqual(rows[0].record_name, 'R6 Audit Probe')
        found = self.env['health.audit.log.view'].search(
            [('record_name', 'ilike', 'R6 Audit Probe')])
        self.assertIn(rows[0], found)
        action = rows[0].action_open_record()
        self.assertEqual((action['res_model'], action['res_id']), ('res.partner', partner.id))
        # A record the viewer cannot read is refused (and named generically).
        with patch.object(type(self.env['res.partner']), 'check_access',
                          side_effect=AccessError('no')):
            with self.assertRaises(UserError):
                rows[0].action_open_record()

    # ------------------------------------------------------------ item 8
    def _holiday_vals(self, **extra):
        vals = {'name': 'R6 Probe Holiday', 'date_from': datetime(2027, 3, 3, 0, 0),
                'date_to': datetime(2027, 3, 3, 23, 0), 'resource_id': False,
                'calendar_id': False}
        vals.update(extra)
        return vals

    def test_8a_owner_creates_edits_archives_company_wide_holidays(self):
        Leaves = self.env['resource.calendar.leaves'].with_user(self.owner)
        holiday = Leaves.create(self._holiday_vals())
        holiday.write({'name': 'R6 Probe Holiday (renamed)', 'price_multiplier': 2.0})
        holiday.action_archive()
        self.assertFalse(holiday.active)
        holiday.action_unarchive()
        self.assertTrue(holiday.active)

    def test_8b_owner_cannot_touch_staff_time_off(self):
        other = new_test_user(self.env, login='r6_staff_with_leave')
        emp = self.env['hr.employee'].create({'name': 'R6 Staff', 'user_id': other.id})
        leave = self.env['resource.calendar.leaves'].create(self._holiday_vals(
            name='R6 Staff: Time Off', resource_id=emp.resource_id.id,
            calendar_id=emp.resource_calendar_id.id))
        with self.assertRaises(AccessError):
            leave.with_user(self.owner).write({'name': 'changed'})
        with self.assertRaises(AccessError):
            self.env['resource.calendar.leaves'].with_user(self.owner).create(
                self._holiday_vals(resource_id=emp.resource_id.id))

    def test_8c_other_staff_cannot_create_public_holidays(self):
        with self.assertRaises(AccessError):
            self.env['resource.calendar.leaves'].with_user(self.nurse).create(self._holiday_vals())

    def test_8d_screen_lists_public_holidays_only(self):
        action = self.env.ref('health_landing.action_admin_holidays', raise_if_not_found=False)
        if not action:
            self.skipTest('health_landing not installed')
        self.assertIn("('resource_id', '=', False)", action.domain)
        self.assertIn("('calendar_id', '=', False)", action.domain)
