import math

from odoo import api, models


class HealthFieldserviceOrderEvvExemption(models.Model):
    """EVV geofence exemption for online visits (handover §2.5).

    Shipped defect this module owns: ``_compute_evv_status`` requires
    check-in AND check-out to be ``inside_geofence`` (measured against the
    patient's home coords), so an ONLINE visit — where staff are never at the
    patient's home — can NEVER verify. Fix, surgically: after the base
    compute, recompute ONLY online orders treating geofence as satisfied and
    dropping the physical-signature requirement (verification is event
    presence alone — a valid chain with a check-in and a check-out). Home /
    clinic orders are untouched (proven by re-running /health_evv).

    Distance data stays recorded on the events; only the verified verdict is
    branched.
    """
    _inherit = 'health.fieldservice.order'

    @api.depends('evv_event_ids', 'evv_event_ids.inside_geofence',
                 'evv_event_ids.chain_valid', 'evv_event_ids.event_type',
                 'evv_event_ids.event_datetime', 'scheduled_duration',
                 'actual_start_datetime', 'actual_end_datetime',
                 'service_location')
    def _compute_evv_status(self):
        super()._compute_evv_status()
        for order in self:
            if order.service_location != 'online':
                continue
            events = order.evv_event_ids.sorted(
                key=lambda event: (event.sequence, event.id))
            if not events:
                continue
            chain_valid = bool(all(event.chain_valid for event in events))
            checkin = events.filtered(
                lambda event: event.event_type == 'checkin')[:1]
            checkout = events.filtered(
                lambda event: event.event_type == 'checkout')[-1:]
            # Geofence treated as satisfied; no signature required for online.
            verified = bool(chain_valid and checkin and checkout)
            order.evv_verified = verified
            units = 0.0
            if verified and checkout.event_datetime and checkin.event_datetime:
                hours = (checkout.event_datetime
                         - checkin.event_datetime).total_seconds() / 3600.0
                units = math.floor(max(hours, 0.0) * 4.0) / 4.0
                if order.scheduled_duration:
                    units = min(
                        units, order.scheduled_duration / 60.0 + 0.5)
            order.evv_verified_units = units
