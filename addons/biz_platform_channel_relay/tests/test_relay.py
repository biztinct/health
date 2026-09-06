# -*- coding: utf-8 -*-
"""T1–T15 — the relay's routing, queue and reconcile, without a second box.

Two things are being proved over and over, and everything else is plumbing:

* **no clinic's traffic ever reaches another clinic's system** (T1–T6), and
* **a customer that cannot be reached costs Meta nothing** (T7–T11) — the
  failure becomes ours to retry, never an error code that makes Meta redeliver
  the batch for everybody.

Every provider call is a plain function (ledger §5.76 — a second ``autospec``
patch silently stops binding ``self``), and every cross-database seam
(``_pg_cursor``, ``_tenant_env``) is stood in for, because a second cursor
cannot see this transaction's rows at all (ledger §5.63).
"""
import hashlib
import hmac
import json
from contextlib import contextmanager
from datetime import timedelta
from unittest.mock import patch

import requests

from odoo import fields
from odoo.tests import tagged

from odoo.addons.health_care_command_channels.models.care_channel_message import (
    CareChannelMessage,
)
from odoo.addons.health_care_command_channels.services import channel_crypto
from odoo.addons.biz_platform_channel_relay.models.relay_delivery import (
    BACKOFF, MAX_ATTEMPTS,
)
from odoo.addons.biz_platform_channel_relay.models.relay_tenant import (
    ChannelRelayTenant, REDIRECT_BASE_PARAM,
)
from odoo.addons.biz_platform_channel_relay.services import relay

from .common import (
    FakeCursor, FakeResponse, META_APP_ID, META_SECRET, PAGE_LOCAL, PAGE_UNKNOWN,
    PAGE_X, PAGE_Y, PHONE_1, PHONE_2, RelayCase, fb_payload, wa_payload,
)


def _pg_cursor_returning(rows_by_slug):
    """A stand-in for ``biz.tenants._pg_cursor``. A PLAIN function (§5.76)."""
    @contextmanager
    def fake(self, dbname='postgres'):
        yield FakeCursor(rows_by_slug.get(dbname))
    return fake


@tagged('post_install', '-at_install')
class TestRelaySplit(RelayCase):
    """T1–T3 — the boundary, as a pure function."""

    def _classify(self, owners):
        def classify(resource_id):
            return owners.get(resource_id, (relay.UNKNOWN, None))
        return classify

    # ==================================================================
    # T1 — Messenger: three pages, three owners, three sub-payloads
    # ==================================================================
    def test_01_split_fb_three_owners(self):
        payload = fb_payload(PAGE_LOCAL, PAGE_X, PAGE_UNKNOWN)
        original = json.dumps(payload, sort_keys=True)
        buckets = relay.split_payload(
            'fb', payload, self._classify({
                PAGE_LOCAL: (relay.LOCAL, None),
                PAGE_X: (relay.TENANT, 'tenx'),
            }))

        self.assertEqual(len(buckets['local']['entry']), 1)
        self.assertEqual(buckets['local']['entry'][0]['id'], PAGE_LOCAL)
        self.assertEqual(len(buckets['unknown']['entry']), 1)
        self.assertEqual(buckets['unknown']['entry'][0]['id'], PAGE_UNKNOWN)
        self.assertEqual(list(buckets['tenants']), ['tenx'])
        self.assertEqual(len(buckets['tenants']['tenx']['entry']), 1)
        self.assertEqual(buckets['tenants']['tenx']['entry'][0]['id'], PAGE_X)

        for sub in (buckets['local'], buckets['unknown'],
                    buckets['tenants']['tenx']):
            self.assertEqual(sub['object'], 'page',
                             'the batch kind travels with every share')
        self.assertEqual(json.dumps(payload, sort_keys=True), original,
                         'the caller still holds the original, untouched')

    # ==================================================================
    # T2 — WhatsApp: ONE entry, two numbers, two customers
    # ==================================================================
    def test_02_split_whatsapp_splits_changes(self):
        payload = wa_payload(PHONE_1, PHONE_2)
        self.assertEqual(len(payload['entry']), 1)
        self.assertEqual(len(payload['entry'][0]['changes']), 2)

        buckets = relay.split_payload(
            'whatsapp', payload, self._classify({
                PHONE_1: (relay.TENANT, 'tenx'),
                PHONE_2: (relay.TENANT, 'teny'),
            }))
        self.assertEqual(sorted(buckets['tenants']), ['tenx', 'teny'])
        for slug, mine, theirs in (('tenx', PHONE_1, PHONE_2),
                                   ('teny', PHONE_2, PHONE_1)):
            sub = buckets['tenants'][slug]
            self.assertEqual(len(sub['entry']), 1)
            changes = sub['entry'][0]['changes']
            self.assertEqual(len(changes), 1, 'one change, not two')
            self.assertEqual(
                changes[0]['value']['metadata']['phone_number_id'], mine)
            blob = json.dumps(sub)
            self.assertNotIn(theirs, blob,
                             'the other clinic\'s number must not be in here')
            self.assertNotIn('wamid_%s' % theirs, blob,
                             'and neither must their messages')

    # ==================================================================
    # T3 — an entry whose every change belongs elsewhere is DROPPED
    # ==================================================================
    def test_03_entry_with_no_surviving_change_is_dropped(self):
        payload = wa_payload(PHONE_1, PHONE_2)
        buckets = relay.split_payload(
            'whatsapp', payload, self._classify({
                PHONE_1: (relay.TENANT, 'tenx'),
                PHONE_2: (relay.TENANT, 'tenx'),
            }))
        # Both belong to one customer, so nobody else gets an entry at all —
        # not an entry with an empty `changes` list.
        self.assertIsNone(buckets['local'])
        self.assertIsNone(buckets['unknown'])
        self.assertEqual(list(buckets['tenants']), ['tenx'])

        buckets = relay.split_payload(
            'whatsapp', payload, self._classify({
                PHONE_1: (relay.TENANT, 'tenx'),
            }))
        for sub in (buckets['tenants']['tenx'], buckets['unknown']):
            for entry in sub['entry']:
                self.assertTrue(entry['changes'],
                                'an entry with no changes is not an entry')


@tagged('post_install', '-at_install')
class TestRelayRouting(RelayCase):
    """T4–T8 — the routing decision and what it does with each share."""

    def setUp(self):
        super().setUp()
        self.sent = []

        def fake_post(url, data=None, headers=None, timeout=None, **kwargs):
            self.sent.append({'url': url, 'data': data, 'headers': headers,
                              'timeout': timeout})
            return FakeResponse(self.status)

        self.status = 200
        self.fake_post = fake_post
        self.tenx = self._relay_tenant('tenx', 'Clinic X')
        self._route(self.tenx, 'fb', PAGE_X)

    def _expected_signature(self, body):
        return 'sha256=' + hmac.new(META_SECRET.encode(), body,
                                    hashlib.sha256).hexdigest()

    # ==================================================================
    # T4 — one routed Page: split, re-signed, posted at the customer
    # ==================================================================
    def test_04_routed_page_is_forwarded(self):
        before = self._audit_count('relay_forwarded')
        payload = fb_payload(PAGE_X)
        with patch.object(relay.requests, 'post', self.fake_post):
            counts = self.Router._route_meta('fb', payload)

        self.assertEqual(counts['forwarded'], 1)
        self.assertEqual(counts['queued'], 0)
        self.assertEqual(len(self.sent), 1)
        call = self.sent[0]
        self.assertEqual(call['headers']['Host'],
                         self.Service._tenant_host('tenx'))
        self.assertEqual(call['url'],
                         '%s/care_channels/meta/fb/webhook'
                         % relay.forward_base(self.env))
        body = call['data']
        self.assertEqual(
            json.loads(body),
            {'object': 'page', 'entry': payload['entry']},
            'the customer receives their own entries and nothing else')
        self.assertEqual(body, json.dumps(json.loads(body),
                                          separators=(',', ':')).encode(),
                         'compact JSON — the bytes are what is signed')
        self.assertEqual(call['headers']['X-Hub-Signature-256'],
                         self._expected_signature(body))
        self.assertEqual(call['timeout'], relay.RELAY_TIMEOUT)

        self.assertEqual(self._audit_count('relay_forwarded'), before + 1)
        row = self.Audit.sudo().search(
            [('event', '=', 'relay_forwarded')], limit=1)
        self.assertIn('tenx', row.detail_redacted)
        self.assertNotIn(PAGE_X, row.detail_redacted or '',
                         'a page id is never written down here')
        self.assertNotIn('PSID', row.detail_redacted or '')
        self.assertTrue(self.tenx.last_forward_at)

    # ==================================================================
    # T5 — the platform is a clinic too: local ingests, tenant forwards
    # ==================================================================
    def test_05_local_and_tenant_in_one_batch(self):
        local = self._conn('fb', state='ready',
                           resource_external_id=PAGE_LOCAL)
        seen = []

        def fake_dispatch(self_model, connection, payload):
            seen.append((connection.id, payload))
            return {'ingested': 1, 'status': 0, 'ignored': 0}

        payload = fb_payload(PAGE_LOCAL, PAGE_X)
        with patch.object(CareChannelMessage, '_dispatch_connection',
                          fake_dispatch), \
                patch.object(relay.requests, 'post', self.fake_post):
            counts = self.Router._route_meta('fb', payload)

        self.assertEqual(counts['local'], 1)
        self.assertEqual(counts['forwarded'], 1)
        self.assertEqual(len(seen), 1)
        connection_id, local_payload = seen[0]
        self.assertEqual(connection_id, local.id)
        self.assertEqual([e['id'] for e in local_payload['entry']],
                         [PAGE_LOCAL],
                         'the platform never sees a customer\'s entry')
        forwarded = json.loads(self.sent[0]['data'])
        self.assertEqual([e['id'] for e in forwarded['entry']], [PAGE_X],
                         'and the customer never sees the platform\'s')

    # ==================================================================
    # T6 — an unknown Page is captured, and asks for ONE re-read a minute
    # ==================================================================
    def test_06_unknown_page_is_captured_and_resyncs_once(self):
        calls = []

        def fake_reconcile(self_model, push_credentials=True):
            calls.append(push_credentials)
            return {}

        payload = fb_payload(PAGE_UNKNOWN)
        with patch.object(ChannelRelayTenant, '_reconcile', fake_reconcile), \
                patch.object(relay.requests, 'post', self.fake_post):
            first = self.Router._route_meta('fb', payload)
            second = self.Router._route_meta('fb', payload)

        self.assertEqual(first['unknown'], 1)
        self.assertEqual(second['unknown'], 1)
        self.assertEqual(calls, [False],
                         'once, and routes only — a webhook must not be able '
                         'to make the platform open every database it likes')

        rows = self.Capture.sudo().search(
            [('reason_code', '=', 'unknown_resource'),
             ('resource_external_id', '=', PAGE_UNKNOWN)])
        self.assertTrue(rows)
        payloads = json.loads(rows[0].raw_payload)
        self.assertEqual([e['id'] for e in payloads['entry']], [PAGE_UNKNOWN],
                         'the unrouted queue holds the unrouted share only')

    # ==================================================================
    # T7 — the customer could not be reached: queued, never lost
    # ==================================================================
    def test_07_network_failure_is_queued(self):
        before = self._audit_count('relay_failed')

        def boom(url, data=None, headers=None, timeout=None, **kwargs):
            raise requests.ConnectionError('connection refused')

        with patch.object(relay.requests, 'post', boom):
            counts = self.Router._route_meta('fb', fb_payload(PAGE_X))

        self.assertEqual(counts['queued'], 1)
        self.assertEqual(counts['forwarded'], 0)
        row = self.Delivery.sudo().search(
            [('tenant_id', '=', self.tenx.id), ('state', '=', 'pending')])
        self.assertEqual(len(row), 1)
        self.assertTrue(row.body_enc.startswith('chs$1$'),
                        'the only copy of a message on this machine is '
                        'encrypted: %r' % (row.body_enc or '')[:16])
        self.assertEqual(row.entry_count, 1)
        self.assertEqual(row.attempts, 0)
        self.assertLessEqual(
            abs((row.next_at - fields.Datetime.now()).total_seconds()), 60)
        self.assertEqual(self._audit_count('relay_failed'), before + 1)

    # ==================================================================
    # T8 — a customer that refuses the signature is queued too
    # ==================================================================
    def test_08_forbidden_is_queued(self):
        self.status = 403
        with patch.object(relay.requests, 'post', self.fake_post):
            counts = self.Router._route_meta('fb', fb_payload(PAGE_X))

        self.assertEqual(counts['queued'], 1)
        row = self.Delivery.sudo().search(
            [('tenant_id', '=', self.tenx.id), ('state', '=', 'pending')])
        self.assertEqual(len(row), 1)
        self.assertIn('403', row.last_error)
        self.assertNotIn('PSID', row.last_error)
        self.assertNotIn(PAGE_X, row.last_error)

    # ==================================================================
    # T21 — one clinic's share can never be lost by another's failure
    # ==================================================================
    def test_21_a_broken_local_ingest_still_forwards(self):
        """The customers are served FIRST, and each share is isolated.

        The local ingest reaches a long way into this system's own clinical
        spine. If it raised and took the batch with it, every OTHER clinic's
        messages in it would be gone — unqueued, with Meta already answered
        200 and no redelivery coming.
        """
        self._conn('fb', state='ready', resource_external_id=PAGE_LOCAL)

        def exploding_dispatch(self_model, connection, payload):
            raise ValueError('the local ingest fell over')

        payload = fb_payload(PAGE_LOCAL, PAGE_X)
        with patch.object(CareChannelMessage, '_dispatch_connection',
                          exploding_dispatch), \
                patch.object(relay.requests, 'post', self.fake_post):
            counts = self.Router._route_meta('fb', payload)

        self.assertEqual(counts['forwarded'], 1,
                         'the customer was served before the platform, and '
                         'the platform falling over cost them nothing')
        self.assertEqual(counts['local'], 0)
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(
            [e['id'] for e in json.loads(self.sent[0]['data'])['entry']],
            [PAGE_X])

    def test_21b_a_broken_capture_still_forwards(self):
        def exploding_capture(self_model, *args, **kwargs):
            raise ValueError('the unrouted queue fell over')

        payload = fb_payload(PAGE_UNKNOWN, PAGE_X)
        with patch.object(type(self.Capture), '_capture', exploding_capture), \
                patch.object(ChannelRelayTenant, '_maybe_resync',
                             lambda self_model, reason='': False), \
                patch.object(relay.requests, 'post', self.fake_post):
            counts = self.Router._route_meta('fb', payload)

        self.assertEqual(counts['forwarded'], 1)
        self.assertEqual(counts['unknown'], 0)

    def test_21c_the_route_answers_200_when_the_router_falls_over(self):
        """Whatever happens inside, Meta is answered 200 after verification.

        A non-2xx makes Meta redeliver the whole batch for every customer in
        it and, sustained, switches the application's Messenger webhook off for
        all of them — so the router may never propagate.
        """
        def exploding_route(self_model, channel, payload, counts):
            raise ValueError('everything fell over at once')

        with patch.object(type(self.Router), '_route', exploding_route):
            counts = self.Router._route_meta('fb', fb_payload(PAGE_X))
        self.assertEqual(counts,
                         {'local': 0, 'forwarded': 0, 'queued': 0, 'unknown': 0},
                         'it returns a counter, it does not raise')


@tagged('post_install', '-at_install')
class TestRelayQueue(RelayCase):
    """T9–T11 — the retry queue is ours, and it is a queue, not an archive."""

    def setUp(self):
        super().setUp()
        self.tenx = self._relay_tenant('tenx', 'Clinic X')
        self.body = json.dumps({'object': 'page', 'entry': [{'id': PAGE_X}]},
                               separators=(',', ':')).encode()
        self.signature = 'sha256=' + hmac.new(
            META_SECRET.encode(), self.body, hashlib.sha256).hexdigest()
        self.row = self.Delivery._queue(
            self.tenx, 'fb', self.body, self.signature, 1, 'HTTP 502')

    # ==================================================================
    # T9 — the retry sends the SAME bytes with the SAME signature
    # ==================================================================
    def test_09_retry_delivers(self):
        sent = []

        def fake_post(url, data=None, headers=None, timeout=None, **kwargs):
            sent.append({'data': data, 'headers': headers})
            return FakeResponse(200)

        with patch.object(relay.requests, 'post', fake_post):
            result = self.Delivery._cron_retry()

        self.assertGreaterEqual(result['landed'], 1)
        row = self.row.sudo()
        self.assertEqual(row.state, 'delivered')
        self.assertFalse(row.body_enc)
        self.assertTrue(row.delivered_at)
        self.assertEqual(sent[0]['data'], self.body,
                         'a re-sent message is byte-identical or the '
                         'signature it carries stops matching it')
        self.assertEqual(sent[0]['headers']['X-Hub-Signature-256'],
                         self.signature)

    # ==================================================================
    # T10 — the waiting time grows, and it gives up rather than hammering
    # ==================================================================
    def test_10_backoff_then_dead(self):
        def boom(url, data=None, headers=None, timeout=None, **kwargs):
            raise requests.ConnectionError('still down')

        row = self.row.sudo()
        with patch.object(relay.requests, 'post', boom):
            for _ in range(3):
                row._attempt()
            self.assertEqual(row.attempts, 3)
            self.assertEqual(BACKOFF[2], 900)
            wait = (row.next_at - fields.Datetime.now()).total_seconds()
            self.assertLessEqual(abs(wait - 900), 60,
                                 'the third failure waits a quarter of an hour')
            self.assertEqual(row.state, 'pending')

            for _ in range(MAX_ATTEMPTS - 3):
                row._attempt()
        self.assertEqual(row.attempts, MAX_ATTEMPTS)
        self.assertEqual(row.state, 'dead')
        self.assertTrue(row.body_enc,
                        'given up on is not thrown away — an operator can '
                        'still press Retry now')

    # ==================================================================
    # T11 — a week later the queue lets go, and the message goes with it
    # ==================================================================
    def test_11_purge_finished_deliveries(self):
        old = fields.Datetime.now() - timedelta(days=8)
        delivered = self.Delivery._queue(
            self.tenx, 'fb', self.body, self.signature, 1, 'HTTP 502')
        delivered.sudo().write({'state': 'delivered', 'body_enc': False,
                                'delivered_at': old})
        dead = self.Delivery._queue(
            self.tenx, 'fb', self.body, self.signature, 1, 'HTTP 502')
        dead.sudo().write({'state': 'dead'})
        # write_date is the ORM's; a raw UPDATE is the only way to age it,
        # and it needs the flush/invalidate pair (ledger §5.9).
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE channel_relay_delivery SET write_date = %s WHERE id = %s",
            (old, dead.id))
        self.env.invalidate_all()

        pending_id, delivered_id, dead_id = self.row.id, delivered.id, dead.id
        removed = self.Delivery._cron_purge()

        self.assertGreaterEqual(removed, 2)
        self.assertFalse(self.Delivery.sudo().browse(delivered_id).exists())
        self.assertFalse(self.Delivery.sudo().browse(dead_id).exists())
        self.assertTrue(self.Delivery.sudo().browse(pending_id).exists(),
                        'a message still waiting to be delivered is not residue')


@tagged('post_install', '-at_install')
class TestRelayReconcile(RelayCase):
    """T12–T14 — the customer list, the route table and the secret."""

    # ==================================================================
    # T12 — who exists, who owns what, and who is claiming somebody else's
    # ==================================================================
    def test_12_reconcile_routes(self):
        Biz = self.env['biz.tenant'].sudo()
        alpha = Biz.create({'slug': 'r1alpha', 'name': 'Alpha', 'state': 'live'})
        Biz.create({'slug': 'r1beta', 'name': 'Beta', 'state': 'trial'})
        Biz.create({'slug': 'r1gamma', 'name': 'Gamma', 'state': 'paused'})

        rows = {'r1alpha': [('fb', PAGE_X), ('whatsapp', PHONE_1)],
                'r1beta': [('fb', PAGE_Y)]}
        with patch.object(type(self.Service), '_pg_cursor',
                          _pg_cursor_returning(rows)):
            self.Relay._reconcile(push_credentials=False)

        served = self.Relay.sudo().search([])
        self.assertEqual(sorted(served.mapped('slug')), ['r1alpha', 'r1beta'],
                         'a paused customer is not relayed for')
        alpha_row = served.filtered(lambda r: r.slug == 'r1alpha')
        beta_row = served.filtered(lambda r: r.slug == 'r1beta')
        self.assertEqual(alpha_row.name, 'Alpha')
        self.assertEqual(
            self.Route.sudo().search_count([('tenant_id', '=', alpha_row.id)]), 2)
        self.assertEqual(alpha_row.route_count, 2)
        self.assertEqual(
            self.Route.sudo().search_count([('tenant_id', '=', beta_row.id)]), 1)

        # A page the customer no longer has is removed, not left routing.
        rows['r1alpha'] = [('fb', PAGE_X)]
        with patch.object(type(self.Service), '_pg_cursor',
                          _pg_cursor_returning(rows)):
            self.Relay._reconcile(push_credentials=False)
        self.assertEqual(
            self.Route.sudo().search_count([('tenant_id', '=', alpha_row.id)]), 1)
        self.assertFalse(self.Route.sudo().search_count(
            [('resource_external_id', '=', PHONE_1)]))

        # Two customers claiming one page: the first keeps it, the second is
        # told, and nothing becomes a coin flip.
        rows['r1beta'] = [('fb', PAGE_Y), ('fb', PAGE_X)]
        before = self._audit_count('relay_failed')
        with patch.object(type(self.Service), '_pg_cursor',
                          _pg_cursor_returning(rows)):
            self.Relay._reconcile(push_credentials=False)
        self.assertEqual(self.Route._find('fb', PAGE_X), alpha_row)
        self.assertIn('two customers', beta_row.last_error or '')
        self.assertIn('r1alpha', beta_row.last_error)
        self.assertNotIn(PAGE_X, beta_row.last_error,
                         'safety rail 6: the page id is provider material '
                         'about a real clinic and never goes on a screen or '
                         'into an audit row')
        self.assertEqual(self._audit_count('relay_failed'), before + 1)
        row = self.Audit.sudo().search(
            [('event', '=', 'relay_failed')], limit=1)
        self.assertNotIn(PAGE_X, row.detail_redacted or '')

        # A customer that stops serving stops being relayed for.
        alpha.write({'state': 'paused'})
        rows.pop('r1alpha')
        with patch.object(type(self.Service), '_pg_cursor',
                          _pg_cursor_returning(rows)):
            self.Relay._reconcile(push_credentials=False)
        self.assertFalse(alpha_row.active)
        self.assertTrue(beta_row.active)

    def test_12c_the_platform_never_relays_to_itself(self):
        """A customer row whose short name IS this database is skipped.

        It should never exist, but a mis-typed row in the cockpit is one
        keystroke — and it would make the relay forward a batch straight back
        into the route it arrived on and push the platform's own Meta
        application into the platform.
        """
        self.env['biz.tenant'].sudo().create(
            {'slug': 'r1self', 'name': 'The platform itself', 'state': 'live'})
        # The database this suite runs on may carry an underscore, which the
        # short-name shape already refuses — so the guard is pinned by naming
        # this system, not by hoping the database is called the right thing.
        with patch.object(ChannelRelayTenant, '_own_slug',
                          lambda self_model: 'r1self'), \
                patch.object(type(self.Service), '_pg_cursor',
                             _pg_cursor_returning({})):
            counts = self.Relay._reconcile(push_credentials=False)
        self.assertEqual(counts['customers'], 0)
        self.assertFalse(self.Relay.sudo().with_context(
            active_test=False).search_count([('slug', '=', 'r1self')]))

    def test_12b_customer_behind_on_releases_is_skipped(self):
        self.env['biz.tenant'].sudo().create(
            {'slug': 'r1delta', 'name': 'Delta', 'state': 'live'})
        with patch.object(type(self.Service), '_pg_cursor',
                          _pg_cursor_returning({})):
            counts = self.Relay._reconcile(push_credentials=False)
        self.assertEqual(counts['customers'], 1)
        self.assertEqual(counts['routes'], 0)
        self.assertEqual(counts['problems'], 0,
                         'a customer whose system has no channels yet is '
                         'skipped, never a failure')

    # ==================================================================
    # T13 — the application reaches the customer, encrypted THERE
    # ==================================================================
    def test_13_push_credentials(self):
        """WHICH HALF THIS PROVES, and which half it cannot (ledger §5.180).

        The stand-in collapses two databases into one environment, so what is
        under test here is the SHAPE of the push: which fields are written, that
        the token is a `chs$1$` one, that the redirect parameter lands, that the
        customer row reads "in step". Encrypting and decrypting in a single
        environment says nothing about the property the push exists for — that
        the secret is encrypted with the TARGET database's own key (§5.172).
        That half is asymmetric and can only be proved live: the platform signs
        with its secret and the customer accepts the signature with the copy it
        was pushed. The deploy proof in the phase report is where it lives.
        """
        self.env['biz.tenant'].sudo().create(
            {'slug': 'r1alpha', 'name': 'Alpha', 'state': 'live'})
        env = self.env
        state = {'entered': 0}

        @contextmanager
        def fake_tenant_env(self_service, dbname):
            # The stand-in yields THIS environment (a second database cannot
            # be reached from a test transaction, ledger §5.63). Archiving the
            # platform's own row on the way in makes the row the push FINDS a
            # different row from the one it is copying — the values were read
            # before the loop started.
            state['entered'] += 1
            if state['entered'] == 1:
                self.meta_app.sudo().write({'active': False})
            yield env

        with patch.object(type(self.Service), '_pg_cursor',
                          _pg_cursor_returning({'r1alpha': []})), \
                patch.object(type(self.Service), '_tenant_env',
                             fake_tenant_env):
            counts = self.Relay._reconcile(push_credentials=True)

        self.assertEqual(counts['pushed'], 1)
        pushed = self.App.sudo().search(
            [('provider', '=', 'meta'), ('active', '=', True)])
        self.assertEqual(len(pushed), 1)
        self.assertNotEqual(pushed, self.meta_app)
        self.assertEqual(pushed.client_id, META_APP_ID)
        self.assertEqual(json.loads(pushed.extra_json).get('verify_token'),
                         json.loads(self.meta_app.extra_json)['verify_token'])
        self.assertEqual(pushed.secret_hint, '••••' + META_SECRET[-4:])
        self.assertEqual(
            channel_crypto.decrypt(self.env, pushed.client_secret_enc),
            META_SECRET,
            'the secret is encrypted in the environment it is stored in')
        self.assertEqual(
            self.env['ir.config_parameter'].sudo().get_param(
                REDIRECT_BASE_PARAM),
            self.Service._platform_url(),
            'and the customer\'s sign-in now returns to the platform')

        row = self.Relay.sudo().search([('slug', '=', 'r1alpha')])
        self.assertTrue(row.credentials_pushed_at)
        self.assertEqual(row.pushed_secret_hint, '••••' + META_SECRET[-4:])
        self.assertTrue(row.in_step)

    def test_13b_a_second_push_writes_nothing(self):
        row = self._relay_tenant('r1alpha', 'Alpha')
        env = self.env
        app = self.App.sudo().search([('provider', '=', 'meta')], limit=1)
        secret = app._get_secret()
        hint = self.Relay._hint_for(secret)
        writes = []

        @contextmanager
        def fake_tenant_env(self_service, dbname):
            yield env

        with patch.object(type(self.Service), '_tenant_env', fake_tenant_env):
            # Archive the platform row so the push creates a fresh one.
            self.meta_app.sudo().write({'active': False})
            first = self.Relay._push_one(
                self.Service, row, META_APP_ID, self.meta_app.extra_json,
                secret, hint, 'https://example.test')
            original_write = type(self.App).write

            def counting_write(self_model, vals):
                writes.append(sorted(vals))
                return original_write(self_model, vals)

            with patch.object(type(self.App), 'write', counting_write):
                second = self.Relay._push_one(
                    self.Service, row, META_APP_ID, self.meta_app.extra_json,
                    secret, hint, 'https://example.test')

        self.assertTrue(first, 'the first push changes something')
        self.assertFalse(second, 'the second has nothing left to change')
        self.assertFalse(writes, 'and writes no secret it does not have to')

    # ==================================================================
    # T14 — nothing to send is not a failure
    # ==================================================================
    def test_14_no_secret_no_push(self):
        self.env['biz.tenant'].sudo().create(
            {'slug': 'r1alpha', 'name': 'Alpha', 'state': 'live'})
        self.meta_app.sudo().write({'active': False})
        self.App.sudo().create({'provider': 'meta', 'client_id': META_APP_ID})

        def explode(self_service, dbname):
            raise AssertionError('nothing may be pushed without a secret')

        with patch.object(type(self.Service), '_pg_cursor',
                          _pg_cursor_returning({'r1alpha': []})), \
                patch.object(type(self.Service), '_tenant_env', explode):
            counts = self.Relay._reconcile(push_credentials=True)
        self.assertEqual(counts['pushed'], 0)
        self.assertEqual(counts['problems'], 0)


@tagged('post_install', '-at_install')
class TestRelaySignInAllowlist(RelayCase):
    """T15 — the short name in a sign-in ticket is routing, not trust."""

    def test_15_slug_from_state(self):
        self._relay_tenant('hhh', 'HHH Clinic')
        self.assertEqual(self.Relay._slug_from_state('hhh~abc'), 'hhh')

        for value, why in (
                ('zzz~abc', 'a customer this platform does not relay for'),
                ('abc', 'the platform\'s own sign-in carries no prefix'),
                ('HHH~x', 'a short name is small letters and digits'),
                ('../~x', 'nothing that could climb out of an address'),
                ('~abc', 'an empty short name'),
                ('', 'nothing at all'),
                (None, 'no ticket'),
                (123, 'not even a string')):
            self.assertIsNone(self.Relay._slug_from_state(value), why)

        # An archived customer is off the allowlist immediately.
        self.Relay.sudo().search([('slug', '=', 'hhh')]).write(
            {'active': False})
        self.assertIsNone(self.Relay._slug_from_state('hhh~abc'))
