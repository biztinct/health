# -*- coding: utf-8 -*-
"""Phase GC-2 — spec-grade search behaviour (register item G17).

Two families of defect are covered here, both of which a real client hits on
day one and neither of which the structural tests could see:

- **token syntax** (§3.1): FHIR sends `system|code`, `|code` or a bare `code`
  for every token param. The facade used to match the raw string, so
  `code=http://loinc.org|8867-4` — a perfectly conformant query — returned
  nothing. A token whose explicit system does not match the param's system is
  ZERO MATCHES, not an error (R4 §3.1.1.6.3).
- **string semantics** (§3.2): a FHIR `string` param defaults to
  case-insensitive STARTS-WITH; substring is `:contains` and exact is
  `:exact`. The facade defaulted to substring, which silently over-matches.

Every assertion is written against THIS suite's own fixtures (`assertIn` /
`assertNotIn` on ids), never against a result-set size — vietuat carries live
patients whose names collide with any realistic search term (§5.50).
"""

from odoo.tests import TransactionCase, tagged

from odoo.addons.health_fhir_core.serializers import REGISTRY
from odoo.addons.health_fhir_core.serializers.base import (
    FHIRBadRequest, FHIRNotSupported, LOINC_SYSTEM, escape_like,
    string_param_domain, token_domain, token_status_domain,
)

IMPOSSIBLE = [('id', '=', 0)]
OBSERVATION_STATUS_SYSTEM = 'http://hl7.org/fhir/observation-status'


@tagged('post_install', '-at_install')
class TestFHIRSearchGC2(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env

        cls.province = env['health.catchment.province'].search([], limit=1)
        if not cls.province:
            cls.province = env['health.catchment.province'].create({
                'name': 'GC2 Province'})
        cls.facility = env['health.facility'].search(
            [('catchment_province_id', '=', cls.province.id)], limit=1)
        if not cls.facility:
            cls.facility = env['health.facility'].create({
                'name': 'GC2 Facility', 'code': 'GC2TST',
                'catchment_province_id': cls.province.id})

        def patient(name):
            return env['res.partner'].create({
                'name': name, 'is_patient': True,
                'catchment_province_id': cls.province.id,
                'primary_facility_id': cls.facility.id})

        # Neither name STARTS WITH "Văn" — that is the point of T2.2: under
        # the spec default a middle-name search matches nobody, and the caller
        # must ask for `:contains` to get the old behaviour.
        cls.p_nguyen = patient('Nguyễn Văn Alpha GC2')
        cls.p_tran = patient('Trần Văn Bravo GC2')
        # LIKE-wildcard escaping: without escaping, `%` in the search value
        # would match p_wild_x too.
        cls.p_wild = patient('Percent%Escape GC2')
        cls.p_wild_x = patient('PercentXEscape GC2')

        cls.observation = env['health.observation'].create_coded(
            cls.p_nguyen.id, '8867-4', 72)

    # ==================================================================
    # T2.1 — token `system|code`
    # ==================================================================

    def _obs_search(self, value):
        records, _total, _cursor = REGISTRY['Observation'].search_records(
            self.env, {'code': [value]})
        return records

    def test_31_token_bare_system_and_pipe_forms_match(self):
        for value in ('8867-4', '%s|8867-4' % LOINC_SYSTEM, '|8867-4'):
            self.assertIn(
                self.observation, self._obs_search(value),
                'Observation.code=%r did not match the fixture' % value)

    def test_32_token_wrong_system_is_zero_matches_not_an_error(self):
        """R4 §3.1.1.6.3: an explicit system that does not match yields no
        results — it is NOT a 400. The domain is impossible, so the search
        stays cheap and the Bundle is simply empty."""
        translate = REGISTRY['Observation'].search_params['code']['domain']
        self.assertEqual(translate('http://snomed.info/sct|8867-4'), IMPOSSIBLE)
        self.assertNotIn(
            self.observation, self._obs_search('http://snomed.info/sct|8867-4'))

    def test_33_token_helper_grammar(self):
        """The kernel helper itself, away from any model."""
        bare = token_domain('field')
        self.assertEqual(bare('x'), [('field', '=', 'x')])
        self.assertEqual(bare('  x  '), [('field', '=', 'x')])
        self.assertEqual(bare('|x'), [('field', '=', 'x')])
        # no system_uri declared → any explicit system is accepted
        self.assertEqual(bare('urn:any|x'), [('field', '=', 'x')])
        scoped = token_domain('field', 'urn:right')
        self.assertEqual(scoped('urn:right|x'), [('field', '=', 'x')])
        self.assertEqual(scoped('urn:wrong|x'), IMPOSSIBLE)
        self.assertEqual(scoped('|x'), [('field', '=', 'x')])
        self.assertEqual(scoped('x'), [('field', '=', 'x')])

    def test_34_status_params_accept_the_token_syntax(self):
        """Status params reverse a map into ('state','in',[…]) so they cannot
        use token_domain directly — token_status_domain adapts them, and an
        unknown status is still a strict 400 through the wrapper."""
        translate = REGISTRY['Observation'].search_params['status']['domain']
        self.assertEqual(translate('final'), [('state', '=', 'final')])
        self.assertEqual(translate('%s|final' % OBSERVATION_STATUS_SYSTEM),
                         [('state', '=', 'final')])
        self.assertEqual(translate('|final'), [('state', '=', 'final')])
        with self.assertRaises(FHIRBadRequest):
            translate('not-a-status')
        with self.assertRaises(FHIRBadRequest):
            translate('urn:x|not-a-status')

        # the other status shape: one FHIR code → several Odoo states
        encounter = REGISTRY['Encounter'].search_params['status']['domain']
        self.assertEqual(encounter('finished'), encounter('|finished'))
        self.assertEqual(encounter('finished'),
                         encounter('urn:whatever|finished'))
        self.assertEqual(encounter('finished')[0][0], 'state')

        # …and the wrapper still refuses a non-matching explicit system when
        # one is declared
        scoped = token_status_domain(lambda code: [('state', '=', code)],
                                     'urn:right')
        self.assertEqual(scoped('urn:wrong|x'), IMPOSSIBLE)
        self.assertEqual(scoped('urn:right|x'), [('state', '=', 'x')])

    def test_35_status_search_still_finds_records(self):
        records, _total, _cursor = REGISTRY['Observation'].search_records(
            self.env, {'patient': ['Patient/%s' % self.p_nguyen.id],
                       'status': ['|final']})
        self.assertIn(self.observation, records)

    # ==================================================================
    # T2.2 — string params: starts-with default, :contains, :exact
    # ==================================================================

    def _patient_search(self, params):
        records, _total, _cursor = REGISTRY['Patient'].search_records(
            self.env, params)
        return records

    def test_36_string_default_is_starts_with(self):
        starts = self._patient_search({'name': ['Nguyễn Văn Alpha']})
        self.assertIn(self.p_nguyen, starts)
        self.assertNotIn(self.p_tran, starts)
        # "Văn" is a MIDDLE name in both fixtures — the spec default is
        # starts-with, so it matches neither (this is the behaviour change).
        middle = self._patient_search({'name': ['Văn Alpha GC2']})
        self.assertNotIn(self.p_nguyen, middle)
        self.assertNotIn(self.p_tran, middle)

    def test_37_contains_modifier_restores_substring(self):
        found = self._patient_search({'name:contains': ['Văn']})
        self.assertIn(self.p_nguyen, found)
        self.assertIn(self.p_tran, found)

    def test_38_exact_modifier_is_case_sensitive(self):
        exact = self._patient_search({'name:exact': ['Nguyễn Văn Alpha GC2']})
        self.assertIn(self.p_nguyen, exact)
        self.assertNotIn(self.p_tran, exact)
        # exact means exact: a lowercased value matches nothing…
        self.assertNotIn(
            self.p_nguyen,
            self._patient_search({'name:exact': ['nguyễn văn alpha gc2']}))
        # …and so does a prefix.
        self.assertNotIn(
            self.p_nguyen,
            self._patient_search({'name:exact': ['Nguyễn Văn Alpha']}))

    def test_39_like_wildcards_in_the_value_are_escaped(self):
        """A `%` a caller sends is DATA, not a wildcard — otherwise
        `name=A%` is a full-table scan dressed up as a search."""
        self.assertEqual(escape_like('a%b_c\\d'), 'a\\%b\\_c\\\\d')
        found = self._patient_search({'name': ['Percent%E']})
        self.assertIn(self.p_wild, found)
        self.assertNotIn(self.p_wild_x, found)

    def test_40_string_domain_shapes(self):
        translate = string_param_domain('name')
        self.assertEqual(translate('Lê'), [('name', '=ilike', 'Lê%')])
        self.assertEqual(translate('Lê', 'contains'), [('name', 'ilike', 'Lê')])
        self.assertEqual(translate('Lê', 'exact'), [('name', '=', 'Lê')])
        # every string param in the registry goes through the same factory
        for rtype, serializer in REGISTRY.items():
            for name, spec in serializer.search_params.items():
                if spec['type'] != 'string':
                    continue
                self.assertEqual(
                    spec['domain']('Z', 'exact')[0][1], '=',
                    '%s.%s is declared string but does not implement the '
                    'modifier contract' % (rtype, name))

    # ==================================================================
    # T2.3 — anything else is a strict 400
    # ==================================================================

    def test_41_unknown_modifier_is_not_supported(self):
        serializer = REGISTRY['Patient']
        with self.assertRaises(FHIRNotSupported):
            serializer.build_domain(self.env, {'name:fuzzy': ['x']})
        with self.assertRaises(FHIRNotSupported):
            serializer.build_domain(self.env, {'name:missing': ['true']})

    def test_42_modifier_on_a_non_string_param_is_not_supported(self):
        serializer = REGISTRY['Patient']
        for param in ('identifier:exact', 'birthdate:contains',
                      '_lastUpdated:exact'):
            with self.assertRaises(FHIRNotSupported):
                serializer.build_domain(self.env, {param: ['x']})
        with self.assertRaises(FHIRNotSupported):
            REGISTRY['Observation'].build_domain(
                self.env, {'status:exact': ['final']})

    def test_43_reserved_params_are_still_exact(self):
        """`_count` is skipped by name; `_count:foo` is NOT `_count`, and
        strict handling means it must not be silently swallowed."""
        serializer = REGISTRY['Patient']
        self.assertEqual(
            serializer.build_domain(self.env, {'_count': ['5']}),
            serializer.base_domain(self.env))
        with self.assertRaises(FHIRNotSupported):
            serializer.build_domain(self.env, {'_count:exact': ['5']})
