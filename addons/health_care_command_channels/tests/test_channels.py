# -*- coding: utf-8 -*-
"""T50–T69 — the CC-B message spine: verifiers, ingest, merge, send, dock.

TransactionCase ONLY (ledger §5.32/§5.61): the controllers are ten-line shells
around the model methods exercised here, so this suite covers everything below
HTTP header plumbing without an HttpCase's cross-cursor side effects.

Every provider payload is a simulated fixture from ``common_spine``; every
outbound HTTP call is mocked. Nothing here can reach Meta, Telegram or anyone
else, by construction.
"""
import json
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from odoo.addons.health_care_command_channels.services.webhook_verify import (
    meta_challenge, verify_meta, verify_telegram,
)

from .common_spine import (
    FB_PAGE_ID, META_VERIFY_TOKEN, TG_PATH_SECRET, WA_PHONE_ID,
    ChannelSpineCase,
)


@tagged('post_install', '-at_install')
class TestChannelSpine(ChannelSpineCase):

    # ==================================================================
    # T50 — Meta HMAC, fail closed in every direction
    # ==================================================================
    def test_50_meta_signature(self):
        raw = self.raw(self.wa_payload())

        self.assertTrue(verify_meta(self.meta_app, raw, self.meta_signature(raw)))
        # A signature over a DIFFERENT body must not validate this one.
        other = self.meta_signature(self.raw(self.wa_payload(text='tampered')))
        self.assertFalse(verify_meta(self.meta_app, raw, other))
        self.assertFalse(verify_meta(self.meta_app, raw, 'sha256=deadbeef'))
        self.assertFalse(verify_meta(self.meta_app, raw, None))
        self.assertFalse(verify_meta(self.meta_app, raw, ''))
        # No platform app at all → refuse (the zalo webhook accepts here).
        self.assertFalse(verify_meta(self.App.browse(), raw,
                                     self.meta_signature(raw)))

        # Configured app but NO secret stored → still refuse.
        self.meta_app.write({'active': False})
        naked = self.App.create({'provider': 'meta', 'client_id': 'no-secret'})
        self.assertFalse(verify_meta(naked, raw, self.meta_signature(raw)))

    # ==================================================================
    # T51 — Meta GET handshake
    # ==================================================================
    def test_51_meta_challenge(self):
        self.assertEqual(
            meta_challenge(self.meta_app, 'subscribe', META_VERIFY_TOKEN, '42'),
            '42')
        self.assertIsNone(
            meta_challenge(self.meta_app, 'subscribe', 'wrong-token', '42'))
        self.assertIsNone(meta_challenge(self.meta_app, 'subscribe', '', '42'))
        # Only the subscribe handshake is honoured.
        self.assertIsNone(
            meta_challenge(self.meta_app, 'unsubscribe', META_VERIFY_TOKEN, '42'))
        # No app, or an app with no verify token, refuses.
        self.assertIsNone(
            meta_challenge(self.App.browse(), 'subscribe', META_VERIFY_TOKEN, '42'))
        self.meta_app.write({'active': False})
        bare = self.App.create({'provider': 'meta', 'client_id': 'bare'})
        self.assertIsNone(
            meta_challenge(bare, 'subscribe', META_VERIFY_TOKEN, '42'))

    # ==================================================================
    # T52 — Telegram path + header secret
    # ==================================================================
    def test_52_telegram_verify(self):
        conn = self._tg_conn()
        self.assertTrue(verify_telegram(conn, TG_PATH_SECRET, TG_PATH_SECRET))
        # Header absent: the unguessable path secret is the credential.
        self.assertTrue(verify_telegram(conn, TG_PATH_SECRET, None))
        # Header present and WRONG is a hard reject.
        self.assertFalse(verify_telegram(conn, TG_PATH_SECRET, 'nope'))
        self.assertFalse(verify_telegram(conn, 'wrong-path', TG_PATH_SECRET))
        self.assertFalse(verify_telegram(conn, '', ''))
        # No connection at all → refuse.
        self.assertFalse(verify_telegram(
            self.Conn.browse(), TG_PATH_SECRET, TG_PATH_SECRET))
        # Connection with no stored secret → refuse.
        naked = self._conn('telegram', company=self.company2, state='testing')
        self.assertFalse(verify_telegram(naked, TG_PATH_SECRET, TG_PATH_SECRET))

    # ==================================================================
    # T53 — WhatsApp inbound lands on the spine
    # ==================================================================
    def test_53_whatsapp_inbound(self):
        conn = self._wa_conn()
        counts = self.Message._dispatch_meta('whatsapp', self.wa_payload())
        self.assertEqual(counts['ingested'], 1)

        identity = self.identity_of(conn, '84901234567')
        self.assertTrue(identity)
        self.assertEqual(identity.display_name, 'Chị Lan')

        msg = self.Message.sudo().search([('identity_id', '=', identity.id)])
        self.assertEqual(len(msg), 1)
        self.assertEqual(msg.direction, 'incoming')
        self.assertEqual(msg.state, 'received')
        self.assertEqual(msg.external_message_id, 'wamid.FIXTURE1')

        conv = self.conv_of(identity)
        self.assertEqual(len(conv), 1)
        self.assertEqual(conv.channel_primary, 'whatsapp')
        self.assertEqual(conv.channel_effective, 'whatsapp')
        self.assertEqual(conv.status, 'needs_reply')
        self.assertGreaterEqual(conv.unread_count, 1)
        self.assertTrue(conv.has_channel_activity)
        # The phone anchor goes through the SAME normaliser the spine uses.
        self.assertEqual(conv.phone_normalized,
                         self.Care._safe_phone('84901234567'))
        self.assertEqual(msg.conversation_id, conv)

    # ==================================================================
    # T54 — webhook redelivery is idempotent
    # ==================================================================
    def test_54_redelivery_idempotent(self):
        conn = self._wa_conn()
        payload = self.wa_payload()
        self.Message._dispatch_meta('whatsapp', payload)
        identity = self.identity_of(conn, '84901234567')
        conv = self.conv_of(identity)
        unread_first = conv.unread_count

        self.Message._dispatch_meta('whatsapp', payload)

        self.assertEqual(
            self.Message.sudo().search_count([('identity_id', '=', identity.id)]), 1)
        self.assertEqual(len(self.conv_of(identity)), 1)
        conv.invalidate_recordset(['unread_count'])
        self.assertEqual(conv.unread_count, unread_first,
                         'a redelivered event must not bump unread twice')

    # ==================================================================
    # T55 — Messenger: the identity is a legal SOLE anchor
    # ==================================================================
    def test_55_fb_inbound_identity_only(self):
        conn = self._fb_conn()
        self.Message._dispatch_meta('fb', self.fb_payload())

        identity = self.identity_of(conn, 'PSID_1')
        self.assertTrue(identity)
        conv = self.conv_of(identity)
        self.assertEqual(len(conv), 1)
        # No phone, no email, no partner, no lead — _check_anchor passed on the
        # channel identity alone, which is the whole point of the override.
        self.assertFalse(conv.phone_normalized)
        self.assertFalse(conv.email_normalized)
        self.assertFalse(conv.partner_id)
        self.assertFalse(conv.lead_id)
        self.assertEqual(conv.channel_primary, 'fb')
        # Messenger sends no profile name in the webhook (Graph enrichment is
        # CC-E), so the PSID is the honest display name.
        self.assertEqual(identity.display_name, 'PSID_1')
        self.assertEqual(conv.display_name_c, 'PSID_1')

    # ==================================================================
    # T56 — Telegram inbound + composite dedupe key
    # ==================================================================
    def test_56_telegram_inbound(self):
        conn = self._tg_conn()
        self.Message._dispatch_connection(conn, self.tg_payload())

        identity = self.identity_of(conn, '555001')
        self.assertTrue(identity)
        self.assertEqual(identity.display_name, 'Minh')
        msg = self.Message.sudo().search([('identity_id', '=', identity.id)])
        self.assertEqual(msg.external_message_id, '555001:11')
        conv = self.conv_of(identity)
        self.assertEqual(conv.channel_primary, 'telegram')

        # Same update again → one row (the composite key is the dedupe).
        self.Message._dispatch_connection(conn, self.tg_payload())
        self.assertEqual(
            self.Message.sudo().search_count([('identity_id', '=', identity.id)]), 1)

    # ==================================================================
    # T57 — WhatsApp merges into an existing phone-anchored thread
    # ==================================================================
    def test_57_whatsapp_merges_phone_thread(self):
        conn = self._wa_conn()
        phone = self.Care._safe_phone('84901234567')
        self.assertTrue(phone, 'fixture number must normalise')
        existing = self.Care._find_or_create_for(
            {'phone_normalized': phone},
            {'channel': 'call', 'inbound': True,
             'event_at': fields.Datetime.now(), 'set_status': 'needs_reply'})

        self.Message._dispatch_meta('whatsapp', self.wa_payload())

        identity = self.identity_of(conn, '84901234567')
        conv = self.conv_of(identity)
        self.assertEqual(conv, existing, 'WA must merge, not fork')
        self.assertEqual(conv.channel_identity_id, identity)
        self.assertEqual(
            self.Care.sudo().search_count([('phone_normalized', '=', phone)]), 1)

    # ==================================================================
    # T58 — web-chat lifecycle
    # ==================================================================
    def test_58_webchat_lifecycle(self):
        conn = self._wc_conn()
        started = self.Message._webchat_start()
        session = started['session']
        self.assertTrue(session)
        self.assertEqual(started['greeting'],
                         'Xin chào! Chúng tôi có thể giúp gì?')

        msg = self.Message._webchat_ingest(session, 'Tôi muốn hỏi giá')
        self.assertTrue(msg)
        identity = self.identity_of(conn, session)
        conv = self.conv_of(identity)
        self.assertEqual(conv.channel_primary, 'webchat')
        self.assertEqual(conv.status, 'needs_reply')

        # Unknown session: nothing created, no oracle for the caller.
        self.assertFalse(self.Message._webchat_ingest('not-a-session', 'hi'))
        # Resuming a known session keeps the same identity.
        again = self.Message._webchat_start(session=session)
        self.assertEqual(again['session'], session)
        # An empty message is not a message.
        self.assertFalse(self.Message._webchat_ingest(session, '   '))

    # ==================================================================
    # T59 — web-chat poll cursor
    # ==================================================================
    def test_59_webchat_poll_cursor(self):
        self._wc_conn()
        session = self.Message._webchat_start()['session']
        first = self.Message._webchat_ingest(session, 'câu hỏi 1')
        conv = first.conversation_id

        with self.mock_post():
            self.Care.action_send_channel(conv.id, 'webchat', 'Chào anh/chị')

        rows = self.Message._webchat_poll(session, after_id=first.id)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['direction'], 'outgoing')
        self.assertEqual(rows[0]['body'], 'Chào anh/chị')
        self.assertGreater(rows[0]['id'], first.id)

        everything = self.Message._webchat_poll(session, after_id=0)
        self.assertEqual(len(everything), 2)
        self.assertEqual([r['direction'] for r in everything],
                         ['incoming', 'outgoing'])

    # ==================================================================
    # T60 — outbound per channel (mocked HTTP)
    # ==================================================================
    def test_60_outbound_per_channel(self):
        cases = [
            ('whatsapp', self._wa_conn(), self.wa_payload(),
             {'messages': [{'id': 'wamid.OUT1'}]}, 'wamid.OUT1'),
            ('fb', self._fb_conn(), self.fb_payload(),
             {'message_id': 'mid.OUT1'}, 'mid.OUT1'),
            ('telegram', self._tg_conn(), self.tg_payload(),
             {'ok': True, 'result': {'message_id': 99,
                                     'chat': {'id': 555001}}}, '555001:99'),
        ]
        for channel, conn, payload, reply, expected_id in cases:
            with self.subTest(channel=channel):
                if channel == 'telegram':
                    self.Message._dispatch_connection(conn, payload)
                else:
                    self.Message._dispatch_meta(channel, payload)
                conv = self.Care.sudo().search(
                    [('channel_identity_id.connection_id', '=', conn.id)], limit=1)
                self.assertTrue(conv)

                with self.mock_post(response=reply) as mocked:
                    bubble = self.Care.action_send_channel(
                        conv.id, channel, 'Cảm ơn anh/chị')
                self.assertTrue(mocked.called)
                self.assertEqual(bubble['direction'], 'out')
                self.assertEqual(bubble['kind'], channel)

                out = self.Message.sudo().search(
                    [('connection_id', '=', conn.id),
                     ('direction', '=', 'outgoing')], limit=1)
                self.assertEqual(out.state, 'sent')
                self.assertEqual(out.external_message_id, expected_id)

                conv.invalidate_recordset(['status', 'unread_count'])
                self.assertEqual(conv.status, 'waiting')
                self.assertEqual(conv.unread_count, 0)

        # A provider error is a clean UserError + a failed row, never a crash
        # and never a silent success.
        conn = cases[0][1]
        conv = self.Care.sudo().search(
            [('channel_identity_id.connection_id', '=', conn.id)], limit=1)
        # NOT assertRaises: Odoo wraps it in a savepoint and rolls back every
        # write made before the raise (ledger §5.8), which would erase the very
        # evidence this asserts on.
        with self.mock_post(response={'error': {'message': 'boom'}}, status=500):
            try:
                self.Care.action_send_channel(conv.id, 'whatsapp', 'again')
                self.fail('a provider error must surface as a UserError')
            except UserError:
                pass
        failed = self.Message.sudo().search(
            [('connection_id', '=', conn.id), ('state', '=', 'failed')])
        self.assertTrue(failed)
        self.assertTrue(failed[0].error_message)

    # ==================================================================
    # T61 — capabilities degrade honestly
    # ==================================================================
    def test_61_capabilities(self):
        conn = self._tg_conn()
        self.Message._dispatch_connection(conn, self.tg_payload())
        identity = self.identity_of(conn, '555001')
        conv = self.conv_of(identity)

        detail = self.Care.get_conversation_detail(conv.id)
        self.assertEqual(detail['capabilities'].get('ext_reply_channel'),
                         'telegram')

        # Disable the connection: the composer must stop offering the send.
        conn._transition('disabled', reason='test')
        conv.invalidate_recordset()
        detail = self.Care.get_conversation_detail(conv.id)
        self.assertNotIn('ext_reply_channel', detail['capabilities'])

        # A conversation with no identity at all never gains the key.
        plain = self.Care._find_or_create_for(
            {'email_normalized': 'plain@example.com'},
            {'channel': 'email', 'inbound': True})
        self.assertNotIn('ext_reply_channel', plain._capabilities())

    # ==================================================================
    # T62 — access control on the send path
    # ==================================================================
    def test_62_access(self):
        conn = self._tg_conn()
        self.Message._dispatch_connection(conn, self.tg_payload())
        conv = self.conv_of(self.identity_of(conn, '555001'))

        plain = self._mk_user('chub_plain_t62', [])
        with self.assertRaises(AccessError):
            self.Care.with_user(plain).action_send_channel(
                conv.id, 'telegram', 'hi')

        with self.mock_post(response={'ok': True,
                                      'result': {'message_id': 5,
                                                 'chat': {'id': 555001}}}):
            bubble = self.Care.with_user(self.crm_user).action_send_channel(
                conv.id, 'telegram', 'Chào bạn')
        self.assertEqual(bubble['direction'], 'out')

        # A CRM user reads the connection, but never its credentials.
        as_user = conn.with_user(self.crm_user)
        with self.assertRaises(AccessError):
            as_user.read(['provider_secret_enc'])

    # ==================================================================
    # T63 — multi-company isolation
    # ==================================================================
    def test_63_multi_company(self):
        self._wa_conn()  # company 1
        conn2 = self._wa_conn(company=self.company2, phone_id='PHONE_ID_2')

        self.Message._dispatch_meta(
            'whatsapp', self.wa_payload(wa_id='84907654321',
                                        mid='wamid.CO2', phone_id='PHONE_ID_2'))
        identity = self.identity_of(conn2, '84907654321')
        conv = self.conv_of(identity)
        self.assertEqual(conv.company_id, self.company2,
                         'ingest must land in the connection\'s company')

        data = self.Care.with_user(self.crm_user).get_workspace_data(view='all')
        self.assertNotIn(conv.id, [row['id'] for row in data['conversations']])

    # ==================================================================
    # T64 — watchlist runs on adapter inbound too
    # ==================================================================
    def test_64_watchlist(self):
        self.env['care.watch.phrase'].create({
            'phrase': 'khiếu nại', 'company_id': self.company.id})
        conn = self._tg_conn()
        self.Message._dispatch_connection(
            conn, self.tg_payload(text='Tôi muốn khiếu nại về dịch vụ'))
        conv = self.conv_of(self.identity_of(conn, '555001'))
        self.assertTrue(conv.watch_flag)
        self.assertIn('khiếu nại', conv.watch_terms or '')

    # ==================================================================
    # T65 — a failing spine write cannot poison the host transaction
    # ==================================================================
    def test_65_savepoint_isolation(self):
        conn = self._tg_conn()

        def _boom(*args, **kwargs):
            # A DATABASE-level error: a plain Python raise would prove nothing,
            # because it is precisely the aborted-transaction case that a bare
            # try/except cannot recover from (ledger §5.55).
            self.env.cr.execute('SELECT 1/0')

        with patch.object(type(self.Care), '_find_or_create_for',
                          side_effect=_boom):
            self.Message._dispatch_connection(conn, self.tg_payload())

        # The transaction is still alive...
        self.env.cr.execute('SELECT 1')
        self.assertEqual(self.env.cr.fetchone()[0], 1)
        # ...and the message row survived the spine failure.
        identity = self.identity_of(conn, '555001')
        self.assertEqual(
            self.Message.sudo().search_count([('identity_id', '=', identity.id)]), 1)

    # ==================================================================
    # T66 — the public web-chat routes are rate-bounded
    # ==================================================================
    def test_66_rate_limit(self):
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('gateway.rate_limit_per_min', '3')
        icp.set_param('gateway.rate_limit_burst', '3')
        self.addCleanup(icp.set_param, 'gateway.rate_limit_per_min', '120')
        self.addCleanup(icp.set_param, 'gateway.rate_limit_burst', '240')

        counter = self.env['gateway.rate.counter'].sudo()
        key = 'webchat:msg:t66-session'
        outcomes = [counter.hit(key)[0] for _ in range(5)]
        self.assertEqual(outcomes[:3], [True, True, True])
        self.assertFalse(outcomes[3], 'the fourth hit in the window is blocked')
        self.assertFalse(outcomes[4])

    # ==================================================================
    # T67 — _channel_keys() reflects real connections
    # ==================================================================
    def test_67_channel_keys(self):
        base = ('zalo', 'call', 'email', 'zns')
        keys = self.Care._channel_keys()
        self.assertEqual(tuple(keys), base,
                         'no connection ⇒ the 4 adapter icons stay dark')

        conn = self._wa_conn()
        self.assertIn('whatsapp', self.Care._channel_keys())
        for key in base:
            self.assertIn(key, self.Care._channel_keys())

        # A connection that is merely being set up is NOT a live channel.
        conn._transition('action_required', reason='test')
        self.assertNotIn('whatsapp', self.Care._channel_keys())

        data = self.Care.get_workspace_data(view='all')
        self.assertNotIn('whatsapp', data['active_channels'])

    # ==================================================================
    # T68 — timeline merge, sorted and capped
    # ==================================================================
    def test_68_timeline_merge(self):
        conn = self._tg_conn()
        self.Message._dispatch_connection(conn, self.tg_payload(text='one'))
        identity = self.identity_of(conn, '555001')
        conv = self.conv_of(identity)

        timeline = conv._detail_timeline()
        self.assertTrue(any(e['kind'] == 'telegram' and e['text'] == 'one'
                            for e in timeline))

        # Bulk history: the merged timeline stays capped and ordered.
        now = fields.Datetime.now()
        self.Message.sudo().create([{
            'connection_id': conn.id,
            'identity_id': identity.id,
            'conversation_id': conv.id,
            'direction': 'incoming',
            'body': 'bulk %s' % i,
            'external_message_id': '555001:bulk%s' % i,
            'event_at': now,
        } for i in range(110)])
        timeline = conv._detail_timeline()
        self.assertEqual(len(timeline), 100)
        self.assertEqual(timeline, sorted(timeline, key=lambda e: e['ts']))

    # ==================================================================
    # T69 — WhatsApp delivery receipts
    # ==================================================================
    def test_69_status_events(self):
        conn = self._wa_conn()
        self.Message._dispatch_meta('whatsapp', self.wa_payload())
        identity = self.identity_of(conn, '84901234567')
        conv = self.conv_of(identity)

        with self.mock_post(response={'messages': [{'id': 'wamid.OUT9'}]}):
            self.Care.action_send_channel(conv.id, 'whatsapp', 'ok')
        out = self.Message.sudo().search(
            [('external_message_id', '=', 'wamid.OUT9')])
        self.assertEqual(out.state, 'sent')

        counts = self.Message._dispatch_meta(
            'whatsapp', self.wa_status_payload(mid='wamid.OUT9',
                                               status='delivered'))
        self.assertEqual(counts['status'], 1)
        out.invalidate_recordset(['state'])
        self.assertEqual(out.state, 'delivered')

        self.Message._dispatch_meta(
            'whatsapp', self.wa_status_payload(mid='wamid.OUT9', status='read'))
        out.invalidate_recordset(['state'])
        self.assertEqual(out.state, 'read')

        # A late out-of-order receipt never walks the state backwards.
        self.Message._dispatch_meta(
            'whatsapp', self.wa_status_payload(mid='wamid.OUT9', status='sent'))
        out.invalidate_recordset(['state'])
        self.assertEqual(out.state, 'read')

        # An unknown id is ignored quietly — no row, no exception.
        before = self.Message.sudo().search_count([])
        self.Message._dispatch_meta(
            'whatsapp', self.wa_status_payload(mid='wamid.NEVER-SEEN'))
        self.assertEqual(self.Message.sudo().search_count([]), before)

    # ==================================================================
    # T95 — a volunteered web-chat phone NEVER anchors (CC-B review fix)
    # ==================================================================
    def test_95_webchat_phone_never_anchors(self):
        """An anonymous visitor typing a patient's phone into the pre-chat
        form must NOT be merged onto the patient's thread: the merge would
        route every ops reply on that thread to the visitor. Only a
        provider-asserted phone (WhatsApp wa_id) may anchor."""
        self._wc_conn()
        phone = self.Care._safe_phone('84901234567')
        patient_thread = self.Care._find_or_create_for(
            {'phone_normalized': phone},
            {'channel': 'call', 'inbound': True,
             'event_at': fields.Datetime.now(), 'set_status': 'needs_reply'})

        started = self.Message._webchat_start(
            name='Web visitor', phone='84901234567')
        msg = self.Message._webchat_ingest(started['session'], 'xin chào')
        self.assertTrue(msg)
        conv = msg.conversation_id

        self.assertNotEqual(conv, patient_thread,
                            'volunteered phone must not merge threads')
        self.assertFalse(conv.phone_normalized,
                         'volunteered phone must not become an anchor')
        self.assertFalse(patient_thread.channel_identity_id,
                         'the patient thread must not adopt the visitor '
                         'identity')
        # The phone is still stored on the identity, display-only for ops.
        identity = msg.identity_id
        self.assertEqual(identity.peer_phone, '84901234567')
