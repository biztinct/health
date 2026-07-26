# -*- coding: utf-8 -*-
"""T142–T149 — Email on the connection framework (CC-F).

TransactionCase only (ledger §5.32), and nothing here reaches a network.
That is easier than it sounds for this channel: Odoo's Gmail/Outlook mixins
build their consent URL from ``ir.config_parameter`` and an HMAC of
``(model, id)`` with **no HTTP at all**, so T143/T144 exercise the real
compute rather than a mock of ourselves. The only two things mocked are the
places that genuinely leave the box: ``ir.mail_server.send_email`` (T145) and
nothing else.

The provider callback is simulated by writing the refresh token onto the mail
server row — which is *precisely* what core's ``/google_gmail/confirm``
controller does (google_gmail/controllers/main.py, ``record.write({...
'google_gmail_refresh_token': refresh_token})``). Simulating the effect of a
core controller is fair; asserting against a mock of our own code is not, and
T85 already paid for that lesson.

Two rules from the ledger drive the shape below:

* §5.78 — a required check that can leave ``pass`` is a traffic kill switch.
  T147 drives a connection all the way to ``ready`` FIRST, because a test that
  stops at ``configuring`` structurally cannot see the demotion it claims to
  cover.
* §5.8/§5.65 — failure paths that must leave evidence are asserted with
  ``try/except``, never ``assertRaises`` (which rolls the evidence back), and
  ``assertRaises`` cannot take a tuple of classes here anyway (§5.70).
"""
import time
from unittest.mock import patch

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from odoo.addons.health_care_command_channels.services.adapters import (
    EMAIL_PLATFORM_PARAMS, EMAIL_PROVIDER_SETTING, ChannelSendError,
)

from .common_spine import ChannelSpineCase

HTTPS_BASE = 'https://care.example.test'

# Fixtures. Not one of these is a real Google credential.
GOOGLE_CLIENT_ID = 'fixture-client-id.apps.googleusercontent.com'
GOOGLE_CLIENT_SECRET = 'GOCSPX-fixture-secret-value'
MAILBOX = 'lienhe@vietuc.test'
REFRESH_TOKEN = 'gmail-refresh-token-fixture'


@tagged('post_install', '-at_install')
class TestEmailCenter(ChannelSpineCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.icp = cls.env['ir.config_parameter'].sudo()
        cls.icp.set_param('web.base.url', HTTPS_BASE)
        # A clean third plane: CC-F is the first phase to touch these keys, so
        # a value left by an administrator would silently satisfy T143.
        for id_key, secret_key in EMAIL_PLATFORM_PARAMS.values():
            cls.icp.set_param(id_key, '')
            cls.icp.set_param(secret_key, '')

    # -- helpers -------------------------------------------------------
    def _google_app(self):
        """The operator's Google app. Created PER TEST, never in setUpClass:
        T142 has to observe the state of vietuat today, which is its absence."""
        app = self.App.create({'provider': 'google',
                               'client_id': GOOGLE_CLIENT_ID})
        app.action_set_secret(GOOGLE_CLIENT_SECRET)
        return app

    def _email_conn(self):
        conn = self.Conn.center_begin('email')
        return self.Conn.browse(conn['connection_id'])

    def _sign_in(self, conn, refresh=REFRESH_TOKEN):
        """Simulate what core's own OAuth callback writes on the server row."""
        server = conn.sudo()._get_adapter().mail_server()
        server.sudo().write({
            'google_gmail_refresh_token': refresh,
            'google_gmail_access_token': 'access-fixture',
            # int4, not bigint — a far-future sentinel overflows the column.
            'google_gmail_access_token_expiration': int(time.time()) + 3600,
        })
        return server

    def _connected(self):
        """A live email channel, driven to `ready` the way a tenant would."""
        self._google_app()
        conn = self._email_conn()
        self.Conn.center_email_start(conn.id, 'google', MAILBOX)
        self._sign_in(conn)
        self.Conn.center_email_status(conn.id)
        # outbound + inbound are the two remaining required checks.
        with patch.object(type(self.env['ir.mail_server']), 'send_email',
                          lambda self, message, **kw: 'fixture-message-id'):
            self.Conn.center_test(conn.id)
        conn.sudo()._get_adapter().fetch_server()._care_note_inbound()
        conn.invalidate_recordset()
        self.assertEqual(conn.state, 'ready',
                         'the fixture must reach ready or T147 cannot see a '
                         'demotion (ledger §5.78)')
        return conn

    # =================================================================
    # T142 — no platform app ⇒ honestly unavailable. This IS vietuat today.
    # =================================================================
    def test_142_email_not_available_without_platform_app(self):
        self.assertFalse(
            self.App._get_for_provider('google'),
            'fixture guard: this test asserts the ABSENCE of a google app')
        card = next(c for c in self.Conn.center_overview()
                    if c['channel'] == 'email')
        self.assertFalse(card['available'])
        self.assertEqual(card['primary_action'], 'unavailable')
        self.assertEqual(card['primary_label'], 'Not available yet')
        # Implemented but not offerable — the two gates are separate claims.
        self.assertTrue(card['implemented'])

        raised = False
        try:
            self.Conn.center_begin('email')
        except UserError:
            raised = True
        self.assertTrue(raised, 'center_begin must refuse an unavailable channel')
        self.assertFalse(self.Conn._center_connection('email'),
                         'a refused begin must leave no connection behind')

    # =================================================================
    # T143 — the platform app mirrors INTO the mixin's keys, one way
    # =================================================================
    def test_143_platform_credentials_mirror_one_way_only(self):
        app = self._google_app()
        conn = self._email_conn()
        adapter = conn.sudo()._get_adapter()
        id_key, secret_key = EMAIL_PLATFORM_PARAMS['google']

        self.assertFalse(self.icp.get_param(id_key))
        self.assertTrue(adapter.mirror_platform_credentials('google'))
        self.assertEqual(self.icp.get_param(id_key), GOOGLE_CLIENT_ID)
        self.assertEqual(self.icp.get_param(secret_key), GOOGLE_CLIENT_SECRET)

        # Idempotent: a second call changes nothing.
        self.assertFalse(adapter.mirror_platform_credentials('google'))

        # ...and NEVER the other way round. An operator rotating the app must
        # win; a config parameter edited by hand must not rewrite the plane.
        self.icp.set_param(id_key, 'tampered-client-id')
        self.icp.set_param(secret_key, 'tampered-secret')
        adapter.mirror_platform_credentials('google')
        self.assertEqual(app.client_id, GOOGLE_CLIENT_ID)
        self.assertEqual(app._get_secret(), GOOGLE_CLIENT_SECRET)
        self.assertEqual(self.icp.get_param(id_key), GOOGLE_CLIENT_ID,
                         'the mirror must restore the operator value')

        # The secret reaches no return value and no readable column.
        info = self.Conn.center_email_info(conn.id)
        self.assertNotIn(GOOGLE_CLIENT_SECRET, str(info))
        self.assertNotIn(GOOGLE_CLIENT_SECRET, str(self.Conn.center_overview()))

    # =================================================================
    # T144 — sign-in creates both servers; a failed sign-in stores nothing
    # =================================================================
    def test_144_signin_creates_servers_and_selects_the_mailbox(self):
        self._google_app()
        conn = self._email_conn()
        result = self.Conn.center_email_start(conn.id, 'google', MAILBOX)

        # The consent URL is built by Odoo's own mixin: public app id, our
        # redirect, a CSRF-signed state — and no secret.
        self.assertIn('accounts.google.com', result['url'])
        self.assertIn(GOOGLE_CLIENT_ID, result['url'])
        self.assertNotIn(GOOGLE_CLIENT_SECRET, result['url'])

        adapter = conn.sudo()._get_adapter()
        server, fetcher = adapter.mail_server(), adapter.fetch_server()
        self.assertTrue(server and fetcher)
        self.assertEqual(server.smtp_authentication, 'gmail')
        self.assertEqual(server.smtp_user, MAILBOX)
        self.assertEqual(fetcher.server_type, 'gmail')
        self.assertEqual(fetcher.state, 'draft',
                         'nothing may be polled before a grant exists')
        self.assertFalse(adapter.signed_in())
        conn.invalidate_recordset()
        self.assertEqual(conn.state, 'authorizing')

        # Nothing proven yet — an unfinished sign-in is not a connection.
        status = self.Conn.center_email_status(conn.id)
        self.assertFalse(status['signed_in'])
        self.assertEqual(conn.state, 'authorizing')

        # Now the provider's callback lands.
        self._sign_in(conn)
        status = self.Conn.center_email_status(conn.id)
        self.assertTrue(status['signed_in'])
        self.assertEqual(status['mailbox'], MAILBOX)
        conn.invalidate_recordset()
        self.assertEqual(conn.state, 'testing')
        self.assertEqual(conn.resource_external_id, MAILBOX)
        self.assertEqual(adapter.fetch_server().state, 'done',
                         'only a real grant may start the IMAP poll')
        statuses = {c.check_key: c.status for c in conn.readiness_check_ids}
        self.assertEqual(statuses.get('authorization_valid'), 'pass')
        self.assertEqual(statuses.get('resource_selected'), 'pass')

        # Idempotent: a second start re-points the same two rows.
        self.Conn.center_email_start(conn.id, 'google', MAILBOX)
        self.assertEqual(
            self.env['ir.mail_server'].sudo().with_context(
                active_test=False).search_count(
                [('care_connection_id', '=', conn.id)]), 1)

    def test_144b_a_bad_mailbox_stores_nothing(self):
        self._google_app()
        conn = self._email_conn()
        for bad in ('', 'not-an-address', 'a@b', 'x@y.z, evil@attacker.test',
                    'x@y.test\nBcc: evil@attacker.test'):
            raised = False
            try:
                self.Conn.center_email_start(conn.id, 'google', bad)
            except UserError:
                raised = True
            self.assertTrue(raised, 'refused: %r' % bad)
        self.assertFalse(conn.sudo()._get_adapter().mail_server(),
                         'a refused address must leave no mail server behind')

    # =================================================================
    # T145 — the test send goes to the tenant's OWN mailbox
    # =================================================================
    def test_145_center_test_sends_to_the_tenant_mailbox(self):
        self._google_app()
        conn = self._email_conn()
        self.Conn.center_email_start(conn.id, 'google', MAILBOX)
        self._sign_in(conn)
        self.Conn.center_email_status(conn.id)

        sent = {}

        def _send(self, message, **kwargs):
            sent['to'] = message['To']
            sent['from'] = message['From']
            sent['server'] = kwargs.get('mail_server_id')
            return 'fixture-message-id'

        # A PLAIN function, never a second autospec (ledger §5.76).
        with patch.object(type(self.env['ir.mail_server']), 'send_email', _send):
            result = self.Conn.center_test(conn.id)
        self.assertEqual(sent['to'], MAILBOX)
        self.assertEqual(sent['from'], MAILBOX)
        self.assertEqual(sent['server'],
                         conn.sudo()._get_adapter().mail_server().id)
        self.assertEqual(result['sent_to'], MAILBOX)
        conn.invalidate_recordset()
        statuses = {c.check_key: c.status for c in conn.readiness_check_ids}
        self.assertEqual(statuses.get('outbound_ok'), 'pass')

    def test_145b_a_failed_send_records_redacted_evidence(self):
        self._google_app()
        conn = self._email_conn()
        self.Conn.center_email_start(conn.id, 'google', MAILBOX)
        self._sign_in(conn)
        self.Conn.center_email_status(conn.id)

        def _boom(self, message, **kwargs):
            raise Exception(
                'SMTP AUTH failed: access_token=%s is invalid' % REFRESH_TOKEN)

        raised = False
        with patch.object(type(self.env['ir.mail_server']), 'send_email', _boom):
            # try/except, never assertRaises: the evidence written before the
            # raise has to survive to be asserted (§5.8/§5.65).
            try:
                self.Conn.center_test(conn.id)
            except UserError as exc:
                raised = True
                self.assertNotIn(REFRESH_TOKEN, str(exc))
        self.assertTrue(raised)
        conn.invalidate_recordset()
        self.assertTrue(conn.last_error_redacted)
        self.assertNotIn(REFRESH_TOKEN, conn.last_error_redacted)
        statuses = {c.check_key: c.status for c in conn.readiness_check_ids}
        self.assertNotEqual(statuses.get('outbound_ok'), 'pass',
                            'a failed send must never claim outbound works')
        audit = self.Audit.sudo().search(
            [('connection_id', '=', conn.id), ('event', '=', 'test_fail')])
        self.assertTrue(audit)
        self.assertNotIn(REFRESH_TOKEN, str(audit.mapped('detail_redacted')))

    # =================================================================
    # T146 — a real fetched message is what flips inbound_ok
    # =================================================================
    def test_146_a_fetched_message_proves_inbound(self):
        self._google_app()
        conn = self._email_conn()
        self.Conn.center_email_start(conn.id, 'google', MAILBOX)
        self._sign_in(conn)
        self.Conn.center_email_status(conn.id)
        with patch.object(type(self.env['ir.mail_server']), 'send_email',
                          lambda self, message, **kw: 'ok'):
            self.Conn.center_test(conn.id)
        conn.invalidate_recordset()
        self.assertEqual(conn.state, 'testing', 'inbound is still unproven')

        # The real seam: core sets `default_fetchmail_server_id` around every
        # message it processes from an incoming server, and that context flag
        # is what we key on. Drive it through `message_process` for real.
        fetcher = conn.sudo()._get_adapter().fetch_server()
        raw = (
            'Content-Type: text/plain\n'
            'MIME-Version: 1.0\n'
            'From: Chi Lan <lan@example.test>\n'
            'To: %s\n'
            'Subject: Toi can dat lich\n'
            'Message-Id: <fixture-inbound-1@example.test>\n'
            '\n'
            'Xin chao.\n' % MAILBOX
        )
        self.env['mail.thread'].with_context(
            default_fetchmail_server_id=fetcher.id).message_process(
            'crm.lead', raw)

        conn.invalidate_recordset()
        statuses = {c.check_key: c.status for c in conn.readiness_check_ids}
        self.assertEqual(statuses.get('inbound_ok'), 'pass')
        self.assertTrue(conn.last_inbound_at)
        self.assertEqual(conn.state, 'ready')
        # IMAP has no webhook, and claiming one would be a state nobody could
        # act on.
        self.assertEqual(conn.webhook_state, 'none')

    # =================================================================
    # T147 — §5.78: a quiet or failing poll NEVER lowers a live mailbox
    # =================================================================
    def test_147_a_quiet_poll_never_demotes_a_ready_mailbox(self):
        conn = self._connected()
        adapter = conn.sudo()._get_adapter()

        # (a) The health cron on a mailbox that received nothing today.
        self.assertTrue(adapter.health_check()['ok'])
        conn.invalidate_recordset()
        self.assertEqual(conn.state, 'ready')

        # (b) A status re-read that cannot see the grant — a transient read
        #     failure, not a revocation. It must leave every check alone.
        server = adapter.mail_server()
        stored = server.sudo().google_gmail_refresh_token
        server.sudo().write({'google_gmail_refresh_token': False})
        status = self.Conn.center_email_status(conn.id)
        self.assertFalse(status['signed_in'])
        conn.invalidate_recordset()
        statuses = {c.check_key: c.status for c in conn.readiness_check_ids}
        self.assertEqual(statuses.get('authorization_valid'), 'pass')
        self.assertEqual(statuses.get('inbound_ok'), 'pass')
        self.assertEqual(
            conn.state, 'ready',
            'a poll that could not read the grant must not drop the inbox — '
            'action_required is NOT ingestable (ledger §5.78)')
        server.sudo().write({'google_gmail_refresh_token': stored})

        # (c) The health check on the same unreadable state: reports the
        #     problem, still lowers nothing.
        server.sudo().write({'google_gmail_refresh_token': False})
        self.assertFalse(adapter.health_check()['ok'])
        conn.invalidate_recordset()
        self.assertEqual(conn.state, 'ready')
        statuses = {c.check_key: c.status for c in conn.readiness_check_ids}
        self.assertEqual(statuses.get('inbound_ok'), 'pass')

    # =================================================================
    # T148 — email chat stays on mail.message; zero channel message rows
    # =================================================================
    def test_148_email_chat_stays_on_mail_message(self):
        conn = self._connected()
        self.assertEqual(
            self.Message.sudo().search_count(
                [('connection_id', '=', conn.id)]), 0,
            'CC-F takes the boundary, not the storage — email chat belongs to '
            'mail.message and core action_send_email')

        lead = self.env['crm.lead'].create({
            'name': 'CC-F email lead', 'email_from': 'khach@example.test',
            'company_id': self.company.id})
        conv = self.Care.sudo().search([('lead_id', '=', lead.id)], limit=1)
        self.assertTrue(conv, 'the care.conversation spine still owns the thread')
        before = self.env['mail.message'].sudo().search_count(
            [('model', '=', 'crm.lead'), ('res_id', '=', lead.id)])
        self.Care.action_send_email(conv.id, 'Chào anh chị.')
        after = self.env['mail.message'].sudo().search_count(
            [('model', '=', 'crm.lead'), ('res_id', '=', lead.id)])
        self.assertEqual(after, before + 1)
        self.assertEqual(
            self.Message.sudo().search_count([('connection_id', '=', conn.id)]),
            0, 'still no care.channel.message row for email')

    # =================================================================
    # T149 — disconnect stops the poll without wiping the grant
    # =================================================================
    def test_149_disconnect_stops_traffic_and_keeps_the_grant(self):
        conn = self._connected()
        adapter = conn.sudo()._get_adapter()
        fetcher = adapter.fetch_server()
        self.assertEqual(fetcher.state, 'done')

        self.Conn.center_disconnect(conn.id)
        conn.invalidate_recordset()
        self.assertEqual(conn.state, 'disabled')
        self.assertEqual(
            adapter.fetch_server().state, 'draft',
            "Odoo's fetch cron is not ours: only draft actually stops it")
        self.assertTrue(adapter.signed_in(),
                        'turning a channel off is not revoking a grant')
        # History survives a disconnect. It belongs to the clinic.
        statuses = {c.check_key: c.status for c in conn.readiness_check_ids}
        self.assertEqual(statuses.get('inbound_ok'), 'pass')
        self.assertTrue(conn.last_inbound_at)

        # ...and coming back does not re-ask for anything.
        info = self.Conn.center_reconnect(conn.id)
        conn.invalidate_recordset()
        self.assertEqual(info['state'], 'authorizing')
        self.assertEqual(adapter.fetch_server().state, 'done')
        self.assertTrue(self.Conn.center_email_info(conn.id)['signed_in'])

    # =================================================================
    # T154a — spoof: a plain CRM user and another company's connection
    # =================================================================
    def test_154a_email_endpoints_refuse_a_spoof(self):
        conn = self._connected()
        as_user = self.Conn.with_user(self.crm_user)
        for call in (
            lambda m: m.center_email_info(conn.id),
            lambda m: m.center_email_start(conn.id, 'google', MAILBOX),
            lambda m: m.center_email_status(conn.id),
        ):
            raised = False
            try:
                call(as_user)
            except (UserError, AccessError):
                # Either class is correct — the record rule may hide the row
                # before the explicit gate runs. §5.70: never a tuple in
                # assertRaises.
                raised = True
            self.assertTrue(raised, 'a plain CRM user must be refused')

        other = self._conn('email', company=self.company2, state='testing')
        raised = False
        try:
            self.Conn.with_user(self.crm_mgr).center_email_info(other.id)
        except (UserError, AccessError):
            raised = True
        self.assertTrue(raised, "another company's connection must be refused")

    def test_154b_wrong_channel_is_refused(self):
        """An email endpoint pointed at a Telegram connection is a spoof too."""
        tg = self._tg_conn()
        raised = False
        try:
            self.Conn.center_email_info(tg.id)
        except UserError:
            raised = True
        self.assertTrue(raised)

    # =================================================================
    # An adapter with no platform app refuses rather than guessing
    # =================================================================
    def test_143b_adapter_refuses_without_a_platform_app(self):
        conn = self._conn('email', state='authorizing')
        adapter = conn.sudo()._get_adapter()
        self.assertEqual(adapter.available_providers(), [])
        raised = False
        try:
            adapter.authorize_url('google', MAILBOX)
        except ChannelSendError:
            raised = True
        self.assertTrue(raised)
        self.assertFalse(adapter.mail_server(),
                         'a refusal must not create a mail server')
        self.assertFalse(
            self.icp.get_param(EMAIL_PLATFORM_PARAMS['google'][0]),
            'and must not write the third credential plane either')

    def test_143c_settings_never_accept_a_credential(self):
        """The provider choice rides settings_json, which any manager reads."""
        self._google_app()
        conn = self._email_conn()
        self.Conn.center_email_start(conn.id, 'google', MAILBOX)
        self.assertEqual(conn.get_setting(EMAIL_PROVIDER_SETTING), 'google')
        raised = False
        try:
            conn.set_settings({'email_refresh_token': REFRESH_TOKEN})
        except UserError:
            raised = True
        self.assertTrue(raised, 'settings_json must refuse credential-shaped keys')
