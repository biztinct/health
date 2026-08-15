# -*- coding: utf-8 -*-
"""Preserve crm.lead's pre-conversion gender values before Odoo drops them."""
from odoo import api, SUPERUSER_ID

from odoo.addons.health_base.lookup_migration import snapshot_legacy_columns


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    snapshot_legacy_columns(env)
