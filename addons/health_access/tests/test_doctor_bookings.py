# -*- coding: utf-8 -*-
"""A doctor reads every booking in their area, and changes none.

Owner ruling 2026-09-30 (after AR-3): doctors see ALL bookings, not only the
visits arranged for them. The row rule `rule_fso_doctor_own_visits` is scoped
by the catchment area alone. This test pins three things:

* a doctor who is on NO visit still reads a booking in their area;
* a booking in another area stays out of reach;
* the doctor cannot write the booking they can read.
"""
import uuid

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestDoctorReadsEveryBookingInTheirArea(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        tag = uuid.uuid4().hex[:5]
        Province = cls.env['health.catchment.province']
        cls.province = Province.create({'name': 'DB P %s' % tag, 'code': 'D%s' % tag[:3]})
        cls.elsewhere = Province.create({'name': 'DB E %s' % tag, 'code': 'E%s' % tag[:3]})

        def facility(name, province):
            return cls.env['health.facility'].create({
                'name': '%s %s' % (name, tag), 'code': '%s%s' % (name[:2], tag[:3]),
                'street': '1 St', 'city': 'City',
                'catchment_province_id': province.id})

        def patient(name, province, fac):
            return cls.env['res.partner'].create({
                'name': '%s %s' % (name, tag), 'is_patient': True,
                'catchment_province_id': province.id,
                'primary_facility_id': fac.id,
                'mobile': '09%08d' % (uuid.uuid4().int % 10 ** 8)})

        def booking(pat, fac):
            return cls.env['health.fieldservice.order'].create({
                'patient_id': pat.id, 'facility_id': fac.id,
                'scheduled_datetime': fields.Datetime.now(),
                'scheduled_duration': 60, 'service_type': 'home_visit'})

        fac_here = facility('DBH', cls.province)
        fac_there = facility('DBT', cls.elsewhere)
        cls.booking_here = booking(patient('DB Here', cls.province, fac_here), fac_here)
        cls.booking_there = booking(patient('DB There', cls.elsewhere, fac_there), fac_there)

        # A pure doctor: the doctor tier and nothing wider, in THIS area, and on
        # no visit at all.
        doctor_group = cls.env.ref('health_base.group_healthcare_doctor')
        cls.doctor = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'DB Doctor %s' % tag,
            'login': 'db.doctor.%s' % tag,
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id, doctor_group.id])],
            'catchment_province_id': cls.province.id,
        })

    def _as_doctor(self):
        return self.env['health.fieldservice.order'].with_user(self.doctor)

    def test_01_a_booking_in_their_area_is_readable_even_when_they_are_on_no_visit(self):
        self.assertFalse(self.booking_here.assignment_ids)
        self.assertFalse(self.booking_here.primary_doctor_id)
        seen = self._as_doctor().search([('id', '=', self.booking_here.id)])
        self.assertEqual(seen, self.booking_here,
                         "a doctor must read every booking in their area, assigned or not")
        # and the read itself goes through, not only the search
        self.assertTrue(seen.read(['scheduled_datetime']))

    def test_02_a_booking_in_another_area_stays_out_of_reach(self):
        seen = self._as_doctor().search([('id', '=', self.booking_there.id)])
        self.assertFalse(seen, "the catchment area still scopes what a doctor sees")

    def test_03_the_doctor_cannot_change_what_they_read(self):
        row = self._as_doctor().browse(self.booking_here.id)
        with self.assertRaises(AccessError):
            row.write({'scheduled_duration': 90})

    def test_04_the_rule_is_scoped_by_area_alone(self):
        rule = self.env.ref('health_access.rule_fso_doctor_own_visits')
        self.assertIn('catchment_province_id', rule.domain_force)
        for who in ('assignment_ids', 'primary_doctor_id', 'primary_nurse_id'):
            self.assertNotIn(who, rule.domain_force,
                             "the owner ruled doctors see ALL bookings — no assignment clause")
