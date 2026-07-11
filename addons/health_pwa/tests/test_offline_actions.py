# -*- coding: utf-8 -*-
"""Tests for offline visit action replay (pwa-offline-actions phase).

HttpCase throughout — the idempotent replay only means anything through the
real /health_pwa/sync/push route with a real authenticated minimal-ACL nurse.

§5.32 / fact 11: this suite STARTS visits, so `action_start_service` fires
health_workflow_auto's E.4 timecard hook. `timecard_sync_enabled` is pinned OFF
in setUp via addCleanup (restoring the original) so no polluting hr.attendance
for `today` is created — otherwise TestTimecardSync's
cron_reconcile_timecards(for_date=today) breaks later in the same run.
"""
import json
import uuid
from datetime import timedelta

from odoo import fields
from odoo.tests import HttpCase, tagged, new_test_user


@tagged('post_install', '-at_install')
class OfflineActionsBase(HttpCase):

    def setUp(self):
        super().setUp()
        ICP = self.env['ir.config_parameter'].sudo()
        # §5.32 — pin the timecard hook OFF (restore the ORIGINAL value; unset
        # maps back to "absent").
        self.addCleanup(ICP.set_param, 'health_workflow_auto.timecard_sync_enabled',
                        ICP.get_param('health_workflow_auto.timecard_sync_enabled'))
        ICP.set_param('health_workflow_auto.timecard_sync_enabled', 'False')

        Province = self.env['health.catchment.province']
        Facility = self.env['health.facility']
        self.province = Province.create({
            'name': 'OA Prov %s' % uuid.uuid4().hex[:5],
            'code': 'OAP%s' % uuid.uuid4().hex[:3]})
        self.facility = Facility.create({
            'name': 'OA Facility', 'code': 'OAF%s' % uuid.uuid4().hex[:3],
            'street': '1 St', 'city': 'City',
            'catchment_province_id': self.province.id})

        # action_start_service needs an in_progress stage (falls back to any
        # state='in_progress' stage — see order model :2533).
        Stage = self.env['health.fieldservice.stage']
        for st in ('confirmed', 'assigned', 'in_progress', 'completed'):
            if not Stage.search([('state', '=', st), ('active', '=', True)], limit=1):
                Stage.create({'name': st.replace('_', ' ').title(), 'state': st})

        self.patient = self._patient('OA Patient')

        # Minimal nurse: nurse group only (NO sale/account ACL) + a password.
        self.nurse_user = new_test_user(
            self.env, login='oa_nurse_%s' % uuid.uuid4().hex[:6],
            groups='base.group_user,health_base.group_healthcare_nurse',
            password='oanursepw')
        self.nurse_user.write({'catchment_province_id': False})
        self.nurse_staff = self.env['hr.employee'].create(
            {'name': 'OA Nurse Emp', 'user_id': self.nurse_user.id})

        # An UNASSIGNED internal nurse — the scope attacker (test 4).
        self.other_user = new_test_user(
            self.env, login='oa_other_%s' % uuid.uuid4().hex[:6],
            groups='base.group_user,health_base.group_healthcare_nurse',
            password='oaotherpw')
        self.other_staff = self.env['hr.employee'].create(
            {'name': 'OA Other Emp', 'user_id': self.other_user.id})

        self.order = self._order(self.patient)
        self.order.action_assign_staff_to_fso(self.nurse_staff.id, assignment_role='lead')
        # Deterministic start state for the guard (assign only moves draft->assigned).
        self.order.sudo().write({'state': 'assigned'})

    # -- fixtures -----------------------------------------------------------
    def _patient(self, name):
        return self.env['res.partner'].create({
            'name': name, 'is_patient': True,
            'catchment_province_id': self.province.id,
            'primary_facility_id': self.facility.id,
            'mobile': '09%08d' % (uuid.uuid4().int % 10 ** 8)})

    def _order(self, patient):
        return self.env['health.fieldservice.order'].create({
            'patient_id': patient.id, 'facility_id': self.facility.id,
            'scheduled_datetime': fields.Datetime.now() + timedelta(hours=2),
            'scheduled_duration': 60, 'service_type': 'home_visit'})

    # -- helpers ------------------------------------------------------------
    def _push(self, changes):
        resp = self.url_open(
            '/health_pwa/sync/push',
            data=json.dumps({'jsonrpc': '2.0', 'method': 'call',
                             'params': {'changes': changes}}),
            headers={'Content-Type': 'application/json'}).json()
        return resp.get('result', resp)

    def _iso(self, dt):
        return dt.strftime('%Y-%m-%dT%H:%M:%S') + 'Z'

    def _start(self, fso_id, client_uuid, claimed_at, client_ref='ref-start'):
        return {'action_type': 'start_service', 'fso_id': fso_id,
                'client_action_uuid': client_uuid, 'client_ref': client_ref,
                'claimed_at': claimed_at, 'payload': {}}

    def _receipts(self, action_type, client_uuid):
        return self.env['health.pwa.action.receipt'].sudo().search([
            ('fso_id', '=', self.order.id),
            ('action_type', '=', action_type),
            ('client_action_uuid', '=', client_uuid)])


# =====================================================================
# 1 — replay start + claimed time honored
# =====================================================================
@tagged('post_install', '-at_install')
class TestStartReplay(OfflineActionsBase):

    def test_replay_start_honors_claimed_time(self):
        self.authenticate(self.nurse_user.login, 'oanursepw')
        claimed = fields.Datetime.now() - timedelta(minutes=10)
        u = uuid.uuid4().hex
        resp = self._push({'actions': [self._start(self.order.id, u, self._iso(claimed))]})
        self.assertTrue(resp['success'], resp)
        item = resp['results'][0]
        self.assertTrue(item['success'], item)
        self.assertEqual(item['state'], 'in_progress')
        self.assertNotIn('claimed_at_clamped', item)

        self.order.invalidate_recordset()
        self.assertEqual(self.order.state, 'in_progress')
        self.assertEqual(
            self.order.actual_start_datetime.replace(microsecond=0),
            claimed.replace(microsecond=0))

        receipt = self._receipts('start_service', u)
        self.assertEqual(len(receipt), 1)
        self.assertEqual(receipt.state, 'applied')


# =====================================================================
# 2 — idempotency
# =====================================================================
@tagged('post_install', '-at_install')
class TestIdempotency(OfflineActionsBase):

    def test_same_uuid_replays_once(self):
        self.authenticate(self.nurse_user.login, 'oanursepw')
        claimed = fields.Datetime.now() - timedelta(minutes=10)
        u = uuid.uuid4().hex
        first = self._push({'actions': [self._start(self.order.id, u, self._iso(claimed))]})
        self.order.invalidate_recordset()
        started_at = self.order.actual_start_datetime

        second = self._push({'actions': [self._start(self.order.id, u, self._iso(claimed))]})
        self.assertEqual(second['results'][0], first['results'][0])

        self.order.invalidate_recordset()
        self.assertEqual(self.order.actual_start_datetime, started_at)
        self.assertEqual(len(self._receipts('start_service', u)), 1)


# =====================================================================
# 3 — state conflict (rejected receipt sticks)
# =====================================================================
@tagged('post_install', '-at_install')
class TestStateConflict(OfflineActionsBase):

    def test_conflict_rejected_and_sticks(self):
        self.authenticate(self.nurse_user.login, 'oanursepw')
        # Move the order past the guard so a start conflicts.
        self.order.sudo().write({'state': 'in_progress'})
        u = uuid.uuid4().hex
        claimed = self._iso(fields.Datetime.now())
        resp = self._push({'actions': [self._start(self.order.id, u, claimed)]})
        item = resp['results'][0]
        self.assertFalse(item['success'], item)
        self.assertEqual(item['error'], 'state_conflict')

        self.order.invalidate_recordset()
        self.assertEqual(self.order.state, 'in_progress')
        receipt = self._receipts('start_service', u)
        self.assertEqual(len(receipt), 1)
        self.assertEqual(receipt.state, 'rejected')
        self.assertEqual(receipt.reject_reason, 'state_conflict')

        # Replaying the SAME rejected uuid returns the same rejection.
        again = self._push({'actions': [self._start(self.order.id, u, claimed)]})
        self.assertEqual(again['results'][0], item)
        self.assertEqual(len(self._receipts('start_service', u)), 1)


# =====================================================================
# 4 — scope: unassigned nurse denied, no receipt
# =====================================================================
@tagged('post_install', '-at_install')
class TestScope(OfflineActionsBase):

    def test_unassigned_denied_no_receipt(self):
        self.authenticate(self.other_user.login, 'oaotherpw')
        u = uuid.uuid4().hex
        resp = self._push({'actions': [
            self._start(self.order.id, u, self._iso(fields.Datetime.now()))]})
        item = resp['results'][0]
        self.assertFalse(item['success'], item)
        self.assertEqual(item['error'], 'Access denied')
        # No receipt row created for an unauthorized caller (uuid not squatted).
        self.assertEqual(len(self._receipts('start_service', u)), 0)
        self.order.invalidate_recordset()
        self.assertEqual(self.order.state, 'assigned')


# =====================================================================
# 5 — clamp (far-past + garbage → server time, receipt notes clamp)
# =====================================================================
@tagged('post_install', '-at_install')
class TestClamp(OfflineActionsBase):

    def _assert_clamped(self, claimed_at_raw):
        u = uuid.uuid4().hex
        before = fields.Datetime.now()
        resp = self._push({'actions': [self._start(self.order.id, u, claimed_at_raw)]})
        item = resp['results'][0]
        self.assertTrue(item['success'], item)
        self.assertTrue(item.get('claimed_at_clamped'), item)
        self.order.invalidate_recordset()
        # actual_start is the SERVER time (recent), not the stale/garbage claim.
        delta = abs((self.order.actual_start_datetime - before).total_seconds())
        self.assertLess(delta, 120)
        receipt = self._receipts('start_service', u)
        self.assertEqual(receipt.state, 'applied')
        self.assertIn('claimed_at_clamped', json.loads(receipt.result_json))

    def test_far_past_claim_clamped(self):
        self.authenticate(self.nurse_user.login, 'oanursepw')
        self._assert_clamped(self._iso(fields.Datetime.now() - timedelta(days=3)))

    def test_garbage_claim_clamped(self):
        self.authenticate(self.nurse_user.login, 'oanursepw')
        # Fresh order per test method (setUp), so reuse is safe.
        self._assert_clamped('not-a-real-date-@@@')


# =====================================================================
# 6 — clinical notes replay (whitelist; unknown key ignored)
# =====================================================================
@tagged('post_install', '-at_install')
class TestNotesReplay(OfflineActionsBase):

    def test_notes_create_whitelisted(self):
        self.authenticate(self.nurse_user.login, 'oanursepw')
        u = uuid.uuid4().hex
        action = {
            'action_type': 'save_clinical_notes', 'fso_id': self.order.id,
            'client_action_uuid': u, 'client_ref': 'ref-notes',
            'claimed_at': self._iso(fields.Datetime.now()),
            'payload': {
                'clinical_notes': 'BP stable, patient comfortable',
                'diagnosis': 'Routine check',
                'injection_count': 2,
                'bogus_field': 'should be ignored',
                'state': 'completed',  # not in the note whitelist — ignored
            }}
        resp = self._push({'actions': [action]})
        item = resp['results'][0]
        self.assertTrue(item['success'], item)
        note = self.env['health.clinical.note'].sudo().browse(item['note_id'])
        self.assertTrue(note.exists())
        self.assertEqual(note.order_id, self.order)
        self.assertEqual(note.injection_count, 2)
        self.assertEqual(note.diagnosis, 'Routine check')
        self.assertIn('BP stable', str(note.clinical_notes or ''))
        # Unknown keys never became fields / never errored — item succeeded and
        # the note has exactly one applied receipt.
        self.assertEqual(len(self._receipts('save_clinical_notes', u)), 1)


# =====================================================================
# 7 — client_ref echo across a mixed batch
# =====================================================================
@tagged('post_install', '-at_install')
class TestClientRefEcho(OfflineActionsBase):

    def test_mixed_batch_refs_map_each_item(self):
        self.authenticate(self.nurse_user.login, 'oanursepw')
        u = uuid.uuid4().hex
        changes = {
            'actions': [self._start(self.order.id, u,
                                    self._iso(fields.Datetime.now()), client_ref='a1')],
            'field_service_orders': [
                {'id': self.order.id, 'patient_notes': 'note via push',
                 'client_ref': 'f1'}],
            'patients': [
                {'id': self.patient.id, 'is_patient': True, 'phone': '0900000000',
                 'client_ref': 'p1'}],
        }
        resp = self._push(changes)
        self.assertTrue(resp['success'], resp)
        self.assertEqual(len(resp['results']), 3)
        self.assertTrue(all(r.get('client_ref') for r in resp['results']))
        byref = {r['client_ref']: r for r in resp['results']}
        self.assertEqual(byref['a1']['type'], 'action')
        self.assertEqual(byref['f1']['type'], 'field_service_order')
        self.assertEqual(byref['p1']['type'], 'patient')


# =====================================================================
# 8 — batch isolation (bad action does not block the good one)
# =====================================================================
@tagged('post_install', '-at_install')
class TestBatchIsolation(OfflineActionsBase):

    def test_bad_action_does_not_poison_batch(self):
        self.authenticate(self.nurse_user.login, 'oanursepw')
        # Force the start to conflict (order already in_progress); the notes
        # action has no state guard and must still apply.
        self.order.sudo().write({'state': 'in_progress'})
        bad = self._start(self.order.id, uuid.uuid4().hex,
                          self._iso(fields.Datetime.now()), client_ref='bad')
        notes_uuid = uuid.uuid4().hex
        good = {'action_type': 'save_clinical_notes', 'fso_id': self.order.id,
                'client_action_uuid': notes_uuid, 'client_ref': 'good',
                'claimed_at': self._iso(fields.Datetime.now()),
                'payload': {'clinical_notes': 'Applied despite the bad sibling'}}
        resp = self._push({'actions': [bad, good]})
        byref = {r['client_ref']: r for r in resp['results']}
        self.assertFalse(byref['bad']['success'])
        self.assertEqual(byref['bad']['error'], 'state_conflict')
        self.assertTrue(byref['good']['success'], byref['good'])
        self.assertTrue(
            self.env['health.clinical.note'].sudo().browse(
                byref['good']['note_id']).exists())
