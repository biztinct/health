# -*- coding: utf-8 -*-
"""Model-layer tests for the FHIR Phase 2 clinical-spine resources.

Mirrors test_fhir_core.py: TransactionCase, direct serializer calls (no
HTTP), every emitted dict validated against fhir.resources (R4B, pydantic).
"""

from datetime import datetime, timedelta

from odoo import fields
from odoo.tests import TransactionCase, tagged

from odoo.addons.health_fhir_core.capability import (
    build_capability, clear_capability_cache,
)
from odoo.addons.health_fhir_core.serializers import REGISTRY
from odoo.addons.health_fhir_core.serializers.base import validate_resource

NEW_RESOURCES = (
    'Observation', 'CarePlan', 'Goal', 'Task', 'MedicationRequest',
    'MedicationAdministration', 'Questionnaire', 'QuestionnaireResponse',
    'AdverseEvent', 'Flag', 'Consent',
)


@tagged('post_install', '-at_install')
class TestFHIRPhase2(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env

        cls.province = env['health.catchment.province'].search([], limit=1)
        if not cls.province:
            cls.province = env['health.catchment.province'].create({
                'name': 'FHIR P2 Province'})
        cls.facility = env['health.facility'].search(
            [('catchment_province_id', '=', cls.province.id)], limit=1)
        if not cls.facility:
            cls.facility = env['health.facility'].create({
                'name': 'FHIR P2 Facility', 'code': 'FHIRP2',
                'street': '1 Test', 'city': 'Hà Nội',
                'catchment_province_id': cls.province.id})
        cls.patient = env['res.partner'].create({
            'name': 'Lê Thị Bệnh Nhân P2', 'is_patient': True,
            'catchment_province_id': cls.province.id,
            'primary_facility_id': cls.facility.id})
        cls.employee = env['hr.employee'].create({
            'name': 'Nurse P2', 'healthcare_facility_id': cls.facility.id})
        # An Encounter-qualifying visit (assigned) …
        cls.fso = env['health.fieldservice.order'].create({
            'patient_id': cls.patient.id, 'facility_id': cls.facility.id,
            'scheduled_datetime': datetime(2026, 7, 10, 2, 0, 0),
            'scheduled_duration': 60})
        cls.fso.write({'state': 'assigned'})
        # … and a draft visit (Appointment-only, no Encounter).
        cls.draft_fso = env['health.fieldservice.order'].create({
            'patient_id': cls.patient.id, 'facility_id': cls.facility.id,
            'scheduled_datetime': datetime(2026, 7, 12, 2, 0, 0),
            'scheduled_duration': 60})

    def _validate(self, resource_dict):
        try:
            return validate_resource(resource_dict)
        except ImportError:
            self.skipTest('fhir.resources is not installed in this environment')

    # ------------------------------------------------------------------
    # CapabilityStatement — Phase 2 adds 11 resources (>=19; downstream
    # modules such as health_fhir_terminology register more, e.g. CodeSystem)
    # ------------------------------------------------------------------
    def test_capability_lists_phase2_resources(self):
        clear_capability_cache()
        statement = build_capability(self.env)
        listed = [r['type'] for r in statement['rest'][0]['resource']]
        self.assertGreaterEqual(len(listed), 19)
        for rtype in NEW_RESOURCES:
            self.assertIn(rtype, listed)
        # each new resource mirrors its registry search-param table
        for resource in statement['rest'][0]['resource']:
            if resource['type'] not in NEW_RESOURCES:
                continue
            names = [p['name'] for p in resource['searchParam']]
            for name in REGISTRY[resource['type']].search_params:
                self.assertIn(name, names)
        self._validate(statement)

    # ------------------------------------------------------------------
    # Observation
    # ------------------------------------------------------------------
    def test_observation_heart_rate(self):
        obs = self.env['health.observation'].create_coded(
            self.patient.id, '8867-4', 72, fso_id=self.fso.id)
        resource = REGISTRY['Observation'].to_fhir(obs)
        self.assertEqual(resource['status'], 'final')
        self.assertEqual(resource['code']['coding'][0]['code'], '8867-4')
        self.assertEqual(resource['code']['coding'][0]['system'],
                         'http://loinc.org')
        self.assertEqual(resource['valueQuantity']['value'], 72)
        self.assertEqual(resource['valueQuantity']['code'], '/min')
        self.assertEqual(resource['subject']['reference'],
                         'Patient/%s' % self.patient.id)
        # assigned FSO qualifies as an Encounter
        self.assertEqual(resource['encounter']['reference'],
                         'Encounter/%s' % self.fso.id)
        # heart rate is a FHIR vital sign
        self.assertEqual(resource['category'][0]['coding'][0]['code'],
                         'vital-signs')
        self.assertEqual(REGISTRY['Observation'].patient_ids_of(obs),
                         [self.patient.id])
        self._validate(resource)

    def test_observation_panel_has_components(self):
        panel = self.env['health.observation'].create_panel(
            self.patient.id, 'bp_panel',
            [{'code': 'bp_sys', 'value': 120},
             {'code': 'bp_dia', 'value': 80}])
        resource = REGISTRY['Observation'].to_fhir(panel)
        self.assertNotIn('valueQuantity', resource)
        self.assertEqual(len(resource['component']), 2)
        codes = {c['code']['coding'][0]['code'] for c in resource['component']}
        self.assertEqual(codes, {'8480-6', '8462-4'})
        self._validate(resource)

    def test_observation_draft_fso_omits_encounter(self):
        obs = self.env['health.observation'].create_coded(
            self.patient.id, '8867-4', 68, fso_id=self.draft_fso.id)
        resource = REGISTRY['Observation'].to_fhir(obs)
        self.assertNotIn('encounter', resource)
        self._validate(resource)

    def test_observation_search_by_patient_and_status(self):
        self.env['health.observation'].create_coded(
            self.patient.id, '8867-4', 70)
        serializer = REGISTRY['Observation']
        records, _, _ = serializer.search_records(self.env, {
            'patient': ['Patient/%s' % self.patient.id],
            'status': ['final']})
        self.assertTrue(records)
        self.assertTrue(all(r.client_id == self.patient for r in records))

    # ------------------------------------------------------------------
    # CarePlan + Goal + Task
    # ------------------------------------------------------------------
    def _make_plan(self):
        plan = self.env['health.careplan'].create({
            'client_id': self.patient.id, 'category': 'chronic',
            'title': 'BP control', 'period_start': fields.Date.today()})
        hr = self.env['health.vitals.type'].get_by_code('hr')
        self.env['health.careplan.goal'].create({
            'careplan_id': plan.id, 'name': 'Keep HR in range',
            'vitals_type_id': hr.id, 'lifecycle_status': 'active',
            'target_value_min': 55, 'target_value_max': 95,
            'due_date': fields.Date.today() + timedelta(days=30)})
        self.env['health.careplan.activity'].create({
            'careplan_id': plan.id, 'name': 'Check vital signs',
            'frequency': 'every_visit'})
        plan.action_activate()
        return plan

    def test_careplan_goal_serialize(self):
        plan = self._make_plan()
        resource = REGISTRY['CarePlan'].to_fhir(plan)
        self.assertEqual(resource['status'], 'active')
        self.assertEqual(resource['intent'], 'plan')
        self.assertEqual(resource['category'][0]['coding'][0]['code'],
                         'chronic')
        self.assertEqual(len(resource['activity']), 1)
        self.assertEqual(resource['activity'][0]['detail']['status'],
                         'scheduled')
        self.assertTrue(resource['goal'])
        self._validate(resource)

        goal = plan.goal_ids
        goal_resource = REGISTRY['Goal'].to_fhir(goal)
        self.assertEqual(goal_resource['lifecycleStatus'], 'active')
        self.assertEqual(goal_resource['subject']['reference'],
                         'Patient/%s' % self.patient.id)
        target = goal_resource['target'][0]
        self.assertEqual(target['measure']['coding'][0]['code'], '8867-4')
        self.assertEqual(target['detailRange']['low']['value'], 55)
        self.assertEqual(target['detailRange']['high']['value'], 95)
        self._validate(goal_resource)

    def test_task_compiles_and_serializes(self):
        plan = self._make_plan()
        fso = self.env['health.fieldservice.order'].create({
            'patient_id': self.patient.id, 'facility_id': self.facility.id,
            'scheduled_datetime': fields.Datetime.now() + timedelta(days=1)})
        fso.write({'state': 'confirmed'})
        task = fso.careplan_task_ids
        self.assertTrue(task, 'a task must compile onto the confirmed visit')
        task = task[0]
        resource = REGISTRY['Task'].to_fhir(task)
        self.assertEqual(resource['status'], 'requested')
        self.assertEqual(resource['intent'], 'order')
        self.assertEqual(resource['for']['reference'],
                         'Patient/%s' % self.patient.id)
        self.assertEqual(resource['basedOn'][0]['reference'],
                         'CarePlan/%s' % plan.id)
        self._validate(resource)

        # not_done → statusReason coding
        task.action_mark_not_done(reason='client_refused', note='asleep')
        resource = REGISTRY['Task'].to_fhir(task)
        self.assertEqual(resource['status'], 'failed')
        self.assertEqual(resource['statusReason']['coding'][0]['code'],
                         'client_refused')
        self.assertEqual(resource['statusReason']['text'], 'asleep')
        self._validate(resource)

    # ------------------------------------------------------------------
    # MedicationRequest + MedicationAdministration
    # ------------------------------------------------------------------
    def _make_order(self):
        med = self.env['health.medication'].create({
            'name': 'Paracetamol 500mg', 'rxnorm_code': '198440',
            'dav_reg_no': 'VD-12345-20'})
        order = self.env['health.medication.order'].create({
            'client_id': self.patient.id, 'medication_id': med.id,
            'dose_quantity': 1.0, 'dose_unit': 'tablet', 'route': 'oral',
            'frequency': 'od',
            'start_date': fields.Date.today() + timedelta(days=1)})
        order.action_activate()  # single order → no interaction API call
        return order

    def test_medication_request_serialize(self):
        order = self._make_order()
        resource = REGISTRY['MedicationRequest'].to_fhir(order)
        self.assertEqual(resource['status'], 'active')
        self.assertEqual(resource['intent'], 'order')
        codings = resource['medicationCodeableConcept']['coding']
        systems = {c['system']: c['code'] for c in codings}
        self.assertEqual(
            systems['http://www.nlm.nih.gov/research/umls/rxnorm'], '198440')
        self.assertEqual(systems['https://dav.gov.vn/so-dang-ky'],
                         'VD-12345-20')
        dosage = resource['dosageInstruction'][0]
        self.assertEqual(dosage['route']['text'], 'Oral')
        self.assertEqual(dosage['doseAndRate'][0]['doseQuantity']['value'],
                         1.0)
        self._validate(resource)

    def test_medication_administration_excludes_planned(self):
        order = self._make_order()
        serializer = REGISTRY['MedicationAdministration']
        # planned slots must NOT appear on the facade
        planned = self.env['health.medication.administration'].search(
            [('order_id', '=', order.id)], order='planned_datetime')
        self.assertTrue(planned)
        records, _, _ = serializer.search_records(self.env, {
            'patient': ['Patient/%s' % self.patient.id]})
        self.assertFalse(records & planned,
                         'planned administrations must be excluded')
        # record one given → now visible + valid
        slot = planned[0]
        slot.action_record_given()
        self.assertEqual(slot.state, 'given')
        resource = serializer.to_fhir(slot)
        self.assertEqual(resource['status'], 'completed')
        self.assertEqual(resource['request']['reference'],
                         'MedicationRequest/%s' % order.id)
        self.assertEqual(resource['subject']['reference'],
                         'Patient/%s' % self.patient.id)
        self._validate(resource)
        records, _, _ = serializer.search_records(self.env, {
            'patient': [str(self.patient.id)], 'status': ['completed']})
        self.assertIn(slot, records)

    # ------------------------------------------------------------------
    # Questionnaire + QuestionnaireResponse
    # ------------------------------------------------------------------
    def _pain_template(self):
        template = self.env['health.form.template'].search(
            [('code', '=', 'PAIN'), ('state', '=', 'published')], limit=1)
        self.assertTrue(template, 'seeded PAIN template must exist')
        return template

    def test_questionnaire_serialize(self):
        template = self._pain_template()
        resource = REGISTRY['Questionnaire'].to_fhir(template)
        self.assertEqual(resource['status'], 'active')
        self.assertEqual(resource['name'], 'PAIN')
        link_ids = {item['linkId']: item for item in resource['item']}
        self.assertIn('pain_score', link_ids)
        self.assertEqual(link_ids['pain_score']['type'], 'decimal')
        self.assertEqual(link_ids['pain_location']['type'], 'string')
        self.assertEqual(link_ids['pain_character']['type'], 'choice')
        self.assertTrue(link_ids['pain_character']['answerOption'])
        self._validate(resource)

    def test_questionnaire_response_serialize(self):
        template = self._pain_template()
        instance = self.env['health.form.instance'].create({
            'template_id': template.id, 'client_id': self.patient.id,
            'order_id': self.fso.id,
            'answers_json': {'pain_score': 5, 'pain_location': 'lower back',
                             'pain_character': 'dull'}})
        instance.action_complete()
        self.assertEqual(instance.state, 'completed')
        resource = REGISTRY['QuestionnaireResponse'].to_fhir(instance)
        self.assertEqual(resource['status'], 'completed')
        self.assertEqual(resource['questionnaire'],
                         'Questionnaire/%s' % template.id)
        items = {item['linkId']: item['answer'][0] for item in resource['item']}
        # linkIds correlate with the Questionnaire schema keys
        self.assertEqual(items['pain_score']['valueDecimal'], 5)
        self.assertEqual(items['pain_location']['valueString'], 'lower back')
        self.assertEqual(items['pain_character']['valueString'], 'dull')
        self.assertEqual(resource['encounter']['reference'],
                         'Encounter/%s' % self.fso.id)
        self._validate(resource)

    # ------------------------------------------------------------------
    # AdverseEvent
    # ------------------------------------------------------------------
    def test_adverse_event_serialize_and_excludes_staff_only(self):
        incident = self.env['health.incident'].create({
            'incident_type': 'fall', 'severity': '3',
            'client_id': self.patient.id, 'order_id': self.fso.id,
            'description': 'Client slipped in the bathroom.'})
        resource = REGISTRY['AdverseEvent'].to_fhir(incident)
        self.assertEqual(resource['actuality'], 'actual')
        self.assertEqual(resource['event']['coding'][0]['code'], 'fall')
        self.assertEqual(resource['severity']['coding'][0]['code'], 'moderate')
        self.assertEqual(resource['subject']['reference'],
                         'Patient/%s' % self.patient.id)
        self.assertEqual(resource['encounter']['reference'],
                         'Encounter/%s' % self.fso.id)
        # PHI narrative is never exported
        self.assertNotIn('description', resource)
        self._validate(resource)

        # staff-only incident (no client) is excluded from the facade
        staff_only = self.env['health.incident'].create({
            'incident_type': 'injury', 'severity': '2',
            'description': 'Staff strained back moving equipment.'})
        serializer = REGISTRY['AdverseEvent']
        records, _, _ = serializer.search_records(self.env, {})
        self.assertIn(incident, records)
        self.assertNotIn(staff_only, records)

    # ------------------------------------------------------------------
    # Flag ← health.fall.risk
    # ------------------------------------------------------------------
    def test_flag_status_active_then_superseded(self):
        older = self.env['health.fall.risk'].create({
            'patient_id': self.patient.id,
            'assessment_date': datetime(2026, 1, 1, 8, 0, 0),
            'history_of_falling': True, 'ambulatory_aid': 'furniture'})
        self.assertEqual(older.risk_level, 'high')
        serializer = REGISTRY['Flag']
        resource = serializer.to_fhir(older)
        self.assertEqual(resource['status'], 'active')
        self.assertEqual(resource['code']['coding'][0]['code'], 'falls-risk')
        self.assertIn('Morse', resource['code']['text'])
        self._validate(resource)

        newer = self.env['health.fall.risk'].create({
            'patient_id': self.patient.id,
            'assessment_date': datetime(2026, 6, 1, 8, 0, 0),
            'history_of_falling': True, 'ambulatory_aid': 'furniture'})
        self.assertEqual(serializer.to_fhir(older)['status'], 'inactive')
        self.assertEqual(serializer.to_fhir(newer)['status'], 'active')

    # ------------------------------------------------------------------
    # Consent
    # ------------------------------------------------------------------
    def test_consent_active_and_withdrawn(self):
        active = self.env['health.consent'].create({
            'client_id': self.patient.id, 'consent_type': 'service',
            'method': 'verbal', 'effective_date': fields.Date.today()})
        active.action_grant()
        resource = REGISTRY['Consent'].to_fhir(active)
        self.assertEqual(resource['status'], 'active')
        self.assertEqual(resource['scope']['coding'][0]['code'], 'treatment')
        self.assertEqual(resource['category'][0]['coding'][0]['code'],
                         'service')
        self.assertEqual(resource['patient']['reference'],
                         'Patient/%s' % self.patient.id)
        self._validate(resource)

        withdrawn = self.env['health.consent'].create({
            'client_id': self.patient.id, 'consent_type': 'photography',
            'method': 'verbal', 'effective_date': fields.Date.today()})
        withdrawn.action_grant()
        withdrawn.write({'withdrawal_reason': 'Client asked'})
        withdrawn.action_withdraw()
        resource = REGISTRY['Consent'].to_fhir(withdrawn)
        self.assertEqual(resource['status'], 'inactive')
        self.assertEqual(resource['scope']['coding'][0]['code'],
                         'patient-privacy')
        self._validate(resource)

        # base_domain excludes drafts
        serializer = REGISTRY['Consent']
        records, _, _ = serializer.search_records(self.env, {
            'patient': ['Patient/%s' % self.patient.id], 'status': ['active']})
        self.assertIn(active, records)
        self.assertNotIn(withdrawn, records)
