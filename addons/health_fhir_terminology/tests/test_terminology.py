# -*- coding: utf-8 -*-
"""Tests for health_fhir_terminology (handover §7). Direct-call, no HTTP."""

import base64
import csv
import io
from datetime import datetime

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tools.misc import file_open

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


SAMPLE_FIXTURE = ('health_fhir_terminology/tests/fixtures/'
                  'icd10_sample_50.csv')


@tagged('post_install', '-at_install')
class TestIcd10SampleLoad(TransactionCase):
    """Phase GC-2 / D4 — the ICD-10 load path, verified on a committed
    licence-safe sample (register item G8, engineering half).

    The real WHO release cannot be committed (licensed) and cannot be
    downloaded in a test (no network), so what is proven here is the part we
    own: the converter's OUTPUT SHAPE goes through `medical.code.import`
    cleanly, hierarchy resolves when parents post-date their children, Vietnamese
    diacritics survive the round trip, a malformed row is counted rather than
    aborting the file — and a SECOND run of the same file changes nothing.
    Idempotence is what makes a 14k-row load safe to repeat after a partial
    failure, which is the operational risk in the runbook.

    Every expectation is DERIVED from the fixture (never a literal count), so
    editing the fixture cannot leave a stale assertion passing.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Code = cls.env['medical.code']
        cls.icd10 = cls.env['medical.coding.system'].search(
            [('code', '=', 'icd10')], limit=1)
        with file_open(SAMPLE_FIXTURE, 'rb') as handle:
            cls.sample_bytes = handle.read()
        rows = list(csv.reader(io.StringIO(
            cls.sample_bytes.decode('utf-8-sig'))))
        cls.header, cls.data_rows = rows[0], rows[1:]
        # a row is malformed for the importer when code or display is empty
        cls.malformed = [row for row in cls.data_rows
                         if not row[0].strip() or not row[1].strip()]
        cls.valid_rows = [row for row in cls.data_rows
                          if row not in cls.malformed]

    def _import(self):
        wizard = self.env['medical.code.import'].create({
            'system_id': self.icd10.id,
            'file': base64.b64encode(self.sample_bytes),
            'filename': 'icd10_sample_50.csv'})
        wizard.action_import()
        return wizard

    def test_70_fixture_is_the_shape_the_converter_emits(self):
        self.assertEqual(self.header,
                         ['code', 'display', 'display_vi', 'parent_code',
                          'synonyms'])
        self.assertEqual(len(self.data_rows), 50)
        self.assertEqual(len(self.malformed), 1,
                         'the fixture must carry exactly one malformed row')
        codes = [row[0] for row in self.data_rows]
        self.assertEqual(len(set(codes)), len(codes), 'duplicate code')
        # parents post-date their children — the 2-pass resolution is the
        # thing under test, and a parents-first file would not exercise it
        position = {code: index for index, code in enumerate(codes)}
        for row in self.valid_rows:
            if row[3]:
                self.assertIn(row[3], position,
                              'unknown parent_code %r' % row[3])
                self.assertGreater(position[row[3]], position[row[0]],
                                   'parent %r precedes its child %r'
                                   % (row[3], row[0]))
        self.assertTrue(any(any(ord(ch) > 127 for ch in row[2])
                            for row in self.valid_rows),
                        'no Vietnamese diacritics in the fixture')

    def test_71_first_pass_creates_and_counts_the_malformed_row(self):
        wizard = self._import()
        self.assertEqual(wizard.created_count, len(self.valid_rows))
        self.assertEqual(wizard.updated_count, 0)
        self.assertEqual(wizard.skipped_count, len(self.malformed))
        self.assertTrue(wizard.error_text,
                        'the malformed row was not reported')
        # hierarchy resolved across the file (child row before its parent row)
        child = next(row for row in self.valid_rows if row[3])
        record = self.Code.get('icd10', child[0])
        self.assertTrue(record)
        self.assertEqual(record.parent_id.code, child[3])
        # diacritics survived the base64 → utf-8-sig → ORM round trip
        vietnamese = next(row for row in self.valid_rows
                          if any(ord(ch) > 127 for ch in row[2]))
        self.assertEqual(
            self.Code.get('icd10', vietnamese[0]).display_vi, vietnamese[2])

    def test_72_second_pass_is_a_no_op(self):
        """Idempotence: re-running the SAME file creates nothing and updates
        nothing. This is what lets ops re-run a 14k-row load after a partial
        failure without deduplicating by hand."""
        self._import()
        before = self.Code.with_context(active_test=False).search_count(
            [('system_id', '=', self.icd10.id)])
        second = self._import()
        self.assertEqual(second.created_count, 0)
        self.assertEqual(second.updated_count, 0)
        self.assertEqual(second.skipped_count, len(self.malformed))
        after = self.Code.with_context(active_test=False).search_count(
            [('system_id', '=', self.icd10.id)])
        self.assertEqual(after, before, 'the re-import duplicated rows')

    def test_73_changed_display_updates_in_place(self):
        """The other half of idempotence: a corrected translation must reach
        the existing row, not create a second one."""
        self._import()
        target = self.valid_rows[0]
        edited = [self.header] + [
            [target[0], target[1], 'ĐÃ SỬA — bản dịch mới', target[3],
             target[4]]]
        buffer = io.StringIO()
        csv.writer(buffer, lineterminator='\n').writerows(edited)
        wizard = self.env['medical.code.import'].create({
            'system_id': self.icd10.id,
            'file': base64.b64encode(buffer.getvalue().encode('utf-8')),
            'filename': 'fix.csv'})
        wizard.action_import()
        self.assertEqual(wizard.created_count, 0)
        self.assertEqual(wizard.updated_count, 1)
        self.assertEqual(self.Code.get('icd10', target[0]).display_vi,
                         'ĐÃ SỬA — bản dịch mới')
