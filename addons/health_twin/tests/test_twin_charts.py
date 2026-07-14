# -*- coding: utf-8 -*-
"""Tests for ``health.twin.risk.chart_series`` (twin-phase2 §4).

The OWL widget rendering is browser-QA'd (evidence pack); the ORM data
facade is unit-tested here. TransactionCase only (no HttpCase — §5.32
does not apply).
"""
from datetime import timedelta

from odoo import fields
from odoo.tests import TransactionCase, new_test_user, tagged

from .test_twin import _get_fixture


@tagged('post_install', '-at_install')
class TestTwinCharts(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.province, cls.facility, cls.patient = _get_fixture(cls.env)
        cls.Obs = cls.env['health.observation']
        cls.Score = cls.env['health.ews.score']
        cls.Threshold = cls.env['health.vitals.threshold']
        cls.Twin = cls.env['health.twin.risk']
        cls.VType = cls.env['health.vitals.type']
        # An hr.employee for the current user (observation/FSO plumbing).
        if not cls.env.user.employee_id:
            cls.env['hr.employee'].create({
                'name': 'Twin Chart Emp', 'user_id': cls.env.user.id})
            cls.env.user.invalidate_recordset()
        # Nurse in the SAME catchment for the ACL/isolation test.
        cls.nurse = new_test_user(
            cls.env, login='twin_chart_nurse', password='twin_chart_nurse',
            groups='base.group_user,health_base.group_healthcare_nurse')
        cls.nurse.catchment_province_id = cls.province
        # Second province + patient for the cross-catchment isolation test.
        cls.provinceB = cls.env['health.catchment.province'].create({
            'name': 'Twin Chart Province B', 'code': 'TCPB'})
        _pB, _fB, cls.patientB = _get_fixture(
            cls.env, suffix='CB', province=cls.provinceB)

    # -- helpers ------------------------------------------------------------
    def _obs(self, code, value, days_ago, patient=None):
        pid = (patient or self.patient).id
        when = fields.Datetime.now() - timedelta(days=days_ago)
        return self.Obs.create_coded(
            pid, code, value, effective_datetime=when)

    def _score(self, total, band, days_ago, superseded=False, patient=None):
        pid = (patient or self.patient).id
        when = fields.Datetime.now() - timedelta(days=days_ago)
        return self.Score.sudo().create({
            'client_id': pid, 'score_datetime': when,
            'total': total, 'band': band, 'superseded': superseded})

    def _panel(self, res, key):
        return next((p for p in res['panels'] if p['key'] == key), None)

    # -- 1: happy path ------------------------------------------------------
    def test_01_happy_path(self):
        # A week of readings across all core vitals types.
        for d in (6, 4, 2, 0):
            self._obs('hr', 70 + d, d)
            self._obs('bp_sys', 120 + d, d)
            self._obs('bp_dia', 78 + d, d)
            self._obs('spo2_po', 97, d)
            self._obs('temp', 36.5, d)
            self._obs('weight', 68.0, d)
        # Three explicit NEWS2 scores (one superseded — history).
        self._score(2, 'low', 5)
        self._score(4, 'low_medium', 3, superseded=True)
        self._score(6, 'medium', 1)

        res = self.Twin.chart_series(self.patient.id, 30)
        self.assertEqual(res['range_days'], 30)
        keys = [p['key'] for p in res['panels']]
        for k in ('bp', 'hr', 'spo2', 'temp', 'weight', 'news2'):
            self.assertIn(k, keys)

        hr = self._panel(res, 'hr')
        self.assertEqual(len(hr['series']), 1)
        self.assertEqual(len(hr['series'][0]['points']), 4)
        # [iso_string, value] shape, oldest-first.
        pts = hr['series'][0]['points']
        self.assertIsInstance(pts[0][0], str)
        self.assertIsInstance(pts[0][1], float)
        self.assertTrue(pts[0][0] <= pts[-1][0])

        bp = self._panel(res, 'bp')
        self.assertEqual(len(bp['series']), 2)   # systolic + diastolic
        self.assertEqual({s['name'] for s in bp['series']},
                         {'Systolic', 'Diastolic'})

        news2 = self._panel(res, 'news2')
        # At least the three explicit scores (incl. the superseded one) —
        # creating the vitals observations also auto-scores NEWS2, so the
        # history is a superset of 3 (exact-history is asserted in test_06 on
        # a clean patient with no auto-scoring interference).
        self.assertGreaterEqual(len(news2['series'][0]['points']), 3)
        self.assertEqual(news2['band_zones'],
                         [[0, 4, 'success'], [5, 6, 'warning'],
                          [7, 20, 'danger']])

    # -- 2: threshold bands -------------------------------------------------
    def test_02_threshold_bands(self):
        hr_type = self.VType.get_by_code('hr')
        self.Threshold.create({
            'client_id': self.patient.id, 'vitals_type_id': hr_type.id,
            'severity': 'warning', 'min_value': 50, 'max_value': 100,
            'escalation_action': 'none'})
        self.Threshold.create({
            'client_id': self.patient.id, 'vitals_type_id': hr_type.id,
            'severity': 'critical', 'min_value': 40, 'max_value': 120,
            'escalation_action': 'none'})
        self._obs('hr', 72, 1)

        res = self.Twin.chart_series(self.patient.id, 30)
        hr = self._panel(res, 'hr')
        sev = {b['severity']: b for b in hr['bands']}
        self.assertEqual(set(sev), {'warning', 'critical'})
        self.assertEqual(sev['warning']['min'], 50)
        self.assertEqual(sev['warning']['max'], 100)
        self.assertEqual(sev['critical']['min'], 40)
        self.assertEqual(sev['critical']['max'], 120)

    # -- 3: range clamp + window --------------------------------------------
    def test_03_range_clamp_and_window(self):
        self.assertEqual(
            self.Twin.chart_series(self.patient.id, 999)['range_days'], 90)
        self.assertEqual(
            self.Twin.chart_series(self.patient.id, 5)['range_days'], 7)
        self.assertEqual(
            self.Twin.chart_series(self.patient.id)['range_days'], 30)

        # An observation older than the window is excluded.
        self._obs('hr', 61, 100)   # 100 days ago
        self._obs('hr', 62, 3)     # 3 days ago
        res90 = self.Twin.chart_series(self.patient.id, 90)
        hr = self._panel(res90, 'hr')
        self.assertEqual(len(hr['series'][0]['points']), 1)  # only the 3d one
        self.assertEqual(hr['series'][0]['points'][0][1], 62.0)

    # -- 4: ACL / cross-catchment isolation ---------------------------------
    def test_04_no_cross_catchment_leak(self):
        # Seed province-B patient with data (as admin).
        self._obs('hr', 88, 1, patient=self.patientB)
        self._score(9, 'high', 1, patient=self.patientB)

        # Nurse in province A charting the province-B patient → no leak.
        res = self.Twin.with_user(self.nurse).chart_series(
            self.patientB.id, 30)
        # Either empty panels (partner unreadable) or panels with empty series;
        # in NO case do province-B readings appear.
        for p in res['panels']:
            for s in p['series']:
                self.assertEqual(
                    s['points'], [],
                    "cross-catchment leak in panel %s" % p['key'])

        # Sanity: the same nurse CAN chart their own-catchment patient.
        self._obs('hr', 71, 1)
        res_ok = self.Twin.with_user(self.nurse).chart_series(
            self.patient.id, 30)
        hr = self._panel(res_ok, 'hr')
        self.assertTrue(hr and hr['series'][0]['points'])

    # -- 5: empty patient + glucose absence ---------------------------------
    def test_05_empty_patient(self):
        _p, _f, empty = _get_fixture(self.env, suffix='EMPTY',
                                     province=self.province)
        res = self.Twin.chart_series(empty.id, 30)
        keys = [p['key'] for p in res['panels']]
        # Core vitals panels present with empty series.
        for k in ('bp', 'hr', 'spo2', 'temp', 'weight', 'news2'):
            self.assertIn(k, keys)
        for p in res['panels']:
            for s in p['series']:
                self.assertEqual(s['points'], [])
        # Glucose panel absent when the patient never recorded one.
        self.assertNotIn('glucose', keys)

    # -- 6: NEWS2 history includes superseded -------------------------------
    def test_06_news2_history_superseded(self):
        _p, _f, subj = _get_fixture(self.env, suffix='N2',
                                    province=self.province)
        self._score(3, 'low', 4, superseded=True, patient=subj)
        self._score(7, 'high', 1, superseded=False, patient=subj)
        res = self.Twin.chart_series(subj.id, 30)
        news2 = self._panel(res, 'news2')
        pts = news2['series'][0]['points']
        self.assertEqual(len(pts), 2)                 # both, incl superseded
        self.assertEqual([v for _t, v in pts], [3, 7])  # oldest-first

    # -- 7: spo2 union ------------------------------------------------------
    def test_07_spo2_union(self):
        _p, _f, subj = _get_fixture(self.env, suffix='SPO2',
                                    province=self.province)
        self._obs('spo2_po', 96, 4, patient=subj)
        self._obs('spo2', 95, 2, patient=subj)
        self._obs('spo2_po', 97, 0, patient=subj)
        res = self.Twin.chart_series(subj.id, 30)
        spo2 = self._panel(res, 'spo2')
        # ONE merged series, time-ordered.
        self.assertEqual(len(spo2['series']), 1)
        pts = spo2['series'][0]['points']
        self.assertEqual(len(pts), 3)
        self.assertEqual([v for _t, v in pts], [96.0, 95.0, 97.0])

    # -- 8: glucose appears only when present -------------------------------
    def test_08_glucose_present_when_recorded(self):
        _p, _f, subj = _get_fixture(self.env, suffix='GLU',
                                    province=self.province)
        self._obs('glucose', 5.4, 1, patient=subj)
        res = self.Twin.chart_series(subj.id, 30)
        glu = self._panel(res, 'glucose')
        self.assertTrue(glu, "glucose panel should appear when recorded")
        self.assertEqual(len(glu['series'][0]['points']), 1)
        self.assertEqual(glu['series'][0]['points'][0][1], 5.4)
