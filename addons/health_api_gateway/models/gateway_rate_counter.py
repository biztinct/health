# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models

# NOTE (spec B.8): this fixed-window counter is a correctness FALLBACK, not
# DDoS protection. The throttle of record is the edge proxy (Traefik/Nginx)
# in front of Odoo — see the module README.
DEFAULT_LIMIT_PER_MIN = 120
DEFAULT_BURST = 240


class GatewayRateCounter(models.Model):
    _name = 'gateway.rate.counter'
    _description = 'API Gateway Rate Counter (fixed window fallback)'
    _log_access = False
    _rec_name = 'key_ref'

    key_ref = fields.Char(required=True, index=True)
    window_start = fields.Datetime(required=True)
    count = fields.Integer(default=0)

    _sql_constraints = [
        ('key_window_unique', 'unique(key_ref, window_start)',
         'One counter row per key and window.'),
    ]

    def init(self):
        # Odoo 19 no longer materializes _sql_constraints automatically, and
        # the ON CONFLICT upsert in hit() requires this unique index.
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS gateway_rate_counter_key_window_uidx
            ON gateway_rate_counter (key_ref, window_start)
        """)

    @api.model
    def hit(self, key_ref):
        """Increment the current 1-minute window counter for `key_ref` via
        atomic upsert. Returns ``(allowed: bool, retry_after: int seconds)``."""
        icp = self.env['ir.config_parameter'].sudo()
        try:
            limit = int(icp.get_param('gateway.rate_limit_per_min',
                                      DEFAULT_LIMIT_PER_MIN))
        except (TypeError, ValueError):
            limit = DEFAULT_LIMIT_PER_MIN
        try:
            burst = int(icp.get_param('gateway.rate_limit_burst', DEFAULT_BURST))
        except (TypeError, ValueError):
            burst = DEFAULT_BURST
        limit = max(limit, 1)
        burst = max(burst, limit)

        now = fields.Datetime.now()
        window = now.replace(second=0, microsecond=0)
        self.env.cr.execute(
            """
            INSERT INTO gateway_rate_counter (key_ref, window_start, count)
            VALUES (%s, %s, 1)
            ON CONFLICT (key_ref, window_start)
            DO UPDATE SET count = gateway_rate_counter.count + 1
            RETURNING count
            """,
            (key_ref, window),
        )
        count = self.env.cr.fetchone()[0]
        if count > burst or count > limit:
            retry_after = max(1, int((window + timedelta(minutes=1) - now)
                                     .total_seconds()))
            return False, retry_after
        return True, 0

    @api.model
    def _cron_prune(self):
        """Nightly prune of counter rows older than one hour (spec B.8)."""
        cutoff = fields.Datetime.now() - timedelta(hours=1)
        self.sudo().search([('window_start', '<', cutoff)]).unlink()
        return True
