# -*- coding: utf-8 -*-
"""Tests for the risk trajectory (twin-phase3 §4).

``health.twin.risk.history`` append rules (change-point + daily cap), the
snapshot trajectory fields (trend_direction / score_delta / previous_*), the
``chart_series`` risk panel, the retention GC cron, and append-only + ACL.

Signals are driven via alerts (not observations) so the NEWS2 auto-scoring
hook does not add noise, and recomputes are made deterministic with a
freeze/thaw of ``twin_enabled`` (the create/state hooks no-op while frozen, so
each explicit ``_recompute`` is the ONLY recompute — exact history counts).
TransactionCase only (no HttpCase — §5.32 does not apply).
"""
from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, new_test_user, tagged

from .test_twin import _get_fixture


@tagged('post_install', '-at_install')
class TestTwinHistory(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.province, cls.facility, cls.patient = _get_fixture(cls.env)
        cls.Alert = cls.env['health.monitor.alert']
        cls.Twin = cls.env['health.twin.risk']
        cls.Hist = cls.env['health.twin.risk.history']
        cls.Param = cls.env['ir.config_parameter'].sudo()
        if not cls.env.user.employee_id:
            cls.env['hr.employee'].create({
                'name': 'Twin Hist Emp', 'user_id': cls.env.user.id})
            cls.env.user.invalidate_recordset()
        cls.nurse = new_test_user(
            cls.env, login='twin_hist_nurse', password='twin_hist_nurse',
            groups='base.group_user,health_base.group_healthcare_nurse')
        cls.nurse.catchment_province_id = cls.province
        cls.provinceB = cls.env['health.catchment.province'].create({
            'name': 'Twin Hist Province B', 'code': 'THPB'})
        _pB, _fB, cls.patientB = _get_fixture(
            cls.env, suffix='HB', province=cls.provinceB)

    # -- helpers ----------------------------------------------------------
    def _set(self, key, val):
        self.Param.set_param('health_twin.%s' % key, val)

    def _freeze(self):
        self._set('twin_enabled', 'False')

    def _thaw(self):
        self._set('twin_enabled', 'True')

    def _mk_alert(self, patient=None, severity='critical', rule='threshold'):
        return self.Alert.sudo().create({
            'client_id': (patient or self.patient).id,
            'rule': rule, 'severity': severity, 'title': 'QA alert'})

    def _recent_visit(self, patient, days_ago=1):
        """Force a recently-completed FSO (raw SQL, §5.9) so the staleness
        component is 0 — otherwise a patient with no visit carries the
        999-day sentinel (+5 baseline score) that shifts small-signal bands."""
        fso = self.env['health.fieldservice.order'].create({
            'patient_id': patient.id, 'facility_id': self.facility.id,
            'scheduled_datetime': (
                fields.Datetime.now() - timedelta(days=days_ago))})
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE health_fieldservice_order SET state='completed' "
            "WHERE id=%s", (fso.id,))
        self.env.invalidate_all()
        return fso

    def _recompute(self, patient=None):
        patient = patient or self.patient
        self.Twin.sudo()._recompute_for_patients(patient)
        return self.Twin.sudo().search([('patient_id', '=', patient.id)])

    def _points(self, patient=None):
        return self.Hist.sudo().search(
            [('patient_id', '=', (patient or self.patient).id)],
            order='computed_at, id')

    def _mk_point(self, patient, score, band, days_ago, trigger='first'):
        """Directly append a history point (su bypasses the guard) for the
        chart / GC / ACL tests that need pre-seeded trajectory rows."""
        return self.Hist.sudo().create({
            'patient_id': patient.id,
            'computed_at': fields.Datetime.now() - timedelta(days=days_ago),
            'composite_score': score, 'risk_band': band, 'trigger': trigger})

    # -- 1: first recompute → one 'first' point, snapshot 'new' -----------
    def test_01_first_point(self):
        _p, _f, patient = _get_fixture(self.env, suffix='F1',
                                       province=self.province)
        self._freeze()
        self._mk_alert(patient)
        self._thaw()
        row = self._recompute(patient)
        pts = self._points(patient)
        self.assertEqual(len(pts), 1)
        self.assertEqual(pts.trigger, 'first')
        self.assertEqual(row.trend_direction, 'new')
        self.assertEqual(row.score_delta, 0)
        self.assertEqual(row.previous_score, 0)
        self.assertFalse(row.previous_computed_at)

    # -- 2: band change low→critical → 'band_change', worsening ----------
    def test_02_band_change_worsening(self):
        _p, _f, patient = _get_fixture(self.env, suffix='F2',
                                       province=self.province)
        # First recompute: no open alert → low band, 'first' point.
        row0 = self._recompute(patient)
        first_band = row0.risk_band
        first_score = row0.composite_score
        self.assertNotEqual(first_band, 'critical')
        # Now a critical alert → clinical floor to critical band.
        self._freeze()
        self._mk_alert(patient)
        self._thaw()
        row = self._recompute(patient)
        pts = self._points(patient)
        self.assertEqual(len(pts), 2)
        self.assertEqual(pts[-1].trigger, 'band_change')
        self.assertEqual(row.risk_band, 'critical')
        self.assertEqual(row.trend_direction, 'worsening')
        self.assertGreater(row.score_delta, 0)
        self.assertEqual(row.previous_score, first_score)
        self.assertTrue(row.previous_computed_at)

    # -- 3: improving high→low → 'improving', delta < 0 ------------------
    def test_03_improving(self):
        _p, _f, patient = _get_fixture(self.env, suffix='F3',
                                       province=self.province)
        self._freeze()
        alert = self._mk_alert(patient)
        self._thaw()
        self._recompute(patient)                      # critical, 'new'
        self._freeze()
        alert.action_resolve()                        # close it (frozen)
        self._thaw()
        row = self._recompute(patient)                # drops to low
        self.assertEqual(row.trend_direction, 'improving')
        self.assertLess(row.score_delta, 0)
        self.assertEqual(row.risk_band, 'low')

    # -- 4: stable within noise band → 'stable', NO new point ------------
    def test_04_stable_no_append(self):
        _p, _f, patient = _get_fixture(self.env, suffix='F4',
                                       province=self.province)
        self._freeze()
        self._mk_alert(patient, severity='warning')   # small, band low
        self._thaw()
        self._recompute(patient)                       # 'new', 'first' point
        n_after_first = len(self._points(patient))
        self.assertEqual(n_after_first, 1)
        # Recompute again, identical signals → delta 0 → stable, no append.
        row = self._recompute(patient)
        self.assertEqual(row.trend_direction, 'stable')
        self.assertEqual(row.score_delta, 0)
        self.assertEqual(len(self._points(patient)), 1)   # unchanged

    # -- 5: score move ≥ min_delta, same band → 'delta' ------------------
    def test_05_delta_same_band(self):
        _p, _f, patient = _get_fixture(self.env, suffix='F5',
                                       province=self.province)
        self._recent_visit(patient)                    # staleness 0 → clean band
        self._freeze()
        self._mk_alert(patient, severity='warning')    # 1 warn → ~7, low
        self._thaw()
        self._recompute(patient)
        self._freeze()
        self._mk_alert(patient, severity='warning')    # now 3 warns → ~21, low
        self._mk_alert(patient, severity='warning')
        self._thaw()
        row = self._recompute(patient)
        pts = self._points(patient)
        self.assertEqual(len(pts), 2)
        self.assertEqual(pts[-1].trigger, 'delta')
        self.assertEqual(row.risk_band, 'low')          # same band throughout
        self.assertGreaterEqual(abs(row.score_delta), 8)
        self.assertEqual(row.trend_direction, 'worsening')

    # -- 6: daily heartbeat — last point on an earlier day → 'daily' -----
    def test_06_daily_heartbeat(self):
        _p, _f, patient = _get_fixture(self.env, suffix='F6',
                                       province=self.province)
        self._freeze()
        self._mk_alert(patient, severity='warning')
        self._thaw()
        self._recompute(patient)
        pt = self._points(patient)
        self.assertEqual(len(pt), 1)
        # Backdate the only point to yesterday (plain field, su write).
        pt.sudo().write({
            'computed_at': fields.Datetime.now() - timedelta(days=1)})
        # Recompute with NO material change → the once-a-day heartbeat fires.
        self._recompute(patient)
        pts = self._points(patient)
        self.assertEqual(len(pts), 2)
        self.assertEqual(pts[-1].trigger, 'daily')

    # -- 7: no-flood — two same-day recomputes → at most one point -------
    def test_07_no_flood(self):
        _p, _f, patient = _get_fixture(self.env, suffix='F7',
                                       province=self.province)
        self._freeze()
        self._mk_alert(patient, severity='warning')
        self._thaw()
        self._recompute(patient)
        self._recompute(patient)
        self._recompute(patient)
        # First made a point; the rest are same-day/same-score no-ops.
        self.assertEqual(len(self._points(patient)), 1)

    # -- 8: history_enabled=False → no points; trajectory still computes --
    def test_08_history_disabled(self):
        _p, _f, patient = _get_fixture(self.env, suffix='F8',
                                       province=self.province)
        self._set('history_enabled', 'False')
        try:
            self._freeze()
            self._mk_alert(patient)
            self._thaw()
            row = self._recompute(patient)
            self.assertFalse(self._points(patient))
            # Snapshot trajectory fields still populate (cheap, independent).
            self.assertEqual(row.trend_direction, 'new')
            self.assertEqual(row.score_delta, 0)
        finally:
            self._set('history_enabled', 'True')

    # -- 9: chart_series risk panel — 3 points oldest-first + zones -------
    def test_09_chart_risk_panel(self):
        _p, _f, patient = _get_fixture(self.env, suffix='F9',
                                       province=self.province)
        self._mk_point(patient, 10, 'low', 4, trigger='first')
        self._mk_point(patient, 40, 'moderate', 2, trigger='delta')
        self._mk_point(patient, 70, 'high', 0, trigger='delta')
        res = self.Twin.chart_series(patient.id, 30)
        risk = next((p for p in res['panels'] if p['key'] == 'risk'), None)
        self.assertTrue(risk, "risk panel should be present")
        pts = risk['series'][0]['points']
        self.assertEqual(len(pts), 3)
        self.assertEqual([v for _t, v in pts], [10, 40, 70])   # oldest-first
        self.assertTrue(pts[0][0] <= pts[-1][0])
        self.assertTrue(risk['band_zones'])
        # Zones use the twin band thresholds (25 / 50).
        self.assertEqual(risk['band_zones'][0], [0, 24, 'success'])
        self.assertEqual(risk['band_zones'][1], [25, 49, 'warning'])
        self.assertEqual(risk['band_zones'][2], [50, 100, 'danger'])
        # A window older than the point is excluded.
        self._mk_point(patient, 99, 'critical', 100, trigger='first')
        res7 = self.Twin.chart_series(patient.id, 7)
        risk7 = next(p for p in res7['panels'] if p['key'] == 'risk')
        self.assertEqual(len(risk7['series'][0]['points']), 3)  # not the 100d

    # -- 10: GC cron prunes past retention, gate honoured ----------------
    def test_10_gc_cron(self):
        _p, _f, patient = _get_fixture(self.env, suffix='F10',
                                       province=self.province)
        old = self._mk_point(patient, 20, 'low', 400)
        recent = self._mk_point(patient, 30, 'moderate', 1)
        # Gate OFF → no-op.
        self._set('history_gc_enabled', 'False')
        self.Hist.cron_twin_history_gc()
        self.assertTrue(old.exists())
        self.assertTrue(recent.exists())
        # Gate ON → old pruned, recent survives (retention 365d default).
        self._set('history_gc_enabled', 'True')
        self.Hist.cron_twin_history_gc()
        self.assertFalse(old.exists())
        self.assertTrue(recent.exists())

    # -- 11: append-only + ACL + catchment isolation ---------------------
    def test_11_append_only_and_acl(self):
        point = self._mk_point(self.patient, 55, 'high', 0)
        # Nurse (same catchment) can READ.
        self.assertEqual(
            point.with_user(self.nurse).read(['composite_score'])[0]['id'],
            point.id)
        # Nurse cannot create (perm_create=0 → AccessError; create has no
        # Python guard) nor write/unlink (engine-only guard fires first →
        # UserError, §5.39).
        with self.assertRaises(AccessError):
            self.Hist.with_user(self.nurse).create({
                'patient_id': self.patient.id,
                'computed_at': fields.Datetime.now(),
                'composite_score': 1, 'risk_band': 'low', 'trigger': 'first'})
        with self.assertRaises(UserError):
            point.with_user(self.nurse).write({'composite_score': 1})
        with self.assertRaises(UserError):
            point.with_user(self.nurse).unlink()
        # Catchment isolation: a province-B point is invisible to nurse A.
        pointB = self._mk_point(self.patientB, 60, 'high', 0)
        self.assertNotIn(
            pointB, self.Hist.with_user(self.nurse).search([]))
