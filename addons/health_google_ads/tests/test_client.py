# -*- coding: utf-8 -*-
"""GA2-T10 … T13 — the token lifecycle and the read-only client.

Two things are being proven here that no amount of reading the code settles:
that two workers cannot both stampede a refresh (a REAL second connection
takes the lock), and that a provider error body never reaches a stored field
with a bearer token still in it.
"""
from datetime import timedelta
from unittest.mock import patch

import requests

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.health_care_command_channels.services import channel_crypto
from odoo.addons.health_google_ads.models.google_ads_account import (
    REPORTING_LOCK_CLASS,
)
from odoo.addons.health_google_ads.services import google_ads_client as gads

from .common import (
    CHILD_C1,
    CUSTOMER_A1,
    FIXTURE_ACCESS,
    FIXTURE_REFRESH,
    FakeResponse,
    GoogleAdsGa2Case,
)


@tagged('post_install', '-at_install')
class TestGoogleAdsClient(GoogleAdsGa2Case):

    # ==================================================================
    # GA2-T10 — refreshing an access token
    # ==================================================================
    def test_ga2_t10a_a_valid_token_costs_no_http_call(self):
        fake = self._fake_google()
        account = self._grant(self.account_a1, expires_in=3600)
        self.assertEqual(account._reporting_access_token(), FIXTURE_ACCESS)
        self.assertFalse(fake.calls,
                         'a token good for another hour must not be refreshed')

    def test_ga2_t10b_an_expired_token_is_refreshed_exactly_once(self):
        fake = self._fake_google()
        fake.token_queue = [{'access_token': 'fresh-access', 'expires_in': 900,
                             'scope': gads.SCOPE}]
        account = self._grant(self.account_a1, expires_in=-120)
        before = fields.Datetime.now()

        self.assertEqual(account._reporting_access_token(), 'fresh-access')
        self.assertEqual(len([c for c in fake.calls if c['kind'] == 'form']), 1)
        posted = fake.calls[-1]
        self.assertEqual(posted['url'], gads.TOKEN_URL)
        self.assertEqual(posted['data']['grant_type'], 'refresh_token')
        self.assertEqual(posted['data']['refresh_token'], FIXTURE_REFRESH)

        secure = account.sudo()
        secure.invalidate_recordset()
        self.assertEqual(
            channel_crypto.decrypt(self.env, secure.access_token_enc),
            'fresh-access')
        # expires_in honoured, to the second.
        self.assertLessEqual(abs((secure.token_expires_at
                                  - (before + timedelta(seconds=900))
                                  ).total_seconds()), 5)
        # A response with no refresh token keeps ours (Google rarely rotates).
        self.assertEqual(
            channel_crypto.decrypt(self.env, secure.refresh_token_enc),
            FIXTURE_REFRESH)

    def test_ga2_t10c_a_rotated_refresh_token_replaces_ours(self):
        fake = self._fake_google()
        fake.token_queue = [{'access_token': 'a2', 'expires_in': 900,
                             'refresh_token': 'rotated-refresh',
                             'scope': gads.SCOPE}]
        account = self._grant(self.account_a1, expires_in=-120)
        account._reporting_access_token()
        secure = account.sudo()
        secure.invalidate_recordset()
        self.assertEqual(
            channel_crypto.decrypt(self.env, secure.refresh_token_enc),
            'rotated-refresh')

    def test_ga2_t10d_no_grant_at_all_asks_for_a_sign_in(self):
        self._fake_google()
        account = self._grant(self.account_a1, access=None, refresh=None,
                              expires_in=None, state='not_connected')
        raised = None
        try:
            account._reporting_access_token()
        except gads.GoogleAdsError as caught:
            raised = caught
        self.assertIsNotNone(raised)
        self.assertEqual(raised.code, 'no_grant')
        self.assertTrue(raised.needs_reconnect)

    # ==================================================================
    # GA2-T11 — a withdrawn grant, and what it must NOT touch
    # ==================================================================
    def test_ga2_t11_invalid_grant_moves_reporting_only(self):
        fake = self._fake_google()
        # A real Google-attributed website enquiry first, so the website
        # capability reads "Receiving" and can be seen NOT to move.
        self.Service.sudo().process_submission(self._google_payload(index=0))
        account = self.account_a1
        account.invalidate_recordset()
        self.assertEqual(account.website_status, 'receiving')
        website_before = account.website_status
        leads_before = account.website_lead_count

        self._grant(account, expires_in=-120, state='connected')
        fake.token_queue = [gads._error_from_response(FakeResponse(
            400, {'error': 'invalid_grant',
                  'error_description': 'Token has been expired or revoked.'}))]

        result = account.action_list_reporting_accounts()
        account.invalidate_recordset()

        self.assertEqual(account.reporting_state, 'action_required')
        self.assertEqual(account.last_error_code, 'invalid_grant')
        self.assertIn('Reconnect', account.reporting_error_redacted or '')
        self.assertEqual(account.customer_id, CUSTOMER_A1,
                         'the advertising account number is not a credential')
        # Rail R6 — the website half is untouched.
        self.assertEqual(account.website_status, website_before)
        self.assertEqual(account.website_lead_count, leads_before)
        # A sticky warning, not an exception: a UserError would roll the
        # action_required write back with itself (ledger §5.65).
        self.assertEqual(result['tag'], 'display_notification')
        self.assertEqual(result['params']['type'], 'warning')

    # ==================================================================
    # GA2-T12 — the advisory lock, against a REAL second connection
    # ==================================================================
    def test_ga2_t12_a_second_worker_is_told_to_come_back(self):
        fake = self._fake_google()
        account = self._grant(self.account_a1, expires_in=-120)
        # The record was created inside this transaction, so a second cursor
        # cannot SEE it (ledger §5.63) — and does not need to: an advisory key
        # is just an integer, which is exactly what makes this stageable.
        other = self.registry.cursor()
        try:
            other.execute('SELECT pg_try_advisory_xact_lock(%s, %s)',
                          (REPORTING_LOCK_CLASS, account.id))
            self.assertTrue(other.fetchone()[0],
                            'the second connection must actually hold it')

            raised = None
            started = fields.Datetime.now()
            try:
                account._reporting_access_token()
            except gads.GoogleAdsError as caught:
                raised = caught
            waited = (fields.Datetime.now() - started).total_seconds()
            self.assertIsNotNone(raised, 'a contended refresh must not hang')
            self.assertEqual(raised.code, 'busy')
            self.assertTrue(raised.retryable)
            self.assertLess(waited, 30, 'lock_timeout must bound the wait')
            self.assertFalse([c for c in fake.calls if c['kind'] == 'form'],
                             'the loser must not refresh behind the winner')
        finally:
            other.rollback()
            other.close()

        # With the lock gone, the same call goes through and refreshes once.
        fake.token_queue = [{'access_token': 'after-lock', 'expires_in': 900,
                             'scope': gads.SCOPE}]
        self.assertEqual(account._reporting_access_token(), 'after-lock')
        self.assertEqual(len([c for c in fake.calls if c['kind'] == 'form']), 1)

    # ==================================================================
    # GA2-T13 — paging, error mapping and redaction
    # ==================================================================
    def _client(self):
        account = self._grant(self.account_a1, expires_in=3600)
        return account._google_client()

    def test_ga2_t13a_every_page_is_followed(self):
        rows = [{'customer': {'id': CHILD_C1}}]
        fake = self._fake_google(search_pages=[
            {'results': rows, 'nextPageToken': 'p2'},
            {'results': rows, 'nextPageToken': 'p3'},
            {'results': rows},
        ])
        client = self._client()
        found = client._search(CUSTOMER_A1, gads.Q_CUSTOMER)
        self.assertEqual(len(found), 3, 'no silent first-page success')
        tokens = [c['body'].get('pageToken')
                  for c in fake.calls if c['kind'] == 'json']
        self.assertEqual(tokens, [None, 'p2', 'p3'])

    def test_ga2_t13b_an_endless_token_stops_at_the_cap(self):
        self._fake_google()
        client = self._client()

        def _endless(url, json_body=None, headers=None):
            return {'results': [], 'nextPageToken': 'always'}

        with patch.object(gads, '_http_post_json', _endless), \
                patch.object(gads, 'MAX_PAGES', 3):
            raised = None
            try:
                client._search(CUSTOMER_A1, gads.Q_CUSTOMER)
            except gads.GoogleAdsError as caught:
                raised = caught
        self.assertIsNotNone(raised)
        self.assertEqual(raised.code, 'too_many_pages')

    def test_ga2_t13c_transient_failures_are_marked_retryable(self):
        for status in (429, 503):
            error = gads._error_from_response(
                FakeResponse(status, {'error': {'code': status,
                                                'status': 'UNAVAILABLE'}}))
            self.assertTrue(error.retryable, 'HTTP %s is transient' % status)
            self.assertFalse(error.needs_reconnect)

        def _boom(*args, **kwargs):
            raise requests.ConnectionError('boom')

        with patch.object(gads.requests, 'get', _boom):
            raised = None
            try:
                gads._http_get('https://googleads.googleapis.com/x')
            except gads.GoogleAdsError as caught:
                raised = caught
        self.assertIsNotNone(raised)
        self.assertEqual(raised.code, 'network')
        self.assertTrue(raised.retryable)

    def test_ga2_t13d_a_401_forces_one_refresh_then_gives_up(self):
        fake = self._fake_google()
        client = self._client()
        unauthorized = gads._error_from_response(FakeResponse(401, {
            'error': {'code': 401, 'status': 'UNAUTHENTICATED', 'details': [
                {'errors': [{'errorCode': {
                    'authenticationError': 'OAUTH_TOKEN_INVALID'}}]}]}}))

        def _always_401(url, json_body=None, headers=None):
            fake.calls.append({'kind': 'json', 'url': url,
                               'body': dict(json_body or {}),
                               'headers': dict(headers or {})})
            raise unauthorized

        with patch.object(gads, '_http_post_json', _always_401):
            raised = None
            try:
                client._search(CUSTOMER_A1, gads.Q_CUSTOMER)
            except gads.GoogleAdsError as caught:
                raised = caught
        self.assertIsNotNone(raised)
        self.assertTrue(raised.needs_reconnect)
        self.assertEqual(len([c for c in fake.calls if c['kind'] == 'json']), 2,
                         'exactly one retry after one forced refresh')
        self.assertEqual(len([c for c in fake.calls if c['kind'] == 'form']), 1,
                         'and exactly one refresh')

    def test_ga2_t13e_an_echoed_token_never_survives_into_the_detail(self):
        leaked = 'ya29.SUPER-SECRET-ACCESS-TOKEN'
        body = {'error': {'code': 400, 'status': 'INVALID_ARGUMENT',
                          'message': 'Authorization: Bearer %s' % leaked,
                          'details': []}}
        text = ('{"error": {"message": "Authorization: Bearer %s", '
                '"access_token": "%s"}}' % (leaked, leaked))
        error = gads._error_from_response(FakeResponse(400, body, text=text))
        detail = error.detail_redacted or ''
        self.assertNotIn(leaked, detail,
                         'a provider body that echoes the request must not '
                         'carry the bearer token into a stored field')
        self.assertNotIn('Bearer ya29', detail)
        self.assertIn('redacted', detail)

    def test_ga2_t13f_the_reporting_surface_is_read_only(self):
        self._fake_google()
        client = self._client()
        # GA3 implemented both reads. What GA2 asserted through
        # `NotImplementedError` — that no caller can put a query on the wire —
        # is asserted here directly, because that is the property that matters
        # and it has to keep holding now the methods do something.
        self.assertEqual(client.list_campaigns(CUSTOMER_A1), [])
        # Dates are `datetime.date` OBJECTS the client formats itself. A
        # caller STRING is refused outright, so there is no interpolation path
        # from an RPC into the query.
        for bad in (('2026-09-01', '2026-09-15'), (None, None)):
            raised = None
            try:
                client.fetch_campaign_days(CUSTOMER_A1, *bad)
            except gads.GoogleAdsError as caught:
                raised = caught
            self.assertIsNotNone(raised, 'a caller string reached the query')
            self.assertEqual(raised.code, 'bad_window')
        # Every query this module can run is a module-level constant, and not
        # one of them names a write.
        for name in dir(gads):
            if not name.startswith('Q_'):
                continue
            query = getattr(gads, name)
            self.assertTrue(query.upper().startswith('SELECT '), name)
            for verb in ('MUTATE', 'INSERT', 'UPDATE', 'DELETE', 'REMOVE'):
                self.assertNotIn(verb, query.upper(), '%s names %s' % (name,
                                                                       verb))
        # There is no path from a caller to a query string at all.
        self.assertFalse([name for name in dir(client)
                          if name in ('search', 'query', 'mutate', 'run_gaql')])

    def test_ga2_t13g_the_pinned_version_is_recorded_with_its_sunset(self):
        self.assertEqual(gads.API_VERSION, 'v25')
        self.assertEqual(gads.API_SUNSET, 'August 2027')
        self.assertTrue(gads.ADS_HOST.startswith('https://'))
        self.assertTrue(gads.TOKEN_URL.startswith('https://'))
        self.assertTrue(gads.AUTH_URL.startswith('https://'))
