# -*- coding: utf-8 -*-
"""Tests for the pwa-cache-hygiene phase.

Server-contract coverage for the three server-side changes: honest cap
semantics on the FSO delta (`capped` flag + scheduled_datetime-desc selection +
uncapped removals), the tightened `health.pwa.staff.notification` ACL, and the
deprecated `check_access_rights` -> `check_access` swap at the three endpoint
gates. The client-side patient GC itself is JS and is verified in browser QA;
these tests pin the server flag the GC keys on.

§5.32-aware: none of these HttpCases completes a visit, so no config-param
pinning is needed. The cap tests monkeypatch the MODULE attribute
`FSO_UPSERT_CAP` (the controller reads it as a module global at call time, so
the patch is visible to the in-process test server) and restore it via
addCleanup.
"""
import uuid
from datetime import timedelta
from urllib.parse import quote

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import HttpCase, TransactionCase, tagged, new_test_user

import odoo.addons.health_pwa.controllers.sync as sync_controller


def _iso(dt):
    return dt.isoformat()


@tagged('post_install', '-at_install')
class CacheHygieneBase(HttpCase):
    """Minimal own-fixtures base: a single minimal nurse with exactly the
    orders each test creates (no shared order set, so the cap tests can assert
    exact record counts)."""

    def setUp(self):
        super().setUp()
        Province = self.env['health.catchment.province']
        Facility = self.env['health.facility']
        self.province = Province.create({
            'name': 'Cache P %s' % uuid.uuid4().hex[:5],
            'code': 'CP%s' % uuid.uuid4().hex[:3]})
        self.facility = Facility.create({
            'name': 'Cache Facility', 'code': 'CF%s' % uuid.uuid4().hex[:3],
            'street': '1 C St', 'city': 'C City',
            'catchment_province_id': self.province.id})

        # Minimal nurse: nurse group only, NO catchment, NO sale/account ACL.
        self.nurse_user = new_test_user(
            self.env, login='cache_nurse_%s' % uuid.uuid4().hex[:6],
            groups='base.group_user,health_base.group_healthcare_nurse',
            password='cachenursepw')
        self.nurse_user.write({'catchment_province_id': False})
        self.nurse_staff = self.env['hr.employee'].create(
            {'name': 'Cache Nurse Emp', 'user_id': self.nurse_user.id})

    # -- fixtures -----------------------------------------------------------
    def _patient(self, name):
        return self.env['res.partner'].create({
            'name': name, 'is_patient': True,
            'catchment_province_id': self.province.id,
            'primary_facility_id': self.facility.id,
            'mobile': '09%08d' % (uuid.uuid4().int % 10 ** 8)})

    def _order(self, patient, days_ahead=1):
        return self.env['health.fieldservice.order'].create({
            'patient_id': patient.id, 'facility_id': self.facility.id,
            'scheduled_datetime': fields.Datetime.now() + timedelta(days=days_ahead),
            'scheduled_duration': 120, 'service_type': 'home_visit'})

    def _assign(self, order, staff=None):
        order.action_assign_staff_to_fso(
            (staff or self.nurse_staff).id, assignment_role='lead')

    # -- endpoint helpers ---------------------------------------------------
    def _changes(self, since=None, force_full=False):
        url = '/health_pwa/sync/changes'
        params = []
        if force_full:
            params.append('force_full=true')
        if since is not None:
            params.append('since=%s' % quote(since))
        if params:
            url += '?' + '&'.join(params)
        return self.url_open(url).json()

    def _far_past(self):
        return _iso(fields.Datetime.now() - timedelta(days=365))

    def _data_ids(self, resp, key='field_service_orders'):
        recs = resp['changes'][key]['records']
        return [r['id'] for r in recs if not r.get('is_deleted')]

    def _removal_ids(self, resp, key='field_service_orders'):
        recs = resp['changes'][key]['records']
        return {r['id'] for r in recs if r.get('is_deleted')}

    def _patch_cap(self, value):
        orig = sync_controller.FSO_UPSERT_CAP
        sync_controller.FSO_UPSERT_CAP = value
        self.addCleanup(setattr, sync_controller, 'FSO_UPSERT_CAP', orig)


# =====================================================================
# 1 — staff-notification ACL tightening (TransactionCase)
# =====================================================================
@tagged('post_install', '-at_install')
class TestStaffNotificationACL(TransactionCase):

    def test_nurse_cannot_crud_notifications(self):
        # After tightening to base.group_system, an ordinary internal/nurse
        # user has NO access to the PHI-adjacent notification model. Every real
        # code path is sudo, so this closes the CRUD hole without breaking them.
        nurse = new_test_user(
            self.env, login='acl_nurse_%s' % uuid.uuid4().hex[:6],
            groups='base.group_user,health_base.group_healthcare_nurse')
        Notif = self.env['health.pwa.staff.notification'].with_user(nurse)
        with self.assertRaises(AccessError):
            Notif.search([])
        with self.assertRaises(AccessError):
            Notif.create({
                'user_id': nurse.id, 'notification_type': 'cancelled',
                'patient_name': 'Leak'})


# =====================================================================
# 2 — bell still works via the sudo path (HttpCase)
# =====================================================================
@tagged('post_install', '-at_install')
class TestBellStillWorks(CacheHygieneBase):

    def test_notifications_endpoint_ok_for_nurse(self):
        # The pending-notifications endpoint reads the tightened model via
        # .sudo(), so the ACL change must not break it for a plain nurse.
        self.authenticate(self.nurse_user.login, 'cachenursepw')
        r = self.url_open('/health_pwa/api/notifications/pending')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['success'], r.json())


# =====================================================================
# 3-5 — honest cap semantics (HttpCase)
# =====================================================================
@tagged('post_install', '-at_install')
class TestHonestCap(CacheHygieneBase):

    def test_capped_flag_and_latest_selected(self):
        # cap = 2, four assigned orders -> exactly 2 data records, capped True,
        # and the two returned are the LATEST by scheduled_datetime.
        self._patch_cap(2)
        orders = []
        for i in range(4):
            o = self._order(self._patient('Cap P%d' % i), days_ahead=i + 1)
            self._assign(o)
            orders.append(o)

        self.authenticate(self.nurse_user.login, 'cachenursepw')
        resp = self._changes(since=self._far_past())
        self.assertTrue(resp['success'], resp)

        fso = resp['changes']['field_service_orders']
        data_ids = self._data_ids(resp)
        self.assertEqual(len(data_ids), 2, resp)
        self.assertTrue(fso.get('capped'), resp)
        # days_ahead 4 and 3 are the two latest.
        self.assertEqual(set(data_ids), {orders[3].id, orders[2].id})

    def test_capped_absent_when_under_cap(self):
        # Unpatched (cap 500), four orders -> no capped key, all four records.
        for i in range(4):
            o = self._order(self._patient('Uncap P%d' % i), days_ahead=i + 1)
            self._assign(o)

        self.authenticate(self.nurse_user.login, 'cachenursepw')
        resp = self._changes(since=self._far_past())
        fso = resp['changes']['field_service_orders']
        self.assertFalse(fso.get('capped'), resp)
        self.assertEqual(len(self._data_ids(resp)), 4, resp)

    def test_removals_uncapped_under_cap(self):
        # cap = 1, two in-scope orders + one de-scoped (cancelled assignment).
        # The capped data set is 1 row but the removal STILL arrives.
        self._patch_cap(1)
        for i in range(2):
            o = self._order(self._patient('Keep P%d' % i), days_ahead=i + 1)
            self._assign(o)
        gone = self._order(self._patient('Gone P'), days_ahead=1)
        self._assign(gone)
        gone.assignment_ids.write({'state': 'cancelled'})  # out of scope now

        self.authenticate(self.nurse_user.login, 'cachenursepw')
        resp = self._changes(since=self._far_past())
        fso = resp['changes']['field_service_orders']
        self.assertEqual(len(self._data_ids(resp)), 1, resp)   # cap = 1
        self.assertTrue(fso.get('capped'), resp)
        self.assertIn(gone.id, self._removal_ids(resp))        # removal uncapped


# =====================================================================
# 6 — fact-8 deprecated-API swap smoke (HttpCase)
# =====================================================================
@tagged('post_install', '-at_install')
class TestCheckAccessSwap(CacheHygieneBase):

    def test_gated_routes_still_200(self):
        # A 200 proves check_access('read') returned True in each gate (the
        # gates swallow exceptions and return False -> 403/denied, so an
        # AttributeError from a bad swap could never masquerade as success).
        self.authenticate(self.nurse_user.login, 'cachenursepw')

        # sync.py:_check_sync_access
        r1 = self.url_open('/health_pwa/sync/changes?since=%s' % quote(self._far_past()))
        self.assertEqual(r1.status_code, 200)
        self.assertTrue(r1.json()['success'], r1.json())

        # api.py:_check_api_access (patients list is gated on it)
        r2 = self.url_open('/health_pwa/api/patients')
        self.assertEqual(r2.status_code, 200)
        self.assertTrue(r2.json()['success'], r2.json())

        # pwa.py:_check_health_access (the /health_pwa shell route)
        r3 = self.url_open('/health_pwa')
        self.assertEqual(r3.status_code, 200)


# =====================================================================
# 7 — no patient leak around the cap-sort edit (HttpCase)
# =====================================================================
@tagged('post_install', '-at_install')
class TestNoPatientLeak(CacheHygieneBase):

    def test_out_of_scope_patient_never_appears(self):
        # A patient whose only order belongs to ANOTHER nurse must never appear
        # in this nurse's delta — the cap-sort refactor must not widen scope.
        mine = self._order(self._patient('Mine P'), days_ahead=1)
        self._assign(mine)

        other_user = new_test_user(
            self.env, login='cache_other_%s' % uuid.uuid4().hex[:6],
            groups='base.group_user,health_base.group_healthcare_nurse',
            password='cacheotherpw')
        other_staff = self.env['hr.employee'].create(
            {'name': 'Cache Other Emp', 'user_id': other_user.id})
        secret_patient = self._patient('Secret P')
        theirs = self._order(secret_patient, days_ahead=1)
        self._assign(theirs, staff=other_staff)

        self.authenticate(self.nurse_user.login, 'cachenursepw')
        resp = self._changes(since=self._far_past())
        patient_data = self._data_ids(resp, 'patients')
        patient_removals = self._removal_ids(resp, 'patients')
        self.assertIn(mine.patient_id.id, patient_data)
        self.assertNotIn(secret_patient.id, patient_data)
        self.assertNotIn(secret_patient.id, patient_removals)
        self.assertNotIn(theirs.id, self._data_ids(resp))
