# -*- coding: utf-8 -*-
"""eMAR acceptance tests (spec §3.10).

The external RxNorm interaction API is always mocked — tests must not
hit the network; the stored health.medication.interaction catalog
covers the major-interaction path (AC5).
"""
import uuid
from datetime import timedelta
from unittest.mock import patch

import pytz

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged

HCM_TZ = pytz.timezone('Asia/Ho_Chi_Minh')


def _get_fixture(env):
    """Patient partners REQUIRE catchment_province_id; FSOs REQUIRE
    facility_id + patient_id + scheduled_datetime. Search existing
    province/facility first, create fallback."""
    province = env['health.catchment.province'].search([], limit=1)
    if not province:
        province = env['health.catchment.province'].create({
            'name': 'Test eMAR Province',
            'code': 'TEP',
        })
    facility = env['health.facility'].search(
        [('catchment_province_id', '=', province.id)], limit=1)
    if not facility:
        facility = env['health.facility'].create({
            'name': 'Test eMAR Facility',
            'code': 'TEPF',
            'street': '1 eMAR Street',
            'city': 'Test City',
            'catchment_province_id': province.id,
        })
    patient = env['res.partner'].create({
        'name': 'eMAR Test Patient',
        'is_patient': True,
        'catchment_province_id': province.id,
        'primary_facility_id': facility.id,
    })
    return province, facility, patient


def _no_api(*args, **kwargs):
    """Mocked health.medication.safety.check_drug_interactions."""
    return []


@tagged('post_install', '-at_install')
class TestHealthEmar(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.province, cls.facility, cls.patient = _get_fixture(cls.env)
        cls.Order = cls.env['health.medication.order']
        cls.Admin = cls.env['health.medication.administration']
        suffix = uuid.uuid4().hex[:6]
        cls.med_para = cls.env['health.medication'].create({
            'name': 'EMAR Test Paracetamol %s' % suffix,
            'form': 'tablet',
            'strength': '500 mg',
        })
        cls.med_warfarin = cls.env['health.medication'].create({
            'name': 'EMAR Test Warfarin %s' % suffix,
        })
        cls.med_aspirin = cls.env['health.medication'].create({
            'name': 'EMAR Test Aspirin %s' % suffix,
        })
        cls.env['health.medication.interaction'].create({
            'medication1_id': cls.med_warfarin.id,
            'medication2_id': cls.med_aspirin.id,
            'severity': 'major',
            'description': 'Increased bleeding risk.',
        })

    def _make_order(self, medication=None, **extra):
        vals = {
            'client_id': self.patient.id,
            'medication_id': (medication or self.med_para).id,
            'dose_quantity': 1.0,
            'dose_unit': 'tablet',
            'route': 'oral',
            'frequency': 'od',
            'start_date': fields.Date.today() + timedelta(days=1),
        }
        vals.update(extra)
        return self.Order.create(vals)

    def _activate(self, order):
        with patch.object(
                type(self.env['health.medication.safety']),
                'check_drug_interactions', _no_api):
            order.action_activate()
        return order

    def _make_fso(self, dt=None):
        return self.env['health.fieldservice.order'].create({
            'patient_id': self.patient.id,
            'facility_id': self.facility.id,
            'scheduled_datetime': dt or (
                fields.Datetime.now() + timedelta(days=1)),
        })

    def _make_nurse(self):
        return self.env['res.users'].create({
            'name': 'eMAR Test Nurse',
            'login': 'emar_test_nurse_%s' % uuid.uuid4().hex[:8],
            'group_ids': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref('health_base.group_healthcare_nurse').id])],
            'catchment_province_id': self.province.id,
        })

    # ------------------------------------------------------------------
    # AC1 — activation guards + default schedule
    # ------------------------------------------------------------------
    def test_01_activation_requires_dosage(self):
        order = self.Order.create({
            'client_id': self.patient.id,
            'medication_id': self.med_para.id,
        })
        self.assertEqual(order.state, 'draft')
        self.assertTrue(order.name.startswith('MO'))
        with self.assertRaises(UserError):
            order.action_activate()
        order.write({
            'dose_quantity': 1.0,
            'dose_unit': 'tablet',
            'route': 'oral',
            'frequency': 'od',
            'start_date': fields.Date.today() + timedelta(days=1),
        })
        self._activate(order)
        self.assertEqual(order.state, 'active')
        slots = self.Admin.search([('order_id', '=', order.id)])
        # od default 08:00 — one slot per day across the 7-day horizon
        # (all in the future: start_date is tomorrow).
        self.assertEqual(len(slots), 7)
        self.assertTrue(all(s.state == 'planned' for s in slots))

    # ------------------------------------------------------------------
    # AC2 — custom admin_times, tz-aware, idempotent
    # ------------------------------------------------------------------
    def test_02_bd_custom_times_tz_and_idempotency(self):
        order = self._make_order(
            frequency='bd', admin_times='07:30,19:30')
        self._activate(order)
        slots = self.Admin.search(
            [('order_id', '=', order.id)], order='planned_datetime')
        self.assertEqual(len(slots), 14)  # 2/day * 7 days
        local_times = set()
        for slot in slots:
            local = pytz.utc.localize(
                slot.planned_datetime).astimezone(HCM_TZ)
            local_times.add(local.strftime('%H:%M'))
        self.assertEqual(local_times, {'07:30', '19:30'})
        # Regeneration is idempotent.
        order.action_generate_schedule()
        self.assertEqual(self.Admin.search_count(
            [('order_id', '=', order.id)]), 14)

    # ------------------------------------------------------------------
    # AC3 — FSO slot linking
    # ------------------------------------------------------------------
    def test_03_fso_linking(self):
        visit_dt = fields.Datetime.now() + timedelta(days=2)
        fso = self._make_fso(visit_dt)
        fso.write({'state': 'confirmed'})
        order = self._make_order(frequency='od')
        self._activate(order)
        linked = self.Admin.search([
            ('order_id', '=', order.id), ('fso_id', '=', fso.id)])
        self.assertTrue(linked, 'Slot on the visit date must link to FSO')
        for slot in linked:
            self.assertEqual(slot._get_local_date(), fso.scheduled_date)

    # ------------------------------------------------------------------
    # AC4 — refused needs a reason; recorded rows are append-only
    # ------------------------------------------------------------------
    def test_04_refused_reason_and_immutability(self):
        order = self._make_order(frequency='od')
        self._activate(order)
        slot = self.Admin.search(
            [('order_id', '=', order.id)], order='planned_datetime',
            limit=1)
        with self.assertRaises(Exception):
            slot.action_record_refused(False)
        reason = self.env.ref('health_emar.notgiven_reason_refused_client')
        nurse = self._make_nurse()
        slot.with_user(nurse).action_record_refused(
            reason.id, notes='Client declined')
        self.assertEqual(slot.state, 'refused')
        self.assertEqual(slot.nurse_id.id, nurse.id)
        self.assertEqual(slot.reason_id, reason)
        self.assertTrue(slot.actual_datetime)
        # Recorded ticks are append-only for nurses (notes stays open).
        with self.assertRaises(UserError):
            slot.with_user(nurse).write({'state': 'given'})
        with self.assertRaises(UserError):
            slot.with_user(nurse).write({'dose_given': 9})
        slot.with_user(nurse).write({'notes': 'follow-up noted'})
        with self.assertRaises(UserError):
            slot.with_user(nurse).unlink()
        # not_given-only reason cannot be used for refused.
        slot2 = self.Admin.search(
            [('order_id', '=', order.id), ('state', '=', 'planned')],
            limit=1)
        npo = self.env.ref('health_emar.notgiven_reason_npo')
        with self.assertRaises(Exception):
            slot2.action_record_refused(npo.id)

    # ------------------------------------------------------------------
    # AC5 — major interaction blocks activation until acknowledged
    # ------------------------------------------------------------------
    def test_05_major_interaction_gate(self):
        warfarin_order = self._make_order(medication=self.med_warfarin)
        self._activate(warfarin_order)
        aspirin_order = self._make_order(medication=self.med_aspirin)
        # Detection: the check itself reports the major interaction.
        check_vals = aspirin_order._run_interaction_check()
        self.assertEqual(check_vals.get('interaction_severity'), 'major')
        self.assertIn('bleeding', check_vals.get('interaction_warning', ''))
        # Activation is blocked while unacknowledged.
        with self.assertRaises(UserError):
            self._activate(aspirin_order)
        self.assertEqual(aspirin_order.state, 'draft')
        # In production the findings survive the rollback via a separate
        # cursor (_persist_interaction_result); assertRaises' savepoint
        # rollback makes that untestable here — simulate the persistence.
        aspirin_order.write(check_vals)
        self.assertEqual(aspirin_order.interaction_severity, 'major')
        aspirin_order.action_acknowledge_interaction()
        self.assertTrue(aspirin_order.interaction_ack)
        self.assertEqual(
            aspirin_order.interaction_ack_by_id, self.env.user)
        self._activate(aspirin_order)
        self.assertEqual(aspirin_order.state, 'active')

    # ------------------------------------------------------------------
    # AC6 — hold cancels future slots; resume regenerates them
    # ------------------------------------------------------------------
    def test_06_hold_resume(self):
        order = self._make_order(frequency='bd')
        self._activate(order)
        before = self.Admin.search_count(
            [('order_id', '=', order.id), ('state', '=', 'planned')])
        self.assertTrue(before)
        order.action_hold()
        self.assertEqual(order.state, 'on_hold')
        self.assertFalse(self.Admin.search_count(
            [('order_id', '=', order.id), ('state', '=', 'planned')]))
        order.action_resume()
        self.assertEqual(order.state, 'active')
        after = self.Admin.search_count(
            [('order_id', '=', order.id), ('state', '=', 'planned')])
        self.assertEqual(after, before)

    # ------------------------------------------------------------------
    # AC7 — PRN: no auto slots; ad-hoc dose linked to the visit
    # ------------------------------------------------------------------
    def test_07_prn(self):
        order = self._make_order(
            frequency='prn', prn_reason='Pain > 4/10')
        self.assertTrue(order.is_prn)
        self._activate(order)
        self.assertFalse(self.Admin.search_count(
            [('order_id', '=', order.id)]))
        fso = self._make_fso()
        dose = self.Admin.create_prn_dose(order, fso=fso)
        self.assertTrue(dose.is_prn_dose)
        self.assertEqual(dose.fso_id, fso)
        self.assertEqual(dose.state, 'planned')
        dose.action_record_given()
        self.assertEqual(dose.state, 'given')
        # PRN orders require a reason (Python constraint).
        with self.assertRaises(ValidationError):
            self._make_order(frequency='prn')

    # ------------------------------------------------------------------
    # AC8 — nurses record administrations, cannot author orders
    # ------------------------------------------------------------------
    def test_08_nurse_acl(self):
        from odoo.exceptions import AccessError
        nurse = self._make_nurse()
        with self.assertRaises(AccessError):
            self.Order.with_user(nurse).create({
                'client_id': self.patient.id,
                'medication_id': self.med_para.id,
            })
        order = self._make_order(frequency='od')
        self._activate(order)
        with self.assertRaises(AccessError):
            order.with_user(nurse).write({'dose_quantity': 2})
        slot = self.Admin.search(
            [('order_id', '=', order.id)], limit=1)
        slot.with_user(nurse).action_record_given()
        self.assertEqual(slot.state, 'given')

    # ------------------------------------------------------------------
    # AC9 — catchment record rules
    # ------------------------------------------------------------------
    def test_09_catchment_rules(self):
        order = self._make_order(frequency='od')
        self.assertEqual(order.catchment_province_id, self.province)
        other_province = self.env['health.catchment.province'].create({
            'name': 'Other eMAR Province %s' % uuid.uuid4().hex[:6],
            'code': 'OEP%s' % uuid.uuid4().hex[:4],
        })
        outsider = self.env['res.users'].create({
            'name': 'eMAR Outside Nurse',
            'login': 'emar_out_nurse_%s' % uuid.uuid4().hex[:8],
            'group_ids': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref('health_base.group_healthcare_nurse').id])],
            'catchment_province_id': other_province.id,
        })
        visible = self.Order.with_user(outsider).search(
            [('id', '=', order.id)])
        self.assertFalse(visible,
                         'Nurse from another catchment must not see the order')

    # ------------------------------------------------------------------
    # AC10 — nightly cron: rolling horizon + auto-complete
    # ------------------------------------------------------------------
    def test_10_cron_maintenance(self):
        order = self._make_order(frequency='od')
        self._activate(order)
        count_before = self.Admin.search_count(
            [('order_id', '=', order.id)])
        with patch.object(
                type(self.env['health.medication.safety']),
                'check_drug_interactions', _no_api):
            self.Order._cron_emar_maintenance()
        # Idempotent horizon — no duplicates.
        self.assertEqual(self.Admin.search_count(
            [('order_id', '=', order.id)]), count_before)
        # Auto-complete: active order past its end date, no planned slots.
        expired = self._make_order(
            frequency='od',
            start_date=fields.Date.today() - timedelta(days=10),
            end_date=fields.Date.today() - timedelta(days=1))
        self._activate(expired)
        self.assertEqual(expired.state, 'active')
        self.assertFalse(self.Admin.search_count(
            [('order_id', '=', expired.id), ('state', '=', 'planned')]))
        with patch.object(
                type(self.env['health.medication.safety']),
                'check_drug_interactions', _no_api):
            self.Order._cron_emar_maintenance()
        self.assertEqual(expired.state, 'completed')

    # ------------------------------------------------------------------
    # Extra guards — dates, dose, cancel flow, amendments
    # ------------------------------------------------------------------
    def test_11_constraints(self):
        with self.assertRaises(Exception):
            self._make_order(
                start_date=fields.Date.today(),
                end_date=fields.Date.today() - timedelta(days=2))
        with self.assertRaises(Exception):
            self._make_order(admin_times='25:99')

    def test_12_cancel_and_amend(self):
        order = self._make_order(frequency='od')
        self._activate(order)
        slot = self.Admin.search(
            [('order_id', '=', order.id)], limit=1)
        slot.action_record_given()
        # Amendment path: head_nurse+ (test env user is admin-level su
        # equivalent) may correct — flagged and logged, never silent.
        slot.write({'dose_given': 0.5})
        self.assertTrue(slot.is_amended)
        self.assertTrue(slot.amended_by_id)
        order.action_cancel()
        self.assertEqual(order.state, 'cancelled')
        self.assertFalse(self.Admin.search_count(
            [('order_id', '=', order.id), ('state', '=', 'planned')]))
        # given tick untouched by cancel
        self.assertEqual(slot.state, 'given')
        order.action_reset_draft()
        self.assertEqual(order.state, 'draft')
