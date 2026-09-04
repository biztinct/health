# -*- coding: utf-8 -*-
"""What counts as a problem, what a person is told, and what the world reads.

Every judgement in `alert_rules.py`, exercised with plain dictionaries. The two
that earn their keep are the privacy proof on `status_state` — fed a state full
of customer names, and asserted to emit none of them — and the white-label
assertion over every sentence any of these functions can produce (ledger F43:
the word reached a user-visible string through a system account name, and the
test that caught it is worth copying into anything that writes sentences).
"""
from datetime import date, datetime, timedelta

from odoo.tests import TransactionCase, tagged

from odoo.addons.biz_tenants.models.alert_rules import (
    ALERT_KINDS, BACKUP_MIN_FILES, DEFAULT_THRESHOLDS, KIND_ICON, KIND_LABEL,
    SEVERITY_ORDER, capacity_verdict, digest_headline, digest_lines,
    readings_to_alerts, reconcile, render_status_page, should_notify,
    status_state, worst_severity,
)

NOW = datetime(2026, 9, 4, 8, 0, 0)


def _healthy_tenant(**kw):
    row = {'id': 1, 'name': 'Ann Ltd', 'slug': 'ann', 'state': 'live',
           'health': 'ok', 'last_backup_at': NOW - timedelta(hours=2),
           'last_backup_failed': False, 'last_backup_small': False,
           'cert_state': 'own', 'cert_days_left': 60, 'error_lines': 0,
           'release_state': 'on', 'behind_count': 0, 'stale_count': 0}
    row.update(kw)
    return row


def _healthy(**kw):
    row = {
        'now': NOW,
        'tenants': [_healthy_tenant()],
        'disk': {'free_pct': 60, 'free_gb': 30.0, 'total_gb': 58.0},
        'memory': {'total_mb': 1910, 'available_mb': 800},
        'capacity': {'level': 'ok', 'reason': 'Room for 6 more customers.'},
        'mail': {'can_send': True, 'reason': ''},
        'rollout': {},
        'status_page': {'writable': True, 'age_min': 2, 'reason': ''},
        'master_errors': 40,
    }
    row.update(kw)
    return row


def _kinds(alerts):
    return sorted(a['kind'] for a in alerts)


@tagged('post_install', '-at_install')
class TestReadingsToAlerts(TransactionCase):

    def test_a_healthy_platform_raises_nothing(self):
        self.assertEqual(readings_to_alerts(_healthy()), [])

    def test_a_customer_that_does_not_answer_is_urgent(self):
        rows = readings_to_alerts(
            _healthy(tenants=[_healthy_tenant(health='down')]))
        self.assertEqual(_kinds(rows), ['tenant_unreachable'])
        self.assertEqual(rows[0]['severity'], 'critical')
        self.assertEqual(rows[0]['key'], 'tenant_unreachable:ann')

    def test_a_customer_that_has_never_been_copied_is_urgent(self):
        rows = readings_to_alerts(
            _healthy(tenants=[_healthy_tenant(last_backup_at=None)]))
        self.assertEqual(_kinds(rows), ['backup_missing'])
        self.assertIn('never been copied', rows[0]['title'])

    def test_a_stale_copy_and_a_failed_copy_are_different_problems(self):
        stale = readings_to_alerts(_healthy(tenants=[_healthy_tenant(
            last_backup_at=NOW - timedelta(hours=40))]))
        self.assertEqual(_kinds(stale), ['backup_stale'])
        failed = readings_to_alerts(_healthy(tenants=[_healthy_tenant(
            last_backup_failed=True)]))
        self.assertEqual(_kinds(failed), ['backup_missing'])

    def test_a_copy_that_is_not_a_real_copy_is_its_own_problem(self):
        """H4a's F59 verdict, read back rather than assumed: an archive with
        almost nothing in it says "done" and restores a system with no
        documents."""
        rows = readings_to_alerts(_healthy(tenants=[_healthy_tenant(
            last_backup_small=True)]))
        self.assertEqual(_kinds(rows), ['backup_small'])
        self.assertEqual(rows[0]['severity'], 'critical')

    def test_the_small_copy_threshold_excludes_the_incident_it_came_from(self):
        """⚠ Ledger H70. The wreckage was an archive with FIVE files in it, so
        a guard written `files < 5` passes the very thing it was written for."""
        self.assertGreater(BACKUP_MIN_FILES, 5)

    def test_a_certificate_running_out_gets_louder_as_it_gets_closer(self):
        warn = readings_to_alerts(
            _healthy(tenants=[_healthy_tenant(cert_days_left=10)]))
        self.assertEqual(warn[0]['severity'], 'warning')
        crit = readings_to_alerts(
            _healthy(tenants=[_healthy_tenant(cert_days_left=2)]))
        self.assertEqual(crit[0]['severity'], 'critical')

    def test_a_customer_with_no_certificate_of_their_own_is_said_differently(self):
        rows = readings_to_alerts(
            _healthy(tenants=[_healthy_tenant(cert_state='none')]))
        self.assertEqual(_kinds(rows), ['cert_missing'])

    def test_errors_are_counted_against_a_threshold_that_can_be_moved(self):
        readings = _healthy(tenants=[_healthy_tenant(error_lines=3)])
        self.assertEqual(_kinds(readings_to_alerts(readings)), ['tenant_errors'])
        self.assertEqual(readings_to_alerts(readings, {'error_lines': 10}), [])

    def test_a_customer_who_is_not_live_is_not_judged(self):
        """A system still being built logs errors of its own and has no copy
        yet — alerting on it would be crying wolf at the one moment somebody is
        watching it anyway."""
        for state in ('draft', 'provisioning', 'decommissioned'):
            rows = readings_to_alerts(_healthy(tenants=[
                _healthy_tenant(state=state, health='down',
                                last_backup_at=None)]))
            self.assertEqual(rows, [], state)

    def test_a_reading_nobody_took_neither_raises_nor_silences(self):
        """A missing key means NOT MEASURED and is skipped rather than guessed
        at."""
        self.assertEqual(readings_to_alerts({'now': NOW}), [])
        self.assertEqual(readings_to_alerts(_healthy(disk={}, memory={})), [])

    def test_the_disk_and_the_memory_have_an_urgent_level_of_their_own(self):
        disk = readings_to_alerts(_healthy(
            disk={'free_pct': 3, 'free_gb': 1.0, 'total_gb': 58.0}))
        self.assertEqual(disk[0]['severity'], 'critical')
        mem = readings_to_alerts(_healthy(
            memory={'total_mb': 1910, 'available_mb': 100}))
        self.assertEqual(mem[0]['severity'], 'critical')

    def test_a_full_machine_is_said_without_calling_it_a_fault(self):
        rows = readings_to_alerts(_healthy(capacity={
            'level': 'full', 'reason': 'No room.'}))
        self.assertEqual(_kinds(rows), ['capacity_full'])
        self.assertEqual(rows[0]['severity'], 'warning')
        self.assertIn('Nothing is broken', rows[0]['text'])

    def test_no_mail_account_is_stated_rather_than_left_silent(self):
        """It is not noise. It is the honest statement that this platform
        cannot reach a human, and it stays open until it can."""
        rows = readings_to_alerts(_healthy(mail={
            'can_send': False, 'reason': 'There is no outgoing mail account.'}))
        self.assertEqual(_kinds(rows), ['mail_not_configured'])
        self.assertIn('on this screen', rows[0]['text'])

    def test_a_stopped_rollout_is_said_with_its_reason(self):
        rows = readings_to_alerts(_healthy(rollout={
            'state': 'paused', 'release': '2026.09.04-1',
            'reason': 'Ann fell over.'}))
        self.assertEqual(_kinds(rows), ['rollout_stopped'])
        self.assertIn('Ann fell over.', rows[0]['text'])

    def test_a_public_page_that_cannot_be_written_is_said(self):
        rows = readings_to_alerts(_healthy(status_page={
            'writable': False, 'age_min': None, 'reason': 'No folder.'}))
        self.assertEqual(_kinds(rows), ['status_page_unwritable'])

    def test_the_platform_s_own_error_count_is_gathered_and_not_alerted_on(self):
        """⚠ Ledger F39. This machine logs its own test runs, so a rule about
        its own errors would have to be written against that noise first — and a
        rule written against noise is a rule nobody trusts."""
        self.assertEqual(readings_to_alerts(_healthy(master_errors=900)), [])

    def test_every_alert_says_what_to_do_next(self):
        """An alert that hands somebody a number and leaves them to work out
        the rest is an alert they learn to scroll past."""
        rows = readings_to_alerts(_healthy(
            tenants=[_healthy_tenant(health='down', last_backup_at=None,
                                     cert_state='none', error_lines=9)],
            disk={'free_pct': 3, 'free_gb': 1.0, 'total_gb': 58.0},
            memory={'total_mb': 1910, 'available_mb': 100},
            capacity={'level': 'full', 'reason': 'No room.'},
            mail={'can_send': False, 'reason': 'No account.'},
            rollout={'state': 'paused', 'release': 'R', 'reason': 'x'},
            status_page={'writable': False, 'age_min': None, 'reason': 'x'}))
        self.assertGreaterEqual(len(rows), 8)
        for row in rows:
            self.assertTrue(row['title'])
            self.assertGreater(len(row['text']), 60, row['kind'])
            self.assertIn('What to do next', row['text'], row['kind'])

    def test_every_kind_that_can_be_raised_is_declared(self):
        rows = readings_to_alerts(_healthy(
            tenants=[_healthy_tenant(health='down', last_backup_at=None,
                                     cert_state='none', error_lines=9)],
            disk={'free_pct': 3, 'free_gb': 1.0, 'total_gb': 58.0},
            memory={'total_mb': 1910, 'available_mb': 100},
            capacity={'level': 'full', 'reason': 'x'},
            mail={'can_send': False, 'reason': 'x'},
            rollout={'state': 'paused', 'release': 'R', 'reason': 'x'},
            status_page={'writable': False, 'age_min': None, 'reason': 'x'}))
        for row in rows:
            self.assertIn(row['kind'], ALERT_KINDS)
            self.assertIn(row['kind'], KIND_LABEL)
            self.assertIn(row['kind'], KIND_ICON)


@tagged('post_install', '-at_install')
class TestWhiteLabel(TransactionCase):
    """⚠ LEDGER F43, AND IT IS THE ASSERTION THAT CAUGHT IT.

    The word reached a user-visible string through a SYSTEM ACCOUNT NAME —
    "give it to the odoo user" — which is a technical instruction and is
    absolutely forbidden on a screen. The test asserts it of every sentence
    every alert kind can produce, and of the public page's whole text.
    """

    def _every_sentence(self):
        rows = readings_to_alerts(_healthy(
            tenants=[_healthy_tenant(health='down', last_backup_at=None,
                                     cert_state='none', error_lines=9,
                                     last_backup_failed=False,
                                     last_backup_small=False)],
            disk={'free_pct': 3, 'free_gb': 1.0, 'total_gb': 58.0},
            memory={'total_mb': 1910, 'available_mb': 100},
            capacity={'level': 'full', 'reason': 'No room here.'},
            mail={'can_send': False, 'reason': 'No account.'},
            rollout={'state': 'paused', 'release': 'R', 'reason': 'x'},
            status_page={'writable': False, 'age_min': None, 'reason': 'x'}))
        rows += readings_to_alerts(_healthy(tenants=[
            _healthy_tenant(last_backup_failed=True)]))
        rows += readings_to_alerts(_healthy(tenants=[
            _healthy_tenant(last_backup_small=True)]))
        rows += readings_to_alerts(_healthy(tenants=[
            _healthy_tenant(last_backup_at=NOW - timedelta(hours=40))]))
        rows += readings_to_alerts(_healthy(tenants=[
            _healthy_tenant(cert_days_left=3)]))
        out = []
        for row in rows:
            out.append(row['title'])
            out.append(row['text'])
        out.extend(KIND_LABEL.values())
        return out

    def test_no_alert_text_names_the_software_underneath(self):
        for text in self._every_sentence():
            self.assertNotIn('odoo', text.lower(), text)

    def test_no_alert_text_names_a_product_or_an_industry(self):
        for text in self._every_sentence():
            low = text.lower()
            for banned in ('payobook', 'viet uc', 'carejiox', 'clinic',
                           'patient', 'nurse', 'payroll'):
                self.assertNotIn(banned, low, text)

    def test_the_public_page_names_the_software_nowhere(self):
        page = render_status_page(
            status_state([], [], [], NOW, tz='Asia/Ho_Chi_Minh'),
            brand='Acme Care', tz='Asia/Ho_Chi_Minh')
        self.assertNotIn('odoo', page.lower())
        self.assertIn('Acme Care', page)

    def test_the_public_page_takes_its_name_from_the_caller(self):
        """The brand is a setting; a page with a written-down name in it is a
        page that is wrong for the next product that uses this."""
        page = render_status_page(status_state([], [], [], NOW), brand='Zed Ltd')
        self.assertIn('Zed Ltd', page)
        self.assertNotIn('Acme', page)

    def test_a_page_with_no_brand_says_something_neutral(self):
        page = render_status_page(status_state([], [], [], NOW), brand='')
        self.assertIn('Service status', page)


@tagged('post_install', '-at_install')
class TestReconcile(TransactionCase):
    """T7 — one row per problem, ever."""

    def _open(self, **kw):
        row = {'id': 5, 'key': 'backup_stale:ann', 'kind': 'backup_stale',
               'severity': 'critical', 'state': 'open', 'count': 3}
        row.update(kw)
        return row

    def _fresh(self, **kw):
        row = {'key': 'backup_stale:ann', 'kind': 'backup_stale',
               'severity': 'critical', 'title': 'No recent copy',
               'text': 'do this', 'tenant_id': 1}
        row.update(kw)
        return row

    def test_something_new_is_created_with_both_sightings_stamped(self):
        create, bump, resolve = reconcile([], [self._fresh()], NOW)
        self.assertEqual(len(create), 1)
        self.assertEqual(create[0]['first_seen'], NOW)
        self.assertEqual(create[0]['last_seen'], NOW)
        self.assertEqual(create[0]['count'], 1)
        self.assertEqual(create[0]['state'], 'open')
        self.assertEqual((bump, resolve), ([], []))

    def test_the_same_problem_bumps_its_count_and_refreshes_its_wording(self):
        create, bump, resolve = reconcile(
            [self._open()], [self._fresh(text='2 days now')], NOW)
        self.assertEqual(create, [])
        self.assertEqual(len(bump), 1)
        aid, vals = bump[0]
        self.assertEqual(aid, 5)
        self.assertEqual(vals['count'], 4)
        self.assertEqual(vals['last_seen'], NOW)
        self.assertEqual(vals['body_text'], '2 days now')

    def test_a_clean_reading_resolves_what_it_no_longer_sees(self):
        create, bump, resolve = reconcile([self._open()], [], NOW)
        self.assertEqual(resolve, [5])

    def test_an_acknowledged_problem_is_still_reconciled(self):
        create, bump, resolve = reconcile(
            [self._open(state='acknowledged')], [], NOW)
        self.assertEqual(resolve, [5])

    def test_a_problem_that_got_worse_keeps_its_row_and_changes_its_level(self):
        _c, bump, _r = reconcile([self._open(severity='warning')],
                                 [self._fresh(severity='critical')], NOW)
        self.assertEqual(bump[0][1]['severity'], 'critical')


@tagged('post_install', '-at_install')
class TestShouldNotify(TransactionCase):

    def _alert(self, **kw):
        row = {'state': 'open', 'severity': 'warning', 'spoken_at': None,
               'spoken_severity': ''}
        row.update(kw)
        return row

    def test_one_never_spoken_always_speaks(self):
        self.assertTrue(should_notify(self._alert(), NOW))

    def test_an_acknowledged_one_never_speaks_again(self):
        """Acknowledging IS "I know"."""
        self.assertFalse(should_notify(self._alert(state='acknowledged'), NOW))

    def test_a_resolved_one_never_speaks_as_a_reminder(self):
        self.assertFalse(should_notify(self._alert(state='resolved'), NOW))

    def test_it_waits_out_its_interval(self):
        row = self._alert(spoken_at=NOW - timedelta(hours=1))
        self.assertFalse(should_notify(row, NOW, 2, 6))
        row = self._alert(spoken_at=NOW - timedelta(hours=7))
        self.assertTrue(should_notify(row, NOW, 2, 6))

    def test_one_that_got_worse_speaks_immediately_whatever_the_interval(self):
        """"The thing I told you about is now urgent" is new information."""
        row = self._alert(severity='critical', spoken_severity='warning',
                          spoken_at=NOW - timedelta(minutes=1))
        self.assertTrue(should_notify(row, NOW, 2, 6))

    def test_an_interval_of_nought_means_never_remind(self):
        row = self._alert(spoken_at=NOW - timedelta(days=9))
        self.assertFalse(should_notify(row, NOW, 0, 0))


@tagged('post_install', '-at_install')
class TestDigest(TransactionCase):
    """T7 — the severity floor. Ledger F68."""

    def _row(self, sev, subject='Something', **kw):
        row = {'severity': sev, 'subject': subject, 'state': 'open',
               'first_seen': NOW - timedelta(hours=3), 'count': 1, 'key': 'k'}
        row.update(kw)
        return row

    def test_an_info_only_morning_is_announced_for_information(self):
        """⚠ An `info` announced as "something needs your attention" is crying
        wolf about the one thing that must never be scrolled past."""
        heading, intro = digest_headline([self._row('info')], 3)
        self.assertEqual(heading, 'For information')
        self.assertIn('Nothing needs you', intro)

    def test_a_warning_morning_says_none_of_it_is_urgent(self):
        heading, intro = digest_headline(
            [self._row('warning'), self._row('info')], 3)
        self.assertEqual(heading, 'Worth a look')
        self.assertIn('None of it is urgent', intro)

    def test_an_urgent_morning_says_so(self):
        heading, _i = digest_headline(
            [self._row('critical'), self._row('info')], 3)
        self.assertEqual(heading, 'Needs attention now')

    def test_an_empty_morning_is_the_point(self):
        """A channel that only ever speaks when something is broken cannot be
        told apart from a channel that is broken."""
        heading, intro = digest_headline([], 3)
        self.assertEqual(heading, 'All clear')
        self.assertIn('3 customers', intro)

    def test_the_lines_are_worst_first_and_carry_how_long_it_has_gone_on(self):
        rows = [self._row('warning', 'Small'), self._row('critical', 'Big')]
        lines = digest_lines(rows, NOW)
        self.assertTrue(lines[0].startswith('Needs attention now: Big'))
        self.assertIn('3 hours', lines[0])

    def test_a_line_says_when_it_has_been_seen_more_than_once(self):
        lines = digest_lines([self._row('warning', count=9)], NOW)
        self.assertIn('seen 9 times', lines[0])

    def test_an_acknowledged_line_says_you_already_know(self):
        lines = digest_lines([self._row('warning', state='acknowledged')], NOW)
        self.assertIn('you know about this', lines[0])

    def test_the_worst_of_a_group_is_the_loudest_in_it(self):
        self.assertEqual(worst_severity([]), 'info')
        self.assertEqual(worst_severity([{'severity': 'info'},
                                         {'severity': 'critical'},
                                         {'severity': 'warning'}]), 'critical')
        self.assertEqual(SEVERITY_ORDER['critical'], 2)


@tagged('post_install', '-at_install')
class TestCapacity(TransactionCase):
    """T10 — room = (free − reserve) ÷ cost, floored at nought."""

    def test_the_arithmetic_is_exactly_that(self):
        cap = capacity_verdict(1910, 1000, 1, 60, 400)
        self.assertEqual(cap['headroom'], 10)     # (1000-400) // 60
        self.assertEqual(cap['level'], 'ok')

    def test_it_never_goes_below_nought(self):
        cap = capacity_verdict(1910, 300, 1, 60, 400)
        self.assertEqual(cap['headroom'], 0)
        self.assertEqual(cap['level'], 'full')

    def test_room_for_one_is_a_warning_rather_than_a_green_light(self):
        cap = capacity_verdict(1910, 470, 1, 60, 400)
        self.assertEqual(cap['headroom'], 1)
        self.assertEqual(cap['level'], 'warn')
        self.assertIn('before the next sale', cap['reason'])

    def test_a_cost_somebody_cleared_never_divides_by_nought(self):
        for bad in (0, None, ''):
            cap = capacity_verdict(1910, 1000, 1, bad, 400)
            self.assertEqual(cap['cost_per_tenant_mb'], 60)

    def test_the_reason_names_both_halves_of_the_arithmetic(self):
        cap = capacity_verdict(1910, 1000, 1, 60, 400)
        self.assertIn('1000 MB', cap['reason'])
        self.assertIn('60 MB', cap['reason'])
        self.assertIn('400 MB', cap['reason'])

    def test_the_full_refusal_says_what_is_free_and_what_is_held_back(self):
        cap = capacity_verdict(1910, 380, 2, 60, 400)
        self.assertIn('380 MB', cap['reason'])
        self.assertIn('400 MB', cap['reason'])

    def test_the_setting_is_a_policy_and_moving_it_moves_the_answer(self):
        """⚠ Ledger F34. The measurement on this machine is about 11 MB; the
        setting is that plus a deliberate allowance, and it is a SETTING so it
        can be re-weighed rather than redeployed."""
        loose = capacity_verdict(1910, 1000, 1, 11, 400)
        tight = capacity_verdict(1910, 1000, 1, 200, 400)
        self.assertGreater(loose['headroom'], tight['headroom'])


@tagged('post_install', '-at_install')
class TestStatusState(TransactionCase):
    """T11 — THE PRIVACY PROOF. `status_state` is the one door between what
    the platform knows and what the world reads."""

    NAMES = ('Ann Ltd', 'ann', 'Bee Health', 'bee', 'hhh', 'HHH')

    def _loaded(self):
        """A state stuffed with customer names in every field that has one."""
        alerts = [
            {'kind': 'tenant_unreachable', 'severity': 'critical',
             'state': 'open', 'subject': 'Ann Ltd cannot be reached',
             'text': 'Nobody at Ann Ltd can sign in. Open ann and press…',
             'tenant': 'Ann Ltd', 'tenant_slug': 'ann', 'key':
             'tenant_unreachable:ann'},
            {'kind': 'backup_stale', 'severity': 'critical', 'state': 'open',
             'subject': 'Bee Health has no recent copy', 'text': 'bee, hhh',
             'tenant': 'Bee Health', 'tenant_slug': 'bee',
             'key': 'backup_stale:bee'},
        ]
        notices = [{'kind': 'maintenance',
                    'text': 'A short update is planned.',
                    'range': 'tonight 22:00–01:00 · Asia/Ho_Chi_Minh'}]
        incidents = [{'kind': 'tenant_unreachable', 'minutes': 45,
                      'ended': datetime(2026, 9, 1, 10, 0)}]
        return status_state(alerts, notices, incidents, NOW,
                            tz='Asia/Ho_Chi_Minh')

    def _leaks(self, text):
        """Which of the customer names appear IN THE TEXT AS WORDS.

        ⚠ A whole word, not a substring (ledger H68, third time in this
        programme). The slug `ann` sits inside "planned", so a plain `in`
        reported a leak on a page that names nobody — and a privacy test that
        cries wolf is a privacy test somebody turns off.
        """
        import re as _re
        return [n for n in self.NAMES
                if _re.search(r'\b%s\b' % _re.escape(n), text)]

    def test_not_one_customer_name_comes_out(self):
        self.assertEqual(self._leaks(repr(self._loaded())), [])

    def test_not_one_customer_name_reaches_the_rendered_page(self):
        page = render_status_page(self._loaded(), brand='Acme Care',
                                  tz='Asia/Ho_Chi_Minh')
        self.assertEqual(self._leaks(page), [])

    def test_the_privacy_test_would_notice_a_real_leak(self):
        """The proof that the proof works. A test that can only ever pass is
        not a test, and this one was one word away from being exactly that."""
        self.assertEqual(self._leaks('Ann Ltd cannot be reached'), ['Ann Ltd'])
        self.assertEqual(self._leaks('an update is planned'), [])

    def test_an_urgent_problem_colours_the_component_it_belongs_to(self):
        state = self._loaded()
        levels = {c['name']: c['level'] for c in state['components']}
        self.assertEqual(levels['Customer sites'], 'down')
        self.assertEqual(state['level'], 'down')

    def test_a_warning_about_one_customer_is_not_a_degraded_service(self):
        state = status_state([{'kind': 'tenant_unreachable',
                               'severity': 'warning', 'state': 'open'}],
                             [], [], NOW)
        self.assertEqual(state['level'], 'ok')

    def test_nobody_else_s_business_never_colours_the_page(self):
        """A copy that did not run, a page that would not write, a release that
        stopped and a mail account nobody has connected are all real and none
        of them are visible to anybody outside."""
        for kind in ('backup_missing', 'backup_stale', 'backup_small',
                     'capacity_full', 'rollout_stopped',
                     'status_page_unwritable', 'mail_not_configured'):
            state = status_state([{'kind': kind, 'severity': 'critical',
                                   'state': 'open'}], [], [], NOW)
            self.assertEqual(state['level'], 'ok', kind)

    def test_planned_work_is_a_different_colour_from_a_fault(self):
        """A page that shouts the same colour for "we told you about this" and
        "something broke" teaches its readers nothing."""
        state = status_state([], [], [], NOW, maintenance=True)
        self.assertEqual(state['level'], 'maintenance')
        self.assertIn('Planned', state['headline'])

    def test_an_incident_is_a_duration_and_never_a_name(self):
        state = self._loaded()
        self.assertEqual(len(state['incidents']), 1)
        self.assertIn('45 minutes', state['incidents'][0]['what'])

    def test_the_page_names_the_zone_it_speaks(self):
        """⚠ Ledger F38. A file on disk has no reader to ask what time it is,
        so the zone has to be printed or the page is a lie by omission."""
        state = status_state([], [], [], NOW, updated_at='2026-09-04 15:00',
                             tz='Asia/Ho_Chi_Minh')
        page = render_status_page(state, brand='Acme', tz='Asia/Ho_Chi_Minh')
        self.assertIn('Asia/Ho_Chi_Minh', page)
        self.assertIn('2026-09-04 15:00', page)

    def test_the_page_checks_its_own_age(self):
        state = status_state([], [], [], NOW)
        state['updated_iso'] = '2026-09-04T08:00:00Z'
        page = render_status_page(state, brand='Acme')
        self.assertIn('2026-09-04T08:00:00Z', page)
        self.assertIn('id="stale"', page)
        self.assertIn(str(DEFAULT_THRESHOLDS['status_page_minutes']), page)

    def test_the_page_asks_the_internet_for_nothing(self):
        """Its entire job is to be readable on the day the application is not."""
        page = render_status_page(self._loaded(), brand='Acme')
        for needle in ('http://', 'https://', '<img', 'src="//'):
            self.assertNotIn(needle, page, needle)

    def test_a_quiet_week_says_so_rather_than_showing_an_empty_box(self):
        page = render_status_page(status_state([], [], [], NOW), brand='Acme')
        self.assertIn('Nothing has gone wrong in the last seven days.', page)

    def test_everything_that_reaches_the_page_is_escaped(self):
        """The page carries a script of its own — the few lines that check its
        own age — so what is asserted is that nothing which CAME IN as text
        goes out as markup."""
        state = status_state([], [{'kind': 'info', 'text': '<script>bad()</script>',
                                   'range': ''}], [], NOW)
        page = render_status_page(state, brand='<b>Acme</b>')
        self.assertNotIn('<script>bad()</script>', page)
        self.assertIn('&lt;script&gt;bad()&lt;/script&gt;', page)
        self.assertNotIn('<b>Acme</b>', page)
        self.assertIn('&lt;b&gt;Acme&lt;/b&gt;', page)
