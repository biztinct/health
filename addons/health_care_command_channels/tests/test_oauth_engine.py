# -*- coding: utf-8 -*-
"""T82–T86, T88 — the authorization engine.

The callback is exercised through ``care.channel.oauth.session._handle_callback``,
the model method the controller wraps: no HttpCase anywhere in this module
(ledger §5.32).
"""
import base64
import hashlib
from datetime import timedelta
from unittest.mock import patch

import psycopg2

from odoo import fields
from odoo.exceptions import UserError
from odoo.modules.registry import Registry

from odoo.addons.health_care_command_channels.models.care_channel_connection import (
    REFRESH_LOCK_CLASS,
)
from odoo.tests import tagged

from odoo.addons.health_care_command_channels.services import adapters
from odoo.addons.health_care_command_channels.services import channel_crypto

from .common import ChannelHubCase


@tagged('post_install', '-at_install')
class TestOauthEngine(ChannelHubCase):

    # ------------------------------------------------------------------
    # T82 — the raw state leaves the server exactly once
    # ------------------------------------------------------------------
    def test_82_session_create(self):
        conn = self._conn('zalo')
        result = self.Session.create_for(conn, redirect_target='/odoo/care-command')

        state = result['state']
        self.assertTrue(state)
        self.assertEqual(result['code_challenge_method'], 'S256')

        session = self.Session.browse(result['session_id'])
        self.assertEqual(session.provider, 'zalo')
        self.assertEqual(session.user_id, self.env.user)
        self.assertEqual(session.company_id, conn.company_id)
        self.assertFalse(session.used_at)
        self.assertEqual(session.outcome, 'pending')

        # The database holds the HASH, never the state itself.
        self.env.flush_all()
        self.env.cr.execute(
            'SELECT state_hash FROM care_channel_oauth_session WHERE id = %s',
            (session.id,))
        stored = self.env.cr.fetchone()[0]
        self.assertEqual(
            stored, hashlib.sha256(state.encode('utf-8')).hexdigest())
        self.assertNotEqual(stored, state)

        # PKCE per RFC 7636: challenge = base64url(sha256(verifier)), unpadded.
        verifier = session._get_pkce_verifier()
        self.assertTrue(verifier)
        expected = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode('ascii')).digest()
        ).rstrip(b'=').decode('ascii')
        self.assertEqual(result['code_challenge'], expected)

        # The verifier is encrypted at rest.
        self.env.cr.execute(
            'SELECT pkce_verifier_enc FROM care_channel_oauth_session '
            'WHERE id = %s', (session.id,))
        self.assertTrue(self.env.cr.fetchone()[0].startswith(
            channel_crypto.TOKEN_PREFIX))

        # Opening an attempt is auditable.
        self.assertTrue(self.Audit.search_count([
            ('connection_id', '=', conn.id), ('event', '=', 'connect_start')]))

        # A channel with no provider sign-in cannot open one at all.
        with self.assertRaises(UserError):
            self.Session.create_for(self._conn('webchat'))

    # ------------------------------------------------------------------
    # T83 — single use, and every failure looks identical
    # ------------------------------------------------------------------
    def test_83_consume_single_use(self):
        conn = self._conn('zalo')
        state = self.Session.create_for(conn)['state']

        session = self.Session._consume(state)
        self.assertTrue(session)
        self.assertTrue(session.used_at)

        # Replay is dead...
        self.assertIsNone(self.Session._consume(state))
        # ...an unknown state is dead...
        self.assertIsNone(self.Session._consume('never-issued'))
        self.assertIsNone(self.Session._consume(''))
        self.assertIsNone(self.Session._consume(None))

        # ...and so is an expired one. All four return exactly None: the
        # caller cannot tell which case it hit (no oracle).
        state2 = self.Session.create_for(conn)['state']
        session2 = self.Session.search(
            [('state_hash', '=',
              hashlib.sha256(state2.encode('utf-8')).hexdigest())])
        session2.write({'expires_at': fields.Datetime.now() - timedelta(minutes=1)})
        self.assertIsNone(self.Session._consume(state2))
        self.assertEqual(session2.outcome, 'expired')
        self.assertTrue(session2.used_at, 'an expired state must also be burned')

    # ------------------------------------------------------------------
    # T84 — callback logic (controller-free)
    # ------------------------------------------------------------------
    def test_84_handle_callback(self):
        conn = self._conn('zalo')

        # (a) The user said no.
        state = self.Session.create_for(conn)['state']
        result = self.Session._handle_callback(
            'zalo', {'state': state, 'error': 'access_denied'})
        self.assertEqual(result['outcome'], 'denied')
        self.assertFalse(result['ok'])
        self.assertEqual(result['channel'], 'zalo')
        self.assertTrue(self.Audit.search_count([
            ('connection_id', '=', conn.id), ('event', '=', 'callback_denied')]))

        # (b) Re-using a consumed state is generic — same page as unknown.
        self.assertEqual(
            self.Session._handle_callback('zalo', {'state': state}),
            {'outcome': 'generic', 'ok': False, 'channel': False})

        # (c) Unknown / missing state: identical.
        self.assertEqual(
            self.Session._handle_callback('zalo', {'state': 'nope'})['outcome'],
            'generic')
        self.assertEqual(
            self.Session._handle_callback('zalo', {})['outcome'], 'generic')

        # (d) Provider mismatch: also generic, and the state is burned.
        state = self.Session.create_for(conn)['state']
        self.assertEqual(
            self.Session._handle_callback('meta', {'state': state})['outcome'],
            'generic')
        self.assertIsNone(self.Session._consume(state))

        # (e) CC-A adapters are declaration-only, so a real exchange reports
        #     an honest error rather than pretending to have connected.
        state = self.Session.create_for(conn)['state']
        self.assertEqual(
            self.Session._handle_callback(
                'zalo', {'state': state, 'code': 'irrelevant'})['outcome'],
            'error')

        # (f) With an adapter that DOES exchange, the happy path completes.
        class _WorkingZalo(adapters.ZaloAdapter):
            def handle_callback(self, session, params):
                return {'next_step': 'select_resource'}

        state = self.Session.create_for(conn)['state']
        with patch.dict(adapters.CHANNEL_ADAPTERS, {'zalo': _WorkingZalo}):
            result = self.Session._handle_callback(
                'zalo', {'state': state, 'code': 'irrelevant'})
        self.assertEqual(result, {'outcome': 'ok', 'ok': True, 'channel': 'zalo'})
        self.assertTrue(self.Audit.search_count([
            ('connection_id', '=', conn.id), ('event', '=', 'callback_ok')]))

    # ------------------------------------------------------------------
    # T85 — refresh lock + fresh-cursor persistence
    # ------------------------------------------------------------------
    def test_85_refresh_lock_and_fresh_persist(self):
        """NOTE on what a TransactionCase can and cannot prove here.

        Odoo opens every connection at **REPEATABLE READ**
        (``sql_db.py`` imports ``ISOLATION_LEVEL_REPEATABLE_READ``), so this
        test's transaction works from a snapshot taken at setUp: a row another
        connection commits afterwards is INVISIBLE to it, and a row this
        transaction created is invisible to everybody else. A genuine
        two-worker lock race therefore cannot be staged — our
        ``FOR UPDATE NOWAIT`` would simply match zero rows and take no lock.
        The contended branch is driven instead by making the NOWAIT statement
        raise exactly what PostgreSQL raises; what is under test is our
        HANDLING (no exception escapes, the callable does not run, the
        transaction stays usable), which is the part we wrote.

        Part (c) works around the same isolation rule by keeping the whole
        round trip outside this transaction: a committed fixture row, the real
        fresh-cursor write, and a read-back on a THIRD cursor with its own
        snapshot. It is deleted again in the finally block (ledger §5.34).
        """
        conn = self._conn('telegram')

        # (a) Real SQL, real lock, callable runs under it.
        calls = []
        self.assertEqual(
            conn._with_refresh_lock(lambda: calls.append(1) or 'done'), 'done')
        self.assertEqual(len(calls), 1)

        # (b) Another worker is already refreshing ⇒ 'locked'. Never a raise,
        #     and the callable must NOT run — a second rotation would burn
        #     Zalo's single-use refresh token.
        #
        #     CC-D review: this is REAL two-connection contention now, not a
        #     mocked LockNotAvailable. The lock became advisory (§5.74: a row
        #     lock deadlocked against the fresh cursor that persists the
        #     rotation), and an advisory key is just an integer — so a second
        #     cursor can contend for it without needing to SEE this
        #     transaction's uncommitted row, which is precisely what §5.63
        #     made impossible for the old row lock. There is also no aborted
        #     statement to absorb any more: pg_try_advisory_xact_lock returns
        #     false rather than raising.
        #     A DIFFERENT record, deliberately: an advisory *xact* lock is held
        #     until the transaction ends, so this transaction still owns the
        #     key it took in (a) — and a second cursor asking for that same key
        #     would be refused, which would prove the fixture rather than the
        #     code. (Assert that property here rather than tiptoe around it.)
        other = self._conn('whatsapp')
        ran = []
        with Registry(self.env.cr.dbname).cursor() as cr2:
            cr2.execute('SELECT pg_try_advisory_xact_lock(%s, %s)',
                        (REFRESH_LOCK_CLASS, conn.id))
            self.assertFalse(
                cr2.fetchone()[0],
                'the key taken in (a) is held until this transaction ends')
            cr2.execute('SELECT pg_try_advisory_xact_lock(%s, %s)',
                        (REFRESH_LOCK_CLASS, other.id))
            self.assertTrue(cr2.fetchone()[0],
                            'the contending worker must get the key first')
            self.assertEqual(other._with_refresh_lock(lambda: ran.append(1)),
                             'locked')
        self.assertFalse(ran)
        # ...and once the contender's transaction ends, the key frees up.
        self.assertEqual(other._with_refresh_lock(lambda: 'ran'), 'ran')
        # The transaction is untouched and still usable.
        self.assertTrue(self._conn('email').id)

        # (c) Rotated credentials are written through the dedicated cursor path
        #     and land encrypted, with the scopes the provider reported.
        dbname = self.env.cr.dbname
        with Registry(dbname).cursor() as cr0:
            cr0.execute(
                "INSERT INTO care_channel_connection "
                "(channel, company_id, state, webhook_state, active, "
                " consecutive_failures) "
                "VALUES ('webchat', %s, 'ready', 'none', true, 0) RETURNING id",
                (self.env.company.id,))
            committed_id = cr0.fetchone()[0]
        try:
            self.assertTrue(
                self.Conn.browse(committed_id)._persist_refreshed_tokens(
                    access_token='rotated-access-1',
                    refresh_token='rotated-refresh-1',
                    granted_scopes='oa.manage'))
            with Registry(dbname).cursor() as cr3:
                cr3.execute('SELECT access_token_enc, refresh_token_enc, '
                            'granted_scopes FROM care_channel_connection '
                            'WHERE id = %s', (committed_id,))
                access_enc, refresh_enc, scopes = cr3.fetchone()
            self.assertTrue(access_enc.startswith(channel_crypto.TOKEN_PREFIX))
            self.assertNotIn('rotated-access-1', access_enc)
            self.assertNotIn('rotated-refresh-1', refresh_enc)
            self.assertEqual(scopes, 'oa.manage')
            self.assertEqual(channel_crypto.decrypt(self.env, access_enc),
                             'rotated-access-1')
            self.assertEqual(channel_crypto.decrypt(self.env, refresh_enc),
                             'rotated-refresh-1')
        finally:
            with Registry(dbname).cursor() as cr4:
                cr4.execute('DELETE FROM care_channel_audit '
                            'WHERE connection_id = %s', (committed_id,))
                cr4.execute('DELETE FROM care_channel_connection '
                            'WHERE id = %s', (committed_id,))

    # ------------------------------------------------------------------
    # T86 — the redirect allowlist (no open redirects on a callback)
    # ------------------------------------------------------------------
    def test_86_redirect_allowlist(self):
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('web.base.url', 'https://care.biztinct.com')
        icp.set_param('channel_hub.allowed_redirect_hosts', '')

        allowed = self.Session._allowed_redirect
        self.assertTrue(allowed('/odoo/care-command'))
        self.assertTrue(allowed(None))
        self.assertTrue(allowed('https://care.biztinct.com/odoo/action-1'))
        self.assertFalse(allowed('https://evil.example.com/steal'))
        self.assertFalse(allowed('//evil.example.com/steal'))
        # Browsers normalize '/\' to '//' — the backslash disguise must be
        # refused too (CC-A review finding #3).
        self.assertFalse(allowed('/\\evil.example.com/steal'))
        self.assertFalse(allowed('javascript:alert(1)'))
        self.assertFalse(allowed(42))

        icp.set_param('channel_hub.allowed_redirect_hosts',
                      'partner.example.com, other.example.com')
        self.assertTrue(allowed('https://partner.example.com/back'))
        self.assertTrue(allowed('https://other.example.com/back'))
        self.assertFalse(allowed('https://evil.example.com/steal'))

        # A rejected target never opens a session, and the error text is fixed
        # (it never echoes the URL back).
        with self.assertRaises(UserError):
            self.Session.create_for(self._conn('zalo'),
                                    redirect_target='https://evil.example.com/x')

    # ------------------------------------------------------------------
    # T88 — session purge cron
    # ------------------------------------------------------------------
    def test_88_purge_cron(self):
        conn = self._conn('zalo')
        old = self.Session.browse(self.Session.create_for(conn)['session_id'])
        conn2 = self._conn('fb')
        fresh = self.Session.browse(self.Session.create_for(conn2)['session_id'])

        # create_date is ORM-managed: backdate it in raw SQL, flushing first
        # and invalidating after (ledger §5.9).
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE care_channel_oauth_session SET create_date = %s WHERE id = %s",
            (fields.Datetime.now() - timedelta(hours=30), old.id))
        self.env.invalidate_all()

        purged = self.Session._cron_purge_oauth_sessions()
        self.assertGreaterEqual(purged, 1)
        self.assertFalse(old.exists())
        self.assertTrue(fresh.exists())
