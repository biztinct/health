# -*- coding: utf-8 -*-
"""``health.route.leg`` — the distance cache (handover §2.1).

Every routed origin→destination pair in this module goes through
``leg_minutes()``: external routers are slow and rate-limited, so a pair is
computed once (via ``health_base.geo_utils.driving_distance`` — Google→OSRM→
approx) and stored, keyed on the coordinate 4-tuple rounded to 4 dp (~11 m).

Travel is treated as SYMMETRIC in v1 (A→B and B→A share one row) — the key is
normalized so the two directions collapse. When
``health_routes.use_external_router`` is False (the vietuat default) the
lookup skips straight to the deterministic 1.3×-haversine @ 30 km/h approx
tier — no network — and still caches the result.
"""
import logging

from odoo import api, fields, models
from odoo.addons.health_base.models.geo_utils import (
    driving_distance, haversine_km,
)

_logger = logging.getLogger(__name__)

_DEFAULT_TTL_DAYS = 30


class HealthRouteLeg(models.Model):
    _name = 'health.route.leg'
    _description = 'Route Leg Distance Cache'
    _order = 'computed_at desc, id desc'

    o_lat = fields.Float('Origin Lat', digits=(16, 4), required=True)
    o_lng = fields.Float('Origin Lng', digits=(16, 4), required=True)
    d_lat = fields.Float('Dest Lat', digits=(16, 4), required=True)
    d_lng = fields.Float('Dest Lng', digits=(16, 4), required=True)
    km = fields.Float('Distance (km)')
    minutes = fields.Float('Travel (minutes)')
    method = fields.Char('Method', help="google | osrm | approx | district | unknown")
    computed_at = fields.Datetime('Computed At')

    def init(self):
        # Ledger §1: _sql_constraints are not materialized — create the unique
        # cache-key index by hand. The key is stored already-normalized so the
        # symmetric pair shares one row.
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS health_route_leg_key_uidx
            ON health_route_leg (o_lat, o_lng, d_lat, d_lng)
        """)

    # ------------------------------------------------------------------
    # Key normalization (symmetric)
    # ------------------------------------------------------------------
    @staticmethod
    def _norm_key(o_lat, o_lng, d_lat, d_lng):
        """Round to 4 dp and order the endpoints so A→B and B→A collapse to
        one key. Returns (o_lat, o_lng, d_lat, d_lng) or None if any coord is
        missing/falsy."""
        if not (o_lat and o_lng and d_lat and d_lng):
            return None
        a = (round(float(o_lat), 4), round(float(o_lng), 4))
        b = (round(float(d_lat), 4), round(float(d_lng), 4))
        lo, hi = (a, b) if a <= b else (b, a)
        return (lo[0], lo[1], hi[0], hi[1])

    def _ttl_days(self):
        val = self.env['ir.config_parameter'].sudo().get_param(
            'health_routes.leg_ttl_days')
        try:
            return int(val) if val else _DEFAULT_TTL_DAYS
        except (TypeError, ValueError):
            return _DEFAULT_TTL_DAYS

    def _use_external_router(self):
        val = self.env['ir.config_parameter'].sudo().get_param(
            'health_routes.use_external_router')
        # Default OFF (vietuat must not hammer public OSRM).
        return str(val).lower() in ('1', 'true', 'yes')

    # ------------------------------------------------------------------
    # Computation
    # ------------------------------------------------------------------
    def _compute_leg(self, o_lat, o_lng, d_lat, d_lng):
        """Return {km, minutes, method} for a coordinate pair. Honors the
        use_external_router switch (off → approx-only, no network)."""
        if self._use_external_router():
            res = driving_distance(self.env, o_lat, o_lng, d_lat, d_lng)
            if res:
                return res
        # Approx tier, computed locally (mirrors geo_utils.driving_distance's
        # fallback: ~1.3× crow-flies @ 30 km/h) — deterministic, no request.
        crow = haversine_km(o_lat, o_lng, d_lat, d_lng)
        km = round(crow * 1.3, 2)
        return {'km': km, 'minutes': round(km / 30.0 * 60.0, 1), 'method': 'approx'}

    # ------------------------------------------------------------------
    # Public accessor
    # ------------------------------------------------------------------
    @api.model
    def leg_minutes(self, o_lat, o_lng, d_lat, d_lng):
        """Search-first cache accessor. Returns {km, minutes, method}; a
        missing coordinate yields {method:'unknown', minutes:None, km:None}
        (callers must degrade to "unknown", never crash / never fake)."""
        key = self._norm_key(o_lat, o_lng, d_lat, d_lng)
        if key is None:
            return {'km': None, 'minutes': None, 'method': 'unknown'}
        k_olat, k_olng, k_dlat, k_dlng = key
        row = self.sudo().search([
            ('o_lat', '=', k_olat), ('o_lng', '=', k_olng),
            ('d_lat', '=', k_dlat), ('d_lng', '=', k_dlng),
        ], limit=1)
        now = fields.Datetime.now()
        if row and row.computed_at:
            from datetime import timedelta
            if row.computed_at > now - timedelta(days=self._ttl_days()):
                return {'km': row.km, 'minutes': row.minutes,
                        'method': row.method}
        res = self._compute_leg(k_olat, k_olng, k_dlat, k_dlng)
        vals = {
            'o_lat': k_olat, 'o_lng': k_olng, 'd_lat': k_dlat, 'd_lng': k_dlng,
            'km': res.get('km'), 'minutes': res.get('minutes'),
            'method': res.get('method'), 'computed_at': now,
        }
        try:
            if row:
                row.sudo().write(vals)   # TTL refresh
            else:
                self.sudo().create(vals)
        except Exception as exc:  # noqa: BLE001 — a cache write must never break a lookup
            _logger.warning('route.leg: could not cache %s: %s', key, exc)
        return res
