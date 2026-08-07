# -*- coding: utf-8 -*-
import hashlib
import json
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

MAX_CACHE_MB = 200


class BiQueryCache(models.Model):
    """Cross-worker query result cache. The key includes the user's RLS
    fingerprint and language, so two users with different row/column rules
    (or languages) never share an entry."""
    _name = 'bi.query.cache'
    _description = 'BI Query Cache'
    _log_access = False

    cache_key = fields.Char(required=True, index=True)
    dataset_id = fields.Many2one('bi.dataset', required=True,
                                 ondelete='cascade', index=True)
    result_json = fields.Json(required=True)
    created_at = fields.Datetime(default=fields.Datetime.now, required=True)
    expires_at = fields.Datetime(required=True, index=True)
    hit_count = fields.Integer(default=0)

    @api.model
    def make_key(self, request_payload, rls_fingerprint, lang):
        canonical = json.dumps(request_payload, sort_keys=True,
                               separators=(',', ':'), default=str)
        raw = '%s|%s|%s' % (canonical, rls_fingerprint, lang)
        return hashlib.sha256(raw.encode()).hexdigest()

    @api.model
    def fetch_result(self, cache_key):
        # NOT named fetch(): that is BaseModel.fetch(field_names), and
        # shadowing it with a different signature breaks every ORM read of
        # this model (a list view of the cache crashed on result_json).
        self.env.cr.execute("""
            UPDATE bi_query_cache
            SET hit_count = hit_count + 1
            WHERE cache_key = %s AND expires_at > (now() AT TIME ZONE 'UTC')
            RETURNING result_json
        """, (cache_key,))
        row = self.env.cr.fetchone()
        return row[0] if row else None

    @api.model
    def store(self, cache_key, dataset_id, result, ttl_seconds):
        self.env.cr.execute("""
            INSERT INTO bi_query_cache
                (cache_key, dataset_id, result_json, created_at,
                 expires_at, hit_count)
            VALUES (%s, %s, %s, now() AT TIME ZONE 'UTC',
                    (now() AT TIME ZONE 'UTC') + (%s || ' seconds')::interval,
                    0)
            ON CONFLICT DO NOTHING
        """, (cache_key, dataset_id, json.dumps(result, default=str),
              ttl_seconds))

    @api.model
    def invalidate_dataset(self, dataset_id):
        self.env.cr.execute(
            "DELETE FROM bi_query_cache WHERE dataset_id = %s", (dataset_id,))

    @api.model
    def _vacuum(self):
        """Hourly cron: drop expired rows; LRU-trim if the table outgrows
        the configured budget."""
        self.env.cr.execute(
            "DELETE FROM bi_query_cache "
            "WHERE expires_at <= (now() AT TIME ZONE 'UTC')")
        self.env.cr.execute(
            "SELECT pg_total_relation_size('bi_query_cache')")
        size = self.env.cr.fetchone()[0]
        budget = int(self.env['ir.config_parameter'].sudo().get_param(
            'biz_bi.cache_budget_mb', MAX_CACHE_MB)) * 1024 * 1024
        if size > budget:
            self.env.cr.execute("""
                DELETE FROM bi_query_cache WHERE id IN (
                    SELECT id FROM bi_query_cache
                    ORDER BY hit_count ASC, created_at ASC
                    LIMIT (SELECT GREATEST(count(*) / 2, 1)
                           FROM bi_query_cache)
                )
            """)
            _logger.info("biz_bi: cache LRU-trimmed (was %s bytes)", size)
