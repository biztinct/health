# -*- coding: utf-8 -*-
"""T18–T19 — the customer half of the relay, and the seam it rides on.

T18 is this module's whole product: the short name reaches the sign-in ticket,
and nothing else about the ticket changes — same hash, same single use, same
expiry.

T19 belongs to the seam ``health_care_command_channels`` opened for R1 rather
than to this module's own code, and it lives here on purpose: it is a test of
behaviour that only exists once a relay is in play, and putting it here keeps
the sanctioned edit list (handover §6) to source files.
"""
import hashlib
import json
from unittest.mock import patch

from odoo.tests import tagged

from odoo.addons.health_care_command_channels.services.adapters import (
    CHANNEL_ADAPTERS, META_CALLBACK_PATH, OAUTH_REDIRECT_BASE_PARAM,
)
from odoo.addons.health_care_command_channels.tests.common import ChannelHubCase

SLUG_PARAM = 'biz_tenancy.slug'
PLATFORM = 'https://carejiox.test'
LOCAL = 'https://hhh.carejiox.test'

META_APP_ID = '1234567890123'
META_SECRET = 'relay-app-secret-r1-fixture'


@tagged('post_install', '-at_install')
class TestChannelRelayClient(ChannelHubCase):

    def setUp(self):
        super().setUp()
        self.icp = self.env['ir.config_parameter'].sudo()
        self.icp.set_param('web.base.url', LOCAL)
        self.conn = self._conn('fb', state='authorizing')

    # ==================================================================
    # T18 — the ticket carries this system's short name, and nothing else
    #       about it moves
    # ==================================================================
    def test_18_state_carries_the_short_name(self):
        self.icp.set_param(SLUG_PARAM, 'hhh')
        result = self.Session.create_for(self.conn, provider='meta')
        state = result['state']

        self.assertTrue(state.startswith('hhh~'),
                        'the platform learns whose sign-in this is from '
                        'here, and from nowhere else: %r' % state[:12])
        self.assertGreater(len(state.split('~', 1)[1]), 20,
                           'the ticket itself is untouched')

        session = self.Session.sudo().browse(result['session_id'])
        self.assertEqual(
            session.state_hash,
            hashlib.sha256(state.encode('utf-8')).hexdigest(),
            'the hash is of the WHOLE string — the far end hashes whatever '
            'comes back, so a prefix must be inside it')

        consumed = self.Session._consume(state)
        self.assertEqual(consumed, session)
        self.assertIsNone(self.Session._consume(state),
                          'still single use')

    def test_18b_no_short_name_no_prefix(self):
        self.icp.set_param(SLUG_PARAM, '')
        state = self.Session.create_for(self.conn, provider='meta')['state']
        self.assertNotIn('~', state,
                         'the platform\'s own sign-in is finished at home')

        self.icp.set_param(SLUG_PARAM, 'Bad Slug')
        state = self.Session.create_for(self.conn, provider='meta')['state']
        self.assertNotIn('~', state,
                         'anything that is not a short name is not routing')

    # ==================================================================
    # T19 — the sign-in return address follows the parameter, for Meta only
    # ==================================================================
    def test_19_redirect_uri_follows_the_platform(self):
        adapter = CHANNEL_ADAPTERS['fb'](self.env, self.conn)
        self.assertEqual(adapter._redirect_uri(), LOCAL + META_CALLBACK_PATH)

        self.icp.set_param(OAUTH_REDIRECT_BASE_PARAM, PLATFORM + '/')
        self.assertEqual(adapter._redirect_uri(), PLATFORM + META_CALLBACK_PATH,
                         'a trailing slash must not double up')

        app = self.App.create({'provider': 'meta', 'client_id': META_APP_ID})
        app.action_set_secret(META_SECRET)
        seen = {}

        def fake_get(self_adapter, url, *, params=None, headers=None):
            seen.update(params or {})
            return {'access_token': 'tok', 'expires_in': 0}

        with patch.object(type(adapter), '_get', fake_get):
            adapter.exchange_code('CODE_FIXTURE')
        self.assertEqual(seen.get('redirect_uri'),
                         PLATFORM + META_CALLBACK_PATH,
                         'Meta refuses an exchange whose return address is '
                         'not the one the code was issued for')

    def test_19b_only_meta_follows_it(self):
        self.icp.set_param(OAUTH_REDIRECT_BASE_PARAM, PLATFORM)
        meta = self.App.create({
            'provider': 'meta', 'client_id': META_APP_ID,
            'extra_json': json.dumps({'verify_token': 'x'})})
        zalo = self.App.create({'provider': 'zalo', 'client_id': '999'})

        self.assertEqual(meta.oauth_redirect_uri,
                         PLATFORM + META_CALLBACK_PATH)
        self.assertTrue(zalo.oauth_redirect_uri.startswith(LOCAL),
                        'no other provider is touched: %s'
                        % zalo.oauth_redirect_uri)
        self.assertTrue(meta.webhook_urls.count(LOCAL),
                        'and the webhook addresses are still THIS system\'s — '
                        'the platform is what Meta calls, and it forwards')

        redirect, _hooks = self.App._golive_urls('meta')
        self.assertEqual(redirect, PLATFORM + META_CALLBACK_PATH)
        redirect, _hooks = self.App._golive_urls('zalo')
        self.assertTrue(redirect.startswith(LOCAL))
