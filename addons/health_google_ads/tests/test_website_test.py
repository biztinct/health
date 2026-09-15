# -*- coding: utf-8 -*-
"""GA1-T12 — the synthetic website proof creates nothing (rail R6)."""
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .common import GoogleAdsCase


@tagged('post_install', '-at_install')
class TestGoogleAdsWebsiteTest(GoogleAdsCase):

    def _counts(self):
        """Fresh-cursor-shaped counts: invalidate first, so a cached row the
        savepoint has already discarded cannot be counted (ledger §5.34's
        in-transaction cousin)."""
        self.env.invalidate_all()
        return (self.Lead.sudo().with_context(active_test=False).search_count([]),
                self.Touchpoint.sudo().search_count([]))

    def test_ga1_t12_the_test_creates_nothing(self):
        before = self._counts()
        result = self.account_a1.with_user(self.operator).action_test_website()
        after = self._counts()

        self.assertEqual(before, after,
                         'a synthetic run must leave no enquiry and no touch')
        self.assertEqual(result['type'], 'ir.actions.client')
        self.assertEqual(result['tag'], 'display_notification')

        self.account_a1.invalidate_recordset()
        self.assertTrue(self.account_a1.website_test_at,
                        'a passing test records when it passed')
        self.assertEqual(self.account_a1.website_test_kind, 'server')
        self.assertIn('matched', (self.account_a1.website_test_summary or ''),
                      'A1 carries a customer id, so the run must report a '
                      'match')

    def test_ga1_t12b_the_result_is_posted_to_the_chatter_once(self):
        before = self.env['mail.message'].sudo().search_count(
            [('model', '=', 'google.ads.account'),
             ('res_id', '=', self.account_a1.id)])
        self.account_a1.with_user(self.operator).action_test_website()
        after = self.env['mail.message'].sudo().search_count(
            [('model', '=', 'google.ads.account'),
             ('res_id', '=', self.account_a1.id)])
        self.assertEqual(after, before + 1, 'one message per run')

    def test_ga1_t12c_a_second_press_moves_the_timestamp(self):
        self.account_a1.with_user(self.operator).action_test_website()
        self.account_a1.invalidate_recordset()
        first = self.account_a1.website_test_at
        self.assertTrue(first)
        # Force a distinguishable "before" so the comparison is about the
        # write happening, not about clock resolution (ledger §5.35: Odoo
        # truncates datetimes to the second, so two presses inside one second
        # would otherwise be indistinguishable).
        self.account_a1.sudo().with_context(google_ads_internal=True).write(
            {'website_test_at': '2020-01-01 00:00:00'})
        self.account_a1.with_user(self.operator).action_test_website()
        self.account_a1.invalidate_recordset()
        self.assertNotEqual(str(self.account_a1.website_test_at),
                            '2020-01-01 00:00:00',
                            'a later run replaces the evidence')

    def test_ga1_t12d_a_plain_crm_user_is_refused(self):
        with self.assertRaises(AccessError):
            self.account_a1.with_user(self.crm_user).action_test_website()

    def test_ga1_t12e_no_connector_means_no_test_and_no_evidence(self):
        company = self.env['res.company'].create({'name': 'GADS NoConn Co'})
        account = self.Account.create({'name': 'GADS no connector',
                                       'company_id': company.id,
                                       'customer_id': '9999999999'})
        with self.assertRaises(UserError):
            account.action_test_website()
        account.invalidate_recordset()
        self.assertFalse(account.website_test_at)
        self.assertFalse(account.website_test_summary)

    def test_ga1_t12f_real_leads_alone_move_the_last_lead_stamp(self):
        """The synthetic rows roll back, so the compute — which reads real
        touchpoints — must be untouched by a test run."""
        self.account_a1.invalidate_recordset()
        before = self.account_a1.website_last_lead_at
        self.account_a1.with_user(self.operator).action_test_website()
        self.env.invalidate_all()
        self.assertEqual(self.account_a1.website_last_lead_at, before)
        self.assertEqual(self.account_a1.website_status, 'test_passed',
                         'a server test alone is "test passed", never '
                         '"receiving"')

    def test_ga1_t12g_the_card_chip_stays_honest_after_a_server_test(self):
        self.account_a1.with_user(self.operator).action_test_website()
        self.env.invalidate_all()
        card = self.env['google.ads.account'].with_company(
            self.company)._center_card_payload()
        caps = {c['key']: c for c in card['capabilities']}
        self.assertEqual(caps['website']['status'], 'test_passed')
        self.assertEqual(caps['reporting']['status'], 'not_connected')
        # Website evidence alone is "partially connected" — never "Connected".
        self.assertEqual(card['state_chip'], 'Partially connected')
        self.assertNotEqual(card['state_chip'], 'Connected')
