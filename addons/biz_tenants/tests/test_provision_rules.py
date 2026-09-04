# -*- coding: utf-8 -*-
"""The provisioning judgements, tested where they can be reached (rail R6).

The acts themselves — copy a database, ask for a certificate — happen on a live
machine and are proved by running them there and reporting it. These are the
decisions in front of each act.
"""
from odoo.tests import TransactionCase, tagged

from odoo.addons.biz_tenants.models.provision_rules import (
    PROVISION_STEPS, STEP_KEYS, backup_verdict, check_slug, free_memory_mb,
    generated_password, human_bytes, memory_verdict, next_step, step_label,
)


@tagged('post_install', '-at_install')
class TestSlug(TransactionCase):
    """The short name is the DATABASE NAME and the first word of the WEB
    ADDRESS at once, which is why the rule is this tight."""

    def _ok(self, slug, **kw):
        ok, reason = check_slug(slug, **kw)
        self.assertTrue(ok, 'expected "%s" to be allowed: %s' % (slug, reason))

    def _no(self, slug, expect='', **kw):
        ok, reason = check_slug(slug, **kw)
        self.assertFalse(ok, 'expected "%s" to be refused' % slug)
        self.assertTrue(reason, 'a refusal has to say why')
        if expect:
            self.assertIn(expect, reason.lower())

    def test_a_good_short_name_passes(self):
        self._ok('hhh')
        self._ok('greenvalley')
        self._ok('clinic7')

    def test_capitals_are_refused_and_the_reason_names_the_address(self):
        self._no('HHH', 'small letters')

    def test_an_underscore_is_refused_and_the_reason_says_why(self):
        """The web server drops any hostname carrying one, and that rule is
        what keeps the blank system off the public internet."""
        self._no('green_valley', 'underscore')

    def test_a_leading_digit_is_refused(self):
        self._no('7clinic')

    def test_something_far_too_long_is_refused(self):
        self._no('a' * 40)

    def test_postgres_own_names_are_refused_by_name(self):
        for name in ('postgres', 'template0', 'template1'):
            self._no(name, 'kept for the platform')

    def test_the_platform_s_own_system_is_refused_with_its_own_sentence(self):
        self._no('carejiox', 'platform', apex_db='carejiox')

    def test_the_blank_system_is_refused_with_its_own_sentence(self):
        self._no('blanksys', 'copied from', template_db='blanksys')

    def test_a_practice_copy_name_is_refused(self):
        self._no('hhhstaging', 'practice')

    def test_a_name_already_on_the_machine_is_refused(self):
        self._no('hhh', 'already', taken=('hhh',))

    def test_nothing_at_all_is_refused_with_a_sentence_that_helps(self):
        self._no('', 'short name')


@tagged('post_install', '-at_install')
class TestMemoryGuard(TransactionCase):

    MEMINFO = ("MemTotal:        1956000 kB\n"
               "MemFree:          106000 kB\n"
               "MemAvailable:     650240 kB\n")

    def test_it_reads_available_and_not_free(self):
        """Free memory on a busy machine is near zero and always has been —
        the kernel keeps the rest as cache it hands back on demand. A guard
        reading MemFree refuses every single time."""
        self.assertEqual(free_memory_mb(self.MEMINFO), 635)

    def test_text_it_cannot_read_answers_minus_one_not_nought(self):
        self.assertEqual(free_memory_mb('nonsense'), -1)

    def test_below_the_floor_is_refused_and_the_refusal_names_the_way_out(self):
        ok, reason = memory_verdict(300, 400)
        self.assertFalse(ok)
        self.assertIn('400', reason)
        self.assertIn('bigger', reason)

    def test_above_the_floor_passes_with_nothing_to_say(self):
        self.assertEqual(memory_verdict(650, 400), (True, ''))

    def test_a_machine_it_could_not_read_is_allowed_through_with_a_warning(self):
        """The real capacity guard is a later phase's. A guard that cannot read
        the machine must not be the thing that stops a customer being made."""
        ok, reason = memory_verdict(-1, 400)
        self.assertTrue(ok)
        self.assertTrue(reason)


@tagged('post_install', '-at_install')
class TestBackupVerdict(TransactionCase):
    """Ledger F59 — a copy taken with the wrong home folder contains no
    attachments and still says "done"."""

    def test_a_real_copy_passes(self):
        self.assertEqual(backup_verdict(50_000_000, 200_000_000, 1280),
                         (True, ''))

    def test_an_empty_database_file_fails(self):
        ok, reason = backup_verdict(0, 200_000_000, 1280)
        self.assertFalse(ok)
        self.assertTrue(reason)

    def test_an_attachments_archive_with_almost_nothing_in_it_fails(self):
        """THE EXACT SHAPE OF THE INCIDENT: a 9 MB archive with FIVE files in
        it, recorded as good beside a real one of 219 MB with 1,280."""
        ok, reason = backup_verdict(50_000_000, 9_000_000, 5)
        self.assertFalse(ok)
        self.assertIn('attachments', reason)
        self.assertIn('thrown away', reason,
                      'a bad copy is thrown away, never recorded as good')

    def test_a_tiny_attachments_archive_fails_even_with_files_in_it(self):
        ok, reason = backup_verdict(50_000_000, 100, 40)
        self.assertFalse(ok)
        self.assertIn('thrown away', reason)


@tagged('post_install', '-at_install')
class TestSteps(TransactionCase):

    def test_the_six_steps_are_in_the_order_they_run(self):
        self.assertEqual(
            STEP_KEYS,
            ('clone', 'configure', 'admin', 'https', 'verify', 'done'))

    def test_every_step_has_a_label_a_person_can_read(self):
        for key, label in PROVISION_STEPS:
            self.assertTrue(label)
            self.assertNotEqual(label, key)
            self.assertEqual(step_label(key), label)

    def test_nothing_reached_yet_means_start_at_the_beginning(self):
        self.assertEqual(next_step(''), 'clone')
        self.assertEqual(next_step(False), 'clone')

    def test_it_continues_from_the_step_after_the_last_one_that_finished(self):
        self.assertEqual(next_step('clone'), 'configure')
        self.assertEqual(next_step('verify'), 'done')

    def test_after_the_last_step_there_is_nothing_left(self):
        self.assertEqual(next_step('done'), '')

    def test_a_step_nobody_has_heard_of_starts_again_rather_than_crashing(self):
        self.assertEqual(next_step('nonsense'), 'clone')


@tagged('post_install', '-at_install')
class TestSmallThings(TransactionCase):

    def test_sizes_read_as_a_person_would_say_them(self):
        self.assertEqual(human_bytes(0), '0 B')
        self.assertEqual(human_bytes(1536), '1.5 KB')
        self.assertIn('MB', human_bytes(120 * 1024 * 1024))

    def test_a_password_is_readable_down_a_telephone(self):
        pw = generated_password('AbCdEfGhIjKlMnOp')
        self.assertEqual(len(pw), 14)
        self.assertEqual(pw.count('-'), 2)

    def test_a_short_token_still_makes_a_whole_password(self):
        self.assertEqual(len(generated_password('ab')), 14)
