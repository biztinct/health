# -*- coding: utf-8 -*-
import json
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import HttpCase, TransactionCase, new_test_user, tagged

from odoo.addons.health_telemonitoring.models import tm_config
from odoo.addons.health_telemonitoring.models.news2 import (
    news2_band, news2_component_scores)


def _get_fixture(env, suffix=''):
    """Province + facility + patient (conventions §6)."""
    Partner = env['res.partner']
    Facility = env['health.facility']
    province = env['health.catchment.province'].search([], limit=1)
    if not province:
        province = env['health.catchment.province'].create({
            'name': 'TM Test Province', 'code': 'TMP'})
    facility = Facility.search(
        [('catchment_province_id', '=', province.id)], limit=1)
    if not facility:
        facility = Facility.create({
            'name': 'TM Test Facility', 'code': 'TMF',
            'street': '1 TM Street', 'city': 'Test City',
            'catchment_province_id': province.id})
    patient = Partner.create({
        'name': 'TM Test Patient%s' % suffix,
        'is_patient': True,
        'catchment_province_id': province.id,
        'primary_facility_id': facility.id})
    return province, facility, patient


# =====================================================================
# 1-2 — NEWS2 kernel (pure functions)
# =====================================================================
@tagged('post_install', '-at_install')
class TestNews2Kernel(TransactionCase):

    def _one(self, **kw):
        """Neutral (all-zero) baseline; override one axis via kwargs."""
        base = dict(rr=16, spo2=98, on_oxygen=False, sbp=120, hr=70,
                    temp=37.0, acvpu='A', scale2=False)
        base.update(kw)
        return news2_component_scores(**base)

    def test_01_rr_boundaries(self):
        expected = {8: 3, 9: 1, 11: 1, 12: 0, 20: 0, 21: 2, 24: 2, 25: 3}
        for rr, score in expected.items():
            self.assertEqual(self._one(rr=rr)['rr_score'], score,
                             'RR %s' % rr)

    def test_01_spo2_scale1_boundaries(self):
        expected = {91: 3, 92: 2, 93: 2, 94: 1, 95: 1, 96: 0}
        for spo2, score in expected.items():
            self.assertEqual(self._one(spo2=spo2)['spo2_score'], score,
                             'SpO2 s1 %s' % spo2)

    def test_01_spo2_scale2_boundaries(self):
        on_air = {83: 3, 84: 2, 85: 2, 87: 1, 88: 0, 92: 0, 93: 0}
        for spo2, score in on_air.items():
            self.assertEqual(
                self._one(spo2=spo2, scale2=True, on_oxygen=False)['spo2_score'],
                score, 'SpO2 s2 air %s' % spo2)
        on_o2 = {93: 1, 94: 1, 95: 2, 96: 2, 97: 3}
        for spo2, score in on_o2.items():
            self.assertEqual(
                self._one(spo2=spo2, scale2=True, on_oxygen=True)['spo2_score'],
                score, 'SpO2 s2 o2 %s' % spo2)

    def test_01_o2_sbp_hr_temp_boundaries(self):
        self.assertEqual(self._one(on_oxygen=True)['o2_score'], 2)
        self.assertEqual(self._one(on_oxygen=False)['o2_score'], 0)
        sbp = {90: 3, 91: 2, 100: 2, 101: 1, 110: 1, 111: 0, 219: 0, 220: 3}
        for v, s in sbp.items():
            self.assertEqual(self._one(sbp=v)['bp_score'], s, 'SBP %s' % v)
        hr = {40: 3, 41: 1, 50: 1, 51: 0, 90: 0, 91: 1, 110: 1, 111: 2,
              130: 2, 131: 3}
        for v, s in hr.items():
            self.assertEqual(self._one(hr=v)['hr_score'], s, 'HR %s' % v)
        temp = {35.0: 3, 35.1: 1, 36.0: 1, 36.1: 0, 38.0: 0, 38.1: 1,
                39.0: 1, 39.1: 2}
        for v, s in temp.items():
            self.assertEqual(self._one(temp=v)['temp_score'], s, 'temp %s' % v)

    def test_01_acvpu(self):
        for acvpu, score in {'A': 0, 'C': 3, 'V': 3, 'P': 3, 'U': 3}.items():
            self.assertEqual(
                self._one(acvpu=acvpu)['consciousness_score'], score)

    def test_02_bands(self):
        self.assertEqual(news2_band({'a': 0, 'b': 0})[1], 'low')       # 0
        self.assertEqual(news2_band({'a': 2, 'b': 2})[1], 'low')       # 4, no 3
        self.assertEqual(news2_band({'a': 2, 'b': 2, 'c': 1})[1], 'medium')  # 5
        self.assertEqual(news2_band({'a': 3, 'b': 2, 'c': 2})[1], 'high')    # 7
        # single component 3, total 3 -> low_medium
        total, band = news2_band({'a': 3, 'b': 0, 'c': 0})
        self.assertEqual((total, band), (3, 'low_medium'))

    def test_02_invalid_acvpu(self):
        with self.assertRaises(ValueError):
            news2_component_scores(16, 98, False, 120, 70, 37.0, acvpu='X')


# =====================================================================
# 3-15, 21-22 — engine + inbox (TransactionCase)
# =====================================================================
@tagged('post_install', '-at_install')
class TestTelemonitoring(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.province, cls.facility, cls.patient = _get_fixture(cls.env)
        cls.Obs = cls.env['health.observation']
        cls.Score = cls.env['health.ews.score']
        cls.Alert = cls.env['health.monitor.alert']
        # Facility manager with a linked user (activity target).
        employee = cls.env.user.employee_id
        if not employee:
            employee = cls.env['hr.employee'].create({
                'name': 'TM Manager', 'user_id': cls.env.user.id,
                'is_om_role': True})
            cls.env.user.invalidate_recordset()
        cls.facility.facility_manager_id = employee
        # Clinical users for the lifecycle / ACL tests.
        cls.nurse = new_test_user(
            cls.env, login='tm_nurse', password='tm_nurse',
            groups='base.group_user,health_base.group_healthcare_nurse')
        cls.nurse.catchment_province_id = cls.province
        cls.head_nurse = new_test_user(
            cls.env, login='tm_head', password='tm_head',
            groups='base.group_user,health_base.group_healthcare_head_nurse')
        cls.head_nurse.catchment_province_id = cls.province

    # -- helpers -------------------------------------------------------
    def _make_fso(self):
        return self.env['health.fieldservice.order'].create({
            'patient_id': self.patient.id,
            'facility_id': self.facility.id,
            'scheduled_datetime': fields.Datetime.now() + timedelta(days=1)})

    def _capture(self, fso, rr=16, spo2=98, sbp=120, hr=70, temp=36.5,
                 when=None, acvpu=None, o2=None, patient=None):
        pid = (patient or self.patient).id
        when = when or fields.Datetime.now()
        self.Obs.create_coded(pid, 'rr', rr, fso_id=fso.id,
                              effective_datetime=when)
        self.Obs.create_coded(pid, 'hr', hr, fso_id=fso.id,
                              effective_datetime=when)
        self.Obs.create_coded(pid, 'temp', temp, fso_id=fso.id,
                              effective_datetime=when)
        self.Obs.create_coded(pid, 'spo2_po', spo2, fso_id=fso.id,
                              effective_datetime=when)
        if acvpu is not None:
            self.Obs.create_coded(pid, 'acvpu', acvpu, fso_id=fso.id,
                                  effective_datetime=when)
        if o2 is not None:
            self.Obs.create_coded(pid, 'o2_flow', o2, fso_id=fso.id,
                                  effective_datetime=when)
        self.Obs.create_panel(
            pid, 'bp_panel',
            [{'code': 'bp_sys', 'value': sbp},
             {'code': 'bp_dia', 'value': 80}],
            order_id=fso.id, effective_datetime=when)

    def _current(self, patient=None):
        return self.Score.search([
            ('client_id', '=', (patient or self.patient).id),
            ('superseded', '=', False)])

    # -- 3: E2E -------------------------------------------------------
    def test_03_e2e_capture(self):
        fso = self._make_fso()
        self._capture(fso, rr=16, spo2=98, sbp=120, hr=70, temp=36.5)
        score = self._current()
        self.assertEqual(len(score), 1)
        self.assertEqual(score.total, 0)
        self.assertEqual(score.band, 'low')
        self.assertEqual(score.order_id, fso)
        self.assertGreaterEqual(len(score.observation_ids), 5)
        self.assertEqual(score.rr_value, 16)
        self.assertEqual(score.spo2_value, 98)
        self.assertEqual(score.sbp_value, 120)
        self.assertEqual(score.hr_value, 70)
        self.assertEqual(score.temp_value, 36.5)

    # -- 4: missing component ----------------------------------------
    def test_04_missing_component(self):
        fso = self._make_fso()
        when = fields.Datetime.now()
        # No temperature -> no score.
        self.Obs.create_coded(self.patient.id, 'rr', 16, fso_id=fso.id,
                              effective_datetime=when)
        self.Obs.create_coded(self.patient.id, 'hr', 70, fso_id=fso.id,
                              effective_datetime=when)
        self.Obs.create_coded(self.patient.id, 'spo2_po', 98, fso_id=fso.id,
                              effective_datetime=when)
        self.Obs.create_panel(
            self.patient.id, 'bp_panel',
            [{'code': 'bp_sys', 'value': 120}, {'code': 'bp_dia', 'value': 80}],
            order_id=fso.id, effective_datetime=when)
        self.assertFalse(self._current())

    # -- 5: ACVPU defaulted ------------------------------------------
    def test_05_acvpu_defaulted(self):
        fso = self._make_fso()
        self._capture(fso)
        score = self._current()
        self.assertEqual(score.acvpu_value, 'A')
        self.assertTrue(score.defaulted_consciousness)

    # -- 6: oxygen ---------------------------------------------------
    def test_06_on_oxygen(self):
        fso = self._make_fso()
        self._capture(fso, o2=2.0)
        score = self._current()
        self.assertTrue(score.on_oxygen)
        self.assertEqual(score.o2_score, 2)

    # -- 7: scale 2 --------------------------------------------------
    def test_07_scale2(self):
        self.patient.news2_spo2_scale2 = True
        fso = self._make_fso()
        self._capture(fso, spo2=91)   # scale1 would score 3
        score = self._current()
        self.assertEqual(score.spo2_score, 0)
        self.assertEqual(score.spo2_scale, '2')

    # -- 8: supersede ------------------------------------------------
    def test_08_supersede(self):
        fso = self._make_fso()
        t0 = fields.Datetime.now() - timedelta(minutes=10)
        self._capture(fso, when=t0)
        first = self._current()
        self.assertEqual(len(first), 1)
        self._capture(fso, when=fields.Datetime.now())
        # Exactly one current score; the earlier one is superseded.
        self.assertEqual(len(self._current()), 1)
        self.assertTrue(first.superseded)
        self.assertGreaterEqual(self.Score.search_count([
            ('client_id', '=', self.patient.id)]), 2)

    # -- 9: amendment ------------------------------------------------
    def test_09_amendment(self):
        fso = self._make_fso()
        self._capture(fso)
        first = self._current()
        hr_obs = self.Obs.search([
            ('client_id', '=', self.patient.id),
            ('vitals_type_id.code', '=', 'hr')], limit=1)
        hr_obs.write({'value_quantity': 130})
        current = self._current()
        self.assertEqual(len(current), 1)
        self.assertNotEqual(current, first)
        self.assertTrue(first.superseded)

    # -- 10: disabled ------------------------------------------------
    def test_10_ews_disabled(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'health_telemonitoring.ews_enabled', 'False')
        fso = self._make_fso()
        self._capture(fso)
        self.assertFalse(self._current())

    # -- 11: high band -> critical alert + activity ------------------
    def test_11_band_high(self):
        fso = self._make_fso()
        self._capture(fso, rr=30, spo2=90, sbp=88, hr=70, temp=36.5)
        score = self._current()
        self.assertEqual(score.band, 'high')
        alert = self.Alert.search([
            ('client_id', '=', self.patient.id), ('rule', '=', 'ews_high')])
        self.assertEqual(len(alert), 1)
        self.assertEqual(alert.severity, 'critical')
        activity = self.env['mail.activity'].search([
            ('res_model', '=', 'res.partner'),
            ('res_id', '=', self.patient.id)])
        self.assertTrue(activity)

    # -- 12: medium band ---------------------------------------------
    def test_12_band_medium(self):
        fso = self._make_fso()
        self._capture(fso, rr=22, spo2=98, sbp=120, hr=125, temp=38.5)
        score = self._current()
        self.assertEqual(score.band, 'medium')
        alert = self.Alert.search([
            ('client_id', '=', self.patient.id), ('rule', '=', 'ews_medium')])
        self.assertEqual(len(alert), 1)
        self.assertEqual(alert.severity, 'warning')
        self.assertFalse(self.env['mail.activity'].search([
            ('res_model', '=', 'res.partner'),
            ('res_id', '=', self.patient.id)]))

    # -- 13: low_medium and low --------------------------------------
    def test_13_band_low_medium_and_low(self):
        fso = self._make_fso()
        self._capture(fso, rr=30, spo2=98, sbp=120, hr=70, temp=36.5)
        score = self._current()
        self.assertEqual(score.band, 'low_medium')
        self.assertTrue(self.Alert.search([
            ('client_id', '=', self.patient.id), ('rule', '=', 'ews_single3')]))
        # Fresh patient, all-normal -> low -> no alert.
        _p, _f, patient2 = _get_fixture(self.env, suffix=' low')
        fso2 = self.env['health.fieldservice.order'].create({
            'patient_id': patient2.id, 'facility_id': self.facility.id,
            'scheduled_datetime': fields.Datetime.now() + timedelta(days=1)})
        self._capture(fso2, patient=patient2)
        self.assertEqual(self._current(patient2).band, 'low')
        self.assertFalse(self.Alert.search([('client_id', '=', patient2.id)]))

    # -- 14: threshold mirror ----------------------------------------
    def test_14_threshold_mirror(self):
        fso = self._make_fso()
        hr_type = self.env.ref('health_vitals.vitals_type_heart_rate')
        self.env['health.vitals.threshold'].create({
            'client_id': self.patient.id,
            'vitals_type_id': hr_type.id,
            'severity': 'critical',
            'max_value': 50,
            'escalation_action': 'activity'})
        self.Obs.create_coded(self.patient.id, 'hr', 120, fso_id=fso.id)
        # super() escalation ran (activity) AND a threshold inbox alert.
        self.assertTrue(self.env['mail.activity'].search([
            ('res_model', '=', 'res.partner'),
            ('res_id', '=', self.patient.id)]))
        alert = self.Alert.search([
            ('client_id', '=', self.patient.id), ('rule', '=', 'threshold')])
        self.assertEqual(len(alert), 1)
        self.assertEqual(alert.vitals_type_id, hr_type)
        self.assertEqual(alert.severity, 'critical')

    # -- 15: open-dedup ----------------------------------------------
    def test_15_open_dedup(self):
        fso = self._make_fso()
        self._capture(fso, rr=30, spo2=90, sbp=88, hr=70, temp=36.5,
                      when=fields.Datetime.now() - timedelta(minutes=20))
        self._capture(fso, rr=30, spo2=90, sbp=88, hr=70, temp=36.5,
                      when=fields.Datetime.now())
        alerts = self.Alert.search([
            ('client_id', '=', self.patient.id), ('rule', '=', 'ews_high')])
        self.assertEqual(len(alerts), 1, 'dedup while open')
        alerts.action_resolve()
        self._capture(fso, rr=30, spo2=90, sbp=88, hr=70, temp=36.5)
        self.assertEqual(self.Alert.search_count([
            ('client_id', '=', self.patient.id), ('rule', '=', 'ews_high')]), 2)

    # -- 21: never-block ---------------------------------------------
    def test_21_never_block(self):
        fso = self._make_fso()

        def boom(*a, **k):
            raise RuntimeError('boom')
        with patch.object(type(self.Score), '_score_from_observations', boom):
            obs = self.Obs.create_coded(self.patient.id, 'hr', 80,
                                        fso_id=fso.id)
        self.assertTrue(obs.exists())
        self.assertFalse(self._current())

    # -- 22: append-only + ACL ---------------------------------------
    def test_22_append_only(self):
        fso = self._make_fso()
        self._capture(fso, rr=30, spo2=90, sbp=88, hr=70, temp=36.5)
        score = self._current()
        alert = self.Alert.search([('client_id', '=', self.patient.id)], limit=1)
        # Score: the model's append-only guard fires before the ACL check.
        with self.assertRaises(UserError):
            score.with_user(self.nurse).unlink()
        # Alert: no python guard — the ACL (perm_unlink=0 for nurse) denies.
        with self.assertRaises(AccessError):
            alert.with_user(self.nurse).unlink()
        with self.assertRaises(AccessError):
            self.Alert.with_user(self.nurse).create({
                'client_id': self.patient.id, 'rule': 'ews_high',
                'severity': 'critical', 'title': 'x'})

    # -- 20: lifecycle -----------------------------------------------
    def test_20_lifecycle(self):
        fso = self._make_fso()
        self._capture(fso, rr=30, spo2=90, sbp=88, hr=70, temp=36.5)
        alert = self.Alert.search([
            ('client_id', '=', self.patient.id), ('rule', '=', 'ews_high')],
            limit=1)
        alert.with_user(self.nurse).action_acknowledge()
        self.assertEqual(alert.state, 'acknowledged')
        self.assertEqual(alert.ack_user_id, self.nurse)
        # Nurse cannot resolve.
        with self.assertRaises(UserError):
            alert.with_user(self.nurse).action_resolve()
        # Dismiss without a closing note raises.
        with self.assertRaises(UserError):
            alert.with_user(self.head_nurse).action_dismiss()
        # Head nurse resolves.
        alert.with_user(self.head_nurse).action_resolve()
        self.assertEqual(alert.state, 'resolved')

    # -- 24: settings kill-switch roundtrip (review fix HIGH-1) --------
    def test_24_settings_toggle_off_roundtrip(self):
        """Saving a default-True Boolean as False must persist: core
        set_param() unlinks falsy values and tm_config would fall back to
        the True default — the set_values override stores explicit
        strings."""
        settings = self.env['res.config.settings'].create({
            'tm_ews_enabled': False,
            'tm_trend_enabled': False,
            'tm_activity_on_critical': False,
            'tm_ews_window_minutes': 0,
        })
        settings.set_values()
        self.assertFalse(tm_config.get_bool(self.env, 'ews_enabled', True))
        self.assertFalse(tm_config.get_bool(self.env, 'trend_enabled', True))
        self.assertFalse(
            tm_config.get_bool(self.env, 'activity_on_critical', True))
        # Zero window clamps back to the default rather than unlinking.
        self.assertEqual(
            tm_config.get_int(self.env, 'ews_window_minutes', 60), 60)
        # And the engine actually honours the persisted OFF switch.
        fso = self._make_fso()
        self._capture(fso, rr=30, spo2=90, sbp=88, hr=70, temp=36.5)
        self.assertFalse(self._current())
        # Toggle back on via the same path.
        settings = self.env['res.config.settings'].create({
            'tm_ews_enabled': True, 'tm_trend_enabled': True,
            'tm_activity_on_critical': True, 'tm_ews_window_minutes': 60})
        settings.set_values()
        self.assertTrue(tm_config.get_bool(self.env, 'ews_enabled', False))

    # -- 25: lifecycle gates not bypassable by direct write ------------
    def test_25_direct_write_bypass_blocked(self):
        fso = self._make_fso()
        self._capture(fso, rr=30, spo2=90, sbp=88, hr=70, temp=36.5)
        alert = self.Alert.search([
            ('client_id', '=', self.patient.id), ('rule', '=', 'ews_high')],
            limit=1)
        # A nurse holding the model write ACL cannot flip lifecycle fields.
        with self.assertRaises(UserError):
            alert.with_user(self.nurse).write({'state': 'resolved'})
        with self.assertRaises(UserError):
            alert.with_user(self.head_nurse).write({'state': 'dismissed'})
        self.assertEqual(alert.state, 'new')
        # close_note stays user-writable (needed before dismiss).
        alert.with_user(self.head_nurse).write({'close_note': 'duplicate'})
        alert.with_user(self.head_nurse).action_dismiss()
        self.assertEqual(alert.state, 'dismissed')


# =====================================================================
# 16-19 — trend sweep
# =====================================================================
@tagged('post_install', '-at_install')
class TestTelemonitoringTrend(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.province, cls.facility, cls.patient = _get_fixture(
            cls.env, suffix=' trend')
        cls.Obs = cls.env['health.observation']
        cls.Alert = cls.env['health.monitor.alert']

    def _obs(self, code, value, days_ago):
        self.Obs.create_coded(
            self.patient.id, code, value,
            effective_datetime=fields.Datetime.now() - timedelta(days=days_ago))

    def test_16_hr_drift(self):
        for d in (14, 15, 16):
            self._obs('hr', 70, d)
        for d in (1, 2, 3):
            self._obs('hr', 90, d)
        self.Alert._trend_sweep_client(self.patient, fields.Datetime.now())
        alert = self.Alert.search([
            ('client_id', '=', self.patient.id),
            ('rule', '=', 'trend_hr_drift')])
        self.assertTrue(alert)
        self.assertEqual(alert.severity, 'warning')
        data = json.loads(alert.evidence_json)
        self.assertEqual(data['median_recent'], 90)
        self.assertEqual(data['median_prior'], 70)

    def test_17_weight_loss(self):
        self._obs('weight', 60, 10)
        self._obs('weight', 57, 2)
        self.Alert._trend_sweep_client(self.patient, fields.Datetime.now())
        self.assertTrue(self.Alert.search([
            ('client_id', '=', self.patient.id),
            ('rule', '=', 'trend_weight_loss')]))

    def test_18_spo2_decline(self):
        for d in (14, 15, 16):
            self._obs('spo2_po', 97, d)
        for d in (1, 2, 3):
            self._obs('spo2_po', 92, d)
        self.Alert._trend_sweep_client(self.patient, fields.Datetime.now())
        alert = self.Alert.search([
            ('client_id', '=', self.patient.id),
            ('rule', '=', 'trend_spo2_decline')])
        self.assertTrue(alert)
        self.assertEqual(alert.severity, 'critical')

    def test_19_gate_and_cap(self):
        # Make this client trend-eligible (>= min_points rows).
        for d in (14, 15, 16):
            self._obs('hr', 70, d)
        for d in (1, 2, 3):
            self._obs('hr', 90, d)
        # Disabled -> per-client method never called.
        self.env['ir.config_parameter'].sudo().set_param(
            'health_telemonitoring.trend_enabled', 'False')
        with patch.object(type(self.Alert), '_trend_sweep_client',
                          return_value=0) as m_off:
            self.Alert.cron_trend_sweep()
        self.assertEqual(m_off.call_count, 0)
        # Enabled, cap 1 -> exactly one client processed.
        self.env['ir.config_parameter'].sudo().set_param(
            'health_telemonitoring.trend_enabled', 'True')
        self.env['ir.config_parameter'].sudo().set_param(
            'health_telemonitoring.trend_batch_cap', '1')
        with patch.object(type(self.Alert), '_trend_sweep_client',
                          return_value=0) as m_on:
            self.Alert.cron_trend_sweep()
        self.assertEqual(m_on.call_count, 1)


# =====================================================================
# 23 — PWA endpoint HttpCase
# =====================================================================
@tagged('post_install', '-at_install')
class TestTelemonitoringHttp(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.province, cls.facility, cls.patient = _get_fixture(
            cls.env, suffix=' http')
        cls.fso = cls.env['health.fieldservice.order'].create({
            'patient_id': cls.patient.id, 'facility_id': cls.facility.id,
            'scheduled_datetime': fields.Datetime.now() + timedelta(days=1)})
        cls.nurse = new_test_user(
            cls.env, login='tm_http_nurse', password='tm_http_nurse',
            groups='base.group_user,health_base.group_healthcare_nurse')
        cls.nurse.catchment_province_id = cls.province
        # The nurse must be ASSIGNED to the visit to read it (FSO record
        # rule) — clone the assigned-nurse fixture (conventions §6).
        cls.nurse_emp = cls.env['hr.employee'].create({
            'name': 'TM Http Nurse Emp', 'user_id': cls.nurse.id})
        if not cls.env.user.employee_id:
            cls.env['hr.employee'].create({
                'name': 'TM Http Admin Emp', 'user_id': cls.env.user.id})
        cls.fso.action_assign_staff_to_fso(
            cls.nurse_emp.id, assignment_role='lead')

    def setUp(self):
        super().setUp()
        # Ledger §5.32: pin OFF side-effect switches we do not assert on.
        Param = self.env['ir.config_parameter'].sudo()
        self._saved = {
            'health_workflow_auto.timecard_sync_enabled':
                Param.get_param('health_workflow_auto.timecard_sync_enabled'),
            'health_telemonitoring.activity_on_critical':
                Param.get_param('health_telemonitoring.activity_on_critical'),
        }
        Param.set_param('health_workflow_auto.timecard_sync_enabled', 'False')
        Param.set_param('health_telemonitoring.activity_on_critical', 'False')

    def tearDown(self):
        Param = self.env['ir.config_parameter'].sudo()
        for key, val in self._saved.items():
            Param.set_param(key, val if val not in (None, False) else '')
        super().tearDown()

    def test_23_pwa_ews_payload(self):
        self.authenticate('tm_http_nurse', 'tm_http_nurse')
        payload = {
            'observations': [
                {'code': 'rr', 'value': 26},
                {'code': 'hr', 'value': 122},
                {'code': 'temp', 'value': 39.2},
                {'code': 'spo2_po', 'value': 90},
                {'code': 'acvpu', 'value': 'V'},
                {'code': 'o2_flow', 'value': 2},
            ],
            'bp': {'systolic': 88, 'diastolic': 80},
        }
        resp = self.url_open(
            '/health_pwa/api/fso/%s/vitals' % self.fso.id,
            data=json.dumps(payload),
            headers={'Content-Type': 'application/json'})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body['success'], body)
        ews = body['data']['ews']
        self.assertIsNotNone(ews, 'NEWS2 payload present')
        # rr3 + spo2_3 + o2_2 + bp3 + hr2 + temp2 + consciousness3 = 18
        self.assertEqual(ews['total'], 18)
        self.assertEqual(ews['band'], 'high')
