# -*- coding: utf-8 -*-
"""Patient/$everything — whole-record clinical export (compartment pull).

The operation composes the existing serializers into ONE consent-gated
searchset Bundle. These tests exercise the gather/bundle logic at the model
layer (``build_everything_bundle``) — the controller is a thin auth+audit
wrapper — plus the CapabilityStatement and compartment-coverage invariants.
"""

from datetime import datetime, timedelta

from odoo import fields
from odoo.tests import TransactionCase, new_test_user, tagged

from odoo.addons.health_fhir_core.capability import (
    build_capability, clear_capability_cache,
)
from odoo.addons.health_fhir_core.serializers import REGISTRY
from odoo.addons.health_fhir_core.serializers.base import (
    FHIRNotFound, validate_resource,
)
from odoo.addons.health_fhir_core.serializers.everything import (
    build_everything_bundle, patient_compartment,
)

# Registry resources that are NOT in a patient compartment. Patient is the
# compartment ROOT (added explicitly, has no patient/subject search param);
# the rest are non-PHI reference/terminology resources (patient_ids_of == []).
# A FUTURE serializer added WITHOUT a patient/subject param trips test_03 —
# add it here ONLY after confirming it carries no patient PHI (this is the
# intended guard: a silent conscious classification, per handover §4.3).
# 'CodeSystem' is injected into REGISTRY by health_fhir_terminology.
NON_COMPARTMENT_RESOURCES = {
    'Patient', 'Practitioner', 'Organization', 'Location', 'Questionnaire',
    'CodeSystem',
}


@tagged('post_install', '-at_install')
class TestFhirEverything(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env

        # -- two provinces (isolation) ------------------------------------
        cls.province = env['health.catchment.province'].create(
            {'name': 'EV Prov A'})
        cls.province2 = env['health.catchment.province'].create(
            {'name': 'EV Prov B'})
        cls.facility = env['health.facility'].create({
            'name': 'EV Facility A', 'code': 'EVFA',
            'street': '1 St', 'city': 'Hà Nội',
            'catchment_province_id': cls.province.id})
        cls.facility2 = env['health.facility'].create({
            'name': 'EV Facility B', 'code': 'EVFB',
            'street': '2 St', 'city': 'Hà Nội',
            'catchment_province_id': cls.province2.id})

        # -- primary patient with a clinical spread -----------------------
        cls.patient = env['res.partner'].create({
            'name': 'Nguyễn Văn Everything', 'is_patient': True,
            'catchment_province_id': cls.province.id,
            'primary_facility_id': cls.facility.id,
            'birth_date': '1950-01-01', 'gender': 'male'})
        # a SECOND patient in the other catchment (must never leak in)
        cls.other_patient = env['res.partner'].create({
            'name': 'Trần Thị Other', 'is_patient': True,
            'catchment_province_id': cls.province2.id,
            'primary_facility_id': cls.facility2.id})

        cls.employee = env['hr.employee'].create({
            'name': 'Y Tá Everything',
            'healthcare_facility_id': cls.facility.id})

        # FSO → Encounter / Appointment / ServiceRequest
        cls.fso = env['health.fieldservice.order'].create({
            'patient_id': cls.patient.id, 'facility_id': cls.facility.id,
            'scheduled_datetime': datetime(2026, 7, 10, 2, 0, 0),
            'scheduled_duration': 60})
        cls.fso.write({'state': 'assigned'})
        env['health.staff.assignment'].create({
            'fso_id': cls.fso.id, 'staff_id': cls.employee.id,
            'assignment_role': 'lead'})

        # two observations
        cls.obs1 = env['health.observation'].create_coded(
            cls.patient.id, '8867-4', 72, fso_id=cls.fso.id)
        cls.obs2 = env['health.observation'].create_coded(
            cls.patient.id, '8310-5', 37, fso_id=cls.fso.id)

        # a clinical note → DocumentReference
        cls.note = env['health.clinical.note'].create({
            'order_id': cls.fso.id,
            'clinical_notes': '<p>Chăm sóc vết thương</p>',
            'diagnosis': 'Loét tì đè độ II'})

        # a careplan
        cls.plan = env['health.careplan'].create({
            'client_id': cls.patient.id, 'category': 'chronic',
            'title': 'BP control', 'period_start': fields.Date.today()})

        # a resource that belongs to the OTHER patient (isolation probe)
        cls.other_fso = env['health.fieldservice.order'].create({
            'patient_id': cls.other_patient.id, 'facility_id': cls.facility2.id,
            'scheduled_datetime': datetime(2026, 7, 11, 2, 0, 0),
            'scheduled_duration': 60})
        cls.other_fso.write({'state': 'assigned'})
        env['health.observation'].create_coded(
            cls.other_patient.id, '8867-4', 99, fso_id=cls.other_fso.id)

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _validate(self, resource_dict):
        try:
            return validate_resource(resource_dict)
        except ImportError:
            self.skipTest('fhir.resources is not installed in this environment')

    @staticmethod
    def _by_type(bundle):
        out = {}
        for entry in bundle['entry']:
            rtype = entry['resource']['resourceType']
            out.setdefault(rtype, []).append(entry)
        return out

    # ------------------------------------------------------------------
    # 1. shape: Patient first, compartment present, total matches, validates
    # ------------------------------------------------------------------
    def test_01_bundle_shape_and_validates(self):
        bundle, patient_rec = build_everything_bundle(
            self.env, self.patient.id, {}, 'http://test', enforced=False)
        self.assertEqual(patient_rec, self.patient)
        self.assertEqual(bundle['resourceType'], 'Bundle')
        self.assertEqual(bundle['type'], 'searchset')
        # Patient resource is FIRST and is a search.mode 'match'
        first = bundle['entry'][0]
        self.assertEqual(first['resource']['resourceType'], 'Patient')
        self.assertEqual(first['resource']['id'], str(self.patient.id))
        self.assertEqual(first['search']['mode'], 'match')
        by_type = self._by_type(bundle)
        for rtype in ('Encounter', 'Observation', 'DocumentReference',
                      'CarePlan'):
            self.assertIn(rtype, by_type, '%s missing from $everything' % rtype)
        self.assertEqual(len(by_type['Observation']), 2)
        # total counts real matches; no OperationOutcome (no truncation)
        self.assertEqual(bundle['total'], len(bundle['entry']))
        self.assertNotIn('OperationOutcome', by_type)
        for entry in bundle['entry']:
            self.assertEqual(entry['search']['mode'],
                             'match' if entry is first else 'include')
            self._validate(entry['resource'])
        self._validate(bundle)

    # ------------------------------------------------------------------
    # 2. compartment correctness: ONLY this patient's records
    # ------------------------------------------------------------------
    def test_02_isolation_other_patient_absent(self):
        bundle, _ = build_everything_bundle(
            self.env, self.patient.id, {}, 'http://test', enforced=False)
        for entry in bundle['entry']:
            res = entry['resource']
            if res['resourceType'] == 'OperationOutcome':
                continue
            # no reference to the other patient anywhere
            subject = (res.get('subject') or {}).get('reference', '')
            self.assertNotIn('Patient/%s' % self.other_patient.id, subject)
        # the other patient's FSO id must not appear as an Encounter
        by_type = self._by_type(bundle)
        enc_ids = {e['resource']['id'] for e in by_type.get('Encounter', [])}
        self.assertNotIn(str(self.other_fso.id), enc_ids)

    # ------------------------------------------------------------------
    # 3. compartment coverage invariant (guards a future PHI serializer)
    # ------------------------------------------------------------------
    def test_03_compartment_coverage(self):
        # Every serializer with a patient/subject param is in the compartment;
        # every one WITHOUT is a known non-compartment (root or non-PHI).
        compartment_types = {s.resource_type
                             for s, _dom in patient_compartment(
                                 self.env, self.patient.id)}
        for rtype, serializer in REGISTRY.items():
            has_param = bool(serializer.search_params.get('patient')
                             or serializer.search_params.get('subject'))
            if rtype in NON_COMPARTMENT_RESOURCES:
                self.assertFalse(
                    has_param and rtype != 'Patient',
                    '%s is flagged non-compartment but has a patient param'
                    % rtype)
                self.assertNotIn(rtype, compartment_types)
            else:
                # a PHI compartment resource MUST expose the param, else its
                # PHI would silently miss $everything
                self.assertTrue(
                    has_param,
                    '%s has no patient/subject search param — its PHI would '
                    'be silently missing from $everything' % rtype)
                self.assertIn(rtype, compartment_types)

    # ------------------------------------------------------------------
    # 4. non-PHI excluded
    # ------------------------------------------------------------------
    def test_04_non_phi_excluded(self):
        bundle, _ = build_everything_bundle(
            self.env, self.patient.id, {}, 'http://test', enforced=False)
        present = set(self._by_type(bundle))
        for rtype in ('Organization', 'Practitioner', 'Location',
                      'Questionnaire'):
            self.assertNotIn(rtype, present)

    # ------------------------------------------------------------------
    # 5. consent gate — ONE decision, logged (source fhir_everything)
    # ------------------------------------------------------------------
    def _logs(self, patient):
        return self.env['health.consent.check.log'].sudo().search([
            ('client_id', '=', patient.id),
            ('consent_type', '=', 'data_sharing'),
            ('source', '=', 'fhir_everything')])

    def test_05a_enforced_without_consent_denies_and_logs(self):
        # NOTE (§5.8): assertRaises' savepoint rollback would VOID the
        # consent-check log written just before the raise — capture the
        # exception manually so the audit row survives to be asserted.
        before = len(self._logs(self.patient))
        raised = False
        try:
            build_everything_bundle(
                self.env, self.patient.id, {}, 'http://test', enforced=True)
        except FHIRNotFound:
            raised = True
        self.assertTrue(raised, '$everything did not deny an unconsented patient')
        self.assertGreater(len(self._logs(self.patient)), before,
                           'consent check was not logged on deny')

    def test_05b_enforced_with_consent_returns_full(self):
        consent = self.env['health.consent'].create({
            'client_id': self.patient.id, 'consent_type': 'data_sharing',
            'method': 'verbal'})
        consent.action_grant()
        bundle, _ = build_everything_bundle(
            self.env, self.patient.id, {}, 'http://test', enforced=True)
        by_type = self._by_type(bundle)
        self.assertIn('Observation', by_type)
        self.assertTrue(self._logs(self.patient))

    def test_05c_log_only_returns_full_and_logs(self):
        before = self._logs(self.patient)
        bundle, _ = build_everything_bundle(
            self.env, self.patient.id, {}, 'http://test', enforced=False)
        self.assertIn('Observation', self._by_type(bundle))  # nothing withheld
        self.assertGreater(len(self._logs(self.patient)), len(before))

    def test_05d_default_follows_the_config_parameter(self):
        """Every other test in this suite pins `enforced=` explicitly, so
        SOMETHING must still prove the default resolves from
        `health_fhir_core.consent_enforced`. It does — and this is the branch
        that changed the meaning of eight tests when GC-2 flipped the
        parameter on vietuat."""
        ICP = self.env['ir.config_parameter'].sudo()
        before = ICP.get_param('health_fhir_core.consent_enforced')
        self.addCleanup(ICP.set_param,
                        'health_fhir_core.consent_enforced', before)

        ICP.set_param('health_fhir_core.consent_enforced', 'True')
        raised = False
        try:  # §5.8: assertRaises' savepoint would void the consent log row
            build_everything_bundle(
                self.env, self.patient.id, {}, 'http://test')
        except FHIRNotFound:
            raised = True
        self.assertTrue(raised, 'the default did not read the enforced flag')

        ICP.set_param('health_fhir_core.consent_enforced', 'False')
        bundle, _ = build_everything_bundle(
            self.env, self.patient.id, {}, 'http://test')
        self.assertIn('Observation', self._by_type(bundle))

    # ------------------------------------------------------------------
    # 6. record-rule isolation: cross-catchment caller → FHIRNotFound
    # ------------------------------------------------------------------
    def test_06_record_rule_isolation(self):
        nurse = new_test_user(
            self.env, login='ev_nurse_b',
            groups='health_base.group_healthcare_nurse')
        nurse.catchment_province_id = self.province2.id
        env = self.env(user=nurse)
        # the nurse cannot see the province-A patient at all
        with self.assertRaises(FHIRNotFound):
            build_everything_bundle(env, self.patient.id, {}, 'http://test',
                                    enforced=False)

    # ------------------------------------------------------------------
    # 7. _type restricts resource types
    # ------------------------------------------------------------------
    def test_07_type_filter(self):
        bundle, _ = build_everything_bundle(
            self.env, self.patient.id,
            {'_type': ['Observation,Encounter']}, 'http://test',
            enforced=False)
        present = set(self._by_type(bundle))
        self.assertEqual(present, {'Observation', 'Encounter'})
        self.assertNotIn('Patient', present)  # Patient not in _type → excluded

    # ------------------------------------------------------------------
    # 8. _since filters on lastUpdated (write_date)
    # ------------------------------------------------------------------
    def test_08_since_filter(self):
        # backdate obs1's write_date to 2020 (raw SQL — write_date is ORM-managed)
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE health_observation SET write_date = %s WHERE id = %s",
            ('2020-01-01 00:00:00', self.obs1.id))
        self.env.invalidate_all()
        bundle, _ = build_everything_bundle(
            self.env, self.patient.id, {'_since': ['2023-01-01']},
            'http://test', enforced=False)
        obs_ids = {e['resource']['id']
                   for e in self._by_type(bundle).get('Observation', [])}
        self.assertNotIn(str(self.obs1.id), obs_ids)  # 2020 < since → excluded
        self.assertIn(str(self.obs2.id), obs_ids)      # recent → included

    # ------------------------------------------------------------------
    # 9. cap: > _count resources → truncation DECLARED, never silent
    # ------------------------------------------------------------------
    def test_09_truncation_declared(self):
        bundle, _ = build_everything_bundle(
            self.env, self.patient.id, {'_count': ['2']}, 'http://test',
            enforced=False)
        by_type = self._by_type(bundle)
        self.assertIn('OperationOutcome', by_type,
                      'truncation was not declared')
        oo = by_type['OperationOutcome'][0]
        self.assertEqual(oo['search']['mode'], 'outcome')
        self.assertEqual(oo['resource']['issue'][0]['code'], 'incomplete')
        # exactly 2 real resources + the declaration entry
        real = [e for e in bundle['entry']
                if e['resource']['resourceType'] != 'OperationOutcome']
        self.assertEqual(len(real), 2)
        self.assertGreater(bundle['total'], 2)  # total reflects the true count
        self._validate(oo['resource'])

    # ------------------------------------------------------------------
    # 11. unauthorized compartment model → DECLARED omission, not a hard fail
    # ------------------------------------------------------------------
    def test_11_unauthorized_model_declared(self):
        # A compartment model the caller cannot read (live example:
        # health.fall.risk / Flag ships with NO ir.model.access, so no token
        # user can read it) must be OMITTED and DECLARED, never 403 the whole
        # record. Force the AccessError on just the Flag model so the test is
        # not entangled with the pre-existing Patient-serializer field-ACL
        # fragility (gated res.partner fields) that only bites non-admin users.
        from unittest.mock import patch
        from odoo.exceptions import AccessError
        FallRisk = type(self.env['health.fall.risk'])
        original = FallRisk.search_count

        def _deny(model, *args, **kwargs):
            if model._name == 'health.fall.risk':
                raise AccessError('QA: simulated no access to health.fall.risk')
            return original(model, *args, **kwargs)

        with patch.object(FallRisk, 'search_count', _deny):
            bundle, _ = build_everything_bundle(
                self.env, self.patient.id, {}, 'http://test', enforced=False)
        self.assertEqual(bundle['resourceType'], 'Bundle')
        by_type = self._by_type(bundle)
        self.assertIn('Patient', by_type)       # root still readable
        self.assertIn('Observation', by_type)    # accessible types still present
        suppressed = [e['resource'] for e in bundle['entry']
                      if e['resource']['resourceType'] == 'OperationOutcome'
                      and e['resource']['issue'][0]['code'] == 'suppressed']
        self.assertTrue(suppressed, 'unauthorized model omission not declared')
        self.assertIn('Flag', suppressed[0]['issue'][0]['diagnostics'])
        self.assertEqual(suppressed[0]['issue'][0]['severity'], 'warning')
        self._validate(suppressed[0])

    # ------------------------------------------------------------------
    # 10. CapabilityStatement declares the everything operation on Patient
    # ------------------------------------------------------------------
    def test_10_capability_declares_everything(self):
        clear_capability_cache()
        statement = build_capability(self.env)
        patient = next(r for r in statement['rest'][0]['resource']
                       if r['type'] == 'Patient')
        ops = [o['name'] for o in patient.get('operation', [])]
        self.assertIn('everything', ops)
        # other resources do NOT carry it
        encounter = next(r for r in statement['rest'][0]['resource']
                         if r['type'] == 'Encounter')
        self.assertNotIn('operation', encounter)
        self._validate(statement)
        clear_capability_cache()
