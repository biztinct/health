# -*- coding: utf-8 -*-
"""Multi-account channels + the Unrouted queue + channel attribution.

Covers the three client requirements that landed together:

1. two Facebook pages / two Zalo accounts under ONE company, and walk-in as a
   conversation channel that is deliberately NOT connectable;
2. every contact autologged — the Unrouted queue behind each of the drop
   points that used to end in a log line;
3. GCLID and the Facebook / Zalo equivalents.

TransactionCase only, like every other suite here (ledger §5.32). Every
provider payload is a simulated fixture; nothing reaches a real provider.
"""
import json
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from odoo.addons.health_care_command.models.care_conversation import (
    CHANNEL_SELECTION, CONNECTABLE_CHANNELS,
)
from odoo.addons.health_care_command_channels.models.channel_center import (
    CENTER_CHANNELS,
)

from .common_spine import FB_PAGE_ID, ChannelSpineCase

FB_PAGE_2 = 'PAGE_2'


@tagged('post_install', '-at_install')
class TestMultiAccount(ChannelSpineCase):

    # ==================================================================
    # Walk-in: a conversation channel that can never be connected
    # ==================================================================
    def test_ma_01_walk_in_is_not_connectable(self):
        keys = [k for k, _l in CHANNEL_SELECTION]
        self.assertIn('walk_in', keys,
                      'walk-in must be a conversation channel')
        self.assertNotIn('walk_in', CONNECTABLE_CHANNELS,
                         'walk-in has no provider and no adapter')
        self.assertNotIn('walk_in', CENTER_CHANNELS,
                         'the Center must not offer a Connect button for it')
        # The catalogue is unchanged in size: 8 connectable channels.
        self.assertEqual(len(CENTER_CHANNELS), 8)

    def test_ma_02_walk_in_connection_refused(self):
        with self.assertRaises(ValueError):
            # An invalid Selection value: walk_in is not in the connection's
            # own list, so it can never become a care.channel.connection.
            self._conn('walk_in')

    def test_ma_03_log_walk_in(self):
        Care = self.env['care.conversation']
        res = Care.action_log_walk_in(name='Chị Lan', phone='0901234567',
                                      note='Hỏi về khám tổng quát')
        self.assertTrue(res['ok'])
        conv = Care.browse(res['conversation_id'])
        self.assertEqual(conv.channel_primary, 'walk_in')
        self.assertEqual(conv.channel_effective, 'walk_in')
        self.assertEqual(conv.status, 'needs_reply')
        self.assertTrue(conv.has_channel_activity,
                        'somebody physically arrived — that is real traffic')

        # Idempotent on the same phone: the same person coming back twice is
        # one conversation, not two.
        again = Care.action_log_walk_in(name='Chị Lan', phone='0901234567')
        self.assertEqual(again['conversation_id'], conv.id)

    def test_ma_04_walk_in_needs_a_way_to_reply(self):
        with self.assertRaises(UserError):
            self.env['care.conversation'].action_log_walk_in(name='Nobody')

    # ==================================================================
    # Two accounts on one channel
    # ==================================================================
    def test_ma_10_two_pages_one_company(self):
        first = self._fb_conn()
        second = self._fb_conn(page_id=FB_PAGE_2)
        self.assertNotEqual(first.id, second.id)
        self.assertEqual(first.company_id, second.company_id)
        both = self.Conn.search([('channel', '=', 'fb'),
                                 ('company_id', '=', self.company.id)])
        self.assertEqual(len(both), 2,
                         'the old (channel, company) index blocked this')

    def test_ma_11_same_page_twice_refused(self):
        self._fb_conn()
        # A clean ValidationError from the PRE-check, not an IntegrityError
        # that would poison the transaction (ledger §5.3).
        with self.assertRaises(ValidationError):
            self._conn('fb', state='ready', resource_external_id=FB_PAGE_ID)

    def test_ma_12_same_page_other_company_refused(self):
        self._fb_conn()
        with self.assertRaises(ValidationError):
            self._conn('fb', company=self.company2, state='ready',
                       resource_external_id=FB_PAGE_ID)

    def test_ma_13_webchat_default_is_shared(self):
        """webchat uses the literal 'default' for every company on purpose."""
        self._wc_conn()
        other = self._conn('webchat', company=self.company2,
                           state='testing', resource_external_id='default')
        self.assertTrue(other.exists(),
                        'the cross-company index must exclude webchat')

    def test_ma_14_unclaimed_rows_are_unconstrained(self):
        """Two half-finished rows may coexist: a tenant has to be able to
        start their second account while the first is mid-stepper."""
        self._conn('fb')
        second = self._conn('fb')
        self.assertTrue(second.exists())

    # ==================================================================
    # Outbound goes back out the account it came in on
    # ==================================================================
    def test_ma_20_reply_uses_the_arrival_account(self):
        first = self._fb_conn()
        second = self._fb_conn(page_id=FB_PAGE_2)
        # A thread that arrived on the SECOND page.
        ident = self.Identity._upsert(second, 'PSID_2', 'Anh Minh')
        conv = self.Care.sudo()._find_or_create_for(
            {'channel_identity_id': ident.id},
            {'channel': 'fb', 'inbound': True, 'set_status': 'needs_reply'})
        self.assertEqual(conv.sudo()._sendable_connection(), second,
                         'replying from the other page reaches nobody')
        self.assertNotEqual(conv.sudo()._sendable_connection(), first)

    def test_ma_21_reconnect_follows_the_same_page(self):
        """A disconnected account's peers follow the page to its NEW row —
        but never to a sibling page."""
        first = self._fb_conn()
        other_page = self._fb_conn(page_id=FB_PAGE_2)
        ident = self.Identity._upsert(first, 'PSID_1', 'Chị Lan')
        conv = self.Care.sudo()._find_or_create_for(
            {'channel_identity_id': ident.id},
            {'channel': 'fb', 'inbound': True, 'set_status': 'needs_reply'})

        # The page's own connection goes down and is archived.
        first.with_context(**self._internal_ctx()).write({'active': False})
        self.assertFalse(conv.sudo()._sendable_connection(),
                         'must NOT fall back to the other page')

        # Reconnecting the SAME page id gives the old peers a route again.
        replacement = self._fb_conn(page_id=FB_PAGE_ID)
        self.assertEqual(conv.sudo()._sendable_connection(), replacement)
        self.assertNotEqual(conv.sudo()._sendable_connection(), other_page)

    def _internal_ctx(self):
        from odoo.addons.health_care_command_channels.models\
            .care_channel_connection import INTERNAL_CTX
        return {INTERNAL_CTX: True}

    # ==================================================================
    # The catalogue lists every account
    # ==================================================================
    def test_ma_30_overview_lists_accounts(self):
        self._fb_conn()
        second = self._fb_conn(page_id=FB_PAGE_2)
        second.write({'account_label': 'Messenger — Hà Nội'})

        cards = self.Conn.center_overview()
        card = next(c for c in cards if c['channel'] == 'fb')
        self.assertEqual(len(card['accounts']), 2)
        self.assertTrue(card['multi_account'])
        self.assertTrue(card['can_add_account'])
        labels = [a['account_label'] for a in card['accounts']]
        self.assertIn('Messenger — Hà Nội', labels)
        # Every account carries its own id and state, so a broken second page
        # cannot hide behind a healthy first one.
        self.assertEqual(len({a['connection_id'] for a in card['accounts']}), 2)

    def test_ma_31_card_headline_is_the_healthiest_account(self):
        healthy = self._fb_conn()
        broken = self._fb_conn(page_id=FB_PAGE_2)
        broken._transition('error', reason='test')

        cards = self.Conn.center_overview()
        card = next(c for c in cards if c['channel'] == 'fb')
        self.assertEqual(card['state'], 'ready',
                         'a channel with one working page works')
        self.assertEqual(card['connection_id'], healthy.id)
        states = {a['connection_id']: a['state'] for a in card['accounts']}
        self.assertEqual(states[broken.id], 'error',
                         'the broken account is listed, not hidden')

    def test_ma_32_webchat_is_single_account(self):
        self._wc_conn()
        cards = self.Conn.center_overview()
        card = next(c for c in cards if c['channel'] == 'webchat')
        self.assertFalse(card['multi_account'])
        self.assertFalse(card['can_add_account'])

    def test_ma_33_no_credentials_in_the_account_payload(self):
        """T97's rule extends to the per-account rows."""
        conn = self._fb_conn()
        conn.write({'account_label': 'Messenger — HCM'})
        blob = json.dumps(self.Conn.center_overview(), default=str)
        self.assertNotIn('fb-page-token-fixture', blob)

    def test_ma_34_rename_account(self):
        conn = self._fb_conn()
        self.Conn.center_rename_account(conn.id, '  Messenger — HCM  ')
        self.assertEqual(conn.account_label, 'Messenger — HCM')
        self.assertIn('Messenger — HCM', conn.display_name)


@tagged('post_install', '-at_install')
class TestContactCapture(ChannelSpineCase):
    """Client requirement 2 — nothing vanishes in thin air."""

    def setUp(self):
        super().setUp()
        self.Capture = self.env['care.contact.capture']

    def test_cap_01_unknown_page_is_captured(self):
        """A verified webhook for a page nobody connected."""
        self._fb_conn()
        before = self.Care.search_count([])
        counts = self.Message._dispatch_meta(
            'fb', self.fb_payload(page_id='PAGE_NOBODY_CONNECTED'))
        self.assertEqual(counts['unknown'], 1)
        self.assertEqual(self.Care.search_count([]), before,
                         'an unknown page must NOT create a conversation')
        row = self.Capture.search([('reason_code', '=', 'unknown_resource')])
        self.assertEqual(len(row), 1)
        self.assertEqual(row.resource_external_id, 'PAGE_NOBODY_CONNECTED')
        self.assertEqual(row.state, 'new')

    def test_cap_02_half_configured_channel_is_captured(self):
        conn = self._conn('fb', state='authorizing',
                          resource_external_id=FB_PAGE_ID)
        counts = self.Message._dispatch_connection(conn, self.fb_payload())
        self.assertEqual(counts['ignored'], 1)
        row = self.Capture.search([('reason_code', '=', 'not_ingestable')])
        self.assertEqual(len(row), 1)
        self.assertEqual(row.connection_id, conn)

    def test_cap_03_redelivery_makes_one_row(self):
        self._fb_conn()
        payload = self.fb_payload(page_id='PAGE_NOBODY_CONNECTED')
        self.Message._dispatch_meta('fb', payload)
        self.Message._dispatch_meta('fb', payload)
        # No external_event_id on this reason, so dedupe is not claimed here —
        # what IS asserted is that a captured event carrying one dedupes.
        first = self.Capture._capture('no_anchor', 'zalo',
                                      external_event_id='evt-1', phone='0901234567')
        second = self.Capture._capture('no_anchor', 'zalo',
                                       external_event_id='evt-1', phone='0901234567')
        self.assertEqual(first, second)
        self.assertEqual(self.Capture.search_count(
            [('external_event_id', '=', 'evt-1')]), 1)

    def test_cap_04_convert_creates_one_conversation(self):
        row = self.Capture._capture('unknown_resource', 'fb',
                                    peer_hint='Chị Lan', phone='0901234567',
                                    body='Cho hỏi giá khám')
        self.assertTrue(row)
        row.action_convert()
        self.assertEqual(row.state, 'converted')
        self.assertTrue(row.conversation_id)
        self.assertEqual(row.conversation_id.status, 'needs_reply')
        self.assertEqual(row.conversation_id.channel_primary, 'fb')
        # Handled once.
        with self.assertRaises(UserError):
            row.action_convert()

    def test_cap_05_convert_needs_something_to_reply_to(self):
        row = self.Capture._capture('unknown_resource', 'fb',
                                    peer_hint='anonymous')
        with self.assertRaises(UserError):
            row.action_convert()

    def test_cap_06_dismiss(self):
        row = self.Capture._capture('spam_suspect', 'webchat',
                                    phone='0901234567')
        row.action_dismiss(reason='bot')
        self.assertEqual(row.state, 'dismissed')
        self.assertEqual(row.dismiss_reason, 'bot')

    def test_cap_07_evidence_is_immutable(self):
        row = self.Capture._capture('unknown_resource', 'fb',
                                    phone='0901234567')
        user_env = row.with_user(self.env.ref('base.user_admin'))
        with self.assertRaises(UserError):
            user_env.write({'reason_id': self.env['health.lookup.value']._default_for('unrouted_contact_reason', 'spam_suspect')})
        with self.assertRaises(UserError):
            user_env.write({'channel': 'zalo'})

    def test_cap_08_capture_never_breaks_the_caller(self):
        """A capture that cannot be written must not cost us the message."""
        with patch.object(type(self.Capture), 'create',
                          side_effect=Exception('boom')):
            self.assertFalse(
                self.Capture._capture('unknown_resource', 'fb',
                                      phone='0901234567'))
        # And the transaction is still usable afterwards.
        self.assertTrue(self.Care.search_count([]) >= 0)

    def test_cap_09_secrets_never_reach_the_queue(self):
        row = self.Capture._capture(
            'unknown_resource', 'fb',
            raw='{"access_token": "SECRET-VALUE", "text": "hi"}')
        self.assertNotIn('SECRET-VALUE', row.raw_payload or '')

    def test_cap_10_raw_payload_keeps_more_than_a_log_line(self):
        """The evidence cap is 8 KB, not the 300-char detail cap."""
        long_body = 'x' * 4000
        row = self.Capture._capture('unknown_resource', 'fb', raw=long_body)
        self.assertGreater(len(row.raw_payload), 1000)

    def test_cap_11_badge_counts_only_the_backlog(self):
        self.Capture._capture('unknown_resource', 'fb', phone='0901234567')
        handled = self.Capture._capture('unknown_resource', 'fb',
                                        phone='0907654321')
        self.assertEqual(self.Capture.unrouted_count(), 2)
        handled.action_dismiss()
        self.assertEqual(self.Capture.unrouted_count(), 1)

    def test_cap_12_webchat_abandoned_is_captured(self):
        """A visitor who left a phone number and typed nothing."""
        self._wc_conn()
        self.Message._webchat_start(name='Chị Lan', phone='0901234567')
        row = self.Capture.search([('reason_code', '=', 'webchat_abandoned')])
        self.assertEqual(len(row), 1)
        self.assertEqual(row.phone_normalized, '0901234567')

    def test_cap_13_a_real_chat_is_not_captured_twice(self):
        """Once they actually type, the conversation is the record."""
        self._wc_conn()
        started = self.Message._webchat_start(name='Chị Lan',
                                              phone='0901234567')
        self.Message._webchat_ingest(started['session'], 'Cho hỏi giá khám')
        # Re-opening the widget must not add a second capture.
        self.Message._webchat_start(session=started['session'],
                                    name='Chị Lan', phone='0901234567')
        self.assertEqual(
            self.Capture.search_count([('reason_code', '=', 'webchat_abandoned')]),
            1, 'first capture stands; a live chat adds nothing')

    def _stored_score(self, conv):
        """Read the COLUMN, not the field.

        `urgency_score` is a stored compute, so reading it through the ORM can
        trigger the very recomputation this test is trying to prove the cron is
        responsible for. Going to SQL is the only way to see what the wall
        would actually have sorted on.
        """
        self.env.cr.execute(
            'SELECT urgency_score FROM care_conversation WHERE id = %s',
            (conv.id,))
        return self.env.cr.fetchone()[0]

    def test_cap_14_ageing_moves_an_untouched_conversation(self):
        """`urgency_score` is evaluated at write time, so without the cron an
        untouched conversation never ages and the wall ordering lies."""
        conv = self.Care.sudo()._find_or_create_for(
            {'phone_normalized': '0901234567'},
            {'channel': 'call', 'inbound': True, 'set_status': 'needs_reply'})
        # Nobody has touched it for well over a day. Written through the ORM so
        # the score is computed once, exactly as a real inbound would.
        conv.sudo().write({'last_inbound_at': fields.Datetime.subtract(
            fields.Datetime.now(), hours=30)})
        conv.flush_recordset()
        true_score = self._stored_score(conv)
        self.assertGreater(true_score, 40,
                           'a day-old unanswered contact scores high')

        # Simulate the stale column a never-rewritten conversation really has.
        # The invalidation is load-bearing: raw SQL leaves the ORM cache
        # holding the OLD value, and a recompute that matches cache writes
        # nothing — so without this the test would fail for a reason the cron
        # never encounters (a real cron searches with a cold cache).
        self.env.cr.execute(
            'UPDATE care_conversation SET urgency_score = 1 WHERE id = %s',
            (conv.id,))
        conv.invalidate_recordset(['urgency_score'])
        self.assertEqual(self._stored_score(conv), 1)

        self.Care._cron_age_conversations()
        self.assertEqual(self._stored_score(conv), true_score,
                         'the cron must restore the true score')


@tagged('post_install', '-at_install')
class TestChannelAttribution(ChannelSpineCase):
    """Client requirement 3 — GCLID and the Facebook / Zalo equivalents."""

    def setUp(self):
        super().setUp()
        self.Touch = self.env['health.lead.touchpoint']

    def test_at_01_webchat_captures_the_click_id(self):
        self._wc_conn()
        started = self.Message._webchat_start(
            name='Chị Lan', phone='0901234567',
            attribution={'gclid': 'TEST-GCLID-123',
                         'utm_source': 'google', 'utm_medium': 'cpc',
                         'page_url': 'https://vietuc.example/kham?gclid=x',
                         'evil_key': 'dropped'})
        self.Message._webchat_ingest(started['session'], 'Cho hỏi giá khám')

        touch = self.Touch.sudo().search([], order='id desc', limit=1)
        self.assertEqual(touch.gclid, 'TEST-GCLID-123')
        self.assertEqual(touch.utm_source, 'google')
        self.assertTrue(touch.conversation_id)
        self.assertFalse(touch.lead_id, 'a chat touch precedes any lead')

    def test_at_02_attribution_is_whitelisted(self):
        cleaned = self.Care._clean_attribution({
            'gclid': 'ok', 'evil_key': 'no', 'utm_source': 'google'})
        self.assertEqual(set(cleaned), {'gclid', 'utm_source'})
        self.assertEqual(self.Care._clean_attribution('not a dict'), {})

    def test_at_03_messenger_referral_is_parsed(self):
        from odoo.addons.health_care_command_channels.services.adapters import (
            _fb_referral,
        )
        parsed = _fb_referral({'referral': {
            'ref': 'promo-tet-2026', 'source': 'ADS', 'type': 'OPEN_THREAD',
            'ad_id': '120200000000000',
            'ads_context_data': {'ad_title': 'Khám tổng quát Tết'},
        }})
        self.assertEqual(parsed['referral_ref'], 'promo-tet-2026')
        self.assertEqual(parsed['ad_id'], '120200000000000')
        self.assertEqual(parsed['utm_campaign'], 'Khám tổng quát Tết')
        self.assertEqual(parsed['utm_source'], 'facebook')
        # An organic message carries none of this.
        self.assertEqual(_fb_referral({'message': {'text': 'hi'}}), {})
        # And it is read from all three places Meta puts it.
        self.assertEqual(
            _fb_referral({'postback': {'referral': {'ref': 'x'}}})['referral_ref'],
            'x')

    def test_at_04_account_defaults_are_the_floor(self):
        """A page with no per-event data still attributes to its own account."""
        source = self.env['utm.source'].create({'name': 'Messenger HCM'})
        conn = self._fb_conn()
        conn.write({'utm_source_id': source.id})
        ident = self.Identity._upsert(conn, 'PSID_9', 'Anh Minh')
        conv = self.Care.sudo()._find_or_create_for(
            {'channel_identity_id': ident.id},
            {'channel': 'fb', 'inbound': True, 'set_status': 'needs_reply'})
        conv._record_attribution({}, connection=conn)
        touch = self.Touch.sudo().search([('conversation_id', '=', conv.id)])
        self.assertEqual(touch.utm_source, 'Messenger HCM')

    def test_at_05_first_touch_wins(self):
        conn = self._fb_conn()
        ident = self.Identity._upsert(conn, 'PSID_8', 'Anh Minh')
        conv = self.Care.sudo()._find_or_create_for(
            {'channel_identity_id': ident.id},
            {'channel': 'fb', 'inbound': True, 'set_status': 'needs_reply'})
        conv._record_attribution({'referral_ref': 'first'}, connection=conn)
        conv._record_attribution({'referral_ref': 'second'}, connection=conn)
        touches = self.Touch.sudo().search([('conversation_id', '=', conv.id)])
        self.assertEqual(len(touches), 1)
        self.assertEqual(touches.referral_ref, 'first')

    def test_at_06_zalo_ref_bucket(self):
        parsed = self.Message._zalo_attribution({
            'event_name': 'user_click_chatnow',
            'info': {'ref': 'zalo-ad-42'},
        })
        self.assertEqual(parsed['referral_ref'], 'zalo-ad-42')
        self.assertEqual(parsed['referral_source'], 'zalo')
        # An ordinary inbound text carries no referral.
        self.assertEqual(
            self.Message._zalo_attribution({'event_name': 'user_send_text'}),
            {})

    def test_at_07_lead_inherits_the_click_id(self):
        """The payoff: a chat-originated lead is exportable to Google Ads."""
        self._wc_conn()
        started = self.Message._webchat_start(
            name='Chị Lan', phone='0901234567',
            attribution={'gclid': 'TEST-GCLID-777', 'utm_source': 'google',
                         'utm_medium': 'cpc'})
        msg = self.Message._webchat_ingest(started['session'], 'Cho hỏi giá')
        conv = msg.conversation_id
        self.assertTrue(conv)

        self.Care.action_create_lead(conv.id)
        lead = conv.lead_id
        self.assertTrue(lead, 'the lead itself must still be created')
        self.assertEqual(lead.gclid, 'TEST-GCLID-777')
        self.assertEqual(lead.source_id.name, 'google')
        touch = self.Touch.sudo().search([('conversation_id', '=', conv.id)])
        self.assertEqual(touch.lead_id, lead,
                         'the touch must follow the lead for W4 export')

    def test_at_08_touchpoint_must_belong_to_something(self):
        with self.assertRaises(ValidationError):
            self.Touch.sudo().create({
                'touchpoint_type_id': self.env['health.lookup.value']._default_for('touchpoint_type', 'manual'),
                'occurred_at': fields.Datetime.now(),
            })

    def test_at_09_review_queue_ignores_leadless_touches(self):
        """A chat touch with no lead must not flood the campaign review."""
        from odoo.addons.health_web_leads.models.lead_touchpoint import (
            UNMATCHED_CAMPAIGN_DOMAIN,
        )
        conn = self._fb_conn()
        ident = self.Identity._upsert(conn, 'PSID_7', 'Anh Minh')
        conv = self.Care.sudo()._find_or_create_for(
            {'channel_identity_id': ident.id},
            {'channel': 'fb', 'inbound': True, 'set_status': 'needs_reply'})
        conv._record_attribution({'utm_campaign': 'never-seeded'},
                                 connection=conn)
        hits = self.Touch.sudo().search(UNMATCHED_CAMPAIGN_DOMAIN)
        self.assertNotIn(conv.id, hits.mapped('conversation_id').ids)
