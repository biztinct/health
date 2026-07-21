# -*- coding: utf-8 -*-

import hashlib
import hmac
import json
from datetime import datetime

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

from ..services.cdr_sync import (
    parse_call_data,
    parse_datetime,
    process_call_record,
)


@tagged('post_install', '-at_install')
class TestVoip24h(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.config = cls.env['voip.config'].create({
            'name': 'Test VoIP24h',
            'account_id': 'ACC-TEST-001',
            'company_id': cls.env.company.id,
        })
        cls.partner = cls.env['res.partner'].create({
            'name': 'VoIP Test Partner',
            'phone': '+84900000111',
        })

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    def test_parse_datetime_aware_to_naive_utc(self):
        # +07:00 wall clock must land as naive UTC (Odoo Datetime convention)
        dt = parse_datetime('2026-07-21T10:00:00+07:00')
        self.assertEqual(dt, datetime(2026, 7, 21, 3, 0, 0))
        self.assertIsNone(dt.tzinfo)

    def test_parse_datetime_z_suffix(self):
        dt = parse_datetime('2026-07-21T03:00:00Z')
        self.assertEqual(dt, datetime(2026, 7, 21, 3, 0, 0))
        self.assertIsNone(dt.tzinfo)

    def test_parse_datetime_garbage(self):
        self.assertFalse(parse_datetime('not-a-date'))
        self.assertFalse(parse_datetime(None))

    def test_parse_call_data_clamps_unknown_selections(self):
        vals = parse_call_data(self.config, {
            'call_id': 'CALL-1',
            'direction': 'weird-direction',
            'call_type': 'weird-type',
            'status': 'weird-status',
        })
        self.assertEqual(vals['direction'], 'incoming')
        self.assertEqual(vals['call_type'], 'answered')
        self.assertEqual(vals['call_status'], 'completed')
        # call_date is required — must be backfilled when the API omits it
        self.assertTrue(vals['call_date'])

    def test_normalize_phone(self):
        Log = self.env['voip.call.log']
        self.assertEqual(Log._normalize_phone('+84 (90) 000-0111'), '+84900000111')
        self.assertFalse(Log._normalize_phone(False))

    # ------------------------------------------------------------------
    # CDR processing
    # ------------------------------------------------------------------

    def _call_payload(self, call_id='CALL-100', **overrides):
        payload = {
            'call_id': call_id,
            'direction': 'incoming',
            'call_type': 'answered',
            'caller_number': '+84900000111',
            'called_number': '19001000',
            'call_date': '2026-07-20T09:00:00+07:00',
            'duration': 65,
            'talk_duration': 50,
            'status': 'completed',
        }
        payload.update(overrides)
        return payload

    def test_process_call_record_create_then_update(self):
        result = process_call_record(self.config, self._call_payload())
        self.assertEqual(result, 'created')

        log = self.env['voip.call.log'].search([
            ('call_id', '=', 'CALL-100'),
            ('voip_config_id', '=', self.config.id),
        ])
        self.assertEqual(len(log), 1)
        # auto-matched to the partner by exact phone
        self.assertEqual(log.partner_id, self.partner)
        self.assertTrue(log.auto_matched)
        # naive UTC conversion of the +07:00 call date
        self.assertEqual(log.call_date, datetime(2026, 7, 20, 2, 0, 0))

        # same call_id again → update, not duplicate
        result = process_call_record(self.config, self._call_payload(duration=99))
        self.assertEqual(result, 'updated')
        logs = self.env['voip.call.log'].search([
            ('call_id', '=', 'CALL-100'),
            ('voip_config_id', '=', self.config.id),
        ])
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs.duration_seconds, 99)

    def test_process_call_record_creates_recording_stub(self):
        process_call_record(self.config, self._call_payload(
            call_id='CALL-REC-1',
            has_recording=True,
            recording_url='https://recordings.example.com/rec1.mp3',
            recording_id='REC-1',
        ))
        log = self.env['voip.call.log'].search([('call_id', '=', 'CALL-REC-1')])
        self.assertEqual(len(log.recording_ids), 1)
        self.assertEqual(log.recording_ids.state, 'pending')

    def test_process_call_record_skip_recordings_flag(self):
        process_call_record(self.config, self._call_payload(
            call_id='CALL-REC-2',
            has_recording=True,
            recording_url='https://recordings.example.com/rec2.mp3',
        ), create_recordings=False)
        log = self.env['voip.call.log'].search([('call_id', '=', 'CALL-REC-2')])
        self.assertFalse(log.recording_ids)

    def test_auto_match_last9_fallback(self):
        # stored 0-prefixed local format, call arrives as +84
        partner = self.env['res.partner'].create({
            'name': 'Local Format Partner',
            'phone': '0900000222',
        })
        Log = self.env['voip.call.log']
        matched = Log.auto_match_contact_from_phone('+84900000222')
        self.assertEqual(matched, partner)

    def test_duration_display(self):
        log = self.env['voip.call.log'].create({
            'call_id': 'CALL-DUR',
            'voip_config_id': self.config.id,
            'direction': 'incoming',
            'call_type': 'answered',
            'call_date': '2026-07-20 02:00:00',
            'duration_seconds': 3725,
        })
        self.assertEqual(log.duration_display, '01:02:05')

    # ------------------------------------------------------------------
    # Config gates + credentials
    # ------------------------------------------------------------------

    def test_calling_gates(self):
        self.assertFalse(self.config.can_make_outgoing_calls())
        self.config.enable_call_functionality = True
        self.assertTrue(self.config.can_make_outgoing_calls())
        self.assertTrue(self.config.can_show_incoming_popups())
        self.config.enable_outgoing_calls = False
        self.assertFalse(self.config.can_make_outgoing_calls())

    def test_sync_without_credentials_raises(self):
        with self.assertRaises(UserError):
            self.config.action_sync_call_history()

    def test_initiate_call_disabled_raises(self):
        with self.assertRaises(UserError):
            self.config.initiate_user_call('+84900000111')

    def test_initiate_call_no_extension_raises(self):
        self.config.write({
            'enable_call_functionality': True,
            'enable_outgoing_calls': True,
        })
        with self.assertRaises(UserError):
            self.config.initiate_user_call('+84900000111')

    # ------------------------------------------------------------------
    # Webhook signature
    # ------------------------------------------------------------------

    def test_webhook_signature_no_secret_accepts(self):
        body = json.dumps({'event_type': 'call.started'}).encode()
        self.assertTrue(self.config._verify_webhook_signature(body, None))

    def test_webhook_signature_valid_and_invalid(self):
        self.config.sudo().webhook_secret = 'topsecret'
        body = json.dumps({'event_type': 'call.started'}).encode()
        good = hmac.new(b'topsecret', body, hashlib.sha256).hexdigest()

        self.assertTrue(self.config._verify_webhook_signature(body, good))
        self.assertTrue(self.config._verify_webhook_signature(body, 'sha256=' + good))
        self.assertFalse(self.config._verify_webhook_signature(body, 'deadbeef'))
        self.assertFalse(self.config._verify_webhook_signature(body, None))

    # ------------------------------------------------------------------
    # Stats propagation
    # ------------------------------------------------------------------

    def test_partner_voip_stats(self):
        process_call_record(self.config, self._call_payload(call_id='CALL-STAT-1'))
        self.assertEqual(self.partner.voip_call_count, 1)
        self.assertEqual(self.partner.voip_last_call_date, datetime(2026, 7, 20, 2, 0, 0))
