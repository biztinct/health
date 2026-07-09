# -*- coding: utf-8 -*-
"""Family "on the way" ETA upgrade (handover §2.6).

Overrides ``_travel_eta_text`` so the family page's "on the way" ETA uses
cached ROAD minutes (health.route.leg) instead of the 25 km/h straight-line
haversine. On None / 'unknown' / any exception it falls back to super() (the
haversine estimate) — no template change, same "khoảng X phút (about X min)"
string with the same round-up-to-5 / floor-5 rules.
"""
import logging

from odoo import models

_logger = logging.getLogger(__name__)

_ETA_ROUND_TO_MIN = 5
_ETA_FLOOR_MIN = 5


class HealthFamilyLink(models.Model):
    _inherit = 'health.family.link'

    def _travel_eta_text(self, event):
        try:
            patient = self.fso_id.patient_id
            if patient:
                leg = self.env['health.route.leg'].leg_minutes(
                    event.lat, event.lng,
                    patient.partner_latitude, patient.partner_longitude)
                if leg.get('minutes') is not None and leg.get('method') != 'unknown':
                    minutes = leg['minutes']
                    rounded = int(-(-minutes // _ETA_ROUND_TO_MIN)) * _ETA_ROUND_TO_MIN
                    rounded = max(rounded, _ETA_FLOOR_MIN)
                    return 'khoảng %s phút (about %s min)' % (rounded, rounded)
        except Exception as exc:  # noqa: BLE001 — fall back to the haversine estimate
            _logger.debug('route ETA upgrade skipped: %s', exc)
        return super()._travel_eta_text(event)
