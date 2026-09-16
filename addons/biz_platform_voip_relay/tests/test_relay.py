# -*- coding: utf-8 -*-
"""R01–R24 — the routing decision, the reconcile, and the retry queue.

Everything here runs without HTTP and without a second database. The two public
routes are proved separately, over real HTTP, in ``test_relay_http.py``.
"""
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from odoo.addons.biz_platform_voip_relay.models import relay_delivery
from odoo.addons.biz_platform_voip_relay.services import relay

from .common import (
    HOTLINE_A, HOTLINE_B, HOTLINE_NOBODY, RECEIVER_NOBODY, SLUG_A, SLUG_B,
    VoipRelayCase,
)

FORWARD = 'odoo.addons.biz_platform_voip_relay.services.relay.forward'
PG_CURSOR = 'odoo.addons.biz_tenants.models.service.BizTenants._pg_cursor'
TENANT_ENV = 'odoo.addons.biz_tenants.models.service.BizTenants._tenant_env'


@tagged('post_install', '-at_install')
class TestRouting(VoipRelayCase):
    """Who a call-back belongs to."""

    def test_01_unknown_address_belongs_to_nobody(self):
        kind, tenant = self.Router._classify(RECEIVER_NOBODY)
        self.assertEqual(kind, relay.UNKNOWN)
        self.assertFalse(tenant)

    def test_02_a_customers_own_address_is_theirs(self):
        row = self._relay_tenant(SLUG_A)
        self._route(row, 'receiver', 'RecvOfCustomerA111')
        kind, tenant = self.Router._classify('RecvOfCustomerA111')
        self.assertEqual(kind, relay.TENANT)
        self.assertEqual(tenant, row)

    def test_03_this_systems_own_address_is_handled_here(self):
        kind, tenant = self.Router._classify(self.local_receiver)
        self.assertEqual(kind, relay.LOCAL)
        self.assertFalse(tenant)

    def test_04_a_shared_address_splits_on_the_hotline(self):
        """One account with the supplier, several clinics behind it."""
        row = self._relay_tenant(SLUG_A)
        self._route(row, 'hotline', HOTLINE_A)
        kind, tenant = self.Router._classify(self.local_receiver, HOTLINE_A)
        self.assertEqual(kind, relay.TENANT)
        self.assertEqual(tenant, row)

    def test_05_a_hotline_nobody_owns_stays_here(self):
        self._route(self._relay_tenant(SLUG_A), 'hotline', HOTLINE_A)
        kind, tenant = self.Router._classify(self.local_receiver,
                                             HOTLINE_NOBODY)
        self.assertEqual(kind, relay.LOCAL)
        self.assertFalse(tenant)

    def test_06_the_address_beats_the_hotline(self):
        """A call that arrived on a customer's own address is theirs, full stop.

        Nothing in a payload may re-select a customer — otherwise anyone who
        can post to a known address could aim a call at a clinic that never
        received it.
        """
        owner = self._relay_tenant(SLUG_A)
        other = self._relay_tenant(SLUG_B)
        self._route(owner, 'receiver', 'RecvOfCustomerA111')
        self._route(other, 'hotline', HOTLINE_B)
        kind, tenant = self.Router._classify('RecvOfCustomerA111', HOTLINE_B)
        self.assertEqual(kind, relay.TENANT)
        self.assertEqual(tenant, owner)

    def test_07_an_archived_customer_is_not_routed_to(self):
        row = self._relay_tenant(SLUG_A)
        self._route(row, 'receiver', 'RecvOfCustomerA111')
        row.write({'active': False})
        kind, tenant = self.Router._classify('RecvOfCustomerA111')
        self.assertEqual(kind, relay.UNKNOWN)
        self.assertFalse(tenant)

    def test_08_two_customers_cannot_claim_one_key(self):
        a = self._relay_tenant(SLUG_A)
        b = self._relay_tenant(SLUG_B)
        self._route(a, 'hotline', HOTLINE_A)
        with self.assertRaises(ValidationError):
            self._route(b, 'hotline', HOTLINE_A)

    def test_09_the_same_key_may_repeat_across_kinds(self):
        """A hotline and an address are different namespaces."""
        a = self._relay_tenant(SLUG_A)
        self._route(a, 'hotline', HOTLINE_A)
        self._route(a, 'receiver', HOTLINE_A)  # absurd, but must not clash
        self.assertEqual(
            self.Route.sudo().search_count([('key', '=', HOTLINE_A)]), 2)


@tagged('post_install', '-at_install')
class TestReconcile(VoipRelayCase):
    """Reading the customers, and telling them where to point the supplier."""

    def test_10_customers_appear_and_leave_on_their_own(self):
        if 'biz.tenant' not in self.env:
            self.skipTest('no customer list on this system')
        Biz = self.env['biz.tenant'].sudo()
        self._relay_tenant(SLUG_A, state='live', with_biz=True)
        with patch(PG_CURSOR, lambda s, db='postgres':
                   self._pg_cursor_yielding([])):
            self.Relay._reconcile(push_settings=False)
        row = self.Relay.sudo().with_context(active_test=False).search(
            [('slug', '=', SLUG_A)])
        self.assertTrue(row.active, 'a live customer is served')

        Biz.search([('slug', '=', SLUG_A)]).write({'state': 'draft'})
        with patch(PG_CURSOR, lambda s, db='postgres':
                   self._pg_cursor_yielding([])):
            self.Relay._reconcile(push_settings=False)
        row.invalidate_recordset()
        self.assertFalse(row.active,
                         'a customer that stopped serving is not routed to')

    def test_11_the_platform_never_relays_to_itself(self):
        if 'biz.tenant' not in self.env:
            self.skipTest('no customer list on this system')
        own = self.Relay._own_slug()
        Biz = self.env['biz.tenant'].sudo()
        if not Biz.search([('slug', '=', own)]):
            Biz.create({'slug': own, 'name': 'This platform', 'state': 'live'})
        else:
            Biz.search([('slug', '=', own)]).write({'state': 'live'})
        with patch(PG_CURSOR, lambda s, db='postgres':
                   self._pg_cursor_yielding([])):
            self.Relay._reconcile(push_settings=False)
        self.assertFalse(
            self.Relay.sudo().with_context(active_test=False).search_count(
                [('slug', '=', own), ('active', '=', True)]),
            'relaying to itself would be an endless loop over loopback')

    def test_12_addresses_are_read_from_the_customers_system(self):
        row = self._relay_tenant(SLUG_A)
        counts = {'problems': 0}
        with patch(PG_CURSOR, lambda s, db='postgres':
                   self._pg_cursor_yielding(['RecvRead1', 'RecvRead2'])):
            total = self.Relay._sync_receivers(self.Service, row, counts)
        self.assertEqual(total, 2)
        self.assertEqual(row.receiver_count, 2)
        self.assertEqual(self.Router._classify('RecvRead1')[1], row)

    def test_13_an_address_that_went_away_stops_routing(self):
        row = self._relay_tenant(SLUG_A)
        counts = {'problems': 0}
        with patch(PG_CURSOR, lambda s, db='postgres':
                   self._pg_cursor_yielding(['RecvRead1', 'RecvRead2'])):
            self.Relay._sync_receivers(self.Service, row, counts)
        with patch(PG_CURSOR, lambda s, db='postgres':
                   self._pg_cursor_yielding(['RecvRead2'])):
            self.Relay._sync_receivers(self.Service, row, counts)
        # The one still there FIRST. Asking about an address nobody owns makes
        # the router re-read the customers, and in this suite the customer list
        # is deliberately empty — so that re-read archives the fixture and
        # every later lookup would answer "nobody" for the wrong reason.
        self.assertEqual(self.Router._classify('RecvRead2')[1], row)
        self.assertEqual(self.Router._classify('RecvRead1')[0], relay.UNKNOWN)

    def test_14_a_typed_hotline_survives_a_re_read(self):
        """The reconcile owns the addresses; the operator owns the hotlines."""
        row = self._relay_tenant(SLUG_A)
        self._route(row, 'hotline', HOTLINE_A)
        counts = {'problems': 0}
        with patch(PG_CURSOR, lambda s, db='postgres':
                   self._pg_cursor_yielding(['RecvRead1'])):
            self.Relay._sync_receivers(self.Service, row, counts)
        self.assertEqual(row.hotline_count, 1,
                         'a re-read must not delete what an operator typed')

    def test_15_one_address_on_two_customers_is_reported_not_guessed(self):
        """A copied database, and the only honest answer is "stop"."""
        a = self._relay_tenant(SLUG_A)
        b = self._relay_tenant(SLUG_B)
        counts = {'problems': 0}
        with patch(PG_CURSOR, lambda s, db='postgres':
                   self._pg_cursor_yielding(['RecvClash1'])):
            self.Relay._sync_receivers(self.Service, a | b, counts)
        self.assertEqual(counts['problems'], 1)
        self.assertEqual(self.Router._classify('RecvClash1')[1], a,
                         'the first customer seen keeps it')
        self.assertTrue(b.last_error, 'and the second is told, on their row')

    def test_16_a_customer_behind_on_releases_is_skipped(self):
        row = self._relay_tenant(SLUG_A)
        counts = {'problems': 0}
        with patch(PG_CURSOR, lambda s, db='postgres':
                   self._pg_cursor_yielding(None)):
            total = self.Relay._sync_receivers(self.Service, row, counts)
        self.assertEqual(total, 0)
        self.assertEqual(counts['problems'], 0,
                         'not yet upgraded is not a problem to report')

    def test_17_a_customer_that_cannot_be_read_does_not_stop_the_run(self):
        a = self._relay_tenant(SLUG_A)
        b = self._relay_tenant(SLUG_B)
        counts = {'problems': 0}
        seen = []

        def cursor(service, dbname='postgres'):
            seen.append(dbname)
            if dbname == SLUG_A:
                raise RuntimeError('boom')
            return self._pg_cursor_yielding(['RecvRead2'])

        with patch(PG_CURSOR, cursor):
            self.Relay._sync_receivers(self.Service, a | b, counts)
        self.assertEqual(counts['problems'], 1)
        self.assertTrue(a.last_error)
        self.assertEqual(self.Router._classify('RecvRead2')[1], b,
                         'the customer after the broken one was still read')

    def test_18_customers_are_told_to_point_the_supplier_here(self):
        row = self._relay_tenant(SLUG_A)
        counts = {'problems': 0}
        env = self.env
        with patch(TENANT_ENV,
                   lambda s, db: self._tenant_env_yielding(env)), \
                patch.object(type(self.Service), '_platform_url',
                             lambda s: 'https://carejiox.com'):
            pushed = self.Relay._push_callback_base(self.Service, row, counts)
        self.assertEqual(pushed, 1)
        self.assertEqual(
            self.env['ir.config_parameter'].sudo().get_param(
                'voip24h.callback_base'), 'https://carejiox.com')
        self.assertTrue(row.callback_base_pushed_at)
        # Told where to point, but nothing has been read back from them yet.
        # "In step" means BOTH, because either one alone relays no calls.
        self.assertFalse(row.in_step)
        self._route(row, 'receiver', 'RecvOfCustomerA111')
        row.invalidate_recordset()
        self.assertTrue(row.in_step)

    def test_19_telling_a_customer_twice_changes_nothing(self):
        row = self._relay_tenant(SLUG_A)
        counts = {'problems': 0}
        env = self.env
        with patch(TENANT_ENV,
                   lambda s, db: self._tenant_env_yielding(env)), \
                patch.object(type(self.Service), '_platform_url',
                             lambda s: 'https://carejiox.com'):
            self.Relay._push_callback_base(self.Service, row, counts)
            again = self.Relay._push_callback_base(self.Service, row, counts)
        self.assertEqual(again, 0, 'nothing moved, so nothing is reported')

    def test_20_a_resync_cannot_be_asked_for_twice_in_a_minute(self):
        """A public route must not be able to open every database on demand."""
        with patch(PG_CURSOR, lambda s, db='postgres':
                   self._pg_cursor_yielding([])):
            first = self.Relay._maybe_resync(reason='test')
            second = self.Relay._maybe_resync(reason='test')
        self.assertTrue(first)
        self.assertFalse(second)


@tagged('post_install', '-at_install')
class TestHandOver(VoipRelayCase):
    """Giving a call to the customer it belongs to."""

    def setUp(self):
        super().setUp()
        self.tenant = self._relay_tenant(SLUG_A)

    def test_21_the_customers_answer_is_the_suppliers_answer(self):
        with patch(FORWARD, return_value=(200, '{"status":"accepted"}')):
            status, body = self.Router._hand_over(
                self.tenant, 'cdr', self._delivery())
        self.assertEqual(status, 200)
        self.assertEqual(body, '{"status":"accepted"}')
        self.assertTrue(self.tenant.last_forward_at)
        self.assertFalse(self.Delivery.sudo().search_count(
            [('tenant_id', '=', self.tenant.id)]))

    def test_22_a_refusal_is_a_verdict_not_a_retry(self):
        """A rotated token must not fill this platform with stale credentials."""
        with patch(FORWARD, return_value=(403, '{"status":"denied"}')):
            status, _body = self.Router._hand_over(
                self.tenant, 'cdr', self._delivery())
        self.assertEqual(status, 403)
        self.assertEqual(self.Delivery.sudo().search_count(
            [('tenant_id', '=', self.tenant.id)]), 0,
            'a refusal is passed on, never queued')
        self.assertIn('403', self.tenant.last_error or '')

    def test_23_a_customer_that_cannot_be_reached_is_queued(self):
        with patch(FORWARD, side_effect=relay.RelayError('HTTP 502')):
            status, body = self.Router._hand_over(
                self.tenant, 'cdr', self._delivery())
        self.assertEqual(status, 202)
        self.assertEqual(body, {'status': 'accepted'})
        queued = self.Delivery.sudo().search(
            [('tenant_id', '=', self.tenant.id)])
        self.assertEqual(len(queued), 1)
        self.assertEqual(queued.state, 'pending')

    def test_24_a_queued_call_is_never_readable(self):
        with patch(FORWARD, side_effect=relay.RelayError('HTTP 502')):
            self.Router._hand_over(self.tenant, 'cdr', self._delivery())
        queued = self.Delivery.sudo().search(
            [('tenant_id', '=', self.tenant.id)])
        self.assertTrue(queued.payload_enc.startswith('vps$1$'),
                        'the call-back rests encrypted or not at all')
        self.assertNotIn('02873007777', queued.payload_enc)

    def test_25_a_queued_call_is_replayed_byte_for_byte(self):
        body = b'{"src":"\xff\xfe not utf-8"}'
        delivery = self._delivery(method='POST', body=body,
                                  content_type='application/json')
        with patch(FORWARD, side_effect=relay.RelayError('HTTP 502')):
            self.Router._hand_over(self.tenant, 'cdr', delivery)
        queued = self.Delivery.sudo().search(
            [('tenant_id', '=', self.tenant.id)])
        self.assertEqual(queued._unpack()['body'], body)
        self.assertEqual(queued._unpack()['path'], delivery['path'])
        self.assertEqual(queued._unpack()['query'], delivery['query'])


@tagged('post_install', '-at_install')
class TestRetryQueue(VoipRelayCase):
    """The hand-offs that did not land."""

    def setUp(self):
        super().setUp()
        self.tenant = self._relay_tenant(SLUG_A)
        self.row = self.Delivery._queue(self.tenant, 'cdr', self._delivery(),
                                        'HTTP 502')

    def test_26_a_landed_retry_clears_the_call(self):
        with patch(FORWARD, return_value=(200, '{"status":"accepted"}')):
            landed = self.row._attempt()
        self.assertTrue(landed)
        self.assertEqual(self.row.state, 'delivered')
        self.assertFalse(self.row.payload_enc,
                         'the call is erased on delivery, not on the purge')

    def test_27_a_failed_retry_waits_longer_each_time(self):
        with patch(FORWARD, side_effect=relay.RelayError('HTTP 502')):
            self.row._attempt()
        self.assertEqual(self.row.attempts, 1)
        first = self.row.next_at
        with patch(FORWARD, side_effect=relay.RelayError('HTTP 502')):
            self.row._attempt()
        self.assertEqual(self.row.attempts, 2)
        self.assertGreater(self.row.next_at, first)

    def test_28_it_gives_up_but_keeps_the_call(self):
        self.row.write({'attempts': relay_delivery.MAX_ATTEMPTS - 1})
        with patch(FORWARD, side_effect=relay.RelayError('HTTP 502')):
            self.row._attempt()
        self.assertEqual(self.row.state, 'dead')
        self.assertTrue(self.row.payload_enc,
                        'an operator can still press "Try this again"')

    def test_29_a_retry_that_is_refused_is_finished_with(self):
        with patch(FORWARD, return_value=(400, '{"status":"malformed"}')):
            landed = self.row._attempt()
        self.assertFalse(landed)
        self.assertEqual(self.row.state, 'delivered')
        self.assertIn('400', self.row.last_error)

    def test_30_the_cron_works_on_the_ones_that_are_due(self):
        self.row.write({'next_at': fields.Datetime.now() - timedelta(hours=1)})
        later = self.Delivery._queue(self.tenant, 'cdr', self._delivery(),
                                     'HTTP 502')
        later.write({'next_at': fields.Datetime.now() + timedelta(hours=1)})
        with patch(FORWARD, return_value=(200, '{"status":"accepted"}')):
            result = self.Delivery._cron_retry()
        self.assertEqual(result['landed'], 1)
        self.assertEqual(later.state, 'pending')

    def test_31_one_poisoned_row_does_not_stop_the_run(self):
        self.row.write({'payload_enc': 'not-a-token'})
        other = self.Delivery._queue(self.tenant, 'cdr', self._delivery(),
                                     'HTTP 502')
        with patch(FORWARD, return_value=(200, '{"status":"accepted"}')):
            self.Delivery._cron_retry()
        self.assertEqual(self.row.state, 'dead')
        self.assertEqual(other.state, 'delivered')

    def test_32_the_queue_is_a_queue_not_an_archive(self):
        old = fields.Datetime.now() - timedelta(
            days=relay_delivery.PURGE_AFTER_DAYS + 1)
        self.row.write({'state': 'delivered', 'delivered_at': old})
        keep = self.Delivery._queue(self.tenant, 'cdr', self._delivery(), 'x')
        self.Delivery._cron_purge()
        self.assertFalse(self.row.exists())
        self.assertTrue(keep.exists())


@tagged('post_install', '-at_install')
class TestSignposting(VoipRelayCase):
    """Reading just enough of a call-back to know where it goes."""

    class _Req:
        def __init__(self, method='GET', args=None, form=None, data=b'',
                     content_type=''):
            self.method = method
            self.args = args or {}
            self.form = form or {}
            self._data = data
            self.content_type = content_type
            self.path = '/voip24h/v3/cdr/A/B'
            self.query_string = b''

        def get_data(self):
            return self._data

    def test_33_a_hotline_is_read_from_a_get(self):
        req = self._Req(args={'did': HOTLINE_A})
        self.assertEqual(relay.peek_hotline(req), HOTLINE_A)

    def test_34_a_hotline_is_read_from_posted_json(self):
        req = self._Req(method='POST',
                        data=b'{"did":"%s"}' % HOTLINE_A.encode(),
                        content_type='application/json')
        self.assertEqual(relay.peek_hotline(req), HOTLINE_A)

    def test_35_a_signpost_never_breaks_a_call_back(self):
        """Whatever arrives, the answer is a string and never an exception."""
        for req in (self._Req(method='POST', data=b'not json at all',
                              content_type='application/json'),
                    self._Req(method='POST', data=b'[1,2,3]',
                              content_type='application/json'),
                    self._Req(method='POST', data=b'', content_type='text/xml'),
                    self._Req(args={})):
            self.assertEqual(relay.peek_hotline(req), '')

    def test_36_a_call_back_is_captured_whole(self):
        req = self._Req(method='POST', data=b'{"id":"1"}',
                        content_type='application/json')
        req.query_string = b'a=1&b=2'
        captured = relay.capture(req)
        self.assertEqual(captured['method'], 'POST')
        self.assertEqual(captured['path'], '/voip24h/v3/cdr/A/B')
        self.assertEqual(captured['query'], 'a=1&b=2')
        self.assertEqual(captured['body'], b'{"id":"1"}')


@tagged('post_install', '-at_install')
class TestPublishedAddress(VoipRelayCase):
    """Which address a clinic gives the phone supplier."""

    def _icp(self):
        return self.env['ir.config_parameter'].sudo()

    def test_37_without_a_platform_this_systems_own_address_is_published(self):
        self._icp().set_param('voip24h.callback_base', '')
        self.assertEqual(self.config._callback_base(), self.config._base_url())

    def test_38_the_platform_address_is_published_when_it_is_set(self):
        self._icp().set_param('voip24h.callback_base', 'https://carejiox.com/')
        self.assertEqual(self.config._callback_base(), 'https://carejiox.com')
        self.config.invalidate_recordset()
        self.assertTrue(self.config.sudo().cdr_webhook_url.startswith(
            'https://carejiox.com/voip24h/v3/cdr/'))

    def test_39_the_address_and_token_are_unchanged_by_the_relay(self):
        """The same address, on a different doorstep. That is the whole trick."""
        self._icp().set_param('voip24h.callback_base', '')
        self.config.invalidate_recordset()
        direct = self.config.sudo().cdr_webhook_url
        self._icp().set_param('voip24h.callback_base', 'https://carejiox.com')
        self.config.invalidate_recordset()
        relayed = self.config.sudo().cdr_webhook_url
        self.assertEqual(direct.split('/voip24h/', 1)[1],
                         relayed.split('/voip24h/', 1)[1])

    def test_40_a_setting_that_is_not_an_address_is_ignored(self):
        """This string is pasted into a third party's dashboard."""
        for bad in ('carejiox.com', 'http://carejiox.com', 'https://',
                    'javascript:alert(1)'):
            self._icp().set_param('voip24h.callback_base', bad)
            self.assertEqual(self.config._callback_base(),
                             self.config._base_url(), bad)
