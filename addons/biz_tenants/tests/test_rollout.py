# -*- coding: utf-8 -*-
"""The rollout, on a database — the guards, the lock, and the acts a pure test
cannot reach.

⚠ THE SUITE HAS TO STAND DOWN THE REAL FLEET FIRST (ledger F28). A
`TransactionCase` on the platform's own database runs against REAL customer
rows and REAL rollouts: a live customer joins every plan (so `filtered()` stops
being a singleton), and one genuinely stopped rollout makes every test in here
fail with "a release is already going out" — which is the guard working,
against the suite. `setUp` closes the real customers and calls off the real
rollouts INSIDE the transaction, which is rolled back and never reaches them.
"""
import os
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from odoo.addons.biz_tenants.models import tenants_common as common


@tagged('post_install', '-at_install')
class RolloutCase(TransactionCase):
    """The base every rollout test sits on, and the stand-down that makes it
    safe to run on the platform's own database."""

    def setUp(self):
        super().setUp()
        self.service = self.env['biz.tenants']
        # ⚠ F28. Inside the transaction, and rolled back with it.
        self.env['biz.rollout'].sudo().search(
            [('state', 'not in', ('done', 'aborted'))]).write(
                {'state': 'aborted', 'note': 'stood down by the test suite'})
        self.env['biz.tenant'].sudo().search(
            [('state', '!=', 'decommissioned')]).write(
                {'state': 'decommissioned'})
        self.release = self.env['biz.release'].sudo().create({
            'name': 'ZZ-test-1', 'cut_on': fields.Datetime.now(),
            'notes': 'What changed, written for the customer.',
            'module_fingerprint': '{}', 'module_count': 1,
        })
        self.tenant = self.env['biz.tenant'].sudo().create({
            'name': 'Ann Ltd', 'slug': 'zzannrollout', 'state': 'live',
            'ring': 'canary', 'tz': 'Asia/Ho_Chi_Minh',
        })

    def _plan(self):
        """A plan whose steps name no database this machine has to have."""
        return {
            'tasks': [
                {'sequence': 10, 'ring': 'rehearsal',
                 'target_db': '%s-staging' % self.tenant.slug,
                 'label': 'Ann Ltd (practice copy)', 'tenant_id': None,
                 'source_tenant_id': self.tenant.id},
                {'sequence': 20, 'ring': 'canary', 'target_db':
                 self.tenant.slug, 'label': 'Ann Ltd',
                 'tenant_id': self.tenant.id, 'source_tenant_id': None},
            ],
            'excluded': [], 'warnings': [],
            'release': {'id': self.release.id, 'name': self.release.name},
        }


@tagged('post_install', '-at_install')
class TestBlockers(RolloutCase):
    """T4 — rail R4 is enforced, not hoped for."""

    def test_no_copy_to_practise_on_blocks_the_start_by_name(self):
        """⚠ Ledger F31. With the only usable copy moved aside, the planner
        shrugged, left the practice run out and offered to update a real
        customer with nobody having rehearsed anything. It is a BLOCKER, and it
        names the customer and the button that fixes it."""
        with patch.object(type(self.service), '_master_behind',
                          return_value=[]), \
             patch.object(type(self.service), '_tenancy_installed',
                          return_value=True):
            blockers = self.service._rollout_blockers(
                self.release, [], self.service._plan_for(self.release))
        joined = '\n'.join(blockers)
        self.assertIn('no copy to practise on', joined)
        self.assertIn('Ann Ltd', joined)
        self.assertIn('Copy now', joined)

    def test_a_release_with_no_notes_is_blocked_because_customers_read_them(self):
        self.release.notes = ''
        with patch.object(type(self.service), '_master_behind',
                          return_value=[]), \
             patch.object(type(self.service), '_tenancy_installed',
                          return_value=True), \
             patch.object(type(self.service), '_rehearsal_source',
                          return_value={'id': self.tenant.id,
                                        'name': 'Ann Ltd', 'slug': 'x'}):
            blockers = self.service._rollout_blockers(
                self.release, [], self.service._plan_for(self.release))
        self.assertTrue([b for b in blockers if 'what changed' in b])

    def test_a_platform_behind_its_own_files_sends_nothing_out(self):
        with patch.object(type(self.service), '_master_behind',
                          return_value=['health_base']), \
             patch.object(type(self.service), '_tenancy_installed',
                          return_value=True), \
             patch.object(type(self.service), '_rehearsal_source',
                          return_value={'id': self.tenant.id,
                                        'name': 'Ann Ltd', 'slug': 'x'}):
            blockers = self.service._rollout_blockers(
                self.release, [], self.service._plan_for(self.release))
        self.assertTrue([b for b in blockers if 'health_base' in b])

    def test_a_customer_with_no_platform_link_is_named(self):
        with patch.object(type(self.service), '_master_behind',
                          return_value=[]), \
             patch.object(type(self.service), '_rehearsal_source',
                          return_value={'id': self.tenant.id,
                                        'name': 'Ann Ltd', 'slug': 'x'}):
            blockers = self.service._rollout_blockers(
                self.release, ['Ann Ltd'], self.service._plan_for(self.release))
        self.assertTrue([b for b in blockers if 'cannot be told anything' in b])


@tagged('post_install', '-at_install')
class TestOneAtATime(RolloutCase):
    """T3 — ONE ROLLOUT AT A TIME, ENFORCED BY THE DATABASE."""

    def _start(self):
        return self.service.rollout_start(self.release.id)

    def test_a_second_start_gets_the_refusal_and_never_a_second_rollout(self):
        """⚠ Ledger F50. Two presses inside ninety seconds are two rollouts
        that destroy each other's practice copy, because the whole practice run
        happens BEFORE the first one commits and the second press cannot see it.

        The lock is `pg_advisory_xact_lock`, held to the end of the
        transaction. Inside ONE transaction it is re-entrant — which is what
        lets this test run at all — so what is proved here is the other half:
        the second call is refused BY NAME, and exactly one rollout exists
        afterwards. That the lock is taken on the first line, before anything
        else happens, is asserted on the source in `test_generic`.
        """
        Rollout = self.env['biz.rollout'].sudo()
        before = Rollout.search_count([])
        with patch.object(type(self.service), '_plan_for',
                          return_value=self._plan()), \
             patch.object(type(self.service), '_master_behind',
                          return_value=[]), \
             patch.object(type(self.service), '_tenancy_installed',
                          return_value=True), \
             patch.object(type(self.service), '_rollout_tick',
                          return_value={'ok': True}):
            self._start()
            self.assertEqual(Rollout.search_count([]), before + 1)
            with self.assertRaises(UserError) as caught:
                self._start()
        self.assertIn('already going out', str(caught.exception))
        self.assertIn('practice copy has one name', str(caught.exception))
        self.assertEqual(Rollout.search_count([]), before + 1)

    def test_the_first_ring_is_the_practice_run_and_it_runs_at_once(self):
        ticked = []
        with patch.object(type(self.service), '_plan_for',
                          return_value=self._plan()), \
             patch.object(type(self.service), '_master_behind',
                          return_value=[]), \
             patch.object(type(self.service), '_tenancy_installed',
                          return_value=True), \
             patch.object(type(self.service), '_rollout_tick',
                          side_effect=lambda r: ticked.append(r.id)):
            self._start()
        rollout = self.env['biz.rollout'].sudo().search([], order='id desc',
                                                        limit=1)
        self.assertEqual(rollout.ring, 'rehearsal')
        self.assertEqual(rollout.state, 'rehearsing')
        self.assertEqual(ticked, [rollout.id])
        self.assertEqual(len(rollout.task_ids), 2)


@tagged('post_install', '-at_install')
class TestTheControls(RolloutCase):
    """Every button, and the refusals that say what to press instead."""

    def _rollout(self, **kw):
        vals = {'release_id': self.release.id, 'state': 'running',
                'ring': 'canary', 'started_at': fields.Datetime.now()}
        vals.update(kw)
        rollout = self.env['biz.rollout'].sudo().create(vals)
        self.canary = self.env['biz.rollout.task'].sudo().create({
            'rollout_id': rollout.id, 'ring': 'canary', 'sequence': 10,
            'tenant_id': self.tenant.id, 'label': 'Ann Ltd',
            'target_db': self.tenant.slug, 'state': 'waiting'})
        self.later = self.env['biz.rollout.task'].sudo().create({
            'rollout_id': rollout.id, 'ring': 'everyone', 'sequence': 20,
            'label': 'Bee Health', 'target_db': 'zzbee', 'state': 'waiting'})
        return rollout

    def test_run_now_on_a_later_ring_is_refused_by_name(self):
        """⚠ Ledger F30. `advance()` only ever looks at the CURRENT ring, so
        setting the flag on a later one does NOTHING AT ALL — silently. It is a
        refusal that names the ring and points at the button that does what the
        person actually meant."""
        self._rollout()
        with self.assertRaises(UserError) as caught:
            self.service.task_run_now(self.later.id)
        message = str(caught.exception)
        self.assertIn('Bee Health', message)
        self.assertIn('later ring', message)
        self.assertIn('Continue now', message)
        self.assertFalse(self.later.run_now)

    def test_run_now_inside_the_current_ring_is_allowed_and_recorded(self):
        rollout = self._rollout()
        with patch.object(type(self.service), '_rollout_tick',
                          return_value={'ok': True}):
            self.service.task_run_now(self.canary.id)
        self.assertTrue(self.canary.run_now)
        self.assertEqual(self.canary.run_now_by, self.env.user)
        self.assertIn('rather than in their own window',
                      rollout.log)

    def test_leaving_a_customer_behind_needs_their_short_name_typed(self):
        self._rollout()
        with self.assertRaises(UserError) as caught:
            self.service.task_skip(self.canary.id, 'wrong')
        self.assertIn(self.tenant.slug, str(caught.exception))
        with patch.object(type(self.service), '_rollout_tick',
                          return_value={'ok': True}):
            self.service.task_skip(self.canary.id, self.tenant.slug)
        self.assertEqual(self.canary.state, 'skipped')

    def test_carrying_on_around_a_failure_is_refused_by_name(self):
        """Carrying on around a failure is how a customer gets forgotten."""
        rollout = self._rollout(state='paused')
        self.canary.state = 'failed'
        with self.assertRaises(UserError) as caught:
            self.service.rollout_resume(rollout.id)
        self.assertIn('Ann Ltd', str(caught.exception))
        self.assertIn('still marked failed', str(caught.exception))

    def test_trying_a_failed_step_again_puts_the_rollout_back_to_running(self):
        rollout = self._rollout(state='paused', note='It fell over.')
        self.canary.state = 'failed'
        with patch.object(type(self.service), '_rollout_tick',
                          return_value={'ok': True}):
            self.service.task_retry(self.canary.id)
        self.assertEqual(self.canary.state, 'waiting')
        self.assertEqual(rollout.state, 'running')
        self.assertFalse(rollout.note)

    def test_calling_it_off_needs_the_release_named_and_leaves_the_rest_behind(self):
        rollout = self._rollout()
        with self.assertRaises(UserError):
            self.service.rollout_abort(rollout.id, 'nope')
        self.service.rollout_abort(rollout.id, self.release.name)
        self.assertEqual(rollout.state, 'aborted')
        self.assertEqual(self.canary.state, 'skipped')
        self.assertEqual(self.later.state, 'skipped')

    def test_continue_now_only_applies_while_something_is_being_watched(self):
        rollout = self._rollout(state='running')
        with self.assertRaises(UserError) as caught:
            self.service.rollout_continue_now(rollout.id)
        self.assertIn('Nothing is being watched', str(caught.exception))

    def test_pausing_records_who_did_it_and_why(self):
        rollout = self._rollout()
        with patch.object(type(self.service), '_rollout_tick',
                          return_value={'ok': True}):
            self.service.rollout_pause(rollout.id)
        self.assertEqual(rollout.state, 'paused')
        self.assertIn(self.env.user.name, rollout.note)


@tagged('post_install', '-at_install')
class TestTheHealthGate(RolloutCase):
    """T5 — the gate, its ignore list, and the window it measures."""

    LINES = [
        '2026-09-04 10:00:00,001 2994560 ERROR zzannrollout odoo.modules: '
        'something went wrong\n',
        '2026-09-04 10:00:01,001 2994560 ERROR zzannrollout vendor.licence: '
        'License check FAILED\n',
        '2026-09-04 09:00:00,001 2994560 ERROR zzannrollout odoo.modules: '
        'before the window\n',
        '2026-09-04 10:00:02,001 2994560 ERROR zzsomebodyelse odoo.modules: '
        "somebody else's problem\n",
        '2026-09-04 10:00:03,001 2994560 INFO zzannrollout odoo.modules: '
        'fine\n',
    ]

    def test_ignored_lines_are_counted_and_recorded_never_dropped(self):
        """⚠ Ledger F25. A gate that cries wolf on every run is a gate somebody
        learns to click past — and one that hides what it ignored cannot be
        checked by anybody."""
        self.env['ir.config_parameter'].sudo().set_param(
            common.P_HEALTH_IGNORE, 'license check failed')
        with patch.object(type(self.service), '_log_tail_lines',
                          return_value=self.LINES), \
             patch.object(type(self.service), '_probe',
                          return_value=(200, 12)):
            gate = self.service._health_gate(
                'zzannrollout', '2026-09-04 09:30:00', 0, 'x.example')
        self.assertFalse(gate['ok'])
        self.assertEqual(gate['error_count'], 1)
        self.assertEqual(gate['ignored_count'], 1)
        self.assertEqual(len(gate['ignored']), 1)
        self.assertIn('License check FAILED', gate['ignored'][0])

    def test_the_window_starts_where_it_is_told_to(self):
        """⚠ Ledger F26. A restore writes errors of its own, so a practice
        run's window starts when the UPDATE starts, not when the restore
        does."""
        with patch.object(type(self.service), '_log_tail_lines',
                          return_value=self.LINES):
            late = self.service._health_gate('zzannrollout',
                                             '2026-09-04 09:30:00', 0)
            early = self.service._health_gate('zzannrollout',
                                              '2026-09-04 08:00:00', 0)
        self.assertEqual(late['error_count'], 2)     # nothing ignored here
        self.assertEqual(early['error_count'], 3)    # the earlier line joins

    def test_it_reads_only_the_system_it_was_asked_about(self):
        with patch.object(type(self.service), '_log_tail_lines',
                          return_value=self.LINES):
            gate = self.service._health_gate('zzannrollout',
                                             '2026-09-04 09:30:00', 0)
        for line in gate['errors']:
            self.assertIn('zzannrollout', line)

    def test_a_log_that_cannot_be_read_is_said_and_never_reported_as_clean(self):
        with patch.object(type(self.service), '_log_tail_lines',
                          return_value=None):
            gate = self.service._health_gate('zzannrollout', '2026-01-01', 0)
        self.assertTrue(gate['ok'])
        self.assertEqual(gate['error_count'], -1)
        self.assertIn('could not be read', gate['reason'])

    def test_the_sweep_reads_the_log_ONCE_for_every_system_it_cares_about(self):
        """⚠ Ledger F39. One pass per customer would be twenty megabytes of
        reading per customer per sweep."""
        calls = []

        def tail(_self):
            calls.append(1)
            return self.LINES

        with patch.object(type(self.service), '_log_tail_lines', tail):
            counts = self.service._log_error_counts(
                ['zzannrollout', 'zzsomebodyelse', self.env.cr.dbname],
                '2026-09-04 09:30:00')
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(counts['zzannrollout']['errors']), 2)
        self.assertEqual(len(counts['zzsomebodyelse']['errors']), 1)
        self.assertEqual(counts[self.env.cr.dbname]['errors'], [])


@tagged('post_install', '-at_install')
class TestThePracticeCopyAlwaysGoes(RolloutCase):
    """T4 — the copy is dropped in a `finally` that wraps the restore ITSELF."""

    def _task(self):
        rollout = self.env['biz.rollout'].sudo().create({
            'release_id': self.release.id, 'state': 'rehearsing',
            'ring': 'rehearsal'})
        return self.env['biz.rollout.task'].sudo().create({
            'rollout_id': rollout.id, 'ring': 'rehearsal', 'sequence': 10,
            'source_tenant_id': self.tenant.id,
            'label': 'Ann Ltd (practice copy)',
            'target_db': '%s-staging' % self.tenant.slug})

    def test_a_restore_that_falls_over_still_drops_the_copy(self):
        """⚠ Ledger F26. With the restore OUTSIDE the try, a damaged copy left
        a part-built system behind on a machine with two gigabytes of memory —
        which is the one outcome this whole method exists to make impossible."""
        dropped = []
        task = self._task()
        with patch.object(type(self.service), 'restore_to_staging',
                          side_effect=RuntimeError('the file is damaged')), \
             patch.object(type(self.service), 'drop_staging',
                          side_effect=lambda tid: dropped.append(tid)):
            with self.assertRaises(UserError) as caught:
                self.service._run_rehearsal(task)
        self.assertEqual(dropped, [self.tenant.id])
        message = str(caught.exception)
        self.assertIn('Ann Ltd', message)
        self.assertIn('Copy now', message)
        self.assertIn('Nothing has been done to Ann Ltd themselves', message)

    def test_a_practice_run_that_works_still_drops_the_copy(self):
        dropped = []
        task = self._task()
        with patch.object(type(self.service), 'restore_to_staging',
                          return_value={'ok': True, 'from_backup': 'x.dump'}), \
             patch.object(type(self.service), '_run_unit',
                          return_value={'skipped_count': 0}), \
             patch.object(type(self.service), '_log_tail_lines',
                          return_value=[]), \
             patch.object(type(self.service), 'drop_staging',
                          side_effect=lambda tid: dropped.append(tid)):
            _res, health = self.service._run_rehearsal(task)
        self.assertEqual(dropped, [self.tenant.id])
        self.assertTrue(health['ok'])

    def test_a_copy_that_will_not_drop_is_said_out_loud(self):
        task = self._task()
        with patch.object(type(self.service), 'restore_to_staging',
                          return_value={'ok': True, 'from_backup': 'x.dump'}), \
             patch.object(type(self.service), '_run_unit',
                          return_value={'skipped_count': 0}), \
             patch.object(type(self.service), '_log_tail_lines',
                          return_value=[]), \
             patch.object(type(self.service), 'drop_staging',
                          side_effect=RuntimeError('still connected')):
            self.service._run_rehearsal(task)
        self.assertIn('could NOT be deleted', task.rollout_id.log)


@tagged('post_install', '-at_install')
class TestTheWorkerCommitsPerSystem(RolloutCase):
    """⚠ F29 / H69 — A TEST CURSOR'S COMMIT REFUSAL IS BOLTED TO THE INSTANCE.

    `patch.object(type(self.env.cr), 'commit', …)` does nothing and the
    framework raises "Cannot commit or rollback a cursor from inside a test"
    anyway. `patch.object(self.env.cr, 'commit', …)` — the OBJECT — is what
    lets a scheduled job that commits per customer be tested at all. Written
    down a third time because this repo keeps tripping over it.
    """

    def test_the_scheduled_worker_does_nothing_when_nobody_started_anything(self):
        commits = []
        with patch.object(self.env.cr, 'commit',
                          side_effect=lambda: commits.append(1)):
            self.assertFalse(self.service._cron_rollout_worker())
        self.assertEqual(commits, [])

    def test_the_scheduled_worker_takes_one_step_and_commits(self):
        rollout = self.env['biz.rollout'].sudo().create({
            'release_id': self.release.id, 'state': 'running',
            'ring': 'canary'})
        commits = []
        with patch.object(self.env.cr, 'commit',
                          side_effect=lambda: commits.append(1)), \
             patch.object(type(self.service), '_rollout_tick',
                          return_value={'ok': True}):
            self.assertTrue(self.service._cron_rollout_worker())
        self.assertEqual(len(commits), 1)
        self.assertTrue(rollout.exists())


@tagged('post_install', '-at_install')
class TestOneCustomerSWindow(RolloutCase):
    """The Updates tab: the ring, the hour, and the sentence with the zone."""

    def test_the_window_is_shown_in_their_clock_with_the_zone_named(self):
        data = self.service.tenant_updates(self.tenant.id)
        self.assertIn('their time', data['next_window'])
        self.assertIn('Asia/Ho_Chi_Minh', data['next_window'])
        self.assertEqual(data['tz'], 'Asia/Ho_Chi_Minh')

    def test_an_hour_outside_the_clock_is_refused(self):
        for bad in (-1, 24, 99):
            with self.assertRaises(UserError):
                self.service.tenant_set_window(self.tenant.id, start_hour=bad)

    def test_a_window_longer_than_half_a_day_is_not_a_window(self):
        with self.assertRaises(UserError) as caught:
            self.service.tenant_set_window(self.tenant.id, hours=20)
        self.assertIn('not a window', str(caught.exception))

    def test_a_ring_that_is_not_a_ring_is_refused(self):
        with self.assertRaises(UserError):
            self.service.tenant_set_window(self.tenant.id, ring='rehearsal')

    def test_changing_it_leaves_a_line_on_their_own_trail(self):
        self.service.tenant_set_window(self.tenant.id, ring='early',
                                       start_hour=2, hours=4)
        self.assertEqual(self.tenant.ring, 'early')
        self.assertEqual(self.tenant.maintenance_start, 2)
        self.assertIn('Update settings changed', self.tenant.provision_log)


@tagged('post_install', '-at_install')
class TestTheReleaseStampWaitsForTheGate(RolloutCase):
    """A customer must never be shown "you are on release X — here is what
    changed" about an update that is about to be called a failure."""

    def test_inside_a_rollout_the_stamp_is_deferred(self):
        plan = {'release_state': 'on', 'database': 'zz'}
        pushed = []
        with patch.object(type(self.service), 'push_settings',
                          side_effect=lambda *a, **k: pushed.append(a)):
            self.service.with_context(
                biz_defer_release_stamp=True)._push_release_stamp(
                    self.tenant.id, plan, self.release, lambda *a, **k: None)
        self.assertEqual(pushed, [])
        self.assertTrue(plan['release_deferred'])

    def test_outside_a_rollout_it_happens_as_it_always_did(self):
        plan = {'release_state': 'on', 'database': 'zz'}
        with patch.object(type(self.service), 'push_settings',
                          return_value={'ok': True}):
            self.service._push_release_stamp(
                self.tenant.id, plan, self.release, lambda *a, **k: None)
        self.assertTrue(plan['release_pushed'])
