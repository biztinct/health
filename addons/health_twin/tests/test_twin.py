# -*- coding: utf-8 -*-
import json
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, new_test_user, tagged

from odoo.addons.health_twin.models import twin_config, twin_score


def _get_fixture(env, suffix='', province=None):
    """Province + facility + patient (conventions §6)."""
    Partner = env['res.partner']
    Facility = env['health.facility']
    if province is None:
        province = env['health.catchment.province'].search([], limit=1)
        if not province:
            province = env['health.catchment.province'].create({
                'name': 'Twin Test Province', 'code': 'TWP'})
    facility = Facility.search(
        [('catchment_province_id', '=', province.id)], limit=1)
    if not facility:
        facility = Facility.create({
            'name': 'Twin Test Facility%s' % suffix, 'code': 'TWF%s' % suffix,
            'street': '1 Twin Street', 'city': 'Test City',
            'catchment_province_id': province.id})
    patient = Partner.create({
        'name': 'Twin Test Patient%s' % suffix,
        'is_patient': True,
        'catchment_province_id': province.id,
        'primary_facility_id': facility.id})
    return province, facility, patient


# =====================================================================
# 1 — scoring kernel (pure functions)
# =====================================================================
@tagged('post_install', '-at_install')
class TestTwinKernel(TransactionCase):

    def test_01_news2_component(self):
        # band → points, with linear decay
        self.assertEqual(twin_score.news2_component('high', 0, 336), 100.0)
        self.assertEqual(twin_score.news2_component('high', 336, 336), 0.0)
        self.assertEqual(twin_score.news2_component('high', 168, 336), 50.0)
        self.assertEqual(twin_score.news2_component('low', 0, 336), 0.0)
        self.assertEqual(twin_score.news2_component('', 0, 336), 0.0)
        # medium band base 55, half-decay → 27.5
        self.assertAlmostEqual(
            twin_score.news2_component('medium', 168, 336), 27.5)

    def test_01_alert_component(self):
        self.assertEqual(twin_score.alert_component(1, 0), 100.0)   # 1 crit
        self.assertEqual(twin_score.alert_component(0, 2), 40.0)    # 2 warn
        self.assertEqual(twin_score.alert_component(0, 4), 60.0)    # capped
        self.assertEqual(twin_score.alert_component(1, 5), 100.0)   # crit wins

    def test_01_trend_component(self):
        self.assertEqual(twin_score.trend_component(0), 0.0)
        self.assertEqual(twin_score.trend_component(2), 80.0)
        self.assertEqual(twin_score.trend_component(3), 100.0)      # capped

    def test_01_staleness_component(self):
        self.assertEqual(twin_score.staleness_component(5, 10), 0.0)
        self.assertEqual(twin_score.staleness_component(10, 10), 0.0)
        self.assertEqual(twin_score.staleness_component(15, 10), 50.0)
        self.assertEqual(twin_score.staleness_component(20, 10), 100.0)
        self.assertEqual(twin_score.staleness_component(999, 10), 100.0)

    def test_01_composite_normalization(self):
        w = {'news2': 0.5, 'alert': 0.35, 'trend': 0.1, 'staleness': 0.05}
        # all 100 → 100 regardless of weights
        self.assertEqual(twin_score.composite(
            {'news2': 100, 'alert': 100, 'trend': 100, 'staleness': 100}, w),
            100)
        # only news2 → 100*0.5/1.0 = 50
        self.assertEqual(twin_score.composite(
            {'news2': 100, 'alert': 0, 'trend': 0, 'staleness': 0}, w), 50)
        # weights that don't sum to 1 are normalized (can't exceed 100)
        self.assertEqual(twin_score.composite(
            {'news2': 100, 'alert': 100, 'trend': 100, 'staleness': 100},
            {'news2': 2, 'alert': 2, 'trend': 2, 'staleness': 2}), 100)

    def test_01_band_for(self):
        th = {'moderate': 25, 'high': 50, 'critical': 75}
        self.assertEqual(twin_score.band_for(0, th), 'low')
        self.assertEqual(twin_score.band_for(24, th), 'low')
        self.assertEqual(twin_score.band_for(25, th), 'moderate')
        self.assertEqual(twin_score.band_for(49, th), 'moderate')
        self.assertEqual(twin_score.band_for(50, th), 'high')
        self.assertEqual(twin_score.band_for(74, th), 'high')
        self.assertEqual(twin_score.band_for(75, th), 'critical')
        self.assertEqual(twin_score.band_for(100, th), 'critical')


# =====================================================================
# 2-16 — engine, hooks, cron, settings, ACL
# =====================================================================
@tagged('post_install', '-at_install')
class TestTwinEngine(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.province, cls.facility, cls.patient = _get_fixture(cls.env)
        cls.Obs = cls.env['health.observation']
        cls.Score = cls.env['health.ews.score']
        cls.Alert = cls.env['health.monitor.alert']
        cls.Twin = cls.env['health.twin.risk']
        cls.Param = cls.env['ir.config_parameter'].sudo()
        # An hr.employee for the current user (FSO / activity plumbing).
        if not cls.env.user.employee_id:
            cls.env['hr.employee'].create({
                'name': 'Twin Admin Emp', 'user_id': cls.env.user.id})
            cls.env.user.invalidate_recordset()
        # A nurse in the SAME catchment for the ACL / isolation tests.
        cls.nurse = new_test_user(
            cls.env, login='twin_nurse', password='twin_nurse',
            groups='base.group_user,health_base.group_healthcare_nurse')
        cls.nurse.catchment_province_id = cls.province
        # A second province + patient for catchment-isolation.
        cls.provinceB = cls.env['health.catchment.province'].create({
            'name': 'Twin Province B', 'code': 'TWPB'})
        _pB, _fB, cls.patientB = _get_fixture(
            cls.env, suffix='B', province=cls.provinceB)

    # -- helpers -------------------------------------------------------
    def _make_fso(self, patient=None, when=None):
        return self.env['health.fieldservice.order'].create({
            'patient_id': (patient or self.patient).id,
            'facility_id': self.facility.id,
            'scheduled_datetime': when or (
                fields.Datetime.now() + timedelta(days=1))})

    def _complete_fso(self, patient, days_ago):
        """Create an FSO and force it 'completed' at `days_ago` via raw SQL
        (§5.9) — bypasses the write-side completion notifications."""
        when = fields.Datetime.now() - timedelta(days=days_ago)
        fso = self.env['health.fieldservice.order'].create({
            'patient_id': patient.id, 'facility_id': self.facility.id,
            'scheduled_datetime': when})
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE health_fieldservice_order SET state='completed' "
            "WHERE id=%s", (fso.id,))
        self.env.invalidate_all()
        return fso

    def _capture(self, fso, rr=16, spo2=98, sbp=120, hr=70, temp=36.5,
                 when=None, patient=None):
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
        self.Obs.create_panel(
            pid, 'bp_panel',
            [{'code': 'bp_sys', 'value': sbp},
             {'code': 'bp_dia', 'value': 80}],
            order_id=fso.id, effective_datetime=when)

    def _row(self, patient=None):
        return self.Twin.sudo().search(
            [('patient_id', '=', (patient or self.patient).id)])

    def _recompute(self, patient=None):
        self.Twin.sudo()._recompute_for_patients(patient or self.patient)
        return self._row(patient)

    def _mk_alert(self, patient=None, rule='threshold', severity='critical'):
        return self.Alert.sudo().create({
            'client_id': (patient or self.patient).id,
            'rule': rule, 'severity': severity, 'title': 'QA alert'})

    # -- 2: live high NEWS2 → high/critical row -----------------------
    def test_02_recompute_high_news2(self):
        fso = self._make_fso()
        self._capture(fso, rr=30, spo2=90, sbp=88, hr=70, temp=36.5)
        row = self._recompute()
        self.assertEqual(len(row), 1)
        self.assertIn(row.risk_band, ('high', 'critical'))
        self.assertGreater(row.news2_total, 0)
        self.assertTrue(row.news2_at)
        self.assertTrue(row.ews_score_id)
        self.assertEqual(row.news2_band, 'high')
        self.assertTrue(0 <= row.composite_score <= 100)

    # -- 3: open critical alert, no NEWS2 -----------------------------
    def test_03_alert_only(self):
        self._mk_alert(self.patientB)  # isolated patient, no NEWS2
        row = self._recompute(self.patientB)
        self.assertEqual(len(row), 1)
        self.assertEqual(row.alert_points, 100)
        self.assertEqual(row.open_critical_count, 1)
        self.assertEqual(row.news2_total, 0)
        # The alert component drives the score off 'low'. NOTE: under the
        # specified 0.35 alert weight a lone critical alert yields composite
        # ~35-40 → 'moderate' (see report deviation D1), NOT 'high'.
        self.assertNotEqual(row.risk_band, 'low')

    # -- 4: no signals → composite ~0 / band low ----------------------
    def test_04_no_signals(self):
        _p, _f, patient = _get_fixture(self.env, suffix='NoSig')
        row = self._recompute(patient)
        self.assertEqual(len(row), 1)
        self.assertEqual(row.news2_total, 0)
        self.assertEqual(row.open_alert_count, 0)
        self.assertEqual(row.risk_band, 'low')
        self.assertLess(row.composite_score, 25)

    # -- 5: aged NEWS2 decays to ~0 -----------------------------------
    def test_05_decay(self):
        fso = self._make_fso()
        self._capture(fso, rr=30, spo2=90, sbp=88, hr=70, temp=36.5,
                      when=fields.Datetime.now() - timedelta(days=20))
        # Remove the open alert so only the (decayed) NEWS2 could score.
        self.Alert.sudo().search([
            ('client_id', '=', self.patient.id),
            ('state', 'in', ('new', 'acknowledged'))]).action_resolve()
        row = self._recompute()
        self.assertEqual(row.news2_points, 0)     # 20d > 14d decay window
        self.assertEqual(row.risk_band, 'low')

    # -- 6: upsert keeps exactly one row ------------------------------
    def test_06_upsert(self):
        fso = self._make_fso()
        self._capture(fso, rr=30, spo2=90, sbp=88, hr=70, temp=36.5)
        row1 = self._recompute()
        self.assertEqual(len(row1), 1)
        first_id = row1.id
        self._recompute()
        rows = self._row()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows.id, first_id)   # updated, not re-inserted

    # -- 7: staleness from an old completed visit ---------------------
    def test_07_staleness(self):
        _p, _f, patient = _get_fixture(self.env, suffix='Stale')
        self._complete_fso(patient, days_ago=25)
        row = self._recompute(patient)
        self.assertEqual(row.days_since_last_visit, 25)
        self.assertGreater(row.staleness_points, 0)   # 25d > 10d threshold
        # Small weight: staleness alone does not reach 'high'.
        self.assertNotEqual(row.risk_band, 'high')
        self.assertNotEqual(row.risk_band, 'critical')

    # -- 8: event hook on new NEWS2 score -----------------------------
    def test_08_hook_ews(self):
        fso = self._make_fso()
        self.assertFalse(self._row())
        self._capture(fso, rr=30, spo2=90, sbp=88, hr=70, temp=36.5)
        # The ews.score create hook recomputed the row — no explicit call.
        row = self._row()
        self.assertEqual(len(row), 1)
        self.assertEqual(row.news2_band, 'high')

    # -- 9: state-change hook drops open_critical_count ---------------
    def test_09_hook_alert_state(self):
        alert = self._mk_alert()
        row = self._row()
        self.assertEqual(row.open_critical_count, 1)
        alert.action_acknowledge()   # still open
        alert.action_resolve()       # now closed → hook recomputes
        row = self._row()
        self.assertEqual(row.open_critical_count, 0)

    # -- 10: cron gate + candidate union + batch cap ------------------
    def test_10_cron(self):
        # Gate OFF → no processing.
        self.Param.set_param('health_twin.twin_sweep_enabled', 'False')
        with patch.object(type(self.Twin), '_recompute_for_patients',
                          return_value=None) as m_off:
            self.Twin.cron_twin_sweep()
        self.assertEqual(m_off.call_count, 0)
        self.Param.set_param('health_twin.twin_sweep_enabled', 'True')

        # Candidate union: a patient with ONLY a completed visit (in-horizon,
        # 20d — stale enough that its composite stays >0 and survives the
        # zero-score prune, proving it was actually processed).
        _p, _f, visit_only = _get_fixture(self.env, suffix='VisitOnly')
        self._complete_fso(visit_only, days_ago=20)
        self.Twin.cron_twin_sweep()
        self.assertTrue(self._row(visit_only),
                        'visit-only patient is a sweep candidate')

        # Batch cap 1 with 2 eligible → exactly 1 recompute call.
        self.Param.set_param('health_twin.twin_sweep_batch_cap', '1')
        self._mk_alert(self.patient)
        self._mk_alert(self.patientB)
        with patch.object(type(self.Twin), '_recompute_for_patients') as m_cap:
            self.Twin.cron_twin_sweep()
        # One call with a single-record set (the cap).
        self.assertEqual(m_cap.call_count, 1)
        self.assertEqual(len(m_cap.call_args[0][0]), 1)

    # -- 11: worklist default filter shows high+critical, hides low ---
    def test_11_default_filter(self):
        fso = self._make_fso()
        self._capture(fso, rr=30, spo2=90, sbp=88, hr=70, temp=36.5)
        self._recompute()                       # patient → critical
        _p, _f, low = _get_fixture(self.env, suffix='Low')
        self._recompute(low)                     # low patient
        dom = [('risk_band', 'in', ('high', 'critical'))]
        visible = self.Twin.sudo().search(dom)
        self.assertIn(self._row(), visible)
        self.assertNotIn(self._row(low), visible)

    # -- 12: ACL — nurse reads, cannot write/create/unlink; isolation -
    def test_12_acl(self):
        fso = self._make_fso()
        self._capture(fso, rr=30, spo2=90, sbp=88, hr=70, temp=36.5)
        self._recompute()
        row = self._row()
        # Nurse in the same catchment can read.
        self.assertEqual(
            row.with_user(self.nurse).read(['composite_score'])[0]['id'],
            row.id)
        # Nurse cannot create/write/unlink. create() has no Python guard so
        # the perm_create=0 ACL raises AccessError; write()/unlink() carry the
        # engine-only Python guard (ews.score shape) which fires first with a
        # UserError (cf. telemonitoring test_22_append_only).
        with self.assertRaises(AccessError):
            self.Twin.with_user(self.nurse).create({
                'patient_id': self.patient.id})
        with self.assertRaises(UserError):
            row.with_user(self.nurse).write({'composite_score': 1})
        with self.assertRaises(UserError):
            row.with_user(self.nurse).unlink()
        # Catchment isolation: a province-B row is invisible to nurse A.
        self._mk_alert(self.patientB)
        rowB = self._recompute(self.patientB)
        self.assertTrue(rowB)
        self.assertNotIn(
            rowB, self.Twin.with_user(self.nurse).search([]))

    # -- 13: never-block — a recompute crash can't break capture ------
    def test_13_never_block(self):
        fso = self._make_fso()

        def boom(*a, **k):
            raise RuntimeError('boom')
        with patch.object(type(self.Twin), '_recompute_for_patients', boom):
            self._capture(fso, rr=30, spo2=90, sbp=88, hr=70, temp=36.5)
            alert = self._mk_alert()
        # The score and the alert were still created despite the crash.
        self.assertTrue(self.Score.search([
            ('client_id', '=', self.patient.id)]))
        self.assertTrue(alert.exists())

    # -- 14: settings §5.36 roundtrip ---------------------------------
    def test_14_settings_toggle(self):
        settings = self.env['res.config.settings'].create({
            'twin_enabled': False, 'twin_sweep_enabled': False})
        settings.set_values()
        self.assertFalse(twin_config.get_bool(self.env, 'twin_enabled', True))
        self.assertFalse(
            twin_config.get_bool(self.env, 'twin_sweep_enabled', True))
        # Engine honours the persisted OFF switch: recompute is a no-op.
        fso = self._make_fso()
        self._capture(fso, rr=30, spo2=90, sbp=88, hr=70, temp=36.5)
        self.assertFalse(self._row())
        # Toggle back on.
        settings = self.env['res.config.settings'].create({
            'twin_enabled': True, 'twin_sweep_enabled': True})
        settings.set_values()
        self.assertTrue(twin_config.get_bool(self.env, 'twin_enabled', False))

    # -- 15: factors_json is valid + has the breakdown ----------------
    def test_15_factors_json(self):
        fso = self._make_fso()
        self._capture(fso, rr=30, spo2=90, sbp=88, hr=70, temp=36.5)
        row = self._recompute()
        data = json.loads(row.factors_json)
        self.assertIn('components', data)
        self.assertIn('weights', data)
        self.assertIn('raw', data)
        for key in ('news2', 'alert', 'trend', 'staleness'):
            self.assertIn(key, data['components'])
            self.assertIn(key, data['weights'])

    # -- 16: catchment compute mirrors the patient --------------------
    def test_16_catchment(self):
        fso = self._make_fso()
        self._capture(fso, rr=30, spo2=90, sbp=88, hr=70, temp=36.5)
        row = self._recompute()
        self.assertEqual(row.catchment_province_id,
                         self.patient._get_health_catchment_province())
        self.assertEqual(row.catchment_province_id, self.province)
