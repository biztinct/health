# -*- coding: utf-8 -*-
"""Phase GC-1 — capability truth + the two integration-breaking defects.

Covers the gap register items G14 (minimal-privilege Patient read), G15 (Flag
ACL), G2/G12 (operations declared, capability nits), G3 (software element),
G11 (R4B pin) and the C2 baseline/route-diff controls.

The suite is deliberately hostile to "it works for admin": every access test
runs as a user holding ONE healthcare group and nothing else, because that is
what a real service token maps onto.
"""

import importlib
import importlib.metadata
import json

from odoo.tests import TransactionCase, new_test_user, tagged
from odoo.tools.misc import file_open

from odoo.addons.health_fhir_core.capability import (
    SEARCH_PARAM_BASE, build_capability, clear_capability_cache,
)
from odoo.addons.health_fhir_core.serializers import REGISTRY
from odoo.addons.health_fhir_core.serializers.base import validate_resource
from odoo.addons.health_fhir_core.serializers.everything import (
    build_everything_bundle,
)


def _gender(env, code):
    """The `gender` vocabulary row for a code — gender is a lookup value, not
    a Selection, since it joined the client-editable dropdowns."""
    return env['health.lookup.value'].with_context(active_test=False).search(
        [('category_code', '=', 'gender'), ('code', '=', code)], limit=1)


BASELINE_PATH = 'health_fhir_core/conformance/capability_baseline.json'


def _normalized(statement):
    """The comparable form of a CapabilityStatement: everything except the
    generation timestamp, key-sorted so the comparison is byte-exact."""
    comparable = {k: v for k, v in statement.items() if k != 'date'}
    return json.dumps(comparable, sort_keys=True, indent=2, ensure_ascii=False)


@tagged('post_install', '-at_install')
class TestFHIRConformanceGC1(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env

        cls.province = env['health.catchment.province'].search([], limit=1)
        if not cls.province:
            cls.province = env['health.catchment.province'].create({
                'name': 'GC1 Province'})

        cls.facility = env['health.facility'].search(
            [('catchment_province_id', '=', cls.province.id)], limit=1)
        if not cls.facility:
            cls.facility = env['health.facility'].create({
                'name': 'GC1 Facility', 'code': 'GC1TST',
                'catchment_province_id': cls.province.id})

        cls.patient = env['res.partner'].create({
            'name': 'Lê Thị Tối Thiểu GC1',
            'is_patient': True,
            'catchment_province_id': cls.province.id,
            'mobile': '+84 913 111 222',
            'birth_date': '1949-03-11',
            'gender_id': _gender(env, 'female').id,
        })

        # A minimally-scoped service user: ONE healthcare group, nothing from
        # accounting/settings. This is the shape of an external partner's
        # token user, and the shape that G14 broke.
        cls.receptionist = new_test_user(
            env, login='gc1_reception',
            groups='health_base.group_healthcare_receptionist')
        cls.receptionist.catchment_province_id = cls.province.id

        cls.nurse = new_test_user(
            env, login='gc1_nurse',
            groups='health_base.group_healthcare_nurse')
        cls.nurse.catchment_province_id = cls.province.id

        # Morse 25 + 15 + 20 = 60 → risk_level 'high', which is the Flag
        # serializer's base_domain.
        cls.fall_risk = env['health.fall.risk'].create({
            'patient_id': cls.patient.id,
            'history_of_falling': True,
            'secondary_diagnosis': True,
            'iv_therapy': True,
        })

    def _validate(self, resource_dict):
        try:
            return validate_resource(resource_dict)
        except ImportError:
            self.skipTest('fhir.resources is not installed in this environment')

    # ==================================================================
    # T1.1 / T1.2 — D1: minimal-privilege Patient read (G14)
    # ==================================================================

    def test_11_minimal_privilege_patient_serializes(self):
        """A user with ONLY group_healthcare_receptionist can serialize a
        Patient. Before D1 this raised AccessError, because the blanket
        stored-field prefetch pulled res.partner's group-gated accounting
        fields (credit_limit, signup_type) into the same read."""
        env = self.env(user=self.receptionist)
        serializer = REGISTRY['Patient']
        record = serializer.read_record(env, self.patient.id)
        self.assertTrue(record, 'record rules hid the patient from the '
                                'minimal-privilege user — fixture problem')
        resource = serializer.serialize_batch(record)[0]
        self.assertEqual(resource['resourceType'], 'Patient')
        self.assertEqual(resource['id'], str(self.patient.id))
        self.assertEqual(resource['name'][0]['text'], 'Lê Thị Tối Thiểu GC1')
        self._validate(resource)

    def test_12_minimal_privilege_patient_search_bundle(self):
        env = self.env(user=self.receptionist)
        bundle, records = REGISTRY['Patient'].search_bundle(
            env, {'name': ['Lê Thị Tối Thiểu']}, 'http://test')
        self.assertEqual(bundle['resourceType'], 'Bundle')
        self.assertEqual(bundle['type'], 'searchset')
        self.assertIn(self.patient.id, records.ids)
        ids = {entry['resource']['id'] for entry in bundle['entry']}
        self.assertIn(str(self.patient.id), ids)
        self._validate(bundle['entry'][0]['resource'])

    def test_13_prefetch_declaration_covers_every_mapped_field(self):
        """The prefetch list is a promise about what to_fhir reads; a field
        mapped but not declared would silently regress to a per-record query
        (or, worse, tempt someone to restore the blanket fetch)."""
        declared = set(REGISTRY['Patient'].prefetch_fields)
        for name in ('name', 'active', 'patient_code', 'insurance_number',
                     'phone', 'mobile', 'email', 'gender_id', 'birth_date',
                     'deceased', 'street', 'street2', 'city', 'zip',
                     'district_id', 'state_id', 'country_id',
                     'primary_facility_id', 'write_date'):
            self.assertIn(name, declared)
        # …and it must NOT re-admit the group-gated fields G14 was about.
        self.assertNotIn('credit_limit', declared)
        self.assertNotIn('signup_type', declared)

    # ==================================================================
    # T1.3 — D2: the Flag compartment is populated, not suppressed (G15)
    # ==================================================================

    def test_14_nurse_can_read_fall_risk(self):
        env = self.env(user=self.nurse)
        # No assertion on the count — the point is that it does not raise.
        env['health.fall.risk'].search_count([])
        self.assertTrue(
            env['health.fall.risk'].search([('id', '=', self.fall_risk.id)]),
            'the nurse ACL row did not make the fixture readable')

    def test_15_everything_contains_flag_and_declares_nothing_suppressed(self):
        env = self.env(user=self.nurse)
        bundle, _record = build_everything_bundle(
            env, self.patient.id, {}, 'http://test', enforced=False)
        by_type = {}
        for entry in bundle['entry']:
            by_type.setdefault(
                entry['resource']['resourceType'], []).append(entry['resource'])
        self.assertIn('Flag', by_type, 'the fall-risk compartment is empty — '
                                       'the ACL did not take effect')
        flag_ids = {resource['id'] for resource in by_type['Flag']}
        self.assertIn(str(self.fall_risk.id), flag_ids)
        suppressed = [
            resource for resource in by_type.get('OperationOutcome', [])
            if resource['issue'][0]['code'] == 'suppressed']
        for outcome in suppressed:
            self.assertNotIn(
                'Flag', outcome['issue'][0]['diagnostics'],
                'Flag is still declared as an authorization omission')

    # ==================================================================
    # T1.5 / T1.9 — A1: the capability declares what the server does
    # ==================================================================

    def _statement(self):
        clear_capability_cache()
        self.addCleanup(clear_capability_cache)
        return build_capability(self.env)

    def test_16_capability_declares_every_operation(self):
        statement = self._statement()
        entries = {r['type']: r for r in statement['rest'][0]['resource']}
        declared = {
            (rtype, operation['name'])
            for rtype, entry in entries.items()
            for operation in entry.get('operation', [])}
        self.assertIn(('Patient', 'everything'), declared)
        self.assertIn(('CodeSystem', 'lookup'), declared)
        self.assertIn(('ValueSet', 'expand'), declared)
        for _rtype, operation in [
                (r, o) for r, e in entries.items()
                for o in e.get('operation', [])]:
            self.assertTrue(
                operation['definition'].startswith(
                    'http://hl7.org/fhir/OperationDefinition/'),
                'operation %r has no canonical definition' % operation['name'])

    def test_17_valueset_is_operation_only(self):
        statement = self._statement()
        valueset = next(r for r in statement['rest'][0]['resource']
                        if r['type'] == 'ValueSet')
        self.assertNotIn('interaction', valueset,
                         'ValueSet has no serializer — declaring read/search '
                         'would be a lie')
        self.assertNotIn('searchParam', valueset)
        self.assertEqual([o['name'] for o in valueset['operation']], ['expand'])

    def test_18_count_is_not_a_search_param(self):
        statement = self._statement()
        for resource in statement['rest'][0]['resource']:
            names = [p['name'] for p in resource.get('searchParam', [])]
            self.assertNotIn(
                '_count', names,
                '%s declares the paging control _count as a SearchParameter'
                % resource['type'])
            if resource['type'] in REGISTRY:
                self.assertIn('_lastUpdated', names)

    def test_19_search_param_definitions_are_canonical(self):
        statement = self._statement()
        seen = 0
        for resource in statement['rest'][0]['resource']:
            for param in resource.get('searchParam', []):
                if 'definition' not in param:
                    continue
                seen += 1
                self.assertTrue(
                    param['definition'].startswith(SEARCH_PARAM_BASE),
                    '%s.%s definition %r is not an hl7.org SearchParameter '
                    'canonical' % (resource['type'], param['name'],
                                   param['definition']))
        self.assertGreater(seen, 0, 'no searchParam carries a definition')
        # spot-check the shared clinical canonicals actually landed
        observation = next(r for r in statement['rest'][0]['resource']
                           if r['type'] == 'Observation')
        by_name = {p['name']: p for p in observation['searchParam']}
        self.assertEqual(by_name['patient']['definition'],
                         SEARCH_PARAM_BASE + 'clinical-patient')
        self.assertEqual(by_name['code']['definition'],
                         SEARCH_PARAM_BASE + 'clinical-code')

    def test_20_statement_validates(self):
        self._validate(self._statement())

    # ==================================================================
    # T1.6 — A2: software element (G3)
    # ==================================================================

    def test_21_software_element_carries_the_deployed_version(self):
        statement = self._statement()
        self.assertEqual(statement['software']['name'], 'health19 / CarejioX')
        module = self.env['ir.module.module'].sudo().search(
            [('name', '=', 'health_fhir_core')], limit=1)
        self.assertEqual(statement['software']['version'],
                         module.latest_version)

    # ==================================================================
    # T1.7 — C2: the committed capability baseline (control with teeth)
    # ==================================================================

    def test_22_capability_matches_the_committed_baseline(self):
        with file_open(BASELINE_PATH) as handle:
            baseline = json.load(handle)
        self.assertNotIn(
            'date', baseline,
            'the baseline must not pin a generation timestamp')
        current = _normalized(self._statement())
        self.assertEqual(
            current, _normalized(baseline),
            'The CapabilityStatement no longer matches '
            '%s. This is control C2 doing its job: a capability change is '
            'only sanctioned by REGENERATING the baseline in the same commit '
            'as the code that changed it.' % BASELINE_PATH)

    # ==================================================================
    # T1.8 — C2: route ↔ capability diff, empty in BOTH directions
    # ==================================================================

    def test_23_routes_and_capability_agree(self):
        statement = self._statement()
        entries = {r['type']: r for r in statement['rest'][0]['resource']}

        routed_operations = set()
        routed_types = set()
        for rule in self.env['ir.http'].routing_map().iter_rules():
            path = rule.rule
            if not path.startswith('/fhir/r4/'):
                continue
            segments = [s for s in path[len('/fhir/r4/'):].split('/') if s]
            operation = next(
                (s for s in segments if s.startswith('$')), None)
            if operation is None:
                continue
            rtype = segments[0]
            self.assertNotIn(
                '<', rtype,
                'operation route %r does not name its resource type '
                'literally — the diff cannot check it' % path)
            routed_operations.add((rtype, operation[1:]))
            routed_types.add(rtype)

        declared_operations = {
            (rtype, operation['name'])
            for rtype, entry in entries.items()
            for operation in entry.get('operation', [])}

        self.assertEqual(
            routed_operations, declared_operations,
            'route/capability operation diff is not empty: routed-only=%s '
            'declared-only=%s' % (sorted(routed_operations - declared_operations),
                                  sorted(declared_operations - routed_operations)))
        # sanity: the three we know about
        self.assertEqual(routed_operations, {
            ('Patient', 'everything'),
            ('CodeSystem', 'lookup'),
            ('ValueSet', 'expand')})

        # every REGISTRY type has an interaction-bearing entry, and every
        # interaction-bearing entry is in REGISTRY (no phantom resources)
        interaction_types = {rtype for rtype, entry in entries.items()
                             if 'interaction' in entry}
        self.assertEqual(interaction_types, set(REGISTRY))

        # operation-only entries carry no interaction and are not in REGISTRY
        for rtype, entry in entries.items():
            if 'interaction' in entry:
                continue
            self.assertNotIn(rtype, REGISTRY)
            self.assertTrue(entry.get('operation'),
                            '%s declares neither interaction nor operation'
                            % rtype)

    # ==================================================================
    # A3 — the R4B pin resolves as documented (G11)
    # ==================================================================

    def test_24_fhir_resources_pin_resolves(self):
        try:
            module = importlib.import_module('fhir.resources.R4B.patient')
        except ImportError:
            self.skipTest('fhir.resources is not installed in this environment')
        self.assertTrue(hasattr(module, 'Patient'))
        version = importlib.metadata.version('fhir.resources')
        self.assertTrue(
            version.startswith('8.'),
            'fhir.resources resolved to %s; docs/conformance/'
            'r4-r4b-equivalence.md and requirements-fhir.txt pin 8.3.0, and '
            'the R4/R4B equivalence claim is scoped to that model set'
            % version)
