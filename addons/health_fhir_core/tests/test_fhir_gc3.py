# -*- coding: utf-8 -*-
"""Phase GC-3 — continuous conformance machinery (register items G4, G10).

Two controls are tested here:

C4 — sampled runtime validation. The mechanism already existed
(`validate_responses`) but was all-or-nothing and therefore switched off,
which is precisely what kept G10 open. The tests exercise the two things that
make it usable in production: the sampling decision, and the guarantee that a
drift finding is LOGGED and never surfaced to the caller.

C5 — the weekly conformance cron. Tested by calling `run_weekly_check()`
directly (the cron record is one line of `state='code'` around it): the green
path over live data, and the drift path via a deliberately wrong baseline.

Note for anyone reading the drift fixture below: `fhir.resources` does NOT
validate required-binding membership — a Location with `status='not-a-status'`
validates clean. That is measured, not assumed, and it is the reason the
binding tables in test_fhir_bindings.py have to exist as a separate tier. The
drift fixture therefore corrupts something the library DOES check
(`meta.lastUpdated`).
"""

import json
import logging
from unittest.mock import patch

from odoo.tests import HttpCase, TransactionCase, new_test_user, tagged

from odoo.addons.health_fhir_core.models.fhir_conformance import (
    ALARM_SUMMARY, OWNER_LOGIN_PARAM,
)
from odoo.addons.health_fhir_core.serializers import REGISTRY
from odoo.addons.health_fhir_core.serializers.base import (
    VALIDATE_CANARY_CLIENT_PARAM, VALIDATE_SAMPLE_PCT_PARAM,
    validation_sample_hit, validation_sample_pct,
)

CONTROLLER_LOGGER = 'odoo.addons.health_fhir_core.controllers.fhir'
CRON_LOGGER = 'odoo.addons.health_fhir_core.models.fhir_conformance'


def _drifted_location(self, facility):
    """A Location whose `meta.lastUpdated` is not an instant — the shape of a
    real serializer regression, and something `fhir.resources` rejects."""
    return {
        'resourceType': 'Location',
        'id': str(facility.id),
        'meta': {'lastUpdated': 'not-an-instant'},
        'status': 'active',
        'name': facility.name or '',
    }


@tagged('post_install', '-at_install')
class TestFHIRSamplingGC3(TransactionCase):
    """The sampling decision itself — no HTTP, so the branches are exact."""

    def setUp(self):
        super().setUp()
        self.ICP = self.env['ir.config_parameter'].sudo()
        for param in (VALIDATE_SAMPLE_PCT_PARAM, VALIDATE_CANARY_CLIENT_PARAM):
            before = self.ICP.get_param(param)
            self.addCleanup(self.ICP.set_param, param, before or '')
            self.ICP.set_param(param, '')

    def test_80_sample_pct_is_parsed_defensively(self):
        for raw, expected in (('', 0), ('0', 0), ('25', 25), ('100', 100),
                              ('  40 ', 40), ('7.9', 7), ('banana', 0),
                              ('-5', 0), ('900', 100), ('True', 0)):
            self.ICP.set_param(VALIDATE_SAMPLE_PCT_PARAM, raw)
            self.assertEqual(
                validation_sample_pct(self.env), expected,
                '%r should parse to %s — a typo in a config parameter must '
                'not become an outage, and must not silently mean 100'
                % (raw, expected))

    def test_81_zero_percent_never_samples(self):
        self.ICP.set_param(VALIDATE_SAMPLE_PCT_PARAM, '0')
        self.assertFalse(any(
            validation_sample_hit(self.env, 'some-client')
            for _ in range(200)))

    def test_82_hundred_percent_always_samples(self):
        self.ICP.set_param(VALIDATE_SAMPLE_PCT_PARAM, '100')
        self.assertTrue(all(
            validation_sample_hit(self.env, 'some-client')
            for _ in range(20)))

    def test_83_canary_client_matches_on_the_audited_label(self):
        """The canary is matched against `gateway_auth['key_ref']` — the same
        identifier the audit row carries — so "which client drifted" and
        "which client was sampled" are the same question."""
        self.ICP.set_param(VALIDATE_SAMPLE_PCT_PARAM, '0')
        self.ICP.set_param(VALIDATE_CANARY_CLIENT_PARAM, 'partner-alpha')
        self.assertTrue(validation_sample_hit(self.env, 'partner-alpha'))
        self.assertTrue(validation_sample_hit(self.env, ' partner-alpha '))
        self.assertFalse(validation_sample_hit(self.env, 'partner-beta'))
        self.assertFalse(validation_sample_hit(self.env, None))
        self.assertFalse(validation_sample_hit(self.env, ''))


@tagged('post_install', '-at_install')
class TestFHIRRuntimeValidationGC3(HttpCase):
    """C4 end to end over the real route. Location is used deliberately: it
    carries no PHI (`patient_ids_of == []`), so the consent gate is not part
    of what is being measured."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.province = env['health.catchment.province'].search([], limit=1)
        if not cls.province:
            cls.province = env['health.catchment.province'].create(
                {'name': 'GC3 Province'})
        cls.facility = env['health.facility'].search(
            [('catchment_province_id', '=', cls.province.id)], limit=1)
        if not cls.facility:
            cls.facility = env['health.facility'].create({
                'name': 'GC3 Facility', 'code': 'GC3TST',
                'street': '3 Đường GC3', 'city': 'Hà Nội',
                'catchment_province_id': cls.province.id})

        # A service user shaped like a real token user: one healthcare group
        # (read on health.facility), nothing else.
        cls.service_user = new_test_user(
            env, login='gc3_fhir_service',
            groups='base.group_user,'
                   'health_base.group_healthcare_receptionist')
        cls.service_user.catchment_province_id = cls.province.id

        cls.client = env['gateway.oauth.client'].create({
            'name': 'GC3 Conformance Client',
            'user_id': cls.service_user.id,
            'allowed_scope_ids': [(6, 0, env['api.key.scope'].search(
                [('code', '=', 'system/Location.read')]).ids)],
            'token_lifetime': 3600,
        })
        cls.token = env['gateway.token'].issue(
            cls.client, ['system/Location.read'])
        # A second token for the ACL-failure probe: the receptionist service
        # user has NO ir.model.access row on health.clinical.note.
        cls.docref_token = env['gateway.token'].issue(
            cls.client, ['system/DocumentReference.read'])

    def setUp(self):
        super().setUp()
        self.ICP = self.env['ir.config_parameter'].sudo()
        for param in (VALIDATE_SAMPLE_PCT_PARAM, VALIDATE_CANARY_CLIENT_PARAM,
                      'health_fhir_core.validate_responses'):
            before = self.ICP.get_param(param)
            self.addCleanup(self.ICP.set_param, param, before or '')
            self.ICP.set_param(param, '')

    def _get_location(self):
        return self.url_open(
            '/fhir/r4/Location/%s' % self.facility.id,
            headers={'Authorization': 'Bearer %s' % self.token})

    def test_84_drift_is_logged_and_the_caller_still_gets_a_response(self):
        """pct=100 + a serializer emitting an invalid resource: the drift is
        logged once, and the response is unchanged. Turning a monitoring
        control into a 500 would be strictly worse than no control."""
        self.ICP.set_param(VALIDATE_SAMPLE_PCT_PARAM, '100')
        serializer_cls = type(REGISTRY['Location'])
        with patch.object(serializer_cls, 'to_fhir', _drifted_location):
            with self.assertLogs(CONTROLLER_LOGGER, level='ERROR') as captured:
                response = self._get_location()
        self.assertEqual(response.status_code, 200,
                         'a conformance finding must never reach the caller')
        body = json.loads(response.content.decode('utf-8'))
        self.assertEqual(body['resourceType'], 'Location')
        self.assertEqual(body['id'], str(self.facility.id))
        drift = [line for line in captured.output
                 if 'FHIR-CONFORMANCE-DRIFT' in line]
        self.assertEqual(len(drift), 1, 'expected exactly one drift line, '
                                        'got: %s' % captured.output)
        self.assertIn('rtype=Location', drift[0])
        self.assertIn('id=%s' % self.facility.id, drift[0])

    def test_85_zero_percent_does_not_validate_at_all(self):
        """The default. Sampling off means the validator is never called —
        not called-and-ignored, which would still cost the latency."""
        self.ICP.set_param(VALIDATE_SAMPLE_PCT_PARAM, '0')
        with patch('odoo.addons.health_fhir_core.controllers.fhir'
                   '.validate_resource') as validator:
            response = self._get_location()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(validator.call_count, 0,
                         'validate_resource ran with sampling at 0%')

    def test_86_canary_client_validates_without_sampling(self):
        """The canary path over the real route: pct stays 0, and this
        client's response is validated because it is named."""
        self.ICP.set_param(VALIDATE_SAMPLE_PCT_PARAM, '0')
        self.ICP.set_param(VALIDATE_CANARY_CLIENT_PARAM,
                           self.client.client_id)
        with patch('odoo.addons.health_fhir_core.controllers.fhir'
                   '.validate_resource') as validator:
            response = self._get_location()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            validator.call_count, 1,
            'the canary client was not validated — check that the label '
            'matched is the one the gateway stamps (gateway_auth key_ref)')


    def test_93_practitioner_prefetch_drops_the_hr_private_fields(self):
        """G14's second instance, found live by the GC-3 deploy smoke.

        `hr.employee` treats every field outside its public-profile whitelist
        as private, and the blanket stored-field prefetch dragged ~30 of them
        (`private_phone`, `birthday`, `salary_distribution`, `hourly_cost`,
        `pin`, …), so the prefetch alone raised AccessError for a service user
        with no HR group. `prefetch_fields` now declares only what `to_fhir`
        reads — the same fix D1 applied to Patient in GC-1 — and this asserts
        the prefetch itself is clean for such a user.

        SH-1 §4 closed the other half: `to_fhir` also reads
        `healthcare_skill_ids` for `Practitioner.qualification`, which was
        private on the public profile too. It is now published on
        `hr.employee.public` by health_fieldservice (NOT health_base, as the
        GC-3 report guessed) and declared in `prefetch_fields`, so the fetch
        below covers it. The qualification output itself is asserted in
        `test_sh1_practitioner.py`."""
        env = self.env(user=self.service_user)
        employee = env['hr.employee'].sudo().search(
            [('healthcare_facility_id', '!=', False)], limit=1)
        if not employee:
            self.skipTest('no healthcare hr.employee record to serialize')
        serializer = REGISTRY['Practitioner']
        record = serializer.read_record(env, employee.id)
        self.assertTrue(record, 'record rules hid the employee from the '
                                'minimal-privilege user — fixture problem')

        declared = serializer.prefetch_fields
        self.assertIsNotNone(
            declared, 'Practitioner went back to the blanket prefetch')
        for name in ('name', 'active', 'staff_code', 'license_number',
                     'work_phone', 'work_email', 'write_date'):
            self.assertIn(name, declared)
        for name in ('private_phone', 'birthday', 'hourly_cost', 'pin',
                     'salary_distribution', 'employee_properties'):
            self.assertNotIn(name, declared)

        # The prefetch step of serialize_batch, for a user with no HR group:
        # this is the read that used to raise before the declaration existed.
        record.fetch([f for f in declared if f in record._fields
                      and record._fields[f].store])
        self.assertEqual(record.name, employee.sudo().name)

    def test_92_missing_acl_is_a_fhir_403_not_an_html_page(self):
        """A token whose service user is missing ONE model's ACL must get a
        FHIR OperationOutcome, not Odoo's HTML 403. Found live by the GC-3
        deploy smoke: `/fhir/r4/DocumentReference` answered
        `<!doctype html><title>403 Forbidden</title>` — unparseable by any
        FHIR client, and it named the Odoo user in the body."""
        response = self.url_open(
            '/fhir/r4/DocumentReference?_count=1',
            headers={'Authorization': 'Bearer %s' % self.docref_token})
        self.assertEqual(response.status_code, 403)
        self.assertIn('application/fhir+json',
                      response.headers.get('Content-Type', ''))
        body = json.loads(response.content.decode('utf-8'))
        self.assertEqual(body['resourceType'], 'OperationOutcome')
        self.assertEqual(body['issue'][0]['code'], 'forbidden')
        self.assertIn('DocumentReference', body['issue'][0]['diagnostics'])
        # The diagnostic must not leak the Odoo model, the ACL rule or the user.
        self.assertNotIn('health.clinical.note', response.text)
        self.assertNotIn('ir.model.access', response.text)


@tagged('post_install', '-at_install')
class TestFHIRConformanceCronGC3(TransactionCase):
    """C5 — the weekly self-check."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Conformance = cls.env['fhir.conformance']

    def setUp(self):
        super().setUp()
        self.ICP = self.env['ir.config_parameter'].sudo()
        before = self.ICP.get_param(OWNER_LOGIN_PARAM)
        self.addCleanup(self.ICP.set_param, OWNER_LOGIN_PARAM, before or '')
        self.ICP.set_param(OWNER_LOGIN_PARAM, '')

    def _open_alarms(self):
        return self.env['mail.activity'].sudo().search(
            [('summary', '=', ALARM_SUMMARY)])

    def _capture(self, level=logging.INFO):
        """Own handler rather than assertLogs: assertLogs REPLACES the
        logger's handlers and raises when it captured nothing, which turns
        "the check reported failures" into "no logs triggered" and hides the
        failure list — the one thing worth reading. This keeps the real
        assertion first and the log assertion second."""
        records = []
        logger = logging.getLogger(CRON_LOGGER)
        handler = logging.Handler(level=level)
        handler.emit = records.append
        old_level = logger.level
        logger.setLevel(level)
        logger.addHandler(handler)
        self.addCleanup(logger.setLevel, old_level)
        self.addCleanup(logger.removeHandler, handler)
        return records

    def test_87_green_path_logs_ok_and_raises_nothing(self):
        """The real check over the live database: capability equals the
        committed baseline, and one record of every populated resource type
        still validates."""
        before = self._open_alarms()
        records = self._capture()
        failures = self.Conformance.run_weekly_check()
        self.assertEqual(
            failures, [],
            'the weekly conformance check failed on live data: %s'
            % ' | '.join(failures))
        messages = [record.getMessage() for record in records]
        ok = [m for m in messages if 'FHIR-CONFORMANCE-OK' in m]
        self.assertEqual(len(ok), 1,
                         'expected exactly one OK line, got %s' % messages)
        self.assertEqual(self._open_alarms(), before,
                         'a green run raised an alarm')

    def test_88_corrupt_baseline_fails_and_creates_an_activity(self):
        """C2's teeth, re-grown in production: if the deployed code would
        serve a statement the committed baseline does not describe, someone
        gets a to-do."""
        wrong = {'resourceType': 'CapabilityStatement', 'status': 'active',
                 'fhirVersion': '4.0.1', 'rest': []}
        before = self._open_alarms()
        records = self._capture()
        with patch.object(type(self.Conformance), '_read_baseline',
                          return_value=wrong):
            failures = self.Conformance.run_weekly_check()
        self.assertTrue(failures)
        self.assertTrue(any('capability' in f for f in failures), failures)
        messages = [record.getMessage() for record in records]
        self.assertTrue(any('FHIR-CONFORMANCE-FAIL' in m for m in messages),
                        messages)
        raised = self._open_alarms() - before
        self.assertEqual(len(raised), 1,
                         'the failure did not produce exactly one activity')
        self.assertEqual(raised.res_model, 'res.partner')
        self.assertEqual(raised.res_id, raised.user_id.partner_id.id)
        self.assertIn('capability', raised.note)

    def test_89_a_second_failure_reuses_the_open_activity(self):
        """A weekly cron that stacks a new to-do every run turns a finding
        into noise (ledger §5.89: the dedupe key is whatever you search on)."""
        wrong = {'resourceType': 'CapabilityStatement', 'rest': []}
        before = self._open_alarms()
        with patch.object(type(self.Conformance), '_read_baseline',
                          return_value=wrong):
            self.Conformance.run_weekly_check()
            self.Conformance.run_weekly_check()
        self.assertEqual(len(self._open_alarms() - before), 1)

    def test_90_owner_param_selects_the_assignee_and_falls_back(self):
        owner = new_test_user(self.env, login='gc3_conformance_owner',
                              groups='base.group_user')
        self.ICP.set_param(OWNER_LOGIN_PARAM, 'gc3_conformance_owner')
        self.assertEqual(self.Conformance._owner_user(), owner)

        # A param naming nobody must not silently swallow the alarm.
        self.ICP.set_param(OWNER_LOGIN_PARAM, 'nobody_by_that_login')
        fallback = self.Conformance._owner_user()
        self.assertTrue(fallback, 'no fallback owner — the alarm would '
                                  'have nowhere to land')
        self.assertNotEqual(fallback, owner)

    def test_91_a_broken_resource_is_reported_per_type(self):
        """The resource half of the check, forced: a serializer emitting an
        invalid resource is named with its type and record id."""
        serializer_cls = type(REGISTRY['Location'])
        if not self.env['health.facility'].sudo().search([], limit=1):
            self.skipTest('no health.facility record to sample')
        with patch.object(serializer_cls, 'to_fhir', _drifted_location):
            failures, checked = self.Conformance._check_resources()
        self.assertGreater(checked, 0)
        location_failures = [f for f in failures if f.startswith('Location/')]
        self.assertEqual(len(location_failures), 1, failures)
