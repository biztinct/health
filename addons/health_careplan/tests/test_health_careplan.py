# -*- coding: utf-8 -*-
"""health_careplan acceptance tests (clinical spec §1.10)."""
from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError, ValidationError
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
            'name': 'Test Careplan Province',
            'code': 'TCP',
        })
    facility = Facility.search(
        [('catchment_province_id', '=', province.id)], limit=1)
    if not facility:
        facility = Facility.create({
            'name': 'Test Careplan Facility',
            'code': 'TCF',
            'street': '1 Careplan Street',
            'city': 'Test City',
            'catchment_province_id': province.id,
        })
    patient = Partner.create({
        'name': 'Careplan Test Patient',
        'is_patient': True,
        'catchment_province_id': province.id,
        'primary_facility_id': facility.id,
    })
    return province, facility, patient


@tagged('post_install', '-at_install')
class TestHealthCareplan(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.province, cls.facility, cls.patient = _get_fixture(cls.env)
        cls.Careplan = cls.env['health.careplan']
        cls.Task = cls.env['health.careplan.task']
        cls.type_hr = cls.env.ref('health_vitals.vitals_type_heart_rate')

    def _make_plan(self, activate=True, frequency='every_visit',
                   frequency_interval=1, visit_filter='all', **plan_vals):
        plan = self.Careplan.create(dict({
            'client_id': self.patient.id,
            'category': 'home_care',
            'title': 'Test plan',
            'period_start': fields.Date.today() - timedelta(days=10),
        }, **plan_vals))
        self.env['health.careplan.goal'].create({
            'careplan_id': plan.id,
            'name': 'Keep heart rate in range',
            'vitals_type_id': self.type_hr.id,
            'target_value_min': 55,
            'target_value_max': 95,
        })
        self.env['health.careplan.activity'].create({
            'careplan_id': plan.id,
            'name': 'Check vital signs',
            'frequency': frequency,
            'frequency_interval': frequency_interval,
            'visit_filter': visit_filter,
        })
        if activate:
            plan.action_activate()
        return plan

    def _make_fso(self, days_ahead=1, confirm=True, **vals):
        order = self.env['health.fieldservice.order'].create(dict({
            'patient_id': self.patient.id,
            'facility_id': self.facility.id,
            'scheduled_datetime': fields.Datetime.now()
            + timedelta(days=days_ahead),
        }, **vals))
        if confirm and order.state != 'confirmed':
            order.write({'state': 'confirmed'})
        return order

    def _force_fso_state(self, orders, state):
        """Bypass the FSO completion automation (notifications,
        invoicing checks) — only the stored state matters for the
        drift computation under test."""
        self.env.flush_all()
        self.env.cr.execute(
            'UPDATE health_fieldservice_order SET state = %s '
            'WHERE id IN %s', (state, tuple(orders.ids)))
        self.env.invalidate_all()

    # ------------------------------------------------------------------
    # Acceptance #1 — activation guards
    # ------------------------------------------------------------------
    def test_activate(self):
        plan = self._make_plan(activate=False)
        plan.action_activate()
        self.assertEqual(plan.state, 'active')
        self.assertEqual(plan.name[:2], 'CP')

    def test_activate_requires_goals(self):
        plan = self.Careplan.create({
            'client_id': self.patient.id,
            'category': 'chronic',
        })
        with self.assertRaises(UserError):
            plan.action_activate()

    # ------------------------------------------------------------------
    # Acceptance #9 — one active plan per client + category
    # ------------------------------------------------------------------
    def test_one_active_per_category(self):
        self._make_plan()
        with self.assertRaises(ValidationError):
            self._make_plan()

    # ------------------------------------------------------------------
    # Acceptance #2 — compilation on confirm, idempotent re-save
    # ------------------------------------------------------------------
    def test_compile_on_confirm(self):
        plan = self._make_plan()
        order = self._make_fso()
        tasks = order.careplan_task_ids
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks.careplan_id, plan)
        self.assertEqual(tasks.state, 'pending')
        self.assertEqual(tasks.name, 'Check vital signs')
        self.assertEqual(tasks.catchment_province_id, self.province)
        # Re-saving the FSO does not duplicate tasks.
        order.write({'scheduled_datetime': order.scheduled_datetime
                     + timedelta(hours=2)})
        self.assertEqual(len(order.careplan_task_ids), 1)
        self.assertEqual(order.careplan_task_count, 1)
        self.assertTrue(order.has_open_careplan_tasks)

    def test_no_compile_for_draft_plan(self):
        self._make_plan(activate=False)
        order = self._make_fso()
        self.assertFalse(order.careplan_task_ids)

    def test_visit_filter(self):
        self._make_plan(visit_filter='clinic_visit')
        order = self._make_fso(service_type='home_visit')
        self.assertFalse(order.careplan_task_ids)
        clinic = self._make_fso(days_ahead=2, service_type='clinic_visit')
        self.assertEqual(len(clinic.careplan_task_ids), 1)

    def test_cleanup_on_cancelled_activity(self):
        plan = self._make_plan()
        order = self._make_fso()
        self.assertEqual(len(order.careplan_task_ids), 1)
        plan.careplan_activity_ids.write({'status': 'cancelled'})
        order.write({'scheduled_datetime': order.scheduled_datetime
                     + timedelta(hours=1)})
        self.assertFalse(order.careplan_task_ids)

    # ------------------------------------------------------------------
    # Acceptance #3 — weekly frequency: one task per rolling window
    # ------------------------------------------------------------------
    def test_weekly_window(self):
        self._make_plan(frequency='weekly', frequency_interval=1)
        daily_orders = self.env['health.fieldservice.order']
        for day in range(1, 6):  # daily visits
            daily_orders |= self._make_fso(days_ahead=day)
        tasks = daily_orders.mapped('careplan_task_ids')
        self.assertEqual(len(tasks), 1,
                         'Weekly activity must compile on at most one '
                         'FSO per rolling 7-day window')
        # Next window gets its own task.
        later = self._make_fso(days_ahead=9)
        self.assertEqual(len(later.careplan_task_ids), 1)

    # ------------------------------------------------------------------
    # Acceptance #4 — not-done requires a reason
    # ------------------------------------------------------------------
    def test_task_tick(self):
        self._make_plan()
        order = self._make_fso()
        task = order.careplan_task_ids
        with self.assertRaises(ValidationError):
            task.action_mark_not_done()
        task.action_mark_not_done(reason='client_refused', note='asleep')
        self.assertEqual(task.state, 'not_done')
        self.assertEqual(task.not_done_reason, 'client_refused')
        self.assertEqual(task.not_done_note, 'asleep')
        self.assertEqual(task.completed_by_id, self.env.user)
        self.assertTrue(task.completed_datetime)
        # Correction: not_done → done is allowed.
        task.action_mark_done()
        self.assertEqual(task.state, 'done')
        self.assertFalse(task.not_done_reason)
        task.action_reset_pending()
        self.assertEqual(task.state, 'pending')
        self.assertFalse(task.completed_by_id)

    # ------------------------------------------------------------------
    # Acceptance #5 (model layer) — PRN tasks
    # ------------------------------------------------------------------
    def test_prn_task(self):
        plan = self._make_plan(activate=False)
        prn_activity = self.env['health.careplan.activity'].create({
            'careplan_id': plan.id,
            'name': 'PRN wound dressing',
            'frequency': 'prn',
        })
        plan.action_activate()
        order = self._make_fso()
        # PRN activities never auto-compile.
        self.assertNotIn(
            prn_activity, order.careplan_task_ids.mapped('activity_id'))
        task = self.Task.add_prn_task(order, prn_activity)
        self.assertTrue(task.is_prn)
        self.assertEqual(task.fso_id, order)
        # PRN duplicates are exempt from the uniqueness rule.
        second = self.Task.add_prn_task(order, prn_activity)
        self.assertTrue(second.exists())

    def test_uniq_activity_per_fso(self):
        plan = self._make_plan()
        order = self._make_fso()
        with self.assertRaises(ValidationError):
            self.Task.create({
                'careplan_id': plan.id,
                'activity_id': plan.careplan_activity_ids.id,
                'fso_id': order.id,
                'name': 'Duplicate',
            })

    # ------------------------------------------------------------------
    # Acceptance #7 — review cycle
    # ------------------------------------------------------------------
    def test_review_cycle(self):
        plan = self._make_plan(
            period_start=fields.Date.today() - timedelta(days=120),
            review_cycle_days=90)
        self.assertEqual(
            plan.next_review_date,
            plan.period_start + timedelta(days=90))
        self.Careplan._cron_careplan_reviews()
        self.assertEqual(plan.state, 'under_review')
        todo = self.env['mail.activity'].search([
            ('res_model', '=', 'health.careplan'),
            ('res_id', '=', plan.id),
            ('user_id', '=', plan.author_id.id),
        ])
        self.assertTrue(todo)
        version_before = plan.version
        plan.action_confirm_review()
        self.assertEqual(plan.state, 'active')
        self.assertEqual(plan.version, version_before + 1)
        self.assertEqual(plan.last_review_date, fields.Date.today())
        self.assertEqual(
            plan.next_review_date,
            fields.Date.today() + timedelta(days=90))

    # ------------------------------------------------------------------
    # Acceptance #8 — drift detection
    # ------------------------------------------------------------------
    def test_drift(self):
        self._make_plan()
        plan = self.Careplan.search([
            ('client_id', '=', self.patient.id),
            ('state', '=', 'active'),
        ], limit=1)
        orders = self.env['health.fieldservice.order']
        for day in range(1, 5):
            orders |= self._make_fso(days_ahead=day)
        tasks = orders.mapped('careplan_task_ids')
        self.assertEqual(len(tasks), 4)
        # Deliver all visits inside the trailing-30-day window (SQL to
        # sidestep the FSO scheduling/notification automations that are
        # out of scope here; scheduled_date is set alongside to keep
        # the stored compute consistent).
        delivered = fields.Datetime.now() - timedelta(days=3)
        self.env.flush_all()
        self.env.cr.execute(
            'UPDATE health_fieldservice_order '
            'SET scheduled_datetime = %s, scheduled_date = %s '
            'WHERE id IN %s',
            (delivered, delivered.date(), tuple(orders.ids)))
        self.env.invalidate_all()
        self._force_fso_state(orders, 'completed')
        # 1 of 4 done → 25% adherence < 0.8 threshold.
        tasks[0].action_mark_done()
        self.Careplan._cron_careplan_drift()
        self.assertTrue(plan.drift_flag)
        self.assertAlmostEqual(plan.adherence_rate, 0.25)
        # All done → flag clears.
        (tasks - tasks[0]).action_mark_done()
        self.Careplan._cron_careplan_drift()
        self.assertFalse(plan.drift_flag)
        self.assertAlmostEqual(plan.adherence_rate, 1.0)

    # ------------------------------------------------------------------
    # Goal progress from health_vitals observations
    # ------------------------------------------------------------------
    def test_goal_progress(self):
        plan = self._make_plan()
        goal = plan.goal_ids
        self.assertFalse(goal.is_on_target)
        self.env['health.observation'].create_coded(
            self.patient.id, 'hr', 72)
        goal.invalidate_recordset(
            ['latest_value', 'latest_value_date', 'is_on_target'])
        self.assertEqual(goal.latest_value, 72)
        self.assertTrue(goal.is_on_target)
        self.env['health.observation'].create_coded(
            self.patient.id, 'hr', 120)
        goal.invalidate_recordset(
            ['latest_value', 'latest_value_date', 'is_on_target'])
        self.assertEqual(goal.latest_value, 120)
        self.assertFalse(goal.is_on_target)

    # ------------------------------------------------------------------
    # Cancel unlinks pending tasks on future visits
    # ------------------------------------------------------------------
    def test_cancel_unlinks_pending(self):
        plan = self._make_plan()
        order = self._make_fso()
        done_order = self._make_fso(days_ahead=2)
        done_order.careplan_task_ids.action_mark_done()
        plan.action_cancel()
        self.assertEqual(plan.state, 'cancelled')
        self.assertFalse(order.careplan_task_ids)
        self.assertTrue(done_order.careplan_task_ids)

    # ------------------------------------------------------------------
    # copy() duplicates goals + activities explicitly (Odoo 19 gotcha)
    # ------------------------------------------------------------------
    def test_copy_duplicates_children(self):
        plan = self._make_plan(activate=False)
        duplicate = plan.copy()
        self.assertEqual(duplicate.state, 'draft')
        self.assertEqual(len(duplicate.goal_ids), 1)
        self.assertEqual(len(duplicate.careplan_activity_ids), 1)
        self.assertNotEqual(duplicate.goal_ids, plan.goal_ids)

    # ------------------------------------------------------------------
    # Period constraint
    # ------------------------------------------------------------------
    def test_period_constraint(self):
        with self.assertRaises(ValidationError):
            self.Careplan.create({
                'client_id': self.patient.id,
                'period_start': fields.Date.today(),
                'period_end': fields.Date.today() - timedelta(days=1),
            })
