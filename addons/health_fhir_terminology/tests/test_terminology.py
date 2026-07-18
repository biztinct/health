# -*- coding: utf-8 -*-
"""Tests for health_fhir_terminology (handover §7). Direct-call, no HTTP."""

import base64
from datetime import datetime

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged

from odoo.addons.health_fhir_core.capability import (
    build_capability, clear_capability_cache,
)
from odoo.addons.health_fhir_core.serializers import REGISTRY
from odoo.addons.health_fhir_core.serializers.base import validate_resource

ICD10_URI = 'http://hl7.org/fhir/sid/icd-10'


@tagged('post_install', '-at_install')
class TestTerminology(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.System = cls.env['medical.coding.system']
        cls.Code = cls.env['medical.code']
        cls.icd10 = cls.System.search([('code', '=', 'icd10')], limit=1)
        cls.loinc = cls.System.search([('code', '=', 'loinc')], limit=1)

    def _validate(self, resource_dict):
        try:
            return validate_resource(resource_dict)
        except ImportError:
            self.skipTest('fhir.resources is not installed in this environment')

    # ------------------------------------------------------------------
    # 1. Seeds
    # ------------------------------------------------------------------
    def test_seeds_present(self):
        codes = self.System.with_context(active_test=False).search([]).mapped(
            'code')
        for expected in ('icd10', 'loinc', 'ucum', 'rxnorm', 'snomed',
                         'health19-services'):
            self.assertIn(expected, codes)
        snomed = self.System.with_context(active_test=False).search(
            [('code', '=', 'snomed')])
        self.assertFalse(snomed.active, 'SNOMED must be seeded inactive')
        self.assertGreaterEqual(
            self.Code.search_count([('system_id', '=', self.loinc.id)]), 13)
        self.assertGreaterEqual(
            self.Code.search_count([('system_id', '=', self.icd10.id)]), 25)

    # ------------------------------------------------------------------
    # 2. Unique guard (pre-check, not IntegrityError)
    # ------------------------------------------------------------------
    def test_duplicate_code_raises_validation_error(self):
        with self.assertRaises(ValidationError):
            self.Code.create({
                'system_id': self.icd10.id, 'code': 'I10',
                'display': 'Duplicate hypertension'})

    def test_duplicate_system_uri_raises_validation_error(self):
        with self.assertRaises(ValidationError):
            self.System.create({
                'name': 'Dup ICD', 'uri': ICD10_URI, 'code': 'icd10_dup'})

    # ------------------------------------------------------------------
    # 3. name_search (Vietnamese-first typeahead)
    # ------------------------------------------------------------------
    def test_name_search_code_vi_and_synonym(self):
        # by code prefix
        by_code = self.Code.name_search(name='I10')
        self.assertIn('I10', [self.Code.browse(i).code for i, _ in by_code])
        # by a Vietnamese display fragment
        by_vi = self.Code.name_search(name='Tăng huyết áp')
        self.assertTrue(by_vi)
        self.assertIn('I10', [self.Code.browse(i).code for i, _ in by_vi])
        # by synonym
        by_syn = self.Code.name_search(name='bedsore')
        self.assertIn('L89', [self.Code.browse(i).code for i, _ in by_syn])
        # display_name is Vietnamese-first
        i10 = self.Code.get('icd10', 'I10')
        self.assertEqual(i10.display_name, '[I10] Tăng huyết áp vô căn (nguyên phát)')

    # ------------------------------------------------------------------
    # 4. Importer
    # ------------------------------------------------------------------
    def test_importer_upsert_parent_and_reimport(self):
        # child before parent; one malformed row (no display)
        csv_text = (
            'code,display,display_vi,parent_code,synonyms\n'
            'T99.1,Child code,Mã con,T99,\n'
            'T99,Parent code,Mã cha,,\n'
            'T88,Standalone,Đơn lẻ,,syn1;syn2\n'
            'T77,Another,Khác,,\n'
            'T66,,No display so skipped,,\n')
        wizard = self.env['medical.code.import'].create({
            'system_id': self.icd10.id,
            'file': base64.b64encode(csv_text.encode('utf-8')),
            'filename': 'codes.csv'})
        wizard.action_import()
        self.assertEqual(wizard.created_count, 4)
        self.assertEqual(wizard.updated_count, 0)
        self.assertEqual(wizard.skipped_count, 1)
        child = self.Code.get('icd10', 'T99.1')
        parent = self.Code.get('icd10', 'T99')
        self.assertEqual(child.parent_id, parent, 'parent resolved 2nd pass')

        # re-import with a changed display → update, no duplicate
        csv_text2 = (
            'code,display,display_vi,parent_code,synonyms\n'
            'T88,Standalone UPDATED,Đơn lẻ,,syn1;syn2\n')
        wizard2 = self.env['medical.code.import'].create({
            'system_id': self.icd10.id,
            'file': base64.b64encode(csv_text2.encode('utf-8')),
            'filename': 'codes2.csv'})
        wizard2.action_import()
        self.assertEqual(wizard2.created_count, 0)
        self.assertEqual(wizard2.updated_count, 1)
        self.assertEqual(
            self.Code.with_context(active_test=False).search_count([
                ('system_id', '=', self.icd10.id), ('code', '=', 'T88')]), 1)
        self.assertEqual(
            self.Code.get('icd10', 'T88').display, 'Standalone UPDATED')

    # ------------------------------------------------------------------
    # 5. Clinical-note sidecar
    # ------------------------------------------------------------------
    def test_clinical_note_condition_codes(self):
        province = self.env['health.catchment.province'].search([], limit=1)
        if not province:
            province = self.env['health.catchment.province'].create(
                {'name': 'Term Province'})
        facility = self.env['health.facility'].search(
            [('catchment_province_id', '=', province.id)], limit=1)
        if not facility:
            facility = self.env['health.facility'].create({
                'name': 'Term Facility', 'code': 'TERMF',
                'catchment_province_id': province.id})
        patient = self.env['res.partner'].create({
            'name': 'Terminology Patient', 'is_patient': True,
            'catchment_province_id': province.id})
        fso = self.env['health.fieldservice.order'].create({
            'patient_id': patient.id, 'facility_id': facility.id,
            'scheduled_datetime': datetime(2026, 7, 10, 2, 0, 0)})
        note = self.env['health.clinical.note'].create({
            'order_id': fso.id, 'diagnosis': 'Tăng huyết áp'})
        i10 = self.Code.get('icd10', 'I10')
        e11 = self.Code.get('icd10', 'E11')
        note.condition_code_ids = [(6, 0, (i10 | e11).ids)]
        self.assertEqual(note.condition_code_ids, i10 | e11)

    # ------------------------------------------------------------------
    # 6. CodeSystem serializer + capability
    # ------------------------------------------------------------------
    def test_codesystem_serializer_and_capability(self):
        self.assertIn('CodeSystem', REGISTRY)
        serializer = REGISTRY['CodeSystem']
        resource = serializer.to_fhir(self.icd10)
        self.assertEqual(resource['resourceType'], 'CodeSystem')
        self.assertEqual(resource['url'], ICD10_URI)
        self.assertEqual(resource['name'], 'icd10')
        self.assertEqual(resource['content'], 'fragment')
        self.assertGreaterEqual(resource['count'], 25)
        self._validate(resource)

        clear_capability_cache()
        statement = build_capability(self.env)
        listed = [r['type'] for r in statement['rest'][0]['resource']]
        self.assertIn('CodeSystem', listed)
        # >= (not ==): downstream modules register more resources into the
        # shared REGISTRY (health_condition adds Condition → 21). An exact
        # count is a brittle cross-module coupling.
        self.assertGreaterEqual(len(listed), 20)

    # ------------------------------------------------------------------
    # 7. $lookup / $expand helpers
    # ------------------------------------------------------------------
    def test_lookup_known_and_unknown(self):
        payload = self.Code.fhir_lookup(ICD10_URI, 'I10')
        self.assertEqual(payload['resourceType'], 'Parameters')
        params = {p['name']: p for p in payload['parameter']}
        self.assertEqual(params['display']['valueString'],
                         'Essential (primary) hypertension')
        designation = params['designation']['part']
        vi = {p['name']: p for p in designation}
        self.assertEqual(vi['language']['valueCode'], 'vi')
        self.assertEqual(vi['value']['valueString'],
                         'Tăng huyết áp vô căn (nguyên phát)')
        self._validate(payload)
        # unknown code / system → None
        self.assertIsNone(self.Code.fhir_lookup(ICD10_URI, 'NOPE99'))
        self.assertIsNone(self.Code.fhir_lookup('urn:bogus', 'I10'))

    def test_expand_with_vi_filter(self):
        payload = self.Code.fhir_expand(ICD10_URI, filter_text='Đái tháo', count=10)
        self.assertEqual(payload['resourceType'], 'ValueSet')
        codes = [c['code'] for c in payload['expansion']['contains']]
        self.assertIn('E11', codes)
        self._validate(payload)
        # count clamps to 50; unfiltered returns rows
        full = self.Code.fhir_expand(ICD10_URI, count=999)
        self.assertLessEqual(len(full['expansion']['contains']), 50)
        # unknown system → None
        self.assertIsNone(self.Code.fhir_expand('urn:bogus'))
