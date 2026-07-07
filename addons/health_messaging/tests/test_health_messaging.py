# -*- coding: utf-8 -*-
"""Tests for health_messaging (handover §7). ZNS is mocked at the service
boundary (ZaloAPIClient.send_zns_notification); no network is ever hit."""

import uuid
from datetime import datetime, timedelta
from unittest.mock import patch

from odoo import fields
from odoo.tests import TransactionCase, tagged

from odoo.addons.health_zalo.services.zalo_api import ZaloAPIClient


@tagged('post_install', '-at_install')
class TestHealthMessaging(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.Msg = env['health.outbound.message']
        cls.province = env['health.catchment.province'].search([], limit=1)
        if not cls.province:
            cls.province = env['health.catchment.province'].create(
                {'name': 'Messaging Province'})
        cls.facility = env['health.facility'].create({
            'name': 'Messaging Facility', 'code': 'MSGF',
            'street': '1 Đường Nhắn Tin', 'city': 'Hà Nội',
            'timezone': 'Asia/Ho_Chi_Minh',
            'catchment_province_id': cls.province.id})
        cls.patient = env['res.partner'].create({
            'name': 'Trần Thị Nhắn', 'is_patient': True,
            'catchment_province_id': cls.province.id,
            'primary_facility_id': cls.facility.id,
            'mobile': '0912345678', 'email': 'patient@test.vn'})

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _set(self, key, value):
        self.env['ir.config_parameter'].sudo().set_param(
            'health_messaging.%s' % key, value)

    def _enable(self, dry_run=None):
        self._set('enabled', 'True')
        # disable quiet hours unless a test exercises them
        self._set('quiet_start', '0.0')
        self._set('quiet_end', '0.0')
        if dry_run is not None:
            self._set('dry_run', 'True' if dry_run else 'False')

    def _make_fso(self, when=None, patient=None, confirm=False):
        fso = self.env['health.fieldservice.order'].create({
            'patient_id': (patient or self.patient).id,
            'facility_id': self.facility.id,
            'scheduled_datetime': when or datetime(2026, 7, 10, 2, 0, 0),
            'scheduled_duration': 60})
        if confirm:
            fso.write({'state': 'confirmed'})
        return fso

    def _make_lead(self, fso):
        user = self.env['res.users'].create({
            'name': 'Lead Nurse',
            'login': 'msg_lead_%s' % uuid.uuid4().hex[:8],
            'email': 'lead@test.vn'})
        emp = self.env['hr.employee'].create({
            'name': 'Lead Nurse', 'user_id': user.id,
            'healthcare_facility_id': self.facility.id})
        self.env['health.staff.assignment'].create({
            'fso_id': fso.id, 'staff_id': emp.id, 'assignment_role': 'lead'})
        return user

    def _msgs(self, fso, purpose=None):
        domain = [('fso_id', '=', fso.id)]
        if purpose:
            domain.append(('purpose', '=', purpose))
        return self.Msg.search(domain)

    # ------------------------------------------------------------------
    # 1. Confirmation trigger + tz-correct payload (dry_run default)
    # ------------------------------------------------------------------
    def test_01_confirmation_simulated_tz(self):
        self._enable()  # dry_run left at default True
        fso = self._make_fso()
        fso.write({'state': 'confirmed'})
        msgs = self._msgs(fso, 'booking_confirmation')
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs.state, 'simulated')
        # 02:00 UTC in Asia/Ho_Chi_Minh (UTC+7) → 09:00 wall-clock
        self.assertEqual(msgs.payload_json['visit_time'], '09:00')
        self.assertEqual(msgs.payload_json['visit_date'], '10/07/2026')
        self.assertEqual(msgs.payload_json['patient_name'], 'Trần Thị Nhắn')

    # ------------------------------------------------------------------
    # 2. Dedup — exactly one row per (fso, purpose)
    # ------------------------------------------------------------------
    def test_02_dedup_noop(self):
        self._enable()
        fso = self._make_fso(confirm=True)
        # calling the helper again must no-op (no ValidationError, no 2nd row)
        self.Msg.process_purpose(fso, 'booking_confirmation')
        self.Msg.process_purpose(fso, 'booking_confirmation')
        self.assertEqual(len(self._msgs(fso, 'booking_confirmation')), 1)

    # ------------------------------------------------------------------
    # 3. reminder_24h cron window + state filter
    # ------------------------------------------------------------------
    def test_03_reminder_24h_window(self):
        self._enable()
        now = fields.Datetime.now()
        in_window = self._make_fso(when=now + timedelta(hours=23, minutes=30),
                                   confirm=True)
        out_window = self._make_fso(when=now + timedelta(hours=30),
                                    confirm=True)
        draft = self._make_fso(when=now + timedelta(hours=23, minutes=30))
        self.Msg.cron_process_visit_messages()
        self.assertTrue(self._msgs(in_window, 'reminder_24h'))
        self.assertFalse(self._msgs(out_window, 'reminder_24h'))
        self.assertFalse(self._msgs(draft, 'reminder_24h'))

    # ------------------------------------------------------------------
    # 4. Cascade fallback (dry_run OFF, ZNS raising)
    # ------------------------------------------------------------------
    def test_04_cascade_email_then_escalate(self):
        self._enable(dry_run=False)
        config = self.env['zalo.config'].search([('active', '=', True)],
                                                limit=1)
        if not config:
            config = self.env['zalo.config'].create({
                'name': 'Msg Test', 'app_id': 'a', 'app_secret': 's',
                'oa_id': 'o', 'active': True})
        self._set('zns_template_confirmation', 'TPL123')

        with patch.object(ZaloAPIClient, 'send_zns_notification',
                          side_effect=Exception('boom')):
            # patient WITH email → falls to email
            fso_email = self._make_fso()
            fso_email.write({'state': 'confirmed'})
            msg = self._msgs(fso_email, 'booking_confirmation')
            self.assertEqual(msg.state, 'sent')
            self.assertEqual(msg.channel, 'email')

            # patient WITHOUT email + ZNS failing → escalated to lead staff
            no_email = self.env['res.partner'].create({
                'name': 'Không Email', 'is_patient': True,
                'catchment_province_id': self.province.id,
                'primary_facility_id': self.facility.id,
                'mobile': '0912000111'})
            fso_esc = self._make_fso(patient=no_email)
            lead_user = self._make_lead(fso_esc)
            fso_esc.write({'state': 'confirmed'})
            msg2 = self._msgs(fso_esc, 'booking_confirmation')
            self.assertEqual(msg2.state, 'escalated')
            self.assertEqual(msg2.channel, 'staff_activity')
            activity = self.env['mail.activity'].search([
                ('res_model', '=', 'health.fieldservice.order'),
                ('res_id', '=', fso_esc.id),
                ('user_id', '=', lead_user.id)])
            self.assertTrue(activity)

    # ------------------------------------------------------------------
    # 5. No template id → ZNS skipped, email attempted
    # ------------------------------------------------------------------
    def test_05_no_template_email_path(self):
        self._enable()  # dry_run True, no zns template param set
        fso = self._make_fso(confirm=True)
        msg = self._msgs(fso, 'booking_confirmation')
        self.assertEqual(msg.state, 'simulated')
        self.assertEqual(msg.channel, 'email')

    # ------------------------------------------------------------------
    # 6. Quiet hours defer then process
    # ------------------------------------------------------------------
    def test_06_quiet_hours(self):
        self._enable()
        self._set('quiet_start', '0.0')
        self._set('quiet_end', '24.0')  # whole day is quiet
        fso = self._make_fso(confirm=True)
        msg = self._msgs(fso, 'booking_confirmation')
        self.assertEqual(msg.state, 'queued')
        # window passes → re-process succeeds
        self._set('quiet_start', '0.0')
        self._set('quiet_end', '0.0')
        msg._run_cascade()
        self.assertEqual(msg.state, 'simulated')

    # ------------------------------------------------------------------
    # 7. Cancellation from confirmed sends; from draft does not
    # ------------------------------------------------------------------
    def test_07_cancellation(self):
        self._enable()
        fso = self._make_fso(confirm=True)
        fso.write({'state': 'cancelled'})
        self.assertTrue(self._msgs(fso, 'cancellation_notice'))

        draft = self._make_fso()
        draft.write({'state': 'cancelled'})
        self.assertFalse(self._msgs(draft, 'cancellation_notice'))

    # ------------------------------------------------------------------
    # 8. No usable phone + no email → escalated
    # ------------------------------------------------------------------
    def test_08_no_phone_escalates(self):
        self._enable()
        # res.partner.create validates/normalizes mobile, so an invalid
        # number can never be stored — the real "no usable phone" case is an
        # empty mobile (the cascade's _safe_phone also swallows the
        # ValidationError defensively for any legacy bad value).
        bad = self.env['res.partner'].create({
            'name': 'Không Số', 'is_patient': True,
            'catchment_province_id': self.province.id,
            'primary_facility_id': self.facility.id})  # no mobile, no email
        fso = self._make_fso(patient=bad)
        self._make_lead(fso)
        fso.write({'state': 'confirmed'})
        msg = self._msgs(fso, 'booking_confirmation')
        self.assertEqual(msg.state, 'escalated')

    # ------------------------------------------------------------------
    # 9. Write-hook resilience — a raising cascade never blocks the booking
    # ------------------------------------------------------------------
    def test_09_hook_resilience(self):
        self._enable()
        fso = self._make_fso()
        with patch.object(type(self.Msg), 'process_purpose',
                          side_effect=Exception('boom')):
            fso.write({'state': 'confirmed'})
        self.assertEqual(fso.state, 'confirmed')
