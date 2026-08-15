# -*- coding: utf-8 -*-
"""Preserve the pre-conversion Selection values before Odoo drops them.

Runs PRE, deliberately: Odoo removes the `ir.model.fields` row for a deleted
field at the end of an upgrade and drops its column with it. Any old value not
captured before that point is gone — which is exactly how the `home_visit` /
`clinic_visit` crm.lead interests were lost on the first UAT run.

Idempotent, and a no-op on a database whose columns have already gone.
"""
from odoo import api, SUPERUSER_ID

from odoo.addons.health_base.lookup_migration import snapshot_legacy_columns


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    snapshot_legacy_columns(env)
