# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


def _get_fixture(env):
    """Patient partners REQUIRE catchment_province_id; FSOs REQUIRE
    facility_id + patient_id + scheduled_datetime. Search existing
    province/facility first, create fallback."""
    Partner = env['res.partner']
    Facility = env['health.facility']

    province = env['health.catchment.province'].search([], limit=1)
    if not province:
        province = env['health.catchment.province'].create({
            'name': 'Test Vitals Province',
            'code': 'TVP',
        })
    facility = Facility.search(
        [('catchment_province_id', '=', province.id)], limit=1)
    if not facility:
        facility = Facility.create({
            'name': 'Test Vitals Facility',
            'code': 'TVF',
            'street': '1 Vitals Street',
            'city': 'Test City',
            'catchment_province_id': province.id,
        })
    patient = Partner.create({
        'name': 'Vitals Test Patient',
        'is_patient': True,
        'catchment_province_id': province.id,
        'primary_facility_id': facility.id,
    })
    return province, facility, patient


@tagged('post_install', '-at_install')
class TestHealthVitals(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.province, cls.facility, cls.patient = _get_fixture(cls.env)
        cls.Observation = cls.env['health.observation']
        cls.Type = cls.env['health.vitals.type']
        cls.Threshold = cls.env['health.vitals.threshold']
        cls.type_hr = cls.env.ref('health_vitals.vitals_type_heart_rate')
        cls.type_weight = cls.env.ref('health_vitals.vitals_type_weight')
        # Facility manager with a linked user (activity escalation
        # target); reuse the running user's employee when present.
        employee = cls.env.user.employee_id
        if not employee:
            employee = cls.env['hr.employee'].create({
                'name': 'Vitals Test Manager',
                'user_id': cls.env.user.id,
            })
            cls.env.user.invalidate_recordset()
        cls.facility.facility_manager_id = employee

    def _make_fso(self):
        return self.env['health.fieldservice.order'].create({
            'patient_id': self.patient.id,
            'facility_id': self.facility.id,
            'scheduled_datetime': fields.Datetime.now() + timedelta(days=1),
        })

    # ------------------------------------------------------------------
    # Catalog seeds (acceptance #1)
    # ------------------------------------------------------------------
    def test_seed_catalog(self):
        types = self.Type.with_context(active_test=False).search([])
        self.assertGreaterEqual(len(types), 13)
        loinc_codes = types.mapped('loinc_code')
        self.assertEqual(len(loinc_codes), len(set(loinc_codes)),
                         'LOINC codes must be unique')
        bp_panel = self.env.ref('health_vitals.vitals_type_bp_panel')
        self.assertEqual(bp_panel.value_type, 'panel')
        self.assertEqual(
            set(bp_panel.child_ids.mapped('code')), {'bp_sys', 'bp_dia'})
        self.assertEqual(self.type_hr.loinc_code, '8867-4')

    def test_get_by_code(self):
        self.assertEqual(self.Type.get_by_code('8867-4'), self.type_hr)
        # Internal short codes resolve through the same entry point.
        self.assertEqual(self.Type.get_by_code('hr'), self.type_hr)
        self.assertFalse(self.Type.get_by_code('nope-0'))

    # ------------------------------------------------------------------
    # create_coded public interface
    # ------------------------------------------------------------------
    def test_create_coded(self):
        fso = self._make_fso()
        observation = self.Observation.create_coded(
            self.patient.id, '8867-4', 82, fso_id=fso.id,
            note='post-exercise')
        self.assertEqual(observation.vitals_type_id, self.type_hr)
        self.assertEqual(observation.value_quantity, 82)
        self.assertEqual(observation.order_id, fso)
        self.assertEqual(observation.state, 'final')
        self.assertEqual(observation.loinc_code, '8867-4')
        self.assertEqual(
            observation.catchment_province_id, self.province)
        self.assertEqual(fso.observation_count, 1)

    def test_create_coded_unknown_code(self):
        with self.assertRaises(UserError):
            self.Observation.create_coded(self.patient.id, '0000-0', 1)

    # ------------------------------------------------------------------
    # Plausible range (acceptance #3 — seed range 20-300 for HR)
    # ------------------------------------------------------------------
    def test_plausible_range(self):
        observation = self.Observation.create({
            'client_id': self.patient.id,
            'vitals_type_id': self.type_hr.id,
            'value_quantity': 180,
        })
        self.assertEqual(observation.value_quantity, 180)
        with self.assertRaises(ValidationError):
            self.Observation.create({
                'client_id': self.patient.id,
                'vitals_type_id': self.type_hr.id,
                'value_quantity': 350,
            })

    # ------------------------------------------------------------------
    # BP panel (acceptance #2)
    # ------------------------------------------------------------------
    def test_create_panel(self):
        fso = self._make_fso()
        panel = self.Observation.create_panel(
            self.patient.id, 'bp_panel',
            [{'code': 'bp_sys', 'value': 120},
             {'code': 'bp_dia', 'value': 80}],
            order_id=fso.id, body_position='sitting')
        self.assertEqual(panel.vitals_type_id.code, 'bp_panel')
        self.assertEqual(len(panel.child_ids), 2)
        values = {child.vitals_type_id.code: child.value_quantity
                  for child in panel.child_ids}
        self.assertEqual(values, {'bp_sys': 120.0, 'bp_dia': 80.0})
        self.assertTrue(all(
            child.parent_id == panel for child in panel.child_ids))
        self.assertTrue(all(
            child.order_id == fso for child in panel.child_ids))

    # ------------------------------------------------------------------
    # Thresholds + escalation (acceptance #4)
    # ------------------------------------------------------------------
    def test_threshold_critical_activity(self):
        self.Threshold.create({
            'client_id': self.patient.id,
            'vitals_type_id': self.type_hr.id,
            'severity': 'critical',
            'max_value': 120,
            'escalation_action': 'activity',
        })
        before = self.env['mail.activity'].search_count(
            [('res_model', '=', 'res.partner'),
             ('res_id', '=', self.patient.id)])
        observation = self.Observation.create({
            'client_id': self.patient.id,
            'vitals_type_id': self.type_hr.id,
            'value_quantity': 130,
        })
        self.assertTrue(observation.is_abnormal)
        self.assertEqual(observation.alert_level, 'critical')
        after = self.env['mail.activity'].search_count(
            [('res_model', '=', 'res.partner'),
             ('res_id', '=', self.patient.id)])
        self.assertEqual(after, before + 1)

    def test_threshold_not_breached(self):
        self.Threshold.create({
            'client_id': self.patient.id,
            'vitals_type_id': self.type_hr.id,
            'severity': 'warning',
            'max_value': 100,
            'escalation_action': 'none',
        })
        observation = self.Observation.create({
            'client_id': self.patient.id,
            'vitals_type_id': self.type_hr.id,
            'value_quantity': 90,
        })
        self.assertFalse(observation.is_abnormal)
        self.assertEqual(observation.alert_level, 'none')

    def test_threshold_needs_bound(self):
        with self.assertRaises(ValidationError):
            self.Threshold.create({
                'client_id': self.patient.id,
                'vitals_type_id': self.type_hr.id,
                'severity': 'warning',
                'escalation_action': 'none',
            })

    # ------------------------------------------------------------------
    # Trend (acceptance #5) + entered-in-error exclusion (#7)
    # ------------------------------------------------------------------
    def test_get_trend_excludes_entered_in_error(self):
        base = fields.Datetime.now()
        weights = []
        for offset, value in enumerate((70.0, 71.0, 72.0)):
            weights.append(self.Observation.create({
                'client_id': self.patient.id,
                'vitals_type_id': self.type_weight.id,
                'value_quantity': value,
                'effective_datetime': base - timedelta(days=3 - offset),
            }))
        weights[1].action_mark_entered_in_error()
        trend = self.Observation.get_trend(
            self.patient.id, self.type_weight.id)
        self.assertEqual([point['value'] for point in trend], [70.0, 72.0])

    # ------------------------------------------------------------------
    # Append-only discipline (acceptance #7, #8)
    # ------------------------------------------------------------------
    def test_unlink_guard(self):
        observation = self.Observation.create({
            'client_id': self.patient.id,
            'vitals_type_id': self.type_hr.id,
            'value_quantity': 80,
        })
        nurse_group = self.env.ref('health_base.group_healthcare_nurse')
        nurse_user = self.env['res.users'].create({
            'name': 'Vitals Nurse',
            'login': 'vitals_nurse_test',
            'group_ids': [(6, 0, [
                self.env.ref('base.group_user').id, nurse_group.id])],
        })
        with self.assertRaises(UserError):
            observation.with_user(nurse_user).unlink()
        observation.action_mark_entered_in_error()
        self.assertEqual(observation.state, 'entered_in_error')
        with self.assertRaises(UserError):
            observation.action_mark_entered_in_error()

    def test_amend_on_value_write(self):
        observation = self.Observation.create({
            'client_id': self.patient.id,
            'vitals_type_id': self.type_hr.id,
            'value_quantity': 80,
        })
        self.assertEqual(observation.state, 'final')
        observation.write({'value_quantity': 85})
        self.assertEqual(observation.state, 'amended')
        # Amended rows still count for trends.
        trend = self.Observation.get_trend(
            self.patient.id, self.type_hr.id)
        self.assertIn(85.0, [point['value'] for point in trend])

    def test_amend_reevaluates_thresholds(self):
        self.Threshold.create({
            'client_id': self.patient.id,
            'vitals_type_id': self.type_hr.id,
            'severity': 'warning',
            'max_value': 100,
            'escalation_action': 'none',
        })
        observation = self.Observation.create({
            'client_id': self.patient.id,
            'vitals_type_id': self.type_hr.id,
            'value_quantity': 110,
        })
        self.assertEqual(observation.alert_level, 'warning')
        observation.write({'value_quantity': 90})
        self.assertEqual(observation.state, 'amended')
        self.assertEqual(observation.alert_level, 'none')
        self.assertFalse(observation.is_abnormal)

    # ------------------------------------------------------------------
    # Clinical note sidecar (acceptance #6)
    # ------------------------------------------------------------------
    def test_clinical_note_structured_flag(self):
        fso = self._make_fso()
        note = self.env['health.clinical.note'].create({
            'order_id': fso.id,
            'vital_signs': 'BP 120/80, afebrile',
        })
        self.assertFalse(note.has_structured_vitals)
        self.Observation.create({
            'client_id': self.patient.id,
            'vitals_type_id': self.type_hr.id,
            'value_quantity': 76,
            'order_id': fso.id,
            'clinical_note_id': note.id,
        })
        self.assertTrue(note.has_structured_vitals)
        # Free-text stays untouched (coding-sidecar pattern).
        self.assertEqual(note.vital_signs, 'BP 120/80, afebrile')

    def test_client_derived_from_note(self):
        fso = self._make_fso()
        note = self.env['health.clinical.note'].create({
            'order_id': fso.id,
        })
        observation = self.Observation.create({
            'vitals_type_id': self.type_hr.id,
            'value_quantity': 76,
            'clinical_note_id': note.id,
        })
        self.assertEqual(observation.client_id, self.patient)
