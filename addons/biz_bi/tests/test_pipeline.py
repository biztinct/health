# -*- coding: utf-8 -*-
from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('biz_bi', 'post_install', '-at_install')
class TestPipeline(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        # raw staging table simulating a messy CSV import
        env.cr.execute("""
            CREATE TABLE bi_test_raw (
                id serial PRIMARY KEY,
                full_name text,
                amount_raw text,
                created text
            )
        """)
        env.cr.execute("""
            INSERT INTO bi_test_raw (full_name, amount_raw, created) VALUES
            ('Alpha', '10,5', '2026-01-05'),
            ('Alpha', '20', '2026-01-06'),
            ('Beta', 'oops', '2026-01-07'),
            ('Gamma', '30.25', '2026-01-08')
        """)
        cls.source = env['bi.source'].create({
            'name': 'Raw Test', 'type': 'sql_view',
            'view_name': 'bi_test_raw'})
        cls.pipeline = env['bi.pipeline'].create({
            'source_id': cls.source.id,
            'steps_json': {'version': 1, 'steps': [
                {'id': 's1', 'type': 'rename',
                 'params': {'map': {'full_name': 'customer'}}},
                {'id': 's2', 'type': 'cast',
                 'params': {'col': 'amount_raw', 'to': 'numeric'}},
                {'id': 's3', 'type': 'calc',
                 'params': {'as': 'amount_double',
                            'expression': 'coalesce([amount_raw], 0) * 2'}},
                {'id': 's4', 'type': 'filter',
                 'params': {'conditions': [['customer', 'neq', 'Gamma']]}},
            ]},
        })

    def test_compile_and_apply(self):
        self.pipeline.action_apply()
        self.assertFalse(self.pipeline.last_error)
        self.assertTrue(self.source.has_active_pipeline)
        self.env.cr.execute(
            "SELECT customer, amount_raw, amount_double "
            "FROM bi_clean_%d ORDER BY id" % self.source.id)
        rows = self.env.cr.fetchall()
        # Gamma filtered out; 'oops' guarded to NULL; '10,5' -> 10.5
        self.assertEqual(len(rows), 3)
        self.assertEqual(float(rows[0][1]), 10.5)
        self.assertEqual(float(rows[0][2]), 21.0)
        self.assertIsNone(rows[2][1])  # 'oops'
        self.assertEqual(float(rows[2][2]), 0.0)  # coalesce -> 0 * 2

    def test_schema_follows_pipeline(self):
        self.pipeline.action_apply()
        columns = {c['name']: c['odoo_type']
                   for c in self.source._fetch_schema()}
        self.assertIn('customer', columns)
        self.assertNotIn('full_name', columns)
        self.assertEqual(columns['amount_raw'], 'float')
        self.assertIn('amount_double', columns)

    def test_dedupe(self):
        self.pipeline.steps_json = {'version': 1, 'steps': [
            {'id': 's1', 'type': 'dedupe',
             'params': {'keys': ['full_name'],
                        'order_by': [{'col': 'created', 'dir': 'desc'}]}},
        ]}
        self.pipeline.action_apply()
        self.env.cr.execute(
            "SELECT count(*) FROM bi_clean_%d" % self.source.id)
        self.assertEqual(self.env.cr.fetchone()[0], 3)  # Alpha deduped

    def test_rejects_hostile_input(self):
        hostile_cases = [
            [{'id': 's1', 'type': 'rename',
              'params': {'map': {'full_name': 'x"; DROP TABLE res_users;--'}}}],
            [{'id': 's1', 'type': 'filter',
              'params': {'conditions': [['nope', 'eq', 1]]}}],
            [{'id': 's1', 'type': 'calc',
              'params': {'as': 'x', 'expression': 'pg_sleep(10)'}}],
            [{'id': 's1', 'type': 'union_all', 'params': {}}],
        ]
        for steps in hostile_cases:
            self.pipeline.steps_json = {'version': 1, 'steps': steps}
            with self.assertRaises(UserError):
                self.pipeline.compile_sql()

    def test_editor_data_and_step_schemas(self):
        data = self.env['bi.pipeline'].get_editor_data(self.source.id)
        # schema BEFORE each of the 4 steps + implicit base
        self.assertEqual(len(data['schemas']), 5)
        self.assertIsNone(data['invalid_step'])
        base_cols = dict(data['schemas'][0])
        self.assertIn('full_name', base_cols)
        after_rename = dict(data['schemas'][1])
        self.assertIn('customer', after_rename)
        self.assertNotIn('full_name', after_rename)

    def test_save_steps_reports_invalid_step(self):
        data = self.env['bi.pipeline'].save_steps(self.source.id, [
            {'id': 's1', 'type': 'rename',
             'params': {'map': {'full_name': 'customer'}}},
            {'id': 's2', 'type': 'filter',
             'params': {'conditions': [['ghost_column', 'eq', 1]]}},
        ])
        self.assertEqual(data['invalid_step'], 1)
        self.assertIn('ghost_column', data['error'])

    def test_dataset_reads_clean_view(self):
        self.pipeline.action_apply()
        workspace = self.env['bi.workspace'].create({'name': 'P'})
        dataset = self.env['bi.dataset'].create({
            'name': 'Clean Data', 'workspace_id': workspace.id})
        node = self.env['bi.dataset.node'].create({
            'dataset_id': dataset.id, 'source_id': self.source.id,
            'is_root': True})
        node.action_scan_fields()
        amount = dataset.field_ids.filtered(
            lambda f: f.technical_name == 'amount_raw')
        amount.write({'role': 'measure', 'default_agg': 'sum',
                      'visibility': 'visible'})
        dataset.action_publish()
        result = self.env['bi.query.engine'].run({
            'dataset_id': dataset.id,
            'dimensions': [],
            'measures': [{'field_id': amount.id, 'agg': 'sum'}],
        })
        # The dataset reads the CLEANED view, so every step is visible in this
        # one number: '10,5' cast to 10.5, 'oops' guarded to NULL, and Gamma
        # (30.25) removed by the pipeline's filter step — 10.5 + 20 = 30.5.
        # The original literal (60.75) added Gamma back in and was therefore
        # red on every database, not only on one with live data.
        self.assertEqual(float(result['rows'][0][0]), 30.5)
        # and prove it is the clean view, not the raw table: a query over
        # `bi_test_raw` could not sum `amount_raw` at all (it is text there)
        self.assertEqual(self.source._table_name(),
                         self.pipeline._clean_view_name())


@tagged('biz_bi', 'post_install', '-at_install')
class TestSnapshot(TransactionCase):

    def test_snapshot_xlsx_builds(self):
        env = self.env
        workspace = env['bi.workspace'].create({'name': 'Snap'})
        source = env['bi.source'].create({
            'name': 'Partners Snap', 'type': 'odoo_model',
            'model_id': env['ir.model']._get_id('res.partner')})
        dataset = env['bi.dataset'].create({
            'name': 'Snap DS', 'workspace_id': workspace.id})
        node = env['bi.dataset.node'].create({
            'dataset_id': dataset.id, 'source_id': source.id,
            'is_root': True})
        node.action_scan_fields()
        name_field = dataset.field_ids.filtered(
            lambda f: f.technical_name == 'name')[:1]
        dataset.action_publish()
        chart = env['bi.chart'].create({
            'name': 'Partner Count', 'dataset_id': dataset.id,
            'chart_type': 'kpi',
            'config_json': {'slots': {'values': [
                {'field_id': name_field.id, 'agg': 'count'}]}},
        })
        dashboard = env['bi.dashboard'].create({
            'name': 'Snap Dash', 'workspace_id': workspace.id,
            'schedule_enabled': True, 'schedule_interval': 'daily',
        })
        env['bi.dashboard.widget'].create({
            'dashboard_id': dashboard.id, 'chart_id': chart.id})
        content = dashboard._build_snapshot_xlsx()
        self.assertTrue(content.startswith(b'PK'))  # xlsx = zip container
        self.assertGreater(len(content), 500)
        # a dashboard created with the schedule already on must be QUEUED —
        # `_process_snapshot_queue` selects on next_send, so an empty one is a
        # snapshot that never sends (the create() hole this phase closed)
        self.assertTrue(dashboard.next_send)
        self.assertGreater(dashboard.next_send, fields.Datetime.now())
        # ...and turning the schedule off must clear it again
        dashboard.schedule_enabled = False
        self.assertFalse(dashboard.next_send)
