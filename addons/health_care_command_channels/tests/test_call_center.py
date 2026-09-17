# -*- coding: utf-8 -*-
"""T150–T155 — Calls (VoIP24h) on the connection framework (CC-F, CC-F2).

Receive-only by design, and these tests exist to keep it that way.

**CC-F2 rewrote the card.** The supplier's own documents arrived
(docs/voip24hdocs/), and they contradicted what the card had been telling
operators to ask for. What they actually say:

* ``Authorization.docx`` — an API key and an API secret are exchanged for a
  token at ``POST /v3/authentication``. That is the customer's only credential.
* ``Webhook.docx`` — the customer registers a call-back address themselves at
  ``POST /v3/webhook-call-log/``, or hands it to the supplier's staff.
* The delivery carries ``msgid, id, calldate, callid, play, eplay, download,
  did, src, dst, status, note, disposition, billsec, duration, type`` — and
  **nothing identifying the customer**. There is no account id in an event, no
  signature and no signing header.

So the card no longer asks for an account name (it is not sent) or a signing
secret (there is none). T153 asserts that, because the previous wording sent a
real operator looking for a secret that does not exist.

The two suppliers' endpoints these tests DO exercise are patched at
``VoIP24hAPI._request`` and answer the documents' verbatim shapes — everything
above that seam runs for real. Fetching past calls and dialling from the server
are still unevidenced and still refused.

The legacy ``/voip24h/webhook`` route is unchanged and still resolves by
account id, so T150/T151 keep a legacy-shaped fixture (``_configured``).

Everything is a TransactionCase (ledger §5.32). The controller is tested
through the model methods it calls: an HttpCase in this module has poisoned
later suites before, and §5.75 means a manual run would error every one of
them in setUpClass anyway.
"""
import hashlib
import hmac
import json
from contextlib import contextmanager
from unittest.mock import patch

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

    def _configured(self, company=None, account=VOIP_ACCOUNT):
        """A LEGACY-shaped connection: a typed account id and a signing secret.

        `/voip24h/webhook` still exists and still resolves by account id, so
        the suites that prove its refusals need a connection in that shape.
        The Channel Center no longer produces one (see `_center_configured`),
        so this builds it directly rather than through a flow that would now
        do something else entirely.
        """
        conn = self._conn('call', company=company, state='testing',
                          resource_external_id=account)
        conn.action_set_secret('provider_secret', VOIP_SECRET)
        if self.has_voip:
            # The legacy route resolves its config BY ACCOUNT ID, so these
            # suites need the row that lookup will find. The Channel Center
            # used to make it as a side effect of being configured; it no
            # longer does, so the fixture asks for it directly.
            self.env['voip.config'].sudo()._sync_from_connection(
                conn, account_id=account)
        conn.invalidate_recordset()
        return conn

    @contextmanager
    def _provider_accepts(self, auth=True, register=True):
        """The supplier, answering exactly what their documents show.

        Patched at `_request` — the one HTTP seam — so everything above it runs
        for real: `authenticate` parses this, `_store_token` writes the state
        the card reads back, and the facade sees what a live call would leave
        behind. Patching higher would prove only that the stub was called.
        """
        from odoo.addons.health_voip24h.services.voip24h_api import VoIP24hAPI

        def _fake(api_self, method, path, **kwargs):
            if 'authentication' in path:
                if not auth:
                    raise UserError('The phone system refused these details.')
                # Authorization.docx, verbatim (status 1000, misspelt expried).
                return {'message': 'Success', 'status': 1000, 'data': {
                    'token': 'fixture-token',
                    'createAt': '2026-09-17 10:00:00',
                    'expried': '2026-09-24 10:00:00',
                    'isLonglive': True}}
            if 'webhook-call-log' in path:
                if not register:
                    raise UserError('The phone system refused the address.')
                # Webhook.docx, verbatim (status 200).
                return {'status': 200,
                        'message': 'Update webhook call log is success'}
            raise AssertionError('unexpected provider call: %s %s'
                                 % (method, path))

        with patch.object(VoIP24hAPI, '_request', _fake):
            yield

    def _center_configured(self, conn=None, register=True):
        """A connection set up the way the Calls card now does it."""
        conn = conn or self._call_conn()
        with self._provider_accepts():
            self.Conn.center_call_save_credentials(
                conn.id, 'fixture-api-key', 'fixture-api-secret')
            if register:
                self.Conn.center_call_register(conn.id)
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

    def test_150c_a_connection_for_another_account_never_lends_its_secret(self):
        """Self-review finding: two resolutions of one question disagree.

        The webhook router resolves the connection by ``account_id``; the
        config used to resolve it by COMPANY. When a company's Calls
        connection has claimed account **Y** and an event arrives for account
        **X** (a config whose account id was edited, or a second PBX), the
        company match would hand back the Y connection and verify X's event
        with Y's secret. It must fall through to the legacy column instead.
        """
        if not self.has_voip:
            self.skipTest('health_voip24h is not installed')
        other = self._conn('call', company=self.company, state='testing',
                           resource_external_id='SOME-OTHER-ACCOUNT')
        other.action_set_secret('provider_secret', 'the-other-accounts-secret')
        config = self.env['voip.config'].sudo().create({
            'name': 'Second PBX', 'account_id': VOIP_ACCOUNT,
            'company_id': self.company.id, 'webhook_secret': VOIP_SECRET,
            'auto_sync_enabled': False})

        self.assertFalse(config._channel_connection(),
                         'a connection that owns another account is not this '
                         "config's connection")
        raw = json.dumps(self._event()).encode()
        self.assertTrue(
            config._verify_webhook_signature(raw, _sign(VOIP_SECRET, raw)),
            'it must fall through to this config\'s own secret')
        self.assertFalse(
            config._verify_webhook_signature(
                raw, _sign('the-other-accounts-secret', raw)),
            "another account's secret must never validate this event")

    def test_150d_cdr_sync_refuses_without_credentials(self):
        """The cron is the ONE path into the unverified API with no gate.

        `action_sync_call_history` and the wizard both call
        `_check_credentials()` first; `cron_sync_call_history` does not — it
        selects on auto_sync_enabled + state and calls straight through. A
        Center-created config is kept out of that domain, but the domain is
        two editable booleans away from letting it in, so the guard belongs in
        `sync_call_history` where every caller inherits it.
        """
        if not self.has_voip:
            self.skipTest('health_voip24h is not installed')
        from odoo.addons.health_voip24h.services.cdr_sync import (
            sync_call_history,
        )
        conn = self._configured()
        config = self.env['voip.config'].sudo().search(
            [('account_id', '=', VOIP_ACCOUNT)], limit=1)
        self.assertFalse(config.api_key)
        raised = False
        try:
            sync_call_history(config)
        except UserError:
            raised = True
        self.assertTrue(raised, 'no credentials must fail closed BEFORE the '
                                'first byte leaves for an endpoint nobody has '
                                'verified')

    # =================================================================
    # T150e/f — the cross-company account-id collision (review CRITICAL)
    # =================================================================
    def test_150e_a_second_company_cannot_claim_an_account_id(self):
        """The cross-tenant claim is now structurally impossible (CC-F2).

        `call` USED TO BE the one channel whose resource id a tenant typed, and
        an unchecked claim reached across tenants: typing a neighbour's account
        name made the route resolve THEIR event to YOUR connection. The refusal
        is still there, but it can no longer be provoked from the UI — nobody
        types the key any more. It is minted per company from random bytes, so
        two clinics cannot collide even deliberately.
        """
        if not self.has_voip:
            self.skipTest('health_voip24h is not installed')
        first = self._center_configured()
        mine = first.resource_external_id
        self.assertTrue(mine, 'the connection is linked to its phone account')
        self.assertNotEqual(mine, VOIP_ACCOUNT,
                            'the key is minted here, not typed by anybody')

        # Another company, its own admin, its own Center.
        other = self._conn('call', company=self.company2, state='authorizing')
        self._center_configured(conn=other, register=False)
        other.invalidate_recordset()
        self.assertTrue(other.resource_external_id)
        self.assertNotEqual(other.resource_external_id, mine,
                            'two clinics can never share a routing key')

        # Nothing a tenant can type reaches the routing key at all — which is
        # the point. The deployment-wide refusal is kept in
        # `center_call_save_credentials` for a database where a collision
        # somehow already exists, but it is no longer reachable from the UI.
        self.assertEqual(
            self.Conn.sudo().with_context(active_test=False).search_count(
                [('channel', '=', 'call'),
                 ('resource_external_id', '=', mine)]), 1)

    def test_150f_a_foreign_connection_never_speaks_for_a_config(self):
        """The guard for databases where a collision already exists."""
        if not self.has_voip:
            self.skipTest('health_voip24h is not installed')
        # Company 2 holds the account id; company 1 owns the legacy config.
        stranger = self._conn('call', company=self.company2, state='testing',
                              resource_external_id=VOIP_ACCOUNT)
        stranger.action_set_secret('provider_secret', 'the-strangers-secret')
        config = self.env['voip.config'].sudo().create({
            'name': 'Company 1 PBX', 'account_id': VOIP_ACCOUNT,
            'company_id': self.company.id, 'webhook_secret': VOIP_SECRET,
            'webhook_enabled': False, 'auto_sync_enabled': False})

        Cfg = self.env['voip.config']
        self.assertTrue(Cfg._resolve_channel_connection(VOIP_ACCOUNT),
                        'fixture guard: the stranger IS resolvable by id')
        self.assertIsNone(
            Cfg._route_channel_connection(config, VOIP_ACCOUNT),
            "a connection from another company must not speak for this config "
            "— that is what skipped the owner's webhook_enabled switch")

        # And the owner's own secret is what verifies, not the stranger's.
        raw = json.dumps(self._event()).encode()
        self.assertTrue(
            config._verify_webhook_signature(raw, _sign(VOIP_SECRET, raw)))
        self.assertFalse(
            config._verify_webhook_signature(
                raw, _sign('the-strangers-secret', raw)))

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
        # FORCED FIXTURE EDIT (CC-G): company2, not company. The migration
        # looks for an existing Calls connection with `active_test=False`
        # (correctly — §5.27), so setUpClass archiving the deployment's live
        # rows does NOT hide them from it. vietuat grew an `authorizing` call
        # connection for company 1 today, and this test then measured "0
        # created, 1 already present" and failed on live data rather than on
        # code. A company created inside the transaction has no live rows by
        # construction.
        config = self.env['voip.config'].sudo().create({
            'name': 'Legacy PBX', 'account_id': VOIP_ACCOUNT,
            'company_id': self.company2.id, 'webhook_secret': VOIP_SECRET,
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
        # FORCED FIXTURE EDIT (CC-G) — see test_151b: company2 keeps the
        # migration's active_test=False lookup away from the deployment's own
        # Calls connection.
        config = self.env['voip.config'].sudo().create({
            'name': 'Legacy PBX', 'account_id': VOIP_ACCOUNT,
            'company_id': self.company2.id,
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
                 ('company_id', '=', self.company2.id)]), 1)

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
        # The LEGACY signed route stays OFF, and that is a change of posture,
        # not a regression. Before the rebuild `_sync_from_connection` forced
        # `webhook_enabled = True`, which switched on the old
        # `/voip24h/webhook` route for every connection the Center made —
        # including ones that would never use it. Call records now arrive on
        # the v3 receivers, so the old route is opt-in and off until somebody
        # knows a producer still posts to it.
        self.assertFalse(config.webhook_enabled,
                         'the legacy signed route is opt-in since the rebuild')

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
        conn = self._call_conn()
        card = next(c for c in self.Conn.center_overview()
                    if c['channel'] == 'call')
        self.assertTrue(card['available'])
        self.assertTrue(card['implemented'])
        self.assertTrue(card.get('notice'))
        notice = card['notice'].lower()
        self.assertIn('not offered here', notice)
        self.assertIn('past call history', notice)
        # CC-F2: the notice may no longer claim the supplier's documentation
        # cannot be read. It can — it is in docs/voip24hdocs/ — and saying
        # otherwise is what let the rest of the card go unchecked for so long.
        self.assertNotIn('appointment', notice)

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
            # center_test raises the card notice itself (03103e07 wording).
            self.assertIn('not offered here', str(exc).lower())
        self.assertTrue(raised)

        # The adapter itself refuses too — the honesty is not only in the UI.
        raised = False
        try:
            conn.sudo()._get_adapter().test_connection()
        except Exception as exc:  # ChannelSendError
            raised = True
            self.assertIn('cannot verify', str(exc).lower())
        self.assertTrue(raised)

    def test_153b_a_credential_the_provider_refuses_is_never_stored(self):
        """The state that would make this card lie.

        A key kept without ever being accepted reads as set up, and no call
        ever arrives. The save authenticates first and raises on refusal, and
        a raising request rolls its transaction back — so nothing is kept.
        """
        if not self.has_voip:
            self.skipTest('health_voip24h is not installed')
        conn = self._call_conn()

        for key, secret in (('', ''), ('key-only', ''), ('', 'secret-only')):
            raised = False
            try:
                self.Conn.center_call_save_credentials(conn.id, key, secret)
            except UserError:
                raised = True
            self.assertTrue(raised, 'both halves are required')

        raised = False
        try:
            with self._provider_accepts(auth=False):
                self.Conn.center_call_save_credentials(conn.id, 'k', 's')
        except UserError:
            raised = True
        self.assertTrue(raised, 'a refused credential must raise')
        conn.invalidate_recordset()
        info = self.Conn.center_call_info(conn.id)
        self.assertFalse(info.get('credentials_ok'),
                         'a refused credential must never read as working')

    def test_153c_no_credential_ever_comes_back(self):
        if not self.has_voip:
            self.skipTest('health_voip24h is not installed')
        conn = self._center_configured()
        info = self.Conn.center_call_info(conn.id)
        self.assertTrue(info['has_credentials'])
        self.assertTrue(info['credentials_ok'])
        self.assertTrue(info['registered'])
        blob = json.dumps(info) + json.dumps(self.Conn.center_overview())
        for secret in ('fixture-api-key', 'fixture-api-secret',
                       'fixture-token'):
            self.assertNotIn(secret, blob)
        # The v3 receiver, not the legacy route — and the token half of the
        # address is masked for anybody who is not a system administrator.
        self.assertIn('/voip24h/v3/cdr/', info['callback_url'])

    # =================================================================
    # T154 — spoof: a plain CRM user and another company's connection
    # =================================================================
    def test_154_call_endpoints_refuse_a_spoof(self):
        conn = self._call_conn()
        as_user = self.Conn.with_user(self.crm_user)
        for call in (
            lambda m: m.center_call_info(conn.id),
            lambda m: m.center_call_save_credentials(conn.id, 'k', 's'),
            lambda m: m.center_call_register(conn.id),
        ):
            raised = False
            try:
                call(as_user)
            except (UserError, AccessError):
                raised = True  # §5.70: never a tuple in assertRaises
            self.assertTrue(raised, 'a plain CRM user must be refused')
        self.assertFalse(conn.sudo().provider_secret_enc,
                         'a refused call must store no secret')

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
        # GA1 forced edit (conventions §5.62): acquisition cards contributed
        # by `_center_extra_cards()` are filtered out — this assertion is
        # about the conversation catalogue.
        cards = [c for c in self.Conn.center_overview()
                 if c.get('kind', 'conversation') != 'acquisition']
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

        # Calls must not be marked done merely because credentials were pasted:
        # the last step still waits for a real call record and offers only
        # "Check again" until one arrives.
        self.assertIn('refreshCallStatus', script)
        self.assertIn('Check again', arch)
        self.assertIn('registerCallWebhook', script)

        # CC-F2: the card must not ask for the things the supplier's documents
        # show it never sends. This is the assertion that would have caught the
        # wrong screen, so each is pinned by the exact string that was there.
        # Scoped to strings only the CALLS block ever had — `Webhook secret` on
        # its own is Zalo's, and Zalo really does issue one.
        for gone in ('callAccountId',
                     'account identifier included in every event',
                     'X-Voip24h-Signature',
                     'signing secret used for this webhook'):
            self.assertNotIn(gone, arch, gone)
