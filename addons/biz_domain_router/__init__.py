"""Loaded with --load=base,web,biz_domain_router before database selection."""
import logging
from odoo import http
from odoo.tools import config
from .router import domain_map, select_database

_logger = logging.getLogger(__name__)
_original = http.db_filter
if not getattr(_original, '_customer_domain_router', False):
    def db_filter(dbs, host=None, _fallback=_original):
        # Explicit single-database test runs must stay isolated from the fleet.
        if config['dbfilter'] and '%d' not in config['dbfilter'] and '%h' not in config['dbfilter']:
            return _fallback(dbs, host)
        if host is None:
            host = http.request.httprequest.environ.get('HTTP_HOST', '')
        try:
            mapping = domain_map()
        except Exception:
            _logger.error('Customer domain map unavailable; refusing database selection')
            return []
        return select_database(dbs, host, mapping, _fallback)
    db_filter._customer_domain_router = True
    http.db_filter = db_filter
