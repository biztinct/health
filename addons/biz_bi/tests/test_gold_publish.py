# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tools import SQL

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

    def test_missing_matview_falls_back_to_live_and_self_heals(self):
        """A gold dataset whose matview vanished (restored DB, cascade drop)
        must not error every query while its job reports idle — the health
        check consults the catalog, the engine falls back to live, and the
        next refresh recreates the matview instead of failing forever."""
        self.dataset.storage_mode = 'gold'
        self.dataset.action_publish()
        matview = self.dataset._gold_matview_name()
        job = self.dataset.refresh_job_id

        self.env.cr.execute(SQL(
            "DROP MATERIALIZED VIEW %s CASCADE", SQL.identifier(matview)))
        self.assertEqual(job.state, 'idle')          # the job has no idea
        self.assertFalse(job.is_healthy())           # the catalog knows

        result = self.engine.run(self._base_request())
        self.assertNotIn('error', result)
        self.assertEqual(result['meta']['source'], 'live',
                         "queries must fall back to live, not crash on gold")

        job._refresh_one()                           # heals: full republish
        self.assertTrue(self._relation_exists(matview))
        self.assertTrue(job.is_healthy())
        self.assertEqual(job.state, 'idle')
        healed = self.engine.run(self._base_request())
        self.assertEqual(healed['meta']['source'], 'gold')

    def test_stale_column_does_not_kill_publish(self):
        """A column dropped from the source model after the scan must not
        fail the whole dataset's publish (Visit Margin lost its matview to
        one stale hidden field) — it is skipped, and everything else works."""
        stale = self.env['bi.field'].create({
            'dataset_id': self.dataset.id,
            'node_id': self.node_root.id,
            'technical_name': 'column_dropped_long_ago',
            'name': 'Ghost Column',
            'origin': 'stored',
            'data_type': 'text',
            'role': 'dimension',
            'visibility': 'hidden',
        })
        self.assertIn(stale, self.dataset._stale_stored_fields())
        self.dataset.storage_mode = 'gold'
        self.dataset.action_publish()               # must not raise
        self.assertTrue(self._relation_exists(self.dataset._gold_matview_name()))
        result = self.engine.run(self._base_request())
        self.assertNotIn('error', result)
        self.assertEqual(result['meta']['source'], 'gold')
