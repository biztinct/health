# -*- coding: utf-8 -*-
"""H01–H07 — the two public call-back addresses, over real HTTP.

The whole point of this module is what the route DOES before any model code
runs: it must hand a call to somebody else without the supplier noticing, and
it must degrade into the system that was already there for everything else —
including the flat refusal that stops this address being an oracle for which
clinics live behind the platform. A model-level test proves neither, so these
are HttpCase.

``relay.forward`` is patched throughout. It is the one line that leaves this
process, and a test that really posted to loopback would either hit the
developer's own machine or hang for eight seconds per case.
"""
import json
from unittest.mock import patch
from urllib.parse import urlencode

from odoo.tests import HttpCase, tagged

CDR_URL = '/voip24h/v3/cdr/%s/%s'
EVENTS_URL = '/voip24h/v3/events/%s/%s'
FORWARD = 'odoo.addons.biz_platform_voip_relay.services.relay.forward'

# A short name with `relay` in it can never be a clinic's web address, so a
# fixture can never collide with the row the relay wrote for a live customer.
SLUG = 'vrelayhttp'
TENANT_RECEIVER = 'RecvOfHttpCustomer1'
TENANT_TOKEN = 'a-token-only-the-customer-can-check'


@tagged('post_install', '-at_install')
class TestRelayRoutesHttp(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        # §5.42: the superuser is a member of NO group.
        env.user.sudo().write({'group_ids': [
            (4, env.ref('base.group_system').id)]})
        # §5.95: the deployment's own rows would take the unique indexes this
        # suite's fixtures need, and would route real traffic during it.
        env['voip.relay.tenant'].sudo().with_context(
            active_test=False).search([]).write({'active': False})
        env['voip.config'].sudo().with_context(
            active_test=False).search([]).write({'active': False})
        if 'biz.tenant' in env:
            env['biz.tenant'].sudo().search([]).write({'state': 'draft'})

        cls.config = env['voip.config'].create({
            'name': 'Relay HTTP fixture',
            'account_id': 'ACC-RELAY-HTTP',
            'company_id': env.company.id,
            'provider_timezone': 'Asia/Ho_Chi_Minh',
            'cdr_ingest_enabled': True,
            'state_ingest_enabled': True,
        })
        cls.config._ensure_receiver()
        cls.local_receiver = cls.config.receiver_id
        cls.local_token = cls.config.sudo()._voip_secret_read('cdr_token')

        cls.tenant = env['voip.relay.tenant'].sudo().create({
            'slug': SLUG, 'name': 'HTTP fixture customer'})
        env['voip.relay.route'].sudo().create({
            'tenant_id': cls.tenant.id, 'kind': 'receiver',
            'key': TENANT_RECEIVER})

    # ------------------------------------------------------------------
    def test_01_a_customers_call_is_handed_over(self):
        """The supplier gets the customer's own answer, not the platform's."""
        seen = {}

        def fake_forward(env, host, delivery):
            seen.update({'host': host, 'delivery': delivery})
            return 200, '{"status":"accepted"}'

        with patch(FORWARD, fake_forward):
            response = self.url_open(
                (CDR_URL % (TENANT_RECEIVER, TENANT_TOKEN))
                + '?' + urlencode({'id': '9001', 'callid': 'c-9001'}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'accepted'})
        self.assertTrue(seen['host'].startswith(SLUG + '.'),
                        'handed to that customer and nobody else')

    def test_02_the_token_is_forwarded_untouched(self):
        """The platform never reads, stores or re-mints a customer's token."""
        seen = {}

        def fake_forward(env, host, delivery):
            seen.update(delivery)
            return 200, '{"status":"accepted"}'

        with patch(FORWARD, fake_forward):
            self.url_open((CDR_URL % (TENANT_RECEIVER, TENANT_TOKEN))
                          + '?id=9002')
        self.assertEqual(seen['path'],
                         CDR_URL % (TENANT_RECEIVER, TENANT_TOKEN))
        self.assertEqual(seen['query'], 'id=9002')

    def test_03_a_posted_body_survives_the_hand_over(self):
        seen = {}
        payload = {'id': '9003', 'callid': 'c-9003', 'did': '02873001111'}

        def fake_forward(env, host, delivery):
            seen.update(delivery)
            return 200, '{"status":"accepted"}'

        with patch(FORWARD, fake_forward):
            response = self.url_open(
                CDR_URL % (TENANT_RECEIVER, TENANT_TOKEN),
                data=json.dumps(payload),
                headers={'Content-Type': 'application/json'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(seen['method'], 'POST')
        self.assertEqual(json.loads(seen['body']), payload)

    def test_04_a_customers_refusal_reaches_the_supplier(self):
        with patch(FORWARD, return_value=(403, '{"status":"denied"}')):
            response = self.url_open(
                (CDR_URL % (TENANT_RECEIVER, TENANT_TOKEN)) + '?id=9004')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {'status': 'denied'})

    def test_05_an_address_nobody_answers_to_is_refused_flatly(self):
        """Identical to a wrong token, so this is not an oracle."""
        unknown = self.url_open(
            (CDR_URL % ('NoSuchReceiverAtAll1', 'x' * 20)) + '?id=9005')
        wrong_token = self.url_open(
            (CDR_URL % (self.local_receiver, 'x' * 20)) + '?id=9005')
        self.assertEqual(unknown.status_code, 403)
        self.assertEqual(wrong_token.status_code, 403)
        self.assertEqual(unknown.json(), wrong_token.json())

    def test_06_this_systems_own_calls_are_still_handled_here(self):
        """The relay must be invisible to the clinic the platform itself runs."""
        Event = self.env['voip.call.event'].sudo()
        before = Event.search_count([('voip_config_id', '=', self.config.id)])
        response = self.url_open(
            (CDR_URL % (self.local_receiver, self.local_token)) + '?'
            + urlencode({'id': '9006', 'callid': 'c-9006', 'type': 'Inbound',
                         'disposition': 'ANSWERED',
                         'calldate': '2026-09-17 09:25:50',
                         'src': '0977700001', 'dst': '531',
                         'billsec': '121', 'duration': '129'}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get('status'), 'accepted')
        self.assertEqual(
            Event.search_count([('voip_config_id', '=', self.config.id)]),
            before + 1, 'it landed in this system, not somebody else\'s')

    def test_07_an_oversized_call_back_is_refused_before_any_lookup(self):
        response = self.url_open(
            (CDR_URL % (TENANT_RECEIVER, TENANT_TOKEN))
            + '?id=9007&pad=' + ('x' * (33 * 1024)))
        self.assertEqual(response.status_code, 413)

    def test_08_the_live_events_address_relays_too(self):
        seen = {}

        def fake_forward(env, host, delivery):
            seen.update(delivery)
            return 200, '{"status":"accepted"}'

        with patch(FORWARD, fake_forward):
            response = self.url_open(
                (EVENTS_URL % (TENANT_RECEIVER, TENANT_TOKEN))
                + '?' + urlencode({'uniqueid': 'u-9008', 'state': 'ring',
                                   'extend': '531'}))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(seen['path'].startswith('/voip24h/v3/events/'))
