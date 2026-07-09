# -*- coding: utf-8 -*-
"""Tests for health_routes (handover §4).

External requests raise in test mode, and use_external_router is forced OFF, so
every distance lands on the deterministic 1.3×-haversine @ 30 km/h approx tier
— the expected minutes are pinned in the asserts.

Fixture geometry: patient_near at BASE, patient_far +0.2° lat (~22.24 km).
  approx road km = round(22.239 * 1.3, 2) = 28.91
  approx minutes = round(28.91 / 30 * 60, 1) = 57.8
  buffer (config) = 10  →  ok ≥ 67.8 min gap, warn 57.8–67.8, critical < 57.8
"""
import time as _time
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from odoo import fields
from odoo.tests import TransactionCase, tagged

BASE_LAT = 10.7769000
BASE_LNG = 106.7009000
FAR_LAT = 10.9769000            # +0.2° lat ≈ 22.24 km due north
APPROX_MIN = 57.8              # pinned approx travel near↔far


def _fixture(env):
    Partner = env['res.partner']
    Facility = env['health.facility']
    province = env['health.catchment.province'].search([], limit=1) \
        or env['health.catchment.province'].create({'name': 'RT Prov', 'code': 'RTP'})
    facility = Facility.search(
        [('catchment_province_id', '=', province.id)], limit=1)
    if not facility:
        facility = Facility.create({
            'name': 'RT Facility', 'code': 'RTF', 'street': '1 RT St',
            'city': 'Test City', 'phone': '02838000000',
            'timezone': 'Asia/Ho_Chi_Minh',
            'catchment_province_id': province.id})
    near = Partner.create({
        'name': 'RT Near', 'is_patient': True,
        'catchment_province_id': province.id, 'primary_facility_id': facility.id,
        'mobile': '0912000001',
        'partner_latitude': BASE_LAT, 'partner_longitude': BASE_LNG})
    far = Partner.create({
        'name': 'RT Far', 'is_patient': True,
        'catchment_province_id': province.id, 'primary_facility_id': facility.id,
        'mobile': '0912000002',
        'partner_latitude': FAR_LAT, 'partner_longitude': BASE_LNG})
    nocoord = Partner.create({
        'name': 'RT NoCoord', 'is_patient': True,
        'catchment_province_id': province.id, 'primary_facility_id': facility.id,
        'mobile': '0912000003'})
    staff_user = env['res.users'].create({
        'name': 'RT Staff', 'login': 'rt_staff_%s' % province.id,
        'email': 'rt_staff@example.com'})
    staff = env['hr.employee'].create({
        'name': 'RT Nurse', 'user_id': staff_user.id,
        'healthcare_facility_id': facility.id,
        'staff_catchment_province_id': province.id})
    product = env['product.product'].search([('sale_ok', '=', True)], limit=1) \
        or env['product.product'].create(
            {'name': 'RT Service', 'type': 'service', 'list_price': 100.0})
    return province, facility, near, far, nocoord, staff_user, staff, product


@tagged('post_install', '-at_install')
class RoutesBase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        (cls.province, cls.facility, cls.near, cls.far, cls.nocoord,
         cls.staff_user, cls.staff, cls.product) = _fixture(cls.env)
        ICP = cls.env['ir.config_parameter'].sudo()
        ICP.set_param('health_routes.use_external_router', 'False')
        ICP.set_param('health_routes.enabled', 'True')
        ICP.set_param('health_routes.buffer_minutes', '10')
        ICP.set_param('health_routes.leg_ttl_days', '30')
        if not cls.env.user.employee_id:
            cls.env['hr.employee'].create(
                {'name': 'RT Admin Emp', 'user_id': cls.env.user.id})
            cls.env.user.invalidate_recordset()

    def _fso(self, patient, start_utc, dur=60, state='confirmed',
             staff=True, location='home'):
        fso = self.env['health.fieldservice.order'].create({
            'patient_id': patient.id, 'facility_id': self.facility.id,
            'scheduled_datetime': start_utc, 'scheduled_duration': dur,
            'service_type': 'telemedicine' if location == 'online' else 'home_visit',
            'service_location': location})
        if staff:
            fso.action_assign_staff_to_fso(self.staff.id, assignment_role='lead')
        if state:
            fso.write({'state': state})
        return fso


class TestTransitionMath(RoutesBase):

    def _pair(self, next_start_local_min_after_9):
        """prev 08:00-09:00 (near), next (far) at 09:00 + N minutes."""
        base = datetime(2026, 8, 15, 8, 0, 0)
        prev = self._fso(self.near, base, dur=60, staff=False)
        nxt = self._fso(self.far,
                        base + timedelta(hours=1, minutes=next_start_local_min_after_9),
                        dur=60, staff=False)
        return self.env['health.route.transition']._check_transition(prev, nxt)

    def test_ok(self):
        r = self._pair(70)   # gap 70 ≥ 67.8
        self.assertEqual(r['status'], 'ok')
        self.assertAlmostEqual(r['travel_min'], APPROX_MIN, places=1)

    def test_warn(self):
        r = self._pair(60)   # 57.8 ≤ 60 < 67.8
        self.assertEqual(r['status'], 'warn')

    def test_critical(self):
        r = self._pair(10)   # 10 < 57.8
        self.assertEqual(r['status'], 'critical')

    def test_unknown_missing_coords(self):
        base = datetime(2026, 8, 15, 8, 0, 0)
        prev = self._fso(self.near, base, dur=60, staff=False)
        nxt = self._fso(self.nocoord, base + timedelta(hours=2),
                        dur=60, staff=False)
        r = self.env['health.route.transition']._check_transition(prev, nxt)
        self.assertEqual(r['status'], 'unknown')
        self.assertIsNone(r['travel_min'])

    def test_online_excluded_from_day_query(self):
        """A home→online→home day: the non-online query returns only the two
        home visits, so the pair checked is home→home directly."""
        day = datetime(2026, 8, 16, 1, 0, 0)          # ~08:00 local
        a = self._fso(self.near, day, dur=60)
        self._fso(self.near, day + timedelta(hours=2), dur=60, location='online')
        c = self._fso(self.far, day + timedelta(hours=4), dur=60)
        Trans = self.env['health.route.transition']
        fsos = Trans._nonline_fsos_between(
            self.staff, day - timedelta(days=1), day + timedelta(days=1))
        self.assertIn(a, fsos)
        self.assertIn(c, fsos)
        self.assertEqual(len(fsos.filtered(lambda f: f.service_location == 'online')), 0)


class TestLegCache(RoutesBase):

    def setUp(self):
        super().setUp()
        self.env['ir.config_parameter'].sudo().set_param(
            'health_routes.use_external_router', 'True')

    def test_cache_hit_and_symmetry_and_rounding(self):
        Leg = self.env['health.route.leg']
        counter = {'n': 0}

        def fake_driving(env, o_lat, o_lng, d_lat, d_lng):
            counter['n'] += 1
            return {'km': 5.0, 'minutes': 12.3, 'method': 'osrm'}

        with patch('odoo.addons.health_routes.models.route_leg.driving_distance',
                   side_effect=fake_driving):
            r1 = Leg.leg_minutes(BASE_LAT, BASE_LNG, FAR_LAT, BASE_LNG)
            self.assertEqual(r1['minutes'], 12.3)
            self.assertEqual(counter['n'], 1)
            # identical → cache hit, no second call
            Leg.leg_minutes(BASE_LAT, BASE_LNG, FAR_LAT, BASE_LNG)
            self.assertEqual(counter['n'], 1)
            # reversed endpoints → symmetric, same row, no call
            Leg.leg_minutes(FAR_LAT, BASE_LNG, BASE_LAT, BASE_LNG)
            self.assertEqual(counter['n'], 1)
            # sub-4dp jitter → same rounded key, no call
            Leg.leg_minutes(BASE_LAT + 0.000001, BASE_LNG, FAR_LAT, BASE_LNG)
            self.assertEqual(counter['n'], 1)
        rows = Leg.sudo().search([
            ('o_lat', '=', round(BASE_LAT, 4)), ('o_lng', '=', round(BASE_LNG, 4)),
            ('d_lat', '=', round(FAR_LAT, 4)), ('d_lng', '=', round(BASE_LNG, 4))])
        self.assertEqual(len(rows), 1)

    def test_ttl_expiry_recomputes(self):
        Leg = self.env['health.route.leg']
        counter = {'n': 0}

        def fake_driving(env, *a):
            counter['n'] += 1
            return {'km': 5.0, 'minutes': 9.0, 'method': 'osrm'}

        with patch('odoo.addons.health_routes.models.route_leg.driving_distance',
                   side_effect=fake_driving):
            Leg.leg_minutes(BASE_LAT, BASE_LNG, FAR_LAT, BASE_LNG)
            self.assertEqual(counter['n'], 1)
            row = Leg.sudo().search([('o_lat', '=', round(BASE_LAT, 4))], limit=1)
            row.sudo().write(
                {'computed_at': fields.Datetime.now() - timedelta(days=40)})
            Leg.leg_minutes(BASE_LAT, BASE_LNG, FAR_LAT, BASE_LNG)  # stale → recompute
            self.assertEqual(counter['n'], 2)

    def test_external_off_no_request(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'health_routes.use_external_router', 'False')

        def bomb(*a, **k):
            raise AssertionError('external router must not be called')

        with patch('odoo.addons.health_routes.models.route_leg.driving_distance',
                   side_effect=bomb):
            r = self.env['health.route.leg'].leg_minutes(
                BASE_LAT, BASE_LNG, FAR_LAT, BASE_LNG)
        self.assertEqual(r['method'], 'approx')
        self.assertAlmostEqual(r['minutes'], APPROX_MIN, places=1)


class TestSweep(RoutesBase):

    def _teleport_day(self, day, gap_after_first_min):
        first = self._fso(self.near, day, dur=60)
        second = self._fso(self.far, day + timedelta(hours=1, minutes=gap_after_first_min),
                           dur=60)
        return first, second

    def test_sweep_creates_critical_and_one_activity(self):
        Trans = self.env['health.route.transition']
        day = datetime(2026, 8, 20, 1, 0, 0)
        first, second = self._teleport_day(day, 10)   # gap 10 < 57.8 → critical
        Trans._sweep_day(day.date(), fields.Datetime.now())
        rows = Trans.search([('staff_id', '=', self.staff.id),
                             ('date', '=', day.date())])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows.status, 'critical')
        acts = self.env['mail.activity'].search([
            ('res_model', '=', 'health.fieldservice.order'),
            ('res_id', '=', second.id)])
        self.assertEqual(len(acts), 1)
        # Re-run → still one row, no duplicate activity (dedup).
        Trans._sweep_day(day.date(), fields.Datetime.now())
        rows2 = Trans.search([('staff_id', '=', self.staff.id),
                              ('date', '=', day.date())])
        self.assertEqual(len(rows2), 1)
        acts2 = self.env['mail.activity'].search([
            ('res_model', '=', 'health.fieldservice.order'),
            ('res_id', '=', second.id)])
        self.assertEqual(len(acts2), 1)

    def test_sweep_clears_when_fixed(self):
        Trans = self.env['health.route.transition']
        day = datetime(2026, 8, 21, 1, 0, 0)
        first, second = self._teleport_day(day, 10)
        Trans._sweep_day(day.date(), fields.Datetime.now())
        self.assertTrue(Trans.search([('staff_id', '=', self.staff.id),
                                      ('date', '=', day.date())]))
        # Widen the gap → feasible → next sweep clears the day's rows.
        second.write({'scheduled_datetime': day + timedelta(hours=3)})
        Trans._sweep_day(day.date(), fields.Datetime.now())
        self.assertFalse(Trans.search([('staff_id', '=', self.staff.id),
                                       ('date', '=', day.date())]))

    def test_matrix_travel_filled(self):
        """Bonus: sweep fills the inert matrix travel floats when rows exist."""
        Trans = self.env['health.route.transition']
        day = datetime(2026, 8, 22, 1, 0, 0)
        first, second = self._teleport_day(day, 10)
        Matrix = self.env['health.staff.availability.matrix']
        m_prev = Matrix.create({
            'staff_id': self.staff.id, 'availability_date': day.date(),
            'start_time': 8.0, 'end_time': 9.0, 'fso_id': first.id})
        m_next = Matrix.create({
            'staff_id': self.staff.id, 'availability_date': day.date(),
            'start_time': 9.0, 'end_time': 10.0, 'fso_id': second.id})
        Trans._sweep_day(day.date(), fields.Datetime.now())
        self.assertAlmostEqual(m_prev.travel_time_to_next, APPROX_MIN / 60.0, places=2)
        self.assertAlmostEqual(m_next.travel_time_from_previous, APPROX_MIN / 60.0, places=2)


class TestDropWarning(RoutesBase):

    def _setup_drop(self):
        # prev visit near, 08:00-09:00 UTC on the day.
        base = datetime(2026, 8, 25, 8, 0, 0)
        self._fso(self.near, base, dur=60)
        # the dropped FSO (far patient) — needs an assignment for validate_drop.
        dropped = self._fso(self.far, base + timedelta(hours=5), dur=60)
        assignment = dropped.assignment_ids[:1]
        # proposed window right after prev: 09:05-10:05 → gap 5 → critical.
        start = base + timedelta(hours=1, minutes=5)
        end = start + timedelta(hours=1)
        return dropped, assignment, start.isoformat(), end.isoformat()

    def test_message_appended_when_base_ok(self):
        from odoo.addons.health_fieldservice.models.health_staff_assignment \
            import HealthStaffAssignment as Base
        dropped, assignment, s_iso, e_iso = self._setup_drop()
        Assign = self.env['health.staff.assignment']
        ok_base = {'ok': True, 'hard_block': False, 'reason': 'ok', 'message': ''}
        with patch.object(Base, 'validate_drop', return_value=dict(ok_base)):
            res = Assign.validate_drop(self.staff.id, s_iso, e_iso,
                                       assignment_id=assignment.id)
        self.assertTrue(res['ok'])
        self.assertFalse(res['hard_block'])
        self.assertIn('phút', res['message'])   # the bilingual travel warning

    def test_exception_returns_super_untouched(self):
        from odoo.addons.health_fieldservice.models.health_staff_assignment \
            import HealthStaffAssignment as Base
        dropped, assignment, s_iso, e_iso = self._setup_drop()
        Assign = self.env['health.staff.assignment']
        Trans = self.env['health.route.transition']
        ok_base = {'ok': True, 'hard_block': False, 'reason': 'ok', 'message': 'X'}
        # Base forced OK so the warning seam is actually reached in both runs.
        with patch.object(Base, 'validate_drop', return_value=dict(ok_base)):
            with patch.object(type(Trans), '_drop_warnings', return_value=[]):
                baseline = Assign.validate_drop(self.staff.id, s_iso, e_iso,
                                                assignment_id=assignment.id)
            with patch.object(type(Trans), '_drop_warnings',
                              side_effect=Exception('boom')):
                raised = Assign.validate_drop(self.staff.id, s_iso, e_iso,
                                              assignment_id=assignment.id)
        self.assertEqual(raised, baseline)
        self.assertEqual(raised, ok_base)   # byte-identical to super


class TestProposerGuard(RoutesBase):

    def test_guard_drops_critical_keeps_feasible(self):
        Trans = self.env['health.route.transition']
        # Existing far visit ending 08:55 local (01:55 UTC) on the slot day.
        day = fields.Date.to_date('2026-08-28')
        existing_start = datetime(2026, 8, 28, 0, 0, 0)   # 07:00 local
        self._fso(self.far, existing_start, dur=115)      # ends 01:55 UTC / 08:55 local
        slot_critical = {'date': day, 'start_time': 9.0,   # 09:00 local, gap 5 → critical
                         'staff_id': self.staff.id, 'staff_name': 'RT', 'confidence': 0.5}
        slot_feasible = {'date': day, 'start_time': 14.0,  # 14:00 local, huge gap → ok
                         'staff_id': self.staff.id, 'staff_name': 'RT', 'confidence': 0.5}
        kept = Trans._filter_slots_travel(
            self.near, [slot_critical, slot_feasible])
        self.assertNotIn(slot_critical, kept)
        self.assertIn(slot_feasible, kept)

    def test_proposer_inherit_wires_the_guard(self):
        Offer = self.env['health.visit.offer']
        Trans = self.env['health.route.transition']
        # Identity filter → baseline list; raising filter → same list (super untouched).
        with patch.object(type(Trans), '_filter_slots_travel',
                          side_effect=lambda partner, slots: slots):
            baseline = Offer._propose_slots_for_partner(self.near, count=3)
        with patch.object(type(Trans), '_filter_slots_travel',
                          side_effect=Exception('boom')):
            raised = Offer._propose_slots_for_partner(self.near, count=3)
        self.assertEqual(raised, baseline)
        # Drop-everything filter → proposer returns [] (proves it is called).
        with patch.object(type(Trans), '_filter_slots_travel',
                          side_effect=lambda partner, slots: []):
            emptied = Offer._propose_slots_for_partner(self.near, count=3)
        self.assertEqual(emptied, [])

    def test_guard_timing_six_slots(self):
        """Report extra (c): the post-filter budget is < ~1s for 6 slots with a
        warm leg cache."""
        Trans = self.env['health.route.transition']
        day = fields.Date.to_date('2026-08-29')
        self._fso(self.far, datetime(2026, 8, 29, 0, 0, 0), dur=115)
        slots = [{'date': day, 'start_time': 9.0 + i, 'staff_id': self.staff.id,
                  'staff_name': 'RT', 'confidence': 0.5} for i in range(6)]
        Trans._filter_slots_travel(self.near, slots)   # warm the cache
        t0 = _time.perf_counter()
        Trans._filter_slots_travel(self.near, slots)
        elapsed = _time.perf_counter() - t0
        self.assertLess(elapsed, 1.0)


class TestFamilyEta(RoutesBase):

    def _link_and_event(self):
        fso = self._fso(self.near, datetime(2026, 8, 30, 1, 0, 0),
                        dur=60, staff=False)
        link = self.env['health.family.link'].new({'fso_id': fso.id})
        event = SimpleNamespace(lat=FAR_LAT, lng=BASE_LNG)   # nurse far from patient
        return link, event

    def test_road_minutes_rendered(self):
        link, event = self._link_and_event()
        # approx 57.8 min → round up to 60.
        txt = link._travel_eta_text(event)
        self.assertIn('60', txt)

    def test_unknown_falls_back_to_super(self):
        link, event = self._link_and_event()
        # leg unknown → super() haversine: 22.239/25*60 = 53.4 → round up to 55.
        with patch.object(type(self.env['health.route.leg']), 'leg_minutes',
                          return_value={'km': None, 'minutes': None,
                                        'method': 'unknown'}):
            txt = link._travel_eta_text(event)
        self.assertIn('55', txt)
