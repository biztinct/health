# -*- coding: utf-8 -*-
"""Family page "on the way" state (handover §2.2).

When the nurse taps "Đang đến (On my way)" in the PWA, a ``travel_start``
EVV event is posted for the visit. This inherit teaches the family page's
render context to surface that: an UPCOMING visit with a fresh
``travel_start`` flips to ``mode='on_the_way'`` and, when both endpoints'
coordinates are known, shows an honest haversine ETA.

Design constraints honored:
- ``arrived`` / ``completed`` take precedence automatically — super()
  returns them before this hook ever looks at travel events.
- No new FSO fields, no polling model, no fake precision. The travel EVV
  event IS the record; the ETA is a straight-line estimate only.
- A 3-hour staleness guard: a forgotten "On my way" tap must not show
  "on the way" all day.
"""
import logging
from datetime import timedelta

from odoo import fields, models

_logger = logging.getLogger(__name__)

# Straight-line ETA assumptions (handover §2.2).
_URBAN_SPEED_KMH = 25.0
_ETA_ROUND_TO_MIN = 5     # round UP to the nearest 5 minutes
_ETA_FLOOR_MIN = 5        # never show less than 5 minutes
# A travel_start older than this is treated as stale (forgotten tap).
_TRAVEL_FRESH_HOURS = 3


class HealthFamilyLink(models.Model):
    _inherit = 'health.family.link'

    def _latest_travel_event(self):
        """The most recent travel_start/travel_cancel for this visit, in
        chain order (server-assigned ``sequence`` is monotonic per FSO and
        survives offline re-sequencing)."""
        self.ensure_one()
        return self.env['health.evv.event'].sudo().search(
            [('fso_id', '=', self.fso_id.id),
             ('event_type', 'in', ('travel_start', 'travel_cancel'))],
            order='sequence desc, id desc', limit=1)

    def _travel_eta_text(self, event):
        """"khoảng X phút (about X min)" from a straight-line haversine of
        the travel event's GPS to the patient's home, or '' when either
        endpoint's coordinates are missing (no fake precision)."""
        from odoo.addons.health_base.models.geo_utils import haversine_km
        patient = self.fso_id.patient_id
        ev_lat, ev_lng = event.lat, event.lng
        pt_lat = patient.partner_latitude if patient else 0.0
        pt_lng = patient.partner_longitude if patient else 0.0
        if not (ev_lat and ev_lng and pt_lat and pt_lng):
            return ''
        km = haversine_km(ev_lat, ev_lng, pt_lat, pt_lng)
        if km is None:
            return ''
        minutes = (km / _URBAN_SPEED_KMH) * 60.0
        # Round UP to the nearest 5, floor at 5.
        rounded = int(-(-minutes // _ETA_ROUND_TO_MIN)) * _ETA_ROUND_TO_MIN
        rounded = max(rounded, _ETA_FLOOR_MIN)
        return 'khoảng %s phút (about %s min)' % (rounded, rounded)

    def _page_context(self):
        ctx = super()._page_context()
        if ctx.get('mode') != 'upcoming':
            return ctx
        event = self._latest_travel_event()
        if not event or event.event_type != 'travel_start':
            return ctx
        # Staleness guard — a forgotten tap must not show "on the way" all
        # day. Freshness is measured from the tap (event_datetime, UTC).
        started = event.event_datetime
        if not started or started < (
                fields.Datetime.now() - timedelta(hours=_TRAVEL_FRESH_HOURS)):
            return ctx
        ctx = dict(ctx)
        ctx['mode'] = 'on_the_way'
        ctx['eta_text'] = self._travel_eta_text(event)
        return ctx
