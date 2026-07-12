# -*- coding: utf-8 -*-
"""PWA point-of-care finalize endpoint (emr-record-spine phase 1.5).

Verifies /health_pwa/api/fso/<id>/clinical_notes/<note>/finalize signs as the
authenticated nurse (attestation attribution) and enforces the author gate.
Skips when health_emr is not installed (health_pwa keeps no hard dep on it)."""
import json
import uuid

from odoo.tests import HttpCase, new_test_user, tagged
from odoo import fields
from datetime import timedelta


@tagged('post_install', '-at_install')
class TestEmrFinalizeEndpoint(HttpCase):

    def setUp(self):
        super().setUp()
        if 'emr_state' not in self.env['health.clinical.note']._fields:
            self.skipTest('health_emr not installed')

        Province = self.env['health.catchment.province']
        Facility = self.env['health.facility']
        self.province = Province.create({
            'name': 'FZ Prov %s' % uuid.uuid4().hex[:5],
            'code': 'FZ%s' % uuid.uuid4().hex[:3]})
        self.facility = Facility.create({
            'name': 'FZ Facility', 'code': 'FZF%s' % uuid.uuid4().hex[:3],
            'street': '1 St', 'city': 'City',
            'catchment_province_id': self.province.id})
        self.patient = self.env['res.partner'].create({
            'name': 'FZ Patient', 'is_patient': True,
            'catchment_province_id': self.province.id,
            'primary_facility_id': self.facility.id,
            'mobile': '09%08d' % (uuid.uuid4().int % 10 ** 8)})
        self.nurse = new_test_user(
            self.env, login='fz_nurse_%s' % uuid.uuid4().hex[:6],
            groups='base.group_user,health_base.group_healthcare_nurse',
            password='fznursepw')
        self.other = new_test_user(
            self.env, login='fz_other_%s' % uuid.uuid4().hex[:6],
            groups='base.group_user,health_base.group_healthcare_nurse',
            password='fzotherpw')
        self.order = self.env['health.fieldservice.order'].create({
            'patient_id': self.patient.id, 'facility_id': self.facility.id,
            'scheduled_datetime': fields.Datetime.now() + timedelta(hours=1),
            'scheduled_duration': 60, 'service_type': 'home_visit'})
        # Note authored BY the nurse (author gate is on the author). Created
        # sudo with an explicit author_id — the real system creates notes sudo
        # (the PHI-encryption inverse writes ciphertext, which a create-only
        # nurse cannot do directly).
        self.note = self.env['health.clinical.note'].sudo().create({
            'order_id': self.order.id,
            'author_id': self.nurse.id,
            'clinical_notes': '<p>BP 120/80, stable</p>'})

    def _finalize(self, order_id, note_id):
        return self.url_open(
            '/health_pwa/api/fso/%s/clinical_notes/%s/finalize' % (order_id, note_id),
            data='{}',
            headers={'Content-Type': 'application/json'}).json()

    def test_author_finalizes_and_signs(self):
        self.authenticate(self.nurse.login, 'fznursepw')
        resp = self._finalize(self.order.id, self.note.id)
        self.assertTrue(resp.get('success'), resp)
        self.assertEqual(resp['data']['emr_state'], 'final')
        self.note.invalidate_recordset()
        self.assertEqual(self.note.emr_state, 'final')
        # Signature attributed to the nurse, NOT the sudo/superuser.
        self.assertEqual(self.note.signed_by_id, self.nurse)
        self.assertTrue(self.note.content_hash)

    def test_idempotent_second_call(self):
        self.authenticate(self.nurse.login, 'fznursepw')
        first = self._finalize(self.order.id, self.note.id)
        self.note.invalidate_recordset()
        seal = self.note.content_hash
        second = self._finalize(self.order.id, self.note.id)
        self.assertTrue(second.get('success'), second)
        self.note.invalidate_recordset()
        self.assertEqual(self.note.content_hash, seal)  # unchanged

    def test_non_author_denied(self):
        self.authenticate(self.other.login, 'fzotherpw')
        resp = self._finalize(self.order.id, self.note.id)
        self.assertFalse(resp.get('success', False), resp)
        self.note.invalidate_recordset()
        self.assertEqual(self.note.emr_state, 'draft')

    def test_wrong_order_path_404(self):
        other_order = self.env['health.fieldservice.order'].create({
            'patient_id': self.patient.id, 'facility_id': self.facility.id,
            'scheduled_datetime': fields.Datetime.now(),
            'scheduled_duration': 60, 'service_type': 'home_visit'})
        self.authenticate(self.nurse.login, 'fznursepw')
        resp = self._finalize(other_order.id, self.note.id)
        self.assertFalse(resp.get('success', False), resp)
        self.note.invalidate_recordset()
        self.assertEqual(self.note.emr_state, 'draft')
