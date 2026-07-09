# -*- coding: utf-8 -*-
"""Tests for health_pwa_daystrip (handover §4).

Covers: the two new EVV event types (chain intact + geofence-inert),
completion unaffected by travel events, the family page "on the way"
context + ETA math, the public page block + meta-refresh gating, and the
shell asset/version pins.
"""
import os
import uuid
from datetime import datetime, timedelta

from odoo import fields
from odoo.tests import TransactionCase, HttpCase, tagged
from odoo.tests.common import new_test_user

BASE_LAT = 10.7769000
BASE_LNG = 106.7009000
DEG_30M = 30.0 / 111195.0        # ~30 m north (inside a 150 m fence)
DEG_5KM = 5000.0 / 111195.0      # ~5 km north (outside the fence; 12 min @ 25 km/h)


def _fixture(env):
    """Patient with coordinates + geofence (for the ETA math), a distinct
    representative for the family relation, and a staff employee."""
    Partner = env['res.partner']
    Facility = env['health.facility']

    province = env['health.catchment.province'].search([], limit=1)
    if not province:
        province = env['health.catchment.province'].create(
            {'name': 'DS Province', 'code': 'DSP'})
    facility = Facility.search(
        [('catchment_province_id', '=', province.id)], limit=1)
    if not facility:
        facility = Facility.create({
            'name': 'DS Facility', 'code': 'DSF',
            'street': '1 DS Street', 'city': 'Test City',
            'phone': '02838000000', 'timezone': 'Asia/Ho_Chi_Minh',
            'catchment_province_id': province.id,
        })
    patient = Partner.create({
        'name': 'DS Patient',
        'is_patient': True,
        'catchment_province_id': province.id,
        'primary_facility_id': facility.id,
        'mobile': '0912345678',
        'partner_latitude': BASE_LAT,
        'partner_longitude': BASE_LNG,
        'geofence_radius_m': 150,
        'geofence_enabled': True,
    })
    representative = Partner.create({
        'name': 'Nguyen Van Con',
        'is_representative': True,
        'mobile': '0987654321',
    })
    staff_user = env['res.users'].create({
        'name': 'DS Staff User',
        'login': 'ds_staff_%s' % uuid.uuid4().hex[:8],
        'email': 'ds_staff_%s@example.com' % uuid.uuid4().hex[:6],
    })
    staff = env['hr.employee'].create(
        {'name': 'Tran Thi Hoa', 'user_id': staff_user.id})
    product = env['product.product'].search([('sale_ok', '=', True)], limit=1)
    if not product:
        product = env['product.product'].create(
            {'name': 'DS Service', 'type': 'service', 'list_price': 100.0})
    return province, facility, patient, representative, staff, product


def _ensure_stages(env):
    Stage = env['health.fieldservice.stage']
    for state in ('confirmed', 'assigned', 'in_progress', 'completed'):
        if not Stage.search([('state', '=', state), ('active', '=', True)], limit=1):
            Stage.create({'name': state.title(), 'state': state})


class DaystripMixin:
    """FSO builders shared by TransactionCase and HttpCase suites."""

    def _make_fso(self, scheduled=None):
        fso = self.env['health.fieldservice.order'].create({
            'patient_id': self.patient.id,
            'facility_id': self.facility.id,
            'scheduled_datetime': scheduled or (
                fields.Datetime.now() + timedelta(days=1)),
            'scheduled_duration': 120,
            'service_type': 'home_visit',
        })
        so = self.env['sale.order'].create({
            'partner_id': self.patient.id,
            'fso_id': fso.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1, 'price_unit': 100.0})],
        })
        fso.sale_order_id = so.id
        fso.booking_timezone = 'Asia/Ho_Chi_Minh'
        return fso

    def _confirm(self, fso):
        fso.action_assign_staff_to_fso(self.staff.id, assignment_role='lead')
        fso.action_confirm_booking()
        return fso

    def _relation(self):
        return self.env['health.client.relation'].create({
            'client_id': self.patient.id,
            'representative_id': self.representative.id,
            'role': 'caregiver',
            'relationship_type': 'child',
            'receives_visit_updates': True,
            'can_receive_medical_info': True,
        })

    def _travel(self, fso, event_type, when=None, lat=0.0, lng=0.0):
        return self.env['health.evv.event'].append_event(fso, {
            'event_type': event_type,
            'event_datetime': when or fields.Datetime.now(),
            'lat': lat, 'lng': lng, 'accuracy_m': 10.0,
            'staff_id': self.staff.id,
            'device_uuid': 'dev-test',
            'client_event_uuid': str(uuid.uuid4()),
            'payload': {},
        })


@tagged('post_install', '-at_install')
class DaystripBase(TransactionCase, DaystripMixin):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        (cls.province, cls.facility, cls.patient, cls.representative,
         cls.staff, cls.product) = _fixture(cls.env)
        if not cls.env.user.employee_id:
            cls.env['hr.employee'].create(
                {'name': 'DS Admin Employee', 'user_id': cls.env.user.id})
            cls.env.user.invalidate_recordset()
        _ensure_stages(cls.env)

    def _upcoming_link(self, scheduled=None):
        fso = self._make_fso(scheduled=scheduled)
        self._confirm(fso)
        link = self.env['health.family.link']._get_or_create_link(
            fso, self._relation())
        return fso, link


# =====================================================================
# 1 — EVV event types: chain intact with mixed types, geofence-inert
# =====================================================================
@tagged('post_install', '-at_install')
class TestTravelEvents(DaystripBase):

    def test_travel_type_registered(self):
        selection = dict(
            self.env['health.evv.event']._fields['event_type'].selection)
        self.assertIn('travel_start', selection)
        self.assertIn('travel_cancel', selection)

    def test_mixed_chain_valid_and_geofence_inert(self):
        fso = self._make_fso()
        ci = self._travel(fso, 'checkin', lat=BASE_LAT + DEG_30M, lng=BASE_LNG)
        ts = self._travel(fso, 'travel_start',
                          lat=BASE_LAT + DEG_5KM, lng=BASE_LNG)
        co = self._travel(fso, 'checkout', lat=BASE_LAT + DEG_30M, lng=BASE_LNG)
        sig = self._travel(fso, 'signature', lat=BASE_LAT + DEG_30M,
                           lng=BASE_LNG, when=fields.Datetime.now())
        self.assertEqual([ci.sequence, ts.sequence, co.sequence, sig.sequence],
                         [1, 2, 3, 4])
        result = self.env['health.evv.event'].validate_chain(fso)
        self.assertTrue(result['valid'])
        self.assertIsNone(result['first_bad_sequence'])
        # The travel event, posted 5 km from home, is simply outside the
        # fence (inert data) — it does not create a violation and does not
        # degrade the visit's verification, which reads only checkin/checkout.
        self.assertFalse(ts.inside_geofence)
        fso.invalidate_recordset(['evv_verified'])
        self.assertTrue(fso.evv_verified)

    def test_travel_cancel_after_start_both_chain(self):
        fso = self._make_fso()
        self._travel(fso, 'travel_start', lat=BASE_LAT + DEG_5KM, lng=BASE_LNG)
        self._travel(fso, 'travel_cancel')
        self.assertTrue(
            self.env['health.evv.event'].validate_chain(fso)['valid'])


# =====================================================================
# 2 — Stage gates / completion unaffected by travel events
# =====================================================================
@tagged('post_install', '-at_install')
class TestStageGates(DaystripBase):

    def test_completion_unaffected_by_travel_events(self):
        fso = self._make_fso()
        self._confirm(fso)
        self._travel(fso, 'travel_start', lat=BASE_LAT + DEG_5KM, lng=BASE_LNG)
        fso.action_start_service()
        self.env['health.clinical.note'].create(
            {'order_id': fso.id, 'clinical_notes': 'ok'})
        fso.action_complete_service()
        self.assertIn(fso.state, ('completed', 'completed_pending_invoice'))


# =====================================================================
# 3 — Family _page_context: on_the_way, staleness, cancel, precedence, ETA
# =====================================================================
@tagged('post_install', '-at_install')
class TestFamilyContext(DaystripBase):

    def test_fresh_travel_start_flips_to_on_the_way(self):
        fso, link = self._upcoming_link()
        self._travel(fso, 'travel_start', lat=BASE_LAT + DEG_5KM, lng=BASE_LNG)
        self.assertEqual(link._page_context()['mode'], 'on_the_way')

    def test_stale_travel_start_is_plain_upcoming(self):
        fso, link = self._upcoming_link()
        self._travel(fso, 'travel_start',
                     when=fields.Datetime.now() - timedelta(hours=4),
                     lat=BASE_LAT + DEG_5KM, lng=BASE_LNG)
        self.assertEqual(link._page_context()['mode'], 'upcoming')

    def test_travel_cancel_reverts_to_upcoming(self):
        fso, link = self._upcoming_link()
        self._travel(fso, 'travel_start', lat=BASE_LAT + DEG_5KM, lng=BASE_LNG)
        self._travel(fso, 'travel_cancel')
        self.assertEqual(link._page_context()['mode'], 'upcoming')

    def test_in_progress_arrived_takes_precedence(self):
        fso, link = self._upcoming_link()
        self._travel(fso, 'travel_start', lat=BASE_LAT + DEG_5KM, lng=BASE_LNG)
        fso.action_start_service()
        self.assertEqual(link._page_context()['mode'], 'arrived')

    def test_eta_text_from_known_coords(self):
        fso, link = self._upcoming_link()
        # 5 km north / 25 km/h = 12 min -> rounded up to 15.
        self._travel(fso, 'travel_start', lat=BASE_LAT + DEG_5KM, lng=BASE_LNG)
        ctx = link._page_context()
        self.assertEqual(ctx['mode'], 'on_the_way')
        self.assertEqual(ctx['eta_text'], 'khoảng 15 phút (about 15 min)')

    def test_eta_empty_when_event_coords_missing(self):
        fso, link = self._upcoming_link()
        self._travel(fso, 'travel_start', lat=0.0, lng=0.0)
        ctx = link._page_context()
        self.assertEqual(ctx['mode'], 'on_the_way')
        self.assertEqual(ctx['eta_text'], '')


# =====================================================================
# 4 — Public page: on-the-way block + meta refresh ONLY in that mode
# =====================================================================
@tagged('post_install', '-at_install')
class TestPublicOnTheWay(HttpCase, DaystripMixin):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        (cls.province, cls.facility, cls.patient, cls.representative,
         cls.staff, cls.product) = _fixture(cls.env)
        if not cls.env.user.employee_id:
            cls.env['hr.employee'].create(
                {'name': 'DS Admin Emp', 'user_id': cls.env.user.id})
            cls.env.user.invalidate_recordset()
        _ensure_stages(cls.env)

    def test_block_and_meta_refresh_gated_by_mode(self):
        fso = self._make_fso()
        self._confirm(fso)
        link = self.env['health.family.link']._get_or_create_link(
            fso, self._relation())
        # Fresh travel_start -> on-the-way page.
        self._travel(fso, 'travel_start', lat=BASE_LAT + DEG_5KM, lng=BASE_LNG)
        resp = self.url_open('/family/visit/%s' % link.token)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('trên đường', resp.text)
        self.assertIn('http-equiv="refresh"', resp.text)

        # Cancel travel -> plain upcoming: no block, no meta refresh.
        self._travel(fso, 'travel_cancel')
        resp2 = self.url_open('/family/visit/%s' % link.token)
        self.assertEqual(resp2.status_code, 200)
        self.assertIn('Sắp diễn ra', resp2.text)
        self.assertNotIn('http-equiv="refresh"', resp2.text)


# =====================================================================
# 5 — Shell HttpCase: daystrip assets + version 1.9.0, ergo still served
# =====================================================================
@tagged('post_install', '-at_install')
class TestShellAssets(HttpCase):

    def test_shell_serves_daystrip_at_1_8_0(self):
        user = new_test_user(
            self.env, login='ds_shell_user', groups='base.group_user')
        self.authenticate(user.login, user.login)
        res = self.url_open('/health_pwa')
        self.assertEqual(res.status_code, 200)
        body = res.text
        self.assertIn('daystrip.css?v=1.9.0', body)
        self.assertIn('daystrip.js?v=1.9.0', body)
        self.assertIn('1.9.0', body)
        # Co-resident ergo assets must still be served after the bump.
        self.assertIn('ergo.css?v=1.9.0', body)


# =====================================================================
# 6 — Static CSS pin: ergo-compat sections exist
# =====================================================================
@tagged('post_install', '-at_install')
class TestCssPins(TransactionCase):

    def test_glove_and_sunlight_rules_present(self):
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(here, 'static', 'src', 'css', 'daystrip.css'),
                  encoding='utf-8') as fh:
            css = fh.read()
        self.assertIn('html.vu-glove', css)
        self.assertIn('html.vu-sunlight', css)
        self.assertIn('--touch-target', css)
