# -*- coding: utf-8 -*-
"""PWA "Notes to sign" reminder endpoint (emr-record-spine phase 1.7).

Verifies GET /health_pwa/api/clinical_notes/unsigned lists the authenticated
nurse's OWN unsigned (draft) clinical notes for the home-screen sign reminder.
Read-only nudge, author-scoped, ONLINE-only. Skips when health_emr is not
installed (health_pwa keeps no hard dep on it)."""
import uuid
from datetime import timedelta

from odoo.tests import HttpCase, new_test_user, tagged
from odoo import fields


@tagged('post_install', '-at_install')
class TestPwaSignReminder(HttpCase):

    def setUp(self):
        super().setUp()
        if 'emr_state' not in self.env['health.clinical.note']._fields:
            self.skipTest('health_emr not installed')

        Province = self.env['health.catchment.province']
        Facility = self.env['health.facility']
        self.province = Province.create({
            'name': 'SR Prov %s' % uuid.uuid4().hex[:5],
            'code': 'SR%s' % uuid.uuid4().hex[:3]})
        self.facility = Facility.create({
            'name': 'SR Facility', 'code': 'SRF%s' % uuid.uuid4().hex[:3],
            'street': '1 St', 'city': 'City',
            'catchment_province_id': self.province.id})
        self.patient = self.env['res.partner'].create({
            'name': 'SR Patient', 'is_patient': True,
            'catchment_province_id': self.province.id,
            'primary_facility_id': self.facility.id,
            'mobile': '09%08d' % (uuid.uuid4().int % 10 ** 8)})
        self.nurse = new_test_user(
            self.env, login='sr_nurse_%s' % uuid.uuid4().hex[:6],
            groups='base.group_user,health_base.group_healthcare_nurse',
            password='srnursepw')
        self.other = new_test_user(
            self.env, login='sr_other_%s' % uuid.uuid4().hex[:6],
            groups='base.group_user,health_base.group_healthcare_nurse',
            password='srotherpw')
        # Deterministic overdue threshold (Phase-1.6 config).
        self.env['ir.config_parameter'].sudo().set_param(
            'health_emr.reminder_hours', '24')

    def _order(self):
        return self.env['health.fieldservice.order'].create({
            'patient_id': self.patient.id, 'facility_id': self.facility.id,
            'scheduled_datetime': fields.Datetime.now() + timedelta(hours=1),
            'scheduled_duration': 60, 'service_type': 'home_visit'})

    def _note(self, author, order=None, body='<p>BP 120/80, stable</p>'):
        # Notes are created SUDO with an explicit author_id — the real system
        # creates them sudo (the PHI-encryption inverse writes ciphertext a
        # create-only nurse cannot do directly).
        return self.env['health.clinical.note'].sudo().create({
            'order_id': (order or self._order()).id,
            'author_id': author.id,
            'clinical_notes': body})

    def _backdate(self, note, hours):
        """Backdate a note's ORM-managed write_date via raw SQL (§5.9)."""
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE health_clinical_note SET write_date = %s WHERE id = %s",
            (fields.Datetime.now() - timedelta(hours=hours), note.id))
        self.env.invalidate_all()

    def _fetch(self):
        return self.url_open(
            '/health_pwa/api/clinical_notes/unsigned',
            headers={'Content-Type': 'application/json'}).json()

    # 1 — author sees her OWN draft, correct shape
    def test_01_lists_own_draft(self):
        note = self._note(self.nurse)
        self.authenticate(self.nurse.login, 'srnursepw')
        resp = self._fetch()
        self.assertTrue(resp.get('success'), resp)
        data = resp['data']
        self.assertEqual(data['count'], 1)
        row = data['notes'][0]
        self.assertEqual(row['note_id'], note.id)
        self.assertEqual(row['order_id'], note.order_id.id)
        self.assertEqual(row['patient_name'], self.patient.name)
        self.assertIn('age_hours', row)
        self.assertIn('overdue', row)
        # No PHI body leaks into the list.
        self.assertNotIn('clinical_notes', row)

    # 2 — a FINALIZED note of hers is EXCLUDED (drafts only)
    def test_02_finalized_excluded(self):
        note = self._note(self.nurse)
        note.with_user(self.nurse).action_finalize()
        note.invalidate_recordset()
        self.assertEqual(note.emr_state, 'final')
        self.authenticate(self.nurse.login, 'srnursepw')
        resp = self._fetch()
        self.assertTrue(resp.get('success'), resp)
        self.assertEqual(resp['data']['count'], 0)

    # 3 — another author's draft is EXCLUDED (author-scoping)
    def test_03_other_author_excluded(self):
        mine = self._note(self.nurse)
        self._note(self.other)  # not mine
        self.authenticate(self.nurse.login, 'srnursepw')
        resp = self._fetch()
        self.assertTrue(resp.get('success'), resp)
        ids = [n['note_id'] for n in resp['data']['notes']]
        self.assertEqual(ids, [mine.id])

    # 4 — overdue flag by write_date age; fresh & overdue both listed
    def test_04_overdue_flag(self):
        fresh = self._note(self.nurse)
        old = self._note(self.nurse)
        self._backdate(old, 48)  # > 24h reminder → overdue
        self.authenticate(self.nurse.login, 'srnursepw')
        resp = self._fetch()
        self.assertTrue(resp.get('success'), resp)
        by_id = {n['note_id']: n for n in resp['data']['notes']}
        self.assertEqual(resp['data']['count'], 2)
        self.assertTrue(by_id[old.id]['overdue'])
        self.assertFalse(by_id[fresh.id]['overdue'])
        self.assertEqual(resp['data']['overdue_count'], 1)

    # 5 — ordering: overdue-first, then oldest write_date first
    def test_05_ordering(self):
        fresh = self._note(self.nurse)
        old_a = self._note(self.nurse)
        old_b = self._note(self.nurse)
        self._backdate(old_a, 30)   # overdue, newer of the two overdue
        self._backdate(old_b, 72)   # overdue, oldest → should top
        self.authenticate(self.nurse.login, 'srnursepw')
        resp = self._fetch()
        self.assertTrue(resp.get('success'), resp)
        order = [n['note_id'] for n in resp['data']['notes']]
        # Overdue-first (oldest write_date first among overdue), fresh last.
        self.assertEqual(order, [old_b.id, old_a.id, fresh.id])

    # 6 — empty: a nurse with no drafts → {'notes': [], 'count': 0} (200)
    def test_06_empty(self):
        self.authenticate(self.nurse.login, 'srnursepw')
        resp = self._fetch()
        self.assertTrue(resp.get('success'), resp)
        self.assertEqual(resp['data']['count'], 0)
        self.assertEqual(resp['data']['notes'], [])
        self.assertEqual(resp['data']['overdue_count'], 0)

    # 7 — endpoint requires auth (auth='user' → not publicly reachable)
    def test_07_requires_auth(self):
        self._note(self.nurse)
        resp = self.url_open(
            '/health_pwa/api/clinical_notes/unsigned', allow_redirects=False)
        # Unauthenticated: auth='user' redirects to login (302/303) or an
        # explicit deny — never a 200 payload exposing notes.
        self.assertIn(resp.status_code, (302, 303, 401, 403))
        self.assertNotEqual(resp.status_code, 200)
