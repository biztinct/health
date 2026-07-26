# -*- coding: utf-8 -*-
"""T113–T118 — the health_zalo half of CC-D.

These live here, not in health_care_command_channels, because they need
``zalo.config`` / ``zalo.message`` — and the dependency runs health_zalo →
framework, never back. The framework half (adapter, verifier, Center
endpoints) is asserted in
``health_care_command_channels/tests/test_zalo_center.py``.

TransactionCase only, every provider call mocked, no real credential
anywhere. Two shapes to notice:

* fixtures **reuse** whatever this database already has — one active
  ``zalo.config`` and the migrated ``legacy`` connection both exist on a live
  server, and both carry uniqueness constraints (``_check_active_config``, the
  partial index on ``(channel, company)``). A fixture that assumes an empty
  table fails on vietuat and passes on a fresh database;
* nothing-stored assertions use ``try/except``, never ``assertRaises`` — the
  savepoint would roll back exactly the writes being asserted on (§5.8), and
  ``assertRaises`` cannot take a tuple of classes at all (§5.70).
"""
import json
from unittest.mock import patch

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged

from odoo.addons.health_care_command_channels.models.care_channel_connection import (
    INTERNAL_CTX,
)
from odoo.addons.health_zalo.services.zalo_api import ZaloAPIClient, get_api_client

OA_ID = 'OA_CCD_FIXTURE'
APP_ID = '9876543210987654321'
APP_SECRET = 'zalo-app-secret-fixture'


@tagged('post_install', '-at_install')
class TestZaloCCD(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.company = env.company
        cls.Config = env['zalo.config']
        cls.Conn = env['care.channel.connection']
        cls.Check = env['care.channel.readiness.check']
        cls.Message = env['care.channel.message']
        cls.ZMessage = env['zalo.message']

        # A TransactionCase runs as uid 1, which is a member of NO group
        # (has_group checks real membership, not su — ledger §5.42), so the
        # group-gated service methods would refuse their own fixtures.
        env.user.sudo().write({'group_ids': [
            (4, env.ref('base.group_system').id),
            (4, env.ref('health_crm.group_health_crm_manager').id),
            (4, env.ref('health_zalo.group_zalo_admin').id)]})

        cls.platform_app = env['channel.platform.app'].sudo().search(
            [('provider', '=', 'zalo')], limit=1)
        if not cls.platform_app:
            cls.platform_app = env['channel.platform.app'].sudo().create({
                'provider': 'zalo', 'client_id': APP_ID})
        else:
            cls.platform_app.sudo().write({'client_id': APP_ID,
                                           'active': True})
        cls.platform_app.action_set_secret(APP_SECRET)

    # -- fixtures -------------------------------------------------------
    def _config(self):
        """This company's active config — the live row where there is one."""
        config = self.Config.sudo().search([
            ('company_id', '=', self.company.id),
            ('active', '=', True)], limit=1)
        if not config:
            config = self.Config.sudo().create({
                'name': 'CC-D fixture OA',
                'app_id': APP_ID,
                'app_secret': APP_SECRET,
                'oa_id': OA_ID,
                'company_id': self.company.id,
            })
        else:
            config.sudo().write({'oa_id': OA_ID, 'state': 'connected'})
        return config

    def _connection(self, state='testing'):
        conn = self.Conn.sudo().with_context(active_test=False).search([
            ('channel', '=', 'zalo'),
            ('company_id', '=', self.company.id)], order='id desc', limit=1)
        if not conn:
            conn = self.Conn.sudo().with_context(**{INTERNAL_CTX: True}).create(
                {'channel': 'zalo', 'company_id': self.company.id})
        conn = self.Conn.sudo().browse(conn.id)
        conn.with_context(**{INTERNAL_CTX: True}).write({
            'active': True, 'state': state,
            'resource_external_id': OA_ID,
            'resource_display_name': 'CC-D fixture OA'})
        return conn

    def _linked(self, state='testing'):
        """A config and the connection that serves it.

        There is no FK between them by design (see zalo_config.py): the join
        key is the framework's own uniqueness key, one active connection per
        (channel, company). "Linked" therefore means "both exist for this
        company", which is also what the migration produces.
        """
        return self._config(), self._connection(state)

    @staticmethod
    def _event(msg_id='MSG_CCD_1', text='xin chào'):
        return {
            'app_id': APP_ID,
            'oa_id': OA_ID,
            'event_name': 'user_send_text',
            'sender': {'id': 'ZALO_USER_CCD_1'},
            'recipient': {'id': OA_ID},
            'message': {'text': text, 'msg_id': msg_id},
            'timestamp': '1769000000000',
        }

    # ==================================================================
    # T113 — inbound: the legacy pipeline, run synchronously, deduped
    # ==================================================================
    def test_113_inbound_legacy_pipeline(self):
        _config, conn = self._linked()
        payload = self._event()

        counts = self.Message._dispatch_zalo(conn, payload)
        self.assertEqual(counts['ingested'], 1)

        rows = self.ZMessage.sudo().search(
            [('zalo_message_id', '=', 'MSG_CCD_1')])
        self.assertEqual(len(rows), 1,
                         'the verified event lands as a zalo.message — the '
                         'rails Care Command already reads')
        self.assertEqual(rows.direction, 'incoming')
        self.assertEqual(rows.text, 'xin chào')
        # Z3: the old handler dispatched through with_delay() with no
        # queue_job addon, swallowed the AttributeError and returned 200 —
        # every event was dropped. One row here is that defect closed.

        # Traffic is what proves the webhook, and it flows into readiness.
        conn.invalidate_recordset()
        self.assertTrue(conn.last_inbound_at)
        self.assertEqual(conn.webhook_state, 'verified')
        statuses = {c.check_key: c.status for c in conn.readiness_check_ids}
        self.assertEqual(statuses.get('webhook_verified'), 'pass')
        self.assertEqual(statuses.get('inbound_ok'), 'pass')

        # Z7: the same msg_id twice is ONE row.
        again = self.Message._dispatch_zalo(conn, payload)
        self.assertEqual(again['duplicate'], 1)
        self.assertEqual(again['ingested'], 0)
        self.assertEqual(self.ZMessage.sudo().search_count(
            [('zalo_message_id', '=', 'MSG_CCD_1')]), 1)

        # A different message on the same thread still lands.
        self.Message._dispatch_zalo(conn, self._event(msg_id='MSG_CCD_2',
                                                      text='tôi cần đặt lịch'))
        self.assertEqual(self.ZMessage.sudo().search_count(
            [('zalo_message_id', 'in', ['MSG_CCD_1', 'MSG_CCD_2'])]), 2)

    # ==================================================================
    # T114 — the three legacy routes are 410 shims
    # ==================================================================
    def test_114_legacy_routes_are_gone(self):
        from odoo.addons.health_zalo.controllers.webhook import (
            ZaloWebhookController,
        )
        for name in ('webhook_handler', 'webhook_test', 'oauth_callback'):
            handler = getattr(ZaloWebhookController, name)
            routing = getattr(handler, 'original_routing', {})
            self.assertTrue(routing, name)
            self.assertEqual(routing.get('type'), 'http', name)
            self.assertEqual(routing.get('auth'), 'public', name)
            self.assertFalse(routing.get('save_session'), name)

        # The whole point: nothing behind them can accept or process an event
        # any more. Read the HANDLERS, not the module — a module-wide grep
        # matches this file's own prose about the defects it removed (the
        # first run failed on exactly that).
        import inspect
        for name in ('webhook_handler', 'webhook_test', 'oauth_callback'):
            body = inspect.getsource(getattr(ZaloWebhookController, name))
            self.assertIn('_gone()', body, name)
            for banned in ('with_delay', '_validate_webhook_signature',
                           'process_webhook_event',
                           'action_exchange_code_for_token', 'request.render'):
                self.assertNotIn(banned, body,
                                 '%s must not survive in %s' % (banned, name))
        self.assertIn('410', inspect.getsource(ZaloWebhookController._gone))
        self.assertFalse(
            hasattr(ZaloWebhookController, '_validate_webhook_signature'),
            'the fail-open verifier is gone, not merely unreferenced')
        # Live curls against all three are in the evidence pack (§6).

    # ==================================================================
    # T115 — the frozen ZNS contract, and the facade under it
    # ==================================================================
    def test_115_facade_contract(self):
        import inspect

        # -- the three things ten modules depend on, unchanged -----------
        client = get_api_client(self.env)
        self.assertIsInstance(client, ZaloAPIClient)
        config = self.Config.search([('active', '=', True)], limit=1)
        self.assertTrue(config, 'the active-config search still finds a row')
        self.assertEqual(
            list(inspect.signature(
                ZaloAPIClient.send_zns_notification).parameters),
            ['self', 'config', 'phone', 'template_id', 'template_data'])

        config, conn = self._linked()
        conn.action_set_secret('access_token', 'connection-access-token')

        # -- the facade reads the CONNECTION, not the plaintext column ----
        config.sudo().write({'access_token': 'stale-legacy-column-value'})
        self.assertEqual(config._effective_access_token(),
                         'connection-access-token')
        self.assertEqual(config.get_valid_token(), 'connection-access-token')
        # ...and falls back where there is no connection at all (a
        # never-migrated tenant, or a Center that was never installed).
        conn.with_context(**{INTERNAL_CTX: True}).write({'active': False})
        config.invalidate_recordset()
        self.assertEqual(config._effective_access_token(),
                         'stale-legacy-column-value')
        conn.with_context(**{INTERNAL_CTX: True}).write({'active': True})

        # -- a ZNS send Zalo accepted is what makes the sub-card honest ---
        ok = {'error': 0, 'message': 'Success', 'data': {'msg_id': 'ZNS1'}}
        with patch.object(ZaloAPIClient, '_make_request', return_value=ok):
            result = client.send_zns_notification(
                config, '84900000000', 'TPL-1', {'customer_name': 'Lan'})
        self.assertEqual(result, ok, 'the return contract is untouched')
        conn.invalidate_recordset()
        statuses = {c.check_key: c.status for c in conn.readiness_check_ids}
        self.assertEqual(statuses.get('provider_approvals'), 'pass')
        self.assertEqual(statuses.get('outbound_ok'), 'pass')
        self.assertTrue(conn.last_outbound_at)

        # -- a failure still raises exactly what the consumers catch ------
        # try/except, not assertRaises: the evidence written before the raise
        # is what this asserts on (§5.8).
        boom = UserError('Zalo API error: 401 unauthorized')
        raised = False
        with patch.object(ZaloAPIClient, '_make_request', side_effect=boom):
            try:
                client.send_zns_notification(config, '84900000000', 'TPL-1', {})
            except UserError:
                raised = True
        self.assertTrue(raised, 'the error contract is unchanged')
        conn.invalidate_recordset()
        self.assertTrue(conn.last_error_redacted)
        statuses = {c.check_key: c.status for c in conn.readiness_check_ids}
        self.assertEqual(statuses.get('authorization_valid'), 'fail',
                         'a 401 on a real send is a lost grant')

    # ==================================================================
    # T116 — the migration is idempotent and destroys nothing
    # ==================================================================
    def test_116_migration_idempotent(self):
        config = self._config()
        config.sudo().write({
            'access_token': 'legacy-plaintext-access',
            'refresh_token': 'legacy-plaintext-refresh',
        })
        # Start from a connection with no credentials so the copy is visible.
        conn = self._connection(state='legacy')
        conn.with_context(**{INTERNAL_CTX: True}).write({
            'access_token_enc': False, 'refresh_token_enc': False})

        before = self.Conn.sudo().with_context(active_test=False).search_count(
            [('channel', '=', 'zalo')])
        first = self.Config._migrate_legacy_connections()
        config.invalidate_recordset()
        conn.invalidate_recordset()

        self.assertEqual(first['created'], 0,
                         'an existing connection is used, never duplicated')
        self.assertGreaterEqual(first['existing'], 1)
        self.assertGreaterEqual(first['copied'], 1)
        self.assertEqual(
            self.Conn.sudo().with_context(active_test=False).search_count(
                [('channel', '=', 'zalo')]), before,
            'the migration creates no second connection for a company that '
            'already has one')

        # Plaintext tokens are encrypt-COPIED, never moved and never wiped.
        self.assertEqual(conn._get_secret('access_token'),
                         'legacy-plaintext-access')
        self.assertEqual(conn._get_secret('refresh_token'),
                         'legacy-plaintext-refresh')
        self.env.flush_all()
        self.env.cr.execute(
            'SELECT access_token_enc FROM care_channel_connection '
            'WHERE id = %s', (conn.id,))
        stored = self.env.cr.fetchone()[0]
        self.env.invalidate_all()
        self.assertTrue(stored.startswith('chs$1$'))
        self.assertNotIn('legacy-plaintext', stored)
        self.assertEqual(config.sudo().access_token, 'legacy-plaintext-access',
                         'nothing on the legacy side is deleted this phase')
        self.assertEqual(conn.resource_external_id, OA_ID)

        # Re-running copies nothing and creates nothing.
        second = self.Config._migrate_legacy_connections()
        self.assertEqual(second['created'], 0)
        self.assertEqual(second['copied'], 0)
        self.assertEqual(
            self.Conn.sudo().with_context(active_test=False).search_count(
                [('channel', '=', 'zalo')]), before)

        # ...and where there is NO connection yet, exactly one is created, in
        # `legacy` — migrated, not silently promoted to working.
        other = self.env['res.company'].create({'name': 'CCD Migrate Co'})
        self.Config.sudo().create({
            'name': 'CC-D second company OA', 'app_id': APP_ID,
            'app_secret': APP_SECRET, 'oa_id': 'OA_SECOND_CO',
            'company_id': other.id,
        })
        third = self.Config._migrate_legacy_connections()
        self.assertEqual(third['created'], 1)
        fresh = self.Conn.sudo().search([
            ('channel', '=', 'zalo'), ('company_id', '=', other.id)])
        self.assertEqual(len(fresh), 1)
        self.assertEqual(fresh.state, 'legacy')
        self.assertEqual(fresh.resource_external_id, 'OA_SECOND_CO')
        self.assertFalse(fresh.has_credentials,
                         'a config with no tokens produces a connection with '
                         'none either — nothing is invented')

    # ==================================================================
    # T117 — Z1: the app secret is no longer copied into the chatter
    # ==================================================================
    def test_117_app_secret_untracked(self):
        config = self._config()
        field = self.env['ir.model.fields']._get('zalo.config', 'app_secret')
        self.assertTrue(field)
        self.assertFalse(
            getattr(self.Config._fields['app_secret'], 'tracking', False),
            'a tracked secret is copied verbatim into mail.tracking.value, '
            'which walks straight around the field groups')

        Tracking = self.env['mail.tracking.value'].sudo()
        before = Tracking.search_count([('field_id', '=', field.id)])
        config.sudo().write({'app_secret': 'rotated-secret-value-fixture'})
        # Tracking posts at PRECOMMIT (§5.56) — a TransactionCase never
        # commits, so the callbacks have to be run explicitly or this passes
        # for the wrong reason.
        self.env.flush_all()
        self.env.cr.precommit.run()
        self.assertEqual(Tracking.search_count([('field_id', '=', field.id)]),
                         before,
                         'writing the app secret must create no tracking value')

        # ...and the one-time clean-up removes whatever already leaked.
        self.assertIsInstance(self.Config._drop_app_secret_tracking(), int)
        self.assertEqual(Tracking.search_count([('field_id', '=', field.id)]), 0)

    # ==================================================================
    # T118 — Z4 (no record rule at all) and Z5 (token-exfil vector)
    # ==================================================================
    def test_118_company_scope_and_api_base(self):
        province = self.env['health.catchment.province'].search([], limit=1) \
            or self.env['health.catchment.province'].create({'name': 'CCD Prov'})
        other_company = self.env['res.company'].create({'name': 'CCD Other Co'})
        outsider = self.env['res.users'].create({
            'name': 'ccd_zalo_outsider', 'login': 'ccd_zalo_outsider',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id,
                                  self.env.ref('health_zalo.group_zalo_manager').id])],
            'company_id': other_company.id,
            'company_ids': [(6, 0, [other_company.id])],
            'catchment_province_id': province.id,
        })
        config = self._config()

        # Z4: before CC-D there was no ir.rule anywhere in this module, so this
        # config was readable by every Zalo user of every company.
        visible = self.Config.with_user(outsider).search([])
        self.assertNotIn(config.id, visible.ids,
                         'another company must not see this configuration')
        raised = False
        try:
            self.Config.with_user(outsider).browse(config.id).read(['oa_id'])
        except (AccessError, UserError):
            raised = True
        self.assertTrue(raised, 'a direct id read must be refused too')

        # Z5: repointing api_base_url exfiltrates the NEXT refresh — app_id
        # plus refresh_token, posted to a host of the attacker's choosing.
        insider = self.env['res.users'].create({
            'name': 'ccd_zalo_manager', 'login': 'ccd_zalo_manager',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id,
                                  self.env.ref('health_zalo.group_zalo_manager').id])],
            'company_id': self.company.id,
            'company_ids': [(6, 0, [self.company.id])],
            'catchment_province_id': province.id,
        })
        raised = False
        try:
            config.with_user(insider).write(
                {'api_base_url': 'https://attacker.example'})
        except (UserError, AccessError):
            raised = True
        self.assertTrue(raised, 'a Zalo manager must not repoint the API host')
        config.invalidate_recordset()
        self.assertNotEqual(config.sudo().api_base_url,
                            'https://attacker.example')

        # A system administrator (and every server path) still can.
        config.sudo().write({'api_base_url': 'https://openapi.zalo.me'})
        self.assertEqual(config.sudo().api_base_url, 'https://openapi.zalo.me')

    # ==================================================================
    # The legacy OAuth entry points are retired, not merely unused (Z6/Z9)
    # ==================================================================
    def test_123_retired_entry_points(self):
        config = self._config()
        for name in ('action_connect_zalo', 'action_enable_webhook',
                     'action_disable_webhook'):
            with self.assertRaises(UserError, msg=name):
                getattr(config, name)()
        with self.assertRaises(UserError):
            config.action_exchange_code_for_token('some-code')

        # Z9: the demo-config auto-create is gone from both call sites. It used
        # to manufacture a live row with app_id/app_secret/oa_id = "demo",
        # which then satisfied the ZNS contract's active-config search for
        # every module in the system.
        import inspect
        from odoo.addons.health_zalo.models import crm_lead, res_partner
        for model in (crm_lead.CrmLead, res_partner.ResPartner):
            body = inspect.getsource(model.action_open_zalo_chat)
            # The fingerprint of the fake row, not the prose about it: a
            # module-wide grep matches the comment that explains the removal.
            self.assertNotIn("'app_secret': 'demo'", body,
                             '%s still manufactures a fake configuration'
                             % model.__name__)
            self.assertNotIn("zalo.config'].create(", body, model.__name__)
        self.assertFalse(hasattr(self.env['res.partner'],
                                 'action_link_zalo_user'),
                         'the button pointed at a model that never existed')
        self.assertFalse(self.Config.sudo().with_context(
            active_test=False).search_count(
            [('name', 'like', 'Demo Zalo Config')]),
            'no demo configuration may exist on this database')

    # ==================================================================
    # The bridge the adapter calls after a successful sign-in
    # ==================================================================
    def test_124_sync_from_connection(self):
        config = self._config()
        config.sudo().write({'state': 'draft'})
        conn = self._connection(state='configuring')
        result = self.Config._sync_from_connection(
            conn, oa_id='OA_SYNCED', oa_name='Synced OA')
        self.assertEqual(result, config)
        config.invalidate_recordset()
        # state='connected' is not cosmetic: get_active_config() filters on it,
        # so the legacy inbound pipeline cannot resolve a config without it.
        self.assertEqual(config.sudo().state, 'connected')
        self.assertEqual(config._channel_connection(), conn)
        self.assertEqual(config.sudo().oa_id, 'OA_SYNCED')
        # No credential is copied down: the tokens stay encrypted on the
        # connection and are read through the facade.
        blob = json.dumps(config.sudo().read(
            ['name', 'oa_id', 'state'])[0], default=str)
        self.assertNotIn('chs$1$', blob)
