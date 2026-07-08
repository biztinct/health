# -*- coding: utf-8 -*-
"""Two new EVV event types: travel_start / travel_cancel.

An "On my way" tap in the PWA posts a ``travel_start`` event through the
EXISTING EVV endpoints (evv_api.py) and the EXISTING offline queue
(evv-queue.js). The hash chain is untouched by design: the canonical
payload recipe already treats ``event_type`` as ordinary hashed data
(health_evv/models/health_evv_event.py::_canonical_payload_bytes), so a
new type extends the chain without breaking it.

Inspection findings (handover §2.1 report-back a/b/c), verified Jul 2026:

(a) The EVV controller does NOT validate ``event_type`` against a
    hardcoded whitelist — evv_api.py passes ``body.get('event_type')``
    straight to ``append_event``; the ONLY special case is
    ``event_type == 'checkin'`` (auto start-service). So a new type is
    accepted with no controller change. The Selection field itself is
    the validator, which is exactly what this ``selection_add`` extends.
(b) Geofence: ``_compute_distance`` runs for every event and stores
    ``inside_geofence`` / ``distance_m``, but nothing REJECTS an event
    for being outside the fence — and ``_compute_evv_status`` reads
    ``inside_geofence`` ONLY on the check-in and check-out events. A
    travel event posted away from the home therefore records a large
    distance as inert data; it never creates a "violation" and never
    affects ``evv_verified``. No geofence change needed.
(c) Enumerations: the FSO EVV computes filter strictly on
    ``'checkin'`` / ``'checkout'`` / ``'signature'`` — travel events are
    ignored by every stage gate and the verified-units math. The report
    and list views render ``event_type`` generically. So travel events
    neither satisfy nor break any gate.
"""
from odoo import fields, models


class HealthEvvEvent(models.Model):
    _inherit = 'health.evv.event'

    event_type = fields.Selection(
        selection_add=[
            ('travel_start', 'Travel Start'),
            ('travel_cancel', 'Travel Cancel'),
        ],
        ondelete={
            'travel_start': 'cascade',
            'travel_cancel': 'cascade',
        },
    )
