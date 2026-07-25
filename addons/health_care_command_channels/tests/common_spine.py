# -*- coding: utf-8 -*-
"""Shared CC-B fixtures: connections, canonical provider payloads, HTTP mocks.

TransactionCase only, like every other suite in this module (ledger §5.32).
Every provider payload below is a *simulated* one checked into the repository —
no test in this phase reaches a real provider, and no credential in it is real.
"""
import hashlib
import hmac
import json
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from .common import ChannelHubCase

META_APP_SECRET = 'meta-app-secret-fixture'
META_VERIFY_TOKEN = 'verify-token-fixture'
TG_PATH_SECRET = 'tg-path-secret-fixture-32chars-xx'
TG_BOT_TOKEN = '123456:bot-token-fixture'

WA_PHONE_ID = 'PHONE_ID_1'
WA_WABA_ID = 'WABA_1'
FB_PAGE_ID = 'PAGE_1'


class ChannelSpineCase(ChannelHubCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Identity = cls.env['care.channel.identity']
        cls.Message = cls.env['care.channel.message']
        cls.Care = cls.env['care.conversation']

        cls.meta_app = cls.App.create({
            'provider': 'meta', 'client_id': 'meta-app-1',
            'extra_json': json.dumps({'verify_token': META_VERIFY_TOKEN}),
        })
        cls.meta_app.action_set_secret(META_APP_SECRET)

    # -- connection fixtures -------------------------------------------
    def _ready(self, channel, **extra):
        """A connection that has actually proven itself: created in `testing`
        and driven to `ready` through the readiness model, never by asserting
        the state — that is the whole point of the framework."""
        conn = self._conn(channel, state='testing', **extra)
        self._seed_checks(conn)
        self.assertEqual(conn.state, 'ready')
        return conn

    def _wa_conn(self, company=None, phone_id=WA_PHONE_ID):
        conn = self._ready('whatsapp', company=company,
                           resource_external_id=phone_id,
                           resource_secondary_id=WA_WABA_ID)
        conn.action_set_secret('access_token', 'wa-access-token-fixture')
        return conn

    def _fb_conn(self, page_id=FB_PAGE_ID):
        conn = self._ready('fb', resource_external_id=page_id)
        conn.action_set_secret('access_token', 'fb-page-token-fixture')
        return conn

    def _tg_conn(self, path_secret=TG_PATH_SECRET):
        conn = self._ready('telegram', resource_external_id='bot1',
                           webhook_path_secret=path_secret)
        conn.action_set_secret('provider_secret', TG_BOT_TOKEN)
        return conn

    def _wc_conn(self, greeting='Xin chào! Chúng tôi có thể giúp gì?'):
        conn = self._ready('webchat', resource_external_id='default')
        conn.set_settings({'greeting': greeting,
                           'allowed_origins': ['https://tenant.example']})
        return conn

    # -- canonical simulated payloads ----------------------------------
    @staticmethod
    def wa_payload(wa_id='84901234567', mid='wamid.FIXTURE1',
                   text='Xin chào, tôi cần đặt lịch', name='Chị Lan',
                   phone_id=WA_PHONE_ID, ts=1769000000):
        """WhatsApp Cloud API `messages` webhook, trimmed to what we read."""
        return {
            'object': 'whatsapp_business_account',
            'entry': [{
                'id': WA_WABA_ID,
                'changes': [{
                    'field': 'messages',
                    'value': {
                        'messaging_product': 'whatsapp',
                        'metadata': {'display_phone_number': '842471000000',
                                     'phone_number_id': phone_id},
                        'contacts': [{'profile': {'name': name},
                                      'wa_id': wa_id}],
                        'messages': [{
                            'from': wa_id, 'id': mid, 'timestamp': str(ts),
                            'type': 'text', 'text': {'body': text},
                        }],
                    },
                }],
            }],
        }

    @staticmethod
    def wa_status_payload(mid='wamid.FIXTURE1', status='delivered',
                          phone_id=WA_PHONE_ID, ts=1769000060):
        return {
            'object': 'whatsapp_business_account',
            'entry': [{
                'id': WA_WABA_ID,
                'changes': [{
                    'field': 'messages',
                    'value': {
                        'messaging_product': 'whatsapp',
                        'metadata': {'phone_number_id': phone_id},
                        'statuses': [{'id': mid, 'status': status,
                                      'timestamp': str(ts),
                                      'recipient_id': '84901234567'}],
                    },
                }],
            }],
        }

    @staticmethod
    def fb_payload(psid='PSID_1', mid='m_fixture1', text='Hello there',
                   page_id=FB_PAGE_ID, ts=1769000000000):
        return {
            'object': 'page',
            'entry': [{
                'id': page_id, 'time': ts,
                'messaging': [{
                    'sender': {'id': psid},
                    'recipient': {'id': page_id},
                    'timestamp': ts,
                    'message': {'mid': mid, 'text': text},
                }],
            }],
        }

    @staticmethod
    def tg_payload(chat_id=555001, message_id=11, text='chào bạn',
                   first_name='Minh', ts=1769000000):
        return {
            'update_id': 900001,
            'message': {
                'message_id': message_id,
                'from': {'id': chat_id, 'is_bot': False,
                         'first_name': first_name},
                'chat': {'id': chat_id, 'first_name': first_name,
                         'type': 'private'},
                'date': ts,
                'text': text,
            },
        }

    # -- helpers --------------------------------------------------------
    @staticmethod
    def meta_signature(raw_body, secret=META_APP_SECRET):
        return 'sha256=' + hmac.new(secret.encode(), raw_body,
                                    hashlib.sha256).hexdigest()

    @staticmethod
    def raw(payload):
        return json.dumps(payload).encode()

    @contextmanager
    def mock_post(self, response=None, status=200, exc=None):
        """Patch the ONE place adapters do HTTP. No test ever leaves the box."""
        with self._mock_http('post', response, status, exc) as mocked:
            yield mocked

    @contextmanager
    def mock_get(self, response=None, status=200, exc=None):
        """Same, for the credential-validation calls (Telegram ``getMe``)."""
        with self._mock_http('get', response, status, exc) as mocked:
            yield mocked

    @contextmanager
    def _mock_http(self, verb, response=None, status=200, exc=None):
        target = ('odoo.addons.health_care_command_channels.services.'
                  'adapters.requests.%s' % verb)
        if exc is not None:
            with patch(target, side_effect=exc) as mocked:
                yield mocked
            return
        reply = MagicMock()
        reply.status_code = status
        reply.text = json.dumps(response or {})
        reply.json.return_value = response or {}
        with patch(target, return_value=reply) as mocked:
            yield mocked

    def conv_of(self, identity):
        return self.Care.sudo().search(
            [('channel_identity_id', '=', identity.id)])

    def identity_of(self, connection, external_id):
        return self.Identity.sudo().search([
            ('connection_id', '=', connection.id),
            ('external_id', '=', external_id)], limit=1)
