# -*- coding: utf-8 -*-
"""T127–T140 — Meta (WhatsApp + Messenger) on the connection framework (CC-E).

TransactionCase ONLY, like every other suite in this module (ledger §5.32),
and **every** provider call is mocked: nothing here can reach
graph.facebook.com or connect.facebook.net, and no credential in it is real.

Meta cannot be proven live on this deployment — a Business-type app, Business
Verification and App Review of five permissions are multi-week human processes
that have not started, and there are zero ``channel.platform.app`` rows on
vietuat. So the fixtures below seed a platform app INSIDE the test transaction
(it rolls back with the class) and the suite proves the software against the
provider contract, not against Meta. T137 asserts the honest dark state that
the real server is in.

Three test-writing rules earn their keep repeatedly below:

* a failure path that must leave NOTHING behind is asserted with
  ``try/except``, never ``assertRaises`` — Odoo wraps the latter in a savepoint
  and rolls back every write made before the raise, which would make a leaky
  implementation look clean (ledger §5.8/§5.65). ``assertRaises`` also cannot
  take a TUPLE of exception classes here (§5.70);
* readiness is never asserted into place. Fixtures reach their state by proving
  checks, which is the behaviour under test;
* nothing asserts on the TEXT of a source file to prove a behaviour (§5.72):
  every claim below is exercised.
"""
import json
from datetime import timedelta
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from odoo.addons.health_care_command_channels.services.adapters import (
    FB_MESSAGE_TAGS, BaseChannelAdapter, ChannelSendError, meta_window_state,
)

from .common_spine import (
    FB_PAGE_ID, META_APP_SECRET, WA_PHONE_ID, WA_WABA_ID, ChannelSpineCase,
)

HTTPS_BASE = 'https://care.example.test'

# Fixtures. None of these is a real Meta credential.
ES_CONFIG_ID = '111222333444555'
FLB_CONFIG_ID = '555444333222111'
WA_USER_TOKEN = 'meta-bisu-token-fixture'
FB_USER_TOKEN = 'meta-user-token-fixture'
FB_PAGE_TOKEN = 'meta-page-token-fixture'

WA_SCOPES = ['whatsapp_business_management', 'whatsapp_business_messaging',
             'business_management']
FB_SCOPES = ['pages_show_list', 'pages_messaging', 'pages_manage_metadata']

PHONE_ROW = {
    'id': WA_PHONE_ID,
    'display_phone_number': '+84 24 7100 0000',
    'verified_name': 'Phòng khám Việt Úc',
    'quality_rating': 'GREEN',
    'name_status': 'APPROVED',
    'code_verification_status': 'VERIFIED',
}


def _debug_token(scopes, wabas=()):
    return {'data': {
        'is_valid': True,
        'app_id': 'meta-app-1',
        'scopes': list(scopes),
        'granular_scopes': [
            {'scope': 'whatsapp_business_management',
             'target_ids': list(wabas)},
        ] if wabas else [],
    }}


@tagged('post_install', '-at_install')
class TestMetaCenter(ChannelSpineCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # The shared fixture already seeded a `meta` platform app with the
        # webhook verify token; CC-E adds the two configuration ids the
        # platform operator pastes in (operator checklist §12.3).
        extra = json.loads(cls.meta_app.extra_json or '{}')
        extra.update({'es_config_id': ES_CONFIG_ID,
                      'flb_config_id': FLB_CONFIG_ID})
        cls.meta_app.write({'extra_json': json.dumps(extra)})

    def setUp(self):
        super().setUp()
        self._set_base_url(HTTPS_BASE)

    # -- helpers -------------------------------------------------------
    def _set_base_url(self, value):
        self.env['ir.config_parameter'].sudo().set_param('web.base.url', value)

    def _center_connection(self, channel):
        conn = self.Conn.sudo().search([
            ('channel', '=', channel),
            ('company_id', '=', self.company.id)], limit=1)
        return conn

    def _mock_graph(self, get_map=None, post_map=None):
        """Patch the adapters' HTTP helpers with URL-aware fakes.

        The Meta flows chain several DIFFERENT Graph calls in one method, so a
        single canned reply (the CC-D idiom) cannot express them. Matching on a
        substring of the URL keeps every call inside the box while still
        letting a test say what each endpoint answered.

        Patched with PLAIN FUNCTIONS, deliberately not ``autospec=True``: a
        Meta flow is several stages long, so a test re-arms the mock between
        stages — and a second ``autospec`` patch builds its spec from the FIRST
        patch's mock, which quietly stops binding ``self`` and makes every
        later call return an empty reply. (Cost four red tests on the first
        run: a listing that was mocked with two rows came back with none.)
        A function assigned to the class is an ordinary descriptor and stacks
        correctly however many times it is applied.
        """
        get_map = get_map or {}
        post_map = post_map or {}
        calls = {'get': [], 'post': []}

        def _pick(mapping, url):
            for fragment, reply in mapping.items():
                if fragment in url:
                    return reply
            raise AssertionError('unmocked Graph call: %s' % url)

        def _fake_get(inner, url, params=None, headers=None):
            calls['get'].append((url, params or {}, headers or {}))
            reply = _pick(get_map, url)
            if isinstance(reply, Exception):
                raise reply
            return reply

        def _fake_post(inner, url, json_body=None, params=None, headers=None):
            calls['post'].append((url, json_body or {}, params or {},
                                  headers or {}))
            reply = _pick(post_map, url)
            if isinstance(reply, Exception):
                raise reply
            return reply

        for name, func in (('_get', _fake_get), ('_post', _fake_post)):
            p = patch.object(BaseChannelAdapter, name, func)
            p.start()
            self.addCleanup(p.stop)
        return calls

    def _authorize_wa(self, conn, scopes=None, wabas=(WA_WABA_ID,),
                      hint=None):
        """Drive a WhatsApp connection through Embedded Signup."""
        payload = self.Conn.center_meta_start('whatsapp')
        self._mock_graph(get_map={
            'oauth/access_token': {'access_token': WA_USER_TOKEN},
            'debug_token': _debug_token(scopes or WA_SCOPES, wabas),
        })
        return self.Conn.center_meta_exchange(
            conn.id, 'es-code-fixture', payload['state_token'], hint)

    def _authorize_fb(self, conn, scopes=None):
        payload = self.Conn.center_meta_start('fb')
        state = parse_qs(urlparse(payload['url']).query)['state'][0]
        self._mock_graph(get_map={
            'oauth/access_token': {'access_token': FB_USER_TOKEN},
            'debug_token': _debug_token(scopes or FB_SCOPES),
        })
        return self.env['care.channel.oauth.session']._handle_callback(
            'meta', {'state': state, 'code': 'flb-code-fixture'})

    # ==================================================================
    # T127 — the sign-in payload: app id + config id, NO secret, state once
    # ==================================================================
    def test_127_meta_start_payload(self):
        self.Conn.center_begin('whatsapp')
        conn = self._center_connection('whatsapp')
        payload = self.Conn.center_meta_start('whatsapp')

        self.assertEqual(payload['mode'], 'embedded_signup')
        self.assertEqual(payload['app_id'], 'meta-app-1')
        self.assertEqual(payload['config_id'], ES_CONFIG_ID)
        self.assertTrue(payload['state_token'])
        self.assertEqual(payload['sdk_url'],
                         'https://connect.facebook.net/en_US/sdk.js')

        # The app secret is server-only: it exists in the token exchange and
        # in the debug_token app-token, and in nothing the browser is handed.
        blob = json.dumps(payload, default=str)
        self.assertNotIn(META_APP_SECRET, blob)
        self.assertNotIn('client_secret', blob)
        self.assertNotIn('chs$1$', blob)

        # Messenger gets a real Facebook Login for Business dialog URL —
        # config_id, no scope list, and again no secret.
        self.Conn.center_begin('fb')
        fb_payload = self.Conn.center_meta_start('fb')
        parsed = urlparse(fb_payload['url'])
        query = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        self.assertEqual(parsed.netloc, 'www.facebook.com')
        self.assertEqual(parsed.path, '/v21.0/dialog/oauth')
        self.assertEqual(query['client_id'], 'meta-app-1')
        self.assertEqual(query['config_id'], FLB_CONFIG_ID)
        self.assertEqual(query['response_type'], 'code')
        self.assertEqual(query['redirect_uri'],
                         '%s/channel_hub/oauth/callback/meta' % HTTPS_BASE)
        self.assertNotIn(META_APP_SECRET, fb_payload['url'])
        self.assertNotIn('client_secret', fb_payload['url'])

        # The state is SINGLE USE: burning it once is all anyone gets.
        Session = self.env['care.channel.oauth.session']
        self.assertTrue(Session._consume(payload['state_token']))
        self.assertIsNone(Session._consume(payload['state_token']))

        # A platform app with no configuration id cannot start a sign-in —
        # inventing one would be a manufactured credential.
        self.meta_app.write({'extra_json': json.dumps({})})
        with self.assertRaises(UserError):
            self.Conn.center_meta_start('whatsapp')
        conn.invalidate_recordset()
        self.assertFalse(conn.sudo().has_credentials)

    # ==================================================================
    # T128 — the code exchange happy path
    # ==================================================================
    def test_128_exchange_happy_path(self):
        self.Conn.center_begin('whatsapp')
        conn = self._center_connection('whatsapp')
        payload = self.Conn.center_meta_start('whatsapp')
        calls = self._mock_graph(get_map={
            'oauth/access_token': {'access_token': WA_USER_TOKEN},
            'debug_token': _debug_token(WA_SCOPES, (WA_WABA_ID,)),
        })
        result = self.Conn.center_meta_exchange(
            conn.id, 'es-code-fixture', payload['state_token'],
            {'waba_id': '77001', 'phone_number_id': '77002'})

        # The exchange carried the secret server-to-server, and NO redirect_uri
        # (the ES popup owns its own — sending one makes Meta refuse).
        exchange = [c for c in calls['get'] if 'oauth/access_token' in c[0]][0]
        self.assertEqual(exchange[1]['client_id'], 'meta-app-1')
        self.assertEqual(exchange[1]['client_secret'], META_APP_SECRET)
        self.assertEqual(exchange[1]['code'], 'es-code-fixture')
        self.assertNotIn('redirect_uri', exchange[1])

        # debug_token is what makes the scope claim honest, and it is called
        # with the APP token, never with the tenant's own.
        inspect = [c for c in calls['get'] if 'debug_token' in c[0]][0]
        self.assertEqual(inspect[1]['input_token'], WA_USER_TOKEN)
        self.assertEqual(inspect[1]['access_token'],
                         'meta-app-1|%s' % META_APP_SECRET)

        # The token is in the database as ciphertext and nowhere else.
        self.env.flush_all()
        self.env.cr.execute(
            'SELECT access_token_enc, granted_scopes FROM '
            'care_channel_connection WHERE id = %s', (conn.id,))
        access_enc, scopes = self.env.cr.fetchone()
        self.env.invalidate_all()
        self.assertTrue(access_enc.startswith('chs$1$'))
        self.assertNotIn(WA_USER_TOKEN, access_enc)
        self.assertEqual(conn.sudo()._get_secret('access_token'), WA_USER_TOKEN)
        self.assertIn('whatsapp_business_messaging', scopes)

        statuses = {c.check_key: c.status
                    for c in conn.sudo().readiness_check_ids}
        self.assertEqual(statuses.get('authorization_valid'), 'pass')
        self.assertEqual(statuses.get('scopes_granted'), 'pass')
        self.assertEqual(conn.state, 'select_resource')
        self.assertEqual(result['missing_scopes'], [])

        # The WABA came from BOTH the popup hint and debug_token's granular
        # scopes; the phone hint is stored as a hint, never as a selection.
        self.assertIn(WA_WABA_ID, conn.sudo().get_setting('meta_waba_ids'))
        self.assertIn('77001', conn.sudo().get_setting('meta_waba_ids'))
        self.assertEqual(conn.sudo().get_setting('meta_phone_hint'), '77002')
        self.assertFalse(conn.resource_external_id,
                         'a hint is not a selection')

        # NOTHING about the grant comes back to the browser.
        blob = json.dumps(result, default=str)
        self.assertNotIn(WA_USER_TOKEN, blob)
        self.assertNotIn(META_APP_SECRET, blob)
        self.assertNotIn(payload['state_token'], blob)

    # ==================================================================
    # T129 — an exchange Meta refuses stores NOTHING
    # ==================================================================
    def test_129_exchange_refusals(self):
        self.Conn.center_begin('whatsapp')
        conn = self._center_connection('whatsapp')

        # (a) Meta refuses the code. try/except, NOT assertRaises: the
        # savepoint would roll back exactly the writes this catches (§5.8).
        payload = self.Conn.center_meta_start('whatsapp')
        calls = self._mock_graph(get_map={
            'oauth/access_token': {'error': {'message': 'Invalid verification '
                                             'code format.', 'code': 100}},
            'debug_token': _debug_token(WA_SCOPES, (WA_WABA_ID,)),
        })
        raised = False
        try:
            self.Conn.center_meta_exchange(conn.id, 'bad-code',
                                           payload['state_token'])
        except UserError:
            raised = True
        self.assertTrue(raised)
        self.assertFalse([c for c in calls['get'] if 'debug_token' in c[0]],
                         'a refused exchange must not go on to inspect a '
                         'token it never got')
        conn.invalidate_recordset()
        self.assertFalse(conn.sudo().has_credentials)
        self.assertFalse(conn.resource_external_id)
        self.assertEqual(conn.state, 'authorizing')
        self.assertFalse(self.Check.sudo().search_count(
            [('connection_id', '=', conn.id)]))

        # (b) a replayed state is indistinguishable from an unknown one, and
        # neither reaches the network.
        for state in (payload['state_token'], 'never-issued'):
            raised = False
            try:
                self.Conn.center_meta_exchange(conn.id, 'code', state)
            except UserError:
                raised = True
            self.assertTrue(raised, state)

        # (c) an empty code never leaves the server at all.
        with self.assertRaises(UserError):
            self.Conn.center_meta_exchange(conn.id, '', 'whatever')

        # (d) Messenger has no paste-a-code door: its flow finishes on the
        # OAuth callback, and offering a second entry point would be a second
        # thing to get wrong.
        self.Conn.center_begin('fb')
        fb = self._center_connection('fb')
        with self.assertRaises(UserError):
            self.Conn.center_meta_exchange(fb.id, 'code', 'state')

        conn.invalidate_recordset()
        self.assertFalse(conn.sudo().has_credentials)

    # ==================================================================
    # T130 — a partial grant is a visible failure, never a half-connect
    # ==================================================================
    def test_130_partial_scopes(self):
        self.Conn.center_begin('whatsapp')
        conn = self._center_connection('whatsapp')
        result = self._authorize_wa(
            conn, scopes=['whatsapp_business_management'])

        self.assertEqual(result['missing_scopes'],
                         ['whatsapp_business_messaging'])
        conn.invalidate_recordset()
        statuses = {c.check_key: c.status
                    for c in conn.sudo().readiness_check_ids}
        self.assertEqual(statuses.get('authorization_valid'), 'pass',
                         'the grant itself is real — it is incomplete')
        self.assertEqual(statuses.get('scopes_granted'), 'fail')
        row = self.Check.sudo().search([
            ('connection_id', '=', conn.id),
            ('check_key', '=', 'scopes_granted')], limit=1)
        self.assertIn('whatsapp_business_messaging', row.detail_redacted,
                      'the tenant must be able to read what Meta withheld')

        # A failed required check keeps the connection out of ready from every
        # recompute state — even with everything else proven.
        conn.sudo()._transition('testing', reason='T130 fixture')
        for key in ('resource_selected', 'webhook_configured', 'outbound_ok',
                    'provider_approvals'):
            self.Check.upsert_check(conn.sudo(), key, 'pass')
        conn.invalidate_recordset()
        self.assertEqual(conn.state, 'action_required',
                         'a permission Meta withheld is a real failure, not a '
                         'check that merely has not happened yet')
        self.assertNotIn('whatsapp', self.Care._channel_keys(),
                         'a half-granted channel must not light the dock')

        # Messenger's own required set behaves identically.
        self.Conn.center_begin('fb')
        fb = self._center_connection('fb')
        self._authorize_fb(fb, scopes=['pages_show_list'])
        fb.invalidate_recordset()
        fb_statuses = {c.check_key: c.status
                       for c in fb.sudo().readiness_check_ids}
        self.assertEqual(fb_statuses.get('scopes_granted'), 'fail')

    # ==================================================================
    # T131 — WABA / number listing and selection
    # ==================================================================
    def test_131_wa_resource_selection(self):
        self.Conn.center_begin('whatsapp')
        conn = self._center_connection('whatsapp')
        self._authorize_wa(conn)

        self._mock_graph(get_map={
            '/phone_numbers': {'data': [PHONE_ROW, {
                'id': 'PHONE_ID_2', 'display_phone_number': '+84 28 3800 0000',
                'verified_name': 'Chi nhánh 2', 'name_status': 'PENDING_REVIEW',
            }]},
        })
        listing = self.Conn.center_meta_resources(conn.id)
        self.assertEqual([r['id'] for r in listing['resources']],
                         [WA_PHONE_ID, 'PHONE_ID_2'])
        self.assertIn('Phòng khám Việt Úc', listing['resources'][0]['name'])
        self.assertEqual(listing['resources'][0]['meta']['waba_id'], WA_WABA_ID)
        self.assertFalse(listing['selected'])

        # A number that is not on the granted account is refused, and nothing
        # moves.
        with self.assertRaises(UserError):
            self.Conn.center_meta_select(conn.id, 'PHONE_ID_ELSEWHERE')
        conn.invalidate_recordset()
        self.assertFalse(conn.resource_external_id)

        chosen = self.Conn.center_meta_select(conn.id, WA_PHONE_ID)
        conn.invalidate_recordset()
        self.assertEqual(conn.resource_external_id, WA_PHONE_ID)
        self.assertEqual(conn.resource_secondary_id, WA_WABA_ID)
        self.assertIn('+84 24 7100 0000', conn.resource_display_name)
        self.assertEqual(chosen['state'], 'configuring')
        statuses = {c.check_key: c.status
                    for c in conn.sudo().readiness_check_ids}
        self.assertEqual(statuses.get('resource_selected'), 'pass')

        # The stored resource id is EXACTLY what the webhook routes on — the
        # contract T134 depends on.
        self.assertTrue(self.Conn._find_for_resource('whatsapp', WA_PHONE_ID))

    # ==================================================================
    # T132 — subscribed_apps: success is a check, failure is not a lie
    # ==================================================================
    def test_132_subscribe_webhook(self):
        self.Conn.center_begin('whatsapp')
        conn = self._center_connection('whatsapp')
        self._authorize_wa(conn)
        self._mock_graph(
            get_map={'/phone_numbers': {'data': [PHONE_ROW]}},
            post_map={'/subscribed_apps': {'error': {
                'message': 'Application does not have permission for this '
                           'action', 'code': 200}}})
        self.Conn.center_meta_select(conn.id, WA_PHONE_ID)

        # -- Meta refuses -------------------------------------------------
        raised = False
        try:
            self.Conn.center_meta_subscribe(conn.id)
        except UserError as exc:
            raised = True
            self.assertNotIn(WA_USER_TOKEN, str(exc))
        self.assertTrue(raised)
        conn.invalidate_recordset()
        self.assertEqual(conn.webhook_state, 'none',
                         'a refused subscription must never leave a state '
                         'that claims it worked')
        statuses = {c.check_key: c.status
                    for c in conn.sudo().readiness_check_ids}
        self.assertEqual(statuses.get('webhook_configured'), 'fail')
        self.assertTrue(conn.last_error_redacted)
        self.assertNotIn(WA_USER_TOKEN, conn.last_error_redacted)
        self.assertTrue(self.Audit.sudo().search_count([
            ('connection_id', '=', conn.id),
            ('event', '=', 'webhook_failed')]))

        # -- Meta accepts --------------------------------------------------
        calls = self._mock_graph(
            get_map={'/phone_numbers': {'data': [PHONE_ROW]}},
            post_map={'/subscribed_apps': {'success': True}})
        self.Conn.center_meta_subscribe(conn.id)
        posted = calls['post'][0]
        self.assertIn('/%s/subscribed_apps' % WA_WABA_ID, posted[0],
                      'WhatsApp subscribes the WABA, not the phone number')
        self.assertEqual(posted[2]['access_token'], WA_USER_TOKEN)
        conn.invalidate_recordset()
        self.assertEqual(conn.webhook_state, 'subscribed')
        self.assertEqual(conn.state, 'testing')
        statuses = {c.check_key: c.status
                    for c in conn.sudo().readiness_check_ids}
        self.assertEqual(statuses.get('webhook_configured'), 'pass')

    # ==================================================================
    # T133 — the Messenger Page picker and its per-page token
    # ==================================================================
    def test_133_fb_page_picker(self):
        self.Conn.center_begin('fb')
        conn = self._center_connection('fb')
        outcome = self._authorize_fb(conn)
        self.assertTrue(outcome['ok'])
        conn.invalidate_recordset()
        self.assertEqual(conn.state, 'select_resource')
        # The USER token is held for the picker; nothing may SEND yet.
        self.assertEqual(conn.sudo()._get_secret('refresh_token'), FB_USER_TOKEN)
        self.assertFalse(conn.sudo()._get_secret('access_token'))

        self._mock_graph(get_map={'me/accounts': {'data': [
            {'id': FB_PAGE_ID, 'name': 'Phòng khám Việt Úc',
             'access_token': FB_PAGE_TOKEN},
            {'id': 'PAGE_2', 'name': 'Chi nhánh 2',
             'access_token': 'other-page-token-fixture'},
        ]}})
        listing = self.Conn.center_meta_resources(conn.id)
        self.assertEqual([r['id'] for r in listing['resources']],
                         [FB_PAGE_ID, 'PAGE_2'])
        # A page token is a non-expiring credential — it must never come back
        # to the browser.
        blob = json.dumps(listing, default=str)
        self.assertNotIn(FB_PAGE_TOKEN, blob)
        self.assertNotIn('other-page-token-fixture', blob)
        self.assertNotIn('access_token', blob)

        with self.assertRaises(UserError):
            self.Conn.center_meta_select(conn.id, 'PAGE_NOT_MINE')

        self.Conn.center_meta_select(conn.id, FB_PAGE_ID)
        conn.invalidate_recordset()
        self.assertEqual(conn.resource_external_id, FB_PAGE_ID)
        self.assertEqual(conn.resource_display_name, 'Phòng khám Việt Úc')

        # The PAGE token is what send_message spends, stored encrypted.
        self.env.flush_all()
        self.env.cr.execute(
            'SELECT access_token_enc FROM care_channel_connection '
            'WHERE id = %s', (conn.id,))
        stored = self.env.cr.fetchone()[0]
        self.env.invalidate_all()
        self.assertTrue(stored.startswith('chs$1$'))
        self.assertNotIn(FB_PAGE_TOKEN, stored)
        self.assertEqual(conn.sudo()._get_secret('access_token'), FB_PAGE_TOKEN)

        # ...and the subscription uses the PAGE, with a narrow field list.
        calls = self._mock_graph(
            get_map={'me/accounts': {'data': [
                {'id': FB_PAGE_ID, 'name': 'Phòng khám Việt Úc',
                 'access_token': FB_PAGE_TOKEN}]}},
            post_map={'/subscribed_apps': {'success': True}})
        self.Conn.center_meta_subscribe(conn.id)
        posted = calls['post'][0]
        self.assertIn('/%s/subscribed_apps' % FB_PAGE_ID, posted[0])
        self.assertEqual(posted[2]['subscribed_fields'],
                         'messages,messaging_postbacks')
        self.assertEqual(posted[2]['access_token'], FB_PAGE_TOKEN)

    # ==================================================================
    # T134 — inbound routes to the right connection (CC-B's _dispatch_meta)
    # ==================================================================
    def test_134_inbound_routing(self):
        wa = self._wa_conn()
        fb = self._fb_conn()
        other = self._wa_conn(company=self.company2, phone_id='PHONE_OTHER')

        counts = self.Message._dispatch_meta('whatsapp', self.wa_payload())
        self.assertEqual(counts['ingested'], 1)
        self.assertEqual(counts['unknown'], 0)
        identity = self.identity_of(wa, '84901234567')
        self.assertTrue(identity)
        self.assertFalse(self.identity_of(other, '84901234567'),
                         'another tenant must never receive this traffic')

        counts = self.Message._dispatch_meta('fb', self.fb_payload())
        self.assertEqual(counts['ingested'], 1)
        self.assertTrue(self.identity_of(fb, 'PSID_1'))

        # An id nobody owns is ignored — and says nothing about who exists.
        counts = self.Message._dispatch_meta(
            'whatsapp', self.wa_payload(phone_id='PHONE_NOBODY'))
        self.assertEqual(counts['unknown'], 1)
        self.assertEqual(counts['ingested'], 0)

        # The routing key is EXACTLY the field the CC-E picker writes.
        self.assertEqual(
            self.Message._meta_resource_ids('whatsapp', self.wa_payload()),
            [WA_PHONE_ID])
        self.assertEqual(
            self.Message._meta_resource_ids('fb', self.fb_payload()),
            [FB_PAGE_ID])
        self.assertEqual(wa.resource_external_id, WA_PHONE_ID)
        self.assertEqual(fb.resource_external_id, FB_PAGE_ID)

    # ==================================================================
    # T135 — the 24 h window, and the ONE Messenger tag that still exists
    # ==================================================================
    def test_135_customer_service_window(self):
        wa = self._wa_conn()
        fb = self._fb_conn()
        self.Message._dispatch_meta('whatsapp', self.wa_payload())
        self.Message._dispatch_meta('fb', self.fb_payload())
        wa_ident = self.identity_of(wa, '84901234567')
        fb_ident = self.identity_of(fb, 'PSID_1')
        wa_conv = self.conv_of(wa_ident)
        fb_conv = self.conv_of(fb_ident)

        # --- inside the window: an ordinary reply is allowed --------------
        now = fields.Datetime.now()
        self.Message.sudo().search(
            [('identity_id', 'in', (wa_ident | fb_ident).ids)]).write(
                {'event_at': now - timedelta(hours=1)})
        window = self.Care.channel_send_window(wa_conv.id)
        self.assertTrue(window['open'])
        self.assertFalse(window['requires_template'])
        with self.mock_post({'messages': [{'id': 'wamid.OUT1'}]}):
            self.Care.action_send_channel(wa_conv.id, 'whatsapp', 'xin chào')

        window = self.Care.channel_send_window(fb_conv.id)
        self.assertTrue(window['open'])
        self.assertEqual(window['tags'], [])
        with self.mock_post({'message_id': 'm_out1'}) as mocked:
            self.Care.action_send_channel(fb_conv.id, 'fb', 'xin chào')
        self.assertEqual(mocked.call_args.kwargs['json']['messaging_type'],
                         'RESPONSE')
        self.assertNotIn('tag', mocked.call_args.kwargs['json'])

        # --- outside 24 h: WhatsApp refuses free-form, offers the template -
        self.Message.sudo().search(
            [('identity_id', '=', wa_ident.id)]).write(
                {'event_at': now - timedelta(hours=30)})
        window = self.Care.channel_send_window(wa_conv.id)
        self.assertFalse(window['open'])
        self.assertTrue(window['requires_template'])
        self.assertIn('template', window['message'].lower())
        with self.mock_post({'messages': [{'id': 'x'}]}) as mocked:
            raised = False
            try:
                self.Care.action_send_channel(wa_conv.id, 'whatsapp', 'hello')
            except UserError:
                raised = True
            self.assertTrue(raised, 'a free-form send outside the window must '
                                    'be refused HERE, not at Meta')
            mocked.assert_not_called()

        # ...and the template path is the one that works.
        with self.mock_post({'messages': [{'id': 'wamid.TPL1'}]}) as mocked:
            self.Care.action_send_channel_template(
                wa_conv.id, 'whatsapp', 'visit_reminder', 'vi', ['09:00'])
        body = mocked.call_args.kwargs['json']
        self.assertEqual(body['type'], 'template')
        self.assertEqual(body['template']['name'], 'visit_reminder')
        self.assertEqual(body['template']['language']['code'], 'vi')
        self.assertEqual(
            body['template']['components'][0]['parameters'][0]['text'], '09:00')

        # --- outside 24 h: Messenger gets HUMAN_AGENT and nothing else -----
        self.Message.sudo().search(
            [('identity_id', '=', fb_ident.id),
             ('direction', '=', 'incoming')]).write(
                {'event_at': now - timedelta(hours=30)})
        window = self.Care.channel_send_window(fb_conv.id)
        self.assertFalse(window['open'])
        self.assertTrue(window['requires_tag'])
        self.assertEqual(window['tags'], ['HUMAN_AGENT'])
        self.assertEqual(list(FB_MESSAGE_TAGS), ['HUMAN_AGENT'],
                         'every other Messenger tag died on 2026-04-27 and '
                         'must not be offered')
        with self.mock_post({'message_id': 'm_out2'}) as mocked:
            self.Care.action_send_channel(fb_conv.id, 'fb', 'chúng tôi đây')
        sent = mocked.call_args.kwargs['json']
        self.assertEqual(sent['messaging_type'], 'MESSAGE_TAG')
        self.assertEqual(sent['tag'], 'HUMAN_AGENT')

        # A tag Meta retired is refused by US, not sent and rejected there.
        with self.assertRaises(ChannelSendError):
            fb.sudo()._get_adapter().send_message(
                fb_ident, 'x', tag='CONFIRMED_EVENT_UPDATE')

        # --- past 7 days: nothing may go out at all ------------------------
        self.Message.sudo().search(
            [('identity_id', '=', fb_ident.id),
             ('direction', '=', 'incoming')]).write(
                {'event_at': now - timedelta(days=9)})
        window = self.Care.channel_send_window(fb_conv.id)
        self.assertTrue(window['blocked'])
        self.assertFalse(window['requires_tag'])
        with self.mock_post({'message_id': 'x'}) as mocked:
            with self.assertRaises(UserError):
                self.Care.action_send_channel(fb_conv.id, 'fb', 'hello')
            mocked.assert_not_called()

        # A channel with no provider window answers open, unconditionally, so
        # no caller has to special-case Meta.
        tg = self._tg_conn()
        self.assertTrue(meta_window_state(self.env, tg.sudo(), None)['open'])

    # ==================================================================
    # T136 — approvals are provider STATE, never our failure
    # ==================================================================
    def test_136_approvals_never_fail_readiness(self):
        self.Conn.center_begin('whatsapp')
        conn = self._center_connection('whatsapp')
        self._authorize_wa(conn)
        self._mock_graph(get_map={'/phone_numbers': {'data': [PHONE_ROW]}})
        self.Conn.center_meta_select(conn.id, WA_PHONE_ID)

        # (a) nothing asked yet ⇒ no rows, and provider_approvals is NOT pass.
        cards = {c['channel']: c for c in self.Conn.center_overview()}
        self.assertEqual(cards['whatsapp']['approvals'], [])
        statuses = {c.check_key: c.status
                    for c in conn.sudo().readiness_check_ids}
        self.assertNotEqual(statuses.get('provider_approvals'), 'pass')

        # (b) Meta says "still reviewing" ⇒ pending rows, pending check, and
        # the connection does NOT fall into action_required over it.
        self._mock_graph(get_map={
            '/message_templates': {'data': []},
            '/%s' % WA_PHONE_ID: {'id': WA_PHONE_ID,
                                  'name_status': 'PENDING_REVIEW'},
            '/%s' % WA_WABA_ID: {'id': WA_WABA_ID,
                                 'account_review_status': 'PENDING'},
        })
        result = self.Conn.center_meta_approvals(conn.id, refresh=True)
        by_key = {r['key']: r for r in result['approvals']}
        self.assertEqual(by_key['business_verification']['status'], 'pending')
        self.assertEqual(by_key['display_name']['status'], 'pending')
        self.assertEqual(by_key['templates']['status'], 'pending')
        for row in result['approvals']:
            self.assertNotEqual(row['status'], 'fail',
                                'a review in progress is not a failure')
            self.assertTrue(row['message'])
        conn.invalidate_recordset()
        statuses = {c.check_key: c.status
                    for c in conn.sudo().readiness_check_ids}
        self.assertEqual(statuses.get('provider_approvals'), 'pending')
        self.assertNotEqual(conn.state, 'action_required')

        # (c) even a DECLINED display name only ever reads back as pending on
        # the readiness check — the row tells the truth, the state machine does
        # not lock the channel out of traffic over a review it can still win.
        self._mock_graph(get_map={
            '/message_templates': {'data': [{'name': 't', 'status': 'APPROVED',
                                             'language': 'vi'}]},
            '/%s' % WA_PHONE_ID: {'id': WA_PHONE_ID,
                                  'name_status': 'DECLINED'},
            '/%s' % WA_WABA_ID: {'id': WA_WABA_ID,
                                 'account_review_status': 'APPROVED'},
        })
        result = self.Conn.center_meta_approvals(conn.id, refresh=True)
        by_key = {r['key']: r for r in result['approvals']}
        self.assertEqual(by_key['display_name']['status'], 'fail')
        conn.invalidate_recordset()
        statuses = {c.check_key: c.status
                    for c in conn.sudo().readiness_check_ids}
        self.assertEqual(statuses.get('provider_approvals'), 'pending')
        self.assertNotIn(statuses.get('provider_approvals'), ('fail',))

        # (d) ONLY Meta reporting every item approved flips it — never setup.
        self._mock_graph(get_map={
            '/message_templates': {'data': [{'name': 't', 'status': 'APPROVED',
                                             'language': 'vi'}]},
            '/%s' % WA_PHONE_ID: {'id': WA_PHONE_ID,
                                  'name_status': 'APPROVED'},
            '/%s' % WA_WABA_ID: {'id': WA_WABA_ID,
                                 'account_review_status': 'APPROVED'},
        })
        self.Conn.center_meta_approvals(conn.id, refresh=True)
        conn.invalidate_recordset()
        statuses = {c.check_key: c.status
                    for c in conn.sudo().readiness_check_ids}
        self.assertEqual(statuses.get('provider_approvals'), 'pass')

        # (e) Meta being unreachable never raises at the UI — and, now that
        # provider_approvals is a LATCH (CC-E review HIGH-1), an unreadable
        # refresh does NOT lower the `pass` earned in (d): a transient outage
        # must not demote a live channel out of ingestion. The card row says
        # "couldn't refresh"; the check holds.
        self._mock_graph(get_map={
            '/message_templates': ChannelSendError('network error: boom'),
            '/%s' % WA_PHONE_ID: ChannelSendError('network error: boom'),
            '/%s' % WA_WABA_ID: ChannelSendError('network error: boom'),
        })
        result = self.Conn.center_meta_approvals(conn.id, refresh=True)
        self.assertEqual([r['status'] for r in result['approvals']],
                         ['pending'])
        conn.invalidate_recordset()
        statuses = {c.check_key: c.status
                    for c in conn.sudo().readiness_check_ids}
        self.assertEqual(statuses.get('provider_approvals'), 'pass',
                         'the advisory poll must never lower an earned pass')

    # ==================================================================
    # T141 — CC-E review: the approvals poll must not demote a LIVE channel,
    # and template approval is not a prerequisite to reply in-window
    # ==================================================================
    def _wa_to_ready(self):
        """A WhatsApp connection that has cleared every TECHNICAL check and
        reached `ready` — which T136's fixture never does (it stops at
        `configuring`, outside RECOMPUTE_STATES, so it could not see a
        ready→action_required demotion at all)."""
        self.Conn.center_begin('whatsapp')
        conn = self._center_connection('whatsapp')
        self._authorize_wa(conn)
        self._mock_graph(get_map={'/phone_numbers': {'data': [PHONE_ROW]}})
        self.Conn.center_meta_select(conn.id, WA_PHONE_ID)
        # Into `testing` — the real flow reaches it via subscribe_webhook, and
        # `_recompute_ready` only acts from a RECOMPUTE_STATE, so the checks
        # below cannot promote a `configuring` connection.
        conn.sudo()._transition('testing', reason='test to ready')
        Check = self.env['care.channel.readiness.check']
        for key in ('webhook_configured', 'inbound_ok', 'outbound_ok'):
            Check.upsert_check(conn.sudo(), key, 'pass')
        return conn

    def test_141_approvals_poll_never_demotes_live_channel(self):
        conn = self._wa_to_ready()

        # Business + display name approved, and NO templates at all: a
        # reply-only clinic. Template approval is informational, not a gate
        # (Trap 1), so this reaches provider_approvals=pass and `ready`.
        self._mock_graph(get_map={
            '/message_templates': {'data': []},
            '/%s' % WA_PHONE_ID: {'id': WA_PHONE_ID, 'name_status': 'APPROVED'},
            '/%s' % WA_WABA_ID: {'id': WA_WABA_ID,
                                 'account_review_status': 'APPROVED'},
        })
        self.Conn.center_meta_approvals(conn.id, refresh=True)
        conn.invalidate_recordset()
        statuses = {c.check_key: c.status
                    for c in conn.sudo().readiness_check_ids}
        self.assertEqual(statuses.get('provider_approvals'), 'pass',
                         'a business with no template still reaches ready — '
                         'it can reply inside the 24 h window')
        self.assertEqual(conn.state, 'ready')
        self.assertTrue(conn._may_ingest())

        # Now Meta is unreachable on the nightly poll. Before the latch this
        # demoted ready→action_required and DROPPED inbound. It must not.
        self._mock_graph(get_map={
            '/message_templates': ChannelSendError(
                'network error: with url: /v17.0/x?access_token=EAAsecret123'),
            '/%s' % WA_PHONE_ID: ChannelSendError('network error: boom'),
            '/%s' % WA_WABA_ID: ChannelSendError('network error: boom'),
        })
        self.Conn.center_meta_approvals(conn.id, refresh=True)
        conn.invalidate_recordset()
        self.assertEqual(conn.state, 'ready',
                         'a transient Meta outage must not demote a live '
                         'channel out of ingestion')
        self.assertTrue(conn._may_ingest())

        # ...and the stored failure detail carries no token (MED-1).
        cached = conn.sudo()._get_adapter()._setting('meta_approvals') or {}
        blob = json.dumps(cached, default=str)
        self.assertNotIn('EAAsecret123', blob,
                         'the unreadable detail must be redacted before it '
                         'lands in settings_json')

        # A positively-reported regression also keeps traffic flowing: the row
        # tells the truth on the card, the send path is what catches a real
        # loss of capability.
        self._mock_graph(get_map={
            '/message_templates': {'data': []},
            '/%s' % WA_PHONE_ID: {'id': WA_PHONE_ID, 'name_status': 'DECLINED'},
            '/%s' % WA_WABA_ID: {'id': WA_WABA_ID,
                                 'account_review_status': 'APPROVED'},
        })
        self.Conn.center_meta_approvals(conn.id, refresh=True)
        conn.invalidate_recordset()
        self.assertEqual(conn.state, 'ready')
        self.assertTrue(conn._may_ingest())

    # ==================================================================
    # T137 — the honest dark state: this IS vietuat today
    # ==================================================================
    def test_137_no_platform_app_is_honest(self):
        self.meta_app.write({'active': False})
        self.addCleanup(self.meta_app.write, {'active': True})
        self.assertFalse(self.App.sudo().search_count(
            [('provider', '=', 'meta'), ('active', '=', True)]))

        cards = {c['channel']: c for c in self.Conn.center_overview()}
        for channel in ('whatsapp', 'fb'):
            card = cards[channel]
            self.assertFalse(card['available'], channel)
            self.assertEqual(card['primary_action'], 'unavailable', channel)
            self.assertEqual(card['primary_label'], 'Not available yet',
                             channel)
            # Still IMPLEMENTED: the software is complete, the platform app is
            # what is missing. Conflating the two is how a card lies.
            self.assertTrue(card['implemented'], channel)
            self.assertEqual(card['state'], 'not_connected', channel)

        for channel in ('whatsapp', 'fb'):
            with self.assertRaisesRegex(UserError, 'not available yet'):
                self.Conn.center_begin(channel)
            with self.assertRaises(UserError):
                self.Conn.center_meta_start(channel)

        # Nothing was created on the way through.
        self.assertFalse(self.Conn.with_context(active_test=False).search_count(
            [('channel', 'in', ('whatsapp', 'fb')),
             ('company_id', '=', self.company.id)]))

        # ...and an adapter asked directly refuses rather than guessing.
        probe = self._conn('whatsapp', state='authorizing')
        with self.assertRaises(ChannelSendError):
            probe._get_adapter().authorize_url(None, 'state-x')

    # ==================================================================
    # T138 — spoofing every new endpoint
    # ==================================================================
    def test_138_endpoint_spoof(self):
        conn = self._conn('whatsapp', state='select_resource',
                          resource_external_id=WA_PHONE_ID,
                          resource_secondary_id=WA_WABA_ID)
        intruder = self._mk_user(
            'chub_admin_meta_b', ['health_user_admin.group_health_user_admin'],
            company=self.company2)
        Conn = self.Conn.with_user(intruder)

        for name, call in (
            ('exchange',
             lambda: Conn.center_meta_exchange(conn.id, 'code', 'state')),
            ('resources', lambda: Conn.center_meta_resources(conn.id)),
            ('select', lambda: Conn.center_meta_select(conn.id, WA_PHONE_ID)),
            ('subscribe', lambda: Conn.center_meta_subscribe(conn.id)),
            ('approvals',
             lambda: Conn.center_meta_approvals(conn.id, refresh=True)),
            ('templates', lambda: Conn.center_meta_templates(conn.id)),
            ('test', lambda: Conn.center_test(conn.id)),
        ):
            with self.assertRaisesRegex(UserError, 'another company', msg=name):
                call()

        # A plain CRM user is not a channel administrator anywhere.
        Plain = self.Conn.with_user(self.crm_user)
        for name, call in (
            ('start', lambda: Plain.center_meta_start('whatsapp')),
            ('exchange',
             lambda: Plain.center_meta_exchange(conn.id, 'code', 'state')),
            ('resources', lambda: Plain.center_meta_resources(conn.id)),
            ('select', lambda: Plain.center_meta_select(conn.id, WA_PHONE_ID)),
            ('subscribe', lambda: Plain.center_meta_subscribe(conn.id)),
            ('approvals', lambda: Plain.center_meta_approvals(conn.id)),
            ('templates', lambda: Plain.center_meta_templates(conn.id)),
        ):
            raised = False
            try:
                call()
            except (UserError, AccessError):
                raised = True
            self.assertTrue(raised, '%s must refuse a plain CRM user' % name)

        # Nothing moved and no credential landed.
        conn.invalidate_recordset()
        self.assertEqual(conn.state, 'select_resource')
        self.assertFalse(conn.sudo().has_credentials)
        self.assertFalse(self.env['care.channel.oauth.session'].sudo()
                         .search_count([('connection_id', '=', conn.id)]))

        # The secret columns stay invisible to a Center persona (CC-A §7.2):
        # they are not even in the field list, so nothing can export them.
        admin = self._mk_user(
            'chub_admin_meta_a', ['health_user_admin.group_health_user_admin'])
        visible = conn.with_user(admin).fields_get()
        for column in ('access_token_enc', 'refresh_token_enc',
                       'provider_secret_enc', 'webhook_path_secret'):
            self.assertNotIn(column, visible, column)

    # ==================================================================
    # T139 — the catalogue is still 8 cards, in dock order
    # ==================================================================
    def test_139_catalogue_shape(self):
        cards = self.Conn.center_overview()
        self.assertEqual([c['channel'] for c in cards],
                         ['zalo', 'call', 'email', 'zns', 'whatsapp', 'fb',
                          'telegram', 'webchat'],
                         'the catalogue is the dock order, all eight channels')
        by_key = {c['channel']: c for c in cards}

        # Meta's platform app is seeded in this fixture, so both Meta cards are
        # available AND implemented from CC-E on.
        for channel in ('whatsapp', 'fb'):
            self.assertTrue(by_key[channel]['available'], channel)
            self.assertTrue(by_key[channel]['implemented'], channel)
            self.assertEqual(by_key[channel]['primary_action'], 'connect')
            self.assertEqual(len(by_key[channel]['guide_steps']), 4)
            for step in by_key[channel]['guide_steps']:
                self.assertTrue(step.get('title'))
                self.assertTrue(step.get('body'),
                                'a Meta stepper screen with a title and no '
                                'body is CC-C structure, not CC-E copy')
        self.assertEqual(by_key['whatsapp']['mode'], 'embedded_signup')
        self.assertEqual(by_key['fb']['mode'], 'oauth_popup')

        # Zalo/Google have no platform app in this fixture — unchanged.
        for channel in ('zalo', 'zns', 'email'):
            self.assertFalse(by_key[channel]['available'], channel)
        self.assertTrue(by_key['call']['available'])
        self.assertFalse(by_key['call']['implemented'])

        # No credential material of any kind reaches the browser.
        blob = json.dumps(cards, default=str)
        self.assertNotIn(META_APP_SECRET, blob)
        self.assertNotIn('chs$1$', blob)
        self.assertNotIn(ES_CONFIG_ID, blob,
                         'the catalogue has no business carrying provider '
                         'configuration ids — that is the stepper payload')

    # ==================================================================
    # T140 — regression: the CC-C/CC-D channels are untouched
    # ==================================================================
    def test_140_other_channels_unaffected(self):
        # Telegram: still a guided secret with its own four screens, and a
        # send is unchanged by the Meta window plumbing — the window helper
        # answers "open" for every channel that has no provider window.
        tg = self._tg_conn()
        info = self.Conn.center_begin('telegram')
        self.assertEqual(info['mode'], 'guided_secret')
        self.assertEqual(len(info['guide_steps']), 4)
        self.assertEqual(info['guide_steps'][0]['title'], 'Create your bot')

        self.Message._dispatch_connection(tg.sudo(), self.tg_payload())
        ident = self.identity_of(tg, '555001')
        conv = self.conv_of(ident)
        window = self.Care.channel_send_window(conv.id)
        self.assertTrue(window['open'])
        self.assertFalse(window['requires_template'])
        self.assertFalse(window['requires_tag'])
        with self.mock_post({'ok': True, 'result': {'message_id': 3,
                                                    'chat': {'id': 555001}}}):
            sent = self.Care.action_send_channel(conv.id, 'telegram', 'chào')
        self.assertEqual(sent['delivery'], 'sent')

        # Web chat: still one click, still no window, and its stepper works.
        info = self.Conn.center_begin('webchat')
        self.assertEqual(info['mode'], 'one_click')
        res = self.Conn.center_webchat_enable(
            info['connection_id'], ['https://vietuc.example'])
        self.assertEqual(res['state'], 'testing')
        self.assertIn('?v=', res['snippet'])
        wc = self.Conn.browse(info['connection_id'])
        self.assertTrue(meta_window_state(self.env, wc.sudo(), None)['open'])

        # Zalo: still gated on ITS platform app, and ZNS is still a sub-card.
        cards = {c['channel']: c for c in self.Conn.center_overview()}
        self.assertFalse(cards['zalo']['available'])
        self.assertEqual(cards['zns']['parent_channel'], 'zalo')
        with self.assertRaises(UserError):
            self.Conn.center_begin('zns')

        # The Meta webhook controller CC-B shipped is untouched: still raw
        # http, still POST-only, still fail-closed, still no session.
        from odoo.addons.health_care_command_channels.controllers.meta import (
            MetaWebhookController,
        )
        routing = getattr(MetaWebhookController.meta_webhook,
                          'original_routing', {})
        self.assertEqual(routing.get('type'), 'http')
        self.assertEqual(routing.get('auth'), 'public')
        self.assertEqual(routing.get('methods'), ['POST'])
        self.assertFalse(routing.get('csrf'))
        self.assertFalse(routing.get('save_session'))
