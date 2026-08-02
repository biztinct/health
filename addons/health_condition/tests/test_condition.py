# -*- coding: utf-8 -*-
"""Condition-spine tests (handover §4).

Covers the additive sync (create/write/AI-approve/finalized/removal),
reactivation, backfill idempotency, the unique index, the FHIR Condition
serializer + $everything join, the facade search domains, and record rules.
"""

from datetime import datetime

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged

from odoo.addons.health_fhir_core.serializers import REGISTRY
from odoo.addons.health_fhir_core.serializers.base import validate_resource
from odoo.addons.health_fhir_core.serializers.everything import (
    build_everything_bundle,
)
from odoo.addons.health_condition.serializers.condition import (
    ICD10_SYSTEM, ConditionSerializer,
)


@tagged('post_install', '-at_install')
class TestCondition(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.Condition = env['health.condition']
        cls.Note = env['health.clinical.note']

        cls.province = env['health.catchment.province'].create(
            {'name': 'COND Prov A'})
        cls.province2 = env['health.catchment.province'].create(
            {'name': 'COND Prov B'})
        cls.facility = env['health.facility'].create({
            'name': 'COND Facility A', 'code': 'CONDFA',
            'street': '1 St', 'city': 'Hà Nội',
            'catchment_province_id': cls.province.id})
        cls.facility2 = env['health.facility'].create({
            'name': 'COND Facility B', 'code': 'CONDFB',
            'street': '2 St', 'city': 'Hà Nội',
            'catchment_province_id': cls.province2.id})
        cls.patient = env['res.partner'].create({
            'name': 'Nguyễn Văn Condition', 'is_patient': True,
            'catchment_province_id': cls.province.id,
            'primary_facility_id': cls.facility.id})
        cls.patient2 = env['res.partner'].create({
            'name': 'Trần Thị Other', 'is_patient': True,
            'catchment_province_id': cls.province2.id,
            'primary_facility_id': cls.facility2.id})
        cls.employee = env['hr.employee'].create({
            'name': 'Y Tá Condition',
            'healthcare_facility_id': cls.facility.id})

        cls.code_i10 = cls._ensure_icd10(
            env, 'I10', 'Essential hypertension', 'Tăng huyết áp vô căn')
        cls.code_e11 = cls._ensure_icd10(
            env, 'E11', 'Type 2 diabetes mellitus', 'Đái tháo đường típ 2')

    # -- helpers -----------------------------------------------------------
    @staticmethod
    def _ensure_icd10(env, code, display, display_vi=False):
        rec = env['medical.code'].get('icd10', code)
        if rec:
            if display_vi and not rec.display_vi:
                rec.display_vi = display_vi
            return rec
        system = env['medical.coding.system'].search(
            [('code', '=', 'icd10')], limit=1)
        if not system:
            system = env['medical.coding.system'].create({
                'name': 'ICD-10', 'code': 'icd10',
                'uri': 'http://hl7.org/fhir/sid/icd-10'})
        return env['medical.code'].create({
            'system_id': system.id, 'code': code, 'display': display,
            'display_vi': display_vi})

    def _make_fso(self, patient=None, facility=None):
        return self.env['health.fieldservice.order'].create({
            'patient_id': (patient or self.patient).id,
            'facility_id': (facility or self.facility).id,
            'scheduled_datetime': datetime(2026, 7, 10, 2, 0, 0),
            'scheduled_duration': 60})

    def _make_note(self, fso=None, codes=(), content='<p>Chăm sóc</p>'):
        fso = fso or self._make_fso()
        vals = {'order_id': fso.id, 'clinical_notes': content}
        if codes:
            vals['condition_code_ids'] = [(6, 0, [c.id for c in codes])]
        return self.Note.create(vals)

    def _make_user(self, group_xmlid, province=None):
        return self.env['res.users'].create({
            'name': 'COND ' + group_xmlid,
            'login': 'cond_%s_%d' % (
                group_xmlid.split('.')[-1], (province or self.province).id),
            'group_ids': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref(group_xmlid).id])],
            'catchment_province_id': (province or self.province).id})

    def _cond(self, patient, code):
        return self.Condition.with_context(active_test=False).search([
            ('patient_id', '=', patient.id), ('code_id', '=', code.id)])

    # ==================================================================
    # 1. sidecar write on a note creates the condition
    # ==================================================================
    def test_01_note_create_syncs_condition(self):
        note = self._make_note(codes=[self.code_i10])
        cond = self._cond(self.patient, self.code_i10)
        self.assertEqual(len(cond), 1)
        self.assertEqual(cond.patient_id, self.patient)
        self.assertEqual(cond.code_id, self.code_i10)
        self.assertEqual(cond.recorded_date, note.create_date.date())
        self.assertEqual(cond.recorder_id, note.author_id)
        self.assertIn(note, cond.note_ids)
        self.assertTrue(cond.active)
        self.assertEqual(cond.clinical_status, 'active')
        self.assertEqual(cond.verification_status, 'confirmed')

    # ==================================================================
    # 2. idempotency: a second note → one condition, two evidence notes
    # ==================================================================
    def test_02_second_note_advances_not_duplicates(self):
        note1 = self._make_note(codes=[self.code_i10])
        cond = self._cond(self.patient, self.code_i10)
        first_recorded = cond.recorded_date
        first_recorder = cond.recorder_id
        # backdate the condition's last_asserted so the second note advances it
        cond.last_asserted_date = fields.Date.to_date('2000-01-01')
        note2 = self._make_note(codes=[self.code_i10])
        cond2 = self._cond(self.patient, self.code_i10)
        self.assertEqual(cond, cond2)
        self.assertEqual(len(cond2), 1)
        self.assertEqual(len(cond2.note_ids), 2)
        self.assertIn(note1, cond2.note_ids)
        self.assertIn(note2, cond2.note_ids)
        # provenance frozen; last_asserted advanced
        self.assertEqual(cond2.recorded_date, first_recorded)
        self.assertEqual(cond2.recorder_id, first_recorder)
        self.assertEqual(cond2.last_asserted_date, note2.create_date.date())

    # ==================================================================
    # 3. full AI path: action_approve flows through the note-write hook
    # ==================================================================
    def test_03_ai_approve_creates_condition(self):
        note = self._make_note()  # no codes yet
        self.assertFalse(self._cond(self.patient, self.code_e11))
        sugg = self.env['health.ai.code.suggestion'].create({
            'note_id': note.id, 'code_id': self.code_e11.id,
            'confidence': 0.9, 'evidence': 'diabetes'})
        doctor = self._make_user('health_base.group_healthcare_doctor')
        sugg.with_user(doctor).action_approve()
        cond = self._cond(self.patient, self.code_e11)
        self.assertEqual(len(cond), 1)
        self.assertIn(note, cond.note_ids)

    # ==================================================================
    # 4. approve on a FINALIZED note still creates the condition
    # ==================================================================
    def test_04_approve_on_finalized_note(self):
        note = self._make_note(content='<p>Bệnh nhân đái tháo đường</p>')
        note.action_finalize()
        self.assertEqual(note.emr_state, 'final')
        sugg = self.env['health.ai.code.suggestion'].create({
            'note_id': note.id, 'code_id': self.code_e11.id,
            'confidence': 0.8, 'evidence': 'diabetes'})
        doctor = self._make_user('health_base.group_healthcare_doctor')
        sugg.with_user(doctor).action_approve()
        cond = self._cond(self.patient, self.code_e11)
        self.assertEqual(len(cond), 1)

    # ==================================================================
    # 5. additive-only: removing the code from the note leaves the condition
    # ==================================================================
    def test_05_removal_is_additive_only(self):
        note = self._make_note(codes=[self.code_i10])
        cond = self._cond(self.patient, self.code_i10)
        self.assertTrue(cond)
        note.write({'condition_code_ids': [(3, self.code_i10.id)]})
        self.assertFalse(note.condition_code_ids)
        cond2 = self._cond(self.patient, self.code_i10)
        self.assertEqual(cond, cond2)
        self.assertTrue(cond2.active)
        # evidence link is NOT torn down by the sync (additive-only)
        self.assertIn(note, cond2.note_ids)

    # ==================================================================
    # 6. reactivation: a fresh assertion re-opens a resolved/archived problem
    # ==================================================================
    def test_06_reactivation(self):
        self._make_note(codes=[self.code_i10])
        cond = self._cond(self.patient, self.code_i10)
        cond.write({'active': False, 'clinical_status': 'resolved'})
        self.assertFalse(cond.active)
        # a new note asserting the same code re-opens it
        self._make_note(codes=[self.code_i10])
        cond.invalidate_recordset()
        self.assertTrue(cond.active)
        self.assertEqual(cond.clinical_status, 'active')

    # ==================================================================
    # 7. backfill: pre-seed sidecar rows, run the hook → created; re-run → 0
    # ==================================================================
    def test_07_backfill_idempotent(self):
        # seed two coded notes WITHOUT going through the (already-installed)
        # hook is impossible — but the hook fn is what the backfill replays, so
        # assert the replay is a no-op on already-synced data.
        note = self._make_note(codes=[self.code_i10, self.code_e11])
        before = self.Condition.with_context(active_test=False).search_count([
            ('patient_id', '=', self.patient.id)])
        self.assertEqual(before, 2)
        # re-run the sync (what post_init replays) → creates nothing new
        note._sync_health_conditions()
        after = self.Condition.with_context(active_test=False).search_count([
            ('patient_id', '=', self.patient.id)])
        self.assertEqual(after, before)

    # ==================================================================
    # 8. unique index exists + duplicate create raises
    # ==================================================================
    def test_08_unique_index_and_duplicate(self):
        self.env.cr.execute("""
            SELECT 1 FROM pg_indexes
            WHERE indexname = 'health_condition_patient_code_uidx'
        """)
        self.assertTrue(self.env.cr.fetchone(), 'unique index missing')
        self.Condition.create({
            'patient_id': self.patient.id, 'code_id': self.code_i10.id})
        with self.assertRaises(ValidationError):
            self.Condition.create({
                'patient_id': self.patient.id, 'code_id': self.code_i10.id})

    # ==================================================================
    # 9. to_fhir validates against fhir.resources Condition (both statuses, vi)
    # ==================================================================
    def test_09_to_fhir_validates(self):
        note = self._make_note(codes=[self.code_i10])
        cond_active = self._cond(self.patient, self.code_i10)
        cond_resolved = self.Condition.create({
            'patient_id': self.patient.id, 'code_id': self.code_e11.id,
            'clinical_status': 'resolved'})
        serializer = ConditionSerializer()
        for cond in (cond_active, cond_resolved):
            resource = serializer.to_fhir(cond)
            self.assertEqual(resource['resourceType'], 'Condition')
            self.assertEqual(
                resource['clinicalStatus']['coding'][0]['code'],
                cond.clinical_status)
            try:
                validate_resource(resource)
            except ImportError:
                self.skipTest('fhir.resources not installed')
        # Vietnamese-first text (whatever the seeded/created code carries) +
        # evidence → DocumentReference
        active_res = serializer.to_fhir(cond_active)
        self.assertEqual(active_res['code']['text'],
                         self.code_i10.display_vi or self.code_i10.display)
        self.assertEqual(
            active_res['evidence'][0]['detail'][0]['reference'],
            'DocumentReference/%d' % note.id)

    # ==================================================================
    # 10. registry: Condition present + capability lists it
    # ==================================================================
    def test_10_registry_and_capability(self):
        self.assertIn('Condition', REGISTRY)
        self.assertIsInstance(REGISTRY['Condition'], ConditionSerializer)
        from odoo.addons.health_fhir_core.capability import build_capability
        cap = build_capability(self.env, 'http://test')
        types = {r['type'] for r in cap['rest'][0]['resource']}
        self.assertIn('Condition', types)

    # ==================================================================
    # 11. $everything on a coded patient includes the Condition entry
    # ==================================================================
    def test_11_everything_includes_condition(self):
        self._make_note(codes=[self.code_i10])
        bundle, _rec = build_everything_bundle(
            self.env, self.patient.id, {}, 'http://test', enforced=False)
        by_type = {}
        for entry in bundle['entry']:
            by_type.setdefault(
                entry['resource']['resourceType'], []).append(entry)
        self.assertIn('Condition', by_type)
        cond_res = by_type['Condition'][0]['resource']
        self.assertEqual(
            cond_res['subject']['reference'],
            'Patient/%d' % self.patient.id)

    # ==================================================================
    # 12. facade search domains (patient scope, code filter, archived excluded)
    # ==================================================================
    def test_12_search_domains(self):
        self._make_note(codes=[self.code_i10])
        self._make_note(fso=self._make_fso(patient=self.patient2,
                                           facility=self.facility2),
                        codes=[self.code_i10])
        serializer = ConditionSerializer()
        # patient param scopes to the right patient
        recs, _t, _c = serializer.search_records(
            self.env, {'patient': ['Patient/%d' % self.patient.id]})
        self.assertTrue(recs)
        self.assertEqual(recs.mapped('patient_id'), self.patient)
        # code=I10 filters
        recs_i10, _t, _c = serializer.search_records(
            self.env, {'code': ['I10']})
        self.assertTrue(all(r.code_id == self.code_i10 for r in recs_i10))
        # archived condition NOT in the facade search (working problem list)
        cond = self._cond(self.patient, self.code_i10)
        cond.active = False
        recs_after, _t, _c = serializer.search_records(
            self.env, {'patient': ['Patient/%d' % self.patient.id]})
        self.assertNotIn(cond, recs_after)

    # ==================================================================
    # 12b. GC-2 §3.1 — FHIR token syntax on `code` and `clinical-status`
    # ==================================================================
    def test_12b_token_system_code_search(self):
        """`code=http://hl7.org/fhir/sid/icd-10|I10` is what a conformant
        client sends. It used to match nothing (the raw string was compared
        to the code column); a code qualified with a FOREIGN system must now
        return zero rows — which is the spec's answer, not an error."""
        self._make_note(codes=[self.code_i10])
        cond = self._cond(self.patient, self.code_i10)
        serializer = ConditionSerializer()
        for value in ('I10', '%s|I10' % ICD10_SYSTEM, '|I10'):
            recs, _t, _c = serializer.search_records(
                self.env, {'code': [value]})
            self.assertIn(cond, recs, 'code=%r did not match' % value)
        # a different code system → zero matches, no exception
        translate = serializer.search_params['code']['domain']
        self.assertEqual(translate('http://snomed.info/sct|I10'),
                         [('id', '=', 0)])
        recs, _t, _c = serializer.search_records(
            self.env, {'code': ['http://snomed.info/sct|I10']})
        self.assertNotIn(cond, recs)
        # clinical-status asserts no system, so `|active` works too
        recs, _t, _c = serializer.search_records(
            self.env, {'clinical-status': ['|active'],
                       'patient': ['Patient/%d' % self.patient.id]})
        self.assertIn(cond, recs)

    # ==================================================================
    # 13. recorded-date search param — the Date-column-vs-datetime-literal
    # concern (§2.4): ge/eq prefixes must filter a fields.Date correctly
    # ==================================================================
    def test_13_recorded_date_search(self):
        self._make_note(codes=[self.code_i10])
        cond = self._cond(self.patient, self.code_i10)
        serializer = ConditionSerializer()
        recs, _t, _c = serializer.search_records(
            self.env,
            {'recorded-date': ['ge%s' % cond.recorded_date.isoformat()]})
        self.assertIn(cond, recs)
        recs_future, _t, _c = serializer.search_records(
            self.env, {'recorded-date': ['ge2099-01-01']})
        self.assertNotIn(cond, recs_future)
        # bare eq day form (expands to >= day AND < day+1)
        recs_eq, _t, _c = serializer.search_records(
            self.env,
            {'recorded-date': [cond.recorded_date.isoformat()]})
        self.assertIn(cond, recs_eq)

    # ==================================================================
    # 14. record rules: cross-catchment head-nurse sees nothing; owner all
    # ==================================================================
    def test_14_record_rules(self):
        self._make_note(codes=[self.code_i10])
        cond = self._cond(self.patient, self.code_i10)
        # a head nurse in the OTHER catchment sees nothing of province A
        hn_other = self._make_user(
            'health_base.group_healthcare_head_nurse', province=self.province2)
        visible = self.Condition.with_user(hn_other).search(
            [('id', '=', cond.id)])
        self.assertFalse(visible)
        # owner sees all
        owner = self._make_user('health_base.group_healthcare_owner',
                                province=self.province2)
        visible_owner = self.Condition.with_user(owner).search(
            [('id', '=', cond.id)])
        self.assertEqual(visible_owner, cond)
