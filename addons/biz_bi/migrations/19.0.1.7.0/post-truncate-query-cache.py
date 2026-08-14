# -*- coding: utf-8 -*-
"""BG-3 — drop every cached query envelope written before the grain cut moved.

`bi_query_cache` stores whole result envelopes keyed on (request, RLS
fingerprint, language, timezone). BG-3 changes what a grained request MEANS —
`DATE_TRUNC('month', col)` cut the month at UTC midnight, it now cuts it on
the viewer's wall clock — without changing the request payload, so a
pre-upgrade envelope is indistinguishable from a post-upgrade one and would be
served, with the old buckets, for the whole of its TTL (up to the gold
refresh interval).

The table is a cache: truncating it costs one recomputation per live query and
is the only way to guarantee nobody reads a stale cut. `post-` is the right
stage — this touches biz_bi's OWN table and no other module's registry
(conventions §5.135).
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    cr.execute("SELECT to_regclass('public.bi_query_cache')")
    if not cr.fetchone()[0]:
        _logger.info(
            "biz_bi BG-3: no bi_query_cache table, nothing to truncate")
        return
    cr.execute("SELECT count(*) FROM bi_query_cache")
    before = cr.fetchone()[0]
    cr.execute("TRUNCATE TABLE bi_query_cache")
    _logger.info(
        "biz_bi BG-3: truncated bi_query_cache — %s pre-BG-3 envelope(s) "
        "dropped so no stale UTC-cut grain bucket can be served", before)
