# -*- coding: utf-8 -*-
"""An install hook does not fire on an upgrade (the A2 family, ledger H61).

Everything this module must be true of BOTH paths lives in an idempotent
function reachable from both. This is the upgrade half.
"""
import logging

from odoo.addons.health_tenancy.hooks import (
    ensure_feature_catalogue, wire_doors, wire_features,
)

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    from odoo import SUPERUSER_ID, api
    env = api.Environment(cr, SUPERUSER_ID, {})
    wire_doors(env)
    report = wire_features(env)
    ensure_feature_catalogue(env)
    _logger.info("health_tenancy 19.0.1.1.0: %d left-menu entries wired to a "
                 "part of the product.", len(report['wired']))
