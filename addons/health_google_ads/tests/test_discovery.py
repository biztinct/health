# -*- coding: utf-8 -*-
"""GA2-T07 … T09 — finding the advertising account, and binding to it.

The directly accessible list is NOT the whole picture: a clinic whose ads are
run by an agency sees only a manager account, and the advertising accounts
hang underneath it. Everything here is about walking that hierarchy honestly —
and about the two things that must never happen: a manager account used as the
data row, and one advertising customer bound to two clinics.
"""
from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.health_google_ads.services import google_ads_client as gads

from .common import (
    CHILD_C1,
    CHILD_C2,
    CHILD_C3,
    CHILD_C4,
    DIRECT_D,
    MANAGER_M,
    FakeResponse,
    GoogleAdsGa2Case,
)


@tagged('post_install', '-at_install')
class TestGoogleAdsDiscovery(GoogleAdsGa2Case):

    def _hierarchy(self, **kwargs):
        """M is a manager with four children; D is a direct advertiser."""
        fake = self._fake_google(**kwargs)
        fake.accessible = [MANAGER_M, DIRECT_D]
        fake.customers = {
            MANAGER_M: fake.customer(MANAGER_M, name='Viet UC Manager',
                                     manager=True),
            DIRECT_D: fake.customer(DIRECT_D, name='Viet UC Direct'),
            CHILD_C1: fake.customer(CHILD_C1, name='Viet UC Hanoi'),
        }
        fake.children = {MANAGER_M: [
            fake.customer(CHILD_C1, name='Viet UC Hanoi', level='2'),
            fake.customer(CHILD_C2, name='Sub manager', manager=True,
                          level='2'),
            fake.customer(CHILD_C3, name='Hidden one', hidden=True, level='2'),
            fake.customer(CHILD_C4, name='Closed one', status='CANCELED',
                          level='2'),
        ]}
        return fake

    # ==================================================================
    # GA2-T07 — discovery
    # ==================================================================
    def test_ga2_t07_a_manager_is_walked_and_its_managers_are_dropped(self):
        fake = self._hierarchy()
        self._grant(self.draft, state='select_account')

        found = self.draft._discover_reporting_candidates()
        by_id = {entry['id']: entry for entry in found}

        self.assertEqual(set(by_id), {DIRECT_D, CHILD_C1, CHILD_C4},
                         'a manager row and a hidden row are not advertising '
                         'accounts a clinic can report on')
        self.assertNotIn(CHILD_C2, by_id)
        self.assertNotIn(CHILD_C3, by_id)
        self.assertNotIn(MANAGER_M, by_id)

        self.assertFalse(by_id[DIRECT_D]['login_customer_id'],
                         'a directly accessible advertiser needs no manager '
                         'context')
        self.assertEqual(by_id[CHILD_C1]['login_customer_id'], MANAGER_M)
        self.assertEqual(by_id[CHILD_C4]['login_customer_id'], MANAGER_M)
        # Kept, not hidden: the screen greys it out rather than pretending it
        # is not there.
        self.assertEqual(by_id[CHILD_C4]['status'], 'CANCELED')
        self.assertEqual(by_id[CHILD_C1]['currency'], 'VND')

    def test_ga2_t07b_the_manager_header_travels_only_on_the_children_call(self):
        fake = self._hierarchy()
        self._grant(self.draft, state='select_account')
        self.draft._discover_reporting_candidates()

        children_calls = [c for c in fake.calls
                          if c['kind'] == 'json'
                          and 'FROM customer_client' in (c['body'].get('query')
                                                         or '')]
        self.assertEqual(len(children_calls), 1)
        self.assertEqual(children_calls[0]['headers'].get('login-customer-id'),
                         MANAGER_M)

        direct_calls = [c for c in fake.calls
                        if c['kind'] == 'json'
                        and 'FROM customer ' in (c['body'].get('query') or '')]
        self.assertTrue(direct_calls)
        for call in direct_calls:
            self.assertNotIn('login-customer-id', call['headers'],
                             'a direct read must not claim a manager context')
            self.assertTrue(call['headers']['Authorization'].startswith(
                'Bearer '))
            self.assertTrue(call['headers']['developer-token'])

    def test_ga2_t07c_the_wizard_offers_exactly_those_lines(self):
        self._hierarchy()
        self._grant(self.draft, state='select_account')
        action = self.draft.action_list_reporting_accounts()
        self.assertEqual(action['res_model'], 'google.ads.account.select')
        wizard = self.env['google.ads.account.select'].browse(action['res_id'])
        self.assertEqual(set(wizard.line_ids.mapped('customer_id')),
                         {DIRECT_D, CHILD_C1, CHILD_C4})
        self.assertFalse(any(wizard.line_ids.mapped('is_manager')))

    def test_ga2_t07d_no_grant_means_no_listing(self):
        self._hierarchy()
        raised = None
        try:
            self.draft.action_list_reporting_accounts()
        except UserError as caught:
            raised = caught
        self.assertIsNotNone(raised)
        self.assertIn('Connect a Google account', str(raised))

    # ==================================================================
    # GA2-T08 — binding
    # ==================================================================
    def test_ga2_t08a_a_manager_can_never_be_the_data_row(self):
        fake = self._hierarchy()
        self._grant(self.draft, state='select_account')
        raised = None
        try:
            self.draft.action_select_reporting_account(MANAGER_M)
        except UserError as caught:
            raised = caught
        self.assertIsNotNone(raised)
        self.assertIn('manager', str(raised))
        self.draft.invalidate_recordset()
        self.assertFalse(self.draft.customer_id)
        self.assertNotEqual(self.draft.reporting_state, 'connected')

    def test_ga2_t08b_a_child_binds_with_its_manager_context(self):
        fake = self._hierarchy()
        self._grant(self.draft, state='select_account')

        self.draft.action_select_reporting_account(CHILD_C1, MANAGER_M)
        self.draft.invalidate_recordset()
        self.assertEqual(self.draft.customer_id, CHILD_C1)
        self.assertEqual(self.draft.login_customer_id, MANAGER_M)
        # From GA3 the binding step also QUEUES the first read, so the record
        # lands on `syncing` rather than `connected`: a screen that says
        # "Connected" and shows no figures at all invites exactly one question.
        self.assertEqual(self.draft.reporting_state, 'syncing')
        self.assertTrue(self.draft.sync_requested_at)
        self.assertEqual(self.draft.provider_name, 'Viet UC Hanoi')
        self.assertEqual(self.draft.currency_id.name, 'VND')
        self.assertEqual(self.draft.account_timezone, 'Asia/Ho_Chi_Minh')
        self.assertFalse(self.draft.last_error_code)
        # Queued, never fetched in the request (rail R7): no figures here.
        self.assertFalse(self.draft.last_sync_success_at)

        validation = [c for c in fake.calls if c['kind'] == 'json'][-1]
        self.assertEqual(validation['headers'].get('login-customer-id'),
                         MANAGER_M)

    def test_ga2_t08c_google_refusing_leaves_the_record_where_it_was(self):
        fake = self._hierarchy()
        self._grant(self.draft, state='select_account')
        fake.search_error = gads._error_from_response(FakeResponse(403, {
            'error': {'code': 403, 'status': 'PERMISSION_DENIED', 'details': [
                {'errors': [{'errorCode': {
                    'authorizationError': 'USER_PERMISSION_DENIED'},
                    'message': 'User doesn\'t have permission.'}]}]}}))

        raised = None
        try:
            self.draft.action_select_reporting_account(CHILD_C1)
        except UserError as caught:
            raised = caught
        self.assertIsNotNone(raised)
        self.assertIn('cannot read that advertising account', str(raised))
        # The evidence write happens before the raise; in a real RPC the
        # dispatcher's rollback takes it with the error (ledger §5.65), which
        # is why the STATE is what must not move.
        self.assertEqual(self.draft.last_error_code, 'USER_PERMISSION_DENIED')
        self.assertFalse(self.draft.customer_id)
        self.assertEqual(self.draft.reporting_state, 'select_account')

    def test_ga2_t08d_an_id_that_is_not_ten_digits_never_builds_a_url(self):
        fake = self._hierarchy()
        self._grant(self.draft, state='select_account')
        for bad in ('12345', 'abcdefghij', '12345678901'):
            raised = None
            try:
                self.draft.action_select_reporting_account(bad)
            except UserError as caught:
                raised = caught
            self.assertIsNotNone(raised, '%r must be refused' % bad)
        self.assertFalse([c for c in fake.calls if c['kind'] == 'json'],
                         'a malformed id must not reach Google')

    # ==================================================================
    # GA2-T09 — one advertising customer, one clinic
    # ==================================================================
    def test_ga2_t09_a_customer_bound_elsewhere_is_refused_without_naming_it(self):
        fake = self._hierarchy()
        other = self.Account.create({
            'name': 'GADS other clinic', 'company_id': self.company2.id,
            'customer_id': CHILD_C1,
        })
        self._grant(self.draft, state='select_account')

        raised = None
        try:
            self.draft.action_select_reporting_account(CHILD_C1, MANAGER_M)
        except UserError as caught:
            raised = caught
        self.assertIsNotNone(raised)
        message = str(raised)
        self.assertNotIn(self.company2.name, message,
                         'which other clinic holds it is not this operator\'s '
                         'business')
        self.assertNotIn(other.name, message)
        self.assertFalse([c for c in fake.calls if c['kind'] == 'json'],
                         'the clash is settled before Google is asked')

        other.invalidate_recordset()
        self.assertEqual(other.customer_id, CHILD_C1)
        self.assertEqual(other.reporting_state, 'not_connected')
        self.draft.invalidate_recordset()
        self.assertFalse(self.draft.customer_id)
