# -*- coding: utf-8 -*-
"""Tests for health_schedule_canvas (handover §4).

Server-testable surfaces:
  * can_schedule_create — ops True / nurse False (§4.1)
  * schedule_canvas_prefill — UTC→facility-local conversion + off-hours warning
    (§4.2, the +7h-bug seam)
  * get_schedule_overlay granularity — month drops 'off', keeps everything else
    (§4.3)
  * template retirement — no template on manual-assign, default_get honours
    context, ignores leftover rows, post_init cleanup unlinks them (§4.6)

The dynamic_range clause and the hiddenDates builder are pure JS (browser-QA'd),
noted in QA_LIVE.md.

Staff availability uses the legacy working_hours_<day> char fields; per
conventions §5.26 resource_calendar_id must be cleared first or it wins. The
base window sits at 02:00 UTC = 09:00 Asia/Ho_Chi_Minh (+7).
"""
import uuid
from datetime import datetime

from odoo.tests.common import TransactionCase, tagged

BASE = datetime(2026, 8, 3, 2, 0, 0)   # Mon 03 Aug 2026, 02:00 UTC = 09:00 ICT
_DAYS = ('monday', 'tuesday', 'wednesday', 'thursday', 'friday',
         'saturday', 'sunday')


@tagged('post_install', '-at_install')
class CanvasBase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Province = cls.env['health.catchment.province']
        Facility = cls.env['health.facility']
        cls.province = Province.search([], limit=1) or Province.create(
            {'name': 'Canvas Province', 'code': 'CVP'})
        cls.facility = Facility.search(
            [('catchment_province_id', '=', cls.province.id)], limit=1)
        if not cls.facility:
            cls.facility = Facility.create({
                'name': 'Canvas Facility', 'code': 'CVF',
                'street': '1 Canvas Street', 'city': 'Test City',
                'phone': '02838000000', 'timezone': 'Asia/Ho_Chi_Minh',
                'catchment_province_id': cls.province.id})
        cls.patient = cls.env['res.partner'].create({
            'name': 'Canvas Patient', 'is_patient': True,
            'catchment_province_id': cls.province.id,
            'primary_facility_id': cls.facility.id, 'mobile': '0912345678'})
        cls.ops = cls._user('health_base.group_healthcare_operations_manager')
        cls.nurse = cls._user('health_base.group_healthcare_nurse')

    @classmethod
    def _user(cls, group_xmlid):
        return cls.env['res.users'].create({
            'name': 'Canvas %s' % group_xmlid.split('_')[-1],
            'login': 'cvs_%s' % uuid.uuid4().hex[:10],
            'email': 'cvs_%s@example.com' % uuid.uuid4().hex[:6],
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id,
                                  cls.env.ref(group_xmlid).id])],
            'catchment_province_id': cls.province.id})

    def _staff(self, hours='00:00-23:59'):
        user = self.env['res.users'].create({
            'name': 'Canvas Staff', 'login': 'cst_%s' % uuid.uuid4().hex[:10],
            'email': 'cst_%s@example.com' % uuid.uuid4().hex[:6]})
        emp = self.env['hr.employee'].create({
            'name': 'Canvas Staff', 'user_id': user.id,
            'is_healthcare_staff': True, 'employment_status': 'active',
            'healthcare_facility_id': self.facility.id})
        # §5.26 — clear the auto-set company calendar so the char hours apply.
        emp.write({'resource_calendar_id': False})
        emp.write({'working_hours_%s' % d: hours for d in _DAYS})
        return emp

    def _fso(self, when=None):
        fso = self.env['health.fieldservice.order'].create({
            'patient_id': self.patient.id, 'facility_id': self.facility.id,
            'scheduled_datetime': when or BASE, 'scheduled_duration': 60,
            'service_type': 'home_visit'})
        fso.state = 'assigned'
        return fso


# =====================================================================
# §4.1 — can_schedule_create
# =====================================================================
@tagged('post_install', '-at_install')
class TestCanCreate(CanvasBase):

    def test_ops_can_create(self):
        Asg = self.env['health.staff.assignment']
        self.assertTrue(Asg.with_user(self.ops).can_schedule_create())

    def test_nurse_cannot_create(self):
        Asg = self.env['health.staff.assignment']
        self.assertFalse(Asg.with_user(self.nurse).can_schedule_create())


# =====================================================================
# §4.2 — schedule_canvas_prefill (facility-local conversion)
# =====================================================================
@tagged('post_install', '-at_install')
class TestPrefill(CanvasBase):

    def test_utc_click_becomes_facility_local(self):
        staff = self._staff()
        Asg = self.env['health.staff.assignment']
        res = Asg.with_user(self.ops).schedule_canvas_prefill(
            staff.id, '2026-08-03 02:00:00')   # 02:00 UTC on a +7 facility
        self.assertTrue(res['ok'])
        self.assertEqual(res['date'], '2026-08-03')
        self.assertEqual(res['time_hour'], 9.0)       # 09:00 ICT
        self.assertEqual(res['staff_id'], staff.id)
        self.assertEqual(res['facility_id'], self.facility.id)
        self.assertTrue(res['can_create'])            # ops user

    def test_prefill_reports_nurse_cannot_create(self):
        staff = self._staff()
        res = self.env['health.staff.assignment'].with_user(
            self.nurse).schedule_canvas_prefill(staff.id, '2026-08-03 02:00:00')
        self.assertTrue(res['ok'])
        self.assertFalse(res['can_create'])

    def test_offhours_click_warns_but_ok(self):
        # 09:00 ICT click on a 10:00-17:00 staff → outside hours → warning set,
        # but ok stays True (creating off-hours is allowed, just flagged).
        staff = self._staff(hours='10:00-17:00')
        res = self.env['health.staff.assignment'].with_user(
            self.ops).schedule_canvas_prefill(staff.id, '2026-08-03 02:00:00')
        self.assertTrue(res['ok'])
        self.assertTrue(res['warning'])

    def test_inhours_click_no_warning(self):
        staff = self._staff(hours='00:00-23:59')
        res = self.env['health.staff.assignment'].with_user(
            self.ops).schedule_canvas_prefill(staff.id, '2026-08-03 02:00:00')
        self.assertFalse(res['warning'])

    def test_unknown_staff_refused(self):
        res = self.env['health.staff.assignment'].with_user(
            self.ops).schedule_canvas_prefill(0, '2026-08-03 02:00:00')
        self.assertFalse(res['ok'])


# =====================================================================
# §4.3 — get_schedule_overlay granularity
# =====================================================================
@tagged('post_install', '-at_install')
class TestOverlayGranularity(CanvasBase):

    def test_month_drops_off_backgrounds(self):
        staff = self._staff(hours='08:00-17:00')  # → 'off' segments exist
        Asg = self.env['health.staff.assignment']
        ds, de = '2026-08-03 00:00:00', '2026-08-04 00:00:00'
        day = Asg.get_schedule_overlay(ds, de, [staff.id], self.facility.id)
        off_day = [b for b in day['backgrounds'] if b['kind'] == 'off']
        self.assertTrue(off_day, "day scale must include 'off' backgrounds")
        month = Asg.get_schedule_overlay(
            ds, de, [staff.id], self.facility.id, 'month')
        off_month = [b for b in month['backgrounds'] if b['kind'] == 'off']
        self.assertFalse(off_month, "month granularity must drop 'off' backgrounds")

    def test_day_granularity_unchanged(self):
        staff = self._staff(hours='08:00-17:00')
        Asg = self.env['health.staff.assignment']
        ds, de = '2026-08-03 00:00:00', '2026-08-04 00:00:00'
        base = Asg.get_schedule_overlay(ds, de, [staff.id], self.facility.id)
        explicit = Asg.get_schedule_overlay(
            ds, de, [staff.id], self.facility.id, 'day')
        self.assertEqual(len(base['backgrounds']), len(explicit['backgrounds']))


# =====================================================================
# §4.6 — template retirement
# =====================================================================
@tagged('post_install', '-at_install')
class TestTemplateRetirement(CanvasBase):

    def _seed_template(self, fso):
        return self.env['health.staff.assignment'].create({
            'fso_id': fso.id, 'staff_id': False, 'state': 'template'})

    def test_manual_assign_creates_no_template(self):
        fso = self._fso()
        before = self.env['health.staff.assignment'].search_count(
            [('state', '=', 'template')])
        fso.action_manual_assign_staff()
        after = self.env['health.staff.assignment'].search_count(
            [('state', '=', 'template')])
        self.assertEqual(after, before,
                         "action_manual_assign_staff must not create a template row")

    def test_default_get_honours_context_fso(self):
        fso = self._fso()
        defaults = self.env['health.staff.assignment'].with_context(
            default_fso_id=fso.id).default_get(['fso_id'])
        self.assertEqual(defaults.get('fso_id'), fso.id)

    def test_default_get_ignores_leftover_template(self):
        fso = self._fso()
        self._seed_template(fso)
        defaults = self.env['health.staff.assignment'].default_get(['fso_id'])
        self.assertFalse(
            defaults.get('fso_id'),
            "a leftover template must no longer leak into new-assignment defaults")

    def test_post_init_cleanup_unlinks_templates(self):
        from odoo.addons.health_schedule_canvas.hooks import (
            post_init_cleanup_templates,
        )
        fso = self._fso()
        self._seed_template(fso)
        self.assertTrue(self.env['health.staff.assignment'].search_count(
            [('state', '=', 'template')]))
        post_init_cleanup_templates(self.env)
        self.assertFalse(self.env['health.staff.assignment'].search_count(
            [('state', '=', 'template')]))
