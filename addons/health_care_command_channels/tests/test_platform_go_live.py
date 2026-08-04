# -*- coding: utf-8 -*-
"""T156–T169 — CC-G: truthful platform availability + the go-live console.

Two things are under test and they pull in opposite directions:

* the card gate must **tighten** — a half-filled platform-app row must not
  light a channel up (T156/T157), because the Connect it offers could only
  fail; and
* it must not tighten past the truth — a COMPLETE row still lights the card
  (T157/T158/T168), and channels that need no platform app at all are
  untouched (T160).

TransactionCase only (ledger §5.32) and no test here reaches a provider: the
Meta preflight's two Graph calls are patched with a PLAIN FUNCTION (§5.76 —
a second ``autospec`` patch stops binding ``self``), and the zalo/google/
microsoft path asserts the HTTP layer was never called at all.
"""
import json
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from odoo.addons.health_care_command_channels.controllers.meta import (
    MetaWebhookController,
)
from odoo.addons.health_care_command_channels.models.channel_platform_app import (
    PREFLIGHT_UNVERIFIABLE,
)
from odoo.addons.health_care_command_channels.services.adapters import (
    CAPABILITY_KEYS, CHANNEL_ADAPTERS, OPTIONAL_CAPABILITY_KEYS, EmailAdapter,
    get_adapter,
)

from .common import ChannelHubCase

HTTPS_BASE = 'https://care.example.test'

# None of these is a real credential.
META_ID = 'meta-app-cc-g'
META_SECRET = 'meta-secret-cc-g-fixture'
ZALO_ID = 'zalo-app-cc-g'
ZALO_SECRET = 'zalo-secret-cc-g-fixture'
GOOGLE_ID = 'google-client-cc-g.apps.googleusercontent.com'
GOOGLE_SECRET = 'google-secret-cc-g-fixture'
ES_ID = '900111222333444'
FLB_ID = '900444333222111'
APP_TOKEN = 'meta-app-access-token-fixture'
APP_NAME = 'Việt Úc Care (dev)'

GRAPH_TARGET = ('odoo.addons.health_care_command_channels.services.'
                'adapters.requests.get')


@tagged('post_install', '-at_install')
class TestPlatformGoLive(ChannelHubCase):

    def setUp(self):
        super().setUp()
        self.env['ir.config_parameter'].sudo().set_param('web.base.url',
                                                         HTTPS_BASE)
        # A live deployment may already carry an operator's own platform-app
        # rows, and `provider` is unique among the ACTIVE ones — every fixture
        # below would collide with them, and "no app exists yet" would read a
        # row it never made. Archived (never deleted) inside the test
        # transaction, exactly as common.py does for connections.
        self.App.sudo().with_context(active_test=False).search([]).write(
            {'active': False})

    # -- helpers -------------------------------------------------------
    def _cards(self, user=None):
        Conn = self.Conn.with_user(user) if user else self.Conn
        return {c['channel']: c for c in Conn.center_overview()}

    def _meta_app(self, complete=True, **extra):
        app = self.App.create({'provider': 'meta', 'client_id': META_ID})
        if complete:
            app.action_set_secret(META_SECRET)
            payload = {'verify_token': 'verify-cc-g', 'es_config_id': ES_ID,
                       'flb_config_id': FLB_ID}
            payload.update(extra)
            app.write({'extra_json': json.dumps(payload)})
        return app

    def _zalo_app(self):
        app = self.App.create({'provider': 'zalo', 'client_id': ZALO_ID})
        app.action_set_secret(ZALO_SECRET)
        return app

    def _google_app(self):
        app = self.App.create({'provider': 'google', 'client_id': GOOGLE_ID})
        app.action_set_secret(GOOGLE_SECRET)
        return app

    @contextmanager
    def _mock_graph(self, replies):
        """Patch the ONE place adapters do HTTP with a URL-aware fake.

        ``replies`` is [(url_fragment, status, body)], matched in order. Any
        call that matches nothing is an assertion failure, not a silent empty
        reply — a preflight that quietly hit an unexpected endpoint would look
        like a pass.
        """
        calls = []

        def fake_get(url, params=None, headers=None, timeout=None):
            calls.append({'url': url, 'params': dict(params or {}),
                          'headers': dict(headers or {}), 'timeout': timeout})
            for fragment, status, body in replies:
                if fragment in url:
                    reply = MagicMock()
                    reply.status_code = status
                    reply.json.return_value = body
                    reply.text = json.dumps(body)
                    return reply
            raise AssertionError('unexpected provider call: %s' % url)

        with patch(GRAPH_TARGET, fake_get):
            yield calls

    # ==================================================================
    # T156 — an EMPTY platform-app row lights nothing up
    # ==================================================================
    def test_156_empty_row_is_not_availability(self):
        app = self.App.create({'provider': 'meta'})
        self.assertTrue(app.active)

        cards = self._cards()
        for channel in ('whatsapp', 'fb'):
            self.assertFalse(
                cards[channel]['available'],
                '%s must stay dark against a row the operator has only just '
                'created — Connect could only fail' % channel)
            self.assertEqual(cards[channel]['primary_action'], 'unavailable')
            self.assertEqual(cards[channel]['primary_label'],
                             'Not available yet')
            # Implemented is a claim about the SOFTWARE and does not move.
            self.assertTrue(cards[channel]['implemented'], channel)

        with self.assertRaisesRegex(UserError, 'not available yet'):
            self.Conn.center_begin('whatsapp')
        # ...and the refusal left nothing behind.
        self.assertFalse(self.Conn.with_context(active_test=False).search_count(
            [('channel', '=', 'whatsapp'),
             ('company_id', '=', self.company.id)]))

    # ==================================================================
    # T157 — completeness is per requirement, and per channel
    # ==================================================================
    def test_157_requirements_light_up_one_at_a_time(self):
        app = self.App.create({'provider': 'meta', 'client_id': META_ID})
        app.action_set_secret(META_SECRET)
        app.write({'extra_json': json.dumps({'verify_token': 'verify-cc-g'})})

        cards = self._cards()
        self.assertFalse(cards['whatsapp']['available'],
                         'no es_config_id ⇒ Embedded Signup cannot start')
        self.assertFalse(cards['fb']['available'])

        app.write({'extra_json': json.dumps({'verify_token': 'verify-cc-g',
                                             'es_config_id': ES_ID})})
        cards = self._cards()
        self.assertTrue(cards['whatsapp']['available'])
        self.assertFalse(cards['fb']['available'],
                         'Messenger needs its OWN configuration id — one app '
                         'row, two products, two prerequisites')

        app.write({'extra_json': json.dumps({'verify_token': 'verify-cc-g',
                                             'es_config_id': ES_ID,
                                             'flb_config_id': FLB_ID})})
        cards = self._cards()
        self.assertTrue(cards['whatsapp']['available'])
        self.assertTrue(cards['fb']['available'])

        # The verify token is a prerequisite too: without it Meta's handshake
        # 403s and webhook_verified can never pass.
        app.write({'extra_json': json.dumps({'es_config_id': ES_ID,
                                             'flb_config_id': FLB_ID})})
        cards = self._cards()
        self.assertFalse(cards['whatsapp']['available'])
        self.assertFalse(cards['fb']['available'])

    # ==================================================================
    # T158 — zalo needs no extra key, and zns still mirrors it
    # ==================================================================
    def test_158_zalo_complete_row_is_available(self):
        self._zalo_app()
        cards = self._cards()
        self.assertTrue(cards['zalo']['available'],
                        'client id + secret is the whole Zalo prerequisite')
        self.assertEqual(cards['zalo']['primary_action'], 'connect')

        # ZNS is a capability OF the Zalo connection: same availability, but
        # it is not a sign-in of its own.
        self.assertTrue(cards['zns']['available'])
        self.assertEqual(cards['zns']['parent_channel'], 'zalo')
        with self.assertRaisesRegex(UserError, 'part of the'):
            self.Conn.center_begin('zns')

        # Archiving the row is still the instant feature flag it always was.
        self.App._get_for_provider('zalo').write({'active': False})
        dark = self._cards()
        self.assertFalse(dark['zalo']['available'])
        self.assertFalse(dark['zns']['available'])

    # ==================================================================
    # T159 — email availability IS available_providers()
    # ==================================================================
    def test_159_email_matches_the_adapter(self):
        adapter = get_adapter(self.env, 'email')
        self.assertIsInstance(adapter, EmailAdapter)

        self.assertFalse(adapter.available_providers())
        self.assertFalse(self._cards()['email']['available'])

        self._google_app()
        # The addon-presence half is environment truth, not a fixture: assert
        # the CARD equals the ADAPTER, whichever way that comes out here.
        expected = bool(adapter.available_providers())
        self.assertEqual(self._cards()['email']['available'], expected)
        self.assertEqual(adapter.platform_ready(), expected)
        if expected:
            self.assertIn('google', adapter.available_providers())

    # ==================================================================
    # T160 — channels that need no platform app are untouched
    # ==================================================================
    def test_160_non_platform_channels_unaffected(self):
        self.assertFalse(
            self.App.sudo().search_count([('active', '=', True)]),
            'fixture guard: this test is the zero-platform-app state')
        cards = self._cards()
        for channel in ('telegram', 'webchat', 'call'):
            adapter = get_adapter(self.env, channel)
            self.assertFalse(
                adapter.authorization_capabilities()['needs_platform_app'],
                channel)
            self.assertTrue(adapter.platform_ready(), channel)
            self.assertTrue(cards[channel]['available'], channel)
            self.assertTrue(cards[channel]['implemented'], channel)

    # ==================================================================
    # T161 — no credential material anywhere in the new surfaces
    # ==================================================================
    def test_161_no_secret_in_the_console(self):
        app = self._meta_app()
        with self._mock_graph([('oauth/access_token', 200,
                                {'access_token': APP_TOKEN}),
                               (META_ID, 200, {'name': APP_NAME})]):
            app.action_preflight()

        blob = json.dumps(self.Conn.center_overview(), default=str)
        blob += json.dumps(app.read([
            'go_live_checklist', 'webhook_urls', 'oauth_redirect_uri',
            'preflight_status', 'preflight_detail', 'secret_hint',
        ]), default=str)
        blob += json.dumps(self.Audit.sudo().search_read(
            [('event', 'in', ('preflight', 'verify_token_generated'))],
            ['detail_redacted']), default=str)

        for forbidden in (META_SECRET, app.sudo().client_secret_enc, 'chs$1$',
                          APP_TOKEN):
            self.assertNotIn(forbidden, blob,
                             'no credential material may reach an operator '
                             'screen, a stored detail or an audit row')
        # The checklist is still doing its job: it names the app id, which is
        # public, and reports the row as complete.
        self.assertIn('Done', app.go_live_checklist)
        self.assertNotIn('To do', app.go_live_checklist)

    # ==================================================================
    # T162 — the verify-token generator merges, never clobbers
    # ==================================================================
    def test_162_verify_token_generator(self):
        app = self.App.create({
            'provider': 'meta', 'client_id': META_ID,
            'extra_json': json.dumps({'es_config_id': ES_ID,
                                      'flb_config_id': FLB_ID})})
        before = self.Audit.sudo().search_count(
            [('event', '=', 'verify_token_generated')])

        app.action_generate_verify_token()
        extra = json.loads(app.extra_json)
        token = extra.get('verify_token')
        self.assertTrue(token and len(token) >= 24,
                        'the token must be generated, not invented by a human')
        self.assertEqual(extra.get('es_config_id'), ES_ID,
                         'a sibling key must survive the merge')
        self.assertEqual(extra.get('flb_config_id'), FLB_ID)
        self.assertEqual(
            self.Audit.sudo().search_count(
                [('event', '=', 'verify_token_generated')]), before + 1)

        # Regenerating silently would break the handshake: Meta's dashboard
        # still holds the old value.
        raised = False
        try:
            app.action_generate_verify_token()
        except UserError:
            raised = True
        self.assertTrue(raised)
        self.assertEqual(json.loads(app.extra_json).get('verify_token'), token,
                         'the refused call must leave the token untouched')

        # Not a Meta row ⇒ not a Meta concept.
        zalo = self._zalo_app()
        with self.assertRaises(UserError):
            zalo.action_generate_verify_token()

    # ==================================================================
    # T163 — Meta preflight, the pass path
    # ==================================================================
    def test_163_meta_preflight_pass(self):
        app = self._meta_app()
        self.assertEqual(app.preflight_status, 'none')

        with self._mock_graph([('oauth/access_token', 200,
                                {'access_token': APP_TOKEN}),
                               (META_ID, 200, {'name': APP_NAME,
                                               'id': META_ID})]) as calls:
            result = app.action_preflight()

        self.assertEqual(app.preflight_status, 'pass')
        self.assertEqual(app.preflight_detail, APP_NAME,
                         'seeing their own app name back is what proves the '
                         'operator pasted the right app\'s secret')
        self.assertTrue(app.preflight_at)
        self.assertEqual(result.get('tag'), 'display_notification')

        # Two calls, in order, and the app token never touched a URL.
        self.assertEqual(len(calls), 2)
        self.assertIn('oauth/access_token', calls[0]['url'])
        self.assertEqual(calls[0]['params'].get('grant_type'),
                         'client_credentials')
        self.assertEqual(calls[0]['params'].get('client_secret'), META_SECRET,
                         'the check must really send the pasted secret')
        self.assertTrue(calls[0]['timeout'], 'every provider call is bounded')
        self.assertIn(META_ID, calls[1]['url'])
        self.assertEqual(calls[1]['headers'].get('Authorization'),
                         'Bearer %s' % APP_TOKEN)
        self.assertNotIn(APP_TOKEN, calls[1]['url'])

        audit = self.Audit.sudo().search([('event', '=', 'preflight')], limit=1)
        self.assertTrue(audit)
        self.assertIn('pass', audit.detail_redacted)
        for forbidden in (META_SECRET, APP_TOKEN):
            self.assertNotIn(forbidden, audit.detail_redacted or '')
            self.assertNotIn(forbidden, app.preflight_detail or '')

    # ==================================================================
    # T164 — Meta preflight, the refusal path: persist, never raise
    # ==================================================================
    def test_164_meta_preflight_failure_is_persisted(self):
        app = self._meta_app()
        refusal = {'error': {'message': 'Invalid OAuth access token',
                             'type': 'OAuthException', 'code': 101,
                             'fbtrace_id': 'AbC123'}}
        with self._mock_graph([('oauth/access_token', 400, refusal)]):
            result = app.action_preflight()

        # The button answers; it does not blow up in the operator's face.
        self.assertEqual(result.get('tag'), 'display_notification')

        app.invalidate_recordset()
        self.assertEqual(app.preflight_status, 'fail',
                         'the evidence of the failure must survive the call')
        self.assertTrue(app.preflight_at)
        self.assertTrue(app.preflight_detail, 'a fail with no reason is not '
                                              'evidence, it is a shrug')
        self.assertNotIn(META_SECRET, app.preflight_detail)
        audit = self.Audit.sudo().search([('event', '=', 'preflight')], limit=1)
        self.assertIn('fail', audit.detail_redacted)

        # A row with no secret fails honestly rather than calling anyone.
        naked = self.App.create({'provider': 'meta', 'client_id': 'x',
                                 'active': False})
        with self._mock_graph([]) as calls:
            naked.action_preflight()
        self.assertEqual(naked.preflight_status, 'fail')
        self.assertFalse(calls)

    # ==================================================================
    # T165 — the three providers with no honest check say so
    # ==================================================================
    def test_165_unverifiable_providers_call_nobody(self):
        apps = [self._zalo_app(), self._google_app(),
                self.App.create({'provider': 'microsoft',
                                 'client_id': 'ms-app-cc-g'})]
        # The audit count below has to be scoped to THIS test's own rows.
        # `care.channel.audit` is append-only operational evidence that
        # accumulates on a real database, so an unscoped `search_count` was
        # asserting against however many times an operator had ever pressed
        # Preflight — on vietuat it counted 9 and had been failing since the
        # first real use of the CC-G console.
        before = self.Audit.sudo().search_count([('event', '=', 'preflight')])
        with self._mock_graph([]) as calls:
            for app in apps:
                app.action_preflight()
        self.assertFalse(calls, 'no undocumented provider probing (§13)')
        for app in apps:
            self.assertEqual(app.preflight_status, 'unverifiable', app.provider)
            self.assertEqual(app.preflight_detail, PREFLIGHT_UNVERIFIABLE)
            self.assertTrue(app.preflight_at)
        self.assertEqual(
            self.Audit.sudo().search_count([('event', '=', 'preflight')]),
            before + 3,
            'every preflight is audited, including the ones that ask nobody')

    # ==================================================================
    # T166 — the computed URLs are the routes we actually serve
    # ==================================================================
    def test_166_computed_urls(self):
        meta = self._meta_app()
        self.assertEqual(meta.oauth_redirect_uri,
                         '%s/channel_hub/oauth/callback/meta' % HTTPS_BASE)

        # Built from the controller's OWN route rule, so a renamed route
        # cannot leave this tab printing a URL nobody answers.
        rule = MetaWebhookController.meta_webhook.original_routing['routes'][0]
        for channel in ('whatsapp', 'fb'):
            expected = HTTPS_BASE + rule.replace('<string:channel>', channel)
            self.assertIn(expected, meta.webhook_urls, channel)

        zalo = self._zalo_app()
        self.assertEqual(zalo.oauth_redirect_uri,
                         '%s/channel_hub/oauth/callback/zalo' % HTTPS_BASE)
        self.assertIn('%s/care_channels/zalo/webhook' % HTTPS_BASE,
                      zalo.webhook_urls)

        # Google/Microsoft sign in through Odoo's own mixins, which own their
        # redirect URIs — ours would be refused by the provider (deviation D1).
        google = self._google_app()
        self.assertEqual(google.oauth_redirect_uri,
                         '%s/google_gmail/confirm' % HTTPS_BASE)
        self.assertIn('IMAP', google.webhook_urls,
                      'no webhook exists for mail; say so instead of showing '
                      'an empty box')

        # The checklist names what is still missing, per provider.
        empty = self.App.create({'provider': 'microsoft'})
        self.assertIn('To do', empty.go_live_checklist)
        self.assertIn('entra.microsoft.com', empty.go_live_checklist)

    # ==================================================================
    # T167 — the platform plane stays with the platform operator
    # ==================================================================
    def test_167_non_system_user_is_refused(self):
        # Deliberately a row on which BOTH buttons would otherwise WORK: a
        # meta app with credentials and no verify token yet. A refusal that
        # would have happened anyway proves nothing about the gate.
        app = self.App.create({
            'provider': 'meta', 'client_id': META_ID,
            'extra_json': json.dumps({'es_config_id': ES_ID})})
        app.action_set_secret(META_SECRET)
        as_mgr = app.with_user(self.crm_mgr)

        with self.assertRaises(AccessError):
            as_mgr.read(['client_id'])

        # RPC-by-name reaches the method, not the view: both buttons carry
        # their own gate. Either exception class is a refusal (ledger §5.70) —
        # the model gate fires before the ACL (§5.39).
        with self._mock_graph([]) as calls:
            for name in ('action_preflight', 'action_generate_verify_token'):
                raised = False
                try:
                    getattr(as_mgr, name)()
                except (UserError, AccessError):
                    raised = True
                self.assertTrue(raised, '%s must refuse a non-operator' % name)
        self.assertFalse(calls, 'a refused button must reach no provider')

        # Neither button did anything on the way through.
        app.invalidate_recordset()
        self.assertEqual(app.preflight_status, 'none')
        self.assertFalse(app.preflight_at)
        self.assertNotIn('verify_token', json.loads(app.extra_json or '{}'))

    # ==================================================================
    # T168 — the gate's sudo reads survive a real tenant persona
    # ==================================================================
    def test_168_tenant_persona_reads_the_catalogue(self):
        self._zalo_app()
        cards = self._cards(user=self.crm_mgr)
        self.assertTrue(cards['zalo']['available'],
                        'the gate reads the platform plane under sudo(); a '
                        'Care Command manager must never see an AccessError')
        self.assertEqual(cards['zalo']['primary_action'], 'connect')
        self.assertEqual(len(cards), 8)

        # ...and the platform plane is still invisible to them.
        with self.assertRaises(AccessError):
            self.App.with_user(self.crm_mgr).search([])

    # ==================================================================
    # T169 — the capability contract is a contract, not a comment
    # ==================================================================
    def test_169_capability_keys_are_declared(self):
        """OPTIONAL_CAPABILITY_KEYS was enforced by nothing until now.

        ``CAPABILITY_KEYS`` has T81 behind it; the optional list was a
        docstring in constant form, so a typo'd ``required_platform_key``
        would have silently declared no requirement at all — the exact
        failure this phase exists to remove.
        """
        allowed = set(CAPABILITY_KEYS) | set(OPTIONAL_CAPABILITY_KEYS)
        for channel, cls in sorted(CHANNEL_ADAPTERS.items()):
            caps = cls(self.env, channel).authorization_capabilities()
            self.assertFalse(set(caps) - allowed,
                             '%s declares unknown capability keys' % channel)
            for key in caps.get('required_platform_keys') or ():
                self.assertTrue(
                    caps.get('needs_platform_app'),
                    '%s requires a platform key but claims to need no '
                    'platform app' % channel)
                self.assertTrue(isinstance(key, str) and key)
