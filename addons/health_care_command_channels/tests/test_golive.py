# -*- coding: utf-8 -*-
"""T170–T182 — GL-1: the Go-Live Studio's server framework.

What is actually under test is one sentence: **a step is done because the
artifact exists, never because somebody said so**. Everything else here is the
plumbing that keeps that true — the regexes that refuse a paste before a row is
created, the merge that keeps a sibling configuration id alive, the secret that
appears in no return value, and the two public webhooks that write the only
honest proof a provider ever gives us that our URL was pasted correctly.

Two suites, deliberately:

* a ``TransactionCase`` for the model surface, mocked at ``meta_app_identity``
  with a PLAIN FUNCTION (§5.76 — a second ``autospec`` patch stops binding
  ``self``), so nothing here can reach Meta;
* an ``HttpCase`` for the handshake logging, because the audit row is written
  by a controller and a model-level test would prove nothing about the route.
  It is the first HttpCase in this module (ledger §5.32 kept them out): its
  requests run on a ``TestCursor``, so every row it makes rolls back with the
  class, and it asserts on DELTAS rather than absolute counts because
  ``care.channel.audit`` is append-only evidence that accumulates on a real
  deployment (§5.50/§5.95).
"""
import hashlib
import json
import logging
import os
import re
import secrets
import time
from datetime import timedelta
from functools import wraps
from unittest.mock import patch
from urllib.parse import urlencode

from markupsafe import escape

from odoo import fields
from odoo.addons.base.models.ir_mail_server import MailDeliveryException
from odoo.exceptions import UserError, ValidationError
from odoo.modules.module import get_manifest
from odoo.tests import HttpCase, new_test_user, tagged

from odoo.addons.health_care_command_channels.models.care_channel_connection import (
    INTERNAL_CTX,
)
from odoo.addons.health_care_command_channels.models.care_channel_message import (
    CareChannelMessage,
)
from odoo.addons.health_care_command_channels.models.channel_golive import (
    GOLIVE_PROVIDERS, GOLIVE_STEP_KEYS,
)
from odoo.addons.health_care_command_channels.models.channel_platform_app import (
    PROVIDER_EXTERNAL_STEPS,
)
from odoo.addons.health_care_command_channels.services.adapters import (
    ChannelSendError,
)

from .common import ChannelHubCase

_logger = logging.getLogger(__name__)

HTTPS_BASE = 'https://care.example.test'

# None of these is a real credential.
META_APP_ID = '1234567890123'
META_APP_ID_2 = '9876543210987'
META_SECRET = 'meta-app-secret-gl1-fixture'
META_APP_NAME = 'Việt Úc Care (go-live)'
ES_ID = '111222333444555'
FLB_ID = '555444333222111'
ES_ID_2 = '111222333444999'
FLB_ID_2 = '555444333222999'
SEED_TOKEN = 'seeded-verify-token-gl1'

ZALO_APP_ID = '1234567890123456789'
ZALO_SECRET = 'zalo-app-secret-gl1-fixture'
ZALO_OA_ID = 'OA_GL1_FIXTURE'
ZALO_WEBHOOK_SECRET = 'oa-webhook-secret-gl1-fixture'

IDENTITY_TARGET = ('odoo.addons.health_care_command_channels.models.'
                   'channel_platform_app.meta_app_identity')


@tagged('post_install', '-at_install')
class TestGoliveStudio(ChannelHubCase):

    def setUp(self):
        super().setUp()
        self.env['ir.config_parameter'].sudo().set_param('web.base.url',
                                                         HTTPS_BASE)
        # A live deployment carries the operator's own rows, and `provider` is
        # unique among the ACTIVE ones — every fixture below would collide
        # with them and "nothing exists yet" would read a row it never made.
        # Archived (never deleted) inside the test transaction, exactly as
        # common.py does for connections (test_platform_go_live.py:68).
        self.App.sudo().with_context(active_test=False).search([]).write(
            {'active': False})
        self.env['channel.golive.progress'].sudo().with_context(
            active_test=False).search([]).write({'active': False})

    # -- helpers -------------------------------------------------------
    def _state(self, provider='meta'):
        return {p['provider']: p for p in self.App.golive_state()}[provider]

    def _steps(self, provider='meta', state=None):
        state = state or self._state(provider)
        return {s['key']: s for s in state['steps']}

    def _identity(self, name=META_APP_NAME, exc=None):
        """Patch Meta's ONE credentials-only call with a plain function.

        ``patch(..., autospec=True)`` re-applied over an existing patch stops
        binding ``self`` and silently returns the mock's default (§5.76); a
        plain function is an ordinary descriptor and stacks correctly.
        """
        def fake_identity(env, client_id, secret):
            if exc is not None:
                raise exc
            return name
        return patch(IDENTITY_TARGET, fake_identity)

    def _create_app_step(self, app_id=META_APP_ID):
        return self.App.golive_submit('meta', 'create_app',
                                      {'client_id': app_id})

    # ==================================================================
    # T170 — the platform plane stays with the platform operator
    # ==================================================================
    def test_170_operator_gate(self):
        """All three methods are RPC-reachable by name, so the ACL is not the
        whole story — each one carries its own gate (channel_platform_app.py
        :487, the same reasoning as action_set_secret)."""
        As = self.App.with_user(self.crm_mgr)
        for name, call in (
            ('golive_state', lambda: As.golive_state()),
            ('golive_submit',
             lambda: As.golive_submit('meta', 'create_app',
                                      {'client_id': META_APP_ID})),
            ('golive_mark',
             lambda: As.golive_mark('meta', 'business_verification', True)),
        ):
            with self.assertRaises(UserError, msg=name):
                call()

        # ...and the refused calls left nothing behind at all.
        self.assertFalse(self.App.sudo().search_count([('active', '=', True)]))
        self.assertFalse(self.env['channel.golive.progress'].sudo()
                         .search_count([('active', '=', True)]))

        # The operator gets through every one of them.
        self.assertTrue(self.App.golive_state())
        self.App.golive_mark('meta', 'business_verification', True)
        self.App.golive_submit('meta', 'create_app', {'client_id': META_APP_ID})

    # ==================================================================
    # T171 — the empty deployment: every step declared, nothing claimed
    # ==================================================================
    def test_171_fresh_state(self):
        state = self.App.golive_state()
        self.assertEqual([p['provider'] for p in state],
                         list(GOLIVE_PROVIDERS))
        meta = {p['provider']: p for p in state}['meta']
        zalo = {p['provider']: p for p in state}['zalo']

        self.assertEqual(len(meta['steps']), 7)
        self.assertEqual(len(zalo['steps']), 5)
        for provider in (meta, zalo):
            self.assertFalse(provider['app_id'])
            self.assertFalse(provider['client_id'])
            self.assertFalse(provider['secret_hint'])
            self.assertEqual(provider['preflight']['status'], 'none')
            self.assertEqual(provider['progress'], {})
            # The URLs are properties of the DEPLOYMENT, not of a row: the
            # operator must be able to paste them into the provider console
            # before anything exists here.
            self.assertTrue(provider['values']['oauth_redirect_uri'])
            self.assertTrue(provider['values']['webhook_urls'])
            self.assertIn(HTTPS_BASE, provider['values']['oauth_redirect_uri'])
            for step in provider['steps']:
                for key in GOLIVE_STEP_KEYS + ('status', 'marked_on'):
                    self.assertIn(key, step, step['key'])
                # A webhook_handshake row is append-only evidence a real
                # deployment may already carry, and it is the one thing that
                # can legitimately be `done` here.
                if step['verify'] == 'handshake' and provider[
                        'last_handshake_at']:
                    self.assertEqual(step['status'], 'done')
                else:
                    self.assertEqual(step['status'], 'todo',
                                     '%s/%s' % (provider['provider'],
                                                step['key']))

        self.assertEqual(meta['channels'], ['fb', 'whatsapp'])
        self.assertEqual(zalo['channels'], ['zalo', 'zns'])
        self.assertFalse(any(meta['platform_ready'].values()))

        # A console link that needs the app id is FALSE until we know it: a
        # half-interpolated URL 404s and reads as "Meta lost your app".
        steps = self._steps('meta', meta)
        self.assertFalse(steps['store_secret']['console'])
        self.assertTrue(steps['create_app']['console'].startswith('https://'))
        self.assertEqual(steps['webhooks']['copy_values'],
                         ['oauth_redirect_uri', 'webhook_urls', 'verify_token'])
        self.assertFalse(meta['values']['verify_token'])
        # Zalo has no verify token — it is not a Zalo concept.
        self.assertNotIn('verify_token', zalo['values'])

    # ==================================================================
    # T172 — a refused paste creates NOTHING
    # ==================================================================
    def test_172_regex_refusal_creates_no_row(self):
        with self.assertRaises(ValidationError):
            self.App.golive_submit('meta', 'create_app', {'client_id': 'abc'})
        self.assertFalse(
            self.App.sudo().with_context(active_test=False).search_count(
                [('provider', '=', 'meta'), ('active', '=', True)]),
            'validation runs BEFORE the row is created — a typo must not '
            'leave a half-built platform application behind')

        # The declared error string is what the operator sees, not a regex.
        try:
            self.App.golive_submit('meta', 'create_app', {'client_id': 'abc'})
        except ValidationError as exc:
            self.assertIn('long number', str(exc))

    # ==================================================================
    # T173 — one row per provider, created on first submit, updated after
    # ==================================================================
    def test_173_first_submit_creates_one_row(self):
        state = self._create_app_step()
        meta = {p['provider']: p for p in state}['meta']
        app = self.App.sudo().search([('provider', '=', 'meta'),
                                      ('active', '=', True)])
        self.assertEqual(len(app), 1)
        self.assertEqual(app.client_id, META_APP_ID)
        self.assertEqual(meta['app_id'], app.id)
        self.assertEqual(meta['client_id'], META_APP_ID)
        self.assertEqual(self._steps('meta', meta)['create_app']['status'],
                         'done')
        # Now the app-scoped consoles resolve.
        self.assertIn(META_APP_ID,
                      self._steps('meta', meta)['store_secret']['console'])

        # A second submit UPDATES: `_check_provider_unique` is never reached,
        # because a second row is never attempted.
        state = self._create_app_step(META_APP_ID_2)
        self.assertEqual(
            self.App.sudo().search_count([('provider', '=', 'meta'),
                                          ('active', '=', True)]), 1)
        app.invalidate_recordset()
        self.assertEqual(app.client_id, META_APP_ID_2)

    # ==================================================================
    # T174 — the secret: one write path, a real check, and no echo
    # ==================================================================
    def test_174_secret_submit_and_preflight(self):
        self._create_app_step()
        with self._identity():
            state = self.App.golive_submit('meta', 'store_secret',
                                           {'client_secret': META_SECRET})
        meta = {p['provider']: p for p in state}['meta']
        app = self.App._get_for_provider('meta')

        self.assertTrue(app.has_secret)
        self.assertTrue(app.sudo().client_secret_enc.startswith('chs$1$'))
        self.assertNotIn(META_SECRET, app.sudo().client_secret_enc)
        self.assertEqual(app.preflight_status, 'pass')
        self.assertEqual(app.preflight_detail, META_APP_NAME)
        self.assertEqual(meta['secret_hint'], app.secret_hint)
        self.assertEqual(self._steps('meta', meta)['store_secret']['status'],
                         'done')

        # The whole payload, serialised: no secret material may be in it.
        blob = json.dumps(state, default=str)
        for forbidden in (META_SECRET, app.sudo().client_secret_enc, 'chs$1$'):
            self.assertNotIn(forbidden, blob,
                             'no credential material may reach the Studio')

    # ==================================================================
    # T175 — a provider refusal is an ANSWER, and it is visible
    # ==================================================================
    def test_175_preflight_refusal(self):
        self._create_app_step()
        with self._identity(exc=ChannelSendError('bad app secret')):
            # No exception reaches the caller: action_preflight persists the
            # outcome and never raises on a refusal (channel_platform_app:416).
            state = self.App.golive_submit('meta', 'store_secret',
                                           {'client_secret': META_SECRET})
        app = self.App._get_for_provider('meta')
        self.assertEqual(app.preflight_status, 'fail')
        self.assertTrue(app.preflight_detail,
                        'a fail with no reason is not evidence, it is a shrug')
        self.assertNotIn(META_SECRET, app.preflight_detail)
        meta = {p['provider']: p for p in state}['meta']
        self.assertEqual(self._steps('meta', meta)['store_secret']['status'],
                         'fail')
        self.assertEqual(meta['preflight']['status'], 'fail')
        self.assertNotIn(META_SECRET, json.dumps(state, default=str))

        # The secret IS stored — the refusal is about the value, and the
        # operator fixes it by pasting again.
        self.assertTrue(app.has_secret)

    # ==================================================================
    # T176 — extra_json is MERGED, and the verify token is minted once
    # ==================================================================
    def test_176_config_ids_merge_and_token(self):
        # (a) a token that already exists survives the write untouched.
        self._create_app_step()
        app = self.App._get_for_provider('meta')
        app.sudo().write({'extra_json': json.dumps(
            {'verify_token': SEED_TOKEN})})
        state = self.App.golive_submit(
            'meta', 'config_ids', {'es_config_id': ES_ID,
                                   'flb_config_id': FLB_ID})
        extra = json.loads(app.sudo().extra_json)
        self.assertEqual(extra['es_config_id'], ES_ID)
        self.assertEqual(extra['flb_config_id'], FLB_ID)
        self.assertEqual(extra['verify_token'], SEED_TOKEN,
                         'losing a sibling key dark-cards a channel')
        meta = {p['provider']: p for p in state}['meta']
        self.assertEqual(self._steps('meta', meta)['config_ids']['status'],
                         'done')
        self.assertEqual(meta['values']['verify_token'], SEED_TOKEN)
        self.assertEqual(meta['values']['es_config_id'], ES_ID)

        # (b) with no token yet, the first extra-write mints one...
        app.sudo().write({'active': False})
        self._create_app_step()
        fresh = self.App._get_for_provider('meta')
        self.assertNotEqual(fresh.id, app.id)
        self.App.golive_submit('meta', 'config_ids',
                               {'es_config_id': ES_ID, 'flb_config_id': FLB_ID})
        token = json.loads(fresh.sudo().extra_json)['verify_token']
        self.assertTrue(token and len(token) >= 24,
                        'the token must be generated, not invented by a human')

        # ...and a second submit does NOT re-mint: Meta's dashboard still
        # holds the first one.
        self.App.golive_submit('meta', 'config_ids',
                               {'es_config_id': ES_ID_2,
                                'flb_config_id': FLB_ID_2})
        extra = json.loads(fresh.sudo().extra_json)
        self.assertEqual(extra['verify_token'], token)
        self.assertEqual(extra['es_config_id'], ES_ID_2)
        self.assertEqual(extra['flb_config_id'], FLB_ID_2)

        # One id at a time is a legal submit, and it keeps the other.
        self.App.golive_submit('meta', 'config_ids', {'es_config_id': ES_ID})
        extra = json.loads(fresh.sudo().extra_json)
        self.assertEqual(extra['es_config_id'], ES_ID)
        self.assertEqual(extra['flb_config_id'], FLB_ID_2)

    # ==================================================================
    # T177 — marks are for what we cannot see, and only for that
    # ==================================================================
    def test_177_mark_waiting_steps_only(self):
        state = self.App.golive_mark('meta', 'business_verification', True)
        meta = {p['provider']: p for p in state}['meta']
        step = self._steps('meta', meta)['business_verification']
        self.assertEqual(step['status'], 'waiting',
                         'submitted is not approved — a wait step never says '
                         'done on a human process Meta has not finished')
        self.assertTrue(step['marked_on'])
        self.assertEqual(meta['progress']['business_verification']['marked_on'],
                         step['marked_on'])
        self.assertEqual(
            self.env['channel.golive.progress'].sudo().search_count(
                [('provider', '=', 'meta'), ('active', '=', True)]), 1)

        # A derived step refuses a hand-mark: a green step over a dark channel
        # is the exact lie the readiness model exists to prevent.
        raised = False
        try:
            self.App.golive_mark('meta', 'store_secret', True)
        except (UserError, ValidationError):
            raised = True
        self.assertTrue(raised)
        # ...and the refusal wrote nothing.
        row = self.env['channel.golive.progress'].sudo().search(
            [('provider', '=', 'meta'), ('active', '=', True)])
        self.assertNotIn('store_secret', row._steps())

        # The webhook step is proven by Meta calling us, not by a tick.
        raised = False
        try:
            self.App.golive_mark('meta', 'webhooks', True)
        except (UserError, ValidationError):
            raised = True
        self.assertTrue(raised)

        # Unmarking works, and a second wait step is independent.
        self.App.golive_mark('meta', 'app_review', True)
        state = self.App.golive_mark('meta', 'business_verification', False)
        steps = self._steps('meta', {p['provider']: p
                                     for p in state}['meta'])
        self.assertEqual(steps['business_verification']['status'], 'todo')
        self.assertFalse(steps['business_verification']['marked_on'])
        self.assertEqual(steps['app_review']['status'], 'waiting')

        # A second row for the same provider is never created.
        self.assertEqual(
            self.env['channel.golive.progress'].sudo().search_count(
                [('provider', '=', 'meta'), ('active', '=', True)]), 1)
        with self.assertRaises(ValidationError):
            self.env['channel.golive.progress'].sudo().create(
                {'provider': 'meta'})

    # ==================================================================
    # T178 — derived truth outranks the progress row, in both directions
    # ==================================================================
    def test_178_handshake_beats_the_mark(self):
        self._create_app_step()
        self.assertEqual(self._steps('meta')['webhooks']['status'], 'todo')

        self.Audit._log('webhook_handshake', channel='whatsapp',
                        detail='meta dashboard handshake ok')
        state = self._state('meta')
        self.assertTrue(state['last_handshake_at'])
        self.assertEqual(self._steps('meta', state)['webhooks']['status'],
                         'done',
                         'the handshake reached us — that is the proof, and '
                         'no steps_json entry was needed to say so')

        # The last step is the platform-app completeness check said in words:
        # it cannot be reached until every prerequisite really is in place.
        self.assertEqual(self._steps('meta', state)['done']['status'], 'todo')
        with self._identity():
            self.App.golive_submit('meta', 'store_secret',
                                   {'client_secret': META_SECRET})
        self.App.golive_submit('meta', 'config_ids',
                               {'es_config_id': ES_ID, 'flb_config_id': FLB_ID})
        state = self._state('meta')
        self.assertEqual(self._steps('meta', state)['done']['status'], 'done')
        self.assertTrue(all(state['platform_ready'].values()),
                        'the finished go-live is exactly what lights the cards')

    # ==================================================================
    # T179 — everything unknown is refused, cleanly
    # ==================================================================
    def test_179_unknown_inputs_are_refused(self):
        with self.assertRaises(ValidationError):
            self.App.golive_submit('meta', 'create_app',
                                   {'client_id': META_APP_ID,
                                    'client_secret': META_SECRET})
        with self.assertRaises(ValidationError):
            self.App.golive_submit('meta', 'not_a_step', {'client_id': '1'})
        with self.assertRaises(ValidationError):
            self.App.golive_submit('google', 'create_app',
                                   {'client_id': META_APP_ID})
        with self.assertRaises(ValidationError):
            self.App.golive_submit('meta', 'business_verification', {})
        with self.assertRaises(ValidationError):
            self.App.golive_mark('zalo', 'not_a_step', True)
        with self.assertRaises(ValidationError):
            self.App.golive_mark('microsoft', 'done', True)
        self.assertFalse(self.App.sudo().search_count([('active', '=', True)]),
                         'not one refusal created a row')

        # Zalo's own credentials step takes both values at once and has no
        # server-side check to run afterwards.
        state = self.App.golive_submit(
            'zalo', 'credentials', {'client_id': ZALO_APP_ID,
                                    'client_secret': ZALO_SECRET})
        zalo = {p['provider']: p for p in state}['zalo']
        steps = self._steps('zalo', zalo)
        self.assertEqual(steps['credentials']['status'], 'done')
        self.assertEqual(steps['create_app']['status'], 'done')
        self.assertEqual(self.App._get_for_provider('zalo').preflight_status,
                         'none', 'Zalo publishes no credentials-only check, '
                                 'so we do not pretend to run one')
        self.assertNotIn(ZALO_SECRET, json.dumps(state, default=str))

    # ==================================================================
    # T182 — one source of truth for the paperwork
    # ==================================================================
    def test_182_checklist_reads_the_declarations(self):
        self.assertNotIn('meta', PROVIDER_EXTERNAL_STEPS)
        self.assertNotIn('zalo', PROVIDER_EXTERNAL_STEPS)

        app = self.App.create({'provider': 'meta', 'client_id': META_APP_ID})
        html = str(app._render_go_live_checklist())
        for step in self.App._golive_steps()['meta']:
            self.assertIn('<li>%s</li>' % step['title'], html, step['key'])
        self.assertEqual(html.count('<li>'), 7)

        zalo = self.App.create({'provider': 'zalo', 'client_id': ZALO_APP_ID})
        zhtml = str(zalo._render_go_live_checklist())
        self.assertEqual(zhtml.count('<li>'), 5)

        # google keeps the old dict until GL-4 declares its steps.
        google = self.App.create({'provider': 'google'})
        ghtml = str(google._render_go_live_checklist())
        self.assertIn(PROVIDER_EXTERNAL_STEPS['google'][0], ghtml)
        self.assertEqual(ghtml.count('<li>'),
                         len(PROVIDER_EXTERNAL_STEPS['google']))


@tagged('post_install', '-at_install')
class TestGoliveHandshakeHttp(HttpCase):
    """T180–T181 — the handshake audit rows, written by the real routes.

    The proof a webhook step depends on is created inside a public controller,
    so it can only be tested by making the request. Both suites assert on
    DELTAS: ``care.channel.audit`` is append-only and a live deployment
    accumulates rows nobody may delete.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        # The default test user is the superuser, a member of NO group
        # (has_group checks real membership, not su — ledger §5.42).
        env.user.sudo().write({'group_ids': [
            (4, env.ref('base.group_system').id),
            (4, env.ref('health_crm.group_health_crm_manager').id)]})
        env['channel.platform.app'].sudo().with_context(
            active_test=False).search([]).write({'active': False})
        env['care.channel.connection'].sudo().with_context(
            active_test=False).search([]).write({'active': False})

        cls.Audit = env['care.channel.audit']
        cls.verify_token = 'gl1-verify-token-fixture'
        cls.meta_app = env['channel.platform.app'].create({
            'provider': 'meta', 'client_id': META_APP_ID,
            'extra_json': json.dumps({'verify_token': cls.verify_token})})
        cls.meta_app.action_set_secret(META_SECRET)

        cls.zalo_app = env['channel.platform.app'].create({
            'provider': 'zalo', 'client_id': ZALO_APP_ID})
        cls.zalo_app.action_set_secret(ZALO_SECRET)

    def _handshakes(self, channels):
        return self.Audit.sudo().search_count(
            [('event', '=', 'webhook_handshake'), ('channel', 'in', channels)])

    # ==================================================================
    # T180 — Meta's dashboard handshake, and only the success path
    # ==================================================================
    def test_180_meta_handshake_is_evidence(self):
        before = self._handshakes(['whatsapp', 'fb'])
        fb_before = self._handshakes(['fb'])
        query = urlencode({'hub.mode': 'subscribe',
                           'hub.verify_token': self.verify_token,
                           'hub.challenge': 'gl1-challenge-42'})
        resp = self.url_open('/care_channels/meta/whatsapp/webhook?%s' % query)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.text, 'gl1-challenge-42',
                         'the response bytes are what Meta checks — the audit '
                         'row must not change them')
        self.assertEqual(self._handshakes(['whatsapp', 'fb']), before + 1)
        row = self.Audit.sudo().search(
            [('event', '=', 'webhook_handshake')], limit=1)
        self.assertEqual(row.channel, 'whatsapp')
        self.assertNotIn(META_SECRET, row.detail_redacted or '')

        # A wrong guess stays an UNLOGGED 403: auditing refusals would make
        # this route an oracle for "is a verify token configured here".
        bad = urlencode({'hub.mode': 'subscribe',
                         'hub.verify_token': 'not-the-token',
                         'hub.challenge': 'gl1-challenge-99'})
        resp = self.url_open('/care_channels/meta/whatsapp/webhook?%s' % bad)
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.text, '')
        self.assertEqual(self._handshakes(['whatsapp', 'fb']), before + 1)

        # The other product writes its own row, under its own channel.
        resp = self.url_open('/care_channels/meta/fb/webhook?%s' % query)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self._handshakes(['fb']), fb_before + 1)

    # ==================================================================
    # T181 — Zalo has no handshake, so the first verified event is one
    # ==================================================================
    def test_181_zalo_first_event_only(self):
        env = self.env
        conn = env['care.channel.connection'].with_context(
            **{INTERNAL_CTX: True}).create({
                'channel': 'zalo', 'company_id': env.company.id,
                'state': 'testing', 'resource_external_id': ZALO_OA_ID})
        conn = env['care.channel.connection'].browse(conn.id)
        conn.action_set_secret('provider_secret', ZALO_WEBHOOK_SECRET)

        before = self._handshakes(['zalo'])
        calls = []
        original = CareChannelMessage._dispatch_zalo

        @wraps(original)
        def counting(self, connection, payload):
            calls.append(payload)
            return original(self, connection, payload)

        with patch.object(CareChannelMessage, '_dispatch_zalo', counting):
            first = self._post_zalo(b'{"oa_id":"%s","event_name":"user_send_'
                                    b'text","message":{"msg_id":"gl1-1"}}'
                                    % ZALO_OA_ID.encode())
            second = self._post_zalo(b'{"oa_id":"%s","event_name":"user_send_'
                                     b'text","message":{"msg_id":"gl1-2"}}'
                                     % ZALO_OA_ID.encode())

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(len(calls), 2,
                         'the handshake bookkeeping must not short-circuit '
                         'the dispatch of a real event')

        after = self._handshakes(['zalo'])
        expected = 1 if not before else 0
        self.assertEqual(after - before, expected,
                         'exactly one handshake row for the deployment — '
                         'every verified event would otherwise spam the audit')
        self.assertGreaterEqual(after, 1)

        # An unsigned event is the same bodyless 403 it always was, and it
        # proves nothing about anything.
        resp = self.url_open('/care_channels/zalo/webhook',
                             data=b'{"oa_id":"%s"}' % ZALO_OA_ID.encode(),
                             headers={'Content-Type': 'application/json'})
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.text, '')
        self.assertEqual(self._handshakes(['zalo']), after)

    def _post_zalo(self, raw, secret=ZALO_WEBHOOK_SECRET):
        ts = str(int(time.time() * 1000))
        mac = hashlib.sha256(ZALO_APP_ID.encode() + raw + ts.encode()
                             + secret.encode()).hexdigest()
        return self.url_open(
            '/care_channels/zalo/webhook', data=raw,
            headers={'Content-Type': 'application/json',
                     'X-ZEvent-Signature': 'mac=%s' % mac,
                     'X-ZEvent-Timestamp': ts})


@tagged('post_install', '-at_install')
class TestGoliveStudioUi(ChannelHubCase):
    """T183–T185, T187 — GL-2: the Studio's entry points and its bundle.

    None of this drives the component (that is the tour and the browser
    evidence pack). What it defends is everything a UI phase can silently lose
    between deploys: an action whose tag stops matching the registry line, a
    menu that loses its group, a CMS leaf that never gets seeded — the §5.69
    trap that made a whole phase deep-link-only — an asset line dropped from
    the bundle, and a stylesheet that fails to compile and takes every
    co-bundled module down with it (§5.68).
    """

    GOLIVE_ASSETS = (
        'health_care_command_channels/static/src/golive/golive_studio.css',
        'health_care_command_channels/static/src/golive/golive_studio.scss',
        'health_care_command_channels/static/src/golive/golive_studio.js',
        'health_care_command_channels/static/src/golive/golive_studio.xml',
    )

    # ==================================================================
    # T183 — the three entry points exist and point at the same tag
    # ==================================================================
    def test_183_entry_points(self):
        action = self.env.ref(
            'health_care_command_channels.action_channel_golive_studio')
        self.assertEqual(action._name, 'ir.actions.client')
        self.assertEqual(action.tag, 'channel_golive_studio')
        self.assertEqual(action.target, 'current')

        menu = self.env.ref(
            'health_care_command_channels.menu_channel_golive_studio')
        self.assertIn(self.env.ref('base.group_system'), menu.group_ids,
                      'the platform plane stays with the platform operator')
        self.assertEqual(menu.parent_id,
                         self.env.ref('health_care_command.menu_care_command_config'))

        # §5.69: a backend menuitem is NOT a reachable surface for the users
        # who live in the /bizapp shell. The sidebar leaf is part of "done".
        item = self.env.ref('health_care_command_channels.item_golive_studio')
        self.assertEqual(item.action_tag, 'channel_golive_studio')
        self.assertEqual(item.match_action_tags, 'channel_golive_studio')
        self.assertEqual(
            item.action_xmlid,
            'health_care_command_channels.action_channel_golive_studio')
        self.assertEqual(item.section_id,
                         self.env.ref('health_cms_sidebar.section_admin'))
        # §5.69(a): a leaf with a parent turns that parent into a
        # non-navigating accordion. This one is a sibling, explicitly.
        self.assertFalse(item.parent_id)
        # `cms.sidebar.item` declares no inverse One2many, so "has children"
        # is a search, not a field — and it is the thing that matters here.
        self.assertFalse(self.env['cms.sidebar.item'].with_context(
            active_test=False).search_count([('parent_id', '=', item.id)]))
        # §5.94: `match_models` in a last-wins index would steal the highlight
        # of the model's one primary surface (Platform Applications).
        self.assertFalse(item.match_models)

        # The raw form keeps its escape-hatch button, pointing at this action.
        arch = self.env.ref(
            'health_care_command_channels.view_channel_platform_app_form'
        ).get_combined_arch()
        self.assertIn('name="%d"' % action.id, arch)

    # ==================================================================
    # T184 — the bundle lines, in the order libsass needs them
    # ==================================================================
    def test_184_assets_are_bundled(self):
        manifest = get_manifest('health_care_command_channels')
        backend = list(manifest['assets']['web.assets_backend'])
        for path in self.GOLIVE_ASSETS:
            self.assertIn(path, backend, 'lost from web.assets_backend: %s' % path)

        # §5.51: the plain CSS carrying the data-URI mask icons must load
        # BEFORE the scss, or libsass mangles them.
        self.assertLess(backend.index(self.GOLIVE_ASSETS[0]),
                        backend.index(self.GOLIVE_ASSETS[1]))

        # The tour is only a test if it ships in the test bundle.
        self.assertIn('health_care_command_channels/static/tests/tours/**/*',
                      manifest['assets']['web.assets_tests'])

    # ==================================================================
    # T185 — the stylesheet really COMPILES, and does not take the bundle
    #        down with it if it does not (ledger §5.68)
    # ==================================================================
    def test_185_backend_css_carries_both_consoles(self):
        """Nothing else in this repo's suites compiles an asset bundle.

        §5.68 was paid for live: one CSS-native `min()` in a `.scss` made
        libsass fail the WHOLE bundle, which shipped every co-bundled module
        unstyled — with a single WARNING in the log and a green test run. The
        assertion that matters is the PAIR: our own selector AND a known-good
        sibling. Our selector alone could pass on a bundle that had lost
        everything else.
        """
        # `.css()` hands back the generated ir.attachment, not the text —
        # measured on vietuat: /web/assets/<hash>/web.assets_web.min.css,
        # 2.19 MB when the compilation is healthy, ~40 KB when it is not.
        bundle = self.env['ir.qweb']._get_asset_bundle(
            'web.assets_web', css=True, js=False, assets_params={})
        css = (bundle.css().raw or b'').decode('utf-8', 'replace')
        self.assertGreater(len(css), 500000,
                           'the backend CSS bundle collapsed — a scss file in '
                           'SOME module failed to compile (§5.68)')
        self.assertIn('.o_golive_studio', css,
                      'the Studio stylesheet did not reach the backend bundle')
        self.assertIn('.o_channel_center', css,
                      'a sibling stylesheet vanished — the whole scss '
                      'compilation failed, not just ours')
        # The mask icons live in the plain CSS and must survive verbatim.
        self.assertIn('ic-rocket', css)

    # ==================================================================
    # T187 — the Center is untouched (regression tripwire for the strip)
    # ==================================================================
    def test_187_channel_center_action_untouched(self):
        action = self.env.ref(
            'health_care_command_channels.action_channel_center')
        self.assertEqual(action.tag, 'channel_center')
        self.assertEqual(action.target, 'current')
        item = self.env.ref(
            'health_care_command_channels.item_channel_center')
        self.assertEqual(item.action_tag, 'channel_center')
        self.assertEqual(item.section_id,
                         self.env.ref('health_cms_sidebar.section_crm'))

        # The strip is the only new element, and it is bound to a probe that
        # can only succeed for an operator. Assert the shape structurally: the
        # template renders it under `state.golive` and nothing else.
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'static', 'src', 'center', 'channel_center.xml')
        with open(path, encoding='utf-8') as handle:
            template = handle.read()
        self.assertEqual(template.count('cc-golive-strip'), 1)
        self.assertIn('t-if="state.golive" class="cc-golive-strip"', template)


@tagged('post_install', '-at_install')
class TestGoliveStudioHttp(HttpCase):
    """T186, T188 — the Studio over HTTP.

    T186 needs no browser: what the refusal card renders is whatever
    `golive_state` answers a non-operator over the wire, and that is the thing
    worth pinning. T188 is the OWL tour and runs only where a Chrome binary
    exists — Odoo raises `unittest.SkipTest` otherwise, so a missing browser is
    reported as a skip and never as a pass (§5.83).
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        # §5.86: `admin/admin` is a fresh demo database's credentials, not
        # this one's. Own the users. A login of 8+ characters keeps
        # new_test_user's default password equal to the login.
        province = env['health.catchment.province'].search([], limit=1)
        extra = {'catchment_province_id': province.id} if province else {}
        cls.operator = new_test_user(
            env, login='gl2operator', groups='base.group_system,'
            'health_crm.group_health_crm_manager', **extra)
        cls.tenant = new_test_user(
            env, login='gl2manager',
            groups='health_crm.group_health_crm_manager', **extra)

    def _call_kw(self, method):
        return self.url_open(
            '/web/dataset/call_kw',
            data=json.dumps({
                'jsonrpc': '2.0', 'method': 'call',
                'params': {'model': 'channel.platform.app', 'method': method,
                           'args': [], 'kwargs': {}}}),
            headers={'Content-Type': 'application/json'})

    # ==================================================================
    # T186 — a non-operator is refused in words, over the wire
    # ==================================================================
    def test_186_non_operator_is_refused(self):
        self.authenticate('gl2manager', 'gl2manager')
        payload = self._call_kw('golive_state').json()
        self.assertNotIn('result', payload,
                         'a CRM manager must never receive the platform state')
        error = payload['error']['data']
        self.assertTrue(error['name'].endswith('UserError'),
                        'the component keys its honest refusal card on the '
                        'exception CLASS: %s' % error['name'])
        self.assertIn('platform administrator', error['message'])

        # ...and the operator gets the real thing on the same route.
        self.authenticate('gl2operator', 'gl2operator')
        payload = self._call_kw('golive_state').json()
        self.assertIn('result', payload, payload.get('error'))
        self.assertEqual([p['provider'] for p in payload['result']],
                         list(GOLIVE_PROVIDERS))

    # ==================================================================
    # T188 — the journey map renders and the Meta rail opens
    # ==================================================================
    def test_188_studio_tour(self):
        self.start_tour(
            '/odoo/action-health_care_command_channels.'
            'action_channel_golive_studio',
            'channel_golive_studio_tour', login='gl2operator')


# =====================================================================
# GL-3 — delegation invites
# =====================================================================
INVITE_EMAIL = 'console.owner@example.test'
INVITE_EMAIL_2 = 'the.other.one@example.test'
INVITE_VERIFY_TOKEN = 'gl3-verify-token-fixture'


def _fake_send(records, auto_commit=False, raise_exception=False,
               post_send_callback=None, sink=None):
    """Stand-in for ``mail.mail.send`` — a PLAIN FUNCTION, never an autospec
    mock (§5.76), and deliberately NOT unlinking the auto_delete row: the
    rendered body is the only place the token ever exists and the tests have to
    be able to read it back."""
    if sink is not None:
        sink.append(records)
    return True


@tagged('post_install', '-at_install')
class TestGoliveInvite(ChannelHubCase):
    """T189–T191, T195 — the invitation model and its two RPCs.

    The single claim under test: **the token is in the email and nowhere
    else.** Everything else here is what keeps that true — the rotation that
    means one live link per step, the send failure that takes its own
    invitation down with it, and the state payload that carries an operator's
    ledger without carrying a credential.
    """

    def setUp(self):
        super().setUp()
        self.env['ir.config_parameter'].sudo().set_param('web.base.url',
                                                         HTTPS_BASE)
        self.App.sudo().with_context(active_test=False).search([]).write(
            {'active': False})
        self.Invite = self.env['channel.golive.invite']
        self.Invite.sudo().with_context(active_test=False).search([]).write(
            {'active': False})

    # -- helpers -------------------------------------------------------
    def _mailbox(self):
        """``(sink, patcher)`` — the sink collects the mail.mail records."""
        sink = []

        def send(records, auto_commit=False, raise_exception=False,
                 post_send_callback=None):
            return _fake_send(records, sink=sink)

        return sink, patch.object(type(self.env['mail.mail']), 'send', send)

    def _live(self, provider='meta', step_key='webhooks'):
        return self.Invite.sudo().search(
            [('provider', '=', provider), ('step_key', '=', step_key),
             ('revoked', '=', False)])

    def _audits(self, event):
        return self.Audit.sudo().search_count([('event', '=', event)])

    @staticmethod
    def _token_from(mail):
        match = re.search(r'/channels/golive/([A-Za-z0-9_-]+)',
                          str(mail.body_html or ''))
        return match.group(1) if match else None

    # ==================================================================
    # T189 — everything that must be refused, is
    # ==================================================================
    def test_189_send_refusals(self):
        sink, patcher = self._mailbox()
        with patcher:
            # A non-operator: the platform plane stays with the platform
            # operator, and both new methods are RPC-reachable by name.
            with self.assertRaises(UserError):
                self.App.with_user(self.crm_mgr).golive_invite_send(
                    'meta', 'webhooks', INVITE_EMAIL)
            with self.assertRaises(UserError):
                self.App.with_user(self.crm_mgr).golive_invite_revoke(1)

            # A provider review is not somebody else's to finish.
            with self.assertRaises(ValidationError):
                self.App.golive_invite_send('meta', 'business_verification',
                                            INVITE_EMAIL)
            with self.assertRaises(ValidationError):
                self.App.golive_invite_send('meta', 'done', INVITE_EMAIL)

            # Unknown step, unknown provider.
            with self.assertRaises(ValidationError):
                self.App.golive_invite_send('meta', 'not_a_step', INVITE_EMAIL)
            with self.assertRaises(ValidationError):
                self.App.golive_invite_send('google', 'create_app', INVITE_EMAIL)

            # Addresses that are not addresses.
            for bad in ('', '   ', 'nobody', 'no@body', 'two@@at.com',
                        'has space@example.test', 'a@b.', 'a@.b', 'a' * 260):
                with self.assertRaises(ValidationError, msg=repr(bad)):
                    self.App.golive_invite_send('meta', 'webhooks', bad)

            # A revoke of nothing.
            with self.assertRaises(ValidationError):
                self.App.golive_invite_revoke(0)

        self.assertFalse(sink, 'not one refusal sent an email')
        self.assertFalse(
            self.Invite.sudo().with_context(active_test=False).search_count([]),
            'not one refusal created an invitation')

    # ==================================================================
    # T190 — one live link per step, and the token lives only in the email
    # ==================================================================
    def test_190_rotation_and_token_secrecy(self):
        sink, patcher = self._mailbox()
        with patcher:
            self.App.golive_invite_send('meta', 'webhooks', INVITE_EMAIL)

        invite = self._live()
        self.assertEqual(len(invite), 1)
        self.assertEqual(invite.email, INVITE_EMAIL)
        self.assertEqual(invite.invited_by_id, self.env.user)
        self.assertEqual(invite.view_count, 0)
        self.assertGreater(invite.expires_at, fields.Datetime.now())

        # The email carries the URL...
        self.assertEqual(len(sink), 1)
        mail = sink[0]
        self.assertEqual(mail.email_to, INVITE_EMAIL)
        self.assertIn(HTTPS_BASE, str(mail.body_html or ''))
        token = self._token_from(mail)
        self.assertTrue(token, 'the email must carry the link — it is the only '
                               'place the token exists at all')

        # ...and what the database holds is its DIGEST, not the token.
        self.assertEqual(len(invite.token_hash), 64)
        self.assertNotEqual(token, invite.token_hash)
        self.assertEqual(self.Invite._hash_token(token), invite.token_hash)

        # The token appears in NO stored column, NO audit row and NO RPC return.
        row = json.dumps(invite.sudo().read()[0], default=str)
        self.assertNotIn(token, row)
        for audit in self.Audit.sudo().search([('event', 'like', 'golive_invite')]):
            self.assertNotIn(token, audit.detail_redacted or '')
            self.assertNotIn(INVITE_EMAIL, audit.detail_redacted or '',
                             'the audit carries a masked address, never the '
                             'whole one')
        self.assertNotIn(token, json.dumps(self.App.golive_state(), default=str))

        # One audit row, saying what it was without saying the secret part.
        sent_audit = self.Audit.sudo().search(
            [('event', '=', 'golive_invite_sent')], limit=1)
        self.assertIn('meta/webhooks', sent_audit.detail_redacted)
        self.assertIn('c***@example.test', sent_audit.detail_redacted)

        # A re-send is a ROTATION, not a second key.
        sink2, patcher2 = self._mailbox()
        with patcher2:
            self.App.golive_invite_send('meta', 'webhooks', INVITE_EMAIL_2)
        both = self.Invite.sudo().search(
            [('provider', '=', 'meta'), ('step_key', '=', 'webhooks')],
            order='id asc')
        self.assertEqual(len(both), 2)
        self.assertTrue(both[0].revoked,
                        'the earlier link dies the moment a new one is sent')
        self.assertFalse(both[1].revoked)
        self.assertEqual(len(self._live()), 1)
        token2 = self._token_from(sink2[0])
        self.assertNotEqual(token, token2)
        self.assertNotEqual(both[0].token_hash, both[1].token_hash)

        # A different step is a different invitation, untouched by the rotation.
        sink3, patcher3 = self._mailbox()
        with patcher3:
            self.App.golive_invite_send('meta', 'create_app', INVITE_EMAIL)
        self.assertEqual(len(self._live('meta', 'create_app')), 1)
        self.assertEqual(len(self._live('meta', 'webhooks')), 1)

    # ==================================================================
    # T191 — a link nobody received must not stay live
    # ==================================================================
    def test_191_mail_failure_revokes_the_invite(self):
        before = self._audits('golive_invite_sent')

        def boom(records, auto_commit=False, raise_exception=False,
                 post_send_callback=None):
            raise MailDeliveryException('Unable to connect to SMTP Server')

        raised = False
        # try/except, never assertRaises: Odoo wraps assertRaises in a savepoint
        # and rolls back every write made before the raise (§5.8/§5.65) — which
        # is exactly the evidence this test exists to look at.
        with patch.object(type(self.env['mail.mail']), 'send', boom):
            try:
                self.App.golive_invite_send('meta', 'webhooks', INVITE_EMAIL)
            except UserError:
                raised = True
        self.assertTrue(raised, 'a send that failed must not read as a success')

        invites = self.Invite.sudo().search([('provider', '=', 'meta')])
        self.assertEqual(len(invites), 1)
        self.assertTrue(invites.revoked)
        self.assertFalse(self._live())
        self.assertEqual(self._audits('golive_invite_sent'), before,
                         'nothing went out, so nothing may claim it did')

    # ==================================================================
    # T195 — the state block, and revoke
    # ==================================================================
    def test_195_state_carries_invites(self):
        sink, patcher = self._mailbox()
        with patcher:
            state = self.App.golive_invite_send('meta', 'webhooks',
                                                INVITE_EMAIL)
        meta = {p['provider']: p for p in state}['meta']
        zalo = {p['provider']: p for p in state}['zalo']

        self.assertEqual(zalo['invites'], [],
                         'one provider\'s invitations are not another\'s')
        self.assertEqual(len(meta['invites']), 1)
        row = meta['invites'][0]
        for key in ('id', 'step_key', 'email', 'sent_on', 'expires_at',
                    'revoked', 'expired', 'view_count', 'last_viewed_at'):
            self.assertIn(key, row)
        self.assertEqual(row['step_key'], 'webhooks')
        self.assertEqual(row['email'], INVITE_EMAIL)
        self.assertFalse(row['revoked'])
        self.assertFalse(row['expired'])
        self.assertEqual(row['view_count'], 0)
        self.assertFalse(row['last_viewed_at'])

        # GL-1's payload is untouched — `invites` is purely additive.
        self.assertEqual(len(meta['steps']), 7)
        self.assertEqual(len(zalo['steps']), 5)

        # No token material of any kind reaches the Studio.
        invite = self.Invite.sudo().browse(row['id'])
        blob = json.dumps(state, default=str)
        self.assertNotIn(invite.token_hash, blob)
        self.assertNotIn(self._token_from(sink[0]), blob)

        # Revoke flips it, writes evidence, and is idempotent.
        before = self._audits('golive_invite_revoked')
        state = self.App.golive_invite_revoke(row['id'])
        meta = {p['provider']: p for p in state}['meta']
        self.assertEqual(len(meta['invites']), 1)
        self.assertTrue(meta['invites'][0]['revoked'])
        self.assertEqual(self._audits('golive_invite_revoked'), before + 1)
        self.App.golive_invite_revoke(row['id'])
        self.assertEqual(self._audits('golive_invite_revoked'), before + 1,
                         'revoking an already-revoked link is not a new event')

        # An expired row reports itself as expired without being revoked.
        invite.sudo().write({'revoked': False,
                             'expires_at': fields.Datetime.now()
                             - timedelta(minutes=1)})
        meta = {p['provider']: p for p in self.App.golive_state()}['meta']
        self.assertTrue(meta['invites'][0]['expired'])
        self.assertFalse(meta['invites'][0]['revoked'])

        # An invitation is revoked, never erased (ACL perm_unlink 0).
        access = self.env['ir.model.access'].sudo().search(
            [('model_id.model', '=', 'channel.golive.invite')])
        self.assertTrue(access)
        self.assertFalse(any(access.mapped('perm_unlink')),
                         'a link that was handed out is evidence')


@tagged('post_install', '-at_install')
class TestGoliveInvitePublic(HttpCase):
    """T192–T194 — the public page, which is the security surface of GL-3.

    Every assertion here is one of the D3 rails, and each rail is the reason a
    line of the controller is in the order it is in. The suite asserts on
    DELTAS (``care.channel.audit`` is append-only evidence a real deployment
    accumulates) and owns its own users (§5.86 — ``admin/admin`` is a fresh
    demo database's credentials, not this one's).
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.Invite = env['channel.golive.invite']
        cls.Audit = env['care.channel.audit']
        cls.App = env['channel.platform.app']
        cls.Icp = env['ir.config_parameter'].sudo()

        env.user.sudo().write({'group_ids': [
            (4, env.ref('base.group_system').id)]})
        cls.App.sudo().with_context(active_test=False).search([]).write(
            {'active': False})
        cls.Invite.sudo().with_context(active_test=False).search([]).write(
            {'active': False})

        province = env['health.catchment.province'].search([], limit=1)
        extra = {'catchment_province_id': province.id} if province else {}
        cls.operator = new_test_user(
            env, login='gl3operator', groups='base.group_system', **extra)

        cls.meta_app = cls.App.create({
            'provider': 'meta', 'client_id': META_APP_ID,
            'extra_json': json.dumps({'verify_token': INVITE_VERIFY_TOKEN})})
        cls.meta_app.action_set_secret(META_SECRET)
        cls.zalo_app = cls.App.create({'provider': 'zalo',
                                       'client_id': ZALO_APP_ID})

        # The public page speaks the SENDER's language, not the anonymous
        # visitor's, so every expectation below has to be resolved in that
        # language too — on a Vietnamese deployment the step copy comes back
        # translated and an English literal would red-light correct code
        # (§5.50's family: never assert on text a live setting can move).
        cls.sender_lang = cls.operator.lang or env.lang or 'en_US'
        cls.SenderApp = cls.App.with_context(lang=cls.sender_lang)

    def setUp(self):
        super().setUp()
        # §5.32: an HttpCase that moves a global config switch poisons every
        # later suite. Restore both counters whatever happens.
        self._rate_before = (self.Icp.get_param('gateway.rate_limit_per_min'),
                             self.Icp.get_param('gateway.rate_limit_burst'))
        self.addCleanup(self._restore_rate)

    def _restore_rate(self):
        for key, value in zip(('gateway.rate_limit_per_min',
                               'gateway.rate_limit_burst'), self._rate_before):
            if value:
                self.Icp.set_param(key, value)
            else:
                self.Icp.search([('key', '=', key)]).unlink()

    # -- helpers -------------------------------------------------------
    def _mk_invite(self, provider='meta', step_key='webhooks', **vals):
        token = secrets.token_urlsafe(32)
        values = {
            'provider': provider,
            'step_key': step_key,
            'email': INVITE_EMAIL,
            'token_hash': self.Invite._hash_token(token),
            'invited_by_id': self.operator.id,
            'expires_at': fields.Datetime.now() + timedelta(days=14),
        }
        values.update(vals)
        return self.Invite.sudo().create(values), token

    def _get(self, token):
        return self.url_open('/channels/golive/%s' % token)

    def _audits(self, event):
        return self.Audit.sudo().search_count([('event', '=', event)])

    # ==================================================================
    # T192 — the page a colleague opens, and every rail on it
    # ==================================================================
    def test_192_public_page_and_its_rails(self):
        invite, token = self._mk_invite()
        expires_before = invite.expires_at
        views_before = self._audits('golive_invite_viewed')

        resp = self._get(token)
        self.assertEqual(resp.status_code, 200)
        body = resp.text

        # -- the step's own words, and the values it says to copy ----------
        step = self.SenderApp._golive_step('meta', 'webhooks')
        self.assertIn(str(escape(step['title'])), body)
        self.assertIn(str(escape(step['body'][:40])), body)
        self.assertIn(INVITE_VERIFY_TOKEN, body)
        self.assertIn('/care_channels/meta/whatsapp/webhook', body)
        self.assertIn('/care_channels/meta/fb/webhook', body)
        self.assertIn('/channel_hub/oauth/callback/meta', body)
        # ...and the console deep link, resolved with the real app id.
        self.assertIn('developers.facebook.com/apps/%s/webhooks' % META_APP_ID,
                      body)
        self.assertIn('rel="noopener noreferrer"', body)

        # -- NOTHING to type back ------------------------------------------
        self.assertNotIn('<input', body.lower(),
                         'an input on an unauthenticated page is a credential '
                         'form wearing our chrome')
        self.assertNotIn('<form', body.lower())

        # -- and no secret material anywhere -------------------------------
        for forbidden in (META_SECRET, 'chs$1$', 'client_secret',
                          self.meta_app.sudo().client_secret_enc or 'chs$1$'):
            self.assertNotIn(forbidden, body,
                             'no credential material may reach a public page')

        # -- headers: not indexed, not cached, and no Referer to the console
        self.assertIn('noindex', resp.headers.get('X-Robots-Tag', ''))
        self.assertIn('no-referrer', resp.headers.get('Referrer-Policy', ''))
        self.assertIn('no-store', resp.headers.get('Cache-Control', ''))
        self.assertNotIn('set-cookie', {k.lower() for k in resp.headers})
        self.assertFalse(resp.cookies, 'a public page needs no session at all')

        # -- the receipt: exactly one view, one audit row, no new expiry ----
        invite.invalidate_recordset()
        self.assertEqual(invite.view_count, 1)
        self.assertTrue(invite.last_viewed_at)
        self.assertEqual(invite.expires_at, expires_before,
                         'a link that renewed itself on every open would '
                         'never expire')
        self.assertEqual(self._audits('golive_invite_viewed'),
                         views_before + 1)
        audit = self.Audit.sudo().search(
            [('event', '=', 'golive_invite_viewed')], order='id desc', limit=1)
        self.assertIn('meta/webhooks', audit.detail_redacted)
        self.assertNotIn(token, audit.detail_redacted)

        # A second open is a second view and a second row — and still nothing
        # else moves.
        self._get(token)
        invite.invalidate_recordset()
        self.assertEqual(invite.view_count, 2)
        self.assertEqual(self._audits('golive_invite_viewed'),
                         views_before + 2)

        # A step whose verify token has NOT been minted says so rather than
        # minting one: a public route must never write configuration.
        self.meta_app.sudo().write({'extra_json': json.dumps({})})
        fresh, fresh_token = self._mk_invite()
        body = self._get(fresh_token).text
        notes = [block['note'] for block
                 in self.SenderApp.sudo()._golive_invite_values(fresh)['blocks']
                 if block['note']]
        self.assertTrue(notes, 'a missing verify token must say so in words')
        self.assertIn(str(escape(notes[0])), body)
        self.assertNotIn(INVITE_VERIFY_TOKEN, body)
        self.assertEqual(json.loads(self.meta_app.sudo().extra_json or '{}'), {},
                         'the page must not have minted anything')
        self.meta_app.sudo().write(
            {'extra_json': json.dumps({'verify_token': INVITE_VERIFY_TOKEN})})

    # ==================================================================
    # T193 — the non-oracle: four causes, one answer
    # ==================================================================
    def test_193_four_identical_dead_ends(self):
        expired, expired_token = self._mk_invite(
            step_key='create_app',
            expires_at=fields.Datetime.now() - timedelta(days=1))
        revoked, revoked_token = self._mk_invite(step_key='config_ids',
                                                 revoked=True)
        archived, archived_token = self._mk_invite(provider='zalo',
                                                   step_key='oauth_redirect')
        self.zalo_app.sudo().write({'active': False})
        bogus_token = secrets.token_urlsafe(32)

        views_before = self._audits('golive_invite_viewed')
        cases = [('unknown token', bogus_token),
                 ('expired invitation', expired_token),
                 ('revoked invitation', revoked_token),
                 ('archived platform application', archived_token)]
        bodies, statuses = [], []
        for _label, token in cases:
            resp = self._get(token)
            bodies.append(resp.text)
            statuses.append(resp.status_code)

        digests = {hashlib.sha256(b.encode('utf-8')).hexdigest()
                   for b in bodies}
        _logger.info(
            'GL3-NONORACLE: %s responses (%s) -> %s distinct status %s, '
            '%s distinct body sha256 %s',
            len(bodies), ', '.join(label for label, _t in cases),
            len(set(statuses)), sorted(set(statuses)), len(digests),
            sorted(digests))
        self.assertEqual(set(statuses), {200},
                         'a different status is an oracle by itself')
        self.assertEqual(len(digests), 1,
                         'four causes must be one answer, byte for byte')
        self.assertIn('no longer available', bodies[0])
        # It says nothing about anything.
        for token in (expired_token, revoked_token, archived_token,
                      bogus_token):
            self.assertNotIn(token, bodies[0])
        # ("meta" is excluded on purpose — every HTML head has <meta charset>.)
        for word in ('expired', 'revoked', 'archived', 'invitation', 'zalo',
                     'facebook', 'webhook'):
            self.assertNotIn(word, bodies[0].lower())

        # ...and none of them moved anything.
        self.assertEqual(self._audits('golive_invite_viewed'), views_before)
        for invite in (expired, revoked, archived):
            invite.invalidate_recordset()
            self.assertEqual(invite.view_count, 0)
            self.assertFalse(invite.last_viewed_at)
        self.zalo_app.sudo().write({'active': True})

    # ==================================================================
    # T194 — guessing costs more than it can win
    # ==================================================================
    def test_194_rate_limit_fires_before_the_lookup(self):
        invite, token = self._mk_invite(step_key='create_app')
        self.assertEqual(self._get(token).status_code, 200)
        invite.invalidate_recordset()
        self.assertEqual(invite.view_count, 1)

        # One request per minute is enough to prove the gate; the deployment
        # default is 120 and hammering it in a test buys nothing.
        self.Icp.set_param('gateway.rate_limit_per_min', '1')
        self.Icp.set_param('gateway.rate_limit_burst', '1')

        blocked = False
        for _attempt in range(4):
            invite.invalidate_recordset()
            views_before = invite.view_count
            audits_before = self._audits('golive_invite_viewed')
            resp = self._get(token)
            self.assertEqual(resp.status_code, 200)
            if 'no longer available' in resp.text:
                blocked = True
                # The rate limit runs BEFORE the lookup: a VALID token gets the
                # dead end and the row it points at is never touched.
                invite.invalidate_recordset()
                self.assertEqual(invite.view_count, views_before)
                self.assertEqual(self._audits('golive_invite_viewed'),
                                 audits_before)
                break
        self.assertTrue(blocked, 'the rate limit never fired')

        # Restored (addCleanup also does it) — and the same token works again.
        self._restore_rate()
        title = self.SenderApp._golive_step('meta', 'create_app')['title']
        self.assertIn(str(escape(title)), self._get(token).text)
