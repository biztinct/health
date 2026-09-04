# -*- coding: utf-8 -*-
"""T96–T105 — the Channel Connection Center (CC-C).

TransactionCase ONLY, like every other suite in this module (ledger §5.32),
and every provider call is mocked: nothing here can reach Telegram, Meta or
anyone else, and no credential in it is real.

Two test-writing rules earn their keep repeatedly below:

* a failure path that must leave NOTHING behind is asserted with
  ``try/except UserError``, never ``assertRaises`` — Odoo wraps the latter in a
  savepoint and rolls back every write made before the raise, which would make
  a leaky implementation look clean (ledger §5.8/§5.65);
* readiness is never asserted into place. Fixtures reach ``ready`` by proving
  checks, which is the behaviour under test.
"""
import json
import os
import re

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from odoo.addons.health_care_command_channels.controllers.webchat import (
    WebChatController,
)
from odoo.addons.health_care_command_channels.services.webhook_verify import (
    verify_telegram,
)

from .common_spine import TG_BOT_TOKEN, ChannelSpineCase

# A syntactically real-looking bot token that is not a real bot token.
TG_TOKEN = '777001:AAHfixture-token-value-not-real'
TG_BOT = {'ok': True, 'result': {'id': 777001, 'is_bot': True,
                                 'first_name': 'Viet Uc Care',
                                 'username': 'vietuc_care_bot'}}
HTTPS_BASE = 'https://care.example.test'


@tagged('post_install', '-at_install')
class TestChannelCenter(ChannelSpineCase):

    def _set_base_url(self, value):
        self.env['ir.config_parameter'].sudo().set_param('web.base.url', value)

    def _tenant_admin(self):
        return self._mk_user(
            'chub_tenant_admin', ['health_access.group_clinic_admin'])

    # ==================================================================
    # T96 — Amendment F1: a testing connection is not locked out (§5.66)
    # ==================================================================
    def test_96_testing_survives_missing_checks(self):
        conn = self._conn('webchat', state='testing',
                          resource_external_id='default')
        # Only ONE of the two required checks is proven so far.
        self.Check.upsert_check(conn, 'resource_selected', 'pass')
        self.assertEqual(
            conn.state, 'testing',
            'a merely-unproven check must not demote a connection that is '
            'still being set up')
        self.assertTrue(conn._may_ingest(),
                        'the connection must still accept the traffic that '
                        'would finish proving it')

        # The first real inbound: exactly what CC-B's ingest funnel does.
        conn._note_inbound()
        self.assertEqual(conn.state, 'ready')

        # ...and it got there without ever passing through action_required.
        moves = self.Audit.sudo().search([('connection_id', '=', conn.id),
                                          ('event', '=', 'health_transition')])
        self.assertFalse(
            [a for a in moves if 'action_required' in (a.detail_redacted or '')],
            'the connection must never have been demoted on the way to ready')

        # A genuine FAIL from testing still demotes — the fix narrows the
        # trigger, it does not remove it.
        other = self._conn('telegram', state='testing')
        self.Check.upsert_check(other, 'authorization_valid', 'fail')
        self.assertEqual(other.state, 'action_required')
        self.assertFalse(other._may_ingest())

    # ==================================================================
    # T97 — the catalogue: 8 honest cards, no secret material
    # ==================================================================
    def test_97_center_overview(self):
        tg = self._tg_conn()
        cards = self.Conn.center_overview()

        self.assertEqual([c['channel'] for c in cards],
                         ['zalo', 'call', 'email', 'zns', 'whatsapp', 'fb',
                          'telegram', 'webchat'],
                         'the catalogue is the dock order, all eight channels')

        blob = json.dumps(cards, default=str)
        for forbidden in (TG_BOT_TOKEN, 'chs$1$', tg.sudo().secret_hint):
            self.assertNotIn(forbidden, blob,
                             'no credential material may reach the browser')
        self.assertNotIn('provider_secret', blob)

        by_key = {c['channel']: c for c in cards}
        # Meta's platform app exists in this fixture, Zalo's and Google's do not.
        self.assertTrue(by_key['whatsapp']['available'])
        self.assertTrue(by_key['fb']['available'])
        for key in ('zalo', 'zns', 'email'):
            self.assertFalse(by_key[key]['available'],
                             '%s must read "not available yet" with no '
                             'platform app' % key)
            self.assertEqual(by_key[key]['primary_action'], 'unavailable')
        # FORCED EDIT (CC-F): `call` needs no platform app and its stepper is
        # now real, so it is available AND implemented. What keeps it honest is
        # not a disabled card but the receive-only notice it carries — CC-F
        # cannot verify VoIP24h's API, and the card says exactly that.
        self.assertTrue(by_key['call']['available'])
        self.assertTrue(by_key['call']['implemented'])
        self.assertIn('cannot verify', (by_key['call'].get('notice') or '').lower())
        # ZNS is a capability OF zalo, rendered inside its card.
        self.assertEqual(by_key['zns']['parent_channel'], 'zalo')

        # Archiving the platform app is the instant feature flag.
        self.meta_app.write({'active': False})
        again = {c['channel']: c for c in self.Conn.center_overview()}
        self.assertFalse(again['whatsapp']['available'])
        self.meta_app.write({'active': True})

        # The proven connection reads as connected, with its checks.
        card = by_key['telegram']
        self.assertEqual(card['state'], 'ready')
        self.assertEqual(card['primary_action'], 'open')
        self.assertEqual(card['checks_done'], card['checks_total'])
        self.assertTrue(card['implemented'])

        # Company isolation: another company's admin sees their own states.
        other_admin = self._mk_user(
            'chub_mgr_b', ['health_crm.group_health_crm_manager'],
            company=self.company2)
        theirs = {c['channel']: c
                  for c in self.Conn.with_user(other_admin).center_overview()}
        self.assertEqual(theirs['telegram']['state'], 'not_connected')
        self.assertFalse(theirs['telegram']['connection_id'])

    # ==================================================================
    # T98 — the tenant-admin ACL that CC-A deferred
    # ==================================================================
    def test_98_tenant_admin_acl(self):
        admin = self._tenant_admin()
        Conn = self.Conn.with_user(admin)

        # ...can run the happy path through the Center endpoints.
        info = Conn.center_begin('webchat')
        self.assertTrue(info['connection_id'])
        result = Conn.center_webchat_enable(
            info['connection_id'], ['https://vietuc.example'], 'Xin chào')
        self.assertEqual(result['state'], 'testing')
        self.assertTrue(Conn.center_overview())

        # ...and cannot forge a state by writing the record directly. The
        # model guard fires BEFORE the ACL, so this is UserError (ledger §5.39).
        conn = self.Conn.browse(info['connection_id'])
        with self.assertRaises(UserError):
            conn.with_user(admin).write({'state': 'ready'})
        with self.assertRaises(UserError):
            conn.with_user(admin).write({'resource_external_id': 'spoofed'})

        # The platform plane is not theirs at all.
        with self.assertRaises(AccessError):
            self.App.with_user(admin).search([])
        # The audit trail is readable, never writable.
        self.Audit.with_user(admin).search([], limit=1)
        with self.assertRaises(AccessError):
            self.Audit.with_user(admin).create({'event': 'forged'})

        # A plain CRM user is not a channel administrator.
        with self.assertRaises(UserError):
            self.Conn.with_user(self.crm_user).center_begin('telegram')

    # ==================================================================
    # T99 — Telegram: validate before storing anything
    # ==================================================================
    def test_99_telegram_validate(self):
        conn = self._conn('telegram', state='authorizing')

        # --- the refusal path stores NOTHING -------------------------
        # try/except, NOT assertRaises: the savepoint would roll back exactly
        # the writes this assertion exists to catch (ledger §5.8).
        raised = False
        try:
            with self.mock_get({'ok': False, 'description': 'Unauthorized'},
                               status=401):
                self.Conn.center_telegram_validate(conn.id, TG_TOKEN)
        except UserError:
            raised = True
        self.assertTrue(raised, 'an unusable key must be refused')
        conn.invalidate_recordset()
        self.assertEqual(conn.state, 'authorizing')
        self.assertFalse(conn.has_credentials)
        self.assertFalse(conn.resource_external_id)
        self.assertFalse(self.Check.sudo().search_count(
            [('connection_id', '=', conn.id)]))

        # An obvious paste accident never reaches the network at all.
        with self.mock_get(TG_BOT) as mocked:
            with self.assertRaises(UserError):
                self.Conn.center_telegram_validate(conn.id, 'not-a-token')
            mocked.assert_not_called()

        # --- the happy path ------------------------------------------
        with self.mock_get(TG_BOT):
            res = self.Conn.center_telegram_validate(conn.id, TG_TOKEN)
        self.assertEqual(res['bot_username'], 'vietuc_care_bot')
        self.assertNotIn(TG_TOKEN, json.dumps(res, default=str))
        conn.invalidate_recordset()
        self.assertEqual(conn.state, 'configuring')
        self.assertEqual(conn.resource_external_id, '777001')
        self.assertEqual(conn.resource_display_name, '@vietuc_care_bot')
        statuses = {c.check_key: c.status
                    for c in conn.sudo().readiness_check_ids}
        self.assertEqual(statuses.get('authorization_valid'), 'pass')
        self.assertEqual(statuses.get('resource_selected'), 'pass')

        # The key is in the database as ciphertext and nowhere else.
        self.env.flush_all()
        self.env.cr.execute(
            'SELECT provider_secret_enc FROM care_channel_connection '
            'WHERE id = %s', (conn.id,))
        stored = self.env.cr.fetchone()[0]
        self.env.invalidate_all()
        self.assertTrue(stored.startswith('chs$1$'))
        self.assertNotIn('AAHfixture', stored)

    # ==================================================================
    # T100 — Telegram: setWebhook, https only, idempotent
    # ==================================================================
    def test_100_telegram_register_webhook(self):
        conn = self._conn('telegram', state='configuring')
        conn.action_set_secret('provider_secret', TG_TOKEN)

        # http:// is refused BEFORE any provider call: Telegram would either
        # reject it or downgrade the hop.
        self._set_base_url('http://care.example.test')
        with self.mock_post({'ok': True}) as mocked:
            with self.assertRaises(UserError):
                self.Conn.center_telegram_register_webhook(conn.id)
            mocked.assert_not_called()
        conn.invalidate_recordset()
        self.assertFalse(conn.sudo().webhook_path_secret)

        self._set_base_url(HTTPS_BASE)
        with self.mock_post({'ok': True}) as mocked:
            self.Conn.center_telegram_register_webhook(conn.id)
            called_url = mocked.call_args.kwargs['json']['url']
            secret_token = mocked.call_args.kwargs['json']['secret_token']
            self.assertEqual(mocked.call_args.kwargs['json']['allowed_updates'],
                             ['message'])
        conn.invalidate_recordset()
        minted = conn.sudo().webhook_path_secret
        self.assertTrue(minted)
        self.assertEqual(secret_token, minted)
        self.assertEqual(
            called_url,
            '%s/care_channels/telegram/webhook/%s' % (HTTPS_BASE, minted))
        self.assertEqual(conn.webhook_state, 'subscribed')
        self.assertEqual(conn.state, 'testing')

        # Re-registering keeps the SAME secret: rotating it silently would
        # orphan a webhook Telegram still holds.
        with self.mock_post({'ok': True}):
            self.Conn.center_telegram_register_webhook(conn.id)
        conn.invalidate_recordset()
        self.assertEqual(conn.sudo().webhook_path_secret, minted)

    # ==================================================================
    # T101 — Telegram end to end, self-service, to ready
    # ==================================================================
    def test_101_telegram_full_flow(self):
        self._set_base_url(HTTPS_BASE)
        info = self.Conn.center_begin('telegram')
        conn = self.Conn.browse(info['connection_id'])
        self.assertEqual(info['mode'], 'guided_secret')
        self.assertEqual(len(info['guide_steps']), 4)

        with self.mock_get(TG_BOT):
            self.Conn.center_telegram_validate(conn.id, TG_TOKEN)
        with self.mock_post({'ok': True}):
            self.Conn.center_telegram_register_webhook(conn.id)
        conn.invalidate_recordset()
        self.assertEqual(conn.state, 'testing')
        self.assertNotIn('telegram', self.Care._channel_keys(),
                         'a channel still being proven must not light the dock')

        # The tenant messages the bot. The path secret is the credential and
        # the header carries the same value (CC-B verifier).
        secret = conn.sudo().webhook_path_secret
        self.assertTrue(verify_telegram(conn.sudo(), secret, secret))
        self.assertFalse(verify_telegram(conn.sudo(), secret, 'wrong-header'))
        counts = self.Message._dispatch_connection(
            conn.sudo(), self.tg_payload(chat_id=555777, message_id=1,
                                         text='chào bạn'))
        self.assertEqual(counts['ingested'], 1)
        conn.invalidate_recordset()
        self.assertEqual(conn.state, 'testing',
                         'the proving inbound must not lock the channel out')

        # The Center's synthetic reply proves outbound — and it is synthetic.
        with self.mock_post({'ok': True, 'result': {'message_id': 7,
                                                    'chat': {'id': 555777}}}) as mocked:
            result = self.Conn.center_test(conn.id)
        body = mocked.call_args.kwargs['json']['text']
        self.assertIn('test', body.lower())
        self.assertTrue(result['sent_to'])

        conn.invalidate_recordset()
        self.assertEqual(conn.state, 'ready')
        self.assertIn('telegram', self.Care._channel_keys())

    # ==================================================================
    # T102 — Web chat: one click, then the first real message
    # ==================================================================
    def test_102_webchat_enable(self):
        info = self.Conn.center_begin('webchat')
        conn = self.Conn.browse(info['connection_id'])
        self.assertEqual(info['mode'], 'one_click')

        for bad in ('javascript:alert(1)', 'vietuc.example',
                    'http://vietuc.example', 'https://vietuc.example/chat',
                    'https://vietuc.example?a=1', 'ftp://vietuc.example'):
            with self.assertRaises(UserError):
                self.Conn.center_webchat_enable(conn.id, [bad])
        with self.assertRaises(UserError):
            self.Conn.center_webchat_enable(conn.id, [])

        res = self.Conn.center_webchat_enable(
            conn.id,
            ['https://vietuc.example/', 'http://localhost:8069',
             'https://vietuc.example'],
            'Xin chào! Chúng tôi có thể giúp gì?')
        self.assertEqual(res['origins'],
                         ['https://vietuc.example', 'http://localhost:8069'],
                         'origins are normalised and de-duplicated; localhost '
                         'stays usable for a tenant testing locally')
        conn.invalidate_recordset()
        self.assertEqual(conn.state, 'testing')
        self.assertEqual(conn.get_setting('greeting'),
                         'Xin chào! Chúng tôi có thể giúp gì?')
        self.assertIn('?v=', res['snippet'])
        self.assertIn('data-origin=', res['snippet'])
        self.assertIn('/care_channels/webchat/demo', res['demo_url'])

        # The first real widget message is what finishes the setup.
        session = self.Message._webchat_start()['session']
        self.Message._webchat_ingest(session, 'tôi cần đặt lịch')
        conn.invalidate_recordset()
        self.assertEqual(conn.state, 'ready')
        self.assertIn('webchat', self.Care._channel_keys())

        # CC-B touch-up: the widget polls with POST, so the session id (the
        # visitor's credential for their own thread) stays out of proxy logs.
        routing = getattr(WebChatController.webchat_poll, 'original_routing', {})
        self.assertEqual(routing.get('methods'), ['POST'])
        rows = self.Message._webchat_poll(session, after_id=0)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['direction'], 'incoming')

    # ==================================================================
    # T103 — disconnect stops traffic; reconnect never re-asks for the key
    # ==================================================================
    def test_103_disconnect_reconnect(self):
        self._set_base_url(HTTPS_BASE)
        conn = self._tg_conn()
        payload = self.tg_payload(chat_id=555888, message_id=2)
        self.Message._dispatch_connection(conn.sudo(), payload)
        identity = self.identity_of(conn, '555888')
        conv = self.conv_of(identity)
        self.assertTrue(conv)

        self.Conn.center_disconnect(conn.id)
        conn.invalidate_recordset()
        self.assertEqual(conn.state, 'disabled')
        self.assertNotIn('telegram', self.Care._channel_keys())

        # A disabled channel must not keep filling the inbox.
        before = self.Audit.sudo().search_count(
            [('connection_id', '=', conn.id), ('event', '=', 'webhook_ignored')])
        counts = self.Message._dispatch_connection(
            conn.sudo(), self.tg_payload(chat_id=555888, message_id=3))
        self.assertEqual(counts['ignored'], 1)
        self.assertEqual(counts['ingested'], 0)
        self.assertEqual(self.Audit.sudo().search_count(
            [('connection_id', '=', conn.id),
             ('event', '=', 'webhook_ignored')]), before + 1)

        # ...and the composer refuses honestly rather than failing at Telegram.
        with self.assertRaises(UserError):
            self.Care.action_send_channel(conv.id, 'telegram', 'xin chào')

        # Reconnect: the key was never wiped, so nothing is asked for twice.
        self.assertTrue(conn.sudo().has_credentials)
        back = self.Conn.center_reconnect(conn.id)
        self.assertTrue(back['has_credentials'])
        conn.invalidate_recordset()
        self.assertEqual(conn.state, 'authorizing')
        with self.mock_post({'ok': True}):
            self.Conn.center_telegram_register_webhook(conn.id)
        conn.invalidate_recordset()
        self.assertEqual(conn.state, 'ready',
                         'the checks it already proved still count')
        self.assertIn('telegram', self.Care._channel_keys())

    # ==================================================================
    # T104 — center_begin is idempotent
    # ==================================================================
    def test_104_center_begin_idempotent(self):
        # FORCED EDIT (CC-D): both counts below used to be absolute, which only
        # held while the table was empty. The zalo migration now lands a
        # `legacy` row on every real database — archived by the shared fixture,
        # so `active_test=False` still SEES it. The contract this test exists
        # for is "a repeated begin creates no second row" and "a refused begin
        # creates nothing at all", so both are now relative to a baseline.
        #
        # FORCED EDIT (CC-E): `whatsapp` and `fb` left this list — their
        # onboarding is implemented from CC-E on, and the shared fixture seeds
        # the `meta` platform app, so `center_begin` on them now SUCCEEDS. That
        # is asserted below instead. (Ledger §5.62's family: widening what a
        # service accepts breaks the tests that assert what it refuses.)
        # FORCED EDIT (CC-F): `call` left this list for the same reason the
        # Meta pair did — its stepper is implemented and it needs no platform
        # app, so `center_begin('call')` now succeeds. `email` stays: it is
        # implemented too, but no google/microsoft platform app is seeded, so
        # the availability gate still refuses it (which is vietuat today).
        unimplemented = ['zalo', 'zns', 'email']
        before = self.Conn.with_context(active_test=False).search_count([
            ('channel', 'in', unimplemented),
            ('company_id', '=', self.company.id)])

        first = self.Conn.center_begin('webchat')
        second = self.Conn.center_begin('webchat')
        self.assertEqual(first['connection_id'], second['connection_id'])
        self.assertEqual(self.Conn.search_count([
            ('channel', '=', 'webchat'),
            ('company_id', '=', self.company.id)]), 1)

        # A channel whose flow does not exist yet says so instead of half
        # creating something.
        for channel in unimplemented:
            with self.assertRaises(UserError):
                self.Conn.center_begin(channel)
        self.assertEqual(self.Conn.with_context(active_test=False).search_count([
            ('channel', 'in', unimplemented),
            ('company_id', '=', self.company.id)]), before)
        with self.assertRaises(UserError):
            self.Conn.center_begin('not-a-channel')

        # CC-E: the two Meta channels DO begin now (a `meta` platform app is
        # seeded in this fixture), and are idempotent the same way.
        # CC-F: and so does `call`, which needs no platform app at all.
        for channel in ('whatsapp', 'fb', 'call'):
            first = self.Conn.center_begin(channel)
            second = self.Conn.center_begin(channel)
            self.assertEqual(first['connection_id'], second['connection_id'],
                             channel)
            self.assertEqual(self.Conn.search_count([
                ('channel', '=', channel),
                ('company_id', '=', self.company.id)]), 1, channel)
        self.assertEqual(self.Conn.center_begin('whatsapp')['mode'],
                         'embedded_signup')
        self.assertEqual(self.Conn.center_begin('fb')['mode'], 'oauth_popup')

    # ==================================================================
    # T105 — Vietnamese catalogue: present, marked, and actually applied
    # ==================================================================
    def test_105_vi_translations(self):
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'i18n', 'vi.po')
        with open(path, encoding='utf-8') as handle:
            content = handle.read()

        blocks = [b for b in re.split(r'\n\n+', content) if 'msgid "' in b]
        self.assertGreater(len(blocks), 20)

        # §29: an entry with no module comment CRASHES the registry load.
        # And (CC-C, found live): an entry with no `#:` OCCURRENCE line is
        # yielded by nothing at all — Odoo's PoFileReader emits one row per
        # occurrence, so a reference-less entry is invisible whatever comment
        # markers it carries. The whole catalogue shipped inert until this.
        for block in blocks[1:]:   # [0] is the header
            self.assertIn('#. module: health_care_command_channels', block,
                          'missing module comment:\n%s' % block[:120])
            self.assertIn('\n#: ', '\n' + block,
                          'a .po entry with no occurrence line is never read '
                          'at all:\n%s' % block[:160])
            if '#. odoo-python' in block or '#. odoo-javascript' in block:
                self.assertIn(
                    '#: code:addons/health_care_command_channels/', block,
                    'a code translation needs a code: occurrence:\n%s'
                    % block[:160])

        # A duplicated msgid is not valid PO and silently makes one of the two
        # translations unreachable.
        ids = re.findall(r'^msgid "(.+)"$', content, re.M)
        self.assertEqual(len(ids), len(set(ids)), 'duplicate msgid in vi.po')

        # §5.58: a CODE string with no odoo-python / odoo-javascript marker
        # ships inert. (Model/field/selection labels legitimately have none —
        # they are matched as model terms — so this is asserted per string.)
        for msgid in ('Not connected', 'Connected', 'Create your bot',
                      'Turn on web chat', 'Website widget',
                      'Health19 connection test — please ignore.',
                      'Channel Connection Center', 'Copied ✓',
                      'Waiting for the first message…'):
            self.assertIn('msgid "%s"' % msgid, content,
                          '%r is a Center string with no Vietnamese' % msgid)
            block = [b for b in blocks if 'msgid "%s"\n' % msgid in b + '\n']
            self.assertTrue(block, msgid)
            self.assertTrue(
                '#. odoo-python' in block[0] or '#. odoo-javascript' in block[0],
                'a code string with no marker is inert: %r' % msgid)

        # ...and it is really applied at runtime.
        if self.env['res.lang'].sudo().search_count([('code', '=', 'vi_VN')]):
            vi = self.Conn.with_context(lang='vi_VN')
            self.assertEqual(vi._center_state_chips()['ready'], 'Đã kết nối')
            steps = vi._center_guide_texts()
            self.assertEqual(
                steps['channel_hub.guide.webchat.enable']['title'],
                'Bật trò chuyện trên website')

    # ==================================================================
    # T106 — the off switch works mid-setup (CC-C review MED-1)
    # ==================================================================
    def test_106_disconnect_mid_setup(self):
        # A tenant who registered a webhook for the wrong bot must be able to
        # turn the channel off WITHOUT first finishing the setup that would
        # prove it: `testing` is ingestable, and before this fix it only
        # exited forward (ready/action_required), never to disabled.
        conn = self._conn('telegram', state='testing')
        self.assertTrue(conn._may_ingest())
        self.Conn.center_disconnect(conn.id)
        conn.invalidate_recordset()
        self.assertEqual(conn.state, 'disabled')
        self.assertFalse(conn._may_ingest())

        # ...and from configuring, the other ingestable mid-setup state.
        other = self._conn('webchat', state='configuring',
                           resource_external_id='default')
        self.Conn.center_disconnect(other.id)
        other.invalidate_recordset()
        self.assertEqual(other.state, 'disabled')

        # Restart-setup is the matching backward edge: reconnect from
        # `testing` goes to authorizing instead of raising a raw
        # transition-refused error at the tenant.
        third = self._conn('whatsapp', state='testing',
                           resource_external_id='PHONE_T106')
        back = self.Conn.center_reconnect(third.id)
        self.assertEqual(back['state'], 'authorizing')

        # ...and reconnect on a connection already authorizing is a no-op,
        # not a self-transition crash.
        again = self.Conn.center_reconnect(third.id)
        self.assertEqual(again['state'], 'authorizing')

    # ==================================================================
    # T107 — a tenant admin cannot reach another company's connection by id
    # ==================================================================
    def test_107_cross_company_id_passing(self):
        conn = self._tg_conn()   # company 1, ready
        intruder = self._mk_user(
            'chub_admin_b', ['health_access.group_clinic_admin'],
            company=self.company2)
        Conn = self.Conn.with_user(intruder)

        # Every conn_id endpoint refuses at the company gate — including the
        # ones that would write or send.
        for name, call in (
            ('disconnect', lambda: Conn.center_disconnect(conn.id)),
            ('reconnect', lambda: Conn.center_reconnect(conn.id)),
            ('test', lambda: Conn.center_test(conn.id)),
            ('register_webhook',
             lambda: Conn.center_telegram_register_webhook(conn.id)),
            ('webchat_settings',
             lambda: Conn.center_webchat_settings(conn.id)),
        ):
            with self.assertRaisesRegex(UserError, 'another company',
                                        msg=name):
                call()

        # The direct writers are gated the same way (AccessError when the
        # record rule hides the row first, UserError from the explicit gate).
        # try/except, not assertRaises: Odoo's savepoint-wrapping override
        # calls issubclass() on its argument, so a TUPLE of exception classes
        # is a TypeError there (unlike stock unittest).
        for name, call in (
            ('set_settings',
             lambda: conn.with_user(intruder).set_settings({'greeting': 'x'})),
            ('action_set_secret',
             lambda: conn.with_user(intruder).action_set_secret(
                 'provider_secret', '999:not-a-real-secret-value')),
        ):
            raised = False
            try:
                call()
            except (UserError, AccessError):
                raised = True
            self.assertTrue(raised, '%s must refuse a cross-company id' % name)

        # Nothing moved, nothing leaked into a state change.
        conn.invalidate_recordset()
        self.assertEqual(conn.state, 'ready')
