# -*- coding: utf-8 -*-
"""The "in step" decisions, tested where they can be reached.

Everything the feature DOES happens against another database on this machine
and is reachable from no test (rail R6). These are the judgements, and they are
pure, so this file is the whole of what can be proved without a live box.
"""
from odoo.tests import TransactionCase, tagged

from odoo.addons.biz_tenants.models import tenants_common as common
from odoo.addons.biz_tenants.models.sync_rules import (
    log_lines_of_interest, master_behind_files, norm_version, release_name,
    release_state, sync_diff, sync_split, template_cron_plan,
)


@tagged('post_install', '-at_install')
class TestVersions(TransactionCase):
    """Ledger F1/F8 — the trap that let a customer sit two versions behind
    while being reported green."""

    def test_the_framework_series_is_stripped_from_both_sides(self):
        self.assertEqual(norm_version('19.0.1.7.0'), norm_version('1.7.0'))

    def test_a_plain_three_part_version_is_not_mistaken_for_a_prefixed_one(self):
        self.assertEqual(norm_version('1.7.0'), (1, 7, 0))

    def test_ten_is_newer_than_nine_which_text_comparison_gets_wrong(self):
        self.assertGreater(norm_version('1.10.0'), norm_version('1.9.0'))
        self.assertGreater(norm_version('19.0.1.10.0'), norm_version('1.9.0'))

    def test_something_that_is_not_a_number_is_an_answer_not_a_crash(self):
        self.assertEqual(norm_version('19.0.1.7.0-rc1'), (1, 7, 0))

    def test_nothing_at_all_is_the_oldest_thing_there_is(self):
        self.assertEqual(norm_version(''), (0,))
        self.assertLess(norm_version(''), norm_version('0.0.1'))


@tagged('post_install', '-at_install')
class TestSyncSplit(TransactionCase):

    def setUp(self):
        super().setUp()
        # Registrations are process-wide, so a test that adds one has to put
        # the world back — a fixture may borrow a registration, it may never
        # decide what was in it (ledger H17).
        self._never = dict(common.NEVER)
        self._prefixes = list(common.NEVER_PREFIXES)
        self.addCleanup(self._restore)

    def _restore(self):
        common.NEVER.clear()
        common.NEVER.update(self._never)
        common.NEVER_PREFIXES[:] = self._prefixes

    def test_names_only_answers_what_is_missing(self):
        install, held = sync_split(['a', 'b', 'c'], ['a'])
        self.assertEqual(install, ['b', 'c'])
        self.assertEqual(held, [])

    def test_a_version_behind_is_found_and_names_alone_would_miss_it(self):
        """The whole of ledger F1 in one assertion."""
        master = {'a': '19.0.1.10.0'}
        tenant = {'a': '19.0.1.9.0'}
        self.assertEqual(sync_split(master, tenant)[0], [],
                         'names only cannot see a version difference')
        diff = sync_diff(master, tenant)
        self.assertEqual([r['module'] for r in diff['to_update']], ['a'])

    def test_a_customer_ahead_of_the_master_is_reported_and_never_touched(self):
        diff = sync_diff({'a': '1.1.0'}, {'a': '1.2.0'})
        self.assertEqual([r['module'] for r in diff['ahead']], ['a'])
        self.assertEqual(diff['to_update'], [])
        self.assertEqual(diff['to_install'], [])

    def test_the_cockpit_itself_is_always_held_back(self):
        _install, held = sync_split(['biz_tenants', 'a'], ['a'])
        self.assertEqual(held, ['biz_tenants'])

    def test_the_never_list_is_honoured_on_both_sides(self):
        """A system that somehow already holds one must not be upgraded
        either."""
        common.register_never({'zz_forbidden': 'because'})
        diff = sync_diff({'zz_forbidden': '1.2.0'}, {'zz_forbidden': '1.1.0'})
        self.assertEqual(diff['held_back'], ['zz_forbidden'])
        self.assertEqual(diff['to_update'], [])

    def test_the_prefix_rail_refuses_a_module_nobody_has_listed(self):
        common.register_never(None, prefixes=('zz_platform',))
        self.assertTrue(common.is_never('zz_platform_anything'))
        _install, held = sync_split(['zz_platform_new'], [])
        self.assertEqual(held, ['zz_platform_new'])

    def test_something_only_the_customer_has_is_never_our_business(self):
        diff = sync_diff({'a': '1.0'}, {'a': '1.0', 'theirs': '1.0'})
        self.assertEqual(diff['to_install'], [])
        self.assertEqual(diff['to_update'], [])
        self.assertEqual(diff['ahead'], [])


@tagged('post_install', '-at_install')
class TestReleaseState(TransactionCase):

    SNAP = {'a': '1.0.0', 'b': '1.0.0', 'c': '1.0.0', 'd': '1.0.0'}

    def test_everything_at_that_version_or_newer_is_in_step(self):
        self.assertEqual(release_state(
            self.SNAP, {'a': '1.0.0', 'b': '1.1.0', 'c': '1.0.0',
                        'd': '1.0.0'}), 'on')

    def test_one_part_older_is_behind(self):
        self.assertEqual(release_state(
            self.SNAP, {'a': '1.0.0', 'b': '0.9.0', 'c': '1.0.0',
                        'd': '1.0.0'}), 'behind')

    def test_holding_less_than_half_is_not_behind_it_is_nowhere_near(self):
        """Calling that "behind" would put a system nobody has ever brought in
        step one button-press away from an install nobody has thought about."""
        self.assertEqual(release_state(self.SNAP, {'a': '1.0.0'}), 'none')

    def test_a_release_with_nothing_in_it_answers_nowhere_near(self):
        self.assertEqual(release_state({}, {'a': '1.0.0'}), 'none')


@tagged('post_install', '-at_install')
class TestMasterBehindFiles(TransactionCase):
    """Rail R3 lives or dies here."""

    def test_a_newer_file_than_the_database_has_applied_is_found(self):
        self.assertEqual(
            master_behind_files([('a', '19.0.1.1.0', '19.0.1.2.0')]), ['a'])

    def test_a_database_in_step_with_its_own_files_is_the_good_answer(self):
        self.assertEqual(
            master_behind_files([('a', '19.0.1.2.0', '19.0.1.2.0')]), [])

    def test_a_module_with_no_file_version_is_not_an_arrear(self):
        self.assertEqual(master_behind_files([('a', '19.0.1.2.0', '')]), [])


@tagged('post_install', '-at_install')
class TestReleaseName(TransactionCase):

    def test_the_first_one_today_is_the_bare_date(self):
        from datetime import date
        self.assertEqual(release_name(date(2026, 9, 4), []), '2026.09.04')

    def test_the_second_one_today_is_suffixed_and_so_is_the_third(self):
        from datetime import date
        self.assertEqual(
            release_name(date(2026, 9, 4), ['2026.09.04']), '2026.09.04-2')
        self.assertEqual(
            release_name(date(2026, 9, 4), ['2026.09.04', '2026.09.04-2']),
            '2026.09.04-3')


@tagged('post_install', '-at_install')
class TestTemplateCrons(TransactionCase):
    """Ledger F9 — an install switches the blank system's jobs back ON."""

    def test_everything_active_is_switched_off(self):
        to_disable, _param = template_cron_plan([3, 1, 2], '')
        self.assertEqual(sorted(to_disable), [1, 2, 3])

    def test_the_written_list_only_gains_what_it_does_not_already_hold(self):
        to_disable, param = template_cron_plan([1, 4], '1,2,3')
        self.assertEqual(param, '1,2,3,4')
        self.assertEqual(sorted(to_disable), [1, 4],
                         'an already recorded job that is running again still '
                         'has to be switched off')

    def test_rubbish_in_the_recorded_list_is_ignored_rather_than_fatal(self):
        _to_disable, param = template_cron_plan([], '1,,x,2')
        self.assertEqual(param, '1,2')


@tagged('post_install', '-at_install')
class TestLogReading(TransactionCase):
    """Ledger F25/F27 — the ignore list, and what it is NOT."""

    LINES = [
        "2026-09-04 10:00:00,001 123 ERROR hhh odoo.modules: something broke",
        "2026-09-04 10:00:01,002 123 ERROR hhh vendor_licence: check FAILED",
        "2026-09-04 10:00:02,003 123 INFO hhh odoo.modules: fine",
        "2026-09-04 09:00:00,004 123 ERROR hhh odoo.modules: yesterday's",
        "2026-09-04 10:00:03,005 123 ERROR other odoo.modules: not ours",
    ]

    def test_only_errors_for_this_system_since_the_moment_asked_about(self):
        out = log_lines_of_interest(self.LINES, 'hhh', '2026-09-04 09:30:00')
        self.assertEqual(len(out['errors']), 2)
        self.assertEqual(out['ignored'], [])

    def test_an_ignored_line_is_still_counted_and_never_deleted(self):
        out = log_lines_of_interest(self.LINES, 'hhh', '2026-09-04 09:30:00',
                                    ignore=['licence'])
        self.assertEqual(len(out['errors']), 1)
        self.assertEqual(len(out['ignored']), 1,
                         'an ignored line is recorded, never dropped')

    def test_another_system_s_errors_are_never_this_one_s(self):
        out = log_lines_of_interest(self.LINES, 'other', '2026-09-04 09:30:00')
        self.assertEqual(len(out['errors']), 1)

    def test_a_half_line_at_the_start_of_the_tail_is_skipped_not_fatal(self):
        out = log_lines_of_interest(['…the end of a line'], 'hhh', '')
        self.assertEqual(out, {'errors': [], 'ignored': []})
