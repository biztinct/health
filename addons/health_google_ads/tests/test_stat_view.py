# -*- coding: utf-8 -*-
"""GA3 — the report itself: the SQL view, its screens and the rollups.

Covers GA3-T08, GA3-T11 and GA3-T15.

The view is the ONE place the reporting definitions of design §8 are written
down, so these are the tests that say what the numbers MEAN:

* a **new enquiry** is the touch that opened an enquiry — the one whose event
  id is the enquiry's own submission id;
* a **submission** is every accepted Google-attributed touch, including the
  ones added to an enquiry that already existed;
* a day is the ADVERTISING ACCOUNT's day, not the server's, so a touch at
  17:30 UTC on the 14th belongs to the 15th in `Asia/Ho_Chi_Minh`;
* zero is not unknown: a day Google has answered for reads `has_metrics` True,
  a day it has not reads False with a zero beside it.
"""
from datetime import date, datetime, time, timedelta

from lxml import etree

from odoo.tests import tagged

from .common import (
    BIG_CAMPAIGN_ID,
    CUSTOMER_A1,
    OTHER_CAMPAIGN_ID,
    GoogleAdsGa3Case,
)

# 2026-09-14T17:30Z is 2026-09-15T00:30 in Asia/Ho_Chi_Minh. The whole of
# rail R4 is in that one line.
TOUCH_INSTANT = datetime(2026, 9, 14, 17, 30, 0)
TOUCH_LOCAL_DAY = date(2026, 9, 15)
METRICS_ONLY_DAY = date(2026, 9, 10)


@tagged('post_install', '-at_install')
class TestGoogleAdsStatView(GoogleAdsGa3Case):

    # ==================================================================
    # Fixtures
    # ==================================================================
    def _seed_touches(self):
        """Three Google touches on A1, all at the SAME UTC instant.

        One opens an enquiry, one is merged into an older organic enquiry, and
        one names a campaign this system has never heard of.
        """
        account = self.account_a1
        campaign = self.Campaign.create({
            'account_id': account.id,
            'external_campaign_id': BIG_CAMPAIGN_ID,
            'name': 'Hà Nội — Search',
        })

        # (1) A NEW enquiry: the touch that created it.
        created = self.Service.process_submission(self._google_payload(0))
        self.assertEqual(created['status'], 'created')
        new_lead = self._lead_of(created)
        self.assertEqual(new_lead.google_ads_origin, 'website')

        # (2) An organic enquiry, then a paid follow-up that MERGES into it.
        #     A submission, never a new enquiry (design §8).
        organic = self._payload(1)
        older = self._lead_of(self.Service.process_submission(organic))
        self.assertFalse(older.google_ads_origin)
        follow_up = self._payload(
            1, name=organic['name'],
            utm={'source': 'google', 'medium': 'cpc'},
            click_ids={'gclid': 'EAIaGA3merged'},
            google_ads={'customer_id': CUSTOMER_A1,
                        'campaign_id': BIG_CAMPAIGN_ID})
        merged = self.Service.process_submission(follow_up)
        self.assertEqual(merged['status'], 'merged')

        # (3) A touch naming a campaign no row explains.
        stray = self.Service.process_submission(self._google_payload(
            2, google_ads={'customer_id': CUSTOMER_A1,
                           'campaign_id': OTHER_CAMPAIGN_ID}))
        self.assertEqual(stray['status'], 'created')

        # Every Google touch onto the same UTC instant, so the day boundary is
        # the only thing under test.
        touches = self.Touchpoint.sudo().search(
            [('google_ads_account_id', '=', account.id),
             ('google_ads_origin', '!=', False)])
        self.assertEqual(len(touches), 3)
        touches.write({'occurred_at': TOUCH_INSTANT})
        self.env.flush_all()
        return campaign

    def _rows(self, account, campaign=None):
        domain = [('account_id', '=', account.id)]
        if campaign:
            domain.append(('campaign_id', '=', campaign.id))
        return self.Stat.sudo().search(domain)

    # ==================================================================
    # GA3-T08 — what the numbers mean
    # ==================================================================
    def test_ga3_t08_new_enquiries_submissions_and_local_days(self):
        account = self.account_a1
        campaign = self._seed_touches()

        rows = self._rows(account, campaign)
        self.assertEqual(len(rows), 1, 'one campaign, one local day')
        row = rows
        # 17:30 UTC on the 14th is the 15th where this account lives (R4).
        self.assertEqual(row.date, TOUCH_LOCAL_DAY)
        self.assertEqual(row.submissions, 2)
        self.assertEqual(row.new_enquiries, 1)
        # Nothing has been read from Google for that day.
        self.assertFalse(row.has_metrics)
        self.assertEqual(row.spend, 0.0)
        self.assertEqual(row.clicks, 0)
        self.assertEqual(row.company_id, account.company_id)
        self.assertEqual(row.currency_id, self.currency)

        # The stray touch is in NO view row, and is counted where an operator
        # can see it instead.
        self.assertEqual(len(self._rows(account)), 1)
        account.invalidate_recordset()
        self.assertEqual(account.unresolved_campaign_count, 1)

    def test_ga3_t08b_metrics_without_touches_is_a_zero_that_says_so(self):
        account = self.account_a1
        campaign = self._seed_touches()
        self.Day.sudo().create({
            'account_id': account.id, 'campaign_id': campaign.id,
            'date': METRICS_ONLY_DAY, 'currency_id': self.currency.id,
            'impressions': 900, 'clicks': 30, 'cost_micros': '5000000',
            'google_conversions': 2.0,
        })
        self.env.flush_all()

        rows = self._rows(account, campaign)
        self.assertEqual(len(rows), 2)
        metrics_day = rows.filtered(lambda r: r.date == METRICS_ONLY_DAY)
        touch_day = rows.filtered(lambda r: r.date == TOUCH_LOCAL_DAY)

        # A day Google answered for: figures, and no enquiries.
        self.assertTrue(metrics_day.has_metrics)
        self.assertEqual(metrics_day.clicks, 30)
        self.assertAlmostEqual(metrics_day.spend, self.currency.round(5.0),
                               delta=0.01)
        self.assertEqual(metrics_day.new_enquiries, 0)
        self.assertEqual(metrics_day.submissions, 0)

        # A day it has not: enquiries, and an honest zero beside them.
        self.assertFalse(touch_day.has_metrics)
        self.assertEqual(touch_day.spend, 0.0)
        self.assertEqual(touch_day.new_enquiries, 1)

    def test_ga3_t08c_another_account_never_borrows_these_touches(self):
        """The join is account AND campaign id, never campaign id alone."""
        account = self.account_a1
        self._seed_touches()
        twin = self.Campaign.create({
            'account_id': self.account_a2.id,
            'external_campaign_id': BIG_CAMPAIGN_ID,
            'name': 'the same number on another account',
        })
        self.env.flush_all()
        self.assertFalse(self._rows(self.account_a2, twin))
        self.assertEqual(len(self._rows(account)), 1)

    # ==================================================================
    # GA3-T11 — the screens say what the view means
    # ==================================================================
    def test_ga3_t11_pivot_arch_carries_the_currency_row(self):
        pivot = self.env.ref(
            'health_google_ads.view_google_ads_campaign_stat_pivot')
        arch = etree.fromstring(pivot.arch_db.encode())
        rows = [node.get('name') for node in arch.iter('field')
                if node.get('type') == 'row']
        # Rail R5 — money is never summed across currencies, so the currency
        # is a DIMENSION of the pivot rather than a column somebody may hide.
        self.assertIn('currency_id', rows)
        self.assertIn('campaign_id', rows)

        measures = [node.get('name') for node in arch.iter('field')
                    if node.get('type') == 'measure']
        # `has_metrics` is a yes/no about whether Google answered at all;
        # averaging it would read as a percentage of nothing.
        self.assertNotIn('has_metrics', measures)
        for name in ('spend', 'clicks', 'google_conversions', 'new_enquiries',
                     'submissions'):
            self.assertIn(name, measures)

        # §5.93 — a `search_default_` on the VIEW would erase the arch rows.
        # The grouping the list wants lives on the ACTION.
        self.assertNotIn('search_default_', pivot.arch_db)
        action = self.env.ref(
            'health_google_ads.action_google_ads_campaign_stat')
        self.assertIn('search_default_group_campaign', action.context)
        self.assertIn('search_default_last_30', action.context)

    def test_ga3_t11b_the_account_button_opens_its_own_account_only(self):
        action = self.account_a1.action_open_report()
        self.assertEqual(action['res_model'], 'google.ads.campaign.stat')
        self.assertIn(('account_id', '=', self.account_a1.id),
                      [tuple(clause) for clause in action['domain']])
        self.assertEqual(action['context']['search_default_group_campaign'], 1)
        runs = self.account_a1.action_open_sync_runs()
        self.assertEqual(runs['res_model'], 'google.ads.sync.run')

    # ==================================================================
    # GA3-T15 — the rollups are the view, summed
    # ==================================================================
    def test_ga3_t15_rollups_match_the_view(self):
        account = self.account_a1
        campaign = self._seed_touches()
        fake = self._fake_google()
        self._no_sleep()
        window = account._sync_window()
        days = [window[1] - timedelta(days=index) for index in (2, 1, 0)]
        # Move the touches INSIDE the window Google answers for, whatever the
        # day the suite happens to run on: 03:00 UTC is mid-morning in
        # Asia/Ho_Chi_Minh, so the account-local day is `days[0]` exactly.
        self.Touchpoint.sudo().search(
            [('google_ads_account_id', '=', account.id),
             ('google_ads_origin', '!=', False)]).write(
            {'occurred_at': datetime.combine(days[0], time(3, 0))})
        self.env.flush_all()
        fake.campaigns = [fake.campaign_row(BIG_CAMPAIGN_ID,
                                            name='Hà Nội — Search')]
        fake.campaign_days = [
            fake.day_row(BIG_CAMPAIGN_ID, day.isoformat(), impressions='100',
                         clicks='10', cost_micros='2000000', conversions=0.5)
            for day in days
        ]
        run = account._sync_reporting('scheduled')
        self.assertEqual(run.state, 'success')

        campaign.invalidate_recordset()
        rows = self.Stat.sudo().search([
            ('account_id', '=', account.id),
            ('campaign_id', '=', campaign.id),
            ('date', '>=', window[0]), ('date', '<=', window[1])])
        self.assertEqual(campaign.clicks_30d, sum(rows.mapped('clicks')))
        self.assertEqual(campaign.impressions_30d,
                         sum(rows.mapped('impressions')))
        self.assertAlmostEqual(campaign.spend_30d, sum(rows.mapped('spend')),
                               delta=0.01)
        self.assertAlmostEqual(campaign.conversions_30d,
                               sum(rows.mapped('google_conversions')),
                               delta=0.0001)
        self.assertEqual(campaign.new_enquiries_30d,
                         sum(rows.mapped('new_enquiries')))
        self.assertEqual(campaign.submissions_30d,
                         sum(rows.mapped('submissions')))
        self.assertEqual((campaign.window_from, campaign.window_to), window)

        # Cost per new enquiry is spend over OUR enquiries, and it says so.
        if campaign.new_enquiries_30d:
            self.assertAlmostEqual(
                campaign.cost_per_new_enquiry_30d,
                campaign.spend_30d / campaign.new_enquiries_30d, delta=0.01)
            self.assertNotEqual(campaign.cost_per_new_enquiry_display, '—')

    def test_ga3_t15b_no_enquiries_shows_a_dash_not_a_zero(self):
        account = self.account_a1
        campaign = self.Campaign.create({
            'account_id': account.id,
            'external_campaign_id': OTHER_CAMPAIGN_ID,
            'name': 'nobody enquired',
        })
        campaign.write({'spend_30d': 1000.0, 'new_enquiries_30d': 0,
                        'cost_per_new_enquiry_30d': 0.0})
        # A zero would read as "these enquiries were free", which is the
        # opposite of what an empty denominator means.
        self.assertEqual(campaign.cost_per_new_enquiry_display, '—')
        campaign.write({'new_enquiries_30d': 4,
                        'cost_per_new_enquiry_30d': 250.0})
        self.assertNotEqual(campaign.cost_per_new_enquiry_display, '—')
        self.assertIn('250', campaign.cost_per_new_enquiry_display)
