# -*- coding: utf-8 -*-
"""Tier 2 of the Selection -> Many2one conversion for health_consent.

Snapshot FIRST: Odoo drops the old column when it removes the field at the end
of the upgrade, so this pre-migrate equivalent inside post is not enough on its
own — see the module's pre-migrate. Here we seed the new vocabularies and point
the new Many2one at the row whose code matches the retired Selection value.

Tier 2 differs from Tier 1 only in that python compared these values, so each
converted model also gained a `<field>_code` related field and the comparisons
now read that.
"""
from odoo import api, SUPERUSER_ID

from odoo.addons.health_base.lookup_migration import (
    backfill_module,
    seed_lookup_values,
    snapshot_legacy_columns,
)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    seed_lookup_values(env)
    backfill_module(env, 'health_consent')
