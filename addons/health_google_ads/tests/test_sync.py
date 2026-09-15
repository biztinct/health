# -*- coding: utf-8 -*-
"""GA3 — the client reads, the window, and the sync engine.

Covers GA3-T01 … T07, T09, T10, T12, T13, T16.

Every HTTP call is replaced at the module level with a PLAIN FUNCTION
(`patch.object(gads, '_http_post_json', fn)`), never `autospec` — ledger
§5.76. The one wait in the engine is replaced the same way, so a retry test
takes no wall-clock time and can still assert the delays it asked for.
"""
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from odoo.addons.health_google_ads.models import google_ads_sync as gsync
from odoo.addons.health_google_ads.models.google_ads_campaign_day import (
    micros_to_amount,
)
from odoo.addons.health_google_ads.services import google_ads_client as gads
from odoo.addons.health_google_ads.services.google_ads_client import (
    GoogleAdsError,
)

from .common import BIG_CAMPAIGN_ID, OTHER_CAMPAIGN_ID, GoogleAdsGa3Case


@tagged('post_install', '-at_install')
class TestGoogleAdsSync(GoogleAdsGa3Case):

    # ==================================================================
    # GA3-T01 — the client parses Google's own spellings
    # ==================================================================
    def test_ga3_t01a_campaign_metadata_is_parsed(self):
        fake = self._fake_google()
        fake.campaigns = [
            fake.campaign_row(BIG_CAMPAIGN_ID, name='Hà Nội — Search',
                              status='ENABLED', channel='SEARCH'),
            fake.campaign_row(OTHER_CAMPAIGN_ID, name='HCM — PMax',
                              status='PAUSED', channel='PERFORMANCE_MAX'),
        ]
        client = self.account_a1._google_client()
        rows = client.list_campaigns(self.account_a1.customer_id)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['id'], BIG_CAMPAIGN_ID)
        # A STRING, not an int — the id is past 2**53 and an int() would
        # silently rename the campaign (rail R3).
        self.assertIsInstance(rows[0]['id'], str)
        self.assertEqual(rows[0]['name'], 'Hà Nội — Search')
        self.assertEqual(rows[0]['status'], 'ENABLED')
        self.assertEqual(rows[0]['advertising_channel_type'], 'SEARCH')
        self.assertEqual(rows[1]['advertising_channel_type'],
                         'PERFORMANCE_MAX')

    def test_ga3_t01b_metric_rows_keep_their_types(self):
        fake = self._fake_google()
        fake.campaign_days = [
            fake.day_row(BIG_CAMPAIGN_ID, '2026-09-01', impressions='123',
                         clicks='4', cost_micros='1230000', conversions=1.5),
        ]
        rows = self.account_a1._google_client().fetch_campaign_days(
            self.account_a1.customer_id, date(2026, 9, 1), date(2026, 9, 2))
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['campaign_id'], BIG_CAMPAIGN_ID)
        self.assertIsInstance(row['campaign_id'], str)
        self.assertEqual(row['date'], date(2026, 9, 1))
        self.assertEqual(row['impressions'], 123)
        self.assertEqual(row['clicks'], 4)
        # The exact string, untouched.
        self.assertEqual(row['cost_micros'], '1230000')
        self.assertIsInstance(row['cost_micros'], str)
        self.assertEqual(row['conversions'], 1.5)

    def test_ga3_t01c_three_pages_are_all_followed(self):
        fake = self._fake_google()
        fake.campaign_day_pages = [
            {'results': [fake.day_row(BIG_CAMPAIGN_ID, '2026-09-01')],
             'nextPageToken': '1'},
            {'results': [fake.day_row(BIG_CAMPAIGN_ID, '2026-09-02')],
             'nextPageToken': '2'},
            {'results': [fake.day_row(BIG_CAMPAIGN_ID, '2026-09-03')]},
        ]
        rows = self.account_a1._google_client().fetch_campaign_days(
            self.account_a1.customer_id, date(2026, 9, 1), date(2026, 9, 3))
        self.assertEqual([r['date'] for r in rows],
                         [date(2026, 9, 1), date(2026, 9, 2),
                          date(2026, 9, 3)])

    def test_ga3_t01d_an_impossible_window_is_refused(self):
        self._fake_google()
        client = self.account_a1._google_client()
        with self.assertRaises(GoogleAdsError) as caught:
            client.fetch_campaign_days(self.account_a1.customer_id,
                                       date(2026, 9, 10), date(2026, 9, 1))
        self.assertEqual(caught.exception.code, 'bad_window')
        with self.assertRaises(GoogleAdsError) as caught:
            client.fetch_campaign_days(self.account_a1.customer_id,
                                       date(2024, 1, 1), date(2026, 1, 1))
        self.assertEqual(caught.exception.code, 'bad_window')
        # A string is never accepted — the query is built from date objects.
        with self.assertRaises(GoogleAdsError) as caught:
            client.fetch_campaign_days(self.account_a1.customer_id,
                                       '2026-09-01', '2026-09-02')
        self.assertEqual(caught.exception.code, 'bad_window')

    def test_ga3_t01e_the_days_query_is_not_segmented_by_conversion_action(
            self):
        """Segmenting the metrics table by conversion action repeats every
        cost row once per action and multiplies spend (design §7.2)."""
        self.assertNotIn('segments.conversion_action', gads.Q_DAYS)
        self.assertIn('metrics.cost_micros', gads.Q_DAYS)
        self.assertIn('metrics.conversions', gads.Q_DAYS)

    # ==================================================================
    # GA3-T02 — the window is the ACCOUNT's calendar, not the server's
    # ==================================================================
    def test_ga3_t02_window_is_account_local(self):
        account = self.account_a1
        moment = datetime(2026, 9, 14, 17, 30, 0)
        with patch.object(fields.Datetime, 'now', staticmethod(
                lambda: moment)):
            account._internal().write(
                {'account_timezone': 'Asia/Ho_Chi_Minh'})
            self.assertEqual(account._sync_window(),
                             (date(2026, 8, 17), date(2026, 9, 15)))
            account._internal().write({'account_timezone': 'UTC'})
            self.assertEqual(account._sync_window(),
                             (date(2026, 8, 16), date(2026, 9, 14)))
            # A zone nobody has heard of falls back to UTC rather than taking
            # the whole sync down.
            account._internal().write({'account_timezone': 'Mars/Olympus'})
            self.assertEqual(account._sync_window(),
                             (date(2026, 8, 16), date(2026, 9, 14)))
        account._internal().write({'account_timezone': 'Asia/Ho_Chi_Minh'})

    # ==================================================================
    # GA3-T03 — the happy sync
    # ==================================================================
    def _arm_happy(self, fake, window):
        date_from, date_to = window
        days = [date_to - timedelta(days=2), date_to - timedelta(days=1),
                date_to]
        fake.campaigns = [
            fake.campaign_row(BIG_CAMPAIGN_ID, name='Hà Nội — Search'),
            fake.campaign_row(OTHER_CAMPAIGN_ID, name='HCM — Search',
                              status='PAUSED'),
        ]
        fake.campaign_days = [
            fake.day_row(BIG_CAMPAIGN_ID, day.isoformat(), impressions='100',
                         clicks='10', cost_micros='2000000', conversions=0.5)
            for day in days
        ] + [
            fake.day_row(OTHER_CAMPAIGN_ID, day.isoformat(),
                         impressions='50', clicks='5', cost_micros='1000000',
                         conversions=0.0)
            for day in days
        ]
        return days

    def test_ga3_t03_happy_sync_fills_the_cache(self):
        account = self.account_a1
        # A row somebody typed in by hand, for one of the ids Google will
        # answer for: it must be flipped to `provider` and renamed.
        manual = self.Campaign.create({
            'account_id': account.id,
            'external_campaign_id': BIG_CAMPAIGN_ID,
            'name': 'typed in by hand',
        })
        self.assertEqual(manual.source, 'manual')
        fake = self._fake_google()
        self._no_sleep()
        window = account._sync_window()
        self._arm_happy(fake, window)

        run = account._sync_reporting('scheduled')

        self.assertEqual(run.state, 'success')
        self.assertEqual(run.kind, 'scheduled')
        self.assertEqual(run.campaigns_seen, 2)
        self.assertEqual(run.rows_written, 6)
        self.assertEqual(run.rows_removed, 0)
        self.assertEqual(run.attempts, 1)
        self.assertTrue(run.finished_at)
        self.assertEqual((run.window_from, run.window_to), window)

        campaigns = self.Campaign.sudo().search(
            [('account_id', '=', account.id)])
        self.assertEqual(len(campaigns), 2)
        self.assertEqual(set(campaigns.mapped('source')), {'provider'})
        manual.invalidate_recordset()
        self.assertEqual(manual.name, 'Hà Nội — Search')
        self.assertEqual(manual.source, 'provider')
        self.assertTrue(manual.last_seen_at)
        self.assertEqual(manual.status_label, 'Running')
        paused = self._campaign_of(account, OTHER_CAMPAIGN_ID)
        self.assertEqual(paused.status_label, 'Paused')

        self.assertEqual(len(self._days_of(account)), 6)
        self.assertTrue(account.last_sync_success_at)
        self.assertFalse(account.last_error_code)
        self.assertEqual(account.reporting_state, 'connected')

        # Rollups filled from the cache, per campaign.
        manual.invalidate_recordset()
        self.assertEqual(manual.clicks_30d, 30)
        self.assertAlmostEqual(manual.spend_30d, 6.0, places=6)
        self.assertEqual((manual.window_from, manual.window_to), window)

    # ==================================================================
    # GA3-T04 — a second sync REPLACES the window and nothing else
    # ==================================================================
    def test_ga3_t04_second_sync_replaces_the_window_only(self):
        account = self.account_a1
        fake = self._fake_google()
        self._no_sleep()
        window = account._sync_window()
        days = self._arm_happy(fake, window)
        account._sync_reporting('scheduled')

        campaign = self._campaign_of(account, BIG_CAMPAIGN_ID)
        other = self._campaign_of(account, OTHER_CAMPAIGN_ID)
        # A day row OUTSIDE the window, which nothing in this phase may touch.
        outside = self.Day.sudo().create({
            'account_id': account.id, 'campaign_id': campaign.id,
            'date': window[0] - timedelta(days=5),
            'cost_micros': '999000', 'clicks': 9, 'impressions': 90,
        })

        # Google revises one day and stops reporting another (campaign, day).
        fake.campaign_days = [
            fake.day_row(BIG_CAMPAIGN_ID, day.isoformat(),
                         impressions='100', clicks='10',
                         cost_micros='2000000', conversions=0.5)
            for day in days
        ] + [
            fake.day_row(OTHER_CAMPAIGN_ID, day.isoformat(),
                         impressions='50', clicks='5',
                         cost_micros='1000000', conversions=0.0)
            for day in days[1:]
        ]
        fake.campaign_days[0] = fake.day_row(
            BIG_CAMPAIGN_ID, days[0].isoformat(), impressions='777',
            clicks='77', cost_micros='7000000', conversions=7.0)
        # A campaign Google no longer lists at all.
        fake.campaigns = [fake.campaign_row(BIG_CAMPAIGN_ID,
                                            name='Hà Nội — Search')]

        run = account._sync_reporting('scheduled')

        self.assertEqual(run.state, 'success')
        self.assertEqual(run.rows_removed, 1)
        revised = self.Day.sudo().search([
            ('account_id', '=', account.id),
            ('campaign_id', '=', campaign.id), ('date', '=', days[0])])
        self.assertEqual(revised.clicks, 77)
        self.assertAlmostEqual(revised.spend, 7.0, places=6)
        dropped = self.Day.sudo().search([
            ('account_id', '=', account.id),
            ('campaign_id', '=', other.id), ('date', '=', days[0])])
        self.assertFalse(dropped)
        # Untouched: outside the window, and a campaign row is never deleted.
        self.assertTrue(outside.exists())
        self.assertEqual(outside.clicks, 9)
        self.assertTrue(other.exists())

    # ==================================================================
    # GA3-T05 — a failed fetch changes NOTHING
    # ==================================================================
    def test_ga3_t05_a_failed_fetch_keeps_the_previous_figures(self):
        account = self.account_a1
        fake = self._fake_google()
        slept = self._no_sleep()
        window = account._sync_window()
        days = self._arm_happy(fake, window)
        account._sync_reporting('scheduled')
        before_success = account.last_sync_success_at
        before_count = len(self._days_of(account))
        sample = self.Day.sudo().search([
            ('account_id', '=', account.id),
            ('date', '=', days[0])], limit=1)
        before_clicks = sample.clicks

        # Page 1 answers, page 2 refuses — on every attempt.
        fake.campaign_day_pages = [
            {'results': [fake.day_row(BIG_CAMPAIGN_ID, days[0].isoformat())],
             'nextPageToken': '1'},
            GoogleAdsError('http_503', http_status=503, retryable=True,
                           request_id='req-503'),
        ]
        run = account._sync_reporting('scheduled')

        self.assertEqual(run.state, 'failed')
        self.assertEqual(run.attempts, 3)
        self.assertEqual(run.error_code, 'http_503')
        self.assertEqual(run.request_id, 'req-503')
        self.assertEqual(slept, [2, 8])
        self.assertEqual(len(self._days_of(account)), before_count)
        sample.invalidate_recordset()
        self.assertEqual(sample.clicks, before_clicks)
        self.assertEqual(account.last_sync_success_at, before_success)
        self.assertEqual(account.reporting_state, 'connected')
        self.assertEqual(account.last_error_code, 'http_503')

    # ==================================================================
    # GA3-T06 — a lost sign-in
    # ==================================================================
    def test_ga3_t06_needs_reconnect_leaves_the_cache_alone(self):
        account = self.account_a1
        fake = self._fake_google()
        slept = self._no_sleep()
        window = account._sync_window()
        self._arm_happy(fake, window)
        account._sync_reporting('scheduled')
        before_count = len(self._days_of(account))
        before_website = account.website_status

        fake.days_error = GoogleAdsError('invalid_grant', http_status=401,
                                         needs_reconnect=True)
        run = account._sync_reporting('scheduled')

        self.assertEqual(run.state, 'skipped_reconnect')
        self.assertEqual(run.error_code, 'invalid_grant')
        # Not retried: there is nothing to retry when the grant is gone.
        self.assertEqual(slept, [])
        self.assertEqual(account.reporting_state, 'action_required')
        self.assertEqual(len(self._days_of(account)), before_count)
        # A lost reporting grant is not a lost website connector (rail R6).
        self.assertEqual(account.website_status, before_website)

    # ==================================================================
    # GA3-T07 — exact micros, malformed rows, int4
    # ==================================================================
    def test_ga3_t07_money_is_exact_and_junk_is_refused(self):
        account = self.account_a1
        fake = self._fake_google()
        self._no_sleep()
        window = account._sync_window()
        day = window[1]
        fake.campaigns = [fake.campaign_row(BIG_CAMPAIGN_ID),
                          fake.campaign_row(OTHER_CAMPAIGN_ID)]
        fake.campaign_days = [
            fake.day_row(BIG_CAMPAIGN_ID, day.isoformat(),
                         impressions=str(2 ** 31), clicks='4',
                         cost_micros='12345678901234567890'),
            fake.day_row(OTHER_CAMPAIGN_ID, day.isoformat(),
                         cost_micros='abc'),
            fake.day_row(OTHER_CAMPAIGN_ID,
                         (day - timedelta(days=1)).isoformat(),
                         cost_micros='-1'),
        ]
        run = account._sync_reporting('scheduled')

        self.assertEqual(run.state, 'success')
        self.assertEqual(run.rows_written, 1)
        self.assertIn('2 malformed rows', run.detail_redacted)

        row = self.Day.sudo().search([('account_id', '=', account.id),
                                      ('date', '=', day)])
        self.assertEqual(len(row), 1)
        # Byte for byte, the string Google sent (rail R3).
        self.assertEqual(row.cost_micros, '12345678901234567890')
        # The DERIVATION is exact: nineteen digits of micros through `Decimal`,
        # with no float division anywhere in the chain.
        self.assertEqual(micros_to_amount('12345678901234567890'),
                         float(Decimal('12345678901234567890') / Decimal(10)
                               ** 6))
        # What is STORED is that figure rounded to the advertising account's
        # own currency, because a Monetary column has the currency's precision
        # and nothing finer. In đồng there are no sub-units at all, so the
        # stored spend is a whole number — the exact figure stays readable in
        # `cost_micros`, which is the whole reason that column is text.
        self.assertAlmostEqual(
            row.spend,
            self.currency.round(12345678901234.567890),
            delta=0.01)
        # int4 (§5.80): the ceiling, and the row says it is a floor.
        self.assertEqual(row.impressions, 2 ** 31 - 1)
        self.assertTrue(row.overflow)

    # ==================================================================
    # GA3-T09 — one run per account (REAL contention)
    # ==================================================================
    def test_ga3_t09_a_second_run_is_skipped_not_queued(self):
        account = self.account_a1
        fake = self._fake_google()
        self._no_sleep()
        self._arm_happy(fake, account._sync_window())

        # A REAL second connection takes the advisory lock. An advisory key is
        # just an integer, so two-connection contention IS stageable in a
        # TransactionCase — ledger §5.74's bonus; §5.63 only blocks it for row
        # locks, which cannot see an uncommitted row.
        other = self.registry.cursor()
        try:
            other.execute('SELECT pg_try_advisory_xact_lock(%s, %s)',
                          (gsync.SYNC_LOCK_CLASS, account.id))
            self.assertTrue(other.fetchone()[0])
            before_calls = len(fake.calls)
            run = account._sync_reporting('manual')
            self.assertEqual(run.state, 'skipped_locked')
            self.assertEqual(len(fake.calls), before_calls,
                             'a skipped run made a call to Google')
        finally:
            other.rollback()
            other.close()

        run = account._sync_reporting('manual')
        self.assertEqual(run.state, 'success')

    # ==================================================================
    # GA3-T10 — "Sync now" never talks to Google
    # ==================================================================
    def test_ga3_t10_sync_now_only_enqueues(self):
        account = self.account_a1
        fake = self._fake_google()
        self._no_sleep()
        self._arm_happy(fake, account._sync_window())
        account._internal().write({
            'last_sync_success_at': fields.Datetime.now() - timedelta(days=1)})

        triggers = []
        cron = self.env.ref(
            'health_google_ads.ir_cron_google_ads_sync_reporting')

        def fake_trigger(self, at=None):
            triggers.append(at)
            return True

        patcher = patch.object(type(cron), '_trigger', fake_trigger)
        patcher.start()
        self.addCleanup(patcher.stop)

        before_calls = len(fake.calls)
        result = account.action_sync_now()
        self.assertEqual(account.reporting_state, 'syncing')
        self.assertTrue(account.sync_requested_at)
        self.assertEqual(len(triggers), 1)
        self.assertEqual(len(fake.calls), before_calls,
                         'a browser button called Google')
        self.assertIn('display_notification', str(result))

        # Pressed twice: still one trigger, and the second press says so.
        second = account.action_sync_now()
        self.assertEqual(len(triggers), 1)
        self.assertEqual(second['params']['type'], 'warning')

        # A plain CRM user may not press it at all.
        with self.assertRaises(AccessError):
            account.with_user(self.crm_user).action_sync_now()

        # The job then does the work, as a MANUAL run.
        self.Account._cron_sync_reporting()
        run = self._runs_of(account).sorted('id')[-1]
        self.assertEqual(run.kind, 'manual')
        self.assertEqual(run.state, 'success')
        self.assertEqual(account.reporting_state, 'connected')
        self.assertFalse(account.sync_requested_at)

    def test_ga3_t10b_sync_now_refuses_an_unconnected_account(self):
        self._fake_google()
        with self.assertRaises(UserError):
            self.account_a2.action_sync_now()

    # ==================================================================
    # GA3-T12 — zero is not unknown
    # ==================================================================
    def test_ga3_t12_zero_versus_unknown_on_the_card(self):
        account = self.account_a1
        fake = self._fake_google()
        self._no_sleep()
        fake.campaigns = []
        fake.campaign_days = []

        run = account._sync_reporting('scheduled')
        self.assertEqual(run.state, 'success')
        self.assertEqual(run.rows_written, 0)
        self.assertEqual(run.campaigns_seen, 0)

        card = self.Account._center_card_payload()
        self.assertTrue(card['lines'][1].startswith('Reporting updated:'))
        self.assertNotIn('failed', card['lines'][1])
        stamped = card['lines'][1]

        fake.days_error = GoogleAdsError('http_503', http_status=503,
                                         retryable=True)
        failed = account._sync_reporting('scheduled')
        self.assertEqual(failed.state, 'failed')

        card = self.Account._center_card_payload()
        self.assertTrue(card['lines'][1].startswith(stamped))
        self.assertIn('last attempt failed (http_503)', card['lines'][1])

    def test_ga3_t12b_the_card_says_syncing_in_plain_words(self):
        self.account_a1._internal().write({'reporting_state': 'syncing'})
        card = self.Account._center_card_payload()
        reporting = [c for c in card['capabilities']
                     if c['key'] == 'reporting'][0]
        self.assertEqual(reporting['status_label'], 'Syncing…')
        self.assertEqual(reporting['tone'], 'info')

    # ==================================================================
    # GA3-T13 — the backfill queue
    # ==================================================================
    def test_ga3_t13_backfill_is_clamped_bounded_and_finite(self):
        account = self.account_a1
        fake = self._fake_google()
        self._no_sleep()
        fake.campaigns = [fake.campaign_row(BIG_CAMPAIGN_ID)]
        fake.campaign_days = []

        wizard = self.env['google.ads.backfill.wizard'].create({
            'account_id': account.id, 'days': 400})
        wizard.action_apply()
        today = account.sudo()._sync_today()
        window_from = account._sync_window()[0]
        self.assertEqual(account.backfill_cursor, window_from)
        # 400 clamped to 365.
        self.assertEqual(account.backfill_until,
                         today - timedelta(days=gsync.BACKFILL_MAX_DAYS))

        account._run_backfill_windows()
        runs = self._runs_of(account)
        self.assertEqual(len(runs), gsync.BACKFILL_WINDOWS_PER_RUN)
        self.assertEqual(set(runs.mapped('kind')), {'backfill'})
        self.assertEqual(set(runs.mapped('state')), {'success'})
        # Three 30-day windows walked backwards, none overlapping the rolling
        # one, and the cursor moved with them.
        self.assertEqual(max(runs.mapped('window_to')),
                         window_from - timedelta(days=1))
        self.assertEqual(account.backfill_cursor, min(runs.mapped(
            'window_from')))
        self.assertTrue(account.backfill_until)

        # Walk it out: the fields clear themselves when the cursor passes.
        for _index in range(20):
            if not account.backfill_until:
                break
            account._run_backfill_windows()
        self.assertFalse(account.backfill_until)
        self.assertFalse(account.backfill_cursor)

    # ==================================================================
    # GA3-T16 — one account's failure is not another's
    # ==================================================================
    def test_ga3_t16_the_job_isolates_accounts_and_prunes_runs(self):
        first, second = self.account_a1, self.account_a2
        second._internal().write({
            'account_timezone': 'Asia/Ho_Chi_Minh',
            'currency_id': self.currency.id,
        })
        self._grant(second)
        fake = self._fake_google()
        self._no_sleep()
        self._arm_happy(fake, first._sync_window())

        real_list = gads.GoogleAdsClient.list_campaigns

        def list_campaigns(client, customer_id, login_customer_id=None):
            if customer_id == first.customer_id:
                raise GoogleAdsError('CUSTOMER_NOT_ENABLED')
            return real_list(client, customer_id,
                             login_customer_id=login_customer_id)

        patcher = patch.object(gads.GoogleAdsClient, 'list_campaigns',
                               list_campaigns)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.Account._cron_sync_reporting()

        self.assertEqual(self._runs_of(first).sorted('id')[-1].state, 'failed')
        self.assertEqual(self._runs_of(second).sorted('id')[-1].state,
                         'success')

        # The log is capped per account, oldest dropped first.
        Run = self.Run.sudo()
        Run.create([{
            'account_id': first.id, 'kind': 'scheduled', 'state': 'success',
        } for _index in range(gsync.RUNS_KEPT + 5)])
        first._sync_prune_runs()
        self.assertEqual(len(self._runs_of(first)), gsync.RUNS_KEPT)
