# -*- coding: utf-8 -*-
"""T16–T17 — the two public routes, over real HTTP.

The whole point of both of them is what the route DOES before any model code
runs — a signature check on raw bytes, and a redirect that must never be
reachable by anything but the platform's own customer list. A model-level test
proves neither, so these are HttpCase.

They assert on DELTAS: ``care.channel.audit`` is append-only evidence and a
real platform accumulates rows nobody may delete (§5.50/§5.95). Requests run on
a ``TestCursor``, so everything they write rolls back with the class.
"""
import hashlib
import hmac
import json
from unittest.mock import patch
from urllib.parse import urlencode

from odoo.tests import HttpCase, tagged

from odoo.addons.biz_platform_channel_relay.services import relay

from .common import (
    FakeResponse, META_APP_ID, META_SECRET, PAGE_UNKNOWN, PAGE_X, VERIFY_TOKEN,
    fb_payload,
)

WEBHOOK_URL = '/care_channels/meta/fb/webhook'
CALLBACK_URL = '/channel_hub/oauth/callback/meta'


@tagged('post_install', '-at_install')
class TestRelayRoutesHttp(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        # §5.42: the superuser is a member of NO group; §5.95: the deployment's
        # own rows would take the unique indexes this suite's fixtures need.
        env.user.sudo().write({'group_ids': [
            (4, env.ref('base.group_system').id)]})
        env['channel.platform.app'].sudo().with_context(
            active_test=False).search([]).write({'active': False})
        env['care.channel.connection'].sudo().with_context(
            active_test=False).search([]).write({'active': False})
        env['channel.relay.tenant'].sudo().with_context(
            active_test=False).search([]).write({'active': False})

        cls.Audit = env['care.channel.audit']
        cls.Capture = env['care.contact.capture']
        cls.meta_app = env['channel.platform.app'].create({
            'provider': 'meta', 'client_id': META_APP_ID,
            'extra_json': json.dumps({'verify_token': VERIFY_TOKEN})})
        cls.meta_app.action_set_secret(META_SECRET)

        cls.tenant = env['channel.relay.tenant'].sudo().create(
            {'slug': 'hhh', 'name': 'HHH Clinic'})
        env['channel.relay.route'].sudo().create({
            'tenant_id': cls.tenant.id, 'channel': 'fb',
            'resource_external_id': PAGE_X})

    def _audit(self, event):
        return self.Audit.sudo().search_count([('event', '=', event)])

    @staticmethod
    def _sign(body):
        return 'sha256=' + hmac.new(META_SECRET.encode(), body,
                                    hashlib.sha256).hexdigest()

    # ==================================================================
    # T16 — the platform's webhook: verify, split, hand on. Always 200.
    # ==================================================================
    def test_16_webhook_forwards_a_routed_page(self):
        sent = []

        def fake_post(url, data=None, headers=None, timeout=None, **kwargs):
            sent.append({'url': url, 'data': data, 'headers': headers})
            return FakeResponse(200)

        body = json.dumps(fb_payload(PAGE_X)).encode()
        before = self._audit('relay_forwarded')
        with patch.object(relay.requests, 'post', fake_post):
            resp = self.url_open(
                WEBHOOK_URL, data=body,
                headers={'Content-Type': 'application/json',
                         'X-Hub-Signature-256': self._sign(body)})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(sent), 1)
        forwarded = json.loads(sent[0]['data'])
        self.assertEqual([e['id'] for e in forwarded['entry']], [PAGE_X])
        self.assertEqual(sent[0]['headers']['Host'], self.tenant.host)
        self.assertEqual(self._audit('relay_forwarded'), before + 1)

        # A batch nobody signed is refused before anything is read.
        sent.clear()
        with patch.object(relay.requests, 'post', fake_post):
            bad = self.url_open(
                WEBHOOK_URL, data=body,
                headers={'Content-Type': 'application/json',
                         'X-Hub-Signature-256': 'sha256=' + '0' * 64})
        self.assertEqual(bad.status_code, 403)
        self.assertEqual(bad.text, '')
        self.assertFalse(sent, 'nothing leaves this machine unverified')

    def test_16b_unknown_page_is_200_and_captured(self):
        body = json.dumps(fb_payload(PAGE_UNKNOWN)).encode()
        before = self.Capture.sudo().search_count(
            [('resource_external_id', '=', PAGE_UNKNOWN)])
        resp = self.url_open(
            WEBHOOK_URL, data=body,
            headers={'Content-Type': 'application/json',
                     'X-Hub-Signature-256': self._sign(body)})
        self.assertEqual(resp.status_code, 200,
                         'a page nobody owns is still answered 200 — an error '
                         'makes Meta redeliver the batch for every customer')
        self.assertEqual(
            self.Capture.sudo().search_count(
                [('resource_external_id', '=', PAGE_UNKNOWN)]), before + 1)

    # ==================================================================
    # T17 — one sign-in address for everybody, and an allowlist behind it
    # ==================================================================
    def test_17_sign_in_is_sent_home(self):
        before = self._audit('relay_routed_signin')
        query = urlencode({'code': 'CODE_FIXTURE', 'state': 'hhh~abc'})
        resp = self.url_open('%s?%s' % (CALLBACK_URL, query),
                             allow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        expected = '%s%s?%s' % (
            self.env['biz.tenants']._tenant_url('hhh'), CALLBACK_URL, query)
        self.assertEqual(resp.headers.get('Location'), expected,
                         'every parameter travels on verbatim — the ticket is '
                         'hashed at the far end and must not change')

        self.assertEqual(self._audit('relay_routed_signin'), before + 1)
        row = self.Audit.sudo().search(
            [('event', '=', 'relay_routed_signin')], limit=1)
        self.assertEqual(row.detail_redacted, 'hhh')
        self.assertNotIn('CODE_FIXTURE', row.detail_redacted or '')

    def test_17b_a_ticket_with_no_customer_is_handled_here(self):
        resp = self.url_open(
            '%s?%s' % (CALLBACK_URL, urlencode({'code': 'X', 'state': 'abc'})),
            allow_redirects=False)
        self.assertEqual(resp.status_code, 200,
                         'the platform\'s own sign-in is finished here')
        self.assertNotIn('abc', resp.text, 'and nothing is echoed back')

        resp = self.url_open(
            '%s?%s' % (CALLBACK_URL,
                       urlencode({'code': 'X', 'state': 'zzz~abc'})),
            allow_redirects=False)
        self.assertEqual(resp.status_code, 200,
                         'a short name nobody here relays for is not a '
                         'redirect — an open redirect on a sign-in callback '
                         'is a phishing primitive')
