# -*- coding: utf-8 -*-
from odoo.tests import tagged

from .common import BiCase


@tagged('biz_bi', 'post_install', '-at_install')
class TestGoldPublish(BiCase):

    def _relation_exists(self, name, kinds=('m',)):
        self.env.cr.execute(
            "SELECT relkind FROM pg_class WHERE relname = %s", (name,))
        row = self.env.cr.fetchone()
        return bool(row and row[0] in kinds)

    def test_silver_view_created(self):
        self.assertTrue(self._relation_exists(
            self.dataset._silver_view_name(), kinds=('v',)))

    def test_gold_publish_creates_matview_and_indexes(self):
        self.dataset.storage_mode = 'gold'
        self.dataset.action_publish()
        matview = self.dataset._gold_matview_name()
        self.assertTrue(self._relation_exists(matview))
        self.env.cr.execute("""
            SELECT indexname FROM pg_indexes WHERE tablename = %s
        """, (matview,))
        indexes = {row[0] for row in self.env.cr.fetchall()}
        self.assertIn('%s_pk' % matview, indexes)
        job = self.dataset.refresh_job_id
        self.assertTrue(job)
        self.assertEqual(job.state, 'idle')
        self.assertTrue(job.last_refresh)

    def test_gold_queries_hit_matview(self):
        self.dataset.storage_mode = 'gold'
        self.dataset.action_publish()
        result = self.engine.run(self._base_request())
        self.assertEqual(result['meta']['source'], 'gold')
        rows = {row[0]: row[1] for row in result['rows']}
        self.assertEqual(rows.get(self.country_a.name), 30.0)

    def test_concurrent_refresh_succeeds(self):
        self.dataset.storage_mode = 'gold'
        self.dataset.action_publish()
        job = self.dataset.refresh_job_id
        job._refresh_one()
        self.assertEqual(job.state, 'idle')
        self.assertFalse(job.last_error)

    def test_refresh_invalidates_cache(self):
        self.dataset.storage_mode = 'gold'
        self.dataset.action_publish()
        request = self._base_request()
        self.engine.run(request)
        cached = self.env['bi.query.cache'].search_count(
            [('dataset_id', '=', self.dataset.id)])
        self.assertTrue(cached)
        self.dataset.refresh_job_id._refresh_one()
        remaining = self.env['bi.query.cache'].search_count(
            [('dataset_id', '=', self.dataset.id)])
        self.assertFalse(remaining)

    def test_unlink_drops_relations(self):
        self.dataset.storage_mode = 'gold'
        self.dataset.action_publish()
        silver = self.dataset._silver_view_name()
        gold = self.dataset._gold_matview_name()
        self.dataset.unlink()
        self.assertFalse(self._relation_exists(silver, kinds=('v',)))
        self.assertFalse(self._relation_exists(gold))
