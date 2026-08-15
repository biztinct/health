# -*- coding: utf-8 -*-
"""Re-seed the vocabularies and re-run health_base's own back-fill.

Picks up vocabulary values added after the first rollout — notably the two
legacy `service_interest` codes the first back-fill reported as unmappable.
"""
from odoo import api, SUPERUSER_ID

from odoo.addons.health_base.lookup_migration import (
    backfill_module,
    seed_lookup_values,
)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    seed_lookup_values(env)
    backfill_module(env, 'health_base')
