# -*- coding: utf-8 -*-
"""Phase GC-2 — required-binding membership (register item G17).

Every FHIR element this facade emits with a REQUIRED binding must carry a code
from that binding's ValueSet. A resource can validate structurally and still
be wrong here: `fhir.resources` checks types and cardinality, not that
`Task.status = 'not_done'` is not a member of R4's TaskStatus.

Method: import the serializers' ACTUAL mapping dicts (never retype their
values — a retyped table drifts and proves nothing) and assert
`set(values) ⊆ required set`. The allowed sets below are transcribed from the
R4 (4.0.1) specification and are the fixed side of the comparison: a violation
is fixed in the MAPPING, never by widening the set.

Both directions of each table are checked where a search map exists: the
emitted status (what a client reads) and the searchable status (what a client
may send as `?status=`) are different dicts and can drift apart.
"""

from odoo.tests import TransactionCase, tagged

from odoo.addons.health_fhir_core.serializers import REGISTRY, fso_common
from odoo.addons.health_fhir_core.serializers.careplan import (
    _ACTIVITY_STATUS, _CAREPLAN_STATUS, _CAREPLAN_STATUS_SEARCH,
    _GOAL_LIFECYCLE, _GOAL_LIFECYCLE_SEARCH, _TASK_STATUS, _TASK_STATUS_SEARCH,
)
from odoo.addons.health_fhir_core.serializers.consent import (
    _STATUS as _CONSENT_STATUS, _STATUS_SEARCH as _CONSENT_STATUS_SEARCH,
)
from odoo.addons.health_fhir_core.serializers.medication import (
    _ADMIN_STATUS, _ADMIN_STATUS_SEARCH, _REQUEST_STATUS,
    _REQUEST_STATUS_SEARCH,
)
from odoo.addons.health_fhir_core.serializers.observation import (
    _STATE_TO_STATUS as _OBSERVATION_STATUS, _STATUS_TO_STATE,
)
from odoo.addons.health_fhir_core.serializers.questionnaire import (
    _INSTANCE_STATUS, _INSTANCE_STATUS_SEARCH, _TEMPLATE_STATUS,
    _TEMPLATE_STATUS_SEARCH,
)

# --- R4 4.0.1 required bindings (handover §3.3, verbatim) ------------------
OBSERVATION_STATUS = {
    'registered', 'preliminary', 'final', 'amended', 'corrected', 'cancelled',
    'entered-in-error', 'unknown'}
ENCOUNTER_STATUS = {
    'planned', 'arrived', 'triaged', 'in-progress', 'onleave', 'finished',
    'cancelled', 'entered-in-error', 'unknown'}
APPOINTMENT_STATUS = {
    'proposed', 'pending', 'booked', 'arrived', 'fulfilled', 'cancelled',
    'noshow', 'entered-in-error', 'checked-in', 'waitlist'}
CAREPLAN_STATUS = {
    'draft', 'active', 'on-hold', 'revoked', 'completed', 'entered-in-error',
    'unknown'}
GOAL_LIFECYCLE_STATUS = {
    'proposed', 'planned', 'accepted', 'active', 'on-hold', 'completed',
    'cancelled', 'entered-in-error', 'rejected'}
TASK_STATUS = {
    'draft', 'requested', 'received', 'accepted', 'rejected', 'ready',
    'cancelled', 'in-progress', 'on-hold', 'failed', 'completed',
    'entered-in-error'}
MEDICATION_REQUEST_STATUS = {
    'active', 'on-hold', 'cancelled', 'completed', 'entered-in-error',
    'stopped', 'draft', 'unknown'}
MEDICATION_ADMINISTRATION_STATUS = {
    'in-progress', 'not-done', 'on-hold', 'completed', 'entered-in-error',
    'stopped', 'unknown'}
QUESTIONNAIRE_RESPONSE_STATUS = {
    'in-progress', 'completed', 'amended', 'entered-in-error', 'stopped'}
CONSENT_STATUS = {
    'draft', 'proposed', 'active', 'rejected', 'inactive', 'entered-in-error'}
FLAG_STATUS = {'active', 'inactive', 'entered-in-error'}
CONDITION_CLINICAL_STATUS = {
    'active', 'recurrence', 'relapse', 'inactive', 'remission', 'resolved'}
SERVICE_REQUEST_STATUS = {
    'draft', 'active', 'on-hold', 'revoked', 'completed', 'entered-in-error',
    'unknown'}

# Bindings beyond the handover's 13, asserted for the same reason.
PUBLICATION_STATUS = {'draft', 'active', 'retired', 'unknown'}
CAREPLAN_ACTIVITY_STATUS = {
    'not-started', 'scheduled', 'in-progress', 'on-hold', 'completed',
    'cancelled', 'stopped', 'unknown', 'entered-in-error'}


@tagged('post_install', '-at_install')
class TestFHIRBindings(TransactionCase):

    def _subset(self, label, values, allowed):
        extra = set(values) - allowed
        self.assertFalse(
            extra,
            '%s emits %s, which is NOT in the R4 required binding. Fix the '
            'MAPPING (docs/conformance/clinical-status-mappings.md is '
            'generated from it) — never widen the allowed set.'
            % (label, sorted(extra)))
        self.assertTrue(values, '%s: empty mapping — wrong import?' % label)

    # ==================================================================
    # T2.4 — the 13 tables of handover §3.3
    # ==================================================================

    def test_51_observation_status(self):
        self._subset('Observation.status',
                     _OBSERVATION_STATUS.values(), OBSERVATION_STATUS)
        self._subset('Observation.status (searchable)',
                     _STATUS_TO_STATE.keys(), OBSERVATION_STATUS)

    def test_52_encounter_status(self):
        self._subset('Encounter.status',
                     fso_common.ENCOUNTER_STATUS_MAP.values(),
                     ENCOUNTER_STATUS)

    def test_53_appointment_status(self):
        self._subset('Appointment.status',
                     fso_common.APPOINTMENT_STATUS_MAP.values(),
                     APPOINTMENT_STATUS)

    def test_54_careplan_status(self):
        self._subset('CarePlan.status', _CAREPLAN_STATUS.values(),
                     CAREPLAN_STATUS)
        self._subset('CarePlan.status (searchable)',
                     _CAREPLAN_STATUS_SEARCH.keys(), CAREPLAN_STATUS)

    def test_55_goal_lifecycle_status(self):
        self._subset('Goal.lifecycleStatus', _GOAL_LIFECYCLE.values(),
                     GOAL_LIFECYCLE_STATUS)
        self._subset('Goal.lifecycleStatus (searchable)',
                     _GOAL_LIFECYCLE_SEARCH.keys(), GOAL_LIFECYCLE_STATUS)

    def test_56_task_status(self):
        self._subset('Task.status', _TASK_STATUS.values(), TASK_STATUS)
        self._subset('Task.status (searchable)',
                     _TASK_STATUS_SEARCH.keys(), TASK_STATUS)

    def test_57_medication_request_status(self):
        self._subset('MedicationRequest.status', _REQUEST_STATUS.values(),
                     MEDICATION_REQUEST_STATUS)
        self._subset('MedicationRequest.status (searchable)',
                     _REQUEST_STATUS_SEARCH.keys(), MEDICATION_REQUEST_STATUS)

    def test_58_medication_administration_status(self):
        self._subset('MedicationAdministration.status', _ADMIN_STATUS.values(),
                     MEDICATION_ADMINISTRATION_STATUS)
        self._subset('MedicationAdministration.status (searchable)',
                     _ADMIN_STATUS_SEARCH.keys(),
                     MEDICATION_ADMINISTRATION_STATUS)

    def test_59_questionnaire_response_status(self):
        self._subset('QuestionnaireResponse.status', _INSTANCE_STATUS.values(),
                     QUESTIONNAIRE_RESPONSE_STATUS)
        self._subset('QuestionnaireResponse.status (searchable)',
                     _INSTANCE_STATUS_SEARCH.keys(),
                     QUESTIONNAIRE_RESPONSE_STATUS)

    def test_60_consent_status(self):
        self._subset('Consent.status', _CONSENT_STATUS.values(),
                     CONSENT_STATUS)
        self._subset('Consent.status (searchable)',
                     _CONSENT_STATUS_SEARCH.keys(), CONSENT_STATUS)

    def test_61_flag_status(self):
        """Flag.status is not a dict — the serializer decides per record
        (superseded assessments go inactive). Both branches are exercised so
        the assertion is over what the code can actually emit."""
        province = self.env['health.catchment.province'].search([], limit=1)
        if not province:
            province = self.env['health.catchment.province'].create(
                {'name': 'GC2 Binding Province'})
        patient = self.env['res.partner'].create({
            'name': 'GC2 Binding Patient', 'is_patient': True,
            'catchment_province_id': province.id})
        FallRisk = self.env['health.fall.risk']
        common = {'patient_id': patient.id, 'history_of_falling': True,
                  'secondary_diagnosis': True, 'iv_therapy': True}
        older = FallRisk.create(
            dict(common, assessment_date='2026-01-01 00:00:00'))
        newer = FallRisk.create(
            dict(common, assessment_date='2026-06-01 00:00:00'))
        serializer = REGISTRY['Flag']
        emitted = {serializer.to_fhir(older)['status'],
                   serializer.to_fhir(newer)['status']}
        self.assertEqual(emitted, {'active', 'inactive'},
                         'the fixture did not exercise both branches')
        self._subset('Flag.status', emitted, FLAG_STATUS)

    def test_62_condition_clinical_status(self):
        """Condition.clinicalStatus is copied straight from the model's
        Selection, so the Selection IS the mapping table. health_condition is
        a downstream module — assert only when it is installed, and say so
        loudly if it is not (a silently skipped binding test is worthless)."""
        if 'health.condition' not in self.env:
            self.skipTest('health_condition is not installed on this database')
        selection = self.env['health.condition']._fields[
            'clinical_status'].selection
        values = [value for value, _label in selection]
        self._subset('Condition.clinicalStatus', values,
                     CONDITION_CLINICAL_STATUS)
        self.assertIn('Condition', REGISTRY,
                      'health.condition exists but no serializer registered')

    def test_63_service_request_status(self):
        self._subset('ServiceRequest.status',
                     fso_common.SERVICE_REQUEST_STATUS_MAP.values(),
                     SERVICE_REQUEST_STATUS)

    # ==================================================================
    # Beyond the 13 — same class of defect, same cost to assert
    # ==================================================================

    def test_64_questionnaire_publication_status(self):
        self._subset('Questionnaire.status', _TEMPLATE_STATUS.values(),
                     PUBLICATION_STATUS)
        self._subset('Questionnaire.status (searchable)',
                     _TEMPLATE_STATUS_SEARCH.keys(), PUBLICATION_STATUS)

    def test_65_careplan_activity_detail_status(self):
        self._subset('CarePlan.activity.detail.status',
                     _ACTIVITY_STATUS.values(), CAREPLAN_ACTIVITY_STATUS)

    # ==================================================================
    # The mapping document is generated from these same dicts — if a new
    # status-bearing resource is registered without a table here, the doc is
    # silently incomplete. This is the guard for that.
    # ==================================================================

    def test_66_every_status_bearing_resource_has_a_binding_test(self):
        covered = {
            'Observation', 'Encounter', 'Appointment', 'CarePlan', 'Goal',
            'Task', 'MedicationRequest', 'MedicationAdministration',
            'Questionnaire', 'QuestionnaireResponse', 'Consent', 'Flag',
            'Condition', 'ServiceRequest',
        }
        status_bearing = {
            rtype for rtype, serializer in REGISTRY.items()
            if {'status', 'lifecycle-status', 'clinical-status'}
            & set(serializer.search_params)
        }
        missing = status_bearing - covered
        self.assertFalse(
            missing,
            '%s expose a status search param but have no binding table in '
            'this module (and therefore no row in '
            'docs/conformance/clinical-status-mappings.md)' % sorted(missing))
