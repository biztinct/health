# -*- coding: utf-8 -*-
"""T108–T112, T119, T120 — Zalo on the connection framework (CC-D).

TransactionCase ONLY, like every other suite in this module (ledger §5.32),
and **every** provider call is mocked: nothing here can reach
oauth.zaloapp.com or openapi.zalo.me, and no credential in it is real.

The health_zalo half of CC-D (the legacy pipeline, the 410 shim, the facade,
the migration and defects Z1/Z4/Z5) is asserted in
``health_zalo/tests/test_zalo_cc_d.py``: those tests need models this module
must not depend on — the dependency runs health_zalo → framework, never back.

Two test-writing rules earn their keep repeatedly below:

* a failure path that must leave NOTHING behind is asserted with
  ``try/except``, never ``assertRaises`` — Odoo wraps the latter in a
  savepoint and rolls back every write made before the raise, which would make
  a leaky implementation look clean (ledger §5.8/§5.65). ``assertRaises`` also
  cannot take a TUPLE of classes here (§5.70);
* readiness is never asserted into place. Fixtures reach their state by
  proving checks, which is the behaviour under test.
"""
import base64
import hashlib
import json
import time
from urllib.parse import parse_qs, urlparse

import requests

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from odoo.addons.health_care_command_channels.services.adapters import (
    ChannelSendError,
)
from odoo.addons.health_care_command_channels.services.webhook_verify import (
    verify_zalo,
)

from .common_spine import ChannelSpineCase

HTTPS_BASE = 'https://care.example.test'

# Fixtures. None of these is a real Zalo credential.
ZALO_APP_ID = '1234567890123456789'
ZALO_APP_SECRET = 'zalo-app-secret-fixture'
ZALO_OA_ID = 'OA_FIXTURE_1'
ZALO_OA_NAME = 'Phòng khám Việt Úc'
ZALO_WEBHOOK_SECRET = 'oa-webhook-secret-fixture'

TOKEN_OK = {'access_token': 'zalo-access-fixture-1',
            'refresh_token': 'zalo-refresh-fixture-1',
            'expires_in': '90000'}
TOKEN_ROTATED = {'access_token': 'zalo-access-fixture-2',
                 'refresh_token': 'zalo-refresh-fixture-2',
                 'expires_in': '90000'}
GETOA_OK = {'data': {'oa_id': ZALO_OA_ID, 'name': ZALO_OA_NAME},
            'error': 0, 'message': 'Success'}


def _s256(verifier):
    digest = hashlib.sha256(verifier.encode('ascii')).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b'=').decode('ascii')


@tagged('post_install', '-at_install')
class TestZaloCenter(ChannelSpineCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.zalo_app = cls.App.create({
            'provider': 'zalo', 'client_id': ZALO_APP_ID})
        cls.zalo_app.action_set_secret(ZALO_APP_SECRET)

    def setUp(self):
        super().setUp()
        self._set_base_url(HTTPS_BASE)

    # -- helpers -------------------------------------------------------
    def _set_base_url(self, value):
        self.env['ir.config_parameter'].sudo().set_param('web.base.url', value)

    def _zalo_conn(self, state='authorizing', **extra):
        return self._conn('zalo', state=state, **extra)

    def _open_session(self, conn):
        """Start a real authorization attempt and keep what only exists once."""
        Session = self.env['care.channel.oauth.session']
        opened = Session.create_for(conn, provider='zalo')
        session = Session.sudo().browse(opened['session_id'])
        return session, opened

    # ==================================================================
    # T108 — the authorization URL: PKCE S256, no secret material
    # ==================================================================
    def test_108_authorize_url(self):
        conn = self._zalo_conn()
        session, opened = self._open_session(conn)
        verifier = session._get_pkce_verifier()
        url = conn._get_adapter().authorize_url(
            session, opened['state'], opened['code_challenge'])

        parsed = urlparse(url)
        query = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        self.assertEqual(parsed.netloc, 'oauth.zaloapp.com')
        self.assertEqual(parsed.path, '/v4/oa/permission')
        self.assertEqual(query['app_id'], ZALO_APP_ID)
        self.assertEqual(query['state'], opened['state'])
        self.assertEqual(query['redirect_uri'],
                         '%s/channel_hub/oauth/callback/zalo' % HTTPS_BASE)

        # PKCE is not decorative: the challenge really is S256(verifier), and
        # the verifier itself never leaves the server.
        self.assertTrue(verifier)
        self.assertEqual(query['code_challenge'], _s256(verifier))
        self.assertEqual(opened['code_challenge_method'], 'S256')
        self.assertNotIn(verifier, url)

        # T79's probe, aimed at this URL: the app SECRET travels in a header
        # on the token call and must never appear here in any form.
        self.assertNotIn(ZALO_APP_SECRET, url)
        self.assertNotIn('secret_key', url)

        # No platform app ⇒ refuse rather than build a URL that cannot work.
        self.zalo_app.write({'active': False})
        with self.assertRaises(ChannelSendError):
            conn._get_adapter().authorize_url(
                session, opened['state'], opened['code_challenge'])
        self.zalo_app.write({'active': True})

    # ==================================================================
    # T109 — the callback happy path
    # ==================================================================
    def test_109_callback_happy_path(self):
        conn = self._zalo_conn()
        session, opened = self._open_session(conn)
        verifier = session._get_pkce_verifier()

        with self.mock_post(TOKEN_OK) as posted, self.mock_get(GETOA_OK):
            result = self.env['care.channel.oauth.session']._handle_callback(
                'zalo', {'state': opened['state'], 'code': 'auth-code-1'})

        self.assertTrue(result['ok'])
        self.assertEqual(result['channel'], 'zalo')

        # The exchange carried the secret in a HEADER and the PKCE verifier in
        # the form body — the two things health_zalo's version never did.
        kwargs = posted.call_args.kwargs
        self.assertEqual(kwargs['headers']['secret_key'], ZALO_APP_SECRET)
        self.assertEqual(kwargs['data']['code_verifier'], verifier)
        self.assertEqual(kwargs['data']['grant_type'], 'authorization_code')
        self.assertEqual(kwargs['data']['app_id'], ZALO_APP_ID)
        self.assertEqual(posted.call_args.args[0],
                         'https://oauth.zaloapp.com/v4/oa/access_token')

        # Tokens are in the database as ciphertext and nowhere else.
        self.env.flush_all()
        self.env.cr.execute(
            'SELECT access_token_enc, refresh_token_enc '
            'FROM care_channel_connection WHERE id = %s', (conn.id,))
        access_enc, refresh_enc = self.env.cr.fetchone()
        self.env.invalidate_all()
        self.assertTrue(access_enc.startswith('chs$1$'))
        self.assertTrue(refresh_enc.startswith('chs$1$'))
        self.assertNotIn(TOKEN_OK['access_token'], access_enc)
        self.assertNotIn(TOKEN_OK['refresh_token'], refresh_enc)
        self.assertEqual(conn.sudo()._get_secret('access_token'),
                         TOKEN_OK['access_token'])

        # getoa is what makes resource_selected honest.
        self.assertEqual(conn.resource_external_id, ZALO_OA_ID)
        self.assertEqual(conn.resource_display_name, ZALO_OA_NAME)
        statuses = {c.check_key: c.status
                    for c in conn.sudo().readiness_check_ids}
        for key in ('authorization_valid', 'resource_selected', 'token_fresh'):
            self.assertEqual(statuses.get(key), 'pass', key)
        self.assertEqual(conn.state, 'configuring')
        self.assertTrue(conn.token_expires_at)

        # Nothing about the grant comes back to the browser.
        blob = json.dumps(result, default=str)
        self.assertNotIn(TOKEN_OK['access_token'], blob)
        self.assertNotIn(TOKEN_OK['refresh_token'], blob)
        self.assertNotIn(opened['state'], blob)

    # ==================================================================
    # T110 — the callback refusals
    # ==================================================================
    def test_110_callback_refusals(self):
        Session = self.env['care.channel.oauth.session']

        # (a) the provider refuses the exchange ⇒ NOTHING is stored.
        conn = self._zalo_conn()
        _session, opened = self._open_session(conn)
        with self.mock_post({'error': -201, 'message': 'invalid code'},
                            status=400), self.mock_get(GETOA_OK) as fetched:
            result = Session._handle_callback(
                'zalo', {'state': opened['state'], 'code': 'bad-code'})
        self.assertEqual(result['outcome'], 'error')
        fetched.assert_not_called()
        conn.invalidate_recordset()
        self.assertFalse(conn.sudo().has_credentials)
        self.assertFalse(conn.resource_external_id)
        self.assertEqual(conn.state, 'authorizing')
        self.assertFalse(self.Check.sudo().search_count(
            [('connection_id', '=', conn.id)]))

        # (b) a state is single use — the replay is indistinguishable from an
        # unknown state, which is what stops the endpoint being an oracle.
        _session2, opened2 = self._open_session(conn)
        with self.mock_post(TOKEN_OK), self.mock_get(GETOA_OK):
            first = Session._handle_callback(
                'zalo', {'state': opened2['state'], 'code': 'c'})
        self.assertTrue(first['ok'])
        with self.mock_post(TOKEN_OK), self.mock_get(GETOA_OK) as fetched:
            replay = Session._handle_callback(
                'zalo', {'state': opened2['state'], 'code': 'c'})
        self.assertEqual(replay, {'outcome': 'generic', 'ok': False,
                                  'channel': False})
        fetched.assert_not_called()
        self.assertEqual(
            Session._handle_callback('zalo', {'state': 'never-issued'}),
            {'outcome': 'generic', 'ok': False, 'channel': False})

        # (c) the tenant said no: the engine's own branch, unbroken by the
        # zalo adapter existing — and nothing is stored on the way through.
        _session3, opened3 = self._open_session(conn)
        with self.mock_post(TOKEN_OK) as posted:
            denied = Session._handle_callback(
                'zalo', {'state': opened3['state'],
                         'error': 'access_denied',
                         'error_description': 'user cancelled'})
        self.assertEqual(denied['outcome'], 'denied')
        self.assertEqual(denied['channel'], 'zalo')
        posted.assert_not_called()

        # (d) a state minted for zalo answered on another provider's callback
        # is a generic refusal, not an exchange.
        _session4, opened4 = self._open_session(conn)
        with self.mock_post(TOKEN_OK) as posted:
            mismatched = Session._handle_callback(
                'meta', {'state': opened4['state'], 'code': 'c'})
        self.assertEqual(mismatched['outcome'], 'generic')
        posted.assert_not_called()

    # ==================================================================
    # T111 — refresh: single-use rotation, and what a failure must NOT do
    # ==================================================================
    def test_111_refresh_rotation(self):
        conn = self._zalo_conn(state='testing',
                               resource_external_id=ZALO_OA_ID)
        conn.action_set_secret('access_token', TOKEN_OK['access_token'])
        conn.action_set_secret('refresh_token', TOKEN_OK['refresh_token'])
        self.Check.upsert_check(conn, 'token_fresh', 'pass')

        with self.mock_post(TOKEN_ROTATED) as posted:
            result = conn._get_adapter().refresh_authorization()
        self.assertTrue(result['ok'])
        kwargs = posted.call_args.kwargs
        self.assertEqual(kwargs['headers']['secret_key'], ZALO_APP_SECRET)
        self.assertEqual(kwargs['data']['grant_type'], 'refresh_token')
        self.assertEqual(kwargs['data']['refresh_token'],
                         TOKEN_OK['refresh_token'])

        # The NEW refresh token is what is stored: Zalo invalidated the old one
        # the moment it answered, so keeping it would be keeping a dead grant.
        conn.invalidate_recordset()
        self.env.invalidate_all()
        self.assertEqual(conn.sudo()._get_secret('refresh_token'),
                         TOKEN_ROTATED['refresh_token'])
        self.assertEqual(conn.sudo()._get_secret('access_token'),
                         TOKEN_ROTATED['access_token'])
        statuses = {c.check_key: c.status
                    for c in conn.sudo().readiness_check_ids}
        self.assertEqual(statuses.get('token_fresh'), 'pass')

        # A network wobble must not cost a working channel its readiness...
        raised = False
        try:
            with self.mock_post(exc=requests.RequestException('boom')):
                conn._get_adapter().refresh_authorization()
        except ChannelSendError:
            raised = True
        self.assertTrue(raised)
        conn.invalidate_recordset()
        self.env.invalidate_all()
        self.assertEqual(conn.sudo()._get_secret('refresh_token'),
                         TOKEN_ROTATED['refresh_token'],
                         'a failed refresh must leave the old token intact')
        statuses = {c.check_key: c.status
                    for c in conn.sudo().readiness_check_ids}
        self.assertEqual(statuses.get('token_fresh'), 'pass',
                         'a transient error is not a lost grant')

        # ...but a refusal from Zalo is a lost grant, and says so.
        # try/except, NOT assertRaises: the savepoint would roll back the very
        # evidence this asserts on (ledger §5.8/§5.65).
        raised = False
        try:
            with self.mock_post({'error': -216,
                                 'message': 'invalid refresh token'}):
                conn._get_adapter().refresh_authorization()
        except ChannelSendError:
            raised = True
        self.assertTrue(raised)
        conn.invalidate_recordset()
        self.env.invalidate_all()
        self.assertEqual(conn.sudo()._get_secret('refresh_token'),
                         TOKEN_ROTATED['refresh_token'])
        statuses = {c.check_key: c.status
                    for c in conn.sudo().readiness_check_ids}
        self.assertEqual(statuses.get('token_fresh'), 'fail')
        self.assertTrue(self.Audit.sudo().search_count([
            ('connection_id', '=', conn.id), ('event', '=', 'refresh_fail')]))

        # The NOWAIT lock is what makes the rotation safe under two workers.
        # A genuine two-worker race cannot be staged in a TransactionCase
        # (ledger §5.63) — the live smoke check is in the evidence pack. What
        # IS provable here: the statement runs uncontended and the callable
        # really goes through it.
        self.assertEqual(conn.sudo()._with_refresh_lock(lambda: 'ran'), 'ran')

    # ==================================================================
    # T112 — verify_zalo: one golden vector, then the refusal matrix
    # ==================================================================
    def test_112_verify_zalo(self):
        conn = self._zalo_conn(state='testing',
                               resource_external_id=ZALO_OA_ID)
        conn.action_set_secret('provider_secret', ZALO_WEBHOOK_SECRET)
        raw = b'{"oa_id":"OA_FIXTURE_1","event_name":"user_send_text"}'

        # -- the golden vector, computed here the way the spec words it -----
        ts = str(int(time.time() * 1000))
        expected = hashlib.sha256(
            ZALO_APP_ID.encode() + raw + ts.encode()
            + ZALO_WEBHOOK_SECRET.encode()).hexdigest()
        headers = {'X-ZEvent-Signature': 'mac=%s' % expected,
                   'X-ZEvent-Timestamp': ts}
        self.assertTrue(verify_zalo(conn.sudo(), raw, headers))
        # The `mac=` prefix is optional, the value is what matters.
        self.assertTrue(verify_zalo(
            conn.sudo(), raw,
            {'X-ZEvent-Signature': expected, 'X-ZEvent-Timestamp': ts}))

        # -- the refusal matrix — every one of these is fail-CLOSED --------
        self.assertFalse(verify_zalo(conn.sudo(), raw,
                                     {'X-ZEvent-Timestamp': ts}),
                         'missing signature header')
        self.assertFalse(verify_zalo(conn.sudo(), raw,
                                     {'X-ZEvent-Signature': 'mac=%s' % expected}),
                         'missing timestamp header')
        self.assertFalse(verify_zalo(conn.sudo(), raw, {}), 'no headers')
        self.assertFalse(
            verify_zalo(conn.sudo(), raw,
                        {'X-ZEvent-Signature': 'mac=' + 'a' * 64,
                         'X-ZEvent-Timestamp': ts}), 'wrong mac')
        self.assertFalse(verify_zalo(conn.sudo(), raw + b' ', headers),
                         'the body is signed byte for byte')
        stale = str(int((time.time() - 3600) * 1000))
        stale_mac = hashlib.sha256(
            ZALO_APP_ID.encode() + raw + stale.encode()
            + ZALO_WEBHOOK_SECRET.encode()).hexdigest()
        self.assertFalse(
            verify_zalo(conn.sudo(), raw,
                        {'X-ZEvent-Signature': 'mac=%s' % stale_mac,
                         'X-ZEvent-Timestamp': stale}),
            'a correctly signed but hour-old event is a replay')
        self.assertFalse(verify_zalo(None, raw, headers), 'unknown oa_id')

        # An unknown oa_id really does resolve to nothing at controller level.
        self.assertFalse(self.Conn._find_for_resource('zalo', 'NOT_AN_OA'))

        # No per-OA secret ⇒ reject. This is defect Z2 in one assertion: the
        # old webhook ACCEPTED events in exactly this situation.
        naked = self._conn('zalo', company=self.company2, state='testing',
                           resource_external_id='OA_NAKED')
        self.assertFalse(verify_zalo(naked.sudo(), raw, headers))

        # No platform app ⇒ reject (there is no app_id to sign with).
        self.zalo_app.write({'active': False})
        self.assertFalse(verify_zalo(conn.sudo(), raw, headers))
        self.zalo_app.write({'active': True})

    # ==================================================================
    # T119 — the Center flow, end to end
    # ==================================================================
    def test_119_center_flow(self):
        cards = {c['channel']: c for c in self.Conn.center_overview()}
        self.assertTrue(cards['zalo']['available'],
                        'a seeded zalo platform app makes the card offerable')
        self.assertTrue(cards['zalo']['implemented'])
        self.assertEqual(cards['zalo']['mode'], 'oauth_popup')
        self.assertEqual(cards['zns']['parent_channel'], 'zalo')

        info = self.Conn.center_begin('zalo')
        conn = self.Conn.browse(info['connection_id'])
        self.assertEqual(info['mode'], 'oauth_popup')
        self.assertEqual(len(info['guide_steps']), 4)
        self.assertEqual(conn.state, 'authorizing')

        # -- sign in ---------------------------------------------------
        started = self.Conn.center_zalo_authorize(conn.id)
        self.assertTrue(started['url'].startswith(
            'https://oauth.zaloapp.com/v4/oa/permission?'))
        # The URL is all the browser gets: no verifier, no session id, no
        # separate state field it could stash.
        self.assertEqual(set(started), {'connection_id', 'state', 'url'})
        state = parse_qs(urlparse(started['url']).query)['state'][0]

        with self.mock_post(TOKEN_OK), self.mock_get(GETOA_OK):
            self.env['care.channel.oauth.session']._handle_callback(
                'zalo', {'state': state, 'code': 'auth-code-119'})
        conn.invalidate_recordset()
        self.assertEqual(conn.state, 'configuring')
        self.assertEqual(conn.resource_display_name, ZALO_OA_NAME)

        # -- the portal-guided webhook step ----------------------------
        detail = self.Conn.center_zalo_info(conn.id)
        self.assertEqual(detail['webhook_url'],
                         '%s/care_channels/zalo/webhook' % HTTPS_BASE)
        self.assertFalse(detail['has_webhook_secret'])

        saved = self.Conn.center_zalo_set_webhook_secret(
            conn.id, ZALO_WEBHOOK_SECRET)
        conn.invalidate_recordset()
        self.assertEqual(saved['state'], 'testing')
        self.assertEqual(conn.webhook_state, 'subscribed')
        self.env.flush_all()
        self.env.cr.execute(
            'SELECT provider_secret_enc FROM care_channel_connection '
            'WHERE id = %s', (conn.id,))
        stored = self.env.cr.fetchone()[0]
        self.env.invalidate_all()
        self.assertTrue(stored.startswith('chs$1$'))
        self.assertNotIn(ZALO_WEBHOOK_SECRET, stored)
        # Pasting a secret is a CLAIM. webhook_verified stays pending until a
        # signed event actually arrives.
        statuses = {c.check_key: c.status
                    for c in conn.sudo().readiness_check_ids}
        self.assertEqual(statuses.get('webhook_configured'), 'pass')
        self.assertNotEqual(statuses.get('webhook_verified'), 'pass')

        # -- the first verified inbound (amendment F1) -----------------
        conn.sudo()._note_inbound()
        conn.invalidate_recordset()
        self.assertEqual(conn.state, 'testing',
                         'the proving inbound must not demote the connection '
                         'out of the traffic that finishes the job')
        self.assertTrue(conn._may_ingest())
        statuses = {c.check_key: c.status
                    for c in conn.sudo().readiness_check_ids}
        self.assertEqual(statuses.get('webhook_verified'), 'pass')

        # ...and outbound is the last required check.
        self.Check.upsert_check(conn, 'outbound_ok', 'pass')
        conn.invalidate_recordset()
        self.assertEqual(conn.state, 'ready')

        # -- ZNS renders honestly, and is never its own connection ------
        cards = {c['channel']: c for c in self.Conn.center_overview()}
        zns = cards['zns']['zns']
        self.assertEqual(zns['templates_total'], 12)
        self.assertEqual(zns['approvals'], 'pending')
        self.assertIn('Not proven yet', zns['proof'])
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('health_messaging.zns_template_reminder2', 'TPL-FIXTURE')
        zns = {c['channel']: c
               for c in self.Conn.center_overview()}['zns']['zns']
        self.assertGreaterEqual(zns['templates_configured'], 1)

        # A ZNS send Zalo accepted is the only thing that flips it.
        self.Check.upsert_check(conn, 'provider_approvals', 'pass')
        zns = {c['channel']: c
               for c in self.Conn.center_overview()}['zns']['zns']
        self.assertEqual(zns['approvals'], 'pass')
        self.assertIn('Proven', zns['proof'])

        # T104's contract still holds: ZNS is part of the Zalo connection.
        with self.assertRaises(UserError):
            self.Conn.center_begin('zns')

    # ==================================================================
    # T120 — spoofing the new endpoints
    # ==================================================================
    def test_120_endpoint_spoof(self):
        conn = self._zalo_conn(state='configuring',
                               resource_external_id=ZALO_OA_ID)
        intruder = self._mk_user(
            'chub_admin_zalo_b', ['health_user_admin.group_health_user_admin'],
            company=self.company2)
        Conn = self.Conn.with_user(intruder)

        for name, call in (
            ('authorize', lambda: Conn.center_zalo_authorize(conn.id)),
            ('info', lambda: Conn.center_zalo_info(conn.id)),
            ('set_webhook_secret',
             lambda: Conn.center_zalo_set_webhook_secret(conn.id, 'x' * 20)),
            ('test', lambda: Conn.center_test(conn.id)),
        ):
            with self.assertRaisesRegex(UserError, 'another company', msg=name):
                call()

        # A plain CRM user is not a channel administrator anywhere.
        Plain = self.Conn.with_user(self.crm_user)
        for name, call in (
            ('authorize', lambda: Plain.center_zalo_authorize(conn.id)),
            ('info', lambda: Plain.center_zalo_info(conn.id)),
            ('set_webhook_secret',
             lambda: Plain.center_zalo_set_webhook_secret(conn.id, 'x' * 20)),
        ):
            raised = False
            try:
                call()
            except (UserError, AccessError):
                raised = True
            self.assertTrue(raised, '%s must refuse a plain CRM user' % name)

        # Nothing moved and no credential landed.
        conn.invalidate_recordset()
        self.assertEqual(conn.state, 'configuring')
        self.assertFalse(conn.sudo().has_credentials)
        self.assertFalse(self.env['care.channel.oauth.session'].sudo()
                         .search_count([('connection_id', '=', conn.id)]))

    # ==================================================================
    # The webhook route itself is declared the way §5.61 requires
    # ==================================================================
    def test_121_webhook_route_shape(self):
        from odoo.addons.health_care_command_channels.controllers.zalo import (
            ZaloWebhookController,
        )
        routing = getattr(ZaloWebhookController.zalo_webhook,
                          'original_routing', {})
        self.assertEqual(routing.get('type'), 'http',
                         'a jsonrpc route re-serialises the JSON and the mac '
                         'can never match (defect Z2)')
        self.assertEqual(routing.get('auth'), 'public')
        self.assertEqual(routing.get('methods'), ['POST'])
        self.assertFalse(routing.get('csrf'))
        self.assertFalse(routing.get('save_session'))

        # An unverifiable body never reaches an ingest path: with no oa_id in
        # it there is no connection, and with no connection there is no secret.
        oa_id, payload = ZaloWebhookController._oa_id(b'{"event_name":"x"}')
        self.assertIsNone(oa_id)
        self.assertEqual(payload, {'event_name': 'x'})
        self.assertEqual(ZaloWebhookController._oa_id(b'not json'),
                         (None, None))
        self.assertEqual(
            ZaloWebhookController._oa_id(b'{"recipient":{"id":"OA9"}}')[0],
            'OA9')

    # ==================================================================
    # A non-ingestable zalo connection drops the traffic, audibly
    # ==================================================================
    def test_122_dispatch_gate(self):
        conn = self._zalo_conn(state='disabled',
                               resource_external_id=ZALO_OA_ID)
        counts = self.Message._dispatch_zalo(conn.sudo(), {'oa_id': ZALO_OA_ID})
        self.assertEqual(counts['ignored'], 1)
        self.assertEqual(counts['ingested'], 0)
        self.assertTrue(self.Audit.sudo().search_count([
            ('connection_id', '=', conn.id),
            ('event', '=', 'webhook_ignored')]))
        conn.invalidate_recordset()
        self.assertFalse(conn.last_inbound_at,
                         'a dropped event is not proof that anything works')
