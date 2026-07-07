# -*- coding: utf-8 -*-
"""health_incident acceptance tests (clinical spec §5.10)."""
from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


def _get_fixture(env):
    """Patient partners REQUIRE catchment_province_id; FSOs REQUIRE
    facility_id + patient_id + scheduled_datetime. Search existing
    province/facility first, create fallback (health_vitals test
    pattern)."""
    Partner = env['res.partner']
    Facility = env['health.facility']

    province = env['health.catchment.province'].search([], limit=1)
    if not province:
        province = env['health.catchment.province'].create({
            'name': 'Test Incident Province',
            'code': 'TIP',
        })
    facility = Facility.search(
        [('catchment_province_id', '=', province.id)], limit=1)
    if not facility:
        facility = Facility.create({
            'name': 'Test Incident Facility',
            'code': 'TIF',
            'street': '1 Incident Street',
            'city': 'Test City',
            'catchment_province_id': province.id,
        })
    patient = Partner.create({
        'name': 'Incident Test Patient',
        'is_patient': True,
        'catchment_province_id': province.id,
        'primary_facility_id': facility.id,
    })
    return province, facility, patient


@tagged('post_install', '-at_install')
class TestHealthIncident(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.province, cls.facility, cls.patient = _get_fixture(cls.env)
        cls.Incident = cls.env['health.incident']
        cls.Action = cls.env['health.incident.action']
        # Facility manager with a linked user (severe-incident activity
        # target); reuse the running user's employee when present
        # (health_vitals fixture pattern).
        employee = cls.env.user.employee_id
        if not employee:
            employee = cls.env['hr.employee'].create({
                'name': 'Incident Test Manager',
                'user_id': cls.env.user.id,
            })
            cls.env.user.invalidate_recordset()
        cls.facility.facility_manager_id = employee
        cls.facility.head_nurse_id = cls.env.user

    def _make_incident(self, **vals):
        return self.Incident.create(dict({
            'incident_type': 'injury',
            'severity': '2',
            'client_id': self.patient.id,
            'incident_datetime': fields.Datetime.now(),
            'description': 'Test incident description',
        }, **vals))

    def _make_action(self, incident, **vals):
        return self.Action.create(dict({
            'incident_id': incident.id,
            'name': 'Fix the hazard',
            'assignee_id': self.env.user.id,
            'due_date': fields.Date.today() + timedelta(days=7),
        }, **vals))

    def _incident_activity_count(self, incident):
        return self.env['mail.activity'].search_count(
            [('res_model', '=', 'health.incident'),
             ('res_id', '=', incident.id)])

    # ------------------------------------------------------------------
    # Acceptance #1 — creation basics
    # ------------------------------------------------------------------
    def test_create(self):
        incident = self._make_incident()
        self.assertEqual(incident.name[:3], 'INC')
        self.assertEqual(incident.state, 'reported')
        self.assertEqual(incident.reporter_id, self.env.user)
        self.assertEqual(incident.facility_id, self.facility)
        self.assertEqual(incident.catchment_province_id, self.province)
        self.assertFalse(incident.notifiable)
        self.assertIn('INC', incident.display_name)

    def test_staff_only_incident_facility_catchment(self):
        # Acceptance #9: staff-only incident (no client) takes the
        # facility's catchment.
        incident = self._make_incident(
            client_id=False, facility_id=self.facility.id)
        self.assertEqual(incident.catchment_province_id, self.province)

    # ------------------------------------------------------------------
    # Acceptance #2 — severe incident schedules a manager activity
    # ------------------------------------------------------------------
    def test_severe_incident_activity(self):
        incident = self._make_incident(severity='5')
        self.assertTrue(incident.notifiable)
        activities = self.env['mail.activity'].search(
            [('res_model', '=', 'health.incident'),
             ('res_id', '=', incident.id)])
        self.assertTrue(any(
            'Severe incident reported' in (activity.summary or '')
            for activity in activities))

    # ------------------------------------------------------------------
    # Acceptance #3 — fall incident triggers Morse reassessment
    # ------------------------------------------------------------------
    def test_fall_trigger(self):
        incident = self._make_incident(incident_type='fall')
        self.assertTrue(incident.fall_risk_reassessment_triggered)
        activities = self.env['mail.activity'].search(
            [('res_model', '=', 'health.incident'),
             ('res_id', '=', incident.id)])
        self.assertTrue(any(
            'Reassess fall risk' in (activity.summary or '')
            for activity in activities))

    def test_fall_trigger_on_write(self):
        incident = self._make_incident(incident_type='injury')
        self.assertFalse(incident.fall_risk_reassessment_triggered)
        incident.write({'incident_type': 'fall'})
        self.assertTrue(incident.fall_risk_reassessment_triggered)

    def test_fall_trigger_idempotent(self):
        incident = self._make_incident(incident_type='fall')
        before = self._incident_activity_count(incident)
        incident._trigger_fall_risk_reassessment()
        self.assertEqual(self._incident_activity_count(incident), before)

    # ------------------------------------------------------------------
    # Acceptance #4 — workflow guards
    # ------------------------------------------------------------------
    def test_investigation_requires_investigator(self):
        incident = self._make_incident()
        incident.action_start_review()
        self.assertEqual(incident.state, 'under_review')
        with self.assertRaises(UserError):
            incident.action_start_investigation()
        incident.investigator_id = self.env.user
        incident.action_start_investigation()
        self.assertEqual(incident.state, 'investigation')

    def test_assign_actions_guards(self):
        incident = self._make_incident(severity='3')
        incident.action_start_review()
        incident.investigator_id = self.env.user
        incident.action_start_investigation()
        with self.assertRaises(UserError):
            incident.action_assign_actions()  # no root cause, no action
        incident.root_cause = 'Wet floor'
        with self.assertRaises(UserError):
            incident.action_assign_actions()  # still no open action
        self._make_action(incident)
        incident.action_assign_actions()
        self.assertEqual(incident.state, 'actions_assigned')

    def test_close_blocked_by_open_actions(self):
        incident = self._make_incident(severity='3')
        incident.action_start_review()
        incident.investigator_id = self.env.user
        incident.action_start_investigation()
        incident.root_cause = 'Wet floor'
        action = self._make_action(incident)
        incident.action_assign_actions()
        with self.assertRaises(UserError):
            incident.action_close()
        action.action_done()
        incident.action_close()
        self.assertEqual(incident.state, 'closed')
        self.assertTrue(incident.closed_date)
        self.assertEqual(incident.closed_by_id, self.env.user)

    def test_close_notifiable_requires_authority(self):
        incident = self._make_incident(severity='3', notifiable=True)
        incident.action_start_review()
        incident.investigator_id = self.env.user
        incident.action_start_investigation()
        incident.root_cause = 'Wrong dose drawn'
        action = self._make_action(incident)
        incident.action_assign_actions()
        action.action_done()
        with self.assertRaises(UserError):
            incident.action_close()
        incident.write({
            'notified_authority': 'Sở Y tế',
            'notified_date': fields.Date.today(),
        })
        incident.action_close()
        self.assertEqual(incident.state, 'closed')

    # ------------------------------------------------------------------
    # Acceptance #5 — fast-close only for severity 1-2
    # ------------------------------------------------------------------
    def test_close_minor(self):
        incident = self._make_incident(severity='2')
        incident.action_close_minor()
        self.assertEqual(incident.state, 'closed')

    def test_close_minor_blocked_for_severe(self):
        incident = self._make_incident(severity='3')
        with self.assertRaises(UserError):
            incident.action_close_minor()

    # ------------------------------------------------------------------
    # Acceptance #6 — corrective actions
    # ------------------------------------------------------------------
    def test_action_deadline_activity_and_done(self):
        incident = self._make_incident()
        action = self._make_action(incident)
        activities = self.env['mail.activity'].search(
            [('res_model', '=', 'health.incident.action'),
             ('res_id', '=', action.id)])
        self.assertTrue(activities)
        self.assertEqual(activities[0].date_deadline, action.due_date)
        self.assertEqual(activities[0].user_id, self.env.user)
        action.action_start()
        self.assertEqual(action.state, 'in_progress')
        action.action_done()
        self.assertEqual(action.state, 'done')
        self.assertEqual(action.completed_date, fields.Date.today())
        remaining = self.env['mail.activity'].search(
            [('res_model', '=', 'health.incident.action'),
             ('res_id', '=', action.id)])
        self.assertFalse(remaining)
        self.assertEqual(incident.open_action_count, 0)
        self.assertEqual(incident.action_count, 1)

    def test_action_cancel(self):
        incident = self._make_incident()
        action = self._make_action(incident)
        action.action_cancel_action()
        self.assertEqual(action.state, 'cancelled')
        with self.assertRaises(UserError):
            action.action_start()

    # ------------------------------------------------------------------
    # Acceptance #10 — reopen restricted to manager+ (group check is
    # bypassed for admin; state guard still applies)
    # ------------------------------------------------------------------
    def test_reopen(self):
        incident = self._make_incident(severity='1')
        with self.assertRaises(UserError):
            incident.action_reopen()  # not closed yet
        incident.action_close_minor()
        incident.action_reopen()
        self.assertEqual(incident.state, 'under_review')
        self.assertFalse(incident.closed_date)
        self.assertFalse(incident.closed_by_id)

    # ------------------------------------------------------------------
    # Binding design decision — severity 4-5 incidents are append-only
    # after closing (no edits below manager)
    # ------------------------------------------------------------------
    def test_closed_severe_append_only(self):
        from odoo.exceptions import AccessError
        incident = self._make_incident(
            severity='5',
            notified_authority='Sở Y tế',
            notified_date=fields.Date.today())
        incident.action_start_review()
        incident.investigator_id = self.env.user
        incident.action_start_investigation()
        incident.root_cause = 'Root cause'
        action = self._make_action(incident)
        incident.action_assign_actions()
        action.action_done()
        incident.action_close()
        self.assertEqual(incident.state, 'closed')
        head_nurse = self.env['res.users'].create({
            'name': 'Incident Test Head Nurse',
            'login': 'incident_test_head_nurse',
            'group_ids': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref(
                    'health_base.group_healthcare_head_nurse').id,
            ])],
            'catchment_province_id': self.province.id,
        })
        with self.assertRaises(AccessError):
            incident.with_user(head_nurse).write(
                {'location': 'Edited after close'})
        # Manager-level (admin bypass) edits still work.
        incident.write({'location': 'Manager amendment'})
        self.assertEqual(incident.location, 'Manager amendment')

    # ------------------------------------------------------------------
    # Register aggregates (spec §5.4)
    # ------------------------------------------------------------------
    def test_get_register(self):
        self._make_incident(incident_type='fall', severity='4')
        self._make_incident(incident_type='injury', severity='2')
        overdue_incident = self._make_incident(incident_type='injury')
        self._make_action(
            overdue_incident,
            due_date=fields.Date.today() - timedelta(days=3))
        register = self.Incident.get_register(
            fields.Datetime.now() - timedelta(days=1),
            fields.Datetime.now() + timedelta(days=1))
        self.assertGreaterEqual(register['notifiable_count'], 1)
        self.assertGreaterEqual(register['overdue_action_count'], 1)
        total = sum(group['count'] for group in register['counts'])
        self.assertGreaterEqual(total, 3)

    # ------------------------------------------------------------------
    # Configurable notifiable types (binding design decision)
    # ------------------------------------------------------------------
    def test_notifiable_types_param(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'health_incident.notifiable_types', 'medication_error')
        incident = self._make_incident(
            incident_type='medication_error', severity='2')
        self.assertTrue(incident.notifiable)

    # ------------------------------------------------------------------
    # PWA idempotency key (acceptance #8, model side)
    # ------------------------------------------------------------------
    def test_client_mutation_id_lookup(self):
        incident = self._make_incident(
            client_mutation_id='test-mutation-0001')
        found = self.Incident.search(
            [('client_mutation_id', '=', 'test-mutation-0001')])
        self.assertEqual(found, incident)

    # ------------------------------------------------------------------
    # copy() duplicates corrective actions explicitly (Odoo 19 gotcha)
    # ------------------------------------------------------------------
    def test_copy_duplicates_actions(self):
        incident = self._make_incident()
        self._make_action(incident)
        duplicate = incident.copy()
        self.assertEqual(duplicate.state, 'reported')
        self.assertEqual(len(duplicate.action_ids), 1)
        self.assertNotEqual(duplicate.action_ids, incident.action_ids)
