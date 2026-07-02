# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged


def envelope(columns, rows):
    return {'columns': columns, 'rows': rows, 'meta': {}}


TIME_COLS = [
    {'ref': 'd0', 'label': 'Month', 'type': 'date', 'grain': 'month',
     'role': 'date'},
    {'ref': 'm0', 'label': 'Revenue', 'type': 'monetary', 'role': 'measure'},
]
CAT_COLS = [
    {'ref': 'd0', 'label': 'Facility', 'type': 'text', 'role': 'dimension'},
    {'ref': 'm0', 'label': 'Bookings', 'type': 'integer', 'role': 'measure'},
]


@tagged('biz_bi', 'post_install', '-at_install')
class TestInsights(TransactionCase):

    def setUp(self):
        super().setUp()
        self.insights = self.env['bi.insights']

    def test_trend_detected(self):
        rows = [['2026-01-01', 100], ['2026-02-01', 110],
                ['2026-03-01', 100], ['2026-04-01', 150],
                ['2026-05-01', 40]]  # trailing partial bucket
        findings = self.insights._compute_findings(
            envelope(TIME_COLS, rows))
        trend = [f for f in findings if f['kind'] == 'trend']
        self.assertTrue(trend)
        # compares Apr (last complete) vs Mar: +50%
        self.assertEqual(trend[0]['data']['change_pct'], 50.0)
        self.assertEqual(trend[0]['severity'], 'high')

    def test_anomaly_detected(self):
        rows = [['2026-0%d-01' % m, 100] for m in range(1, 8)]
        rows[3][1] = 400  # spike
        findings = self.insights._compute_findings(
            envelope(TIME_COLS, rows))
        anomalies = [f for f in findings if f['kind'] == 'anomaly']
        self.assertEqual(len(anomalies), 1)
        self.assertEqual(anomalies[0]['data']['value'], 400)

    def test_flat_series_quiet(self):
        rows = [['2026-0%d-01' % m, 100] for m in range(1, 7)]
        findings = self.insights._compute_findings(
            envelope(TIME_COLS, rows))
        self.assertFalse([f for f in findings
                          if f['kind'] in ('anomaly',)])

    def test_concentration_detected(self):
        rows = [['HCM', 800], ['Hanoi', 100], ['Danang', 50],
                ['Hue', 30], ['Cantho', 20]]
        findings = self.insights._compute_findings(
            envelope(CAT_COLS, rows))
        concentration = [f for f in findings
                         if f['kind'] == 'concentration']
        self.assertTrue(concentration)
        self.assertEqual(concentration[0]['data']['share_pct'], 80.0)
        self.assertEqual(concentration[0]['severity'], 'high')

    def test_balanced_categories_quiet(self):
        rows = [['A', 100], ['B', 95], ['C', 105], ['D', 98], ['E', 102]]
        findings = self.insights._compute_findings(
            envelope(CAT_COLS, rows))
        self.assertFalse([f for f in findings
                          if f['kind'] in ('concentration', 'outlier')])

    def test_empty_scope(self):
        findings = self.insights._compute_findings(envelope(TIME_COLS, []))
        self.assertEqual(findings[0]['kind'], 'empty')

    def test_kpi_value(self):
        cols = [{'ref': 'm0', 'label': 'Total', 'type': 'integer',
                 'role': 'measure'}]
        findings = self.insights._compute_findings(envelope(cols, [[42]]))
        self.assertEqual(findings[0]['kind'], 'value')
        self.assertEqual(findings[0]['data']['value'], 42)