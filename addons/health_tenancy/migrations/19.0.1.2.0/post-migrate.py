# -*- coding: utf-8 -*-
"""An install hook does not fire on an upgrade (the A2 family, ledger H61).

SAAS H4d's half: the plans this product sells have to reach the cockpit's table
on an upgrade as well as on an install. Measured on the rehearsal — the
cockpit's own data file ran before this module had been imported, read an empty
registry, and seeded nothing.
"""
import logging

from odoo.addons.health_tenancy.hooks import (
    ensure_feature_catalogue, ensure_plan_catalogue, wire_doors, wire_features,
)

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    from odoo import SUPERUSER_ID, api
    env = api.Environment(cr, SUPERUSER_ID, {})
    wire_doors(env)
    wire_features(env)
    ensure_feature_catalogue(env)
    made = ensure_plan_catalogue(env)
    _logger.info("health_tenancy 19.0.1.2.0: %d plans seeded into the "
                 "cockpit's table.", made)
