# -*- coding: utf-8 -*-
"""The rollout's judgements, hammered without a second database anywhere.

Everything a rollout DOES needs another system, a restore and a log; every
DECISION it takes is in `rollout_rules.py` and needs nothing at all. This file
is what makes "what will it do at three in the morning" a question with an
answer rather than a thing to find out on a customer.
"""
from datetime import datetime, timedelta

from odoo.tests import TransactionCase, tagged

from odoo.addons.biz_tenants.models.rollout_rules import (
    CUSTOMER_RINGS, DEFAULT_HOURS, DEFAULT_START_HOUR, RING_LABEL, RING_MEANING,
    RING_ORDER, STUCK_MINUTES, advance, eligible, filter_errors, health_verdict,
    next_window, notice_for, plan_tasks, render_range, say_window, to_local,
    watch_hours_for, window_bounds, window_open,
)

#: A fixed instant so nothing here depends on when it is run. 08:00 UTC is
#: 15:00 in Ho Chi Minh City — daytime there, so a 22:00 window is CLOSED.
NOW = datetime(2026, 9, 4, 8, 0, 0)
VN = 'Asia/Ho_Chi_Minh'


def _task(**kw):
    row = {'id': 1, 'ring': 'canary', 'state': 'waiting', 'run_now': False,
           'label': 'A customer', 'tz': VN,
           'maintenance_start': DEFAULT_START_HOUR,
           'maintenance_hours': DEFAULT_HOURS,
           'started_at': None, 'error': ''}
    row.update(kw)
    return row


def _snap(tasks, **kw):
    row = {'state': 'running', 'current_ring': 'canary', 'ring_done_at': None,
           'watch_skipped': False, 'watch_hours': {'canary': 24, 'early': 48},
           'watch_health': [], 'tasks': tasks}
    row.update(kw)
    return row


@tagged('post_install', '-at_install')
class TestWindows(TransactionCase):
    """T2 — a window is stored in UTC and SAID in the customer's clock."""

    def test_the_window_is_a_wall_clock_band_where_the_customer_is(self):
        # 15:00 in Ho Chi Minh City: their 22:00 window is shut.
        self.assertFalse(window_open(NOW, VN, 22, 3))
        # 22:30 there is 15:30 UTC.
        self.assertTrue(window_open(datetime(2026, 9, 4, 15, 30), VN, 22, 3))

    def test_a_window_that_runs_past_midnight_wraps(self):
        """22:00 for three hours ends at 01:00 the next day, and that is the
        case everybody gets wrong."""
        # 00:30 local is 17:30 UTC the previous day.
        self.assertTrue(window_open(datetime(2026, 9, 3, 17, 30), VN, 22, 3))
        # 01:30 local — half an hour after it shut.
        self.assertFalse(window_open(datetime(2026, 9, 3, 18, 30), VN, 22, 3))

    def test_the_next_window_is_built_from_the_local_wall_clock(self):
        opens = next_window(NOW, VN, 22, 3)
        # 22:00 in a +07:00 zone is 15:00 UTC the same day.
        self.assertEqual(opens, datetime(2026, 9, 4, 15, 0))

    def test_an_open_window_answers_now(self):
        moment = datetime(2026, 9, 4, 16, 0)
        self.assertEqual(next_window(moment, VN, 22, 3), moment)

    def test_the_bounds_are_the_opening_and_the_closing(self):
        opens, closes = window_bounds(NOW, VN, 22, 3)
        self.assertEqual(opens, datetime(2026, 9, 4, 15, 0))
        self.assertEqual(closes, datetime(2026, 9, 4, 18, 0))

    def test_the_operator_s_preview_equals_what_is_delivered(self):
        """Ledger F17: the conversion happens once, in one direction, and the
        window the screen shows is the window the worker will use."""
        opens, closes = window_bounds(NOW, VN, 22, 3)
        local_open, local_close = to_local(opens, VN), to_local(closes, VN)
        self.assertEqual(local_open.hour, 22)
        self.assertEqual(local_close.hour, 1)
        self.assertTrue(window_open(opens, VN, 22, 3))

    def test_the_window_is_said_with_its_zone_named(self):
        """⚠ Ledger F32. `render_range` formats whatever it is handed and will
        happily print a lie; a correctly-converted window printed WITHOUT its
        zone beside it reads exactly like one that was never converted."""
        opens, closes = window_bounds(NOW, VN, 22, 3)
        said = say_window(to_local(opens, VN), to_local(closes, VN),
                          to_local(NOW, VN), VN)
        self.assertIn('22:00', said)
        self.assertIn('01:00', said)
        self.assertIn('their time', said)
        self.assertIn(VN, said)

    def test_handing_the_renderer_utc_prints_the_wrong_hour(self):
        """The trap itself, asserted, so nobody has to rediscover it: the same
        window rendered from UTC says 15:00 where the customer's own bar says
        22:00."""
        opens, closes = window_bounds(NOW, VN, 22, 3)
        wrong = render_range(opens, closes, NOW)
        right = render_range(to_local(opens, VN), to_local(closes, VN),
                             to_local(NOW, VN))
        self.assertIn('15:00', wrong)
        self.assertIn('22:00', right)
        self.assertNotEqual(wrong, right)

    def test_an_unknown_zone_falls_back_rather_than_stopping(self):
        """The wrong hour is survivable. A rollout that silently stops is not."""
        self.assertIsNotNone(next_window(NOW, 'Mars/Olympus', 22, 3))

    def test_an_unset_window_is_falsy_safe(self):
        """⚠ Ledger F23. An unset Datetime reads as `False`, not `None`, and a
        plain `is None` lets the boolean through to the next line."""
        self.assertEqual(advance(_snap([], ring_done_at=False), NOW), ('done',))
        row = _snap([_task(state='running', started_at=False)])
        # A running step with no start time must not raise; it waits.
        self.assertEqual(advance(row, NOW)[0], 'wait')
        self.assertIsNone(to_local(False, VN))
        self.assertEqual(render_range(False, False, NOW), '')


@tagged('post_install', '-at_install')
class TestPlan(TransactionCase):
    """T1 — the plan, and rail R4 inside it."""

    def test_the_practice_run_is_always_first(self):
        plan = plan_tasks({'id': 1, 'name': 'R'},
                          [{'id': 7, 'name': 'A', 'slug': 'a', 'state': 'live',
                            'ring': 'canary'}],
                          {'id': 7, 'name': 'A', 'slug': 'a'}, 'blank')
        rings = [t['ring'] for t in plan['tasks']]
        self.assertEqual(rings[0], 'rehearsal')
        self.assertEqual(rings[1], 'template')
        self.assertEqual(plan['tasks'][0]['target_db'], 'a-staging')

    def test_with_no_copy_to_practise_on_the_plan_says_so(self):
        plan = plan_tasks({'id': 1, 'name': 'R'},
                          [{'id': 7, 'name': 'A', 'slug': 'a', 'state': 'live',
                            'ring': 'canary'}], None, 'blank')
        self.assertFalse([t for t in plan['tasks'] if t['ring'] == 'rehearsal'])
        self.assertTrue(plan['warnings'])

    def test_the_rings_come_out_in_order(self):
        tenants = [
            {'id': 1, 'name': 'Zed', 'slug': 'z', 'state': 'live',
             'ring': 'everyone'},
            {'id': 2, 'name': 'Ann', 'slug': 'a', 'state': 'live',
             'ring': 'canary'},
            {'id': 3, 'name': 'Bee', 'slug': 'b', 'state': 'live',
             'ring': 'early'},
        ]
        plan = plan_tasks({'id': 1, 'name': 'R'}, tenants, None, 'blank')
        rings = [t['ring'] for t in plan['tasks'] if t['ring'] in CUSTOMER_RINGS]
        self.assertEqual(rings, ['canary', 'early', 'everyone'])

    def test_a_customer_left_out_is_left_out_with_a_reason(self):
        """Silence about a customer who did not get the update is the failure
        this list exists to prevent."""
        tenants = [
            {'id': 1, 'name': 'Half', 'slug': 'h', 'state': 'provisioning',
             'ring': 'everyone'},
            {'id': 2, 'name': 'Gone', 'slug': 'g', 'state': 'decommissioned',
             'ring': 'everyone'},
            {'id': 3, 'name': 'Sick', 'slug': 's', 'state': 'error',
             'ring': 'everyone'},
        ]
        plan = plan_tasks({'id': 1, 'name': 'R'}, tenants, None, 'blank')
        self.assertEqual(len(plan['excluded']), 3)
        for row in plan['excluded']:
            self.assertTrue(row['reason'])
            self.assertGreater(len(row['reason']), 12)

    def test_a_ring_nobody_is_in_is_not_a_ring_that_holds_things_up(self):
        plan = plan_tasks({'id': 1, 'name': 'R'}, [], None, 'blank')
        self.assertEqual([t['ring'] for t in plan['tasks']], ['template'])

    def test_every_ring_has_a_name_and_a_meaning_for_the_screen(self):
        for ring in RING_ORDER:
            self.assertTrue(RING_LABEL.get(ring))
            self.assertGreater(len(RING_MEANING.get(ring, '')), 40)


@tagged('post_install', '-at_install')
class TestAdvance(TransactionCase):
    """T1 — the state machine. A ring opens only when the one before it
    finished CLEAN, and a failure stops the walk."""

    def test_a_ring_opens_only_when_the_previous_one_finished(self):
        tasks = [_task(id=1, ring='template', state='done'),
                 _task(id=2, ring='canary', state='waiting')]
        snap = _snap(tasks, current_ring='template')
        # The template ring is finished but not stamped yet.
        self.assertEqual(advance(snap, NOW), ('ring_done', 'template'))
        snap['ring_done_at'] = NOW
        # The template ring has no watch period, so the next one opens.
        self.assertEqual(advance(snap, NOW), ('advance_ring', 'canary'))

    def test_a_failure_stops_the_whole_walk(self):
        tasks = [_task(id=1, state='failed', error='It fell over.'),
                 _task(id=2, state='waiting')]
        kind, reason = advance(_snap(tasks), NOW)
        self.assertEqual(kind, 'pause')
        self.assertEqual(reason, 'It fell over.')

    def test_a_failure_with_no_reason_still_names_the_customer(self):
        tasks = [_task(id=1, state='failed', error='', label='Ann')]
        kind, reason = advance(_snap(tasks), NOW)
        self.assertEqual(kind, 'pause')
        self.assertIn('Ann', reason)

    def test_it_only_ever_looks_at_the_current_ring(self):
        """⚠ Ledger F30, and it is why "Run now" on a later ring has to be a
        refusal BY NAME rather than a silent no-op: this function cannot see
        it."""
        tasks = [_task(id=1, ring='canary', state='waiting'),
                 _task(id=2, ring='everyone', state='waiting', run_now=True)]
        kind, payload = advance(_snap(tasks, current_ring='canary'), NOW)
        # It waits for the canary's window and never picks up the later one.
        self.assertEqual(kind, 'wait')
        kind, payload = advance(_snap(tasks, current_ring='everyone'), NOW)
        self.assertEqual(kind, 'run')
        self.assertEqual(payload['id'], 2)

    def test_run_now_skips_the_window(self):
        tasks = [_task(id=1, state='waiting', run_now=True)]
        kind, payload = advance(_snap(tasks), NOW)
        self.assertEqual(kind, 'run')
        self.assertEqual(payload['id'], 1)

    def test_the_practice_run_and_the_blank_system_need_nobody_s_window(self):
        for ring in ('rehearsal', 'template'):
            tasks = [_task(id=1, ring=ring, state='waiting', tz=None)]
            kind, _p = advance(_snap(tasks, current_ring=ring), NOW)
            self.assertEqual(kind, 'run', ring)
            self.assertTrue(eligible(tasks[0], NOW))

    def test_a_step_stuck_for_too_long_stops_the_rollout(self):
        started = NOW - timedelta(minutes=STUCK_MINUTES + 5)
        tasks = [_task(id=1, state='running', started_at=started, label='Ann')]
        kind, reason = advance(_snap(tasks), NOW)
        self.assertEqual(kind, 'pause')
        self.assertIn('Ann', reason)
        self.assertIn('never finished', reason)

    def test_a_step_running_normally_is_waited_for(self):
        tasks = [_task(id=1, state='running',
                       started_at=NOW - timedelta(minutes=2))]
        kind, until = advance(_snap(tasks), NOW)
        self.assertEqual(kind, 'wait')
        self.assertLessEqual(until, NOW + timedelta(minutes=5))

    def test_the_watch_period_holds_the_next_ring_back(self):
        tasks = [_task(id=1, ring='canary', state='done'),
                 _task(id=2, ring='everyone', state='waiting')]
        snap = _snap(tasks, current_ring='canary', state='waiting',
                     ring_done_at=NOW - timedelta(hours=2))
        kind, until = advance(snap, NOW)
        self.assertEqual(kind, 'wait')
        self.assertEqual(until, NOW - timedelta(hours=2) + timedelta(hours=24))

    def test_continuing_early_opens_the_next_ring(self):
        tasks = [_task(id=1, ring='canary', state='done'),
                 _task(id=2, ring='everyone', state='waiting')]
        snap = _snap(tasks, current_ring='canary', state='waiting',
                     ring_done_at=NOW - timedelta(hours=2), watch_skipped=True)
        self.assertEqual(advance(snap, NOW), ('advance_ring', 'everyone'))

    def test_a_customer_that_went_quiet_during_the_watch_stops_it(self):
        tasks = [_task(id=1, ring='canary', state='done')]
        snap = _snap(tasks, current_ring='canary', state='waiting',
                     ring_done_at=NOW,
                     watch_health=[{'name': 'Ann', 'ok': False,
                                    'reason': 'it did not answer'}])
        kind, reason = advance(snap, NOW)
        self.assertEqual(kind, 'pause')
        self.assertIn('Ann', reason)

    def test_the_last_ring_finishing_finishes_the_rollout(self):
        tasks = [_task(id=1, ring='everyone', state='done')]
        snap = _snap(tasks, current_ring='everyone', ring_done_at=NOW)
        self.assertEqual(advance(snap, NOW), ('done',))

    def test_the_watch_period_is_nought_for_the_rings_nobody_uses(self):
        for ring in ('rehearsal', 'template', 'everyone'):
            self.assertEqual(watch_hours_for(ring), 0)
        self.assertEqual(watch_hours_for('canary'), 24)
        self.assertEqual(watch_hours_for('canary', {'canary': 6}), 6)
        self.assertEqual(watch_hours_for('canary', {'canary': 'nonsense'}), 24)


@tagged('post_install', '-at_install')
class TestHealthGate(TransactionCase):
    """T5 — the verdict, and the ignore list that does not delete."""

    def test_no_answer_at_all_is_the_first_thing_reported(self):
        ok, why = health_verdict(0, 0, [])
        self.assertFalse(ok)
        self.assertIn('did not answer', why)

    def test_a_server_error_is_reported_with_its_code(self):
        ok, why = health_verdict(500, 0, [])
        self.assertFalse(ok)
        self.assertIn('500', why)

    def test_something_installed_that_did_not_load_fails_the_gate(self):
        ok, why = health_verdict(200, 2, [])
        self.assertFalse(ok)
        self.assertIn('did not load', why)

    def test_errors_in_the_log_fail_the_gate(self):
        ok, why = health_verdict(200, 0, ['one', 'two'])
        self.assertFalse(ok)
        self.assertIn('2 errors', why)

    def test_a_clean_run_passes(self):
        self.assertEqual(health_verdict(200, 0, []), (True, ''))

    def test_could_not_tell_passes_and_says_so_rather_than_reporting_nought(self):
        """⚠ -1 is an honest "could not tell", NEVER a green nought."""
        ok, why = health_verdict(200, -1, [])
        self.assertTrue(ok)
        self.assertIn('could not be determined', why)

    def test_the_blank_system_has_no_address_to_ask(self):
        self.assertEqual(health_verdict(None, 0, []), (True, ''))

    def test_ignored_lines_are_set_aside_and_never_dropped(self):
        """⚠ Ledger F25. A gate that cries wolf on every run is a gate somebody
        learns to click past — and one that HIDES what it ignored cannot be
        checked by anybody."""
        lines = ['ERROR licence check FAILED', 'ERROR something real']
        kept, ignored = filter_errors(lines, ['licence check'])
        self.assertEqual(kept, ['ERROR something real'])
        self.assertEqual(ignored, ['ERROR licence check FAILED'])
        self.assertEqual(len(kept) + len(ignored), len(lines))

    def test_an_empty_ignore_list_ignores_nothing(self):
        """The strict behaviour is always one empty setting away."""
        lines = ['ERROR anything']
        self.assertEqual(filter_errors(lines, [])[0], lines)
        self.assertEqual(filter_errors(lines, None)[0], lines)

    def test_the_ignore_list_does_not_care_about_case(self):
        kept, ignored = filter_errors(['ERROR LICENCE CHECK'], ['licence'])
        self.assertEqual(kept, [])
        self.assertEqual(len(ignored), 1)


@tagged('post_install', '-at_install')
class TestNotices(TransactionCase):
    """What a customer's own people are told, and the name in it."""

    def test_the_brand_comes_from_the_caller_and_never_from_this_file(self):
        pre = notice_for('pre', 'Acme Care')
        now = notice_for('now', 'Acme Care')
        self.assertIn('Acme Care', pre['text'])
        self.assertIn('Acme Care', now['text'])
        self.assertEqual(pre['kind'], 'maintenance')

    def test_with_no_brand_it_says_something_neutral_rather_than_nothing(self):
        self.assertIn('The system', notice_for('pre', '')['text'])

    def test_a_rollout_sends_two_kinds_of_message_and_no_others(self):
        with self.assertRaises(ValueError):
            notice_for('shout', 'Acme')
