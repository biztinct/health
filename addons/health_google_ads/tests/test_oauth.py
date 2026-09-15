# -*- coding: utf-8 -*-
"""GA2-T03 … T06, T14, T15 — the sign-in handshake end to end.

The callback route is PUBLIC. It trusts nothing but a state it can burn, and
every way of failing looks the same from outside: unknown, already used,
expired and wrong-provider all render the generic page, so the endpoint is not
an oracle for guessing a valid state.
"""
import hashlib
from datetime import timedelta
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from odoo.addons.health_care_command_channels.services import channel_crypto
from odoo.addons.health_google_ads.models.google_ads_oauth_session import _s256
from odoo.addons.health_google_ads.services import google_ads_client as gads

from .common import (
    CHILD_C1,
    FIXTURE_ACCESS,
    FIXTURE_CLIENT_ID,
    FIXTURE_CLIENT_SECRET,
    FIXTURE_REFRESH,
    FakeResponse,
    GoogleAdsGa2Case,
)


@tagged('post_install', '-at_install')
class TestGoogleAdsOauth(GoogleAdsGa2Case):

    def _callback(self, params):
        """Exactly what the public controller calls — through the dispatcher.

        Going in by `care.channel.oauth.session` rather than straight to our
        own model is deliberate: the ORM override IS the integration, and a
        test that skipped it would prove nothing about the route.
        """
        return self.env['care.channel.oauth.session'].sudo()._handle_callback(
            'google_ads', params)

    # ==================================================================
    # GA2-T03 — starting the handshake
    # ==================================================================
    def test_ga2_t03a_no_application_means_no_handshake(self):
        self.config.sudo().write({'active': False})
        before = self.draft.reporting_state
        raised = None
        try:
            self.draft.action_start_reporting_oauth()
        except UserError as caught:
            raised = caught
        self.assertIsNotNone(raised)
        self.assertIn('platform operator', str(raised))
        self.draft.invalidate_recordset()
        self.assertEqual(self.draft.reporting_state, before,
                         'a refused start must not move the state')
        self.assertFalse(self.env['google.ads.oauth.session'].sudo().search_count(
            [('account_id', '=', self.draft.id)]))

    def test_ga2_t03b_the_authorization_url_carries_what_google_needs(self):
        self._fake_google()
        action, query = self._start_oauth(self.draft)
        self.assertEqual(action['type'], 'ir.actions.act_url')
        self.assertTrue(action['url'].startswith(gads.AUTH_URL + '?'))
        self.assertEqual(query['client_id'], FIXTURE_CLIENT_ID)
        self.assertEqual(query['redirect_uri'], self.config.redirect_uri)
        self.assertEqual(query['response_type'], 'code')
        self.assertEqual(query['scope'], gads.SCOPE)
        self.assertIn('adwords', query['scope'])
        # Both are required or Google returns an hour of access and nothing
        # durable.
        self.assertEqual(query['access_type'], 'offline')
        self.assertEqual(query['prompt'], 'consent')
        self.assertEqual(query['code_challenge_method'], 'S256')
        self.assertTrue(query['code_challenge'])

        session = self.env['google.ads.oauth.session'].sudo().search(
            [('account_id', '=', self.draft.id)], limit=1)
        self.assertTrue(session)
        self.assertEqual(
            session.state_hash,
            hashlib.sha256(query['state'].encode('utf-8')).hexdigest(),
            'the state is stored HASHED — a database reader cannot replay it')
        self.assertNotEqual(session.state_hash, query['state'])
        self.assertTrue(session.pkce_verifier_enc.startswith(
            channel_crypto.TOKEN_PREFIX))
        self.draft.invalidate_recordset()
        self.assertEqual(self.draft.reporting_state, 'authorizing')

    def test_ga2_t03c_an_insecure_address_is_refused(self):
        def _insecure(configs):
            for config in configs:
                config.redirect_uri = 'http://example.invalid' \
                                      + gads.CALLBACK_PATH

        Config = type(self.env['google.ads.platform.config'])
        with patch.object(Config, '_compute_redirect_uri', _insecure):
            raised = None
            try:
                self.draft.action_start_reporting_oauth()
            except UserError as caught:
                raised = caught
        self.assertIsNotNone(raised)
        self.assertIn('https', str(raised))

    # ==================================================================
    # GA2-T04 — the callback trusts a burnt state and nothing else
    # ==================================================================
    def test_ga2_t04a_an_unknown_state_is_generic(self):
        result = self._callback({'state': 'not-a-state', 'code': 'x'})
        self.assertEqual(result['outcome'], 'generic')
        self.assertFalse(result['ok'])

    def test_ga2_t04b_a_state_is_single_use(self):
        fake = self._fake_google()
        _action, query = self._start_oauth(self.draft)
        first = self._callback({'state': query['state'], 'code': 'code-1'})
        self.assertEqual(first['outcome'], 'ok')
        second = self._callback({'state': query['state'], 'code': 'code-1'})
        self.assertEqual(second['outcome'], 'generic',
                         'a replayed state must be indistinguishable from an '
                         'unknown one')
        self.assertEqual(len([c for c in fake.calls if c['kind'] == 'form']), 1,
                         'the replay must not reach Google at all')

    def test_ga2_t04c_an_expired_state_is_generic_and_labelled(self):
        self._fake_google()
        _action, query = self._start_oauth(self.draft)
        session = self.env['google.ads.oauth.session'].sudo().search(
            [('account_id', '=', self.draft.id)], limit=1)
        session.write({'expires_at': fields.Datetime.now()
                       - timedelta(minutes=1)})
        result = self._callback({'state': query['state'], 'code': 'c'})
        self.assertEqual(result['outcome'], 'generic')
        session.invalidate_recordset()
        self.assertEqual(session.outcome, 'expired')
        self.assertTrue(session.used_at, 'an expired state is still burnt')

    def test_ga2_t04d_our_state_does_not_work_on_another_provider(self):
        self._fake_google()
        _action, query = self._start_oauth(self.draft)
        result = self.env['care.channel.oauth.session'].sudo()._handle_callback(
            'meta', {'state': query['state'], 'code': 'c'})
        self.assertEqual(result['outcome'], 'generic')
        session = self.env['google.ads.oauth.session'].sudo().search(
            [('account_id', '=', self.draft.id)], limit=1)
        self.assertEqual(session.outcome, 'pending')
        self.assertFalse(session.used_at, 'our session must be untouched')
        self.draft.invalidate_recordset()
        self.assertEqual(self.draft.reporting_state, 'authorizing')

    # ==================================================================
    # GA2-T05 — the person said no
    # ==================================================================
    def test_ga2_t05a_denied_returns_the_account_to_not_connected(self):
        self._fake_google()
        _action, query = self._start_oauth(self.draft)
        result = self._callback({'state': query['state'],
                                 'error': 'access_denied',
                                 'error_description': 'The user denied it'})
        self.assertEqual(result['outcome'], 'denied')
        self.draft.invalidate_recordset()
        self.assertEqual(self.draft.reporting_state, 'not_connected')

    def test_ga2_t05b_a_cancelled_reconnect_keeps_a_working_account(self):
        self._fake_google()
        account = self._grant(self.account_a1, state='connected')
        _action, query = self._start_oauth(account)
        account.invalidate_recordset()
        self.assertEqual(account.reporting_state, 'connected',
                         'starting a RECONNECT must not drop the state')
        self._callback({'state': query['state'], 'error': 'access_denied'})
        account.invalidate_recordset()
        self.assertEqual(account.reporting_state, 'connected',
                         'a cancelled reconnect must not disconnect a working '
                         'account')

    # ==================================================================
    # GA2-T06 — the exchange
    # ==================================================================
    def test_ga2_t06a_a_successful_exchange_stores_an_encrypted_grant(self):
        fake = self._fake_google()
        _action, query = self._start_oauth(self.draft)
        before = fields.Datetime.now()
        result = self._callback({'state': query['state'], 'code': 'auth-code'})
        self.assertEqual(result, {'outcome': 'ok', 'ok': True,
                                  'channel': 'google_ads'})

        account = self.draft.sudo()
        account.invalidate_recordset()
        self.assertTrue(account.access_token_enc.startswith(
            channel_crypto.TOKEN_PREFIX))
        self.assertTrue(account.refresh_token_enc.startswith(
            channel_crypto.TOKEN_PREFIX))
        self.assertEqual(
            channel_crypto.decrypt(self.env, account.access_token_enc),
            FIXTURE_ACCESS)
        self.assertEqual(account.reporting_state, 'select_account')
        self.assertEqual(account.authorized_by, self.env.user)
        self.assertTrue(account.authorized_at)
        # now + expires_in - 60, to the second.
        expected = before + timedelta(seconds=3600 - 60)
        self.assertLessEqual(
            abs((account.token_expires_at - expected).total_seconds()), 5)

        exchange = [c for c in fake.calls if c['kind'] == 'form'][-1]
        self.assertEqual(exchange['url'], gads.TOKEN_URL)
        self.assertEqual(exchange['data']['grant_type'], 'authorization_code')
        self.assertEqual(exchange['data']['code'], 'auth-code')
        self.assertEqual(exchange['data']['redirect_uri'],
                         self.config.redirect_uri)
        self.assertEqual(exchange['data']['client_secret'],
                         FIXTURE_CLIENT_SECRET)
        self.assertEqual(_s256(exchange['data']['code_verifier']),
                         query['code_challenge'],
                         'the verifier posted to Google must be the one the '
                         'challenge was minted from')

        # Nothing from the answer is stored anywhere readable.
        for value in (account.last_error_code, account.website_test_summary,
                      account.reporting_error_redacted, account.provider_name):
            self.assertNotIn(FIXTURE_ACCESS, value or '')
            self.assertNotIn(FIXTURE_REFRESH, value or '')

    def test_ga2_t06b_a_failed_exchange_stores_nothing(self):
        fake = self._fake_google()
        fake.token_queue = [gads._error_from_response(FakeResponse(
            400, {'error': 'invalid_request',
                  'error_description': 'bad code'}))]
        _action, query = self._start_oauth(self.draft)
        result = self._callback({'state': query['state'], 'code': 'bad'})
        self.assertEqual(result['outcome'], 'error')

        account = self.draft.sudo()
        account.invalidate_recordset()
        self.assertFalse(account.access_token_enc)
        self.assertFalse(account.refresh_token_enc)
        self.assertEqual(account.reporting_state, 'not_connected')
        self.assertEqual(account.last_error_code, 'oauth_exchange')
        self.assertTrue(account.reporting_error_redacted)

    def test_ga2_t06c_no_refresh_token_and_none_stored_is_refused(self):
        fake = self._fake_google()
        fake.token_queue = [{'access_token': FIXTURE_ACCESS,
                             'expires_in': 3600, 'scope': gads.SCOPE}]
        _action, query = self._start_oauth(self.draft)
        result = self._callback({'state': query['state'], 'code': 'c'})
        self.assertEqual(result['outcome'], 'error')
        account = self.draft.sudo()
        account.invalidate_recordset()
        self.assertEqual(account.last_error_code, 'no_refresh_token')
        self.assertIn('third-party access',
                      account.reporting_error_redacted or '')
        self.assertFalse(account.access_token_enc)

    def test_ga2_t06d_a_re_consent_keeps_the_refresh_token_we_hold(self):
        fake = self._fake_google()
        account = self._grant(self.account_a2, state='connected')
        held = account.sudo().refresh_token_enc
        fake.token_queue = [{'access_token': 'second-access',
                             'expires_in': 1800, 'scope': gads.SCOPE}]
        fake.customers = {account.customer_id: fake.customer(
            account.customer_id, name='A2 in Google')}
        _action, query = self._start_oauth(account)
        result = self._callback({'state': query['state'], 'code': 'c'})
        self.assertEqual(result['outcome'], 'ok')
        account.invalidate_recordset()
        self.assertEqual(account.sudo().refresh_token_enc, held,
                         'a response without a refresh token must keep ours')
        self.assertEqual(
            channel_crypto.decrypt(self.env, account.sudo().access_token_enc),
            'second-access')
        # customer_id already set ⇒ validated and straight to connected.
        self.assertEqual(account.reporting_state, 'connected')
        self.assertEqual(account.provider_name, 'A2 in Google')

    def test_ga2_t06e_a_grant_without_the_advertising_permission_is_refused(self):
        fake = self._fake_google()
        fake.token_queue = [{'access_token': FIXTURE_ACCESS,
                             'expires_in': 3600,
                             'refresh_token': FIXTURE_REFRESH,
                             'scope': 'https://www.googleapis.com/auth/'
                                      'userinfo.email'}]
        _action, query = self._start_oauth(self.draft)
        result = self._callback({'state': query['state'], 'code': 'c'})
        self.assertEqual(result['outcome'], 'error')
        account = self.draft.sudo()
        account.invalidate_recordset()
        self.assertEqual(account.last_error_code, 'scope_missing')
        self.assertFalse(account.refresh_token_enc)

    # ==================================================================
    # GA2-T14 — disconnect, and reconnect
    # ==================================================================
    def test_ga2_t14a_disconnect_drops_our_tokens_and_nothing_else(self):
        fake = self._fake_google()
        account = self._grant(self.account_a1, state='connected')
        account._internal().write({'provider_name': 'Viet UC HN',
                                   'account_timezone': 'Asia/Ho_Chi_Minh'})
        connector = account.website_connector_id
        calls_before = len(fake.calls)

        account.action_disconnect_reporting()
        account.invalidate_recordset()
        secure = account.sudo()
        self.assertFalse(secure.access_token_enc)
        self.assertFalse(secure.refresh_token_enc)
        self.assertFalse(secure.token_expires_at)
        self.assertFalse(secure.token_scope)
        self.assertEqual(account.reporting_state, 'not_connected')
        self.assertFalse(account.has_reporting_grant)
        # Everything that is not a credential survives.
        self.assertTrue(account.customer_id)
        self.assertEqual(account.provider_name, 'Viet UC HN')
        self.assertEqual(account.account_timezone, 'Asia/Ho_Chi_Minh')
        self.assertEqual(account.website_connector_id, connector)
        self.assertEqual(len(fake.calls), calls_before,
                         'disconnect must not call Google at all — a shared '
                         'grant may back the clinic mailbox too')

    def test_ga2_t14b_reconnect_restores_connected_without_a_second_choice(self):
        fake = self._fake_google()
        account = self._grant(self.account_a1, state='connected')
        account.action_disconnect_reporting()
        fake.customers = {account.customer_id: fake.customer(
            account.customer_id, name='Viet UC HN', currency='VND')}

        action = account.action_reconnect_reporting()
        account.invalidate_recordset()
        self.assertEqual(account.reporting_state, 'authorizing')

        # Replay the state the browser would have carried back.
        query = {k: v[0] for k, v in
                 parse_qs(urlparse(action['url']).query).items()}
        result = self._callback({'state': query['state'], 'code': 'c'})
        self.assertEqual(result['outcome'], 'ok')
        account.invalidate_recordset()
        self.assertEqual(account.reporting_state, 'connected')
        self.assertEqual(account.provider_name, 'Viet UC HN')

    # ==================================================================
    # GA2-T15 — who may press these buttons
    # ==================================================================
    def test_ga2_t15a_a_plain_crm_user_may_press_nothing(self):
        self._fake_google()
        account = self.Account.with_user(self.crm_user).browse(
            self.account_a1.id)
        for method, args in (
                ('action_start_reporting_oauth', ()),
                ('action_reconnect_reporting', ()),
                ('action_list_reporting_accounts', ()),
                ('action_select_reporting_account', (CHILD_C1,)),
                ('action_disconnect_reporting', ())):
            raised = None
            try:
                getattr(account, method)(*args)
            except (AccessError, UserError) as caught:
                raised = caught
            self.assertIsNotNone(
                raised, '%s must refuse a plain CRM user' % method)

    def test_ga2_t15b_another_company_operator_is_refused(self):
        self._fake_google()
        account = self.Account.with_user(self.operator2).browse(
            self.account_a1.id)
        raised = None
        try:
            account.action_start_reporting_oauth()
        except (AccessError, UserError) as caught:
            raised = caught
        self.assertIsNotNone(
            raised, "company 2's operator must not act on company 1's "
                    'advertising account')
