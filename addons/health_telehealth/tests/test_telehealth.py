# -*- coding: utf-8 -*-
"""Tests for health_telehealth (handover §4).

Covers: session creation + ZNS rails matrix at confirm, home-visit scoping,
double-confirm idempotency, the waiting-room page state machine + URL gating
+ meta refresh, the PWA join endpoint access rule, the EVV online geofence
exemption, the logged consent check, timezone correctness, and hook
resilience.
"""
import os
import uuid
from datetime import datetime, timedelta
from unittest.mock import patch

from odoo import fields
from odoo.tests import TransactionCase, HttpCase, tagged
from odoo.tests.common import new_test_user

BASE_LAT = 10.7769000
BASE_LNG = 106.7009000
DEG_5KM = 5000.0 / 111195.0      # ~5 km north — outside a 150 m home fence


def _fixture(env):
    Partner = env['res.partner']
    Facility = env['health.facility']

    province = env['health.catchment.province'].search([], limit=1)
    if not province:
        province = env['health.catchment.province'].create(
            {'name': 'TH Province', 'code': 'THP'})
    facility = Facility.search(
        [('catchment_province_id', '=', province.id)], limit=1)
    if not facility:
        facility = Facility.create({
            'name': 'TH Facility', 'code': 'THF',
            'street': '1 TH Street', 'city': 'Test City',
            'phone': '02838000000', 'timezone': 'Asia/Ho_Chi_Minh',
            'catchment_province_id': province.id,
        })
    patient = Partner.create({
        'name': 'TH Patient',
        'is_patient': True,
        'catchment_province_id': province.id,
        'primary_facility_id': facility.id,
        'mobile': '0912345678',
        'partner_latitude': BASE_LAT,
        'partner_longitude': BASE_LNG,
        'geofence_radius_m': 150,
        'geofence_enabled': True,
    })
    staff_user = env['res.users'].create({
        'name': 'TH Staff User',
        'login': 'th_staff_%s' % uuid.uuid4().hex[:8],
        'email': 'th_staff_%s@example.com' % uuid.uuid4().hex[:6],
    })
    staff = env['hr.employee'].create(
        {'name': 'Bac Si Minh', 'user_id': staff_user.id})
    product = env['product.product'].search([('sale_ok', '=', True)], limit=1)
    if not product:
        product = env['product.product'].create(
            {'name': 'TH Service', 'type': 'service', 'list_price': 100.0})
    return province, facility, patient, staff_user, staff, product


def _ensure_stages(env):
    Stage = env['health.fieldservice.stage']
    for state in ('confirmed', 'assigned', 'in_progress', 'completed'):
        if not Stage.search([('state', '=', state), ('active', '=', True)], limit=1):
            Stage.create({'name': state.title(), 'state': state})


class TeleMixin:
    """FSO builders shared by TransactionCase and HttpCase suites."""

    def _make_fso(self, online=True, scheduled=None):
        fso = self.env['health.fieldservice.order'].create({
            'patient_id': self.patient.id,
            'facility_id': self.facility.id,
            'scheduled_datetime': scheduled or (
                fields.Datetime.now() + timedelta(days=1)),
            'scheduled_duration': 120,
            'service_type': 'telemedicine' if online else 'home_visit',
            'service_location': 'online' if online else 'home',
        })
        so = self.env['sale.order'].create({
            'partner_id': self.patient.id,
            'fso_id': fso.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1, 'price_unit': 100.0})],
        })
        fso.sale_order_id = so.id
        return fso

    def _confirm(self, fso):
        fso.action_assign_staff_to_fso(self.staff.id, assignment_role='lead')
        fso.action_confirm_booking()
        return fso

    def _evv(self, fso, event_type, when=None, lat=0.0, lng=0.0):
        return self.env['health.evv.event'].append_event(fso, {
            'event_type': event_type,
            'event_datetime': when or fields.Datetime.now(),
            'lat': lat, 'lng': lng, 'accuracy_m': 10.0,
            'staff_id': self.staff.id,
            'device_uuid': 'dev-test',
            'client_event_uuid': str(uuid.uuid4()),
            'payload': {},
        })

    def _set_rails(self, template='', enabled=False, dry_run=True):
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('health_telehealth.zns_template_join', template)
        ICP.set_param('health_messaging.enabled', 'True' if enabled else 'False')
        ICP.set_param('health_messaging.dry_run', 'True' if dry_run else 'False')


@tagged('post_install', '-at_install')
class TeleBase(TransactionCase, TeleMixin):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        (cls.province, cls.facility, cls.patient, cls.staff_user,
         cls.staff, cls.product) = _fixture(cls.env)
        if not cls.env.user.employee_id:
            cls.env['hr.employee'].create(
                {'name': 'TH Admin Employee', 'user_id': cls.env.user.id})
            cls.env.user.invalidate_recordset()
        _ensure_stages(cls.env)


# =====================================================================
# 1 — Confirm online FSO: session + ZNS rails matrix
# =====================================================================
@tagged('post_install', '-at_install')
class TestConfirmSession(TeleBase):

    def test_online_confirm_creates_session_and_fills_fso(self):
        self._set_rails(template='999', enabled=True, dry_run=True)
        fso = self._make_fso(online=True)
        self._confirm(fso)
        session = self.env['health.telehealth.session'].search(
            [('fso_id', '=', fso.id)])
        self.assertEqual(len(session), 1)
        self.assertEqual(session.state, 'pending')
        self.assertTrue(session.room_slug)
        # The ONLY FSO write: the shipped online-visit fields now show the room.
        self.assertEqual(fso.online_meeting_url, session.room_url)
        self.assertEqual(fso.online_platform, 'custom')
        # Dry-run -> a simulated (not sent) join row.
        self.assertEqual(session.outbound_message_id.state, 'simulated')

    def test_empty_template_creates_no_row(self):
        self._set_rails(template='', enabled=True, dry_run=True)
        fso = self._make_fso(online=True)
        self._confirm(fso)
        session = self.env['health.telehealth.session'].search(
            [('fso_id', '=', fso.id)])
        self.assertTrue(session)
        self.assertFalse(session.outbound_message_id)

    def test_disabled_messaging_skips_send(self):
        self._set_rails(template='999', enabled=False, dry_run=True)
        fso = self._make_fso(online=True)
        self._confirm(fso)
        session = self.env['health.telehealth.session'].search(
            [('fso_id', '=', fso.id)])
        self.assertEqual(session.outbound_message_id.state, 'skipped')


# =====================================================================
# 2 — Home visit scoping: no session, no rows
# =====================================================================
@tagged('post_install', '-at_install')
class TestScoping(TeleBase):

    def test_home_visit_no_session(self):
        self._set_rails(template='999', enabled=True, dry_run=True)
        fso = self._make_fso(online=False)
        self._confirm(fso)
        self.assertFalse(self.env['health.telehealth.session'].search(
            [('fso_id', '=', fso.id)]))


# =====================================================================
# 3 — Double confirm: one session, one row (dedup + search-first)
# =====================================================================
@tagged('post_install', '-at_install')
class TestIdempotency(TeleBase):

    def test_double_confirm_single_session_and_row(self):
        self._set_rails(template='999', enabled=True, dry_run=True)
        fso = self._make_fso(online=True)
        self._confirm(fso)
        fso.action_confirm_booking()   # confirm again
        sessions = self.env['health.telehealth.session'].search(
            [('fso_id', '=', fso.id)])
        self.assertEqual(len(sessions), 1)
        rows = self.env['health.outbound.message'].search(
            [('dedup_key', '=', 'telejoin-%s' % sessions.id)])
        self.assertEqual(len(rows), 1)


# =====================================================================
# 4 — EVV online geofence exemption
# =====================================================================
@tagged('post_install', '-at_install')
class TestEvvExemption(TeleBase):

    def test_online_verifies_outside_geofence(self):
        fso = self._make_fso(online=True)
        self._confirm(fso)
        self._evv(fso, 'checkin', lat=BASE_LAT + DEG_5KM, lng=BASE_LNG)
        self._evv(fso, 'checkout', lat=BASE_LAT + DEG_5KM, lng=BASE_LNG)
        fso.invalidate_recordset(['evv_verified'])
        self.assertTrue(fso.evv_verified)

    def test_home_visit_outside_geofence_unchanged(self):
        fso = self._make_fso(online=False)
        self._confirm(fso)
        self._evv(fso, 'checkin', lat=BASE_LAT + DEG_5KM, lng=BASE_LNG)
        self._evv(fso, 'checkout', lat=BASE_LAT + DEG_5KM, lng=BASE_LNG)
        fso.invalidate_recordset(['evv_verified'])
        self.assertFalse(fso.evv_verified)


# =====================================================================
# 5 — Consent check logged at confirm (log-only; confirm still succeeds)
# =====================================================================
@tagged('post_install', '-at_install')
class TestConsentLogged(TeleBase):

    def test_service_consent_check_logged(self):
        self._set_rails(template='', enabled=False, dry_run=True)
        fso = self._make_fso(online=True)
        before = self.env['health.consent.check.log'].search_count([
            ('client_id', '=', self.patient.id),
            ('consent_type', '=', 'service')])
        self._confirm(fso)
        after = self.env['health.consent.check.log'].search_count([
            ('client_id', '=', self.patient.id),
            ('consent_type', '=', 'service')])
        self.assertGreater(after, before)
        self.assertEqual(fso.state, 'confirmed')


# =====================================================================
# 6 — Timezone: 02:00 UTC + Asia/Ho_Chi_Minh -> 09:00 wall clock
# =====================================================================
@tagged('post_install', '-at_install')
class TestTimezone(TeleBase):

    def test_pending_time_window_is_wall_clock(self):
        self._set_rails(template='', enabled=False, dry_run=True)
        # 02:00 UTC -> 09:00 Asia/Ho_Chi_Minh (facility tz).
        sched = datetime(2026, 8, 1, 2, 0, 0)
        fso = self._make_fso(online=True, scheduled=sched)
        self._confirm(fso)
        session = self.env['health.telehealth.session'].search(
            [('fso_id', '=', fso.id)])
        ctx = session._page_context()
        self.assertEqual(ctx['mode'], 'pending')
        self.assertTrue(ctx['time_window'].startswith('09:00'))


# =====================================================================
# 7 — Hook resilience: a send failure never blocks confirmation
# =====================================================================
@tagged('post_install', '-at_install')
class TestHookResilience(TeleBase):

    def test_confirm_survives_send_exception(self):
        self._set_rails(template='999', enabled=True, dry_run=True)
        fso = self._make_fso(online=True)
        target = ('odoo.addons.health_telehealth.models.telehealth_session.'
                  'HealthTelehealthSession._send_join_zns')
        with patch(target, side_effect=ValueError('boom')):
            self._confirm(fso)
        self.assertEqual(fso.state, 'confirmed')
        # The session itself is still created (creation precedes the send).
        self.assertTrue(self.env['health.telehealth.session'].search(
            [('fso_id', '=', fso.id)]))


# =====================================================================
# 8 — Join-URL access rule (method-level: assigned / unassigned / draft)
# =====================================================================
@tagged('post_install', '-at_install')
class TestJoinAccess(TeleBase):

    def test_join_url_rules(self):
        self._set_rails(template='', enabled=False, dry_run=True)
        # Assigned staff + in_progress -> url (identity is the assignment, so
        # no catchment is required — the method sudo-reads and gates on user).
        fso = self._make_fso(online=True)
        self._confirm(fso)
        fso.action_start_service()
        url = fso.with_user(self.staff_user)._tele_join_url()
        self.assertTrue(url)
        self.assertIn(fso.telehealth_session_id.room_slug, url)

        # Unassigned nurse -> empty (not assigned, not privileged).
        other_user = new_test_user(
            self.env, login='th_other_%s' % uuid.uuid4().hex[:6],
            groups='base.group_user,health_base.group_healthcare_nurse')
        self.env['hr.employee'].create(
            {'name': 'TH Other', 'user_id': other_user.id})
        other_user.invalidate_recordset()
        self.assertFalse(fso.with_user(other_user)._tele_join_url())

        # Draft (unconfirmed) online FSO -> empty (no session).
        draft = self._make_fso(online=True)
        self.assertFalse(draft.with_user(self.staff_user)._tele_join_url())


# =====================================================================
# 9 — Waiting-room page state machine + URL gating + meta refresh (HTTP)
# =====================================================================
@tagged('post_install', '-at_install')
class TestWaitingRoom(HttpCase, TeleMixin):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        (cls.province, cls.facility, cls.patient, cls.staff_user,
         cls.staff, cls.product) = _fixture(cls.env)
        if not cls.env.user.employee_id:
            cls.env['hr.employee'].create(
                {'name': 'TH Admin Emp', 'user_id': cls.env.user.id})
            cls.env.user.invalidate_recordset()
        _ensure_stages(cls.env)
        cls.env['ir.config_parameter'].sudo().set_param(
            'health_telehealth.zns_template_join', '')

    def test_page_states_and_url_gating(self):
        fso = self._make_fso(online=True)
        self._confirm(fso)
        session = self.env['health.telehealth.session'].search(
            [('fso_id', '=', fso.id)])
        slug = session.room_slug
        token = session.patient_token

        # pending: date/staff shown, room URL absent, meta refresh present.
        resp = self.url_open('/tele/visit/%s' % token)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Sắp diễn ra', resp.text)
        self.assertNotIn(slug, resp.text)
        self.assertIn('http-equiv="refresh"', resp.text)

        # open (in_progress): the Join URL appears — the ONLY state with it.
        fso.action_start_service()
        resp2 = self.url_open('/tele/visit/%s' % token)
        self.assertEqual(resp2.status_code, 200)
        self.assertIn(slug, resp2.text)
        self.assertIn('http-equiv="refresh"', resp2.text)

        # closed (completed): thank-you body, URL gone again.
        self.env['health.clinical.note'].create(
            {'order_id': fso.id, 'clinical_notes': 'done'})
        fso.action_complete_service()
        resp3 = self.url_open('/tele/visit/%s' % token)
        self.assertEqual(resp3.status_code, 200)
        self.assertIn('đã kết thúc', resp3.text)
        self.assertNotIn(slug, resp3.text)
        self.assertNotIn('http-equiv="refresh"', resp3.text)

        # bogus token -> identical neutral page.
        resp4 = self.url_open('/tele/visit/nope-not-a-real-token')
        self.assertEqual(resp4.status_code, 200)
        self.assertIn('Không có thông tin', resp4.text)
        self.assertNotIn(slug, resp4.text)


# =====================================================================
# 10 — Join endpoint (HTTP) + shell asset/version pins
# =====================================================================
@tagged('post_install', '-at_install')
class TestEndpointAndShell(HttpCase, TeleMixin):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        (cls.province, cls.facility, cls.patient, cls.staff_user,
         cls.staff, cls.product) = _fixture(cls.env)
        if not cls.env.user.employee_id:
            cls.env['hr.employee'].create(
                {'name': 'TH Admin Emp2', 'user_id': cls.env.user.id})
            cls.env.user.invalidate_recordset()
        _ensure_stages(cls.env)
        cls.env['ir.config_parameter'].sudo().set_param(
            'health_telehealth.zns_template_join', '')

    def test_join_endpoint_returns_url_for_assigned_staff(self):
        # A real login-able nurse (new_test_user: login == password), assigned
        # to the visit. No catchment set -> proves the endpoint's sudo-existence
        # + assignment-based access (ledger §5 #4) works end to end over HTTP.
        nurse = new_test_user(
            self.env, login='th_join_%s' % uuid.uuid4().hex[:6],
            groups='base.group_user,health_base.group_healthcare_nurse')
        emp = self.env['hr.employee'].create(
            {'name': 'TH Join Nurse', 'user_id': nurse.id})
        nurse.invalidate_recordset()
        fso = self._make_fso(online=True)
        fso.action_assign_staff_to_fso(emp.id, assignment_role='lead')
        fso.action_confirm_booking()
        fso.action_start_service()
        self.authenticate(nurse.login, nurse.login)
        res = self.url_open('/health_pwa/api/fso/%s/tele/join' % fso.id)
        self.assertEqual(res.status_code, 200)
        self.assertIn(fso.telehealth_session_id.room_slug, res.text)

    def test_shell_serves_telehealth_at_1_8_0(self):
        user = new_test_user(
            self.env, login='th_shell_user', groups='base.group_user')
        self.authenticate(user.login, user.login)
        res = self.url_open('/health_pwa')
        self.assertEqual(res.status_code, 200)
        body = res.text
        self.assertIn('telehealth.css?v=1.8.0', body)
        self.assertIn('telehealth.js?v=1.8.0', body)
        # Co-resident daystrip + ergo assets must still be served after the bump.
        self.assertIn('daystrip.js?v=1.8.0', body)
        self.assertIn('ergo.css?v=1.8.0', body)


# =====================================================================
# 11 — Static CSS pin: ergo-compat sections exist
# =====================================================================
@tagged('post_install', '-at_install')
class TestCssPins(TransactionCase):

    def test_glove_and_sunlight_rules_present(self):
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(here, 'static', 'src', 'css', 'telehealth.css'),
                  encoding='utf-8') as fh:
            css = fh.read()
        self.assertIn('html.vu-glove', css)
        self.assertIn('html.vu-sunlight', css)
        self.assertIn('--touch-target', css)
