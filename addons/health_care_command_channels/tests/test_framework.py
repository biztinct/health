# -*- coding: utf-8 -*-
"""T73–T81 — the two credential planes, the state machine, readiness,
the append-only audit, redaction, company isolation and the adapter registry."""
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged

from odoo.addons.health_care_command_channels.services import channel_crypto
from odoo.addons.health_care_command_channels.services.adapters import (
    CAPABILITY_KEYS, CHANNEL_ADAPTERS, CHECK_KEYS, VALID_MODES, get_adapter,
)
from odoo.addons.health_care_command_channels.services.redact import redact
from odoo.addons.health_care_command_channels.models.care_channel_connection import (
    INTERNAL_CTX,
)

from .common import ChannelHubCase


@tagged('post_install', '-at_install')
class TestChannelFramework(ChannelHubCase):

    # ------------------------------------------------------------------
    # T73 — Plane 1: uniqueness + write-only secret
    # ------------------------------------------------------------------
    def test_73_platform_app_uniqueness_and_secret(self):
        app = self.App.create({'provider': 'meta', 'client_id': '111'})

        # One ACTIVE app per provider. Pre-checked in create() so the caller
        # gets a ValidationError instead of an IntegrityError that would
        # poison the transaction (ledger §5.3).
        with self.assertRaises(ValidationError):
            self.App.create({'provider': 'meta', 'client_id': '222'})

        # Archiving frees the slot — that is what the partial index means.
        app.write({'active': False})
        app2 = self.App.create({'provider': 'meta', 'client_id': '222'})
        self.assertTrue(app2.id)

        # The wizard is the only writer, and it stores nothing readable.
        wizard = self.env['channel.platform.app.secret.wizard'].create({
            'app_id': app2.id, 'secret': 'super-secret-value-9911'})
        wizard.action_apply()

        self.assertEqual(app2.secret_hint, '••••9911')
        self.assertTrue(app2.has_secret)
        self.assertFalse(wizard.secret, 'plaintext must not linger on the wizard')

        # Read the raw column: the plaintext is not in the database.
        self.env.flush_all()
        self.env.cr.execute(
            'SELECT client_secret_enc FROM channel_platform_app WHERE id = %s',
            (app2.id,))
        stored = self.env.cr.fetchone()[0]
        self.assertTrue(stored.startswith(channel_crypto.TOKEN_PREFIX))
        self.assertNotIn('super-secret-value-9911', stored)
        self.assertEqual(app2._get_secret(), 'super-secret-value-9911')

        # Empty secrets are refused rather than silently clearing the grant.
        with self.assertRaises(UserError):
            app2.action_set_secret('   ')

    # ------------------------------------------------------------------
    # T74 — secrets are not reachable from the RPC surface
    # ------------------------------------------------------------------
    def test_74_secret_non_exposure(self):
        conn = self._conn('telegram', state='authorizing')
        conn.action_set_secret('provider_secret', 'bot-token-abcdef123456')
        self.assertEqual(conn.secret_hint, '••••3456')
        self.assertTrue(conn.has_credentials)
        self.assertEqual(conn._get_secret('provider_secret'),
                         'bot-token-abcdef123456')

        as_mgr = conn.with_user(self.crm_mgr)

        # The field is invisible in the schema...
        self.assertNotIn('provider_secret_enc', as_mgr.fields_get().keys())
        # ...raises on an explicit read...
        with self.assertRaises(AccessError):
            as_mgr.read(['provider_secret_enc'])
        # ...and cannot be exported. The export RIGHT is granted first, so the
        # denial proves the FIELD is the blocker, not a missing export group.
        self.crm_mgr.sudo().write({
            'group_ids': [(4, self.env.ref('base.group_allow_export').id)]})
        with self.assertRaises(AccessError):
            as_mgr.export_data(['provider_secret_enc'])

        # has_credentials still works for a non-system reader (it computes
        # through sudo on purpose).
        self.assertTrue(as_mgr.with_user(self.crm_user).has_credentials)

        # No ciphertext anywhere in the UI payload.
        summary = as_mgr.readiness_summary()
        self.assertNotIn(channel_crypto.TOKEN_PREFIX, str(summary))
        self.assertNotIn('bot-token-abcdef123456', str(summary))
        self.assertEqual(summary['secret_hint'], '••••3456')

    # ------------------------------------------------------------------
    # T75 — the state machine is the only writer of `state`
    # ------------------------------------------------------------------
    def test_75_state_machine(self):
        conn = self._conn('zalo')
        self.assertEqual(conn.state, 'not_connected')

        self.assertTrue(conn._transition('authorizing', reason='test'))
        self.assertEqual(conn.state, 'authorizing')
        audit = self.Audit.search([('connection_id', '=', conn.id),
                                   ('event', '=', 'health_transition')])
        self.assertTrue(audit)
        self.assertIn('not_connected -> authorizing', audit[0].detail_redacted)

        # A no-op transition is not an error, and writes nothing.
        self.assertFalse(conn._transition('authorizing'))

        # A jump the table does not allow is refused.
        fresh = self._conn('fb')
        with self.assertRaises(UserError):
            fresh._transition('ready')
        self.assertEqual(fresh.state, 'not_connected')

        # And no RPC caller can shortcut it.
        with self.assertRaises(UserError):
            conn.with_user(self.crm_mgr).write({'state': 'ready'})
        with self.assertRaises(UserError):
            conn.with_user(self.crm_mgr).write({'resource_external_id': 'oa1'})
        # uid 1 is su, so an su-based guard would be dead code here (§5.4) —
        # this one is keyed on the internal context instead, and still fires.
        with self.assertRaises(UserError):
            conn.write({'granted_scopes': 'everything'})

        # The context flag is NOT a key a client can forge: RPC callers
        # control their context, so flag-without-escalation must still be
        # refused (CC-A review finding #1).
        from ..models.care_channel_connection import INTERNAL_CTX
        with self.assertRaises(UserError):
            conn.with_user(self.crm_mgr).with_context(
                **{INTERNAL_CTX: True}).write({'state': 'ready'})
        self.assertEqual(conn.state, 'authorizing')

        # `active` is the one field a user may touch.
        conn.with_user(self.crm_mgr).write({'active': False})
        self.assertFalse(conn.active)

    # ------------------------------------------------------------------
    # T76 — one active connection per (channel, company)
    # ------------------------------------------------------------------
    def test_76_one_active_connection_per_channel(self):
        first = self._conn('whatsapp')
        with self.assertRaises(ValidationError):
            self._conn('whatsapp')

        # Same channel, different company: fine.
        other = self._conn('whatsapp', company=self.company2)
        self.assertTrue(other.id)

        # Archived rows free the slot.
        first.write({'active': False})
        second = self._conn('whatsapp')
        self.assertTrue(second.id)

        # ...and un-archiving the first one is refused while the second lives.
        with self.assertRaises(ValidationError):
            first.write({'active': True})

    # ------------------------------------------------------------------
    # T77 — readiness derivation ("configured" ≠ "connected")
    # ------------------------------------------------------------------
    def test_77_readiness_derivation(self):
        conn = self._conn('telegram')
        required = conn._required_checks()
        self.assertEqual(
            set(required),
            {'authorization_valid', 'resource_selected', 'webhook_configured',
             'outbound_ok'})

        # Seeding every check while still not_connected must NOT make it ready:
        # readiness derivation only runs for a connection that got as far as
        # being tested.
        self._seed_checks(conn)
        self.assertEqual(conn.state, 'not_connected')

        conn._transition('authorizing')
        conn._transition('testing')
        conn._recompute_ready()
        self.assertEqual(conn.state, 'ready')
        self.assertEqual(conn.health_status, 'healthy')

        # One failure is enough to lose Ready — and it falls to action_required
        # (the tenant must act), never to error (the framework broke).
        self.Check.upsert_check(conn, 'webhook_configured', 'fail',
                                detail='provider said no')
        self.assertEqual(conn.state, 'action_required')

        # `n_a` does NOT satisfy a REQUIRED check.
        self.Check.upsert_check(conn, 'webhook_configured', 'n_a')
        self.assertEqual(conn.state, 'action_required')

        self.Check.upsert_check(conn, 'webhook_configured', 'pass')
        self.assertEqual(conn.state, 'ready')

        # A check outside the required set never blocks readiness.
        self.Check.upsert_check(conn, 'token_fresh', 'fail')
        self.assertEqual(conn.state, 'ready')

        summary = conn.readiness_summary()
        by_key = {row['check_key']: row for row in summary['checks']}
        self.assertTrue(by_key['webhook_configured']['required'])
        self.assertFalse(by_key['token_fresh']['required'])
        self.assertEqual(summary['state'], 'ready')

    # ------------------------------------------------------------------
    # T78 — append-only audit
    # ------------------------------------------------------------------
    def test_78_audit_append_only(self):
        conn = self._conn('email')
        row = self.Audit._log('test_ok', connection=conn, detail='hello')
        self.assertTrue(row.id)

        # Unconditional guards: uid 1 runs as su and is refused all the same.
        with self.assertRaises(UserError):
            row.write({'detail_redacted': 'rewritten'})
        with self.assertRaises(UserError):
            row.unlink()

        # A failing log must not take the caller's transaction down with it:
        # the create runs inside cr.savepoint(), so the aborted INSERT is
        # rolled back and the transaction stays usable (ledger §5.55).
        broken = self.Audit._log('test_fail', company_id=2 ** 30)
        self.assertFalse(broken)
        self.assertTrue(self._conn('webchat').id,
                        'transaction poisoned by the failed audit write')

    # ------------------------------------------------------------------
    # T79 — redaction
    # ------------------------------------------------------------------
    def test_79_redaction(self):
        out = redact('access_token=abc123 https://x.y/cb?code=zzz&state=s')
        self.assertNotIn('abc123', out)
        self.assertNotIn('zzz', out)
        self.assertNotIn('state=s', out)
        self.assertIn('<redacted>', out)

        for probe in ('client_secret: hunter2', 'Authorization: Bearer xyzzy',
                      'api_key=AKIAWHATEVER', 'X-Hub-Signature=deadbeef',
                      'password=letmein',
                      # JSON provider bodies — quoted keys/values must not
                      # break the match (CC-A review finding #2).
                      '{"access_token": "hunter2", "expires_in": 90000}',
                      "{'refresh_token': 'xyzzy'}"):
            cleaned = redact(probe)
            for leak in ('hunter2', 'xyzzy', 'AKIAWHATEVER', 'deadbeef',
                         'letmein'):
                self.assertNotIn(leak, cleaned)

        long_text = 'x' * 900
        self.assertLessEqual(len(redact(long_text)), 300)
        self.assertFalse(redact(''))
        self.assertFalse(redact(None))

        # Every persisted detail goes through it.
        conn = self._conn('zalo')
        self.Check.upsert_check(conn, 'authorization_valid', 'fail',
                                detail='refused: access_token=leakme')
        check = conn.readiness_check_ids.filtered(
            lambda c: c.check_key == 'authorization_valid')
        self.assertNotIn('leakme', check.detail_redacted)
        row = self.Audit._log('test_fail', connection=conn,
                              detail='oops secret=leakme2')
        self.assertNotIn('leakme2', row.detail_redacted)

    # ------------------------------------------------------------------
    # T80 — company isolation
    # ------------------------------------------------------------------
    def test_80_company_isolation(self):
        mine = self._conn('call')
        theirs = self._conn('call', company=self.company2)

        as_mgr = self.Conn.with_user(self.crm_mgr)
        found = as_mgr.search([('channel', '=', 'call')])
        self.assertIn(mine, found)
        self.assertNotIn(theirs, found)

        with self.assertRaises(AccessError):
            as_mgr.browse(theirs.id).read(['channel'])

        # The audit trail is scoped the same way.
        self.Audit._log('test_ok', connection=theirs)
        self.assertFalse(
            self.Audit.with_user(self.crm_mgr).search(
                [('connection_id', '=', theirs.id)]))

    # ------------------------------------------------------------------
    # T81 — adapter registry + capability declarations
    # ------------------------------------------------------------------
    def test_81_adapter_registry(self):
        expected = {'zalo', 'call', 'email', 'zns', 'whatsapp', 'fb',
                    'telegram', 'webchat'}
        self.assertEqual(set(CHANNEL_ADAPTERS), expected)

        valid_checks = {key for key, _label in
                        self.Check._fields['check_key'].selection}
        self.assertEqual(valid_checks, set(CHECK_KEYS))

        for key in expected:
            conn = self._conn(key) if key != 'call' else self._conn('call')
            caps = conn._capabilities()
            for capability_key in CAPABILITY_KEYS:
                self.assertIn(capability_key, caps,
                              '%s adapter is missing %s' % (key, capability_key))
            self.assertIn(caps['mode'], VALID_MODES)
            self.assertTrue(caps['required_checks'],
                            '%s declares no readiness requirement' % key)
            self.assertFalse(set(caps['required_checks']) - set(CHECK_KEYS))
            # The declaration must not be mutable through the accessor.
            caps['required_checks'].append('bogus')
            self.assertNotIn('bogus', conn._capabilities()['required_checks'])
            conn.write({'active': False})   # free the (channel, company) slot

        # ZNS renders as a sub-card of Zalo rather than as its own sign-in.
        zns = self._conn('zns')
        self.assertEqual(zns._capabilities().get('parent_channel'), 'zalo')

        # An unregistered key is a programming error, not a degraded channel.
        with self.assertRaises(ValueError):
            get_adapter(self.env, 'instagram')

    # ------------------------------------------------------------------
    # T87 — health cron: skip, back off, warn about expiry
    # ------------------------------------------------------------------
    def test_87_health_cron(self):
        from datetime import timedelta
        from unittest.mock import patch

        from odoo import fields
        from odoo.addons.health_care_command_channels.services import adapters

        now = fields.Datetime.now()
        conn = self._conn('telegram', state='authorizing')
        conn._transition('testing')
        conn._transition('ready')
        conn.with_context(**{INTERNAL_CTX: True}).write(
            {'next_health_check_at': now - timedelta(minutes=1)})

        # (a) A declaration-only adapter raises NotImplementedError: skip
        #     quietly, reschedule, count NO failure.
        self.Conn._cron_channel_health()
        self.assertEqual(conn.consecutive_failures, 0)
        self.assertTrue(conn.next_health_check_at > now)

        # (b) A failing adapter increments the counter and the backoff grows.
        class _FailingAdapter(adapters.TelegramAdapter):
            def health_check(self):
                raise RuntimeError('provider said access_token=leak')

        delays = []
        with patch.dict(adapters.CHANNEL_ADAPTERS,
                        {'telegram': _FailingAdapter}):
            for _ in range(3):
                conn.with_context(**{INTERNAL_CTX: True}).write(
                    {'next_health_check_at': fields.Datetime.now() - timedelta(minutes=1)})
                self.Conn._cron_channel_health()
                delays.append(conn.next_health_check_at - fields.Datetime.now())
        self.assertEqual(conn.consecutive_failures, 3)
        self.assertEqual(conn.health_status, 'provider_down')
        self.assertEqual(conn.state, 'ready',
                         'a provider outage is not the tenant being broken')
        self.assertNotIn('leak', conn.last_error_redacted or '')
        self.assertLess(delays[0], delays[1])
        self.assertLess(delays[1], delays[2])

        # (c) Expiry sweep: one warning activity, and a second pass adds none.
        expiring = self._conn('fb', state='authorizing')
        expiring._transition('testing')
        expiring._transition('ready')
        expiring.with_context(**{INTERNAL_CTX: True}).write({
            'token_expires_at': fields.Datetime.now() + timedelta(days=5),
            'next_health_check_at': fields.Datetime.now() - timedelta(minutes=1),
        })
        self.Conn._cron_channel_health()
        self.assertEqual(expiring.health_status, 'expiring')
        self.assertEqual(expiring.state, 'expiring')
        model_id = self.env['ir.model']._get_id('care.channel.connection')
        domain = [('res_model_id', '=', model_id), ('res_id', '=', expiring.id)]
        first_count = self.env['mail.activity'].sudo().search_count(domain)
        self.assertEqual(first_count, 1, 'exactly ONE warning, not one per manager')

        self.Conn._sweep_token_expiry()
        self.assertEqual(self.env['mail.activity'].sudo().search_count(domain),
                         first_count, 'the expiry warning must be idempotent')
        # The note carries no credential material.
        activity = self.env['mail.activity'].sudo().search(domain, limit=1)
        self.assertNotIn(channel_crypto.TOKEN_PREFIX, activity.note or '')

    # ------------------------------------------------------------------
    # T89 — settings roundtrip
    # ------------------------------------------------------------------
    def test_89_settings_param(self):
        settings = self.env['res.config.settings'].create({
            'channel_hub_allowed_redirect_hosts': 'partner.example.com'})
        settings.execute()
        icp = self.env['ir.config_parameter'].sudo()
        self.assertEqual(icp.get_param('channel_hub.allowed_redirect_hosts'),
                         'partner.example.com')
        self.assertEqual(
            self.env['res.config.settings'].create({})
                .channel_hub_allowed_redirect_hosts,
            'partner.example.com')
