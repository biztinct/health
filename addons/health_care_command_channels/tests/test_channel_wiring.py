# -*- coding: utf-8 -*-
"""T90–T94 — the wiring CC-B adds on top of the phase-6 spine.

These are the tests that make the framework *worth having*: that a channel can
only send when the connection says so, that real traffic — not an operator's
opinion — is what proves a channel works, that the dock is company-honest, and
that the platform plane fails closed when nobody has seeded a provider app.
"""
from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.health_care_command_channels.services.webhook_verify import (
    meta_challenge, verify_meta, verify_telegram,
)

from .common_spine import META_VERIFY_TOKEN, TG_PATH_SECRET, ChannelSpineCase


@tagged('post_install', '-at_install')
class TestChannelWiring(ChannelSpineCase):

    def _tg_conversation(self):
        conn = self._tg_conn()
        self.Message._dispatch_connection(conn, self.tg_payload())
        conv = self.conv_of(self.identity_of(conn, '555001'))
        return conn, conv

    @staticmethod
    def tg_ok(message_id=7):
        # A distinct provider id per send: two outgoing rows sharing one
        # external_message_id would (correctly) hit the dedupe index.
        return {'ok': True,
                'result': {'message_id': message_id, 'chat': {'id': 555001}}}

    # ==================================================================
    # T90 — send gating follows the connection state, and only that
    # ==================================================================
    def test_90_send_gating(self):
        conn, conv = self._tg_conversation()

        # (a) ready sends.
        with self.mock_post(response=self.tg_ok(101)):
            self.assertEqual(
                self.Care.action_send_channel(conv.id, 'telegram', 'a')['direction'],
                'out')
        self.assertEqual(conv._capabilities().get('ext_reply_channel'),
                         'telegram')

        # (b) expiring still sends: a grant that dies next week works today,
        # and going mute would be the worse failure.
        conn._transition('expiring', reason='test')
        self.assertEqual(conv._capabilities().get('ext_reply_channel'),
                         'telegram')
        with self.mock_post(response=self.tg_ok(102)):
            self.Care.action_send_channel(conv.id, 'telegram', 'b')

        # (c) action_required does NOT send — and says so cleanly.
        conn.invalidate_recordset(['state'])
        conn._transition('action_required', reason='test')
        self.assertNotIn('ext_reply_channel', conv._capabilities())
        with self.assertRaises(UserError):
            self.Care.action_send_channel(conv.id, 'telegram', 'c')

        # (d) disabled does not send.
        conn._transition('disabled', reason='test')
        with self.assertRaises(UserError):
            self.Care.action_send_channel(conv.id, 'telegram', 'd')

        # (e) a conversation with no channel identity at all cannot use the
        # generic send path, whatever channel it claims.
        plain = self.Care._find_or_create_for(
            {'email_normalized': 't90@example.com'},
            {'channel': 'email', 'inbound': True})
        with self.assertRaises(UserError):
            self.Care.action_send_channel(plain.id, 'telegram', 'e')

        # (f) the channel argument must match the conversation's own channel.
        conn._transition('authorizing', reason='test')
        conn._transition('ready', reason='test')
        with self.assertRaises(UserError):
            self.Care.action_send_channel(conv.id, 'whatsapp', 'f')

    # ==================================================================
    # T91 — traffic is what proves a channel works
    # ==================================================================
    def test_91_traffic_to_truth(self):
        conn = self._wa_conn()
        conn._internal().write({'webhook_state': 'pending',
                                'last_inbound_at': False,
                                'last_outbound_at': False})

        # (a) inbound: webhook verified + inbound proven, from real traffic.
        self.Message._dispatch_meta('whatsapp', self.wa_payload())
        conn.invalidate_recordset()
        self.assertTrue(conn.last_inbound_at)
        self.assertTrue(conn.last_webhook_at)
        self.assertEqual(conn.webhook_state, 'verified')
        statuses = {c.check_key: c.status for c in conn.readiness_check_ids}
        self.assertEqual(statuses.get('webhook_verified'), 'pass')
        self.assertEqual(statuses.get('inbound_ok'), 'pass')

        conv = self.conv_of(self.identity_of(conn, '84901234567'))

        # (b) a successful send proves outbound.
        with self.mock_post(response={'messages': [{'id': 'wamid.T91'}]}):
            self.Care.action_send_channel(conv.id, 'whatsapp', 'hello')
        conn.invalidate_recordset()
        self.assertTrue(conn.last_outbound_at)
        statuses = {c.check_key: c.status for c in conn.readiness_check_ids}
        self.assertEqual(statuses.get('outbound_ok'), 'pass')
        self.assertEqual(conn.state, 'ready')

        # (c) a 401 costs the connection its authorization: the tenant has to
        # act, and the composer stops offering a send that cannot work.
        # try/except, not assertRaises: Odoo's assertRaises rolls back every
        # write made before the raise (ledger §5.8) — including the readiness
        # collapse this test exists to prove.
        with self.mock_post(response={'error': {'code': 190,
                                                'message': 'expired'}},
                            status=401):
            try:
                self.Care.action_send_channel(conv.id, 'whatsapp', 'again')
                self.fail('a 401 must surface as a UserError')
            except UserError:
                pass
        conn.invalidate_recordset()
        statuses = {c.check_key: c.status for c in conn.readiness_check_ids}
        self.assertEqual(statuses.get('authorization_valid'), 'fail')
        self.assertEqual(conn.state, 'action_required')
        self.assertEqual(conn.health_status, 'permission_lost')
        conv.invalidate_recordset()
        self.assertNotIn('ext_reply_channel', conv._capabilities())

        # The stored reason is redacted, never a raw provider body.
        self.assertTrue(conn.last_error_redacted)

        # (d) a webhook for a connection that is no longer ingestable is
        # dropped with an audit row rather than silently filling the inbox.
        conn._transition('disabled', reason='test')
        before = self.Message.sudo().search_count([])
        counts = self.Message._dispatch_meta(
            'whatsapp', self.wa_payload(mid='wamid.AFTER-DISABLE'))
        self.assertEqual(counts['ignored'], 1)
        self.assertEqual(self.Message.sudo().search_count([]), before)
        self.assertTrue(self.Audit.search_count([
            ('connection_id', '=', conn.id), ('event', '=', 'webhook_ignored')]))

    # ==================================================================
    # T92 — the dock is company-scoped
    # ==================================================================
    def test_92_channel_keys_company_scope(self):
        base = ('zalo', 'call', 'email', 'zns')
        self._wa_conn()  # company 1 only

        keys_a = self.Care.with_company(self.company).sudo()._channel_keys()
        keys_b = self.Care.with_company(self.company2).sudo()._channel_keys()
        self.assertIn('whatsapp', keys_a)
        self.assertNotIn('whatsapp', keys_b)
        for key in base:
            self.assertIn(key, keys_a)
            self.assertIn(key, keys_b)

        # A draft (never-connected) connection in company 2 changes nothing.
        self._conn('telegram', company=self.company2, state='not_connected')
        self.assertNotIn(
            'telegram', self.Care.with_company(self.company2)._channel_keys())

        # ...and a ready one in company 2 activates it THERE only.
        tg2 = self._conn('whatsapp', company=self.company2, state='testing',
                         resource_external_id='PHONE_ID_B')
        self._seed_checks(tg2)
        self.assertIn('whatsapp',
                      self.Care.with_company(self.company2)._channel_keys())
        self.assertIn('whatsapp',
                      self.Care.with_company(self.company)._channel_keys())

    # ==================================================================
    # T93 — the platform plane fails closed
    # ==================================================================
    def test_93_platform_plane_fail_closed(self):
        # No meta platform app at all (the state of every fresh database).
        self.meta_app.write({'active': False})
        app = self.env['channel.platform.app']._get_for_provider('meta')
        self.assertFalse(app)

        raw = self.raw(self.wa_payload())
        self.assertIsNone(meta_challenge(app, 'subscribe', META_VERIFY_TOKEN, '1'))
        # A valid-LOOKING signature (correctly formed, wrong provenance) is
        # still refused: with no app secret there is nothing to verify against.
        self.assertFalse(verify_meta(app, raw, self.meta_signature(raw)))

        # ...and the header variants an attacker actually sends are all
        # refused too (a TransactionCase cannot drive the controller, so the
        # verifier IS the gate under test — the live-route 403s are browser/
        # curl evidence).
        self._wa_conn()
        self.assertFalse(verify_meta(app, raw, None))
        self.assertFalse(verify_meta(app, raw, 'sha256='))
        self.assertFalse(verify_meta(app, raw, 'sha256=' + '0' * 64))

        # Telegram: a path secret nobody registered resolves to no connection,
        # and no connection means no verification.
        unknown = self.Conn.sudo().search([
            ('channel', '=', 'telegram'),
            ('webhook_path_secret', '=', 'never-registered')], limit=1)
        self.assertFalse(unknown)
        self.assertFalse(verify_telegram(unknown, 'never-registered', None))
        self._tg_conn()
        self.assertFalse(verify_telegram(
            self.Conn.sudo().search([('channel', '=', 'telegram')], limit=1),
            'never-registered', TG_PATH_SECRET))

    # ==================================================================
    # T94 — reply templates cover the new channels
    # ==================================================================
    def test_94_reply_templates(self):
        Template = self.env['care.reply.template']
        anywhere = Template.create({
            'name': 'T94 any', 'body': 'Cảm ơn bạn.', 'channel': 'any',
            'company_id': self.company.id})
        whatsapp = Template.create({
            'name': 'T94 whatsapp', 'body': 'Chào bạn trên WhatsApp.',
            'channel': 'whatsapp', 'company_id': self.company.id})
        telegram = Template.create({
            'name': 'T94 telegram', 'body': 'Chào bạn trên Telegram.',
            'channel': 'telegram', 'company_id': self.company.id})
        # The four new values are legal on the model at all — that is the
        # selection_add this phase adds.
        for value in ('whatsapp', 'fb', 'telegram', 'webchat'):
            self.assertIn(value, dict(Template._fields['channel'].selection))

        conn = self._wa_conn()
        self.Message._dispatch_meta('whatsapp', self.wa_payload())
        conv = self.conv_of(self.identity_of(conn, '84901234567'))
        self.assertEqual(conv.channel_effective, 'whatsapp')

        ids = {row['id'] for row in conv._reply_templates()}
        self.assertIn(anywhere.id, ids)
        self.assertIn(whatsapp.id, ids)
        self.assertNotIn(telegram.id, ids,
                         'another channel\'s templates must not leak in')
