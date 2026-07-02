# -*- coding: utf-8 -*-
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import BiCase


@tagged('biz_bi', 'post_install', '-at_install')
class TestQueryEngine(BiCase):

    def test_basic_group_by(self):
        result = self.engine.run(self._base_request())
        self.assertNotIn('error', result)
        refs = [col['ref'] for col in result['columns']]
        self.assertEqual(refs, ['d0', 'm0'])
        rows = {row[0]: row[1] for row in result['rows']}
        vn_name = self.country_a.name
        au_name = self.country_b.name
        self.assertEqual(rows.get(vn_name), 30.0)   # 10 + 20
        self.assertEqual(rows.get(au_name), 30.0)
        self.assertEqual(result['meta']['source'], 'live')

    def test_measure_only_kpi(self):
        result = self.engine.run(self._base_request(dimensions=[]))
        self.assertEqual(len(result['rows']), 1)
        self.assertEqual(result['rows'][0][0], 60.0)

    def test_calculated_measure(self):
        result = self.engine.run(self._base_request(
            dimensions=[],
            measures=[{'field_id': self.f_calc.id, 'agg': 'sum'}]))
        self.assertEqual(result['rows'][0][0], 120.0)

    def test_date_grain(self):
        result = self.engine.run(self._base_request(
            dimensions=[{'field_id': self.f_create_date.id,
                         'grain': 'month'}]))
        self.assertTrue(result['rows'])

    def test_rejects_bad_grain(self):
        # hostile grain strings are rejected...
        with self.assertRaises(UserError):
            self.engine.run(self._base_request(
                dimensions=[{'field_id': self.f_create_date.id,
                             'grain': "1); DROP TABLE res_users"}]))
        # ...but a valid grain on a non-date field is simply ignored
        result = self.engine.run(self._base_request(
            dimensions=[{'field_id': self.f_country_name.id,
                         'grain': 'month'}]))
        self.assertNotIn('error', result)

    def test_rejects_foreign_field(self):
        other = self.env['bi.dataset'].create({
            'name': 'Other', 'workspace_id': self.workspace.id})
        node = self.env['bi.dataset.node'].create({
            'dataset_id': other.id, 'source_id': self.source_partner.id,
            'is_root': True})
        node.action_scan_fields()
        foreign_field = other.field_ids[0]
        with self.assertRaises(UserError):
            self.engine.run(self._base_request(
                dimensions=[{'field_id': foreign_field.id}]))

    def test_rejects_bad_operator(self):
        with self.assertRaises(UserError):
            self.engine.run(self._base_request(
                filters=[{'field_id': self.f_name.id,
                          'op': 'union_select', 'value': 'x'}]))

    def test_rejects_bad_agg(self):
        with self.assertRaises(UserError):
            self.engine.run(self._base_request(
                measures=[{'field_id': self.f_latitude.id,
                           'agg': 'string_agg'}]))

    def test_rejects_bad_sort_ref(self):
        with self.assertRaises(UserError):
            self.engine.run(self._base_request(
                sort=[{'ref': '1; DROP TABLE res_users', 'dir': 'asc'}]))

    def test_hostile_label_never_reaches_sql(self):
        """Business names never enter SQL — renaming a field to an injection
        string must not affect execution."""
        self.f_country_name.name = '"; DROP TABLE res_users; --'
        result = self.engine.run(self._base_request())
        self.assertNotIn('error', result)
        self.assertTrue(self.env['res.users'].search_count([]))

    def test_limit_cap(self):
        result = self.engine.run(self._base_request(limit=999999))
        self.assertLessEqual(len(result['rows']), 5000)

    def test_relative_filter(self):
        result = self.engine.run(self._base_request(
            filters=[{'field_id': self.f_create_date.id,
                      'op': 'relative', 'value': 'today'}]))
        # fixtures were created today
        self.assertTrue(result['rows'])
        with self.assertRaises(UserError):
            self.engine.run(self._base_request(
                filters=[{'field_id': self.f_create_date.id,
                          'op': 'relative', 'value': 'sometime'}]))

    def test_in_and_between_filters(self):
        result = self.engine.run(self._base_request(
            filters=[
                {'field_id': self.f_name.id, 'op': 'like_i',
                 'value': 'BI Test'},
                {'field_id': self.f_latitude.id, 'op': 'between',
                 'value': [15, 35]},
            ]))
        total = sum(row[1] for row in result['rows'])
        self.assertEqual(total, 50.0)  # 20 + 30

    def test_cache_roundtrip(self):
        request = self._base_request()
        first = self.engine.run(request)
        self.assertEqual(first['meta']['cache'], 'miss')
        second = self.engine.run(request)
        self.assertEqual(second['meta']['cache'], 'hit')
        self.assertEqual(first['rows'], second['rows'])

    def test_batch_isolates_errors(self):
        results = self.engine.run_batch([
            self._base_request(),
            {'dataset_id': 999999, 'measures': []},
        ])
        self.assertNotIn('error', results[0])
        self.assertIn('error', results[1])

    def test_top_n_with_others(self):
        result = self.engine.run(self._base_request(
            options={'top_n': {'ref': 'm0', 'n': 1, 'others': True}}))
        self.assertEqual(len(result['rows']), 2)  # top-1 + Others
        self.assertEqual(result['rows'][1][0], '__bi_others__')
        # additive: top + others == grand total (60)
        total = sum(row[1] for row in result['rows'])
        self.assertEqual(total, 60.0)

    def test_shift_filters_previous(self):
        shifted, any_shifted = self.engine.shift_filters_previous([
            {'field_id': self.f_create_date.id, 'op': 'relative',
             'value': 'this_month'},
            {'field_id': self.f_name.id, 'op': 'like_i', 'value': 'x'},
        ])
        self.assertTrue(any_shifted)
        self.assertEqual(shifted[0]['op'], 'date_range')
        self.assertEqual(shifted[1]['op'], 'like_i')  # untouched
        # previous window ends where the current one starts
        from odoo import fields as odoo_fields
        start, _end = self.engine.relative_bounds('this_month')
        self.assertEqual(odoo_fields.Date.to_date(shifted[0]['value'][1]),
                         start)
        # no date filter -> not shiftable
        _s, any2 = self.engine.shift_filters_previous(
            [{'field_id': self.f_name.id, 'op': 'eq', 'value': 'x'}])
        self.assertFalse(any2)

    def test_compare_request_runs(self):
        chart = self.env['bi.chart'].create({
            'name': 'KPI', 'dataset_id': self.dataset.id, 'chart_type': 'kpi',
            'config_json': {'slots': {
                'values': [{'field_id': self.f_latitude.id, 'agg': 'sum'}]},
                'filters': [{'field_id': self.f_create_date.id,
                             'op': 'relative', 'value': 'this_month'}]},
        })
        compare_request = chart._to_compare_request()
        self.assertIsNotNone(compare_request)
        result = self.engine.run(compare_request)
        # previous month has no fixture rows -> SUM is NULL
        self.assertEqual(result['rows'][0][0], None)
        # chart without date filter has nothing to compare
        chart.config_json = {'slots': {'values': [
            {'field_id': self.f_latitude.id, 'agg': 'sum'}]}, 'filters': []}
        self.assertIsNone(chart._to_compare_request())

    def test_grain_override_drill(self):
        chart = self.env['bi.chart'].create({
            'name': 'Trend', 'dataset_id': self.dataset.id,
            'chart_type': 'line',
            'config_json': {'slots': {
                'x': [{'field_id': self.f_create_date.id, 'grain': 'year'}],
                'values': [{'field_id': self.f_latitude.id, 'agg': 'sum'}]}},
        })
        request = chart._to_query_request(
            grain_overrides={str(self.f_create_date.id): 'month'})
        self.assertEqual(request['dimensions'][0]['grain'], 'month')
        # drill filter: this year's bucket only, finer grain — runs clean
        start, end = self.engine.relative_bounds('this_year')
        result = self.engine.run(dict(request, filters=[
            {'field_id': self.f_create_date.id, 'op': 'date_range',
             'value': [str(start), str(end)]}]))
        self.assertNotIn('error', result)
        self.assertTrue(result['rows'])

    def test_chart_to_request(self):
        chart = self.env['bi.chart'].create({
            'name': 'Test Chart',
            'dataset_id': self.dataset.id,
            'chart_type': 'bar',
            'config_json': {
                'slots': {
                    'x': [{'field_id': self.f_country_name.id}],
                    'values': [{'field_id': self.f_latitude.id,
                                'agg': 'sum'}],
                },
                'filters': [{'field_id': self.f_name.id, 'op': 'like_i',
                             'value': 'BI Test'}],
                'limit': 100,
            },
        })
        request = chart._to_query_request(
            extra_filters=[{'field_id': self.f_latitude.id, 'op': 'gte',
                            'value': 15}])
        result = self.engine.run(request)
        total = sum(row[1] for row in result['rows'])
        self.assertEqual(total, 50.0)
