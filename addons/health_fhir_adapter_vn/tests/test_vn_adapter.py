# -*- coding: utf-8 -*-
"""Tests for the Vietnam EMR adapter (handover §6)."""

import json
from datetime import datetime

from odoo import fields
from odoo.tests import TransactionCase, tagged

from odoo.addons.health_fhir_core.serializers.base import validate_resource


@tagged('post_install', '-at_install')
class TestVnAdapter(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.adapter = env['fhir.adapter.vn']
        cls.province = env['health.catchment.province'].search([], limit=1)
        if not cls.province:
            cls.province = env['health.catchment.province'].create(
                {'name': 'VN Adapter Province'})
        cls.facility = env['health.facility'].create({
            'name': 'VN Adapter Facility', 'code': 'VNADP',
            'street': '1 Đường EMR', 'city': 'Hà Nội',
            'catchment_province_id': cls.province.id})
        cls.patient = env['res.partner'].create({
            'name': 'Phạm Văn EMR', 'is_patient': True,
            'catchment_province_id': cls.province.id,
            'primary_facility_id': cls.facility.id})
        cls.employee = env['hr.employee'].create({
            'name': 'VN Adapter Nurse',
            'healthcare_facility_id': cls.facility.id})
        cls.fso = env['health.fieldservice.order'].create({
            'patient_id': cls.patient.id, 'facility_id': cls.facility.id,
            'scheduled_datetime': datetime(2026, 7, 10, 2, 0, 0),
            'scheduled_duration': 60})
        cls.fso.write({'state': 'assigned'})

    # ------------------------------------------------------------------
    # 1. Bundle builder
    # ------------------------------------------------------------------
    def test_build_patient_bundle(self):
        self.env['health.observation'].create_coded(
            self.patient.id, '8867-4', 72, fso_id=self.fso.id)
        consent = self.env['health.consent'].create({
            'client_id': self.patient.id, 'consent_type': 'service',
            'method': 'verbal', 'effective_date': fields.Date.today()})
        consent.action_grant()
        note = self.env['health.clinical.note'].create({
            'order_id': self.fso.id, 'diagnosis': 'Tăng huyết áp, ĐTĐ'})
        i10 = self.env['medical.code'].get('icd10', 'I10')
        e11 = self.env['medical.code'].get('icd10', 'E11')
        note.condition_code_ids = [(6, 0, (i10 | e11).ids)]

        bundle = self.adapter.build_patient_bundle(self.patient)
        self.assertEqual(bundle['resourceType'], 'Bundle')
        self.assertEqual(bundle['type'], 'collection')
        types = [e['resource']['resourceType'] for e in bundle['entry']]
        for expected in ('Patient', 'Encounter', 'Observation', 'Consent',
                         'DocumentReference', 'Condition'):
            self.assertIn(expected, types)
        # exactly 2 Condition entries with the deterministic ids
        conditions = [e['resource'] for e in bundle['entry']
                      if e['resource']['resourceType'] == 'Condition']
        self.assertEqual(len(conditions), 2)
        cond_ids = {c['id'] for c in conditions}
        self.assertEqual(cond_ids, {
            'cond-%s-%s' % (note.id, i10.id),
            'cond-%s-%s' % (note.id, e11.id)})
        # each Condition carries the ICD-10 coding + encounter (assigned FSO)
        for cond in conditions:
            self.assertEqual(cond['code']['coding'][0]['system'],
                             'http://hl7.org/fhir/sid/icd-10')
            self.assertEqual(cond['encounter']['reference'],
                             'Encounter/%s' % self.fso.id)
        # fullUrl uses the urn scheme
        self.assertTrue(all(e['fullUrl'].startswith('urn:health19:')
                            for e in bundle['entry']))
        # every entry validates as FHIR R4
        try:
            for entry in bundle['entry']:
                validate_resource(entry['resource'])
        except ImportError:
            self.skipTest('fhir.resources not installed')
        # deterministic: build twice → same content hash
        bundle2 = self.adapter.build_patient_bundle(self.patient)
        self.assertEqual(self.adapter.bundle_sha256(bundle),
                         self.adapter.bundle_sha256(bundle2))

    # ------------------------------------------------------------------
    # 2. Profile validation
    # ------------------------------------------------------------------
    def test_validate_vn_profile(self):
        bundle = self.adapter.build_patient_bundle(self.patient)
        issues = self.adapter.validate_vn_profile(bundle, self.patient)
        codes = {i['code'] for i in issues}
        self.assertIn('patient-no-national-id', codes)
        self.assertIn('facility-no-moh-code', codes)
        # setting the MOH code clears that error
        self.facility.moh_facility_code = '01234'
        issues2 = self.adapter.validate_vn_profile(
            self.adapter.build_patient_bundle(self.patient), self.patient)
        self.assertNotIn('facility-no-moh-code',
                         {i['code'] for i in issues2})

    # ------------------------------------------------------------------
    # 3. Export action
    # ------------------------------------------------------------------
    def test_export_creates_log_and_attachment(self):
        self.env['health.observation'].create_coded(
            self.patient.id, '8867-4', 80, fso_id=self.fso.id)
        log = self.adapter.export_patient_bundle(self.patient)
        self.assertEqual(log.state, 'exported')
        self.assertTrue(log.bundle_sha256)
        self.assertGreater(log.entry_count, 0)
        self.assertTrue(log.issue_text)  # fixture has gaps → issues recorded
        self.assertTrue(log.attachment_id)
        parsed = json.loads(log.attachment_id.raw)
        self.assertEqual(self.adapter.bundle_sha256(parsed),
                         log.bundle_sha256)
        self.assertEqual(len(parsed['entry']), log.entry_count)

    # ------------------------------------------------------------------
    # 5. Readiness wizard (coding density)
    # ------------------------------------------------------------------
    def test_readiness_coding_density(self):
        coded_note = self.env['health.clinical.note'].create({
            'order_id': self.fso.id, 'diagnosis': 'coded'})
        coded_note.condition_code_ids = [
            (6, 0, self.env['medical.code'].get('icd10', 'I10').ids)]
        self.env['health.clinical.note'].create({
            'order_id': self.fso.id, 'diagnosis': 'uncoded'})
        wizard = self.env['vn.emr.readiness'].create(
            {'facility_id': self.facility.id})
        self.assertEqual(wizard.notes_total, 2)
        self.assertEqual(wizard.notes_coded, 1)
        self.assertEqual(wizard.coding_density, 50.0)
        self.assertIn('Circular 54', wizard.report_html)

    # ------------------------------------------------------------------
    # 6. VNeID mirror (create path)
    # ------------------------------------------------------------------
    def test_vneid_date_defaults_on_create(self):
        partner = self.env['res.partner'].create({
            'name': 'VNeID Person', 'is_patient': True,
            'catchment_province_id': self.province.id,
            'vneid_verified': True})
        self.assertEqual(partner.vneid_verified_date,
                         fields.Date.context_today(partner))
