# -*- coding: utf-8 -*-
"""UAT round 6 (docs/handovers/uat-video-fixes-2026-11-04.md §8), booking side.

  2  the booking's driving distance: set by hand by the OM/Owner (history
     note, sticks through an address/geo recompute, refused to others), and a
     client distance set on purpose — 0 included — is used as is
  6  MOH report: company + clinic in the body, the delivering doctor, notes
  9b the booking model reads "Booking" to a person
"""
from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestUatRound6(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.facility = cls.env['health.facility'].search(
            [('catchment_province_id', '!=', False)], limit=1)
        cls.province = cls.facility.catchment_province_id
        cls.patient = cls.env['res.partner'].with_context(
            skip_auto_geocode=True, skip_distance_recompute=True).create({
            'name': 'Round6 Client', 'is_patient': True,
            'catchment_province_id': cls.province.id,
            'primary_facility_id': cls.facility.id,
        })
        vals = {'name': 'Round6 Doctor', 'is_healthcare_staff': True,
                'employment_status': 'active',
                'healthcare_facility_id': cls.facility.id}
        Role = cls.env['biz.access.role'] if 'biz.access.role' in cls.env else None
        role = Role.search([('clinical_kind', '=', 'doctor')], limit=1) if (
            Role is not None and 'clinical_kind' in Role._fields) else False
        if role:
            vals['job_role_id'] = role.id
        cls.doctor = cls.env['hr.employee'].create(vals)
        if not role:
            cls.doctor.write({'is_doctor_role': True})
        cls.om = new_test_user(cls.env, login='r6_om', groups=(
            'base.group_user,health_base.group_healthcare_operations_manager'))
        cls.nurse = new_test_user(cls.env, login='r6_nurse', groups=(
            'base.group_user,health_base.group_healthcare_nurse'))
        (cls.om | cls.nurse).write({'catchment_province_id': cls.province.id})

    def _booking(self, **extra):
        vals = {
            'patient_id': self.patient.id,
            'facility_id': self.facility.id,
            'scheduled_datetime': fields.Datetime.now().replace(microsecond=0) + timedelta(days=4),
            'service_type': 'home_visit',
            'service_location': 'home',
        }
        vals.update(extra)
        return self.env['health.fieldservice.order'].create(vals)

    # ------------------------------------------------------------ item 2
    def test_2a_client_distance_set_on_purpose_counts_even_at_zero(self):
        # Written by a person/import: marked 'manual' (no lookup method sent).
        self.patient.write({'clinic_drive_distance_km': 0.0})
        self.assertEqual(self.patient.clinic_distance_method, 'manual')
        booking = self._booking()
        booking.write({'travel_distance': 5.76})  # what an old road lookup left
        booking.write({'travel_distance_manual': False})
        booking._update_travel_distance()
        self.assertEqual(booking.travel_distance, 0.0)
        # A looked-up value is not "manual".
        self.patient.with_context(skip_distance_recompute=True).write({
            'clinic_drive_distance_km': 6.0, 'clinic_distance_method': 'osrm'})
        self.assertFalse(self.patient._has_manual_clinic_distance())

    def test_2b_om_sets_the_booking_distance_and_it_sticks(self):
        self.patient.write({'clinic_drive_distance_km': 6.0})
        booking = self._booking()
        self.assertEqual(booking.travel_distance, 6.0)
        self.assertTrue(booking.with_user(self.om).can_edit_travel_distance)
        self.assertFalse(booking.with_user(self.nurse).can_edit_travel_distance)
        before = len(booking.message_ids)
        booking.with_user(self.om).write({'travel_distance': 0.0})
        self.assertEqual(booking.travel_distance, 0.0)
        self.assertTrue(booking.travel_distance_manual)
        notes = booking.message_ids[:len(booking.message_ids) - before]
        self.assertTrue(any('Distance changed from 6.00 to 0.00 km' in (m.body or '')
                            for m in notes), [m.body for m in notes])
        # A later address/geo recompute keeps the typed value.
        booking._update_travel_distance()
        booking.write({'facility_id': self.facility.id})
        self.assertEqual(booking.travel_distance, 0.0)

    def test_2c_others_cannot_change_the_distance(self):
        booking = self._booking()
        with self.assertRaises(UserError):
            booking.with_user(self.nurse).write({'travel_distance': 3.0})
        booking.write({'state': 'cancelled'})
        with self.assertRaises(UserError):
            booking.with_user(self.om).write({'travel_distance': 3.0})

    # ------------------------------------------------------------ item 6
    def test_6_moh_report_names_company_clinic_doctor_and_notes(self):
        booking = self._booking(service_type='clinic_visit', service_location='clinic',
                                completion_notes='Wound dressed, client stable.')
        booking.action_assign_staff_to_fso(self.doctor.id, assignment_role='lead')
        booking.invalidate_recordset()
        self.assertEqual(booking._moh_report_doctor_name(), self.doctor.name)
        html, _fmt = self.env['ir.actions.report']._render_qweb_html(
            'health_fieldservice.action_report_moh_single', booking.ids)
        html = html.decode() if isinstance(html, bytes) else html
        company = booking._moh_report_company()
        self.assertIn(company.name, html)
        self.assertIn(self.facility.name, html)
        self.assertIn(self.doctor.name, html)
        self.assertIn('Wound dressed, client stable.', html)
        self.assertNotIn('San Francisco', html)
        # ONE html document: a nested one made the PDF engine run out of
        # memory on the server (UAT round 7).
        self.assertEqual(html.count('<head>'), 1)
        self.assertEqual(html.count('class="article"'), 1)
        self.assertNotIn('src="data:', html, 'no data: images in a PDF body')
        # Placeholder street parts never print.
        self.assertNotIn('-, ', booking._moh_report_address(self.facility))

    def test_6b_notes_fall_back_to_the_clinical_summary(self):
        booking = self._booking(clinical_notes='<p>Simulated care only.</p>')
        self.assertEqual(booking._moh_report_notes(), 'Simulated care only.')
        self.assertEqual(self._booking()._moh_report_notes(), '')

    # ------------------------------------------------------------ item 9b
    def test_9_booking_model_reads_booking(self):
        self.assertEqual(self.env['health.fieldservice.order']._description, 'Booking')
        self.assertEqual(self.env['ir.model']._get('health.fieldservice.order').name, 'Booking')
