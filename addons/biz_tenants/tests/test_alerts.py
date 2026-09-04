# -*- coding: utf-8 -*-
"""The alerts, the capacity guard and the public page, on a database.

⚠ THE SUITE STANDS DOWN THE REAL FLEET FIRST (ledger F28), for the same reason
the rollout tests do: this runs against the platform's own database, where real
customers and real alerts live.

⚠ AND TWO THINGS HERE ARE NOT ROLLED BACK BY A TRANSACTION. A file written by a
model (F44) and a message sent by one (F67) both escape the test's own
transaction — a suite run on the live platform once published a public page
built from invented customers. Both stand down at the writer, and both are
proved here rather than assumed.
"""
import os
from unittest.mock import patch

import odoo
from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from odoo.addons.biz_tenants.models import tenants_common as common


@tagged('post_install', '-at_install')
class AlertCase(TransactionCase):

    def setUp(self):
        super().setUp()
        self.service = self.env['biz.tenants']
        self.Alert = self.env['biz.alert'].sudo()
        # F28 — inside the transaction, and rolled back with it.
        self.env['biz.rollout'].sudo().search(
            [('state', 'not in', ('done', 'aborted'))]).write(
                {'state': 'aborted'})
        self.env['biz.tenant'].sudo().search(
            [('state', '!=', 'decommissioned')]).write(
                {'state': 'decommissioned'})
        self.Alert.search([]).unlink()
        self.tenant = self.env['biz.tenant'].sudo().create({
            'name': 'Ann Ltd', 'slug': 'zzannalerts', 'state': 'live',
        })


@tagged('post_install', '-at_install')
class TestTheChannelIsHonestlyDark(AlertCase):
    """T8 — everything that would send is built, and says plainly that it did
    not."""

    def test_with_no_mail_account_the_platform_says_what_it_cannot_do(self):
        can, why = self.service._mail_capability()
        if self.env['ir.mail_server'].sudo().search_count([]):
            self.skipTest("this platform has an outgoing mail account")
        self.assertFalse(can)
        self.assertIn('no outgoing mail account', why)
        self.assertNotIn('odoo', why.lower())

    def test_the_send_path_returns_dark_and_raises_nothing(self):
        """⚠ Ledger F40 and F67 together: it returns `('dark', reason)`, it
        does not raise, and it does not add to the pile of messages nobody can
        send."""
        before = self.env['mail.mail'].sudo().search_count([])
        state, reason = self.service._send_alert_mail('subject', 'body')
        self.assertEqual(state, 'dark')
        self.assertTrue(reason)
        self.assertEqual(self.env['mail.mail'].sudo().search_count([]), before)

    def test_under_a_test_run_no_message_is_even_built(self):
        """⚠ Ledger F67. The suite's own attempts to send wrote error lines
        into the very log the rollout's health gate reads."""
        self.assertTrue(odoo.tools.config['test_enable'],
                        'this assertion only means anything under a test run')
        state, reason = self.service._send_alert_mail('s', 'b',
                                                      recipients=['a@b.com'])
        self.assertEqual(state, 'dark')
        self.assertIn('test run', reason)

    def test_send_a_test_email_answers_in_one_plain_sentence(self):
        """⚠ Never a stack trace and never a lie."""
        if self.env['ir.mail_server'].sudo().search_count([]):
            self.skipTest("this platform has an outgoing mail account")
        res = self.service.mail_test()
        self.assertFalse(res['ok'])
        self.assertEqual(res['state'], 'dark')
        self.assertIn('no outgoing mail account', res['message'])
        self.assertIn('press this again', res['message'])
        self.assertIn('nothing is lost', res['message'].lower())
        for banned in ('Traceback', 'odoo', 'Exception'):
            self.assertNotIn(banned, res['message'])

    def test_an_alert_that_was_never_sent_never_says_it_was(self):
        """⚠ Ledger F40. If a send fails and the stamp is written anyway, the
        problem falls silent for two hours on the strength of a message nobody
        received."""
        alert = self.Alert.create({
            'key': 'zz:test', 'kind': 'disk_low', 'severity': 'critical',
            'subject': 'A test', 'body_text': 'x'})
        self.service._speak(alert, self.Alert.browse(),
                            fields.Datetime.now())
        self.assertFalse(alert.spoken_at)
        self.assertEqual(alert.channel_state, 'dark')
        self.assertTrue(alert.channel_reason)

    def test_the_platform_checks_do_not_hide_themselves(self):
        """⚠ Ledger F42. The card that went away the moment its checks passed
        took the "Send a test email" button with it — and that button is wanted
        on a good day too."""
        rows = self.service.platform_checks()
        keys = [r['key'] for r in rows]
        self.assertEqual(keys, ['mail', 'status_page', 'capacity'])
        for row in rows:
            self.assertTrue(row['hint'], row['key'])
            self.assertNotIn('odoo', row['hint'].lower(), row['key'])
        mail_row = [r for r in rows if r['key'] == 'mail'][0]
        self.assertEqual(mail_row['action_label'], 'Send a test email')


@tagged('post_install', '-at_install')
class TestTheSweep(AlertCase):
    """T7 — dedup, reconcile, and the screen that is the channel."""

    def _readings(self, **kw):
        row = {
            'now': fields.Datetime.now(),
            'tenants': [{
                'id': self.tenant.id, 'name': 'Ann Ltd',
                'slug': self.tenant.slug, 'state': 'live', 'health': 'ok',
                'last_backup_at': None, 'last_backup_failed': False,
                'last_backup_small': False, 'cert_state': 'own',
                'cert_days_left': 60, 'error_lines': 0, 'release_state': 'on',
                'behind_count': 0, 'stale_count': 0,
            }],
            'disk': {'free_pct': 60, 'free_gb': 30.0, 'total_gb': 58.0},
            'memory': {'total_mb': 1910, 'available_mb': 900},
            'capacity': {'level': 'ok', 'reason': 'Room.'},
            'mail': {'can_send': True, 'reason': ''},
            'rollout': {}, 'master_errors': 0,
            'status_page': {'writable': True, 'age_min': 1, 'reason': ''},
        }
        row.update(kw)
        return row

    def _sweep(self, readings):
        with patch.object(type(self.service), '_gather_readings',
                          return_value=readings), \
             patch.object(self.env.cr, 'commit', side_effect=lambda: None):
            self.service._cron_alerts()

    def test_a_problem_is_created_once_and_bumped_afterwards(self):
        self._sweep(self._readings())
        rows = self.Alert.search([('key', '=', 'backup_missing:%s'
                                   % self.tenant.slug)])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows.count, 1)
        first_seen = rows.first_seen
        self._sweep(self._readings())
        rows = self.Alert.search([('key', '=', 'backup_missing:%s'
                                   % self.tenant.slug)])
        self.assertEqual(len(rows), 1, 'a second row for the same problem')
        self.assertEqual(rows.count, 2)
        self.assertEqual(rows.first_seen, first_seen)

    def test_a_clean_reading_closes_it(self):
        self._sweep(self._readings())
        rows = self._readings()
        rows['tenants'][0]['last_backup_at'] = fields.Datetime.now()
        self._sweep(rows)
        alert = self.Alert.search([('key', '=', 'backup_missing:%s'
                                    % self.tenant.slug)])
        self.assertEqual(alert.state, 'resolved')
        self.assertTrue(alert.resolved_at)

    def test_the_alert_carries_the_customer_it_is_about(self):
        self._sweep(self._readings())
        alert = self.Alert.search([('kind', '=', 'backup_missing')], limit=1)
        self.assertEqual(alert.tenant_id, self.tenant)

    def test_nothing_is_stamped_as_told_while_the_channel_is_dark(self):
        self._sweep(self._readings())
        for alert in self.Alert.search([]):
            self.assertFalse(alert.spoken_at, alert.key)
            self.assertEqual(alert.channel_state, 'dark')

    def test_the_screen_groups_by_how_urgent_it_is(self):
        self._sweep(self._readings(
            disk={'free_pct': 3, 'free_gb': 1.0, 'total_gb': 58.0},
            capacity={'level': 'full', 'reason': 'No room.'}))
        data = self.service.alerts_data()
        self.assertTrue(data['critical'])
        self.assertTrue(data['warning'])
        self.assertEqual(data['open_count'],
                         len(data['critical']) + len(data['warning'])
                         + len(data['info']) + len(data['acknowledged']))

    def test_since_you_were_last_here_is_measured_from_the_last_visit(self):
        """With nothing being emailed, this strip is how the owner finds out
        that anything happened at all.

        The last visit is stamped explicitly rather than by calling the screen
        first: a sweep in the same SECOND as the visit is neither new nor old,
        and a test that turns on which side of a tie the code falls is a test
        that fails on a fast machine and passes on a slow one.
        """
        self.env['ir.config_parameter'].sudo().set_param(
            common.P_ALERTS_SEEN,
            (fields.Datetime.now() - timedelta(hours=1)).strftime(
                '%Y-%m-%d %H:%M:%S'))
        self._sweep(self._readings())
        data = self.service.alerts_data()
        self.assertGreater(data['new_count'], 0)
        # Looking again, having now been seen: the count falls back to nought.
        data = self.service.alerts_data()
        self.assertEqual(data['new_count'], 0)

    def test_reading_the_screen_without_marking_it_seen_is_possible(self):
        self.env['ir.config_parameter'].sudo().set_param(
            common.P_ALERTS_SEEN,
            (fields.Datetime.now() - timedelta(hours=1)).strftime(
                '%Y-%m-%d %H:%M:%S'))
        self._sweep(self._readings())
        first = self.service.alerts_data(mark_seen=False)
        second = self.service.alerts_data(mark_seen=False)
        self.assertEqual(first['new_count'], second['new_count'])

    def test_saying_you_know_stops_it_reminding_and_leaves_it_open(self):
        self._sweep(self._readings())
        alert = self.Alert.search([('kind', '=', 'backup_missing')], limit=1)
        self.service.alert_ack(alert.id)
        self.assertEqual(alert.state, 'acknowledged')
        self.assertEqual(alert.acknowledged_by, self.env.user)

    def test_removing_an_alert_is_a_different_act_from_closing_it(self):
        """⚠ Ledger F41. A RESOLVED urgent alert becomes an incident on the
        public page for seven days, which is right for something that really
        happened and wrong for one raised while somebody was testing the
        alarm."""
        self._sweep(self._readings())
        alert = self.Alert.search([('kind', '=', 'backup_missing')], limit=1)
        alert_id = alert.id
        self.service.alert_delete(alert_id)
        self.assertFalse(self.Alert.browse(alert_id).exists())

    def test_a_resolved_urgent_alert_does_reach_the_public_page(self):
        """The other half of the same rule, so the difference is proved rather
        than asserted: closing one puts an incident on the page."""
        self.Alert.create({
            'key': 'zz:done', 'kind': 'tenant_unreachable',
            'severity': 'critical', 'subject': 'Ann Ltd was unreachable',
            'body_text': 'x', 'tenant_id': self.tenant.id,
            'state': 'resolved', 'resolved_at': fields.Datetime.now(),
            'first_seen': fields.Datetime.now()})
        state = self.service._status_inputs()
        self.assertEqual(len(state['incidents']), 1)
        self.assertNotIn('Ann', repr(state))

    def test_the_banner_lights_up_for_something_urgent_and_says_it_was_not_sent(self):
        self._sweep(self._readings(
            disk={'free_pct': 3, 'free_gb': 1.0, 'total_gb': 58.0}))
        banner = self.service.alert_banner()
        self.assertEqual(banner['level'], 'critical')
        self.assertTrue(banner['dark'])
        self.assertTrue(banner['text'])

    def test_the_banner_is_silent_when_nothing_is_urgent(self):
        banner = self.service.alert_banner()
        self.assertEqual(banner['level'], '')

    def test_the_morning_summary_is_built_even_though_it_cannot_be_sent(self):
        self._sweep(self._readings())
        res = self.service._cron_alert_digest()
        self.assertEqual(res['state'], 'dark')
        self.assertTrue(res['lines'])
        self.assertTrue(res['heading'])


@tagged('post_install', '-at_install')
class TestCapacity(AlertCase):
    """T10 — the gauge, and the refusal that names the way out."""

    def _set(self, cost, reserve):
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param(common.P_TENANT_COST, str(cost))
        icp.set_param(common.P_CAPACITY_RESERVE, str(reserve))

    def test_the_cost_is_read_as_a_setting_and_not_as_a_constant(self):
        with patch.object(type(self.service), '_memory_reading',
                          return_value={'total_mb': 1910,
                                        'available_mb': 1000}):
            self._set(60, 400)
            self.assertEqual(self.service._capacity()['headroom'], 10)
            self._set(300, 400)
            self.assertEqual(self.service._capacity()['headroom'], 2)

    def test_at_nought_room_provisioning_is_refused_by_name(self):
        with patch.object(type(self.service), '_memory_reading',
                          return_value={'total_mb': 1910,
                                        'available_mb': 500}):
            self._set(4000, 400)
            with self.assertRaises(UserError) as caught:
                self.service._capacity_gate()
        message = str(caught.exception)
        self.assertIn('no room on this machine', message)
        self.assertIn('SAAS_RESIZE_RUNBOOK.md', message)
        self.assertIn(common.P_TENANT_COST, message)
        self.assertNotIn('odoo', message.lower().replace(
            'saas_resize_runbook.md', ''))

    def test_putting_the_setting_back_makes_the_refusal_go_away(self):
        with patch.object(type(self.service), '_memory_reading',
                          return_value={'total_mb': 1910,
                                        'available_mb': 1000}):
            self._set(4000, 400)
            with self.assertRaises(UserError):
                self.service._capacity_gate()
            self._set(60, 400)
            self.assertEqual(self.service._capacity_gate()['level'], 'ok')

    def test_a_cleared_setting_falls_back_rather_than_dividing_by_nought(self):
        self.env['ir.config_parameter'].sudo().set_param(
            common.P_TENANT_COST, '')
        self.assertEqual(common.tenant_cost_mb(self.env), 60.0)

    def test_the_dry_run_asks_the_same_question_the_real_run_will(self):
        """A preview that says "this would work" must never be followed by a
        refusal at the door."""
        with patch.object(type(self.service), '_memory_reading',
                          return_value={'total_mb': 1910,
                                        'available_mb': 500}):
            self._set(4000, 400)
            preview = self.service.provision_preview(
                {'name': 'Zed', 'slug': 'zzcapacity',
                 'contact_email': 'a@b.com'})
        self.assertFalse(preview['ok'])
        self.assertTrue([p for p in preview['problems']
                         if 'no room' in p.lower()])

    def test_the_fleet_screen_carries_the_gauge(self):
        fleet = self.service.get_fleet()
        self.assertIn('capacity', fleet)
        self.assertIn('headroom', fleet['capacity'])
        self.assertIn('reason', fleet['capacity'])
        self.assertIn('alert', fleet)


@tagged('post_install', '-at_install')
class TestThePublicPage(AlertCase):
    """T9 / T11 — the writer, the privacy, and the guard that keeps a test run
    off the public internet."""

    def test_under_a_test_run_the_writer_returns_early(self):
        """⚠ Ledger F44. A file written by a model is NOT rolled back by a
        test, and a suite run on the live platform once published a page built
        from customers that do not exist."""
        self.assertTrue(odoo.tools.config['test_enable'])
        res = self.service._write_status_page()
        self.assertEqual(res.get('skipped'), 'test run')

    def test_the_page_on_disk_does_not_move_across_a_test_run(self):
        """The behavioural half of the same rule, measured rather than
        asserted: the file's own timestamp before and after every path that
        could write it."""
        path = self.service._status_file()
        if not path or not os.path.exists(path):
            self.skipTest("this machine has no public page to watch")
        before = os.path.getmtime(path)
        self.service._write_status_page()
        self.service.status_page_refresh()
        self.service._refresh_status_page_quietly()
        self.service._cron_status_page()
        alert = self.Alert.create({
            'key': 'zz:page', 'kind': 'disk_low', 'severity': 'critical',
            'subject': 'x', 'body_text': 'y'})
        self.service.alert_ack(alert.id)
        self.service.alert_resolve(alert.id)
        self.assertEqual(os.path.getmtime(path), before,
                         'a test run rewrote the public page')

    def test_the_preview_is_available_even_though_the_writer_stands_down(self):
        """A test can still see what WOULD be published, which is the whole
        point of separating the render from the write."""
        page = self.service.status_page_preview()
        self.assertIn('<!doctype html>', page)
        self.assertNotIn('odoo', page.lower())

    def test_the_page_names_no_customer(self):
        self.Alert.create({
            'key': 'zz:down', 'kind': 'tenant_unreachable',
            'severity': 'critical',
            'subject': 'Ann Ltd cannot be reached',
            'body_text': 'Nobody at Ann Ltd can sign in. Open zzannalerts.',
            'tenant_id': self.tenant.id})
        page = self.service.status_page_preview()
        for name in ('Ann Ltd', 'zzannalerts'):
            self.assertNotIn(name, page, 'the public page names "%s"' % name)

    def test_a_message_to_customers_reaches_the_page_without_naming_them(self):
        # ⚠ A window that has already closed is DELIBERATELY dropped, so the
        # one here is still open. Getting that wrong once is how a public page
        # advertises last week's maintenance for ever.
        self.tenant.write({'notice': 'A short update is planned.',
                           'notice_kind': 'maintenance',
                           'notice_from': fields.Datetime.now(),
                           'notice_to': fields.Datetime.now()
                           + timedelta(hours=6)})
        state = self.service._status_inputs()
        self.assertEqual(len(state['notices']), 1)
        self.assertNotIn('Ann', repr(state['notices']))

    def test_a_message_whose_window_has_closed_is_dropped(self):
        """Otherwise the public page advertises last week's maintenance for
        ever, which is how a status page stops being read."""
        self.tenant.write({'notice': 'A short update was planned.',
                           'notice_kind': 'maintenance',
                           'notice_from': fields.Datetime.now()
                           - timedelta(hours=9),
                           'notice_to': fields.Datetime.now()
                           - timedelta(hours=3)})
        self.assertEqual(self.service._status_inputs()['notices'], [])

    def test_the_same_message_on_five_customers_is_one_line_in_public(self):
        second = self.env['biz.tenant'].sudo().create({
            'name': 'Bee Health', 'slug': 'zzbeealerts', 'state': 'live'})
        for rec in (self.tenant, second):
            rec.write({'notice': 'A short update is planned.',
                       'notice_kind': 'maintenance'})
        state = self.service._status_inputs()
        self.assertEqual(len(state['notices']), 1)

    def test_the_page_says_which_clock_it_speaks(self):
        """⚠ Ledger F38. A file on disk has no reader to ask what time it is."""
        self.env['ir.config_parameter'].sudo().set_param(
            common.P_STATUS_TZ, 'Asia/Ho_Chi_Minh')
        state = self.service._status_inputs()
        self.assertEqual(state['tz'], 'Asia/Ho_Chi_Minh')
        self.assertIn('Asia/Ho_Chi_Minh', self.service.status_page_preview())

    def test_a_missing_folder_is_reported_rather_than_raised(self):
        self.env['ir.config_parameter'].sudo().set_param(
            common.P_STATUS_DIR, '/nowhere/at/all/zz')
        reading = self.service._status_reading()
        self.assertFalse(reading['writable'])
        self.assertIn('does not exist', reading['reason'])
        # And it becomes an alert of its own rather than breaking a caller.
        self.assertEqual(self.service._refresh_status_page_quietly()['ok'],
                         True)   # under a test run the writer stands down

    def test_the_writer_uses_a_temp_file_and_a_rename(self):
        """A reader arriving mid-write must get the OLD page rather than half
        of the new one — the whole promise of this file is that it is there
        when nothing else is. Asserted on the source, because the behaviour is
        exactly what a test run is not allowed to perform."""
        from odoo.modules.module import get_module_path
        path = os.path.join(get_module_path('biz_tenants'), 'models',
                            'alert_service.py')
        with open(path, encoding='utf-8') as fh:
            body = fh.read().split('def _write_status_page', 1)[1]
        head = body.split('\n    def ', 1)[0]
        self.assertIn("path + '.tmp'", head)
        self.assertIn('os.replace(tmp, path)', head)


@tagged('post_install', '-at_install')
class TestTheGuard(AlertCase):
    """The alerts screen is the platform owner's, like everything else here."""

    def test_a_colleague_is_refused_every_new_door(self):
        from odoo.exceptions import AccessError
        plain = self.env['res.users'].sudo().create({
            'name': 'A colleague', 'login': 'bzt_h4b_colleague',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])]})
        service = self.env['biz.tenants'].with_user(plain)
        for method, args in (('alerts_data', []),
                             ('alert_banner', []),
                             ('alert_settings', []),
                             ('capacity_check', []),
                             ('rollout_state', []),
                             ('mail_test', []),
                             ('status_page_refresh', [])):
            with self.assertRaises(AccessError, msg=method):
                getattr(service, method)(*args)


@tagged('post_install', '-at_install')
class TestSettings(AlertCase):

    def test_a_bad_address_is_refused_by_name(self):
        with self.assertRaises(UserError) as caught:
            self.service.alert_settings_save({'alert_to': 'not-an-address'})
        self.assertIn('not-an-address', str(caught.exception))

    def test_a_threshold_outside_its_range_is_refused_with_the_range(self):
        with self.assertRaises(UserError) as caught:
            self.service.alert_settings_save(
                {'thresholds': {'disk_free_pct': 500}})
        self.assertIn('between', str(caught.exception))

    def test_a_threshold_that_is_not_a_number_is_refused(self):
        with self.assertRaises(UserError):
            self.service.alert_settings_save(
                {'thresholds': {'error_lines': 'lots'}})

    def test_a_saved_threshold_changes_what_counts_as_a_problem(self):
        self.service.alert_settings_save({'thresholds': {'error_lines': 99}})
        self.assertEqual(self.service._alert_thresholds()['error_lines'], 99)

    def test_the_settings_say_out_loud_that_the_cost_is_a_policy(self):
        """⚠ Ledger F34. Somebody will otherwise read a policy as a
        measurement."""
        data = self.service.alert_settings()
        self.assertIn('POLICY', data['cost_note'])
        self.assertIn('11 MB', data['cost_note'])
