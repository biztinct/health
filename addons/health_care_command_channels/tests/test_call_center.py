# -*- coding: utf-8 -*-
"""T150–T155 — Calls (VoIP24h) on the connection framework (CC-F).

Receive-only by design, and these tests exist to keep it that way. **No test
here calls a VoIP24h endpoint, because no VoIP24h endpoint has ever been
verified**: their documentation is unreachable from outside Vietnam and every
path in ``health_voip24h/services/voip24h_api.py`` is an unevidenced guess
(see docs/strategy/voip24h-contract-capture.md). T153 asserts that the product
says so out loud instead of shipping a button that cannot work.

The webhook half is asserted against the ALREADY-EXISTING verifier rather than
a new one — CC-F adopted it, and porting its assertions here is how we prove
the adoption did not regress it (T150).

Everything is a TransactionCase (ledger §5.32). The controller is tested
through the model methods it calls: an HttpCase in this module has poisoned
later suites before, and §5.75 means a manual run would error every one of
them in setUpClass anyway.
"""
import hashlib
import hmac
import json

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from odoo.addons.health_care_command_channels.models.channel_center import (
    CENTER_CHANNELS,
)

from .common_spine import ChannelSpineCase

HTTPS_BASE = 'https://care.example.test'
VOIP_ACCOUNT = 'VU-CLINIC-01'
VOIP_SECRET = 'voip-webhook-secret-fixture'


def _sign(secret, raw):
    return hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()


@tagged('post_install', '-at_install')
class TestCallCenter(ChannelSpineCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['ir.config_parameter'].sudo().set_param('web.base.url', HTTPS_BASE)
        cls.has_voip = 'voip.config' in cls.env
        if cls.has_voip:
            # Live rows would collide with the fixtures below exactly the way
            # the migrated zalo connections did in CC-D (see common.py).
            cls.env['voip.config'].sudo().with_context(
                active_test=False).search([]).write({'active': False})

    # -- helpers -------------------------------------------------------
    def _call_conn(self):
        opened = self.Conn.center_begin('call')
        return self.Conn.browse(opened['connection_id'])

    def _configured(self):
        conn = self._call_conn()
        self.Conn.center_call_configure(conn.id, VOIP_ACCOUNT, VOIP_SECRET)
        conn.invalidate_recordset()
        return conn

    def _event(self, event_type='call.missed', call_id='CALL-1'):
        return {'event_type': event_type, 'account_id': VOIP_ACCOUNT,
                'call_data': {'call_id': call_id, 'direction': 'incoming',
                              'caller_number': '84901234567'}}

    # =================================================================
    # T150 — the adopted verifier still refuses everything it used to
    # =================================================================
    def test_150_the_adopted_verifier_still_fails_closed(self):
        if not self.has_voip:
            self.skipTest('health_voip24h is not installed')
        from odoo.addons.health_voip24h.models.voip_config import (
            verify_voip_signature,
        )
        raw = json.dumps(self._event()).encode()
        good = _sign(VOIP_SECRET, raw)

        # The shape of the contract, unchanged by the move to a module
        # function: raw bytes, hex, an optional sha256= prefix, constant time.
        self.assertTrue(verify_voip_signature(VOIP_SECRET, raw, good))
        self.assertTrue(verify_voip_signature(VOIP_SECRET, raw,
                                              'sha256=' + good.upper()))
        # ...and every refusal.
        self.assertFalse(verify_voip_signature(VOIP_SECRET, raw, ''))
        self.assertFalse(verify_voip_signature(VOIP_SECRET, raw, 'deadbeef'))
        self.assertFalse(verify_voip_signature(VOIP_SECRET, raw + b' ', good),
                         'the signature is over the RAW bytes')
        self.assertFalse(verify_voip_signature('', raw, good),
                         'FAIL CLOSED with no secret — the route is public')
        self.assertFalse(verify_voip_signature(None, raw, good))

        config = self.env['voip.config'].sudo().create({
            'name': 'CC-F fixture', 'account_id': VOIP_ACCOUNT,
            'company_id': self.company.id, 'auto_sync_enabled': False})
        self.assertFalse(config._verify_webhook_signature(raw, good),
                         'a config with no secret anywhere must refuse')
        config.sudo().write({'webhook_secret': VOIP_SECRET})
        self.assertTrue(config._verify_webhook_signature(raw, good))

    def test_150b_the_connection_secret_wins_over_the_plaintext_column(self):
        """The whole point of the facade: the encrypted copy is authoritative."""
        if not self.has_voip:
            self.skipTest('health_voip24h is not installed')
        conn = self._configured()
        config = self.env['voip.config'].sudo().search(
            [('account_id', '=', VOIP_ACCOUNT)], limit=1)
        self.assertTrue(config)
        config.sudo().write({'webhook_secret': 'a-stale-plaintext-secret'})
        raw = json.dumps(self._event()).encode()
        self.assertTrue(
            config._verify_webhook_signature(raw, _sign(VOIP_SECRET, raw)),
            'the encrypted connection secret must win')
        self.assertFalse(
            config._verify_webhook_signature(
                raw, _sign('a-stale-plaintext-secret', raw)))

    # =================================================================
    # T151 — a verified event routes, proves, and is dropped when disabled
    # =================================================================
    def test_151_a_verified_event_proves_the_channel(self):
        if not self.has_voip:
            self.skipTest('health_voip24h is not installed')
        conn = self._configured()
        self.assertEqual(conn.state, 'testing')
        config = self.env['voip.config'].sudo().search(
            [('account_id', '=', VOIP_ACCOUNT)], limit=1)

        self.assertEqual(config._note_channel_event('call.missed'), 'ok')
        conn.invalidate_recordset()
        statuses = {c.check_key: c.status for c in conn.readiness_check_ids}
        self.assertEqual(statuses.get('webhook_verified'), 'pass')
        self.assertEqual(statuses.get('inbound_ok'), 'pass')
        self.assertTrue(conn.last_inbound_at)
        self.assertEqual(conn.state, 'ready',
                         'those two checks ARE the whole required set')

        # A disabled channel must stop filling the inbox, and say why.
        self.Conn.center_disconnect(conn.id)
        conn.invalidate_recordset()
        before = self.Audit.sudo().search_count(
            [('connection_id', '=', conn.id), ('event', '=', 'webhook_ignored')])
        self.assertEqual(config._note_channel_event('call.missed'), 'ignored')
        self.assertEqual(
            self.Audit.sudo().search_count(
                [('connection_id', '=', conn.id),
                 ('event', '=', 'webhook_ignored')]), before + 1)

    def test_151b_a_legacy_connection_observes_without_gating(self):
        """The §5.66 trap, avoided: upgrading must not mute a working PBX.

        The migration parks every existing config on a ``legacy`` connection,
        which is NOT in INGESTABLE_STATES. If the gate applied there, the day
        this module ships would be the day a live phone system stopped
        producing call logs.
        """
        if not self.has_voip:
            self.skipTest('health_voip24h is not installed')
        config = self.env['voip.config'].sudo().create({
            'name': 'Legacy PBX', 'account_id': VOIP_ACCOUNT,
            'company_id': self.company.id, 'webhook_secret': VOIP_SECRET,
            'auto_sync_enabled': False})
        self.env['voip.config']._migrate_legacy_connections()
        conn = config._channel_connection()
        self.assertTrue(conn)
        self.assertEqual(conn.state, 'legacy')
        self.assertFalse(conn._may_ingest())
        self.assertEqual(config._note_channel_event('call.missed'), 'ok',
                         'a legacy row observes traffic, it does not gate it')
        conn.invalidate_recordset()
        self.assertTrue(conn.last_inbound_at)

    # =================================================================
    # T152 — the facade migration is idempotent and destroys nothing
    # =================================================================
    def test_152_migration_is_idempotent(self):
        if not self.has_voip:
            self.skipTest('health_voip24h is not installed')
        config = self.env['voip.config'].sudo().create({
            'name': 'Legacy PBX', 'account_id': VOIP_ACCOUNT,
            'company_id': self.company.id,
            'api_key': 'legacy-api-key', 'api_secret': 'legacy-api-secret',
            'webhook_secret': VOIP_SECRET, 'auto_sync_enabled': False})

        first = self.env['voip.config']._migrate_legacy_connections()
        self.assertEqual(first['created'], 1)
        self.assertEqual(first['copied'], 3)
        conn = config._channel_connection()
        self.assertEqual(conn.resource_external_id, VOIP_ACCOUNT)
        self.assertEqual(conn._get_secret('provider_secret'), VOIP_SECRET)
        self.assertEqual(conn._get_secret('access_token'), 'legacy-api-key')
        self.assertEqual(conn._get_secret('refresh_token'), 'legacy-api-secret')
        # Ciphertext, not the value — the whole reason to migrate.
        self.assertNotIn(VOIP_SECRET, conn.sudo().provider_secret_enc or '')

        # Nothing is deleted: existing code keeps reading what it always read.
        self.assertEqual(config.sudo().api_key, 'legacy-api-key')
        self.assertEqual(config.sudo().webhook_secret, VOIP_SECRET)

        second = self.env['voip.config']._migrate_legacy_connections()
        self.assertEqual(second['created'], 0)
        self.assertEqual(second['existing'], 1)
        self.assertEqual(second['copied'], 0)
        self.assertEqual(
            self.Conn.sudo().with_context(active_test=False).search_count(
                [('channel', '=', 'call'),
                 ('company_id', '=', self.company.id)]), 1)

    def test_152b_a_center_created_config_cannot_reach_the_api(self):
        """The emptiness of api_key/api_secret is a SAFETY MECHANISM.

        ``_check_credentials`` is what stands between a Center-created
        connection and six unverified endpoints — including the CDR cron,
        which ships ACTIVE on this deployment and selects on
        ``auto_sync_enabled`` + ``state='connected'``.
        """
        if not self.has_voip:
            self.skipTest('health_voip24h is not installed')
        conn = self._configured()
        config = self.env['voip.config'].sudo().search(
            [('account_id', '=', VOIP_ACCOUNT)], limit=1)
        self.assertTrue(config, 'a config must exist or call logs cannot land')
        self.assertFalse(config.api_key)
        self.assertFalse(config.api_secret)
        self.assertFalse(config.auto_sync_enabled)
        self.assertNotEqual(config.state, 'connected')
        self.assertTrue(config.webhook_enabled)

        raised = False
        try:
            config._get_api_client()
        except UserError:
            raised = True
        self.assertTrue(raised, 'no credentials ⇒ no API client ⇒ no call to '
                                'an endpoint nobody has verified')
        # And the CDR cron simply does not select it.
        self.assertNotIn(config, self.env['voip.config'].sudo().search(
            [('auto_sync_enabled', '=', True), ('state', '=', 'connected')]))

    # =================================================================
    # T153 — the card is honest: receive-only, and no test button
    # =================================================================
    def test_153_the_calls_card_is_receive_only_and_says_so(self):
        conn = self._configured() if self.has_voip else self._call_conn()
        card = next(c for c in self.Conn.center_overview()
                    if c['channel'] == 'call')
        self.assertTrue(card['available'])
        self.assertTrue(card['implemented'])
        self.assertTrue(card.get('notice'))
        self.assertIn('cannot verify', card['notice'].lower())

        # Required checks are ONLY what arriving traffic can prove. Anything
        # needing an API round trip would be a demand we cannot test.
        keys = {c['key'] for c in card['checks']}
        self.assertEqual(keys, {'webhook_verified', 'inbound_ok'})
        self.assertNotIn('outbound_ok', keys)
        self.assertNotIn('authorization_valid', keys)

        # center_test refuses instead of calling anything.
        raised = False
        try:
            self.Conn.center_test(conn.id)
        except UserError as exc:
            raised = True
            self.assertIn('cannot verify', str(exc).lower())
        self.assertTrue(raised)

        # The adapter itself refuses too — the honesty is not only in the UI.
        raised = False
        try:
            conn.sudo()._get_adapter().test_connection()
        except Exception as exc:  # ChannelSendError
            raised = True
            self.assertIn('cannot verify', str(exc).lower())
        self.assertTrue(raised)

    def test_153b_configure_refuses_without_a_secret(self):
        conn = self._call_conn()
        raised = False
        try:
            self.Conn.center_call_configure(conn.id, VOIP_ACCOUNT, '')
        except UserError:
            raised = True
        self.assertTrue(raised, 'no secret means every event is refused — the '
                                'stepper must not let a tenant finish blind')
        conn.invalidate_recordset()
        self.assertFalse(conn.resource_external_id,
                         'a refused configure must store nothing')

        raised = False
        try:
            self.Conn.center_call_configure(conn.id, '', VOIP_SECRET)
        except UserError:
            raised = True
        self.assertTrue(raised, 'an empty account id must be refused')

    def test_153c_the_stored_secret_never_comes_back(self):
        conn = self._configured() if self.has_voip else None
        if conn is None:
            conn = self._call_conn()
            self.Conn.center_call_configure(conn.id, VOIP_ACCOUNT, VOIP_SECRET)
        info = self.Conn.center_call_info(conn.id)
        self.assertTrue(info['has_webhook_secret'])
        self.assertNotIn(VOIP_SECRET, json.dumps(info))
        self.assertNotIn(VOIP_SECRET, json.dumps(self.Conn.center_overview()))
        self.assertIn('/voip24h/webhook', info['webhook_url'])

    # =================================================================
    # T154 — spoof: a plain CRM user and another company's connection
    # =================================================================
    def test_154_call_endpoints_refuse_a_spoof(self):
        conn = self._call_conn()
        as_user = self.Conn.with_user(self.crm_user)
        for call in (
            lambda m: m.center_call_info(conn.id),
            lambda m: m.center_call_configure(conn.id, VOIP_ACCOUNT, VOIP_SECRET),
        ):
            raised = False
            try:
                call(as_user)
            except (UserError, AccessError):
                raised = True  # §5.70: never a tuple in assertRaises
            self.assertTrue(raised, 'a plain CRM user must be refused')
        self.assertFalse(conn.sudo().provider_secret_enc,
                         'a refused configure must store no secret')

        other = self._conn('call', company=self.company2, state='testing')
        raised = False
        try:
            self.Conn.with_user(self.crm_mgr).center_call_info(other.id)
        except (UserError, AccessError):
            raised = True
        self.assertTrue(raised, "another company's connection must be refused")

        # And an endpoint pointed at the wrong channel is a spoof as well.
        raised = False
        try:
            self.Conn.center_call_info(self._tg_conn().id)
        except UserError:
            raised = True
        self.assertTrue(raised)

    # =================================================================
    # T155 — the catalogue is intact and no stepper inherited a neighbour's
    #        copy (the trap CC-E half-fixed and CC-F finished)
    # =================================================================
    def test_155_catalogue_and_stepper_keys_are_intact(self):
        cards = self.Conn.center_overview()
        self.assertEqual([c['channel'] for c in cards], list(CENTER_CHANNELS))
        self.assertEqual(len(cards), 8, 'eight channels, in dock order')
        # Seven top-level cards: `zns` is a capability OF zalo and renders
        # inside it, which is what `parent_channel` means.
        self.assertEqual(len([c for c in cards if not c['parent_channel']]), 7)

        by_key = {c['channel']: c for c in cards}
        # Every channel is now implemented; availability is the separate gate.
        for channel in ('telegram', 'webchat', 'zalo', 'whatsapp', 'fb',
                        'email', 'call'):
            self.assertTrue(by_key[channel]['implemented'], channel)
        self.assertTrue(by_key['telegram']['available'])
        self.assertTrue(by_key['webchat']['available'])
        self.assertTrue(by_key['call']['available'])
        self.assertFalse(by_key['email']['available'],
                         'no google/microsoft platform app exists (T142)')

        # The steppers: three channels share `oauth_popup` and two share
        # `guided_secret`, so the copy must be keyed per CHANNEL. Nobody may
        # be handed a neighbour's words.
        steps = {c['channel']: [s['key'] for s in c['guide_steps']]
                 for c in cards}
        self.assertTrue(all(k.startswith('channel_hub.guide.email.')
                            for k in steps['email']), steps['email'])
        self.assertTrue(all(k.startswith('channel_hub.guide.call.')
                            for k in steps['call']), steps['call'])
        self.assertTrue(all(k.startswith('channel_hub.guide.zalo.')
                            for k in steps['zalo']), steps['zalo'])
        self.assertTrue(all(k.startswith('channel_hub.guide.telegram.')
                            for k in steps['telegram']), steps['telegram'])
        self.assertEqual(by_key['email']['mode'], by_key['zalo']['mode'])
        self.assertEqual(by_key['call']['mode'], by_key['telegram']['mode'])

        # Every step key resolves to real copy, so no card can render blank.
        texts = self.Conn._center_guide_texts()
        for channel, keys in steps.items():
            for key in keys:
                self.assertIn(key, texts, '%s: %s' % (channel, key))
                self.assertTrue(texts[key].get('title'))

    def test_155b_no_stepper_branch_is_keyed_on_a_mode(self):
        """The structural half of T155, asserted where the bug would live.

        A mode-keyed branch is how `call` would silently inherit Telegram's
        BotFather copy and `email` would inherit Zalo's. Grep for the
        fingerprint that can only appear in a branch condition — never in
        prose (ledger §5.72).
        """
        import os

        base = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                            'static', 'src', 'center')
        with open(os.path.join(base, 'channel_center.xml'), encoding='utf-8') as fh:
            arch = fh.read()
        self.assertNotIn("state.mode === '", arch,
                         'stepper branches must key on a channel, not a mode')
        for getter in ('isTelegram', 'isEmail', 'isCall', 'isWebchat'):
            self.assertIn(getter, arch, getter)
        with open(os.path.join(base, 'channel_center.js'), encoding='utf-8') as fh:
            script = fh.read()
        for getter in ('get isTelegram', 'get isEmail', 'get isCall',
                       'get isWebchat'):
            self.assertIn(getter, script, getter)
