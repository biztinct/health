# -*- coding: utf-8 -*-
import uuid
from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

BARTHEL_INDEPENDENT = {
    'feeding': 'independent',
    'bathing': 'independent',
    'grooming': 'independent',
    'dressing': 'independent',
    'bowels': 'continent',
    'bladder': 'continent',
    'toilet_use': 'independent',
    'transfers': 'independent',
    'mobility': 'independent',
    'stairs': 'independent',
}


def _get_fixture(env):
    """Patient partners REQUIRE catchment_province_id; FSOs REQUIRE
    facility_id + patient_id + scheduled_datetime. Search existing
    province/facility first, create fallback."""
    province = env['health.catchment.province'].search([], limit=1)
    if not province:
        province = env['health.catchment.province'].create({
            'name': 'Test Forms Province',
            'code': 'TFP',
        })
    facility = env['health.facility'].search(
        [('catchment_province_id', '=', province.id)], limit=1)
    if not facility:
        facility = env['health.facility'].create({
            'name': 'Test Forms Facility',
            'code': 'TFPF',
            'street': '1 Forms Street',
            'city': 'Test City',
            'catchment_province_id': province.id,
        })
    patient = env['res.partner'].create({
        'name': 'Forms Test Patient',
        'is_patient': True,
        'catchment_province_id': province.id,
        'primary_facility_id': facility.id,
    })
    return province, facility, patient


@tagged('post_install', '-at_install')
class TestHealthForms(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.province, cls.facility, cls.patient = _get_fixture(cls.env)
        cls.Template = cls.env['health.form.template']
        cls.Instance = cls.env['health.form.instance']
        cls.barthel = cls.env.ref('health_forms.form_template_barthel')
        cls.pain = cls.env.ref('health_forms.form_template_pain')

    def _make_fso(self):
        return self.env['health.fieldservice.order'].create({
            'patient_id': self.patient.id,
            'facility_id': self.facility.id,
            'scheduled_datetime': fields.Datetime.now() + timedelta(days=1),
        })

    def _make_instance(self, template, answers, **extra):
        vals = {
            'template_id': template.id,
            'client_id': self.patient.id,
            'answers_json': answers,
        }
        vals.update(extra)
        return self.Instance.create(vals)

    # ------------------------------------------------------------------
    # AC1 — seeds & schema shape
    # ------------------------------------------------------------------
    def test_01_seeds(self):
        codes = ['PAIN', 'BARTHEL', 'MNA_SF', 'BRADEN', 'AMTS']
        for code in codes:
            template = self.Template.search([
                ('code', '=', code), ('version', '=', 1)])
            self.assertEqual(len(template), 1, 'Missing seed %s' % code)
            self.assertEqual(template.state, 'published')
            schema = template.schema_json
            self.assertEqual(schema['code'], code)
            self.assertEqual(schema['version'], 1)
            self.assertTrue(schema['title_vi'])
            self.assertTrue(schema['questions'])
            for question in schema['questions']:
                self.assertRegex(question['key'], r'^[a-z][a-z0-9_]*$')
                if question['type'] in ('selection', 'boolean'):
                    self.assertTrue(question['options'])
            self.assertEqual(schema['scoring']['method'], 'sum')
            self.assertTrue(schema['scoring']['bands'])
        for type_code in ('barthel_total', 'mna_sf_total',
                          'braden_total', 'amts_total'):
            self.assertTrue(self.env['health.vitals.type'].search(
                [('code', '=', type_code)], limit=1),
                'Missing assessment vitals type %s' % type_code)

    # ------------------------------------------------------------------
    # AC2 — immutability + versioning + snapshot pinning
    # ------------------------------------------------------------------
    def test_02_published_immutable_and_new_version(self):
        with self.assertRaises(UserError):
            self.barthel.write({'scoring_method': 'none'})
        with self.assertRaises(UserError):
            self.barthel.question_ids[0].write({'label': 'Changed'})
        action = self.barthel.action_new_version()
        new_template = self.Template.browse(action['res_id'])
        self.assertEqual(new_template.state, 'draft')
        self.assertEqual(new_template.version, 2)
        self.assertEqual(new_template.predecessor_id, self.barthel)
        self.assertEqual(len(new_template.question_ids),
                         len(self.barthel.question_ids))
        # Instances keep rendering from their own snapshot after retire.
        instance = self._make_instance(self.barthel, BARTHEL_INDEPENDENT)
        instance.action_complete()
        self.barthel.action_retire()
        self.assertEqual(instance.schema_snapshot['code'], 'BARTHEL')
        self.assertEqual(len(instance.schema_snapshot['questions']), 10)
        new_template.unlink()

    # ------------------------------------------------------------------
    # AC3 — scoring + required guard
    # ------------------------------------------------------------------
    def test_03_barthel_scoring(self):
        instance = self._make_instance(self.barthel, BARTHEL_INDEPENDENT)
        instance.action_complete()
        self.assertEqual(instance.total_score, 100.0)
        self.assertEqual(instance.score_label, 'Independent/mild')
        self.assertEqual(instance.score_label_vi, 'Độc lập/nhẹ')
        self.assertEqual(instance.state, 'completed')

        partial = dict(BARTHEL_INDEPENDENT)
        partial.pop('stairs')
        blocked = self._make_instance(self.barthel, partial)
        with self.assertRaises(UserError):
            blocked.action_complete()

    def test_03b_number_bounds(self):
        instance = self._make_instance(self.pain, {'pain_score': 15})
        with self.assertRaises(UserError):
            instance.action_complete()
        instance.answers_json = {'pain_score': 7}
        instance.action_complete()
        self.assertEqual(instance.total_score, 7.0)
        self.assertEqual(instance.score_label, 'Severe')

    # ------------------------------------------------------------------
    # AC4 — observation extraction
    # ------------------------------------------------------------------
    def test_04_extraction(self):
        fso = self._make_fso()
        instance = self._make_instance(
            self.barthel, BARTHEL_INDEPENDENT, order_id=fso.id)
        instance.action_complete()
        totals = instance.observation_ids.filtered(
            lambda o: o.vitals_type_id.code == 'barthel_total')
        self.assertEqual(len(totals), 1)
        self.assertEqual(totals.value_quantity, 100.0)
        self.assertEqual(totals.form_instance_id, instance)

        pain = self._make_instance(self.pain, {'pain_score': 8})
        pain.action_complete()
        pain_obs = pain.observation_ids.filtered(
            lambda o: o.loinc_code == '72514-3')
        self.assertTrue(pain_obs)
        self.assertIn(8.0, pain_obs.mapped('value_quantity'))

    # ------------------------------------------------------------------
    # AC5 — amendment re-scores and re-extracts
    # ------------------------------------------------------------------
    def test_05_amendment(self):
        instance = self._make_instance(self.barthel, BARTHEL_INDEPENDENT)
        instance.action_complete()
        previous = instance.observation_ids
        amended = dict(BARTHEL_INDEPENDENT, feeding='unable')
        instance.write({'answers_json': amended})
        self.assertEqual(instance.state, 'amended')
        self.assertEqual(instance.total_score, 90.0)
        self.assertTrue(all(
            o.state == 'entered_in_error' for o in previous))
        fresh = instance.observation_ids.filtered(
            lambda o: o.state != 'entered_in_error'
            and o.vitals_type_id.code == 'barthel_total')
        self.assertEqual(fresh.value_quantity, 90.0)

    # ------------------------------------------------------------------
    # AC7 — visible_if hides, exempts required, unscores
    # ------------------------------------------------------------------
    def test_07_visible_if(self):
        template = self.Template.create({
            'name': 'Conditional Test',
            'code': 'COND_TEST',
            'scoring_method': 'sum',
            'scoring_bands_json': [
                {'min': 0, 'max': 100, 'label': 'Any',
                 'label_vi': 'Bất kỳ', 'color': '#1B6E20'},
            ],
            'question_ids': [
                (0, 0, {'key': 'has_pain', 'question_type': 'boolean',
                        'label': 'Has pain?', 'required': True,
                        'options_json': [
                            {'value': 'true', 'label': 'Yes', 'score': 1},
                            {'value': 'false', 'label': 'No', 'score': 0},
                        ]}),
                (0, 0, {'key': 'pain_level', 'question_type': 'number',
                        'label': 'Pain level', 'required': True,
                        'min_value': 0, 'max_value': 10,
                        'score_weight': 1.0,
                        'visible_if_json': {
                            'key': 'has_pain', 'operator': '=',
                            'value': True}}),
            ],
        })
        template.action_publish()
        # Hidden: required exemption + no score contribution.
        instance = self._make_instance(template, {'has_pain': False})
        instance.action_complete()
        self.assertEqual(instance.total_score, 0.0)
        # Visible: required enforced.
        blocked = self._make_instance(template, {'has_pain': True})
        with self.assertRaises(UserError):
            blocked.action_complete()
        answered = self._make_instance(
            template, {'has_pain': True, 'pain_level': 5})
        answered.action_complete()
        self.assertEqual(answered.total_score, 6.0)

    # ------------------------------------------------------------------
    # AC8 — service-type applicability
    # ------------------------------------------------------------------
    def test_08_service_filtering(self):
        service = self.env['health.service.type'].search([], limit=1)
        if not service:
            service = self.env['health.service.type'].create({
                'name': 'Forms Test Service', 'code': 'FTS'})
        scoped = self.Template.create({
            'name': 'Scoped Form',
            'code': 'SCOPED_TEST',
            'scoring_method': 'none',
            'service_type_ids': [(6, 0, service.ids)],
            'question_ids': [
                (0, 0, {'key': 'note', 'question_type': 'text',
                        'label': 'Note'})],
        })
        scoped.action_publish()
        all_schemas = self.Template.get_templates_for_service()
        self.assertIn('SCOPED_TEST',
                      [schema['code'] for schema in all_schemas])
        matching = self.Template.get_templates_for_service(service.ids)
        self.assertIn('SCOPED_TEST',
                      [schema['code'] for schema in matching])
        # Universal templates (empty m2m) always apply.
        self.assertIn('BARTHEL', [schema['code'] for schema in matching])

    # ------------------------------------------------------------------
    # AC6/AC10 adjacent — client_uuid idempotency & guards
    # ------------------------------------------------------------------
    def test_09_client_uuid_unique(self):
        key = str(uuid.uuid4())
        self._make_instance(
            self.pain, {'pain_score': 3}, client_uuid=key)
        with self.assertRaises(Exception):
            self._make_instance(
                self.pain, {'pain_score': 4}, client_uuid=key)

    def test_10_completed_no_unlink(self):
        instance = self._make_instance(self.pain, {'pain_score': 2})
        instance.action_complete()
        nurse_group = self.env.ref('health_base.group_healthcare_nurse')
        nurse = self.env['res.users'].create({
            'name': 'Forms Test Nurse',
            'login': 'forms_test_nurse_%s' % uuid.uuid4().hex[:8],
            'group_ids': [(6, 0, [
                self.env.ref('base.group_user').id, nurse_group.id])],
            'catchment_province_id': self.province.id,
        })
        with self.assertRaises(UserError):
            instance.with_user(nurse).unlink()
        with self.assertRaises(UserError):
            instance.with_user(nurse).action_cancel()
