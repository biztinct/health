# -*- coding: utf-8 -*-
"""Model-layer tests for the FHIR facade (§C.7 acceptance criteria).

HTTP controllers are thin wrappers; serialization and search-domain
translation are exercised directly through the serializer registry so the
suite runs without an HTTP client. Every serialized resource is validated by
constructing the corresponding ``fhir.resources`` (pydantic v2) class.
"""

import base64
from datetime import datetime

from odoo.tests import TransactionCase, tagged

from odoo.addons.health_fhir_core.capability import (
    build_capability, clear_capability_cache,
)
from odoo.addons.health_fhir_core.serializers import REGISTRY
from odoo.addons.health_fhir_core.serializers.base import (
    FHIRNotFound, FHIRNotSupported, validate_resource,
)


def _gender(env, code):
    """The `gender` vocabulary row for a code — gender is a lookup value, not
    a Selection, since it joined the client-editable dropdowns."""
    return env['health.lookup.value'].with_context(active_test=False).search(
        [('category_code', '=', 'gender'), ('code', '=', code)], limit=1)


EXPECTED_RESOURCES = (
    'Patient', 'Practitioner', 'Organization', 'Location',
    'Encounter', 'Appointment', 'ServiceRequest', 'DocumentReference',
)


@tagged('post_install', '-at_install')
class TestFHIRCore(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env

        # -- province (search first, create fallback) ---------------------
        cls.province = env['health.catchment.province'].search([], limit=1)
        if not cls.province:
            cls.province = env['health.catchment.province'].create({
                'name': 'FHIR Test Province',
            })

        # -- facility (search first, create fallback) ---------------------
        cls.facility = env['health.facility'].search(
            [('catchment_province_id', '=', cls.province.id)], limit=1)
        if not cls.facility:
            cls.facility = env['health.facility'].create({
                'name': 'FHIR Test Facility',
                'code': 'FHIRTST',
                'street': '1 Đường Thử Nghiệm',
                'city': 'Hà Nội',
                'catchment_province_id': cls.province.id,
            })

        # -- patient (catchment_province_id is required) -------------------
        cls.patient = env['res.partner'].create({
            'name': 'Nguyễn Văn Tèo FHIR',
            'is_patient': True,
            'catchment_province_id': cls.province.id,
            'mobile': '+84 912 345 678',
            'birth_date': '1954-02-19',
            'gender_id': _gender(env, 'male').id,
        })

        # -- practitioner ---------------------------------------------------
        cls.employee = env['hr.employee'].create({
            'name': 'Trần Thị Y Tá FHIR',
            'healthcare_facility_id': cls.facility.id,
        })

        # -- one FSO fixture (facility + patient + scheduled_datetime) -----
        cls.fso = env['health.fieldservice.order'].create({
            'patient_id': cls.patient.id,
            'facility_id': cls.facility.id,
            'scheduled_datetime': datetime(2026, 7, 10, 2, 0, 0),
            'scheduled_duration': 60,
        })
        cls.fso.write({'state': 'assigned'})
        cls.assignment = env['health.staff.assignment'].create({
            'fso_id': cls.fso.id,
            'staff_id': cls.employee.id,
            'assignment_role': 'lead',
        })

        # -- clinical note ----------------------------------------------------
        cls.note = env['health.clinical.note'].create({
            'order_id': cls.fso.id,
            'clinical_notes': '<p>Chăm sóc vết thương tại nhà</p>',
            'diagnosis': 'Loét tì đè độ II',
            'treatment_performed': 'Thay băng, rửa vết thương',
            'injection_count': 2,
        })

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _validate(self, resource_dict):
        """Construct-and-validate via fhir.resources; skip only if the lib is
        missing in the local environment (it is installed on the server)."""
        try:
            return validate_resource(resource_dict)
        except ImportError:
            self.skipTest('fhir.resources is not installed in this environment')

    # ------------------------------------------------------------------
    # CapabilityStatement
    # ------------------------------------------------------------------

    def test_capability_statement_lists_phase1_resources(self):
        clear_capability_cache()
        statement = build_capability(self.env)
        self.assertEqual(statement['resourceType'], 'CapabilityStatement')
        self.assertEqual(statement['fhirVersion'], '4.0.1')
        listed = [r['type'] for r in statement['rest'][0]['resource']]
        # Phase 2 adds resources to the registry — assert the 8 Phase-1
        # resources remain present (subset), not an exact count.
        self.assertTrue(set(EXPECTED_RESOURCES).issubset(set(listed)))
        phase1 = [r for r in statement['rest'][0]['resource']
                  if r['type'] in EXPECTED_RESOURCES]
        for resource in phase1:
            codes = [i['code'] for i in resource['interaction']]
            self.assertEqual(codes, ['read', 'search-type'])
            names = [p['name'] for p in resource['searchParam']]
            self.assertIn('_lastUpdated', names)
            # GC-1 / G12: `_count` is a paging control, not a SearchParameter,
            # and declaring it as one is a conformance nit. It is now absent
            # (test_fhir_conformance.test_18 asserts the removal repo-wide).
            self.assertNotIn('_count', names)
            # searchParam list mirrors the registry table
            serializer = REGISTRY[resource['type']]
            for name in serializer.search_params:
                self.assertIn(name, names)
        self._validate(statement)

    # ------------------------------------------------------------------
    # Patient
    # ------------------------------------------------------------------

    def test_patient_read_serializes_and_validates(self):
        serializer = REGISTRY['Patient']
        record = serializer.read_record(self.env, self.patient.id)
        self.assertEqual(record, self.patient)
        resource = serializer.serialize_batch(record)[0]
        self.assertEqual(resource['resourceType'], 'Patient')
        self.assertEqual(resource['id'], str(self.patient.id))
        # Vietnamese diacritics preserved
        self.assertEqual(resource['name'][0]['text'], 'Nguyễn Văn Tèo FHIR')
        self.assertEqual(resource['gender'], 'male')
        self.assertEqual(resource['birthDate'], '1954-02-19')
        systems = [i['system'] for i in resource['identifier']]
        self.assertIn('urn:health19:partner', systems)
        # meta.lastUpdated carries an explicit UTC offset
        self.assertTrue(resource['meta']['lastUpdated'].endswith('+00:00'))
        self._validate(resource)

    def test_patient_national_id_identifier_slot(self):
        self.patient.write({'national_id': '012345678901'})
        resource = REGISTRY['Patient'].to_fhir(self.patient)
        vneid = [i for i in resource['identifier']
                 if i['system'] == 'https://vneid.gov.vn/id']
        self.assertEqual(len(vneid), 1)
        self.assertEqual(vneid[0]['value'], '012345678901')
        self._validate(resource)

    def test_patient_search_by_identifier_and_name(self):
        serializer = REGISTRY['Patient']
        # identifier = odoo id (token)
        records, total, _ = serializer.search_records(
            self.env, {'identifier': [str(self.patient.id)]})
        self.assertIn(self.patient, records)
        # identifier = patient_code when the sequence assigned one
        if self.patient.patient_code:
            records, _, _ = serializer.search_records(
                self.env, {'identifier': [self.patient.patient_code]})
            self.assertIn(self.patient, records)
        # GC-2 §3.2: the `string` default is now spec-correct STARTS-WITH, so
        # a middle-of-name search must ask for `:contains` (it used to be the
        # implicit default — the change is the point of the phase).
        records, _, _ = serializer.search_records(
            self.env, {'name:contains': ['Văn Tèo FHIR']})
        self.assertIn(self.patient, records)
        # …and the prefix form still finds it.
        records, _, _ = serializer.search_records(
            self.env, {'name': ['Nguyễn Văn Tèo']})
        self.assertIn(self.patient, records)

    def test_unsupported_search_param_is_strict_400(self):
        serializer = REGISTRY['Patient']
        with self.assertRaises(FHIRNotSupported):
            serializer.build_domain(self.env, {'foo': ['1']})
        outcome = FHIRNotSupported('nope').to_operation_outcome()
        self.assertEqual(outcome['issue'][0]['code'], 'not-supported')
        self._validate(outcome)

    # ------------------------------------------------------------------
    # FSO → Encounter + Appointment + ServiceRequest
    # ------------------------------------------------------------------

    def test_fso_splits_into_three_linked_resources(self):
        fso_id = str(self.fso.id)

        encounter = REGISTRY['Encounter'].to_fhir(self.fso)
        appointment = REGISTRY['Appointment'].to_fhir(self.fso)
        service_request = REGISTRY['ServiceRequest'].to_fhir(self.fso)

        # status maps (state == assigned)
        self.assertEqual(encounter['status'], 'planned')
        self.assertEqual(appointment['status'], 'booked')
        self.assertEqual(service_request['status'], 'active')
        self.assertEqual(encounter['class']['code'], 'HH')
        self.assertEqual(service_request['intent'], 'order')

        # cross-references between the three resources
        self.assertEqual(encounter['appointment'][0]['reference'],
                         'Appointment/%s' % fso_id)
        self.assertEqual(service_request['encounter']['reference'],
                         'Encounter/%s' % fso_id)
        patient_ref = 'Patient/%s' % self.patient.id
        self.assertEqual(encounter['subject']['reference'], patient_ref)
        self.assertEqual(service_request['subject']['reference'], patient_ref)
        self.assertEqual(appointment['participant'][0]['actor']['reference'],
                         patient_ref)

        # practitioner participation from the staff assignment
        practitioner_ref = 'Practitioner/%s' % self.employee.id
        self.assertEqual(encounter['participant'][0]['individual']['reference'],
                         practitioner_ref)
        actor_refs = [p['actor']['reference'] for p in appointment['participant']]
        self.assertIn(practitioner_ref, actor_refs)

        # scheduled datetimes serialize as UTC with explicit offset
        self.assertEqual(appointment['start'], '2026-07-10T02:00:00+00:00')

        for resource in (encounter, appointment, service_request):
            self._validate(resource)

    def test_fso_in_progress_status_maps(self):
        self.fso.write({'state': 'in_progress'})
        self.assertEqual(REGISTRY['Encounter'].to_fhir(self.fso)['status'],
                         'in-progress')
        self.assertEqual(REGISTRY['Appointment'].to_fhir(self.fso)['status'],
                         'arrived')

    def test_encounter_base_domain_excludes_scheduling_states(self):
        serializer = REGISTRY['Encounter']
        self.assertTrue(serializer.read_record(self.env, self.fso.id))
        self.fso.write({'state': 'draft'})
        self.assertFalse(serializer.read_record(self.env, self.fso.id))
        # but the Appointment view still exists (draft → proposed)
        appointment = REGISTRY['Appointment']
        self.assertTrue(appointment.read_record(self.env, self.fso.id))
        self.assertEqual(appointment.to_fhir(self.fso)['status'], 'proposed')

    def test_encounter_search_by_patient_and_date(self):
        serializer = REGISTRY['Encounter']
        records, _, _ = serializer.search_records(self.env, {
            'patient': ['Patient/%s' % self.patient.id],
            'date': ['ge2026-07-01', 'le2026-07-31'],
        })
        self.assertIn(self.fso, records)
        records, _, _ = serializer.search_records(self.env, {
            'patient': [str(self.patient.id)],
            'date': ['ge2026-08-01'],
        })
        self.assertNotIn(self.fso, records)

    # ------------------------------------------------------------------
    # DocumentReference
    # ------------------------------------------------------------------

    def test_document_reference_compiles_note_text(self):
        serializer = REGISTRY['DocumentReference']
        resource = serializer.to_fhir(self.note)
        self.assertEqual(resource['status'], 'current')
        self.assertEqual(resource['subject']['reference'],
                         'Patient/%s' % self.patient.id)
        self.assertEqual(resource['context']['encounter'][0]['reference'],
                         'Encounter/%s' % self.fso.id)
        text = base64.b64decode(
            resource['content'][0]['attachment']['data']).decode('utf-8')
        self.assertIn('Chăm sóc vết thương tại nhà', text)
        self.assertIn('Loét tì đè độ II', text)
        self.assertIn('Thay băng, rửa vết thương', text)
        self.assertIn('Injections Given: 2', text)
        self.assertEqual(serializer.patient_ids_of(self.note),
                         [self.patient.id])
        self._validate(resource)

    # ------------------------------------------------------------------
    # Bundle pagination
    # ------------------------------------------------------------------

    def test_bundle_pagination_cursor(self):
        marker = 'FHIRPAGE'
        for index in range(5):
            self.env['res.partner'].create({
                'name': 'Bệnh nhân %s %s' % (marker, index),
                'is_patient': True,
                'catchment_province_id': self.province.id,
            })
        serializer = REGISTRY['Patient']
        # the marker sits mid-name → `:contains` (GC-2 §3.2 starts-with default)
        params = {'name:contains': [marker], '_count': ['2']}
        seen_ids = []
        pages = 0
        cursor = None
        while True:
            page_params = dict(params)
            if cursor is not None:
                page_params['_cursor'] = [str(cursor)]
            bundle, records = serializer.search_bundle(
                self.env, page_params, 'http://test')
            pages += 1
            self.assertEqual(bundle['resourceType'], 'Bundle')
            self.assertEqual(bundle['type'], 'searchset')
            self.assertEqual(bundle['total'], 5)
            self.assertLessEqual(len(bundle['entry']), 2)
            seen_ids += records.ids
            next_links = [l for l in bundle['link'] if l['relation'] == 'next']
            if pages == 1:
                # 5 > _count=2 → link[next] must be present on the first page
                self.assertTrue(next_links)
                self.assertIn('_cursor=', next_links[0]['url'])
            if not next_links:
                break
            cursor = records[-1].id
            self.assertLess(pages, 10, 'pagination did not terminate')
        # exhaustive, no gaps, no overlaps
        self.assertEqual(len(seen_ids), 5)
        self.assertEqual(len(set(seen_ids)), 5)
        self._validate(bundle)

    # ------------------------------------------------------------------
    # OperationOutcome on unknown id
    # ------------------------------------------------------------------

    def test_unknown_id_yields_not_found_outcome(self):
        serializer = REGISTRY['Patient']
        missing = serializer.read_record(self.env, 999999999)
        self.assertFalse(missing)
        outcome = FHIRNotFound('No Patient resource with id 999999999')
        self.assertEqual(outcome.status, 404)
        payload = outcome.to_operation_outcome()
        self.assertEqual(payload['resourceType'], 'OperationOutcome')
        self.assertEqual(payload['issue'][0]['code'], 'not-found')
        self._validate(payload)

    # ------------------------------------------------------------------
    # Practitioner / Organization / Location smoke + validation
    # ------------------------------------------------------------------

    def test_remaining_resources_serialize_and_validate(self):
        practitioner = REGISTRY['Practitioner'].to_fhir(self.employee)
        self.assertEqual(practitioner['name'][0]['text'], 'Trần Thị Y Tá FHIR')
        organization = REGISTRY['Organization'].to_fhir(self.facility)
        self.assertEqual(organization['name'], self.facility.name)
        location = REGISTRY['Location'].to_fhir(self.facility)
        self.assertEqual(location['managingOrganization']['reference'],
                         'Organization/%s' % self.facility.id)
        for resource in (practitioner, organization, location):
            self._validate(resource)

    def test_location_search_by_organization_reference(self):
        records, _, _ = REGISTRY['Location'].search_records(
            self.env, {'organization': ['Organization/%s' % self.facility.id]})
        self.assertIn(self.facility, records)
