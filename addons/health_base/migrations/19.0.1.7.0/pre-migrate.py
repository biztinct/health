# -*- coding: utf-8 -*-
"""Preserve res.partner.gender / crm.lead.gender before Odoo drops them.

Same reason as every other conversion in this series: removing a field deletes
its ir.model.fields row at the end of the upgrade and DROPS THE COLUMN with it,
so the varchar has to be copied out while it still exists. `gender` is the one
vocabulary the migration import also writes, so an unrecoverable loss here
would be expensive.
"""
from odoo import api, SUPERUSER_ID

from odoo.addons.health_base.lookup_migration import snapshot_legacy_columns


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    snapshot_legacy_columns(env)
