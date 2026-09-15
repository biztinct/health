# -*- coding: utf-8 -*-
"""GA3 — who may read the figures, and what the screens call things.

Covers GA3-T14 (access) and GA3-T17 (plain words, no vendor name anywhere a
clinic can read).

Spend is commercially sensitive and it is money: the three new models are
readable by account-level operators only, writable by nobody but the job, and
fenced by a GLOBAL company rule so one clinic's figures can never appear on
another clinic's screen.
"""
from datetime import date

from odoo.exceptions import AccessError
from odoo.tests import tagged

from .common import BIG_CAMPAIGN_ID, GoogleAdsGa3Case

GA3_MODELS = ('google.ads.campaign.day', 'google.ads.sync.run',
              'google.ads.campaign.stat', 'google.ads.backfill.wizard')


@tagged('post_install', '-at_install')
class TestGoogleAdsReportingAccess(GoogleAdsGa3Case):

    def _seed_one_day(self):
        campaign = self.Campaign.create({
            'account_id': self.account_a1.id,
            'external_campaign_id': BIG_CAMPAIGN_ID,
            'name': 'Hà Nội — Search',
        })
        day = self.Day.sudo().create({
            'account_id': self.account_a1.id,
            'campaign_id': campaign.id,
            'date': date(2026, 9, 15),
            'currency_id': self.currency.id,
            'impressions': 100, 'clicks': 10, 'cost_micros': '2000000',
        })
        run = self.Run.sudo().create({
            'account_id': self.account_a1.id,
            'kind': 'scheduled', 'state': 'success',
        })
        self.env.flush_all()
        return campaign, day, run

    # ==================================================================
    # GA3-T14 — access
    # ==================================================================
    def test_ga3_t14_ordinary_staff_cannot_read_the_figures(self):
        self._seed_one_day()
        for model in ('google.ads.campaign.day', 'google.ads.sync.run',
                      'google.ads.campaign.stat'):
            with self.assertRaises(AccessError, msg=model):
                self.env[model].with_user(self.crm_user).search([])

    def test_ga3_t14b_another_clinic_reads_none_of_these_rows(self):
        """Not an error — an EMPTY answer. A refusal would confirm the rows
        exist; the company rule simply makes them invisible."""
        campaign, day, run = self._seed_one_day()
        self.assertTrue(self.Day.with_user(self.operator).search(
            [('id', '=', day.id)]), 'the owning clinic still sees its own row')

        other = self.Day.with_user(self.operator2).search([])
        self.assertFalse(other)
        self.assertFalse(self.Run.with_user(self.operator2).search([]))
        self.assertFalse(self.Stat.with_user(self.operator2).search([]))

    def test_ga3_t14c_an_operator_cannot_write_the_cache_by_hand(self):
        campaign, day, run = self._seed_one_day()
        with self.assertRaises(AccessError):
            self.Day.with_user(self.operator).create({
                'account_id': self.account_a1.id,
                'campaign_id': campaign.id,
                'date': date(2026, 9, 16),
            })
        with self.assertRaises(AccessError):
            day.with_user(self.operator).write({'clicks': 9999})
        with self.assertRaises(AccessError):
            run.with_user(self.operator).write({'state': 'success'})
        # And the report is readable but never writable, by anyone.
        stat = self.Stat.with_user(self.operator).search([], limit=1)
        self.assertTrue(stat)
        with self.assertRaises(AccessError):
            stat.write({'clicks': 1})

    def test_ga3_t14d_the_backfill_request_is_operator_only(self):
        with self.assertRaises(AccessError):
            self.env['google.ads.backfill.wizard'].with_user(
                self.crm_user).create({'account_id': self.account_a1.id})

    # ==================================================================
    # GA3-T17 — plain words, and no vendor name on any screen
    # ==================================================================
    def test_ga3_t17_no_vendor_name_in_any_new_label(self):
        """The product is white-labelled: the application vendor's name may
        appear in no string a clinic can read. (Google IS named, on purpose —
        it is the advertising platform the clinic actually uses.)"""
        offenders = []
        for model in GA3_MODELS:
            for name, spec in self.env[model].fields_get().items():
                for key in ('string', 'help'):
                    text = spec.get(key) or ''
                    if 'odoo' in text.lower():
                        offenders.append('%s.%s %s: %s' % (model, name, key,
                                                           text))
                for _value, label in spec.get('selection') or []:
                    if 'odoo' in (label or '').lower():
                        offenders.append('%s.%s selection: %s'
                                         % (model, name, label))
        self.assertFalse(offenders, 'vendor name on a clinic screen:\n%s'
                         % '\n'.join(offenders))

    def test_ga3_t17b_status_and_result_labels_are_plain_words(self):
        campaign = self.Campaign.create({
            'account_id': self.account_a1.id,
            'external_campaign_id': BIG_CAMPAIGN_ID,
            'name': 'Hà Nội — Search', 'status': 'ENABLED',
        })
        self.assertEqual(campaign.status_label, 'Running')
        campaign.write({'status': 'PAUSED'})
        self.assertEqual(campaign.status_label, 'Paused')
        campaign.write({'status': 'REMOVED'})
        self.assertEqual(campaign.status_label, 'Removed')
        campaign.write({'status': 'SOMETHING_NEW'})
        self.assertEqual(campaign.status_label, 'Unknown')

        # The honesty log reads as sentences, not as enum names.
        labels = dict(self.Run._fields['state'].selection)
        self.assertEqual(labels['skipped_locked'], 'Skipped — already running')
        self.assertEqual(labels['skipped_reconnect'],
                         'Skipped — sign-in needed')
        kinds = dict(self.Run._fields['kind'].selection)
        self.assertEqual(kinds['backfill'], 'Older days')

    def test_ga3_t17c_the_report_action_explains_zero_versus_unknown(self):
        action = self.env.ref(
            'health_google_ads.action_google_ads_campaign_stat')
        self.assertIn('not expected to match', action.help)
        self.assertIn('not because nothing was spent', action.help)
        self.assertNotIn('Odoo', action.help)

    def test_ga3_t17d_the_sidebar_leaf_matches_the_new_screens(self):
        """The CMS sidebar highlights a leaf by action and by model; a screen
        missing from both lists opens with nothing lit up."""
        item = self.env.ref(
            'health_google_ads.item_google_ads', raise_if_not_found=False)
        if not item:
            self.skipTest('the Google Ads sidebar leaf is not installed here')
        self.assertIn('action_google_ads_campaign_stat',
                      item.match_action_xmlids)
        self.assertIn('action_google_ads_sync_runs', item.match_action_xmlids)
        self.assertIn('google.ads.campaign.stat', item.match_models)
