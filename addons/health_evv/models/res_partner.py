# -*- coding: utf-8 -*-
from odoo import fields, models


class ResPartner(models.Model):
    """Geofence configuration on the client (spec A.2.1).

    The geofence centre reuses the existing geocoded coordinates
    ``partner_latitude`` / ``partner_longitude`` maintained by
    health_base (auto-geocoded on address write) — no new geocoding here.
    """
    _inherit = 'res.partner'

    geofence_radius_m = fields.Integer(
        string='Geofence Radius (m)',
        default=150,
        help='Geofence radius in metres around the geocoded home location '
             '(partner_latitude / partner_longitude) used for EVV '
             'check-in/check-out verification.',
    )
    geofence_enabled = fields.Boolean(
        string='Geofence Enabled',
        default=True,
        help='Disable per client when GPS is unreliable at the location '
             '(e.g. apartment towers).',
    )
