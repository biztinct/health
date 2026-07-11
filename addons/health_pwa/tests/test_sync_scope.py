# -*- coding: utf-8 -*-
"""Tests for the scoped incremental sync delta (pwa-sync-delta phase).

HttpCase throughout: the scope + sudo path only means anything through the
real routes with a real authenticated (minimal-ACL) user. §5.32 aware — no
test here completes a visit, so no config-param pinning is required.
"""
import json
import uuid
from datetime import datetime, timedelta
from urllib.parse import quote

from odoo import fields
from odoo.tests import HttpCase, tagged, new_test_user


def _iso(dt):
    return dt.isoformat()


@tagged('post_install', '-at_install')
class SyncScopeBase(HttpCase):

    def setUp(self):
        super().setUp()
        Partner = self.env['res.partner']
        Province = self.env['health.catchment.province']
        Facility = self.env['health.facility']

        # Two provinces so the manager/owner audience test has an X and a Y.
        self.province_x = Province.create({'name': 'Sync X %s' % uuid.uuid4().hex[:5],
                                           'code': 'SX%s' % uuid.uuid4().hex[:3]})
        self.province_y = Province.create({'name': 'Sync Y %s' % uuid.uuid4().hex[:5],
                                           'code': 'SY%s' % uuid.uuid4().hex[:3]})
        self.facility_x = Facility.create({
            'name': 'Sync Facility X', 'code': 'SFX%s' % uuid.uuid4().hex[:3],
            'street': '1 X St', 'city': 'X City',
            'catchment_province_id': self.province_x.id})
        self.facility_y = Facility.create({
            'name': 'Sync Facility Y', 'code': 'SFY%s' % uuid.uuid4().hex[:3],
            'street': '1 Y St', 'city': 'Y City',
            'catchment_province_id': self.province_y.id})

        # Patients (need catchment_province_id, conventions §6).
        self.patient_a = self._patient('Sync Patient A', self.province_x, self.facility_x)
        self.patient_b = self._patient('Sync Patient B', self.province_x, self.facility_x)
        self.patient_c = self._patient('Sync Patient C', self.province_x, self.facility_x)
        self.patient_y = self._patient('Sync Patient Y', self.province_y, self.facility_y)

        # The headline user: a MINIMAL nurse — NO catchment, NO sale/account
        # ACL, just the nurse group + a password to authenticate.
        self.nurse_user = new_test_user(
            self.env, login='sync_nurse_%s' % uuid.uuid4().hex[:6],
            groups='base.group_user,health_base.group_healthcare_nurse',
            password='syncnursepw')
        self.nurse_user.write({'catchment_province_id': False})
        self.nurse_staff = self.env['hr.employee'].create(
            {'name': 'Sync Nurse Emp', 'user_id': self.nurse_user.id})

        # A second nurse (the "other staff" — order B belongs to them).
        self.other_user = new_test_user(
            self.env, login='sync_other_%s' % uuid.uuid4().hex[:6],
            groups='base.group_user,health_base.group_healthcare_nurse',
            password='syncotherpw')
        self.other_staff = self.env['hr.employee'].create(
            {'name': 'Sync Other Emp', 'user_id': self.other_user.id})

        # A system admin user for the debug-gate test — base.group_system
        # passes the gate; the owner group lets the debug body read the health
        # models (group_system alone does NOT bypass ACLs, only superuser does).
        self.sys_user = new_test_user(
            self.env, login='sync_sys_%s' % uuid.uuid4().hex[:6],
            groups='base.group_user,base.group_system,health_base.group_healthcare_owner',
            password='syncsyspw')

        # Orders. A -> nurse, B -> other, C -> team (nurse is a member).
        self.order_a = self._order(self.patient_a, self.facility_x)
        self._assign(self.order_a, self.nurse_staff)
        self.order_b = self._order(self.patient_b, self.facility_x)
        self._assign(self.order_b, self.other_staff)

        self.team = self.env['health.fieldservice.team'].create({
            'name': 'Sync Team %s' % uuid.uuid4().hex[:5],
            'member_ids': [(4, self.nurse_user.id)]})
        self.order_c = self._order(self.patient_c, self.facility_x, team=self.team)

    # -- fixtures -----------------------------------------------------------
    def _patient(self, name, province, facility):
        return self.env['res.partner'].create({
            'name': name, 'is_patient': True,
            'catchment_province_id': province.id,
            'primary_facility_id': facility.id,
            'mobile': '09%08d' % (uuid.uuid4().int % 10 ** 8),
            'allergies': 'Penicillin', 'medical_history': 'Confidential history'})

    def _order(self, patient, facility, team=None):
        vals = {
            'patient_id': patient.id, 'facility_id': facility.id,
            'scheduled_datetime': fields.Datetime.now() + timedelta(days=1),
            'scheduled_duration': 120, 'service_type': 'home_visit'}
        if team:
            vals['team_id'] = team.id
        return self.env['health.fieldservice.order'].create(vals)

    def _assign(self, order, staff):
        order.action_assign_staff_to_fso(staff.id, assignment_role='lead')

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

    def _push(self, changes):
        resp = self.url_open(
            '/health_pwa/sync/push',
            data=json.dumps({'jsonrpc': '2.0', 'method': 'call',
                             'params': {'changes': changes}}),
            headers={'Content-Type': 'application/json'}).json()
        return resp.get('result', resp)

    def _data_ids(self, resp, key):
        recs = resp['changes'][key]['records']
        return {r['id'] for r in recs if not r.get('is_deleted')}

    def _removal_ids(self, resp, key):
        recs = resp['changes'][key]['records']
        return {r['id'] for r in recs if r.get('is_deleted')}

    def _far_past(self):
        return _iso(fields.Datetime.now() - timedelta(days=365))


# =====================================================================
# 1 — since parsing
# =====================================================================
@tagged('post_install', '-at_install')
class TestSinceParsing(SyncScopeBase):

    def test_js_iso_since_parses(self):
        self.authenticate(self.nurse_user.login, 'syncnursepw')
        # JS-style millis + Z suffix, well before the fixtures -> A returned.
        past = _iso(fields.Datetime.now() - timedelta(days=2)).replace(' ', 'T') + '.000Z'
        resp = self._changes(since=past)
        self.assertTrue(resp['success'], resp)
        self.assertIn(self.order_a.id, self._data_ids(resp, 'field_service_orders'))

    def test_future_since_returns_nothing(self):
        self.authenticate(self.nurse_user.login, 'syncnursepw')
        future = _iso(fields.Datetime.now() + timedelta(days=5)).replace(' ', 'T') + 'Z'
        resp = self._changes(since=future)
        self.assertTrue(resp['success'], resp)
        self.assertEqual(resp['changes']['field_service_orders']['records'], [])

    def test_garbage_since_falls_back_no_500(self):
        self.authenticate(self.nurse_user.login, 'syncnursepw')
        resp = self._changes(since='not-a-date-@@@')
        # 30-day fallback, never a 500.
        self.assertTrue(resp['success'], resp)
        self.assertIn(self.order_a.id, self._data_ids(resp, 'field_service_orders'))


# =====================================================================
# 2 — minimal-nurse scope (the headline)
# =====================================================================
@tagged('post_install', '-at_install')
class TestMinimalNurseScope(SyncScopeBase):

    def test_nurse_sees_only_own_visit_and_patient(self):
        self.authenticate(self.nurse_user.login, 'syncnursepw')
        resp = self._changes(since=self._far_past())
        self.assertTrue(resp['success'], resp)

        order_data = self._data_ids(resp, 'field_service_orders')
        patient_data = self._data_ids(resp, 'patients')

        # Order A + patient A present as DATA records.
        self.assertIn(self.order_a.id, order_data)
        self.assertIn(self.patient_a.id, patient_data)

        # Order B never leaks as a data record; patient B fully absent.
        self.assertNotIn(self.order_b.id, order_data)
        self.assertNotIn(self.patient_b.id, patient_data)
        self.assertNotIn(self.patient_b.id, self._removal_ids(resp, 'patients'))

        # The minimal nurse (no sale/account ACL) still gets PHI via sudo.
        rec_a = next(r for r in resp['changes']['patients']['records']
                     if r['id'] == self.patient_a.id)
        self.assertEqual(rec_a['allergies'], 'Penicillin')
        self.assertEqual(rec_a['medical_history'], 'Confidential history')


# =====================================================================
# 3 — team grant
# =====================================================================
@tagged('post_install', '-at_install')
class TestTeamGrant(SyncScopeBase):

    def test_team_member_gets_team_order(self):
        self.authenticate(self.nurse_user.login, 'syncnursepw')
        resp = self._changes(since=self._far_past())
        # Order C has no assignment for the nurse, only a shared team -> in scope.
        self.assertIn(self.order_c.id, self._data_ids(resp, 'field_service_orders'))
        self.assertIn(self.patient_c.id, self._data_ids(resp, 'patients'))


# =====================================================================
# 4 — manager audience preserved
# =====================================================================
@tagged('post_install', '-at_install')
class TestManagerAudience(SyncScopeBase):

    def test_manager_sees_own_catchment_owner_sees_all(self):
        # Manager with catchment X.
        manager = new_test_user(
            self.env, login='sync_mgr_%s' % uuid.uuid4().hex[:6],
            groups='base.group_user,health_base.group_healthcare_operations_manager',
            password='syncmgrpw')
        manager.write({'catchment_province_id': self.province_x.id})
        order_y = self._order(self.patient_y, self.facility_y)

        self.authenticate(manager.login, 'syncmgrpw')
        resp = self._changes(since=self._far_past())
        mgr_orders = self._data_ids(resp, 'field_service_orders')
        self.assertIn(self.order_a.id, mgr_orders)      # province X
        self.assertNotIn(order_y.id, mgr_orders)         # province Y — out

        # Owner sees everything.
        owner = new_test_user(
            self.env, login='sync_owner_%s' % uuid.uuid4().hex[:6],
            groups='base.group_user,health_base.group_healthcare_owner',
            password='syncownerpw')
        self.authenticate(owner.login, 'syncownerpw')
        resp2 = self._changes(since=self._far_past())
        owner_orders = self._data_ids(resp2, 'field_service_orders')
        self.assertIn(self.order_a.id, owner_orders)
        self.assertIn(order_y.id, owner_orders)


# =====================================================================
# 5 — removals (de-scope / archive / hard delete)
# =====================================================================
@tagged('post_install', '-at_install')
class TestRemovals(SyncScopeBase):

    def test_descope_archive_and_tombstone_emit_removals(self):
        self.authenticate(self.nurse_user.login, 'syncnursepw')

        # (a) cancel the nurse's assignment on A -> A out of scope -> removal,
        # and A must carry NO data fields.
        self.order_a.assignment_ids.write({'state': 'cancelled'})
        resp = self._changes(since=self._far_past())
        self.assertIn(self.order_a.id, self._removal_ids(resp, 'field_service_orders'))
        self.assertNotIn(self.order_a.id, self._data_ids(resp, 'field_service_orders'))
        rec_a = next(r for r in resp['changes']['field_service_orders']['records']
                     if r['id'] == self.order_a.id)
        self.assertEqual(set(rec_a.keys()), {'id', 'is_deleted'})

        # (b) archive an in-scope order (C, team grant) -> removal.
        self.order_c.write({'active': False})
        resp = self._changes(since=self._far_past())
        self.assertIn(self.order_c.id, self._removal_ids(resp, 'field_service_orders'))

        # (c) hard-delete an assigned order -> tombstone -> removal.
        doomed = self._order(self.patient_a, self.facility_x)
        self._assign(doomed, self.nurse_staff)
        doomed_id = doomed.id
        doomed.unlink()
        self.assertTrue(self.env['health.pwa.sync.tombstone'].sudo().search_count(
            [('res_model', '=', 'health.fieldservice.order'), ('res_id', '=', doomed_id)]))
        resp = self._changes(since=self._far_past())
        self.assertIn(doomed_id, self._removal_ids(resp, 'field_service_orders'))

    def _backdate(self, order, days=2, assignments=True):
        """Push an order (and optionally its assignments) out of the delta
        window via raw SQL — write_date is ORM-managed and can't be written
        normally."""
        self.env.cr.execute(
            "UPDATE health_fieldservice_order"
            " SET write_date = write_date - interval '%s days',"
            "     create_date = create_date - interval '%s days'"
            " WHERE id = %s", (days, days, order.id))
        if assignments:
            self.env.cr.execute(
                "UPDATE health_staff_assignment"
                " SET write_date = write_date - interval '%s days',"
                "     create_date = create_date - interval '%s days'"
                " WHERE fso_id = %s", (days, days, order.id))
        self.env.invalidate_all()

    def test_descope_via_assignment_only_write_emits_removal(self):
        # Cancelling an assignment writes only the ASSIGNMENT row (no stored
        # compute on the order depends on assignment state), so the order's
        # write_date never enters the delta window. The assignment-window
        # candidate source must still produce the removal.
        self.authenticate(self.nurse_user.login, 'syncnursepw')
        self._backdate(self.order_a)
        since = _iso(fields.Datetime.now() - timedelta(hours=1))
        self.order_a.assignment_ids.write({'state': 'cancelled'})
        resp = self._changes(since=since)
        self.assertIn(self.order_a.id, self._removal_ids(resp, 'field_service_orders'))
        self.assertNotIn(self.order_a.id, self._data_ids(resp, 'field_service_orders'))

    def test_new_assignment_on_stale_order_appears(self):
        # Mirror image: assigning the nurse to an order whose ROW is outside
        # the delta window must still upsert the order (and its patient) into
        # the nurse's delta via the assignment-window candidates.
        self.authenticate(self.nurse_user.login, 'syncnursepw')
        since = _iso(fields.Datetime.now() - timedelta(hours=1))
        self._assign(self.order_b, self.nurse_staff)
        # Assigning may bump the ORDER row via stored computes — re-backdate
        # the row (keep the fresh assignment) so ONLY the assignment window
        # can put B in the candidate set. Strict proof of the fix.
        self._backdate(self.order_b, assignments=False)
        resp = self._changes(since=since)
        self.assertIn(self.order_b.id, self._data_ids(resp, 'field_service_orders'))
        self.assertIn(self.patient_b.id, self._data_ids(resp, 'patients'))


# =====================================================================
# 6 — push scope
# =====================================================================
@tagged('post_install', '-at_install')
class TestPushScope(SyncScopeBase):

    def test_push_requires_assignment_and_drops_stage(self):
        self.authenticate(self.nurse_user.login, 'syncnursepw')

        # Unassigned target: nurse is NOT assigned to order B -> refused.
        res = self._push({'field_service_orders': [
            {'id': self.order_b.id, 'patient_notes': 'hacked'}]})
        item = res['results'][0]
        self.assertFalse(item['success'], res)
        self.order_b.invalidate_recordset()
        self.assertNotEqual(self.order_b.patient_notes, 'hacked')

        # Assigned target: nurse pushes patient_notes + stage_id on A. Notes
        # written (sudo path); stage_id IGNORED (not written, not an error).
        stage_before = self.order_a.stage_id.id
        other_stage = self.env['health.fieldservice.stage'].search(
            [('id', '!=', stage_before)], limit=1)
        res2 = self._push({'field_service_orders': [
            {'id': self.order_a.id, 'patient_notes': 'visit ok',
             'stage_id': other_stage.id}]})
        item2 = res2['results'][0]
        self.assertTrue(item2['success'], res2)
        self.assertNotIn('stage_id', item2['updated_fields'])
        self.order_a.invalidate_recordset()
        self.assertEqual(self.order_a.patient_notes, 'visit ok')
        self.assertEqual(self.order_a.stage_id.id, stage_before)

    def test_push_patient_out_of_scope_refused(self):
        self.authenticate(self.nurse_user.login, 'syncnursepw')
        # Patient B is out of the nurse's order horizon -> refused.
        res = self._push({'patients': [
            {'id': self.patient_b.id, 'phone': '0999999999'}]})
        item = res['results'][0]
        self.assertFalse(item['success'], res)
        self.patient_b.invalidate_recordset()
        self.assertNotEqual(self.patient_b.phone, '0999999999')


# =====================================================================
# 7 — debug gate
# =====================================================================
@tagged('post_install', '-at_install')
class TestDebugGate(SyncScopeBase):

    def test_nurse_403_admin_200(self):
        self.authenticate(self.nurse_user.login, 'syncnursepw')
        r = self.url_open('/health_pwa/sync/debug')
        self.assertEqual(r.status_code, 403)

        self.authenticate(self.sys_user.login, 'syncsyspw')
        r2 = self.url_open('/health_pwa/sync/debug')
        self.assertEqual(r2.status_code, 200)
        self.assertTrue(r2.json()['success'])


# =====================================================================
# 8 — watermark
# =====================================================================
@tagged('post_install', '-at_install')
class TestWatermark(SyncScopeBase):

    def test_watermark_present_and_fresh(self):
        start = fields.Datetime.now()
        self.authenticate(self.nurse_user.login, 'syncnursepw')
        resp = self._changes(since=self._far_past())
        self.assertIn('watermark', resp)
        wm = datetime.fromisoformat(resp['watermark'])
        # Compare naive datetimes; allow a 5s clock-skew slack backwards.
        self.assertGreaterEqual(wm.replace(tzinfo=None), start - timedelta(seconds=5))
