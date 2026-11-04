# -*- coding: utf-8 -*-
"""UAT video defect fixes, 2026-11-04 (docs/handovers/uat-video-fixes-2026-11-04.md).

Server-side halves of items 3-9, 11 and 14:
  3  a doctor reads booking stages and teams (the nurse app's profile/list)
  4  a declined lead is no longer Lead Staff
  5  the reschedule screen lists doctors and every assigned person
  6  a reschedule leaves a history entry
  7  Quick Booking's doctor becomes a doctor assignment
  8  recurring bookings carry the contact and the visit location
  9  the client's booking cards show the reader's wall clock
  11 the 'confirmed' status reads "Confirmed"
  14 no distance chip for a clinic visit
"""
from datetime import timedelta

from unittest.mock import patch

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestUatVideoFixes(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.facility = cls.env['health.facility'].search(
            [('catchment_province_id', '!=', False)], limit=1)
        cls.province = cls.facility.catchment_province_id
        cls.patient = cls.env['res.partner'].with_context(skip_auto_geocode=True).create({
            'name': 'UAT Fix Patient',
            'is_patient': True,
            'catchment_province_id': cls.province.id,
            'primary_facility_id': cls.facility.id,
        })
        cls.nurse = cls._staff('UAT Fix Nurse', 'nurse')
        cls.nurse2 = cls._staff('UAT Fix Nurse Two', 'nurse')
        cls.doctor = cls._staff('UAT Fix Doctor', 'doctor')

    @classmethod
    def _staff(cls, name, kind):
        vals = {
            'name': name,
            'is_healthcare_staff': True,
            'employment_status': 'active',
            'healthcare_facility_id': cls.facility.id,
        }
        Role = cls.env['biz.access.role'] if 'biz.access.role' in cls.env else None
        role = False
        if Role is not None and 'clinical_kind' in Role._fields:
            role = Role.search([('clinical_kind', '=', kind)], limit=1)
        if role:
            vals['job_role_id'] = role.id
        emp = cls.env['hr.employee'].create(vals)
        if not role:
            emp.write({'is_doctor_role': kind == 'doctor', 'is_nurse_role': kind == 'nurse'})
        assert emp.is_doctor_role == (kind == 'doctor'), name
        return emp

    def _booking(self, **extra):
        vals = {
            'patient_id': self.patient.id,
            'facility_id': self.facility.id,
            'scheduled_datetime': fields.Datetime.now().replace(microsecond=0) + timedelta(days=3),
            'service_type': 'clinic_visit',
            'service_location': 'clinic',
        }
        vals.update(extra)
        return self.env['health.fieldservice.order'].create(vals)

    # ---------------------------------------------------------------- 3
    def test_03_doctor_reads_stages_and_teams(self):
        user = new_test_user(self.env, login='uatfix_doctor',
                             groups='base.group_user,health_base.group_healthcare_doctor')
        for model in ('health.fieldservice.stage', 'health.fieldservice.team'):
            self.env[model].with_user(user).check_access('read')
            self.assertFalse(self.env[model].with_user(user).has_access('write'),
                             '%s: the doctor gets read only' % model)

    # ---------------------------------------------------------------- 4
    def test_04_declined_lead_is_not_lead_staff(self):
        fso = self._booking()
        fso.assigned_staff_ids = [(6, 0, [self.nurse.id])]
        lead = fso.assignment_ids.filtered(lambda a: a.staff_id == self.nurse)
        self.assertEqual(lead.assignment_role, 'lead')
        self.assertEqual(fso.lead_staff_id, self.nurse)
        # The nurse declines in the nurse app; the office gives it to a doctor.
        lead.write({'state': 'cancelled'})
        fso.assigned_doctor_ids = [(4, self.doctor.id)]
        fso.invalidate_recordset()
        self.assertFalse(fso.lead_staff_id, 'a declined nurse must not stay Lead Staff')
        self.assertNotIn(self.nurse, fso.assigned_staff_ids)
        self.assertIn(self.doctor, fso.assigned_doctor_ids)
        # Re-staffing: the next nurse becomes lead and the decline is kept.
        fso.assigned_staff_ids = [(6, 0, [self.nurse2.id])]
        fso.invalidate_recordset()
        self.assertEqual(fso.lead_staff_id, self.nurse2)
        self.assertTrue(lead.exists(), 'the declined assignment is history, not deleted')

    # ---------------------------------------------------------------- 5
    def test_05_reschedule_lists_doctors_and_every_assigned_person(self):
        fso = self._booking()
        fso.assigned_staff_ids = [(6, 0, [self.nurse.id])]
        fso.assigned_doctor_ids = [(4, self.doctor.id)]
        data = fso.get_reschedule_data()
        chips = {c['id']: c for c in data['staff_list']}
        self.assertIn(self.doctor.id, chips, 'eligible doctors are listed')
        self.assertTrue(chips[self.doctor.id]['is_doctor'])
        self.assertFalse(chips[self.nurse.id]['is_doctor'])
        self.assertEqual(set(data['assigned_staff_ids']), {self.nurse.id, self.doctor.id})
        self.assertTrue(set(data['assigned_staff_ids']) <= set(chips),
                        'every assigned person has a removable chip')

    # ---------------------------------------------------------------- 5 + 6
    def test_06_reschedule_writes_history_and_can_remove_the_doctor(self):
        fso = self._booking(scheduled_datetime=fields.Datetime.to_datetime('2030-01-07 03:00:00'))
        fso.assigned_staff_ids = [(6, 0, [self.nurse.id])]
        fso.assigned_doctor_ids = [(4, self.doctor.id)]
        before = len(fso.message_ids)
        res = self.env['health.fieldservice.order'].with_context(lang='en_US').action_reschedule_from_wizard(
            fso.id, '2030-01-08', 14.5, [self.nurse.id], 1)
        self.assertTrue(res['success'])
        fso.invalidate_recordset()
        self.assertGreater(len(fso.message_ids), before)
        bodies = ' '.join(fso.message_ids.mapped('body'))
        self.assertIn('Rescheduled from 07/01/2030 10:00 to 08/01/2030 14:30', bodies)
        self.assertIn('Staff removed: %s' % self.doctor.name, bodies)
        self.assertNotIn(self.doctor, fso.assigned_doctor_ids)

    def test_06b_history_is_in_the_users_language(self):
        if not self.env['res.lang']._lang_get('vi_VN'):
            self.skipTest('Vietnamese is not installed')
        fso = self._booking(scheduled_datetime=fields.Datetime.to_datetime('2030-01-07 03:00:00'))
        self.env['health.fieldservice.order'].with_context(lang='vi_VN').action_reschedule_from_wizard(
            fso.id, '2030-01-09', 9.0, [], 1)
        self.assertIn('Đã dời lịch từ 07/01/2030 10:00 sang 09/01/2030 09:00',
                      ' '.join(fso.message_ids.mapped('body')))

    # ---------------------------------------------------------------- 7
    def test_07_quick_booking_doctor_is_an_assignment(self):
        res = self.env['health.fieldservice.order'].action_create_from_quick_booking_owl({
            'patient_id': self.patient.id,
            'service_type': 'clinic_visit',
            'duration_hours': 1,
            'time_hour': 10.0,
            'date': str(fields.Date.today() + timedelta(days=5)),
            'facility_id': self.facility.id,
            'service_location': 'clinic',
            'staff_id': self.nurse.id,
            'doctor_id': self.doctor.id,
        })
        self.assertTrue(res['success'], res)
        fso = self.env['health.fieldservice.order'].browse(res['booking_id'])
        doc = fso.assignment_ids.filtered(lambda a: a.staff_id == self.doctor)
        self.assertEqual(len(doc), 1, 'the doctor gets an assignment (and so the offer)')
        self.assertEqual(doc.assignment_role, 'doctor')
        self.assertIn(self.doctor, fso.assigned_doctor_ids)
        self.assertEqual(fso.lead_staff_id, self.nurse)
        # idempotent
        fso._ensure_doctor_assignment(self.doctor.id)
        self.assertEqual(len(fso.assignment_ids.filtered(lambda a: a.staff_id == self.doctor)), 1)

    def test_07b_crm_user_booking_gives_the_same_offers(self):
        """Owner ruling 2026-11-04: a CRM user who picks staff in Quick
        Booking gets the same assignments (offers) as an Operations Manager:
        lead nurse, support nurse and the doctor, each waiting to accept."""
        Role = self.env['biz.access.role'] if 'biz.access.role' in self.env else None
        role = Role.with_context(lang='en_US').search([('name', '=', 'CRM')], limit=1) if Role is not None else False
        if role:
            groups = role.group_ids
        else:
            groups = (self.env.ref('base.group_user')
                      | self.env.ref('health_base.group_healthcare_sales')
                      | self.env.ref('health_base.group_healthcare_operations_manager'))
        crm = new_test_user(self.env, login='uatfix_crm', groups='base.group_user')
        crm.write({'group_ids': [(4, g.id) for g in groups],
                   'catchment_province_id': self.province.id})
        res = self.env['health.fieldservice.order'].with_user(crm).action_create_from_quick_booking_owl({
            'patient_id': self.patient.id,
            'service_type': 'clinic_visit',
            'duration_hours': 1,
            'time_hour': 11.0,
            'date': str(fields.Date.today() + timedelta(days=6)),
            'facility_id': self.facility.id,
            'service_location': 'clinic',
            'staff_id': self.nurse.id,
            'assigned_staff_ids': [self.nurse2.id],
            'doctor_id': self.doctor.id,
        })
        self.assertTrue(res['success'], res)
        fso = self.env['health.fieldservice.order'].browse(res['booking_id'])
        roles = {a.staff_id: a.assignment_role for a in fso.assignment_ids}
        self.assertEqual(roles.get(self.nurse), 'lead')
        self.assertEqual(roles.get(self.nurse2), 'support')
        self.assertEqual(roles.get(self.doctor), 'doctor')
        self.assertEqual(set(fso.assignment_ids.mapped('state')), {'assigned'},
                         'every picked person has an offer waiting to be accepted')
        self.assertEqual(len(fso.assignment_ids), 3, 'only the staff that were picked')

    # ---------------------------------------------------------------- 7 + 8
    def test_08_recurring_carries_contact_location_and_doctor(self):
        if 'crm.lead' not in self.env:
            self.skipTest('contacts module not installed')
        lead = self.env['crm.lead'].create({
            'name': 'UAT Fix Caller', 'type': 'opportunity',
            'catchment_province_id': self.province.id,
        })
        start = fields.Date.today() + timedelta(days=10)
        res = self.env['health.fieldservice.order'].action_create_recurring_from_owl(
            self.patient.id, 'clinic_visit', 1, 10.0, self.facility.id, 'daily', list(range(7)),
            str(start), 2, doctor_id=self.doctor.id, lead_id=lead.id,
            service_address='12 Phố Huế, Hà Nội')
        self.assertTrue(res['success'], res)
        bookings = self.env['health.fieldservice.order'].browse(res['ids'])
        self.assertEqual(len(bookings), 2)
        for fso in bookings:
            self.assertEqual(fso.crm_lead_id, lead, 'each booking links to its contact')
            self.assertEqual(fso.service_location, 'clinic', 'a clinic visit is not "at home"')
            self.assertEqual(fso.service_address, '12 Phố Huế, Hà Nội')
            self.assertTrue(fso.assignment_ids.filtered(
                lambda a: a.staff_id == self.doctor and a.assignment_role == 'doctor'))
        self.assertEqual(lead.patient_id, self.patient)

    def test_08b_recurring_without_contact_still_gets_the_location(self):
        start = fields.Date.today() + timedelta(days=20)
        res = self.env['health.fieldservice.order'].action_create_recurring_from_owl(
            self.patient.id, 'clinic_visit', 1, 9.0, self.facility.id, 'daily', list(range(7)),
            str(start), 1, draft_only=True)
        fso = self.env['health.fieldservice.order'].browse(res['ids'])
        self.assertEqual(fso.service_location, 'clinic')
        self.assertFalse(fso.crm_lead_id)

    # ---------------------------------------------------------------- 9
    def test_09_timeline_cards_use_the_readers_clock(self):
        self._booking(scheduled_datetime=fields.Datetime.to_datetime('2030-10-19 13:30:00'))
        data = self.patient.with_context(tz='Asia/Ho_Chi_Minh').get_booking_timeline_data()
        card = [b for b in data['bookings'] if b['date'] == '2030-10-19']
        self.assertTrue(card, data['bookings'])
        self.assertEqual(card[0]['time'], '08:30 PM')
        # Late-evening UTC lands on the next Vietnam day.
        self._booking(scheduled_datetime=fields.Datetime.to_datetime('2030-10-20 18:00:00'))
        data = self.patient.with_context(tz='Asia/Ho_Chi_Minh').get_booking_timeline_data()
        self.assertTrue([b for b in data['bookings'] if b['date'] == '2030-10-21' and b['time'] == '01:00 AM'])

    # ---------------------------------------------------------------- 11
    def test_11_confirmed_status_reads_confirmed(self):
        Order = self.env['health.fieldservice.order'].with_context(lang='en_US')
        labels = dict(Order.fields_get(['state'])['state']['selection'])
        self.assertEqual(labels['confirmed'], 'Confirmed')

    # ---------------------------------------------------------------- 14
    def test_14_no_distance_chip_for_clinic_or_online(self):
        Order = self.env['health.fieldservice.order']
        for loc in ('clinic', 'online'):
            keys = [f['key'] for f in Order._quick_booking_pricing_factors(
                {'service_location': loc, 'distance': 6.0})]
            self.assertNotIn('pin', keys, loc)
        keys = [f['key'] for f in Order._quick_booking_pricing_factors(
            {'service_location': 'home', 'distance': 6.0})]
        self.assertIn('pin', keys)

    # ---------------------------------------------------------------- round 3
    def _om_user(self, login, area):
        """A login employed as Operations Manager, working in `area`."""
        user = new_test_user(self.env, login=login, groups='base.group_user')
        user.write({'catchment_province_id': area.id})
        emp = self.env['hr.employee'].create({'name': login, 'user_id': user.id})
        Role = self.env['biz.access.role'] if 'biz.access.role' in self.env else None
        role = False
        if Role is not None and 'clinical_kind' in Role._fields:
            role = Role.search([('clinical_kind', '=', 'operations_manager')], limit=1)
        if role:
            emp.job_role_id = role
        else:
            emp.write({'is_om_role': True})
        self.assertTrue(emp.is_om_role)
        return user

    def test_r3_1_no_further_visits_is_stored_and_shown(self):
        fso = self._booking()
        res = fso.with_context(lang='en_US').action_record_visit_close(
            'no_further', reason='Patient improved/recovered')
        self.assertEqual(res['follow_up_users'], [])
        self.assertEqual(fso.visit_close_answer, 'no_further')
        self.assertEqual(fso.visit_close_reason, 'Patient improved/recovered')
        self.assertEqual(fso.visit_close_by_id, self.env.user)
        self.assertTrue(fso.visit_close_date)
        self.assertFalse(fso.visit_close_follow_up)
        status = self.patient.with_context(lang='en_US', tz='Asia/Ho_Chi_Minh').visit_close_status
        self.assertIn('No further visits wanted — Patient improved/recovered', status)
        self.assertIn(fso.name, status)
        self.assertIn('by %s' % self.env.user.name, status)

    def test_r3_1b_the_card_is_on_the_booking_and_the_line_on_the_client(self):
        arch = self.env['health.fieldservice.order'].get_view(
            self.env.ref('health_fieldservice.view_health_fso_form_ops').id, 'form')['arch']
        self.assertIn('visit_close_card', arch)
        self.assertIn('visit_close_answer', arch)
        arch = self.env['res.partner'].get_view(
            self.env.ref('health_fieldservice.view_health_patient_form_ops').id, 'form')['arch']
        self.assertIn('visit_close_status', arch)

    def test_r3_2_follow_up_goes_to_the_areas_operations_manager(self):
        other = self.env['health.catchment.province'].create({'name': 'UAT Other Area', 'code': '75'})
        here = self._om_user('uatfix_om_here', self.province)
        there = self._om_user('uatfix_om_there', other)
        fso = self._booking()
        res = fso.action_record_visit_close('no_further', reason='Patient declined', need_follow_up=True)
        self.assertIn(here.name, res['follow_up_users'])
        self.assertNotIn(there.name, res['follow_up_users'])
        self.assertIn(here, fso.visit_close_follow_up_user_ids)
        acts = self.env['mail.activity'].search([
            ('res_model', '=', 'res.partner'), ('res_id', '=', self.patient.id),
            ('user_id', '=', here.id)])
        self.assertTrue(acts, 'the area OM has a follow-up task')
        self.assertFalse(self.env['mail.activity'].search([
            ('res_model', '=', 'res.partner'), ('res_id', '=', self.patient.id),
            ('user_id', '=', there.id)]))

    def test_r3_2b_no_om_falls_back_to_an_owner_and_never_fakes_success(self):
        fso = self._booking()
        Emp = self.env['hr.employee']
        with patch.object(type(Emp), 'search', lambda self_, *a, **k: Emp.browse()):
            owners = fso._follow_up_recipients()
        owner_group = self.env.ref('health_base.group_healthcare_owner')
        self.assertTrue(owners, 'an Owner exists on this database')
        self.assertTrue(all(owner_group in u.all_group_ids for u in owners))
        with patch.object(type(fso), '_follow_up_recipients', lambda self_: self.env['res.users']):
            with self.assertRaises(UserError):
                fso.action_record_visit_close('no_further', reason='x', need_follow_up=True)

    def test_r3_7_thirty_minute_quick_booking(self):
        res = self.env['health.fieldservice.order'].action_create_from_quick_booking_owl({
            'patient_id': self.patient.id,
            'service_type': 'clinic_visit',
            'duration_hours': 0.5,
            'time_hour': 9.5,
            'date': str(fields.Date.today() + timedelta(days=7)),
            'facility_id': self.facility.id,
            'service_location': 'clinic',
            'draft_only': True,
        })
        self.assertTrue(res['success'], res)
        fso = self.env['health.fieldservice.order'].browse(res['booking_id'])
        self.assertEqual(fso.scheduled_duration, 30)
        self.assertEqual(fso.estimated_end_datetime - fso.scheduled_datetime, timedelta(minutes=30))
        self.assertEqual(fso.estimated_duration, 0.5)
        product = self.env['product.product'].create(
            {'name': 'UAT 30 min probe', 'type': 'service', 'list_price': 120000, 'sale_ok': True})
        preview = self.env['health.fieldservice.order'].preview_quick_booking_pricing({
            'patient_id': self.patient.id, 'service_type': 'clinic_visit',
            'service_location': 'clinic', 'facility_id': self.facility.id,
            'date': str(fields.Date.today() + timedelta(days=7)), 'time_hour': 9.5,
            'duration_hours': 0.5, 'product_lines': [{'product_id': product.id, 'qty': 1}]})
        self.assertEqual(len(preview['lines']), 1)
        self.assertGreater(preview['lines'][0]['unit_price'], 0)

    # ---------------------------------------------------------------- round 5
    def test_r5_1_booking_shows_the_main_phone(self):
        self.patient.write({'phone': '0900000101', 'mobile': '0900000212'})
        fso = self._booking()
        self.assertEqual(fso.patient_phone, '0900000101')
        self.assertEqual(fso.patient_second_phone, '0900000212')
        Order = self.env['health.fieldservice.order']
        self.assertIn(fso, Order.search([('patient_phone', 'ilike', '0900000101')]))
        self.assertIn(fso, Order.search([('patient_phone', 'ilike', '0900000212')]))
        # only a second number on file: it is the phone, no second line
        self.patient.write({'phone': False})
        fso.invalidate_recordset()
        self.assertEqual(fso.patient_phone, '0900000212')
        self.assertFalse(fso.patient_second_phone)
        arch = Order.get_view(self.env.ref('health_fieldservice.view_health_fso_form_ops').id, 'form')['arch']
        self.assertIn('patient_second_phone', arch)

    def test_r5_2_nurse_banner_only_for_restricted_nurses(self):
        view = self.env.ref('health_fieldservice.view_healthcare_quote_form_custom')
        nurse = new_test_user(self.env, login='uatfix_r5_nurse',
                              groups='base.group_user,health_base.group_healthcare_nurse,sales_team.group_sale_salesman')
        om = new_test_user(self.env, login='uatfix_r5_om', groups=','.join([
            'base.group_user', 'health_base.group_healthcare_nurse',
            'health_base.group_healthcare_operations_manager', 'sales_team.group_sale_salesman']))
        Quote = self.env['sale.order']
        self.assertIn('Nurse Access', Quote.with_user(nurse).get_view(view.id, 'form')['arch'])
        self.assertNotIn('Nurse Access', Quote.with_user(om).get_view(view.id, 'form')['arch'])

    def test_r5_3_quote_dialog_always_shows_the_unit(self):
        view = self.env.ref('health_fieldservice.view_healthcare_quote_form_custom')
        om = new_test_user(self.env, login='uatfix_r5_om2', groups=','.join([
            'base.group_user', 'health_base.group_healthcare_operations_manager',
            'sales_team.group_sale_salesman']))
        arch = self.env['sale.order'].with_user(om).get_view(view.id, 'form')['arch']
        self.assertIn('name="product_uom_id"', arch, 'the Unit column is there without the multi-unit setting')

