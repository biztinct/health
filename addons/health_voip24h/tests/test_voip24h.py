# -*- coding: utf-8 -*-
"""Unit tests for the parsers, the reducer and the guards.

What these prove and what they do not: unit tests prove parsing and state
reduction; the HTTP tests prove routing and authentication; mocked-SDK tests
prove UI transitions. **Only a real controlled phone call proves audio.** No
test in this file should ever be cited as evidence that the browser phone
works — that belongs to the P-series checks in the acceptance matrix, run with
a real handset.
"""

import json
from datetime import datetime, timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, tagged

from ..services import phone_ident
from ..services.event_normalizer import (
    dump_normalised,
    load_normalised,
    normalise_final_record,
    normalise_state_event,
    redact,
)
from ..services.event_reducer import ReduceQuarantine, reduce_event
from ..services.event_worker import drain_effects, drain_events
from ..services.voip24h_api import parse_provider_datetime


# The section 17.1 fixture: parser-only, never a number to dial.
FIXTURE_CDR = {
    'msgid': 'fixture-delivery-01',
    'id': 'fixture-cdr-01',
    'callid': 'fixture-call-01',
    'calldate': '2026-09-17 09:00:00',
    'src': '531',
    'dst': '0912345678',
    'type': 'outbound',
    'disposition': 'NO ANSWER',
    'status': 'NO ANSWER',
    'duration': '20',
    'billsec': '0',
}


@tagged('post_install', '-at_install')
class VoipCommon(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.config = cls.env['voip.config'].create({
            'name': 'Test Phone System',
            'account_id': 'ACC-TEST-001',
            'company_id': cls.env.company.id,
            'provider_timezone': 'Asia/Ho_Chi_Minh',
            'cdr_ingest_enabled': True,
            'state_ingest_enabled': True,
            'live_notifications_enabled': True,
        })
        cls.config._ensure_receiver()
        cls.extension = cls.env['voip.extension'].create({
            'name': 'Reception',
            'extension_number': '531',
            'voip_config_id': cls.config.id,
        })
        # The master database carries ~37k live partners, and a hard-coded
        # test number collides with real ones — which makes the matcher answer
        # "ambiguous", indistinguishable from a broken matcher. Pick a number
        # nothing in this database already uses (ledger §5.50's family: a
        # fixture that meets live data inherits it). Deterministic: the FIRST
        # unused candidate wins, in a fixed order.
        cls.peer = cls._unused_number()

    @classmethod
    def _unused_number(cls):
        Partner = cls.env['res.partner'].sudo()
        Lead = cls.env['crm.lead'].sudo()
        for suffix in range(100):
            candidate = '09777%05d' % suffix
            domain = ['|', ('phone', '=', candidate), ('mobile', '=', candidate)]
            if Partner.search_count(domain):
                continue
            if Lead.search_count([('phone', '=', candidate)]):
                continue
            return candidate
        raise AssertionError('no unused test phone number available')

    # -- helpers -------------------------------------------------------

    def _ingest_cdr(self, data, config=None):
        config = config or self.config
        normalised = normalise_final_record(config, data)
        return self.env['voip.call.event']._ingest(
            config, 'cdr', normalised,
            transport='get', auth_method='url_token',
            payload_redacted=dump_normalised(normalised, payload=redact(data)),
            payload_raw=json.dumps(data))

    def _ingest_state(self, data, config=None):
        config = config or self.config
        normalised = normalise_state_event(config, data)
        return self.env['voip.call.event']._ingest(
            config, 'state', normalised,
            transport='get', auth_method='url_token',
            payload_redacted=dump_normalised(normalised, payload=redact(data)),
            payload_raw=json.dumps(data))

    def _reduce(self, event):
        return reduce_event(self.env, event)


@tagged('post_install', '-at_install')
class TestAuthParsing(VoipCommon):
    """A01/A02 — the V1 body, including the vendor's misspelled expiry."""

    def test_01_expried_is_read_in_the_provider_timezone(self):
        parsed, quality = parse_provider_datetime(
            '2024-10-04 16:35:36', 'Asia/Ho_Chi_Minh')
        self.assertEqual(quality, 'ok')
        # 16:35:36 +07 is 09:35:36 UTC. Odoo stores naive UTC.
        self.assertEqual(parsed, datetime(2024, 10, 4, 9, 35, 36))
        self.assertIsNone(parsed.tzinfo)

    def test_02_missing_expiry_is_visible_not_assumed(self):
        parsed, quality = parse_provider_datetime('', 'Asia/Ho_Chi_Minh')
        self.assertIsNone(parsed)
        self.assertEqual(quality, 'missing')

    def test_03_unparsable_expiry_is_flagged(self):
        parsed, quality = parse_provider_datetime('next tuesday', 'Asia/Ho_Chi_Minh')
        self.assertIsNone(parsed)
        self.assertEqual(quality, 'unparsable')

    def test_04_no_timezone_configured_is_its_own_answer(self):
        parsed, quality = parse_provider_datetime('2024-10-04 16:35:36', '')
        self.assertIsNone(parsed)
        self.assertEqual(quality, 'no_timezone')

    def test_05_storing_a_token_without_an_expiry_degrades_the_connection(self):
        self.config._store_token('tok', expires_at=None,
                                 expiry_quality='missing', longlive=False)
        self.assertEqual(self.config.state, 'degraded')
        self.assertEqual(self.config.token_expiry_quality, 'missing')
        # The token is stored encrypted, and the plaintext column is cleared.
        self.assertFalse(self.config.access_token)
        self.assertTrue(self.config.access_token_enc)
        self.assertNotIn('tok', self.config.access_token_enc)
        self.assertEqual(self.config._voip_secret_read('access_token'), 'tok')

    def test_06_a_valid_token_enables_no_capability(self):
        self.config._store_token('tok', expires_at=fields.Datetime.now(),
                                 expiry_quality='ok', longlive=False)
        for flag in ('history_sync_verified', 'rest_originate_verified',
                     'extension_sync_verified', 'webrtc_enabled',
                     'outbound_enabled'):
            self.assertFalse(self.config[flag],
                             '%s must not be switched on by a token' % flag)


@tagged('post_install', '-at_install')
class TestFeedAParsing(VoipCommon):
    """W01 — the completed-call payload, mapped exactly."""

    def test_10_deterministic_fixture(self):
        normalised = normalise_final_record(self.config, FIXTURE_CDR)
        data = normalised['data']
        self.assertEqual(normalised['canonical_type'], 'final_cdr')
        self.assertIsNone(normalised['quarantine_reason'])
        self.assertEqual(data['call_date'], datetime(2026, 9, 17, 2, 0, 0))
        self.assertEqual(data['direction'], 'outgoing')
        self.assertEqual(data['external_peer']['key'], '0912345678')
        self.assertEqual(data['external_peer']['e164'], '+84912345678')
        self.assertEqual(data['internal_extension'], '531')
        self.assertEqual(data['duration'], 20)
        self.assertEqual(data['billsec'], 0)
        self.assertEqual(data['wait_seconds'], 20)
        self.assertEqual(data['call_type'], 'missed')
        self.assertEqual(data['call_status'], 'no_answer')
        self.assertEqual(data['outcome'], 'no_answer')

    def test_11_every_documented_disposition_maps(self):
        expected = {
            'ANSWERED': ('answered', 'answered', 'completed'),
            'NO ANSWER': ('no_answer', 'missed', 'no_answer'),
            'MISSED': ('no_answer', 'missed', 'no_answer'),
            'BUSY': ('busy', 'busy', 'busy'),
            'FAILED': ('failed', 'failed', 'failed'),
        }
        for disposition, (outcome, call_type, status) in expected.items():
            data = dict(FIXTURE_CDR, disposition=disposition, status=disposition,
                        id='cdr-%s' % disposition)
            parsed = normalise_final_record(self.config, data)['data']
            self.assertEqual(parsed['outcome'], outcome, disposition)
            self.assertEqual(parsed['call_type'], call_type, disposition)
            self.assertEqual(parsed['call_status'], status, disposition)

    def test_12_an_unknown_disposition_is_unknown_not_answered(self):
        data = dict(FIXTURE_CDR, disposition='TELEPORTED', status='TELEPORTED')
        parsed = normalise_final_record(self.config, data)['data']
        self.assertEqual(parsed['outcome'], 'unknown')
        self.assertEqual(parsed['call_type'], 'unknown')
        self.assertEqual(parsed['call_status'], 'unknown')
        self.assertTrue(any('TELEPORTED' in q for q in parsed['data_quality']))

    def test_13_status_and_disposition_disagreeing_is_flagged(self):
        data = dict(FIXTURE_CDR, disposition='ANSWERED', status='BUSY')
        parsed = normalise_final_record(self.config, data)['data']
        # `disposition` wins inside this profile; the conflict is recorded.
        self.assertEqual(parsed['outcome'], 'answered')
        self.assertTrue(any('disagree' in q for q in parsed['data_quality']))

    def test_14_zero_and_unknown_are_different(self):
        answered = normalise_final_record(
            self.config, dict(FIXTURE_CDR, billsec='0'))['data']
        self.assertEqual(answered['billsec'], 0)
        missing = normalise_final_record(
            self.config, dict(FIXTURE_CDR, billsec=''))['data']
        self.assertIsNone(missing['billsec'])
        # And a derived wait needs BOTH to be valid.
        self.assertIsNone(missing['wait_seconds'])

    def test_15_negative_and_absurd_durations_are_refused(self):
        parsed = normalise_final_record(
            self.config, dict(FIXTURE_CDR, duration='-5', billsec='99999999'))['data']
        self.assertIsNone(parsed['duration'])
        self.assertIsNone(parsed['billsec'])

    def test_16_a_bad_call_date_quarantines_rather_than_using_now(self):
        normalised = normalise_final_record(
            self.config, dict(FIXTURE_CDR, calldate='soon'))
        self.assertEqual(normalised['quarantine_reason'], 'bad_call_date')
        self.assertIsNone(normalised['data']['call_date'])

    def test_17_an_unknown_type_quarantines(self):
        normalised = normalise_final_record(
            self.config, dict(FIXTURE_CDR, type='sideways'))
        self.assertEqual(normalised['quarantine_reason'], 'unknown_direction')

    def test_18_recording_links_are_kept_apart_and_out_of_the_fingerprint(self):
        base = dict(FIXTURE_CDR,
                    play='https://customer.voip24h.vn/fdownload/play?x=1',
                    download='https://customer.voip24h.vn/fdownload/downloadFile?x=1',
                    recording='https://customer.voip24h.vn/fdownload/recording?x=1')
        first = normalise_final_record(self.config, base)
        urls = first['data']['recording_urls']
        self.assertEqual(set(urls), {'play', 'download', 'recording'})
        # A re-signed link is not a second call.
        resigned = dict(base, play='https://customer.voip24h.vn/fdownload/play?x=2')
        second = normalise_final_record(self.config, resigned)
        self.assertEqual(first['fingerprint'], second['fingerprint'])

    def test_18b_datetimes_survive_the_round_trip_to_the_inbox(self):
        # JSON has no datetime. Writing them with `default=str` and reading
        # them back as strings is the quiet version of this bug: it only
        # fires on the branch that does arithmetic with them.
        normalised = normalise_final_record(self.config, FIXTURE_CDR)
        reloaded = load_normalised(dump_normalised(normalised))
        self.assertIsInstance(reloaded['data']['call_date'], datetime)
        self.assertEqual(reloaded['data']['call_date'],
                         normalised['data']['call_date'])
        self.assertIsInstance(reloaded['provider_time'], datetime)

    def test_19_redaction_removes_tokens_and_link_query_strings(self):
        redacted = redact({
            'auth': 'super-secret',
            'download': 'https://customer.voip24h.vn/fdownload/x?pkeyID=abc&xKey=0',
            'src': '531',
        })
        self.assertEqual(redacted['auth'], '***')
        self.assertNotIn('pkeyID', redacted['download'])
        self.assertIn('customer.voip24h.vn', redacted['download'])
        self.assertEqual(redacted['src'], '531')


@tagged('post_install', '-at_install')
class TestFeedBParsing(VoipCommon):
    """W02 — live states and the nested record."""

    def test_20_state_tokens_map_case_insensitively(self):
        for raw, canonical in (('Ring', 'ringing'), ('ring', 'ringing'),
                               ('Up', 'answered'), ('Hangup', 'ended_pending_cdr'),
                               ('Cdr', 'final_cdr'), ('cdr', 'final_cdr')):
            parsed = normalise_state_event(self.config, {
                'uniqueid': '1726107765.130271', 'state': raw,
                'type': 'outbound', 'extend': '531'})
            self.assertEqual(parsed['data']['state'], canonical, raw)
            self.assertEqual(parsed['raw_state_token'], raw)

    def test_21_an_unknown_state_quarantines(self):
        parsed = normalise_state_event(self.config, {
            'uniqueid': 'x', 'state': 'Levitating', 'type': 'outbound'})
        self.assertEqual(parsed['quarantine_reason'], 'unknown_state')
        self.assertEqual(parsed['data']['state'], 'unknown')

    def test_22_nested_cdr_parses_as_json(self):
        parsed = normalise_state_event(self.config, {
            'uniqueid': '1726107765.130271',
            'linkedid': '1726107765.130271',
            'channel': 'SIP/531-0000434a',
            'extend': '531',
            'state': 'Cdr',
            'type': 'outbound',
            'phone': '0919840943',
            'cdr': json.dumps({
                'source': '916635328',
                'destination': '0919840943',
                'starttime': '2024-09-12 09:25:50',
                'answertime': '2024-09-12 09:25:58',
                'endtime': '2024-09-12 09:28:00',
                'duration': '129',
                'billsec': '121',
                'disposition': 'ANSWERED',
            }),
        })
        cdr = parsed['data']['cdr']
        self.assertEqual(cdr['outcome'], 'answered')
        self.assertEqual(cdr['billsec'], 121)
        self.assertEqual(cdr['start_time'], datetime(2024, 9, 12, 2, 25, 50))
        # The vendor's sample is off by exactly one second in both pairs
        # (130 measured vs 129 stated; 122 vs 121). That is inclusive/
        # exclusive rounding, not a contradiction — flagging it would make
        # the data-quality flag fire on every call and be ignored.
        self.assertFalse(any('measured' in q
                             for q in parsed['data']['data_quality']))

    def test_22b_a_real_duration_contradiction_is_flagged(self):
        parsed = normalise_state_event(self.config, {
            'uniqueid': 'contradiction', 'state': 'Cdr', 'type': 'outbound',
            'cdr': json.dumps({
                'source': '531', 'destination': '0912345678',
                'starttime': '2024-09-12 09:25:50',
                'answertime': '2024-09-12 09:25:58',
                'endtime': '2024-09-12 09:28:00',
                'duration': '9', 'billsec': '5', 'disposition': 'ANSWERED',
            }),
        })
        quality = parsed['data']['data_quality']
        self.assertTrue(any('duration' in q for q in quality), quality)
        self.assertTrue(any('talk time' in q for q in quality), quality)
        # Both numbers survive. Neither is rewritten from the other.
        self.assertEqual(parsed['data']['cdr']['duration'], 9)
        self.assertEqual(parsed['data']['cdr']['billsec'], 5)

    def test_23_nested_cdr_parses_as_a_plain_key_value_block(self):
        parsed = normalise_state_event(self.config, {
            'uniqueid': 'x', 'state': 'Cdr', 'type': 'inbound',
            'cdr': ('source: 0912345678 destination: 531 '
                    'starttime: 2026-09-17 09:00:00 billsec: 30 '
                    'duration: 35 disposition: ANSWERED'),
        })
        self.assertEqual(parsed['data']['cdr']['billsec'], 30)
        self.assertEqual(parsed['data']['cdr']['outcome'], 'answered')

    def test_24_an_unreadable_nested_cdr_quarantines_the_final_state(self):
        parsed = normalise_state_event(self.config, {
            'uniqueid': 'x', 'state': 'Cdr', 'type': 'inbound',
            'cdr': '<<garbage>>'})
        self.assertEqual(parsed['quarantine_reason'], 'cdr_unreadable')


@tagged('post_install', '-at_install')
class TestNumbers(VoipCommon):
    """C01 — three representations, kept apart."""

    def test_30_vietnamese_forms_agree(self):
        for raw in ('0912345678', '+84912345678', '84912345678',
                    '0912 345 678'):
            peer = phone_ident.normalise_peer(raw)
            self.assertEqual(peer['key'], '0912345678', raw)
            self.assertEqual(peer['e164'], '+84912345678', raw)
            self.assertFalse(peer['is_extension'], raw)

    def test_31_an_extension_stays_an_extension(self):
        peer = phone_ident.normalise_peer('531')
        self.assertTrue(peer['is_extension'])
        self.assertIsNone(peer['key'])
        self.assertIsNone(peer['e164'])
        self.assertEqual(phone_ident.dial_string('531'), '531')

    def test_32_a_withheld_caller_is_anonymous_not_a_number(self):
        for raw in ('', 'anonymous', 'unknown', 'Restricted'):
            peer = phone_ident.normalise_peer(raw)
            self.assertTrue(peer['is_anonymous'], raw)
            self.assertIsNone(phone_ident.dial_string(raw), raw)

    def test_33_an_international_number_is_not_forced_through_the_vn_helper(self):
        peer = phone_ident.normalise_peer('+6591234567')
        self.assertIsNone(peer['key'])
        self.assertEqual(peer['e164'], '+6591234567')

    def test_34_direction_decides_which_side_is_the_customer(self):
        inbound = phone_ident.resolve_parties('0912345678', '531', 'incoming')
        self.assertEqual(inbound['peer']['key'], '0912345678')
        self.assertEqual(inbound['internal_extension'], '531')
        outbound = phone_ident.resolve_parties('531', '0912345678', 'outgoing')
        self.assertEqual(outbound['peer']['key'], '0912345678')
        internal = phone_ident.resolve_parties('531', '532', 'internal')
        self.assertTrue(internal['peer']['is_anonymous'])


@tagged('post_install', '-at_install')
class TestIngestAndReduce(VoipCommon):
    """W03/W04/W05/W10 — the inbox and the state machine."""

    def test_40_a_duplicate_delivery_is_one_event_and_one_call(self):
        first, created_first = self._ingest_cdr(FIXTURE_CDR)
        self.assertTrue(created_first)
        second, created_second = self._ingest_cdr(FIXTURE_CDR)
        self.assertFalse(created_second)
        self.assertEqual(first, second)

        self._reduce(first)
        self.assertEqual(self.env['voip.call.session'].search_count(
            [('voip_config_id', '=', self.config.id)]), 1)
        # Replaying the SAME event produces no second call and no second log.
        self._reduce(first)
        self.assertEqual(self.env['voip.call.session'].search_count(
            [('voip_config_id', '=', self.config.id)]), 1)
        self.assertEqual(self.env['voip.call.log'].search_count(
            [('voip_config_id', '=', self.config.id)]), 1)

    def test_41_url_encoded_equivalents_do_not_create_a_second_call(self):
        first, _ = self._ingest_cdr(FIXTURE_CDR)
        self._reduce(first)
        # The receiver URL-decodes once; the same values arrive as the same
        # strings, so the fingerprint must match.
        again, created = self._ingest_cdr(dict(FIXTURE_CDR))
        self.assertFalse(created)
        self.assertEqual(first, again)

    def test_42_the_same_ids_under_another_config_stay_separate(self):
        other = self.env['voip.config'].create({
            'name': 'Second clinic',
            'account_id': 'ACC-TEST-002',
            'company_id': self.env.company.id,
            'cdr_ingest_enabled': True,
        })
        other._ensure_receiver()
        mine, _ = self._ingest_cdr(FIXTURE_CDR)
        theirs, created = self._ingest_cdr(FIXTURE_CDR, config=other)
        self.assertTrue(created)
        self.assertNotEqual(mine, theirs)
        self._reduce(mine)
        self._reduce(theirs)
        self.assertEqual(self.env['voip.call.session'].search_count(
            [('voip_config_id', '=', self.config.id)]), 1)
        self.assertEqual(self.env['voip.call.session'].search_count(
            [('voip_config_id', '=', other.id)]), 1)

    def test_43_up_before_ring_does_not_invent_a_ringing_time(self):
        up, _ = self._ingest_state({
            'uniqueid': 'leg-1', 'linkedid': 'call-1', 'state': 'Up',
            'type': 'inbound', 'extend': '531', 'phone': '0912345678'})
        result = self._reduce(up)
        leg = result['leg']
        self.assertEqual(leg.state, 'answered')
        self.assertFalse(leg.ringing_at)
        self.assertTrue(leg.answered_at)

        # A LATE Ring cannot walk the leg backwards.
        ring, _ = self._ingest_state({
            'uniqueid': 'leg-1', 'linkedid': 'call-1', 'state': 'Ring',
            'type': 'inbound', 'extend': '531', 'phone': '0912345678'})
        self._reduce(ring)
        self.assertEqual(leg.state, 'answered')

    def test_44_hangup_ends_its_own_leg_only(self):
        for leg_id in ('leg-a', 'leg-b'):
            ring, _ = self._ingest_state({
                'uniqueid': leg_id, 'linkedid': 'call-2', 'state': 'Ring',
                'type': 'inbound', 'extend': '531', 'phone': '0912345678'})
            self._reduce(ring)
        session = self.env['voip.call.session'].search(
            [('voip_config_id', '=', self.config.id)], limit=1)
        self.assertEqual(len(session.leg_ids), 2)

        hangup, _ = self._ingest_state({
            'uniqueid': 'leg-a', 'linkedid': 'call-2', 'state': 'Hangup',
            'type': 'inbound', 'extend': '531', 'phone': self.peer})
        self._reduce(hangup)
        # One leg ended; the interaction is still open because the other is up.
        self.assertEqual(session.live_state, 'ringing')

        hangup_b, _ = self._ingest_state({
            'uniqueid': 'leg-b', 'linkedid': 'call-2', 'state': 'Hangup',
            'type': 'inbound', 'extend': '531', 'phone': '0912345678'})
        self._reduce(hangup_b)
        self.assertEqual(session.live_state, 'ended_pending_cdr')

    def test_45_a_ring_group_loser_does_not_create_a_missed_interaction(self):
        answered = dict(FIXTURE_CDR, id='cdr-win', callid='ring-group',
                        type='inbound', src='0912345678', dst='531',
                        disposition='ANSWERED', status='ANSWERED',
                        billsec='42', duration='50')
        lost = dict(answered, id='cdr-lose', disposition='NO ANSWER',
                    status='NO ANSWER', billsec='0', duration='8')
        first, _ = self._ingest_cdr(lost)
        self._reduce(first)
        session = self.env['voip.call.session'].search(
            [('voip_config_id', '=', self.config.id)], limit=1)
        self.assertEqual(session.callback_state, 'due')

        second, _ = self._ingest_cdr(answered)
        self._reduce(second)
        # Both final records are kept — they are evidence — but the aggregate
        # says the customer was reached and nobody owes them a ring back.
        self.assertEqual(len(session.log_ids), 2)
        self.assertEqual(session.outcome, 'answered')
        self.assertEqual(session.callback_state, 'none')

    def test_46_a_final_record_is_enriched_not_duplicated(self):
        first, _ = self._ingest_cdr(FIXTURE_CDR)
        self._reduce(first)
        correction = dict(FIXTURE_CDR, disposition='ANSWERED',
                          status='ANSWERED', billsec='30', duration='35')
        second, created = self._ingest_cdr(correction)
        self.assertTrue(created, 'different content is a different message')
        self._reduce(second)
        logs = self.env['voip.call.log'].search(
            [('voip_config_id', '=', self.config.id)])
        self.assertEqual(len(logs), 1, 'the same provider record id is one row')
        self.assertEqual(logs.call_type, 'answered')
        self.assertEqual(logs.talk_duration_seconds, 30)

    def test_47_a_correction_does_not_erase_staff_work(self):
        first, _ = self._ingest_cdr(FIXTURE_CDR)
        self._reduce(first)
        log = self.env['voip.call.log'].search(
            [('voip_config_id', '=', self.config.id)], limit=1)
        log.write({'call_notes': 'Left a voicemail', 'state': 'reviewed',
                   'call_outcome': 'follow_up_required'})
        correction = dict(FIXTURE_CDR, disposition='ANSWERED',
                          status='ANSWERED', billsec='30', duration='35')
        second, _ = self._ingest_cdr(correction)
        self._reduce(second)
        self.assertEqual(log.call_notes, 'Left a voicemail')
        self.assertEqual(log.state, 'reviewed')
        self.assertEqual(log.call_outcome, 'follow_up_required')

    def test_48_a_switched_off_feed_changes_no_business_record(self):
        self.config.cdr_ingest_enabled = False
        event, _ = self._ingest_cdr(FIXTURE_CDR)
        result = self._reduce(event)
        self.assertTrue(result.get('ignored'))
        self.assertEqual(event.processing_state, 'quarantined')
        self.assertEqual(self.env['voip.call.session'].search_count(
            [('voip_config_id', '=', self.config.id)]), 0)
        self.assertFalse(self.config.ready_cdr_at)

    def test_49_a_quarantined_message_is_kept_whole_and_projects_nothing(self):
        event, _ = self._ingest_cdr(dict(FIXTURE_CDR, calldate='soon'))
        self.assertEqual(event.processing_state, 'quarantined')
        self.assertEqual(event.error_code, 'bad_call_date')
        self.assertTrue(event.payload_redacted)
        summary = drain_events(self.env, config=self.config)
        self.assertEqual(summary['total'], 0, 'quarantined rows are not claimed')

    def test_50_an_unknown_state_with_no_session_quarantines(self):
        event, _ = self._ingest_state({
            'uniqueid': 'orphan', 'state': 'Levitating', 'type': 'inbound'})
        # The normaliser already quarantined it, so the reducer never runs.
        self.assertEqual(event.processing_state, 'quarantined')
        # And even if it did, it refuses.
        event.processing_state = 'pending'
        with self.assertRaises(ReduceQuarantine):
            self._reduce(event)


@tagged('post_install', '-at_install')
class TestMatchingAndCallbacks(VoipCommon):
    """C02/C03/C04 — who the caller is and who owes them a ring back."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Fixture requirement (conventions §6): a patient partner needs a
        # catchment province. Reuse a seeded one where the database has one —
        # a fresh install may not.
        cls.partner_vals = {'phone': cls.peer}
        if 'catchment_province_id' in cls.env['res.partner']._fields:
            Province = cls.env['health.catchment.province']
            province = Province.search([], limit=1) or Province.create(
                {'name': 'VoIP Test Province'})
            cls.partner_vals['catchment_province_id'] = province.id

    def _inbound(self, **overrides):
        data = dict(FIXTURE_CDR, type='inbound', src=self.peer, dst='531',
                    disposition='NO ANSWER', status='NO ANSWER',
                    billsec='0', duration='12')
        data.update(overrides)
        event, _ = self._ingest_cdr(data)
        self._reduce(event)
        return self.env['voip.call.session'].search(
            [('voip_config_id', '=', self.config.id)],
            order='id desc', limit=1)

    def test_60_one_matching_contact_links_automatically(self):
        partner = self.env['res.partner'].create(
            dict(self.partner_vals, name='Single Match'))
        session = self._inbound()
        self.assertEqual(session.partner_id, partner)
        self.assertEqual(session.match_state, 'auto')

    def test_61_a_family_sharing_a_number_is_ambiguous_not_a_guess(self):
        self.env['res.partner'].create(dict(self.partner_vals, name='Mother'))
        self.env['res.partner'].create(dict(self.partner_vals, name='Child'))
        session = self._inbound()
        self.assertFalse(session.partner_id)
        self.assertEqual(session.match_state, 'ambiguous')
        self.assertGreaterEqual(session.match_candidate_count, 2)

    def test_62_an_unanswered_inbound_call_owes_a_ring_back(self):
        session = self._inbound()
        self.assertEqual(session.callback_state, 'due')

    def test_63_an_unsuccessful_outbound_attempt_leaves_it_owed(self):
        inbound = self._inbound(id='cdr-in-1', callid='in-1')
        self.assertEqual(inbound.callback_state, 'due')
        for index, disposition in enumerate(('BUSY', 'NO ANSWER', 'FAILED')):
            attempt, _ = self._ingest_cdr(dict(
                FIXTURE_CDR, id='cdr-out-%s' % index, dst=self.peer,
                callid='out-%s' % index, disposition=disposition,
                status=disposition, billsec='0', duration='9'))
            self._reduce(attempt)
        self.assertEqual(inbound.callback_state, 'due')
        self.assertEqual(inbound.callback_attempts, 3)

    def test_64_an_answered_outbound_call_with_talk_time_resolves_it(self):
        inbound = self._inbound(id='cdr-in-2', callid='in-2')
        success, _ = self._ingest_cdr(dict(
            FIXTURE_CDR, id='cdr-out-ok', callid='out-ok', dst=self.peer,
            disposition='ANSWERED', status='ANSWERED',
            billsec='45', duration='52'))
        self._reduce(success)
        self.assertEqual(inbound.callback_state, 'resolved')
        self.assertEqual(inbound.callback_resolution, 'answered')

    def test_65_answered_with_zero_talk_time_needs_a_person(self):
        inbound = self._inbound(id='cdr-in-3', callid='in-3')
        rounding, _ = self._ingest_cdr(dict(
            FIXTURE_CDR, id='cdr-out-zero', callid='out-zero', dst=self.peer,
            disposition='ANSWERED', status='ANSWERED',
            billsec='0', duration='4'))
        self._reduce(rounding)
        self.assertEqual(inbound.callback_state, 'due',
                         'provider rounding is not proof of a conversation')
        self.assertEqual(inbound.callback_attempts, 1)

    def test_66_an_internal_call_never_creates_a_patient_obligation(self):
        event, _ = self._ingest_cdr(dict(
            FIXTURE_CDR, id='cdr-internal', callid='internal-1',
            type='local', src='531', dst='532',
            disposition='NO ANSWER', status='NO ANSWER'))
        self._reduce(event)
        session = self.env['voip.call.session'].search(
            [('voip_config_id', '=', self.config.id)], order='id desc', limit=1)
        self.assertEqual(session.direction, 'internal')
        self.assertEqual(session.callback_state, 'none')
        self.assertEqual(session.match_state, 'internal')

    def test_67_a_late_record_cannot_reopen_a_resolved_obligation(self):
        inbound = self._inbound(id='cdr-in-4', callid='in-4')
        inbound.with_context(voip_reducer=True)._resolve_callback('manual')
        self.assertEqual(inbound.callback_state, 'resolved')
        # A late duplicate of the ORIGINAL missed call arrives.
        late, _ = self._ingest_cdr(dict(
            FIXTURE_CDR, id='cdr-in-4', callid='in-4', type='inbound',
            src=self.peer, dst='531', disposition='MISSED',
            status='MISSED', billsec='0', duration='13'))
        self._reduce(late)
        self.assertEqual(inbound.callback_state, 'resolved')

    def test_68_a_withheld_caller_still_lands_in_the_queue(self):
        session = self._inbound(id='cdr-anon', callid='anon-1',
                                src='anonymous')
        self.assertTrue(session.is_anonymous)
        self.assertEqual(session.callback_state, 'due')
        self.assertFalse(session.partner_id)


@tagged('post_install', '-at_install')
class TestEffectsAndNotifications(VoipCommon):
    """N01 — the right people, and nobody else."""

    def test_70_one_effect_per_recipient_per_version(self):
        user = self.env['res.users'].create({
            'name': 'Agent Smith', 'login': 'voip-agent-smith',
            'group_ids': [(4, self.env.ref('health_voip24h.group_voip_user').id)],
        })
        self.extension.user_id = user
        event, _ = self._ingest_cdr(dict(
            FIXTURE_CDR, type='inbound', src=self.peer, dst='531'))
        self._reduce(event)
        session = self.env['voip.call.session'].search(
            [('voip_config_id', '=', self.config.id)], limit=1)
        effects = self.env['voip.call.effect'].search([
            ('session_id', '=', session.id), ('effect_type', '=', 'notify')])
        self.assertEqual(len(effects), 1)
        self.assertEqual(effects.recipient_uid, user.id)

        # Re-enqueueing the same business event is a no-op.
        self.env['voip.call.effect']._enqueue(
            session, 'notify', dedupe_key=effects.dedupe_key,
            recipient_uid=user.id)
        self.assertEqual(self.env['voip.call.effect'].search_count([
            ('session_id', '=', session.id), ('effect_type', '=', 'notify')]), 1)

    def test_71_effects_are_delivered_after_the_fact_is_written(self):
        event, _ = self._ingest_cdr(dict(
            FIXTURE_CDR, type='inbound', src=self.peer, dst='531'))
        self._reduce(event)
        summary = drain_effects(self.env)
        self.assertGreaterEqual(summary['total'], 1)
        self.assertEqual(summary['retried'], 0)

    def test_72_one_callback_task_per_obligation(self):
        partner = self.env['res.partner'].create({
            'name': 'Task Owner', 'phone': self.peer})
        event, _ = self._ingest_cdr(dict(
            FIXTURE_CDR, type='inbound', src=self.peer, dst='531'))
        self._reduce(event)
        drain_effects(self.env)
        session = self.env['voip.call.session'].search(
            [('voip_config_id', '=', self.config.id)], limit=1)
        self.assertEqual(session.partner_id, partner)
        self.assertTrue(session.activity_id)
        # A second drain does not create a second task.
        first_activity = session.activity_id
        drain_effects(self.env)
        self.assertEqual(session.activity_id, first_activity)


@tagged('post_install', '-at_install')
class TestGuards(VoipCommon):
    """S01/P01/P02/R02 — what a crafted request cannot do."""

    def test_80_provider_facts_refuse_a_normal_write(self):
        event, _ = self._ingest_cdr(FIXTURE_CDR)
        self._reduce(event)
        log = self.env['voip.call.log'].search(
            [('voip_config_id', '=', self.config.id)], limit=1)
        with self.assertRaises(UserError):
            log.write({'call_type': 'answered'})
        with self.assertRaises(UserError):
            log.write({'duration_seconds': 9999})
        # Staff work is still writable.
        log.write({'call_notes': 'fine'})
        self.assertEqual(log.call_notes, 'fine')

    def test_81_session_provider_facts_refuse_a_normal_write(self):
        event, _ = self._ingest_cdr(FIXTURE_CDR)
        self._reduce(event)
        session = self.env['voip.call.session'].search(
            [('voip_config_id', '=', self.config.id)], limit=1)
        with self.assertRaises(UserError):
            session.write({'outcome': 'answered'})
        with self.assertRaises(UserError):
            session.write({'talk_seconds': 600})

    def test_82_a_version_mismatch_refuses_a_stale_write_up(self):
        event, _ = self._ingest_cdr(FIXTURE_CDR)
        self._reduce(event)
        session = self.env['voip.call.session'].search(
            [('voip_config_id', '=', self.config.id)], limit=1)
        with self.assertRaises(UserError):
            session.update_disposition(notes='stale',
                                       version=session.projection_version - 1)

    def test_83_a_sip_password_can_be_set_but_never_read_back(self):
        self.extension.sip_password_input = 'a-real-password'
        # The inverse runs at flush, not at assignment.
        self.env.flush_all()
        stored = self.extension.sudo().sip_password_enc
        self.assertTrue(stored)
        self.assertNotIn('a-real-password', stored)
        self.extension.invalidate_recordset()
        self.assertFalse(self.extension.sip_password_input,
                         'a stored secret is never handed back on a read')
        self.assertTrue(self.extension.sip_password_set)
        # The only reader is the bootstrap helper.
        self.extension.write({'sip_host': 'sip.example.test',
                              'sip_username': '531'})
        self.assertEqual(self.extension._sip_credentials()['sip_password'],
                         'a-real-password')

    def test_84_one_owning_browser_per_extension(self):
        Lease = self.env['voip.client.lease']
        lease, token = Lease._acquire(self.config, self.extension, 'browser-1')
        self.assertTrue(token)
        # The same browser re-acquiring is fine; a different one is refused.
        same, _ = Lease._acquire(self.config, self.extension, 'browser-1')
        self.assertEqual(same, lease)
        other_user = self.env['res.users'].create({
            'name': 'Other', 'login': 'voip-other-browser'})
        with self.assertRaises(UserError):
            Lease.with_user(other_user)._acquire(
                self.config, self.extension, 'browser-2')

    def test_85_a_replaced_lease_is_refused(self):
        Lease = self.env['voip.client.lease']
        lease, token = Lease._acquire(self.config, self.extension, 'browser-1')
        self.assertTrue(Lease._authenticate(lease.id, token, lease.fence))
        self.assertFalse(Lease._authenticate(lease.id, 'wrong', lease.fence))
        self.assertFalse(Lease._authenticate(lease.id, token, lease.fence + 1))
        lease._release('test')
        self.assertFalse(Lease._authenticate(lease.id, token, lease.fence))

    def test_86_a_dial_request_is_idempotent(self):
        Action = self.env['voip.call.action']
        first, created_first = Action._record(
            self.config, 'dial', uuid_value='abc-123',
            extension=self.extension, destination='0912345678')
        second, created_second = Action._record(
            self.config, 'dial', uuid_value='abc-123',
            extension=self.extension, destination='0912345678')
        self.assertTrue(created_first)
        self.assertFalse(created_second)
        self.assertEqual(first, second)

    def test_87_destination_policy_refuses_what_it_should(self):
        allowed, _reason = self.extension._destination_allowed('0912345678')
        self.assertTrue(allowed)
        allowed, reason = self.extension._destination_allowed('+6591234567')
        self.assertFalse(allowed, reason)
        self.extension.destination_allowlist = '09'
        allowed, _ = self.extension._destination_allowed('0812345678')
        self.assertFalse(allowed)
        allowed, _ = self.extension._destination_allowed('0912345678')
        self.assertTrue(allowed)

    def test_88_transfer_is_unavailable_until_it_is_switched_on(self):
        allowed, reason = self.extension._transfer_target_allowed('532')
        self.assertFalse(allowed, reason)
        self.extension.allow_transfer = True
        allowed, reason = self.extension._transfer_target_allowed('0912345678')
        self.assertFalse(allowed, 'external targets are not approved yet')
        self.env['voip.extension'].create({
            'name': 'Nurses', 'extension_number': '532',
            'voip_config_id': self.config.id})
        allowed, _ = self.extension._transfer_target_allowed('532')
        self.assertTrue(allowed)

    def test_89_recording_urls_are_validated_against_ssrf(self):
        from ..services.recording_fetch import RecordingFetchError, _check_url
        allowed = {'customer.voip24h.vn'}
        with self.assertRaises(RecordingFetchError):
            _check_url('http://customer.voip24h.vn/x', allowed)
        with self.assertRaises(RecordingFetchError):
            _check_url('https://evil.example/x', allowed)
        with self.assertRaises(RecordingFetchError):
            _check_url('https://127.0.0.1/x', allowed)
        # The vendor's own links embed `hostname=192.168.2.51` as a query
        # VALUE. Query text is not a network target and must not be treated
        # as one.
        with self.assertRaises(RecordingFetchError):
            _check_url('https://evil.example/f?hostname=192.168.2.51', allowed)

    def test_90_a_callback_token_is_checked_in_constant_time_and_rotates(self):
        Config = self.env['voip.config']
        token = self.config._voip_secret_read('cdr_token')
        self.assertTrue(token)
        self.assertTrue(Config._resolve_receiver(
            self.config.receiver_id, 'cdr', token))
        self.assertFalse(Config._resolve_receiver(
            self.config.receiver_id, 'cdr', token + 'x'))
        # A state token is not a CDR token.
        state_token = self.config._voip_secret_read('state_token')
        self.assertFalse(Config._resolve_receiver(
            self.config.receiver_id, 'cdr', state_token))
        # Rotation keeps the old one alive for the overlap window.
        self.config.action_rotate_receiver_tokens()
        new_token = self.config._voip_secret_read('cdr_token')
        self.assertNotEqual(token, new_token)
        self.assertTrue(Config._resolve_receiver(
            self.config.receiver_id, 'cdr', new_token))
        self.assertTrue(Config._resolve_receiver(
            self.config.receiver_id, 'cdr', token),
            'the previous address must keep working during the overlap')
        self.config.token_rotation_grace_until = \
            fields.Datetime.now() - timedelta(hours=1)
        self.assertFalse(Config._resolve_receiver(
            self.config.receiver_id, 'cdr', token))

    def test_91_unverified_provider_endpoints_refuse(self):
        self.config.write({'api_key': 'k', 'api_secret': 's'})
        api = self.config._get_api_client()
        for call in (api.get_call_history, api.get_extensions):
            with self.assertRaises(UserError):
                call()
        with self.assertRaises(UserError):
            api.initiate_call('531', '0912345678')

    def test_92_an_api_base_url_off_the_allowlist_is_refused(self):
        self.config.write({'api_key': 'k', 'api_secret': 's',
                           'api_base_url': 'https://evil.example/v3'})
        with self.assertRaises(UserError):
            self.config._get_api_client()

    def test_93_recording_playback_needs_its_own_permission(self):
        event, _ = self._ingest_cdr(dict(
            FIXTURE_CDR,
            download='https://customer.voip24h.vn/fdownload/downloadFile?x=1'))
        self._reduce(event)
        recording = self.env['voip.call.recording'].search(
            [('call_log_id.voip_config_id', '=', self.config.id)], limit=1)
        self.assertTrue(recording)
        self.assertEqual(recording.state, 'advertised')
        self.assertFalse(recording.mimetype,
                         'the media type is observed, never assumed')
        user = self.env['res.users'].create({
            'name': 'No Recordings', 'login': 'voip-no-recordings',
            'group_ids': [(4, self.env.ref('health_voip24h.group_voip_user').id)],
        })
        with self.assertRaises(AccessError):
            recording.with_user(user)._check_playback_access()


@tagged('post_install', '-at_install')
class TestFinalisation(VoipCommon):
    """A call with no ending is an admission, not a disposition."""

    def test_100_a_call_with_no_final_record_becomes_unconfirmed(self):
        from ..services.event_reducer import finalise_stale_sessions
        hangup, _ = self._ingest_state({
            'uniqueid': 'stale-leg', 'linkedid': 'stale', 'state': 'Hangup',
            'type': 'inbound', 'extend': '531', 'phone': self.peer})
        self._reduce(hangup)
        session = self.env['voip.call.session'].search(
            [('voip_config_id', '=', self.config.id)], limit=1)
        session.with_context(voip_reducer=True).write({
            'ended_at': fields.Datetime.now() - timedelta(minutes=10)})
        self.assertEqual(finalise_stale_sessions(self.env, self.config), 1)
        self.assertEqual(session.live_state, 'stale_unconfirmed')
        self.assertEqual(session.outcome, 'unknown')
        self.assertEqual(session.data_quality_state, 'incomplete')
        self.assertNotEqual(session.outcome, 'answered')


@tagged('post_install', '-at_install')
class TestLiveAuthContract(VoipCommon):
    """G01 — the shape the LIVE service really answers with.

    Captured from `https://api.voip24h.vn/v3/authentication` on 2026-09-17 and
    pinned here, because it differs from `Authorization.docx` in three places
    and the document's version made this module refuse a SUCCESSFUL login:

        document : status 1000, data.expried,  data.isLonglive
        live     : status  200, data.expired,  data.isLongLive

    An operator hit this with real credentials and got nothing but a screen
    message. Both shapes are accepted now; these tests fail if either is
    dropped.
    """

    def _auth_with(self, body):
        from ..services.voip24h_api import VoIP24hAPI
        self.config.sudo().write({'api_key': 'k', 'api_secret': 's'})

        def _fake(api_self, method, path, **kwargs):
            self.assertIn('authentication', path)
            return body

        with patch.object(VoIP24hAPI, '_request', _fake):
            return VoIP24hAPI(self.config.sudo()).authenticate()

    def test_110_the_live_success_shape_is_accepted(self):
        """status 200, `expired`, `isLongLive` — what they actually send."""
        self._auth_with({
            'message': 'Success', 'status': 200,
            'data': {'token': 'live-token',
                     'createAt': '2026-09-17 10:39:53',
                     'expired': '2026-09-18 10:39:53',
                     'isLongLive': False}})
        self.config.invalidate_recordset()
        self.assertEqual(self.config.state, 'connected',
                         'a live-shaped success must not read as a failure')
        self.assertEqual(self.config.token_expiry_quality, 'ok',
                         '`expired` must be read, not just `expried`')
        self.assertTrue(self.config.token_expires_at)

    def test_111_the_documented_success_shape_still_works(self):
        """status 1000, `expried`, `isLonglive` — what they published."""
        self._auth_with({
            'message': 'Success', 'status': 1000,
            'data': {'token': 'doc-token',
                     'createAt': '2026-09-17 10:39:53',
                     'expried': '2026-09-24 10:39:53',
                     'isLonglive': True}})
        self.config.invalidate_recordset()
        self.assertEqual(self.config.state, 'connected')
        self.assertEqual(self.config.token_expiry_quality, 'ok')
        self.assertTrue(self.config.token_longlive,
                        '`isLonglive` must still be read')

    def test_112_an_unknown_status_is_still_a_refusal(self):
        """Accepting two evidenced values is not accepting anything."""
        from ..services.voip24h_api import VoIP24hError
        raised = False
        try:
            self._auth_with({'message': 'Nope', 'status': 4321,
                             'data': {'token': 'x'}})
        except (VoIP24hError, UserError):
            raised = True
        self.assertTrue(raised)
        self.config.invalidate_recordset()
        self.assertEqual(self.config.state, 'error')
