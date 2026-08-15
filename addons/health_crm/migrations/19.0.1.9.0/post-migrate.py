# -*- coding: utf-8 -*-
"""crm.lead.gender -> gender_id, on the shared conversion machinery.

The lead's gender mirrors res.partner's and shares the same `gender`
vocabulary, so it back-fills from the same codes. health_base seeds the
vocabulary; this only has to repoint the column.
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
    backfill_module(env, 'health_crm')
