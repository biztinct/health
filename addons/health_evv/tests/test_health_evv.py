# -*- coding: utf-8 -*-
import uuid
from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

GENESIS = '0' * 64

# ~30 m north in degrees of latitude (1 deg lat ~ 111.195 km).
DEG_30M = 30.0 / 111195.0
DEG_300M = 300.0 / 111195.0

BASE_LAT = 10.7769000
BASE_LNG = 106.7009000


def _get_fixture(env):
    """Patient partners REQUIRE catchment_province_id; FSOs REQUIRE
    facility_id + patient_id + scheduled_datetime. Search existing
    province/facility first, create fallback."""
    Partner = env['res.partner']
    Facility = env['health.facility']

    province = env['health.catchment.province'].search([], limit=1)
    if not province:
        province = env['health.catchment.province'].create({
            'name': 'Test EVV Province',
            'code': 'TEV',
        })
    facility = Facility.search(
        [('catchment_province_id', '=', province.id)], limit=1)
    if not facility:
        facility = Facility.create({
            'name': 'Test EVV Facility',
            'code': 'TEVF',
            'street': '1 EVV Street',
            'city': 'Test City',
            'catchment_province_id': province.id,
        })
    patient = Partner.create({
        'name': 'EVV Test Patient',
        'is_patient': True,
        'catchment_province_id': province.id,
        'primary_facility_id': facility.id,
        'partner_latitude': BASE_LAT,
        'partner_longitude': BASE_LNG,
        'geofence_radius_m': 150,
        'geofence_enabled': True,
    })
    employee = env['hr.employee'].search([], limit=1)
    if not employee:
        employee = env['hr.employee'].create({'name': 'EVV Test Nurse'})
    return province, facility, patient, employee


@tagged('post_install', '-at_install')
class TestHealthEvv(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        (cls.province, cls.facility, cls.patient,
         cls.employee) = _get_fixture(cls.env)
        cls.Event = cls.env['health.evv.event']
        # action_start_service needs the current user to have an
        # employee (staff_id source) and an In Progress stage to exist.
        if not cls.env.user.employee_id:
            cls.env['hr.employee'].create({
                'name': 'EVV Admin Employee',
                'user_id': cls.env.user.id,
            })
            cls.env.user.invalidate_recordset()
        Stage = cls.env['health.fieldservice.stage']
        if not Stage.search([('state', '=', 'in_progress'),
                             ('active', '=', True)], limit=1):
            Stage.create({'name': 'In Progress', 'state': 'in_progress'})

    def _make_fso(self):
        return self.env['health.fieldservice.order'].create({
            'patient_id': self.patient.id,
            'facility_id': self.facility.id,
            'scheduled_datetime': fields.Datetime.now() + timedelta(days=1),
            'scheduled_duration': 120,
        })

    def _vals(self, fso, event_type, **overrides):
        vals = {
            'event_type': event_type,
            'event_datetime': fields.Datetime.now(),
            'lat': BASE_LAT + DEG_30M,
            'lng': BASE_LNG,
            'accuracy_m': 12.4,
            'staff_id': self.employee.id,
            'device_uuid': 'dev-test',
            'client_event_uuid': str(uuid.uuid4()),
            'payload': {},
        }
        vals.update(overrides)
        return vals

    def _build_chain(self, fso, checkin_dt=None, checkout_dt=None):
        checkin = self.Event.append_event(
            fso, self._vals(fso, 'checkin',
                            event_datetime=checkin_dt
                            or fields.Datetime.now()))
        attest = self.Event.append_event(
            fso, self._vals(fso, 'task_attest',
                            payload={'task_code': 'vitals', 'done': True}))
        checkout = self.Event.append_event(
            fso, self._vals(fso, 'checkout',
                            event_datetime=checkout_dt
                            or fields.Datetime.now()))
        signature = self.Event.append_event(
            fso, self._vals(fso, 'signature', payload={
                'signer_name': 'Nguyễn Văn A',
                'signer_relationship': 'family',
                'png_sha256': 'ab' * 32,
            }))
        return checkin, attest, checkout, signature

    # ------------------------------------------------------------------
    def test_chain_build_and_validate_happy_path(self):
        """Acceptance 1: checkin -> task_attest -> checkout -> signature
        yields sequences 1-4 and validate_chain returns valid."""
        fso = self._make_fso()
        events = self._build_chain(fso)
        self.assertEqual([e.sequence for e in events], [1, 2, 3, 4])
        self.assertEqual(events[0].prev_hash, GENESIS)
        self.assertEqual(events[1].prev_hash, events[0].payload_hash)
        result = self.Event.validate_chain(fso)
        self.assertTrue(result['valid'])
        self.assertIsNone(result['first_bad_sequence'])
        self.assertTrue(all(e.chain_valid for e in events))
        self.assertTrue(fso.evv_chain_valid)

    def test_tamper_detection(self):
        """Acceptance 2: direct SQL mutation of a mid-chain event breaks
        validation from that sequence on."""
        fso = self._make_fso()
        events = self._build_chain(fso)
        self.env.cr.execute(
            "UPDATE health_evv_event SET lat = 0 "
            "WHERE fso_id = %s AND sequence = 2", (fso.id,))
        self.env['health.evv.event'].invalidate_model()
        result = self.Event.validate_chain(fso)
        self.assertFalse(result['valid'])
        self.assertEqual(result['first_bad_sequence'], 2)
        self.assertTrue(events[0].chain_valid)
        self.assertFalse(events[1].chain_valid)
        self.assertFalse(events[2].chain_valid)
        self.assertFalse(fso.evv_chain_valid)
        self.assertFalse(fso.evv_verified)

    def test_idempotent_replay(self):
        """Acceptance 3: replaying the same client_event_uuid returns the
        original event; no second row."""
        fso = self._make_fso()
        vals = self._vals(fso, 'checkin')
        first = self.Event.append_event(fso, vals)
        replay = self.Event.append_event(fso, dict(vals))
        self.assertEqual(first.id, replay.id)
        self.assertEqual(self.Event.search_count(
            [('fso_id', '=', fso.id)]), 1)

    def test_append_only_enforcement(self):
        """Acceptance 8: write()/unlink() raise UserError for every user,
        superuser included."""
        fso = self._make_fso()
        event = self.Event.append_event(fso, self._vals(fso, 'checkin'))
        with self.assertRaises(UserError):
            event.write({'lat': 0.0})
        with self.assertRaises(UserError):
            event.unlink()
        # chain_valid alone stays writable (validator escape hatch).
        event.write({'chain_valid': True})

    def test_geofence_distance(self):
        """Acceptance 4: 30 m inside a 150 m fence; 300 m outside."""
        fso = self._make_fso()
        near = self.Event.append_event(fso, self._vals(fso, 'checkin'))
        self.assertAlmostEqual(near.distance_m, 30.0, delta=3.0)
        self.assertTrue(near.inside_geofence)
        far = self.Event.append_event(fso, self._vals(
            fso, 'checkout', lat=BASE_LAT + DEG_300M))
        self.assertAlmostEqual(far.distance_m, 300.0, delta=10.0)
        self.assertFalse(far.inside_geofence)
        self.assertFalse(fso.evv_verified)

    def test_verified_units_compute(self):
        """Acceptance 7: checkin 08:00 / checkout 10:07 -> 2.0 verified
        units (floor to 0.25h)."""
        fso = self._make_fso()
        today = fields.Datetime.now().replace(
            hour=8, minute=0, second=0, microsecond=0)
        self._build_chain(
            fso, checkin_dt=today,
            checkout_dt=today + timedelta(hours=2, minutes=7))
        self.assertTrue(fso.evv_chain_valid)
        self.assertTrue(fso.evv_verified)
        self.assertEqual(fso.evv_verified_units, 2.0)

    def test_client_hash_mismatch_recorded_not_rejected(self):
        """Mismatched client hash is recorded in the payload but the
        event is stored and the chain still validates."""
        fso = self._make_fso()
        event = self.Event.append_event(
            fso, self._vals(fso, 'checkin'), client_hash='f' * 64)
        self.assertEqual(
            event.payload.get('client_hash_mismatch'), 'f' * 64)
        result = self.Event.validate_chain(fso)
        self.assertTrue(result['valid'])

    def test_start_service_context_wiring(self):
        """Acceptance 9 (model level): action_start_service with EVV
        context auto-appends a checkin event; without context nothing is
        emitted; EVV failure never blocks the workflow."""
        staff = (self.env['hr.employee'].search([], limit=1)
                 or self.env['hr.employee'].create({'name': 'EVV Test Nurse'}))
        fso = self._make_fso()
        fso.write({'assigned_staff_ids': [(6, 0, [staff.id])],
                   'state': 'assigned'})
        client_uuid = str(uuid.uuid4())
        fso.with_context(
            evv_lat=BASE_LAT + DEG_30M, evv_lng=BASE_LNG,
            evv_accuracy=9.0, evv_device_uuid='dev-test',
            evv_client_uuid=client_uuid,
        ).action_start_service()
        self.assertEqual(fso.state, 'in_progress')
        self.assertTrue(fso.actual_start_datetime)
        events = self.Event.search([('fso_id', '=', fso.id)])
        self.assertEqual(len(events), 1)
        self.assertEqual(events.event_type, 'checkin')
        self.assertEqual(events.client_event_uuid, client_uuid)

        # Desktop transition (no EVV context) emits no event.
        fso2 = self._make_fso()
        fso2.write({'assigned_staff_ids': [(6, 0, [staff.id])],
                    'state': 'assigned'})
        fso2.action_start_service()
        self.assertEqual(self.Event.search_count(
            [('fso_id', '=', fso2.id)]), 0)
