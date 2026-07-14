# -*- coding: utf-8 -*-
"""Tests for the deterioration forecast (twin-phase4 §4).

Two halves:
  * the PURE ``twin_forecast`` kernel (the §2.1 worked vectors — fast, no ORM);
  * model integration on ``health.twin.risk`` (forecast fields folded into the
    snapshot in ``_upsert_one``, the ``will_escalate`` money field, the
    never-lowers rail, the ``chart_series`` forecast segment).

Integration signals are driven via alerts (not observations) so the NEWS2
auto-scoring hook adds no noise, and recomputes are made deterministic with a
freeze/thaw of ``twin_enabled``. Forecast-test patients get a recent completed
visit (§5.43) so the 999-day staleness sentinel does not perturb the band math.
TransactionCase only (no HttpCase — §5.32 does not apply).
"""
from datetime import timedelta

from odoo import fields
from odoo.tests import TransactionCase, tagged

from odoo.addons.health_twin.models import twin_forecast
from odoo.addons.health_twin.models.health_twin_risk import _BAND_IX

from .test_twin import _get_fixture

# Kernel config for the pure-vector tests (mirrors the seed defaults §2.6).
_KCFG = {'horizon_days': 3, 'min_points': 4, 'min_r2': 0.3,
         'min_slope': 1.0, 'lookback_days': 14}


# =====================================================================
# Pure kernel — the §2.1 worked vectors (no ORM)
# =====================================================================
@tagged('post_install', '-at_install')
class TestTwinForecastKernel(TransactionCase):

    def test_01_fit_rising(self):
        # Rising [(-6,10),(-4,20),(-2,30),(0,40)] → slope 5, intercept 40, r2 1.
        fr = twin_forecast.fit([(-6, 10), (-4, 20), (-2, 30), (0, 40)])
        b, a, r2, n = fr
        self.assertAlmostEqual(b, 5.0)
        self.assertAlmostEqual(a, 40.0)
        self.assertAlmostEqual(r2, 1.0)
        self.assertEqual(n, 4)

    def test_02_fit_degenerate(self):
        # n < 2 → None.
        self.assertIsNone(twin_forecast.fit([]))
        self.assertIsNone(twin_forecast.fit([(0, 40)]))
        # All points at the same x (no time spread) → slope undefined → None.
        self.assertIsNone(twin_forecast.fit([(0, 10), (0, 20), (0, 30)]))
        # Flat series → slope 0, r2 1.0 (a zero slope fully explains it).
        fr = twin_forecast.fit([(-6, 30), (-4, 30), (-2, 30), (0, 30)])
        b, _a, r2, _n = fr
        self.assertAlmostEqual(b, 0.0)
        self.assertAlmostEqual(r2, 1.0)

    def test_03_project(self):
        # Rising horizon 3 → 55, has_forecast True.
        res = twin_forecast.project(
            [(-6, 10), (-4, 20), (-2, 30), (0, 40)], _KCFG)
        self.assertTrue(res['has_forecast'])
        self.assertEqual(res['score'], 55)
        self.assertAlmostEqual(res['slope'], 5.0)
        # Falling → projection clamps to 0 (still a valid fit).
        res_f = twin_forecast.project(
            [(-6, 60), (-4, 40), (-2, 20), (0, 10)], _KCFG)
        self.assertTrue(res_f['has_forecast'])
        self.assertEqual(res_f['score'], 0)
        self.assertLess(res_f['slope'], 0)
        # Sparse (n < min_points) → no forecast, confidence 'none', echo latest.
        res_s = twin_forecast.project([(0, 40)], _KCFG)
        self.assertFalse(res_s['has_forecast'])
        self.assertEqual(res_s['confidence'], 'none')
        self.assertEqual(res_s['score'], 40)

    def test_04_confidence(self):
        # high: r2 >= 0.7 AND n >= min_points + 2 (=6).
        self.assertEqual(
            twin_forecast.confidence((1.0, 0.0, 0.8, 6), _KCFG), 'high')
        # medium: r2 >= min_r2 but not high (n=4 < 6).
        self.assertEqual(
            twin_forecast.confidence((1.0, 0.0, 0.5, 4), _KCFG), 'medium')
        # low: enough points, but r2 below min_r2.
        self.assertEqual(
            twin_forecast.confidence((1.0, 0.0, 0.1, 4), _KCFG), 'low')
        # none: fewer than min_points, or no fit at all.
        self.assertEqual(
            twin_forecast.confidence((1.0, 0.0, 1.0, 2), _KCFG), 'none')
        self.assertEqual(twin_forecast.confidence(None, _KCFG), 'none')

    def test_05_eta_days(self):
        self.assertAlmostEqual(twin_forecast.eta_days(40, 5.0, 50), 2.0)
        self.assertIsNone(twin_forecast.eta_days(40, -1.0, 50))  # falling
        self.assertIsNone(twin_forecast.eta_days(60, 5.0, 50))   # already above


# =====================================================================
# Model integration
# =====================================================================
@tagged('post_install', '-at_install')
class TestTwinForecastModel(TransactionCase):

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
                'name': 'Twin Fc Emp', 'user_id': cls.env.user.id})
            cls.env.user.invalidate_recordset()

    _TREND_RULES = ('trend_hr_drift', 'trend_sbp_drift', 'trend_spo2_decline')

    # -- helpers ----------------------------------------------------------
    def _set(self, key, val):
        self.Param.set_param('health_twin.%s' % key, val)

    def _freeze(self):
        self._set('twin_enabled', 'False')

    def _thaw(self):
        self._set('twin_enabled', 'True')

    def _mk_alert(self, patient, severity='critical', rule='threshold'):
        return self.Alert.sudo().create({
            'client_id': patient.id,
            'rule': rule, 'severity': severity, 'title': 'QA alert'})

    def _mk_trend_alerts(self, patient):
        """Three distinct open trend alerts → a deterministic moderate (31)
        live composite when staleness is 0 (alert 60·0.35 + trend 100·0.1)."""
        for rule in self._TREND_RULES:
            self._mk_alert(patient, severity='warning', rule=rule)

    def _recent_visit(self, patient, days_ago=1):
        """Force a recently-completed FSO (raw SQL §5.9) → staleness 0, so the
        999-day sentinel (+5 baseline, §5.43) does not shift the band."""
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

    def _mk_point(self, patient, score, band, days_ago, trigger='delta'):
        return self.Hist.sudo().create({
            'patient_id': patient.id,
            'computed_at': fields.Datetime.now() - timedelta(days=days_ago),
            'composite_score': score, 'risk_band': band, 'trigger': trigger})

    def _recompute(self, patient):
        self.Twin.sudo()._recompute_for_patients(patient)
        return self.Twin.sudo().search([('patient_id', '=', patient.id)])

    # -- 6: rising trajectory → will_escalate, forecast_band high --------
    def test_06_rising_escalates(self):
        _p, _f, patient = _get_fixture(self.env, suffix='FC6',
                                       province=self.province)
        self._recent_visit(patient)
        # History climbing low → moderate (strictly before now).
        self._mk_point(patient, 10, 'low', 6, 'first')
        self._mk_point(patient, 18, 'low', 4)
        self._mk_point(patient, 26, 'moderate', 2)
        self._set('forecast_horizon_days', '7')
        try:
            self._freeze()
            self._mk_trend_alerts(patient)      # current 31 → moderate
            self._thaw()
            row = self._recompute(patient)
            self.assertEqual(row.risk_band, 'moderate')
            self.assertTrue(row.will_escalate)
            self.assertEqual(row.forecast_band, 'high')
            self.assertGreater(row.forecast_eta_days, 0.0)
            self.assertIn(row.forecast_confidence, ('medium', 'high'))
            self.assertGreaterEqual(row.forecast_score, 50)
            self.assertGreater(row.forecast_slope, 0.0)
        finally:
            self._set('forecast_horizon_days', '3')

    # -- 7: falling + currently critical → no escalate, no de-rank -------
    def test_07_falling_no_derank(self):
        _p, _f, crit = _get_fixture(self.env, suffix='FC7c',
                                    province=self.province)
        # History descending, all critical; current floored to critical.
        self._mk_point(crit, 95, 'critical', 6, 'first')
        self._mk_point(crit, 88, 'critical', 4)
        self._mk_point(crit, 82, 'critical', 2)
        self._freeze()
        self._mk_alert(crit, severity='critical')   # clinical floor → critical
        self._thaw()
        crit_row = self._recompute(crit)
        self.assertEqual(crit_row.risk_band, 'critical')
        self.assertFalse(crit_row.will_escalate)
        self.assertLess(crit_row.forecast_slope, 0.0)   # genuinely falling
        # Forecast band is never ABOVE the current band.
        self.assertLessEqual(
            _BAND_IX[crit_row.forecast_band], _BAND_IX['critical'])
        # A moderate patient must rank BELOW the critical one — the falling
        # forecast changes nothing about the composite-desc worklist sort.
        _p2, _f2, mod = _get_fixture(self.env, suffix='FC7m',
                                     province=self.province)
        self._recent_visit(mod)
        self._freeze()
        self._mk_trend_alerts(mod)
        self._thaw()
        mod_row = self._recompute(mod)
        self.assertEqual(mod_row.risk_band, 'moderate')
        ordered = self.Twin.sudo().search(
            [('patient_id', 'in', (crit.id, mod.id))],
            order='composite_score desc, id desc')
        self.assertEqual(ordered[0].patient_id, crit,
                         'currently-critical patient must not be de-ranked')

    # -- 8: sparse (< min_points) → no forecast --------------------------
    def test_08_sparse_no_forecast(self):
        _p, _f, patient = _get_fixture(self.env, suffix='FC8',
                                       province=self.province)
        self._recent_visit(patient)
        self._freeze()
        self._mk_alert(patient, severity='warning')   # 1 warn → low, 1 point
        self._thaw()
        row = self._recompute(patient)
        # Only the live anchor (no prior history) → fit degenerate.
        self.assertEqual(row.forecast_confidence, 'none')
        self.assertFalse(row.will_escalate)
        self.assertEqual(row.forecast_score, row.composite_score)
        self.assertEqual(row.forecast_band, row.risk_band)

    # -- 9: forecast_enabled=False → no forecast; snapshot still computes -
    def test_09_forecast_disabled(self):
        _p, _f, patient = _get_fixture(self.env, suffix='FC9',
                                       province=self.province)
        self._set('forecast_enabled', 'False')
        try:
            self._recent_visit(patient)
            # A rising history that WOULD escalate if forecasting were on.
            self._mk_point(patient, 10, 'low', 6, 'first')
            self._mk_point(patient, 18, 'low', 4)
            self._mk_point(patient, 26, 'moderate', 2)
            self._freeze()
            self._mk_trend_alerts(patient)
            self._thaw()
            row = self._recompute(patient)
            # The rest of the snapshot still computes.
            self.assertEqual(row.risk_band, 'moderate')
            self.assertGreater(row.composite_score, 0)
            self.assertEqual(row.trend_direction, 'new')
            # Forecast fields are the self-consistent no-forecast defaults.
            self.assertEqual(row.forecast_confidence, 'none')
            self.assertFalse(row.will_escalate)
            self.assertEqual(row.forecast_score, row.composite_score)
            self.assertEqual(row.forecast_band, row.risk_band)
        finally:
            self._set('forecast_enabled', 'True')

    # -- 10: never-escalate-below (forecast band LOWER than current) -----
    def test_10_never_escalate_below(self):
        _p, _f, patient = _get_fixture(self.env, suffix='FC10',
                                       province=self.province)
        self._recent_visit(patient)
        # History descending within the moderate band; forecast projects DOWN
        # into low — must never set will_escalate even with a clean fit.
        self._mk_point(patient, 45, 'moderate', 6, 'first')
        self._mk_point(patient, 40, 'moderate', 4)
        self._mk_point(patient, 35, 'moderate', 2)
        self._freeze()
        self._mk_trend_alerts(patient)      # current 31 → moderate
        self._thaw()
        row = self._recompute(patient)
        self.assertEqual(row.risk_band, 'moderate')
        self.assertLess(row.forecast_slope, 0.0)
        self.assertIn(row.forecast_band, ('low', 'moderate'))
        self.assertLessEqual(
            _BAND_IX[row.forecast_band], _BAND_IX['moderate'])
        self.assertFalse(row.will_escalate)
        self.assertEqual(row.forecast_eta_days, 0.0)

    # -- 11: chart_series — forecast segment present iff a forecast ------
    def test_11_chart_forecast_segment(self):
        # (a) rising patient → risk panel gains a 2-point 'Forecast' series.
        _p, _f, patient = _get_fixture(self.env, suffix='FC11a',
                                       province=self.province)
        self._recent_visit(patient)
        self._mk_point(patient, 10, 'low', 6, 'first')
        self._mk_point(patient, 18, 'low', 4)
        self._mk_point(patient, 26, 'moderate', 2)
        self._set('forecast_horizon_days', '7')
        try:
            self._freeze()
            self._mk_trend_alerts(patient)
            self._thaw()
            row = self._recompute(patient)
            self.assertTrue(row.will_escalate)
        finally:
            self._set('forecast_horizon_days', '3')
        res = self.Twin.chart_series(patient.id, 30)
        risk = next(p for p in res['panels'] if p['key'] == 'risk')
        names = [s['name'] for s in risk['series']]
        self.assertIn('Forecast', names)
        fc = next(s for s in risk['series'] if s['name'] == 'Forecast')
        self.assertEqual(len(fc['points']), 2)          # now, now+horizon
        # The projected end point matches the stored forecast score.
        self.assertEqual(fc['points'][1][1], row.forecast_score)

        # (b) no-forecast patient → the risk panel keeps a single series.
        _p2, _f2, sparse = _get_fixture(self.env, suffix='FC11b',
                                        province=self.province)
        self._recent_visit(sparse)
        self._freeze()
        self._mk_alert(sparse, severity='warning')
        self._thaw()
        self._recompute(sparse)
        res2 = self.Twin.chart_series(sparse.id, 30)
        risk2 = next(p for p in res2['panels'] if p['key'] == 'risk')
        self.assertEqual(len(risk2['series']), 1)
        self.assertNotIn('Forecast', [s['name'] for s in risk2['series']])
