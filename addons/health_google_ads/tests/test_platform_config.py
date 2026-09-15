# -*- coding: utf-8 -*-
"""GA2-T01, T02, T16, T17 — the platform application, and what never leaks.

The platform plane is the one place on this system that holds a credential
serving EVERY clinic. These tests are about the three properties that make
that safe: only a platform administrator can read or write it, the stored
values are ciphertext rather than text, and nothing a clinic user can call
returns either of them.
"""
import json

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from odoo.addons.health_care_command_channels.services import channel_crypto
from odoo.addons.health_google_ads.services import google_ads_client as gads

from .common import (
    FIXTURE_CLIENT_ID,
    FIXTURE_CLIENT_SECRET,
    FIXTURE_DEV_TOKEN,
    GoogleAdsGa2Case,
)


@tagged('post_install', '-at_install')
class TestGoogleAdsPlatformConfig(GoogleAdsGa2Case):

    # ==================================================================
    # GA2-T01 — storage, hints, the ACL and the one-active rule
    # ==================================================================
    def test_ga2_t01a_secrets_are_stored_encrypted_with_a_hint(self):
        config = self.config.sudo()
        self.assertTrue(config.has_client_secret)
        self.assertTrue(config.has_developer_token)
        self.assertEqual(config.client_secret_hint,
                         '••••' + FIXTURE_CLIENT_SECRET[-4:])
        self.assertEqual(config.developer_token_hint,
                         '••••' + FIXTURE_DEV_TOKEN[-4:])

        # Ciphertext in the column, plaintext only through the underscore
        # accessors — which are not RPC-callable.
        self.assertTrue(config.client_secret_enc.startswith(
            channel_crypto.TOKEN_PREFIX))
        self.assertTrue(config.developer_token_enc.startswith(
            channel_crypto.TOKEN_PREFIX))
        self.assertNotIn(FIXTURE_CLIENT_SECRET, config.client_secret_enc)
        self.assertNotIn(FIXTURE_DEV_TOKEN, config.developer_token_enc)
        self.assertEqual(config._get_client_secret(), FIXTURE_CLIENT_SECRET)
        self.assertEqual(config._get_developer_token(), FIXTURE_DEV_TOKEN)
        self.assertTrue(config._ready())

    def test_ga2_t01b_a_short_secret_gets_no_tail(self):
        """'••••' plus the last four of a five-character value IS the value."""
        self.config.action_set_client_secret('abcde')
        self.assertEqual(self.config.sudo().client_secret_hint, '••••')
        # Put the fixture back for every later test in the class.
        self.config.action_set_client_secret(FIXTURE_CLIENT_SECRET)

    def test_ga2_t01c_a_clinic_operator_cannot_read_the_application(self):
        raised = None
        try:
            self.Config.with_user(self.operator).browse(
                self.config.id).read(['client_id'])
        except AccessError as caught:
            raised = caught
        self.assertIsNotNone(
            raised, 'a CRM manager must not be able to read the platform '
                    'application at all')

        raised = None
        try:
            self.Config.with_user(self.crm_user).search([])
        except AccessError as caught:
            raised = caught
        self.assertIsNotNone(raised)

    def test_ga2_t01d_the_setters_refuse_a_non_platform_caller(self):
        config = self.config.with_user(self.operator)
        for method, value in (('action_set_client_secret', 'x' * 20),
                              ('action_set_developer_token', 'y' * 20)):
            raised = None
            try:
                getattr(config, method)(value)
            except (AccessError, UserError) as caught:
                raised = caught
            self.assertIsNotNone(
                raised, '%s must refuse a clinic operator' % method)
        # And the stored values are untouched.
        self.assertEqual(self.config.sudo()._get_client_secret(),
                         FIXTURE_CLIENT_SECRET)

    def test_ga2_t01e_an_empty_value_is_refused(self):
        for method in ('action_set_client_secret', 'action_set_developer_token'):
            raised = None
            try:
                getattr(self.config, method)('   ')
            except UserError as caught:
                raised = caught
            self.assertIsNotNone(raised)

    def test_ga2_t01f_only_one_active_application(self):
        raised = None
        try:
            self.Config.create({'name': 'second', 'client_id': 'x'})
        except UserError as caught:
            raised = caught
        self.assertIsNotNone(
            raised, 'a second ACTIVE application must be refused with an '
                    'actionable message, not a database error')

        # Archived is fine, and un-archiving it is refused for the same reason.
        second = self.Config.create({'name': 'archived one', 'active': False})
        self.assertTrue(second)
        raised = None
        try:
            second.write({'active': True})
        except UserError as caught:
            raised = caught
        self.assertIsNotNone(raised)

    def test_ga2_t01g_ready_is_false_until_all_three_are_present(self):
        bare = self.Config.create({'name': 'bare', 'active': False})
        self.assertFalse(bare._ready())
        raised = None
        try:
            bare._get_client_secret()
        except UserError as caught:
            raised = caught
        self.assertIsNotNone(raised)
        self.assertIn('not configured', str(raised))

    # ==================================================================
    # GA2-T02 — no credential material reaches any tenant-visible payload
    # ==================================================================
    def test_ga2_t02_no_secret_reaches_the_card_or_the_account(self):
        self._grant(self.account_a1)
        needles = [FIXTURE_CLIENT_SECRET, FIXTURE_DEV_TOKEN,
                   channel_crypto.TOKEN_PREFIX, 'access_token',
                   'refresh_token', 'client_secret', 'developer-token']

        cards = self.Conn.with_user(self.operator).center_overview()
        dumped = json.dumps(cards, default=str)
        for needle in needles:
            self.assertNotIn(needle, dumped,
                             '%r must not reach the Center payload' % needle)

        account = self.Account.with_user(self.operator).browse(
            self.account_a1.id)
        readable = ['name', 'customer_id', 'login_customer_id',
                    'reporting_state', 'token_expires_at', 'token_scope',
                    'authorized_at', 'authorized_by', 'last_error_code',
                    'reporting_error_redacted', 'provider_name',
                    'account_timezone', 'website_test_summary',
                    'has_reporting_grant']
        dumped = json.dumps(account.read(readable), default=str)
        for needle in needles:
            self.assertNotIn(needle, dumped,
                             '%r must not reach an operator read' % needle)

        # The grant itself is readable as a yes/no, which is the point of it.
        self.assertTrue(account.has_reporting_grant)

    def test_ga2_t02b_the_token_columns_are_group_restricted(self):
        self._grant(self.account_a1)
        account = self.Account.with_user(self.operator).browse(
            self.account_a1.id)
        raised = None
        try:
            account.read(['access_token_enc'])
        except AccessError as caught:
            raised = caught
        self.assertIsNotNone(
            raised, 'access_token_enc must be unreadable without '
                    'base.group_system')
        # Even a system reader gets ciphertext, never the plaintext.
        blob = self.account_a1.sudo().access_token_enc
        self.assertTrue(blob.startswith(channel_crypto.TOKEN_PREFIX))

    # ==================================================================
    # GA2-T16 — the return address, and the purge cron
    # ==================================================================
    def test_ga2_t16a_redirect_uri_is_the_base_url_plus_the_callback(self):
        base = (self.env['ir.config_parameter'].sudo()
                .get_param('web.base.url') or '').rstrip('/')
        self.assertEqual(self.config.redirect_uri,
                         base + '/channel_hub/oauth/callback/google_ads')
        self.assertEqual(gads.CALLBACK_PATH,
                         '/channel_hub/oauth/callback/google_ads')

    def test_ga2_t16b_the_purge_cron_drops_only_stale_sessions(self):
        self._fake_google()
        self._start_oauth(self.draft)
        young = self.Session.sudo().search([('account_id', '=', self.draft.id)])
        self.assertEqual(len(young), 1)

        old = self.Session.sudo().create({
            'account_id': self.draft.id,
            'company_id': self.company.id,
            'user_id': self.env.uid,
            'state_hash': 'ga2-stale-hash',
            'expires_at': '2026-01-01 00:00:00',
        })
        # `create_date` is ORM-managed: raw SQL is the only way to backdate
        # it, with the flush/invalidate pair of ledger §5.9 around it.
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE google_ads_oauth_session SET create_date = "
            "(now() AT TIME ZONE 'utc') - interval '30 hours' WHERE id = %s",
            (old.id,))
        self.env.invalidate_all()

        purged = self.Session._cron_purge_oauth_sessions()
        self.assertGreaterEqual(purged, 1)
        self.assertFalse(old.exists(), 'a day-old session is residue')
        self.assertTrue(young.exists(), 'a live session must survive the purge')

    # ==================================================================
    # GA2-T17 — white label
    # ==================================================================
    def test_ga2_t17_no_product_name_of_ours_in_any_new_label(self):
        for model in ('google.ads.platform.config',
                      'google.ads.platform.secret.wizard',
                      'google.ads.oauth.session',
                      'google.ads.account.select',
                      'google.ads.account.select.line'):
            described = self.env[model].fields_get()
            for name, spec in described.items():
                blob = json.dumps(spec, default=str)
                self.assertNotIn(
                    'odoo', blob.lower(),
                    '%s.%s carries a forbidden brand name' % (model, name))
